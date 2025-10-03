"""Unit tests for extractor modules.

Tests verify ACTUAL behavior of extractors, not documentation claims.
Each test uses real code samples to ensure extractors work correctly.

Test Coverage:
1. PythonExtractor - AST-based import/SQL/route extraction
2. JavaScriptExtractor - Import/SQL/route/auth extraction
3. BaseExtractor - Regex-based JWT/SQL object extraction
"""

import ast
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from theauditor.indexer.extractors import BaseExtractor
from theauditor.indexer.extractors.python import PythonExtractor
from theauditor.indexer.extractors.javascript import JavaScriptExtractor


# ============================================================================
# PythonExtractor Tests
# ============================================================================

class TestPythonExtractor:
    """Unit tests for Python extractor AST-based methods."""

    def test_extract_imports_returns_3tuples(self):
        """Verify imports are 3-tuples (kind, module, line)."""
        extractor = PythonExtractor(root_path=Path('.'))

        code = '''import os
import sys
from pathlib import Path
from typing import Dict, List
'''

        # Parse with Python AST
        tree = ast.parse(code)
        tree_dict = {'tree': tree, 'type': 'python_ast'}

        # Extract imports
        result = extractor._extract_imports_ast(tree_dict)

        # VERIFY: All imports are 3-tuples
        assert len(result) == 4, f"Expected 4 imports, got {len(result)}"
        for imp in result:
            assert len(imp) == 3, f"Import should be 3-tuple, got {len(imp)}-tuple: {imp}"
            kind, module, line = imp
            assert kind in ('import', 'from'), f"Invalid kind: {kind}"
            assert isinstance(module, str), f"Module should be string, got {type(module)}"
            assert isinstance(line, int), f"Line should be int, got {type(line)}"

        # VERIFY: Correct content
        imports_dict = {imp[1]: imp for imp in result}
        assert 'os' in imports_dict
        assert 'sys' in imports_dict
        assert 'pathlib' in imports_dict
        assert 'typing' in imports_dict

        # VERIFY: Correct kinds
        assert imports_dict['os'][0] == 'import'
        assert imports_dict['pathlib'][0] == 'from'

        # VERIFY: Line numbers are sequential
        assert imports_dict['os'][2] == 1
        assert imports_dict['sys'][2] == 2
        assert imports_dict['pathlib'][2] == 3
        assert imports_dict['typing'][2] == 4

    def test_extract_imports_empty_on_ast_failure(self):
        """Verify empty list when AST parsing fails (NOT crash)."""
        extractor = PythonExtractor(root_path=Path('.'))

        # Pass None tree
        result = extractor._extract_imports_ast(None)
        assert result == [], "Should return empty list for None tree"

        # Pass invalid tree type
        result = extractor._extract_imports_ast({'tree': 'invalid', 'type': 'tree_sitter'})
        assert result == [], "Should return empty list for wrong AST type"

        # Pass tree without 'tree' key
        result = extractor._extract_imports_ast({'type': 'python_ast'})
        assert result == [], "Should return empty list for missing tree"

    def test_extract_imports_handles_relative_imports(self):
        """Verify handling of relative imports (from . import X)."""
        extractor = PythonExtractor(root_path=Path('.'))

        code = '''from . import utils
from .. import models
from ...parent import config
'''

        tree = ast.parse(code)
        tree_dict = {'tree': tree, 'type': 'python_ast'}

        result = extractor._extract_imports_ast(tree_dict)

        # VERIFY: No imports with empty module names
        # (Relative imports with module=None are skipped)
        for imp in result:
            _, module, _ = imp
            assert module, f"Module should not be empty: {imp}"

    def test_extract_sql_queries_detects_execute_calls(self):
        """Verify SQL extraction from cursor.execute() calls."""
        extractor = PythonExtractor(root_path=Path('.'))

        code = '''
import sqlite3
conn = sqlite3.connect('db.sqlite')
cursor = conn.cursor()
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
cursor.executemany("INSERT INTO logs (msg) VALUES (?)", rows)
'''

        tree = ast.parse(code)
        tree_dict = {'tree': tree, 'type': 'python_ast'}

        # Extract SQL queries
        result = extractor._extract_sql_queries_ast(tree_dict, code, 'test.py')

        # VERIFY: Found execute calls
        assert len(result) >= 1, f"Should find at least 1 SQL query, got {len(result)}"

        # VERIFY: Each query has required fields
        for query in result:
            assert 'line' in query
            assert 'query_text' in query
            assert 'command' in query
            assert 'tables' in query
            assert 'extraction_source' in query

            # VERIFY: Command is not UNKNOWN
            assert query['command'] != 'UNKNOWN', f"Query should be parseable: {query['query_text']}"

    def test_extract_sql_queries_categorizes_sources(self):
        """Verify extraction_source categorization (migration/ORM/code)."""
        extractor = PythonExtractor(root_path=Path('.'))

        # Test migration file detection
        source = extractor._determine_sql_source('db/migrations/0001_initial.py', 'execute')
        assert source == 'migration_file', f"Should detect migration file, got {source}"

        # Test ORM method detection
        source = extractor._determine_sql_source('models.py', 'filter')
        assert source == 'orm_query', f"Should detect ORM query, got {source}"

        source = extractor._determine_sql_source('views.py', 'create')
        assert source == 'orm_query', f"Should detect ORM create, got {source}"

        # Test code execution
        source = extractor._determine_sql_source('api.py', 'execute')
        assert source == 'code_execute', f"Should detect code execution, got {source}"

    def test_extract_routes_detects_flask_decorators(self):
        """Verify Flask route extraction with decorators."""
        extractor = PythonExtractor(root_path=Path('.'))

        code = '''
from flask import Flask
app = Flask(__name__)

@app.route('/api/users', methods=['GET'])
@login_required
def get_users():
    return jsonify(users)

@app.route('/api/users/<id>', methods=['POST'])
@permission_required('admin')
@auth_required
def update_user(id):
    return jsonify(user)
'''

        tree = ast.parse(code)
        tree_dict = {'tree': tree, 'type': 'python_ast'}

        # Extract routes
        result = extractor._extract_routes_ast(tree_dict, 'app.py')

        # VERIFY: Found 2 routes
        assert len(result) == 2, f"Should find 2 routes, got {len(result)}"

        # VERIFY: Each route has all required fields
        for route in result:
            assert 'line' in route
            assert 'method' in route
            assert 'pattern' in route
            assert 'path' in route
            assert 'has_auth' in route
            assert 'handler_function' in route
            assert 'controls' in route

        # VERIFY: Auth detection
        routes_with_auth = [r for r in result if r['has_auth']]
        assert len(routes_with_auth) == 2, f"Both routes should have auth, got {len(routes_with_auth)}"

        # VERIFY: Handler function names
        handlers = [r['handler_function'] for r in result]
        assert 'get_users' in handlers
        assert 'update_user' in handlers

        # VERIFY: Controls (non-route decorators)
        # First route should have login_required in controls
        route_1 = [r for r in result if r['handler_function'] == 'get_users'][0]
        assert 'login_required' in route_1['controls']

    def test_extract_routes_empty_without_ast(self):
        """Verify empty routes when AST not available."""
        extractor = PythonExtractor(root_path=Path('.'))

        code = '''
@app.route('/test')
def test():
    pass
'''

        # Call extract with no tree
        file_info = {'path': 'test.py'}
        result = extractor.extract(file_info, code, tree=None)

        # VERIFY: Routes use fallback format
        # Fallback returns list but with limited metadata
        assert isinstance(result['routes'], list)

    def test_extract_variable_usage_tracks_all_operations(self):
        """Verify variable usage extraction for read/write/delete."""
        extractor = PythonExtractor(root_path=Path('.'))

        code = '''
x = 5
y = x + 10
z = y * 2
del x
print(z)
'''

        tree = ast.parse(code)
        tree_dict = {'tree': tree, 'type': 'python_ast'}

        # Extract variable usage
        result = extractor._extract_variable_usage(tree_dict, code)

        # VERIFY: Found multiple usage records
        assert len(result) > 0, "Should find variable usage"

        # VERIFY: Each record has required fields
        for usage in result:
            assert 'line' in usage
            assert 'variable_name' in usage
            assert 'usage_type' in usage
            assert 'in_component' in usage
            assert 'scope_level' in usage

        # VERIFY: Different usage types
        usage_types = {u['usage_type'] for u in result}
        assert 'write' in usage_types, "Should detect writes"
        assert 'read' in usage_types, "Should detect reads"

        # VERIFY: Variable names
        var_names = {u['variable_name'] for u in result}
        assert 'x' in var_names
        assert 'y' in var_names
        assert 'z' in var_names

    def test_extract_variable_usage_tracks_scopes(self):
        """Verify scope detection (global/function/class)."""
        extractor = PythonExtractor(root_path=Path('.'))

        code = '''
global_var = 1

def my_function():
    local_var = 2
    return local_var

class MyClass:
    def method(self):
        method_var = 3
        return method_var
'''

        tree = ast.parse(code)
        tree_dict = {'tree': tree, 'type': 'python_ast'}

        result = extractor._extract_variable_usage(tree_dict, code)

        # VERIFY: Different scopes detected
        scopes = {u['in_component'] for u in result}
        assert 'global' in scopes
        assert 'my_function' in scopes or any('my_function' in s for s in scopes)
        assert any('MyClass' in s for s in scopes), f"Should detect class scope, got {scopes}"


