/**
 * Database service with raw SQL queries
 *
 * Tests sql_queries and sql_query_tables extraction.
 * All queries use raw SQL (not ORM) to populate sql_queries table.
 */

const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || 'app_db',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'password'
});

/**
 * Get user by email using raw SQL
 *
 * Tests:
 * - Raw SQL query touching 'users' table
 * - TAINT FLOW: email parameter (potential user input)
 *
 * @param {string} email - User email (potential TAINT SOURCE)
 * @returns {Promise<Object|null>} User object or null
 */
async function getUserByEmail(email) {
  // Query touches 'users' table
  const query = 'SELECT id, username, email, password_hash, role_id, created_at FROM users WHERE email = $1';

  const result = await pool.query(query, [email]);

  return result.rows[0] || null;
}

/**
 * Get admin users using raw SQL with JOIN
 *
 * Tests:
 * - Raw SQL with JOIN touching 'users' AND 'roles' tables
 * - Query filtering by role
 *
 * @returns {Promise<Array>} List of admin users
 */
async function getAdminUsers() {
  // Query touches 'users' AND 'roles' tables
  const query = `
    SELECT u.id, u.username, u.email, r.name AS role_name
    FROM users u
    JOIN roles r ON u.role_id = r.id
    WHERE r.name = 'admin'
  `;

  const result = await pool.query(query);

  return result.rows;
}

/**
 * Search users with dynamic query building
 *
 * Tests:
 * - MULTI-SOURCE ASSIGNMENT: query built from multiple variables
 * - TAINT FLOW: searchTerm and roleFilter from user input
 * - Dynamic SQL construction (potential SQL injection if not parameterized)
 *
 * @param {string} searchTerm - Search term (TAINT SOURCE - user input)
 * @param {string|null} roleFilter - Optional role filter (TAINT SOURCE - user input)
 * @returns {Promise<Array>} List of matching users
 */
async function searchUsers(searchTerm, roleFilter = null) {
  // MULTI-SOURCE ASSIGNMENT: Building query from multiple sources
  let baseQuery = `
    SELECT u.id, u.username, u.email, r.name AS role_name
    FROM users u
    LEFT JOIN roles r ON u.role_id = r.id
  `;

  const conditions = [];
  const params = [];

  // Add search condition
  if (searchTerm) {
    conditions.push('(u.username LIKE $' + (params.length + 1) + ' OR u.email LIKE $' + (params.length + 2) + ')');
    const searchPattern = `%${searchTerm}%`;
    params.push(searchPattern, searchPattern);
  }

  // Add role filter
  if (roleFilter) {
    conditions.push('r.name = $' + (params.length + 1));
    params.push(roleFilter);
  }

  // MULTI-SOURCE: Combine all parts into final query
  let query = baseQuery;
  if (conditions.length > 0) {
    query += ' WHERE ' + conditions.join(' AND ');
  }

  // Execute query (touches 'users' and 'roles' tables)
  const result = await pool.query(query, params);

  return result.rows;
}

/**
 * Get user order statistics using raw SQL with aggregation
 *
 * Tests:
 * - Raw SQL with JOIN across multiple tables
 * - Touches 'users', 'orders', 'order_items' tables
 * - Aggregation queries
 *
 * @param {number} userId - User ID (TAINT SOURCE)
 * @returns {Promise<Object>} Stats object
 */
async function getUserOrderStats(userId) {
  // Query touches 'orders' and 'order_items' tables with JOIN
  const query = `
    SELECT
      COUNT(DISTINCT o.id) AS order_count,
      SUM(o.total_amount) AS total_spent,
      COUNT(oi.id) AS items_purchased
    FROM orders o
    LEFT JOIN order_items oi ON o.id = oi.order_id
    WHERE o.user_id = $1
  `;

  const result = await pool.query(query, [userId]);
  const row = result.rows[0];

  return {
    orderCount: parseInt(row.order_count) || 0,
    totalSpent: parseFloat(row.total_spent) || 0.0,
    itemsPurchased: parseInt(row.items_purchased) || 0
  };
}

/**
 * Log user activity to database
 *
 * Tests:
 * - INSERT query (sql_queries table)
 * - Query touches 'activity_log' table (sql_query_tables)
 * - TAINT SINK: Logging user actions
 *
 * @param {number} userId - User ID
 * @param {string} action - Action type (e.g., 'login', 'create_order')
 * @param {string} details - Action details (potential TAINT SOURCE)
 */
async function logUserActivity(userId, action, details) {
  // INSERT query touching 'activity_log' table
  const query = `
    INSERT INTO activity_log (user_id, action, details, created_at)
    VALUES ($1, $2, $3, NOW())
  `;

  await pool.query(query, [userId, action, details]);
}

/**
 * VULNERABLE: SQL Injection example for taint detection
 *
 * Tests:
 * - SQL injection vulnerability (no parameterization)
 * - TAINT FLOW: user input directly concatenated into query
 *
 * @param {string} username - Username (TAINT SOURCE - user input)
 * @returns {Promise<Object|null>} User object or null
 */
async function vulnerableSearch(username) {
  // VULNERABLE: Direct string concatenation (SQL injection)
  // TAINT FLOW: username → query string
  const query = `SELECT * FROM users WHERE username = '${username}'`;

  const result = await pool.query(query);

  return result.rows[0] || null;
}

module.exports = {
  getUserByEmail,
  getAdminUsers,
  searchUsers,
  getUserOrderStats,
  logUserActivity,
  vulnerableSearch
};
