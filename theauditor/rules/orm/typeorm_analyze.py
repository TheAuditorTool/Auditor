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

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
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
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, method, args in cursor.fetchall():
            # Check for unbounded methods in Python
            if not any(method.endswith(f'.{m}') for m in UNBOUNDED_METHODS):
                continue
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
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        cursor.execute(query)

        # Filter and group by file to detect patterns
        file_queries = {}
        for file, line, method, args in cursor.fetchall():
            # Check for findOne methods in Python
            if not any(method.endswith(f'.{m}') for m in ['findOne', 'findOneBy', 'findOneOrFail']):
                continue
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
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           order_by="file, line")
        cursor.execute(query)

        # Filter and group operations by file
        file_operations = {}
        for file, line, method in cursor.fetchall():
            # Check for write methods in Python
            if not any(f'.{m}' in method for m in WRITE_METHODS):
                continue
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
                    # Check for transaction - fetch and filter in Python
                    trans_query = build_query('function_call_args', ['callee_function'],
                                             where="file = ? AND line BETWEEN ? AND ?")
                    cursor.execute(trans_query, (file, op1['line'] - 10, op2['line'] + 10))

                    has_transaction = False
                    for (callee,) in cursor.fetchall():
                        if 'transaction' in callee.lower() or 'queryrunner' in callee.lower():
                            has_transaction = True
                            break

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
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func, args in cursor.fetchall():
            # Check for query methods in Python
            func_lower = func.lower()
            if not (func == 'query' or '.query' in func_lower or
                   'querybuilder' in func_lower or '.createquerybuilder' in func_lower):
                continue
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
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        cursor.execute(query)
        # Store results before nested loop (avoid cursor state bug)
        all_calls = cursor.fetchall()

        for file, line, method, args in all_calls:
            # Check for getMany methods in Python
            method_lower = method.lower()
            if not ('getmany' in method_lower or 'getrawmany' in method_lower or 'getmanyandcount' in method_lower):
                continue

            # Check if there's a limit() or take() call nearby - fetch and filter in Python
            limit_query = build_query('function_call_args', ['callee_function'],
                                     where="file = ? AND ABS(line - ?) <= 5")
            cursor.execute(limit_query, (file, line))

            has_limit_nearby = False
            for (callee,) in cursor.fetchall():
                if callee.endswith('.limit') or callee.endswith('.take'):
                    has_limit_nearby = True
                    break

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
        # Fetch all assignments, filter in Python
        query = build_query('assignments', ['file', 'line', 'source_expr'])
        cursor.execute(query)

        for file, line, expr in cursor.fetchall():
            # Check for cascade:true patterns in Python
            if not expr:
                continue
            expr_lower = expr.lower().replace(' ', '')
            if 'cascade' not in expr_lower or 'true' not in expr_lower:
                continue
            # Verify it's actually cascade: true (various formats)
            if not any(pattern in expr_lower for pattern in ['cascade:true', 'cascade"true', "cascade'true"]):
                continue
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
        # Fetch all assignments, filter in Python (METADATA handles file exclusions)
        query = build_query('assignments', ['file', 'line', 'source_expr'])
        cursor.execute(query)

        for file, line, expr in cursor.fetchall():
            # Check for synchronize:true patterns in Python
            if not expr:
                continue
            expr_lower = expr.lower().replace(' ', '')
            if 'synchronize' not in expr_lower or 'true' not in expr_lower:
                continue
            # Verify it's actually synchronize: true
            if not any(pattern in expr_lower for pattern in ['synchronize:true', 'synchronize"true', "synchronize'true"]):
                continue
            # Skip test/spec/mock files
            file_lower = file.lower()
            if any(pattern in file_lower for pattern in ['test', 'spec', 'mock']):
                continue
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
        # Find entity files - fetch all files, filter in Python
        query = build_query('files', ['path'])
        cursor.execute(query)

        entity_files = []
        for (path,) in cursor.fetchall():
            # Check for entity files in Python
            path_lower = path.lower()
            if not (path.endswith('.entity.ts') or path.endswith('.entity.js')):
                continue
            # Skip test/spec files (METADATA handles this but double-check)
            if 'test' in path_lower or 'spec' in path_lower:
                continue
            entity_files.append(path)

        for entity_file in entity_files:
            # Check for common fields in this entity
            for field in COMMON_INDEXED_FIELDS:
                # Fetch symbols and filter in Python
                field_query = build_query('symbols', ['line', 'name'],
                                         where="path = ? AND type IN ('property', 'field', 'member')")
                cursor.execute(field_query, (entity_file,))

                field_result = None
                for line, name in cursor.fetchall():
                    if field.lower() in name.lower():
                        field_result = (line,)
                        break

                if field_result:
                    field_line = field_result[0]

                    # Check if there's an @Index nearby - fetch and filter in Python
                    index_query = build_query('symbols', ['name'],
                                             where="path = ? AND ABS(line - ?) <= 3")
                    cursor.execute(index_query, (entity_file, field_line))

                    has_index = False
                    for (symbol_name,) in cursor.fetchall():
                        if 'index' in symbol_name.lower():
                            has_index = True
                            break

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
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        cursor.execute(query)

        # Filter and count joins per query
        join_counts = {}
        for file, line, method, args in cursor.fetchall():
            # Check for join methods in Python
            method_lower = method.lower()
            if not ('leftjoin' in method_lower or 'innerjoin' in method_lower or 'leftjoinandselect' in method_lower):
                continue
            key = f"{file}:{line // 10}"  # Group by 10-line blocks
            if key not in join_counts:
                join_counts[key] = {'file': file, 'line': line, 'count': 0}
            join_counts[key]['count'] += 1

        # Check for complex joins without limit
        for key, data in join_counts.items():
            if data['count'] >= 3:
                # Check for limit/take - fetch and filter in Python
                limit_query = build_query('function_call_args', ['callee_function'],
                                         where="file = ? AND ABS(line - ?) <= 10")
                cursor.execute(limit_query, (data['file'], data['line']))

                has_limit = False
                for (callee,) in cursor.fetchall():
                    if callee.endswith('.limit') or callee.endswith('.take'):
                        has_limit = True
                        break

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
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           order_by="file, line")
        cursor.execute(query)

        # Filter for EntityManager usage
        manager_usage = []
        for file, line, func in cursor.fetchall():
            func_lower = func.lower()
            if 'entitymanager.' in func_lower or 'getmanager' in func_lower:
                manager_usage.append((file, line, func))

        if len(manager_usage) > 20:  # Significant EntityManager usage
            # Check if using repositories - fetch all again and filter
            repo_query = build_query('function_call_args', ['callee_function'])
            cursor.execute(repo_query)

            repo_count = 0
            for (callee,) in cursor.fetchall():
                callee_lower = callee.lower()
                if 'getrepository' in callee_lower or 'getcustomrepository' in callee_lower:
                    repo_count += 1

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
