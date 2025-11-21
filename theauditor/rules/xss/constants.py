"""XSS Detection Constants - Single Source of Truth.

All XSS-related constants consolidated here to ensure consistency
across xss_analyze.py, vue_xss_analyze.py, and template_xss_analyze.py.

NO DUPLICATES. One brain for sanitizers, sinks, and sources.
"""


# ============================================================================
# USER INPUT SOURCES (Taint Sources)
# ============================================================================

# Common user input across all frameworks
COMMON_INPUT_SOURCES = frozenset([
    # Express/Node.js
    'req.body', 'req.query', 'req.params', 'req.cookies', 'req.headers',
    'request.body', 'request.query', 'request.params', 'request.cookies',
    # Browser APIs
    'location.search', 'location.hash', 'location.href', 'location.pathname',
    'URLSearchParams', 'searchParams', 'document.cookie',
    'localStorage.getItem', 'sessionStorage.getItem',
    'window.name', 'document.referrer', 'document.URL',
    '.value', 'event.data', 'message.data', 'postMessage',
    # Generic
    'request.', 'req.', 'params.', 'query.', 'body.',
    'user.', 'input.', 'data.', 'form.',
    # PHP
    'GET[', 'POST[', 'REQUEST[', 'COOKIE[',
    # Browser
    'location.', 'window.', 'document.'
])

# Vue-specific input sources
VUE_INPUT_SOURCES = frozenset([
    '$route.params', '$route.query', '$route.hash',
    'props.', 'this.props',
    'data.', 'this.data',
    '$attrs', '$listeners',
    'localStorage.getItem', 'sessionStorage.getItem',
    'document.cookie', 'window.location',
    '$refs.', 'event.target.value'
])


# ============================================================================
# DANGEROUS SINKS (XSS Vectors)
# ============================================================================

# Universal dangerous sinks - ALWAYS risky regardless of framework
UNIVERSAL_DANGEROUS_SINKS = frozenset([
    'innerHTML', 'outerHTML', 'document.write', 'document.writeln',
    'eval', 'Function', 'setTimeout', 'setInterval', 'execScript',
    'insertAdjacentHTML', 'createContextualFragment', 'parseFromString',
    'writeln', 'documentElement.innerHTML'
])


# ============================================================================
# FRAMEWORK-SPECIFIC SAFE SINKS (Auto-escaped)
# ============================================================================

EXPRESS_SAFE_SINKS = frozenset([
    'res.json', 'res.jsonp', 'res.status().json',
    'response.json', 'response.jsonp', 'response.status().json'
])

REACT_AUTO_ESCAPED = frozenset([
    'React.createElement', 'jsx', 'JSXElement',
    'createElement', 'cloneElement'
])

VUE_AUTO_ESCAPED = frozenset([
    'createVNode', 'h', 'createElementVNode',
    'createTextVNode', 'createCommentVNode'
])

ANGULAR_AUTO_ESCAPED = frozenset([
    'sanitize', 'DomSanitizer.sanitize',
    'bypassSecurityTrustHtml'  # Actually dangerous, flagged separately
])


# ============================================================================
# SANITIZERS - Single Source of Truth
# ============================================================================

# Base sanitizer names (for reference and pattern building)
SANITIZER_NAMES = frozenset([
    'DOMPurify.sanitize', 'sanitize', 'escape', 'escapeHtml',
    'encodeURIComponent', 'encodeURI', 'encodeHTML',
    'Handlebars.escapeExpression', 'lodash.escape', '_.escape',
    'he.encode', 'entities.encode', 'htmlspecialchars',
    'validator.escape', 'xss.clean', 'sanitize-html'
])

# CRITICAL: Use function call patterns with "(" to prevent false positives
# on definitions like "const escapeHtml = ..." vs usage "escapeHtml(input)"
SANITIZER_CALL_PATTERNS = frozenset([
    'DOMPurify.sanitize(',
    'sanitize(',
    'escape(',
    'escapeHtml(',
    'encodeURIComponent(',
    'encodeURI(',
    'encodeHTML(',
    'Handlebars.escapeExpression(',
    'lodash.escape(',
    '_.escape(',
    'he.encode(',
    'entities.encode(',
    'htmlspecialchars(',
    'validator.escape(',
    'xss.clean(',
    'sanitize-html('
])


