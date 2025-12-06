"""Module resolution for TypeScript/JavaScript projects with tsconfig.json support."""

import json
import re
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

try:
    import json5

    HAS_JSON5 = True
except ImportError:
    HAS_JSON5 = False


class ModuleResolver:
    """Resolves module imports for TypeScript/JavaScript projects."""

    def __init__(self, project_root: str | None = None, db_path: str = ".pf/repo_index.db"):
        """Initialize resolver with database path."""
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.db_path = Path(db_path)
        self.configs_by_context: dict[str, Any] = {}
        self.path_mappings_by_context: dict[str, dict[str, list[str]]] = {}

        self.base_url: str | None = None
        self.path_mappings: dict[str, list[str]] = {}

        self._load_all_configs_from_db()

    def _load_all_configs_from_db(self) -> None:
        """Load ALL tsconfig files from database and organize by context."""
        if not self.db_path.exists():
            return

        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT path, content, context_dir
                FROM config_files
                WHERE type = 'tsconfig'
            """)
            configs = cursor.fetchall()
        except sqlite3.OperationalError:
            conn.close()
            return
        finally:
            if conn:
                conn.close()

        for path, content, context_dir in configs:
            config = self._parse_tsconfig(content, path)
            if config is None:
                continue

            if context_dir is None:
                if config.get("references"):
                    continue
                context_dir = "root"

            self.configs_by_context[context_dir] = config
            mappings = self._extract_path_mappings(config, context_dir)
            self.path_mappings_by_context[context_dir] = mappings

            if not self.path_mappings and mappings:
                self.path_mappings = mappings
                self.base_url = config.get("compilerOptions", {}).get("baseUrl", ".")

    def _parse_tsconfig(self, content: str, path: str) -> dict | None:
        """Parse tsconfig content, handling JSON5 comments."""
        if HAS_JSON5:
            try:
                return json5.loads(content)
            except Exception as e:
                logger.debug(f"json5 failed to parse {path}: {e}")
                return None

        lines = content.split("\n")
        cleaned_lines = []
        for line in lines:
            comment_pos = line.find("//")
            if comment_pos >= 0:
                before_comment = line[:comment_pos]

                if before_comment.count('"') % 2 == 0:
                    line = before_comment
            cleaned_lines.append(line)
        content = "\n".join(cleaned_lines)

        if "/*" in content and "*/" in content:
            content = re.sub(r"(?<!@)/\*.*?\*/", "", content, flags=re.DOTALL)

        content = re.sub(r",(\s*[}\]])", r"\1", content)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse {path}: {e}")
            return None

    def _extract_path_mappings(self, config: dict, context_dir: str) -> dict[str, list[str]]:
        """Extract path mappings from tsconfig compilerOptions."""
        compiler_opts = config.get("compilerOptions", {})
        base_url = compiler_opts.get("baseUrl", ".")
        paths = compiler_opts.get("paths", {})

        mappings = {}
        for alias_pattern, targets in paths.items():
            normalized_alias = alias_pattern.rstrip("*")
            normalized_targets = []

            for target in targets:
                target = target.rstrip("*")

                if context_dir == "backend" and base_url == "./src":
                    full_target = f"{context_dir}/src/{target}"
                elif context_dir == "frontend" and base_url == ".":
                    if target.startswith("./"):
                        target = target[2:]
                    full_target = f"{context_dir}/{target}"
                else:
                    full_target = target

                normalized_targets.append(full_target)

            mappings[normalized_alias] = normalized_targets
            logger.debug(
                f"{normalized_alias} -> {normalized_targets[0] if normalized_targets else 'None'}"
            )

        return mappings

    def _to_relative_path(self, absolute_path: Path) -> str:
        """Convert absolute path to relative, with forward slashes."""
        try:
            return str(absolute_path.relative_to(self.project_root)).replace("\\", "/")
        except ValueError:
            return str(absolute_path).replace("\\", "/")

    def resolve(self, import_path: str, containing_file_path: str) -> str:
        """Resolve an import path to its actual file location."""

        if import_path.startswith("."):
            return import_path

        for alias_prefix, target_patterns in self.path_mappings.items():
            if not import_path.startswith(alias_prefix):
                continue

            suffix = import_path[len(alias_prefix) :]

            for target_pattern in target_patterns:
                if self.base_url:
                    base_path = self.project_root / self.base_url
                    resolved_path = base_path / target_pattern / suffix
                else:
                    resolved_path = self.project_root / target_pattern / suffix

                if not resolved_path.suffix:
                    for ext in [".ts", ".tsx", ".js", ".jsx", ".d.ts"]:
                        test_path = resolved_path.with_suffix(ext)
                        if test_path.exists():
                            return self._to_relative_path(test_path)

                    for index_name in ["index.ts", "index.tsx", "index.js", "index.jsx"]:
                        test_path = resolved_path / index_name
                        if test_path.exists():
                            return self._to_relative_path(test_path)

                if resolved_path.exists():
                    return self._to_relative_path(resolved_path)

                return self._to_relative_path(resolved_path)

        return import_path

    def resolve_with_context(self, import_path: str, source_file: str, context: str) -> str:
        """Resolve import using the appropriate context's path mappings."""
        if import_path.startswith("."):
            return import_path

        mappings = self.path_mappings_by_context.get(context, {})

        for alias_prefix, target_patterns in mappings.items():
            if import_path.startswith(alias_prefix):
                suffix = import_path[len(alias_prefix) :]
                if target_patterns:
                    resolved = target_patterns[0] + suffix
                    logger.debug(f"Resolved: {import_path} -> {resolved} (context: {context})")
                    return resolved

        return import_path
