/**
 * Controller layer - receives user input (TAINT SOURCES)
 *
 * Expected taint flows:
 *   - req.query → service → database (cross-file, 3 hops)
 *   - req.params → service → database (cross-file, 3 hops)
 *   - req.body → service → database (cross-file, 3 hops)
 */

import { Request, Response } from 'express';
import { SearchService } from './service';

const searchService = new SearchService();

export class SearchController {
  /**
   * TAINT SOURCE: req.query.search
   *
   * Expected path:
   *   controller.ts:24 (req.query) → service.ts:18 (search) → database.ts:25 (query in try block)
   */
  async search(req: Request, res: Response) {
    // SOURCE: User-controlled query parameter
    const query = req.query.search as string;

    // Cross-file call with tainted data
    const results = await searchService.search(query);

    res.send(results);
  }

  /**
   * TAINT SOURCE: req.params.id
   *
   * Expected path:
   *   controller.ts:40 (req.params) → service.ts:35 (getUserById) → database.ts:52 (execute in try block)
   */
  async getUserById(req: Request, res: Response) {
    // SOURCE: User-controlled URL parameter
    const userId = req.params.id;

    // Cross-file call with tainted data
    const user = await searchService.getUserById(userId);

    res.send(user);
  }

  /**
   * TAINT SOURCE: req.body.filter
   *
   * Expected path:
   *   controller.ts:56 (req.body) → service.ts:52 (filterRecords) → database.ts:79 (raw in try block)
   */
  async filterRecords(req: Request, res: Response) {
    // SOURCE: User-controlled JSON body
    const filterExpression = req.body.filter;

    // Cross-file call with tainted data
    const records = await searchService.filterRecords(filterExpression);

    res.send({ data: records });
  }

  /**
   * TAINT SOURCE: req.body.items
   *
   * Expected path:
   *   controller.ts:72 (req.body) → service.ts:69 (batchProcess) → database.ts:106 (query in try block)
   */
  async batchProcess(req: Request, res: Response) {
    // SOURCE: User-controlled array of items
    const items = req.body.items;

    // Cross-file call with tainted data
    await searchService.batchProcess(items);

    res.send({ status: 'processed' });
  }
}
