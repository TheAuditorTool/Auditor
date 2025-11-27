"""Framework Security Analyzers.

Database-first framework-specific security rules for:
- Express.js (Backend, 10 checks)
- FastAPI (Backend, 11 checks)
- Flask (Backend, 13 checks)
- Next.js (Full-stack, 8 checks)
- React (Frontend, 12 checks)
- Vue.js (Frontend, 8 checks)

Total: 62 security patterns across 6 frameworks.

All rules follow schema contract architecture (v1.1+):
- NO file I/O operations
- Pure SQL queries against repo_index.db
- Frozenset patterns for O(1) lookups
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Standardized contracts (StandardRuleContext -> List[StandardFinding])

Orchestrator Discovery:
- All rules exported with `find_*_issues` naming convention
- Functions starting with `find_` are auto-discovered
- Import this module to access all framework analyzers
"""

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
