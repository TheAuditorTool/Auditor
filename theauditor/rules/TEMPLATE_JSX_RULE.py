"""RULE TEMPLATE: JSX-Specific Rule (Requires Preserved JSX Pass).

================================================================================
RULE TEMPLATE DOCUMENTATION
================================================================================

⚠️ CRITICAL: FUNCTION NAMING REQUIREMENT
--------------------------------------------------------------------------------
Your rule function MUST start with 'find_' prefix:
  ✅ def find_jsx_injection(context: StandardRuleContext)
  ✅ def find_react_xss(context: StandardRuleContext)
  ❌ def analyze(context: StandardRuleContext)  # WRONG - Won't be discovered!
  ❌ def detect_xss(context: StandardRuleContext)  # WRONG - Must start with find_

The orchestrator ONLY discovers functions starting with 'find_'. Any other
name will be silently ignored and your rule will never run.
--------------------------------------------------------------------------------

⚠️ CRITICAL: StandardFinding PARAMETER NAMES
--------------------------------------------------------------------------------
ALWAYS use these EXACT parameter names when creating findings:
  ✅ file_path=     (NOT file=)
  ✅ rule_name=     (NOT rule=)
  ✅ cwe_id=        (NOT cwe=)
  ✅ severity=Severity.CRITICAL (NOT severity='CRITICAL')

Using wrong names will cause RUNTIME CRASHES. See examples at line 297+.
--------------------------------------------------------------------------------

This template is for JSX-SPECIFIC RULES that analyze React/Vue components and
require access to PRESERVED JSX syntax. These rules:

✅ Run on: .jsx, .tsx, .vue files ONLY
✅ Query: JSX-specific tables (symbols_jsx, function_call_args_jsx, etc.)
✅ Use: Preserved JSX data (before transformation to React.createElement)
❌ Skip: Backend .py, .js files (filtered by orchestrator)

WHEN TO USE THIS TEMPLATE:
- JSX element injection patterns (<{UserInput} />)
- JSX attribute injection ({...userProps})
- Component name security (dynamic component rendering)
- JSX-specific XSS patterns (lost in transformation)
- React/Vue component security patterns

WHEN NOT TO USE THIS TEMPLATE:
- React hooks analysis (useState/useEffect) → Use TEMPLATE_STANDARD_RULE.py
  (Hooks work on TRANSFORMED data, available in standard tables)
- Backend SQL injection → Use TEMPLATE_STANDARD_RULE.py
- General XSS (dangerouslySetInnerHTML) → Use TEMPLATE_STANDARD_RULE.py
  (Available in standard tables)

================================================================================
WHY PRESERVED JSX?
================================================================================

JSX transformation loses information:

BEFORE (Preserved JSX):
  const UserProfile = () => <div className={userClass}>{userName}</div>

AFTER (Transformed):
  const UserProfile = () => React.createElement('div', {className: userClass}, userName)

Information LOST in transformation:
- JSX tag syntax (< >)
- Attribute vs children distinction
- Self-closing tag detection
- Spread operator context ({...props})

Information PRESERVED in both:
- Function calls (React.createElement)
- Variable usage (userClass, userName)
- Hook calls (useState, useEffect)

RULE OF THUMB:
- If you need to detect JSX SYNTAX → Use this template (requires_jsx_pass=True)
- If you detect FUNCTION CALLS → Use standard template (requires_jsx_pass=False)

================================================================================
TEMPLATE BASED ON: react_xss_analyze.py (Production Rule)
RULE METADATA: JSX-specific with framework detection
================================================================================
"""

import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="your_jsx_rule_name",
    category="react",
    requires_jsx_pass=True,
    jsx_pass_mode="preserved",
    target_extensions=[".jsx", ".tsx", ".vue"],
    target_file_patterns=["frontend/", "client/", "src/components/", "app/"],
    exclude_patterns=["__tests__/", "*.test.jsx", "*.stories.jsx", "node_modules/"],
)


