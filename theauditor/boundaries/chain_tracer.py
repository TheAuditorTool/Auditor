"""Validation Chain Tracer - trace validation through data flow.

Traces validation from entry point through function calls, detecting where
type safety breaks (e.g., `as any` casts, missing type hints).

Chain status values:
- intact: Validation exists at entry AND type preserved through all hops
- broken: Validation exists but type safety lost at intermediate hop
- no_validation: No validation detected at entry point

ZERO FALLBACK: Uses regex pattern matching for type detection.
The is_any boolean flag in type_annotations table is unreliable (only 3 records).
"""

import re
import sqlite3
from dataclasses import dataclass, field

from theauditor.boundaries.boundary_analyzer import _detect_frameworks

# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class ChainHop:
    """A single hop in a validation chain.

    Attributes:
        function: Function name at this hop
        file: File path
        line: Line number
        type_info: Type at this hop (e.g., "CreateUserInput", "any", "unknown")
        validation_status: One of "validated", "preserved", "broken", "unknown"
        break_reason: Why chain broke (e.g., "cast to any"), None if not broken
    """

    function: str
    file: str
    line: int
    type_info: str
    validation_status: str
    break_reason: str | None = None


@dataclass
class ValidationChain:
    """A complete validation chain from entry point through data flow.

    Attributes:
        entry_point: Route/endpoint description (e.g., "POST /users")
        entry_file: File containing the entry point
        entry_line: Line number of entry point
        hops: List of ChainHop objects representing the data flow
        chain_status: One of "intact", "broken", "no_validation"
        break_index: Index in hops list where chain broke, None if intact
    """

    entry_point: str
    entry_file: str
    entry_line: int
    hops: list[ChainHop] = field(default_factory=list)
    chain_status: str = "unknown"
    break_index: int | None = None


# =============================================================================
# TYPE SAFETY DETECTION (REGEX ONLY - NO FALLBACKS)
# =============================================================================

# Word boundaries prevent false positives like "Company", "Germany", "ManyItems"
# Per design.md Decision 2 and CLAUDE.md Section 4 (Zero Fallback Policy)
ANY_TYPE_PATTERNS = [
    re.compile(r":\s*any\b"),  # Type annotation: `: any`
    re.compile(r"\bas\s+any\b"),  # Cast: `as any`
    re.compile(r"<\s*any\s*>"),  # Generic: `<any>`
    re.compile(r"<\s*any\s*,"),  # Generic first: `<any, T>`
    re.compile(r",\s*any\s*>"),  # Generic last: `<T, any>`
    re.compile(r"\|\s*any\b"),  # Union: `| any`
    re.compile(r"\bany\s*\|"),  # Union: `any |`
    re.compile(r"=>\s*any\b"),  # Return type: `=> any`
]

# TypeScript unknown type patterns
UNKNOWN_TYPE_PATTERNS = [
    re.compile(r":\s*unknown\b"),  # Type annotation: `: unknown`
    re.compile(r"\bas\s+unknown\b"),  # Cast: `as unknown`
    re.compile(r"<\s*unknown\s*>"),  # Generic: `<unknown>`
]

# Python type ignore patterns
PYTHON_TYPE_IGNORE_PATTERNS = [
    re.compile(r"#\s*type:\s*ignore"),  # type: ignore comment
    re.compile(r"#\s*noqa"),  # lint suppression (often used with type issues)
]

# Go interface{} pattern (type safety loss)
GO_INTERFACE_PATTERN = re.compile(r"\binterface\s*\{\s*\}")

# Validation library patterns that contain "any" but are SOURCES, not breaks
# z.any(), Joi.any(), yup.mixed() are validation schemas, not type degradation
VALIDATION_ANY_EXCLUSIONS = ["z.any()", "Joi.any()", "yup.mixed()"]


def is_type_unsafe(type_annotation: str | None) -> bool:
    """Check if a type annotation indicates type safety loss.

    Single code path. No fallbacks. Per CLAUDE.md Section 4.

    Args:
        type_annotation: The type annotation string to check

    Returns:
        True if the type contains unsafe patterns (any, unknown, etc.)
        False if the type is safe or unknown (empty/None)
    """
    if not type_annotation:
        return False  # Unknown is not the same as unsafe

    # Check exclusions first - validation sources are not breaks
    for excl in VALIDATION_ANY_EXCLUSIONS:
        if excl in type_annotation:
            return False

    # Check any patterns
    if any(p.search(type_annotation) for p in ANY_TYPE_PATTERNS):
        return True

    # Check unknown patterns (TypeScript)
    return any(p.search(type_annotation) for p in UNKNOWN_TYPE_PATTERNS)


def get_type_break_reason(type_annotation: str | None) -> str | None:
    """Get the reason why a type annotation breaks the validation chain.

    Args:
        type_annotation: The type annotation string to check

    Returns:
        Human-readable reason for the break, or None if no break
    """
    if not type_annotation:
        return None

    # Check exclusions
    for excl in VALIDATION_ANY_EXCLUSIONS:
        if excl in type_annotation:
            return None

    # Check specific patterns and return descriptive reason
    for pattern in ANY_TYPE_PATTERNS:
        if pattern.search(type_annotation):
            if "as" in pattern.pattern:
                return "Cast to any"
            elif ":" in pattern.pattern:
                return "Type annotation is any"
            elif "=>" in pattern.pattern:
                return "Return type is any"
            elif "<" in pattern.pattern or ">" in pattern.pattern:
                return "Generic type parameter is any"
            elif "|" in pattern.pattern:
                return "Union includes any"
            return "Type contains any"

    for pattern in UNKNOWN_TYPE_PATTERNS:
        if pattern.search(type_annotation):
            return "Type is unknown (requires narrowing)"

    return None


def is_python_type_ignored(type_annotation: str | None, source_line: str | None = None) -> bool:
    """Check if Python type checking is disabled for this location.

    Args:
        type_annotation: The type annotation (may contain comment)
        source_line: The full source line (may contain type: ignore comment)

    Returns:
        True if type checking is explicitly disabled
    """
    check_str = (type_annotation or "") + " " + (source_line or "")
    return any(p.search(check_str) for p in PYTHON_TYPE_IGNORE_PATTERNS)


