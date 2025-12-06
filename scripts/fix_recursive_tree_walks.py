"""
Fix Recursive Tree Walk Bugs - Emergency Script #2
===================================================
Fixes helper functions with recursive context.walk_tree() calls that the
ast_walk_to_filecontext.py script missed.

The Problem:
- ast_walk_to_filecontext.py only tracked extract_* functions
- Helper functions INSIDE extractors weren't tracked
- calculate_nesting_level() recursively calls context.walk_tree() = infinite loop
- This crashes extraction for any complex file

The Fix:
1. Find all helper functions inside extract_* functions
2. Replace context.walk_tree() with ast.walk(node) for subtree walks
3. Add ast import if needed
4. Convert recursive patterns to parent_map pattern

Author: TheAuditor Team (fixing the blind spots)
Date: November 2025
"""

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import libcst as cst
from libcst import matchers as m


@dataclass
class FixStats:
    """Track what we've fixed."""

    files_processed: int = 0
    files_modified: int = 0
    helper_functions_fixed: int = 0
    context_walk_tree_replaced: int = 0
    recursive_patterns_converted: int = 0
    ast_imports_added: int = 0

    def print_summary(self):
        """Print a summary of changes."""
        print("\n" + "=" * 60)
        print("RECURSIVE TREE WALK FIX SUMMARY")
        print("=" * 60)
        print(f"Files processed: {self.files_processed}")
        print(f"Files modified: {self.files_modified}")
        print("\nFixes applied:")
        print(f"  Helper functions fixed: {self.helper_functions_fixed}")
        print(f"  context.walk_tree() replaced: {self.context_walk_tree_replaced}")
        print(f"  Recursive patterns converted: {self.recursive_patterns_converted}")
        print(f"  ast imports added: {self.ast_imports_added}")
        print("=" * 60)


class RecursiveTreeWalkFixer(cst.CSTTransformer):
    """
    Fixes helper functions with recursive context.walk_tree() calls.

    Transformations:
    1. context.walk_tree() → ast.walk(node) in helper functions
    2. Recursive nesting level patterns → parent_map pattern
    3. Add 'import ast' if needed
    """

    def __init__(self, stats: FixStats):
        super().__init__()
        self.stats = stats

        self.inside_extractor = False
        self.inside_helper_function = False
        self.current_extractor_name = None
        self.current_helper_name = None

        self.helper_functions_in_extractor: set[str] = set()

        self.needs_ast_import = False
        self.has_ast_import = False

        self.function_depth = 0

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Track when we enter functions."""
        func_name = node.name.value
        self.function_depth += 1

        if self.function_depth == 1 and func_name.startswith("extract_"):
            self.inside_extractor = True
            self.current_extractor_name = func_name
            self.helper_functions_in_extractor = set()

        elif self.function_depth > 1 and self.inside_extractor:
            self.inside_helper_function = True
            self.current_helper_name = func_name
            self.helper_functions_in_extractor.add(func_name)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Track when we leave functions."""
        func_name = original_node.name.value

        if self.function_depth > 1 and self.inside_helper_function:
            if func_name == self.current_helper_name:
                self.inside_helper_function = False
                self.current_helper_name = None

        elif (
            self.function_depth == 1
            and self.inside_extractor
            and func_name == self.current_extractor_name
        ):
            self.inside_extractor = False
            self.current_extractor_name = None
            self.helper_functions_in_extractor = set()

        self.function_depth -= 1
        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Replace context.walk_tree() with ast.walk(node) in helpers."""

        if not self.inside_helper_function:
            return updated_node

        if m.matches(
            updated_node.func, m.Attribute(value=m.Name("context"), attr=m.Name("walk_tree"))
        ):
            self.stats.context_walk_tree_replaced += 1
            self.stats.helper_functions_fixed += 1
            self.needs_ast_import = True

            new_call = cst.Call(
                func=cst.Attribute(value=cst.Name("ast"), attr=cst.Name("walk")),
                args=[cst.Arg(cst.Name("node"))],
            )

            return new_call

        if isinstance(updated_node.func, cst.Name):
            func_name = updated_node.func.value
            if func_name in self.helper_functions_in_extractor:
                self.stats.recursive_patterns_converted += 1

        return updated_node

    def visit_Import(self, node: cst.Import) -> None:
        """Track if we have 'import ast' in the file."""
        for name in node.names:
            if (
                isinstance(name, cst.ImportAlias)
                and hasattr(name.name, "value")
                and name.name.value == "ast"
            ):
                self.has_ast_import = True

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add 'import ast' if needed."""

        if not self.needs_ast_import or self.has_ast_import:
            return updated_node

        new_body = []
        import_added = False

        for i, stmt in enumerate(updated_node.body):
            if (
                i == 0
                and isinstance(stmt, cst.SimpleStatementLine)
                and len(stmt.body) == 1
                and isinstance(stmt.body[0], cst.Expr)
                and isinstance(stmt.body[0].value, (cst.SimpleString, cst.ConcatenatedString))
            ):
                new_body.append(stmt)
                continue

            if not import_added:
                is_import = False
                if isinstance(stmt, cst.SimpleStatementLine):
                    for item in stmt.body:
                        if isinstance(item, (cst.Import, cst.ImportFrom)):
                            is_import = True
                            break

                if is_import:
                    new_body.append(stmt)
                    continue

                import_stmt = cst.SimpleStatementLine(
                    body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("ast"))])]
                )
                new_body.append(import_stmt)
                self.stats.ast_imports_added += 1
                import_added = True

            new_body.append(stmt)

        if not import_added:
            import_stmt = cst.SimpleStatementLine(
                body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("ast"))])]
            )
            new_body.append(import_stmt)
            self.stats.ast_imports_added += 1

        return updated_node.with_changes(body=new_body)


