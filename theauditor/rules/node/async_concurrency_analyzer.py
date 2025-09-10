"""JavaScript/TypeScript async and concurrency issue detector.

Detects race conditions, async issues, and concurrency problems in JS/TS code.
Replaces regex patterns from runtime_issues.yml with proper AST analysis.
"""

from typing import List, Dict, Any, Set, Optional


def register_taint_patterns(taint_registry):
    """Register JavaScript/TypeScript concurrency-related patterns with the taint analysis registry.
    
    Args:
        taint_registry: TaintRegistry instance from theauditor.taint.registry
    """
    # Register shared state sources
    SHARED_STATE_SOURCES = [
        "global", "window", "globalThis", "process.env",
        "module.exports", "exports", "self",
        "localStorage", "sessionStorage", "document",
        "SharedArrayBuffer", "Atomics"
    ]
    
    for pattern in SHARED_STATE_SOURCES:
        taint_registry.register_source(pattern, "shared_state", "javascript")
    
    # Register async operations as sinks
    ASYNC_SINKS = [
        "Promise.all", "Promise.race", "Promise.allSettled", "Promise.any",
        "async", "await", "then", "catch", "finally",
        "setTimeout", "setInterval", "setImmediate",
        "process.nextTick", "queueMicrotask"
    ]
    
    for pattern in ASYNC_SINKS:
        taint_registry.register_sink(pattern, "async_operation", "javascript")
    
    # Register worker/thread operations as sinks
    WORKER_SINKS = [
        "Worker", "SharedWorker", "ServiceWorker",
        "worker_threads", "cluster.fork", "child_process.spawn",
        "child_process.fork", "child_process.exec",
        "postMessage", "terminate", "disconnect"
    ]
    
    for pattern in WORKER_SINKS:
        taint_registry.register_sink(pattern, "worker_thread", "javascript")
    
    # Register stream operations as sinks
    STREAM_SINKS = [
        "createReadStream", "createWriteStream",
        "pipe", "pipeline", "stream.Readable", "stream.Writable",
        "fs.watch", "fs.watchFile", "chokidar.watch"
    ]
    
    for pattern in STREAM_SINKS:
        taint_registry.register_sink(pattern, "stream_operation", "javascript")
    
    # Register file system operations as sinks
    FS_SINKS = [
        "fs.readFile", "fs.writeFile", "fs.readFileSync", "fs.writeFileSync",
        "fs.mkdir", "fs.mkdirSync", "fs.unlink", "fs.unlinkSync",
        "fs.promises.readFile", "fs.promises.writeFile"
    ]
    
    for pattern in FS_SINKS:
        taint_registry.register_sink(pattern, "filesystem", "javascript")