def is_go_interface_empty(type_annotation: str | None) -> bool:
    """Check if Go type is empty interface (interface{}).

    Args:
        type_annotation: The type annotation string

    Returns:
        True if type is interface{} (Go's any equivalent)
    """
    if not type_annotation:
        return False
    return bool(GO_INTERFACE_PATTERN.search(type_annotation))


# =============================================================================
# VALIDATION SOURCE DETECTION
# =============================================================================

# Validation library patterns that indicate validation at entry
VALIDATION_PATTERNS = {
    # TypeScript/JavaScript
    "zod": [
        r"z\.object\(",
        r"\.parse\(",
        r"\.safeParse\(",
        r"z\.string\(",
        r"z\.number\(",
        r"z\.array\(",
        r"z\.infer<",  # Type inference from schema
    ],
    "joi": [
        r"Joi\.object\(",
        r"\.validate\(",
        r"Joi\.string\(",
        r"Joi\.number\(",
    ],
    "yup": [
        r"yup\.object\(",
        r"\.validate\(",
        r"yup\.string\(",
        r"yup\.number\(",
        r"InferType<",  # Yup type inference
    ],
    "io-ts": [
        r"t\.type\(",
        r"\.decode\(",
        r"TypeOf<",  # io-ts type inference
    ],
    "class-validator": [
        r"@IsString\(",
        r"@IsNumber\(",
        r"@IsEmail\(",
        r"@ValidateNested\(",
        r"@IsOptional\(",
        r"@IsNotEmpty\(",
    ],
    "runtypes": [
        r"Record\(",
        r"\.check\(",
        r"Static<",  # runtypes type inference
    ],
    # Python
    "pydantic": [
        r"BaseModel",
        r"@validator\(",
        r"@field_validator\(",
        r"Field\(",
        r"@model_validator\(",
    ],
    "marshmallow": [
        r"Schema",
        r"fields\.",
        r"@validates\(",
        r"@pre_load",
        r"@post_load",
    ],
    "cerberus": [
        r"Validator\(",
        r"\.validate\(",
    ],
    # Go
    "go-validator": [
        r"validate\.Struct\(",
        r"`validate:",
        r"validator\.New\(",
    ],
    "ozzo-validation": [
        r"validation\.ValidateStruct\(",
        r"validation\.Field\(",
    ],
    # Rust
    "validator": [
        r"#\[validate\(",
        r"\.validate\(\)",
    ],
    "garde": [
        r"#\[garde\(",
        r"Garde",
    ],
}

# Validation library output type mapping
# Maps library name to info about the validated output type
VALIDATION_OUTPUT_TYPES = {
    # TypeScript/JavaScript - inferred types
    "zod": {
        "language": "typescript",
        "output_type": "inferred",  # z.infer<typeof Schema>
        "type_safe": True,
        "runtime_validation": True,
    },
    "joi": {
        "language": "typescript",
        "output_type": "manual",  # Requires manual type definition
        "type_safe": False,  # No automatic type inference
        "runtime_validation": True,
    },
    "yup": {
        "language": "typescript",
        "output_type": "inferred",  # InferType<typeof Schema>
        "type_safe": True,
        "runtime_validation": True,
    },
    "io-ts": {
        "language": "typescript",
        "output_type": "inferred",  # TypeOf<typeof Codec>
        "type_safe": True,
        "runtime_validation": True,
    },
    "class-validator": {
        "language": "typescript",
        "output_type": "class",  # Class instance
        "type_safe": True,
        "runtime_validation": True,
    },
    "runtypes": {
        "language": "typescript",
        "output_type": "inferred",  # Static<typeof Runtype>
        "type_safe": True,
        "runtime_validation": True,
    },
    # Python
    "pydantic": {
        "language": "python",
        "output_type": "model",  # Pydantic model instance
        "type_safe": True,
        "runtime_validation": True,
    },
    "marshmallow": {
        "language": "python",
        "output_type": "dict",  # Returns dict by default
        "type_safe": False,  # Unless using dataclass integration
        "runtime_validation": True,
    },
    "cerberus": {
        "language": "python",
        "output_type": "dict",
        "type_safe": False,
        "runtime_validation": True,
    },
    # Go
    "go-validator": {
        "language": "go",
        "output_type": "struct",  # Validates existing struct
        "type_safe": True,  # Go is statically typed
        "runtime_validation": True,
    },
    "ozzo-validation": {
        "language": "go",
        "output_type": "struct",
        "type_safe": True,
        "runtime_validation": True,
    },
    # Rust
    "validator": {
        "language": "rust",
        "output_type": "struct",
        "type_safe": True,  # Rust is statically typed
        "runtime_validation": True,
    },
    "garde": {
        "language": "rust",
        "output_type": "struct",
        "type_safe": True,
        "runtime_validation": True,
    },
}

# Compiled patterns for efficiency
_COMPILED_VALIDATION_PATTERNS: dict[str, list[re.Pattern]] = {}


def _get_validation_patterns() -> dict[str, list[re.Pattern]]:
    """Get compiled validation patterns (lazy initialization)."""
    global _COMPILED_VALIDATION_PATTERNS
    if not _COMPILED_VALIDATION_PATTERNS:
        for lib, patterns in VALIDATION_PATTERNS.items():
            _COMPILED_VALIDATION_PATTERNS[lib] = [re.compile(p) for p in patterns]
    return _COMPILED_VALIDATION_PATTERNS


def detect_validation_library(code_snippet: str) -> str | None:
    """Detect which validation library is used in a code snippet.

    Args:
        code_snippet: Source code to analyze

    Returns:
        Library name (e.g., "zod", "pydantic") or None if no validation detected
    """
    patterns = _get_validation_patterns()
    for lib, lib_patterns in patterns.items():
        for pattern in lib_patterns:
            if pattern.search(code_snippet):
                return lib
    return None


def get_validation_output_info(library: str) -> dict | None:
    """Get information about the output type of a validation library.

    Args:
        library: Name of the validation library

    Returns:
        Dict with output type info, or None if unknown library
    """
    return VALIDATION_OUTPUT_TYPES.get(library)


