# Migration Database Fixture (User → Account Rename)

## Purpose
Simulates a database schema migration project:
- **Before**: User, Profile, Post models with `users` table
- **After**: Account, Profile, Post models with `accounts` table (User renamed to Account)

Tests TheAuditor's ability to track:
- ORM model renames and their cascading impacts
- Foreign key relationship updates
- Table name changes in SQLAlchemy models
- Bidirectional relationship consistency after refactoring

This fixture demonstrates **how TheAuditor handles database schema migrations** where model names, table names, and FK constraints change while preserving relationship semantics.

## Project Structure

```
migration-database/
├── spec.yaml           # Verification rules for ORM relationships
├── before/             # Original schema (User model)
│   └── models.py       # User, Profile, Post with users table
└── after/              # Migrated schema (Account model)
    └── models.py       # Account, Profile, Post with accounts table
```

## ORM Patterns Included

### 1. Model Renaming (User → Account)

| Aspect | Before | After |
|---|---|---|
| **Class name** | `User` | `Account` |
| **Table name** | `users` | `accounts` |
| **FK column** | `user_id` | `account_id` |
| **Relationship attribute** | `profile.user` | `profile.account` |
| **Back-populates** | `back_populates='user'` | `back_populates='account'` |

### 2. SQLAlchemy Relationships Tracked

Both before/ and after/ include:

**User/Account Model** (Parent):
- **1-to-1**: `profile` relationship → Profile (uselist=False, cascade delete-orphan)
- **1-to-many**: `posts` relationship → Post (cascade delete-orphan)

**Profile Model** (Child):
- **Many-to-1**: `user`/`account` relationship → User/Account
- **Foreign Key**: `user_id`/`account_id` with CASCADE DELETE

**Post Model** (Child):
- **Many-to-1**: `author` relationship → User/Account
- **Foreign Key**: `author_id` with CASCADE DELETE

### 3. Cascade Delete Flags

Both versions include:
```python
# On parent (User/Account)
relationship('Profile', cascade='all, delete-orphan')
relationship('Post', cascade='all, delete-orphan')

# On FK (Profile/Post)
ForeignKey('users.id'/'accounts.id', ondelete='CASCADE')
```

**Security Impact**: Deleting a User/Account cascades to all Profile and Post records.

### 4. Relationship Cardinality Patterns

| Pattern | Models | Cardinality | TheAuditor Field |
|---|---|---|---|
| **1-to-1** | User/Account ↔ Profile | uselist=False | `relationship_type='one-to-one'` |
| **1-to-many** | User/Account → Post | uselist=True (default) | `relationship_type='one-to-many'` |
| **Many-to-1** | Profile → User/Account | back_populates parent | `relationship_type='many-to-one'` |
| **Many-to-1** | Post → User/Account | back_populates parent | `relationship_type='many-to-one'` |

## Populated Database Tables

After running `aud index` from TheAuditor root:

| Table | Before Count | After Count | What It Tests |
|---|---|---|---|
| **python_orm_models** | 3 | 3 | Model extraction (User→Account, Profile, Post) |
| **python_orm_fields** | 13 | 13 | Field extraction (id, username, email, etc.) |
| **orm_relationships** | 6 | 6 | Bidirectional relationships (3 models × 2 directions) |
| **symbols** | 9 | 9 | Class/method symbols |

**Key Point**: Table counts are identical - only names changed, not structure.

## Sample Verification Queries

### Query 1: Find All ORM Models and Their Tables

```sql
SELECT
    model_name,
    table_name,
    file
FROM python_orm_models
WHERE file LIKE '%migration-database%'
ORDER BY file, model_name;
```

**Expected Results**:
- Before: User → users, Profile → profiles, Post → posts
- After: Account → accounts, Profile → profiles, Post → posts

### Query 2: Track Foreign Key Changes (User → Account)

```sql
SELECT
    pof.model_name,
    pof.field_name,
    pof.is_foreign_key,
    pof.foreign_key_table,
    pof.file
FROM python_orm_fields pof
WHERE pof.is_foreign_key = 1
  AND pof.file LIKE '%migration-database%'
ORDER BY pof.file, pof.model_name;
```

**Expected Results**:
- Before: Profile.user_id → users, Post.author_id → users
- After: Profile.account_id → accounts, Post.author_id → accounts

### Query 3: Verify Bidirectional Relationships

```sql
SELECT
    source_model,
    source_field,
    target_model,
    relationship_type,
    cascade_delete,
    file
FROM orm_relationships
WHERE file LIKE '%migration-database%'
ORDER BY file, source_model, source_field;
```

