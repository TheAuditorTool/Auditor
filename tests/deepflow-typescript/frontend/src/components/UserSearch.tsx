/**
 * User search component - HOP 20: Frontend taint source.
 *
 * User input from this component flows through 20 hops to reach
 * a SQL injection sink on the backend.
 */

import React, { useState } from 'react';
import { apiClient } from '../api/client';

export function UserSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  /**
   * Handle search submission.
   *
   * HOP 20: User input from useState becomes taint source.
   * Flows: useState -> fetch -> Express -> ... -> SQL sink
   *
   * VULNERABILITY: SQL Injection (20 hops from frontend to backend sink)
   */
  const handleSearch = async () => {
    setLoading(true);
    try {
      // HOP 19: API client sends tainted query to backend
      const data = await apiClient.searchUsers(query); // query is TAINTED
      setResults(data.result || []);
    } catch (error) {
      console.error('Search failed:', error);
    }
    setLoading(false);
  };

  return (
    <div className="user-search">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)} // TAINT SOURCE
        placeholder="Search users..."
      />
      <button onClick={handleSearch} disabled={loading}>
        {loading ? 'Searching...' : 'Search'}
      </button>

      <ul>
        {results.map((user, index) => (
          <li key={index}>
            {user.name} - {user.email}
          </li>
        ))}
      </ul>
    </div>
  );
}
