"""
LibCST Codemod: Fix invalid stderr= argument in console.print() calls.

The rich_migration.py script incorrectly added stderr=True to console.print() calls,
but Rich's Console.print() doesn't have a stderr parameter AT ALL. To print to stderr
in Rich, you need a separate Console instance created with Console(stderr=True).

This script fixes that mistake by:
1. Finding console.print(..., stderr=...) calls (True OR False)
2. ALWAYS removing the stderr argument (Rich doesn't accept it)
3. If stderr=True: switching console -> err_console
4. If stderr=False: just removing the arg (stays on console)
5. Also handles self.console.print() pattern

Transforms:
    console.print("msg", stderr=True)
    -> err_console.print("msg")

    console.print("[error]msg[/error]", stderr=True, highlight=False)
    -> err_console.print("[error]msg[/error]", highlight=False)

    console.print("msg", stderr=False)
    -> console.print("msg")

    self.console.print("msg", stderr=True)
    -> self.err_console.print("msg")

Usage:
    # Dry run (preview changes)
    python scripts/fix_stderr_migration.py theauditor/commands/ --dry-run

    # Apply changes
    python scripts/fix_stderr_migration.py theauditor/commands/

    # Single file test
    python scripts/fix_stderr_migration.py theauditor/commands/explain.py --dry-run

Author: TheAuditor Team
Version: 1.1.0
"""

import argparse
import sys
from pathlib import Path
from typing import Sequence, Union

import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor


class FixStderrMigration(cst.CSTTransformer):
    """
    Transform console.print(..., stderr=True, ...) to err_console.print(...).

    This fixes the incorrect stderr=True parameter that was added by rich_migration.py.
    Rich's Console.print() doesn't have a stderr parameter - you need a separate
    Console instance created with Console(stderr=True).
    """

    def __init__(self, context: CodemodContext) -> None:
        super().__init__()
        self.context = context
        self.transformations = 0

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.Call:
        """
        Transform console.print(..., stderr=...) calls.

        Handles:
        - console.print(..., stderr=True) -> err_console.print(...)
        - console.print(..., stderr=False) -> console.print(...) [just remove arg]
        - self.console.print(..., stderr=True) -> self.err_console.print(...)

        Rich's Console.print() doesn't accept stderr parameter at all,
        so we must remove it regardless of True/False value.
        """
        # 1. MATCHING: Loosen the match to catch 'console.print' AND 'self.console.print'
        # Check if the function being called is 'print'
        if not m.matches(updated_node.func, m.Attribute(attr=m.Name("print"))):
            return updated_node

        # Check if the object calling print is 'console' or 'self.console'
        func_value = updated_node.func.value
        is_console_call = False

        if m.matches(func_value, m.Name("console")):
            is_console_call = True
        elif m.matches(func_value, m.Attribute(value=m.Name("self"), attr=m.Name("console"))):
            is_console_call = True

        if not is_console_call:
            return updated_node

        # 2. ARGUMENT PROCESSING
        has_stderr_kw = False
        is_stderr_true = False
        new_args = []

        for arg in updated_node.args:
            if arg.keyword is not None and arg.keyword.value == "stderr":
                has_stderr_kw = True
                # Check if it is specifically True
                if m.matches(arg.value, m.Name("True")):
                    is_stderr_true = True
                # We ALWAYS skip adding this arg to new_args,
                # because Rich's print() never accepts 'stderr='
                continue

            new_args.append(arg)

        if not has_stderr_kw:
            return updated_node

        # 3. TRANSFORMATION
        # Only switch to err_console if stderr was explicitly True
        # If stderr=False, we just removed the arg and stayed on console.print
        new_func = updated_node.func

        if is_stderr_true:
            # Handle switching the object (console -> err_console)
            if m.matches(func_value, m.Name("console")):
                # console.print -> err_console.print
                new_func = updated_node.func.with_changes(
                    value=cst.Name("err_console")
                )
                # Register import
                AddImportsVisitor.add_needed_import(
                    self.context,
                    "theauditor.pipeline.ui",
                    "err_console"
                )
            elif m.matches(func_value, m.Attribute(value=m.Name("self"), attr=m.Name("console"))):
                # self.console.print -> self.err_console.print
                new_func = updated_node.func.with_changes(
                    value=cst.Attribute(
                        value=cst.Name("self"),
                        attr=cst.Name("err_console")
                    )
                )

        self.transformations += 1

        return updated_node.with_changes(
            func=new_func,
            args=new_args
        )


