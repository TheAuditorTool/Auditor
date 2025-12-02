"""Centralized logging configuration using Loguru with Pino-compatible output.

This module provides a unified logging interface that outputs NDJSON compatible
with Pino (Node.js logging library), enabling unified log viewing across
Python and TypeScript components.

Usage:
    from theauditor.utils.logging import logger
    logger.info("Message")
    logger.debug("Debug message")  # Only shows if THEAUDITOR_LOG_LEVEL=DEBUG

Environment Variables:
    THEAUDITOR_LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default: INFO)
    THEAUDITOR_LOG_JSON: 0|1 (default: 0, human-readable)
    THEAUDITOR_LOG_FILE: path to log file (optional)
    THEAUDITOR_REQUEST_ID: correlation ID for cross-language tracing
"""

import json
import os
import sys
import uuid
from pathlib import Path

from loguru import logger

# Remove default handler
logger.remove()

# Pino-compatible numeric levels
PINO_LEVELS = {
    "TRACE": 10,
    "DEBUG": 20,
    "INFO": 30,
    "WARNING": 40,
    "ERROR": 50,
    "CRITICAL": 60,
}

# Get configuration from environment
_log_level = os.environ.get("THEAUDITOR_LOG_LEVEL", "INFO").upper()
_json_mode = os.environ.get("THEAUDITOR_LOG_JSON", "0") == "1"
_log_file = os.environ.get("THEAUDITOR_LOG_FILE")
_request_id = os.environ.get("THEAUDITOR_REQUEST_ID") or str(uuid.uuid4())


def pino_compatible_sink(message):
    """Format log records as Pino-compatible NDJSON.

    Output format matches Pino exactly for unified log viewing:
    {"level":30,"time":1715629847123,"msg":"...","pid":12345,"request_id":"..."}
    """
    record = message.record

    pino_log = {
        "level": PINO_LEVELS.get(record["level"].name, 30),
        "time": int(record["time"].timestamp() * 1000),
        "msg": record["message"],
        "pid": record["process"].id,
        "request_id": record["extra"].get("request_id", _request_id),
    }

    # Add any extra context fields
    for key, value in record["extra"].items():
        if key not in ("request_id",):
            pino_log[key] = value

    # Add exception info if present (Pino err format)
    if record["exception"]:
        pino_log["err"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else "Error",
            "message": str(record["exception"].value) if record["exception"].value else "",
        }

    # Write to stderr (no emojis - Windows CP1252 compatibility)
    logger.error(json.dumps(pino_log))


# Human-readable format (no emojis - Windows CP1252 compatibility)
_human_format = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# Console handler - choose format based on JSON mode
if _json_mode:
    logger.add(
        pino_compatible_sink,
        level=_log_level,
        colorize=False,
    )
else:
    logger.add(
        sys.stderr,
        level=_log_level,
        format=_human_format,
        colorize=True,
    )

# Optional file handler (always NDJSON for machine parsing)
if _log_file:
    logger.add(
        pino_compatible_sink,
        level="DEBUG",  # File always captures everything
    )


def configure_file_logging(log_dir: Path, level: str = "DEBUG") -> None:
    """Add rotating file handler for persistent logs.

    Args:
        log_dir: Directory for log files (e.g., Path(".pf"))
        level: Minimum log level for file output
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "theauditor.log"

    # File logging uses human-readable format (for manual inspection)
    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


def get_request_id() -> str:
    """Get the current request ID for correlation."""
    return _request_id


def get_subprocess_env() -> dict:
    """Get environment dict with REQUEST_ID for subprocess calls.

    Use this when spawning TypeScript extractor or other subprocesses
    to maintain log correlation.

    Example:
        env = get_subprocess_env()
        subprocess.run(["node", "extractor.js"], env=env)
    """
    env = os.environ.copy()
    env["THEAUDITOR_REQUEST_ID"] = _request_id
    return env


__all__ = ["logger", "configure_file_logging", "get_request_id", "get_subprocess_env"]
