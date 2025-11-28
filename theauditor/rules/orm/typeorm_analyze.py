"""TypeORM Analyzer - Database-First Approach."""

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
    name="typeorm_orm_issues",
    category="orm",
    target_extensions=[".ts", ".tsx", ".mjs"],
    exclude_patterns=[
        "__tests__/",
        "test/",
        "tests/",
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        "migrations/",
        "migration/",
        ".pf/",
        ".auditor_venv/",
    ],
    requires_jsx_pass=False,
)


UNBOUNDED_METHODS = frozenset(
    ["find", "findAndCount", "getMany", "getManyAndCount", "getRawMany", "getRawAndEntities"]
)


WRITE_METHODS = frozenset(
    [
        "save",
        "insert",
        "update",
        "delete",
        "remove",
        "softDelete",
        "restore",
        "upsert",
        "increment",
        "decrement",
        "create",
    ]
)


RAW_QUERY_METHODS = frozenset(
    [
        "query",
        "createQueryBuilder",
        "getQuery",
        "getSql",
        "manager.query",
        "connection.query",
        "entityManager.query",
        "dataSource.query",
        "queryRunner.query",
    ]
)


QUERYBUILDER_MANY = frozenset(["getMany", "getManyAndCount", "getRawMany", "getRawAndEntities"])


TRANSACTION_METHODS = frozenset(
    [
        "transaction",
        "startTransaction",
        "commitTransaction",
        "rollbackTransaction",
        "queryRunner.startTransaction",
    ]
)


COMMON_INDEXED_FIELDS = frozenset(
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
        "deletedAt",
        "deleted_at",
        "status",
        "type",
        "slug",
        "code",
        "uuid",
        "tenantId",
        "tenant_id",
    ]
)


DANGEROUS_CASCADE = frozenset(
    ["cascade: true", "cascade:true", "cascade : true", '"cascade": true', '"cascade":true']
)


DANGEROUS_SYNC = frozenset(
    [
        "synchronize: true",
        "synchronize:true",
        "synchronize : true",
        '"synchronize": true',
        '"synchronize":true',
    ]
)


REPOSITORY_PATTERNS = frozenset(
    [
        "getRepository",
        "getCustomRepository",
        "getTreeRepository",
        "getMongoRepository",
        "EntityManager",
        "getManager",
    ]
)


