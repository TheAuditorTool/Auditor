"""Tests for mypy dynamic config generation (Issue #30).

Tests the three fixes:
1. Auto-detect python_version from requires-python
2. Auto-detect mypy plugins from frameworks table
3. Filter external paths (typeshed/system Python) from findings
"""

import sqlite3

import pytest

from theauditor.indexer.database.base_database import BaseDatabaseManager
from theauditor.linters.config_generator import ConfigGenerator


@pytest.fixture
def temp_project(tmp_path):
    """Create temporary project structure with database."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Create .pf directory
    pf_dir = project_root / ".pf"
    pf_dir.mkdir()

    # Create database
    db_path = pf_dir / "repo_index.db"
    conn = sqlite3.connect(str(db_path))

    # Create frameworks table
    conn.execute("""
        CREATE TABLE frameworks (
            id INTEGER NOT NULL PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT,
            language TEXT NOT NULL,
            path TEXT DEFAULT '.',
            source TEXT,
            package_manager TEXT,
            is_primary BOOLEAN DEFAULT 0,
            UNIQUE(name, language, path)
        )
    """)

    # Create files table (for FK constraint)
    conn.execute("""
        CREATE TABLE files (
            path TEXT PRIMARY KEY,
            ext TEXT,
            file_category TEXT
        )
    """)

    # Create findings_consolidated table
    conn.execute("""
        CREATE TABLE findings_consolidated (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT NOT NULL,
            line INTEGER,
            column INTEGER,
            rule TEXT,
            tool TEXT,
            message TEXT,
            severity TEXT,
            category TEXT,
            confidence TEXT,
            code_snippet TEXT,
            cwe TEXT,
            timestamp TEXT,
            cfg_function TEXT,
            cfg_complexity INTEGER,
            cfg_block_count INTEGER,
            cfg_edge_count INTEGER,
            cfg_has_loops BOOLEAN,
            cfg_has_recursion BOOLEAN,
            cfg_start_line INTEGER,
            cfg_end_line INTEGER,
            cfg_threshold INTEGER,
            graph_id TEXT,
            graph_in_degree INTEGER,
            graph_out_degree INTEGER,
            graph_total_connections INTEGER,
            graph_centrality REAL,
            graph_score REAL,
            graph_cycle_nodes TEXT,
            mypy_error_code TEXT,
            mypy_severity_int TEXT,
            mypy_column INTEGER,
            tf_finding_id TEXT,
            tf_resource_id TEXT,
            tf_remediation TEXT,
            tf_graph_context TEXT,
            FOREIGN KEY (file) REFERENCES files(path)
        )
    """)

    conn.commit()
    conn.close()

    return project_root


class TestPythonVersionDetection:
    """Test _detect_python_version() method."""

    def test_detects_simple_version(self, temp_project):
        """Test detection of simple version spec like '>=3.12'."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
requires-python = ">=3.12"
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            version = gen._detect_python_version()

        assert version == "3.12"

    def test_detects_range_version(self, temp_project):
        """Test detection of range spec like '>=3.8,<4.0'."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
requires-python = ">=3.8,<4.0"
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            version = gen._detect_python_version()

        assert version == "3.8"

    def test_detects_exact_version(self, temp_project):
        """Test detection of exact version like '3.14'."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
requires-python = "3.14"
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            version = gen._detect_python_version()

        assert version == "3.14"

    def test_fallback_to_runtime_when_no_pyproject(self, temp_project):
        """Test fallback to runtime Python version when no pyproject.toml."""
        import sys

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            version = gen._detect_python_version()

        expected = f"{sys.version_info.major}.{sys.version_info.minor}"
        assert version == expected

    def test_fallback_when_no_requires_python(self, temp_project):
        """Test fallback when pyproject.toml exists but no requires-python."""
        import sys

        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            version = gen._detect_python_version()

        expected = f"{sys.version_info.major}.{sys.version_info.minor}"
        assert version == expected


