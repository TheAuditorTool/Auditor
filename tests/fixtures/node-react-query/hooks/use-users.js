/**
 * User Query Hooks - Comprehensive useQuery patterns
 * Tests: useQuery, dependent queries, refetch intervals, error handling
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { API_BASE_URL, queryKeys } from '../config/query-client';

/**
 * Fetch user by ID
 * Tests: Basic API request with axios
 * TAINT FLOW: userId (user input) -> API request
 */
async function fetchUser(userId) {
  const { data } = await axios.get(`${API_BASE_URL}/users/${userId}`);
  return data;
}

/**
 * useUser Hook - Fetch single user
 * Tests: Basic useQuery pattern with error handling
 */
export function useUser(userId, options = {}) {
  return useQuery({
    queryKey: queryKeys.users.detail(userId),
    queryFn: () => fetchUser(userId),
    enabled: !!userId, // Only fetch if userId provided
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options
  });
}

/**
 * Fetch users list with filters
 * Tests: Query with parameters
 * TAINT FLOW: filters (user input) -> API request
 */
async function fetchUsers(filters = {}) {
  const params = new URLSearchParams(filters);
  const { data } = await axios.get(`${API_BASE_URL}/users?${params}`);
  return data;
}

/**
 * useUsers Hook - Fetch users list
 * Tests: useQuery with filters, refetch interval (polling)
 */
export function useUsers(filters = {}, options = {}) {
  return useQuery({
    queryKey: queryKeys.users.list(filters),
    queryFn: () => fetchUsers(filters),
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: options.polling ? 30000 : false, // Poll every 30s if enabled
    placeholderData: (previousData) => previousData, // Keep previous data while refetching
    ...options
  });
}

/**
 * Fetch user profile (requires authentication)
 * Tests: Query with authentication headers
 * TAINT FLOW: token (sensitive) -> Authorization header
 */
async function fetchUserProfile(token) {
  const { data } = await axios.get(`${API_BASE_URL}/users/me`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data;
}

/**
 * useUserProfile Hook - Fetch current user profile
 * Tests: Dependent query (depends on token), retry logic
 */
export function useUserProfile(token) {
  return useQuery({
    queryKey: ['userProfile'],
    queryFn: () => fetchUserProfile(token),
    enabled: !!token, // Only fetch if authenticated
    retry: 1, // Only retry once for auth errors
    staleTime: Infinity, // Profile rarely changes
    cacheTime: 30 * 60 * 1000 // Keep in cache for 30 minutes
  });
}

/**
 * Prefetch user - Optimistic data loading
 * Tests: Query prefetching for better UX
 */
export function usePrefetchUser() {
  const queryClient = useQueryClient();

  return (userId) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.users.detail(userId),
      queryFn: () => fetchUser(userId),
      staleTime: 5 * 60 * 1000
    });
  };
}

/**
 * Fetch user's posts (dependent query)
 * Tests: Related data fetching
 */
async function fetchUserPosts(userId) {
  const { data } = await axios.get(`${API_BASE_URL}/users/${userId}/posts`);
  return data;
}

/**
 * useUserPosts Hook - Fetch user's posts
 * Tests: Dependent query that waits for user data
 */
export function useUserPosts(userId) {
  const { data: user } = useUser(userId);

  return useQuery({
    queryKey: ['users', userId, 'posts'],
    queryFn: () => fetchUserPosts(userId),
    enabled: !!user, // Wait for user to load first
    staleTime: 2 * 60 * 1000
  });
}

/**
 * Fetch user statistics
 * Tests: Aggregated data fetching
 */
async function fetchUserStats(userId) {
  const { data } = await axios.get(`${API_BASE_URL}/users/${userId}/stats`);
  return data;
}

/**
 * useUserStats Hook - Real-time user stats with polling
 * Tests: useQuery with refetch interval (live updates)
 */
export function useUserStats(userId, options = {}) {
  return useQuery({
    queryKey: ['users', userId, 'stats'],
    queryFn: () => fetchUserStats(userId),
    enabled: !!userId && options.enabled !== false,
    refetchInterval: 10000, // Refetch every 10 seconds
    refetchIntervalInBackground: false // Stop polling when tab inactive
  });
}

/**
 * Search users
 * Tests: Search query with debouncing (external)
 * TAINT FLOW: searchQuery (user input) -> API request
 */
async function searchUsers(query) {
  if (!query || query.length < 2) {
    return { users: [] };
  }

  const { data } = await axios.get(`${API_BASE_URL}/users/search`, {
    params: { q: query }
  });
  return data;
}

/**
 * useUserSearch Hook - Search users with query
 * Tests: useQuery with search, enabled condition
 */
export function useUserSearch(searchQuery) {
  return useQuery({
    queryKey: ['users', 'search', searchQuery],
    queryFn: () => searchUsers(searchQuery),
    enabled: searchQuery && searchQuery.length >= 2, // Min 2 characters
    staleTime: 30000, // Search results stale after 30s
    cacheTime: 5 * 60 * 1000 // Keep searches for 5 min
  });
}
