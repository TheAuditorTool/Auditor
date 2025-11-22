/**
 * React Query Client Configuration
 * Tests: QueryClient setup, default options, cache configuration
 */

import { QueryClient } from '@tanstack/react-query';

/**
 * Create Query Client with default configuration
 * Tests: QueryClient instantiation with options
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: Data considered fresh for 5 minutes
      staleTime: 5 * 60 * 1000,

      // Cache time: Inactive queries stay in cache for 10 minutes
      cacheTime: 10 * 60 * 1000,

      // Retry failed queries 3 times with exponential backoff
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Refetch on window focus
      refetchOnWindowFocus: true,

      // Refetch on reconnect
      refetchOnReconnect: true,

      // Don't refetch on mount if data is fresh
      refetchOnMount: false,

      // Suspense mode disabled by default
      suspense: false
    },
    mutations: {
      // Retry mutations once
      retry: 1,

      // Mutation retry delay
      retryDelay: 1000
    }
  }
});

/**
 * API base URL
 * Tests: Environment-based configuration
 */
export const API_BASE_URL =
  process.env.REACT_APP_API_URL || 'https://api.example.com';

/**
 * Query keys factory
 * Tests: Centralized query key management
 */
export const queryKeys = {
  // Users
  users: {
    all: ['users'],
    lists: () => [...queryKeys.users.all, 'list'],
    list: (filters) => [...queryKeys.users.lists(), { filters }],
    details: () => [...queryKeys.users.all, 'detail'],
    detail: (id) => [...queryKeys.users.details(), id]
  },

  // Posts
  posts: {
    all: ['posts'],
    lists: () => [...queryKeys.posts.all, 'list'],
    list: (filters) => [...queryKeys.posts.lists(), { filters }],
    details: () => [...queryKeys.posts.all, 'detail'],
    detail: (id) => [...queryKeys.posts.details(), id],
    infinite: (filters) => [...queryKeys.posts.all, 'infinite', { filters }]
  },

  // Comments
  comments: {
    all: ['comments'],
    byPost: (postId) => [...queryKeys.comments.all, 'post', postId]
  },

  // Products
  products: {
    all: ['products'],
    lists: () => [...queryKeys.products.all, 'list'],
    list: (filters) => [...queryKeys.products.lists(), { filters }],
    details: () => [...queryKeys.products.all, 'detail'],
    detail: (id) => [...queryKeys.products.details(), id],
    search: (query) => [...queryKeys.products.all, 'search', query]
  },

  // Orders
  orders: {
    all: ['orders'],
    lists: () => [...queryKeys.orders.all, 'list'],
    list: (filters) => [...queryKeys.orders.lists(), { filters }],
    details: () => [...queryKeys.orders.all, 'detail'],
    detail: (id) => [...queryKeys.orders.details(), id]
  }
};

export default queryClient;
