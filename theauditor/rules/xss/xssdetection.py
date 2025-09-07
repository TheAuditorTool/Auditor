"""Security rules for detecting Cross-Site Scripting (XSS) vulnerabilities."""

import ast
import re
from typing import List, Dict, Any


def find_xss_vulnerabilities(tree: Any, taint_checker=None) -> List[Dict[str, Any]]:
    """Find potential Cross-Site Scripting (XSS) vulnerabilities (language-aware).
    
    Detects:
    - User input directly rendered without escaping
    - Unsafe template rendering
    - Direct HTML generation with user data
    
    Supports:
    - Python (native ast.AST)
    - JavaScript/TypeScript (tree-sitter or regex fallback)
    
    Args:
        tree: Either a Python ast.AST object (legacy) or a wrapped AST dict from ast_parser.py
        taint_checker: Optional function from orchestrator to check if variable is tainted
    
    Returns:
        List of findings with details about XSS vulnerabilities
    """
    # Handle both legacy (direct ast.AST) and new wrapped format
    if isinstance(tree, ast.AST):
        # Legacy format - direct Python AST
        return _find_xss_vulnerabilities_python(tree, taint_checker)
    elif isinstance(tree, dict):
        # New wrapped format from ast_parser.py
        tree_type = tree.get("type")
        language = tree.get("language", "")  # Empty not unknown
        
        if tree_type == "python_ast":
            return _find_xss_vulnerabilities_python(tree["tree"], taint_checker)
        elif tree_type == "tree_sitter":
            return _find_xss_vulnerabilities_tree_sitter(tree, taint_checker)
        elif tree_type == "regex_ast":
            return _find_xss_vulnerabilities_regex_ast(tree, taint_checker)
        else:
            # Unknown tree type
            return []
    else:
        # Unknown format
        return []


