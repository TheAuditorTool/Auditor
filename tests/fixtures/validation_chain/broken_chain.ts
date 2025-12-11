/**
 * Test Fixture: Broken Validation Chain
 *
 * Demonstrates a validation chain that breaks midway:
 * 1. Zod validates at entry point (GOOD)
 * 2. Type preserved in orderService.processOrder() (GOOD)
 * 3. Type cast to `any` in legacyAdapter.send() (BAD - chain breaks)
 *
 * Expected: chain_status = "broken", break_index = 2
 */
import express, { Request, Response } from 'express';
import { z } from 'zod';

// Zod schema for order creation
const CreateOrderSchema = z.object({
  productId: z.string().uuid(),
  quantity: z.number().min(1).max(100),
  customerId: z.string(),
  notes: z.string().optional(),
});

type CreateOrderInput = z.infer<typeof CreateOrderSchema>;

// Validation middleware
function validateOrder(req: Request, res: Response, next: Function) {
  const result = CreateOrderSchema.safeParse(req.body);
  if (!result.success) {
    return res.status(400).json({ errors: result.error.errors });
  }
  req.body = result.data;
  next();
}

// Order service - preserves type
class OrderService {
  constructor(private legacyAdapter: LegacyOrderAdapter) {}

  async processOrder(order: CreateOrderInput): Promise<OrderResult> {
    // Type preserved here
    const validated = this.validateBusinessRules(order);
    // CHAIN BREAKS HERE: casting to any before calling legacy system
    return this.legacyAdapter.send(validated as any);
  }

  private validateBusinessRules(order: CreateOrderInput): CreateOrderInput {
    if (order.quantity > 50) {
      console.log('Large order detected, flagging for review');
    }
    return order;
  }
}

// Legacy adapter - accepts any (type safety lost)
class LegacyOrderAdapter {
  async send(data: any): Promise<OrderResult> {
    // Type safety is completely lost here
    // This is where vulnerabilities can creep in
    console.log(`Legacy system received: ${JSON.stringify(data)}`);
    return {
      orderId: 'ORDER-' + Math.random().toString(36).substr(2, 9),
      status: 'pending',
      data: data, // Untyped data passed through
    };
  }
}

interface OrderResult {
  orderId: string;
  status: string;
  data: any; // Untyped - problematic
}

// Express app setup
const app = express();
app.use(express.json());

const legacyAdapter = new LegacyOrderAdapter();
const orderService = new OrderService(legacyAdapter);

// Route with broken validation chain
// Entry: validateOrder validates with Zod
// Hop 1: orderService.processOrder preserves CreateOrderInput
// Hop 2: legacyAdapter.send receives `any` - CHAIN BROKEN
app.post(
  '/api/orders',
  validateOrder,
  async (req: Request, res: Response) => {
    const orderData: CreateOrderInput = req.body;
    const result = await orderService.processOrder(orderData);
    res.json(result);
  }
);

export { app, CreateOrderSchema, CreateOrderInput };
