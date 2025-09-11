"""Cache manager for CFG analysis results.

This module provides persistent caching for expensive CFG analysis operations,
dramatically improving performance on subsequent runs.
"""

import sqlite3
import json
import time
import hashlib
import os
from pathlib import Path
from typing import Optional, Dict, Any

class CFGCacheManager:
    """
    Persistent cache for CFG analysis results.
    
    Why this matters: First analysis = 10 minutes
                      Cached analysis = 30 seconds
    
    The cache is invalidated when source files change, ensuring
    correctness while maximizing performance.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize cache manager with optional custom database path."""
        if db_path is None:
            # Use default cache location
            cache_dir = Path(".pf/.cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(cache_dir / "cfg_analysis_cache.db")
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_cache_tables()
        self.debug = os.environ.get("THEAUDITOR_CACHE_DEBUG")
    
    def _create_cache_tables(self):
        """Create cache tables if they don't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cfg_analysis_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                function_signature TEXT,
                entry_state_hash TEXT,
                analysis_result TEXT,
                vulnerable_paths TEXT,
                file_mtime INTEGER,
                created_at INTEGER,
                hit_count INTEGER DEFAULT 0,
                last_accessed INTEGER,
                UNIQUE(function_signature, entry_state_hash)
            )
        """)
        
        # Index for fast lookups
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_lookup
            ON cfg_analysis_cache(function_signature, entry_state_hash)
        """)
        
        # Index for cache eviction (LRU)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_lru
            ON cfg_analysis_cache(last_accessed)
        """)
        
        self.conn.commit()
    
    def get_cached_analysis(
        self,
        file_path: str,
        function_name: str,
        entry_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached analysis if still valid."""
        
        if self.debug:
            print(f"[CACHE] Checking cache for {function_name} in {file_path}", file=os.sys.stderr)
        
        # Check if file changed since cache
        try:
            file_mtime = int(Path(file_path).stat().st_mtime)
        except FileNotFoundError:
            return None
        
        func_sig = f"{file_path}:{function_name}"
        state_hash = self._hash_state(entry_state)
        
        cursor = self.conn.execute("""
            SELECT analysis_result, file_mtime, id
            FROM cfg_analysis_cache
            WHERE function_signature = ? AND entry_state_hash = ?
        """, (func_sig, state_hash))
        
        row = cursor.fetchone()
        if row:
            cached_result, cached_mtime, cache_id = row
            
            if cached_mtime >= file_mtime:
                # Cache is still valid
                if self.debug:
                    print(f"[CACHE] Hit for {function_name}", file=os.sys.stderr)
                
                # Update hit count and last accessed time
                self.conn.execute("""
                    UPDATE cfg_analysis_cache
                    SET hit_count = hit_count + 1,
                        last_accessed = ?
                    WHERE id = ?
                """, (int(time.time()), cache_id))
                self.conn.commit()
                
                return json.loads(cached_result)
            else:
                if self.debug:
                    print(f"[CACHE] Stale cache for {function_name} (file modified)", file=os.sys.stderr)
        else:
            if self.debug:
                print(f"[CACHE] Miss for {function_name}", file=os.sys.stderr)
        
        return None  # Cache miss or stale
    
    def cache_analysis(
        self,
        file_path: str,
        function_name: str,
        entry_state: Dict[str, Any],
        analysis_result: Any
    ):
        """Store analysis result in cache."""
        
        if self.debug:
            print(f"[CACHE] Caching result for {function_name} in {file_path}", file=os.sys.stderr)
        
        try:
            file_mtime = int(Path(file_path).stat().st_mtime)
        except FileNotFoundError:
            return  # Don't cache if file doesn't exist
        
        func_sig = f"{file_path}:{function_name}"
        state_hash = self._hash_state(entry_state)
        
        # Serialize result
        if isinstance(analysis_result, str):
            result_json = analysis_result
        else:
            result_json = json.dumps(analysis_result)
        
        current_time = int(time.time())
        
        try:
            # Insert or replace cache entry
            self.conn.execute("""
                INSERT OR REPLACE INTO cfg_analysis_cache
                (function_signature, entry_state_hash, analysis_result, 
                 file_mtime, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (func_sig, state_hash, result_json, file_mtime, 
                  current_time, current_time))
            self.conn.commit()
            
            # Evict old entries if cache is too large
            self._evict_if_needed()
            
        except sqlite3.Error as e:
            if self.debug:
                print(f"[CACHE] Error caching result: {e}", file=os.sys.stderr)
    
    def _hash_state(self, state: Dict[str, Any]) -> str:
        """Create a hash of the entry state for cache keying."""
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.md5(state_str.encode()).hexdigest()
    
    def _evict_if_needed(self, max_entries: int = 10000):
        """Evict least recently used entries if cache is too large."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM cfg_analysis_cache")
        count = cursor.fetchone()[0]
        
        if count > max_entries:
            # Delete oldest 10% of entries
            to_delete = count // 10
            
            if self.debug:
                print(f"[CACHE] Evicting {to_delete} entries", file=os.sys.stderr)
            
            self.conn.execute("""
                DELETE FROM cfg_analysis_cache
                WHERE id IN (
                    SELECT id FROM cfg_analysis_cache
                    ORDER BY last_accessed ASC
                    LIMIT ?
                )
            """, (to_delete,))
            self.conn.commit()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total_entries,
                SUM(hit_count) as total_hits,
                AVG(hit_count) as avg_hits
            FROM cfg_analysis_cache
        """)
        
        row = cursor.fetchone()
        return {
            "total_entries": row[0] or 0,
            "total_hits": row[1] or 0,
            "avg_hits": row[2] or 0
        }
    
    def clear_cache(self):
        """Clear all cached entries."""
        if self.debug:
            print("[CACHE] Clearing all cache entries", file=os.sys.stderr)
        
        self.conn.execute("DELETE FROM cfg_analysis_cache")
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        self.conn.close()