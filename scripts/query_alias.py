"""Query database for alias tracking capabilities."""
import sqlite3

# Check repo_index.db
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

# Look at field assignments with property_path
c.execute("""
    SELECT file, line, target_var, source_expr, in_function, property_path
    FROM assignments
    WHERE property_path IS NOT NULL AND property_path != ''
    LIMIT 15
""")
print('=== FIELD ASSIGNMENTS WITH PROPERTY PATH ===')
for row in c.fetchall():
    f = row[0].split('/')[-1] if row[0] else '?'
    src = str(row[3])[:40] if row[3] else '?'
    print(f'{f}:{row[1]} | {row[2]}.{row[5]} = {src} | in {row[4]}')

print()

# Check assignment_source_vars - tracks where assignment values come from
c.execute("SELECT * FROM assignment_source_vars LIMIT 10")
print('=== ASSIGNMENT_SOURCE_VARS SAMPLE ===')
for row in c.fetchall():
    print(row)

print()

# Look for variable-to-variable assignments (B = A pattern)
c.execute("""
    SELECT file, line, target_var, source_expr, in_function
    FROM assignments
    WHERE source_expr NOT LIKE '%(%'
      AND source_expr NOT LIKE '%{%'
      AND source_expr NOT LIKE '%[%'
      AND source_expr NOT LIKE '%"%'
      AND source_expr NOT LIKE "%'%"
      AND LENGTH(source_expr) < 30
    LIMIT 20
""")
print('=== VARIABLE-TO-VARIABLE ASSIGNMENTS (B = A pattern) ===')
for row in c.fetchall():
    f = row[0].split('/')[-1] if row[0] else '?'
    print(f'{f}:{row[1]} | {row[2]} = {row[3]} | in {row[4]}')

conn.close()

# Now check graphs.db for edges between variables
print('\n' + '='*60)
conn = sqlite3.connect('.pf/graphs.db')
c = conn.cursor()

# Look for assignment edges where source looks like a simple variable
c.execute("""
    SELECT source, target
    FROM edges
    WHERE type = 'assignment'
      AND source NOT LIKE '%string_literal%'
      AND source NOT LIKE '%number_literal%'
      AND source NOT LIKE '%array_literal%'
      AND source NOT LIKE '%object_literal%'
      AND source NOT LIKE '%.%'
    LIMIT 20
""")
print('\n=== SIMPLE VAR ASSIGNMENT EDGES (A -> B) ===')
for row in c.fetchall():
    src = row[0].split('::')[-1] if '::' in row[0] else row[0]
    tgt = row[1].split('::')[-1] if '::' in row[1] else row[1]
    print(f'{src} -> {tgt}')

conn.close()
