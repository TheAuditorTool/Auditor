"""Indexer orchestration logic.

This module contains the IndexerOrchestrator class that coordinates:
- File walking and discovery
- AST parsing and caching
- Extractor coordination
- Database storage (via DataStorer)
- JSX dual-pass processing

The orchestrator implements the main indexing workflow while delegating
specialized concerns to focused modules (storage, extractors, database).

CRITICAL SCHEMA NOTE: When adding new tables to any schema file:
1. Add the table definition to the appropriate schema file (e.g., node_schema.py)
2. Add storage handler to the corresponding storage file (e.g., node_storage.py)
3. Add database method to the corresponding database file (e.g., node_database.py)
4. Update table count in schema.py
5. RUN: python -m theauditor.indexer.schemas.codegen
   This regenerates generated_cache.py which taint analysis uses for memory loading!
   WITHOUT THIS STEP, YOUR TABLE WON'T BE ACCESSIBLE TO THE ANALYZER!
"""


import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from theauditor.config_runtime import load_runtime_config
from theauditor.ast_parser import ASTParser

from .config import (
    DEFAULT_BATCH_SIZE, JS_BATCH_SIZE,
    SUPPORTED_AST_EXTENSIONS, SQL_EXTENSIONS,
    DOCKERFILE_PATTERNS
)
from .core import FileWalker, ASTCache
from .database import DatabaseManager
from .storage import DataStorer
from .extractors import ExtractorRegistry
from .extractors.docker import DockerExtractor
from .extractors.generic import GenericExtractor
from .extractors.github_actions import GitHubWorkflowExtractor

logger = logging.getLogger(__name__)


