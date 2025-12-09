/**
 * Path utilities - HOP 16: Path operations.
 *
 * Provides path manipulation that does NOT prevent path traversal.
 */

import * as path from 'path';
import * as fs from 'fs';

/**
 * Build file path.
 *
 * HOP 16: DOES NOT sanitize path traversal.
 *
 * @param base - Base directory path
 * @param filename - Filename (TAINTED - may contain ..)
 * @returns Combined path (VULNERABLE to path traversal)
 */
export function buildPath(base: string, filename: string): string {
  // VULNERABLE: path.join does NOT prevent path traversal
  // If filename contains .., it can escape base
  // Example: filename = "../../etc/passwd"
  return path.join(base, filename);
}

/**
 * Get file extension.
 *
 * @param filename - Filename (TAINTED)
 * @returns Extension (still part of TAINTED filename)
 */
export function getExtension(filename: string): string {
  if (!filename) return '';
  return path.extname(filename).toLowerCase();
}

/**
 * Normalize path (DOES NOT prevent traversal).
 *
 * @param filePath - Path to normalize (TAINTED)
 * @returns Normalized path (still VULNERABLE)
 */
export function normalizePath(filePath: string): string {
  // WARNING: normalize resolves .. but doesn't prevent traversal
  return path.normalize(filePath);
}

/**
 * Safely join paths (SAFE VERSION).
 *
 * @param base - Base directory (trusted)
 * @param parts - Path parts to join (may be tainted)
 * @returns Safe joined path or throws if traversal detected
 */
export function safeJoin(base: string, ...parts: string[]): string {
  // Join the paths
  const joined = path.join(base, ...parts);

  // Resolve to absolute path
  const resolved = path.resolve(joined);
  const baseResolved = path.resolve(base);

  // SAFE: Check that resolved path starts with base
  if (!resolved.startsWith(baseResolved + path.sep) && resolved !== baseResolved) {
    throw new Error(`Path traversal detected: ${joined}`);
  }

  return resolved;
}

/**
 * Read file (VULNERABLE).
 *
 * @param filePath - TAINTED file path
 */
export function readFile(filePath: string): string {
  // VULNERABLE: Reading from user-controlled path
  return fs.readFileSync(filePath, 'utf-8');
}
