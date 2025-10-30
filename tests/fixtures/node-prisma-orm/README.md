# Node Prisma ORM Fixture

Prisma ORM fixture for testing schema extraction, relationship tracking, ORM query patterns, and taint flows through Prisma client.

## Purpose

Simulates a production Prisma application with:
- Comprehensive Prisma schema (9 models, 15+ relationships)
- One-to-one, one-to-many, many-to-many relationships
- Cascade delete relationships
- Complex nested queries with deep includes
- Prisma transactions
- ORM query patterns (findUnique, findMany, create, update, delete)
- Taint flows through Prisma client queries
- Many-to-many join tables

## Prisma Schema (188 lines)

### Models and Relationships

#### User Model
```prisma
model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  username  String   @unique
  password  String
  role      Role     @default(USER)

  // One-to-one relationship (User -> Profile)
  profile   Profile?

  // One-to-many relationships
  posts     Post[]
  comments  Comment[]
  sessions  Session[]
}
```

**Relationships**:
- One-to-one: User -> Profile (CASCADE delete)
- One-to-many: User -> Posts (CASCADE delete)
- One-to-many: User -> Comments (CASCADE delete)
- One-to-many: User -> Sessions (CASCADE delete)

#### Post Model with Many-to-Many
```prisma
model Post {
  id          Int      @id @default(autoincrement())
  title       String
  content     String
  published   Boolean  @default(false)
  viewCount   Int      @default(0)

  // One-to-many relationship (Post -> User)
  authorId    Int
  author      User     @relation(fields: [authorId], references: [id], onDelete: Cascade)

  // One-to-many relationship (Post -> Comments)
  comments    Comment[]

  // Many-to-many relationships via join tables
  tags        PostTag[]
  categories  PostCategory[]
}
```

**Relationships**:
- One-to-many: Post -> User (CASCADE delete)
- One-to-many: Post -> Comments (CASCADE delete)
- Many-to-many: Post <-> Tags (via PostTag join table, CASCADE)
- Many-to-many: Post <-> Categories (via PostCategory join table, CASCADE)

#### Join Tables for Many-to-Many
```prisma
// Post <-> Tag many-to-many
model PostTag {
  id        Int      @id @default(autoincrement())
  postId    Int
  tagId     Int

  post      Post     @relation(fields: [postId], references: [id], onDelete: Cascade)
  tag       Tag      @relation(fields: [tagId], references: [id], onDelete: Cascade)

  @@unique([postId, tagId])
}

// Post <-> Category many-to-many
model PostCategory {
  id         Int      @id @default(autoincrement())
  postId     Int
  categoryId Int

  post       Post     @relation(fields: [postId], references: [id], onDelete: Cascade)
  category   Category @relation(fields: [categoryId], references: [id], onDelete: Cascade)

  @@unique([postId, categoryId])
}
```

**Tests**: Many-to-many join table extraction, compound unique constraints

## Service Functions

### 1. User Service (190 lines)

#### getUserById - Deep Nested Includes
```javascript
async function getUserById(userId) {
  // TAINT FLOW: userId -> Prisma query
  const user = await prisma.user.findUnique({
    where: { id: userId },
    include: {
      profile: true,
      posts: {
        where: { published: true },
        include: {
          tags: {
            include: {
              tag: true  // Deep nesting: user -> posts -> tags -> tag
            }
          },
          categories: {
            include: {
              category: true  // Deep nesting: user -> posts -> categories -> category
            }
          }
        }
      },
      _count: {
        select: {
          posts: true,
          comments: true
        }
      }
    }
  });

  return user;
}
```

**Tests**:
- Deep nested includes (3 levels)
- _count aggregation
- Taint flow: userId (param) -> Prisma query

#### createUser - Nested Create
```javascript
async function createUser(userData) {
  const { email, username, password, bio, website } = userData;

  // TAINT FLOW: userData -> Prisma nested create
  const user = await prisma.user.create({
    data: {
      email,
      username,
      password,
      profile: {
        create: {
          bio: bio || null,
          website: website || null
        }
      }
    },
    include: {
      profile: true
    }
  });

  return user;
}
```

**Tests**:
- Nested create (User with Profile)
- Taint from request body -> ORM create

#### searchUsers - Multi-Source Taint
```javascript
async function searchUsers(searchTerm) {
  // TAINT FLOW: searchTerm -> Prisma query with OR
  const users = await prisma.user.findMany({
    where: {
      OR: [
        { username: { contains: searchTerm, mode: 'insensitive' } },
        { email: { contains: searchTerm, mode: 'insensitive' } }
      ]
    },
    include: {
      profile: true,
      _count: {
        select: { posts: true, comments: true }
      }
    }
  });

  return users;
}
```

