"""Configuration and pattern definitions for dependency analysis rules.

This module contains all constant definitions, typosquatting dictionaries,
and pattern frozensets used by dependency security rules.

Design principles:
- Use frozensets for O(1) membership tests
- Keep patterns finite and maintainable
- No regex (use string matching for performance)
"""

from dataclasses import dataclass


# ============================================================================
# TYPOSQUATTING DETECTION PATTERNS
# ============================================================================
# Common typos and malicious package name variations
# Source: Real-world typosquatting attacks from PyPI and npm registries
# ============================================================================

# Python package typos (PyPI)
PYTHON_TYPOSQUATS: frozenset[tuple[str, str]] = frozenset([
    ('requets', 'requests'),
    ('request', 'requests'),
    ('reques', 'requests'),
    ('beautifulsoup', 'beautifulsoup4'),
    ('bs4', 'beautifulsoup4'),  # Not typo but commonly confused
    ('pillow', 'PIL'),  # Reverse - PIL is old name
    ('urlib', 'urllib3'),
    ('urllib', 'urllib3'),
    ('pythondateutil', 'python-dateutil'),
    ('python_dateutil', 'python-dateutil'),
    ('pyyaml', 'PyYAML'),  # Case variation
    ('py-yaml', 'PyYAML'),
    ('numpy', 'NumPy'),  # Case variation (rare but seen)
    ('pandas', 'Pandas'),  # Case variation
    ('scikit-learn', 'sklearn'),  # Reverse - sklearn is alias
    ('pip-tools', 'piptools'),
    ('pytest-cov', 'pytestcov'),
    ('python-dotenv', 'dotenv'),
    ('django-rest-framework', 'djangorestframework'),
    ('django_rest_framework', 'djangorestframework'),
    ('celery-beat', 'celerybeat'),
    ('celery_beat', 'celerybeat'),
])

# JavaScript/Node.js package typos (npm)
JAVASCRIPT_TYPOSQUATS: frozenset[tuple[str, str]] = frozenset([
    ('expres', 'express'),
    ('expresss', 'express'),
    ('react-dom', 'reactdom'),  # Not standard but seen
    ('reactjs', 'react'),
    ('vue-router', 'vuerouter'),
    ('vuejs', 'vue'),
    ('axios', 'Axios'),  # Case variation
    ('lodash', 'Lodash'),  # Case variation
    ('moment', 'Moment'),  # Case variation
    ('jquery', 'jQuery'),  # Case variation
    ('webpack', 'Webpack'),  # Case variation
    ('babel-core', 'babelcore'),
    ('babel_core', 'babel-core'),
    ('eslint-config-airbnb', 'eslintconfigairbnb'),
    ('prettier-eslint', 'prettiereslint'),
    ('typescript', 'TypeScript'),  # Case variation
    ('ts-node', 'tsnode'),
    ('ts_node', 'ts-node'),
    ('next', 'nextjs'),  # Reverse - nextjs not standard
    ('node-fetch', 'nodefetch'),
    ('node_fetch', 'node-fetch'),
    ('dotenv', 'dot-env'),
    ('cross-env', 'crossenv'),
    ('cors', 'CORS'),  # Case variation
])

# Combined typosquatting dictionary (typo -> correct)
TYPOSQUATTING_MAP: dict[str, str] = dict(PYTHON_TYPOSQUATS | JAVASCRIPT_TYPOSQUATS)


# ============================================================================
# SUSPICIOUS VERSION PATTERNS
# ============================================================================
# Version strings that indicate security issues or poor dependency management
# ============================================================================

SUSPICIOUS_VERSIONS: frozenset[str] = frozenset([
    # Wildcard versions (completely unpinned)
    '*',
    'latest',
    'x',
    'X',

    # Development/test versions
    '0.0.0',
    '0.0.001',
    '0.0.1-dev',
    '0.0.1-alpha',
    '1.0.0-dev',
    '1.0.0-test',
    'dev',
    'test',
    'snapshot',
    'SNAPSHOT',

    # Unknown/placeholder versions
    'unknown',
    'UNKNOWN',
    'undefined',
    'null',
    'none',
    'TBD',
    'TODO',

    # Git references (should use commit SHAs, not branches)
    'master',
    'main',
    'develop',
    'HEAD',
])

