#!/usr/bin/env python3
"""
Fix the order of imports - from __future__ must come first
"""

import re
from pathlib import Path


def fix_future_imports():
    """Fix import order in all Python extractor files"""

    python_dir = Path("theauditor/ast_extractors/python")

    if not python_dir.exists():
        print(f"ERROR: {python_dir} not found")
        return False

    fixed_count = 0

    for py_file in python_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")

        # Check if file has both imports in wrong order
        if ("from theauditor.ast_extractors.utils.context import FileContext" in content and
            "from __future__ import annotations" in content):

            lines = content.split('\n')
            new_lines = []
            future_line = None
            context_line = None

            # Find and remove both lines
            for line in lines:
                if line.strip() == "from __future__ import annotations":
                    future_line = line
                    continue  # Skip this line for now
                elif line.strip() == "from theauditor.ast_extractors.utils.context import FileContext":
                    context_line = line
                    continue  # Skip this line for now
                else:
                    new_lines.append(line)

            # If we found both, reinsert them in correct order after docstring
            if future_line and context_line:
                # Find where to insert (after docstring)
                insert_index = 0
                docstring_count = 0

                for i, line in enumerate(new_lines):
                    if '"""' in line:
                        docstring_count += line.count('"""')
                        if docstring_count >= 2:  # End of docstring
                            insert_index = i + 1
                            break

                # Insert in correct order
                new_lines.insert(insert_index, future_line)
                new_lines.insert(insert_index + 1, context_line)

                # Write back
                new_content = '\n'.join(new_lines)
                if new_content != content:
                    py_file.write_text(new_content, encoding="utf-8")
                    print(f"Fixed: {py_file.name}")
                    fixed_count += 1

    print(f"\nFixed {fixed_count} files")
    return fixed_count > 0

if __name__ == "__main__":
    fix_future_imports()
