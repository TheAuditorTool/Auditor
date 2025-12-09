"""Serializers - HOP 16: Data serialization.

Serializes data for responses without sanitization.
"""

import json
from typing import Any


def serialize_result(data: Any) -> dict:
    """Serialize result for response.

    HOP 16: Final hop before return to client.
    Does NOT sanitize data.

    Args:
        data: Data to serialize (may contain TAINTED values)

    Returns:
        Serialized dict (TAINTED values pass through)
    """
    if data is None:
        return {"result": None}

    if isinstance(data, dict):
        return {"result": data}

    if isinstance(data, list):
        return {"result": data, "count": len(data)}

    return {"result": data}


def to_json(data: Any) -> str:
    """Convert to JSON string.

    Args:
        data: Data to convert (may contain TAINTED values)

    Returns:
        JSON string (TAINTED values in output)
    """
    return json.dumps(data, default=str)


def from_json(json_str: str) -> Any:
    """Parse JSON string.

    Args:
        json_str: JSON string (TAINTED)

    Returns:
        Parsed data (TAINTED)
    """
    return json.loads(json_str)


def serialize_for_log(data: Any) -> str:
    """Serialize for logging.

    Args:
        data: Data to serialize (may contain TAINTED values)

    Returns:
        String representation (TAINTED values visible in logs)
    """
    try:
        return json.dumps(data, default=str, indent=2)
    except Exception:
        return str(data)


def sanitized_serialize(data: Any) -> dict:
    """Serialize with sanitization (SAFE VERSION).

    Used to demonstrate sanitized path detection.

    Args:
        data: Data to serialize

    Returns:
        Sanitized serialized data
    """
    import html

    def sanitize_value(v: Any) -> Any:
        if isinstance(v, str):
            return html.escape(v)
        if isinstance(v, dict):
            return {k: sanitize_value(val) for k, val in v.items()}
        if isinstance(v, list):
            return [sanitize_value(item) for item in v]
        return v

    return {"result": sanitize_value(data)}