# ============================================================================
# VUE-SPECIFIC CONSTANTS
# ============================================================================

VUE_DANGEROUS_DIRECTIVES = frozenset([
    'v-html',  # Raw HTML rendering
    'v-once',  # Combined with v-html can be dangerous
    'v-pre'    # Skips compilation - can expose templates
])

VUE_SAFE_DIRECTIVES = frozenset([
    'v-text',  # Safe text binding
    'v-model',  # Two-way binding (escaped)
    'v-show', 'v-if', 'v-else', 'v-else-if',  # Conditionals
    'v-for',  # Iteration
    'v-bind', ':',  # Attribute binding (mostly safe)
    'v-on', '@'  # Event binding
])

VUE_COMPILE_METHODS = frozenset([
    'Vue.compile', '$compile',
    'compileToFunctions', 'parseComponent'
])


# ============================================================================
# TEMPLATE ENGINE CONSTANTS
# ============================================================================

TEMPLATE_ENGINES: dict[str, dict[str, frozenset[str]]] = {
    # Python template engines
    'jinja2': {
        'safe': frozenset(['{{}}', '{%%}']),
        'unsafe': frozenset(['|safe', 'autoescape off', 'Markup(', 'render_template_string'])
    },
    'django': {
        'safe': frozenset(['{{}}', '{%%}']),
        'unsafe': frozenset(['|safe', 'autoescape off', 'mark_safe', 'format_html'])
    },
    'mako': {
        'safe': frozenset(['${}']),
        'unsafe': frozenset(['|n', '|h', 'disable_unicode=True'])
    },

    # JavaScript template engines
    'ejs': {
        'safe': frozenset(['<%= %>']),
        'unsafe': frozenset(['<%- %>', 'unescape'])
    },
    'pug': {
        'safe': frozenset(['#{}']),
        'unsafe': frozenset(['!{}', '!{-}', '|'])
    },
    'handlebars': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['{{{', '}}}', 'SafeString'])
    },
    'mustache': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['{{{', '}}}', '&'])
    },
    'nunjucks': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['|safe', 'autoescape false'])
    },
    'doT': {
        'safe': frozenset(['{{!}}']),
        'unsafe': frozenset(['{{=}}', '{{#}}'])
    },
    'lodash': {
        'safe': frozenset(['<%- %>']),
        'unsafe': frozenset(['<%= %>', '<%'])
    },

    # PHP template engines
    'twig': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['|raw', 'autoescape false'])
    },
    'blade': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['{!!', '!!}', '@php'])
    }
}

TEMPLATE_COMPILE_FUNCTIONS = frozenset([
    'compile', 'render', 'render_template', 'render_template_string',
    'Template', 'from_string', 'compileToFunctions',
    'Handlebars.compile', 'ejs.compile', 'pug.compile',
    'nunjucks.renderString', 'doT.template', '_.template'
])


# ============================================================================
# FILE EXTENSIONS
# ============================================================================

XSS_TARGET_EXTENSIONS = ['.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.html']
VUE_TARGET_EXTENSIONS = ['.vue', '.js', '.ts']
TEMPLATE_TARGET_EXTENSIONS = ['.py', '.js', '.ts', '.html', '.ejs', '.pug', '.vue', '.jinja2']


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_sanitized(source_expr: str) -> bool:
    """Check if expression contains a sanitizer CALL (not just mention).

    Uses SANITIZER_CALL_PATTERNS to ensure we're checking for actual
    function calls like "escape(input)" not definitions like "const escape = ...".
    """
    return any(pattern in source_expr for pattern in SANITIZER_CALL_PATTERNS)


def contains_user_input(expr: str) -> bool:
    """Check if expression contains any user input source."""
    return any(source in expr for source in COMMON_INPUT_SOURCES)
