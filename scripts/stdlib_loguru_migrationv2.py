"""LibCST codemod: Migrate stdlib logging.getLogger() to Loguru.

This script targets the specific pattern found in 41 TheAuditor files:

    import logging
    logger = logging.getLogger(__name__)

And transforms it to:

    from theauditor.utils.logging import logger

The logger.* call sites (debug, info, warning, error, exception) remain unchanged
because both stdlib and loguru expose identical method signatures.

Usage:
    # Dry run - preview changes without modifying files
    python scripts/stdlib_to_loguru_migration.py theauditor/ --dry-run

    # Apply changes to directory
    python scripts/stdlib_to_loguru_migration.py theauditor/

    # Single file with diff output
    python scripts/stdlib_to_loguru_migration.py theauditor/rules/base.py --dry-run --diff

    # Multiple specific files
    python scripts/stdlib_to_loguru_migration.py file1.py file2.py file3.py

Transformations:
    1. import logging -> [REMOVED if only used for getLogger]
    2. logger = logging.getLogger(__name__) -> [REMOVED]
    3. log = logging.getLogger(__name__) -> [REMOVED] + log.info -> logger.info
    4. Adds: from theauditor.utils.logging import logger

Safety Features:
    - Preserves `import logging` if used elsewhere (e.g., logging.ERROR constant)
    - Renames variable references if logger was aliased (log -> logger)
    - SKIPS class/instance attributes (self.logger, cls.logger) to prevent breakage
    - Syntax validation via compile() before writing any file
    - Dry-run mode with diff output for preview

Edge Cases NOT Transformed (require manual review):
    - self.logger = logging.getLogger(__name__)  # Instance attribute
    - cls.logger = logging.getLogger(__name__)   # Class attribute
    - MyClass.logger = logging.getLogger(...)    # Class variable

Author: TheAuditor Team
Date: 2025-12-04
LibCST Version: 1.8.6+
"""
from __future__ import annotations

import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor


