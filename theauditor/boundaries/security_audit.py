"""Security Boundary Audit - comprehensive trust boundary analysis.

Audits four trust boundaries:
- INPUT: Where untrusted data enters (API endpoints) - validation check
- OUTPUT: Where data leaves to user (responses) - XSS prevention check
- DATABASE: Where data persists (queries) - SQLi prevention check
- FILE: Where data touches filesystem - path traversal check

Output format follows truth courier philosophy - facts only, no recommendations.
"""

import re
import sqlite3
from dataclasses import dataclass, field

from theauditor.boundaries.boundary_analyzer import _detect_frameworks

# =============================================================================
# AUDIT CATEGORIES
# =============================================================================

AUDIT_CATEGORIES = {
    "input": {
        "name": "INPUT BOUNDARIES",
        "description": "Entry points where untrusted data enters the system",
        "patterns": ["zod", "joi", "yup", "validate", "sanitize", "parse", "schema"],
        "severity": "CRITICAL",
        "check_type": "validation",
    },
    "output": {
        "name": "OUTPUT BOUNDARIES",
        "description": "Response points where data is sent to users",
        "patterns": ["escape", "sanitize", "encode", "DOMPurify", "htmlspecialchars"],
        "severity": "HIGH",
        "check_type": "xss_prevention",
    },
    "database": {
        "name": "DATABASE BOUNDARIES",
        "description": "Query points where data interacts with database",
        "patterns": ["parameterized", "prepared", "$1", "?", "execute"],
        "severity": "CRITICAL",
        "check_type": "sqli_prevention",
    },
    "file": {
        "name": "FILE BOUNDARIES",
        "description": "File operations where data touches filesystem",
        "patterns": ["path.resolve", "path.normalize", "realpath", "path.join"],
        "severity": "HIGH",
        "check_type": "path_traversal",
    },
}

# Dangerous output patterns (potential XSS sinks)
OUTPUT_SINK_PATTERNS = [
    re.compile(r"\.innerHTML\s*="),
    re.compile(r"\.outerHTML\s*="),
    re.compile(r"document\.write\("),
    re.compile(r"response\.send\("),
    re.compile(r"res\.send\("),
    re.compile(r"res\.json\("),
    re.compile(r"render\("),
    re.compile(r"dangerouslySetInnerHTML"),
]

# Safe output patterns (XSS prevention)
OUTPUT_SAFE_PATTERNS = [
    re.compile(r"escape\("),
    re.compile(r"sanitize\("),
    re.compile(r"encode\("),
    re.compile(r"DOMPurify"),
    re.compile(r"htmlspecialchars\("),
    re.compile(r"encodeURIComponent\("),
    re.compile(r"textContent\s*="),  # textContent is safe
]

# Dangerous database patterns (potential SQLi)
DATABASE_DANGER_PATTERNS = [
    re.compile(r'["\'].*\+.*["\']'),  # String concatenation in quotes
    re.compile(r"f['\"].*\{.*\}"),  # Python f-strings with variables
    re.compile(r"\$\{.*\}"),  # Template literals with variables
    re.compile(r"\.format\("),  # Python .format()
    re.compile(r"%s"),  # Python % formatting
]

# Safe database patterns (SQLi prevention)
DATABASE_SAFE_PATTERNS = [
    re.compile(r"\?"),  # Parameterized placeholder
    re.compile(r"\$\d+"),  # PostgreSQL style $1, $2
    re.compile(r":\w+"),  # Named parameters :name
    re.compile(r"@\w+"),  # SQL Server style @param
    re.compile(r"\.prepare\("),
    re.compile(r"prisma\."),  # Prisma ORM (safe by default)
    re.compile(r"sequelize\."),  # Sequelize (safe by default)
    re.compile(r"\.query\(\s*['\"][^'\"]*['\"],\s*\["),  # query("...", [...])
]

# Dangerous file patterns (potential path traversal)
FILE_DANGER_PATTERNS = [
    re.compile(r"\.\."),  # Path traversal sequence
    re.compile(r"readFile\("),
    re.compile(r"writeFile\("),
    re.compile(r"open\("),
    re.compile(r"fs\."),
]

