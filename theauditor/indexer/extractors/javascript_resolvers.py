"""Resolution logic for JavaScript/TypeScript analysis."""

import json
import os
import re
import sqlite3

from theauditor.utils.logging import logger


class JavaScriptResolversMixin:
    """Mixin containing static database resolution methods."""

    @staticmethod
    def resolve_router_mount_hierarchy(db_path: str):
        """Resolve router mount hierarchy to populate api_endpoints.full_path."""
        debug = os.getenv("THEAUDITOR_DEBUG") == "1"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file, line, mount_path_expr, router_variable, is_literal
            FROM router_mounts
            ORDER BY file, line
        """)
        raw_mounts = cursor.fetchall()

        if debug:
            logger.debug(f"Loaded {len(raw_mounts)} mount statements")

        if not raw_mounts:
            conn.close()
            return

        cursor.execute("""
            SELECT file, target_var, source_expr
            FROM assignments
            WHERE target_var LIKE '%PREFIX%' OR target_var LIKE '%prefix%'
        """)

        constants = {}
        for file, var_name, value in cursor.fetchall():
            key = f"{file}::{var_name}"
            cleaned_value = value.strip().strip("\"'")
            constants[key] = cleaned_value

        if debug:
            logger.debug(f"Loaded {len(constants)} constant definitions")

        cursor.execute("""
            SELECT file, package, alias_name
            FROM import_styles
            WHERE alias_name IS NOT NULL
        """)

        imports = {}
        for file, package, alias_name in cursor.fetchall():
            if not alias_name:
                continue

            if package.startswith("."):
                file_dir = "/".join(file.split("/")[:-1])

                if package == ".":
                    resolved = file_dir
                elif package.startswith("./"):
                    resolved = f"{file_dir}/{package[2:]}"
                elif package.startswith("../"):
                    parent_dir = "/".join(file_dir.split("/")[:-1])
                    resolved = f"{parent_dir}/{package[3:]}"
                else:
                    resolved = package

                if not resolved.endswith((".ts", ".js", ".tsx", ".jsx")):
                    resolved = f"{resolved}.ts"

                key = f"{file}::{alias_name}"
                imports[key] = resolved

        if debug:
            logger.debug(f"Loaded {len(imports)} import mappings")

        mount_map = {}

        for file, line, mount_expr, router_var, is_literal in raw_mounts:
            resolved_mount = None

            if is_literal:
                resolved_mount = mount_expr
            else:
                if mount_expr.startswith("`"):
                    var_pattern = r"\$\{([^}]+)\}"
                    matches = re.findall(var_pattern, mount_expr)

                    resolved_template = mount_expr.strip("`")
                    for var_name in matches:
                        const_key = f"{file}::{var_name}"
                        if const_key in constants:
                            var_value = constants[const_key]
                            resolved_template = resolved_template.replace(
                                f"${{{var_name}}}", var_value
                            )
                        else:
                            resolved_template = None
                            break

                    resolved_mount = resolved_template
                else:
                    const_key = f"{file}::{mount_expr}"
                    resolved_mount = constants.get(const_key)

            if not resolved_mount:
                if debug:
                    logger.debug(f"Failed to resolve mount: {file}:{line} - {mount_expr}")
                continue

            import_key = f"{file}::{router_var}"
            router_file = imports.get(import_key)

            if not router_file:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM router_mounts
                    WHERE file = ? AND router_variable = ?
                """,
                    (file, router_var),
                )
                if cursor.fetchone()[0] > 0:
                    router_file = file
                    if debug:
                        logger.debug(f"{router_var} is local to {file}")

            if router_file:
                mount_map[router_file] = resolved_mount
                if debug:
                    logger.debug(f"{router_file} → {resolved_mount}")

        updated_count = 0
        for file_path, mount_path in mount_map.items():
            cursor.execute(
                """
                SELECT rowid, pattern
                FROM api_endpoints
                WHERE file = ?
            """,
                (file_path,),
            )

            for rowid, pattern in cursor.fetchall():
                if pattern and pattern.startswith("/"):
                    full_path = mount_path + pattern
                else:
                    full_path = mount_path + "/" + (pattern or "")

                cursor.execute(
                    """
                    UPDATE api_endpoints
                    SET full_path = ?
                    WHERE rowid = ?
                """,
                    (full_path, rowid),
                )
                updated_count += 1

        conn.commit()
        conn.close()

    @staticmethod
    def resolve_handler_file_paths(db_path: str):
        """Resolve handler_file for express_middleware_chains from import statements."""
        debug = os.getenv("THEAUDITOR_DEBUG") == "1"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT rowid, file, handler_function
            FROM express_middleware_chains
            WHERE handler_file IS NULL
              AND handler_function IS NOT NULL
              AND handler_function != ''
        """)
        chains_to_resolve = cursor.fetchall()

        if debug:
            logger.debug(f"Found {len(chains_to_resolve)} chains to resolve")

        if not chains_to_resolve:
            conn.close()
            return

        cursor.execute("""
            SELECT file, import_line, specifier_name
            FROM import_specifiers
        """)
        specifier_to_line = {}
        for file, import_line, specifier_name in cursor.fetchall():
            key = (file, specifier_name.lower())
            specifier_to_line[key] = import_line

        cursor.execute("""
            SELECT file, line, package
            FROM import_styles
        """)
        line_to_module = {}
        for file, line, package in cursor.fetchall():
            key = (file, line)
            line_to_module[key] = package

        cursor.execute("""
            SELECT file, target_var, source_expr
            FROM assignments
            WHERE source_expr LIKE 'new %'
        """)
        var_to_class = {}
        for file, target_var, source_expr in cursor.fetchall():
            class_match = re.match(r"new\s+([A-Za-z0-9_]+)", source_expr)
            if class_match:
                class_name = class_match.group(1)
                key = (file, target_var.lower())
                var_to_class[key] = class_name

        if debug:
            logger.debug(
                f"Loaded {len(specifier_to_line)} specifiers, {len(line_to_module)} modules, {len(var_to_class)} class instantiations"
            )

        updates = []
        resolved_count = 0
        unresolved_count = 0

        for rowid, route_file, handler_function in chains_to_resolve:
            target_handler = handler_function

            bind_match = re.match(r"^(.+)\.bind\s*\(", target_handler)
            if bind_match:
                target_handler = bind_match.group(1)

            if "(" in target_handler:
                func_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", target_handler)
                func_name = func_match.group(1) if func_match else None

                if func_name:
                    target_handler = func_name
                else:
                    unresolved_count += 1
                    continue

            if target_handler.endswith("!"):
                target_handler = target_handler[:-1]

            import_line = None

            if "." not in target_handler:
                lookup_name = target_handler
                key = (route_file, lookup_name.lower())
                import_line = specifier_to_line.get(key)

                if not import_line:
                    for (f, spec), line in specifier_to_line.items():
                        if f == route_file and spec.lower() == lookup_name.lower():
                            import_line = line
                            break

                if not import_line:
                    unresolved_count += 1
                    continue
            else:
                parts = target_handler.split(".")
                class_name = parts[0]
                var_name = class_name[0].lower() + class_name[1:] if class_name else class_name

                key = (route_file, var_name.lower())
                import_line = specifier_to_line.get(key)

                if not import_line:
                    for (f, spec), line in specifier_to_line.items():
                        if f == route_file and spec.lower() == var_name.lower():
                            import_line = line
                            break

                if not import_line:
                    instantiation_key = (route_file, var_name.lower())
                    actual_class = var_to_class.get(instantiation_key)
                    if actual_class:
                        class_key = (route_file, actual_class.lower())
                        import_line = specifier_to_line.get(class_key)
                        if not import_line:
                            for (f, spec), line in specifier_to_line.items():
                                if f == route_file and spec.lower() == actual_class.lower():
                                    import_line = line
                                    break

                if not import_line:
                    unresolved_count += 1
                    continue

            module_path = line_to_module.get((route_file, import_line))
            if not module_path:
                unresolved_count += 1
                continue

            resolved_path = None

            if module_path.startswith("."):
                route_dir = "/".join(route_file.split("/")[:-1])
                if module_path.startswith("./"):
                    resolved_path = f"{route_dir}/{module_path[2:]}"
                elif module_path.startswith("../"):
                    parent_dir = "/".join(route_dir.split("/")[:-1])
                    resolved_path = f"{parent_dir}/{module_path[3:]}"
                else:
                    resolved_path = module_path

            if not resolved_path:
                resolved_path = module_path

            if resolved_path and not resolved_path.endswith((".ts", ".js", ".tsx", ".jsx")):
                resolved_path = f"{resolved_path}.ts"

            cursor.execute(
                """
                SELECT 1 FROM symbols WHERE path = ? LIMIT 1
            """,
                (resolved_path,),
            )
            if cursor.fetchone():
                updates.append((resolved_path, rowid))
                resolved_count += 1
            else:
                unresolved_count += 1

        if updates:
            cursor.executemany(
                """
                UPDATE express_middleware_chains
                SET handler_file = ?
                WHERE rowid = ?
            """,
                updates,
            )
            conn.commit()

        conn.close()

        if debug:
            logger.debug(f"Resolved {resolved_count} handler files")
            logger.debug(f"Unresolved: {unresolved_count}")

    @staticmethod
    def resolve_cross_file_parameters(db_path: str):
        """Resolve parameter names for cross-file function calls."""
        logger = None
        if "logger" in globals():
            logger = globals()["logger"]

        debug = os.getenv("THEAUDITOR_DEBUG") == "1"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT rowid, callee_function, argument_index, param_name
            FROM function_call_args
            WHERE param_name LIKE 'arg%'
        """)

        calls_to_fix = cursor.fetchall()
        total_calls = len(calls_to_fix)

        if logger:
            logger.info(
                f"[PARAM RESOLUTION] Found {total_calls} function calls with generic param names"
            )
        elif debug:
            logger.debug(f"Found {total_calls} function calls with generic param names")

        if total_calls == 0:
            conn.close()
            return

        cursor.execute("""
            SELECT name, parameters
            FROM symbols
            WHERE type = 'function' AND parameters IS NOT NULL
        """)

        param_lookup = {}
        for name, params_json in cursor.fetchall():
            try:
                params = json.loads(params_json)

                parts = name.split(".")
                base_name = parts[-1] if parts else name

                param_lookup[base_name] = params
            except (json.JSONDecodeError, TypeError):
                continue

        if debug:
            logger.debug(f"Built lookup with {len(param_lookup)} functions")

        updates = []
        resolved_count = 0
        unresolved_count = 0

        for rowid, callee_function, arg_index, current_param_name in calls_to_fix:
            parts = callee_function.split(".")
            base_name = parts[-1] if parts else callee_function

            if base_name in param_lookup:
                params = param_lookup[base_name]

                if arg_index is not None and arg_index < len(params):
                    param_value = params[arg_index]

                    if isinstance(param_value, dict):
                        actual_param_name = param_value.get("name", f"arg{arg_index}")
                    else:
                        actual_param_name = param_value

                    updates.append((actual_param_name, rowid))
                    resolved_count += 1

                    if debug and resolved_count <= 5:
                        logger.debug(
                            f"{callee_function}[{arg_index}]: {current_param_name} -> {actual_param_name}"
                        )
                else:
                    unresolved_count += 1
            else:
                unresolved_count += 1

        if updates:
            cursor.executemany(
                """
                UPDATE function_call_args
                SET param_name = ?
                WHERE rowid = ?
            """,
                updates,
            )
            conn.commit()

            if logger:
                logger.info(f"[PARAM RESOLUTION] Resolved {resolved_count} parameter names")
                logger.info(
                    f"[PARAM RESOLUTION] Unresolved: {unresolved_count} (external libs, dynamic calls)"
                )
            elif debug:
                logger.debug(f"Resolved {resolved_count} parameter names")
                logger.debug(f"Unresolved: {unresolved_count} (external libs, dynamic calls)")

        conn.close()

    @staticmethod
    def resolve_import_paths(db_path: str):
        """Resolve import paths using indexed file data."""
        debug = os.getenv("THEAUDITOR_DEBUG") == "1"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT path FROM files
            WHERE ext IN ('.ts', '.tsx', '.js', '.jsx', '.vue', '.mjs', '.cjs')
        """)
        indexed_paths = {row[0] for row in cursor.fetchall()}

        if debug:
            logger.debug(f"Loaded {len(indexed_paths)} indexed JS/TS paths")

        cursor.execute("""
            SELECT rowid, file, package FROM import_styles
            WHERE package LIKE './%'
               OR package LIKE '../%'
        """)
        imports_to_resolve = cursor.fetchall()

        if debug:
            logger.debug(f"Found {len(imports_to_resolve)} imports to resolve")

        resolved_count = 0
        unresolved_count = 0

        for rowid, from_file, import_path in imports_to_resolve:
            resolved = _resolve_import(import_path, from_file, indexed_paths)
            if resolved:
                cursor.execute(
                    "UPDATE import_styles SET resolved_path = ? WHERE rowid = ?",
                    (resolved, rowid),
                )
                resolved_count += 1
            else:
                unresolved_count += 1

        conn.commit()
        conn.close()

        if debug:
            logger.debug(f"Resolved {resolved_count}/{len(imports_to_resolve)} imports")
            logger.debug(f"Unresolved: {unresolved_count}")


def _resolve_import(
    import_path: str,
    from_file: str,
    indexed_paths: set,
) -> str | None:
    """Resolve a single import path against indexed files.

    NOTE: Path alias resolution (@/, ~/) removed - TypeScript handles this
    via getAliasedSymbol(). Only relative paths are resolved here.
    """
    resolved_base = None

    if import_path.startswith("."):
        from_dir = "/".join(from_file.split("/")[:-1])
        if import_path.startswith("./"):
            resolved_base = from_dir + "/" + import_path[2:]
        elif import_path.startswith("../"):
            resolved_base = _resolve_parent_path(from_dir, import_path)
        else:
            resolved_base = from_dir + "/" + import_path[1:]

    if not resolved_base:
        return None

    resolved_base = _normalize_path(resolved_base)

    extensions = [".ts", ".tsx", ".js", ".jsx", ".vue", ""]
    index_files = ["index.ts", "index.tsx", "index.js", "index.jsx"]

    for ext in extensions:
        candidate = resolved_base + ext
        if candidate in indexed_paths:
            return candidate

    for index in index_files:
        candidate = resolved_base + "/" + index
        if candidate in indexed_paths:
            return candidate

    return None


def _resolve_parent_path(from_dir: str, import_path: str) -> str:
    """Resolve parent path traversals (../)."""
    parts = from_dir.split("/")
    import_parts = import_path.split("/")

    while import_parts and import_parts[0] == "..":
        import_parts.pop(0)
        if parts:
            parts.pop()

    return "/".join(parts + import_parts)


def _normalize_path(path: str) -> str:
    """Normalize path by resolving . and .. segments.

    GRAPH FIX G17: Convert backslashes to forward slashes BEFORE splitting.
    Without this, Windows-style paths like '..\\utils\\helper.ts' pass through
    unchanged because split("/") returns a single element, and the .. resolution
    logic never executes.
    """

    path = path.replace("\\", "/")
    parts = path.split("/")
    result = []
    for part in parts:
        if part == "..":
            if result:
                result.pop()
        elif part and part != ".":
            result.append(part)
    return "/".join(result)
