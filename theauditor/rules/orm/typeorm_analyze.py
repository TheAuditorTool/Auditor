"""TypeORM Analyzer - Database-First Approach.

Detects TypeORM anti-patterns and performance issues using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels
"""

import sqlite3
import json
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA - SMART FILTERING
# ============================================================================

METADATA = RuleMetadata(
    name="typeorm_orm_issues",
    category="orm",

    # Target TypeScript files (TypeORM is TypeScript-first)
    target_extensions=['.ts', '.tsx', '.mjs'],

    # Exclude patterns - skip tests, migrations, build, TheAuditor folders
    exclude_patterns=[
        '__tests__/',
        'test/',
        'tests/',
        'node_modules/',
        'dist/',
        'build/',
        '.next/',
        'migrations/',
        'migration/',          # TypeORM-specific migrations
        '.pf/',                # TheAuditor output directory
        '.auditor_venv/'       # TheAuditor sandboxed tools
    ],

    # This is a DATABASE-ONLY rule (no JSX required)
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Use Frozensets)
# ============================================================================

# TypeORM query methods that need pagination
UNBOUNDED_METHODS = frozenset([
    'find', 'findAndCount', 'getMany', 'getManyAndCount',
    'getRawMany', 'getRawAndEntities'
])

# TypeORM write operations that may need transactions
WRITE_METHODS = frozenset([
    'save', 'insert', 'update', 'delete', 'remove',
    'softDelete', 'restore', 'upsert', 'increment',
    'decrement', 'create'
])

# Raw query methods that could have SQL injection
RAW_QUERY_METHODS = frozenset([
    'query', 'createQueryBuilder', 'getQuery', 'getSql',
    'manager.query', 'connection.query', 'entityManager.query',
    'dataSource.query', 'queryRunner.query'
])

# QueryBuilder methods that return multiple results
QUERYBUILDER_MANY = frozenset([
    'getMany', 'getManyAndCount', 'getRawMany', 'getRawAndEntities'
])

# Transaction-related methods
TRANSACTION_METHODS = frozenset([
    'transaction', 'startTransaction', 'commitTransaction',
    'rollbackTransaction', 'queryRunner.startTransaction'
])

# Common fields that should be indexed
COMMON_INDEXED_FIELDS = frozenset([
    'id', 'email', 'username', 'userId', 'user_id',
    'createdAt', 'created_at', 'updatedAt', 'updated_at',
    'deletedAt', 'deleted_at', 'status', 'type', 'slug',
    'code', 'uuid', 'tenantId', 'tenant_id'
])

# Dangerous cascade options
DANGEROUS_CASCADE = frozenset([
    'cascade: true', 'cascade:true', 'cascade : true',
    '"cascade": true', '"cascade":true'
])

# Dangerous synchronize patterns
DANGEROUS_SYNC = frozenset([
    'synchronize: true', 'synchronize:true', 'synchronize : true',
    '"synchronize": true', '"synchronize":true'
])

