"""Centralized error handler for TheAuditor commands.

This module provides a decorator that captures detailed error information
including full tracebacks, while presenting clean error messages to users.
All detailed debugging information is logged to .pf/error.log.
"""

import traceback
from collections.abc import Callable
from functools import wraps
from typing import Any

import click

from .constants import ERROR_LOG_FILE, PF_DIR


def handle_exceptions(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that provides robust error handling with detailed logging.

    This decorator:
    1. Catches all exceptions from the wrapped command
    2. Logs full traceback to .pf/error.log for debugging
    3. Shows clean, user-friendly error messages in the console
    4. Points users to the error log for detailed information

    Args:
        func: The Click command function to wrap

    Returns:
        Wrapped function with enhanced error handling
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Inner wrapper that implements the try-except logic."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            PF_DIR.mkdir(parents=True, exist_ok=True)

            error_log_path = ERROR_LOG_FILE

            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 80 + "\n")
                f.write(f"Error in command: {func.__name__}\n")
                f.write("=" * 80 + "\n")

                traceback.print_exc(file=f)
                f.write("=" * 80 + "\n\n")

            error_type = type(e).__name__
            error_msg = str(e)

            user_message = (
                f"{error_type}: {error_msg}\n\n"
                f"Detailed error information has been logged to: {error_log_path}\n"
                f"Please check the log file for the full traceback and debugging information."
            )

            raise click.ClickException(user_message)

    return wrapper
