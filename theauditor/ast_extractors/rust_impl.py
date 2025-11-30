"""Rust AST extraction using tree-sitter.

Tree-sitter node type reference (verified 2025-11-29):
- struct_item: struct definitions
- enum_item: enum definitions
- trait_item: trait definitions
- impl_item: impl blocks
- function_item: function definitions
- use_declaration: use statements
- mod_item: module declarations
- macro_definition: macro_rules! definitions
- macro_invocation: macro calls
- unsafe_block: unsafe blocks
- foreign_mod_item: extern blocks (NOT extern_block)
- function_signature_item: extern function declarations (no body)
"""

from typing import Any


def _get_child_by_type(node: Any, node_type: str) -> Any | None:
    """Get first child of given type."""
    for child in node.children:
        if child.type == node_type:
            return child
    return None


def _get_children_by_type(node: Any, node_type: str) -> list[Any]:
    """Get all children of given type."""
    return [child for child in node.children if child.type == node_type]


def _get_text(node: Any) -> str:
    """Safely decode node text."""
    if node is None:
        return ""
    return node.text.decode("utf-8", errors="ignore")


def _has_modifier(node: Any, modifier: str) -> bool:
    """Check if function_item has a specific modifier (async, unsafe, const)."""
    modifiers = _get_child_by_type(node, "function_modifiers")
    if modifiers is None:
        return False
    for child in modifiers.children:
        if child.type == modifier:
            return True
    return False


def _extract_visibility(node: Any) -> str:
    """Extract visibility modifier (pub, pub(crate), etc.)."""
    vis = _get_child_by_type(node, "visibility_modifier")
    if vis is None:
        return ""
    return _get_text(vis)


def _extract_generics(node: Any) -> str | None:
    """Extract type_parameters as string."""
    params = _get_child_by_type(node, "type_parameters")
    if params is None:
        return None
    return _get_text(params)


def _extract_where_clause(node: Any) -> str | None:
    """Extract where_clause as string."""
    clause = _get_child_by_type(node, "where_clause")
    if clause is None:
        return None
    return _get_text(clause)


def extract_rust_modules(root_node: Any, file_path: str) -> list[dict]:
    """Extract mod declarations from tree-sitter AST.

    Args:
        root_node: Tree-sitter root node
        file_path: Path to the source file

    Returns:
        List of module dicts with keys matching rust_modules table
    """
    modules = []

    def visit(node: Any, parent_module: str | None = None) -> None:
        if node.type == "mod_item":
            name_node = _get_child_by_type(node, "identifier")
            decl_list = _get_child_by_type(node, "declaration_list")

            modules.append({
                "file_path": file_path,
                "module_name": _get_text(name_node) if name_node else "",
                "line": node.start_point[0] + 1,
                "visibility": _extract_visibility(node),
                "is_inline": decl_list is not None,
                "parent_module": parent_module,
            })

            if decl_list:
                new_parent = _get_text(name_node) if name_node else None
                for child in decl_list.children:
                    visit(child, new_parent)
        else:
            for child in node.children:
                visit(child, parent_module)

    visit(root_node)
    return modules


