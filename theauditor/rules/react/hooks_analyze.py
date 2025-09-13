"""React Hooks Analyzer - Pure Database Implementation.

This module detects React Hooks violations using ONLY indexed database data.
NO AST TRAVERSAL. NO FILE I/O. Just efficient SQL queries.

Detects:
- Missing dependencies in useEffect, useCallback, useMemo
- Memory leaks from missing cleanup functions
- Hooks called conditionally (rules of hooks violation)
- Excessive re-renders from incorrect dependencies
- Stale closure issues
- Custom hooks violations
- Performance anti-patterns
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_react_hooks_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect React Hooks issues using indexed database data.
    
    Returns:
        List of React Hooks violations and issues
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, verify this is a React project
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
        
        # Run all React Hooks checks
        findings.extend(_find_conditional_hooks(cursor, react_files))
        findings.extend(_find_missing_deps(cursor, react_files))
        findings.extend(_find_async_useeffect(cursor, react_files))
        findings.extend(_find_memory_leaks(cursor, react_files))
        findings.extend(_find_stale_closures(cursor, react_files))
        findings.extend(_find_custom_hook_violations(cursor, react_files))
        findings.extend(_find_excessive_rerenders(cursor, react_files))
        findings.extend(_find_hooks_after_return(cursor, react_files))
        findings.extend(_find_multiple_state_updates(cursor, react_files))
        findings.extend(_find_missing_usememo(cursor, react_files))
        findings.extend(_find_unsafe_refs(cursor, react_files))
        findings.extend(_find_effect_race_conditions(cursor, react_files))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# CHECK 1: Conditional Hooks (Rules of Hooks Violation)
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
              AND cb.block_type IN ('condition', 'loop')
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
                cwe_id='CWE-670'
            ))
        
        # Also check for early returns before hooks
        cursor.execute("""
            SELECT f.line, f.callee_function
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function LIKE 'use%'
              AND EXISTS (
                  SELECT 1 FROM function_returns r
                  WHERE r.file = f.file
                    AND r.function_name = f.caller_function
                    AND r.line < f.line
              )
            ORDER BY f.line
        """, [file])
        
        for line, hook in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-hook-after-return',
                message=f'React Hook "{hook}" potentially called after early return',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='react',
                snippet=f'{hook}() after conditional return',
                fix_suggestion='Move all hooks before any conditional returns',
                cwe_id='CWE-670'
            ))
    
    return findings


# ============================================================================
# CHECK 2: Missing Dependencies
# ============================================================================

def _find_missing_deps(cursor, react_files) -> List[StandardFinding]:
    """Find hooks with missing dependencies using database analysis."""
    findings = []
    
    for file in react_files:
        # Find useEffect/useCallback/useMemo with empty deps but using variables
        cursor.execute("""
            SELECT f.line, f.callee_function, f.argument_expr, f.caller_function
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function IN ('useEffect', 'useCallback', 'useMemo')
              AND f.argument_expr LIKE '%[]%'
            ORDER BY f.line
        """, [file])
        
        for line, hook, args, caller_func in cursor.fetchall():
            # Check for variables used within proximity of the hook
            cursor.execute("""
                SELECT DISTINCT s.name
                FROM symbols s
                WHERE s.path = ?
                  AND s.line >= ?
                  AND s.line <= ? + 10
                  AND s.type IN ('variable', 'property')
                  AND s.name NOT LIKE 'use%'
                  AND s.name NOT IN ('console', 'window', 'document', 'Math')
                LIMIT 10
            """, [file, line, line])
            
            used_vars = [row[0] for row in cursor.fetchall()]
            
            if len(used_vars) > 2:
                findings.append(StandardFinding(
                    rule_name='react-missing-dependencies',
                    message=f'{hook} has empty deps but uses: {", ".join(used_vars[:3])}...',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='react',
                    snippet=f'{hook}(() => {{...}}, [])',
                    fix_suggestion=f'Add dependencies: [{", ".join(used_vars[:3])}]',
                    cwe_id='CWE-670'
                ))
        
        # Check for props/state usage without deps
        cursor.execute("""
            SELECT f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function IN ('useEffect', 'useCallback', 'useMemo')
              AND (f.argument_expr LIKE '%props.%' 
                   OR f.argument_expr LIKE '%state.%'
                   OR f.argument_expr LIKE '%setState%')
              AND f.argument_expr LIKE '%[]%'
            ORDER BY f.line
        """, [file])
        
        for line, hook, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-props-state-no-deps',
                message=f'{hook} uses props/state but has empty dependency array',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='react',
                snippet=f'{hook}(...props/state..., [])',
                fix_suggestion='Add props/state to dependency array',
                cwe_id='CWE-670'
            ))
    
    return findings


# ============================================================================
# CHECK 3: Async useEffect
# ============================================================================

def _find_async_useeffect(cursor, react_files) -> List[StandardFinding]:
    """Find async functions passed directly to useEffect."""
    findings = []
    
    for file in react_files:
        cursor.execute("""
            SELECT f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function = 'useEffect'
              AND (f.argument_expr LIKE '%async%=>%'
                   OR f.argument_expr LIKE '%async function%'
                   OR f.argument_expr LIKE '%async ()%')
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
# CHECK 4: Memory Leaks
# ============================================================================

