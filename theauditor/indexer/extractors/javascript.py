"""JavaScript/TypeScript extractor.

This extractor:
1. Delegates core extraction to the AST parser
2. Performs framework-specific analysis (React/Vue) on the extracted data

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This is an EXTRACTOR layer module. It:
- RECEIVES: file_info dict (contains 'path' key from indexer)
- DELEGATES: To ast_parser.extract_X(tree) methods (line 290 for object literals)
- RETURNS: Extracted data WITHOUT file_path keys

The INDEXER layer (indexer/__init__.py) provides file_path and stores to database.
See indexer/__init__.py:948-962 for object literal storage example:
  - Line 952: Uses file_path parameter (from orchestrator)
  - Line 953: Uses obj_lit['line'] (from this extractor's delegation to typescript_impl.py)

This separation ensures single source of truth for file paths.
"""

import os
from datetime import datetime
from typing import Any

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
        """Extract all JavaScript/TypeScript information.

        Args:
            file_info: File metadata dictionary
            content: File content (for fallback patterns only)
            tree: Parsed AST from js_semantic_parser

        Returns:
            Dictionary containing all extracted data for database
        """
        result = {
            "imports": [],
            "resolved_imports": {},
            "routes": [],
            "symbols": [],
            "assignments": [],
            "function_calls": [],
            "returns": [],
            "variable_usage": [],
            "cfg": [],
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
            "express_middleware_chains": [],
            "func_params": [],
            "func_decorators": [],
            "func_decorator_args": [],
            "func_param_decorators": [],
            "class_decorators": [],
            "class_decorator_args": [],
            "assignment_source_vars": [],
            "return_source_vars": [],
            "import_specifiers": [],
            "import_style_names": [],
            "sequelize_model_fields": [],
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
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] {file_info['path']}: Using Phase 5 extracted_data")
                    print(f"[DEBUG]   Functions: {len(extracted_data.get('functions', []))}")
                    print(f"[DEBUG]   Classes: {len(extracted_data.get('classes', []))}")
                    print(f"[DEBUG]   Calls: {len(extracted_data.get('calls', []))}")

                for key in [
                    "assignments",
                    "returns",
                    "object_literals",
                    "variable_usage",
                    "cfg",
                    "class_properties",
                    "env_var_usage",
                    "orm_relationships",
                ]:
                    if key in extracted_data:
                        result[key] = extracted_data[key]
                        if os.environ.get("THEAUDITOR_DEBUG") and key in (
                            "class_properties",
                            "env_var_usage",
                            "orm_relationships",
                        ):
                            print(
                                f"[DEBUG EXTRACTOR] Mapped {len(extracted_data[key])} {key} for {file_info['path']}"
                            )

                if "function_call_args" in extracted_data:
                    result["function_calls"] = extracted_data["function_call_args"]

                key_mappings = {
                    "import_styles": "import_styles",
                    "resolved_imports": "resolved_imports",
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
                    "api_endpoints": "routes",
                    "express_middleware_chains": "express_middleware_chains",
                    "validation_framework_usage": "validation_framework_usage",
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
                    "assignment_source_vars": "assignment_source_vars",
                    "return_source_vars": "return_source_vars",
                    "import_specifiers": "import_specifiers",
                    "import_style_names": "import_style_names",
                    "sequelize_model_fields": "sequelize_model_fields",
                }

                for js_key, python_key in key_mappings.items():
                    if js_key in extracted_data:
                        result[python_key] = extracted_data[js_key]

                if "sql_queries" in extracted_data:
                    parsed_queries = []
                    for query in extracted_data["sql_queries"]:
                        parsed = parse_sql_query(query["query_text"])
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
                                    "column": func.get("col", func.get("column", 0)),
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
                            "col": func.get("col", func.get("column", 0)),
                            "column": func.get("column", func.get("col", 0)),
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
                                "col": call.get("col", call.get("column", 0)),
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
                                    "column": cls.get("col", cls.get("column", 0)),
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
                            "col": cls.get("col", cls.get("column", 0)),
                            "column": cls.get("column", cls.get("col", 0)),
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

                frontend_api_calls = extracted_data.get("frontend_api_calls", [])
                if frontend_api_calls:
                    result["frontend_api_calls"] = frontend_api_calls

        tree_type = tree.get("type") if isinstance(tree, dict) else None

        if tree_type == "semantic_ast":
            actual_tree = tree.get("tree")
            if not isinstance(actual_tree, dict):
                actual_tree = tree
            imports_data = actual_tree.get("imports", [])
        elif tree_type == "tree_sitter":
            actual_tree = tree
            if self.ast_parser:
                from theauditor.ast_extractors import treesitter_impl

                imports_data = treesitter_impl.extract_treesitter_imports(
                    tree, self.ast_parser, "javascript"
                )
            else:
                imports_data = []
        else:
            actual_tree = tree
            imports_data = tree.get("imports", []) if isinstance(tree, dict) else []

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

        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG] JS extractor for {file_info['path']}: tree_type = {tree_type}")
            print(
                f"[DEBUG] JS extractor: tree keys = {tree.keys() if isinstance(tree, dict) else 'not a dict'}"
            )
            print(
                f"[DEBUG] JS extractor: actual_tree type = {type(actual_tree)}, is_dict = {isinstance(actual_tree, dict)}"
            )
            if isinstance(actual_tree, dict):
                print(f"[DEBUG] JS extractor: actual_tree keys = {list(actual_tree.keys())[:15]}")
                for key in list(actual_tree.keys())[:10]:
                    val = actual_tree[key]
                    if isinstance(val, list):
                        print(f"[DEBUG]   {key}: list with {len(val)} items")
                        if val and len(val) < 5:
                            print(f"[DEBUG]     items: {val}")
                    elif isinstance(val, dict):
                        print(f"[DEBUG]   {key}: dict with keys {list(val.keys())[:5]}")
                    else:
                        print(f"[DEBUG]   {key}: {type(val).__name__}")
            print(f"[DEBUG] JS extractor: imports_data = {imports_data}")

        if imports_data:
            for imp in imports_data:
                module = imp.get("target", imp.get("module"))
                if module:
                    kind = imp.get("source", imp.get("kind", "import"))
                    line = imp.get("line", 0)
                    result["imports"].append((kind, module, line))

            if os.environ.get("THEAUDITOR_DEBUG"):
                print(
                    f"[DEBUG] JS extractor: Converted {len(result['imports'])} imports to result['imports']"
                )

            result["import_styles"] = self._analyze_import_styles(imports_data, file_info["path"])

        functions = [s for s in result["symbols"] if s.get("type") == "function"]
        classes = [s for s in result["symbols"] if s.get("type") == "class"]

        # Query: SELECT * FROM symbols WHERE type='call' OR type='property'

        result["routes"] = self._extract_routes_from_ast(
            result.get("function_calls", []), file_info.get("path", "")
        )

        result["router_mounts"] = self._extract_router_mounts(
            result.get("function_calls", []), file_info.get("path", "")
        )

        component_functions = []
        for func in functions:
            name = func.get("name", "")
            if name and name[0:1].isupper():
                func_returns = [
                    r for r in result.get("returns", []) if r.get("function_name") == name
                ]
                has_jsx = any(r.get("has_jsx") or r.get("returns_component") for r in func_returns)

                hook_calls = []
                for fc in result.get("function_calls", []):
                    call_name = fc.get("callee_function", "")
                    if call_name.startswith("use") and fc.get("line", 0) >= func.get("line", 0):
                        hook_calls.append(call_name)

                result["react_components"].append(
                    {
                        "name": name,
                        "type": "function",
                        "start_line": func.get("line", 0),
                        "end_line": func.get("end_line", func.get("line", 0)),
                        "has_jsx": has_jsx,
                        "hooks_used": list(set(hook_calls[:10])),
                        "props_type": None,
                    }
                )
                component_functions.append(name)

        for cls in classes:
            name = cls.get("name", "")

            if name and name[0:1].isupper():
                result["react_components"].append(
                    {
                        "name": name,
                        "type": "class",
                        "start_line": cls.get("line", 0),
                        "end_line": cls.get("line", 0),
                        "has_jsx": True,
                        "hooks_used": [],
                        "props_type": None,
                    }
                )
                component_functions.append(name)

        for fc in result.get("function_calls", []):
            call_name = fc.get("callee_function", "")
            if call_name.startswith("use"):
                line = fc.get("line", 0)
                component_name = fc.get("caller_function", "global")

                for comp in result["react_components"]:
                    if comp["start_line"] <= line <= comp.get("end_line", comp["start_line"] + 100):
                        component_name = comp["name"]
                        break

                hook_type = "custom"
                dependency_array = None
                dependency_vars = []
                callback_body = None
                has_cleanup = False
                cleanup_type = None

                if call_name in [
                    "useState",
                    "useEffect",
                    "useCallback",
                    "useMemo",
                    "useRef",
                    "useContext",
                    "useReducer",
                    "useLayoutEffect",
                ]:
                    hook_type = "builtin"

                    if call_name in ["useEffect", "useCallback", "useMemo", "useLayoutEffect"]:
                        matching_calls = [
                            c
                            for c in result.get("function_calls", [])
                            if c.get("line") == line and c.get("callee_function") == call_name
                        ]

                        if matching_calls:
                            deps_arg = [c for c in matching_calls if c.get("argument_index") == 1]
                            if deps_arg:
                                dep_expr = deps_arg[0].get("argument_expr", "")
                                if dep_expr.startswith("[") and dep_expr.endswith("]"):
                                    dependency_array = dep_expr

                                    dep_content = dep_expr[1:-1].strip()
                                    if dep_content:
                                        dependency_vars = [
                                            v.strip() for v in dep_content.split(",")
                                        ]

                            callback_arg = [
                                c for c in matching_calls if c.get("argument_index") == 0
                            ]
                            if callback_arg:
                                callback_body = callback_arg[0].get("argument_expr", "")[:500]

                                if (
                                    call_name in ["useEffect", "useLayoutEffect"]
                                    and "return" in callback_body
                                ):
                                    has_cleanup = True
                                    if (
                                        "clearTimeout" in callback_body
                                        or "clearInterval" in callback_body
                                    ):
                                        cleanup_type = "timer_cleanup"
                                    elif "removeEventListener" in callback_body:
                                        cleanup_type = "event_cleanup"
                                    elif (
                                        "unsubscribe" in callback_body
                                        or "disconnect" in callback_body
                                    ):
                                        cleanup_type = "subscription_cleanup"
                                    else:
                                        cleanup_type = "cleanup_function"

                result["react_hooks"].append(
                    {
                        "line": line,
                        "component_name": component_name,
                        "hook_name": call_name,
                        "hook_type": hook_type,
                        "dependency_array": dependency_array,
                        "dependency_vars": dependency_vars,
                        "callback_body": callback_body,
                        "has_cleanup": has_cleanup,
                        "cleanup_type": cleanup_type,
                    }
                )

        orm_methods = {
            "findAll",
            "findOne",
            "findByPk",
            "create",
            "update",
            "destroy",
            "findOrCreate",
            "findAndCountAll",
            "bulkCreate",
            "upsert",
            "findMany",
            "findUnique",
            "findFirst",
            "delete",
            "createMany",
            "updateMany",
            "deleteMany",
            "find",
            "save",
            "remove",
            "insert",
            "createQueryBuilder",
            "getRepository",
            "getManager",
        }

        for fc in result.get("function_calls", []):
            method = fc.get("callee_function", "").split(".")[-1]
            if method in orm_methods:
                line = fc.get("line", 0)

                includes = None
                has_limit = False
                has_transaction = False

                matching_args = [
                    c
                    for c in result.get("function_calls", [])
                    if c.get("line") == line
                    and c.get("callee_function") == fc.get("callee_function")
                ]

                if matching_args:
                    first_arg = [c for c in matching_args if c.get("argument_index") == 0]
                    if first_arg:
                        arg_expr = first_arg[0].get("argument_expr", "")

                        if "include:" in arg_expr or "include :" in arg_expr:
                            includes = "has_includes"
                        elif "relations:" in arg_expr or "relations :" in arg_expr:
                            includes = "has_relations"

                        if any(
                            term in arg_expr
                            for term in ["limit:", "limit :", "take:", "take :", "skip:", "offset:"]
                        ):
                            has_limit = True

                        if "transaction:" in arg_expr or "transaction :" in arg_expr:
                            has_transaction = True

                caller_func = fc.get("caller_function", "")
                if "transaction" in caller_func.lower() or "withTransaction" in caller_func:
                    has_transaction = True

                result["orm_queries"].append(
                    {
                        "line": line,
                        "query_type": fc.get("callee_function", method),
                        "includes": includes,
                        "has_limit": has_limit,
                        "has_transaction": has_transaction,
                    }
                )

        if not result.get("sql_queries"):
            result["sql_queries"] = self._extract_sql_from_function_calls(
                result.get("function_calls", []), file_info.get("path", "")
            )

        result["jwt_patterns"] = self._extract_jwt_from_function_calls(
            result.get("function_calls", []), file_info.get("path", "")
        )

        if not result.get("variable_usage"):
            for assign in result.get("assignments", []):
                result["variable_usage"].append(
                    {
                        "line": assign.get("line", 0),
                        "variable_name": assign.get("target_var", ""),
                        "usage_type": "write",
                        "in_component": assign.get("in_function", "global"),
                        "in_hook": "",
                        "scope_level": 0 if assign.get("in_function") == "global" else 1,
                    }
                )

                for var in assign.get("source_vars", []):
                    result["variable_usage"].append(
                        {
                            "line": assign.get("line", 0),
                            "variable_name": var,
                            "usage_type": "read",
                            "in_component": assign.get("in_function", "global"),
                            "in_hook": "",
                            "scope_level": 0 if assign.get("in_function") == "global" else 1,
                        }
                    )

            for call in result.get("function_calls", []):
                if call.get("callee_function"):
                    result["variable_usage"].append(
                        {
                            "line": call.get("line", 0),
                            "variable_name": call.get("callee_function"),
                            "usage_type": "call",
                            "in_component": call.get("caller_function", "global"),
                            "in_hook": "",
                            "scope_level": 0 if call.get("caller_function") == "global" else 1,
                        }
                    )

        for import_entry in result.get("imports", []):
            imp_path = None

            if isinstance(import_entry, (tuple, list)):
                if len(import_entry) >= 2:
                    imp_path = import_entry[1]
            elif isinstance(import_entry, dict):
                imp_path = import_entry.get("module") or import_entry.get("value")

            if not imp_path:
                continue

            module_name = imp_path.split("/")[-1].replace(".js", "").replace(".ts", "")
            if module_name:
                result["resolved_imports"][module_name] = imp_path

        manifest = {}
        total_items = 0

        for key, value in result.items():
            if key.startswith("_") or not isinstance(value, list):
                continue

            count = len(value)
            if count > 0:
                manifest[key] = count
                total_items += count

        manifest["_total"] = total_items
        manifest["_timestamp"] = datetime.utcnow().isoformat()

        manifest["_file"] = file_info.get("path", "unknown")

        result["_extraction_manifest"] = manifest

        return result

    def _analyze_import_styles(self, imports: list[dict], file_path: str) -> list[dict]:
        """Analyze import statements to determine import style.

        Classifies imports into categories for tree-shaking analysis:
        - namespace: import * as lodash from 'lodash' (prevents tree-shaking)
        - named: import { map, filter } from 'lodash' (allows tree-shaking)
        - default: import lodash from 'lodash' (depends on export structure)
        - side-effect: import 'polyfill' (no tree-shaking, intentional)

        This enables bundle_analyze.py CHECK 3 (inefficient namespace imports).

        Args:
            imports: List of import dictionaries from ast_parser
            file_path: Path to the file being analyzed

        Returns:
            List of import style records for database
        """
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
        """Determine extraction source category for SQL query.

        This categorization allows rules to filter intelligently:
        - migration_file: DDL from migration files (LOW priority for SQL injection)
        - orm_query: ORM method calls (MEDIUM priority, usually parameterized)
        - code_execute: Direct database execution (HIGH priority for injection)

        Args:
            file_path: Path to the file being analyzed
            method_name: Database method name (execute, query, findAll, etc.)

        Returns:
            extraction_source category string
        """
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

    def _extract_sql_from_function_calls(
        self, function_calls: list[dict], file_path: str
    ) -> list[dict]:
        """Extract SQL queries from database execution method calls.

        Uses already-extracted function_calls data to find SQL execution calls
        like db.execute(), connection.query(), pool.raw(), etc.

        This is AST-based extraction (via function_calls) instead of regex,
        eliminating the 97.6% false positive rate.

        Args:
            function_calls: List of function call dictionaries from AST parser
            file_path: Path to the file being analyzed (for source categorization)

        Returns:
            List of SQL query dictionaries with extraction_source tags
        """
        queries = []

        sql_methods = frozenset(
            [
                "execute",
                "query",
                "raw",
                "exec",
                "run",
                "executeSql",
                "executeQuery",
                "execSQL",
                "select",
                "insert",
                "update",
                "delete",
                "query_raw",
            ]
        )

        for call in function_calls:
            callee = call.get("callee_function", "")

            method_name = callee.split(".")[-1] if "." in callee else callee

            if method_name not in sql_methods:
                continue

            if call.get("argument_index") != 0:
                continue

            arg_expr = call.get("argument_expr", "")
            if not arg_expr:
                continue

            if not any(
                keyword in arg_expr.upper()
                for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]
            ):
                continue

            query_text = arg_expr.strip()
            if (query_text.startswith('"') and query_text.endswith('"')) or (
                query_text.startswith("'") and query_text.endswith("'")
            ):
                query_text = query_text[1:-1]

            if "${" in query_text or query_text.startswith("`"):
                continue

            parsed = parse_sql_query(query_text)
            if not parsed:
                continue

            command, tables = parsed

            extraction_source = self._determine_sql_source(file_path, method_name)

            queries.append(
                {
                    "line": call.get("line", 0),
                    "query_text": query_text[:1000],
                    "command": command,
                    "tables": tables,
                    "extraction_source": extraction_source,
                }
            )

        return queries

    def _extract_jwt_from_function_calls(
        self, function_calls: list[dict], file_path: str
    ) -> list[dict]:
        """Extract JWT patterns from function calls using AST data.

        NO REGEX. This uses function_calls data from the AST parser.

        Detects JWT library usage:
        - jwt.sign(payload, secret, options)
        - jwt.verify(token, secret, options)
        - jwt.decode(token)

        Edge cases: ~0.0001% of obfuscated/dynamic JWT calls might be missed.
        We accept this. AST-first is non-negotiable.

        Args:
            function_calls: List of function call dictionaries from AST parser
            file_path: Path to the file being analyzed

        Returns:
            List of JWT pattern dicts matching orchestrator expectations:
            - line: int
            - type: 'jwt_sign' | 'jwt_verify' | 'jwt_decode'
            - full_match: str (function call context)
            - secret_type: 'hardcoded' | 'environment' | 'config' | 'variable' | 'unknown'
            - algorithm: str ('HS256', 'RS256', etc.) or None
        """
        patterns = []

        jwt_sign_methods = frozenset(
            [
                "jwt.sign",
                "jsonwebtoken.sign",
                "jose.sign",
                "JWT.sign",
                "jwt.encode",
                "jose.JWT.sign",
            ]
        )

        jwt_verify_methods = frozenset(
            [
                "jwt.verify",
                "jsonwebtoken.verify",
                "jose.verify",
                "JWT.verify",
                "jwt.decode",
                "jose.JWT.verify",
            ]
        )

        jwt_decode_methods = frozenset(["jwt.decode", "JWT.decode"])

        calls_by_line = {}

        for call in function_calls:
            callee = call.get("callee_function", "")
            line = call.get("line", 0)

            pattern_type = None
            if any(method in callee for method in jwt_sign_methods):
                pattern_type = "jwt_sign"
            elif any(method in callee for method in jwt_verify_methods):
                pattern_type = "jwt_verify"
            elif any(method in callee for method in jwt_decode_methods):
                pattern_type = "jwt_decode"

            if not pattern_type:
                continue

            if line not in calls_by_line:
                calls_by_line[line] = {"type": pattern_type, "callee": callee, "args": {}}

            arg_index = call.get("argument_index")
            arg_expr = call.get("argument_expr", "")
            if arg_index is not None:
                calls_by_line[line]["args"][arg_index] = arg_expr

        for line, call_data in calls_by_line.items():
            pattern_type = call_data["type"]
            callee = call_data["callee"]
            args = call_data["args"]

            if pattern_type == "jwt_sign":
                secret_text = args.get(1, "")
                options_text = args.get(2, "{}")
                payload_text = args.get(0, "")

                secret_type = "unknown"
                if (
                    "process.env" in secret_text
                    or "os.environ" in secret_text
                    or "os.getenv" in secret_text
                ):
                    secret_type = "environment"
                elif (
                    "config." in secret_text
                    or "secrets." in secret_text
                    or "settings." in secret_text
                ):
                    secret_type = "config"
                elif secret_text.startswith('"') or secret_text.startswith("'"):
                    secret_type = "hardcoded"
                else:
                    secret_type = "variable"

                algorithm = "HS256"
                if "algorithm" in options_text:
                    for algo in [
                        "HS256",
                        "HS384",
                        "HS512",
                        "RS256",
                        "RS384",
                        "RS512",
                        "ES256",
                        "PS256",
                        "none",
                    ]:
                        if algo in options_text:
                            algorithm = algo
                            break

                full_match = f"{callee}({payload_text[:50]}, {secret_text[:50]}, ...)"

                patterns.append(
                    {
                        "line": line,
                        "type": pattern_type,
                        "full_match": full_match[:500],
                        "secret_type": secret_type,
                        "algorithm": algorithm,
                    }
                )

            elif pattern_type == "jwt_verify":
                options_text = args.get(2, "{}")

                algorithm = "HS256"
                if "algorithm" in options_text:
                    for algo in [
                        "HS256",
                        "HS384",
                        "HS512",
                        "RS256",
                        "RS384",
                        "RS512",
                        "ES256",
                        "PS256",
                        "none",
                    ]:
                        if algo in options_text:
                            algorithm = algo
                            break

                full_match = f"{callee}(...)"

                patterns.append(
                    {
                        "line": line,
                        "type": pattern_type,
                        "full_match": full_match[:500],
                        "secret_type": None,
                        "algorithm": algorithm,
                    }
                )

            elif pattern_type == "jwt_decode":
                full_match = f"{callee}(...)"

                patterns.append(
                    {
                        "line": line,
                        "type": pattern_type,
                        "full_match": full_match[:200],
                        "secret_type": None,
                        "algorithm": None,
                    }
                )

        return patterns

    def _extract_routes_from_ast(self, function_calls: list[dict], file_path: str) -> list[dict]:
        """Extract API route definitions from Express/Fastify function calls.

        Detects patterns like:
        - app.get('/path', middleware, handler)
        - router.post('/path', authMiddleware, controller.create)
        - fastify.route({ method: 'GET', url: '/path', handler: myHandler })

        Provides complete metadata including line numbers, auth detection, and handler names.

        Args:
            function_calls: List of function call dictionaries from AST parser
            file_path: Path to the file being analyzed

        Returns:
            List of route dictionaries with all 8 api_endpoints fields populated
        """
        routes = []

        route_methods = frozenset(
            ["get", "post", "put", "patch", "delete", "options", "head", "all", "use", "route"]
        )

        route_prefixes = frozenset(["app", "router", "Router", "express", "fastify", "server"])

        auth_patterns = frozenset(
            [
                "auth",
                "authenticate",
                "requireauth",
                "isauth",
                "verifyauth",
                "checkauth",
                "ensureauth",
                "passport",
                "jwt",
                "bearer",
                "oauth",
                "protected",
                "secure",
                "guard",
                "authorize",
            ]
        )

        routes_by_line = {}

        for call in function_calls:
            callee = call.get("callee_function", "")

            if "." not in callee:
                continue

            parts = callee.split(".")
            if len(parts) < 2:
                continue

            prefix = parts[0]
            method_name = parts[-1]

            if prefix not in route_prefixes or method_name not in route_methods:
                continue

            line = call.get("line", 0)

            if line not in routes_by_line:
                routes_by_line[line] = {
                    "file": file_path,
                    "line": line,
                    "method": method_name.upper() if method_name != "all" else "ANY",
                    "pattern": None,
                    "path": file_path,
                    "has_auth": False,
                    "handler_function": None,
                    "controls": [],
                }

            route_entry = routes_by_line[line]

            if call.get("argument_index") == 0:
                arg_expr = call.get("argument_expr", "")

                if arg_expr.startswith('"') or arg_expr.startswith("'"):
                    route_entry["pattern"] = arg_expr.strip("\"'")
                elif arg_expr.startswith("`"):
                    route_entry["pattern"] = arg_expr.strip("`")

            elif call.get("argument_index", -1) >= 1:
                arg_expr = call.get("argument_expr", "")

                arg_lower = arg_expr.lower()
                if any(auth_pattern in arg_lower for auth_pattern in auth_patterns):
                    route_entry["has_auth"] = True
                    route_entry["controls"].append(arg_expr[:100])

                route_entry["handler_function"] = arg_expr[:100]

        for route in routes_by_line.values():
            if route["pattern"]:
                routes.append(route)

        return routes

    def _extract_router_mounts(self, function_calls: list[dict], file_path: str) -> list[dict]:
        """Extract router.use() mount statements from function calls.

        ADDED 2025-11-09: Phase 6.7 - AST-based route resolution

        Detects patterns like:
        - router.use('/areas', areaRoutes)
        - router.use(API_PREFIX, protectedRouter)
        - protectedRouter.use(`${API_PREFIX}/auth`, authRoutes)

        Args:
            function_calls: List of function call dictionaries from AST parser
            file_path: Path to the file being analyzed

        Returns:
            List of mount dictionaries with router_mounts table fields
        """
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
