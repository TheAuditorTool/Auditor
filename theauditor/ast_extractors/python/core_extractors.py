"""Python core AST extractors - Language fundamentals.

This module contains extraction logic for core Python language features:
- Functions, classes, imports, exports
- Assignments, returns, calls
- Properties, dicts
- Type annotations and helpers

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.
"""

import ast
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from ..base import (
    get_node_name,
    extract_vars_from_expr,
    find_containing_function_python,
    find_containing_class_python,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Type Annotation Helpers
# ============================================================================

def _get_type_annotation(node: Optional[ast.AST]) -> Optional[str]:
    """Convert an annotation AST node into source text."""
    if node is None:
        return None
    try:
        if hasattr(ast, "unparse"):
            return ast.unparse(node)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Failed to unparse annotation at line %s: %s",
            getattr(node, "lineno", "?"),
            exc,
        )
    return None


def _analyze_annotation_flags(
    node: Optional[ast.AST], annotation_text: Optional[str]
) -> Tuple[bool, bool, Optional[str]]:
    """Derive generic flags from an annotation node."""
    if node is None or annotation_text is None:
        return False, False, None

    if isinstance(node, ast.Subscript):
        # Subscript indicates parametrised generic: List[int], Optional[str], etc.
        type_params_text = _get_type_annotation(getattr(node, "slice", None))
        if type_params_text:
            return True, True, type_params_text
        return True, False, None

    return False, False, None


def _parse_function_type_comment(comment: Optional[str]) -> Tuple[List[str], Optional[str]]:
    """Parse legacy PEP 484 type comments into parameter and return segments."""
    if not comment:
        return [], None

    text = comment.strip()
    if not text:
        return [], None

    # Strip optional leading markers ("# type:", "type:")
    if text.startswith("#"):
        text = text.lstrip("#").strip()
    if text.lower().startswith("type:"):
        text = text[5:].strip()

    if "->" not in text:
        return [], text or None

    params_part, return_part = text.split("->", 1)
    params_part = params_part.strip()
    return_part = return_part.strip() or None

    param_types: List[str] = []
    if params_part.startswith("(") and params_part.endswith(")"):
        inner = params_part[1:-1].strip()
        if inner:
            param_types = [segment.strip() for segment in inner.split(",")]
    elif params_part:
        param_types = [params_part]

    return param_types, return_part


# ============================================================================
# Core Language Extractors
# ============================================================================

def extract_python_functions(tree: Dict, parser_self) -> List[Dict]:
    """Extract function definitions from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance for accessing methods

    Returns:
        List of function info dictionaries
    """
    functions = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return functions

    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # CRITICAL FIX: Add end_line for proper function boundaries
            end_line = getattr(node, "end_lineno", node.lineno)
            col = getattr(node, "col_offset", 0)

            function_entry: Dict[str, Any] = {
                "name": node.name,
                "line": node.lineno,
                "end_line": end_line,
                "column": col,
                "async": isinstance(node, ast.AsyncFunctionDef),
            }

            parameter_entries: List[Dict[str, Any]] = []

            def _register_param(arg: ast.arg, kind: str) -> None:
                if not isinstance(arg, ast.arg):
                    return

                annotation_text = _get_type_annotation(getattr(arg, "annotation", None))
                if not annotation_text and getattr(arg, "type_comment", None):
                    annotation_text = arg.type_comment.strip()

                is_generic, has_type_params, type_params = _analyze_annotation_flags(
                    getattr(arg, "annotation", None), annotation_text
                )

                parameter_entries.append({
                    "name": arg.arg,
                    "kind": kind,
                    "line": getattr(arg, "lineno", node.lineno),
                    "column": getattr(arg, "col_offset", 0),
                    "type_annotation": annotation_text,
                    "is_any": annotation_text in {"Any", "typing.Any"} if annotation_text else False,
                    "is_generic": is_generic,
                    "has_type_params": has_type_params,
                    "type_params": type_params,
                })

            # Positional-only args (Python 3.8+)
            for arg in getattr(node.args, "posonlyargs", []):
                _register_param(arg, "posonly")

            # Regular args
            for arg in node.args.args:
                _register_param(arg, "arg")

            # Vararg (*args)
            if node.args.vararg:
                _register_param(node.args.vararg, "vararg")

            # Keyword-only args
            for arg in node.args.kwonlyargs:
                _register_param(arg, "kwonly")

            # Kwarg (**kwargs)
            if node.args.kwarg:
                _register_param(node.args.kwarg, "kwarg")

            # Map type comments (legacy) onto parameters if present
            type_comment_params, type_comment_return = _parse_function_type_comment(
                getattr(node, "type_comment", None)
            )
            if type_comment_params:
                for idx, comment_value in enumerate(type_comment_params):
                    if idx < len(parameter_entries) and comment_value:
                        entry = parameter_entries[idx]
                        if not entry["type_annotation"]:
                            entry["type_annotation"] = comment_value

            # Capture decorator names for downstream analysis (e.g., typing.overload)
            decorators: List[str] = []
            for decorator in getattr(node, "decorator_list", []):
                decorators.append(get_node_name(decorator))

            # Collect parameter names for backward compatibility
            function_entry["args"] = [
                arg.arg for arg in node.args.args
            ]
            function_entry["parameters"] = [p["name"] for p in parameter_entries]

            # Determine return annotation (including legacy comments)
            return_annotation = _get_type_annotation(getattr(node, "returns", None))
            if not return_annotation and type_comment_return:
                return_annotation = type_comment_return

            is_generic, has_type_params, type_params = _analyze_annotation_flags(
                getattr(node, "returns", None), return_annotation
            )

            type_annotation_records: List[Dict[str, Any]] = []

            # Parameter records
            for param in parameter_entries:
                if not param["type_annotation"]:
                    continue
                type_annotation_records.append({
                    "line": param["line"],
                    "column": param["column"],
                    "symbol_name": f"{node.name}.{param['name']}",
                    "symbol_kind": "parameter",
                    "language": "python",
                    "type_annotation": param["type_annotation"],
                    "is_any": param["is_any"],
                    "is_unknown": False,
                    "is_generic": param["is_generic"],
                    "has_type_params": param["has_type_params"],
                    "type_params": param["type_params"],
                    "return_type": None,
                })

            # Function return record
            if return_annotation:
                is_any_return = return_annotation in {"Any", "typing.Any"}
                type_annotation_records.append({
                    "line": node.lineno,
                    "column": col,
                    "symbol_name": node.name,
                    "symbol_kind": "function",
                    "language": "python",
                    "type_annotation": None,
                    "return_type": return_annotation,
                    "is_any": is_any_return,
                    "is_unknown": False,
                    "is_generic": is_generic,
                    "has_type_params": has_type_params,
                    "type_params": type_params,
                })

            function_entry["type_annotations"] = type_annotation_records
            function_entry["return_type"] = return_annotation
            function_entry["is_typed"] = bool(type_annotation_records)
            function_entry["decorators"] = decorators

            functions.append(function_entry)

    return functions


