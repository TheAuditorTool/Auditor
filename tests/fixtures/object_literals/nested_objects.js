const routes = {
  api: {
    users: {
      create: createUser,
      update: updateUser,
    },
    posts: {
      create: createPost,
    },
  },
  public: {
    home: homeHandler,
  },
};

const complex = {
  level1: value1,
  nested: {
    level2: value2,
    deeper: {
      level3: value3,
    },
  },
};
