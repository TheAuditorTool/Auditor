"""Report model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Report:
    """Report data model."""

    id: int
    title: str
    content: Optional[str] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "user_id": self.user_id,
            "created_at": str(self.created_at) if self.created_at else None,
        }
