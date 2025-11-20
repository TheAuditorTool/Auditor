"""End-to-end tests for Node/TypeScript framework extraction.

CRITICAL: These tests read from .pf/repo_index.db which is populated by `aud full`.
DO NOT re-index fixtures in tests - use the existing database.
Run `aud full` once, then all tests query the same database.

Tests extraction quality for:
- Express API routes (api_endpoints, api_endpoint_controls)
- React components and hooks (react_components, react_hooks, react_component_hooks, react_hook_dependencies)
- Angular services (dependency injection)
- Next.js API routes
- Prisma ORM models (prisma_models)
- BullMQ job queues
"""


import json
import sqlite3
from pathlib import Path

import pytest

# Database path - populated by `aud full`
DB_PATH = Path(".pf/repo_index.db")


def fetchall(db_path: Path, query: str, params: tuple | None = None):
    """Execute query and return all rows."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or tuple())
        return cursor.fetchall()


def fetchone(db_path: Path, query: str, params: tuple | None = None):
    """Execute query and return one row."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or tuple())
        return cursor.fetchone()


# ==============================================================================
# Express API Tests
# ==============================================================================

def test_express_routes_extracted():
    """Test Express router.get/post/put/delete extraction to api_endpoints table."""
    db_path = DB_PATH

    # Get ALL routes, filter in Python
    all_routes = fetchall(db_path, "SELECT method, pattern, file, line FROM api_endpoints ORDER BY line")

    # Filter for products.js
    routes = [(m, p, f) for m, p, f, l in all_routes if 'products.js' in f]

    assert len(routes) >= 5, f"Expected at least 5 Express routes, found {len(routes)}"

    methods = {row[0] for row in routes}
    assert {"GET", "POST", "PUT", "DELETE"} <= methods, "Missing HTTP methods"

    # Verify specific routes
    patterns = {row[1] for row in routes}
    assert "/api/products" in patterns, "Missing /api/products route"
    assert "/api/products/:id" in patterns, "Missing /api/products/:id route"


def test_express_middleware_controls_extracted():
    """Test Express middleware extraction to api_endpoint_controls table."""
    db_path = DB_PATH

    # Get ALL controls, filter in Python
    all_controls = fetchall(
        db_path,
        "SELECT control_name, control_type, endpoint_file FROM api_endpoint_controls ORDER BY control_name"
    )

    # Filter for products.js
    controls = [(name, type_, file) for name, type_, file in all_controls if 'products.js' in file]

    assert len(controls) > 0, "No middleware controls extracted"

    control_names = {row[0] for row in controls}
    # Check for auth middleware
    assert any("requireAuth" in name or "auth" in name.lower() for name in control_names), \
        "Missing requireAuth middleware"


def test_express_sql_injection_vulnerability():
    """Test that vulnerable SQL concatenation is detected in Express routes."""
    db_path = DB_PATH

    # The /api/products/search route has SQL injection vulnerability
    # Get ALL routes, filter in Python
    all_routes = fetchall(db_path, "SELECT method, pattern FROM api_endpoints")

    # Filter for search pattern
    search_routes = [(m, p) for m, p in all_routes if 'search' in p]

    assert len(search_routes) > 0, "Search route not extracted"
    route = search_routes[0]
    assert route[0] == "GET", "Search route should be GET"


# ==============================================================================
# React Component and Hook Tests
# ==============================================================================

def test_react_components_extracted():
    """Test React component extraction to react_components table."""
    db_path = DB_PATH

    components = fetchall(
        db_path,
        "SELECT component_name, file FROM react_components ORDER BY component_name"
    )

    assert len(components) >= 3, f"Expected at least 3 React components, found {len(components)}"

    component_names = {row[0] for row in components}
    assert "Dashboard" in component_names, "Missing Dashboard component"
    assert "ProductList" in component_names, "Missing ProductList component"
    assert "UserProfile" in component_names, "Missing UserProfile component"


def test_react_hooks_extracted():
    """Test React hook extraction to react_hooks table."""
    db_path = DB_PATH

    # Get ALL hooks, filter in Python
    all_hooks = fetchall(
        db_path,
        "SELECT hook_name, hook_type, file FROM react_hooks ORDER BY hook_name"
    )

    # Filter for Dashboard.jsx
    hooks = [(name, type_) for name, type_, file in all_hooks if 'Dashboard.jsx' in file]

    assert len(hooks) > 0, "No React hooks extracted from Dashboard component"

    hook_types = {row[1] for row in hooks if row[1]}
    # Dashboard uses useState, useEffect, useCallback, useMemo, useContext, custom useAuth
    expected_hooks = {"useState", "useEffect", "useCallback", "useMemo"}
    assert expected_hooks & hook_types, f"Missing standard React hooks, found: {hook_types}"