def is_type_safe_validation(library: str) -> bool:
    """Check if a validation library provides type-safe output.

    Type-safe means the validated data has a known type that the type checker
    can verify, not just `any` or `unknown`.

    Args:
        library: Name of the validation library

    Returns:
        True if the library provides type-safe validated output
    """
    info = VALIDATION_OUTPUT_TYPES.get(library)
    return info.get("type_safe", False) if info else False


def detect_validation_in_chain(
    cursor: sqlite3.Cursor,
    file: str,
    function_name: str,
) -> tuple[str | None, bool]:
    """Detect if a function uses validation and if it's type-safe.

    Queries validation_framework_usage table first, falls back to pattern matching.

    Args:
        cursor: Database cursor
        file: File path
        function_name: Function name to check

    Returns:
        Tuple of (library_name, is_type_safe) or (None, False)
    """
    # Check validation_framework_usage table first
    cursor.execute(
        """
        SELECT framework FROM validation_framework_usage
        WHERE file_path = ? AND is_validator = 1
        LIMIT 1
        """,
        (file,),
    )
    row = cursor.fetchone()
    if row:
        library = row[0].lower()
        return library, is_type_safe_validation(library)

    # No direct match found
    return None, False


# =============================================================================
# CHAIN TRACING - FRAMEWORK DISPATCHER
# =============================================================================


def trace_validation_chains(
    db_path: str, max_entries: int = 50, file_filter: str | None = None
) -> list[ValidationChain]:
    """Trace validation chains for all entry points in the codebase.

    Routes to framework-specific chain tracers based on detected frameworks.
    NO generic if/else chains - framework detection decides which tables to query.

    Args:
        db_path: Path to repo_index.db
        max_entries: Maximum entry points to analyze
        file_filter: Optional file path to filter chains to (for aud explain --validated)

    Returns:
        List of ValidationChain objects
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results: list[ValidationChain] = []

    try:
        # Step 1: Detect frameworks
        frameworks = _detect_frameworks(cursor)

        # Step 2: Route to framework-specific chain tracers
        if "express" in frameworks:
            results.extend(
                _trace_express_chains(cursor, frameworks["express"], max_entries, db_path)
            )

        if "fastapi" in frameworks:
            results.extend(
                _trace_fastapi_chains(cursor, frameworks["fastapi"], max_entries, db_path)
            )

        if "flask" in frameworks:
            results.extend(
                _trace_flask_chains(cursor, frameworks["flask"], max_entries, db_path)
            )

        if "django" in frameworks:
            results.extend(
                _trace_django_chains(cursor, frameworks["django"], max_entries, db_path)
            )

        # Step 3: Generic fallback for remaining entry points (Go/Rust/unknown)
        remaining = max_entries - len(results)
        if remaining > 0:
            results.extend(_trace_generic_chains(cursor, remaining, db_path))

    finally:
        conn.close()

    # Apply file filter if specified (for aud explain --validated)
    if file_filter:
        # Normalize the filter for comparison
        filter_normalized = file_filter.replace("\\", "/").lstrip("./")
        results = [
            chain
            for chain in results
            if filter_normalized in chain.entry_file.replace("\\", "/")
        ]

    return results


def trace_validation_chain(
    entry_file: str, entry_line: int, db_path: str
) -> ValidationChain:
    """Trace validation chain for a single entry point.

    Args:
        entry_file: File containing the entry point
        entry_line: Line number of entry point
        db_path: Path to repo_index.db

    Returns:
        ValidationChain for the entry point
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        frameworks = _detect_frameworks(cursor)

        if "express" in frameworks:
            return _trace_single_express_chain(cursor, entry_file, entry_line, db_path)
        elif "fastapi" in frameworks:
            return _trace_single_fastapi_chain(cursor, entry_file, entry_line, db_path)
        elif "flask" in frameworks:
            return _trace_single_flask_chain(cursor, entry_file, entry_line, db_path)
        elif "django" in frameworks:
            return _trace_single_django_chain(cursor, entry_file, entry_line, db_path)
        else:
            return _trace_single_generic_chain(cursor, entry_file, entry_line, db_path)

    finally:
        conn.close()


# =============================================================================
# FRAMEWORK-SPECIFIC CHAIN TRACERS
# =============================================================================

# Validation middleware patterns for Express
EXPRESS_VALIDATION_MIDDLEWARE = [
    "validate",
    "validateBody",
    "validateParams",
    "validateQuery",
    "zodMiddleware",
    "joiMiddleware",
    "yupMiddleware",
]

# Django middleware patterns that provide validation/security
DJANGO_VALIDATION_MIDDLEWARE = [
    "csrfviewmiddleware",
    "authenticationmiddleware",
    "sessionmiddleware",
    "securitymiddleware",
    "xframeoptions",
    "contenttype",
    "validation",
    "sanitize",
    "permission",
]

# Django decorator patterns that indicate security controls
DJANGO_SECURITY_DECORATORS = [
    "login_required",
    "permission_required",
    "user_passes_test",
    "csrf_protect",
    "require_http_methods",
    "require_post",
    "require_get",
]


def _get_type_annotation(
    cursor: sqlite3.Cursor, file: str, line: int, symbol_name: str | None = None
) -> str | None:
    """Get type annotation for a symbol at a specific location.

    Args:
        cursor: Database cursor
        file: File path
        line: Line number
        symbol_name: Optional symbol name to filter

    Returns:
        Type annotation string or None
    """
    if symbol_name:
        cursor.execute(
            """
            SELECT type_annotation FROM type_annotations
            WHERE file = ? AND line = ? AND symbol_name = ?
            LIMIT 1
            """,
            (file, line, symbol_name),
        )
    else:
        cursor.execute(
            """
            SELECT type_annotation FROM type_annotations
            WHERE file = ? AND line = ?
            LIMIT 1
            """,
            (file, line),
        )
    row = cursor.fetchone()
    return row[0] if row else None


