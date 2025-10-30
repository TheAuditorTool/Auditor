/**
 * Authentication Store with Persist Middleware
 * Tests: Store creation, middleware, state updates, derived state, security patterns
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { devtools } from 'zustand/middleware';

/**
 * Authentication Store
 * Tests: Zustand store with persist and devtools middleware
 * TAINT FLOW: user credentials -> login action -> state
 */
const useAuthStore = create(
  devtools(
    persist(
      (set, get) => ({
        // State
        user: null,
        token: null,
        refreshToken: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        lastLoginAt: null,
        sessionExpiresAt: null,

        /**
         * Login action
         * Tests: State update with user credentials
         * TAINT FLOW: credentials (user input) -> user state
         */
        login: async (credentials) => {
          set({ isLoading: true, error: null });

          try {
            // Simulate API call
            const response = await fetch('/api/auth/login', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(credentials)
            });

            if (!response.ok) {
              throw new Error('Login failed');
            }

            const data = await response.json();

            // Update state with auth data
            set({
              user: data.user,
              token: data.token,
              refreshToken: data.refreshToken,
              isAuthenticated: true,
              isLoading: false,
              lastLoginAt: new Date().toISOString(),
              sessionExpiresAt: data.expiresAt,
              error: null
            });

            return { success: true };
          } catch (error) {
            set({
              isLoading: false,
              error: error.message,
              isAuthenticated: false
            });

            return { success: false, error: error.message };
          }
        },

        /**
         * Logout action
         * Tests: State reset
         */
        logout: () => {
          set({
            user: null,
            token: null,
            refreshToken: null,
            isAuthenticated: false,
            lastLoginAt: null,
            sessionExpiresAt: null,
            error: null
          });
        },

        /**
         * Refresh token action
         * Tests: Token rotation
         */
        refreshSession: async () => {
          const { refreshToken } = get();

          if (!refreshToken) {
            return { success: false, error: 'No refresh token' };
          }

          try {
            const response = await fetch('/api/auth/refresh', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ refreshToken })
            });

            const data = await response.json();

            set({
              token: data.token,
              refreshToken: data.refreshToken,
              sessionExpiresAt: data.expiresAt
            });

            return { success: true };
          } catch (error) {
            // Token refresh failed - logout user
            get().logout();
            return { success: false, error: error.message };
          }
        },

        /**
         * Update user profile
         * Tests: Partial state update
         * TAINT FLOW: profileData (user input) -> user state
         */
        updateProfile: (profileData) => {
          set((state) => ({
            user: {
              ...state.user,
              ...profileData
            }
          }));
        },

        /**
         * Check if session is expired
         * Tests: Derived state computation
         */
        isSessionExpired: () => {
          const { sessionExpiresAt } = get();

          if (!sessionExpiresAt) {
            return true;
          }

          return new Date(sessionExpiresAt) < new Date();
        },

        /**
         * Get time until session expiry
         * Tests: Computed value
         */
        getSessionTimeRemaining: () => {
          const { sessionExpiresAt } = get();

          if (!sessionExpiresAt) {
            return 0;
          }

          const now = new Date();
          const expiry = new Date(sessionExpiresAt);
          const diff = expiry - now;

          return Math.max(0, diff);
        },

        /**
         * Check if user has permission
         * Tests: Permission checking logic
         */
        hasPermission: (permission) => {
          const { user } = get();

          if (!user || !user.permissions) {
            return false;
          }

          return user.permissions.includes(permission);
        },

        /**
         * Check if user has role
         * Tests: Role checking logic
         */
        hasRole: (role) => {
          const { user } = get();

          if (!user || !user.roles) {
            return false;
          }

          return user.roles.includes(role);
        },

        /**
         * Clear error
         * Tests: Error state management
         */
        clearError: () => {
          set({ error: null });
        }
      }),
      {
        name: 'auth-storage', // localStorage key
        storage: createJSONStorage(() => localStorage),
        partialize: (state) => ({
          // Only persist these fields
          user: state.user,
          token: state.token,
          refreshToken: state.refreshToken,
          isAuthenticated: state.isAuthenticated,
          lastLoginAt: state.lastLoginAt,
          sessionExpiresAt: state.sessionExpiresAt
          // Don't persist: isLoading, error
        }),
        onRehydrateStorage: () => {
          return (state, error) => {
            if (error) {
              console.error('Failed to rehydrate auth store:', error);
            } else if (state) {
              // Check if session expired on rehydration
              if (state.isSessionExpired()) {
                state.logout();
              }
            }
          };
        }
      }
    ),
    {
      name: 'AuthStore',
      enabled: process.env.NODE_ENV === 'development'
    }
  )
);

/**
 * Selectors - Optimize re-renders by selecting specific state slices
 * Tests: Selector patterns
 */

export const selectUser = (state) => state.user;
export const selectIsAuthenticated = (state) => state.isAuthenticated;
export const selectToken = (state) => state.token;
export const selectError = (state) => state.error;
export const selectIsLoading = (state) => state.isLoading;

// Derived selectors
export const selectUserEmail = (state) => state.user?.email;
export const selectUserRole = (state) => state.user?.roles?.[0];
export const selectHasActiveSession = (state) =>
  state.isAuthenticated && !state.isSessionExpired();

export default useAuthStore;
