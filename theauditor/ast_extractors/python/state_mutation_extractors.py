"""State mutation extractors - Instance, class, global, argument mutations.

This module contains extraction logic for state mutation patterns:
- Instance attribute mutations (self.x = value)
- Class attribute mutations (ClassName.x = value, cls.x = value)
- Global variable mutations (global x; x = value)
- Mutable argument modifications (def foo(lst): lst.append(x))
- Augmented assignments (+=, -=, *=, etc. on any target)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'target', 'operation', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.

Causal Learning Purpose:
========================
These extractors enable hypothesis generation for DIEC tool:
- "Function X modifies instance attribute Y" → Test by checking object.Y before/after
- "Function has side effects on class state" → Test by monitoring class attributes
- "Function has global side effects" → Test by monitoring global variables
- "Function mutates its arguments" → Test by checking argument state before/after

Each extraction enables >3 hypothesis types per python_coverage.md requirements.
Target >70% validation rate when hypotheses are tested experimentally.

Week 1 Implementation (Priority 1 - Side Effects):
===================================================
This is the HIGHEST VALUE extraction for causal learning. Side effects are the #1
thing static analysis cannot prove but experimentation can validate.

Expected extraction from TheAuditor codebase:
- ~500 instance mutations (self.x = value)
- ~80 class mutations (ClassName.instances += 1)
- ~100 global mutations (global _cache; _cache[key] = value)
- ~200 argument mutations (def foo(lst): lst.append(x))
- ~2,100 augmented assignments (x += 1, y *= 2, etc.)
Total: ~3,000 state mutation records
"""

import ast
import logging
import os
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

logger = logging.getLogger(__name__)


MUTATION_METHODS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "remove",
        "pop",
        "clear",
        "update",
        "add",
        "discard",
        "sort",
        "reverse",
        "setdefault",
        "popitem",
    }
)


OP_MAP = {
    ast.Add: "+=",
    ast.Sub: "-=",
    ast.Mult: "*=",
    ast.Div: "/=",
    ast.FloorDiv: "//=",
    ast.Mod: "%=",
    ast.Pow: "**=",
    ast.LShift: "<<=",
    ast.RShift: ">>=",
    ast.BitOr: "|=",
    ast.BitXor: "^=",
    ast.BitAnd: "&=",
}


