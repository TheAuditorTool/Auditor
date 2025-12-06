"""SQL-based TypeScript type safety analyzer - ENHANCED with semantic type data.

Detects TypeScript type safety issues including:
- Explicit 'any' types and type assertions
- Missing return types and parameter types
- Unsafe type assertions (as any, as unknown)
- Non-null assertions (!) bypassing null checks
- Dangerous types (Function, Object, {})
- Type suppression comments (@ts-ignore, @ts-nocheck)
- Untyped catch blocks and event handlers
- Missing generic type parameters
- Unsafe property access patterns
- Unknown types requiring narrowing

CWE-843: Type Confusion
CWE-476: NULL Pointer Dereference
"""

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
    name="typescript_type_safety",
    category="type-safety",
    execution_scope="database",
    primary_table="type_annotations",
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
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect TypeScript type safety issues using semantic type data.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        ts_files = _get_typescript_files(db)
        if not ts_files:
            return RuleResult(findings=[], manifest=db.get_manifest())

        findings: list[StandardFinding] = []
        findings.extend(_find_explicit_any_types(db, ts_files))
        findings.extend(_find_missing_return_types(db, ts_files))
        findings.extend(_find_missing_parameter_types(db, ts_files))
        findings.extend(_find_unsafe_type_assertions(db, ts_files))
        findings.extend(_find_non_null_assertions(db, ts_files))
        findings.extend(_find_dangerous_type_patterns(db, ts_files))
        findings.extend(_find_untyped_json_parse(db, ts_files))
        findings.extend(_find_untyped_api_responses(db, ts_files))
        findings.extend(_find_missing_interfaces(db, ts_files))
        findings.extend(_find_type_suppression_comments(db, ts_files))
        findings.extend(_find_untyped_catch_blocks(db, ts_files))
        findings.extend(_find_missing_generic_types(db, ts_files))
        findings.extend(_find_untyped_event_handlers(db, ts_files))
        findings.extend(_find_unsafe_property_access(db, ts_files))
        findings.extend(_find_unknown_types(db, ts_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_typescript_files(db: RuleDB) -> set[str]:
    """Get set of TypeScript file paths from database."""
    rows = db.query(Q("files").select("path").where("ext IN ('.ts', '.tsx')"))
    return {row[0] for row in rows}


def _find_explicit_any_types(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find explicit 'any' type annotations using semantic type data."""
    findings = []

    rows = db.query(
        Q("type_annotations")
        .select("file", "line", "symbol_name", "type_annotation", "symbol_kind")
        .where("is_any = 1")
    )

    for file, line, name, type_ann, kind in rows:
        if file not in ts_files:
            continue
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

    assignment_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr IS NOT NULL")
    )

    for file, line, var, expr in assignment_rows:
        if file not in ts_files:
            continue
        if "as any" in expr:
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


def _find_missing_return_types(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find functions without explicit return types using semantic type data."""
    findings = []

    rows = db.query(
        Q("type_annotations")
        .select("file", "line", "symbol_name", "return_type")
        .where("symbol_kind = 'function'")
        .where("(return_type IS NULL OR return_type = '')")
    )

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

    for file, line, name, _return_type in rows:
        if file not in ts_files:
            continue
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


def _find_missing_parameter_types(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find function parameters without type annotations."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
    )

    for file, line, func, args in rows:
        if file not in ts_files:
            continue
        if "function" not in func.lower():
            continue
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


def _find_unsafe_type_assertions(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find unsafe type assertions (as any, as unknown)."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr IS NOT NULL")
    )

    for file, line, var, expr in rows:
        if file not in ts_files:
            continue
        if not any(pattern in expr for pattern in ["as any", "as unknown", "as Function", "<any>"]):
            continue

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


def _find_non_null_assertions(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find non-null assertions (!) that bypass null checks."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "source_expr").where("source_expr IS NOT NULL")
    )

    for file, line, expr in rows:
        if file not in ts_files:
            continue
        if not any(pattern in expr for pattern in ["!.", "!)", "!;"]):
            continue

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


def _find_dangerous_type_patterns(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find dangerous type patterns like Function, Object, {} using semantic type data."""
    findings = []

    dangerous_types = ("Function", "Object", "{}")

    rows = db.query(
        Q("type_annotations")
        .select("file", "line", "symbol_name", "type_annotation")
        .where("type_annotation IS NOT NULL")
    )

    for file, line, name, type_ann in rows:
        if file not in ts_files:
            continue

        for dangerous_type in dangerous_types:
            if (
                type_ann == dangerous_type
                or type_ann == f"{dangerous_type}[]"
                or f"<{dangerous_type}>" in type_ann
            ):
                rule_suffix = dangerous_type.lower().replace("{", "").replace("}", "empty")
                findings.append(
                    StandardFinding(
                        rule_name=f"typescript-dangerous-type-{rule_suffix}",
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


def _find_untyped_json_parse(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find JSON.parse without type validation.

    Uses pre-fetch pattern to avoid N+1 queries.
    """
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where("callee_function IS NOT NULL")
    )

    json_parse_by_file: dict[str, list[int]] = {}
    for file, line, func in rows:
        if file not in ts_files:
            continue
        if "JSON.parse" in func:
            if file not in json_parse_by_file:
                json_parse_by_file[file] = []
            json_parse_by_file[file].append(line)

    if not json_parse_by_file:
        return findings

    assignment_rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where_in("file", list(json_parse_by_file.keys()))
        .where("source_expr IS NOT NULL")
    )

    assignments_by_file_line: dict[str, dict[int, str]] = {}
    for file, line, source_expr in assignment_rows:
        if file not in assignments_by_file_line:
            assignments_by_file_line[file] = {}
        assignments_by_file_line[file][line] = source_expr

    validation_patterns = ("as ", "zod", "joi", "validate")
    for file, json_lines in json_parse_by_file.items():
        file_assignments = assignments_by_file_line.get(file, {})
        for json_line in json_lines:
            has_validation = False
            for check_line in range(json_line, json_line + 6):
                source_expr = file_assignments.get(check_line)
                if source_expr and any(p in source_expr for p in validation_patterns):
                    has_validation = True
                    break

            if not has_validation:
                findings.append(
                    StandardFinding(
                        rule_name="typescript-untyped-json-parse",
                        message="JSON.parse result not validated or typed",
                        file_path=file,
                        line=json_line,
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                        category="type-safety",
                        snippet="JSON.parse(data)",
                        cwe_id="CWE-843",
                    )
                )

    return findings


def _find_untyped_api_responses(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find API calls without typed responses.

    Uses pre-fetch pattern to avoid N+1 queries.
    """
    findings = []

    api_patterns = ("fetch", "axios", "request", "http.get", "http.post", "ajax")

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where("callee_function IS NOT NULL")
    )

    api_calls_by_file: dict[str, list[tuple[int, str]]] = {}
    for file, line, func in rows:
        if file not in ts_files:
            continue
        for pattern in api_patterns:
            if pattern in func:
                if file not in api_calls_by_file:
                    api_calls_by_file[file] = []
                api_calls_by_file[file].append((line, pattern))
                break

    if not api_calls_by_file:
        return findings

    assignment_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where_in("file", list(api_calls_by_file.keys()))
    )

    assignments_by_file: dict[str, list[tuple[int, str, str]]] = {}
    for file, line, target_var, source_expr in assignment_rows:
        if file not in assignments_by_file:
            assignments_by_file[file] = []
        assignments_by_file[file].append((line, target_var or "", source_expr or ""))

    for file, api_calls in api_calls_by_file.items():
        file_assignments = assignments_by_file.get(file, [])
        for api_line, pattern in api_calls:
            has_typing = False
            for assign_line, target_var, source_expr in file_assignments:
                if not (api_line - 2 <= assign_line <= api_line + 10):
                    continue
                if ": " in target_var:
                    has_typing = True
                    break
                if source_expr and (
                    "as " in source_expr or ("<" in source_expr and ">" in source_expr)
                ):
                    has_typing = True
                    break

            if not has_typing:
                findings.append(
                    StandardFinding(
                        rule_name="typescript-untyped-api-response",
                        message=f"API call ({pattern}) without typed response",
                        file_path=file,
                        line=api_line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="type-safety",
                        snippet=f"{pattern}(url)",
                        cwe_id="CWE-843",
                    )
                )

    return findings


def _find_missing_interfaces(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find objects that should have interface definitions."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr IS NOT NULL")
        .where("target_var IS NOT NULL")
        .where("LENGTH(source_expr) > 50")
    )

    for file, line, var, expr in rows:
        if file not in ts_files:
            continue
        if "{" not in expr or "}" not in expr:
            continue
        if ": " in var:
            continue
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


def _find_type_suppression_comments(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find @ts-ignore, @ts-nocheck, and @ts-expect-error comments."""
    findings = []

    suppressions = (
        ("@ts-ignore", Severity.HIGH, Confidence.HIGH),
        ("@ts-nocheck", Severity.CRITICAL, Confidence.HIGH),
        ("@ts-expect-error", Severity.MEDIUM, Confidence.MEDIUM),
    )

    rows = db.query(
        Q("symbols")
        .select("path", "line", "name")
        .where("type = 'comment'")
        .where("name IS NOT NULL")
    )

    for file, line, comment in rows:
        if file not in ts_files:
            continue

        for suppression, severity, confidence in suppressions:
            if suppression in comment:
                rule_suffix = suppression.replace("@", "").replace("-", "_")
                findings.append(
                    StandardFinding(
                        rule_name=f"typescript-suppression-{rule_suffix}",
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


def _find_untyped_catch_blocks(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find catch blocks without typed errors."""
    findings = []

    rows = db.query(Q("symbols").select("path", "line", "name").where("type = 'catch'"))

    for file, line, name in rows:
        if file not in ts_files:
            continue
        if "unknown" in (name or "") or ":" in (name or ""):
            continue

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


def _find_missing_generic_types(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find usage of generic types without type parameters using semantic type data."""
    findings = []

    generic_types = ("Array", "Promise", "Map", "Set", "WeakMap", "WeakSet", "Record")

    for generic in generic_types:
        rows = db.query(
            Q("type_annotations")
            .select("file", "line", "symbol_name", "type_annotation", "type_params")
            .where("type_annotation = ?", generic)
            .where("(is_generic = 0 OR type_params IS NULL OR type_params = '')")
        )

        for file, line, _name, type_ann, _type_params in rows:
            if file not in ts_files:
                continue

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


def _find_untyped_event_handlers(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find event handlers without proper typing."""
    findings = []

    event_patterns = ("onClick", "onChange", "onSubmit", "addEventListener", "on(")

    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function", "argument_expr")
    )

    for file, line, func, args in rows:
        if file not in ts_files:
            continue

        func_str = func or ""
        args_str = args or ""

        for pattern in event_patterns:
            if pattern not in func_str and pattern not in args_str:
                continue

            if "event" in args_str.lower() and ":" not in args_str:
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
                break

    return findings


def _find_unsafe_property_access(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find unsafe property access patterns."""
    findings = []

    rows = db.query(Q("symbols").select("path", "line", "name").where("name IS NOT NULL"))

    for file, line, name in rows:
        if file not in ts_files:
            continue
        if "[" not in name or "]" not in name:
            continue

        if not name.strip().startswith('"') and not name.strip().startswith("'"):
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


def _find_unknown_types(db: RuleDB, ts_files: set[str]) -> list[StandardFinding]:
    """Find 'unknown' types requiring type narrowing using semantic type data."""
    findings = []

    rows = db.query(
        Q("type_annotations")
        .select("file", "line", "symbol_name", "type_annotation", "symbol_kind")
        .where("is_unknown = 1")
    )

    for file, line, name, type_ann, _kind in rows:
        if file not in ts_files:
            continue

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
