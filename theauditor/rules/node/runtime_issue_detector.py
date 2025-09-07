"""Security rules for detecting Node.js runtime security issues.

Supports:
- JavaScript/TypeScript (via ESLint AST and tree-sitter AST)
"""

import re
from typing import List, Dict, Any


def find_node_runtime_issues(tree: Any, taint_checker=None) -> List[Dict[str, Any]]:
    """Find Node.js runtime security issues (command injection, prototype pollution).
    
    Detects:
    - Insecure child_process.exec() usage with user input
    - Prototype pollution patterns in object merging
    
    Supports:
    - ESLint AST (preferred - from prompt 4 integration)
    - Tree-sitter AST (fallback)
    - Regex-based AST (last resort)
    
    Args:
        tree: Either an ESLint AST dict, tree-sitter AST, or regex AST from ast_parser.py
        taint_checker: Optional function from orchestrator to check if variable is tainted
    
    Returns:
        List of findings with details about Node.js runtime vulnerabilities
    """
    # Handle different AST formats
    if isinstance(tree, dict):
        tree_type = tree.get("type")
        
        if tree_type == "eslint_ast":
            return _find_node_runtime_issues_eslint(tree, taint_checker)
        elif tree_type == "tree_sitter":
            return _find_node_runtime_issues_tree_sitter(tree, taint_checker)
        elif tree_type == "regex_ast":
            return _find_node_runtime_issues_regex(tree, taint_checker)
        else:
            # Unknown tree type
            return []
    else:
        # Unknown format
        return []


