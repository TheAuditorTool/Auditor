/**
 * String utilities - HOP 15: String operations.
 *
 * Provides string manipulation that does NOT sanitize dangerous content.
 */

/**
 * Clean whitespace from string.
 *
 * HOP 15: Only removes whitespace, does NOT sanitize.
 *
 * @param value - String with potential whitespace (still TAINTED)
 * @returns String with trimmed whitespace (still TAINTED)
 */
export function cleanWhitespace(value: string): string {
  if (!value) return value;

  // Only cleans whitespace - dangerous chars pass through
  // SQL injection: ' OR '1'='1' --  -> ' OR '1'='1' --
  // XSS: <script>alert(1)</script> -> <script>alert(1)</script>
  // Command injection: ; rm -rf / -> ; rm -rf /
  return value.trim();
}

/**
 * Truncate string to max length.
 *
 * Does NOT sanitize content.
 *
 * @param value - String to truncate (TAINTED)
 * @param maxLength - Maximum length
 * @returns Truncated string (still TAINTED)
 */
export function truncate(value: string, maxLength: number = 255): string {
  if (!value) return value;
  return value.substring(0, maxLength);
}

/**
 * Normalize case.
 *
 * Does NOT sanitize content.
 *
 * @param value - String to normalize (TAINTED)
 * @param toCase - 'lower' or 'upper'
 * @returns Case-normalized string (still TAINTED)
 */
export function normalizeCase(
  value: string,
  toCase: 'lower' | 'upper' = 'lower'
): string {
  if (!value) return value;
  return toCase === 'lower' ? value.toLowerCase() : value.toUpperCase();
}

/**
 * Escape HTML (SAFE VERSION).
 *
 * Used to demonstrate sanitized path detection.
 *
 * @param text - Text to escape
 * @returns Escaped HTML (SAFE)
 */
export function escapeHtml(text: string): string {
  if (!text) return text;

  // SAFE: Proper HTML escaping
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Sanitize for logging (WEAK).
 *
 * @param value - String to sanitize (TAINTED)
 * @returns String with newlines removed (still TAINTED for other attacks)
 */
export function sanitizeForLogging(value: string): string {
  if (!value) return value;
  // Only removes newlines - other dangerous chars pass through
  return value.replace(/\n/g, ' ').replace(/\r/g, ' ');
}
