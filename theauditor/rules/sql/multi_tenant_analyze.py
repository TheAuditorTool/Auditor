"""Multi-Tenant Security Analyzer - Phase 2 Clean Implementation.

Database-first detection using ONLY indexed data. No AST traversal, no file I/O.
Focuses on PostgreSQL RLS (Row Level Security) patterns for multi-tenant applications.

Truth Courier Design: Reports facts about tenant isolation patterns, not recommendations.
"""

import sqlite3
from typing import List
from dataclasses import dataclass
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA - Phase 3B Addition (2025-10-02)
# ============================================================================
METADATA = RuleMetadata(
    name="multi_tenant",
    category="sql",
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs', '.sql'],
    # NOTE: Do NOT exclude migrations/ - RLS policies (CREATE POLICY) are in migrations
    exclude_patterns=['frontend/', 'client/', 'test/', '__tests__/'],
    requires_jsx_pass=False
)


@dataclass(frozen=True)
class MultiTenantPatterns:
    """Finite pattern sets for multi-tenant detection - no regex."""

    # Sensitive tables requiring tenant isolation
    SENSITIVE_TABLES: frozenset = frozenset([
        'products', 'orders', 'inventory', 'customers', 'users',
        'locations', 'transfers', 'invoices', 'payments', 'shipments',
        'accounts', 'transactions', 'balances', 'billing', 'subscriptions',
        'zones', 'batches', 'plants', 'harvests', 'workers', 'facilities'
    ])

    # Tenant filtering fields
    TENANT_FIELDS: frozenset = frozenset([
        'facility_id', 'tenant_id', 'organization_id',
        'company_id', 'store_id', 'account_id'
    ])

    # RLS context setting patterns
    RLS_CONTEXT: frozenset = frozenset([
        'SET LOCAL app.current_facility_id',
        'SET LOCAL app.current_tenant_id',
        'SET LOCAL app.current_account_id',
        'current_setting'
    ])

    # Superuser account names
    SUPERUSER_NAMES: frozenset = frozenset([
        'postgres', 'root', 'admin', 'superuser', 'sa', 'administrator'
    ])

    # Transaction keywords
    TRANSACTION_KEYWORDS: frozenset = frozenset([
        'transaction', 'sequelize.transaction', 'db.transaction',
        'begin', 'BEGIN', 'start_transaction'
    ])


def find_multi_tenant_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect multi-tenant security issues using database queries.

    Detection strategy:
    1. Query sql_queries for sensitive tables without tenant filtering
    2. Query for RLS policies missing USING clause
    3. Check transactions for missing SET LOCAL context
    4. Find direct ID access without tenant validation
    5. Detect superuser database connections
    6. Find raw queries outside transactions
    7. Detect ORM queries without tenant scope
    8. Find bulk operations without tenant filtering
    9. Detect cross-tenant JOINs
    10. Find subqueries without tenant filtering

    Args:
        context: Rule execution context with db_path

    Returns:
        List of multi-tenant security findings
    """
    findings = []

    if not context.db_path:
        return findings

    patterns = MultiTenantPatterns()
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Check table availability (graceful degradation)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        available_tables = {row[0] for row in cursor.fetchall()}

        required_tables = {'sql_queries', 'function_call_args'}
        if not required_tables.issubset(available_tables):
            return findings  # Cannot run without required tables

        # Primary detection: sql_queries table (clean data only)
        findings.extend(_find_queries_without_tenant_filter(cursor, patterns))
        findings.extend(_find_rls_policies_without_using(cursor, patterns))
        findings.extend(_find_direct_id_access(cursor, patterns))
        findings.extend(_find_bulk_operations_without_tenant(cursor, patterns))
        findings.extend(_find_cross_tenant_joins(cursor, patterns))
        findings.extend(_find_subquery_without_tenant(cursor, patterns))

        # Secondary detection: function_call_args for transactions and ORM
        findings.extend(_find_missing_rls_context(cursor, patterns))
        findings.extend(_find_raw_query_without_transaction(cursor, patterns))
        findings.extend(_find_superuser_connections(cursor, patterns))

        # Tertiary detection: orm_queries table (1,287 rows available)
        findings.extend(_find_orm_missing_tenant_scope(cursor, patterns))

    finally:
        conn.close()

    return findings


def _find_queries_without_tenant_filter(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find queries on sensitive tables without tenant filtering."""
    findings = []

    # Check each sensitive table
    for table in patterns.SENSITIVE_TABLES:
        # NOTE: frontend/test filtering handled by METADATA
        # Keep migration check - sensitive table queries in migrations are data seeds, not DDL
        cursor.execute("""
            SELECT file_path, line_number, query_text, command
            FROM sql_queries
            WHERE command != 'UNKNOWN'
              AND command IS NOT NULL
              AND (tables LIKE ? OR query_text LIKE ?)
              AND file_path NOT LIKE '%migration%'
            ORDER BY file_path, line_number
            LIMIT 10
        """, (f'%{table}%', f'%{table}%'))

        for file, line, query, command in cursor.fetchall():
            query_lower = query.lower()

            # Check if query has tenant filtering
            has_tenant = any(field in query_lower for field in patterns.TENANT_FIELDS)

            if has_tenant:
                continue  # Query has tenant filtering

            # Determine severity
            if 'where' in query_lower:
                severity = Severity.HIGH
                message = f'{command} on {table} without tenant filtering'
            else:
                severity = Severity.CRITICAL
                message = f'{command} on {table} with NO WHERE clause - cross-tenant leak'

            findings.append(StandardFinding(
                rule_name='multi-tenant-missing-filter',
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                cwe_id='CWE-863'
            ))

    return findings


