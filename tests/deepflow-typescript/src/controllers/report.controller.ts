/**
 * Report controller - HOP 1: Report-related taint sources.
 *
 * Contains endpoints with XSS and template injection vulnerabilities.
 */

import { Router, Request, Response } from 'express';
import { authMiddleware } from '../middleware/auth.middleware';
import { ReportService } from '../services/report.service';

const router = Router();
const reportService = new ReportService();

/**
 * Generate report with custom title.
 *
 * HOP 1: Taint SOURCE - user input from request body.
 *
 * VULNERABILITY: XSS (15 hops)
 */
router.post('/generate', authMiddleware, async (req: Request, res: Response) => {
  const title = req.body.title; // TAINTED - XSS source
  const data = req.body.data;
  const result = await reportService.generate(title, data);
  res.json(result);
});

/**
 * Render report preview.
 *
 * XSS via preview content.
 */
router.post('/preview', authMiddleware, async (req: Request, res: Response) => {
  const content = req.body.content; // TAINTED - XSS source
  const html = await reportService.preview(content);
  res.send(html);
});

/**
 * Search reports.
 *
 * SQL injection via search query.
 */
router.get('/search', authMiddleware, async (req: Request, res: Response) => {
  const query = req.query.q as string; // TAINTED
  const results = await reportService.search(query);
  res.json(results);
});

export { router as reportController };
