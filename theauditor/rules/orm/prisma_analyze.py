"""Prisma ORM Analyzer - Database-First Approach.

Detects Prisma ORM anti-patterns and performance issues using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels
"""

import sqlite3

from theauditor.indexer.schema import build_query
from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="prisma_orm_issues",
    category="orm",
    target_extensions=[".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs"],
    exclude_patterns=[
        "__tests__/",
        "test/",
        "tests/",
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        "migrations/",
        "prisma/migrations/",
        ".pf/",
        ".auditor_venv/",
    ],
    requires_jsx_pass=False,
)


UNBOUNDED_METHODS = frozenset(["findMany", "findManyRaw", "aggregateRaw"])


WRITE_METHODS = frozenset(
    [
        "create",
        "createMany",
        "update",
        "updateMany",
        "delete",
        "deleteMany",
        "upsert",
        "deleteMany",
        "executeRaw",
        "executeRawUnsafe",
        "createManyAndReturn",
    ]
)


THROW_METHODS = frozenset(
    [
        "findUniqueOrThrow",
        "findFirstOrThrow",
        "findManyOrThrow",
        "deleteOrThrow",
        "updateOrThrow",
        "upsertOrThrow",
    ]
)


RAW_QUERY_METHODS = frozenset(
    [
        "$queryRaw",
        "$queryRawUnsafe",
        "$executeRaw",
        "$executeRawUnsafe",
        "queryRaw",
        "queryRawUnsafe",
        "executeRaw",
        "executeRawUnsafe",
    ]
)


COMMON_INDEX_FIELDS = frozenset(
    [
        "id",
        "email",
        "username",
        "userId",
        "user_id",
        "createdAt",
        "created_at",
        "updatedAt",
        "updated_at",
        "status",
        "type",
        "slug",
        "uuid",
    ]
)


