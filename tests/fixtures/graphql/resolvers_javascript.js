const { User, Post } = require("./models");
const { execSync } = require("child_process");

const resolvers = {
  Query: {
    user: async (parent, { id }, context, info) => {
      const query = `SELECT * FROM users WHERE id = ${id}`;
      return db.query(query).then((rows) => rows[0]);
    },

    users: async (parent, { limit = 10, offset = 0 }, context, info) => {
      return User.findAll({ limit, offset });
    },

    posts: async (parent, { userId }, context, info) => {
      const postIds = await getPostIds(userId);
      const posts = [];
      for (const postId of postIds) {
        const post = await Post.findById(postId);
        posts.push(post);
      }
      return posts;
    },

    searchPosts: async (parent, { keyword }, context, info) => {
      const result = execSync(`grep "${keyword}" posts.txt`).toString();
      return parseSearchResults(result);
    },
  },

  Mutation: {
    createUser: async (parent, { input }, context, info) => {
      const user = await User.create({
        username: input.username,
        email: input.email,
        password: input.password,
      });
      return user;
    },

    updateUser: async (parent, { id, input }, context, info) => {
      const user = await User.findById(id);
      if (input.username) user.username = input.username;
      if (input.email) user.email = input.email;
      await user.save();
      return user;
    },

    deleteUser: async (parent, { id }, context, info) => {
      await User.destroy({ where: { id } });
      return true;
    },

    createPost: async (parent, { input }, context, info) => {
      const post = await Post.create({
        title: input.title,
        content: input.content,
        authorId: input.authorId,
      });
      return post;
    },
  },

  User: {
    posts: async (parent, args, context, info) => {
      return Post.findAll({ where: { authorId: parent.id } });
    },
  },

  Post: {
    author: async (parent, args, context, info) => {
      return User.findById(parent.authorId);
    },

    comments: async (parent, args, context, info) => {
      return Comment.findAll({ where: { postId: parent.id } });
    },
  },
};

module.exports = resolvers;