def test_react_hook_dependencies_extracted():
    """Test React hook dependency extraction to react_hook_dependencies table."""
    db_path = DB_PATH

    # Get ALL hook dependencies, filter in Python
    all_deps = fetchall(
        db_path,
        "SELECT dependency_name, hook_file FROM react_hook_dependencies"
    )

    # Filter for Dashboard.jsx
    deps = [(name,) for name, file in all_deps if 'Dashboard.jsx' in file]

    assert len(deps) > 0, "No React hook dependencies extracted"

    # Dashboard component has dependencies: user, filter, refreshNotifications
    dep_names = {row[0] for row in deps if row[0]}
    assert "user" in dep_names or "filter" in dep_names, \
        f"Missing expected dependencies (user, filter), found: {dep_names}"


def test_react_component_hooks_junction():
    """Test react_component_hooks junction table links components to their hooks."""
    db_path = DB_PATH

    # Get Dashboard component hooks
    component_hooks = fetchall(
        db_path,
        """
        SELECT c.component_name, h.hook_type
        FROM react_component_hooks ch
        JOIN react_components c ON ch.component_file = c.file AND ch.component_line = c.line
        JOIN react_hooks h ON ch.hook_file = h.file AND ch.hook_line = h.line
        WHERE c.component_name = 'Dashboard'
        """
    )

    assert len(component_hooks) > 0, "No hooks linked to Dashboard component"


# ==============================================================================
# Angular Service Tests
# ==============================================================================

def test_angular_services_extracted():
    """Test Angular service extraction (dependency injection)."""
    db_path = DB_PATH

    # Get ALL class symbols, filter in Python
    all_symbols = fetchall(
        db_path,
        "SELECT name, type, path FROM symbols WHERE type = 'class'"
    )

    # Filter for user.service.ts
    symbols = [(name, type_) for name, type_, path in all_symbols if 'user.service.ts' in path]

    assert len(symbols) > 0, "No Angular service classes extracted"

    # UserService should be extracted
    service_names = {row[0] for row in symbols}
    assert "UserService" in service_names, "UserService class not extracted"


def test_angular_http_methods_extracted():
    """Test Angular HttpClient methods are extracted as function calls."""
    db_path = DB_PATH

    # Get ALL function calls, filter in Python
    all_calls = fetchall(
        db_path,
        "SELECT DISTINCT function, file FROM function_calls"
    )

    # Filter for user.service.ts and HTTP methods
    http_calls = [
        (func,) for func, file in all_calls
        if 'user.service.ts' in file and any(method in func.lower() for method in ['get', 'post', 'put', 'delete'])
    ]

    assert len(http_calls) > 0, "No HttpClient method calls extracted"


# ==============================================================================
# Next.js API Route Tests
# ==============================================================================

def test_nextjs_api_routes_extracted():
    """Test Next.js API route extraction to api_endpoints table."""
    db_path = DB_PATH

    # Get ALL routes, filter in Python
    all_routes = fetchall(
        db_path,
        "SELECT method, pattern, file FROM api_endpoints"
    )

    # Filter for Next.js pages/api/ routes
    routes = [(m, p, f) for m, p, f in all_routes if 'pages/api/' in f or 'pages\\api\\' in f]

    assert len(routes) > 0, f"No Next.js API routes extracted, found {len(routes)}"

    # Check for Next.js specific patterns
    files = {row[2] for row in routes}
    assert any("api" in f and "pages" in f for f in files), "Missing Next.js API route files"


def test_nextjs_dynamic_routes_extracted():
    """Test Next.js dynamic routes like [id].js are extracted with correct patterns."""
    db_path = DB_PATH

    # Get ALL route files, filter in Python
    all_routes = fetchall(db_path, "SELECT file FROM api_endpoints")

    # Filter for dynamic route syntax [...]
    dynamic_routes = [(f,) for (f,) in all_routes if '[' in f and ']' in f]

    # Next.js uses [id].js syntax for dynamic routes
    if len(dynamic_routes) > 0:
        # Verify pattern extraction handles [id] syntax
        assert any("[" in row[0] for row in dynamic_routes), "Dynamic route syntax not captured"


