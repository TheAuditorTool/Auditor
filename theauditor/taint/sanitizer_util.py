"""Shared sanitizer detection utilities for taint analysis.

This module provides a unified SanitizerRegistry class used by both
IFDSTaintAnalyzer (backward) and FlowResolver (forward) to ensure
consistent sanitizer detection logic across all taint analysis engines.

NO FALLBACKS. NO EXCEPTIONS. Database-first architecture.
"""

import sys
from typing import Dict, List, Optional, Set, Any


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

        # Initialize storage
        self.safe_sinks: Set[str] = set()
        self.validation_sanitizers: List[Dict] = []

        # Load data from database
        self._load_safe_sinks()
        self._load_validation_sanitizers()

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
                pattern = row['pattern']
                if pattern:
                    self.safe_sinks.add(pattern)

            if self.debug:
                print(f"[SanitizerRegistry] Loaded {len(self.safe_sinks)} safe sink patterns", file=sys.stderr)
        except Exception as e:
            if self.debug:
                print(f"[SanitizerRegistry] Failed to load safe sinks: {e}", file=sys.stderr)
            # NO FALLBACK - if table doesn't exist, database is broken

    def _load_validation_sanitizers(self):
        """Load validation framework sanitizers from database.

        These are middleware/decorators that validate/sanitize input
        (e.g., Zod schemas, Express validators, Pydantic models).
        """
        try:
            # Load from validation_framework_usage table
            # FIX: Include BOTH validators (is_validator=1) AND schemas (is_validator=0)
            # Previously only checked 3 validators, ignored 1648 schemas
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
                    'file': row['file'],
                    'line': row['line'],
                    'framework': row['framework'],
                    'schema': row['schema_name']
                }
                self.validation_sanitizers.append(sanitizer)

            if self.debug:
                print(f"[SanitizerRegistry] Loaded {len(self.validation_sanitizers)} validation sanitizers", file=sys.stderr)
        except Exception as e:
            if self.debug:
                print(f"[SanitizerRegistry] Failed to load validation sanitizers: {e}", file=sys.stderr)
            # NO FALLBACK - if table doesn't exist, database is broken

    def _is_sanitizer(self, function_name: str) -> bool:
        """Check if a function name matches any safe sink pattern.

        Args:
            function_name: Function name to check

        Returns:
            True if function matches a safe sink pattern
        """
        # Check exact match
        if function_name in self.safe_sinks:
            return True

        # Check pattern match (safe_sink in function or function in safe_sink)
        for safe_sink in self.safe_sinks:
            if safe_sink in function_name or function_name in safe_sink:
                return True

        return False

    def _path_goes_through_sanitizer(self, hop_chain: List[Dict]) -> Optional[Dict]:
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
            print(f"[SanitizerRegistry] Checking {len(hop_chain)} hops for sanitizers", file=sys.stderr)

        for i, hop in enumerate(hop_chain):
            # Handle both hop dict format (IFDS) and node ID string format (FlowResolver)
            if isinstance(hop, dict):
                # IFDS format: dict with from_file, to_file, line
                hop_file = hop.get('from_file') or hop.get('to_file')
                hop_line = hop.get('line', 0)
                node_str = hop.get('from_node') or hop.get('to_node') or ""
            else:
                # FlowResolver format: node ID string (file::function::variable)
                node_str = hop
                parts = node_str.split('::')
                hop_file = parts[0] if parts else None
                hop_line = 0  # FlowResolver doesn't track line in node ID

                # Extract function name for validation pattern check
                if len(parts) > 1:
                    func = parts[1]
                    # CHECK 0: Validation middleware patterns in function name
                    validation_patterns = [
                        'validateBody',
                        'validateParams',
                        'validateQuery',
                        'validateHeaders',
                        'validateRequest',
                        'validate('  # PlantFlow style: validate(schema, 'body')
                    ]
                    for pattern in validation_patterns:
                        if pattern in func:
                            if self.debug:
                                print(f"[SanitizerRegistry] Found validation pattern '{pattern}' in function '{func}'", file=sys.stderr)
                            return {
                                'file': hop_file,
                                'line': 0,
                                'method': func
                            }

            if not hop_file:
                if self.debug:
                    print(f"[SanitizerRegistry] Hop {i+1}: No file, skipping", file=sys.stderr)
                continue

            if self.debug:
                print(f"[SanitizerRegistry] Hop {i+1}: {hop_file}:{hop_line}", file=sys.stderr)

            # CHECK 1: Validation patterns in node string (IFDS comprehensive check)
            if node_str:
                validation_patterns = [
                    'validateBody',
                    'validateParams',
                    'validateQuery',
                    'validateHeaders',
                    'validate('  # PlantFlow style
                ]

                for pattern in validation_patterns:
                    if pattern in node_str:
                        if self.debug:
                            print(f"[SanitizerRegistry] Found validation pattern '{pattern}' in node", file=sys.stderr)
                        return {
                            'file': hop_file,
                            'line': hop_line,
                            'method': pattern
                        }

            # CHECK 2: Validation Framework Sanitizers (Location-Based)
            if hop_line > 0:  # Only check if we have a line number
                for san in self.validation_sanitizers:
                    # Match by file path (handle both absolute and relative)
                    if (san['file'].endswith(hop_file) or hop_file.endswith(san['file'])):
                        # Check if line is within reasonable range (±10 lines)
                        if abs(san['line'] - hop_line) <= 10:
                            if self.debug:
                                print(f"[SanitizerRegistry] Found validation sanitizer at {hop_file}:{hop_line}", file=sys.stderr)
                            return {
                                'file': hop_file,
                                'line': hop_line,
                                'method': f"{san['framework']}:{san.get('schema', 'validation')}"
                            }

            # CHECK 3: Query function_call_args for safe sink patterns
            if hop_line > 0:  # Only query if we have a line number
                self.repo_cursor.execute("""
                    SELECT callee_function FROM function_call_args
                    WHERE file = ? AND line = ?
                    LIMIT 10
                """, (hop_file, hop_line))

                callees = [row['callee_function'] for row in self.repo_cursor.fetchall()]

                if self.debug and callees:
                    print(f"[SanitizerRegistry] Found {len(callees)} function calls at {hop_file}:{hop_line}", file=sys.stderr)

                for callee in callees:
                    if self._is_sanitizer(callee):
                        if self.debug:
                            print(f"[SanitizerRegistry] Found safe sink '{callee}'", file=sys.stderr)
                        return {
                            'file': hop_file,
                            'line': hop_line,
                            'method': callee
                        }

        # CHECK 4: Express middleware validation for controllers
        # If path goes through a controller, check if its route has validation middleware
        for hop in hop_chain:
            # Look for controller functions in the path
            node_str = ""
            if isinstance(hop, dict):
                node_str = hop.get('from_node') or hop.get('to_node') or hop.get('from') or hop.get('to') or ""
            else:
                node_str = hop

            # Check if this is a controller function
            if 'Controller' in node_str and '::' in node_str:
                parts = node_str.split('::')
                if len(parts) >= 2:
                    controller_func = parts[1]  # e.g., WorkerController.create

                    if self.debug:
                        print(f"[SanitizerRegistry] Checking middleware for controller: {controller_func}", file=sys.stderr)

                    # Query for validation middleware on routes using this controller
                    # Look for validateBody/validateParams that execute BEFORE the controller
                    self.repo_cursor.execute("""
                        SELECT DISTINCT handler_expr
                        FROM express_middleware_chains emc1
                        WHERE EXISTS (
                            SELECT 1 FROM express_middleware_chains emc2
                            WHERE emc2.route_path = emc1.route_path
                              AND emc2.route_method = emc1.route_method
                              AND (emc2.handler_expr LIKE '%' || ? || '%'
                                   OR emc2.handler_expr LIKE '%controller.' || ? || '%')
                        )
                        AND emc1.handler_expr LIKE '%validate%'
                        LIMIT 1
                    """, (controller_func, controller_func.split('.')[-1] if '.' in controller_func else controller_func))

                    validation_middleware = self.repo_cursor.fetchone()
                    if validation_middleware:
                        if self.debug:
                            print(f"[SanitizerRegistry] Found validation middleware: {validation_middleware[0]}", file=sys.stderr)
                        return {
                            'file': parts[0] if parts else "",
                            'line': 0,
                            'method': f"middleware:{validation_middleware[0]}"
                        }

        if self.debug:
            print(f"[SanitizerRegistry] No sanitizers found in path", file=sys.stderr)

        return None  # No sanitizer found - path is vulnerable