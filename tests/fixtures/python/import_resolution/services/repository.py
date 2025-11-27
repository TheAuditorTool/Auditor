"""Repository stub used by UserService."""

from typing import Any


class UserRepository:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def save(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def all(self) -> list[dict[str, Any]]:
        return list(self._records)
