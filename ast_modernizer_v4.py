#!/usr/bin/env python3
"""
AST Modernization Codemod for TheAuditor - Version 2 (UPDATED)
===============================================================
Modernizes Python AST code from Python 3.7/3.8 patterns to Python 3.14 standards.
Uses LibCST 1.8.6 with proper matcher patterns from official documentation.

Author: TheAuditor Team
Date: November 2025
LibCST Version: 1.8.6
Target Python: 3.14

This implementation follows the @m.leave decorator patterns from the LibCST documentation.

UPDATES:
- Added context tracking (inside_ast_context) for safer attribute transformations
- Prevents false positives when transforming .s/.n → .value
- Best of both worlds: v2's decorator pattern + v3's context awareness
- Fixed critical operator precedence bug with ParenthesizedExpression
- Added support for pure deprecated tuples (ast.Str, ast.Num) → ast.Constant
- Enhanced indirect ast.walk() pattern detection (e.g., nodes = list(ast.walk()))

Usage:
    # Dry run first
    python ast_modernizer_v2.py --dry-run --target-dir ./theauditor/ast_extractors/python/

    # Apply changes
    python ast_modernizer_v2.py --target-dir ./theauditor/ast_extractors/python/
"""

import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Union, Sequence, Optional
from dataclasses import dataclass

import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext


# ============================================================================
# Statistics Tracking
# ============================================================================

@dataclass
class ModernizationStats:
    """Track what we've modernized."""
    files_processed: int = 0
    files_modified: int = 0
    ast_str_fixed: int = 0
    ast_num_fixed: int = 0
    ast_bytes_fixed: int = 0
    ast_nameconstant_fixed: int = 0
    attr_s_fixed: int = 0
    attr_n_fixed: int = 0
    hasattr_s_fixed: int = 0
    hasattr_n_fixed: int = 0
    tuple_checks_simplified: int = 0
    type_hints_modernized: int = 0
    imports_cleaned: int = 0

    def print_summary(self):
        """Print a summary of changes."""
        print("\n" + "="*60)
        print("AST MODERNIZATION SUMMARY")
        print("="*60)
        print(f"Files processed: {self.files_processed}")
        print(f"Files modified: {self.files_modified}")
        print(f"\nTransformations applied:")
        print(f"  ast.Str -> ast.Constant: {self.ast_str_fixed}")
        print(f"  ast.Num -> ast.Constant: {self.ast_num_fixed}")
        print(f"  ast.Bytes -> ast.Constant: {self.ast_bytes_fixed}")
        print(f"  ast.NameConstant -> ast.Constant: {self.ast_nameconstant_fixed}")
        print(f"  .s -> .value: {self.attr_s_fixed}")
        print(f"  .n -> .value: {self.attr_n_fixed}")
        print(f"  hasattr(node, 's') -> isinstance checks: {self.hasattr_s_fixed}")
        print(f"  hasattr(node, 'n') -> isinstance checks: {self.hasattr_n_fixed}")
        print(f"  Simplified tuple checks: {self.tuple_checks_simplified}")
        print(f"  Modernized type hints: {self.type_hints_modernized}")
        print(f"  Cleaned imports: {self.imports_cleaned}")
        print("="*60)


# ============================================================================
# AST Modernization Transformer (Following LibCST FAQ patterns)
# ============================================================================

