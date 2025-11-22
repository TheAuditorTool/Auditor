/**
 * Database layer - contains SQL injection sinks in TRY BLOCKS (TAINT SINKS)
 *
 * CRITICAL: All sinks are inside try blocks to test TypeScript CFG fix.
 * The CFG fix ensures try block bodies have proper line ranges (e.g., lines 20-30)
 * instead of single-line markers (e.g., line 20 only).
 *
 * This demonstrates taint reaching sinks after cross-file propagation:
 *   controller.ts (source) → service.ts (propagation) → database.ts (SINK in try block)
 */

import * as mysql from 'mysql2/promise';

export class Database {
  private connection: any;

  constructor() {
    this.connection = mysql.createConnection({
      host: 'localhost',
      user: 'root',
      database: 'test'
    });
  }

  /**
   * SINK: connection.query inside try block with tainted query parameter
   *
   * Expected vulnerability: SQL Injection
   * Expected CFG: Try block spans lines 30-42 (not single-line marker at 30)
   * Expected taint path: controller.ts:24 → service.ts:18 → database.ts:35
   */
  async executeSearch(query: string) {
    try {
      // VULNERABLE: String concatenation in SQL query
      const sql = `SELECT * FROM users WHERE name = '${query}'`;

      // SINK: Execute query with tainted data (inside try block!)
      const [rows] = await this.connection.query(sql);

      return rows;
    } catch (error) {
      console.error('Search failed:', error);
      throw error;
    }
  }

  /**
   * SINK: connection.execute inside try block with tainted userId
   *
   * Expected vulnerability: SQL Injection
   * Expected CFG: Try block spans lines 51-63 (not single-line marker at 51)
   * Expected taint path: controller.ts:40 → service.ts:35 → database.ts:56
   */
  async getUser(userId: string) {
    try {
      // VULNERABLE: Direct string interpolation
      const sql = "SELECT * FROM users WHERE id = " + userId;

      // SINK: Execute query with tainted data (inside try block!)
      const [rows] = await this.connection.execute(sql);

      return rows[0];
    } catch (error) {
      console.error('Get user failed:', error);
      return null;
    }
  }

  /**
   * SINK: connection.query inside try block with tainted filter expression
   *
   * Expected vulnerability: SQL Injection
   * Expected CFG: Try block spans lines 72-84 (not single-line marker at 72)
   * Expected taint path: controller.ts:56 → service.ts:52 → database.ts:77
   */
  async dynamicQuery(filterExpression: string) {
    try {
      // VULNERABLE: User-controlled WHERE clause
      const sql = `SELECT * FROM records WHERE ${filterExpression}`;

      // SINK: Execute query with tainted data (inside try block!)
      const [rows] = await this.connection.query(sql);

      return rows;
    } catch (error) {
      console.error('Dynamic query failed:', error);
      return [];
    }
  }

  /**
   * SINK: connection.query inside try block with tainted data values
   *
   * Expected vulnerability: SQL Injection
   * Expected CFG: Try block spans lines 93-108 (not single-line marker at 93)
   * Expected taint path: controller.ts:72 → service.ts:69 → database.ts:99
   */
  async batchInsert(data: any) {
    try {
      // VULNERABLE: String interpolation of user data
      const columns = Object.keys(data).join(', ');
      const values = Object.values(data).map(v => `'${v}'`).join(', ');
      const sql = `INSERT INTO items (${columns}) VALUES (${values})`;

      // SINK: Execute query with tainted data (inside try block!)
      await this.connection.query(sql);

      return { success: true };
    } catch (error) {
      console.error('Batch insert failed:', error);
      throw error;
    }
  }

  /**
   * SINK: Nested try blocks with tainted data
   *
   * Expected vulnerability: SQL Injection
   * Expected CFG: Outer try spans lines 117-138, inner try spans lines 119-129
   * Expected taint path: Should handle nested try blocks correctly
   */
  async complexOperation(userInput: string) {
    try {
      try {
        // VULNERABLE: User input in SQL
        const sql = `SELECT * FROM data WHERE value = '${userInput}'`;

        // SINK: Execute query in nested try block
        const [rows] = await this.connection.query(sql);

        return rows;
      } catch (innerError) {
        console.error('Inner operation failed:', innerError);
        throw innerError;
      }
    } catch (outerError) {
      console.error('Outer operation failed:', outerError);
      return [];
    }
  }

  /**
   * SINK: Try-finally block with tainted data
   *
   * Expected vulnerability: SQL Injection
   * Expected CFG: Try block spans lines 147-156
   * Expected taint path: Should handle try-finally correctly
   */
  async transactionalQuery(query: string) {
    try {
      await this.connection.beginTransaction();

      // VULNERABLE: User input in SQL
      const sql = `DELETE FROM logs WHERE ${query}`;

      // SINK: Execute query in try-finally
      await this.connection.query(sql);

      await this.connection.commit();
    } finally {
      // Cleanup
      console.log('Transaction completed');
    }
  }
}
