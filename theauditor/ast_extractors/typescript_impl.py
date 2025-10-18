"""TypeScript/JavaScript semantic AST extraction implementations.

This module contains all TypeScript compiler API extraction logic for semantic analysis.
"""

import os
from typing import Any, List, Dict, Optional


def _strip_comment_prefix(text: Optional[str]) -> str:
    """Return the first non-comment, non-empty line from the given text."""
    if not text:
        return ""

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or stripped == "*/":
            continue
        return stripped

    return text.strip()


def _identifier_from_node(node: Any) -> str:
    """Extract a single identifier string from a semantic AST node."""
    if not isinstance(node, dict):
        return ""

    # Preferred fields in priority order
    candidates: List[str] = []

    text_value = node.get("text")
    if isinstance(text_value, str):
        candidates.append(text_value)

    escaped_text = node.get("escapedText")
    if isinstance(escaped_text, str):
        candidates.append(escaped_text)

    name_field = node.get("name")
    if isinstance(name_field, str):
        candidates.append(name_field)
    elif isinstance(name_field, dict):
        nested = _identifier_from_node(name_field)
        if nested:
            candidates.append(nested)

    for candidate in candidates:
        cleaned = _strip_comment_prefix(candidate)
        if cleaned:
            return cleaned

    return ""


def _canonical_member_name(node: Any) -> str:
    """Build a canonical member path (e.g., app.get) from a semantic AST node."""
    if not isinstance(node, dict):
        return ""

    kind = node.get("kind")

    if kind == "Identifier" or kind == "PrivateIdentifier":
        return _identifier_from_node(node)

    if kind == "ThisKeyword":
        return "this"

    if kind == "SuperKeyword":
        return "super"

    if kind == "PropertyAccessExpression":
        left = _canonical_member_name(node.get("expression"))

        right_node = node.get("name")
        if isinstance(right_node, dict):
            right = _canonical_member_name(right_node)
        elif isinstance(right_node, str):
            right = _strip_comment_prefix(right_node)
        else:
            right = ""

        if not right and isinstance(node.get("children"), list):
            for child in node["children"]:
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    right = _canonical_member_name(child)
                    if right:
                        break

        if left and right:
            return f"{left}.{right}"
        return right or left

    if kind == "CallExpression":
        return _canonical_member_name(node.get("expression"))

    if kind == "ElementAccessExpression":
        base = _canonical_member_name(node.get("expression"))
        argument = _canonical_member_name(node.get("argumentExpression"))
        if base and argument:
            return f"{base}[{argument}]"
        return base

    return _identifier_from_node(node)


def _canonical_callee_from_call(node: Dict[str, Any]) -> str:
    """Return a sanitized callee name for a CallExpression node."""
    if not isinstance(node, dict):
        return ""

    expression = node.get("expression")
    name = _canonical_member_name(expression)
    if name:
        return sanitize_call_name(_strip_comment_prefix(name))

    return sanitize_call_name(_strip_comment_prefix(_identifier_from_node(node)))

