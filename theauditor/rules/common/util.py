"""Security Analysis Utility Library.

Common utility functions for security pattern detection and analysis.
Provides entropy calculation, pattern recognition, and encoding validation.

IMPORTANT: This is a UTILITY MODULE, not a security rule.
- Does NOT query the database
- Does NOT implement StandardRuleContext interface
- Provides pure computational functions for other rules to use

These functions analyze strings/patterns algorithmically and don't need
database access. They're used by security rules to analyze data that
the rules have already extracted from the database.

Module Type: Utility Library (no rule interface required)
Status: No refactor needed - correct as-is
"""

import base64
import binascii
import math
from typing import Optional, Dict, Set
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

class EntropyLevel(Enum):
    """Entropy thresholds for different content types."""
    VERY_LOW = 2.0   # Highly repetitive/predictable
    LOW = 2.5        # Simple patterns
    MEDIUM = 3.0     # Natural language
    HIGH = 4.0       # Random-looking content
    VERY_HIGH = 5.0  # Cryptographic quality


@dataclass(frozen=True)
class PatternConfig:
    """Configuration for pattern detection."""
    
    # Minimum length for sequential detection
    MIN_SEQUENTIAL_LENGTH = 3
    
    # Maximum repetition ratio before considering content invalid
    MAX_REPETITION_RATIO = 0.9
    
    # Maximum length for test value checking
    MAX_TEST_VALUE_LENGTH = 30
    
    # Common test/placeholder values
    TEST_VALUES = frozenset([
        'test', 'testing', 'example', 'sample', 'demo',
        'password', 'secret', 'admin', 'root', 'user',
        'localhost', '127.0.0.1', '0.0.0.0',
        'placeholder', 'changeme', 'your_password_here',
        'aaaa', 'bbbb', 'xxxx', '0000', '1111', '1234'
    ])


@dataclass(frozen=True)
class KeyboardPatterns:
    """Keyboard walk patterns for QWERTY layout."""
    
    # Horizontal row patterns
    ROW_PATTERNS = {
        'top': ['qwertyuiop', 'qwertyuio', 'qwertyui', 'qwertyu', 'qwerty', 'qwert'],
        'home': ['asdfghjkl', 'asdfghjk', 'asdfghj', 'asdfgh', 'asdfg', 'asdf'],
        'bottom': ['zxcvbnm', 'zxcvbn', 'zxcvb', 'zxcv'],
        'numbers': ['1234567890', '123456789', '12345678', '1234567', '123456', '12345', '1234', '123']
    }
    
    # Reverse patterns (automatically generated from ROW_PATTERNS)
    
    # Diagonal/vertical patterns
    DIAGONAL_PATTERNS = frozenset([
        '1qaz2wsx3edc', '1qaz2wsx', '1qaz', '2wsx', '3edc',
        'zaq1xsw2cde3', 'zaq1xsw2', 'zaq1', 'xsw2', 'cde3',
        '!qaz@wsx', '!qaz', '@wsx'
    ])
    
    @classmethod
    def get_all_patterns(cls) -> Set[str]:
        """Get all keyboard walk patterns including reverses."""
        patterns = set()
        
        # Add forward patterns
        for row_patterns in cls.ROW_PATTERNS.values():
            patterns.update(row_patterns)
        
        # Add reverse patterns
        for row_patterns in cls.ROW_PATTERNS.values():
            patterns.update(p[::-1] for p in row_patterns)
        
        # Add diagonal patterns
        patterns.update(cls.DIAGONAL_PATTERNS)
        
        return patterns


# Initialize configurations
PATTERN_CONFIG = PatternConfig()
KEYBOARD_CONFIG = KeyboardPatterns()


# ============================================================================
# ENTROPY CALCULATION
# ============================================================================

class EntropyCalculator:
    """Shannon entropy calculator for randomness measurement."""
    
    @staticmethod
    def calculate(text: str) -> float:
        """Calculate Shannon entropy of a string.
        
        High entropy (>4.0) typically indicates random strings like API keys.
        Low entropy (<3.0) typically indicates natural language or simple patterns.
        
        Args:
            text: String to analyze
            
        Returns:
            Shannon entropy value (0.0 for empty strings)
        """
        if not text:
            return 0.0
        
        # Count character frequencies
        char_frequencies = EntropyCalculator._get_character_frequencies(text)
        
        # Calculate entropy using Shannon's formula
        entropy = 0.0
        text_len = len(text)
        
        for count in char_frequencies.values():
            probability = count / text_len
            if probability > 0:
                entropy -= probability * math.log2(probability)
        
        return entropy
    
    @staticmethod
    def _get_character_frequencies(text: str) -> Dict[str, int]:
        """Get frequency count of each character."""
        frequencies: Dict[str, int] = {}
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


# ============================================================================
# PATTERN DETECTION
# ============================================================================

