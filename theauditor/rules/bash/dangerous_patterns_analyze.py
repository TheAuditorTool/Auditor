"""Bash Dangerous Patterns Analyzer - Detects security anti-patterns in shell scripts."""

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="bash_dangerous_patterns",
    category="security",
    target_extensions=[".sh", ".bash"],
    exclude_patterns=["node_modules/", "vendor/", ".git/"],
    execution_scope="database",
    primary_table="bash_commands",
)


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


NETWORK_COMMANDS = frozenset(["curl", "wget", "nc", "netcat", "fetch"])


SHELL_COMMANDS = frozenset(["bash", "sh", "zsh", "ksh", "dash", "eval", "source"])


SENSITIVE_COMMANDS = (
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


def find_bash_dangerous_patterns(context: StandardRuleContext) -> RuleResult:
    """Detect dangerous Bash patterns.

    Named find_* for orchestrator discovery.

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []
    seen: set[str] = set()

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    def add_finding(
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
        if key in seen:
            return
        seen.add(key)

        findings.append(
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

    with RuleDB(context.db_path, METADATA.name) as db:
        _check_curl_pipe_bash(db, add_finding)

        _check_hardcoded_credentials(db, add_finding)

        _check_unsafe_temp_files(db, add_finding)

        _check_missing_safety_flags(db, add_finding)

        _check_sudo_abuse(db, add_finding)

        _check_chmod_777(db, add_finding)

        _check_weak_crypto(db, add_finding)

        _check_path_manipulation(db, add_finding)

        _check_ifs_manipulation(db, add_finding)

        _check_relative_command_paths(db, add_finding)

        _check_security_sensitive_commands(db, add_finding)

        _check_dangerous_environment_vars(db, add_finding)

        _check_read_without_raw(db, add_finding)

        _check_ssl_bypass(db, add_finding)

        _check_debug_mode_leak(db, add_finding)

        _check_ssh_hostkey_bypass(db, add_finding)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_curl_pipe_bash(db: RuleDB, add_finding) -> None:
    """Detect curl/wget piped directly to bash - critical security risk."""

    network_list = ", ".join(f"'{cmd}'" for cmd in NETWORK_COMMANDS)
    shell_list = ", ".join(f"'{cmd}'" for cmd in SHELL_COMMANDS)

    sql, params = Q.raw(
        f"""
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
        """,
        [],
    )

    for row in db.execute(sql, params):
        add_finding(
            file=row[0],
            line=row[1],
            rule_name="bash-curl-pipe-bash",
            message="Remote code execution: piping network data to shell",
            severity=Severity.CRITICAL,
            confidence=Confidence.HIGH,
            cwe_id="CWE-94",
        )


def _check_hardcoded_credentials(db: RuleDB, add_finding) -> None:
    """Detect hardcoded credentials in variable assignments."""

    like_conditions = " OR ".join(
        f"UPPER(name) LIKE '%{pattern}%'" for pattern in CREDENTIAL_PATTERNS
    )

    sql, params = Q.raw(
        f"""
        SELECT file, line, name, value_expr, scope
        FROM bash_variables
        WHERE ({like_conditions})
          AND value_expr IS NOT NULL
          AND value_expr != ''
          AND value_expr NOT LIKE '$%'
        """,
        [],
    )

    for row in db.execute(sql, params):
        file, line, name, value_expr, _scope = row
        value = value_expr or ""

        if value.startswith("$") or value.startswith("${"):
            continue

        if value in ('""', "''"):
            continue

        add_finding(
            file=file,
            line=line,
            rule_name="bash-hardcoded-credential",
            message=f"Potential hardcoded credential: {name}",
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-798",
        )


def _check_unsafe_temp_files(db: RuleDB, add_finding) -> None:
    """Detect predictable temp file usage without mktemp."""
    rows = db.query(
        Q("bash_redirections")
        .select("file", "line", "target", "direction")
        .where("target LIKE ?", "/tmp/%")
    )

    for file, line, target, _direction in rows:
        if "$$" not in target and "$RANDOM" not in target and "mktemp" not in target.lower():
            add_finding(
                file=file,
                line=line,
                rule_name="bash-unsafe-temp",
                message=f"Predictable temp file: {target}",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-377",
            )


def _check_missing_safety_flags(db: RuleDB, add_finding) -> None:
    """Check if script has set -e, set -u, set -o pipefail."""

    rows = db.query(Q("bash_commands").select("file"))

    files = {file for (file,) in rows}

    for file in files:
        set_rows = db.query(Q("bash_set_options").select("options").where("file = ?", file))

        has_set_e = False
        has_set_u = False

        for (options,) in set_rows:
            opts = options or ""
            if "-e" in opts or "errexit" in opts:
                has_set_e = True
            if "-u" in opts or "nounset" in opts:
                has_set_u = True

        if not has_set_e:
            add_finding(
                file=file,
                line=1,
                rule_name="bash-missing-set-e",
                message="Script lacks 'set -e' - errors may go unnoticed",
                severity=Severity.LOW,
                confidence=Confidence.HIGH,
            )

        if not has_set_u:
            add_finding(
                file=file,
                line=1,
                rule_name="bash-missing-set-u",
                message="Script lacks 'set -u' - undefined variables allowed",
                severity=Severity.LOW,
                confidence=Confidence.HIGH,
            )


def _check_sudo_abuse(db: RuleDB, add_finding) -> None:
    """Detect sudo with variable arguments."""
    rows = db.query(Q("bash_commands").select("file", "line").where("command_name = ?", "sudo"))

    for file, line in rows:
        arg_rows = db.query(
            Q("bash_command_args")
            .select("has_expansion")
            .where("file = ? AND command_line = ?", file, line)
        )

        has_expansion = any(has_exp for (has_exp,) in arg_rows if has_exp)

        if has_expansion:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-sudo-variable",
                message="sudo with variable expansion - privilege escalation risk",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-269",
            )


def _check_chmod_777(db: RuleDB, add_finding) -> None:
    """Detect chmod 777 and other overly permissive modes."""
    rows = db.query(Q("bash_commands").select("file", "line").where("command_name = ?", "chmod"))

    for file, line in rows:
        arg_rows = db.query(
            Q("bash_command_args")
            .select("arg_value")
            .where("file = ? AND command_line = ?", file, line)
        )

        for (arg_value,) in arg_rows:
            if arg_value == "777":
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-chmod-777",
                    message="chmod 777 creates world-writable file",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-732",
                )
            elif arg_value == "666":
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-chmod-666",
                    message="chmod 666 creates world-writable file",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-732",
                )


def _check_weak_crypto(db: RuleDB, add_finding) -> None:
    """Detect usage of weak cryptographic tools.

    Note: In shell scripts, md5sum/sha1sum are typically used for file integrity
    checks rather than password hashing. Downgraded to LOW severity.
    """
    rows = db.query(
        Q("bash_commands")
        .select("file", "line", "command_name")
        .where("command_name IN (?, ?, ?, ?)", "md5sum", "md5", "sha1sum", "sha1")
    )

    for file, line, command_name in rows:
        add_finding(
            file=file,
            line=line,
            rule_name="bash-weak-crypto",
            message=f"Weak hash algorithm: {command_name} (verify not used for security)",
            severity=Severity.LOW,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-328",
        )


def _check_path_manipulation(db: RuleDB, add_finding) -> None:
    """Detect PATH variable manipulation."""
    rows = db.query(
        Q("bash_variables")
        .select("file", "line", "name", "value_expr", "scope")
        .where("name = ?", "PATH")
    )

    for file, line, _name, value_expr, _scope in rows:
        value = value_expr or ""

        if value.startswith(".") or value.startswith("$PWD"):
            add_finding(
                file=file,
                line=line,
                rule_name="bash-path-injection",
                message="PATH prepended with relative/current directory",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-426",
            )
        elif "PATH" in value:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-path-modification",
                message="PATH environment variable modified",
                severity=Severity.LOW,
                confidence=Confidence.HIGH,
            )


def _check_ifs_manipulation(db: RuleDB, add_finding) -> None:
    """Detect IFS variable manipulation.

    IFS (Internal Field Separator) manipulation can alter word splitting
    behavior, potentially bypassing unquoted variable protections.
    """
    rows = db.query(
        Q("bash_variables")
        .select("file", "line", "name", "value_expr", "scope", "containing_function")
        .where("name = ?", "IFS")
    )

    for file, line, _name, value_expr, _scope, containing_func in rows:
        value = value_expr or ""

        if value == '""' or value == "''":
            add_finding(
                file=file,
                line=line,
                rule_name="bash-ifs-empty",
                message="IFS set to empty - word splitting disabled",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        elif value:
            func_note = f" (in {containing_func})" if containing_func else ""
            add_finding(
                file=file,
                line=line,
                rule_name="bash-ifs-modified",
                message=f"IFS modified - manual review required{func_note}",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
            )


def _check_relative_command_paths(db: RuleDB, add_finding) -> None:
    """Detect commands invoked without absolute paths.

    Security-sensitive commands should use absolute paths to prevent
    PATH-based command hijacking attacks.
    """
    sensitive_list = ", ".join(f"'{cmd}'" for cmd in SENSITIVE_COMMANDS)

    sql, params = Q.raw(
        f"""
        SELECT file, line, command_name, containing_function
        FROM bash_commands
        WHERE command_name IN ({sensitive_list})
          AND command_name NOT LIKE '/%'
          AND command_name NOT LIKE './%'
        """,
        [],
    )

    for row in db.execute(sql, params):
        file, line, command_name, _containing_func = row
        add_finding(
            file=file,
            line=line,
            rule_name="bash-relative-sensitive-cmd",
            message=f"Security-sensitive command '{command_name}' uses relative path",
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-426",
        )


def _check_security_sensitive_commands(db: RuleDB, add_finding) -> None:
    """Flag security-sensitive commands that need careful review."""

    rows = db.query(
        Q("bash_commands")
        .select("file", "line", "command_name", "wrapped_command")
        .where("wrapped_command IS NOT NULL AND wrapped_command LIKE ?", "$%")
    )

    for file, line, command_name, _wrapped_command in rows:
        add_finding(
            file=file,
            line=line,
            rule_name="bash-wrapper-variable-cmd",
            message=f"Wrapper '{command_name}' executes variable command",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            cwe_id="CWE-78",
        )

    rows = db.query(
        Q("bash_commands").select("file", "line", "command_name").where("command_name LIKE ?", "$%")
    )

    for file, line, command_name in rows:
        add_finding(
            file=file,
            line=line,
            rule_name="bash-variable-command",
            message=f"Variable used as command: {command_name}",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            cwe_id="CWE-78",
        )


def _check_dangerous_environment_vars(db: RuleDB, add_finding) -> None:
    """Detect dangerous environment variables that can hijack execution.

    LD_PRELOAD, LD_LIBRARY_PATH, PYTHONPATH, PERL5LIB can be used to inject
    malicious libraries or modules into child processes.
    """
    DANGEROUS_VARS = ("LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH", "PERL5LIB", "NODE_PATH")  # noqa: N806 - constant

    placeholders = ", ".join(["?"] * len(DANGEROUS_VARS))
    sql, params = Q.raw(
        f"""
        SELECT file, line, name
        FROM bash_variables
        WHERE name IN ({placeholders})
        """,
        list(DANGEROUS_VARS),
    )

    for row in db.execute(sql, params):
        file, line, name = row
        add_finding(
            file=file,
            line=line,
            rule_name="bash-environment-injection",
            message=f"Setting dangerous environment variable: {name}",
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-426",
        )


def _check_read_without_raw(db: RuleDB, add_finding) -> None:
    """Detect read command without -r flag.

    Without -r, backslashes in input are interpreted as escape characters,
    allowing line continuation injection. An attacker can inject:
        input\\nmalicious_command
    which becomes a single line, potentially executing unintended commands.

    CWE-78: Improper Neutralization of Special Elements used in an OS Command
    """
    rows = db.query(Q("bash_commands").select("file", "line").where("command_name = ?", "read"))

    for file, line in rows:
        arg_rows = db.query(
            Q("bash_command_args")
            .select("arg_value", "normalized_flags")
            .where("file = ? AND command_line = ?", file, line)
        )

        has_raw_flag = False
        for arg_value, normalized_flags in arg_rows:
            flags = normalized_flags or ""
            arg = arg_value or ""

            if "r" in flags or arg == "-r" or (arg.startswith("-") and "r" in arg):
                has_raw_flag = True
                break

        if not has_raw_flag:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-read-without-r",
                message="read without -r flag allows backslash escape injection",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                cwe_id="CWE-78",
            )


def _check_ssl_bypass(db: RuleDB, add_finding) -> None:
    """Detect SSL/TLS certificate validation bypass.

    curl -k, curl --insecure, wget --no-check-certificate disable
    certificate validation, enabling MITM attacks.

    CWE-295: Improper Certificate Validation
    """
    INSECURE_FLAGS = frozenset(["-k", "--insecure", "--no-check-certificate"])  # noqa: N806 - constant

    rows = db.query(
        Q("bash_commands")
        .select("file", "line", "command_name")
        .where("command_name IN (?, ?)", "curl", "wget")
    )

    for file, line, command_name in rows:
        arg_rows = db.query(
            Q("bash_command_args")
            .select("arg_value")
            .where("file = ? AND command_line = ?", file, line)
        )

        for (arg_value,) in arg_rows:
            if arg_value in INSECURE_FLAGS:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-ssl-bypass",
                    message=f"{command_name} with {arg_value} disables certificate validation - MITM risk",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-295",
                )
                break


def _check_debug_mode_leak(db: RuleDB, add_finding) -> None:
    """Detect debug mode that leaks secrets to stderr.

    set -x (or set -o xtrace) prints all executed commands including
    their arguments to stderr. Secrets passed as arguments are exposed.

    CWE-532: Insertion of Sensitive Information into Log File
    """
    rows = db.query(Q("bash_set_options").select("file", "line", "options"))

    for file, line, options in rows:
        opts = options or ""

        if "-x" in opts or "xtrace" in opts:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-debug-mode-leak",
                message="set -x exposes all commands and arguments to stderr (secrets leak)",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-532",
            )


def _check_ssh_hostkey_bypass(db: RuleDB, add_finding) -> None:
    """Detect SSH host key checking bypass.

    ssh -o StrictHostKeyChecking=no disables host key verification,
    enabling man-in-the-middle attacks on SSH connections.

    CWE-300: Channel Accessible by Non-Endpoint
    """
    rows = db.query(
        Q("bash_commands")
        .select("file", "line", "command_name")
        .where("command_name IN (?, ?, ?)", "ssh", "scp", "sftp")
    )

    for file, line, command_name in rows:
        arg_rows = db.query(
            Q("bash_command_args")
            .select("arg_value")
            .where("file = ? AND command_line = ?", file, line)
        )

        for (arg_value,) in arg_rows:
            arg = arg_value or ""

            if "StrictHostKeyChecking=no" in arg or "StrictHostKeyChecking=accept-new" in arg:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-ssh-hostkey-bypass",
                    message=f"{command_name} with StrictHostKeyChecking disabled - MITM risk",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-300",
                )
                break

            if "UserKnownHostsFile=/dev/null" in arg:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-ssh-hostkey-bypass",
                    message=f"{command_name} with UserKnownHostsFile=/dev/null - host verification disabled",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-300",
                )
                break
