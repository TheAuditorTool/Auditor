"""Generate database.md documentation from repo_index.db"""

import sqlite3
import os

def generate_database_docs():
    output = []
    output.append('# TheAuditor Database Schema Reference')
    output.append('')
    output.append('This document provides a complete reference of the database schema created by the indexer.')
    output.append('Use this to understand what data is available when writing security rules.')
    output.append('')
    output.append('## Quick Reference')
    output.append('')
    output.append('### Most Useful Tables for Rules')
    output.append('- **function_call_args**: All function calls with arguments (jwt.sign, bcrypt.hash, etc.)')
    output.append('- **assignments**: All variable assignments (secrets, configs, tokens)')
    output.append('- **symbols**: All code symbols (functions, classes, properties)')
    output.append('- **api_endpoints**: REST API endpoints with methods and paths')
    output.append('- **sql_queries**: All SQL query strings found')
    output.append('- **config_files**: Parsed configuration files')
    output.append('')
    output.append('---')
    output.append('')

    # Test with PlantFlow database first (it has data)
    db_path = 'C:/Users/santa/Desktop/PlantFlow/.pf/repo_index.db'
    if not os.path.exists(db_path):
        db_path = 'C:/Users/santa/Desktop/TheAuditor/.pf/repo_index.db'

    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [t[0] for t in cursor.fetchall() if t[0] != 'sqlite_sequence']
        
        output.append('## Database Tables')
        output.append('')
        
        for table in tables:
            output.append(f'### Table: `{table}`')
            output.append('')
            
            # Get schema
            cursor.execute(f'PRAGMA table_info({table})')
            columns = cursor.fetchall()
            
            output.append('#### Schema')
            output.append('| Column | Type | Required | Default | Description |')
            output.append('|--------|------|----------|---------|-------------|')
            
            for col in columns:
                cid, name, dtype, notnull, default, pk = col
                required = 'Yes' if notnull else 'No'
                default = default if default else 'NULL'
                pk_mark = ' (PK)' if pk else ''
                desc = ''
                
                # Add descriptions for common columns
                if 'file' in name or 'path' in name:
                    desc = 'File path relative to project root'
                elif name == 'line':
                    desc = 'Line number in source file'
                elif name == 'col' or name == 'column':
                    desc = 'Column position in line'
                elif 'function' in name and 'callee' in name:
                    desc = 'Function being called'
                elif 'function' in name and 'caller' in name:
                    desc = 'Function making the call'
                elif 'var' in name or 'target' in name:
                    desc = 'Variable name'
                elif 'expr' in name or 'source' in name:
                    desc = 'Source expression/code'
                elif name == 'type':
                    desc = 'Symbol/entity type'
                elif name == 'sha256':
                    desc = 'File content hash'
                elif name == 'bytes' or name == 'size':
                    desc = 'File size in bytes'
                elif name == 'loc':
                    desc = 'Lines of code'
                elif name == 'ext':
                    desc = 'File extension'
                elif 'arg' in name:
                    desc = 'Function argument'
                elif name == 'severity':
                    desc = 'Issue severity level'
                
                output.append(f'| {name}{pk_mark} | {dtype} | {required} | {default} | {desc} |')
            
            output.append('')
            
            # Get row count
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            row_count = cursor.fetchone()[0]
            output.append(f'**Total Records**: {row_count:,}')
            output.append('')
            
            # Get sample data
            output.append('#### Sample Data')
            output.append('```sql')
            cursor.execute(f'SELECT * FROM {table} LIMIT 3')
            rows = cursor.fetchall()
            if rows:
                # Show column names
                col_names = [col[1] for col in columns]
                output.append('-- Columns: ' + ', '.join(col_names))
                output.append('-- Sample rows:')
                for i, row in enumerate(rows, 1):
                    # Truncate long values
                    row_str = []
                    for val in row:
                        s = str(val) if val is not None else 'NULL'
                        if len(s) > 50:
                            s = s[:47] + '...'
                        row_str.append(s)
                    output.append(f'-- Row {i}: ' + ' | '.join(row_str))
            else:
                output.append('-- No data in this table')
            output.append('```')
            output.append('')
            
            # Add useful queries for specific tables
            if table == 'function_call_args':
                output.append('#### Useful Queries')
                output.append('```sql')
                output.append('-- Find JWT sign/verify calls')
                output.append("SELECT * FROM function_call_args WHERE callee_function LIKE '%jwt%';")
                output.append('')
                output.append('-- Find bcrypt/crypto calls')
                output.append("SELECT * FROM function_call_args WHERE callee_function LIKE '%crypt%';")
                output.append('')
                output.append('-- Find SQL query executions')
                output.append("SELECT * FROM function_call_args WHERE callee_function IN ('query', 'execute', 'run');")
                output.append('```')
                output.append('')
            elif table == 'assignments':
                output.append('#### Useful Queries')
                output.append('```sql')
                output.append('-- Find secret/key assignments')
                output.append("SELECT * FROM assignments WHERE target_var LIKE '%secret%' OR target_var LIKE '%key%';")
                output.append('')
                output.append('-- Find hardcoded values')
                output.append("SELECT * FROM assignments WHERE source_expr LIKE '\"%\"' OR source_expr LIKE \"'%'\";")
                output.append('```')
                output.append('')
            elif table == 'sql_queries':
                output.append('#### Useful Queries')
                output.append('```sql')
                output.append('-- Find queries with string concatenation (SQL injection risk)')
                output.append("SELECT * FROM sql_queries WHERE query_template LIKE '%' || '%';")
                output.append('')
                output.append('-- Find SELECT * queries')
                output.append("SELECT * FROM sql_queries WHERE query_template LIKE 'SELECT * %';")
                output.append('```')
                output.append('')
        
        output.append('---')
        output.append('')
        output.append('## Common Query Patterns for Rules')
        output.append('')
        output.append('### Authentication & JWT')
        output.append('```sql')
        output.append('-- Find all JWT operations')
        output.append("SELECT * FROM function_call_args")
        output.append("WHERE callee_function IN ('jwt.sign', 'jwt.verify', 'jsonwebtoken.sign', 'jsonwebtoken.verify');")
        output.append('')
        output.append('-- Find weak secrets')
        output.append("SELECT * FROM assignments")
        output.append("WHERE target_var LIKE '%SECRET%'")
        output.append("  AND LENGTH(source_expr) < 32;")
        output.append('```')
        output.append('')
        
        output.append('### SQL Injection')
        output.append('```sql')
        output.append('-- Find dynamic SQL construction')
        output.append("SELECT * FROM assignments")
        output.append("WHERE target_var LIKE '%query%'")
        output.append("  AND (source_expr LIKE '%+%' OR source_expr LIKE '%${%');")
        output.append('```')
        output.append('')
        
        output.append('### Cryptography')
        output.append('```sql')
        output.append('-- Find weak hashing algorithms')
        output.append("SELECT * FROM function_call_args")
        output.append("WHERE callee_function LIKE '%md5%' OR callee_function LIKE '%sha1%';")
        output.append('```')
        output.append('')
        
        output.append('### API Security')
        output.append('```sql')
        output.append('-- Find unprotected endpoints')
        output.append("SELECT * FROM api_endpoints")
        output.append("WHERE auth_required = 0 OR auth_required IS NULL;")
        output.append('```')
        output.append('')
        
        conn.close()
        
        output.append('---')
        output.append('')
        output.append('## Notes for Rule Writers')
        output.append('')
        output.append('1. **Always query the database first** - The indexer has already parsed everything')
        output.append('2. **Use indexed data** - Don\'t re-parse ASTs or files')
        output.append('3. **Join tables when needed** - Combine data from multiple tables')
        output.append('4. **Check for NULL values** - Not all columns are always populated')
        output.append('5. **Use LIKE for patterns** - SQL LIKE operator is powerful for matching')
        output.append('')
        output.append('## Example Rule Using Database')
        output.append('')
        output.append('```python')
        output.append('def find_jwt_issues(context: StandardRuleContext) -> List[StandardFinding]:')
        output.append('    """Find JWT vulnerabilities using indexed data."""')
        output.append('    ')
        output.append('    conn = sqlite3.connect(context.db_path)')
        output.append('    cursor = conn.cursor()')
        output.append('    findings = []')
        output.append('    ')
        output.append('    # Query for JWT sign calls')
        output.append('    cursor.execute("""')
        output.append('        SELECT file, line, argument_expr, param_name')
        output.append('        FROM function_call_args')
        output.append('        WHERE callee_function IN (\'jwt.sign\', \'jsonwebtoken.sign\')')
        output.append('    """)')
        output.append('    ')
        output.append('    for row in cursor.fetchall():')
        output.append('        file_path, line, arg_expr, param = row')
        output.append('        ')
        output.append('        # Check for weak secret (usually 2nd argument)')
        output.append('        if param == \'arg1\' and len(arg_expr) < 32:')
        output.append('            findings.append(StandardFinding(')
        output.append('                rule_name=\'jwt-weak-secret\',')
        output.append('                message=f\'Weak JWT secret: {len(arg_expr)} chars\',')
        output.append('                file_path=file_path,')
        output.append('                line=line,')
        output.append('                severity=Severity.CRITICAL')
        output.append('            ))')
        output.append('    ')
        output.append('    conn.close()')
        output.append('    return findings')
        output.append('```')

    return '\n'.join(output)

if __name__ == '__main__':
    content = generate_database_docs()
    with open('C:/Users/santa/Desktop/TheAuditor/database.md', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Generated database.md ({len(content):,} bytes)')