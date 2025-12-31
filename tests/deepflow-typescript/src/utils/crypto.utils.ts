/**
 * Crypto utilities - HOP 17: Cryptographic operations.
 *
 * Provides hashing and encryption utilities.
 */

import * as crypto from 'crypto';

/**
 * Hash a value.
 *
 * @param value - Value to hash (TAINTED passes through hash)
 * @returns Hash of value
 */
export function hash(value: string): string {
  return crypto.createHash('sha256').update(value).digest('hex');
}

/**
 * Generate random token.
 *
 * @returns Random token
 */
export function generateToken(): string {
  return crypto.randomBytes(32).toString('hex');
}

/**
 * Compare hashes (timing-safe).
 *
 * @param a - First hash
 * @param b - Second hash
 * @returns True if equal
 */
export function compareHashes(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}
