/**
 * Safe repository - Demonstrates secure database access.
 *
 * Uses parameterized queries to prevent SQL injection.
 */

export class SafeRepository {
  /**
   * Search safely using parameterized query.
   *
   * SAFE: Uses parameterized query - SQL injection prevented.
   *
   * @param query - Search query (already validated)
   */
  searchSafe(query: string): any {
    // Simulated parameterized query
    // In real implementation: SELECT * FROM users WHERE name LIKE $1
    const parameterizedQuery = {
      text: 'SELECT * FROM users WHERE name LIKE $1',
      values: [`%${query}%`], // Parameter binding prevents injection
    };
    return { results: [], query: parameterizedQuery };
  }

  /**
   * Find by ID safely.
   *
   * SAFE: Uses numeric validation + parameterized query.
   *
   * @param userId - User ID (already validated as numeric)
   */
  findByIdSafe(userId: string): any {
    // Simulated parameterized query
    const parameterizedQuery = {
      text: 'SELECT * FROM users WHERE id = $1',
      values: [parseInt(userId, 10)], // Numeric + parameterized
    };
    return { user: null, query: parameterizedQuery };
  }
}