class TestPluginDetection:
    """Test _detect_required_plugins_from_db() method."""

    def test_detects_pydantic_plugin(self, temp_project):
        """Test detection of pydantic framework -> pydantic.mypy plugin."""
        db_path = temp_project / ".pf" / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('pydantic', 'python')"
        )
        conn.commit()
        conn.close()

        with ConfigGenerator(temp_project, db_path) as gen:
            plugins = gen._detect_required_plugins_from_db()

        assert "pydantic.mypy" in plugins

    def test_detects_django_plugin(self, temp_project):
        """Test detection of django framework -> mypy_django_plugin.main."""
        db_path = temp_project / ".pf" / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('django', 'python')"
        )
        conn.commit()
        conn.close()

        with ConfigGenerator(temp_project, db_path) as gen:
            plugins = gen._detect_required_plugins_from_db()

        assert "mypy_django_plugin.main" in plugins

    def test_detects_sqlalchemy_plugin(self, temp_project):
        """Test detection of sqlalchemy framework -> sqlalchemy.ext.mypy.plugin."""
        db_path = temp_project / ".pf" / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('sqlalchemy', 'python')"
        )
        conn.commit()
        conn.close()

        with ConfigGenerator(temp_project, db_path) as gen:
            plugins = gen._detect_required_plugins_from_db()

        assert "sqlalchemy.ext.mypy.plugin" in plugins

    def test_detects_multiple_plugins(self, temp_project):
        """Test detection of multiple frameworks -> multiple plugins."""
        db_path = temp_project / ".pf" / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('pydantic', 'python')"
        )
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('django', 'python')"
        )
        conn.commit()
        conn.close()

        with ConfigGenerator(temp_project, db_path) as gen:
            plugins = gen._detect_required_plugins_from_db()

        assert "pydantic.mypy" in plugins
        assert "mypy_django_plugin.main" in plugins
        assert len(plugins) == 2

    def test_ignores_non_python_frameworks(self, temp_project):
        """Test that non-Python frameworks are ignored."""
        db_path = temp_project / ".pf" / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('react', 'javascript')"
        )
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('pydantic', 'python')"
        )
        conn.commit()
        conn.close()

        with ConfigGenerator(temp_project, db_path) as gen:
            plugins = gen._detect_required_plugins_from_db()

        assert "pydantic.mypy" in plugins
        assert len(plugins) == 1

    def test_ignores_unmapped_frameworks(self, temp_project):
        """Test that frameworks without mypy plugins are ignored."""
        db_path = temp_project / ".pf" / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('fastapi', 'python')"
        )
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('pytest', 'python')"
        )
        conn.commit()
        conn.close()

        with ConfigGenerator(temp_project, db_path) as gen:
            plugins = gen._detect_required_plugins_from_db()

        assert len(plugins) == 0

    def test_empty_database_returns_empty_list(self, temp_project):
        """Test that empty frameworks table returns empty plugin list."""
        db_path = temp_project / ".pf" / "repo_index.db"

        with ConfigGenerator(temp_project, db_path) as gen:
            plugins = gen._detect_required_plugins_from_db()

        assert plugins == []


class TestProjectConfigDetection:
    """Test _detect_project_python_config() method."""

    def test_detects_pyproject_with_mypy_section(self, temp_project):
        """Test detection of pyproject.toml with [tool.mypy] section."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[tool.mypy]
python_version = "3.12"
strict = true
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            config = gen._detect_project_python_config()

        assert config == pyproject

    def test_ignores_pyproject_without_mypy_section(self, temp_project):
        """Test that pyproject.toml without [tool.mypy] is ignored."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"

