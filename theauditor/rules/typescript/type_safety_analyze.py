"""SQL-based TypeScript type safety analyzer - ENHANCED with semantic type data."""

import logging
import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

logger = logging.getLogger(__name__)


METADATA = RuleMetadata(
    name="typescript_type_safety",
    category="type-safety",
    target_extensions=[".ts", ".tsx"],
    exclude_patterns=[
        "node_modules/",
        "dist/",
        "build/",
        "__tests__/",
        "test/",
        "spec/",
        ".next/",
        "coverage/",
    ],
    requires_jsx_pass=False,
)


def find_type_safety_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect TypeScript type safety issues using semantic type data from TypeScript compiler."""
    findings = []

    if not context.db_path:
        return findings

    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT path FROM files WHERE ext IN ('.ts', '.tsx')")
        ts_files = {row[0] for row in cursor.fetchall()}

        if not ts_files:
            return findings

        findings.extend(_find_explicit_any_types(cursor, ts_files))

        findings.extend(_find_missing_return_types(cursor, ts_files))

        findings.extend(_find_missing_parameter_types(cursor, ts_files))

        findings.extend(_find_unsafe_type_assertions(cursor, ts_files))

        findings.extend(_find_non_null_assertions(cursor, ts_files))

        findings.extend(_find_dangerous_type_patterns(cursor, ts_files))

        findings.extend(_find_untyped_json_parse(cursor, ts_files))

        findings.extend(_find_untyped_api_responses(cursor, ts_files))

        findings.extend(_find_missing_interfaces(cursor, ts_files))

        findings.extend(_find_type_suppression_comments(cursor, ts_files))

        findings.extend(_find_untyped_catch_blocks(cursor, ts_files))

        findings.extend(_find_missing_generic_types(cursor, ts_files))

        findings.extend(_find_untyped_event_handlers(cursor, ts_files))

        findings.extend(_find_type_mismatches(cursor, ts_files))

        findings.extend(_find_unsafe_property_access(cursor, ts_files))

        findings.extend(_find_unknown_types(cursor, ts_files))

        conn.close()

    except sqlite3.Error as e:
        logger.warning(f"TypeScript type safety analysis failed: {e}")
        return findings

    return findings


def _find_explicit_any_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find explicit 'any' type annotations using semantic type data."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT file, line, symbol_name, type_annotation, symbol_kind
        FROM type_annotations
        WHERE file IN ({placeholders})
          AND is_any = 1
    """,
        list(ts_files),
    )

    any_types = cursor.fetchall()

    for file, line, name, type_ann, kind in any_types:
        findings.append(
            StandardFinding(
                rule_name="typescript-explicit-any",
                message=f"Explicit 'any' type in {kind}: {name}",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category="type-safety",
                snippet=f"{name}: {type_ann}" if type_ann else f"{name}: any",
                cwe_id="CWE-843",
            )
        )

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.file IN ({placeholders})
              AND a.source_expr IS NOT NULL
        """,
        list(ts_files),
    )

    any_assertions = []
    for file, line, var, expr in cursor.fetchall():
        if "as any" in expr:
            any_assertions.append((file, line, var, expr))

    for file, line, var, _expr in any_assertions:
        findings.append(
            StandardFinding(
                rule_name="typescript-any-assertion",
                message=f"Type assertion to 'any' in '{var}'",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category="type-safety",
                snippet="... as any",
                cwe_id="CWE-843",
            )
        )

    return findings


def _find_missing_return_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find functions without explicit return types using semantic type data."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT file, line, symbol_name, return_type
        FROM type_annotations
        WHERE file IN ({placeholders})
          AND symbol_kind = 'function'
          AND (return_type IS NULL OR return_type = '')
    """,
        list(ts_files),
    )

    missing_returns = cursor.fetchall()

    known_exceptions = frozenset(
        [
            "constructor",
            "render",
            "componentDidMount",
            "componentDidUpdate",
            "componentWillUnmount",
            "componentWillMount",
            "shouldComponentUpdate",
            "getSnapshotBeforeUpdate",
            "componentDidCatch",
        ]
    )

    for file, line, name, _return_type in missing_returns:
        if name not in known_exceptions:
            findings.append(
                StandardFinding(
                    rule_name="typescript-missing-return-type",
                    message=f"Function '{name}' missing explicit return type",
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    category="type-safety",
                    snippet=f"function {name}(...)",
                    cwe_id="CWE-843",
                )
            )

    return findings


