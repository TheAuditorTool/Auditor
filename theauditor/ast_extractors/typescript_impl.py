"""TypeScript/JavaScript Behavioral AST Extraction Layer.

This module is Part 2 of the TypeScript implementation layer split.

RESPONSIBILITY: Behavioral Analysis (Context-Dependent Semantic Extraction)
================================================================================

Core Components:
- Assignments: Variable assignment tracking with accurate function context
- Function Parameters: Parameter extraction for all function types
- Call Arguments: Call-site analysis with scope resolution
- Returns: Return statement analysis with JSX detection
- CFG: Control flow graph extraction and construction
- Object Literals: Object literal parsing for dynamic dispatch resolution

ARCHITECTURAL CONTRACT:
- Depends on typescript_impl_structure.py for scope mapping foundation
- Uses build_scope_map() for O(1) line-to-function lookups
- NO file_path context (3-layer architecture: INDEXER provides file paths)
- Stateful operations (requires scope context from build_scope_map)

DEPENDENCIES:
- build_scope_map: Used by 4/7 extractors (assignments, calls_with_args, returns, object_literals)
- _canonical_callee_from_call: Call name resolution (calls_with_args, object_literals)
- _strip_comment_prefix: Text cleaning (calls_with_args)
- detect_jsx_in_node: JSX detection (returns)

CONSUMERS:
- ast_extractors/__init__.py (orchestrator router)
- Taint analysis (uses function_call_args, assignments, returns)
- Pattern rules (uses all behavioral data)
- CFG analysis (uses cfg_blocks, cfg_edges)
"""

import os
import sys
from typing import Any

from .base import extract_vars_from_typescript_node
from .typescript_impl_structure import (
    _canonical_callee_from_call,
    _strip_comment_prefix,
    build_scope_map,
    detect_jsx_in_node,
)


