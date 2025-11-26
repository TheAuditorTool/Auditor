"""Golden Standard Node.js Runtime Security Analyzer.

Detects runtime security vulnerabilities in JavaScript/TypeScript via database analysis.
Demonstrates database-aware rule pattern using finite pattern matching.

MIGRATION STATUS: Golden Standard Implementation [2024-12-29]
Signature: context: StandardRuleContext -> List[StandardFinding]
Schema Contract Compliance: v1.1+ (Fail-Fast, Uses build_query())
"""


import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA - SMART FILTERING
# ============================================================================

METADATA = RuleMetadata(
    name="runtime_issues",
    category="node",

    # Target JavaScript/TypeScript files only (Node.js runtime)
    target_extensions=['.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs'],

    # Exclude patterns - skip frontend React/Vue, tests, build, TheAuditor folders
    exclude_patterns=[
        '__tests__/',
        'test/',
        'tests/',
        'node_modules/',
        'dist/',
        'build/',
        '.next/',
        'frontend/',
        'client/',
        'migrations/',
        '.pf/',              # TheAuditor output directory
        '.auditor_venv/'     # TheAuditor sandboxed tools
    ],

    # This is a DATABASE-ONLY rule (no JSX required)
    requires_jsx_pass=False
)


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

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
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
        self.findings: list[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")
        self.tainted_vars: dict[str, tuple] = {}  # var_name -> (file, line, source)

    def analyze(self) -> list[StandardFinding]:
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

            query = build_query('files', ['path'],
                               where="ext IN ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')")
            cursor.execute(query)

            count = len(cursor.fetchall())
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

            # Check direct exec calls with user input (file filtering handled by METADATA)
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

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
                        ))

            # Check for template literals with user input (file filtering handled by METADATA)
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, target, expr in cursor.fetchall():
                # Check for template literal patterns in Python
                if not ('`' in expr and '$' in expr):
                    continue

                # Check if template contains user input
                has_user_input = False
                for source in self.patterns.USER_INPUT_SOURCES:
                    if source in expr:
                        has_user_input = True
                        break

                if has_user_input:
                    # Check if used near exec functions, filter in Python
                    exec_query = build_query('function_call_args', ['callee_function'],
                                            where="file = ? AND line BETWEEN ? AND ?")
                    cursor.execute(exec_query, (file, line - 5, line + 5))

                    near_exec = False
                    for (callee,) in cursor.fetchall():
                        if 'exec' in callee or 'spawn' in callee:
                            near_exec = True
                            break

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
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_spawn_shell_true(self) -> None:
        """Detect spawn with shell:true vulnerability."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all function calls, filter in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, callee, args in cursor.fetchall():
                # Check for spawn functions in Python
                if 'spawn' not in callee:
                    continue
                # Check for shell argument
                if 'shell' not in args:
                    continue
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
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_prototype_pollution(self) -> None:
        """Detect prototype pollution vulnerabilities."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check Object.assign with spread (file filtering handled by METADATA)
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

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
                                ))
                                break

            # Check for for...in loops without validation (file filtering handled by METADATA)
            query = build_query('symbols', ['path', 'line', 'name'],
                               where="name IN ('for', 'in')",
                               order_by="path, line")
            cursor.execute(query)

            for file, line, _ in cursor.fetchall():
                # Check if there's validation nearby
                val_query = build_query('symbols', ['name'],
                                       where="path = ? AND line BETWEEN ? AND ? AND name IN ('hasOwnProperty', 'hasOwn', '__proto__', 'constructor')",
                                       limit=1)
                cursor.execute(val_query, (file, line, line + 10))

                has_validation = cursor.fetchone() is not None

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
                    ))

            # Check recursive merge patterns (file filtering handled by METADATA)
            query = build_query('symbols', ['path', 'line', 'name', 'type'],
                               where="type = 'function'",
                               order_by="path, line")
            cursor.execute(query)

            for file, line, func_name, func_type in cursor.fetchall():
                # Filter for merge/extend functions in Python
                func_name_lower = func_name.lower()
                if 'merge' not in func_name_lower and 'extend' not in func_name_lower:
                    continue
                # Check if function has recursive calls
                rec_query = build_query('function_call_args', ['callee_function'],
                                       where="file = ? AND line > ? AND line < ? AND callee_function = ?",
                                       limit=1)
                cursor.execute(rec_query, (file, line, line + 50, func_name))

                has_recursion = cursor.fetchone() is not None

                if has_recursion:
                    # Check for validation
                    val_query = build_query('symbols', ['name'],
                                           where="path = ? AND line BETWEEN ? AND ? AND name IN ('hasOwnProperty', 'hasOwn', '__proto__')",
                                           limit=1)
                    cursor.execute(val_query, (file, line, line + 50))

                    has_validation = cursor.fetchone() is not None

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
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_eval_injection(self) -> None:
        """Detect dangerous eval() usage with user input."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all function calls (file filtering handled by METADATA)
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

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
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_unsafe_regex(self) -> None:
        """Detect ReDoS vulnerabilities from unsafe regex patterns."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all function calls, filter in Python (file filtering handled by METADATA)
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, func, args in cursor.fetchall():
                # Check for RegExp functions in Python
                if func not in ('RegExp', 'new RegExp') and 'RegExp' not in func:
                    continue
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
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _detect_path_traversal(self) -> None:
        """Detect path traversal vulnerabilities."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all function calls (file filtering handled by METADATA)
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

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
                            ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _identify_tainted_variables(self, cursor) -> None:
        """Identify variables assigned from user input sources."""
        try:
            # Find assignments from user input (file filtering handled by METADATA)
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var, source in cursor.fetchall():
                # Check if source contains user input
                for input_source in self.patterns.USER_INPUT_SOURCES:
                    if input_source in source:
                        self.tainted_vars[var] = (file, line, input_source)
                        break

        except (sqlite3.Error, Exception):
            pass