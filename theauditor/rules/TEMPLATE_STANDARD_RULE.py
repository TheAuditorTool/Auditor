"""RULE TEMPLATE: Standard Backend/Database Rule (No JSX Required).

================================================================================
RULE TEMPLATE DOCUMENTATION
================================================================================

⚠️ CRITICAL: FUNCTION NAMING REQUIREMENT
--------------------------------------------------------------------------------
Your rule function MUST start with 'find_' prefix:
  ✅ def find_sql_injection(context: StandardRuleContext)
  ✅ def find_hardcoded_secrets(context: StandardRuleContext)
  ❌ def analyze(context: StandardRuleContext)  # WRONG - Won't be discovered!
  ❌ def detect_xss(context: StandardRuleContext)  # WRONG - Must start with find_

The orchestrator ONLY discovers functions starting with 'find_'. Any other
name will be silently ignored and your rule will never run.
--------------------------------------------------------------------------------

⚠️ CRITICAL: StandardFinding PARAMETER NAMES
--------------------------------------------------------------------------------
ALWAYS use these EXACT parameter names when creating findings:
  ✅ file_path=     (NOT file=)
  ✅ rule_name=     (NOT rule=)
  ✅ cwe_id=        (NOT cwe=)
  ✅ severity=Severity.HIGH (NOT severity='HIGH')

Using wrong names will cause RUNTIME CRASHES. See examples at line 250.
--------------------------------------------------------------------------------

This template is for STANDARD RULES that analyze backend code, databases, or
general language patterns. These rules:

✅ Run on: .py, .js, .ts files (backend/server code)
✅ Query: Standard tables (function_call_args, symbols, assignments, etc.)
✅ Skip: Frontend JSX/TSX files (filtered by orchestrator)
❌ Do NOT use: JSX-specific tables (*_jsx tables)

WHEN TO USE THIS TEMPLATE:
- SQL injection detection
- Authentication/authorization issues
- Backend API security
- Database query analysis
- Server-side validation
- ORM/database patterns
- Python/Node.js specific issues

WHEN NOT TO USE THIS TEMPLATE:
- React/Vue component analysis → Use TEMPLATE_JSX_RULE.py
- Frontend-specific XSS → Use TEMPLATE_JSX_RULE.py
- JSX element injection → Use TEMPLATE_JSX_RULE.py

================================================================================
TEMPLATE BASED ON: sql_injection_analyze.py (Production Rule)
RULE METADATA: Declares file targeting to skip frontend files
================================================================================
"""
from __future__ import annotations


import sqlite3
from typing import List
from dataclasses import dataclass
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA - COPY THIS SECTION AND CUSTOMIZE
# ============================================================================
# This metadata tells the orchestrator WHERE and WHEN to run your rule.
# The orchestrator uses this to skip irrelevant files (e.g., don't run SQL
# injection rules on React components).
# ============================================================================

METADATA = RuleMetadata(
    name="your_rule_name",  # Change this: snake_case identifier
    category="security",     # Change this: sql, xss, auth, secrets, etc.

    # Target file extensions - rule ONLY runs on these files
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs'],

    # Exclude patterns - rule SKIPS these paths
    exclude_patterns=[
        'frontend/',     # Skip React/Vue frontend
        'client/',       # Skip client-side code
        'migrations/',   # Skip database migrations (low priority)
        'test/',         # Skip test files
        '__tests__/'     # Skip Jest tests
    ],

    # JSX settings (for standard rules, always False)
    requires_jsx_pass=False,  # This rule uses STANDARD tables, not *_jsx
    execution_scope='database',  # Use 'file' for per-file/AST rules

    # Optional: Target specific file patterns (include, not exclude)
    # target_file_patterns=['backend/', 'server/', 'api/']
)


# ============================================================================
# PATTERN DEFINITIONS - CUSTOMIZE FOR YOUR RULE
# ============================================================================
# Use frozensets for O(1) lookup performance (not lists).
# Define all detection patterns as constants for maintainability.
# ============================================================================

@dataclass(frozen=True)
class YourRulePatterns:
    """Pattern definitions for your security rule.

    Design principles:
    - Use frozensets for O(1) membership tests
    - No regex (use string matching on indexed database fields)
    - Keep patterns finite and maintainable
    """

    # Example: Dangerous function calls
    DANGEROUS_FUNCTIONS: frozenset = frozenset([
        'eval', 'exec', 'execfile',
        'compile', '__import__',
        'Function', 'setTimeout', 'setInterval'
    ])

    # Example: User input sources
    INPUT_SOURCES: frozenset = frozenset([
        'request.', 'req.', 'params.',
        'query.', 'body.', 'cookies.',
        'argv', 'stdin', 'input()'
    ])

    # Example: Safe sanitization functions
    SAFE_SANITIZERS: frozenset = frozenset([
        'escape', 'sanitize', 'validate',
        'DOMPurify', 'validator.escape'
    ])


# ============================================================================
# MAIN DETECTION FUNCTION - REQUIRED SIGNATURE
# ============================================================================
# This is the entry point called by the orchestrator.
# Function name MUST start with 'find_' (orchestrator requirement).
# Signature MUST be: (context: StandardRuleContext) -> List[StandardFinding]
# ============================================================================

