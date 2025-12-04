"""Vue.js reactivity and props mutation analyzer - Database-First Implementation."""

import json
import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="vue_reactivity",
    category="vue",
    target_extensions=[".vue", ".js", ".ts"],
    target_file_patterns=["frontend/", "client/", "src/components/", "src/views/"],
    exclude_patterns=["backend/", "server/", "api/", "__tests__/", "*.test.*", "*.spec.*"],
    execution_scope="database")


PROP_ACCESS_PATTERNS = frozenset(["this.", "props.", "$props.", "this.$props."])


NON_REACTIVE_INITIALIZERS = frozenset(
    ["{}", "[]", "{ }", "[ ]", "new Object()", "new Array()", "Object.create(null)"]
)


def find_vue_reactivity_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Vue.js reactivity and props mutation issues using database queries."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        findings.extend(_find_props_mutations(cursor))
        findings.extend(_find_non_reactive_data(cursor))

    finally:
        conn.close()

    return findings


def _find_props_mutations(cursor) -> list[StandardFinding]:
    """Find direct props mutations using database queries."""
    findings = []

    cursor.execute("""
        SELECT file, props_definition, composition_api_used
        FROM vue_components
        WHERE props_definition IS NOT NULL
          AND props_definition != ''
          AND props_definition != 'null'
    """)

    for file, props_json, is_composition in cursor.fetchall():
        try:
            props_data = json.loads(props_json) if props_json else {}

            if isinstance(props_data, list):
                prop_names = set(props_data)
            elif isinstance(props_data, dict):
                prop_names = set(props_data.keys())
            else:
                continue

            if not prop_names:
                continue

            cursor.execute(
                """
                SELECT line, target_var, source_expr
                FROM assignments
                WHERE file = ?
                  AND target_var IS NOT NULL
            """,
                (file,),
            )

            for line, target, source in cursor.fetchall():
                matched_prop = None
                for prop_name in prop_names:
                    patterns = [
                        f"this.{prop_name}",
                        f"props.{prop_name}",
                        f"this.$props.{prop_name}",
                        f"this.props.{prop_name}",
                    ]
                    if any(pattern in target for pattern in patterns):
                        matched_prop = prop_name
                        break

                if not matched_prop:
                    continue

                api_type = "Composition API" if is_composition else "Options API"

                findings.append(
                    StandardFinding(
                        rule_name="vue-props-mutation",
                        message=f'Direct mutation of prop "{matched_prop}" violates one-way data flow ({api_type})',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="vue",
                        confidence=Confidence.HIGH,
                        snippet=f"{target} = {source[:50]}..."
                        if len(source) > 50
                        else f"{target} = {source}",
                        cwe_id="CWE-915",
                    )
                )

        except (json.JSONDecodeError, TypeError):
            continue

    return findings


def _find_non_reactive_data(cursor) -> list[StandardFinding]:
    """Find non-reactive data initialization in Options API."""
    findings = []

    cursor.execute("""
        SELECT file, name
        FROM vue_components
        WHERE composition_api_used = 0
    """)

    for file, _component_name in cursor.fetchall():
        cursor.execute(
            """
            SELECT line, name
            FROM symbols
            WHERE path = ?
              AND name = 'data'
              AND type IN ('function', 'method')
        """,
            (file,),
        )

        data_methods = cursor.fetchall()
        if not data_methods:
            continue

        for data_line, _ in data_methods:
            cursor.execute(
                """
                SELECT line, target_var, source_expr, in_function
                FROM assignments
                WHERE file = ?
                  AND line BETWEEN ? AND ?
                  AND in_function IS NOT NULL
            """,
                (file, data_line, data_line + 20),
            )

            for line, target, source, in_function in cursor.fetchall():
                if "data" not in in_function.lower():
                    continue

                source_stripped = source.strip()
                if source_stripped in NON_REACTIVE_INITIALIZERS:
                    if source_stripped in ("{}", "{ }", "new Object()", "Object.create(null)"):
                        init_type = "object"
                    else:
                        init_type = "array"

                    findings.append(
                        StandardFinding(
                            rule_name="vue-non-reactive-data",
                            message=f"Non-reactive {init_type} literal in data() will be shared across component instances",
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category="vue",
                            confidence=Confidence.MEDIUM,
                            snippet=f"{target}: {source}",
                            cwe_id="CWE-1323",
                        )
                    )

    return findings


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point."""
    return find_vue_reactivity_issues(context)
