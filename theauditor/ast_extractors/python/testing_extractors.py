"""Python testing pattern extractors - pytest and unittest."""

import ast
from typing import Any

from ..base import get_node_name
from .utils.context import FileContext


def extract_pytest_fixtures(context: FileContext) -> list[dict[str, Any]]:
    """Extract pytest fixture definitions from Python AST."""
    fixtures = []

    if not context.tree:
        return fixtures

    for node in context.find_nodes(ast.FunctionDef):
        for dec in node.decorator_list:
            decorator_name = get_node_name(dec)

            if "fixture" in decorator_name:
                scope = "function"
                if isinstance(dec, ast.Call):
                    for keyword in dec.keywords:
                        if keyword.arg == "scope" and (
                            isinstance(keyword.value, ast.Constant)
                            or isinstance(keyword.value, ast.Constant)
                            and isinstance(keyword.value.value, str)
                        ):
                            scope = keyword.value.value

                fixtures.append(
                    {
                        "line": node.lineno,
                        "fixture_name": node.name,
                        "scope": scope,
                        "is_autouse": any(
                            kw.arg == "autouse"
                            and (
                                isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                                or isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            )
                            for kw in (dec.keywords if isinstance(dec, ast.Call) else [])
                        ),
                    }
                )

    return fixtures


def extract_pytest_parametrize(context: FileContext) -> list[dict[str, Any]]:
    """Extract pytest.mark.parametrize decorators from Python AST."""
    parametrizes = []

    if not context.tree:
        return parametrizes

    for node in context.find_nodes(ast.FunctionDef):
        for dec in node.decorator_list:
            decorator_name = get_node_name(dec)

            if "parametrize" in decorator_name:
                param_names = []
                params = []

                if isinstance(dec, ast.Call) and dec.args:
                    first_arg = dec.args[0]
                    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                        param_names = [n.strip() for n in first_arg.value.split(",")]

                    if len(dec.args) >= 2:
                        second_arg = dec.args[1]
                        if isinstance(second_arg, (ast.List, ast.Tuple)):
                            for idx, elt in enumerate(second_arg.elts):
                                try:
                                    value_str = ast.unparse(elt)
                                except Exception:
                                    value_str = "<complex>"

                                name = param_names[0] if param_names else str(idx)
                                params.append({"name": name, "value": value_str})

                parametrizes.append(
                    {
                        "line": node.lineno,
                        "test_name": node.name,
                        "param_names": param_names,
                        "params": params,
                    }
                )

    return parametrizes


def extract_pytest_markers(context: FileContext) -> list[dict[str, Any]]:
    """Extract custom pytest markers from Python AST."""
    markers = []

    if not context.tree:
        return markers

    for node in context.find_nodes(ast.FunctionDef):
        for dec in node.decorator_list:
            decorator_name = get_node_name(dec)

            if "pytest.mark." in decorator_name and "parametrize" not in decorator_name:
                marker_name = decorator_name.replace("pytest.mark.", "")

                markers.append(
                    {
                        "line": node.lineno,
                        "test_name": node.name,
                        "marker_name": marker_name,
                    }
                )

    return markers


