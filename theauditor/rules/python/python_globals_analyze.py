"""Detect risky global mutable state usage in Python modules."""

import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import (
    StandardRuleContext,
    StandardFinding,
    Severity,
    Confidence,
    RuleMetadata,
)


METADATA = RuleMetadata(
    name="python_globals",
    category="concurrency",
    target_extensions=[".py"],
    exclude_patterns=[
        "frontend/",
        "client/",
        "node_modules/",
        "test/",
        "__tests__/",
        "migrations/",
    ],
    execution_scope="database",
    requires_jsx_pass=False,
)


@dataclass(frozen=True)
class GlobalPatterns:
    MUTABLE_LITERALS = frozenset(["{}", "[]", "dict(", "list(", "set("])
    IMMUTABLE_OK = frozenset(["logging.getLogger"])


class GlobalAnalyzer:
    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = GlobalPatterns()
        self.findings: list[StandardFinding] = []

    def analyze(self) -> list[StandardFinding]:
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        cursor = conn.cursor()

        try:
            from theauditor.indexer.schema import build_query

            query = build_query(
                "assignments",
                ["file", "line", "target_var", "source_expr"],
                where="source_expr IS NOT NULL",
                order_by="file, line",
            )
            cursor.execute(query)

            candidates = []
            for file, line, var, expr in cursor.fetchall():
                if not expr:
                    continue

                if any(literal in expr for literal in self.patterns.MUTABLE_LITERALS):
                    candidates.append((file, line, var, expr))

            for file, line, var, expr in candidates:
                var_lower = (var or "").lower()
                if not var_lower or var_lower.startswith("_"):
                    continue
                if var_lower.isupper():
                    continue
                if any(allowed in (expr or "") for allowed in self.patterns.IMMUTABLE_OK):
                    continue

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM variable_usage
                    WHERE file = ?
                      AND variable_name = ?
                      AND scope_level IS NOT NULL
                      AND scope_level > 0
                    """,
                    (file, var),
                )
                usage_count = cursor.fetchone()[0]
                if usage_count == 0:
                    continue

                self.findings.append(
                    StandardFinding(
                        rule_name="python-global-mutable-state",
                        message=f'Global mutable "{var}" is modified inside functions ({usage_count} writes)',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="concurrency",
                    )
                )

        finally:
            conn.close()

        return self.findings


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    analyzer = GlobalAnalyzer(context)
    return analyzer.analyze()
