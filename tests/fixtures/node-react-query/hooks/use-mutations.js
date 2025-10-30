/**
 * Mutation Hooks - useMutation for data modifications
 * Tests: useMutation, optimistic updates, cache invalidation, error handling
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { API_BASE_URL, queryKeys } from '../config/query-client';

/**
 * Create user mutation
 * Tests: POST request with mutation
 * TAINT FLOW: userData (user input) -> API request
 */
async function createUser(userData) {
  const { data } = await axios.post(`${API_BASE_URL}/users`, userData);
  return data;
}

/**
 * useCreateUser Hook - Create new user
 * Tests: useMutation with cache invalidation
 */
export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createUser,
    onSuccess: (newUser) => {
      // Invalidate users list to trigger refetch
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });

      // Optionally set the new user in cache
      queryClient.setQueryData(queryKeys.users.detail(newUser.id), newUser);
    },
    onError: (error) => {
      console.error('Failed to create user:', error);
    }
  });
}

/**
 * Update user mutation
 * Tests: PUT request with optimistic update
 * TAINT FLOW: updates (user input) -> API request
 */
async function updateUser({ userId, updates }) {
  const { data } = await axios.put(`${API_BASE_URL}/users/${userId}`, updates);
  return data;
}

/**
 * useUpdateUser Hook - Update existing user
 * Tests: useMutation with optimistic updates and rollback
 */
export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateUser,

    // Optimistic update before server response
    onMutate: async ({ userId, updates }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.users.detail(userId) });

      // Snapshot previous value for rollback
      const previousUser = queryClient.getQueryData(queryKeys.users.detail(userId));

      // Optimistically update cache
      if (previousUser) {
        queryClient.setQueryData(queryKeys.users.detail(userId), (old) => ({
          ...old,
          ...updates
        }));
      }

      // Return context for rollback
      return { previousUser, userId };
    },

    // On success, just invalidate lists
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
    },

    // On error, rollback optimistic update
    onError: (error, variables, context) => {
      if (context?.previousUser) {
        queryClient.setQueryData(
          queryKeys.users.detail(context.userId),
          context.previousUser
        );
      }
    },

    // Always refetch after error or success
    onSettled: (data, error, variables, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.detail(variables.userId) });
    }
  });
}

/**
 * Delete user mutation
 * Tests: DELETE request with cache removal
 */
async function deleteUser(userId) {
  await axios.delete(`${API_BASE_URL}/users/${userId}`);
  return userId;
}

/**
 * useDeleteUser Hook - Delete user
 * Tests: useMutation with cache removal and list invalidation
 */
export function useDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteUser,
    onSuccess: (userId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: queryKeys.users.detail(userId) });

      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
    }
  });
}

/**
 * Create post mutation
 * Tests: POST with relationship data
 * TAINT FLOW: postData (user input) -> API request
 */
async function createPost(postData) {
  const { data } = await axios.post(`${API_BASE_URL}/posts`, postData);
  return data;
}

/**
 * useCreatePost Hook - Create new post
 * Tests: useMutation with multiple cache invalidations
 */
export function useCreatePost() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createPost,
    onSuccess: (newPost) => {
      // Invalidate posts lists
      queryClient.invalidateQueries({ queryKey: queryKeys.posts.lists() });

      // Invalidate user's posts if available
      if (newPost.userId) {
        queryClient.invalidateQueries({
          queryKey: ['users', newPost.userId, 'posts']
        });
      }

      // Set in cache
      queryClient.setQueryData(queryKeys.posts.detail(newPost.id), newPost);
    }
  });
}

/**
 * Like post mutation
 * Tests: POST with optimistic UI update
 */
async function likePost(postId) {
  const { data } = await axios.post(`${API_BASE_URL}/posts/${postId}/like`);
  return data;
}

/**
 * useLikePost Hook - Like a post
 * Tests: Optimistic update for instant UI feedback
 */
export function useLikePost() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: likePost,

    onMutate: async (postId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.posts.detail(postId) });

      const previousPost = queryClient.getQueryData(queryKeys.posts.detail(postId));

      // Optimistically increment like count
      if (previousPost) {
        queryClient.setQueryData(queryKeys.posts.detail(postId), (old) => ({
          ...old,
          likes: old.likes + 1,
          isLiked: true
        }));
      }

      return { previousPost, postId };
    },

    onError: (error, postId, context) => {
      // Rollback on error
      if (context?.previousPost) {
        queryClient.setQueryData(queryKeys.posts.detail(context.postId), context.previousPost);
      }
    }
  });
}

/**
 * Upload file mutation
 * Tests: File upload with progress tracking
 * TAINT FLOW: file (user upload) -> FormData -> API
 */
async function uploadFile(file, onUploadProgress) {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await axios.post(`${API_BASE_URL}/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress
  });

  return data;
}

/**
 * useUploadFile Hook - Upload file with progress
 * Tests: useMutation with progress tracking
 */
export function useUploadFile() {
  return useMutation({
    mutationFn: ({ file, onProgress }) => uploadFile(file, onProgress)
  });
}

/**
 * Bulk delete mutation
 * Tests: Batch operation with multiple cache updates
 */
async function bulkDeleteUsers(userIds) {
  const { data } = await axios.post(`${API_BASE_URL}/users/bulk-delete`, { userIds });
  return data;
}

/**
 * useBulkDeleteUsers Hook - Delete multiple users
 * Tests: Batch mutation with bulk cache invalidation
 */
export function useBulkDeleteUsers() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: bulkDeleteUsers,
    onSuccess: (result, userIds) => {
      // Remove each user from cache
      userIds.forEach((userId) => {
        queryClient.removeQueries({ queryKey: queryKeys.users.detail(userId) });
      });

      // Invalidate all lists
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
    }
  });
}

/**
 * Update user settings with debouncing
 * Tests: Mutation for incremental updates
 */
async function updateUserSettings({ userId, settings }) {
  const { data } = await axios.patch(`${API_BASE_URL}/users/${userId}/settings`, settings);
  return data;
}

/**
 * useUpdateSettings Hook - Update user settings
 * Tests: useMutation with debounced updates
 */
export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateUserSettings,
    onSuccess: (data, variables) => {
      // Update settings in cache
      queryClient.setQueryData(['userProfile'], (old) =>
        old ? { ...old, settings: { ...old.settings, ...variables.settings } } : old
      );
    }
  });
}
