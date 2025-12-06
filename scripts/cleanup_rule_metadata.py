#!/usr/bin/env python
"""LibCST-based cleanup script for rule METADATA.

Removes deprecated fields from RuleMetadata(...) calls:
- requires_jsx_pass (dead code - never read)

Usage:
    python scripts/cleanup_rule_metadata.py --dry-run  # Preview changes
    python scripts/cleanup_rule_metadata.py            # Apply changes
"""

import argparse
import sys
from pathlib import Path

import libcst as cst
from libcst import matchers as m


class RemoveDeprecatedMetadataFields(cst.CSTTransformer):
    """Remove deprecated keyword arguments from RuleMetadata calls."""

    DEPRECATED_FIELDS = frozenset(["requires_jsx_pass", "jsx_pass_mode"])

    def __init__(self):
        super().__init__()
        self.changes_made = 0

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.Call:
        """Remove deprecated kwargs from RuleMetadata(...) calls."""
        # Match: RuleMetadata(...)
        if not m.matches(updated_node.func, m.Name("RuleMetadata")):
            return updated_node

        # Filter out deprecated keyword arguments
        new_args = []
        removed = []

        for arg in updated_node.args:
            # Skip positional args (keep them)
            if arg.keyword is None:
                new_args.append(arg)
                continue

            # Check if this keyword is deprecated
            if arg.keyword.value in self.DEPRECATED_FIELDS:
                removed.append(arg.keyword.value)
                self.changes_made += 1
            else:
                new_args.append(arg)

        if not removed:
            return updated_node

        # Fix trailing comma on last arg if needed
        if new_args:
            # Ensure last arg has no trailing comma if it's the only one
            # or has proper trailing comma for multi-line
            last_idx = len(new_args) - 1
            last_arg = new_args[last_idx]

            # Check if this is a multi-line call (has newlines in whitespace)
            is_multiline = any(
                isinstance(arg.comma, cst.Comma)
                and arg.comma.whitespace_after
                and "\n" in arg.comma.whitespace_after.value
                if hasattr(arg.comma, "whitespace_after")
                and hasattr(arg.comma.whitespace_after, "value")
                else False
                for arg in updated_node.args
            )

            if is_multiline:
                # Keep trailing comma for multi-line formatting
                if not isinstance(last_arg.comma, cst.Comma):
                    new_args[last_idx] = last_arg.with_changes(
                        comma=cst.Comma(
                            whitespace_after=cst.SimpleWhitespace("")
                        )
                    )
            else:
                # Remove trailing comma for single-line
                if isinstance(last_arg.comma, cst.Comma):
                    new_args[last_idx] = last_arg.with_changes(
                        comma=cst.MaybeSentinel.DEFAULT
                    )

        return updated_node.with_changes(args=new_args)


def process_file(file_path: Path, dry_run: bool = False) -> tuple[bool, int]:
    """Process a single file, return (changed, num_changes)."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"  SKIP: {file_path} (encoding error)")
        return False, 0

    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        print(f"  SKIP: {file_path} (parse error: {e})")
        return False, 0

    transformer = RemoveDeprecatedMetadataFields()
    modified = module.visit(transformer)

    if transformer.changes_made == 0:
        return False, 0

    if not module.deep_equals(modified):
        if dry_run:
            print(f"  WOULD MODIFY: {file_path} ({transformer.changes_made} field(s))")
        else:
            file_path.write_text(modified.code, encoding="utf-8")
            print(f"  MODIFIED: {file_path} ({transformer.changes_made} field(s))")
        return True, transformer.changes_made

    return False, 0


def main():
    parser = argparse.ArgumentParser(
        description="Remove deprecated fields from RuleMetadata calls"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("theauditor/rules"),
        help="Path to rules directory (default: theauditor/rules)",
    )
    args = parser.parse_args()

    rules_dir = args.path
    if not rules_dir.exists():
        print(f"ERROR: Rules directory not found: {rules_dir}")
        sys.exit(1)

    print(f"{'DRY RUN - ' if args.dry_run else ''}Scanning {rules_dir}...")
    print(f"Removing deprecated fields: {', '.join(RemoveDeprecatedMetadataFields.DEPRECATED_FIELDS)}")
    print()

    files_modified = 0
    total_changes = 0

    for py_file in sorted(rules_dir.rglob("*.py")):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file):
            continue
        if py_file.name.startswith("test_"):
            continue

        changed, num_changes = process_file(py_file, args.dry_run)
        if changed:
            files_modified += 1
            total_changes += num_changes

    print()
    print(f"{'Would modify' if args.dry_run else 'Modified'}: {files_modified} file(s)")
    print(f"Total changes: {total_changes}")

    if args.dry_run and files_modified > 0:
        print()
        print("Run without --dry-run to apply changes")


if __name__ == "__main__":
    main()