def find_your_rule_name(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect [YOUR VULNERABILITY TYPE] using database-only approach.

    REQUIRED DOCSTRING STRUCTURE:
    1. One-line summary of what this rule detects
    2. Detection strategy (how it works)
    3. Database tables used
    4. Known limitations

    Detection Strategy:
    1. Query function_call_args for dangerous function calls
    2. Check if arguments contain user input patterns
    3. Exclude if sanitization detected
    4. Filter out test files, migrations, frontend

    Database Tables Used:
    - function_call_args: For detecting function calls
    - assignments: For tracking data flow
    - symbols: For function definitions (optional)

    Args:
        context: Rule execution context with db_path, project_path, etc.

    Returns:
        List of findings (empty list if no issues found)

    Known Limitations:
    - Cannot detect dynamic function names (variables)
    - May miss obfuscated patterns
    - Requires accurate AST extraction
    """
    findings = []

    # Validate database path
    if not context.db_path:
        return findings

    patterns = YourRulePatterns()
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # NO TABLE CHECKS - Database MUST be correct (ZERO FALLBACK POLICY)
        # If query fails, it means database is wrong and SHOULD crash
        findings.extend(_check_dangerous_calls(cursor, patterns))
        findings.extend(_check_user_input_flow(cursor, patterns))
        # Add more checks as needed

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER DETECTION FUNCTIONS - CUSTOMIZE THESE
# ============================================================================
# Break detection into small, testable functions.
# Each function queries ONE specific pattern.
# ============================================================================

def _check_dangerous_calls(cursor, patterns: YourRulePatterns) -> list[StandardFinding]:
    """Check for dangerous function calls with user input.

    Query pattern:
    1. Find all calls to dangerous functions
    2. Check if arguments contain user input
    3. Deduplicate by file:line
    """
    findings = []

    # Build SQL WHERE clause from pattern frozenset
    dangerous_funcs = ', '.join(f"'{func}'" for func in patterns.DANGEROUS_FUNCTIONS)

    cursor.execute(f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN ({dangerous_funcs})
          AND argument_index = 0
        ORDER BY file, line
    """)

    seen = set()

    for file, line, func, args in cursor.fetchall():
        # Skip if no arguments
        if not args:
            continue

        # Check for user input in arguments
        has_user_input = any(src in args for src in patterns.INPUT_SOURCES)

        if not has_user_input:
            continue  # Safe - no user input

        # Check for sanitization
        has_sanitizer = any(san in args for san in patterns.SAFE_SANITIZERS)

        if has_sanitizer:
            continue  # Safe - sanitized

        # Deduplicate by file:line
        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            file_path=file,           # ✅ CORRECT: Use file_path= not file=
            line=line,
            rule_name='your-rule-dangerous-call',  # ✅ CORRECT: Use rule_name= not rule=
            message=f'Dangerous function {func}() called with user input',
            severity=Severity.HIGH,  # Choose: CRITICAL, HIGH, MEDIUM, LOW, INFO
            category='security',      # Match METADATA.category
            snippet=args[:80] + '...' if len(args) > 80 else args,
            cwe_id='CWE-XXX'  # Optional: CWE identifier
        ))

    return findings


def _check_user_input_flow(cursor, patterns: YourRulePatterns) -> list[StandardFinding]:
    """Check for direct user input flow to dangerous sinks.

    Uses assignments table to track data flow.
    """
    findings = []

    # Example: Find assignments where user input flows to dangerous variable
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
        ORDER BY file, line
        LIMIT 1000
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check for user input patterns
        if 'request.' not in source and 'req.' not in source:
            continue
        # Check if target variable is used in dangerous context
        # (This is simplified - real implementation would query function_call_args)

        has_input = any(src in source for src in patterns.INPUT_SOURCES)

        if has_input:
            findings.append(StandardFinding(
                file_path=file,           # ✅ CORRECT parameter order
                line=line,
                rule_name='your-rule-input-flow',  # ✅ CORRECT: rule_name= not rule=
                message=f'User input assigned to variable {target}',
                severity=Severity.MEDIUM,
                category='security',
                snippet=f'{target} = {source[:60]}'
            ))

    return findings


# ============================================================================
# OPTIONAL: FRAMEWORK-AWARE DETECTION
# ============================================================================
# Check frameworks table to enable framework-specific detection
# ============================================================================

def _is_express_app(conn) -> bool:
    """Check if this is an Express.js application."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM frameworks
        WHERE name = 'express' AND language = 'javascript'
    """)

    return cursor.fetchone()[0] > 0


def _get_framework_safe_sinks(conn, framework_name: str) -> frozenset:
    """Get safe sinks for a specific framework."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fss.sink_pattern
        FROM framework_safe_sinks fss
        JOIN frameworks f ON f.id = fss.framework_id
        WHERE f.name = ?
          AND fss.is_safe = 1
    """, [framework_name])

    return frozenset(row[0] for row in cursor.fetchall())


# ============================================================================
# TESTING YOUR RULE (Run this before committing)
# ============================================================================
#
# 1. Test on plant project:
#    python -c "from theauditor.rules.your_rule import find_your_rule_name;
#               from theauditor.rules.base import StandardRuleContext;
#               from pathlib import Path;
#               ctx = StandardRuleContext(db_path='C:/Users/santa/Desktop/plant/.pf/repo_index.db');
#               findings = find_your_rule_name(ctx);
#               print(f'Found {len(findings)} issues');
#               [print(f'  {f.file_path}:{f.line} - {f.message}') for f in findings[:5]]"
#
# 2. Verify no false positives on TheAuditor itself:
#    aud detect-patterns --category=your_category
#
# 3. Check performance:
#    time aud detect-patterns --category=your_category
#    Should complete in <5 seconds for 10K LOC project
#
# ============================================================================