from .base import (
    extract_vars_from_typescript_node,
    sanitize_call_name,
)  # AST-pure variable extraction and call normalization


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
        full_name = _canonical_member_name(node)

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
        name = _canonical_callee_from_call(node)

        if name:
            symbols.append({
                "name": name,
                "line": node.get("line", 0),
                "column": node.get("column", 0),
                "type": "call"
            })

    # Identifier nodes that might be property accesses or function references
    elif kind == "Identifier":
        text = _strip_comment_prefix(node.get("text", ""))
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

    # DEDUPLICATION: With full AST traversal, same symbol may appear via multiple paths
    # (e.g., req.body as PropertyAccessExpression + nested Identifier)
    # Only deduplicate at top level (depth=0) to avoid redundant work in recursion
    if depth == 0 and symbols:
        seen = {}
        deduped = []
        for sym in symbols:
            key = (sym.get("name"), sym.get("line"), sym.get("column", 0), sym.get("type"))
            if key not in seen:
                seen[key] = True
                deduped.append(sym)
        return deduped

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

    # Track class context for qualified names
    class_stack = []

    def collect_functions(node, depth=0):
        """Recursively collect all function declarations with their line ranges.

        CRITICAL FIX: Now handles PropertyDeclaration with wrapped functions
        (e.g., create = this.asyncHandler(async (req, res) => {}))
        """
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind", "")

        # Track class context for qualified names
        if kind == "ClassDeclaration":
            class_name = "UnknownClass"
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    class_name = child.get("text", "UnknownClass")
                    break
            class_stack.append(class_name)

            # Recurse through class members
            for child in node.get("children", []):
                collect_functions(child, depth + 1)

            # Pop class context
            if class_stack:
                class_stack.pop()
            return  # Don't double-traverse

        # CRITICAL FIX: Handle PropertyDeclaration with function initializers
        # Patterns:
        #   1. Direct: create = async (req, res) => {}
        #   2. Wrapped: create = this.asyncHandler(async (req, res) => {})
        if kind == "PropertyDeclaration":
            initializer = node.get("initializer")
            if not initializer:
                # Search for actual initializer in children (may be after modifiers like static/readonly)
                children = node.get("children", [])
                for child in children:
                    if isinstance(child, dict):
                        child_kind = child.get("kind", "")
                        # Skip modifiers and identifiers, find the actual initializer
                        if child_kind not in ["Identifier", "StaticKeyword", "ReadonlyKeyword",
                                              "PrivateKeyword", "PublicKeyword", "ProtectedKeyword",
                                              "AsyncKeyword", "AbstractKeyword", "DeclareKeyword"]:
                            initializer = child
                            break

            if isinstance(initializer, dict):
                init_kind = initializer.get("kind", "")


                # Pattern 1: Direct arrow function or function expression
                is_arrow_func = init_kind in ["ArrowFunction", "FunctionExpression"]

                # Pattern 2: Wrapped function (CallExpression wrapping a function)
                is_wrapped_func = False
                func_start_line = None
                func_end_line = None

                if init_kind == "CallExpression":
                    call_args = initializer.get("arguments", initializer.get("children", [])[1:])
                    for arg in call_args:
                        if isinstance(arg, dict) and arg.get("kind") in ["ArrowFunction", "FunctionExpression"]:
                            is_wrapped_func = True
                            func_start_line = arg.get("line", node.get("line", 0))
                            func_end_line = arg.get("endLine")
                            break
                elif is_arrow_func:
                    # Direct arrow/function expression - use initializer's line range
                    func_start_line = initializer.get("line", node.get("line", 0))
                    func_end_line = initializer.get("endLine")

                if is_arrow_func or is_wrapped_func:
                    # Get property name
                    prop_name = ""
                    for child in node.get("children", []):
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            prop_name = child.get("text", "")
                            break

                    # Build qualified name with class context
                    func_name = f"{class_stack[-1]}.{prop_name}" if class_stack else prop_name

                    # Use the function's line range (direct or wrapped)
                    start_line = func_start_line or node.get("line", 0)
                    end_line = func_end_line

                    if not end_line:
                        # Conservative estimate
                        end_line = start_line + 50

                    if start_line > 0:
                        function_ranges.append({
                            "name": func_name,
                            "start": start_line,
                            "end": end_line,
                            "depth": depth,
                            "is_property_function": True,  # Mark for debugging
                            "is_wrapped": is_wrapped_func,
                            "is_direct_arrow": is_arrow_func
                        })

                    # Don't recurse into children - we already handled the function
                    return

        # Standard function nodes
        if kind in ["FunctionDeclaration", "MethodDeclaration", "ArrowFunction",
                    "FunctionExpression", "Constructor", "GetAccessor", "SetAccessor"]:
            # Get function name
            name = node.get("name", "anonymous")

            # Convert dict names to strings if needed
            if isinstance(name, dict):
                name = name.get("text", "anonymous")

            # For MethodDeclaration, add class context
            if kind == "MethodDeclaration" and class_stack:
                # Get method name from children
                method_name = ""
                for child in node.get("children", []):
                    if isinstance(child, dict) and child.get("kind") == "Identifier":
                        method_name = child.get("text", "")
                        break
                if method_name:
                    name = f"{class_stack[-1]}.{method_name}"

            # Get line range
            start_line = node.get("line", 0)
            end_line = node.get("endLine")

            if not end_line:
                end_line = start_line + 50

            if start_line > 0:
                function_ranges.append({
                    "name": name,
                    "start": start_line,
                    "end": end_line,
                    "depth": depth
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
    if function_ranges:
        max_line = max(func["end"] for func in function_ranges)
        for line in range(1, max_line + 1):
            if line not in scope_map:
                scope_map[line] = "global"

    return scope_map


def extract_typescript_functions_for_symbols(tree: Dict, parser_self) -> List[Dict]:
    """Extract function metadata from TypeScript semantic AST for symbol table.

    COMPREHENSIVE FIX for TypeScript class property arrow functions.

    This implementation uses HYBRID APPROACH:
    1. AST TRAVERSAL - Detects ALL function patterns including PropertyDeclaration
    2. SYMBOL ENRICHMENT - Merges rich type metadata from TypeScript compiler

    Function patterns detected:
    1. FunctionDeclaration - standard function declarations
    2. MethodDeclaration - class methods (async method() {})
    3. PropertyDeclaration - class property arrow functions (prop = async () => {})
    4. Constructor - class constructors
    5. GetAccessor/SetAccessor - property accessors

    CRITICAL: PropertyDeclaration with ArrowFunction/FunctionExpression initializers
    are now properly detected and extracted with full class context.

    This unblocks multi-hop taint analysis by ensuring ALL functions are indexed.
    """
    functions = []

    # Get the full AST root for traversal
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree

    if not actual_tree or not actual_tree.get("success"):
        return functions

    ast_root = actual_tree.get("ast", {})

    if not ast_root:
        return functions

    # PHASE 2: Type metadata now comes directly from AST nodes (serializeNode inline extraction)
    # No longer need symbol_metadata lookup - removed for single-pass architecture

    # Skip parameters - these should NEVER be marked as functions
    PARAMETER_NAMES = {"req", "res", "next", "err", "error", "ctx", "request", "response", "callback", "done", "cb"}

    # Track class context as we traverse
    class_stack = []  # Stack of class names for proper scoping

    # PHASE 2: Removed enrich_with_metadata() - type info now read directly from AST nodes

    def traverse(node, depth=0):
        """Recursively traverse AST extracting ALL function patterns."""
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind", "")

        # Track class context for qualified names
        if kind == "ClassDeclaration":
            # CORRECT: Look for Identifier in children, not node.get("name")
            class_name = "UnknownClass"
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    class_name = child.get("text", "UnknownClass")
                    break
            class_stack.append(class_name)

            # Recurse through class members
            for child in node.get("children", []):
                traverse(child, depth + 1)

            # Pop class context
            if class_stack:
                class_stack.pop()
            return  # Don't double-traverse

        is_function_like = False
        func_name = ""
        line = node.get("line", 0)
        func_entry = {
            "line": line,
            "col": node.get("column", 0),
            "column": node.get("column", 0),
            "end_line": node.get("endLine"),
            "type": "function",
            "kind": kind,
        }
        base_name_for_enrichment = ""

        # Pattern 1: Standard FunctionDeclaration
        if kind == "FunctionDeclaration":
            is_function_like = True
            # CORRECT: Look for Identifier in children
            func_name = ""
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    func_name = child.get("text", "")
                    break
            base_name_for_enrichment = func_name

        # Pattern 2: MethodDeclaration (class methods)
        elif kind == "MethodDeclaration":
            is_function_like = True
            # CORRECT: Look for Identifier in children
            method_name = ""
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    method_name = child.get("text", "")
                    break
            base_name_for_enrichment = method_name
            func_name = f"{class_stack[-1]}.{method_name}" if class_stack else method_name

        # Pattern 3: PropertyDeclaration with ArrowFunction/FunctionExpression (CRITICAL FIX)
        elif kind == "PropertyDeclaration":
            initializer = node.get("initializer")
            if not initializer:  # Fallback for different AST structures
                children = node.get("children", [])
                if len(children) > 1:
                    initializer = children[1]

            if isinstance(initializer, dict):
                init_kind = initializer.get("kind", "")
                is_arrow_func = init_kind in ["ArrowFunction", "FunctionExpression"]
                is_wrapped_func = False
                # Handle wrapped functions like this.asyncHandler(async () => {})
                if init_kind == "CallExpression":
                    call_args = initializer.get("arguments", initializer.get("children", [])[1:])
                    for arg in call_args:
                        if isinstance(arg, dict) and arg.get("kind") in ["ArrowFunction", "FunctionExpression"]:
                            is_wrapped_func = True
                            break

                if is_arrow_func or is_wrapped_func:
                    is_function_like = True
                    # CORRECT: Look for Identifier in children
                    prop_name = ""
                    for child in node.get("children", []):
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            prop_name = child.get("text", "")
                            break
                    base_name_for_enrichment = prop_name
                    func_name = f"{class_stack[-1]}.{prop_name}" if class_stack else prop_name

        # Pattern 4: Constructor, GetAccessor, SetAccessor
        elif kind in ["Constructor", "GetAccessor", "SetAccessor"]:
            is_function_like = True
            if kind == "Constructor":
                accessor_name = "constructor"
            else:
                # CORRECT: Look for Identifier in children
                accessor_name = ""
                for child in node.get("children", []):
                    if isinstance(child, dict) and child.get("kind") == "Identifier":
                        accessor_name = child.get("text", "")
                        break
            base_name_for_enrichment = accessor_name
            prefix = ""
            if kind == "GetAccessor": prefix = "get "
            if kind == "SetAccessor": prefix = "set "
            func_name = f"{class_stack[-1]}.{prefix}{accessor_name}" if class_stack else f"{prefix}{accessor_name}"

        if is_function_like and func_name and func_name not in PARAMETER_NAMES:
            func_entry["name"] = func_name

            # PHASE 2: Read type metadata directly from AST node (inline extraction from serializeNode)
            for metadata_key in (
                "type_annotation",
                "is_any",
                "is_unknown",
                "is_generic",
                "has_type_params",
                "type_params",
                "return_type",
                "extends_type",
            ):
                if metadata_key in node:
                    func_entry[metadata_key] = node.get(metadata_key)

            functions.append(func_entry)

        # Recurse through all children
        for child in node.get("children", []):
            traverse(child, depth + 1)

    # Start traversal from AST root
    traverse(ast_root)

    import sys
    import os

    # DEDUPLICATION: With full AST traversal, functions may be extracted multiple times
    # (e.g., from both AST nodes and symbol metadata)
    # Use (name, line, column) as unique key
    seen = {}
    deduped_functions = []
    for func in functions:
        key = (func.get("name"), func.get("line"), func.get("col", func.get("column", 0)))
        if key not in seen:
            seen[key] = True
            deduped_functions.append(func)

    if os.environ.get("THEAUDITOR_DEBUG"):
        print(f"[DEBUG] extract_typescript_functions_for_symbols: Found {len(deduped_functions)} functions (deduped from {len(functions)})", file=sys.stderr)
        for func in deduped_functions[:5]:
            print(f"[DEBUG]   {func['name']} at line {func['line']}", file=sys.stderr)

    return deduped_functions


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
    """Extract class definitions from TypeScript semantic AST.

    PHASE 2: Rewritten to use single-pass AST traversal instead of filtered symbols.
    """
    classes = []

    # Get the actual AST tree
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if not actual_tree or not actual_tree.get("success"):
        return classes

    ast_root = actual_tree.get("ast", {})
    if not ast_root:
        return classes

    def traverse(node, depth=0):
        """Recursively traverse AST extracting class and interface declarations."""
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind", "")

        # Extract class and interface declarations
        if kind in ["ClassDeclaration", "InterfaceDeclaration"]:
            # Extract class/interface name
            class_name = node.get("name", "")
            if isinstance(class_name, dict):
                class_name = class_name.get("text", class_name.get("name", ""))

            # Try alternate name extraction from children
            if not class_name or class_name == "anonymous":
                for child in node.get("children", []):
                    if isinstance(child, dict) and child.get("kind") == "Identifier":
                        class_name = child.get("text", "")
                        break

            if class_name and class_name != "anonymous":
                class_entry = {
                    "name": class_name,
                    "line": node.get("line", 0),
                    "col": node.get("column", node.get("col", 0)),
                    "column": node.get("column", 0),
                    "type": "class",
                }

                # PHASE 2: Read type metadata directly from AST node
                for key in (
                    "type_annotation",
                    "extends_type",
                    "type_params",
                    "has_type_params",
                ):
                    if key in node:
                        class_entry[key] = node.get(key)

                classes.append(class_entry)

        # Recurse through all children
        for child in node.get("children", []):
            traverse(child, depth + 1)

    # Start traversal from AST root
    traverse(ast_root)

    # DEDUPLICATION: With full AST traversal, classes may be extracted multiple times
    # Use (name, line, column) as unique key
    seen = {}
    deduped_classes = []
    for cls in classes:
        key = (cls.get("name"), cls.get("line"), cls.get("col", cls.get("column", 0)))
        if key not in seen:
            seen[key] = True
            deduped_classes.append(cls)

    return deduped_classes


def extract_typescript_calls(tree: Dict, parser_self) -> List[Dict]:
    """Extract function calls from TypeScript semantic AST.

    PHASE 3: Single-pass extraction using only AST traversal.
    Removed filtered symbols loop and deduplication logic.
    """
    calls = []

    # Get actual tree structure
    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if actual_tree and actual_tree.get("success"):
        ast_root = actual_tree.get("ast")
        if ast_root:
            # Single-pass AST traversal extracts ALL calls/properties
            calls = extract_semantic_ast_symbols(ast_root)

    return calls


def extract_typescript_imports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract import statements from TypeScript semantic AST."""
    imports = []
    
    # Use TypeScript compiler API data
    for imp in tree.get("imports", []):
        specifiers = imp.get("specifiers", []) or []
        namespace = None
        default = None
        named = []

        for spec in specifiers:
            if isinstance(spec, dict):
                if spec.get("isNamespace"):
                    namespace = spec.get("name")
                elif spec.get("isDefault"):
                    default = spec.get("name")
                elif spec.get("isNamed"):
                    named.append(spec.get("name"))
            elif isinstance(spec, str):
                named.append(spec)

        import_entry = {
            "source": imp.get("kind", "import"),
            "target": imp.get("module"),
            "type": imp.get("kind", "import"),
            "line": imp.get("line", 0),
            "specifiers": specifiers,
            "namespace": imp.get("namespace", namespace),
            "default": imp.get("default", default),
            "names": imp.get("names", named),
        }

        if not import_entry.get("text"):
            module = import_entry.get("target") or ""
            parts = []
            if import_entry["default"]:
                parts.append(import_entry["default"])
            if import_entry["namespace"]:
                parts.append(f"* as {import_entry['namespace']}")
            if import_entry["names"]:
                parts.append("{ " + ", ".join(import_entry["names"]) + " }")

            if parts:
                import_entry["text"] = f"import {', '.join(parts)} from '{module}'"
            else:
                import_entry["text"] = f"import '{module}'"

        imports.append(import_entry)
    
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
                callee_file_path = node.get("calleeFilePath")  # May be None if resolution failed

                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] CallExpression: caller={caller_function}, callee={callee_name}, callee_file={callee_file_path}, args={len(arguments)}")

                # Get parameters for this function if we know them
                callee_params = function_params.get(callee_name.split(".")[-1], [])

                # Process arguments
                for i, arg in enumerate(arguments):
                    if isinstance(arg, dict):
                        raw_arg_text = arg.get("text", "")
                        arg_text = _strip_comment_prefix(raw_arg_text) or raw_arg_text.strip()
                        param_name = callee_params[i] if i < len(callee_params) else f"arg{i}"

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


def extract_typescript_object_literals(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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

    def traverse(node, depth=0):
        if depth > 100 or not isinstance(node, dict):
            return

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
