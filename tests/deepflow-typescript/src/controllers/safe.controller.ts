/**
 * Safe controller - Sanitized path demonstrations.
 *
 * These endpoints demonstrate SAFE patterns that should NOT be
 * flagged as vulnerable by TheAuditor.
 */

import { Router, Request, Response } from 'express';
import { SafeService } from '../services/safe.service';

const router = Router();
const safeService = new SafeService();

/**
 * Safe search with parameterized queries.
 *
 * SANITIZED PATH #1: Parameterized SQL query.
 */
router.get('/search', async (req: Request, res: Response) => {
  const query = req.query.q as string;
  // Input is passed to parameterized query (safe)
  const results = await safeService.safeSearch(query);
  res.json(results);
});

/**
 * Safe user lookup with input validation.
 *
 * SANITIZED PATH #2: Input validation with Joi/Zod-like schema.
 */
router.get('/users/:userId', async (req: Request, res: Response) => {
  const userId = req.params.userId;

  // SANITIZER: Validate userId is numeric
  if (!/^\d+$/.test(userId)) {
    return res.status(400).json({ error: 'Invalid user ID format' });
  }

  const user = await safeService.getUserById(userId);
  res.json(user);
});

/**
 * Safe HTML rendering with escaping.
 *
 * SANITIZED PATH #3: HTML escaping prevents XSS.
 */
router.post('/render', async (req: Request, res: Response) => {
  const content = req.body.content;
  // Content is HTML-escaped before rendering
  const html = await safeService.safeRender(content);
  res.send(html);
});

export { router as safeController };