def find_async_concurrency_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find async and concurrency issues in JavaScript/TypeScript code.
    
    Detects:
    1. check-then-act (TOCTOU) - Time-of-check-time-of-use race conditions
    2. shared-state-no-lock - Global/static variables modified without protection
    3. async-without-await - Async calls that aren't awaited
    4. parallel-writes-no-sync - Promise.all with write operations
    5. sleep-in-loop - Performance issues with setTimeout in loops
    6. retry-without-backoff - Retry loops without exponential backoff
    7. unprotected-global-increment - Counter increments without protection
    8. shared-collection-mutation - Object/array mutations without synchronization
    9. promise-no-catch - Promise chain without error handling
    10. worker-no-terminate - Worker thread/process created but never terminated
    11. stream-no-close - Stream created without cleanup
    12. field-use-before-init - Class field used in constructor before initialization
    13. singleton-race - Singleton pattern without proper synchronization
    
    Args:
        tree: ESLint AST, tree-sitter AST, or dict wrapper from ast_parser.py
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checking function
    
    Returns:
        List of findings with details about concurrency issues
    """
    findings = []
    
    # Handle different AST formats
    if isinstance(tree, dict):
        tree_type = tree.get("type")
        
        if tree_type == "eslint_ast":
            return _analyze_eslint_ast(tree, file_path, taint_checker)
        elif tree_type == "tree_sitter":
            return _analyze_tree_sitter_ast(tree, file_path, taint_checker)
        elif tree_type == "regex_ast":
            # Fallback to simple analysis
            return _analyze_regex_ast(tree, file_path, taint_checker)
    
    return findings


def _analyze_eslint_ast(tree_wrapper: Dict[str, Any], file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Analyze ESLint AST for async/concurrency issues."""
    findings = []
    
    ast = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    
    if not ast or not isinstance(ast, dict):
        return findings
    
    # Track state for analysis
    global_vars = set()
    static_vars = set()
    async_calls = []
    await_locations = set()
    in_loop = False
    in_async_function = False
    has_worker_threads = False
    workers_created = []
    streams_created = []
    promises_without_catch = []
    class_fields = {}
    
    def traverse_ast(node: Dict[str, Any], parent: Dict[str, Any] = None):
        nonlocal in_loop, in_async_function
        
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # Track imports to understand concurrency context
        if node_type == "ImportDeclaration":
            source = node.get("source", {}).get("value", "")
            if source in ["worker_threads", "cluster", "child_process"]:
                has_worker_threads = True
        
        # Track global/static variables
        if node_type == "VariableDeclaration":
            kind = node.get("kind")
            for declarator in node.get("declarations", []):
                var_id = declarator.get("id", {})
                if var_id.get("type") == "Identifier":
                    var_name = var_id.get("name")
                    # Check if it's at program level (global)
                    if parent and parent.get("type") == "Program":
                        global_vars.add(var_name)
        
        # Track static class members
        if node_type == "PropertyDefinition" and node.get("static"):
            key = node.get("key", {})
            if key.get("type") == "Identifier":
                static_vars.add(key.get("name"))
        
        # Track async function context
        if node_type in ["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"]:
            old_async = in_async_function
            if node.get("async"):
                in_async_function = True
            
            # Check body for async-without-await
            body = node.get("body")
            if body and in_async_function:
                _check_async_without_await(body, node, findings)
            
            traverse_ast(body, node)
            in_async_function = old_async
            return
        
        # Pattern 1: check-then-act (TOCTOU)
        if node_type == "IfStatement":
            _check_toctou_pattern(node, findings)
        
        # Track loop context
        if node_type in ["ForStatement", "ForInStatement", "ForOfStatement", "WhileStatement", "DoWhileStatement"]:
            old_loop = in_loop
            in_loop = True
            
            # Pattern 5: sleep-in-loop
            _check_sleep_in_loop(node, findings)
            
            # Pattern 6: retry-without-backoff
            _check_retry_without_backoff(node, findings, content)
            
            traverse_ast(node.get("body"), node)
            in_loop = old_loop
            return
        
        # Pattern 3: async-without-await and additional patterns
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            callee_text = _extract_node_text(callee, content)
            
            # Check if it's an async call
            if _is_async_call(callee, content):
                async_calls.append(node)
                
                # Check if parent is await
                if parent and parent.get("type") != "AwaitExpression":
                    # Check if it's properly handled (Promise.then, etc)
                    if not _is_properly_handled_async(node, parent):
                        loc = node.get("loc", {}).get("start", {})
                        findings.append({
                            'line': loc.get("line", 0),
                            'column': loc.get("column", 0),
                            'type': 'async_without_await',
                            'severity': 'HIGH',
                            'confidence': 0.85,
                            'message': 'Async function called without await',
                            'hint': 'Add await or handle with .then()/.catch()'
                        })
            
            # Pattern 4: parallel-writes-no-sync
            if _is_promise_all(callee):
                _check_parallel_writes(node, findings, content)
            
            # Pattern 9: promise-no-catch
            if callee.get("type") == "MemberExpression":
                prop = callee.get("property", {})
                if prop.get("type") == "Identifier" and prop.get("name") == "then":
                    # Check if there's a .catch() chained
                    if not _has_catch_handler(parent):
                        loc = node.get("loc", {}).get("start", {})
                        promises_without_catch.append({
                            'line': loc.get("line", 0),
                            'column': loc.get("column", 0),
                            'node': node
                        })
                        findings.append({
                            'line': loc.get("line", 0),
                            'column': loc.get("column", 0),
                            'type': 'promise_no_catch',
                            'severity': 'HIGH',
                            'confidence': 0.85,
                            'message': 'Promise chain without error handling',
                            'hint': 'Add .catch() to handle promise rejections'
                        })
            
            # Pattern 10: worker-no-terminate
            if 'Worker' in callee_text or 'fork' in callee_text or 'spawn' in callee_text:
                loc = node.get("loc", {}).get("start", {})
                workers_created.append({
                    'line': loc.get("line", 0),
                    'name': callee_text,
                    'node': node
                })
            
            # Pattern 11: stream-no-close
            if 'createReadStream' in callee_text or 'createWriteStream' in callee_text:
                loc = node.get("loc", {}).get("start", {})
                streams_created.append({
                    'line': loc.get("line", 0),
                    'name': callee_text,
                    'node': node
                })
                findings.append({
                    'line': loc.get("line", 0),
                    'column': loc.get("column", 0),
                    'type': 'stream_no_close',
                    'severity': 'HIGH',
                    'confidence': 0.75,
                    'message': 'Stream created without cleanup in finally block',
                    'hint': 'Ensure stream.close() or stream.destroy() is called'
                })
        
        # Track await expressions
        if node_type == "AwaitExpression":
            loc = node.get("loc", {}).get("start", {})
            await_locations.add(loc.get("line", 0))
        
        # Pattern 2 & 7: shared-state-no-lock and unprotected-global-increment
        if node_type == "AssignmentExpression":
            left = node.get("left", {})
            operator = node.get("operator")
            
            if left.get("type") == "Identifier":
                var_name = left.get("name")
                
                # Check if it's a global/static variable
                if var_name in global_vars or var_name in static_vars:
                    loc = node.get("loc", {}).get("start", {})
                    line_num = loc.get("line", 0)
                    
                    # Check if variable is tainted
                    is_tainted = False
                    if taint_checker and line_num > 0:
                        is_tainted = taint_checker(var_name, line_num)
                    
                    # Pattern 7: unprotected-global-increment
                    if operator in ["+=", "-=", "++", "--"]:
                        findings.append({
                            'line': line_num,
                            'column': loc.get("column", 0),
                            'type': 'unprotected_global_increment',
                            'variable': var_name,
                            'operator': operator,
                            'severity': 'CRITICAL' if is_tainted else 'HIGH',
                            'confidence': 0.95 if is_tainted else 0.80,
                            'message': f'Global variable "{var_name}" modified without synchronization{" (tainted!)" if is_tainted else ""}',
                            'hint': 'Use atomic operations or mutex/semaphore for thread safety',
                            'tainted': is_tainted
                        })
                    # Pattern 2: shared-state-no-lock
                    elif operator == "=":
                        findings.append({
                            'line': line_num,
                            'column': loc.get("column", 0),
                            'type': 'shared_state_no_lock',
                            'variable': var_name,
                            'severity': 'CRITICAL' if is_tainted else 'HIGH',
                            'confidence': 0.90 if is_tainted else 0.75,
                            'message': f'Shared state "{var_name}" modified without protection{" (tainted!)" if is_tainted else ""}',
                            'hint': 'Consider using locks or immutable updates',
                            'tainted': is_tainted
                        })
            
            # Pattern 8: shared-collection-mutation
            elif left.get("type") == "MemberExpression":
                obj = left.get("object", {})
                if obj.get("type") == "Identifier":
                    var_name = obj.get("name")
                    if var_name in global_vars or var_name in static_vars:
                        loc = node.get("loc", {}).get("start", {})
                        findings.append({
                            'line': loc.get("line", 0),
                            'column': loc.get("column", 0),
                            'type': 'shared_collection_mutation',
                            'variable': var_name,
                            'severity': 'HIGH',
                            'confidence': 0.80,
                            'message': f'Shared collection "{var_name}" modified without synchronization',
                            'hint': 'Use immutable updates or synchronization primitives'
                        })
        
        # Pattern 7: Also check update expressions (++, --)
        if node_type == "UpdateExpression":
            argument = node.get("argument", {})
            if argument.get("type") == "Identifier":
                var_name = argument.get("name")
                if var_name in global_vars or var_name in static_vars:
                    loc = node.get("loc", {}).get("start", {})
                    line_num = loc.get("line", 0)
                    
                    # Check if tainted
                    is_tainted = False
                    if taint_checker and line_num > 0:
                        is_tainted = taint_checker(var_name, line_num)
                    
                    findings.append({
                        'line': line_num,
                        'column': loc.get("column", 0),
                        'type': 'unprotected_global_increment',
                        'variable': var_name,
                        'operator': node.get("operator"),
                        'severity': 'CRITICAL' if is_tainted else 'HIGH',
                        'confidence': 0.95 if is_tainted else 0.80,
                        'message': f'Global variable "{var_name}" incremented without synchronization{" (tainted!)" if is_tainted else ""}',
                        'hint': 'Use atomic operations for thread-safe increments',
                        'tainted': is_tainted
                    })
        
        # Pattern 12: field-use-before-init
        if node_type == "MethodDefinition" and node.get("key", {}).get("name") == "constructor":
            _check_field_use_before_init(node, findings, class_fields)
        
        # Pattern 13: singleton-race
        if node_type == "IfStatement":
            _check_singleton_pattern(node, findings)
        
        # Track class fields
        if node_type == "PropertyDefinition":
            key = node.get("key", {})
            if key.get("type") == "Identifier":
                field_name = key.get("name")
                if parent and parent.get("type") == "ClassBody":
                    class_fields[field_name] = node
        
        # Recursively traverse
        for key, value in node.items():
            if key in ["type", "loc", "range", "raw", "value", "name"]:
                continue
            
            if isinstance(value, dict):
                traverse_ast(value, node)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        traverse_ast(item, node)
    
    # Start traversal
    if ast.get("type") == "Program":
        traverse_ast(ast)
    
    # Check for workers not terminated
    for worker in workers_created:
        findings.append({
            'line': worker['line'],
            'column': 0,
            'type': 'worker_no_terminate',
            'severity': 'MEDIUM',
            'confidence': 0.60,
            'message': f'Worker/process created but may not be terminated: {worker["name"]}',
            'hint': 'Ensure proper cleanup with terminate() or disconnect()'
        })
    
    return findings