# Version range prefixes that indicate unpinned dependencies
RANGE_PREFIXES: frozenset[str] = frozenset([
    '^',  # npm caret (allows minor/patch updates)
    '~',  # npm tilde (allows patch updates)
    '>',  # Greater than (completely open-ended)
    '<',  # Less than (rarely used alone)
    '>=', # Greater or equal (often combined with <)
    '<=', # Less or equal
    '||', # OR operator (multiple ranges)
])


# ============================================================================
# DEPENDENCY BLOAT THRESHOLDS
# ============================================================================
# Limits for dependency health checks
# ============================================================================

@dataclass(frozen=True)
class DependencyThresholds:
    """Thresholds for dependency analysis rules."""

    # Maximum number of direct dependencies before flagging
    MAX_DIRECT_DEPS = 50

    # Maximum number of transitive dependencies (would require lock file parsing)
    MAX_TRANSITIVE_DEPS = 500

    # Maximum number of dev dependencies
    MAX_DEV_DEPS = 100

    # Warn if production dependency count exceeds this
    WARN_PRODUCTION_DEPS = 30


# ============================================================================
# PACKAGE MANAGER DETECTION
# ============================================================================
# File patterns for detecting package managers
# ============================================================================

PACKAGE_FILES: frozenset[str] = frozenset([
    'package.json',
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
    'requirements.txt',
    'Pipfile',
    'Pipfile.lock',
    'pyproject.toml',
    'poetry.lock',
    'setup.py',
    'setup.cfg',
    'Gemfile',
    'Gemfile.lock',
    'Cargo.toml',
    'Cargo.lock',
    'go.mod',
    'go.sum',
    'composer.json',
    'composer.lock',
])

# Lock files (for future transitive dependency analysis)
LOCK_FILES: frozenset[str] = frozenset([
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
    'Pipfile.lock',
    'poetry.lock',
    'Gemfile.lock',
    'Cargo.lock',
    'go.sum',
    'composer.lock',
])


# ============================================================================
# SAFE DEPENDENCY SCOPES
# ============================================================================
# Dependencies that are safe to have in production vs dev-only
# ============================================================================

# Tools that should ONLY be in devDependencies (never in dependencies)
DEV_ONLY_PACKAGES: frozenset[str] = frozenset([
    # Build tools
    'webpack', 'webpack-cli', 'webpack-dev-server',
    'vite', 'rollup', 'parcel',
    'esbuild', 'turbopack',

    # Testing
    'jest', 'mocha', 'chai', 'jasmine', 'karma',
    'pytest', 'unittest', 'nose',
    'vitest', '@testing-library/react',

    # Linters/formatters
    'eslint', 'prettier', 'tslint', 'stylelint',
    'pylint', 'flake8', 'black', 'ruff',

    # Type checking
    'typescript', 'flow-bin', '@types/',
    'mypy', 'pyright',

    # Documentation
    'jsdoc', 'typedoc', 'sphinx', 'mkdocs',

    # Development servers
    'nodemon', 'concurrently', 'npm-run-all',
    'watchman', 'chokidar',
])


# ============================================================================
# FRAMEWORK DETECTION HELPERS
# ============================================================================
# Common framework packages for context-aware rules
# ============================================================================

FRONTEND_FRAMEWORKS: frozenset[str] = frozenset([
    'react', 'react-dom',
    'vue', '@vue/core',
    'angular', '@angular/core',
    'svelte',
    'solid-js',
    'preact',
])

# Meta-frameworks built on top of frontend frameworks
META_FRAMEWORKS: frozenset[str] = frozenset([
    'next',      # React meta-framework
    'nuxt',      # Vue meta-framework
    '@vue/cli',  # Vue CLI (build tool/framework hybrid)
])

BACKEND_FRAMEWORKS: frozenset[str] = frozenset([
    'express', 'koa', 'fastify', 'hapi',
    'django', 'flask', 'fastapi',
    'rails', 'sinatra',
    'spring', 'quarkus',
])


# ============================================================================
# EXPORT CONSTANTS
# ============================================================================

__all__ = [
    'TYPOSQUATTING_MAP',
    'PYTHON_TYPOSQUATS',
    'JAVASCRIPT_TYPOSQUATS',
    'SUSPICIOUS_VERSIONS',
    'RANGE_PREFIXES',
    'DependencyThresholds',
    'PACKAGE_FILES',
    'LOCK_FILES',
    'DEV_ONLY_PACKAGES',
    'FRONTEND_FRAMEWORKS',
    'META_FRAMEWORKS',
    'BACKEND_FRAMEWORKS',
]
