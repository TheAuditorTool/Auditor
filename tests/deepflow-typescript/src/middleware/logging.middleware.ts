/**
 * Logging middleware - Logs requests without sanitization.
 */

import { Request, Response, NextFunction } from 'express';

/**
 * Request logger.
 *
 * Logs request details including potentially tainted data.
 */
export function requestLogger(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const timestamp = new Date().toISOString();
  const method = req.method;
  const path = req.path;

  // TAINTED data may appear in logs
  console.log(`[${timestamp}] ${method} ${path}`, {
    query: req.query,
    body: req.body,
    params: req.params,
  });

  next();
}

/**
 * Response logger.
 */
export function responseLogger(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const originalSend = res.send.bind(res);

  res.send = function (body: any): Response {
    console.log(`Response for ${req.path}:`, typeof body);
    return originalSend(body);
  };

  next();
}
