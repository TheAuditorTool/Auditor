"""
Fix forward reference errors after removing __future__ import annotations.

When we remove `from __future__ import annotations`, forward references
(when a class references itself in type hints) need to be quoted.

This script finds and fixes common forward reference patterns.
"""

import re
import sys
from pathlib import Path


def fix_forward_references(file_path):
    """Fix forward references in a Python file."""
    content = file_path.read_text(encoding="utf-8")
    original_content = content

    class_pattern = re.compile(r"^class\s+(\w+)", re.MULTILINE)
    classes_in_file = set(class_pattern.findall(content))

    if not classes_in_file:
        return False

    modified = False
    for class_name in classes_in_file:
        pattern1 = re.compile(rf"(\)\s*->\s*)({class_name})(\s*:)", re.MULTILINE)
        if pattern1.search(content):
            content = pattern1.sub(rf'\1"{class_name}"\3', content)
            modified = True

        pattern2 = re.compile(
            rf"(:\s*(?:dict|list|set|tuple)\[[^\]]*?)({class_name})([^\w])", re.MULTILINE
        )
        if pattern2.search(content):
            content = pattern2.sub(r'\1"\2"\3', content)
            modified = True

        pattern3 = re.compile(rf"(:\s*(?:Optional\[))({class_name})(\])", re.MULTILINE)
        if pattern3.search(content):
            content = pattern3.sub(r'\1"\2"\3', content)
            modified = True

        pattern4 = re.compile(rf"(:\s*)({class_name})(\s*\|\s*None)", re.MULTILINE)
        if pattern4.search(content):
            content = pattern4.sub(r'\1"\2"\3', content)
            modified = True

    if modified and content != original_content:
        file_path.write_text(content, encoding="utf-8")
        return True

    return False


def main():
    """Main entry point."""
    print("=" * 70)
    print("FORWARD REFERENCE FIXER")
    print("=" * 70)

    py_files = list(Path("theauditor").rglob("*.py"))
    print(f"Found {len(py_files)} Python files to check")

    fixed_count = 0
    for py_file in py_files:
        if fix_forward_references(py_file):
            print(f"  Fixed: {py_file}")
            fixed_count += 1

    print(f"\n{'=' * 70}")
    print(f"Fixed {fixed_count} files with forward reference issues")
    print("=" * 70)

    if fixed_count > 0:
        print("\nNow testing if aud works...")
        import subprocess

        result = subprocess.run(["aud", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[SUCCESS] aud works! Version: {result.stdout.strip()}")
        else:
            print(f"[ERROR] aud still has issues:\n{result.stderr}")
            print("\nThere may be additional forward reference patterns to fix.")

    return 0 if fixed_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
