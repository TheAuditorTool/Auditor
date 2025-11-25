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
1. _process_file() (orchestrator.py): Passes file_info['path'] to extractors
2. _store_extracted_data() (orchestrator.py): INDEXER provides file_path for all database operations
3. Object literal storage: Example of correct pattern:
   - db_manager.add_object_literal(file_path, obj_lit['line'], ...)
   - Uses file_path parameter (from orchestrator context)
   - Uses obj_lit['line'] (from extractor data)
   - DOES NOT use obj_lit['file'] (which would violate architecture)

This separation ensures single source of truth for file paths and prevents
architectural violations where extractors/implementations incorrectly track files.

See also:
- indexer/extractors/*.py - EXTRACTOR layer (delegates to parser)
- ast_extractors/*_impl.py - IMPLEMENTATION layer (returns line numbers only)
"""

# Core orchestrator
from .orchestrator import IndexerOrchestrator

# Core components
from .core import FileWalker
from ..cache.ast_cache import ASTCache
from .database import DatabaseManager
from .extractors import ExtractorRegistry

# Clean entry point (replaces deprecated indexer_compat.build_index)
from .runner import run_repository_index

__all__ = [
    'IndexerOrchestrator',
    'FileWalker',
    'DatabaseManager',
    'ASTCache',
    'ExtractorRegistry',
    'run_repository_index',
]