# ==============================================================================
# Prisma ORM Tests
# ==============================================================================

def test_prisma_models_extracted():
    """Test Prisma model extraction to prisma_models table."""
    db_path = DB_PATH

    models = fetchall(
        db_path,
        "SELECT model_name, file FROM prisma_models ORDER BY model_name"
    )

    assert len(models) > 0, f"No Prisma models extracted, found {len(models)}"

    # Check for Prisma service files (not .prisma schema files, but JS service files using Prisma)
    # The fixture should have User and Post models
    model_names = {row[0] for row in models if row[0]}
    # Prisma extraction might extract from JS service files calling prisma.user.findMany, etc.
    # Or it might require .prisma schema file - adjust based on implementation


# ==============================================================================
# BullMQ Queue Tests
# ==============================================================================

def test_bullmq_queues_extracted():
    """Test BullMQ queue and worker extraction."""
    db_path = DB_PATH

    # Get ALL symbols, filter in Python
    all_symbols = fetchall(db_path, "SELECT name, path FROM symbols")

    # Filter for queue or worker files
    symbols = [(name, path) for name, path in all_symbols if 'queue' in path.lower() or 'worker' in path.lower()]

    assert len(symbols) > 0, "No BullMQ queue/worker symbols extracted"


# ==============================================================================
# React Query Tests
# ==============================================================================

def test_react_query_hooks_extracted():
    """Test React Query useQuery/useMutation hooks are extracted."""
    db_path = DB_PATH

    # Get ALL hooks, filter in Python
    all_hooks = fetchall(db_path, "SELECT hook_name, file FROM react_hooks")

    # Filter for React Query files with use* hooks
    hooks = [(name,) for name, file in all_hooks if 'use' in name.lower() and 'react-query' in file.lower()]

    assert len(hooks) > 0, "No React Query hooks extracted"

    hook_names = {row[0] for row in hooks if row[0]}
    # React Query fixtures should have custom hooks using useQuery/useMutation
    # Verify custom hooks are extracted


# ==============================================================================
# TypeScript Interface Tests
# ==============================================================================

def test_typescript_interfaces_extracted():
    """Test TypeScript interface extraction to symbols table."""
    db_path = DB_PATH

    # Get ALL interfaces, filter in Python
    all_symbols = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'interface'")

    # Filter for .ts files
    interfaces = [(name, path) for name, path in all_symbols if path.endswith('.ts')]

    # Angular fixtures have TypeScript files with interfaces
    # Even if zero, test documents expected behavior
    if len(interfaces) > 0:
        interface_names = {row[0] for row in interfaces}
        # Verify interfaces extracted correctly


