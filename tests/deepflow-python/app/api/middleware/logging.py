"""Logging middleware - Additional HOP in the chain.

Logs requests but does not sanitize tainted data.
"""

import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def log_request(func: Callable) -> Callable:
    """Log request decorator.

    Logs the function call but passes all parameters through unchanged.
    Tainted data is logged (potential log injection) but not sanitized.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Log the call - tainted data may appear in logs
        logger.info(f"Calling {func.__name__} with kwargs: {kwargs}")

        result = await func(*args, **kwargs)

        logger.info(f"Completed {func.__name__}")
        return result

    return wrapper