def _check_toctou_pattern(if_node: Dict[str, Any], findings: List[Dict[str, Any]]):
    """Check for time-of-check-time-of-use patterns."""
    test = if_node.get("test", {})
    consequent = if_node.get("consequent", {})
    
    # Check if test is checking existence
    is_check = False
    check_type = None
    
    # Pattern: !fs.existsSync(path)
    if test.get("type") == "UnaryExpression" and test.get("operator") == "!":
        argument = test.get("argument", {})
        if argument.get("type") == "CallExpression":
            callee = argument.get("callee", {})
            if callee.get("type") == "MemberExpression":
                prop = callee.get("property", {})
                if prop.get("type") == "Identifier":
                    method_name = prop.get("name", "")
                    if method_name in ["existsSync", "exists", "has", "contains", "includes"]:
                        is_check = True
                        check_type = method_name
    
    # Pattern: map.has(key) or array.includes(item)
    elif test.get("type") == "CallExpression":
        callee = test.get("callee", {})
        if callee.get("type") == "MemberExpression":
            prop = callee.get("property", {})
            if prop.get("type") == "Identifier":
                method_name = prop.get("name", "")
                if method_name in ["has", "includes", "contains"]:
                    is_check = True
                    check_type = method_name
    
    if is_check:
        # Check if body performs write operation
        if _contains_write_operation(consequent):
            loc = if_node.get("loc", {}).get("start", {})
            findings.append({
                'line': loc.get("line", 0),
                'column': loc.get("column", 0),
                'type': 'check_then_act',
                'pattern': f'{check_type}_then_write',
                'severity': 'CRITICAL',
                'confidence': 0.90,
                'message': 'Time-of-check-time-of-use (TOCTOU) race condition',
                'hint': 'Use atomic operations or locks to prevent race conditions'
            })


