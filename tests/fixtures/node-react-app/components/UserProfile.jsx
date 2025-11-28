import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";

function UserProfile({ userId, showDetails }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [orders, setOrders] = useState([]);

  useEffect(() => {
    async function fetchUser() {
      setLoading(true);
      setError(null);

      try {
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
  }, [userId]);

  useEffect(() => {
    async function fetchOrders() {
      if (!showDetails) return;

      try {
        const response = await axios.get(`/api/users/${userId}/orders`);
        setOrders(response.data);
      } catch (err) {
        console.error("Failed to fetch orders:", err);
      }
    }

    if (userId && showDetails) {
      fetchOrders();
    }
  }, [userId, showDetails]);

  const handleUpdate = useCallback(
    async (updates) => {
      try {
        await axios.put(`/api/users/${userId}`, updates);

        const response = await axios.get(`/api/users/${userId}`);
        setUser(response.data);
      } catch (err) {
        setError(err.message);
      }
    },
    [userId],
  );

  const fullName = useMemo(() => {
    if (!user) return "";
    return `${user.firstName} ${user.lastName}`;
  }, [user]);

  const orderStats = useMemo(() => {
    if (!orders.length) {
      return { total: 0, count: 0 };
    }

    return {
      total: orders.reduce((sum, order) => sum + order.amount, 0),
      count: orders.length,
    };
  }, [orders]);

  if (loading) {
    return <div>Loading user #{userId}...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  if (!user) {
    return <div>User not found</div>;
  }

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