def _find_xss_vulnerabilities_python(tree: ast.AST, taint_checker=None) -> List[Dict[str, Any]]:
    """Find potential Cross-Site Scripting (XSS) vulnerabilities in Python AST (original implementation).
    
    This is the original Python-specific implementation.
    If taint_checker is provided by orchestrator, uses that instead of tracking taint locally.
    """
    findings = []
    
    # If orchestrator provides taint_checker, use that. Otherwise fall back to local tracking
    if taint_checker:
        # Use orchestrator's taint data
        tainted_vars = None  # Not needed when using taint_checker
        sanitized_vars = set()
    else:
        # Track tainted variables locally (fallback for standalone use)
        tainted_vars = set()
        sanitized_vars = set()
    
    # Common sources of user input
    input_sources = {
        # Flask/Werkzeug
        'request.args.get', 'request.form', 'request.values', 'request.data',
        'request.get_json', 'request.cookies', 'request.headers',
        # Django
        'request.GET', 'request.POST', 'request.FILES', 'request.META',
        # Express.js style (for Python frameworks that mimic it)
        'req.query', 'req.body', 'req.params', 'req.cookies',
        # Generic
        'input', 'raw_input', 'sys.stdin.read',
    }
    
    # Common sinks where XSS can occur
    dangerous_sinks = {
        # Flask/Jinja2
        'render_template_string', 'Markup', 'make_response',
        # Django
        'mark_safe', 'format_html', 'HttpResponse',
        # Direct HTML manipulation
        'innerHTML', 'document.write', 'eval',
        # Response methods
        'send', 'write', 'end', 'json',
    }
    
    # Common sanitization functions
    sanitizers = {
        'escape', 'html.escape', 'markupsafe.escape', 'jinja2.escape',
        'bleach.clean', 'cgi.escape', 'django.utils.html.escape',
        'flask.escape', 'werkzeug.utils.escape',
    }
    
    # Walk the AST
    for node in ast.walk(tree):
        # Track assignments from user input sources
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id
                    
                    # Check if assignment is from a user input source
                    if isinstance(node.value, ast.Call):
                        call_name = _get_call_name(node.value)
                        if any(source in call_name for source in input_sources):
                            tainted_vars.add(var_name)
                    
                    # Check if assignment is from another tainted variable
                    elif isinstance(node.value, ast.Name):
                        if node.value.id in tainted_vars:
                            tainted_vars.add(var_name)
                    
                    # Check if variable is being sanitized
                    elif isinstance(node.value, ast.Call):
                        call_name = _get_call_name(node.value)
                        if any(san in call_name for san in sanitizers):
                            # Check if sanitizing a tainted variable
                            if len(node.value.args) > 0:
                                if isinstance(node.value.args[0], ast.Name):
                                    if node.value.args[0].id in tainted_vars:
                                        sanitized_vars.add(var_name)
                                        tainted_vars.discard(var_name)
        
        # Check for direct user input in dangerous sinks
        elif isinstance(node, ast.Call):
            call_name = _get_call_name(node)
            
            # Check if this is a dangerous sink
            if any(sink in call_name for sink in dangerous_sinks):
                # Check arguments for tainted variables
                for arg in node.args:
                    if isinstance(arg, ast.Name):
                        # Use taint_checker if available, otherwise check local tainted_vars
                        is_tainted = False
                        if taint_checker:
                            is_tainted = taint_checker(arg.id, getattr(node, 'lineno', 0))
                        elif tainted_vars is not None:
                            is_tainted = arg.id in tainted_vars and arg.id not in sanitized_vars
                        
                        if is_tainted:
                            findings.append({
                                'line': getattr(node, 'lineno', 0),
                                'column': getattr(node, 'col_offset', 0),
                                'variable': arg.id,
                                'sink': call_name,
                                'snippet': f'{call_name}({arg.id})',
                                'severity': 'CRITICAL',
                                'type': 'xss_vulnerability',
                                'hint': f'Sanitize {arg.id} before passing to {call_name}. Use escape() or similar.'
                            })
                    
                    # Check for direct user input calls in arguments
                    elif isinstance(arg, ast.Call):
                        inner_call_name = _get_call_name(arg)
                        if any(source in inner_call_name for source in input_sources):
                            findings.append({
                                'line': getattr(node, 'lineno', 0),
                                'column': getattr(node, 'col_offset', 0),
                                'source': inner_call_name,
                                'sink': call_name,
                                'snippet': f'{call_name}({inner_call_name}...)',
                                'severity': 'CRITICAL',
                                'type': 'xss_vulnerability',
                                'hint': f'User input from {inner_call_name} directly passed to {call_name}. Must escape!'
                            })
                    
                    # Check for f-strings or string concatenation with tainted vars
                    elif isinstance(arg, ast.JoinedStr):  # f-string
                        for value in arg.values:
                            if isinstance(value, ast.FormattedValue):
                                if isinstance(value.value, ast.Name):
                                    # Use taint_checker if available
                                    is_tainted = False
                                    if taint_checker:
                                        is_tainted = taint_checker(value.value.id, getattr(node, 'lineno', 0))
                                    elif tainted_vars is not None:
                                        is_tainted = value.value.id in tainted_vars and value.value.id not in sanitized_vars
                                    
                                    if is_tainted:
                                        findings.append({
                                            'line': getattr(node, 'lineno', 0),
                                            'column': getattr(node, 'col_offset', 0),
                                            'variable': value.value.id,
                                            'sink': call_name,
                                            'snippet': f'{call_name}(f"...{{{value.value.id}}}...")',
                                            'severity': 'CRITICAL',
                                            'type': 'xss_vulnerability',
                                            'hint': f'Tainted variable {value.value.id} in f-string passed to {call_name}'
                                        })
        
        # Check for string formatting with tainted variables
        elif isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Mod):  # % formatting
                # Check if right operand contains tainted variables
                tainted_in_format = False
                if isinstance(node.right, ast.Name):
                    if node.right.id in tainted_vars and node.right.id not in sanitized_vars:
                        tainted_in_format = True
                elif isinstance(node.right, ast.Tuple):
                    for elt in node.right.elts:
                        if isinstance(elt, ast.Name):
                            if elt.id in tainted_vars and elt.id not in sanitized_vars:
                                tainted_in_format = True
                                break
                
                if tainted_in_format:
                    # Check if this formatted string is used in a dangerous context
                    parent = _get_parent_node(tree, node)
                    if isinstance(parent, ast.Call):
                        call_name = _get_call_name(parent)
                        if any(sink in call_name for sink in dangerous_sinks):
                            findings.append({
                                'line': getattr(node, 'lineno', 0),
                                'column': getattr(node, 'col_offset', 0),
                                'snippet': 'String formatting with tainted data',
                                'severity': 'CRITICAL',
                                'type': 'xss_vulnerability',
                                'hint': 'Escape user input before string formatting in HTML context'
                            })
    
    return findings


def _get_call_name(node: ast.Call) -> str:
    """Helper to extract the full call name from a Call node."""
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


def _get_parent_node(tree: ast.AST, target_node: ast.AST) -> ast.AST:
    """Helper to find the parent node of a given node in the AST."""
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            if child == target_node:
                return node
    return None