**Expected Results** (before/):
1. User.profile → Profile (one-to-one, cascade=1)
2. Profile.user → User (many-to-one, cascade=0)
3. User.posts → Post (one-to-many, cascade=1)
4. Post.author → User (many-to-one, cascade=0)

**Expected Results** (after/):
1. Account.profile → Profile (one-to-one, cascade=1)
2. Profile.account → Account (many-to-one, cascade=0)
3. Account.posts → Post (one-to-many, cascade=1)
4. Post.author → Account (many-to-one, cascade=0)

### Query 4: Find Models with Cascade Delete (Security Risk)

```sql
SELECT DISTINCT
    source_model,
    target_model,
    cascade_delete
FROM orm_relationships
WHERE cascade_delete = 1
  AND file LIKE '%migration-database%'
ORDER BY source_model;
```

**Expected Results**: User/Account → Profile (cascade), User/Account → Post (cascade)

**Security Implication**: Deleting a user account destroys all associated data without explicit confirmation.

### Query 5: Compare Relationship Counts (Before vs After)

```sql
SELECT
    CASE
        WHEN file LIKE '%before%' THEN 'Before (User)'
        WHEN file LIKE '%after%' THEN 'After (Account)'
    END AS version,
    COUNT(*) as relationship_count
FROM orm_relationships
WHERE file LIKE '%migration-database%'
GROUP BY version;
```

**Expected Results**: Both should have 6 relationships (3 bidirectional pairs)

## Testing Use Cases

This fixture enables testing:

1. **Model Rename Detection**: Verify User → Account rename doesn't break relationship tracking
2. **FK Constraint Updates**: Ensure foreign_key_table updates from `users` to `accounts`
3. **Bidirectional Consistency**: Confirm back_populates updates match FK changes
4. **Cascade Delete Tracking**: Identify security risks from cascade='all, delete-orphan'
5. **Migration Diff Analysis**: Compare before/ and after/ to verify schema consistency

## How to Use This Fixture

1. **Index the project**:
   ```bash
   cd C:/Users/santa/Desktop/TheAuditor
   aud index
   ```

2. **Run spec.yaml verification**:
   ```bash
   # Query should find relationships in both before/ and after/
   # with identical structure but different names
   ```

3. **Query relationship changes**:
   ```bash
   aud context query --symbol User --show-relationships
   aud context query --symbol Account --show-relationships
   ```

4. **Compare ORM schemas**:
   ```sql
   -- Find all relationship pairs
   SELECT
       before.source_model AS before_source,
       after.source_model AS after_source,
       before.target_model AS before_target,
       after.target_model AS after_target
   FROM orm_relationships before
   JOIN orm_relationships after
       ON before.source_field = after.source_field
   WHERE before.file LIKE '%before%'
     AND after.file LIKE '%after%';
   ```

## Expected Schema Population

When this fixture is indexed, expect:

- ✅ **3 ORM models** in before/ (User, Profile, Post)
- ✅ **3 ORM models** in after/ (Account, Profile, Post)
- ✅ **6 bidirectional relationships** in before/ (User↔Profile, User↔Post, Profile→User, Post→User)
- ✅ **6 bidirectional relationships** in after/ (Account↔Profile, Account↔Post, Profile→Account, Post→Account)
- ✅ **Cascade delete flags** on parent→child relationships (User/Account → Profile, User/Account → Post)
- ✅ **Foreign key table names** updated from `users` to `accounts`

## Diff Summary

| Aspect | Lines Changed | Impact |
|---|---|---|
| **Class name** | 1 | `class User` → `class Account` |
| **Table name** | 1 | `__tablename__ = 'users'` → `'accounts'` |
| **FK columns** | 2 | `user_id` → `account_id` (Profile, Post) |
| **FK table references** | 2 | `ForeignKey('users.id')` → `ForeignKey('accounts.id')` |
| **Relationship names** | 2 | `profile.user` → `profile.account`, `back_populates='user'` → `'account'` |
| **Total affected** | ~10 lines | Same relationships, different naming |

## Security Implications

Both versions have identical security posture:

- **Cascade Delete Risk**: Deleting a User/Account destroys all Profile and Post data
- **No Soft Delete**: Hard DELETE with no audit trail
- **No Ownership Validation**: Relationship deletion relies solely on FK constraints

TheAuditor should flag these patterns consistently in both before/ and after/ states.

## Why This Fixture Matters

Real-world database migrations often involve:
- Model renames that ripple through 10+ files
- FK constraint updates across dozens of relationships
- Risk of breaking bidirectional back_populates references

This fixture validates that **TheAuditor can track schema changes** even when model names, table names, and relationship attributes are refactored. If the indexer works correctly, queries on before/ and after/ should return structurally identical results with only name differences.
