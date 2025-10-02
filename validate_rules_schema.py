#!/usr/bin/env python3
"""
Cross-reference ALL database queries in rules against the actual schema.
Comprehensive validation report for SQL queries in TheAuditor rules.
"""

import ast
import re
from pathlib import Path
from collections import defaultdict
import sys

# Import schema
sys.path.insert(0, str(Path.cwd()))
from theauditor.indexer.schema import TABLES


class SQLQueryExtractor(ast.NodeVisitor):
    """Extract SQL queries from AST nodes."""

    def __init__(self):
        self.queries = []

    def visit_Call(self, node):
        """Visit function call nodes."""
        # Check if it's an execute call
        func_name = None
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        if func_name and 'execute' in func_name.lower():
            # Get first argument (the SQL query)
            if node.args:
                arg = node.args[0]
                query_text = None

                if isinstance(arg, ast.Constant):  # Python 3.8+
                    query_text = arg.value
                elif isinstance(arg, ast.Str):  # Python 3.7
                    query_text = arg.s
                elif isinstance(arg, ast.JoinedStr):  # f-strings
                    # Try to reconstruct the query (partial)
                    parts = []
                    for val in arg.values:
                        if isinstance(val, ast.Constant):
                            parts.append(val.value)
                        elif isinstance(val, ast.Str):
                            parts.append(val.s)
                        else:
                            parts.append('?')  # Placeholder for variables
                    query_text = ''.join(parts)

                if query_text and isinstance(query_text, str):
                    # Must contain SQL keywords
                    if re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|CREATE|ALTER)\b', query_text, re.IGNORECASE):
                        self.queries.append(query_text)

        self.generic_visit(node)