# Repository/Entity manager patterns
REPOSITORY_PATTERNS = frozenset([
    'getRepository', 'getCustomRepository', 'getTreeRepository',
    'getMongoRepository', 'EntityManager', 'getManager'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect TypeORM anti-patterns and performance issues.

    Detects:
    - Unbounded queries without pagination
    - N+1 query patterns
    - Missing transactions for multiple writes
    - Unsafe raw SQL queries
    - Dangerous cascade configurations
    - synchronize: true in production
    - Missing database indexes
    - Complex joins without limits

    Args:
        context: Standardized rule context with database path

    Returns:
        List of TypeORM issues found
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:

        # ========================================================
        # CHECK 1: Unbounded Queries (find, getMany without limit)
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'])
        cursor.execute(query + """
            WHERE (callee_function LIKE '%.find'
                   OR callee_function LIKE '%.findAndCount'
                   OR callee_function LIKE '%.getMany'
                   OR callee_function LIKE '%.getManyAndCount'
                   OR callee_function LIKE '%.getRawMany')
            ORDER BY file, line
        """)

        for file, line, method, args in cursor.fetchall():
            # Check if limit/take is present
            has_limit = args and any(term in str(args) for term in
                                    ['limit', 'take', 'skip', 'offset'])

            if not has_limit:
                method_name = method.split('.')[-1] if '.' in method else method
                findings.append(StandardFinding(
                    rule_name='typeorm-unbounded-query',
                    message=f'Unbounded query: {method} without pagination',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH if method_name in QUERYBUILDER_MANY else Severity.MEDIUM,
                    category='orm-performance',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-400'
                ))

        # ========================================================
        # CHECK 2: N+1 Query Patterns
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'])
        cursor.execute(query + """
            WHERE (callee_function LIKE '%.findOne'
                   OR callee_function LIKE '%.findOneBy'
                   OR callee_function LIKE '%.findOneOrFail')
            ORDER BY file, line
        """)

        # Group by file to detect patterns
        file_queries = {}
        for file, line, method, args in cursor.fetchall():
            if file not in file_queries:
                file_queries[file] = []
            file_queries[file].append({'line': line, 'method': method, 'args': args})

        # Detect N+1 patterns (multiple findOne close together)
        for file, queries in file_queries.items():
            for i in range(len(queries) - 1):
                q1 = queries[i]
                q2 = queries[i + 1]

                # Multiple findOne within 10 lines
                if q2['line'] - q1['line'] <= 10:
                    # Check if they have relations/joins
                    has_relations1 = q1['args'] and 'relations' in str(q1['args'])
                    has_relations2 = q2['args'] and 'relations' in str(q2['args'])

                    if not has_relations1 and not has_relations2:
                        findings.append(StandardFinding(
                            rule_name='typeorm-n-plus-one',
                            message=f'Potential N+1: Multiple {q1["method"]} calls without relations',
                            file_path=file,
                            line=q1['line'],
                            severity=Severity.HIGH,
                            category='orm-performance',
                            confidence=Confidence.MEDIUM,
                            cwe_id='CWE-400'
                        ))
                        break

        # ========================================================
        # CHECK 3: Missing Transactions for Multiple Writes
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function'])
        cursor.execute(query + """
            WHERE callee_function LIKE '%.save'
               OR callee_function LIKE '%.insert'
               OR callee_function LIKE '%.update'
               OR callee_function LIKE '%.delete'
               OR callee_function LIKE '%.remove'
               OR callee_function LIKE '%.softDelete'
            ORDER BY file, line
        """)

        # Group operations by file
        file_operations = {}
        for file, line, method in cursor.fetchall():
            if file not in file_operations:
                file_operations[file] = []
            file_operations[file].append({'line': line, 'method': method})

        # Check for close operations without transactions
        for file, operations in file_operations.items():
            for i in range(len(operations) - 1):
                op1 = operations[i]
                op2 = operations[i + 1]

                # Operations within 20 lines
                if op2['line'] - op1['line'] <= 20:
                    # Check for transaction
                    trans_query = build_query('function_call_args', ['COUNT(*)'])
                    cursor.execute(trans_query + """
                        WHERE file = ?
                          AND (callee_function LIKE '%transaction%'
                               OR callee_function LIKE '%queryRunner%')
                          AND line BETWEEN ? AND ?
                    """, (file, op1['line'] - 10, op2['line'] + 10))

                    has_transaction = cursor.fetchone()[0] > 0

                    if not has_transaction:
                        findings.append(StandardFinding(
                            rule_name='typeorm-missing-transaction',
                            message=f"Multiple writes without transaction: {op1['method']} and {op2['method']}",
                            file_path=file,
                            line=op1['line'],
                            severity=Severity.HIGH,
                            category='orm-data-integrity',
                            confidence=Confidence.MEDIUM,
                            cwe_id='CWE-662'
                        ))
                        break

        # ========================================================
        # CHECK 4: Raw SQL Injection Risks
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'])
        cursor.execute(query + """
            WHERE callee_function LIKE '%.query'
               OR callee_function LIKE '%.createQueryBuilder'
               OR callee_function LIKE '%QueryBuilder%'
               OR callee_function = 'query'
            ORDER BY file, line
        """)

        for file, line, func, args in cursor.fetchall():
            if args:
                args_str = str(args)
                # Check for string interpolation
                has_interpolation = any(pattern in args_str for pattern in [
                    '${', '"+', '" +', '` +', 'concat', '+', '`'
                ])

                # Check for parameterization
                has_params = ':' in args_str or '$' in args_str

                if has_interpolation and not has_params:
                    findings.append(StandardFinding(
                        rule_name='typeorm-sql-injection',
                        message=f'Potential SQL injection in {func}',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='orm-security',
                        confidence=Confidence.HIGH if 'query' in func else Confidence.MEDIUM,
                        cwe_id='CWE-89'
                    ))

        # ========================================================
        # CHECK 5: QueryBuilder Without Limits
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'])
        cursor.execute(query + """
            WHERE callee_function LIKE '%getMany%'
               OR callee_function LIKE '%getRawMany%'
               OR callee_function LIKE '%getManyAndCount%'
            ORDER BY file, line
        """)
        # ✅ FIX: Store results before loop to avoid cursor state bug
        getmany_calls = cursor.fetchall()

        for file, line, method, args in getmany_calls:
            # Check if there's a limit() or take() call nearby
            limit_query = build_query('function_call_args', ['COUNT(*)'])
            cursor.execute(limit_query + """
                WHERE file = ?
                  AND (callee_function LIKE '%.limit'
                       OR callee_function LIKE '%.take')
                  AND ABS(line - ?) <= 5
            """, (file, line))

            has_limit_nearby = cursor.fetchone()[0] > 0

            if not has_limit_nearby:
                findings.append(StandardFinding(
                    rule_name='typeorm-querybuilder-no-limit',
                    message=f'QueryBuilder {method} without limit/take',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='orm-performance',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-400'
                ))

        # ========================================================
        # CHECK 6: Dangerous Cascade Configuration
        # ========================================================
        query = build_query('assignments', ['file', 'line', 'source_expr'])
        cursor.execute(query + """
            WHERE source_expr LIKE '%cascade%true%'
               OR source_expr LIKE '%cascade:%true%'
               OR source_expr LIKE '%cascade :%true%'
        """)

        for file, line, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='typeorm-cascade-true',
                message='cascade: true can cause unintended data deletion',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='orm-data-integrity',
                confidence=Confidence.HIGH,
                cwe_id='CWE-672'
            ))

        # ========================================================
        # CHECK 7: Synchronize True in Production
        # ========================================================
        query = build_query('assignments', ['file', 'line', 'source_expr'])
        cursor.execute(query + """
            WHERE (source_expr LIKE '%synchronize%true%'
                   OR source_expr LIKE '%synchronize:%true%')
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec%'
              AND file NOT LIKE '%mock%'
        """)

        for file, line, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='typeorm-synchronize-true',
                message='synchronize: true detected - NEVER use in production',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='orm-security',
                confidence=Confidence.HIGH,
                cwe_id='CWE-665'
            ))

        # ========================================================
        # CHECK 8: Missing Indexes on Common Fields
        # ========================================================
        # Find entity files
        # Note: Using raw SQL because build_query() doesn't support DISTINCT
        cursor.execute("""
            SELECT DISTINCT path
            FROM files
            WHERE (path LIKE '%.entity.ts' OR path LIKE '%.entity.js')
              AND path NOT LIKE '%test%'
              AND path NOT LIKE '%spec%'
        """)

        entity_files = cursor.fetchall()

        for (entity_file,) in entity_files:
            # Check for common fields in this entity
            for field in COMMON_INDEXED_FIELDS:
                field_query = build_query('symbols', ['line'])
                cursor.execute(field_query + """
                    WHERE path = ?
                      AND name LIKE ?
                      AND type IN ('property', 'field', 'member')
                    LIMIT 1
                """, (entity_file, f'%{field}%'))

                field_result = cursor.fetchone()

                if field_result:
                    field_line = field_result[0]

                    # Check if there's an @Index nearby
                    index_query = build_query('symbols', ['COUNT(*)'])
                    cursor.execute(index_query + """
                        WHERE path = ?
                          AND name LIKE '%Index%'
                          AND ABS(line - ?) <= 3
                    """, (entity_file, field_line))

                    has_index = cursor.fetchone()[0] > 0

                    if not has_index:
                        findings.append(StandardFinding(
                            rule_name='typeorm-missing-index',
                            message=f'Common field "{field}" is not indexed',
                            file_path=entity_file,
                            line=field_line,
                            severity=Severity.MEDIUM,
                            category='orm-performance',
                            confidence=Confidence.MEDIUM,
                            cwe_id='CWE-400'
                        ))

        # ========================================================
        # CHECK 9: Complex Joins Without Pagination
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'])
        cursor.execute(query + """
            WHERE (callee_function LIKE '%leftJoin%'
                   OR callee_function LIKE '%innerJoin%'
                   OR callee_function LIKE '%leftJoinAndSelect%')
            ORDER BY file, line
        """)

        # Count joins per query
        join_counts = {}
        for file, line, method, args in cursor.fetchall():
            key = f"{file}:{line // 10}"  # Group by 10-line blocks
            if key not in join_counts:
                join_counts[key] = {'file': file, 'line': line, 'count': 0}
            join_counts[key]['count'] += 1

        # Check for complex joins without limit
        for key, data in join_counts.items():
            if data['count'] >= 3:
                # Check for limit/take
                limit_query = build_query('function_call_args', ['COUNT(*)'])
                cursor.execute(limit_query + """
                    WHERE file = ?
                      AND (callee_function LIKE '%.limit'
                           OR callee_function LIKE '%.take')
                      AND ABS(line - ?) <= 10
                """, (data['file'], data['line']))

                has_limit = cursor.fetchone()[0] > 0

                if not has_limit:
                    findings.append(StandardFinding(
                        rule_name='typeorm-complex-joins',
                        message=f'Complex query with {data["count"]} joins but no pagination',
                        file_path=data['file'],
                        line=data['line'],
                        severity=Severity.HIGH,
                        category='orm-performance',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-400'
                    ))

        # ========================================================
        # CHECK 10: Entity Manager vs Repository Pattern
        # ========================================================
        query = build_query('function_call_args', ['file', 'line', 'callee_function'])
        cursor.execute(query + """
            WHERE callee_function LIKE '%entityManager.%'
               OR callee_function LIKE '%getManager%'
            ORDER BY file, line
        """)

        manager_usage = cursor.fetchall()

        if len(manager_usage) > 20:  # Significant EntityManager usage
            # Check if using repositories
            repo_query = build_query('function_call_args', ['COUNT(*)'])
            cursor.execute(repo_query + """
                WHERE callee_function LIKE '%getRepository%'
                   OR callee_function LIKE '%getCustomRepository%'
            """)

            repo_count = cursor.fetchone()[0]

            if repo_count < 5:  # Very few repository uses
                findings.append(StandardFinding(
                    rule_name='typeorm-entity-manager-overuse',
                    message='Heavy EntityManager usage - consider Repository pattern',
                    file_path=manager_usage[0][0],
                    line=1,
                    severity=Severity.LOW,
                    category='orm-architecture',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1061'
                ))

    finally:
        conn.close()

    return findings


def register_taint_patterns(taint_registry):
    """Register TypeORM-specific taint patterns.

    This function is called by the orchestrator to register
    ORM-specific sources and sinks for taint analysis.

    Args:
        taint_registry: TaintRegistry instance
    """
    # Register TypeORM raw query methods as SQL sinks
    for pattern in RAW_QUERY_METHODS:
        taint_registry.register_sink(pattern, 'sql', 'javascript')
        taint_registry.register_sink(pattern, 'sql', 'typescript')

    # Register TypeORM input sources
    TYPEORM_SOURCES = frozenset([
        'find', 'findOne', 'findOneBy', 'findBy',
        'where', 'andWhere', 'orWhere', 'having'
    ])

    for pattern in TYPEORM_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')
        taint_registry.register_source(pattern, 'user_input', 'typescript')

    # Register transaction methods
    for pattern in TRANSACTION_METHODS:
        taint_registry.register_sink(pattern, 'transaction', 'javascript')
        taint_registry.register_sink(pattern, 'transaction', 'typescript')
