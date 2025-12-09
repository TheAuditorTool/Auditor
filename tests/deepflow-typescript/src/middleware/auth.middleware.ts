/**
 * Authentication middleware - HOP 2: Passes tainted data through.
 *
 * This middleware performs authentication but does NOT sanitize
 * the tainted parameters, allowing them to flow to deeper layers.
 */

import { Request, Response, NextFunction } from 'express';

/**
 * Authentication middleware.
 *
 * HOP 2: Middleware passes tainted data through without sanitization.
 *
 * The middleware checks authorization headers but does not modify or
 * sanitize any request parameters - tainted input flows through unchanged.
 */
export function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const authHeader = req.headers.authorization;

  // Simple auth check - doesn't touch tainted params
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    // For fixture purposes, allow all requests
    // In real app, would return 401
  }

  // CRITICAL: req.query, req.body, req.params all pass through unchanged
  // Tainted data flows to the next handler
  next();
}

/**
 * Logging middleware.
 *
 * Logs requests but does not sanitize tainted data.
 */
export function loggingMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  // Log the request - tainted data appears in logs
  console.log(`${req.method} ${req.path}`, {
    query: req.query, // May contain TAINTED data
    body: req.body, // May contain TAINTED data
  });

  next();
}

/**
 * Validation middleware (WEAK).
 *
 * Only checks for required fields, not content.
 */
export function validationMiddleware(requiredFields: string[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    for (const field of requiredFields) {
      if (!req.body[field]) {
        res.status(400).json({ error: `Missing required field: ${field}` });
        return;
      }
    }
    // Does NOT validate content of fields - tainted data passes through
    next();
  };
}
