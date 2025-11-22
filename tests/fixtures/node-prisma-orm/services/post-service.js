/**
 * Post service with Prisma ORM
 *
 * Tests:
 * - Complex Prisma queries with many-to-many relationships
 * - Nested creates/updates with join tables
 * - Taint flows through relationship queries
 * - Transaction patterns
 */

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

/**
 * Get post by ID with all relationships
 * Tests:
 * - Deep nested includes (post -> author -> profile, post -> tags, post -> categories)
 * - Taint flow: postId -> Prisma query
 *
 * @param {number} postId - Post ID (TAINT SOURCE)
 */
async function getPostById(postId) {
  // TAINT FLOW: postId -> Prisma query
  const post = await prisma.post.findUnique({
    where: { id: postId },
    include: {
      author: {
        include: {
          profile: true
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
        },
        orderBy: { createdAt: 'desc' }
      },
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
  });

  return post;
}

/**
 * Create post with tags and categories
 * Tests:
 * - Prisma nested create with many-to-many relationships
 * - Multi-source taint (authorId + postData)
 *
 * @param {number} authorId - Author ID (TAINT SOURCE 1)
 * @param {Object} postData - Post data (TAINT SOURCE 2)
 */
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
            connect: { id: tagId }
          }
        }))
      },
      categories: {
        create: categoryIds.map(categoryId => ({
          category: {
            connect: { id: categoryId }
          }
        }))
      }
    },
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
  });

  return post;
}

/**
 * Update post tags
 * Tests:
 * - Prisma deleteMany + createMany pattern
 * - Multi-source taint (postId + tagIds)
 *
 * @param {number} postId - Post ID (TAINT SOURCE 1)
 * @param {Array<number>} tagIds - Tag IDs (TAINT SOURCE 2)
 */
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

/**
 * Search posts by content and tags
 * Tests:
 * - Multi-source taint (searchTerm + tagName)
 * - Complex Prisma filters with nested conditions
 *
 * @param {string} searchTerm - Search term (TAINT SOURCE 1)
 * @param {string} tagName - Tag name (TAINT SOURCE 2)
 */
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
    include: {
      author: {
        select: {
          id: true,
          username: true
        }
      },
      tags: {
        include: {
          tag: true
        }
      },
      _count: {
        select: { comments: true }
      }
    },
    orderBy: { createdAt: 'desc' },
    take: 50
  });

  return posts;
}

/**
 * Publish post and increment view count
 * Tests:
 * - Prisma update with increment
 * - Taint flow: postId -> update
 *
 * @param {number} postId - Post ID (TAINT SOURCE)
 */
async function publishPost(postId) {
  // TAINT FLOW: postId -> Prisma update
  const post = await prisma.post.update({
    where: { id: postId },
    data: {
      published: true,
      viewCount: {
        increment: 1
      }
    }
  });

  return post;
}

/**
 * Get posts by author with pagination
 * Tests:
 * - Prisma pagination (skip/take)
 * - Multi-source taint (authorId + page + limit)
 *
 * @param {number} authorId - Author ID (TAINT SOURCE 1)
 * @param {number} page - Page number (TAINT SOURCE 2)
 * @param {number} limit - Results per page (TAINT SOURCE 3)
 */
async function getPostsByAuthor(authorId, page = 1, limit = 10) {
  const skip = (page - 1) * limit;

  // MULTI-SOURCE TAINT: authorId + page + limit -> Prisma query
  const posts = await prisma.post.findMany({
    where: { authorId },
    skip,
    take: limit,
    orderBy: { createdAt: 'desc' },
    include: {
      tags: {
        include: {
          tag: true
        }
      },
      _count: {
        select: { comments: true }
      }
    }
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

module.exports = {
  getPostById,
  createPost,
  updatePostTags,
  searchPosts,
  publishPost,
  getPostsByAuthor
};