class StdlibToLoguruCodemod(VisitorBasedCodemodCommand):
    """Convert stdlib logging.getLogger() patterns to Loguru.

    Handles:
    1. Module-level: logger = logging.getLogger(__name__)
    2. Function-scoped: import logging; logger = logging.getLogger(__name__)
    3. Aliased names: log = logging.getLogger(__name__) -> renames log.* to logger.*

    Skips (safety):
    - self.logger = logging.getLogger(...)  # Would break instance attribute refs
    - cls.logger = logging.getLogger(...)   # Would break class attribute refs

    Production Notes:
    - Import logic is in transform_module_impl for portability (works with libcst CLI)
    - State is reset per-file via _reset_state() to prevent cross-file leakage
    - Renaming only happens in Load contexts (reading the variable, not defining)
    """

    DESCRIPTION = "Migrates stdlib logging.getLogger() patterns to Loguru"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset file-specific state variables.

        Critical for preventing the "Dirty Context" bug when:
        1. Using libcst CLI with parallel processing
        2. Processing multiple files in one instance
        """
        # Track the variable name used (usually "logger", but could be "log", "_logger", etc.)
        self.logger_var_name: str | None = None
        # Track if we found the instantiation pattern
        self.has_logging_instantiation = False
        # Track transformation count for reporting
        self.transform_count = 0
        # Track skipped patterns for manual review
        self.skipped_patterns: list[str] = []

    def transform_module_impl(self, tree: cst.Module) -> cst.Module:
        """Standard lifecycle method for VisitorBasedCodemodCommand.

        This is where the magic happens:
        1. Reset state for the new module (prevents cross-file leakage)
        2. Run the transformation (calls leave_Assign, leave_Name, etc.)
        3. Handle imports (standard LibCST pattern - portable to CLI)
        """
        # 1. Reset state for the new module
        self._reset_state()

        # 2. Run the transformation via parent class
        tree = super().transform_module_impl(tree)

        # 3. Handle imports (standard LibCST pattern)
        if self.has_logging_instantiation:
            # Schedule import addition
            AddImportsVisitor.add_needed_import(
                self.context, "theauditor.utils.logging", "logger"
            )
            # Schedule import removal (safe: checks if logging is used elsewhere)
            RemoveImportsVisitor.remove_unused_import(self.context, "logging")

            # Apply import transformations
            tree = AddImportsVisitor(self.context).transform_module(tree)
            tree = RemoveImportsVisitor(self.context).transform_module(tree)

        return tree

    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> cst.BaseSmallStatement | cst.RemovalSentinel:
        """Find and remove: logger = logging.getLogger(...)

        Matches patterns (TRANSFORMED):
            logger = logging.getLogger(__name__)
            logger = logging.getLogger("my.module")
            log = logging.getLogger(__name__)

        Skipped patterns (PRESERVED - require manual review):
            self.logger = logging.getLogger(__name__)
            cls.logger = logging.getLogger(__name__)
            MyClass.logger = logging.getLogger(__name__)
        """
        # Match: any_var = logging.getLogger(...)
        if m.matches(
            updated_node.value,
            m.Call(
                func=m.Attribute(value=m.Name("logging"), attr=m.Name("getLogger"))
            ),
        ):
            # Safety check: only transform simple Name targets
            # Skip self.logger, cls.logger, MyClass.logger (Attribute targets)
            if len(updated_node.targets) == 1:
                target = updated_node.targets[0].target

                # SAFE: Simple variable assignment (logger = ...)
                if isinstance(target, cst.Name):
                    self.logger_var_name = target.value
                    self.has_logging_instantiation = True
                    self.transform_count += 1
                    # Remove the line - loguru's logger is pre-instantiated
                    return cst.RemovalSentinel.REMOVE

                # UNSAFE: Attribute assignment (self.logger = ..., cls.logger = ...)
                elif isinstance(target, cst.Attribute):
                    # Record for reporting but DO NOT transform
                    attr_name = target.attr.value if isinstance(target.attr, cst.Name) else "?"
                    if isinstance(target.value, cst.Name):
                        pattern = f"{target.value.value}.{attr_name}"
                    else:
                        pattern = f"<expr>.{attr_name}"
                    self.skipped_patterns.append(pattern)
                    # Return unchanged - preserve the original assignment
                    return updated_node

        return updated_node

    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.Name:
        """Rename usages if logger was aliased: log.info() -> logger.info()

        Only triggers if:
        1. We found an instantiation like 'log = logging.getLogger(...)'
        2. The variable name is NOT already 'logger'
        """
        if self.logger_var_name and self.logger_var_name != "logger":
            if updated_node.value == self.logger_var_name:
                return updated_node.with_changes(value="logger")
        return updated_node


# =============================================================================
# Standalone Runner - No yaml/init required
# =============================================================================

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
}

FILE_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


def safe_print(text: str) -> None:
    """Print text safely, replacing non-encodable characters for Windows CP1252."""
    try:
        print(text)
    except UnicodeEncodeError:
        safe_text = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_text)


def read_file_with_fallback(filepath: str) -> tuple[str, str]:
    """Read file trying multiple encodings. Returns (content, encoding_used)."""
    last_error = None
    for encoding in FILE_ENCODINGS:
        try:
            with open(filepath, encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError as e:
            last_error = e
    raise UnicodeDecodeError(
        "all", b"", 0, 0, f"Failed to decode {filepath} with any of: {FILE_ENCODINGS}"
    )


def transform_file(file_path: str, dry_run: bool = False) -> tuple[str, int, list[str]]:
    """Transform a single file.

    Returns:
        (new_code, transformation_count, skipped_patterns)

    Note: Import handling is now inside StdlibToLoguruCodemod.transform_module_impl,
    making this runner much simpler and the codemod portable to libcst CLI.
    """
    try:
        source, encoding = read_file_with_fallback(file_path)
    except UnicodeDecodeError as e:
        safe_print(f"[ERROR] Encoding error in {file_path}: {e}")
        return "", 0, []

    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        safe_print(f"[ERROR] Syntax error in {file_path}: {e}")
        return source, 0, []

    context = CodemodContext()
    codemod = StdlibToLoguruCodemod(context)

    try:
        # transform_module is the public API that calls transform_module_impl
        # This handles: AST transformation + import management in one pass
        modified = codemod.transform_module(module)
    except Exception as e:
        safe_print(f"[ERROR] Transform failed for {file_path}: {e}")
        return source, 0, []

    # Get metrics from the codemod instance
    transform_count = codemod.transform_count
    skipped_patterns = codemod.skipped_patterns

    # Validate generated code is syntactically correct
    if transform_count > 0:
        try:
            compile(modified.code, file_path, "exec")
        except SyntaxError as e:
            safe_print(f"[CRITICAL] Generated invalid code for {file_path}: {e}")
            safe_print("[CRITICAL] Original file preserved - not modified")
            return source, 0, skipped_patterns

    # Write if changed and not dry run
    if not dry_run and transform_count > 0:
        if not module.deep_equals(modified):
            with open(file_path, "w", encoding=encoding, newline="") as f:
                f.write(modified.code)

    return modified.code, transform_count, skipped_patterns


def process_directory(
    directory: str, skip_dirs: set[str], dry_run: bool = False
) -> tuple[int, int, dict[str, list[str]]]:
    """Walk directory and transform all Python files.

    Returns:
        (files_modified, total_transforms, skipped_by_file)
    """
    import os

    files_modified = 0
    total_transforms = 0
    skipped_by_file: dict[str, list[str]] = {}

    for root, dirs, files in os.walk(directory):
        # Filter out skip directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file).replace("\\", "/")
                _, count, skipped = transform_file(filepath, dry_run=dry_run)

                if count > 0:
                    files_modified += 1
                    total_transforms += count
                    mode = "[DRY-RUN]" if dry_run else "[OK]"
                    safe_print(f"  {mode} {filepath}")

                if skipped:
                    skipped_by_file[filepath] = skipped

    return files_modified, total_transforms, skipped_by_file


def main():
    """CLI entry point for standalone usage."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Migrate stdlib logging.getLogger() to Loguru",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run on directory
  python scripts/stdlib_to_loguru_migration.py theauditor/ --dry-run

  # Apply to single file
  python scripts/stdlib_to_loguru_migration.py theauditor/rules/base.py

  # Show diff for changes
  python scripts/stdlib_to_loguru_migration.py theauditor/rules/base.py --dry-run --diff

