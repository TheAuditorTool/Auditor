"""TypeScript/JavaScript semantic AST extraction implementations.

This module contains all TypeScript compiler API extraction logic for semantic analysis.
"""

import os
from typing import Any, List, Dict, Optional

from .base import extract_vars_from_tree_sitter_expr


def extract_semantic_ast_symbols(node, depth=0):
    """Extract symbols from TypeScript semantic AST including property accesses.
    
    This is a helper used by multiple extraction functions.
    """
    symbols = []
    if depth > 100 or not isinstance(node, dict):
        return symbols
    
    kind = node.get("kind")
    
    # PropertyAccessExpression: req.body, req.params, res.send, etc.
    if kind == "PropertyAccessExpression":
        # Use the authoritative text from TypeScript compiler (now restored)
        full_name = node.get("text", "").strip()
        
        # Only fall back to reconstruction if text is missing (shouldn't happen now)
        if not full_name:
            # Build the full property access chain
            name_parts = []
            current = node
            while current and isinstance(current, dict):
                if current.get("name"):
                    if isinstance(current["name"], dict) and current["name"].get("name"):
                        name_parts.append(str(current["name"]["name"]))
                    elif isinstance(current["name"], str):
                        name_parts.append(current["name"])
                # Look for the expression part
                if current.get("children"):
                    for child in current["children"]:
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            if child.get("text"):
                                name_parts.append(child["text"])
                current = current.get("expression")
            
            if name_parts:
                full_name = ".".join(reversed(name_parts))
            else:
                full_name = None
        
        if full_name:
            # CRITICAL FIX: Extract ALL property accesses for taint analysis
            # The taint analyzer will filter for the specific sources it needs
            # This ensures we capture req.body, req.query, request.params, etc.
            
            # Default all property accesses as "property" type
            db_type = "property"
            
            # Override only for known sink patterns that should be "call" type
            if any(sink in full_name for sink in ["res.send", "res.render", "res.json", "response.write", "innerHTML", "outerHTML", "exec", "eval", "system", "spawn"]):
                db_type = "call"  # Taint analyzer looks for sinks as calls
            
            symbols.append({
                "name": full_name,
                "line": node.get("line", 0),
                "column": node.get("column", 0),
                "type": db_type
            })
    
    # CallExpression: function calls including method calls
    elif kind == "CallExpression":
        # Use text field first if available (now restored)
        name = None
        if node.get("text"):
            # Extract function name from text
            text = node["text"]
            if "(" in text:
                name = text.split("(")[0].strip()
        elif node.get("name"):
            name = node["name"]
        
        # Also check for method calls on children
        if not name and node.get("children"):
            for child in node["children"]:
                if isinstance(child, dict):
                    if child.get("kind") == "PropertyAccessExpression":
                        name = child.get("text", "").split("(")[0].strip()
                        break
                    elif child.get("text") and "." in child.get("text", ""):
                        name = child["text"].split("(")[0].strip()
                        break
        
        if name:
            symbols.append({
                "name": name,
                "line": node.get("line", 0),
                "column": node.get("column", 0),
                "type": "call"
            })
    
    # Identifier nodes that might be property accesses or function references
    elif kind == "Identifier":
        text = node.get("text", "")
        # Check if it looks like a property access pattern
        if "." in text:
            # Determine type based on pattern
            db_type = "property"
            # Check for sink patterns
            if any(sink in text for sink in ["res.send", "res.render", "res.json", "response.write"]):
                db_type = "call"
            
            symbols.append({
                "name": text,
                "line": node.get("line", 0),
                "column": node.get("column", 0),
                "type": db_type
            })
    
    # Recurse through children
    for child in node.get("children", []):
        symbols.extend(extract_semantic_ast_symbols(child, depth + 1))
    
    return symbols


def extract_typescript_functions_for_symbols(tree: Dict, parser_self) -> List[Dict]:
    """Extract function metadata from TypeScript semantic AST for symbol table.
    
    This returns simplified metadata for the symbol table (name, line, type).
    For CFG extraction, use extract_typescript_function_nodes instead.
    """
    functions = []
    
    # Use symbols for quick metadata extraction
    for symbol in tree.get("symbols", []):
        ts_kind = symbol.get("kind", 0)
        symbol_name = symbol.get("name", "")
        
        if not symbol_name or symbol_name == "anonymous":
            continue
        
        # Skip parameters
        PARAMETER_NAMES = {"req", "res", "next", "err", "error", "ctx", "request", "response", "callback", "done", "cb"}
        if symbol_name in PARAMETER_NAMES:
            continue
        
        # Check if this is a function symbol
        is_function = False
        if isinstance(ts_kind, str):
            if "Function" in ts_kind or "Method" in ts_kind:
                is_function = True
        elif isinstance(ts_kind, (int, float)):
            if ts_kind == 8388608:  # Parameter
                continue
            elif ts_kind in [16, 8192, 16384]:  # Function, Method, Constructor
                is_function = True
        
        if is_function:
            functions.append({
                "name": symbol_name,
                "line": symbol.get("line", 0),
                "type": "function",
                "kind": ts_kind
            })
    
    return functions


