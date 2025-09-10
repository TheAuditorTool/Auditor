"""Vue.js framework-specific security analyzer using AST."""

from typing import Any, Dict, List


def find_vue_issues(tree: Any, file_path: str = None, content: str = None, **kwargs) -> List[Dict[str, Any]]:
    """Find Vue.js security issues using AST analysis.
    
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
    
    # Check if this is a Vue file
    is_vue = (
        '.vue' in file_path if file_path else False
    ) or (
        'import Vue' in content or
        'from "vue"' in content or
        "from 'vue'" in content or
        'createApp' in content or
        'defineComponent' in content or
        'v-model' in content or
        'v-if' in content or
        'v-for' in content
    )
    
    if not is_vue:
        return findings
    
    # Pattern 1: Check for v-html directive
    v_html = _find_v_html(content)
    for line_num in v_html:
        findings.append({
            "pattern_name": "vue-v-html",
            "type": "VUE_V_HTML",
            "message": "Use of v-html directive - primary XSS vector in Vue",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "xss",
            "snippet": "v-html can execute arbitrary HTML"
        })
    
    # Pattern 2: Check for v-bind:innerHTML
    v_bind_html = _find_v_bind_innerhtml(content)
    for line_num in v_bind_html:
        findings.append({
            "pattern_name": "vue-v-bind-innerHTML",
            "type": "VUE_V_BIND_INNERHTML",
            "message": "Binding to innerHTML property - XSS vulnerability",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "xss",
            "snippet": "Use v-text or {{ }} instead of innerHTML"
        })
    
    # Pattern 3: Check for eval in templates
    eval_template = _find_eval_template(content)
    for line_num in eval_template:
        findings.append({
            "pattern_name": "vue-eval-template",
            "type": "VUE_EVAL_TEMPLATE",
            "message": "Using eval in Vue template or component - code injection risk",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "critical",
            "category": "injection",
            "snippet": "Remove eval from Vue component"
        })
    
    # Pattern 4: Check for exposed API keys
    exposed_keys = _find_exposed_api_keys(content)
    for line_num, key_name in exposed_keys:
        findings.append({
            "pattern_name": "vue-exposed-api-keys",
            "type": "VUE_EXPOSED_API_KEYS",
            "message": f"Exposed API key '{key_name}' in Vue component",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "security",
            "snippet": f"Move {key_name} to environment variables"
        })
    
    # Pattern 5: Check for unescaped interpolation
    unescaped = _find_unescaped_interpolation(content)
    for line_num in unescaped:
        findings.append({
            "pattern_name": "vue-unescaped-interpolation",
            "type": "VUE_UNESCAPED_INTERPOLATION",
            "message": "Triple mustache {{{ }}} unescaped interpolation - XSS risk",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "xss",
            "snippet": "Use {{ }} instead of {{{ }}}"
        })
    
    # Pattern 6: Check for dynamic component injection
    dynamic_comp = _find_dynamic_component_injection(content)
    for line_num in dynamic_comp:
        findings.append({
            "pattern_name": "vue-dynamic-component-injection",
            "type": "VUE_DYNAMIC_COMPONENT_INJECTION",
            "message": "Dynamic component with user-controlled input - component injection risk",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "injection",
            "snippet": "Validate component name before dynamic loading"
        })
    
    # Pattern 7: Check for unsafe target="_blank"
    unsafe_links = _find_unsafe_target_blank(content)
    for line_num in unsafe_links:
        findings.append({
            "pattern_name": "vue-unsafe-target-blank",
            "type": "VUE_UNSAFE_TARGET_BLANK",
            "message": "External link without rel='noopener' - reverse tabnabbing vulnerability",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "medium",
            "category": "security",
            "snippet": "Add rel='noopener noreferrer'"
        })
    
    # Pattern 8: Check for direct DOM manipulation
    direct_dom = _find_direct_dom_manipulation(content)
    for line_num in direct_dom:
        findings.append({
            "pattern_name": "vue-direct-dom-manipulation",
            "type": "VUE_DIRECT_DOM_MANIPULATION",
            "message": "Direct DOM manipulation bypassing Vue's reactivity system",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "xss",
            "snippet": "Use Vue's data binding instead"
        })
    
    # Pattern 9: Check for missing prop validation
    missing_validation = _find_missing_prop_validation(content)
    for line_num in missing_validation:
        findings.append({
            "pattern_name": "vue-missing-prop-validation",
            "type": "VUE_MISSING_PROP_VALIDATION",
            "message": "Props without type or validation - potential type confusion",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "low",
            "category": "validation",
            "snippet": "Add prop type and validation"
        })
    
    return findings


def register_taint_patterns(taint_registry):
    """Register Vue.js-specific taint patterns.
    
    Args:
        taint_registry: TaintRegistry instance from theauditor.taint.registry
    """
    # Vue XSS sinks
    VUE_XSS_SINKS = [
        "v-html",
        "$refs.innerHTML",
        "innerHTML",
        "outerHTML",
        "v-bind:innerHTML",
        ":innerHTML"
    ]
    
    for pattern in VUE_XSS_SINKS:
        taint_registry.register_sink(pattern, "xss", "javascript")
    
    # Vue user input sources
    VUE_INPUT_SOURCES = [
        "$route.params",
        "$route.query",
        "this.$route",
        "props.",
        "v-model",
        "$emit",
        "$attrs",
        "$listeners"
    ]
    
    for pattern in VUE_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")


# Helper functions for pattern detection
def _find_v_html(content: str) -> List[int]:
    """Find uses of v-html directive."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'v-html' in line:
            findings.append(i)
    
    return findings