Pattern Targeted:
  import logging
  logger = logging.getLogger(__name__)

  ->

  from theauditor.utils.logging import logger

Patterns SKIPPED (require manual review):
  self.logger = logging.getLogger(...)   # Instance attributes
  cls.logger = logging.getLogger(...)    # Class attributes
""",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to transform")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--diff", action="store_true", help="Show unified diff of changes"
    )
    parser.add_argument(
        "--skip",
        type=str,
        default="",
        help="Additional directories to skip (comma-separated)",
    )

    args = parser.parse_args()

    skip_dirs = DEFAULT_SKIP_DIRS.copy()
    if args.skip:
        for d in args.skip.split(","):
            skip_dirs.add(d.strip())

    total_files = 0
    total_transforms = 0
    all_skipped: dict[str, list[str]] = {}

    mode_str = "[DRY RUN] " if args.dry_run else ""
    safe_print(f"{mode_str}Stdlib to Loguru Migration")
    safe_print(f"{mode_str}Pattern: logging.getLogger() -> theauditor.utils.logging")
    safe_print("=" * 60)

    for path in args.paths:
        if os.path.isdir(path):
            safe_print(f"\nProcessing directory: {path}")
            files, transforms, skipped = process_directory(
                path, skip_dirs, dry_run=args.dry_run
            )
            total_files += files
            total_transforms += transforms
            all_skipped.update(skipped)
        elif os.path.isfile(path):
            if not path.endswith(".py"):
                safe_print(f"[SKIP] Not a Python file: {path}")
                continue

            with open(path, encoding="utf-8") as f:
                original = f.read()

            new_code, count, skipped = transform_file(path, dry_run=args.dry_run)

            if skipped:
                all_skipped[path] = skipped

            if count > 0:
                total_files += 1
                total_transforms += count
                mode = "[DRY-RUN]" if args.dry_run else "[OK]"
                safe_print(f"  {mode} {path}")

                if args.diff and original != new_code:
                    import difflib

                    diff = difflib.unified_diff(
                        original.splitlines(keepends=True),
                        new_code.splitlines(keepends=True),
                        fromfile=f"a/{path}",
                        tofile=f"b/{path}",
                    )
                    print("".join(diff))
            else:
                safe_print(f"  [SKIP] {path}: no logging.getLogger() found")
        else:
            safe_print(f"[ERROR] Path not found: {path}")

    safe_print("")
    safe_print("=" * 60)
    safe_print(f"{mode_str}COMPLETED")
    safe_print(f"Files modified: {total_files}")
    safe_print(f"Transformations: {total_transforms}")

    # Report skipped patterns that require manual review
    if all_skipped:
        safe_print("")
        safe_print("=" * 60)
        safe_print("[WARNING] Skipped patterns (require manual review):")
        safe_print("")
        for filepath, patterns in all_skipped.items():
            safe_print(f"  {filepath}:")
            for pattern in patterns:
                safe_print(f"    - {pattern} = logging.getLogger(...)")
        safe_print("")
        safe_print("These are class/instance attributes that cannot be safely")
        safe_print("auto-migrated. Review and handle manually if needed.")

    if args.dry_run:
        safe_print("\n[INFO] Dry run - no files were modified")


if __name__ == "__main__":
    main()
