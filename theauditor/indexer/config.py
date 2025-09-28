"""Centralized configuration for the indexer.

All constants, patterns, and configuration values used across the indexer
package are defined here.
"""

import re

# Directories to skip (always ignored)
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    "out",
    ".venv",
    ".auditor_venv",  # TheAuditor's isolated virtual environment
    ".venv_wsl",  # WSL virtual environments
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",  # Rust
    ".next",  # Next.js
    ".nuxt",  # Nuxt
    "coverage",
    ".coverage",
    "htmlcov",
    ".tox",
    ".egg-info",
    "__pycache__",
    "*.egg-info",
    ".pf",  # TheAuditor's own output directory (contains all artifacts now)
    ".claude",  # Claude integration directory
}

# Compiled regex patterns for extraction
IMPORT_PATTERNS = [
    # JavaScript/TypeScript
    re.compile(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"import\s*\(['\"]([^'\"]+)['\"]\)"),
    re.compile(r"require\s*\(['\"]([^'\"]+)['\"]\)"),
    # Python
    re.compile(r"from\s+([^\s]+)\s+import"),
    re.compile(r"import\s+([^\s,]+)"),
    # Go
    re.compile(r'import\s+"([^"]+)"'),
    re.compile(r"import\s+\(\s*[\"']([^\"']+)[\"']"),
    # Java
    re.compile(r"import\s+([^\s;]+);"),
    re.compile(r"package\s+([^\s;]+);"),
    # Ruby
    re.compile(r"require\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"require_relative\s+['\"]([^'\"]+)['\"]"),
]

ROUTE_PATTERNS = [
    # Express/Fastify style
    re.compile(r"(?:app|router)\.(get|post|put|patch|delete|all)\s*\(['\"`]([^'\"`]+)['\"`]"),
    # Decorator style (Python Flask, Java Spring, etc)
    re.compile(r"@(Get|Post|Put|Patch|Delete|RequestMapping)\s*\(['\"`]([^'\"`]+)['\"`]\)"),
    re.compile(r"@(GET|POST|PUT|PATCH|DELETE)\s*\(['\"`]([^'\"`]+)['\"`]\)"),
]

SQL_PATTERNS = [
    re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+POLICY\s+(\w+)", re.IGNORECASE),
    re.compile(r"CONSTRAINT\s+(\w+)", re.IGNORECASE),
]

# Patterns to find SQL query strings in code
SQL_QUERY_PATTERNS = [
    # Multi-line SQL strings (Python, JS, etc.)
    re.compile(r'"""([^"]*(?:SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)[^"]*)"""', re.IGNORECASE | re.DOTALL),
    re.compile(r"'''([^']*(?:SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)[^']*)'''", re.IGNORECASE | re.DOTALL),
    re.compile(r'`([^`]*(?:SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)[^`]*)`', re.IGNORECASE | re.DOTALL),
    # Single-line SQL strings
    re.compile(r'"([^"]*(?:SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)[^"]*)"', re.IGNORECASE),
    re.compile(r"'([^']*(?:SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)[^']*)'", re.IGNORECASE),
    # Common ORM/query builder patterns
    re.compile(r'\.query\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'\.execute\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'\.raw\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE),
]

# JWT-specific patterns for enhanced extraction
JWT_SIGN_PATTERN = re.compile(
    r'(?:jwt|jsonwebtoken)\.sign\s*\(\s*'
    r'([^,)]+)\s*,\s*'       # arg0: payload
    r'([^,)]+)\s*'            # arg1: secret
    r'(?:,\s*([^)]+))?\s*\)', # arg2: options (optional)
    re.DOTALL
)

JWT_VERIFY_PATTERN = re.compile(
    r'(?:jwt|jsonwebtoken)\.verify\s*\(\s*'
    r'([^,)]+)\s*,\s*'        # arg0: token
    r'([^,)]+)\s*'            # arg1: secret
    r'(?:,\s*([^)]+))?\s*\)', # arg2: options (optional)
    re.DOTALL
)

JWT_DECODE_PATTERN = re.compile(
    r'(?:jwt|jsonwebtoken)\.decode\s*\(\s*([^)]+)\s*\)',
    re.DOTALL
)

# Patterns for detecting JWT configuration
JWT_SECRET_PATTERNS = [
    re.compile(r'JWT_SECRET\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'jwtSecret\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'secret:\s*["\']([^"\']+)["\']'),
]

# Default batch size for database operations
DEFAULT_BATCH_SIZE = 200
MAX_BATCH_SIZE = 1000

# File processing batch size for JavaScript/TypeScript
JS_BATCH_SIZE = 20

# Standard monorepo structures to check
STANDARD_MONOREPO_PATHS = [
    ("backend", "src"),      # backend/src
    ("frontend", "src"),     # frontend/src
    ("mobile", "src"),       # mobile/src
    ("server", "src"),       # server/src
    ("client", "src"),       # client/src
    ("web", "src"),          # web/src
    ("api", "src"),          # api/src
    ("packages", None),      # packages/* (for lerna/yarn workspaces)
    ("apps", None),          # apps/* (for nx/turborepo)
]

# Common root-level entry files in monorepos
MONOREPO_ENTRY_FILES = ["app.ts", "app.js", "index.ts", "index.js", "server.ts", "server.js"]

# File extensions supported for AST parsing
SUPPORTED_AST_EXTENSIONS = [".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]

# SQL file extensions
SQL_EXTENSIONS = [".sql", ".psql", ".ddl"]

# Dockerfile name patterns
DOCKERFILE_PATTERNS = ['dockerfile', 'dockerfile.dev', 'dockerfile.prod', 'dockerfile.test']

# Docker Compose file patterns
COMPOSE_PATTERNS = [
    'docker-compose.yml', 'docker-compose.yaml',
    'docker-compose.override.yml', 'docker-compose.override.yaml',
    'compose.yml', 'compose.yaml'
]

# Nginx config file patterns
NGINX_PATTERNS = ['nginx.conf', 'default.conf', 'site.conf']

# Sensitive ports for Docker security analysis
SENSITIVE_PORTS = ['22', '23', '135', '139', '445', '3389']  # SSH, Telnet, SMB, RDP

# Sensitive keywords for Docker ENV security analysis
SENSITIVE_ENV_KEYWORDS = ['SECRET', 'TOKEN', 'PASSWORD', 'API_KEY', 'PRIVATE_KEY', 'ACCESS_KEY']

# ORM method patterns to detect
SEQUELIZE_METHODS = {
    'findAll', 'findOne', 'findByPk', 'findOrCreate',
    'create', 'update', 'destroy', 'bulkCreate', 'bulkUpdate',
    'count', 'max', 'min', 'sum', 'findAndCountAll'
}

PRISMA_METHODS = {
    'findMany', 'findFirst', 'findUnique', 'findUniqueOrThrow',
    'create', 'createMany', 'update', 'updateMany', 'upsert',
    'delete', 'deleteMany', 'count', 'aggregate', 'groupBy'
}

TYPEORM_REPOSITORY_METHODS = {
    'find', 'findOne', 'findOneBy', 'findOneOrFail', 'findBy',
    'findAndCount', 'findAndCountBy', 'save', 'remove', 'delete',
    'update', 'insert', 'create', 'merge', 'preload', 'count',
    'increment', 'decrement', 'restore', 'softRemove'
}

TYPEORM_QB_METHODS = {
    'createQueryBuilder', 'select', 'addSelect', 'where', 'andWhere',
    'orWhere', 'having', 'orderBy', 'groupBy', 'limit', 'take',
    'skip', 'offset', 'getMany', 'getOne', 'getRawMany', 'getRawOne',
    'getManyAndCount', 'getCount', 'execute', 'delete', 'update', 'insert'
}