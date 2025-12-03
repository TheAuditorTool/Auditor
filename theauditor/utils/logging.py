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

    # Write to stdout (Pino convention: machine logs to stdout)
    # CRITICAL: Never call logger.* inside a sink - causes infinite recursion
    sys.stdout.write(json.dumps(pino_log) + "\n")
    sys.stdout.flush()


# Human-readable format (no emojis - Windows CP1252 compatibility)
# Note: <level> tag uses loguru's default colors (INFO=white, ERROR=red, etc.)
_human_format = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}:{function}:{line}</cyan> - "
    "<level>{message}</level>"
)

# Custom level colors - make ERROR/WARNING more visible
# This overrides loguru's defaults
logger.level("DEBUG", color="<blue>")
logger.level("INFO", color="<white>")
logger.level("WARNING", color="<yellow>")
logger.level("ERROR", color="<red>")
logger.level("CRITICAL", color="<red><bold>")

# Track the human-mode handler ID so it can be swapped for Rich integration
_human_handler_id: int | None = None

# Console handler - choose format based on JSON mode
if _json_mode:
    logger.add(
        pino_compatible_sink,
        level=_log_level,
        colorize=False,
    )
else:
    _human_handler_id = logger.add(
        sys.stderr,
        level=_log_level,
        format=_human_format,
        colorize=None,  # Auto-detect: colors if TTY, plain if piped
    )

# Optional file handler (always NDJSON for machine parsing)
if _log_file:
    def _file_pino_sink(message):
        """Write Pino-format JSON to the configured log file."""
        record = message.record
        pino_log = {
            "level": PINO_LEVELS.get(record["level"].name, 30),
            "time": int(record["time"].timestamp() * 1000),
            "msg": record["message"],
            "pid": record["process"].id,
            "request_id": record["extra"].get("request_id", _request_id),
        }
        for key, value in record["extra"].items():
            if key not in ("request_id",):
                pino_log[key] = value
        if record["exception"]:
            pino_log["err"] = {
                "type": record["exception"].type.__name__ if record["exception"].type else "Error",
                "message": str(record["exception"].value) if record["exception"].value else "",
            }
        # Write directly to file - never call logger.* inside a sink
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(pino_log) + "\n")

    logger.add(
        _file_pino_sink,
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


def swap_to_rich_sink(rich_sink_fn) -> int | None:
    """Swap stderr handler to a Rich-compatible sink for Live display integration.

    When Rich Live is active, logs to stderr get overwritten by Live's refresh.
    This function removes the stderr handler and adds a custom sink that routes
    logs through Rich's console (which knows how to print above Live displays).

    Args:
        rich_sink_fn: A callable that accepts loguru message objects.
                      Typically renderer.log_message from RichRenderer.

    Returns:
        The new handler ID, or None if in JSON mode (no swap needed).

    Usage:
        # In renderer.start():
        self._loguru_handler_id = swap_to_rich_sink(self.log_message)

        # In renderer.stop():
        restore_stderr_sink(self._loguru_handler_id)
    """
    global _human_handler_id

    # In JSON mode, we don't use stderr for human output - no swap needed
    if _json_mode or _human_handler_id is None:
        return None

    # Remove the stderr handler
    logger.remove(_human_handler_id)
    _human_handler_id = None

    # Add the Rich sink with ANSI color codes preserved
    # Rich's Console.print() can render ANSI escape sequences
    new_handler_id = logger.add(
        rich_sink_fn,
        level=_log_level,
        format=_human_format,
        colorize=True,  # Preserve ANSI codes - Rich handles them
    )

    return new_handler_id


def restore_stderr_sink(rich_handler_id: int | None) -> None:
    """Restore the default stderr handler after Rich Live display ends.

    Args:
        rich_handler_id: The handler ID returned by swap_to_rich_sink().
    """
    global _human_handler_id

    # In JSON mode, nothing to restore
    if _json_mode:
        return

    # Remove the Rich handler if it exists
    if rich_handler_id is not None:
        try:
            logger.remove(rich_handler_id)
        except ValueError:
            pass  # Already removed

    # Restore stderr handler
    _human_handler_id = logger.add(
        sys.stderr,
        level=_log_level,
        format=_human_format,
        colorize=None,  # Auto-detect: colors if TTY, plain if piped
    )


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


__all__ = [
    "logger",
    "configure_file_logging",
    "get_request_id",
    "get_subprocess_env",
    "swap_to_rich_sink",
    "restore_stderr_sink",
]