def _check_async_without_await(body: Dict[str, Any], func_node: Dict[str, Any], findings: List[Dict[str, Any]]):
    """Check for async calls without await in async functions."""
    def check_node(node: Dict[str, Any], parent: Dict[str, Any] = None):
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            
            # Check if it's an async call
            if _is_async_call(callee, ""):
                # Check if parent is await
                if not parent or parent.get("type") != "AwaitExpression":
                    # Check if it's handled with .then() or similar
                    if not _is_properly_handled_async(node, parent):
                        loc = node.get("loc", {}).get("start", {})
                        findings.append({
                            'line': loc.get("line", 0),
                            'column': loc.get("column", 0),
                            'type': 'async_without_await',
                            'severity': 'HIGH',
                            'confidence': 0.85,
                            'message': 'Async function called without await in async function',
                            'hint': 'Add await or use .then()/.catch() for proper handling'
                        })
        
        # Recurse
        for key, value in node.items():
            if key in ["type", "loc", "range"]:
                continue
            if isinstance(value, dict):
                check_node(value, node)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        check_node(item, node)
    
    check_node(body)


def _check_parallel_writes(promise_all_node: Dict[str, Any], findings: List[Dict[str, Any]], content: str):
    """Check for Promise.all with write operations."""
    args = promise_all_node.get("arguments", [])
    
    if args and args[0].get("type") == "ArrayExpression":
        elements = args[0].get("elements", [])
        
        for elem in elements:
            if elem and elem.get("type") == "CallExpression":
                callee = elem.get("callee", {})
                call_text = _extract_node_text(elem, content)
                
                # Check for write operation patterns
                write_patterns = ['save', 'update', 'insert', 'write', 'delete', 'remove', 'create', 'put', 'post']
                if any(pattern in call_text.lower() for pattern in write_patterns):
                    loc = promise_all_node.get("loc", {}).get("start", {})
                    findings.append({
                        'line': loc.get("line", 0),
                        'column': loc.get("column", 0),
                        'type': 'parallel_writes_no_sync',
                        'severity': 'CRITICAL',
                        'confidence': 0.80,
                        'message': 'Parallel write operations without synchronization in Promise.all',
                        'hint': 'Use sequential operations or database transactions for data consistency'
                    })
                    break