def _find_rls_policies_without_using(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find CREATE POLICY statements without proper USING clause."""
    findings = []

    cursor.execute("""
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE (query_text LIKE '%CREATE POLICY%' OR query_text LIKE '%create policy%')
          AND command != 'UNKNOWN'
        ORDER BY file_path, line_number
    """)

    for file, line, query in cursor.fetchall():
        query_upper = query.upper()

        # Check for USING clause
        if 'USING' not in query_upper:
            findings.append(StandardFinding(
                rule_name='multi-tenant-rls-no-using',
                message='CREATE POLICY without USING clause for row filtering',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                cwe_id='CWE-863'
            ))
        else:
            # Check if USING clause has tenant field or current_setting
            query_lower = query.lower()
            has_tenant_check = any(field in query_lower for field in patterns.TENANT_FIELDS)
            has_current_setting = 'current_setting' in query_lower

            if not (has_tenant_check or has_current_setting):
                findings.append(StandardFinding(
                    rule_name='multi-tenant-rls-weak-using',
                    message='RLS policy USING clause missing tenant field validation',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=query[:100] + '...' if len(query) > 100 else query,
                    cwe_id='CWE-863'
                ))

    return findings


def _find_direct_id_access(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find queries accessing records by ID without tenant validation."""
    findings = []

    # NOTE: frontend/test filtering handled by METADATA
    # Keep migration check - ID-based queries in migrations are usually data fixes
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command IN ('SELECT', 'UPDATE', 'DELETE')
          AND (query_text LIKE '%WHERE id = %'
               OR query_text LIKE '%WHERE id=%'
               OR query_text LIKE '%WHERE "id" = %'
               OR query_text LIKE '%WHERE `id` = %')
          AND file_path NOT LIKE '%migration%'
        ORDER BY file_path, line_number
        LIMIT 15
    """)

    for file, line, query, command in cursor.fetchall():
        query_lower = query.lower()

        # Check if it has tenant filtering
        has_tenant = any(field in query_lower for field in patterns.TENANT_FIELDS)

        if not has_tenant:
            findings.append(StandardFinding(
                rule_name='multi-tenant-direct-id-access',
                message=f'{command} by ID without tenant validation - potential cross-tenant access',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                cwe_id='CWE-863'
            ))

    return findings


def _find_missing_rls_context(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find transactions without SET LOCAL for RLS context."""
    findings = []

    # Find transaction starts
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE (callee_function LIKE '%transaction%'
               OR callee_function LIKE '%begin%')
        ORDER BY file, line
    """)

    transactions = cursor.fetchall()

    for file, line, func in transactions:
        # Check for SET LOCAL within transaction scope (±30 lines)
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args
            WHERE file = ?
              AND line BETWEEN ? AND ?
              AND argument_expr LIKE '%SET LOCAL%'
              AND (argument_expr LIKE '%current_facility_id%'
                   OR argument_expr LIKE '%current_tenant_id%'
                   OR argument_expr LIKE '%current_account_id%')
        """, (file, line, line + 30))

        has_set_local = cursor.fetchone()[0] > 0

        # Also check sql_queries
        if not has_set_local:
            cursor.execute("""
                SELECT COUNT(*)
                FROM sql_queries
                WHERE file_path = ?
                  AND line_number BETWEEN ? AND ?
                  AND query_text LIKE '%SET LOCAL%'
                  AND (query_text LIKE '%current_facility_id%'
                       OR query_text LIKE '%current_tenant_id%'
                       OR query_text LIKE '%current_account_id%')
            """, (file, line, line + 30))

            has_set_local = cursor.fetchone()[0] > 0

        if not has_set_local:
            findings.append(StandardFinding(
                rule_name='multi-tenant-missing-rls-context',
                message='Transaction without SET LOCAL app.current_facility_id',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=f'{func}(...)',
                cwe_id='CWE-863'
            ))

    return findings


