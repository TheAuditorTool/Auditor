#!/usr/bin/env python
"""Check if template literals are being extracted."""
import sqlite3
from pathlib import Path

conn = sqlite3.connect('C:/Users/santa/Desktop/plant/.pf/repo_index.db')
c = conn.cursor()

# Check if template literal query from line 7 is extracted
print('=== QUERIES FROM 20250916000008-add-critical-constraints.js ===')
c.execute("SELECT line_number, command, query_text FROM sql_queries WHERE file_path LIKE '%20250916000008%' ORDER BY line_number")
results = c.fetchall()

if results:
    for line, cmd, query in results:
        query_preview = query[:80].replace('\n', ' ')
        print(f'Line {line}: [{cmd}] {query_preview}')
else:
    print('NO QUERIES EXTRACTED from this file')

# This file has template literal at line 7 and 14
print('\n=== FUNCTION CALL ARGS FROM SAME FILE (lines 7, 14) ===')
c.execute("SELECT line, argument_expr FROM function_call_args WHERE file LIKE '%20250916000008%' AND line IN (7, 14) AND argument_index = 0")
args = c.fetchall()
for line, arg in args:
    arg_preview = arg[:80].replace('\n', ' ')
    is_template = '(template literal)' if arg.strip().startswith('`') else '(plain string)'
    print(f'Line {line}: {is_template} {arg_preview}')

# Count template literals in function_call_args
print('\n=== TEMPLATE LITERALS IN FUNCTION_CALL_ARGS ===')
c.execute("SELECT COUNT(*) FROM function_call_args WHERE argument_expr LIKE '`%' AND argument_index = 0")
template_count = c.fetchone()[0]
print(f'Total template literals (backtick strings): {template_count}')

# Count template literals with SQL keywords
c.execute("""
    SELECT COUNT(*) FROM function_call_args
    WHERE argument_expr LIKE '`%'
    AND argument_index = 0
    AND (
        UPPER(argument_expr) LIKE '%SELECT%' OR
        UPPER(argument_expr) LIKE '%INSERT%' OR
        UPPER(argument_expr) LIKE '%UPDATE%' OR
        UPPER(argument_expr) LIKE '%DELETE%' OR
        UPPER(argument_expr) LIKE '%CREATE%' OR
        UPPER(argument_expr) LIKE '%ALTER%' OR
        UPPER(argument_expr) LIKE '%DROP%'
    )
""")
sql_template_count = c.fetchone()[0]
print(f'Template literals with SQL keywords: {sql_template_count}')

# Sample template literal SQL queries
print('\n=== SAMPLE TEMPLATE LITERAL SQL ===')
c.execute("""
    SELECT file, line, callee_function, SUBSTR(argument_expr, 1, 60) as arg_preview
    FROM function_call_args
    WHERE argument_expr LIKE '`%'
    AND argument_index = 0
    AND UPPER(argument_expr) LIKE '%ALTER%'
    LIMIT 5
""")
samples = c.fetchall()
for file, line, callee, arg in samples:
    file_name = Path(file).name
    print(f'{file_name}:{line} {callee}(...)')
    print(f'  {arg}...')

conn.close()
