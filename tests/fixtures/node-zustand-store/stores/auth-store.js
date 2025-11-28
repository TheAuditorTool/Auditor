import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { devtools } from "zustand/middleware";

const useAuthStore = create(
  devtools(
    persist(
      (set, get) => ({
        user: null,
        token: null,
        refreshToken: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        lastLoginAt: null,
        sessionExpiresAt: null,

        login: async (credentials) => {
          set({ isLoading: true, error: null });

          try {
            const response = await fetch("/api/auth/login", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(credentials),
            });

            if (!response.ok) {
              throw new Error("Login failed");
            }

            const data = await response.json();

            set({
              user: data.user,
              token: data.token,
              refreshToken: data.refreshToken,
              isAuthenticated: true,
              isLoading: false,
              lastLoginAt: new Date().toISOString(),
              sessionExpiresAt: data.expiresAt,
              error: null,
            });

            return { success: true };
          } catch (error) {
            set({
              isLoading: false,
              error: error.message,
              isAuthenticated: false,
            });

            return { success: false, error: error.message };
          }
        },

        logout: () => {
          set({
            user: null,
            token: null,
            refreshToken: null,
            isAuthenticated: false,
            lastLoginAt: null,
            sessionExpiresAt: null,
            error: null,
          });
        },

        refreshSession: async () => {
          const { refreshToken } = get();

          if (!refreshToken) {
            return { success: false, error: "No refresh token" };
          }

          try {
            const response = await fetch("/api/auth/refresh", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ refreshToken }),
            });

            const data = await response.json();

            set({
              token: data.token,
              refreshToken: data.refreshToken,
              sessionExpiresAt: data.expiresAt,
            });

            return { success: true };
          } catch (error) {
            get().logout();
            return { success: false, error: error.message };
          }
        },

        updateProfile: (profileData) => {
          set((state) => ({
            user: {
              ...state.user,
              ...profileData,
            },
          }));
        },

        isSessionExpired: () => {
          const { sessionExpiresAt } = get();

          if (!sessionExpiresAt) {
            return true;
          }

          return new Date(sessionExpiresAt) < new Date();
        },

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

        hasPermission: (permission) => {
          const { user } = get();

          if (!user || !user.permissions) {
            return false;
          }

          return user.permissions.includes(permission);
        },

        hasRole: (role) => {
          const { user } = get();

          if (!user || !user.roles) {
            return false;
          }

          return user.roles.includes(role);
        },

        clearError: () => {
          set({ error: null });
        },
      }),
      {
        name: "auth-storage",
        storage: createJSONStorage(() => localStorage),
        partialize: (state) => ({
          user: state.user,
          token: state.token,
          refreshToken: state.refreshToken,
          isAuthenticated: state.isAuthenticated,
          lastLoginAt: state.lastLoginAt,
          sessionExpiresAt: state.sessionExpiresAt,
        }),
        onRehydrateStorage: () => {
          return (state, error) => {
            if (error) {
              console.error("Failed to rehydrate auth store:", error);
            } else if (state) {
              if (state.isSessionExpired()) {
                state.logout();
              }
            }
          };
        },
      },
    ),
    {
      name: "AuthStore",
      enabled: process.env.NODE_ENV === "development",
    },
  ),
);

export const selectUser = (state) => state.user;
export const selectIsAuthenticated = (state) => state.isAuthenticated;
export const selectToken = (state) => state.token;
export const selectError = (state) => state.error;
export const selectIsLoading = (state) => state.isLoading;

export const selectUserEmail = (state) => state.user?.email;
export const selectUserRole = (state) => state.user?.roles?.[0];
export const selectHasActiveSession = (state) =>
  state.isAuthenticated && !state.isSessionExpired();

export default useAuthStore;
