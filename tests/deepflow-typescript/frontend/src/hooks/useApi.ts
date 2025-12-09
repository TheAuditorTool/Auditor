/**
 * API hook - Custom React hook for API calls.
 *
 * Provides loading state and error handling for API requests.
 */

import { useState, useCallback } from 'react';

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  execute: (...args: any[]) => Promise<void>;
}

/**
 * Custom hook for API calls.
 *
 * @param apiFunction - API function to call
 * @returns Object with data, loading, error, and execute function
 */
export function useApi<T>(
  apiFunction: (...args: any[]) => Promise<T>
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(
    async (...args: any[]) => {
      setLoading(true);
      setError(null);
      try {
        // TAINTED args flow through to API call
        const result = await apiFunction(...args);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
      }
      setLoading(false);
    },
    [apiFunction]
  );

  return { data, loading, error, execute };
}