# Safe file patterns (path traversal prevention)
FILE_SAFE_PATTERNS = [
    re.compile(r"path\.resolve\("),
    re.compile(r"path\.normalize\("),
    re.compile(r"realpath\("),
    re.compile(r"path\.join\(.*__dirname"),  # Anchored to __dirname
    re.compile(r"os\.path\.abspath\("),
    re.compile(r"os\.path\.realpath\("),
]


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class AuditFinding:
    """A single audit finding for a trust boundary check."""

    category: str  # input, output, database, file
    location: str  # file:line
    file: str
    line: int
    function: str | None
    status: str  # "PASS" or "FAIL"
    message: str
    evidence: str | None = None  # Code snippet or pattern matched


@dataclass
class AuditResult:
    """Complete audit result for a category."""

    category: str
    name: str  # Display name
    severity: str
    findings: list[AuditFinding] = field(default_factory=list)
    pass_count: int = 0
    fail_count: int = 0


@dataclass
class SecurityAuditReport:
    """Complete security audit report."""

    results: dict[str, AuditResult] = field(default_factory=dict)
    total_pass: int = 0
    total_fail: int = 0


# =============================================================================
# AUDIT IMPLEMENTATION
# =============================================================================


def run_security_audit(db_path: str, max_findings: int = 100) -> SecurityAuditReport:
    """Run comprehensive security boundary audit.

    Checks four trust boundaries:
    - INPUT: Entry points with/without validation
    - OUTPUT: Response points with/without sanitization
    - DATABASE: Query points with/without parameterization
    - FILE: File operations with/without path validation

    Args:
        db_path: Path to repo_index.db
        max_findings: Maximum findings per category

    Returns:
        SecurityAuditReport with findings for each category
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    report = SecurityAuditReport()

    try:
        # Initialize results for each category
        for cat_key, cat_info in AUDIT_CATEGORIES.items():
            report.results[cat_key] = AuditResult(
                category=cat_key,
                name=cat_info["name"],
                severity=cat_info["severity"],
            )

        # Detect frameworks for context
        frameworks = _detect_frameworks(cursor)

        # Run category-specific audits
        _audit_input_boundaries(cursor, report, frameworks, max_findings)
        _audit_output_boundaries(cursor, report, frameworks, max_findings)
        _audit_database_boundaries(cursor, report, frameworks, max_findings)
        _audit_file_boundaries(cursor, report, frameworks, max_findings)

        # Calculate totals
        for result in report.results.values():
            report.total_pass += result.pass_count
            report.total_fail += result.fail_count

    finally:
        conn.close()

    return report


def _audit_input_boundaries(
    cursor: sqlite3.Cursor,
    report: SecurityAuditReport,
    frameworks: dict,
    max_findings: int,
) -> None:
    """Audit input validation at entry points."""
    result = report.results["input"]

    # Check Express routes
    if "express" in frameworks:
        cursor.execute(
            """
            SELECT DISTINCT file, route_line, route_path, route_method
            FROM express_middleware_chains
            LIMIT ?
            """,
            (max_findings,),
        )
        routes = cursor.fetchall()

        for file, line, path, method in routes:
            # Check if route has validation middleware
            cursor.execute(
                """
                SELECT handler_expr FROM express_middleware_chains
                WHERE file = ? AND route_line = ? AND handler_type = 'middleware'
                """,
                (file, line),
            )
            middlewares = [row[0].lower() if row[0] else "" for row in cursor.fetchall()]

            has_validation = any(
                pat in mw
                for mw in middlewares
                for pat in ["validate", "zod", "joi", "yup", "schema"]
            )

            finding = AuditFinding(
                category="input",
                location=f"{file}:{line}",
                file=file,
                line=line,
                function=f"{method or 'GET'} {path}",
                status="PASS" if has_validation else "FAIL",
                message="Validation middleware present" if has_validation else "No validation middleware",
                evidence=", ".join(middlewares[:3]) if middlewares else None,
            )
            result.findings.append(finding)
            if has_validation:
                result.pass_count += 1
            else:
                result.fail_count += 1

    # Check Python routes (FastAPI/Flask)
    cursor.execute(
        """
        SELECT file, line, method, pattern, handler_function, framework
        FROM python_routes
        LIMIT ?
        """,
        (max_findings,),
    )
    py_routes = cursor.fetchall()

    for file, line, method, pattern, handler, framework in py_routes:
        # Check if handler has Pydantic type hint (FastAPI automatic validation)
        has_validation = False
        if framework == "fastapi":
            cursor.execute(
                """
                SELECT type_annotation FROM type_annotations
                WHERE file = ? AND symbol_name = ?
                """,
                (file, handler),
            )
            for (type_ann,) in cursor.fetchall():
                if type_ann and "BaseModel" in type_ann:
                    has_validation = True
                    break

        finding = AuditFinding(
            category="input",
            location=f"{file}:{line}",
            file=file,
            line=line,
            function=f"{method or 'GET'} {pattern or '/'}",
            status="PASS" if has_validation else "FAIL",
            message="Pydantic validation" if has_validation else "No input validation detected",
        )
        result.findings.append(finding)
        if has_validation:
            result.pass_count += 1
        else:
            result.fail_count += 1


def _audit_output_boundaries(
    cursor: sqlite3.Cursor,
    report: SecurityAuditReport,
    frameworks: dict,
    max_findings: int,
) -> None:
    """Audit output sanitization for XSS prevention."""
    result = report.results["output"]

    # Find potential output sinks in function calls
    cursor.execute(
        """
        SELECT DISTINCT file, line, callee_function, caller_function
        FROM function_call_args
        WHERE callee_function IN ('send', 'json', 'render', 'write', 'innerHTML')
        LIMIT ?
        """,
        (max_findings,),
    )
    outputs = cursor.fetchall()

    for file, line, callee, caller in outputs:
        # Check if there's sanitization in the same function
        cursor.execute(
            """
            SELECT callee_function FROM function_call_args
            WHERE file = ? AND caller_function = ?
            AND callee_function IN ('escape', 'sanitize', 'encode', 'encodeURIComponent')
            """,
            (file, caller),
        )
        has_sanitization = cursor.fetchone() is not None

        # React JSX is auto-escaped (unless dangerouslySetInnerHTML)
        is_react_safe = "react" in frameworks or "next" in frameworks

        finding = AuditFinding(
            category="output",
            location=f"{file}:{line}",
            file=file,
            line=line,
            function=f"{caller}() -> {callee}()",
            status="PASS" if has_sanitization or is_react_safe else "FAIL",
            message="Output sanitized" if has_sanitization else (
                "React auto-escapes" if is_react_safe else "No output sanitization detected"
            ),
        )
        result.findings.append(finding)
        if has_sanitization or is_react_safe:
            result.pass_count += 1
        else:
            result.fail_count += 1


def _audit_database_boundaries(
    cursor: sqlite3.Cursor,
    report: SecurityAuditReport,
    frameworks: dict,
    max_findings: int,
) -> None:
    """Audit database query safety for SQLi prevention."""
    result = report.results["database"]

    # Check ORM queries (usually safe - ORMs parameterize by default)
    # Schema: file, line, query_type, includes, has_limit, has_transaction
    cursor.execute(
        """
        SELECT file, line, query_type, includes
        FROM orm_queries
        LIMIT ?
        """,
        (max_findings // 2,),
    )
    orm_queries = cursor.fetchall()

    for file, line, query_type, includes in orm_queries:
        # ORM queries are generally parameterized by default
        is_safe = True  # ORMs handle parameterization

        finding = AuditFinding(
            category="database",
            location=f"{file}:{line}",
            file=file,
            line=line,
            function=f"ORM.{query_type}()",
            status="PASS" if is_safe else "FAIL",
            message="ORM query (parameterized by default)",
            evidence=includes[:60] if includes else None,
        )
        result.findings.append(finding)
        if is_safe:
            result.pass_count += 1
        else:
            result.fail_count += 1

    # Check raw SQL queries
    # Schema: file_path, line_number, query_text, command, extraction_source
    cursor.execute(
        """
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE query_text IS NOT NULL
        LIMIT ?
        """,
        (max_findings // 2,),
    )
    raw_queries = cursor.fetchall()

    for file, line, query_text, command in raw_queries:
        # Check for parameterization patterns
        has_params = any(p.search(query_text or "") for p in DATABASE_SAFE_PATTERNS)
        has_danger = any(p.search(query_text or "") for p in DATABASE_DANGER_PATTERNS)

        is_safe = has_params and not has_danger

        finding = AuditFinding(
            category="database",
            location=f"{file}:{line}",
            file=file,
            line=line,
            function=f"SQL {command or 'query'}",
            status="PASS" if is_safe else "FAIL",
            message="Parameterized query" if is_safe else "Potential string concatenation (SQLi risk)",
            evidence=query_text[:100] if query_text else None,
        )
        result.findings.append(finding)
        if is_safe:
            result.pass_count += 1
        else:
            result.fail_count += 1


def _audit_file_boundaries(
    cursor: sqlite3.Cursor,
    report: SecurityAuditReport,
    frameworks: dict,
    max_findings: int,
) -> None:
    """Audit file operations for path traversal prevention."""
    result = report.results["file"]

    # Find file operations
    cursor.execute(
        """
        SELECT DISTINCT file, line, callee_function, caller_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN (
            'readFile', 'writeFile', 'readFileSync', 'writeFileSync',
            'open', 'read', 'write', 'unlink', 'rmdir', 'mkdir',
            'createReadStream', 'createWriteStream'
        )
        LIMIT ?
        """,
        (max_findings,),
    )
    file_ops = cursor.fetchall()

    for file, line, callee, caller, arg_expr in file_ops:
        # Check if path validation exists in the same function
        cursor.execute(
            """
            SELECT callee_function FROM function_call_args
            WHERE file = ? AND caller_function = ?
            AND (
                callee_function LIKE '%resolve%'
                OR callee_function LIKE '%normalize%'
                OR callee_function LIKE '%realpath%'
                OR callee_function LIKE '%join%'
            )
            """,
            (file, caller),
        )
        has_path_validation = cursor.fetchone() is not None

        # Check if argument uses user input
        uses_user_input = arg_expr and any(
            pat in (arg_expr or "").lower()
            for pat in ["req.", "request.", "params", "query", "body", "input"]
        )

        # Safe if has validation OR doesn't use user input
        is_safe = has_path_validation or not uses_user_input

        finding = AuditFinding(
            category="file",
            location=f"{file}:{line}",
            file=file,
            line=line,
            function=f"{caller}() -> {callee}()",
            status="PASS" if is_safe else "FAIL",
            message="Path validated" if has_path_validation else (
                "Static path" if not uses_user_input else "User input without path validation"
            ),
            evidence=arg_expr[:50] if arg_expr else None,
        )
        result.findings.append(finding)
        if is_safe:
            result.pass_count += 1
        else:
            result.fail_count += 1


# =============================================================================
# INDIVIDUAL CHECK FUNCTIONS
# =============================================================================


def check_output_sanitization(file: str, line: int, db_path: str) -> AuditFinding:
    """Check if output at a specific location is sanitized.

    Args:
        file: File path
        line: Line number
        db_path: Path to repo_index.db

    Returns:
        AuditFinding with PASS/FAIL status
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get the function at this location
        cursor.execute(
            """
            SELECT name FROM symbols
            WHERE path = ? AND line <= ? AND type IN ('function', 'method')
            ORDER BY line DESC LIMIT 1
            """,
            (file, line),
        )
        row = cursor.fetchone()
        function = row[0] if row else "unknown"

        # Check for sanitization calls in this function
        cursor.execute(
            """
            SELECT callee_function FROM function_call_args
            WHERE file = ? AND caller_function = ?
            AND callee_function IN ('escape', 'sanitize', 'encode', 'encodeURIComponent', 'DOMPurify')
            """,
            (file, function),
        )
        has_sanitization = cursor.fetchone() is not None

        return AuditFinding(
            category="output",
            location=f"{file}:{line}",
            file=file,
            line=line,
            function=function,
            status="PASS" if has_sanitization else "FAIL",
            message="Output sanitized" if has_sanitization else "No sanitization detected",
        )

    finally:
        conn.close()