def _find_node_runtime_issues_eslint(tree_wrapper: Dict[str, Any], taint_checker=None) -> List[Dict[str, Any]]:
    """Find Node.js runtime issues using ESLint AST (highest fidelity).
    
    Uses the ESLint AST format from our prompt 4 integration for accurate analysis.
    If taint_checker is provided by orchestrator, uses that instead of tracking taint locally.
    """
    findings = []
    
    # Get the ESLint AST and source code
    ast = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    
    if not ast or not isinstance(ast, dict):
        return findings
    
    # If orchestrator provides taint_checker, use that. Otherwise track locally
    if taint_checker:
        tainted_vars = None  # Not needed when using taint_checker
    else:
        # Track tainted variables locally (fallback)
        tainted_vars = set()
    
    # Common sources of user input in Node.js
    input_sources = [
        'req.body', 'req.query', 'req.params', 'req.headers', 'req.cookies',
        'request.body', 'request.query', 'request.params',
        'process.argv', 'process.env',
    ]
    
    # Helper function to traverse ESLint AST recursively
    def traverse_ast(node: Dict[str, Any], parent: Dict[str, Any] = None):
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # Track variable declarations from user input (skip if using taint_checker)
        if node_type == "VariableDeclarator" and not taint_checker:
            var_id = node.get("id", {})
            var_init = node.get("init", {})
            
            if var_id.get("type") == "Identifier":
                var_name = var_id.get("name")
                
                # Check if initialized from user input
                init_text = _extract_text_from_eslint_node(var_init, content)
                if any(source in init_text for source in input_sources):
                    tainted_vars.add(var_name)
        
        # Check for child_process.exec() calls
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            
            # Check for exec, execSync, spawn with shell:true
            if callee.get("type") == "MemberExpression":
                obj = callee.get("object", {})
                prop = callee.get("property", {})
                
                # Check if it's child_process.exec or require('child_process').exec
                is_child_process = False
                if obj.get("type") == "Identifier" and obj.get("name") == "child_process":
                    is_child_process = True
                elif obj.get("type") == "CallExpression":
                    obj_callee = obj.get("callee", {})
                    if obj_callee.get("type") == "Identifier" and obj_callee.get("name") == "require":
                        obj_args = obj.get("arguments", [])
                        if obj_args and obj_args[0].get("type") == "Literal":
                            if obj_args[0].get("value") == "child_process":
                                is_child_process = True
                
                if is_child_process and prop.get("type") == "Identifier":
                    method_name = prop.get("name")
                    
                    if method_name in ["exec", "execSync", "execFile", "execFileSync"]:
                        # Check the command argument
                        args = node.get("arguments", [])
                        if args:
                            cmd_arg = args[0]
                            
                            # Check if command is constructed with user input
                            is_vulnerable = False
                            vulnerability_details = ""
                            
                            # Template literal with tainted variables
                            if cmd_arg.get("type") == "TemplateLiteral":
                                expressions = cmd_arg.get("expressions", [])
                                for expr in expressions:
                                    if expr.get("type") == "Identifier":
                                        var_name = expr.get("name")
                                        # Use taint_checker if available
                                        if taint_checker:
                                            if taint_checker(var_name, start.get("line", 0)):
                                                is_vulnerable = True
                                                vulnerability_details = f"Template literal contains tainted variable: {var_name}"
                                                break
                                        elif tainted_vars is not None and var_name in tainted_vars:
                                            is_vulnerable = True
                                            vulnerability_details = f"Template literal contains tainted variable: {var_name}"
                                            break
                                    # Check for direct user input in template
                                    expr_text = _extract_text_from_eslint_node(expr, content)
                                    if any(source in expr_text for source in input_sources):
                                        is_vulnerable = True
                                        vulnerability_details = f"Template literal contains user input: {expr_text[:50]}"
                                        break
                            
                            # Binary expression (string concatenation)
                            elif cmd_arg.get("type") == "BinaryExpression" and cmd_arg.get("operator") == "+":
                                # Check if any part contains tainted data
                                left_text = _extract_text_from_eslint_node(cmd_arg.get("left", {}), content)
                                right_text = _extract_text_from_eslint_node(cmd_arg.get("right", {}), content)
                                
                                if any(var in left_text + right_text for var in tainted_vars):
                                    is_vulnerable = True
                                    vulnerability_details = "String concatenation with tainted variable"
                                elif any(source in left_text + right_text for source in input_sources):
                                    is_vulnerable = True
                                    vulnerability_details = "String concatenation with user input"
                            
                            # Direct tainted variable
                            elif cmd_arg.get("type") == "Identifier":
                                if cmd_arg.get("name") in tainted_vars:
                                    is_vulnerable = True
                                    vulnerability_details = f"Command is tainted variable: {cmd_arg.get('name')}"
                            
                            if is_vulnerable:
                                loc = node.get("loc", {})
                                start = loc.get("start", {})
                                
                                findings.append({
                                    'line': start.get("line", 0),
                                    'column': start.get("column", 0),
                                    'type': 'command_injection',
                                    'method': f'child_process.{method_name}',
                                    'details': vulnerability_details,
                                    'snippet': f'{method_name}(...user_input...)',
                                    'confidence': 0.95,
                                    'severity': 'CRITICAL',
                                    'hint': f'Never pass user input to {method_name}(). Use execFile() with argument array or validate/sanitize input.'
                                })
                    
                    # Check for spawn with shell:true
                    elif method_name == "spawn":
                        args = node.get("arguments", [])
                        if len(args) >= 3:
                            options_arg = args[2]
                            if options_arg.get("type") == "ObjectExpression":
                                properties = options_arg.get("properties", [])
                                for prop in properties:
                                    if prop.get("type") == "Property":
                                        key = prop.get("key", {})
                                        value = prop.get("value", {})
                                        if key.get("name") == "shell" and value.get("value") == True:
                                            # Check if command or args contain user input
                                            cmd_arg = args[0]
                                            args_arg = args[1] if len(args) > 1 else None
                                            
                                            is_vulnerable = False
                                            if cmd_arg.get("type") == "Identifier" and cmd_arg.get("name") in tainted_vars:
                                                is_vulnerable = True
                                            elif args_arg and args_arg.get("type") == "ArrayExpression":
                                                elements = args_arg.get("elements", [])
                                                for elem in elements:
                                                    if elem.get("type") == "Identifier" and elem.get("name") in tainted_vars:
                                                        is_vulnerable = True
                                                        break
                                            
                                            if is_vulnerable:
                                                loc = node.get("loc", {})
                                                start = loc.get("start", {})
                                                
                                                findings.append({
                                                    'line': start.get("line", 0),
                                                    'column': start.get("column", 0),
                                                    'type': 'command_injection',
                                                    'method': 'child_process.spawn',
                                                    'details': 'spawn() with shell:true and user input',
                                                    'snippet': 'spawn(cmd, args, {shell: true})',
                                                    'confidence': 0.95,
                                                    'severity': 'CRITICAL',
                                                    'hint': 'Remove shell:true or validate/sanitize all inputs'
                                                })
        
        # Check for prototype pollution patterns
        if node_type == "ForInStatement" or node_type == "ForOfStatement":
            # Look for patterns like: for (key in source) { target[key] = source[key] }
            left = node.get("left", {})
            right = node.get("right", {})
            body = node.get("body", {})
            
            if left.get("type") == "VariableDeclaration":
                declarations = left.get("declarations", [])
                if declarations and declarations[0].get("id", {}).get("type") == "Identifier":
                    key_var = declarations[0].get("id", {}).get("name")
                    
                    # Check body for dangerous assignment pattern
                    if body.get("type") == "BlockStatement":
                        statements = body.get("body", [])
                        for stmt in statements:
                            if _is_prototype_pollution_assignment(stmt, key_var):
                                loc = node.get("loc", {})
                                start = loc.get("start", {})
                                
                                findings.append({
                                    'line': start.get("line", 0),
                                    'column': start.get("column", 0),
                                    'type': 'prototype_pollution',
                                    'pattern': 'recursive_merge',
                                    'details': f'Unsafe property assignment with dynamic key: target[{key_var}] = source[{key_var}]',
                                    'snippet': f'for ({key_var} in source) {{ target[{key_var}] = ... }}',
                                    'confidence': 0.85,
                                    'severity': 'HIGH',
                                    'hint': 'Check for __proto__, constructor, and prototype keys before assignment. Use Object.hasOwn() or Map instead.'
                                })
                                break
        
        # Recursively traverse child nodes
        for key, value in node.items():
            if key in ["type", "loc", "range", "raw", "value"]:
                continue
            
            if isinstance(value, dict):
                traverse_ast(value, node)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        traverse_ast(item, node)
    
    # Start traversal from root
    if ast.get("type") == "Program":
        traverse_ast(ast)
    
    return findings


