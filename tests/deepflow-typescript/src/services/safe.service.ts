/**
 * Safe service - Demonstrates sanitized patterns.
 *
 * These methods use secure coding practices that should be
 * recognized by TheAuditor as NOT vulnerable.
 */

import { SafeRepository } from '../repositories/safe.repository';
import { escapeHtml } from '../utils/string.utils';

export class SafeService {
  private repository: SafeRepository;

  constructor() {
    this.repository = new SafeRepository();
  }

  /**
   * Safe search using parameterized queries.
   *
   * @param query - Search query (will be parameterized, not concatenated)
   */
  async safeSearch(query: string): Promise<any> {
    return this.repository.searchSafe(query);
  }

  /**
   * Get user by ID (already validated).
   *
   * @param userId - User ID (numeric, already validated)
   */
  async getUserById(userId: string): Promise<any> {
    return this.repository.findByIdSafe(userId);
  }

  /**
   * Safe HTML rendering with escaping.
   *
   * @param content - Content to render (will be HTML escaped)
   */
  async safeRender(content: string): Promise<string> {
    // SANITIZER: HTML escape before rendering
    const safeContent = escapeHtml(content);
    return `<div class="content">${safeContent}</div>`;
  }
}
