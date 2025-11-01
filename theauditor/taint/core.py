"""Core taint analysis engine.

This module contains the main taint analysis function and TaintPath class.

Schema Contract:
    All queries use build_query() for schema compliance.
    Table existence is guaranteed by schema contract - no checks needed.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from .memory_cache import MemoryCache

from theauditor.indexer.schema import build_query
from .sources import TAINT_SOURCES, SECURITY_SINKS, SANITIZERS
from .config import TaintConfig
from .database import (
    find_taint_sources,
    find_security_sinks,
    build_call_graph,
    get_containing_function,
)
from .propagation import deduplicate_paths
from .analysis import TaintFlowAnalyzer


class TaintPath:
    """Represents a taint flow path from source to sink."""
    
    def __init__(self, source: Dict[str, Any], sink: Dict[str, Any], path: List[Dict[str, Any]]):
        self.source = source
        self.sink = sink
        self.path = path
        self.vulnerability_type = self._classify_vulnerability()
        
        # CFG-specific attributes (optional, added by cfg_integration)
        self.flow_sensitive = False
        self.conditions = []
        self.condition_summary = ""
        self.path_complexity = 0
        self.tainted_vars = []
        self.sanitized_vars = []
        self.related_sources: List[Dict[str, Any]] = []
    
    def _classify_vulnerability(self) -> str:
        """Classify the vulnerability based on sink type - factual categorization."""
        sink_name = self.sink.get("name", "").lower()
        sink_category = self.sink.get("category", "")
        
        # Use category if available, otherwise infer from name
        if sink_category:
            category_map = {
                "sql": "SQL Injection",
                "command": "Command Injection", 
                "xss": "Cross-Site Scripting (XSS)",
                "path": "Path Traversal",
                "ldap": "LDAP Injection",
                "nosql": "NoSQL Injection"
            }
            return category_map.get(sink_category, "Data Exposure")
        
        # Fallback: infer from sink name patterns
        for vuln_type, sinks in SECURITY_SINKS.items():
            if any(s.lower() in sink_name for s in sinks):
                return {
                    "sql": "SQL Injection",
                    "command": "Command Injection",
                    "xss": "Cross-Site Scripting (XSS)",
                    "path": "Path Traversal",
                    "ldap": "LDAP Injection",
                    "nosql": "NoSQL Injection"
                }.get(vuln_type, "Data Exposure")
        
        return "Data Exposure"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization with guaranteed structure."""
        # Ensure source dict has all required keys
        source_dict = self.source or {}
        source_dict.setdefault("name", "unknown_source")
        source_dict.setdefault("file", "unknown_file")
        source_dict.setdefault("line", 0)
        source_dict.setdefault("pattern", "unknown_pattern")
        
        # Ensure sink dict has all required keys
        sink_dict = self.sink or {}
        sink_dict.setdefault("name", "unknown_sink")
        sink_dict.setdefault("file", "unknown_file")
        sink_dict.setdefault("line", 0)
        sink_dict.setdefault("pattern", "unknown_pattern")
        
        result = {
            "source": source_dict,
            "sink": sink_dict,
            "path": self.path or [],
            "path_length": len(self.path) if self.path else 0,
            "vulnerability_type": self.vulnerability_type
        }
        
        # Include CFG metadata if present (from cfg_integration)
        if self.flow_sensitive:
            result["flow_sensitive"] = self.flow_sensitive
            result["conditions"] = self.conditions
            result["condition_summary"] = self.condition_summary
            result["path_complexity"] = self.path_complexity
            result["tainted_vars"] = self.tainted_vars
            result["sanitized_vars"] = self.sanitized_vars
        
        if self.related_sources:
            result["related_sources"] = self.related_sources
            result["related_source_count"] = len(self.related_sources)
            result["unique_source_count"] = len(self.related_sources) + 1
        
        return result

    def add_related_path(self, other: "TaintPath") -> None:
        """Attach additional source/path metadata that reaches the same sink."""
        related_entry = {
            "source": {
                "file": other.source.get("file"),
                "line": other.source.get("line"),
                "name": other.source.get("name"),
                "pattern": other.source.get("pattern"),
            },
            "path": other.path,
            "path_length": len(other.path) if other.path else 0,
            "flow_sensitive": other.flow_sensitive,
        }
        self.related_sources.append(related_entry)


