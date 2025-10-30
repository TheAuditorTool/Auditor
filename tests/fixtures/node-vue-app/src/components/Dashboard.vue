<template>
  <div v-if="!isAuthenticated" class="login-prompt">
    <p>Please log in to access the dashboard.</p>
  </div>

  <div v-else class="dashboard">
    <h1>Welcome, {{ user.username }}</h1>

    <div v-if="stats" class="stats-grid">
      <div class="stat-card">
        <h3>Orders</h3>
        <p class="stat-value">{{ stats.orderCount }}</p>
      </div>
      <div class="stat-card">
        <h3>Total Spent</h3>
        <p class="stat-value">${{ stats.totalSpent }}</p>
      </div>
      <div class="stat-card">
        <h3>Unique Products</h3>
        <p class="stat-value">{{ stats.uniqueProducts }}</p>
      </div>
    </div>

    <div class="notifications-section">
      <h2>Notifications ({{ unreadCount }} unread)</h2>

      <div class="filters">
        <select v-model="notificationFilter">
          <option value="">All Notifications</option>
          <option value="unread">Unread Only</option>
          <option value="orders">Orders</option>
          <option value="promotions">Promotions</option>
        </select>
        <button @click="refreshNotifications">Refresh</button>
      </div>

      <div class="notification-list">
        <div
          v-for="notification in filteredNotifications"
          :key="notification.id"
          :class="['notification-card', { unread: !notification.read }]"
          @click="markAsRead(notification.id)"
        >
          <p>{{ notification.message }}</p>
          <span class="timestamp">{{ formatDate(notification.createdAt) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * Dashboard component with complex reactive patterns
 *
 * Tests:
 * - Custom composable usage (useAuth)
 * - Multiple computed properties with tainted dependencies
 * - Complex watchers with multiple sources
 * - Taint flows: user.id (from localStorage token) -> API calls
 * - Multi-source taint: user.id + notificationFilter -> API calls
 */

import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import axios from 'axios';
import { useAuth } from '../composables/useAuth';

export default {
  name: 'Dashboard',

  props: {
    filter: {
      type: String,
      default: ''
      // TAINT SOURCE: filter from parent component (potentially from URL)
    }
  },

  setup(props) {
    // Use auth composable
    // TAINT: user.id comes from localStorage token (useAuth composable)
    const { user, isAuthenticated, isAdmin, logout } = useAuth();

    // Reactive refs
    const stats = ref(null);
    const notifications = ref([]);
    const notificationFilter = ref(props.filter);  // TAINT SOURCE: Prop

    let refreshInterval = null;

    /**
     * Computed: unreadCount
     * Tests: Computed property with array filter
     */
    const unreadCount = computed(() => {
      return notifications.value.filter(n => !n.read).length;
    });

    /**
     * Computed: filteredNotifications
     * Tests: Computed property with tainted filter dependency
     */
    const filteredNotifications = computed(() => {
      let filtered = notifications.value;

      // TAINT FLOW: notificationFilter (user input) -> filter logic
      if (notificationFilter.value) {
        switch (notificationFilter.value) {
          case 'unread':
            filtered = filtered.filter(n => !n.read);
            break;
          case 'orders':
            filtered = filtered.filter(n => n.type === 'order');
            break;
          case 'promotions':
            filtered = filtered.filter(n => n.type === 'promotion');
            break;
        }
      }

      return filtered;
    });

    /**
     * Fetch user stats
     * Tests: Async function with tainted user.id from composable
     */
    async function fetchStats() {
      if (!user.value) return;

      try {
        // TAINT FLOW: user.value.id (from localStorage token) -> axios API call
        const response = await axios.get(`/api/users/${user.value.id}/stats`);
        stats.value = response.data;
      } catch (err) {
        console.error('Failed to fetch stats:', err);
      }
    }

    /**
     * Fetch notifications with filter
     * Tests: Multi-source taint (user.id + notificationFilter)
     */
    async function fetchNotifications() {
      if (!user.value) return;

      try {
        const params = new URLSearchParams();

        // MULTI-SOURCE TAINT: user.id (from token) + notificationFilter (user input)
        if (notificationFilter.value) {
          params.append('filter', notificationFilter.value);
        }

        // TAINT FLOW: user.value.id + params -> axios API call
        const response = await axios.get(
          `/api/users/${user.value.id}/notifications?${params.toString()}`
        );
        notifications.value = response.data;
      } catch (err) {
        console.error('Failed to fetch notifications:', err);
      }
    }

    /**
     * Refresh notifications (called by button)
     * Tests: Manual refresh triggering API call
     */
    async function refreshNotifications() {
      await fetchNotifications();
    }

    /**
     * Mark notification as read
     * Tests: Event handler with tainted notification ID
     */
    async function markAsRead(notificationId) {
      try {
        // TAINT FLOW: user.value.id + notificationId -> axios PUT
        await axios.put(
          `/api/users/${user.value.id}/notifications/${notificationId}`,
          { read: true }
        );

        // Update local state
        const notification = notifications.value.find(n => n.id === notificationId);
        if (notification) {
          notification.read = true;
        }
      } catch (err) {
        console.error('Failed to mark as read:', err);
      }
    }

    /**
     * Format date
     * Tests: Pure function for computed values
     */
    function formatDate(dateString) {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }

    /**
     * Watch: user (from composable)
     * Tests: Watcher on composable ref triggering API calls
     */
    watch(user, (newUser) => {
      if (newUser) {
        // TAINT FLOW: user change -> fetch stats and notifications
        fetchStats();
        fetchNotifications();
      }
    });

    /**
     * Watch: notificationFilter
     * Tests: Watcher on tainted v-model ref
     */
    watch(notificationFilter, () => {
      // TAINT FLOW: notificationFilter change -> fetchNotifications
      fetchNotifications();
    });

    /**
     * Watch: props.filter
     * Tests: Watcher on tainted prop
     */
    watch(() => props.filter, (newFilter) => {
      notificationFilter.value = newFilter;
      // This will trigger the notificationFilter watcher above
    });

    /**
     * Lifecycle: onMounted
     * Tests: Setup auto-refresh interval
     */
    onMounted(() => {
      if (user.value) {
        fetchStats();
        fetchNotifications();
      }

      // Auto-refresh every 30 seconds
      refreshInterval = setInterval(() => {
        if (user.value) {
          fetchNotifications();
        }
      }, 30000);
    });

    /**
     * Lifecycle: onUnmounted
     * Tests: Cleanup interval
     */
    onUnmounted(() => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    });

    // Expose to template
    return {
      user,
      isAuthenticated,
      isAdmin,
      stats,
      notifications,
      notificationFilter,
      unreadCount,
      filteredNotifications,
      refreshNotifications,
      markAsRead,
      formatDate,
      logout
    };
  }
};
</script>

<style scoped>
.dashboard {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin: 30px 0;
}

.stat-card {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
  text-align: center;
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  color: #007bff;
  margin: 10px 0 0 0;
}

.notifications-section {
  margin-top: 40px;
}

.filters {
  display: flex;
  gap: 10px;
  margin: 20px 0;
}

.filters select,
.filters button {
  padding: 8px 16px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.notification-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notification-card {
  padding: 15px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.notification-card.unread {
  background: #e3f2fd;
  border-color: #007bff;
}

.notification-card:hover {
  background: #f5f5f5;
}

.timestamp {
  font-size: 0.875rem;
  color: #666;
}

.login-prompt {
  padding: 40px;
  text-align: center;
}
</style>