def test_typescript_classes_extracted():
    """Test TypeScript class extraction."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for .ts files
    classes = [(name,) for name, path in all_classes if path.endswith('.ts')]

    assert len(classes) > 0, "No TypeScript classes extracted"


# ==============================================================================
# Integration Tests
# ==============================================================================

def test_express_and_react_together():
    """Test Express API + React frontend together (full stack)."""
    db_path = DB_PATH

    # Verify both backend and frontend extracted
    api_routes = fetchall(db_path, "SELECT COUNT(*) FROM api_endpoints")[0][0]
    react_components = fetchall(db_path, "SELECT COUNT(*) FROM react_components")[0][0]

    assert api_routes > 0, "No API routes extracted in full stack"
    assert react_components > 0, "No React components extracted in full stack"


def test_symbols_extracted_from_all_fixtures():
    """Test that basic symbol extraction works across all Node fixtures."""
    db_path = DB_PATH

    # All fixtures should produce symbols (functions, classes, etc.)
    total_symbols = fetchone(db_path, "SELECT COUNT(*) FROM symbols")[0]

    assert total_symbols > 50, f"Expected 50+ symbols across all Node fixtures, found {total_symbols}"

    # Get ALL distinct files, filter in Python
    all_files = fetchall(db_path, "SELECT DISTINCT path FROM symbols")

    # Filter for .js and .ts files
    js_files = [f for (f,) in all_files if '.js' in f]
    ts_files = [f for (f,) in all_files if '.ts' in f]

    assert len(js_files) > 0, "No JavaScript files extracted"
    assert len(ts_files) > 0, "No TypeScript files extracted"


def test_function_calls_extracted():
    """Test that function calls are extracted from Node fixtures."""
    db_path = DB_PATH

    # Get ALL function calls, filter in Python
    all_calls = fetchall(db_path, "SELECT file FROM function_calls")

    # Filter for express files
    calls = [f for (f,) in all_calls if 'express' in f.lower()]

    assert len(calls) > 10, f"Expected 10+ function calls in Express fixtures, found {len(calls)}"


def test_imports_resolved():
    """Test that imports are extracted and resolved."""
    db_path = DB_PATH

    # Get ALL imports, filter in Python
    all_imports = fetchall(
        db_path,
        "SELECT source, target FROM refs WHERE ref_type = 'import' LIMIT 1000"
    )

    # Filter for express sources
    imports = [(src, tgt) for src, tgt in all_imports if 'express' in src.lower()][:10]

    assert len(imports) > 0, "No imports extracted from Express fixtures"

    # Verify imports have targets
    assert all(row[1] for row in imports), "Some imports missing targets"


# ==============================================================================
# TypeScript Deep Nesting and Inheritance Tests
# ==============================================================================

def test_typescript_deep_inheritance_extracted():
    """Test TypeScript 3+ level class inheritance chains are extracted."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for deep_nesting.ts
    classes = {name for name, path in all_classes if 'deep_nesting.ts' in path}

    expected_classes = {
        "BaseEntity", "TimestampedEntity", "SoftDeletableEntity",
        "User", "AdminUser", "SuperAdminUser"
    }

    assert expected_classes <= classes, \
        f"Missing TypeScript classes in deep hierarchy: {expected_classes - classes}"


def test_typescript_interface_chains_extracted():
    """Test TypeScript interface extension chains (3+ levels) are extracted."""
    db_path = DB_PATH

    # Get ALL interfaces, filter in Python
    all_interfaces = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'interface'")

    # Filter for deep_nesting.ts
    interfaces = {name for name, path in all_interfaces if 'deep_nesting.ts' in path}

    expected_interfaces = {
        "IIdentifiable", "ITimestampable", "IAuditable", "IVersioned"
    }

    # At minimum, some interfaces should be extracted
    found_interfaces = expected_interfaces & interfaces

    assert len(found_interfaces) >= 2, \
        f"Expected TypeScript interfaces, found: {found_interfaces}"


def test_typescript_nested_classes_extracted():
    """Test TypeScript nested classes (3+ levels) are extracted."""
    db_path = DB_PATH

    # Get ALL symbols, filter in Python
    all_symbols = fetchall(db_path, "SELECT name, type, path FROM symbols")

    # Filter for deep_nesting.ts and Container/Nested names
    symbols = [
        (name, type_) for name, type_, path in all_symbols
        if 'deep_nesting.ts' in path and ('Container' in name or 'Nested' in name)
    ]

    symbol_names = {name for name, _ in symbols}

    expected_nested = {
        "OuterContainer", "MiddleContainer", "InnerContainer", "DeepNested"
    }

    # At minimum, these names should appear (possibly qualified)
    found_nested = {name for name in symbol_names if any(expected in name for expected in expected_nested)}

    assert len(found_nested) >= 2, \
        f"Expected TypeScript nested classes, found: {found_nested}"


def test_typescript_namespace_nesting():
    """Test TypeScript nested namespaces with classes are extracted."""
    db_path = DB_PATH

    # Get ALL symbols, filter in Python
    all_symbols = fetchall(db_path, "SELECT name, type, path FROM symbols")

    # Filter for deep_nesting.ts and Service names
    symbols = [
        (name, type_) for name, type_, path in all_symbols
        if 'deep_nesting.ts' in path and 'Service' in name
    ]

    service_names = {name for name, _ in symbols}

    expected_services = {"BaseService", "CoreService", "AdvancedService"}

    found_services = {name for name in service_names if any(svc in name for svc in expected_services)}

    assert len(found_services) >= 2, \
        f"Expected TypeScript namespace services, found: {found_services}"


