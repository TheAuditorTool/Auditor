import { useState, useEffect, useCallback, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../contexts/AuthContext";

function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadUser = async () => {
      try {
        const token = localStorage.getItem("authToken");

        if (token) {
          axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;

          const response = await axios.get("/api/auth/me");
          setUser(response.data);
        }
      } catch (err) {
        console.error("Failed to load user:", err);
        localStorage.removeItem("authToken");
      } finally {
        setLoading(false);
      }
    };

    loadUser();
  }, []);

  const login = useCallback(async (email, password) => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post("/api/auth/login", {
        email,
        password,
      });

      const { token, user } = response.data;

      localStorage.setItem("authToken", token);

      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;

      setUser(user);
      return { success: true };
    } catch (err) {
      const message = err.response?.data?.error || "Login failed";
      setError(message);
      return { success: false, error: message };
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      if (user) {
        await axios.post("/api/auth/logout");
      }

      localStorage.removeItem("authToken");
      delete axios.defaults.headers.common["Authorization"];
      setUser(null);
    } catch (err) {
      console.error("Logout failed:", err);
    }
  }, [user]);

  return {
    user,
    loading,
    error,
    login,
    logout,
    isAuthenticated: !!user,
  };
}

export default useAuth;
