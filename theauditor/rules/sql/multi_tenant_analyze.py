"""Multi-Tenant Security Analyzer - Pure Database Implementation.

This module detects multi-tenant security issues using ONLY indexed database data.
NO AST TRAVERSAL. NO FILE I/O. Just efficient SQL queries against the sql_queries table.

The sql_queries table contains 4,723 actual SQL queries with:
- file_path: Where the query is located
- line_number: Line in source file
- query_text: The actual SQL query text
- command: Type of query (SELECT, INSERT, UPDATE, DELETE)
- tables: Tables referenced in the query
"""

import sqlite3
from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_multi_tenant_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect multi-tenant security issues using indexed SQL queries.
    
    Returns:
        List of multi-tenant security findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First check if we have SQL queries indexed
        cursor.execute("SELECT COUNT(*) FROM sql_queries")
        query_count = cursor.fetchone()[0]
        
        if query_count == 0:
            # No SQL queries indexed, fallback to function call analysis
            findings.extend(_find_tenant_issues_in_function_calls(cursor))
        else:
            # Primary analysis using actual SQL queries
            findings.extend(_find_cross_tenant_data_leaks(cursor))
            findings.extend(_find_queries_without_tenant_filter(cursor))
            findings.extend(_find_global_delete_operations(cursor))
            findings.extend(_find_missing_rls_policies(cursor))
            findings.extend(_find_direct_id_access(cursor))
            findings.extend(_find_join_without_tenant(cursor))
            findings.extend(_find_bulk_operations(cursor))
            findings.extend(_find_cross_tenant_joins(cursor))
        
        # Secondary analysis using function calls and symbols
        findings.extend(_find_missing_rls_context(cursor))
        findings.extend(_find_bypass_rls_with_superuser(cursor))
        findings.extend(_find_missing_tenant_scopes(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# PRIMARY DETECTION: Using sql_queries table
# ============================================================================

def _find_cross_tenant_data_leaks(cursor) -> List[StandardFinding]:
    """Find queries on sensitive tables without tenant filtering in actual SQL queries."""
    findings = []
    
    # Sensitive tables requiring tenant isolation
    SENSITIVE_TABLES = [
        'products', 'orders', 'inventory', 'customers', 'users',
        'locations', 'transfers', 'invoices', 'payments', 'shipments',
        'accounts', 'transactions', 'balances', 'billing', 'subscriptions'
    ]
    
    # Tenant filtering fields
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id', 'company_id', 'store_id']
    
    # Query all SQL queries that touch sensitive tables
    for table in SENSITIVE_TABLES:
        cursor.execute("""
            SELECT file_path, line_number, query_text, command, tables
            FROM sql_queries
            WHERE tables LIKE ?
               OR query_text LIKE ?
            ORDER BY file_path, line_number
        """, (f'%{table}%', f'%{table}%'))
        
        for file, line, query, command, tables in cursor.fetchall():
            query_lower = query.lower()
            
            # Check if it has tenant filtering
            has_tenant_filter = any(field in query_lower for field in TENANT_FIELDS)
            
            if not has_tenant_filter:
                # Check if it has WHERE clause at all
                if 'where' in query_lower:
                    severity = Severity.HIGH
                    message = f'{command} on {table} without tenant filtering'
                else:
                    severity = Severity.CRITICAL
                    message = f'{command} on {table} with NO WHERE clause - cross-tenant leak'
                
                findings.append(StandardFinding(
                    rule_name='multi-tenant-data-leak',
                    message=message,
                    file_path=file,
                    line=line,
                    severity=severity,
                    category='security',
                    snippet=query[:100] + '...' if len(query) > 100 else query,
                    fix_suggestion='Add tenant filtering: WHERE facility_id = ? or tenant_id = ?',
                    cwe_id='CWE-863'
                ))
    
    return findings


def _find_queries_without_tenant_filter(cursor) -> List[StandardFinding]:
    """Find all queries missing tenant isolation filters."""
    findings = []
    
    # Tenant fields that should appear in WHERE clauses
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id', 'company_id', 'store_id']
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command, tables
        FROM sql_queries
        WHERE command IN ('SELECT', 'UPDATE', 'DELETE')
          AND query_text LIKE '%WHERE%'
          AND tables IS NOT NULL
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command, tables in cursor.fetchall():
        query_lower = query.lower()
        
        # Skip system tables and common non-tenant tables
        if any(sys_table in tables.lower() for sys_table in ['migrations', 'schema', 'pg_', 'information_schema']):
            continue
        
        # Check if query has tenant filtering
        has_tenant = any(field in query_lower for field in TENANT_FIELDS)
        
        if not has_tenant:
            # Check if it's a likely multi-tenant table (has multiple table references)
            if ',' in tables or 'join' in query_lower:
                findings.append(StandardFinding(
                    rule_name='multi-tenant-missing-filter',
                    message=f'{command} query potentially missing tenant isolation',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='security',
                    snippet=query[:100] + '...' if len(query) > 100 else query,
                    fix_suggestion='Consider adding tenant field (facility_id, tenant_id) to WHERE clause',
                    cwe_id='CWE-863'
                ))
    
    return findings


def _find_global_delete_operations(cursor) -> List[StandardFinding]:
    """Find DELETE operations that might affect multiple tenants."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, tables
        FROM sql_queries
        WHERE command = 'DELETE'
        ORDER BY file_path, line_number
    """)
    
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id', 'company_id', 'store_id']
    
    for file, line, query, tables in cursor.fetchall():
        query_lower = query.lower()
        
        # Check if it has tenant filtering
        has_tenant = any(field in query_lower for field in TENANT_FIELDS)
        
        if not has_tenant:
            if 'where' not in query_lower:
                severity = Severity.CRITICAL
                message = 'DELETE without WHERE - will delete across ALL tenants'
            else:
                severity = Severity.HIGH
                message = 'DELETE without tenant filter - may affect multiple tenants'
            
            findings.append(StandardFinding(
                rule_name='multi-tenant-global-delete',
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                fix_suggestion='Add tenant filter to DELETE: WHERE facility_id = ? AND ...',
                cwe_id='CWE-863'
            ))
    
    return findings


def _find_missing_rls_policies(cursor) -> List[StandardFinding]:
    """Find CREATE POLICY statements without proper USING clause."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE query_text LIKE '%CREATE POLICY%'
           OR query_text LIKE '%create policy%'
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
                fix_suggestion="Add USING (facility_id = current_setting('app.current_facility_id')::uuid)",
                cwe_id='CWE-863'
            ))
        else:
            # Check if USING clause has proper tenant filtering
            if not any(field in query.lower() for field in ['facility_id', 'tenant_id', 'current_setting']):
                findings.append(StandardFinding(
                    rule_name='multi-tenant-rls-weak-using',
                    message='RLS policy USING clause missing tenant field check',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=query[:100] + '...' if len(query) > 100 else query,
                    fix_suggestion='Ensure USING clause checks facility_id or tenant_id',
                    cwe_id='CWE-863'
                ))
    
    return findings


def _find_direct_id_access(cursor) -> List[StandardFinding]:
    """Find queries accessing records by ID without tenant check."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command, tables
        FROM sql_queries
        WHERE (query_text LIKE '%WHERE id = %'
               OR query_text LIKE '%WHERE id=%'
               OR query_text LIKE '%WHERE "id" = %'
               OR query_text LIKE '%WHERE `id` = %')
          AND command IN ('SELECT', 'UPDATE', 'DELETE')
        ORDER BY file_path, line_number
    """)
    
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id']
    
    for file, line, query, command, tables in cursor.fetchall():
        query_lower = query.lower()
        
        # Check if it also has tenant filtering
        has_tenant = any(field in query_lower for field in TENANT_FIELDS)
        
        if not has_tenant:
            findings.append(StandardFinding(
                rule_name='multi-tenant-direct-id-access',
                message=f'{command} by ID without tenant validation - potential cross-tenant access',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                fix_suggestion='Add tenant check: WHERE id = ? AND facility_id = ?',
                cwe_id='CWE-863'
            ))
    
    return findings


def _find_join_without_tenant(cursor) -> List[StandardFinding]:
    """Find JOIN operations without tenant conditions."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, tables
        FROM sql_queries
        WHERE (query_text LIKE '%JOIN%' OR query_text LIKE '%join%')
          AND command = 'SELECT'
        ORDER BY file_path, line_number
    """)
    
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id']
    
    for file, line, query, tables in cursor.fetchall():
        query_lower = query.lower()
        
        # Count JOINs
        join_count = query_lower.count(' join ') + query_lower.count(' left join ') + query_lower.count(' inner join ')
        
        if join_count > 0:
            # Check if JOIN conditions include tenant fields
            has_tenant_join = any(f'.{field}' in query_lower or f' {field}' in query_lower for field in TENANT_FIELDS)
            
            if not has_tenant_join:
                findings.append(StandardFinding(
                    rule_name='multi-tenant-join-leak',
                    message='JOIN without tenant field in join condition - may join across tenants',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=query[:100] + '...' if len(query) > 100 else query,
                    fix_suggestion='Add tenant field to JOIN: ON a.id = b.id AND a.facility_id = b.facility_id',
                    cwe_id='CWE-863'
                ))
    
    return findings


def _find_bulk_operations(cursor) -> List[StandardFinding]:
    """Find bulk INSERT/UPDATE operations that might affect tenant isolation."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command IN ('INSERT', 'UPDATE')
          AND (query_text LIKE '%VALUES%(%,%'
               OR query_text LIKE '%INSERT INTO%SELECT%'
               OR query_text LIKE '%UPDATE%SET%=%SELECT%')
        ORDER BY file_path, line_number
    """)
    
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id']
    
    for file, line, query, command in cursor.fetchall():
        query_lower = query.lower()
        
        # Check if tenant field is included
        has_tenant = any(field in query_lower for field in TENANT_FIELDS)
        
        if not has_tenant:
            if command == 'INSERT':
                message = 'Bulk INSERT without tenant field - records may lack tenant association'
            else:
                message = 'Bulk UPDATE without tenant filter - may affect multiple tenants'
            
            findings.append(StandardFinding(
                rule_name='multi-tenant-bulk-operation',
                message=message,
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                fix_suggestion='Ensure tenant field is included in bulk operations',
                cwe_id='CWE-863'
            ))
    
    return findings


def _find_cross_tenant_joins(cursor) -> List[StandardFinding]:
    """Find queries that might inadvertently join data across tenants."""
    findings = []
    
    # Find queries with subqueries that might leak tenant data
    cursor.execute("""
        SELECT file_path, line_number, query_text, tables
        FROM sql_queries
        WHERE command = 'SELECT'
          AND (query_text LIKE '%(SELECT%FROM%'
               OR query_text LIKE '%IN (SELECT%'
               OR query_text LIKE '%EXISTS (SELECT%')
        ORDER BY file_path, line_number
    """)
    
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id']
    
    for file, line, query, tables in cursor.fetchall():
        query_lower = query.lower()
        
        # Count tenant field occurrences
        tenant_count = sum(query_lower.count(field) for field in TENANT_FIELDS)
        
        # Subqueries should have tenant filtering in both outer and inner query
        if tenant_count < 2:  # Less than 2 occurrences suggests missing tenant filter
            findings.append(StandardFinding(
                rule_name='multi-tenant-subquery-leak',
                message='Subquery without consistent tenant filtering - potential cross-tenant data access',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                fix_suggestion='Ensure both outer and inner queries filter by tenant field',
                cwe_id='CWE-863'
            ))
    
    return findings


# ============================================================================
# SECONDARY DETECTION: Using function_call_args and symbols  
# ============================================================================

def _find_tenant_issues_in_function_calls(cursor) -> List[StandardFinding]:
    """Fallback detection using function calls when sql_queries is empty."""
    findings = []
    
    # Find execute/query calls without tenant filtering
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%execute%'
               OR f.callee_function LIKE '%query%')
          AND (f.argument_expr LIKE '%SELECT%'
               OR f.argument_expr LIKE '%UPDATE%'
               OR f.argument_expr LIKE '%DELETE%')
        ORDER BY f.file, f.line
    """)
    
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id']
    
    for file, line, func, args in cursor.fetchall():
        if args:
            args_lower = args.lower()
            has_tenant = any(field in args_lower for field in TENANT_FIELDS)
            
            if not has_tenant and 'where' in args_lower:
                findings.append(StandardFinding(
                    rule_name='multi-tenant-missing-filter-fallback',
                    message='Query without tenant filtering detected',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                    fix_suggestion='Add tenant field to WHERE clause',
                    cwe_id='CWE-863'
                ))
    
    return findings


