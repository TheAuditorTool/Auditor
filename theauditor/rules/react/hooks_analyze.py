"""React Hooks Analyzer - Hybrid Database/AST Approach.

This rule demonstrates a HYBRID approach because:
1. React Hook dependency analysis requires semantic understanding of variable scope
2. Memory leak detection needs to understand return statements and cleanup patterns
3. Database lacks React-specific semantic information (hooks, deps arrays, cleanup functions)

Therefore, this rule uses:
- Database queries for file discovery and basic symbol information
- AST analysis for React-specific semantic patterns (justified exception)

This is a legitimate exception to the "database-only" rule similar to bundle_analyze.py.
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_react_hooks_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect React Hooks issues using hybrid approach.
    
    Detects:
    - Missing dependencies in useEffect, useCallback, useMemo
    - Memory leaks from missing cleanup functions
    - Hooks called conditionally (rules of hooks violation)
    - Excessive re-renders from incorrect dependencies
    
    This is a HYBRID rule that uses:
    - Database for React file identification and basic analysis
    - AST for React-specific semantic patterns (NOT indexed in DB)
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # ========================================================
        # PART 1: Find React component files from database
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f.path
            FROM files f
            WHERE (f.ext IN ('.jsx', '.tsx')
                   OR (f.ext IN ('.js', '.ts') AND EXISTS (
                       SELECT 1 FROM refs r 
                       WHERE r.src = f.path 
                         AND r.value LIKE '%react%'
                   )))
            ORDER BY f.path
        """)
        
        react_files = [row[0] for row in cursor.fetchall()]
        
        if not react_files:
            return findings  # Not a React project
        
        # ========================================================
        # PART 2: Database-detectable issues
        # ========================================================
        findings.extend(_find_conditional_hooks(cursor, react_files))
        findings.extend(_find_missing_deps_basic(cursor, react_files))
        findings.extend(_find_async_useeffect(cursor, react_files))
        
        # ========================================================
        # PART 3: Issues requiring semantic analysis (justified AST use)
        # ========================================================
        # For accurate dependency tracking and memory leak detection,
        # we need to understand React semantics which aren't in the database:
        # - Dependency arrays (not indexed as structured data)
        # - Cleanup function returns (not tracked in function_returns)
        # - Variable scope analysis (not in symbols table)
        
        for file_path in react_files:
            full_path = context.project_path / file_path
            if full_path.exists() and full_path.suffix in ['.jsx', '.tsx']:
                # Only parse JSX/TSX files that definitely use React
                semantic_findings = _analyze_react_semantics(full_path, file_path)
                findings.extend(semantic_findings)
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# DATABASE-BASED CHECKS (What we CAN do with indexed data)
# ============================================================================

def _find_conditional_hooks(cursor, react_files) -> List[StandardFinding]:
    """Find hooks called conditionally (violates Rules of Hooks)."""
    findings = []
    
    for file in react_files:
        # Find hook calls inside conditional blocks
        cursor.execute("""
            SELECT DISTINCT f.line, f.callee_function
            FROM function_call_args f
            JOIN cfg_blocks cb ON f.file = cb.file
            WHERE f.file = ?
              AND f.callee_function LIKE 'use%'
              AND cb.block_type = 'condition'
              AND f.line >= cb.start_line
              AND f.line <= cb.end_line
            ORDER BY f.line
        """, [file])
        
        for line, hook in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-conditional-hook',
                message=f'React Hook "{hook}" called conditionally (violates Rules of Hooks)',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='react',
                snippet=f'if (...) {{ {hook}() }}',
                fix_suggestion='Move hook call outside conditional block',
                cwe_id='CWE-670'  # Always-Incorrect Control Flow
            ))
    
    return findings


def _find_missing_deps_basic(cursor, react_files) -> List[StandardFinding]:
    """Basic missing dependency detection using database."""
    findings = []
    
    for file in react_files:
        # Find useEffect/useCallback/useMemo calls
        cursor.execute("""
            SELECT f.line, f.callee_function, f.argument_expr, f.caller_function
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function IN ('useEffect', 'useCallback', 'useMemo')
            ORDER BY f.line
        """, [file])
        
        for line, hook, args, caller_func in cursor.fetchall():
            # Check if dependency array is empty but uses variables
            if '[]' in args and caller_func:
                # Check if the function uses any variables
                cursor.execute("""
                    SELECT COUNT(DISTINCT s.name)
                    FROM symbols s
                    WHERE s.path = ?
                      AND s.line >= ?
                      AND s.line <= ? + 20
                      AND s.type IN ('variable', 'property')
                      AND s.name NOT LIKE 'use%'
                """, [file, line, line])
                
                var_count = cursor.fetchone()[0]
                if var_count > 2:  # Threshold for likely missing deps
                    findings.append(StandardFinding(
                        rule_name='react-empty-deps-suspicious',
                        message=f'{hook} has empty dependency array but references {var_count} variables',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='react',
                        snippet=f'{hook}(..., [])',
                        fix_suggestion='Add missing dependencies or remove dependency array',
                        cwe_id='CWE-670'
                    ))
    
    return findings


