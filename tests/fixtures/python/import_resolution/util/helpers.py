"""Helper functions shared across modules."""

import time


def now_millis() -> int:
    return int(time.time() * 1000)


def slugify(value: str) -> str:
    return value.strip().replace(" ", "-").lower()
