"""Dependency helpers referenced by FastAPI routes."""


from collections.abc import Generator

from ..repositories.accounts import AccountRepository
from ..services.emails import SupportEmailService


class _InMemorySession:
    """Lightweight stand-in for a SQLAlchemy session."""

    def __init__(self) -> None:
        self._closed = False

    def close(self) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed


def get_db() -> Generator[_InMemorySession]:
    """Yield a fake session so dependency graphs see a database handle."""

    session = _InMemorySession()
    try:
        yield session
    finally:
        session.close()


def get_repository() -> AccountRepository:
    """Return a repository wired with the in-memory session."""

    return AccountRepository(session=_InMemorySession())


def get_email_service() -> SupportEmailService:
    """Provide a support email service for dependency injection."""

    return SupportEmailService(default_sender="support@example.com")
