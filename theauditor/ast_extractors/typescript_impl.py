"""TypeScript/JavaScript semantic AST extraction implementations.

This module contains all TypeScript compiler API extraction logic for semantic analysis.
"""

import os
from typing import Any, List, Dict, Optional

from .base import extract_vars_from_tree_sitter_expr  # DEPRECATED: Returns [] to enforce AST purity


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


# ========================================================
# COMPREHENSIVE JSX NODE TYPE DEFINITIONS
# ========================================================
# Complete enumeration of all JSX node types for proper detection

JSX_NODE_KINDS = frozenset([
    # Element nodes
    "JsxElement",              # <div>...</div>
    "JsxSelfClosingElement",   # <img />
    "JsxFragment",             # <>...</>

    # Structural nodes
    "JsxOpeningElement",       # <div>
    "JsxClosingElement",       # </div>
    "JsxOpeningFragment",      # <>
    "JsxClosingFragment",      # </>

    # Content nodes
    "JsxText",                 # Text between tags
    "JsxExpression",           # {expression}
    "JsxExpressionContainer",  # Container for expressions
    "JsxSpreadChild",          # {...spread}

    # Attribute nodes
    "JsxAttribute",            # name="value"
    "JsxAttributes",           # Collection of attributes
    "JsxSpreadAttribute",      # {...props}

    # Namespace nodes
    "JsxNamespacedName",       # svg:path

    # Edge cases
    "JsxMemberExpression",     # Component.SubComponent
    "JsxIdentifier",           # Component name identifier
])


def detect_jsx_in_node(node, depth=0):
    """Comprehensively detect JSX in AST node.

    This function handles both preserved and transformed JSX:
    - Preserved mode: Detects actual JSX syntax nodes
    - Transformed mode: Detects React.createElement patterns

    Returns:
        Tuple of (has_jsx, returns_component)
    """
    if depth > 50 or not isinstance(node, dict):
        return False, False

    kind = node.get('kind', '')

    # Direct JSX node - check against complete set
    if kind in JSX_NODE_KINDS:
        # Check if it's a component (capital letter)
        if kind in ["JsxElement", "JsxSelfClosingElement"]:
            tag_name = extract_jsx_tag_name(node)
            is_component = tag_name and tag_name[0].isupper() if tag_name else False
            return True, is_component
        return True, False

    # Container nodes that might have JSX
    if kind in ["ParenthesizedExpression", "ConditionalExpression",
                "BinaryExpression", "LogicalExpression", "ArrayLiteralExpression",
                "ObjectLiteralExpression", "ArrowFunction", "FunctionExpression"]:
        # Deep search for JSX in complex expressions
        for key in ['expression', 'initializer', 'left', 'right', 'operand',
                    'condition', 'whenTrue', 'whenFalse', 'arguments', 'elements',
                    'properties', 'body', 'statements', 'children']:
            if key in node:
                child = node[key]
                if isinstance(child, list):
                    for item in child:
                        has_jsx, is_comp = detect_jsx_in_node(item, depth + 1)
                        if has_jsx:
                            return has_jsx, is_comp
                elif isinstance(child, dict):
                    has_jsx, is_comp = detect_jsx_in_node(child, depth + 1)
                    if has_jsx:
                        return has_jsx, is_comp

    # React.createElement pattern (for transformed mode)
    if kind == "CallExpression":
        callee = node.get('expression', {})
        if isinstance(callee, dict):
            callee_text = callee.get('text', '')
            if "React.createElement" in callee_text or "jsx" in callee_text or "_jsx" in callee_text:
                # This was JSX before transformation
                return True, analyze_create_element_component(node)

    return False, False


def extract_jsx_tag_name(node):
    """Extract tag name from JSX element node.

    Handles various JSX element structures to extract the tag name.
    """
    # For JsxElement with openingElement
    if 'openingElement' in node:
        opening = node['openingElement']
        if isinstance(opening, dict) and 'tagName' in opening:
            tag_name = opening['tagName']
            if isinstance(tag_name, dict):
                return tag_name.get('escapedText', '') or tag_name.get('text', '')

    # For JsxSelfClosingElement
    if 'tagName' in node:
        tag_name = node['tagName']
        if isinstance(tag_name, dict):
            return tag_name.get('escapedText', '') or tag_name.get('text', '')

    return None


def analyze_create_element_component(node):
    """Analyze React.createElement call to determine if it's a component.

    Components have capital letters or are passed as references.
    """
    if 'arguments' in node and isinstance(node['arguments'], list):
        if len(node['arguments']) > 0:
            first_arg = node['arguments'][0]
            if isinstance(first_arg, dict):
                # String literal component name
                if first_arg.get('kind') == 'StringLiteral':
                    text = first_arg.get('text', '')
                    return text and text[0].isupper()
                # Identifier (component reference)
                elif first_arg.get('kind') == 'Identifier':
                    text = first_arg.get('escapedText', '')
                    return text and text[0].isupper()
    return False