def _check_sleep_in_loop(loop_node: Dict[str, Any], findings: List[Dict[str, Any]]):
    """Check for setTimeout/sleep in loops."""
    def has_timeout(node: Dict[str, Any]) -> bool:
        if not isinstance(node, dict):
            return False
        
        if node.get("type") == "CallExpression":
            callee = node.get("callee", {})
            if callee.get("type") == "Identifier":
                name = callee.get("name", "")
                if name in ["setTimeout", "setInterval", "sleep", "delay"]:
                    return True
        
        # Recurse
        for key, value in node.items():
            if key in ["type", "loc", "range"]:
                continue
            if isinstance(value, dict):
                if has_timeout(value):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and has_timeout(item):
                        return True
        return False
    
    body = loop_node.get("body", {})
    if has_timeout(body):
        loc = loop_node.get("loc", {}).get("start", {})
        findings.append({
            'line': loc.get("line", 0),
            'column': loc.get("column", 0),
            'type': 'sleep_in_loop',
            'severity': 'MEDIUM',
            'confidence': 0.90,
            'message': 'setTimeout/delay in loop can cause performance issues',
            'hint': 'Consider using async/await patterns or Promise-based delays'
        })


def _check_retry_without_backoff(loop_node: Dict[str, Any], findings: List[Dict[str, Any]], content: str):
    """Check for retry loops without exponential backoff."""
    loop_text = _extract_node_text(loop_node, content).lower()
    
    # Check if this looks like a retry loop
    has_retry = any(word in loop_text for word in ['retry', 'attempt', 'tries', 'maxretries'])
    
    if has_retry:
        # Check for backoff patterns
        has_backoff = any(pattern in loop_text for pattern in ['math.pow', '**', 'exponential', 'backoff', '*='])
        
        if not has_backoff:
            loc = loop_node.get("loc", {}).get("start", {})
            findings.append({
                'line': loc.get("line", 0),
                'column': loc.get("column", 0),
                'type': 'retry_without_backoff',
                'severity': 'MEDIUM',
                'confidence': 0.70,
                'message': 'Retry logic without exponential backoff',
                'hint': 'Implement exponential backoff: delay *= 2 or delay = Math.pow(2, retryCount)'
            })


