"""Common utility functions for security rules.

This package provides computational utilities used across security rules:
- Entropy calculation (Shannon entropy for randomness measurement)
- Pattern detection (sequential, keyboard walks, repetitive patterns)
- Encoding validation (Base64 decoding and verification)
- Test value detection (placeholder/test string identification)

These are UTILITY functions, not security rules. They provide pure
computational analysis without database access.

Module Type: Utility Package
Usage: from theauditor.rules.common.util import calculate_entropy
"""

from theauditor.rules.common.util import (
    KEYBOARD_CONFIG,
    PATTERN_CONFIG,
    Base64Validator,
    EntropyCalculator,
    EntropyLevel,
    KeyboardPatterns,
    PatternConfig,
    PatternDetector,
    calculate_entropy,
    decode_and_verify_base64,
    is_keyboard_walk,
    is_sequential,
)

__all__ = [
    "calculate_entropy",
    "is_sequential",
    "is_keyboard_walk",
    "decode_and_verify_base64",
    "EntropyCalculator",
    "EntropyLevel",
    "PatternDetector",
    "Base64Validator",
    "PatternConfig",
    "KeyboardPatterns",
    "PATTERN_CONFIG",
    "KEYBOARD_CONFIG",
]