def extract_typescript_functions(tree: Dict, parser_self) -> List[Dict]:
    """For backward compatibility, returns metadata for symbols."""
    return extract_typescript_functions_for_symbols(tree, parser_self)


def extract_typescript_function_nodes(tree: Dict, parser_self) -> List[Dict]:
    """Extract COMPLETE function AST nodes from TypeScript semantic AST.
    
    This returns the full AST node for each function, including its body,
    which is essential for Control Flow Graph construction.
    """
    functions = []
    
    # Get the actual AST tree, not the symbols
    # The AST can be in different locations depending on how it was parsed
    ast_root = tree.get("ast", {})
    if not ast_root and "tree" in tree and isinstance(tree["tree"], dict):
        # For semantic_ast type, the AST is nested at tree['tree']['ast']
        ast_root = tree["tree"].get("ast", {})
    
    if not ast_root:
        return []
    
    def traverse_for_functions(node, depth=0):
        """Recursively find all function nodes in the AST."""
        if depth > 100 or not isinstance(node, dict):
            return
        
        kind = node.get("kind")
        
        # These are the TypeScript AST node types for functions
        function_kinds = [
            "FunctionDeclaration",
            "MethodDeclaration", 
            "ArrowFunction",
            "FunctionExpression",
            "Constructor",
            "GetAccessor",
            "SetAccessor"
        ]
        
        if kind in function_kinds:
            # Return the ENTIRE node - it contains everything including body
            functions.append(node)
            # Still traverse children for nested functions
            for child in node.get("children", []):
                traverse_for_functions(child, depth + 1)
        else:
            # Not a function, keep looking in children
            for child in node.get("children", []):
                traverse_for_functions(child, depth + 1)
    
    traverse_for_functions(ast_root)
    return functions


def extract_typescript_classes(tree: Dict, parser_self) -> List[Dict]:
    """Extract class definitions from TypeScript semantic AST."""
    classes = []
    
    # CRITICAL FIX: Symbols are at tree["symbols"], not tree["tree"]["symbols"]
    for symbol in tree.get("symbols", []):
        ts_kind = symbol.get("kind", 0)
        symbol_name = symbol.get("name", "")
        
        if not symbol_name or symbol_name == "anonymous":
            continue
        
        # Check if this is a class symbol
        is_class = False
        if isinstance(ts_kind, str):
            if "Class" in ts_kind or "Interface" in ts_kind:
                is_class = True
        elif isinstance(ts_kind, (int, float)):
            # TypeScript SymbolFlags: Class = 32, Interface = 64
            if ts_kind in [32, 64]:
                is_class = True
        
        if is_class:
            classes.append({
                "name": symbol_name,
                "line": symbol.get("line", 0),
                "column": 0,
                "type": "class",
                "kind": ts_kind
            })
    
    return classes


