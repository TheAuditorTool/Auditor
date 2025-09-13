"""Input Validation Security Analyzer - Database-Driven Implementation.

Detects input validation and deserialization issues using indexed data.
NO AST TRAVERSAL. Just efficient SQL queries.

This rule follows the TRUE golden standard:
1. Query the database for pre-indexed data
2. Process results with simple logic  
3. Return findings

Detects:
- Missing input validation before database operations
- Unsafe deserialization (eval, exec, pickle.loads)
- Missing CSRF protection on state-changing routes
- Direct use of request data in sensitive operations
"""

import sqlite3
import json
import re
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_input_validation_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect input validation security issues using indexed data.
    
    Main entry point that delegates to specific detectors.
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, identify request/input variables
        request_vars = _identify_request_variables(cursor)
        validated_vars = _identify_validated_variables(cursor)
        
        # Run each validation check
        findings.extend(_find_missing_validation(cursor, request_vars, validated_vars))
        findings.extend(_find_unsafe_deserialization(cursor, request_vars))
        findings.extend(_find_missing_csrf_protection(cursor))
        findings.extend(_find_direct_request_usage(cursor))
        findings.extend(_find_mass_assignment(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# HELPER: Identify Request Variables
# ============================================================================

def _identify_request_variables(cursor) -> Set[str]:
    """Identify variables that hold request/user input data."""
    request_vars = set()
    
    # Find assignments from request sources
    request_sources = [
        'req.body', 'req.query', 'req.params', 'req.headers',
        'request.body', 'request.query', 'request.params', 'request.form',
        'request.json', 'request.args', 'request.data', 'request.files',
        'params', 'query', 'body', 'form', 'args'
    ]
    
    for source in request_sources:
        cursor.execute("""
            SELECT DISTINCT a.target_var
            FROM assignments a
            WHERE a.source_expr LIKE ?
        """, [f'%{source}%'])
        
        for row in cursor.fetchall():
            request_vars.add(row[0])
    
    # Also find function parameters in route handlers
    cursor.execute("""
        SELECT DISTINCT s.name
        FROM symbols s
        WHERE s.type = 'parameter'
          AND s.in_function IN (
              SELECT DISTINCT f.caller_function
              FROM function_call_args f
              WHERE f.callee_function LIKE '%route%'
                 OR f.callee_function LIKE '%get%'
                 OR f.callee_function LIKE '%post%'
                 OR f.callee_function LIKE '%put%'
                 OR f.callee_function LIKE '%delete%'
          )
    """)
    
    for row in cursor.fetchall():
        if row[0] in ['req', 'request', 'res', 'response']:
            continue  # Skip framework objects
        request_vars.add(row[0])
    
    return request_vars


# ============================================================================
# HELPER: Identify Validated Variables
# ============================================================================

def _identify_validated_variables(cursor) -> Set[str]:
    """Identify variables that have been validated."""
    validated_vars = set()
    
    # Find variables passed to validation functions
    validation_functions = [
        'validate', 'verify', 'check', 'sanitize', 'clean',
        'isValid', 'validateInput', 'validateData', 
        'schema.validate', 'joi.validate', 'yup.validate'
    ]
    
    for func in validation_functions:
        cursor.execute("""
            SELECT DISTINCT f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
        """, [f'%{func}%'])
        
        for row in cursor.fetchall():
            # Extract variable names from arguments
            arg_expr = row[0]
            # Simple extraction - could be improved
            import re
            var_matches = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', arg_expr)
            for var in var_matches:
                validated_vars.add(var)
    
    return validated_vars


# ============================================================================
# CHECK 1: Missing Input Validation
# ============================================================================

def _find_missing_validation(cursor, request_vars: Set[str], validated_vars: Set[str]) -> List[StandardFinding]:
    """Find database operations using unvalidated input."""
    findings = []
    
    # Database operation functions
    db_operations = [
        'create', 'update', 'save', 'insert', 'query', 'execute',
        'filter', 'find', 'findOne', 'findOneAndUpdate', 
        'updateOne', 'updateMany', 'insertOne', 'insertMany',
        'bulk_create', 'bulk_update', 'get_or_create'
    ]
    
    for op in db_operations:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
            ORDER BY f.file, f.line
        """, [f'%{op}%'])
        
        for file, line, func, args in cursor.fetchall():
            # Check if arguments contain request variables
            unvalidated_vars = []
            for var in request_vars:
                if var not in validated_vars and var in args:
                    unvalidated_vars.append(var)
            
            if unvalidated_vars:
                findings.append(StandardFinding(
                    rule_name='input-missing-validation',
                    message=f'Database operation {func} uses unvalidated input: {", ".join(unvalidated_vars)}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{func}({unvalidated_vars[0]}...)',
                    fix_suggestion='Validate all user input before database operations',
                    cwe_id='CWE-20'  # Improper Input Validation
                ))
    
    # Also check for direct req.body usage
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.argument_expr LIKE '%req.body%' 
               OR f.argument_expr LIKE '%request.body%'
               OR f.argument_expr LIKE '%request.json%')
          AND f.callee_function IN ({})
        ORDER BY f.file, f.line
    """.format(','.join(['?' for _ in db_operations])), db_operations)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='input-direct-request-body',
            message=f'Direct use of request body in {func} without validation',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{func}(req.body)',
            fix_suggestion='Validate and sanitize request body before use',
            cwe_id='CWE-20'
        ))
    
    return findings


