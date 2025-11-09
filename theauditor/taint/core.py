"""Core taint analysis engine.

This module contains the main taint analysis function and TaintPath class.

Schema Contract:
    All queries use build_query() for schema compliance.
    Table existence is guaranteed by schema contract - no checks needed.
"""

import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING, Tuple
from collections import defaultdict

if TYPE_CHECKING:
    from .memory_cache import MemoryCache

from theauditor.indexer.schema import build_query
# ARCHITECTURAL FIX (2025-11-09): TaintFlowAnalyzer removed (dormant engine)
# analysis.py renamed to analysis.py.backup per Priority 1 directive
# Only IFDSTaintAnalyzer is active (ifds_analyzer.py)


# ============================================================================
# TAINT REGISTRY - Pattern accumulator for dynamic rule discovery
# ============================================================================

class TaintRegistry:
    """Lightweight pattern accumulator for taint sources, sinks, and sanitizers.

    Populated dynamically by orchestrator from 200+ rules, then fed to discovery.

    Structure: Language-aware nested dictionaries
        sources[language][category] = [patterns]
        sinks[language][category] = [patterns]
        sanitizers[language] = [patterns]

    This allows orchestrator to filter rules by detected frameworks (e.g., only
    run Python rules if Flask detected) and populate registry with pre-filtered patterns.
    """

    def __init__(self):
        # Language-aware nested structure: sources[language][category] = [patterns]
        self.sources: Dict[str, Dict[str, List[str]]] = {}
        self.sinks: Dict[str, Dict[str, List[str]]] = {}
        self.sanitizers: Dict[str, List[str]] = {}

    def register_source(self, pattern: str, category: str, language: str):
        """Register a taint source pattern for a specific language.

        Args:
            pattern: Source pattern (e.g., 'req.body', 'request.args')
            category: Source category (e.g., 'user_input', 'http_request')
            language: Language identifier (e.g., 'python', 'javascript', 'rust')
        """
        if language not in self.sources:
            self.sources[language] = {}
        if category not in self.sources[language]:
            self.sources[language][category] = []
        if pattern not in self.sources[language][category]:
            self.sources[language][category].append(pattern)

    def register_sink(self, pattern: str, category: str, language: str):
        """Register a taint sink pattern for a specific language.

        Args:
            pattern: Sink pattern (e.g., 'execute', 'eval', 'system')
            category: Sink category (e.g., 'sql', 'command', 'xss')
            language: Language identifier (e.g., 'python', 'javascript', 'rust')
        """
        if language not in self.sinks:
            self.sinks[language] = {}
        if category not in self.sinks[language]:
            self.sinks[language][category] = []
        if pattern not in self.sinks[language][category]:
            self.sinks[language][category].append(pattern)

    def register_sanitizer(self, pattern: str, language: str = None):
        """Register a sanitizer pattern, optionally language-specific.

        Args:
            pattern: Sanitizer function name (e.g., 'sanitize', 'escape')
            language: Optional language identifier (None = applies to all languages)
        """
        lang_key = language if language else 'global'
        if lang_key not in self.sanitizers:
            self.sanitizers[lang_key] = []
        if pattern not in self.sanitizers[lang_key]:
            self.sanitizers[lang_key].append(pattern)

    def is_sanitizer(self, function_name: str, language: str = None) -> bool:
        """Check if a function is a registered sanitizer.

        Args:
            function_name: Function name to check
            language: Optional language to check (also checks global sanitizers)

        Returns:
            True if function is a registered sanitizer
        """
        # Check global sanitizers
        if 'global' in self.sanitizers and function_name in self.sanitizers['global']:
            return True
        # Check language-specific sanitizers
        if language and language in self.sanitizers and function_name in self.sanitizers[language]:
            return True
        return False

    def get_sources_for_language(self, language: str) -> Dict[str, List[str]]:
        """Get all source patterns for a specific language.

        Args:
            language: Language identifier (e.g., 'python', 'javascript')

        Returns:
            Dictionary mapping category to pattern list
        """
        return self.sources.get(language, {})

    def get_sinks_for_language(self, language: str) -> Dict[str, List[str]]:
        """Get all sink patterns for a specific language.

        Args:
            language: Language identifier (e.g., 'python', 'javascript')

        Returns:
            Dictionary mapping category to pattern list
        """
        return self.sinks.get(language, {})

    def get_stats(self) -> Dict[str, int]:
        """Get registry statistics for debugging.

        Returns:
            Dictionary with simple total counts
        """
        # Count total sources across all languages
        total_sources = sum(
            len(patterns)
            for lang_sources in self.sources.values()
            for patterns in lang_sources.values()
        )

        # Count total sinks across all languages
        total_sinks = sum(
            len(patterns)
            for lang_sinks in self.sinks.values()
            for patterns in lang_sinks.values()
        )

        # Count total sanitizers
        total_sanitizers = sum(len(patterns) for patterns in self.sanitizers.values())

        return {
            'total_sources': total_sources,
            'total_sinks': total_sinks,
            'total_sanitizers': total_sanitizers
        }


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

        # PHASE 6: Sanitizer metadata (added by ifds_analyzer when path is sanitized)
        self.sanitizer_file: Optional[str] = None
        self.sanitizer_line: Optional[int] = None
        self.sanitizer_method: Optional[str] = None
    
    def _classify_vulnerability(self) -> str:
        """Classify the vulnerability based on sink type - factual categorization.

        Uses sink category from discovery (populated by database queries).
        ZERO FALLBACK POLICY: If category missing, return generic type.
        """
        sink_category = self.sink.get("category", "")

        # Map sink category to vulnerability classification
        # These are factual categories from database schema, not interpretations
        category_map = {
            "sql": "SQL Injection",
            "command": "Command Injection",
            "xss": "Cross-Site Scripting (XSS)",
            "path": "Path Traversal",
            "ldap": "LDAP Injection",
            "nosql": "NoSQL Injection"
        }

        return category_map.get(sink_category, "Data Exposure")
    
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


