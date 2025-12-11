"""Graph builder module - constructs dependency and call graphs."""

import os
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import click

from theauditor.ast_extractors.ast_parser import ASTParser
from theauditor.ast_extractors.module_resolver import ModuleResolver
from theauditor.indexer.config import SKIP_DIRS
from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.utils.logging import logger


@dataclass
class GraphNode:
    """Represents a node in the dependency or call graph."""

    id: str
    file: str
    lang: str | None = None
    loc: int = 0
    churn: int | None = None
    type: str = "module"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Represents an edge in the graph."""

    source: str
    target: str
    type: str = "import"
    file: str | None = None
    line: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def create_bidirectional_graph_edges(
    source: str,
    target: str,
    edge_type: str,
    file: str | None = None,
    line: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[GraphEdge]:
    """Create both forward and reverse edges for IFDS backward traversal.

    GRAPH FIX G3: Import/call graphs need reverse edges for taint analysis.
    Without reverse edges, IFDS analyzer cannot traverse backward through
    function boundaries, causing 99.6% of flows to hit max_depth.
    """
    if metadata is None:
        metadata = {}

    edges = []

    forward = GraphEdge(
        source=source,
        target=target,
        type=edge_type,
        file=file,
        line=line,
        metadata=metadata,
    )
    edges.append(forward)

    reverse_meta = metadata.copy()
    reverse_meta["is_reverse"] = True
    reverse_meta["original_type"] = edge_type

    reverse = GraphEdge(
        source=target,
        target=source,
        type=f"{edge_type}_reverse",
        file=file,
        line=line,
        metadata=reverse_meta,
    )
    edges.append(reverse)

    return edges


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
    score: float


@dataclass
class ImpactAnalysis:
    """Results of change impact analysis."""

    targets: list[str]
    upstream: list[str]
    downstream: list[str]
    total_impacted: int


class XGraphBuilder:
    """Build cross-project dependency and call graphs."""

    def __init__(
        self, batch_size: int = 200, exclude_patterns: list[str] = None, project_root: str = "."
    ):
        """Initialize builder with configuration."""
        self.batch_size = batch_size
        self.exclude_patterns = exclude_patterns or []
        self.checkpoint_file = Path(".pf/xgraph_checkpoint.json")
        self.project_root = Path(project_root).resolve()
        self.db_path = self.project_root / ".pf" / "repo_index.db"

        from theauditor.graph.db_cache import GraphDatabaseCache

        self.db_cache = GraphDatabaseCache(self.db_path)

        self.known_files = self.db_cache.known_files

        self.module_resolver = ModuleResolver(db_path=str(self.db_path))
        self.ast_parser = ASTParser()

    @lru_cache(maxsize=1024)  # noqa: B019 - singleton, lives entire session
    def _find_tsconfig_context(self, folder_path: Path) -> str:
        """Recursive lookup for the nearest tsconfig.json."""

        if (folder_path / "tsconfig.json").exists():
            try:
                return str(folder_path.relative_to(self.project_root)).replace("\\", "/")
            except ValueError:
                return "root"

        if folder_path == self.project_root or folder_path.parent == folder_path:
            return "root"

        return self._find_tsconfig_context(folder_path.parent)

    def detect_language(self, file_path: Path) -> str | None:
        """Detect language from file extension.

        Only languages with import resolution support in resolve_import_path.
        Bash/HCL have extractors but no meaningful import graphs.
        """
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".vue": "javascript",
            ".go": "go",
            ".rs": "rust",
        }
        return ext_map.get(file_path.suffix.lower())

    def should_skip(self, file_path: Path) -> bool:
        """Check if file should be skipped based on exclude patterns."""

        for part in file_path.parts:
            if part in SKIP_DIRS:
                return True

        path_str = str(file_path)
        return any(pattern in path_str for pattern in self.exclude_patterns)

    def extract_imports_from_db(self, rel_path: str) -> list[dict[str, Any]]:
        """Return structured import metadata for the given file."""
        return self.db_cache.get_imports(rel_path)

    def extract_imports(self, file_path: Path, lang: str) -> list[dict[str, Any]]:
        """Normalize file paths and fetch import metadata."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        return self.extract_imports_from_db(str(rel_path))

    def extract_exports_from_db(self, rel_path: str) -> list[dict[str, Any]]:
        """Return exported symbol metadata for the given file."""
        return self.db_cache.get_exports(rel_path)

    def extract_exports(self, file_path: Path, lang: str) -> list[dict[str, Any]]:
        """Wrapper that normalizes paths before querying exports."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        return self.extract_exports_from_db(str(rel_path))

    def extract_call_args_from_db(self, rel_path: str) -> list[dict[str, Any]]:
        """Return call argument metadata for the given file."""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT file, line, caller_function, callee_function,
                   argument_index, argument_expr, param_name, callee_file_path
              FROM function_call_args
             WHERE file = ?
            """,
            (rel_path,),
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

        db_path = str(rel_path).replace("\\", "/")
        return self.extract_call_args_from_db(db_path)

    def resolve_import_path(self, import_str: str, source_file: Path, lang: str) -> str:
        """Resolve import string to a normalized module path that matches actual files in the graph."""

        import_str = import_str.strip().strip("\"'`;")

        if lang == "python":
            if import_str.startswith("."):
                level = 0
                temp_str = import_str
                while temp_str.startswith("."):
                    level += 1
                    temp_str = temp_str[1:]

                module_name = temp_str

                current_dir = source_file.parent
                try:
                    for _ in range(level - 1):
                        current_dir = current_dir.parent
                except ValueError:
                    return f"external::{import_str}"

                try:
                    current_dir_rel = current_dir.relative_to(self.project_root)
                except ValueError:
                    current_dir_rel = current_dir

                if str(current_dir_rel) == ".":
                    rel_prefix = ""
                else:
                    rel_prefix = f"{str(current_dir_rel).replace(chr(92), '/')}/"

                if not module_name:
                    candidates = [f"{rel_prefix}__init__.py"]
                else:
                    base_path = module_name.replace(".", "/")
                    candidates = [
                        f"{rel_prefix}{base_path}.py",
                        f"{rel_prefix}{base_path}/__init__.py",
                    ]

                for candidate in candidates:
                    norm_candidate = str(candidate).replace("\\", "/")
                    if self.db_cache.file_exists(norm_candidate):
                        return norm_candidate

                return str(candidates[0]).replace("\\", "/")

            if "/" in import_str:
                return import_str.replace("\\", "/")

            parts = import_str.split(".")
            base_path = "/".join(parts)

            init_path = f"{base_path}/__init__.py"
            if self.db_cache.file_exists(init_path):
                return init_path

            module_path = f"{base_path}.py"
            if self.db_cache.file_exists(module_path):
                return module_path

            return module_path
        elif lang in ["javascript", "typescript"]:
            source_dir = source_file.parent

            try:
                str(source_file.relative_to(self.project_root)).replace("\\", "/")
            except ValueError:
                pass

            if import_str.startswith("@"):
                context = self._find_tsconfig_context(source_file.parent)

                resolved = self.module_resolver.resolve_with_context(
                    import_str, str(source_file), context
                )

                real_file = self.db_cache.resolve_filename(resolved)
                if real_file:
                    return real_file

                return resolved

            elif import_str.startswith("."):
                try:
                    rel_import = import_str.lstrip("./")

                    up_count = import_str.count("../")
                    current_dir = source_dir
                    for _ in range(up_count):
                        current_dir = current_dir.parent

                    if up_count > 0:
                        rel_import = import_str.replace("../", "")

                    target_path = current_dir / rel_import
                    rel_target = str(target_path.relative_to(self.project_root)).replace("\\", "/")

                    real_file = self.db_cache.resolve_filename(rel_target)
                    if real_file:
                        return real_file

                    return rel_target

                except (ValueError, OSError):
                    pass

            else:
                return import_str

            return import_str

        elif lang == "go":
            if import_str.startswith("./") or import_str.startswith("../"):
                source_dir = source_file.parent
                try:
                    up_count = import_str.count("../")
                    current_dir = source_dir
                    for _ in range(up_count):
                        current_dir = current_dir.parent

                    rel_import = import_str.replace("../", "").lstrip("./")
                    target_path = current_dir / rel_import

                    try:
                        rel_target = str(target_path.relative_to(self.project_root)).replace(
                            "\\", "/"
                        )
                    except ValueError:
                        rel_target = str(target_path).replace("\\", "/")

                    for suffix in ["", ".go"]:
                        candidate = f"{rel_target}{suffix}"
                        if self.db_cache.file_exists(candidate):
                            return candidate

                    return rel_target
                except (ValueError, OSError):
                    pass

            return import_str

        elif lang == "rust":
            if import_str.startswith("crate::"):
                module_path = import_str[7:].replace("::", "/")
                candidates = [
                    f"src/{module_path}.rs",
                    f"src/{module_path}/mod.rs",
                    f"{module_path}.rs",
                    f"{module_path}/mod.rs",
                ]
                for candidate in candidates:
                    if self.db_cache.file_exists(candidate):
                        return candidate
                return candidates[0]

            elif import_str.startswith("super::"):
                module_path = import_str[7:].replace("::", "/")
                source_dir = source_file.parent.parent
                try:
                    rel_dir = str(source_dir.relative_to(self.project_root)).replace("\\", "/")
                except ValueError:
                    rel_dir = str(source_dir).replace("\\", "/")

                rel_dir = "" if rel_dir == "." else f"{rel_dir}/"

                candidates = [
                    f"{rel_dir}{module_path}.rs",
                    f"{rel_dir}{module_path}/mod.rs",
                ]
                for candidate in candidates:
                    if self.db_cache.file_exists(candidate):
                        return candidate
                return candidates[0]

            elif import_str.startswith("self::"):
                module_path = import_str[6:].replace("::", "/")
                source_dir = source_file.parent
                try:
                    rel_dir = str(source_dir.relative_to(self.project_root)).replace("\\", "/")
                except ValueError:
                    rel_dir = str(source_dir).replace("\\", "/")

                rel_dir = "" if rel_dir == "." else f"{rel_dir}/"

                candidates = [
                    f"{rel_dir}{module_path}.rs",
                    f"{rel_dir}{module_path}/mod.rs",
                ]
                for candidate in candidates:
                    if self.db_cache.file_exists(candidate):
                        return candidate
                return candidates[0]

            return import_str

        else:
            return import_str

    def get_file_metrics(self, file_path: Path) -> dict[str, Any]:
        """Get basic metrics for a file from manifest/database."""

        return {"loc": 0, "churn": None}

    def _get_metrics_for(
        self, rel_path: str, manifest_lookup: dict[str, dict[str, Any]], root_path: Path
    ) -> tuple[int, Any]:
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

        manifest_lookup_rel: dict[str, dict[str, Any]] = {}
        files: list[tuple[Path, str]] = []

        if file_list is not None:
            for item in file_list:
                manifest_path = Path(item["path"])
                rel_path_str = str(manifest_path).replace("\\", "/")
                manifest_lookup_rel[rel_path_str] = item
                file = root_path / manifest_path
                lang = self.detect_language(manifest_path)
                if lang and (not langs or lang in langs):
                    files.append((file, lang))
        else:
            for dirpath, dirnames, filenames in os.walk(root_path):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                if self.exclude_patterns:
                    dirnames[:] = [
                        d
                        for d in dirnames
                        if not any(pattern in d for pattern in self.exclude_patterns)
                    ]
                for filename in filenames:
                    file = Path(dirpath) / filename
                    if not self.should_skip(file):
                        lang = self.detect_language(file)
                        if lang and (not langs or lang in langs):
                            files.append((file, lang))

        current_files = {}
        for file_path, lang in files:
            rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
            current_files[rel_path] = {"language": lang}

        with click.progressbar(
            files,
            label="Building import graph",
            show_pos=True,
            show_percent=True,
            show_eta=True,
            item_show_func=lambda x: str(x[0].name) if x else None,
        ) as bar:
            for file_path, lang in bar:
                rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
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
                    resolved = (
                        self.resolve_import_path(raw_value, file_path, lang)
                        if raw_value
                        else raw_value
                    )
                    resolved_norm = resolved.replace("\\", "/") if resolved else None

                    resolved_exists = (
                        self.db_cache.file_exists(resolved_norm) if resolved_norm else False
                    )

                    if resolved_exists:
                        target_id = resolved_norm
                        target_lang = current_files.get(resolved_norm, {}).get("language")
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

                    new_edges = create_bidirectional_graph_edges(
                        source=module_node.id,
                        target=target_id,
                        edge_type="import",
                        file=rel_path,
                        line=imp.get("line"),
                        metadata=edge_metadata,
                    )
                    edges.extend(new_edges)

        for file_path, lang in files:
            rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
            module_node = self._ensure_module_node(
                nodes,
                rel_path,
                lang,
                manifest_lookup_rel,
                root_path,
                status="cached",
            )
            module_node.metadata.setdefault("language", lang)
            module_node.metadata.setdefault(
                "import_count", module_node.metadata.get("import_count", 0)
            )

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(root_path),
                "languages": sorted({node.lang for node in nodes.values() if node.lang}),
                "total_files": len(nodes),
                "total_imports": len(edges),
            },
        }

        return FidelityToken.attach_manifest(result)

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
                manifest_path = Path(item["path"])
                rel_path_str = str(manifest_path).replace("\\", "/")
                manifest_lookup_rel[rel_path_str] = item
                file = root_path / manifest_path
                lang = self.detect_language(manifest_path)
                if lang and (not langs or lang in langs):
                    files.append((file, lang))
        else:
            for dirpath, dirnames, filenames in os.walk(root_path):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                if self.exclude_patterns:
                    dirnames[:] = [
                        d
                        for d in dirnames
                        if not any(pattern in d for pattern in self.exclude_patterns)
                    ]
                for filename in filenames:
                    file = Path(dirpath) / filename
                    if not self.should_skip(file):
                        lang = self.detect_language(file)
                        if lang and (not langs or lang in langs):
                            files.append((file, lang))

        current_files: dict[str, dict[str, Any]] = {}
        for file_path, lang in files:
            try:
                rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
            except ValueError:
                rel_path = str(file_path).replace("\\", "/")
            current_files[rel_path] = {"language": lang}

        function_defs: dict[str, set[str]] = defaultdict(set)
        function_lines: dict[tuple[str, str], int | None] = {}
        returns_map: dict[tuple[str, str], dict[str, Any]] = {}
        if self.db_path.exists():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT path, name, line FROM symbols WHERE type IN ('function', 'class')"
            )
            for row in cursor.fetchall():
                rel = row["path"].replace("\\", "/")
                function_defs[row["name"]].add(rel)
                function_lines[(rel, row["name"])] = row["line"]

            logger.info("Querying function returns from normalized schema...")
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
            logger.info("Processing function return data...")
            for row in cursor.fetchall():
                rel = row["file"].replace("\\", "/")
                returns_map[(rel, row["function_name"])] = {
                    "return_expr": row["return_expr"],
                    "return_vars": row["return_vars"],
                }
        else:
            conn = None

        def ensure_function_node(
            module_path: str, function_name: str, lang: str | None, status: str
        ) -> GraphNode:
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

        logger.info("Loading pre-resolved imports from import_styles.resolved_path...")
        file_imports_resolved: dict[str, set[str]] = {}

        with click.progressbar(
            files,
            label="Loading resolved imports",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: str(x[0].name) if x else None,
        ) as bar:
            for file_path, _lang in bar:
                rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
                resolved_imports = set(self.db_cache.get_resolved_imports(rel_path))
                file_imports_resolved[rel_path] = resolved_imports

        with click.progressbar(
            files,
            label="Building call graph",
            show_pos=True,
            show_percent=True,
            show_eta=True,
            item_show_func=lambda x: str(x[0].name) if x else None,
        ) as bar:
            for file_path, lang in bar:
                rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")

                resolved_imports = file_imports_resolved[rel_path]

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
                    func_node = ensure_function_node(
                        rel_path, export.get("name", ""), lang, "exported"
                    )
                    func_node.metadata.setdefault("symbol_type", export.get("symbol_type"))
                    func_node.metadata.setdefault("line", export.get("line"))

                call_records = self.extract_call_args(file_path, lang)
                for record in call_records:
                    caller = record.get("caller_function")
                    callee = record.get("callee_function")
                    line = record.get("line")
                    pre_resolved_path = record.get("callee_file_path")
                    caller_node = ensure_function_node(rel_path, caller, lang, "caller")

                    target_module = None
                    resolution_status = "unresolved"

                    # GRAPH FIX G8: Use pre-resolved callee_file_path from function_call_args
                    # when available. This correctly handles namespace imports like
                    # `import * as variantService from '@/services/variants'` where
                    # import_styles.resolved_path is NULL but the JS extractor already
                    # resolved the call target.
                    if pre_resolved_path:
                        normalized_pre = pre_resolved_path.replace("\\", "/")
                        # Check if it's a project file (not external like node_modules)
                        if normalized_pre in current_files:
                            target_module = normalized_pre
                            resolution_status = "pre_resolved"
                        elif not normalized_pre.startswith(
                            ("node_modules/", ".auditor_venv/", "external::")
                        ):
                            # Project file not in current_files but exists
                            if self.db_cache.file_exists(normalized_pre):
                                target_module = normalized_pre
                                resolution_status = "pre_resolved_db"

                    # ZERO FALLBACK: Single lookup path, no guessing
                    # If pre_resolved_path didn't work, try exact symbol lookup only
                    if not target_module:
                        # For namespace calls like variantService.createVariant, extract the function name
                        lookup_name = callee.split(".")[-1] if "." in callee else callee
                        target_candidates = function_defs.get(lookup_name, set())

                        if target_candidates:
                            # Priority 1: Defined in current file (local call)
                            if rel_path in target_candidates:
                                target_module = rel_path
                                resolution_status = "local_def"
                            else:
                                # Priority 2: Defined in exactly one imported file
                                matches = [c for c in target_candidates if c in resolved_imports]
                                if len(matches) == 1:
                                    target_module = matches[0]
                                    resolution_status = "imported_def"
                                # No guessing on ambiguous - mark as unresolved

                    if target_module:
                        target_lang = current_files.get(target_module, {}).get("language")
                        # For namespace imports (variantService.createVariant), use short name
                        # to match symbols table which has 'createVariant' not the full path
                        callee_name = callee.split(".")[-1] if "." in callee else callee
                        callee_node = ensure_function_node(
                            target_module, callee_name, target_lang, "callee"
                        )
                        resolved = True
                    else:
                        # Unresolved = external. No ambiguous guessing.
                        node_id = f"external::{callee}"
                        if node_id not in nodes:
                            nodes[node_id] = GraphNode(
                                id=node_id,
                                file=callee or "unknown",
                                lang=None,
                                loc=0,
                                churn=None,
                                type="external_function",
                                metadata={"status": "external"},
                            )
                        callee_node = nodes[node_id]
                        resolved = False

                    edge_metadata = {
                        "argument_index": record.get("argument_index"),
                        "argument_expr": record.get("argument_expr"),
                        "param_name": record.get("param_name"),
                        "resolved": resolved,
                        "resolution_status": resolution_status,
                    }
                    if target_module:
                        edge_metadata["callee_module"] = target_module

                    new_edges = create_bidirectional_graph_edges(
                        source=caller_node.id,
                        target=callee_node.id,
                        edge_type="call",
                        file=rel_path,
                        line=line,
                        metadata=edge_metadata,
                    )
                    edges.extend(new_edges)

        if self.db_path.exists():
            if conn is None:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            logger.info("Querying SQL queries from normalized schema...")
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
            logger.info(f"Found {len(sql_rows)} SQL query records")

            for row in sql_rows:
                rel_file = row["file_path"].replace("\\", "/")
                module_node = self._ensure_module_node(
                    nodes,
                    rel_file,
                    current_files.get(rel_file, {}).get("language"),
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
                        "snippet": (row["query_text"] or "")[:200],
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
                rel_file = row["file"].replace("\\", "/")
                module_node = self._ensure_module_node(
                    nodes,
                    rel_file,
                    current_files.get(rel_file, {}).get("language"),
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

            logger.info("Querying React hooks from normalized schema...")
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
            logger.info(f"Found {len(react_hook_rows)} React hook records")
            for row in react_hook_rows:
                rel_file = row["file"].replace("\\", "/")
                module_node = self._ensure_module_node(
                    nodes,
                    rel_file,
                    current_files.get(rel_file, {}).get("language"),
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
            rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
            module_node = self._ensure_module_node(
                nodes,
                rel_path,
                lang,
                manifest_lookup_rel,
                root_path,
                status="cached",
            )
            module_node.metadata.setdefault("language", lang)

        function_count = sum(1 for node in nodes.values() if node.type == "function")
        sql_count = sum(1 for node in nodes.values() if node.type == "sql_query")
        orm_count = sum(1 for node in nodes.values() if node.type == "orm_query")

        result = {
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

        return FidelityToken.attach_manifest(result)

    def merge_graphs(self, import_graph: dict, call_graph: dict) -> dict[str, Any]:
        """Merge import and call graphs into a unified graph."""

        nodes = {}
        for node in import_graph["nodes"]:
            nodes[node["id"]] = node
        for node in call_graph["nodes"]:
            nodes[node["id"]] = node

        edges = import_graph["edges"] + call_graph["edges"]

        result = {
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

        return FidelityToken.attach_manifest(result)
