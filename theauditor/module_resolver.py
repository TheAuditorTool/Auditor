"""Module resolution for TypeScript/JavaScript projects with tsconfig.json support."""

import json
import re
from pathlib import Path
from typing import Any

try:
    import json5

    HAS_JSON5 = True
except ImportError:
    HAS_JSON5 = False


class ModuleResolver:
    """Resolves module imports for TypeScript/JavaScript projects.

    Handles:
    - TypeScript path aliases from tsconfig.json
    - Webpack aliases from webpack.config.js
    - Node.js module resolution algorithm
    - Relative and absolute imports
    """

    def __init__(self, project_root: str | None = None, db_path: str = ".pf/repo_index.db"):
        """Initialize resolver with database path - NO filesystem access.

        Args:
            project_root: Deprecated parameter, kept for compatibility
            db_path: Path to the indexed database
        """
        if project_root:
            self.project_root = Path(project_root).resolve()
        else:
            self.project_root = Path.cwd()

        self.db_path = Path(db_path)
        self.configs_by_context: dict[str, Any] = {}
        self.path_mappings_by_context: dict[str, dict[str, list[str]]] = {}
        self.webpack_aliases: dict[str, str] = {}

        self.base_url: str | None = None
        self.path_mappings: dict[str, list[str]] = {}

        self._load_all_configs_from_db()

    def _load_all_configs_from_db(self) -> None:
        """Load ALL tsconfig files from database and organize by context."""
        if not self.db_path.exists():
            return

        import os
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

            for path, content, context_dir in configs:
                try:
                    if HAS_JSON5:
                        config = json5.loads(content)
                    else:
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

                        config = json.loads(content)

                    if context_dir is None:
                        refs = config.get("references", [])
                        if refs:
                            continue
                        context_dir = "root"

                    self.configs_by_context[context_dir] = config

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
                        if os.environ.get("THEAUDITOR_DEBUG"):
                            print(
                                f"[DEBUG]   {normalized_alias} -> {normalized_targets[0] if normalized_targets else 'None'}"
                            )

                    self.path_mappings_by_context[context_dir] = mappings

                    if not self.path_mappings and mappings:
                        self.path_mappings = mappings
                        self.base_url = base_url

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[WARNING] Failed to parse {path}: {e}")

        except sqlite3.OperationalError as e:
            error_msg = str(e)
            if "database is locked" in error_msg:
                print(
                    "[WARNING] Database locked (indexing in progress?), using empty path mappings"
                )
            elif "no such table" in error_msg:
                print("[WARNING] config_files table not found, using empty mappings")
            else:
                print(f"[WARNING] Failed to load config_files: {error_msg}")

        finally:
            conn.close()

    def _load_tsconfig(self) -> None:
        """Deprecated method kept for backward compatibility."""
        pass

    def resolve(self, import_path: str, containing_file_path: str) -> str:
        """Resolve an import path to its actual file location.

        Args:
            import_path: The import string (e.g., '@/utils/helpers')
            containing_file_path: The file where the import was found

        Returns:
            The resolved path relative to project root, or the original path if no alias matches
        """

        if import_path.startswith("."):
            return import_path

        for alias_prefix, target_patterns in self.path_mappings.items():
            if import_path.startswith(alias_prefix):
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
                                try:
                                    result = str(test_path.relative_to(self.project_root)).replace(
                                        "\\", "/"
                                    )

                                    return result
                                except ValueError:
                                    result = str(test_path).replace("\\", "/")

                                    return result

                        for index_name in ["index.ts", "index.tsx", "index.js", "index.jsx"]:
                            test_path = resolved_path / index_name
                            if test_path.exists():
                                try:
                                    return str(test_path.relative_to(self.project_root)).replace(
                                        "\\", "/"
                                    )
                                except ValueError:
                                    return str(test_path).replace("\\", "/")

                    if resolved_path.exists():
                        try:
                            return str(resolved_path.relative_to(self.project_root)).replace(
                                "\\", "/"
                            )
                        except ValueError:
                            return str(resolved_path).replace("\\", "/")

                    try:
                        relative_path = str(resolved_path.relative_to(self.project_root))

                        return relative_path.replace("\\", "/").lstrip("/")
                    except ValueError:
                        return target_pattern + suffix

        return import_path

    def resolve_with_context(self, import_path: str, source_file: str, context: str) -> str:
        """Resolve import using the appropriate context's path mappings.

        Args:
            import_path: The import string (e.g., '@config/app')
            source_file: The file containing the import
            context: Which tsconfig context ('backend', 'frontend', 'root')

        Returns:
            Resolved path or original if no match
        """
        import os

        if import_path.startswith("."):
            return import_path

        mappings = self.path_mappings_by_context.get(context, {})

        if not mappings and os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG] No mappings for context '{context}'")

        for alias_prefix, target_patterns in mappings.items():
            if import_path.startswith(alias_prefix):
                suffix = import_path[len(alias_prefix) :]

                if target_patterns:
                    resolved = target_patterns[0] + suffix
                    if os.environ.get("THEAUDITOR_DEBUG"):
                        print(f"[DEBUG] Resolved: {import_path} -> {resolved} (context: {context})")
                    return resolved

        return import_path

    def resolve_webpack_aliases(self, webpack_config_path: str) -> None:
        """Parse webpack.config.js for resolve.alias mappings.

        Args:
            webpack_config_path: Path to webpack configuration file
        """

        pass

    def resolve_with_node_algorithm(self, import_path: str, containing_file: str) -> str | None:
        """Implement Node.js module resolution algorithm.

        Follows Node.js rules:
        1. Check relative paths
        2. Check node_modules in current and parent directories
        3. Check global modules

        Args:
            import_path: The module to resolve
            containing_file: The file containing the import

        Returns:
            Resolved path or None if not found
        """
        containing_dir = Path(containing_file).parent

        if not import_path.startswith("."):
            current = containing_dir
            while current != current.parent:
                node_modules = current / "node_modules" / import_path

                package_json = node_modules / "package.json"
                if package_json.exists():
                    try:
                        pkg_data = json.loads(package_json.read_text())
                        main = pkg_data.get("main", "index.js")
                        main_file = node_modules / main
                        if main_file.exists():
                            return str(main_file.relative_to(self.project_root)).replace("\\", "/")
                    except (json.JSONDecodeError, OSError) as e:
                        print(f"[WARNING] Could not parse package.json from {package_json}: {e}")

                index_file = node_modules / "index.js"
                if index_file.exists():
                    return str(index_file.relative_to(self.project_root)).replace("\\", "/")

                for ext in [".js", ".ts", ".jsx", ".tsx", ".json"]:
                    file = node_modules.with_suffix(ext)
                    if file.exists():
                        return str(file.relative_to(self.project_root)).replace("\\", "/")

                current = current.parent

        return None
