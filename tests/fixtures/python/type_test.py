"""Fixture module for verifying Python type hint extraction."""

from typing import Dict, List, Optional, Tuple, Union


def add(x: int, y: int) -> int:
    return x + y


def process(items: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        result[item] = len(item)
    return result


def find_user(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    return f"user-{user_id}"


def parse_payload(payload: str | bytes) -> tuple[str, int]:
    if isinstance(payload, bytes):
        decoded = payload.decode("utf-8")
    else:
        decoded = payload
    return decoded, len(decoded)


def mixed_types(alpha: int, beta, gamma: list[int | str]) -> None:
    del alpha
    del beta
    del gamma