def extract_queries_from_file(file_path):
    """Extract all SQL queries from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))
        extractor = SQLQueryExtractor()
        extractor.visit(tree)
        return extractor.queries
    except Exception as e:
        # If AST parsing fails, try regex fallback
        return []


def extract_table_from_query(query):
    """Extract table names from SQL query."""
    tables = set()

    # FROM clauses
    for match in re.finditer(r'\bFROM\s+(\w+)', query, re.IGNORECASE):
        tables.add(match.group(1))

    # JOIN clauses
    for match in re.finditer(r'\bJOIN\s+(\w+)', query, re.IGNORECASE):
        tables.add(match.group(1))

    # INSERT INTO
    for match in re.finditer(r'\bINSERT\s+INTO\s+(\w+)', query, re.IGNORECASE):
        tables.add(match.group(1))

    # UPDATE
    for match in re.finditer(r'\bUPDATE\s+(\w+)', query, re.IGNORECASE):
        tables.add(match.group(1))

    # DELETE FROM
    for match in re.finditer(r'\bDELETE\s+FROM\s+(\w+)', query, re.IGNORECASE):
        tables.add(match.group(1))

    return tables


def extract_columns_from_query(query, table_name):
    """Extract column names referenced for a specific table."""
    columns = set()

    # Pattern: table.column
    for match in re.finditer(rf'\b{table_name}\.(\w+)', query, re.IGNORECASE):
        columns.add(match.group(1))

    # Pattern: SELECT columns FROM table
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM\s+' + table_name, query, re.IGNORECASE | re.DOTALL)
    if select_match:
        cols_str = select_match.group(1)
        # Skip * and functions
        if '*' not in cols_str:
            for col in re.split(r',\s*', cols_str):
                col = col.strip()
                # Remove table prefix if present
                if '.' in col:
                    col = col.split('.')[-1]
                # Remove AS aliases
                col = col.split()[0]
                # Skip functions
                if '(' not in col and col.upper() not in ['DISTINCT', 'ALL']:
                    columns.add(col)

    # Pattern: WHERE table.column
    for match in re.finditer(rf'\b{table_name}\.(\w+)\s*[=<>!]', query, re.IGNORECASE):
        columns.add(match.group(1))

    return columns


def main():
    print('=' * 80)
    print('DATABASE SCHEMA VALIDATION REPORT')
    print('=' * 80)
    print(f'\nTotal tables defined in schema: {len(TABLES)}')

    # Build lookup structures
    valid_tables = set(TABLES.keys())
    table_columns = {}
    for table_name, schema in TABLES.items():
        table_columns[table_name] = {col.name for col in schema.columns}

    print('\n' + '=' * 80)
    print('SCANNING RULES FOR SQL QUERIES (AST-based extraction)')
    print('=' * 80)

    # Scan rule files
    rules_dir = Path('theauditor/rules')

    queries_by_file = {}
    tables_referenced = defaultdict(int)
    columns_by_table = defaultdict(lambda: defaultdict(set))

    total_queries = 0
    total_files = 0

    for rule_file in rules_dir.rglob('*.py'):
        if rule_file.name.startswith('__') or 'test' in rule_file.name.lower():
            continue

        total_files += 1
        queries = extract_queries_from_file(rule_file)

        if queries:
            queries_by_file[str(rule_file)] = queries
            total_queries += len(queries)

            for query in queries:
                # Extract tables
                tables = extract_table_from_query(query)
                for table in tables:
                    tables_referenced[table] += 1

                    # Extract columns for this table
                    columns = extract_columns_from_query(query, table)
                    for col in columns:
                        columns_by_table[table][col].add(str(rule_file))

    print(f'\nScanned files: {total_files}')
    print(f'Total SQL queries found: {total_queries}')
    print(f'Files with queries: {len(queries_by_file)}')
    print(f'Unique tables referenced: {len(tables_referenced)}')

    print('\n' + '=' * 80)
    print('TABLE REFERENCES')
    print('=' * 80)

    for table in sorted(tables_referenced.keys()):
        count = tables_referenced[table]
        status = 'VALID' if table in valid_tables else '** MISSING **'
        print(f'  {table:35} {count:4} refs - {status}')

    print('\n' + '=' * 80)
    print('CRITICAL ISSUES: MISSING TABLES')
    print('=' * 80)

    missing_tables = [t for t in tables_referenced.keys() if t not in valid_tables]
    if missing_tables:
        print(f'\nFound {len(missing_tables)} tables referenced but NOT in schema:')
        for table in sorted(missing_tables):
            print(f'  - {table} (referenced {tables_referenced[table]} times)')
            # Show which files reference it
            for file_path, queries in queries_by_file.items():
                for query in queries:
                    if table in extract_table_from_query(query):
                        print(f'      File: {Path(file_path).name}')
                        break
    else:
        print('\nALL TABLES VALID - No missing tables found')

    print('\n' + '=' * 80)
    print('HIGH PRIORITY: COLUMN VALIDATION')
    print('=' * 80)

    column_issues = []
    for table in sorted(columns_by_table.keys()):
        if table not in valid_tables:
            continue  # Already reported as missing table

        valid_cols = table_columns[table]
        for column in sorted(columns_by_table[table].keys()):
            if column not in valid_cols:
                files = columns_by_table[table][column]
                column_issues.append((table, column, files))

    if column_issues:
        print(f'\nFound {len(column_issues)} column mismatches:')
        for table, column, files in column_issues:
            print(f'\n  Table: {table}')
            print(f'  Column: {column} ** NOT IN SCHEMA **')
            valid = sorted(table_columns[table])
            print(f'  Valid columns ({len(valid)}): {", ".join(valid[:15])}{"..." if len(valid) > 15 else ""}')
            print(f'  Referenced in: {len(files)} file(s)')
            for f in sorted(files)[:5]:  # Show first 5 files
                print(f'    - {Path(f).name}')
            if len(files) > 5:
                print(f'    ... and {len(files) - 5} more')
    else:
        print('\nALL COLUMNS VALID - No column mismatches found')

    print('\n' + '=' * 80)
    print('COMMON PATTERNS')
    print('=' * 80)

    # Show top 10 most queried tables
    print('\nTop 10 Most Queried Tables:')
    for table, count in sorted(tables_referenced.items(), key=lambda x: x[1], reverse=True)[:10]:
        status = 'OK' if table in valid_tables else 'MISSING'
        print(f'  {table:30} {count:4} queries - {status}')

    print('\n' + '=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print(f'Total SQL queries analyzed: {total_queries}')
    print(f'Tables in schema: {len(valid_tables)}')
    print(f'Tables referenced: {len(tables_referenced)}')
    print(f'Missing tables: {len(missing_tables)}')
    print(f'Column mismatches: {len(column_issues)}')

    # Note about sqlite_master
    if 'sqlite_master' in missing_tables:
        print('\nNOTE: sqlite_master is a SQLite system table (valid)')
        missing_tables.remove('sqlite_master')

    if missing_tables or column_issues:
        print('\nSTATUS: ** FAILED ** - Schema mismatches detected')
        return 1
    else:
        print('\nSTATUS: ** PASSED ** - All queries valid')
        return 0


if __name__ == '__main__':
    sys.exit(main())
