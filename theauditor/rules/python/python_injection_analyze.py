"""Python Injection Vulnerability Analyzer - Database-First Approach.

Detects various injection vulnerabilities in Python code using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows golden standard patterns from compose_analyze.py:
- Frozensets for all patterns
- Table existence checks
- Graceful degradation
- Proper confidence levels

Detects:
- SQL Injection
- Command Injection
- Code Injection (eval/exec)
- Template Injection
- LDAP Injection
- NoSQL Injection
- XPath Injection
"""

import sqlite3
from typing import List, Set
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class InjectionPatterns:
    """Immutable pattern definitions for injection detection."""

    # SQL Injection vulnerable methods
    SQL_METHODS = frozenset([
        'execute', 'executemany', 'executescript', 'raw',
        'connection.execute', 'cursor.execute', 'db.execute',
        'query', 'run_query', 'session.execute', 'db.session.execute',
        'select', 'insert', 'update', 'delete', 'create_table'
    ])

    # String formatting that leads to injection
    STRING_FORMAT_PATTERNS = frozenset([
        '.format(', '% (', 'f"', "f'", '%%',
        '+ request.', '+ params.', '+ args.',
        '+ user_input', '+ data[', '+ input('
    ])

    # Command injection vulnerable functions
    COMMAND_METHODS = frozenset([
        'os.system', 'subprocess.call', 'subprocess.run',
        'subprocess.Popen', 'os.popen', 'popen',
        'commands.getstatusoutput', 'commands.getoutput',
        'subprocess.check_output', 'subprocess.check_call',
        'os.exec', 'os.spawn', 'os.startfile'
    ])

    # Shell=True is particularly dangerous
    SHELL_TRUE_PATTERN = frozenset([
        'shell=True', 'shell = True', 'shell= True', 'shell =True'
    ])

    # Code injection vulnerable functions
    CODE_INJECTION = frozenset([
        'eval', 'exec', 'compile', '__import__',
        'execfile', 'input', 'raw_input'  # Python 2
    ])

    # Template injection patterns
    TEMPLATE_PATTERNS = frozenset([
        'render_template_string', 'Environment', 'Template',
        'jinja2.Template', 'django.template.Template',
        'mako.template.Template', 'tornado.template.Template'
    ])

    # LDAP injection patterns
    LDAP_METHODS = frozenset([
        'search', 'search_s', 'search_ext', 'search_ext_s',
        'ldap.search', 'ldap3.search', 'ldap_search',
        'modify', 'modify_s', 'add', 'add_s', 'delete', 'delete_s'
    ])

    # NoSQL injection patterns (MongoDB, etc.)
    NOSQL_METHODS = frozenset([
        'find', 'find_one', 'find_and_modify', 'update_one',
        'update_many', 'delete_one', 'delete_many', 'aggregate',
        'collection.find', 'collection.update', 'collection.delete',
        'db.find', 'db.update', 'db.delete'
    ])

    # XPath injection patterns
    XPATH_METHODS = frozenset([
        'xpath', 'findall', 'find', 'XPath', 'evaluate',
        'selectNodes', 'selectSingleNode', 'query'
    ])

    # User input sources (taint sources)
    USER_INPUTS = frozenset([
        'request.args', 'request.form', 'request.values',
        'request.data', 'request.json', 'request.files',
        'request.GET', 'request.POST', 'request.REQUEST',
        'input()', 'raw_input()', 'sys.argv', 'os.environ',
        'flask.request', 'django.request', 'bottle.request'
    ])

    # Safe parameterization patterns
    SAFE_PATTERNS = frozenset([
        'paramstyle', 'params=', 'parameters=',
        '?', '%s', '%(', ':name',
        'prepared', 'statement', 'placeholder'
    ])

    # Dangerous SQL keywords often in injected strings
    SQL_KEYWORDS = frozenset([
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP',
        'UNION', 'WHERE', 'ORDER BY', 'GROUP BY',
        'CREATE', 'ALTER', 'EXEC', 'EXECUTE',
        '--', '/*', '*/', ';', 'OR 1=1', 'OR true'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class InjectionAnalyzer:
    """Analyzer for Python injection vulnerabilities."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = InjectionPatterns()
        self.findings = []
        self.existing_tables = set()

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of injection vulnerabilities found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Check available tables for graceful degradation
            self._check_table_availability()

            # Must have minimum tables for any analysis
            if not self._has_minimum_tables():
                return []

            # Run injection checks based on available data
            if 'function_call_args' in self.existing_tables:
                self._check_sql_injection()
                self._check_command_injection()
                self._check_code_injection()
                self._check_template_injection()
                self._check_ldap_injection()
                self._check_nosql_injection()
                self._check_xpath_injection()

            if 'sql_queries' in self.existing_tables:
                self._check_raw_sql_construction()

        finally:
            conn.close()

        return self.findings

    def _check_table_availability(self):
        """Check which tables exist for graceful degradation."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'function_call_args', 'assignments', 'sql_queries',
                'symbols', 'refs', 'files', 'api_endpoints'
            )
        """)
        self.existing_tables = {row[0] for row in self.cursor.fetchall()}

    def _has_minimum_tables(self) -> bool:
        """Check if we have minimum required tables."""
        required = {'function_call_args', 'files'}
        return required.issubset(self.existing_tables)

    def _check_sql_injection(self):
        """Detect SQL injection vulnerabilities."""
        sql_placeholders = ','.join('?' * len(self.patterns.SQL_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({sql_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """, list(self.patterns.SQL_METHODS))

        for file, line, method, args in self.cursor.fetchall():
            if not args:
                continue

            # Check for string formatting in SQL
            has_formatting = any(fmt in args for fmt in self.patterns.STRING_FORMAT_PATTERNS)
            has_concatenation = '+' in args and any(inp in args for inp in ['request.', 'params.', 'args.', 'user_'])

            # Check for safe parameterization
            has_safe_params = any(safe in args for safe in self.patterns.SAFE_PATTERNS)

            if (has_formatting or has_concatenation) and not has_safe_params:
                # Determine severity and confidence
                severity = Severity.CRITICAL
                confidence = Confidence.HIGH

                # Check if SQL keywords present (higher confidence)
                has_sql_keywords = any(kw.lower() in args.lower() for kw in self.patterns.SQL_KEYWORDS)
                if not has_sql_keywords:
                    confidence = Confidence.MEDIUM

                self.findings.append(StandardFinding(
                    rule_name='python-sql-injection',
                    message=f'SQL injection in {method} with string formatting',
                    file_path=file,
                    line=line,
                    severity=severity,
                    category='injection',
                    confidence=confidence,
                    cwe_id='CWE-89'
                ))

            # Check for f-strings in SQL
            if 'f"' in args or "f'" in args:
                self.findings.append(StandardFinding(
                    rule_name='python-sql-fstring',
                    message=f'F-string used in SQL query - high injection risk',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-89'
                ))

    def _check_command_injection(self):
        """Detect command injection vulnerabilities."""
        cmd_placeholders = ','.join('?' * len(self.patterns.COMMAND_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({cmd_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """, list(self.patterns.COMMAND_METHODS))

        for file, line, method, args in self.cursor.fetchall():
            if not args:
                continue

            # Check for shell=True
            has_shell_true = any(shell in args for shell in self.patterns.SHELL_TRUE_PATTERN)

            # Check for string concatenation with user input
            has_user_input = any(inp in args for inp in self.patterns.USER_INPUTS)
            has_concatenation = '+' in args or '.format(' in args or 'f"' in args or "f'" in args

            if has_shell_true:
                self.findings.append(StandardFinding(
                    rule_name='python-shell-true',
                    message=f'Command execution with shell=True is dangerous',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-78'
                ))

            elif has_user_input or has_concatenation:
                confidence = Confidence.HIGH if has_user_input else Confidence.MEDIUM

                self.findings.append(StandardFinding(
                    rule_name='python-command-injection',
                    message=f'Command injection risk in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=confidence,
                    cwe_id='CWE-78'
                ))

    def _check_code_injection(self):
        """Detect code injection (eval/exec) vulnerabilities."""
        code_placeholders = ','.join('?' * len(self.patterns.CODE_INJECTION))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({code_placeholders})
            ORDER BY file, line
        """, list(self.patterns.CODE_INJECTION))

        for file, line, method, args in self.cursor.fetchall():
            # eval/exec/compile are always dangerous with user input
            severity = Severity.CRITICAL
            confidence = Confidence.HIGH

            # Check if it's a constant string (slightly less dangerous)
            if args and (args.startswith('"') or args.startswith("'")):
                if not any(inp in args for inp in self.patterns.USER_INPUTS):
                    confidence = Confidence.MEDIUM
                    severity = Severity.HIGH

            self.findings.append(StandardFinding(
                rule_name='python-code-injection',
                message=f'Code injection risk: {method}() with dynamic input',
                file_path=file,
                line=line,
                severity=severity,
                category='injection',
                confidence=confidence,
                cwe_id='CWE-94'
            ))

    def _check_template_injection(self):
        """Detect template injection vulnerabilities."""
        template_placeholders = ','.join('?' * len(self.patterns.TEMPLATE_PATTERNS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({template_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """, list(self.patterns.TEMPLATE_PATTERNS))

        for file, line, method, args in self.cursor.fetchall():
            # Check for user input in template
            has_user_input = any(inp in args for inp in self.patterns.USER_INPUTS)

            if 'render_template_string' in method:
                self.findings.append(StandardFinding(
                    rule_name='python-template-injection',
                    message='render_template_string() is vulnerable to template injection',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-1336'
                ))

            elif has_user_input:
                self.findings.append(StandardFinding(
                    rule_name='python-template-user-input',
                    message=f'User input passed to template {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='injection',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1336'
                ))

    def _check_ldap_injection(self):
        """Detect LDAP injection vulnerabilities."""
        ldap_placeholders = ','.join('?' * len(self.patterns.LDAP_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({ldap_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """, list(self.patterns.LDAP_METHODS))

        for file, line, method, args in self.cursor.fetchall():
            # Check for string formatting in LDAP queries
            has_formatting = any(fmt in args for fmt in self.patterns.STRING_FORMAT_PATTERNS)
            has_user_input = any(inp in args for inp in self.patterns.USER_INPUTS)

            if has_formatting or has_user_input:
                self.findings.append(StandardFinding(
                    rule_name='python-ldap-injection',
                    message=f'LDAP injection risk in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='injection',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-90'
                ))

    def _check_nosql_injection(self):
        """Detect NoSQL injection vulnerabilities."""
        nosql_placeholders = ','.join('?' * len(self.patterns.NOSQL_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({nosql_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """, list(self.patterns.NOSQL_METHODS))

        for file, line, method, args in self.cursor.fetchall():
            # Check for $where, $regex, or JavaScript in MongoDB queries
            dangerous_operators = ['$where', '$regex', '$function', 'function()', 'eval(']
            has_dangerous = any(op in args for op in dangerous_operators)

            # Check for user input
            has_user_input = any(inp in args for inp in self.patterns.USER_INPUTS)

            if has_dangerous:
                self.findings.append(StandardFinding(
                    rule_name='python-nosql-dangerous-operator',
                    message=f'Dangerous NoSQL operator in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-943'
                ))

            elif has_user_input:
                self.findings.append(StandardFinding(
                    rule_name='python-nosql-injection',
                    message=f'NoSQL injection risk in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='injection',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-943'
                ))

    def _check_xpath_injection(self):
        """Detect XPath injection vulnerabilities."""
        xpath_placeholders = ','.join('?' * len(self.patterns.XPATH_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({xpath_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """, list(self.patterns.XPATH_METHODS))

        for file, line, method, args in self.cursor.fetchall():
            # Check for string formatting in XPath
            has_formatting = any(fmt in args for fmt in self.patterns.STRING_FORMAT_PATTERNS)

            if has_formatting:
                self.findings.append(StandardFinding(
                    rule_name='python-xpath-injection',
                    message=f'XPath injection risk in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='injection',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-91'
                ))

    def _check_raw_sql_construction(self):
        """Check for SQL constructed in assignments."""
        if 'assignments' not in self.existing_tables:
            return

        # Look for SQL keyword assignments
        sql_keyword_list = list(self.patterns.SQL_KEYWORDS)
        for keyword in sql_keyword_list[:10]:  # Check top keywords to avoid too many queries
            self.cursor.execute("""
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE source_expr LIKE ?
                  AND (source_expr LIKE '%+%'
                       OR source_expr LIKE '%.format(%'
                       OR source_expr LIKE '%f"%'
                       OR source_expr LIKE "%f'%")
                ORDER BY file, line
            """, [f'%{keyword}%'])

            for file, line, var, expr in self.cursor.fetchall():
                # Check if this looks like SQL construction
                if any(kw in expr.upper() for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
                    self.findings.append(StandardFinding(
                        rule_name='python-sql-string-building',
                        message=f'SQL query built with string concatenation in {var}',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='injection',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-89'
                    ))


# ============================================================================
# MISSING DATABASE FEATURES FLAGGED
# ============================================================================

"""
FLAGGED: Missing database features that would improve injection detection:

1. String literal tracking:
   - Need to differentiate between string literals and variables
   - Would help identify hardcoded vs dynamic SQL

2. Data flow tracking:
   - Need to track if user input flows into dangerous functions
   - Currently we can't trace request.args -> variable -> execute()

3. Import context:
   - Need to know which libraries are imported (SQLAlchemy vs raw DB-API)
   - Different libraries have different safe patterns

4. Function parameter names:
   - Currently we have argument_expr but not parameter names
   - Would help identify if 'params=' is being used correctly

5. String interpolation details:
   - Can't differentiate between f"{safe_var}" and f"{user_input}"
   - Need more granular string formatting analysis
"""


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_injection_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Python injection vulnerabilities.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of injection vulnerabilities found
    """
    analyzer = InjectionAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# TAINT REGISTRATION (For Orchestrator)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register injection-specific taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = InjectionPatterns()

    # Register user input sources
    for pattern in patterns.USER_INPUTS:
        taint_registry.register_source(pattern, "user_input", "python")

    # Register SQL sinks
    for pattern in patterns.SQL_METHODS:
        taint_registry.register_sink(pattern, "sql", "python")

    # Register command sinks
    for pattern in patterns.COMMAND_METHODS:
        taint_registry.register_sink(pattern, "command", "python")

    # Register code execution sinks
    for pattern in patterns.CODE_INJECTION:
        taint_registry.register_sink(pattern, "code_execution", "python")

    # Register template sinks
    for pattern in patterns.TEMPLATE_PATTERNS:
        taint_registry.register_sink(pattern, "template", "python")

    # Register LDAP sinks
    for pattern in patterns.LDAP_METHODS:
        taint_registry.register_sink(pattern, "ldap", "python")

    # Register NoSQL sinks
    for pattern in patterns.NOSQL_METHODS:
        taint_registry.register_sink(pattern, "nosql", "python")