def _find_missing_parameter_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find function parameters without type annotations."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({placeholders})
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
    """,
        list(ts_files),
    )

    function_calls = []
    for file, line, func, args in cursor.fetchall():
        if "function" in func.lower():
            function_calls.append((file, line, func, args))

    for file, line, _func, args in function_calls:
        if args and "function(" in args.lower() and ":" not in args and "(" in args and ")" in args:
            findings.append(
                StandardFinding(
                    rule_name="typescript-untyped-parameters",
                    message="Function parameters without type annotations",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category="type-safety",
                    snippet="function(param1, param2)",
                    cwe_id="CWE-843",
                )
            )

    return findings


def _find_unsafe_type_assertions(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find unsafe type assertions (as any, as unknown)."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({placeholders})
          AND a.source_expr IS NOT NULL
    """,
        list(ts_files),
    )

    type_assertions = []
    for file, line, var, expr in cursor.fetchall():
        if any(pattern in expr for pattern in ["as any", "as unknown", "as Function", "<any>"]):
            type_assertions.append((file, line, var, expr))

    for file, line, var, expr in type_assertions:
        severity = Severity.HIGH if "as any" in expr else Severity.MEDIUM
        confidence = Confidence.HIGH if "as any" in expr else Confidence.MEDIUM
        findings.append(
            StandardFinding(
                rule_name="typescript-unsafe-assertion",
                message=f"Unsafe type assertion in '{var}'",
                file_path=file,
                line=line,
                severity=severity,
                confidence=confidence,
                category="type-safety",
                snippet=f"{var} = ... as any",
                cwe_id="CWE-843",
            )
        )

    return findings


