"""Core taint analysis engine."""

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from theauditor.utils.logging import logger

if TYPE_CHECKING:
    from .memory_cache import MemoryCache

from theauditor.indexer.schema import build_query
from theauditor.taint.fidelity import (
    create_analysis_manifest,
    create_db_manifest,
    create_db_receipt,
    create_discovery_manifest,
    reconcile_taint_fidelity,
)


class TaintRegistry:
    """Single Source of Truth for taint patterns with O(1) metadata lookup.

    Replaces hardcoded pattern lists in discovery.py and taint_path.py with
    database-driven lookups that compute vulnerability types at registration time.
    """

    CATEGORY_TO_VULN_TYPE: dict[str, str] = {
        "xss": "Cross-Site Scripting (XSS)",
        "sql": "SQL Injection",
        "nosql": "NoSQL Injection",
        "command": "Command Injection",
        "code_injection": "Code Injection",
        "path": "Path Traversal",
        "ldap": "LDAP Injection",
        "ssrf": "Server-Side Request Forgery (SSRF)",
        "proto": "Prototype Pollution",
        "log": "Log Injection",
        "redirect": "Open Redirect",
        "crypto": "Weak Cryptography",
        "http_request": "Unvalidated Input",
        "user_input": "Unvalidated Input",
        "orm": "ORM Injection",
        "template": "Template Injection",
        "deserialization": "Insecure Deserialization",
        "xxe": "XML External Entity (XXE)",
        "unknown": "Data Exposure",
    }

    def __init__(self):
        self.sources: dict[str, dict[str, list[str]]] = {}
        self.sinks: dict[str, dict[str, list[str]]] = {}
        self.sanitizers: dict[str, list[str]] = {}

        self.sink_metadata: dict[str, dict[str, Any]] = {}
        self.source_metadata: dict[str, dict[str, Any]] = {}

    def register_source(self, pattern: str, category: str, language: str):
        """Register a taint source pattern with metadata for O(1) lookup."""
        if language not in self.sources:
            self.sources[language] = {}
        if category not in self.sources[language]:
            self.sources[language][category] = []
        if pattern not in self.sources[language][category]:
            self.sources[language][category].append(pattern)

        self.source_metadata[pattern] = {
            "category": category,
            "language": language,
            "vulnerability_type": "Unvalidated Input",
        }

    def register_sink(self, pattern: str, category: str, language: str):
        """Register a taint sink and pre-calculate its vulnerability type."""
        if language not in self.sinks:
            self.sinks[language] = {}
        if category not in self.sinks[language]:
            self.sinks[language][category] = []
        if pattern not in self.sinks[language][category]:
            self.sinks[language][category].append(pattern)

        vuln_type = self.CATEGORY_TO_VULN_TYPE.get(category, "Data Exposure")

        self.sink_metadata[pattern] = {
            "category": category,
            "language": language,
            "vulnerability_type": vuln_type,
            "risk": self._estimate_risk(category),
        }

    def register_sanitizer(self, pattern: str, language: str = None):
        """Register a sanitizer pattern, optionally language-specific."""
        lang_key = language if language else "global"
        if lang_key not in self.sanitizers:
            self.sanitizers[lang_key] = []
        if pattern not in self.sanitizers[lang_key]:
            self.sanitizers[lang_key].append(pattern)

    def is_sanitizer(self, function_name: str, language: str = None) -> bool:
        """Check if a function is a registered sanitizer."""

        if "global" in self.sanitizers and function_name in self.sanitizers["global"]:
            return True

        return bool(
            language and language in self.sanitizers and function_name in self.sanitizers[language]
        )

    def get_sources_for_language(self, language: str) -> dict[str, list[str]]:
        """Get all source patterns for a specific language."""
        return self.sources.get(language, {})

    def get_sinks_for_language(self, language: str) -> dict[str, list[str]]:
        """Get all sink patterns for a specific language."""
        return self.sinks.get(language, {})

    def get_sink_info(self, pattern: str) -> dict[str, Any]:
        """Get all known metadata for a sink pattern.

        Used by discovery.py and taint_path.py to stop guessing types.
        Returns default metadata if pattern not registered.
        """
        return self.sink_metadata.get(
            pattern,
            {
                "vulnerability_type": "Data Exposure",
                "risk": "medium",
                "category": "unknown",
                "language": "unknown",
            },
        )

    def get_vulnerability_type(self, pattern: str) -> str:
        """Get just the vulnerability type string for a pattern.

        Convenience method for quick lookups.
        """
        return self.get_sink_info(pattern)["vulnerability_type"]

    def get_vulnerability_type_by_category(self, category: str) -> str:
        """Get vulnerability type from category name.

        Used when we have category but not pattern (e.g., in discovery).
        """
        return self.CATEGORY_TO_VULN_TYPE.get(category, "Data Exposure")

    def _estimate_risk(self, category: str) -> str:
        """Internal risk estimator based on category."""
        if category in ("command", "code_injection", "sql", "deserialization"):
            return "critical"
        if category in ("xss", "path", "ssrf", "xxe", "template"):
            return "high"
        if category in ("nosql", "ldap", "orm", "redirect"):
            return "medium"
        return "low"

    def get_stats(self) -> dict[str, int]:
        """Get registry statistics for debugging."""

        total_sources = sum(
            len(patterns)
            for lang_sources in self.sources.values()
            for patterns in lang_sources.values()
        )

        total_sinks = sum(
            len(patterns) for lang_sinks in self.sinks.values() for patterns in lang_sinks.values()
        )

        total_sanitizers = sum(len(patterns) for patterns in self.sanitizers.values())

        return {
            "total_sources": total_sources,
            "total_sinks": total_sinks,
            "total_sanitizers": total_sanitizers,
        }

    def load_from_database(self, cursor: sqlite3.Cursor) -> None:
        """Load patterns from database tables."""
        self._load_taint_patterns(cursor)
        self._load_safe_sinks(cursor)
        self._load_validation_sanitizers(cursor)

    def _load_taint_patterns(self, cursor: sqlite3.Cursor) -> None:
        """Load source/sink patterns from framework_taint_patterns table."""
        query = """
            SELECT f.language, ftp.pattern, ftp.pattern_type, ftp.category
            FROM framework_taint_patterns ftp
            JOIN frameworks f ON ftp.framework_id = f.id
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            lang = row[0] or "global"
            pattern = row[1]
            pattern_type = row[2]
            category = row[3] or "unknown"

            if not pattern:
                continue

            if pattern_type == "source":
                self.register_source(pattern, category, lang)
            elif pattern_type == "sink":
                self.register_sink(pattern, category, lang)

    def _load_safe_sinks(self, cursor: sqlite3.Cursor) -> None:
        """Load safe sink patterns from framework_safe_sinks table."""
        query = """
            SELECT f.language, fss.sink_pattern, fss.sink_type
            FROM framework_safe_sinks fss
            JOIN frameworks f ON fss.framework_id = f.id
            WHERE fss.is_safe = 1
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            lang = row[0] or "global"
            pattern = row[1]
            if pattern:
                self.register_sanitizer(pattern, lang)

    def _load_validation_sanitizers(self, cursor: sqlite3.Cursor) -> None:
        """Load validation patterns from validation_framework_usage table."""
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

            if method:
                self.register_sanitizer(method, "javascript")

            if var_name and method:
                self.register_sanitizer(f"{var_name}.{method}", "javascript")

            if framework and method:
                self.register_sanitizer(f"{framework}.{method}", "javascript")

    def get_source_patterns(self, language: str) -> list[str]:
        """Get flattened list of source patterns for a language."""
        patterns = []
        lang_sources = self.sources.get(language, {})
        for category_patterns in lang_sources.values():
            patterns.extend(category_patterns)
        return patterns

    def get_sink_patterns(self, language: str) -> list[str]:
        """Get flattened list of sink patterns for a language."""
        patterns = []
        lang_sinks = self.sinks.get(language, {})
        for category_patterns in lang_sinks.values():
            patterns.extend(category_patterns)
        return patterns

    def get_sanitizer_patterns(self, language: str) -> list[str]:
        """Get sanitizer patterns for a language (includes global sanitizers)."""
        patterns = []

        if "global" in self.sanitizers:
            patterns.extend(self.sanitizers["global"])

        if language in self.sanitizers:
            patterns.extend(self.sanitizers[language])
        return patterns


