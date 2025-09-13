"""Performance Analyzer - Database-Driven Implementation.

Detects performance anti-patterns using indexed database data.
NO AST TRAVERSAL. Just efficient SQL queries.

This rule follows the TRUE golden standard:
1. Query the database for pre-indexed data
2. Process results with simple logic  
3. Return findings

Detects:
- Database queries in loops (N+1 problems)
- Expensive operations in loops (file I/O, HTTP requests)
- Inefficient string concatenation in loops
"""

import sqlite3
from typing import List, Dict, Any, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_performance_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect performance anti-patterns using indexed data.
    
    Main entry point that delegates to specific detectors.
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # Run each performance check
        findings.extend(_find_queries_in_loops(cursor))
        findings.extend(_find_expensive_operations_in_loops(cursor))
        findings.extend(_find_inefficient_string_concat(cursor))
        findings.extend(_find_synchronous_io_patterns(cursor))
        findings.extend(_find_unbounded_operations(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# CHECK 1: Database Queries in Loops (N+1 Problem)
# ============================================================================

def _find_queries_in_loops(cursor) -> List[StandardFinding]:
    """Find database queries executed inside loops.
    
    The N+1 query problem is one of the most common performance killers.
    Instead of 1 query to fetch all data, the code executes N queries in a loop.
    """
    findings = []
    
    # Database operation patterns
    db_operations = [
        # SQL operations
        'query', 'execute', 'fetch', 'fetchone', 'fetchall', 'fetchmany',
        'select', 'insert', 'update', 'delete',
        
        # ORM operations
        'find', 'findOne', 'findMany', 'findAll', 'findUnique', 'findFirst',
        'create', 'save', 'update', 'upsert', 'delete', 'deleteMany',
        'filter', 'filter_by', 'get', 'all', 'first', 'one',
        
        # MongoDB
        'find_one', 'find_one_and_update', 'insert_one', 'update_one',
        'delete_one', 'aggregate', 'count_documents',
        
        # Prisma/Sequelize/TypeORM
        'findMany', 'findByPk', 'findOrCreate', 'findAndCountAll',
        'createMany', 'updateMany', 'deleteMany'
    ]
    
    # Step 1: Find all loop blocks from control flow graph
    cursor.execute("""
        SELECT DISTINCT cb.file, cb.function_name, cb.start_line, cb.end_line
        FROM cfg_blocks cb
        WHERE cb.block_type IN ('loop', 'for_loop', 'while_loop', 'do_while')
           OR cb.condition_expr LIKE '%for%'
           OR cb.condition_expr LIKE '%while%'
        ORDER BY cb.file, cb.start_line
    """)
    
    loops = cursor.fetchall()
    
    # Step 2: For each loop, find database operations within its line range
    for file, function, loop_start, loop_end in loops:
        # Query for function calls within this loop's line range
        placeholders = ','.join(['?' for _ in db_operations])
        cursor.execute(f"""
            SELECT f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line >= ? 
              AND f.line <= ?
              AND f.callee_function IN ({placeholders})
            ORDER BY f.line
        """, [file, loop_start, loop_end] + db_operations)
        
        for line, operation, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='perf-query-in-loop',
                message=f'Database operation "{operation}" executed inside loop (N+1 problem)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='performance',
                snippet=f'{operation}({args[:50]}...)' if len(args) > 50 else f'{operation}({args})',
                fix_suggestion='Move query outside loop and use batch operations or JOINs',
                cwe_id='CWE-1050'  # Excessive Platform Resource Consumption
            ))
    
    # Step 3: Also check for array iteration methods with DB operations (JS/TS)
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('forEach', 'map', 'filter', 'reduce', 'some', 'every')
          AND EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f.file
                AND f2.caller_function = f.caller_function
                AND f2.callee_function IN ({})
          )
        ORDER BY f.file, f.line
    """.format(','.join(['?' for _ in db_operations])), db_operations)
    
    for file, line, method, _ in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-query-in-array-method',
            message=f'Database operations inside array.{method}() creates implicit loop',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='performance',
            snippet=f'array.{method}() with DB operations',
            fix_suggestion='Fetch all data first, then process with array methods',
            cwe_id='CWE-1050'
        ))
    
    return findings


# ============================================================================
# CHECK 2: Expensive Operations in Loops
# ============================================================================

def _find_expensive_operations_in_loops(cursor) -> List[StandardFinding]:
    """Find expensive operations that should be moved outside loops.
    
    Detects file I/O, network requests, regex compilation, and other
    expensive operations that shouldn't be repeated in loops.
    """
    findings = []
    
    # Expensive operations to detect
    expensive_ops = {
        # File I/O
        'open': ('File I/O in loop', 'CRITICAL', 'Open file once outside loop'),
        'read': ('File read in loop', 'HIGH', 'Read file once and process data'),
        'write': ('File write in loop', 'HIGH', 'Batch writes or use buffering'),
        'readFile': ('File read in loop', 'HIGH', 'Read file once outside loop'),
        'writeFile': ('File write in loop', 'HIGH', 'Batch writes outside loop'),
        
        # Network operations
        'fetch': ('HTTP request in loop', 'CRITICAL', 'Use batch API or Promise.all()'),
        'axios': ('HTTP request in loop', 'CRITICAL', 'Use concurrent requests'),
        'request': ('HTTP request in loop', 'CRITICAL', 'Batch requests or use async'),
        'get': ('HTTP GET in loop', 'CRITICAL', 'Use batch endpoint'),
        'post': ('HTTP POST in loop', 'CRITICAL', 'Send batch request'),
        
        # Regex compilation
        'compile': ('Regex compilation in loop', 'HIGH', 'Compile regex once outside loop'),
        're.compile': ('Regex compilation in loop', 'HIGH', 'Move compilation outside loop'),
        'RegExp': ('Regex creation in loop', 'HIGH', 'Create RegExp once and reuse'),
        
        # Sleep/delays
        'sleep': ('Sleep in loop', 'CRITICAL', 'Use async/await or event-driven approach'),
        'time.sleep': ('Sleep in loop', 'CRITICAL', 'Blocks execution - use async'),
        'setTimeout': ('Timeout in loop', 'HIGH', 'Consider Promise-based delays'),
        
        # Cryptographic operations
        'hash': ('Hashing in loop', 'MEDIUM', 'Consider batch hashing if possible'),
        'encrypt': ('Encryption in loop', 'MEDIUM', 'Batch encrypt if possible'),
        'bcrypt': ('bcrypt in loop', 'CRITICAL', 'bcrypt is CPU-intensive - avoid loops'),
    }
    
    # Find loops and check for expensive operations
    cursor.execute("""
        SELECT DISTINCT cb.file, cb.start_line, cb.end_line
        FROM cfg_blocks cb
        WHERE cb.block_type IN ('loop', 'for_loop', 'while_loop')
    """)
    
    loops = cursor.fetchall()
    
    for file, loop_start, loop_end in loops:
        # Find expensive function calls within loop
        op_names = list(expensive_ops.keys())
        placeholders = ','.join(['?' for _ in op_names])
        
        cursor.execute(f"""
            SELECT f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line >= ?
              AND f.line <= ?
              AND f.callee_function IN ({placeholders})
            ORDER BY f.line
        """, [file, loop_start, loop_end] + op_names)
        
        for line, operation, args in cursor.fetchall():
            if operation in expensive_ops:
                desc, severity, suggestion = expensive_ops[operation]
                
                findings.append(StandardFinding(
                    rule_name='perf-expensive-in-loop',
                    message=desc,
                    file_path=file,
                    line=line,
                    severity=Severity[severity],
                    category='performance',
                    snippet=f'{operation}() in loop',
                    fix_suggestion=suggestion,
                    cwe_id='CWE-1050'
                ))
    
    return findings


# ============================================================================
# CHECK 3: Inefficient String Concatenation
# ============================================================================

def _find_inefficient_string_concat(cursor) -> List[StandardFinding]:
    """Find inefficient string concatenation in loops.
    
    String concatenation with + or += in loops is O(n²) because
    strings are immutable. Each concat creates a new string object.
    """
    findings = []
    
    # Find loops
    cursor.execute("""
        SELECT DISTINCT cb.file, cb.start_line, cb.end_line, cb.function_name
        FROM cfg_blocks cb
        WHERE cb.block_type IN ('loop', 'for_loop', 'while_loop')
    """)
    
    loops = cursor.fetchall()
    
    for file, loop_start, loop_end, function in loops:
        # Find string concatenation assignments within loop
        cursor.execute("""
            SELECT a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.line <= ?
              AND a.in_function = ?
              AND (
                  a.source_expr LIKE '%+%'
                  OR a.source_expr LIKE '%+=%'
                  OR a.source_expr LIKE '%concat%'
              )
              AND (
                  a.target_var LIKE '%str%'
                  OR a.target_var LIKE '%text%'
                  OR a.target_var LIKE '%result%'
                  OR a.target_var LIKE '%output%'
                  OR a.source_expr LIKE '"%'
                  OR a.source_expr LIKE "'%"
              )
            ORDER BY a.line
        """, [file, loop_start, loop_end, function])
        
        for line, var_name, expr in cursor.fetchall():
            # Check if this looks like string concatenation
            if '+' in expr and ('"' in expr or "'" in expr):
                findings.append(StandardFinding(
                    rule_name='perf-string-concat-loop',
                    message=f'Inefficient string concatenation "{var_name} += ..." in loop (O(n²) complexity)',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='performance',
                    snippet=f'{var_name} += ... in loop',
                    fix_suggestion='Use list.append() in loop, then "".join(list) after loop (O(n))',
                    cwe_id='CWE-1050'
                ))
    
    # Also check for JavaScript/TypeScript string concatenation
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%+=%'
          AND (a.target_var LIKE '%str%' OR a.target_var LIKE '%String%' OR a.target_var LIKE '%text%')
          AND EXISTS (
              SELECT 1 FROM cfg_blocks cb
              WHERE cb.file = a.file
                AND a.line >= cb.start_line
                AND a.line <= cb.end_line
                AND cb.block_type LIKE '%loop%'
          )
    """)
    
    for file, line, var_name, _ in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-string-concat-loop',
            message=f'String concatenation "{var_name} += ..." in loop degrades performance',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='performance',
            snippet=f'{var_name} += ... in loop',
            fix_suggestion='Use array.push() in loop, then array.join("") after',
            cwe_id='CWE-1050'
        ))
    
    return findings


