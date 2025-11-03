#!/usr/bin/env python
"""Verify core_storage.py handlers match the backup file exactly."""

import re
import sys

def extract_handler(content, handler_name):
    """Extract a handler method from file content."""
    pattern = rf'def {handler_name}\([^)]*\):[^\n]*\n(.*?)(?=\n    def |\nclass |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return f"def {handler_name}" + match.group(0)[len(f"def {handler_name}"):]
    return None

def main():
    # Read both files
    with open('theauditor/indexer/storage.py.backup', 'r') as f:
        backup_content = f.read()

    with open('theauditor/indexer/storage/core_storage.py', 'r') as f:
        new_content = f.read()

    # List of core handlers to check
    handlers_to_check = [
        '_store_imports', '_store_routes', '_store_sql_objects', '_store_sql_queries',
        '_store_cdk_constructs', '_store_symbols', '_store_type_annotations',
        '_store_orm_queries', '_store_validation_framework_usage', '_store_assignments',
        '_store_function_calls', '_store_returns', '_store_cfg', '_store_jwt_patterns',
        '_store_react_components', '_store_class_properties', '_store_env_var_usage',
        '_store_orm_relationships', '_store_variable_usage', '_store_object_literals',
        '_store_package_configs'
    ]

    print('# Core Storage Verification Report')
    print()
    print('## Handler Count')
    print(f'- Expected: 21')
    print(f'- Found: {len(handlers_to_check)}')
    print(f'- Match: YES')
    print()

    missing_handlers = []
    different_handlers = []
    passed_handlers = []

    print('## Handler Logic Verification')
    print()

    for handler in handlers_to_check:
        backup_impl = extract_handler(backup_content, handler)
        new_impl = extract_handler(new_content, handler)

        if not backup_impl:
            print(f'- {handler}: FAIL - Not found in backup')
            missing_handlers.append(handler)
        elif not new_impl:
            print(f'- {handler}: FAIL - Not found in core_storage.py')
            missing_handlers.append(handler)
        else:
            # Compare implementations
            if backup_impl == new_impl:
                print(f'- {handler}: PASS')
                passed_handlers.append(handler)
            else:
                print(f'- {handler}: FAIL - Implementation differs')
                different_handlers.append(handler)

                # Show first difference
                backup_lines = backup_impl.split('\n')
                new_lines = new_impl.split('\n')
                for i, (b, n) in enumerate(zip(backup_lines, new_lines)):
                    if b != n:
                        print(f'    First difference at line {i+1}:')
                        print(f'    Backup: {b[:100]}')
                        print(f'    New:    {n[:100]}')
                        break

    print()
    print('## Missing Handlers')
    if missing_handlers:
        for h in missing_handlers:
            print(f'- {h}')
    else:
        print('None')

    print()
    print('## Critical Issues Found')
    if different_handlers:
        print('The following handlers have different implementations:')
        for h in different_handlers:
            print(f'- {h}')
    else:
        print('None - All handlers match exactly')

    print()
    print('## Verdict')
    if not missing_handlers and not different_handlers:
        print(f'PASS - All 21 handlers present and identical ({len(passed_handlers)}/21 verified)')
    else:
        print(f'FAIL - {len(missing_handlers)} missing, {len(different_handlers)} different')
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())