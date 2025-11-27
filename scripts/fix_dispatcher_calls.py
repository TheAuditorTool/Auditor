#!/usr/bin/env python3
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
    original = content

    # Patterns to replace
    patterns = [
        # core_extractors.extract_X(tree, self.ast_parser)
        (r'(core_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # framework_extractors.extract_X(tree, self.ast_parser)
        (r'(framework_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # orm_extractors.extract_X(tree, self.ast_parser)
        (r'(orm_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\s*\)', r'\1(context)'),
        (r'(orm_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # django_web_extractors.extract_X(tree, self.ast_parser)
        (r'(django_web_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # flask_extractors.extract_X(tree, self.ast_parser)
        (r'(flask_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # security_extractors.extract_X(tree, self.ast_parser)
        (r'(security_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # testing_extractors.extract_X(tree, self.ast_parser)
        (r'(testing_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # performance_extractors.extract_X(tree, self.ast_parser)
        (r'(performance_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # task_graphql_extractors.extract_X(tree, self.ast_parser)
        (r'(task_graphql_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # stdlib_pattern_extractors.extract_X(tree, self.ast_parser)
        (r'(stdlib_pattern_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # validation_extractors.extract_X(tree, self.ast_parser)
        (r'(validation_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # Any other module.extract_X(tree, self.ast_parser)
        (r'([a-zA-Z0-9_]+_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # Generic extractors (tree, self)
        (r'(extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\s*\)', r'\1(context)'),

        # Fundamental extractors
        (r'(fundamental_extractors\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*self\.ast_parser\s*\)', r'\1(context)'),

        # Any remaining .extract_X(tree, something)
        (r'(\w+\.extract_[a-zA-Z0-9_]+)\s*\(\s*tree\s*,\s*[^)]+\)', r'\1(context)'),
    ]

    total_replacements = 0
    for pattern, replacement in patterns:
        content, count = re.subn(pattern, replacement, content)
        if count > 0:
            print(f"  Replaced {count} instances of pattern: {pattern[:50]}...")
            total_replacements += count

    if total_replacements > 0:
        # Write the updated content
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
