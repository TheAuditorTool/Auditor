"""PII Data Flow Analyzer - Database-Driven Implementation.

Detects PII (Personally Identifiable Information) exposure using indexed data.
NO AST TRAVERSAL. Just efficient SQL queries.

This rule follows the TRUE golden standard:
1. Query the database for pre-indexed data
2. Process results with simple logic  
3. Return findings

Detects:
- PII in logging statements
- PII in error responses
- PII in URL parameters
- Unencrypted PII storage
- PII in exception handling
"""

import sqlite3
import json
import re
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


# PII field patterns to detect
PII_FIELD_PATTERNS = {
    'ssn', 'social_security', 'socialsecurity', 'sin',
    'email', 'email_address', 'emailaddress', 'mail',
    'phone', 'phone_number', 'phonenumber', 'mobile', 'cell',
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
    'credit_card', 'creditcard', 'cc_number', 'card_number', 'cardnumber',
    'dob', 'date_of_birth', 'dateofbirth', 'birthdate', 'birthday',
    'address', 'street', 'zipcode', 'postal_code', 'postalcode',
    'passport', 'drivers_license', 'driverslicense', 'license_number',
    'bank_account', 'bankaccount', 'account_number', 'accountnumber',
    'routing_number', 'routingnumber', 'iban', 'swift',
    'tax_id', 'taxid', 'ein', 'national_id', 'nationalid',
    'ip_address', 'ipaddress', 'mac_address', 'macaddress',
    'username', 'user_name', 'login', 'userid', 'user_id',
    'first_name', 'firstname', 'last_name', 'lastname', 'full_name', 'fullname',
    'maiden_name', 'maidenname', 'nickname',
    'salary', 'income', 'wage', 'compensation',
    'medical_record', 'medicalrecord', 'health_record', 'diagnosis',
    'biometric', 'fingerprint', 'retina', 'face_id', 'faceid'
}


def find_pii_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect PII exposure issues using indexed data.
    
    Main entry point that delegates to specific detectors.
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, identify PII variables
        pii_vars = _identify_pii_variables(cursor)
        
        # Run each PII check
        findings.extend(_find_pii_in_logging(cursor, pii_vars))
        findings.extend(_find_pii_in_error_responses(cursor, pii_vars))
        findings.extend(_find_pii_in_urls(cursor, pii_vars))
        findings.extend(_find_unencrypted_pii_storage(cursor, pii_vars))
        findings.extend(_find_pii_in_exceptions(cursor, pii_vars))
        findings.extend(_find_pii_in_client_code(cursor, pii_vars))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# HELPER: Identify PII Variables
# ============================================================================

def _identify_pii_variables(cursor) -> Set[str]:
    """Identify variables that contain PII data."""
    pii_vars = set()
    
    # Build conditions for PII patterns
    conditions = []
    for pattern in PII_FIELD_PATTERNS:
        conditions.append(f'a.target_var LIKE "%{pattern}%"')
        conditions.append(f's.name LIKE "%{pattern}%"')
    
    # Find assignments with PII field names
    cursor.execute(f"""
        SELECT DISTINCT a.target_var
        FROM assignments a
        WHERE {' OR '.join(conditions[:len(PII_FIELD_PATTERNS)])}
    """)
    
    for row in cursor.fetchall():
        pii_vars.add(row[0])
    
    # Find symbols with PII field names
    cursor.execute(f"""
        SELECT DISTINCT s.name
        FROM symbols s
        WHERE s.type IN ('variable', 'property', 'field')
          AND ({' OR '.join(conditions[len(PII_FIELD_PATTERNS):][:20])})
    """)
    
    for row in cursor.fetchall():
        pii_vars.add(row[0])
    
    return pii_vars


# ============================================================================
# CHECK 1: PII in Logging
# ============================================================================

