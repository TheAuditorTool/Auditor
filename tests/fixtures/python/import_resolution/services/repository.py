"""Repository stub used by UserService."""

from typing import Any, Dict


class UserRepository:
    def __init__(self) -> None:
        self._records: list[Dict[str, Any]] = []

    def save(self, record: Dict[str, Any]) -> None:
        self._records.append(record)

    def all(self) -> list[Dict[str, Any]]:
        return list(self._records)