TYPEORM_SOURCES = frozenset(
    ["find", "findOne", "findOneBy", "findBy", "where", "andWhere", "orWhere", "having"]
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect TypeORM anti-patterns and performance issues."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, method, args in cursor.fetchall():
            if not any(method.endswith(f".{m}") for m in UNBOUNDED_METHODS):
                continue

            has_limit = args and any(
                term in str(args) for term in ["limit", "take", "skip", "offset"]
            )

            if not has_limit:
                method_name = method.split(".")[-1] if "." in method else method
                findings.append(
                    StandardFinding(
                        rule_name="typeorm-unbounded-query",
                        message=f"Unbounded query: {method} without pagination",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH
                        if method_name in QUERYBUILDER_MANY
                        else Severity.MEDIUM,
                        category="orm-performance",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-400",
                    )
                )

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        file_queries = {}
        for file, line, method, args in cursor.fetchall():
            if not any(method.endswith(f".{m}") for m in ["findOne", "findOneBy", "findOneOrFail"]):
                continue
            if file not in file_queries:
                file_queries[file] = []
            file_queries[file].append({"line": line, "method": method, "args": args})

        for file, queries in file_queries.items():
            for i in range(len(queries) - 1):
                q1 = queries[i]
                q2 = queries[i + 1]

                if q2["line"] - q1["line"] <= 10:
                    has_relations1 = q1["args"] and "relations" in str(q1["args"])
                    has_relations2 = q2["args"] and "relations" in str(q2["args"])

                    if not has_relations1 and not has_relations2:
                        findings.append(
                            StandardFinding(
                                rule_name="typeorm-n-plus-one",
                                message=f"Potential N+1: Multiple {q1['method']} calls without relations",
                                file_path=file,
                                line=q1["line"],
                                severity=Severity.HIGH,
                                category="orm-performance",
                                confidence=Confidence.MEDIUM,
                                cwe_id="CWE-400",
                            )
                        )
                        break

        query = build_query(
            "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
        )
        cursor.execute(query)

        file_operations = {}
        for file, line, method in cursor.fetchall():
            if not any(f".{m}" in method for m in WRITE_METHODS):
                continue
            if file not in file_operations:
                file_operations[file] = []
            file_operations[file].append({"line": line, "method": method})

        for file, operations in file_operations.items():
            for i in range(len(operations) - 1):
                op1 = operations[i]
                op2 = operations[i + 1]

                if op2["line"] - op1["line"] <= 20:
                    trans_query = build_query(
                        "function_call_args",
                        ["callee_function"],
                        where="file = ? AND line BETWEEN ? AND ?",
                    )
                    cursor.execute(trans_query, (file, op1["line"] - 10, op2["line"] + 10))

                    has_transaction = False
                    for (callee,) in cursor.fetchall():
                        if "transaction" in callee.lower() or "queryrunner" in callee.lower():
                            has_transaction = True
                            break

                    if not has_transaction:
                        findings.append(
                            StandardFinding(
                                rule_name="typeorm-missing-transaction",
                                message=f"Multiple writes without transaction: {op1['method']} and {op2['method']}",
                                file_path=file,
                                line=op1["line"],
                                severity=Severity.HIGH,
                                category="orm-data-integrity",
                                confidence=Confidence.MEDIUM,
                                cwe_id="CWE-662",
                            )
                        )
                        break

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, func, args in cursor.fetchall():
            func_lower = func.lower()
            if not (
                func == "query"
                or ".query" in func_lower
                or "querybuilder" in func_lower
                or ".createquerybuilder" in func_lower
            ):
                continue
            if args:
                args_str = str(args)

                has_interpolation = any(
                    pattern in args_str
                    for pattern in ["${", '"+', '" +', "` +", "concat", "+", "`"]
                )

                has_params = ":" in args_str or "$" in args_str

                if has_interpolation and not has_params:
                    findings.append(
                        StandardFinding(
                            rule_name="typeorm-sql-injection",
                            message=f"Potential SQL injection in {func}",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="orm-security",
                            confidence=Confidence.HIGH if "query" in func else Confidence.MEDIUM,
                            cwe_id="CWE-89",
                        )
                    )

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        all_calls = cursor.fetchall()

        for file, line, method, _args in all_calls:
            method_lower = method.lower()
            if not (
                "getmany" in method_lower
                or "getrawmany" in method_lower
                or "getmanyandcount" in method_lower
            ):
                continue

            limit_query = build_query(
                "function_call_args", ["callee_function"], where="file = ? AND ABS(line - ?) <= 5"
            )
            cursor.execute(limit_query, (file, line))

            has_limit_nearby = False
            for (callee,) in cursor.fetchall():
                if callee.endswith(".limit") or callee.endswith(".take"):
                    has_limit_nearby = True
                    break

            if not has_limit_nearby:
                findings.append(
                    StandardFinding(
                        rule_name="typeorm-querybuilder-no-limit",
                        message=f"QueryBuilder {method} without limit/take",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="orm-performance",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-400",
                    )
                )

        query = build_query("assignments", ["file", "line", "source_expr"])
        cursor.execute(query)

        for file, line, expr in cursor.fetchall():
            if not expr:
                continue
            expr_lower = expr.lower().replace(" ", "")
            if "cascade" not in expr_lower or "true" not in expr_lower:
                continue

            if not any(
                pattern in expr_lower
                for pattern in ["cascade:true", 'cascade"true', "cascade'true"]
            ):
                continue
            findings.append(
                StandardFinding(
                    rule_name="typeorm-cascade-true",
                    message="cascade: true can cause unintended data deletion",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="orm-data-integrity",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-672",
                )
            )

        query = build_query("assignments", ["file", "line", "source_expr"])
        cursor.execute(query)

        for file, line, expr in cursor.fetchall():
            if not expr:
                continue
            expr_lower = expr.lower().replace(" ", "")
            if "synchronize" not in expr_lower or "true" not in expr_lower:
                continue

            if not any(
                pattern in expr_lower
                for pattern in ["synchronize:true", 'synchronize"true', "synchronize'true"]
            ):
                continue

            file_lower = file.lower()
            if any(pattern in file_lower for pattern in ["test", "spec", "mock"]):
                continue
            findings.append(
                StandardFinding(
                    rule_name="typeorm-synchronize-true",
                    message="synchronize: true detected - NEVER use in production",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="orm-security",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-665",
                )
            )

        query = build_query("files", ["path"])
        cursor.execute(query)

        entity_files = []
        for (path,) in cursor.fetchall():
            path_lower = path.lower()
            if not (path.endswith(".entity.ts") or path.endswith(".entity.js")):
                continue

            if "test" in path_lower or "spec" in path_lower:
                continue
            entity_files.append(path)

        for entity_file in entity_files:
            for field in COMMON_INDEXED_FIELDS:
                field_query = build_query(
                    "symbols",
                    ["line", "name"],
                    where="path = ? AND type IN ('property', 'field', 'member')",
                )
                cursor.execute(field_query, (entity_file,))

                field_result = None
                for line, name in cursor.fetchall():
                    if field.lower() in name.lower():
                        field_result = (line,)
                        break

                if field_result:
                    field_line = field_result[0]

                    index_query = build_query(
                        "symbols", ["name"], where="path = ? AND ABS(line - ?) <= 3"
                    )
                    cursor.execute(index_query, (entity_file, field_line))

                    has_index = False
                    for (symbol_name,) in cursor.fetchall():
                        if "index" in symbol_name.lower():
                            has_index = True
                            break

                    if not has_index:
                        findings.append(
                            StandardFinding(
                                rule_name="typeorm-missing-index",
                                message=f'Common field "{field}" is not indexed',
                                file_path=entity_file,
                                line=field_line,
                                severity=Severity.MEDIUM,
                                category="orm-performance",
                                confidence=Confidence.MEDIUM,
                                cwe_id="CWE-400",
                            )
                        )

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        join_counts = {}
        for file, line, method, _args in cursor.fetchall():
            method_lower = method.lower()
            if not (
                "leftjoin" in method_lower
                or "innerjoin" in method_lower
                or "leftjoinandselect" in method_lower
            ):
                continue
            key = f"{file}:{line // 10}"
            if key not in join_counts:
                join_counts[key] = {"file": file, "line": line, "count": 0}
            join_counts[key]["count"] += 1

        for _key, data in join_counts.items():
            if data["count"] >= 3:
                limit_query = build_query(
                    "function_call_args",
                    ["callee_function"],
                    where="file = ? AND ABS(line - ?) <= 10",
                )
                cursor.execute(limit_query, (data["file"], data["line"]))

                has_limit = False
                for (callee,) in cursor.fetchall():
                    if callee.endswith(".limit") or callee.endswith(".take"):
                        has_limit = True
                        break

                if not has_limit:
                    findings.append(
                        StandardFinding(
                            rule_name="typeorm-complex-joins",
                            message=f"Complex query with {data['count']} joins but no pagination",
                            file_path=data["file"],
                            line=data["line"],
                            severity=Severity.HIGH,
                            category="orm-performance",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-400",
                        )
                    )

        query = build_query(
            "function_call_args", ["file", "line", "callee_function"], order_by="file, line"
        )
        cursor.execute(query)

        manager_usage = []
        for file, line, func in cursor.fetchall():
            func_lower = func.lower()
            if "entitymanager." in func_lower or "getmanager" in func_lower:
                manager_usage.append((file, line, func))

        if len(manager_usage) > 20:
            repo_query = build_query("function_call_args", ["callee_function"])
            cursor.execute(repo_query)

            repo_count = 0
            for (callee,) in cursor.fetchall():
                callee_lower = callee.lower()
                if "getrepository" in callee_lower or "getcustomrepository" in callee_lower:
                    repo_count += 1

            if repo_count < 5:
                findings.append(
                    StandardFinding(
                        rule_name="typeorm-entity-manager-overuse",
                        message="Heavy EntityManager usage - consider Repository pattern",
                        file_path=manager_usage[0][0],
                        line=1,
                        severity=Severity.LOW,
                        category="orm-architecture",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-1061",
                    )
                )

    finally:
        conn.close()

    return findings


def register_taint_patterns(taint_registry):
    """Register TypeORM-specific taint patterns."""
    for pattern in RAW_QUERY_METHODS:
        taint_registry.register_sink(pattern, "sql", "javascript")
        taint_registry.register_sink(pattern, "sql", "typescript")

    for pattern in TYPEORM_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")
        taint_registry.register_source(pattern, "user_input", "typescript")

    for pattern in TRANSACTION_METHODS:
        taint_registry.register_sink(pattern, "transaction", "javascript")
        taint_registry.register_sink(pattern, "transaction", "typescript")