def _find_xss_vulnerabilities_tree_sitter(tree_wrapper: Dict[str, Any], taint_checker=None) -> List[Dict[str, Any]]:
    """Find potential XSS vulnerabilities in JavaScript/TypeScript using tree-sitter AST.
    
    If taint_checker is provided by orchestrator, uses that instead of tracking taint locally.
    """
    findings = []
    
    # If orchestrator provides taint_checker with JavaScript support, use that
    if taint_checker:
        # Orchestrator's taint analyzer has JavaScript pattern support now
        tainted_vars = None  # Not needed
        sanitized_vars = set()
    else:
        # Track tainted variables locally (fallback)
        tainted_vars = set()
        sanitized_vars = set()
    
    # JavaScript/TypeScript taint sources
    input_sources = {
        # Express.js / Node.js
        'req.body', 'req.query', 'req.params', 'req.cookies', 'req.headers',
        'request.body', 'request.query', 'request.params', 'request.cookies',
        # Browser APIs
        'location.search', 'location.hash', 'location.href', 'location.pathname',
        'document.location', 'window.location', 'document.URL', 'document.referrer',
        'document.cookie', 'localStorage.getItem', 'sessionStorage.getItem',
        # Form inputs
        'getElementById', 'querySelector', 'querySelectorAll',
        '.value', '.innerHTML', '.innerText', '.textContent',
        # URL parameters
        'URLSearchParams', 'searchParams.get',
        # React/Vue/Angular inputs
        'props.', 'this.props.', '$route.params', '$route.query',
        # WebSocket/PostMessage
        'message.data', 'event.data',
    }
    
    # Dangerous sinks for JavaScript/TypeScript
    dangerous_sinks = {
        # Direct DOM manipulation
        'innerHTML', 'outerHTML', 'document.write', 'document.writeln',
        'insertAdjacentHTML', 'createContextualFragment',
        # React dangerous methods
        'dangerouslySetInnerHTML',
        # jQuery methods
        'html', 'append', 'prepend', 'after', 'before', 'replaceWith',
        # Script execution
        'eval', 'setTimeout', 'setInterval', 'Function', 'execScript',
        # Template literals in dangerous contexts
        'v-html',  # Vue.js
        '[innerHTML]',  # Angular
        # Server-side rendering
        'res.send', 'res.write', 'res.end', 'res.render',
        'response.send', 'response.write', 'response.end',
    }
    
    # Common sanitizers for JavaScript
    sanitizers = {
        'DOMPurify.sanitize', 'sanitize', 'escape', 'escapeHtml',
        'encodeURIComponent', 'encodeURI', 'encodeHTML',
        'validator.escape', 'xss.clean', 'sanitize-html',
        'he.encode', 'entities.encode', 'htmlspecialchars',
        'Handlebars.escapeExpression', 'lodash.escape', '_.escape',
    }
    
    tree = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    language = tree_wrapper.get("language", "javascript")
    
    if not tree:
        return findings
    
    # Try to use tree-sitter for proper traversal
    try:
        import tree_sitter
        from tree_sitter_language_pack import get_language
        
        lang = get_language(language)
        
        # Query for variable declarations and assignments
        var_query = lang.query("""
            [
                (variable_declaration
                  (variable_declarator
                    name: (identifier) @var_name
                    value: (_) @var_value))
                (assignment_expression
                  left: (identifier) @var_name
                  right: (_) @var_value)
            ]
        """)
        
        # Track tainted variables from assignments (skip if using orchestrator's taint_checker)
        if not taint_checker:
            for capture in var_query.captures(tree.root_node):
                node, capture_name = capture
                
                if capture_name == "var_name":
                    var_name = node.text.decode("utf-8", errors="ignore")
                    
                    # Find the corresponding value node
                    parent = node.parent
                    value_node = None
                    
                    if parent.type == "variable_declarator":
                        for child in parent.children:
                            if child != node and child.type != "=":
                                value_node = child
                                break
                    elif parent.type == "assignment_expression":
                        for child in parent.children:
                            if child != node and child.type != "=":
                                value_node = child
                                break
                    
                    if value_node:
                        value_text = value_node.text.decode("utf-8", errors="ignore")
                        
                        # Check if value is from a taint source
                        is_tainted = any(source in value_text for source in input_sources)
                        
                        # Check if value is from another tainted variable
                        if not is_tainted and value_node.type == "identifier":
                            if value_text in tainted_vars:
                                is_tainted = True
                        
                        # Check if value is being sanitized
                        is_sanitized = any(san in value_text for san in sanitizers)
                        
                        if is_tainted and not is_sanitized:
                            tainted_vars.add(var_name)
                        elif is_sanitized:
                            sanitized_vars.add(var_name)
                            tainted_vars.discard(var_name)
        
        # Query for function calls (potential sinks)
        call_query = lang.query("""
            (call_expression) @call
        """)
        
        # Check for dangerous sinks with tainted data
        for capture in call_query.captures(tree.root_node):
            call_node, _ = capture
            call_text = call_node.text.decode("utf-8", errors="ignore")
            
            # Check if this is a dangerous sink
            sink_found = None
            for sink in dangerous_sinks:
                if sink in call_text:
                    sink_found = sink
                    break
            
            if sink_found:
                # Extract all variable names from the call
                import re
                var_names = re.findall(r'\b[a-zA-Z_]\w*\b', call_text)
                
                if taint_checker:
                    # Use orchestrator's taint checker
                    for var_name in var_names:
                        if taint_checker(var_name, call_node.start_point[0] + 1):
                            snippet = call_text[:100] + "..." if len(call_text) > 100 else call_text
                            findings.append({
                                'line': call_node.start_point[0] + 1,
                                'column': call_node.start_point[1],
                                'variable': var_name,
                                'sink': sink_found,
                                'snippet': snippet,
                                'severity': 'CRITICAL',
                                'type': 'xss_vulnerability',
                                'hint': f'Sanitize {var_name} before using with {sink_found}. Use DOMPurify or similar.'
                            })
                            break
                else:
                    # Use local taint tracking
                    for tainted_var in tainted_vars:
                        if tainted_var in call_text and tainted_var not in sanitized_vars:
                            snippet = call_text[:100] + "..." if len(call_text) > 100 else call_text
                            findings.append({
                                'line': call_node.start_point[0] + 1,
                                'column': call_node.start_point[1],
                                'variable': tainted_var,
                                'sink': sink_found,
                                'snippet': snippet,
                                'severity': 'CRITICAL',
                                'type': 'xss_vulnerability',
                                'hint': f'Sanitize {tainted_var} before using with {sink_found}. Use DOMPurify or similar.'
                            })
                            break
                
                # Check for direct taint sources in the call
                for source in input_sources:
                    if source in call_text:
                        snippet = call_text[:100] + "..." if len(call_text) > 100 else call_text
                        
                        findings.append({
                            'line': call_node.start_point[0] + 1,
                            'column': call_node.start_point[1],
                            'source': source,
                            'sink': sink_found,
                            'snippet': snippet,
                            'severity': 'CRITICAL',
                            'type': 'xss_vulnerability',
                            'hint': f'User input from {source} directly passed to {sink_found}. Must sanitize!'
                        })
                        break
        
        # Query for JSX elements with dangerous props (React-specific)
        if language == "typescript" or "tsx" in tree_wrapper.get("content", ""):
            jsx_query = lang.query("""
                (jsx_element
                  (jsx_opening_element
                    (jsx_attribute
                      (property_identifier) @prop_name
                      (jsx_expression) @prop_value)))
            """)
            
            for capture in jsx_query.captures(tree.root_node):
                node, capture_name = capture
                
                if capture_name == "prop_name":
                    prop_name = node.text.decode("utf-8", errors="ignore")
                    
                    # Check for dangerouslySetInnerHTML
                    if prop_name == "dangerouslySetInnerHTML":
                        parent = node.parent
                        if parent:
                            for child in parent.children:
                                if child.type == "jsx_expression":
                                    expr_text = child.text.decode("utf-8", errors="ignore")
                                    
                                    # Check for tainted variables
                                    for tainted_var in tainted_vars:
                                        if tainted_var in expr_text and tainted_var not in sanitized_vars:
                                            findings.append({
                                                'line': node.start_point[0] + 1,
                                                'column': node.start_point[1],
                                                'variable': tainted_var,
                                                'sink': 'dangerouslySetInnerHTML',
                                                'snippet': f'dangerouslySetInnerHTML={{...{tainted_var}...}}',
                                                'severity': 'CRITICAL',
                                                'type': 'xss_vulnerability',
                                                'hint': f'Never use dangerouslySetInnerHTML with unsanitized user input!'
                                            })
                                            break
    
    except (ImportError, Exception):
        # Tree-sitter not available or query failed, fall back to regex_ast
        return _find_xss_vulnerabilities_regex_ast(tree_wrapper)
    
    return findings