def _find_memory_leaks(cursor, react_files) -> List[StandardFinding]:
    """Find potential memory leaks from missing cleanup functions."""
    findings = []
    
    for file in react_files:
        # Find useEffect with subscriptions but no cleanup
        cursor.execute("""
            SELECT DISTINCT f1.line, f1.caller_function
            FROM function_call_args f1
            WHERE f1.file = ?
              AND f1.callee_function = 'useEffect'
              AND EXISTS (
                  -- Has subscription patterns
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.line > f1.line
                    AND f2.line <= f1.line + 20
                    AND f2.callee_function IN (
                        'addEventListener', 'setInterval', 'setTimeout',
                        'subscribe', 'on', 'WebSocket', 'EventSource'
                    )
              )
              AND NOT EXISTS (
                  -- But no return statement
                  SELECT 1 FROM function_returns r
                  WHERE r.file = f1.file
                    AND r.line > f1.line
                    AND r.line <= f1.line + 20
                    AND r.function_name = f1.caller_function
              )
            ORDER BY f1.line
        """, [file])
        
        for line, func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-memory-leak',
                message='useEffect creates subscriptions but lacks cleanup function',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='react',
                snippet='useEffect with addEventListener/setInterval but no return',
                fix_suggestion='Return a cleanup function to remove listeners/clear timers',
                cwe_id='CWE-401'
            ))
        
        # Check for fetch without AbortController
        cursor.execute("""
            SELECT f1.line
            FROM function_call_args f1
            WHERE f1.file = ?
              AND f1.callee_function = 'useEffect'
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.line > f1.line
                    AND f2.line <= f1.line + 20
                    AND f2.callee_function IN ('fetch', 'axios')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM symbols s
                  WHERE s.path = f1.file
                    AND s.line >= f1.line
                    AND s.line <= f1.line + 20
                    AND s.name LIKE '%AbortController%'
              )
            ORDER BY f1.line
        """, [file])
        
        for (line,) in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-fetch-no-abort',
                message='Fetch in useEffect without AbortController',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='react',
                snippet='useEffect with fetch but no AbortController',
                fix_suggestion='Use AbortController to cancel requests on unmount',
                cwe_id='CWE-401'
            ))
    
    return findings


# ============================================================================
# CHECK 5: Stale Closures
# ============================================================================

def _find_stale_closures(cursor, react_files) -> List[StandardFinding]:
    """Find potential stale closure issues."""
    findings = []
    
    for file in react_files:
        # Find setInterval/setTimeout in useEffect with state references
        cursor.execute("""
            SELECT DISTINCT f1.line, f1.callee_function
            FROM function_call_args f1
            WHERE f1.file = ?
              AND f1.callee_function IN ('setInterval', 'setTimeout')
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.callee_function = 'useEffect'
                    AND f1.line > f2.line
                    AND f1.line <= f2.line + 20
              )
              AND EXISTS (
                  SELECT 1 FROM symbols s
                  WHERE s.path = f1.file
                    AND s.line >= f1.line - 5
                    AND s.line <= f1.line + 5
                    AND (s.name LIKE '%state%' OR s.name LIKE '%State')
              )
            ORDER BY f1.line
        """, [file])
        
        for line, func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-stale-closure',
                message=f'{func} with state reference may cause stale closure',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='react',
                snippet=f'{func}(() => {{...state...}})',
                fix_suggestion='Use functional state updates or useRef for latest values',
                cwe_id='CWE-667'
            ))
    
    return findings


# ============================================================================
# CHECK 6: Custom Hook Violations
# ============================================================================

