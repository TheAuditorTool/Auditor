import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

const useUIStore = create(
  devtools(
    persist(
      (set, get) => ({
        theme: "light",

        sidebarOpen: true,
        sidebarCollapsed: false,

        modals: {
          login: false,
          signup: false,
          confirmDelete: false,
          settings: false,
          profile: false,
        },

        notifications: [],

        loadingStates: {},

        errors: {},

        setTheme: (theme) => {
          set({ theme });

          if (typeof document !== "undefined") {
            document.documentElement.setAttribute("data-theme", theme);
          }
        },

        toggleTheme: () => {
          const { theme } = get();
          const newTheme = theme === "light" ? "dark" : "light";
          get().setTheme(newTheme);
        },

        setSidebarOpen: (open) => {
          set({ sidebarOpen: open });
        },

        toggleSidebar: () => {
          set((state) => ({ sidebarOpen: !state.sidebarOpen }));
        },

        setSidebarCollapsed: (collapsed) => {
          set({ sidebarCollapsed: collapsed });
        },

        toggleSidebarCollapse: () => {
          set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }));
        },

        openModal: (modalName) => {
          set((state) => ({
            modals: {
              ...state.modals,
              [modalName]: true,
            },
          }));
        },

        closeModal: (modalName) => {
          set((state) => ({
            modals: {
              ...state.modals,
              [modalName]: false,
            },
          }));
        },

        closeAllModals: () => {
          set((state) => ({
            modals: Object.keys(state.modals).reduce((acc, key) => {
              acc[key] = false;
              return acc;
            }, {}),
          }));
        },

        addNotification: (notification) => {
          const id = `notif-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

          const newNotification = {
            id,
            type: notification.type || "info",
            title: notification.title,
            message: notification.message,
            duration: notification.duration || 5000,
            createdAt: Date.now(),
          };

          set((state) => ({
            notifications: [...state.notifications, newNotification],
          }));

          if (newNotification.duration > 0) {
            setTimeout(() => {
              get().removeNotification(id);
            }, newNotification.duration);
          }

          return id;
        },

        removeNotification: (id) => {
          set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
          }));
        },

        clearNotifications: () => {
          set({ notifications: [] });
        },

        showSuccess: (message, title = "Success") => {
          return get().addNotification({
            type: "success",
            title,
            message,
          });
        },

        showError: (message, title = "Error") => {
          return get().addNotification({
            type: "error",
            title,
            message,
            duration: 0,
          });
        },

        showWarning: (message, title = "Warning") => {
          return get().addNotification({
            type: "warning",
            title,
            message,
          });
        },

        showInfo: (message, title = "Info") => {
          return get().addNotification({
            type: "info",
            title,
            message,
          });
        },

        setLoading: (key, loading) => {
          set((state) => ({
            loadingStates: {
              ...state.loadingStates,
              [key]: loading,
            },
          }));
        },

        isLoading: (key) => {
          const { loadingStates } = get();
          return loadingStates[key] || false;
        },

        clearLoading: (key) => {
          set((state) => {
            const { [key]: _, ...rest } = state.loadingStates;
            return { loadingStates: rest };
          });
        },

        setError: (key, error) => {
          set((state) => ({
            errors: {
              ...state.errors,
              [key]: error,
            },
          }));
        },

        clearError: (key) => {
          set((state) => {
            const { [key]: _, ...rest } = state.errors;
            return { errors: rest };
          });
        },

        clearAllErrors: () => {
          set({ errors: {} });
        },

        getError: (key) => {
          const { errors } = get();
          return errors[key] || null;
        },

        hasOpenModal: () => {
          const { modals } = get();
          return Object.values(modals).some((open) => open);
        },

        getNotificationCount: () => {
          const { notifications } = get();
          return notifications.length;
        },

        getNotificationsByType: (type) => {
          const { notifications } = get();
          return notifications.filter((n) => n.type === type);
        },
      }),
      {
        name: "ui-storage",
        partialize: (state) => ({
          theme: state.theme,
          sidebarOpen: state.sidebarOpen,
          sidebarCollapsed: state.sidebarCollapsed,
        }),
      },
    ),
    {
      name: "UIStore",
      enabled: process.env.NODE_ENV === "development",
    },
  ),
);

export const selectTheme = (state) => state.theme;
export const selectSidebarOpen = (state) => state.sidebarOpen;
export const selectSidebarCollapsed = (state) => state.sidebarCollapsed;
export const selectModals = (state) => state.modals;
export const selectNotifications = (state) => state.notifications;
export const selectLoadingStates = (state) => state.loadingStates;
export const selectErrors = (state) => state.errors;

export const selectIsModalOpen = (modalName) => (state) =>
  state.modals[modalName] || false;

export const selectHasOpenModal = (state) => state.hasOpenModal();

export const selectNotificationCount = (state) => state.getNotificationCount();

export const selectNotificationsByType = (type) => (state) =>
  state.getNotificationsByType(type);

export const selectIsLoading = (key) => (state) => state.isLoading(key);

export const selectError = (key) => (state) => state.getError(key);

export default useUIStore;
