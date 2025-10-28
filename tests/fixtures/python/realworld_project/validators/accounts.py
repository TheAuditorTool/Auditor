"""Pydantic models that exercise field and root validators."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, root_validator, validator


class AccountPayload(BaseModel):
    email: EmailStr
    organization_id: int
    timezone: str = Field(default="UTC", description="IANA timezone string")
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("timezone")
    def timezone_supported(cls, value: str) -> str:
        if not value:
            raise ValueError("timezone required")
        if value not in {"UTC", "US/Pacific", "US/Eastern"}:
            raise ValueError("unsupported timezone")
        return value

    @root_validator
    def title_matches_role(cls, values: dict) -> dict:
        title = values.get("title")
        if title and len(title) < 3:
            raise ValueError("title too short")
        return values


class AccountResponse(BaseModel):
    id: int
    email: EmailStr
    organization_id: int
    timezone: str
    title: Optional[str]
