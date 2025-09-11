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
        """Run the complete indexing process.
        
        Returns:
            Tuple of (counts, stats) dictionaries
        """
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
        
        # Report results with database location
        base_msg = (f"[Indexer] Indexed {self.counts['files']} files, "
                   f"{self.counts['symbols']} symbols, {self.counts['refs']} imports, "
                   f"{self.counts['routes']} routes")
        
        # Add config counts if present
        if self.counts.get('compose', 0) > 0:
            base_msg += f", {self.counts['compose']} compose services"
        if self.counts.get('nginx', 0) > 0:
            base_msg += f", {self.counts['nginx']} nginx blocks"
        
        print(base_msg)
        print(f"[Indexer] Database updated: {self.db_manager.db_path}")
        
        return self.counts, stats
    
    def _process_file(self, file_info: Dict[str, Any], js_ts_cache: Dict[str, Any]):
        """Process a single file.
        
        Args:
            file_info: File metadata
            js_ts_cache: Cache of pre-parsed JS/TS ASTs
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
            for assignment in extracted['assignments']:
                self.db_manager.add_assignment(
                    file_path, assignment['line'], assignment['target_var'],
                    assignment['source_expr'], assignment['source_vars'],
                    assignment['in_function']
                )
        
        if 'function_calls' in extracted:
            for call in extracted['function_calls']:
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
            
            # Store Webpack configuration (future implementation)
            # if 'webpack' in extracted['config_data']:
            #     webpack_data = extracted['config_data']['webpack']
            #     # TODO: Add webpack-specific storage when database table is created


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