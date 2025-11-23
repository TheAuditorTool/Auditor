"""Integration tests for explain command."""

import pytest
from click.testing import CliRunner
from theauditor.commands.explain import explain, detect_target_type


class MockEngine:
    """Mock CodeQueryEngine for testing."""

    def get_component_tree(self, name):
        if name == "Dashboard":
            return {"name": "Dashboard", "type": "function"}
        return {"error": "not found"}


def test_detect_target_type_file_ts():
    """Test detection of TypeScript file."""
    assert detect_target_type("src/auth.ts", None) == 'file'


def test_detect_target_type_file_py():
    """Test detection of Python file."""
    assert detect_target_type("app.py", None) == 'file'


def test_detect_target_type_file_tsx():
    """Test detection of TSX file."""
    assert detect_target_type("components/Button.tsx", None) == 'file'


def test_detect_target_type_file_with_path():
    """Test detection of path-like patterns."""
    assert detect_target_type("src/utils/helpers", None) == 'file'


def test_detect_target_type_qualified_symbol():
    """Test detection of qualified symbol (Class.method)."""
    assert detect_target_type("UserController.create", None) == 'symbol'


def test_detect_target_type_simple_symbol():
    """Test detection of simple symbol."""
    engine = MockEngine()
    assert detect_target_type("authenticate", engine) == 'symbol'


def test_detect_target_type_component():
    """Test detection of React component."""
    engine = MockEngine()
    assert detect_target_type("Dashboard", engine) == 'component'


def test_explain_command_help():
    """Test help text is displayed correctly."""
    runner = CliRunner()
    result = runner.invoke(explain, ['--help'])
    assert result.exit_code == 0
    assert 'comprehensive context' in result.output.lower()
    assert 'TARGET' in result.output


def test_explain_command_options():
    """Test that all options are present."""
    runner = CliRunner()
    result = runner.invoke(explain, ['--help'])
    assert '--depth' in result.output
    assert '--format' in result.output
    assert '--section' in result.output
    assert '--no-code' in result.output
    assert '--limit' in result.output


def test_detect_target_type_vue():
    """Test detection of Vue file."""
    assert detect_target_type("components/Modal.vue", None) == 'file'


def test_detect_target_type_rust():
    """Test detection of Rust file."""
    assert detect_target_type("src/lib.rs", None) == 'file'


def test_detect_target_type_java():
    """Test detection of Java file."""
    assert detect_target_type("Main.java", None) == 'file'