def _find_custom_hook_violations(cursor, react_files) -> List[StandardFinding]:
    """Find custom hooks that violate naming conventions or patterns."""
    findings = []
    
    for file in react_files:
        # Find functions starting with 'use' that don't call other hooks
        cursor.execute("""
            SELECT DISTINCT s.name, s.line
            FROM symbols s
            WHERE s.path = ?
              AND s.type = 'function'
              AND s.name LIKE 'use%'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f
                  WHERE f.file = s.path
                    AND f.caller_function = s.name
                    AND f.callee_function LIKE 'use%'
              )
            ORDER BY s.line
        """, [file])
        
        for name, line in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-invalid-custom-hook',
                message=f'Function "{name}" starts with "use" but doesn\'t call hooks',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='react',
                snippet=f'function {name}() {{...}}',
                fix_suggestion='Rename function or ensure it calls React hooks',
                cwe_id='CWE-1061'
            ))
        
        # Find hooks called outside components/custom hooks
        cursor.execute("""
            SELECT f.line, f.callee_function, f.caller_function
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function LIKE 'use%'
              AND f.caller_function NOT LIKE 'use%'
              AND f.caller_function NOT LIKE '%Component'
              AND f.caller_function NOT IN (
                  SELECT s.name FROM symbols s
                  WHERE s.path = f.file
                    AND s.type = 'function'
                    AND (s.name LIKE 'use%' OR s.name LIKE '%Component')
              )
            ORDER BY f.line
        """, [file])
        
        for line, hook, caller in cursor.fetchall():
            if caller and not caller.startswith('_'):  # Ignore private functions
                findings.append(StandardFinding(
                    rule_name='react-hook-outside-component',
                    message=f'Hook "{hook}" called outside React component/hook',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='react',
                    snippet=f'{hook}() in {caller}()',
                    fix_suggestion='Only call hooks from React components or custom hooks',
                    cwe_id='CWE-670'
                ))
    
    return findings


# ============================================================================
# CHECK 7: Excessive Re-renders
# ============================================================================

def _find_excessive_rerenders(cursor, react_files) -> List[StandardFinding]:
    """Find patterns that cause excessive re-renders."""
    findings = []
    
    for file in react_files:
        # Find inline object/array literals in dependency arrays
        cursor.execute("""
            SELECT f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function IN ('useEffect', 'useCallback', 'useMemo')
              AND (f.argument_expr LIKE '%[{%' 
                   OR f.argument_expr LIKE '%[[%'
                   OR f.argument_expr LIKE '%() => {%')
            ORDER BY f.line
        """, [file])
        
        for line, hook, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-inline-dependency',
                message=f'{hook} has inline object/function in dependency array',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='react',
                snippet=f'{hook}(..., [{{}}])',
                fix_suggestion='Extract object/function outside component or memoize',
                cwe_id='CWE-1050'
            ))
        
        # Find setState in render phase
        cursor.execute("""
            SELECT f.line, f.callee_function
            FROM function_call_args f
            WHERE f.file = ?
              AND (f.callee_function LIKE '%setState%' 
                   OR f.callee_function LIKE '%dispatch%')
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f.file
                    AND f2.callee_function IN ('useEffect', 'useLayoutEffect')
                    AND f.line > f2.line
                    AND f.line <= f2.line + 20
              )
            ORDER BY f.line
            LIMIT 5
        """, [file])
        
        for line, func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-setstate-in-render',
                message=f'{func} called during render phase',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='react',
                snippet=f'{func}() outside useEffect',
                fix_suggestion='Move state updates to event handlers or effects',
                cwe_id='CWE-670'
            ))
    
    return findings


# ============================================================================
# CHECK 8: Hooks After Return
# ============================================================================

def _find_hooks_after_return(cursor, react_files) -> List[StandardFinding]:
    """Find hooks that might not be called consistently."""
    findings = []
    
    for file in react_files:
        cursor.execute("""
            SELECT DISTINCT f.line, f.callee_function, f.caller_function
            FROM function_call_args f
            WHERE f.file = ?
              AND f.callee_function LIKE 'use%'
              AND EXISTS (
                  SELECT 1 FROM cfg_blocks cb
                  WHERE cb.file = f.file
                    AND cb.function_name = f.caller_function
                    AND cb.block_type = 'unreachable'
                    AND f.line >= cb.start_line
                    AND f.line <= cb.end_line
              )
            ORDER BY f.line
        """, [file])
        
        for line, hook, func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-unreachable-hook',
                message=f'Hook "{hook}" in unreachable code',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='react',
                snippet=f'{hook}() after return/throw',
                fix_suggestion='Remove unreachable hook call',
                cwe_id='CWE-561'
            ))
    
    return findings


# ============================================================================
# CHECK 9: Multiple State Updates
# ============================================================================

