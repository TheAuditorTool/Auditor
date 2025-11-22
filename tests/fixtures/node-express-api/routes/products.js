/**
 * Products API routes
 *
 * Tests api_endpoints and api_endpoint_controls extraction.
 * Routes use middleware chains: requireAuth → requireRole → handler
 */

const express = require('express');
const { requireAuth, requireRole, requirePermission, rateLimit } = require('../middleware/auth');
const database = require('../services/database');

const router = express.Router();

/**
 * GET /api/products
 *
 * Tests:
 * - api_endpoints extraction
 * - api_endpoint_controls with single middleware (requireAuth)
 * - Rate limiting control
 */
router.get('/api/products', requireAuth, rateLimit(100), async (req, res) => {
  try {
    // TAINT SOURCE: Query parameter from user
    const search = req.query.search;

    let products;
    if (search) {
      // TAINT FLOW: search → database query
      const query = `SELECT * FROM products WHERE name LIKE '%${search}%'`;
      const result = await database.pool.query(query);
      products = result.rows;
    } else {
      const result = await database.pool.query('SELECT * FROM products');
      products = result.rows;
    }

    res.json({ products });
  } catch (err) {
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * POST /api/products
 *
 * Tests:
 * - api_endpoints extraction
 * - api_endpoint_controls with MULTIPLE middleware (requireAuth + requireRole)
 * - Taint flow from req.body → SQL INSERT
 */
router.post('/api/products', requireAuth, requireRole('admin'), async (req, res) => {
  try {
    // TAINT SOURCE: Request body from user
    const { name, description, price, category } = req.body;

    // TAINT FLOW: body fields → database INSERT
    const query = `
      INSERT INTO products (name, description, price, category, created_at)
      VALUES ($1, $2, $3, $4, NOW())
      RETURNING *
    `;

    const result = await database.pool.query(query, [name, description, price, category]);
    const product = result.rows[0];

    // Log admin action
    await database.logUserActivity(req.user.id, 'create_product', `Created product: ${name}`);

    res.status(201).json({ product });
  } catch (err) {
    res.status(500).json({ error: 'Failed to create product' });
  }
});

/**
 * PUT /api/products/:id
 *
 * Tests:
 * - api_endpoints extraction with URL parameters
 * - api_endpoint_controls with permission check
 * - Taint flow from req.params → SQL UPDATE
 */
router.put('/api/products/:id', requireAuth, requirePermission('products:update'), async (req, res) => {
  try {
    // TAINT SOURCE: URL parameter
    const productId = req.params.id;

    // TAINT SOURCE: Request body
    const { name, description, price } = req.body;

    // MULTI-SOURCE TAINT: productId + body fields → database UPDATE
    const query = `
      UPDATE products
      SET name = $1, description = $2, price = $3, updated_at = NOW()
      WHERE id = $4
      RETURNING *
    `;

    const result = await database.pool.query(query, [name, description, price, productId]);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Product not found' });
    }

    const product = result.rows[0];
    res.json({ product });
  } catch (err) {
    res.status(500).json({ error: 'Failed to update product' });
  }
});

/**
 * DELETE /api/products/:id
 *
 * Tests:
 * - api_endpoints extraction for DELETE method
 * - api_endpoint_controls with admin role
 * - Taint flow from req.params → SQL DELETE
 */
router.delete('/api/products/:id', requireAuth, requireRole('admin'), async (req, res) => {
  try {
    // TAINT SOURCE: URL parameter
    const productId = req.params.id;

    // TAINT FLOW: productId → database DELETE
    const query = 'DELETE FROM products WHERE id = $1 RETURNING id';

    const result = await database.pool.query(query, [productId]);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Product not found' });
    }

    // Log admin action
    await database.logUserActivity(req.user.id, 'delete_product', `Deleted product ID: ${productId}`);

    res.json({ message: 'Product deleted successfully' });
  } catch (err) {
    res.status(500).json({ error: 'Failed to delete product' });
  }
});

/**
 * GET /api/products/search
 *
 * Tests:
 * - VULNERABLE: SQL injection vulnerability
 * - Taint flow from req.query → vulnerable SQL concatenation
 * - No authentication (security issue)
 */
router.get('/api/products/search', async (req, res) => {
  try {
    // TAINT SOURCE: Query parameter (no sanitization)
    const searchTerm = req.query.term;

    // VULNERABLE: Direct string concatenation (SQL injection)
    // TAINT FLOW: searchTerm → query string
    const vulnerableQuery = `SELECT * FROM products WHERE name LIKE '%${searchTerm}%' OR description LIKE '%${searchTerm}%'`;

    const result = await database.pool.query(vulnerableQuery);

    res.json({ products: result.rows });
  } catch (err) {
    res.status(500).json({ error: 'Search failed' });
  }
});

module.exports = router;
