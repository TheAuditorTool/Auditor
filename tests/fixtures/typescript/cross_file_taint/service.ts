import { Database } from "./database";

export class SearchService {
  private db: Database;

  constructor() {
    this.db = new Database();
  }

  async search(query: string) {
    const results = await this.db.executeSearch(query);
    return results;
  }

  async getUserById(userId: string) {
    const user = await this.db.getUser(userId);
    return user;
  }

  async filterRecords(filterExpression: string) {
    const records = await this.db.dynamicQuery(filterExpression);
    return records;
  }

  async batchProcess(items: any[]) {
    for (const item of items) {
      await this.db.batchInsert(item);
    }
  }

  async advancedSearch(searchTerm: string, options: any) {
    const processedQuery = `%${searchTerm}%`;

    const results = await this.db.executeSearch(processedQuery);

    return results;
  }
}