def _get_callees_from_function(
    cursor: sqlite3.Cursor, file: str, caller_function: str, max_depth: int = 10
) -> list[dict]:
    """Get callees from a function using function_call_args table.

    Returns list of {callee_function, callee_file, callee_line} dicts.
    Uses BFS traversal with depth limit.
    """
    callees = []
    visited = set()
    queue = [(file, caller_function, 0)]

    while queue:
        current_file, current_func, depth = queue.pop(0)
        if depth >= max_depth:
            continue

        key = (current_file, current_func)
        if key in visited:
            continue
        visited.add(key)

        # Get direct callees
        cursor.execute(
            """
            SELECT DISTINCT callee_function, callee_file_path
            FROM function_call_args
            WHERE file = ? AND caller_function = ?
            AND callee_function IS NOT NULL
            """,
            (current_file, current_func),
        )

        for callee_func, callee_file in cursor.fetchall():
            # Get line number from symbols table
            callee_line = None
            if callee_file:
                cursor.execute(
                    """
                    SELECT line FROM symbols
                    WHERE path = ? AND name = ? AND type IN ('function', 'method', 'arrow_function')
                    LIMIT 1
                    """,
                    (callee_file, callee_func),
                )
                row = cursor.fetchone()
                callee_line = row[0] if row else None

            callees.append({
                "function": callee_func,
                "file": callee_file or current_file,
                "line": callee_line or 0,
                "depth": depth + 1,
            })

            # Add to queue for further traversal if we have file info
            if callee_file:
                queue.append((callee_file, callee_func, depth + 1))

    return callees


def _trace_express_chains(
    cursor: sqlite3.Cursor,
    framework_info: list[dict],
    max_entries: int,
    db_path: str,
) -> list[ValidationChain]:
    """Trace validation chains for Express.js entry points.

    Uses:
    - express_middleware_chains for entry points and middleware
    - validation_framework_usage for Zod/Joi detection
    - type_annotations for type info (TypeScript)
    """
    results: list[ValidationChain] = []

    # Get unique routes from express_middleware_chains
    cursor.execute(
        """
        SELECT DISTINCT file, route_line, route_path, route_method
        FROM express_middleware_chains
        LIMIT ?
        """,
        (max_entries,),
    )
    routes = cursor.fetchall()

    for file, route_line, route_path, route_method in routes:
        entry_point = f"{route_method or 'GET'} {route_path}"

        # Get the middleware chain for this route
        cursor.execute(
            """
            SELECT execution_order, handler_expr, handler_type, handler_function
            FROM express_middleware_chains
            WHERE file = ? AND route_line = ?
            ORDER BY execution_order ASC
            """,
            (file, route_line),
        )
        chain_rows = cursor.fetchall()

        # Build the validation chain
        hops: list[ChainHop] = []
        chain_status = "no_validation"
        break_index: int | None = None
        has_validation = False
        controller_function: str | None = None

        for _exec_order, handler_expr, handler_type, handler_func in chain_rows:
            # Check if this is a validation middleware
            is_validation_middleware = False
            if handler_type == "middleware" and handler_expr:
                handler_lower = handler_expr.lower()
                is_validation_middleware = any(
                    pat.lower() in handler_lower for pat in EXPRESS_VALIDATION_MIDDLEWARE
                )

            # Get type annotation for this position
            type_info = _get_type_annotation(cursor, file, route_line) or "unknown"

            if handler_type == "middleware":
                if is_validation_middleware:
                    has_validation = True
                    chain_status = "intact"
                    hops.append(ChainHop(
                        function=handler_expr or "middleware",
                        file=file,
                        line=route_line,
                        type_info="validated",
                        validation_status="validated",
                        break_reason=None,
                    ))
                else:
                    # Non-validation middleware
                    status = "preserved" if has_validation else "unknown"
                    hops.append(ChainHop(
                        function=handler_expr or "middleware",
                        file=file,
                        line=route_line,
                        type_info=type_info,
                        validation_status=status,
                        break_reason=None,
                    ))

            elif handler_type == "controller":
                controller_function = handler_func
                # Check type annotation for controller
                type_info = _get_type_annotation(cursor, file, route_line) or "unknown"

                # Check if type is unsafe
                if is_type_unsafe(type_info):
                    break_reason = get_type_break_reason(type_info)
                    if has_validation and chain_status == "intact":
                        chain_status = "broken"
                        break_index = len(hops)
                    hops.append(ChainHop(
                        function=handler_func or "controller",
                        file=file,
                        line=route_line,
                        type_info=type_info,
                        validation_status="broken",
                        break_reason=break_reason,
                    ))
                else:
                    status = "preserved" if has_validation else "unknown"
                    hops.append(ChainHop(
                        function=handler_func or "controller",
                        file=file,
                        line=route_line,
                        type_info=type_info,
                        validation_status=status,
                        break_reason=None,
                    ))

        # Trace through callees from controller if we have one
        if controller_function and chain_status == "intact":
            callees = _get_callees_from_function(cursor, file, controller_function, max_depth=5)
            for callee in callees:
                type_info = _get_type_annotation(
                    cursor, callee["file"], callee["line"], callee["function"]
                ) or "unknown"

                if is_type_unsafe(type_info):
                    break_reason = get_type_break_reason(type_info)
                    chain_status = "broken"
                    break_index = len(hops)
                    hops.append(ChainHop(
                        function=callee["function"],
                        file=callee["file"],
                        line=callee["line"],
                        type_info=type_info,
                        validation_status="broken",
                        break_reason=break_reason,
                    ))
                    break  # Stop at first break
                else:
                    hops.append(ChainHop(
                        function=callee["function"],
                        file=callee["file"],
                        line=callee["line"],
                        type_info=type_info,
                        validation_status="preserved",
                        break_reason=None,
                    ))

        results.append(ValidationChain(
            entry_point=entry_point,
            entry_file=file,
            entry_line=route_line,
            hops=hops,
            chain_status=chain_status,
            break_index=break_index,
        ))

    return results