# ============================================================================
# UTILITY FUNCTIONS (Moved from propagation.py during cleanup)
# ============================================================================

def has_sanitizer_between(cursor: sqlite3.Cursor, source: Dict[str, Any], sink: Dict[str, Any]) -> bool:
    """Check if there's a sanitizer call between source and sink in the same function.

    Schema Contract:
        Queries symbols table (guaranteed to exist)
    """
    if source["file"] != sink["file"]:
        return False

    # Initialize registry for sanitizer checking
    registry = TaintRegistry()

    # Find all calls between source and sink lines
    query = build_query('symbols', ['name', 'line'],
        where="path = ? AND type = 'call' AND line > ? AND line < ?",
        order_by="line"
    )
    cursor.execute(query, (source["file"], source["line"], sink["line"]))

    intermediate_calls = cursor.fetchall()

    # Check if any intermediate call is a sanitizer using registry
    for call_name, _ in intermediate_calls:
        if registry.is_sanitizer(call_name):
            return True

    return False


def deduplicate_paths(paths: List[Any]) -> List[Any]:  # Returns List[TaintPath]
    """Deduplicate taint paths while preserving the most informative flow for each source-sink pair.

    Key rule: Prefer cross-file / multi-hop and flow-sensitive paths over shorter, same-file variants.
    This prevents the Stage 2 direct path (2 steps) from overwriting Stage 3 multi-hop results.
    """

    def _path_score(path: Any) -> Tuple[int, int, int]:
        """Score paths so we keep the most informative version per source/sink pair.

        Score dimensions (higher is better):
        1. Number of cross-file hops (`cfg_call`, `argument_pass`, `return_flow`)
        2. Whether the path used flow-sensitive analysis (Stage 3)
        3. Path length (prefer longer when cross-file, shorter otherwise)
        """
        steps = path.path or []

        cross_hops = 0
        uses_cfg = bool(getattr(path, "flow_sensitive", False))

        for step in steps:
            step_type = step.get("type")
            if step_type == "cfg_call":
                uses_cfg = True  # Ensure cfg-aware paths win ties
            if step_type in {"cfg_call", "argument_pass", "return_flow"}:
                from_file = step.get("from_file")
                to_file = step.get("to_file")
                # Always print for cfg_call to debug
                if step_type == "cfg_call":
                    print(f"[DEDUP] cfg_call step: from={from_file} to={to_file}", file=sys.stderr)
                if from_file and to_file and from_file != to_file:
                    cross_hops += 1
                    print(f"[DEDUP] Cross-file hop detected! cross_hops={cross_hops}", file=sys.stderr)

        length = len(steps)

        # Prefer longer paths when they traverse files, shorter otherwise (cleaner intra-file output)
        length_component = length if cross_hops else -length

        if cross_hops > 0:
            print(f"[DEDUP] Path score: cross_hops={cross_hops}, uses_cfg={1 if uses_cfg else 0}, length={length_component}", file=sys.stderr)

        return (cross_hops, 1 if uses_cfg else 0, length_component)

    # Phase 1: retain the best path for each unique source/sink pairing.
    unique_source_sink: Dict[Tuple[str, str], Tuple[Any, Tuple[int, int, int]]] = {}

    for path in paths:
        key = (
            f"{path.source['file']}:{path.source['line']}",
            f"{path.sink['file']}:{path.sink['line']}",
        )
        score = _path_score(path)

        if key not in unique_source_sink or score > unique_source_sink[key][1]:
            unique_source_sink[key] = (path, score)

    if not unique_source_sink:
        return []

    # Phase 2: group by sink location so we only emit one finding per sink line.
    sink_groups: Dict[Tuple[str, int], List[Any]] = {}
    for path, _score in unique_source_sink.values():
        sink = path.sink
        sink_key = (sink.get("file", "unknown_file"), sink.get("line", 0))
        sink_groups.setdefault(sink_key, []).append(path)

    deduped_paths: List[Any] = []
    for sink_key, sink_paths in sink_groups.items():
        if not sink_paths:
            continue

        scored_paths = [(p, _path_score(p)) for p in sink_paths]
        scored_paths.sort(key=lambda item: item[1], reverse=True)
        best_path, _ = scored_paths[0]

        # Reset aggregation before attaching related sources
        best_path.related_sources = []

        for other_path, _ in scored_paths[1:]:
            best_path.add_related_path(other_path)

        deduped_paths.append(best_path)

    # Debug: Check what we're returning
    multi_file_count = sum(1 for p in deduped_paths if p.source.get('file') != p.sink.get('file'))
    print(f"[DEDUP] Returning {len(deduped_paths)} paths ({multi_file_count} multi-file)", file=sys.stderr)

    return deduped_paths


