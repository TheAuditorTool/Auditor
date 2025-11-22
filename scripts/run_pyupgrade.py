#!/usr/bin/env python3
"""Run pyupgrade --py314-plus on all Python files in the project."""

from pathlib import Path
import subprocess
import sys

# Find all Python files in theauditor/ and tests/
files = list(Path('theauditor').rglob('*.py')) + list(Path('tests').rglob('*.py'))
print(f'Found {len(files)} Python files to modernize with pyupgrade...\n')

modified_files = []
errors = []

for pyfile in files:
    # Run pyupgrade --py314-plus on each file
    result = subprocess.run(
        ['pyupgrade', '--py314-plus', str(pyfile)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        errors.append(f'{pyfile}: {result.stderr}')
        print(f'ERROR: {pyfile}')
    elif result.stdout:
        # pyupgrade prints diff if file was modified
        modified_files.append(pyfile)
        print(f'+ {pyfile}')

print(f'\n{"="*60}')
print(f'PYUPGRADE SUMMARY')
print(f'{"="*60}')
print(f'Files processed: {len(files)}')
print(f'Files modified: {len(modified_files)}')
print(f'Errors: {len(errors)}')

if errors:
    print(f'\nErrors encountered:')
    for err in errors[:10]:  # Show first 10 errors
        print(f'  {err}')
    sys.exit(1)
else:
    print('\nAll files processed successfully!')
    sys.exit(0)
