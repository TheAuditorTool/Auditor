/**
 * UI Store - Global UI State Management
 * Tests: Multiple independent state slices, boolean flags, notifications queue
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

/**
 * UI Store
 * Tests: Global UI state with persist for theme/preferences
 */
const useUIStore = create(
  devtools(
    persist(
      (set, get) => ({
        // Theme
        theme: 'light', // 'light', 'dark', 'auto'

        // Sidebar
        sidebarOpen: true,
        sidebarCollapsed: false,

        // Modals
        modals: {
          login: false,
          signup: false,
          confirmDelete: false,
          settings: false,
          profile: false
        },

        // Notifications
        notifications: [],

        // Loading states
        loadingStates: {},

        // Errors
        errors: {},

        /**
         * Set theme
         * Tests: Theme switching
         */
        setTheme: (theme) => {
          set({ theme });

          // Apply theme to document
          if (typeof document !== 'undefined') {
            document.documentElement.setAttribute('data-theme', theme);
          }
        },

        /**
         * Toggle theme
         * Tests: Theme toggle between light/dark
         */
        toggleTheme: () => {
          const { theme } = get();
          const newTheme = theme === 'light' ? 'dark' : 'light';
          get().setTheme(newTheme);
        },

        /**
         * Set sidebar open state
         * Tests: Boolean state update
         */
        setSidebarOpen: (open) => {
          set({ sidebarOpen: open });
        },

        /**
         * Toggle sidebar
         * Tests: Boolean toggle
         */
        toggleSidebar: () => {
          set((state) => ({ sidebarOpen: !state.sidebarOpen }));
        },

        /**
         * Set sidebar collapsed state
         * Tests: Sidebar collapse for mobile
         */
        setSidebarCollapsed: (collapsed) => {
          set({ sidebarCollapsed: collapsed });
        },

        /**
         * Toggle sidebar collapse
         * Tests: Boolean toggle
         */
        toggleSidebarCollapse: () => {
          set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }));
        },

        /**
         * Open modal
         * Tests: Nested object update
         */
        openModal: (modalName) => {
          set((state) => ({
            modals: {
              ...state.modals,
              [modalName]: true
            }
          }));
        },

        /**
         * Close modal
         * Tests: Nested object update
         */
        closeModal: (modalName) => {
          set((state) => ({
            modals: {
              ...state.modals,
              [modalName]: false
            }
          }));
        },

        /**
         * Close all modals
         * Tests: Bulk state reset
         */
        closeAllModals: () => {
          set((state) => ({
            modals: Object.keys(state.modals).reduce((acc, key) => {
              acc[key] = false;
              return acc;
            }, {})
          }));
        },

        /**
         * Add notification
         * Tests: Array state push with unique ID
         */
        addNotification: (notification) => {
          const id = `notif-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

          const newNotification = {
            id,
            type: notification.type || 'info', // 'success', 'error', 'warning', 'info'
            title: notification.title,
            message: notification.message,
            duration: notification.duration || 5000,
            createdAt: Date.now()
          };

          set((state) => ({
            notifications: [...state.notifications, newNotification]
          }));

          // Auto-remove after duration
          if (newNotification.duration > 0) {
            setTimeout(() => {
              get().removeNotification(id);
            }, newNotification.duration);
          }

          return id;
        },

        /**
         * Remove notification
         * Tests: Array filtering by ID
         */
        removeNotification: (id) => {
          set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id)
          }));
        },

        /**
         * Clear all notifications
         * Tests: Array reset
         */
        clearNotifications: () => {
          set({ notifications: [] });
        },

        /**
         * Show success notification
         * Tests: Convenience wrapper
         */
        showSuccess: (message, title = 'Success') => {
          return get().addNotification({
            type: 'success',
            title,
            message
          });
        },

        /**
         * Show error notification
         * Tests: Convenience wrapper
         */
        showError: (message, title = 'Error') => {
          return get().addNotification({
            type: 'error',
            title,
            message,
            duration: 0 // Errors don't auto-dismiss
          });
        },

        /**
         * Show warning notification
         * Tests: Convenience wrapper
         */
        showWarning: (message, title = 'Warning') => {
          return get().addNotification({
            type: 'warning',
            title,
            message
          });
        },

        /**
         * Show info notification
         * Tests: Convenience wrapper
         */
        showInfo: (message, title = 'Info') => {
          return get().addNotification({
            type: 'info',
            title,
            message
          });
        },

        /**
         * Set loading state
         * Tests: Dynamic key object update
         */
        setLoading: (key, loading) => {
          set((state) => ({
            loadingStates: {
              ...state.loadingStates,
              [key]: loading
            }
          }));
        },

        /**
         * Get loading state
         * Tests: Dynamic key access
         */
        isLoading: (key) => {
          const { loadingStates } = get();
          return loadingStates[key] || false;
        },

        /**
         * Clear loading state
         * Tests: Object key deletion
         */
        clearLoading: (key) => {
          set((state) => {
            const { [key]: _, ...rest } = state.loadingStates;
            return { loadingStates: rest };
          });
        },

        /**
         * Set error
         * Tests: Error state management
         */
        setError: (key, error) => {
          set((state) => ({
            errors: {
              ...state.errors,
              [key]: error
            }
          }));
        },

        /**
         * Clear error
         * Tests: Error state cleanup
         */
        clearError: (key) => {
          set((state) => {
            const { [key]: _, ...rest } = state.errors;
            return { errors: rest };
          });
        },

        /**
         * Clear all errors
         * Tests: Bulk error reset
         */
        clearAllErrors: () => {
          set({ errors: {} });
        },

        /**
         * Get error
         * Tests: Error retrieval
         */
        getError: (key) => {
          const { errors } = get();
          return errors[key] || null;
        },

        /**
         * Check if any modal is open
         * Tests: Computed boolean from object
         */
        hasOpenModal: () => {
          const { modals } = get();
          return Object.values(modals).some((open) => open);
        },

        /**
         * Get notification count
         * Tests: Array length accessor
         */
        getNotificationCount: () => {
          const { notifications } = get();
          return notifications.length;
        },

        /**
         * Get notifications by type
         * Tests: Array filtering
         */
        getNotificationsByType: (type) => {
          const { notifications } = get();
          return notifications.filter((n) => n.type === type);
        }
      }),
      {
        name: 'ui-storage',
        partialize: (state) => ({
          // Only persist theme and sidebar preferences
          theme: state.theme,
          sidebarOpen: state.sidebarOpen,
          sidebarCollapsed: state.sidebarCollapsed
          // Don't persist: modals, notifications, loadingStates, errors
        })
      }
    ),
    {
      name: 'UIStore',
      enabled: process.env.NODE_ENV === 'development'
    }
  )
);

/**
 * Selectors
 * Tests: Selector patterns for UI state
 */

export const selectTheme = (state) => state.theme;
export const selectSidebarOpen = (state) => state.sidebarOpen;
export const selectSidebarCollapsed = (state) => state.sidebarCollapsed;
export const selectModals = (state) => state.modals;
export const selectNotifications = (state) => state.notifications;
export const selectLoadingStates = (state) => state.loadingStates;
export const selectErrors = (state) => state.errors;

// Modal selectors
export const selectIsModalOpen = (modalName) => (state) =>
  state.modals[modalName] || false;

export const selectHasOpenModal = (state) => state.hasOpenModal();

// Notification selectors
export const selectNotificationCount = (state) => state.getNotificationCount();

export const selectNotificationsByType = (type) => (state) =>
  state.getNotificationsByType(type);

// Loading selectors
export const selectIsLoading = (key) => (state) => state.isLoading(key);

// Error selectors
export const selectError = (key) => (state) => state.getError(key);

export default useUIStore;
