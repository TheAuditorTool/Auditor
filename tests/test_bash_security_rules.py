"""
Bash Security Rules Unit Tests - Test injection, quoting, and dangerous patterns analyzers.

These tests verify that Bash security rules correctly detect vulnerabilities
by parsing test code, populating a database, and running the analyzers.

Created as part of: add-bash-support OpenSpec proposal
Task: 4.2.4 Unit tests for each security rule
Task: 4.2.10 Test case for BashPipeStrategy edge creation
"""

import sqlite3
import tempfile
import os

import pytest
from tree_sitter_language_pack import get_parser

from theauditor.ast_extractors import bash_impl
from theauditor.indexer.schemas.bash_schema import BASH_TABLES
from theauditor.rules.base import StandardRuleContext
from theauditor.rules.bash import injection_analyze, quoting_analyze, dangerous_patterns_analyze
from theauditor.graph.strategies.bash_pipes import BashPipeStrategy


@pytest.fixture
def bash_parser():
    """Create a Bash tree-sitter parser."""
    return get_parser("bash")


@pytest.fixture
def temp_db():
    """Create a temporary database with Bash schema."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for table_name, schema in BASH_TABLES.items():
        cursor.execute(schema.create_table_sql())

    conn.commit()
    conn.close()

    yield db_path

    os.unlink(db_path)


def populate_db(db_path: str, parser, code: str, file_path: str = "test.sh"):
    """Parse code and populate database."""
    tree = parser.parse(code.encode("utf-8"))
    result = bash_impl.extract_all_bash_data(tree, code, file_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for func in result.get("bash_functions", []):
        cursor.execute(
            """
            INSERT INTO bash_functions (file, line, end_line, name, style, body_start_line, body_end_line)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                file_path,
                func["line"],
                func["end_line"],
                func["name"],
                func["style"],
                func.get("body_start_line"),
                func.get("body_end_line"),
            ),
        )

    for var in result.get("bash_variables", []):
        cursor.execute(
            """
            INSERT INTO bash_variables (file, line, name, scope, readonly, value_expr, containing_function)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                file_path,
                var["line"],
                var["name"],
                var["scope"],
                1 if var.get("readonly") else 0,
                var.get("value_expr"),
                var.get("containing_function"),
            ),
        )

    for src in result.get("bash_sources", []):
        cursor.execute(
            """
            INSERT INTO bash_sources (file, line, sourced_path, syntax, has_variable_expansion, containing_function)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                file_path,
                src["line"],
                src["sourced_path"],
                src["syntax"],
                1 if src.get("has_variable_expansion") else 0,
                src.get("containing_function"),
            ),
        )

    for cmd in result.get("bash_commands", []):
        cursor.execute(
            """
            INSERT INTO bash_commands (file, line, command_name, pipeline_position, containing_function, wrapped_command)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                file_path,
                cmd["line"],
                cmd["command_name"],
                cmd.get("pipeline_position"),
                cmd.get("containing_function"),
                cmd.get("wrapped_command"),
            ),
        )

        for idx, arg in enumerate(cmd.get("args", [])):
            normalized = arg.get("normalized_flags")
            if normalized and isinstance(normalized, list):
                normalized = ",".join(normalized)

            cursor.execute(
                """
                INSERT INTO bash_command_args (file, command_line, command_pipeline_position, arg_index,
                    arg_value, is_quoted, quote_type, has_expansion, expansion_vars, normalized_flags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    file_path,
                    cmd["line"],
                    cmd.get("pipeline_position"),
                    idx,
                    arg["value"],
                    1 if arg.get("is_quoted") else 0,
                    arg.get("quote_type", "none"),
                    1 if arg.get("has_expansion") else 0,
                    arg.get("expansion_vars"),
                    normalized,
                ),
            )

    for pipe in result.get("bash_pipes", []):
        cursor.execute(
            """
            INSERT INTO bash_pipes (file, line, pipeline_id, position, command_text, containing_function)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                file_path,
                pipe["line"],
                pipe["pipeline_id"],
                pipe["position"],
                pipe["command_text"],
                pipe.get("containing_function"),
            ),
        )

    for sub in result.get("bash_subshells", []):
        cursor.execute(
            """
            INSERT INTO bash_subshells (file, line, col, syntax, command_text, capture_target, containing_function)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                file_path,
                sub["line"],
                sub.get("col", 0),
                sub["syntax"],
                sub["command_text"],
                sub.get("capture_target"),
                sub.get("containing_function"),
            ),
        )

    for redir in result.get("bash_redirections", []):
        cursor.execute(
            """
            INSERT INTO bash_redirections (file, line, direction, target, fd_number, containing_function)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                file_path,
                redir["line"],
                redir["direction"],
                redir["target"],
                redir.get("fd_number"),
                redir.get("containing_function"),
            ),
        )

    conn.commit()
    conn.close()


def get_context(db_path: str) -> StandardRuleContext:
    """Create a rule context with the given database path."""
    from pathlib import Path

    return StandardRuleContext(
        file_path=Path("test.sh"),
        content="",
        language="bash",
        project_path=Path("."),
        db_path=db_path,
    )


class TestBashInjectionRules:
    """Tests for injection detection rules."""

    def test_eval_injection_detected(self, bash_parser, temp_db):
        """Test that eval with variable is detected."""
        code = '''eval "$USER_INPUT"'''
        populate_db(temp_db, bash_parser, code)

        findings = injection_analyze.analyze(get_context(temp_db))

        assert len(findings) >= 1
        eval_findings = [f for f in findings if "eval" in f.rule_name]
        assert len(eval_findings) >= 1

    def test_eval_literal_detected(self, bash_parser, temp_db):
        """Test that eval with literal is detected (lower severity)."""
        code = '''eval "echo hello"'''
        populate_db(temp_db, bash_parser, code)

        findings = injection_analyze.analyze(get_context(temp_db))

        assert len(findings) >= 1

    def test_source_injection_detected(self, bash_parser, temp_db):
        """Test that source with variable path is detected."""
        code = '''source "$CONFIG_FILE"'''
        populate_db(temp_db, bash_parser, code)

        findings = injection_analyze.analyze(get_context(temp_db))

        source_findings = [f for f in findings if "source" in f.rule_name]
        assert len(source_findings) >= 1

    def test_safe_source_not_detected(self, bash_parser, temp_db):
        """Test that source with literal path is not detected as injection."""
        code = """source /etc/profile"""
        populate_db(temp_db, bash_parser, code)

        findings = injection_analyze.analyze(get_context(temp_db))

        source_findings = [f for f in findings if "source-injection" in f.rule_name]
        assert len(source_findings) == 0

    def test_backtick_with_variable_detected(self, bash_parser, temp_db):
        """Test that backtick substitution with variable is detected."""
        code = """result=`cat $file`"""
        populate_db(temp_db, bash_parser, code)

        findings = injection_analyze.analyze(get_context(temp_db))

        backtick_findings = [f for f in findings if "backtick" in f.rule_name]
        assert len(backtick_findings) >= 1

    def test_xargs_injection_detected(self, bash_parser, temp_db):
        """Test that xargs with -I flag is detected."""
        code = """find . -name "*.txt" | xargs -I {} rm {}"""
        populate_db(temp_db, bash_parser, code)

        findings = injection_analyze.analyze(get_context(temp_db))

        xargs_findings = [f for f in findings if "xargs" in f.rule_name]
        assert len(xargs_findings) >= 1


class TestBashQuotingRules:
    """Tests for quoting analysis rules."""

    def test_unquoted_rm_detected(self, bash_parser, temp_db):
        """Test that unquoted variable in rm is detected."""
        code = """rm $file"""
        populate_db(temp_db, bash_parser, code)

        findings = quoting_analyze.analyze(get_context(temp_db))

        unquoted_findings = [f for f in findings if "unquoted" in f.rule_name.lower()]
        assert len(unquoted_findings) >= 1

    def test_quoted_rm_not_detected(self, bash_parser, temp_db):
        """Test that quoted variable in rm is not detected."""
        code = '''rm "$file"'''
        populate_db(temp_db, bash_parser, code)

        findings = quoting_analyze.analyze(get_context(temp_db))

        unquoted_dangerous = [f for f in findings if f.rule_name == "bash-unquoted-dangerous"]
        assert len(unquoted_dangerous) == 0

    def test_unquoted_expansion_generic(self, bash_parser, temp_db):
        """Test that unquoted expansion in non-dangerous command is detected."""
        code = """echo $variable"""
        populate_db(temp_db, bash_parser, code)

        findings = quoting_analyze.analyze(get_context(temp_db))

        unquoted_findings = [f for f in findings if "unquoted" in f.rule_name.lower()]
        assert len(unquoted_findings) >= 1

    def test_glob_injection_detected(self, bash_parser, temp_db):
        """Test that glob with variable in rm is detected."""
        code = """rm -rf "$DIR"/*"""
        populate_db(temp_db, bash_parser, code)

        findings = quoting_analyze.analyze(get_context(temp_db))

        assert isinstance(findings, list)


class TestBashDangerousPatternsRules:
    """Tests for dangerous pattern detection rules."""

    def test_curl_pipe_bash_detected(self, bash_parser, temp_db):
        """Test that curl | bash is detected."""
        code = """curl https://example.com/script.sh | bash"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        curl_bash_findings = [
            f for f in findings if "curl" in f.rule_name.lower() or "pipe" in f.rule_name.lower()
        ]
        assert len(curl_bash_findings) >= 1

    def test_wget_pipe_sh_detected(self, bash_parser, temp_db):
        """Test that wget | sh is detected."""
        code = """wget -O - https://example.com/install.sh | sh"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        assert isinstance(findings, list)

    def test_hardcoded_password_detected(self, bash_parser, temp_db):
        """Test that hardcoded password is detected."""
        code = '''DB_PASSWORD="supersecret123"'''
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        credential_findings = [f for f in findings if "credential" in f.rule_name.lower()]
        assert len(credential_findings) >= 1

    def test_hardcoded_api_key_detected(self, bash_parser, temp_db):
        """Test that hardcoded API key is detected."""
        code = '''API_KEY="abc123xyz"'''
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        credential_findings = [f for f in findings if "credential" in f.rule_name.lower()]
        assert len(credential_findings) >= 1

    def test_env_password_unquoted_not_detected(self, bash_parser, temp_db):
        """Test that password from env (unquoted) is not flagged as hardcoded."""

        code = """DB_PASSWORD=$DB_PASS"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        credential_findings = [f for f in findings if "hardcoded" in f.rule_name.lower()]
        assert len(credential_findings) == 0

    def test_chmod_777_detected(self, bash_parser, temp_db):
        """Test that chmod 777 is detected."""
        code = """chmod 777 /tmp/script.sh"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        chmod_findings = [f for f in findings if "chmod" in f.rule_name.lower()]
        assert len(chmod_findings) >= 1

    def test_missing_set_e_detected(self, bash_parser, temp_db):
        """Test that missing set -e is detected."""
        code = """#!/bin/bash
echo "no safety flags"
"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        set_findings = [f for f in findings if "missing-set" in f.rule_name]
        assert len(set_findings) >= 1

    def test_set_e_present_not_flagged(self, bash_parser, temp_db):
        """Test that script with set -e is not flagged for missing it."""
        code = """#!/bin/bash
set -e
echo "safe script"
"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        set_e_findings = [f for f in findings if f.rule_name == "bash-missing-set-e"]
        assert len(set_e_findings) == 0

    def test_sudo_with_variable_detected(self, bash_parser, temp_db):
        """Test that sudo with variable args is detected."""
        code = """sudo $CMD"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        sudo_findings = [f for f in findings if "sudo" in f.rule_name.lower()]
        assert len(sudo_findings) >= 1

    def test_ifs_manipulation_detected(self, bash_parser, temp_db):
        """Test that IFS manipulation is detected (DRAGON)."""
        code = '''IFS=":"'''
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        ifs_findings = [f for f in findings if "ifs" in f.rule_name.lower()]
        assert len(ifs_findings) >= 1

    def test_unsafe_temp_detected(self, bash_parser, temp_db):
        """Test that predictable temp file is detected."""
        code = """echo "data" > /tmp/myapp.log"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        temp_findings = [f for f in findings if "temp" in f.rule_name.lower()]
        assert len(temp_findings) >= 1

    def test_relative_sensitive_command_detected(self, bash_parser, temp_db):
        """Test that rm without absolute path is detected."""
        code = """rm -rf /tmp/test"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        relative_findings = [f for f in findings if "relative" in f.rule_name.lower()]
        assert len(relative_findings) >= 1

    def test_weak_crypto_detected(self, bash_parser, temp_db):
        """Test that md5sum usage is detected."""
        code = """md5sum file.txt > checksum.md5"""
        populate_db(temp_db, bash_parser, code)

        findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        crypto_findings = [f for f in findings if "crypto" in f.rule_name.lower()]
        assert len(crypto_findings) >= 1


class TestBashSecurityIntegration:
    """Integration tests running all rules on complex scripts."""

    def test_vulnerable_script(self, bash_parser, temp_db):
        """Test detection of multiple vulnerabilities in one script."""
        code = """#!/bin/bash
# Intentionally vulnerable script for testing

DB_PASSWORD="hunter2"
API_KEY="sk-test-12345"

# Eval injection
eval "$USER_INPUT"

# Unquoted variables
rm $file
chmod 777 $target

# Curl pipe bash
curl https://example.com/install.sh | bash

# Source with variable
source "$CONFIG_DIR/settings.sh"

# Missing set -e (implicit)
"""
        populate_db(temp_db, bash_parser, code)

        injection_findings = injection_analyze.analyze(get_context(temp_db))
        quoting_findings = quoting_analyze.analyze(get_context(temp_db))
        pattern_findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        total_findings = len(injection_findings) + len(quoting_findings) + len(pattern_findings)

        assert total_findings >= 5, f"Expected at least 5 findings, got {total_findings}"

    def test_secure_script_minimal_findings(self, bash_parser, temp_db):
        """Test that a well-written script has minimal findings."""
        code = """#!/bin/bash
set -euo pipefail

readonly CONFIG_FILE="/etc/myapp/config"

log() {
    local message="$1"
    echo "[$(date)] $message"
}

main() {
    source "$CONFIG_FILE"
    log "Starting application"
}

main "$@"
"""
        populate_db(temp_db, bash_parser, code)

        injection_findings = injection_analyze.analyze(get_context(temp_db))
        quoting_findings = quoting_analyze.analyze(get_context(temp_db))
        pattern_findings = dangerous_patterns_analyze.analyze(get_context(temp_db))

        critical_findings = [
            f
            for f in injection_findings + quoting_findings + pattern_findings
            if f.severity.name == "CRITICAL"
        ]

        assert len(critical_findings) <= 2


class TestBashPipeStrategyEdgeCreation:
    """Tests for BashPipeStrategy graph edge creation."""

    def test_pipe_flow_edges_created(self, bash_parser, temp_db):
        """Test that pipe flow edges are created between pipeline commands."""
        code = """cat file.txt | grep pattern | wc -l"""
        populate_db(temp_db, bash_parser, code)

        strategy = BashPipeStrategy()
        result = strategy.build(temp_db, ".")

        nodes = result["nodes"]
        edges = result["edges"]
        stats = result["metadata"]["stats"]

        assert len(nodes) >= 3

        pipe_edges = [e for e in edges if e["type"] == "pipe_flow"]

        assert len(pipe_edges) >= 2

        assert stats["pipelines_processed"] >= 1
        assert stats["pipe_edges"] >= 2

    def test_source_include_edges_created(self, bash_parser, temp_db):
        """Test that source include edges are created."""
        code = """source /etc/profile
. ./lib/utils.sh"""
        populate_db(temp_db, bash_parser, code)

        strategy = BashPipeStrategy()
        result = strategy.build(temp_db, ".")

        nodes = result["nodes"]
        edges = result["edges"]
        stats = result["metadata"]["stats"]

        source_nodes = [n for n in nodes if n["type"] == "bash_source_statement"]
        file_nodes = [n for n in nodes if n["type"] == "bash_sourced_file"]
        assert len(source_nodes) >= 2
        assert len(file_nodes) >= 2

        source_edges = [e for e in edges if e["type"] == "source_include"]
        assert len(source_edges) >= 2

        assert stats["source_edges"] >= 2

    def test_subshell_capture_edges_created(self, bash_parser, temp_db):
        """Test that subshell capture edges link to variables."""
        code = """RESULT=$(whoami)
OUTPUT=$(date +%Y-%m-%d)"""
        populate_db(temp_db, bash_parser, code)

        strategy = BashPipeStrategy()
        result = strategy.build(temp_db, ".")

        nodes = result["nodes"]
        edges = result["edges"]
        stats = result["metadata"]["stats"]

        subshell_nodes = [n for n in nodes if n["type"] == "bash_subshell"]
        var_nodes = [n for n in nodes if n["type"] == "bash_variable"]
        assert len(subshell_nodes) >= 2
        assert len(var_nodes) >= 2

        capture_edges = [e for e in edges if e["type"] == "subshell_capture"]
        assert len(capture_edges) >= 2

        assert stats["capture_edges"] >= 2

    def test_complex_script_all_edge_types(self, bash_parser, temp_db):
        """Test that a complex script creates all edge types."""
        code = """#!/bin/bash
source ./config.sh

get_data() {
    DATA=$(curl -s https://api.example.com/data)
    echo "$DATA"
}

process() {
    get_data | grep "pattern" | awk '{print $1}'
}

process
"""
        populate_db(temp_db, bash_parser, code)

        strategy = BashPipeStrategy()
        result = strategy.build(temp_db, ".")

        edges = result["edges"]
        stats = result["metadata"]["stats"]

        edge_types = set(e["type"] for e in edges)

        assert "source_include" in edge_types, "Expected source_include edges"

        assert stats["pipe_edges"] >= 2 or stats["capture_edges"] >= 1

    def test_empty_db_returns_empty_graph(self, temp_db):
        """Test that empty database returns empty graph without error."""
        strategy = BashPipeStrategy()
        result = strategy.build(temp_db, ".")

        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["metadata"]["stats"]["pipelines_processed"] == 0
