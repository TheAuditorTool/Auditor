"""TypeScript/JavaScript Structural AST Extraction Layer."""

import sys
from typing import Any

from .base import sanitize_call_name
from theauditor.utils.logging import logger

PARAMETER_NAMES = frozenset(
    {
        "req",
        "res",
        "next",
        "err",
        "error",
        "ctx",
        "request",
        "response",
        "callback",
        "done",
        "cb",
    }
)


def _strip_comment_prefix(text: str | None) -> str:
    """Return the first non-comment, non-empty line from the given text."""
    if not text:
        return ""

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            stripped.startswith("//")
            or stripped.startswith("/*")
            or stripped.startswith("*")
            or stripped == "*/"
        ):
            continue
        return stripped

    return text.strip()


def _identifier_from_node(node: Any) -> str:
    """Extract a single identifier string from a semantic AST node."""
    if not isinstance(node, dict):
        return ""

    candidates: list[str] = []

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


def _canonical_callee_from_call(node: dict[str, Any]) -> str:
    """Return a sanitized callee name for a CallExpression node."""
    if not isinstance(node, dict):
        return ""

    expression = node.get("expression")
    name = _canonical_member_name(expression)
    if name:
        return sanitize_call_name(_strip_comment_prefix(name))

    return sanitize_call_name(_strip_comment_prefix(_identifier_from_node(node)))


def extract_semantic_ast_symbols(node, depth=0):
    """Extract symbols from TypeScript semantic AST including property accesses."""
    symbols = []
    if depth > 100 or not isinstance(node, dict):
        return symbols

    kind = node.get("kind")

    if kind == "PropertyAccessExpression":
        full_name = _canonical_member_name(node)

        if full_name:
            db_type = "property"

            if any(
                sink in full_name
                for sink in [
                    "res.send",
                    "res.render",
                    "res.json",
                    "response.write",
                    "innerHTML",
                    "outerHTML",
                    "exec",
                    "eval",
                    "system",
                    "spawn",
                ]
            ):
                db_type = "call"

            symbols.append(
                {
                    "name": full_name,
                    "line": node.get("line", 0),
                    "column": node.get("column", 0),
                    "type": db_type,
                }
            )

    elif kind == "CallExpression":
        name = _canonical_callee_from_call(node)

        if name:
            symbols.append(
                {
                    "name": name,
                    "line": node.get("line", 0),
                    "column": node.get("column", 0),
                    "type": "call",
                }
            )

    elif kind == "Identifier":
        text = _strip_comment_prefix(node.get("text", ""))

        if "." in text:
            db_type = "property"

            if any(
                sink in text for sink in ["res.send", "res.render", "res.json", "response.write"]
            ):
                db_type = "call"

            symbols.append(
                {
                    "name": text,
                    "line": node.get("line", 0),
                    "column": node.get("column", 0),
                    "type": db_type,
                }
            )

    for child in node.get("children", []):
        symbols.extend(extract_semantic_ast_symbols(child, depth + 1))

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


JSX_NODE_KINDS = frozenset(
    [
        "JsxElement",
        "JsxSelfClosingElement",
        "JsxFragment",
        "JsxOpeningElement",
        "JsxClosingElement",
        "JsxOpeningFragment",
        "JsxClosingFragment",
        "JsxText",
        "JsxExpression",
        "JsxExpressionContainer",
        "JsxSpreadChild",
        "JsxAttribute",
        "JsxAttributes",
        "JsxSpreadAttribute",
        "JsxNamespacedName",
        "JsxMemberExpression",
        "JsxIdentifier",
    ]
)


def detect_jsx_in_node(node, depth=0):
    """Comprehensively detect JSX in AST node."""
    if depth > 50 or not isinstance(node, dict):
        return False, False

    kind = node.get("kind", "")

    if kind in JSX_NODE_KINDS:
        if kind in ["JsxElement", "JsxSelfClosingElement"]:
            tag_name = extract_jsx_tag_name(node)
            is_component = tag_name and tag_name[0].isupper() if tag_name else False
            return True, is_component
        return True, False

    if kind in [
        "ParenthesizedExpression",
        "ConditionalExpression",
        "BinaryExpression",
        "LogicalExpression",
        "ArrayLiteralExpression",
        "ObjectLiteralExpression",
        "ArrowFunction",
        "FunctionExpression",
    ]:
        for key in [
            "expression",
            "initializer",
            "left",
            "right",
            "operand",
            "condition",
            "whenTrue",
            "whenFalse",
            "arguments",
            "elements",
            "properties",
            "body",
            "statements",
            "children",
        ]:
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

    if kind == "CallExpression":
        callee = node.get("expression", {})
        if isinstance(callee, dict):
            callee_text = callee.get("text", "")
            if (
                "React.createElement" in callee_text
                or "jsx" in callee_text
                or "_jsx" in callee_text
            ):
                return True, analyze_create_element_component(node)

    return False, False