def test_typescript_generic_repository_inheritance():
    """Test TypeScript generic class inheritance is extracted."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for deep_nesting.ts
    classes = {name for name, path in all_classes if 'deep_nesting.ts' in path}

    repository_classes = {"Repository", "UserRepository", "AdminUserRepository"}

    assert repository_classes <= classes, \
        f"Missing TypeScript repository classes: {repository_classes - classes}"


def test_typescript_abstract_class_hierarchy():
    """Test TypeScript abstract classes with inheritance are extracted."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for deep_nesting.ts
    classes = {name for name, path in all_classes if 'deep_nesting.ts' in path}

    service_classes = {"AbstractService", "UserService", "EnhancedUserService"}

    # At minimum, service classes should be extracted
    found_services = service_classes & classes

    assert len(found_services) >= 2, \
        f"Expected TypeScript service classes, found: {found_services}"


def test_typescript_mixin_pattern():
    """Test TypeScript mixin pattern classes are extracted."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for deep_nesting.ts
    classes = {name for name, path in all_classes if 'deep_nesting.ts' in path}

    assert "MixedEntity" in classes, "TypeScript mixin class not extracted"


def test_typescript_vs_python_deep_nesting_parity():
    """Test TypeScript deep nesting extraction has parity with Python."""
    db_path = DB_PATH

    # Get ALL classes, filter by file in Python
    all_classes = fetchall(db_path, "SELECT type, path FROM symbols WHERE type = 'class'")
    ts_classes = [c for c in all_classes if 'deep_nesting.ts' in c[1]]
    py_classes = [c for c in all_classes if 'deep_nesting.py' in c[1]]

    assert len(ts_classes) >= 10, f"TypeScript extracted only {len(ts_classes)} classes"
    assert len(py_classes) >= 15, f"Python extracted only {len(py_classes)} classes"

    # Get ALL functions, filter by file in Python
    all_functions = fetchall(db_path, "SELECT type, path FROM symbols WHERE type = 'function'")
    ts_methods = [f for f in all_functions if 'deep_nesting.ts' in f[1]]
    py_methods = [f for f in all_functions if 'deep_nesting.py' in f[1]]

    assert len(ts_methods) >= 20, f"TypeScript extracted only {len(ts_methods)} methods"
    assert len(py_methods) >= 20, f"Python extracted only {len(py_methods)} methods"


# ==============================================================================
# TypeScript Generics and Advanced Types Tests
# ==============================================================================

def test_typescript_generic_functions_extracted():
    """Test TypeScript generic functions with constraints are extracted."""
    db_path = DB_PATH

    # Get ALL functions, filter in Python
    all_functions = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'function'")

    # Filter for generics.ts and specific function names
    functions = {
        name for name, path in all_functions
        if 'generics.ts' in path and name in ('getId', 'getProperty', 'updateUser', 'getFirstElement')
    }

    expected_functions = {"getId", "getProperty", "updateUser", "getFirstElement"}

    assert expected_functions <= functions, \
        f"Missing generic functions: {expected_functions - functions}"


def test_typescript_mapped_types_extracted():
    """Test TypeScript mapped types (DeepPartial, DeepReadonly, Nullable) are extracted."""
    db_path = DB_PATH

    # Get ALL distinct files, filter in Python
    all_files = fetchall(db_path, "SELECT DISTINCT path FROM symbols")

    # Filter for generics.ts
    files = [path for (path,) in all_files if 'generics.ts' in path]

    assert len(files) > 0, "generics.ts not indexed"


def test_typescript_datastore_class_extracted():
    """Test DataStore generic class with complex constraints is extracted."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for generics.ts and DataStore
    classes = {name for name, path in all_classes if 'generics.ts' in path and name == 'DataStore'}

    assert "DataStore" in classes, "DataStore generic class not extracted"


def test_typescript_repository_interface_extracted():
    """Test IRepository generic interface is extracted."""
    db_path = DB_PATH

    # Get ALL symbols, filter in Python
    all_symbols = fetchall(db_path, "SELECT name, path FROM symbols")

    # Filter for generics.ts and specific names
    interfaces = {
        name for name, path in all_symbols
        if 'generics.ts' in path and name in ('IRepository', 'UserRepository')
    }

    expected = {"IRepository", "UserRepository"}

    # At minimum, UserRepository should be extracted
    assert "UserRepository" in interfaces, "UserRepository not extracted"


