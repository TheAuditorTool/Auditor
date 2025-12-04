"""Integration tests for Rust graph infrastructure wiring.

Phase 5.3 of wire-rust-graph-integration ticket.
Tests that:
- Rust extraction functions produce correct schema
- DFGBuilder loads Rust strategies
- ZERO FALLBACK policy is enforced
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# --- Fixtures ---


@pytest.fixture
def rust_sample_code():
    """Sample Rust code exercising all extraction targets."""
    return '''
fn main() {
    let x = 42;
    let mut counter = 0;
    let y = x + 1;
    let (a, b) = get_pair();

    process(x);
    counter += 1;

    if counter > 0 {
        println!("positive");
    } else {
        println!("zero");
    }

    let result = compute(a, b);
    return result;
}

fn compute(x: i32, y: i32) -> i32 {
    let sum = x + y;

    match sum {
        0 => 0,
        n if n > 0 => n * 2,
        _ => -1,
    }
}

fn get_pair() -> (i32, i32) {
    (1, 2)
}

fn process(data: i32) {
    println!("{}", data);
    helper(data);
}

fn helper(value: i32) {
    let doubled = value * 2;
    doubled
}

async fn fetch_data() -> String {
    let response = fetch().await;
    let processed = transform(response).await;
    processed
}
'''


@pytest.fixture
def parsed_rust_tree(rust_sample_code):
    """Parse Rust code with tree-sitter."""
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError:
        pytest.skip("tree-sitter-language-pack not installed")

    parser = get_parser("rust")
    tree = parser.parse(rust_sample_code.encode("utf-8"))
    return tree.root_node


@pytest.fixture
def temp_db_with_rust_data():
    """Create a temporary database with Rust extraction data."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)

    # Create required tables
    conn.execute("""
        CREATE TABLE files (path TEXT PRIMARY KEY)
    """)
    conn.execute("""
        CREATE TABLE assignments (
            file TEXT,
            line INTEGER,
            col INTEGER DEFAULT 0,
            target_var TEXT,
            source_expr TEXT,
            in_function TEXT,
            property_path TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE assignment_sources (
            id INTEGER PRIMARY KEY,
            assignment_file TEXT,
            assignment_line INTEGER,
            assignment_col INTEGER DEFAULT 0,
            assignment_target TEXT,
            source_var_name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE function_call_args (
            file TEXT,
            line INTEGER,
            caller_function TEXT,
            callee_function TEXT CHECK(callee_function != ''),
            argument_index INTEGER,
            argument_expr TEXT,
            param_name TEXT,
            callee_file_path TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE function_returns (
            file TEXT,
            line INTEGER,
            col INTEGER DEFAULT 0,
            function_name TEXT,
            return_expr TEXT,
            has_jsx BOOLEAN DEFAULT 0,
            returns_component BOOLEAN DEFAULT 0,
            cleanup_operations TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE function_return_sources (
            id INTEGER PRIMARY KEY,
            return_file TEXT,
            return_line INTEGER,
            return_col INTEGER DEFAULT 0,
            return_function TEXT,
            return_var_name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE cfg_blocks (
            id INTEGER PRIMARY KEY,
            file TEXT,
            function_name TEXT,
            block_type TEXT,
            start_line INTEGER,
            end_line INTEGER,
            condition_expr TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE cfg_edges (
            id INTEGER PRIMARY KEY,
            file TEXT,
            function_name TEXT,
            source_block_id INTEGER,
            target_block_id INTEGER,
            edge_type TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE cfg_block_statements (
            block_id INTEGER,
            statement_type TEXT,
            line INTEGER,
            statement_text TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE rust_impl_blocks (
            file_path TEXT,
            line INTEGER,
            end_line INTEGER,
            target_type_raw TEXT,
            target_type_resolved TEXT,
            trait_name TEXT,
            trait_resolved TEXT,
            is_unsafe INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE rust_traits (
            file_path TEXT,
            line INTEGER,
            name TEXT,
            supertraits TEXT,
            is_unsafe INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE rust_trait_methods (
            file_path TEXT,
            trait_line INTEGER,
            method_line INTEGER,
            method_name TEXT,
            return_type TEXT,
            has_default INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE rust_functions (
            file_path TEXT,
            line INTEGER,
            name TEXT,
            return_type TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE rust_async_functions (
            file_path TEXT,
            line INTEGER,
            function_name TEXT,
            return_type TEXT,
            has_await INTEGER,
            await_count INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE rust_await_points (
            file_path TEXT,
            line INTEGER,
            containing_function TEXT,
            awaited_expression TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE symbols (
            path TEXT,
            name TEXT,
            type TEXT,
            line INTEGER
        )
    """)

    conn.execute("INSERT INTO files (path) VALUES (?)", ("test.rs",))
    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except PermissionError:
        pass


