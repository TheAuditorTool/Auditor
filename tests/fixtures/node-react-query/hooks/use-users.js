import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { API_BASE_URL, queryKeys } from "../config/query-client";

async function fetchUser(userId) {
  const { data } = await axios.get(`${API_BASE_URL}/users/${userId}`);
  return data;
}

export function useUser(userId, options = {}) {
  return useQuery({
    queryKey: queryKeys.users.detail(userId),
    queryFn: () => fetchUser(userId),
    enabled: !!userId,
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}

async function fetchUsers(filters = {}) {
  const params = new URLSearchParams(filters);
  const { data } = await axios.get(`${API_BASE_URL}/users?${params}`);
  return data;
}

export function useUsers(filters = {}, options = {}) {
  return useQuery({
    queryKey: queryKeys.users.list(filters),
    queryFn: () => fetchUsers(filters),
    staleTime: 2 * 60 * 1000,
    refetchInterval: options.polling ? 30000 : false,
    placeholderData: (previousData) => previousData,
    ...options,
  });
}

async function fetchUserProfile(token) {
  const { data } = await axios.get(`${API_BASE_URL}/users/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return data;
}

export function useUserProfile(token) {
  return useQuery({
    queryKey: ["userProfile"],
    queryFn: () => fetchUserProfile(token),
    enabled: !!token,
    retry: 1,
    staleTime: Infinity,
    cacheTime: 30 * 60 * 1000,
  });
}

export function usePrefetchUser() {
  const queryClient = useQueryClient();

  return (userId) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.users.detail(userId),
      queryFn: () => fetchUser(userId),
      staleTime: 5 * 60 * 1000,
    });
  };
}

async function fetchUserPosts(userId) {
  const { data } = await axios.get(`${API_BASE_URL}/users/${userId}/posts`);
  return data;
}

export function useUserPosts(userId) {
  const { data: user } = useUser(userId);

  return useQuery({
    queryKey: ["users", userId, "posts"],
    queryFn: () => fetchUserPosts(userId),
    enabled: !!user,
    staleTime: 2 * 60 * 1000,
  });
}

async function fetchUserStats(userId) {
  const { data } = await axios.get(`${API_BASE_URL}/users/${userId}/stats`);
  return data;
}

export function useUserStats(userId, options = {}) {
  return useQuery({
    queryKey: ["users", userId, "stats"],
    queryFn: () => fetchUserStats(userId),
    enabled: !!userId && options.enabled !== false,
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
  });
}

async function searchUsers(query) {
  if (!query || query.length < 2) {
    return { users: [] };
  }

  const { data } = await axios.get(`${API_BASE_URL}/users/search`, {
    params: { q: query },
  });
  return data;
}

export function useUserSearch(searchQuery) {
  return useQuery({
    queryKey: ["users", "search", searchQuery],
    queryFn: () => searchUsers(searchQuery),
    enabled: searchQuery && searchQuery.length >= 2,
    staleTime: 30000,
    cacheTime: 5 * 60 * 1000,
  });
}
