"""Tests for ASCII-only CLI help output.

Windows Command Prompt uses CP1252 encoding which cannot handle emojis
or Unicode characters. This test ensures all CLI help text is pure ASCII.

See CLAUDE.md: NEVER USE EMOJIS IN PYTHON OUTPUT
"""

import pytest
from click.testing import CliRunner

from theauditor.cli import cli
from theauditor.commands.manual import EXPLANATIONS


class TestCliAsciiCompliance:
    """Ensure all CLI output is ASCII-safe for Windows CP1252."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_root_help_ascii(self, runner):
        """Test aud --help contains only ASCII characters."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

        try:
            result.output.encode("ascii")
        except UnicodeEncodeError as e:
            pytest.fail(f"Non-ASCII character in aud --help: {e}")

    def test_query_help_ascii(self, runner):
        """Test aud query --help contains only ASCII characters."""
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0
        try:
            result.output.encode("ascii")
        except UnicodeEncodeError as e:
            pytest.fail(f"Non-ASCII character in aud query --help: {e}")

    def test_explain_help_ascii(self, runner):
        """Test aud explain --help contains only ASCII characters."""
        result = runner.invoke(cli, ["explain", "--help"])
        assert result.exit_code == 0
        try:
            result.output.encode("ascii")
        except UnicodeEncodeError as e:
            pytest.fail(f"Non-ASCII character in aud explain --help: {e}")

    def test_manual_list_ascii(self, runner):
        """Test aud manual --list contains only ASCII characters."""
        result = runner.invoke(cli, ["manual", "--list"])
        assert result.exit_code == 0
        try:
            result.output.encode("ascii")
        except UnicodeEncodeError as e:
            pytest.fail(f"Non-ASCII character in aud manual --list: {e}")

    @pytest.mark.parametrize("concept", list(EXPLANATIONS.keys()))
    def test_manual_concepts_ascii(self, runner, concept):
        """Test each manual concept contains only ASCII characters."""
        result = runner.invoke(cli, ["manual", concept])
        assert result.exit_code == 0
        try:
            result.output.encode("ascii")
        except UnicodeEncodeError as e:
            pytest.fail(f"Non-ASCII character in aud manual {concept}: {e}")

    def test_explanations_dict_ascii(self):
        """Test EXPLANATIONS dict values are all ASCII."""
        for concept, info in EXPLANATIONS.items():
            for field in ["title", "summary", "explanation"]:
                try:
                    info[field].encode("ascii")
                except UnicodeEncodeError as e:
                    pytest.fail(f"Non-ASCII in EXPLANATIONS['{concept}']['{field}']: {e}")


class TestHelpLineCount:
    """Ensure help outputs stay within reasonable limits."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_root_help_under_150_lines(self, runner):
        """Test aud --help is under 150 lines."""
        result = runner.invoke(cli, ["--help"])
        line_count = len(result.output.splitlines())
        assert line_count < 150, f"aud --help is {line_count} lines (target: <150)"

    def test_query_help_under_200_lines(self, runner):
        """Test aud query --help is under 200 lines."""
        result = runner.invoke(cli, ["query", "--help"])
        line_count = len(result.output.splitlines())
        assert line_count < 200, f"aud query --help is {line_count} lines (target: <200)"

    def test_explain_help_under_150_lines(self, runner):
        """Test aud explain --help is under 150 lines."""
        result = runner.invoke(cli, ["explain", "--help"])
        line_count = len(result.output.splitlines())
        assert line_count < 150, f"aud explain --help is {line_count} lines (target: <150)"
