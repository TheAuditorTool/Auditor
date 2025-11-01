# Design Document: Storage Layer Domain Split Refactor

**Change ID**: `refactor-storage-domain-split`
**Type**: Architecture & Code Organization
**Status**: Design Phase
**Authors**: Claude (Opus AI - Lead Coder)
**Reviewers**: Human (Architect)
**Date**: 2025-01-01

---

## Table of Contents

1. [Context](#1-context)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Architecture Overview](#3-architecture-overview)
4. [Detailed Design](#4-detailed-design)
5. [Domain Boundaries](#5-domain-boundaries)
6. [Implementation Patterns](#6-implementation-patterns)
7. [Data Flow](#7-data-flow)
8. [Trade-Offs & Alternatives](#8-trade-offs--alternatives)
9. [Migration Strategy](#9-migration-strategy)
10. [Testing Strategy](#10-testing-strategy)
11. [Open Questions](#11-open-questions)

---

## 1. Context

### 1.1 Background

TheAuditor's indexer extracts code patterns from multiple languages (Python, JavaScript, TypeScript, Terraform, GraphQL) and stores them in `repo_index.db`. The storage layer (`storage.py`) was created 24 hours ago to separate storage concerns from the orchestration logic.

**Original Design** (from orchestrator.py):
```python
def _store_extracted_data(self, file_path, extracted):
    """God method - 1,169 lines"""
    # All storage logic inline...
```

**Current Design** (storage.py):
```python
class DataStorer:
    """Handler dispatch pattern - 2,127 lines"""
    def __init__(self, db_manager, counts):
        self.handlers = {
            'python_orm_models': self._store_python_orm_models,
            # ... 106 more handlers
        }

    def store(self, file_path, extracted, jsx_pass):
        for data_type, data in extracted.items():
            handler = self.handlers.get(data_type)
            if handler:
                handler(file_path, data, jsx_pass)
```

**Problem**: The file has grown to 2,127 lines with 107 handlers. Python Phase 3 extraction added 41 handlers, and future phases will add more. Without organization, storage.py will become unmaintainable.

### 1.2 Precedent: Schema Refactor

**Commit 5c71739** split `indexer/schema.py` (monolithic) into domain-specific modules:

```
indexer/schemas/
├── __init__.py          # Unified TABLES export
├── core_schema.py       # Language-agnostic tables
├── python_schema.py     # Python-specific tables
├── node_schema.py       # JavaScript/TypeScript tables
├── infrastructure_schema.py  # Terraform, CDK
├── security_schema.py   # JWT, SQL injection
├── frameworks_schema.py # ORM, validation
├── graphql_schema.py    # GraphQL types
├── graphs_schema.py     # Dependency graphs
└── planning_schema.py   # Metadata
```

**Result**: Clean architecture, easy navigation, no breaking changes.

**Insight**: The same pattern can be applied to storage.py with identical benefits.

---

## 2. Goals & Non-Goals

### 2.1 Goals

1. **Maintainability**: Reduce cognitive load by splitting 2,127 lines into domain-focused modules
2. **Navigation**: Enable developers to find handlers by domain (Python → `python_storage.py`)
3. **Scalability**: Create structure that supports future language additions without file bloat
4. **Consistency**: Match schema layer architecture for uniform codebase organization
5. **Zero Breaking Changes**: Maintain 100% backward compatibility with existing code

### 2.2 Non-Goals

1. **Functional Changes**: No behavior modifications, pure code organization
2. **Performance Optimization**: No runtime performance improvements (already fast)
3. **API Redesign**: Public interface (`DataStorer.store()`) remains unchanged
4. **Schema Changes**: No database table or column modifications
5. **Handler Refactoring**: Individual handler logic remains identical

### 2.3 Success Metrics

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| **Lines per file** | 2,127 | <600 | wc -l on all modules |
| **Navigation time** | ~30 sec | <5 sec | Time to locate Python handler |
| **Merge conflicts** | High | Low | Git blame on storage/ vs storage.py |
| **Onboarding clarity** | Poor | Good | Developer feedback |
| **Backward compat** | 100% | 100% | All tests pass unchanged |

---

## 3. Architecture Overview

### 3.1 Current Architecture

```
orchestrator.py
    │
    ├─> DataStorer(db_manager, counts)  [storage.py - 2,127 lines]
    │       │
    │       ├─> _store_python_orm_models()
    │       ├─> _store_python_routes()
    │       ├─> _store_react_hooks()
    │       ├─> _store_terraform_resources()
    │       └─> ... 103 more handlers
    │
    └─> data_storer.store(file_path, extracted, jsx_pass)
```

**Issues**:
- Single 2,127-line file
- 107 handlers with no grouping
- Python/Node/Infrastructure code intermixed
- Difficult to navigate

### 3.2 Target Architecture

```
orchestrator.py
    │
    ├─> DataStorer(db_manager, counts)  [storage/__init__.py - exports]
    │       │
    │       ├─> CoreStorage(db_manager, counts)  [core_storage.py - 420 lines]
    │       │       └─> 21 handlers: imports, symbols, cfg, assignments...
    │       │
    │       ├─> PythonStorage(db_manager, counts)  [python_storage.py - 1,180 lines]
    │       │       └─> 59 handlers: orm, django, flask, celery, pytest...
    │       │
    │       ├─> NodeStorage(db_manager, counts)  [node_storage.py - 300 lines]
    │       │       └─> 15 handlers: react, vue, angular, sequelize, bullmq...
    │       │
    │       └─> InfrastructureStorage(db_manager, counts)  [infrastructure_storage.py - 360 lines]
    │               └─> 12 handlers: terraform, cdk, graphql...
    │
    └─> data_storer.store(file_path, extracted, jsx_pass)
```

**Benefits**:
- 5 focused modules (120-1,180 lines each)
- Clear domain boundaries
- Parallel development enabled
- Easy to locate handlers
- Matches schema architecture

---

## 4. Detailed Design

### 4.1 Module Structure

#### 4.1.1 `storage/__init__.py` (Unified Export)

**Purpose**: Export `DataStorer` class for backward compatibility.

```python
"""Storage layer: Domain-specific handler modules.

This module provides the DataStorer class that dispatches extracted data
to domain-specific storage modules (core, python, node, infrastructure).

Architecture:
- DataStorer: Main orchestrator, delegates to domain modules
- BaseStorage: Shared logic (db_manager, counts, _current_extracted)
- CoreStorage: Language-agnostic handlers (symbols, cfg, assignments)
- PythonStorage: Python framework handlers (django, flask, pytest)
- NodeStorage: JavaScript framework handlers (react, vue, angular)
- InfrastructureStorage: IaC handlers (terraform, cdk, graphql)

Design Pattern:
- Handler dispatch via registry dict (data_type -> handler method)
- Domain modules inherit from BaseStorage
- DataStorer aggregates all domain handlers into unified registry

Usage:
    from theauditor.indexer.storage import DataStorer
    storer = DataStorer(db_manager, counts)
    storer.store(file_path, extracted, jsx_pass=False)
"""

from .base import BaseStorage
from .core_storage import CoreStorage
from .python_storage import PythonStorage
from .node_storage import NodeStorage
from .infrastructure_storage import InfrastructureStorage

class DataStorer:
    """Main storage orchestrator - aggregates domain-specific handlers."""

    def __init__(self, db_manager, counts):
        self.db_manager = db_manager
        self.counts = counts

        # Instantiate domain modules
        self.core = CoreStorage(db_manager, counts)
        self.python = PythonStorage(db_manager, counts)
        self.node = NodeStorage(db_manager, counts)
        self.infrastructure = InfrastructureStorage(db_manager, counts)

        # Aggregate handlers from all domains
        self.handlers = {
            **self.core.handlers,
            **self.python.handlers,
            **self.node.handlers,
            **self.infrastructure.handlers,
        }

    def store(self, file_path: str, extracted: dict, jsx_pass: bool = False):
        """Store extracted data via domain-specific handlers."""
        # Store extracted for cross-cutting access (e.g., resolved_imports)
        self._current_extracted = extracted

        # Propagate to domain modules (for handlers that need it)
        self.core._current_extracted = extracted
        self.python._current_extracted = extracted
        self.node._current_extracted = extracted
        self.infrastructure._current_extracted = extracted

        # JSX pass filtering
        jsx_only_types = {'symbols', 'assignments', 'function_calls', 'returns', 'cfg'}

        for data_type, data in extracted.items():
            if jsx_pass and data_type not in jsx_only_types:
                continue

            handler = self.handlers.get(data_type)
            if handler:
                handler(file_path, data, jsx_pass)
            else:
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] No handler for data type: {data_type}")

__all__ = ["DataStorer"]
```

**Design Decision**: `DataStorer` remains the public API, domain modules are internal implementation detail.

---

#### 4.1.2 `storage/base.py` (Shared Logic)

**Purpose**: Base class with shared dependencies and utilities.

```python
"""Base class for domain-specific storage modules.

Provides shared infrastructure:
- db_manager: DatabaseManager instance for database operations
- counts: Statistics tracking dict (mutated across all handlers)
- _current_extracted: Cross-cutting data access (e.g., resolved_imports)

All domain storage modules (CoreStorage, PythonStorage, etc.) inherit from
this base class to access shared dependencies without duplication.
"""

from typing import Dict, Any

class BaseStorage:
    """Base class for domain-specific storage handlers."""

    def __init__(self, db_manager, counts: Dict[str, int]):
        self.db_manager = db_manager
        self.counts = counts
        self._current_extracted = {}  # Set by DataStorer.store()

    def _debug(self, message: str):
        """Debug logging helper."""
        import os
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG STORAGE] {message}")
```

**Design Decision**: Single base class (not multiple inheritance) for simplicity.

---

#### 4.1.3 `storage/core_storage.py` (21 Core Handlers)

**Purpose**: Language-agnostic handlers used across Python, Node, Rust, etc.

```python
"""Core storage handlers for language-agnostic patterns.

This module contains handlers for code patterns that apply across all languages:
- File tracking: imports, refs
- Code structure: symbols, type_annotations, class_properties
- Data flow: assignments, function_calls, returns
- Security: sql_objects, sql_queries, jwt_patterns
- Control flow: cfg blocks/edges/statements
- Analysis: variable_usage, object_literals

Handler Count: 21
Lines: ~420
"""

import json
import os
from typing import List
from .base import BaseStorage

class CoreStorage(BaseStorage):
    """Core storage handlers for language-agnostic patterns."""

    def __init__(self, db_manager, counts):
        super().__init__(db_manager, counts)

        # Register handlers
        self.handlers = {
            'imports': self._store_imports,
            'routes': self._store_routes,
            'sql_objects': self._store_sql_objects,
            'sql_queries': self._store_sql_queries,
            'cdk_constructs': self._store_cdk_constructs,
            'symbols': self._store_symbols,
            'type_annotations': self._store_type_annotations,
            'orm_queries': self._store_orm_queries,
            'validation_framework_usage': self._store_validation_framework_usage,
            'assignments': self._store_assignments,
            'function_calls': self._store_function_calls,
            'returns': self._store_returns,
            'cfg': self._store_cfg,
            'jwt_patterns': self._store_jwt_patterns,
            'react_components': self._store_react_components,
            'class_properties': self._store_class_properties,
            'env_var_usage': self._store_env_var_usage,
            'orm_relationships': self._store_orm_relationships,
            'variable_usage': self._store_variable_usage,
            'object_literals': self._store_object_literals,
            'package_configs': self._store_package_configs,
        }

    def _store_imports(self, file_path: str, imports: List, jsx_pass: bool):
        """Store imports/references."""
        # ... (copy from storage.py lines 191-206)

    # ... (20 more handlers)
```

**Design Decision**: "Core" = used by multiple languages, not Python-specific.

---

#### 4.1.4 `storage/python_storage.py` (59 Python Handlers)

**Purpose**: All Python framework and pattern handlers.

```python
"""Python storage handlers for framework-specific patterns.

This module contains handlers for Python frameworks and patterns:
- ORM: sqlalchemy, django models, fields
- HTTP: flask routes, django views, fastapi endpoints
- Validation: pydantic, marshmallow, django forms, wtforms, drf
- Testing: unittest, pytest, hypothesis, mocking
- Async: celery tasks, async/await, generators
- Security: auth decorators, password hashing, JWT, injection patterns
- Type System: protocols, generics, typed dicts, overloads

Handler Count: 59
Lines: ~1,180
"""

import json
from typing import List
from .base import BaseStorage

class PythonStorage(BaseStorage):
    """Python-specific storage handlers."""

    def __init__(self, db_manager, counts):
        super().__init__(db_manager, counts)

        self.handlers = {
            # ORM & Routes (6 handlers)
            'python_orm_models': self._store_python_orm_models,
            'python_orm_fields': self._store_python_orm_fields,
            'python_routes': self._store_python_routes,
            'python_blueprints': self._store_python_blueprints,
            'python_django_views': self._store_python_django_views,
            'python_django_forms': self._store_python_django_forms,

            # Django Framework (8 handlers)
            'python_django_form_fields': self._store_python_django_form_fields,
            'python_django_admin': self._store_python_django_admin,
            'python_django_middleware': self._store_python_django_middleware,
            'python_django_signals': self._store_python_django_signals,
            'python_django_receivers': self._store_python_django_receivers,
            'python_django_managers': self._store_python_django_managers,
            'python_django_querysets': self._store_python_django_querysets,

            # Validation Frameworks (6 handlers)
            'python_marshmallow_schemas': self._store_python_marshmallow_schemas,
            'python_marshmallow_fields': self._store_python_marshmallow_fields,
            'python_drf_serializers': self._store_python_drf_serializers,
            'python_drf_serializer_fields': self._store_python_drf_serializer_fields,
            'python_wtforms_forms': self._store_python_wtforms_forms,
            'python_wtforms_fields': self._store_python_wtforms_fields,

            # Async & Celery (7 handlers)
            'python_celery_tasks': self._store_python_celery_tasks,
            'python_celery_task_calls': self._store_python_celery_task_calls,
            'python_celery_beat_schedules': self._store_python_celery_beat_schedules,
            'python_generators': self._store_python_generators,
            'python_async_functions': self._store_python_async_functions,
            'python_await_expressions': self._store_python_await_expressions,
            'python_async_generators': self._store_python_async_generators,

            # Flask Framework - Phase 3.1 (9 handlers)
            'python_flask_apps': self._store_python_flask_apps,
            'python_flask_extensions': self._store_python_flask_extensions,
            'python_flask_hooks': self._store_python_flask_hooks,
            'python_flask_error_handlers': self._store_python_flask_error_handlers,
            'python_flask_websockets': self._store_python_flask_websockets,
            'python_flask_cli_commands': self._store_python_flask_cli_commands,
            'python_flask_cors': self._store_python_flask_cors,
            'python_flask_rate_limits': self._store_python_flask_rate_limits,
            'python_flask_cache': self._store_python_flask_cache,

            # Testing Ecosystem - Phase 3.2 (8 handlers)
            'python_unittest_test_cases': self._store_python_unittest_test_cases,
            'python_assertion_patterns': self._store_python_assertion_patterns,
            'python_pytest_plugin_hooks': self._store_python_pytest_plugin_hooks,
            'python_hypothesis_strategies': self._store_python_hypothesis_strategies,
            'python_pytest_fixtures': self._store_python_pytest_fixtures,
            'python_pytest_parametrize': self._store_python_pytest_parametrize,
            'python_pytest_markers': self._store_python_pytest_markers,
            'python_mock_patterns': self._store_python_mock_patterns,

            # Security Patterns - Phase 3.3 (8 handlers)
            'python_auth_decorators': self._store_python_auth_decorators,
            'python_password_hashing': self._store_python_password_hashing,
            'python_jwt_operations': self._store_python_jwt_operations,
            'python_sql_injection': self._store_python_sql_injection,
            'python_command_injection': self._store_python_command_injection,
            'python_path_traversal': self._store_python_path_traversal,
            'python_dangerous_eval': self._store_python_dangerous_eval,
            'python_crypto_operations': self._store_python_crypto_operations,

            # Type System - Phase 3.4 (7 handlers)
            'python_validators': self._store_python_validators,
            'python_decorators': self._store_python_decorators,
            'python_context_managers': self._store_python_context_managers,
            'python_protocols': self._store_python_protocols,
            'python_generics': self._store_python_generics,
            'python_typed_dicts': self._store_python_typed_dicts,
            'python_literals': self._store_python_literals,
            'python_overloads': self._store_python_overloads,
        }

    def _store_python_orm_models(self, file_path: str, python_orm_models: List, jsx_pass: bool):
        """Store Python ORM models."""
        # ... (copy from storage.py lines 641-653)

    # ... (58 more handlers)
```

**Design Decision**: All `python_*` handlers grouped together for domain expertise.

---

#### 4.1.5 `storage/node_storage.py` (15 Node Handlers)

**Purpose**: JavaScript/TypeScript framework handlers.

```python
"""Node.js storage handlers for JavaScript/TypeScript frameworks.

This module contains handlers for JavaScript/TypeScript frameworks:
- React: components, hooks
- Vue: components, hooks, directives, provide/inject
- Angular: components, services, modules, guards, DI
- ORM: sequelize models/associations
- Queue: bullmq queues/workers
- Build: import styles, lock analysis

Handler Count: 15
Lines: ~300
"""

import json
from typing import List
from .base import BaseStorage

class NodeStorage(BaseStorage):
    """Node.js/JavaScript framework storage handlers."""

    def __init__(self, db_manager, counts):
        super().__init__(db_manager, counts)

        self.handlers = {
            # React (2 handlers)
            'react_hooks': self._store_react_hooks,

            # Vue (4 handlers)
            'vue_components': self._store_vue_components,
            'vue_hooks': self._store_vue_hooks,
            'vue_directives': self._store_vue_directives,
            'vue_provide_inject': self._store_vue_provide_inject,

            # Angular (5 handlers)
            'angular_components': self._store_angular_components,
            'angular_services': self._store_angular_services,
            'angular_modules': self._store_angular_modules,
            'angular_guards': self._store_angular_guards,
            'di_injections': self._store_di_injections,

            # ORM (2 handlers)
            'sequelize_models': self._store_sequelize_models,
            'sequelize_associations': self._store_sequelize_associations,

            # Queue (2 handlers)
            'bullmq_queues': self._store_bullmq_queues,
            'bullmq_workers': self._store_bullmq_workers,

            # Build System (3 handlers - moved from core)
            'import_styles': self._store_import_styles,
            'lock_analysis': self._store_lock_analysis,
        }

    def _store_react_hooks(self, file_path: str, react_hooks: List, jsx_pass: bool):
        """Store React hooks."""
        # ... (copy from storage.py lines 1581-1595)

    # ... (14 more handlers)
```

**Design Decision**: React components handler stays in `core_storage.py` (used for JSX analysis), but react_hooks moves here.

---

#### 4.1.6 `storage/infrastructure_storage.py` (12 Infrastructure Handlers)

**Purpose**: Infrastructure-as-Code and GraphQL handlers.

```python
"""Infrastructure storage handlers for IaC and GraphQL.

This module contains handlers for infrastructure patterns:
- Terraform: files, resources, variables, outputs
- CDK: AWS constructs and properties
- GraphQL: schemas, types, fields, resolvers

Handler Count: 12
Lines: ~360
"""

import json
from typing import List, Dict
from .base import BaseStorage

class InfrastructureStorage(BaseStorage):
    """Infrastructure-as-Code storage handlers."""

    def __init__(self, db_manager, counts):
        super().__init__(db_manager, counts)

        self.handlers = {
            # Terraform (5 handlers)
            'terraform_file': self._store_terraform_file,
            'terraform_resources': self._store_terraform_resources,
            'terraform_variables': self._store_terraform_variables,
            'terraform_variable_values': self._store_terraform_variable_values,
            'terraform_outputs': self._store_terraform_outputs,

            # CDK (1 handler) - Note: cdk_constructs moves to core_storage (AWS infra detection)
            # (Actually stays in core_storage.py due to cross-language usage)

            # GraphQL (6 handlers)
            'graphql_schemas': self._store_graphql_schemas,
            'graphql_types': self._store_graphql_types,
            'graphql_fields': self._store_graphql_fields,
            'graphql_field_args': self._store_graphql_field_args,
            'graphql_resolver_mappings': self._store_graphql_resolver_mappings,
            'graphql_resolver_params': self._store_graphql_resolver_params,
        }

    def _store_terraform_file(self, file_path: str, terraform_file: Dict, jsx_pass: bool):
        """Store Terraform infrastructure definitions."""
        # ... (copy from storage.py lines 1740-1753)

    # ... (11 more handlers)
```

**Design Decision**: CDK constructs stay in `core_storage.py` (cross-language AWS infrastructure detection).

---

## 5. Domain Boundaries

### 5.1 Domain Classification Rules

| Domain | Inclusion Criteria | Examples |
|--------|-------------------|----------|
| **Core** | Used by 2+ languages OR language-agnostic | symbols, cfg, assignments, imports |
| **Python** | Python-only handlers with `python_` prefix | python_orm_models, python_flask_apps |
| **Node** | JavaScript/TypeScript frameworks | react, vue, angular, sequelize |
| **Infrastructure** | IaC and API schemas | terraform, cdk, graphql |

### 5.2 Edge Cases & Decisions

| Handler | Ambiguous? | Decision | Rationale |
|---------|------------|----------|-----------|
| `react_components` | ✅ Yes | **Core** | Used for JSX analysis across languages |
| `react_hooks` | ❌ No | **Node** | React-specific, not cross-language |
| `cdk_constructs` | ✅ Yes | **Core** | AWS infra detection (Python + TypeScript) |
| `orm_queries` | ✅ Yes | **Core** | Generic ORM pattern (Python + Node) |
| `orm_relationships` | ✅ Yes | **Core** | Sequelize + SQLAlchemy both use this |
| `validation_framework_usage` | ✅ Yes | **Core** | Yup (JS) + Pydantic (Python) + Joi (Node) |
| `package_configs` | ✅ Yes | **Core** | package.json + requirements.txt + cargo.toml |
| `lock_analysis` | ❌ No | **Node** | package-lock.json, yarn.lock (Node-specific) |
| `import_styles` | ❌ No | **Node** | ES6 import/require patterns |

### 5.3 Disputed Handlers (Architecture Team Decision Required)

**None identified.** All 107 handlers have clear domain boundaries based on usage patterns.

---

## 6. Implementation Patterns

### 6.1 Handler Registry Pattern

**Current** (storage.py):
```python
class DataStorer:
    def __init__(self, db_manager, counts):
        self.handlers = {
            'python_orm_models': self._store_python_orm_models,
            # ... 106 more
        }
```

**Target** (storage/__init__.py):
```python
class DataStorer:
    def __init__(self, db_manager, counts):
        # Instantiate domain modules
        self.core = CoreStorage(db_manager, counts)
        self.python = PythonStorage(db_manager, counts)
        self.node = NodeStorage(db_manager, counts)
        self.infrastructure = InfrastructureStorage(db_manager, counts)

        # Aggregate handlers
        self.handlers = {
            **self.core.handlers,
            **self.python.handlers,
            **self.node.handlers,
            **self.infrastructure.handlers,
        }
```

**Benefit**: Each domain manages its own registry, DataStorer aggregates.

---

### 6.2 Cross-Cutting Data Pattern

**Problem**: `_store_imports()` needs access to `resolved_imports` from extracted data.

**Current Solution** (storage.py:168-169, 202):
```python
def store(self, file_path, extracted, jsx_pass):
    self._current_extracted = extracted  # Store for handlers

def _store_imports(self, file_path, imports, jsx_pass):
    resolved = self._current_extracted.get('resolved_imports', {}).get(value, value)
```

**Target Solution** (same pattern, propagate to domains):
```python
# storage/__init__.py
def store(self, file_path, extracted, jsx_pass):
    self._current_extracted = extracted

    # Propagate to domain modules
    self.core._current_extracted = extracted
    self.python._current_extracted = extracted
    # ...
```

**Benefit**: Handlers in domain modules can still access cross-cutting data.

---

### 6.3 JSX Pass Filtering Pattern

**Requirement**: JSX preserved mode only processes 5 data types (symbols, assignments, function_calls, returns, cfg).

**Current** (storage.py:172-177):
```python
jsx_only_types = {'symbols', 'assignments', 'function_calls', 'returns', 'cfg'}

for data_type, data in extracted.items():
    if jsx_pass and data_type not in jsx_only_types:
        continue
```

**Target** (same logic, stays in DataStorer):
```python
# storage/__init__.py - DataStorer.store()
jsx_only_types = {'symbols', 'assignments', 'function_calls', 'returns', 'cfg'}

for data_type, data in extracted.items():
    if jsx_pass and data_type not in jsx_only_types:
        continue

    handler = self.handlers.get(data_type)
    if handler:
        handler(file_path, data, jsx_pass)
```

**Benefit**: JSX filtering logic remains centralized in orchestrator.

---

## 7. Data Flow

### 7.1 Storage Operation Flow

```
orchestrator.py
    │
    ├─> IndexerOrchestrator.__init__()
    │       └─> self.data_storer = DataStorer(db_manager, counts)
    │
    ├─> IndexerOrchestrator._process_file(file_path)
    │       ├─> extractor.extract(file_info, content, tree)
    │       │       └─> returns: {'python_orm_models': [...], 'symbols': [...]}
    │       │
    │       └─> self.data_storer.store(file_path, extracted, jsx_pass=False)
    │               │
    │               ├─> DataStorer.store()  [storage/__init__.py]
    │               │       ├─> self._current_extracted = extracted
    │               │       ├─> Propagate to domain modules
    │               │       └─> For each data_type in extracted:
    │               │               ├─> handler = self.handlers.get(data_type)
    │               │               └─> handler(file_path, data, jsx_pass)
    │               │
    │               ├─> CoreStorage._store_symbols(file_path, symbols, jsx_pass)
    │               │       └─> db_manager.add_symbol(...)
    │               │
    │               ├─> PythonStorage._store_python_orm_models(file_path, models, jsx_pass)
    │               │       └─> db_manager.add_python_orm_model(...)
    │               │
    │               └─> ... (105 more handlers)
    │
    └─> db_manager.flush_all_batches()  (after all files processed)
```

### 7.2 Handler Execution Pattern

```python
# orchestrator.py
extracted = extractor.extract(file_info, content, tree)
# extracted = {
#     'symbols': [{'name': 'User', 'type': 'class', 'line': 10}],
#     'python_orm_models': [{'model_name': 'User', 'table_name': 'users', 'line': 10}]
# }

self.data_storer.store(file_path, extracted, jsx_pass=False)

# storage/__init__.py - DataStorer.store()
for data_type, data in extracted.items():
    # data_type = 'symbols', data = [{'name': 'User', ...}]
    handler = self.handlers.get(data_type)  # -> CoreStorage._store_symbols
    handler(file_path, data, jsx_pass)

    # data_type = 'python_orm_models', data = [{'model_name': 'User', ...}]
    handler = self.handlers.get(data_type)  # -> PythonStorage._store_python_orm_models
    handler(file_path, data, jsx_pass)
```

---

## 8. Trade-Offs & Alternatives

### 8.1 Chosen Design: Domain Split with Aggregation

**Pros**:
- ✅ Clear domain boundaries (Python devs → python_storage.py)
- ✅ Matches schema architecture (consistency)
- ✅ Proven pattern (schema refactor success)
- ✅ Easy to navigate (4 domain modules)
- ✅ Backward compatible (no API changes)

**Cons**:
- ⚠️ More files to manage (1 → 5 files)
- ⚠️ Requires handler registry aggregation (minimal complexity)
- ⚠️ Cross-domain handler lookup requires understanding structure

**Trade-Off Accepted**: Navigation benefits outweigh file count increase.

---

### 8.2 Alternative 1: Flat Structure with Naming Convention

**Design**: Keep single file, rename handlers with prefixes: `_CORE_store_symbols()`, `_PYTHON_store_orm_models()`.

**Pros**:
- ✅ No file split required (zero refactor effort)
- ✅ Simple implementation

**Cons**:
- ❌ Still 2,127 lines in single file (cognitive load unchanged)
- ❌ Naming convention is fragile (easy to violate)
- ❌ Doesn't match schema architecture (inconsistent)
- ❌ Doesn't scale (Python Phase 4+ adds more handlers)

**Decision**: ❌ **REJECTED** - Doesn't solve core problem (file size).

---

### 8.3 Alternative 2: Functional Organization (ORM, HTTP, Testing, etc.)

**Design**: Split by functionality: `orm_storage.py`, `http_storage.py`, `testing_storage.py`.

**Pros**:
- ✅ Fine-grained organization
- ✅ Cross-language grouping (Python ORM + Node ORM together)

**Cons**:
- ❌ 10+ files (over-engineered)
- ❌ Python/Node handlers intermixed (cross-domain confusion)
- ❌ Doesn't match schema architecture (inconsistent)
- ❌ Unclear boundaries (is Flask HTTP or Flask framework?)

**Decision**: ❌ **REJECTED** - Too fine-grained, unclear boundaries.

---

### 8.4 Alternative 3: File Extension Split (.py, .js, .tf, etc.)

**Design**: Split by file extension: `python_file_storage.py`, `js_file_storage.py`.

**Pros**:
- ✅ Simple mapping (file extension → storage module)

**Cons**:
- ❌ React/Vue/Angular handlers share .js/.ts but have different concerns
- ❌ GraphQL schemas can be .graphql, .gql, or embedded in .js/.ts/.py
- ❌ Doesn't align with developer expertise (frontend dev needs Vue + React together)
- ❌ Doesn't match schema architecture

**Decision**: ❌ **REJECTED** - File extension doesn't map to domain expertise.

---

### 8.5 Alternative 4: Micro-Modules (1 handler per file)

**Design**: `storage/python_orm_models.py`, `storage/python_routes.py`, etc. (107 files).

**Pros**:
- ✅ Ultimate separation
- ✅ Easy to test individual handlers

**Cons**:
- ❌ 107 files (extreme over-engineering)
- ❌ Import explosion (`from storage.python_orm_models import`, 107 times)
- ❌ Directory navigation nightmare
- ❌ No domain grouping (lose context)

**Decision**: ❌ **REJECTED** - Over-engineered, poor developer experience.

---

## 9. Migration Strategy

### 9.1 Migration Steps

**Phase 1: Setup** (0 breaking changes)
1. Create `storage/` directory
2. Create `storage/base.py` with `BaseStorage` class
3. Test: Import `BaseStorage` → should work

**Phase 2: Core Migration** (0 breaking changes)
4. Create `storage/core_storage.py`
5. Copy 21 core handlers from `storage.py`
6. Inherit from `BaseStorage`
7. Test: Instantiate `CoreStorage` → handlers dict populated

**Phase 3: Python Migration** (0 breaking changes)
8. Create `storage/python_storage.py`
9. Copy 59 Python handlers from `storage.py`
10. Test: Instantiate `PythonStorage` → handlers dict populated

**Phase 4: Node Migration** (0 breaking changes)
11. Create `storage/node_storage.py`
12. Copy 15 Node handlers from `storage.py`
13. Test: Instantiate `NodeStorage` → handlers dict populated

**Phase 5: Infrastructure Migration** (0 breaking changes)
14. Create `storage/infrastructure_storage.py`
15. Copy 12 infrastructure handlers from `storage.py`
16. Test: Instantiate `InfrastructureStorage` → handlers dict populated

**Phase 6: Integration** (1 breaking change - import path)
17. Create `storage/__init__.py` with `DataStorer` aggregator
18. Update `orchestrator.py`: `from .storage import DataStorer` → **NO CHANGE**
19. Delete old `storage.py`
20. Test: `aud index tests/fixtures/python/` → should work identically

### 9.2 Rollback Plan

**If refactor fails**:
1. Revert commit: `git revert HEAD`
2. Old `storage.py` is restored
3. orchestrator.py unchanged (no migration needed)
4. Zero downtime, instant rollback

### 9.3 Validation Tests

**Before Migration**:
```bash
aud index tests/fixtures/python/ > /tmp/before.log
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM python_orm_models;" > /tmp/before_counts.txt
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols;" >> /tmp/before_counts.txt
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM function_call_args;" >> /tmp/before_counts.txt
```

**After Migration**:
```bash
aud index tests/fixtures/python/ > /tmp/after.log
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM python_orm_models;" > /tmp/after_counts.txt
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols;" >> /tmp/after_counts.txt
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM function_call_args;" >> /tmp/after_counts.txt
```

**Verify Identical**:
```bash
diff /tmp/before_counts.txt /tmp/after_counts.txt  # Should be empty
```

---

## 10. Testing Strategy

### 10.1 Unit Tests (New)

Create `tests/test_storage_refactor.py`:

```python
import pytest
from theauditor.indexer.storage import DataStorer
from theauditor.indexer.storage.core_storage import CoreStorage
from theauditor.indexer.storage.python_storage import PythonStorage

def test_data_storer_aggregates_handlers():
    """Verify DataStorer aggregates all domain handlers."""
    db_manager = MockDatabaseManager()
    counts = {}

    storer = DataStorer(db_manager, counts)

    # Verify handler count
    assert len(storer.handlers) == 107, "Should have 107 handlers"

    # Verify core handlers present
    assert 'symbols' in storer.handlers
    assert 'imports' in storer.handlers

    # Verify Python handlers present
    assert 'python_orm_models' in storer.handlers
    assert 'python_flask_apps' in storer.handlers

    # Verify Node handlers present
    assert 'react_hooks' in storer.handlers
    assert 'vue_components' in storer.handlers

def test_domain_modules_independent():
    """Verify domain modules can be instantiated independently."""
    db_manager = MockDatabaseManager()
    counts = {}

    core = CoreStorage(db_manager, counts)
    python = PythonStorage(db_manager, counts)

    assert len(core.handlers) == 21
    assert len(python.handlers) == 59

def test_cross_cutting_data_propagation():
    """Verify _current_extracted propagates to domain modules."""
    db_manager = MockDatabaseManager()
    counts = {}
    storer = DataStorer(db_manager, counts)

    extracted = {'resolved_imports': {'foo': 'bar'}}
    storer.store('/fake/path.py', extracted, jsx_pass=False)

    assert storer.core._current_extracted == extracted
    assert storer.python._current_extracted == extracted
```

### 10.2 Integration Tests (Existing)

Run existing tests to verify no regressions:

```bash
pytest tests/test_indexer.py -v
pytest tests/test_python_extraction.py -v
```

### 10.3 End-to-End Tests

```bash
# Test Python project
aud index tests/fixtures/python/ --verbose

# Test Node project
aud index tests/fixtures/javascript/ --verbose

# Test mixed project
aud index tests/fixtures/mixed/ --verbose
```

---

## 11. Open Questions

### ❓ Question 1: Should react_components stay in core_storage.py?

**Context**: `react_components` is used for JSX analysis, which applies to JavaScript AND TypeScript (cross-language).

**Options**:
- A) Keep in `core_storage.py` (current decision)
- B) Move to `node_storage.py` (framework-specific)

**Recommendation**: **A) Keep in core** - JSX analysis is language-agnostic.

**Decision**: ✅ **RESOLVED** - Keep in core_storage.py

---

### ❓ Question 2: Should we add domain-specific docstrings to each module?

**Context**: Each module could have a detailed docstring explaining domain patterns and handler responsibilities.

**Options**:
- A) Add comprehensive docstrings (example: "Python Storage - SQLAlchemy patterns: Models inherit from Base, fields are Column()")
- B) Keep minimal docstrings (just list handlers)

**Recommendation**: **A) Add comprehensive docstrings** - Improves onboarding and documentation.

**Decision**: ⏳ **AWAITING ARCHITECT APPROVAL**

---

### ❓ Question 3: Should we create domain-specific test suites?

**Context**: Could create `tests/test_python_storage.py`, `tests/test_node_storage.py`, etc.

**Options**:
- A) Create domain-specific test suites (better test organization)
- B) Keep single `tests/test_storage.py` (simpler)

**Recommendation**: **A) Create domain-specific test suites** - Matches module organization.

