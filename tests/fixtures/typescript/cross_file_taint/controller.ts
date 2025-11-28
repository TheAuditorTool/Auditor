import { Request, Response } from "express";
import { SearchService } from "./service";

const searchService = new SearchService();

export class SearchController {
  async search(req: Request, res: Response) {
    const query = req.query.search as string;

    const results = await searchService.search(query);

    res.send(results);
  }

  async getUserById(req: Request, res: Response) {
    const userId = req.params.id;

    const user = await searchService.getUserById(userId);

    res.send(user);
  }

  async filterRecords(req: Request, res: Response) {
    const filterExpression = req.body.filter;

    const records = await searchService.filterRecords(filterExpression);

    res.send({ data: records });
  }

  async batchProcess(req: Request, res: Response) {
    const items = req.body.items;

    await searchService.batchProcess(items);

    res.send({ status: "processed" });
  }
}
