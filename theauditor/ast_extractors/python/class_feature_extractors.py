"""Advanced class feature extractors - Metaclasses, descriptors, dataclasses, enums."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext


def _find_containing_function(node: ast.AST, function_ranges: list) -> str:
    """Find the function containing this node."""
    if not hasattr(node, "lineno"):
        return "global"

    line_no = node.lineno
    for fname, start, end in function_ranges:
        if start <= line_no <= end:
            return fname
    return "global"


LIFECYCLE_DUNDERS = {"__init__", "__new__", "__del__"}
REPRESENTATION_DUNDERS = {"__str__", "__repr__", "__format__", "__bytes__"}
COMPARISON_DUNDERS = {"__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__hash__"}
NUMERIC_DUNDERS = {
    "__add__",
    "__sub__",
    "__mul__",
    "__truediv__",
    "__floordiv__",
    "__mod__",
    "__pow__",
    "__radd__",
    "__rsub__",
    "__rmul__",
    "__rtruediv__",
    "__rfloordiv__",
    "__rmod__",
    "__rpow__",
}
CONTAINER_DUNDERS = {
    "__len__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__contains__",
    "__iter__",
    "__next__",
}
ATTRIBUTE_DUNDERS = {"__getattr__", "__setattr__", "__delattr__", "__getattribute__"}
CALLABLE_DUNDERS = {"__call__"}
CONTEXT_DUNDERS = {"__enter__", "__exit__", "__aenter__", "__aexit__"}


def extract_metaclasses(context: FileContext) -> list[dict[str, Any]]:
    """Extract metaclass definitions and usage."""
    metaclasses = []

    if not isinstance(context.tree, ast.AST):
        return metaclasses

    for node in context.find_nodes(ast.ClassDef):
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "type":
                metaclass_data = {
                    "line": node.lineno,
                    "class_name": node.name,
                    "metaclass_name": node.name,
                    "is_definition": True,
                }
                metaclasses.append(metaclass_data)

        for keyword in node.keywords:
            if keyword.arg == "metaclass":
                metaclass_name = "unknown"
                if isinstance(keyword.value, ast.Name):
                    metaclass_name = keyword.value.id

                metaclass_data = {
                    "line": node.lineno,
                    "class_name": node.name,
                    "metaclass_name": metaclass_name,
                    "is_definition": False,
                }
                metaclasses.append(metaclass_data)

    return metaclasses


def extract_descriptors(context: FileContext) -> list[dict[str, Any]]:
    """Extract descriptor protocol implementations."""
    descriptors = []

    if not isinstance(context.tree, ast.AST):
        return descriptors

    for node in context.find_nodes(ast.ClassDef):
        has_get = False
        has_set = False
        has_delete = False

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == "__get__":
                    has_get = True
                elif item.name == "__set__":
                    has_set = True
                elif item.name == "__delete__":
                    has_delete = True

        if has_get:
            descriptor_type = "data" if has_set or has_delete else "non-data"

            descriptor_data = {
                "line": node.lineno,
                "class_name": node.name,
                "has_get": has_get,
                "has_set": has_set,
                "has_delete": has_delete,
                "descriptor_type": descriptor_type,
            }
            descriptors.append(descriptor_data)

    return descriptors


def extract_dataclasses(context: FileContext) -> list[dict[str, Any]]:
    """Extract dataclass definitions."""
    dataclasses = []

    if not isinstance(context.tree, ast.AST):
        return dataclasses

    for node in context.find_nodes(ast.ClassDef):
        has_dataclass = False
        frozen = False

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
                has_dataclass = True
            elif (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id == "dataclass"
            ):
                has_dataclass = True

                for keyword in decorator.keywords:
                    if keyword.arg == "frozen" and (
                        isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                    ):
                        frozen = True

        if has_dataclass:
            field_count = 0
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    field_count += 1

            dataclass_data = {
                "line": node.lineno,
                "class_name": node.name,
                "frozen": frozen,
                "field_count": field_count,
            }
            dataclasses.append(dataclass_data)

    return dataclasses


def extract_enums(context: FileContext) -> list[dict[str, Any]]:
    """Extract Enum class definitions."""
    enums = []

    if not isinstance(context.tree, ast.AST):
        return enums

    enum_types = {"Enum", "IntEnum", "Flag", "IntFlag", "StrEnum"}

    for node in context.find_nodes(ast.ClassDef):
        enum_type = None

        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in enum_types:
                enum_type = base.id
            elif isinstance(base, ast.Attribute) and base.attr in enum_types:
                enum_type = base.attr

        if enum_type:
            member_count = 0
            for item in node.body:
                if isinstance(item, ast.Assign):
                    member_count += len(item.targets)

            enum_data = {
                "line": node.lineno,
                "enum_name": node.name,
                "enum_type": enum_type,
                "member_count": member_count,
            }
            enums.append(enum_data)

    return enums


def extract_slots(context: FileContext) -> list[dict[str, Any]]:
    """Extract __slots__ usage."""
    slots = []

    if not isinstance(context.tree, ast.AST):
        return slots

    for node in context.find_nodes(ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__slots__":
                        slot_count = 0
                        if isinstance(item.value, (ast.List, ast.Tuple)):
                            slot_count = len(item.value.elts)

                        slots_data = {
                            "line": item.lineno,
                            "class_name": node.name,
                            "slot_count": slot_count,
                        }
                        slots.append(slots_data)

    return slots


def extract_abstract_classes(context: FileContext) -> list[dict[str, Any]]:
    """Extract abstract base classes (ABC) and abstract methods."""
    abstract_classes = []

    if not isinstance(context.tree, ast.AST):
        return abstract_classes

    for node in context.find_nodes(ast.ClassDef):
        inherits_abc = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in ("ABC", "ABCMeta"):
                inherits_abc = True

        abstract_method_count = 0
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "abstractmethod":
                        abstract_method_count += 1

        if inherits_abc or abstract_method_count > 0:
            abc_data = {
                "line": node.lineno,
                "class_name": node.name,
                "abstract_method_count": abstract_method_count,
            }
            abstract_classes.append(abc_data)

    return abstract_classes


def extract_method_types(context: FileContext) -> list[dict[str, Any]]:
    """Extract method types (@classmethod, @staticmethod, instance methods)."""
    method_types = []

    if not isinstance(context.tree, ast.AST):
        return method_types

    for node in context.find_nodes(ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_type = "instance"

                for decorator in item.decorator_list:
                    if isinstance(decorator, ast.Name):
                        if decorator.id == "classmethod":
                            method_type = "class"
                        elif decorator.id == "staticmethod":
                            method_type = "static"

                method_data = {
                    "line": item.lineno,
                    "method_name": item.name,
                    "method_type": method_type,
                    "in_class": node.name,
                }
                method_types.append(method_data)

    return method_types


def extract_multiple_inheritance(context: FileContext) -> list[dict[str, Any]]:
    """Extract multiple inheritance patterns."""
    multi_inheritance = []

    if not isinstance(context.tree, ast.AST):
        return multi_inheritance

    for node in context.find_nodes(ast.ClassDef):
        if len(node.bases) > 1:
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(base.attr)

            inheritance_data = {
                "line": node.lineno,
                "class_name": node.name,
                "base_count": len(node.bases),
                "base_classes": ", ".join(base_names),
            }
            multi_inheritance.append(inheritance_data)

    return multi_inheritance


def extract_dunder_methods(context: FileContext) -> list[dict[str, Any]]:
    """Extract dunder (magic) method definitions."""
    dunder_methods = []

    if not isinstance(context.tree, ast.AST):
        return dunder_methods

    def categorize_dunder(name):
        """Categorize dunder method by name."""
        if name in LIFECYCLE_DUNDERS:
            return "lifecycle"
        elif name in REPRESENTATION_DUNDERS:
            return "representation"
        elif name in COMPARISON_DUNDERS:
            return "comparison"
        elif name in NUMERIC_DUNDERS:
            return "numeric"
        elif name in CONTAINER_DUNDERS:
            return "container"
        elif name in ATTRIBUTE_DUNDERS:
            return "attribute"
        elif name in CALLABLE_DUNDERS:
            return "callable"
        elif name in CONTEXT_DUNDERS:
            return "context_manager"
        else:
            return "other"

    for node in context.find_nodes(ast.ClassDef):
        for item in node.body:
            if (
                isinstance(item, ast.FunctionDef)
                and item.name.startswith("__")
                and item.name.endswith("__")
            ):
                dunder_data = {
                    "line": item.lineno,
                    "method_name": item.name,
                    "category": categorize_dunder(item.name),
                    "in_class": node.name,
                }
                dunder_methods.append(dunder_data)

    return dunder_methods


def extract_visibility_conventions(context: FileContext) -> list[dict[str, Any]]:
    """Extract naming conventions for visibility (_private, __name_mangling)."""
    visibility = []

    if not isinstance(context.tree, ast.AST):
        return visibility

    for node in context.find_nodes(ast.ClassDef):
        for item in node.body:
            name = None
            line = None

            if isinstance(item, ast.FunctionDef):
                name = item.name
                line = item.lineno
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        line = item.lineno

            if name and not (name.startswith("__") and name.endswith("__")):
                if name.startswith("__"):
                    vis = "private"
                    is_mangled = True
                elif name.startswith("_"):
                    vis = "protected"
                    is_mangled = False
                else:
                    vis = "public"
                    is_mangled = False

                visibility_data = {
                    "line": line,
                    "name": name,
                    "visibility": vis,
                    "is_name_mangled": is_mangled,
                    "in_class": node.name,
                }
                visibility.append(visibility_data)

    return visibility
