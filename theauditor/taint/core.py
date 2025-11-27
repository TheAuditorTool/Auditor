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
from typing import Any, TYPE_CHECKING
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
        self.sources: dict[str, dict[str, list[str]]] = {}
        self.sinks: dict[str, dict[str, list[str]]] = {}
        self.sanitizers: dict[str, list[str]] = {}

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

    def get_sources_for_language(self, language: str) -> dict[str, list[str]]:
        """Get all source patterns for a specific language.

        Args:
            language: Language identifier (e.g., 'python', 'javascript')

        Returns:
            Dictionary mapping category to pattern list
        """
        return self.sources.get(language, {})

    def get_sinks_for_language(self, language: str) -> dict[str, list[str]]:
        """Get all sink patterns for a specific language.

        Args:
            language: Language identifier (e.g., 'python', 'javascript')

        Returns:
            Dictionary mapping category to pattern list
        """
        return self.sinks.get(language, {})

    def get_stats(self) -> dict[str, int]:
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

    # =========================================================================
    # DATABASE LOADING - Polyglot pattern loading (Phase 2 refactor 2025-11-27)
    # =========================================================================

    def load_from_database(self, cursor: sqlite3.Cursor) -> None:
        """Load patterns from database tables.

        Queries framework_taint_patterns for sources/sinks, framework_safe_sinks
        and validation_framework_usage for sanitizers.

        Args:
            cursor: Database cursor for repo_index.db

        Note: ZERO FALLBACK - if tables are empty, returns empty. No hardcoded defaults.
        """
        self._load_taint_patterns(cursor)
        self._load_safe_sinks(cursor)
        self._load_validation_sanitizers(cursor)

    def _load_taint_patterns(self, cursor: sqlite3.Cursor) -> None:
        """Load source/sink patterns from framework_taint_patterns table.

        Schema:
            framework_taint_patterns(id, framework_id, pattern, pattern_type, category)
            frameworks(id, name, version, language, path, source, package_manager, is_primary)

        This is the Database-First architecture fix: patterns are seeded during
        indexing and loaded here at analysis time.
        """
        query = """
            SELECT f.language, ftp.pattern, ftp.pattern_type, ftp.category
            FROM framework_taint_patterns ftp
            JOIN frameworks f ON ftp.framework_id = f.id
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            lang = row[0] or 'global'
            pattern = row[1]
            pattern_type = row[2]
            category = row[3] or 'unknown'

            if not pattern:
                continue

            if pattern_type == 'source':
                self.register_source(pattern, category, lang)
            elif pattern_type == 'sink':
                self.register_sink(pattern, category, lang)

    def _load_safe_sinks(self, cursor: sqlite3.Cursor) -> None:
        """Load safe sink patterns from framework_safe_sinks table.

        Schema:
            frameworks(id, name, version, language, path, source, package_manager, is_primary)
            framework_safe_sinks(framework_id, sink_pattern, sink_type, is_safe, reason)

        Note: Must JOIN with frameworks to get language column.
        """
        query = """
            SELECT f.language, fss.sink_pattern, fss.sink_type
            FROM framework_safe_sinks fss
            JOIN frameworks f ON fss.framework_id = f.id
            WHERE fss.is_safe = 1
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            lang = row[0] or 'global'
            pattern = row[1]
            if pattern:
                self.register_sanitizer(pattern, lang)

    def _load_validation_sanitizers(self, cursor: sqlite3.Cursor) -> None:
        """Load validation patterns from validation_framework_usage table.

        Schema:
            validation_framework_usage(
                file_path, line, framework, method, variable_name,
                is_validator, argument_expr
            )

        Registers validation methods as sanitizers (e.g., zod.parse, joi.validate).
        """
        query = """
            SELECT DISTINCT framework, method, variable_name
            FROM validation_framework_usage
            WHERE is_validator = 1
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            framework = row[0]
            method = row[1]
            var_name = row[2]

            # Register the method itself as sanitizer
            if method:
                self.register_sanitizer(method, 'javascript')

            # Register qualified patterns (e.g., 'schema.parse', 'userSchema.validate')
            if var_name and method:
                self.register_sanitizer(f"{var_name}.{method}", 'javascript')

            # Register framework-qualified patterns (e.g., 'zod.parse')
            if framework and method:
                self.register_sanitizer(f"{framework}.{method}", 'javascript')

    # =========================================================================
    # PATTERN ACCESSORS - Flattened pattern lists for taint analysis
    # =========================================================================

    def get_source_patterns(self, language: str) -> list[str]:
        """Get flattened list of source patterns for a language.

        Args:
            language: Language identifier ('python', 'javascript', 'rust')

        Returns:
            List of source patterns (e.g., ['req.body', 'req.params', 'req.query'])
        """
        patterns = []
        lang_sources = self.sources.get(language, {})
        for category_patterns in lang_sources.values():
            patterns.extend(category_patterns)
        return patterns

    def get_sink_patterns(self, language: str) -> list[str]:
        """Get flattened list of sink patterns for a language.

        Args:
            language: Language identifier ('python', 'javascript', 'rust')

        Returns:
            List of sink patterns (e.g., ['execute', 'eval', 'system'])
        """
        patterns = []
        lang_sinks = self.sinks.get(language, {})
        for category_patterns in lang_sinks.values():
            patterns.extend(category_patterns)
        return patterns

    def get_sanitizer_patterns(self, language: str) -> list[str]:
        """Get sanitizer patterns for a language (includes global sanitizers).

        Args:
            language: Language identifier ('python', 'javascript', 'rust')

        Returns:
            List of sanitizer patterns for the language + global sanitizers
        """
        patterns = []
        # Add global sanitizers first
        if 'global' in self.sanitizers:
            patterns.extend(self.sanitizers['global'])
        # Add language-specific sanitizers
        if language in self.sanitizers:
            patterns.extend(self.sanitizers[language])
        return patterns


# ============================================================================
# UTILITY FUNCTIONS (Moved from propagation.py during cleanup)
# ============================================================================

def has_sanitizer_between(cursor: sqlite3.Cursor, source: dict[str, Any], sink: dict[str, Any]) -> bool:
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


def deduplicate_paths(paths: list[Any]) -> list[Any]:  # Returns List[TaintPath]
    """Deduplicate taint paths while preserving the most informative flow for each source-sink pair.

    Key rule: Prefer cross-file / multi-hop and flow-sensitive paths over shorter, same-file variants.
    This prevents the Stage 2 direct path (2 steps) from overwriting Stage 3 multi-hop results.
    """

    def _path_score(path: Any) -> tuple[int, int, int]:
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
    unique_source_sink: dict[tuple[str, str], tuple[Any, tuple[int, int, int]]] = {}

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
    sink_groups: dict[tuple[str, int], list[Any]] = {}
    for path, _score in unique_source_sink.values():
        sink = path.sink
        sink_key = (sink.get("file", "unknown_file"), sink.get("line", 0))
        sink_groups.setdefault(sink_key, []).append(path)

    deduped_paths: list[Any] = []
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
                cache: MemoryCache | None = None,
                graph_db_path: str = None, mode: str = "backward") -> dict[str, Any]:
    """
    Perform taint analysis by tracing data flow from sources to sinks.

    Args:
        db_path: Path to repo_index.db database
        max_depth: Maximum depth to trace taint propagation (default 10)
        registry: MANDATORY TaintRegistry with patterns from rules (NO FALLBACK for backward mode)
        use_memory_cache: Enable in-memory caching for performance (default: True)
        memory_limit_mb: Memory limit for cache in MB (default: 12000)
        cache: Optional pre-loaded MemoryCache to use (avoids reload)
        graph_db_path: Path to graphs.db (default: .pf/graphs.db, MUST exist)
        mode: Analysis mode - 'backward' (IFDS), 'forward' or 'complete' (flow resolution)

    Mode Options:
        - backward: Traditional IFDS backward taint analysis (finds vulnerabilities)
        - forward/complete: Complete flow resolution to populate ALL flows

    IFDS Mode (backward - BASED ON ALLEN ET AL. 2021):
        Uses pre-computed graphs.db for 5-10 hop cross-file taint tracking.
        Implements demand-driven backward IFDS with access path tracking.
        NO FALLBACKS - If graphs.db or registry missing, CRASHES.

    Forward/Complete Mode (NEW - Codebase Truth Generation):
        Traces ALL flows from ALL entry points to ALL exit points.
        Populates resolved_flow_audit table with >100,000 resolved flows.
        Transforms codebase into queryable atomic truth for AI agents.

    Returns:
        Dictionary containing:
        - taint_paths: List of source-to-sink vulnerability paths
        - sources_found: Number of taint sources identified
        - sinks_found: Number of security sinks identified
        - vulnerabilities: Count by vulnerability type
        - total_flows_resolved: Number of flows resolved (forward mode only)
    """
    import sqlite3
    import os

    # ARCHITECTURAL FIX: Database-first architecture

    # Forward-Only Mode: Use FlowResolver for complete flow resolution (no vulnerability detection)
    if mode == "forward":
        print(f"[TAINT] Using forward-only flow resolution mode", file=sys.stderr)

        # Ensure graphs.db exists
        if graph_db_path is None:
            db_dir = Path(db_path).parent
            graph_db_path = str(db_dir / "graphs.db")

        if not Path(graph_db_path).exists():
            raise FileNotFoundError(
                f"graphs.db not found at {graph_db_path}. "
                f"Run 'aud graph build' to create it. "
                f"NO FALLBACKS - Flow resolution requires pre-computed graphs."
            )

        # Use FlowResolver for complete flow resolution
        from .flow_resolver import FlowResolver

        resolver = FlowResolver(db_path, graph_db_path, registry=registry)
        total_flows = resolver.resolve_all_flows()
        resolver.close()

        print(f"[TAINT] Flow resolution complete: {total_flows} flows resolved", file=sys.stderr)

        # TODO: Apply security rules from /rules/ to classify flows
        # For now, return success with flow count
        return {
            "success": True,
            "taint_paths": [],  # To be populated after rule application
            "vulnerabilities": [],
            "paths": [],
            "sources_found": 0,  # Will be updated after discovery
            "sinks_found": 0,  # Will be updated after discovery
            "total_vulnerabilities": 0,  # Will be updated after rule application
            "total_flows_resolved": total_flows,  # NEW field for forward mode
            "total_flows": total_flows,
            "vulnerabilities_by_type": {},
            "summary": {
                "total_count": total_flows,
                "by_type": {},
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0
            }
        }

    # Complete Mode: Run BOTH engines and merge results
    # ARCHITECTURAL FIX: Connects IFDS (backward) + FlowResolver (forward)
    if mode == "complete":
        print(f"[TAINT] Using complete mode: IFDS (backward) + FlowResolver (forward)", file=sys.stderr)

        # STEP 1: Run FlowResolver (forward flow resolution)
        print(f"[TAINT] STEP 1/2: Running FlowResolver (forward analysis)", file=sys.stderr)

        # Ensure graphs.db exists
        if graph_db_path is None:
            db_dir = Path(db_path).parent
            graph_db_path = str(db_dir / "graphs.db")

        if not Path(graph_db_path).exists():
            raise FileNotFoundError(
                f"graphs.db not found at {graph_db_path}. "
                f"Run 'aud graph build' to create it. "
                f"NO FALLBACKS - Flow resolution requires pre-computed graphs."
            )

        from .flow_resolver import FlowResolver

        resolver = FlowResolver(db_path, graph_db_path, registry=registry)
        total_flows = resolver.resolve_all_flows()
        resolver.close()

        print(f"[TAINT] FlowResolver complete: {total_flows} flows resolved", file=sys.stderr)

        # STEP 2: Run IFDS (backward vulnerability detection)
        # Registry is MANDATORY for this step
        if registry is None:
            raise ValueError(
                "Registry is MANDATORY for complete mode (includes IFDS). "
                "Run with orchestrator.collect_rule_patterns(registry) first. "
                "NO FALLBACKS ALLOWED."
            )

        print(f"[TAINT] STEP 2/2: Running IFDS (backward vulnerability analysis)", file=sys.stderr)

        # Fall through to backward mode logic below (lines 384+)
        # DO NOT return early - let the backward mode code run and merge with FlowResolver results

    # BACKWARD MODE (existing IFDS analysis)
    # ZERO FALLBACK POLICY: Registry is MANDATORY for backward mode
    if registry is None:
        raise ValueError(
            "Registry is MANDATORY for backward taint analysis. "
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
    merged_sources: dict[str, list[str]] = {}
    for lang_sources in registry.sources.values():
        for category, patterns in lang_sources.items():
            if category not in merged_sources:
                merged_sources[category] = []
            merged_sources[category].extend(patterns)

    merged_sinks: dict[str, list[str]] = {}
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
        # SCHEMA VALIDATION: Check if generated code is stale
        from theauditor.indexer.schemas.codegen import SchemaCodeGenerator
        from theauditor.utils.exit_codes import ExitCodes

        # Get current schema hash
        current_hash = SchemaCodeGenerator.get_schema_hash()

        # Check generated cache file for its hash
        cache_file = Path(__file__).parent.parent / 'indexer' / 'schemas' / 'generated_cache.py'
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
                output_dir = Path(__file__).parent.parent / 'indexer' / 'schemas'
                SchemaCodeGenerator.write_generated_code(output_dir)
                print("[SCHEMA FIX] Generated code updated successfully", file=sys.stderr)
                print("[SCHEMA FIX] Please re-run the command", file=sys.stderr)
                sys.exit(ExitCodes.SCHEMA_STALE)
            except Exception as e:
                print(f"[SCHEMA ERROR] Failed to regenerate code: {e}", file=sys.stderr)
                raise RuntimeError(f"Schema validation failed and auto-fix failed: {e}")

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
        from .type_resolver import TypeResolver

        # Create TypeResolver for ORM aliasing and controller detection
        graph_conn = sqlite3.connect(graph_db_path)
        graph_conn.row_factory = sqlite3.Row
        repo_conn = sqlite3.connect(db_path)
        repo_conn.row_factory = sqlite3.Row
        type_resolver = TypeResolver(graph_conn.cursor(), repo_conn.cursor())

        print(f"[TAINT] Analyzing {len(sinks)} sinks against {len(sources)} sources (demand-driven)", file=sys.stderr)
        sys.stderr.flush()

        ifds_analyzer = IFDSTaintAnalyzer(
            repo_db_path=db_path,
            graph_db_path=graph_db_path,
            cache=cache,
            registry=registry,
            type_resolver=type_resolver
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
        # Clean up TypeResolver connections
        graph_conn.close()
        repo_conn.close()
        print(f"[TAINT] IFDS found {len(all_vulnerable_paths)} vulnerable paths, {len(all_sanitized_paths)} sanitized paths", file=sys.stderr)

        # Step 5: Deduplicate vulnerable paths (keep legacy behavior)
        unique_vulnerable_paths = deduplicate_paths(all_vulnerable_paths)

        # PHASE 6: Deduplicate sanitized paths separately
        unique_sanitized_paths = deduplicate_paths(all_sanitized_paths)

        # Step 6: Persist flows to database (resolved_flow_audit table - PHASE 6)
        import json
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Clear existing IFDS flows only (preserve FlowResolver flows from complete mode)
        cursor.execute("DELETE FROM resolved_flow_audit WHERE engine = 'IFDS'")
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
                    status, sanitizer_file, sanitizer_line, sanitizer_method,
                    engine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                None,  # sanitizer_method
                'IFDS'  # engine column
            ))
            total_inserted += 1

        # Insert sanitized paths (status='SANITIZED', with sanitizer metadata)
        for path in unique_sanitized_paths:
            cursor.execute("""
                INSERT INTO resolved_flow_audit (
                    source_file, source_line, source_pattern,
                    sink_file, sink_line, sink_pattern,
                    vulnerability_type, path_length, hops, path_json, flow_sensitive,
                    status, sanitizer_file, sanitizer_line, sanitizer_method,
                    engine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                path.sanitizer_method,
                'IFDS'  # engine column
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

        # ARCHITECTURAL FIX: Include FlowResolver data if in complete mode
        result = {
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

        # ARCHITECTURAL FIX: If complete mode, add FlowResolver data
        if mode == "complete":
            # Query resolved_flow_audit to get FlowResolver results count
            # Filter by engine='FlowResolver' to separate from IFDS flows
            conn_temp = sqlite3.connect(db_path)
            cursor_temp = conn_temp.cursor()
            cursor_temp.execute("SELECT COUNT(*) FROM resolved_flow_audit WHERE engine = 'FlowResolver' AND status = 'VULNERABLE'")
            flow_resolver_vulnerable = cursor_temp.fetchone()[0]
            cursor_temp.execute("SELECT COUNT(*) FROM resolved_flow_audit WHERE engine = 'FlowResolver' AND status = 'SANITIZED'")
            flow_resolver_sanitized = cursor_temp.fetchone()[0]
            conn_temp.close()

            result["flow_resolver_vulnerable"] = flow_resolver_vulnerable
            result["flow_resolver_sanitized"] = flow_resolver_sanitized
            result["total_flows_resolved"] = total_flows  # From FlowResolver run above
            result["mode"] = "complete"
            result["engines_used"] = ["IFDS (backward)", "FlowResolver (forward)"]

            print(f"[TAINT] COMPLETE MODE RESULTS:", file=sys.stderr)
            print(f"[TAINT]   IFDS found: {len(unique_paths)} vulnerable paths", file=sys.stderr)
            print(f"[TAINT]   FlowResolver resolved: {total_flows} total flows", file=sys.stderr)
            print(f"[TAINT]   resolved_flow_audit table: {flow_resolver_vulnerable} vulnerable, {flow_resolver_sanitized} sanitized", file=sys.stderr)

        return result

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


def save_taint_analysis(analysis_result: dict[str, Any], output_path: str = "./.pf/taint_analysis.json"):
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


def normalize_taint_path(path: dict[str, Any]) -> dict[str, Any]:
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