def extract_typescript_assignments(tree: dict, parser_self) -> list[dict[str, Any]]:
    """Extract ALL assignment patterns from TypeScript semantic AST, including destructuring.

    CRITICAL FIX: Now uses line-based scope mapping for accurate function context.
    """
    assignments = []

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys

            print("[AST_DEBUG] extract_typescript_assignments: No success in tree", file=sys.stderr)
        return assignments

    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "assignments" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys

            print(
                f"[DEBUG] extract_typescript_assignments: Using PRE-EXTRACTED data ({len(extracted_data['assignments'])} assignments)",
                file=sys.stderr,
            )
        return extracted_data["assignments"]

    ast_root = actual_tree.get("ast", {})
    scope_map = build_scope_map(ast_root)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        print(
            "[AST_DEBUG] extract_typescript_assignments: Starting extraction with scope map",
            file=sys.stderr,
        )

    def traverse(node, depth=0):
        if depth > 100 or not isinstance(node, dict):
            return

        try:
            kind = node.get("kind", "")

            if os.environ.get("THEAUDITOR_DEBUG"):
                import sys

                if depth < 5:
                    print(f"[AST_DEBUG] Depth {depth}: kind='{kind}'", file=sys.stderr)
                if (
                    "Variable" in kind
                    or "Assignment" in kind
                    or "Binary" in kind
                    or "=" in str(node.get("text", ""))
                ):
                    print(
                        f"[AST_DEBUG] *** POTENTIAL ASSIGNMENT at depth {depth}: {kind}, text={str(node.get('text', ''))[:50]} ***",
                        file=sys.stderr,
                    )

            if kind in ["VariableDeclaration", "BinaryExpression"]:
                is_assignment = True
                if kind == "BinaryExpression":
                    op_token = node.get("operatorToken", {})
                    if not (isinstance(op_token, dict) and op_token.get("kind") == "EqualsToken"):
                        is_assignment = False

                if is_assignment:
                    if kind == "VariableDeclaration":
                        full_text = node.get("text", "")
                        if "=" in full_text:
                            parts = full_text.split("=", 1)
                            target_var = parts[0].strip()
                            source_expr = parts[1].strip()
                            if target_var and source_expr:
                                line = node.get("line", 0)

                                in_function = scope_map.get(line, "global")

                                source_vars = []

                                for child in node.get("children", []):
                                    if (
                                        isinstance(child, dict)
                                        and child.get("kind") != "Identifier"
                                    ):
                                        source_vars = extract_vars_from_typescript_node(child)
                                        break

                                if os.environ.get("THEAUDITOR_DEBUG"):
                                    import sys

                                    print(
                                        f"[AST_DEBUG] Found TS assignment: {target_var} = {source_expr[:30]}... at line {line} in {in_function}",
                                        file=sys.stderr,
                                    )
                                assignments.append(
                                    {
                                        "target_var": target_var,
                                        "source_expr": source_expr,
                                        "line": line,
                                        "in_function": in_function,
                                        "source_vars": source_vars,
                                    }
                                )
                    else:
                        target_node = node.get("left")
                        source_node = node.get("right")

                        if isinstance(target_node, dict) and isinstance(source_node, dict):
                            if target_node.get("kind") in [
                                "ObjectBindingPattern",
                                "ArrayBindingPattern",
                            ]:
                                source_expr = source_node.get("text", "unknown_source")

                                source_vars = (
                                    extract_vars_from_typescript_node(source_node)
                                    if isinstance(source_node, dict)
                                    else []
                                )

                                for element in target_node.get("elements", []):
                                    if isinstance(element, dict) and element.get("name"):
                                        target_var = element.get("name", {}).get("text")
                                        if target_var:
                                            line = element.get("line", node.get("line", 0))

                                            in_function = scope_map.get(line, "global")

                                            assignments.append(
                                                {
                                                    "target_var": target_var,
                                                    "source_expr": source_expr,
                                                    "line": line,
                                                    "in_function": in_function,
                                                    "source_vars": source_vars,
                                                }
                                            )
                            else:
                                target_var = target_node.get("text", "")
                                source_expr = source_node.get("text", "")
                                if target_var and source_expr:
                                    line = node.get("line", 0)

                                    in_function = scope_map.get(line, "global")

                                    source_vars = (
                                        extract_vars_from_typescript_node(source_node)
                                        if isinstance(source_node, dict)
                                        else []
                                    )

                                    if os.environ.get("THEAUDITOR_DEBUG"):
                                        import sys

                                        print(
                                            f"[AST_DEBUG] Found assignment: {target_var} = {source_expr[:50]}... at line {line} in {in_function}",
                                            file=sys.stderr,
                                        )
                                    assignments.append(
                                        {
                                            "target_var": target_var,
                                            "source_expr": source_expr,
                                            "line": line,
                                            "in_function": in_function,
                                            "source_vars": source_vars,
                                        }
                                    )

            for child in node.get("children", []):
                traverse(child, depth + 1)

        except Exception:
            pass

    ast_root = actual_tree.get("ast", {})
    traverse(ast_root)

    seen = set()
    deduped = []
    for a in assignments:
        key = (a["line"], a["target_var"], a["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(assignments) != len(deduped):
            print(
                f"[AST_DEBUG] Deduplication: {len(assignments)} -> {len(deduped)} assignments ({len(assignments) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )
        print(
            f"[AST_DEBUG] extract_typescript_assignments: Found {len(deduped)} unique assignments",
            file=sys.stderr,
        )
        if deduped and len(deduped) < 5:
            for a in deduped[:3]:
                print(
                    f"[AST_DEBUG]   Example: {a['target_var']} = {a['source_expr'][:30]}...",
                    file=sys.stderr,
                )

    return deduped


def extract_typescript_function_params(tree: dict, parser_self) -> dict[str, list[str]]:
    """Extract function parameters from TypeScript semantic AST."""
    debug = os.environ.get("THEAUDITOR_DEBUG")

    if debug:
        print(
            "[DEBUG typescript_impl.py:1132] extract_typescript_function_params called",
            file=sys.stderr,
        )

    func_params = {}

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        if debug:
            print(
                "[DEBUG typescript_impl.py:1132] WARNING: actual_tree invalid or not successful",
                file=sys.stderr,
            )
        return func_params

    if debug:
        print("[DEBUG typescript_impl.py:1132] Starting traverse of AST", file=sys.stderr)

    def traverse(node, depth=0):
        import sys

        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind")

        if debug and depth <= 2:
            print(
                f"[DEBUG typescript_impl.py:traverse] depth={depth}, kind={kind}", file=sys.stderr
            )

        if kind in [
            "FunctionDeclaration",
            "MethodDeclaration",
            "ArrowFunction",
            "FunctionExpression",
        ]:
            name_node = node.get("name")
            func_name = "anonymous"
            if isinstance(name_node, dict):
                func_name = name_node.get("text", "anonymous")
            elif isinstance(name_node, str):
                func_name = name_node
            elif not name_node:
                for child in node.get("children", []):
                    if isinstance(child, dict) and child.get("kind") == "Identifier":
                        func_name = child.get("text", "anonymous")
                        break

            if debug:
                print(
                    f"[DEBUG typescript_impl.py:1147] Found {kind} named '{func_name}' at line {node.get('line', '?')}",
                    file=sys.stderr,
                )

            params = []
            param_nodes = node.get("parameters", [])

            if debug:
                print(
                    f"[DEBUG typescript_impl.py:1166] param_nodes type: {type(param_nodes)}, length: {len(param_nodes) if isinstance(param_nodes, list) else 'N/A'}",
                    file=sys.stderr,
                )

            for param in param_nodes:
                if not isinstance(param, dict):
                    raise TypeError(
                        f"EXTRACTION BUG: Parameter must be dict, got {type(param).__name__}. "
                        f"Fix core_ast_extractors.js parameter serialization."
                    )

                param_name = param.get("name")
                if not isinstance(param_name, str):
                    raise TypeError(
                        f"EXTRACTION BUG: Parameter name must be str, got {type(param_name).__name__}. "
                        f"Value: {param_name}. Fix core_ast_extractors.js:338."
                    )

                if param_name:
                    params.append(param_name)

            if debug:
                print(
                    f"[DEBUG typescript_impl.py:1198] Extracted params for '{func_name}': {params}",
                    file=sys.stderr,
                )

            if func_name != "anonymous" and params:
                func_params[func_name] = params
            elif debug and func_name == "anonymous":
                print(
                    "[DEBUG typescript_impl.py:1198] Skipping anonymous function", file=sys.stderr
                )
            elif debug and not params:
                print(
                    f"[DEBUG typescript_impl.py:1198] WARNING: No params extracted for '{func_name}'",
                    file=sys.stderr,
                )

        elif kind == "PropertyDeclaration":
            initializer = node.get("initializer")

            if isinstance(initializer, dict):
                init_kind = initializer.get("kind", "")

                if init_kind in ["ArrowFunction", "FunctionExpression"]:
                    prop_name = None
                    for child in node.get("children", []):
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            prop_name = child.get("text", "")
                            break

                    params = []
                    param_nodes = initializer.get("parameters", [])

                    for param in param_nodes:
                        if not isinstance(param, dict):
                            raise TypeError(
                                f"EXTRACTION BUG: Parameter must be dict, got {type(param).__name__}. "
                                f"Fix core_ast_extractors.js parameter serialization."
                            )

                        param_name = param.get("name")
                        if not isinstance(param_name, str):
                            raise TypeError(
                                f"EXTRACTION BUG: Parameter name must be str, got {type(param_name).__name__}. "
                                f"Value: {param_name}. Fix core_ast_extractors.js:338."
                            )

                        if param_name:
                            params.append(param_name)

                    if prop_name and params:
                        func_params[prop_name] = params
                        if os.environ.get("THEAUDITOR_DEBUG"):
                            import sys

                            print(
                                f"[DEBUG] Extracted PropertyDeclaration params: {prop_name}({', '.join(params)})",
                                file=sys.stderr,
                            )

                elif init_kind == "CallExpression":
                    prop_name = None
                    for child in node.get("children", []):
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            prop_name = child.get("text", "")
                            break

                    call_children = initializer.get("children", [])
                    if len(call_children) >= 2:
                        wrapped_func = call_children[1]
                        wrapped_kind = wrapped_func.get("kind", "")

                        if wrapped_kind in ["ArrowFunction", "FunctionExpression"]:
                            params = []
                            param_nodes = wrapped_func.get("parameters", [])

                            for param in param_nodes:
                                if not isinstance(param, dict):
                                    raise TypeError(
                                        f"EXTRACTION BUG: Parameter must be dict, got {type(param).__name__}. "
                                        f"Fix core_ast_extractors.js parameter serialization."
                                    )

                                param_name = param.get("name")
                                if not isinstance(param_name, str):
                                    raise TypeError(
                                        f"EXTRACTION BUG: Parameter name must be str, got {type(param_name).__name__}. "
                                        f"Value: {param_name}. Fix core_ast_extractors.js:338."
                                    )

                                if param_name:
                                    params.append(param_name)

                            if prop_name and params:
                                func_params[prop_name] = params
                                if os.environ.get("THEAUDITOR_DEBUG"):
                                    import sys

                                    print(
                                        f"[DEBUG] Extracted wrapped PropertyDeclaration params: {prop_name}({', '.join(params)})",
                                        file=sys.stderr,
                                    )

        for child in node.get("children", []):
            traverse(child, depth + 1)

    ast_root = actual_tree.get("ast", {})

    if debug:
        print(
            f"[DEBUG typescript_impl.py:1257] ast_root type: {type(ast_root)}, is_dict: {isinstance(ast_root, dict)}",
            file=sys.stderr,
        )
        if isinstance(ast_root, dict):
            print(
                f"[DEBUG typescript_impl.py:1257] ast_root keys: {list(ast_root.keys())[:10]}",
                file=sys.stderr,
            )
            print(
                f"[DEBUG typescript_impl.py:1257] ast_root.get('kind'): {ast_root.get('kind')}",
                file=sys.stderr,
            )
        else:
            print(
                "[DEBUG typescript_impl.py:1257] WARNING: ast_root is NOT a dict!", file=sys.stderr
            )

    traverse(ast_root)

    if debug:
        print(
            f"[DEBUG typescript_impl.py:1260] FINAL RESULT: Extracted {len(func_params)} total functions with params",
            file=sys.stderr,
        )
        if func_params:
            sample = list(func_params.items())[:5]
            print(f"[DEBUG typescript_impl.py:1260] Sample functions: {sample}", file=sys.stderr)
        else:
            print(
                "[DEBUG typescript_impl.py:1260] WARNING: func_params is EMPTY - no functions with params found!",
                file=sys.stderr,
            )

    return func_params


def extract_typescript_calls_with_args(
    tree: dict, function_params: dict[str, list[str]], parser_self
) -> list[dict[str, Any]]:
    """Extract function calls with arguments from TypeScript semantic AST.

    CRITICAL FIX: Now uses line-based scope mapping instead of broken recursive tracking.
    This solves the "100% anonymous caller" problem that crippled taint analysis.
    """
    calls = []

    if os.environ.get("THEAUDITOR_DEBUG"):
        print(
            f"[DEBUG] extract_typescript_calls_with_args: tree type={type(tree)}, success={tree.get('success') if tree else 'N/A'}"
        )

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(
                "[DEBUG] extract_typescript_calls_with_args: Returning early - no tree or no success"
            )
        return calls

    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "function_call_args" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys

            print(
                f"[DEBUG] extract_typescript_calls_with_args: Using PRE-EXTRACTED data ({len(extracted_data['function_call_args'])} calls)",
                file=sys.stderr,
            )
        return extracted_data["function_call_args"]

    ast_root = actual_tree.get("ast", {})
    scope_map = build_scope_map(ast_root)

    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] Built scope map with {len(scope_map)} line mappings")

        sample_lines = sorted([ln for ln in scope_map if scope_map[ln] != "global"])[:5]
        for line in sample_lines:
            print(f"[DEBUG]   Line {line} -> {scope_map[line]}")

    visited_nodes = set()

    def traverse(node, depth=0):
        """Traverse AST extracting calls. Scope is determined by line number lookup."""
        if depth > 100 or not isinstance(node, dict):
            return

        node_id = (node.get("line"), node.get("column", 0), node.get("kind"))
        if node_id in visited_nodes:
            return
        visited_nodes.add(node_id)

        try:
            kind = node.get("kind", "")

            if kind == "CallExpression":
                line = node.get("line", 0)

                caller_function_raw = scope_map.get(line, "global") or "global"
                caller_function = _strip_comment_prefix(caller_function_raw) or "global"

                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] Found CallExpression at line {line}, caller={caller_function}")

                children = node.get("children", [])
                if not children:
                    arguments = node.get("arguments", [])
                else:
                    arguments = children[1:] if len(children) > 1 else []

                callee_name = _canonical_callee_from_call(node) or "unknown"

                callee_file_path_raw = node.get("calleeFilePath")
                if isinstance(callee_file_path_raw, dict):
                    callee_file_path = None
                elif isinstance(callee_file_path_raw, str):
                    callee_file_path = callee_file_path_raw
                else:
                    callee_file_path = None

                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(
                        f"[DEBUG] CallExpression: caller={caller_function}, callee={callee_name}, callee_file={callee_file_path}, args={len(arguments)}"
                    )

                callee_params = function_params.get(callee_name.split(".")[-1], [])

                for i, arg in enumerate(arguments):
                    if isinstance(arg, dict):
                        raw_arg_text = arg.get("text", "")
                        arg_text = _strip_comment_prefix(raw_arg_text) or raw_arg_text.strip()

                        if i < len(callee_params):
                            param = callee_params[i]
                            if isinstance(param, dict):
                                param_name = param.get("name", f"arg{i}")
                            elif isinstance(param, str):
                                param_name = param
                            else:
                                param_name = f"arg{i}"
                        else:
                            param_name = f"arg{i}"

                        calls.append(
                            {
                                "line": line,
                                "caller_function": caller_function,
                                "callee_function": callee_name,
                                "argument_index": i,
                                "argument_expr": arg_text,
                                "param_name": param_name,
                                "callee_file_path": callee_file_path,
                            }
                        )

            for child in node.get("children", []):
                traverse(child, depth + 1)

        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Error in extract_typescript_calls_with_args: {e}")

    traverse(ast_root)

    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] Extracted {len(calls)} function calls with args from semantic AST")

        from collections import Counter

        caller_dist = Counter(c["caller_function"] for c in calls)
        print(f"[DEBUG] Caller distribution: {dict(caller_dist)}")

    return calls