def extract_rust_use_statements(root_node: Any, file_path: str) -> list[dict]:
    """Extract use declarations from tree-sitter AST.

    Handles grouped imports like `use std::sync::{Arc, Mutex};` by expanding
    them into separate entries for each imported item.

    Args:
        root_node: Tree-sitter root node
        file_path: Path to the source file

    Returns:
        List of use statement dicts with keys matching rust_use_statements table
    """
    uses = []

    def _expand_grouped_import(
        import_path: str, line: int, visibility: str
    ) -> list[dict]:
        """Expand grouped imports like std::sync::{Arc, Mutex} into separate entries."""
        # Find the grouped portion: everything after ::{ and before }
        if "::{" not in import_path or "}" not in import_path:
            return []

        brace_start = import_path.index("::{")
        base_path = import_path[:brace_start]

        # Extract items between { and }
        items_start = brace_start + 3  # len("::{")
        items_end = import_path.rindex("}")
        items_str = import_path[items_start:items_end]

        # Split by comma, handling nested braces
        items = []
        current_item = ""
        brace_depth = 0
        for char in items_str:
            if char == "{":
                brace_depth += 1
                current_item += char
            elif char == "}":
                brace_depth -= 1
                current_item += char
            elif char == "," and brace_depth == 0:
                item = current_item.strip()
                if item:
                    items.append(item)
                current_item = ""
            else:
                current_item += char
        # Don't forget the last item
        if current_item.strip():
            items.append(current_item.strip())

        result = []
        for item in items:
            # Handle self keyword: use std::sync::{self, Arc} -> std::sync
            if item == "self":
                local_name = base_path.split("::")[-1] if "::" in base_path else base_path
                canonical = base_path
            else:
                # Handle aliased imports: Arc as MyArc
                if " as " in item:
                    original, alias = item.split(" as ", 1)
                    local_name = alias.strip()
                    canonical = f"{base_path}::{original.strip()}"
                else:
                    local_name = item
                    canonical = f"{base_path}::{item}"

            result.append({
                "file_path": file_path,
                "line": line,
                "import_path": import_path,  # Keep original for traceability
                "local_name": local_name,
                "canonical_path": canonical,
                "is_glob": False,
                "visibility": visibility,
            })

        return result

    def visit(node: Any) -> None:
        if node.type == "use_declaration":
            use_clause = None
            for child in node.children:
                if child.type not in ["use", ";", "visibility_modifier"]:
                    use_clause = child
                    break

            import_path = _get_text(use_clause) if use_clause else ""
            line = node.start_point[0] + 1
            visibility = _extract_visibility(node)
            is_glob = "*" in import_path

            # Handle grouped imports: use std::sync::{Arc, Mutex};
            if "::{" in import_path and "}" in import_path:
                expanded = _expand_grouped_import(import_path, line, visibility)
                uses.extend(expanded)
            else:
                # Simple import
                local_name = None
                if "::" in import_path and not is_glob:
                    parts = import_path.split("::")
                    local_name = parts[-1].strip()

                uses.append({
                    "file_path": file_path,
                    "line": line,
                    "import_path": import_path,
                    "local_name": local_name,
                    "canonical_path": import_path,
                    "is_glob": is_glob,
                    "visibility": visibility,
                })

        for child in node.children:
            visit(child)

    visit(root_node)
    return uses


def extract_rust_functions(root_node: Any, file_path: str) -> list[dict]:
    """Extract function definitions from tree-sitter AST.

    Args:
        root_node: Tree-sitter root node
        file_path: Path to the source file

    Returns:
        List of function dicts with keys matching rust_functions table
    """
    functions = []

    def visit(node: Any) -> None:
        if node.type == "function_item":
            name_node = _get_child_by_type(node, "identifier")
            params_node = _get_child_by_type(node, "parameters")
            block_node = _get_child_by_type(node, "block")

            return_type = None
            for i, child in enumerate(node.children):
                if child.type == "->":
                    if i + 1 < len(node.children):
                        return_type = _get_text(node.children[i + 1])
                    break

            extern_modifier = _get_child_by_type(node, "extern_modifier")
            abi = None
            if extern_modifier:
                abi_node = _get_child_by_type(extern_modifier, "string_literal")
                abi = _get_text(abi_node).strip('"') if abi_node else "C"

            functions.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1 if block_node else node.start_point[0] + 1,
                "name": _get_text(name_node) if name_node else "",
                "visibility": _extract_visibility(node),
                "is_async": _has_modifier(node, "async"),
                "is_unsafe": _has_modifier(node, "unsafe"),
                "is_const": _has_modifier(node, "const"),
                "is_extern": extern_modifier is not None,
                "abi": abi,
                "return_type": return_type,
                "params_json": _get_text(params_node) if params_node else None,
                "generics": _extract_generics(node),
                "where_clause": _extract_where_clause(node),
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return functions


def extract_rust_structs(root_node: Any, file_path: str) -> list[dict]:
    """Extract struct definitions from tree-sitter AST.

    Args:
        root_node: Tree-sitter root node
        file_path: Path to the source file

    Returns:
        List of struct dicts with keys matching rust_structs table
    """
    structs = []

    def visit(node: Any) -> None:
        if node.type == "struct_item":
            name_node = _get_child_by_type(node, "type_identifier")
            field_list = _get_child_by_type(node, "field_declaration_list")
            tuple_fields = _get_child_by_type(node, "ordered_field_declaration_list")

            is_tuple = tuple_fields is not None
            is_unit = field_list is None and tuple_fields is None

            structs.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "name": _get_text(name_node) if name_node else "",
                "visibility": _extract_visibility(node),
                "generics": _extract_generics(node),
                "is_tuple_struct": is_tuple,
                "is_unit_struct": is_unit,
                "derives_json": None,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return structs


