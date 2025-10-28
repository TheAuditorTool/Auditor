"""Utility service that records outbound email events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class SupportEmailService:
    """Collects messages so the taint engine can follow data flows."""

    default_sender: str
    _outbox: List[dict] = field(default_factory=list)

    def enqueue_welcome(self, recipient: str) -> None:
        self._outbox.append({"type": "welcome", "recipient": recipient, "sender": self.default_sender})

    def enqueue_password_reset(self, recipient: str) -> None:
        self._outbox.append({"type": "password_reset", "recipient": recipient, "sender": self.default_sender})

    def pending(self) -> List[dict]:
        return list(self._outbox)
