"""Pydantic fixture exercising validators and nested models."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, root_validator, validator


class Address(BaseModel):
    street: str = Field(min_length=3)
    city: str
    postal_code: str

    @validator("postal_code")
    def postal_code_length(cls, value: str) -> str:
        if len(value) != 5 or not value.isdigit():
            raise ValueError("postal code must be 5 digits")
        return value


class UserSettings(BaseModel):
    newsletter_opt_in: bool = False
    timezone: str = "UTC"

    @validator("timezone")
    def timezone_not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("timezone required")
        return value


class UserPayload(BaseModel):
    email: str
    password: str
    password_confirm: str
    roles: List[str] = Field(default_factory=list)
    settings: UserSettings = UserSettings()
    created_at: Optional[datetime] = None
    address: Optional[Address] = None

    @validator("email")
    def email_must_have_at(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("invalid email")
        return value

    @root_validator
    def passwords_match(cls, values):
        if values.get("password") != values.get("password_confirm"):
            raise ValueError("password mismatch")
        return values


class BulkInvite(BaseModel):
    emails: List[str]
    invite_message: Optional[str] = None

    @validator("emails")
    def emails_not_empty(cls, values: List[str]) -> List[str]:
        if not values:
            raise ValueError("at least one email required")
        return values
