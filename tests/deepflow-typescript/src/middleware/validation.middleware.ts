/**
 * Validation middleware - Additional HOP in the chain.
 *
 * Performs weak validation that does NOT prevent attacks.
 */

import { Request, Response, NextFunction } from 'express';

/**
 * Request body validator (WEAK).
 *
 * Only checks types, not content. Does NOT sanitize.
 */
export function validateBody(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  // WEAK: Only checks if body exists
  if (!req.body || typeof req.body !== 'object') {
    res.status(400).json({ error: 'Invalid request body' });
    return;
  }

  // Does NOT check for injection patterns
  // Tainted data passes through
  next();
}

/**
 * Query parameter validator (WEAK).
 *
 * Only checks for empty strings.
 */
export function validateQuery(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const query = req.query.q as string;

  // WEAK: Only checks if query is non-empty
  if (query && query.length === 0) {
    res.status(400).json({ error: 'Empty query not allowed' });
    return;
  }

  // Does NOT check for SQL injection patterns
  // Tainted data passes through
  next();
}

/**
 * Length validator.
 *
 * Checks max length but NOT content.
 */
export function validateLength(maxLength: number) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const query = req.query.q as string;

    if (query && query.length > maxLength) {
      res.status(400).json({ error: 'Query too long' });
      return;
    }

    // Length is OK, but content not checked
    // SQL injection, XSS, etc. all pass through
    next();
  };
}
