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

# Export all public utility functions for easy import
from theauditor.rules.common.util import (
    # Entropy calculation
    calculate_entropy,
    EntropyCalculator,
    EntropyLevel,

    # Pattern detection
    is_sequential,
    is_keyboard_walk,
    PatternDetector,

    # Encoding validation
    decode_and_verify_base64,
    Base64Validator,

    # Configuration
    PatternConfig,
    KeyboardPatterns,
    PATTERN_CONFIG,
    KEYBOARD_CONFIG,
)

__all__ = [
    # Functions (backward compatibility API)
    'calculate_entropy',
    'is_sequential',
    'is_keyboard_walk',
    'decode_and_verify_base64',

    # Classes (modern API)
    'EntropyCalculator',
    'EntropyLevel',
    'PatternDetector',
    'Base64Validator',

    # Configuration
    'PatternConfig',
    'KeyboardPatterns',
    'PATTERN_CONFIG',
    'KEYBOARD_CONFIG',
]
