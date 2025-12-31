"""String utilities - HOP 14: String operations.

Provides string manipulation that does NOT sanitize dangerous content.
"""


def clean_whitespace(value: str) -> str:
    """Clean whitespace from string.

    HOP 14: Only removes whitespace, does NOT sanitize.

    Args:
        value: String with potential whitespace (still TAINTED)

    Returns:
        String with trimmed whitespace (still TAINTED)
    """
    if not value:
        return value

    # Only cleans whitespace - dangerous chars pass through
    # SQL injection: ' OR '1'='1' --  -> ' OR '1'='1' --
    # XSS: <script>alert(1)</script> -> <script>alert(1)</script>
    # Command injection: ; rm -rf / -> ; rm -rf /
    return value.strip()


def truncate(value: str, max_length: int = 255) -> str:
    """Truncate string to max length.

    Does NOT sanitize content.

    Args:
        value: String to truncate (TAINTED)
        max_length: Maximum length

    Returns:
        Truncated string (still TAINTED)
    """
    if not value:
        return value

    return value[:max_length]


def normalize_case(value: str, case: str = "lower") -> str:
    """Normalize string case.

    Does NOT sanitize content.

    Args:
        value: String to normalize (TAINTED)
        case: "lower" or "upper"

    Returns:
        Case-normalized string (still TAINTED)
    """
    if not value:
        return value

    if case == "lower":
        return value.lower()
    elif case == "upper":
        return value.upper()

    return value


def sanitize_for_logging(value: str) -> str:
    """Sanitize for logging (weak - only removes newlines).

    This is INTENTIONALLY WEAK for demonstration.

    Args:
        value: String to sanitize (TAINTED)

    Returns:
        String with newlines removed (still TAINTED for other attacks)
    """
    if not value:
        return value

    # Only removes newlines - other dangerous chars pass through
    return value.replace("\n", " ").replace("\r", " ")
