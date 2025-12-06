"""Configuration and pattern definitions for dependency analysis rules."""

from dataclasses import dataclass

PYTHON_TYPOSQUATS: frozenset[tuple[str, str]] = frozenset(
    [
        ("requets", "requests"),
        ("request", "requests"),
        ("reques", "requests"),
        ("beautifulsoup", "beautifulsoup4"),
        ("bs4", "beautifulsoup4"),
        ("pillow", "PIL"),
        ("urlib", "urllib3"),
        ("urllib", "urllib3"),
        ("pythondateutil", "python-dateutil"),
        ("python_dateutil", "python-dateutil"),
        ("pyyaml", "PyYAML"),
        ("py-yaml", "PyYAML"),
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("scikit-learn", "sklearn"),
        ("pip-tools", "piptools"),
        ("pytest-cov", "pytestcov"),
        ("python-dotenv", "dotenv"),
        ("django-rest-framework", "djangorestframework"),
        ("django_rest_framework", "djangorestframework"),
        ("celery-beat", "celerybeat"),
        ("celery_beat", "celerybeat"),
    ]
)


JAVASCRIPT_TYPOSQUATS: frozenset[tuple[str, str]] = frozenset(
    [
        ("expres", "express"),
        ("expresss", "express"),
        ("react-dom", "reactdom"),
        ("reactjs", "react"),
        ("vue-router", "vuerouter"),
        ("vuejs", "vue"),
        ("axios", "Axios"),
        ("lodash", "Lodash"),
        ("moment", "Moment"),
        ("jquery", "jQuery"),
        ("webpack", "Webpack"),
        ("babel-core", "babelcore"),
        ("babel_core", "babel-core"),
        ("eslint-config-airbnb", "eslintconfigairbnb"),
        ("prettier-eslint", "prettiereslint"),
        ("typescript", "TypeScript"),
        ("ts-node", "tsnode"),
        ("ts_node", "ts-node"),
        ("next", "nextjs"),
        ("node-fetch", "nodefetch"),
        ("node_fetch", "node-fetch"),
        ("dotenv", "dot-env"),
        ("cross-env", "crossenv"),
        ("cors", "CORS"),
    ]
)


TYPOSQUATTING_MAP: dict[str, str] = dict(PYTHON_TYPOSQUATS | JAVASCRIPT_TYPOSQUATS)


SUSPICIOUS_VERSIONS: frozenset[str] = frozenset(
    [
        "*",
        "latest",
        "x",
        "X",
        "0.0.0",
        "0.0.001",
        "0.0.1-dev",
        "0.0.1-alpha",
        "1.0.0-dev",
        "1.0.0-test",
        "dev",
        "test",
        "snapshot",
        "SNAPSHOT",
        "unknown",
        "UNKNOWN",
        "undefined",
        "null",
        "none",
        "TBD",
        "TODO",
        "master",
        "main",
        "develop",
        "HEAD",
    ]
)


RANGE_PREFIXES: frozenset[str] = frozenset(
    [
        "^",
        "~",
        ">",
        "<",
        ">=",
        "<=",
        "||",
    ]
)


@dataclass(frozen=True)
class DependencyThresholds:
    """Thresholds for dependency analysis rules."""

    MAX_DIRECT_DEPS = 50

    MAX_TRANSITIVE_DEPS = 500

    MAX_DEV_DEPS = 100

    WARN_PRODUCTION_DEPS = 30


PACKAGE_FILES: frozenset[str] = frozenset(
    [
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "requirements.txt",
        "Pipfile",
        "Pipfile.lock",
        "pyproject.toml",
        "poetry.lock",
        "setup.py",
        "setup.cfg",
        "Gemfile",
        "Gemfile.lock",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        "composer.json",
        "composer.lock",
    ]
)


LOCK_FILES: frozenset[str] = frozenset(
    [
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "Gemfile.lock",
        "Cargo.lock",
        "go.sum",
        "composer.lock",
    ]
)


DEV_ONLY_PACKAGES: frozenset[str] = frozenset(
    [
        "webpack",
        "webpack-cli",
        "webpack-dev-server",
        "vite",
        "rollup",
        "parcel",
        "esbuild",
        "turbopack",
        "jest",
        "mocha",
        "chai",
        "jasmine",
        "karma",
        "pytest",
        "unittest",
        "nose",
        "vitest",
        "@testing-library/react",
        "@testing-library/jest-dom",
        "@testing-library/user-event",
        "cypress",
        "playwright",
        "@playwright/test",
        "eslint",
        "prettier",
        "tslint",
        "stylelint",
        "pylint",
        "flake8",
        "black",
        "ruff",
        "typescript",
        "flow-bin",
        "@types/",
        "mypy",
        "pyright",
        "jsdoc",
        "typedoc",
        "sphinx",
        "mkdocs",
        "nodemon",
        "concurrently",
        "npm-run-all",
        "watchman",
        "chokidar",
        "husky",
        "lint-staged",
        "simple-git-hooks",
        "lefthook",
        "storybook",
        "@storybook/react",
        "@storybook/vue3",
        "@storybook/angular",
        "@storybook/addon-essentials",
        "nyc",
        "c8",
        "istanbul",
        "coverage",
    ]
)


FRONTEND_FRAMEWORKS: frozenset[str] = frozenset(
    [
        "react",
        "react-dom",
        "vue",
        "@vue/core",
        "angular",
        "@angular/core",
        "svelte",
        "solid-js",
        "preact",
    ]
)


META_FRAMEWORKS: frozenset[str] = frozenset(
    [
        "next",
        "nuxt",
        "@vue/cli",
    ]
)

BACKEND_FRAMEWORKS: frozenset[str] = frozenset(
    [
        "express",
        "koa",
        "fastify",
        "hapi",
        "django",
        "flask",
        "fastapi",
        "rails",
        "sinatra",
        "spring",
        "quarkus",
    ]
)


__all__ = [
    "TYPOSQUATTING_MAP",
    "PYTHON_TYPOSQUATS",
    "JAVASCRIPT_TYPOSQUATS",
    "SUSPICIOUS_VERSIONS",
    "RANGE_PREFIXES",
    "DependencyThresholds",
    "PACKAGE_FILES",
    "LOCK_FILES",
    "DEV_ONLY_PACKAGES",
    "FRONTEND_FRAMEWORKS",
    "META_FRAMEWORKS",
    "BACKEND_FRAMEWORKS",
]
