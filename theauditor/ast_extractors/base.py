"""Base utilities and shared helpers for AST extraction."""

import ast
from pathlib import Path
from typing import Any


def get_node_name(node: Any) -> str:
    """Get the name from an AST node, handling different node types."""
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


def extract_vars_from_expr(node: ast.AST) -> list[str]:
    """Extract all variable names from a Python expression."""
    vars_list = []
    for subnode in ast.walk(node):
        if isinstance(subnode, ast.Name):
            vars_list.append(subnode.id)
        elif isinstance(subnode, ast.Attribute):
            chain = []
            current = subnode
            while isinstance(current, ast.Attribute):
                chain.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                chain.append(current.id)
                vars_list.append(".".join(reversed(chain)))
    return vars_list


def extract_vars_from_typescript_node(node: Any, depth: int = 0) -> list[str]:
    """Extract all variable names from a TypeScript/JavaScript AST node."""
    if depth > 50 or not isinstance(node, dict):
        return []

    vars_list = []
    kind = node.get("kind", "")

    if kind == "PropertyAccessExpression":
        full_text = node.get("text", "").strip()
        if full_text:
            vars_list.append(full_text)

            parts = full_text.split(".")
            for i in range(len(parts) - 1, 0, -1):
                prefix = ".".join(parts[:i])
                if prefix:
                    vars_list.append(prefix)

    elif kind == "Identifier":
        text = node.get("text", "").strip()
        if text:
            vars_list.append(text)

    elif kind == "CallExpression":
        pass

    for child in node.get("children", []):
        if isinstance(child, dict):
            vars_list.extend(extract_vars_from_typescript_node(child, depth + 1))

    seen = set()
    result = []
    for var in vars_list:
        if var not in seen:
            seen.add(var)
            result.append(var)

    return result


def sanitize_call_name(name: Any) -> str:
    """Normalize call expression names for downstream analysis."""
    if not isinstance(name, str):
        return ""

    cleaned = name.strip()
    if not cleaned:
        return ""

    paren_idx = cleaned.find("(")
    if paren_idx != -1:
        cleaned = cleaned[:paren_idx]

    cleaned = " ".join(cleaned.split())
    cleaned = cleaned.rstrip(".")

    return cleaned


def find_containing_function_python(tree: ast.AST, line: int) -> str | None:
    """Find the function containing a given line in Python AST."""
    containing_func = None

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and hasattr(node, "lineno")
            and hasattr(node, "end_lineno")
            and node.lineno <= line <= (node.end_lineno or node.lineno)
            and (containing_func is None or node.lineno > containing_func[1])
        ):
            containing_func = (node.name, node.lineno)

    return containing_func[0] if containing_func else None


def find_containing_class_python(tree: ast.AST, line: int) -> str | None:
    """Find the class containing a given line in Python AST."""
    containing_class = None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ClassDef)
            and hasattr(node, "lineno")
            and hasattr(node, "end_lineno")
            and node.lineno <= line <= (node.end_lineno or node.lineno)
            and (containing_class is None or node.lineno > containing_class[1])
        ):
            containing_class = (node.name, node.lineno)

    return containing_class[0] if containing_class else None


def find_containing_function_tree_sitter(node: Any, content: str, language: str) -> str | None:
    """Find the function containing a node in Tree-sitter AST."""

    current = node
    while current and hasattr(current, "parent") and current.parent:
        current = current.parent
        if language in ["javascript", "typescript"]:
            function_types = [
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_definition",
                "generator_function",
                "async_function",
            ]

            if current.type in function_types:
                if current.type == "arrow_function":
                    parent = current.parent if hasattr(current, "parent") else None
                    if parent:
                        if parent.type == "variable_declarator":
                            if hasattr(parent, "child_by_field_name"):
                                name_node = parent.child_by_field_name("name")
                                if name_node and name_node.text:
                                    return name_node.text.decode("utf-8", errors="ignore")

                            for child in parent.children:
                                if child.type == "identifier" and child != current:
                                    return child.text.decode("utf-8", errors="ignore")

                        elif parent.type == "pair":
                            for child in parent.children:
                                if (
                                    child.type in ["property_identifier", "identifier", "string"]
                                    and child != current
                                ):
                                    text = child.text.decode("utf-8", errors="ignore")

                                    return text.strip("\"'")

                    continue

                if hasattr(current, "child_by_field_name"):
                    name_node = current.child_by_field_name("name")
                    if name_node and name_node.text:
                        return name_node.text.decode("utf-8", errors="ignore")

                for child in current.children:
                    if child.type in ["identifier", "property_identifier"]:
                        return child.text.decode("utf-8", errors="ignore")

                return "anonymous"

        elif language == "python":
            if current.type == "function_definition":
                if hasattr(current, "child_by_field_name"):
                    name_node = current.child_by_field_name("name")
                    if name_node and name_node.text:
                        return name_node.text.decode("utf-8", errors="ignore")

                for child in current.children:
                    if child.type == "identifier":
                        return child.text.decode("utf-8", errors="ignore")

    return "global"


def extract_vars_from_rust_node(node: Any, content: str, depth: int = 0) -> list[str]:
    """Extract all variable names from a Rust tree-sitter AST node."""
    if depth > 50 or node is None:
        return []

    vars_list = []

    def _get_text(n):
        """Helper to extract text from tree-sitter node."""
        if n is None:
            return ""
        return content[n.start_byte : n.end_byte]

    if node.type == "field_expression":
        full_text = _get_text(node).strip()
        if full_text:
            vars_list.append(full_text)

            parts = full_text.split(".")
            for i in range(len(parts) - 1, 0, -1):
                prefix = ".".join(parts[:i])
                if prefix:
                    vars_list.append(prefix)

    elif node.type == "identifier":
        text = _get_text(node).strip()

        if text and text not in ["self", "super", "crate", "true", "false", "None", "Some"]:
            vars_list.append(text)

    if hasattr(node, "children"):
        for child in node.children:
            vars_list.extend(extract_vars_from_rust_node(child, content, depth + 1))

    seen = set()
    result = []
    for var in vars_list:
        if var not in seen:
            seen.add(var)
            result.append(var)

    return result


def detect_language(file_path: Path) -> str:
    """Detect language from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".vue": "javascript",
        ".rs": "rust",
    }
    return ext_map.get(file_path.suffix.lower(), "")


def check_tree_sitter_parse_quality(root_node: Any, file_path: str, logger: Any) -> None:
    """Log warning if tree-sitter parse has high error rate.

    Tree-sitter is forgiving - it returns partial trees with ERROR nodes
    instead of failing. This function detects when >10% of the tree is
    errors, which indicates extraction will be incomplete.

    Args:
        root_node: Tree-sitter root node
        file_path: Path to the file being parsed (for logging)
        logger: Logger instance for warnings
    """
    error_count = 0
    total_count = 0

    def count_nodes(node: Any) -> None:
        nonlocal error_count, total_count
        total_count += 1
        if node.type == "ERROR":
            error_count += 1
        for child in node.children:
            count_nodes(child)

    count_nodes(root_node)

    if total_count > 0 and error_count / total_count > 0.1:
        logger.warning(
            "High parse error rate (%d/%d nodes, %.1f%%) in %s - extraction may be incomplete",
            error_count,
            total_count,
            100 * error_count / total_count,
            file_path,
        )
