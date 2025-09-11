"""Cache for pattern detection results.

This module implements caching for security pattern detection results,
with automatic invalidation when pattern definitions change.
"""

import sqlite3
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, List, Any


class PatternCache:
    """Cache pattern detection results per file and pattern version.
    
    The key insight here is that pattern results depend on two things:
    1. The content of the file being analyzed
    2. The pattern definitions themselves
    
    When either changes, the cache must be invalidated. This is handled
    by using a composite key of (file_hash, pattern_version).
    """
    
    def __init__(self, cache_dir: Path):
        """Initialize the pattern cache.
        
        Args:
            cache_dir: Base directory for cache files
        """
        self.cache_dir = cache_dir
        self.db_path = cache_dir / "patterns.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_tables()
        self._pattern_version = None
        self._pattern_dir = Path(__file__).parent.parent / "rules" / "YAML"
    
    def _create_tables(self):
        """Create cache tables if they don't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pattern_cache (
                file_hash TEXT NOT NULL,
                pattern_version TEXT NOT NULL,
                results TEXT NOT NULL,
                created_at INTEGER,
                last_accessed INTEGER,
                hit_count INTEGER DEFAULT 0,
                PRIMARY KEY (file_hash, pattern_version)
            )
        """)
        
        # Index for fast lookups
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pattern_lookup
            ON pattern_cache(file_hash, pattern_version)
        """)
        
        # Index for LRU eviction
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pattern_lru
            ON pattern_cache(last_accessed)
        """)
        
        # Metadata table for pattern version tracking
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pattern_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        self.conn.commit()
    
    def get_pattern_version(self) -> str:
        """Calculate hash of all pattern files.
        
        This creates a version identifier for the current state of all
        pattern definitions. When any pattern file changes, this hash
        changes, automatically invalidating all cached results.
        
        Returns:
            MD5 hash of all pattern files concatenated
        """
        if self._pattern_version:
            return self._pattern_version
        
        # Check if we have a cached version hash
        cursor = self.conn.execute(
            "SELECT value FROM pattern_metadata WHERE key = 'pattern_version'"
        )
        row = cursor.fetchone()
        if row:
            stored_version = row[0]
            # Verify it's still valid by checking modification times
            if self._verify_pattern_version(stored_version):
                self._pattern_version = stored_version
                return stored_version
        
        # Calculate new version hash
        if not self._pattern_dir.exists():
            # Fallback to default if pattern directory doesn't exist
            return "default"
        
        hasher = hashlib.md5()
        pattern_files = []
        
        # Collect all YAML pattern files
        for pattern_file in sorted(self._pattern_dir.glob("**/*.yml")):
            pattern_files.append(pattern_file)
        for pattern_file in sorted(self._pattern_dir.glob("**/*.yaml")):
            pattern_files.append(pattern_file)
        
        # Hash file contents
        for pattern_file in sorted(pattern_files):
            try:
                with open(pattern_file, 'rb') as f:
                    hasher.update(f.read())
            except (OSError, PermissionError):
                pass
        
        version_hash = hasher.hexdigest()
        
        # Store the version hash
        self.conn.execute("""
            INSERT OR REPLACE INTO pattern_metadata (key, value)
            VALUES ('pattern_version', ?)
        """, (version_hash,))
        
        # Also store file modification times for verification
        mtimes = {}
        for pattern_file in pattern_files:
            try:
                mtimes[str(pattern_file)] = pattern_file.stat().st_mtime
            except OSError:
                pass
        
        self.conn.execute("""
            INSERT OR REPLACE INTO pattern_metadata (key, value)
            VALUES ('pattern_mtimes', ?)
        """, (json.dumps(mtimes),))
        
        self.conn.commit()
        
        self._pattern_version = version_hash
        return version_hash
    
    def _verify_pattern_version(self, version_hash: str) -> bool:
        """Verify that a cached pattern version is still valid.
        
        Args:
            version_hash: Previously calculated version hash
        
        Returns:
            True if pattern files haven't changed
        """
        cursor = self.conn.execute(
            "SELECT value FROM pattern_metadata WHERE key = 'pattern_mtimes'"
        )
        row = cursor.fetchone()
        if not row:
            return False
        
        try:
            stored_mtimes = json.loads(row[0])
        except json.JSONDecodeError:
            return False
        
        # Check if all files still have the same modification times
        for file_path, stored_mtime in stored_mtimes.items():
            path = Path(file_path)
            if not path.exists():
                return False
            try:
                current_mtime = path.stat().st_mtime
                if abs(current_mtime - stored_mtime) > 0.001:  # Allow tiny float differences
                    return False
            except OSError:
                return False
        
        return True
    
    def get(self, key: str, context: Dict[str, Any]) -> Optional[List[Dict]]:
        """Get cached pattern results for a file.
        
        Args:
            key: File content hash
            context: Additional context (unused but required by protocol)
        
        Returns:
            List of pattern matches or None if not cached
        """
        file_hash = key  # Key is the file content hash
        pattern_version = self.get_pattern_version()
        
        cursor = self.conn.execute("""
            SELECT results FROM pattern_cache
            WHERE file_hash = ? AND pattern_version = ?
        """, (file_hash, pattern_version))
        
        row = cursor.fetchone()
        if row:
            results_json = row[0]
            
            # Update hit count and last accessed time
            self.conn.execute("""
                UPDATE pattern_cache
                SET hit_count = hit_count + 1,
                    last_accessed = ?
                WHERE file_hash = ? AND pattern_version = ?
            """, (int(time.time()), file_hash, pattern_version))
            self.conn.commit()
            
            return json.loads(results_json)
        
        return None
    
    def set(self, key: str, value: List[Dict], context: Dict[str, Any]) -> None:
        """Cache pattern results for a file.
        
        Args:
            key: File content hash
            value: List of pattern matches to cache
            context: Additional context (unused)
        """
        file_hash = key
        pattern_version = self.get_pattern_version()
        results_json = json.dumps(value)
        current_time = int(time.time())
        
        self.conn.execute("""
            INSERT OR REPLACE INTO pattern_cache
            (file_hash, pattern_version, results, created_at, last_accessed)
            VALUES (?, ?, ?, ?, ?)
        """, (file_hash, pattern_version, results_json, current_time, current_time))
        self.conn.commit()
        
        # Evict old entries if cache is too large
        self._evict_if_needed()
    
    def invalidate(self, key: str) -> None:
        """Invalidate cache entries for a specific file.
        
        Args:
            key: File content hash to invalidate
        """
        self.conn.execute(
            "DELETE FROM pattern_cache WHERE file_hash = ?",
            (key,)
        )
        self.conn.commit()
    
    def invalidate_patterns(self) -> None:
        """Invalidate all cached results when patterns change.
        
        This is called when pattern files are modified.
        """
        self._pattern_version = None  # Force recalculation
        self.conn.execute("DELETE FROM pattern_cache")
        self.conn.execute("DELETE FROM pattern_metadata")
        self.conn.commit()
    
    def _evict_if_needed(self, max_entries: int = 5000):
        """Evict least recently used entries if cache is too large.
        
        Args:
            max_entries: Maximum number of cache entries
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM pattern_cache")
        count = cursor.fetchone()[0]
        
        if count > max_entries:
            # Delete oldest 20% of entries
            to_delete = count // 5
            
            self.conn.execute("""
                DELETE FROM pattern_cache
                WHERE rowid IN (
                    SELECT rowid FROM pattern_cache
                    ORDER BY last_accessed ASC
                    LIMIT ?
                )
            """, (to_delete,))
            self.conn.commit()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total_entries,
                SUM(hit_count) as total_hits,
                AVG(hit_count) as avg_hits,
                MAX(last_accessed) as last_used
            FROM pattern_cache
        """)
        
        row = cursor.fetchone()
        
        # Get pattern version info
        pattern_version = self.get_pattern_version()
        
        return {
            "total_entries": row[0] or 0,
            "total_hits": row[1] or 0,
            "avg_hits": round(row[2] or 0, 2),
            "last_used": row[3] or 0,
            "pattern_version": pattern_version[:8],  # First 8 chars of hash
        }
    
    def clear_cache(self) -> None:
        """Clear all cached entries."""
        self.conn.execute("DELETE FROM pattern_cache")
        self.conn.commit()
        self._pattern_version = None
    
    def close(self) -> None:
        """Close database connection."""
        self.conn.close()