# ============================================================================
# CHECK 4: Synchronous I/O in Async Context
# ============================================================================

def _find_synchronous_io_patterns(cursor) -> List[StandardFinding]:
    """Find synchronous I/O operations that block the event loop.
    
    In async contexts (Node.js, Python asyncio), synchronous I/O
    blocks the entire event loop, affecting all concurrent operations.
    """
    findings = []
    
    # Synchronous operations that should be async
    sync_operations = {
        # Node.js/JavaScript
        'readFileSync': 'Use fs.readFile() or fs.promises.readFile()',
        'writeFileSync': 'Use fs.writeFile() or fs.promises.writeFile()',
        'existsSync': 'Use fs.exists() or fs.promises.access()',
        'mkdirSync': 'Use fs.mkdir() or fs.promises.mkdir()',
        'readdirSync': 'Use fs.readdir() or fs.promises.readdir()',
        'statSync': 'Use fs.stat() or fs.promises.stat()',
        'unlinkSync': 'Use fs.unlink() or fs.promises.unlink()',
        'execSync': 'Use exec() with callbacks or promisify',
        'spawnSync': 'Use spawn() with event handlers',
        
        # Python
        'time.sleep': 'Use asyncio.sleep() in async functions',
        'requests.get': 'Use aiohttp or httpx for async requests',
        'requests.post': 'Use aiohttp or httpx for async requests',
        'open': 'Use aiofiles for async file operations',
    }
    
    # Find synchronous operations
    op_names = list(sync_operations.keys())
    placeholders = ','.join(['?' for _ in op_names])
    
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.caller_function
        FROM function_call_args f
        WHERE f.callee_function IN ({placeholders})
        ORDER BY f.file, f.line
    """, op_names)
    
    for file, line, operation, caller in cursor.fetchall():
        # Check if in async context (function name contains async/await indicators)
        is_async_context = False
        if caller and ('async' in caller.lower() or 'await' in caller.lower() or 
                       'promise' in caller.lower() or 'callback' in caller.lower()):
            is_async_context = True
        
        severity = Severity.CRITICAL if is_async_context else Severity.HIGH
        
        findings.append(StandardFinding(
            rule_name='perf-sync-io',
            message=f'Synchronous operation "{operation}" blocks event loop',
            file_path=file,
            line=line,
            severity=severity,
            category='performance',
            snippet=f'{operation}()',
            fix_suggestion=sync_operations.get(operation, 'Use async alternative'),
            cwe_id='CWE-1050'
        ))
    
    return findings


# ============================================================================
# CHECK 5: Unbounded Operations
# ============================================================================

def _find_unbounded_operations(cursor) -> List[StandardFinding]:
    """Find operations without proper limits that could cause memory issues.
    
    Detects:
    - Database queries without LIMIT
    - Array operations on unbounded data
    - Recursive operations without depth limits
    """
    findings = []
    
    # Check for database queries without limits
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('find', 'findMany', 'findAll', 'select', 'query', 'all')
          AND f.argument_expr NOT LIKE '%limit%'
          AND f.argument_expr NOT LIKE '%take%'
          AND f.argument_expr NOT LIKE '%first%'
          AND f.argument_expr NOT LIKE '%findOne%'
          AND f.argument_expr NOT LIKE '%findUnique%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, operation, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-unbounded-query',
            message=f'Database query "{operation}" without limit could return excessive data',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='performance',
            snippet=f'{operation}() without limit',
            fix_suggestion='Add pagination with limit/offset or use streaming',
            cwe_id='CWE-770'  # Allocation of Resources Without Limits
        ))
    
    # Check for readFile on potentially large files
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('readFile', 'readFileSync', 'read')
          AND (
              f.argument_expr LIKE '%.log%'
              OR f.argument_expr LIKE '%.csv%'
              OR f.argument_expr LIKE '%.json%'
              OR f.argument_expr LIKE '%.xml%'
          )
    """)
    
    for file, line, file_arg in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-large-file-read',
            message=f'Reading potentially large file entirely into memory',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='performance',
            snippet=f'readFile({file_arg[:30]}...)',
            fix_suggestion='Use streaming reads for large files (createReadStream/readline)',
            cwe_id='CWE-770'
        ))
    
    # Check for array operations that could be expensive
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.callee_function IN ('sort', 'reverse')
          AND EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f.file
                AND f2.line = f.line - 1
                AND f2.callee_function IN ('find', 'findMany', 'findAll', 'query')
          )
    """)
    
    for file, line, operation in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='perf-memory-intensive',
            message=f'Sorting/reversing large dataset in memory',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='performance',
            snippet=f'Large dataset.{operation}()',
            fix_suggestion='Sort at database level with ORDER BY clause',
            cwe_id='CWE-770'
        ))
    
    return findings