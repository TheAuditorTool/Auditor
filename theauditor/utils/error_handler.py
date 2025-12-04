"""Centralized error handler for TheAuditor commands."""

import traceback
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any

import click

from theauditor.utils.logging import logger

from .constants import ERROR_LOG_FILE, PF_DIR


def handle_exceptions(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that provides robust error handling with detailed logging."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Inner wrapper that implements the try-except logic."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            PF_DIR.mkdir(parents=True, exist_ok=True)

            error_log_path = ERROR_LOG_FILE
            error_type = type(e).__name__
            error_msg = str(e)
            tb = traceback.format_exc()

            # Log via loguru for console/Rich/Pino-NDJSON output
            logger.opt(exception=True).error(
                "Command '{cmd}' failed: {err}",
                cmd=func.__name__,
                err=error_msg,
            )

            # Also write to error.log file for persistent debugging
            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 80 + "\n")
                f.write(f"[{datetime.now().isoformat()}] Error in command: {func.__name__}\n")
                f.write("=" * 80 + "\n")
                f.write(f"{error_type}: {error_msg}\n\n")
                f.write(tb)
                f.write("=" * 80 + "\n\n")

            user_message = (
                f"{error_type}: {error_msg}\n\n"
                f"Full traceback logged to: {error_log_path}"
            )

            raise click.ClickException(user_message) from e

    return wrapper
