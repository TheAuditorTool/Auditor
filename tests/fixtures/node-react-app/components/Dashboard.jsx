/**
 * Dashboard component with complex hook composition
 *
 * Tests:
 * - Multiple hook types in one component
 * - useContext extraction
 * - Hook dependencies with computed values
 */

import { useState, useEffect, useCallback, useMemo, useContext } from 'react';
import axios from 'axios';
import { AuthContext } from '../contexts/AuthContext';
import useAuth from '../hooks/useAuth';

/**
 * Dashboard component
 *
 * Tests complex hook composition and context usage.
 *
 * @param {Object} props
 * @param {string} props.filter - Dashboard filter (TAINT SOURCE)
 */
function Dashboard({ filter }) {
  const { user } = useAuth(); // Custom hook
  const [stats, setStats] = useState(null);
  const [notifications, setNotifications] = useState([]);

  /**
   * Fetch dashboard stats
   * TAINTED: Depends on user.id (from auth token, localStorage)
   */
  useEffect(() => {
    const fetchStats = async () => {
      if (!user) return;

      try {
        // TAINT FLOW: user.id (from localStorage token) → API
        const response = await axios.get(`/api/users/${user.id}/stats`);
        setStats(response.data);
      } catch (err) {
        console.error('Failed to fetch stats:', err);
      }
    };

    fetchStats();
  }, [user]);

  /**
   * Fetch notifications with filter
   * TAINTED: Depends on user.id + filter prop
   */
  const refreshNotifications = useCallback(async () => {
    if (!user) return;

    try {
      // TAINT FLOW: user.id + filter → API
      const params = filter ? `?filter=${filter}` : '';
      const response = await axios.get(`/api/users/${user.id}/notifications${params}`);
      setNotifications(response.data);
    } catch (err) {
      console.error('Failed to fetch notifications:', err);
    }
  }, [user, filter]); // Multiple tainted dependencies

  // Trigger notification fetch
  useEffect(() => {
    refreshNotifications();
  }, [refreshNotifications]);

  // Computed notification count
  const unreadCount = useMemo(() => {
    return notifications.filter(n => !n.read).length;
  }, [notifications]);

  if (!user) {
    return <div>Please log in</div>;
  }

  return (
    <div className="dashboard">
      <h1>Welcome, {user.username}</h1>

      {stats && (
        <div className="stats">
          <div>Orders: {stats.orderCount}</div>
          <div>Total Spent: ${stats.totalSpent}</div>
        </div>
      )}

      <div className="notifications">
        <h2>Notifications ({unreadCount} unread)</h2>
        {notifications.map(notif => (
          <div key={notif.id} className={notif.read ? 'read' : 'unread'}>
            {notif.message}
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dashboard;
