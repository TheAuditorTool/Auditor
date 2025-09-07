"""Centralized error handler for TheAuditor commands.

This module provides a decorator that captures detailed error information
including full tracebacks, while presenting clean error messages to users.
All detailed debugging information is logged to .pf/error.log.
"""

import click
import traceback
from functools import wraps
from pathlib import Path


def handle_exceptions(func):
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
    def wrapper(*args, **kwargs):
        """Inner wrapper that implements the try-except logic."""
        try:
            # Execute the original command
            return func(*args, **kwargs)
        except Exception as e:
            # Step 1: Ensure log directory exists
            log_dir = Path("./.pf")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Step 2: Define error log path
            error_log_path = log_dir / "error.log"
            
            # Step 3: Write detailed traceback to log file
            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 80 + "\n")
                f.write(f"Error in command: {func.__name__}\n")
                f.write("=" * 80 + "\n")
                # Write the full traceback with all details
                traceback.print_exc(file=f)
                f.write("=" * 80 + "\n\n")
            
            # Step 4: Construct user-friendly error message
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Create informative but clean error message
            user_message = (
                f"{error_type}: {error_msg}\n\n"
                f"Detailed error information has been logged to: {error_log_path}\n"
                f"Please check the log file for the full traceback and debugging information."
            )
            
            # Step 5: Raise clean Click exception for user
            raise click.ClickException(user_message)
    
    return wrapper