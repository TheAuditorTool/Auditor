/**
 * Redis adapter - HOP 9: Caching layer.
 *
 * Caches query results but does NOT sanitize queries.
 */

import { QueryBuilder } from '../core/query.builder';
import { TemplateEngine } from '../core/template.engine';
import { deepMerge } from '../utils/serializer';

export class RedisAdapter {
  private cache: Map<string, any> = new Map();
  private queryBuilder: QueryBuilder;
  private templateEngine: TemplateEngine;

  constructor() {
    this.queryBuilder = new QueryBuilder();
    this.templateEngine = new TemplateEngine();
  }

  /**
   * Get from cache or fetch from database.
   *
   * HOP 9: Cache miss triggers query builder with TAINTED key.
   *
   * @param key - TAINTED search term - flows to SQL query
   */
  getOrFetch(key: string): any {
    const cacheKey = `search:${key}`;
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    // Cache miss - build and execute query (HOP 10+)
    const result = this.queryBuilder.buildUserSearch(key); // key is TAINTED
    this.cache.set(cacheKey, result);
    return result;
  }

  /**
   * Get by ID from cache or database.
   *
   * @param id - TAINTED ID
   */
  getOrFetchById(id: string): any {
    const cacheKey = `id:${id}`;
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    const result = this.queryBuilder.buildUserLookup(id); // TAINTED
    this.cache.set(cacheKey, result);
    return result;
  }

  /**
   * Store settings.
   *
   * @param userId - User ID
   * @param settings - TAINTED settings object
   */
  storeSettings(userId: string, settings: any): any {
    // VULNERABLE: Deep merge with user-controlled object
    // Prototype Pollution vector
    const existing = this.cache.get(`settings:${userId}`) || {};
    const merged = deepMerge(existing, settings); // PROTOTYPE POLLUTION SINK
    this.cache.set(`settings:${userId}`, merged);
    return merged;
  }

  /**
   * Cache report.
   *
   * @param title - TAINTED title
   * @param data - Report data
   */
  cacheReport(title: string, data: any): any {
    // TAINTED title flows to template engine
    const rendered = this.templateEngine.renderReport(title, data);
    this.cache.set(`report:${title}`, rendered);
    return rendered;
  }

  /**
   * Cache content.
   *
   * @param content - TAINTED content
   */
  cacheContent(content: string): string {
    // TAINTED content flows to template engine
    return this.templateEngine.renderContent(content);
  }
}