def _find_missing_rls_context(cursor) -> List[StandardFinding]:
    """Find transactions without SET LOCAL for RLS context."""
    findings = []
    
    # Transaction patterns
    transaction_patterns = [
        'transaction', 'begin_nested', 'atomic', 'sequelize.transaction',
        'db.transaction', 'START TRANSACTION', 'BEGIN'
    ]
    
    # Find transaction starts
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE ({})
        ORDER BY f.file, f.line
    """.format(' OR '.join([f"f.callee_function LIKE '%{pattern}%'" for pattern in transaction_patterns])))
    
    transactions = cursor.fetchall()
    
    for file, line, func in transactions:
        # Check if there's SET LOCAL within transaction scope (±30 lines)
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.line BETWEEN ? AND ?
              AND f2.argument_expr LIKE '%SET LOCAL%'
              AND (f2.argument_expr LIKE '%current_facility_id%' 
                   OR f2.argument_expr LIKE '%current_tenant_id%')
        """, (file, line, line + 30))
        
        has_set_local = cursor.fetchone()[0] > 0
        
        # Also check assignments for SET LOCAL
        if not has_set_local:
            cursor.execute("""
                SELECT COUNT(*)
                FROM assignments a
                WHERE a.file = ?
                  AND a.line BETWEEN ? AND ?
                  AND a.source_expr LIKE '%SET LOCAL%'
                  AND (a.source_expr LIKE '%current_facility_id%'
                       OR a.source_expr LIKE '%current_tenant_id%')
            """, (file, line, line + 30))
            
            has_set_local = cursor.fetchone()[0] > 0
        
        if not has_set_local:
            findings.append(StandardFinding(
                rule_name='missing-rls-context-setting',
                message='Transaction without SET LOCAL app.current_facility_id',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=f'{func}(...)',
                fix_suggestion='Add SET LOCAL app.current_facility_id = ? at transaction start',
                cwe_id='CWE-863'
            ))
    
    return findings