def extract_python_classes(tree: Dict, parser_self) -> List[Dict]:
    """Extract class definitions from Python AST."""
    classes = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return classes

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "column": node.col_offset,
                "bases": [get_node_name(base) for base in node.bases],
                "type_annotations": [],
            })

    return classes


def extract_python_attribute_annotations(tree: Dict, parser_self) -> List[Dict]:
    """Extract type annotations declared on class or module attributes."""
    annotations: List[Dict[str, Any]] = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return annotations

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.AnnAssign):
            target_name = get_node_name(node.target)
            if not target_name:
                continue

            annotation_text = _get_type_annotation(node.annotation)
            if not annotation_text:
                continue

            class_name = find_containing_class_python(actual_tree, getattr(node, "lineno", 0))
            is_generic, has_type_params, type_params = _analyze_annotation_flags(node.annotation, annotation_text)

            annotations.append({
                "line": getattr(node, "lineno", 0),
                "column": getattr(node, "col_offset", 0),
                "symbol_name": f"{class_name}.{target_name}" if class_name else target_name,
                "symbol_kind": "class_attribute" if class_name else "module_attribute",
                "language": "python",
                "type_annotation": annotation_text,
                "return_type": None,
                "class_name": class_name,
                "is_any": annotation_text in {"Any", "typing.Any"},
                "is_unknown": False,
                "is_generic": is_generic,
                "has_type_params": has_type_params,
                "type_params": type_params,
            })

    return annotations


def extract_python_imports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract import statements from Python AST."""
    imports = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return imports

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "source": "import",
                    "target": alias.name,
                    "type": "import",
                    "line": node.lineno,
                    "as": alias.asname,
                    "specifiers": []
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append({
                    "source": "from",
                    "target": module,
                    "type": "from",
                    "line": node.lineno,
                    "imported": alias.name,
                    "as": alias.asname,
                    "specifiers": [alias.name]
                })

    return imports


def extract_python_exports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract export statements from Python AST.

    In Python, all top-level functions, classes, and assignments are "exported".
    """
    exports = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return exports

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.FunctionDef) and node.col_offset == 0:
            exports.append({
                "name": node.name,
                "type": "function",
                "line": node.lineno,
                "default": False
            })
        elif isinstance(node, ast.ClassDef) and node.col_offset == 0:
            exports.append({
                "name": node.name,
                "type": "class",
                "line": node.lineno,
                "default": False
            })
        elif isinstance(node, ast.Assign) and node.col_offset == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    exports.append({
                        "name": target.id,
                        "type": "variable",
                        "line": node.lineno,
                        "default": False
                    })

    return exports


