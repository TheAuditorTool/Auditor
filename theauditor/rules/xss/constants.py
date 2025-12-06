"""XSS Detection Constants - Single Source of Truth."""

COMMON_INPUT_SOURCES = frozenset(
    [
        "req.body",
        "req.query",
        "req.params",
        "req.cookies",
        "req.headers",
        "request.body",
        "request.query",
        "request.params",
        "request.cookies",
        "location.search",
        "location.hash",
        "location.href",
        "location.pathname",
        "URLSearchParams",
        "searchParams",
        "document.cookie",
        "localStorage.getItem",
        "sessionStorage.getItem",
        "window.name",
        "document.referrer",
        "document.URL",
        ".value",
        "event.data",
        "message.data",
        "postMessage",
        "request.",
        "req.",
        "params.",
        "query.",
        "body.",
        "user.",
        "input.",
        "data.",
        "form.",
        "GET[",
        "POST[",
        "REQUEST[",
        "COOKIE[",
        "location.",
        "window.",
        "document.",
    ]
)


VUE_INPUT_SOURCES = frozenset(
    [
        "$route.params",
        "$route.query",
        "$route.hash",
        "props.",
        "this.props",
        "data.",
        "this.data",
        "$attrs",
        "$listeners",
        "localStorage.getItem",
        "sessionStorage.getItem",
        "document.cookie",
        "window.location",
        "$refs.",
        "event.target.value",
    ]
)


REACT_INPUT_SOURCES = frozenset(
    [
        "props.",
        "this.props.",
        "state.",
        "this.state.",
        "location.search",
        "location.hash",
        "match.params",
        "params.",
        "query.",
        "searchParams.",
        "localStorage.getItem",
        "sessionStorage.getItem",
        "document.cookie",
        "window.name",
        "event.target.value",
        "e.target.value",
        "ref.current.value",
        "useParams(",
        "useSearchParams(",
    ]
)


UNIVERSAL_DANGEROUS_SINKS = frozenset(
    [
        "innerHTML",
        "outerHTML",
        "document.write",
        "document.writeln",
        "eval",
        "Function",
        "setTimeout",
        "setInterval",
        "execScript",
        "insertAdjacentHTML",
        "createContextualFragment",
        "parseFromString",
        "writeln",
        "documentElement.innerHTML",
    ]
)


EXPRESS_SAFE_SINKS = frozenset(
    [
        "res.json",
        "res.jsonp",
        "res.status().json",
        "response.json",
        "response.jsonp",
        "response.status().json",
    ]
)

REACT_AUTO_ESCAPED = frozenset(
    ["React.createElement", "jsx", "JSXElement", "createElement", "cloneElement"]
)

REACT_DANGEROUS_PATTERNS = frozenset(
    [
        "dangerouslySetInnerHTML",
        "__html",
        "href=javascript:",
        "href={'javascript:",
        'href={"javascript:',
    ]
)

VUE_AUTO_ESCAPED = frozenset(
    ["createVNode", "h", "createElementVNode", "createTextVNode", "createCommentVNode"]
)

ANGULAR_AUTO_ESCAPED = frozenset(["sanitize", "DomSanitizer.sanitize"])

ANGULAR_BYPASS_SECURITY = frozenset(
    [
        "bypassSecurityTrustHtml",
        "bypassSecurityTrustScript",
        "bypassSecurityTrustStyle",
        "bypassSecurityTrustUrl",
        "bypassSecurityTrustResourceUrl",
    ]
)


SANITIZER_NAMES = frozenset(
    [
        "DOMPurify.sanitize",
        "sanitize",
        "escape",
        "escapeHtml",
        "encodeURIComponent",
        "encodeURI",
        "encodeHTML",
        "Handlebars.escapeExpression",
        "lodash.escape",
        "_.escape",
        "he.encode",
        "entities.encode",
        "htmlspecialchars",
        "validator.escape",
        "xss.clean",
        "sanitize-html",
        "isomorphic-dompurify",
        "xss-filters",
        "sanitizer.sanitize",
        "Sanitizer",
        "setHTML",
        "bleach.clean",
        "html.escape",
        "cgi.escape",
        "markupsafe.escape",
    ]
)


