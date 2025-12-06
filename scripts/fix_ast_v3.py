"""
AST Fixer V3: Production-Ready Context-Aware Transformation
============================================================
Combines Lead Auditor's V2 brilliance with LibCST FAQ best practices.

Fixes from V2:
- Import management now uses AddImportsVisitor (FAQ recommended)
- isinstance extraction checks first 3 statements (more robust)
- Better parameter heuristics for multi-param functions
- Fixed backup file extension (string concat, not .with_suffix)
- Added comprehensive error handling and validation

Author: TheAuditor Team (V2 by Lead Auditor, V3 refinements)
Date: November 2025
"""

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor


@dataclass
class FixStats:
    files_processed: int = 0
    files_modified: int = 0
    recursion_bombs_defused: int = 0
    missed_optimizations_fixed: int = 0
    imports_added: int = 0
    errors: int = 0

    def print_summary(self):
        print("\n" + "=" * 60)
        print("V3 FIXER SUMMARY")
        print("=" * 60)
        print(f"Files processed: {self.files_processed}")
        print(f"Files modified: {self.files_modified}")
        print(f"Recursion Bombs Defused (Critical): {self.recursion_bombs_defused}")
        print(f"Missed Optimizations Applied: {self.missed_optimizations_fixed}")
        print(f"AST Imports Added: {self.imports_added}")
        if self.errors > 0:
            print(f"Errors: {self.errors}")
        print("=" * 60)


