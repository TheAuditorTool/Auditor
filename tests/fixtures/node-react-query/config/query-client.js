import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,

      cacheTime: 10 * 60 * 1000,

      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      refetchOnWindowFocus: true,

      refetchOnReconnect: true,

      refetchOnMount: false,

      suspense: false,
    },
    mutations: {
      retry: 1,

      retryDelay: 1000,
    },
  },
});

export const API_BASE_URL =
  process.env.REACT_APP_API_URL || "https://api.example.com";

export const queryKeys = {
  users: {
    all: ["users"],
    lists: () => [...queryKeys.users.all, "list"],
    list: (filters) => [...queryKeys.users.lists(), { filters }],
    details: () => [...queryKeys.users.all, "detail"],
    detail: (id) => [...queryKeys.users.details(), id],
  },

  posts: {
    all: ["posts"],
    lists: () => [...queryKeys.posts.all, "list"],
    list: (filters) => [...queryKeys.posts.lists(), { filters }],
    details: () => [...queryKeys.posts.all, "detail"],
    detail: (id) => [...queryKeys.posts.details(), id],
    infinite: (filters) => [...queryKeys.posts.all, "infinite", { filters }],
  },

  comments: {
    all: ["comments"],
    byPost: (postId) => [...queryKeys.comments.all, "post", postId],
  },

  products: {
    all: ["products"],
    lists: () => [...queryKeys.products.all, "list"],
    list: (filters) => [...queryKeys.products.lists(), { filters }],
    details: () => [...queryKeys.products.all, "detail"],
    detail: (id) => [...queryKeys.products.details(), id],
    search: (query) => [...queryKeys.products.all, "search", query],
  },

  orders: {
    all: ["orders"],
    lists: () => [...queryKeys.orders.all, "list"],
    list: (filters) => [...queryKeys.orders.lists(), { filters }],
    details: () => [...queryKeys.orders.all, "detail"],
    detail: (id) => [...queryKeys.orders.details(), id],
  },
};

export default queryClient;
