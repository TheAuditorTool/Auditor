/**
 * User controller - HOP 1: Taint sources from HTTP requests.
 *
 * This module contains endpoints that accept user input, which becomes
 * the SOURCE of taint in our vulnerability chains.
 */

import { Router, Request, Response } from 'express';
import { authMiddleware } from '../middleware/auth.middleware';
import { UserService } from '../services/user.service';

const router = Router();
const userService = new UserService();

/**
 * Search users by query.
 *
 * HOP 1: Taint SOURCE - user input from query parameter 'q'.
 * This input flows through 18 layers to reach a SQL sink.
 *
 * VULNERABILITY: SQL Injection (18 hops)
 */
router.get('/search', authMiddleware, async (req: Request, res: Response) => {
  const query = req.query.q as string; // TAINTED
  const results = await userService.search(query);
  res.json(results);
});

/**
 * Get user by ID.
 *
 * HOP 1: Taint SOURCE - user input from path parameter.
 */
router.get('/:userId', authMiddleware, async (req: Request, res: Response) => {
  const userId = req.params.userId; // TAINTED
  const user = await userService.getById(userId);
  res.json(user);
});

/**
 * Update user settings.
 *
 * HOP 1: Taint SOURCE - user input from request body.
 *
 * VULNERABILITY: Prototype Pollution (8 hops)
 */
router.put('/:userId/settings', authMiddleware, async (req: Request, res: Response) => {
  const userId = req.params.userId;
  const settings = req.body.settings; // TAINTED - Prototype Pollution source
  const result = await userService.updateSettings(userId, settings);
  res.json(result);
});

/**
 * Filter users.
 *
 * HOP 1: Taint SOURCE - user input for NoSQL injection.
 *
 * VULNERABILITY: NoSQL Injection (12 hops)
 */
router.post('/filter', authMiddleware, async (req: Request, res: Response) => {
  const filter = req.body.filter; // TAINTED - NoSQL injection source
  const results = await userService.filter(filter);
  res.json(results);
});

export { router as userController };
