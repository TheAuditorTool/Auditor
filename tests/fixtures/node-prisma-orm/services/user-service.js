const { PrismaClient } = require("@prisma/client");
const prisma = new PrismaClient();

async function getUserById(userId) {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    include: {
      profile: true,
      posts: {
        where: { published: true },
        orderBy: { createdAt: "desc" },
        take: 10,
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
      },
      _count: {
        select: {
          posts: true,
          comments: true,
        },
      },
    },
  });

  return user;
}

async function searchUsers(searchTerm) {
  const users = await prisma.user.findMany({
    where: {
      OR: [
        { username: { contains: searchTerm, mode: "insensitive" } },
        { email: { contains: searchTerm, mode: "insensitive" } },
      ],
    },
    include: {
      profile: true,
      _count: {
        select: { posts: true, comments: true },
      },
    },
    take: 20,
  });

  return users;
}

async function createUser(userData) {
  const { email, username, password, bio, website } = userData;

  const user = await prisma.user.create({
    data: {
      email,
      username,
      password,
      profile: {
        create: {
          bio: bio || null,
          website: website || null,
        },
      },
    },
    include: {
      profile: true,
    },
  });

  return user;
}

async function updateUser(userId, updates) {
  const { username, email, bio, website } = updates;

  const user = await prisma.user.update({
    where: { id: userId },
    data: {
      username,
      email,
      profile: {
        update: {
          bio,
          website,
        },
      },
    },
    include: {
      profile: true,
    },
  });

  return user;
}

async function deleteUser(userId) {
  const user = await prisma.user.delete({
    where: { id: userId },
  });

  return user;
}

async function getUsersWithMinPosts(minPosts) {
  const users = await prisma.user.findMany({
    where: {
      posts: {
        some: {},
      },
    },
    include: {
      profile: true,
      _count: {
        select: { posts: true },
      },
    },
  });

  const filtered = users.filter((user) => user._count.posts >= minPosts);

  return filtered;
}

module.exports = {
  getUserById,
  searchUsers,
  createUser,
  updateUser,
  deleteUser,
  getUsersWithMinPosts,
};