@dataclass(frozen=True)
class JSXSecurityPatterns:
    """Pattern definitions for JSX security analysis.

    These patterns detect issues specific to JSX syntax that are lost
    when JSX is transformed to React.createElement() calls.
    """

    DANGEROUS_PROPS: frozenset = frozenset(
        ["dangerouslySetInnerHTML", "href", "src", "formAction", "srcdoc"]
    )

    REACT_INPUT_SOURCES: frozenset = frozenset(
        [
            "props.",
            "this.props.",
            "location.search",
            "location.hash",
            "match.params",
            "searchParams.",
            "localStorage.",
            "sessionStorage.",
            "document.cookie",
            "window.name",
            "ref.current.value",
        ]
    )

    SAFE_METHODS: frozenset = frozenset(["React.createElement", "jsx", "jsxs", "jsxDEV"])

    VUE_DANGEROUS_DIRECTIVES: frozenset = frozenset(["v-html", "v-bind:href", "v-bind:src"])


def find_your_jsx_vulnerability(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect JSX-specific security issues using preserved JSX data.

    CRITICAL: This rule queries JSX-SPECIFIC TABLES:
    - symbols_jsx (NOT symbols)
    - assignments_jsx (NOT assignments)
    - function_call_args_jsx (NOT function_call_args)

    Detection Strategy:
    1. Verify this is a React/Vue app (check frameworks table)
    2. Query symbols_jsx for JSX elements with dangerous patterns
    3. Check assignments_jsx for user input flowing to JSX props
    4. Validate against framework safe sinks

    Database Tables Used:
    - symbols_jsx: JSX elements in preserved syntax
    - assignments_jsx: Variable assignments in JSX context
    - function_call_args_jsx: Function calls within JSX
    - react_components: Component metadata
    - frameworks: Framework detection

    Args:
        context: Rule execution context

    Returns:
        List of JSX-specific security findings
    """
    findings = []

    if not context.db_path:
        return findings

    patterns = JSXSecurityPatterns()
    conn = sqlite3.connect(context.db_path)

    try:
        if not _is_react_or_vue_app(conn):
            return findings

        findings.extend(_check_jsx_element_injection(conn, patterns))
        findings.extend(_check_jsx_attribute_injection(conn, patterns))
        findings.extend(_check_dangerous_jsx_props(conn, patterns))

        if _is_vue_app(conn):
            findings.extend(_check_vue_v_html(conn, patterns))

    finally:
        conn.close()

    return findings


def _check_jsx_element_injection(conn, patterns: JSXSecurityPatterns) -> list[StandardFinding]:
    """Detect dynamic JSX element injection: <{UserComponent} />

    This pattern is LOST in transformed AST (becomes createElement call).
    Can only be detected in preserved JSX.
    """
    findings = []
    cursor = conn.cursor()

    cursor.execute("""
        SELECT path, name, line, jsx_mode
        FROM symbols_jsx
        WHERE type = 'JSXElement'
          AND jsx_mode = 'preserved'
          AND name IS NOT NULL
        ORDER BY path, line
    """)

    for file, element_name, line, _jsx_mode in cursor.fetchall():
        if "{" not in element_name:
            continue

        if "{" in element_name and "}" in element_name:
            import re

            var_match = re.search(r"\{(\w+)\}", element_name)
            if not var_match:
                continue

            var_name = var_match.group(1)

            cursor.execute(
                """
                SELECT source_expr
                FROM assignments_jsx
                WHERE file = ?
                  AND target_var = ?
                  AND jsx_mode = 'preserved'
                  AND line < ?
                ORDER BY line DESC
                LIMIT 1
            """,
                [file, var_name, line],
            )

            assignment = cursor.fetchone()
            if not assignment:
                continue

            source_expr = assignment[0]
            has_user_input = any(src in source_expr for src in patterns.REACT_INPUT_SOURCES)

            if has_user_input:
                findings.append(
                    StandardFinding(
                        file_path=file,
                        line=line,
                        rule_name="jsx-element-injection",
                        message=f"Dynamic JSX element from user input: <{{{var_name}}} />",
                        severity=Severity.CRITICAL,
                        category="xss",
                        snippet=f"<{element_name} /> with {var_name} from props",
                        cwe_id="CWE-79",
                    )
                )

    return findings


def _check_jsx_attribute_injection(conn, patterns: JSXSecurityPatterns) -> list[StandardFinding]:
    """Detect JSX spread operator injection: <div {...userProps} />

    Spread operator can inject arbitrary props including dangerous ones.
    """
    findings = []
    cursor = conn.cursor()

    cursor.execute("""
        SELECT path, name, line
        FROM symbols_jsx
        WHERE type = 'JSXElement'
          AND jsx_mode = 'preserved'
          AND name IS NOT NULL
        ORDER BY path, line
    """)

    for file, element_name, line in cursor.fetchall():
        if "..." not in element_name:
            continue

        if "..." in element_name:
            import re

            spread_match = re.search(r"\.\.\.\s*(\w+)", element_name)
            if not spread_match:
                continue

            spread_var = spread_match.group(1)

            has_user_input = any(src in spread_var for src in patterns.REACT_INPUT_SOURCES)

            if has_user_input or spread_var.startswith("props"):
                findings.append(
                    StandardFinding(
                        file_path=file,
                        line=line,
                        rule_name="jsx-spread-injection",
                        message=f"JSX spread operator with user-controlled object: {{...{spread_var}}}",
                        severity=Severity.HIGH,
                        category="xss",
                        snippet=f"<element {{...{spread_var}}} />",
                        cwe_id="CWE-79",
                    )
                )

    return findings


def _check_dangerous_jsx_props(conn, patterns: JSXSecurityPatterns) -> list[StandardFinding]:
    """Check for dangerous props like dangerouslySetInnerHTML with user input."""
    findings = []
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments_jsx
        WHERE jsx_mode = 'preserved'
          AND target_var IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, target, source in cursor.fetchall():
        if "dangerouslySetInnerHTML" not in target and "__html" not in target:
            continue

        has_user_input = any(src in source for src in patterns.REACT_INPUT_SOURCES)

        has_sanitizer = "DOMPurify" in source or "sanitize" in source.lower()

        if has_user_input and not has_sanitizer:
            findings.append(
                StandardFinding(
                    file_path=file,
                    line=line,
                    rule_name="jsx-dangerous-html",
                    message="dangerouslySetInnerHTML with unsanitized user input",
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=source[:80],
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_vue_v_html(conn, patterns: JSXSecurityPatterns) -> list[StandardFinding]:
    """Check Vue v-html directive with user input (Vue-specific)."""
    findings = []
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, line, directive_name, value_expr
        FROM vue_directives
        WHERE directive_name = 'v-html'
        ORDER BY file, line
    """)

    for file, line, _directive, value in cursor.fetchall():
        if not value:
            continue

        has_user_input = any(src in value for src in patterns.REACT_INPUT_SOURCES)

        if has_user_input:
            findings.append(
                StandardFinding(
                    file_path=file,
                    line=line,
                    rule_name="vue-v-html-xss",
                    message="v-html directive with user input",
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=f'v-html="{value[:60]}"',
                    cwe_id="CWE-79",
                )
            )

    return findings


def _is_react_or_vue_app(conn) -> bool:
    """Check if this is a React or Vue application."""
    return _is_react_app(conn) or _is_vue_app(conn)


def _is_react_app(conn) -> bool:
    """Check if this is a React application."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM frameworks
        WHERE name IN ('react', 'React', 'react.js')
          AND language = 'javascript'
    """)

    if cursor.fetchone()[0] > 0:
        return True

    cursor.execute("""
        SELECT COUNT(*) FROM react_components
        LIMIT 1
    """)

    return cursor.fetchone()[0] > 0


def _is_vue_app(conn) -> bool:
    """Check if this is a Vue application."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM frameworks
        WHERE name IN ('vue', 'Vue', 'vue.js')
          AND language = 'javascript'
    """)

    if cursor.fetchone()[0] > 0:
        return True

    cursor.execute("""
        SELECT COUNT(*) FROM vue_components
        LIMIT 1
    """)

    return cursor.fetchone()[0] > 0
