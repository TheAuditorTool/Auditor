import { ref, computed, onMounted } from "vue";
import axios from "axios";

export function useAuth() {
  const user = ref(null);
  const loading = ref(true);
  const error = ref(null);
  const token = ref(null);

  const isAuthenticated = computed(() => !!user.value);

  const isAdmin = computed(() => user.value?.role === "admin");

  async function loadUser() {
    try {
      const storedToken = localStorage.getItem("authToken");

      if (storedToken) {
        token.value = storedToken;

        axios.defaults.headers.common["Authorization"] =
          `Bearer ${storedToken}`;

        const response = await axios.get("/api/auth/me");
        user.value = response.data;
      }
    } catch (err) {
      error.value = err.message;
      localStorage.removeItem("authToken");
      delete axios.defaults.headers.common["Authorization"];
    } finally {
      loading.value = false;
    }
  }

  async function login(email, password) {
    loading.value = true;
    error.value = null;

    try {
      const response = await axios.post("/api/auth/login", {
        email,
        password,
      });

      const { token: authToken, user: userData } = response.data;

      localStorage.setItem("authToken", authToken);
      token.value = authToken;

      axios.defaults.headers.common["Authorization"] = `Bearer ${authToken}`;

      user.value = userData;
      return { success: true };
    } catch (err) {
      error.value = err.response?.data?.error || "Login failed";
      return { success: false, error: error.value };
    } finally {
      loading.value = false;
    }
  }

  async function logout() {
    try {
      if (user.value) {
        await axios.post("/api/auth/logout");
      }

      localStorage.removeItem("authToken");
      delete axios.defaults.headers.common["Authorization"];

      user.value = null;
      token.value = null;
    } catch (err) {
      console.error("Logout failed:", err);
    }
  }

  async function refreshUser() {
    if (!token.value) return;

    try {
      const response = await axios.get("/api/auth/me");
      user.value = response.data;
    } catch (err) {
      console.error("Failed to refresh user:", err);
    }
  }

  onMounted(() => {
    loadUser();
  });

  return {
    user,
    loading,
    error,
    token,
    isAuthenticated,
    isAdmin,
    login,
    logout,
    refreshUser,
  };
}