def extract_jsx_tag_name(node):
    """Extract tag name from JSX element node."""

    if "openingElement" in node:
        opening = node["openingElement"]
        if isinstance(opening, dict) and "tagName" in opening:
            tag_name = opening["tagName"]
            if isinstance(tag_name, dict):
                return tag_name.get("escapedText", "") or tag_name.get("text", "")

    if "tagName" in node:
        tag_name = node["tagName"]
        if isinstance(tag_name, dict):
            return tag_name.get("escapedText", "") or tag_name.get("text", "")

    return None


def analyze_create_element_component(node):
    """Analyze React.createElement call to determine if it's a component."""
    if "arguments" in node and isinstance(node["arguments"], list) and len(node["arguments"]) > 0:
        first_arg = node["arguments"][0]
        if isinstance(first_arg, dict):
            if first_arg.get("kind") == "StringLiteral":
                text = first_arg.get("text", "")
                return text and text[0].isupper()

            elif first_arg.get("kind") == "Identifier":
                text = first_arg.get("escapedText", "")
                return text and text[0].isupper()
    return False


def check_for_jsx(node, depth=0):
    """Legacy function name for backward compatibility."""
    return detect_jsx_in_node(node, depth)


def build_scope_map(ast_root: dict) -> dict[int, str]:
    """Build a map of line numbers to containing function names."""

    scope_map = {}
    function_ranges = []

    class_stack = []

    def collect_functions(node, depth=0):
        """Recursively collect all function declarations with their line ranges."""
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind", "")

        if kind == "ClassDeclaration":
            class_name = "UnknownClass"
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    class_name = child.get("text", "UnknownClass")
                    break
            class_stack.append(class_name)

            for child in node.get("children", []):
                collect_functions(child, depth + 1)

            if class_stack:
                class_stack.pop()
            return

        if kind == "PropertyDeclaration":
            initializer = node.get("initializer")
            if not initializer:
                children = node.get("children", [])
                for child in children:
                    if isinstance(child, dict):
                        child_kind = child.get("kind", "")

                        if child_kind not in [
                            "Identifier",
                            "StaticKeyword",
                            "ReadonlyKeyword",
                            "PrivateKeyword",
                            "PublicKeyword",
                            "ProtectedKeyword",
                            "AsyncKeyword",
                            "AbstractKeyword",
                            "DeclareKeyword",
                        ]:
                            initializer = child
                            break

            if isinstance(initializer, dict):
                init_kind = initializer.get("kind", "")

                is_arrow_func = init_kind in ["ArrowFunction", "FunctionExpression"]

                is_wrapped_func = False
                func_start_line = None
                func_end_line = None

                if init_kind == "CallExpression":
                    call_args = initializer.get("arguments", initializer.get("children", [])[1:])
                    for arg in call_args:
                        if isinstance(arg, dict) and arg.get("kind") in [
                            "ArrowFunction",
                            "FunctionExpression",
                        ]:
                            is_wrapped_func = True
                            func_start_line = arg.get("line", node.get("line", 0))
                            func_end_line = arg.get("endLine")
                            break
                elif is_arrow_func:
                    func_start_line = initializer.get("line", node.get("line", 0))
                    func_end_line = initializer.get("endLine")

                if is_arrow_func or is_wrapped_func:
                    prop_name = ""
                    for child in node.get("children", []):
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            prop_name = child.get("text", "")
                            break

                    func_name = f"{class_stack[-1]}.{prop_name}" if class_stack else prop_name

                    start_line = func_start_line or node.get("line", 0)
                    end_line = func_end_line

                    if not end_line:
                        end_line = start_line + 50

                    if start_line > 0:
                        function_ranges.append(
                            {
                                "name": func_name,
                                "start": start_line,
                                "end": end_line,
                                "depth": depth,
                                "is_property_function": True,
                                "is_wrapped": is_wrapped_func,
                                "is_direct_arrow": is_arrow_func,
                            }
                        )

                    return

        if kind in [
            "FunctionDeclaration",
            "MethodDeclaration",
            "ArrowFunction",
            "FunctionExpression",
            "Constructor",
            "GetAccessor",
            "SetAccessor",
        ]:
            name = node.get("name", "anonymous")

            if isinstance(name, dict):
                name = name.get("text", "anonymous")

            if kind == "MethodDeclaration" and class_stack:
                method_name = ""
                for child in node.get("children", []):
                    if isinstance(child, dict) and child.get("kind") == "Identifier":
                        method_name = child.get("text", "")
                        break
                if method_name:
                    name = f"{class_stack[-1]}.{method_name}"

            start_line = node.get("line", 0)
            end_line = node.get("endLine")

            if not end_line:
                end_line = start_line + 50

            if start_line > 0:
                function_ranges.append(
                    {"name": name, "start": start_line, "end": end_line, "depth": depth}
                )

        for child in node.get("children", []):
            collect_functions(child, depth + 1)

    collect_functions(ast_root)

    function_ranges.sort(key=lambda x: (x["start"], -x["depth"]))

    for func in reversed(function_ranges):
        for line in range(func["start"], func["end"] + 1):
            if line not in scope_map or func["depth"] > 0:
                scope_map[line] = func["name"]

    if function_ranges:
        max_line = max(func["end"] for func in function_ranges)
        for line in range(1, max_line + 1):
            if line not in scope_map:
                scope_map[line] = "global"

    return scope_map