def trace_taint(db_path: str, max_depth: int = 5, registry=None,
                use_cfg: bool = True,
                use_memory_cache: bool = True, memory_limit_mb: int = 12000,
                cache: Optional['MemoryCache'] = None) -> Dict[str, Any]:
    """
    Perform taint analysis by tracing data flow from sources to sinks.

    Args:
        db_path: Path to the SQLite database
        max_depth: Maximum depth to trace taint propagation
        registry: Optional TaintRegistry with enriched patterns from rules
        use_cfg: Enable CFG-based analysis (Stage 3 multi-hop when True, Stage 2 when False)
        use_memory_cache: Enable in-memory caching for performance (default: True)
        memory_limit_mb: Memory limit for cache in MB (default: 12000)
        cache: Optional pre-loaded MemoryCache to use (avoids reload)

    Stage Selection (v1.2.1):
        - use_cfg=True: Stage 3 (CFG-based multi-hop with worklist)
        - use_cfg=False: Stage 2 (call-graph flow-insensitive)

    Note: The stage3 parameter was removed in v1.2.1 - use_cfg now controls everything.

    Returns:
        Dictionary containing:
        - taint_paths: List of source-to-sink vulnerability paths
        - sources_found: Number of taint sources identified
        - sinks_found: Number of security sinks identified
        - vulnerabilities: Count by vulnerability type
    """
    import sqlite3
    import os
    
    # Create configuration instead of modifying globals
    # This ensures thread safety and reentrancy
    
    # Load framework data from database (not output files)
    frameworks = []
    # CRITICAL FIX: Use parameter, don't shadow it
    db_path_obj = Path(db_path)
    if db_path_obj.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get all frameworks for enhancement
            # Schema Contract: frameworks table guaranteed to exist
            query = build_query('frameworks',
                ['name', 'version', 'language', 'path'],
                order_by="is_primary DESC"
            )
            cursor.execute(query)

            for name, version, language, path in cursor.fetchall():
                frameworks.append({
                    "framework": name,
                    "version": version or "unknown",
                    "language": language or "unknown",
                    "path": path or "."
                })

            conn.close()
        except (sqlite3.Error, ImportError):
            # Gracefully continue without framework enhancement
            pass
    
    # ARCHITECTURAL FIX: Database-first architecture
    # Framework patterns are handled upstream and registered via TaintRegistry
    # The taint analyzer operates ONLY on patterns provided by the registry
    if registry:
        # CRITICAL FIX: Load defaults FIRST, then merge registry on top
        # TaintConfig() creates empty config - we need from_defaults() first!
        config = TaintConfig.from_defaults().with_registry(registry)
    else:
        # Fallback to defaults if no registry provided
        # This maintains backward compatibility but won't include framework-specific patterns
        config = TaintConfig.from_defaults()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Attempt to preload database into memory cache for performance
    # CRITICAL FIX: Use provided cache if available (avoids reload in pipeline)
    if use_memory_cache:
        if cache is None:  # Only create if not provided
            # Always use SchemaMemoryCache (feature flags removed)
            from theauditor.indexer.schemas.generated_cache import SchemaMemoryCache
            from .schema_cache_adapter import SchemaMemoryCacheAdapter
            print("[TAINT] Using SchemaMemoryCache", file=sys.stderr)
            schema_cache = SchemaMemoryCache(db_path)
            cache = SchemaMemoryCacheAdapter(schema_cache)
            print(f"[TAINT] SchemaMemoryCache loaded: {cache.get_memory_usage_mb():.1f}MB", file=sys.stderr)
        else:
            # Using pre-loaded cache from pipeline
            print(f"[TAINT] Using pre-loaded cache: {cache.get_memory_usage_mb():.1f}MB", file=sys.stderr)
    else:
        cache = None  # Explicitly disable cache if not requested
    
    try:
        # Always use database-driven discovery when cache available (feature flags removed)
        if cache:
            # Use database-driven discovery
            from .discovery import TaintDiscovery
            print("[TAINT] Using database-driven discovery", file=sys.stderr)
            discovery = TaintDiscovery(cache)
            sources = discovery.discover_sources(config.sources)
            sinks = discovery.discover_sinks(config.sinks)
            sinks = discovery.filter_framework_safe_sinks(sinks)
        else:
            # Fallback when cache not available (should be rare)
            # This is not a feature flag, just handling when cache is disabled
            print("[TAINT] Cache not available, using direct database queries", file=sys.stderr)
            sources = find_taint_sources(cursor, config.sources, cache=None)
            sinks = find_security_sinks(cursor, config.sinks, cache=None)
            from .database import filter_framework_safe_sinks
            sinks = filter_framework_safe_sinks(cursor, sinks)

        # Step 3: Build a call graph for efficient traversal
        call_graph = build_call_graph(cursor)

        # Step 3.5: Helper function for proximity filtering
        def filter_sinks_by_proximity(source, all_sinks):
            """Filter sinks to same module as source for performance.

            Reduces O(sources × sinks) from 4M to ~400K combinations.
            Trade-off: May miss legitimate cross-module flows.
            """
            source_file = source.get('file', '')
            if not source_file:
                return all_sinks  # No filtering if source file unknown

            # Extract top-level module (e.g., 'theauditor' from 'theauditor/taint/core.py')
            source_parts = source_file.replace('\\', '/').split('/')
            source_module = source_parts[0] if source_parts else ''

            if not source_module:
                return all_sinks

            # Filter sinks to same top-level module
            filtered = []
            for sink in all_sinks:
                sink_file = sink.get('file', '')
                if not sink_file:
                    continue
                sink_parts = sink_file.replace('\\', '/').split('/')
                sink_module = sink_parts[0] if sink_parts else ''

                if sink_module == source_module:
                    filtered.append(sink)

            # If no sinks in same module, return all (fallback for cross-module flows)
            return filtered if filtered else all_sinks

        # Step 4: Trace taint flow from each source
        taint_paths = []

        # Use unified analyzer if CFG enabled and cache available
        if use_cfg and cache:
            analyzer = TaintFlowAnalyzer(cache, cursor)
            taint_paths = analyzer.analyze_interprocedural(sources, sinks, call_graph, max_depth)
        else:
            # Fallback to old method for now (will be removed in final cleanup)
            from .propagation import trace_from_source
            for source in sources:
                # Find what function contains this source
                source_function = get_containing_function(cursor, source)
                if not source_function:
                    continue

                # Filter sinks by proximity for performance (10x speedup)
                relevant_sinks = filter_sinks_by_proximity(source, sinks)

                # Trace taint propagation from this source
                paths = trace_from_source(
                    cursor, source, source_function, relevant_sinks, call_graph, max_depth, use_cfg, cache=cache
                )
                taint_paths.extend(paths)
        
        # Step 5: Deduplicate paths
        unique_paths = deduplicate_paths(taint_paths)
        
        # Step 6: Build factual summary with vulnerability counts
        # Count vulnerabilities by type (factual categorization, not interpretation)
        # Clean implementation - only TaintPath objects now
        vulnerabilities_by_type = defaultdict(int)
        for path in unique_paths:
            vulnerabilities_by_type[path.vulnerability_type] += 1
        
        # Convert paths to dictionaries
        # Clean implementation - all paths are TaintPath objects
        path_dicts = [p.to_dict() for p in unique_paths]
        
        # Create summary for pipeline integration
        summary = {
            "total_count": len(unique_paths),
            "by_type": dict(vulnerabilities_by_type),
            # Basic counts for pipeline - no severity interpretation
            "critical_count": 0,  # Base analyzer doesn't assign severity
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0
        }

        return {
            "success": True,
            "taint_paths": path_dicts,  # Keep original key for backward compatibility
            "vulnerabilities": path_dicts,  # Expected key for pipeline
            "paths": path_dicts,  # Add expected key for report generation
            "sources_found": len(sources),
            "sinks_found": len(sinks),
            "total_vulnerabilities": len(unique_paths),  # Expected field name
            "total_flows": len(unique_paths),  # Keep for compatibility
            "vulnerabilities_by_type": dict(vulnerabilities_by_type),
            "summary": summary
        }
        
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            return {
                "success": False,
                "error": "Database is corrupted or incomplete. Run 'aud index' to rebuild the repository index.",
                "taint_paths": [],
                "vulnerabilities": [],
                "paths": [],  # Include both keys for compatibility
                "sources_found": 0,
                "sinks_found": 0,
                "total_vulnerabilities": 0,
                "total_flows": 0,
                "vulnerabilities_by_type": {},
                "summary": {"total_count": 0, "by_type": {}, "critical_count": 0, "high_count": 0, "medium_count": 0, "low_count": 0}
            }
        else:
            return {
                "success": False,
                "error": str(e),
                "taint_paths": [],
                "vulnerabilities": [],
                "paths": [],
                "sources_found": 0,
                "sinks_found": 0,
                "total_vulnerabilities": 0,
                "total_flows": 0,
                "vulnerabilities_by_type": {},
                "summary": {"total_count": 0, "by_type": {}, "critical_count": 0, "high_count": 0, "medium_count": 0, "low_count": 0}
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "taint_paths": [],
            "vulnerabilities": [],
            "paths": [],  # Include both keys for compatibility
            "sources_found": 0,
            "sinks_found": 0,
            "total_vulnerabilities": 0,
            "total_flows": 0,
            "vulnerabilities_by_type": {},
            "summary": {"total_count": 0, "by_type": {}, "critical_count": 0, "high_count": 0, "medium_count": 0, "low_count": 0}
        }
    finally:
        conn.close()
        # No need to restore globals - we never modified them!