SANITIZER_CALL_PATTERNS = frozenset(
    [
        "DOMPurify.sanitize(",
        "sanitize(",
        "escape(",
        "escapeHtml(",
        "encodeURIComponent(",
        "encodeURI(",
        "encodeHTML(",
        "Handlebars.escapeExpression(",
        "lodash.escape(",
        "_.escape(",
        "he.encode(",
        "entities.encode(",
        "htmlspecialchars(",
        "validator.escape(",
        "xss.clean(",
        "sanitize-html(",
        "sanitizer.sanitize(",
        "setHTML(",
        "bleach.clean(",
        "html.escape(",
        "markupsafe.escape(",
    ]
)


VUE_DANGEROUS_DIRECTIVES = frozenset(["v-html"])

VUE_SAFE_DIRECTIVES = frozenset(
    [
        "v-text",
        "v-model",
        "v-show",
        "v-if",
        "v-else",
        "v-else-if",
        "v-for",
        "v-bind",
        ":",
        "v-on",
        "@",
    ]
)

VUE_COMPILE_METHODS = frozenset(["Vue.compile", "$compile", "compileToFunctions", "parseComponent"])


TEMPLATE_ENGINES: dict[str, dict[str, frozenset[str]]] = {
    "jinja2": {
        "safe": frozenset(["{{}}", "{%%}"]),
        "unsafe": frozenset(["|safe", "autoescape off", "Markup(", "render_template_string"]),
    },
    "django": {
        "safe": frozenset(["{{}}", "{%%}"]),
        "unsafe": frozenset(["|safe", "autoescape off", "mark_safe", "format_html"]),
    },
    "mako": {"safe": frozenset(["${}", "|h"]), "unsafe": frozenset(["|n", "disable_unicode=True"])},
    "ejs": {"safe": frozenset(["<%= %>"]), "unsafe": frozenset(["<%- %>", "unescape"])},
    "pug": {"safe": frozenset(["#{}"]), "unsafe": frozenset(["!{}", "!{-}", "|"])},
    "handlebars": {"safe": frozenset(["{{}}"]), "unsafe": frozenset(["{{{", "}}}", "SafeString"])},
    "mustache": {"safe": frozenset(["{{}}"]), "unsafe": frozenset(["{{{", "}}}", "&"])},
    "nunjucks": {"safe": frozenset(["{{}}"]), "unsafe": frozenset(["|safe", "autoescape false"])},
    "doT": {"safe": frozenset(["{{!}}"]), "unsafe": frozenset(["{{=}}", "{{#}}"])},
    "lodash": {"safe": frozenset(["<%- %>"]), "unsafe": frozenset(["<%= %>", "<%"])},
    "twig": {"safe": frozenset(["{{}}"]), "unsafe": frozenset(["|raw", "autoescape false"])},
    "blade": {"safe": frozenset(["{{}}"]), "unsafe": frozenset(["{!!", "!!}", "@php"])},
}

TEMPLATE_COMPILE_FUNCTIONS = frozenset(
    [
        "compile",
        "render",
        "render_template",
        "render_template_string",
        "Template",
        "from_string",
        "compileToFunctions",
        "Handlebars.compile",
        "ejs.compile",
        "pug.compile",
        "nunjucks.renderString",
        "doT.template",
        "_.template",
    ]
)


XSS_TARGET_EXTENSIONS = [".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".html"]
VUE_TARGET_EXTENSIONS = [".vue", ".js", ".ts"]
TEMPLATE_TARGET_EXTENSIONS = [".py", ".js", ".ts", ".html", ".ejs", ".pug", ".vue", ".jinja2"]


def is_sanitized(source_expr: str) -> bool:
    """Check if expression contains a sanitizer CALL (not just mention)."""
    return any(pattern in source_expr for pattern in SANITIZER_CALL_PATTERNS)


def contains_user_input(expr: str) -> bool:
    """Check if expression contains any user input source."""
    return any(source in expr for source in COMMON_INPUT_SOURCES)