def _find_pii_in_logging(cursor, pii_vars: Set[str]) -> List[StandardFinding]:
    """Find PII data being logged."""
    findings = []
    
    # Logging functions
    logging_functions = [
        'print', 'console.log', 'console.debug', 'console.info', 
        'console.warn', 'console.error', 'console.trace',
        'logger.debug', 'logger.info', 'logger.warning', 'logger.error',
        'logging.debug', 'logging.info', 'logging.warning', 'logging.error',
        'log.debug', 'log.info', 'log.warning', 'log.error',
        'winston.debug', 'winston.info', 'winston.warn', 'winston.error',
        'bunyan.debug', 'bunyan.info', 'bunyan.warn', 'bunyan.error',
        'pino.debug', 'pino.info', 'pino.warn', 'pino.error'
    ]
    
    for log_func in logging_functions:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = ?
               OR f.callee_function LIKE ?
            ORDER BY f.file, f.line
        """, [log_func, f'%.{log_func}'])
        
        for file, line, func, args in cursor.fetchall():
            # Check if arguments contain PII variables
            pii_found = []
            for var in pii_vars:
                if var in args:
                    pii_found.append(var)
            
            # Also check for PII patterns directly in arguments
            for pattern in PII_FIELD_PATTERNS:
                if pattern in args.lower() and '.' in args:
                    # Likely accessing a PII property
                    pii_found.append(pattern)
            
            if pii_found:
                findings.append(StandardFinding(
                    rule_name='pii-logged',
                    message=f'PII data logged: {", ".join(set(pii_found))}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='privacy',
                    snippet=f'{func}({pii_found[0]}...)',
                    fix_suggestion='Redact or mask PII before logging',
                    cwe_id='CWE-532'  # Information Exposure Through Log Files
                ))
    
    return findings


# ============================================================================
# CHECK 2: PII in Error Responses
# ============================================================================

def _find_pii_in_error_responses(cursor, pii_vars: Set[str]) -> List[StandardFinding]:
    """Find PII in error responses sent to clients."""
    findings = []
    
    # Error response functions
    error_functions = [
        'Response', 'HttpResponse', 'JsonResponse', 'render',
        'make_response', 'jsonify', 'send_error', 'abort',
        'res.send', 'res.json', 'res.status', 'res.render',
        'response.send', 'response.json', 'response.status',
        'ctx.body', 'ctx.response', 'reply.send', 'reply.code'
    ]
    
    for resp_func in error_functions:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
            ORDER BY f.file, f.line
        """, [f'%{resp_func}%'])
        
        for file, line, func, args in cursor.fetchall():
            # Check if in error context (near catch blocks or error handlers)
            cursor.execute("""
                SELECT 1 FROM symbols s
                WHERE s.path = ?
                  AND (s.type = 'catch' OR s.name LIKE '%error%' OR s.name LIKE '%exception%')
                  AND ABS(s.line - ?) <= 10
                LIMIT 1
            """, [file, line])
            
            if cursor.fetchone():  # In error context
                # Check for PII in arguments
                pii_found = []
                for var in pii_vars:
                    if var in args:
                        pii_found.append(var)
                
                if pii_found:
                    findings.append(StandardFinding(
                        rule_name='pii-error-response',
                        message=f'PII in error response: {", ".join(set(pii_found))}',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='privacy',
                        snippet=f'{func}({{error: {pii_found[0]}}})',
                        fix_suggestion='Sanitize error messages before sending to client',
                        cwe_id='CWE-209'  # Information Exposure Through Error Messages
                    ))
    
    return findings


# ============================================================================
# CHECK 3: PII in URLs
# ============================================================================

def _find_pii_in_urls(cursor, pii_vars: Set[str]) -> List[StandardFinding]:
    """Find PII being included in URLs/query parameters."""
    findings = []
    
    # URL construction functions
    url_functions = [
        'urlencode', 'urllib.parse.urlencode', 'build_url', 'make_url',
        'encodeURIComponent', 'encodeURI', 'URLSearchParams'
    ]
    
    for url_func in url_functions:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
            ORDER BY f.file, f.line
        """, [f'%{url_func}%'])
        
        for file, line, func, args in cursor.fetchall():
            # Check for PII in arguments
            pii_found = []
            for var in pii_vars:
                if var in args:
                    pii_found.append(var)
            
            # Check for PII patterns in string concatenation
            for pattern in ['password', 'ssn', 'credit_card', 'token', 'api_key']:
                if pattern in args.lower():
                    pii_found.append(pattern)
            
            if pii_found:
                findings.append(StandardFinding(
                    rule_name='pii-in-url',
                    message=f'PII in URL parameters: {", ".join(set(pii_found))}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='privacy',
                    snippet=f'{func}({pii_found[0]}=...)',
                    fix_suggestion='Never include sensitive data in URLs - use POST body instead',
                    cwe_id='CWE-598'  # Information Exposure Through Query Strings
                ))
    
    # Also check for string concatenation patterns building URLs
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%url%' OR a.target_var LIKE '%uri%' OR a.target_var LIKE '%link%')
          AND a.source_expr LIKE '%?%'
          AND a.source_expr LIKE '%=%'
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, expr in cursor.fetchall():
        for pii_var in pii_vars:
            if pii_var in expr:
                findings.append(StandardFinding(
                    rule_name='pii-url-concat',
                    message=f'PII variable {pii_var} concatenated into URL',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='privacy',
                    snippet=f'{var} = "...?{pii_var}=..."',
                    fix_suggestion='Use POST requests for sensitive data',
                    cwe_id='CWE-598'
                ))
    
    return findings


# ============================================================================
# CHECK 4: Unencrypted PII Storage
# ============================================================================

def _find_unencrypted_pii_storage(cursor, pii_vars: Set[str]) -> List[StandardFinding]:
    """Find PII being stored without encryption."""
    findings = []
    
    # Database storage functions
    storage_functions = [
        'execute', 'executemany', 'insert', 'update', 'save', 'create',
        'bulk_create', 'bulk_update', 'bulk_insert',
        'findOneAndUpdate', 'updateOne', 'updateMany', 
        'insertOne', 'insertMany', 'replaceOne'
    ]
    
    for store_func in storage_functions:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
            ORDER BY f.file, f.line
        """, [f'%{store_func}%'])
        
        for file, line, func, args in cursor.fetchall():
            # Check for sensitive PII fields
            sensitive_pii = []
            for pattern in ['password', 'ssn', 'social_security', 'credit_card', 
                          'bank_account', 'tax_id', 'passport', 'medical_record']:
                if pattern in args.lower():
                    sensitive_pii.append(pattern)
            
            # Check for PII variables
            for var in pii_vars:
                if var in args and any(p in var.lower() for p in ['password', 'ssn', 'credit']):
                    sensitive_pii.append(var)
            
            if sensitive_pii:
                # Check if there's encryption nearby
                cursor.execute("""
                    SELECT 1 FROM function_call_args f2
                    WHERE f2.file = ?
                      AND ABS(f2.line - ?) <= 5
                      AND (f2.callee_function LIKE '%encrypt%'
                           OR f2.callee_function LIKE '%hash%'
                           OR f2.callee_function LIKE '%bcrypt%'
                           OR f2.callee_function LIKE '%crypto%')
                    LIMIT 1
                """, [file, line])
                
                if not cursor.fetchone():  # No encryption found
                    findings.append(StandardFinding(
                        rule_name='pii-unencrypted-storage',
                        message=f'Sensitive PII stored without encryption: {", ".join(set(sensitive_pii))}',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='privacy',
                        snippet=f'{func}({{"{sensitive_pii[0]}": ...}})',
                        fix_suggestion='Encrypt sensitive PII before storage',
                        cwe_id='CWE-311'  # Missing Encryption of Sensitive Data
                    ))
    
    return findings