def extract_typescript_functions_for_symbols(tree: dict, parser_self) -> list[dict]:
    """Extract function metadata from TypeScript semantic AST for symbol table."""
    functions = []

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree

    if not actual_tree or not actual_tree.get("success"):
        return functions

    extracted_data = actual_tree.get("extracted_data")
    if extracted_data and "functions" in extracted_data:
        import os

        if os.getenv("THEAUDITOR_DEBUG"):
            logger.debug(f"extract_typescript_functions_for_symbols: Using PRE-EXTRACTED data ({len(extracted_data['functions'])} functions)")
        return extracted_data["functions"]

    import os

    if os.getenv("THEAUDITOR_DEBUG"):
        logger.debug("extract_typescript_functions_for_symbols: Using FALLBACK AST traversal")
    ast_root = actual_tree.get("ast", {})

    if not ast_root:
        return functions

    class_stack = []

    def traverse(node, depth=0):
        """Recursively traverse AST extracting ALL function patterns."""
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind", "")

        if kind == "ClassDeclaration":
            class_name = "UnknownClass"
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    class_name = child.get("text", "UnknownClass")
                    break
            class_stack.append(class_name)

            for child in node.get("children", []):
                traverse(child, depth + 1)

            if class_stack:
                class_stack.pop()
            return

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

        if kind == "FunctionDeclaration":
            is_function_like = True

            func_name = ""
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    func_name = child.get("text", "")
                    break

        elif kind == "MethodDeclaration":
            is_function_like = True

            method_name = ""
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("kind") == "Identifier":
                    method_name = child.get("text", "")
                    break
            func_name = f"{class_stack[-1]}.{method_name}" if class_stack else method_name

        elif kind == "PropertyDeclaration":
            initializer = node.get("initializer")
            if not initializer:
                children = node.get("children", [])
                if len(children) > 1:
                    initializer = children[1]

            if isinstance(initializer, dict):
                init_kind = initializer.get("kind", "")
                is_arrow_func = init_kind in ["ArrowFunction", "FunctionExpression"]
                is_wrapped_func = False

                if init_kind == "CallExpression":
                    call_args = initializer.get("arguments", initializer.get("children", [])[1:])
                    for arg in call_args:
                        if isinstance(arg, dict) and arg.get("kind") in [
                            "ArrowFunction",
                            "FunctionExpression",
                        ]:
                            is_wrapped_func = True
                            break

                if is_arrow_func or is_wrapped_func:
                    is_function_like = True

                    prop_name = ""
                    for child in node.get("children", []):
                        if isinstance(child, dict) and child.get("kind") == "Identifier":
                            prop_name = child.get("text", "")
                            break
                    func_name = f"{class_stack[-1]}.{prop_name}" if class_stack else prop_name

        elif kind in ["Constructor", "GetAccessor", "SetAccessor"]:
            is_function_like = True
            if kind == "Constructor":
                accessor_name = "constructor"
            else:
                accessor_name = ""
                for child in node.get("children", []):
                    if isinstance(child, dict) and child.get("kind") == "Identifier":
                        accessor_name = child.get("text", "")
                        break
            prefix = ""
            if kind == "GetAccessor":
                prefix = "get "
            if kind == "SetAccessor":
                prefix = "set "
            func_name = (
                f"{class_stack[-1]}.{prefix}{accessor_name}"
                if class_stack
                else f"{prefix}{accessor_name}"
            )

        if is_function_like and func_name and func_name not in PARAMETER_NAMES:
            func_entry["name"] = func_name

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

        for child in node.get("children", []):
            traverse(child, depth + 1)

    traverse(ast_root)

    seen = {}
    deduped_functions = []
    for func in functions:
        key = (func.get("name"), func.get("line"), func.get("col", func.get("column", 0)))
        if key not in seen:
            seen[key] = True
            deduped_functions.append(func)
    logger.debug(f"extract_typescript_functions_for_symbols: Found {len(deduped_functions)} functions (deduped from {len(functions)})")
    for func in deduped_functions[:5]:
        print(f"[DEBUG]   {func['name']} at line {func['line']}", file=sys.stderr)

    return deduped_functions


