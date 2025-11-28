const jwt = require("jsonwebtoken");

function requireAuth(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader) {
    return res.status(401).json({ error: "Missing authorization token" });
  }

  try {
    const token = authHeader.startsWith("Bearer ")
      ? authHeader.substring(7)
      : authHeader;

    const secret = process.env.JWT_SECRET || "default-secret";
    const decoded = jwt.verify(token, secret);

    req.user = {
      id: decoded.userId,
      username: decoded.username,
      role: decoded.role,
    };

    next();
  } catch (err) {
    return res.status(401).json({ error: "Invalid or expired token" });
  }
}

function requireRole(role) {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({ error: "Authentication required" });
    }

    const userRole = req.user.role;

    if (userRole !== role) {
      return res.status(403).json({ error: `Requires ${role} role` });
    }

    next();
  };
}

function requirePermission(permission) {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({ error: "Authentication required" });
    }

    if (req.user.role === "admin") {
      return next();
    }

    const [resource, action] = permission.includes(":")
      ? permission.split(":")
      : [permission, "access"];

    if (action !== "read") {
      return res
        .status(403)
        .json({ error: `Requires permission: ${permission}` });
    }

    next();
  };
}

function rateLimit(requestsPerMinute = 60) {
  const requests = new Map();

  return (req, res, next) => {
    const ip = req.ip;
    const now = Date.now();
    const minute = Math.floor(now / 60000);
    const key = `${ip}:${minute}`;

    const count = requests.get(key) || 0;
    requests.set(key, count + 1);

    for (const [k, v] of requests.entries()) {
      const [_, keyMinute] = k.split(":");
      if (parseInt(keyMinute) < minute - 1) {
        requests.delete(k);
      }
    }

    if (count >= requestsPerMinute) {
      return res.status(429).json({ error: "Rate limit exceeded" });
    }

    next();
  };
}

module.exports = {
  requireAuth,
  requireRole,
  requirePermission,
  rateLimit,
};
