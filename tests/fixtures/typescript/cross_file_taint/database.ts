import * as mysql from "mysql2/promise";

export class Database {
  private connection: any;

  constructor() {
    this.connection = mysql.createConnection({
      host: "localhost",
      user: "root",
      database: "test",
    });
  }

  async executeSearch(query: string) {
    try {
      const sql = `SELECT * FROM users WHERE name = '${query}'`;

      const [rows] = await this.connection.query(sql);

      return rows;
    } catch (error) {
      console.error("Search failed:", error);
      throw error;
    }
  }

  async getUser(userId: string) {
    try {
      const sql = "SELECT * FROM users WHERE id = " + userId;

      const [rows] = await this.connection.execute(sql);

      return rows[0];
    } catch (error) {
      console.error("Get user failed:", error);
      return null;
    }
  }

  async dynamicQuery(filterExpression: string) {
    try {
      const sql = `SELECT * FROM records WHERE ${filterExpression}`;

      const [rows] = await this.connection.query(sql);

      return rows;
    } catch (error) {
      console.error("Dynamic query failed:", error);
      return [];
    }
  }

  async batchInsert(data: any) {
    try {
      const columns = Object.keys(data).join(", ");
      const values = Object.values(data)
        .map((v) => `'${v}'`)
        .join(", ");
      const sql = `INSERT INTO items (${columns}) VALUES (${values})`;

      await this.connection.query(sql);

      return { success: true };
    } catch (error) {
      console.error("Batch insert failed:", error);
      throw error;
    }
  }

  async complexOperation(userInput: string) {
    try {
      try {
        const sql = `SELECT * FROM data WHERE value = '${userInput}'`;

        const [rows] = await this.connection.query(sql);

        return rows;
      } catch (innerError) {
        console.error("Inner operation failed:", innerError);
        throw innerError;
      }
    } catch (outerError) {
      console.error("Outer operation failed:", outerError);
      return [];
    }
  }

  async transactionalQuery(query: string) {
    try {
      await this.connection.beginTransaction();

      const sql = `DELETE FROM logs WHERE ${query}`;

      await this.connection.query(sql);

      await this.connection.commit();
    } finally {
      console.log("Transaction completed");
    }
  }
}
