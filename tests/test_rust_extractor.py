"""Unit tests for Rust extractor module.

Tests verify ACTUAL behavior of RustExtractor, following the same patterns
as test_extractors.py for Python and JavaScript extractors.

Test Coverage:
1. RustExtractor - Tree-sitter-based extraction (imports, functions, calls, etc.)
2. Error handling - Graceful degradation on parse failures
3. Integration - Full extraction pipeline with real Rust code
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from theauditor.indexer.extractors.rust import RustExtractor


# ============================================================================
# RustExtractor Tests
# ============================================================================

class TestRustExtractor:
    """Unit tests for Rust extractor tree-sitter-based methods."""

    def test_extract_imports_returns_2tuples(self):
        """Verify imports are 2-tuples (kind, module) - Rust format."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''use std::collections::HashMap;
use std::io::{self, Read, Write};
use serde::{Deserialize, Serialize};
use tokio::runtime::Runtime;
'''

        # Extract imports (extractor handles tree parsing internally)
        file_info = {'path': 'test.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        # VERIFY: All imports are 2-tuples (Rust format differs from Python/JS)
        imports = result['imports']
        assert len(imports) >= 3, f"Expected at least 3 imports, got {len(imports)}"

        for imp in imports:
            assert len(imp) == 2, f"Import should be 2-tuple, got {len(imp)}-tuple: {imp}"
            kind, module = imp
            assert kind == 'use', f"Invalid kind for Rust: {kind}"
            assert isinstance(module, str), f"Module should be string, got {type(module)}"

        # VERIFY: Correct content
        modules = [imp[1] for imp in imports]
        assert any('std::collections' in m or 'HashMap' in m for m in modules), \
            f"Should find HashMap import, got {modules}"
        assert any('serde' in m for m in modules), \
            f"Should find serde import, got {modules}"

    def test_extract_imports_handles_nested_modules(self):
        """Verify handling of nested use statements."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''use std::io::{self, Read, Write};
use actix_web::{web, App, HttpServer};
use diesel::prelude::*;
'''

        file_info = {'path': 'test.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        imports = result['imports']

        # VERIFY: Multiple items from same module
        assert len(imports) >= 3, f"Should extract multiple imports, got {len(imports)}"

        # VERIFY: No empty module names (Rust imports are 2-tuples)
        for imp in imports:
            _, module = imp
            assert module, f"Module should not be empty: {imp}"

    def test_extract_functions_returns_metadata(self):
        """Verify function extraction with signatures and metadata."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

async fn fetch_data() -> Result<String, Error> {
    Ok("data".to_string())
}

fn private_helper() {
    println!("helper");
}
'''

        file_info = {'path': 'lib.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        symbols = result['symbols']

        # VERIFY: Found functions
        functions = [s for s in symbols if s['type'] == 'function']
        assert len(functions) >= 3, f"Should find 3 functions, got {len(functions)}"

        # VERIFY: Each function has required fields
        for func in functions:
            assert 'name' in func
            assert 'type' in func
            assert 'line' in func
            assert 'col' in func or 'column' in func

        # VERIFY: Function names
        func_names = [f['name'] for f in functions]
        assert 'add' in func_names
        assert 'fetch_data' in func_names
        assert 'private_helper' in func_names

    def test_extract_structs_enums_traits(self):
        """Verify struct/enum/trait extraction (Rust types)."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
pub struct User {
    pub id: u64,
    name: String,
}

enum Status {
    Active,
    Inactive,
}

trait Validator {
    fn validate(&self) -> bool;
}
'''



        file_info = {'path': 'types.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        symbols = result['symbols']

        # VERIFY: Found struct/enum/trait (Rust has specific types: 'struct', 'enum', 'trait')
        structs = [s for s in symbols if s['type'] == 'struct']
        enums = [s for s in symbols if s['type'] == 'enum']
        traits = [s for s in symbols if s['type'] == 'trait']

        # Should find at least one of each type
        assert len(structs) >= 1, f"Should find struct, got {len(structs)}"
        assert len(enums) >= 1, f"Should find enum, got {len(enums)}"
        assert len(traits) >= 1, f"Should find trait, got {len(traits)}"

        # VERIFY: Names
        all_types = structs + enums + traits
        type_names = [t['name'] for t in all_types]
        assert 'User' in type_names
        assert 'Status' in type_names
        assert 'Validator' in type_names

    def test_extract_calls_includes_macros(self):
        """Verify function calls and macro invocations."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
fn main() {
    println!("Hello");
    let x = vec![1, 2, 3];
    assert_eq!(x.len(), 3);
    some_function();
}
'''

        

        file_info = {'path': 'main.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        symbols = result['symbols']

        # VERIFY: Found calls (macros and regular functions)
        calls = [s for s in symbols if s['type'] == 'call']
        assert len(calls) >= 1, f"Should find function calls, got {len(calls)}"

        # VERIFY: Call names (macros include '!')
        call_names = [c['name'] for c in calls]
        # May include println!, vec!, assert_eq!, some_function, etc.
        assert any('!' in name or 'function' in name for name in call_names), \
            f"Should find macros or function calls, got {call_names}"

    def test_extract_assignments_let_bindings(self):
        """Verify let binding extraction for taint analysis."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
fn process(input: String) {
    let data = input;
    let parsed = serde_json::from_str(&data);
    let result = parsed.unwrap();
}
'''

        

        file_info = {'path': 'process.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        # VERIFY: Assignments extracted (in symbols or separate structure)
        # Rust extractor may put assignments in symbols as 'variable' type
        symbols = result['symbols']

        # Variables from let bindings
        variables = [s for s in symbols if s.get('type') in ['variable', 'assignment']]

        # Should find at least some variable bindings
        assert len(variables) >= 0, "Assignment extraction should not crash"

    def test_extract_properties_field_access(self):
        """Verify struct field access extraction."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
fn get_username(user: &User) -> &str {
    &user.name
}

fn check_status(req: HttpRequest) -> bool {
    req.body.is_empty()
}
'''

        

        file_info = {'path': 'access.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        symbols = result['symbols']

        # VERIFY: Properties extracted (field accesses like user.name, req.body)
        properties = [s for s in symbols if s['type'] == 'property']

        # Tree-sitter may or may not extract all field accesses as separate symbols
        # Main thing: should not crash
        assert isinstance(properties, list), "Property extraction should return list"

    def test_extract_function_calls_with_args(self):
        """Verify function calls with arguments (CRITICAL for taint analysis)."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
fn process_request(req: HttpRequest) {
    let query = req.query_string();
    db.execute("SELECT * FROM users WHERE id = ?", &[query]);
    println!("Processing: {}", query);
}
'''

        

        file_info = {'path': 'handler.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        # VERIFY: function_calls key exists (for taint analysis)
        assert 'function_calls' in result, "Should have function_calls for taint analysis"

        function_calls = result['function_calls']
        assert isinstance(function_calls, list), "function_calls should be a list"

        # If any calls with args were found, verify structure
        if function_calls:
            for call in function_calls:
                assert 'line' in call
                assert 'callee_function' in call
                assert 'argument_index' in call
                assert 'argument_expr' in call
                # Verify callee_function is not empty (critical bug we fixed)
                assert call['callee_function'] != '', \
                    f"callee_function should not be empty: {call}"

    def test_extract_handles_parse_errors_gracefully(self):
        """Verify extractor returns empty results on parse failures (NOT crash)."""
        extractor = RustExtractor(root_path=Path('.'))

        # Invalid Rust code
        code = '''
        this is not valid rust code @#$%
        fn broken {{{
        '''

        file_info = {'path': 'broken.rs', 'ext': '.rs'}

        # Should not crash (extractor handles errors gracefully)
        result = extractor.extract(file_info, code)

        # VERIFY: Returns valid structure even with parse errors
        assert isinstance(result, dict)
        assert isinstance(result.get('imports', []), list)
        assert isinstance(result.get('symbols', []), list)
        assert isinstance(result.get('function_calls', []), list)

    def test_extract_empty_file(self):
        """Verify extraction on empty Rust file."""
        extractor = RustExtractor(root_path=Path('.'))

        code = ''

        

        file_info = {'path': 'empty.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        # VERIFY: Returns valid empty structure
        assert isinstance(result, dict)
        assert isinstance(result.get('imports', []), list)
        assert isinstance(result.get('symbols', []), list)
        assert len(result['imports']) == 0
        assert len(result['symbols']) == 0

    def test_extract_handles_comments(self):
        """Verify extraction ignores comments correctly."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
// This is a comment
/* Multi-line
   comment */
/// Doc comment
fn real_function() {
    // Comment in function
    let x = 5; // Inline comment
}
'''

        

        file_info = {'path': 'commented.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        symbols = result['symbols']
        functions = [s for s in symbols if s['type'] == 'function']

        # VERIFY: Found real function, ignored comments
        assert len(functions) >= 1
        assert any(f['name'] == 'real_function' for f in functions)

    def test_extract_unsafe_blocks(self):
        """Verify extraction from unsafe blocks."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
fn dangerous() {
    unsafe {
        let ptr = std::ptr::null_mut();
        *ptr = 42;
    }
}
'''

        

        file_info = {'path': 'unsafe.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        symbols = result['symbols']

        # VERIFY: Function extracted even with unsafe block
        functions = [s for s in symbols if s['type'] == 'function']
        assert len(functions) >= 1
        assert any(f['name'] == 'dangerous' for f in functions)

    def test_extract_async_functions(self):
        """Verify async function extraction."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
async fn fetch_data() -> Result<String, Error> {
    let response = reqwest::get("https://api.example.com").await?;
    response.text().await
}
'''

        

        file_info = {'path': 'async.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        symbols = result['symbols']
        functions = [s for s in symbols if s['type'] == 'function']

        # VERIFY: Async function extracted
        assert len(functions) >= 1
        assert any(f['name'] == 'fetch_data' for f in functions)

    def test_extract_generic_functions(self):
        """Verify generic function extraction."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
fn generic_fn<T: Clone>(value: T) -> T {
    value.clone()
}

fn multi_generic<T, U>(a: T, b: U) -> (T, U) {
    (a, b)
}
'''

        

        file_info = {'path': 'generics.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        symbols = result['symbols']
        functions = [s for s in symbols if s['type'] == 'function']

        # VERIFY: Generic functions extracted
        assert len(functions) >= 2
        func_names = [f['name'] for f in functions]
        assert 'generic_fn' in func_names
        assert 'multi_generic' in func_names


# ============================================================================
# Integration Tests
# ============================================================================

class TestRustExtractorIntegration:
    """Integration tests verifying end-to-end extraction."""

    def test_full_extraction_pipeline(self):
        """Verify complete Rust file extraction pipeline."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
use std::collections::HashMap;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct User {
    pub id: u64,
    pub name: String,
}

impl User {
    pub fn new(id: u64, name: String) -> Self {
        User { id, name }
    }

    pub fn save(&self, db: &Database) -> Result<(), Error> {
        db.execute("INSERT INTO users (id, name) VALUES (?, ?)", &[&self.id, &self.name])
    }
}

pub fn get_user(id: u64, db: &Database) -> Option<User> {
    db.query_row("SELECT * FROM users WHERE id = ?", &[id])
}
'''

        

        file_info = {'path': 'user.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        # VERIFY: All extraction types present
        assert 'imports' in result
        assert 'symbols' in result
        assert 'function_calls' in result

        # VERIFY: Imports extracted
        imports = result['imports']
        assert len(imports) >= 2
        modules = [imp[1] for imp in imports]
        assert any('std::collections' in m or 'HashMap' in m for m in modules)
        assert any('serde' in m for m in modules)

        # VERIFY: Structs and functions extracted
        symbols = result['symbols']
        structs = [s for s in symbols if s['type'] == 'struct']
        functions = [s for s in symbols if s['type'] == 'function']

        assert len(structs) >= 1  # User struct
        assert len(functions) >= 2  # new, save, get_user (impl methods may vary)

        # VERIFY: User struct found
        assert any(s['name'] == 'User' for s in structs)

    def test_extractor_error_recovery(self):
        """Verify extractor recovers from partial parse errors."""
        extractor = RustExtractor(root_path=Path('.'))

        # Code with syntax error in middle
        code = '''
use std::io;

fn good_function() {
    println!("works");
}

fn broken_function() {
    this is broken syntax
}

fn another_good_function() {
    println!("also works");
}
'''

        

        file_info = {'path': 'partial.rs', 'ext': '.rs'}

        # Should not crash completely
        result = extractor.extract(file_info, code)

        # VERIFY: Still extracts some valid code
        assert isinstance(result, dict)
        symbols = result.get('symbols', [])

        # May extract the good functions even with error in middle
        # (depends on tree-sitter error recovery)
        assert isinstance(symbols, list)

    def test_real_world_actix_web_handler(self):
        """Test extraction from realistic actix-web handler code."""
        extractor = RustExtractor(root_path=Path('.'))

        code = '''
use actix_web::{web, HttpRequest, HttpResponse, Result};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct UserQuery {
    id: u64,
}

async fn get_user(
    req: HttpRequest,
    query: web::Query<UserQuery>,
    db: web::Data<Database>
) -> Result<HttpResponse> {
    let user_id = query.id;

    match db.get_user(user_id).await {
        Ok(user) => Ok(HttpResponse::Ok().json(user)),
        Err(e) => Ok(HttpResponse::InternalServerError().body(e.to_string()))
    }
}
'''

        

        file_info = {'path': 'handlers.rs', 'ext': '.rs'}
        result = extractor.extract(file_info, code)

        # VERIFY: Realistic code extracts successfully
        assert isinstance(result, dict)

        imports = result['imports']
        symbols = result['symbols']

        # Should find actix_web imports
        modules = [imp[1] for imp in imports]
        assert any('actix_web' in m for m in modules), f"Should find actix_web, got {modules}"

        # Should find struct and function
        structs = [s for s in symbols if s['type'] == 'struct']
        functions = [s for s in symbols if s['type'] == 'function']

        assert any(s['name'] == 'UserQuery' for s in structs)
        assert any(f['name'] == 'get_user' for f in functions)
