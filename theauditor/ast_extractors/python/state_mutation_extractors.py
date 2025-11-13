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
from typing import Any, Dict, List, Optional

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

def _get_str_constant(node: Optional[ast.AST]) -> Optional[str]:
    """Return string value for constant nodes.

    Handles both Python 3.8+ ast.Constant and legacy ast.Str nodes.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):  # Python 3.7 compat (though we require 3.11+)
        return node.s
    return None


# ============================================================================
# State Mutation Extractors
# ============================================================================

def extract_instance_mutations(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(actual_tree, ast.AST):
        return mutations

    # Build function ranges for context detection
    # CRITICAL FIX: Track as list, not dict, to handle multiple functions with same name
    # (e.g., multiple __init__ methods in different classes)
    function_ranges = []  # List of (name, start, end, is_property_setter, is_dunder)
    class_ranges = {}

    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                func_name = node.name
                start_line = node.lineno
                end_line = node.end_lineno or node.lineno

                # Detect property setters: @property.setter or @x.setter
                is_property_setter = any(
                    isinstance(dec, ast.Attribute) and dec.attr == "setter"
                    for dec in node.decorator_list
                )

                # Detect dunder methods (special methods with expected mutations)
                is_dunder = (
                    func_name.startswith("__") and func_name.endswith("__") and
                    func_name in ["__init__", "__setitem__", "__enter__", "__exit__",
                                  "__setattr__", "__delattr__", "__set__"]
                )

                function_ranges.append((func_name, start_line, end_line, is_property_setter, is_dunder))

        elif isinstance(node, ast.ClassDef):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

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

    # Extract mutations with single-pass AST walk
    for node in ast.walk(actual_tree):
        # Pattern 1: self.x = value (ast.Assign with ast.Attribute target)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    # Check if target is self.x or self.nested.x
                    attr_chain = get_attribute_chain(target)
                    if attr_chain and attr_chain.startswith("self."):
                        in_function, is_prop_setter, is_dunder = find_containing_function(node.lineno)
                        mutations.append({
                            'line': node.lineno,
                            'target': attr_chain,
                            'operation': 'assignment',
                            'in_function': in_function,
                            'is_init': (in_function == "__init__"),
                            'is_property_setter': is_prop_setter,
                            'is_dunder_method': is_dunder,
                        })

        # Pattern 2: self.x += 1 (ast.AugAssign with ast.Attribute target)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Attribute):
                attr_chain = get_attribute_chain(node.target)
                if attr_chain and attr_chain.startswith("self."):
                    in_function, is_prop_setter, is_dunder = find_containing_function(node.lineno)
                    mutations.append({
                        'line': node.lineno,
                        'target': attr_chain,
                        'operation': 'augmented_assignment',
                        'in_function': in_function,
                        'is_init': (in_function == "__init__"),
                        'is_property_setter': is_prop_setter,
                        'is_dunder_method': is_dunder,
                    })

        # Pattern 3: self.items.append(x) (method call mutation)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                # Check if func.value is self.something
                if isinstance(node.func.value, ast.Attribute):
                    attr_chain = get_attribute_chain(node.func.value)
                    if attr_chain and attr_chain.startswith("self."):
                        # Mutation methods: append, extend, update, add, remove, pop, clear, etc.
                        mutation_methods = {
                            'append', 'extend', 'insert', 'remove', 'pop', 'clear',
                            'update', 'add', 'discard', 'sort', 'reverse'
                        }
                        if node.func.attr in mutation_methods:
                            in_function, is_prop_setter, is_dunder = find_containing_function(node.lineno)
                            mutations.append({
                                'line': node.lineno,
                                'target': attr_chain,
                                'operation': 'method_call',
                                'in_function': in_function,
                                'is_init': (in_function == "__init__"),
                                'is_property_setter': is_prop_setter,
                                'is_dunder_method': is_dunder,
                            })
                # Also check direct self.method() calls (e.g., self.clear())
                elif isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                    # This catches self.method_name() patterns
                    # We record the method being called on self, not a mutation
                    # Skip this pattern - it's not a state mutation
                    pass

    # CRITICAL: Deduplicate by (line, target, in_function) - core_extractors.py:452-468 pattern
    seen = set()
    deduped = []
    for m in mutations:
        key = (m['line'], m['target'], m['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(mutations) != len(deduped):
            print(f"[AST_DEBUG] Instance mutations deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_class_mutations(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(actual_tree, ast.AST):
        return mutations

    # Build class name registry and function ranges for context
    class_names = set()
    function_ranges = []  # List of (name, start, end, is_classmethod)

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.ClassDef):
            class_names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                func_name = node.name
                start_line = node.lineno
                end_line = node.end_lineno or node.lineno

                # Detect @classmethod decorator
                is_classmethod = any(
                    (isinstance(dec, ast.Name) and dec.id == "classmethod") or
                    (isinstance(dec, ast.Attribute) and dec.attr == "classmethod")
                    for dec in node.decorator_list
                )

                function_ranges.append((func_name, start_line, end_line, is_classmethod))

    def find_containing_function(line_no):
        """Find the function containing this line.

        Returns tuple: (function_name, is_classmethod)
        """
        for fname, start, end, is_cm in function_ranges:
            if start <= line_no <= end:
                return fname, is_cm
        return "global", False

    # Extract class mutations with single-pass AST walk
    for node in ast.walk(actual_tree):
        # Pattern 1: ClassName.attr = value (ast.Assign with ast.Attribute target)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    # Check if target is ClassName.attr or cls.attr
                    if isinstance(target.value, ast.Name):
                        class_or_cls = target.value.id

                        # Match if it's 'cls' or a known class name
                        if class_or_cls == 'cls' or class_or_cls in class_names:
                            in_function, is_cm = find_containing_function(node.lineno)
                            mutations.append({
                                'line': node.lineno,
                                'class_name': class_or_cls,
                                'attribute': target.attr,
                                'operation': 'assignment',
                                'in_function': in_function,
                                'is_classmethod': is_cm,
                            })

        # Pattern 2: ClassName.attr += 1 (ast.AugAssign with ast.Attribute target)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Attribute):
                if isinstance(node.target.value, ast.Name):
                    class_or_cls = node.target.value.id

                    # Match if it's 'cls' or a known class name
                    if class_or_cls == 'cls' or class_or_cls in class_names:
                        in_function, is_cm = find_containing_function(node.lineno)
                        mutations.append({
                            'line': node.lineno,
                            'class_name': class_or_cls,
                            'attribute': node.target.attr,
                            'operation': 'augmented_assignment',
                            'in_function': in_function,
                            'is_classmethod': is_cm,
                        })

    # CRITICAL: Deduplicate by (line, class_name, attribute) - core_extractors.py:452-468 pattern
    seen = set()
    deduped = []
    for m in mutations:
        key = (m['line'], m['class_name'], m['attribute'])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(mutations) != len(deduped):
            print(f"[AST_DEBUG] Class mutations deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_global_mutations(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(actual_tree, ast.AST):
        return mutations

    # Build function ranges and track global declarations
    function_ranges = []  # List of (name, start, end)
    globals_by_function = {}  # {function_name: set(global_var_names)}

    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                func_name = node.name
                start_line = node.lineno
                end_line = node.end_lineno or node.lineno
                function_ranges.append((func_name, start_line, end_line))

                # Track global declarations within this function
                global_vars = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Global):
                        global_vars.update(child.names)

                if global_vars:
                    globals_by_function[func_name] = global_vars

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    # Extract global mutations
    for node in ast.walk(actual_tree):
        # Pattern 1: global x; x = value (ast.Assign)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id
                    in_function = find_containing_function(node.lineno)

                    # Check if this variable was declared global in this function
                    if in_function != "global" and in_function in globals_by_function:
                        if var_name in globals_by_function[in_function]:
                            mutations.append({
                                'line': node.lineno,
                                'global_name': var_name,
                                'operation': 'assignment',
                                'in_function': in_function,
                            })
                # Pattern 2: global dict; dict['key'] = value (subscript assignment)
                elif isinstance(target, ast.Subscript):
                    if isinstance(target.value, ast.Name):
                        var_name = target.value.id
                        in_function = find_containing_function(node.lineno)

                        if in_function != "global" and in_function in globals_by_function:
                            if var_name in globals_by_function[in_function]:
                                mutations.append({
                                    'line': node.lineno,
                                    'global_name': var_name,
                                    'operation': 'item_assignment',
                                    'in_function': in_function,
                                })
                # Pattern 3: global obj; obj.attr = value (attribute assignment)
                elif isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name):
                        var_name = target.value.id
                        in_function = find_containing_function(node.lineno)

                        if in_function != "global" and in_function in globals_by_function:
                            if var_name in globals_by_function[in_function]:
                                mutations.append({
                                    'line': node.lineno,
                                    'global_name': var_name,
                                    'operation': 'attr_assignment',
                                    'in_function': in_function,
                                })

        # Pattern 4: global x; x += 1 (ast.AugAssign)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                var_name = node.target.id
                in_function = find_containing_function(node.lineno)

                if in_function != "global" and in_function in globals_by_function:
                    if var_name in globals_by_function[in_function]:
                        mutations.append({
                            'line': node.lineno,
                            'global_name': var_name,
                            'operation': 'augmented_assignment',
                            'in_function': in_function,
                        })

    # CRITICAL: Deduplicate by (line, global_name) - core_extractors.py:452-468 pattern
    seen = set()
    deduped = []
    for m in mutations:
        key = (m['line'], m['global_name'])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(mutations) != len(deduped):
            print(f"[AST_DEBUG] Global mutations deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_argument_mutations(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(actual_tree, ast.AST):
        return mutations

    # Build map of function parameters
    function_params = {}  # {function_name: set(parameter_names)}

    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            param_names = set()

            # Extract all parameter names (args, kwargs, etc.)
            if hasattr(node, 'args') and node.args:
                args_obj = node.args
                # Regular args
                for arg in args_obj.args:
                    param_names.add(arg.arg)
                # *args
                if args_obj.vararg:
                    param_names.add(args_obj.vararg.arg)
                # **kwargs
                if args_obj.kwarg:
                    param_names.add(args_obj.kwarg.arg)
                # kwonly args
                for arg in args_obj.kwonlyargs:
                    param_names.add(arg.arg)

            # CRITICAL: Remove 'self' and 'cls' - they're handled by instance/class mutation extractors
            param_names.discard('self')
            param_names.discard('cls')

            if param_names:
                function_params[func_name] = param_names

    # Build function ranges for context detection
    function_ranges = []  # List of (name, start, end)
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    # Mutation method names (methods that modify the object in place)
    MUTATION_METHODS = {
        'append', 'extend', 'insert', 'remove', 'pop', 'clear',  # list
        'update', 'add', 'discard',  # set/dict
        'sort', 'reverse',  # list
        'setdefault', 'popitem',  # dict
    }

    # Extract argument mutations
    for node in ast.walk(actual_tree):
        in_function = find_containing_function(node.lineno) if hasattr(node, 'lineno') else "global"

        # Skip if not in a function or function has no params
        if in_function == "global" or in_function not in function_params:
            continue

        param_names = function_params[in_function]

        # Pattern 1: param.method() (method call mutation)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                # Check if calling method on a parameter (e.g., lst.append(x))
                if isinstance(node.func.value, ast.Name):
                    var_name = node.func.value.id
                    method_name = node.func.attr

                    if var_name in param_names and method_name in MUTATION_METHODS:
                        mutations.append({
                            'line': node.lineno,
                            'parameter_name': var_name,
                            'mutation_type': 'method_call',
                            'mutation_detail': method_name,
                            'in_function': in_function,
                        })

        # Pattern 2: param['key'] = value (subscript assignment)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    if isinstance(target.value, ast.Name):
                        var_name = target.value.id
                        if var_name in param_names:
                            mutations.append({
                                'line': node.lineno,
                                'parameter_name': var_name,
                                'mutation_type': 'item_assignment',
                                'mutation_detail': 'setitem',
                                'in_function': in_function,
                            })
                # Pattern 3: param.attr = value (attribute assignment)
                elif isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name):
                        var_name = target.value.id
                        if var_name in param_names:
                            mutations.append({
                                'line': node.lineno,
                                'parameter_name': var_name,
                                'mutation_type': 'attr_assignment',
                                'mutation_detail': target.attr,
                                'in_function': in_function,
                            })
                # Pattern 4: param = value (direct reassignment - less common but possible)
                elif isinstance(target, ast.Name):
                    var_name = target.id
                    if var_name in param_names:
                        mutations.append({
                            'line': node.lineno,
                            'parameter_name': var_name,
                            'mutation_type': 'assignment',
                            'mutation_detail': 'reassignment',
                            'in_function': in_function,
                        })

        # Pattern 5: param += value (augmented assignment)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                var_name = node.target.id
                if var_name in param_names:
                    mutations.append({
                        'line': node.lineno,
                        'parameter_name': var_name,
                        'mutation_type': 'augmented_assignment',
                        'mutation_detail': node.op.__class__.__name__,
                        'in_function': in_function,
                    })

    # CRITICAL: Deduplicate by (line, parameter_name) - core_extractors.py:452-468 pattern
    seen = set()
    deduped = []
    for m in mutations:
        key = (m['line'], m['parameter_name'])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(mutations) != len(deduped):
            print(f"[AST_DEBUG] Argument mutations deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_augmented_assignments(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(actual_tree, ast.AST):
        return mutations

    # Build context: class names, global variables, function parameters
    class_names = set()
    globals_by_function = {}  # {function_name: set(global_var_names)}
    function_params = {}  # {function_name: set(parameter_names)}
    function_ranges = []  # List of (name, start, end)

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.ClassDef):
            class_names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges.append((func_name, node.lineno, node.end_lineno or node.lineno))

            # Track global declarations
            global_vars = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Global):
                    global_vars.update(child.names)
            if global_vars:
                globals_by_function[func_name] = global_vars

            # Track parameters
            param_names = set()
            if hasattr(node, 'args') and node.args:
                args_obj = node.args
                for arg in args_obj.args:
                    param_names.add(arg.arg)
                if args_obj.vararg:
                    param_names.add(args_obj.vararg.arg)
                if args_obj.kwarg:
                    param_names.add(args_obj.kwarg.arg)
                for arg in args_obj.kwonlyargs:
                    param_names.add(arg.arg)
            # Remove self/cls (they're instance/class, not argument)
            param_names.discard('self')
            param_names.discard('cls')
            if param_names:
                function_params[func_name] = param_names

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    # Map operator AST nodes to string representation
    OP_MAP = {
        ast.Add: '+=',
        ast.Sub: '-=',
        ast.Mult: '*=',
        ast.Div: '/=',
        ast.FloorDiv: '//=',
        ast.Mod: '%=',
        ast.Pow: '**=',
        ast.LShift: '<<=',
        ast.RShift: '>>=',
        ast.BitOr: '|=',
        ast.BitXor: '^=',
        ast.BitAnd: '&=',
    }

    # Extract all augmented assignments
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.AugAssign):
            in_function = find_containing_function(node.lineno)
            operator = OP_MAP.get(type(node.op), '?=')

            # Determine target and target_type
            target_expr = None
            target_type = 'unknown'

            if isinstance(node.target, ast.Name):
                # Simple name: x += 1
                var_name = node.target.id
                target_expr = var_name

                # Classify target type
                if in_function != "global":
                    # Check if it's a parameter
                    if in_function in function_params and var_name in function_params[in_function]:
                        target_type = 'argument'
                    # Check if it's a declared global
                    elif in_function in globals_by_function and var_name in globals_by_function[in_function]:
                        target_type = 'global'
                    else:
                        target_type = 'local'
                else:
                    target_type = 'global'  # Module-level

            elif isinstance(node.target, ast.Attribute):
                # Attribute: self.x += 1 or cls.x += 1 or Counter.instances += 1
                if isinstance(node.target.value, ast.Name):
                    base_name = node.target.value.id
                    attr_name = node.target.attr
                    target_expr = f"{base_name}.{attr_name}"

                    if base_name == 'self':
                        target_type = 'instance'
                    elif base_name == 'cls' or base_name in class_names:
                        target_type = 'class'
                    else:
                        target_type = 'attribute'
                else:
                    # Complex attribute chain (rare)
                    target_type = 'attribute'
                    target_expr = 'complex_attribute'

            elif isinstance(node.target, ast.Subscript):
                # Subscript: lst[0] += 1 or dict['key'] += 1
                if isinstance(node.target.value, ast.Name):
                    var_name = node.target.value.id
                    target_expr = f"{var_name}[...]"
                    target_type = 'subscript'
                else:
                    target_expr = 'subscript'
                    target_type = 'subscript'

            if target_expr:
                mutations.append({
                    'line': node.lineno,
                    'target': target_expr,
                    'operator': operator,
                    'target_type': target_type,
                    'in_function': in_function,
                })

    # CRITICAL: Deduplicate by (line, target) - core_extractors.py:452-468 pattern
    seen = set()
    deduped = []
    for m in mutations:
        key = (m['line'], m['target'])
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(mutations) != len(deduped):
            print(f"[AST_DEBUG] Augmented assignments deduplication: {len(mutations)} -> {len(deduped)} ({len(mutations) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped
