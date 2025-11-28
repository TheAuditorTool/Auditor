"""Centralized error handler for TheAuditor commands."""

import traceback
from collections.abc import Callable
from functools import wraps
from typing import Any

import click

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

            raise click.ClickException(user_message) from e

    return wrapper
