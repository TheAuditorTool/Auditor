/**
 * Report service - HOP 3: Business logic for reports.
 *
 * Handles report generation with XSS vulnerability.
 */

import { DataTransformer } from '../processors/data.transformer';

export class ReportService {
  private transformer: DataTransformer;

  constructor() {
    this.transformer = new DataTransformer();
  }

  /**
   * Generate report with custom title.
   *
   * HOP 3: Passes tainted title to processor.
   *
   * @param title - TAINTED title - XSS vector
   * @param data - Report data
   */
  async generate(title: string, data: any): Promise<any> {
    return this.transformer.prepareReportGeneration(title, data);
  }

  /**
   * Preview report content.
   *
   * @param content - TAINTED content - XSS vector
   */
  async preview(content: string): Promise<string> {
    return this.transformer.preparePreview(content);
  }

  /**
   * Search reports.
   *
   * @param query - TAINTED query - SQL injection vector
   */
  async search(query: string): Promise<any> {
    return this.transformer.prepareReportSearch(query);
  }
}
