import { useInfiniteQuery } from "@tanstack/react-query";
import axios from "axios";
import { API_BASE_URL, queryKeys } from "../config/query-client";

async function fetchPostsPage({ pageParam = 1, filters = {} }) {
  const params = new URLSearchParams({
    page: pageParam,
    limit: 20,
    ...filters,
  });

  const { data } = await axios.get(`${API_BASE_URL}/posts?${params}`);
  return data;
}

export function useInfinitePosts(filters = {}) {
  return useInfiniteQuery({
    queryKey: queryKeys.posts.infinite(filters),
    queryFn: ({ pageParam }) => fetchPostsPage({ pageParam, filters }),
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => {
      return lastPage.hasMore ? lastPage.nextPage : undefined;
    },
    getPreviousPageParam: (firstPage, allPages) => {
      return firstPage.page > 1 ? firstPage.page - 1 : undefined;
    },
    staleTime: 2 * 60 * 1000,
  });
}

async function fetchProductsPage({ pageParam, filters = {} }) {
  const params = new URLSearchParams({
    limit: 20,
    ...filters,
  });

  if (pageParam) {
    params.append("cursor", pageParam);
  }

  const { data } = await axios.get(`${API_BASE_URL}/products?${params}`);
  return data;
}

export function useInfiniteProducts(filters = {}) {
  return useInfiniteQuery({
    queryKey: [...queryKeys.products.all, "infinite", filters],
    queryFn: ({ pageParam }) => fetchProductsPage({ pageParam, filters }),
    initialPageParam: undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor || undefined,
    select: (data) => ({
      pages: data.pages,
      pageParams: data.pageParams,
      products: data.pages.flatMap((page) => page.products),
    }),
    staleTime: 5 * 60 * 1000,
  });
}

async function fetchCommentsPage({ postId, pageParam = 1 }) {
  const { data } = await axios.get(
    `${API_BASE_URL}/posts/${postId}/comments?page=${pageParam}&limit=50`,
  );
  return data;
}

export function useInfiniteComments(postId) {
  return useInfiniteQuery({
    queryKey: [...queryKeys.comments.byPost(postId), "infinite"],
    queryFn: ({ pageParam }) => fetchCommentsPage({ postId, pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      return lastPage.hasMore ? lastPage.nextPage : undefined;
    },
    enabled: !!postId,
    staleTime: 60000,
  });
}

async function searchProductsPage({ pageParam = 1, query, category }) {
  const params = new URLSearchParams({
    q: query,
    category: category || "",
    page: pageParam,
    limit: 20,
  });

  const { data } = await axios.get(`${API_BASE_URL}/products/search?${params}`);
  return data;
}

export function useInfiniteProductSearch(query, category) {
  return useInfiniteQuery({
    queryKey: [
      ...queryKeys.products.all,
      "search-infinite",
      { query, category },
    ],
    queryFn: ({ pageParam }) =>
      searchProductsPage({ pageParam, query, category }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.nextPage || undefined,
    enabled: query && query.length >= 2,
    staleTime: 30000,
  });
}

async function fetchOrdersPage({ userId, pageParam = 1, filters = {} }) {
  const params = new URLSearchParams({
    page: pageParam,
    limit: 10,
    ...filters,
  });

  const { data } = await axios.get(
    `${API_BASE_URL}/users/${userId}/orders?${params}`,
  );
  return data;
}

export function useInfiniteOrders(userId, filters = {}) {
  return useInfiniteQuery({
    queryKey: [...queryKeys.orders.all, "infinite", userId, filters],
    queryFn: ({ pageParam }) => fetchOrdersPage({ userId, pageParam, filters }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.nextPage || undefined,
    enabled: !!userId,
    staleTime: 60000,
  });
}
