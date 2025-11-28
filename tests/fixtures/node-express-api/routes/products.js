const express = require("express");
const {
  requireAuth,
  requireRole,
  requirePermission,
  rateLimit,
} = require("../middleware/auth");
const database = require("../services/database");

const router = express.Router();

router.get("/api/products", requireAuth, rateLimit(100), async (req, res) => {
  try {
    const search = req.query.search;

    let products;
    if (search) {
      const query = `SELECT * FROM products WHERE name LIKE '%${search}%'`;
      const result = await database.pool.query(query);
      products = result.rows;
    } else {
      const result = await database.pool.query("SELECT * FROM products");
      products = result.rows;
    }

    res.json({ products });
  } catch (err) {
    res.status(500).json({ error: "Internal server error" });
  }
});

router.post(
  "/api/products",
  requireAuth,
  requireRole("admin"),
  async (req, res) => {
    try {
      const { name, description, price, category } = req.body;

      const query = `
      INSERT INTO products (name, description, price, category, created_at)
      VALUES ($1, $2, $3, $4, NOW())
      RETURNING *
    `;

      const result = await database.pool.query(query, [
        name,
        description,
        price,
        category,
      ]);
      const product = result.rows[0];

      await database.logUserActivity(
        req.user.id,
        "create_product",
        `Created product: ${name}`,
      );

      res.status(201).json({ product });
    } catch (err) {
      res.status(500).json({ error: "Failed to create product" });
    }
  },
);

router.put(
  "/api/products/:id",
  requireAuth,
  requirePermission("products:update"),
  async (req, res) => {
    try {
      const productId = req.params.id;

      const { name, description, price } = req.body;

      const query = `
      UPDATE products
      SET name = $1, description = $2, price = $3, updated_at = NOW()
      WHERE id = $4
      RETURNING *
    `;

      const result = await database.pool.query(query, [
        name,
        description,
        price,
        productId,
      ]);

      if (result.rows.length === 0) {
        return res.status(404).json({ error: "Product not found" });
      }

      const product = result.rows[0];
      res.json({ product });
    } catch (err) {
      res.status(500).json({ error: "Failed to update product" });
    }
  },
);

router.delete(
  "/api/products/:id",
  requireAuth,
  requireRole("admin"),
  async (req, res) => {
    try {
      const productId = req.params.id;

      const query = "DELETE FROM products WHERE id = $1 RETURNING id";

      const result = await database.pool.query(query, [productId]);

      if (result.rows.length === 0) {
        return res.status(404).json({ error: "Product not found" });
      }

      await database.logUserActivity(
        req.user.id,
        "delete_product",
        `Deleted product ID: ${productId}`,
      );

      res.json({ message: "Product deleted successfully" });
    } catch (err) {
      res.status(500).json({ error: "Failed to delete product" });
    }
  },
);

router.get("/api/products/search", async (req, res) => {
  try {
    const searchTerm = req.query.term;

    const vulnerableQuery = `SELECT * FROM products WHERE name LIKE '%${searchTerm}%' OR description LIKE '%${searchTerm}%'`;

    const result = await database.pool.query(vulnerableQuery);

    res.json({ products: result.rows });
  } catch (err) {
    res.status(500).json({ error: "Search failed" });
  }
});

module.exports = router;
