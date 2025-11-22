<template>
  <div v-if="loading" class="loading">Loading...</div>
  <div v-else-if="error" class="error">{{ error }}</div>
  <div v-else class="user-profile">
    <h2>{{ fullName }}</h2>
    <p>Email: {{ user.email }}</p>
    <p>Role: {{ user.role }}</p>

    <div v-if="showDetails" class="user-details">
      <h3>Orders ({{ orderStats.count }})</h3>
      <p>Total Spent: ${{ orderStats.total }}</p>

      <div v-for="order in orders" :key="order.id" class="order-card">
        <span>{{ order.date }}</span>
        <span>${{ order.amount }}</span>
      </div>
    </div>

    <button @click="handleUpdate">Update Last Seen</button>
  </div>
</template>

<script>
/**
 * UserProfile component with Vue 3 Composition API
 *
 * Tests:
 * - Vue component extraction
 * - ref, computed, watch, watchEffect
 * - onMounted, onUnmounted lifecycle hooks
 * - Tainted props (userId, showDetails) in reactive dependencies
 * - Computed properties depending on tainted data
 * - Taint flows: props -> ref -> axios API calls
 */

import { ref, computed, watch, watchEffect, onMounted, onUnmounted } from 'vue';
import axios from 'axios';

export default {
  name: 'UserProfile',

  props: {
    userId: {
      type: Number,
      required: true
      // TAINT SOURCE: userId from parent component (potentially from URL)
    },
    showDetails: {
      type: Boolean,
      default: false
      // TAINT SOURCE: showDetails from parent component
    }
  },

  setup(props) {
    // Reactive refs
    const user = ref(null);
    const loading = ref(true);
    const error = ref(null);
    const orders = ref([]);
    const lastSeen = ref(new Date());

    /**
     * Computed property: fullName
     * Tests: Computed properties depending on reactive data
     */
    const fullName = computed(() => {
      if (!user.value) return '';
      return `${user.value.firstName} ${user.value.lastName}`;
    });

    /**
     * Computed property: orderStats
     * Tests: Computed properties with reduce operations
     */
    const orderStats = computed(() => {
      if (!orders.value.length) return { total: 0, count: 0 };

      return {
        total: orders.value.reduce((sum, order) => sum + order.amount, 0),
        count: orders.value.length
      };
    });

    /**
     * Fetch user data
     * Tests: Async function with tainted userId prop
     */
    async function fetchUser() {
      loading.value = true;
      error.value = null;

      try {
        // TAINT FLOW: props.userId -> axios API call
        const response = await axios.get(`/api/users/${props.userId}`);
        user.value = response.data;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    }

    /**
     * Fetch user orders
     * Tests: Conditional fetch based on tainted showDetails prop
     */
    async function fetchOrders() {
      if (!props.showDetails) return;

      try {
        // TAINT FLOW: props.userId -> axios API call
        const response = await axios.get(`/api/users/${props.userId}/orders`);
        orders.value = response.data;
      } catch (err) {
        console.error('Failed to fetch orders:', err);
      }
    }

    /**
     * Update user last seen
     * Tests: Function with tainted userId in closure
     */
    async function handleUpdate() {
      try {
        // TAINT FLOW: props.userId -> axios API call
        await axios.put(`/api/users/${props.userId}`, {
          lastSeen: new Date().toISOString()
        });

        // Refetch user data
        await fetchUser();
      } catch (err) {
        console.error('Failed to update user:', err);
      }
    }

    /**
     * Watch: userId prop
     * Tests: Watcher on tainted prop triggering API calls
     */
    watch(() => props.userId, (newUserId, oldUserId) => {
      if (newUserId !== oldUserId) {
        // TAINT FLOW: props.userId change -> fetchUser -> axios API call
        fetchUser();
      }
    });

    /**
     * Watch: showDetails prop
     * Tests: Watcher on tainted prop with conditional logic
     */
    watch(() => props.showDetails, (newShowDetails) => {
      if (newShowDetails) {
        // TAINT FLOW: props.userId -> fetchOrders -> axios API call
        fetchOrders();
      }
    });

    /**
     * watchEffect: Auto-track dependencies
     * Tests: watchEffect with tainted dependencies
     */
    watchEffect(() => {
      // This will re-run whenever props.userId or props.showDetails changes
      if (props.userId && props.showDetails) {
        lastSeen.value = new Date();
      }
    });

    /**
     * Lifecycle: onMounted
     * Tests: Lifecycle hook with tainted data
     */
    onMounted(() => {
      // TAINT FLOW: props.userId -> fetchUser on mount
      fetchUser();

      if (props.showDetails) {
        fetchOrders();
      }
    });

    /**
     * Lifecycle: onUnmounted
     * Tests: Cleanup lifecycle hook
     */
    onUnmounted(() => {
      // Cleanup
      user.value = null;
      orders.value = [];
    });

    // Expose to template
    return {
      user,
      loading,
      error,
      orders,
      fullName,
      orderStats,
      handleUpdate
    };
  }
};
</script>

<style scoped>
.user-profile {
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 8px;
}

.loading, .error {
  padding: 20px;
  text-align: center;
}

.order-card {
  display: flex;
  justify-content: space-between;
  padding: 10px;
  margin: 5px 0;
  background: #f5f5f5;
  border-radius: 4px;
}
</style>
