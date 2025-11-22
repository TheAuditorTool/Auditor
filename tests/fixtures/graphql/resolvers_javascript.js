/**
 * Sample JavaScript GraphQL resolvers for testing (Apollo Server style).
 */

const { User, Post } = require('./models');
const { execSync } = require('child_process');

const resolvers = {
  Query: {
    /**
     * Get user by ID - NO AUTH CHECK (should be flagged)
     */
    user: async (parent, { id }, context, info) => {
      // VULNERABILITY: SQL injection via template literal (should be flagged)
      const query = `SELECT * FROM users WHERE id = ${id}`;
      return db.query(query).then(rows => rows[0]);
    },

    /**
     * List all users - NO AUTH CHECK (should be flagged)
     */
    users: async (parent, { limit = 10, offset = 0 }, context, info) => {
      return User.findAll({ limit, offset });
    },

    /**
     * Get posts by user ID
     */
    posts: async (parent, { userId }, context, info) => {
      // VULNERABILITY: N+1 query pattern (should be flagged)
      const postIds = await getPostIds(userId);
      const posts = [];
      for (const postId of postIds) {
        const post = await Post.findById(postId);
        posts.push(post);
      }
      return posts;
    },

    /**
     * Search posts - NO INPUT VALIDATION (should be flagged)
     */
    searchPosts: async (parent, { keyword }, context, info) => {
      // VULNERABILITY: Command injection (should be flagged)
      const result = execSync(`grep "${keyword}" posts.txt`).toString();
      return parseSearchResults(result);
    },
  },

  Mutation: {
    /**
     * Create new user - NO AUTH CHECK (should be flagged)
     */
    createUser: async (parent, { input }, context, info) => {
      // VULNERABILITY: Password stored in plaintext (should be flagged)
      const user = await User.create({
        username: input.username,
        email: input.email,
        password: input.password, // Should be hashed!
      });
      return user;
    },

    /**
     * Update user - NO AUTH CHECK (should be flagged)
     */
    updateUser: async (parent, { id, input }, context, info) => {
      const user = await User.findById(id);
      if (input.username) user.username = input.username;
      if (input.email) user.email = input.email;
      await user.save();
      return user;
    },

    /**
     * Delete user - NO AUTH CHECK (should be flagged)
     */
    deleteUser: async (parent, { id }, context, info) => {
      await User.destroy({ where: { id } });
      return true;
    },

    /**
     * Create post - NO AUTH CHECK (should be flagged)
     */
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
    /**
     * Resolve posts for a user - N+1 query risk
     */
    posts: async (parent, args, context, info) => {
      // VULNERABILITY: N+1 query (should be flagged)
      return Post.findAll({ where: { authorId: parent.id } });
    },
  },

  Post: {
    /**
     * Resolve author for a post
     */
    author: async (parent, args, context, info) => {
      return User.findById(parent.authorId);
    },

    /**
     * Resolve comments for a post - N+1 query risk
     */
    comments: async (parent, args, context, info) => {
      return Comment.findAll({ where: { postId: parent.id } });
    },
  },
};

module.exports = resolvers;
