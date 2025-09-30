import express from 'express';
import type { Request, Response } from 'express';
import { fetchPlants, storeSnapshot } from '../utils/data';

const app = express();
app.use(express.json());

app.get('/api/plants', async (req: Request, res: Response) => {
  const owner = typeof req.query.owner === 'string' ? req.query.owner : 'unknown';
  const plants = await fetchPlants(owner);
  res.json(plants.rows);
});

app.post('/api/plants', async (req: Request, res: Response) => {
  await storeSnapshot(JSON.stringify(req.body));
  res.status(201).json({ ok: true });
});

export default app;
