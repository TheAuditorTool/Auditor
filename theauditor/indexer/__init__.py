"""TheAuditor Indexer Package.

This package provides modular, extensible code indexing functionality.
It includes:
- FileWalker for directory traversal with monorepo support
- DatabaseManager for SQLite operations
- Pluggable language extractors
- AST caching for performance

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This is the INDEXER layer - the orchestrator of extraction. It:
- PROVIDES: file_path (absolute or relative path to source file)
- CALLS: extractor.extract(file_info, content, tree) via _process_file()
- RECEIVES: Extracted data WITHOUT file_path keys
- STORES: Database records WITH file_path context via _store_extracted_data()

Key Implementation Points:
--------------------------
1. _process_file() (line 504): Passes file_info['path'] to extractors
2. _store_extracted_data() (line 619): INDEXER provides file_path for all database operations
3. Object literal storage (line 948-962): Example of correct pattern:
   - Line 952: db_manager.add_object_literal(file_path, obj_lit['line'], ...)
   - Uses file_path parameter (from orchestrator context)
   - Uses obj_lit['line'] (from extractor data)
   - DOES NOT use obj_lit['file'] (which would violate architecture)

This separation ensures single source of truth for file paths and prevents
architectural violations where extractors/implementations incorrectly track files.

See also:
- indexer/extractors/*.py - EXTRACTOR layer (delegates to parser)
- ast_extractors/*_impl.py - IMPLEMENTATION layer (returns line numbers only)
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
from .extractors import ExtractorRegistry
from .extractors.docker import DockerExtractor
from .extractors.generic import GenericExtractor

logger = logging.getLogger(__name__)


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

        # Inject db_manager into special extractors (Phase 3C fix)
        # GenericExtractor uses database-first architecture and needs direct access
        self.docker_extractor.db_manager = self.db_manager
        self.generic_extractor.db_manager = self.db_manager

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
            # Configuration
            "frameworks": 0,
            "package_configs": 0,
            "config_files": 0,
        }

    def _detect_frameworks_inline(self) -> List[Dict]:
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

    def index(self) -> Tuple[Dict[str, int], Dict[str, Any]]:
        """Run the complete indexing process.

        Returns:
            Tuple of (counts, stats) dictionaries
        """
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

        # PHASE 6: Resolve cross-file parameter names
        # After all files indexed, update function_call_args.param_name with actual parameter names
        # from symbols table (fixes file-scoped limitation in JavaScript extraction)
        from theauditor.indexer.extractors.javascript import JavaScriptExtractor
        if os.environ.get("THEAUDITOR_DEBUG"):
            print("[INDEXER] PHASE 6: Resolving cross-file parameter names...", file=sys.stderr)
        JavaScriptExtractor.resolve_cross_file_parameters(self.db_manager.db_path)
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
        if self.counts.get('type_annotations', 0) > 0:
            base_msg += f", {self.counts['type_annotations']} TypeScript type annotations"

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

                # Symbols (function/class/variable declarations)
                for symbol in extracted.get('symbols', []):
                    self.db_manager.add_symbol_jsx(
                        file_path_str, symbol['name'], symbol['type'],
                        symbol['line'], symbol['col'],
                        jsx_mode='preserved', extraction_pass=2
                    )
                    jsx_counts['symbols'] += 1

                # Assignments (var = expr tracking for taint)
                for assign in extracted.get('assignments', []):
                    self.db_manager.add_assignment_jsx(
                        file_path_str, assign['line'], assign['target_var'],
                        assign['source_expr'], assign['source_vars'],
                        assign['in_function'], assign.get('property_path'),  # Pass destructuring property path
                        jsx_mode='preserved', extraction_pass=2
                    )
                    jsx_counts['assignments'] += 1

                # Function call arguments (for taint tracking)
                for call in extracted.get('function_calls', []):
                    self.db_manager.add_function_call_arg_jsx(
                        file_path_str, call['line'], call['caller_function'],
                        call['callee_function'], call['argument_index'],
                        call['argument_expr'], call['param_name'],
                        jsx_mode='preserved', extraction_pass=2
                    )
                    jsx_counts['calls'] += 1

                # Return statements (component returns, cleanup functions)
                for ret in extracted.get('returns', []):
                    self.db_manager.add_function_return_jsx(
                        file_path_str, ret['line'], ret['function_name'],
                        ret['return_expr'], ret['return_vars'],
                        ret.get('has_jsx', False), ret.get('returns_component', False),
                        ret.get('cleanup_operations'),
                        jsx_mode='preserved', extraction_pass=2
                    )
                    jsx_counts['returns'] += 1

                # CFG extraction (JSX PASS)
                # Extract CFG from JSX files - critical for control flow analysis
                for function_cfg in extracted.get('cfg', []):
                    if not function_cfg:
                        continue

                    # Map temporary block IDs to real IDs
                    block_id_map = {}

                    # Store blocks and build ID mapping
                    for block in function_cfg.get('blocks', []):
                        temp_id = block['id']
                        real_id = self.db_manager.add_cfg_block(
                            file_path_str,
                            function_cfg['function_name'],
                            block['type'],
                            block['start_line'],
                            block['end_line'],
                            block.get('condition')
                        )
                        block_id_map[temp_id] = real_id
                        self.counts['cfg_blocks'] += 1

                        # Store statements for this block
                        for stmt in block.get('statements', []):
                            self.db_manager.add_cfg_statement(
                                real_id,
                                stmt['type'],
                                stmt['line'],
                                stmt.get('text')
                            )
                            self.counts['cfg_statements'] += 1

                    # Store edges with mapped IDs
                    for edge in function_cfg.get('edges', []):
                        source_id = block_id_map.get(edge['source'], edge['source'])
                        target_id = block_id_map.get(edge['target'], edge['target'])
                        self.db_manager.add_cfg_edge(
                            file_path_str,
                            function_cfg['function_name'],
                            source_id,
                            target_id,
                            edge['type']
                        )
                        self.counts['cfg_edges'] += 1

                    # Track count
                    if 'cfg_functions' not in self.counts:
                        self.counts['cfg_functions'] = 0
                    self.counts['cfg_functions'] += 1

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
    
    def _process_file(self, file_info: Dict[str, Any], js_ts_cache: Dict[str, Any]):
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
    
    def _get_or_parse_ast(self, file_info: Dict[str, Any], 
                          file_path: Path, js_ts_cache: Dict[str, Any]) -> Optional[Dict]:
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
        if self.generic_extractor.should_extract(file_path):
            return self.generic_extractor
        
        # Use registry for standard extension-based extraction
        return self.extractor_registry.get_extractor(file_path, file_ext)
    
    def _store_extracted_data(self, file_path: str, extracted: Dict[str, Any]):
        """Store extracted data in the database.

        Args:
            file_path: Path to the source file
            extracted: Dictionary of extracted data
        """
        import json  # Ensure json is available for all code paths

        # Store imports/references
        if 'imports' in extracted:

            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Processing {len(extracted['imports'])} imports for {file_path}")
            for import_tuple in extracted['imports']:
                # Handle both 2-tuple (kind, value) and 3-tuple (kind, value, line) formats
                if len(import_tuple) == 3:
                    kind, value, line = import_tuple
                else:
                    kind, value = import_tuple
                    line = None

                # Check for resolved import
                resolved = extracted.get('resolved_imports', {}).get(value, value)
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG]   Adding ref: {file_path} -> {kind} {resolved} (line {line})")
                self.db_manager.add_ref(file_path, kind, resolved, line)
                self.counts['refs'] += 1
        
        # Store routes (api_endpoints with all 8 fields)
        if 'routes' in extracted:
            for route in extracted['routes']:
                # Handle both old tuple format and new dictionary format for compatibility
                if isinstance(route, dict):
                    self.db_manager.add_endpoint(
                        file_path=file_path,
                        method=route.get('method', 'GET'),
                        pattern=route.get('pattern', ''),
                        controls=route.get('controls', []),
                        line=route.get('line'),
                        path=route.get('path'),
                        has_auth=route.get('has_auth', False),
                        handler_function=route.get('handler_function')
                    )
                else:
                    # Legacy tuple format: (method, pattern, controls)
                    method, pattern, controls = route
                    self.db_manager.add_endpoint(file_path, method, pattern, controls)
                self.counts['routes'] += 1
        
        # Store SQL objects
        if 'sql_objects' in extracted:
            for kind, name in extracted['sql_objects']:
                self.db_manager.add_sql_object(file_path, kind, name)
                self.counts['sql'] += 1
        
        # Store SQL queries
        if 'sql_queries' in extracted:
            for query in extracted['sql_queries']:
                self.db_manager.add_sql_query(
                    file_path, query['line'], query['query_text'],
                    query['command'], query['tables'],
                    query.get('extraction_source', 'code_execute')  # Phase 3B: source tagging
                )
                self.counts['sql_queries'] += 1
        
        # Store symbols
        if 'symbols' in extracted:
            import json
            for symbol in extracted['symbols']:
                # Serialize parameters array to JSON if present
                parameters_json = None
                if 'parameters' in symbol and symbol['parameters']:
                    parameters_json = json.dumps(symbol['parameters'])

                self.db_manager.add_symbol(
                    file_path, symbol['name'], symbol['type'],
                    symbol['line'], symbol['col'], symbol.get('end_line'),
                    symbol.get('type_annotation'),  # Pass type_annotation if present
                    parameters_json  # Pass JSON-serialized parameters
                )
                self.counts['symbols'] += 1

        # Store TypeScript type annotations
        if 'type_annotations' in extracted:
            for annotation in extracted['type_annotations']:
                self.db_manager.add_type_annotation(
                    file_path,
                    annotation.get('line', 0),
                    annotation.get('column', 0),
                    annotation.get('symbol_name', ''),
                    annotation.get('annotation_type', annotation.get('symbol_kind', 'unknown')),
                    annotation.get('type_annotation', annotation.get('type_text', '')),
                    annotation.get('is_any', False),
                    annotation.get('is_unknown', False),
                    annotation.get('is_generic', False),
                    annotation.get('has_type_params', False),
                    annotation.get('type_params'),
                    annotation.get('return_type'),
                    annotation.get('extends_type')
                )
                self.counts['type_annotations'] += 1

        # Store ORM queries
        if 'orm_queries' in extracted:
            for query in extracted['orm_queries']:
                self.db_manager.add_orm_query(
                    file_path, query['line'], query['query_type'],
                    query.get('includes'), query.get('has_limit', False),
                    query.get('has_transaction', False)
                )
                self.counts['orm'] += 1

        # Store validation framework usage (for taint analysis sanitizer detection)
        # DEBUG: Check if validation_framework_usage key exists
        if os.environ.get("THEAUDITOR_VALIDATION_DEBUG") and file_path.endswith('validate.ts'):
            print(f"[PY-DEBUG] Extracted keys for {file_path}: {list(extracted.keys())}", file=sys.stderr)
            if 'validation_framework_usage' in extracted:
                print(f"[PY-DEBUG] validation_framework_usage has {len(extracted['validation_framework_usage'])} items", file=sys.stderr)

        if 'validation_framework_usage' in extracted:
            for usage in extracted['validation_framework_usage']:
                self.db_manager.generic_batches['validation_framework_usage'].append((
                    file_path,
                    usage['line'],
                    usage['framework'],
                    usage['method'],
                    usage.get('variable_name'),
                    1 if usage.get('is_validator', True) else 0,
                    usage.get('argument_expr', '')
                ))
            # Flush if batch is full
            if len(self.db_manager.generic_batches['validation_framework_usage']) >= self.db_manager.batch_size:
                self.db_manager.flush_generic_batch('validation_framework_usage')

        # Store data flow information for taint analysis
        if 'assignments' in extracted:
            if extracted['assignments']:
                logger.info(f"[DEBUG] Found {len(extracted['assignments'])} assignments in {file_path}")
                # Log first assignment for debugging
                if extracted['assignments']:
                    first = extracted['assignments'][0]
                    logger.info(f"[DEBUG] First assignment: line {first.get('line')}, {first.get('target_var')} = {first.get('source_expr', '')[:50]}")
            for assignment in extracted['assignments']:
                self.db_manager.add_assignment(
                    file_path, assignment['line'], assignment['target_var'],
                    assignment['source_expr'], assignment['source_vars'],
                    assignment['in_function'], assignment.get('property_path')  # Pass destructuring property path
                )
                self.counts['assignments'] += 1
        
        if 'function_calls' in extracted:
            for call in extracted['function_calls']:
                callee = call['callee_function']

                # JWT Categorization Enhancement
                if 'jwt' in callee.lower() or 'jsonwebtoken' in callee.lower():
                    if '.sign' in callee:
                        # Check secret type from arg1
                        if call.get('argument_index') == 1:
                            arg_expr = call.get('argument_expr', '')
                            if 'process.env' in arg_expr:
                                call['callee_function'] = 'JWT_SIGN_ENV'
                            elif '"' in arg_expr or "'" in arg_expr:
                                call['callee_function'] = 'JWT_SIGN_HARDCODED'
                            else:
                                call['callee_function'] = 'JWT_SIGN_VAR'
                        else:
                            # Keep original for other args but mark
                            call['callee_function'] = f'JWT_SIGN#{call["callee_function"]}'
                    elif '.verify' in callee:
                        call['callee_function'] = f'JWT_VERIFY#{callee}'
                    elif '.decode' in callee:
                        call['callee_function'] = f'JWT_DECODE#{callee}'

                # CRITICAL: Pass callee_file_path resolved by TypeScript checker
                # This enables unambiguous cross-file taint tracking
                self.db_manager.add_function_call_arg(
                    file_path, call['line'], call['caller_function'],
                    call['callee_function'], call['argument_index'],
                    call['argument_expr'], call['param_name'],
                    callee_file_path=call.get('callee_file_path')  # Resolved by TypeScript checker (may be None)
                )
                self.counts['function_calls'] += 1

        if 'returns' in extracted:
            for ret in extracted['returns']:
                self.db_manager.add_function_return(
                    file_path, ret['line'], ret['function_name'],
                    ret['return_expr'], ret['return_vars']
                )
                self.counts['returns'] += 1
        
        # Store control flow graph data
        if 'cfg' in extracted:
            for function_cfg in extracted['cfg']:
                if not function_cfg:
                    continue
                    
                # Map temporary block IDs to real IDs
                block_id_map = {}
                
                # Store blocks and build ID mapping
                for block in function_cfg.get('blocks', []):
                    temp_id = block['id']
                    real_id = self.db_manager.add_cfg_block(
                        file_path,
                        function_cfg['function_name'],
                        block['type'],
                        block['start_line'],
                        block['end_line'],
                        block.get('condition')
                    )
                    block_id_map[temp_id] = real_id
                    self.counts['cfg_blocks'] += 1

                    # Store statements for this block
                    for stmt in block.get('statements', []):
                        self.db_manager.add_cfg_statement(
                            real_id,
                            stmt['type'],
                            stmt['line'],
                            stmt.get('text')
                        )
                        self.counts['cfg_statements'] += 1

                # Store edges with mapped IDs
                for edge in function_cfg.get('edges', []):
                    source_id = block_id_map.get(edge['source'], edge['source'])
                    target_id = block_id_map.get(edge['target'], edge['target'])
                    self.db_manager.add_cfg_edge(
                        file_path,
                        function_cfg['function_name'],
                        source_id,
                        target_id,
                        edge['type']
                    )
                    self.counts['cfg_edges'] += 1
                
                # Track count
                if 'cfg_functions' not in self.counts:
                    self.counts['cfg_functions'] = 0
                self.counts['cfg_functions'] += 1
        
        # Store dedicated JWT patterns
        if 'jwt_patterns' in extracted:
            for pattern in extracted['jwt_patterns']:
                # CORRECT - storing in jwt_patterns table
                self.db_manager.add_jwt_pattern(
                    file_path=file_path,
                    line_number=pattern['line'],
                    pattern_type=pattern['type'],
                    pattern_text=pattern.get('full_match', ''),
                    secret_source=pattern.get('secret_type', 'unknown'),
                    algorithm=pattern.get('algorithm')
                )
                self.counts['jwt'] = self.counts.get('jwt', 0) + 1

        # Store React-specific data
        if 'react_components' in extracted:
            for component in extracted['react_components']:
                self.db_manager.add_react_component(
                    file_path,
                    component['name'],
                    component['type'],
                    component['start_line'],
                    component['end_line'],
                    component['has_jsx'],
                    component.get('hooks_used'),
                    component.get('props_type')
                )
                self.counts['react_components'] += 1

        # Store class property declarations (TypeScript/JavaScript ES2022+)
        if 'class_properties' in extracted:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG INDEXER] Found {len(extracted['class_properties'])} class_properties for {file_path}")
            for prop in extracted['class_properties']:
                if os.environ.get("THEAUDITOR_DEBUG") and len(extracted['class_properties']) > 0:
                    print(f"[DEBUG INDEXER]   Adding {prop['class_name']}.{prop['property_name']} at line {prop['line']}")
                self.db_manager.add_class_property(
                    file_path,
                    prop['line'],
                    prop['class_name'],
                    prop['property_name'],
                    prop.get('property_type'),
                    prop.get('is_optional', False),
                    prop.get('is_readonly', False),
                    prop.get('access_modifier'),
                    prop.get('has_declare', False),
                    prop.get('initializer')
                )
                if 'class_properties' not in self.counts:
                    self.counts['class_properties'] = 0
                self.counts['class_properties'] += 1

        # Store environment variable usage (process.env.X)
        if 'env_var_usage' in extracted:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG INDEXER] Found {len(extracted['env_var_usage'])} env_var_usage for {file_path}")
            for usage in extracted['env_var_usage']:
                self.db_manager.add_env_var_usage(
                    file_path,
                    usage['line'],
                    usage['var_name'],
                    usage['access_type'],
                    usage.get('in_function'),
                    usage.get('property_access')
                )
                if 'env_var_usage' not in self.counts:
                    self.counts['env_var_usage'] = 0
                self.counts['env_var_usage'] += 1

        # Store ORM relationship declarations (hasMany, belongsTo, etc.)
        if 'orm_relationships' in extracted:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG INDEXER] Found {len(extracted['orm_relationships'])} orm_relationships for {file_path}")
            for rel in extracted['orm_relationships']:
                self.db_manager.add_orm_relationship(
                    file_path,
                    rel['line'],
                    rel['source_model'],
                    rel['target_model'],
                    rel['relationship_type'],
                    rel.get('foreign_key'),
                    rel.get('cascade_delete', False),
                    rel.get('as_name')
                )
                if 'orm_relationships' not in self.counts:
                    self.counts['orm_relationships'] = 0
                self.counts['orm_relationships'] += 1

        if 'python_orm_models' in extracted:
            for model in extracted['python_orm_models']:
                self.db_manager.add_python_orm_model(
                    file_path,
                    model.get('line', 0),
                    model.get('model_name', ''),
                    model.get('table_name'),
                    model.get('orm_type', 'sqlalchemy')
                )
                if 'python_orm_models' not in self.counts:
                    self.counts['python_orm_models'] = 0
                self.counts['python_orm_models'] += 1

        if 'python_orm_fields' in extracted:
            for field in extracted['python_orm_fields']:
                self.db_manager.add_python_orm_field(
                    file_path,
                    field.get('line', 0),
                    field.get('model_name', ''),
                    field.get('field_name', ''),
                    field.get('field_type'),
                    field.get('is_primary_key', False),
                    field.get('is_foreign_key', False),
                    field.get('foreign_key_target')
                )
                if 'python_orm_fields' not in self.counts:
                    self.counts['python_orm_fields'] = 0
                self.counts['python_orm_fields'] += 1

        if 'python_routes' in extracted:
            for route in extracted['python_routes']:
                self.db_manager.add_python_route(
                    file_path,
                    route.get('line'),
                    route.get('framework', ''),
                    route.get('method', ''),
                    route.get('pattern', ''),
                    route.get('handler_function', ''),
                    route.get('has_auth', False),
                    route.get('dependencies'),
                    route.get('blueprint')
                )
                if 'python_routes' not in self.counts:
                    self.counts['python_routes'] = 0
                self.counts['python_routes'] += 1

        if 'python_blueprints' in extracted:
            for blueprint in extracted['python_blueprints']:
                self.db_manager.add_python_blueprint(
                    file_path,
                    blueprint.get('line'),
                    blueprint.get('blueprint_name', ''),
                    blueprint.get('url_prefix'),
                    blueprint.get('subdomain')
                )
                if 'python_blueprints' not in self.counts:
                    self.counts['python_blueprints'] = 0
                self.counts['python_blueprints'] += 1

        if 'python_validators' in extracted:
            for validator in extracted['python_validators']:
                self.db_manager.add_python_validator(
                    file_path,
                    validator.get('line', 0),
                    validator.get('model_name', ''),
                    validator.get('field_name'),
                    validator.get('validator_method', ''),
                    validator.get('validator_type', '')
                )
                if 'python_validators' not in self.counts:
                    self.counts['python_validators'] = 0
                self.counts['python_validators'] += 1

        if 'react_hooks' in extracted:
            for hook in extracted['react_hooks']:
                self.db_manager.add_react_hook(
                    file_path,
                    hook['line'],
                    hook['component_name'],
                    hook['hook_name'],
                    hook.get('dependency_array'),
                    hook.get('dependency_vars'),
                    hook.get('callback_body'),
                    hook.get('has_cleanup', False),
                    hook.get('cleanup_type')
                )
                self.counts['react_hooks'] += 1

        # Store Vue-specific data
        if 'vue_components' in extracted:
            for component in extracted['vue_components']:
                self.db_manager.add_vue_component(
                    file_path,
                    component['name'],
                    component['type'],
                    component['start_line'],
                    component['end_line'],
                    component.get('has_template', False),
                    component.get('has_style', False),
                    component.get('composition_api_used', False),
                    component.get('props_definition'),
                    component.get('emits_definition'),
                    component.get('setup_return')
                )
                if 'vue_components' not in self.counts:
                    self.counts['vue_components'] = 0
                self.counts['vue_components'] += 1

        if 'vue_hooks' in extracted:
            for hook in extracted['vue_hooks']:
                self.db_manager.add_vue_hook(
                    file_path,
                    hook['line'],
                    hook['component_name'],
                    hook['hook_name'],
                    hook.get('hook_type', 'unknown'),
                    hook.get('dependencies'),
                    hook.get('return_value'),
                    hook.get('is_async', False)
                )
                if 'vue_hooks' not in self.counts:
                    self.counts['vue_hooks'] = 0
                self.counts['vue_hooks'] += 1

        if 'vue_directives' in extracted:
            for directive in extracted['vue_directives']:
                self.db_manager.add_vue_directive(
                    file_path,
                    directive['line'],
                    directive['directive_name'],
                    directive.get('value_expr', ''),
                    directive.get('in_component', 'global'),
                    directive.get('is_dynamic', False),
                    directive.get('modifiers')
                )
                if 'vue_directives' not in self.counts:
                    self.counts['vue_directives'] = 0
                self.counts['vue_directives'] += 1

        if 'vue_provide_inject' in extracted:
            for pi in extracted['vue_provide_inject']:
                self.db_manager.add_vue_provide_inject(
                    file_path,
                    pi['line'],
                    pi['component_name'],
                    pi.get('operation_type', 'unknown'),
                    pi.get('key_name', ''),
                    pi.get('value_expr'),
                    pi.get('is_reactive', False)
                )

        if 'variable_usage' in extracted:
            for var in extracted['variable_usage']:
                self.db_manager.add_variable_usage(
                    file_path,
                    var['line'],
                    var['variable_name'],
                    var['usage_type'],
                    var.get('in_component'),
                    var.get('in_hook'),
                    var.get('scope_level', 0)
                )
                self.counts['variable_usage'] += 1

        # === PHASE 3: OBJECT LITERAL STORAGE ===
        if 'object_literals' in extracted:
            for obj_lit in extracted['object_literals']:
                self.db_manager.add_object_literal(
                    file_path,
                    obj_lit['line'],
                    obj_lit['variable_name'],
                    obj_lit['property_name'],
                    obj_lit['property_value'],
                    obj_lit['property_type'],
                    obj_lit.get('nested_level', 0),
                    obj_lit.get('in_function', '')
                )
                self.counts['object_literals'] += 1

        # Store build analysis data
        if 'package_configs' in extracted:
            for pkg_config in extracted['package_configs']:
                self.db_manager.add_package_config(
                    pkg_config['file_path'],
                    pkg_config['package_name'],
                    pkg_config['version'],
                    pkg_config.get('dependencies'),
                    pkg_config.get('dev_dependencies'),
                    pkg_config.get('peer_dependencies'),
                    pkg_config.get('scripts'),
                    pkg_config.get('engines'),
                    pkg_config.get('workspaces'),
                    pkg_config.get('is_private', False)
                )
                self.counts['package_configs'] += 1

        if 'lock_analysis' in extracted:
            for lock in extracted['lock_analysis']:
                self.db_manager.add_lock_analysis(
                    lock['file_path'],
                    lock['lock_type'],
                    lock.get('package_manager_version'),
                    lock['total_packages'],
                    lock.get('duplicate_packages'),
                    lock.get('lock_file_version')
                )
                if 'lock_analysis' not in self.counts:
                    self.counts['lock_analysis'] = 0
                self.counts['lock_analysis'] += 1

        if 'import_styles' in extracted:
            for import_style in extracted['import_styles']:
                self.db_manager.add_import_style(
                    file_path,
                    import_style['line'],
                    import_style['package'],
                    import_style['import_style'],
                    import_style.get('imported_names'),
                    import_style.get('alias_name'),
                    import_style.get('full_statement')
                )
                if 'import_styles' not in self.counts:
                    self.counts['import_styles'] = 0
                self.counts['import_styles'] += 1

        # Store Terraform infrastructure definitions
        if 'terraform_file' in extracted:
            file_record = extracted['terraform_file']
            self.db_manager.add_terraform_file(
                file_path=file_record['file_path'],
                module_name=file_record.get('module_name'),
                stack_name=file_record.get('stack_name'),
                backend_type=file_record.get('backend_type'),
                providers_json=file_record.get('providers_json'),
                is_module=file_record.get('is_module', False),
                module_source=file_record.get('module_source')
            )
            if 'terraform_files' not in self.counts:
                self.counts['terraform_files'] = 0
            self.counts['terraform_files'] += 1

        if 'terraform_resources' in extracted:
            for resource in extracted['terraform_resources']:
                self.db_manager.add_terraform_resource(
                    resource_id=resource['resource_id'],
                    file_path=resource['file_path'],
                    resource_type=resource['resource_type'],
                    resource_name=resource['resource_name'],
                    module_path=resource.get('module_path'),
                    properties_json=json.dumps(resource.get('properties', {})),
                    depends_on_json=json.dumps(resource.get('depends_on', [])),
                    sensitive_flags_json=json.dumps(resource.get('sensitive_properties', [])),
                    has_public_exposure=resource.get('has_public_exposure', False),
                    line=resource.get('line')
                )
                if 'terraform_resources' not in self.counts:
                    self.counts['terraform_resources'] = 0
                self.counts['terraform_resources'] += 1

        if 'terraform_variables' in extracted:
            for variable in extracted['terraform_variables']:
                self.db_manager.add_terraform_variable(
                    variable_id=variable['variable_id'],
                    file_path=variable['file_path'],
                    variable_name=variable['variable_name'],
                    variable_type=variable.get('variable_type'),
                    default_json=json.dumps(variable.get('default')) if variable.get('default') is not None else None,
                    is_sensitive=variable.get('is_sensitive', False),
                    description=variable.get('description', ''),
                    source_file=variable.get('source_file'),
                    line=variable.get('line')
                )
                if 'terraform_variables' not in self.counts:
                    self.counts['terraform_variables'] = 0
                self.counts['terraform_variables'] += 1

        if 'terraform_variable_values' in extracted:
            for value in extracted['terraform_variable_values']:
                raw_value = value.get('variable_value')
                value_json = value.get('variable_value_json')
                if value_json is None and raw_value is not None:
                    try:
                        value_json = json.dumps(raw_value)
                    except TypeError:
                        value_json = json.dumps(str(raw_value))

                self.db_manager.add_terraform_variable_value(
                    file_path=value['file_path'],
                    variable_name=value['variable_name'],
                    variable_value_json=value_json,
                    line=value.get('line'),
                    is_sensitive_context=value.get('is_sensitive_context', False)
                )
                if 'terraform_variable_values' not in self.counts:
                    self.counts['terraform_variable_values'] = 0
                self.counts['terraform_variable_values'] += 1

        if 'terraform_outputs' in extracted:
            for output in extracted['terraform_outputs']:
                self.db_manager.add_terraform_output(
                    output_id=output['output_id'],
                    file_path=output['file_path'],
                    output_name=output['output_name'],
                    value_json=json.dumps(output.get('value')) if output.get('value') is not None else None,
                    is_sensitive=output.get('is_sensitive', False),
                    description=output.get('description', ''),
                    line=output.get('line')
                )
                if 'terraform_outputs' not in self.counts:
                    self.counts['terraform_outputs'] = 0
                self.counts['terraform_outputs'] += 1

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
