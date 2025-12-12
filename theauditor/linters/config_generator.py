"""Intelligent linter config generation based on project analysis.

Generates ESLint and TypeScript configs dynamically based on detected
frameworks and file types from the database. Respects existing project
configs when present.
"""

import json
import shutil
import sqlite3
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