[tool.ruff]
line-length = 100
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            config = gen._detect_project_python_config()

        assert config is None

    def test_detects_mypy_ini(self, temp_project):
        """Test detection of mypy.ini file."""
        mypy_ini = temp_project / "mypy.ini"
        mypy_ini.write_text("""
[mypy]
python_version = 3.12
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            config = gen._detect_project_python_config()

        assert config == mypy_ini

    def test_detects_dot_mypy_ini(self, temp_project):
        """Test detection of .mypy.ini file."""
        mypy_ini = temp_project / ".mypy.ini"
        mypy_ini.write_text("""
[mypy]
python_version = 3.12
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            config = gen._detect_project_python_config()

        assert config == mypy_ini

    def test_returns_none_when_no_config_exists(self, temp_project):
        """Test returns None when no config files exist."""
        db_path = temp_project / ".pf" / "repo_index.db"

        with ConfigGenerator(temp_project, db_path) as gen:
            config = gen._detect_project_python_config()

        assert config is None


class TestConfigGeneration:
    """Test generate_python_config() end-to-end."""

    def test_generates_config_with_detected_version(self, temp_project):
        """Test generated config includes auto-detected python_version."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
requires-python = ">=3.12"
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            config_path = gen.generate_python_config()

        config_content = config_path.read_text()
        assert "python_version = 3.12" in config_content

    def test_generates_config_with_detected_plugins(self, temp_project):
        """Test generated config includes auto-detected plugins."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
requires-python = ">=3.12"
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('pydantic', 'python')"
        )
        conn.execute(
            "INSERT INTO frameworks (name, language) VALUES ('django', 'python')"
        )
        conn.commit()
        conn.close()

        with ConfigGenerator(temp_project, db_path) as gen:
            config_path = gen.generate_python_config()

        config_content = config_path.read_text()
        # Check both plugins are present (order may vary based on DB query)
        assert "pydantic.mypy" in config_content
        assert "mypy_django_plugin.main" in config_content
        assert "plugins =" in config_content

    def test_generates_config_without_plugins_when_none_detected(self, temp_project):
        """Test generated config has no plugins section when none detected."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
requires-python = ">=3.12"
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            config_path = gen.generate_python_config()

        config_content = config_path.read_text()
        assert "plugins" not in config_content

    def test_uses_existing_project_config_when_present(self, temp_project):
        """Test returns existing project config instead of generating."""
        project_mypy = temp_project / "mypy.ini"
        project_mypy.write_text("""
