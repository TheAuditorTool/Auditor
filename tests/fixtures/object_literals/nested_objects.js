// Test 6: Nested objects
const routes = {
    api: {
        users: {
            create: createUser,
            update: updateUser
        },
        posts: {
            create: createPost
        }
    },
    public: {
        home: homeHandler
    }
};

// Test 7: Mixed nesting levels
const complex = {
    level1: value1,
    nested: {
        level2: value2,
        deeper: {
            level3: value3
        }
    }
};
