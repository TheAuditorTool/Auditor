"""JavaScript/TypeScript extractor."""

import os
from datetime import datetime
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.utils.logging import logger

from . import BaseExtractor
from .javascript_resolvers import JavaScriptResolversMixin
from .sql import parse_sql_query


class JavaScriptExtractor(BaseExtractor, JavaScriptResolversMixin):
    """Extractor for JavaScript and TypeScript files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue"]

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all JavaScript/TypeScript information."""
        result = {
            "imports": [],
            "refs": {},
            "symbols": [],
            "assignments": [],
            "function_calls": [],
            "returns": [],
            "variable_usage": [],
            "frontend_api_calls": [],
            "sql_queries": [],
            "jwt_patterns": [],
            "type_annotations": [],
            "react_components": [],
            "react_hooks": [],
            "react_component_hooks": [],
            "react_hook_dependencies": [],
            "vue_components": [],
            "vue_hooks": [],
            "vue_directives": [],
            "vue_provide_inject": [],
            "orm_queries": [],
            "api_endpoints": [],
            "object_literals": [],
            "class_properties": [],
            "env_var_usage": [],
            "orm_relationships": [],
            "cdk_constructs": [],
            "cdk_construct_properties": [],
            "sequelize_models": [],
            "sequelize_associations": [],
            "bullmq_queues": [],
            "bullmq_workers": [],
            "angular_components": [],
            "angular_services": [],
            "angular_modules": [],
            "angular_guards": [],
            "di_injections": [],
            "angular_component_styles": [],
            "angular_module_declarations": [],
            "angular_module_imports": [],
            "angular_module_providers": [],
            "angular_module_exports": [],
            "vue_component_props": [],
            "vue_component_emits": [],
            "vue_component_setup_returns": [],
            "middleware_chains": [],
            "validation_calls": [],
            "graphql_resolver_params": [],
            "assignment_source_vars": [],
            "return_source_vars": [],
            "func_params": [],
            "func_decorators": [],
            "func_decorator_args": [],
            "func_param_decorators": [],
            "class_decorators": [],
            "class_decorator_args": [],
            "import_specifiers": [],
            "import_style_names": [],
            "sequelize_model_fields": [],
            "cfg_blocks": [],
            "cfg_edges": [],
            "cfg_block_statements": [],
        }

        if not tree or not self.ast_parser:
            return result

        if isinstance(tree, dict):
            extracted_data = tree.get("extracted_data")

            if not extracted_data:
                actual_tree = tree.get("tree") if tree.get("type") == "semantic_ast" else tree
                if isinstance(actual_tree, dict):
                    extracted_data = actual_tree.get("extracted_data")

            if extracted_data and isinstance(extracted_data, dict):
                logger.debug(f"{file_info['path']}: Using Phase 5 extracted_data")
                logger.debug(f"Functions: {len(extracted_data.get('functions', []))}")
                logger.debug(f"Classes: {len(extracted_data.get('classes', []))}")
                logger.debug(f"Calls: {len(extracted_data.get('calls', []))}")

                for key in [
                    "assignments",
                    "returns",
                    "object_literals",
                    "variable_usage",
                    "class_properties",
                    "env_var_usage",
                    "orm_relationships",
                    "api_endpoints",
                ]:
                    if key in extracted_data:
                        result[key] = extracted_data[key]
                        if os.environ.get("THEAUDITOR_DEBUG") and key in (
                            "class_properties",
                            "env_var_usage",
                            "orm_relationships",
                        ):
                            logger.debug(
                                f"Mapped {len(extracted_data[key])} {key} for {file_info['path']}"
                            )

                if "function_call_args" in extracted_data:
                    result["function_calls"] = extracted_data["function_call_args"]

                key_mappings = {
                    "import_styles": "import_styles",
                    "refs": "refs",
                    "react_components": "react_components",
                    "react_hooks": "react_hooks",
                    "react_component_hooks": "react_component_hooks",
                    "react_hook_dependencies": "react_hook_dependencies",
                    "vue_components": "vue_components",
                    "vue_hooks": "vue_hooks",
                    "vue_directives": "vue_directives",
                    "vue_provide_inject": "vue_provide_inject",
                    "vue_component_props": "vue_component_props",
                    "vue_component_emits": "vue_component_emits",
                    "vue_component_setup_returns": "vue_component_setup_returns",
                    "orm_queries": "orm_queries",
                    "middleware_chains": "middleware_chains",
                    "validation_calls": "validation_calls",
                    "cdk_constructs": "cdk_constructs",
                    "cdk_construct_properties": "cdk_construct_properties",
                    "angular_component_styles": "angular_component_styles",
                    "angular_module_declarations": "angular_module_declarations",
                    "angular_module_imports": "angular_module_imports",
                    "angular_module_providers": "angular_module_providers",
                    "angular_module_exports": "angular_module_exports",
                    "func_params": "func_params",
                    "func_decorators": "func_decorators",
                    "func_decorator_args": "func_decorator_args",
                    "func_param_decorators": "func_param_decorators",
                    "class_decorators": "class_decorators",
                    "class_decorator_args": "class_decorator_args",
                    "import_specifiers": "import_specifiers",
                    "import_style_names": "import_style_names",
                    "sequelize_model_fields": "sequelize_model_fields",
                    "jwt_patterns": "jwt_patterns",
                    "cfg_blocks": "cfg_blocks",
                    "cfg_edges": "cfg_edges",
                    "cfg_block_statements": "cfg_block_statements",
                    "graphql_resolver_params": "graphql_resolver_params",
                    "assignment_source_vars": "assignment_source_vars",
                    "return_source_vars": "return_source_vars",
                    "frontend_api_calls": "frontend_api_calls",
                }

                for js_key, python_key in key_mappings.items():
                    if js_key in extracted_data:
                        result[python_key] = extracted_data[js_key]

                if "sql_queries" in extracted_data:
                    parsed_queries = []
                    for query in extracted_data["sql_queries"]:
                        try:
                            parsed = parse_sql_query(query["query_text"])
                        except Exception as e:
                            logger.warning(
                                f"SQL parse error in {file_info['path']} line {query.get('line', '?')}: {e}"
                            )
                            continue
                        if not parsed:
                            continue

                        command, tables = parsed

                        extraction_source = self._determine_sql_source(file_info["path"], "query")

                        parsed_queries.append(
                            {
                                "line": query["line"],
                                "query_text": query["query_text"],
                                "command": command,
                                "tables": tables,
                                "extraction_source": extraction_source,
                            }
                        )

                    result["sql_queries"] = parsed_queries

                if "functions" in extracted_data:
                    for func in extracted_data["functions"]:
                        if func.get("type_annotation") or func.get("return_type"):
                            result["type_annotations"].append(
                                {
                                    "line": func.get("line", 0),
                                    "column": func.get("col", 0),
                                    "symbol_name": func.get("name", ""),
                                    "symbol_kind": "function",
                                    "language": "typescript",
                                    "type_annotation": func.get("type_annotation"),
                                    "is_any": func.get("is_any", False),
                                    "is_unknown": func.get("is_unknown", False),
                                    "is_generic": func.get("is_generic", False),
                                    "has_type_params": func.get("has_type_params", False),
                                    "type_params": func.get("type_params"),
                                    "return_type": func.get("return_type"),
                                    "extends_type": func.get("extends_type"),
                                }
                            )

                        symbol_entry = {
                            "name": func.get("name", ""),
                            "type": "function",
                            "line": func.get("line", 0),
                            "col": func.get("col", 0),
                        }

                        for key in (
                            "type_annotation",
                            "return_type",
                            "type_params",
                            "has_type_params",
                            "is_any",
                            "is_unknown",
                            "is_generic",
                            "extends_type",
                            "parameters",
                        ):
                            if key in func:
                                symbol_entry[key] = func[key]
                        result["symbols"].append(symbol_entry)

                if "calls" in extracted_data:
                    for call in extracted_data["calls"]:
                        result["symbols"].append(
                            {
                                "name": call.get("name", ""),
                                "type": call.get("type", "call"),
                                "line": call.get("line", 0),
                                "col": call.get("col", 0),
                            }
                        )

                if "classes" in extracted_data:
                    for cls in extracted_data["classes"]:
                        if (
                            cls.get("type_annotation")
                            or cls.get("extends_type")
                            or cls.get("type_params")
                        ):
                            result["type_annotations"].append(
                                {
                                    "line": cls.get("line", 0),
                                    "column": cls.get("col", 0),
                                    "symbol_name": cls.get("name", ""),
                                    "symbol_kind": "class",
                                    "language": "typescript",
                                    "type_annotation": cls.get("type_annotation"),
                                    "is_any": cls.get("is_any", False),
                                    "is_unknown": cls.get("is_unknown", False),
                                    "is_generic": cls.get("is_generic", False),
                                    "has_type_params": cls.get("has_type_params", False),
                                    "type_params": cls.get("type_params"),
                                    "return_type": None,
                                    "extends_type": cls.get("extends_type"),
                                }
                            )

                        symbol_entry = {
                            "name": cls.get("name", ""),
                            "type": "class",
                            "line": cls.get("line", 0),
                            "col": cls.get("col", 0),
                        }

                        result["symbols"].append(symbol_entry)

                if "interfaces" in extracted_data:
                    for iface in extracted_data["interfaces"]:
                        symbol_entry = {
                            "name": iface.get("name", ""),
                            "type": "interface",
                            "line": iface.get("line", 0),
                            "col": iface.get("col", 0),
                        }
                        result["symbols"].append(symbol_entry)

                sequelize_models = extracted_data.get("sequelize_models", [])
                if sequelize_models:
                    result["sequelize_models"].extend(sequelize_models)

                sequelize_associations = extracted_data.get("sequelize_associations", [])
                if sequelize_associations:
                    result["sequelize_associations"].extend(sequelize_associations)

                bullmq_queues = extracted_data.get("bullmq_queues", [])
                if bullmq_queues:
                    result["bullmq_queues"].extend(bullmq_queues)

                bullmq_workers = extracted_data.get("bullmq_workers", [])
                if bullmq_workers:
                    result["bullmq_workers"].extend(bullmq_workers)

                angular_components = extracted_data.get("angular_components", [])
                if angular_components:
                    result["angular_components"].extend(angular_components)

                angular_services = extracted_data.get("angular_services", [])
                if angular_services:
                    result["angular_services"].extend(angular_services)

                angular_modules = extracted_data.get("angular_modules", [])
                if angular_modules:
                    result["angular_modules"].extend(angular_modules)

                angular_guards = extracted_data.get("angular_guards", [])
                if angular_guards:
                    result["angular_guards"].extend(angular_guards)

                di_injections = extracted_data.get("di_injections", [])
                if di_injections:
                    result["di_injections"].extend(di_injections)

        imports_data = []
        if isinstance(tree, dict):
            extracted_data = tree.get("extracted_data")
            if not extracted_data and tree.get("type") == "semantic_ast":
                actual_tree = tree.get("tree")
                if isinstance(actual_tree, dict):
                    extracted_data = actual_tree.get("extracted_data")
            if extracted_data and isinstance(extracted_data, dict):
                imports_data = extracted_data.get("imports", [])

        normalized_imports = []
        for imp in imports_data:
            if not isinstance(imp, dict):
                normalized_imports.append(imp)
                continue

            specifiers = imp.get("specifiers") or []
            namespace = imp.get("namespace")
            default = imp.get("default")
            names = imp.get("names")

            extracted_names = []
            for spec in specifiers:
                if isinstance(spec, dict):
                    if spec.get("isNamespace") and not namespace:
                        namespace = spec.get("name")
                    if spec.get("isDefault") and not default:
                        default = spec.get("name")
                    if spec.get("isNamed") and spec.get("name"):
                        extracted_names.append(spec.get("name"))
                elif isinstance(spec, str):
                    extracted_names.append(spec)

            if names is None:
                names = extracted_names
            elif extracted_names:
                names = list(dict.fromkeys(list(names) + extracted_names))

            if names is None:
                names = []

            imp["namespace"] = namespace
            imp["default"] = default
            imp["names"] = names

            if not imp.get("target") and imp.get("module"):
                imp["target"] = imp.get("module")

            if not imp.get("text"):
                module_ref = imp.get("target") or imp.get("module") or ""
                parts = []
                if default:
                    parts.append(default)
                if namespace:
                    parts.append(f"* as {namespace}")
                if names:
                    parts.append("{ " + ", ".join(names) + " }")

                if parts:
                    imp["text"] = f"import {', '.join(parts)} from '{module_ref}'"
                else:
                    imp["text"] = f"import '{module_ref}'"

            normalized_imports.append(imp)

        imports_data = normalized_imports

        if imports_data:
            for imp in imports_data:
                module = imp.get("target", imp.get("module"))
                if module:
                    kind = imp.get("source", imp.get("kind", "import"))
                    line = imp.get("line", 0)
                    result["imports"].append((kind, module, line))
            logger.debug(
                f"JS extractor: Converted {len(result['imports'])} imports to result['imports']"
            )

            if not result.get("import_styles"):
                result["import_styles"] = self._analyze_import_styles(
                    imports_data, file_info["path"]
                )

        result["router_mounts"] = self._extract_router_mounts(
            result.get("function_calls", []), file_info.get("path", "")
        )

        if "_extraction_manifest" in result:
            node_manifest = result["_extraction_manifest"]

            first_value = next(iter(node_manifest.values()), None) if node_manifest else None
            if isinstance(first_value, dict) and "tx_id" in first_value:
                logger.debug("Using Node-generated manifest (new architecture)")

                node_manifest["_total"] = sum(
                    v.get("count", 0)
                    for v in node_manifest.values()
                    if isinstance(v, dict) and not str(v).startswith("_")
                )
                node_manifest["_timestamp"] = datetime.utcnow().isoformat()
                node_manifest["_file"] = file_info.get("path", "unknown")
                return result

        logger.debug("Building manifest from Node output (Python-side)")
        result = FidelityToken.attach_manifest(result)

        return result

    def _analyze_import_styles(self, imports: list[dict], file_path: str) -> list[dict]:
        """Analyze import statements to determine import style."""
        import_styles = []

        for imp in imports:
            target = imp.get("target", "")
            if not target:
                continue

            line = imp.get("line", 0)

            import_style = None
            imported_names = None
            alias_name = None
            full_statement = imp.get("text", "")

            if imp.get("namespace"):
                import_style = "namespace"
                alias_name = imp.get("namespace")

            elif imp.get("names"):
                import_style = "named"
                imported_names = imp.get("names", [])

            elif imp.get("default"):
                import_style = "default"
                alias_name = imp.get("default")

            elif not imp.get("namespace") and not imp.get("names") and not imp.get("default"):
                import_style = "side-effect"

            if import_style:
                import_styles.append(
                    {
                        "line": line,
                        "package": target,
                        "import_style": import_style,
                        "imported_names": imported_names,
                        "alias_name": alias_name,
                        "full_statement": full_statement[:200] if full_statement else None,
                    }
                )

        return import_styles

    def _determine_sql_source(self, file_path: str, method_name: str) -> str:
        """Determine extraction source category for SQL query."""
        file_path_lower = file_path.lower()

        if "migration" in file_path_lower or "migrate" in file_path_lower:
            return "migration_file"

        if file_path.endswith(".sql") or "schema" in file_path_lower:
            return "migration_file"

        orm_methods = frozenset(
            [
                "findAll",
                "findOne",
                "findByPk",
                "create",
                "update",
                "destroy",
                "findMany",
                "findUnique",
                "findFirst",
                "upsert",
                "createMany",
                "find",
                "save",
                "remove",
                "createQueryBuilder",
                "getRepository",
            ]
        )

        if method_name in orm_methods:
            return "orm_query"

        return "code_execute"

    def _extract_router_mounts(self, function_calls: list[dict], file_path: str) -> list[dict]:
        """Extract router.use() mount statements from function calls."""
        mounts = []

        mounts_by_line = {}

        for call in function_calls:
            callee = call.get("callee_function", "")

            if not callee.endswith(".use"):
                continue

            line = call.get("line", 0)

            if line not in mounts_by_line:
                mounts_by_line[line] = {
                    "file": file_path,
                    "line": line,
                    "mount_path_expr": None,
                    "router_variable": None,
                    "is_literal": False,
                }

            mount_entry = mounts_by_line[line]

            if call.get("argument_index") == 0:
                arg_expr = call.get("argument_expr", "")

                if not arg_expr:
                    continue

                if arg_expr.startswith('"') or arg_expr.startswith("'"):
                    mount_entry["mount_path_expr"] = arg_expr.strip("\"'")
                    mount_entry["is_literal"] = True

                elif arg_expr.startswith("`"):
                    mount_entry["mount_path_expr"] = arg_expr
                    mount_entry["is_literal"] = False

                else:
                    mount_entry["mount_path_expr"] = arg_expr
                    mount_entry["is_literal"] = False

            elif call.get("argument_index") == 1:
                arg_expr = call.get("argument_expr", "")
                if arg_expr:
                    mount_entry["router_variable"] = arg_expr

        for mount in mounts_by_line.values():
            if mount["mount_path_expr"] and mount["router_variable"]:
                mounts.append(mount)

        return mounts