def _find_bypass_rls_with_superuser(cursor) -> List[StandardFinding]:
    """Find usage of superuser database connections."""
    findings = []
    
    # Superuser names
    SUPERUSER_NAMES = ['postgres', 'root', 'admin', 'superuser', 'sa', 'administrator']
    
    # Database user variable patterns
    DB_USER_VARS = ['DB_USER', 'DATABASE_USER', 'POSTGRES_USER', 'PG_USER', 'DB_USERNAME']
    
    # Check assignments to database user variables
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE ({})
    """.format(' OR '.join([f"a.target_var LIKE '%{var}%'" for var in DB_USER_VARS])))
    
    db_user_assignments = cursor.fetchall()
    
    for file, line, var, expr in db_user_assignments:
        if expr:
            expr_lower = expr.lower()
            for superuser in SUPERUSER_NAMES:
                if superuser in expr_lower:
                    findings.append(StandardFinding(
                        rule_name='bypass-rls-with-superuser',
                        message=f'Using superuser "{superuser}" bypasses RLS policies',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        snippet=f'{var} = "{superuser}"',
                        fix_suggestion='Use a limited database user with RLS policies applied',
                        cwe_id='CWE-250'
                    ))
                    break
    
    # Check environment variable references
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.symbol_type = 'string'
          AND ({})
    """.format(' OR '.join([f"s.name LIKE '%{superuser}%'" for superuser in SUPERUSER_NAMES])))
    
    superuser_strings = cursor.fetchall()
    
    for file, line, name in superuser_strings:
        # Check if it's in a database configuration context
        cursor.execute("""
            SELECT COUNT(*)
            FROM symbols s2
            WHERE s2.file = ?
              AND s2.line BETWEEN ? AND ?
              AND (s2.name LIKE '%database%' OR s2.name LIKE '%sequelize%' OR s2.name LIKE '%connection%')
        """, (file, line - 10, line + 10))
        
        if cursor.fetchone()[0] > 0:
            findings.append(StandardFinding(
                rule_name='bypass-rls-with-superuser',
                message='Potential superuser connection string detected',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=name[:50],
                fix_suggestion='Ensure database connections use limited users with RLS',
                cwe_id='CWE-250'
            ))
    
    return findings