def check_database_safety(file: str, line: int, db_path: str) -> AuditFinding:
    """Check if database query at a specific location is parameterized.

    Args:
        file: File path
        line: Line number
        db_path: Path to repo_index.db

    Returns:
        AuditFinding with PASS/FAIL status
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if this is an ORM query
        cursor.execute(
            """
            SELECT query_type FROM orm_queries
            WHERE file = ? AND line = ?
            """,
            (file, line),
        )
        row = cursor.fetchone()
        if row:
            query_type = row[0]
            # ORM queries are parameterized by default
            return AuditFinding(
                category="database",
                location=f"{file}:{line}",
                file=file,
                line=line,
                function=f"ORM.{query_type}",
                status="PASS",
                message="ORM query (parameterized by default)",
            )

        # Check raw SQL
        cursor.execute(
            """
            SELECT query_text FROM sql_queries
            WHERE file_path = ? AND line_number = ?
            """,
            (file, line),
        )
        row = cursor.fetchone()
        if row:
            query_text = row[0] or ""
            has_params = any(p.search(query_text) for p in DATABASE_SAFE_PATTERNS)
            return AuditFinding(
                category="database",
                location=f"{file}:{line}",
                file=file,
                line=line,
                function="raw SQL",
                status="PASS" if has_params else "FAIL",
                message="Parameterized" if has_params else "No parameterization detected",
                evidence=query_text[:100],
            )

        return AuditFinding(
            category="database",
            location=f"{file}:{line}",
            file=file,
            line=line,
            function="unknown",
            status="FAIL",
            message="No database query found at location",
        )

    finally:
        conn.close()


def check_file_safety(file: str, line: int, db_path: str) -> AuditFinding:
    """Check if file operation at a specific location has path validation.

    Args:
        file: File path
        line: Line number
        db_path: Path to repo_index.db

    Returns:
        AuditFinding with PASS/FAIL status
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get the function at this location
        cursor.execute(
            """
            SELECT name FROM symbols
            WHERE path = ? AND line <= ? AND type IN ('function', 'method')
            ORDER BY line DESC LIMIT 1
            """,
            (file, line),
        )
        row = cursor.fetchone()
        function = row[0] if row else "unknown"

        # Check for path validation in this function
        cursor.execute(
            """
            SELECT callee_function FROM function_call_args
            WHERE file = ? AND caller_function = ?
            AND (
                callee_function LIKE '%resolve%'
                OR callee_function LIKE '%normalize%'
                OR callee_function LIKE '%realpath%'
            )
            """,
            (file, function),
        )
        has_validation = cursor.fetchone() is not None

        return AuditFinding(
            category="file",
            location=f"{file}:{line}",
            file=file,
            line=line,
            function=function,
            status="PASS" if has_validation else "FAIL",
            message="Path validated" if has_validation else "No path validation detected",
        )

    finally:
        conn.close()


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================