def extract_rust_enums(root_node: Any, file_path: str) -> list[dict]:
    """Extract enum definitions from tree-sitter AST.

    Args:
        root_node: Tree-sitter root node
        file_path: Path to the source file

    Returns:
        List of enum dicts with keys matching rust_enums table
    """
    enums = []

    def visit(node: Any) -> None:
        if node.type == "enum_item":
            name_node = _get_child_by_type(node, "type_identifier")

            enums.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "name": _get_text(name_node) if name_node else "",
                "visibility": _extract_visibility(node),
                "generics": _extract_generics(node),
                "derives_json": None,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return enums


def extract_rust_traits(root_node: Any, file_path: str) -> list[dict]:
    """Extract trait definitions from tree-sitter AST.

    Args:
        root_node: Tree-sitter root node
        file_path: Path to the source file

    Returns:
        List of trait dicts with keys matching rust_traits table
    """
    traits = []

    def visit(node: Any) -> None:
        if node.type == "trait_item":
            name_node = _get_child_by_type(node, "type_identifier")

            is_unsafe = False
            for child in node.children:
                if child.type == "unsafe":
                    is_unsafe = True
                    break

            supertraits = None
            trait_bounds = _get_child_by_type(node, "trait_bounds")
            if trait_bounds:
                # trait_bounds includes the `:` prefix, strip it
                supertraits = _get_text(trait_bounds).lstrip(": ").strip()

            is_auto = False
            for child in node.children:
                if child.type == "auto":
                    is_auto = True
                    break

            traits.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "name": _get_text(name_node) if name_node else "",
                "visibility": _extract_visibility(node),
                "generics": _extract_generics(node),
                "supertraits": supertraits,
                "is_unsafe": is_unsafe,
                "is_auto": is_auto,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return traits


def extract_rust_impl_blocks(root_node: Any, file_path: str) -> list[dict]:
    """Extract impl blocks from tree-sitter AST.

    Args:
        root_node: Tree-sitter root node
        file_path: Path to the source file

    Returns:
        List of impl block dicts with keys matching rust_impl_blocks table
    """
    impls = []

    def visit(node: Any) -> None:
        if node.type == "impl_item":
            is_unsafe = False
            for child in node.children:
                if child.type == "unsafe":
                    is_unsafe = True
                    break

            target_type = None
            trait_name = None

            type_nodes = _get_children_by_type(node, "type_identifier")
            generic_types = _get_children_by_type(node, "generic_type")

            for_keyword_found = False
            for child in node.children:
                if child.type == "for":
                    for_keyword_found = True
                    break

            if for_keyword_found:
                if len(type_nodes) >= 1:
                    trait_name = _get_text(type_nodes[0])
                if len(type_nodes) >= 2:
                    target_type = _get_text(type_nodes[1])
                elif len(generic_types) >= 1:
                    target_type = _get_text(generic_types[0])
            else:
                if type_nodes:
                    target_type = _get_text(type_nodes[0])
                elif generic_types:
                    target_type = _get_text(generic_types[0])

            impls.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "target_type_raw": target_type or "",
                "target_type_resolved": None,
                "trait_name": trait_name,
                "trait_resolved": None,
                "generics": _extract_generics(node),
                "where_clause": _extract_where_clause(node),
                "is_unsafe": is_unsafe,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return impls


# =============================================================================
# Phase 2: Advanced Extraction Functions
# =============================================================================


