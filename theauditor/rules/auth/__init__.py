"""Authentication and authorization security rules."""

from .jwt_analyze import find_jwt_flaws
from .session_analyze import find_session_issues
from .password_analyze import find_password_issues
from .oauth_analyze import find_oauth_issues

__all__ = ["find_jwt_flaws", "find_session_issues", "find_password_issues", "find_oauth_issues"]
