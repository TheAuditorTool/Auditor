"""Fixture module for verifying Python type hint extraction."""

from typing import Dict, List, Optional, Tuple, Union


def add(x: int, y: int) -> int:
    return x + y


def process(items: List[str]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for item in items:
        result[item] = len(item)
    return result


def find_user(user_id: Optional[int]) -> Optional[str]:
    if user_id is None:
        return None
    return f"user-{user_id}"


def parse_payload(payload: Union[str, bytes]) -> Tuple[str, int]:
    if isinstance(payload, bytes):
        decoded = payload.decode("utf-8")
    else:
        decoded = payload
    return decoded, len(decoded)


def mixed_types(alpha: int, beta, gamma: List[Union[int, str]]) -> None:
    del alpha
    del beta
    del gamma
