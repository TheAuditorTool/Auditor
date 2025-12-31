/**
 * API client - HOP 19: Frontend HTTP calls.
 *
 * Makes HTTP requests to the backend, carrying tainted data.
 */

const API_BASE = '/api';

/**
 * Search users.
 *
 * HOP 19: Sends TAINTED query to backend.
 *
 * @param query - TAINTED search query from user input
 */
async function searchUsers(query: string): Promise<any> {
  // TAINTED query sent to backend
  const response = await fetch(`${API_BASE}/users/search?q=${encodeURIComponent(query)}`);
  return response.json();
}

/**
 * Generate report.
 *
 * HOP 19: Sends TAINTED title to backend.
 *
 * @param title - TAINTED title from user input
 */
async function generateReport(title: string): Promise<any> {
  // TAINTED title sent to backend
  const response = await fetch(`${API_BASE}/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, data: {} }),
  });
  return response.json();
}

/**
 * Update user settings.
 *
 * HOP 19: Sends TAINTED settings to backend.
 *
 * @param userId - User ID
 * @param settings - TAINTED settings object (Prototype Pollution)
 */
async function updateSettings(userId: string, settings: any): Promise<any> {
  // TAINTED settings sent to backend
  const response = await fetch(`${API_BASE}/users/${userId}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings }),
  });
  return response.json();
}

/**
 * Filter users.
 *
 * HOP 19: Sends TAINTED filter to backend.
 *
 * @param filter - TAINTED filter object (NoSQL Injection)
 */
async function filterUsers(filter: any): Promise<any> {
  // TAINTED filter sent to backend
  const response = await fetch(`${API_BASE}/users/filter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filter }),
  });
  return response.json();
}

export const apiClient = {
  searchUsers,
  generateReport,
  updateSettings,
  filterUsers,
};
