"""User model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User data model."""

    id: int
    name: str
    email: str
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": str(self.created_at) if self.created_at else None,
        }
