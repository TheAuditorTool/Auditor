"""Graph builder module - constructs dependency and call graphs."""

import os
import platform
import sqlite3
import subprocess
import tempfile
import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from collections import defaultdict

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
        self.module_resolver = ModuleResolver(db_path=str(self.db_path))
        self.ast_parser = ASTParser()  # Initialize AST parser for structural analysis

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
        """Return structured import metadata for the given file."""
        if not self.db_path.exists():
            print(f"Warning: Database not found at {self.db_path}")
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT kind, value, line
                  FROM refs
                 WHERE src = ?
                   AND kind IN ('import', 'require', 'from', 'import_type', 'export', 'import_dynamic')
                """,
                (rel_path,)
            )
            imports = [
                {
                    "kind": row[0],
                    "value": row[1],
                    "line": row[2],
                }
                for row in cursor.fetchall()
            ]
            conn.close()
            return imports
        except sqlite3.Error as exc:
            print(f"Warning: Failed to read imports for {rel_path}: {exc}")
            return []

    def extract_imports(self, file_path: Path, lang: str) -> list[dict[str, Any]]:
        """Normalize file paths and fetch import metadata."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        db_path = str(rel_path).replace("\\", "/")
        return self.extract_imports_from_db(db_path)

    def extract_exports_from_db(self, rel_path: str) -> list[dict[str, Any]]:
        """Return exported symbol metadata for the given file."""
        if not self.db_path.exists():
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, type, line FROM symbols WHERE path = ? AND type IN ('function', 'class')",
                (rel_path,)
            )
            exports = [
                {
                    "name": row[0],
                    "symbol_type": row[1],
                    "line": row[2],
                }
                for row in cursor.fetchall()
            ]
            conn.close()
            return exports
        except sqlite3.Error:
            return []

    def extract_exports(self, file_path: Path, lang: str) -> list[dict[str, Any]]:
        """Wrapper that normalizes paths before querying exports."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        db_path = str(rel_path).replace("\\", "/")
        return self.extract_exports_from_db(db_path)

    def extract_call_args_from_db(self, rel_path: str) -> list[dict[str, Any]]:
        """Return call argument metadata for the given file."""
        if not self.db_path.exists():
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
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
        except sqlite3.Error:
            return []

    def extract_call_args(self, file_path: Path, lang: str) -> list[dict[str, Any]]:
        """Wrapper to normalize file paths before querying call arguments."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        db_path = str(rel_path).replace("\\", "/")
        return self.extract_call_args_from_db(db_path)

    def resolve_import_path(self, import_str: str, source_file: Path, lang: str) -> str:
        """Resolve import string to a normalized module path that matches actual files in the graph."""
        import sqlite3
        
        # Clean up the import string (remove quotes, semicolons, etc.)
        import_str = import_str.strip().strip('"\'`;')
        
        # Language-specific resolution
        if lang == "python":
            # Convert Python module path to file path
            parts = import_str.split(".")
            return "/".join(parts)
        elif lang in ["javascript", "typescript"]:
            # Get source file directory for relative imports
            source_dir = source_file.parent
            # Handle case where source_file might already be relative or might be from manifest
            try:
                source_rel = str(source_file.relative_to(self.project_root)).replace("\\", "/")
            except ValueError:
                # If source_file is already relative or from a different root, use it as is
                source_rel = str(source_file).replace("\\", "/")
            
            # Handle different import patterns
            resolved_path = None
            
            # 1. Handle TypeScript path aliases using ModuleResolver (database-driven)
            if import_str.startswith("@"):
                # Determine context from source file location
                try:
                    source_rel = str(source_file.relative_to(self.project_root)).replace("\\", "/")
                except ValueError:
                    source_rel = str(source_file).replace("\\", "/")
                
                # Determine which tsconfig context applies
                if "backend/" in source_rel:
                    context = "backend"
                elif "frontend/" in source_rel:
                    context = "frontend"
                else:
                    context = "root"
                
                # Use ModuleResolver's context-aware resolution
                resolved = self.module_resolver.resolve_with_context(import_str, str(source_file), context)
                
                # Check if resolution succeeded
                if resolved != import_str:
                    # Resolution worked, now verify file exists in database
                    if self.db_path.exists():
                        try:
                            conn = sqlite3.connect(self.db_path)
                            cursor = conn.cursor()
                            
                            # Try with common extensions if no extension
                            test_paths = [resolved]
                            if not Path(resolved).suffix:
                                for ext in [".ts", ".tsx", ".js", ".jsx"]:
                                    test_paths.append(resolved + ext)
                                test_paths.append(resolved + "/index.ts")
                                test_paths.append(resolved + "/index.js")
                            
                            for test_path in test_paths:
                                cursor.execute("SELECT 1 FROM files WHERE path = ? LIMIT 1", (test_path,))
                                if cursor.fetchone():
                                    conn.close()
                                    return test_path
                            
                            conn.close()
                        except sqlite3.Error:
                            pass
                    
                    # Return resolved even if file check failed
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
                    
                    # Check if this file exists (try with extensions)
                    if self.db_path.exists():
                        try:
                            conn = sqlite3.connect(self.db_path)
                            cursor = conn.cursor()
                            
                            # Try with common extensions
                            for ext in ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]:
                                test_path = rel_target + ext
                                cursor.execute("SELECT 1 FROM files WHERE path = ? LIMIT 1", (test_path,))
                                if cursor.fetchone():
                                    conn.close()
                                    return test_path
                            
                            conn.close()
                        except sqlite3.Error:
                            pass
                    
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
        """Get basic metrics for a file."""
        metrics = {"loc": 0, "churn": None}

        # When working with manifest data, skip file reading
        # The manifest already has loc and other metrics
        if not file_path.exists():
            # File doesn't exist, we're working with manifest data
            # Return default metrics - the caller should use manifest data instead
            return metrics

        # Count lines of code
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                metrics["loc"] = sum(1 for _ in f)
        except (IOError, UnicodeDecodeError, OSError) as e:
            print(f"Warning: Failed to read {file_path} for metrics: {e}")
            # Still return default metrics but LOG the failure

        # Get git churn (commit count)
        try:
            # Use temp files to avoid buffer overflow
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt', encoding='utf-8') as stdout_fp, \
                 tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt', encoding='utf-8') as stderr_fp:
                
                stdout_path = stdout_fp.name
                stderr_path = stderr_fp.name
                
                result = subprocess.run(
                    ["git", "log", "--oneline", str(file_path)],
                    stdout=stdout_fp,
                    stderr=stderr_fp,
                    text=True,
                    timeout=5,
                    cwd=Path.cwd(),
                    shell=IS_WINDOWS  # Windows compatibility fix
                )
            
            with open(stdout_path, 'r', encoding='utf-8') as f:
                result.stdout = f.read()
            with open(stderr_path, 'r', encoding='utf-8') as f:
                result.stderr = f.read()
            
            os.unlink(stdout_path)
            os.unlink(stderr_path)
            if result.returncode == 0:
                metrics["churn"] = len(result.stdout.strip().split("\n"))
        except (subprocess.TimeoutExpired, OSError, IOError) as e:
            print(f"Warning: Failed to get git churn for {file_path}: {e}")
            # Still return default metrics but LOG the failure

        return metrics

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
        nodes: dict[str, GraphNode],
        rel_path: str,
        lang: str | None,
        manifest_lookup: dict[str, dict[str, Any]],
        root_path: Path,
        status: str,
    ) -> GraphNode:
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
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []

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

        # Compute file hashes for incremental cache lookup
        current_files = {}
        for file_path, lang in files:
            try:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
                current_files[rel_path] = {
                    'hash': file_hash,
                    'language': lang,
                    'size': file_path.stat().st_size if file_path.exists() else 0,
                }
            except (OSError, PermissionError):
                pass


        from theauditor.cache.graph_cache import GraphCache
        # Initialize graph cache for incremental updates
        cache_dir = root_path / ".pf" / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        graph_cache = GraphCache(cache_dir)

        added, removed, modified = graph_cache.get_changed_files(
            {path: info['hash'] for path, info in current_files.items()}
        )
        invalidated = added | removed | modified

        cached_edges = graph_cache.get_all_edges()
        valid_cached_edges: list[GraphEdge] = []
        for source, target, edge_type, metadata in cached_edges:
            if source in invalidated:
                continue
            meta = metadata or {}
            valid_cached_edges.append(
                GraphEdge(
                    source=source,
                    target=target,
                    type=edge_type,
                    file=meta.get('file'),
                    line=meta.get('line'),
                    metadata=meta,
                )
            )

        files_to_process = []
        for file_path, lang in files:
            rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
            if rel_path in invalidated:
                files_to_process.append((file_path, lang))

        print(f"[Graph Cache] Using {len(valid_cached_edges)} cached edges, processing {len(files_to_process)} changed files")

        if invalidated:
            graph_cache.invalidate_edges(invalidated)

        new_edges: list[tuple[str, str, str, dict[str, Any]]] = []
        with click.progressbar(
            files_to_process,
            label="Building import graph (incremental)",
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
                    resolved_exists = resolved_norm in current_files

                    if resolved_exists:
                        target_id = resolved_norm
                        target_lang = current_files[resolved_norm].get('language')
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

                    cache_meta = dict(edge_metadata)
                    cache_meta["file"] = edge.file
                    cache_meta["line"] = edge.line
                    new_edges.append((edge.source, edge.target, edge.type, cache_meta))

        edges.extend(valid_cached_edges)

        if new_edges:
            graph_cache.add_edges(new_edges)
        if current_files:
            graph_cache.update_file_states(current_files)
        if removed:
            graph_cache.remove_file_states(removed)

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
                "cached_edges": len(valid_cached_edges),
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
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []
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
            cursor.execute("SELECT path, name, line FROM symbols WHERE type = 'function'")
            for row in cursor.fetchall():
                rel = row['path'].replace('\\', '/')
                function_defs[row['name']].add(rel)
                function_lines[(rel, row['name'])] = row['line']
            cursor.execute("SELECT file, function_name, return_expr, return_vars FROM function_returns")
            for row in cursor.fetchall():
                rel = row['file'].replace('\\', '/')
                returns_map[(rel, row['function_name'])] = {
                    "return_expr": row['return_expr'],
                    "return_vars": row['return_vars'],
                }
        else:
            conn = None

        def ensure_function_node(module_path: str, function_name: str, lang: str | None, status: str) -> GraphNode:
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

                    target_candidates = function_defs.get(callee, set())
                    if target_candidates:
                        if rel_path in target_candidates:
                            target_module = rel_path
                        else:
                            target_module = next(iter(target_candidates))
                        target_lang = current_files.get(target_module, {}).get('language') if target_module in current_files else None
                        callee_node = ensure_function_node(target_module, callee, target_lang, "callee")
                        resolved = True
                    else:
                        target_module = None
                        external_id = f"external::{callee}"
                        if external_id not in nodes:
                            nodes[external_id] = GraphNode(
                                id=external_id,
                                file=callee or "unknown",
                                lang=None,
                                loc=0,
                                churn=None,
                                type="external_function",
                                metadata={"status": "external"},
                            )
                        callee_node = nodes[external_id]
                        resolved = False

                    edge_metadata = {
                        "argument_index": record.get("argument_index"),
                        "argument_expr": record.get("argument_expr"),
                        "param_name": record.get("param_name"),
                        "resolved": resolved,
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

            cursor.execute(
                "SELECT file_path, line_number, command, tables, extraction_source, query_text FROM sql_queries"
            )
            for row in cursor.fetchall():
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
                        "tables": row["tables"],
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
                    "tables": row["tables"],
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

            cursor.execute(
                "SELECT file, line, hook_name, dependency_vars FROM react_hooks"
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
                hook_node_id = f"{rel_file}::hook:{row['line']}"
                if hook_node_id not in nodes:
                    metadata = {
                        "status": "react_hook",
                        "hook_name": row["hook_name"],
                        "dependency_vars": row["dependency_vars"],
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