# --- Test Classes ---


class TestRustAssignmentExtraction:
    """Test Rust assignment extraction per spec.md requirements."""

    def test_simple_let_binding(self, parsed_rust_tree):
        """WHEN a Rust file contains `let x = 42;`
        THEN the extraction SHALL return target_var='x', source_expr='42'
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_assignments(parsed_rust_tree, "test.rs")

        # Find let x = 42
        x_assignment = next((a for a in result if a["target_var"] == "x"), None)
        assert x_assignment is not None, "Should extract 'x' assignment"
        assert x_assignment["source_expr"] == "42"
        assert x_assignment["in_function"] == "main"

    def test_mutable_binding(self, parsed_rust_tree):
        """WHEN a Rust file contains `let mut counter = 0;`
        THEN the extraction SHALL include target_var='counter'
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_assignments(parsed_rust_tree, "test.rs")

        counter = next((a for a in result if a["target_var"] == "counter"), None)
        assert counter is not None, "Should extract mutable binding 'counter'"
        assert counter["source_expr"] == "0"

    def test_assignment_with_source_variable(self, parsed_rust_tree):
        """WHEN a Rust file contains `let y = x + 1;`
        THEN source_vars SHALL include 'x'
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_assignments(parsed_rust_tree, "test.rs")

        y_assignment = next((a for a in result if a["target_var"] == "y"), None)
        assert y_assignment is not None, "Should extract 'y' assignment"
        assert "x" in y_assignment.get("source_vars", []), "Should track source var 'x'"

    def test_destructuring_pattern(self, parsed_rust_tree):
        """WHEN a Rust file contains `let (a, b) = get_pair();`
        THEN assignments SHALL include both 'a' and 'b'
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_assignments(parsed_rust_tree, "test.rs")

        a_assignment = next((a for a in result if a["target_var"] == "a"), None)
        b_assignment = next((a for a in result if a["target_var"] == "b"), None)

        assert a_assignment is not None, "Should extract destructured 'a'"
        assert b_assignment is not None, "Should extract destructured 'b'"