# ============================================================================
# JavaScriptExtractor Tests
# ============================================================================

class TestJavaScriptExtractor:
    """Unit tests for JavaScript extractor."""

    def test_extract_requires_ast_parser(self):
        """Verify extractor returns empty results without AST parser."""
        extractor = JavaScriptExtractor(root_path=Path('.'), ast_parser=None)

        code = 'import React from "react";'
        file_info = {'path': 'test.js', 'ext': '.js'}

        result = extractor.extract(file_info, code, tree=None)

        # VERIFY: All lists are empty without parser
        assert result['imports'] == []
        assert result['symbols'] == []
        assert result['routes'] == []

    def test_extract_imports_from_semantic_ast(self):
        """Verify import extraction from semantic AST format."""
        # Create mock AST parser
        mock_parser = MagicMock()
        mock_parser.extract_functions.return_value = []
        mock_parser.extract_classes.return_value = []
        mock_parser.extract_calls.return_value = []
        mock_parser.extract_properties.return_value = []
        mock_parser.extract_assignments.return_value = []
        mock_parser.extract_function_calls_with_args.return_value = []
        mock_parser.extract_returns.return_value = []
        mock_parser.extract_cfg.return_value = []

        extractor = JavaScriptExtractor(root_path=Path('.'), ast_parser=mock_parser)

        # Simulate semantic AST structure
        tree = {
            'type': 'semantic_ast',
            'tree': {
                'imports': [
                    {'kind': 'import', 'module': 'react', 'line': 1},
                    {'kind': 'import', 'module': 'express', 'line': 2},
                    {'kind': 'require', 'module': 'lodash', 'line': 3}
                ]
            }
        }

        file_info = {'path': 'test.js', 'ext': '.js'}
        result = extractor.extract(file_info, '', tree=tree)

        # VERIFY: Imports extracted as 3-tuples
        assert len(result['imports']) == 3, f"Expected 3 imports, got {len(result['imports'])}"

        for imp in result['imports']:
            assert len(imp) == 3, f"Import should be 3-tuple: {imp}"
            kind, module, line = imp
            assert kind in ('import', 'require')
            assert isinstance(module, str)
            assert isinstance(line, int)

        # VERIFY: Correct modules
        modules = [imp[1] for imp in result['imports']]
        assert 'react' in modules
        assert 'express' in modules
        assert 'lodash' in modules

    def test_extract_sql_from_function_calls(self):
        """Verify SQL extraction from db.execute() calls."""
        mock_parser = MagicMock()
        mock_parser.extract_functions.return_value = []
        mock_parser.extract_classes.return_value = []
        mock_parser.extract_calls.return_value = []
        mock_parser.extract_properties.return_value = []
        mock_parser.extract_assignments.return_value = []
        mock_parser.extract_returns.return_value = []
        mock_parser.extract_cfg.return_value = []

        # Mock function calls with SQL
        mock_parser.extract_function_calls_with_args.return_value = [
            {
                'line': 10,
                'callee_function': 'db.query',
                'argument_index': 0,
                'argument_expr': '"SELECT * FROM users WHERE id = ?"'
            },
            {
                'line': 15,
                'callee_function': 'connection.execute',
                'argument_index': 0,
                'argument_expr': '"INSERT INTO logs (message) VALUES (?)"'
            }
        ]

        extractor = JavaScriptExtractor(root_path=Path('.'), ast_parser=mock_parser)

        tree = {'type': 'semantic_ast', 'tree': {'imports': []}}
        file_info = {'path': 'test.js', 'ext': '.js'}

        result = extractor.extract(file_info, '', tree=tree)

        # VERIFY: SQL queries extracted
        assert len(result['sql_queries']) >= 1, f"Should find SQL queries, got {len(result['sql_queries'])}"

        for query in result['sql_queries']:
            assert 'line' in query
            assert 'query_text' in query
            assert 'command' in query
            assert 'tables' in query
            assert 'extraction_source' in query

    def test_determine_sql_source_categories(self):
        """Verify SQL source categorization for JS files."""
        extractor = JavaScriptExtractor(root_path=Path('.'))

        # Test migration file
        source = extractor._determine_sql_source('db/migrations/001_create_users.js', 'query')
        assert source == 'migration_file'

        # Test ORM method
        source = extractor._determine_sql_source('models/user.js', 'findAll')
        assert source == 'orm_query'

        # Test code execution
        source = extractor._determine_sql_source('api/users.js', 'execute')
        assert source == 'code_execute'

    def test_extract_routes_from_express(self):
        """Verify Express route extraction with auth detection."""
        mock_parser = MagicMock()
        mock_parser.extract_functions.return_value = []
        mock_parser.extract_classes.return_value = []
        mock_parser.extract_calls.return_value = []
        mock_parser.extract_properties.return_value = []
        mock_parser.extract_assignments.return_value = []
        mock_parser.extract_returns.return_value = []
        mock_parser.extract_cfg.return_value = []

        # Mock Express route calls
        mock_parser.extract_function_calls_with_args.return_value = [
            # app.get('/api/users', ...)
            {
                'line': 10,
                'callee_function': 'app.get',
                'argument_index': 0,
                'argument_expr': '"/api/users"'
            },
            {
                'line': 10,
                'callee_function': 'app.get',
                'argument_index': 1,
                'argument_expr': 'authMiddleware'
            },
            {
                'line': 10,
                'callee_function': 'app.get',
                'argument_index': 2,
                'argument_expr': 'getUsers'
            },
            # app.post('/api/login', ...)
            {
                'line': 20,
                'callee_function': 'app.post',
                'argument_index': 0,
                'argument_expr': '"/api/login"'
            },
            {
                'line': 20,
                'callee_function': 'app.post',
                'argument_index': 1,
                'argument_expr': 'loginHandler'
            }
        ]

        extractor = JavaScriptExtractor(root_path=Path('.'), ast_parser=mock_parser)

        tree = {'type': 'semantic_ast', 'tree': {'imports': []}}
        file_info = {'path': 'routes.js', 'ext': '.js'}

        result = extractor.extract(file_info, '', tree=tree)

        # VERIFY: Routes extracted
        assert len(result['routes']) == 2, f"Should find 2 routes, got {len(result['routes'])}"

        # VERIFY: Each route has required fields
        for route in result['routes']:
            assert 'line' in route
            assert 'method' in route
            assert 'pattern' in route
            assert 'path' in route
            assert 'has_auth' in route
            assert 'handler_function' in route
            assert 'controls' in route

        # VERIFY: Auth detection
        routes_with_auth = [r for r in result['routes'] if r['has_auth']]
        assert len(routes_with_auth) == 1, f"Should detect 1 route with auth, got {len(routes_with_auth)}"

        # VERIFY: Route patterns
        patterns = [r['pattern'] for r in result['routes']]
        assert '/api/users' in patterns
        assert '/api/login' in patterns


