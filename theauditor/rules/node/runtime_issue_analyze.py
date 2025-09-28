"""Golden Standard Node.js Runtime Security Analyzer.

Detects runtime security vulnerabilities in JavaScript/TypeScript via database analysis.
Demonstrates database-aware rule pattern using finite pattern matching.

MIGRATION STATUS: Golden Standard Implementation [2024-12-29]
Signature: context: StandardRuleContext -> List[StandardFinding]
"""

import json
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# PATTERN CONFIGURATION - Finite Pattern Sets
# ============================================================================

@dataclass(frozen=True)
class RuntimePatterns:
    """Configuration for Node.js runtime security patterns."""

    # User input sources that are taint sources
    USER_INPUT_SOURCES = frozenset([
        'req.body', 'req.query', 'req.params', 'req.headers', 'req.cookies',
        'request.body', 'request.query', 'request.params', 'request.headers',
        'process.argv', 'process.env', 'location.search', 'location.hash',
        'window.location', 'document.location', 'URLSearchParams'
    ])

    # Command execution functions
    EXEC_FUNCTIONS = frozenset([
        'exec', 'execSync', 'execFile', 'execFileSync',
        'spawn', 'spawnSync', 'fork', 'execCommand',
        'child_process.exec', 'child_process.spawn'
    ])

    # Object manipulation functions prone to pollution
    MERGE_FUNCTIONS = frozenset([
        'Object.assign', 'merge', 'extend', 'deepMerge',
        'mergeDeep', 'mergeRecursive', '_.merge', '_.extend',
        'lodash.merge', 'jQuery.extend', '$.extend'
    ])

    # Dangerous evaluation functions
    EVAL_FUNCTIONS = frozenset([
        'eval', 'Function', 'setTimeout', 'setInterval',
        'setImmediate', 'execScript', 'scriptElement.text',
        'scriptElement.textContent', 'scriptElement.innerText'
    ])

    # File system operations
    FILE_OPERATIONS = frozenset([
        'readFile', 'readFileSync', 'writeFile', 'writeFileSync',
        'createReadStream', 'createWriteStream', 'open', 'openSync',
        'access', 'accessSync', 'stat', 'statSync', 'unlink', 'unlinkSync',
        'mkdir', 'mkdirSync', 'rmdir', 'rmdirSync', 'readdir', 'readdirSync'
    ])

    # Path manipulation functions (safe)
    PATH_SAFE_FUNCTIONS = frozenset([
        'path.join', 'path.resolve', 'path.normalize',
        'path.basename', 'path.dirname', 'path.relative'
    ])

    # Prototype pollution dangerous keys
    DANGEROUS_KEYS = frozenset([
        '__proto__', 'constructor', 'prototype',
        '__defineGetter__', '__defineSetter__',
        '__lookupGetter__', '__lookupSetter__'
    ])

    # Validation functions for prototype pollution
    VALIDATION_FUNCTIONS = frozenset([
        'hasOwnProperty', 'hasOwn', 'Object.hasOwn',
        'Object.prototype.hasOwnProperty', 'propertyIsEnumerable'
    ])

    # Template literal indicators
    TEMPLATE_INDICATORS = frozenset([
        '${', '`', 'template', 'interpolation'
    ])