def extract_mock_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract unittest.mock usage from Python AST."""
    mocks = []

    if not context.tree:
        return mocks

    for node in context.find_nodes(ast.FunctionDef):
        for dec in node.decorator_list:
            decorator_name = get_node_name(dec)

            if "patch" in decorator_name or "mock" in decorator_name.lower():
                mock_target = None
                if isinstance(dec, ast.Call) and dec.args:
                    first_arg = dec.args[0]
                    if (
                        isinstance(first_arg, ast.Constant)
                        or isinstance(first_arg, ast.Constant)
                        and isinstance(first_arg.value, str)
                    ):
                        mock_target = first_arg.value

                mocks.append(
                    {
                        "line": node.lineno,
                        "test_name": node.name,
                        "mock_type": "decorator",
                        "mock_target": mock_target,
                    }
                )

    for node in context.find_nodes(ast.Call):
        func_name = get_node_name(node.func)
        if "Mock" in func_name or "mock" in func_name:
            mocks.append(
                {
                    "line": node.lineno,
                    "mock_type": "instantiation",
                    "mock_class": func_name,
                }
            )

    return mocks


def extract_unittest_test_cases(context: FileContext) -> list[dict[str, Any]]:
    """Extract unittest.TestCase classes and test methods."""
    test_cases = []

    if not context.tree:
        return test_cases

    for node in context.find_nodes(ast.ClassDef):
        base_names = [get_node_name(base) for base in node.bases]
        is_test_case = any("TestCase" in base for base in base_names)
        if not is_test_case:
            continue

        test_methods = []
        has_setup = False
        has_teardown = False
        has_setupclass = False
        has_teardownclass = False

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_name = item.name
                if method_name.startswith("test_"):
                    test_methods.append(method_name)
                elif method_name == "setUp":
                    has_setup = True
                elif method_name == "tearDown":
                    has_teardown = True
                elif method_name == "setUpClass":
                    has_setupclass = True
                elif method_name == "tearDownClass":
                    has_teardownclass = True

        test_cases.append(
            {
                "line": node.lineno,
                "test_class_name": node.name,
                "test_method_count": len(test_methods),
                "has_setup": has_setup,
                "has_teardown": has_teardown,
                "has_setupclass": has_setupclass,
                "has_teardownclass": has_teardownclass,
            }
        )

    return test_cases


def extract_assertion_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract assertion statements and methods."""
    assertions = []

    if not context.tree:
        return assertions

    function_ranges = {}
    for node in context.find_nodes(ast.FunctionDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    def get_containing_function(line_no):
        for fname, (start, end) in function_ranges.items():
            if start <= line_no <= end:
                return fname
        return "<module>"

    for node in context.find_nodes(ast.Assert):
        assertions.append(
            {
                "line": node.lineno,
                "function_name": get_containing_function(node.lineno),
                "assertion_type": "assert",
                "test_expr": get_node_name(node.test)
                if hasattr(node.test, "__class__")
                else "unknown",
            }
        )

    for node in context.find_nodes(ast.Call):
        func_name = get_node_name(node.func)
        if func_name and (func_name.startswith("self.assert") or func_name.startswith("self.fail")):
            assertion_method = func_name.replace("self.", "")
            assertions.append(
                {
                    "line": node.lineno,
                    "function_name": get_containing_function(node.lineno),
                    "assertion_type": "unittest",
                    "assertion_method": assertion_method,
                }
            )

    return assertions


def extract_pytest_plugin_hooks(context: FileContext) -> list[dict[str, Any]]:
    """Extract pytest plugin hooks from conftest.py."""
    hooks = []

    if not context.tree:
        return hooks

    pytest_hooks = [
        "pytest_configure",
        "pytest_collection_modifyitems",
        "pytest_addoption",
        "pytest_runtest_setup",
        "pytest_runtest_call",
        "pytest_runtest_teardown",
        "pytest_sessionstart",
        "pytest_sessionfinish",
        "pytest_collection_finish",
    ]

    for node in context.find_nodes(ast.FunctionDef):
        if node.name in pytest_hooks:
            param_count = len(node.args.args)

            hooks.append(
                {
                    "line": node.lineno,
                    "hook_name": node.name,
                    "param_count": param_count,
                }
            )

    return hooks


def extract_hypothesis_strategies(context: FileContext) -> list[dict[str, Any]]:
    """Extract Hypothesis property-based testing strategies."""
    strategies = []

    if not context.tree:
        return strategies

    for node in context.find_nodes(ast.FunctionDef):
        for dec in node.decorator_list:
            decorator_name = get_node_name(dec)

            if "given" in decorator_name:
                strategy_types = []
                if isinstance(dec, ast.Call):
                    for arg in dec.args:
                        strategy_name = get_node_name(arg)
                        if strategy_name:
                            strategy_types.append(strategy_name)
                    for keyword in dec.keywords:
                        strategy_name = get_node_name(keyword.value)
                        if strategy_name:
                            strategy_types.append(strategy_name)

                strategies.append(
                    {
                        "line": node.lineno,
                        "test_name": node.name,
                        "strategy_count": len(strategy_types),
                        "strategies": ",".join(strategy_types) if strategy_types else None,
                    }
                )

    return strategies
