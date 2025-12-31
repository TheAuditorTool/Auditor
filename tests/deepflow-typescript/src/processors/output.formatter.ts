/**
 * Output formatter - HOP 7: Output formatting layer.
 *
 * Formats data for output but does NOT sanitize tainted values.
 */

import { BaseRepository } from '../repositories/base.repository';

export class OutputFormatter {
  private repository: BaseRepository;

  constructor() {
    this.repository = new BaseRepository();
  }

  /**
   * Format data for output.
   *
   * HOP 7: Formats and passes to repository (HOP 8).
   *
   * @param data - Data containing TAINTED values
   */
  format(data: any): any {
    // Add formatting metadata
    data.formatted = true;
    data.formattedAt = new Date().toISOString();

    // Pass to repository (HOP 8)
    if (data.searchTerm) {
      return this.repository.findByTerm(data.searchTerm);
    }
    if (data.userId) {
      return this.repository.findById(data.userId);
    }
    return data;
  }

  /**
   * Format settings for processing.
   *
   * @param data - Data with TAINTED settings
   */
  formatSettings(data: any): any {
    data.formatted = true;
    // TAINTED settings passed to repository
    return this.repository.updateSettings(data.userId, data.settings);
  }

  /**
   * Format filter for query.
   *
   * @param data - Data with TAINTED filter
   */
  formatFilter(data: any): any {
    data.formatted = true;
    // TAINTED filter passed to repository
    return this.repository.filterRecords(data.filter);
  }

  /**
   * Format output for conversion.
   *
   * @param data - Data with TAINTED format
   */
  formatOutput(data: any): any {
    data.formatted = true;
    // TAINTED format passed to command execution
    return this.repository.executeConversion(data.orderId, data.format);
  }

  /**
   * Format file operation.
   *
   * @param data - Data with TAINTED filename
   */
  formatFile(data: any): any {
    data.formatted = true;
    return this.repository.exportToFile(data.orderId, data.filename);
  }

  /**
   * Format report for generation.
   *
   * @param data - Data with TAINTED title
   */
  formatReport(data: any): any {
    data.formatted = true;
    // TAINTED title passed to template rendering
    return this.repository.generateReport(data.title, data.data);
  }

  /**
   * Format content for preview.
   *
   * @param data - Data with TAINTED content
   */
  formatContent(data: any): any {
    data.formatted = true;
    // TAINTED content passed to template rendering
    return this.repository.renderContent(data.content);
  }
}