# ============================================================================
# MAIN ENTRY POINT (Orchestrator Pattern)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Node.js runtime security issues.

    This is the main entry point called by the orchestrator.

    Args:
        context: Standardized rule context with project metadata

    Returns:
        List of runtime security findings
    """
    analyzer = RuntimeAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# ANALYZER CLASS
# ============================================================================

class RuntimeAnalyzer:
    """Main analyzer for Node.js runtime security issues."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with context."""
        self.context = context
        self.patterns = RuntimePatterns()
        self.findings: List[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")
        self.tainted_vars: Dict[str, tuple] = {}  # var_name -> (file, line, source)

    def analyze(self) -> List[StandardFinding]:
        """Run complete runtime security analysis."""
        if not self._is_javascript_project():
            return self.findings

        # Run all security checks
        self._detect_command_injection()
        self._detect_spawn_shell_true()
        self._detect_prototype_pollution()
        self._detect_eval_injection()
        self._detect_unsafe_regex()
        self._detect_path_traversal()

        return self.findings

    def _is_javascript_project(self) -> bool:
        """Check if this is a JavaScript/TypeScript project."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) FROM files
                WHERE ext IN ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')
            """)

            count = cursor.fetchone()[0]
            conn.close()
            return count > 0

        except (sqlite3.Error, Exception):
            return False

    def _detect_command_injection(self) -> None:
        """Detect command injection vulnerabilities."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # First, identify tainted variables
            self._identify_tainted_variables(cursor)

            # Check direct exec calls with user input
            cursor.execute("""
                SELECT DISTINCT f.file, f.line, f.callee_function, f.argument_expr
                FROM function_call_args f
                WHERE f.file LIKE '%.js' OR f.file LIKE '%.jsx'
                   OR f.file LIKE '%.ts' OR f.file LIKE '%.tsx'
                ORDER BY f.file, f.line
            """)

            for file, line, func, args in cursor.fetchall():
                # Check if it's an exec function
                is_exec = False
                for exec_func in self.patterns.EXEC_FUNCTIONS:
                    if exec_func in func:
                        is_exec = True
                        break

                if is_exec and args:
                    # Check for user input in arguments
                    has_user_input = False
                    found_source = None

                    for source in self.patterns.USER_INPUT_SOURCES:
                        if source in args:
                            has_user_input = True
                            found_source = source
                            break

                    # Check for tainted variables
                    if not has_user_input:
                        for var_name in self.tainted_vars:
                            if var_name in args:
                                has_user_input = True
                                found_source = f"tainted variable '{var_name}'"
                                break

                    if has_user_input:
                        self.findings.append(StandardFinding(
                            rule_name='command-injection-direct',
                            message=f'Command injection: {func} with {found_source}',
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category='runtime-security',
                            confidence=Confidence.HIGH,
                            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                            fix_suggestion='Use parameterized commands or validate/sanitize input'
                        ))

            # Check for template literals with user input
            cursor.execute("""
                SELECT DISTINCT a.file, a.line, a.source_expr
                FROM assignments a
                WHERE a.source_expr LIKE '%`%'
                  AND a.source_expr LIKE '%$%'
                  AND (a.file LIKE '%.js' OR a.file LIKE '%.jsx'
                       OR a.file LIKE '%.ts' OR a.file LIKE '%.tsx')
                ORDER BY a.file, a.line
            """)

            for file, line, expr in cursor.fetchall():
                # Check if template contains user input
                has_user_input = False
                for source in self.patterns.USER_INPUT_SOURCES:
                    if source in expr:
                        has_user_input = True
                        break

                if has_user_input:
                    # Check if used near exec functions
                    cursor.execute("""
                        SELECT COUNT(*) FROM function_call_args
                        WHERE file = ?
                          AND line BETWEEN ? AND ?
                          AND (callee_function LIKE '%exec%'
                               OR callee_function LIKE '%spawn%')
                    """, (file, line - 5, line + 5))

                    near_exec = cursor.fetchone()[0] > 0

                    if near_exec:
                        self.findings.append(StandardFinding(
                            rule_name='command-injection-template',
                            message='Template literal with user input near exec function',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category='runtime-security',
                            confidence=Confidence.MEDIUM,
                            snippet=expr[:80] + '...' if len(expr) > 80 else expr,
                            fix_suggestion='Use parameterized commands instead of template literals'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_spawn_shell_true(self) -> None:
        """Detect spawn with shell:true vulnerability."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Look for spawn calls
            cursor.execute("""
                SELECT f.file, f.line, f.argument_expr
                FROM function_call_args f
                WHERE f.callee_function LIKE '%spawn%'
                  AND f.argument_expr LIKE '%shell%'
                ORDER BY f.file, f.line
            """)

            for file, line, args in cursor.fetchall():
                # Check if shell:true is present
                if 'shell' in args and 'true' in args:
                    # Check for user input
                    has_user_input = False
                    for source in self.patterns.USER_INPUT_SOURCES:
                        if source in args:
                            has_user_input = True
                            break

                    if has_user_input:
                        self.findings.append(StandardFinding(
                            rule_name='spawn-shell-true',
                            message='spawn() with shell:true and user input',
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category='runtime-security',
                            confidence=Confidence.HIGH,
                            snippet='spawn(..., {shell: true})',
                            fix_suggestion='Remove shell:true or validate/sanitize all inputs'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_prototype_pollution(self) -> None:
        """Detect prototype pollution vulnerabilities."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check Object.assign with spread
            cursor.execute("""
                SELECT f.file, f.line, f.callee_function, f.argument_expr
                FROM function_call_args f
                WHERE f.file LIKE '%.js' OR f.file LIKE '%.jsx'
                   OR f.file LIKE '%.ts' OR f.file LIKE '%.tsx'
                ORDER BY f.file, f.line
            """)

            for file, line, func, args in cursor.fetchall():
                # Check if it's a merge function
                is_merge = False
                for merge_func in self.patterns.MERGE_FUNCTIONS:
                    if merge_func in func:
                        is_merge = True
                        break

                if is_merge and args:
                    # Check for spread of user input
                    if '...' in args:
                        for source in self.patterns.USER_INPUT_SOURCES:
                            if source in args:
                                self.findings.append(StandardFinding(
                                    rule_name='prototype-pollution-spread',
                                    message=f'Prototype pollution: {func} with spread of user input',
                                    file_path=file,
                                    line=line,
                                    severity=Severity.HIGH,
                                    category='runtime-security',
                                    confidence=Confidence.HIGH,
                                    snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                                    fix_suggestion='Validate object keys before merging'
                                ))
                                break

            # Check for for...in loops without validation
            cursor.execute("""
                SELECT s.path, s.line, s.name
                FROM symbols s
                WHERE s.name IN ('for', 'in')
                  AND (s.path LIKE '%.js' OR s.path LIKE '%.jsx'
                       OR s.path LIKE '%.ts' OR s.path LIKE '%.tsx')
                ORDER BY s.path, s.line
            """)

            for file, line, _ in cursor.fetchall():
                # Check if there's validation nearby
                cursor.execute("""
                    SELECT COUNT(*) FROM symbols
                    WHERE path = ?
                      AND line BETWEEN ? AND ?
                      AND name IN ('hasOwnProperty', 'hasOwn', '__proto__', 'constructor')
                """, (file, line, line + 10))

                has_validation = cursor.fetchone()[0] > 0

                if not has_validation:
                    self.findings.append(StandardFinding(
                        rule_name='prototype-pollution-forin',
                        message='for...in loop without key validation',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category='runtime-security',
                        confidence=Confidence.LOW,
                        snippet='for...in without hasOwnProperty check',
                        fix_suggestion='Use Object.hasOwn() to validate keys'
                    ))

            # Check recursive merge patterns
            cursor.execute("""
                SELECT s.path, s.line, s.name
                FROM symbols s
                WHERE s.type = 'function'
                  AND (s.name LIKE '%merge%' OR s.name LIKE '%extend%')
                  AND (s.path LIKE '%.js' OR s.path LIKE '%.jsx'
                       OR s.path LIKE '%.ts' OR s.path LIKE '%.tsx')
                ORDER BY s.path, s.line
            """)

            for file, line, func_name in cursor.fetchall():
                # Check if function has recursive calls
                cursor.execute("""
                    SELECT COUNT(*) FROM function_call_args
                    WHERE file = ?
                      AND line > ?
                      AND line < ? + 50
                      AND callee_function = ?
                """, (file, line, line, func_name))

                has_recursion = cursor.fetchone()[0] > 0

                if has_recursion:
                    # Check for validation
                    cursor.execute("""
                        SELECT COUNT(*) FROM symbols
                        WHERE path = ?
                          AND line BETWEEN ? AND ?
                          AND name IN ('hasOwnProperty', 'hasOwn', '__proto__')
                    """, (file, line, line + 50))

                    has_validation = cursor.fetchone()[0] > 0

                    if not has_validation:
                        self.findings.append(StandardFinding(
                            rule_name='prototype-pollution-recursive',
                            message=f'Recursive {func_name} without key validation',
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            category='runtime-security',
                            confidence=Confidence.MEDIUM,
                            snippet=f'function {func_name}(...) with recursion',
                            fix_suggestion='Add key validation to prevent __proto__ pollution'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_eval_injection(self) -> None:
        """Detect dangerous eval() usage with user input."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f.file, f.line, f.callee_function, f.argument_expr
                FROM function_call_args f
                WHERE f.file LIKE '%.js' OR f.file LIKE '%.jsx'
                   OR f.file LIKE '%.ts' OR f.file LIKE '%.tsx'
                ORDER BY f.file, f.line
            """)

            for file, line, func, args in cursor.fetchall():
                # Check if it's an eval function
                is_eval = False
                for eval_func in self.patterns.EVAL_FUNCTIONS:
                    if eval_func in func:
                        is_eval = True
                        break

                if is_eval and args:
                    # Check for user input
                    has_user_input = False
                    found_source = None

                    for source in self.patterns.USER_INPUT_SOURCES:
                        if source in args:
                            has_user_input = True
                            found_source = source
                            break

                    # Also check for generic suspicious patterns
                    if not has_user_input:
                        suspicious = ['input', 'data', 'user', 'param', 'query']
                        for pattern in suspicious:
                            if pattern in args.lower():
                                has_user_input = True
                                found_source = pattern
                                break

                    if has_user_input:
                        self.findings.append(StandardFinding(
                            rule_name='eval-injection',
                            message=f'Code injection: {func} with {found_source}',
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category='runtime-security',
                            confidence=Confidence.HIGH if found_source in str(self.patterns.USER_INPUT_SOURCES) else Confidence.MEDIUM,
                            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                            fix_suggestion='Never use eval() or Function() with user input'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_unsafe_regex(self) -> None:
        """Detect ReDoS vulnerabilities from unsafe regex patterns."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Look for RegExp constructor with user input
            cursor.execute("""
                SELECT f.file, f.line, f.callee_function, f.argument_expr
                FROM function_call_args f
                WHERE (f.callee_function = 'RegExp'
                       OR f.callee_function = 'new RegExp'
                       OR f.callee_function LIKE '%RegExp%')
                  AND (f.file LIKE '%.js' OR f.file LIKE '%.jsx'
                       OR f.file LIKE '%.ts' OR f.file LIKE '%.tsx')
                ORDER BY f.file, f.line
            """)

            for file, line, func, args in cursor.fetchall():
                if args:
                    # Check for user input
                    has_user_input = False
                    for source in self.patterns.USER_INPUT_SOURCES:
                        if source in args:
                            has_user_input = True
                            break

                    # Check for variable names suggesting user input
                    if not has_user_input:
                        suspicious = ['input', 'user', 'search', 'pattern', 'query']
                        for pattern in suspicious:
                            if pattern in args.lower():
                                has_user_input = True
                                break

                    if has_user_input:
                        self.findings.append(StandardFinding(
                            rule_name='unsafe-regex',
                            message='ReDoS: RegExp constructed from user input',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category='runtime-security',
                            confidence=Confidence.MEDIUM,
                            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                            fix_suggestion='Use pre-defined regex patterns or validate input'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_path_traversal(self) -> None:
        """Detect path traversal vulnerabilities."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f.file, f.line, f.callee_function, f.argument_expr
                FROM function_call_args f
                WHERE f.file LIKE '%.js' OR f.file LIKE '%.jsx'
                   OR f.file LIKE '%.ts' OR f.file LIKE '%.tsx'
                ORDER BY f.file, f.line
            """)

            for file, line, func, args in cursor.fetchall():
                # Check if it's a file operation
                is_file_op = False
                for file_op in self.patterns.FILE_OPERATIONS:
                    if file_op in func:
                        is_file_op = True
                        break

                if is_file_op and args:
                    # Check for user input
                    has_user_input = False
                    for source in self.patterns.USER_INPUT_SOURCES:
                        if source in args:
                            has_user_input = True
                            break

                    if has_user_input:
                        # Check if path is properly sanitized
                        has_sanitization = False
                        for safe_func in self.patterns.PATH_SAFE_FUNCTIONS:
                            if safe_func in args:
                                has_sanitization = True
                                break

                        if not has_sanitization:
                            self.findings.append(StandardFinding(
                                rule_name='path-traversal',
                                message=f'Path traversal: {func} with user input',
                                file_path=file,
                                line=line,
                                severity=Severity.HIGH,
                                category='runtime-security',
                                confidence=Confidence.HIGH,
                                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                                fix_suggestion='Use path.join() or path.resolve() to normalize paths'
                            ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _identify_tainted_variables(self, cursor) -> None:
        """Identify variables assigned from user input sources."""
        try:
            # Find assignments from user input
            cursor.execute("""
                SELECT DISTINCT file, line, target_var, source_expr
                FROM assignments
                WHERE file LIKE '%.js' OR file LIKE '%.jsx'
                   OR file LIKE '%.ts' OR file LIKE '%.tsx'
                ORDER BY file, line
            """)

            for file, line, var, source in cursor.fetchall():
                # Check if source contains user input
                for input_source in self.patterns.USER_INPUT_SOURCES:
                    if input_source in source:
                        self.tainted_vars[var] = (file, line, input_source)
                        break

        except (sqlite3.Error, Exception):
            pass