CONNECTION_DANGER_PATTERNS = frozenset(
    [
        "connection_limit=100",
        "connection_limit=50",
        "connectionLimit=100",
        "connectionLimit=50",
        "pool_size=100",
        "pool_size=50",
    ]
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Prisma ORM anti-patterns and performance issues.

    Detects:
    - Unbounded queries without pagination
    - N+1 query patterns
    - Missing transactions for multiple writes
    - Unhandled OrThrow methods
    - Unsafe raw SQL queries
    - Missing database indexes
    - Connection pool configuration issues

    Args:
        context: Standardized rule context with database path

    Returns:
        List of Prisma ORM issues found
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        query = build_query(
            "orm_queries",
            ["file", "line", "query_type", "has_limit"],
            where="has_limit = 0 OR has_limit IS NULL",
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, query_type, _has_limit in cursor.fetchall():
            if not any(f".{method}" in query_type for method in UNBOUNDED_METHODS):
                continue
            model = query_type.split(".")[0] if "." in query_type else "unknown"
            method = query_type.split(".")[-1] if "." in query_type else query_type

            findings.append(
                StandardFinding(
                    rule_name="prisma-unbounded-query",
                    message=f"Unbounded {method} on {model} - missing take/skip pagination",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="orm-performance",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-400",
                )
            )

        query = build_query(
            "orm_queries",
            ["file", "line", "query_type", "includes"],
            where="includes IS NULL OR includes = '[]' OR includes = '{}' OR includes = ''",
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, query_type, _includes in cursor.fetchall():
            if ".findMany" not in query_type:
                continue
            model = query_type.split(".")[0] if "." in query_type else "unknown"

            findings.append(
                StandardFinding(
                    rule_name="prisma-n-plus-one",
                    message=f"Potential N+1: findMany on {model} without includes",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="orm-performance",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-400",
                )
            )

        query = build_query(
            "orm_queries", ["file", "line", "query_type", "has_transaction"], order_by="file, line"
        )
        cursor.execute(query)

        file_operations = {}
        for file, line, query_type, has_transaction in cursor.fetchall():
            if not any(f".{method}" in query_type for method in WRITE_METHODS):
                continue
            if file not in file_operations:
                file_operations[file] = []
            file_operations[file].append(
                {"line": line, "query": query_type, "has_transaction": has_transaction}
            )

        for file, operations in file_operations.items():
            for i in range(len(operations) - 1):
                op1 = operations[i]
                op2 = operations[i + 1]

                if (
                    op2["line"] - op1["line"] <= 30
                    and not op1["has_transaction"]
                    and not op2["has_transaction"]
                ):
                    findings.append(
                        StandardFinding(
                            rule_name="prisma-missing-transaction",
                            message=f"Multiple writes without transaction: {op1['query']} and {op2['query']}",
                            file_path=file,
                            line=op1["line"],
                            severity=Severity.HIGH,
                            category="orm-data-integrity",
                            confidence=Confidence.HIGH,
                            cwe_id="CWE-662",
                        )
                    )
                    break

        query = build_query("orm_queries", ["file", "line", "query_type"], order_by="file, line")
        cursor.execute(query)

        all_orm_queries = cursor.fetchall()

        for file, line, query_type in all_orm_queries:
            if not any(f".{method}" in query_type for method in THROW_METHODS):
                continue

            cfg_query = build_query("cfg_blocks", ["block_type"], limit=1)
            cursor.execute(
                cfg_query
                + """
                WHERE file = ?
                  AND block_type IN ('try', 'catch', 'except', 'finally')
                  AND ? BETWEEN start_line - 5 AND end_line + 5
            """,
                (file, line),
            )
            has_error_handling = cursor.fetchone() is not None

            if not has_error_handling:
                method = query_type.split(".")[-1] if "." in query_type else query_type
                findings.append(
                    StandardFinding(
                        rule_name="prisma-unhandled-throw",
                        message=f"OrThrow method {method} without visible error handling",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="orm-error-handling",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-755",
                    )
                )

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, func, args in cursor.fetchall():
            func_lower = func.lower()
            if not ("queryraw" in func_lower or "executeraw" in func_lower):
                continue

            is_unsafe = "Unsafe" in func
            has_interpolation = False

            if args:
                has_interpolation = (
                    "${" in args or "+" in args or "`" in args or "concat" in args.lower()
                )

            if is_unsafe or has_interpolation:
                findings.append(
                    StandardFinding(
                        rule_name="prisma-sql-injection",
                        message=f"Potential SQL injection in {func} with {'unsafe method' if is_unsafe else 'string interpolation'}",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL if is_unsafe else Severity.HIGH,
                        category="orm-security",
                        confidence=Confidence.HIGH if is_unsafe else Confidence.MEDIUM,
                        cwe_id="CWE-89",
                    )
                )

        cursor.execute("""
            SELECT p.model_name, COUNT(DISTINCT p.field_name) as indexed_count
            FROM prisma_models p
            WHERE p.is_indexed = 1 OR p.is_unique = 1
            GROUP BY p.model_name
            HAVING indexed_count < 2
        """)

        poorly_indexed_models = {row[0]: row[1] for row in cursor.fetchall()}

        if poorly_indexed_models:
            query = build_query(
                "orm_queries", ["file", "line", "query_type"], order_by="file, line"
            )
            cursor.execute(query)

            for file, line, query_type in cursor.fetchall():
                if not any(
                    method in query_type for method in [".findMany", ".findFirst", ".findUnique"]
                ):
                    continue
                model = query_type.split(".")[0] if "." in query_type else None

                if model in poorly_indexed_models:
                    indexed_count = poorly_indexed_models[model]
                    findings.append(
                        StandardFinding(
                            rule_name="prisma-missing-index",
                            message=f"Query on {model} with only {indexed_count} indexed field(s) - verify performance",
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            category="orm-performance",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-400",
                        )
                    )

        query = build_query("files", ["path"], limit=100)
        cursor.execute(query)

        schema_file = None
        for (path,) in cursor.fetchall():
            if "schema.prisma" in path or "prisma/schema" in path:
                schema_file = (path,)
                break

        if schema_file:
            query = build_query(
                "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
            )
            cursor.execute(query)

            DB_VAR_PATTERNS = frozenset(["DATABASE_URL", "DATABASE", "POSTGRES", "MYSQL"])

            for file, line, var, expr in cursor.fetchall():
                var_upper = var.upper()
                if not any(pattern in var_upper for pattern in DB_VAR_PATTERNS):
                    continue

                if expr and "connection_limit" not in expr.lower():
                    findings.append(
                        StandardFinding(
                            rule_name="prisma-no-connection-limit",
                            message=f"Database URL in {var} without connection_limit parameter",
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            category="orm-configuration",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-770",
                        )
                    )

                if expr:
                    for danger_pattern in CONNECTION_DANGER_PATTERNS:
                        if danger_pattern in expr.lower():
                            findings.append(
                                StandardFinding(
                                    rule_name="prisma-high-connection-limit",
                                    message=f"Connection limit too high in {var} - may exhaust database",
                                    file_path=file,
                                    line=line,
                                    severity=Severity.HIGH,
                                    category="orm-configuration",
                                    confidence=Confidence.HIGH,
                                    cwe_id="CWE-770",
                                )
                            )
                            break

        cursor.execute("""
            SELECT DISTINCT p.model_name, p.field_name
            FROM prisma_models p
            WHERE p.field_name IN ('email', 'username', 'userId', 'user_id', 'slug', 'uuid')
              AND p.is_indexed = 0
              AND p.is_unique = 0
        """)

        for model_name, field_name in cursor.fetchall():
            findings.append(
                StandardFinding(
                    rule_name="prisma-unindexed-common-field",
                    message=f"Common field {field_name} in {model_name} is not indexed",
                    file_path="schema.prisma",
                    line=0,
                    severity=Severity.MEDIUM,
                    category="orm-performance",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-400",
                )
            )

    finally:
        conn.close()

    return findings


def register_taint_patterns(taint_registry):
    """Register Prisma-specific taint patterns.

    This function is called by the orchestrator to register
    ORM-specific sources and sinks for taint analysis.

    Args:
        taint_registry: TaintRegistry instance
    """

    for pattern in RAW_QUERY_METHODS:
        taint_registry.register_sink(pattern, "sql", "javascript")
        taint_registry.register_sink(f"prisma.{pattern}", "sql", "javascript")
        taint_registry.register_sink(f"db.{pattern}", "sql", "javascript")

    PRISMA_SOURCES = frozenset(
        ["findMany", "findFirst", "findUnique", "where", "select", "include", "orderBy"]
    )

    for pattern in PRISMA_SOURCES:
        taint_registry.register_source(f"prisma.{pattern}", "user_input", "javascript")

    taint_registry.register_sink("prisma.$transaction", "transaction", "javascript")
    taint_registry.register_sink("$transaction", "transaction", "javascript")
