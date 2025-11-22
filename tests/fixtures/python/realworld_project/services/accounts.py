"""Business logic that coordinates repositories, validators, and email service."""


from typing import List

from collections.abc import Iterable

from ..config.settings import DEFAULT_EMAIL_SETTINGS
from ..models.accounts import Profile, User
from ..models.audit import AuditLog
from ..repositories.accounts import AccountRepository, _StoredAccount
from ..validators.accounts import AccountPayload, AccountResponse
from .emails import SupportEmailService


class AccountService:
    """Provides higher-level orchestration for account management."""

    def __init__(self, repository: AccountRepository, email_service: SupportEmailService) -> None:
        self.repository = repository
        self.email_service = email_service
        if not self.email_service.default_sender:
            self.email_service.default_sender = DEFAULT_EMAIL_SETTINGS.sender

    def register_account(self, payload: AccountPayload) -> User:
        """Create an account, profile, audit entry, and welcome notification."""

        user = self.repository.create_account(email=payload.email, organization_id=payload.organization_id)
        profile = Profile(user_id=user.id, timezone=payload.timezone, title=payload.title)
        self.repository.save_profile(user.id, profile)
        self.repository.log_event(AuditLog(actor_id=user.id, event_type="account.created", context=payload.email))
        self.email_service.enqueue_welcome(payload.email)
        return user

    def fetch_account(self, account_id: int) -> _StoredAccount:
        stored = self.repository.get_account(account_id)
        if stored is None:
            raise KeyError(f"account {account_id} not found")
        return stored

    def list_accounts(self) -> Iterable[_StoredAccount]:
        return self.repository.list_accounts()

    def serialize_account(self, stored: _StoredAccount) -> AccountResponse:
        """Convert an in-memory record to a Pydantic response model."""

        profile = stored.profile
        return AccountResponse(
            id=stored.user.id,
            email=stored.user.email,
            organization_id=stored.organization.id,
            timezone=profile.timezone if profile else "UTC",
            title=profile.title if profile else None,
        )

    def stream_audit_events(self, limit: int = 10) -> list[AuditLog]:
        return self.repository.recent_events(limit=limit)