**Tests**:
- OR queries
- Case-insensitive search
- Multi-source taint (username OR email)

#### deleteUser - Cascade Delete
```javascript
async function deleteUser(userId) {
  // TAINT FLOW: userId -> Prisma delete (cascades to profile, posts, comments, sessions)
  const user = await prisma.user.delete({
    where: { id: userId }
  });

  return user;
}
```

**Tests**:
- Cascade delete relationships
- Side effects: deletes profile, posts, comments, sessions

### 2. Post Service (279 lines)

#### getPostById - Complex Nested Includes
```javascript
async function getPostById(postId) {
  // TAINT FLOW: postId -> Prisma query
  const post = await prisma.post.findUnique({
    where: { id: postId },
    include: {
      author: {
        include: {
          profile: true  // Nested: post -> author -> profile
        }
      },
      comments: {
        include: {
          author: {
            select: {
              id: true,
              username: true
            }
          }
        }
      },
      tags: {
        include: {
          tag: true  // Many-to-many: post -> postTag -> tag
        }
      },
      categories: {
        include: {
          category: true  // Many-to-many: post -> postCategory -> category
        }
      }
    }
  });

  return post;
}
```

**Tests**:
- Deep nested includes across multiple relationships
- Many-to-many relationship traversal
- Select vs include patterns

#### createPost - Nested Create with Many-to-Many
```javascript
async function createPost(authorId, postData) {
  const { title, content, tagIds, categoryIds } = postData;

  // MULTI-SOURCE TAINT: authorId + postData -> Prisma nested create
  const post = await prisma.post.create({
    data: {
      title,
      content,
      authorId,
      tags: {
        create: tagIds.map(tagId => ({
          tag: {
            connect: { id: tagId }  // Connect to existing tags
          }
        }))
      },
      categories: {
        create: categoryIds.map(categoryId => ({
          category: {
            connect: { id: categoryId }  // Connect to existing categories
          }
        }))
      }
    }
  });

  return post;
}
```

**Tests**:
- Nested create with many-to-many relationships
- Connect operations for existing records
- Multi-source taint (authorId + tagIds + categoryIds)

#### updatePostTags - Prisma Transaction
```javascript
async function updatePostTags(postId, tagIds) {
  // MULTI-SOURCE TAINT: postId + tagIds -> Prisma transaction
  const post = await prisma.$transaction(async (tx) => {
    // Delete existing tags
    await tx.postTag.deleteMany({
      where: { postId }
    });

    // Create new tag associations
    await tx.postTag.createMany({
      data: tagIds.map(tagId => ({
        postId,
        tagId
      }))
    });

    // Return updated post
    return tx.post.findUnique({
      where: { id: postId },
      include: {
        tags: {
          include: {
            tag: true
          }
        }
      }
    });
  });

  return post;
}
```

**Tests**:
- Prisma transactions ($transaction)
- Atomic operations (deleteMany + createMany)
- Join table manipulation

#### searchPosts - Complex Filters
```javascript
async function searchPosts(searchTerm, tagName = null) {
  const filters = [];

  // MULTI-SOURCE TAINT: searchTerm + tagName -> Prisma query
  if (searchTerm) {
    filters.push({
      OR: [
        { title: { contains: searchTerm, mode: 'insensitive' } },
        { content: { contains: searchTerm, mode: 'insensitive' } }
      ]
    });
  }

  if (tagName) {
    filters.push({
      tags: {
        some: {
          tag: {
            name: { equals: tagName, mode: 'insensitive' }
          }
        }
      }
    });
  }

  const posts = await prisma.post.findMany({
    where: {
      AND: [
        { published: true },
        ...filters
      ]
    },
    orderBy: { createdAt: 'desc' },
    take: 50
  });

  return posts;
}
```

**Tests**:
- Dynamic filter building
- AND/OR query composition
- Multi-source taint (searchTerm + tagName)

#### getPostsByAuthor - Pagination
```javascript
async function getPostsByAuthor(authorId, page = 1, limit = 10) {
  const skip = (page - 1) * limit;

  // MULTI-SOURCE TAINT: authorId + page + limit -> Prisma query
  const posts = await prisma.post.findMany({
    where: { authorId },
    skip,
    take: limit,
    orderBy: { createdAt: 'desc' }
  });

  const total = await prisma.post.count({
    where: { authorId }
  });

  return {
    posts,
    total,
    page,
    totalPages: Math.ceil(total / limit)
  };
}
```

