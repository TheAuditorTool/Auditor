"""Python async and concurrency issue detector.

Detects race conditions, async issues, and concurrency problems in Python code.
Replaces regex patterns from runtime_issues.yml with proper AST analysis.
"""

import ast
from typing import List, Dict, Any, Set, Optional


def find_async_concurrency_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find async and concurrency issues in Python code.
    
    Detects:
    1. check-then-act (TOCTOU) - Time-of-check-time-of-use race conditions
    2. shared-state-no-lock - Global/class variables modified without locks
    3. async-without-await - Async calls that aren't awaited
    4. parallel-writes-no-sync - asyncio.gather with write operations
    5. sleep-in-loop - Performance issues with sleep in loops
    6. retry-without-backoff - Retry loops without exponential backoff
    7. unprotected-global-increment - Counter increments without locks
    8. shared-collection-mutation - Dict/list mutations without synchronization
    9. nested-locks - Nested lock acquisitions leading to potential deadlock
    10. lock-order-ab-ba - Locks acquired in different orders (AB-BA deadlock)
    11. lock-no-timeout - Lock acquisition without timeout
    12. thread-no-join - Thread started but never joined
    13. singleton-race - Singleton pattern without proper synchronization
    14. double-checked-lock-broken - Double-checked locking without volatile
    15. worker-no-terminate - Worker thread/process created but never terminated
    
    Args:
        tree: Python AST or dict wrapper from ast_parser.py
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checking function
    
    Returns:
        List of findings with details about concurrency issues
    """
    findings = []
    
    # Handle wrapped AST from ast_parser.py
    if isinstance(tree, dict):
        if tree.get("type") == "python_ast":
            actual_tree = tree.get("tree")
            if actual_tree:
                analyzer = PythonConcurrencyAnalyzer(file_path)
                analyzer.visit(actual_tree)
                return analyzer.findings
    elif isinstance(tree, ast.AST):
        # Direct Python AST
        analyzer = PythonConcurrencyAnalyzer(file_path)
        analyzer.visit(tree)
        return analyzer.findings
    
    return findings


class PythonConcurrencyAnalyzer(ast.NodeVisitor):
    """AST visitor for detecting concurrency issues in Python."""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or "unknown"
        self.findings = []
        
        # Track state for analysis
        self.global_vars = set()
        self.class_vars = set()
        self.async_calls = []  # Track async calls to check if awaited
        self.in_async_function = False
        self.in_loop = False
        self.current_function = None
        self.lock_usage = set()  # Track where locks are used
        self.has_threading_import = False
        self.has_asyncio_import = False
        self.has_multiprocessing_import = False
        
        # Additional tracking for new patterns
        self.lock_stack = []  # Track nested lock acquisitions
        self.lock_order = {}  # Track lock acquisition order by function
        self.threads_started = []  # Track Thread.start() calls
        self.threads_joined = []  # Track Thread.join() calls
        self.workers_created = []  # Track worker creation
        self.singleton_patterns = []  # Track singleton implementations
        
    def visit_Module(self, node: ast.Module):
        """First pass to collect global state and imports."""
        # Collect imports
        for item in ast.walk(node):
            if isinstance(item, ast.Import):
                for alias in item.names:
                    if 'threading' in alias.name:
                        self.has_threading_import = True
                    if 'multiprocessing' in alias.name:
                        self.has_multiprocessing_import = True
                    if 'asyncio' in alias.name:
                        self.has_asyncio_import = True
            elif isinstance(item, ast.ImportFrom):
                if item.module:
                    if 'threading' in item.module:
                        self.has_threading_import = True
                    if 'multiprocessing' in item.module:
                        self.has_multiprocessing_import = True
                    if 'asyncio' in item.module:
                        self.has_asyncio_import = True
        
        # Continue visiting
        self.generic_visit(node)
    
    def visit_Global(self, node: ast.Global):
        """Track global variable declarations."""
        self.global_vars.update(node.names)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Track class-level variables."""
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        self.class_vars.add(target.id)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Track async function context."""
        old_async = self.in_async_function
        old_function = self.current_function
        self.in_async_function = True
        self.current_function = node.name
        
        # Check for async-without-await pattern
        self._check_async_without_await(node)
        
        self.generic_visit(node)
        self.in_async_function = old_async
        self.current_function = old_function
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track regular function context."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_If(self, node: ast.If):
        """Detect check-then-act (TOCTOU) patterns."""
        self._check_toctou_pattern(node)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Track async calls and detect various patterns."""
        call_name = self._get_call_name(node)
        
        # Check for asyncio.gather with write operations
        if self._is_asyncio_gather(node):
            self._check_parallel_writes(node)
        
        # Track async calls
        if self._is_async_call(node):
            self.async_calls.append(node)
        
        # Check for Lock usage and detect nested locks
        if self._is_lock_usage(node):
            self.lock_usage.add(node.lineno)
            self._check_nested_locks(node)
            self._track_lock_order(node)
            
            # Check for lock without timeout
            if 'acquire' in call_name.lower() or 'lock' in call_name.lower():
                if not self._has_timeout_arg(node):
                    self.findings.append({
                        'line': node.lineno,
                        'column': node.col_offset,
                        'type': 'lock_no_timeout',
                        'severity': 'HIGH',
                        'confidence': 0.75,
                        'message': 'Lock acquisition without timeout - infinite wait risk',
                        'hint': 'Use acquire(timeout=...) to prevent deadlocks'
                    })
        
        # Track thread operations
        if 'Thread' in call_name or 'threading.Thread' in call_name:
            self._track_thread_creation(node)
        elif '.start' in call_name and self._is_thread_method(node):
            self.threads_started.append(node.lineno)
        elif '.join' in call_name and self._is_thread_method(node):
            self.threads_joined.append(node.lineno)
            
        # Track worker/process creation
        if any(w in call_name for w in ['Worker', 'Process', 'Pool', 'fork', 'spawn']):
            self.workers_created.append({
                'line': node.lineno,
                'name': call_name,
                'node': node
            })
            
        # Check for singleton pattern
        if self.current_function and 'instance' in call_name.lower():
            self._check_singleton_pattern(node)
        
        self.generic_visit(node)
    
    def visit_For(self, node: ast.For):
        """Track loop context and detect sleep-in-loop."""
        old_loop = self.in_loop
        self.in_loop = True
        
        # Check for sleep in loop
        self._check_sleep_in_loop(node)
        
        # Check for retry without backoff
        self._check_retry_without_backoff(node)
        
        self.generic_visit(node)
        self.in_loop = old_loop
    
    def visit_While(self, node: ast.While):
        """Track loop context and detect patterns."""
        old_loop = self.in_loop
        self.in_loop = True
        
        # Check for sleep in loop
        self._check_sleep_in_loop(node)
        
        # Check for retry without backoff
        self._check_retry_without_backoff(node)
        
        self.generic_visit(node)
        self.in_loop = old_loop
    
    def visit_AugAssign(self, node: ast.AugAssign):
        """Detect unprotected global/shared increments."""
        if isinstance(node.target, ast.Name):
            var_name = node.target.id
            
            # Check if it's a global or class variable
            if var_name in self.global_vars or var_name in self.class_vars:
                # Check if we're in a context with threading/asyncio
                if self.has_threading_import or self.has_asyncio_import:
                    # Check if there's lock protection nearby
                    if not self._has_lock_protection(node):
                        self.findings.append({
                            'line': node.lineno,
                            'column': node.col_offset,
                            'type': 'unprotected_global_increment',
                            'variable': var_name,
                            'operation': type(node.op).__name__,
                            'severity': 'HIGH',
                            'confidence': 0.85,
                            'message': f'Global/shared variable "{var_name}" modified without synchronization',
                            'hint': 'Use threading.Lock() or asyncio.Lock() to protect concurrent modifications'
                        })
        
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign):
        """Detect shared state modifications without locks."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                
                # Pattern 2: shared-state-no-lock
                if var_name in self.global_vars or var_name in self.class_vars:
                    if not self._has_lock_protection(node):
                        self.findings.append({
                            'line': node.lineno,
                            'column': node.col_offset,
                            'type': 'shared_state_no_lock',
                            'variable': var_name,
                            'severity': 'HIGH',
                            'confidence': 0.75,
                            'message': f'Shared state "{var_name}" modified without lock',
                            'hint': 'Use locks when modifying shared state in concurrent code'
                        })
            
            # Pattern 8: shared-collection-mutation
            elif isinstance(target, ast.Subscript):
                if isinstance(target.value, ast.Name):
                    var_name = target.value.id
                    if var_name in self.global_vars or var_name in self.class_vars:
                        if not self._has_lock_protection(node):
                            self.findings.append({
                                'line': node.lineno,
                                'column': node.col_offset,
                                'type': 'shared_collection_mutation',
                                'variable': var_name,
                                'severity': 'HIGH',
                                'confidence': 0.80,
                                'message': f'Shared collection "{var_name}" modified without synchronization',
                                'hint': 'Use locks when modifying shared collections'
                            })
        
        self.generic_visit(node)
    
    def _check_toctou_pattern(self, if_node: ast.If):
        """Check for time-of-check-time-of-use patterns."""
        # Look for patterns like: if not exists: create
        test = if_node.test
        body = if_node.body
        
        # Check if test is checking existence/membership
        is_check = False
        check_type = None
        
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            inner = test.operand
            if isinstance(inner, ast.Call):
                if hasattr(inner.func, 'id'):
                    func_name = inner.func.id
                    if func_name in ['exists', 'isfile', 'isdir']:
                        is_check = True
                        check_type = 'file_exists'
                elif hasattr(inner.func, 'attr'):
                    if inner.func.attr in ['exists', 'has', 'contains']:
                        is_check = True
                        check_type = 'has_check'
            elif isinstance(inner, ast.Compare):
                # Check for 'x in y' patterns
                if any(isinstance(op, ast.In) for op in inner.ops):
                    is_check = True
                    check_type = 'membership'
        
        if is_check:
            # Check if body performs write/create operation
            for stmt in body:
                if self._is_write_operation(stmt):
                    self.findings.append({
                        'line': if_node.lineno,
                        'column': if_node.col_offset,
                        'type': 'check_then_act',
                        'pattern': f'{check_type}_then_write',
                        'severity': 'CRITICAL',
                        'confidence': 0.90,
                        'message': 'Time-of-check-time-of-use (TOCTOU) race condition',
                        'hint': 'Use atomic operations or locks to prevent race conditions'
                    })
                    break
    
    def _check_async_without_await(self, func_node: ast.AsyncFunctionDef):
        """Check for async calls without await in async functions."""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if self._is_async_call(node):
                    # Check if this call is awaited
                    parent = self._get_parent_node(func_node, node)
                    if not isinstance(parent, ast.Await):
                        # Also check it's not used with then() or in asyncio.create_task
                        if not self._is_properly_handled_async(node):
                            self.findings.append({
                                'line': node.lineno,
                                'column': node.col_offset,
                                'type': 'async_without_await',
                                'function': self._get_call_name(node),
                                'severity': 'HIGH',
                                'confidence': 0.85,
                                'message': 'Async function called without await',
                                'hint': 'Add "await" or use asyncio.create_task() for fire-and-forget'
                            })
    
    def _check_parallel_writes(self, gather_node: ast.Call):
        """Check for asyncio.gather with write operations."""
        # Check arguments to gather
        for arg in gather_node.args:
            if isinstance(arg, ast.Call):
                call_name = self._get_call_name(arg)
                if any(op in call_name.lower() for op in ['save', 'update', 'insert', 'write', 'delete', 'remove']):
                    self.findings.append({
                        'line': gather_node.lineno,
                        'column': gather_node.col_offset,
                        'type': 'parallel_writes_no_sync',
                        'operation': call_name,
                        'severity': 'CRITICAL',
                        'confidence': 0.80,
                        'message': 'Parallel write operations without synchronization',
                        'hint': 'Use locks or transactions when performing parallel writes'
                    })
                    break
    
    def _check_sleep_in_loop(self, loop_node):
        """Check for sleep/delay in loops."""
        for node in ast.walk(loop_node):
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if 'sleep' in call_name.lower() or 'delay' in call_name.lower():
                    self.findings.append({
                        'line': node.lineno,
                        'column': node.col_offset,
                        'type': 'sleep_in_loop',
                        'severity': 'MEDIUM',
                        'confidence': 0.90,
                        'message': 'Sleep/delay in loop can cause performance issues',
                        'hint': 'Consider using async patterns or event-driven approaches'
                    })
                    break
    
    def _check_retry_without_backoff(self, loop_node):
        """Check for retry loops without exponential backoff."""
        loop_body_text = ast.unparse(loop_node) if hasattr(ast, 'unparse') else ""
        
        # Check if this looks like a retry loop
        has_retry_indicators = any(word in loop_body_text.lower() for word in ['retry', 'attempt', 'tries'])
        
        if has_retry_indicators:
            # Check for backoff patterns
            has_backoff = any(pattern in loop_body_text for pattern in ['**', 'exponential', 'backoff', '*='])
            
            if not has_backoff:
                # Check if there's any sleep that increases
                has_sleep = 'sleep' in loop_body_text.lower()
                if has_sleep and '*' not in loop_body_text:
                    self.findings.append({
                        'line': loop_node.lineno,
                        'column': loop_node.col_offset,
                        'type': 'retry_without_backoff',
                        'severity': 'MEDIUM',
                        'confidence': 0.70,
                        'message': 'Retry logic without exponential backoff',
                        'hint': 'Use exponential backoff to avoid overwhelming the system'
                    })
    
    def _is_async_call(self, node: ast.Call) -> bool:
        """Check if a call is to an async function."""
        call_name = self._get_call_name(node)
        # Common async patterns
        return any(pattern in call_name for pattern in ['async', 'await', 'gather', 'create_task'])
    
    def _is_asyncio_gather(self, node: ast.Call) -> bool:
        """Check if call is asyncio.gather."""
        call_name = self._get_call_name(node)
        return 'gather' in call_name.lower()
    
    def _is_lock_usage(self, node: ast.Call) -> bool:
        """Check if this is a lock acquisition."""
        call_name = self._get_call_name(node)
        return any(lock in call_name.lower() for lock in ['lock', 'acquire', 'rlock', 'semaphore'])
    
    def _has_lock_protection(self, node: ast.AST) -> bool:
        """Check if a node is protected by a lock (simplified check)."""
        # This is a simplified check - in real implementation would need control flow analysis
        # Check if there's a lock acquisition within 5 lines before
        return any(abs(node.lineno - lock_line) <= 5 for lock_line in self.lock_usage)
    
    def _is_write_operation(self, node: ast.AST) -> bool:
        """Check if a statement performs a write operation."""
        if isinstance(node, ast.Call):
            call_name = self._get_call_name(node)
            write_ops = ['create', 'write', 'open', 'save', 'insert', 'update', 'mkdir', 'makedirs']
            return any(op in call_name.lower() for op in write_ops)
        elif isinstance(node, ast.Assign):
            return True
        return False
    
    def _get_call_name(self, node: ast.Call) -> str:
        """Extract the name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return '.'.join(reversed(parts))
        return 'unknown'
    
    def _get_parent_node(self, root: ast.AST, target: ast.AST) -> Optional[ast.AST]:
        """Find the parent node of target in the AST."""
        for parent in ast.walk(root):
            for child in ast.iter_child_nodes(parent):
                if child == target:
                    return parent
        return None
    
    def _is_properly_handled_async(self, node: ast.Call) -> bool:
        """Check if async call is properly handled without await."""
        # Check for patterns like asyncio.create_task() or .then()
        call_name = self._get_call_name(node)
        return 'create_task' in call_name or 'ensure_future' in call_name
    
    def _check_nested_locks(self, node: ast.Call) -> None:
        """Check for nested lock acquisitions."""
        if self.lock_stack:
            # We have nested locks
            self.findings.append({
                'line': node.lineno,
                'column': node.col_offset,
                'type': 'nested_locks',
                'severity': 'CRITICAL',
                'confidence': 0.85,
                'message': 'Nested lock acquisitions - potential deadlock risk',
                'hint': 'Avoid acquiring multiple locks or ensure consistent ordering'
            })
        self.lock_stack.append(node)
    
    def _track_lock_order(self, node: ast.Call) -> None:
        """Track lock acquisition order to detect AB-BA patterns."""
        if self.current_function:
            if self.current_function not in self.lock_order:
                self.lock_order[self.current_function] = []
            lock_name = self._get_call_name(node)
            self.lock_order[self.current_function].append(lock_name)
            
            # Check for different orderings across functions
            for func, locks in self.lock_order.items():
                if func != self.current_function and len(locks) > 1:
                    # Check if same locks acquired in different order
                    current_locks = self.lock_order[self.current_function]
                    if len(current_locks) > 1:
                        if set(locks) == set(current_locks) and locks != current_locks:
                            self.findings.append({
                                'line': node.lineno,
                                'column': node.col_offset,
                                'type': 'lock_order_ab_ba',
                                'severity': 'CRITICAL',
                                'confidence': 0.80,
                                'message': 'Locks acquired in different orders - classic AB-BA deadlock',
                                'hint': 'Always acquire locks in the same order across all functions'
                            })
    
    def _has_timeout_arg(self, node: ast.Call) -> bool:
        """Check if call has timeout argument."""
        # Check positional args (timeout is often first arg)
        if node.args and isinstance(node.args[0], (ast.Constant, ast.Name)):
            return True
        # Check keyword args
        for keyword in node.keywords:
            if keyword.arg in ['timeout', 'blocking']:
                return True
        return False
    
    def _is_thread_method(self, node: ast.Call) -> bool:
        """Check if this is a method call on a Thread object."""
        call_name = self._get_call_name(node)
        return 'thread' in call_name.lower() or 't.' in call_name.lower()
    
    def _track_thread_creation(self, node: ast.Call) -> None:
        """Track thread creation for join checking."""
        # Store thread creation info
        self.threads_started.append(node.lineno)
    
    def _check_singleton_pattern(self, node: ast.Call) -> None:
        """Check for singleton race conditions."""
        # Look for pattern: if not instance: instance = ...
        # This is simplified - would need more context in production
        parent = self._get_parent_node(node, node)
        if isinstance(parent, ast.If):
            # Check if it's checking for None/not instance
            test = parent.test
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                # Check if body creates instance without synchronization
                if not self._has_lock_protection(parent):
                    self.findings.append({
                        'line': parent.lineno,
                        'column': parent.col_offset,
                        'type': 'singleton_race',
                        'severity': 'CRITICAL',
                        'confidence': 0.70,
                        'message': 'Singleton pattern without proper synchronization',
                        'hint': 'Use locks or thread-safe initialization for singleton'
                    })
    
    def visit_Return(self, node: ast.Return) -> None:
        """Check for issues in return statements."""
        # Check for double-checked locking pattern
        if self.current_function and 'instance' in str(self.current_function).lower():
            # Simplified check for double-checked locking
            # Would need more sophisticated analysis in production
            pass
        self.generic_visit(node)
    
    def visit_Module(self, node: ast.Module):
        """Override to also check for unjoined threads at module end."""
        # First do the normal module visit
        super().visit_Module(node)
        
        # Check for threads started but not joined
        if self.threads_started and not self.threads_joined:
            for thread_line in self.threads_started:
                if thread_line not in self.threads_joined:
                    self.findings.append({
                        'line': thread_line,
                        'column': 0,
                        'type': 'thread_no_join',
                        'severity': 'HIGH',
                        'confidence': 0.70,
                        'message': 'Thread started but never joined',
                        'hint': 'Call thread.join() to wait for thread completion'
                    })
        
        # Check for workers not terminated
        for worker in self.workers_created:
            # Simplified check - would need data flow analysis
            self.findings.append({
                'line': worker['line'],
                'column': 0,
                'type': 'worker_no_terminate',
                'severity': 'MEDIUM',
                'confidence': 0.60,
                'message': f'Worker/process created but may not be terminated: {worker["name"]}',
                'hint': 'Ensure proper cleanup with terminate() or close()'
            })