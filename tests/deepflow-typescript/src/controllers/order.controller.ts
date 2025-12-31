/**
 * Order controller - HOP 1: Additional taint sources.
 *
 * Contains endpoints with command injection vulnerabilities.
 */

import { Router, Request, Response } from 'express';
import { authMiddleware } from '../middleware/auth.middleware';
import { OrderService } from '../services/order.service';

const router = Router();
const orderService = new OrderService();

/**
 * Process order with custom format.
 *
 * HOP 1: Taint SOURCE - user input from request body.
 *
 * VULNERABILITY: Command Injection (10 hops)
 */
router.post('/process', authMiddleware, async (req: Request, res: Response) => {
  const orderId = req.body.orderId;
  const outputFormat = req.body.format; // TAINTED - Command Injection source
  const result = await orderService.process(orderId, outputFormat);
  res.json(result);
});

/**
 * Export order to file.
 *
 * Command injection via filename parameter.
 */
router.post('/export', authMiddleware, async (req: Request, res: Response) => {
  const orderId = req.body.orderId;
  const filename = req.body.filename; // TAINTED
  const result = await orderService.export(orderId, filename);
  res.json(result);
});

/**
 * Get order status.
 */
router.get('/:orderId/status', authMiddleware, async (req: Request, res: Response) => {
  const orderId = req.params.orderId;
  const status = await orderService.getStatus(orderId);
  res.json(status);
});

export { router as orderController };
