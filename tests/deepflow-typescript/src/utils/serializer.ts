/**
 * Serializer - HOP 18: Data serialization.
 *
 * Serializes data for responses. Contains Prototype Pollution vulnerability.
 */

/**
 * Serialize result for response.
 *
 * HOP 18: Final hop before return to client.
 * Does NOT sanitize data.
 *
 * @param data - Data to serialize (may contain TAINTED values)
 * @returns Serialized object (TAINTED values pass through)
 */
export function serializeResult(data: any): any {
  if (data === null || data === undefined) {
    return { result: null };
  }

  if (Array.isArray(data)) {
    return { result: data, count: data.length };
  }

  return { result: data };
}

/**
 * Deep merge objects.
 *
 * PROTOTYPE POLLUTION SINK.
 *
 * @param target - Target object
 * @param source - Source object (TAINTED - may contain __proto__)
 * @returns Merged object
 *
 * VULNERABILITY: Recursive merge without __proto__ check.
 * Payload: {"__proto__": {"polluted": true}}
 */
export function deepMerge(target: any, source: any): any {
  if (!source || typeof source !== 'object') {
    return target;
  }

  for (const key of Object.keys(source)) {
    // VULNERABLE: No check for __proto__ or constructor
    // Attacker can pollute Object prototype
    if (
      typeof source[key] === 'object' &&
      source[key] !== null &&
      !Array.isArray(source[key])
    ) {
      if (!target[key]) {
        target[key] = {};
      }
      deepMerge(target[key], source[key]); // Recursive - PROTOTYPE POLLUTION
    } else {
      target[key] = source[key];
    }
  }

  return target;
}

/**
 * Safe deep merge (no prototype pollution).
 *
 * SAFE VERSION - for comparison.
 *
 * @param target - Target object
 * @param source - Source object
 * @returns Merged object (safe)
 */
export function safeDeepMerge(target: any, source: any): any {
  if (!source || typeof source !== 'object') {
    return target;
  }

  for (const key of Object.keys(source)) {
    // SAFE: Skip dangerous keys
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      continue;
    }

    if (
      typeof source[key] === 'object' &&
      source[key] !== null &&
      !Array.isArray(source[key])
    ) {
      if (!target[key]) {
        target[key] = {};
      }
      safeDeepMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }

  return target;
}

/**
 * Convert to JSON string.
 *
 * @param data - Data to convert (may contain TAINTED values)
 * @returns JSON string
 */
export function toJson(data: any): string {
  return JSON.stringify(data);
}

/**
 * Parse JSON string.
 *
 * @param jsonStr - JSON string (TAINTED)
 * @returns Parsed data (TAINTED)
 */
export function fromJson(jsonStr: string): any {
  return JSON.parse(jsonStr);
}