def extract_typescript_functions(tree: dict, parser_self) -> list[dict]:
    """For backward compatibility, returns metadata for symbols."""
    return extract_typescript_functions_for_symbols(tree, parser_self)


def extract_typescript_function_nodes(tree: dict, parser_self) -> list[dict]:
    """Extract COMPLETE function AST nodes from TypeScript semantic AST."""
    functions = []

    ast_root = tree.get("ast", {})
    if not ast_root and "tree" in tree and isinstance(tree["tree"], dict):
        ast_root = tree["tree"].get("ast", {})

    if not ast_root:
        return []

    def traverse_for_functions(node, depth=0):
        """Recursively find all function nodes in the AST."""
        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get("kind")

        function_kinds = [
            "FunctionDeclaration",
            "MethodDeclaration",
            "ArrowFunction",
            "FunctionExpression",
            "Constructor",
            "GetAccessor",
            "SetAccessor",
        ]

        if kind in function_kinds:
            functions.append(node)

            for child in node.get("children", []):
                traverse_for_functions(child, depth + 1)
        else:
            for child in node.get("children", []):
                traverse_for_functions(child, depth + 1)

    traverse_for_functions(ast_root)
    return functions


def extract_typescript_classes(tree: dict, parser_self) -> list[dict]:
    """Extract class definitions from TypeScript semantic AST."""
    classes = []

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

        if kind in ["ClassDeclaration", "InterfaceDeclaration"]:
            class_name = node.get("name", "")
            if isinstance(class_name, dict):
                class_name = class_name.get("text", class_name.get("name", ""))

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

                for key in (
                    "type_annotation",
                    "extends_type",
                    "type_params",
                    "has_type_params",
                ):
                    if key in node:
                        class_entry[key] = node.get(key)

                classes.append(class_entry)

        for child in node.get("children", []):
            traverse(child, depth + 1)

    traverse(ast_root)

    seen = {}
    deduped_classes = []
    for cls in classes:
        key = (cls.get("name"), cls.get("line"), cls.get("col", cls.get("column", 0)))
        if key not in seen:
            seen[key] = True
            deduped_classes.append(cls)

    return deduped_classes


def extract_typescript_calls(tree: dict, parser_self) -> list[dict]:
    """Extract function calls from TypeScript semantic AST."""
    calls = []

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if actual_tree and actual_tree.get("success"):
        extracted_data = actual_tree.get("extracted_data")
        if extracted_data and "calls" in extracted_data:
            import os

            if os.getenv("THEAUDITOR_DEBUG"):
                logger.debug(f"extract_typescript_calls: Using PRE-EXTRACTED data ({len(extracted_data['calls'])} calls)")
            return extracted_data["calls"]

        import os

        if os.getenv("THEAUDITOR_DEBUG"):
            logger.debug("extract_typescript_calls: Using FALLBACK AST traversal")
        ast_root = actual_tree.get("ast")
        if ast_root:
            calls = extract_semantic_ast_symbols(ast_root)

    return calls


def extract_typescript_imports(tree: dict, parser_self) -> list[dict[str, Any]]:
    """Extract import statements from TypeScript semantic AST."""
    imports = []

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if actual_tree and actual_tree.get("success"):
        extracted_data = actual_tree.get("extracted_data")
        if extracted_data and "imports" in extracted_data:
            tree_imports = extracted_data["imports"]
        else:
            tree_imports = tree.get("imports", [])
    else:
        tree_imports = tree.get("imports", [])

    for imp in tree_imports:
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


def extract_typescript_exports(tree: dict, parser_self) -> list[dict[str, Any]]:
    """Extract export statements from TypeScript semantic AST."""
    return []


def extract_typescript_properties(tree: dict, parser_self) -> list[dict]:
    """Extract property accesses from TypeScript semantic AST."""
    properties = []

    actual_tree = tree.get("tree") if isinstance(tree.get("tree"), dict) else tree
    if actual_tree and actual_tree.get("success"):
        ast_root = actual_tree.get("ast")
        if ast_root:
            symbols = extract_semantic_ast_symbols(ast_root)

            properties = [s for s in symbols if s.get("type") == "property"]

    return properties
