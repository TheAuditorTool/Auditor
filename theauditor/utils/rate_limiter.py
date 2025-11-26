"""Async rate limiting utilities for network operations.

Provides throttled concurrency for API calls to avoid 429 bans while
maintaining good throughput. Used by deps.py and docs_fetch.py.

Key insight: Semaphore limits WIDTH (concurrent requests), RateLimiter
limits SPEED (request frequency). You need both for polite scraping.
"""

import asyncio
import time


# =============================================================================
# RATE LIMIT CONSTANTS - Balanced for speed vs ban risk
# =============================================================================

# Registry-specific delays (seconds between requests)
RATE_LIMIT_NPM = 0.05       # npm: 20 req/sec (tolerant, we back off if needed)
RATE_LIMIT_PYPI = 0.1       # PyPI: 10 req/sec (moderate)
RATE_LIMIT_DOCKER = 0.15    # Docker Hub: ~7 req/sec (pickier)
RATE_LIMIT_GITHUB = 0.1     # GitHub raw: 10 req/sec
RATE_LIMIT_DOCS = 0.2       # Generic doc sites: 5 req/sec (be polite)

# Backoff configuration
RATE_LIMIT_BACKOFF = 10     # Initial backoff on 429 (exponential: 10s, 20s, 40s)
RATE_LIMIT_MAX_RETRIES = 3  # Max retries before giving up

# Timeout configuration
TIMEOUT_PROBE = 2           # HEAD request / existence check
TIMEOUT_FETCH = 10          # Full content fetch
TIMEOUT_CRAWL = 5           # Doc page fetch (shorter, many requests)


class AsyncRateLimiter:
    """
    Lightweight async rate limiter that ensures minimum delay between requests.

    Unlike Semaphore which limits concurrency (width), this limits frequency (speed).
    Uses non-blocking asyncio.sleep so other tasks can run while waiting.

    Usage:
        limiter = AsyncRateLimiter(0.1)  # 10 req/sec
        async with some_semaphore:
            await limiter.acquire()
            # ... make request
    """

    def __init__(self, delay: float):
        """
        Args:
            delay: Minimum seconds between requests (e.g., 0.1 = 10 req/sec)
        """
        self.delay = delay
        self.last_request = 0.0
        self._lock: asyncio.Lock | None = None  # Lazy init to avoid event loop issues

    async def acquire(self):
        """Wait until enough time has passed since last request."""
        # Lazy init lock (must be created in async context)
        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            wait = self.delay - elapsed

            if wait > 0:
                await asyncio.sleep(wait)

            self.last_request = time.time()


# =============================================================================
# LIMITER REGISTRY - Per-service rate limiters
# =============================================================================

_rate_limiters: dict[str, AsyncRateLimiter] = {}


def get_rate_limiter(service: str) -> AsyncRateLimiter:
    """
    Get or create rate limiter for a service.

    Args:
        service: Service name ('npm', 'py', 'pypi', 'docker', 'github', 'docs')

    Returns:
        AsyncRateLimiter configured for that service
    """
    # Normalize service names
    service = service.lower()
    if service == 'pypi':
        service = 'py'

    if service not in _rate_limiters:
        delays = {
            'npm': RATE_LIMIT_NPM,
            'py': RATE_LIMIT_PYPI,
            'docker': RATE_LIMIT_DOCKER,
            'github': RATE_LIMIT_GITHUB,
            'docs': RATE_LIMIT_DOCS,
        }
        delay = delays.get(service, RATE_LIMIT_DOCS)  # Default to polite
        _rate_limiters[service] = AsyncRateLimiter(delay)

    return _rate_limiters[service]


def reset_rate_limiters():
    """Reset all rate limiters. Useful for testing."""
    global _rate_limiters
    _rate_limiters = {}