def extract_python_assignments(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract variable assignments from Python AST for data flow analysis."""
    import os
    assignments = []
    actual_tree = tree.get("tree")

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        print(f"[AST_DEBUG] extract_python_assignments called", file=sys.stderr)

    if not actual_tree:
        return assignments

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Assign):
            # Extract target variable(s)
            for target in node.targets:
                target_var = get_node_name(target)
                source_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)

                # Find containing function
                in_function = find_containing_function_python(actual_tree, node.lineno)

                # CRITICAL FIX: Check if this is a class instantiation
                # BeautifulSoup(html) is ast.Call with func.id = "BeautifulSoup"
                is_instantiation = isinstance(node.value, ast.Call)

                assignments.append({
                    "target_var": target_var,
                    "source_expr": source_expr,
                    "line": node.lineno,
                    "in_function": in_function or "global",
                    "source_vars": extract_vars_from_expr(node.value),
                    "is_instantiation": is_instantiation  # Track for taint analysis
                })

        elif isinstance(node, ast.AnnAssign) and node.value:
            # Handle annotated assignments (x: int = 5)
            target_var = get_node_name(node.target)
            source_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)

            in_function = find_containing_function_python(actual_tree, node.lineno)

            assignments.append({
                "target_var": target_var,
                "source_expr": source_expr,
                "line": node.lineno,
                "in_function": in_function or "global",
                "source_vars": extract_vars_from_expr(node.value)
            })

    # CRITICAL FIX: Deduplicate assignments by (line, target_var, in_function)
    # WHY: ast.walk() can visit nodes multiple times if they appear in tree multiple times.
    # Same issue as TypeScript extractor, same solution.
    seen = set()
    deduped = []
    for a in assignments:
        key = (a['line'], a['target_var'], a['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(assignments) != len(deduped):
            print(f"[AST_DEBUG] Python deduplication: {len(assignments)} -> {len(deduped)} assignments ({len(assignments) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_python_function_params(tree: Dict, parser_self) -> Dict[str, List[str]]:
    """Extract function definitions and their parameter names from Python AST."""
    func_params = {}
    actual_tree = tree.get("tree")

    if not actual_tree:
        return func_params

    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [arg.arg for arg in node.args.args]
            func_params[node.name] = params

    return func_params


def extract_python_calls_with_args(tree: Dict, function_params: Dict[str, List[str]], parser_self) -> List[Dict[str, Any]]:
    """Extract Python function calls with argument mapping."""
    calls = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return calls

    # Find containing function for each call
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Call):
            func_name = get_node_name(node.func)

            # Find caller function
            caller_function = "global"
            for fname, (start, end) in function_ranges.items():
                if start <= node.lineno <= end:
                    caller_function = fname
                    break

            # Get callee parameters
            callee_params = function_params.get(func_name.split(".")[-1], [])

            # Map arguments to parameters
            for i, arg in enumerate(node.args):
                arg_expr = ast.unparse(arg) if hasattr(ast, "unparse") else str(arg)
                param_name = callee_params[i] if i < len(callee_params) else f"arg{i}"

                calls.append({
                    "line": node.lineno,
                    "caller_function": caller_function,
                    "callee_function": func_name,
                    "argument_index": i,
                    "argument_expr": arg_expr,
                    "param_name": param_name
                })

    return calls


def extract_python_returns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract return statements from Python AST."""
    returns = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return returns

    # First, map all functions
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    # Extract return statements
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Return):
            # Find containing function
            function_name = "global"
            for fname, (start, end) in function_ranges.items():
                if start <= node.lineno <= end:
                    function_name = fname
                    break

            # Extract return expression
            if node.value:
                return_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)
                return_vars = extract_vars_from_expr(node.value)
            else:
                return_expr = "None"
                return_vars = []

            returns.append({
                "function_name": function_name,
                "line": node.lineno,
                "return_expr": return_expr,
                "return_vars": return_vars
            })

    # CRITICAL FIX: Deduplicate returns by (line, function_name)
    # WHY: ast.walk() can visit nodes multiple times
    # NOTE: PRIMARY KEY is (file, line, function_name) but file is added by orchestrator
    seen = set()
    deduped = []
    for r in returns:
        key = (r['line'], r['function_name'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(returns) != len(deduped):
            print(f"[AST_DEBUG] Python returns deduplication: {len(returns)} -> {len(deduped)} ({len(returns) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_python_properties(tree: Dict, parser_self) -> List[Dict]:
    """Extract property accesses from Python AST.

    In Python, these would be attribute accesses.
    Currently returns empty list for consistency.
    """
    return []


def extract_python_calls(tree: Dict, parser_self) -> List[Dict]:
    """Extract function calls from Python AST."""
    calls = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return calls

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Call):
            func_name = get_node_name(node.func)
            if func_name:
                calls.append({
                    "name": func_name,
                    "line": node.lineno,
                    "column": node.col_offset,
                    "args_count": len(node.args),
                })

    return calls


def extract_python_dicts(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract dict literal structures from Python AST.

    This is the centralized, correct implementation for dict literal extraction.
    Extracts patterns like:
    - {'key': value}
    - {'key': func_ref}
    - {**spread_dict}

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of dict property records matching object_literals schema
    """
    object_literals = []
    actual_tree = tree.get("tree")

    if not actual_tree or not isinstance(actual_tree, ast.Module):
        return object_literals

    # Build function ranges for scope detection
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, (start, end) in function_ranges.items():
            if start <= line_no <= end:
                return fname
        return "global"

    def extract_dict_properties(dict_node, variable_name, line_no):
        """Extract properties from a dict node."""
        records = []
        in_function = find_containing_function(line_no)

        # Handle dict with explicit keys
        if dict_node.keys:
            for i, (key, value) in enumerate(zip(dict_node.keys, dict_node.values)):
                # Skip None keys (these are **spread operations)
                if key is None:
                    # This is a dict unpacking: {**other_dict}
                    spread_name = get_node_name(value)
                    records.append({
                        "line": line_no,
                        "variable_name": variable_name,
                        "property_name": "**spread",
                        "property_value": spread_name,
                        "property_type": "spread",
                        "nested_level": 0,
                        "in_function": in_function
                    })
                    continue

                # Extract key name
                property_name = None
                if isinstance(key, ast.Constant):
                    property_name = str(key.value)
                elif isinstance(key, ast.Str):  # Python 3.7 compat
                    property_name = key.s
                elif isinstance(key, ast.Name):
                    property_name = key.id
                else:
                    property_name = get_node_name(key) or f"<key_{i}>"

                # Extract value
                property_value = ""
                property_type = "value"

                if isinstance(value, ast.Name):
                    # Variable reference (could be function)
                    property_value = value.id
                    property_type = "function_ref"
                elif isinstance(value, (ast.Lambda, ast.FunctionDef)):
                    # Function/lambda
                    property_value = "<lambda>" if isinstance(value, ast.Lambda) else value.name
                    property_type = "function"
                elif isinstance(value, ast.Constant):
                    property_value = str(value.value)[:250]
                    property_type = "literal"
                elif isinstance(value, ast.Str):  # Python 3.7
                    property_value = value.s[:250]
                    property_type = "literal"
                elif isinstance(value, ast.Dict):
                    property_value = "{...}"
                    property_type = "object"
                elif isinstance(value, ast.List):
                    property_value = "[...]"
                    property_type = "array"
                else:
                    # Complex expression
                    property_value = ast.unparse(value)[:250] if hasattr(ast, "unparse") else str(value)[:250]
                    property_type = "expression"

                records.append({
                    "line": line_no,
                    "variable_name": variable_name,
                    "property_name": property_name,
                    "property_value": property_value,
                    "property_type": property_type,
                    "nested_level": 0,
                    "in_function": in_function
                })

        return records

    # Traverse AST to find all dict literals
    for node in ast.walk(actual_tree):
        # Pattern 1: Variable assignment with dict
        # x = {'key': 'value'}
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(node.value, ast.Dict):
                    var_name = get_node_name(target)
                    records = extract_dict_properties(node.value, var_name, node.lineno)
                    object_literals.extend(records)

        # Pattern 2: Return statement with dict
        # return {'key': 'value'}
        elif isinstance(node, ast.Return):
            if node.value and isinstance(node.value, ast.Dict):
                var_name = f"<return_dict_line_{node.lineno}>"
                records = extract_dict_properties(node.value, var_name, node.lineno)
                object_literals.extend(records)

        # Pattern 3: Function call arguments with dict
        # func({'key': 'value'})
        elif isinstance(node, ast.Call):
            for i, arg in enumerate(node.args):
                if isinstance(arg, ast.Dict):
                    var_name = f"<arg_dict_line_{arg.lineno}>"
                    records = extract_dict_properties(arg, var_name, arg.lineno)
                    object_literals.extend(records)

        # Pattern 4: List elements with dict
        # [{'key': 'value'}]
        elif isinstance(node, ast.List):
            for elem in node.elts:
                if isinstance(elem, ast.Dict) and hasattr(elem, 'lineno'):
                    var_name = f"<list_dict_line_{elem.lineno}>"
                    records = extract_dict_properties(elem, var_name, elem.lineno)
                    object_literals.extend(records)

    return object_literals
