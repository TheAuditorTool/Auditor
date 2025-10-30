"""Vue.js Framework Security Analyzer - Database-First Approach.

Analyzes Vue.js applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# METADATA (Orchestrator Discovery)
# ============================================================================

METADATA = RuleMetadata(
    name="vue_security",
    category="frameworks",
    target_extensions=['.vue', '.js', '.ts'],
    exclude_patterns=['node_modules/', 'test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)


# ============================================================================
# SECURITY PATTERNS (Golden Standard: Use Frozensets)
# ============================================================================

# Vue XSS-prone directives
VUE_XSS_DIRECTIVES = frozenset([
    'v-html', ':innerHTML', 'v-bind:innerHTML',
    'v-bind:outerHTML', ':outerHTML'
])

# Sensitive data patterns
SENSITIVE_PATTERNS = frozenset([
    'KEY', 'TOKEN', 'SECRET', 'PASSWORD',
    'PRIVATE', 'API_KEY', 'CREDENTIAL', 'AUTH'
])

# Vue environment prefixes
VUE_ENV_PREFIXES = frozenset([
    'VUE_APP_', 'VITE_', 'NUXT_ENV_'
])

# Vue lifecycle hooks and component markers
VUE_COMPONENT_MARKERS = frozenset([
    'mounted', 'created', 'beforeCreate', 'beforeMount',
    'updated', 'beforeUpdate', 'destroyed', 'beforeDestroy',
    'activated', 'deactivated', 'errorCaptured', 'setup',
    'data', 'methods', 'computed', 'watch', 'props',
    'defineComponent', 'createApp'
])

# Dangerous operations
DANGEROUS_FUNCTIONS = frozenset([
    'eval', 'Function', 'setTimeout', 'setInterval',
    'document.write', 'document.writeln'
])

# DOM manipulation methods
DOM_MANIPULATION = frozenset([
    'innerHTML', 'outerHTML', 'insertAdjacentHTML',
    'document.getElementById', 'document.querySelector',
    'document.getElementsByClassName', 'document.getElementsByTagName'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Vue.js security vulnerabilities using indexed data.

    Detects (from database):
    - v-html directive usage (XSS risk)
    - Direct innerHTML manipulation
    - eval() in Vue components
    - Exposed API keys in frontend
    - Triple mustache {{{ }}} unescaped interpolation
    - Dynamic component injection risks
    - Unsafe target="_blank" links
    - Direct DOM manipulation bypassing Vue

    Known Limitations (requires AST/template parsing):
    - Cannot parse .vue SFC template blocks
    - Cannot detect prop validation structure
    - Cannot analyze Vue template syntax deeply
    - Cannot detect computed property side effects

    Args:
        context: Standardized rule context with database path

    Returns:
        List of StandardFinding objects for detected issues
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Verify this is a Vue project - trust schema contract
        cursor.execute("""
            SELECT DISTINCT src FROM refs
            WHERE value IN ('vue', 'Vue', '@vue/composition-api', 'vuex', 'vue-router')
            LIMIT 1
        """)
        is_vue = cursor.fetchone() is not None

        if not is_vue:
            # Check for .vue files as fallback
            query = build_query('files', ['path'],
                               where="ext = '.vue'") + " LIMIT 1"
            cursor.execute(query)
            is_vue = cursor.fetchone() is not None

        if not is_vue:
            # Check for Vue component markers
            vue_markers_list = list(VUE_COMPONENT_MARKERS)
            placeholders = ','.join('?' * len(vue_markers_list))
            cursor.execute(f"""
                SELECT DISTINCT path FROM symbols
                WHERE name IN ({placeholders})
                LIMIT 1
            """, vue_markers_list)
            is_vue = cursor.fetchone() is not None

        if not is_vue:
            return findings  # Not a Vue project

        # ========================================================
        # CHECK 1: v-html and innerHTML Directives (XSS Risk)
        # ========================================================
        # Fetch all assignments, filter in Python
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, target, html_content in cursor.fetchall():
            # Check for v-html and XSS-prone directives in Python
            if not any(pattern in html_content for pattern in VUE_XSS_DIRECTIVES):
                continue
            findings.append(StandardFinding(
                rule_name='vue-v-html-xss',
                message='Use of v-html or innerHTML binding - primary XSS vector in Vue',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                confidence=Confidence.HIGH,
                cwe_id='CWE-79'
            ))

        # ========================================================
        # CHECK 2: eval() in Vue Components
        # ========================================================
        # Check for eval in files that are Vue components
        cursor.execute("""
            SELECT DISTINCT file, line, argument_expr FROM function_call_args
            WHERE callee_function = 'eval'
            ORDER BY file, line
        """)
        # ✅ FIX: Store results before loop to avoid cursor state bug
        eval_usages = cursor.fetchall()

        for file, line, eval_content in eval_usages:
            # Check if this file is a Vue component
            cursor.execute("""
                SELECT src FROM refs
                WHERE src = ? AND value IN ('vue', 'Vue')
                LIMIT 1
            """, (file,))
            is_vue_file = cursor.fetchone() is not None

            if not is_vue_file and file.endswith('.vue'):
                is_vue_file = True

            if not is_vue_file:
                # Check for Vue lifecycle hooks
                cursor.execute("""
                    SELECT path FROM symbols
                    WHERE path = ? AND name IN ('mounted', 'created', 'methods', 'computed')
                    LIMIT 1
                """, (file,))
                is_vue_file = cursor.fetchone() is not None

            if is_vue_file:
                findings.append(StandardFinding(
                    rule_name='vue-eval-injection',
                    message='Using eval() in Vue component - code injection risk',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-95'
                ))

        # ========================================================
        # CHECK 3: Exposed API Keys in Frontend
        # ========================================================
        # Fetch all assignments, filter in Python
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, var_name, value in cursor.fetchall():
            # Check for Vue env prefixes in Python
            if not any(var_name.startswith(prefix) for prefix in VUE_ENV_PREFIXES):
                continue

            # Check for sensitive patterns in Python
            var_upper = var_name.upper()
            if not any(pattern in var_upper for pattern in SENSITIVE_PATTERNS):
                continue

            # Filter out env var references
            if 'process.env' in value or 'import.meta.env' in value:
                continue
            findings.append(StandardFinding(
                rule_name='vue-exposed-api-key',
                message=f'API key/secret {var_name} hardcoded in Vue component',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                confidence=Confidence.HIGH,
                cwe_id='CWE-200'
            ))

        # ========================================================
        # CHECK 4: Triple Mustache Unescaped Interpolation
        # ========================================================
        # Fetch all assignments, filter in Python
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, target, interpolation in cursor.fetchall():
            # Check for triple mustache in Python
            if '{{{' not in interpolation or '}}}' not in interpolation:
                continue
            findings.append(StandardFinding(
                rule_name='vue-unescaped-interpolation',
                message='Triple mustache {{{ }}} unescaped interpolation - XSS risk',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                confidence=Confidence.HIGH,
                cwe_id='CWE-79'
            ))

        # ========================================================
        # CHECK 5: Dynamic Component Injection
        # ========================================================
        # Fetch all assignments, filter in Python
        user_input_sources = ['$route', 'params', 'query', 'user', 'input', 'data']

        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, target, component_code in cursor.fetchall():
            # Check for <component :is pattern in Python
            if '<component' not in component_code or ':is' not in component_code:
                continue

            # Check for user input sources in Python
            if not any(src in component_code for src in user_input_sources):
                continue
            findings.append(StandardFinding(
                rule_name='vue-dynamic-component-injection',
                message='Dynamic component with user-controlled input - component injection risk',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='injection',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-470'
            ))

        # ========================================================
        # CHECK 6: Unsafe target="_blank" Links
        # ========================================================
        # Fetch all assignments, filter in Python
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, target, link_code in cursor.fetchall():
            # Check for target="_blank" in Python
            if not ('target="_blank"' in link_code or "target='_blank'" in link_code):
                continue

            # Check if noopener/noreferrer is missing
            if 'noopener' in link_code or 'noreferrer' in link_code:
                continue
            findings.append(StandardFinding(
                rule_name='vue-unsafe-target-blank',
                message='External link without rel="noopener" - reverse tabnabbing vulnerability',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1022'
            ))

        # ========================================================
        # CHECK 7: Direct DOM Manipulation via $refs
        # ========================================================
        # Fetch all function calls, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func, args in cursor.fetchall():
            # Check for $refs patterns in Python
            if '$refs' not in func and 'this.$refs' not in func:
                continue
            # Check if using innerHTML or other dangerous properties
            if args and any(danger in args for danger in ['innerHTML', 'outerHTML']):
                findings.append(StandardFinding(
                    rule_name='vue-direct-dom-manipulation',
                    message='Direct DOM manipulation via $refs bypassing Vue security',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-79'
                ))

            # Also check for document.* DOM methods in Vue files
        dom_methods = list(DOM_MANIPULATION)
        placeholders = ','.join('?' * len(dom_methods))

        cursor.execute(f"""
            SELECT DISTINCT file, line, callee_function FROM function_call_args
            WHERE callee_function IN ({placeholders})
            ORDER BY file, line
        """, dom_methods)
        # ✅ FIX: Store results before loop to avoid cursor state bug
        dom_manipulations = cursor.fetchall()

        for file, line, dom_method in dom_manipulations:
            # Check if this is a Vue file
            cursor.execute("""
                SELECT path FROM symbols
                WHERE path = ? AND name IN ('mounted', 'created', 'methods', 'computed')
                LIMIT 1
            """, (file,))

            if cursor.fetchone() or file.endswith('.vue'):
                findings.append(StandardFinding(
                    rule_name='vue-anti-pattern-dom',
                    message=f'Direct DOM access with {dom_method} - anti-pattern in Vue',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='best-practice',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1061'
                ))

        # ========================================================
        # CHECK 8: localStorage/sessionStorage for Sensitive Data
        # ========================================================
        # Fetch storage operations, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where="callee_function IN ('localStorage.setItem', 'sessionStorage.setItem')",
                           order_by="file, line")
        cursor.execute(query)

        storage_operations = []
        for file, line, storage_method, data in cursor.fetchall():
            # Check for sensitive data patterns in Python
            data_lower = data.lower()
            if any(sensitive in data_lower for sensitive in ['token', 'password', 'secret', 'jwt', 'key']):
                storage_operations.append((file, line, storage_method, data))

        for file, line, storage_method, data in storage_operations:
            # Check if Vue file
            is_vue_file = file.endswith('.vue')
            if not is_vue_file:
                cursor.execute("""
                    SELECT src FROM refs
                    WHERE src = ? AND value IN ('vue', 'Vue')
                    LIMIT 1
                """, (file,))
                is_vue_file = cursor.fetchone() is not None

            if is_vue_file:
                storage_type = 'localStorage' if 'localStorage' in storage_method else 'sessionStorage'
                findings.append(StandardFinding(
                    rule_name='vue-insecure-storage',
                    message=f'Sensitive data in {storage_type} - accessible to XSS attacks',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-922'
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
    for pattern in VUE_XSS_DIRECTIVES:
        taint_registry.register_sink(pattern, 'xss', 'javascript')

    # Additional Vue-specific sinks
    VUE_ADDITIONAL_SINKS = frozenset([
        '$refs.innerHTML', '$refs.outerHTML',
        'this.$refs', 'vm.$refs'
    ])

    for pattern in VUE_ADDITIONAL_SINKS:
        taint_registry.register_sink(pattern, 'xss', 'javascript')

    # Vue user input sources
    VUE_INPUT_SOURCES = frozenset([
        '$route.params', '$route.query', 'this.$route',
        'props.', 'v-model', '$emit', '$attrs', '$listeners'
    ])

    for pattern in VUE_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')

    # Dangerous operations
    for pattern in DANGEROUS_FUNCTIONS:
        taint_registry.register_sink(pattern, 'code_execution', 'javascript')