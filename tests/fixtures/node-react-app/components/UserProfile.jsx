/**
 * UserProfile component
 *
 * Tests:
 * - react_component_hooks extraction (useState, useEffect, useCallback, useMemo)
 * - react_hook_dependencies extraction
 * - Tainted dependencies in useEffect
 * - Hook composition patterns
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';

/**
 * UserProfile component with comprehensive hook usage
 *
 * Tests react_component_hooks and react_hook_dependencies junction tables.
 *
 * @param {Object} props
 * @param {string|number} props.userId - User ID (TAINT SOURCE from props)
 * @param {boolean} props.showDetails - Whether to show detailed info
 */
function UserProfile({ userId, showDetails }) {
  // STATE HOOKS: Tests useState extraction
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [orders, setOrders] = useState([]);

  /**
   * TAINTED DEPENDENCY: userId from props (external input)
   *
   * Tests:
   * - react_hook_dependencies extraction (userId in dependency array)
   * - Taint flow: userId (prop) → API call (sink)
   * - useEffect with async function inside
   */
  useEffect(() => {
    async function fetchUser() {
      setLoading(true);
      setError(null);

      try {
        // TAINT SINK: API call with tainted userId
        // userId comes from props (potentially controlled by user/URL)
        const response = await axios.get(`/api/users/${userId}`);
        setUser(response.data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    if (userId) {
      fetchUser();
    }
  }, [userId]); // ← DEPENDENCY on tainted variable

  /**
   * TAINTED DEPENDENCY: userId + showDetails
   *
   * Tests:
   * - Multiple dependencies in array
   * - Conditional execution based on tainted prop
   */
  useEffect(() => {
    async function fetchOrders() {
      if (!showDetails) return;

      try {
        // TAINT SINK: API call with tainted userId
        const response = await axios.get(`/api/users/${userId}/orders`);
        setOrders(response.data);
      } catch (err) {
        console.error('Failed to fetch orders:', err);
      }
    }

    if (userId && showDetails) {
      fetchOrders();
    }
  }, [userId, showDetails]); // ← MULTIPLE tainted dependencies

  /**
   * useCallback with tainted dependency
   *
   * Tests:
   * - useCallback extraction
   * - Callback dependencies on tainted variables
   * - Proper memoization pattern
   */
  const handleUpdate = useCallback(async (updates) => {
    try {
      // TAINT SINK: API call with tainted userId
      await axios.put(`/api/users/${userId}`, updates);

      // Refresh user data after update
      const response = await axios.get(`/api/users/${userId}`);
      setUser(response.data);
    } catch (err) {
      setError(err.message);
    }
  }, [userId]); // ← DEPENDENCY on tainted userId

  /**
   * useMemo with tainted dependency
   *
   * Tests:
   * - useMemo extraction
   * - Computed values depending on tainted data
   */
  const fullName = useMemo(() => {
    if (!user) return '';
    return `${user.firstName} ${user.lastName}`;
  }, [user]); // ← DEPENDENCY on user (indirectly tainted via userId)

  /**
   * useMemo for expensive computation
   *
   * Tests:
   * - useMemo with array dependency
   * - Aggregation on potentially tainted data
   */
  const orderStats = useMemo(() => {
    if (!orders.length) {
      return { total: 0, count: 0 };
    }

    return {
      total: orders.reduce((sum, order) => sum + order.amount, 0),
      count: orders.length
    };
  }, [orders]); // ← DEPENDENCY on orders (fetched using tainted userId)

  // Loading state
  if (loading) {
    return <div>Loading user #{userId}...</div>;
  }

  // Error state
  if (error) {
    return <div>Error: {error}</div>;
  }

  // No user found
  if (!user) {
    return <div>User not found</div>;
  }

  // Render user profile
  return (
    <div className="user-profile">
      <h2>{fullName}</h2>
      <p>Email: {user.email}</p>
      <p>Username: {user.username}</p>

      {showDetails && (
        <div className="user-details">
          <h3>Orders ({orderStats.count})</h3>
          <p>Total Spent: ${orderStats.total.toFixed(2)}</p>

          <button onClick={() => handleUpdate({ lastSeen: new Date() })}>
            Update Last Seen
          </button>
        </div>
      )}
    </div>
  );
}

export default UserProfile;
