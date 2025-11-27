#!/usr/bin/env python3
"""Add 'from __future__ import annotations' to all files with type hints."""

from pathlib import Path


def has_type_hints(content):
    """Check if file likely has type hints."""
    # Simple heuristics
    return (': ' in content or ' -> ' in content) and 'def ' in content

def has_future_annotations(content):
    """Check if file already has future annotations import."""
    return 'from __future__ import annotations' in content

def add_future_annotations(content):
    """Add future annotations import after docstring."""
    lines = content.split('\n')

    # Find where to insert (after module docstring if exists)
    insert_idx = 0
    in_docstring = False
    docstring_quotes = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check for docstring start
        if (i == 0 or (insert_idx == 0 and not stripped)) and (stripped.startswith('"""') or stripped.startswith("'''")):
            docstring_quotes = stripped[:3]
            if stripped.count(docstring_quotes) >= 2:
                # Single-line docstring
                insert_idx = i + 1
                break
            else:
                in_docstring = True
                continue

        # Check for docstring end
        if in_docstring and docstring_quotes in stripped:
            insert_idx = i + 1
            break

        # Skip empty lines and comments after docstring
        if insert_idx == 0 and (not stripped or stripped.startswith('#')):
            continue

        # Found first real code line
        if not in_docstring and stripped and not stripped.startswith('#'):
            insert_idx = i
            break

    # Insert the import
    if insert_idx > 0:
        # Add blank line if not already there
        if lines[insert_idx].strip():
            lines.insert(insert_idx, '')
            insert_idx += 1
        lines.insert(insert_idx, 'from __future__ import annotations')
        lines.insert(insert_idx + 1, '')
    else:
        # No docstring, add at top
        lines.insert(0, 'from __future__ import annotations')
        lines.insert(1, '')

    return '\n'.join(lines)

def main():
    count = 0
    for pyfile in Path('theauditor').rglob('*.py'):
        try:
            with open(pyfile, encoding='utf-8') as f:
                content = f.read()

            if has_type_hints(content) and not has_future_annotations(content):
                new_content = add_future_annotations(content)

                with open(pyfile, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                count += 1
                print(f'Fixed: {pyfile}')

        except Exception as e:
            print(f'ERROR {pyfile}: {e}')

    print(f'\nTotal files fixed: {count}')

if __name__ == '__main__':
    main()
