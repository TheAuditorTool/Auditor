const { PrismaClient } = require("@prisma/client");
const prisma = new PrismaClient();

async function getPostById(postId) {
  const post = await prisma.post.findUnique({
    where: { id: postId },
    include: {
      author: {
        include: {
          profile: true,
        },
      },
      comments: {
        include: {
          author: {
            select: {
              id: true,
              username: true,
            },
          },
        },
        orderBy: { createdAt: "desc" },
      },
      tags: {
        include: {
          tag: true,
        },
      },
      categories: {
        include: {
          category: true,
        },
      },
    },
  });

  return post;
}

async function createPost(authorId, postData) {
  const { title, content, tagIds, categoryIds } = postData;

  const post = await prisma.post.create({
    data: {
      title,
      content,
      authorId,
      tags: {
        create: tagIds.map((tagId) => ({
          tag: {
            connect: { id: tagId },
          },
        })),
      },
      categories: {
        create: categoryIds.map((categoryId) => ({
          category: {
            connect: { id: categoryId },
          },
        })),
      },
    },
    include: {
      tags: {
        include: {
          tag: true,
        },
      },
      categories: {
        include: {
          category: true,
        },
      },
    },
  });

  return post;
}

async function updatePostTags(postId, tagIds) {
  const post = await prisma.$transaction(async (tx) => {
    await tx.postTag.deleteMany({
      where: { postId },
    });

    await tx.postTag.createMany({
      data: tagIds.map((tagId) => ({
        postId,
        tagId,
      })),
    });

    return tx.post.findUnique({
      where: { id: postId },
      include: {
        tags: {
          include: {
            tag: true,
          },
        },
      },
    });
  });

  return post;
}

async function searchPosts(searchTerm, tagName = null) {
  const filters = [];

  if (searchTerm) {
    filters.push({
      OR: [
        { title: { contains: searchTerm, mode: "insensitive" } },
        { content: { contains: searchTerm, mode: "insensitive" } },
      ],
    });
  }

  if (tagName) {
    filters.push({
      tags: {
        some: {
          tag: {
            name: { equals: tagName, mode: "insensitive" },
          },
        },
      },
    });
  }

  const posts = await prisma.post.findMany({
    where: {
      AND: [{ published: true }, ...filters],
    },
    include: {
      author: {
        select: {
          id: true,
          username: true,
        },
      },
      tags: {
        include: {
          tag: true,
        },
      },
      _count: {
        select: { comments: true },
      },
    },
    orderBy: { createdAt: "desc" },
    take: 50,
  });

  return posts;
}

async function publishPost(postId) {
  const post = await prisma.post.update({
    where: { id: postId },
    data: {
      published: true,
      viewCount: {
        increment: 1,
      },
    },
  });

  return post;
}

async function getPostsByAuthor(authorId, page = 1, limit = 10) {
  const skip = (page - 1) * limit;

  const posts = await prisma.post.findMany({
    where: { authorId },
    skip,
    take: limit,
    orderBy: { createdAt: "desc" },
    include: {
      tags: {
        include: {
          tag: true,
        },
      },
      _count: {
        select: { comments: true },
      },
    },
  });

  const total = await prisma.post.count({
    where: { authorId },
  });

  return {
    posts,
    total,
    page,
    totalPages: Math.ceil(total / limit),
  };
}

module.exports = {
  getPostById,
  createPost,
  updatePostTags,
  searchPosts,
  publishPost,
  getPostsByAuthor,
};
