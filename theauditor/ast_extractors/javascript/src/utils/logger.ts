import pino from "pino";

const LOG_LEVEL_MAP: Record<string, pino.Level> = {
  DEBUG: "debug",
  INFO: "info",
  WARNING: "warn",
  WARN: "warn",
  ERROR: "error",
};

const envLevel = process.env.THEAUDITOR_LOG_LEVEL?.toUpperCase() || "INFO";
const pinoLevel = LOG_LEVEL_MAP[envLevel] || "info";

const requestId = process.env.THEAUDITOR_REQUEST_ID || "unknown";

const baseLogger = pino(
  {
    level: pinoLevel,
  },
  pino.destination(2),
);

export const logger = baseLogger.child({ request_id: requestId });

export default logger;
