"""Python AST extraction - Modular architecture (Phase 2.1 - Oct 2025).

⚠️  IMPORTANT: THIS IS THE SINGLE SOURCE OF TRUTH FOR PYTHON EXTRACTION ⚠️

This package is imported as `python_impl` throughout the codebase:
  - Base AST parser: `from . import python as python_impl` (ast_extractors/__init__.py:51)
  - Python extractor: `from theauditor.ast_extractors import python as python_impl` (indexer/extractors/python.py:28)

OLD architecture (DEPRECATED):
  - python_impl.py (1594-line monolithic file) - kept for rollback only, NOT used in production

NEW architecture (ACTIVE):
  - This package (__init__.py) orchestrates modular extraction
  - All functions re-exported here for backward compatibility
  - Acts like JavaScript's js_helper_templates.py pattern (but with Python imports, not file reads)

Module Boundaries:
==================

core_extractors.py (812 lines):
    - Language fundamentals: imports, functions, classes, assignments
    - Core patterns: properties, calls, returns, exports
    - Type annotations and helper functions

framework_extractors.py (568 lines):
    - Web frameworks: Django, Flask, FastAPI
    - ORM frameworks: SQLAlchemy, Django ORM
    - Validators: Pydantic
    - Background tasks: Celery (Phase 2.2)

cdk_extractor.py (NEW - AWS CDK support):
    - AWS CDK Infrastructure-as-Code: CDK v2 construct extraction
    - Security property extraction for cloud infrastructure

cfg_extractor.py (290 lines):
    - Control Flow Graph extraction
    - Matches JavaScript cfg_extractor.js pattern

async_extractors.py: (Phase 2.2 - NOT YET IMPLEMENTED)
    - Async functions, await expressions
    - Async context managers, async generators
    - AsyncIO patterns

testing_extractors.py: (Phase 2.2 - NOT YET IMPLEMENTED)
    - pytest fixtures, parametrize, markers
    - unittest patterns, mocking

type_extractors.py: (Phase 2.2 - NOT YET IMPLEMENTED)
    - Advanced type system: Protocol, Generic, TypedDict
    - Literal types, overload decorators

Backward Compatibility (HOUSE OF CARDS - but it works!):
=========================================================
All functions are re-exported at package level for backward compatibility.
Existing code using `from python_impl import extract_*` will continue working
via re-exports in this __init__.py.

The import alias `python as python_impl` ensures ALL code paths use THIS package,
not the old python_impl.py monolith. This is the glue holding the refactor together.

Architecture Contract (CRITICAL - DO NOT VIOLATE):
==================================================
All extraction functions:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.

For Future Developers (AI and Human):
======================================
If you're reading this wondering "why are there two python_impl things?":
  1. python_impl.py = OLD monolith (DEPRECATED, kept for rollback)
  2. python/ package = NEW modular structure (THIS FILE - production)
  3. Import alias makes them interchangeable: `from . import python as python_impl`
  4. This is intentional technical debt - don't "fix" it without understanding the import chain

Verification Commands:
======================
# Test import resolution works correctly:
python -c "from theauditor.ast_extractors import python_impl; print(python_impl.__file__)"
# Should print: .../theauditor/ast_extractors/python/__init__.py (NOT python_impl.py)

# Test function availability:
python -c "from theauditor.ast_extractors import python_impl; print(hasattr(python_impl, 'extract_python_cdk_constructs'))"
# Should print: True (this function only exists in NEW package)
"""

# Phase 2.1: Import from modular structure
from .core_extractors import (
    # Core extraction functions
    extract_python_functions,
    extract_python_classes,
    extract_python_attribute_annotations,
    extract_python_imports,
    extract_python_exports,
    extract_python_assignments,
    extract_python_function_params,
    extract_python_calls_with_args,
    extract_python_returns,
    extract_python_properties,
    extract_python_calls,
    extract_python_dicts,
)

from .framework_extractors import (
    # Framework extraction functions
    extract_sqlalchemy_definitions,
    extract_django_definitions,
    extract_pydantic_validators,
    extract_flask_blueprints,
    # Constants and helpers (for backward compatibility)
    FASTAPI_HTTP_METHODS,
    _extract_fastapi_dependencies,
)

from .cfg_extractor import (
    # CFG extraction functions
    extract_python_cfg,
)

from .cdk_extractor import (
    # AWS CDK Infrastructure-as-Code extraction
    extract_python_cdk_constructs,
)

# Backward compatibility: re-export all functions at package level
__all__ = [
    # Core extractors
    'extract_python_functions',
    'extract_python_classes',
    'extract_python_attribute_annotations',
    'extract_python_imports',
    'extract_python_exports',
    'extract_python_assignments',
    'extract_python_function_params',
    'extract_python_calls_with_args',
    'extract_python_returns',
    'extract_python_properties',
    'extract_python_calls',
    'extract_python_dicts',
    # Framework extractors
    'extract_sqlalchemy_definitions',
    'extract_django_definitions',
    'extract_pydantic_validators',
    'extract_flask_blueprints',
    # CFG extractor
    'extract_python_cfg',
    # CDK extractor
    'extract_python_cdk_constructs',
]
