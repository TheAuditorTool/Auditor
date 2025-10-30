/**
 * useAuth composable for authentication
 *
 * Tests:
 * - Custom composable extraction
 * - Composable with reactive refs
 * - localStorage as taint source
 * - Taint flows: localStorage -> ref -> axios API calls
 */

import { ref, computed, onMounted } from 'vue';
import axios from 'axios';

/**
 * useAuth composable
 * Tests: Custom composable naming convention (starts with 'use')
 */
export function useAuth() {
  const user = ref(null);
  const loading = ref(true);
  const error = ref(null);
  const token = ref(null);

  /**
   * Computed: isAuthenticated
   * Tests: Computed property in composable
   */
  const isAuthenticated = computed(() => !!user.value);

  /**
   * Computed: isAdmin
   * Tests: Computed property with role check
   */
  const isAdmin = computed(() => user.value?.role === 'admin');

  /**
   * Load user from localStorage and verify token
   * Tests:
   * - TAINT SOURCE: localStorage (user-controlled)
   * - Taint flow: localStorage -> axios headers
   */
  async function loadUser() {
    try {
      // TAINT SOURCE: localStorage (can be manipulated by user)
      const storedToken = localStorage.getItem('authToken');

      if (storedToken) {
        token.value = storedToken;

        // TAINT SINK: Set Authorization header with localStorage token
        axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;

        // Verify token by fetching user data
        const response = await axios.get('/api/auth/me');
        user.value = response.data;
      }
    } catch (err) {
      error.value = err.message;
      // Token invalid, clear it
      localStorage.removeItem('authToken');
      delete axios.defaults.headers.common['Authorization'];
    } finally {
      loading.value = false;
    }
  }

  /**
   * Login function
   * Tests:
   * - Taint from credentials -> axios POST
   * - TAINT SINK: Store token in localStorage
   */
  async function login(email, password) {
    loading.value = true;
    error.value = null;

    try {
      // TAINT SOURCE: email and password from user input
      const response = await axios.post('/api/auth/login', {
        email,
        password
      });

      const { token: authToken, user: userData } = response.data;

      // TAINT SINK: Store token in localStorage (user-controlled storage)
      localStorage.setItem('authToken', authToken);
      token.value = authToken;

      // Set default header for future requests
      axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`;

      user.value = userData;
      return { success: true };
    } catch (err) {
      error.value = err.response?.data?.error || 'Login failed';
      return { success: false, error: error.value };
    } finally {
      loading.value = false;
    }
  }

  /**
   * Logout function
   * Tests: Clear localStorage and axios headers
   */
  async function logout() {
    try {
      if (user.value) {
        await axios.post('/api/auth/logout');
      }

      // Clear auth state
      localStorage.removeItem('authToken');
      delete axios.defaults.headers.common['Authorization'];

      user.value = null;
      token.value = null;
    } catch (err) {
      console.error('Logout failed:', err);
    }
  }

  /**
   * Refresh user data
   * Tests: Refetch user from API
   */
  async function refreshUser() {
    if (!token.value) return;

    try {
      const response = await axios.get('/api/auth/me');
      user.value = response.data;
    } catch (err) {
      console.error('Failed to refresh user:', err);
    }
  }

  // Load user on composable initialization
  onMounted(() => {
    loadUser();
  });

  // Return reactive refs and functions
  return {
    user,
    loading,
    error,
    token,
    isAuthenticated,
    isAdmin,
    login,
    logout,
    refreshUser
  };
}