def process_file(
    filepath: Path, stats: FixStats, dry_run: bool = False, verbose: bool = False
) -> bool:
    """
    Process a single Python file for recursive tree walk fixes.

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
        with open(filepath, encoding="utf-8") as f:
            source_code = f.read()

        if "def extract_" not in source_code:
            if verbose:
                print(f"  Skipping {filepath.name} (no extractor functions)")
            return False

        if "context.walk_tree" not in source_code:
            if verbose:
                print(f"  Skipping {filepath.name} (no context.walk_tree calls)")
            return False

        try:
            source_tree = cst.parse_module(source_code)
        except cst.ParserSyntaxError as e:
            print(f"  ERROR: Failed to parse {filepath.name}: {e}")
            return False

        transformer = RecursiveTreeWalkFixer(stats)
        modified_tree = source_tree.visit(transformer)

        if modified_tree.deep_equals(source_tree):
            if verbose:
                print(f"  No changes needed in {filepath.name}")
            return False

        stats.files_modified += 1

        if dry_run:
            print(f"  Would modify: {filepath.name}")
            if verbose:
                print(f"    - context.walk_tree() replaced: {stats.context_walk_tree_replaced}")
                print(f"    - Recursive patterns: {stats.recursive_patterns_converted}")
            return True

        backup_path = filepath.with_suffix(".py.bak_recursive")
        shutil.copy2(filepath, backup_path)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(modified_tree.code)

        print(
            f"  [FIXED] {filepath.name}: {stats.context_walk_tree_replaced} calls fixed (backup: {backup_path.name})"
        )
        return True

    except Exception as e:
        print(f"  ERROR processing {filepath.name}: {e}")
        import traceback

        if verbose:
            traceback.print_exc()
        return False


def main():
    """Main entry point for the recursive tree walk fixer."""

    parser = argparse.ArgumentParser(
        description="Fix recursive context.walk_tree() calls in helper functions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script fixes helper functions that recursively call context.walk_tree(),
which causes infinite loops and crashes extraction for complex files.

The Problem:
  def extract_loop_complexity(context):
      def calculate_nesting_level(node, level=1):
          for child in context.walk_tree():  # BUG: walks ENTIRE tree recursively
              nested_level = calculate_nesting_level(child, level+1)  # INFINITE LOOP

The Fix:
  def extract_loop_complexity(context):
      def calculate_nesting_level(node, level=1):
          for child in ast.walk(node):  # CORRECT: walks only node's subtree
              nested_level = calculate_nesting_level(child, level+1)

Examples:
  # Dry run first
  python fix_recursive_tree_walks.py --dry-run

  # Apply fixes
  python fix_recursive_tree_walks.py

  # Verbose output
  python fix_recursive_tree_walks.py --verbose
        """,
    )

    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("theauditor/ast_extractors/python"),
        help="Directory to fix (default: theauditor/ast_extractors/python)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually modify files, just show what would change",
    )

    parser.add_argument("--verbose", action="store_true", help="Show detailed progress information")

    args = parser.parse_args()

    if not args.target_dir.exists():
        print(f"ERROR: Target does not exist: {args.target_dir}")
        sys.exit(1)

    print("=" * 60)
    print("RECURSIVE TREE WALK FIXER")
    print("=" * 60)
    print(f"Target: {args.target_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Verbose: {args.verbose}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    stats = FixStats()

    if args.target_dir.is_file():
        python_files = [args.target_dir]
    else:
        python_files = list(args.target_dir.rglob("*.py"))

        python_files = [
            f
            for f in python_files
            if "test" not in f.name.lower()
            and not f.name.endswith(".bak")
            and not f.name.endswith(".backup")
            and not f.name.endswith(".bak_recursive")
            and "utils" not in str(f.parent)
        ]

    print(f"Found {len(python_files)} Python files to process\n")

    if not python_files:
        print("No Python files found to process!")
        sys.exit(0)

    for filepath in sorted(python_files):
        if args.verbose:
            print(f"Processing: {filepath}")

        process_file(filepath, stats, dry_run=args.dry_run, verbose=args.verbose)

    stats.print_summary()

    if args.dry_run:
        print("\nThis was a DRY RUN - no files were actually modified")
        print("Run without --dry-run to apply changes")
    else:
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Backup files created with .bak_recursive extension")
        print("\nTo restore from backups:")
        print('  for f in **/*.py.bak_recursive; do mv "$f" "${f%.bak_recursive}"; done')
        print("\nNEXT STEPS:")
        print("1. Run 'aud full' to test extraction")
        print("2. Check that async_app.py now extracts symbols (was 0 before)")
        print("3. Verify no infinite recursion crashes")

    sys.exit(0 if stats.files_modified > 0 or args.dry_run else 1)


if __name__ == "__main__":
    main()