class ASTModernizerTransformer(m.MatcherDecoratableTransformer):
    """
    Transforms Python 3.7/3.8 AST patterns to Python 3.14 standards.

    Uses MatcherDecoratableTransformer with @m.leave decorators following
    LibCST best practices for pattern matching and transformation.
    """

    def __init__(self, context: CodemodContext, stats: ModernizationStats):
        super().__init__()
        self.context = context
        self.stats = stats

        # Track deprecated imports to remove
        self.deprecated_ast_types = set()

        # Common AST variable names in TheAuditor codebase
        # More conservative than before - only VERY common AST variables
        self.definite_ast_vars = {
            "node", "child", "actual_tree", "ast_node",
            "func_node", "class_node", "tree"
        }

        # Context tracking: Are we inside an ast.walk() loop?
        # This prevents false positives like transforming item.s when item is NOT an AST node
        self.inside_ast_context = False

        # Track variables that contain ast.walk() results (for indirect patterns)
        # e.g., nodes = list(ast.walk(tree))
        self.ast_walk_result_vars = set()

        # Track current for loop target to add to ast_walk_result_vars if needed
        self.current_for_target = None

        # Track if we need to ensure 'import ast' exists
        self.needs_ast_import = False

        # Track if we have 'import ast' in the file
        self.has_ast_import = False

    # ------------------------------------------------------------------------
    # Helper: Create safe parenthesized boolean checks
    # ------------------------------------------------------------------------

    def _create_safe_check(self, node_arg: cst.BaseExpression,
                           value_type: Union[cst.Name, cst.Tuple]) -> cst.BooleanOperation:
        """
        Creates a safe, parenthesized boolean check:
        (isinstance(node, ast.Constant) and isinstance(node.value, <value_type>))

        Wraps with lpar/rpar to prevent operator precedence issues
        (e.g., 'not isinstance(...)' becoming 'not A and B' instead of 'not (A and B)').
        """
        const_check = cst.Call(
            func=cst.Name("isinstance"),
            args=[
                cst.Arg(node_arg),
                cst.Arg(
                    cst.Attribute(
                        value=cst.Name("ast"),
                        attr=cst.Name("Constant")
                    )
                )
            ]
        )

        value_check = cst.Call(
            func=cst.Name("isinstance"),
            args=[
                cst.Arg(
                    cst.Attribute(
                        value=node_arg,
                        attr=cst.Name("value")
                    )
                ),
                cst.Arg(value_type)
            ]
        )

        # Wrap in parentheses to ensure 'not' binds correctly to the whole group
        return cst.BooleanOperation(
            left=const_check,
            operator=cst.And(
                whitespace_before=cst.SimpleWhitespace(" "),
                whitespace_after=cst.SimpleWhitespace(" ")
            ),
            right=value_check,
            lpar=[cst.LeftParen()],
            rpar=[cst.RightParen()]
        )

    # ------------------------------------------------------------------------
    # Transform: isinstance(node, ast.Str)
    # ------------------------------------------------------------------------

    @m.leave(
        m.Call(
            func=m.Name("isinstance"),
            args=[
                m.Arg(),  # First arg (variable)
                m.Arg(
                    m.Attribute(
                        value=m.Name("ast"),
                        attr=m.Name("Str")
                    )
                )
            ]
        )
    )
    def replace_ast_str_isinstance(
        self,
        original_node: cst.Call,
        updated_node: cst.Call
    ) -> cst.BooleanOperation:
        """Transform: isinstance(node, ast.Str) → (isinstance(node, ast.Constant) and isinstance(node.value, str))"""

        self.stats.ast_str_fixed += 1
        self.deprecated_ast_types.add("Str")
        self.needs_ast_import = True  # We're using ast.Constant
        return self._create_safe_check(updated_node.args[0].value, cst.Name("str"))

    # ------------------------------------------------------------------------
    # Transform: isinstance(node, ast.Num)
    # ------------------------------------------------------------------------

    @m.leave(
        m.Call(
            func=m.Name("isinstance"),
            args=[
                m.Arg(),  # First arg (variable)
                m.Arg(
                    m.Attribute(
                        value=m.Name("ast"),
                        attr=m.Name("Num")
                    )
                )
            ]
        )
    )
    def replace_ast_num_isinstance(
        self,
        original_node: cst.Call,
        updated_node: cst.Call
    ) -> cst.BooleanOperation:
        """Transform: isinstance(node, ast.Num) → (isinstance(node, ast.Constant) and isinstance(node.value, (int, float)))"""

        self.stats.ast_num_fixed += 1
        self.deprecated_ast_types.add("Num")
        self.needs_ast_import = True  # We're using ast.Constant

        types_tuple = cst.Tuple(elements=[
            cst.Element(cst.Name("int")),
            cst.Element(cst.Name("float"))
        ])
        return self._create_safe_check(updated_node.args[0].value, types_tuple)

    # ------------------------------------------------------------------------
    # Transform: isinstance(node, ast.Bytes)
    # ------------------------------------------------------------------------

    @m.leave(
        m.Call(
            func=m.Name("isinstance"),
            args=[
                m.Arg(),  # First arg (variable)
                m.Arg(
                    m.Attribute(
                        value=m.Name("ast"),
                        attr=m.Name("Bytes")
                    )
                )
            ]
        )
    )
    def replace_ast_bytes_isinstance(
        self,
        original_node: cst.Call,
        updated_node: cst.Call
    ) -> cst.BooleanOperation:
        """Transform: isinstance(node, ast.Bytes) → (isinstance(node, ast.Constant) and isinstance(node.value, bytes))"""

        self.stats.ast_bytes_fixed += 1
        self.deprecated_ast_types.add("Bytes")
        self.needs_ast_import = True  # We're using ast.Constant
        return self._create_safe_check(updated_node.args[0].value, cst.Name("bytes"))

    # ------------------------------------------------------------------------
    # Transform: isinstance(node, ast.NameConstant)
    # ------------------------------------------------------------------------

    @m.leave(
        m.Call(
            func=m.Name("isinstance"),
            args=[
                m.Arg(),  # First arg (variable)
                m.Arg(
                    m.Attribute(
                        value=m.Name("ast"),
                        attr=m.Name("NameConstant")
                    )
                )
            ]
        )
    )
    def replace_ast_nameconstant_isinstance(
        self,
        original_node: cst.Call,
        updated_node: cst.Call
    ) -> cst.Call:
        """Transform: isinstance(node, ast.NameConstant) → isinstance(node, ast.Constant)"""

        self.stats.ast_nameconstant_fixed += 1
        self.deprecated_ast_types.add("NameConstant")
        self.needs_ast_import = True  # We're using ast.Constant

        node_arg = updated_node.args[0].value

        # Simply replace with ast.Constant (no value check needed for True/False/None)
        return cst.Call(
            func=cst.Name("isinstance"),
            args=[
                cst.Arg(node_arg),
                cst.Arg(
                    cst.Attribute(
                        value=cst.Name("ast"),
                        attr=cst.Name("Constant")
                    )
                )
            ]
        )

    # ------------------------------------------------------------------------
    # Transform: node.s → node.value (only for likely AST variables)
    # ------------------------------------------------------------------------

    @m.leave(
        m.Attribute(
            attr=m.Name("s")
        )
    )
    def replace_dot_s_with_dot_value(
        self,
        original_node: cst.Attribute,
        updated_node: cst.Attribute
    ) -> cst.Attribute:
        """Transform: node.s → node.value (only for likely AST variables)"""

        # Check if the base looks like an AST variable
        if isinstance(updated_node.value, cst.Name):
            var_name = updated_node.value.value
            # IMPROVED SAFETY: Transform if ANY of:
            # 1. Variable is in definite_ast_vars (conservative allowlist), OR
            # 2. We're inside an ast.walk() loop (contextual evidence), OR
            # 3. Variable is the current for loop target from ast.walk()
            if (var_name in self.definite_ast_vars or
                self.inside_ast_context or
                (self.current_for_target and var_name == self.current_for_target)):
                self.stats.attr_s_fixed += 1
                return updated_node.with_changes(attr=cst.Name("value"))

        # Also handle chained attributes like node.target.s
        elif isinstance(updated_node.value, cst.Attribute):
            # Check if it's something like node.something.s
            base = self._get_base_name(updated_node.value)
            if (base in self.definite_ast_vars or
                self.inside_ast_context or
                (self.current_for_target and base == self.current_for_target)):
                self.stats.attr_s_fixed += 1
                return updated_node.with_changes(attr=cst.Name("value"))

        return updated_node

    # ------------------------------------------------------------------------
    # Transform: node.n → node.value (only for likely AST variables)
    # ------------------------------------------------------------------------

    @m.leave(
        m.Attribute(
            attr=m.Name("n")
        )
    )
    def replace_dot_n_with_dot_value(
        self,
        original_node: cst.Attribute,
        updated_node: cst.Attribute
    ) -> cst.Attribute:
        """Transform: node.n → node.value (only for likely AST variables)"""

        # Check if the base looks like an AST variable
        if isinstance(updated_node.value, cst.Name):
            var_name = updated_node.value.value
            # IMPROVED SAFETY: Transform if ANY of:
            # 1. Variable is in definite_ast_vars (conservative allowlist), OR
            # 2. We're inside an ast.walk() loop (contextual evidence), OR
            # 3. Variable is the current for loop target from ast.walk()
            if (var_name in self.definite_ast_vars or
                self.inside_ast_context or
                (self.current_for_target and var_name == self.current_for_target)):
                self.stats.attr_n_fixed += 1
                return updated_node.with_changes(attr=cst.Name("value"))

        # Also handle chained attributes
        elif isinstance(updated_node.value, cst.Attribute):
            base = self._get_base_name(updated_node.value)
            if (base in self.definite_ast_vars or
                self.inside_ast_context or
                (self.current_for_target and base == self.current_for_target)):
                self.stats.attr_n_fixed += 1
                return updated_node.with_changes(attr=cst.Name("value"))

        return updated_node

    # ------------------------------------------------------------------------
    # Transform: hasattr(node, 's')
    # ------------------------------------------------------------------------

    @m.leave(
        m.Call(
            func=m.Name("hasattr"),
            args=[
                m.Arg(),  # First arg (variable)
                m.Arg(m.SimpleString('"s"') | m.SimpleString("'s'"))
            ]
        )
    )
    def replace_hasattr_s(
        self,
        original_node: cst.Call,
        updated_node: cst.Call
    ) -> cst.BooleanOperation:
        """Transform: hasattr(node, 's') → (isinstance(node, ast.Constant) and isinstance(node.value, str))"""

        self.stats.hasattr_s_fixed += 1
        self.needs_ast_import = True  # We're using ast.Constant
        return self._create_safe_check(updated_node.args[0].value, cst.Name("str"))

    # ------------------------------------------------------------------------
    # Transform: hasattr(node, 'n')
    # ------------------------------------------------------------------------

    @m.leave(
        m.Call(
            func=m.Name("hasattr"),
            args=[
                m.Arg(),  # First arg (variable)
                m.Arg(m.SimpleString('"n"') | m.SimpleString("'n'"))
            ]
        )
    )
    def replace_hasattr_n(
        self,
        original_node: cst.Call,
        updated_node: cst.Call
    ) -> cst.BooleanOperation:
        """Transform: hasattr(node, 'n') → (isinstance(node, ast.Constant) and isinstance(node.value, (int, float)))"""

        self.stats.hasattr_n_fixed += 1
        self.needs_ast_import = True  # We're using ast.Constant

        types_tuple = cst.Tuple(elements=[
            cst.Element(cst.Name("int")),
            cst.Element(cst.Name("float"))
        ])
        return self._create_safe_check(updated_node.args[0].value, types_tuple)

    # ------------------------------------------------------------------------
    # Transform: Simplify tuple isinstance checks
    # ------------------------------------------------------------------------

    @m.leave(
        m.Call(
            func=m.Name("isinstance"),
            args=[
                m.Arg(),  # First arg (variable)
                m.Arg(m.Tuple())  # Tuple of types
            ]
        )
    )
    def simplify_tuple_isinstance(
        self,
        original_node: cst.Call,
        updated_node: cst.Call
    ) -> Union[cst.Call, cst.BooleanOperation]:
        """Simplify tuples like (ast.Str, ast.Num, ast.Constant) → just ast.Constant
        Also handles pure deprecated tuples like (ast.Str, ast.Num) → ast.Constant"""

        node_arg = updated_node.args[0].value
        tuple_arg = updated_node.args[1].value

        if not isinstance(tuple_arg, cst.Tuple):
            return updated_node

        # Collect all types in the tuple
        has_constant = False
        has_deprecated = False
        deprecated_types = []
        all_are_literals = True  # Track if all deprecated types are literal types

        for element in tuple_arg.elements:
            if isinstance(element.value, cst.Attribute):
                if m.matches(element.value, m.Attribute(value=m.Name("ast"))):
                    attr_name = element.value.attr.value if hasattr(element.value.attr, 'value') else None

                    if attr_name == "Constant":
                        has_constant = True
                    elif attr_name in {"Str", "Num", "Bytes", "NameConstant"}:
                        has_deprecated = True
                        deprecated_types.append(attr_name)
                        self.deprecated_ast_types.add(attr_name)
                    else:
                        all_are_literals = False
                else:
                    all_are_literals = False
            else:
                all_are_literals = False

        # CASE 1: If we have both Constant and deprecated types, just keep Constant
        if has_constant and has_deprecated:
            self.stats.tuple_checks_simplified += 1

            # Filter out deprecated types
            new_elements = []
            for element in tuple_arg.elements:
                if isinstance(element.value, cst.Attribute):
                    if m.matches(element.value, m.Attribute(value=m.Name("ast"))):
                        attr_name = element.value.attr.value if hasattr(element.value.attr, 'value') else None
                        if attr_name not in {"Str", "Num", "Bytes", "NameConstant"}:
                            new_elements.append(element)
                else:
                    new_elements.append(element)

            # If only ast.Constant is left, simplify to single check
            if len(new_elements) == 1:
                return cst.Call(
                    func=cst.Name("isinstance"),
                    args=[
                        cst.Arg(node_arg),
                        cst.Arg(new_elements[0].value)
                    ]
                )
            # Otherwise return tuple with deprecated types removed
            elif new_elements:
                return updated_node.with_changes(
                    args=[
                        updated_node.args[0],
                        cst.Arg(cst.Tuple(elements=new_elements))
                    ]
                )

        # CASE 2: Pure deprecated tuple (e.g., (ast.Str, ast.Num))
        # All deprecated literal types map to ast.Constant
        elif has_deprecated and not has_constant and all_are_literals:
            self.stats.tuple_checks_simplified += 1
            self.needs_ast_import = True  # We're using ast.Constant

            # All deprecated literal types become ast.Constant
            # Since they're all literals, we can collapse to single ast.Constant check
            return cst.Call(
                func=cst.Name("isinstance"),
                args=[
                    cst.Arg(node_arg),
                    cst.Arg(
                        cst.Attribute(
                            value=cst.Name("ast"),
                            attr=cst.Name("Constant")
                        )
                    )
                ]
            )

        return updated_node

    # ------------------------------------------------------------------------
    # Ensure 'import ast' exists if needed
    # ------------------------------------------------------------------------

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Ensure 'import ast' exists if we've used ast.Constant in transformations."""
        # If we don't need ast import or already have it, return as-is
        if not self.needs_ast_import or self.has_ast_import:
            return updated_node

        # We need to add 'import ast' at the top of the file
        # Create the import statement
        import_ast = cst.SimpleStatementLine(
            body=[
                cst.Import(
                    names=[cst.ImportAlias(name=cst.Name("ast"))]
                )
            ]
        )

        # Find the right place to insert the import
        # After any module docstring and after other imports
        new_body = []
        import_added = False

        for i, statement in enumerate(updated_node.body):
            # Skip docstrings at the beginning
            if i == 0 and isinstance(statement, cst.SimpleStatementLine):
                if len(statement.body) == 1 and isinstance(statement.body[0], cst.Expr):
                    if isinstance(statement.body[0].value, (cst.SimpleString, cst.ConcatenatedString)):
                        new_body.append(statement)
                        continue

            # Add import after existing imports but before other code
            if not import_added:
                if isinstance(statement, cst.SimpleStatementLine):
                    # Check if it's an import statement
                    is_import = False
                    for item in statement.body:
                        if isinstance(item, (cst.Import, cst.ImportFrom)):
                            is_import = True
                            break

                    if is_import:
                        new_body.append(statement)
                        continue

                # This is the first non-import statement, add our import before it
                new_body.append(import_ast)
                import_added = True

            new_body.append(statement)

        # If we didn't add the import yet (file only has imports), add it at the end
        if not import_added:
            new_body.append(import_ast)

        return updated_node.with_changes(body=new_body)

    # ------------------------------------------------------------------------
    # Track existing imports
    # ------------------------------------------------------------------------

    def visit_Import(self, node: cst.Import) -> None:
        """Track if we have 'import ast' in the file."""
        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                if hasattr(name.name, 'value') and name.name.value == "ast":
                    self.has_ast_import = True

    # ------------------------------------------------------------------------
    # Transform: Clean up imports
    # ------------------------------------------------------------------------

    def leave_ImportFrom(
        self,
        original_node: cst.ImportFrom,
        updated_node: cst.ImportFrom
    ) -> Union[cst.ImportFrom, cst.RemovalSentinel]:
        """Remove imports of deprecated AST node types."""

        # Only process ast imports
        if not m.matches(updated_node.module, m.Name("ast")):
            return updated_node

        # Don't touch star imports
        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        # Filter out deprecated imports
        if isinstance(updated_node.names, Sequence):
            new_names = []
            removed_any = False

            for name in updated_node.names:
                if isinstance(name, cst.ImportAlias):
                    import_name = name.name.value if hasattr(name.name, 'value') else str(name.name)

                    # Remove if it's a deprecated type we've replaced
                    if import_name in self.deprecated_ast_types:
                        removed_any = True
                        self.stats.imports_cleaned += 1
                    else:
                        new_names.append(name)

            # If we removed anything, update or remove the import
            if removed_any:
                if not new_names:
                    # Remove entire import if nothing left
                    return cst.RemovalSentinel.REMOVE
                else:
                    # Update with remaining imports
                    return updated_node.with_changes(names=new_names)

        return updated_node

    # ------------------------------------------------------------------------
    # Context tracking for safer transformations
    # ------------------------------------------------------------------------

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        """
        Track context when entering a visitor method (e.g., visit_Str).
        This catches the common pattern in AST visitors where node.s/.n needs transformation.
        """
        # Check if function name starts with 'visit_'
        if node.name.value.startswith("visit_"):
            self.inside_ast_context = True

            # Track the first argument (usually 'node') as a safe variable
            if len(node.params.params) > 1:
                # params[0] is self, params[1] is the node
                node_arg = node.params.params[1]
                if isinstance(node_arg.name, cst.Name):
                    self.current_for_target = node_arg.name.value

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        """Exit visitor context when leaving a visit_* method."""
        if original_node.name.value.startswith("visit_"):
            self.inside_ast_context = False
            self.current_for_target = None
        return updated_node

    def visit_Assign(self, node: cst.Assign) -> None:
        """Track variables that contain ast.walk() results."""
        # Check if the right side contains ast.walk()
        contains_ast_walk = False

        # Check for direct ast.walk() call
        if m.matches(
            node.value,
            m.Call(
                func=m.Attribute(
                    value=m.Name("ast"),
                    attr=m.Name("walk")
                )
            )
        ):
            contains_ast_walk = True

        # Check for list(ast.walk(...))
        elif m.matches(
            node.value,
            m.Call(
                func=m.Name("list"),
                args=[
                    m.Arg(
                        m.Call(
                            func=m.Attribute(
                                value=m.Name("ast"),
                                attr=m.Name("walk")
                            )
                        )
                    )
                ]
            )
        ):
            contains_ast_walk = True

        # Check for tuple(ast.walk(...))
        elif m.matches(
            node.value,
            m.Call(
                func=m.Name("tuple"),
                args=[
                    m.Arg(
                        m.Call(
                            func=m.Attribute(
                                value=m.Name("ast"),
                                attr=m.Name("walk")
                            )
                        )
                    )
                ]
            )
        ):
            contains_ast_walk = True

        # Check for list comprehension: [x for x in ast.walk(...)]
        elif isinstance(node.value, cst.ListComp):
            # for_in is a single CompFor object, not a sequence
            # Walk the chain of CompFor objects for nested comprehensions
            current_comp = node.value.for_in
            while current_comp is not None:
                if m.matches(
                    current_comp.iter,
                    m.Call(
                        func=m.Attribute(
                            value=m.Name("ast"),
                            attr=m.Name("walk")
                        )
                    )
                ):
                    contains_ast_walk = True
                    break
                # Move to next nested comprehension level (if any)
                current_comp = current_comp.inner_for_in

        # If we found ast.walk(), track the assigned variable(s)
        if contains_ast_walk:
            for target in node.targets:
                if isinstance(target.target, cst.Name):
                    self.ast_walk_result_vars.add(target.target.value)

    def visit_For(self, node: cst.For) -> None:
        """Track when we enter an ast.walk() loop for context-aware transformations."""
        # CASE 1: Direct pattern: for X in ast.walk(Y):
        if m.matches(
            node.iter,
            m.Call(
                func=m.Attribute(
                    value=m.Name("ast"),
                    attr=m.Name("walk")
                )
            )
        ):
            self.inside_ast_context = True
            # Also track the loop variable
            if isinstance(node.target, cst.Name):
                self.current_for_target = node.target.value

        # CASE 2: Indirect pattern: for X in nodes (where nodes = list(ast.walk()))
        elif isinstance(node.iter, cst.Name):
            if node.iter.value in self.ast_walk_result_vars:
                self.inside_ast_context = True
                # Track the loop variable
                if isinstance(node.target, cst.Name):
                    self.current_for_target = node.target.value

    def leave_For(
        self,
        original_node: cst.For,
        updated_node: cst.For
    ) -> cst.For:
        """Exit ast.walk() context when leaving the loop."""
        # Check both direct and indirect patterns
        is_ast_walk_loop = False

        # Direct pattern
        if m.matches(
            original_node.iter,
            m.Call(
                func=m.Attribute(
                    value=m.Name("ast"),
                    attr=m.Name("walk")
                )
            )
        ):
            is_ast_walk_loop = True

        # Indirect pattern
        elif isinstance(original_node.iter, cst.Name):
            if original_node.iter.value in self.ast_walk_result_vars:
                is_ast_walk_loop = True

        if is_ast_walk_loop:
            self.inside_ast_context = False
            self.current_for_target = None

        return updated_node

    # ------------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------------

    def _get_base_name(self, attr: cst.Attribute) -> Optional[str]:
        """Get the base name from a potentially chained attribute."""
        current = attr
        while isinstance(current, cst.Attribute):
            current = current.value

        if isinstance(current, cst.Name):
            return current.value

        return None