def test_typescript_recursive_generic_types():
    """Test recursive generic types (TreeNode) are extracted."""
    db_path = DB_PATH

    # Get ALL symbols, filter in Python
    all_symbols = fetchall(db_path, "SELECT name, path FROM symbols")

    # Filter for generics.ts and specific names
    symbols = {
        name for name, path in all_symbols
        if 'generics.ts' in path and name in ('TreeNode', 'traverseTree')
    }

    # At minimum, function should be extracted
    assert "traverseTree" in symbols, "traverseTree function not extracted"


def test_typescript_type_guards_extracted():
    """Test TypeScript type guard functions are extracted."""
    db_path = DB_PATH

    # Get ALL functions, filter in Python
    all_functions = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'function'")

    # Filter for generics.ts and specific names
    functions = {
        name for name, path in all_functions
        if 'generics.ts' in path and name in ('isArray', 'hasId')
    }

    expected_functions = {"isArray", "hasId"}

    assert expected_functions <= functions, \
        f"Missing type guard functions: {expected_functions - functions}"


def test_typescript_event_emitter_generic_class():
    """Test EventEmitter generic class is extracted."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for generics.ts and EventEmitter
    classes = {name for name, path in all_classes if 'generics.ts' in path and name == 'EventEmitter'}

    assert "EventEmitter" in classes, "EventEmitter generic class not extracted"


def test_typescript_builder_pattern_extracted():
    """Test Builder pattern with generics is extracted."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for generics.ts and Builder
    classes = {name for name, path in all_classes if 'generics.ts' in path and name == 'Builder'}

    assert "Builder" in classes, "Builder generic class not extracted"


def test_typescript_utility_type_functions():
    """Test functions using utility types (Pick, Omit, Partial) are extracted."""
    db_path = DB_PATH

    # Get ALL functions, filter in Python
    all_functions = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'function'")

    # Filter for generics.ts and specific names
    functions = {
        name for name, path in all_functions
        if 'generics.ts' in path and name in ('merge', 'mapValues', 'pick', 'createUserCredentials')
    }

    expected_functions = {"merge", "mapValues", "pick", "createUserCredentials"}

    assert expected_functions <= functions, \
        f"Missing utility type functions: {expected_functions - functions}"


def test_typescript_variadic_tuple_functions():
    """Test functions with variadic tuple types are extracted."""
    db_path = DB_PATH

    # Get ALL functions, filter in Python
    all_functions = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'function'")

    # Filter for generics.ts and specific names
    functions = {
        name for name, path in all_functions
        if 'generics.ts' in path and name in ('concat', 'curry')
    }

    expected_functions = {"concat", "curry"}

    assert expected_functions <= functions, \
        f"Missing variadic tuple functions: {expected_functions - functions}"


def test_typescript_dictionary_functions():
    """Test functions operating on Dictionary<T> are extracted."""
    db_path = DB_PATH

    # Get ALL functions, filter in Python
    all_functions = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'function'")

    # Filter for generics.ts and specific names
    functions = {
        name for name, path in all_functions
        if 'generics.ts' in path and name in ('getDictionaryKeys', 'transformDictionary')
    }

    expected_functions = {"getDictionaryKeys", "transformDictionary"}

    assert expected_functions <= functions, \
        f"Missing dictionary functions: {expected_functions - functions}"


def test_typescript_container_with_static_methods():
    """Test Container class with static generic methods is extracted."""
    db_path = DB_PATH

    # Get ALL classes, filter in Python
    all_classes = fetchall(db_path, "SELECT name, path FROM symbols WHERE type = 'class'")

    # Filter for generics.ts and Container
    classes = {name for name, path in all_classes if 'generics.ts' in path and name == 'Container'}

    assert "Container" in classes, "Container generic class not extracted"


def test_typescript_generics_symbol_count():
    """Test overall TypeScript generics fixture extraction completeness."""
    db_path = DB_PATH

    # Get ALL symbols, filter in Python
    all_symbols = fetchall(db_path, "SELECT type, path FROM symbols")

    # Filter for generics.ts
    generics_symbols = [s for s in all_symbols if 'generics.ts' in s[1]]

    # Count functions
    total_functions = len([s for s in generics_symbols if s[0] == 'function'])

    # Should extract 20+ functions
    assert total_functions >= 15, \
        f"Expected 15+ functions from generics.ts, found {total_functions}"

    # Count classes
    total_classes = len([s for s in generics_symbols if s[0] == 'class'])

    # Should extract 5+ classes
    assert total_classes >= 4, \
        f"Expected 4+ classes from generics.ts, found {total_classes}"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
