"""Security Analysis Utility Library."""

import base64
import binascii
import math
from dataclasses import dataclass
from enum import Enum


class EntropyLevel(Enum):
    """Entropy thresholds for different content types."""

    VERY_LOW = 2.0
    LOW = 2.5
    MEDIUM = 3.0
    HIGH = 4.0
    VERY_HIGH = 5.0


@dataclass(frozen=True)
class PatternConfig:
    """Configuration for pattern detection."""

    MIN_SEQUENTIAL_LENGTH = 3

    MAX_REPETITION_RATIO = 0.9

    MAX_TEST_VALUE_LENGTH = 30

    TEST_VALUES = frozenset(
        [
            "test",
            "testing",
            "example",
            "sample",
            "demo",
            "password",
            "secret",
            "admin",
            "root",
            "user",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "placeholder",
            "changeme",
            "your_password_here",
            "aaaa",
            "bbbb",
            "xxxx",
            "0000",
            "1111",
            "1234",
        ]
    )


@dataclass(frozen=True)
class KeyboardPatterns:
    """Keyboard walk patterns for QWERTY layout."""

    ROW_PATTERNS = {
        "top": ["qwertyuiop", "qwertyuio", "qwertyui", "qwertyu", "qwerty", "qwert"],
        "home": ["asdfghjkl", "asdfghjk", "asdfghj", "asdfgh", "asdfg", "asdf"],
        "bottom": ["zxcvbnm", "zxcvbn", "zxcvb", "zxcv"],
        "numbers": [
            "1234567890",
            "123456789",
            "12345678",
            "1234567",
            "123456",
            "12345",
            "1234",
            "123",
        ],
    }

    DIAGONAL_PATTERNS = frozenset(
        [
            "1qaz2wsx3edc",
            "1qaz2wsx",
            "1qaz",
            "2wsx",
            "3edc",
            "zaq1xsw2cde3",
            "zaq1xsw2",
            "zaq1",
            "xsw2",
            "cde3",
            "!qaz@wsx",
            "!qaz",
            "@wsx",
        ]
    )

    @classmethod
    def get_all_patterns(cls) -> set[str]:
        """Get all keyboard walk patterns including reverses."""
        patterns = set()

        for row_patterns in cls.ROW_PATTERNS.values():
            patterns.update(row_patterns)

        for row_patterns in cls.ROW_PATTERNS.values():
            patterns.update(p[::-1] for p in row_patterns)

        patterns.update(cls.DIAGONAL_PATTERNS)

        return patterns


PATTERN_CONFIG = PatternConfig()
KEYBOARD_CONFIG = KeyboardPatterns()


class EntropyCalculator:
    """Shannon entropy calculator for randomness measurement."""

    @staticmethod
    def calculate(text: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not text:
            return 0.0

        char_frequencies = EntropyCalculator._get_character_frequencies(text)

        entropy = 0.0
        text_len = len(text)

        for count in char_frequencies.values():
            probability = count / text_len
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    @staticmethod
    def _get_character_frequencies(text: str) -> dict[str, int]:
        """Get frequency count of each character."""
        frequencies: dict[str, int] = {}
        for char in text:
            frequencies[char] = frequencies.get(char, 0) + 1
        return frequencies

    @staticmethod
    def classify_entropy(entropy: float) -> EntropyLevel:
        """Classify entropy into meaningful categories."""
        if entropy < EntropyLevel.VERY_LOW.value:
            return EntropyLevel.VERY_LOW
        elif entropy < EntropyLevel.LOW.value:
            return EntropyLevel.LOW
        elif entropy < EntropyLevel.MEDIUM.value:
            return EntropyLevel.MEDIUM
        elif entropy < EntropyLevel.HIGH.value:
            return EntropyLevel.HIGH
        else:
            return EntropyLevel.VERY_HIGH


class PatternDetector:
    """Detector for common weak password patterns."""

    @staticmethod
    def is_sequential(text: str) -> bool:
        """Check if string follows a sequential pattern."""
        if len(text) < PATTERN_CONFIG.MIN_SEQUENTIAL_LENGTH:
            return False

        differences = PatternDetector._get_character_differences(text)

        unique_differences = set(differences)
        if len(unique_differences) == 1:
            return differences[0] in [1, -1]

        return False

    @staticmethod
    def _get_character_differences(text: str) -> list[int]:
        """Get ASCII differences between adjacent characters."""
        return [ord(text[i]) - ord(text[i - 1]) for i in range(1, len(text))]

    @staticmethod
    def is_keyboard_walk(text: str) -> bool:
        """Check if string matches keyboard walk patterns."""
        text_lower = text.lower()
        all_patterns = KEYBOARD_CONFIG.get_all_patterns()

        return any(pattern in text_lower or text_lower in pattern for pattern in all_patterns)

    @staticmethod
    def is_repetitive(text: str) -> bool:
        """Check if string is highly repetitive."""
        if not text:
            return False

        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1

        max_count = max(char_counts.values())
        return (max_count / len(text)) > PATTERN_CONFIG.MAX_REPETITION_RATIO

    @staticmethod
    def is_test_value(text: str) -> bool:
        """Check if string is a common test/placeholder value."""
        if len(text) > PATTERN_CONFIG.MAX_TEST_VALUE_LENGTH:
            return False

        text_lower = text.lower()
        return any(test_val in text_lower for test_val in PATTERN_CONFIG.TEST_VALUES)


class Base64Validator:
    """Validator for Base64 encoded secrets."""

    @staticmethod
    def decode_and_verify(value: str) -> bool:
        """Decode Base64 and verify if content is secret-like."""
        decoded_content = Base64Validator._decode_base64(value)
        if decoded_content is None:
            return False

        if isinstance(decoded_content, bytes):
            hex_entropy = EntropyCalculator.calculate(decoded_content.hex())
            return hex_entropy > EntropyLevel.MEDIUM.value

        return Base64Validator._is_secret_like(decoded_content)

    @staticmethod
    def _decode_base64(value: str) -> str | bytes | None:
        """Attempt to decode Base64 string."""
        try:
            decoded_bytes = base64.b64decode(value, validate=True)

            try:
                return decoded_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return decoded_bytes

        except (binascii.Error, ValueError):
            return None

    @staticmethod
    def _is_secret_like(text: str) -> bool:
        """Check if decoded text appears to be a secret."""

        if PatternDetector.is_sequential(text):
            return False

        if PatternDetector.is_keyboard_walk(text):
            return False

        if PatternDetector.is_repetitive(text):
            return False

        if PatternDetector.is_test_value(text):
            return False

        entropy = EntropyCalculator.calculate(text)
        entropy_level = EntropyCalculator.classify_entropy(entropy)

        return entropy_level not in [EntropyLevel.VERY_LOW, EntropyLevel.LOW]


def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string."""
    return EntropyCalculator.calculate(text)


def is_sequential(text: str) -> bool:
    """Check if string follows a sequential pattern."""
    return PatternDetector.is_sequential(text)


def is_keyboard_walk(text: str) -> bool:
    """Check if string matches keyboard walk patterns."""
    return PatternDetector.is_keyboard_walk(text)


def decode_and_verify_base64(value: str) -> bool:
    """Decode Base64 and verify if content is secret-like."""
    return Base64Validator.decode_and_verify(value)
