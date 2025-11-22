/**
 * Authentication and authorization middleware
 *
 * Tests api_endpoint_controls extraction for Express.
 * Middleware chain pattern: requireAuth → requireRole → route handler
 */

const jwt = require('jsonwebtoken');

/**
 * requireAuth middleware
 *
 * Verifies JWT token in Authorization header.
 * Tests api_endpoint_controls extraction.
 */
function requireAuth(req, res, next) {
  // TAINT SOURCE: Token from external input
  const authHeader = req.headers.authorization;

  if (!authHeader) {
    return res.status(401).json({ error: 'Missing authorization token' });
  }

  try {
    // Remove 'Bearer ' prefix if present
    const token = authHeader.startsWith('Bearer ')
      ? authHeader.substring(7)
      : authHeader;

    // TAINT FLOW: Token validation
    const secret = process.env.JWT_SECRET || 'default-secret';
    const decoded = jwt.verify(token, secret);

    // Store user info in request object
    req.user = {
      id: decoded.userId,
      username: decoded.username,
      role: decoded.role
    };

    next();
  } catch (err) {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
}

/**
 * requireRole middleware factory
 *
 * Creates middleware that checks for specific role.
 * Tests api_endpoint_controls extraction with parameterized decorators.
 *
 * @param {string} role - Required role (e.g., 'admin', 'manager')
 */
function requireRole(role) {
  return (req, res, next) => {
    // Assumes requireAuth was already applied
    if (!req.user) {
      return res.status(401).json({ error: 'Authentication required' });
    }

    // TAINT SOURCE: User role from JWT
    const userRole = req.user.role;

    if (userRole !== role) {
      return res.status(403).json({ error: `Requires ${role} role` });
    }

    next();
  };
}

/**
 * requirePermission middleware factory
 *
 * Fine-grained permission check (e.g., 'products:create', 'orders:delete').
 * Tests api_endpoint_controls extraction with complex authorization.
 *
 * @param {string} permission - Required permission string
 */
function requirePermission(permission) {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({ error: 'Authentication required' });
    }

    // In a real app, would check permissions in database
    // For fixture purposes, admin role has all permissions
    if (req.user.role === 'admin') {
      return next();
    }

    // Parse permission (e.g., 'products:create' -> resource:action)
    const [resource, action] = permission.includes(':')
      ? permission.split(':')
      : [permission, 'access'];

    // Non-admins can only read
    if (action !== 'read') {
      return res.status(403).json({ error: `Requires permission: ${permission}` });
    }

    next();
  };
}

/**
 * rateLimit middleware factory
 *
 * Rate limiting decorator.
 * Tests api_endpoint_controls extraction for rate limiting.
 *
 * @param {number} requestsPerMinute - Maximum requests allowed per minute
 */
function rateLimit(requestsPerMinute = 60) {
  // In a real app, would use Redis or similar
  const requests = new Map();

  return (req, res, next) => {
    const ip = req.ip;
    const now = Date.now();
    const minute = Math.floor(now / 60000);
    const key = `${ip}:${minute}`;

    const count = requests.get(key) || 0;
    requests.set(key, count + 1);

    // Clean old entries
    for (const [k, v] of requests.entries()) {
      const [_, keyMinute] = k.split(':');
      if (parseInt(keyMinute) < minute - 1) {
        requests.delete(k);
      }
    }

    if (count >= requestsPerMinute) {
      return res.status(429).json({ error: 'Rate limit exceeded' });
    }

    next();
  };
}

module.exports = {
  requireAuth,
  requireRole,
  requirePermission,
  rateLimit
};
