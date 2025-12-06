"""Vue.js reactivity and props mutation analyzer - Database-First Implementation."""

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
    name="vue_reactivity",
    category="vue",
    target_extensions=[".vue", ".js", ".ts"],
    target_file_patterns=["frontend/", "client/", "src/components/", "src/views/"],
    exclude_patterns=["backend/", "server/", "api/", "__tests__/", "*.test.*", "*.spec.*"],
    execution_scope="database",
    primary_table="files",
)


NON_REACTIVE_INITIALIZERS = frozenset(
    ["{}", "[]", "{ }", "[ ]", "new Object()", "new Array()", "Object.create(null)"]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Vue.js reactivity and props mutation issues using database queries."""
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []
        findings.extend(_find_props_mutations(db))
        findings.extend(_find_non_reactive_data(db))
        return RuleResult(findings=findings, manifest=db.get_manifest())


def _find_props_mutations(db: RuleDB) -> list[StandardFinding]:
    """Find direct props mutations using database queries.

    Detects assignments to props.X, this.propName, $props.X patterns
    which violate Vue's one-way data flow principle.
    """
    findings: list[StandardFinding] = []

    vue_files: set[str] = set()

    file_rows = db.query(Q("files").select("path", "ext").where("ext = ?", ".vue"))
    for path, _ext in file_rows:
        vue_files.add(path)

    symbol_rows = db.query(
        Q("symbols")
        .select("path", "name")
        .where("name IN (?, ?, ?)", "defineComponent", "defineProps", "props")
    )
    for path, _name in symbol_rows:
        vue_files.add(path)

    if not vue_files:
        return findings

    for file in vue_files:
        assignment_rows = db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("file = ?", file)
            .where("target_var IS NOT NULL")
            .order_by("line")
        )

        for file_path, line, target, source in assignment_rows:
            is_props_mutation = False
            prop_name = None

            if target.startswith("props.") and "." in target[6:] is False:
                is_props_mutation = True
                prop_name = target[6:].split(".")[0] if "." in target[6:] else target[6:]

            elif ".$props." in target or target.startswith("$props."):
                is_props_mutation = True
                if target.startswith("$props."):
                    prop_name = target[7:].split(".")[0]
                else:
                    idx = target.find(".$props.")
                    prop_name = target[idx + 8 :].split(".")[0]

            if not is_props_mutation:
                continue

            source_str = source or ""
            snippet = (
                f"{target} = {source_str[:50]}..."
                if len(source_str) > 50
                else f"{target} = {source_str}"
            )

            findings.append(
                StandardFinding(
                    rule_name="vue-props-mutation",
                    message=f'Direct mutation of prop "{prop_name}" violates one-way data flow',
                    file_path=file_path,
                    line=line,
                    severity=Severity.HIGH,
                    category="vue",
                    confidence=Confidence.HIGH,
                    snippet=snippet,
                    cwe_id="CWE-915",
                )
            )

    return findings


def _find_non_reactive_data(db: RuleDB) -> list[StandardFinding]:
    """Find non-reactive data initialization in Options API."""
    findings: list[StandardFinding] = []

    vue_files: set[str] = set()

    file_rows = db.query(Q("files").select("path", "ext").where("ext = ?", ".vue"))
    for path, _ext in file_rows:
        vue_files.add(path)

    for file in vue_files:
        data_method_rows = db.query(
            Q("symbols")
            .select("line", "name")
            .where("path = ?", file)
            .where("name = ?", "data")
            .where("type IN (?, ?)", "function", "method")
        )

        data_methods = list(data_method_rows)
        if not data_methods:
            continue

        for data_line, _ in data_methods:
            assignment_rows = db.query(
                Q("assignments")
                .select("line", "target_var", "source_expr", "in_function")
                .where("file = ?", file)
                .where("line BETWEEN ? AND ?", data_line, data_line + 20)
                .where("in_function IS NOT NULL")
            )

            for line, target, source, in_function in assignment_rows:
                if "data" not in in_function.lower():
                    continue

                source_stripped = (source or "").strip()
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
                            severity=Severity.MEDIUM,
                            category="vue",
                            confidence=Confidence.MEDIUM,
                            snippet=f"{target}: {source}",
                            cwe_id="CWE-1188",
                        )
                    )

    return findings
