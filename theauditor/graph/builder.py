"""Graph builder module - constructs dependency and call graphs."""

import os
import platform
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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


@dataclass
class GraphEdge:
    """Represents an edge in the graph."""

    source: str
    target: str
    type: str = "import"  # import, call, extends, implements
    file: str | None = None
    line: int | None = None


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
        self.module_resolver = ModuleResolver()  # No project_root - uses database!
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

    def extract_imports_from_db(self, rel_path: str) -> list[str]:
        """Extract import statements from the database where indexer already stored them.
        
        Args:
            rel_path: Relative path as stored in the database (e.g., "backend/src/app.ts")
            
        Returns:
            List of import targets
        """
        import sqlite3
        
        # Query the refs table for imports
        db_file = self.project_root / ".pf" / "repo_index.db"
        if not db_file.exists():
            print(f"Warning: Database not found at {db_file}")
            return []
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get all imports for this file from refs table
            # The indexer stores imports with kind like 'import', 'require', etc.
            cursor.execute(
                "SELECT value FROM refs WHERE src = ? AND kind IN ('import', 'require', 'from', 'import_type', 'export')",
                (rel_path,)
            )
            
            imports = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return imports
            
        except sqlite3.Error as e:
            print(f"Warning: Failed to read imports from database: {e}")
            return []

    def extract_imports(self, file_path: Path, lang: str) -> list[str]:
        """Extract import statements from the database where indexer already stored them.
        
        The indexer has already extracted all imports and stored them in the refs table.
        We should read from there instead of re-parsing files.
        """
        import sqlite3
        
        # Get relative path for database lookup
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            # If file_path is already relative or from a different root
            rel_path = file_path
        
        # Normalize path separators for database lookup
        db_path = str(rel_path).replace("\\", "/")
        
        # Query the refs table for imports
        db_file = self.project_root / ".pf" / "repo_index.db"
        if not db_file.exists():
            print(f"Warning: Database not found at {db_file}")
            return []
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get all imports for this file from refs table
            # The indexer stores imports with kind like 'import', 'require', etc.
            cursor.execute(
                "SELECT value FROM refs WHERE src = ? AND kind IN ('import', 'require', 'from', 'import_type', 'export')",
                (db_path,)
            )
            
            imports = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return imports
            
        except sqlite3.Error as e:
            print(f"Warning: Failed to read imports from database: {e}")
            return []

    def extract_exports_from_db(self, rel_path: str) -> list[str]:
        """Extract exported symbols from the database where indexer already stored them.
        
        Args:
            rel_path: Relative path as stored in the database
            
        Returns:
            List of exported symbol names
        """
        import sqlite3
        
        db_file = self.project_root / ".pf" / "repo_index.db"
        if not db_file.exists():
            return []
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get exported functions/classes from symbols table
            # The indexer stores these as 'function' and 'class' types
            cursor.execute(
                "SELECT name FROM symbols WHERE path = ? AND type IN ('function', 'class')",
                (rel_path,)
            )
            
            exports = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return exports
            
        except sqlite3.Error:
            return []

    def extract_exports(self, file_path: Path, lang: str) -> list[str]:
        """Extract exported symbols from the database where indexer already stored them.

        The indexer has already extracted all exports and stored them in the symbols table.
        We read from there instead of re-parsing files.

        Args:
            file_path: Path to the source file
            lang: Programming language (not used, kept for API compatibility)

        Returns:
            List of exported symbol names
        """
        # Get relative path for database lookup
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            # If file_path is already relative or from a different root
            rel_path = file_path

        # Normalize path separators for database lookup
        db_path = str(rel_path).replace("\\", "/")

        # Query database for exports
        return self.extract_exports_from_db(db_path)

    def extract_calls_from_db(self, rel_path: str) -> list[tuple[str, str | None]]:
        """Extract function calls from the database where indexer already stored them.
        
        Args:
            rel_path: Relative path as stored in the database
            
        Returns:
            List of (function_name, None) tuples for calls
        """
        import sqlite3
        
        db_file = self.project_root / ".pf" / "repo_index.db"
        if not db_file.exists():
            return []
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get function calls from symbols table
            # The indexer stores these as 'call' type
            cursor.execute(
                "SELECT name FROM symbols WHERE path = ? AND type = 'call'",
                (rel_path,)
            )
            
            # Return as tuples with None for second element (no parent info)
            calls = [(row[0], None) for row in cursor.fetchall()]
            conn.close()
            
            return calls
            
        except sqlite3.Error:
            return []

    def extract_calls(self, file_path: Path, lang: str) -> list[tuple[str, str | None]]:
        """Extract function calls from the database where indexer already stored them.

        The indexer has already extracted all function calls and stored them in the symbols table.
        We read from there instead of re-parsing files.

        Args:
            file_path: Path to the source file
            lang: Programming language (not used, kept for API compatibility)

        Returns:
            List of (function_name, None) tuples for calls
        """
        # Get relative path for database lookup
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            # If file_path is already relative or from a different root
            rel_path = file_path

        # Normalize path separators for database lookup
        db_path = str(rel_path).replace("\\", "/")

        # Query database for calls
        return self.extract_calls_from_db(db_path)

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
                    db_file = self.project_root / ".pf" / "repo_index.db"
                    if db_file.exists():
                        try:
                            conn = sqlite3.connect(db_file)
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
                    db_file = self.project_root / ".pf" / "repo_index.db"
                    if db_file.exists():
                        try:
                            conn = sqlite3.connect(db_file)
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

    def build_import_graph(
        self,
        root: str = ".",
        langs: list[str] | None = None,
        file_filter: str | None = None,
        file_list: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build import/dependency graph for the project."""
        root_path = Path(root).resolve()
        nodes = {}
        edges = []
        
        # Initialize graph cache for incremental updates
        from ..cache.graph_cache import GraphCache
        cache_dir = root_path / ".pf" / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        graph_cache = GraphCache(cache_dir)

        # Collect all source files
        files = []
        manifest_lookup = {}  # Map file paths to manifest items for metrics
        
        if file_list is not None:
            # Use provided file list from manifest
            # The manifest already contains all the file info we need
            for item in file_list:
                manifest_path = Path(item['path'])
                
                # Use the path from manifest directly - we don't need actual files
                # The manifest has all the data (path, ext, content, etc.)
                file = root_path / manifest_path  # Just for consistent path handling
                
                # Store manifest item for later metric lookup
                manifest_lookup[str(file)] = item
                
                # Detect language from extension in manifest
                lang = self.detect_language(manifest_path)  # Use manifest path
                if lang and (not langs or lang in langs):
                    files.append((file, lang))
        else:
            # Fall back to original os.walk logic for backward compatibility
            for dirpath, dirnames, filenames in os.walk(root_path):
                # CRITICAL: Prune excluded directories before os.walk descends into them
                # This prevents traversal into .venv and other SKIP_DIRS
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                
                # Also prune based on exclude_patterns
                if self.exclude_patterns:
                    dirnames[:] = [d for d in dirnames 
                                  if not any(pattern in d for pattern in self.exclude_patterns)]
                
                # Process files in this directory
                for filename in filenames:
                    file = Path(dirpath) / filename
                    if not self.should_skip(file):
                        lang = self.detect_language(file)
                        if lang and (not langs or lang in langs):
                            files.append((file, lang))

        # Compute file hashes for cache lookup
        import hashlib
        current_files = {}
        for file_path, lang in files:
            try:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
                current_files[rel_path] = {
                    'hash': file_hash,
                    'language': lang,
                    'size': file_path.stat().st_size
                }
            except (OSError, PermissionError):
                pass
        
        # Check for changed files using cache
        added, removed, modified = graph_cache.get_changed_files(
            {path: info['hash'] for path, info in current_files.items()}
        )
        
        # Load cached edges for unchanged files
        cached_edges = graph_cache.get_all_edges()
        valid_cached_edges = []
        
        # Filter out edges from removed/modified files
        invalidated = added | removed | modified
        for source, target, edge_type, metadata in cached_edges:
            if source not in invalidated:
                valid_cached_edges.append({
                    'source': source,
                    'target': target,
                    'type': edge_type
                })
        
        # Only process changed files
        files_to_process = []
        for file_path, lang in files:
            rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
            if rel_path in invalidated:
                files_to_process.append((file_path, lang))
        
        print(f"[Graph Cache] Using {len(valid_cached_edges)} cached edges, processing {len(files_to_process)} changed files")
        
        # Invalidate edges for changed files
        if invalidated:
            graph_cache.invalidate_edges(invalidated)
        
        # Process only changed files with progress bar
        new_edges = []
        with click.progressbar(
            files_to_process,
            label="Building import graph (incremental)",
            show_pos=True,
            show_percent=True,
            show_eta=True,
            item_show_func=lambda x: str(x[0].name) if x else None,
        ) as bar:
            for file_path, lang in bar:
                # Create node for this file
                rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")  # Normalize separators
                node_id = rel_path  # Already normalized

                # Get metrics from manifest if available, otherwise from file
                if str(file_path) in manifest_lookup:
                    # Use manifest data which already has metrics
                    manifest_item = manifest_lookup[str(file_path)]
                    loc = manifest_item.get('loc', 0)
                    churn = None  # Manifest doesn't have churn data
                else:
                    # Fall back to reading file metrics
                    metrics = self.get_file_metrics(file_path)
                    loc = metrics["loc"]
                    churn = metrics["churn"]
                
                node = GraphNode(
                    id=node_id,
                    file=rel_path,  # Already normalized
                    lang=lang,
                    loc=loc,
                    churn=churn,
                    type="module",
                )
                nodes[node_id] = asdict(node)

                # Extract imports and create edges
                # Pass the relative path that matches what's in the database
                imports = self.extract_imports_from_db(rel_path)
                for imp in imports:
                    target = self.resolve_import_path(imp, file_path, lang)
                    edge = GraphEdge(
                        source=node_id,
                        target=target,
                        type="import",
                        file=rel_path,  # Already normalized
                    )
                    edges.append(asdict(edge))
                    new_edges.append((node_id, target, "import", None))
        
        # Add cached edges to the result
        edges.extend(valid_cached_edges)
        
        # Update cache with new edges and file states
        if new_edges:
            graph_cache.add_edges(new_edges)
        if current_files:
            graph_cache.update_file_states(current_files)
        if removed:
            graph_cache.remove_file_states(removed)
        
        # Create nodes for all files (including cached ones)
        for file_path, lang in files:
            rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
            if rel_path not in nodes:
                # Get metrics
                if str(file_path) in manifest_lookup:
                    manifest_item = manifest_lookup[str(file_path)]
                    loc = manifest_item.get('loc', 0)
                    churn = None
                else:
                    metrics = self.get_file_metrics(file_path)
                    loc = metrics["loc"]
                    churn = metrics["churn"]
                
                node = GraphNode(
                    id=rel_path,
                    file=rel_path,
                    lang=lang,
                    loc=loc,
                    churn=churn,
                    type="module",
                )
                nodes[rel_path] = asdict(node)

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "metadata": {
                "root": str(root_path),
                "languages": list(set(n["lang"] for n in nodes.values())),
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
        nodes = {}
        edges = []

        # Collect all source files
        files = []
        
        if file_list is not None:
            # Use provided file list from manifest
            # The manifest already contains all the file info we need
            for item in file_list:
                manifest_path = Path(item['path'])
                
                # Use the path from manifest directly - we don't need actual files
                # The manifest has all the data (path, ext, content, etc.)
                file = root_path / manifest_path  # Just for consistent path handling
                
                # Detect language from extension in manifest
                lang = self.detect_language(manifest_path)  # Use manifest path
                if lang and (not langs or lang in langs):
                    files.append((file, lang))
        else:
            # Fall back to original os.walk logic for backward compatibility
            for dirpath, dirnames, filenames in os.walk(root_path):
                # CRITICAL: Prune excluded directories before os.walk descends into them
                # This prevents traversal into .venv and other SKIP_DIRS
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                
                # Also prune based on exclude_patterns
                if self.exclude_patterns:
                    dirnames[:] = [d for d in dirnames 
                                  if not any(pattern in d for pattern in self.exclude_patterns)]
                
                # Process files in this directory
                for filename in filenames:
                    file = Path(dirpath) / filename
                    if not self.should_skip(file):
                        lang = self.detect_language(file)
                        if lang and (not langs or lang in langs):
                            files.append((file, lang))

        # Process files with progress bar to extract functions and calls
        with click.progressbar(
            files,
            label="Building call graph",
            show_pos=True,
            show_percent=True,
            show_eta=True,
            item_show_func=lambda x: str(x[0].name) if x else None,
        ) as bar:
            for file_path, lang in bar:
                rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")  # Normalize separators
                module_id = rel_path  # Already normalized

                # Extract exported functions/classes from database
                exports = self.extract_exports_from_db(rel_path)
                for export in exports:
                    func_id = f"{module_id}::{export}"
                    node = GraphNode(
                        id=func_id,
                        file=rel_path,  # Already normalized
                        lang=lang,
                        type="function",
                    )
                    nodes[func_id] = asdict(node)

                # Extract calls from database
                calls = self.extract_calls_from_db(rel_path)
                for call, method in calls:
                    # Try to resolve the call target
                    if method:
                        # Method call
                        target_id = f"{call}.{method}"
                    else:
                        # Function call
                        target_id = call

                    # Create edge from module to called function
                    edge = GraphEdge(
                        source=module_id,
                        target=target_id,
                        type="call",
                        file=rel_path,  # Already normalized
                    )
                    edges.append(asdict(edge))

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "metadata": {
                "root": str(root_path),
                "languages": langs or [],
                "total_functions": len(nodes),
                "total_calls": len(edges),
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