def extract_typescript_calls(tree: Dict, parser_self) -> List[Dict]:
    """Extract function calls from TypeScript semantic AST."""
    calls = []
    
    # Common parameter names that should NEVER be marked as functions
    PARAMETER_NAMES = {"req", "res", "next", "err", "error", "ctx", "request", "response", "callback", "done", "cb"}
    
    # Use the symbols already extracted by TypeScript compiler
    # CRITICAL FIX: Symbols are at tree["symbols"], not tree["tree"]["symbols"]
    for symbol in tree.get("symbols", []):
        symbol_name = symbol.get("name", "")
        ts_kind = symbol.get("kind", 0)
        
        # Skip empty/anonymous symbols
        if not symbol_name or symbol_name == "anonymous":
            continue
        
        # CRITICAL FIX: Skip known parameter names that are incorrectly marked as functions
        # These are function parameters, not function definitions
        if symbol_name in PARAMETER_NAMES:
            # These should be marked as properties/variables for taint analysis
            if symbol_name in ["req", "request", "ctx"]:
                calls.append({
                    "name": symbol_name,
                    "line": symbol.get("line", 0),
                    "column": 0,
                    "type": "property"  # Mark as property for taint source detection
                })
            continue  # Skip further processing for parameters
        
        # CRITICAL FIX: Properly categorize based on TypeScript SymbolFlags
        # The 'kind' field from TypeScript can be:
        # - A string like "Function", "Method", "Property" (when ts.SymbolFlags mapping works)
        # - A number representing the flag value (when mapping fails)
        # TypeScript SymbolFlags values:
        # Function = 16, Method = 8192, Property = 98304, Variable = 3, etc.
        
        db_type = "call"  # Default for unknown types
        
        # Check if kind is a string (successful mapping in helper script)
        if isinstance(ts_kind, str):
            # Only mark as function if it's REALLY a function and not a parameter
            if ("Function" in ts_kind or "Method" in ts_kind) and symbol_name not in PARAMETER_NAMES:
                db_type = "function"
            elif "Property" in ts_kind:
                db_type = "property"
            elif "Variable" in ts_kind or "Let" in ts_kind or "Const" in ts_kind:
                # Variables could be sources if they match patterns
                if any(pattern in symbol_name for pattern in ["req", "request", "ctx", "body", "params", "query", "headers"]):
                    db_type = "property"
                else:
                    db_type = "call"
        # Check numeric flags (when string mapping failed)
        elif isinstance(ts_kind, (int, float)):
            # TypeScript SymbolFlags from typescript.d.ts:
            # Function = 16, Method = 8192, Constructor = 16384
            # Property = 98304, Variable = 3, Let = 1, Const = 2
            # Parameter = 8388608 (0x800000)
            
            # CRITICAL: Skip parameter flag (8388608)
            if ts_kind == 8388608:
                # This is a parameter, not a function
                if symbol_name in ["req", "request", "ctx"]:
                    db_type = "property"  # Mark as property for taint analysis
                else:
                    continue  # Skip other parameters
            elif ts_kind in [16, 8192, 16384] and symbol_name not in PARAMETER_NAMES:  # Function, Method, Constructor
                db_type = "function"
            elif ts_kind in [98304, 4, 1048576]:  # Property, EnumMember, Accessor
                db_type = "property"
            elif ts_kind in [3, 1, 2]:  # Variable, Let, Const
                # Check if it looks like a source
                if any(pattern in symbol_name for pattern in ["req", "request", "ctx", "body", "params", "query", "headers"]):
                    db_type = "property"
        
        # Override based on name patterns (for calls and property accesses)
        if "." in symbol_name:
            # Source patterns (user input)
            if any(pattern in symbol_name for pattern in ["req.", "request.", "ctx.", "event.", "body", "params", "query", "headers", "cookies"]):
                db_type = "property"
            # Sink patterns (dangerous functions)
            elif any(pattern in symbol_name for pattern in ["res.send", "res.render", "res.json", "response.write", "exec", "eval"]):
                db_type = "call"
        
        calls.append({
            "name": symbol_name,
            "line": symbol.get("line", 0),
            "column": 0,
            "type": db_type
        })
    
    # Also traverse AST for specific patterns
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if actual_tree and actual_tree.get("success"):
        ast_root = actual_tree.get("ast")
        if ast_root:
            calls.extend(extract_semantic_ast_symbols(ast_root))
    
    return calls


def extract_typescript_imports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract import statements from TypeScript semantic AST."""
    imports = []
    
    # Use TypeScript compiler API data
    for imp in tree.get("imports", []):
        imports.append({
            "source": imp.get("kind", "import"),
            "target": imp.get("module"),
            "type": imp.get("kind", "import"),
            "line": imp.get("line", 0),
            "specifiers": imp.get("specifiers", [])
        })
    
    return imports


def extract_typescript_exports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract export statements from TypeScript semantic AST.
    
    Currently returns empty list - exports aren't extracted by semantic parser yet.
    """
    return []


def extract_typescript_properties(tree: Dict, parser_self) -> List[Dict]:
    """Extract property accesses from TypeScript semantic AST."""
    properties = []
    
    # Already handled in extract_calls via extract_semantic_ast_symbols
    # But we can also extract them specifically here
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if actual_tree and actual_tree.get("success"):
        ast_root = actual_tree.get("ast")
        if ast_root:
            symbols = extract_semantic_ast_symbols(ast_root)
            # Filter for property accesses only
            properties = [s for s in symbols if s.get("type") == "property"]
    
    return properties