# ============================================================================
# BaseExtractor Tests
# ============================================================================

class TestBaseExtractor:
    """Unit tests for BaseExtractor regex methods."""

    def test_extract_jwt_patterns_detects_sign_calls(self):
        """Verify JWT sign pattern detection with metadata."""

        # Create a concrete subclass for testing
        class TestExtractor(BaseExtractor):
            def supported_extensions(self):
                return ['.test']

            def extract(self, file_info, content, tree=None):
                return {}

        extractor = TestExtractor(root_path=Path('.'))

        code = '''
const token = jwt.sign(
    { userId: user.id, password: user.password },
    process.env.JWT_SECRET,
    { algorithm: 'HS256', expiresIn: '1h' }
);

const unsafeToken = jwt.sign(
    { data: "test" },
    "hardcoded-secret-123",
    { algorithm: 'none' }
);
'''

        result = extractor.extract_jwt_patterns(code)

        # VERIFY: Found JWT patterns
        assert len(result) >= 1, f"Should find JWT sign calls, got {len(result)}"

        # VERIFY: Each pattern has required fields
        for pattern in result:
            assert 'type' in pattern
            assert 'line' in pattern

            if pattern['type'] == 'jwt_sign':
                assert 'secret_type' in pattern
                assert 'algorithm' in pattern
                assert 'has_expiry' in pattern
                assert 'sensitive_fields' in pattern

        # VERIFY: Secret type detection
        secret_types = {p['secret_type'] for p in result if p['type'] == 'jwt_sign'}
        assert 'environment' in secret_types or 'hardcoded' in secret_types

        # VERIFY: Sensitive field detection
        signs = [p for p in result if p['type'] == 'jwt_sign']
        sensitive = [p for p in signs if p['sensitive_fields']]
        assert len(sensitive) >= 1, "Should detect password in payload"

    def test_extract_jwt_patterns_detects_verify_vulnerabilities(self):
        """Verify JWT verify pattern detection with security checks."""
        class TestExtractor(BaseExtractor):
            def supported_extensions(self):
                return ['.test']

            def extract(self, file_info, content, tree=None):
                return {}

        extractor = TestExtractor(root_path=Path('.'))

        code = '''
// Dangerous: allows 'none' algorithm
jwt.verify(token, secret, { algorithms: ['HS256', 'none'] });

// Algorithm confusion: both symmetric and asymmetric
jwt.verify(token, secret, { algorithms: ['HS256', 'RS256'] });

// Insecure decode without verification
jwt.decode(token);
'''

        result = extractor.extract_jwt_patterns(code)

        # VERIFY: Found verify patterns
        verify_patterns = [p for p in result if p['type'] == 'jwt_verify']
        assert len(verify_patterns) >= 1, "Should find verify calls"

        # VERIFY: Detects 'none' algorithm
        allows_none = [p for p in verify_patterns if p.get('allows_none')]
        assert len(allows_none) >= 1, "Should detect 'none' algorithm"

        # VERIFY: Detects algorithm confusion
        has_confusion = [p for p in verify_patterns if p.get('has_confusion')]
        assert len(has_confusion) >= 1, "Should detect algorithm confusion"

        # VERIFY: Detects insecure decode
        decode_patterns = [p for p in result if p['type'] == 'jwt_decode']
        assert len(decode_patterns) >= 1, "Should detect decode calls"

    def test_extract_sql_objects_from_ddl(self):
        """Verify SQL object extraction from DDL statements."""
        class TestExtractor(BaseExtractor):
            def supported_extensions(self):
                return ['.sql']

            def extract(self, file_info, content, tree=None):
                return {}

        extractor = TestExtractor(root_path=Path('.'))

        sql = '''
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL
);

CREATE INDEX idx_users_username ON users(username);

CREATE VIEW active_users AS
    SELECT * FROM users WHERE active = true;

CREATE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
'''

        result = extractor.extract_sql_objects(sql)

        # VERIFY: Found SQL objects
        assert len(result) >= 3, f"Should find multiple SQL objects, got {len(result)}"

        # VERIFY: Each object is (kind, name) tuple
        for obj in result:
            assert len(obj) == 2, f"Should be 2-tuple, got {len(obj)}-tuple: {obj}"
            kind, name = obj
            assert isinstance(kind, str)
            assert isinstance(name, str)

        # VERIFY: Object types
        kinds = {obj[0] for obj in result}
        assert 'table' in kinds or 'view' in kinds, f"Should detect table/view, got {kinds}"

        # VERIFY: Object names
        names = {obj[1] for obj in result}
        assert any('users' in n for n in names), f"Should find 'users', got {names}"

    def test_extract_routes_basic_patterns(self):
        """Verify route extraction from code files."""
        class TestExtractor(BaseExtractor):
            def supported_extensions(self):
                return ['.js']

            def extract(self, file_info, content, tree=None):
                return {}

        extractor = TestExtractor(root_path=Path('.'))

        code = '''
app.get('/api/users', getUsers);
app.post('/api/users/:id', updateUser);
router.delete('/api/sessions', logout);
'''

        result = extractor.extract_routes(code)

        # VERIFY: Found routes
        assert len(result) >= 3, f"Should find 3 routes, got {len(result)}"

        # VERIFY: Each route is (method, path) tuple
        for route in result:
            assert len(route) == 2, f"Should be 2-tuple: {route}"
            method, path = route
            assert isinstance(method, str)
            assert isinstance(path, str)

        # VERIFY: Methods extracted correctly
        methods = {r[0] for r in result}
        assert 'GET' in methods or 'POST' in methods or 'DELETE' in methods

        # VERIFY: Paths extracted
        paths = {r[1] for r in result}
        assert any('/api/users' in p for p in paths)


