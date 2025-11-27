"""Python Injection Vulnerability Analyzer - Database-First Approach.

Detects various injection vulnerabilities in Python code using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
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
from dataclasses import dataclass

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="python_injection",
    category="injection",
    target_extensions=[".py"],
    exclude_patterns=[
        "frontend/",
        "client/",
        "node_modules/",
        "test/",
        "__tests__/",
        "migrations/",
    ],
    execution_scope="database",
    requires_jsx_pass=False,
)


@dataclass(frozen=True)
class InjectionPatterns:
    """Immutable pattern definitions for injection detection."""

    SQL_METHODS = frozenset(
        [
            "execute",
            "executemany",
            "executescript",
            "raw",
            "connection.execute",
            "cursor.execute",
            "db.execute",
            "query",
            "run_query",
            "session.execute",
            "db.session.execute",
            "select",
            "insert",
            "update",
            "delete",
            "create_table",
        ]
    )

    STRING_FORMAT_PATTERNS = frozenset(
        [
            ".format(",
            "% (",
            'f"',
            "f'",
            "%%",
            "+ request.",
            "+ params.",
            "+ args.",
            "+ user_input",
            "+ data[",
            "+ input(",
        ]
    )

    COMMAND_METHODS = frozenset(
        [
            "os.system",
            "subprocess.call",
            "subprocess.run",
            "subprocess.Popen",
            "os.popen",
            "popen",
            "commands.getstatusoutput",
            "commands.getoutput",
            "subprocess.check_output",
            "subprocess.check_call",
            "os.exec",
            "os.spawn",
            "os.startfile",
        ]
    )

    SHELL_TRUE_PATTERN = frozenset(["shell=True", "shell = True", "shell= True", "shell =True"])

    CODE_INJECTION = frozenset(
        ["eval", "exec", "compile", "__import__", "execfile", "input", "raw_input"]
    )

    TEMPLATE_PATTERNS = frozenset(
        [
            "render_template_string",
            "Environment",
            "Template",
            "jinja2.Template",
            "django.template.Template",
            "mako.template.Template",
            "tornado.template.Template",
        ]
    )

    LDAP_METHODS = frozenset(
        [
            "search",
            "search_s",
            "search_ext",
            "search_ext_s",
            "ldap.search",
            "ldap3.search",
            "ldap_search",
            "modify",
            "modify_s",
            "add",
            "add_s",
            "delete",
            "delete_s",
        ]
    )

    NOSQL_METHODS = frozenset(
        [
            "find",
            "find_one",
            "find_and_modify",
            "update_one",
            "update_many",
            "delete_one",
            "delete_many",
            "aggregate",
            "collection.find",
            "collection.update",
            "collection.delete",
            "db.find",
            "db.update",
            "db.delete",
        ]
    )

    XPATH_METHODS = frozenset(
        [
            "xpath",
            "findall",
            "find",
            "XPath",
            "evaluate",
            "selectNodes",
            "selectSingleNode",
            "query",
        ]
    )

    USER_INPUTS = frozenset(
        [
            "request.args",
            "request.form",
            "request.values",
            "request.data",
            "request.json",
            "request.files",
            "request.GET",
            "request.POST",
            "request.REQUEST",
            "input()",
            "raw_input()",
            "sys.argv",
            "os.environ",
            "flask.request",
            "django.request",
            "bottle.request",
        ]
    )

    SAFE_PATTERNS = frozenset(
        [
            "paramstyle",
            "params=",
            "parameters=",
            "?",
            "%s",
            "%(",
            ":name",
            "prepared",
            "statement",
            "placeholder",
        ]
    )

    SQL_KEYWORDS = frozenset(
        [
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "UNION",
            "WHERE",
            "ORDER BY",
            "GROUP BY",
            "CREATE",
            "ALTER",
            "EXEC",
            "EXECUTE",
            "--",
            "/*",
            "*/",
            ";",
            "OR 1=1",
            "OR true",
        ]
    )


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

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of injection vulnerabilities found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            self._check_sql_injection()
            self._check_command_injection()
            self._check_code_injection()
            self._check_template_injection()
            self._check_ldap_injection()
            self._check_nosql_injection()
            self._check_xpath_injection()
            self._check_raw_sql_construction()

        finally:
            conn.close()

        return self.findings

    def _get_assignment_expr(self, file: str, variable: str, call_line: int) -> str | None:
        """Get the latest assignment expression for a variable before a call line."""
        self.cursor.execute(
            """
            SELECT source_expr
            FROM assignments
            WHERE file = ? AND target_var = ? AND line <= ?
            ORDER BY line DESC
            LIMIT 1
            """,
            (file, variable, call_line),
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def _check_sql_injection(self):
        """Detect SQL injection vulnerabilities."""
        sql_placeholders = ",".join("?" * len(self.patterns.SQL_METHODS))

        self.cursor.execute(
            f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({sql_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """,
            list(self.patterns.SQL_METHODS),
        )

        for file, line, method, args in self.cursor.fetchall():
            if not args:
                continue

            assignment_expr = None
            arg_is_identifier = args.isidentifier()
            if arg_is_identifier:
                assignment_expr = self._get_assignment_expr(file, args, line)

            expr_to_check = assignment_expr or args

            has_formatting = expr_to_check and any(
                fmt in expr_to_check for fmt in self.patterns.STRING_FORMAT_PATTERNS
            )
            has_concatenation = (
                expr_to_check
                and "+" in expr_to_check
                and any(inp in expr_to_check for inp in ["request.", "params.", "args.", "user_"])
            )

            has_safe_params = expr_to_check and any(
                safe in expr_to_check for safe in self.patterns.SAFE_PATTERNS
            )

            if expr_to_check and (has_formatting or has_concatenation) and not has_safe_params:
                severity = Severity.CRITICAL
                confidence = Confidence.HIGH

                has_sql_keywords = any(
                    kw.lower() in expr_to_check.lower() for kw in self.patterns.SQL_KEYWORDS
                )
                if not has_sql_keywords:
                    confidence = Confidence.MEDIUM

                self.findings.append(
                    StandardFinding(
                        rule_name="python-sql-injection",
                        message=f"SQL injection in {method} with string formatting",
                        file_path=file,
                        line=line,
                        severity=severity,
                        category="injection",
                        confidence=confidence,
                        cwe_id="CWE-89",
                    )
                )

            is_fstring = False
            if expr_to_check and (
                'f"' in expr_to_check
                or "f'" in expr_to_check
                or (
                    arg_is_identifier
                    and assignment_expr
                    and ('f"' in assignment_expr or "f'" in assignment_expr)
                )
            ):
                is_fstring = True

            if is_fstring:
                self.findings.append(
                    StandardFinding(
                        rule_name="python-sql-fstring",
                        message="F-string used in SQL query - high injection risk",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-89",
                    )
                )

    def _check_command_injection(self):
        """Detect command injection vulnerabilities."""
        cmd_placeholders = ",".join("?" * len(self.patterns.COMMAND_METHODS))

        self.cursor.execute(
            f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({cmd_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """,
            list(self.patterns.COMMAND_METHODS),
        )

        for file, line, method, args in self.cursor.fetchall():
            if not args:
                continue

            has_shell_true = any(shell in args for shell in self.patterns.SHELL_TRUE_PATTERN)

            has_user_input = any(inp in args for inp in self.patterns.USER_INPUTS)
            has_concatenation = "+" in args or ".format(" in args or 'f"' in args or "f'" in args

            if has_shell_true:
                self.findings.append(
                    StandardFinding(
                        rule_name="python-shell-true",
                        message="Command execution with shell=True is dangerous",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-78",
                    )
                )

            elif has_user_input or has_concatenation:
                confidence = Confidence.HIGH if has_user_input else Confidence.MEDIUM

                self.findings.append(
                    StandardFinding(
                        rule_name="python-command-injection",
                        message=f"Command injection risk in {method}",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        confidence=confidence,
                        cwe_id="CWE-78",
                    )
                )

    def _check_code_injection(self):
        """Detect code injection (eval/exec) vulnerabilities."""
        code_placeholders = ",".join("?" * len(self.patterns.CODE_INJECTION))

        self.cursor.execute(
            f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({code_placeholders})
            ORDER BY file, line
        """,
            list(self.patterns.CODE_INJECTION),
        )

        for file, line, method, args in self.cursor.fetchall():
            severity = Severity.CRITICAL
            confidence = Confidence.HIGH

            if (
                args
                and (args.startswith('"') or args.startswith("'"))
                and not any(inp in args for inp in self.patterns.USER_INPUTS)
            ):
                confidence = Confidence.MEDIUM
                severity = Severity.HIGH

            self.findings.append(
                StandardFinding(
                    rule_name="python-code-injection",
                    message=f"Code injection risk: {method}() with dynamic input",
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="injection",
                    confidence=confidence,
                    cwe_id="CWE-94",
                )
            )

    def _check_template_injection(self):
        """Detect template injection vulnerabilities."""
        template_placeholders = ",".join("?" * len(self.patterns.TEMPLATE_PATTERNS))

        self.cursor.execute(
            f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({template_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """,
            list(self.patterns.TEMPLATE_PATTERNS),
        )

        for file, line, method, args in self.cursor.fetchall():
            has_user_input = any(inp in args for inp in self.patterns.USER_INPUTS)

            if "render_template_string" in method:
                self.findings.append(
                    StandardFinding(
                        rule_name="python-template-injection",
                        message="render_template_string() is vulnerable to template injection",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-1336",
                    )
                )

            elif has_user_input:
                self.findings.append(
                    StandardFinding(
                        rule_name="python-template-user-input",
                        message=f"User input passed to template {method}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="injection",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-1336",
                    )
                )

    def _check_ldap_injection(self):
        """Detect LDAP injection vulnerabilities."""
        ldap_placeholders = ",".join("?" * len(self.patterns.LDAP_METHODS))

        self.cursor.execute(
            f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({ldap_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """,
            list(self.patterns.LDAP_METHODS),
        )

        for file, line, method, args in self.cursor.fetchall():
            has_formatting = any(fmt in args for fmt in self.patterns.STRING_FORMAT_PATTERNS)
            has_user_input = any(inp in args for inp in self.patterns.USER_INPUTS)

            if has_formatting or has_user_input:
                self.findings.append(
                    StandardFinding(
                        rule_name="python-ldap-injection",
                        message=f"LDAP injection risk in {method}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="injection",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-90",
                    )
                )

    def _check_nosql_injection(self):
        """Detect NoSQL injection vulnerabilities."""
        nosql_placeholders = ",".join("?" * len(self.patterns.NOSQL_METHODS))

        self.cursor.execute(
            f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({nosql_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """,
            list(self.patterns.NOSQL_METHODS),
        )

        for file, line, method, args in self.cursor.fetchall():
            dangerous_operators = ["$where", "$regex", "$function", "function()", "eval("]
            has_dangerous = any(op in args for op in dangerous_operators)

            has_user_input = any(inp in args for inp in self.patterns.USER_INPUTS)

            if has_dangerous:
                self.findings.append(
                    StandardFinding(
                        rule_name="python-nosql-dangerous-operator",
                        message=f"Dangerous NoSQL operator in {method}",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-943",
                    )
                )

            elif has_user_input:
                self.findings.append(
                    StandardFinding(
                        rule_name="python-nosql-injection",
                        message=f"NoSQL injection risk in {method}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="injection",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-943",
                    )
                )

    def _check_xpath_injection(self):
        """Detect XPath injection vulnerabilities."""
        xpath_placeholders = ",".join("?" * len(self.patterns.XPATH_METHODS))

        self.cursor.execute(
            f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({xpath_placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """,
            list(self.patterns.XPATH_METHODS),
        )

        for file, line, method, args in self.cursor.fetchall():
            has_formatting = any(fmt in args for fmt in self.patterns.STRING_FORMAT_PATTERNS)

            if has_formatting:
                self.findings.append(
                    StandardFinding(
                        rule_name="python-xpath-injection",
                        message=f"XPath injection risk in {method}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="injection",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-91",
                    )
                )

    def _check_raw_sql_construction(self):
        """Check for SQL constructed in assignments."""
        from theauditor.indexer.schema import build_query

        query = build_query(
            "assignments", ["file", "line", "target_var", "source_expr"], order_by="file, line"
        )
        self.cursor.execute(query)

        sql_keyword_list = list(self.patterns.SQL_KEYWORDS)
        for file, line, var, expr in self.cursor.fetchall():
            if not expr:
                continue

            expr_upper = expr.upper()
            has_sql_keyword = any(keyword in expr_upper for keyword in sql_keyword_list[:10])
            if not has_sql_keyword:
                continue

            has_formatting = any(pattern in expr for pattern in ["+", ".format(", 'f"', "f'"])
            if not has_formatting:
                continue

            if any(kw in expr_upper for kw in ["SELECT", "INSERT", "UPDATE", "DELETE"]):
                self.findings.append(
                    StandardFinding(
                        rule_name="python-sql-string-building",
                        message=f"SQL query built with string concatenation in {var}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="injection",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-89",
                    )
                )


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


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Python injection vulnerabilities.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of injection vulnerabilities found
    """
    analyzer = InjectionAnalyzer(context)
    return analyzer.analyze()


def register_taint_patterns(taint_registry):
    """Register injection-specific taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = InjectionPatterns()

    for pattern in patterns.USER_INPUTS:
        taint_registry.register_source(pattern, "user_input", "python")

    for pattern in patterns.SQL_METHODS:
        taint_registry.register_sink(pattern, "sql", "python")

    for pattern in patterns.COMMAND_METHODS:
        taint_registry.register_sink(pattern, "command", "python")

    for pattern in patterns.CODE_INJECTION:
        taint_registry.register_sink(pattern, "code_execution", "python")

    for pattern in patterns.TEMPLATE_PATTERNS:
        taint_registry.register_sink(pattern, "template", "python")

    for pattern in patterns.LDAP_METHODS:
        taint_registry.register_sink(pattern, "ldap", "python")

    for pattern in patterns.NOSQL_METHODS:
        taint_registry.register_sink(pattern, "nosql", "python")
