/**
 * useAuth custom hook
 *
 * Tests:
 * - Custom hook extraction
 * - Hook composition (useState, useEffect, useCallback in custom hook)
 * - Context API usage
 * - Local storage taint source
 */

import { useState, useEffect, useCallback, useContext } from 'react';
import axios from 'axios';
import { AuthContext } from '../contexts/AuthContext';

/**
 * useAuth custom hook
 *
 * Manages authentication state and provides login/logout functions.
 *
 * Tests:
 * - Custom hook naming convention (starts with 'use')
 * - Hook composition within custom hook
 * - Taint from localStorage
 *
 * @returns {Object} Auth state and functions
 */
function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /**
   * Load user from localStorage on mount
   *
   * Tests:
   * - TAINT SOURCE: localStorage.getItem (user-controlled data)
   * - useEffect with empty dependency array (runs once)
   */
  useEffect(() => {
    const loadUser = async () => {
      try {
        // TAINT SOURCE: localStorage (can be manipulated by user)
        const token = localStorage.getItem('authToken');

        if (token) {
          // TAINT FLOW: token from localStorage → API header
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

          const response = await axios.get('/api/auth/me');
          setUser(response.data);
        }
      } catch (err) {
        console.error('Failed to load user:', err);
        localStorage.removeItem('authToken');
      } finally {
        setLoading(false);
      }
    };

    loadUser();
  }, []); // Empty deps = run once on mount

  /**
   * Login function with useCallback
   *
   * Tests:
   * - useCallback for memoized function
   * - Taint flow from credentials to API
   * - localStorage write (taint sink)
   */
  const login = useCallback(async (email, password) => {
    setLoading(true);
    setError(null);

    try {
      // TAINT SOURCE: email and password from user input
      const response = await axios.post('/api/auth/login', {
        email,
        password
      });

      const { token, user } = response.data;

      // TAINT SINK: Store token in localStorage (user-controlled storage)
      localStorage.setItem('authToken', token);

      // Set default header for future requests
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

      setUser(user);
      return { success: true };
    } catch (err) {
      const message = err.response?.data?.error || 'Login failed';
      setError(message);
      return { success: false, error: message };
    } finally {
      setLoading(false);
    }
  }, []); // No dependencies = function never changes

  /**
   * Logout function with useCallback
   *
   * Tests:
   * - useCallback with dependency on user
   * - Clear localStorage (security best practice)
   */
  const logout = useCallback(async () => {
    try {
      if (user) {
        await axios.post('/api/auth/logout');
      }

      // Clear auth state
      localStorage.removeItem('authToken');
      delete axios.defaults.headers.common['Authorization'];
      setUser(null);
    } catch (err) {
      console.error('Logout failed:', err);
    }
  }, [user]); // Depends on user

  return {
    user,
    loading,
    error,
    login,
    logout,
    isAuthenticated: !!user
  };
}

export default useAuth;
