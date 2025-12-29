"""Intelligent linter config generation based on project analysis.

Generates ESLint and TypeScript configs dynamically based on detected
frameworks and file types from the database. Respects existing project
configs when present.
"""

import json
import re
import shutil
import sqlite3
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from theauditor.utils.logging import logger


@dataclass(slots=True)
class ConfigResult:
    """Result of config generation.

    Attributes:
        tsconfig_path: Path to tsconfig (generated or copied)
        eslint_config_path: Path to generated ESLint config (None if using project config)
        use_project_eslint: True if project has its own ESLint config
    """

    tsconfig_path: Path | None
    eslint_config_path: Path | None
    use_project_eslint: bool


# ESLint config file detection order (spec.md)
ESLINT_CONFIG_FILES = [
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    "eslint.config.ts",
    "eslint.config.mts",
    "eslint.config.cts",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.yaml",
    ".eslintrc.yml",
    ".eslintrc.json",
    ".eslintrc",
]

# Python config file detection order
PYTHON_CONFIG_FILES = [
    "pyproject.toml",
    "mypy.ini",
    ".mypy.ini",
    "setup.cfg",
]

# Framework to mypy plugin mapping
MYPY_PLUGIN_MAP = {
    "pydantic": "pydantic.mypy",
    "django": "mypy_django_plugin.main",
    "sqlalchemy": "sqlalchemy.ext.mypy.plugin",
}


