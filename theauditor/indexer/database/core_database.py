"""Core database operations for language-agnostic patterns.

This module contains add_* methods for CORE_TABLES defined in schemas/core_schema.py.
Handles 21 core tables including files, symbols, assignments, function calls, CFG, and JSX variants.
"""

from typing import List, Optional


class CoreDatabaseMixin:
    """Mixin providing add_* methods for CORE_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    # ========================================================
    # BASIC DATA FLOW BATCH METHODS
    # ========================================================

    def add_file(self, path: str, sha256: str, ext: str, bytes_size: int, loc: int):
        """Add a file record to the batch.

        Deduplicates paths to prevent UNIQUE constraint violations.
        This can happen with symlinks, junction points, or case sensitivity issues.
        """
        # Check if path already in current batch (O(n) but batches are small)
        batch = self.generic_batches['files']
        if not any(item[0] == path for item in batch):
            batch.append((path, sha256, ext, bytes_size, loc))

    def add_ref(self, src: str, kind: str, value: str, line: Optional[int] = None):
        """Add a reference record to the batch."""
        self.generic_batches['refs'].append((src, kind, value, line))

    def add_symbol(self, path: str, name: str, symbol_type: str, line: int, col: int, end_line: Optional[int] = None,
                   type_annotation: Optional[str] = None, parameters: Optional[str] = None):
        """Add a symbol record to the batch.

        Args:
            path: File path containing the symbol
            name: Symbol name
            symbol_type: Type of symbol ('function', 'class', 'variable', etc.)
            line: Line number where symbol is defined
            col: Column number where symbol is defined
            end_line: Last line of symbol definition (optional)
            type_annotation: TypeScript/type annotation (optional)
            parameters: JSON array of parameter names for functions (optional, e.g., '["data", "_createdBy"]')
        """
        import os
        if os.getenv("THEAUDITOR_DEBUG"):
            # Check if this exact symbol already exists in batch
            symbol_key = (path, name, symbol_type, line, col)
            existing = [s for s in self.generic_batches['symbols'] if (s[0], s[1], s[2], s[3], s[4]) == symbol_key]
            if existing:
                print(f"[DEBUG] add_symbol: DUPLICATE detected! {name} ({symbol_type}) at {path}:{line}:{col}")
            if parameters and os.getenv("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] add_symbol: {name} ({symbol_type}) has parameters: {parameters}")
        self.generic_batches['symbols'].append((path, name, symbol_type, line, col, end_line, type_annotation, parameters))

    def add_assignment(self, file_path: str, line: int, target_var: str, source_expr: str,
                      source_vars: List[str], in_function: str, property_path: Optional[str] = None):
        """Add a variable assignment record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch assignment record (without source_vars column)
        - Phase 2: Batch junction records for each source variable

        Args:
            property_path: Full property path for destructured assignments (e.g., 'req.params.id')
                          NULL for non-destructured assignments (e.g., 'const x = y')

        NO FALLBACKS. If source_vars is malformed, hard fail.
        """
        # DEBUG: Track batch index for duplicate investigation
        import os
        if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
            batch_idx = len(self.generic_batches['assignments'])
            import sys
            print(f"[TRACE] add_assignment() call #{batch_idx}: {file_path}:{line} {target_var} in {in_function}", file=sys.stderr)

        # Phase 1: Add assignment record (6 params including property_path)
        self.generic_batches['assignments'].append((file_path, line, target_var, source_expr, in_function, property_path))

        # Phase 2: Add junction records for each source variable
        if source_vars:
            for source_var in source_vars:
                if not source_var:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['assignment_sources'].append((file_path, line, target_var, source_var))

    def add_function_call_arg(self, file_path: str, line: int, caller_function: str,
                              callee_function: str, arg_index: int, arg_expr: str, param_name: str,
                              callee_file_path: Optional[str] = None):
        """Add a function call argument record to the batch.

        Args:
            file_path: File containing the function call
            line: Line number of the call
            caller_function: Name of the calling function
            callee_function: Name of the called function
            arg_index: Index of the argument (0-based)
            arg_expr: Expression passed as argument
            param_name: Parameter name in callee signature
            callee_file_path: Resolved file path where callee is defined (for cross-file tracking)
        """
        self.generic_batches['function_call_args'].append((file_path, line, caller_function, callee_function,
                                                           arg_index, arg_expr, param_name, callee_file_path))

    def add_function_return(self, file_path: str, line: int, function_name: str,
                           return_expr: str, return_vars: List[str]):
        """Add a function return statement record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch function return record (without return_vars column)
        - Phase 2: Batch junction records for each return variable

        NO FALLBACKS. If return_vars is malformed, hard fail.
        """
        # Phase 1: Add function return record (4 params, no return_vars column)
        self.generic_batches['function_returns'].append((file_path, line, function_name, return_expr))

        # Phase 2: Add junction records for each return variable
        if return_vars:
            for return_var in return_vars:
                if not return_var:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['function_return_sources'].append((file_path, line, function_name, return_var))

    def add_config_file(self, path: str, content: str, file_type: str, context: Optional[str] = None):
        """Add a configuration file content to the batch."""
        self.generic_batches['config_files'].append((path, content, file_type, context))

    # ========================================================
    # CONTROL FLOW GRAPH (CFG) BATCH METHODS
    # ========================================================

    def add_cfg_block(self, file_path: str, function_name: str, block_type: str,
                     start_line: int, end_line: int, condition_expr: Optional[str] = None) -> int:
        """Add a CFG block to the batch and return its temporary ID.

        SPECIAL CASE: CFG blocks use AUTOINCREMENT, so real IDs are unknown until INSERT.
        This method returns a temporary negative ID that will be mapped to real ID during flush.

        Note: Since we use AUTOINCREMENT, we need to handle IDs carefully.
        This returns a temporary ID that will be replaced during flush.
        """
        # Generate temporary ID (negative to distinguish from real IDs)
        batch = self.generic_batches['cfg_blocks']
        temp_id = -(len(batch) + 1)
        batch.append((file_path, function_name, block_type,
                     start_line, end_line, condition_expr, temp_id))
        return temp_id

    def add_cfg_edge(self, file_path: str, function_name: str, source_block_id: int,
                    target_block_id: int, edge_type: str):
        """Add a CFG edge to the batch."""
        self.generic_batches['cfg_edges'].append((file_path, function_name, source_block_id,
                                                  target_block_id, edge_type))

    def add_cfg_statement(self, block_id: int, statement_type: str, line: int,
                         statement_text: Optional[str] = None):
        """Add a CFG block statement to the batch."""
        self.generic_batches['cfg_block_statements'].append((block_id, statement_type, line, statement_text))

    # JSX Preserved Mode CFG Methods
    def add_cfg_block_jsx(self, file_path: str, function_name: str, block_type: str,
                         start_line: int, end_line: int, condition_expr: Optional[str] = None,
                         jsx_mode: str = 'preserved', extraction_pass: int = 2) -> int:
        """Add a CFG block to the JSX batch and return its temporary ID."""
        batch = self.generic_batches['cfg_blocks_jsx']
        temp_id = -(len(batch) + 1)
        batch.append((file_path, function_name, block_type,
                     start_line, end_line, condition_expr, jsx_mode, extraction_pass, temp_id))
        return temp_id

    def add_cfg_edge_jsx(self, file_path: str, function_name: str, source_block_id: int,
                        target_block_id: int, edge_type: str,
                        jsx_mode: str = 'preserved', extraction_pass: int = 2):
        """Add a CFG edge to the JSX batch."""
        self.generic_batches['cfg_edges_jsx'].append((file_path, function_name, source_block_id,
                                                      target_block_id, edge_type, jsx_mode, extraction_pass))

    def add_cfg_statement_jsx(self, block_id: int, statement_type: str, line: int,
                             statement_text: Optional[str] = None,
                             jsx_mode: str = 'preserved', extraction_pass: int = 2):
        """Add a CFG block statement to the JSX batch."""
        self.generic_batches['cfg_block_statements_jsx'].append((block_id, statement_type, line, statement_text, jsx_mode, extraction_pass))

    # ========================================================
    # VARIABLE TRACKING BATCH METHODS
    # ========================================================

    def add_variable_usage(self, file_path: str, line: int, variable_name: str,
                          usage_type: str, in_component: Optional[str] = None,
                          in_hook: Optional[str] = None, scope_level: int = 0):
        """Add a variable usage record to the batch."""
        self.generic_batches['variable_usage'].append((file_path, line, variable_name, usage_type,
                                                       in_component or '', in_hook or '', scope_level))

    def add_object_literal(self, file_path: str, line: int, variable_name: str,
                          property_name: str, property_value: str,
                          property_type: str, nested_level: int = 0,
                          in_function: str = ''):
        """Add object literal property-function mapping to batch.

        Args:
            file_path: Path to the file containing the object literal
            line: Line number where the object literal appears
            variable_name: Name of the variable holding the object (e.g., 'handlers')
            property_name: Key in the object literal (e.g., 'create')
            property_value: Value expression (e.g., 'handleCreate' or '{nested}')
            property_type: Type of value - one of:
                - 'function_ref': Reference to a function (e.g., handleCreate)
                - 'literal': Primitive literal value (string, number, boolean)
                - 'expression': Complex expression
                - 'object': Nested object literal
                - 'method_definition': ES6 method syntax (method() {})
                - 'shorthand': Shorthand property ({ handleClick })
                - 'arrow_function': Inline arrow function
                - 'function_expression': Inline function expression
            nested_level: Depth of nesting (0 = top level, 1 = first nested, etc.)
            in_function: Name of containing function ('' for module scope)
        """
        self.generic_batches['object_literals'].append((
            file_path, line, variable_name, property_name,
            property_value, property_type, nested_level, in_function
        ))

    # ========================================================
    # JSX-SPECIFIC BATCH METHODS FOR DUAL-PASS EXTRACTION
    # ========================================================

    def add_function_return_jsx(self, file_path: str, line: int, function_name: str,
                                return_expr: str, return_vars: List[str], has_jsx: bool = False,
                                returns_component: bool = False, cleanup_operations: Optional[str] = None,
                                jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX function return record for preserved JSX extraction.

        ARCHITECTURE: Normalized many-to-many relationship (JSX variant).
        - Phase 1: Batch JSX function return record (without return_vars column)
        - Phase 2: Batch JSX junction records for each return variable

        NO FALLBACKS. If return_vars is malformed, hard fail.
        """
        # Phase 1: Add JSX function return record (8 params, no return_vars column)
        self.generic_batches['function_returns_jsx'].append((file_path, line, function_name, return_expr,
                                                             has_jsx, returns_component,
                                                             cleanup_operations, jsx_mode, extraction_pass))

        # Phase 2: Add JSX junction records for each return variable
        if return_vars:
            for return_var in return_vars:
                if not return_var:  # Skip empty strings (data validation, not fallback)
                    continue
                # Schema: (return_file, return_line, return_function, jsx_mode, return_var_name)
                self.generic_batches['function_return_sources_jsx'].append((file_path, line, function_name, jsx_mode, return_var))

    def add_symbol_jsx(self, path: str, name: str, symbol_type: str, line: int, col: int,
                      jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX symbol record for preserved JSX extraction."""
        self.generic_batches['symbols_jsx'].append((path, name, symbol_type, line, col, jsx_mode, extraction_pass))

    def add_assignment_jsx(self, file_path: str, line: int, target_var: str, source_expr: str,
                          source_vars: List[str], in_function: str, property_path: Optional[str] = None,
                          jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX assignment record for preserved JSX extraction.

        ARCHITECTURE: Normalized many-to-many relationship (JSX variant).
        - Phase 1: Batch JSX assignment record (without source_vars column)
        - Phase 2: Batch JSX junction records for each source variable

        Args:
            property_path: Full property path for destructured assignments (e.g., 'req.params.id')
                          NULL for non-destructured assignments (e.g., 'const x = y')

        NO FALLBACKS. If source_vars is malformed, hard fail.
        """
        # Phase 1: Add JSX assignment record (8 params including property_path)
        self.generic_batches['assignments_jsx'].append((file_path, line, target_var, source_expr,
                                                        in_function, property_path, jsx_mode, extraction_pass))

        # Phase 2: Add JSX junction records for each source variable
        if source_vars:
            for source_var in source_vars:
                if not source_var:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['assignment_sources_jsx'].append((file_path, line, target_var, jsx_mode, source_var))

    def add_function_call_arg_jsx(self, file_path: str, line: int, caller_function: str,
                                  callee_function: str, arg_index: int, arg_expr: str, param_name: str,
                                  jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX function call argument record for preserved JSX extraction."""
        self.generic_batches['function_call_args_jsx'].append((file_path, line, caller_function, callee_function,
                                                               arg_index, arg_expr, param_name, jsx_mode, extraction_pass))
