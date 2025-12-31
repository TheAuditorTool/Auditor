/**
 * Input validator - HOP 5: Validation layer (INTENTIONALLY WEAK).
 *
 * This validator performs length checks but does NOT sanitize
 * dangerous characters, allowing SQL injection, XSS, etc.
 */

import { DataEnricher } from './data.enricher';

export class InputValidator {
  private enricher: DataEnricher;
  private maxLength = 1000;

  constructor() {
    this.enricher = new DataEnricher();
  }

  /**
   * Check data length (WEAK - does not sanitize content).
   *
   * HOP 5: Only checks length, NOT content.
   * SQL injection chars, XSS payloads all pass through.
   *
   * @param data - Data containing TAINTED values
   */
  checkLength(data: any): any {
    // INTENTIONALLY WEAK: Only check length, not content
    for (const [key, value] of Object.entries(data)) {
      if (typeof value === 'string' && value.length > this.maxLength) {
        throw new Error(`${key} too long`);
      }
      // NOTE: Does NOT check for SQL injection chars
      // NOTE: Does NOT check for XSS payloads
      // NOTE: Does NOT check for command injection chars
    }

    // Pass to enricher (HOP 6)
    return this.enricher.addContext(data);
  }

  /**
   * Check settings (WEAK).
   *
   * @param data - Data with TAINTED settings
   */
  checkSettings(data: any): any {
    // WEAK: Does not validate object structure
    // Prototype pollution vectors pass through
    return this.enricher.addSettingsContext(data);
  }

  /**
   * Check filter (WEAK).
   *
   * @param data - Data with TAINTED filter
   */
  checkFilter(data: any): any {
    // WEAK: Does not validate filter for NoSQL injection
    return this.enricher.addFilterContext(data);
  }

  /**
   * Check format (WEAK).
   *
   * @param data - Data with TAINTED format
   */
  checkFormat(data: any): any {
    // WEAK: Does not validate format for command injection
    const allowedFormats = ['pdf', 'csv', 'json'];
    // BUG: This check is easily bypassed
    // format = "pdf; rm -rf /" passes the includes check
    return this.enricher.addFormatContext(data);
  }

  /**
   * Check filename (WEAK).
   *
   * @param data - Data with TAINTED filename
   */
  checkFilename(data: any): any {
    // WEAK: Does not validate filename for path traversal
    return this.enricher.addFileContext(data);
  }

  /**
   * Check report params (WEAK).
   *
   * @param data - Data with TAINTED title
   */
  checkReportParams(data: any): any {
    // WEAK: Does not validate title for XSS
    return this.enricher.addReportContext(data);
  }

  /**
   * Check content (WEAK).
   *
   * @param data - Data with TAINTED content
   */
  checkContent(data: any): any {
    // WEAK: Does not validate content for XSS
    return this.enricher.addContentContext(data);
  }
}
