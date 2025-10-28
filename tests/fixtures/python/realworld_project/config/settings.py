"""Typed configuration module to feed import resolution and annotations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping


@dataclass(frozen=True)
class EmailSettings:
    sender: str
    retries: int = 3


DEFAULT_EMAIL_SETTINGS: Final[EmailSettings] = EmailSettings(sender="noreply@example.com")


def runtime_flags() -> Mapping[str, bool]:
    """Expose typed mapping so type annotation extraction sees Dict[str, bool]."""

    return {"enable_audit_stream": True, "legacy_mode": False}