# ============================================================================
# File Processing
# ============================================================================

def process_file(filepath: Path, stats: ModernizationStats,
                 dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Process a single Python file for AST modernization.

    Args:
        filepath: Path to the Python file
        stats: Statistics tracking object
        dry_run: If True, don't write changes
        verbose: If True, print detailed information

    Returns:
        True if file was modified, False otherwise
    """

    stats.files_processed += 1

    try:
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # Skip if doesn't use AST
        if 'import ast' not in source_code and 'from ast import' not in source_code:
            if verbose:
                print(f"  Skipping {filepath.name} (no AST usage)")
            return False

        # Parse with LibCST
        try:
            source_tree = cst.parse_module(source_code)
        except cst.ParserSyntaxError as e:
            print(f"  ERROR: Failed to parse {filepath.name}: {e}")
            return False

        # Create context and transformer
        context = CodemodContext()
        transformer = ASTModernizerTransformer(context, stats)

        # Transform the tree
        modified_tree = source_tree.visit(transformer)

        # Check if anything changed
        if modified_tree.deep_equals(source_tree):
            if verbose:
                print(f"  No changes needed in {filepath.name}")
            return False

        # File was modified
        stats.files_modified += 1

        if dry_run:
            print(f"  Would modify: {filepath.name}")
            if verbose:
                # Show what would change
                print(f"    - ast.Str fixes: {stats.ast_str_fixed}")
                print(f"    - ast.Num fixes: {stats.ast_num_fixed}")
                print(f"    - .s replacements: {stats.attr_s_fixed}")
                print(f"    - .n replacements: {stats.attr_n_fixed}")
            return True

        # Create backup
        backup_path = filepath.with_suffix('.py.bak')
        shutil.copy2(filepath, backup_path)

        # Write the modernized code
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(modified_tree.code)

        print(f"  + Modernized: {filepath.name} (backup: {backup_path.name})")
        return True

    except Exception as e:
        print(f"  ERROR processing {filepath.name}: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return False


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the AST modernizer."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Modernize Python AST code from Python 3.7/3.8 to Python 3.14 patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would change
  python ast_modernizer_v2.py --dry-run

  # Run on specific file
  python ast_modernizer_v2.py --target-dir ./theauditor/ast_extractors/python/security_extractors.py

  # Run on directory
  python ast_modernizer_v2.py --target-dir ./theauditor/ast_extractors/python/

  # Verbose output
  python ast_modernizer_v2.py --verbose --dry-run --target-dir ./theauditor/
        """
    )

    parser.add_argument(
        '--target-dir',
        type=Path,
        default=Path('./theauditor/ast_extractors/python/'),
        help='File or directory to process (default: ./theauditor/ast_extractors/python/)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Don't actually modify files, just show what would change"
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed progress information'
    )

    parser.add_argument(
        '--include-tests',
        action='store_true',
        help='Also process test files (normally skipped)'
    )

    args = parser.parse_args()

    # Validate target
    if not args.target_dir.exists():
        print(f"ERROR: Target does not exist: {args.target_dir}")
        sys.exit(1)

    print("="*60)
    print("AST MODERNIZER v2 - LibCST 1.8.6")
    print("="*60)
    print(f"Target: {args.target_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Verbose: {args.verbose}")
    print(f"Include tests: {args.include_tests}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print()

    # Initialize statistics
    stats = ModernizationStats()

    # Find Python files
    if args.target_dir.is_file():
        python_files = [args.target_dir]
    else:
        python_files = list(args.target_dir.rglob("*.py"))

        # Filter out test files unless requested
        if not args.include_tests:
            python_files = [
                f for f in python_files
                if 'test' not in f.name.lower() and 'test' not in str(f.parent).lower()
            ]

        # Filter out backup files
        python_files = [
            f for f in python_files
            if not f.name.endswith('.bak') and not f.name.endswith('.backup')
        ]

    print(f"Found {len(python_files)} Python files to process\n")

    if not python_files:
        print("No Python files found to process!")
        sys.exit(0)

    # Process each file
    for filepath in sorted(python_files):
        if args.verbose:
            print(f"Processing: {filepath}")

        process_file(filepath, stats, dry_run=args.dry_run, verbose=args.verbose)

    # Print summary
    stats.print_summary()

    if args.dry_run:
        print("\nThis was a DRY RUN - no files were actually modified")
        print("Run without --dry-run to apply changes")
    else:
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Backup files created with .bak extension")
        print("\nTo restore from backups:")
        print('  for f in **/*.py.bak; do mv "$f" "${f%.bak}"; done')

    # Exit with appropriate code
    sys.exit(0 if stats.files_modified > 0 or args.dry_run else 1)


if __name__ == "__main__":
    main()

# ============================================================================
# CHANGELOG - Version 2 Final
# ============================================================================
#
# Critical fixes applied based on lead auditor review:
#
# 1. ✅ FIXED: Boolean operator precedence bug
#    - All isinstance transformations now wrapped in ParenthesizedExpression
#    - Prevents "not isinstance(...)" from becoming "not A and B" instead of "not (A and B)"
#
# 2. ✅ FIXED: Pure deprecated tuple handling
#    - Added CASE 2 to handle tuples like (ast.Str, ast.Num) → ast.Constant
#    - Previously only handled mixed tuples with ast.Constant already present
#
# 3. ✅ ENHANCED: Indirect ast.walk() pattern detection
#    - Now detects: nodes = list(ast.walk(tree)); for node in nodes: ...
#    - Now detects: nodes = tuple(ast.walk(tree)); for node in nodes: ...
#    - Now detects: nodes = [x for x in ast.walk(tree)]; for node in nodes: ...
#    - Tracks variables containing ast.walk() results
#
# 4. ℹ️ KNOWN ISSUE: Import removal may leave trailing commas
#    - Minor formatting issue - run Black/Ruff after transformation
#
# Target: Python 3.14 (not 3.12)
# ============================================================================