# ============================================================================
# Integration Tests
# ============================================================================

class TestExtractorIntegration:
    """Integration tests verifying end-to-end extraction."""

    def test_python_extractor_full_extraction(self):
        """Verify complete Python file extraction pipeline."""
        extractor = PythonExtractor(root_path=Path('.'))

        code = '''
import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/users', methods=['GET'])
@login_required
def get_users():
    cursor.execute("SELECT * FROM users")
    return jsonify(cursor.fetchall())
'''

        # Parse and extract
        tree = ast.parse(code)
        tree_dict = {'tree': tree, 'type': 'python_ast'}

        file_info = {'path': 'app.py'}
        result = extractor.extract(file_info, code, tree=tree_dict)

        # VERIFY: All extraction types present
        assert 'imports' in result
        assert 'routes' in result
        assert 'symbols' in result
        assert 'sql_queries' in result

        # VERIFY: Imports extracted
        assert len(result['imports']) >= 2

        # VERIFY: Routes extracted with auth
        assert len(result['routes']) >= 1
        if result['routes']:
            assert result['routes'][0]['has_auth'] == True

    def test_javascript_extractor_minimal_extraction(self):
        """Verify JS extractor handles minimal code gracefully."""
        mock_parser = MagicMock()
        mock_parser.extract_functions.return_value = []
        mock_parser.extract_classes.return_value = []
        mock_parser.extract_calls.return_value = []
        mock_parser.extract_properties.return_value = []
        mock_parser.extract_assignments.return_value = []
        mock_parser.extract_function_calls_with_args.return_value = []
        mock_parser.extract_returns.return_value = []
        mock_parser.extract_cfg.return_value = []

        extractor = JavaScriptExtractor(root_path=Path('.'), ast_parser=mock_parser)

        tree = {'type': 'semantic_ast', 'tree': {'imports': []}}
        file_info = {'path': 'empty.js', 'ext': '.js'}

        result = extractor.extract(file_info, '', tree=tree)

        # VERIFY: Returns valid structure even for empty file
        assert isinstance(result, dict)
        assert isinstance(result['imports'], list)
        assert isinstance(result['routes'], list)
        assert isinstance(result['symbols'], list)

    def test_extractor_error_handling(self):
        """Verify extractors handle errors gracefully."""
        extractor = PythonExtractor(root_path=Path('.'))

        # Invalid Python code
        code = 'this is not valid python code @#$%'

        file_info = {'path': 'broken.py'}

        # Should not crash
        try:
            # Will fail to parse, but extract should handle it
            tree = None  # Simulate parse failure
            result = extractor.extract(file_info, code, tree=tree)

            # Should return empty results, not crash
            assert isinstance(result, dict)
            assert isinstance(result['imports'], list)

        except Exception as e:
            pytest.fail(f"Extractor should handle errors gracefully, got: {e}")