class IndexerOrchestrator:
    """Orchestrates the indexing process, coordinating all components."""

    def __init__(self, root_path: Path, db_path: str,
                 batch_size: int = DEFAULT_BATCH_SIZE,
                 follow_symlinks: bool = False,
                 exclude_patterns: list[str] | None = None):
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
        # ASTCache now expects cache_dir, not root_path
        cache_dir = root_path / ".pf" / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.ast_cache = ASTCache(cache_dir)
        self.db_manager = DatabaseManager(db_path, batch_size)
        self.file_walker = FileWalker(
            root_path, self.config, follow_symlinks, exclude_patterns
        )
        self.extractor_registry = ExtractorRegistry(root_path, self.ast_parser)

        # Special extractors that don't follow standard extension mapping
        self.docker_extractor = DockerExtractor(root_path, self.ast_parser)
        self.generic_extractor = GenericExtractor(root_path, self.ast_parser)
        self.github_workflow_extractor = GitHubWorkflowExtractor(root_path, self.ast_parser)

        # Inject db_manager into special extractors (Phase 3C fix)
        # GenericExtractor uses database-first architecture and needs direct access
        self.docker_extractor.db_manager = self.db_manager
        self.generic_extractor.db_manager = self.db_manager
        self.github_workflow_extractor.db_manager = self.db_manager

        # Inject db_manager into registry extractors that need it
        # PrismaExtractor and any other database-first extractors
        for ext in self.extractor_registry.extractors.values():
            if hasattr(ext, 'extract') and not hasattr(ext, 'db_manager'):
                # Check if extractor uses db_manager by inspecting its code
                import inspect
                source = inspect.getsource(ext.extract)
                if 'self.db_manager' in source:
                    ext.db_manager = self.db_manager

        # Stats tracking
        self.counts = {
            "files": 0,
            "refs": 0,
            "routes": 0,
            "sql": 0,
            "sql_queries": 0,
            "symbols": 0,
            "docker": 0,
            "orm": 0,
            "react_components": 0,
            "react_hooks": 0,
            # Data flow tracking
            "assignments": 0,
            "function_calls": 0,
            "returns": 0,
            "variable_usage": 0,
            "object_literals": 0,  # PHASE 3: Object literal properties
            # Control flow tracking
            "cfg_blocks": 0,
            "cfg_edges": 0,
            "cfg_statements": 0,
            # Type annotations
            "type_annotations": 0,
            "type_annotations_typescript": 0,
            "type_annotations_python": 0,
            "type_annotations_rust": 0,
            # Configuration
            "frameworks": 0,
            "package_configs": 0,
            "config_files": 0,
            # CI/CD
            "github_workflows": 0,
        }

        # Initialize DataStorer for storage operations (after counts)
        self.data_storer = DataStorer(self.db_manager, self.counts)

    def _detect_frameworks_inline(self) -> list[dict]:
        """Detect frameworks inline without file dependency.

        Replaces file-based loading with direct detection to avoid
        chicken-and-egg problem where frameworks.json doesn't exist
        until after indexer runs.

        Stores results to frameworks table via _store_frameworks() call
        at line 229 after second JSX pass completes.

        Returns:
            List of framework dictionaries with keys:
            - framework: str (e.g., "express", "react")
            - version: str (e.g., "4.18.2" or "unknown")
            - language: str (e.g., "javascript", "python")
            - path: str (e.g., "." or "backend" for monorepos)
            - source: str (e.g., "package.json", "requirements.txt")
        """
        from theauditor.framework_detector import FrameworkDetector

        try:
            # Run detection directly on project
            detector = FrameworkDetector(self.root_path, exclude_patterns=[])
            frameworks = detector.detect_all()

            # Save to file for backward compatibility with external tools
            try:
                save_path = self.root_path / ".pf" / "raw" / "frameworks.json"
                save_path.parent.mkdir(parents=True, exist_ok=True)
                detector.save_to_file(save_path)
            except Exception as save_error:
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] Could not save frameworks.json: {save_error}")

            return frameworks

        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Framework detection failed: {e}")
            return []

    def _store_frameworks(self):
        """Store loaded frameworks in database.

        Stores framework information and registers safe sinks for Express.
        """
        for fw in self.frameworks:
            self.db_manager.add_framework(
                name=fw.get('framework'),
                version=fw.get('version'),
                language=fw.get('language'),
                path=fw.get('path', '.'),
                source=fw.get('source'),
                is_primary=(fw.get('path', '.') == '.')
            )
            self.counts['frameworks'] += 1

        # Flush frameworks batch to database BEFORE querying for IDs
        self.db_manager.flush_batch()
        self.db_manager.commit()

        # Add safe sinks for Express (res.json, res.jsonp are auto-encoded)
        if any(fw.get('framework') == 'express' for fw in self.frameworks):
            conn = self.db_manager.conn
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM frameworks WHERE name = ? AND language = ?",
                ('express', 'javascript')
            )
            result = cursor.fetchone()
            if result:
                express_id = result[0]
                safe_sinks = [
                    ('res.json', 'response', True, 'JSON encoded response - auto-sanitized'),
                    ('res.jsonp', 'response', True, 'JSONP callback - auto-sanitized'),
                    ('res.status().json', 'response', True, 'JSON with status - auto-sanitized')
                ]
                for pattern, sink_type, is_safe, reason in safe_sinks:
                    self.db_manager.add_framework_safe_sink(
                        express_id, pattern, sink_type, is_safe, reason
                    )

    def index(self) -> tuple[dict[str, int], dict[str, Any]]:
        """Run the complete indexing process.

        Returns:
            Tuple of (counts, stats) dictionaries
        """
        # SCHEMA VALIDATION: Ensure generated code is up-to-date before indexing
        from theauditor.indexer.schemas.codegen import SchemaCodeGenerator
        from theauditor.utils.exit_codes import ExitCodes
        from pathlib import Path
        import sys

        # Get current schema hash
        current_hash = SchemaCodeGenerator.get_schema_hash()

        # Check generated cache file for its hash
        cache_file = Path(__file__).parent / 'schemas' / 'generated_cache.py'
        built_hash = None

        if cache_file.exists():
            with open(cache_file) as f:
                lines = f.readlines()
                if len(lines) >= 2 and 'SCHEMA_HASH:' in lines[1]:
                    built_hash = lines[1].split('SCHEMA_HASH:')[1].strip()

        # Validate hashes match
        if current_hash != built_hash:
            print("[SCHEMA STALE] Schema files have changed but generated code is out of date!", file=sys.stderr)
            print("[SCHEMA STALE] Regenerating code automatically...", file=sys.stderr)

            try:
                # Auto-regenerate the schema files
                output_dir = Path(__file__).parent / 'schemas'
                SchemaCodeGenerator.write_generated_code(output_dir)
                print("[SCHEMA FIX] Generated code updated successfully", file=sys.stderr)
                print("[SCHEMA FIX] Please re-run the indexing command", file=sys.stderr)
                sys.exit(ExitCodes.SCHEMA_STALE)
            except Exception as e:
                print(f"[SCHEMA ERROR] Failed to regenerate code: {e}", file=sys.stderr)
                raise RuntimeError(f"Schema validation failed and auto-fix failed: {e}")

        # Detect frameworks inline (for safe sink detection)
        self.frameworks = self._detect_frameworks_inline()

        # Walk directory and collect files
        files, stats = self.file_walker.walk()

        if not files:
            print("[Indexer] No files found to index.")
            return self.counts, stats

        print(f"[Indexer] Processing {len(files)} files...")

        # Separate JS/TS files for batch processing
        js_ts_files = []
        js_ts_cache = {}

        for file_info in files:
            if file_info['ext'] in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']:
                file_path = self.root_path / file_info['path']
                js_ts_files.append(file_path)

        # Batch process JS/TS files if there are any
        if js_ts_files:
            print(f"[Indexer] Batch processing {len(js_ts_files)} JavaScript/TypeScript files...")
            try:
                # Process in batches for memory efficiency
                for i in range(0, len(js_ts_files), JS_BATCH_SIZE):
                    batch = js_ts_files[i:i+JS_BATCH_SIZE]
                    batch_trees = self.ast_parser.parse_files_batch(
                        batch, root_path=str(self.root_path)
                    )

                    # Cache the results
                    for file_path in batch:
                        file_str = str(file_path).replace("\\", "/")  # Normalize
                        if file_str in batch_trees:
                            js_ts_cache[file_str] = batch_trees[file_str]

                print(f"[Indexer] Successfully batch processed {len(js_ts_cache)} JS/TS files")

                # CRITICAL FIX (Bug #3): Build global function parameter cache
                # This enables cross-file parameter name resolution for taint analysis
                # Without this, 93.1% of function calls fall back to argN naming
                js_ts_function_params = {}
                for file_str, tree in js_ts_cache.items():
                    if not tree or not isinstance(tree, dict):
                        continue

                    # Extract parameters from this file's tree
                    file_params = self.ast_parser._extract_function_parameters(tree, language='javascript')

                    # Merge into global cache
                    for func_name, param_list in file_params.items():
                        # Store unqualified name (works for same-file calls)
                        if func_name not in js_ts_function_params:
                            js_ts_function_params[func_name] = param_list

                        # ALSO store file-qualified name (for disambiguation)
                        # Format: "backend/src/services/account.service.ts#createAccount"
                        qualified_key = f"{file_str}#{func_name}"
                        js_ts_function_params[qualified_key] = param_list

                # Inject into AST parser for use during extraction
                self.ast_parser.global_function_params = js_ts_function_params

                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] Built global function params cache: {len(js_ts_function_params)} entries", file=sys.stderr)
                    # Show sample entries
                    sample_entries = list(js_ts_function_params.items())[:3]
                    for func_name, params in sample_entries:
                        print(f"[DEBUG]   {func_name} -> {params}", file=sys.stderr)

            except Exception as e:
                print(f"[Indexer] Batch processing failed, falling back to individual processing: {e}")
                js_ts_cache = {}

        # Process all files
        for idx, file_info in enumerate(files):
            # Debug progress
            if os.environ.get("THEAUDITOR_DEBUG") and idx % 50 == 0:
                print(f"[INDEXER_DEBUG] Processing file {idx+1}/{len(files)}: {file_info['path']}",
                      file=sys.stderr)

            # Process the file
            self._process_file(file_info, js_ts_cache)

            # Execute batch inserts periodically
            if (idx + 1) % self.db_manager.batch_size == 0 or idx == len(files) - 1:
                self.db_manager.flush_batch()

        # Final commit
        self.db_manager.commit()

        # Populate refactor_candidates table from existing database data
        from datetime import datetime
        conn = self.db_manager.conn
        cursor = conn.cursor()

        # Query files table for high LOC
        cursor.execute("SELECT path, loc FROM files WHERE loc > 500")
        for row in cursor:
            self.db_manager.add_refactor_candidate(
                file_path=row[0],
                reason='size',
                severity='high' if row[1] > 1000 else 'medium',
                loc=row[1],
                detected_at=datetime.now().isoformat()
            )

        # Query for high coupling (many imports)
        cursor.execute("SELECT src, COUNT(*) as import_count FROM refs WHERE kind IN ('import', 'from', 'require') GROUP BY src HAVING import_count > 20")
        for row in cursor:
            self.db_manager.add_refactor_candidate(
                file_path=row[0],
                reason='coupling',
                severity='medium',
                num_dependencies=row[1],
                detected_at=datetime.now().isoformat()
            )

        self.db_manager.flush_batch()
        self.db_manager.commit()

        # PHASE 6: Resolve cross-file parameter names
        # After all files indexed, update function_call_args.param_name with actual parameter names
        # from symbols table (fixes file-scoped limitation in JavaScript extraction)
        from theauditor.indexer.extractors.javascript import JavaScriptExtractor
        if os.environ.get("THEAUDITOR_DEBUG"):
            print("[INDEXER] PHASE 6: Resolving cross-file parameter names...", file=sys.stderr)
        JavaScriptExtractor.resolve_cross_file_parameters(self.db_manager.db_path)
        self.db_manager.commit()

        # PHASE 6.7: Resolve router mount hierarchy (ADDED 2025-11-09)
        # Populate api_endpoints.full_path by resolving router.use() mount statements
        # CRITICAL: Flush and commit before resolution (opens new connection)
        self.db_manager.flush_batch()
        self.db_manager.commit()

        if os.environ.get("THEAUDITOR_DEBUG"):
            print("[INDEXER] PHASE 6.7: Resolving router mount hierarchy...", file=sys.stderr)
        JavaScriptExtractor.resolve_router_mount_hierarchy(self.db_manager.db_path)
        self.db_manager.commit()

        # Report results with database location
        base_msg = (f"[Indexer] Indexed {self.counts['files']} files, "
                   f"{self.counts['symbols']} symbols, {self.counts['refs']} imports, "
                   f"{self.counts['routes']} routes")

        # React/Vue framework components
        if self.counts.get('react_components', 0) > 0:
            base_msg += f", {self.counts['react_components']} React components"
        if self.counts.get('react_hooks', 0) > 0:
            base_msg += f", {self.counts['react_hooks']} React hooks"
        if self.counts.get('vue_components', 0) > 0:
            base_msg += f", {self.counts['vue_components']} Vue components"
        if self.counts.get('vue_hooks', 0) > 0:
            base_msg += f", {self.counts['vue_hooks']} Vue hooks"
        if self.counts.get('vue_directives', 0) > 0:
            base_msg += f", {self.counts['vue_directives']} Vue directives"

        # TypeScript type system
        annotation_summaries = []
        ts_annotations = self.counts.get('type_annotations_typescript', 0)
        py_annotations = self.counts.get('type_annotations_python', 0)
        rs_annotations = self.counts.get('type_annotations_rust', 0)
        if ts_annotations:
            annotation_summaries.append(f"{ts_annotations} TypeScript")
        if py_annotations:
            annotation_summaries.append(f"{py_annotations} Python")
        if rs_annotations:
            annotation_summaries.append(f"{rs_annotations} Rust")
        if annotation_summaries:
            base_msg += ", type annotations: " + ", ".join(annotation_summaries)

        print(base_msg)

        # Data flow tracking (verbose but critical for taint analysis)
        if self.counts.get('assignments', 0) > 0 or self.counts.get('function_calls', 0) > 0:
            flow_msg = f"[Indexer] Data flow: "
            flow_parts = []
            if self.counts.get('assignments', 0) > 0:
                flow_parts.append(f"{self.counts['assignments']} assignments")
            if self.counts.get('function_calls', 0) > 0:
                flow_parts.append(f"{self.counts['function_calls']} function calls")
            if self.counts.get('returns', 0) > 0:
                flow_parts.append(f"{self.counts['returns']} returns")
            if self.counts.get('variable_usage', 0) > 0:
                flow_parts.append(f"{self.counts['variable_usage']} variable usages")
            if self.counts.get('object_literals', 0) > 0:
                flow_parts.append(f"{self.counts['object_literals']} object literal properties")
            print(flow_msg + ", ".join(flow_parts))

        # Control flow analysis
        if self.counts.get('cfg_blocks', 0) > 0:
            cfg_msg = f"[Indexer] Control flow: {self.counts['cfg_blocks']} blocks, {self.counts['cfg_edges']} edges"
            if self.counts.get('cfg_statements', 0) > 0:
                cfg_msg += f", {self.counts['cfg_statements']} statements"
            print(cfg_msg)

        # Database queries
        if self.counts.get('orm', 0) > 0 or self.counts.get('sql_queries', 0) > 0:
            db_msg = f"[Indexer] Database: "
            db_parts = []
            if self.counts.get('orm', 0) > 0:
                db_parts.append(f"{self.counts['orm']} ORM queries")
            if self.counts.get('sql_queries', 0) > 0:
                db_parts.append(f"{self.counts['sql_queries']} SQL queries")
            print(db_msg + ", ".join(db_parts))

        # Infrastructure configs
        if self.counts.get('compose', 0) > 0 or self.counts.get('nginx', 0) > 0 or self.counts.get('docker', 0) > 0:
            infra_msg = f"[Indexer] Infrastructure: "
            infra_parts = []
            if self.counts.get('docker', 0) > 0:
                infra_parts.append(f"{self.counts['docker']} Dockerfiles")
            if self.counts.get('compose', 0) > 0:
                infra_parts.append(f"{self.counts['compose']} compose services")
            if self.counts.get('nginx', 0) > 0:
                infra_parts.append(f"{self.counts['nginx']} nginx blocks")
            print(infra_msg + ", ".join(infra_parts))

        # Project configuration
        if self.counts.get('frameworks', 0) > 0 or self.counts.get('package_configs', 0) > 0:
            config_msg = f"[Indexer] Configuration: "
            config_parts = []
            if self.counts.get('frameworks', 0) > 0:
                config_parts.append(f"{self.counts['frameworks']} frameworks")
            if self.counts.get('package_configs', 0) > 0:
                config_parts.append(f"{self.counts['package_configs']} package configs")
            if self.counts.get('config_files', 0) > 0:
                config_parts.append(f"{self.counts['config_files']} config files")
            print(config_msg + ", ".join(config_parts))

        print(f"[Indexer] Database updated: {self.db_manager.db_path}")

        # Store frameworks in database if available
        if hasattr(self, 'frameworks') and self.frameworks:
            self._store_frameworks()

        # ================================================================
        # SECOND PASS: JSX PRESERVED MODE EXTRACTION (UNCONDITIONAL)
        # ================================================================
        #
        # WHY THIS IS NECESSARY - CRITICAL ARCHITECTURAL DECISION:
        #
        # The TypeScript compiler can only operate in ONE JSX mode at a time,
        # but we need TWO different views of JSX code for complete analysis:
        #
        # 1. TRANSFORMED MODE (First Pass):
        #    - Converts JSX to React.createElement() calls
        #    - Example: <div>{data}</div> → React.createElement('div', null, data)
        #    - Purpose: Enables data-flow and taint analysis
        #    - Why: Taint analysis needs to see data flow through function calls,
        #            not JSX syntax. This reveals how user input flows through
        #            component props and into DOM rendering.
        #    - Stored in: Standard tables (symbols, assignments, function_call_args, etc.)
        #
        # 2. PRESERVED MODE (Second Pass):
        #    - Keeps original JSX syntax intact
        #    - Example: <div>{data}</div> stays as JSX
        #    - Purpose: Enables structural and accessibility analysis
        #    - Why: Rules checking JSX structure (e.g., a11y rules, component
        #            composition patterns, prop validation) need to see the
        #            actual JSX syntax, not transformed calls.
        #    - Stored in: Parallel _jsx tables (symbols_jsx, assignments_jsx, etc.)
        #
        # RESULT:
        # Downstream tools query the appropriate table based on their needs:
        # - Taint analyzer → queries standard tables (transformed view)
        # - JSX structural rules → query _jsx tables (preserved view)
        # - Pattern detector → queries both as needed
        #
        # WARNING: DO NOT REMOVE THIS SECOND PASS
        # Doing so will break all JSX-aware rules and cause false negatives
        # in taint analysis for React/Vue applications.
        jsx_extensions = ['.jsx', '.tsx']
        jsx_files = [f for f in files if f['ext'] in jsx_extensions]

        if jsx_files:
            print(f"[Indexer] Second pass: Processing {len(jsx_files)} JSX/TSX files (preserved mode)...")

            # Build file paths for batch parsing
            jsx_file_paths = [self.root_path / f['path'] for f in jsx_files]

            # Batch parse with preserved JSX mode
            jsx_cache = {}
            try:
                for i in range(0, len(jsx_file_paths), JS_BATCH_SIZE):
                    batch = jsx_file_paths[i:i+JS_BATCH_SIZE]
                    batch_trees = self.ast_parser.parse_files_batch(
                        batch, root_path=str(self.root_path), jsx_mode='preserved'
                    )

                    # Cache results with normalized paths
                    for file_path in batch:
                        file_str = str(file_path).replace("\\", "/")
                        if file_str in batch_trees:
                            jsx_cache[file_str] = batch_trees[file_str]

                print(f"[Indexer] Parsed {len(jsx_cache)} JSX files in preserved mode")
            except Exception as e:
                print(f"[Indexer] WARNING: Preserved mode parsing failed: {e}")
                jsx_cache = {}

            # Process and store to _jsx tables
            jsx_counts = {'symbols': 0, 'assignments': 0, 'calls': 0, 'returns': 0}

            for idx, file_info in enumerate(jsx_files):
                file_path = self.root_path / file_info['path']
                file_str = str(file_path).replace("\\", "/")

                # Get cached tree
                tree = jsx_cache.get(file_str)
                if not tree:
                    continue

                # DEBUG: Check if AST is present in tree

                if os.environ.get("THEAUDITOR_DEBUG"):
                    has_ast = False
                    if isinstance(tree, dict):
                        if 'ast' in tree:
                            has_ast = tree['ast'] is not None
                        elif 'tree' in tree and isinstance(tree['tree'], dict):
                            has_ast = tree['tree'].get('ast') is not None
                    print(f"[DEBUG] JSX pass - {Path(file_path).name}: has_ast={has_ast}, tree_keys={list(tree.keys())[:5] if isinstance(tree, dict) else 'not_dict'}")

                # Read file content (cap at 1MB)
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        content = f.read(1024 * 1024)
                except Exception:
                    continue

                # Get extractor for this file type
                extractor = self.extractor_registry.get_extractor(file_path, file_info['ext'])
                if not extractor:
                    continue

                # Extract data from preserved AST
                # Check for batch processing failures before extraction
                if isinstance(tree, dict) and tree.get('success') is False:
                    print(f"[Indexer] JavaScript extraction FAILED for {file_path}: {tree.get('error')}", file=sys.stderr)
                    continue  # Skip this file

                try:
                    extracted = extractor.extract(file_info, content, tree)
                except Exception as e:
                    if os.environ.get("THEAUDITOR_DEBUG"):
                        print(f"[DEBUG] JSX extraction failed for {file_path}: {e}")
                    continue

                # Store to _jsx tables (parallel structure to standard tables)
                file_path_str = file_info['path']

                # Delegate all storage to DataStorer with jsx_pass=True
                self.data_storer.store(file_path_str, extracted, jsx_pass=True)

                # Track counts for summary reporting
                jsx_counts['symbols'] += len(extracted.get('symbols', []))
                jsx_counts['assignments'] += len(extracted.get('assignments', []))
                jsx_counts['calls'] += len(extracted.get('function_calls', []))
                jsx_counts['returns'] += len(extracted.get('returns', []))

                # CFG is now handled by DataStorer (stores to cfg_blocks_jsx, cfg_edges_jsx, cfg_block_statements_jsx)

                # Flush batches periodically for memory efficiency
                if (idx + 1) % self.db_manager.batch_size == 0:
                    self.db_manager.flush_batch()

            # Final flush and commit for _jsx tables
            self.db_manager.flush_batch()
            self.db_manager.commit()

            # Report second pass statistics
            print(f"[Indexer] Second pass complete: {jsx_counts['symbols']} symbols, "
                  f"{jsx_counts['assignments']} assignments, {jsx_counts['calls']} calls, "
                  f"{jsx_counts['returns']} returns stored to _jsx tables")

        # Flush all generic batches (validation_framework_usage, etc.)
        for table_name in self.db_manager.generic_batches.keys():
            if self.db_manager.generic_batches[table_name]:  # Only flush if non-empty
                self.db_manager.flush_generic_batch(table_name)
        self.db_manager.commit()

        # Cleanup extractor resources (LSP sessions, temp directories, etc.)
        self._cleanup_extractors()

        return self.counts, stats

    def _process_file(self, file_info: dict[str, Any], js_ts_cache: dict[str, Any]):
        """Process a single file.

        Args:
            file_info: File metadata
            js_ts_cache: Cache of pre-parsed JS/TS ASTs
        """
        # DEBUG: Trace file processing
        import sys
        if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
            print(f"[TRACE] _process_file() called for: {file_info['path']}", file=sys.stderr)

        # Insert file record
        self.db_manager.add_file(
            file_info['path'], file_info['sha256'], file_info['ext'],
            file_info['bytes'], file_info['loc']
        )
        self.counts['files'] += 1

        # Read file content (cap at 1MB)
        file_path = self.root_path / file_info['path']
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read(1024 * 1024)
        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"Debug: Cannot read {file_path}: {e}")
            return

        # Store configuration files for ModuleResolver
        if file_info['path'].endswith('tsconfig.json'):
            # Determine context from path
            context_dir = None
            if 'backend/' in file_info['path']:
                context_dir = 'backend'
            elif 'frontend/' in file_info['path']:
                context_dir = 'frontend'

            self.db_manager.add_config_file(
                file_info['path'],
                content,
                'tsconfig',
                context_dir
            )
            self.counts['config_files'] += 1
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Cached tsconfig: {file_info['path']} (context: {context_dir})")

        # Get or parse AST
        tree = self._get_or_parse_ast(file_info, file_path, js_ts_cache)

        # Select appropriate extractor
        extractor = self._select_extractor(file_info['path'], file_info['ext'])
        if not extractor:
            return  # No extractor for this file type

        # DEBUG: Track file processing

        if os.getenv("THEAUDITOR_DEBUG"):
            print(f"[DEBUG ORCHESTRATOR] _process_file called for: {file_info['path']}")

        # Extract all information
        try:
            extracted = extractor.extract(file_info, content, tree)
        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"Debug: Extraction failed for {file_path}: {e}")
            return

        # Store extracted data in database
        import sys
        if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
            num_assignments = len(extracted.get('assignments', []))
            print(f"[TRACE] _store_extracted_data() called for {file_info['path']}: {num_assignments} assignments", file=sys.stderr)
        self._store_extracted_data(file_info['path'], extracted)

    def _get_or_parse_ast(self, file_info: dict[str, Any],
                          file_path: Path, js_ts_cache: dict[str, Any]) -> dict | None:
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
        file_str = str(file_path).replace("\\", "/")
        if file_str in js_ts_cache:
            return js_ts_cache[file_str]

        # Check persistent AST cache
        cached_tree = self.ast_cache.get(file_info['sha256'])
        if cached_tree:
            return cached_tree

        # Parse the file
        tree = self.ast_parser.parse_file(file_path, root_path=str(self.root_path))

        # Cache the result if it's JSON-serializable
        if tree and isinstance(tree, dict):
            self.ast_cache.set(file_info['sha256'], tree)

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
        if self.github_workflow_extractor.should_extract(file_path):
            return self.github_workflow_extractor
        if self.generic_extractor.should_extract(file_path):
            return self.generic_extractor

        # Use registry for standard extension-based extraction
        return self.extractor_registry.get_extractor(file_path, file_ext)

    def _store_extracted_data(self, file_path: str, extracted: dict[str, Any]):
        """Store extracted data in the database - DELEGATED TO DataStorer.

        This method now delegates all storage operations to the DataStorer class.
        The God Method (1,169 lines) has been refactored into 66 focused handler methods.

        Args:
            file_path: Path to the source file
            extracted: Dictionary of extracted data
        """
        # Delegate to DataStorer
        self.data_storer.store(file_path, extracted, jsx_pass=False)

    # === REMOVED: 1,150 lines of inline storage logic ===
    # All storage handlers migrated to storage.py (DataStorer class)
    # See theauditor/indexer/storage.py for implementation

    def _cleanup_extractors(self):
        """Call cleanup() on all registered extractors.

        This allows extractors to release persistent resources like:
        - LSP sessions (Rust, TypeScript)
        - Database connections
        - Temporary directories
        """
        # Clean up registry extractors
        for extractor in self.extractor_registry.extractors.values():
            try:
                extractor.cleanup()
            except Exception as e:
                logger.debug(f"Extractor cleanup failed: {e}")

        # Clean up special extractors
        try:
            self.docker_extractor.cleanup()
        except Exception as e:
            logger.debug(f"Docker extractor cleanup failed: {e}")

        try:
            self.generic_extractor.cleanup()
        except Exception as e:
            logger.debug(f"Generic extractor cleanup failed: {e}")
