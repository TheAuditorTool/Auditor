"""Graph builder module - constructs dependency and call graphs."""


import os
import platform
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from collections import defaultdict
from functools import lru_cache

# Windows compatibility
IS_WINDOWS = platform.system() == "Windows"

import click

from theauditor.indexer.config import SKIP_DIRS
from theauditor.module_resolver import ModuleResolver
from theauditor.ast_parser import ASTParser


@dataclass
class GraphNode:
    """Represents a node in the dependency or call graph."""

    id: str
    file: str
    lang: str | None = None
    loc: int = 0
    churn: int | None = None  # Git commit count if available
    type: str = "module"  # module, function, class
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Represents an edge in the graph."""

    source: str
    target: str
    type: str = "import"  # import, call, extends, implements
    file: str | None = None
    line: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Cycle:
    """Represents a cycle in the dependency graph."""
    
    nodes: list[str]
    size: int
    
    def __init__(self, nodes: list[str]):
        self.nodes = nodes
        self.size = len(nodes)


@dataclass
class Hotspot:
    """Represents a hotspot node with high connectivity."""
    
    id: str
    in_degree: int
    out_degree: int
    centrality: float
    score: float  # Computed based on weights


@dataclass  
class ImpactAnalysis:
    """Results of change impact analysis."""
    
    targets: list[str]
    upstream: list[str]  # What depends on targets
    downstream: list[str]  # What targets depend on
    total_impacted: int


class XGraphBuilder:
    """Build cross-project dependency and call graphs.

    This builder operates in database-first mode, reading all extraction data
    (imports, exports, calls) from the repo_index.db populated by the indexer.
    No regex-based extraction fallbacks exist - if data is not in the database,
    the extraction will return empty results, allowing us to identify edge cases.
    """

    def __init__(self, batch_size: int = 200, exclude_patterns: list[str] = None, project_root: str = "."):
        """Initialize builder with configuration."""
        self.batch_size = batch_size
        self.exclude_patterns = exclude_patterns or []
        self.checkpoint_file = Path(".pf/xgraph_checkpoint.json")
        self.project_root = Path(project_root).resolve()
        self.db_path = self.project_root / ".pf" / "repo_index.db"

        # ZERO FALLBACK: Cache raises FileNotFoundError if DB missing
        from theauditor.graph.db_cache import GraphDatabaseCache
        self.db_cache = GraphDatabaseCache(self.db_path)

        # Alias for convenience (file existence checks)
        self.known_files = self.db_cache.known_files

        self.module_resolver = ModuleResolver(db_path=str(self.db_path))
        self.ast_parser = ASTParser()  # Initialize AST parser for structural analysis

    @lru_cache(maxsize=1024)
    def _find_tsconfig_context(self, folder_path: Path) -> str:
        """Recursive lookup for the nearest tsconfig.json.

        Returns the string 'context' expected by ModuleResolver.
        This replaces hardcoded "backend"/"frontend" magic strings with
        actual filesystem discovery.

        Args:
            folder_path: Directory to start searching from

        Returns:
            Relative path from project root to tsconfig directory, or "root"

        Examples:
            - backend/tsconfig.json exists → returns "backend"
            - api/services/tsconfig.json exists → returns "api/services"
            - No tsconfig.json found → returns "root"
        """
        # 1. Check if tsconfig exists in this folder
        if (folder_path / "tsconfig.json").exists():
            # FOUND IT!
            # Return the folder path relative to project root
            # ModuleResolver expects this format (e.g., "backend", "frontend", "api")
            try:
                return str(folder_path.relative_to(self.project_root)).replace('\\', '/')
            except ValueError:
                # folder_path is outside project root (shouldn't happen)
                return "root"

        # 2. Stop at project root to prevent infinite loop
        if folder_path == self.project_root or folder_path.parent == folder_path:
            return "root"

        # 3. Recurse up the directory tree
        return self._find_tsconfig_context(folder_path.parent)

    def detect_language(self, file_path: Path) -> str | None:
        """Detect language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".cs": "c#",
            ".php": "php",
            ".rb": "ruby",
            ".c": "c",
            ".cpp": "c++",
            ".h": "c",
            ".hpp": "c++",
            ".rs": "rust",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".R": "r",
            ".m": "objective-c",
            ".mm": "objective-c++",
        }
        return ext_map.get(file_path.suffix.lower())

    def should_skip(self, file_path: Path) -> bool:
        """Check if file should be skipped based on exclude patterns."""
        # First, check if any component of the path is in SKIP_DIRS
        for part in file_path.parts:
            if part in SKIP_DIRS:
                return True
        
        # Second, check against exclude_patterns
        path_str = str(file_path)
        for pattern in self.exclude_patterns:
            if pattern in path_str:
                return True
        return False

    def extract_imports_from_db(self, rel_path: str) -> list[dict[str, Any]]:
        """Return structured import metadata for the given file.

        NO DATABASE ACCESS - Uses pre-loaded cache (O(1) lookup).
        Cache normalizes paths internally (Guardian of Hygiene).
        """
        return self.db_cache.get_imports(rel_path)

    def extract_imports(self, file_path: Path, lang: str) -> list[dict[str, Any]]:
        """Normalize file paths and fetch import metadata."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        # Cache handles path normalization internally
        return self.extract_imports_from_db(str(rel_path))

    def extract_exports_from_db(self, rel_path: str) -> list[dict[str, Any]]:
        """Return exported symbol metadata for the given file.

        NO DATABASE ACCESS - Uses pre-loaded cache (O(1) lookup).
        Cache normalizes paths internally (Guardian of Hygiene).
        """
        return self.db_cache.get_exports(rel_path)

    def extract_exports(self, file_path: Path, lang: str) -> list[dict[str, Any]]:
        """Wrapper that normalizes paths before querying exports."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        # Cache handles path normalization internally
        return self.extract_exports_from_db(str(rel_path))

    def extract_call_args_from_db(self, rel_path: str) -> list[dict[str, Any]]:
        """Return call argument metadata for the given file.

        ZERO FALLBACK: If database missing, __init__ already crashed.
        If query fails, let SQLite error propagate (exposes schema bug).

        Note: Not cached yet (complex JOIN query). Future optimization target.
        """
        # NO FALLBACK - Cache already validated DB exists in __init__
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # NO TRY/EXCEPT - Schema contract guarantees table exists
        cursor.execute(
            """
            SELECT file, line, caller_function, callee_function,
                   argument_index, argument_expr, param_name
              FROM function_call_args
             WHERE file = ?
            """,
            (rel_path,)
        )
        calls = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return calls

    def extract_call_args(self, file_path: Path, lang: str) -> list[dict[str, Any]]:
        """Wrapper to normalize file paths before querying call arguments."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        # Normalize path manually (not in cache yet)
        db_path = str(rel_path).replace("\\", "/")
        return self.extract_call_args_from_db(db_path)

    def resolve_import_path(self, import_str: str, source_file: Path, lang: str) -> str:
        """Resolve import string to a normalized module path that matches actual files in the graph."""
        # Clean up the import string (remove quotes, semicolons, etc.)
        import_str = import_str.strip().strip('"\'`;')

        # Language-specific resolution
        if lang == "python":
            # CRITICAL FIX: refs table stores BOTH file paths AND module names
            # - File path format: "theauditor/cli.py" (contains /)
            # - Module name format: "theauditor.cli" (dots only)

            # [FIX] Handle Relative Imports (starting with .)
            if import_str.startswith("."):
                # Count dots to determine level (1 dot = current, 2 dots = parent)
                level = 0
                temp_str = import_str
                while temp_str.startswith("."):
                    level += 1
                    temp_str = temp_str[1:]

                # Strip dots from the module name
                module_name = temp_str

                # Determine base directory:
                # level 1 (.) = current directory of source_file
                # level 2 (..) = parent of source_file
                # etc.
                current_dir = source_file.parent
                try:
                    for _ in range(level - 1):
                        current_dir = current_dir.parent
                except ValueError:
                    # Went past root - return as external
                    return f"external::{import_str}"

                # Make current_dir relative to project root
                try:
                    current_dir_rel = current_dir.relative_to(self.project_root)
                except ValueError:
                    current_dir_rel = current_dir

                # [FIX] Handle root directory case where relative_to returns "."
                # We want empty string prefix, not "./" which breaks DB cache lookup
                if str(current_dir_rel) == ".":
                    rel_prefix = ""
                else:
                    rel_prefix = f"{str(current_dir_rel).replace(chr(92), '/')}/"

                # Construct candidate paths
                if not module_name:
                    # "from . import x" -> import_str="." -> module_name=""
                    # Target is the __init__.py in the directory
                    candidates = [
                        f"{rel_prefix}__init__.py"
                    ]
                else:
                    # "from .utils import x" -> import_str=".utils"
                    # Target is utils.py OR utils/__init__.py
                    base_path = module_name.replace(".", "/")
                    candidates = [
                        f"{rel_prefix}{base_path}.py",
                        f"{rel_prefix}{base_path}/__init__.py"
                    ]

                # Check existence using cache
                for candidate in candidates:
                    norm_candidate = str(candidate).replace("\\", "/")
                    if self.db_cache.file_exists(norm_candidate):
                        return norm_candidate

                # If relative resolution failed, return first candidate as best guess
                return str(candidates[0]).replace("\\", "/")

            # If already a file path (contains /), return normalized
            if "/" in import_str:
                # Cache handles normalization (Guardian of Hygiene)
                return import_str.replace("\\", "/")

            # Module name -> file path conversion
            parts = import_str.split(".")
            base_path = "/".join(parts)

            # Priority 1: Check for package __init__.py
            # Python treats "import theauditor" as "theauditor/__init__.py"
            init_path = f"{base_path}/__init__.py"
            if self.db_cache.file_exists(init_path):
                return init_path

            # Priority 2: Check for module.py file
            module_path = f"{base_path}.py"
            if self.db_cache.file_exists(module_path):
                return module_path

            # Priority 3: Return best guess (.py extension most common)
            return module_path
        elif lang in ["javascript", "typescript"]:
            # Get source file directory for relative imports
            source_dir = source_file.parent
            # Handle case where source_file might already be relative or might be from manifest
            try:
                str(source_file.relative_to(self.project_root)).replace("\\", "/")
            except ValueError:
                # If source_file is already relative or from a different root, use it as is
                pass

            # 1. Handle TypeScript path aliases using ModuleResolver (database-driven)
            if import_str.startswith("@"):
                # [FIX] Dynamic Context Discovery (The Fix for Bug #2)
                # Instead of hardcoding "backend/" or "frontend/", walk up the directory tree
                # to find the nearest tsconfig.json. This makes the graph builder resilient to:
                # - Projects with non-standard folder names (e.g., "api" instead of "backend")
                # - Nested tsconfig.json files (e.g., "services/auth/tsconfig.json")
                # - Future refactorings that rename folders
                context = self._find_tsconfig_context(source_file.parent)

                # Use ModuleResolver's context-aware resolution
                resolved = self.module_resolver.resolve_with_context(import_str, str(source_file), context)

                # [FIX 2024-11] Use smart cache resolution instead of manual extension loop
                # The cache is the source of truth for file existence - it handles:
                # - Extension permutation (.ts, .tsx, .js, .jsx, .d.ts, .py)
                # - Index file resolution (src/utils -> src/utils/index.ts)
                real_file = self.db_cache.resolve_filename(resolved)
                if real_file:
                    return real_file

                # If cache couldn't find it, return the resolved guess (might be external/broken)
                return resolved
            
            # 2. Handle relative imports (./foo, ../bar/baz)
            elif import_str.startswith("."):
                # Resolve relative to source file
                try:
                    # Remove leading dots and slashes
                    rel_import = import_str.lstrip("./")

                    # Go up directories for ../
                    up_count = import_str.count("../")
                    current_dir = source_dir
                    for _ in range(up_count):
                        current_dir = current_dir.parent

                    if up_count > 0:
                        rel_import = import_str.replace("../", "")

                    # Build the target path
                    target_path = current_dir / rel_import
                    rel_target = str(target_path.relative_to(self.project_root)).replace("\\", "/")

                    # [FIX 2024-11] Use smart cache resolution instead of manual extension loop
                    real_file = self.db_cache.resolve_filename(rel_target)
                    if real_file:
                        return real_file

                    return rel_target

                except (ValueError, OSError):
                    pass
            
            # 3. Handle node_modules imports (just return as-is, they're external)
            else:
                # For npm packages, just return the package name
                return import_str
            
            # If nothing worked, return original
            return import_str
        else:
            # Default: return as-is
            return import_str

    def get_file_metrics(self, file_path: Path) -> dict[str, Any]:
        """Get basic metrics for a file from manifest/database.

        DATABASE-FIRST ARCHITECTURE: Graph builder READS metrics pre-computed by Indexer.
        NO FILESYSTEM ACCESS (no file I/O, no subprocess calls).
        NO SUBPROCESS CALLS (no git commands in production code).

        Separation of concerns:
        - Indexer (aud full): WRITES metrics (LOC, churn) to database
        - Builder (aud graph build): READS metrics from database/manifest

        If metrics missing from manifest, return defaults.
        Indexer will populate on next run.
        """
        # Return defaults - caller should use manifest data
        # If manifest doesn't have metrics, Indexer needs fixing
        return {"loc": 0, "churn": None}

    def _get_metrics_for(self, rel_path: str, manifest_lookup: dict[str, dict[str, Any]], root_path: Path) -> tuple[int, Any]:
        """Return (loc, churn) for a module using manifest or filesystem data."""
        manifest_entry = manifest_lookup.get(rel_path)
        if manifest_entry:
            return manifest_entry.get("loc", 0), manifest_entry.get("churn")

        file_on_disk = root_path / Path(rel_path)
        metrics = self.get_file_metrics(file_on_disk)
        return metrics["loc"], metrics["churn"]

    def _ensure_module_node(
        self,
        nodes: dict[str, "GraphNode"],
        rel_path: str,
        lang: str | None,
        manifest_lookup: dict[str, dict[str, Any]],
        root_path: Path,
        status: str,
    ) -> "GraphNode":
        """Ensure a module node exists and return it."""
        if rel_path in nodes:
            node = nodes[rel_path]
            node.metadata.setdefault("status", status)
            return node

        loc, churn = self._get_metrics_for(rel_path, manifest_lookup, root_path)
        node = GraphNode(
            id=rel_path,
            file=rel_path,
            lang=lang,
            loc=loc,
            churn=churn,
            type="module",
            metadata={"status": status},
        )
        nodes[rel_path] = node
        return node

    def build_import_graph(
        self,
        root: str = ".",
        langs: list[str] | None = None,
        file_filter: str | None = None,
        file_list: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build import/dependency graph for the project."""
        root_path = Path(root).resolve()
        nodes: dict[str, "GraphNode"] = {}
        edges: list["GraphEdge"] = []

        # Track manifest metrics for quick lookup (keyed by relative path)
        manifest_lookup_rel: dict[str, dict[str, Any]] = {}
        files: list[tuple[Path, str]] = []

        if file_list is not None:
            for item in file_list:
                manifest_path = Path(item['path'])
                rel_path_str = str(manifest_path).replace('\\', '/')
                manifest_lookup_rel[rel_path_str] = item
                file = root_path / manifest_path
                lang = self.detect_language(manifest_path)
                if lang and (not langs or lang in langs):
                    files.append((file, lang))
        else:
            for dirpath, dirnames, filenames in os.walk(root_path):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                if self.exclude_patterns:
                    dirnames[:] = [d for d in dirnames if not any(pattern in d for pattern in self.exclude_patterns)]
                for filename in filenames:
                    file = Path(dirpath) / filename
                    if not self.should_skip(file):
                        lang = self.detect_language(file)
                        if lang and (not langs or lang in langs):
                            files.append((file, lang))

        # [FIX 2024-11] Removed expensive file hashing IO (was reading EVERY file to SHA256)
        # The Indexer already stores file metadata in DB. Builder should only read from DB/cache.
        # This change alone can double build speed on large repos.
        current_files = {}
        for file_path, lang in files:
            rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
            current_files[rel_path] = {'language': lang}

        # Build import graph from database (no caching)
        with click.progressbar(
            files,
            label="Building import graph",
            show_pos=True,
            show_percent=True,
            show_eta=True,
            item_show_func=lambda x: str(x[0].name) if x else None,
        ) as bar:
            for file_path, lang in bar:
                rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
                module_node = self._ensure_module_node(
                    nodes,
                    rel_path,
                    lang,
                    manifest_lookup_rel,
                    root_path,
                    status="updated",
                )
                module_node.metadata["language"] = lang

                imports = self.extract_imports_from_db(rel_path)
                module_node.metadata["import_count"] = len(imports)

                for imp in imports:
                    raw_value = imp.get("value")
                    resolved = self.resolve_import_path(raw_value, file_path, lang) if raw_value else raw_value
                    resolved_norm = resolved.replace('\\', '/') if resolved else None

                    # [FIX 2024-11] resolve_import_path now uses cache.resolve_filename() which handles
                    # extension permutation internally. A simple file_exists check is sufficient here.
                    # The redundant extension loop has been removed - all resolution logic is in one place.
                    resolved_exists = self.db_cache.file_exists(resolved_norm) if resolved_norm else False

                    if resolved_exists:
                        target_id = resolved_norm
                        target_lang = current_files.get(resolved_norm, {}).get('language')
                        target_node = self._ensure_module_node(
                            nodes,
                            target_id,
                            target_lang,
                            manifest_lookup_rel,
                            root_path,
                            status="referenced",
                        )
                        target_node.metadata.setdefault("language", target_lang)
                    else:
                        external_id = resolved_norm or raw_value or "unknown"
                        target_id = f"external::{external_id}"
                        if target_id not in nodes:
                            nodes[target_id] = GraphNode(
                                id=target_id,
                                file=raw_value or external_id,
                                lang=None,
                                type="external_module",
                                metadata={"status": "external"},
                            )

                    edge_metadata = {
                        "kind": imp.get("kind"),
                        "raw": raw_value,
                        "resolved": resolved_norm or raw_value,
                        "resolved_exists": resolved_exists,
                    }
                    edge = GraphEdge(
                        source=module_node.id,
                        target=target_id,
                        type="import",
                        file=rel_path,
                        line=imp.get("line"),
                        metadata=edge_metadata,
                    )
                    edges.append(edge)

        for file_path, lang in files:
            rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
            module_node = self._ensure_module_node(
                nodes,
                rel_path,
                lang,
                manifest_lookup_rel,
                root_path,
                status="cached",
            )
            module_node.metadata.setdefault("language", lang)
            module_node.metadata.setdefault("import_count", module_node.metadata.get("import_count", 0))

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(root_path),
                "languages": sorted({node.lang for node in nodes.values() if node.lang}),
                "total_files": len(nodes),
                "total_imports": len(edges),
            },
        }

    def build_call_graph(
        self,
        root: str = ".",
        langs: list[str] | None = None,
        file_filter: str | None = None,
        file_list: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build call graph for the project."""
        root_path = Path(root).resolve()
        nodes: dict[str, "GraphNode"] = {}
        edges: list["GraphEdge"] = []
        manifest_lookup_rel: dict[str, dict[str, Any]] = {}
        files: list[tuple[Path, str]] = []

        if file_list is not None:
            for item in file_list:
                manifest_path = Path(item['path'])
                rel_path_str = str(manifest_path).replace('\\', '/')
                manifest_lookup_rel[rel_path_str] = item
                file = root_path / manifest_path
                lang = self.detect_language(manifest_path)
                if lang and (not langs or lang in langs):
                    files.append((file, lang))
        else:
            for dirpath, dirnames, filenames in os.walk(root_path):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                if self.exclude_patterns:
                    dirnames[:] = [d for d in dirnames if not any(pattern in d for pattern in self.exclude_patterns)]
                for filename in filenames:
                    file = Path(dirpath) / filename
                    if not self.should_skip(file):
                        lang = self.detect_language(file)
                        if lang and (not langs or lang in langs):
                            files.append((file, lang))

        current_files: dict[str, dict[str, Any]] = {}
        for file_path, lang in files:
            try:
                rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
            except ValueError:
                rel_path = str(file_path).replace('\\', '/')
            current_files[rel_path] = {"language": lang}

        # Prepare auxiliary metadata from database
        function_defs: dict[str, set[str]] = defaultdict(set)
        function_lines: dict[tuple[str, str], int | None] = {}
        returns_map: dict[tuple[str, str], dict[str, Any]] = {}
        if self.db_path.exists():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT path, name, line FROM symbols WHERE type IN ('function', 'class')")
            for row in cursor.fetchall():
                rel = row['path'].replace('\\', '/')
                function_defs[row['name']].add(rel)
                function_lines[(rel, row['name'])] = row['line']
            # Query normalized function returns with aggregated return variables
            # Uses LEFT JOIN on function_return_sources junction table (normalized in context branch)
            # GROUP_CONCAT aggregates multiple return_var_name values into comma-separated string
            print("[Graph Builder] Querying function returns from normalized schema...")
            cursor.execute("""
                SELECT
                    fr.file,
                    fr.function_name,
                    fr.return_expr,
                    GROUP_CONCAT(frsrc.return_var_name, ',') as return_vars
                FROM function_returns fr
                LEFT JOIN function_return_sources frsrc
                    ON fr.file = frsrc.return_file
                    AND fr.line = frsrc.return_line
                    AND fr.function_name = frsrc.return_function
                GROUP BY fr.file, fr.function_name, fr.return_expr
            """)
            print(f"[Graph Builder] Processing function return data...")
            for row in cursor.fetchall():
                rel = row['file'].replace('\\', '/')
                returns_map[(rel, row['function_name'])] = {
                    "return_expr": row['return_expr'],
                    "return_vars": row['return_vars'],  # Now comma-separated string from GROUP_CONCAT
                }
        else:
            conn = None

        def ensure_function_node(module_path: str, function_name: str, lang: str | None, status: str) -> "GraphNode":
            node_id = f"{module_path}::{function_name}"
            if node_id in nodes:
                node = nodes[node_id]
                node.metadata.setdefault("status", status)
                return node

            metadata = {
                "status": status,
                "module": module_path,
                "line": function_lines.get((module_path, function_name)),
            }
            returns = returns_map.get((module_path, function_name))
            if returns:
                metadata.update({k: v for k, v in returns.items() if v})

            node = GraphNode(
                id=node_id,
                file=module_path,
                lang=lang,
                loc=0,
                churn=None,
                type="function",
                metadata=metadata,
            )
            nodes[node_id] = node
            return node

        # [FIX] Pre-resolve ALL imports before main loop (2025 Best Practice - Batch Processing)
        # This prevents N redundant resolve_import_path calls inside the loop
        # Trade-off: ~10MB RAM for 1,000 files → 10-100x faster call graph building
        print("[Graph Builder] Pre-resolving imports for all files...")
        file_imports_resolved: dict[str, set[str]] = {}

        with click.progressbar(
            files,
            label="Resolving imports",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: str(x[0].name) if x else None,
        ) as bar:
            for file_path, lang in bar:
                rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
                file_imports = self.extract_imports_from_db(rel_path)
                resolved_imports = set()
                for imp in file_imports:
                    raw_import = imp.get("value")
                    if raw_import:
                        resolved = self.resolve_import_path(raw_import, file_path, lang)
                        if resolved:
                            resolved_imports.add(resolved.replace('\\', '/'))
                file_imports_resolved[rel_path] = resolved_imports

        # Process files to build call edges
        with click.progressbar(
            files,
            label="Building call graph",
            show_pos=True,
            show_percent=True,
            show_eta=True,
            item_show_func=lambda x: str(x[0].name) if x else None,
        ) as bar:
            for file_path, lang in bar:
                rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')

                # [FIX] Use pre-resolved imports (O(1) lookup, no redundant work)
                resolved_imports = file_imports_resolved.get(rel_path, set())

                module_node = self._ensure_module_node(
                    nodes,
                    rel_path,
                    lang,
                    manifest_lookup_rel,
                    root_path,
                    status="active",
                )
                module_node.metadata["language"] = lang

                exports = self.extract_exports_from_db(rel_path)
                for export in exports:
                    func_node = ensure_function_node(rel_path, export.get("name", ""), lang, "exported")
                    func_node.metadata.setdefault("symbol_type", export.get("symbol_type"))
                    func_node.metadata.setdefault("line", export.get("line"))

                call_records = self.extract_call_args(file_path, lang)
                for record in call_records:
                    caller = record.get("caller_function")
                    callee = record.get("callee_function")
                    line = record.get("line")
                    caller_node = ensure_function_node(rel_path, caller, lang, "caller")

                    # [FIX] Import-Aware Resolution Logic
                    # Try exact match first
                    target_candidates = function_defs.get(callee, set())

                    # [FIX] If no exact match, try splitting (module.function or Class.method)
                    # e.g., "os.path.join" -> try "join", "UserService.create" -> try "create"
                    if not target_candidates and "." in callee:
                        short_name = callee.split(".")[-1]
                        target_candidates = function_defs.get(short_name, set())

                    target_module = None
                    resolution_status = "unresolved"

                    if target_candidates:
                        # Case A: Function is defined in the current file (Highest Priority)
                        if rel_path in target_candidates:
                            target_module = rel_path
                            resolution_status = "local_def"

                        # Case B: Function is defined in a file we explicitly imported
                        else:
                            # Find intersection between potential candidates and our actual imports
                            matches = [c for c in target_candidates if c in resolved_imports]

                            if len(matches) == 1:
                                target_module = matches[0]
                                resolution_status = "imported_def"
                            elif len(matches) > 1:
                                # Multiple matches - use first but mark as ambiguous
                                target_module = matches[0]
                                resolution_status = "ambiguous_import"
                            else:
                                # Case C: Name exists in project, but we didn't import it
                                # STOP RANDOM GUESSING. Treat as ambiguous/global.
                                target_module = None
                                resolution_status = "ambiguous_global"

                    # Node Creation based on Resolution
                    if target_module:
                        # We found a valid, trustworthy target
                        target_lang = current_files.get(target_module, {}).get('language')
                        callee_node = ensure_function_node(target_module, callee, target_lang, "callee")
                        resolved = True
                    else:
                        # Fallback: Create a specific node for the ambiguous/external call
                        # Distinguish between "Ambiguous" (exists in project but not linked) vs "External" (not in project)
                        if target_candidates:
                            node_id = f"ambiguous::{callee}"
                            node_type = "ambiguous_function"
                        else:
                            node_id = f"external::{callee}"
                            node_type = "external_function"

                        if node_id not in nodes:
                            nodes[node_id] = GraphNode(
                                id=node_id,
                                file=callee or "unknown",
                                lang=None,
                                loc=0,
                                churn=None,
                                type=node_type,
                                metadata={"status": "external" if node_type == "external_function" else "ambiguous"},
                            )
                        callee_node = nodes[node_id]
                        resolved = False

                    edge_metadata = {
                        "argument_index": record.get("argument_index"),
                        "argument_expr": record.get("argument_expr"),
                        "param_name": record.get("param_name"),
                        "resolved": resolved,
                        "resolution_status": resolution_status,  # Track how call was resolved
                    }
                    if target_module:
                        edge_metadata["callee_module"] = target_module

                    edges.append(
                        GraphEdge(
                            source=caller_node.id,
                            target=callee_node.id,
                            type="call",
                            file=rel_path,
                            line=line,
                            metadata=edge_metadata,
                        )
                    )

        # Supplement graph with database-centric nodes (SQL/ORM/hooks)
        if self.db_path.exists():
            if conn is None:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query normalized SQL queries with aggregated table references
            # Uses LEFT JOIN on sql_query_tables junction table (normalized in context branch)
            # GROUP_CONCAT aggregates multiple table_name values into comma-separated string
            print("[Graph Builder] Querying SQL queries from normalized schema...")
            cursor.execute("""
                SELECT
                    sq.file_path,
                    sq.line_number,
                    sq.command,
                    sq.extraction_source,
                    sq.query_text,
                    GROUP_CONCAT(sqt.table_name, ',') as tables
                FROM sql_queries sq
                LEFT JOIN sql_query_tables sqt
                    ON sq.file_path = sqt.query_file
                    AND sq.line_number = sqt.query_line
                GROUP BY sq.file_path, sq.line_number, sq.command, sq.extraction_source, sq.query_text
            """)
            sql_rows = cursor.fetchall()
            print(f"[Graph Builder] Found {len(sql_rows)} SQL query records")

            for row in sql_rows:
                rel_file = row["file_path"].replace('\\', '/')
                module_node = self._ensure_module_node(
                    nodes,
                    rel_file,
                    current_files.get(rel_file, {}).get('language'),
                    manifest_lookup_rel,
                    root_path,
                    status="referenced",
                )
                sql_node_id = f"{rel_file}::sql:{row['line_number']}"
                if sql_node_id not in nodes:
                    metadata = {
                        "status": "sql_query",
                        "command": row["command"],
                        "tables": row["tables"],  # Now comma-separated string from GROUP_CONCAT
                        "source": row["extraction_source"],
                        "snippet": (row["query_text"] or '')[:200],
                    }
                    nodes[sql_node_id] = GraphNode(
                        id=sql_node_id,
                        file=rel_file,
                        lang=None,
                        loc=0,
                        churn=None,
                        type="sql_query",
                        metadata=metadata,
                    )
                edge_metadata = {
                    "command": row["command"],
                    "tables": row["tables"],  # Now comma-separated string from GROUP_CONCAT
                    "source": row["extraction_source"],
                }
                edges.append(
                    GraphEdge(
                        source=module_node.id,
                        target=sql_node_id,
                        type="sql",
                        file=rel_file,
                        line=row["line_number"],
                        metadata=edge_metadata,
                    )
                )

            cursor.execute(
                "SELECT file, line, query_type, includes, has_limit, has_transaction FROM orm_queries"
            )
            for row in cursor.fetchall():
                rel_file = row["file"].replace('\\', '/')
                module_node = self._ensure_module_node(
                    nodes,
                    rel_file,
                    current_files.get(rel_file, {}).get('language'),
                    manifest_lookup_rel,
                    root_path,
                    status="referenced",
                )
                orm_node_id = f"{rel_file}::orm:{row['line']}"
                if orm_node_id not in nodes:
                    metadata = {
                        "status": "orm_query",
                        "query_type": row["query_type"],
                        "includes": row["includes"],
                        "has_limit": row["has_limit"],
                        "has_transaction": row["has_transaction"],
                    }
                    nodes[orm_node_id] = GraphNode(
                        id=orm_node_id,
                        file=rel_file,
                        lang=None,
                        loc=0,
                        churn=None,
                        type="orm_query",
                        metadata=metadata,
                    )
                edge_metadata = {
                    "query_type": row["query_type"],
                    "includes": row["includes"],
                }
                edges.append(
                    GraphEdge(
                        source=module_node.id,
                        target=orm_node_id,
                        type="orm",
                        file=rel_file,
                        line=row["line"],
                        metadata=edge_metadata,
                    )
                )

            # Query normalized react hooks with aggregated dependency variables
            # Uses LEFT JOIN on react_hook_dependencies junction table (normalized in context branch)
            # GROUP_CONCAT aggregates multiple dependency_name values into comma-separated string
            print("[Graph Builder] Querying React hooks from normalized schema...")
            cursor.execute("""
                SELECT
                    rh.file,
                    rh.line,
                    rh.component_name,
                    rh.hook_name,
                    GROUP_CONCAT(rhd.dependency_name, ',') as dependency_vars
                FROM react_hooks rh
                LEFT JOIN react_hook_dependencies rhd
                    ON rh.file = rhd.hook_file
                    AND rh.line = rhd.hook_line
                    AND rh.component_name = rhd.hook_component
                GROUP BY rh.file, rh.line, rh.component_name, rh.hook_name
            """)
            react_hook_rows = cursor.fetchall()
            print(f"[Graph Builder] Found {len(react_hook_rows)} React hook records")
            for row in react_hook_rows:
                rel_file = row["file"].replace('\\', '/')
                module_node = self._ensure_module_node(
                    nodes,
                    rel_file,
                    current_files.get(rel_file, {}).get('language'),
                    manifest_lookup_rel,
                    root_path,
                    status="referenced",
                )
                hook_node_id = f"{rel_file}::hook:{row['line']}"
                if hook_node_id not in nodes:
                    metadata = {
                        "status": "react_hook",
                        "hook_name": row["hook_name"],
                        "dependency_vars": row["dependency_vars"],  # Now comma-separated string from GROUP_CONCAT
                    }
                    nodes[hook_node_id] = GraphNode(
                        id=hook_node_id,
                        file=rel_file,
                        lang=None,
                        loc=0,
                        churn=None,
                        type="react_hook",
                        metadata=metadata,
                    )
                edges.append(
                    GraphEdge(
                        source=module_node.id,
                        target=hook_node_id,
                        type="react_hook",
                        file=rel_file,
                        line=row["line"],
                        metadata={"hook_name": row["hook_name"]},
                    )
                )

        if conn is not None:
            conn.close()

        for file_path, lang in files:
            rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
            module_node = self._ensure_module_node(
                nodes,
                rel_path,
                lang,
                manifest_lookup_rel,
                root_path,
                status="cached",
            )
            module_node.metadata.setdefault("language", lang)

        function_count = sum(1 for node in nodes.values() if node.type == 'function')
        sql_count = sum(1 for node in nodes.values() if node.type == 'sql_query')
        orm_count = sum(1 for node in nodes.values() if node.type == 'orm_query')

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(root_path),
                "languages": sorted({node.lang for node in nodes.values() if node.lang}),
                "function_nodes": function_count,
                "total_edges": len(edges),
                "sql_nodes": sql_count,
                "orm_nodes": orm_count,
            },
        }

    def merge_graphs(self, import_graph: dict, call_graph: dict) -> dict[str, Any]:
        """Merge import and call graphs into a unified graph."""
        # Combine nodes (dedup by id)
        nodes = {}
        for node in import_graph["nodes"]:
            nodes[node["id"]] = node
        for node in call_graph["nodes"]:
            nodes[node["id"]] = node

        # Combine edges
        edges = import_graph["edges"] + call_graph["edges"]

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "metadata": {
                "root": import_graph["metadata"]["root"],
                "languages": list(
                    set(
                        import_graph["metadata"]["languages"]
                        + call_graph["metadata"].get("languages", [])
                    )
                ),
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
        }