[mypy]
python_version = 3.10
warn_return_any = False
""")

        db_path = temp_project / ".pf" / "repo_index.db"
        with ConfigGenerator(temp_project, db_path) as gen:
            config_path = gen.generate_python_config()

        assert config_path == project_mypy

    def test_generated_config_has_strict_settings(self, temp_project):
        """Test generated config includes strict type checking settings."""
        db_path = temp_project / ".pf" / "repo_index.db"

        with ConfigGenerator(temp_project, db_path) as gen:
            config_path = gen.generate_python_config()

        config_content = config_path.read_text()
        assert "strict = True" in config_content
        assert "disallow_untyped_defs = True" in config_content
        assert "warn_return_any = True" in config_content

    def test_generated_config_has_output_formatting(self, temp_project):
        """Test generated config includes output formatting options."""
        db_path = temp_project / ".pf" / "repo_index.db"

        with ConfigGenerator(temp_project, db_path) as gen:
            config_path = gen.generate_python_config()

        config_content = config_path.read_text()
        assert "show_column_numbers = True" in config_content
        assert "show_error_codes = True" in config_content

    def test_generated_config_has_exclude_patterns(self, temp_project):
        """Test generated config includes exclude patterns."""
        db_path = temp_project / ".pf" / "repo_index.db"

        with ConfigGenerator(temp_project, db_path) as gen:
            config_path = gen.generate_python_config()

        config_content = config_path.read_text()
        assert ".pf" in config_content
        assert "__pycache__" in config_content

    def test_generated_config_in_temp_directory(self, temp_project):
        """Test generated config is placed in .pf/temp/ directory."""
        db_path = temp_project / ".pf" / "repo_index.db"

        with ConfigGenerator(temp_project, db_path) as gen:
            config_path = gen.generate_python_config()

        assert config_path.parent.name == "temp"
        assert config_path.name == "mypy.ini"


class TestExternalPathFiltering:
    """Test _is_external_path() method in BaseDatabaseManager."""

    def test_filters_typeshed_paths(self):
        """Test typeshed paths are identified as external."""
        assert BaseDatabaseManager._is_external_path("/typeshed/stdlib/builtins.pyi")
        assert BaseDatabaseManager._is_external_path(
            "C:\\Python\\Lib\\site-packages\\typeshed\\builtins.pyi"
        )
        assert BaseDatabaseManager._is_external_path("TYPESHED/stdlib/typing.pyi")

    def test_filters_unix_system_python(self):
        """Test Unix system Python paths are identified as external."""
        assert BaseDatabaseManager._is_external_path("/usr/lib/python3.12/typing.py")
        assert BaseDatabaseManager._is_external_path("/lib64/python3.12/asyncio.py")
        assert BaseDatabaseManager._is_external_path(
            "/usr/lib/python3.12/site-packages/pydantic/__init__.py"
        )

    def test_filters_windows_system_python(self):
        """Test Windows system Python paths are identified as external."""
        assert BaseDatabaseManager._is_external_path(
            "C:\\Python312\\lib\\site-packages\\typing.py"
        )
        assert BaseDatabaseManager._is_external_path(
            "C:\\Program Files\\Python\\lib\\site-packages\\pydantic\\__init__.py"
        )

    def test_filters_mypy_placeholders(self):
        """Test mypy placeholder paths are identified as external."""
        assert BaseDatabaseManager._is_external_path("<install>")
        assert BaseDatabaseManager._is_external_path("<string>")

    def test_allows_project_files(self):
        """Test project files are NOT identified as external."""
        assert not BaseDatabaseManager._is_external_path("src/main.py")
        assert not BaseDatabaseManager._is_external_path("app/models.py")
        assert not BaseDatabaseManager._is_external_path("tests/test_app.py")

    def test_filters_empty_paths(self):
        """Test empty paths are identified as external."""
        assert BaseDatabaseManager._is_external_path("")
        assert BaseDatabaseManager._is_external_path(None)


class TestFindingsFiltering:
    """Test write_findings_batch() filters external paths correctly."""

    def test_filters_typeshed_findings(self, temp_project):
        """Test findings from typeshed are filtered out."""
        db_path = temp_project / ".pf" / "repo_index.db"
        db_mgr = BaseDatabaseManager(str(db_path))

        # Add a valid file to files table
        conn = sqlite3.connect(str(db_path))
        conn.execute("INSERT INTO files (path, ext) VALUES ('src/main.py', '.py')")
        conn.commit()
        conn.close()

        findings = [
            {
                "file": "src/main.py",
                "line": 10,
                "rule": "name-defined",
                "tool": "mypy",
                "message": "Name 'foo' is not defined",
                "severity": "error",
            },
            {
                "file": "/typeshed/stdlib/builtins.pyi",
                "line": 100,
                "rule": "misc",
                "tool": "mypy",
                "message": "Type mismatch",
                "severity": "error",
            },
        ]

        db_mgr.write_findings_batch(findings, "mypy")

        # Verify only project file finding was inserted
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT file FROM findings_consolidated")
        results = cursor.fetchall()
        conn.close()

        assert len(results) == 1
        assert results[0][0] == "src/main.py"

    def test_filters_system_python_findings(self, temp_project):
        """Test findings from system Python are filtered out."""
        db_path = temp_project / ".pf" / "repo_index.db"
        db_mgr = BaseDatabaseManager(str(db_path))

        # Add a valid file to files table
        conn = sqlite3.connect(str(db_path))
        conn.execute("INSERT INTO files (path, ext) VALUES ('app/models.py', '.py')")
        conn.commit()
        conn.close()

        findings = [
            {
                "file": "app/models.py",
                "line": 5,
                "rule": "attr-defined",
                "tool": "mypy",
                "message": "Attribute not defined",
                "severity": "error",
            },
            {
                "file": "/usr/lib/python3.12/typing.py",
                "line": 500,
                "rule": "misc",
                "tool": "mypy",
                "message": "Type error",
                "severity": "error",
            },
        ]

        db_mgr.write_findings_batch(findings, "mypy")

        # Verify only project file finding was inserted
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT file FROM findings_consolidated")
        results = cursor.fetchall()
        conn.close()

        assert len(results) == 1
        assert results[0][0] == "app/models.py"

    def test_allows_project_findings(self, temp_project):
        """Test findings from project files are NOT filtered."""
        db_path = temp_project / ".pf" / "repo_index.db"
        db_mgr = BaseDatabaseManager(str(db_path))

        # Add valid files to files table
        conn = sqlite3.connect(str(db_path))
        conn.execute("INSERT INTO files (path, ext) VALUES ('src/main.py', '.py')")
        conn.execute("INSERT INTO files (path, ext) VALUES ('app/models.py', '.py')")
        conn.commit()
        conn.close()

        findings = [
            {
                "file": "src/main.py",
                "line": 10,
                "rule": "name-defined",
                "tool": "mypy",
                "message": "Error 1",
                "severity": "error",
            },
            {
                "file": "app/models.py",
                "line": 20,
                "rule": "attr-defined",
                "tool": "mypy",
                "message": "Error 2",
                "severity": "error",
            },
        ]

        db_mgr.write_findings_batch(findings, "mypy")

        # Verify both project findings were inserted
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT file FROM findings_consolidated ORDER BY file")
        results = cursor.fetchall()
        conn.close()

        assert len(results) == 2
        assert results[0][0] == "app/models.py"
        assert results[1][0] == "src/main.py"