# ============================================================================
# MAIN TAINT ANALYSIS FUNCTION
# ============================================================================

def trace_taint(db_path: str, max_depth: int = 10, registry=None,
                use_memory_cache: bool = True, memory_limit_mb: int = 12000,
                cache: Optional['MemoryCache'] = None,
                graph_db_path: str = None) -> Dict[str, Any]:
    """
    Perform taint analysis by tracing data flow from sources to sinks.

    Args:
        db_path: Path to repo_index.db database
        max_depth: Maximum depth to trace taint propagation (default 10)
        registry: MANDATORY TaintRegistry with patterns from rules (NO FALLBACK)
        use_memory_cache: Enable in-memory caching for performance (default: True)
        memory_limit_mb: Memory limit for cache in MB (default: 12000)
        cache: Optional pre-loaded MemoryCache to use (avoids reload)
        graph_db_path: Path to graphs.db (default: .pf/graphs.db, MUST exist)

    IFDS Mode (ONLY MODE - BASED ON ALLEN ET AL. 2021):
        Uses pre-computed graphs.db for 5-10 hop cross-file taint tracking.
        Implements demand-driven backward IFDS with access path tracking.
        NO FALLBACKS - If graphs.db or registry missing, CRASHES.

    Returns:
        Dictionary containing:
        - taint_paths: List of source-to-sink vulnerability paths
        - sources_found: Number of taint sources identified
        - sinks_found: Number of security sinks identified
        - vulnerabilities: Count by vulnerability type
    """
    import sqlite3
    import os

    # ARCHITECTURAL FIX: Database-first architecture
    # ZERO FALLBACK POLICY: Registry is MANDATORY
    if registry is None:
        raise ValueError(
            "Registry is MANDATORY for taint analysis. "
            "Run with orchestrator.collect_rule_patterns(registry) first. "
            "NO FALLBACKS ALLOWED."
        )

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

    # Merge all language-specific patterns into flat structure for discovery
    # Orchestrator has already filtered rules by detected frameworks,
    # so registry only contains patterns for languages present in the project
    merged_sources: Dict[str, List[str]] = {}
    for lang_sources in registry.sources.values():
        for category, patterns in lang_sources.items():
            if category not in merged_sources:
                merged_sources[category] = []
            merged_sources[category].extend(patterns)

    merged_sinks: Dict[str, List[str]] = {}
    for lang_sinks in registry.sinks.values():
        for category, patterns in lang_sinks.items():
            if category not in merged_sinks:
                merged_sinks[category] = []
            merged_sinks[category].extend(patterns)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # CRITICAL: Cache is MANDATORY (ZERO FALLBACK POLICY)
    # Database is regenerated fresh every run - if cache fails, pipeline is broken
    if cache is None:
        from theauditor.indexer.schemas.generated_cache import SchemaMemoryCache
        from .schema_cache_adapter import SchemaMemoryCacheAdapter
        print("[TAINT] Creating SchemaMemoryCache (mandatory for discovery)", file=sys.stderr)
        schema_cache = SchemaMemoryCache(db_path)
        cache = SchemaMemoryCacheAdapter(schema_cache)
        print(f"[TAINT] SchemaMemoryCache loaded: {cache.get_memory_usage_mb():.1f}MB", file=sys.stderr)
    else:
        print(f"[TAINT] Using pre-loaded cache: {cache.get_memory_usage_mb():.1f}MB", file=sys.stderr)

    try:
        # Database-driven discovery (cache guaranteed to exist)
        from .discovery import TaintDiscovery
        print("[TAINT] Using database-driven discovery", file=sys.stderr)
        discovery = TaintDiscovery(cache)

        # Discover sanitizers from framework tables and register them
        print("[TAINT] Discovering sanitizers from framework tables", file=sys.stderr)
        sanitizers = discovery.discover_sanitizers()
        for sanitizer in sanitizers:
            # Register sanitizers by language
            lang = sanitizer.get('language', 'global')
            pattern = sanitizer.get('pattern', '')
            if pattern:
                registry.register_sanitizer(pattern, lang)
        print(f"[TAINT] Registered {len(sanitizers)} sanitizers from frameworks", file=sys.stderr)

        sources = discovery.discover_sources(merged_sources)
        sinks = discovery.discover_sinks(merged_sinks)
        sinks = discovery.filter_framework_safe_sinks(sinks)

        # Helper function for proximity filtering
        def filter_sinks_by_proximity(source, all_sinks):
            """Filter sinks to same module as source for performance.

            Reduces O(sources × sinks) from 4M to ~400K combinations.
            ZERO FALLBACK: Returns empty list if source file missing (discovery bug).
            """
            source_file = source.get('file', '')
            if not source_file:
                # ZERO FALLBACK POLICY: Source without file is discovery bug, skip it
                return []

            # Extract top-level module (e.g., 'theauditor' from 'theauditor/taint/core.py')
            source_parts = source_file.replace('\\', '/').split('/')
            source_module = source_parts[0] if source_parts else ''

            if not source_module:
                # ZERO FALLBACK POLICY: No module means malformed path, skip it
                return []

            # Filter sinks to same top-level module
            filtered = []
            for sink in all_sinks:
                sink_file = sink.get('file', '')
                if not sink_file:
                    # Skip malformed sink (discovery bug)
                    continue
                sink_parts = sink_file.replace('\\', '/').split('/')
                sink_module = sink_parts[0] if sink_parts else ''

                if sink_module == source_module:
                    filtered.append(sink)

            # ZERO FALLBACK POLICY: Return filtered results only
            # Cross-module flows handled by IFDS multi-hop analysis
            return filtered

        # Step 4: IFDS Taint Analysis (ONLY MODE - NO FALLBACKS)
        # ZERO FALLBACK POLICY: graphs.db MUST exist or CRASH
        if graph_db_path is None:
            db_dir = Path(db_path).parent
            graph_db_path = str(db_dir / "graphs.db")

        if not Path(graph_db_path).exists():
            raise FileNotFoundError(
                f"graphs.db not found at {graph_db_path}. "
                f"Run 'aud graph build' to create it. "
                f"NO FALLBACKS - Taint analysis requires pre-computed graphs."
            )

        print(f"[TAINT] Using IFDS mode with graphs.db", file=sys.stderr)
        sys.stderr.flush()

        from .ifds_analyzer import IFDSTaintAnalyzer

        print(f"[TAINT] Analyzing {len(sinks)} sinks against {len(sources)} sources (demand-driven)", file=sys.stderr)
        sys.stderr.flush()

        ifds_analyzer = IFDSTaintAnalyzer(
            repo_db_path=db_path,
            graph_db_path=graph_db_path,
            cache=cache,
            registry=registry
        )
        ifds_analyzer.debug = os.environ.get("THEAUDITOR_DEBUG") or os.environ.get("THEAUDITOR_TAINT_DEBUG")

        # PHASE 6: Collect BOTH vulnerable and sanitized paths
        all_vulnerable_paths = []
        all_sanitized_paths = []

        # Adaptive progress interval: 10% of total sinks (min 100, max 1000)
        progress_interval = max(100, min(1000, len(sinks) // 10))
        for idx, sink in enumerate(sinks):
            if idx % progress_interval == 0:
                total_found = len(all_vulnerable_paths) + len(all_sanitized_paths)
                print(f"[TAINT] Progress: {idx}/{len(sinks)} sinks analyzed, {total_found} total paths ({len(all_vulnerable_paths)} vulnerable, {len(all_sanitized_paths)} sanitized)", file=sys.stderr)
                sys.stderr.flush()

            vulnerable, sanitized = ifds_analyzer.analyze_sink_to_sources(sink, sources, max_depth)
            all_vulnerable_paths.extend(vulnerable)
            all_sanitized_paths.extend(sanitized)

        ifds_analyzer.close()
        print(f"[TAINT] IFDS found {len(all_vulnerable_paths)} vulnerable paths, {len(all_sanitized_paths)} sanitized paths", file=sys.stderr)

        # PHASE 6: Merge for deduplication (keeps best path per sink)
        taint_paths = all_vulnerable_paths  # Use vulnerable paths for backward compatibility

        # Step 5: Deduplicate vulnerable paths (keep legacy behavior)
        unique_vulnerable_paths = deduplicate_paths(all_vulnerable_paths)

        # PHASE 6: Deduplicate sanitized paths separately
        unique_sanitized_paths = deduplicate_paths(all_sanitized_paths)

        # Step 6: Persist flows to database (resolved_flow_audit table - PHASE 6)
        import json
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Clear existing flows from both tables
        cursor.execute("DELETE FROM resolved_flow_audit")
        cursor.execute("DELETE FROM taint_flows")  # Keep for backward compatibility

        # PHASE 6: Insert ALL resolved flows (vulnerable + sanitized) into resolved_flow_audit
        total_inserted = 0

        # Insert vulnerable paths (status='VULNERABLE', no sanitizer)
        for path in unique_vulnerable_paths:
            cursor.execute("""
                INSERT INTO resolved_flow_audit (
                    source_file, source_line, source_pattern,
                    sink_file, sink_line, sink_pattern,
                    vulnerability_type, path_length, hops, path_json, flow_sensitive,
                    status, sanitizer_file, sanitizer_line, sanitizer_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                path.source.get('file', ''),
                path.source.get('line', 0),
                path.source.get('pattern', ''),
                path.sink.get('file', ''),
                path.sink.get('line', 0),
                path.sink.get('pattern', ''),
                path.vulnerability_type,
                len(path.path) if path.path else 0,
                len(path.path) if path.path else 0,
                json.dumps(path.path) if path.path else '[]',
                1,  # flow_sensitive = True (IFDS is CFG-aware)
                'VULNERABLE',  # status
                None,  # sanitizer_file
                None,  # sanitizer_line
                None   # sanitizer_method
            ))
            total_inserted += 1

        # Insert sanitized paths (status='SANITIZED', with sanitizer metadata)
        for path in unique_sanitized_paths:
            cursor.execute("""
                INSERT INTO resolved_flow_audit (
                    source_file, source_line, source_pattern,
                    sink_file, sink_line, sink_pattern,
                    vulnerability_type, path_length, hops, path_json, flow_sensitive,
                    status, sanitizer_file, sanitizer_line, sanitizer_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                path.source.get('file', ''),
                path.source.get('line', 0),
                path.source.get('pattern', ''),
                path.sink.get('file', ''),
                path.sink.get('line', 0),
                path.sink.get('pattern', ''),
                path.vulnerability_type,
                len(path.path) if path.path else 0,
                len(path.path) if path.path else 0,
                json.dumps(path.path) if path.path else '[]',
                1,  # flow_sensitive = True (IFDS is CFG-aware)
                'SANITIZED',  # status
                path.sanitizer_file,
                path.sanitizer_line,
                path.sanitizer_method
            ))
            total_inserted += 1

        # BACKWARD COMPATIBILITY: Also write vulnerable paths to taint_flows table
        for path in unique_vulnerable_paths:
            cursor.execute("""
                INSERT INTO taint_flows (
                    source_file, source_line, source_pattern,
                    sink_file, sink_line, sink_pattern,
                    vulnerability_type, path_length, hops, path_json, flow_sensitive
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                path.source.get('file', ''),
                path.source.get('line', 0),
                path.source.get('pattern', ''),
                path.sink.get('file', ''),
                path.sink.get('line', 0),
                path.sink.get('pattern', ''),
                path.vulnerability_type,
                len(path.path) if path.path else 0,
                len(path.path) if path.path else 0,
                json.dumps(path.path) if path.path else '[]',
                1  # flow_sensitive = True (IFDS is CFG-aware)
            ))

        conn.commit()
        conn.close()
        print(f"[TAINT] Persisted {total_inserted} flows to resolved_flow_audit ({len(unique_vulnerable_paths)} vulnerable, {len(unique_sanitized_paths)} sanitized)", file=sys.stderr)
        print(f"[TAINT] Persisted {len(unique_vulnerable_paths)} vulnerable flows to taint_flows (backward compatibility)", file=sys.stderr)

        # Continue using unique_vulnerable_paths for return value (backward compatibility)
        unique_paths = unique_vulnerable_paths

        # Step 7: Build factual summary with vulnerability counts
        # Count vulnerabilities by type (factual categorization, not interpretation)
        # Clean implementation - only TaintPath objects now
        vulnerabilities_by_type = defaultdict(int)
        for path in unique_paths:
            vulnerabilities_by_type[path.vulnerability_type] += 1

        # Convert paths to dictionaries
        # Clean implementation - all paths are TaintPath objects
        path_dicts = [p.to_dict() for p in unique_paths]

        # Debug: Check multi-file counts before returning
        multi_file_in_dicts = sum(1 for p in path_dicts if p['source']['file'] != p['sink']['file'])
        print(f"[CORE] Serialized {len(path_dicts)} paths ({multi_file_in_dicts} multi-file)", file=sys.stderr)
        
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
        # ZERO FALLBACK POLICY: Print error before returning (hard fail)
        import traceback
        error_msg = f"[TAINT ERROR] {str(e)}"
        traceback_str = traceback.format_exc()
        print(error_msg, file=sys.stderr)
        print(traceback_str, file=sys.stderr)

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
    # Debug: Check if we're losing multi-file paths
    src_file_before = path.get("source", {}).get("file", "MISSING")
    sink_file_before = path.get("sink", {}).get("file", "MISSING")

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

    # Debug: Check if normalization changed anything
    src_file_after = path["source"]["file"]
    sink_file_after = path["sink"]["file"]
    if src_file_before != src_file_after or sink_file_before != sink_file_after:
        print(f"[NORMALIZE] Changed: {src_file_before} -> {src_file_after}, {sink_file_before} -> {sink_file_after}", file=sys.stderr)

    return path