def _find_multiple_state_updates(cursor, react_files) -> List[StandardFinding]:
    """Find multiple state updates that should be batched."""
    findings = []
    
    for file in react_files:
        cursor.execute("""
            SELECT f1.line, f1.caller_function, COUNT(*) as update_count
            FROM function_call_args f1
            WHERE f1.file = ?
              AND f1.callee_function LIKE '%setState%'
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.callee_function LIKE '%setState%'
                    AND f2.caller_function = f1.caller_function
                    AND ABS(f2.line - f1.line) <= 5
                    AND f2.line != f1.line
              )
            GROUP BY f1.caller_function, f1.line
            HAVING COUNT(*) > 1
            ORDER BY f1.line
        """, [file])
        
        for line, func, count in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-multiple-setstate',
                message=f'Multiple setState calls should be batched',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='react',
                snippet=f'{count} setState calls in {func}',
                fix_suggestion='Combine state updates or use useReducer',
                cwe_id='CWE-1050'
            ))
    
    return findings


# ============================================================================
# CHECK 10: Missing useMemo
# ============================================================================

def _find_missing_usememo(cursor, react_files) -> List[StandardFinding]:
    """Find expensive computations that should be memoized."""
    findings = []
    
    for file in react_files:
        # Find complex computations in render (multiple operations)
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND (a.source_expr LIKE '%.map(%'
                   OR a.source_expr LIKE '%.filter(%'
                   OR a.source_expr LIKE '%.reduce(%'
                   OR a.source_expr LIKE '%.sort(%')
              AND EXISTS (
                  SELECT 1 FROM function_call_args f
                  WHERE f.file = a.file
                    AND f.callee_function LIKE 'use%'
                    AND ABS(f.line - a.line) <= 20
              )
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = a.file
                    AND f2.callee_function = 'useMemo'
                    AND ABS(f2.line - a.line) <= 5
              )
            ORDER BY a.line
            LIMIT 5
        """, [file])
        
        for file_path, line, var, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-expensive-computation',
                message=f'Expensive computation "{var}" should be memoized',
                file_path=file_path,
                line=line,
                severity=Severity.MEDIUM,
                category='react',
                snippet=expr[:50] + '...' if len(expr) > 50 else expr,
                fix_suggestion='Wrap in useMemo() to prevent recalculation',
                cwe_id='CWE-1050'
            ))
    
    return findings


# ============================================================================
# CHECK 11: Unsafe Refs
# ============================================================================

def _find_unsafe_refs(cursor, react_files) -> List[StandardFinding]:
    """Find unsafe usage of refs."""
    findings = []
    
    for file in react_files:
        # Find refs accessed during render
        cursor.execute("""
            SELECT s.line, s.name
            FROM symbols s
            WHERE s.path = ?
              AND s.name LIKE '%.current%'
              AND s.type = 'property'
              AND NOT EXISTS (
                  SELECT 1 FROM function_call_args f
                  WHERE f.file = s.path
                    AND f.callee_function IN ('useEffect', 'useLayoutEffect')
                    AND s.line > f.line
                    AND s.line <= f.line + 20
              )
            ORDER BY s.line
            LIMIT 5
        """, [file])
        
        for line, ref_access in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-ref-during-render',
                message=f'Ref "{ref_access}" accessed during render',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='react',
                snippet=ref_access,
                fix_suggestion='Access refs in effects or event handlers only',
                cwe_id='CWE-670'
            ))
    
    return findings


# ============================================================================
# CHECK 12: Effect Race Conditions
# ============================================================================

def _find_effect_race_conditions(cursor, react_files) -> List[StandardFinding]:
    """Find potential race conditions in effects."""
    findings = []
    
    for file in react_files:
        # Find multiple async operations without proper handling
        cursor.execute("""
            SELECT f1.line, f1.callee_function
            FROM function_call_args f1
            WHERE f1.file = ?
              AND f1.callee_function = 'useEffect'
              AND EXISTS (
                  SELECT COUNT(*) FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.callee_function IN ('fetch', 'axios', 'Promise.all')
                    AND f2.line > f1.line
                    AND f2.line <= f1.line + 20
                  GROUP BY f2.caller_function
                  HAVING COUNT(*) > 1
              )
            ORDER BY f1.line
        """, [file])
        
        for line, _ in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='react-effect-race-condition',
                message='Multiple async operations in useEffect may race',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='react',
                snippet='useEffect with multiple fetch/axios calls',
                fix_suggestion='Use AbortController or track mounted state',
                cwe_id='CWE-362'
            ))
    
    return findings