def extract_typescript_returns(tree: dict, parser_self) -> list[dict[str, Any]]:
    """Extract ALL return statements from TypeScript semantic AST, including JSX.

    CRITICAL FIXES:
    - Uses line-based scope mapping for accurate function context
    - Tracks multiple returns per function (early returns, conditionals)
    - Properly detects and preserves JSX returns for React components
    """
    returns = []

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return returns

    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "returns" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys

            print(
                f"[DEBUG] extract_typescript_returns: Using PRE-EXTRACTED data ({len(extracted_data['returns'])} returns)",
                file=sys.stderr,
            )
        return extracted_data["returns"]

    ast_root = actual_tree.get("ast", {})
    scope_map = build_scope_map(ast_root)

    function_return_counts = {}

    def traverse(node, depth=0):
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind")

        if kind == "ReturnStatement":
            line = node.get("line", 0)

            current_function = scope_map.get(line, "global")

            if current_function not in function_return_counts:
                function_return_counts[current_function] = 0
            function_return_counts[current_function] += 1
            return_index = function_return_counts[current_function]

            expr_node = node.get("expression", {})
            return_expr = ""
            has_jsx = False
            returns_component = False

            if isinstance(expr_node, dict):
                return_expr = expr_node.get("text", "")

                if not return_expr and expr_node.get("children"):
                    first_child = expr_node.get("children", [{}])[0]
                    if isinstance(first_child, dict):
                        return_expr = first_child.get("text", "")

                has_jsx, returns_component = detect_jsx_in_node(expr_node)

                if not has_jsx and return_expr:
                    jsx_indicators = [
                        "React.createElement",
                        "jsx(",
                        "_jsx(",
                        "React.Fragment",
                        "Fragment",
                    ]
                    for indicator in jsx_indicators:
                        if indicator in return_expr:
                            has_jsx = True

                            if return_expr.strip().startswith("<"):
                                stripped = return_expr.strip()
                                if len(stripped) > 1 and stripped[1].isupper():
                                    returns_component = True
                            break
            else:
                return_expr = str(expr_node) if expr_node else "undefined"

                if return_expr in ["null", "undefined", "false"]:
                    has_jsx = False
                    returns_component = False

            return_vars = (
                extract_vars_from_typescript_node(expr_node) if isinstance(expr_node, dict) else []
            )

            returns.append(
                {
                    "function_name": current_function,
                    "line": line,
                    "return_expr": return_expr,
                    "return_vars": return_vars,
                    "has_jsx": has_jsx,
                    "returns_component": returns_component,
                    "return_index": return_index,
                }
            )

        for child in node.get("children", []):
            traverse(child, depth + 1)

    traverse(ast_root)

    seen = set()
    deduped = []
    for r in returns:
        key = (r["line"], r["function_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(returns) != len(deduped):
            print(
                f"[AST_DEBUG] TypeScript returns deduplication: {len(returns)} -> {len(deduped)} ({len(returns) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )
        jsx_returns = [r for r in deduped if r.get("has_jsx")]
        print(
            f"[DEBUG] Found {len(deduped)} total returns, {len(jsx_returns)} with JSX",
            file=sys.stderr,
        )
        if jsx_returns and len(jsx_returns) < 5:
            for r in jsx_returns[:3]:
                print(
                    f"[DEBUG]   JSX return in {r['function_name']} at line {r['line']}: {r['return_expr'][:50]}...",
                    file=sys.stderr,
                )

    return deduped


def extract_typescript_cfg(tree: dict, parser_self) -> list[dict[str, Any]]:
    """Extract control flow graphs from pre-extracted CFG data.

    PHASE 5 UNIFIED SINGLE-PASS ARCHITECTURE:
    CFG is now extracted directly in JavaScript using extractCFG() function,
    which handles ALL node types including JSX (JsxElement, JsxSelfClosingElement, etc.).

    This fixes the jsx='preserved' 0 CFG bug where Python's AST traverser
    couldn't understand JSX nodes.

    Returns:
        List of CFG objects (one per function) from extracted_data.cfg
    """
    cfgs = []

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return cfgs

    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "cfg" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(
                f"[DEBUG] extract_typescript_cfg: Using PRE-EXTRACTED CFG data ({len(extracted_data['cfg'])} CFGs)"
            )
        return extracted_data["cfg"]

    if os.environ.get("THEAUDITOR_DEBUG"):
        print("[DEBUG] extract_typescript_cfg: No 'cfg' key found in extracted_data.")

    return cfgs


def extract_typescript_object_literals(tree: dict, parser_self) -> list[dict[str, Any]]:
    """Extract object literal properties via direct semantic AST traversal.

    This is the centralized, correct implementation for object literal extraction.

    ARCHITECTURAL CONTRACT:
    -----------------------
    This function is an IMPLEMENTATION layer component. It:
    - RECEIVES: AST tree only (no file path context)
    - EXTRACTS: Object literal data with line numbers
    - RETURNS: List[Dict] with keys: line, variable_name, property_name, property_value, property_type, nested_level, in_function
    - MUST NOT: Include 'file' or 'file_path' keys in returned dicts

    File path context is provided by the INDEXER layer when storing to database.
    See indexer/__init__.py:952 which calls db_manager.add_object_literal(file_path, obj_lit['line'], ...)

    This separation ensures single source of truth for file paths.
    """
    object_literals = []

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return object_literals

    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "object_literals" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys

            print(
                f"[DEBUG] extract_typescript_object_literals: Using PRE-EXTRACTED data ({len(extracted_data['object_literals'])} literals)",
                file=sys.stderr,
            )
        return extracted_data["object_literals"]

    ast_root = actual_tree.get("ast", {})
    if not ast_root:
        return object_literals

    scope_map = build_scope_map(ast_root)

    def _get_ts_value(value_node):
        """Helper to extract text from a value node."""
        if not value_node or not isinstance(value_node, dict):
            return ""

        return value_node.get("text", "")[:250]

    def _get_ts_name(name_node):
        """Helper to extract a name identifier."""
        if not name_node or not isinstance(name_node, dict):
            return "<unknown>"
        return (
            name_node.get("name")
            or name_node.get("escapedText")
            or name_node.get("text", "<unknown>")
        )

    def _extract_from_object_node(obj_node, var_name, in_function, line_num):
        """Recursively extract properties from an ObjectLiteralExpression node."""
        props = obj_node.get("properties", obj_node.get("children", []))
        if not isinstance(props, list):
            return

        for prop in props:
            if not isinstance(prop, dict):
                continue

            prop_kind = prop.get("kind", "")
            prop_line = prop.get("line", line_num)

            if prop_kind == "PropertyAssignment":
                prop_name = _get_ts_name(prop.get("name"))
                prop_value = _get_ts_value(prop.get("initializer"))
                prop_type = "value"

                object_literals.append(
                    {
                        "line": prop_line,
                        "variable_name": var_name,
                        "property_name": prop_name,
                        "property_value": prop_value,
                        "property_type": prop_type,
                        "nested_level": 0,
                        "in_function": in_function,
                    }
                )

            elif prop_kind == "ShorthandPropertyAssignment":
                prop_name = _get_ts_name(prop.get("name"))
                object_literals.append(
                    {
                        "line": prop_line,
                        "variable_name": var_name,
                        "property_name": prop_name,
                        "property_value": prop_name,
                        "property_type": "shorthand",
                        "nested_level": 0,
                        "in_function": in_function,
                    }
                )

    visited_nodes = set()

    def traverse(node, depth=0):
        if depth > 100 or not isinstance(node, dict):
            return

        node_id = (node.get("line"), node.get("column", 0), node.get("kind"))
        if node_id in visited_nodes:
            return
        visited_nodes.add(node_id)

        kind = node.get("kind")
        line = node.get("line", 0)
        in_function = scope_map.get(line, "global")

        if kind == "VariableDeclaration":
            initializer = node.get("initializer")
            if initializer and initializer.get("kind") == "ObjectLiteralExpression":
                var_name = _get_ts_name(node.get("name"))
                _extract_from_object_node(initializer, var_name, in_function, line)

        elif (
            kind == "BinaryExpression"
            and node.get("operatorToken", {}).get("kind") == "EqualsToken"
        ):
            right = node.get("right")
            if right and right.get("kind") == "ObjectLiteralExpression":
                var_name = _get_ts_value(node.get("left"))
                _extract_from_object_node(right, var_name, in_function, line)

        elif kind == "ReturnStatement":
            expr = node.get("expression")
            if expr and expr.get("kind") == "ObjectLiteralExpression":
                var_name = f"<return:{in_function}>"
                _extract_from_object_node(expr, var_name, in_function, line)

        elif kind == "CallExpression":
            args = node.get("arguments", [])
            if not args:
                children = node.get("children", [])

                args = children[1:] if len(children) > 1 else []

            for i, arg in enumerate(args):
                if isinstance(arg, dict) and arg.get("kind") == "ObjectLiteralExpression":
                    callee_name = _canonical_callee_from_call(node) or "unknown"
                    var_name = f"<arg{i}:{callee_name}>"
                    _extract_from_object_node(arg, var_name, in_function, arg.get("line", line))

        elif kind == "ArrayLiteralExpression":
            elements = node.get("elements", node.get("children", []))
            for i, elem in enumerate(elements):
                if isinstance(elem, dict) and elem.get("kind") == "ObjectLiteralExpression":
                    var_name = f"<array_elem{i}>"
                    _extract_from_object_node(elem, var_name, in_function, elem.get("line", line))

        elif kind == "PropertyAssignment":
            init = node.get("initializer")
            if init and init.get("kind") == "ObjectLiteralExpression":
                prop_name = _get_ts_name(node.get("name"))
                var_name = f"<property:{prop_name}>"
                _extract_from_object_node(init, var_name, in_function, line)

        elif kind == "PropertyDeclaration":
            init = node.get("initializer")
            if init and init.get("kind") == "ObjectLiteralExpression":
                prop_name = _get_ts_name(node.get("name"))
                var_name = f"<class_property:{prop_name}>"
                _extract_from_object_node(init, var_name, in_function, line)

        for child in node.get("children", []):
            traverse(child, depth + 1)

    traverse(ast_root)
    return object_literals


def build_typescript_function_cfg(func_node: dict) -> dict[str, Any]:
    """Build CFG for a single TypeScript function using AST traversal.

    This properly traverses the AST instead of using string matching.
    """
    blocks = []
    edges = []
    block_counter = [0]

    def get_next_block_id():
        block_counter[0] += 1
        return block_counter[0]

    func_name = "anonymous"
    name_node = func_node.get("name")
    if isinstance(name_node, dict):
        func_name = name_node.get("text", "anonymous")
    elif isinstance(name_node, str):
        func_name = name_node

    func_start_line = func_node.get("line", 1)
    func_end_line = func_node.get("endLine", func_start_line)

    entry_id = get_next_block_id()

    blocks.append(
        {
            "id": entry_id,
            "type": "entry",
            "start_line": func_start_line,
            "end_line": func_end_line,
            "statements": [],
        }
    )

    body_node = None
    for child in func_node.get("children", []):
        if isinstance(child, dict) and child.get("kind") in ["Block", "BlockStatement"]:
            body_node = child
            break

    if not body_node:
        return None

    exit_id = get_next_block_id()

    def process_node(node, current_id, depth=0):
        """Process a node and build CFG blocks."""
        if depth > 50 or not isinstance(node, dict):
            return current_id

        kind = node.get("kind", "")
        line = node.get("line", func_start_line)

        if kind == "IfStatement":
            cond_id = get_next_block_id()
            blocks.append(
                {
                    "id": cond_id,
                    "type": "condition",
                    "start_line": line,
                    "end_line": line,
                    "condition": extract_condition_text(node),
                    "statements": [{"type": "if", "line": line}],
                }
            )
            edges.append({"source": current_id, "target": cond_id, "type": "normal"})

            then_id = get_next_block_id()
            blocks.append(
                {
                    "id": then_id,
                    "type": "basic",
                    "start_line": line,
                    "end_line": line,
                    "statements": [],
                }
            )
            edges.append({"source": cond_id, "target": then_id, "type": "true"})

            then_stmt = get_child_by_kind(node, "Block")
            if then_stmt:
                then_id = process_children(then_stmt, then_id, depth + 1)

            else_stmt = None
            for i, child in enumerate(node.get("children", [])):
                if i > 0 and child.get("kind") == "Block" or child.get("kind") == "IfStatement":
                    else_stmt = child
                    break

            if else_stmt:
                else_id = get_next_block_id()
                blocks.append(
                    {
                        "id": else_id,
                        "type": "basic",
                        "start_line": else_stmt.get("line", line),
                        "end_line": else_stmt.get("line", line),
                        "statements": [],
                    }
                )
                edges.append({"source": cond_id, "target": else_id, "type": "false"})

                if else_stmt.get("kind") == "IfStatement":
                    else_id = process_node(else_stmt, else_id, depth + 1)
                else:
                    else_id = process_children(else_stmt, else_id, depth + 1)

                merge_id = get_next_block_id()
                blocks.append(
                    {
                        "id": merge_id,
                        "type": "merge",
                        "start_line": line,
                        "end_line": line,
                        "statements": [],
                    }
                )
                edges.append({"source": then_id, "target": merge_id, "type": "normal"})
                edges.append({"source": else_id, "target": merge_id, "type": "normal"})
                return merge_id
            else:
                merge_id = get_next_block_id()
                blocks.append(
                    {
                        "id": merge_id,
                        "type": "merge",
                        "start_line": line,
                        "end_line": line,
                        "statements": [],
                    }
                )
                edges.append({"source": cond_id, "target": merge_id, "type": "false"})
                edges.append({"source": then_id, "target": merge_id, "type": "normal"})
                return merge_id

        elif kind in [
            "ForStatement",
            "ForInStatement",
            "ForOfStatement",
            "WhileStatement",
            "DoWhileStatement",
        ]:
            loop_id = get_next_block_id()
            blocks.append(
                {
                    "id": loop_id,
                    "type": "loop_condition",
                    "start_line": line,
                    "end_line": line,
                    "condition": extract_condition_text(node),
                    "statements": [{"type": "loop", "line": line}],
                }
            )
            edges.append({"source": current_id, "target": loop_id, "type": "normal"})

            body_id = get_next_block_id()
            blocks.append(
                {
                    "id": body_id,
                    "type": "loop_body",
                    "start_line": line,
                    "end_line": line,
                    "statements": [],
                }
            )
            edges.append({"source": loop_id, "target": body_id, "type": "true"})

            loop_body = get_child_by_kind(node, "Block")
            if loop_body:
                body_id = process_children(loop_body, body_id, depth + 1)

            edges.append({"source": body_id, "target": loop_id, "type": "back_edge"})

            exit_loop_id = get_next_block_id()
            blocks.append(
                {
                    "id": exit_loop_id,
                    "type": "merge",
                    "start_line": line,
                    "end_line": line,
                    "statements": [],
                }
            )
            edges.append({"source": loop_id, "target": exit_loop_id, "type": "false"})

            return exit_loop_id

        elif kind == "ReturnStatement":
            ret_id = get_next_block_id()
            blocks.append(
                {
                    "id": ret_id,
                    "type": "return",
                    "start_line": line,
                    "end_line": line,
                    "statements": [{"type": "return", "line": line}],
                }
            )
            edges.append({"source": current_id, "target": ret_id, "type": "normal"})
            edges.append({"source": ret_id, "target": exit_id, "type": "normal"})
            return None

        elif kind == "TryStatement":
            try_body = get_child_by_kind(node, "Block")
            try_end_line = try_body.get("endLine", line) if try_body else line

            try_id = get_next_block_id()
            blocks.append(
                {
                    "id": try_id,
                    "type": "try",
                    "start_line": line,
                    "end_line": try_end_line,
                    "statements": [{"type": "try", "line": line}],
                }
            )
            edges.append({"source": current_id, "target": try_id, "type": "normal"})

            if try_body:
                try_id = process_children(try_body, try_id, depth + 1)

            catch_block = None
            for child in node.get("children", []):
                if child.get("kind") == "CatchClause":
                    catch_block = child
                    break

            if catch_block:
                catch_body = get_child_by_kind(catch_block, "Block")
                catch_start_line = catch_block.get("line", line)
                catch_end_line = (
                    catch_body.get("endLine", catch_start_line) if catch_body else catch_start_line
                )

                catch_id = get_next_block_id()
                blocks.append(
                    {
                        "id": catch_id,
                        "type": "except",
                        "start_line": catch_start_line,
                        "end_line": catch_end_line,
                        "statements": [{"type": "catch", "line": catch_start_line}],
                    }
                )
                edges.append({"source": try_id, "target": catch_id, "type": "exception"})

                if catch_body:
                    catch_id = process_children(catch_body, catch_id, depth + 1)

                merge_id = get_next_block_id()
                blocks.append(
                    {
                        "id": merge_id,
                        "type": "merge",
                        "start_line": line,
                        "end_line": line,
                        "statements": [],
                    }
                )
                edges.append({"source": try_id, "target": merge_id, "type": "normal"})
                edges.append({"source": catch_id, "target": merge_id, "type": "normal"})

                return merge_id

            return try_id

        elif kind == "SwitchStatement":
            switch_id = get_next_block_id()
            blocks.append(
                {
                    "id": switch_id,
                    "type": "condition",
                    "start_line": line,
                    "end_line": line,
                    "condition": "switch",
                    "statements": [{"type": "switch", "line": line}],
                }
            )
            edges.append({"source": current_id, "target": switch_id, "type": "normal"})

            case_ids = []
            for child in node.get("children", []):
                if child.get("kind") in ["CaseClause", "DefaultClause"]:
                    case_id = get_next_block_id()
                    blocks.append(
                        {
                            "id": case_id,
                            "type": "basic",
                            "start_line": child.get("line", line),
                            "end_line": child.get("line", line),
                            "statements": [],
                        }
                    )
                    edges.append({"source": switch_id, "target": case_id, "type": "case"})

                    case_id = process_children(child, case_id, depth + 1)
                    case_ids.append(case_id)

            merge_id = get_next_block_id()
            blocks.append(
                {
                    "id": merge_id,
                    "type": "merge",
                    "start_line": line,
                    "end_line": line,
                    "statements": [],
                }
            )

            for case_id in case_ids:
                if case_id:
                    edges.append({"source": case_id, "target": merge_id, "type": "normal"})

            return merge_id

        return current_id

    def process_children(parent_node, current_id, depth):
        """Process all children of a node."""
        for child in parent_node.get("children", []):
            new_id = process_node(child, current_id, depth)
            if new_id is not None:
                current_id = new_id
        return current_id

    def get_child_by_kind(node, kind):
        """Get first child with specified kind."""
        for child in node.get("children", []):
            if child.get("kind") == kind:
                return child
        return None

    def extract_condition_text(node):
        """Extract condition text from control flow node."""

        for child in node.get("children", []):
            if child.get("kind") in [
                "BinaryExpression",
                "UnaryExpression",
                "Identifier",
                "CallExpression",
                "MemberExpression",
                "PropertyAccessExpression",
            ]:
                return child.get("text", "condition")
        return "condition"

    current_id = entry_id
    current_id = process_children(body_node, current_id, 0)

    blocks.append(
        {
            "id": exit_id,
            "type": "exit",
            "start_line": func_start_line,
            "end_line": func_end_line,
            "statements": [],
        }
    )

    if current_id:
        edges.append({"source": current_id, "target": exit_id, "type": "normal"})

    return {"function_name": func_name, "blocks": blocks, "edges": edges}