def extract_rust_struct_fields(root_node: Any, file_path: str) -> list[dict]:
    """Extract struct field definitions from tree-sitter AST."""
    fields = []

    def visit(node: Any) -> None:
        if node.type == "struct_item":
            struct_line = node.start_point[0] + 1
            field_list = _get_child_by_type(node, "field_declaration_list")
            tuple_fields = _get_child_by_type(node, "ordered_field_declaration_list")

            if field_list:
                # Named struct fields
                field_idx = 0
                for child in field_list.children:
                    if child.type == "field_declaration":
                        name_node = _get_child_by_type(child, "field_identifier")
                        type_node = None
                        for c in child.children:
                            if c.type not in ["field_identifier", "visibility_modifier", ":"]:
                                type_node = c
                                break
                        vis = _extract_visibility(child)
                        fields.append({
                            "file_path": file_path,
                            "struct_line": struct_line,
                            "field_index": field_idx,
                            "field_name": _get_text(name_node) if name_node else None,
                            "field_type": _get_text(type_node) if type_node else "",
                            "visibility": vis,
                            "is_pub": vis.startswith("pub"),
                        })
                        field_idx += 1

            elif tuple_fields:
                # Tuple struct fields
                field_idx = 0
                for child in tuple_fields.children:
                    if child.type not in ["(", ")", ","]:
                        vis = ""
                        type_node = child
                        if child.type == "visibility_modifier":
                            vis = _get_text(child)
                            continue
                        fields.append({
                            "file_path": file_path,
                            "struct_line": struct_line,
                            "field_index": field_idx,
                            "field_name": None,
                            "field_type": _get_text(type_node),
                            "visibility": vis,
                            "is_pub": vis.startswith("pub"),
                        })
                        field_idx += 1

        for child in node.children:
            visit(child)

    visit(root_node)
    return fields


def extract_rust_enum_variants(root_node: Any, file_path: str) -> list[dict]:
    """Extract enum variant definitions from tree-sitter AST."""
    variants = []

    def visit(node: Any) -> None:
        if node.type == "enum_item":
            enum_line = node.start_point[0] + 1
            variant_list = _get_child_by_type(node, "enum_variant_list")

            if variant_list:
                variant_idx = 0
                for child in variant_list.children:
                    if child.type == "enum_variant":
                        name_node = _get_child_by_type(child, "identifier")
                        tuple_fields = _get_child_by_type(child, "ordered_field_declaration_list")
                        struct_fields = _get_child_by_type(child, "field_declaration_list")
                        discriminant = None

                        # Check for discriminant (= value)
                        for i, c in enumerate(child.children):
                            if c.type == "=":
                                if i + 1 < len(child.children):
                                    discriminant = _get_text(child.children[i + 1])

                        kind = "unit"
                        fields_json = None
                        if tuple_fields:
                            kind = "tuple"
                            fields_json = _get_text(tuple_fields)
                        elif struct_fields:
                            kind = "struct"
                            fields_json = _get_text(struct_fields)

                        variants.append({
                            "file_path": file_path,
                            "enum_line": enum_line,
                            "variant_index": variant_idx,
                            "variant_name": _get_text(name_node) if name_node else "",
                            "variant_kind": kind,
                            "fields_json": fields_json,
                            "discriminant": discriminant,
                        })
                        variant_idx += 1

        for child in node.children:
            visit(child)

    visit(root_node)
    return variants


def extract_rust_trait_methods(root_node: Any, file_path: str) -> list[dict]:
    """Extract trait method signatures from tree-sitter AST."""
    methods = []

    def visit(node: Any) -> None:
        if node.type == "trait_item":
            trait_line = node.start_point[0] + 1
            decl_list = _get_child_by_type(node, "declaration_list")

            if decl_list:
                for child in decl_list.children:
                    if child.type == "function_signature_item" or child.type == "function_item":
                        name_node = _get_child_by_type(child, "identifier")
                        params_node = _get_child_by_type(child, "parameters")
                        has_default = child.type == "function_item"  # Has body

                        return_type = None
                        for i, c in enumerate(child.children):
                            if c.type == "->":
                                if i + 1 < len(child.children):
                                    return_type = _get_text(child.children[i + 1])

                        is_async = _has_modifier(child, "async") if child.type == "function_item" else False

                        methods.append({
                            "file_path": file_path,
                            "trait_line": trait_line,
                            "method_line": child.start_point[0] + 1,
                            "method_name": _get_text(name_node) if name_node else "",
                            "return_type": return_type,
                            "params_json": _get_text(params_node) if params_node else None,
                            "has_default": has_default,
                            "is_async": is_async,
                        })

        for child in node.children:
            visit(child)

    visit(root_node)
    return methods


def extract_rust_macros(root_node: Any, file_path: str) -> list[dict]:
    """Extract macro definitions from tree-sitter AST."""
    macros = []

    def visit(node: Any) -> None:
        if node.type == "macro_definition":
            name_node = _get_child_by_type(node, "identifier")
            macros.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "name": _get_text(name_node) if name_node else "",
                "macro_type": "macro_rules",
                "visibility": _extract_visibility(node),
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return macros


