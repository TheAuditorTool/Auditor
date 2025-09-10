"""React framework-specific security analyzer using AST."""

from typing import Any, Dict, List


def find_react_issues(tree: Any, file_path: str = None, content: str = None, **kwargs) -> List[Dict[str, Any]]:
    """Find React security issues using AST analysis.
    
    Args:
        tree: AST tree from parser
        file_path: Path to the file being analyzed
        content: File content
        **kwargs: Additional context
        
    Returns:
        List of security findings
    """
    findings = []
    
    if not tree or not content:
        return findings
    
    # Check if this is a React file
    is_react = (
        'import React' in content or
        'from "react"' in content or
        "from 'react'" in content or
        'jsx' in content.lower() or
        'useState' in content or
        'useEffect' in content
    )
    
    if not is_react:
        return findings
    
    # Pattern 1: Check for dangerouslySetInnerHTML
    dangerous_html = _find_dangerous_html(content)
    for line_num in dangerous_html:
        findings.append({
            "pattern_name": "react-dangerous-html",
            "type": "REACT_DANGEROUS_HTML",
            "message": "Use of dangerouslySetInnerHTML - primary XSS vector in React",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "xss",
            "snippet": "dangerouslySetInnerHTML={{__html: ...}}"
        })
    
    # Pattern 2: Check for exposed API keys
    exposed_keys = _find_exposed_api_keys(content)
    for line_num, key_name in exposed_keys:
        findings.append({
            "pattern_name": "react-exposed-api-keys",
            "type": "REACT_EXPOSED_API_KEYS",
            "message": f"Exposed API key '{key_name}' in frontend code - will be in client bundle",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "security",
            "snippet": f"{key_name} exposed in client code"
        })
    
    # Pattern 3: Check for eval with JSX
    eval_jsx = _find_eval_jsx(content)
    for line_num in eval_jsx:
        findings.append({
            "pattern_name": "react-eval-jsx",
            "type": "REACT_EVAL_JSX",
            "message": "Using eval with JSX - code injection vulnerability",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "critical",
            "category": "injection",
            "snippet": "eval() with JSX content"
        })
    
    # Pattern 4: Check for unsafe target="_blank"
    unsafe_links = _find_unsafe_target_blank(content)
    for line_num in unsafe_links:
        findings.append({
            "pattern_name": "react-unsafe-target-blank",
            "type": "REACT_UNSAFE_TARGET_BLANK",
            "message": "External link without rel='noopener' - reverse tabnabbing vulnerability",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "medium",
            "category": "security",
            "snippet": "Add rel='noopener noreferrer' to target='_blank'"
        })
    
    # Pattern 5: Check for direct innerHTML manipulation
    direct_html = _find_direct_innerhtml(content)
    for line_num in direct_html:
        findings.append({
            "pattern_name": "react-direct-innerhtml",
            "type": "REACT_DIRECT_INNERHTML",
            "message": "Direct innerHTML manipulation in React components - use dangerouslySetInnerHTML or text content",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "xss",
            "snippet": "Direct .innerHTML assignment"
        })
    
    # Pattern 6: Check for unescaped user input
    unescaped = _find_unescaped_user_input(content)
    for line_num, input_source in unescaped:
        findings.append({
            "pattern_name": "react-unescaped-user-input",
            "type": "REACT_UNESCAPED_USER_INPUT",
            "message": f"User input '{input_source}' rendered directly without escaping - potential XSS",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "xss",
            "snippet": f"Escape or sanitize {input_source}"
        })
    
    # Pattern 7: Check for missing CSRF tokens
    missing_csrf = _find_missing_csrf(content)
    for line_num in missing_csrf:
        findings.append({
            "pattern_name": "react-missing-csrf",
            "type": "REACT_MISSING_CSRF",
            "message": "Form submission without CSRF token",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "csrf",
            "snippet": "Add CSRF token to form"
        })
    
    # Pattern 8: Check for hardcoded credentials
    hardcoded = _find_hardcoded_credentials(content)
    for line_num, cred_type in hardcoded:
        findings.append({
            "pattern_name": "react-hardcoded-credentials",
            "type": "REACT_HARDCODED_CREDENTIALS",
            "message": f"Hardcoded {cred_type} in React component",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "critical",
            "category": "security",
            "snippet": f"Move {cred_type} to environment variables"
        })
    
    return findings


def register_taint_patterns(taint_registry):
    """Register React-specific taint patterns.
    
    Args:
        taint_registry: TaintRegistry instance from theauditor.taint.registry
    """
    # React dangerous operations
    REACT_XSS_SINKS = [
        "dangerouslySetInnerHTML",
        "innerHTML",
        "outerHTML",
        "document.write",
        "eval",
        "Function"
    ]
    
    for pattern in REACT_XSS_SINKS:
        taint_registry.register_sink(pattern, "xss", "javascript")
    
    # React user input sources
    REACT_INPUT_SOURCES = [
        "props.user",
        "props.input",
        "props.data",
        "location.search",
        "params.",
        "query.",
        "formData.",
        "useState",
        "useReducer"
    ]
    
    for pattern in REACT_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")


