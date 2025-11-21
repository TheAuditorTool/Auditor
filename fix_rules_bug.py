"""Bulk-fix O(N×M) bug in rules by adding execution_scope='database'"""
import re
from pathlib import Path

rules_dir = Path('theauditor/rules')
fixed_count = 0

for rule_file in rules_dir.rglob('*_analyze.py'):
    if rule_file.name.startswith('TEMPLATE'):
        continue

    content = rule_file.read_text(encoding='utf-8')

    # Check if it has METADATA
    if 'METADATA = RuleMetadata' not in content:
        continue

    # Check if it queries assignments or function_call_args globally
    has_global_query = (
        ('FROM assignments' in content or 'FROM function_call_args' in content) and
        'ORDER BY' in content
    )

    if not has_global_query:
        continue

    # Check if execution_scope='database' is missing
    if "execution_scope='database'" in content or 'execution_scope="database"' in content:
        continue  # Already fixed

    # Find the METADATA block and add execution_scope
    pattern = r'(METADATA = RuleMetadata\([^)]+)(requires_jsx_pass=(?:True|False))\s*\)'

    def add_execution_scope(match):
        metadata_start = match.group(1)
        jsx_param = match.group(2)
        return f'{metadata_start}{jsx_param},\n    execution_scope="database"  # Database-wide query, not per-file iteration\n)'

    new_content = re.sub(pattern, add_execution_scope, content, flags=re.DOTALL)

    if new_content != content:
        rule_file.write_text(new_content, encoding='utf-8')
        fixed_count += 1
        print(f'[FIXED] {rule_file.relative_to(rules_dir)}')

print(f'\nTotal rules fixed: {fixed_count}')
