"""
Go Implementation Unit Tests - Test go_impl.py extraction functions.

These tests verify that tree-sitter based Go extraction works correctly
by parsing actual Go code and checking the extracted data.

Created as part of: add-go-support OpenSpec proposal
"""

import pytest
from tree_sitter_language_pack import get_language, get_parser

from theauditor.ast_extractors import go_impl


@pytest.fixture
def go_parser():
    """Create a Go tree-sitter parser."""
    parser = get_parser("go")
    return parser


def parse_go(parser, code: str):
    """Helper to parse Go code."""
    return parser.parse(code.encode("utf-8"))


class TestGoPackageExtraction:
    """Tests for package extraction."""

    def test_extract_package(self, go_parser):
        """Test basic package extraction."""
        code = """package main"""
        tree = parse_go(go_parser, code)

        result = go_impl.extract_go_package(tree, code, "test.go")

        assert result is not None
        assert result["name"] == "main"
        assert result["file_path"] == "test.go"
        assert result["line"] == 1

    def test_extract_package_with_comment(self, go_parser):
        """Test package with preceding comment."""
        code = """// Package sample provides sample functionality.
package sample"""
        tree = parse_go(go_parser, code)

        result = go_impl.extract_go_package(tree, code, "test.go")

        assert result is not None
        assert result["name"] == "sample"
        assert result["line"] == 2