# Helper functions for pattern detection
def _find_dangerous_html(content: str) -> List[int]:
    """Find uses of dangerouslySetInnerHTML."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'dangerouslySetInnerHTML' in line:
            findings.append(i)
    
    return findings


def _find_exposed_api_keys(content: str) -> List[tuple]:
    """Find exposed API keys in frontend code."""
    import re
    findings = []
    lines = content.split('\n')
    
    # Environment variable prefixes that expose to frontend
    frontend_prefixes = ['REACT_APP_', 'NEXT_PUBLIC_', 'VITE_', 'GATSBY_', 'PUBLIC_']
    sensitive_patterns = ['KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'API', 'PRIVATE', 'CREDENTIAL', 'AUTH']
    
    for i, line in enumerate(lines, 1):
        for prefix in frontend_prefixes:
            if prefix in line:
                for pattern in sensitive_patterns:
                    if pattern in line.upper():
                        # Extract the variable name
                        match = re.search(rf'{prefix}[A-Z_]*{pattern}[A-Z_]*', line)
                        if match:
                            findings.append((i, match.group(0)))
                        break
    
    return findings


def _find_eval_jsx(content: str) -> List[int]:
    """Find eval used with JSX."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'eval' in line and any(jsx in line for jsx in ['<', 'jsx', 'JSX', 'React.createElement']):
            findings.append(i)
    
    return findings


def _find_unsafe_target_blank(content: str) -> List[int]:
    """Find links with target="_blank" without rel="noopener"."""
    import re
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'target="_blank"' in line or "target='_blank'" in line or 'target={`_blank`}' in line:
            if 'noopener' not in line and 'noreferrer' not in line:
                findings.append(i)
    
    return findings


def _find_direct_innerhtml(content: str) -> List[int]:
    """Find direct innerHTML manipulation."""
    findings = []
    lines = content.split('\n')
    
    dangerous_patterns = [
        '.innerHTML =',
        '.innerHTML=',
        '.outerHTML =',
        '.outerHTML=',
        'ref.current.innerHTML',
        'document.getElementById',
        'document.querySelector'
    ]
    
    for i, line in enumerate(lines, 1):
        if any(pattern in line for pattern in dangerous_patterns):
            if 'innerHTML' in line and '=' in line:
                findings.append(i)
    
    return findings


def _find_unescaped_user_input(content: str) -> List[tuple]:
    """Find user input rendered without escaping."""
    import re
    findings = []
    lines = content.split('\n')
    
    # User input sources
    input_sources = [
        'props.user',
        'props.input',
        'props.data',
        'location.search',
        'params.',
        'query.',
        'formData.',
        'request.body'
    ]
    
    # Look for JSX rendering of user input
    jsx_pattern = r'\{[^}]*(' + '|'.join(re.escape(src) for src in input_sources) + r')[^}]*\}'
    
    for i, line in enumerate(lines, 1):
        match = re.search(jsx_pattern, line)
        if match and not any(san in line for san in ['sanitize', 'escape', 'DOMPurify', 'clean', 'safe']):
            # Extract the input source
            for src in input_sources:
                if src in match.group(0):
                    findings.append((i, src))
                    break
    
    return findings


def _find_missing_csrf(content: str) -> List[int]:
    """Find forms without CSRF tokens."""
    import re
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Look for POST/PUT/DELETE forms
        if re.search(r'<form[^>]*method\s*=\s*[\'"`](?:POST|PUT|DELETE)[\'"`]', line, re.IGNORECASE):
            # Check if CSRF is mentioned nearby
            context_start = max(0, i - 5)
            context_end = min(len(lines), i + 5)
            context = '\n'.join(lines[context_start:context_end])
            
            if 'csrf' not in context.lower() and 'xsrf' not in context.lower():
                findings.append(i)
    
    return findings


def _find_hardcoded_credentials(content: str) -> List[tuple]:
    """Find hardcoded credentials in React components."""
    import re
    findings = []
    lines = content.split('\n')
    
    credential_patterns = {
        'password': r'password\s*[:=]\s*[\'"`][^\'"`]{8,}[\'"`]',
        'apiKey': r'(?:apiKey|api_key)\s*[:=]\s*[\'"`][^\'"`]{10,}[\'"`]',
        'secret': r'secret\s*[:=]\s*[\'"`][^\'"`]{10,}[\'"`]',
        'token': r'token\s*[:=]\s*[\'"`][^\'"`]{10,}[\'"`]',
        'privateKey': r'(?:privateKey|private_key)\s*[:=]\s*[\'"`][^\'"`]{10,}[\'"`]'
    }
    
    for i, line in enumerate(lines, 1):
        # Skip if using environment variables
        if 'process.env' in line or 'import.meta.env' in line or '${' in line:
            continue
        
        for cred_type, pattern in credential_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings.append((i, cred_type))
                break
    
    return findings