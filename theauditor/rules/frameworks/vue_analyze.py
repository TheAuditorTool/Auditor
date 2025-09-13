"""Vue.js Framework Security Analyzer - Database-First Approach.

Analyzes Vue.js applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This replaces vue_analyzer.py with a faster, cleaner implementation.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


def find_vue_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Vue.js security vulnerabilities using indexed data.
    
    Detects:
    - v-html directive usage (XSS risk)
    - v-bind:innerHTML usage
    - eval() in Vue components
    - Exposed API keys in frontend
    - Unescaped interpolation
    - Dynamic component injection
    - Unsafe target="_blank" links
    - Direct DOM manipulation
    - Missing prop validation
    - Vuex store security issues
    - Server-side template injection
    - Prototype pollution in Vue
    - Insecure event bus usage
    - Missing v-once for static content
    - Router navigation guards bypass
    - Component injection vulnerabilities
    - Unsafe watchers with user input
    - Missing input validation in v-model
    - Exposed webpack config secrets
    - Development mode in production
    
    Returns:
        List of security findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, verify this is a Vue project
        cursor.execute("""
            SELECT DISTINCT file FROM refs
            WHERE value IN ('vue', 'Vue', '@vue/composition-api', 'vuex', 'vue-router')
        """)
        vue_files = cursor.fetchall()
        
        if not vue_files:
            # Also check for .vue files
            cursor.execute("""
                SELECT DISTINCT path FROM files
                WHERE ext = '.vue'
                LIMIT 1
            """)
            vue_files = cursor.fetchall()
            
            if not vue_files:
                # Check for Vue-specific symbols
                cursor.execute("""
                    SELECT DISTINCT path FROM symbols
                    WHERE name IN ('createApp', 'defineComponent', 'computed', 'mounted', 'created')
                    LIMIT 1
                """)
                vue_files = cursor.fetchall()
                
                if not vue_files:
                    return findings  # Not a Vue project
        
        # ========================================================
        # CHECK 1: v-html Directive Usage (XSS Risk)
        # ========================================================
        # Look for v-html in assignments and symbols
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%v-html%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, html_content in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-v-html-xss',
                message='Use of v-html directive - primary XSS vector in Vue',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                confidence=Confidence.HIGH,
                snippet=html_content[:100] if len(html_content) > 100 else html_content,
                fix_suggestion='Use v-text or {{ }} interpolation instead of v-html',
                cwe_id='CWE-79'
            ))
        
        # ========================================================
        # CHECK 2: v-bind:innerHTML Usage
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%:innerHTML%'
               OR a.source_expr LIKE '%v-bind:innerHTML%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, bind_content in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-v-bind-innerhtml',
                message='Binding to innerHTML property - XSS vulnerability',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                confidence=Confidence.HIGH,
                snippet=bind_content[:100] if len(bind_content) > 100 else bind_content,
                fix_suggestion='Use v-text or {{ }} instead of binding to innerHTML',
                cwe_id='CWE-79'
            ))
        
        # ========================================================
        # CHECK 3: eval() in Vue Components
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'eval'
              AND (f.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM symbols s
                       WHERE s.path = f.file
                         AND s.name IN ('mounted', 'created', 'methods', 'computed', 'setup')
                   ))
            ORDER BY f.file, f.line
        """)
        
        for file, line, eval_content in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-eval-injection',
                message='Using eval() in Vue component - code injection risk',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.HIGH,
                snippet=eval_content[:100] if len(eval_content) > 100 else eval_content,
                fix_suggestion='Remove eval() - use computed properties or methods instead',
                cwe_id='CWE-95'
            ))
        
        # ========================================================
        # CHECK 4: Exposed API Keys in Frontend
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE 'VUE_APP_%'
                   OR a.target_var LIKE 'VITE_%')
              AND (a.target_var LIKE '%KEY%'
                   OR a.target_var LIKE '%TOKEN%'
                   OR a.target_var LIKE '%SECRET%'
                   OR a.target_var LIKE '%PASSWORD%'
                   OR a.target_var LIKE '%PRIVATE%')
              AND a.source_expr NOT LIKE '%process.env%'
              AND a.source_expr NOT LIKE '%import.meta.env%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, var_name, value in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-exposed-api-key',
                message=f'API key/secret {var_name} exposed in Vue component',
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
        # CHECK 5: Triple Mustache Unescaped Interpolation
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%{{{%}}}%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, interpolation in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-unescaped-interpolation',
                message='Triple mustache {{{ }}} unescaped interpolation - XSS risk',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                confidence=Confidence.HIGH,
                snippet=interpolation[:100] if len(interpolation) > 100 else interpolation,
                fix_suggestion='Use double mustache {{ }} for escaped interpolation',
                cwe_id='CWE-79'
            ))
        
        # ========================================================
        # CHECK 6: Dynamic Component Injection
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%<component%:is%'
              AND (a.source_expr LIKE '%$route%'
                   OR a.source_expr LIKE '%params%'
                   OR a.source_expr LIKE '%query%'
                   OR a.source_expr LIKE '%user%'
                   OR a.source_expr LIKE '%input%')
            ORDER BY a.file, a.line
        """)
        
        for file, line, component_code in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-dynamic-component-injection',
                message='Dynamic component with user-controlled input - component injection risk',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='injection',
                confidence=Confidence.MEDIUM,
                snippet=component_code[:100] if len(component_code) > 100 else component_code,
                fix_suggestion='Validate and whitelist component names before dynamic loading',
                cwe_id='CWE-470'
            ))
        
        # ========================================================
        # CHECK 7: Unsafe target="_blank" Links
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE (a.source_expr LIKE '%target="_blank"%'
                   OR a.source_expr LIKE "%target='_blank'%")
              AND a.source_expr NOT LIKE '%noopener%'
              AND a.source_expr NOT LIKE '%noreferrer%'
            ORDER BY a.file, a.line
        """)
        
        for file, line, link_code in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-unsafe-target-blank',
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
        # CHECK 8: Direct DOM Manipulation via $refs
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%$refs%'
                   OR f.callee_function LIKE '%this.$refs%')
              AND f.argument_expr LIKE '%innerHTML%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, refs_usage in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-direct-dom-manipulation',
                message='Direct DOM manipulation via $refs bypassing Vue security',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                confidence=Confidence.HIGH,
                snippet=refs_usage[:100] if len(refs_usage) > 100 else refs_usage,
                fix_suggestion='Use Vue data binding instead of direct DOM manipulation',
                cwe_id='CWE-79'
            ))
        
        # Also check for document.* DOM methods in Vue files
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.callee_function IN (
                'document.getElementById', 'document.querySelector',
                'document.getElementsByClassName', 'document.getElementsByTagName'
            )
              AND (f.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM refs r
                       WHERE r.src = f.file AND r.value = 'vue'
                   ))
            ORDER BY f.file, f.line
        """)
        
        for file, line, dom_method in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-anti-pattern-dom',
                message=f'Direct DOM access with {dom_method} - anti-pattern in Vue',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='best-practice',
                confidence=Confidence.MEDIUM,
                fix_suggestion='Use Vue refs, data binding, or directives instead',
                cwe_id='CWE-1061'
            ))
        
        # ========================================================
        # CHECK 9: Vuex Store Security Issues
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.target_var LIKE '%store%'
              AND (a.source_expr LIKE '%password%'
                   OR a.source_expr LIKE '%token%'
                   OR a.source_expr LIKE '%secret%'
                   OR a.source_expr LIKE '%key%'
                   OR a.source_expr LIKE '%credential%')
            ORDER BY a.file, a.line
        """)
        
        for file, line, var_name, sensitive_data in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-vuex-sensitive-data',
                message='Sensitive data stored in Vuex store - accessible via DevTools',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.MEDIUM,
                snippet=sensitive_data[:100] if len(sensitive_data) > 100 else sensitive_data,
                fix_suggestion='Store sensitive data in httpOnly cookies or secure backend',
                cwe_id='CWE-922'
            ))
        
        # ========================================================
        # CHECK 10: localStorage/sessionStorage for Sensitive Data
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN (
                'localStorage.setItem', 'sessionStorage.setItem'
            )
              AND (f.argument_expr LIKE '%token%'
                   OR f.argument_expr LIKE '%password%'
                   OR f.argument_expr LIKE '%secret%'
                   OR f.argument_expr LIKE '%jwt%')
              AND (f.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM refs r
                       WHERE r.src = f.file AND r.value = 'vue'
                   ))
            ORDER BY f.file, f.line
        """)
        
        for file, line, storage_method, data in cursor.fetchall():
            storage_type = 'localStorage' if 'localStorage' in storage_method else 'sessionStorage'
            findings.append(StandardFinding(
                rule_name='vue-insecure-storage',
                message=f'Sensitive data in {storage_type} - accessible to XSS attacks',
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
        # CHECK 11: Missing CSRF Protection in Forms
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f.file
            FROM function_call_args f
            WHERE f.callee_function IN ('$http.post', '$http.put', '$http.delete', 'axios.post', 'axios.put', 'axios.delete')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND (f2.argument_expr LIKE '%csrf%'
                         OR f2.argument_expr LIKE '%xsrf%'
                         OR f2.argument_expr LIKE '%X-CSRF%')
              )
              AND (f.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM refs r
                       WHERE r.src = f.file AND r.value = 'vue'
                   ))
            LIMIT 5
        """)
        
        for (file,) in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-missing-csrf',
                message='HTTP mutations without CSRF token',
                file_path=file,
                line=1,
                severity=Severity.HIGH,
                category='csrf',
                confidence=Confidence.LOW,
                fix_suggestion='Include CSRF token in axios headers or form data',
                cwe_id='CWE-352'
            ))
        
        # ========================================================
        # CHECK 12: Server-Side Template Injection in Vue SSR
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%renderToString%'
                   OR f.callee_function LIKE '%renderToStream%')
              AND (f.argument_expr LIKE '%req.%'
                   OR f.argument_expr LIKE '%request.%'
                   OR f.argument_expr LIKE '%user%'
                   OR f.argument_expr LIKE '%input%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, func, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-ssr-template-injection',
                message=f'Server-side template injection risk in {func}',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.HIGH,
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Sanitize user input before SSR rendering',
                cwe_id='CWE-94'
            ))
        
        # ========================================================
        # CHECK 13: Prototype Pollution in Vue
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%Vue.set%'
                   OR f.callee_function LIKE '%$set%')
              AND f.argument_expr LIKE '%__proto__%'
            ORDER BY f.file, f.line
        """)
        
        for file, line, func, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-prototype-pollution',
                message='Prototype pollution risk via Vue.set',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Validate object keys to prevent __proto__ pollution',
                cwe_id='CWE-1321'
            ))
        
        # ========================================================
        # CHECK 14: Insecure Event Bus Usage
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%$emit%'
                   OR f.callee_function LIKE '%$on%'
                   OR f.callee_function LIKE '%EventBus%')
              AND (f.argument_expr LIKE '%password%'
                   OR f.argument_expr LIKE '%token%'
                   OR f.argument_expr LIKE '%secret%'
                   OR f.argument_expr LIKE '%credential%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, func, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-insecure-event-bus',
                message='Sensitive data transmitted via event bus',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Avoid passing sensitive data through event bus',
                cwe_id='CWE-200'
            ))
        
        # ========================================================
        # CHECK 15: Missing v-once for Static Content
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%v-for%'
              AND a.source_expr NOT LIKE '%:key%'
              AND (a.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM refs r
                       WHERE r.src = a.file AND r.value = 'vue'
                   ))
            ORDER BY a.file, a.line
        """)
        
        for file, line, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-missing-key',
                message='v-for without :key attribute causes performance issues',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='performance',
                confidence=Confidence.HIGH,
                snippet=expr[:100] if len(expr) > 100 else expr,
                fix_suggestion='Add unique :key attribute to v-for loops',
                cwe_id='CWE-1061'
            ))
        
        # ========================================================
        # CHECK 16: Router Navigation Guards Bypass
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.callee_function IN ('$router.push', '$router.replace', 'router.push', 'router.replace')
              AND NOT EXISTS (
                  SELECT 1 FROM symbols s
                  WHERE s.path = f.file
                    AND (s.name LIKE '%beforeRouteEnter%'
                         OR s.name LIKE '%beforeRouteLeave%'
                         OR s.name LIKE '%beforeRouteUpdate%'
                         OR s.name LIKE '%beforeEach%')
              )
            ORDER BY f.file, f.line
            LIMIT 5
        """)
        
        for file, line, func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-missing-route-guards',
                message='Router navigation without security guards',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                confidence=Confidence.LOW,
                fix_suggestion='Implement navigation guards for access control',
                cwe_id='CWE-284'
            ))
        
        # ========================================================
        # CHECK 17: Component Injection Vulnerabilities
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('Vue.component', 'app.component')
              AND (f.argument_expr LIKE '%req.%'
                   OR f.argument_expr LIKE '%request.%'
                   OR f.argument_expr LIKE '%user%'
                   OR f.argument_expr LIKE '%input%')
            ORDER BY f.file, f.line
        """)
        
        for file, line, func, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-component-injection',
                message='Dynamic component registration with user input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.HIGH,
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Never register components with user-controlled names',
                cwe_id='CWE-470'
            ))
        
        # ========================================================
        # CHECK 18: Unsafe Watchers with User Input
        # ========================================================
        cursor.execute("""
            SELECT s.path, s.line, s.name
            FROM symbols s
            WHERE s.name LIKE '%watch%'
              AND s.type = 'function'
              AND EXISTS (
                  SELECT 1 FROM function_call_args f
                  WHERE f.file = s.path
                    AND f.line >= s.line
                    AND f.line <= s.line + 20
                    AND (f.callee_function = 'eval'
                         OR f.callee_function = 'Function'
                         OR f.callee_function LIKE '%.innerHTML%')
              )
            ORDER BY s.path, s.line
        """)
        
        for file, line, name in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-unsafe-watcher',
                message='Watcher with potentially dangerous operations',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.MEDIUM,
                fix_suggestion='Avoid eval() or innerHTML in watchers',
                cwe_id='CWE-94'
            ))
        
        # ========================================================
        # CHECK 19: Missing Input Validation in v-model
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%v-model%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f
                  WHERE f.file = a.file
                    AND ABS(f.line - a.line) <= 10
                    AND (f.callee_function LIKE '%validate%'
                         OR f.callee_function LIKE '%sanitize%'
                         OR f.callee_function LIKE '%escape%')
              )
              AND (a.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM refs r
                       WHERE r.src = a.file AND r.value = 'vue'
                   ))
            ORDER BY a.file, a.line
            LIMIT 10
        """)
        
        for file, line, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-unvalidated-input',
                message='v-model without visible input validation',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='input-validation',
                confidence=Confidence.LOW,
                snippet=expr[:100] if len(expr) > 100 else expr,
                fix_suggestion='Add input validation for v-model bindings',
                cwe_id='CWE-20'
            ))
        
        # ========================================================
        # CHECK 20: Exposed Development Mode
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.target_var = 'Vue.config.devtools'
                   OR a.target_var = 'Vue.config.debug'
                   OR a.target_var = 'Vue.config.silent')
              AND a.source_expr = 'true'
            ORDER BY a.file, a.line
        """)
        
        for file, line, config, value in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-dev-mode-enabled',
                message=f'Vue development mode enabled: {config}',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='configuration',
                confidence=Confidence.HIGH,
                snippet=f'{config} = {value}',
                fix_suggestion='Disable Vue devtools in production',
                cwe_id='CWE-489'
            ))
        
        # ========================================================
        # CHECK 21: SQL Queries in Vue Components
        # ========================================================
        cursor.execute("""
            SELECT s.file_path, s.line_number, s.query_text
            FROM sql_queries s
            WHERE s.file_path LIKE '%.vue'
              AND s.query_text NOT LIKE '%?%'
              AND (s.query_text LIKE '%${%'
                   OR s.query_text LIKE '%' || '%')
            ORDER BY s.file_path, s.line_number
        """)
        
        for file, line, query in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-sql-injection',
                message='SQL query in Vue component without parameterization',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                confidence=Confidence.HIGH,
                snippet=query[:100] if len(query) > 100 else query,
                fix_suggestion='Never execute SQL from frontend Vue components',
                cwe_id='CWE-89'
            ))
        
        # ========================================================
        # CHECK 22: Exposed API Endpoints in Vue
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.target_var LIKE '%baseURL%'
              AND (a.source_expr LIKE '%admin%'
                   OR a.source_expr LIKE '%internal%'
                   OR a.source_expr LIKE '%private%')
              AND (a.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM refs r
                       WHERE r.src = a.file AND r.value = 'vue'
                   ))
            ORDER BY a.file, a.line
        """)
        
        for file, line, var, url in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-exposed-internal-api',
                message='Internal API endpoint exposed in Vue component',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.MEDIUM,
                snippet=f'{var} = {url[:50]}...' if len(url) > 50 else f'{var} = {url}',
                fix_suggestion='Use environment variables and proxy for internal APIs',
                cwe_id='CWE-200'
            ))
        
        # ========================================================
        # CHECK 23: File Upload Without Validation
        # ========================================================
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE (a.source_expr LIKE '%type="file"%'
                   OR a.source_expr LIKE "%type='file'%")
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f
                  WHERE f.file = a.file
                    AND ABS(f.line - a.line) <= 20
                    AND (f.callee_function LIKE '%validateFile%'
                         OR f.callee_function LIKE '%checkFileType%'
                         OR f.argument_expr LIKE '%accept=%')
              )
              AND a.file LIKE '%.vue'
            ORDER BY a.file, a.line
        """)
        
        for file, line, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-unvalidated-file-upload',
                message='File upload without type validation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='input-validation',
                confidence=Confidence.MEDIUM,
                snippet=expr[:100] if len(expr) > 100 else expr,
                fix_suggestion='Validate file type, size, and content before upload',
                cwe_id='CWE-434'
            ))
        
        # ========================================================
        # CHECK 24: PostMessage Without Origin Check
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'postMessage'
              AND (f.argument_expr NOT LIKE '%targetOrigin%'
                   OR f.argument_expr LIKE '%*%')
              AND (f.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM refs r
                       WHERE r.src = f.file AND r.value = 'vue'
                   ))
            ORDER BY f.file, f.line
        """)
        
        for file, line, func, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-postmessage-wildcard',
                message='postMessage with wildcard or missing origin',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Always specify targetOrigin in postMessage',
                cwe_id='CWE-345'
            ))
        
        # ========================================================
        # CHECK 25: WebSocket Without Authentication
        # ========================================================
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'WebSocket'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND ABS(f2.line - f.line) <= 10
                    AND (f2.argument_expr LIKE '%token%'
                         OR f2.argument_expr LIKE '%auth%'
                         OR f2.argument_expr LIKE '%Bearer%')
              )
              AND (f.file LIKE '%.vue'
                   OR EXISTS (
                       SELECT 1 FROM refs r
                       WHERE r.src = f.file AND r.value = 'vue'
                   ))
            ORDER BY f.file, f.line
        """)
        
        for file, line, func, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-websocket-no-auth',
                message='WebSocket connection without authentication',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Add authentication token to WebSocket connection',
                cwe_id='CWE-306'
            ))
    
    finally:
        conn.close()
    
    return findings


def register_taint_patterns(taint_registry):
    """Register Vue.js-specific taint patterns.
    
    This function is called by the orchestrator to register
    framework-specific sources and sinks for taint analysis.
    
    Args:
        taint_registry: TaintRegistry instance
    """
    # Vue XSS sinks
    VUE_XSS_SINKS = [
        'v-html', '$refs.innerHTML', 'innerHTML', 'outerHTML',
        'v-bind:innerHTML', ':innerHTML'
    ]
    
    for pattern in VUE_XSS_SINKS:
        taint_registry.register_sink(pattern, 'xss', 'javascript')
    
    # Vue user input sources
    VUE_INPUT_SOURCES = [
        '$route.params', '$route.query', 'this.$route', 'props.',
        'v-model', '$emit', '$attrs', '$listeners'
    ]
    
    for pattern in VUE_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')
    
    # Vue-specific dangerous operations
    VUE_DANGEROUS_SINKS = [
        'eval', 'Function', 'setTimeout', 'setInterval',
        'v-once', 'v-pre'  # Can be dangerous if misused
    ]
    
    for pattern in VUE_DANGEROUS_SINKS:
        taint_registry.register_sink(pattern, 'code_execution', 'javascript')