def _trace_fastapi_chains(
    cursor: sqlite3.Cursor,
    framework_info: list[dict],
    max_entries: int,
    db_path: str,
) -> list[ValidationChain]:
    """Trace validation chains for FastAPI entry points.

    Uses:
    - python_routes for entry points
    - type_annotations for Pydantic model types
    - function_call_args for call chain
    """
    results: list[ValidationChain] = []

    # Get routes from python_routes
    cursor.execute(
        """
        SELECT file, line, method, pattern, handler_function
        FROM python_routes
        WHERE framework = 'fastapi'
        LIMIT ?
        """,
        (max_entries,),
    )
    routes = cursor.fetchall()

    for file, line, method, pattern, handler_function in routes:
        entry_point = f"{method or 'GET'} {pattern or '/'}"

        # Check if handler has Pydantic type hints (validation at entry)
        has_validation = False
        type_info = "unknown"

        # Check type annotations for the handler function parameters
        cursor.execute(
            """
            SELECT type_annotation FROM type_annotations
            WHERE file = ? AND symbol_name = ?
            """,
            (file, handler_function),
        )
        type_rows = cursor.fetchall()

        for (type_ann,) in type_rows:
            if type_ann and ("BaseModel" in type_ann or "Pydantic" in type_ann.lower()):
                has_validation = True
                type_info = type_ann
                break

        hops: list[ChainHop] = []
        chain_status = "intact" if has_validation else "no_validation"
        break_index: int | None = None

        # Entry hop
        hops.append(ChainHop(
            function=handler_function or "handler",
            file=file,
            line=line,
            type_info=type_info,
            validation_status="validated" if has_validation else "unknown",
            break_reason=None,
        ))

        # Trace callees
        if handler_function and has_validation:
            callees = _get_callees_from_function(cursor, file, handler_function, max_depth=5)
            for callee in callees:
                callee_type = _get_type_annotation(
                    cursor, callee["file"], callee["line"], callee["function"]
                ) or "unknown"

                # Check for type: ignore comments (Python-specific)
                if is_python_type_ignored(callee_type):
                    chain_status = "broken"
                    break_index = len(hops)
                    hops.append(ChainHop(
                        function=callee["function"],
                        file=callee["file"],
                        line=callee["line"],
                        type_info=callee_type,
                        validation_status="broken",
                        break_reason="Type checking disabled (type: ignore)",
                    ))
                    break
                else:
                    hops.append(ChainHop(
                        function=callee["function"],
                        file=callee["file"],
                        line=callee["line"],
                        type_info=callee_type,
                        validation_status="preserved",
                        break_reason=None,
                    ))

        results.append(ValidationChain(
            entry_point=entry_point,
            entry_file=file,
            entry_line=line,
            hops=hops,
            chain_status=chain_status,
            break_index=break_index,
        ))

    return results


def _trace_flask_chains(
    cursor: sqlite3.Cursor,
    framework_info: list[dict],
    max_entries: int,
    db_path: str,
) -> list[ValidationChain]:
    """Trace validation chains for Flask entry points.

    Flask doesn't have built-in validation like FastAPI/Pydantic,
    so we look for explicit validation calls (marshmallow, cerberus, etc).
    """
    results: list[ValidationChain] = []

    # Get routes from python_routes
    cursor.execute(
        """
        SELECT file, line, method, pattern, handler_function
        FROM python_routes
        WHERE framework = 'flask'
        LIMIT ?
        """,
        (max_entries,),
    )
    routes = cursor.fetchall()

    for file, line, method, pattern, handler_function in routes:
        entry_point = f"{method or 'GET'} {pattern or '/'}"

        # Check for validation calls in the handler's call chain
        has_validation = False
        hops: list[ChainHop] = []
        chain_status = "no_validation"
        break_index: int | None = None

        # Entry hop
        type_info = _get_type_annotation(cursor, file, line, handler_function) or "unknown"
        hops.append(ChainHop(
            function=handler_function or "handler",
            file=file,
            line=line,
            type_info=type_info,
            validation_status="unknown",
            break_reason=None,
        ))

        # Check callees for validation patterns
        if handler_function:
            callees = _get_callees_from_function(cursor, file, handler_function, max_depth=5)
            for callee in callees:
                callee_lower = callee["function"].lower()
                # Check if this is a validation call
                is_validation = any(
                    pat in callee_lower
                    for pat in ["validate", "parse", "load", "schema"]
                )

                if is_validation and not has_validation:
                    has_validation = True
                    chain_status = "intact"
                    # Update first hop
                    hops[0] = ChainHop(
                        function=hops[0].function,
                        file=hops[0].file,
                        line=hops[0].line,
                        type_info=hops[0].type_info,
                        validation_status="validated",
                        break_reason=None,
                    )

                callee_type = _get_type_annotation(
                    cursor, callee["file"], callee["line"], callee["function"]
                ) or "unknown"

                hops.append(ChainHop(
                    function=callee["function"],
                    file=callee["file"],
                    line=callee["line"],
                    type_info=callee_type,
                    validation_status="preserved" if has_validation else "unknown",
                    break_reason=None,
                ))

        results.append(ValidationChain(
            entry_point=entry_point,
            entry_file=file,
            entry_line=line,
            hops=hops,
            chain_status=chain_status,
            break_index=break_index,
        ))

    return results


