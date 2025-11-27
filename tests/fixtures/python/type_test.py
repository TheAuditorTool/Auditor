"""Fixture module for verifying Python type hint extraction."""



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
    decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    return decoded, len(decoded)


def mixed_types(alpha: int, beta, gamma: list[int | str]) -> None:
    del alpha
    del beta
    del gamma
