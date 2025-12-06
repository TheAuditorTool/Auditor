"""Integration tests for explain command."""

from click.testing import CliRunner

from theauditor.cli import cli


def test_explain_command_help():
    """Test help text is displayed correctly."""
    runner = CliRunner()
    result = runner.invoke(cli, ["explain", "--help"])
    assert result.exit_code == 0
    assert "comprehensive context" in result.output.lower()
    assert "TARGET" in result.output


def test_explain_command_options():
    """Test that all options are present."""
    runner = CliRunner()
    result = runner.invoke(cli, ["explain", "--help"])
    assert "--depth" in result.output
    assert "--format" in result.output
    assert "--section" in result.output
    assert "--no-code" in result.output
    assert "--limit" in result.output
    assert "--fce" in result.output


def test_explain_command_fce_option_help():
    """Test --fce option is documented."""
    runner = CliRunner()
    result = runner.invoke(cli, ["explain", "--help"])
    assert "--fce" in result.output
    assert "FCE" in result.output or "convergence" in result.output.lower()