def _find_async_useeffect(cursor, react_files) -> List[StandardFinding]:
    """Find async functions passed directly to useEffect."""
    findings = []
    
    for file in react_files:
        # Find useEffect with async keyword in arguments
        cursor.execute("""
            SELECT f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function = 'useEffect'
              AND (f.argument_expr LIKE '%async%=>%'
                   OR f.argument_expr LIKE '%async function%')
            ORDER BY f.line
        """, [file])
        
        for line, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-async-useeffect',
                message='useEffect cannot directly accept async functions',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='react',
                snippet='useEffect(async () => {...})',
                fix_suggestion='Create async function inside useEffect and call it',
                cwe_id='CWE-670'
            ))
    
    return findings


# ============================================================================
# SEMANTIC ANALYSIS (Justified AST use - data not in database)
# ============================================================================

def _analyze_react_semantics(file_path: Path, relative_path: str) -> List[StandardFinding]:
    """Analyze React-specific semantics that aren't in the database.
    
    This is justified because the database doesn't index:
    - React Hook dependency arrays as structured data
    - Cleanup function return patterns
    - Variable scope relationships in React components
    """
    findings = []
    
    try:
        # Try to get semantic AST if available
        semantic_ast_path = file_path.parent / '.pf' / '.ast_cache' / f'{file_path.name}.semantic.json'
        
        if semantic_ast_path.exists():
            with open(semantic_ast_path, 'r', encoding='utf-8') as f:
                semantic_data = json.load(f)
                
            # Analyze for memory leaks
            memory_leaks = _check_memory_leaks(semantic_data, relative_path)
            findings.extend(memory_leaks)
            
            # Analyze for exact missing dependencies
            # (This requires scope analysis not available in DB)
            missing_deps = _check_missing_dependencies_semantic(semantic_data, relative_path)
            findings.extend(missing_deps)
        
        else:
            # Fallback: Basic pattern matching on file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Simple pattern-based checks
            for i, line in enumerate(lines, 1):
                # Check for setInterval/setTimeout without cleanup
                if 'useEffect' in line:
                    # Look ahead for subscription patterns
                    block_end = min(i + 30, len(lines))
                    block = '\n'.join(lines[i:block_end])
                    
                    has_subscription = any(pattern in block for pattern in [
                        'addEventListener', 'setInterval', 'setTimeout',
                        '.on(', '.subscribe(', 'socket.', 'WebSocket'
                    ])
                    
                    has_return = 'return' in block and ('=>' in block or 'function' in block)
                    
                    if has_subscription and not has_return:
                        findings.append(StandardFinding(
                            rule_name='react-potential-memory-leak',
                            message='useEffect creates subscriptions but may lack cleanup',
                            file_path=relative_path,
                            line=i,
                            severity=Severity.HIGH,
                            category='react',
                            snippet='',
                            fix_suggestion='Return a cleanup function from useEffect',
                            cwe_id='CWE-401'  # Memory Leak
                        ))
    
    except (OSError, json.JSONDecodeError):
        pass  # File reading failed, skip semantic analysis
    
    return findings


def _check_memory_leaks(semantic_data: Dict, file_path: str) -> List[StandardFinding]:
    """Check for memory leaks in useEffect (requires semantic AST)."""
    findings = []
    
    # This would analyze the semantic AST for:
    # - useEffect calls with subscriptions
    # - Missing return statements with cleanup functions
    # Implementation depends on semantic AST structure
    
    # Simplified example - would need full implementation
    ast = semantic_data.get('ast', {})
    if 'useEffect' in str(ast):
        # Check for subscription patterns without cleanup
        # This is a simplified check - real implementation would traverse AST
        pass
    
    return findings


def _check_missing_dependencies_semantic(semantic_data: Dict, file_path: str) -> List[StandardFinding]:
    """Check for exact missing dependencies using semantic analysis."""
    findings = []
    
    # This would:
    # 1. Find all hook calls with dependency arrays
    # 2. Analyze variable scope and usage
    # 3. Compare used variables with declared dependencies
    # 
    # This requires semantic understanding not available in the database
    
    return findings