def extract_rust_macro_invocations(root_node: Any, file_path: str) -> list[dict]:
    """Extract macro invocations from tree-sitter AST."""
    invocations = []
    current_function = [None]

    def visit(node: Any) -> None:
        if node.type == "function_item":
            name_node = _get_child_by_type(node, "identifier")
            old_func = current_function[0]
            current_function[0] = _get_text(name_node) if name_node else None

            for child in node.children:
                visit(child)

            current_function[0] = old_func
            return

        if node.type == "macro_invocation":
            name_node = None
            for child in node.children:
                if child.type == "identifier" or child.type == "scoped_identifier":
                    name_node = child
                    break

            # Extract args sample
            args_sample = None
            token_tree = _get_child_by_type(node, "token_tree")
            if token_tree:
                args_text = _get_text(token_tree)
                args_sample = args_text[:200] if args_text else None

            invocations.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "macro_name": _get_text(name_node) if name_node else "",
                "containing_function": current_function[0],
                "args_sample": args_sample,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return invocations


def extract_rust_async_functions(root_node: Any, file_path: str) -> list[dict]:
    """Extract async function metadata from tree-sitter AST."""
    async_funcs = []

    def count_awaits(node: Any) -> int:
        count = 0
        if node.type == "await_expression":
            count = 1
        for child in node.children:
            count += count_awaits(child)
        return count

    def visit(node: Any) -> None:
        if node.type == "function_item" and _has_modifier(node, "async"):
            name_node = _get_child_by_type(node, "identifier")
            block_node = _get_child_by_type(node, "block")

            return_type = None
            for i, child in enumerate(node.children):
                if child.type == "->":
                    if i + 1 < len(node.children):
                        return_type = _get_text(node.children[i + 1])
                    break

            await_count = count_awaits(block_node) if block_node else 0

            async_funcs.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "function_name": _get_text(name_node) if name_node else "",
                "return_type": return_type,
                "has_await": await_count > 0,
                "await_count": await_count,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return async_funcs


def extract_rust_await_points(root_node: Any, file_path: str) -> list[dict]:
    """Extract await expression locations from tree-sitter AST."""
    awaits = []
    current_function = [None]

    def visit(node: Any) -> None:
        if node.type == "function_item":
            name_node = _get_child_by_type(node, "identifier")
            old_func = current_function[0]
            current_function[0] = _get_text(name_node) if name_node else None

            for child in node.children:
                visit(child)

            current_function[0] = old_func
            return

        if node.type == "await_expression":
            awaited_expr = None
            for child in node.children:
                if child.type != "await":
                    awaited_expr = _get_text(child)
                    break

            awaits.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "containing_function": current_function[0],
                "awaited_expression": awaited_expr[:200] if awaited_expr else None,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return awaits


