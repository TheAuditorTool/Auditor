"""Hardcoded Secrets Analyzer - Hybrid Database/Pattern Approach.

This rule demonstrates a HYBRID approach because:
1. Secret detection requires entropy calculation (not in database)
2. Base64 decoding and verification (computational, not indexed)
3. Pattern matching for secret formats (regex-based analysis)

Therefore, this rule uses:
- Database queries for variable assignments and string literals
- Pattern matching and entropy analysis for secret detection

This is a legitimate exception similar to bundle_analyze.py - the database
doesn't index entropy values or decoded Base64 content.
"""

import sqlite3
import re
import base64
import math
from typing import List, Set
from pathlib import Path
from collections import Counter

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_hardcoded_secrets(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect hardcoded secrets using hybrid approach.
    
    Detects:
    - API keys and tokens in code
    - Hardcoded passwords
    - Private keys and certificates
    - AWS/Azure/GCP credentials
    - Database connection strings with passwords
    
    This is a HYBRID rule that uses:
    - Database for finding string assignments
    - Entropy calculation and pattern matching (not in DB)
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # ========================================================
        # PART 1: Find suspicious variable assignments from database
        # ========================================================
        findings.extend(_find_secret_assignments(cursor))
        findings.extend(_find_connection_strings(cursor))
        findings.extend(_find_env_fallbacks(cursor))
        findings.extend(_find_api_keys_in_urls(cursor))
        
        # ========================================================
        # PART 2: Pattern-based detection (requires file content)
        # ========================================================
        # For files with high secret probability, do targeted pattern matching
        suspicious_files = _get_suspicious_files(cursor)
        
        for file_path in suspicious_files:
            full_path = context.project_path / file_path
            if full_path.exists():
                pattern_findings = _scan_file_patterns(full_path, file_path)
                findings.extend(pattern_findings)
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# DATABASE-BASED CHECKS
# ============================================================================

def _find_secret_assignments(cursor) -> List[StandardFinding]:
    """Find variable assignments that look like secrets."""
    findings = []
    
    # Security-related variable names
    secret_keywords = [
        'secret', 'token', 'password', 'passwd', 'pwd',
        'api_key', 'apikey', 'auth_token', 'credential', 
        'private_key', 'privatekey', 'access_token', 'refresh_token',
        'client_secret', 'client_id', 'bearer', 'oauth', 'jwt',
        'aws_secret', 'aws_access', 'azure_key', 'gcp_key',
        'stripe_key', 'github_token', 'gitlab_token'
    ]
    
    # Build query for suspicious variable names
    conditions = ' OR '.join([f'a.target_var LIKE "%{kw}%"' for kw in secret_keywords])
    
    cursor.execute(f"""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE ({conditions})
          AND a.source_expr NOT LIKE '%process.env%'
          AND a.source_expr NOT LIKE '%import.meta.env%'
          AND a.source_expr NOT LIKE '%os.environ%'
          AND a.source_expr NOT LIKE '%getenv%'
          AND LENGTH(a.source_expr) > 10
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, value in cursor.fetchall():
        # Check if value looks like a secret
        if _is_likely_secret(value):
            findings.append(StandardFinding(
                rule_name='secret-hardcoded-assignment',
                message=f'Hardcoded secret in variable "{var}"',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{var} = {"*" * 20}...',
                fix_suggestion=f'Move {var} to environment variables or secure vault',
                cwe_id='CWE-798'  # Use of Hard-coded Credentials
            ))
        # Check for weak/default passwords
        elif var.lower() in ['password', 'passwd', 'pwd'] and value in [
            '"password"', '"admin"', '"123456"', '"changeme"', '"default"',
            "'password'", "'admin'", "'123456'", "'changeme'", "'default'"
        ]:
            findings.append(StandardFinding(
                rule_name='secret-weak-password',
                message=f'Weak/default password in "{var}"',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{var} = {value}',
                fix_suggestion='Use strong passwords from environment variables',
                cwe_id='CWE-521'  # Weak Password Requirements
            ))
    
    return findings


def _find_connection_strings(cursor) -> List[StandardFinding]:
    """Find database connection strings with embedded passwords."""
    findings = []
    
    # Find assignments that look like connection strings
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%mongodb://%'
               OR a.source_expr LIKE '%postgres://%'
               OR a.source_expr LIKE '%mysql://%'
               OR a.source_expr LIKE '%redis://%'
               OR a.source_expr LIKE '%amqp://%'
               OR a.source_expr LIKE '%postgresql://%')
          AND a.source_expr LIKE '%@%'
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, conn_str in cursor.fetchall():
        # Check if connection string has password
        # Pattern: protocol://user:password@host
        if re.search(r'://[^:]+:[^@]+@', conn_str):
            # Extract the password part for checking
            match = re.search(r'://[^:]+:([^@]+)@', conn_str)
            if match:
                password = match.group(1)
                # Check if it's not a placeholder
                if password not in ['password', 'changeme', '<password>', '${PASSWORD}']:
                    findings.append(StandardFinding(
                        rule_name='secret-connection-string',
                        message=f'Database connection string with embedded password',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        snippet=f'{var} = "...://user:***@host..."',
                        fix_suggestion='Use environment variables for database passwords',
                        cwe_id='CWE-798'
                    ))
    
    return findings


def _find_env_fallbacks(cursor) -> List[StandardFinding]:
    """Find environment variable fallbacks with hardcoded secrets."""
    findings = []
    
    # Find patterns like: process.env.SECRET || "hardcoded"
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%process.env%||%'
               OR a.source_expr LIKE '%os.environ.get%'
               OR a.source_expr LIKE '%getenv%||%'
               OR a.source_expr LIKE '%??%')
          AND (a.target_var LIKE '%secret%'
               OR a.target_var LIKE '%key%'
               OR a.target_var LIKE '%token%'
               OR a.target_var LIKE '%password%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, expr in cursor.fetchall():
        # Extract the fallback value
        fallback_match = re.search(r'\|\|\s*["\']([^"\']+)["\']', expr) or \
                        re.search(r'\?\?\s*["\']([^"\']+)["\']', expr) or \
                        re.search(r',\s*["\']([^"\']+)["\']', expr)
        
        if fallback_match:
            fallback = fallback_match.group(1)
            if len(fallback) > 10 and fallback not in ['default', 'changeme', 'placeholder']:
                if _is_likely_secret(fallback):
                    findings.append(StandardFinding(
                        rule_name='secret-env-fallback',
                        message=f'Hardcoded secret as environment variable fallback',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='security',
                        snippet=f'{var} = process.env.X || "***"',
                        fix_suggestion='Use secure defaults or fail if environment variable is missing',
                        cwe_id='CWE-798'
                    ))
    
    return findings


def _find_api_keys_in_urls(cursor) -> List[StandardFinding]:
    """Find API keys embedded in URLs."""
    findings = []
    
    # Find URL constructions with API keys
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function IN ('fetch', 'axios', 'request', 'get', 'post')
               OR f.callee_function LIKE '%.get' 
               OR f.callee_function LIKE '%.post')
          AND (f.argument_expr LIKE '%api_key=%'
               OR f.argument_expr LIKE '%apikey=%'
               OR f.argument_expr LIKE '%token=%'
               OR f.argument_expr LIKE '%key=%'
               OR f.argument_expr LIKE '%secret=%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        # Check if the API key looks hardcoded
        key_match = re.search(r'(api_key|apikey|token|key)=([^&\s]+)', args, re.IGNORECASE)
        if key_match:
            key_value = key_match.group(2)
            # Skip if it's a variable reference
            if not key_value.startswith('${') and not key_value.startswith('process.'):
                if len(key_value) > 10 and key_value not in ['YOUR_API_KEY', 'API_KEY_HERE']:
                    findings.append(StandardFinding(
                        rule_name='secret-api-key-in-url',
                        message='API key hardcoded in URL',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        snippet=f'{func}("...?api_key=***")',
                        fix_suggestion='Pass API keys in headers, not URLs',
                        cwe_id='CWE-598'  # Information Exposure Through Query Strings
                    ))
    
    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_suspicious_files(cursor) -> List[str]:
    """Get list of files likely to contain secrets."""
    suspicious_files = []
    
    # Find files with many secret-related symbols
    cursor.execute("""
        SELECT DISTINCT s.path
        FROM symbols s
        WHERE s.name LIKE '%secret%'
           OR s.name LIKE '%token%'
           OR s.name LIKE '%password%'
           OR s.name LIKE '%api_key%'
           OR s.name LIKE '%credential%'
        GROUP BY s.path
        HAVING COUNT(*) > 3
    """)
    
    suspicious_files.extend([row[0] for row in cursor.fetchall()])
    
    # Find config files
    cursor.execute("""
        SELECT f.path
        FROM files f
        WHERE f.path LIKE '%config%'
           OR f.path LIKE '%settings%'
           OR f.path LIKE '%env%'
    """)
    
    suspicious_files.extend([row[0] for row in cursor.fetchall()])
    
    return list(set(suspicious_files))


def _is_likely_secret(value: str) -> bool:
    """Check if a string value is likely a secret."""
    # Clean the value
    value = value.strip().strip('\'"')
    
    # Skip short strings
    if len(value) < 20:
        return False
    
    # Skip obvious non-secrets
    if value.lower() in ['true', 'false', 'none', 'null', 'undefined', 
                         'development', 'production', 'test', 'staging']:
        return False
    
    # Skip URLs and paths
    if value.startswith(('http://', 'https://', '/', './', '../')):
        return False
    
    # Check for high entropy (randomness)
    entropy = _calculate_entropy(value)
    if entropy > 4.0:
        # Additional checks to reduce false positives
        if not _is_sequential(value) and not _is_keyboard_walk(value):
            return True
    
    # Check for common secret patterns
    secret_patterns = [
        r'^[a-fA-F0-9]{32,}$',  # Hex strings
        r'^[A-Z0-9]{20,}$',  # All caps alphanumeric
        r'^sk_[a-zA-Z0-9]{24,}$',  # Stripe keys
        r'^[a-zA-Z0-9]{40}$',  # GitHub tokens
        r'^AKIA[0-9A-Z]{16}$',  # AWS keys
        r'^[A-Za-z0-9+/]{20,}={0,2}$',  # Base64
    ]
    
    for pattern in secret_patterns:
        if re.match(pattern, value):
            return True
    
    return False


def _calculate_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0
    
    # Count character frequencies
    freq = Counter(s)
    length = len(s)
    
    # Calculate entropy
    entropy = 0
    for count in freq.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy


def _is_sequential(s: str) -> bool:
    """Check if string contains sequential characters."""
    sequential_patterns = [
        'abcdefghijklmnopqrstuvwxyz',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        '0123456789',
        'qwertyuiop',
        'asdfghjkl',
        'zxcvbnm'
    ]
    
    s_lower = s.lower()
    for pattern in sequential_patterns:
        for i in range(len(pattern) - 4):
            if pattern[i:i+5] in s_lower:
                return True
    
    return False


def _is_keyboard_walk(s: str) -> bool:
    """Check if string is a keyboard walk pattern."""
    keyboard_patterns = [
        'qwerty', 'asdfgh', 'zxcvbn',
        '12345', '098765',
        'qazwsx', 'qweasd'
    ]
    
    s_lower = s.lower()
    for pattern in keyboard_patterns:
        if pattern in s_lower:
            return True
    
    return False


def _scan_file_patterns(file_path: Path, relative_path: str) -> List[StandardFinding]:
    """Scan file content for secret patterns (justified file I/O).
    
    This is necessary because the database doesn't store:
    - Full file content for pattern matching
    - Entropy calculations
    - Decoded Base64 values
    """
    findings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Specific patterns that indicate secrets
        high_confidence_patterns = [
            (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
            (r'(?i)aws_secret_access_key\s*=\s*["\']([^"\']+)["\']', 'AWS Secret Key'),
            (r'sk_live_[a-zA-Z0-9]{24,}', 'Stripe Live Key'),
            (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Personal Token'),
            (r'glpat-[a-zA-Z0-9\-_]{20,}', 'GitLab Token'),
            (r'xox[baprs]-[a-zA-Z0-9\-]+', 'Slack Token'),
            (r'-----BEGIN (RSA |EC )?PRIVATE KEY-----', 'Private Key'),
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern, description in high_confidence_patterns:
                if re.search(pattern, line):
                    findings.append(StandardFinding(
                        rule_name='secret-pattern-match',
                        message=f'{description} detected',
                        file_path=relative_path,
                        line=i,
                        severity=Severity.CRITICAL,
                        category='security',
                        snippet='',
                        fix_suggestion='Remove secret and rotate immediately',
                        cwe_id='CWE-798'
                    ))
    
    except OSError:
        pass  # File reading failed
    
    return findings