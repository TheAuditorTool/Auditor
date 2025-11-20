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
from typing import Any, List, Dict, Optional

from .base import extract_vars_from_typescript_node  # Source variable extraction
from .typescript_impl_structure import (
    build_scope_map,              # Core foundation for scope resolution
    _canonical_callee_from_call,  # Call name resolution
    _strip_comment_prefix,        # Text cleaning
    detect_jsx_in_node,          # JSX detection
    # Re-export structural extractors for orchestrator backward compatibility
    extract_typescript_functions,
    extract_typescript_functions_for_symbols,
    extract_typescript_function_nodes,
    extract_typescript_classes,
    extract_typescript_calls,
    extract_typescript_imports,
    extract_typescript_exports,
    extract_typescript_properties,
    extract_semantic_ast_symbols,
)

def extract_typescript_assignments(tree: dict, parser_self) -> list[dict[str, Any]]:
    """Extract ALL assignment patterns from TypeScript semantic AST, including destructuring.

    CRITICAL FIX: Now uses line-based scope mapping for accurate function context.
    """
    assignments = []

    # Check if parsing was successful - handle nested structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys
            print(f"[AST_DEBUG] extract_typescript_assignments: No success in tree", file=sys.stderr)
        return assignments

    # PHASE 5: Check for pre-extracted data FIRST
    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "assignments" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys
            print(f"[DEBUG] extract_typescript_assignments: Using PRE-EXTRACTED data ({len(extracted_data['assignments'])} assignments)", file=sys.stderr)
        return extracted_data["assignments"]

    # CRITICAL FIX: Build scope map FIRST!
    ast_root = actual_tree.get("ast", {})
    scope_map = build_scope_map(ast_root)
    
    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        print(f"[AST_DEBUG] extract_typescript_assignments: Starting extraction with scope map", file=sys.stderr)

    def traverse(node, depth=0):  # No more current_function parameter!
        if depth > 100 or not isinstance(node, dict):
            return

        try:
            kind = node.get("kind", "")
            
            # DEBUG: Log ALL node kinds we see to understand structure
            if os.environ.get("THEAUDITOR_DEBUG"):
                import sys
                if depth < 5:  # Log more depth
                    print(f"[AST_DEBUG] Depth {depth}: kind='{kind}'", file=sys.stderr)
                if "Variable" in kind or "Assignment" in kind or "Binary" in kind or "=" in str(node.get("text", "")):
                    print(f"[AST_DEBUG] *** POTENTIAL ASSIGNMENT at depth {depth}: {kind}, text={str(node.get('text', ''))[:50]} ***", file=sys.stderr)

            # --- Assignment Extraction ---
            # No more function context tracking - scope map handles it!
            # 1. Standard Assignments: const x = y; or x = y;
            # NOTE: TypeScript AST has VariableDeclaration nested under FirstStatement->VariableDeclarationList
            if kind in ["VariableDeclaration", "BinaryExpression"]:
                # For BinaryExpression, check if it's an assignment (=) operator
                is_assignment = True
                if kind == "BinaryExpression":
                    op_token = node.get("operatorToken", {})
                    if not (isinstance(op_token, dict) and op_token.get("kind") == "EqualsToken"):
                        # Not an assignment, just a comparison or arithmetic expression
                        is_assignment = False
                
                if is_assignment:
                    # TypeScript AST structure is different - use children and text
                    if kind == "VariableDeclaration":
                        # For TypeScript VariableDeclaration, extract from text or children
                        full_text = node.get("text", "")
                        if "=" in full_text:
                            parts = full_text.split("=", 1)
                            target_var = parts[0].strip()
                            source_expr = parts[1].strip()
                            if target_var and source_expr:
                                line = node.get("line", 0)
                                # CRITICAL FIX: Get function from scope map
                                in_function = scope_map.get(line, "global")

                                # CRITICAL FIX: Extract source_vars from AST node, not text
                                # Try to get the initializer node from AST structure
                                source_vars = []
                                # Look for initializer in children
                                for child in node.get("children", []):
                                    if isinstance(child, dict) and child.get("kind") != "Identifier":
                                        # This is likely the initializer expression
                                        source_vars = extract_vars_from_typescript_node(child)
                                        break

                                if os.environ.get("THEAUDITOR_DEBUG"):
                                    import sys
                                    print(f"[AST_DEBUG] Found TS assignment: {target_var} = {source_expr[:30]}... at line {line} in {in_function}", file=sys.stderr)
                                assignments.append({
                                    "target_var": target_var,
                                    "source_expr": source_expr,
                                    "line": line,
                                    "in_function": in_function,  # NOW ACCURATE!
                                    "source_vars": source_vars  # NOW EXTRACTED FROM AST!
                                })
                    else:
                        # BinaryExpression - use the original logic
                        target_node = node.get("left")
                        source_node = node.get("right")
                        
                        if isinstance(target_node, dict) and isinstance(source_node, dict):
                            # --- ENHANCEMENT: Handle Destructuring ---
                            if target_node.get("kind") in ["ObjectBindingPattern", "ArrayBindingPattern"]:
                                source_expr = source_node.get("text", "unknown_source")
                                # CRITICAL FIX: Extract variables from source AST node
                                source_vars = extract_vars_from_typescript_node(source_node) if isinstance(source_node, dict) else []

                                # For each element in the destructuring, create a separate assignment
                                for element in target_node.get("elements", []):
                                    if isinstance(element, dict) and element.get("name"):
                                        target_var = element.get("name", {}).get("text")
                                        if target_var:
                                            line = element.get("line", node.get("line", 0))
                                            # CRITICAL FIX: Get function from scope map
                                            in_function = scope_map.get(line, "global")

                                            assignments.append({
                                                "target_var": target_var,
                                                "source_expr": source_expr, # CRITICAL: Source is the original object/array
                                                "line": line,
                                                "in_function": in_function,  # NOW ACCURATE!
                                                "source_vars": source_vars  # NOW EXTRACTED FROM AST!
                                            })
                            else:
                                # --- Standard, non-destructured assignment ---
                                target_var = target_node.get("text", "")
                                source_expr = source_node.get("text", "")
                                if target_var and source_expr:
                                    line = node.get("line", 0)
                                    # CRITICAL FIX: Get function from scope map
                                    in_function = scope_map.get(line, "global")

                                    # CRITICAL FIX: Extract variables from source AST node
                                    source_vars = extract_vars_from_typescript_node(source_node) if isinstance(source_node, dict) else []

                                    if os.environ.get("THEAUDITOR_DEBUG"):
                                        import sys
                                        print(f"[AST_DEBUG] Found assignment: {target_var} = {source_expr[:50]}... at line {line} in {in_function}", file=sys.stderr)
                                    assignments.append({
                                        "target_var": target_var,
                                        "source_expr": source_expr,
                                        "line": line,
                                        "in_function": in_function,  # NOW ACCURATE!
                                        "source_vars": source_vars  # NOW EXTRACTED FROM AST!
                                    })

            # Recurse without tracking function context (scope map handles it)
            for child in node.get("children", []):
                traverse(child, depth + 1)

        except Exception:
            # This safety net catches any unexpected AST structures
            pass

    # Get AST from the correct location after unwrapping
    ast_root = actual_tree.get("ast", {})
    traverse(ast_root)

    # CRITICAL FIX: Deduplicate assignments by (line, target_var, in_function)
    # WHY: TypeScript semantic AST can represent nodes in multiple parent contexts,
    # causing traverse() to visit same VariableDeclaration multiple times.
    # This is NOT a fallback - it's fixing the extraction at source.
    seen = set()
    deduped = []
    for a in assignments:
        # Use composite key matching PRIMARY KEY constraint
        key = (a['line'], a['target_var'], a['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(assignments) != len(deduped):
            print(f"[AST_DEBUG] Deduplication: {len(assignments)} -> {len(deduped)} assignments ({len(assignments) - len(deduped)} duplicates removed)", file=sys.stderr)
        print(f"[AST_DEBUG] extract_typescript_assignments: Found {len(deduped)} unique assignments", file=sys.stderr)
        if deduped and len(deduped) < 5:
            for a in deduped[:3]:
                print(f"[AST_DEBUG]   Example: {a['target_var']} = {a['source_expr'][:30]}...", file=sys.stderr)

    return deduped


def extract_typescript_function_params(tree: dict, parser_self) -> dict[str, list[str]]:
    """Extract function parameters from TypeScript semantic AST."""
    import sys, os
    debug = os.environ.get("THEAUDITOR_DEBUG")

    if debug:
        print(f"[DEBUG typescript_impl.py:1132] extract_typescript_function_params called", file=sys.stderr)

    func_params = {}

    # Check if parsing was successful - handle nested structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        if debug:
            print(f"[DEBUG typescript_impl.py:1132] WARNING: actual_tree invalid or not successful", file=sys.stderr)
        return func_params

    if debug:
        print(f"[DEBUG typescript_impl.py:1132] Starting traverse of AST", file=sys.stderr)

    def traverse(node, depth=0):
        import sys  # Import at function level for all debug statements
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind")

        if debug and depth <= 2:  # Only log top-level nodes to avoid spam
            print(f"[DEBUG typescript_impl.py:traverse] depth={depth}, kind={kind}", file=sys.stderr)

        if kind in ["FunctionDeclaration", "MethodDeclaration", "ArrowFunction", "FunctionExpression"]:
            # Get function name
            name_node = node.get("name")
            func_name = "anonymous"
            if isinstance(name_node, dict):
                func_name = name_node.get("text", "anonymous")
            elif isinstance(name_node, str):
                func_name = name_node
            elif not name_node:
                # Look for Identifier child (TypeScript AST structure)
                for child in node.get("children", []):
                    if isinstance(child, dict) and child.get("kind") == "Identifier":
                        func_name = child.get("text", "anonymous")
                        break

            if debug:
                print(f"[DEBUG typescript_impl.py:1147] Found {kind} named '{func_name}' at line {node.get('line', '?')}", file=sys.stderr)

            # Extract parameter names from explicitly serialized parameters field
            # ZERO FALLBACK POLICY: The JavaScript helper MUST serialize parameters field
            # If parameters are missing, it's a serialization bug that must be fixed
            params = []
            param_nodes = node.get("parameters", [])

            if debug:
                print(f"[DEBUG typescript_impl.py:1166] param_nodes type: {type(param_nodes)}, length: {len(param_nodes) if isinstance(param_nodes, list) else 'N/A'}", file=sys.stderr)

            for param in param_nodes:
                # ARCHITECTURAL CONTRACT: JavaScript helper serializes parameters as:
                # { name: "paramName" } where name is ALWAYS a string extracted from AST
                # See core_ast_extractors.js:328-335 and :338
                if not isinstance(param, dict):
                    # Contract violation - parameters MUST be dict objects
                    if os.environ.get("THEAUDITOR_DEBUG"):
                        print(f"[ERROR typescript_impl.py:298] Parameter is not dict: {type(param)}", file=sys.stderr)
                    continue

                param_name = param.get("name")
                if not isinstance(param_name, str):
                    # Contract violation - name field MUST be string
                    if os.environ.get("THEAUDITOR_DEBUG"):
                        print(f"[ERROR typescript_impl.py:302] Parameter name is not string: {type(param_name)}, value={param_name}", file=sys.stderr)
                        print(f"[ERROR] This indicates JavaScript extractor bug at core_ast_extractors.js:338", file=sys.stderr)
                    continue

                if param_name:  # Only add non-empty param names
                    params.append(param_name)

            if debug:
                print(f"[DEBUG typescript_impl.py:1198] Extracted params for '{func_name}': {params}", file=sys.stderr)

            if func_name != "anonymous" and params:
                func_params[func_name] = params
            elif debug and func_name == "anonymous":
                print(f"[DEBUG typescript_impl.py:1198] Skipping anonymous function", file=sys.stderr)
            elif debug and not params:
                print(f"[DEBUG typescript_impl.py:1198] WARNING: No params extracted for '{func_name}'", file=sys.stderr)

        # CRITICAL FIX: Extract parameters from PropertyDeclaration with ArrowFunction/FunctionExpression
        # This handles modern TypeScript pattern: create = async (req, res) => {}
        # ZERO FALLBACK POLICY: Use explicit parameters field, not children array
        elif kind == "PropertyDeclaration":
            # Get the initializer (the arrow function or function expression)
            initializer = node.get("initializer")

            if isinstance(initializer, dict):
                init_kind = initializer.get("kind", "")

                # Pattern 1: Direct arrow function - create = async (req, res) => {}
                if init_kind in ["ArrowFunction", "FunctionExpression"]:
                    # Extract property name (function name)
                    prop_name = None
                    for child in node.get("children", []):
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            prop_name = child.get("text", "")
                            break

                    # Extract parameters from the initializer using explicit parameters field
                    # MATCH THE PATTERN AT LINE 1166: Use parameters field, not children
                    params = []
                    param_nodes = initializer.get("parameters", [])

                    for param in param_nodes:
                        # ARCHITECTURAL CONTRACT: Same as above - params are { name: "str" } dicts
                        if not isinstance(param, dict):
                            if os.environ.get("THEAUDITOR_DEBUG"):
                                print(f"[ERROR typescript_impl.py:345] Parameter is not dict: {type(param)}", file=sys.stderr)
                            continue

                        param_name = param.get("name")
                        if not isinstance(param_name, str):
                            if os.environ.get("THEAUDITOR_DEBUG"):
                                print(f"[ERROR typescript_impl.py:349] Parameter name is not string: {type(param_name)}", file=sys.stderr)
                            continue

                        if param_name:
                            params.append(param_name)

                    # Store parameter mapping
                    if prop_name and params:
                        func_params[prop_name] = params
                        if os.environ.get("THEAUDITOR_DEBUG"):
                            import sys
                            print(f"[DEBUG] Extracted PropertyDeclaration params: {prop_name}({', '.join(params)})", file=sys.stderr)

                # Pattern 2: Wrapped arrow function - create = this.asyncHandler(async (req, res) => {})
                elif init_kind == "CallExpression":
                    # Extract property name (function name) from PropertyDeclaration
                    prop_name = None
                    for child in node.get("children", []):
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            prop_name = child.get("text", "")
                            break

                    # Get the wrapped function from CallExpression children
                    # children[0] = PropertyAccessExpression (this.asyncHandler)
                    # children[1] = ArrowFunction (the actual function)
                    call_children = initializer.get("children", [])
                    if len(call_children) >= 2:
                        wrapped_func = call_children[1]
                        wrapped_kind = wrapped_func.get("kind", "")

                        # Check if the wrapped function is an arrow function
                        if wrapped_kind in ["ArrowFunction", "FunctionExpression"]:
                            # Extract parameters from the wrapped arrow function
                            params = []
                            param_nodes = wrapped_func.get("parameters", [])

                            for param in param_nodes:
                                # ARCHITECTURAL CONTRACT: Same as above - params are { name: "str" } dicts
                                if not isinstance(param, dict):
                                    if os.environ.get("THEAUDITOR_DEBUG"):
                                        print(f"[ERROR typescript_impl.py:390] Parameter is not dict: {type(param)}", file=sys.stderr)
                                    continue

                                param_name = param.get("name")
                                if not isinstance(param_name, str):
                                    if os.environ.get("THEAUDITOR_DEBUG"):
                                        print(f"[ERROR typescript_impl.py:394] Parameter name is not string: {type(param_name)}", file=sys.stderr)
                                    continue

                                if param_name:
                                    params.append(param_name)

                            # Store parameter mapping using PropertyDeclaration name
                            if prop_name and params:
                                func_params[prop_name] = params
                                if os.environ.get("THEAUDITOR_DEBUG"):
                                    import sys
                                    print(f"[DEBUG] Extracted wrapped PropertyDeclaration params: {prop_name}({', '.join(params)})", file=sys.stderr)
        
        # Recurse through children
        for child in node.get("children", []):
            traverse(child, depth + 1)

    # Get AST from the correct location after unwrapping
    ast_root = actual_tree.get("ast", {})

    if debug:
        print(f"[DEBUG typescript_impl.py:1257] ast_root type: {type(ast_root)}, is_dict: {isinstance(ast_root, dict)}", file=sys.stderr)
        if isinstance(ast_root, dict):
            print(f"[DEBUG typescript_impl.py:1257] ast_root keys: {list(ast_root.keys())[:10]}", file=sys.stderr)
            print(f"[DEBUG typescript_impl.py:1257] ast_root.get('kind'): {ast_root.get('kind')}", file=sys.stderr)
        else:
            print(f"[DEBUG typescript_impl.py:1257] WARNING: ast_root is NOT a dict!", file=sys.stderr)

    traverse(ast_root)

    if debug:
        print(f"[DEBUG typescript_impl.py:1260] FINAL RESULT: Extracted {len(func_params)} total functions with params", file=sys.stderr)
        if func_params:
            sample = list(func_params.items())[:5]
            print(f"[DEBUG typescript_impl.py:1260] Sample functions: {sample}", file=sys.stderr)
        else:
            print(f"[DEBUG typescript_impl.py:1260] WARNING: func_params is EMPTY - no functions with params found!", file=sys.stderr)

    return func_params


def extract_typescript_calls_with_args(tree: dict, function_params: dict[str, list[str]], parser_self) -> list[dict[str, Any]]:
    """Extract function calls with arguments from TypeScript semantic AST.

    CRITICAL FIX: Now uses line-based scope mapping instead of broken recursive tracking.
    This solves the "100% anonymous caller" problem that crippled taint analysis.
    """
    calls = []

    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] extract_typescript_calls_with_args: tree type={type(tree)}, success={tree.get('success') if tree else 'N/A'}")

    # Check if parsing was successful - handle nested structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG] extract_typescript_calls_with_args: Returning early - no tree or no success")
        return calls

    # PHASE 5: Check for pre-extracted data FIRST
    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "function_call_args" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys
            print(f"[DEBUG] extract_typescript_calls_with_args: Using PRE-EXTRACTED data ({len(extracted_data['function_call_args'])} calls)", file=sys.stderr)
        return extracted_data["function_call_args"]

    # CRITICAL FIX: Build scope map FIRST before traversing!
    # This pre-computes which function contains each line number
    ast_root = actual_tree.get("ast", {})
    scope_map = build_scope_map(ast_root)
    
    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] Built scope map with {len(scope_map)} line mappings")
        # Show sample mappings
        sample_lines = sorted([l for l in scope_map.keys() if scope_map[l] != "global"])[:5]
        for line in sample_lines:
            print(f"[DEBUG]   Line {line} -> {scope_map[line]}")

    # CRITICAL FIX: Idempotent traversal to prevent duplicate entries
    # Track visited nodes by (line, column, kind) to avoid processing same node multiple times
    visited_nodes = set()

    def traverse(node, depth=0):  # No more current_function parameter!
        """Traverse AST extracting calls. Scope is determined by line number lookup."""
        if depth > 100 or not isinstance(node, dict):
            return

        # CRITICAL FIX: Idempotency check - prevent processing same node twice
        node_id = (node.get("line"), node.get("column", 0), node.get("kind"))
        if node_id in visited_nodes:
            return  # This node has already been processed
        visited_nodes.add(node_id)

        try:
            kind = node.get("kind", "")

            # CallExpression: function calls
            if kind == "CallExpression":
                line = node.get("line", 0)
                
                # CRITICAL FIX: Get caller from scope map using line number
                # This is O(1) and accurate, unlike the old recursive tracking
                caller_function_raw = scope_map.get(line, "global") or "global"
                caller_function = _strip_comment_prefix(caller_function_raw) or "global"
                
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] Found CallExpression at line {line}, caller={caller_function}")
                
                # FIX: In TypeScript AST, the function and arguments are in children array
                children = node.get("children", [])
                if not children:
                    # Fallback to old structure
                    expression = node.get("expression", {})
                    arguments = node.get("arguments", [])
                else:
                    # New structure: first child is function, rest are arguments
                    expression = children[0] if len(children) > 0 else {}
                    arguments = children[1:] if len(children) > 1 else []
                
                # Get function name from expression (canonicalised)
                callee_name = _canonical_callee_from_call(node) or "unknown"

                # CRITICAL: Read resolved callee file path from AST (added by TypeScript checker)
                # FIX: Ensure callee_file_path is None or string, never a dict
                callee_file_path_raw = node.get("calleeFilePath")
                if isinstance(callee_file_path_raw, dict):
                    # If it's a dict, it might contain the path as a field
                    callee_file_path = None  # Safer to use None than risk another dict
                elif isinstance(callee_file_path_raw, str):
                    callee_file_path = callee_file_path_raw
                else:
                    callee_file_path = None

                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] CallExpression: caller={caller_function}, callee={callee_name}, callee_file={callee_file_path}, args={len(arguments)}")

                # Get parameters for this function if we know them
                callee_params = function_params.get(callee_name.split(".")[-1], [])

                # Process arguments
                for i, arg in enumerate(arguments):
                    if isinstance(arg, dict):
                        raw_arg_text = arg.get("text", "")
                        arg_text = _strip_comment_prefix(raw_arg_text) or raw_arg_text.strip()

                        # DEFENSIVE: Handle case where callee_params contains dicts instead of strings
                        # Architectural contract says params should be strings, but handle legacy dict format
                        if i < len(callee_params):
                            param = callee_params[i]
                            if isinstance(param, dict):
                                # Legacy format: {name: "paramName"} - extract the name
                                param_name = param.get("name", f"arg{i}")
                            elif isinstance(param, str):
                                # Correct format: just the string
                                param_name = param
                            else:
                                param_name = f"arg{i}"
                        else:
                            param_name = f"arg{i}"

                        calls.append({
                            "line": line,
                            "caller_function": caller_function,  # NOW ACCURATE from scope map!
                            "callee_function": callee_name,
                            "argument_index": i,
                            "argument_expr": arg_text,
                            "param_name": param_name,
                            "callee_file_path": callee_file_path  # Resolved by TypeScript checker
                        })

            # Recurse without tracking function context (scope map handles it)
            for child in node.get("children", []):
                traverse(child, depth + 1)

        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Error in extract_typescript_calls_with_args: {e}")

    # Start traversal
    traverse(ast_root)

    # Debug output
    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] Extracted {len(calls)} function calls with args from semantic AST")
        # Show distribution of caller functions
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

    # Check if parsing was successful - handle nested structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return returns

    # PHASE 5: Check for pre-extracted data FIRST
    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "returns" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys
            print(f"[DEBUG] extract_typescript_returns: Using PRE-EXTRACTED data ({len(extracted_data['returns'])} returns)", file=sys.stderr)
        return extracted_data["returns"]

    # CRITICAL FIX: Build scope map FIRST!
    ast_root = actual_tree.get("ast", {})
    scope_map = build_scope_map(ast_root)

    # Track return index per function for multiple returns
    function_return_counts = {}

    # Traverse AST looking for return statements
    def traverse(node, depth=0):  # No more current_function parameter!
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind")

        # ReturnStatement
        if kind == "ReturnStatement":
            line = node.get("line", 0)

            # CRITICAL FIX: Get function from scope map
            current_function = scope_map.get(line, "global")

            # Track multiple returns per function
            if current_function not in function_return_counts:
                function_return_counts[current_function] = 0
            function_return_counts[current_function] += 1
            return_index = function_return_counts[current_function]

            # ENHANCED: Better extraction of return expression
            expr_node = node.get("expression", {})
            return_expr = ""
            has_jsx = False
            returns_component = False

            if isinstance(expr_node, dict):
                # CRITICAL: Preserve the FULL text, including JSX
                return_expr = expr_node.get("text", "")

                # If text is missing, try to reconstruct from children
                if not return_expr and expr_node.get("children"):
                    # Try to get text from first child
                    first_child = expr_node.get("children", [{}])[0]
                    if isinstance(first_child, dict):
                        return_expr = first_child.get("text", "")

                # Check expr_node kind for JSX detection
                expr_kind = expr_node.get("kind", "")

                # Check for JSX elements in return statement
                has_jsx, returns_component = detect_jsx_in_node(expr_node)

                # Additional pattern-based JSX detection for edge cases
                if not has_jsx and return_expr:
                    # Check for JSX patterns in the text that might be missed
                    jsx_indicators = [
                        'React.createElement',
                        'jsx(',
                        '_jsx(',
                        'React.Fragment',
                        'Fragment',
                    ]
                    for indicator in jsx_indicators:
                        if indicator in return_expr:
                            has_jsx = True
                            # Check if it's a component (starts with capital)
                            if return_expr.strip().startswith('<'):
                                # Check if component name starts with capital letter
                                # Pure string operation - no regex needed
                                stripped = return_expr.strip()
                                if len(stripped) > 1 and stripped[1].isupper():
                                    returns_component = True
                            break
            else:
                # Non-dict expression
                return_expr = str(expr_node) if expr_node else "undefined"
                # Check for null/undefined (common React returns)
                if return_expr in ["null", "undefined", "false"]:
                    # These are valid React returns for conditional rendering
                    has_jsx = False
                    returns_component = False

            # CRITICAL FIX: Extract return_vars from AST node, not text
            return_vars = extract_vars_from_typescript_node(expr_node) if isinstance(expr_node, dict) else []

            returns.append({
                "function_name": current_function,  # NOW ACCURATE!
                "line": line,
                "return_expr": return_expr,
                "return_vars": return_vars,  # NOW EXTRACTED FROM AST!
                "has_jsx": has_jsx,  # NEW: Track JSX returns
                "returns_component": returns_component,  # NEW: Track if returning a component
                "return_index": return_index  # NEW: Track multiple returns per function
            })

        # Recurse through children
        for child in node.get("children", []):
            traverse(child, depth + 1)

    # Start traversal
    traverse(ast_root)

    # CRITICAL FIX: Deduplicate returns by (line, function_name)
    # WHY: Same issue as assignments - AST traverse visits nodes multiple times
    # NOTE: PRIMARY KEY is (file, line, function_name) but file is added by orchestrator
    seen = set()
    deduped = []
    for r in returns:
        key = (r['line'], r['function_name'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # Debug output for JSX detection
    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(returns) != len(deduped):
            print(f"[AST_DEBUG] TypeScript returns deduplication: {len(returns)} -> {len(deduped)} ({len(returns) - len(deduped)} duplicates removed)", file=sys.stderr)
        jsx_returns = [r for r in deduped if r.get("has_jsx")]
        print(f"[DEBUG] Found {len(deduped)} total returns, {len(jsx_returns)} with JSX", file=sys.stderr)
        if jsx_returns and len(jsx_returns) < 5:
            for r in jsx_returns[:3]:
                print(f"[DEBUG]   JSX return in {r['function_name']} at line {r['line']}: {r['return_expr'][:50]}...", file=sys.stderr)

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

    # Get the actual tree structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return cfgs

    # Get data from Phase 5 payload
    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "cfg" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG] extract_typescript_cfg: Using PRE-EXTRACTED CFG data ({len(extracted_data['cfg'])} CFGs)")
        return extracted_data["cfg"]

    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] extract_typescript_cfg: No 'cfg' key found in extracted_data.")

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

    # Get the semantic AST root
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return object_literals

    # PHASE 5: Check for pre-extracted data FIRST
    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "object_literals" in extracted_data:
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys
            print(f"[DEBUG] extract_typescript_object_literals: Using PRE-EXTRACTED data ({len(extracted_data['object_literals'])} literals)", file=sys.stderr)
        return extracted_data["object_literals"]

    ast_root = actual_tree.get("ast", {})
    if not ast_root:
        return object_literals

    # For text extraction, we need the original content
    content = tree.get("content", "")

    # Build scope map for accurate function context
    scope_map = build_scope_map(ast_root)

    def _get_ts_value(value_node):
        """Helper to extract text from a value node."""
        if not value_node or not isinstance(value_node, dict):
            return ""
        # The 'text' field populated by the JS helper is the most reliable source
        return value_node.get("text", "")[:250]  # Limit size for database

    def _get_ts_name(name_node):
        """Helper to extract a name identifier."""
        if not name_node or not isinstance(name_node, dict):
            return "<unknown>"
        return name_node.get("name") or name_node.get("escapedText") or name_node.get("text", "<unknown>")

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

                object_literals.append({
                    "line": prop_line,
                    "variable_name": var_name,
                    "property_name": prop_name,
                    "property_value": prop_value,
                    "property_type": prop_type,
                    "nested_level": 0,
                    "in_function": in_function
                })

            elif prop_kind == "ShorthandPropertyAssignment":
                prop_name = _get_ts_name(prop.get("name"))
                object_literals.append({
                    "line": prop_line,
                    "variable_name": var_name,
                    "property_name": prop_name,
                    "property_value": prop_name,
                    "property_type": "shorthand",
                    "nested_level": 0,
                    "in_function": in_function
                })

    # CRITICAL FIX: Idempotent traversal to prevent duplicate entries
    # Track visited nodes by (line, column, kind) to avoid processing same node multiple times
    visited_nodes = set()

    def traverse(node, depth=0):
        if depth > 100 or not isinstance(node, dict):
            return

        # CRITICAL FIX: Idempotency check - prevent processing same node twice
        node_id = (node.get("line"), node.get("column", 0), node.get("kind"))
        if node_id in visited_nodes:
            return  # This node has already been processed
        visited_nodes.add(node_id)

        kind = node.get("kind")
        line = node.get("line", 0)
        in_function = scope_map.get(line, "global")

        # Pattern 1: Variable Declaration (const x = { ... })
        if kind == "VariableDeclaration":
            initializer = node.get("initializer")
            if initializer and initializer.get("kind") == "ObjectLiteralExpression":
                var_name = _get_ts_name(node.get("name"))
                _extract_from_object_node(initializer, var_name, in_function, line)

        # Pattern 2: Assignment (x = { ... })
        elif kind == "BinaryExpression" and node.get("operatorToken", {}).get("kind") == "EqualsToken":
            right = node.get("right")
            if right and right.get("kind") == "ObjectLiteralExpression":
                var_name = _get_ts_value(node.get("left"))
                _extract_from_object_node(right, var_name, in_function, line)

        # Pattern 3: Return statement (return { ... })
        elif kind == "ReturnStatement":
            expr = node.get("expression")
            if expr and expr.get("kind") == "ObjectLiteralExpression":
                # Use function name for context
                var_name = f"<return:{in_function}>"
                _extract_from_object_node(expr, var_name, in_function, line)

        # Pattern 4: Function argument (fn({ ... })) ← CRITICAL FOR SEQUELIZE/PRISMA
        elif kind == "CallExpression":
            # Get arguments from either 'arguments' field or children[1:] structure
            args = node.get("arguments", [])
            if not args:
                children = node.get("children", [])
                # First child is the function expression, rest are arguments
                args = children[1:] if len(children) > 1 else []

            # Check each argument for object literals
            for i, arg in enumerate(args):
                if isinstance(arg, dict) and arg.get("kind") == "ObjectLiteralExpression":
                    # Get function name for context
                    callee_name = _canonical_callee_from_call(node) or "unknown"
                    var_name = f"<arg{i}:{callee_name}>"
                    _extract_from_object_node(arg, var_name, in_function, arg.get("line", line))

        # Pattern 5: Array element ([{ id: 1 }, { id: 2 }])
        elif kind == "ArrayLiteralExpression":
            elements = node.get("elements", node.get("children", []))
            for i, elem in enumerate(elements):
                if isinstance(elem, dict) and elem.get("kind") == "ObjectLiteralExpression":
                    var_name = f"<array_elem{i}>"
                    _extract_from_object_node(elem, var_name, in_function, elem.get("line", line))

        # Pattern 6: Nested property (const x = { config: { port: 3000 } })
        elif kind == "PropertyAssignment":
            init = node.get("initializer")
            if init and init.get("kind") == "ObjectLiteralExpression":
                prop_name = _get_ts_name(node.get("name"))
                var_name = f"<property:{prop_name}>"
                _extract_from_object_node(init, var_name, in_function, line)

        # Pattern 7: Class property (class C { config = { debug: true } })
        elif kind == "PropertyDeclaration":
            init = node.get("initializer")
            if init and init.get("kind") == "ObjectLiteralExpression":
                prop_name = _get_ts_name(node.get("name"))
                var_name = f"<class_property:{prop_name}>"
                _extract_from_object_node(init, var_name, in_function, line)

        # Recurse through all children
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
    block_counter = [0]  # Mutable counter for closures

    def get_next_block_id():
        block_counter[0] += 1
        return block_counter[0]

    # Extract function name
    func_name = 'anonymous'
    name_node = func_node.get('name')
    if isinstance(name_node, dict):
        func_name = name_node.get('text', 'anonymous')
    elif isinstance(name_node, str):
        func_name = name_node

    # CRITICAL FIX: Get full function line range for proper block spanning
    # Entry and exit blocks MUST span the entire function body so get_containing_function
    # can correctly identify ANY line within the function as belonging to it
    func_start_line = func_node.get('line', 1)
    func_end_line = func_node.get('endLine', func_start_line)

    # Entry block
    entry_id = get_next_block_id()

    blocks.append({
        'id': entry_id,
        'type': 'entry',
        'start_line': func_start_line,
        'end_line': func_end_line,  # FIXED: Use function's end line, not start line
        'statements': []
    })

    # Find function body in children
    body_node = None
    for child in func_node.get('children', []):
        if isinstance(child, dict) and child.get('kind') in ['Block', 'BlockStatement']:
            body_node = child
            break

    if not body_node:
        # No body found - might be abstract or interface method
        return None

    # Process function body
    exit_id = get_next_block_id()

    # Process all statements in body
    def process_node(node, current_id, depth=0):
        """Process a node and build CFG blocks."""
        if depth > 50 or not isinstance(node, dict):
            return current_id

        kind = node.get('kind', '')
        line = node.get('line', func_start_line)

        if kind == 'IfStatement':
            # Create condition block
            cond_id = get_next_block_id()
            blocks.append({
                'id': cond_id,
                'type': 'condition',
                'start_line': line,
                'end_line': line,
                'condition': extract_condition_text(node),
                'statements': [{'type': 'if', 'line': line}]
            })
            edges.append({'source': current_id, 'target': cond_id, 'type': 'normal'})

            # Process then branch
            then_id = get_next_block_id()
            blocks.append({
                'id': then_id,
                'type': 'basic',
                'start_line': line,
                'end_line': line,
                'statements': []
            })
            edges.append({'source': cond_id, 'target': then_id, 'type': 'true'})

            # Process then body
            then_stmt = get_child_by_kind(node, 'Block')
            if then_stmt:
                then_id = process_children(then_stmt, then_id, depth + 1)

            # Process else branch if exists
            else_stmt = None
            for i, child in enumerate(node.get('children', [])):
                if i > 0 and child.get('kind') == 'Block':
                    # Second Block is else
                    else_stmt = child
                    break
                elif child.get('kind') == 'IfStatement':
                    # else if
                    else_stmt = child
                    break

            if else_stmt:
                else_id = get_next_block_id()
                blocks.append({
                    'id': else_id,
                    'type': 'basic',
                    'start_line': else_stmt.get('line', line),
                    'end_line': else_stmt.get('line', line),
                    'statements': []
                })
                edges.append({'source': cond_id, 'target': else_id, 'type': 'false'})

                if else_stmt.get('kind') == 'IfStatement':
                    # else if - process as nested if
                    else_id = process_node(else_stmt, else_id, depth + 1)
                else:
                    # else block
                    else_id = process_children(else_stmt, else_id, depth + 1)

                # Merge point
                merge_id = get_next_block_id()
                blocks.append({
                    'id': merge_id,
                    'type': 'merge',
                    'start_line': line,
                    'end_line': line,
                    'statements': []
                })
                edges.append({'source': then_id, 'target': merge_id, 'type': 'normal'})
                edges.append({'source': else_id, 'target': merge_id, 'type': 'normal'})
                return merge_id
            else:
                # No else - false goes to next
                merge_id = get_next_block_id()
                blocks.append({
                    'id': merge_id,
                    'type': 'merge',
                    'start_line': line,
                    'end_line': line,
                    'statements': []
                })
                edges.append({'source': cond_id, 'target': merge_id, 'type': 'false'})
                edges.append({'source': then_id, 'target': merge_id, 'type': 'normal'})
                return merge_id

        elif kind in ['ForStatement', 'ForInStatement', 'ForOfStatement', 'WhileStatement', 'DoWhileStatement']:
            # Create loop condition block
            loop_id = get_next_block_id()
            blocks.append({
                'id': loop_id,
                'type': 'loop_condition',
                'start_line': line,
                'end_line': line,
                'condition': extract_condition_text(node),
                'statements': [{'type': 'loop', 'line': line}]
            })
            edges.append({'source': current_id, 'target': loop_id, 'type': 'normal'})

            # Create loop body block
            body_id = get_next_block_id()
            blocks.append({
                'id': body_id,
                'type': 'loop_body',
                'start_line': line,
                'end_line': line,
                'statements': []
            })
            edges.append({'source': loop_id, 'target': body_id, 'type': 'true'})

            # Process loop body
            loop_body = get_child_by_kind(node, 'Block')
            if loop_body:
                body_id = process_children(loop_body, body_id, depth + 1)

            # Back edge to condition
            edges.append({'source': body_id, 'target': loop_id, 'type': 'back_edge'})

            # Exit from loop
            exit_loop_id = get_next_block_id()
            blocks.append({
                'id': exit_loop_id,
                'type': 'merge',
                'start_line': line,
                'end_line': line,
                'statements': []
            })
            edges.append({'source': loop_id, 'target': exit_loop_id, 'type': 'false'})

            return exit_loop_id

        elif kind == 'ReturnStatement':
            # Create return block linking to exit
            ret_id = get_next_block_id()
            blocks.append({
                'id': ret_id,
                'type': 'return',
                'start_line': line,
                'end_line': line,
                'statements': [{'type': 'return', 'line': line}]
            })
            edges.append({'source': current_id, 'target': ret_id, 'type': 'normal'})
            edges.append({'source': ret_id, 'target': exit_id, 'type': 'normal'})
            return None  # No successor

        elif kind == 'TryStatement':
            # Get try body to determine block span
            try_body = get_child_by_kind(node, 'Block')
            try_end_line = try_body.get('endLine', line) if try_body else line

            # Create try block - FIXED: Span from try keyword to end of try body
            try_id = get_next_block_id()
            blocks.append({
                'id': try_id,
                'type': 'try',
                'start_line': line,
                'end_line': try_end_line,  # FIXED: Use try body's endLine
                'statements': [{'type': 'try', 'line': line}]
            })
            edges.append({'source': current_id, 'target': try_id, 'type': 'normal'})

            # Process try body
            if try_body:
                try_id = process_children(try_body, try_id, depth + 1)

            # Process catch block
            catch_block = None
            for child in node.get('children', []):
                if child.get('kind') == 'CatchClause':
                    catch_block = child
                    break

            if catch_block:
                # Get catch body to determine block span
                catch_body = get_child_by_kind(catch_block, 'Block')
                catch_start_line = catch_block.get('line', line)
                catch_end_line = catch_body.get('endLine', catch_start_line) if catch_body else catch_start_line

                catch_id = get_next_block_id()
                blocks.append({
                    'id': catch_id,
                    'type': 'except',
                    'start_line': catch_start_line,
                    'end_line': catch_end_line,  # FIXED: Use catch body's endLine
                    'statements': [{'type': 'catch', 'line': catch_start_line}]
                })
                edges.append({'source': try_id, 'target': catch_id, 'type': 'exception'})

                # Process catch body
                if catch_body:
                    catch_id = process_children(catch_body, catch_id, depth + 1)

                # Merge after try-catch
                merge_id = get_next_block_id()
                blocks.append({
                    'id': merge_id,
                    'type': 'merge',
                    'start_line': line,
                    'end_line': line,
                    'statements': []
                })
                edges.append({'source': try_id, 'target': merge_id, 'type': 'normal'})
                edges.append({'source': catch_id, 'target': merge_id, 'type': 'normal'})

                return merge_id

            return try_id

        elif kind == 'SwitchStatement':
            # Create switch condition block
            switch_id = get_next_block_id()
            blocks.append({
                'id': switch_id,
                'type': 'condition',
                'start_line': line,
                'end_line': line,
                'condition': 'switch',
                'statements': [{'type': 'switch', 'line': line}]
            })
            edges.append({'source': current_id, 'target': switch_id, 'type': 'normal'})

            # Process cases
            case_ids = []
            for child in node.get('children', []):
                if child.get('kind') in ['CaseClause', 'DefaultClause']:
                    case_id = get_next_block_id()
                    blocks.append({
                        'id': case_id,
                        'type': 'basic',
                        'start_line': child.get('line', line),
                        'end_line': child.get('line', line),
                        'statements': []
                    })
                    edges.append({'source': switch_id, 'target': case_id, 'type': 'case'})

                    # Process case statements
                    case_id = process_children(child, case_id, depth + 1)
                    case_ids.append(case_id)

            # Merge after switch
            merge_id = get_next_block_id()
            blocks.append({
                'id': merge_id,
                'type': 'merge',
                'start_line': line,
                'end_line': line,
                'statements': []
            })

            for case_id in case_ids:
                if case_id:  # Could be None if has return
                    edges.append({'source': case_id, 'target': merge_id, 'type': 'normal'})

            return merge_id

        # Default: not a control flow statement
        return current_id

    def process_children(parent_node, current_id, depth):
        """Process all children of a node."""
        for child in parent_node.get('children', []):
            new_id = process_node(child, current_id, depth)
            if new_id is not None:
                current_id = new_id
        return current_id

    def get_child_by_kind(node, kind):
        """Get first child with specified kind."""
        for child in node.get('children', []):
            if child.get('kind') == kind:
                return child
        return None

    def extract_condition_text(node):
        """Extract condition text from control flow node."""
        # Try to find the condition/test expression
        for child in node.get('children', []):
            if child.get('kind') in ['BinaryExpression', 'UnaryExpression', 'Identifier',
                                     'CallExpression', 'MemberExpression', 'PropertyAccessExpression']:
                return child.get('text', 'condition')
        return 'condition'

    # Start processing from entry
    current_id = entry_id
    current_id = process_children(body_node, current_id, 0)

    # Add exit block
    blocks.append({
        'id': exit_id,
        'type': 'exit',
        'start_line': func_start_line,  # FIXED: Use function's start line
        'end_line': func_end_line,      # FIXED: Use function's end line
        'statements': []
    })

    # Connect last block to exit if not already connected
    if current_id:
        edges.append({'source': current_id, 'target': exit_id, 'type': 'normal'})

    return {
        'function_name': func_name,
        'blocks': blocks,
        'edges': edges
    }
