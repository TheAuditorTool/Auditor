const { Pool } = require("pg");

const pool = new Pool({
  host: process.env.DB_HOST || "localhost",
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || "app_db",
  user: process.env.DB_USER || "postgres",
  password: process.env.DB_PASSWORD || "password",
});

async function getUserByEmail(email) {
  const query =
    "SELECT id, username, email, password_hash, role_id, created_at FROM users WHERE email = $1";

  const result = await pool.query(query, [email]);

  return result.rows[0] || null;
}

async function getAdminUsers() {
  const query = `
    SELECT u.id, u.username, u.email, r.name AS role_name
    FROM users u
    JOIN roles r ON u.role_id = r.id
    WHERE r.name = 'admin'
  `;

  const result = await pool.query(query);

  return result.rows;
}

async function searchUsers(searchTerm, roleFilter = null) {
  let baseQuery = `
    SELECT u.id, u.username, u.email, r.name AS role_name
    FROM users u
    LEFT JOIN roles r ON u.role_id = r.id
  `;

  const conditions = [];
  const params = [];

  if (searchTerm) {
    conditions.push(
      "(u.username LIKE $" +
        (params.length + 1) +
        " OR u.email LIKE $" +
        (params.length + 2) +
        ")",
    );
    const searchPattern = `%${searchTerm}%`;
    params.push(searchPattern, searchPattern);
  }

  if (roleFilter) {
    conditions.push("r.name = $" + (params.length + 1));
    params.push(roleFilter);
  }

  let query = baseQuery;
  if (conditions.length > 0) {
    query += " WHERE " + conditions.join(" AND ");
  }

  const result = await pool.query(query, params);

  return result.rows;
}

async function getUserOrderStats(userId) {
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
    itemsPurchased: parseInt(row.items_purchased) || 0,
  };
}

async function logUserActivity(userId, action, details) {
  const query = `
    INSERT INTO activity_log (user_id, action, details, created_at)
    VALUES ($1, $2, $3, NOW())
  `;

  await pool.query(query, [userId, action, details]);
}

async function vulnerableSearch(username) {
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
  vulnerableSearch,
};
