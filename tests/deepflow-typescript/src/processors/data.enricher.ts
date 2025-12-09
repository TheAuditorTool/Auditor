/**
 * Data enricher - HOP 6: Data enrichment layer.
 *
 * Adds metadata and context but does NOT sanitize tainted data.
 */

import { OutputFormatter } from './output.formatter';

export class DataEnricher {
  private formatter: OutputFormatter;

  constructor() {
    this.formatter = new OutputFormatter();
  }

  /**
   * Add general context to data.
   *
   * HOP 6: Enriches data and passes to formatter (HOP 7).
   *
   * @param data - Data containing TAINTED values
   */
  addContext(data: any): any {
    // Add metadata but don't touch tainted values
    data.enriched = true;
    data.context = 'user_operation';
    data.enrichedAt = new Date().toISOString();

    // Pass to formatter (HOP 7)
    return this.formatter.format(data);
  }

  /**
   * Add settings context.
   *
   * @param data - Data with TAINTED settings
   */
  addSettingsContext(data: any): any {
    data.enriched = true;
    data.context = 'settings_update';
    // TAINTED settings pass through
    return this.formatter.formatSettings(data);
  }

  /**
   * Add filter context.
   *
   * @param data - Data with TAINTED filter
   */
  addFilterContext(data: any): any {
    data.enriched = true;
    data.context = 'filter_operation';
    // TAINTED filter passes through
    return this.formatter.formatFilter(data);
  }

  /**
   * Add format context.
   *
   * @param data - Data with TAINTED format
   */
  addFormatContext(data: any): any {
    data.enriched = true;
    data.context = 'format_operation';
    // TAINTED format passes through
    return this.formatter.formatOutput(data);
  }

  /**
   * Add file context.
   *
   * @param data - Data with TAINTED filename
   */
  addFileContext(data: any): any {
    data.enriched = true;
    data.context = 'file_operation';
    return this.formatter.formatFile(data);
  }

  /**
   * Add report context.
   *
   * @param data - Data with TAINTED title
   */
  addReportContext(data: any): any {
    data.enriched = true;
    data.context = 'report_generation';
    // TAINTED title passes through
    return this.formatter.formatReport(data);
  }

  /**
   * Add content context.
   *
   * @param data - Data with TAINTED content
   */
  addContentContext(data: any): any {
    data.enriched = true;
    data.context = 'content_preview';
    // TAINTED content passes through
    return this.formatter.formatContent(data);
  }
}
