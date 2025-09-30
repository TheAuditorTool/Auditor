"""TheAuditor Indexer Package.

This package provides modular, extensible code indexing functionality.
It includes:
- FileWalker for directory traversal with monorepo support
- DatabaseManager for SQLite operations
- Pluggable language extractors
- AST caching for performance
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from theauditor.config_runtime import load_runtime_config
from theauditor.ast_parser import ASTParser
from theauditor.framework_detector import FrameworkDetector

from .config import (
    DEFAULT_BATCH_SIZE, JS_BATCH_SIZE,
    SUPPORTED_AST_EXTENSIONS, SQL_EXTENSIONS, 
    DOCKERFILE_PATTERNS
)
from .core import FileWalker, ASTCache
from .database import DatabaseManager
from .extractors import ExtractorRegistry
from .extractors.docker import DockerExtractor
from .extractors.generic import GenericExtractor

logger = logging.getLogger(__name__)

FRAMEWORK_SAFE_SINK_DEFAULTS: Dict[str, List[Dict[str, str]]] = {
    "express": [
        {"sink_type": "response", "value": "res.json"},
        {"sink_type": "response", "value": "res.send"},
        {"sink_type": "response", "value": "res.status"},
        {"sink_type": "response", "value": "res.redirect"},
    ],
}


class IndexerOrchestrator:
    """Orchestrates the indexing process, coordinating all components."""
    
    def __init__(self, root_path: Path, db_path: str, 
                 batch_size: int = DEFAULT_BATCH_SIZE,
                 follow_symlinks: bool = False,
                 exclude_patterns: Optional[List[str]] = None):
        """Initialize the indexer orchestrator.
        
        Args:
            root_path: Project root path
            db_path: Path to SQLite database
            batch_size: Batch size for database operations
            follow_symlinks: Whether to follow symbolic links
            exclude_patterns: Patterns to exclude from indexing
        """
        self.root_path = root_path
        self.config = load_runtime_config(str(root_path))
        
        # Initialize components
        self.ast_parser = ASTParser()
        self.ast_cache = ASTCache(root_path)
        self.db_manager = DatabaseManager(db_path, batch_size)
        self.file_walker = FileWalker(
            root_path, self.config, follow_symlinks, exclude_patterns
        )
        self.extractor_registry = ExtractorRegistry(root_path, self.ast_parser)
        
        # Special extractors that don't follow standard extension mapping
        self.docker_extractor = DockerExtractor(root_path, self.ast_parser)
        self.generic_extractor = GenericExtractor(root_path, self.ast_parser)
        
        # Stats tracking
        self.counts = {
            "files": 0,
            "refs": 0,
            "routes": 0,
            "sql": 0,
            "sql_queries": 0,
            "symbols": 0,
            "docker": 0,
            "orm": 0
        }
    
    def index(self) -> Tuple[Dict[str, int], Dict[str, Any]]:
        """Run the complete indexing process with dual-pass JSX handling."""
        files, stats = self.file_walker.walk()

        if not files:
            print("[Indexer] No files found to index.")
            return self.counts, stats

        print(f"[Indexer] Processing {len(files)} files...")

        # Pre-compute useful maps for fast lookup
        file_info_by_path = {file_info["path"]: file_info for file_info in files}
        js_ts_paths: List[Path] = []
        jsx_paths: List[Path] = []

        for file_info in files:
            ext = file_info["ext"]
            if ext in [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]:
                path_obj = self.root_path / file_info["path"]
                js_ts_paths.append(path_obj)
                if ext in [".jsx", ".tsx"]:
                    jsx_paths.append(path_obj)

        # First pass: transformed JSX (default TypeScript emit)
        transformed_cache: Dict[str, Any] = {}
        if js_ts_paths:
            print(
                f"[Indexer] Batch processing {len(js_ts_paths)} JavaScript/TypeScript files (transformed mode)..."
            )
            transformed_cache = self._batch_parse_js(js_ts_paths, jsx_mode="transformed")

        self._persist_frameworks()

        # Process all files with transformed data landing in standard tables
        for idx, file_info in enumerate(files):
            if os.environ.get("THEAUDITOR_DEBUG") and idx % 50 == 0:
                print(
                    f"[INDEXER_DEBUG] Processing file {idx + 1}/{len(files)}: {file_info['path']}",
                    file=sys.stderr,
                )

            ext = file_info["ext"]
            jsx_mode = "transformed" if ext in [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"] else None

            self._process_file(
                file_info,
                cache_lookup=transformed_cache,
                jsx_mode=jsx_mode,
                extraction_pass=1,
                target="standard",
                store_file_record=True,
            )

            if (idx + 1) % self.db_manager.batch_size == 0:
                self.db_manager.flush_batch()

        # Second pass: preserved JSX for `.jsx`/`.tsx` files only
        if jsx_paths:
            print(
                f"[Indexer] Re-parsing {len(jsx_paths)} JSX files in preserved mode for parallel tables..."
            )
            preserved_cache = self._batch_parse_js(jsx_paths, jsx_mode="preserved")

            for idx, path_obj in enumerate(jsx_paths):
                rel_path = str(path_obj.relative_to(self.root_path)).replace("\\", "/")
                file_info = file_info_by_path.get(rel_path)
                if not file_info:
                    continue

                self._process_file(
                    file_info,
                    cache_lookup=preserved_cache,
                    jsx_mode="preserved",
                    extraction_pass=2,
                    target="jsx",
                    store_file_record=False,
                )

                if (idx + 1) % self.db_manager.batch_size == 0:
                    self.db_manager.flush_batch()

        # Final flush & commit
        self.db_manager.flush_batch()
        self.db_manager.commit()

        print(
            f"[Indexer] Indexed {self.counts['files']} files, {self.counts['symbols']} symbols,"
            f" {self.counts['refs']} imports, {self.counts['routes']} routes"
        )
        print(f"[Indexer] Database updated: {self.db_manager.db_path}")

        return self.counts, stats

    def _batch_parse_js(self, paths: List[Path], jsx_mode: str) -> Dict[str, Any]:
        """Parse JavaScript/TypeScript files in batches for a specific JSX mode."""
        cache: Dict[str, Any] = {}
        if not paths:
            return cache

        try:
            for i in range(0, len(paths), JS_BATCH_SIZE):
                batch = paths[i:i + JS_BATCH_SIZE]
                batch_trees = self.ast_parser.parse_files_batch(
                    batch,
                    root_path=str(self.root_path),
                    jsx_mode=jsx_mode,
                )
                for file_path in batch:
                    key = str(file_path.resolve()).replace("\\", "/")
                    tree = batch_trees.get(key)
                    if tree:
                        cache[key] = tree
        except Exception as exc:  # pragma: no cover - defensive logging
            print(
                f"[Indexer] Batch processing failed for {jsx_mode} mode, falling back to per-file parsing: {exc}"
            )
            return {}

        return cache

    def _persist_frameworks(self) -> None:
        """Run inline framework detection and persist results before indexing."""
        try:
            detector = FrameworkDetector(self.root_path)
            frameworks = detector.detect_all()
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[Indexer] Framework detection failed: {exc}")
            return

        if not frameworks:
            return

        primary_by_language: Dict[str, Dict[str, Any]] = {}
        for fw in frameworks:
            language = fw.get("language", "unknown")
            current = primary_by_language.get(language)
            if not current or fw.get("path") in (".", ""):
                primary_by_language[language] = fw

        for fw in frameworks:
            is_primary = fw is primary_by_language.get(fw.get("language", "unknown"))
            self.db_manager.add_framework(
                fw.get("framework", "unknown"),
                fw.get("language", "unknown"),
                fw.get("version"),
                fw.get("source"),
                fw.get("path"),
                is_primary,
            )

            for sink in FRAMEWORK_SAFE_SINK_DEFAULTS.get(fw.get("framework", ""), []):
                self.db_manager.add_framework_safe_sink(
                    fw.get("framework", "unknown"),
                    sink.get("sink_type", "custom"),
                    sink.get("value", ""),
                )

        self._write_framework_artifact(frameworks)

    def _write_framework_artifact(self, frameworks: List[Dict[str, Any]]) -> None:
        raw_dir = self.root_path / ".pf" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = raw_dir / "frameworks.json"
        with open(artifact_path, "w", encoding="utf-8") as handle:
            json.dump({"frameworks": frameworks}, handle, indent=2, sort_keys=True)

    def _process_file(
        self,
        file_info: Dict[str, Any],
        cache_lookup: Dict[str, Any],
        *,
        jsx_mode: Optional[str],
        extraction_pass: int,
        target: str,
        store_file_record: bool,
    ) -> None:
        """Process a single file for either the standard or JSX-preserved pass."""
        file_path = self.root_path / file_info["path"]
        ext = file_info["ext"]

        if store_file_record:
            self.db_manager.add_file(
                file_info["path"],
                file_info["sha256"],
                ext,
                file_info["bytes"],
                file_info["loc"],
            )
            self.counts["files"] += 1

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as handle:
                content = handle.read(256 * 1024)
        except Exception as exc:  # pragma: no cover - debug aid
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Cannot read {file_path}: {exc}")
            return

        if extraction_pass == 1 and file_info["path"].endswith("tsconfig.json"):
            context_dir = None
            if "backend/" in file_info["path"]:
                context_dir = "backend"
            elif "frontend/" in file_info["path"]:
                context_dir = "frontend"

            self.db_manager.add_config_file(
                file_info["path"],
                content,
                "tsconfig",
                context_dir,
            )

        tree = self._get_or_parse_ast(
            file_info,
            file_path,
            cache_lookup,
            jsx_mode=jsx_mode,
        )

        extractor = self._select_extractor(file_info["path"], ext)
        if not extractor:
            return

        enriched_info = dict(file_info)
        enriched_info["jsx_mode"] = jsx_mode
        enriched_info["extraction_pass"] = extraction_pass

        try:
            extracted = extractor.extract(enriched_info, content, tree)
        except Exception as exc:  # pragma: no cover - debug aid
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Extraction failed for {file_path}: {exc}")
            return

        self._store_extracted_data(
            file_info["path"],
            extracted,
            target=target,
            jsx_mode=jsx_mode,
            extraction_pass=extraction_pass,
        )
    
    def _get_or_parse_ast(
        self,
        file_info: Dict[str, Any],
        file_path: Path,
        js_ts_cache: Dict[str, Any],
        *,
        jsx_mode: Optional[str],
    ) -> Optional[Dict]:
        """Get AST from cache or parse the file.
        
        Args:
            file_info: File metadata
            file_path: Path to the file
            js_ts_cache: Cache of pre-parsed JS/TS ASTs
            
        Returns:
            Parsed AST tree or None
        """
        if file_info['ext'] not in SUPPORTED_AST_EXTENSIONS:
            return None
        
        # Check JS/TS batch cache
        file_str = str(file_path.resolve()).replace("\\", "/")
        if file_str in js_ts_cache:
            return js_ts_cache[file_str]

        # Check persistent AST cache
        cache_namespace = f"jsx_{jsx_mode}" if jsx_mode else "default"
        cached_tree = self.ast_cache.get(file_info['sha256'], namespace=cache_namespace)
        if cached_tree:
            return cached_tree

        # Parse the file
        tree = self.ast_parser.parse_file(
            file_path,
            root_path=str(self.root_path),
            jsx_mode=jsx_mode,
        )

        # Cache the result if it's JSON-serializable
        if tree and isinstance(tree, dict):
            self.ast_cache.set(file_info['sha256'], tree, namespace=cache_namespace)

        return tree
    
    def _select_extractor(self, file_path: str, file_ext: str):
        """Select the appropriate extractor for a file.
        
        Args:
            file_path: Path to the file
            file_ext: File extension
            
        Returns:
            Appropriate extractor instance or None
        """
        # Check special extractors first (by filename pattern)
        if self.docker_extractor.should_extract(file_path):
            return self.docker_extractor
        if self.generic_extractor.should_extract(file_path):
            return self.generic_extractor
        
        # Use registry for standard extension-based extraction
        return self.extractor_registry.get_extractor(file_ext)
    
    def _store_extracted_data(
        self,
        file_path: str,
        extracted: Dict[str, Any],
        *,
        target: str,
        jsx_mode: Optional[str],
        extraction_pass: int,
    ) -> None:
        """Store extracted data in the database.

        Args:
            file_path: Path to the source file
            extracted: Dictionary of extracted data
        """
        # Standard pass writes into legacy tables
        if target == "standard":
            if 'imports' in extracted:
                for kind, value in extracted['imports']:
                    resolved = extracted.get('resolved_imports', {}).get(value, value)
                    self.db_manager.add_ref(file_path, kind, resolved)
                    self.counts['refs'] += 1

            if 'routes' in extracted:
                for method, pattern, controls in extracted['routes']:
                    self.db_manager.add_endpoint(file_path, method, pattern, controls)
                    self.counts['routes'] += 1

            if 'sql_objects' in extracted:
                for kind, name in extracted['sql_objects']:
                    self.db_manager.add_sql_object(file_path, kind, name)
                    self.counts['sql'] += 1

            if 'sql_queries' in extracted:
                for query in extracted['sql_queries']:
                    self.db_manager.add_sql_query(
                        file_path,
                        query['line'],
                        query['query_text'],
                        query['command'],
                        query['tables'],
                    )
                    self.counts['sql_queries'] += 1

            if 'symbols' in extracted:
                for symbol in extracted['symbols']:
                    self.db_manager.add_symbol(
                        file_path,
                        symbol['name'],
                        symbol['type'],
                        symbol['line'],
                        symbol['col'],
                    )
                    self.counts['symbols'] += 1

            if 'orm_queries' in extracted:
                for query in extracted['orm_queries']:
                    self.db_manager.add_orm_query(
                        file_path,
                        query['line'],
                        query['query_type'],
                        query.get('includes'),
                        query.get('has_limit', False),
                        query.get('has_transaction', False),
                    )
                    self.counts['orm'] += 1

            if 'docker_info' in extracted and extracted['docker_info']:
                info = extracted['docker_info']
                self.db_manager.add_docker_image(
                    file_path,
                    info.get('base_image'),
                    info.get('exposed_ports', []),
                    info.get('env_vars', {}),
                    info.get('build_args', {}),
                    info.get('user'),
                    info.get('has_healthcheck', False),
                )
                self.counts['docker'] += 1

            if 'docker_issues' in extracted:
                for issue in extracted['docker_issues']:
                    self.db_manager.add_docker_issue(
                        file_path,
                        issue['line'],
                        issue['issue_type'],
                        issue['severity'],
                    )

            if 'assignments' in extracted:
                for assignment in extracted['assignments']:
                    self.db_manager.add_assignment(
                        file_path,
                        assignment['line'],
                        assignment['target_var'],
                        assignment['source_expr'],
                        assignment['source_vars'],
                        assignment['in_function'],
                    )

            if 'function_calls' in extracted:
                for call in extracted['function_calls']:
                    self.db_manager.add_function_call_arg(
                        file_path,
                        call['line'],
                        call['caller_function'],
                        call['callee_function'],
                        call['argument_index'],
                        call['argument_expr'],
                        call['param_name'],
                    )

            if 'returns' in extracted:
                for ret in extracted['returns']:
                    self.db_manager.add_function_return(
                        file_path,
                        ret['line'],
                        ret['function_name'],
                        ret['return_expr'],
                        ret['return_vars'],
                    )

        # Preserved pass writes into JSX-aware tables + React metadata
        if target == "jsx":
            jsx_mode_normalized = jsx_mode or "preserved"

            for symbol in extracted.get('symbols', []):
                self.db_manager.add_symbol_jsx(
                    file_path,
                    symbol['name'],
                    symbol['type'],
                    symbol['line'],
                    symbol['col'],
                    jsx_mode_normalized,
                    extraction_pass,
                )

            for assignment in extracted.get('assignments', []):
                self.db_manager.add_assignment_jsx(
                    file_path,
                    assignment['line'],
                    assignment['target_var'],
                    assignment['source_expr'],
                    assignment['source_vars'],
                    assignment['in_function'],
                    jsx_mode_normalized,
                    extraction_pass,
                )

            for call in extracted.get('function_calls', []):
                self.db_manager.add_function_call_arg_jsx(
                    file_path,
                    call['line'],
                    call['caller_function'],
                    call['callee_function'],
                    call['argument_index'],
                    call['argument_expr'],
                    call['param_name'],
                    jsx_mode_normalized,
                    extraction_pass,
                )

            for ret in extracted.get('returns', []):
                self.db_manager.add_function_return_jsx(
                    file_path,
                    ret['line'],
                    ret['function_name'],
                    ret['return_expr'],
                    ret['return_vars'],
                    ret.get('has_jsx', False),
                    jsx_mode_normalized,
                    extraction_pass,
                )

            for component in extracted.get('react_components', []):
                self.db_manager.add_react_component(
                    file_path,
                    component['name'],
                    component.get('line'),
                    component.get('col'),
                    component.get('export'),
                    component.get('hook_calls', 0),
                )

            for hook in extracted.get('react_hooks', []):
                self.db_manager.add_react_hook(
                    file_path,
                    hook['name'],
                    hook.get('component'),
                    hook.get('line'),
                    hook.get('col'),
                )


# Import backward compatibility functions from the compat module
from ..indexer_compat import (
    build_index,
    walk_directory,
    populate_database,
    extract_imports,
    extract_routes,
    extract_sql_objects,
    extract_sql_queries
)

# Backward compatibility exports
__all__ = [
    'IndexerOrchestrator',
    'FileWalker',
    'DatabaseManager',
    'ASTCache',
    'ExtractorRegistry',
    # Backward compat functions
    'build_index',
    'walk_directory',
    'populate_database',
    'extract_imports',
    'extract_routes', 
    'extract_sql_objects',
    'extract_sql_queries'
]
