"""React Hooks semantic analyzer using TypeScript Compiler API AST.

This module performs high-fidelity semantic analysis of React Hooks
to detect missing dependencies and memory leaks. It operates on the
rich AST produced by js_semantic_parser.py which provides symbol
resolution and type information.
"""

from typing import List, Dict, Any, Set, Optional


def find_react_hooks_issues(tree: Any, file_path: str) -> List[Dict[str, Any]]:
    """
    Detect React Hooks programming errors using semantic AST analysis.
    
    This function analyzes the semantic AST from TypeScript Compiler API
    to detect:
    1. Missing dependencies in useEffect, useCallback, useMemo
    2. Memory leaks from missing cleanup in useEffect
    
    Args:
        tree: Semantic AST from js_semantic_parser.py
        file_path: Path to the file being analyzed
        
    Returns:
        List of issues found with normalized format
    """
    findings = []
    
    # Validate AST structure
    if not tree or not isinstance(tree, dict):
        return findings
    
    # Extract root AST node
    ast_root = tree.get('ast')
    if not ast_root:
        return findings
    
    # Track component-level variables for dependency analysis
    component_scope_vars = set()
    
    # Helper function to extract text from a node
    def get_node_text(node):
        """Extract text content from an AST node."""
        if isinstance(node, dict):
            return node.get('text', '')
        return str(node)
    
    # Helper function to get line number from a node
    def get_node_line(node):
        """Extract line number from an AST node."""
        if isinstance(node, dict):
            return node.get('line', 0)
        return 0
    
    # Helper function to check if a node is a specific hook call
    def is_hook_call(node, hook_name):
        """Check if a node is a call to a specific React Hook."""
        if not isinstance(node, dict):
            return False
        
        if node.get('kind') != 'CallExpression':
            return False
        
        # Get the function being called
        children = node.get('children', [])
        if not children:
            return False
        
        # First child should be the function identifier
        func_node = children[0]
        if isinstance(func_node, dict):
            # Check for direct hook call
            if func_node.get('kind') == 'Identifier':
                func_text = get_node_text(func_node)
                return hook_name in func_text
            # Check for React.useEffect style
            elif func_node.get('kind') == 'PropertyAccessExpression':
                prop_text = get_node_text(func_node)
                return hook_name in prop_text
        
        return False
    
    # Helper function to extract callback and deps from hook call
    def extract_hook_args(node):
        """Extract callback function and dependency array from hook call."""
        callback = None
        deps_array = None
        
        children = node.get('children', [])
        # Skip first child (function identifier)
        args = children[1:] if len(children) > 1 else []
        
        # First argument is the callback
        if args:
            callback = args[0]
        
        # Second argument is the dependency array (optional)
        if len(args) > 1:
            deps_node = args[1]
            if isinstance(deps_node, dict) and deps_node.get('kind') == 'ArrayLiteralExpression':
                deps_array = deps_node
        
        return callback, deps_array
    
    # Helper function to extract dependencies from array literal
    def extract_deps_from_array(deps_node):
        """Extract dependency names from dependency array."""
        deps = set()
        if not deps_node:
            return deps
        
        children = deps_node.get('children', [])
        for child in children:
            if isinstance(child, dict):
                # Handle simple identifiers
                if child.get('kind') == 'Identifier':
                    deps.add(get_node_text(child))
                # Handle property access (e.g., props.value)
                elif child.get('kind') == 'PropertyAccessExpression':
                    # Get the base object name for tracking
                    text = get_node_text(child)
                    if '.' in text:
                        base = text.split('.')[0]
                        deps.add(base)
                    else:
                        deps.add(text)
        
        return deps
    
    # Helper function to find all variables used in callback
    def find_used_variables(node, local_vars=None):
        """Recursively find all variables referenced in a callback."""
        if local_vars is None:
            local_vars = set()
        
        used_vars = set()
        
        if not isinstance(node, dict):
            return used_vars
        
        kind = node.get('kind', '')
        
        # Track local variable declarations
        if kind in ['VariableDeclaration', 'FunctionDeclaration']:
            # Extract variable names being declared
            children = node.get('children', [])
            for child in children:
                if isinstance(child, dict):
                    if child.get('kind') == 'VariableDeclarationList':
                        # Process variable list
                        for var_child in child.get('children', []):
                            if isinstance(var_child, dict) and var_child.get('name'):
                                local_vars.add(var_child.get('name'))
                    elif child.get('name'):
                        local_vars.add(child.get('name'))
        
        # Track parameter declarations
        if kind == 'Parameter':
            if node.get('name'):
                local_vars.add(node.get('name'))
        
        # Check for variable usage
        if kind == 'Identifier':
            var_name = get_node_text(node)
            # Only track if not locally declared
            if var_name and var_name not in local_vars:
                # Filter out React hooks and built-in objects
                built_ins = {
                    'console', 'window', 'document', 'undefined', 'null', 'true', 'false',
                    'Math', 'Object', 'Array', 'String', 'Number', 'Boolean', 'Date',
                    'JSON', 'Promise', 'Set', 'Map', 'WeakMap', 'WeakSet',
                    'addEventListener', 'removeEventListener', 'setTimeout', 'clearTimeout',
                    'setInterval', 'clearInterval', 'fetch', 'XMLHttpRequest',
                    'log', 'error', 'warn', 'info', 'debug', 'alert',
                    'parseInt', 'parseFloat', 'isNaN', 'isFinite',
                    'reduce', 'map', 'filter', 'forEach', 'find', 'some', 'every',
                    'push', 'pop', 'shift', 'unshift', 'slice', 'splice',
                    'toString', 'valueOf', 'hasOwnProperty', 'propertyIsEnumerable',
                    'item', 'value', 'key', 'index', 'length', 'size'
                }
                if not var_name.startswith('use') and var_name not in built_ins:
                    used_vars.add(var_name)
        
        # Check for property access (e.g., props.value, state.count)
        if kind == 'PropertyAccessExpression':
            text = get_node_text(node)
            if '.' in text:
                base = text.split('.')[0]
                # Only track if not locally declared and not a built-in
                built_in_objects = {
                    'console', 'window', 'document', 'Math', 'Object', 'Array', 'String',
                    'Number', 'Boolean', 'Date', 'JSON', 'Promise', 'localStorage', 
                    'sessionStorage', 'location', 'history', 'navigator', 'performance'
                }
                if base not in local_vars and base not in built_in_objects:
                    used_vars.add(base)
        
        # Recursively process children
        children = node.get('children', [])
        for child in children:
            child_vars = find_used_variables(child, local_vars.copy())
            used_vars.update(child_vars)
        
        return used_vars
    
    # Helper function to check for subscription patterns
    def find_subscriptions(node):
        """Find subscription/listener patterns in node."""
        subscriptions = []
        
        if not isinstance(node, dict):
            return subscriptions
        
        kind = node.get('kind', '')
        text = get_node_text(node)
        
        # Check for addEventListener pattern
        if kind == 'CallExpression' and 'addEventListener' in text:
            subscriptions.append({
                'type': 'addEventListener',
                'text': text,
                'line': get_node_line(node)
            })
        
        # Check for socket.on pattern
        if kind == 'CallExpression' and '.on(' in text:
            subscriptions.append({
                'type': 'socket.on',
                'text': text,
                'line': get_node_line(node)
            })
        
        # Check for setInterval/setTimeout
        if kind == 'CallExpression' and ('setInterval' in text or 'setTimeout' in text):
            subscriptions.append({
                'type': 'timer',
                'text': text,
                'line': get_node_line(node)
            })
        
        # Check for subscription patterns (subscribe, watch, observe)
        if kind == 'CallExpression' and any(pattern in text for pattern in ['.subscribe(', '.watch(', '.observe(']):
            subscriptions.append({
                'type': 'subscription',
                'text': text,
                'line': get_node_line(node)
            })
        
        # Recursively check children
        children = node.get('children', [])
        for child in children:
            child_subs = find_subscriptions(child)
            subscriptions.extend(child_subs)
        
        return subscriptions
    
    # Helper function to check if callback returns a cleanup function
    def has_cleanup_return(callback_node):
        """Check if a callback returns a cleanup function."""
        if not isinstance(callback_node, dict):
            return False
        
        # For arrow functions and function expressions
        kind = callback_node.get('kind', '')
        
        # Look for return statements
        def find_return_statements(node):
            returns = []
            if not isinstance(node, dict):
                return returns
            
            if node.get('kind') == 'ReturnStatement':
                returns.append(node)
            
            # Don't traverse into nested functions
            if node.get('kind') in ['FunctionExpression', 'ArrowFunction', 'FunctionDeclaration']:
                if node != callback_node:  # Skip if it's a nested function
                    return returns
            
            children = node.get('children', [])
            for child in children:
                child_returns = find_return_statements(child)
                returns.extend(child_returns)
            
            return returns
        
        return_statements = find_return_statements(callback_node)
        
        # Check if any return statement returns a function
        for ret in return_statements:
            children = ret.get('children', [])
            if children:
                # Check if returning a function
                ret_value = children[0] if children else None
                if ret_value and isinstance(ret_value, dict):
                    ret_kind = ret_value.get('kind', '')
                    # Check for function expression or arrow function
                    if ret_kind in ['FunctionExpression', 'ArrowFunction']:
                        return True
                    # Check for returning a cleanup function reference
                    if ret_kind == 'Identifier':
                        ret_text = get_node_text(ret_value)
                        if 'cleanup' in ret_text.lower() or 'unsubscribe' in ret_text.lower():
                            return True
        
        return False
    
    # Main traversal function
    def traverse_ast(node, depth=0):
        """Traverse AST to find React Hooks issues."""
        if depth > 100 or not isinstance(node, dict):
            return
        
        kind = node.get('kind', '')
        
        # Detection 1: Missing dependencies in useEffect, useCallback, useMemo
        hook_names = ['useEffect', 'useCallback', 'useMemo']
        for hook_name in hook_names:
            if is_hook_call(node, hook_name):
                callback, deps_array = extract_hook_args(node)
                
                if callback:
                    # Find all variables used in the callback
                    used_vars = find_used_variables(callback)
                    
                    # Get declared dependencies
                    declared_deps = extract_deps_from_array(deps_array) if deps_array else set()
                    
                    # Find missing dependencies
                    missing_deps = used_vars - declared_deps
                    
                    # Filter out some common false positives
                    missing_deps = {
                        dep for dep in missing_deps
                        if not dep.startswith('_')  # Skip private convention
                        and dep not in ['React', 'useState', 'useEffect', 'useCallback', 'useMemo', 'useRef']  # Skip React APIs
                        and len(dep) > 1  # Skip single letter vars often used for iteration
                    }
                    
                    if missing_deps:
                        findings.append({
                            'pattern_name': 'REACT_HOOKS_MISSING_DEPS',
                            'message': f'{hook_name} hook missing dependencies: {", ".join(sorted(missing_deps))}',
                            'file': file_path,
                            'line': get_node_line(node),
                            'column': node.get('column', 0),
                            'severity': 'high',
                            'category': 'react',
                            'confidence': 0.85,
                            'details': {
                                'hook': hook_name,
                                'missing_dependencies': sorted(list(missing_deps)),
                                'declared_dependencies': sorted(list(declared_deps)),
                                'used_variables': sorted(list(used_vars))
                            }
                        })
        
        # Detection 2: Memory leaks in useEffect
        if is_hook_call(node, 'useEffect'):
            callback, deps_array = extract_hook_args(node)
            
            if callback:
                # Check for subscriptions/listeners
                subscriptions = find_subscriptions(callback)
                
                if subscriptions:
                    # Check if cleanup function is returned
                    has_cleanup = has_cleanup_return(callback)
                    
                    if not has_cleanup:
                        subscription_types = list(set(sub['type'] for sub in subscriptions))
                        findings.append({
                            'pattern_name': 'REACT_HOOKS_MEMORY_LEAK',
                            'message': f'useEffect creates subscriptions ({", ".join(subscription_types)}) but lacks cleanup function',
                            'file': file_path,
                            'line': get_node_line(node),
                            'column': node.get('column', 0),
                            'severity': 'high',
                            'category': 'react',
                            'confidence': 0.90,
                            'details': {
                                'hook': 'useEffect',
                                'subscriptions': subscriptions,
                                'has_cleanup': False,
                                'recommendation': 'Return a cleanup function that removes event listeners or cancels subscriptions'
                            }
                        })
        
        # Recursively traverse children
        children = node.get('children', [])
        for child in children:
            traverse_ast(child, depth + 1)
    
    # Start traversal from root
    traverse_ast(ast_root)
    
    return findings