def _trace_django_chains(
    cursor: sqlite3.Cursor,
    framework_info: list[dict],
    max_entries: int,
    db_path: str,
) -> list[ValidationChain]:
    """Trace validation chains for Django entry points.

    Django's validation architecture:
    1. Global middleware (MIDDLEWARE setting) - runs BEFORE views
       - Middleware with process_request runs before URL dispatch
       - Middleware with process_view runs after URL dispatch
    2. View decorators (@login_required, @csrf_protect, etc.)
    3. View permission checks (has_permission_check in class-based views)
    4. In-view validation (forms, serializers, manual checks)

    Uses:
    - python_django_middleware for global middleware
    - python_decorators for view decorators
    - python_django_views for CBV permission checks
    - python_routes for entry points (framework='django')
    """
    results: list[ValidationChain] = []

    # Step 1: Get global middleware (applies to ALL routes)
    global_middleware = []
    cursor.execute("""
        SELECT file, line, middleware_class_name,
               has_process_request, has_process_view
        FROM python_django_middleware
    """)
    for row in cursor.fetchall():
        file, line, class_name, has_req, has_view = row
        middleware_lower = class_name.lower() if class_name else ""

        is_validation = any(
            pat in middleware_lower for pat in DJANGO_VALIDATION_MIDDLEWARE
        )

        global_middleware.append({
            "file": file,
            "line": line,
            "class_name": class_name,
            "has_process_request": bool(has_req),
            "has_process_view": bool(has_view),
            "is_validation": is_validation,
        })

    # Step 2: Get Django entry points
    # First try python_routes, then derive from decorated views
    cursor.execute("""
        SELECT file, line, pattern, method, handler_function
        FROM python_routes
        WHERE framework = 'django'
        LIMIT ?
    """, (max_entries,))
    routes = [(r[0], r[1], r[2], r[3], r[4]) for r in cursor.fetchall()]

    # If no routes in python_routes, derive from Django-decorated view functions
    if not routes:
        django_view_decorators = (
            "csrf_exempt", "csrf_protect", "require_http_methods",
            "require_POST", "require_GET", "require_safe",
            "login_required", "permission_required", "user_passes_test",
        )
        placeholders = ",".join("?" * len(django_view_decorators))
        cursor.execute(f"""
            SELECT DISTINCT d.file, MIN(d.line) as line, d.target_name
            FROM python_decorators d
            WHERE d.decorator_name IN ({placeholders})
              AND d.target_type = 'function'
            GROUP BY d.file, d.target_name
            ORDER BY d.file, line
            LIMIT ?
        """, (*django_view_decorators, max_entries))

        for file, line, handler_function in cursor.fetchall():
            pattern = f"/{handler_function.replace('_', '-')}"
            routes.append((file, line, pattern, "ANY", handler_function))

    for file, line, pattern, method, handler_function in routes:
        entry_point = f"{method or 'GET'} {pattern or '/'}"

        hops: list[ChainHop] = []
        chain_status = "no_validation"
        break_index: int | None = None
        has_validation = False

        # Step 3: Add middleware hops (distance 0-1)
        for mw in global_middleware:
            if mw["is_validation"]:
                if mw["has_process_request"]:
                    has_validation = True
                    chain_status = "intact"
                    hops.append(ChainHop(
                        function=mw["class_name"],
                        file=mw["file"],
                        line=mw["line"],
                        type_info="middleware",
                        validation_status="validated",
                        break_reason=None,
                    ))
                elif mw["has_process_view"]:
                    has_validation = True
                    if chain_status != "intact":
                        chain_status = "intact"
                    hops.append(ChainHop(
                        function=mw["class_name"],
                        file=mw["file"],
                        line=mw["line"],
                        type_info="middleware",
                        validation_status="validated",
                        break_reason=None,
                    ))

        # Step 4: Check view decorators (distance 2)
        if handler_function:
            cursor.execute("""
                SELECT decorator_name, line
                FROM python_decorators
                WHERE file = ? AND target_name = ?
            """, (file, handler_function))

            for dec_name, dec_line in cursor.fetchall():
                dec_lower = dec_name.lower() if dec_name else ""
                is_security_decorator = any(
                    pat in dec_lower for pat in DJANGO_SECURITY_DECORATORS
                )
                if is_security_decorator:
                    has_validation = True
                    if chain_status != "intact":
                        chain_status = "intact"
                    hops.append(ChainHop(
                        function=f"@{dec_name}",
                        file=file,
                        line=dec_line,
                        type_info="decorator",
                        validation_status="validated",
                        break_reason=None,
                    ))

        # Step 5: Check class-based view permission checks
        cursor.execute("""
            SELECT view_class_name, has_permission_check
            FROM python_django_views
            WHERE file = ? AND line = ?
        """, (file, line))
        view_row = cursor.fetchone()
        if view_row and view_row[1]:  # has_permission_check
            has_validation = True
            if chain_status != "intact":
                chain_status = "intact"
            hops.append(ChainHop(
                function=f"{view_row[0]}.has_permission",
                file=file,
                line=line,
                type_info="permission_check",
                validation_status="validated",
                break_reason=None,
            ))

        # Step 6: Add handler hop
        type_info = _get_type_annotation(cursor, file, line, handler_function) or "unknown"

        # Check for type: ignore comments (Python-specific)
        if is_python_type_ignored(type_info):
            if has_validation:
                chain_status = "broken"
                break_index = len(hops)
            hops.append(ChainHop(
                function=handler_function or "handler",
                file=file,
                line=line,
                type_info=type_info,
                validation_status="broken",
                break_reason="Type checking disabled (type: ignore)",
            ))
        else:
            hops.append(ChainHop(
                function=handler_function or "handler",
                file=file,
                line=line,
                type_info=type_info,
                validation_status="preserved" if has_validation else "unknown",
                break_reason=None,
            ))

        # Step 7: Trace callees from handler
        if handler_function and chain_status == "intact":
            callees = _get_callees_from_function(cursor, file, handler_function, max_depth=5)
            for callee in callees:
                callee_type = _get_type_annotation(
                    cursor, callee["file"], callee["line"], callee["function"]
                ) or "unknown"

                if is_python_type_ignored(callee_type):
                    chain_status = "broken"
                    break_index = len(hops)
                    hops.append(ChainHop(
                        function=callee["function"],
                        file=callee["file"],
                        line=callee["line"],
                        type_info=callee_type,
                        validation_status="broken",
                        break_reason="Type checking disabled (type: ignore)",
                    ))
                    break
                else:
                    hops.append(ChainHop(
                        function=callee["function"],
                        file=callee["file"],
                        line=callee["line"],
                        type_info=callee_type,
                        validation_status="preserved",
                        break_reason=None,
                    ))

        results.append(ValidationChain(
            entry_point=entry_point,
            entry_file=file,
            entry_line=line,
            hops=hops,
            chain_status=chain_status,
            break_index=break_index,
        ))

    return results


