/**
 * User service - HOP 3: Business logic layer.
 *
 * Receives tainted data from controllers and passes to processors.
 */

import { DataTransformer } from '../processors/data.transformer';

export class UserService {
  private transformer: DataTransformer;

  constructor() {
    this.transformer = new DataTransformer();
  }

  /**
   * Search for users by query string.
   *
   * HOP 3: Service layer passes tainted query to processor.
   *
   * @param query - TAINTED user input from request.query
   */
  async search(query: string): Promise<any> {
    // Pass tainted query to transformer (HOP 4)
    return this.transformer.prepareSearch(query);
  }

  /**
   * Get user by ID.
   *
   * @param userId - TAINTED user input from path parameter
   */
  async getById(userId: string): Promise<any> {
    return this.transformer.prepareLookup(userId);
  }

  /**
   * Update user settings.
   *
   * @param userId - User ID
   * @param settings - TAINTED settings object - Prototype Pollution vector
   */
  async updateSettings(userId: string, settings: any): Promise<any> {
    return this.transformer.prepareSettingsUpdate(userId, settings);
  }

  /**
   * Filter users by criteria.
   *
   * @param filter - TAINTED filter object - NoSQL injection vector
   */
  async filter(filter: any): Promise<any> {
    return this.transformer.prepareFilter(filter);
  }
}
