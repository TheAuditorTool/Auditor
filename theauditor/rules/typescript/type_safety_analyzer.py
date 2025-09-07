"""Security rules for detecting TypeScript type-related issues.

Supports:
- TypeScript (via TypeScript Compiler API semantic AST)
"""

from typing import List, Dict, Any


def find_typescript_type_issues(tree: Dict[str, Any], file_path: str) -> List[Dict[str, Any]]:
    """Find TypeScript type-related issues using semantic AST.
    
    This function operates on the rich AST provided by the TypeScript Compiler API
    to detect problematic type patterns including:
    - Explicit 'any' types
    - Unsafe type assertions (as any, as unknown)
    - Implicit 'any' from compiler diagnostics
    - Type suppression comments (@ts-ignore, @ts-nocheck)
    
    Args:
        tree: Semantic AST from TypeScript Compiler API
        file_path: Path to the TypeScript file being analyzed
        
    Returns:
        List of security findings with severity levels
    """
    findings = []
    
    # Check if we have a semantic AST with type information
    if not tree or tree.get("type") != "semantic_ast":
        return findings
    
    semantic_tree = tree.get("tree", {})
    if not semantic_tree or not semantic_tree.get("success"):
        return findings
    
    # 1. Check for explicit 'any' types in symbols
    for symbol in semantic_tree.get("symbols", []):
        if symbol.get("type") == "any":
            findings.append({
                "rule": "TYPESCRIPT_ANY_TYPE",
                "severity": "MEDIUM",
                "message": f"Symbol '{symbol.get('name')}' has explicit 'any' type",
                "file": file_path,
                "line": symbol.get("line", 0),
                "column": 0,
                "evidence": f"{symbol.get('name')}: any",
                "confidence": "HIGH"
            })
    
    # 2. Parse compiler diagnostics for implicit 'any' errors
    for diagnostic in semantic_tree.get("diagnostics", []):
        message = diagnostic.get("message", "")
        
        # TypeScript error codes for implicit any
        # TS7006: Parameter has implicit 'any' type
        # TS7008: Member has implicit 'any' type
        # TS7031: Binding element has implicit 'any' type
        if diagnostic.get("code") in [7006, 7008, 7031] or "implicit 'any'" in message.lower():
            findings.append({
                "rule": "TYPESCRIPT_IMPLICIT_ANY",
                "severity": "MEDIUM",
                "message": f"Implicit 'any' type: {message}",
                "file": file_path,
                "line": diagnostic.get("line", 0),
                "column": diagnostic.get("column", 0),
                "evidence": message[:200],
                "confidence": "HIGH"
            })
    
    # 3. Recursively search AST for problematic patterns
    def search_ast_node(node: Dict[str, Any], depth: int = 0) -> None:
        if depth > 100 or not isinstance(node, dict):
            return
        
        node_kind = node.get("kind", "")
        node_text = node.get("text", "")
        node_line = node.get("line", 0)
        node_column = node.get("column", 0)
        
        # Check for explicit 'any' keyword nodes
        if node_kind == "AnyKeyword":
            findings.append({
                "rule": "TYPESCRIPT_ANY_KEYWORD",
                "severity": "MEDIUM",
                "message": "Explicit 'any' type annotation detected",
                "file": file_path,
                "line": node_line,
                "column": node_column,
                "evidence": node_text[:100] if node_text else "any",
                "confidence": "HIGH"
            })
        
        # Check for unsafe type assertions (as any, as unknown)
        if node_kind == "AsExpression":
            type_node = node.get("type", {})
            if isinstance(type_node, dict):
                type_kind = type_node.get("kind", "")
                if type_kind == "AnyKeyword":
                    findings.append({
                        "rule": "TYPESCRIPT_UNSAFE_CAST_ANY",
                        "severity": "HIGH",
                        "message": "Unsafe type assertion to 'any' bypasses type checking",
                        "file": file_path,
                        "line": node_line,
                        "column": node_column,
                        "evidence": node_text[:100] if node_text else "as any",
                        "confidence": "HIGH"
                    })
                elif type_kind == "UnknownKeyword":
                    findings.append({
                        "rule": "TYPESCRIPT_UNSAFE_CAST_UNKNOWN",
                        "severity": "HIGH",
                        "message": "Unsafe type assertion to 'unknown' may hide type errors",
                        "file": file_path,
                        "line": node_line,
                        "column": node_column,
                        "evidence": node_text[:100] if node_text else "as unknown",
                        "confidence": "HIGH"
                    })
        
        # Check for type suppression comments
        if "@ts-ignore" in node_text or "@ts-nocheck" in node_text:
            findings.append({
                "rule": "TYPESCRIPT_TYPE_SUPPRESSION",
                "severity": "MEDIUM",
                "message": "TypeScript error suppression comment detected",
                "file": file_path,
                "line": node_line,
                "column": node_column,
                "evidence": node_text[:100],
                "confidence": "HIGH"
            })
        
        # Recursively check children
        for child in node.get("children", []):
            if isinstance(child, dict):
                search_ast_node(child, depth + 1)
    
    # Start recursive search from root AST node
    ast_root = semantic_tree.get("ast", {})
    if ast_root:
        search_ast_node(ast_root)
    
    return findings