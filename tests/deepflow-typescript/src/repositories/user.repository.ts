/**
 * User repository - HOP 8: User data access.
 *
 * Handles user database operations.
 */

import { BaseRepository } from './base.repository';
import { QueryBuilder } from '../core/query.builder';

export class UserRepository extends BaseRepository {
  private queryBuilder: QueryBuilder;

  constructor() {
    super();
    this.queryBuilder = new QueryBuilder();
  }

  /**
   * Search users by term.
   *
   * @param term - TAINTED search term
   */
  searchByTerm(term: string): any {
    return this.queryBuilder.buildUserSearch(term);
  }

  /**
   * Find user by ID.
   *
   * @param userId - TAINTED user ID
   */
  findUserById(userId: string): any {
    return this.queryBuilder.buildUserLookup(userId);
  }
}