# ============================================================================
# CHECK 2: Unsafe Deserialization
# ============================================================================

def _find_unsafe_deserialization(cursor, request_vars: Set[str]) -> List[StandardFinding]:
    """Find unsafe deserialization of user input."""
    findings = []
    
    # Dangerous deserialization functions
    dangerous_functions = {
        # Python
        'eval': ('eval', 'CRITICAL', 'Never use eval with user input'),
        'exec': ('exec', 'CRITICAL', 'Never use exec with user input'),
        'compile': ('compile', 'CRITICAL', 'Avoid compile with user input'),
        '__import__': ('__import__', 'CRITICAL', 'Dynamic imports are dangerous'),
        'pickle.loads': ('pickle.loads', 'CRITICAL', 'Use JSON instead of pickle'),
        'yaml.load': ('yaml.load', 'HIGH', 'Use yaml.safe_load() instead'),
        'marshal.loads': ('marshal.loads', 'HIGH', 'Avoid marshal with untrusted data'),
        
        # JavaScript
        'Function': ('new Function()', 'CRITICAL', 'Never create functions from strings'),
        'eval': ('eval', 'CRITICAL', 'Never use eval with user input'),
        'setTimeout': ('setTimeout with string', 'HIGH', 'Use function reference, not string'),
        'setInterval': ('setInterval with string', 'HIGH', 'Use function reference, not string')
    }
    
    for func, (name, severity, suggestion) in dangerous_functions.items():
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = ?
               OR f.callee_function LIKE ?
            ORDER BY f.file, f.line
        """, [func, f'%.{func}'])
        
        for file, line, called_func, args in cursor.fetchall():
            # Check if using request data or variables
            uses_user_input = False
            
            # Check for direct request usage
            if any(req in args for req in ['req.', 'request.', 'params', 'query', 'body']):
                uses_user_input = True
            
            # Check for request variables
            for var in request_vars:
                if var in args:
                    uses_user_input = True
                    break
            
            if uses_user_input:
                findings.append(StandardFinding(
                    rule_name='input-unsafe-deserialization',
                    message=f'Unsafe deserialization using {name} with user input',
                    file_path=file,
                    line=line,
                    severity=Severity[severity],
                    category='security',
                    snippet=f'{called_func}(user_input)',
                    fix_suggestion=suggestion,
                    cwe_id='CWE-502'  # Deserialization of Untrusted Data
                ))
    
    # Check JSON.parse without try/catch
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'JSON.parse'
          AND (f.argument_expr LIKE '%req.%'
               OR f.argument_expr LIKE '%request.%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, args in cursor.fetchall():
        # Check if there's error handling nearby
        cursor.execute("""
            SELECT 1 FROM symbols s
            WHERE s.path = ?
              AND s.type = 'catch'
              AND ABS(s.line - ?) <= 5
            LIMIT 1
        """, [file, line])
        
        if not cursor.fetchone():
            findings.append(StandardFinding(
                rule_name='input-json-parse-no-catch',
                message='JSON.parse of user input without error handling',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                snippet='JSON.parse(req.body)',
                fix_suggestion='Wrap JSON.parse in try-catch block',
                cwe_id='CWE-502'
            ))
    
    return findings


# ============================================================================
# CHECK 3: Missing CSRF Protection
# ============================================================================

def _find_missing_csrf_protection(cursor) -> List[StandardFinding]:
    """Find state-changing routes without CSRF protection."""
    findings = []
    
    # Find state-changing route handlers
    state_changing_methods = ['post', 'put', 'delete', 'patch']
    
    for method in state_changing_methods:
        cursor.execute("""
            SELECT DISTINCT f.file, f.line, f.callee_function, f.caller_function
            FROM function_call_args f
            WHERE (f.callee_function LIKE ? 
                   OR f.callee_function LIKE ?
                   OR f.callee_function LIKE ?)
            ORDER BY f.file, f.line
        """, [f'%.{method}', f'app.{method}', f'router.{method}'])
        
        for file, line, route_func, handler_func in cursor.fetchall():
            # Check for CSRF protection nearby
            cursor.execute("""
                SELECT 1 FROM function_call_args f2
                WHERE f2.file = ?
                  AND ABS(f2.line - ?) <= 20
                  AND (f2.callee_function LIKE '%csrf%'
                       OR f2.callee_function LIKE '%csurf%'
                       OR f2.argument_expr LIKE '%csrf%')
                LIMIT 1
            """, [file, line])
            
            has_csrf = cursor.fetchone() is not None
            
            # Also check for CSRF decorators/annotations (Python)
            if not has_csrf and file.endswith('.py'):
                cursor.execute("""
                    SELECT 1 FROM symbols s
                    WHERE s.path = ?
                      AND s.type = 'decorator'
                      AND s.name LIKE '%csrf%'
                      AND ABS(s.line - ?) <= 5
                    LIMIT 1
                """, [file, line])
                
                has_csrf = cursor.fetchone() is not None
            
            if not has_csrf:
                findings.append(StandardFinding(
                    rule_name='input-missing-csrf',
                    message=f'State-changing route {method.upper()} without CSRF protection',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{route_func}(...)',
                    fix_suggestion='Add CSRF protection middleware or decorator',
                    cwe_id='CWE-352'  # Cross-Site Request Forgery
                ))
    
    return findings


# ============================================================================
# CHECK 4: Direct Request Usage
# ============================================================================

def _find_direct_request_usage(cursor) -> List[StandardFinding]:
    """Find direct usage of request data in sensitive operations."""
    findings = []
    
    # Sensitive operations that shouldn't use raw request data
    sensitive_ops = [
        'sendEmail', 'sendMail', 'send_email', 'mail',
        'writeFile', 'write_file', 'fs.write',
        'execute', 'exec', 'spawn', 'system',
        'redirect', 'render', 'send', 'json'
    ]
    
    for op in sensitive_ops:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
              AND (f.argument_expr LIKE '%req.%'
                   OR f.argument_expr LIKE '%request.%')
            ORDER BY f.file, f.line
        """, [f'%{op}%'])
        
        for file, line, func, args in cursor.fetchall():
            # Determine severity based on operation
            if any(cmd in func.lower() for cmd in ['exec', 'spawn', 'system']):
                severity = Severity.CRITICAL
                cwe = 'CWE-78'  # OS Command Injection
                suggestion = 'Never use user input in system commands'
            elif 'redirect' in func.lower():
                severity = Severity.HIGH
                cwe = 'CWE-601'  # Open Redirect
                suggestion = 'Validate redirect URLs against whitelist'
            elif 'write' in func.lower():
                severity = Severity.HIGH
                cwe = 'CWE-73'  # External Control of File Name
                suggestion = 'Validate and sanitize file paths'
            else:
                severity = Severity.MEDIUM
                cwe = 'CWE-20'
                suggestion = 'Validate input before use in sensitive operations'
            
            findings.append(StandardFinding(
                rule_name='input-direct-usage',
                message=f'Direct use of request data in {func}',
                file_path=file,
                line=line,
                severity=severity,
                category='security',
                snippet=f'{func}(req...)',
                fix_suggestion=suggestion,
                cwe_id=cwe
            ))
    
    return findings