class ConfigGenerator:
    """Generates intelligent linter configs based on project analysis.

    Queries the database for detected frameworks and file extensions,
    then generates appropriate ESLint and TypeScript configurations.
    Respects existing project configs when present.
    """

    def __init__(self, root: Path, db_path: Path):
        """Initialize with project root and database path.

        Args:
            root: Project root directory
            db_path: Path to repo_index.db

        Raises:
            RuntimeError: If database does not exist
        """
        self.root = Path(root).resolve()
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            raise RuntimeError(f"Database required for config generation: {db_path}")

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        self.temp_dir = self.root / ".pf" / "temp"

    def _query_frameworks(self) -> list[dict]:
        """Query frameworks table for detected frameworks.

        Returns:
            List of dicts with name, version, language keys
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, version, language FROM frameworks")
        return [dict(row) for row in cursor.fetchall()]

    def _query_file_extensions(self) -> dict[str, int]:
        """Query files table for extension counts.

        Returns:
            Dict mapping extension to count (e.g., {".ts": 150, ".tsx": 45})
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT ext, COUNT(*) as count FROM files "
            "WHERE file_category='source' GROUP BY ext"
        )
        return {row["ext"]: row["count"] for row in cursor.fetchall()}

    def _detect_project_eslint_config(self) -> Path | None:
        """Detect existing ESLint config in project root.

        Checks for config files in order specified by spec.md.
        First match wins.

        Returns:
            Path to project ESLint config, or None if not found
        """
        for config_name in ESLINT_CONFIG_FILES:
            config_path = self.root / config_name
            if config_path.exists():
                logger.debug(f"Found project ESLint config: {config_path}")
                return config_path
        return None

    def _detect_project_tsconfig(self) -> Path | None:
        """Detect existing tsconfig.json in project root.

        Returns:
            Path to project tsconfig.json, or None if not found
        """
        tsconfig_path = self.root / "tsconfig.json"
        if tsconfig_path.exists():
            logger.debug(f"Found project tsconfig: {tsconfig_path}")
            return tsconfig_path
        return None

    def _detect_project_python_config(self) -> Path | None:
        """Detect existing Python/mypy config in project root.

        Checks for config files in order: pyproject.toml (with [tool.mypy]),
        mypy.ini, .mypy.ini, setup.cfg.

        Returns:
            Path to project Python config, or None if not found
        """
        for config_name in PYTHON_CONFIG_FILES:
            config_path = self.root / config_name
            if not config_path.exists():
                continue

            if config_name == "pyproject.toml":
                try:
                    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
                    if "mypy" in data.get("tool", {}):
                        logger.debug(f"Found project mypy config in: {config_path}")
                        return config_path
                except Exception as e:
                    logger.warning(f"Failed to parse {config_path}: {e}")
                    continue
            elif "mypy" in config_name or config_name == "setup.cfg":
                logger.debug(f"Found project mypy config: {config_path}")
                return config_path

        return None

    def _detect_python_version(self) -> str:
        """Detect Python version from project's pyproject.toml.

        Uses requires-python field to extract minimum version.
        Falls back to runtime Python version if not specified.

        Returns:
            Python version string (e.g., "3.12")
        """
        pyproject = self.root / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                requires = data.get("project", {}).get("requires-python", "")

                # Extract version from spec like ">=3.12", ">=3.8,<4.0", etc.
                version_match = re.search(r"(\d+\.\d+)", requires)
                if version_match:
                    version = version_match.group(1)
                    logger.debug(f"Detected Python version from requires-python: {version}")
                    return version
            except Exception as e:
                logger.warning(f"Failed to parse {pyproject}: {e}")

        # Fallback to runtime Python version
        runtime_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        logger.debug(f"Using runtime Python version: {runtime_version}")
        return runtime_version

    def _detect_required_plugins_from_db(self) -> list[str]:
        """Query frameworks table for detected Python frameworks.

        Maps detected frameworks to their corresponding mypy plugins.

        Returns:
            List of mypy plugin import paths (e.g., ["pydantic.mypy"])
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT name FROM frameworks WHERE language = 'python'")

        plugins = []
        for row in cursor.fetchall():
            framework_name = row["name"].lower()
            if framework_name in MYPY_PLUGIN_MAP:
                plugin = MYPY_PLUGIN_MAP[framework_name]
                plugins.append(plugin)
                logger.debug(f"Detected framework '{framework_name}' -> plugin '{plugin}'")

        return plugins

    def generate_python_config(self, force_strict: bool = False) -> Path:
        """Generate mypy config for Python linting.

        Detects project Python version and required plugins, then generates
        a mypy.ini config file in temp directory.

        Args:
            force_strict: If True, ignores project config and generates strict defaults.

        Returns:
            Path to generated mypy.ini file

        Raises:
            RuntimeError: If config generation fails
        """
        # Check for existing project config first (unless forcing strict config)
        if not force_strict:
            project_config = self._detect_project_python_config()
            if project_config:
                logger.info(f"Using project mypy config: {project_config}")
                return project_config

        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Detect Python version and plugins
        python_version = self._detect_python_version()
        plugins = self._detect_required_plugins_from_db()

        # Generate mypy.ini content
        config_lines = [
            "[mypy]",
            f"python_version = {python_version}",
            "",
            "# Strict type checking",
            "strict = True",
            "disallow_untyped_defs = True",
            "disallow_any_unimported = True",
            "no_implicit_optional = True",
            "check_untyped_defs = True",
            "warn_return_any = True",
            "warn_unused_configs = True",
            "warn_redundant_casts = True",
            "warn_unused_ignores = True",
            "warn_no_return = True",
            "warn_unreachable = True",
            "strict_optional = True",
            "strict_equality = True",
            "",
            "# Output formatting",
            "no_pretty = True",
            "show_column_numbers = True",
            "show_error_codes = True",
            "show_error_context = True",
            "",
        ]

        # Add plugins if detected
        if plugins:
            plugins_str = ", ".join(plugins)
            config_lines.append(f"plugins = {plugins_str}")
            config_lines.append("")

        # Add exclude patterns
        config_lines.extend([
            "# Exclude patterns",
            "exclude = (?x)(",
            "    \\.pf",
            "    | \\.auditor_venv",
            "    | __pycache__",
            "    | \\.eggs",
            "    | build",
            "    | dist",
            ")",
        ])

        config_content = "\n".join(config_lines)

        # Write config file
        config_path = self.temp_dir / "mypy.ini"
        config_path.write_text(config_content, encoding="utf-8")
        logger.info(f"Generated mypy config at {config_path}")

        return config_path

    def _generate_tsconfig(self, frameworks: list[dict], extensions: dict[str, int]) -> str:
        """Generate tsconfig.json content based on project analysis.

        Args:
            frameworks: List of detected frameworks
            extensions: Dict of file extension counts

        Returns:
            JSON string for tsconfig.json
        """
        has_react = any(f["name"] == "react" for f in frameworks)
        has_node = any(f["name"] in ("express", "fastify", "node") for f in frameworks)
        has_tsx = ".tsx" in extensions
        has_ts = ".ts" in extensions

        config: dict = {
            "compilerOptions": {
                "target": "ES2020",
                "module": "NodeNext" if has_node else "ESNext",
                "moduleResolution": "NodeNext" if has_node else "Bundler",
                "strict": True,
                "esModuleInterop": True,
                "skipLibCheck": True,
            },
            "include": [],
            "exclude": ["node_modules", "dist", "build", ".pf"],
        }

        # Add JSX support for React
        if has_react:
            config["compilerOptions"]["jsx"] = "react-jsx"
            config["compilerOptions"]["lib"] = ["ES2020", "DOM"]
        elif has_node:
            config["compilerOptions"]["types"] = ["node"]

        # Build include patterns based on actual files
        if has_ts:
            config["include"].append("**/*.ts")
        if has_tsx:
            config["include"].append("**/*.tsx")

        # Default if no TS files found (shouldn't happen, but safe)
        if not config["include"]:
            config["include"] = ["**/*.ts", "**/*.tsx"]

        return json.dumps(config, indent=2)

    def _generate_eslint_config(
        self, frameworks: list[dict], extensions: dict[str, int], tsconfig_path: Path
    ) -> str:
        """Generate ESLint config content based on project analysis.

        Uses string concatenation of config blocks per design.md.

        Args:
            frameworks: List of detected frameworks
            extensions: Dict of file extension counts
            tsconfig_path: Path to tsconfig.json (for parserOptions.project)

        Returns:
            JavaScript string for eslint.config.cjs
        """
        has_ts = ".ts" in extensions or ".tsx" in extensions
        has_react = any(f["name"] == "react" for f in frameworks)
        has_node = any(f["name"] in ("express", "fastify", "node") for f in frameworks)

        parts = []

        # Header with imports
        parts.append('const globals = require("globals");')
        parts.append('const js = require("@eslint/js");')

        if has_ts:
            parts.append('const typescript = require("@typescript-eslint/eslint-plugin");')
            parts.append('const typescriptParser = require("@typescript-eslint/parser");')

        if has_react:
            parts.append('const reactHooks = require("eslint-plugin-react-hooks");')

        parts.append("")  # Blank line

        # Module exports start
        parts.append("module.exports = [")
        parts.append("  js.configs.recommended,")
        parts.append("  { ignores: [")
        parts.append('    "node_modules/**",')
        parts.append('    "dist/**",')
        parts.append('    "build/**",')
        parts.append('    ".pf/**",')
        parts.append("  ] },")

        # TypeScript block
        if has_ts:
            # Use relative path from .pf/temp/ to project root for tsconfig
            parts.append("  {")
            parts.append('    files: ["**/*.ts", "**/*.tsx"],')
            parts.append("    languageOptions: {")
            parts.append("      parser: typescriptParser,")
            parts.append("      parserOptions: {")
            parts.append('        project: "./tsconfig.json",')
            parts.append("        tsconfigRootDir: __dirname,")
            parts.append("      },")
            parts.append("    },")
            parts.append('    plugins: { "@typescript-eslint": typescript },')
            parts.append("    rules: {")
            parts.append('      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],')
            parts.append('      "@typescript-eslint/no-explicit-any": "error",')
            parts.append('      "@typescript-eslint/explicit-function-return-type": "warn",')
            parts.append("    },")
            parts.append("  },")

        # React block
        if has_react:
            parts.append("  {")
            parts.append('    files: ["**/*.jsx", "**/*.tsx"],')
            parts.append('    plugins: { "react-hooks": reactHooks },')
            parts.append("    rules: {")
            parts.append('      "react-hooks/rules-of-hooks": "error",')
            parts.append('      "react-hooks/exhaustive-deps": "warn",')
            parts.append("    },")
            parts.append("  },")

        # Globals block - Node or Browser
        if has_node:
            parts.append("  {")
            parts.append('    files: ["**/*.js", "**/*.ts"],')
            parts.append("    languageOptions: { globals: globals.node },")
            parts.append("  },")
        elif has_react:
            parts.append("  {")
            parts.append('    files: ["**/*.jsx", "**/*.tsx"],')
            parts.append("    languageOptions: { globals: globals.browser },")
            parts.append("  },")

        # Close module.exports
        parts.append("];")

        return "\n".join(parts)

    def prepare_configs(self) -> ConfigResult:
        """Prepare ESLint and TypeScript configs for linting.

        Main entry point. Detects existing project configs and generates
        missing ones based on framework/file analysis.

        Returns:
            ConfigResult with paths and flags for config usage
        """
        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Query database for project analysis
        frameworks = self._query_frameworks()
        extensions = self._query_file_extensions()

        logger.debug(f"Detected frameworks: {[f['name'] for f in frameworks]}")
        logger.debug(f"File extensions: {extensions}")

        # Check for TypeScript files
        has_typescript = ".ts" in extensions or ".tsx" in extensions

        # Handle tsconfig
        tsconfig_path: Path | None = None
        project_tsconfig = self._detect_project_tsconfig()

        if project_tsconfig:
            # Copy project tsconfig to temp dir
            tsconfig_path = self.temp_dir / "tsconfig.json"
            shutil.copy2(project_tsconfig, tsconfig_path)
            logger.info(f"Copied project tsconfig to {tsconfig_path}")
        elif has_typescript:
            # Generate tsconfig
            tsconfig_path = self.temp_dir / "tsconfig.json"
            tsconfig_content = self._generate_tsconfig(frameworks, extensions)
            tsconfig_path.write_text(tsconfig_content, encoding="utf-8")
            logger.info(f"Generated tsconfig at {tsconfig_path}")

        # Handle ESLint config
        project_eslint = self._detect_project_eslint_config()

        if project_eslint:
            # Use project's ESLint config (omit --config flag)
            logger.info(f"Using project ESLint config: {project_eslint}")
            return ConfigResult(
                tsconfig_path=tsconfig_path,
                eslint_config_path=None,
                use_project_eslint=True,
            )

        # Generate ESLint config
        eslint_config_path = self.temp_dir / "eslint.config.cjs"

        if tsconfig_path:
            eslint_content = self._generate_eslint_config(frameworks, extensions, tsconfig_path)
        else:
            # No TypeScript - generate minimal config
            eslint_content = self._generate_eslint_config(frameworks, extensions, self.temp_dir)

        eslint_config_path.write_text(eslint_content, encoding="utf-8")
        logger.info(f"Generated ESLint config at {eslint_config_path}")

        return ConfigResult(
            tsconfig_path=tsconfig_path,
            eslint_config_path=eslint_config_path,
            use_project_eslint=False,
        )

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self) -> ConfigGenerator:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close connection."""
        self.close()