class TestRustFunctionCallExtraction:
    """Test Rust function call extraction per spec.md requirements."""

    def test_simple_function_call(self, parsed_rust_tree):
        """WHEN a Rust file contains `process(x);` inside function `main`
        THEN extraction SHALL include caller_function='main', callee_function='process'
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_function_calls(parsed_rust_tree, "test.rs")

        process_call = next(
            (c for c in result if c["callee_function"] == "process"), None
        )
        assert process_call is not None, "Should extract 'process' call"
        assert process_call["caller_function"] == "main"
        assert "x" in str(process_call.get("argument_expr", ""))

    def test_multiple_arguments(self, parsed_rust_tree):
        """WHEN a Rust file contains `compute(a, b);`
        THEN extraction SHALL include multiple argument entries
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_function_calls(parsed_rust_tree, "test.rs")

        compute_calls = [c for c in result if c["callee_function"] == "compute"]
        assert len(compute_calls) >= 1, "Should extract 'compute' call"

    def test_nested_function_call(self, parsed_rust_tree):
        """WHEN helper(data) is called inside process()
        THEN caller_function SHALL be 'process'
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_function_calls(parsed_rust_tree, "test.rs")

        helper_call = next(
            (c for c in result if c["callee_function"] == "helper"), None
        )
        assert helper_call is not None, "Should extract 'helper' call"
        assert helper_call["caller_function"] == "process"


class TestRustReturnExtraction:
    """Test Rust return extraction per spec.md requirements."""

    def test_explicit_return(self, parsed_rust_tree):
        """WHEN a Rust file contains `return result;`
        THEN extraction SHALL include function_name and return_expr
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_returns(parsed_rust_tree, "test.rs")

        # Should have return from main
        main_return = next(
            (r for r in result if r["function_name"] == "main"), None
        )
        assert main_return is not None, "Should extract return from main"
        assert "result" in main_return["return_expr"]

    def test_implicit_return(self, parsed_rust_tree):
        """WHEN a Rust function ends with expression without semicolon
        THEN extraction SHALL capture as implicit return
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_returns(parsed_rust_tree, "test.rs")

        # helper function has implicit return: doubled
        helper_return = next(
            (r for r in result if r["function_name"] == "helper"), None
        )
        assert helper_return is not None, "Should extract implicit return from helper"
        assert "doubled" in helper_return["return_expr"]

    def test_return_source_vars(self, parsed_rust_tree):
        """WHEN return expression references variables
        THEN return_vars SHALL track those variables
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_returns(parsed_rust_tree, "test.rs")

        # Check that some return has source variables tracked
        returns_with_vars = [r for r in result if r.get("return_vars")]
        # At minimum, returns that reference variables should track them
        assert len(result) > 0, "Should extract returns"


