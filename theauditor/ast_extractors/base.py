"""Base utilities and shared helpers for AST extraction.

This module contains utility functions shared across all language implementations.

ARCHITECTURAL PRINCIPLE: NO REGEX FOR EXTRACTION
================================================
This module must remain regex-free for code extraction. We have ASTs - use them.
The only regex that ever existed here was extract_vars_from_tree_sitter_expr(),
which has been deprecated and gutted to enforce proper AST traversal.

If you're tempted to add regex:
1. STOP
2. You already have an AST node
3. Traverse the AST structure instead
4. Text parsing is a lazy escape hatch that defeats the entire purpose

This is a deliberate architectural decision to maintain extraction purity.
"""

import ast
from typing import Any, List, Optional
from pathlib import Path


def get_node_name(node: Any) -> str:
    """Get the name from an AST node, handling different node types.
    
    Works with Python's built-in AST nodes.
    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{get_node_name(node.value)}.{node.attr}"
    elif isinstance(node, ast.Call):
        return get_node_name(node.func)
    elif isinstance(node, str):
        return node
    else:
        return "unknown"


def extract_vars_from_expr(node: ast.AST) -> List[str]:
    """Extract all variable names from a Python expression.

    Walks the AST to find all Name and Attribute nodes.
    """
    vars_list = []
    for subnode in ast.walk(node):
        if isinstance(subnode, ast.Name):
            vars_list.append(subnode.id)
        elif isinstance(subnode, ast.Attribute):
            # For x.y.z, get the full chain
            chain = []
            current = subnode
            while isinstance(current, ast.Attribute):
                chain.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                chain.append(current.id)
                vars_list.append(".".join(reversed(chain)))
    return vars_list


def extract_vars_from_typescript_node(node: Any, depth: int = 0) -> List[str]:
    """Extract all variable names from a TypeScript/JavaScript AST node.

    This is the AST-pure replacement for the gutted extract_vars_from_tree_sitter_expr().
    Recursively traverses the TypeScript compiler API AST to find all identifiers.

    Args:
        node: TypeScript AST node (Dict from semantic parser)
        depth: Recursion depth to prevent infinite loops

    Returns:
        List of variable names found in the expression

    Example:
        node = {"kind": "BinaryExpression", "text": "req.body.name", ...}
        returns ["req.body.name", "req.body", "req"]
    """
    if depth > 50 or not isinstance(node, dict):
        return []

    vars_list = []
    kind = node.get("kind", "")

    # PropertyAccessExpression: req.body, user.name, etc.
    if kind == "PropertyAccessExpression":
        # Use the authoritative text from TypeScript compiler
        full_text = node.get("text", "").strip()
        if full_text:
            vars_list.append(full_text)
            # Also add prefixes: req.body.name → ["req.body.name", "req.body", "req"]
            parts = full_text.split(".")
            for i in range(len(parts) - 1, 0, -1):
                prefix = ".".join(parts[:i])
                if prefix:
                    vars_list.append(prefix)

    # Identifier: single variable name
    elif kind == "Identifier":
        text = node.get("text", "").strip()
        if text:
            vars_list.append(text)

    # CallExpression: function calls - extract the callee
    elif kind == "CallExpression":
        # Don't include the call itself, but do include arguments
        pass

    # Recurse through children
    for child in node.get("children", []):
        if isinstance(child, dict):
            vars_list.extend(extract_vars_from_typescript_node(child, depth + 1))

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for var in vars_list:
        if var not in seen:
            seen.add(var)
            result.append(var)

    return result


def extract_vars_from_tree_sitter_expr(expr: str) -> List[str]:
    """DEPRECATED: DO NOT USE - This is a legacy regex fallback that violates AST purity.

    ARCHITECTURAL DECISION: We have the AST - extract variables from AST nodes, NOT text.

    This function was removed to enforce proper AST traversal. If you're calling this,
    you're doing text parsing when you should be traversing the AST structure.

    Why this is wrong:
    - We already parsed the code into an AST
    - Text parsing is fragile and misses context
    - Regex cannot understand scope, destructuring, or complex expressions
    - This creates a "lazy escape hatch" that prevents proper structural analysis

    What to do instead:
    - For assignments: The AST node already has source node - traverse it
    - For returns: The AST node already has expression node - traverse it
    - Use proper visitor patterns, not text matching

    If source_vars are critical for your use case, extract them from the AST node
    that you already have. Don't convert to text and re-parse with regex.

    CRITICAL: DO NOT add regex back. If this breaks something, fix the caller
    to use proper AST traversal, not text parsing.
    """
    # Return empty list to force callers to handle the absence of this data
    # This will surface edge cases where source_vars are actually needed
    return []


def sanitize_call_name(name: Any) -> str:
    """Normalize call expression names for downstream analysis.

    Removes argument lists, trailing dots, and extra whitespace so that
    `app.get('/users', handler)` and `router.post(`/foo`)` both normalize to
    `app.get` / `router.post`.
    """
    if not isinstance(name, str):
        return ""

    cleaned = name.strip()
    if not cleaned:
        return ""

    # Remove everything after the first parenthesis (argument list)
    paren_idx = cleaned.find('(')
    if paren_idx != -1:
        cleaned = cleaned[:paren_idx]

    # Collapse internal whitespace and trim trailing property separators
    cleaned = " ".join(cleaned.split())
    cleaned = cleaned.rstrip('.')

    return cleaned


def find_containing_function_python(tree: ast.AST, line: int) -> Optional[str]:
    """Find the function containing a given line in Python AST."""
    containing_func = None
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                if node.lineno <= line <= (node.end_lineno or node.lineno):
                    # Check if this is more specific than current containing_func
                    if containing_func is None or node.lineno > containing_func[1]:
                        containing_func = (node.name, node.lineno)
    
    return containing_func[0] if containing_func else None


def find_containing_function_tree_sitter(node: Any, content: str, language: str) -> Optional[str]:
    """Find the function containing a node in Tree-sitter AST.
    
    Walks up the tree to find parent function, handling all modern JS/TS patterns.
    """
    # Walk up the tree to find parent function
    current = node
    while current and hasattr(current, 'parent') and current.parent:
        current = current.parent
        if language in ["javascript", "typescript"]:
            # CRITICAL FIX: Handle ALL function patterns in modern JS/TS
            function_types = [
                "function_declaration",      # function foo() {}
                "function_expression",        # const foo = function() {}
                "arrow_function",            # const foo = () => {}
                "method_definition",         # class { foo() {} }
                "generator_function",        # function* foo() {}
                "async_function",           # async function foo() {}
            ]
            
            if current.type in function_types:
                # Special handling for arrow functions FIRST
                # They need different logic than regular functions
                if current.type == "arrow_function":
                    # Arrow functions don't have names directly, check parent
                    parent = current.parent if hasattr(current, 'parent') else None
                    if parent:
                        # Check if it's assigned to a variable: const foo = () => {}
                        if parent.type == "variable_declarator":
                            # Use field-based API to get the name
                            if hasattr(parent, 'child_by_field_name'):
                                name_node = parent.child_by_field_name('name')
                                if name_node and name_node.text:
                                    return name_node.text.decode("utf-8", errors="ignore")
                            # Fallback to child iteration
                            for child in parent.children:
                                if child.type == "identifier" and child != current:
                                    return child.text.decode("utf-8", errors="ignore")
                        # Check if it's a property: { foo: () => {} }
                        elif parent.type == "pair":
                            for child in parent.children:
                                if child.type in ["property_identifier", "identifier", "string"] and child != current:
                                    text = child.text.decode("utf-8", errors="ignore")
                                    # Remove quotes from string keys
                                    return text.strip('"\'')
                    # CRITICAL FIX (Lead Auditor feedback): Don't return anything here!
                    # Continue searching upward for containing named function
                    # This handles cases like: function outer() { arr.map(() => {}) }
                    # The arrow function should be tracked as within "outer", not "anonymous"
                    # Let the while loop continue to find outer function
                    continue  # Skip the rest and continue searching upward
                
                # For non-arrow functions, try field-based API first
                if hasattr(current, 'child_by_field_name'):
                    name_node = current.child_by_field_name('name')
                    if name_node and name_node.text:
                        return name_node.text.decode("utf-8", errors="ignore")
                
                # Fallback to child iteration for regular functions
                for child in current.children:
                    if child.type in ["identifier", "property_identifier"]:
                        return child.text.decode("utf-8", errors="ignore")
                
                # If still no name found for this regular function, it's anonymous
                return "anonymous"
                
        elif language == "python":
            if current.type == "function_definition":
                # Try field-based API first
                if hasattr(current, 'child_by_field_name'):
                    name_node = current.child_by_field_name('name')
                    if name_node and name_node.text:
                        return name_node.text.decode("utf-8", errors="ignore")
                # Fallback to child iteration
                for child in current.children:
                    if child.type == "identifier":
                        return child.text.decode("utf-8", errors="ignore")
    
    # If no function found, return "global" instead of None for better tracking
    return "global"


def detect_language(file_path: Path) -> str:
    """Detect language from file extension.
    
    Returns empty string for unsupported languages.
    """
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".vue": "javascript",  # Vue SFCs contain JavaScript/TypeScript
    }
    return ext_map.get(file_path.suffix.lower(), "")
