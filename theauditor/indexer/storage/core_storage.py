"""Core storage handlers for language-agnostic patterns."""

import json
import os
import sqlite3
from pathlib import Path

from theauditor.utils.logging import logger

from .base import BaseStorage


class CoreStorage(BaseStorage):
    """Core storage handlers for language-agnostic patterns."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self._valid_construct_ids: set[str] = set()

        self.handlers = {
            "imports": self._store_imports,
            "refs": self._store_imports,
            "resolved_imports": self._store_imports,
            "api_endpoints": self._store_routes,
            "routes": self._store_routes,
            "router_mounts": self._store_router_mounts,
            "middleware_chains": self._store_express_middleware_chains,
            "sql_objects": self._store_sql_objects,
            "sql_queries": self._store_sql_queries,
            "cdk_constructs": self._store_cdk_constructs,
            "cdk_construct_properties": self._store_cdk_construct_properties,
            "symbols": self._store_symbols,
            "type_annotations": self._store_type_annotations,
            "orm_queries": self._store_orm_queries,
            "validation_calls": self._store_validation_framework_usage,
            "assignments": self._store_assignments,
            "function_calls": self._store_function_calls,
            "returns": self._store_returns,
            "cfg": self._store_cfg,
            "jwt_patterns": self._store_jwt_patterns,
            "react_components": self._store_react_components,
            "class_properties": self._store_class_properties,
            "env_var_usage": self._store_env_var_usage,
            "orm_relationships": self._store_orm_relationships,
            "variable_usage": self._store_variable_usage,
            "object_literals": self._store_object_literals,
        }

    def begin_file_processing(self) -> None:
        """Reset per-file gatekeeper state.

        Called by DataStorer.store() at the start of each file to prevent
        cross-file contamination of the gatekeeper tracking sets.
        """
        self._valid_construct_ids.clear()

    def _store_imports(self, file_path: str, imports, jsx_pass: bool):
        """Store imports/references."""

        if isinstance(imports, dict):
            logger.debug(f"Processing {len(imports)} ref entries for {file_path}")
            for _name, resolved_path in imports.items():
                resolved = resolved_path.replace("\\", "/") if resolved_path else ""

                try:
                    self.db_manager.add_ref(file_path, "ref", resolved, None)
                    self.counts["refs"] += 1
                except sqlite3.IntegrityError as e:
                    logger.critical(
                        f"FK VIOLATION in add_ref (dict): src={file_path!r}, "
                        f"target={resolved!r} -- {e}"
                    )
                    raise
            return

        logger.debug(f"Processing {len(imports)} imports for {file_path}")
        for import_item in imports:
            if isinstance(import_item, dict):
                kind = import_item.get("type", "import")
                value = import_item.get("target") or import_item.get("source", "")
                line = import_item.get("line")
            elif isinstance(import_item, (list, tuple)):
                kind = import_item[0] if len(import_item) > 0 else "import"
                value = import_item[1] if len(import_item) > 1 else ""
                line = import_item[2] if len(import_item) > 2 else None
            else:
                kind = "import"
                value = str(import_item)
                line = None

            resolved = self._current_extracted.get("refs", {}).get(value, value)

            if resolved and isinstance(resolved, str):
                resolved = resolved.replace("\\", "/")
            logger.debug(f"Adding ref: {file_path} -> {kind} {resolved} (line {line})")

            try:
                self.db_manager.add_ref(file_path, kind, resolved, line)
                self.counts["refs"] += 1
            except sqlite3.IntegrityError as e:
                logger.critical(
                    f"FK VIOLATION in add_ref: src={file_path!r}, kind={kind!r}, "
                    f"target={resolved!r}, line={line} -- {e}"
                )
                raise

    def _store_routes(self, file_path: str, routes: list, jsx_pass: bool):
        """Store api_endpoints with all 8 fields.

        INPUT VALIDATION: Skip routes missing required 'line' field.
        """
        for route in routes:
            if isinstance(route, dict):
                line = route.get("line")
                if line is None:
                    logger.warning(
                        f"EXTRACTOR BUG: Route missing 'line' field. "
                        f"File: {file_path}, Pattern: {route.get('pattern', 'unknown')}. Skipping."
                    )
                    continue

                self.db_manager.add_endpoint(
                    file_path=file_path,
                    method=route.get("method", "GET"),
                    pattern=route.get("pattern", ""),
                    controls=route.get("controls", []),
                    line=line,
                    path=route.get("path"),
                    has_auth=route.get("has_auth", False),
                    handler_function=route.get("handler_function"),
                )
            else:
                method, pattern, controls = route
                self.db_manager.add_endpoint(file_path, method, pattern, controls, line=0)
            self.counts["routes"] += 1

    def _store_router_mounts(self, file_path: str, router_mounts: list, jsx_pass: bool):
        """Store router mount points (PHASE 6.7 - AST-based route resolution)."""
        for mount in router_mounts:
            if isinstance(mount, dict):
                self.db_manager.add_router_mount(
                    file=mount.get("file", file_path),
                    line=mount.get("line", 0),
                    mount_path_expr=mount.get("mount_path_expr", ""),
                    router_variable=mount.get("router_variable", ""),
                    is_literal=mount.get("is_literal", False),
                )
                if "router_mounts" not in self.counts:
                    self.counts["router_mounts"] = 0
                self.counts["router_mounts"] += 1

    def _store_express_middleware_chains(
        self, file_path: str, express_middleware_chains: list, jsx_pass: bool
    ):
        """Store Express middleware chains (PHASE 5)."""
        for chain in express_middleware_chains:
            if isinstance(chain, dict):
                self.db_manager.generic_batches["express_middleware_chains"].append(
                    (
                        file_path,
                        chain.get("route_line"),
                        chain.get("route_path", ""),
                        chain.get("route_method", "GET"),
                        chain.get("execution_order", 0),
                        chain.get("handler_expr", ""),
                        chain.get("handler_type", "middleware"),
                        chain.get("handler_file"),
                        chain.get("handler_function"),
                        chain.get("handler_line"),
                    )
                )
                if "express_middleware_chains" not in self.counts:
                    self.counts["express_middleware_chains"] = 0
                self.counts["express_middleware_chains"] += 1

    def _store_sql_objects(self, file_path: str, sql_objects: list, jsx_pass: bool):
        """Store SQL objects."""
        for kind, name in sql_objects:
            self.db_manager.add_sql_object(file_path, kind, name)
            self.counts["sql"] += 1

    def _store_sql_queries(self, file_path: str, sql_queries: list, jsx_pass: bool):
        """Store SQL queries."""
        for query in sql_queries:
            self.db_manager.add_sql_query(
                file_path,
                query["line"],
                query["query_text"],
                query["command"],
                query["tables"],
                query.get("extraction_source", "code_execute"),
            )
            self.counts["sql_queries"] += 1

    def _store_cdk_constructs(self, file_path: str, cdk_constructs: list, jsx_pass: bool):
        """Store CDK constructs (AWS Infrastructure-as-Code)."""
        for construct in cdk_constructs:
            if not isinstance(construct, dict):
                continue
            line = construct.get("line", 0)
            cdk_class = construct.get("cdk_class", "")
            construct_name = construct.get("construct_name")

            construct_id = f"{file_path}::L{line}::{cdk_class}::{construct_name or 'unnamed'}"

            if os.environ.get("THEAUDITOR_CDK_DEBUG") == "1":
                logger.info(f"Generating construct_id: {construct_id}")
                logger.info(
                    f"file_path={file_path}, line={line}, cdk_class={cdk_class}, construct_name={construct_name}"
                )

            self.db_manager.add_cdk_construct(
                file_path=file_path,
                line=line,
                cdk_class=cdk_class,
                construct_name=construct_name,
                construct_id=construct_id,
            )

            self._valid_construct_ids.add(construct_id)

            for prop in construct.get("properties", []):
                self.db_manager.add_cdk_construct_property(
                    construct_id=construct_id,
                    property_name=prop.get("name", ""),
                    property_value_expr=prop.get("value_expr", ""),
                    line=prop.get("line", line),
                )

            if "cdk_constructs" not in self.counts:
                self.counts["cdk_constructs"] = 0
            self.counts["cdk_constructs"] += 1

    def _store_cdk_construct_properties(self, file_path: str, properties: list, jsx_pass: bool):
        """Store CDK construct properties from flat junction array (JS format).

        GATEKEEPER: Only insert if parent construct_id exists in _valid_construct_ids.
        Orphaned properties are logged and skipped to prevent FK violations.
        """
        for prop in properties:
            if not isinstance(prop, dict):
                continue

            construct_line = prop.get("construct_line", 0)
            construct_class = prop.get("construct_class", "")
            construct_name = prop.get("construct_name", "unnamed")

            construct_id = f"{file_path}::L{construct_line}::{construct_class}::{construct_name}"

            if construct_id not in self._valid_construct_ids:
                fallback_id = f"{file_path}::L{construct_line}::{construct_class}::unnamed"
                if fallback_id in self._valid_construct_ids:
                    construct_id = fallback_id
                else:
                    logger.warning(
                        f"GATEKEEPER: Skipping orphaned cdk_construct_property. "
                        f"construct_id={construct_id!r} not in valid set. "
                        f"File: {file_path}, Line: {construct_line}"
                    )
                    continue

            self.db_manager.add_cdk_construct_property(
                construct_id=construct_id,
                property_name=prop.get("property_name", ""),
                property_value_expr=prop.get("value_expr", ""),
                line=prop.get("property_line", construct_line),
            )
            self.counts["cdk_construct_properties"] = (
                self.counts.get("cdk_construct_properties", 0) + 1
            )

    def _store_symbols(self, file_path: str, symbols: list, jsx_pass: bool):
        """Store symbols.

        PHASE 1 FIX: Convert TypeError raises to logger.warning + continue.
        One bad symbol should not crash entire file's storage. Log and skip.
        """
        skipped_count = 0
        for idx, symbol in enumerate(symbols):
            if not isinstance(symbol, dict):
                logger.warning(
                    f"EXTRACTOR BUG: Symbol at index {idx} must be dict, got {type(symbol).__name__}. "
                    f"File: {file_path}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(symbol.get("name"), str) or not symbol["name"]:
                logger.warning(
                    f"EXTRACTOR BUG: Symbol.name must be non-empty str. "
                    f"File: {file_path}, Index: {idx}, Got: {repr(symbol.get('name'))}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(symbol.get("type"), str) or not symbol["type"]:
                logger.warning(
                    f"EXTRACTOR BUG: Symbol.type must be non-empty str. "
                    f"File: {file_path}, Symbol: {symbol.get('name')}, Got: {repr(symbol.get('type'))}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(symbol.get("line"), int) or symbol["line"] < 1:
                logger.warning(
                    f"EXTRACTOR BUG: Symbol.line must be int >= 1. "
                    f"File: {file_path}, Symbol: {symbol.get('name')}, Got: {repr(symbol.get('line'))}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(symbol.get("col"), int) or symbol["col"] < 0:
                logger.warning(
                    f"EXTRACTOR BUG: Symbol.col must be int >= 0. "
                    f"File: {file_path}, Symbol: {symbol.get('name')}, Got: {repr(symbol.get('col'))}. Skipping."
                )
                skipped_count += 1
                continue

            if jsx_pass:
                self.db_manager.add_symbol_jsx(
                    file_path,
                    symbol["name"],
                    symbol["type"],
                    symbol["line"],
                    symbol["col"],
                    jsx_mode="preserved",
                    extraction_pass=2,
                )
            else:
                parameters_json = None
                if "parameters" in symbol and symbol["parameters"]:
                    parameters_json = json.dumps(symbol["parameters"])

                self.db_manager.add_symbol(
                    file_path,
                    symbol["name"],
                    symbol["type"],
                    symbol["line"],
                    symbol["col"],
                    symbol.get("end_line"),
                    symbol.get("type_annotation"),
                    parameters_json,
                    symbol.get("is_typed"),
                )
                self.counts["symbols"] += 1

        if skipped_count > 0:
            logger.warning(
                f"Skipped {skipped_count}/{len(symbols)} malformed symbols in {file_path}"
            )

    def _store_type_annotations(self, file_path: str, type_annotations: list, jsx_pass: bool):
        """Store TypeScript type annotations."""
        for annotation in type_annotations:
            self.db_manager.add_type_annotation(
                file_path,
                annotation.get("line", 0),
                annotation.get("column", 0),
                annotation.get("symbol_name", ""),
                annotation.get("annotation_type", annotation.get("symbol_kind", "unknown")),
                annotation.get("type_annotation", annotation.get("type_text", "")),
                annotation.get("is_any", False),
                annotation.get("is_unknown", False),
                annotation.get("is_generic", False),
                annotation.get("has_type_params", False),
                annotation.get("type_params"),
                annotation.get("return_type"),
                annotation.get("extends_type"),
            )

            language = (annotation.get("language") or "").lower()
            if not language:
                ext = Path(file_path).suffix.lower()
                if ext in {".ts", ".tsx", ".js", ".jsx"}:
                    language = "typescript"
                elif ext == ".py":
                    language = "python"
                elif ext == ".rs":
                    language = "rust"

            if language in {"typescript", "javascript"}:
                self.counts["type_annotations_typescript"] += 1
            elif language == "python":
                self.counts["type_annotations_python"] += 1
            elif language == "rust":
                self.counts["type_annotations_rust"] += 1

            self.counts["type_annotations"] += 1

    def _store_orm_queries(self, file_path: str, orm_queries: list, jsx_pass: bool):
        """Store ORM queries."""
        for query in orm_queries:
            self.db_manager.add_orm_query(
                file_path,
                query["line"],
                query["query_type"],
                query.get("includes"),
                query.get("has_limit", False),
                query.get("has_transaction", False),
            )
            self.counts["orm"] += 1

    def _store_validation_framework_usage(
        self, file_path: str, validation_framework_usage: list, jsx_pass: bool
    ):
        """Store validation framework usage (for taint analysis sanitizer detection)."""
        if os.environ.get("THEAUDITOR_VALIDATION_DEBUG") and file_path.endswith("validate.ts"):
            logger.error(
                f"[PY-DEBUG] Extracted keys for {file_path}: {list(self._current_extracted.keys())}"
            )
            logger.error(
                f"[PY-DEBUG] validation_framework_usage has {len(validation_framework_usage)} items"
            )

        for usage in validation_framework_usage:
            self.db_manager.generic_batches["validation_framework_usage"].append(
                (
                    file_path,
                    usage["line"],
                    usage["framework"],
                    usage["method"],
                    usage.get("variable_name"),
                    1 if usage.get("is_validator", True) else 0,
                    usage.get("argument_expr", ""),
                )
            )

    def _store_assignments(self, file_path: str, assignments: list, jsx_pass: bool):
        """Store data flow information for taint analysis.

        TAINT FIX T3: Convert raises to logger.warning + continue.
        One bad assignment should not crash entire file's storage. Log and skip.
        """
        if assignments:
            logger.debug(f"Found {len(assignments)} assignments in {file_path}")
            first = assignments[0]
            logger.debug(
                f"First assignment: line {first.get('line')}, {first.get('target_var')} = {first.get('source_expr', '')[:50]}"
            )

        seen = set()
        skipped_count = 0

        for idx, assignment in enumerate(assignments):
            if not isinstance(assignment, dict):
                logger.warning(
                    f"EXTRACTOR BUG: Assignment at index {idx} must be dict, got {type(assignment).__name__}. "
                    f"File: {file_path}. Skipping."
                )
                skipped_count += 1
                continue

            line_val = assignment.get("line", 0)
            target_var = assignment.get("target_var", "")
            key = (file_path, line_val, assignment.get("col", 0), target_var)
            if key in seen:
                logger.warning(
                    f"EXTRACTOR BUG: Duplicate assignment detected. "
                    f"File: {file_path}, Key: {key}. Skipping duplicate."
                )
                skipped_count += 1
                continue
            seen.add(key)

            if not isinstance(line_val, int) or line_val < 1:
                logger.warning(
                    f"EXTRACTOR BUG: Assignment.line must be int >= 1. "
                    f"File: {file_path}, Got: {repr(line_val)}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(target_var, str) or not target_var:
                logger.warning(
                    f"EXTRACTOR BUG: Assignment.target_var must be non-empty str. "
                    f"File: {file_path}, Line: {line_val}, Got: {repr(target_var)}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(assignment.get("source_expr"), str):
                logger.warning(
                    f"EXTRACTOR BUG: Assignment.source_expr must be str. "
                    f"File: {file_path}, Line: {line_val}, Got: {repr(assignment.get('source_expr'))}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(assignment.get("in_function"), str):
                logger.warning(
                    f"EXTRACTOR BUG: Assignment.in_function must be str. "
                    f"File: {file_path}, Line: {line_val}, Got: {repr(assignment.get('in_function'))}. Skipping."
                )
                skipped_count += 1
                continue

            if jsx_pass:
                self.db_manager.add_assignment_jsx(
                    file_path,
                    assignment["line"],
                    assignment["target_var"],
                    assignment["source_expr"],
                    assignment.get("source_vars", []),
                    assignment["in_function"],
                    assignment.get("property_path"),
                    jsx_mode="preserved",
                    extraction_pass=2,
                )
            else:
                self.db_manager.add_assignment(
                    file_path,
                    assignment["line"],
                    assignment["target_var"],
                    assignment["source_expr"],
                    assignment.get("source_vars", []),
                    assignment["in_function"],
                    assignment.get("property_path"),
                    col=assignment.get("col", 0),
                )
                self.counts["assignments"] += 1

        if skipped_count > 0:
            logger.warning(
                f"Skipped {skipped_count}/{len(assignments)} malformed assignments in {file_path}"
            )

    def _store_function_calls(self, file_path: str, function_calls: list, jsx_pass: bool):
        """Store function calls.

        TAINT FIX T3: Convert raises to logger.warning + continue.
        One bad call should not crash entire file's storage. Log and skip.
        """
        skipped_count = 0

        for idx, call in enumerate(function_calls):
            if not isinstance(call, dict):
                logger.warning(
                    f"EXTRACTOR BUG: Call at index {idx} must be dict, got {type(call).__name__}. "
                    f"File: {file_path}. Skipping."
                )
                skipped_count += 1
                continue

            callee = call.get("callee_function", "")

            if (
                not jsx_pass
                and callee
                and ("jwt" in callee.lower() or "jsonwebtoken" in callee.lower())
            ):
                if ".sign" in callee:
                    if call.get("argument_index") == 1:
                        arg_expr = call.get("argument_expr", "")
                        if "process.env" in arg_expr:
                            call["callee_function"] = "JWT_SIGN_ENV"
                        elif '"' in arg_expr or "'" in arg_expr:
                            call["callee_function"] = "JWT_SIGN_HARDCODED"
                        else:
                            call["callee_function"] = "JWT_SIGN_VAR"
                    else:
                        call["callee_function"] = f"JWT_SIGN#{call['callee_function']}"
                elif ".verify" in callee:
                    call["callee_function"] = f"JWT_VERIFY#{callee}"
                elif ".decode" in callee:
                    call["callee_function"] = f"JWT_DECODE#{callee}"

            if jsx_pass:
                self.db_manager.add_function_call_arg_jsx(
                    file_path,
                    call["line"],
                    call["caller_function"],
                    call["callee_function"],
                    call["argument_index"],
                    call["argument_expr"],
                    call.get("param_name", ""),
                    jsx_mode="preserved",
                    extraction_pass=2,
                )
            else:
                callee_file_path = call.get("callee_file_path")
                param_name = call.get("param_name", "")
                line_val = call.get("line", 0)

                if isinstance(callee_file_path, dict):
                    logger.warning(
                        f"EXTRACTOR BUG: callee_file_path must be str or None, got dict. "
                        f"File: {file_path}, Line: {line_val}. Skipping."
                    )
                    skipped_count += 1
                    continue

                if isinstance(param_name, dict):
                    logger.warning(
                        f"EXTRACTOR BUG: param_name must be str, got dict. "
                        f"File: {file_path}, Line: {line_val}, Callee: {callee}. Skipping."
                    )
                    skipped_count += 1
                    continue

                if not isinstance(line_val, int) or line_val < 1:
                    logger.warning(
                        f"EXTRACTOR BUG: Call.line must be int >= 1. "
                        f"File: {file_path}, Got: {repr(line_val)}. Skipping."
                    )
                    skipped_count += 1
                    continue

                if not isinstance(call.get("caller_function"), str):
                    logger.warning(
                        f"EXTRACTOR BUG: Call.caller_function must be str. "
                        f"File: {file_path}, Line: {line_val}, Got: {repr(call.get('caller_function'))}. Skipping."
                    )
                    skipped_count += 1
                    continue

                if not isinstance(callee, str) or not callee:
                    logger.warning(
                        f"EXTRACTOR BUG: Call.callee_function must be non-empty str. "
                        f"File: {file_path}, Line: {line_val}, Got: {repr(callee)}. Skipping."
                    )
                    skipped_count += 1
                    continue

                self.db_manager.add_function_call_arg(
                    file_path,
                    call["line"],
                    call["caller_function"],
                    call["callee_function"],
                    call["argument_index"],
                    call["argument_expr"],
                    param_name,
                    callee_file_path=callee_file_path,
                )
                self.counts["function_calls"] += 1

        if skipped_count > 0:
            logger.warning(
                f"Skipped {skipped_count}/{len(function_calls)} malformed function calls in {file_path}"
            )

    def _store_returns(self, file_path: str, returns: list, jsx_pass: bool):
        """Store return statements.

        TAINT FIX T3: Convert raises to logger.warning + continue.
        One bad return should not crash entire file's storage. Log and skip.
        """
        seen = set()
        skipped_count = 0

        for idx, ret in enumerate(returns):
            if not isinstance(ret, dict):
                logger.warning(
                    f"EXTRACTOR BUG: Return at index {idx} must be dict, got {type(ret).__name__}. "
                    f"File: {file_path}. Skipping."
                )
                skipped_count += 1
                continue

            line_val = ret.get("line", 0)
            func_name = ret.get("function_name", "")

            key = (file_path, line_val, ret.get("col", 0), func_name)
            if key in seen:
                logger.warning(
                    f"EXTRACTOR BUG: Duplicate function_return detected. "
                    f"File: {file_path}, Key: {key}. Skipping duplicate."
                )
                skipped_count += 1
                continue
            seen.add(key)

            if not isinstance(line_val, int) or line_val < 1:
                logger.warning(
                    f"EXTRACTOR BUG: Return.line must be int >= 1. "
                    f"File: {file_path}, Got: {repr(line_val)}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(func_name, str):
                logger.warning(
                    f"EXTRACTOR BUG: Return.function_name must be str. "
                    f"File: {file_path}, Line: {line_val}, Got: {repr(func_name)}. Skipping."
                )
                skipped_count += 1
                continue

            if not isinstance(ret.get("return_expr"), str):
                logger.warning(
                    f"EXTRACTOR BUG: Return.return_expr must be str. "
                    f"File: {file_path}, Line: {line_val}, Got: {repr(ret.get('return_expr'))}. Skipping."
                )
                skipped_count += 1
                continue

            if jsx_pass:
                self.db_manager.add_function_return_jsx(
                    file_path,
                    ret["line"],
                    ret["function_name"],
                    ret["return_expr"],
                    ret.get("return_vars", []),
                    ret.get("has_jsx", False),
                    ret.get("returns_component", False),
                    ret.get("cleanup_operations"),
                    jsx_mode="preserved",
                    extraction_pass=2,
                )
            else:
                self.db_manager.add_function_return(
                    file_path,
                    ret["line"],
                    ret["function_name"],
                    ret["return_expr"],
                    ret.get("return_vars", []),
                    col=ret.get("col", 0),
                )
                self.counts["returns"] += 1

        if skipped_count > 0:
            logger.warning(
                f"Skipped {skipped_count}/{len(returns)} malformed returns in {file_path}"
            )

    def _store_cfg(self, file_path: str, cfg: list, jsx_pass: bool):
        """Store control flow graph data to main or _jsx tables."""
        for function_cfg in cfg:
            if not function_cfg or not isinstance(function_cfg, dict):
                continue

            block_id_map = {}

            for block in function_cfg.get("blocks", []):
                temp_id = block["id"]

                if jsx_pass:
                    real_id = self.db_manager.add_cfg_block_jsx(
                        file_path,
                        function_cfg["function_name"],
                        block["type"],
                        block["start_line"],
                        block["end_line"],
                        block.get("condition"),
                    )
                else:
                    real_id = self.db_manager.add_cfg_block(
                        file_path,
                        function_cfg["function_name"],
                        block["type"],
                        block["start_line"],
                        block["end_line"],
                        block.get("condition"),
                    )

                block_id_map[temp_id] = real_id
                self.counts["cfg_blocks"] += 1

                for stmt in block.get("statements", []):
                    if jsx_pass:
                        self.db_manager.add_cfg_statement_jsx(
                            real_id, stmt["type"], stmt["line"], stmt.get("text")
                        )
                    else:
                        self.db_manager.add_cfg_statement(
                            real_id, stmt["type"], stmt["line"], stmt.get("text")
                        )
                    self.counts["cfg_statements"] += 1

            for edge in function_cfg.get("edges", []):
                source_id = block_id_map.get(edge["source"], edge["source"])
                target_id = block_id_map.get(edge["target"], edge["target"])

                if jsx_pass:
                    self.db_manager.add_cfg_edge_jsx(
                        file_path, function_cfg["function_name"], source_id, target_id, edge["type"]
                    )
                else:
                    self.db_manager.add_cfg_edge(
                        file_path, function_cfg["function_name"], source_id, target_id, edge["type"]
                    )
                self.counts["cfg_edges"] += 1

            if "cfg_functions" not in self.counts:
                self.counts["cfg_functions"] = 0
            self.counts["cfg_functions"] += 1

    def _store_jwt_patterns(self, file_path: str, jwt_patterns: list, jsx_pass: bool):
        """Store dedicated JWT patterns."""
        for pattern in jwt_patterns:
            self.db_manager.add_jwt_pattern(
                file_path=file_path,
                line_number=pattern["line"],
                pattern_type=pattern["type"],
                pattern_text=pattern.get("full_match", ""),
                secret_source=pattern.get("secret_type", "unknown"),
                algorithm=pattern.get("algorithm"),
            )
            self.counts["jwt"] = self.counts.get("jwt", 0) + 1

    def _store_react_components(self, file_path: str, react_components: list, jsx_pass: bool):
        """Store React-specific data."""
        for component in react_components:
            self.db_manager.add_react_component(
                file_path,
                component["name"],
                component["type"],
                component["start_line"],
                component["end_line"],
                component["has_jsx"],
                component.get("hooks_used"),
                component.get("props_type"),
            )
            self.counts["react_components"] += 1

    def _store_class_properties(self, file_path: str, class_properties: list, jsx_pass: bool):
        """Store class property declarations (TypeScript/JavaScript ES2022+)."""
        logger.debug(f"Found {len(class_properties)} class_properties for {file_path}")
        for prop in class_properties:
            if os.environ.get("THEAUDITOR_DEBUG") and len(class_properties) > 0:
                logger.debug(
                    f"Adding {prop['class_name']}.{prop['property_name']} at line {prop['line']}"
                )
            self.db_manager.add_class_property(
                file_path,
                prop["line"],
                prop["class_name"],
                prop["property_name"],
                prop.get("property_type"),
                prop.get("is_optional", False),
                prop.get("is_readonly", False),
                prop.get("access_modifier"),
                prop.get("has_declare", False),
                prop.get("initializer"),
            )
            if "class_properties" not in self.counts:
                self.counts["class_properties"] = 0
            self.counts["class_properties"] += 1

    def _store_env_var_usage(self, file_path: str, env_var_usage: list, jsx_pass: bool):
        """Store environment variable usage (process.env.X).

        TAINT FIX T3: Convert raises to logger.warning + continue.
        One bad env_var usage should not crash entire file's storage. Log and skip.
        """
        logger.debug(f"Found {len(env_var_usage)} env_var_usage for {file_path}")

        seen = set()
        skipped_count = 0

        for idx, usage in enumerate(env_var_usage):
            if not isinstance(usage, dict):
                logger.warning(
                    f"EXTRACTOR BUG: env_var_usage at index {idx} must be dict, got {type(usage).__name__}. "
                    f"File: {file_path}. Skipping."
                )
                skipped_count += 1
                continue

            line_val = usage.get("line", 0)
            var_name = usage.get("var_name", "")
            access_type = usage.get("access_type", "")

            key = (file_path, line_val, usage.get("col", 0), var_name, access_type)
            if key in seen:
                logger.warning(
                    f"EXTRACTOR BUG: Duplicate env_var_usage detected. "
                    f"File: {file_path}, Key: {key}. Skipping duplicate."
                )
                skipped_count += 1
                continue
            seen.add(key)

            self.db_manager.add_env_var_usage(
                file_path,
                usage["line"],
                usage["var_name"],
                usage["access_type"],
                usage.get("in_function"),
                usage.get("property_access"),
            )
            if "env_var_usage" not in self.counts:
                self.counts["env_var_usage"] = 0
            self.counts["env_var_usage"] += 1

        if skipped_count > 0:
            logger.warning(
                f"Skipped {skipped_count}/{len(env_var_usage)} malformed env_var_usage in {file_path}"
            )

    def _store_orm_relationships(self, file_path: str, orm_relationships: list, jsx_pass: bool):
        """Store ORM relationship declarations (hasMany, belongsTo, etc.)."""
        logger.debug(f"Found {len(orm_relationships)} orm_relationships for {file_path}")
        for rel in orm_relationships:
            self.db_manager.add_orm_relationship(
                file_path,
                rel["line"],
                rel["source_model"],
                rel["target_model"],
                rel["relationship_type"],
                rel.get("foreign_key"),
                rel.get("cascade_delete", False),
                rel.get("as_name"),
            )
            if "orm_relationships" not in self.counts:
                self.counts["orm_relationships"] = 0
            self.counts["orm_relationships"] += 1

    def _store_variable_usage(self, file_path: str, variable_usage: list, jsx_pass: bool):
        """Store variable usage."""
        for var in variable_usage:
            self.db_manager.add_variable_usage(
                file_path,
                var["line"],
                var["variable_name"],
                var["usage_type"],
                var.get("in_component"),
                var.get("in_hook"),
                var.get("scope_level", 0),
            )
            self.counts["variable_usage"] += 1

    def _store_object_literals(self, file_path: str, object_literals: list, jsx_pass: bool):
        """Store object literal storage (PHASE 3)."""
        for obj_lit in object_literals:
            self.db_manager.add_object_literal(
                file_path,
                obj_lit["line"],
                obj_lit["variable_name"],
                obj_lit["property_name"],
                obj_lit["property_value"],
                obj_lit["property_type"],
                obj_lit.get("nested_level", 0),
                obj_lit.get("in_function", ""),
            )
            self.counts["object_literals"] += 1