**Tests**:
- Pagination (skip/take)
- Count queries
- Multi-source taint (authorId + page + limit)

## Populated Tables

| Table | Row Count (est) | Purpose |
|---|---|---|
| `orm_models` | 9 | Prisma models (User, Post, Comment, etc.) |
| `orm_fields` | 50+ | Model fields with types |
| `orm_relationships` | 30+ | Bidirectional relationships with cascade flags |
| `symbols` | 20+ | Service functions, models |
| `function_calls` | 25+ | Prisma client query calls |

## Sample Verification Queries

### Find all Prisma models

```sql
SELECT
  name,
  type,
  path,
  line
FROM symbols
WHERE path LIKE '%node-prisma-orm/prisma/schema.prisma'
  AND type IN ('model', 'class')
ORDER BY name;
```

**Expected**: 9 models (User, Profile, Post, Comment, Category, Tag, PostTag, PostCategory, Session)

### Find one-to-one relationships

```sql
SELECT
  source_model,
  target_model,
  relationship_type,
  cascade_delete
FROM orm_relationships
WHERE file LIKE '%node-prisma-orm%'
  AND relationship_type = 'one_to_one'
ORDER BY source_model, target_model;
```

**Expected**: 2 relationships (User -> Profile bidirectional)

### Find many-to-many relationships

```sql
SELECT
  source_model,
  target_model,
  relationship_type,
  join_table
FROM orm_relationships
WHERE file LIKE '%node-prisma-orm%'
  AND relationship_type = 'many_to_many'
ORDER BY source_model, target_model;
```

**Expected**: 4 relationships (Post <-> Tags, Post <-> Categories bidirectional)

### Find relationships with cascade delete

```sql
SELECT
  source_model,
  target_model,
  relationship_type,
  cascade_delete
FROM orm_relationships
WHERE file LIKE '%node-prisma-orm%'
  AND cascade_delete = 1
ORDER BY source_model, target_model;
```

**Expected**: 8+ relationships with onDelete: Cascade

### Find Prisma client queries

```sql
SELECT
  function_name,
  callee_function,
  file,
  line
FROM function_calls
WHERE file LIKE '%node-prisma-orm/services/%'
  AND (
    callee_function LIKE '%findUnique%'
    OR callee_function LIKE '%findMany%'
    OR callee_function LIKE '%create%'
  )
ORDER BY file, line;
```

**Expected**: 10+ Prisma queries

## Testing Use Cases

1. **Prisma Schema Extraction**: Verify all models, fields, and relationships extracted
2. **ORM Relationships**: Test one-to-one, one-to-many, many-to-many relationships
3. **Cascade Delete**: Test cascade delete flag in orm_relationships
4. **Nested Queries**: Test deep nested includes extraction
5. **Prisma Transactions**: Test $transaction usage
6. **Taint Flows**: Test userId/searchTerm -> Prisma queries
7. **Join Tables**: Test many-to-many join table extraction

## How to Use

### 1. Index from TheAuditor Root

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud index
```

### 2. Query Extracted Data

```bash
# Find all Prisma models
aud context query --table orm_models --filter "file LIKE '%node-prisma-orm%'"

# Find cascade delete relationships
aud context query --table orm_relationships --filter "cascade_delete = 1"
```

### 3. Run Taint Analysis

```bash
# Detect tainted inputs in ORM queries
aud detect-patterns --rule tainted-orm-queries --file tests/fixtures/node-prisma-orm/
```

## Files Structure

```
node-prisma-orm/
├── package.json              # Prisma 5.x dependencies
├── prisma/
│   └── schema.prisma         # 9 models with relationships (188 lines)
├── services/
│   ├── user-service.js       # 6 functions with nested queries (190 lines)
│   └── post-service.js       # 6 functions with transactions (279 lines)
├── spec.yaml                 # 12 verification rules (307 lines)
└── README.md                 # This file