def has_sanitizer_between(
    cursor: sqlite3.Cursor, source: dict[str, Any], sink: dict[str, Any]
) -> bool:
    """Check if there's a sanitizer call between source and sink in the same function."""
    if source["file"] != sink["file"]:
        return False

    registry = TaintRegistry()

    query = build_query(
        "symbols",
        ["name", "line"],
        where="path = ? AND type = 'call' AND line > ? AND line < ?",
        order_by="line",
    )
    cursor.execute(query, (source["file"], source["line"], sink["line"]))

    intermediate_calls = cursor.fetchall()

    return any(registry.is_sanitizer(call_name) for call_name, _ in intermediate_calls)


def deduplicate_paths(paths: list[Any]) -> list[Any]:
    """Deduplicate taint paths while preserving the most informative flow for each source-sink pair."""

    def _path_score(path: Any) -> tuple[int, int, int]:
        """Score paths so we keep the most informative version per source/sink pair."""
        steps = path.path or []

        cross_hops = 0
        uses_cfg = bool(getattr(path, "flow_sensitive", False))

        for step in steps:
            step_type = step.get("type")
            if step_type == "cfg_call":
                uses_cfg = True
            if step_type in {"cfg_call", "argument_pass", "return_flow"}:
                from_file = step.get("from_file")
                to_file = step.get("to_file")

                if step_type == "cfg_call":
                    logger.debug(f"cfg_call step: from={from_file} to={to_file}")
                if from_file and to_file and from_file != to_file:
                    cross_hops += 1
                    logger.debug(f"Cross-file hop detected! cross_hops={cross_hops}")

        length = len(steps)

        length_component = length if cross_hops else -length

        if cross_hops > 0:
            logger.debug(
                f"Path score: cross_hops={cross_hops}, uses_cfg={1 if uses_cfg else 0}, length={length_component}"
            )

        return (cross_hops, 1 if uses_cfg else 0, length_component)

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

    sink_groups: dict[tuple[str, int], list[Any]] = {}
    for path, _score in unique_source_sink.values():
        sink = path.sink
        sink_key = (sink.get("file", "unknown_file"), sink.get("line", 0))
        sink_groups.setdefault(sink_key, []).append(path)

    deduped_paths: list[Any] = []
    for _sink_key, sink_paths in sink_groups.items():
        if not sink_paths:
            continue

        scored_paths = [(p, _path_score(p)) for p in sink_paths]
        scored_paths.sort(key=lambda item: item[1], reverse=True)
        best_path, _ = scored_paths[0]

        best_path.related_sources = []

        for other_path, _ in scored_paths[1:]:
            best_path.add_related_path(other_path)

        deduped_paths.append(best_path)

    multi_file_count = sum(1 for p in deduped_paths if p.source.get("file") != p.sink.get("file"))
    logger.debug(f"Returning {len(deduped_paths)} paths ({multi_file_count} multi-file)")

    return deduped_paths


