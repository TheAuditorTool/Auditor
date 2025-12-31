"""Deeper query for alias tracking."""
import sqlite3

conn = sqlite3.connect('.pf/graphs.db')
c = conn.cursor()

# Let's look at ALL assignment edges and understand the pattern
c.execute("""
    SELECT source, target
    FROM edges
    WHERE type = 'assignment'
    LIMIT 30
""")
print('=== ALL ASSIGNMENT EDGES (first 30) ===')
for row in c.fetchall():
    # Get just the variable part (after last ::)
    src_parts = row[0].split('::')
    tgt_parts = row[1].split('::')
    src_var = src_parts[-1] if src_parts else row[0]
    tgt_var = tgt_parts[-1] if tgt_parts else row[1]
    src_func = src_parts[1] if len(src_parts) > 2 else 'global'
    tgt_func = tgt_parts[1] if len(tgt_parts) > 2 else 'global'
    print(f'{src_func}::{src_var} -> {tgt_func}::{tgt_var}')

print()

# Check if there's cross-function data flow via parameter_binding
c.execute("""
    SELECT e1.source as caller_var, e1.target as param, e2.source as param_src, e2.target as internal_var
    FROM edges e1
    JOIN edges e2 ON e1.target LIKE '%::' || e2.source || '::%'
    WHERE e1.type = 'parameter_binding'
      AND e2.type = 'assignment'
    LIMIT 10
""")
print('=== CROSS-FUNCTION FLOW (param binding -> internal assignment) ===')
for row in c.fetchall():
    print(row)

print()

# Let's check what happens with field access (obj.field patterns)
c.execute("""
    SELECT source, target
    FROM edges
    WHERE type = 'assignment'
      AND (source LIKE '%.data%' OR target LIKE '%.data%')
    LIMIT 20
""")
print('=== FIELD ACCESS ASSIGNMENTS (.data patterns) ===')
for row in c.fetchall():
    src_var = row[0].split('::')[-1]
    tgt_var = row[1].split('::')[-1]
    print(f'{src_var} -> {tgt_var}')

conn.close()

# Check repo_index for how env vars are tracked
print('\n' + '='*60)
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

c.execute("SELECT * FROM env_var_usage LIMIT 10")
print('\n=== ENV VAR USAGE ===')
for row in c.fetchall():
    print(row)

conn.close()
