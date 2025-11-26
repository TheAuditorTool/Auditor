"""Indexer configuration - constants and patterns.

This module contains all configuration values for the indexer package.
Organized into logical sections for maintainability.

CRITICAL: This file should contain ONLY configuration constants.
NO business logic, NO regex extraction methods.
Language extractors should use AST-based extraction, not regex.
"""


import os
import re

# =============================================================================
# PERFORMANCE CONFIGURATION
# =============================================================================

def _get_batch_size(env_var: str, default: int, max_value: int) -> int:
    """Get batch size from environment or use default."""
    try:
        value = int(os.environ.get(env_var, default))
        return min(value, max_value)
    except (ValueError, TypeError):
        return default


# Database batch insert size (configurable via environment)
# Higher values = fewer database commits = faster indexing
# But consumes more memory
DEFAULT_BATCH_SIZE = _get_batch_size('THEAUDITOR_DB_BATCH_SIZE', 200, 5000)
MAX_BATCH_SIZE = 5000  # Hard cap for safety

# JavaScript/TypeScript batch parsing size
# TypeScript compiler is memory-intensive, so keep batches smaller
# Higher values = fewer compiler processes = faster
# But can cause memory issues with large files
JS_BATCH_SIZE = _get_batch_size('THEAUDITOR_JS_BATCH_SIZE', 20, 100)


# =============================================================================
# FILE SYSTEM CONFIGURATION
# =============================================================================

# Directories to always skip during indexing
# These are build artifacts, dependencies, or caches
SKIP_DIRS: set[str] = {
    # Version control
    ".git",
    ".hg",
    ".svn",

    # Dependencies
    "node_modules",

    # Build artifacts
    "dist",
    "build",
    "out",
    "target",  # Rust/Java

    # Python virtual environments
    ".venv",
    ".auditor_venv",  # TheAuditor's own sandbox
    ".venv_wsl",
    "venv",
    "virtualenv",

    # Python caches
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".egg-info",
    "*.egg-info",

    # JavaScript framework artifacts
    ".next",  # Next.js
    ".nuxt",  # Nuxt.js

    # Coverage reports
    "coverage",
    ".coverage",
    "htmlcov",

    # TheAuditor output
    ".pf",  # All TheAuditor artifacts

    # IDE/Editor
    ".claude",
    ".vscode",
    ".idea",
}

# Monorepo detection patterns (DETECTION ONLY - NOT A WHITELIST)
# Used to identify monorepo structure for metadata purposes.
# Does NOT limit which directories are scanned - SKIP_DIRS is the ONLY filter.
# Security tools MUST scan operational code (scripts/, tests/, configs).
# Tuples of (base_directory, source_subdirectory)
# None for source_subdirectory means check all subdirectories
STANDARD_MONOREPO_PATHS: list[tuple[str, str]] = [
    ("backend", "src"),
    ("frontend", "src"),
    ("mobile", "src"),
    ("server", "src"),
    ("client", "src"),
    ("web", "src"),
    ("api", "src"),
    ("packages", None),  # Lerna/Yarn workspaces
    ("apps", None),      # Nx/Turborepo
]

# Root-level entry files in monorepos
# These files at project root indicate monorepo structure
MONOREPO_ENTRY_FILES: list[str] = [
    "app.ts",
    "app.js",
    "index.ts",
    "index.js",
    "server.ts",
    "server.js"
]


# =============================================================================
# FILE TYPE CONFIGURATION
# =============================================================================

# File extensions that support AST parsing
SUPPORTED_AST_EXTENSIONS: list[str] = [
    ".py",       # Python
    ".js",       # JavaScript
    ".jsx",      # React JavaScript
    ".ts",       # TypeScript
    ".tsx",      # React TypeScript
    ".mjs",      # ES Module JavaScript
    ".cjs",      # CommonJS JavaScript
    ".tf",       # Terraform/HCL
    ".tfvars",   # Terraform variables
    ".graphql",  # GraphQL SDL
    ".gql",      # GraphQL SDL (short)
    ".graphqls", # GraphQL SDL (schema)
]

