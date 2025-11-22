/**
 * Service layer - business logic that propagates taint
 *
 * This demonstrates multi-hop taint propagation:
 *   controller.ts (source) → service.ts (propagation) → database.ts (sink in try block)
 */

import { Database } from './database';

export class SearchService {
  private db: Database;

  constructor() {
    this.db = new Database();
  }

  /**
   * TAINT PROPAGATION: query parameter is tainted from controller
   *
   * Expected flow:
   *   query (tainted) → this.db.executeSearch(query) → [cross-file to database.ts]
   */
  async search(query: string) {
    // Propagate tainted data to database layer
    const results = await this.db.executeSearch(query);
    return results;
  }

  /**
   * TAINT PROPAGATION: userId is tainted from controller
   *
   * Expected flow:
   *   userId (tainted) → this.db.getUser(userId) → [cross-file to database.ts]
   */
  async getUserById(userId: string) {
    // Propagate tainted data to database layer
    const user = await this.db.getUser(userId);
    return user;
  }

  /**
   * TAINT PROPAGATION: filterExpression is tainted from controller
   *
   * Expected flow:
   *   filterExpression (tainted) → this.db.dynamicQuery(filterExpression) → [cross-file to database.ts]
   */
  async filterRecords(filterExpression: string) {
    // Propagate tainted data to database layer
    const records = await this.db.dynamicQuery(filterExpression);
    return records;
  }

  /**
   * TAINT PROPAGATION: items array contains tainted data
   *
   * Expected flow:
   *   items (tainted) → this.db.batchInsert(item) → [cross-file to database.ts]
   */
  async batchProcess(items: any[]) {
    // Batch processing that propagates taint
    for (const item of items) {
      await this.db.batchInsert(item);
    }
  }

  /**
   * TAINT PROPAGATION: Complex flow with transformation
   *
   * Expected flow:
   *   searchTerm (tainted) → processedQuery (still tainted) → this.db.executeSearch → [cross-file]
   */
  async advancedSearch(searchTerm: string, options: any) {
    // Transform tainted data (but still tainted)
    const processedQuery = `%${searchTerm}%`;

    // Propagate transformed tainted data
    const results = await this.db.executeSearch(processedQuery);

    return results;
  }
}