# ============================================================================
# CHECK 5: PII in Exception Handling
# ============================================================================

def _find_pii_in_exceptions(cursor, pii_vars: Set[str]) -> List[StandardFinding]:
    """Find PII exposed in exception handling."""
    findings = []
    
    # Find exception handlers
    cursor.execute("""
        SELECT s.path, s.line, s.name
        FROM symbols s
        WHERE s.type = 'catch'
           OR s.type = 'except'
           OR s.name LIKE '%exception%'
           OR s.name LIKE '%error%'
        ORDER BY s.path, s.line
    """)
    
    for file, line, handler_name in cursor.fetchall():
        # Check for logging or response sending within exception handlers
        cursor.execute("""
            SELECT f.callee_function, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line >= ?
              AND f.line <= ? + 20
              AND (f.callee_function LIKE '%log%'
                   OR f.callee_function LIKE '%print%'
                   OR f.callee_function LIKE '%send%'
                   OR f.callee_function LIKE '%json%'
                   OR f.callee_function LIKE '%render%')
            ORDER BY f.line
        """, [file, line, line])
        
        for func, func_line, args in cursor.fetchall():
            # Check if exception details are being exposed
            if any(exc in args for exc in ['exception', 'error', 'exc', 'err', 'e.message', 'e.stack']):
                findings.append(StandardFinding(
                    rule_name='pii-exception-exposure',
                    message='Exception details may contain PII',
                    file_path=file,
                    line=func_line,
                    severity=Severity.MEDIUM,
                    category='privacy',
                    snippet=f'{func}(exception)',
                    fix_suggestion='Sanitize exception messages before logging/sending',
                    cwe_id='CWE-209'
                ))
    
    return findings


# ============================================================================
# CHECK 6: PII in Client-Side Code
# ============================================================================

def _find_pii_in_client_code(cursor, pii_vars: Set[str]) -> List[StandardFinding]:
    """Find PII being sent to client-side JavaScript."""
    findings = []
    
    # Check for PII in template rendering
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('render', 'render_template', 'render_to_response')
          AND f.file LIKE '%.py'
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        # Check if passing PII variables to templates
        pii_found = []
        for var in pii_vars:
            if var in args:
                pii_found.append(var)
        
        if pii_found:
            findings.append(StandardFinding(
                rule_name='pii-client-exposure',
                message=f'PII sent to client template: {", ".join(set(pii_found))}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='privacy',
                snippet=f'{func}("template.html", {pii_found[0]}=...)',
                fix_suggestion='Minimize PII sent to client-side code',
                cwe_id='CWE-201'  # Information Exposure Through Sent Data
            ))
    
    # Check for PII in localStorage/sessionStorage (JavaScript)
    storage_methods = ['localStorage.setItem', 'sessionStorage.setItem']
    
    for method in storage_methods:
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = ?
               OR f.callee_function LIKE ?
            ORDER BY f.file, f.line
        """, [method, f'%.{method}'])
        
        for file, line, args in cursor.fetchall():
            # Check for PII patterns in storage keys/values
            for pattern in ['password', 'ssn', 'credit_card', 'token']:
                if pattern in args.lower():
                    findings.append(StandardFinding(
                        rule_name='pii-browser-storage',
                        message=f'Sensitive PII stored in browser: {pattern}',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='privacy',
                        snippet=f'{method}("{pattern}", ...)',
                        fix_suggestion='Never store sensitive PII in browser storage',
                        cwe_id='CWE-922'  # Insecure Storage of Sensitive Information
                    ))
    
    return findings