# SQL file extensions
SQL_EXTENSIONS: list[str] = [
    ".sql",
    ".psql",    # PostgreSQL
    ".ddl",     # Data Definition Language
]

# Dockerfile patterns (case-insensitive matching)
DOCKERFILE_PATTERNS: list[str] = [
    'dockerfile',
    'dockerfile.dev',
    'dockerfile.prod',
    'dockerfile.test',
]

# Docker Compose file patterns
COMPOSE_PATTERNS: list[str] = [
    'docker-compose.yml',
    'docker-compose.yaml',
    'docker-compose.override.yml',
    'docker-compose.override.yaml',
    'compose.yml',
    'compose.yaml',
]

# Nginx config file patterns
NGINX_PATTERNS: list[str] = [
    'nginx.conf',
    'default.conf',
    'site.conf',
]


# =============================================================================
# SECURITY PATTERN CONFIGURATION
# =============================================================================

# Docker security: Sensitive ports that should not be exposed
SENSITIVE_PORTS: list[str] = [
    '22',    # SSH
    '23',    # Telnet
    '135',   # Windows RPC
    '139',   # NetBIOS
    '445',   # SMB
    '3389',  # RDP
]

# Docker security: Keywords indicating sensitive environment variables
SENSITIVE_ENV_KEYWORDS: list[str] = [
    'SECRET',
    'TOKEN',
    'PASSWORD',
    'API_KEY',
    'PRIVATE_KEY',
    'ACCESS_KEY',
]


# =============================================================================
# STRING-BASED EXTRACTION PATTERNS
# =============================================================================
# These patterns are for CONFIG FILES and situations where AST is not available.
# Language extractors (Python, JavaScript) should use AST-based extraction instead.
# =============================================================================

# Route definitions (inherently string-based in most frameworks)
ROUTE_PATTERNS: list[re.Pattern] = [
    # Express/Fastify/Koa style
    re.compile(r"(?:app|router)\.(get|post|put|patch|delete|all)\s*\(['\"`]([^'\"`]+)['\"`]"),

    # Python Flask/FastAPI decorator style
    re.compile(r"@(?:app\.)?(get|post|put|patch|delete|route)\s*\(['\"`]([^'\"`]+)['\"`]\)"),

    # Java Spring decorator style
    re.compile(r"@(Get|Post|Put|Patch|Delete|RequestMapping)\s*\(['\"`]([^'\"`]+)['\"`]\)"),
    re.compile(r"@(GET|POST|PUT|PATCH|DELETE)\s*\(['\"`]([^'\"`]+)['\"`]\)"),
]

# SQL DDL patterns for .sql files (table/index/view creation)
# These are for actual .sql files, not code files
SQL_PATTERNS: list[re.Pattern] = [
    re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)", re.IGNORECASE),
    re.compile(r"CREATE\s+POLICY\s+(\w+)", re.IGNORECASE),
    re.compile(r"CONSTRAINT\s+(\w+)", re.IGNORECASE),
]

# JWT API call patterns
# These are well-defined and have low false positive rates
JWT_SIGN_PATTERN: re.Pattern = re.compile(
    r'(?:jwt|jsonwebtoken)\.sign\s*\(\s*'
    r'([^,)]+)\s*,\s*'       # arg0: payload
    r'([^,)]+)\s*'            # arg1: secret
    r'(?:,\s*([^)]+))?\s*\)', # arg2: options (optional)
    re.DOTALL
)

JWT_VERIFY_PATTERN: re.Pattern = re.compile(
    r'(?:jwt|jsonwebtoken)\.verify\s*\(\s*'
    r'([^,)]+)\s*,\s*'        # arg0: token
    r'([^,)]+)\s*'            # arg1: secret
    r'(?:,\s*([^)]+))?\s*\)', # arg2: options (optional)
    re.DOTALL
)

JWT_DECODE_PATTERN: re.Pattern = re.compile(
    r'(?:jwt|jsonwebtoken)\.decode\s*\(\s*([^)]+)\s*\)',
    re.DOTALL
)
