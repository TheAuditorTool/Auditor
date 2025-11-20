"""In-memory repository used to emulate database interactions."""


from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from collections.abc import Iterable

from ..models.accounts import Organization, Profile, User
from ..models.audit import AuditLog


@dataclass
class _StoredAccount:
    """Lightweight projection used for deterministic fixture data."""

    user: User
    organization: Organization
    profile: Profile | None


class AccountRepository:
    """Acts like a minimal ORM repository so extraction sees real patterns."""

    def __init__(self, session: object) -> None:
        self.session = session
        self._accounts: dict[int, _StoredAccount] = {}
        self._audit_log: list[AuditLog] = []
        self._id_seq = 1

    def create_account(self, email: str, organization_id: int) -> User:
        organization = Organization(id=organization_id, name="Fixture Org", slug="fixture-org")
        user = User(id=self._id_seq, organization_id=organization_id, email=email, organization=organization)
        self._accounts[user.id] = _StoredAccount(user=user, organization=organization, profile=None)
        self._id_seq += 1
        return user

    def list_accounts(self) -> Iterable[_StoredAccount]:
        return self._accounts.values()

    def get_account(self, account_id: int) -> _StoredAccount | None:
        return self._accounts.get(account_id)

    def save_profile(self, account_id: int, profile: Profile) -> None:
        if account_id in self._accounts:
            stored = self._accounts[account_id]
            stored.profile = profile
            self._accounts[account_id] = stored

    def log_event(self, entry: AuditLog) -> None:
        self._audit_log.append(entry)

    def recent_events(self, limit: int = 10) -> list[AuditLog]:
        return list(self._audit_log)[-limit:]

    def serialize_accounts(self) -> list[dict]:
        payloads: list[dict] = []
        for stored in self._accounts.values():
            record = asdict(stored.user)
            record["organization"] = asdict(stored.organization)
            if stored.profile:
                record["profile"] = asdict(stored.profile)
            payloads.append(record)
        return payloads