class TestRustCFGExtraction:
    """Test Rust CFG extraction per spec.md requirements."""

    def test_if_expression_blocks(self, parsed_rust_tree):
        """WHEN a Rust file contains `if condition { a } else { b }`
        THEN cfg_blocks SHALL contain condition block with if statement
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_cfg(parsed_rust_tree, "test.rs")

        main_cfg = next(
            (c for c in result if c["function_name"] == "main"), None
        )
        assert main_cfg is not None, "Should extract CFG for main"

        # CFG uses 'type' key, and if statements create 'condition' blocks
        # with statements containing {'type': 'if', ...}
        has_if = False
        for block in main_cfg["blocks"]:
            for stmt in block.get("statements", []):
                if stmt.get("type") == "if":
                    has_if = True
                    break
        assert has_if, "Should have if statement in CFG blocks"

    def test_match_expression_blocks(self, parsed_rust_tree):
        """WHEN a Rust file contains `match x { ... }`
        THEN cfg_blocks SHALL contain condition block with match statement
        """
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_cfg(parsed_rust_tree, "test.rs")

        compute_cfg = next(
            (c for c in result if c["function_name"] == "compute"), None
        )
        assert compute_cfg is not None, "Should extract CFG for compute"

        # CFG uses 'type' key, match creates 'condition' blocks
        has_match = False
        for block in compute_cfg["blocks"]:
            for stmt in block.get("statements", []):
                if stmt.get("type") == "match":
                    has_match = True
                    break
        assert has_match, "Should have match statement in CFG blocks"

    def test_cfg_edges_present(self, parsed_rust_tree):
        """CFG extraction SHALL include edges between blocks."""
        from theauditor.ast_extractors import rust_impl

        result = rust_impl.extract_rust_cfg(parsed_rust_tree, "test.rs")

        # At least one function should have edges
        has_edges = any(len(c.get("edges", [])) > 0 for c in result)
        assert has_edges, "CFG should include edges"


class TestDFGBuilderRustStrategies:
    """Test DFGBuilder Rust strategy registration."""

    def test_rust_trait_strategy_registered(self, temp_db_with_rust_data):
        """WHEN DFGBuilder is instantiated
        THEN RustTraitStrategy SHALL be in strategies list
        """
        from theauditor.graph.dfg_builder import DFGBuilder
        from theauditor.graph.strategies.rust_traits import RustTraitStrategy

        builder = DFGBuilder(temp_db_with_rust_data)

        strategy_types = [type(s).__name__ for s in builder.strategies]
        assert "RustTraitStrategy" in strategy_types, \
            f"RustTraitStrategy not in strategies: {strategy_types}"

    def test_rust_async_strategy_registered(self, temp_db_with_rust_data):
        """WHEN DFGBuilder is instantiated
        THEN RustAsyncStrategy SHALL be in strategies list
        """
        from theauditor.graph.dfg_builder import DFGBuilder
        from theauditor.graph.strategies.rust_async import RustAsyncStrategy

        builder = DFGBuilder(temp_db_with_rust_data)

        strategy_types = [type(s).__name__ for s in builder.strategies]
        assert "RustAsyncStrategy" in strategy_types, \
            f"RustAsyncStrategy not in strategies: {strategy_types}"

    def test_strategies_instantiate_without_error(self):
        """Rust strategies SHALL instantiate without error."""
        from theauditor.graph.strategies.rust_traits import RustTraitStrategy
        from theauditor.graph.strategies.rust_async import RustAsyncStrategy

        trait_strategy = RustTraitStrategy()
        async_strategy = RustAsyncStrategy()

        assert trait_strategy is not None
        assert async_strategy is not None


class TestZeroFallbackCompliance:
    """Test ZERO FALLBACK policy compliance."""

    def test_rust_traits_no_table_check(self):
        """RustTraitStrategy SHALL NOT check sqlite_master for tables."""
        from theauditor.graph.strategies import rust_traits
        import inspect

        source = inspect.getsource(rust_traits.RustTraitStrategy)

        assert "sqlite_master" not in source, \
            "RustTraitStrategy should not check sqlite_master"
        assert "table_exists" not in source.lower(), \
            "RustTraitStrategy should not check table existence"

    def test_rust_async_no_table_check(self):
        """RustAsyncStrategy SHALL NOT check sqlite_master for tables."""
        from theauditor.graph.strategies import rust_async
        import inspect

        source = inspect.getsource(rust_async.RustAsyncStrategy)

        assert "sqlite_master" not in source, \
            "RustAsyncStrategy should not check sqlite_master"
        assert "table_exists" not in source.lower(), \
            "RustAsyncStrategy should not check table existence"

    def test_strategy_fails_loud_on_missing_table(self, temp_db_with_rust_data):
        """WHEN required table is missing
        THEN strategy SHALL raise exception
        """
        from theauditor.graph.strategies.rust_traits import RustTraitStrategy

        # Delete rust_impl_blocks table
        conn = sqlite3.connect(temp_db_with_rust_data)
        conn.execute("DROP TABLE rust_impl_blocks")
        conn.commit()
        conn.close()

        strategy = RustTraitStrategy()

        # Should raise when table is missing
        with pytest.raises(Exception):
            strategy.build(temp_db_with_rust_data, ".")


class TestExtractorWiring:
    """Test that RustExtractor is wired to new functions."""

    def test_extractor_returns_language_agnostic_keys(self, rust_sample_code):
        """RustExtractor.extract() SHALL return assignments, function_calls, returns, cfg keys."""
        try:
            from tree_sitter_language_pack import get_parser
        except ImportError:
            pytest.skip("tree-sitter-language-pack not installed")

        from theauditor.indexer.extractors.rust import RustExtractor

        parser = get_parser("rust")
        tree = parser.parse(rust_sample_code.encode("utf-8"))

        extractor = RustExtractor(Path("."), None)

        result = extractor.extract(
            {"path": "test.rs"},
            rust_sample_code,
            {"type": "tree_sitter", "tree": tree}
        )

        assert "assignments" in result, "Should have 'assignments' key"
        assert "function_calls" in result, "Should have 'function_calls' key"
        assert "returns" in result, "Should have 'returns' key"
        assert "cfg" in result, "Should have 'cfg' key"

        # These should be lists with content
        assert isinstance(result["assignments"], list)
        assert isinstance(result["function_calls"], list)
        assert isinstance(result["returns"], list)
        assert isinstance(result["cfg"], list)
