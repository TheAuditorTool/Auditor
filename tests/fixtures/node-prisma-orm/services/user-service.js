/**
 * User service with Prisma ORM
 *
 * Tests:
 * - Prisma client usage
 * - ORM query extraction (findUnique, findMany, create, update, delete)
 * - Taint flows through ORM queries
 * - Complex include/select patterns
 */

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

/**
 * Get user by ID with profile and posts
 * Tests:
 * - ORM query with multiple includes
 * - Taint flow: userId (param) -> prisma.user.findUnique
 *
 * @param {number} userId - User ID (TAINT SOURCE)
 */
async function getUserById(userId) {
  // TAINT FLOW: userId -> Prisma query
  const user = await prisma.user.findUnique({
    where: { id: userId },
    include: {
      profile: true,
      posts: {
        where: { published: true },
        orderBy: { createdAt: 'desc' },
        take: 10,
        include: {
          tags: {
            include: {
              tag: true
            }
          },
          categories: {
            include: {
              category: true
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

/**
 * Search users by username or email
 * Tests:
 * - Multi-source taint (username OR email)
 * - Prisma OR queries
 *
 * @param {string} searchTerm - Search term (TAINT SOURCE)
 */
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
    },
    take: 20
  });

  return users;
}

/**
 * Create user with profile
 * Tests:
 * - Prisma nested create
 * - Taint from request data -> ORM create
 *
 * @param {Object} userData - User data (TAINT SOURCE from request body)
 */
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

/**
 * Update user and profile
 * Tests:
 * - Prisma nested update
 * - Multi-source taint (userId + userData)
 *
 * @param {number} userId - User ID (TAINT SOURCE 1)
 * @param {Object} updates - Update data (TAINT SOURCE 2)
 */
async function updateUser(userId, updates) {
  const { username, email, bio, website } = updates;

  // MULTI-SOURCE TAINT: userId + updates -> Prisma nested update
  const user = await prisma.user.update({
    where: { id: userId },
    data: {
      username,
      email,
      profile: {
        update: {
          bio,
          website
        }
      }
    },
    include: {
      profile: true
    }
  });

  return user;
}

/**
 * Delete user with cascade
 * Tests:
 * - Prisma delete with cascade (deletes profile, posts, comments)
 * - Taint flow: userId -> delete
 *
 * @param {number} userId - User ID (TAINT SOURCE)
 */
async function deleteUser(userId) {
  // TAINT FLOW: userId -> Prisma delete (cascades to profile, posts, comments)
  const user = await prisma.user.delete({
    where: { id: userId }
  });

  return user;
}

/**
 * Get users with post count filter
 * Tests:
 * - Prisma aggregation with having
 * - Complex filter logic
 *
 * @param {number} minPosts - Minimum post count (TAINT SOURCE)
 */
async function getUsersWithMinPosts(minPosts) {
  // TAINT FLOW: minPosts -> Prisma query
  const users = await prisma.user.findMany({
    where: {
      posts: {
        some: {}
      }
    },
    include: {
      profile: true,
      _count: {
        select: { posts: true }
      }
    }
  });

  // Filter by post count (Prisma doesn't support HAVING directly)
  const filtered = users.filter(user => user._count.posts >= minPosts);

  return filtered;
}

module.exports = {
  getUserById,
  searchUsers,
  createUser,
  updateUser,
  deleteUser,
  getUsersWithMinPosts
};
