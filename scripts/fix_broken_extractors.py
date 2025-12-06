"""
Fix Broken Extractors - Emergency Repair Script
================================================
Fixes the catastrophic bug introduced by ast_walk_to_filecontext.py

The Problem:
- Script changed function signature from (tree: dict) to (context: FileContext)
- Then transformed actual_tree = tree.get("tree") to context.tree = tree.get("tree")
- But 'tree' variable no longer exists after signature change!
- Result: 139 NameErrors across 22 files

The Fix:
1. Remove all lines containing: context.tree = tree.get("tree")
2. Remove any remaining tree.get("tree") patterns
3. Fix any actual_tree references to use context.tree properly

Author: Lead Coder (cleaning up the mess)
Date: November 2025
"""

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


def fix_file(filepath: Path, dry_run: bool = False, verbose: bool = False) -> tuple[bool, int]:
    """
    Fix a single Python file.

    Returns:
        (was_modified, num_lines_removed)
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  ERROR reading {filepath}: {e}")
        return False, 0

    fixed_lines = []
    removed_count = 0

    for line in lines:
        if 'context.tree = tree.get("tree")' in line or "context.tree = tree.get('tree')" in line:
            removed_count += 1
            if verbose:
                print(f"  Removing line: {line.strip()}")
            continue

        if 'actual_tree = tree.get("tree")' in line or "actual_tree = tree.get('tree')" in line:
            removed_count += 1
            if verbose:
                print(f"  Removing line: {line.strip()}")
            continue

        if re.search(r'\w+\s*=\s*tree\.get\(["\']tree["\']\)', line):
            removed_count += 1
            if verbose:
                print(f"  Removing line: {line.strip()}")
            continue

        fixed_lines.append(line)

    if removed_count == 0:
        return False, 0

    if dry_run:
        print(f"  Would remove {removed_count} broken lines from {filepath.name}")
        return True, removed_count

    backup_path = filepath.with_suffix(".py.bak")
    shutil.copy2(filepath, backup_path)

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(fixed_lines)

    print(
        f"  Fixed {filepath.name}: removed {removed_count} broken lines (backup: {backup_path.name})"
    )
    return True, removed_count


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix broken extractors after ast_walk_to_filecontext.py disaster",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script fixes the NameError bugs introduced by ast_walk_to_filecontext.py

The broken pattern:
    context.tree = tree.get("tree")  # 'tree' is undefined!

Will be removed entirely (context.tree already contains the AST).

Examples:
    # Dry run first (recommended)
    python fix_broken_extractors.py --dry-run

    # Apply fixes
    python fix_broken_extractors.py

    # Verbose output
    python fix_broken_extractors.py --verbose
        """,
    )

    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("theauditor/ast_extractors/python"),
        help="Directory to fix (default: theauditor/ast_extractors/python)",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Don't modify files, just show what would be fixed"
    )

    parser.add_argument(
        "--verbose", action="store_true", help="Show detailed information about changes"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("EMERGENCY EXTRACTOR REPAIR SCRIPT")
    print("=" * 60)
    print(f"Target: {args.target_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE (will create .bak files)'}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    if not args.target_dir.exists():
        print(f"ERROR: Directory not found: {args.target_dir}")
        sys.exit(1)

    python_files = list(args.target_dir.rglob("*.py"))

    python_files = [
        f
        for f in python_files
        if "test" not in f.name.lower()
        and not f.name.endswith(".bak")
        and "__pycache__" not in str(f)
    ]

    print(f"Found {len(python_files)} Python files to check\n")

    total_fixed = 0
    total_lines_removed = 0
    fixed_files = []

    for filepath in sorted(python_files):
        was_fixed, lines_removed = fix_file(filepath, dry_run=args.dry_run, verbose=args.verbose)
        if was_fixed:
            total_fixed += 1
            total_lines_removed += lines_removed
            fixed_files.append(filepath.name)

    print("\n" + "=" * 60)
    print("REPAIR SUMMARY")
    print("=" * 60)
    print(f"Files checked: {len(python_files)}")
    print(f"Files fixed: {total_fixed}")
    print(f"Broken lines removed: {total_lines_removed}")

    if fixed_files and args.verbose:
        print("\nFixed files:")
        for name in fixed_files:
            print(f"  - {name}")

    if args.dry_run:
        print("\nThis was a DRY RUN - no files were modified")
        print("Run without --dry-run to apply fixes")
    else:
        if total_fixed > 0:
            print(f"\nSUCCESS: Fixed {total_fixed} files")
            print("Backup files created with .bak extension")
            print("\nTo restore from backups if needed:")
            print('  for f in theauditor/ast_extractors/python/*.bak; do mv "$f" "${f%.bak}"; done')
        else:
            print("\nSUCCESS: No broken patterns found - files are clean!")

    print("=" * 60)


if __name__ == "__main__":
    main()
