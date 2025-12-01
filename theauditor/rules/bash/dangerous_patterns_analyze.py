"""Bash Dangerous Patterns Analyzer - Detects security anti-patterns in shell scripts."""

import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="bash_dangerous_patterns",
    category="security",
    target_extensions=[".sh", ".bash"],
    exclude_patterns=["node_modules/", "vendor/", ".git/"],
    execution_scope="database",
    requires_jsx_pass=False,
)

# Credential variable name patterns
CREDENTIAL_PATTERNS = (
    "PASSWORD",
    "PASSWD",
    "SECRET",
    "API_KEY",
    "APIKEY",
    "TOKEN",
    "AUTH",
    "CREDENTIAL",
    "PRIVATE_KEY",
    "AWS_SECRET",
    "DB_PASS",
    "MYSQL_PASS",
    "POSTGRES_PASS",
    "REDIS_PASS",
)

# Network fetching commands
NETWORK_COMMANDS = frozenset(["curl", "wget", "nc", "netcat", "fetch"])

# Shell execution commands (pipe targets)
SHELL_COMMANDS = frozenset(["bash", "sh", "zsh", "ksh", "dash", "eval", "source"])


class BashDangerousPatternsAnalyzer:
    """Analyzer for dangerous Bash patterns."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context."""
        self.context = context
        self.findings: list[StandardFinding] = []
        self.seen: set[str] = set()

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()

        self._check_curl_pipe_bash()
        self._check_hardcoded_credentials()
        self._check_unsafe_temp_files()
        self._check_missing_safety_flags()
        self._check_sudo_abuse()
        self._check_chmod_777()
        self._check_weak_crypto()
        self._check_path_manipulation()
        self._check_ifs_manipulation()  # Task 3.3.6 DRAGON
        self._check_relative_command_paths()  # Task 3.5.1
        self._check_security_sensitive_commands()  # Task 3.5.3

        conn.close()

        return self.findings

    def _add_finding(
        self,
        file: str,
        line: int,
        rule_name: str,
        message: str,
        severity: Severity,
        confidence: Confidence = Confidence.HIGH,
        cwe_id: str | None = None,
    ) -> None:
        """Add a finding if not already seen."""
        key = f"{file}:{line}:{rule_name}"
        if key in self.seen:
            return
        self.seen.add(key)

        self.findings.append(
            StandardFinding(
                rule_name=rule_name,
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="security",
                confidence=confidence,
                cwe_id=cwe_id,
            )
        )

    def _check_curl_pipe_bash(self) -> None:
        """Detect curl/wget piped directly to bash - critical security risk."""
        network_list = ", ".join(f"'{cmd}'" for cmd in NETWORK_COMMANDS)
        shell_list = ", ".join(f"'{cmd}'" for cmd in SHELL_COMMANDS)

        self.cursor.execute(f"""
            SELECT
                p1.file,
                p1.line,
                p1.pipeline_id,
                p1.command_text as source_cmd,
                p2.command_text as sink_cmd
            FROM bash_pipes p1
            JOIN bash_pipes p2
                ON p1.file = p2.file
                AND p1.pipeline_id = p2.pipeline_id
                AND p1.position < p2.position
            JOIN bash_commands c1
                ON p1.file = c1.file AND p1.line = c1.line
            JOIN bash_commands c2
                ON p2.file = c2.file AND p2.line = c2.line
            WHERE c1.command_name IN ({network_list})
              AND c2.command_name IN ({shell_list})
        """)

        for row in self.cursor.fetchall():
            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-curl-pipe-bash",
                message="Remote code execution: piping network data to shell",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-94",
            )

    def _check_hardcoded_credentials(self) -> None:
        """Detect hardcoded credentials in variable assignments."""
        # Build LIKE conditions for credential patterns
        like_conditions = " OR ".join(
            f"UPPER(name) LIKE '%{pattern}%'" for pattern in CREDENTIAL_PATTERNS
        )

        self.cursor.execute(f"""
            SELECT file, line, name, value_expr, scope
            FROM bash_variables
            WHERE ({like_conditions})
              AND value_expr IS NOT NULL
              AND value_expr != ''
              AND value_expr NOT LIKE '$%'
        """)

        for row in self.cursor.fetchall():
            value = row["value_expr"] or ""
            # Skip environment variable references
            if value.startswith("$") or value.startswith("${"):
                continue
            # Skip empty quoted strings
            if value in ('""', "''"):
                continue

            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-hardcoded-credential",
                message=f"Potential hardcoded credential: {row['name']}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-798",
            )

    def _check_unsafe_temp_files(self) -> None:
        """Detect predictable temp file usage without mktemp."""
        self.cursor.execute("""
            SELECT file, line, target, direction
            FROM bash_redirections
            WHERE target LIKE '/tmp/%'
              AND target NOT LIKE '%$$%'
              AND target NOT LIKE '%$RANDOM%'
        """)

        for row in self.cursor.fetchall():
            target = row["target"]
            # Check if it's a predictable name (no random component)
            if "mktemp" not in target.lower():
                self._add_finding(
                    file=row["file"],
                    line=row["line"],
                    rule_name="bash-unsafe-temp",
                    message=f"Predictable temp file: {target}",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-377",
                )

    def _check_missing_safety_flags(self) -> None:
        """Check if script has set -e, set -u, set -o pipefail."""
        # Get all unique files with bash content
        self.cursor.execute("""
            SELECT DISTINCT file FROM bash_commands
        """)

        files = [row["file"] for row in self.cursor.fetchall()]

        for file in files:
            # Check for safety set commands
            self.cursor.execute(
                """
                SELECT command_name, GROUP_CONCAT(a.arg_value, ' ') as args
                FROM bash_commands c
                LEFT JOIN bash_command_args a
                    ON c.file = a.file
                    AND c.line = a.command_line
                    AND c.pipeline_position IS a.command_pipeline_position
                WHERE c.file = ?
                  AND c.command_name = 'set'
                GROUP BY c.file, c.line
            """,
                (file,),
            )

            has_set_e = False
            has_set_u = False
            has_pipefail = False

            for row in self.cursor.fetchall():
                args = row["args"] or ""
                if "-e" in args or "-o errexit" in args:
                    has_set_e = True
                if "-u" in args or "-o nounset" in args:
                    has_set_u = True
                if "pipefail" in args:
                    has_pipefail = True

            if not has_set_e:
                self._add_finding(
                    file=file,
                    line=1,
                    rule_name="bash-missing-set-e",
                    message="Script lacks 'set -e' - errors may go unnoticed",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                )

            if not has_set_u:
                self._add_finding(
                    file=file,
                    line=1,
                    rule_name="bash-missing-set-u",
                    message="Script lacks 'set -u' - undefined variables allowed",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                )

    def _check_sudo_abuse(self) -> None:
        """Detect sudo with variable arguments."""
        self.cursor.execute("""
            SELECT
                c.file,
                c.line,
                GROUP_CONCAT(a.arg_value, ' ') as args,
                a.has_expansion
            FROM bash_commands c
            LEFT JOIN bash_command_args a
                ON c.file = a.file
                AND c.line = a.command_line
                AND c.pipeline_position IS a.command_pipeline_position
            WHERE c.command_name = 'sudo'
            GROUP BY c.file, c.line
            HAVING SUM(CASE WHEN a.has_expansion = 1 THEN 1 ELSE 0 END) > 0
        """)

        for row in self.cursor.fetchall():
            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-sudo-variable",
                message="sudo with variable expansion - privilege escalation risk",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-269",
            )

    def _check_chmod_777(self) -> None:
        """Detect chmod 777 and other overly permissive modes."""
        self.cursor.execute("""
            SELECT c.file, c.line, a.arg_value
            FROM bash_commands c
            JOIN bash_command_args a
                ON c.file = a.file
                AND c.line = a.command_line
                AND c.pipeline_position IS a.command_pipeline_position
            WHERE c.command_name = 'chmod'
              AND (a.arg_value = '777' OR a.arg_value = '666' OR a.arg_value = '+x')
        """)

        for row in self.cursor.fetchall():
            mode = row["arg_value"]
            if mode == "777":
                self._add_finding(
                    file=row["file"],
                    line=row["line"],
                    rule_name="bash-chmod-777",
                    message="chmod 777 creates world-writable file",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-732",
                )
            elif mode == "666":
                self._add_finding(
                    file=row["file"],
                    line=row["line"],
                    rule_name="bash-chmod-666",
                    message="chmod 666 creates world-writable file",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-732",
                )

    def _check_weak_crypto(self) -> None:
        """Detect usage of weak cryptographic tools."""
        self.cursor.execute("""
            SELECT file, line, command_name
            FROM bash_commands
            WHERE command_name IN ('md5sum', 'md5', 'sha1sum', 'sha1')
        """)

        for row in self.cursor.fetchall():
            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-weak-crypto",
                message=f"Weak hash algorithm: {row['command_name']}",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-328",
            )

    def _check_path_manipulation(self) -> None:
        """Detect PATH variable manipulation."""
        self.cursor.execute("""
            SELECT file, line, name, value_expr, scope
            FROM bash_variables
            WHERE name = 'PATH'
        """)

        for row in self.cursor.fetchall():
            value = row["value_expr"] or ""
            # Check for prepending to PATH (can hijack commands)
            if value.startswith(".") or value.startswith("$PWD"):
                self._add_finding(
                    file=row["file"],
                    line=row["line"],
                    rule_name="bash-path-injection",
                    message="PATH prepended with relative/current directory",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-426",
                )
            elif "PATH" in value:
                # Just informational for other PATH modifications
                self._add_finding(
                    file=row["file"],
                    line=row["line"],
                    rule_name="bash-path-modification",
                    message="PATH environment variable modified",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                )

    def _check_ifs_manipulation(self) -> None:
        """Detect IFS variable manipulation (Task 3.3.6 DRAGON).

        IFS (Internal Field Separator) manipulation can alter word splitting
        behavior, potentially bypassing unquoted variable protections.
        """
        self.cursor.execute("""
            SELECT file, line, name, value_expr, scope, containing_function
            FROM bash_variables
            WHERE name = 'IFS'
        """)

        for row in self.cursor.fetchall():
            value = row["value_expr"] or ""
            containing_func = row["containing_function"]

            # Any IFS modification requires manual review
            if value == '""' or value == "''":
                # IFS='' disables word splitting entirely
                self._add_finding(
                    file=row["file"],
                    line=row["line"],
                    rule_name="bash-ifs-empty",
                    message="IFS set to empty - word splitting disabled",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                )
            elif value:
                self._add_finding(
                    file=row["file"],
                    line=row["line"],
                    rule_name="bash-ifs-modified",
                    message=f"IFS modified - manual review required{' (in ' + containing_func + ')' if containing_func else ''}",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                )

    def _check_relative_command_paths(self) -> None:
        """Detect commands invoked without absolute paths (Task 3.5.1).

        Security-sensitive commands should use absolute paths to prevent
        PATH-based command hijacking attacks.
        """
        # Security-sensitive commands that should use absolute paths
        sensitive_commands = (
            "rm",
            "chmod",
            "chown",
            "kill",
            "pkill",
            "mount",
            "umount",
            "iptables",
            "ip6tables",
            "systemctl",
            "service",
            "dd",
        )
        sensitive_list = ", ".join(f"'{cmd}'" for cmd in sensitive_commands)

        self.cursor.execute(f"""
            SELECT file, line, command_name, containing_function
            FROM bash_commands
            WHERE command_name IN ({sensitive_list})
              AND command_name NOT LIKE '/%'
              AND command_name NOT LIKE './%'
        """)

        for row in self.cursor.fetchall():
            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-relative-sensitive-cmd",
                message=f"Security-sensitive command '{row['command_name']}' uses relative path",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-426",
            )

    def _check_security_sensitive_commands(self) -> None:
        """Flag security-sensitive commands that need careful review (Task 3.5.3)."""
        # Commands that should be reviewed for security implications
        high_risk_commands = {
            "eval": "Dynamic code execution",
            "source": "Script injection possible",
            ".": "Script injection possible",
            "exec": "Process replacement",
        }

        # Commands with variable arguments (detected via wrapped_command)
        self.cursor.execute("""
            SELECT file, line, command_name, wrapped_command
            FROM bash_commands
            WHERE wrapped_command IS NOT NULL
              AND wrapped_command LIKE '$%'
        """)

        for row in self.cursor.fetchall():
            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-wrapper-variable-cmd",
                message=f"Wrapper '{row['command_name']}' executes variable command",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-78",
            )

        # Check for commands that execute variable names (command name starts with $)
        self.cursor.execute("""
            SELECT file, line, command_name
            FROM bash_commands
            WHERE command_name LIKE '$%'
        """)

        for row in self.cursor.fetchall():
            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-variable-command",
                message=f"Variable used as command: {row['command_name']}",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-78",
            )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect dangerous Bash patterns."""
    analyzer = BashDangerousPatternsAnalyzer(context)
    return analyzer.analyze()