def extract_typescript_assignments(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract ALL assignment patterns from TypeScript semantic AST, including destructuring."""
    assignments = []
    
    # Check if parsing was successful - handle nested structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        if os.environ.get("THEAUDITOR_DEBUG"):
            import sys
            print(f"[AST_DEBUG] extract_typescript_assignments: No success in tree", file=sys.stderr)
        return assignments
    
    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        print(f"[AST_DEBUG] extract_typescript_assignments: Starting extraction", file=sys.stderr)

    def traverse(node, current_function="global", depth=0):
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

            # --- Function Context Tracking ---
            new_function = current_function
            if kind in ["FunctionDeclaration", "MethodDeclaration", "ArrowFunction", "FunctionExpression"]:
                name_node = node.get("name")
                if name_node and isinstance(name_node, dict):
                    new_function = name_node.get("text", "anonymous")
                else:
                    new_function = "anonymous"

            # --- Assignment Extraction ---
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
                                if os.environ.get("THEAUDITOR_DEBUG"):
                                    import sys
                                    print(f"[AST_DEBUG] Found TS assignment: {target_var} = {source_expr[:30]}... at line {node.get('line', 0)}", file=sys.stderr)
                                assignments.append({
                                    "target_var": target_var,
                                    "source_expr": source_expr,
                                    "line": node.get("line", 0),
                                    "in_function": current_function,
                                    "source_vars": extract_vars_from_tree_sitter_expr(source_expr)
                                })
                    else:
                        # BinaryExpression - use the original logic
                        target_node = node.get("left")
                        source_node = node.get("right")
                        
                        if isinstance(target_node, dict) and isinstance(source_node, dict):
                            # --- ENHANCEMENT: Handle Destructuring ---
                            if target_node.get("kind") in ["ObjectBindingPattern", "ArrayBindingPattern"]:
                                source_expr = source_node.get("text", "unknown_source")
                                # For each element in the destructuring, create a separate assignment
                                for element in target_node.get("elements", []):
                                    if isinstance(element, dict) and element.get("name"):
                                        target_var = element.get("name", {}).get("text")
                                        if target_var:
                                            assignments.append({
                                                "target_var": target_var,
                                                "source_expr": source_expr, # CRITICAL: Source is the original object/array
                                                "line": element.get("line", node.get("line", 0)),
                                                "in_function": current_function,
                                                "source_vars": extract_vars_from_tree_sitter_expr(source_expr)
                                            })
                            else:
                                # --- Standard, non-destructured assignment ---
                                target_var = target_node.get("text", "")
                                source_expr = source_node.get("text", "")
                                if target_var and source_expr:
                                    if os.environ.get("THEAUDITOR_DEBUG"):
                                        import sys
                                        print(f"[AST_DEBUG] Found assignment: {target_var} = {source_expr[:50]}... at line {node.get('line', 0)}", file=sys.stderr)
                                    assignments.append({
                                        "target_var": target_var,
                                        "source_expr": source_expr,
                                        "line": node.get("line", 0),
                                        "in_function": current_function,
                                        "source_vars": extract_vars_from_tree_sitter_expr(source_expr)
                                    })

            # Recurse with updated function context
            for child in node.get("children", []):
                traverse(child, new_function, depth + 1)

        except Exception:
            # This safety net catches any unexpected AST structures
            pass

    # Get AST from the correct location after unwrapping
    ast_root = actual_tree.get("ast", {})
    traverse(ast_root)
    
    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        print(f"[AST_DEBUG] extract_typescript_assignments: Found {len(assignments)} assignments", file=sys.stderr)
        if assignments and len(assignments) < 5:
            for a in assignments[:3]:
                print(f"[AST_DEBUG]   Example: {a['target_var']} = {a['source_expr'][:30]}...", file=sys.stderr)
    
    return assignments


def extract_typescript_function_params(tree: Dict, parser_self) -> Dict[str, List[str]]:
    """Extract function parameters from TypeScript semantic AST."""
    func_params = {}
    
    # Check if parsing was successful - handle nested structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return func_params
    
    def traverse(node, depth=0):
        if depth > 100 or not isinstance(node, dict):
            return
        
        kind = node.get("kind")
        
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
            
            # Extract parameter names
            # FIX: In TypeScript AST, parameters are direct children with kind="Parameter"
            params = []
            
            # Look in children for Parameter nodes
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Parameter":
                    # Found a parameter - get its text directly
                    param_text = child.get("text", "")
                    if param_text:
                        params.append(param_text)
            
            # Fallback to old structure if no parameters found
            if not params:
                param_nodes = node.get("parameters", [])
                for param in param_nodes:
                    if isinstance(param, dict) and param.get("name"):
                        param_name_node = param.get("name")
                        if isinstance(param_name_node, dict):
                            params.append(param_name_node.get("text", ""))
                        elif isinstance(param_name_node, str):
                            params.append(param_name_node)
            
            if func_name != "anonymous" and params:
                func_params[func_name] = params
        
        # Recurse through children
        for child in node.get("children", []):
            traverse(child, depth + 1)
    
    # Get AST from the correct location after unwrapping
    ast_root = actual_tree.get("ast", {})
    traverse(ast_root)
    
    return func_params


def extract_typescript_calls_with_args(tree: Dict, function_params: Dict[str, List[str]], parser_self) -> List[Dict[str, Any]]:
    """Extract function calls with arguments from TypeScript semantic AST."""
    calls = []
    
    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] extract_typescript_calls_with_args: tree type={type(tree)}, success={tree.get('success') if tree else 'N/A'}")
    
    # Check if parsing was successful - handle nested structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG] extract_typescript_calls_with_args: Returning early - no tree or no success")
        return calls

    def traverse(node, current_function="global", depth=0):
        if depth > 100 or not isinstance(node, dict):
            return

        try:
            kind = node.get("kind", "")

            # Track function context
            new_function = current_function
            if kind in ["FunctionDeclaration", "MethodDeclaration", "ArrowFunction", "FunctionExpression"]:
                name_node = node.get("name")
                if name_node and isinstance(name_node, dict):
                    new_function = name_node.get("text", "anonymous")
                else:
                    new_function = "anonymous"

            # CallExpression: function calls
            if kind == "CallExpression":
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] Found CallExpression at line {node.get('line', 0)}")
                
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
                
                # Get function name from expression
                callee_name = "unknown"
                if isinstance(expression, dict):
                    callee_name = expression.get("text", "unknown")
                
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] CallExpression: callee={callee_name}, args={len(arguments)}")
                    if arguments:
                        print(f"[DEBUG] First arg: {arguments[0].get('text', 'N/A') if isinstance(arguments[0], dict) else arguments[0]}")

                # Get parameters for this function if we know them
                callee_params = function_params.get(callee_name.split(".")[-1], [])

                # Process arguments
                for i, arg in enumerate(arguments):
                    if isinstance(arg, dict):
                        arg_text = arg.get("text", "")
                        param_name = callee_params[i] if i < len(callee_params) else f"arg{i}"

                        calls.append({
                            "line": node.get("line", 0),
                            "caller_function": current_function,
                            "callee_function": callee_name,
                            "argument_index": i,
                            "argument_expr": arg_text,
                            "param_name": param_name
                        })

            # Recurse with updated function context
            for child in node.get("children", []):
                traverse(child, new_function, depth + 1)

        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Error in extract_typescript_calls_with_args: {e}")

    # Get AST from the correct location after unwrapping
    ast_root = actual_tree.get("ast", {})
    traverse(ast_root)

    # Debug output
    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] Extracted {len(calls)} function calls with args from semantic AST")

    return calls


def extract_typescript_returns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract return statements from TypeScript semantic AST."""
    returns = []
    
    # Check if parsing was successful - handle nested structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return returns
    
    # Traverse AST looking for return statements
    def traverse(node, current_function="global", depth=0):
        if depth > 100 or not isinstance(node, dict):
            return
        
        kind = node.get("kind")
        
        # Track current function context
        if kind in ["FunctionDeclaration", "FunctionExpression", "ArrowFunction", "MethodDeclaration"]:
            # Extract function name if available
            name_node = node.get("name")
            if name_node and isinstance(name_node, dict):
                current_function = name_node.get("text", "anonymous")
            else:
                current_function = "anonymous"
        
        # ReturnStatement
        elif kind == "ReturnStatement":
            expr_node = node.get("expression", {})
            if isinstance(expr_node, dict):
                return_expr = expr_node.get("text", "")
            else:
                return_expr = str(expr_node) if expr_node else "undefined"
            
            returns.append({
                "function_name": current_function,
                "line": node.get("line", 0),
                "return_expr": return_expr,
                "return_vars": extract_vars_from_tree_sitter_expr(return_expr)
            })
        
        # Recurse through children
        for child in node.get("children", []):
            traverse(child, current_function, depth + 1)
    
    # Get AST from the correct location after unwrapping
    ast_root = actual_tree.get("ast", {})
    traverse(ast_root)
    
    return returns