def save_taint_analysis(analysis_result: Dict[str, Any], output_path: str = "./.pf/taint_analysis.json"):
    """Save taint analysis results to JSON file with normalized structure."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Normalize all paths before saving
    if "taint_paths" in analysis_result:
        analysis_result["taint_paths"] = [
            normalize_taint_path(p) for p in analysis_result.get("taint_paths", [])
        ]
    if "paths" in analysis_result:
        analysis_result["paths"] = [
            normalize_taint_path(p) for p in analysis_result.get("paths", [])
        ]
    
    with open(output, "w") as f:
        json.dump(analysis_result, f, indent=2, sort_keys=True)


def normalize_taint_path(path: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a taint path dictionary to ensure all required keys exist."""
    # Ensure top-level keys
    # REMOVED: vulnerability_type and severity - Truth Couriers don't classify
    path.setdefault("path_length", 0)
    path.setdefault("path", [])
    
    # Ensure source structure
    if "source" not in path:
        path["source"] = {}
    path["source"].setdefault("name", "unknown_source")
    path["source"].setdefault("file", "unknown_file")
    path["source"].setdefault("line", 0)
    path["source"].setdefault("pattern", "unknown_pattern")
    
    # Ensure sink structure
    if "sink" not in path:
        path["sink"] = {}
    path["sink"].setdefault("name", "unknown_sink")
    path["sink"].setdefault("file", "unknown_file")
    path["sink"].setdefault("line", 0)
    path["sink"].setdefault("pattern", "unknown_pattern")
    
    return path