Total: 657 lines of Prisma code
```

## Security Patterns

### 1. Tainted User IDs in ORM Queries (MEDIUM)

**Location**: `services/user-service.js:getUserById`

**Pattern**:
```javascript
async function getUserById(userId) {
  // userId from API route parameter (user-controlled)
  const user = await prisma.user.findUnique({
    where: { id: userId }
  });
}
```

**Impact**: Horizontal privilege escalation if userId not validated

### 2. Multi-Source Taint in Search (MEDIUM)

**Location**: `services/post-service.js:searchPosts`

**Pattern**:
```javascript
async function searchPosts(searchTerm, tagName) {
  // Both inputs from query params flow into Prisma query
  const posts = await prisma.post.findMany({
    where: {
      AND: [
        { OR: [{ title: { contains: searchTerm } }] },
        { tags: { some: { tag: { name: tagName } } } }
      ]
    }
  });
}
```

**Impact**: Logic bugs in complex filters, potential DoS

### 3. Cascade Delete Side Effects (LOW)

**Location**: `services/user-service.js:deleteUser`

**Pattern**:
```javascript
async function deleteUser(userId) {
  // Cascades to: profile, posts, comments, sessions
  const user = await prisma.user.delete({
    where: { id: userId }
  });
}
```

**Impact**: Data loss, unintended side effects, retention policy violations

## Advanced Capabilities Tested

From test_enhancements.md, this fixture tests **4 of 7** advanced capabilities:

1. ❌ **API Security Coverage** - N/A (ORM layer only, no API routes)
2. ❌ **SQL Query Surface Area** - N/A (ORM abstraction, no raw SQL)
3. ✅ **Multi-Source Taint Origin** - searchTerm + tagName → searchPosts
4. ❌ **React Hook Dependencies** - N/A (backend ORM, no React)
5. ✅ **Cross-Function Taint Flow** - API route → service function → Prisma query
6. ✅ **Import Chain Analysis** - import { PrismaClient } from '@prisma/client'
7. ❌ **React Hook Anti-Patterns** - N/A (backend ORM, no React)

**Prisma-specific capabilities**:
- ✅ ORM model extraction (9 models)
- ✅ ORM relationship tracking (15+ relationships)
- ✅ Cascade delete detection
- ✅ Nested query patterns
- ✅ Transaction patterns
- ✅ Many-to-many join tables

## Comparison to Test Requirements

From test_enhancements.md (lines 260-295), this fixture covers:

| Requirement | Status | Evidence |
|---|---|---|
| Prisma schema extraction | ✅ | 9 models with fields |
| One-to-one relationships | ✅ | User <-> Profile (bidirectional) |
| One-to-many relationships | ✅ | User -> Posts, Post -> Comments, etc. |
| Many-to-many relationships | ✅ | Post <-> Tags, Post <-> Categories |
| Cascade delete | ✅ | 8+ relationships with onDelete: Cascade |
| Nested creates | ✅ | createUser with profile, createPost with tags |
| Nested includes | ✅ | Deep 3-level includes |
| Transactions | ✅ | updatePostTags with $transaction |
| Taint flows | ✅ | 6+ distinct taint paths |

## Taint Flow Paths

### Path 1: User ID → Prisma Query

```
userId (SOURCE - API route param)
  → getUserById(userId) (PROPAGATION)
  → prisma.user.findUnique({ where: { id: userId } }) (SINK)
```

### Path 2: Multi-Source Search → Prisma Query

```
searchTerm (SOURCE 1 - query param)
tagName (SOURCE 2 - query param)
  → searchPosts(searchTerm, tagName) (PROPAGATION)
  → prisma.post.findMany({ where: { AND: [...] } }) (SINK)
```

### Path 3: Nested Create → Prisma Transaction

```
authorId (SOURCE 1 - from token)
postData (SOURCE 2 - request body with tagIds, categoryIds)
  → createPost(authorId, postData) (PROPAGATION)
  → prisma.post.create({ data: { ..., tags: { create: [...] } } }) (SINK)
```

### Path 4: Pagination → Prisma Query

```
authorId (SOURCE 1)
page (SOURCE 2 - query param)
limit (SOURCE 3 - query param)
  → getPostsByAuthor(authorId, page, limit) (PROPAGATION)
  → prisma.post.findMany({ skip: (page - 1) * limit, take: limit }) (SINK)
```

## Related Documentation

- [test_enhancements.md](../../../test_enhancements.md) - Prisma patterns (lines 260-295)
- [FIXTURE_ASSESSMENT.md](../../../FIXTURE_ASSESSMENT.md) - Node ecosystem status
- [node-express-api](../node-express-api/) - Express REST API fixture
- [node-nextjs-app](../node-nextjs-app/) - Next.js full-stack fixture

---

**Created**: 2025-10-31
**Total Code**: 657 lines (exceeds 300+ target)
**Language**: JavaScript/Prisma
**Framework**: Prisma ORM 5.x
**Patterns Tested**: ORM relationships, nested queries, transactions, cascade deletes