def transform_file(file_path: str, dry_run: bool = False) -> tuple[str, int]:
    """
    Transform a single file.

    Returns (new_code, transformation_count).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        print(f"[ERROR] Failed to parse {file_path}: {e}", file=sys.stderr)
        return source, 0

    context = CodemodContext()
    transformer = FixStderrMigration(context)

    try:
        modified = module.visit(transformer)
    except Exception as e:
        print(f"[ERROR] Failed to transform {file_path}: {e}", file=sys.stderr)
        return source, 0

    # Apply import changes if we made transformations
    if transformer.transformations > 0:
        modified = AddImportsVisitor(context).transform_module(modified)

    # Verify generated code is syntactically valid
    if transformer.transformations > 0:
        try:
            compile(modified.code, file_path, 'exec')
        except SyntaxError as e:
            print(f"[CRITICAL] Generated invalid code for {file_path}: {e}", file=sys.stderr)
            print(f"[CRITICAL] Original file preserved - not modified", file=sys.stderr)
            return source, 0

    # Write changes if not dry run
    if not dry_run and transformer.transformations > 0:
        if not module.deep_equals(modified):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(modified.code)

    return modified.code, transformer.transformations


DEFAULT_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
    ".pf",
    ".auditor_venv",
    "scripts",  # Don't transform the migration scripts themselves!
}


def process_directory(directory: str, skip_dirs: set, dry_run: bool = False) -> tuple[int, int]:
    """Walk directory and transform all Python files. Returns (files_modified, total_transforms)."""
    import os

    files_modified = 0
    total_transforms = 0

    for root, dirs, files in os.walk(directory):
        # Filter out skip directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file).replace("\\", "/")

                new_code, count = transform_file(filepath, dry_run=dry_run)

                if count > 0:
                    files_modified += 1
                    total_transforms += count
                    mode = "[DRY-RUN]" if dry_run else "[OK]"
                    print(f"  {mode} {filepath}: {count} transformations")

    return files_modified, total_transforms


def show_diff(original: str, modified: str, file_path: str) -> None:
    """Show unified diff between original and modified code."""
    import difflib

    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}"
    )
    diff_text = "".join(diff)
    if diff_text:
        # Use buffer to handle Unicode safely on Windows
        try:
            print(diff_text)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(diff_text.encode('utf-8', errors='replace'))
            sys.stdout.buffer.write(b'\n')


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fix invalid stderr=True in console.print() calls"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Python files or directories to transform"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying files"
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show unified diff of changes"
    )
    parser.add_argument(
        "--skip",
        type=str,
        default="",
        help="Additional directories to skip (comma-separated)"
    )

    args = parser.parse_args()

    skip_dirs = DEFAULT_SKIP_DIRS.copy()
    if args.skip:
        for d in args.skip.split(","):
            skip_dirs.add(d.strip())

    total_transformations = 0
    files_modified = 0

    mode_str = "[DRY RUN] " if args.dry_run else ""
    print(f"{mode_str}Fix stderr Migration v1.0")
    print(f"Transforms: console.print(..., stderr=True) -> err_console.print(...)")
    print("=" * 70)

    for file_path in args.paths:
        path = Path(file_path)

        if path.is_dir():
            print(f"\nProcessing directory: {file_path}")
            files, transforms = process_directory(str(path), skip_dirs, dry_run=args.dry_run)
            files_modified += files
            total_transformations += transforms
        elif path.exists():
            if not path.suffix == ".py":
                print(f"[SKIP] Not a Python file: {file_path}", file=sys.stderr)
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()

            new_code, count = transform_file(file_path, dry_run=args.dry_run)

            if count > 0:
                files_modified += 1
                total_transformations += count

                if args.dry_run:
                    print(f"[DRY-RUN] {file_path}: {count} transformations")
                else:
                    print(f"[OK] {file_path}: {count} transformations")

                if args.diff and original != new_code:
                    show_diff(original, new_code, file_path)
            else:
                print(f"[SKIP] {file_path}: no stderr=True calls found")
        else:
            print(f"[ERROR] Path not found: {file_path}", file=sys.stderr)

    print("")
    print("=" * 70)
    print(f"{mode_str}COMPLETED")
    print(f"Files modified: {files_modified}")
    print(f"Transformations: {total_transformations}")

    if args.dry_run:
        print("\n[INFO] Dry run - no files were modified")
        print("[INFO] Run without --dry-run to apply changes")


if __name__ == "__main__":
    main()
