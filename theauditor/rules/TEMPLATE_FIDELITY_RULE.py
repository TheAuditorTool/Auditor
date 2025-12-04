# ruff: noqa: N999 - UPPERCASE name is intentional for template visibility
"""RULE TEMPLATE: Fidelity-Perfect Rule Pattern (December 2025).

This template demonstrates the CORRECT pattern for writing rules with:
- Q class for schema-validated queries
- RuleDB for connection management + manifest tracking
- RuleResult for fidelity verification by orchestrator

COPY THIS FILE when creating new rules. DO NOT use raw sqlite3.connect().

See: theauditor/rules/dependency/ghost_dependencies.py for a real example.
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

# =============================================================================
# METADATA - Required for orchestrator filtering
# =============================================================================

METADATA = RuleMetadata(
    name="your_rule_name",  # Unique identifier
    category="security",  # Category folder name
    # Target files by extension
    target_extensions=[".py", ".js", ".ts"],
    # Exclude patterns (paths containing these are skipped)
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    # JSX handling - set True only if rule needs preserved JSX data
    execution_scope="database")


# =============================================================================
# MAIN ENTRY POINT - Must be named 'analyze' for orchestrator
# =============================================================================


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect [YOUR VULNERABILITY] in indexed codebase.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings = []

    # Guard: No database means nothing to analyze
    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    # Use RuleDB context manager - handles connection + manifest tracking
    with RuleDB(context.db_path, METADATA.name) as db:
        # Run your analysis
        findings.extend(_check_dangerous_patterns(db))
        findings.extend(_check_user_input_flow(db))

        # Return RuleResult with manifest for fidelity verification
        return RuleResult(findings=findings, manifest=db.get_manifest())


# =============================================================================
# ANALYSIS FUNCTIONS - Use Q class for all queries
# =============================================================================


def _check_dangerous_patterns(db: RuleDB) -> list[StandardFinding]:
    """Check for dangerous function calls.

    Pattern: Query -> Filter -> Create Findings
    """
    findings = []

    # Q class validates table + columns at build() time
    # If "function_call_args" or columns don't exist, raises ValueError immediately
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?, ?)", "eval", "exec", "compile")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        # Skip if no arguments (nothing to analyze)
        if not args:
            continue

        # Check for user input in arguments
        if not _has_user_input(args):
            continue

        findings.append(
            StandardFinding(
                rule_name=f"{METADATA.name}-dangerous-call",
                message=f"Dangerous function {func}() called with user input",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category=METADATA.category,
                snippet=f"{func}({args[:60]}...)" if len(args) > 60 else f"{func}({args})",
                cwe_id="CWE-94",  # Code Injection
            )
        )

    return findings


def _check_user_input_flow(db: RuleDB) -> list[StandardFinding]:
    """Check for user input flowing to dangerous sinks.

    Pattern: Find tainted assignments -> Track to sinks
    """
    findings = []

    # Query assignments table
    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr LIKE ? OR source_expr LIKE ?", "%request.%", "%req.%")
        .limit(1000)  # Reasonable limit to avoid scanning entire codebase
    )

    for file, line, target_var, source_expr in rows:
        findings.append(
            StandardFinding(
                rule_name=f"{METADATA.name}-tainted-assignment",
                message=f"User input assigned to {target_var}",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category=METADATA.category,
                snippet=f"{target_var} = {source_expr[:50]}",
            )
        )

    return findings


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Common user input sources
USER_INPUT_SOURCES = frozenset([
    "request.", "req.", "params.", "query.", "body.",
    "cookies.", "argv", "stdin", "input()", "form.",
])


def _has_user_input(expr: str) -> bool:
    """Check if expression contains user input sources."""
    return any(src in expr for src in USER_INPUT_SOURCES)


# =============================================================================
# ADVANCED PATTERNS (Optional)
# =============================================================================


def _example_join_query(db: RuleDB) -> list[StandardFinding]:
    """Example: JOIN two tables.

    Use when correlating data across tables.
    """
    findings = []

    # JOIN with explicit ON condition (list of column pairs)
    rows = db.query(
        Q("function_call_args")
        .select("function_call_args.file", "function_call_args.line", "assignments.target_var")
        .join("assignments", on=[("file", "file")])
        .where("function_call_args.callee_function = ?", "execute")
    )

    # Process rows...
    _ = rows  # Placeholder

    return findings


def _example_cte_query(db: RuleDB) -> list[StandardFinding]:
    """Example: CTE (Common Table Expression) for complex analysis.

    Use when you need to:
    1. Find tainted sources
    2. Track where they flow
    3. Check if they reach dangerous sinks
    """
    findings = []

    # Step 1: Define CTE to find tainted variables
    tainted_vars = (
        Q("assignments")
        .select("file", "target_var", "line")
        .where("source_expr LIKE ? OR source_expr LIKE ?", "%request.%", "%req.%")
    )

    # Step 2: Main query joins CTE to find dangerous usage
    rows = db.query(
        Q("function_call_args")
        .with_cte("tainted", tainted_vars)
        .select("function_call_args.file", "function_call_args.line", "tainted.target_var")
        .join("tainted", on=[("file", "file")])
        .where("function_call_args.callee_function LIKE ?", "%execute%")
    )

    # Process rows...
    _ = rows  # Placeholder

    return findings


def _example_raw_sql_escape_hatch(db: RuleDB) -> list[StandardFinding]:
    """Example: Raw SQL for edge cases Q cannot express.

    WARNING: Use sparingly. Logs warning for audit trail.
    Prefer Q class for schema validation.
    """
    findings = []

    # Q.raw() bypasses validation - use only when necessary
    sql, params = Q.raw(
        """
        SELECT file, line FROM function_call_args
        WHERE callee_function REGEXP ?
        """,
        ["^(eval|exec)$"],
    )

    # Execute raw SQL (still tracked in manifest)
    rows = db.execute(sql, params)

    # Process rows...
    _ = rows  # Placeholder

    return findings
