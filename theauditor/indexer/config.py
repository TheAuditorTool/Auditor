"""Indexer configuration - constants and patterns."""

import os
import re


def _get_batch_size(env_var: str, default: int, max_value: int) -> int:
    """Get batch size from environment or use default."""
    try:
        value = int(os.environ.get(env_var, default))
        return min(value, max_value)
    except (ValueError, TypeError):
        return default


DEFAULT_BATCH_SIZE = _get_batch_size("THEAUDITOR_DB_BATCH_SIZE", 200, 5000)
MAX_BATCH_SIZE = 5000


JS_BATCH_SIZE = _get_batch_size("THEAUDITOR_JS_BATCH_SIZE", 20, 100)


SKIP_DIRS: set[str] = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "out",
    "target",
    ".venv",
    ".auditor_venv",
    ".venv_wsl",
    "venv",
    "virtualenv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".egg-info",
    "*.egg-info",
    ".next",
    ".nuxt",
    "coverage",
    ".coverage",
    "htmlcov",
    ".pf",
    ".claude",
    ".vscode",
    ".idea",
}


STANDARD_MONOREPO_PATHS: list[tuple[str, str]] = [
    ("backend", "src"),
    ("frontend", "src"),
    ("mobile", "src"),
    ("server", "src"),
    ("client", "src"),
    ("web", "src"),
    ("api", "src"),
    ("packages", None),
    ("apps", None),
]


MONOREPO_ENTRY_FILES: list[str] = [
    "app.ts",
    "app.js",
    "index.ts",
    "index.js",
    "server.ts",
    "server.js",
]


SUPPORTED_AST_EXTENSIONS: list[str] = [
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".tf",
    ".tfvars",
    ".graphql",
    ".gql",
    ".graphqls",
    ".go",
    ".rs",
    ".sh",
    ".bash",
    ".toml",
    ".mod",
    ".json",
    ".txt",
]


SQL_EXTENSIONS: list[str] = [
    ".sql",
    ".psql",
    ".ddl",
]


DOCKERFILE_PATTERNS: list[str] = [
    "dockerfile",
    "dockerfile.dev",
    "dockerfile.prod",
    "dockerfile.test",
]


COMPOSE_PATTERNS: list[str] = [
    "docker-compose.yml",
    "docker-compose.yaml",
    "docker-compose.override.yml",
    "docker-compose.override.yaml",
    "compose.yml",
    "compose.yaml",
]


NGINX_PATTERNS: list[str] = [
    "nginx.conf",
    "default.conf",
    "site.conf",
]


SENSITIVE_PORTS: list[str] = [
    "22",
    "23",
    "135",
    "139",
    "445",
    "3389",
]


SENSITIVE_ENV_KEYWORDS: list[str] = [
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "API_KEY",
    "PRIVATE_KEY",
    "ACCESS_KEY",
]


ROUTE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?:app|router)\.(get|post|put|patch|delete|all)\s*\(['\"`]([^'\"`]+)['\"`]"),
    re.compile(r"@(?:app\.)?(get|post|put|patch|delete|route)\s*\(['\"`]([^'\"`]+)['\"`]\)"),
    re.compile(r"@(Get|Post|Put|Patch|Delete|RequestMapping)\s*\(['\"`]([^'\"`]+)['\"`]\)"),
    re.compile(r"@(GET|POST|PUT|PATCH|DELETE)\s*\(['\"`]([^'\"`]+)['\"`]\)"),
]


SQL_PATTERNS: list[re.Pattern] = [
    re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+POLICY\s+(\w+)", re.IGNORECASE),
    re.compile(r"CONSTRAINT\s+(\w+)", re.IGNORECASE),
]


JWT_SIGN_PATTERN: re.Pattern = re.compile(
    r"(?:jwt|jsonwebtoken)\.sign\s*\(\s*"
    r"([^,)]+)\s*,\s*"
    r"([^,)]+)\s*"
    r"(?:,\s*([^)]+))?\s*\)",
    re.DOTALL,
)

JWT_VERIFY_PATTERN: re.Pattern = re.compile(
    r"(?:jwt|jsonwebtoken)\.verify\s*\(\s*"
    r"([^,)]+)\s*,\s*"
    r"([^,)]+)\s*"
    r"(?:,\s*([^)]+))?\s*\)",
    re.DOTALL,
)

JWT_DECODE_PATTERN: re.Pattern = re.compile(
    r"(?:jwt|jsonwebtoken)\.decode\s*\(\s*([^)]+)\s*\)", re.DOTALL
)