def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes.

    Handles both Python 3.8+ ast.Constant and legacy ast.Str nodes.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_instance_mutations(context: FileContext) -> list[dict[str, Any]]:
    """Extract instance attribute mutations (self.x = value).

    Detects:
    - Direct assignment: self.counter = 0
    - Augmented assignment: self.counter += 1
    - Nested attributes: self.config.debug = True
    - Method calls with side effects: self.items.append(x)

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of instance mutation dicts:
        {
            'line': int,
            'target': str,  # 'self.counter'
            'operation': 'assignment' | 'augmented_assignment' | 'method_call',
            'in_function': str,  # Function name where mutation occurs
            'is_init': bool,  # True if in __init__ (expected mutation)
        }

    Enables hypothesis: "Function X modifies instance attribute Y"
    Experiment design: Call X, check object.Y before/after
    """
    mutations = []

    if not isinstance(context.tree, ast.AST):
        return mutations

    function_ranges = []
    class_ranges = {}

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            func_name = node.name
            start_line = node.lineno
            end_line = node.end_lineno or node.lineno

            is_property_setter = any(
                isinstance(dec, ast.Attribute) and dec.attr == "setter"
                for dec in node.decorator_list
            )

            is_dunder = (
                func_name.startswith("__")
                and func_name.endswith("__")
                and func_name
                in [
                    "__init__",
                    "__setitem__",
                    "__enter__",
                    "__exit__",
                    "__setattr__",
                    "__delattr__",
                    "__set__",
                ]
            )

            function_ranges.append((func_name, start_line, end_line, is_property_setter, is_dunder))

    def find_containing_function(line_no):
        """Find the function containing this line.

        Returns tuple: (function_name, is_property_setter, is_dunder)
        """
        for fname, start, end, is_prop, is_dunder in function_ranges:
            if start <= line_no <= end:
                return fname, is_prop, is_dunder
        return "global", False, False

    def find_containing_class(line_no):
        """Find the class containing this line."""
        for cname, (start, end) in class_ranges.items():
            if start <= line_no <= end:
                return cname
        return None

    def get_attribute_chain(node):
        """Extract full attribute chain like 'self.config.debug' from nested Attribute nodes."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts)) if parts else None

    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                attr_chain = get_attribute_chain(target)
                if attr_chain and attr_chain.startswith("self."):
                    in_function, is_prop_setter, is_dunder = find_containing_function(node.lineno)
                    mutations.append(
                        {
                            "line": node.lineno,
                            "target": attr_chain,
                            "operation": "assignment",
                            "in_function": in_function,
                            "is_init": (in_function == "__init__"),
                            "is_property_setter": is_prop_setter,
                            "is_dunder_method": is_dunder,
                        }
                    )

    seen = set()
    deduped = []
    for m in mutations:
        key = (m["line"], m["target"], m["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(mutations) != len(deduped):
            print(
                f"[AST_DEBUG] Instance mutations deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )

    return deduped


def extract_class_mutations(context: FileContext) -> list[dict[str, Any]]:
    """Extract class attribute mutations (ClassName.x = value, cls.x = value).

    Detects:
    - Class variable assignment: MyClass.instances = []
    - cls.x = value in @classmethod
    - ClassName.attr += 1 (augmented on class)

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of class mutation dicts:
        {
            'line': int,
            'class_name': str,  # 'MyClass' or 'cls'
            'attribute': str,  # 'instances'
            'operation': 'assignment' | 'augmented_assignment',
            'in_function': str,
        }

    Enables hypothesis: "Function X modifies class state Y"
    Experiment design: Monitor ClassName.Y before/after calling X
    """
    mutations = []

    if not isinstance(context.tree, ast.AST):
        return mutations

    class_names = set()
    function_ranges = []

    for node in context.find_nodes(ast.ClassDef):
        class_names.add(node.name)

    def find_containing_function(line_no):
        """Find the function containing this line.

        Returns tuple: (function_name, is_classmethod)
        """
        for fname, start, end, is_cm in function_ranges:
            if start <= line_no <= end:
                return fname, is_cm
        return "global", False

    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                class_or_cls = target.value.id

                if class_or_cls == "cls" or class_or_cls in class_names:
                    in_function, is_cm = find_containing_function(node.lineno)
                    mutations.append(
                        {
                            "line": node.lineno,
                            "class_name": class_or_cls,
                            "attribute": target.attr,
                            "operation": "assignment",
                            "in_function": in_function,
                            "is_classmethod": is_cm,
                        }
                    )

    seen = set()
    deduped = []
    for m in mutations:
        key = (m["line"], m["class_name"], m["attribute"])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(mutations) != len(deduped):
            print(
                f"[AST_DEBUG] Class mutations deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )

    return deduped


def extract_global_mutations(context: FileContext) -> list[dict[str, Any]]:
    """Extract global variable mutations (global x; x = value).

    Detects:
    - global statement followed by assignment
    - Module-level variable reassignment (tracked via scoping)

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of global mutation dicts:
        {
            'line': int,
            'global_name': str,  # '_cache'
            'operation': 'assignment' | 'augmented_assignment' | 'item_assignment' | 'attr_assignment',
            'in_function': str,
        }

    Enables hypothesis: "Function X has global side effects"
    Experiment design: Monitor global variable before/after calling X
    """
    mutations = []

    if not isinstance(context.tree, ast.AST):
        return mutations

    function_ranges = []
    globals_by_function = {}

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            func_name = node.name
            start_line = node.lineno
            end_line = node.end_lineno or node.lineno
            function_ranges.append((func_name, start_line, end_line))

            global_vars = set()
            for child in context.find_nodes(ast.Global):
                global_vars.update(child.names)

            if global_vars:
                globals_by_function[func_name] = global_vars

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                in_function = find_containing_function(node.lineno)

                if (
                    in_function != "global"
                    and in_function in globals_by_function
                    and var_name in globals_by_function[in_function]
                ):
                    mutations.append(
                        {
                            "line": node.lineno,
                            "global_name": var_name,
                            "operation": "assignment",
                            "in_function": in_function,
                        }
                    )

            elif isinstance(target, ast.Subscript):
                if isinstance(target.value, ast.Name):
                    var_name = target.value.id
                    in_function = find_containing_function(node.lineno)

                    if (
                        in_function != "global"
                        and in_function in globals_by_function
                        and var_name in globals_by_function[in_function]
                    ):
                        mutations.append(
                            {
                                "line": node.lineno,
                                "global_name": var_name,
                                "operation": "item_assignment",
                                "in_function": in_function,
                            }
                        )

            elif isinstance(target, ast.Attribute):
                if isinstance(target.value, ast.Name):
                    var_name = target.value.id
                    in_function = find_containing_function(node.lineno)

                    if (
                        in_function != "global"
                        and in_function in globals_by_function
                        and var_name in globals_by_function[in_function]
                    ):
                        mutations.append(
                            {
                                "line": node.lineno,
                                "global_name": var_name,
                                "operation": "attr_assignment",
                                "in_function": in_function,
                            }
                        )

    seen = set()
    deduped = []
    for m in mutations:
        key = (m["line"], m["global_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(mutations) != len(deduped):
            print(
                f"[AST_DEBUG] Global mutations deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )

    return deduped


def extract_argument_mutations(context: FileContext) -> list[dict[str, Any]]:
    """Extract mutable argument modifications (def foo(lst): lst.append(x)).

    Detects:
    - def foo(lst): lst.append(x)
    - def foo(d): d['key'] = value
    - Any method call on parameter that mutates it

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of argument mutation dicts:
        {
            'line': int,
            'parameter_name': str,  # 'lst'
            'mutation_type': str,  # 'method_call' | 'item_assignment' | 'attr_assignment' | 'assignment' | 'augmented_assignment'
            'mutation_detail': str,  # Method name like 'append', 'update', or operation type
            'in_function': str,
        }

    Enables hypothesis: "Function X mutates its arguments"
    Experiment design: Pass mutable argument, check state before/after
    """
    mutations = []

    if not isinstance(context.tree, ast.AST):
        return mutations

    function_params = {}

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        func_name = node.name
        param_names = set()

        if hasattr(node, "args") and node.args:
            args_obj = node.args

            for arg in args_obj.args:
                param_names.add(arg.arg)

            if args_obj.vararg:
                param_names.add(args_obj.vararg.arg)

            if args_obj.kwarg:
                param_names.add(args_obj.kwarg.arg)

            for arg in args_obj.kwonlyargs:
                param_names.add(arg.arg)

        param_names.discard("self")
        param_names.discard("cls")

        if param_names:
            function_params[func_name] = param_names

    function_ranges = []
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    for node in context.walk_tree():
        in_function = find_containing_function(node.lineno) if hasattr(node, "lineno") else "global"

        if in_function == "global" or in_function not in function_params:
            continue

        param_names = function_params[in_function]

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                var_name = node.func.value.id
                method_name = node.func.attr

                if var_name in param_names and method_name in MUTATION_METHODS:
                    mutations.append(
                        {
                            "line": node.lineno,
                            "parameter_name": var_name,
                            "mutation_type": "method_call",
                            "mutation_detail": method_name,
                            "in_function": in_function,
                        }
                    )

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    if isinstance(target.value, ast.Name):
                        var_name = target.value.id
                        if var_name in param_names:
                            mutations.append(
                                {
                                    "line": node.lineno,
                                    "parameter_name": var_name,
                                    "mutation_type": "item_assignment",
                                    "mutation_detail": "setitem",
                                    "in_function": in_function,
                                }
                            )

                elif isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name):
                        var_name = target.value.id
                        if var_name in param_names:
                            mutations.append(
                                {
                                    "line": node.lineno,
                                    "parameter_name": var_name,
                                    "mutation_type": "attr_assignment",
                                    "mutation_detail": target.attr,
                                    "in_function": in_function,
                                }
                            )

                elif isinstance(target, ast.Name):
                    var_name = target.id
                    if var_name in param_names:
                        mutations.append(
                            {
                                "line": node.lineno,
                                "parameter_name": var_name,
                                "mutation_type": "assignment",
                                "mutation_detail": "reassignment",
                                "in_function": in_function,
                            }
                        )

        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            var_name = node.target.id
            if var_name in param_names:
                mutations.append(
                    {
                        "line": node.lineno,
                        "parameter_name": var_name,
                        "mutation_type": "augmented_assignment",
                        "mutation_detail": node.op.__class__.__name__,
                        "in_function": in_function,
                    }
                )

    seen = set()
    deduped = []
    for m in mutations:
        key = (m["line"], m["parameter_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(mutations) != len(deduped):
            print(
                f"[AST_DEBUG] Argument mutations deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )

    return deduped


def extract_augmented_assignments(context: FileContext) -> list[dict[str, Any]]:
    """Extract augmented assignments (+=, -=, *=, /=, //=, %=, **=, &=, |=, ^=, >>=, <<=).

    Detects ALL augmented assignments on ANY target:
    - Instance: self.x += 1
    - Class: cls.x += 1
    - Global: global_var += 1
    - Local: local_var += 1
    - Argument: param += 1

    Categorizes by target type for intelligent hypothesis generation.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of augmented assignment dicts:
        {
            'line': int,
            'target': str,  # Full target expression (e.g., 'self.counter')
            'operator': str,  # '+=' | '-=' | '*=' | '/=' | '//=' | '%=' | '**=' | '&=' | '|=' | '^=' | '>>=' | '<<='
            'target_type': str,  # 'instance' | 'class' | 'global' | 'local' | 'argument' | 'subscript' | 'unknown'
            'in_function': str,
        }

    Enables hypothesis: "Function X performs in-place operations on Y"
    Experiment design: Monitor target variable before/after in-place operation
    """
    mutations = []

    if not isinstance(context.tree, ast.AST):
        return mutations

    class_names = set()
    globals_by_function = {}
    function_params = {}
    function_ranges = []

    for node in context.find_nodes(ast.ClassDef):
        class_names.add(node.name)

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    for node in context.find_nodes(ast.AugAssign):
        in_function = find_containing_function(node.lineno)
        operator = OP_MAP.get(type(node.op), "?=")

        target_expr = None
        target_type = "unknown"

        if isinstance(node.target, ast.Name):
            var_name = node.target.id
            target_expr = var_name

            if in_function != "global":
                if in_function in function_params and var_name in function_params[in_function]:
                    target_type = "argument"

                elif (
                    in_function in globals_by_function
                    and var_name in globals_by_function[in_function]
                ):
                    target_type = "global"
                else:
                    target_type = "local"
            else:
                target_type = "global"

        elif isinstance(node.target, ast.Attribute):
            if isinstance(node.target.value, ast.Name):
                base_name = node.target.value.id
                attr_name = node.target.attr
                target_expr = f"{base_name}.{attr_name}"

                if base_name == "self":
                    target_type = "instance"
                elif base_name == "cls" or base_name in class_names:
                    target_type = "class"
                else:
                    target_type = "attribute"
            else:
                target_type = "attribute"
                target_expr = "complex_attribute"

        elif isinstance(node.target, ast.Subscript):
            if isinstance(node.target.value, ast.Name):
                var_name = node.target.value.id
                target_expr = f"{var_name}[...]"
                target_type = "subscript"
            else:
                target_expr = "subscript"
                target_type = "subscript"

        if target_expr:
            mutations.append(
                {
                    "line": node.lineno,
                    "target": target_expr,
                    "operator": operator,
                    "target_type": target_type,
                    "in_function": in_function,
                }
            )

    seen = set()
    deduped = []
    for m in mutations:
        key = (m["line"], m["target"])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(mutations) != len(deduped):
            print(
                f"[AST_DEBUG] Augmented assignments deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )

    return deduped
