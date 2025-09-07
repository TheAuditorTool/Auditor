"""Common utility functions for security rules."""

import base64
import binascii
import math


def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string to measure randomness.
    
    High entropy (>4.0) typically indicates random strings like API keys.
    Low entropy (<3.0) typically indicates natural language or simple patterns.
    """
    if not text:
        return 0.0
    
    # Count character frequencies
    char_counts = {}
    for char in text:
        char_counts[char] = char_counts.get(char, 0) + 1
    
    # Calculate entropy
    entropy = 0.0
    text_len = len(text)
    for count in char_counts.values():
        probability = count / text_len
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy


def is_sequential(text: str) -> bool:
    """Check if a string follows a sequential pattern (incrementing or decrementing).
    
    Examples:
    - "abcdef" -> True (incrementing)
    - "987654" -> True (decrementing)  
    - "zyxwvu" -> True (decrementing)
    - "abc123" -> False (mixed)
    """
    if len(text) < 3:
        return False
    
    # Get ASCII differences between adjacent characters
    differences = []
    for i in range(1, len(text)):
        diff = ord(text[i]) - ord(text[i-1])
        differences.append(diff)
    
    # Check if all differences are the same (consistent increment/decrement)
    if len(set(differences)) == 1:
        # Common sequential patterns have difference of 1 or -1
        if differences[0] in [1, -1]:
            return True
    
    return False


def is_keyboard_walk(text: str) -> bool:
    """Check if a string matches common keyboard walk patterns.
    
    Keyboard walks are patterns formed by adjacent keys on a QWERTY keyboard.
    
    Examples:
    - "qwerty" -> True
    - "asdfgh" -> True
    - "1qaz2wsx" -> True
    """
    # Common keyboard walks (lowercase for case-insensitive comparison)
    keyboard_patterns = [
        # Horizontal walks (rows)
        'qwertyuiop', 'qwertyuio', 'qwertyui', 'qwertyu', 'qwerty', 'qwert',
        'asdfghjkl', 'asdfghjk', 'asdfghj', 'asdfgh', 'asdfg', 'asdf',
        'zxcvbnm', 'zxcvbn', 'zxcvb', 'zxcv',
        
        # Reverse horizontal walks
        'poiuytrewq', 'oiuytrewq', 'iuytrewq', 'uytrewq', 'ytrewq', 'trewq',
        'lkjhgfdsa', 'kjhgfdsa', 'jhgfdsa', 'hgfdsa', 'gfdsa', 'fdsa',
        'mnbvcxz', 'nbvcxz', 'bvcxz', 'vcxz',
        
        # Vertical/diagonal walks
        '1qaz2wsx3edc', '1qaz2wsx', '1qaz', '2wsx', '3edc',
        'zaq1xsw2cde3', 'zaq1xsw2', 'zaq1', 'xsw2', 'cde3',
        '1234567890', '0987654321',
        
        # Common patterns with shift
        '!qaz@wsx', '!qaz', '@wsx',
        
        # Number row patterns
        '1234567890', '0987654321', '123456789', '987654321',
        '12345678', '87654321', '1234567', '7654321',
        '123456', '654321', '12345', '54321', '1234', '4321', '123', '321',
    ]
    
    # Check if the text matches any pattern (case-insensitive)
    text_lower = text.lower()
    for pattern in keyboard_patterns:
        if pattern in text_lower or text_lower in pattern:
            return True
    
    return False


def decode_and_verify_base64(value: str) -> bool:
    """Decode Base64 string and check if decoded content is actually secret-like.
    
    Args:
        value: String that matches Base64 pattern
        
    Returns:
        True if the string is a valid Base64 encoding of secret-like content,
        False if it's a false positive (sequential, low entropy, repetitive, etc.)
    """
    try:
        # Attempt to decode from Base64
        decoded_bytes = base64.b64decode(value, validate=True)
        
        # Convert to string for analysis (try UTF-8 decoding)
        try:
            decoded_str = decoded_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # If it's not valid UTF-8, it might be binary data (possibly a real secret)
            # Check if it has reasonable entropy as bytes
            byte_entropy = calculate_entropy(decoded_bytes.hex())
            return byte_entropy > 3.0  # Binary secrets often have moderate to high entropy
        
        # Now analyze the decoded string
        
        # Check 1: Is it sequential or keyboard walk?
        if is_sequential(decoded_str) or is_keyboard_walk(decoded_str):
            return False
        
        # Check 2: Does it have very low entropy? (< 2.5 indicates simple/repetitive content)
        entropy = calculate_entropy(decoded_str)
        if entropy < 2.5:
            return False
        
        # Check 3: Is it highly repetitive? (one character makes up > 90%)
        if len(decoded_str) > 0:
            char_counts = {}
            for char in decoded_str:
                char_counts[char] = char_counts.get(char, 0) + 1
            
            max_count = max(char_counts.values())
            if max_count / len(decoded_str) > 0.9:
                return False
        
        # Check 4: Is it a common placeholder or test value?
        common_test_values = [
            'test', 'testing', 'example', 'sample', 'demo',
            'password', 'secret', 'admin', 'root', 'user',
            'localhost', '127.0.0.1', '0.0.0.0',
            'placeholder', 'changeme', 'your_password_here',
            'aaaa', 'bbbb', 'xxxx', '0000', '1111', '1234'
        ]
        
        decoded_lower = decoded_str.lower()
        for test_val in common_test_values:
            if test_val in decoded_lower and len(decoded_lower) < 30:
                return False
        
        # If we get here, it's likely a real secret
        return True
        
    except (binascii.Error, ValueError):
        # Not valid Base64 or decoding failed
        # This shouldn't happen if the regex matched, but be safe
        return False