def _find_v_bind_innerhtml(content: str) -> List[int]:
    """Find v-bind:innerHTML usage."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if ':innerHTML' in line or 'v-bind:innerHTML' in line:
            findings.append(i)
    
    return findings


def _find_eval_template(content: str) -> List[int]:
    """Find eval in Vue templates or methods."""
    findings = []
    lines = content.split('\n')
    
    # Check if we're in a Vue component section
    in_component = False
    
    for i, line in enumerate(lines, 1):
        # Check if entering Vue component definition
        if any(marker in line for marker in ['template:', 'methods:', 'computed:', 'setup(', 'defineComponent']):
            in_component = True
        
        if in_component and 'eval(' in line:
            findings.append(i)
        
        # Exit component context
        if in_component and line.strip() == '},':
            in_component = False
    
    return findings


def _find_exposed_api_keys(content: str) -> List[tuple]:
    """Find exposed API keys in Vue components."""
    import re
    findings = []
    lines = content.split('\n')
    
    # Vue environment variable prefixes
    vue_prefixes = ['VUE_APP_', 'VITE_']
    sensitive_patterns = ['KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'API', 'PRIVATE']
    
    for i, line in enumerate(lines, 1):
        for prefix in vue_prefixes:
            if prefix in line:
                for pattern in sensitive_patterns:
                    if pattern in line.upper():
                        # Extract variable name
                        match = re.search(rf'{prefix}[A-Z_]*{pattern}[A-Z_]*', line)
                        if match:
                            # Check if it's hardcoded (not from env)
                            if '=' in line and ('process.env' not in line and 'import.meta.env' not in line):
                                findings.append((i, match.group(0)))
                        break
    
    return findings


def _find_unescaped_interpolation(content: str) -> List[int]:
    """Find triple mustache unescaped interpolation."""
    import re
    findings = []
    lines = content.split('\n')
    
    # Look for {{{ }}}
    pattern = r'\{\{\{[^}]+\}\}\}'
    
    for i, line in enumerate(lines, 1):
        if re.search(pattern, line):
            findings.append(i)
    
    return findings


def _find_dynamic_component_injection(content: str) -> List[int]:
    """Find dynamic components with user input."""
    findings = []
    lines = content.split('\n')
    
    dangerous_sources = ['user', 'input', 'data', 'params', 'query', '$route']
    
    for i, line in enumerate(lines, 1):
        if '<component' in line and ':is' in line:
            if any(src in line for src in dangerous_sources):
                findings.append(i)
    
    return findings


def _find_unsafe_target_blank(content: str) -> List[int]:
    """Find links with target="_blank" without rel="noopener"."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'target="_blank"' in line or "target='_blank'" in line:
            if 'noopener' not in line and 'noreferrer' not in line:
                findings.append(i)
    
    return findings


def _find_direct_dom_manipulation(content: str) -> List[int]:
    """Find direct DOM manipulation in Vue components."""
    findings = []
    lines = content.split('\n')
    
    dangerous_patterns = [
        'this.$refs.',
        '$refs.',
        'document.getElementById',
        'document.querySelector',
        'document.getElementsBy'
    ]
    
    for i, line in enumerate(lines, 1):
        for pattern in dangerous_patterns:
            if pattern in line and 'innerHTML' in line:
                findings.append(i)
                break
    
    return findings


def _find_missing_prop_validation(content: str) -> List[int]:
    """Find props without validation."""
    import re
    findings = []
    lines = content.split('\n')
    
    # Look for simple prop arrays (no validation)
    # props: ['prop1', 'prop2']
    array_prop_pattern = r'props\s*:\s*\[[^\]]*[\'"`]\w+[\'"`][^\]]*\]'
    
    for i, line in enumerate(lines, 1):
        if re.search(array_prop_pattern, line):
            findings.append(i)
    
    return findings