class ContextAwareTransformer(m.MatcherDecoratableTransformer):
    """
    Context-aware AST transformer that fixes:
    1. Recursion bombs (context.walk_tree in helpers)
    2. Missed optimizations (ast.walk(tree) not converted)

    Uses function stack to track scope and parameter analysis
    to determine correct variable names.
    """

    def __init__(self, context: CodemodContext, stats: FixStats):
        super().__init__()
        self.context = context
        self.stats = stats

        self.function_stack: list[cst.FunctionDef] = []

        self.needs_ast_import = False

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Push function to stack to track nesting level."""
        self.function_stack.append(node)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Pop function from stack."""
        if self.function_stack:
            self.function_stack.pop()
        return updated_node

    def _is_in_extractor_scope(self) -> bool:
        """Check if we are inside an extractor or a helper of an extractor."""
        if not self.function_stack:
            return False

        return any(f.name.value.startswith("extract_") for f in self.function_stack)

    def _get_current_func_params(self) -> list[str]:
        """Get list of parameter names for current function."""
        if not self.function_stack:
            return []
        params = []
        for param in self.function_stack[-1].params.params:
            params.append(param.name.value)
        return params

    def _get_best_node_param(self) -> str | None:
        """
        Get the most likely parameter representing a node/subtree.

        Heuristic priority:
        1. Parameter named 'node', 'current_node', 'ast_node'
        2. Parameter named containing 'node'
        3. First parameter that isn't self/cls/context
        4. None if no suitable parameter found
        """
        params = self._get_current_func_params()

        for p in params:
            if p in ["node", "current_node", "ast_node", "tree_node"]:
                return p

        for p in params:
            if "node" in p.lower() and p not in ["self", "cls", "context"]:
                return p

        for p in params:
            if p not in ["self", "cls", "context"]:
                return p

        return None

    @m.leave(m.Call(func=m.Attribute(value=m.Name("context"), attr=m.Name("walk_tree"))))
    def fix_recursion_bomb(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """
        Fix context.walk_tree() calls in helper functions that should use ast.walk().

        Identifies "recursion bombs" where a helper function walks the entire tree
        instead of its local subtree, causing O(N^k) complexity explosion.
        """

        if not self.function_stack:
            return updated_node

        current_func = self.function_stack[-1]
        func_name = current_func.name.value

        is_nested_helper = len(self.function_stack) > 1
        is_helper_func = not func_name.startswith("extract_")

        target_param = self._get_best_node_param()

        if (is_nested_helper or is_helper_func) and target_param:
            self.stats.recursion_bombs_defused += 1
            self.needs_ast_import = True

            return cst.Call(
                func=cst.Attribute(value=cst.Name("ast"), attr=cst.Name("walk")),
                args=[cst.Arg(cst.Name(target_param))],
            )

        return updated_node

    @m.leave(
        m.For(
            iter=m.Call(func=m.Attribute(value=m.Name("ast"), attr=m.Name("walk")), args=[m.Arg()])
        )
    )
    def optimize_ast_walk(self, original_node: cst.For, updated_node: cst.For) -> cst.For:
        """
        Optimize ast.walk(tree) to context.find_nodes() when walking full tree.

        Only optimizes GLOBAL tree walks, preserves LOCAL subtree walks.
        """

        if not updated_node.iter.args:
            return updated_node

        walk_arg = updated_node.iter.args[0].value

        is_global_tree = False

        if isinstance(walk_arg, cst.Attribute):
            if m.matches(walk_arg, m.Attribute(value=m.Name("context"), attr=m.Name("tree"))):
                is_global_tree = True
        elif isinstance(walk_arg, cst.Name) and walk_arg.value in [
            "tree",
            "actual_tree",
            "ast_tree",
            "source_tree",
        ]:
            is_global_tree = True

        if not is_global_tree:
            return updated_node

        node_type = self._extract_isinstance_node_type(updated_node.body)

        if node_type:
            self.stats.missed_optimizations_fixed += 1
            self.needs_ast_import = True

            new_iter = cst.Call(
                func=cst.Attribute(value=cst.Name("context"), attr=cst.Name("find_nodes")),
                args=[cst.Arg(node_type)],
            )

            new_body = self._remove_isinstance_check(updated_node.body)

            return updated_node.with_changes(iter=new_iter, body=new_body)

        return updated_node

    def _extract_isinstance_node_type(self, body: cst.IndentedBlock) -> cst.BaseExpression | None:
        """
        Extract node type from isinstance check in loop body.

        More robust: checks first 3 statements to handle comments/docstrings.
        """
        if not body.body:
            return None

        for _i, stmt in enumerate(body.body[:3]):
            if m.matches(stmt, m.If(test=m.Call(func=m.Name("isinstance")))):
                isinstance_call = stmt.test
                if len(isinstance_call.args) >= 2:
                    return isinstance_call.args[1].value

        return None

    def _remove_isinstance_check(self, body: cst.IndentedBlock) -> cst.IndentedBlock:
        """
        Unwrap isinstance check from loop body.

        More robust: finds isinstance check in first 3 statements.
        """
        if not body.body:
            return body

        for i, stmt in enumerate(body.body[:3]):
            if m.matches(stmt, m.If(test=m.Call(func=m.Name("isinstance")))):
                if_body = stmt.body.body

                new_body = body.body[:i] + tuple(if_body) + body.body[i + 1 :]
                return body.with_changes(body=new_body)

        return body

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add 'import ast' if needed using AddImportsVisitor (FAQ recommended)."""
        if self.needs_ast_import:
            AddImportsVisitor.add_needed_import(self.context, "ast")
            self.stats.imports_added += 1

        return updated_node


def process_file(
    filepath: Path, stats: FixStats, dry_run: bool = False, verbose: bool = False
) -> bool:
    """
    Process a single Python file.

    Returns:
        True if file was modified, False otherwise
    """
    if verbose:
        print(f"Processing: {filepath.name}")

    stats.files_processed += 1

    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"  ERROR reading {filepath.name}: {e}")
        stats.errors += 1
        return False

    try:
        tree = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        print(f"  ERROR parsing {filepath.name}: {e}")
        stats.errors += 1
        return False

    context = CodemodContext()
    transformer = ContextAwareTransformer(context, stats)

    try:
        modified_tree = tree.visit(transformer)
    except Exception as e:
        print(f"  ERROR transforming {filepath.name}: {e}")
        stats.errors += 1
        return False

    if not modified_tree.deep_equals(tree):
        stats.files_modified += 1

        if dry_run:
            print(f"  [DRY RUN] Would modify {filepath.name}")
            if verbose:
                print(f"    - Recursion bombs: {stats.recursion_bombs_defused}")
                print(f"    - Optimizations: {stats.missed_optimizations_fixed}")
            return True

        backup_path = Path(str(filepath) + ".v2_backup")
        try:
            shutil.copy2(filepath, backup_path)
        except Exception as e:
            print(f"  ERROR creating backup: {e}")
            stats.errors += 1
            return False

        try:
            import_visitor = AddImportsVisitor(context)
            final_tree = modified_tree.visit(import_visitor)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(final_tree.code)

            print(f"  [FIXED] {filepath.name} (backup: {backup_path.name})")
            if verbose:
                print(f"    - Recursion bombs defused: {stats.recursion_bombs_defused}")
                print(f"    - Optimizations applied: {stats.missed_optimizations_fixed}")
            return True

        except Exception as e:
            print(f"  ERROR writing {filepath.name}: {e}")

            shutil.copy2(backup_path, filepath)
            stats.errors += 1
            return False

    if verbose:
        print("  No changes needed")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="V3 Context-Aware AST Fixer (Production Ready)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script fixes two critical AST transformation issues:

1. RECURSION BOMBS (Performance Killer):
   Helper functions calling context.walk_tree() instead of ast.walk(node),
   causing O(N^k) complexity explosion in nested loops.

2. MISSED OPTIMIZATIONS:
   ast.walk(tree) patterns that should be context.find_nodes() for O(1) lookups.

Examples:
  # Dry run first (recommended)
  python fix_ast_v3.py --target-dir theauditor/ast_extractors/python/ --dry-run

  # Apply fixes
  python fix_ast_v3.py --target-dir theauditor/ast_extractors/python/

  # Verbose output
  python fix_ast_v3.py --target-dir theauditor/ast_extractors/python/ --verbose

  # Single file
  python fix_ast_v3.py --target-dir theauditor/ast_extractors/python/performance_extractors.py
        """,
    )

    parser.add_argument(
        "--target-dir", type=Path, required=True, help="Directory or file to process"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be changed without modifying files"
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed progress information")

    args = parser.parse_args()

    if not args.target_dir.exists():
        print(f"ERROR: Target does not exist: {args.target_dir}")
        sys.exit(1)

    print("=" * 60)
    print("AST FIXER V3 - PRODUCTION READY")
    print("=" * 60)
    print(f"Target: {args.target_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Verbose: {args.verbose}")
    print("=" * 60)
    print()

    if args.target_dir.is_file():
        files = [args.target_dir]
    else:
        files = sorted(args.target_dir.rglob("*.py"))

        files = [
            f
            for f in files
            if "test" not in f.name.lower()
            and not f.name.endswith(".bak")
            and not f.name.endswith(".backup")
            and not f.name.endswith("_backup")
            and "utils" not in str(f.parent)
        ]

    if not files:
        print("No Python files found to process!")
        sys.exit(0)

    print(f"Found {len(files)} Python files to process\n")

    stats = FixStats()
    for filepath in files:
        process_file(filepath, stats, dry_run=args.dry_run, verbose=args.verbose)

    stats.print_summary()

    if args.dry_run:
        print("\nThis was a DRY RUN - no files were modified")
        print("Run without --dry-run to apply changes")
    else:
        print("\nBackup files created with .v2_backup extension")
        print("\nTo restore from backups:")
        print("  for f in theauditor/ast_extractors/python/*.v2_backup; do")
        print('    mv "$f" "${f%.v2_backup}"')
        print("  done")
        print("\nNEXT STEPS:")
        print("1. Run 'aud full' to test extraction")
        print("2. Check symbols extracted from complex files (async_app.py)")
        print("3. Verify no infinite recursion or performance issues")

    if stats.errors > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
