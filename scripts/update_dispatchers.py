#!/usr/bin/env python3
"""
Dispatcher Update Script for FileContext Migration
===================================================
Automatically updates the 159 caller locations after migration.

This script:
1. Backs up python.py
2. Adds build_file_context import
3. Injects context initialization logic
4. Replaces all (tree, self) calls with (context)

Author: Lead Auditor
Date: November 2025
"""

import re
import shutil
from pathlib import Path


def update_dispatchers():
    # Configuration
    python_extractor_path = Path("theauditor/indexer/extractors/python.py")
    init_path = Path("theauditor/ast_extractors/__init__.py")

    # ---------------------------------------------------------
    # 1. Update python.py (The Orchestrator)
    # ---------------------------------------------------------
    if python_extractor_path.exists():
        print(f"Processing {python_extractor_path}...")

        # Create backup
        backup_path = python_extractor_path.with_suffix('.py.bak_dispatcher')
        shutil.copy(python_extractor_path, backup_path)
        print(f"   -> Created backup: {backup_path}")

        content = python_extractor_path.read_text(encoding="utf-8")

        # A. Inject Import
        if "from theauditor.ast_extractors.utils.context" not in content:
            print("   -> Injecting import statement")
            # Add after other imports
            import_line = "from theauditor.ast_extractors.utils.context import build_file_context\n"

            # Find a good place to insert (after ast_extractors imports)
            if "from theauditor.ast_extractors" in content:
                # Insert after the last ast_extractors import
                lines = content.split('\n')
                last_ast_import_idx = -1
                for i, line in enumerate(lines):
                    if "from theauditor.ast_extractors" in line:
                        last_ast_import_idx = i

                if last_ast_import_idx >= 0:
                    lines.insert(last_ast_import_idx + 1, import_line.strip())
                    content = '\n'.join(lines)
            else:
                # Just add at the top
                content = import_line + content

        # B. Mass Replace Calls (The tedious part)
        # Pattern matches: extract_anything(tree, self) or extract_anything(tree, parser_self)
        original_content = content

        # Multiple patterns to catch variations
        patterns = [
            (r'(extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\s*\)', r'\1(context)'),
            (r'(extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*parser_self\s*\)', r'\1(context)'),
            (r'(extract_[a-zA-Z0-9_]+)\s*\(\s*actual_tree\s*,\s*self\s*\)', r'\1(context)'),
        ]

        total_replacements = 0
        for pattern, replacement in patterns:
            content, count = re.subn(pattern, replacement, content)
            total_replacements += count

        print(f"   -> Replaced {total_replacements} extractor calls")

        # C. Inject Context Initialization Logic
        # Look for the extract method to add context building
        if "context = build_file_context" not in content:
            print("   -> Injecting context initialization logic")

            # Find the extract method in PythonExtractor class
            # Look for: def extract(self, file_info, content, tree=None):
            extract_pattern = r'(def extract\s*\([^)]+\)\s*(?:->.*?)?\s*:\s*\n)'

            match = re.search(extract_pattern, content)
            if match:
                # Get the indentation of the first line after def extract
                def_end = match.end()

                # Find the indentation of the next line
                next_line_match = re.search(r'\n(\s+)', content[def_end:])
                if next_line_match:
                    indent = next_line_match.group(1)
                else:
                    indent = "        "  # Default 8 spaces

                # Build the context initialization block
                context_init = f'''
{indent}# [AUTO-PATCH] Build FileContext for NodeIndex optimization
{indent}# This replaces 300+ ast.walk calls with 1 walk + O(1) lookups
{indent}if tree and tree.get("type") == "python_ast":
{indent}    actual_tree = tree.get("tree")
{indent}    if actual_tree:
{indent}        from theauditor.ast_extractors.utils.context import build_file_context
{indent}        context = build_file_context(actual_tree, content, str(file_info['path']))
'''

                # Insert after the def line
                content = content[:def_end] + context_init + content[def_end:]
                print("   -> Context initialization injected successfully")
            else:
                print("   WARNING: Could not find extract method - manual edit needed")
                print("   You need to add this at the start of extract():")
                print("       context = build_file_context(tree.get('tree'), content, str(file_info['path']))")

        # Write the updated content
        python_extractor_path.write_text(content, encoding="utf-8")
        print(f"   SUCCESS: {python_extractor_path} updated")

    else:
        print(f"ERROR: Could not find {python_extractor_path}")
        return False

    # ---------------------------------------------------------
    # 2. Update __init__.py (The Mixin)
    # ---------------------------------------------------------
    if init_path.exists():
        print(f"\nProcessing {init_path}...")

        # Create backup
        backup_path = init_path.with_suffix('.py.bak_dispatcher')
        shutil.copy(init_path, backup_path)
        print(f"   -> Created backup: {backup_path}")

        content = init_path.read_text(encoding="utf-8")

        # Mass Replace Calls only (Context should be passed down from caller)
        patterns = [
            (r'(extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\s*\)', r'\1(context)'),
            (r'(extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*parser_self\s*\)', r'\1(context)'),
        ]

        total_replacements = 0
        for pattern, replacement in patterns:
            content, count = re.subn(pattern, replacement, content)
            total_replacements += count

        print(f"   -> Replaced {total_replacements} extractor calls")

        # Check if we need to add context parameter or building
        if total_replacements > 0 and "context" not in content:
            print("   WARNING: __init__.py uses extractors but doesn't define 'context'")
            print("   You may need to manually add context building or parameter passing")

        init_path.write_text(content, encoding="utf-8")
        print(f"   SUCCESS: {init_path} updated")
    else:
        print(f"INFO: {init_path} not found (skipping)")

    print("\n" + "="*60)
    print("DISPATCHER UPDATE COMPLETE")
    print("="*60)
    print("\nNEXT STEPS:")
    print("1. Check python.py to ensure 'context' is properly initialized")
    print("2. If __init__.py calls extractors, ensure it has context available")
    print("3. Run your test suite to verify everything works")
    print("\nBackup files created with .bak_dispatcher extension")

    return True

if __name__ == "__main__":
    success = update_dispatchers()
    if not success:
        print("\nERROR: Update failed. Check the error messages above.")
        exit(1)
