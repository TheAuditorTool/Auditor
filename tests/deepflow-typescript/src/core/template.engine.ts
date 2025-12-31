/**
 * Template engine - HOP 14: HTML template rendering.
 *
 * This is the XSS SINK. Tainted user input is inserted into
 * HTML templates without proper escaping.
 */

import { cleanWhitespace } from '../utils/string.utils';

export class TemplateEngine {
  private baseTemplate = `
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
</head>
<body>
    <h1>{title}</h1>
    <div class="content">
        {content}
    </div>
    <footer>
        Generated at: {timestamp}
    </footer>
</body>
</html>
`;

  /**
   * Render report HTML.
   *
   * XSS SINK.
   *
   * @param title - TAINTED report title
   * @param data - Report data
   *
   * VULNERABILITY: Title is inserted without HTML escaping.
   * Payload: <script>alert('XSS')</script>
   */
  renderReport(title: string, data: any): string {
    // Clean whitespace but NOT HTML chars
    const cleanedTitle = cleanWhitespace(title);

    // VULNERABLE: Direct string replacement without escaping
    let html = this.baseTemplate
      .replace(/{title}/g, cleanedTitle) // XSS SINK - not escaped
      .replace(/{content}/g, JSON.stringify(data))
      .replace(/{timestamp}/g, new Date().toISOString());

    return html;
  }

  /**
   * Render content.
   *
   * XSS SINK.
   *
   * @param content - TAINTED content
   */
  renderContent(content: string): string {
    // VULNERABLE: Content inserted without escaping
    return `<div class="preview">${content}</div>`; // XSS SINK
  }

  /**
   * Render user profile.
   *
   * XSS SINK.
   *
   * @param username - TAINTED username
   * @param bio - TAINTED bio
   */
  renderProfile(username: string, bio: string): string {
    // VULNERABLE: Both fields inserted without escaping
    return `
      <div class="profile">
        <h2>Profile: ${username}</h2>
        <div class="bio">${bio}</div>
      </div>
    `;
  }

  /**
   * Render search results.
   *
   * XSS SINK - reflects search query.
   *
   * @param query - TAINTED search query
   * @param results - Search results
   */
  renderSearchResults(query: string, results: any[]): string {
    const items = results.map((r) => `<li>${r}</li>`).join('');

    // VULNERABLE: Query reflected without escaping
    return `
      <div class="search-results">
        <p>Results for: ${query}</p>
        <ul>${items}</ul>
      </div>
    `;
  }

  /**
   * Render with proper HTML escaping (SAFE VERSION).
   *
   * @param title - Title to escape
   * @param data - Report data
   */
  renderSafe(title: string, data: any): string {
    // SAFE: Proper HTML escaping
    const safeTitle = this.escapeHtml(title);

    return this.baseTemplate
      .replace(/{title}/g, safeTitle) // SAFE - escaped
      .replace(/{content}/g, this.escapeHtml(JSON.stringify(data)))
      .replace(/{timestamp}/g, new Date().toISOString());
  }

  private escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}