def _find_xss_vulnerabilities_regex_ast(tree_wrapper: Dict[str, Any], taint_checker=None) -> List[Dict[str, Any]]:
    """Find potential XSS vulnerabilities using regex-based fallback AST.
    
    This is used when tree-sitter is not available for JavaScript/TypeScript.
    If taint_checker is provided, uses that instead of local tracking.
    """
    findings = []
    
    # JavaScript/TypeScript taint sources (simplified for regex)
    input_sources = [
        r'req\.(body|query|params|cookies|headers)',
        r'request\.(body|query|params|cookies)',
        r'location\.(search|hash|href|pathname)',
        r'document\.(location|URL|referrer|cookie)',
        r'localStorage\.getItem',
        r'sessionStorage\.getItem',
        r'URLSearchParams',
        r'\.value\s*[;\n]',  # Form input values
        r'props\.',
        r'event\.data',
        r'message\.data',
    ]
    
    # Dangerous sinks (simplified for regex)
    dangerous_sinks = [
        r'\.innerHTML\s*=',
        r'\.outerHTML\s*=',
        r'document\.write\(',
        r'document\.writeln\(',
        r'insertAdjacentHTML\(',
        r'dangerouslySetInnerHTML\s*[:=]',
        r'\.html\(',  # jQuery
        r'eval\(',
        r'setTimeout\([\'"`]',
        r'setInterval\([\'"`]',
        r'new\s+Function\(',
        r'res\.(send|write|render)\(',
        r'response\.(send|write|render)\(',
    ]
    
    # Sanitizers (simplified for regex)
    sanitizers = [
        r'DOMPurify\.sanitize',
        r'\.escape\(',
        r'escapeHtml\(',
        r'encodeURIComponent\(',
        r'encodeURI\(',
        r'sanitize\(',
    ]
    
    content = tree_wrapper.get("content", "")
    
    if not content:
        return findings
    
    lines = content.split('\n')
    
    # Simple taint tracking
    tainted_vars = set()
    
    # First pass: identify tainted variables
    for line_num, line in enumerate(lines, 1):
        # Look for variable assignments from taint sources
        # Pattern: const/let/var name = taint_source
        var_assignment = re.search(r'(?:const|let|var)\s+(\w+)\s*=\s*(.+)', line)
        if var_assignment:
            var_name = var_assignment.group(1)
            value = var_assignment.group(2)
            
            # Check if value contains a taint source
            for source_pattern in input_sources:
                if re.search(source_pattern, value):
                    tainted_vars.add(var_name)
                    break
            
            # Check if value is another tainted variable
            for tainted in tainted_vars:
                if tainted in value:
                    # Check if it's being sanitized
                    is_sanitized = any(re.search(san, value) for san in sanitizers)
                    if not is_sanitized:
                        tainted_vars.add(var_name)
                    break
    
    # Second pass: find dangerous sinks with tainted data
    for line_num, line in enumerate(lines, 1):
        for sink_pattern in dangerous_sinks:
            sink_match = re.search(sink_pattern, line)
            if sink_match:
                # Check for tainted variables in this line
                for tainted_var in tainted_vars:
                    if tainted_var in line:
                        # Check if it's being sanitized
                        is_sanitized = any(re.search(san, line) for san in sanitizers)
                        
                        if not is_sanitized:
                            # Extract sink name for reporting
                            sink_name = sink_pattern.replace(r'\(', '').replace(r'\s*=', '').replace('\\', '')
                            
                            findings.append({
                                'line': line_num,
                                'column': sink_match.start(),
                                'variable': tainted_var,
                                'sink': sink_name,
                                'snippet': line.strip()[:80] + "..." if len(line.strip()) > 80 else line.strip(),
                                'severity': 'CRITICAL',
                                'type': 'xss_vulnerability',
                                'hint': f'Sanitize {tainted_var} before using with {sink_name}'
                            })
                            break
                
                # Check for direct taint sources in dangerous sinks
                for source_pattern in input_sources:
                    if re.search(source_pattern, line):
                        # Extract source and sink names for reporting
                        source_match = re.search(source_pattern, line)
                        if source_match:
                            source_name = source_match.group(0)
                            sink_name = sink_pattern.replace(r'\(', '').replace(r'\s*=', '').replace('\\', '')
                            
                            findings.append({
                                'line': line_num,
                                'column': sink_match.start(),
                                'source': source_name,
                                'sink': sink_name,
                                'snippet': line.strip()[:80] + "..." if len(line.strip()) > 80 else line.strip(),
                                'severity': 'CRITICAL',
                                'type': 'xss_vulnerability',
                                'hint': f'User input from {source_name} directly passed to {sink_name}. Must sanitize!'
                            })
                            break
    
    return findings