def _trace_generic_chains(
    cursor: sqlite3.Cursor,
    max_entries: int,
    db_path: str,
) -> list[ValidationChain]:
    """Trace validation chains for generic entry points (Go/Rust/unknown).

    Uses BFS traversal of function_call_args table.
    Queries symbols table for type info.
    Looks for entry points from go_routes, rust_attributes, or api_endpoints.
    """
    results: list[ValidationChain] = []

    # Try Go routes first
    cursor.execute(
        """
        SELECT file, line, path, method
        FROM go_routes
        WHERE path IS NOT NULL
        LIMIT ?
        """,
        (max_entries // 2,),
    )
    go_routes = cursor.fetchall()

    for file, line, path, method in go_routes:
        entry_point = f"{method or 'GET'} {path}"

        # Get containing function
        cursor.execute(
            """
            SELECT name FROM symbols
            WHERE path = ? AND line <= ? AND type IN ('function', 'method')
            ORDER BY line DESC LIMIT 1
            """,
            (file, line),
        )
        row = cursor.fetchone()
        handler_function = row[0] if row else None

        hops: list[ChainHop] = []
        chain_status = "no_validation"
        break_index: int | None = None
        has_validation = False

        # Entry hop
        type_info = _get_type_annotation(cursor, file, line, handler_function) or "unknown"

        # Check for Go interface{} type safety loss
        if is_go_interface_empty(type_info):
            chain_status = "broken"
            break_index = 0
            hops.append(ChainHop(
                function=handler_function or "handler",
                file=file,
                line=line,
                type_info=type_info,
                validation_status="broken",
                break_reason="Type is interface{} (no type safety)",
            ))
        else:
            hops.append(ChainHop(
                function=handler_function or "handler",
                file=file,
                line=line,
                type_info=type_info,
                validation_status="unknown",
                break_reason=None,
            ))

        # Check callees for validation
        if handler_function:
            callees = _get_callees_from_function(cursor, file, handler_function, max_depth=5)
            for callee in callees:
                callee_lower = callee["function"].lower()
                is_validation = "validate" in callee_lower or "bind" in callee_lower

                if is_validation and not has_validation:
                    has_validation = True
                    chain_status = "intact"
                    hops[0] = ChainHop(
                        function=hops[0].function,
                        file=hops[0].file,
                        line=hops[0].line,
                        type_info=hops[0].type_info,
                        validation_status="validated",
                        break_reason=None,
                    )

                callee_type = _get_type_annotation(
                    cursor, callee["file"], callee["line"], callee["function"]
                ) or "unknown"

                if is_go_interface_empty(callee_type) and has_validation:
                    chain_status = "broken"
                    break_index = len(hops)
                    hops.append(ChainHop(
                        function=callee["function"],
                        file=callee["file"],
                        line=callee["line"],
                        type_info=callee_type,
                        validation_status="broken",
                        break_reason="Type is interface{} (no type safety)",
                    ))
                    break
                else:
                    hops.append(ChainHop(
                        function=callee["function"],
                        file=callee["file"],
                        line=callee["line"],
                        type_info=callee_type,
                        validation_status="preserved" if has_validation else "unknown",
                        break_reason=None,
                    ))

        results.append(ValidationChain(
            entry_point=entry_point,
            entry_file=file,
            entry_line=line,
            hops=hops,
            chain_status=chain_status,
            break_index=break_index,
        ))

    # Try Rust routes from attributes
    remaining = max_entries - len(results)
    if remaining > 0:
        cursor.execute(
            """
            SELECT file_path, target_line, args, attribute_name
            FROM rust_attributes
            WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route')
            AND args IS NOT NULL
            LIMIT ?
            """,
            (remaining,),
        )
        rust_routes = cursor.fetchall()

        for file, line, args, attr_name in rust_routes:
            entry_point = f"{attr_name.upper()} {args}"

            # Get containing function
            cursor.execute(
                """
                SELECT name FROM symbols
                WHERE path = ? AND line >= ? AND type = 'function'
                ORDER BY line ASC LIMIT 1
                """,
                (file, line),
            )
            row = cursor.fetchone()
            handler_function = row[0] if row else None

            hops: list[ChainHop] = []
            type_info = _get_type_annotation(cursor, file, line or 0, handler_function) or "unknown"

            hops.append(ChainHop(
                function=handler_function or "handler",
                file=file,
                line=line or 0,
                type_info=type_info,
                validation_status="unknown",
                break_reason=None,
            ))

            # Rust typically has strong types, so we assume intact unless we find issues
            results.append(ValidationChain(
                entry_point=entry_point,
                entry_file=file,
                entry_line=line or 0,
                hops=hops,
                chain_status="no_validation",  # Would need deeper analysis
                break_index=None,
            ))

    return results


def _trace_single_express_chain(
    cursor: sqlite3.Cursor,
    entry_file: str,
    entry_line: int,
    db_path: str,
) -> ValidationChain:
    """Trace validation chain for a single Express entry point."""
    # Get route info for this entry point
    cursor.execute(
        """
        SELECT route_path, route_method
        FROM express_middleware_chains
        WHERE file = ? AND route_line = ?
        LIMIT 1
        """,
        (entry_file, entry_line),
    )
    row = cursor.fetchone()
    if not row:
        return ValidationChain(
            entry_point=f"Express entry at {entry_file}:{entry_line}",
            entry_file=entry_file,
            entry_line=entry_line,
            chain_status="unknown",
        )

    # Use the batch function with a filter
    chains = _trace_express_chains(cursor, [], 1, db_path)
    # Find matching chain
    for chain in chains:
        if chain.entry_file == entry_file and chain.entry_line == entry_line:
            return chain

    return ValidationChain(
        entry_point=f"{row[1] or 'GET'} {row[0]}",
        entry_file=entry_file,
        entry_line=entry_line,
        chain_status="unknown",
    )


def _trace_single_fastapi_chain(
    cursor: sqlite3.Cursor,
    entry_file: str,
    entry_line: int,
    db_path: str,
) -> ValidationChain:
    """Trace validation chain for a single FastAPI entry point."""
    cursor.execute(
        """
        SELECT method, pattern, handler_function
        FROM python_routes
        WHERE file = ? AND line = ? AND framework = 'fastapi'
        LIMIT 1
        """,
        (entry_file, entry_line),
    )
    row = cursor.fetchone()
    if not row:
        return ValidationChain(
            entry_point=f"FastAPI entry at {entry_file}:{entry_line}",
            entry_file=entry_file,
            entry_line=entry_line,
            chain_status="unknown",
        )

    method, pattern, handler_function = row
    entry_point = f"{method or 'GET'} {pattern or '/'}"

    # Check for Pydantic validation
    has_validation = False
    type_info = "unknown"

    cursor.execute(
        """
        SELECT type_annotation FROM type_annotations
        WHERE file = ? AND symbol_name = ?
        """,
        (entry_file, handler_function),
    )
    for (type_ann,) in cursor.fetchall():
        if type_ann and ("BaseModel" in type_ann or "Pydantic" in type_ann.lower()):
            has_validation = True
            type_info = type_ann
            break

    hops = [ChainHop(
        function=handler_function or "handler",
        file=entry_file,
        line=entry_line,
        type_info=type_info,
        validation_status="validated" if has_validation else "unknown",
        break_reason=None,
    )]

    return ValidationChain(
        entry_point=entry_point,
        entry_file=entry_file,
        entry_line=entry_line,
        hops=hops,
        chain_status="intact" if has_validation else "no_validation",
        break_index=None,
    )


def _trace_single_flask_chain(
    cursor: sqlite3.Cursor,
    entry_file: str,
    entry_line: int,
    db_path: str,
) -> ValidationChain:
    """Trace validation chain for a single Flask entry point."""
    cursor.execute(
        """
        SELECT method, pattern, handler_function
        FROM python_routes
        WHERE file = ? AND line = ? AND framework = 'flask'
        LIMIT 1
        """,
        (entry_file, entry_line),
    )
    row = cursor.fetchone()
    if not row:
        return ValidationChain(
            entry_point=f"Flask entry at {entry_file}:{entry_line}",
            entry_file=entry_file,
            entry_line=entry_line,
            chain_status="unknown",
        )

    method, pattern, handler_function = row
    entry_point = f"{method or 'GET'} {pattern or '/'}"

    type_info = _get_type_annotation(cursor, entry_file, entry_line, handler_function) or "unknown"

    hops = [ChainHop(
        function=handler_function or "handler",
        file=entry_file,
        line=entry_line,
        type_info=type_info,
        validation_status="unknown",
        break_reason=None,
    )]

    return ValidationChain(
        entry_point=entry_point,
        entry_file=entry_file,
        entry_line=entry_line,
        hops=hops,
        chain_status="no_validation",
        break_index=None,
    )


def _trace_single_django_chain(
    cursor: sqlite3.Cursor,
    entry_file: str,
    entry_line: int,
    db_path: str,
) -> ValidationChain:
    """Trace validation chain for a single Django entry point."""
    # First try python_routes
    cursor.execute(
        """
        SELECT method, pattern, handler_function
        FROM python_routes
        WHERE file = ? AND line = ? AND framework = 'django'
        LIMIT 1
        """,
        (entry_file, entry_line),
    )
    row = cursor.fetchone()

    if row:
        method, pattern, handler_function = row
    else:
        # Try to get from decorated function at this location
        cursor.execute(
            """
            SELECT target_name FROM python_decorators
            WHERE file = ? AND line = ?
            LIMIT 1
            """,
            (entry_file, entry_line),
        )
        dec_row = cursor.fetchone()
        if dec_row:
            handler_function = dec_row[0]
            pattern = f"/{handler_function.replace('_', '-')}"
            method = "ANY"
        else:
            return ValidationChain(
                entry_point=f"Django entry at {entry_file}:{entry_line}",
                entry_file=entry_file,
                entry_line=entry_line,
                chain_status="unknown",
            )

    entry_point = f"{method or 'GET'} {pattern or '/'}"

    # Check for global middleware validation
    has_validation = False
    hops: list[ChainHop] = []

    # Check python_django_middleware
    cursor.execute("""
        SELECT middleware_class_name, file, line, has_process_request, has_process_view
        FROM python_django_middleware
    """)
    for mw_name, mw_file, mw_line, has_req, has_view in cursor.fetchall():
        mw_lower = mw_name.lower() if mw_name else ""
        is_validation = any(pat in mw_lower for pat in DJANGO_VALIDATION_MIDDLEWARE)
        if is_validation and (has_req or has_view):
            has_validation = True
            hops.append(ChainHop(
                function=mw_name,
                file=mw_file,
                line=mw_line,
                type_info="middleware",
                validation_status="validated",
                break_reason=None,
            ))

    # Check decorators
    if handler_function:
        cursor.execute("""
            SELECT decorator_name, line
            FROM python_decorators
            WHERE file = ? AND target_name = ?
        """, (entry_file, handler_function))
        for dec_name, dec_line in cursor.fetchall():
            dec_lower = dec_name.lower() if dec_name else ""
            if any(pat in dec_lower for pat in DJANGO_SECURITY_DECORATORS):
                has_validation = True
                hops.append(ChainHop(
                    function=f"@{dec_name}",
                    file=entry_file,
                    line=dec_line,
                    type_info="decorator",
                    validation_status="validated",
                    break_reason=None,
                ))

    # Add handler hop
    type_info = _get_type_annotation(cursor, entry_file, entry_line, handler_function) or "unknown"
    hops.append(ChainHop(
        function=handler_function or "handler",
        file=entry_file,
        line=entry_line,
        type_info=type_info,
        validation_status="preserved" if has_validation else "unknown",
        break_reason=None,
    ))

    return ValidationChain(
        entry_point=entry_point,
        entry_file=entry_file,
        entry_line=entry_line,
        hops=hops,
        chain_status="intact" if has_validation else "no_validation",
        break_index=None,
    )


def _trace_single_generic_chain(
    cursor: sqlite3.Cursor,
    entry_file: str,
    entry_line: int,
    db_path: str,
) -> ValidationChain:
    """Trace validation chain for a single generic entry point."""
    # Get containing function
    cursor.execute(
        """
        SELECT name FROM symbols
        WHERE path = ? AND line <= ? AND type IN ('function', 'method')
        ORDER BY line DESC LIMIT 1
        """,
        (entry_file, entry_line),
    )
    row = cursor.fetchone()
    handler_function = row[0] if row else "unknown"

    type_info = _get_type_annotation(cursor, entry_file, entry_line, handler_function) or "unknown"

    hops = [ChainHop(
        function=handler_function,
        file=entry_file,
        line=entry_line,
        type_info=type_info,
        validation_status="unknown",
        break_reason=None,
    )]

    return ValidationChain(
        entry_point=f"Entry at {entry_file}:{entry_line}",
        entry_file=entry_file,
        entry_line=entry_line,
        hops=hops,
        chain_status="unknown",
    )