def _find_non_null_assertions(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find non-null assertions (!) that bypass null checks."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.file IN ({placeholders})
          AND a.source_expr IS NOT NULL
    """,
        list(ts_files),
    )

    non_null_assertions = []
    for file, line, expr in cursor.fetchall():
        if any(pattern in expr for pattern in ["!.", "!)", "!;"]):
            non_null_assertions.append((file, line, expr))

    for file, line, _expr in non_null_assertions:
        findings.append(
            StandardFinding(
                rule_name="typescript-non-null-assertion",
                message="Non-null assertion (!) bypasses null safety",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category="type-safety",
                snippet="value!.property",
                cwe_id="CWE-476",
            )
        )

    return findings


def _find_dangerous_type_patterns(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find dangerous type patterns like Function, Object, {} using semantic type data."""
    findings = []

    dangerous_types = frozenset(["Function", "Object", "{}"])

    placeholders = ",".join(["?" for _ in ts_files])
    for dangerous_type in dangerous_types:
        cursor.execute(
            f"""
            SELECT file, line, symbol_name, type_annotation
            FROM type_annotations
            WHERE file IN ({placeholders})
              AND type_annotation IS NOT NULL
        """,
            list(ts_files),
        )

        for file, line, name, type_ann in cursor.fetchall():
            if (
                type_ann == dangerous_type
                or type_ann == f"{dangerous_type}[]"
                or f"<{dangerous_type}>" in type_ann
            ):
                findings.append(
                    StandardFinding(
                        rule_name=f"typescript-dangerous-type-{dangerous_type.lower().replace('{', '').replace('}', 'empty')}",
                        message=f"Dangerous type '{dangerous_type}' used in {name}",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.HIGH,
                        category="type-safety",
                        snippet=f"{name}: {type_ann}" if type_ann else f": {dangerous_type}",
                        cwe_id="CWE-843",
                    )
                )

    return findings


def _find_untyped_json_parse(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find JSON.parse without type validation."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({placeholders})
          AND f.callee_function IS NOT NULL
    """,
        list(ts_files),
    )

    json_parses = []
    for file, line, func, args in cursor.fetchall():
        if "JSON.parse" in func:
            json_parses.append((file, line, func, args))

    for file, line, _func, _args in json_parses:
        cursor.execute(
            """
                SELECT source_expr
                FROM assignments a
                WHERE a.file = ?
                  AND a.line BETWEEN ? AND ?
                  AND a.source_expr IS NOT NULL
        """,
            (file, line, line + 5),
        )

        validation_count = 0
        for (source_expr,) in cursor.fetchall():
            if any(pattern in source_expr for pattern in ["as ", "zod", "joi", "validate"]):
                validation_count += 1

        has_validation = validation_count > 0

        if not has_validation:
            findings.append(
                StandardFinding(
                    rule_name="typescript-untyped-json-parse",
                    message="JSON.parse result not validated or typed",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    category="type-safety",
                    snippet="JSON.parse(data)",
                    cwe_id="CWE-843",
                )
            )

    return findings


def _find_untyped_api_responses(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find API calls without typed responses."""
    findings = []

    api_patterns = frozenset(["fetch", "axios", "request", "http.get", "http.post", "ajax"])

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.file IN ({placeholders})
          AND f.callee_function IS NOT NULL
    """,
        list(ts_files),
    )

    all_calls = cursor.fetchall()
    for pattern in api_patterns:
        api_calls = [(file, line, func) for file, line, func in all_calls if pattern in func]

        for file, line, _func in api_calls:
            cursor.execute(
                """
                    SELECT target_var, source_expr
                    FROM assignments a
                    WHERE a.file = ?
                      AND a.line BETWEEN ? AND ?
                      AND (a.target_var IS NOT NULL OR a.source_expr IS NOT NULL)
            """,
                (file, line - 2, line + 10),
            )

            typing_count = 0
            for target_var, source_expr in cursor.fetchall():
                if (target_var and ": " in target_var) or (
                    source_expr
                    and ("as " in source_expr or "<" in source_expr and ">" in source_expr)
                ):
                    typing_count += 1

            has_typing = typing_count > 0

            if not has_typing:
                findings.append(
                    StandardFinding(
                        rule_name="typescript-untyped-api-response",
                        message=f"API call ({pattern}) without typed response",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="type-safety",
                        snippet=f"{pattern}(url)",
                        cwe_id="CWE-843",
                    )
                )

    return findings


def _find_missing_interfaces(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find objects that should have interface definitions."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({placeholders})
          AND a.source_expr IS NOT NULL
          AND a.target_var IS NOT NULL
          AND LENGTH(a.source_expr) > 50
    """,
        list(ts_files),
    )

    complex_objects = []
    for file, line, var, expr in cursor.fetchall():
        if "{" in expr and "}" in expr and ": " not in var:
            complex_objects.append((file, line, var, expr))

    for file, line, var, expr in complex_objects:
        if expr.count(":") > 2:
            findings.append(
                StandardFinding(
                    rule_name="typescript-missing-interface",
                    message=f"Complex object '{var}' without interface definition",
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    confidence=Confidence.LOW,
                    category="type-safety",
                    snippet=f"{var} = {{ ... }}",
                    cwe_id="CWE-843",
                )
            )

    return findings


def _find_type_suppression_comments(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find @ts-ignore, @ts-nocheck, and @ts-expect-error comments."""
    findings = []

    suppressions = (
        (
            "@ts-ignore",
            Severity.HIGH,
            Confidence.HIGH,
            "Completely disables type checking for next line",
        ),
        (
            "@ts-nocheck",
            Severity.CRITICAL,
            Confidence.HIGH,
            "Disables ALL type checking for entire file",
        ),
        (
            "@ts-expect-error",
            Severity.MEDIUM,
            Confidence.MEDIUM,
            "Suppresses expected errors but may hide real issues",
        ),
    )

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({placeholders})
          AND s.type = 'comment'
          AND s.name IS NOT NULL
    """,
        list(ts_files),
    )

    all_comments = cursor.fetchall()

    for suppression, severity, confidence, _description in suppressions:
        suppression_comments = [
            (file, line, comment) for file, line, comment in all_comments if suppression in comment
        ]

        for file, line, _comment in suppression_comments:
            findings.append(
                StandardFinding(
                    rule_name=f"typescript-suppression-{suppression.replace('@', '').replace('-', '_')}",
                    message=f"TypeScript error suppression: {suppression}",
                    file_path=file,
                    line=line,
                    severity=severity,
                    confidence=confidence,
                    category="type-safety",
                    snippet=f"// {suppression}",
                    cwe_id="CWE-843",
                )
            )

    return findings


def _find_untyped_catch_blocks(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find catch blocks without typed errors."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({placeholders})
          AND s.type = 'catch'
    """,
        list(ts_files),
    )

    catch_blocks = cursor.fetchall()

    for file, line, name in catch_blocks:
        if "unknown" not in name and ":" not in name:
            findings.append(
                StandardFinding(
                    rule_name="typescript-untyped-catch",
                    message="Catch block with untyped error (defaults to any)",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category="type-safety",
                    snippet="catch (error)",
                    cwe_id="CWE-843",
                )
            )

    return findings


def _find_missing_generic_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find usage of generic types without type parameters using semantic type data."""
    findings = []

    generic_types = frozenset(["Array", "Promise", "Map", "Set", "WeakMap", "WeakSet", "Record"])

    placeholders = ",".join(["?" for _ in ts_files])
    for generic in generic_types:
        cursor.execute(
            f"""
            SELECT file, line, symbol_name, type_annotation, type_params
            FROM type_annotations
            WHERE file IN ({placeholders})
              AND type_annotation = ?
              AND (is_generic = 0 OR type_params IS NULL OR type_params = '')
        """,
            list(ts_files) + [generic],
        )

        untyped_generics = cursor.fetchall()

        for file, line, _name, type_ann, _type_params in untyped_generics:
            findings.append(
                StandardFinding(
                    rule_name=f"typescript-untyped-{generic.lower()}",
                    message=f"{generic} without type parameter defaults to any",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    category="type-safety",
                    snippet=f": {generic}" if not type_ann else f": {type_ann}",
                    cwe_id="CWE-843",
                )
            )

    return findings


def _find_untyped_event_handlers(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find event handlers without proper typing."""
    findings = []

    event_patterns = frozenset(["onClick", "onChange", "onSubmit", "addEventListener", "on("])

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({placeholders})
          AND (f.callee_function IS NOT NULL OR f.argument_expr IS NOT NULL)
    """,
        list(ts_files),
    )

    all_calls = cursor.fetchall()
    for pattern in event_patterns:
        event_handlers = [
            (file, line, func, args)
            for file, line, func, args in all_calls
            if (func and pattern in func) or (args and pattern in args)
        ]

        for file, line, _func, args in event_handlers:
            if args and "event" in args.lower() and ":" not in args:
                findings.append(
                    StandardFinding(
                        rule_name="typescript-untyped-event",
                        message="Event handler without typed event parameter",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        confidence=Confidence.LOW,
                        category="type-safety",
                        snippet="(event) => {...}",
                        cwe_id="CWE-843",
                    )
                )

    return findings


def _find_type_mismatches(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find potential type mismatches in assignments."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file IN ({placeholders})
          AND a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
    """,
        list(ts_files),
    )

    mismatches = []
    for file, line, var, expr in cursor.fetchall():
        var_lower = var.lower()
        expr_lower = expr.lower()

        if (
            ("string" in var_lower and "number" in expr_lower)
            or ("number" in var_lower and "string" in expr_lower)
            or "boolean" in var_lower
            and "true" not in expr_lower
            and "false" not in expr_lower
        ):
            mismatches.append((file, line, var, expr))

    for file, line, var, _expr in mismatches:
        findings.append(
            StandardFinding(
                rule_name="typescript-type-mismatch",
                message=f"Potential type mismatch in assignment to {var}",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                category="type-safety",
                snippet=f"{var} = ...",
                cwe_id="CWE-843",
            )
        )

    return findings


def _find_unsafe_property_access(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find unsafe property access patterns."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT s.path AS file, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({placeholders})
          AND s.name IS NOT NULL
    """,
        list(ts_files),
    )

    bracket_accesses = []
    for file, line, name in cursor.fetchall():
        if "[" in name and "]" in name:
            bracket_accesses.append((file, line, name))

    for file, line, name in bracket_accesses:
        prop_access = name

        if (
            prop_access
            and not prop_access.strip().startswith('"')
            and not prop_access.strip().startswith("'")
        ):
            findings.append(
                StandardFinding(
                    rule_name="typescript-unsafe-property-access",
                    message="Dynamic property access without type safety",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category="type-safety",
                    snippet="obj[dynamicKey]",
                    cwe_id="CWE-843",
                )
            )

    return findings


def _find_unknown_types(cursor, ts_files: set[str]) -> list[StandardFinding]:
    """Find 'unknown' types requiring type narrowing using semantic type data."""
    findings = []

    placeholders = ",".join(["?" for _ in ts_files])
    cursor.execute(
        f"""
        SELECT file, line, symbol_name, type_annotation, symbol_kind
        FROM type_annotations
        WHERE file IN ({placeholders})
          AND is_unknown = 1
    """,
        list(ts_files),
    )

    unknown_types = cursor.fetchall()

    for file, line, name, type_ann, _kind in unknown_types:
        findings.append(
            StandardFinding(
                rule_name="typescript-unknown-type",
                message=f"Symbol '{name}' uses 'unknown' type requiring type narrowing",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category="type-safety",
                snippet=f"{name}: {type_ann}" if type_ann else f"{name}: unknown",
                cwe_id="CWE-843",
            )
        )

    return findings