def trace_taint(
    db_path: str,
    max_depth: int = 25,
    registry=None,
    use_memory_cache: bool = True,
    memory_limit_mb: int = 12000,
    cache: MemoryCache | None = None,
    graph_db_path: str = None,
    mode: str = "backward",
) -> dict[str, Any]:
    """Perform taint analysis by tracing data flow from sources to sinks."""
    import sqlite3

    if mode == "forward":
        logger.info("Using forward-only flow resolution mode")

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

        logger.info(f"Flow resolution complete: {total_flows} flows resolved")

        return {
            "success": True,
            "taint_paths": [],
            "vulnerabilities": [],
            "paths": [],
            "sources_found": 0,
            "sinks_found": 0,
            "total_vulnerabilities": 0,
            "total_flows_resolved": total_flows,
            "total_flows": total_flows,
            "vulnerabilities_by_type": {},
            "summary": {
                "total_count": total_flows,
                "by_type": {},
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
            },
        }

    if mode == "complete":
        logger.info("Using complete mode: IFDS (backward) + FlowResolver (forward)")

        logger.info("STEP 1/2: Running FlowResolver (forward analysis)")

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

        logger.info(f"FlowResolver complete: {total_flows} flows resolved")

        if registry is None:
            raise ValueError(
                "Registry is MANDATORY for complete mode (includes IFDS). "
                "Run with orchestrator.collect_rule_patterns(registry) first. "
                "NO FALLBACKS ALLOWED."
            )

        logger.info("STEP 2/2: Running IFDS (backward vulnerability analysis)")

    if registry is None:
        raise ValueError(
            "Registry is MANDATORY for backward taint analysis. "
            "Run with orchestrator.collect_rule_patterns(registry) first. "
            "NO FALLBACKS ALLOWED."
        )

    frameworks = []

    db_path_obj = Path(db_path)
    if db_path_obj.exists():
        try:
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            query = build_query(
                "frameworks", ["name", "version", "language", "path"], order_by="is_primary DESC"
            )
            cursor.execute(query)

            for name, version, language, path in cursor.fetchall():
                frameworks.append(
                    {
                        "framework": name,
                        "version": version or "unknown",
                        "language": language or "unknown",
                        "path": path or ".",
                    }
                )

            conn.close()
        except (sqlite3.Error, ImportError):
            pass

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

    if cache is None:
        from theauditor.indexer.schemas.codegen import SchemaCodeGenerator
        from theauditor.utils.constants import ExitCodes

        current_hash = SchemaCodeGenerator.get_schema_hash()

        cache_file = Path(__file__).parent.parent / "indexer" / "schemas" / "generated_cache.py"
        built_hash = None

        if cache_file.exists():
            with open(cache_file) as f:
                lines = f.readlines()
                if len(lines) >= 2 and "SCHEMA_HASH:" in lines[1]:
                    built_hash = lines[1].split("SCHEMA_HASH:")[1].strip()

        if current_hash != built_hash:
            logger.error(
                "[SCHEMA STALE] Schema files have changed but generated code is out of date!"
            )
            logger.error("[SCHEMA STALE] Regenerating code automatically...")

            try:
                output_dir = Path(__file__).parent.parent / "indexer" / "schemas"
                SchemaCodeGenerator.write_generated_code(output_dir)
                logger.error("[SCHEMA FIX] Generated code updated successfully")
                logger.error("[SCHEMA FIX] Please re-run the command")
                sys.exit(ExitCodes.SCHEMA_STALE)
            except Exception as e:
                logger.error(f"[SCHEMA ERROR] Failed to regenerate code: {e}")
                raise RuntimeError(f"Schema validation failed and auto-fix failed: {e}") from e

        from theauditor.indexer.schemas.generated_cache import SchemaMemoryCache

        logger.info("Creating SchemaMemoryCache (mandatory for discovery)")
        cache = SchemaMemoryCache(db_path)
        logger.info(f"SchemaMemoryCache loaded: {cache.get_memory_usage_mb():.1f}MB")
    else:
        logger.info(f"Using pre-loaded cache: {cache.get_memory_usage_mb():.1f}MB")

    try:
        from .discovery import TaintDiscovery

        logger.info("Using database-driven discovery")
        discovery = TaintDiscovery(cache, registry=registry)

        logger.info("Discovering sanitizers from framework tables")
        sanitizers = discovery.discover_sanitizers()
        for sanitizer in sanitizers:
            lang = sanitizer.get("language", "global")
            pattern = sanitizer.get("pattern", "")
            if pattern:
                registry.register_sanitizer(pattern, lang)
        logger.info(f"Registered {len(sanitizers)} sanitizers from frameworks")

        sources = discovery.discover_sources(merged_sources)
        sinks = discovery.discover_sinks(merged_sinks)
        sinks = discovery.filter_framework_safe_sinks(sinks)

        # Fidelity Checkpoint 1: Discovery
        discovery_manifest = create_discovery_manifest(sources, sinks)
        reconcile_taint_fidelity(
            discovery_manifest,
            {"sinks_to_analyze": len(sinks)},
            stage="discovery",
        )
        logger.info(
            f"Taint Discovery: {len(sources)} sources, {len(sinks)} sinks [Fidelity: OK]"
        )

        def filter_sinks_by_proximity(source, all_sinks):
            """Filter sinks to same module as source for performance."""
            source_file = source.get("file", "")
            if not source_file:
                return []

            source_parts = source_file.replace("\\", "/").split("/")
            source_module = source_parts[0] if source_parts else ""

            if not source_module:
                return []

            filtered = []
            for sink in all_sinks:
                sink_file = sink.get("file", "")
                if not sink_file:
                    continue
                sink_parts = sink_file.replace("\\", "/").split("/")
                sink_module = sink_parts[0] if sink_parts else ""

                if sink_module == source_module:
                    filtered.append(sink)

            return filtered

        if graph_db_path is None:
            db_dir = Path(db_path).parent
            graph_db_path = str(db_dir / "graphs.db")

        if not Path(graph_db_path).exists():
            raise FileNotFoundError(
                f"graphs.db not found at {graph_db_path}. "
                f"Run 'aud graph build' to create it. "
                f"NO FALLBACKS - Taint analysis requires pre-computed graphs."
            )

        logger.info("Using IFDS mode with graphs.db")
        sys.stderr.flush()

        if mode == "complete":
            logger.info("Handshake: Filtering sinks based on FlowResolver results...")

            handshake_conn = sqlite3.connect(db_path)
            handshake_cursor = handshake_conn.cursor()

            handshake_cursor.execute("""
                SELECT DISTINCT sink_file, sink_line
                FROM resolved_flow_audit
                WHERE engine = 'FlowResolver' AND status IN ('VULNERABLE', 'REACHABLE')
            """)

            reachable_targets = set()
            for row in handshake_cursor.fetchall():
                reachable_targets.add((row[0], row[1]))

            handshake_conn.close()

            logger.info(f"FlowResolver identified {len(reachable_targets)} reachable sinks.")

            flow_resolver_hits = reachable_targets
            for sink in sinks:
                sink_key = (sink.get("file"), sink.get("line"))
                if sink_key in flow_resolver_hits:
                    sink["confirmed_by_forward_analysis"] = True

            # Filter sinks to ONLY those confirmed by FlowResolver (Intersection Strategy)
            confirmed_sinks = [s for s in sinks if s.get("confirmed_by_forward_analysis")]
            skipped_count = len(sinks) - len(confirmed_sinks)

            if confirmed_sinks:
                logger.info(
                    f"Hybrid Optimization Active: Pruned {skipped_count} unreachable sinks. "
                    f"IFDS will analyze ONLY {len(confirmed_sinks)} confirmed targets (Intersection Strategy)."
                )
                sinks = confirmed_sinks
            else:
                logger.warning(
                    "FlowResolver found 0 reachable sinks. Skipping IFDS phase to save time."
                )
                sinks = []
            sys.stderr.flush()

        from .ifds_analyzer import IFDSTaintAnalyzer
        from .type_resolver import TypeResolver

        graph_conn = sqlite3.connect(graph_db_path)
        graph_conn.row_factory = sqlite3.Row
        repo_conn = sqlite3.connect(db_path)
        repo_conn.row_factory = sqlite3.Row
        type_resolver = TypeResolver(graph_conn.cursor(), repo_conn.cursor())

        logger.info(f"Analyzing {len(sinks)} sinks against {len(sources)} sources (demand-driven)")
        sys.stderr.flush()

        ifds_analyzer = IFDSTaintAnalyzer(
            repo_db_path=db_path,
            graph_db_path=graph_db_path,
            cache=cache,
            registry=registry,
            type_resolver=type_resolver,
        )

        all_vulnerable_paths = []
        all_sanitized_paths = []

        progress_interval = max(100, min(1000, len(sinks) // 10))
        for idx, sink in enumerate(sinks):
            if idx % progress_interval == 0:
                total_found = len(all_vulnerable_paths) + len(all_sanitized_paths)
                logger.info(
                    f"Progress: {idx}/{len(sinks)} sinks analyzed, {total_found} total paths ({len(all_vulnerable_paths)} vulnerable, {len(all_sanitized_paths)} sanitized)"
                )
                sys.stderr.flush()

            vulnerable, sanitized = ifds_analyzer.analyze_sink_to_sources(sink, sources, max_depth)
            all_vulnerable_paths.extend(vulnerable)
            all_sanitized_paths.extend(sanitized)

        # Fidelity Checkpoint 2: Analysis
        analysis_manifest = create_analysis_manifest(
            all_vulnerable_paths,
            all_sanitized_paths,
            sinks_analyzed=len(sinks),
            sources_checked=len(sources),
        )
        reconcile_taint_fidelity(
            analysis_manifest,
            {"sinks_to_analyze": len(sinks)},
            stage="analysis",
        )

        ifds_analyzer.close()

        graph_conn.close()
        repo_conn.close()
        logger.info(
            f"IFDS found {len(all_vulnerable_paths)} vulnerable paths, {len(all_sanitized_paths)} sanitized paths"
        )

        unique_vulnerable_paths = deduplicate_paths(all_vulnerable_paths)
        unique_sanitized_paths = deduplicate_paths(all_sanitized_paths)

        logger.info(
            f"Dedup: {len(all_vulnerable_paths)} -> {len(unique_vulnerable_paths)} vulnerable, "
            f"{len(all_sanitized_paths)} -> {len(unique_sanitized_paths)} sanitized"
        )

        import json

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM resolved_flow_audit WHERE engine = 'IFDS'")
        cursor.execute("DELETE FROM taint_flows")

        # Fidelity: Create manifest BEFORE writes with tx_id
        paths_to_write = len(unique_vulnerable_paths) + len(unique_sanitized_paths)
        db_manifest = create_db_manifest(paths_to_write)

        total_inserted = 0

        for path in unique_vulnerable_paths:
            cursor.execute(
                """
                INSERT INTO resolved_flow_audit (
                    source_file, source_line, source_pattern,
                    sink_file, sink_line, sink_pattern,
                    vulnerability_type, path_length, hops, path_json, flow_sensitive,
                    status, sanitizer_file, sanitizer_line, sanitizer_method,
                    engine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    path.source.get("file", ""),
                    path.source.get("line", 0),
                    path.source.get("pattern", ""),
                    path.sink.get("file", ""),
                    path.sink.get("line", 0),
                    path.sink.get("pattern", ""),
                    path.vulnerability_type,
                    len(path.path) if path.path else 0,
                    len(path.path) if path.path else 0,
                    json.dumps(path.path) if path.path else "[]",
                    1,
                    "VULNERABLE",
                    None,
                    None,
                    None,
                    "IFDS",
                ),
            )
            total_inserted += 1

        for path in unique_sanitized_paths:
            cursor.execute(
                """
                INSERT INTO resolved_flow_audit (
                    source_file, source_line, source_pattern,
                    sink_file, sink_line, sink_pattern,
                    vulnerability_type, path_length, hops, path_json, flow_sensitive,
                    status, sanitizer_file, sanitizer_line, sanitizer_method,
                    engine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    path.source.get("file", ""),
                    path.source.get("line", 0),
                    path.source.get("pattern", ""),
                    path.sink.get("file", ""),
                    path.sink.get("line", 0),
                    path.sink.get("pattern", ""),
                    path.vulnerability_type,
                    len(path.path) if path.path else 0,
                    len(path.path) if path.path else 0,
                    json.dumps(path.path) if path.path else "[]",
                    1,
                    "SANITIZED",
                    path.sanitizer_file,
                    path.sanitizer_line,
                    path.sanitizer_method,
                    "IFDS",
                ),
            )
            total_inserted += 1

        for path in unique_vulnerable_paths:
            cursor.execute(
                """
                INSERT INTO taint_flows (
                    source_file, source_line, source_pattern,
                    sink_file, sink_line, sink_pattern,
                    vulnerability_type, path_length, hops, path_json, flow_sensitive
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    path.source.get("file", ""),
                    path.source.get("line", 0),
                    path.source.get("pattern", ""),
                    path.sink.get("file", ""),
                    path.sink.get("line", 0),
                    path.sink.get("pattern", ""),
                    path.vulnerability_type,
                    len(path.path) if path.path else 0,
                    len(path.path) if path.path else 0,
                    json.dumps(path.path) if path.path else "[]",
                    1,
                ),
            )

        conn.commit()

        # Fidelity Checkpoint 3: DB Output (tx_id verification)
        db_receipt = create_db_receipt(
            rows_inserted=total_inserted,
            tx_id=db_manifest["tx_id"],
        )
        reconcile_taint_fidelity(db_manifest, db_receipt, stage="db_output")

        conn.close()
        logger.info(
            f"Persisted {total_inserted} flows to resolved_flow_audit ({len(unique_vulnerable_paths)} vulnerable, {len(unique_sanitized_paths)} sanitized) [Fidelity: OK]"
        )
        logger.info(
            f"Persisted {len(unique_vulnerable_paths)} vulnerable flows to taint_flows (backward compatibility)"
        )

        unique_paths = unique_vulnerable_paths

        vulnerabilities_by_type = defaultdict(int)
        for path in unique_paths:
            vulnerabilities_by_type[path.vulnerability_type] += 1

        path_dicts = [p.to_dict() for p in unique_paths]

        multi_file_in_dicts = sum(1 for p in path_dicts if p["source"]["file"] != p["sink"]["file"])
        logger.debug(f"Serialized {len(path_dicts)} paths ({multi_file_in_dicts} multi-file)")

        summary = {
            "total_count": len(unique_paths),
            "by_type": dict(vulnerabilities_by_type),
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
        }

        result = {
            "success": True,
            "taint_paths": path_dicts,
            "vulnerabilities": path_dicts,
            "paths": path_dicts,
            "sources_found": len(sources),
            "sinks_found": len(sinks),
            "total_vulnerabilities": len(unique_paths),
            "total_flows": len(unique_paths),
            "vulnerabilities_by_type": dict(vulnerabilities_by_type),
            "summary": summary,
        }

        if mode == "complete":
            conn_temp = sqlite3.connect(db_path)
            cursor_temp = conn_temp.cursor()

            cursor_temp.execute(
                "SELECT COUNT(*) FROM resolved_flow_audit WHERE status = 'VULNERABLE'"
            )
            total_vulnerable = cursor_temp.fetchone()[0]

            cursor_temp.execute(
                "SELECT COUNT(*) FROM resolved_flow_audit WHERE status = 'REACHABLE'"
            )
            total_reachable = cursor_temp.fetchone()[0]

            cursor_temp.execute(
                "SELECT COUNT(*) FROM resolved_flow_audit WHERE status = 'SANITIZED'"
            )
            total_sanitized = cursor_temp.fetchone()[0]

            cursor_temp.execute(
                "SELECT engine, status, COUNT(*) FROM resolved_flow_audit GROUP BY engine, status"
            )
            breakdown = {f"{row[0]}:{row[1]}": row[2] for row in cursor_temp.fetchall()}
            conn_temp.close()

            result["total_vulnerable"] = total_vulnerable
            result["total_reachable"] = total_reachable
            result["total_sanitized"] = total_sanitized
            result["total_flows_resolved"] = total_flows
            result["mode"] = "complete"
            result["engines_used"] = ["IFDS (backward)", "FlowResolver (forward)"]
            result["engine_breakdown"] = breakdown

            logger.info("COMPLETE MODE RESULTS:")
            logger.info(f"IFDS found: {len(unique_paths)} confirmed vulnerable paths")
            logger.info(f"FlowResolver resolved: {total_flows} total flows")
            logger.info(
                f"Final: {total_vulnerable} Confirmed, {total_reachable} Reachable, {total_sanitized} Sanitized"
            )

        return result

    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            return {
                "success": False,
                "error": "Database is corrupted or incomplete. Run 'aud full --index' to rebuild the repository index.",
                "taint_paths": [],
                "vulnerabilities": [],
                "paths": [],
                "sources_found": 0,
                "sinks_found": 0,
                "total_vulnerabilities": 0,
                "total_flows": 0,
                "vulnerabilities_by_type": {},
                "summary": {
                    "total_count": 0,
                    "by_type": {},
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0,
                },
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
                "summary": {
                    "total_count": 0,
                    "by_type": {},
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0,
                },
            }
    except Exception as e:
        import traceback

        error_msg = f"[TAINT ERROR] {str(e)}"
        traceback_str = traceback.format_exc()
        logger.error(error_msg)
        logger.error(traceback_str)

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
            "summary": {
                "total_count": 0,
                "by_type": {},
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
            },
        }
    finally:
        conn.close()


VULN_TYPE_TO_SEVERITY: dict[str, str] = {
    "SQL Injection": "critical",
    "Command Injection": "critical",
    "Code Injection": "critical",
    "Insecure Deserialization": "critical",
    "Cross-Site Scripting (XSS)": "high",
    "Path Traversal": "high",
    "Server-Side Request Forgery (SSRF)": "high",
    "XML External Entity (XXE)": "high",
    "Template Injection": "high",
    "NoSQL Injection": "medium",
    "LDAP Injection": "medium",
    "ORM Injection": "medium",
    "Open Redirect": "medium",
    "Prototype Pollution": "medium",
    "Unvalidated Input": "medium",
    "Log Injection": "low",
    "Weak Cryptography": "low",
    "Data Exposure": "low",
}


def normalize_taint_path(path: dict[str, Any]) -> dict[str, Any]:
    """Normalize a taint path dictionary to ensure all required keys exist."""

    src_file_before = path.get("source", {}).get("file", "MISSING")
    sink_file_before = path.get("sink", {}).get("file", "MISSING")

    path.setdefault("path_length", 0)
    path.setdefault("path", [])

    vuln_type = path.get("vulnerability_type", "Data Exposure")
    path.setdefault("severity", VULN_TYPE_TO_SEVERITY.get(vuln_type, "medium"))

    if "source" not in path:
        path["source"] = {}
    path["source"].setdefault("name", "unknown_source")
    path["source"].setdefault("file", "unknown_file")
    path["source"].setdefault("line", 0)
    path["source"].setdefault("pattern", "unknown_pattern")

    if "sink" not in path:
        path["sink"] = {}
    path["sink"].setdefault("name", "unknown_sink")
    path["sink"].setdefault("file", "unknown_file")
    path["sink"].setdefault("line", 0)
    path["sink"].setdefault("pattern", "unknown_pattern")

    src_file_after = path["source"]["file"]
    sink_file_after = path["sink"]["file"]
    if src_file_before != src_file_after or sink_file_before != sink_file_after:
        logger.debug(
            f"Changed: {src_file_before} -> {src_file_after}, {sink_file_before} -> {sink_file_after}"
        )

    return path