def _find_node_runtime_issues_tree_sitter(tree_wrapper: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find Node.js runtime issues using tree-sitter AST (fallback).
    
    Less accurate than ESLint AST but better than regex.
    """
    findings = []
    
    tree = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    
    if not tree:
        return findings
    
    try:
        import tree_sitter
        from tree_sitter_language_pack import get_language
        
        language = tree_wrapper.get("language", "javascript")
        lang = get_language(language)
        
        # Query for child_process.exec calls
        exec_query = lang.query("""
            (call_expression
              function: (member_expression
                object: (_) @obj
                property: (property_identifier) @method)
              arguments: (arguments (_) @cmd))
        """)
        
        # Track tainted variables
        tainted_vars = set()
        
        # Query for variable assignments from user input
        var_query = lang.query("""
            [
              (variable_declarator
                name: (identifier) @var_name
                value: (_) @var_value)
              (assignment_expression
                left: (identifier) @var_name
                right: (_) @var_value)
            ]
        """)
        
        # Find tainted variables
        for capture in var_query.captures(tree.root_node):
            node, capture_name = capture
            if capture_name == "var_name":
                var_name = node.text.decode("utf-8", errors="ignore")
                # Find corresponding value
                parent = node.parent
                value_text = ""
                
                for sibling in parent.children:
                    if sibling != node and sibling.type not in ["=", "const", "let", "var"]:
                        value_text = sibling.text.decode("utf-8", errors="ignore")
                        break
                
                input_sources = ['req.body', 'req.query', 'req.params', 'process.argv']
                if any(source in value_text for source in input_sources):
                    tainted_vars.add(var_name)
        
        # Check exec calls
        for capture in exec_query.captures(tree.root_node):
            node, capture_name = capture
            
            if capture_name == "method":
                method_name = node.text.decode("utf-8", errors="ignore")
                
                if method_name in ["exec", "execSync", "execFile", "spawn"]:
                    # Check if object is child_process
                    parent = node.parent
                    obj_node = None
                    cmd_node = None
                    
                    for child in parent.parent.children:
                        if child.type == "arguments":
                            for arg in child.children:
                                if arg.type not in ["(", ")", ","]:
                                    cmd_node = arg
                                    break
                    
                    if cmd_node:
                        cmd_text = cmd_node.text.decode("utf-8", errors="ignore")
                        
                        # Check for tainted variables or direct user input
                        is_vulnerable = False
                        for tainted in tainted_vars:
                            if tainted in cmd_text:
                                is_vulnerable = True
                                break
                        
                        if not is_vulnerable:
                            input_sources = ['req.body', 'req.query', 'req.params', 'process.argv']
                            for source in input_sources:
                                if source in cmd_text:
                                    is_vulnerable = True
                                    break
                        
                        if is_vulnerable:
                            findings.append({
                                'line': node.start_point[0] + 1,
                                'column': node.start_point[1],
                                'type': 'command_injection',
                                'method': f'child_process.{method_name}',
                                'details': 'Command contains user-controlled input',
                                'snippet': cmd_text[:80] + "..." if len(cmd_text) > 80 else cmd_text,
                                'confidence': 0.85,
                                'severity': 'CRITICAL',
                                'hint': f'Sanitize input before passing to {method_name}() or use safer alternatives'
                            })
        
        # Query for prototype pollution patterns
        pollution_query = lang.query("""
            (for_in_statement
              left: (_) @key_var
              right: (_) @source_obj
              body: (statement_block) @body)
        """)
        
        for capture in pollution_query.captures(tree.root_node):
            node, capture_name = capture
            
            if capture_name == "body":
                body_text = node.text.decode("utf-8", errors="ignore")
                
                # Look for pattern: target[key] = source[key]
                if re.search(r'\w+\[[\w]+\]\s*=\s*\w+\[[\w]+\]', body_text):
                    # Check if there's no key validation
                    if not any(check in body_text for check in ['hasOwnProperty', 'hasOwn', '__proto__', 'constructor', 'prototype']):
                        findings.append({
                            'line': node.start_point[0] + 1,
                            'column': node.start_point[1],
                            'type': 'prototype_pollution',
                            'pattern': 'unsafe_merge',
                            'details': 'Object merge without key validation',
                            'snippet': body_text[:80] + "..." if len(body_text) > 80 else body_text,
                            'confidence': 0.75,
                            'severity': 'HIGH',
                            'hint': 'Validate keys to prevent __proto__ pollution'
                        })
    
    except (ImportError, Exception):
        # Tree-sitter not available, fall back to regex
        return _find_node_runtime_issues_regex(tree_wrapper)
    
    return findings


def _find_node_runtime_issues_regex(tree_wrapper: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find Node.js runtime issues using regex (last resort).
    
    Least accurate but works without any AST parser.
    """
    findings = []
    
    content = tree_wrapper.get("content", "")
    
    if not content:
        return findings
    
    lines = content.split('\n')
    
    # Patterns for command injection
    exec_patterns = [
        # child_process.exec with template literals containing user input
        (r'(?:child_process\.)?exec(?:Sync)?\s*\(\s*`[^`]*\$\{[^}]*(?:req\.|request\.|process\.argv)[^}]*\}', 'template_literal'),
        # exec with string concatenation
        (r'(?:child_process\.)?exec(?:Sync)?\s*\(\s*["\'][^"\']*["\']?\s*\+\s*(?:req\.|request\.|process\.argv)', 'concatenation'),
        # exec with direct user input variable (simplified)
        (r'(?:child_process\.)?exec(?:Sync)?\s*\(\s*(?:userInput|userData|query|params|body|cmd|command)\b', 'direct_variable'),
        # spawn with shell:true
        (r'spawn\s*\([^)]+,\s*\[[^]]*(?:req\.|request\.|process\.argv)[^]]*\][^)]*shell\s*:\s*true', 'spawn_shell'),
    ]
    
    # Patterns for prototype pollution
    pollution_patterns = [
        # for...in without validation
        (r'for\s*\(\s*(?:let|const|var)?\s*(\w+)\s+in\s+\w+\s*\)[^{]*\{[^}]*\1\][^}]*=[^}]*\1\](?![^}]*(?:hasOwn|__proto__|constructor|prototype))', 'for_in_unsafe'),
        # Object.assign with spread of user input
        (r'Object\.assign\s*\([^,)]+,\s*\.\.\.(?:req\.|request\.body|request\.query)', 'assign_spread'),
        # Recursive merge pattern
        (r'function\s+merge[^{]*\{[^}]*for\s*\([^)]+in[^)]+\)[^}]*\[key\]\s*=', 'recursive_merge'),
    ]
    
    # Check each line
    for line_num, line in enumerate(lines, 1):
        # Check for command injection patterns
        for pattern, pattern_type in exec_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                findings.append({
                    'line': line_num,
                    'column': match.start(),
                    'type': 'command_injection',
                    'method': 'child_process.exec',
                    'details': f'Potential command injection via {pattern_type}',
                    'snippet': line.strip()[:80] + "..." if len(line.strip()) > 80 else line.strip(),
                    'confidence': 0.70,  # Lower confidence for regex
                    'severity': 'CRITICAL',
                    'hint': 'Never pass user input to exec(). Use execFile() or validate input.'
                })
                break
        
        # Check for prototype pollution patterns
        for pattern, pattern_type in pollution_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                findings.append({
                    'line': line_num,
                    'column': match.start(),
                    'type': 'prototype_pollution',
                    'pattern': pattern_type,
                    'details': f'Potential prototype pollution via {pattern_type}',
                    'snippet': line.strip()[:80] + "..." if len(line.strip()) > 80 else line.strip(),
                    'confidence': 0.65,  # Lower confidence for regex
                    'severity': 'HIGH',
                    'hint': 'Validate object keys before assignment. Block __proto__, constructor, prototype.'
                })
                break
    
    return findings


def _extract_text_from_eslint_node(node: Dict[str, Any], source: str) -> str:
    """Extract source text from ESLint AST node using location info.
    
    Args:
        node: ESLint AST node with location information
        source: Original source code
        
    Returns:
        Text content of the node
    """
    if not isinstance(node, dict):
        return ""
    
    # For literal values, return the value directly
    if node.get("type") == "Literal":
        return str(node.get("value", ""))
    
    # For identifiers, return the name
    if node.get("type") == "Identifier":
        return node.get("name", "")
    
    # For other nodes, try to extract from source using range
    range_info = node.get("range")
    if range_info and isinstance(range_info, list) and len(range_info) == 2:
        start, end = range_info
        if 0 <= start < end <= len(source):
            return source[start:end]
    
    # Fallback: try to reconstruct from node type
    node_type = node.get("type", "")
    
    if node_type == "MemberExpression":
        obj = _extract_text_from_eslint_node(node.get("object", {}), source)
        prop = _extract_text_from_eslint_node(node.get("property", {}), source)
        return f"{obj}.{prop}"
    
    elif node_type == "CallExpression":
        callee = _extract_text_from_eslint_node(node.get("callee", {}), source)
        return f"{callee}(...)"
    
    elif node_type == "BinaryExpression":
        left = _extract_text_from_eslint_node(node.get("left", {}), source)
        op = node.get("operator", "")
        right = _extract_text_from_eslint_node(node.get("right", {}), source)
        return f"{left} {op} {right}"
    
    return ""


def _is_prototype_pollution_assignment(stmt: Dict[str, Any], key_var: str) -> bool:
    """Check if a statement contains unsafe prototype pollution pattern.
    
    Args:
        stmt: ESLint AST statement node
        key_var: Name of the iteration variable
        
    Returns:
        True if statement contains target[key] = source[key] pattern
    """
    if not isinstance(stmt, dict):
        return False
    
    # Look for expression statement with assignment
    if stmt.get("type") == "ExpressionStatement":
        expr = stmt.get("expression", {})
        
        if expr.get("type") == "AssignmentExpression":
            left = expr.get("left", {})
            right = expr.get("right", {})
            
            # Check if left is target[key]
            if left.get("type") == "MemberExpression" and left.get("computed"):
                left_prop = left.get("property", {})
                if left_prop.get("type") == "Identifier" and left_prop.get("name") == key_var:
                    # Check if right is source[key]
                    if right.get("type") == "MemberExpression" and right.get("computed"):
                        right_prop = right.get("property", {})
                        if right_prop.get("type") == "Identifier" and right_prop.get("name") == key_var:
                            return True
    
    # Check nested statements
    if stmt.get("type") == "IfStatement":
        consequent = stmt.get("consequent", {})
        if _is_prototype_pollution_assignment(consequent, key_var):
            return True
        
        alternate = stmt.get("alternate", {})
        if alternate and _is_prototype_pollution_assignment(alternate, key_var):
            return True
    
    elif stmt.get("type") == "BlockStatement":
        body = stmt.get("body", [])
        for sub_stmt in body:
            if _is_prototype_pollution_assignment(sub_stmt, key_var):
                return True
    
    return False