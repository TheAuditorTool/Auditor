"""YAML-driven refactor profile evaluation."""

import fnmatch
import functools
import re
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

MAX_RESULTS_PER_QUERY = 500


BATCH_SIZE = 50


def _coerce_list(value: Iterable[str] | None) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value if item]


def _normalize_path(path_value: str | None, repo_root: Path | None) -> str:
    if not path_value:
        return ""
    raw_path = Path(path_value)
    try:
        if raw_path.is_absolute():
            abs_path = raw_path.resolve()
        elif repo_root:
            abs_path = (repo_root / raw_path).resolve()
        else:
            abs_path = raw_path
        if repo_root:
            try:
                rel = abs_path.relative_to(repo_root.resolve())
                return rel.as_posix()
            except ValueError:
                return abs_path.as_posix()
        return abs_path.as_posix()
    except Exception:
        return raw_path.as_posix()


@dataclass
class PatternSpec:
    """Match/expectation specification."""

    identifiers: list[str] = field(default_factory=list)
    expressions: list[str] = field(default_factory=list)
    sql_tables: list[str] = field(default_factory=list)
    api_routes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PatternSpec:
        raw = raw or {}
        return cls(
            identifiers=_coerce_list(raw.get("identifiers")),
            expressions=_coerce_list(raw.get("expressions") or raw.get("strings")),
            sql_tables=_coerce_list(raw.get("sql_tables")),
            api_routes=_coerce_list(raw.get("api_routes")),
        )

    def is_empty(self) -> bool:
        return not (self.identifiers or self.expressions or self.sql_tables or self.api_routes)


@dataclass
class RefactorRule:
    """Single rule describing an obsolete/new pairing."""

    id: str
    description: str
    severity: str = "medium"
    category: str = "schema"
    match: PatternSpec = field(default_factory=PatternSpec)
    expect: PatternSpec = field(default_factory=PatternSpec)
    scope: dict[str, list[str]] = field(default_factory=dict)
    guidance: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RefactorRule:
        if "id" not in raw or "description" not in raw:
            raise ValueError("Each refactor rule must include 'id' and 'description'")
        severity = raw.get("severity", "medium").lower()
        if severity not in {"critical", "high", "medium", "low"}:
            raise ValueError(f"Invalid severity '{severity}' for rule '{raw['id']}'")
        category = raw.get("category", "schema")
        return cls(
            id=str(raw["id"]),
            description=str(raw["description"]),
            severity=severity,
            category=str(category),
            match=PatternSpec.from_dict(raw.get("match")),
            expect=PatternSpec.from_dict(raw.get("expect") or raw.get("requires")),
            scope={
                "include": _coerce_list((raw.get("scope") or {}).get("include")),
                "exclude": _coerce_list((raw.get("scope") or {}).get("exclude")),
            },
            guidance=raw.get("guidance"),
        )


