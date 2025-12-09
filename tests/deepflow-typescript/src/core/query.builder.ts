/**
 * Query builder - HOPs 12-18: SQL query construction.
 *
 * This is the SQL INJECTION SINK. Tainted user input is concatenated
 * into SQL queries and executed.
 */

import { cleanWhitespace } from '../utils/string.utils';
import { serializeResult } from '../utils/serializer';

export class QueryBuilder {
  /**
   * Build and execute user search query.
   *
   * HOPS 12-18: SQL INJECTION SINK.
   *
   * @param term - TAINTED search term from user input
   *
   * VULNERABILITY: Template literal SQL concatenation allows injection.
   * Payload: ' OR '1'='1' --
   */
  buildUserSearch(term: string): any {
    // HOP 12: Build base query
    const base = 'SELECT * FROM users WHERE ';

    // HOP 13: Clean whitespace (does NOT sanitize)
    const cleanedTerm = cleanWhitespace(term);

    // HOP 14: Add condition (VULNERABLE - string concatenation)
    const condition = `name LIKE '%${cleanedTerm}%'`; // term is TAINTED!

    // HOP 15: Combine
    let query = base + condition;

    // HOP 16: Add ordering
    query += ' ORDER BY created_at DESC';

    // HOP 17: Add limit
    query += ' LIMIT 100';

    // HOP 18: Execute (SQL INJECTION SINK)
    console.log('Executing query:', query); // VULNERABLE: Tainted query logged
    return serializeResult({ query, results: [] });
  }

  /**
   * Build and execute user lookup query.
   *
   * SQL INJECTION SINK.
   *
   * @param userId - TAINTED user ID
   */
  buildUserLookup(userId: string): any {
    // VULNERABLE: Direct string interpolation
    const query = `SELECT * FROM users WHERE id = ${userId}`; // TAINTED

    console.log('Executing query:', query); // SQL INJECTION SINK
    return serializeResult({ query, user: null });
  }

  /**
   * Build report search query.
   *
   * SQL INJECTION SINK.
   *
   * @param query - TAINTED search query
   */
  buildReportSearch(searchQuery: string): any {
    // VULNERABLE: String concatenation
    const query = `SELECT * FROM reports WHERE title LIKE '%${searchQuery}%'`;
    return serializeResult({ query, results: [] });
  }

  /**
   * Build safe query with parameterization.
   *
   * SAFE VERSION - for comparison.
   *
   * @param term - Search term
   */
  buildSafeSearch(term: string): any {
    // SAFE: Parameterized query
    const query = {
      text: 'SELECT * FROM users WHERE name LIKE $1',
      values: [`%${term}%`],
    };
    return serializeResult({ query, results: [] });
  }
}
