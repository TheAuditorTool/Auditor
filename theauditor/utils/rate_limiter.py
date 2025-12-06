"""Async rate limiting utilities for network operations."""

import asyncio
import time

RATE_LIMIT_NPM = 0.05
RATE_LIMIT_PYPI = 0.1
RATE_LIMIT_DOCKER = 0.15
RATE_LIMIT_GITHUB = 0.1
RATE_LIMIT_DOCS = 0.2
RATE_LIMIT_CARGO = 1.0
RATE_LIMIT_GO = 0.5

RATE_LIMIT_BACKOFF = 10

TIMEOUT_FETCH = 10
TIMEOUT_CRAWL = 15
TIMEOUT_PROBE = 5


class AsyncRateLimiter:
    """Lightweight async rate limiter that ensures minimum delay between requests."""

    def __init__(self, delay: float):
        """Args:"""
        self.delay = delay
        self.last_request = 0.0
        self._lock: asyncio.Lock | None = None

    async def acquire(self):
        """Wait until enough time has passed since last request."""

        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            wait = self.delay - elapsed

            if wait > 0:
                await asyncio.sleep(wait)

            self.last_request = time.time()


_rate_limiters: dict[str, AsyncRateLimiter] = {}


def get_rate_limiter(service: str) -> AsyncRateLimiter:
    """Get or create rate limiter for a service."""

    service = service.lower()
    if service == "pypi":
        service = "py"

    if service not in _rate_limiters:
        delays = {
            "npm": RATE_LIMIT_NPM,
            "py": RATE_LIMIT_PYPI,
            "docker": RATE_LIMIT_DOCKER,
            "github": RATE_LIMIT_GITHUB,
            "docs": RATE_LIMIT_DOCS,
            "cargo": RATE_LIMIT_CARGO,
            "go": RATE_LIMIT_GO,
        }
        delay = delays.get(service, RATE_LIMIT_DOCS)
        _rate_limiters[service] = AsyncRateLimiter(delay)

    return _rate_limiters[service]


def reset_rate_limiters():
    """Reset all rate limiters. Useful for testing."""
    global _rate_limiters
    _rate_limiters = {}
