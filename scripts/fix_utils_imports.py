#!/usr/bin/env python3
"""
Fix imports to use correct utils path
"""

from pathlib import Path


def fix_utils_imports():
    """Fix utils import paths in all files"""

    # Fix in Python extractor files
    python_dir = Path("theauditor/ast_extractors/python")

    fixed_count = 0

    for py_file in python_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        original = content

        # Fix the import path
        content = content.replace(
            "from theauditor.ast_extractors.utils.context import FileContext",
            "from theauditor.ast_extractors.python.utils.context import FileContext"
        )

        if content != original:
            py_file.write_text(content, encoding="utf-8")
            print(f"Fixed: {py_file.name}")
            fixed_count += 1

    # Also fix in python.py
    python_py = Path("theauditor/indexer/extractors/python.py")
    if python_py.exists():
        content = python_py.read_text(encoding="utf-8")
        original = content

        content = content.replace(
            "from theauditor.ast_extractors.utils.context import build_file_context",
            "from theauditor.ast_extractors.python.utils.context import build_file_context"
        )

        if content != original:
            python_py.write_text(content, encoding="utf-8")
            print(f"Fixed: {python_py}")
            fixed_count += 1

    # Fix in benchmark script
    benchmark = Path("test_performance_benchmark.py")
    if benchmark.exists():
        content = benchmark.read_text(encoding="utf-8")
        original = content

        content = content.replace(
            "from theauditor.ast_extractors.utils.node_index import NodeIndex",
            "from theauditor.ast_extractors.python.utils.node_index import NodeIndex"
        )

        if content != original:
            benchmark.write_text(content, encoding="utf-8")
            print(f"Fixed: {benchmark}")
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")
    return fixed_count > 0

if __name__ == "__main__":
    fix_utils_imports()
