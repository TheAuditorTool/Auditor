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
            SELECT DISTINCT file FROM refs
            WHERE value IN ('vue', 'Vue', '@vue/composition-api', 'vuex', 'vue-router')
            LIMIT 1
        """)
        is_vue = cursor.fetchone() is not None

        if not is_vue:
            # Check for .vue files as fallback
            cursor.execute("""
                SELECT path FROM files
                WHERE ext = '.vue'
                LIMIT 1
            """)
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
        # Check for v-html and similar XSS-prone patterns
        xss_patterns = ['%v-html%', '%:innerHTML%', '%v-bind:innerHTML%',
                       '%:outerHTML%', '%v-bind:outerHTML%']
        conditions = ' OR '.join(['source_expr LIKE ?' for _ in xss_patterns])

        cursor.execute(f"""
            SELECT file, line, source_expr
            FROM assignments
            WHERE {conditions}
            ORDER BY file, line
        """, xss_patterns)

        for file, line, html_content in cursor.fetchall():
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
            SELECT DISTINCT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function = 'eval'
            ORDER BY f.file, f.line
        """)
        # ✅ FIX: Store results before loop to avoid cursor state bug
        eval_usages = cursor.fetchall()

        for file, line, eval_content in eval_usages:
            # Check if this file is a Vue component
            cursor.execute("""
                SELECT 1 FROM refs
                WHERE src = ? AND value IN ('vue', 'Vue')
                LIMIT 1
            """, (file,))
            is_vue_file = cursor.fetchone() is not None

            if not is_vue_file and file.endswith('.vue'):
                is_vue_file = True

            if not is_vue_file:
                # Check for Vue lifecycle hooks
                cursor.execute("""
                    SELECT 1 FROM symbols
                    WHERE path = ?
                      AND name IN ('mounted', 'created', 'methods', 'computed')
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
        # Build query for Vue environment variables with sensitive patterns
        env_prefixes = list(VUE_ENV_PREFIXES)
        sensitive = list(SENSITIVE_PATTERNS)

        # Create conditions for env prefixes and sensitive patterns
        prefix_conditions = ' OR '.join([f"target_var LIKE '{prefix}%'" for prefix in env_prefixes])
        sensitive_conditions = ' OR '.join([f"target_var LIKE '%{pattern}%'" for pattern in sensitive])

        cursor.execute(f"""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE ({prefix_conditions})
              AND ({sensitive_conditions})
              AND source_expr NOT LIKE '%process.env%'
              AND source_expr NOT LIKE '%import.meta.env%'
            ORDER BY file, line
        """)

        for file, line, var_name, value in cursor.fetchall():
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
        cursor.execute("""
            SELECT file, line, source_expr
            FROM assignments
            WHERE source_expr LIKE '%{{{%}}}%'
            ORDER BY file, line
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
                cwe_id='CWE-79'
            ))

        # ========================================================
        # CHECK 5: Dynamic Component Injection
        # ========================================================
        # Look for <component :is="userInput"> patterns
        user_input_sources = ['$route', 'params', 'query', 'user', 'input', 'data']
        conditions = ' OR '.join([f"source_expr LIKE '%{src}%'" for src in user_input_sources])

        cursor.execute(f"""
            SELECT file, line, source_expr
            FROM assignments
            WHERE source_expr LIKE '%<component%:is%'
              AND ({conditions})
            ORDER BY file, line
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
                cwe_id='CWE-470'
            ))

        # ========================================================
        # CHECK 6: Unsafe target="_blank" Links
        # ========================================================
        cursor.execute("""
            SELECT file, line, source_expr
            FROM assignments
            WHERE (source_expr LIKE '%target="_blank"%'
                   OR source_expr LIKE "%target='_blank'%")
              AND source_expr NOT LIKE '%noopener%'
              AND source_expr NOT LIKE '%noreferrer%'
            ORDER BY file, line
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
                cwe_id='CWE-1022'
            ))

        # ========================================================
        # CHECK 7: Direct DOM Manipulation via $refs
        # ========================================================
        # Check for $refs with innerHTML manipulation
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function LIKE '%$refs%'
                   OR f.callee_function LIKE '%this.$refs%')
            ORDER BY f.file, f.line
        """)

        for file, line, func, args in cursor.fetchall():
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
            SELECT DISTINCT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.callee_function IN ({placeholders})
            ORDER BY f.file, f.line
        """, dom_methods)
        # ✅ FIX: Store results before loop to avoid cursor state bug
        dom_manipulations = cursor.fetchall()

        for file, line, dom_method in dom_manipulations:
            # Check if this is a Vue file
            cursor.execute("""
                SELECT 1 FROM symbols
                WHERE path = ?
                  AND name IN ('mounted', 'created', 'methods', 'computed')
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
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN (
                'localStorage.setItem', 'sessionStorage.setItem'
            )
              AND (f.argument_expr LIKE '%token%'
                   OR f.argument_expr LIKE '%password%'
                   OR f.argument_expr LIKE '%secret%'
                   OR f.argument_expr LIKE '%jwt%'
                   OR f.argument_expr LIKE '%key%')
            ORDER BY f.file, f.line
        """)
        # ✅ FIX: Store results before loop to avoid cursor state bug
        storage_operations = cursor.fetchall()

        for file, line, storage_method, data in storage_operations:
            # Check if Vue file
            is_vue_file = file.endswith('.vue')
            if not is_vue_file:
                cursor.execute("""
                    SELECT 1 FROM refs
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