# Backward compatibility alias
def check_for_jsx(node, depth=0):
    """Legacy function name for backward compatibility."""
    return detect_jsx_in_node(node, depth)


def build_scope_map(ast_root: Dict) -> Dict[int, str]:
    """Build a map of line numbers to containing function names.

    This solves the core problem: traverse() loses track of which function it's in.
    By pre-mapping all line numbers to their containing functions, we can do O(1)
    lookups instead of broken recursive tracking.

    Returns:
        Dict mapping line number to function name for fast lookups
    """
    scope_map = {}
    function_ranges = []
    
    def collect_functions(node, depth=0, parent=None, grandparent=None, parent_name=None):
        """Recursively collect all function declarations with their line ranges.
        
        The JavaScript helper now provides accurate names using TypeScript's parent context.
        We simply trust those names here.
        """
        if depth > 100 or not isinstance(node, dict):
            return
        
        kind = node.get("kind", "")
        
        # Check if this is a function node
        if kind in ["FunctionDeclaration", "MethodDeclaration", "ArrowFunction", 
                    "FunctionExpression", "Constructor", "GetAccessor", "SetAccessor"]:
            # CRITICAL: Trust the name from JavaScript helper - it has perfect parent context
            name = node.get("name", "anonymous")
            
            # Convert dict names to strings if needed
            if isinstance(name, dict):
                name = name.get("text", "anonymous")
            
            # Get line range - TypeScript provides this!
            start_line = node.get("line", 0)
            end_line = node.get("endLine")
            
            # If no endLine, estimate based on next sibling or use heuristic
            if not end_line:
                # Conservative estimate: 50 lines for anonymous functions
                end_line = start_line + 50
            
            if start_line > 0:  # Valid line number
                function_ranges.append({
                    "name": name,
                    "start": start_line,
                    "end": end_line,
                    "depth": depth  # Track nesting depth for precedence
                })
        
        # Recurse through children
        for child in node.get("children", []):
            collect_functions(child, depth + 1)
    
    # Collect all functions
    collect_functions(ast_root)
    
    # Sort by depth (deeper functions take precedence) then by start line
    function_ranges.sort(key=lambda x: (x["start"], -x["depth"]))
    
    # Build the line-to-function map
    # Process in reverse order so deeper (more specific) functions override
    for func in reversed(function_ranges):
        for line in range(func["start"], func["end"] + 1):
            # Deeper/inner functions take precedence
            if line not in scope_map or func["depth"] > 0:
                scope_map[line] = func["name"]
    
    # Fill in any gaps with "global"
    # This ensures every line has a scope, even outside functions
    if function_ranges:
        max_line = max(func["end"] for func in function_ranges)
        for line in range(1, max_line + 1):
            if line not in scope_map:
                scope_map[line] = "global"
    
    return scope_map


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
                                
                                if os.environ.get("THEAUDITOR_DEBUG"):
                                    import sys
                                    print(f"[AST_DEBUG] Found TS assignment: {target_var} = {source_expr[:30]}... at line {line} in {in_function}", file=sys.stderr)
                                assignments.append({
                                    "target_var": target_var,
                                    "source_expr": source_expr,
                                    "line": line,
                                    "in_function": in_function,  # NOW ACCURATE!
                                    # EDGE CASE DISCOVERY: source_vars now [] due to regex removal
                                    # If taint analysis breaks, extract vars from AST node, not text
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
                                            line = element.get("line", node.get("line", 0))
                                            # CRITICAL FIX: Get function from scope map
                                            in_function = scope_map.get(line, "global")
                                            
                                            assignments.append({
                                                "target_var": target_var,
                                                "source_expr": source_expr, # CRITICAL: Source is the original object/array
                                                "line": line,
                                                "in_function": in_function,  # NOW ACCURATE!
                                                # EDGE CASE DISCOVERY: source_vars now [] due to regex removal
                                                # For destructuring, extract from source_node AST, not text
                                                "source_vars": extract_vars_from_tree_sitter_expr(source_expr)
                                            })
                            else:
                                # --- Standard, non-destructured assignment ---
                                target_var = target_node.get("text", "")
                                source_expr = source_node.get("text", "")
                                if target_var and source_expr:
                                    line = node.get("line", 0)
                                    # CRITICAL FIX: Get function from scope map
                                    in_function = scope_map.get(line, "global")
                                    
                                    if os.environ.get("THEAUDITOR_DEBUG"):
                                        import sys
                                        print(f"[AST_DEBUG] Found assignment: {target_var} = {source_expr[:50]}... at line {line} in {in_function}", file=sys.stderr)
                                    assignments.append({
                                        "target_var": target_var,
                                        "source_expr": source_expr,
                                        "line": line,
                                        "in_function": in_function,  # NOW ACCURATE!
                                        # EDGE CASE DISCOVERY: source_vars now [] due to regex removal
                                        # Extract from source_node AST if needed for taint analysis
                                        "source_vars": extract_vars_from_tree_sitter_expr(source_expr)
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

    def traverse(node, depth=0):  # No more current_function parameter!
        """Traverse AST extracting calls. Scope is determined by line number lookup."""
        if depth > 100 or not isinstance(node, dict):
            return

        try:
            kind = node.get("kind", "")

            # CallExpression: function calls
            if kind == "CallExpression":
                line = node.get("line", 0)
                
                # CRITICAL FIX: Get caller from scope map using line number
                # This is O(1) and accurate, unlike the old recursive tracking
                caller_function = scope_map.get(line, "global")
                
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
                
                # Get function name from expression
                callee_name = "unknown"
                if isinstance(expression, dict):
                    callee_name = expression.get("text", "unknown")
                
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] CallExpression: caller={caller_function}, callee={callee_name}, args={len(arguments)}")

                # Get parameters for this function if we know them
                callee_params = function_params.get(callee_name.split(".")[-1], [])

                # Process arguments
                for i, arg in enumerate(arguments):
                    if isinstance(arg, dict):
                        arg_text = arg.get("text", "")
                        param_name = callee_params[i] if i < len(callee_params) else f"arg{i}"

                        calls.append({
                            "line": line,
                            "caller_function": caller_function,  # NOW ACCURATE from scope map!
                            "callee_function": callee_name,
                            "argument_index": i,
                            "argument_expr": arg_text,
                            "param_name": param_name
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


def extract_typescript_returns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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

            returns.append({
                "function_name": current_function,  # NOW ACCURATE!
                "line": line,
                "return_expr": return_expr,
                # EDGE CASE DISCOVERY: return_vars now [] due to regex removal
                # Extract from expr_node AST if needed for data flow analysis
                "return_vars": extract_vars_from_tree_sitter_expr(return_expr),
                "has_jsx": has_jsx,  # NEW: Track JSX returns
                "returns_component": returns_component,  # NEW: Track if returning a component
                "return_index": return_index  # NEW: Track multiple returns per function
            })

        # Recurse through children
        for child in node.get("children", []):
            traverse(child, depth + 1)

    # Start traversal
    traverse(ast_root)

    # Debug output for JSX detection
    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        jsx_returns = [r for r in returns if r.get("has_jsx")]
        print(f"[DEBUG] Found {len(returns)} total returns, {len(jsx_returns)} with JSX", file=sys.stderr)
        if jsx_returns and len(jsx_returns) < 5:
            for r in jsx_returns[:3]:
                print(f"[DEBUG]   JSX return in {r['function_name']} at line {r['line']}: {r['return_expr'][:50]}...", file=sys.stderr)

    return returns


def extract_typescript_cfg(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract control flow graphs for all TypeScript/JavaScript functions.

    Returns CFG data matching the database schema expectations.
    """
    cfgs = []

    # Get complete function AST nodes
    func_nodes = extract_typescript_function_nodes(tree, parser_self)

    for func_node in func_nodes:
        cfg = build_typescript_function_cfg(func_node)
        if cfg:
            cfgs.append(cfg)

    return cfgs


def build_typescript_function_cfg(func_node: Dict) -> Dict[str, Any]:
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

    # Entry block
    entry_id = get_next_block_id()
    start_line = func_node.get('line', 1)

    blocks.append({
        'id': entry_id,
        'type': 'entry',
        'start_line': start_line,
        'end_line': start_line,
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
        line = node.get('line', start_line)

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
            # Create try block
            try_id = get_next_block_id()
            blocks.append({
                'id': try_id,
                'type': 'try',
                'start_line': line,
                'end_line': line,
                'statements': [{'type': 'try', 'line': line}]
            })
            edges.append({'source': current_id, 'target': try_id, 'type': 'normal'})

            # Process try body
            try_body = get_child_by_kind(node, 'Block')
            if try_body:
                try_id = process_children(try_body, try_id, depth + 1)

            # Process catch block
            catch_block = None
            for child in node.get('children', []):
                if child.get('kind') == 'CatchClause':
                    catch_block = child
                    break

            if catch_block:
                catch_id = get_next_block_id()
                blocks.append({
                    'id': catch_id,
                    'type': 'except',
                    'start_line': catch_block.get('line', line),
                    'end_line': catch_block.get('line', line),
                    'statements': [{'type': 'catch', 'line': catch_block.get('line', line)}]
                })
                edges.append({'source': try_id, 'target': catch_id, 'type': 'exception'})

                # Process catch body
                catch_body = get_child_by_kind(catch_block, 'Block')
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
        'start_line': func_node.get('endLine', start_line),
        'end_line': func_node.get('endLine', start_line),
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