def _is_async_call(callee: Dict[str, Any], content: str) -> bool:
    """Check if a call is to an async function."""
    if callee.get("type") == "Identifier":
        name = callee.get("name", "")
        return name.endswith("Async") or name.startswith("async")
    elif callee.get("type") == "MemberExpression":
        prop = callee.get("property", {})
        if prop.get("type") == "Identifier":
            name = prop.get("name", "")
            return name.endswith("Async") or name.startswith("async")
    return False


def _is_promise_all(callee: Dict[str, Any]) -> bool:
    """Check if call is Promise.all."""
    if callee.get("type") == "MemberExpression":
        obj = callee.get("object", {})
        prop = callee.get("property", {})
        
        if obj.get("type") == "Identifier" and obj.get("name") == "Promise":
            if prop.get("type") == "Identifier" and prop.get("name") == "all":
                return True
    return False


def _is_properly_handled_async(node: Dict[str, Any], parent: Dict[str, Any]) -> bool:
    """Check if async call is properly handled without await."""
    if not parent:
        return False
    
    # Check if it's chained with .then() or .catch()
    if parent.get("type") == "MemberExpression":
        prop = parent.get("property", {})
        if prop.get("type") == "Identifier":
            method = prop.get("name", "")
            if method in ["then", "catch", "finally"]:
                return True
    
    # Check if it's returned
    if parent.get("type") == "ReturnStatement":
        return True
    
    return False


def _contains_write_operation(node: Dict[str, Any]) -> bool:
    """Check if a node contains write operations."""
    if not isinstance(node, dict):
        return False
    
    node_type = node.get("type")
    
    # Check for file system operations
    if node_type == "CallExpression":
        callee = node.get("callee", {})
        if callee.get("type") == "MemberExpression":
            prop = callee.get("property", {})
            if prop.get("type") == "Identifier":
                method = prop.get("name", "")
                write_methods = ['writeFileSync', 'writeFile', 'mkdir', 'mkdirSync', 
                                'create', 'save', 'insert', 'update', 'set', 'put']
                if method in write_methods:
                    return True
    
    # Recurse through children
    for key, value in node.items():
        if key in ["type", "loc", "range"]:
            continue
        if isinstance(value, dict):
            if _contains_write_operation(value):
                return True
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and _contains_write_operation(item):
                    return True
    
    return False


def _extract_node_text(node: Dict[str, Any], content: str) -> str:
    """Extract text from node using range if available."""
    if not node or not content:
        return ""
    
    range_info = node.get("range")
    if range_info and isinstance(range_info, list) and len(range_info) == 2:
        start, end = range_info
        if 0 <= start < end <= len(content):
            return content[start:end]
    
    return ""


def _has_catch_handler(parent: Dict[str, Any]) -> bool:
    """Check if promise has catch handler."""
    if not parent:
        return False
    
    # Check if parent is a CallExpression with .catch()
    if parent.get("type") == "CallExpression":
        callee = parent.get("callee", {})
        if callee.get("type") == "MemberExpression":
            prop = callee.get("property", {})
            if prop.get("type") == "Identifier" and prop.get("name") == "catch":
                return True
    
    # Check if parent is a MemberExpression leading to .catch()
    if parent.get("type") == "MemberExpression":
        prop = parent.get("property", {})
        if prop.get("type") == "Identifier" and prop.get("name") in ["catch", "finally"]:
            return True
    
    return False