def _find_superuser_connections(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find usage of superuser database connections that bypass RLS."""
    findings = []

    # Check assignments to database user variables
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE (target_var LIKE '%DB_USER%'
               OR target_var LIKE '%DATABASE_USER%'
               OR target_var LIKE '%POSTGRES_USER%'
               OR target_var LIKE '%PG_USER%')
          AND source_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        expr_lower = expr.lower()

        # Check if value is a superuser
        for superuser in patterns.SUPERUSER_NAMES:
            if superuser in expr_lower:
                findings.append(StandardFinding(
                    rule_name='multi-tenant-bypass-rls-superuser',
                    message=f'Using superuser "{superuser}" bypasses RLS policies',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=f'{var} = "{superuser}"',
                    cwe_id='CWE-250'
                ))
                break

    return findings


def _find_raw_query_without_transaction(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find raw SQL queries executed outside transaction context."""
    findings = []

    # Find .query() and .raw() calls
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.query%' OR callee_function LIKE '%.raw%')
        ORDER BY file, line
        LIMIT 30
    """)

    raw_queries = cursor.fetchall()

    for file, line, func, args in raw_queries:
        # Check if there's a transaction start within ±30 lines
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args
            WHERE file = ?
              AND line BETWEEN ? AND ?
              AND (callee_function LIKE '%transaction%' OR callee_function LIKE '%begin%')
        """, (file, line - 30, line + 5))

        in_transaction = cursor.fetchone()[0] > 0

        if not in_transaction:
            # Check if query accesses sensitive tables
            args_lower = (args or '').lower()
            has_sensitive = any(table in args_lower for table in patterns.SENSITIVE_TABLES)

            if has_sensitive:
                findings.append(StandardFinding(
                    rule_name='multi-tenant-raw-query-no-transaction',
                    message='Raw SQL on sensitive table outside transaction - RLS context may not apply',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{func}(...)',
                    cwe_id='CWE-863'
                ))

    return findings


def _find_orm_missing_tenant_scope(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find ORM queries without tenant filtering using orm_queries table."""
    findings = []

    # Query orm_queries for findAll/findOne operations
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, query_type
        FROM orm_queries
        WHERE (query_type LIKE '%.findAll%' OR query_type LIKE '%.findOne%')
        ORDER BY file, line
        LIMIT 40
    """)

    seen = set()

    for file, line, query_type in cursor.fetchall():
        # Check if model is sensitive
        model_name = query_type.split('.')[0] if '.' in query_type else query_type
        model_lower = model_name.lower()

        is_sensitive = any(table in model_lower for table in patterns.SENSITIVE_TABLES)

        if not is_sensitive:
            continue

        # Check if there's tenant filtering in nearby assignments (within 5 lines)
        cursor.execute("""
            SELECT COUNT(*)
            FROM assignments
            WHERE file = ?
              AND line BETWEEN ? AND ?
              AND (source_expr LIKE '%facility_id%'
                   OR source_expr LIKE '%tenant_id%'
                   OR source_expr LIKE '%account_id%')
        """, (file, line - 5, line + 5))

        has_tenant = cursor.fetchone()[0] > 0

        if not has_tenant:
            key = f"{file}:{line}"
            if key in seen:
                continue
            seen.add(key)

            findings.append(StandardFinding(
                rule_name='multi-tenant-orm-no-tenant-scope',
                message=f'ORM query on {model_name} without tenant filtering',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=query_type,
                cwe_id='CWE-863'
            ))

    return findings


