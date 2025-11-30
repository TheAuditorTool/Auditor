"""
Fix remaining dispatcher calls in python.py
Replaces all variations of extractor calls with context parameter.
"""

import re
from pathlib import Path


def fix_python_dispatcher():
    """Fix the remaining extractor calls in python.py"""

    python_file = Path("theauditor/indexer/extractors/python.py")

    if not python_file.exists():
        print(f"ERROR: {python_file} not found")
        return False

    print(f"Fixing dispatcher calls in {python_file}...")

    content = python_file.read_text(encoding="utf-8")

    patterns = [
        (
            r"(core_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(framework_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (r"(orm_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\s*\)", r"\1(context)"),
        (
            r"(orm_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(django_web_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(flask_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(security_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(testing_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(performance_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(task_graphql_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(stdlib_pattern_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"(validation_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (
            r"([a-zA-Z0-9_]+_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (r"(extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\s*\)", r"\1(context)"),
        (
            r"(fundamental_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)",
            r"\1(context)",
        ),
        (r"(\w+\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*[^)]+\)", r"\1(context)"),
    ]

    total_replacements = 0
    for pattern, replacement in patterns:
        content, count = re.subn(pattern, replacement, content)
        if count > 0:
            print(f"  Replaced {count} instances of pattern: {pattern[:50]}...")
            total_replacements += count

    if total_replacements > 0:
        python_file.write_text(content, encoding="utf-8")
        print(f"\nTotal replacements: {total_replacements}")
        print(f"SUCCESS: {python_file} updated")
        return True
    else:
        print("No changes needed")
        return False


if __name__ == "__main__":
    success = fix_python_dispatcher()
    if not success:
        print("\nNo dispatcher calls needed fixing")
        exit(0)