def extract_rust_unsafe_blocks(root_node: Any, file_path: str) -> list[dict]:
    """Extract unsafe block locations from tree-sitter AST."""
    import json

    blocks = []
    current_function = [None]

    def get_preceding_comment(node: Any) -> str | None:
        """Get SAFETY comment from preceding sibling or line."""
        # Check previous sibling
        if hasattr(node, "prev_sibling") and node.prev_sibling:
            sibling = node.prev_sibling
            if sibling.type == "line_comment":
                text = _get_text(sibling)
                if "SAFETY" in text.upper():
                    return text
        return None

    def catalog_unsafe_operations(block_node: Any) -> list[dict]:
        """Catalog unsafe operations within a block.

        Detects:
        - Raw pointer dereferences (*ptr)
        - Calls to unsafe functions (transmute, etc.)
        - FFI calls (extern functions)
        - Mutable static access
        - as_ptr/as_mut_ptr calls
        """
        operations = []

        def scan_operations(node: Any) -> None:
            # Raw pointer dereference: unary_expression with *
            if node.type == "unary_expression":
                op = _get_child_by_type(node, "*")
                if op:
                    operations.append({
                        "type": "ptr_deref",
                        "line": node.start_point[0] + 1,
                        "text": _get_text(node)[:50],
                    })

            # Function calls - check for known unsafe patterns
            if node.type == "call_expression":
                func_node = node.children[0] if node.children else None
                func_name = _get_text(func_node) if func_node else ""

                # Known unsafe std functions
                unsafe_patterns = [
                    "transmute", "transmute_copy", "zeroed", "uninitialized",
                    "from_raw", "into_raw", "as_ptr", "as_mut_ptr",
                    "read", "write", "copy", "copy_nonoverlapping",
                    "offset", "add", "sub",  # pointer arithmetic
                ]
                for pattern in unsafe_patterns:
                    if pattern in func_name:
                        operations.append({
                            "type": "unsafe_call",
                            "line": node.start_point[0] + 1,
                            "function": func_name[:100],
                        })
                        break

            # Method calls on raw pointers
            if node.type == "field_expression":
                text = _get_text(node)
                if ".as_ptr()" in text or ".as_mut_ptr()" in text:
                    operations.append({
                        "type": "ptr_cast",
                        "line": node.start_point[0] + 1,
                        "text": text[:50],
                    })

            # Static mut access
            if node.type == "identifier":
                # Check if accessing a static mut (heuristic: SCREAMING_CASE)
                name = _get_text(node)
                if name.isupper() and len(name) > 1:
                    operations.append({
                        "type": "static_access",
                        "line": node.start_point[0] + 1,
                        "name": name,
                    })

            for child in node.children:
                scan_operations(child)

        if block_node:
            scan_operations(block_node)

        return operations

    def visit(node: Any) -> None:
        if node.type == "function_item":
            name_node = _get_child_by_type(node, "identifier")
            old_func = current_function[0]
            current_function[0] = _get_text(name_node) if name_node else None

            for child in node.children:
                visit(child)

            current_function[0] = old_func
            return

        if node.type == "unsafe_block":
            safety_comment = get_preceding_comment(node)
            block_node = _get_child_by_type(node, "block")

            # Catalog operations inside the unsafe block
            operations = catalog_unsafe_operations(block_node)
            operations_json = json.dumps(operations) if operations else None

            blocks.append({
                "file_path": file_path,
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
                "containing_function": current_function[0],
                "reason": None,
                "safety_comment": safety_comment,
                "has_safety_comment": safety_comment is not None,
                "operations_json": operations_json,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return blocks


def extract_rust_unsafe_traits(root_node: Any, file_path: str) -> list[dict]:
    """Extract unsafe trait implementations from tree-sitter AST."""
    unsafe_traits = []

    def visit(node: Any) -> None:
        if node.type == "impl_item":
            is_unsafe = False
            for child in node.children:
                if child.type == "unsafe":
                    is_unsafe = True
                    break

            if is_unsafe:
                trait_name = None
                impl_type = None

                for_found = False
                for child in node.children:
                    if child.type == "for":
                        for_found = True
                        break

                if for_found:
                    type_nodes = _get_children_by_type(node, "type_identifier")
                    if len(type_nodes) >= 1:
                        trait_name = _get_text(type_nodes[0])
                    if len(type_nodes) >= 2:
                        impl_type = _get_text(type_nodes[1])

                    unsafe_traits.append({
                        "file_path": file_path,
                        "line": node.start_point[0] + 1,
                        "trait_name": trait_name or "",
                        "impl_type": impl_type,
                    })

        for child in node.children:
            visit(child)

    visit(root_node)
    return unsafe_traits


def extract_rust_extern_blocks(root_node: Any, file_path: str) -> list[dict]:
    """Extract extern block metadata from tree-sitter AST."""
    blocks = []

    def visit(node: Any) -> None:
        if node.type == "foreign_mod_item":
            abi = "C"
            extern_modifier = _get_child_by_type(node, "extern_modifier")
            if extern_modifier:
                abi_node = _get_child_by_type(extern_modifier, "string_literal")
                if abi_node:
                    abi = _get_text(abi_node).strip('"')

            blocks.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "abi": abi,
            })

        for child in node.children:
            visit(child)

    visit(root_node)
    return blocks


