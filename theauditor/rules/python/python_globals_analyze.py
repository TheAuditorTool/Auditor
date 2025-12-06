"""Python Global Mutable State Analyzer - Detects risky global state that causes concurrency issues."""

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="python_globals",
    category="concurrency",
    target_extensions=[".py"],
    exclude_patterns=[
        "node_modules/",
        "vendor/",
        ".venv/",
        "__pycache__/",
    ],
    execution_scope="database",
    primary_table="assignments",
)


MUTABLE_LITERALS = frozenset(
    [
        "{}",
        "[]",
        "dict(",
        "list(",
        "set(",
        "defaultdict(",
        "OrderedDict(",
        "Counter(",
        "deque(",
    ]
)


SAFE_PATTERNS = frozenset(
    [
        "logging.getLogger",
        "getLogger",
        "frozenset(",
        "tuple(",
        "namedtuple(",
        "Enum(",
        "Lock(",
        "RLock(",
        "Semaphore(",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect global mutable state that causes concurrency issues.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []
        seen: set[str] = set()

        def add_finding(
            file: str,
            line: int,
            rule_name: str,
            message: str,
            severity: Severity,
            confidence: Confidence = Confidence.HIGH,
            cwe_id: str | None = None,
        ) -> None:
            """Add a finding if not already seen."""
            key = f"{file}:{line}:{rule_name}"
            if key in seen:
                return
            seen.add(key)

            findings.append(
                StandardFinding(
                    rule_name=rule_name,
                    message=message,
                    file_path=file,
                    line=line,
                    severity=severity,
                    category=METADATA.category,
                    confidence=confidence,
                    cwe_id=cwe_id,
                )
            )

        _check_global_mutable_state(db, add_finding)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_global_mutable_state(db: RuleDB, add_finding) -> None:
    """Find global mutable state that is modified inside functions.

    Global mutable state (dicts, lists, sets) shared across threads/requests
    causes race conditions, data corruption, and hard-to-debug issues.
    """

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    candidates: list[tuple[str, int, str, str]] = []
    for row in rows:
        file, line, var, expr = row[0], row[1], row[2], row[3]
        if not expr or not var:
            continue

        if any(literal in str(expr) for literal in MUTABLE_LITERALS):
            candidates.append((file, line, var, expr))

    for file, line, var, expr in candidates:
        if var.startswith("_"):
            continue

        if var.isupper():
            continue

        if any(safe in str(expr) for safe in SAFE_PATTERNS):
            continue

        usage_count = _count_function_usages(db, file, var)

        if usage_count == 0:
            continue

        add_finding(
            file=file,
            line=line,
            rule_name="python-global-mutable-state",
            message=f'Global mutable "{var}" is used inside functions ({usage_count} times) - concurrency hazard',
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-362",
        )


def _count_function_usages(db: RuleDB, file: str, var: str) -> int:
    """Count how many times a variable is used inside functions (scope_level > 0)."""
    sql, params = Q.raw(
        """
        SELECT COUNT(*)
        FROM variable_usage
        WHERE file = ?
          AND variable_name = ?
          AND scope_level IS NOT NULL
          AND scope_level > 0
        """,
        [file, var],
    )

    rows = db.execute(sql, params)
    return rows[0][0] if rows else 0