# ============================================================================
# CHECK 5: Mass Assignment
# ============================================================================

def _find_mass_assignment(cursor) -> List[StandardFinding]:
    """Find potential mass assignment vulnerabilities."""
    findings = []
    
    # ORM update operations that might allow mass assignment
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%update%'
               OR f.callee_function LIKE '%create%'
               OR f.callee_function LIKE '%save%')
          AND (f.argument_expr LIKE '%...%'  -- Spread operator
               OR f.argument_expr LIKE '%req.body%'
               OR f.argument_expr LIKE '%request.body%'
               OR f.argument_expr LIKE '%**%')  -- Python kwargs
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        # Check for spread operator or direct body usage
        if '...' in args or '**' in args or 'req.body' in args or 'request.body' in args:
            findings.append(StandardFinding(
                rule_name='input-mass-assignment',
                message=f'Potential mass assignment vulnerability in {func}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=f'{func}(...req.body)',
                fix_suggestion='Explicitly whitelist allowed fields instead of using spread/mass assignment',
                cwe_id='CWE-915'  # Mass Assignment
            ))
    
    # Check for Object.assign with request data
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'Object.assign'
          AND (f.argument_expr LIKE '%req.body%'
               OR f.argument_expr LIKE '%request.body%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='input-object-assign',
            message='Object.assign with request body enables mass assignment',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet='Object.assign(model, req.body)',
            fix_suggestion='Use explicit field assignment or validation library',
            cwe_id='CWE-915'
        ))
    
    return findings