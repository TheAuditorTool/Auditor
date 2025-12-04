"""Integration tests for blueprint command."""

from click.testing import CliRunner

from theauditor.cli import cli


def test_blueprint_command_help():
    """Test help text is displayed correctly."""
    runner = CliRunner()
    result = runner.invoke(cli, ["blueprint", "--help"])
    assert result.exit_code == 0
    assert "architectural" in result.output.lower() or "blueprint" in result.output.lower()


def test_blueprint_command_options():
    """Test that all drill-down options are present."""
    runner = CliRunner()
    result = runner.invoke(cli, ["blueprint", "--help"])
    assert "--structure" in result.output
    assert "--graph" in result.output
    assert "--security" in result.output
    assert "--taint" in result.output
    assert "--boundaries" in result.output
    assert "--deps" in result.output
    assert "--fce" in result.output
    assert "--format" in result.output
    assert "--all" in result.output


def test_blueprint_command_fce_option_help():
    """Test --fce option is documented."""
    runner = CliRunner()
    result = runner.invoke(cli, ["blueprint", "--help"])
    assert "--fce" in result.output
    assert "convergence" in result.output.lower() or "FCE" in result.output
