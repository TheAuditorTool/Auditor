/**
 * Pino logger for TypeScript extractor.
 *
 * Outputs NDJSON to stderr (preserving stdout for JSON data output).
 * Respects same environment variables as Python (Loguru):
 * - THEAUDITOR_LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default: INFO)
 * - THEAUDITOR_REQUEST_ID: Correlation ID passed from Python orchestrator
 *
 * Format matches Python exactly for unified log viewing:
 * {"level":30,"time":1715629847123,"msg":"...","pid":12345,"request_id":"..."}
 */
import pino from "pino";

// Map env var names to Pino level names
const LOG_LEVEL_MAP: Record<string, pino.Level> = {
  DEBUG: "debug",
  INFO: "info",
  WARNING: "warn",
  WARN: "warn",
  ERROR: "error",
};

// Get level from environment, default to info
const envLevel = process.env.THEAUDITOR_LOG_LEVEL?.toUpperCase() || "INFO";
const pinoLevel = LOG_LEVEL_MAP[envLevel] || "info";

// Get request ID from environment (passed by Python orchestrator)
const requestId = process.env.THEAUDITOR_REQUEST_ID || "unknown";

// Create base logger writing to stderr (stdout reserved for JSON data)
// Using pino.destination for stderr (fd 2)
const baseLogger = pino(
  {
    level: pinoLevel,
    // Pino outputs level as number and time as epoch ms by default
    // msg is also default key - perfect match for our Python sink
  },
  pino.destination(2) // fd 2 = stderr
);

// Create child logger with request_id bound
export const logger = baseLogger.child({ request_id: requestId });

// Re-export for convenience
export default logger;
