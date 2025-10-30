/**
 * Next.js API route: GET/PUT /api/users/[id]
 *
 * Tests:
 * - Next.js dynamic API route extraction
 * - api_endpoints table population (method, pattern)
 * - Taint flow from route params -> SQL queries
 * - Authentication middleware in Next.js
 */

import { getUserById, getUserProfile, logActivity } from '../../../lib/database';

/**
 * Middleware: Check authentication
 * Tests: api_endpoint_controls extraction
 */
function requireAuth(handler) {
  return async (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');

    if (!token) {
      return res.status(401).json({ error: 'Authentication required' });
    }

    try {
      // Verify JWT token (simplified)
      const decoded = verifyToken(token);
      req.user = decoded;
      return handler(req, res);
    } catch (err) {
      return res.status(401).json({ error: 'Invalid token' });
    }
  };
}

/**
 * GET /api/users/[id]
 * Tests: Taint flow from route param -> SQL query
 */
async function getUser(req, res) {
  const { id } = req.query; // TAINT SOURCE: Dynamic route param

  if (!id || isNaN(id)) {
    return res.status(400).json({ error: 'Invalid user ID' });
  }

  try {
    // TAINT FLOW: req.query.id -> getUserById -> SQL query
    const user = await getUserById(parseInt(id));

    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    // Get profile stats
    const profile = await getUserProfile(parseInt(id));

    return res.status(200).json({
      user,
      stats: {
        orderCount: profile.order_count,
        totalSpent: profile.total_spent,
        uniqueProducts: profile.unique_products
      }
    });
  } catch (err) {
    console.error('Error fetching user:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
}

/**
 * PUT /api/users/[id]
 * Tests: Multi-source taint (route param + request body -> SQL)
 */
async function updateUser(req, res) {
  const { id } = req.query; // TAINT SOURCE 1: Route param
  const { username, email, bio } = req.body; // TAINT SOURCE 2: Request body

  if (!id || isNaN(id)) {
    return res.status(400).json({ error: 'Invalid user ID' });
  }

  // Authorization: Can only update own profile
  if (req.user.id !== parseInt(id) && req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }

  try {
    const { pool } = require('../../../lib/database');

    // MULTI-SOURCE TAINT: id (route) + body fields -> SQL UPDATE
    const query = `
      UPDATE users
      SET username = $1, email = $2, bio = $3, updated_at = NOW()
      WHERE id = $4
      RETURNING id, username, email, bio, updated_at
    `;

    const result = await pool.query(query, [username, email, bio, parseInt(id)]);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }

    // Log activity
    await logActivity(parseInt(id), 'update_profile', `Updated username: ${username}`);

    return res.status(200).json({ user: result.rows[0] });
  } catch (err) {
    console.error('Error updating user:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
}

/**
 * Main API route handler with authentication
 * Tests: api_endpoint_controls with requireAuth middleware
 */
export default requireAuth(async function handler(req, res) {
  switch (req.method) {
    case 'GET':
      return getUser(req, res);
    case 'PUT':
      return updateUser(req, res);
    default:
      return res.status(405).json({ error: 'Method not allowed' });
  }
});

/**
 * Simple JWT verification (placeholder)
 */
function verifyToken(token) {
  // In real app, use jsonwebtoken library
  // For fixture, just parse the token
  try {
    const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64').toString());
    return payload;
  } catch (err) {
    throw new Error('Invalid token');
  }
}
