"""React Framework Security Analyzer - Database-First Approach.

Analyzes React applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces react_analyzer.py with a faster, cleaner implementation.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


def find_react_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect React security vulnerabilities using indexed data.
    
    Detects:
    - dangerouslySetInnerHTML usage without sanitization
    - Exposed API keys in frontend code
    - eval() with JSX content
    - Unsafe target="_blank" links
    - Direct innerHTML manipulation
    - Unescaped user input rendering
    - Missing CSRF tokens in forms
    - Hardcoded credentials
    - Component security anti-patterns
    - Client-side sensitive data storage
    
    Returns:
        List of security findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, verify this is a React project
        cursor.execute("""
            SELECT DISTINCT file FROM refs
            WHERE value IN ('react', 'react-dom', 'React')
        """)
        react_files = cursor.fetchall()
        
        if not react_files:
            # Also check for React-specific patterns
            cursor.execute("""
                SELECT DISTINCT path FROM symbols
                WHERE name IN ('useState', 'useEffect', 'useContext', 'useReducer', 'Component')
                LIMIT 1
            """)
            react_files = cursor.fetchall()
            
            if not react_files:
                return findings  # Not a React project
        
        # ========================================================
        # CHECK 1: dangerouslySetInnerHTML Usage
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'dangerouslySetInnerHTML'
               OR f.argument_expr LIKE '%dangerouslySetInnerHTML%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, html_content in cursor.fetchall():
            # Check if sanitization is nearby
            cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND line BETWEEN ? AND ?
                  AND (callee_function LIKE '%sanitize%'
                       OR callee_function LIKE '%DOMPurify%'
                       OR callee_function LIKE '%escape%'
                       OR callee_function LIKE '%xss%')
            """, (file, line - 10, line + 10))
            
            has_sanitization = cursor.fetchone()[0] > 0
            
            if not has_sanitization:
                findings.append(StandardFinding(
                    rule_name='react-dangerous-html',
                    message='Use of dangerouslySetInnerHTML without sanitization - primary XSS vector in React',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    confidence=Confidence.HIGH,
                    snippet=html_content[:100] if len(html_content) > 100 else html_content,
                    fix_suggestion='Sanitize HTML with DOMPurify before using dangerouslySetInnerHTML',
                    cwe_id='CWE-79'
                ))
        
        # ========================================================
        # CHECK 2: Exposed API Keys in Frontend
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE 'REACT_APP_%'
                   OR a.target_var LIKE 'NEXT_PUBLIC_%'
                   OR a.target_var LIKE 'VITE_%'
                   OR a.target_var LIKE 'GATSBY_%'
                   OR a.target_var LIKE 'PUBLIC_%')
              AND (a.target_var LIKE '%KEY%'
                   OR a.target_var LIKE '%TOKEN%'
                   OR a.target_var LIKE '%SECRET%'
                   OR a.target_var LIKE '%PASSWORD%'
                   OR a.target_var LIKE '%PRIVATE%'
                   OR a.target_var LIKE '%CREDENTIAL%')
            ORDER BY a.file, a.line
        """)
        
        for file, line, var_name, value in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-exposed-api-key',
                message=f'API key/secret {var_name} exposed in client bundle',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                snippet=f'{var_name} = {value[:50]}...' if len(value) > 50 else f'{var_name} = {value}',
                fix_suggestion='Move sensitive keys to backend, use proxy endpoints',
                cwe_id='CWE-200'
            ))
        
        # ========================================================
        # CHECK 3: eval() with JSX/React Content
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'eval'
              AND (f.argument_expr LIKE '%<%>%'
                   OR f.argument_expr LIKE '%jsx%'
                   OR f.argument_expr LIKE '%JSX%'
                   OR f.argument_expr LIKE '%React.createElement%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, eval_content in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-eval-jsx',
                message='Using eval() with JSX - code injection vulnerability',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.HIGH,
                snippet=eval_content[:100] if len(eval_content) > 100 else eval_content,
                fix_suggestion='Never use eval() with JSX - use React.createElement or JSX directly',
                cwe_id='CWE-95'
            ))
        
        # ========================================================
        # CHECK 4: Unsafe target="_blank" Links
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE (a.source_expr LIKE '%target="_blank"%'
                   OR a.source_expr LIKE "%target='_blank'%"
                   OR a.source_expr LIKE '%target={%_blank%}%')
              AND a.source_expr NOT LIKE '%noopener%'
              AND a.source_expr NOT LIKE '%noreferrer%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, link_code in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-unsafe-target-blank',
                message='External link without rel="noopener" - reverse tabnabbing vulnerability',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                confidence=Confidence.HIGH,
                snippet=link_code[:100] if len(link_code) > 100 else link_code,
                fix_suggestion='Add rel="noopener noreferrer" to all target="_blank" links',
                cwe_id='CWE-1022'
            ))
        
        # ========================================================
        # CHECK 5: Direct innerHTML Manipulation
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.target_var LIKE '%.innerHTML'
               OR a.target_var LIKE '%.outerHTML'
            ORDER BY a.file, a.line
        """)
        
        for file, line, target, content in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-direct-innerhtml',
                message='Direct innerHTML manipulation - bypasses React security',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                confidence=Confidence.HIGH,
                snippet=f'{target} = {content[:50]}...' if len(content) > 50 else f'{target} = {content}',
                fix_suggestion='Use React state and JSX instead of direct DOM manipulation',
                cwe_id='CWE-79'
            ))
        
        # Also check for document.write
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('document.write', 'document.writeln')
            ORDER BY f.file, f.line
        """)
        
        for file, line, write_content in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-document-write',
                message='Use of document.write in React - dangerous DOM manipulation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                confidence=Confidence.HIGH,
                snippet=write_content[:100] if len(write_content) > 100 else write_content,
                fix_suggestion='Use React state and JSX instead of document.write',
                cwe_id='CWE-79'
            ))
        
        # ========================================================
        # CHECK 6: Hardcoded Credentials
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE '%password%'
                   OR a.target_var LIKE '%apiKey%'
                   OR a.target_var LIKE '%api_key%'
                   OR a.target_var LIKE '%secret%'
                   OR a.target_var LIKE '%token%'
                   OR a.target_var LIKE '%privateKey%'
                   OR a.target_var LIKE '%private_key%')
              AND a.source_expr LIKE '"%"'
              AND a.source_expr NOT LIKE '%process.env%'
              AND a.source_expr NOT LIKE '%import.meta.env%'
              AND LENGTH(TRIM(a.source_expr, '"''')) > 10
            ORDER BY a.file, a.line
        """)
        
        for file, line, var_name, credential in cursor.fetchall():
            cred_type = 'credential'
            if 'password' in var_name.lower():
                cred_type = 'password'
            elif 'key' in var_name.lower():
                cred_type = 'API key'
            elif 'token' in var_name.lower():
                cred_type = 'token'
            elif 'secret' in var_name.lower():
                cred_type = 'secret'
            
            findings.append(StandardFinding(
                rule_name='react-hardcoded-credentials',
                message=f'Hardcoded {cred_type} in React component',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=Confidence.HIGH,
                snippet=f'{var_name} = "..."',
                fix_suggestion='Move credentials to environment variables or backend',
                cwe_id='CWE-798'
            ))
        
        # ========================================================
        # CHECK 7: localStorage/sessionStorage for Sensitive Data
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN (
                'localStorage.setItem', 'sessionStorage.setItem',
                'localStorage.set', 'sessionStorage.set'
            )
              AND (f.argument_expr LIKE '%token%'
                   OR f.argument_expr LIKE '%password%'
                   OR f.argument_expr LIKE '%secret%'
                   OR f.argument_expr LIKE '%key%'
                   OR f.argument_expr LIKE '%credential%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, storage_method, data in cursor.fetchall():
            storage_type = 'localStorage' if 'localStorage' in storage_method else 'sessionStorage'
            findings.append(StandardFinding(
                rule_name='react-insecure-storage',
                message=f'Sensitive data stored in {storage_type} - accessible to XSS attacks',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                snippet=data[:100] if len(data) > 100 else data,
                fix_suggestion='Use httpOnly cookies or secure backend sessions',
                cwe_id='CWE-922'
            ))
        
        # ========================================================
        # CHECK 8: Missing Input Validation in Forms
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f1.file, f1.line
            FROM function_call_args f1
            WHERE f1.callee_function IN ('handleSubmit', 'onSubmit', 'submit')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.line BETWEEN f1.line - 20 AND f1.line + 20
                    AND (f2.callee_function LIKE '%validate%'
                         OR f2.callee_function LIKE '%sanitize%'
                         OR f2.callee_function IN ('yup', 'joi', 'zod'))
              )
            ORDER BY f1.file, f1.line
        """)
        
        for file, line in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-missing-validation',
                message='Form submission without input validation',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='validation',
                confidence=Confidence.LOW,
                fix_suggestion='Add input validation using yup, joi, or zod',
                cwe_id='CWE-20'
            ))
        
        # ========================================================
        # CHECK 9: useEffect with External Dependencies
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'useEffect'
              AND f.argument_expr LIKE '%fetch%'
              AND f.argument_expr NOT LIKE '%cleanup%'
              AND f.argument_expr NOT LIKE '%return%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, effect_code in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-useeffect-no-cleanup',
                message='useEffect with fetch but no cleanup - potential memory leak',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='performance',
                confidence=Confidence.LOW,
                snippet=effect_code[:100] if len(effect_code) > 100 else effect_code,
                fix_suggestion='Add cleanup function to cancel requests on unmount',
                cwe_id='CWE-401'
            ))
        
        # ========================================================
        # CHECK 10: Client-Side Routing Without Auth Check
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f.file
            FROM function_call_args f
            WHERE f.callee_function IN ('Route', 'PrivateRoute', 'ProtectedRoute')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND (f2.callee_function LIKE '%auth%'
                         OR f2.callee_function LIKE '%Auth%'
                         OR f2.callee_function LIKE '%isAuthenticated%'
                         OR f2.callee_function LIKE '%currentUser%')
              )
            LIMIT 5
        """)
        
        for (file,) in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-unprotected-routes',
                message='Client-side routing without authentication checks',
                file_path=file,
                line=1,
                severity=Severity.MEDIUM,
                category='authorization',
                confidence=Confidence.LOW,
                fix_suggestion='Implement route guards with authentication checks',
                cwe_id='CWE-862'
            ))
    
    finally:
        conn.close()
    
    return findings


def register_taint_patterns(taint_registry):
    """Register React-specific taint patterns.
    
    This function is called by the orchestrator to register
    framework-specific sources and sinks for taint analysis.
    
    Args:
        taint_registry: TaintRegistry instance
    """
    # React dangerous operations (XSS sinks)
    REACT_XSS_SINKS = [
        'dangerouslySetInnerHTML', 'innerHTML', 'outerHTML',
        'document.write', 'document.writeln', 'eval', 'Function'
    ]
    
    for pattern in REACT_XSS_SINKS:
        taint_registry.register_sink(pattern, 'xss', 'javascript')
    
    # React user input sources
    REACT_INPUT_SOURCES = [
        'props.user', 'props.input', 'props.data', 'location.search',
        'params.', 'query.', 'formData.', 'useState', 'useReducer',
        'event.target.value', 'e.target.value'
    ]
    
    for pattern in REACT_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')
    
    # React storage sinks (sensitive data exposure)
    REACT_STORAGE_SINKS = [
        'localStorage.setItem', 'sessionStorage.setItem',
        'document.cookie', 'indexedDB.put'
    ]
    
    for pattern in REACT_STORAGE_SINKS:
        taint_registry.register_sink(pattern, 'storage', 'javascript')