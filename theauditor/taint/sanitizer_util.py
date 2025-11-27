"""Shared sanitizer detection utilities for taint analysis.

This module provides a unified SanitizerRegistry class used by both
IFDSTaintAnalyzer (backward) and FlowResolver (forward) to ensure
consistent sanitizer detection logic across all taint analysis engines.

NO FALLBACKS. NO EXCEPTIONS. Database-first architecture.
"""

import sys


class SanitizerRegistry:
    """Registry for sanitizer patterns and validation frameworks.

    Provides unified sanitizer detection logic for all taint engines.
    Loads safe sinks and validation sanitizers from database once.
    """

    def __init__(self, repo_cursor, registry=None, debug=False):
        """Initialize sanitizer registry with database cursor.

        Args:
            repo_cursor: Database cursor to repo_index.db
            registry: Optional registry object for additional context
            debug: Enable debug output
        """
        self.repo_cursor = repo_cursor
        self.registry = registry
        self.debug = debug

        self.safe_sinks: set[str] = set()
        self.validation_sanitizers: list[dict] = []

        self.call_args_cache: dict[tuple, list[str]] = {}

        self._load_safe_sinks()
        self._load_validation_sanitizers()
        self._preload_call_args()

    def _load_safe_sinks(self):
        """Load safe sink patterns from framework_safe_sinks table.

        These are function name patterns that are known to sanitize data
        (e.g., escape functions, parameterized query builders).
        """
        try:
            self.repo_cursor.execute("""
                SELECT DISTINCT pattern
                FROM framework_safe_sinks
            """)

            for row in self.repo_cursor.fetchall():
                pattern = row["pattern"]
                if pattern:
                    self.safe_sinks.add(pattern)

            if self.debug:
                print(
                    f"[SanitizerRegistry] Loaded {len(self.safe_sinks)} safe sink patterns",
                    file=sys.stderr,
                )
        except Exception as e:
            if self.debug:
                print(f"[SanitizerRegistry] Failed to load safe sinks: {e}", file=sys.stderr)

    def _load_validation_sanitizers(self):
        """Load validation framework sanitizers from database.

        These are middleware/decorators that validate/sanitize input
        (e.g., Zod schemas, Express validators, Pydantic models).
        """
        try:
            self.repo_cursor.execute("""
                SELECT DISTINCT
                    file_path as file,
                    line,
                    framework,
                    is_validator,
                    variable_name as schema_name
                FROM validation_framework_usage
                WHERE framework IN ('zod', 'joi', 'yup', 'express-validator')
            """)

            for row in self.repo_cursor.fetchall():
                sanitizer = {
                    "file": row["file"],
                    "line": row["line"],
                    "framework": row["framework"],
                    "schema": row["schema_name"],
                }
                self.validation_sanitizers.append(sanitizer)

            if self.debug:
                print(
                    f"[SanitizerRegistry] Loaded {len(self.validation_sanitizers)} validation sanitizers",
                    file=sys.stderr,
                )
        except Exception as e:
            if self.debug:
                print(
                    f"[SanitizerRegistry] Failed to load validation sanitizers: {e}",
                    file=sys.stderr,
                )

    def _preload_call_args(self):
        """Pre-load function_call_args into memory to eliminate DB queries in hot loop.

        ARCHITECTURAL FIX: Converts O(paths × hops) SQL queries to O(1) hash lookups.
        For 10k paths × 8 hops = 80k queries eliminated.
        """
        try:
            self.repo_cursor.execute("""
                SELECT file, line, callee_function
                FROM function_call_args
                WHERE callee_function IS NOT NULL
            """)

            for row in self.repo_cursor.fetchall():
                key = (row["file"], row["line"])
                if key not in self.call_args_cache:
                    self.call_args_cache[key] = []
                self.call_args_cache[key].append(row["callee_function"])

            if self.debug:
                print(
                    f"[SanitizerRegistry] Pre-loaded {len(self.call_args_cache)} file:line locations with {sum(len(v) for v in self.call_args_cache.values())} function calls",
                    file=sys.stderr,
                )
        except Exception as e:
            if self.debug:
                print(f"[SanitizerRegistry] Failed to preload call args: {e}", file=sys.stderr)

    def _is_sanitizer(self, function_name: str) -> bool:
        """Check if a function name matches any safe sink pattern.

        Args:
            function_name: Function name to check

        Returns:
            True if function matches a safe sink pattern
        """

        if function_name in self.safe_sinks:
            return True

        for safe_sink in self.safe_sinks:
            if safe_sink in function_name or function_name in safe_sink:
                return True

        return False

    def _path_goes_through_sanitizer(self, hop_chain: list[dict]) -> dict | None:
        """Check if a taint path goes through any sanitizer.

        This is the UNIFIED sanitizer detection logic used by both engines.
        Combines the most comprehensive checks from both implementations.

        Checks THREE types of sanitizers:
        1. Validation patterns in node names (validateBody, validateParams, etc.)
        2. Validation framework sanitizers (location-based: file:line match)
        3. Safe sink patterns (name-based: function name pattern match)

        Args:
            hop_chain: List of hops/nodes in the taint path

        Returns:
            Dict with sanitizer metadata if path is sanitized, None if vulnerable
            Format: {'file': str, 'line': int, 'method': str}
        """
        if self.debug:
            print(
                f"[SanitizerRegistry] Checking {len(hop_chain)} hops for sanitizers",
                file=sys.stderr,
            )

        for i, hop in enumerate(hop_chain):
            if isinstance(hop, dict):
                hop_file = hop.get("from_file") or hop.get("to_file")
                hop_line = hop.get("line", 0)
                node_str = (
                    hop.get("from")
                    or hop.get("to")
                    or hop.get("from_node")
                    or hop.get("to_node")
                    or ""
                )
            else:
                node_str = hop
                parts = node_str.split("::")
                hop_file = parts[0] if parts else None
                hop_line = 0

                if len(parts) > 1:
                    func = parts[1]

                    validation_patterns = [
                        "validateBody",
                        "validateParams",
                        "validateQuery",
                        "validateHeaders",
                        "validateRequest",
                        "validate",
                        "sanitize",
                        "parse",
                        "safeParse",
                        "authenticate",
                        "requireAuth",
                        "requireAdmin",
                    ]
                    for pattern in validation_patterns:
                        if pattern in func:
                            if self.debug:
                                print(
                                    f"[SanitizerRegistry] Found validation pattern '{pattern}' in function '{func}'",
                                    file=sys.stderr,
                                )
                            return {"file": hop_file, "line": 0, "method": func}

            if not hop_file:
                if self.debug:
                    print(f"[SanitizerRegistry] Hop {i + 1}: No file, skipping", file=sys.stderr)
                continue

            if self.debug:
                print(f"[SanitizerRegistry] Hop {i + 1}: {hop_file}:{hop_line}", file=sys.stderr)

            if node_str:
                validation_patterns = [
                    "validateBody",
                    "validateParams",
                    "validateQuery",
                    "validateHeaders",
                    "validateRequest",
                    "validate",
                    "sanitize",
                    "parse",
                    "safeParse",
                    "authenticate",
                    "requireAuth",
                    "requireAdmin",
                ]

                for pattern in validation_patterns:
                    if pattern in node_str:
                        if self.debug:
                            print(
                                f"[SanitizerRegistry] Found validation pattern '{pattern}' in node",
                                file=sys.stderr,
                            )
                        return {"file": hop_file, "line": hop_line, "method": pattern}

            if hop_line > 0:
                for san in self.validation_sanitizers:
                    if san["file"].endswith(hop_file) or hop_file.endswith(san["file"]):
                        if abs(san["line"] - hop_line) <= 10:
                            if self.debug:
                                print(
                                    f"[SanitizerRegistry] Found validation sanitizer at {hop_file}:{hop_line}",
                                    file=sys.stderr,
                                )
                            return {
                                "file": hop_file,
                                "line": hop_line,
                                "method": f"{san['framework']}:{san.get('schema', 'validation')}",
                            }

            if hop_line > 0:
                callees = self.call_args_cache.get((hop_file, hop_line), [])

                if self.debug and callees:
                    print(
                        f"[SanitizerRegistry] Found {len(callees)} function calls at {hop_file}:{hop_line}",
                        file=sys.stderr,
                    )

                for callee in callees:
                    if self._is_sanitizer(callee):
                        if self.debug:
                            print(
                                f"[SanitizerRegistry] Found safe sink '{callee}'", file=sys.stderr
                            )
                        return {"file": hop_file, "line": hop_line, "method": callee}

        if self.debug:
            print(f"[SanitizerRegistry] No sanitizers found in path", file=sys.stderr)

        return None
