"""Dead code detection rule - finds unused modules, functions, and classes.

Two-pronged approach:
1. Module-level: Uses GraphDeadCodeDetector for graph-based analysis of module import relationships
2. Function-level: Uses Q class queries to find defined-but-never-called functions

Schema Contract Compliance: v2.0 (Fidelity Layer)
"""

from pathlib import Path

from theauditor.context.deadcode_graph import DEFAULT_EXCLUSIONS, GraphDeadCodeDetector
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
    name="deadcode",
    category="quality",
    target_extensions=[".py", ".js", ".ts", ".tsx", ".jsx"],
    exclude_patterns=["node_modules/", ".venv/", "__pycache__/", "dist/", "build/"],
    execution_scope="database",
    primary_table="symbols",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect dead code at module and function level.

    Two-pronged detection:
    1. Module-level: GraphDeadCodeDetector finds modules never imported
    2. Function-level: Q class queries find functions defined but never called

    Returns:
        RuleResult with findings for isolated modules and unused functions.
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    findings: list[StandardFinding] = []
    manifest: dict = {}

    # --- Function-level dead code detection (uses RuleDB + Q) ---
    with RuleDB(context.db_path, METADATA.name) as db:
        func_findings = _find_unused_functions(db)
        findings.extend(func_findings)
        manifest["functions_checked"] = db.get_manifest()

    # --- Module-level dead code detection (uses graphs.db) ---
    graphs_db = Path(context.db_path).parent / "graphs.db"

    if graphs_db.exists():
        detector = GraphDeadCodeDetector(str(graphs_db), context.db_path, debug=False)
        modules = detector.analyze(exclude_patterns=DEFAULT_EXCLUSIONS, analyze_symbols=False)

        for module in modules:
            findings.append(
                StandardFinding(
                    rule_name="deadcode-module",
                    message=f"Module never imported: {module.path}",
                    file_path=str(module.path),
                    line=1,
                    severity=Severity.INFO,
                    category="quality",
                    snippet="",
                    additional_info={
                        "type": "isolated_module",
                        "symbol_count": module.symbol_count,
                        "lines_estimated": module.lines_estimated,
                        "confidence": module.confidence,
                        "reason": module.reason,
                        "cluster_id": module.cluster_id,
                    },
                )
            )
        manifest["modules_analyzed"] = len(modules)
        manifest["graphs_db"] = str(graphs_db)
    else:
        manifest["graphs_db_status"] = "not found - module analysis skipped"

    return RuleResult(findings=findings, manifest=manifest)


# =============================================================================
# FUNCTION-LEVEL DEAD CODE DETECTION
# =============================================================================

# Entry points and special functions that should never be flagged as unused
ENTRY_POINT_PATTERNS = frozenset([
    # Python entry points
    "main", "__main__", "__init__", "__new__", "__del__",
    "__enter__", "__exit__", "__call__", "__iter__", "__next__",
    "__getattr__", "__setattr__", "__getitem__", "__setitem__",
    "__len__", "__str__", "__repr__", "__eq__", "__hash__",
    "__lt__", "__le__", "__gt__", "__ge__", "__add__", "__sub__",
    "__mul__", "__truediv__", "__floordiv__", "__mod__", "__pow__",
    # Test functions
    "setUp", "tearDown", "setUpClass", "tearDownClass",
    "setUpModule", "tearDownModule",
    # Framework hooks
    "configure", "setup", "teardown", "initialize", "shutdown",
    "on_startup", "on_shutdown", "lifespan",
    # CLI entry points
    "cli", "app", "run", "execute", "handle",
    # JS/TS exports
    "default", "module.exports",
])

# Patterns that indicate a function is likely an entry point
ENTRY_POINT_PREFIXES = (
    "test_",      # pytest
    "Test",       # unittest
    "handle_",    # event handlers
    "on_",        # event callbacks
    "get_",       # property-like getters often called dynamically
    "set_",       # property-like setters often called dynamically
)


def _find_unused_functions(db: RuleDB) -> list[StandardFinding]:
    """Find functions that are defined but never called.

    Logic:
    1. Query all defined TOP-LEVEL FUNCTIONS from symbols table (not methods)
    2. Query all function calls from function_call_args table
    3. Query identifier references from refs table (catches callbacks)
    4. Compute difference (defined - called - referenced)
    5. Filter out entry points, test functions, and magic methods

    Note: Methods are excluded to avoid false positives from name collisions
    (e.g., User.save() vs Config.save() both matching 'save').
    """
    findings = []

    # Get all defined TOP-LEVEL FUNCTIONS only (exclude methods to avoid name collisions)
    defined_rows = db.query(
        Q("symbols")
        .select("path", "name", "line", "type")
        .where("type = ?", "function")
        .order_by("path, line")
    )

    # Build set of (file, function_name) -> (line, type) for defined functions
    defined_funcs: dict[tuple[str, str], tuple[int, str]] = {}
    for file_path, func_name, line, func_type in defined_rows:
        # Skip entry points and magic methods
        if func_name in ENTRY_POINT_PATTERNS:
            continue
        if any(func_name.startswith(prefix) for prefix in ENTRY_POINT_PREFIXES):
            continue
        # Skip lambda and anonymous functions
        if func_name in ("<lambda>", "<anonymous>", "anonymous"):
            continue

        key = (file_path, func_name)
        # Keep first definition (in case of overloads)
        if key not in defined_funcs:
            defined_funcs[key] = (line, func_type)

    # Get all function calls (exact callee names only - no stripping context)
    called_rows = db.query(
        Q("function_call_args")
        .select("callee_function")
    )

    # Build set of called function names (exact matches only)
    called_names: set[str] = set()
    for (callee,) in called_rows:
        if callee:
            called_names.add(callee)

    # Get all identifier references (catches callbacks passed as arguments)
    ref_rows = db.query(
        Q("refs")
        .select("value")
        .where("kind = ?", "ref")
    )

    # Build set of referenced identifiers
    referenced_names: set[str] = set()
    for (ref_value,) in ref_rows:
        if ref_value:
            # Extract the simple name from qualified refs
            # e.g., "module.function" -> "function"
            if "." in ref_value:
                referenced_names.add(ref_value.split(".")[-1])
            referenced_names.add(ref_value)

    # Find unused functions
    for (file_path, func_name), (line, func_type) in defined_funcs.items():
        # Skip if called directly
        if func_name in called_names:
            continue

        # Skip if referenced as callback/identifier
        if func_name in referenced_names:
            continue

        # Determine confidence based on naming conventions
        is_private = func_name.startswith("_") and not func_name.startswith("__")

        if is_private:
            # Private functions are less likely to be called dynamically
            confidence = Confidence.MEDIUM
            severity = Severity.LOW
        else:
            # Public functions could be entry points we don't detect
            confidence = Confidence.LOW
            severity = Severity.INFO

        findings.append(
            StandardFinding(
                rule_name="deadcode-function",
                message=f"Function '{func_name}' is defined but never called",
                file_path=file_path,
                line=line,
                severity=severity,
                category="quality",
                confidence=confidence,
                snippet="",
                additional_info={
                    "type": "unused_function",
                    "function_type": func_type,
                    "is_private": is_private,
                },
            )
        )

    return findings
