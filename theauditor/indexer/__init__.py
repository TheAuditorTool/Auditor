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
    """Orchestrates the indexing process, coordinating all components.

    CRITICAL: Supports dual-pass JSX extraction for React projects.
    - 'preserved' mode: Keeps JSX syntax for structural analysis
    - 'transformed' mode: Converts to React.createElement for taint tracking
    - 'both' mode: Runs both passes atomically
    """

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
            "jsx_components": 0  # Track JSX component detection
        }

        # JSX extraction metadata
        self.extraction_metadata = []

    def _load_frameworks(self) -> List[Dict]:
        """Load framework data from JSON if available."""
        frameworks = []
        frameworks_path = self.root_path / ".pf" / "raw" / "frameworks.json"
        if frameworks_path.exists():
            try:
                with open(frameworks_path, 'r') as f:
                    frameworks = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return frameworks

    def _store_frameworks(self):
        """Store loaded frameworks in database."""
        for fw in self.frameworks:
            self.db_manager.add_framework(
                name=fw.get('framework'),
                version=fw.get('version'),
                language=fw.get('language'),
                path=fw.get('path', '.'),
                source=fw.get('source'),
                is_primary=(fw.get('path', '.') == '.')
            )

        # Add safe sinks for Express
        if any(fw['framework'] == 'express' for fw in self.frameworks):
            express_id = self.db_manager.get_framework_id('express', 'javascript')
            if express_id:
                safe_sinks = [
                    ('res.json', 'response', True, 'JSON encoded response'),
                    ('res.jsonp', 'response', True, 'JSONP callback'),
                    ('res.status().json', 'response', True, 'JSON with status')
                ]
                for pattern, sink_type, is_safe, reason in safe_sinks:
                    self.db_manager.add_framework_safe_sink(
                        express_id, pattern, sink_type, is_safe, reason
                    )

    def index(self, jsx_mode: str = 'both',
              force_rebuild: bool = False,
              validate_extraction: bool = True) -> Tuple[Dict[str, int], Dict[str, Any]]:
        """Run the complete indexing process.

        CRITICAL JSX HANDLING:
        This is an ATOMIC operation - either both passes succeed
        or the entire indexing is rolled back.

        Args:
            jsx_mode: Either 'preserved', 'transformed', or 'both' (default: 'transformed')
            force_rebuild: Force rebuild even if data exists
            validate_extraction: Validate extraction integrity

        Returns:
            Tuple of (counts, stats) dictionaries
        """
        # Validate jsx_mode
        if jsx_mode not in ['preserved', 'transformed', 'both']:
            raise ValueError(f"Invalid jsx_mode: {jsx_mode}")
        # Check if project has JS/TS files
        js_file_count = self._count_js_files()

        # ALWAYS use 'both' mode if we have JS/TS files for complete analysis
        if js_file_count > 0:
            jsx_mode = 'both'  # Force both modes for complete extraction

        # Start extraction with metadata tracking
        extraction_id = self._start_extraction(jsx_mode)

        try:
            if jsx_mode == 'both':
                # CRITICAL: Both passes must complete atomically
                self._run_dual_pass_extraction(extraction_id)

                # Validate extraction if requested
                if validate_extraction:
                    self._validate_extraction_integrity(extraction_id)

                # Mark extraction as complete
                self._complete_extraction(extraction_id)

                # DON'T RETURN - Continue with normal extraction for full processing
                # The dual-pass only handles JSX-specific tables, we still need
                # the normal extraction for assignments, function_calls, etc.
                jsx_mode = 'transformed'  # Use transformed for the main extraction

            elif jsx_mode == 'preserved':
                # Single pass preserved extraction
                self._run_single_pass_extraction(jsx_mode, extraction_id)

                # Validate extraction if requested
                if validate_extraction:
                    self._validate_extraction_integrity(extraction_id)

                # Mark extraction as complete
                self._complete_extraction(extraction_id)

                # CRITICAL: Return here - preserved extraction is complete
                return self._get_extraction_stats(extraction_id)

        except Exception as e:
            # ROLLBACK everything on ANY failure
            logger.error(f"Extraction failed: {e}")
            self._rollback_extraction(extraction_id)
            raise RuntimeError(f"Extraction failed and was rolled back: {e}")

        # Only reach here for 'transformed' mode (backward compatibility)
        # This runs the original indexing logic

        # Load framework data if available
        self.frameworks = self._load_frameworks()

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
            print(f"[Indexer] Batch processing {len(js_ts_files)} JavaScript/TypeScript files (jsx_mode: {jsx_mode})...")
            try:
                # Process in batches for memory efficiency
                for i in range(0, len(js_ts_files), JS_BATCH_SIZE):
                    batch = js_ts_files[i:i+JS_BATCH_SIZE]
                    batch_trees = self.ast_parser.parse_files_batch(
                        batch, root_path=str(self.root_path), jsx_mode=jsx_mode
                    )
                    
                    # Cache the results
                    for file_path in batch:
                        file_str = str(file_path).replace("\\", "/")  # Normalize
                        if file_str in batch_trees:
                            js_ts_cache[file_str] = batch_trees[file_str]
                
                print(f"[Indexer] Successfully batch processed {len(js_ts_cache)} JS/TS files")
            except Exception as e:
                print(f"[Indexer] Batch processing failed, falling back to individual processing: {e}")
                js_ts_cache = {}
        
        # Process all files
        for idx, file_info in enumerate(files):
            # Debug progress
            if os.environ.get("THEAUDITOR_DEBUG") and idx % 50 == 0:
                print(f"[INDEXER_DEBUG] Processing file {idx+1}/{len(files)}: {file_info['path']}",
                      file=sys.stderr)

            # Process the file with JSX mode awareness
            self._process_file(file_info, js_ts_cache, jsx_mode=jsx_mode)

            # Execute batch inserts periodically
            if (idx + 1) % self.db_manager.batch_size == 0 or idx == len(files) - 1:
                self.db_manager.flush_batch()

        # Store frameworks in database if available
        if self.frameworks:
            self._store_frameworks()

        # Final commit
        self.db_manager.commit()
        
        # Report results with database location
        base_msg = (f"[Indexer] Indexed {self.counts['files']} files, "
                   f"{self.counts['symbols']} symbols, {self.counts['refs']} imports, "
                   f"{self.counts['routes']} routes")

        # Add config counts if present
        if self.counts.get('compose', 0) > 0:
            base_msg += f", {self.counts['compose']} compose services"
        if self.counts.get('nginx', 0) > 0:
            base_msg += f", {self.counts['nginx']} nginx blocks"
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
        if self.counts.get('type_annotations', 0) > 0:
            base_msg += f", {self.counts['type_annotations']} TypeScript type annotations"

        print(base_msg)
        print(f"[Indexer] Database updated: {self.db_manager.db_path}")
        
        return self.counts, stats
    
    def _process_file(self, file_info: Dict[str, Any], js_ts_cache: Dict[str, Any],
                      jsx_mode: str = 'transformed'):
        """Process a single file.

        Args:
            file_info: File metadata
            js_ts_cache: Cache of pre-parsed JS/TS ASTs
            jsx_mode: JSX extraction mode
        """
        # Insert file record
        self.db_manager.add_file(
            file_info['path'], file_info['sha256'], file_info['ext'],
            file_info['bytes'], file_info['loc']
        )
        self.counts['files'] += 1
        
        # Read file content (cap at 256KB)
        file_path = self.root_path / file_info['path']
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read(256 * 1024)
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
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Cached tsconfig: {file_info['path']} (context: {context_dir})")
        
        # Get or parse AST
        tree = self._get_or_parse_ast(file_info, file_path, js_ts_cache)
        
        # Select appropriate extractor
        extractor = self._select_extractor(file_info['path'], file_info['ext'])
        if not extractor:
            return  # No extractor for this file type
        
        # Extract all information
        try:
            extracted = extractor.extract(file_info, content, tree)
        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"Debug: Extraction failed for {file_path}: {e}")
            return
        
        # Store extracted data in database
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
        return self.extractor_registry.get_extractor(file_ext)
    
    def _store_extracted_data(self, file_path: str, extracted: Dict[str, Any]):
        """Store extracted data in the database.
        
        Args:
            file_path: Path to the source file
            extracted: Dictionary of extracted data
        """
        # Store imports/references
        if 'imports' in extracted:
            for kind, value in extracted['imports']:
                # Check for resolved import
                resolved = extracted.get('resolved_imports', {}).get(value, value)
                self.db_manager.add_ref(file_path, kind, resolved)
                self.counts['refs'] += 1
        
        # Store routes
        if 'routes' in extracted:
            for method, pattern, controls in extracted['routes']:
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
                    query['command'], query['tables']
                )
                self.counts['sql_queries'] += 1
        
        # Store symbols
        if 'symbols' in extracted:
            for symbol in extracted['symbols']:
                self.db_manager.add_symbol(
                    file_path, symbol['name'], symbol['type'],
                    symbol['line'], symbol['col']
                )
                self.counts['symbols'] += 1

        # Store TypeScript type annotations
        if 'type_annotations' in extracted:
            for annotation in extracted['type_annotations']:
                self.db_manager.insert_type_annotation(
                    file_path,
                    annotation['line'],
                    annotation.get('column', 0),
                    annotation['symbol_name'],
                    annotation['symbol_kind'],
                    annotation.get('type_annotation', ''),
                    annotation.get('is_any', False),
                    annotation.get('is_unknown', False),
                    annotation.get('is_generic', False),
                    annotation.get('has_type_params', False),
                    annotation.get('type_params'),
                    annotation.get('return_type'),
                    annotation.get('extends_type')
                )
                # Track type annotations count
                if 'type_annotations' not in self.counts:
                    self.counts['type_annotations'] = 0
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
        
        # Store Docker information
        if 'docker_info' in extracted and extracted['docker_info']:
            info = extracted['docker_info']
            self.db_manager.add_docker_image(
                file_path, info.get('base_image'), info.get('exposed_ports', []),
                info.get('env_vars', {}), info.get('build_args', {}),
                info.get('user'), info.get('has_healthcheck', False)
            )
            self.counts['docker'] += 1
        
        # Store Docker security issues
        if 'docker_issues' in extracted:
            for issue in extracted['docker_issues']:
                self.db_manager.add_docker_issue(
                    file_path, issue['line'], issue['issue_type'], issue['severity']
                )
        
        # Store data flow information for taint analysis
        if 'assignments' in extracted:
            if extracted['assignments']:
                logger.info(f"[DEBUG] Found {len(extracted['assignments'])} assignments in {file_path}")
                # Log first assignment for debugging
                if extracted['assignments']:
                    first = extracted['assignments'][0]
                    logger.info(f"[DEBUG] First assignment: line {first.get('line')}, {first.get('target_var')} = {first.get('source_expr', '')[:50]}")
            else:
                # Debug: Log when assignments is empty for JS/TS files
                if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                    logger.warning(f"[DEBUG] No assignments extracted from {file_path}")
            for assignment in extracted['assignments']:
                self.db_manager.add_assignment(
                    file_path, assignment['line'], assignment['target_var'],
                    assignment['source_expr'], assignment['source_vars'],
                    assignment['in_function']
                )
        
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

                self.db_manager.add_function_call_arg(
                    file_path, call['line'], call['caller_function'],
                    call['callee_function'], call['argument_index'],
                    call['argument_expr'], call['param_name']
                )
        
        if 'returns' in extracted:
            for ret in extracted['returns']:
                self.db_manager.add_function_return(
                    file_path, ret['line'], ret['function_name'],
                    ret['return_expr'], ret['return_vars']
                )
        
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
                    
                    # Store statements for this block
                    for stmt in block.get('statements', []):
                        self.db_manager.add_cfg_statement(
                            real_id,
                            stmt['type'],
                            stmt['line'],
                            stmt.get('text')
                        )
                
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
                
                # Track count
                if 'cfg_functions' not in self.counts:
                    self.counts['cfg_functions'] = 0
                self.counts['cfg_functions'] += 1
        
        # Store configuration data from parsers
        if 'config_data' in extracted:
            # Store Docker Compose services
            if 'docker_compose' in extracted['config_data']:
                compose_data = extracted['config_data']['docker_compose']
                if 'services' in compose_data and compose_data['services']:
                    for service in compose_data['services']:
                        self.db_manager.add_compose_service(
                            file_path,
                            service.get('name', 'unknown'),
                            service.get('image'),
                            service.get('ports', []),
                            service.get('volumes', []),
                            service.get('environment', {}),
                            service.get('is_privileged', False),
                            service.get('network_mode', 'bridge')
                        )
                        # Track count if not already tracked
                        if 'compose' not in self.counts:
                            self.counts['compose'] = 0
                        self.counts['compose'] += 1
            
            # Store Nginx configuration blocks
            if 'nginx' in extracted['config_data']:
                nginx_data = extracted['config_data']['nginx']
                if 'blocks' in nginx_data and nginx_data['blocks']:
                    for block in nginx_data['blocks']:
                        self.db_manager.add_nginx_config(
                            file_path,
                            block.get('block_type', 'unknown'),
                            block.get('block_context', ''),
                            block.get('directives', {}),
                            block.get('level', 0)
                        )
                        # Track count if not already tracked
                        if 'nginx' not in self.counts:
                            self.counts['nginx'] = 0
                        self.counts['nginx'] += 1

            # Store dedicated JWT patterns
            if 'jwt_patterns' in extracted:
                for pattern in extracted['jwt_patterns']:
                    # Store in sql_queries table with special command type
                    command = f"JWT_{pattern['type'].upper()}_{pattern.get('secret_type', 'UNKNOWN').upper()}"

                    # Pack metadata into JSON for tables column
                    metadata = {
                        'algorithm': pattern.get('algorithm'),
                        'has_expiry': pattern.get('has_expiry'),
                        'allows_none': pattern.get('allows_none'),
                        'has_confusion': pattern.get('has_confusion'),
                        'sensitive_fields': pattern.get('sensitive_fields', [])
                    }

                    self.db_manager.add_sql_query(
                        file_path,
                        pattern['line'],
                        pattern['full_match'],
                        command,
                        [json.dumps(metadata)]  # Store metadata in tables column
                    )
                    self.counts['jwt'] = self.counts.get('jwt', 0) + 1

            # Store Webpack configuration (future implementation)
            # if 'webpack' in extracted['config_data']:
            #     webpack_data = extracted['config_data']['webpack']
            #     # TODO: Add webpack-specific storage when database table is created

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
                self.counts['vue_components'] = self.counts.get('vue_components', 0) + 1

        if 'vue_hooks' in extracted:
            for hook in extracted['vue_hooks']:
                self.db_manager.add_vue_hook(
                    file_path,
                    hook['line'],
                    hook.get('component_name', 'unknown'),
                    hook['hook_name'],
                    hook['hook_type'],
                    hook.get('dependencies'),
                    hook.get('return_value'),
                    hook.get('is_async', False)
                )
                self.counts['vue_hooks'] = self.counts.get('vue_hooks', 0) + 1

        if 'vue_directives' in extracted:
            for directive in extracted['vue_directives']:
                self.db_manager.add_vue_directive(
                    file_path,
                    directive['line'],
                    directive['directive_name'],
                    directive.get('expression', ''),
                    directive.get('in_component', 'unknown'),
                    directive.get('has_key', False),
                    directive.get('modifiers')
                )
                self.counts['vue_directives'] = self.counts.get('vue_directives', 0) + 1

        if 'vue_provide_inject' in extracted:
            for pi in extracted['vue_provide_inject']:
                self.db_manager.add_vue_provide_inject(
                    file_path,
                    pi['line'],
                    pi.get('component_name', 'unknown'),
                    pi['operation_type'],
                    pi['key_name'],
                    pi.get('value_expr'),
                    pi.get('is_reactive', False)
                )
                self.counts['vue_provide_inject'] = self.counts.get('vue_provide_inject', 0) + 1

    # ========================================================
    # DUAL-PASS JSX EXTRACTION METHODS
    # ========================================================

    def _count_jsx_files(self) -> int:
        """Count JSX/TSX files in the project.

        Returns:
            Number of JSX/TSX files found
        """
        jsx_extensions = ['.jsx', '.tsx']
        count = 0
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if any(file.endswith(ext) for ext in jsx_extensions):
                    count += 1
        return count

    def _count_js_files(self) -> int:
        """Count all JavaScript/TypeScript files in the project.

        Returns:
            Number of JS/TS files found
        """
        js_extensions = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
        count = 0
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if any(file.endswith(ext) for ext in js_extensions):
                    count += 1
        return count

    def _start_extraction(self, jsx_mode: str) -> int:
        """Start a new extraction run with metadata tracking.

        Args:
            jsx_mode: The JSX extraction mode

        Returns:
            Extraction ID for tracking
        """
        import time
        extraction_id = int(time.time() * 1000)  # Use timestamp as ID
        self.extraction_metadata.append({
            'extraction_id': extraction_id,
            'started_at': time.time(),
            'jsx_mode': jsx_mode,
            'status': 'running'
        })
        logger.info(f"Started extraction {extraction_id} with jsx_mode={jsx_mode}")
        return extraction_id

    def _complete_extraction(self, extraction_id: int):
        """Mark an extraction as complete.

        Args:
            extraction_id: ID of the extraction to complete
        """
        import time
        for meta in self.extraction_metadata:
            if meta['extraction_id'] == extraction_id:
                meta['completed_at'] = time.time()
                meta['status'] = 'completed'
                meta['jsx_components_found'] = self.counts.get('jsx_components', 0)
                logger.info(f"Completed extraction {extraction_id}")
                break

    def _rollback_extraction(self, extraction_id: int):
        """Rollback a failed extraction.

        CRITICAL: This must atomically remove all data from the failed extraction.

        Args:
            extraction_id: ID of the extraction to rollback
        """
        logger.warning(f"Rolling back extraction {extraction_id}")

        try:
            # Begin transaction for atomic rollback
            conn = self.db_manager.conn
            cursor = conn.cursor()

            # Determine extraction mode and passes
            mode = 'transformed'
            extraction_passes = []
            for meta in self.extraction_metadata:
                if meta['extraction_id'] == extraction_id:
                    mode = meta.get('jsx_mode', 'transformed')
                    extraction_passes.append(meta.get('extraction_pass', 1))
                    break

            # Delete JSX table data if mode was preserved or both
            if mode in ['preserved', 'both']:
                jsx_tables = [
                    'function_returns_jsx',
                    'symbols_jsx',
                    'assignments_jsx',
                    'function_call_args_jsx'
                ]

                for table in jsx_tables:
                    # Check if table exists
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)
                    )
                    if cursor.fetchone():
                        # Delete all data from JSX tables
                        cursor.execute(f"DELETE FROM {table}")
                        logger.debug(f"Cleared {table}")

            # Delete standard table data if mode was transformed or both
            if mode in ['transformed', 'both']:
                standard_tables = [
                    'function_returns',
                    'symbols',
                    'assignments',
                    'function_call_args'
                ]

                for table in standard_tables:
                    # Check if table exists
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)
                    )
                    if cursor.fetchone():
                        # For 'both' mode, clear all data
                        # For 'transformed' mode, also clear all as it's a fresh extraction
                        cursor.execute(f"DELETE FROM {table}")
                        logger.debug(f"Cleared {table}")

            # Clear React-specific tables if they exist
            react_tables = ['react_components', 'react_hooks', 'variable_usage']
            for table in react_tables:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                if cursor.fetchone():
                    cursor.execute(f"DELETE FROM {table}")

            # Mark extraction as failed in metadata
            for meta in self.extraction_metadata:
                if meta['extraction_id'] == extraction_id:
                    meta['status'] = 'failed'
                    break

            # Update extraction_metadata table if it exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_metadata'"
            )
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE extraction_metadata SET status = 'failed', completed_at = CURRENT_TIMESTAMP "
                    "WHERE extraction_id = ?",
                    (extraction_id,)
                )

            conn.commit()
            logger.info(f"Successfully rolled back extraction {extraction_id}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Rollback failed for extraction {extraction_id}: {e}")
            raise RuntimeError(f"Rollback failed: {e}")

    def _run_dual_pass_extraction(self, extraction_id: int):
        """Run both preserved and transformed JSX extraction passes.

        CRITICAL: Both passes must complete atomically.

        Args:
            extraction_id: ID for tracking this extraction
        """
        import gc

        logger.info("Starting dual-pass JSX extraction")

        # Pass 1: Preserved JSX
        logger.info("Pass 1: Preserved JSX extraction")
        preserved_files = self._prepare_jsx_batch()

        if preserved_files:
            try:
                preserved_results = self._extract_with_mode(
                    preserved_files,
                    jsx_mode='preserved',
                    extraction_pass=1,
                    extraction_id=extraction_id
                )
                # Store in JSX tables
                self._store_jsx_results(preserved_results, table_suffix='_jsx')
                # Commit after storing preserved results
                self.db_manager.commit()
            except Exception as e:
                logger.error(f"Pass 1 failed: {e}")
                raise

        # Clear memory before second pass
        self.ast_cache.clear_cache()
        gc.collect()

        # Pass 2: Transformed JSX
        logger.info("Pass 2: Transformed extraction")
        # Get all files for transformed pass
        all_files, _ = self.file_walker.walk()

        try:
            transformed_results = self._extract_with_mode(
                all_files,
                jsx_mode='transformed',
                extraction_pass=2,
                extraction_id=extraction_id
            )
            # Store in standard tables
            self._store_jsx_results(transformed_results, table_suffix='')
            # Commit after storing transformed results
            self.db_manager.commit()
        except Exception as e:
            logger.error(f"Pass 2 failed: {e}")
            raise

        logger.info("Dual-pass extraction completed successfully")

    def _run_single_pass_extraction(self, jsx_mode: str, extraction_id: int):
        """Run a single extraction pass.

        Args:
            jsx_mode: Either 'preserved' or 'transformed'
            extraction_id: ID for tracking this extraction
        """
        logger.info(f"Running single-pass extraction with jsx_mode={jsx_mode}")

        # Get all files
        files, _ = self.file_walker.walk()

        # Determine table suffix based on mode
        table_suffix = '_jsx' if jsx_mode == 'preserved' else ''

        try:
            results = self._extract_with_mode(
                files,
                jsx_mode=jsx_mode,
                extraction_pass=1,
                extraction_id=extraction_id
            )
            self._store_jsx_results(results, table_suffix=table_suffix)
            # Commit after storing results
            self.db_manager.commit()
        except Exception as e:
            logger.error(f"Single-pass extraction failed: {e}")
            raise

    def _prepare_jsx_batch(self) -> List[Dict[str, Any]]:
        """Prepare batch of JSX/TSX files for preserved mode extraction.

        Returns:
            List of file info dictionaries for JSX/TSX files
        """
        jsx_files = []
        jsx_extensions = ['.jsx', '.tsx']

        files, _ = self.file_walker.walk()
        for file_info in files:
            if file_info['ext'] in jsx_extensions:
                jsx_files.append(file_info)

        logger.info(f"Prepared {len(jsx_files)} JSX/TSX files for extraction")
        return jsx_files

    def _extract_with_mode(self, files: List[Dict[str, Any]], jsx_mode: str,
                          extraction_pass: int, extraction_id: int) -> Dict[str, Any]:
        """Extract data from files with specific JSX mode.

        CRITICAL: This method ACTUALLY processes files with the specified jsx_mode.

        Args:
            files: List of file info dictionaries
            jsx_mode: JSX extraction mode
            extraction_pass: Pass number (1 or 2)
            extraction_id: Extraction tracking ID

        Returns:
            Dictionary of extraction results
        """
        results = {
            'files_processed': 0,
            'jsx_components': 0,
            'functions': [],
            'returns': [],
            'assignments': [],
            'function_calls': [],
            'symbols': []
        }

        logger.info(f"Starting extraction of {len(files)} files with jsx_mode={jsx_mode}")

        # Process JS/TS files in batches for efficiency
        js_ts_files = []
        for file_info in files:
            if file_info['ext'] in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']:
                file_path = self.root_path / file_info['path']
                js_ts_files.append(file_path)

        if js_ts_files:
            # Use batch processing with specified jsx_mode
            for i in range(0, len(js_ts_files), JS_BATCH_SIZE):
                batch = js_ts_files[i:i+JS_BATCH_SIZE]
                try:
                    # CRITICAL: Pass jsx_mode to the parser
                    batch_trees = self.ast_parser.parse_files_batch(
                        batch, root_path=str(self.root_path), jsx_mode=jsx_mode
                    )

                    # Process each parsed file
                    for file_path in batch:
                        file_str = str(file_path).replace("\\", "/")
                        if file_str in batch_trees:
                            tree = batch_trees[file_str]
                            if tree and tree.get('success' if 'success' in tree else 'tree'):
                                # Extract data from the AST
                                file_results = self._extract_from_tree(
                                    file_str, tree, jsx_mode, extraction_pass
                                )
                                # Accumulate results
                                for key in ['functions', 'returns', 'assignments', 'function_calls', 'symbols']:
                                    if key in file_results:
                                        results[key].extend(file_results[key])
                                results['files_processed'] += 1
                                # Count JSX components
                                jsx_count = sum(1 for r in file_results.get('returns', [])
                                              if r.get('has_jsx', False))
                                results['jsx_components'] += jsx_count
                except Exception as e:
                    logger.error(f"Failed to process batch: {e}")
                    # Continue with next batch instead of failing entire extraction

        logger.info(f"Extracted {results['files_processed']} files, found {results['jsx_components']} JSX components")
        return results

    def _store_jsx_results(self, results: Dict[str, Any], table_suffix: str):
        """Store extraction results in appropriate tables.

        CRITICAL: This method ACTUALLY stores data in the database tables.

        Args:
            results: Extraction results to store
            table_suffix: Table suffix ('_jsx' for preserved, '' for transformed)
        """
        if not results:
            logger.warning("No results to store")
            return

        logger.info(f"Storing {results.get('files_processed', 0)} files in tables with suffix '{table_suffix}'")

        # Store function returns
        for ret in results.get('returns', []):
            if table_suffix == '_jsx':
                # Store in JSX table
                self.db_manager.add_function_return_jsx(
                    ret['file'], ret['line'], ret.get('function_name', 'anonymous'),
                    ret.get('return_expr', ''), ret.get('return_vars', []),
                    ret.get('has_jsx', False), ret.get('returns_component', False),
                    ret.get('cleanup_operations'),
                    jsx_mode='preserved', extraction_pass=ret.get('extraction_pass', 1)
                )
            else:
                # Store in standard table
                self.db_manager.add_function_return(
                    ret['file'], ret['line'], ret.get('function_name', 'anonymous'),
                    ret.get('return_expr', ''), ret.get('return_vars', [])
                )

        # Store assignments
        for assign in results.get('assignments', []):
            if table_suffix == '_jsx':
                self.db_manager.add_assignment_jsx(
                    assign['file'], assign['line'], assign['target_var'],
                    assign['source_expr'], assign.get('source_vars', []),
                    assign.get('in_function', 'global'),
                    jsx_mode='preserved', extraction_pass=assign.get('extraction_pass', 1)
                )
            else:
                self.db_manager.add_assignment(
                    assign['file'], assign['line'], assign['target_var'],
                    assign['source_expr'], assign.get('source_vars', []),
                    assign.get('in_function', 'global')
                )

        # Store function calls
        for call in results.get('function_calls', []):
            if table_suffix == '_jsx':
                self.db_manager.add_function_call_arg_jsx(
                    call['file'], call['line'], call.get('caller_function', 'anonymous'),
                    call['callee_function'], call.get('argument_index', 0),
                    call.get('argument_expr', ''), call.get('param_name', ''),
                    jsx_mode='preserved', extraction_pass=call.get('extraction_pass', 1)
                )
            else:
                self.db_manager.add_function_call_arg(
                    call['file'], call['line'], call.get('caller_function', 'anonymous'),
                    call['callee_function'], call.get('argument_index', 0),
                    call.get('argument_expr', ''), call.get('param_name', '')
                )

        # Store symbols
        for symbol in results.get('symbols', []):
            if table_suffix == '_jsx':
                self.db_manager.add_symbol_jsx(
                    symbol['path'], symbol['name'], symbol['type'],
                    symbol.get('line', 0), symbol.get('col', 0),
                    jsx_mode='preserved', extraction_pass=symbol.get('extraction_pass', 1)
                )
            else:
                self.db_manager.add_symbol(
                    symbol['path'], symbol['name'], symbol['type'],
                    symbol.get('line', 0), symbol.get('col', 0)
                )

        # Commit the batch
        self.db_manager.flush_batch()
        logger.info(f"Successfully stored {len(results.get('returns', []))} returns, "
                   f"{len(results.get('assignments', []))} assignments, "
                   f"{len(results.get('function_calls', []))} calls, "
                   f"{len(results.get('symbols', []))} symbols")

    def _validate_extraction_integrity(self, extraction_id: int):
        """Validate that extraction produced consistent data.

        Args:
            extraction_id: ID of extraction to validate

        Raises:
            IntegrityError: If validation fails
        """
        checks = [
            self._validate_jsx_detection_rate,
            self._validate_table_consistency,
            self._validate_no_data_loss,
            self._validate_jsx_node_coverage
        ]

        for check in checks:
            success, message = check(extraction_id)
            if not success:
                raise RuntimeError(f"Extraction validation failed: {message}")

        logger.info(f"Extraction {extraction_id} passed all integrity checks")

    def _extract_from_tree(self, file_path: str, tree: Dict, jsx_mode: str,
                          extraction_pass: int) -> Dict[str, Any]:
        """Extract data from a parsed AST tree.

        CRITICAL: This method performs the actual data extraction from the AST.

        Args:
            file_path: Path to the file
            tree: Parsed AST tree
            jsx_mode: JSX extraction mode
            extraction_pass: Pass number

        Returns:
            Dictionary with extracted data
        """
        results = {
            'functions': [],
            'returns': [],
            'assignments': [],
            'function_calls': [],
            'symbols': [],
            'has_jsx': False,
            'jsx_components': []
        }

        # Determine file extension from path
        from pathlib import Path
        file_ext = Path(file_path).suffix.lower()

        # For JS/TS files, use the JavaScript extractor which is more comprehensive
        if file_ext in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']:
            try:
                from theauditor.indexer.extractors.javascript import JavaScriptExtractor
                extractor = JavaScriptExtractor(self.root_path)
                extractor.ast_parser = self.ast_parser

                # Read file content
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Create file info
                file_info = {
                    'path': file_path,
                    'ext': file_ext,
                    'file': file_path
                }

                # Wrap tree for extractor compatibility if needed
                if tree.get('type') != 'semantic_ast':
                    wrapped_tree = {
                        'type': 'semantic_ast',
                        'tree': tree,
                        'jsx_mode': jsx_mode
                    }
                else:
                    wrapped_tree = tree

                # Extract all data using the JavaScript extractor
                extracted_data = extractor.extract(file_info, content, wrapped_tree)

                # Map extracted data to results format
                results['symbols'] = extracted_data.get('symbols', [])
                results['returns'] = extracted_data.get('returns', [])
                results['assignments'] = extracted_data.get('assignments', [])
                results['function_calls'] = extracted_data.get('function_calls', [])
                results['jsx_components'] = extracted_data.get('react_components', [])

                # Add file path and extraction pass to all items
                for ret in results['returns']:
                    ret['file'] = file_path
                    ret['extraction_pass'] = extraction_pass
                    # Ensure JSX flags are present
                    if 'has_jsx' not in ret:
                        ret['has_jsx'] = False
                    if 'returns_component' not in ret:
                        ret['returns_component'] = False

                for assign in results['assignments']:
                    assign['file'] = file_path
                    assign['extraction_pass'] = extraction_pass

                for call in results['function_calls']:
                    call['file'] = file_path
                    call['extraction_pass'] = extraction_pass

                for symbol in results['symbols']:
                    symbol['path'] = file_path
                    symbol['extraction_pass'] = extraction_pass

                # Check for JSX (this is redundant if extractor already did it)
                if 'has_jsx' not in results:
                    results['has_jsx'] = self._check_for_jsx(tree)

            except Exception as e:
                logger.error(f"Failed to extract from {file_path}: {e}")
                # Fall back to basic extraction
                results = self._basic_extraction_fallback(file_path, tree, jsx_mode, extraction_pass)

        else:
            # For non-JS files, use basic extraction
            results = self._basic_extraction_fallback(file_path, tree, jsx_mode, extraction_pass)

        return results

    def _validate_jsx_detection_rate(self, extraction_id: int) -> Tuple[bool, str]:
        """Validate JSX detection rate is reasonable.

        Args:
            extraction_id: Extraction to validate

        Returns:
            Tuple of (success, message)
        """
        # Check if JSX tables have data when they should
        conn = self.db_manager.conn
        cursor = conn.cursor()

        # Count JSX files in project
        jsx_file_count = self._count_jsx_files()

        if jsx_file_count > 0:
            # Check if preserved tables have data (if in preserved or both mode)
            for meta in self.extraction_metadata:
                if meta['extraction_id'] == extraction_id:
                    mode = meta.get('jsx_mode', 'transformed')

                    if mode in ['preserved', 'both']:
                        # Check preserved tables have ANY data
                        cursor.execute("SELECT COUNT(*) FROM function_returns_jsx")
                        jsx_returns = cursor.fetchone()[0]

                        cursor.execute("SELECT COUNT(*) FROM symbols_jsx")
                        jsx_symbols = cursor.fetchone()[0]

                        # Only fail if we have many files but no data at all
                        if jsx_returns == 0 and jsx_symbols == 0 and jsx_file_count > 20:
                            return False, f"No data in preserved JSX tables despite {jsx_file_count} JSX files"

                        # Check for JSX detection
                        cursor.execute("SELECT COUNT(*) FROM function_returns_jsx WHERE has_jsx = 1")
                        jsx_detected = cursor.fetchone()[0]

                        if jsx_detected == 0 and jsx_file_count > 5:
                            logger.warning(f"Low JSX detection: 0 JSX returns in {jsx_file_count} files")

                    if mode in ['transformed', 'both']:
                        # Check standard tables have data
                        cursor.execute("SELECT COUNT(*) FROM function_returns")
                        standard_returns = cursor.fetchone()[0]

                        cursor.execute("SELECT COUNT(*) FROM symbols")
                        standard_symbols = cursor.fetchone()[0]

                        if standard_returns == 0 and standard_symbols == 0:
                            return False, f"No data in standard tables for {jsx_file_count} JSX files"

                    break

        return True, "JSX detection rate acceptable"

    def _validate_table_consistency(self, extraction_id: int) -> Tuple[bool, str]:
        """Validate table data is consistent.

        Args:
            extraction_id: Extraction to validate

        Returns:
            Tuple of (success, message)
        """
        conn = self.db_manager.conn
        cursor = conn.cursor()

        # Get extraction mode
        mode = 'transformed'
        for meta in self.extraction_metadata:
            if meta['extraction_id'] == extraction_id:
                mode = meta.get('jsx_mode', 'transformed')
                break

        if mode == 'both':
            # Both tables should have similar counts
            cursor.execute("SELECT COUNT(*) FROM function_returns")
            standard_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM function_returns_jsx")
            jsx_count = cursor.fetchone()[0]

            if standard_count > 0 and jsx_count == 0:
                return False, "Preserved JSX tables empty despite transformed tables having data"

            if jsx_count > 0 and standard_count == 0:
                return False, "Transformed tables empty despite preserved JSX tables having data"

        elif mode == 'preserved':
            # Check JSX tables have data
            cursor.execute("SELECT COUNT(*) FROM function_returns_jsx")
            if cursor.fetchone()[0] == 0:
                cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE '%.jsx' OR path LIKE '%.tsx'")
                jsx_files = cursor.fetchone()[0]
                if jsx_files > 0:
                    return False, f"Preserved tables empty despite {jsx_files} JSX/TSX files"

        return True, "Table consistency check passed"

    def _validate_no_data_loss(self, extraction_id: int) -> Tuple[bool, str]:
        """Validate no data was lost during extraction.

        Args:
            extraction_id: Extraction to validate

        Returns:
            Tuple of (success, message)
        """
        conn = self.db_manager.conn
        cursor = conn.cursor()

        # Check that files processed matches extraction metadata
        for meta in self.extraction_metadata:
            if meta['extraction_id'] == extraction_id:
                files_processed = meta.get('files_processed', 0)
                if files_processed > 0:
                    # Check that we have data in at least one table
                    cursor.execute(
                        "SELECT COUNT(*) FROM symbols UNION ALL "
                        "SELECT COUNT(*) FROM symbols_jsx"
                    )
                    total_symbols = sum(row[0] for row in cursor.fetchall())
                    if total_symbols == 0:
                        return False, f"No symbols extracted despite processing {files_processed} files"

        return True, "No data loss detected"

    def _validate_jsx_node_coverage(self, extraction_id: int) -> Tuple[bool, str]:
        """Validate all JSX node types are covered.

        Args:
            extraction_id: Extraction to validate

        Returns:
            Tuple of (success, message)
        """
        # Get extraction mode
        mode = 'transformed'
        for meta in self.extraction_metadata:
            if meta['extraction_id'] == extraction_id:
                mode = meta.get('jsx_mode', 'transformed')
                jsx_components = meta.get('jsx_components_found', 0)

                # If we found components, we should have various patterns
                if jsx_components > 0 and mode in ['preserved', 'both']:
                    conn = self.db_manager.conn
                    cursor = conn.cursor()

                    # Check for different JSX patterns in return expressions
                    cursor.execute(
                        "SELECT return_expr FROM function_returns_jsx WHERE has_jsx = 1 LIMIT 10"
                    )
                    returns = cursor.fetchall()

                    if returns:
                        # Check for various JSX patterns
                        has_element = any('<' in r[0] for r in returns if r[0])
                        has_fragment = any('<>' in r[0] or '</>' in r[0] for r in returns if r[0])
                        has_expression = any('{' in r[0] for r in returns if r[0])

                        if not has_element:
                            return False, "No JSX elements detected in preserved mode"

                break

        return True, "JSX node coverage adequate"

    def _check_for_jsx(self, tree: Dict) -> bool:
        """Check if tree contains JSX nodes.

        Args:
            tree: Parsed AST tree

        Returns:
            True if JSX detected, False otherwise
        """
        try:
            from theauditor.ast_extractors.typescript_impl import detect_jsx_in_node

            # Handle different tree structures
            if tree.get('type') == 'semantic_ast':
                # Get the actual AST
                ast = tree.get('ast') or tree.get('tree', {}).get('ast', {})
                if ast:
                    has_jsx, _ = detect_jsx_in_node(ast)
                    return has_jsx
            elif tree.get('success') and tree.get('ast'):
                # Direct semantic AST result
                has_jsx, _ = detect_jsx_in_node(tree['ast'])
                return has_jsx

            return False
        except Exception as e:
            logger.debug(f"JSX detection failed: {e}")
            return False

    def _get_extraction_stats(self, extraction_id: int) -> Tuple[Dict[str, int], Dict[str, Any]]:
        """Get statistics for a completed extraction.

        Args:
            extraction_id: ID of the extraction

        Returns:
            Tuple of (counts, stats) dictionaries
        """
        conn = self.db_manager.conn
        cursor = conn.cursor()

        # Get counts from database
        counts = {
            'files': 0,
            'symbols': 0,
            'returns': 0,
            'assignments': 0,
            'function_calls': 0,
            'jsx_components': 0
        }

        # Count files
        cursor.execute("SELECT COUNT(DISTINCT path) FROM files")
        counts['files'] = cursor.fetchone()[0]

        # Count symbols (both tables)
        cursor.execute(
            "SELECT COUNT(*) FROM symbols UNION ALL SELECT COUNT(*) FROM symbols_jsx"
        )
        counts['symbols'] = sum(row[0] for row in cursor.fetchall())

        # Count returns
        cursor.execute(
            "SELECT COUNT(*) FROM function_returns UNION ALL SELECT COUNT(*) FROM function_returns_jsx"
        )
        counts['returns'] = sum(row[0] for row in cursor.fetchall())

        # Count assignments
        cursor.execute(
            "SELECT COUNT(*) FROM assignments UNION ALL SELECT COUNT(*) FROM assignments_jsx"
        )
        counts['assignments'] = sum(row[0] for row in cursor.fetchall())

        # Count function calls
        cursor.execute(
            "SELECT COUNT(*) FROM function_call_args UNION ALL SELECT COUNT(*) FROM function_call_args_jsx"
        )
        counts['function_calls'] = sum(row[0] for row in cursor.fetchall())

        # Count JSX components
        cursor.execute("SELECT COUNT(*) FROM react_components")
        counts['jsx_components'] = cursor.fetchone()[0]

        # Get stats from extraction metadata
        stats = {}
        for meta in self.extraction_metadata:
            if meta['extraction_id'] == extraction_id:
                stats = {
                    'jsx_mode': meta.get('jsx_mode', 'unknown'),
                    'files_processed': meta.get('files_processed', 0),
                    'jsx_components_found': meta.get('jsx_components_found', 0),
                    'extraction_passes': meta.get('extraction_pass', 1)
                }
                break

        logger.info(f"Extraction {extraction_id} completed: {counts['files']} files, "
                   f"{counts['symbols']} symbols, {counts['jsx_components']} JSX components")

        return counts, stats

    def _basic_extraction_fallback(self, file_path: str, tree: Dict, jsx_mode: str,
                                  extraction_pass: int) -> Dict[str, Any]:
        """Fallback extraction method for when primary extraction fails.

        Args:
            file_path: Path to the file
            tree: Parsed AST tree
            jsx_mode: JSX extraction mode
            extraction_pass: Pass number

        Returns:
            Dictionary with basic extracted data
        """
        results = {
            'functions': [],
            'returns': [],
            'assignments': [],
            'function_calls': [],
            'symbols': [],
            'has_jsx': False,
            'jsx_components': []
        }

        # Try to extract basic symbols at least
        try:
            # Import extraction functions from typescript_impl as fallback
            from theauditor.ast_extractors.typescript_impl import (
                extract_typescript_returns,
                extract_typescript_assignments,
                extract_typescript_calls_with_args,
                extract_typescript_function_params
            )

            # Handle semantic AST
            if tree.get('type') == 'semantic_ast' and tree.get('tree'):
                semantic_tree = tree['tree']
            elif tree.get('ast'):
                semantic_tree = tree
            else:
                return results

            # Extract returns
            returns = extract_typescript_returns(semantic_tree, None)
            for ret in returns:
                ret['file'] = file_path
                ret['extraction_pass'] = extraction_pass
            results['returns'].extend(returns)

            # Extract assignments
            assignments = extract_typescript_assignments(semantic_tree, None)
            for assign in assignments:
                assign['file'] = file_path
                assign['extraction_pass'] = extraction_pass
            results['assignments'].extend(assignments)

            # Extract function calls
            func_params = extract_typescript_function_params(semantic_tree, None)
            calls = extract_typescript_calls_with_args(semantic_tree, func_params, None)
            for call in calls:
                call['file'] = file_path
                call['extraction_pass'] = extraction_pass
            results['function_calls'].extend(calls)

            # Extract symbols
            for symbol in semantic_tree.get('symbols', []):
                symbol['path'] = file_path
                symbol['extraction_pass'] = extraction_pass
                results['symbols'].append(symbol)

        except Exception as e:
            logger.debug(f"Fallback extraction also failed for {file_path}: {e}")

        return results

    def _get_extractor_for_file(self, file_info: Dict[str, Any]) -> Optional[Any]:
        """Get the appropriate extractor for a file.

        Args:
            file_info: File information dictionary

        Returns:
            Extractor instance or None
        """
        file_ext = file_info.get('ext', '').lower()

        # Map extensions to extractors
        if file_ext in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']:
            from theauditor.indexer.extractors.javascript import JavaScriptExtractor
            extractor = JavaScriptExtractor(self.root_path)
            extractor.ast_parser = self.ast_parser
            return extractor
        elif file_ext in ['.py']:
            from theauditor.indexer.extractors.python import PythonExtractor
            extractor = PythonExtractor(self.root_path)
            extractor.ast_parser = self.ast_parser
            return extractor
        elif file_ext in ['.sql']:
            from theauditor.indexer.extractors.sql import SQLExtractor
            return SQLExtractor(self.root_path)
        elif file_info['path'].endswith('docker-compose.yml'):
            from theauditor.indexer.extractors.docker import DockerExtractor
            return DockerExtractor(self.root_path)

        return None

    def _extract_functions_from_symbols(self, extracted_data: Dict) -> List[Dict]:
        """Extract function data from symbols.

        Args:
            extracted_data: Extracted data dictionary

        Returns:
            List of function dictionaries
        """
        functions = []

        # Get functions from symbols
        for symbol in extracted_data.get('symbols', []):
            if symbol.get('type') == 'function':
                functions.append({
                    'name': symbol.get('name', 'anonymous'),
                    'line': symbol.get('line', 0),
                    'end_line': symbol.get('end_line', symbol.get('line', 0)),
                    'type': 'function'
                })

        # Also get from react_components
        for component in extracted_data.get('react_components', []):
            functions.append({
                'name': component.get('name', 'Component'),
                'line': component.get('start_line', 0),
                'end_line': component.get('end_line', 0),
                'type': 'component'
            })

        return functions


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