def format_security_audit(report: SecurityAuditReport, max_per_category: int = 10) -> str:
    """Format security audit report for terminal output.

    Args:
        report: SecurityAuditReport to format
        max_per_category: Maximum findings to show per category

    Returns:
        Formatted string for terminal output
    """
    lines = []
    lines.append("=== SECURITY BOUNDARY AUDIT ===\n")

    for cat_key in ["input", "output", "database", "file"]:
        result = report.results.get(cat_key)
        if not result:
            continue

        lines.append(f"{result.name}:")
        lines.append(f"  Pass: {result.pass_count} | Fail: {result.fail_count}")
        lines.append("")

        # Show failures first, limited
        failures = [f for f in result.findings if f.status == "FAIL"]
        passes = [f for f in result.findings if f.status == "PASS"]

        for finding in failures[:max_per_category]:
            lines.append(f"  {finding.function or finding.location}")
            lines.append(f"    [FAIL] {finding.message}")
            lines.append(f"    File: {finding.file}:{finding.line}")
            if finding.evidence:
                lines.append(f"    Evidence: {finding.evidence[:60]}...")
            lines.append("")

        if len(failures) > max_per_category:
            lines.append(f"  ... and {len(failures) - max_per_category} more failures")
            lines.append("")

        # Show sample passes
        for finding in passes[:3]:
            lines.append(f"  {finding.function or finding.location}")
            lines.append(f"    [PASS] {finding.message}")
            lines.append("")

        if len(passes) > 3:
            lines.append(f"  ... and {len(passes) - 3} more passes")
            lines.append("")

        lines.append("-" * 40)
        lines.append("")

    # Summary
    lines.append("SUMMARY:")
    lines.append(f"  Total Checks: {report.total_pass + report.total_fail}")
    lines.append(f"  Passed: {report.total_pass}")
    lines.append(f"  Failed: {report.total_fail}")

    if report.total_pass + report.total_fail > 0:
        pct = report.total_pass * 100 // (report.total_pass + report.total_fail)
        lines.append(f"  Security Score: {pct}%")

    return "\n".join(lines)
