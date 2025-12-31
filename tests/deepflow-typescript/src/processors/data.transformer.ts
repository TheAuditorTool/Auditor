/**
 * Data transformer - HOP 4: Data transformation layer.
 *
 * Transforms data but does NOT sanitize user input.
 */

import { InputValidator } from './input.validator';

export class DataTransformer {
  private validator: InputValidator;

  constructor() {
    this.validator = new InputValidator();
  }

  /**
   * Prepare search term for database query.
   *
   * HOP 4: Transformer adds metadata but doesn't sanitize the term.
   *
   * @param term - TAINTED search term from user input
   */
  prepareSearch(term: string): any {
    // Add metadata but don't sanitize the tainted term
    const prepared = {
      searchTerm: term, // Still TAINTED
      operation: 'search',
      timestamp: new Date().toISOString(),
    };
    // Pass to validator (HOP 5)
    return this.validator.checkLength(prepared);
  }

  /**
   * Prepare user lookup.
   *
   * @param userId - TAINTED user identifier
   */
  prepareLookup(userId: string): any {
    const prepared = {
      userId: userId, // Still TAINTED
      operation: 'lookup',
    };
    return this.validator.checkLength(prepared);
  }

  /**
   * Prepare settings update.
   *
   * @param userId - User ID
   * @param settings - TAINTED settings object
   */
  prepareSettingsUpdate(userId: string, settings: any): any {
    const prepared = {
      userId,
      settings: settings, // TAINTED - Prototype Pollution
      operation: 'update_settings',
    };
    return this.validator.checkSettings(prepared);
  }

  /**
   * Prepare filter for NoSQL query.
   *
   * @param filter - TAINTED filter object
   */
  prepareFilter(filter: any): any {
    const prepared = {
      filter: filter, // TAINTED - NoSQL Injection
      operation: 'filter',
    };
    return this.validator.checkFilter(prepared);
  }

  /**
   * Prepare order processing.
   *
   * @param orderId - Order ID
   * @param outputFormat - TAINTED format string
   */
  prepareOrderProcess(orderId: string, outputFormat: string): any {
    const prepared = {
      orderId,
      format: outputFormat, // TAINTED - Command Injection
      operation: 'process_order',
    };
    return this.validator.checkFormat(prepared);
  }

  /**
   * Prepare order export.
   *
   * @param orderId - Order ID
   * @param filename - TAINTED filename
   */
  prepareOrderExport(orderId: string, filename: string): any {
    const prepared = {
      orderId,
      filename: filename, // TAINTED
      operation: 'export_order',
    };
    return this.validator.checkFilename(prepared);
  }

  /**
   * Prepare status query.
   *
   * @param orderId - Order ID
   */
  prepareStatusQuery(orderId: string): any {
    return this.validator.checkLength({ orderId, operation: 'status' });
  }

  /**
   * Prepare report generation.
   *
   * @param title - TAINTED title
   * @param data - Report data
   */
  prepareReportGeneration(title: string, data: any): any {
    const prepared = {
      title: title, // TAINTED - XSS
      data,
      operation: 'generate_report',
    };
    return this.validator.checkReportParams(prepared);
  }

  /**
   * Prepare preview.
   *
   * @param content - TAINTED content
   */
  preparePreview(content: string): any {
    const prepared = {
      content: content, // TAINTED - XSS
      operation: 'preview',
    };
    return this.validator.checkContent(prepared);
  }

  /**
   * Prepare report search.
   *
   * @param query - TAINTED query
   */
  prepareReportSearch(query: string): any {
    return this.prepareSearch(query);
  }
}
