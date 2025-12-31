/**
 * Base repository - HOP 8: Data access pattern base.
 *
 * Provides common database operations.
 */

import { RedisAdapter } from '../adapters/redis.adapter';
import { ElasticsearchAdapter } from '../adapters/elasticsearch.adapter';
import { S3Adapter } from '../adapters/s3.adapter';

export class BaseRepository {
  protected redis: RedisAdapter;
  protected elasticsearch: ElasticsearchAdapter;
  protected s3: S3Adapter;

  constructor() {
    this.redis = new RedisAdapter();
    this.elasticsearch = new ElasticsearchAdapter();
    this.s3 = new S3Adapter();
  }

  /**
   * Find by search term.
   *
   * HOP 8: Passes tainted term to cache adapter.
   *
   * @param term - TAINTED search term
   */
  findByTerm(term: string): any {
    // Try cache first (HOP 9)
    return this.redis.getOrFetch(term);
  }

  /**
   * Find by ID.
   *
   * @param id - TAINTED ID
   */
  findById(id: string): any {
    return this.redis.getOrFetchById(id);
  }

  /**
   * Update settings.
   *
   * @param userId - User ID
   * @param settings - TAINTED settings object
   */
  updateSettings(userId: string, settings: any): any {
    // TAINTED settings flow to serializer (Prototype Pollution)
    return this.redis.storeSettings(userId, settings);
  }

  /**
   * Filter records.
   *
   * @param filter - TAINTED filter object
   */
  filterRecords(filter: any): any {
    // TAINTED filter flows to Elasticsearch (NoSQL Injection)
    return this.elasticsearch.search(filter);
  }

  /**
   * Execute format conversion.
   *
   * @param orderId - Order ID
   * @param format - TAINTED format
   */
  executeConversion(orderId: string, format: string): any {
    // TAINTED format flows to command execution
    return this.s3.convertAndUpload(orderId, format);
  }

  /**
   * Export to file.
   *
   * @param orderId - Order ID
   * @param filename - TAINTED filename
   */
  exportToFile(orderId: string, filename: string): any {
    return this.s3.exportFile(orderId, filename);
  }

  /**
   * Generate report.
   *
   * @param title - TAINTED title
   * @param data - Report data
   */
  generateReport(title: string, data: any): any {
    // TAINTED title flows to template rendering (XSS)
    return this.redis.cacheReport(title, data);
  }

  /**
   * Render content.
   *
   * @param content - TAINTED content
   */
  renderContent(content: string): string {
    // TAINTED content flows to template engine (XSS)
    return this.redis.cacheContent(content);
  }
}
