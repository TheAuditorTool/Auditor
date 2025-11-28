import { useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { API_BASE_URL, queryKeys } from "../config/query-client";

async function createUser(userData) {
  const { data } = await axios.post(`${API_BASE_URL}/users`, userData);
  return data;
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createUser,
    onSuccess: (newUser) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });

      queryClient.setQueryData(queryKeys.users.detail(newUser.id), newUser);
    },
    onError: (error) => {
      console.error("Failed to create user:", error);
    },
  });
}

async function updateUser({ userId, updates }) {
  const { data } = await axios.put(`${API_BASE_URL}/users/${userId}`, updates);
  return data;
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateUser,

    onMutate: async ({ userId, updates }) => {
      await queryClient.cancelQueries({
        queryKey: queryKeys.users.detail(userId),
      });

      const previousUser = queryClient.getQueryData(
        queryKeys.users.detail(userId),
      );

      if (previousUser) {
        queryClient.setQueryData(queryKeys.users.detail(userId), (old) => ({
          ...old,
          ...updates,
        }));
      }

      return { previousUser, userId };
    },

    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
    },

    onError: (error, variables, context) => {
      if (context?.previousUser) {
        queryClient.setQueryData(
          queryKeys.users.detail(context.userId),
          context.previousUser,
        );
      }
    },

    onSettled: (data, error, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.users.detail(variables.userId),
      });
    },
  });
}

async function deleteUser(userId) {
  await axios.delete(`${API_BASE_URL}/users/${userId}`);
  return userId;
}

export function useDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteUser,
    onSuccess: (userId) => {
      queryClient.removeQueries({ queryKey: queryKeys.users.detail(userId) });

      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
    },
  });
}

async function createPost(postData) {
  const { data } = await axios.post(`${API_BASE_URL}/posts`, postData);
  return data;
}

export function useCreatePost() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createPost,
    onSuccess: (newPost) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.posts.lists() });

      if (newPost.userId) {
        queryClient.invalidateQueries({
          queryKey: ["users", newPost.userId, "posts"],
        });
      }

      queryClient.setQueryData(queryKeys.posts.detail(newPost.id), newPost);
    },
  });
}

async function likePost(postId) {
  const { data } = await axios.post(`${API_BASE_URL}/posts/${postId}/like`);
  return data;
}

export function useLikePost() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: likePost,

    onMutate: async (postId) => {
      await queryClient.cancelQueries({
        queryKey: queryKeys.posts.detail(postId),
      });

      const previousPost = queryClient.getQueryData(
        queryKeys.posts.detail(postId),
      );

      if (previousPost) {
        queryClient.setQueryData(queryKeys.posts.detail(postId), (old) => ({
          ...old,
          likes: old.likes + 1,
          isLiked: true,
        }));
      }

      return { previousPost, postId };
    },

    onError: (error, postId, context) => {
      if (context?.previousPost) {
        queryClient.setQueryData(
          queryKeys.posts.detail(context.postId),
          context.previousPost,
        );
      }
    },
  });
}

async function uploadFile(file, onUploadProgress) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await axios.post(`${API_BASE_URL}/upload`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    onUploadProgress,
  });

  return data;
}

export function useUploadFile() {
  return useMutation({
    mutationFn: ({ file, onProgress }) => uploadFile(file, onProgress),
  });
}

async function bulkDeleteUsers(userIds) {
  const { data } = await axios.post(`${API_BASE_URL}/users/bulk-delete`, {
    userIds,
  });
  return data;
}

export function useBulkDeleteUsers() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: bulkDeleteUsers,
    onSuccess: (result, userIds) => {
      userIds.forEach((userId) => {
        queryClient.removeQueries({ queryKey: queryKeys.users.detail(userId) });
      });

      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
    },
  });
}

async function updateUserSettings({ userId, settings }) {
  const { data } = await axios.patch(
    `${API_BASE_URL}/users/${userId}/settings`,
    settings,
  );
  return data;
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateUserSettings,
    onSuccess: (data, variables) => {
      queryClient.setQueryData(["userProfile"], (old) =>
        old
          ? { ...old, settings: { ...old.settings, ...variables.settings } }
          : old,
      );
    },
  });
}
