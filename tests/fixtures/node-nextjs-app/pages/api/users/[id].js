import {
  getUserById,
  getUserProfile,
  logActivity,
} from "../../../lib/database";

function requireAuth(handler) {
  return async (req, res) => {
    const token = req.headers.authorization?.replace("Bearer ", "");

    if (!token) {
      return res.status(401).json({ error: "Authentication required" });
    }

    try {
      const decoded = verifyToken(token);
      req.user = decoded;
      return handler(req, res);
    } catch (err) {
      return res.status(401).json({ error: "Invalid token" });
    }
  };
}

async function getUser(req, res) {
  const { id } = req.query;

  if (!id || isNaN(id)) {
    return res.status(400).json({ error: "Invalid user ID" });
  }

  try {
    const user = await getUserById(parseInt(id));

    if (!user) {
      return res.status(404).json({ error: "User not found" });
    }

    const profile = await getUserProfile(parseInt(id));

    return res.status(200).json({
      user,
      stats: {
        orderCount: profile.order_count,
        totalSpent: profile.total_spent,
        uniqueProducts: profile.unique_products,
      },
    });
  } catch (err) {
    console.error("Error fetching user:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
}

async function updateUser(req, res) {
  const { id } = req.query;
  const { username, email, bio } = req.body;

  if (!id || isNaN(id)) {
    return res.status(400).json({ error: "Invalid user ID" });
  }

  if (req.user.id !== parseInt(id) && req.user.role !== "admin") {
    return res.status(403).json({ error: "Forbidden" });
  }

  try {
    const { pool } = require("../../../lib/database");

    const query = `
      UPDATE users
      SET username = $1, email = $2, bio = $3, updated_at = NOW()
      WHERE id = $4
      RETURNING id, username, email, bio, updated_at
    `;

    const result = await pool.query(query, [
      username,
      email,
      bio,
      parseInt(id),
    ]);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: "User not found" });
    }

    await logActivity(
      parseInt(id),
      "update_profile",
      `Updated username: ${username}`,
    );

    return res.status(200).json({ user: result.rows[0] });
  } catch (err) {
    console.error("Error updating user:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
}

export default requireAuth(async function handler(req, res) {
  switch (req.method) {
    case "GET":
      return getUser(req, res);
    case "PUT":
      return updateUser(req, res);
    default:
      return res.status(405).json({ error: "Method not allowed" });
  }
});

function verifyToken(token) {
  try {
    const payload = JSON.parse(
      Buffer.from(token.split(".")[1], "base64").toString(),
    );
    return payload;
  } catch (err) {
    throw new Error("Invalid token");
  }
}
