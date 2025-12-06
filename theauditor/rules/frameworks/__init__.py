"""Framework Security Analyzers."""

from .express_analyze import analyze as find_express_issues
from .fastapi_analyze import analyze as find_fastapi_issues
from .flask_analyze import analyze as find_flask_issues
from .nextjs_analyze import analyze as find_nextjs_issues
from .react_analyze import analyze as find_react_issues
from .vue_analyze import analyze as find_vue_issues

__all__ = [
    "find_express_issues",
    "find_fastapi_issues",
    "find_flask_issues",
    "find_nextjs_issues",
    "find_react_issues",
    "find_vue_issues",
]
