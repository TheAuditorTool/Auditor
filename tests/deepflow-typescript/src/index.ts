/**
 * Express application entry point.
 *
 * DeepFlow TypeScript - Multi-hop taint analysis validation fixture.
 *
 * WARNING: This application contains intentional security vulnerabilities
 * for testing purposes. DO NOT deploy in production.
 */

import express from 'express';
import { userController } from './controllers/user.controller';
import { orderController } from './controllers/order.controller';
import { reportController } from './controllers/report.controller';
import { safeController } from './controllers/safe.controller';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Vulnerable routes
app.use('/users', userController);
app.use('/orders', orderController);
app.use('/reports', reportController);

// Safe routes (sanitized path demos)
app.use('/safe', safeController);

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'DeepFlow TypeScript',
    description: 'Multi-hop taint analysis validation fixture',
    warning: 'CONTAINS INTENTIONAL VULNERABILITIES - DO NOT DEPLOY',
    endpoints: {
      '/users/search?q=<query>': 'SQL Injection (18 hops)',
      '/orders/process': 'Command Injection (10 hops)',
      '/reports/generate': 'XSS + NoSQL Injection',
      '/safe/*': 'Sanitized path demonstrations',
    },
  });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(PORT, () => {
  console.log(`DeepFlow TypeScript running on port ${PORT}`);
});

export default app;