def extract_rust_extern_functions(root_node: Any, file_path: str) -> list[dict]:
    """Extract extern function declarations from tree-sitter AST."""
    funcs = []

    def visit(node: Any, current_abi: str = "C") -> None:
        if node.type == "foreign_mod_item":
            abi = "C"
            extern_modifier = _get_child_by_type(node, "extern_modifier")
            if extern_modifier:
                abi_node = _get_child_by_type(extern_modifier, "string_literal")
                if abi_node:
                    abi = _get_text(abi_node).strip('"')

            decl_list = _get_child_by_type(node, "declaration_list")
            if decl_list:
                for child in decl_list.children:
                    visit(child, abi)
            return

        if node.type == "function_signature_item":
            name_node = _get_child_by_type(node, "identifier")
            params_node = _get_child_by_type(node, "parameters")

            return_type = None
            for i, child in enumerate(node.children):
                if child.type == "->":
                    if i + 1 < len(node.children):
                        return_type = _get_text(node.children[i + 1])
                    break

            # Check for variadic
            is_variadic = False
            if params_node:
                params_text = _get_text(params_node)
                is_variadic = "..." in params_text

            funcs.append({
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "name": _get_text(name_node) if name_node else "",
                "abi": current_abi,
                "return_type": return_type,
                "params_json": _get_text(params_node) if params_node else None,
                "is_variadic": is_variadic,
            })

        for child in node.children:
            visit(child, current_abi)

    visit(root_node)
    return funcs


def extract_rust_generics(root_node: Any, file_path: str) -> list[dict]:
    """Extract generic type parameters from tree-sitter AST."""
    generics = []

    def extract_from_type_params(node: Any, parent_line: int, parent_type: str) -> None:
        type_params = _get_child_by_type(node, "type_parameters")
        if not type_params:
            return

        for child in type_params.children:
            # type_parameter: simple type like T, or constrained like T: Clone
            if child.type == "type_parameter":
                name_node = _get_child_by_type(child, "type_identifier")
                bounds_node = _get_child_by_type(child, "trait_bounds")
                generics.append({
                    "file_path": file_path,
                    "parent_line": parent_line,
                    "parent_type": parent_type,
                    "param_name": _get_text(name_node) if name_node else "",
                    "param_kind": "type",
                    "bounds": _get_text(bounds_node).lstrip(": ") if bounds_node else None,
                    "default_value": None,
                })
            # lifetime_parameter: 'a, 'b, etc.
            elif child.type == "lifetime_parameter":
                lt_node = _get_child_by_type(child, "lifetime")
                generics.append({
                    "file_path": file_path,
                    "parent_line": parent_line,
                    "parent_type": parent_type,
                    "param_name": _get_text(lt_node) if lt_node else "",
                    "param_kind": "lifetime",
                    "bounds": None,
                    "default_value": None,
                })
            # const_parameter: const N: usize
            elif child.type == "const_parameter":
                name_node = _get_child_by_type(child, "identifier")
                generics.append({
                    "file_path": file_path,
                    "parent_line": parent_line,
                    "parent_type": parent_type,
                    "param_name": _get_text(name_node) if name_node else "",
                    "param_kind": "const",
                    "bounds": None,
                    "default_value": None,
                })

    def visit(node: Any) -> None:
        if node.type == "struct_item":
            extract_from_type_params(node, node.start_point[0] + 1, "struct")
        elif node.type == "enum_item":
            extract_from_type_params(node, node.start_point[0] + 1, "enum")
        elif node.type == "function_item":
            extract_from_type_params(node, node.start_point[0] + 1, "function")
        elif node.type == "trait_item":
            extract_from_type_params(node, node.start_point[0] + 1, "trait")
        elif node.type == "impl_item":
            extract_from_type_params(node, node.start_point[0] + 1, "impl")

        for child in node.children:
            visit(child)

    visit(root_node)
    return generics


def extract_rust_lifetimes(root_node: Any, file_path: str) -> list[dict]:
    """Extract lifetime parameters from tree-sitter AST."""
    lifetimes = []
    seen = set()

    def extract_from_type_params(node: Any, parent_line: int) -> None:
        type_params = _get_child_by_type(node, "type_parameters")
        if not type_params:
            return

        for child in type_params.children:
            # lifetime_parameter node contains the lifetime
            if child.type == "lifetime_parameter":
                lt_node = _get_child_by_type(child, "lifetime")
                name = _get_text(lt_node) if lt_node else ""
                key = (file_path, parent_line, name)
                if key not in seen:
                    seen.add(key)
                    lifetimes.append({
                        "file_path": file_path,
                        "parent_line": parent_line,
                        "lifetime_name": name,
                        "is_static": name == "'static",
                    })

    def visit(node: Any) -> None:
        if node.type in ["struct_item", "enum_item", "function_item", "trait_item", "impl_item"]:
            extract_from_type_params(node, node.start_point[0] + 1)

        for child in node.children:
            visit(child)

    visit(root_node)
    return lifetimes
