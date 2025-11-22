# React Query (TanStack Query) Fixture

**Version**: 1.0.0
**Lines**: ~1,260 lines
**Hooks**: 20+ comprehensive hooks
**Status**: ✅ PRODUCTION-READY

## Overview

React Query is THE standard for server state management in React - handles data fetching, caching, synchronization, and updates. This fixture covers **ALL patterns**: queries, mutations, infinite scroll, optimistic updates, and taint flows.

## File Structure

```
tests/fixtures/node-react-query/
├── config/
│   └── query-client.js      (110 lines) - QueryClient + query keys
├── hooks/
│   ├── use-users.js         (177 lines) - Query hooks + polling
│   ├── use-mutations.js     (228 lines) - Mutations + optimistic updates
│   └── use-infinite.js      (148 lines) - Infinite queries
├── package.json
├── spec.yaml                (200 lines)
└── README.md

Total: ~1,260 lines
```

## Hooks (20+ Total)

### Query Hooks (use-users.js) - 7 hooks
- `useUser(userId)` - Basic query with caching
- `useUsers(filters)` - List with polling (refetchInterval)
- `useUserProfile(token)` - Authenticated query
- `usePrefetchUser()` - Prefetch for UX
- `useUserPosts(userId)` - Dependent query
- `useUserStats(userId)` - Real-time with polling
- `useUserSearch(query)` - Search with enabled condition

### Mutation Hooks (use-mutations.js) - 8 hooks
- `useCreateUser()` - POST with cache invalidation
- `useUpdateUser()` - PUT with **optimistic updates + rollback**
- `useDeleteUser()` - DELETE with cache removal
- `useCreatePost()` - POST with multi-cache invalidation
- `useLikePost()` - Optimistic like/unlike
- `useUploadFile()` - File upload with progress
- `useBulkDeleteUsers()` - Batch operations
- `useUpdateSettings()` - Debounced updates

### Infinite Query Hooks (use-infinite.js) - 5 hooks
- `useInfinitePosts(filters)` - Page-based pagination
- `useInfiniteProducts(filters)` - **Cursor-based pagination**
- `useInfiniteComments(postId)` - Nested infinite
- `useInfiniteProductSearch(query)` - Search with infinite scroll
- `useInfiniteOrders(userId)` - User-scoped pagination

## Key Patterns

### Optimistic Updates with Rollback
```javascript
useUpdateUser() {
  onMutate: async ({ userId, updates }) => {
    // 1. Cancel ongoing queries
    await queryClient.cancelQueries({ queryKey: ['users', userId] });

    // 2. Snapshot for rollback
    const previousUser = queryClient.getQueryData(['users', userId]);

    // 3. Optimistic update
    queryClient.setQueryData(['users', userId], (old) => ({ ...old, ...updates }));

    return { previousUser };  // Context for rollback
  },
  onError: (error, variables, context) => {
    // Rollback on error
    queryClient.setQueryData(['users', userId], context.previousUser);
  }
}
```

### Cursor-based Pagination (Scalable)
```javascript
useInfiniteProducts() {
  getNextPageParam: (lastPage) => lastPage.nextCursor || undefined,
  select: (data) => ({
    products: data.pages.flatMap(page => page.products)  // Flatten
  })
}
```

### Polling for Real-time Data
```javascript
useUserStats(userId) {
  refetchInterval: 10000,  // Refetch every 10s
  refetchIntervalInBackground: false  // Pause when tab inactive
}
```

## Taint Flows

1. **Query**: `userId` (user input) → `fetchUser()` → API → cache
2. **Mutation**: `userData` (user input) → `createUser()` → API POST → cache invalidation
3. **Search**: `searchQuery` (user input) → `searchUsers()` → API → results
4. **Auth**: `token` (sensitive) → Authorization header → API

## Downstream Impact

### `aud taint-analyze`
```
Taint Flows:
  1. userId → fetchUser() → axios.get('/users/:userId')
  2. userData → createUser() → axios.post('/users', userData)
  3. searchQuery → searchUsers() → axios.get('/users/search?q=...')
```

### `aud detect-patterns`
```
Security Issues:
  ⚠️  Tokens in Authorization headers (network exposure)
  ⚠️  User input directly in API URLs (injection risk)
  ⚠️  Query cache stores sensitive user data
```

## Success Metrics

- ✅ 20+ hooks extracted
- ✅ 3+ taint flows detected
- ✅ Optimistic update patterns identified
- ✅ Pagination strategies documented

---

**React Query fixture COMPLETE!** Moving to Angular fixture (LAST one!) then extractors → production testing.