class PatternDetector:
    """Detector for common weak password patterns."""
    
    @staticmethod
    def is_sequential(text: str) -> bool:
        """Check if string follows a sequential pattern.
        
        Examples:
        - "abcdef" -> True (incrementing)
        - "987654" -> True (decrementing)
        - "zyxwvu" -> True (decrementing)
        - "abc123" -> False (mixed)
        
        Args:
            text: String to analyze
            
        Returns:
            True if text follows consistent sequential pattern
        """
        if len(text) < PATTERN_CONFIG.MIN_SEQUENTIAL_LENGTH:
            return False
        
        # Calculate differences between adjacent characters
        differences = PatternDetector._get_character_differences(text)
        
        # Check for consistent increment/decrement
        unique_differences = set(differences)
        if len(unique_differences) == 1:
            # Common sequential patterns have difference of ±1
            return differences[0] in [1, -1]
        
        return False
    
    @staticmethod
    def _get_character_differences(text: str) -> list[int]:
        """Get ASCII differences between adjacent characters."""
        return [ord(text[i]) - ord(text[i-1]) for i in range(1, len(text))]
    
    @staticmethod
    def is_keyboard_walk(text: str) -> bool:
        """Check if string matches keyboard walk patterns.
        
        Keyboard walks are patterns formed by adjacent keys on QWERTY keyboard.
        
        Examples:
        - "qwerty" -> True
        - "asdfgh" -> True
        - "1qaz2wsx" -> True
        
        Args:
            text: String to analyze
            
        Returns:
            True if text matches known keyboard walk pattern
        """
        text_lower = text.lower()
        all_patterns = KEYBOARD_CONFIG.get_all_patterns()
        
        # Check if text is contained in or contains any pattern
        for pattern in all_patterns:
            if pattern in text_lower or text_lower in pattern:
                return True
        
        return False
    
    @staticmethod
    def is_repetitive(text: str) -> bool:
        """Check if string is highly repetitive.
        
        Args:
            text: String to analyze
            
        Returns:
            True if any character makes up >90% of the string
        """
        if not text:
            return False
        
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        max_count = max(char_counts.values())
        return (max_count / len(text)) > PATTERN_CONFIG.MAX_REPETITION_RATIO
    
    @staticmethod
    def is_test_value(text: str) -> bool:
        """Check if string is a common test/placeholder value.
        
        Args:
            text: String to analyze
            
        Returns:
            True if text contains common test values
        """
        if len(text) > PATTERN_CONFIG.MAX_TEST_VALUE_LENGTH:
            return False
        
        text_lower = text.lower()
        return any(test_val in text_lower for test_val in PATTERN_CONFIG.TEST_VALUES)


# ============================================================================
# ENCODING VALIDATION
# ============================================================================

class Base64Validator:
    """Validator for Base64 encoded secrets."""
    
    @staticmethod
    def decode_and_verify(value: str) -> bool:
        """Decode Base64 and verify if content is secret-like.
        
        Args:
            value: String that matches Base64 pattern
            
        Returns:
            True if valid Base64 encoding of secret-like content,
            False if false positive (sequential, low entropy, etc.)
        """
        decoded_content = Base64Validator._decode_base64(value)
        if decoded_content is None:
            return False
        
        # Analyze decoded content
        if isinstance(decoded_content, bytes):
            # Binary data - check hex representation entropy
            hex_entropy = EntropyCalculator.calculate(decoded_content.hex())
            return hex_entropy > EntropyLevel.MEDIUM.value
        
        # Text content - run full analysis
        return Base64Validator._is_secret_like(decoded_content)
    
    @staticmethod
    def _decode_base64(value: str) -> Optional[str | bytes]:
        """Attempt to decode Base64 string.
        
        Returns:
            Decoded string if UTF-8 decodable,
            Decoded bytes if binary,
            None if invalid Base64
        """
        try:
            decoded_bytes = base64.b64decode(value, validate=True)
            
            # Try UTF-8 decoding
            try:
                return decoded_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # Binary data
                return decoded_bytes
                
        except (binascii.Error, ValueError):
            return None
    
    @staticmethod
    def _is_secret_like(text: str) -> bool:
        """Check if decoded text appears to be a secret.
        
        Args:
            text: Decoded text to analyze
            
        Returns:
            True if text appears to be a legitimate secret
        """
        # Check for weak patterns
        if PatternDetector.is_sequential(text):
            return False
        
        if PatternDetector.is_keyboard_walk(text):
            return False
        
        if PatternDetector.is_repetitive(text):
            return False
        
        if PatternDetector.is_test_value(text):
            return False
        
        # Check entropy level
        entropy = EntropyCalculator.calculate(text)
        entropy_level = EntropyCalculator.classify_entropy(entropy)
        
        # Secrets should have at least low entropy
        return entropy_level not in [EntropyLevel.VERY_LOW, EntropyLevel.LOW]


# ============================================================================
# PUBLIC API (Backward Compatibility)
# ============================================================================

# Export original function names for backward compatibility
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