def _find_missing_tenant_scopes(cursor) -> List[StandardFinding]:
    """Find ORM models without tenant scoping."""
    findings = []
    
    # Sequelize model patterns
    model_patterns = ['Model.findAll', 'Model.findOne', 'Model.update', 'Model.destroy']
    
    # Find ORM model operations
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE ({})
    """.format(' OR '.join([f"f.callee_function LIKE '%{pattern}%'" for pattern in model_patterns])))
    
    model_calls = cursor.fetchall()
    
    TENANT_FIELDS = ['facility_id', 'tenant_id', 'organization_id']
    
    for file, line, func, args in model_calls:
        # Check if it has tenant filtering in where clause
        if args:
            args_lower = args.lower()
            has_tenant_filter = any(field in args_lower for field in TENANT_FIELDS)
            
            if not has_tenant_filter and 'where' in args_lower:
                findings.append(StandardFinding(
                    rule_name='missing-tenant-scope',
                    message='ORM query without tenant filtering',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{func}({{ where: {{...}} }})',
                    fix_suggestion='Add tenant field to WHERE clause or use scoped models',
                    cwe_id='CWE-863'
                ))
    
    # Check for Model definitions without defaultScope
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.symbol_type = 'class'
          AND (s.name LIKE '%Model%' OR s.name LIKE '%Schema%')
    """)
    
    model_definitions = cursor.fetchall()
    
    for file, line, name in model_definitions:
        # Check if defaultScope is defined nearby
        cursor.execute("""
            SELECT COUNT(*)
            FROM symbols s2
            WHERE s2.file = ?
              AND s2.line BETWEEN ? AND ?
              AND (s2.name LIKE '%defaultScope%' OR s2.name LIKE '%addScope%')
        """, (file, line, line + 50))
        
        has_scope = cursor.fetchone()[0] > 0
        
        if not has_scope:
            findings.append(StandardFinding(
                rule_name='model-without-default-scope',
                message=f'Model {name} without defaultScope for tenant isolation',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                snippet=f'class {name} extends Model',
                fix_suggestion='Consider adding defaultScope with facility_id filter',
                cwe_id='CWE-863'
            ))
    
    return findings




