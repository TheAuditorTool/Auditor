"""Repository indexer - Backward Compatibility Shim.

This module provides backward compatibility for code that imports from indexer.py.
All functionality has been refactored into the theauditor.indexer package.

IMPORTANT: New code should import from theauditor.indexer package directly:
    from theauditor.indexer import IndexerOrchestrator
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import from the new package structure  
from theauditor.indexer import IndexerOrchestrator
from theauditor.indexer.config import (
    SKIP_DIRS, IMPORT_PATTERNS, ROUTE_PATTERNS, SQL_PATTERNS,
    SQL_QUERY_PATTERNS, DEFAULT_BATCH_SIZE
)
from theauditor.indexer.core import (
    FileWalker, is_text_file, get_first_lines, load_gitignore_patterns
)
from theauditor.indexer.database import create_database_schema
from theauditor.config_runtime import load_runtime_config

# Re-export commonly used items for backward compatibility
__all__ = [
    'build_index',
    'walk_directory',
    'populate_database',
    'create_database_schema',
    'SKIP_DIRS',
    'extract_imports',
    'extract_routes',
    'extract_sql_objects',
    'extract_sql_queries'
]


def extract_imports(content: str, file_ext: str) -> List[tuple]:
    """Extract import statements - backward compatibility wrapper."""
    imports = []
    for pattern in IMPORT_PATTERNS:
        for match in pattern.finditer(content):
            value = match.group(1) if match.lastindex else match.group(0)
            # Determine kind based on pattern
            if "require" in pattern.pattern:
                kind = "require"
            elif "from" in pattern.pattern and "import" in pattern.pattern:
                kind = "from"
            elif "package" in pattern.pattern:
                kind = "package"
            else:
                kind = "import"
            imports.append((kind, value))
    return imports


def extract_routes(content: str) -> List[tuple]:
    """Extract route definitions - backward compatibility wrapper."""
    routes = []
    for pattern in ROUTE_PATTERNS:
        for match in pattern.finditer(content):
            if match.lastindex == 2:
                method = match.group(1).upper()
                path = match.group(2)
            else:
                method = "ANY"
                path = match.group(1) if match.lastindex else match.group(0)
            routes.append((method, path))
    return routes


def extract_sql_objects(content: str) -> List[tuple]:
    """Extract SQL object definitions - backward compatibility wrapper."""
    objects = []
    for pattern in SQL_PATTERNS:
        for match in pattern.finditer(content):
            name = match.group(1)
            # Determine kind from pattern
            pattern_text = pattern.pattern.lower()
            if "table" in pattern_text:
                kind = "table"
            elif "index" in pattern_text:
                kind = "index"
            elif "view" in pattern_text:
                kind = "view"
            elif "function" in pattern_text:
                kind = "function"
            elif "policy" in pattern_text:
                kind = "policy"
            elif "constraint" in pattern_text:
                kind = "constraint"
            else:
                kind = "unknown"
            objects.append((kind, name))
    return objects


def extract_sql_queries(content: str) -> List[dict]:
    """Extract SQL queries - backward compatibility wrapper.
    
    Note: This requires sqlparse to be installed for full functionality.
    """
    try:
        import sqlparse
    except ImportError:
        return []
    
    queries = []
    for pattern in SQL_QUERY_PATTERNS:
        for match in pattern.finditer(content):
            query_text = match.group(1) if match.lastindex else match.group(0)
            
            # Calculate line number
            line = content[:match.start()].count('\n') + 1
            
            # Clean up the query text
            query_text = query_text.strip()
            if not query_text:
                continue
            
            try:
                # Parse the SQL query
                parsed = sqlparse.parse(query_text)
                if not parsed:
                    continue
                
                for statement in parsed:
                    # Extract command type
                    command = statement.get_type()
                    if not command:
                        # Try to extract manually from first token
                        tokens = statement.tokens
                        for token in tokens:
                            if not token.is_whitespace:
                                command = str(token).upper()
                                break
                    
                    # Extract table names
                    tables = []
                    tokens = list(statement.flatten())
                    for i, token in enumerate(tokens):
                        if token.ttype is None and token.value.upper() in ['FROM', 'INTO', 'UPDATE', 'TABLE', 'JOIN']:
                            # Look for the next non-whitespace token
                            for j in range(i + 1, len(tokens)):
                                next_token = tokens[j]
                                if not next_token.is_whitespace:
                                    if next_token.ttype in [None, sqlparse.tokens.Name]:
                                        table_name = next_token.value
                                        # Clean up table name
                                        table_name = table_name.strip('"\'`')
                                        if '.' in table_name:
                                            table_name = table_name.split('.')[-1]
                                        if table_name and not table_name.upper() in ['SELECT', 'WHERE', 'SET', 'VALUES']:
                                            tables.append(table_name)
                                    break
                    
                    queries.append({
                        'line': line,
                        'query_text': query_text[:1000],  # Limit length
                        'command': command or 'UNKNOWN',
                        'tables': tables
                    })
            except Exception:
                # Skip queries that can't be parsed
                continue
    
    return queries


def walk_directory(
    root_path: Path, 
    follow_symlinks: bool = False, 
    exclude_patterns: Optional[List[str]] = None
) -> tuple[List[dict], Dict[str, Any]]:
    """Walk directory and collect file information - backward compatibility wrapper.
    
    Args:
        root_path: Root directory to walk
        follow_symlinks: Whether to follow symbolic links
        exclude_patterns: Additional patterns to exclude
        
    Returns:
        Tuple of (files_list, statistics)
    """
    config = load_runtime_config(str(root_path))
    walker = FileWalker(root_path, config, follow_symlinks, exclude_patterns)
    return walker.walk()


def populate_database(
    conn: sqlite3.Connection,
    files: List[dict],
    root_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE
) -> Dict[str, int]:
    """Populate SQLite database - backward compatibility wrapper.
    
    Args:
        conn: SQLite connection
        files: List of file dictionaries
        root_path: Project root path
        batch_size: Batch size for database operations
        
    Returns:
        Dictionary of extraction counts
    """
    # Create orchestrator with the existing connection's path
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    orchestrator = IndexerOrchestrator(root_path, db_path, batch_size)
    
    # Close the passed connection as orchestrator creates its own
    conn.close()
    
    # Run the indexing
    counts, _ = orchestrator.index()
    return counts


def build_index(
    root_path: str = ".",
    manifest_path: str = "manifest.json",
    db_path: str = "repo_index.db",
    print_stats: bool = False,
    dry_run: bool = False,
    follow_symlinks: bool = False,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build repository index - main entry point for backward compatibility.
    
    Args:
        root_path: Root directory to index
        manifest_path: Path to write manifest JSON
        db_path: Path to SQLite database
        print_stats: Whether to print statistics
        dry_run: If True, only scan files without creating database
        follow_symlinks: Whether to follow symbolic links
        exclude_patterns: Patterns to exclude from indexing
        
    Returns:
        Dictionary with success status and statistics
    """
    start_time = time.time()
    root = Path(root_path).resolve()

    if not root.exists():
        return {"error": f"Root path does not exist: {root_path}"}

    # Walk directory and collect files
    config = load_runtime_config(str(root))
    walker = FileWalker(root, config, follow_symlinks, exclude_patterns)
    files, walk_stats = walker.walk()

    if dry_run:
        if print_stats:
            elapsed_ms = int((time.time() - start_time) * 1000)
            print(f"Files scanned: {walk_stats['total_files']}")
            print(f"Text files indexed: {walk_stats['text_files']}")
            print(f"Binary files skipped: {walk_stats['binary_files']}")
            print(f"Large files skipped: {walk_stats['large_files']}")
            print(f"Elapsed: {elapsed_ms}ms")
        return {"success": True, "dry_run": True, "stats": walk_stats}

    # Write manifest
    try:
        # Ensure parent directory exists before writing
        Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(files, f, indent=2, sort_keys=True)
    except Exception as e:
        return {"error": f"Failed to write manifest: {e}"}

    # Create and populate database
    try:
        # Ensure parent directory exists for database
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Check if database already exists
        db_exists = Path(db_path).exists()
        
        # Create database schema
        conn = sqlite3.connect(db_path)
        conn.execute("BEGIN IMMEDIATE")
        create_database_schema(conn)
        conn.commit()
        conn.close()
        
        # Report database creation if new
        if not db_exists:
            print(f"[Indexer] Created database: {db_path}")
        
        # Use orchestrator to populate the database
        orchestrator = IndexerOrchestrator(root, db_path, DEFAULT_BATCH_SIZE, 
                                          follow_symlinks, exclude_patterns)
        
        # Clear existing data to avoid UNIQUE constraint errors
        orchestrator.db_manager.clear_tables()
        
        extract_counts, _ = orchestrator.index()
        
    except Exception as e:
        return {"error": f"Failed to create database: {e}"}

    if print_stats:
        elapsed_ms = int((time.time() - start_time) * 1000)
        print(f"Files scanned: {walk_stats['total_files']}")
        print(f"Text files indexed: {walk_stats['text_files']}")
        print(f"Binary files skipped: {walk_stats['binary_files']}")
        print(f"Large files skipped: {walk_stats['large_files']}")
        print(f"Refs extracted: {extract_counts['refs']}")
        print(f"Routes extracted: {extract_counts['routes']}")
        print(f"SQL objects extracted: {extract_counts['sql']}")
        print(f"SQL queries extracted: {extract_counts['sql_queries']}")
        print(f"Docker images analyzed: {extract_counts['docker']}")
        print(f"Symbols extracted: {extract_counts['symbols']}")
        print(f"Elapsed: {elapsed_ms}ms")

    return {
        "success": True,
        "stats": walk_stats,
        "extract_counts": extract_counts,
        "elapsed_ms": int((time.time() - start_time) * 1000),
    }