def _check_field_use_before_init(constructor_node: Dict[str, Any], findings: List[Dict[str, Any]], class_fields: Dict[str, Any]):
    """Check for class field used before initialization in constructor."""
    body = constructor_node.get("value", {}).get("body", {})
    if not body:
        return
    
    initialized_fields = set()
    
    def check_usage(node: Dict[str, Any], parent: Dict[str, Any] = None):
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # Track field initialization
        if node_type == "AssignmentExpression":
            left = node.get("left", {})
            if left.get("type") == "MemberExpression":
                obj = left.get("object", {})
                prop = left.get("property", {})
                if obj.get("type") == "ThisExpression" and prop.get("type") == "Identifier":
                    initialized_fields.add(prop.get("name"))
        
        # Check field usage
        if node_type == "MemberExpression":
            obj = node.get("object", {})
            prop = node.get("property", {})
            if obj.get("type") == "ThisExpression" and prop.get("type") == "Identifier":
                field_name = prop.get("name")
                # Check if used before initialization
                if field_name in class_fields and field_name not in initialized_fields:
                    # Make sure it's not the left side of an assignment
                    if not (parent and parent.get("type") == "AssignmentExpression" and parent.get("left") == node):
                        loc = node.get("loc", {}).get("start", {})
                        findings.append({
                            'line': loc.get("line", 0),
                            'column': loc.get("column", 0),
                            'type': 'field_use_before_init',
                            'field': field_name,
                            'severity': 'HIGH',
                            'confidence': 0.80,
                            'message': f'Class field "{field_name}" used before initialization',
                            'hint': 'Initialize field before using it in constructor'
                        })
        
        # Recurse
        for key, value in node.items():
            if key in ["type", "loc", "range"]:
                continue
            if isinstance(value, dict):
                check_usage(value, node)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        check_usage(item, node)
    
    check_usage(body)


def _check_singleton_pattern(if_node: Dict[str, Any], findings: List[Dict[str, Any]]):
    """Check for singleton race conditions."""
    test = if_node.get("test", {})
    consequent = if_node.get("consequent", {})
    
    # Check if testing for null/undefined instance
    is_singleton_check = False
    
    # Pattern: !instance or instance === null
    if test.get("type") == "UnaryExpression" and test.get("operator") == "!":
        arg = test.get("argument", {})
        if arg.get("type") == "Identifier" and "instance" in arg.get("name", "").lower():
            is_singleton_check = True
    elif test.get("type") == "BinaryExpression":
        left = test.get("left", {})
        operator = test.get("operator")
        if left.get("type") == "Identifier" and "instance" in left.get("name", "").lower():
            if operator in ["==", "==="] and test.get("right", {}).get("type") == "Literal":
                is_singleton_check = True
    
    if is_singleton_check:
        # Check if body creates instance
        if _contains_instance_creation(consequent):
            loc = if_node.get("loc", {}).get("start", {})
            findings.append({
                'line': loc.get("line", 0),
                'column': loc.get("column", 0),
                'type': 'singleton_race',
                'severity': 'CRITICAL',
                'confidence': 0.70,
                'message': 'Singleton pattern without proper synchronization',
                'hint': 'Use double-checked locking or atomic initialization'
            })


def _contains_instance_creation(node: Dict[str, Any]) -> bool:
    """Check if node contains instance creation."""
    if not isinstance(node, dict):
        return False
    
    node_type = node.get("type")
    
    # Check for new Instance() or instance = ...
    if node_type == "NewExpression":
        return True
    elif node_type == "AssignmentExpression":
        left = node.get("left", {})
        if left.get("type") == "Identifier" and "instance" in left.get("name", "").lower():
            return True
    
    # Recurse
    for key, value in node.items():
        if key in ["type", "loc", "range"]:
            continue
        if isinstance(value, dict):
            if _contains_instance_creation(value):
                return True
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and _contains_instance_creation(item):
                    return True
    
    return False


def _analyze_tree_sitter_ast(tree_wrapper: Dict[str, Any], file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Analyze tree-sitter AST (simplified implementation)."""
    # This would need tree-sitter specific implementation
    # For now, return empty list
    return []


def _analyze_regex_ast(tree_wrapper: Dict[str, Any], file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Fallback regex-based analysis (simplified)."""
    # This would be the fallback simple analysis
    # For now, return empty list
    return []