**Decision**: ⏳ **AWAITING ARCHITECT APPROVAL** (Can be done as follow-up)

---

### ✅ All Critical Questions Resolved

**Status**: Ready for implementation pending architect approval of open questions (non-blocking).

---

## Appendix: Handler Migration Table

| Handler | Current Location | Target Location | Lines |
|---------|------------------|-----------------|-------|
| `_store_imports` | storage.py:191-206 | core_storage.py | 16 |
| `_store_routes` | storage.py:208-226 | core_storage.py | 19 |
| `_store_symbols` | storage.py:276-299 | core_storage.py | 24 |
| `_store_python_orm_models` | storage.py:641-653 | python_storage.py | 13 |
| `_store_python_flask_apps` | storage.py:965-978 | python_storage.py | 14 |
| `_store_react_hooks` | storage.py:1581-1595 | node_storage.py | 15 |
| `_store_terraform_file` | storage.py:1740-1753 | infrastructure_storage.py | 14 |
| ... | | | |
| **TOTAL** | **storage.py (2,127 lines)** | **5 modules (~425 lines avg)** | **2,127** |

**Complete migration table available in tasks.md.**

---

**Design Document Status**: ✅ **COMPLETE**
**Approval Status**: ⏳ **AWAITING ARCHITECT REVIEW**

**Author**: Claude (Opus AI - Lead Coder)
**Date**: 2025-01-01
**Protocol**: OpenSpec + SOP v4.20
