"""Shared sanitizer detection utilities for taint analysis."""

import sys


class SanitizerRegistry:
    """Registry for sanitizer patterns and validation frameworks."""

    def __init__(self, repo_cursor, registry=None, debug=False):
        """Initialize sanitizer registry with database cursor."""
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
        """Load safe sink patterns from framework_safe_sinks table."""
        try:
            self.repo_cursor.execute("""
                SELECT DISTINCT sink_pattern
                FROM framework_safe_sinks
                WHERE is_safe = 1
            """)

            for row in self.repo_cursor.fetchall():
                pattern = row["sink_pattern"]
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
        """Load validation framework sanitizers from database."""
        try:
            self.repo_cursor.execute("""
                SELECT DISTINCT
                    file_path as file,
                    line,
                    framework,
                    is_validator,
                    variable_name as schema_name
                FROM validation_framework_usage
                WHERE framework IN ('zod', 'joi', 'yup', 'express-validator', 'validator')
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
        """Pre-load function_call_args into memory to eliminate DB queries in hot loop."""
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
        """Check if a function name matches any safe sink pattern."""

        if function_name in self.safe_sinks:
            return True

        for safe_sink in self.safe_sinks:
            if safe_sink in function_name or function_name in safe_sink:
                return True

        return False

    def _get_language_for_file(self, file_path: str) -> str:
        """Detect language from file extension."""
        if not file_path:
            return "unknown"

        lower = file_path.lower()
        if lower.endswith(".py"):
            return "python"
        elif lower.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")):
            return "javascript"
        elif lower.endswith(".go"):
            return "go"
        elif lower.endswith(".rs"):
            return "rust"
        return "unknown"

    def _get_validation_patterns(self, file_path: str) -> list[str]:
        """Get validation/sanitizer patterns for a file's language."""
        lang = self._get_language_for_file(file_path)

        if not self.registry:
            raise ValueError(
                "TaintRegistry is MANDATORY for SanitizerRegistry._get_validation_patterns(). "
                "NO FALLBACKS. Initialize SanitizerRegistry with registry parameter."
            )

        return self.registry.get_sanitizer_patterns(lang)

    def _path_goes_through_sanitizer(self, hop_chain: list[dict]) -> dict | None:
        """Check if a taint path goes through any sanitizer."""
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

                    validation_patterns = self._get_validation_patterns(hop_file)
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
                validation_patterns = self._get_validation_patterns(hop_file)
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
                    if (san["file"].endswith(hop_file) or hop_file.endswith(san["file"])) and abs(
                        san["line"] - hop_line
                    ) <= 10:
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
            print("[SanitizerRegistry] No sanitizers found in path", file=sys.stderr)

        return None