@dataclass
class RefactorProfile:
    """User-defined profile with multiple rules."""

    refactor_name: str
    description: str
    version: str | None
    rules: list[RefactorRule]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> RefactorProfile:
        """Load profile from a YAML file path."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls._from_dict(data)

    @classmethod
    def load_from_string(cls, yaml_text: str) -> RefactorProfile:
        """Load profile from a YAML string (no temp file needed)."""
        data = yaml.safe_load(yaml_text)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict | None) -> RefactorProfile:
        """Internal: Create profile from parsed YAML dict."""
        if not isinstance(data, dict):
            raise ValueError("Refactor profile must be a YAML mapping")
        name = data.get("refactor_name") or data.get("context_name")
        if not name:
            raise ValueError("Missing 'refactor_name' in refactor profile")
        description = data.get("description") or ""
        rules_raw = data.get("rules")
        if not rules_raw or not isinstance(rules_raw, Sequence):
            raise ValueError("Refactor profile must include a 'rules' list")
        rules = [RefactorRule.from_dict(item) for item in rules_raw]
        version = data.get("version")
        metadata = data.get("metadata") or {}
        return cls(
            refactor_name=str(name),
            description=str(description),
            version=str(version) if version else None,
            rules=rules,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "refactor_name": self.refactor_name,
            "description": self.description,
            "version": self.version,
            "metadata": self.metadata,
            "rule_count": len(self.rules),
        }


@dataclass
class RuleResult:
    """Evaluation result for a single rule."""

    rule: RefactorRule
    violations: list[dict[str, Any]]
    expected_references: list[dict[str, Any]]

    def missing_expectation_files(self) -> list[str]:
        violation_files = {item["file"] for item in self.violations}
        expectation_files = {item["file"] for item in self.expected_references}
        missing = sorted(f for f in violation_files if f and f not in expectation_files)
        return missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule.id,
            "description": self.rule.description,
            "severity": self.rule.severity,
            "category": self.rule.category,
            "violations": self.violations,
            "expected_references": self.expected_references,
            "missing_expectation_files": self.missing_expectation_files(),
            "status": "needs_migration" if self.violations else "clean",
        }


@dataclass
class ProfileEvaluation:
    """Full evaluation summary for a profile."""

    profile: RefactorProfile
    rule_results: list[RuleResult]

    def total_violations(self) -> int:
        return sum(len(rule.violations) for rule in self.rule_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "summary": {
                "total_rules": len(self.rule_results),
                "total_violations": self.total_violations(),
            },
            "rules": [rule.to_dict() for rule in self.rule_results],
        }


@dataclass(frozen=True)
class _SourceQuery:
    table: str
    column: str
    file_field: str
    line_field: str
    label: str
    context_field: str | None = None


IDENTIFIER_SOURCES: tuple[_SourceQuery, ...] = (
    _SourceQuery("symbols", "name", "path", "line", "symbols", "type"),
    _SourceQuery("symbols_jsx", "name", "path", "line", "symbols_jsx", "type"),
    _SourceQuery("variable_usage", "variable_name", "file", "line", "variable_usage", "usage_type"),
    _SourceQuery("assignments", "target_var", "file", "line", "assignments", "source_expr"),
    _SourceQuery(
        "function_call_args",
        "callee_function",
        "file",
        "line",
        "function_call_args",
        "caller_function",
    ),
)

EXPRESSION_SOURCES: tuple[_SourceQuery, ...] = (
    _SourceQuery("assignments", "source_expr", "file", "line", "assignments"),
    _SourceQuery(
        "function_call_args",
        "argument_expr",
        "file",
        "line",
        "function_call_args",
        "callee_function",
    ),
    _SourceQuery("sql_queries", "query_text", "file_path", "line_number", "sql_queries", "command"),
    _SourceQuery("api_endpoints", "path", "file", "line", "api_endpoints", "method"),
)

SQL_TABLE_SOURCES: tuple[_SourceQuery, ...] = (
    _SourceQuery("sql_query_tables", "table_name", "query_file", "query_line", "sql_query_tables"),
)

API_ROUTE_SOURCES: tuple[_SourceQuery, ...] = (
    _SourceQuery("api_endpoints", "path", "file", "line", "api_endpoints", "method"),
)


class RefactorRuleEngine:
    """Executes profile rules against repo_index.db."""

    def __init__(self, db_path: Path, repo_root: Path | None = None):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"repo_index.db not found at {db_path}")
        self.repo_root = Path(repo_root) if repo_root else None
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> RefactorRuleEngine:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def evaluate(self, profile: RefactorProfile) -> ProfileEvaluation:
        results: list[RuleResult] = []
        for rule in profile.rules:
            violations = self._run_spec(rule.match, rule.scope)
            expected = self._run_spec(rule.expect, rule.scope) if not rule.expect.is_empty() else []
            results.append(
                RuleResult(rule=rule, violations=violations, expected_references=expected)
            )
        return ProfileEvaluation(profile=profile, rule_results=results)

    def _run_spec(self, spec: PatternSpec, scope: dict[str, list[str]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if spec.identifiers:
            findings.extend(self._query_sources(spec.identifiers, IDENTIFIER_SOURCES, scope))
        if spec.expressions:
            findings.extend(self._query_sources(spec.expressions, EXPRESSION_SOURCES, scope))
        if spec.sql_tables:
            findings.extend(self._query_sources(spec.sql_tables, SQL_TABLE_SOURCES, scope))
        if spec.api_routes:
            findings.extend(self._query_sources(spec.api_routes, API_ROUTE_SOURCES, scope))
        return findings

    def _query_sources(
        self,
        terms: Sequence[str],
        sources: tuple[_SourceQuery, ...],
        scope: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        """Query sources with batched SQL and regex boundary filtering."""
        if not terms:
            return []

        cursor = self.conn.cursor()
        results: list[dict[str, Any]] = []
        seen: set = set()

        unique_terms = list(dict.fromkeys(terms))

        term_patterns = {}
        for term in unique_terms:
            if term.startswith("/") and term.endswith("/") and len(term) > 2:
                raw_pattern = term[1:-1]
                try:
                    term_patterns[term] = re.compile(raw_pattern, re.IGNORECASE)
                except re.error:
                    term_patterns[term] = re.compile(re.escape(term), re.IGNORECASE)
            else:
                term_patterns[term] = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)

        for chunk in self._chunk_list(unique_terms, BATCH_SIZE):
            like_params = []
            for t in chunk:
                if t.startswith("/") and t.endswith("/") and len(t) > 2:
                    core = t[1:-1].replace(".*", "").replace("\\.", ".")
                    like_params.append(f"%{core}%")
                else:
                    like_params.append(f"%{t}%")

            for source in sources:
                or_clauses = " OR ".join([f"{source.column} LIKE ? COLLATE NOCASE"] * len(chunk))

                query = (
                    f"SELECT {source.file_field} AS file_path, "
                    f"{source.line_field} AS line_number, "
                    f"{source.column} AS match_value"
                )
                if source.context_field:
                    query += f", {source.context_field} AS context_value"
                query += (
                    f" FROM {source.table} "
                    f"WHERE ({or_clauses}) "
                    f"ORDER BY {source.file_field}, {source.line_field} "
                    f"LIMIT {MAX_RESULTS_PER_QUERY}"
                )

                cursor.execute(query, like_params)

                for row in cursor.fetchall():
                    file_raw = row["file_path"]
                    file_path = _normalize_path(file_raw, self.repo_root)
                    if not file_path or not self._in_scope(file_path, scope):
                        continue

                    match_value = row["match_value"] or ""

                    matched_term = None
                    for term in chunk:
                        if term_patterns[term].search(match_value):
                            matched_term = term
                            break

                    if not matched_term:
                        continue

                    line = row["line_number"] or 0
                    context_value = row["context_value"] if source.context_field else None
                    signature = (file_path, line, source.label, match_value)
                    if signature in seen:
                        continue
                    seen.add(signature)

                    results.append(
                        {
                            "file": file_path,
                            "line": int(line),
                            "source": source.label,
                            "match": match_value,
                            "context": context_value,
                            "term": matched_term,
                        }
                    )

        return sorted(results, key=lambda x: (x["file"], x["line"], x["match"]))

    @staticmethod
    def _chunk_list(data: Sequence, size: int):
        """Yield successive chunks of data."""
        for i in range(0, len(data), size):
            yield data[i : i + size]

    @staticmethod
    def _prepare_like_term(term: str) -> str:
        """Prepare LIKE pattern (simple wildcard search)."""
        return f"%{term}%"

    def _in_scope(self, file_path: str, scope: dict[str, list[str]]) -> bool:
        """Check if file matches scope. Delegates to cached method with hashable args."""
        includes = tuple(scope.get("include") or [])
        excludes = tuple(scope.get("exclude") or [])
        return self._in_scope_cached(file_path, includes, excludes)

    @staticmethod
    @functools.lru_cache(maxsize=10000)
    def _in_scope_cached(file_path: str, includes: tuple, excludes: tuple) -> bool:
        """Cached scope check with hashable tuple args."""
        if excludes and any(fnmatch.fnmatch(file_path, pattern) for pattern in excludes):
            return False
        if includes:
            return any(fnmatch.fnmatch(file_path, pattern) for pattern in includes)
        return True
