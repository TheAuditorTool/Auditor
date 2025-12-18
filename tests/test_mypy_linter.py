"""Tests for MypyLinter project config detection.

Tests the _find_project_mypy_config() method which should detect and prefer
project-level mypy configuration over TheAuditor's bundled defaults.

Issue: https://github.com/TheAuditorTool/Auditor/issues/30
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from theauditor.linters.mypy import MypyLinter
from theauditor.utils.toolbox import Toolbox


@pytest.fixture
def mock_toolbox(tmp_path):
    """Create a mock toolbox pointing to tmp_path."""
    toolbox = MagicMock(spec=Toolbox)
    toolbox.sandbox = tmp_path / ".auditor_venv" / ".theauditor_tools"
    toolbox.sandbox.mkdir(parents=True, exist_ok=True)
    return toolbox


@pytest.fixture
def mypy_linter(mock_toolbox, tmp_path):
    """Create MypyLinter instance with mocked toolbox."""
    linter = MypyLinter(mock_toolbox, tmp_path)
    return linter


class TestFindProjectMypyConfig:
    """Tests for _find_project_mypy_config() method."""

    def test_finds_pyproject_toml_with_tool_mypy(self, mypy_linter, tmp_path):
        """Should detect pyproject.toml containing [tool.mypy] section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.mypy]
python_version = "3.14"
strict = true
""")
        result = mypy_linter._find_project_mypy_config()
        assert result == str(pyproject)

    def test_ignores_pyproject_toml_without_tool_mypy(self, mypy_linter, tmp_path):
        """Should return None if pyproject.toml exists but has no [tool.mypy]."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.ruff]
line-length = 100
""")
        result = mypy_linter._find_project_mypy_config()
        assert result is None

    def test_finds_mypy_ini(self, mypy_linter, tmp_path):
        """Should detect mypy.ini config file."""
        mypy_ini = tmp_path / "mypy.ini"
        mypy_ini.write_text("""
[mypy]
python_version = 3.14
strict = True
""")
        result = mypy_linter._find_project_mypy_config()
        assert result == str(mypy_ini)

    def test_finds_dot_mypy_ini(self, mypy_linter, tmp_path):
        """Should detect .mypy.ini config file."""
        dot_mypy_ini = tmp_path / ".mypy.ini"
        dot_mypy_ini.write_text("""
[mypy]
python_version = 3.14
""")
        result = mypy_linter._find_project_mypy_config()
        assert result == str(dot_mypy_ini)

    def test_finds_setup_cfg_with_mypy_section(self, mypy_linter, tmp_path):
        """Should detect setup.cfg containing [mypy] section."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""
[metadata]
name = test

[mypy]
python_version = 3.14
""")
        result = mypy_linter._find_project_mypy_config()
        assert result == str(setup_cfg)

    def test_ignores_setup_cfg_without_mypy_section(self, mypy_linter, tmp_path):
        """Should return None if setup.cfg exists but has no [mypy] section."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""
[metadata]
name = test

[options]
packages = find:
""")
        result = mypy_linter._find_project_mypy_config()
        assert result is None

    def test_returns_none_when_no_config_exists(self, mypy_linter, tmp_path):
        """Should return None when no mypy config exists in project."""
        result = mypy_linter._find_project_mypy_config()
        assert result is None

    def test_prefers_mypy_ini_over_pyproject_toml(self, mypy_linter, tmp_path):
        """mypy.ini should take precedence over pyproject.toml."""
        # Create both config files
        mypy_ini = tmp_path / "mypy.ini"
        mypy_ini.write_text("[mypy]\npython_version = 3.14\n")

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.mypy]\npython_version = \"3.11\"\n")

        result = mypy_linter._find_project_mypy_config()
        assert result == str(mypy_ini)

    def test_prefers_dot_mypy_ini_over_setup_cfg(self, mypy_linter, tmp_path):
        """.mypy.ini should take precedence over setup.cfg."""
        dot_mypy_ini = tmp_path / ".mypy.ini"
        dot_mypy_ini.write_text("[mypy]\npython_version = 3.14\n")

        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("[mypy]\npython_version = 3.11\n")

        result = mypy_linter._find_project_mypy_config()
        assert result == str(dot_mypy_ini)


class TestMypyLinterConfigSelection:
    """Tests verifying config selection logic in run() method setup."""

    def test_uses_project_config_when_available(self, mock_toolbox, tmp_path):
        """Should use project's mypy config instead of TheAuditor's default."""
        # Create project config
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.mypy]\npython_version = \"3.14\"\n")

        # Create TheAuditor's default config
        default_config = mock_toolbox.sandbox / "pyproject.toml"
        default_config.write_text("[tool.mypy]\npython_version = \"3.11\"\n")
        mock_toolbox.get_python_linter_config.return_value = default_config

        linter = MypyLinter(mock_toolbox, tmp_path)

        # Verify it finds project config
        found_config = linter._find_project_mypy_config()
        assert found_config == str(pyproject)

    def test_falls_back_to_default_when_no_project_config(self, mock_toolbox, tmp_path):
        """Should use TheAuditor's default config when project has none."""
        # Create only TheAuditor's default config
        default_config = mock_toolbox.sandbox / "pyproject.toml"
        default_config.write_text("[tool.mypy]\npython_version = \"3.11\"\n")
        mock_toolbox.get_python_linter_config.return_value = default_config

        linter = MypyLinter(mock_toolbox, tmp_path)

        # Verify no project config found
        found_config = linter._find_project_mypy_config()
        assert found_config is None