def _find_bulk_operations_without_tenant(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find bulk INSERT/UPDATE/DELETE operations without tenant field."""
    findings = []

    # Find bulk operations in sql_queries
    # NOTE: frontend/test filtering handled by METADATA
    # Keep migration check - bulk operations in migrations are schema changes, not tenant data
    cursor.execute("""
        SELECT file_path, line_number, query_text, command, tables
        FROM sql_queries
        WHERE command IN ('INSERT', 'UPDATE', 'DELETE')
          AND (query_text LIKE '%INSERT INTO%' OR query_text LIKE '%UPDATE%' OR query_text LIKE '%DELETE FROM%')
          AND file_path NOT LIKE '%migration%'
        ORDER BY file_path, line_number
        LIMIT 20
    """)

    for file, line, query, command, tables in cursor.fetchall():
        # Check if tables are sensitive
        tables_list = (tables or '').split(',')
        has_sensitive = any(
            any(sensitive in table.lower() for sensitive in patterns.SENSITIVE_TABLES)
            for table in tables_list
        )

        if not has_sensitive:
            continue

        query_lower = query.lower()

        # Check if tenant field is present
        has_tenant_field = any(field in query_lower for field in patterns.TENANT_FIELDS)

        if not has_tenant_field:
            if command == 'INSERT':
                severity = Severity.HIGH
                message = f'Bulk INSERT without tenant field - data will be unfiltered'
            elif command == 'UPDATE':
                severity = Severity.CRITICAL
                message = f'Bulk UPDATE without tenant field - cross-tenant data leak'
            else:  # DELETE
                severity = Severity.CRITICAL
                message = f'Bulk DELETE without tenant field - cross-tenant data deletion'

            findings.append(StandardFinding(
                rule_name='multi-tenant-bulk-operation-no-tenant',
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                cwe_id='CWE-863'
            ))

    return findings


def _find_cross_tenant_joins(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find JOINs between tables without tenant field in ON clause."""
    findings = []

    # NOTE: frontend/test filtering handled by METADATA
    # Keep migration check - JOINs in migrations are schema exploration, not queries
    cursor.execute("""
        SELECT file_path, line_number, query_text, command, tables
        FROM sql_queries
        WHERE command = 'SELECT'
          AND (query_text LIKE '%JOIN%' OR query_text LIKE '%join%')
          AND file_path NOT LIKE '%migration%'
        ORDER BY file_path, line_number
        LIMIT 25
    """)

    for file, line, query, command, tables in cursor.fetchall():
        query_upper = query.upper()
        query_lower = query.lower()

        # Check if JOIN has tenant field in ON clause
        if ' ON ' in query_upper or ' on ' in query_lower:
            # Extract ON clause content
            on_start = query_upper.find(' ON ')
            if on_start == -1:
                on_start = query_lower.find(' on ')

            if on_start != -1:
                # Get 200 chars after ON
                on_clause = query[on_start:on_start + 200]

                # Check if tenant field is in ON clause
                has_tenant_in_on = any(field in on_clause.lower() for field in patterns.TENANT_FIELDS)

                if not has_tenant_in_on:
                    findings.append(StandardFinding(
                        rule_name='multi-tenant-cross-tenant-join',
                        message='JOIN without tenant field in ON clause - potential cross-tenant data leak',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='security',
                        snippet=query[:100] + '...' if len(query) > 100 else query,
                        cwe_id='CWE-863'
                    ))

    return findings


def _find_subquery_without_tenant(cursor, patterns: MultiTenantPatterns) -> List[StandardFinding]:
    """Find subqueries on sensitive tables without tenant filtering."""
    findings = []

    # NOTE: frontend/test filtering handled by METADATA
    # Keep migration check - subqueries in migrations are schema queries
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command = 'SELECT'
          AND query_text LIKE '%(SELECT%'
          AND file_path NOT LIKE '%migration%'
        ORDER BY file_path, line_number
        LIMIT 20
    """)

    for file, line, query, command in cursor.fetchall():
        query_lower = query.lower()

        # Check if subquery has sensitive table
        has_sensitive = any(f' {table} ' in query_lower for table in patterns.SENSITIVE_TABLES)

        if not has_sensitive:
            continue

        # Check if subquery has tenant filtering
        # Look for WHERE clause in subquery section
        subquery_start = query_lower.find('(select')
        if subquery_start != -1:
            subquery_end = query_lower.find(')', subquery_start)
            if subquery_end != -1:
                subquery = query_lower[subquery_start:subquery_end]

                has_where = 'where' in subquery
                has_tenant = any(field in subquery for field in patterns.TENANT_FIELDS)

                if has_where and not has_tenant:
                    findings.append(StandardFinding(
                        rule_name='multi-tenant-subquery-no-tenant',
                        message='Subquery on sensitive table without tenant filtering',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='security',
                        snippet=query[:100] + '...' if len(query) > 100 else query,
                        cwe_id='CWE-863'
                    ))
                elif not has_where:
                    findings.append(StandardFinding(
                        rule_name='multi-tenant-subquery-no-where',
                        message='Subquery on sensitive table without WHERE clause',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        snippet=query[:100] + '...' if len(query) > 100 else query,
                        cwe_id='CWE-863'
                    ))

    return findings