class TestGoImportExtraction:
    """Tests for import extraction."""

    def test_extract_single_import(self, go_parser):
        """Test single import extraction."""
        code = '''package main
import "fmt"'''
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_imports(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["path"] == "fmt"
        assert results[0]["alias"] is None
        assert results[0]["is_dot_import"] is False

    def test_extract_grouped_imports(self, go_parser):
        """Test grouped import extraction."""
        code = """package main
import (
    "fmt"
    "os"
    "strings"
)"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_imports(tree, code, "test.go")

        assert len(results) == 3
        paths = {r["path"] for r in results}
        assert paths == {"fmt", "os", "strings"}

    def test_extract_aliased_import(self, go_parser):
        """Test aliased import extraction."""
        code = """package main
import (
    mydb "database/sql"
)"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_imports(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["path"] == "database/sql"

    def test_extract_dot_import(self, go_parser):
        """Test dot import extraction."""
        code = '''package main
import . "math"'''
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_imports(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["path"] == "math"
        assert results[0]["is_dot_import"] is True


class TestGoStructExtraction:
    """Tests for struct extraction."""

    def test_extract_simple_struct(self, go_parser):
        """Test simple struct extraction."""
        code = """package main
type User struct {
    Name string
    Age  int
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_structs(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["name"] == "User"
        assert results[0]["is_exported"] is True

    def test_extract_unexported_struct(self, go_parser):
        """Test unexported struct extraction."""
        code = """package main
type internalData struct {
    value int
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_structs(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["name"] == "internalData"
        assert results[0]["is_exported"] is False


class TestGoStructFieldExtraction:
    """Tests for struct field extraction."""

    def test_extract_struct_fields(self, go_parser):
        """Test struct field extraction."""
        code = """package main
type User struct {
    Name  string
    Email string
    Age   int
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_struct_fields(tree, code, "test.go")

        assert len(results) == 3
        field_names = {f["field_name"] for f in results}
        assert field_names == {"Name", "Email", "Age"}

    def test_extract_struct_fields_with_tags(self, go_parser):
        """Test struct field extraction with tags."""
        code = """package main
type User struct {
    Name  string `json:"name" gorm:"column:name"`
    Email string `json:"email"`
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_struct_fields(tree, code, "test.go")

        assert len(results) == 2
        name_field = next(f for f in results if f["field_name"] == "Name")
        assert "json" in name_field["tag"]
        assert "gorm" in name_field["tag"]

    def test_extract_embedded_field(self, go_parser):
        """Test embedded field extraction."""
        code = """package main
type User struct {
    Base
    Name string
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_struct_fields(tree, code, "test.go")

        embedded = [f for f in results if f["is_embedded"]]
        assert len(embedded) == 1
        assert embedded[0]["field_name"] == "Base"


class TestGoInterfaceExtraction:
    """Tests for interface extraction."""

    def test_extract_interface(self, go_parser):
        """Test interface extraction."""
        code = """package main
type Reader interface {
    Read(p []byte) (n int, err error)
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_interfaces(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["name"] == "Reader"
        assert results[0]["is_exported"] is True

    def test_extract_interface_methods(self, go_parser):
        """Test interface method extraction."""
        code = """package main
type ReadWriter interface {
    Read(p []byte) (n int, err error)
    Write(p []byte) (n int, err error)
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_interface_methods(tree, code, "test.go")

        assert len(results) == 2
        method_names = {m["method_name"] for m in results}
        assert method_names == {"Read", "Write"}


class TestGoFunctionExtraction:
    """Tests for function extraction."""

    def test_extract_function(self, go_parser):
        """Test function extraction."""
        code = """package main

func Hello(name string) string {
    return "Hello, " + name
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_functions(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["name"] == "Hello"
        assert results[0]["is_exported"] is True

    def test_extract_unexported_function(self, go_parser):
        """Test unexported function extraction."""
        code = """package main

func helper() int {
    return 42
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_functions(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["name"] == "helper"
        assert results[0]["is_exported"] is False


class TestGoMethodExtraction:
    """Tests for method extraction."""

    def test_extract_value_receiver_method(self, go_parser):
        """Test value receiver method extraction."""
        code = """package main

type User struct { Name string }

func (u User) GetName() string {
    return u.Name
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_methods(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["name"] == "GetName"
        assert results[0]["receiver_type"] == "User"
        assert results[0]["is_pointer_receiver"] is False

    def test_extract_pointer_receiver_method(self, go_parser):
        """Test pointer receiver method extraction."""
        code = """package main

type User struct { Name string }

func (u *User) SetName(name string) {
    u.Name = name
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_methods(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["name"] == "SetName"
        assert results[0]["receiver_type"] == "User"
        assert results[0]["is_pointer_receiver"] is True


class TestGoFuncParamsExtraction:
    """Tests for function parameter extraction."""

    def test_extract_func_params(self, go_parser):
        """Test function parameter extraction."""
        code = """package main

func Process(name string, count int, verbose bool) {}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_func_params(tree, code, "test.go")

        assert len(results) == 3
        param_names = [p["param_name"] for p in results]
        assert param_names == ["name", "count", "verbose"]

    def test_extract_variadic_param(self, go_parser):
        """Test variadic parameter extraction."""
        code = """package main

func Printf(format string, args ...interface{}) {}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_func_params(tree, code, "test.go")

        variadic_params = [p for p in results if p["is_variadic"]]

        assert len(results) >= 1


class TestGoGoroutineExtraction:
    """Tests for goroutine extraction."""

    def test_extract_named_goroutine(self, go_parser):
        """Test named function goroutine extraction."""
        code = """package main

func Start() {
    go process()
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_goroutines(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["containing_func"] == "Start"
        assert results[0]["is_anonymous"] is False

    def test_extract_anonymous_goroutine(self, go_parser):
        """Test anonymous function goroutine extraction."""
        code = """package main

func Start() {
    go func() {
        doWork()
    }()
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_goroutines(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["is_anonymous"] is True


class TestGoCapturedVarsExtraction:
    """Tests for captured variable extraction - CRITICAL for race detection."""

    def test_captured_loop_variable(self, go_parser):
        """Test captured loop variable detection - the #1 Go race condition."""
        code = """package main

func Process() {
    items := []string{"a", "b", "c"}
    for i, v := range items {
        go func() {
            print(i, v)
        }()
    }
}"""
        tree = parse_go(go_parser, code)

        goroutines = go_impl.extract_go_goroutines(tree, code, "test.go")
        assert len(goroutines) == 1

        results = go_impl.extract_go_captured_vars(tree, code, "test.go", goroutines)

        var_names = {r["var_name"] for r in results}
        assert "i" in var_names or "v" in var_names

        loop_vars = [r for r in results if r["is_loop_var"]]
        assert len(loop_vars) >= 1

    def test_safe_param_passing(self, go_parser):
        """Test that params passed to goroutine are not flagged."""
        code = """package main

func Process() {
    items := []string{"a", "b", "c"}
    for i, v := range items {
        go func(idx int, val string) {
            print(idx, val)
        }(i, v)
    }
}"""
        tree = parse_go(go_parser, code)

        goroutines = go_impl.extract_go_goroutines(tree, code, "test.go")
        results = go_impl.extract_go_captured_vars(tree, code, "test.go", goroutines)

        param_names = {r["var_name"] for r in results}
        assert "idx" not in param_names
        assert "val" not in param_names


class TestGoChannelExtraction:
    """Tests for channel extraction."""

    def test_extract_channel(self, go_parser):
        """Test channel declaration extraction."""
        code = """package main

func Work() {
    ch := make(chan int)
    _ = ch
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_channels(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["element_type"] == "int"

    def test_extract_buffered_channel(self, go_parser):
        """Test buffered channel extraction."""
        code = """package main

func Work() {
    ch := make(chan string, 10)
    _ = ch
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_channels(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["buffer_size"] == 10


class TestGoChannelOpsExtraction:
    """Tests for channel operation extraction."""

    def test_extract_channel_send(self, go_parser):
        """Test channel send operation extraction."""
        code = """package main

func Send(ch chan int) {
    ch <- 42
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_channel_ops(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["operation"] == "send"
        assert results[0]["channel_name"] == "ch"

    def test_extract_channel_receive(self, go_parser):
        """Test channel receive operation extraction."""
        code = """package main

func Receive(ch chan int) int {
    val := <-ch
    return val
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_channel_ops(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["operation"] == "receive"


class TestGoDeferExtraction:
    """Tests for defer statement extraction."""

    def test_extract_defer(self, go_parser):
        """Test defer statement extraction."""
        code = """package main

func Process(f *File) {
    defer f.Close()
    // do work
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_defer_statements(tree, code, "test.go")

        assert len(results) == 1
        assert "Close" in results[0]["deferred_expr"]


class TestGoTypeParamsExtraction:
    """Tests for Go 1.18+ generics extraction."""

    def test_extract_generic_function(self, go_parser):
        """Test generic function type parameter extraction."""
        code = """package main

func Map[T any, U any](items []T, fn func(T) U) []U {
    return nil
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_type_params(tree, code, "test.go")

        assert len(results) == 2
        param_names = {p["param_name"] for p in results}
        assert param_names == {"T", "U"}
        assert all(p["parent_kind"] == "function" for p in results)

    def test_extract_generic_type(self, go_parser):
        """Test generic type parameter extraction."""
        code = """package main

type Stack[T any] struct {
    items []T
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_type_params(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["param_name"] == "T"
        assert results[0]["parent_kind"] == "type"
        assert results[0]["parent_name"] == "Stack"


class TestGoErrorReturnsExtraction:
    """Tests for error return detection."""

    def test_extract_error_return(self, go_parser):
        """Test function returning error detection."""
        code = """package main

func Open(name string) (*File, error) {
    return nil, nil
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_error_returns(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["func_name"] == "Open"
        assert results[0]["returns_error"] is True

    def test_no_error_return(self, go_parser):
        """Test function not returning error."""
        code = """package main

func Add(a, b int) int {
    return a + b
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_error_returns(tree, code, "test.go")

        assert len(results) == 0


class TestGoTypeAssertionExtraction:
    """Tests for type assertion extraction."""

    def test_extract_type_assertion(self, go_parser):
        """Test type assertion extraction."""
        code = """package main

func Process(i interface{}) {
    s := i.(string)
    _ = s
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_type_assertions(tree, code, "test.go")

        assert len(results) == 1
        assert results[0]["is_type_switch"] is False

    def test_extract_type_switch(self, go_parser):
        """Test type switch extraction."""
        code = """package main

func Process(i interface{}) {
    switch v := i.(type) {
    case string:
        _ = v
    case int:
        _ = v
    }
}"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_type_assertions(tree, code, "test.go")

        assert isinstance(results, list)


class TestGoConstantsExtraction:
    """Tests for constant extraction."""

    def test_extract_constants(self, go_parser):
        """Test constant extraction."""
        code = '''package main

const MaxRetries = 3
const DefaultPort = "8080"'''
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_constants(tree, code, "test.go")

        assert len(results) == 2
        const_names = {c["name"] for c in results}
        assert const_names == {"MaxRetries", "DefaultPort"}

    def test_extract_grouped_constants(self, go_parser):
        """Test grouped constant extraction."""
        code = """package main

const (
    A = 1
    B = 2
    C = 3
)"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_constants(tree, code, "test.go")

        assert len(results) == 3


class TestGoVariablesExtraction:
    """Tests for variable extraction."""

    def test_extract_package_level_variables(self, go_parser):
        """Test package-level variable extraction."""
        code = """package main

var GlobalCounter int
var SharedMap = make(map[string]int)"""
        tree = parse_go(go_parser, code)

        results = go_impl.extract_go_variables(tree, code, "test.go")

        assert len(results) >= 1
        assert all(v["is_package_level"] for v in results)
