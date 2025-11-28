import { useState, useEffect, useCallback, useMemo, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../contexts/AuthContext";
import useAuth from "../hooks/useAuth";

function Dashboard({ filter }) {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    const fetchStats = async () => {
      if (!user) return;

      try {
        const response = await axios.get(`/api/users/${user.id}/stats`);
        setStats(response.data);
      } catch (err) {
        console.error("Failed to fetch stats:", err);
      }
    };

    fetchStats();
  }, [user]);

  const refreshNotifications = useCallback(async () => {
    if (!user) return;

    try {
      const params = filter ? `?filter=${filter}` : "";
      const response = await axios.get(
        `/api/users/${user.id}/notifications${params}`,
      );
      setNotifications(response.data);
    } catch (err) {
      console.error("Failed to fetch notifications:", err);
    }
  }, [user, filter]);

  useEffect(() => {
    refreshNotifications();
  }, [refreshNotifications]);

  const unreadCount = useMemo(() => {
    return notifications.filter((n) => !n.read).length;
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
        {notifications.map((notif) => (
          <div key={notif.id} className={notif.read ? "read" : "unread"}>
            {notif.message}
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dashboard;
