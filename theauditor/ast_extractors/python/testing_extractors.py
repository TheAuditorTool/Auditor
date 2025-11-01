"""Python testing pattern extractors - pytest and unittest.

This module contains extraction logic for Python testing frameworks:
- pytest fixtures (@pytest.fixture)
- pytest parametrize (@pytest.mark.parametrize)
- pytest markers (custom markers)
- unittest.mock patterns

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""

import ast
import logging
from typing import Any, Dict, List, Optional

from ..base import get_node_name

logger = logging.getLogger(__name__)


def extract_pytest_fixtures(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract pytest fixture definitions from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of pytest fixture records
    """
    fixtures = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return fixtures

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                decorator_name = get_node_name(dec)

                # Check if it's a pytest.fixture decorator
                if "fixture" in decorator_name:
                    # Extract scope if present
                    scope = "function"  # default
                    if isinstance(dec, ast.Call):
                        for keyword in dec.keywords:
                            if keyword.arg == "scope":
                                if isinstance(keyword.value, ast.Constant):
                                    scope = keyword.value.value
                                elif isinstance(keyword.value, ast.Str):
                                    scope = keyword.value.s

                    fixtures.append({
                        "line": node.lineno,
                        "fixture_name": node.name,
                        "scope": scope,
                        "is_autouse": any(
                            kw.arg == "autouse" and
                            (isinstance(kw.value, ast.Constant) and kw.value.value is True or
                             isinstance(kw.value, ast.NameConstant) and kw.value.value is True)
                            for kw in (dec.keywords if isinstance(dec, ast.Call) else [])
                        ),
                    })

    return fixtures


def extract_pytest_parametrize(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract pytest.mark.parametrize decorators from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of parametrize records
    """
    parametrizes = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return parametrizes

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                decorator_name = get_node_name(dec)

                # Check if it's a pytest.mark.parametrize decorator
                if "parametrize" in decorator_name:
                    # Extract parameter names
                    param_names = []
                    if isinstance(dec, ast.Call) and dec.args:
                        first_arg = dec.args[0]
                        if isinstance(first_arg, ast.Constant):
                            param_names = [first_arg.value]
                        elif isinstance(first_arg, ast.Str):
                            param_names = [first_arg.s]

                    parametrizes.append({
                        "line": node.lineno,
                        "test_name": node.name,
                        "param_names": param_names,
                    })

    return parametrizes


def extract_pytest_markers(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract custom pytest markers from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of marker records
    """
    markers = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return markers

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                decorator_name = get_node_name(dec)

                # Check if it's a pytest.mark.* decorator (but not parametrize/fixture)
                if "pytest.mark." in decorator_name and "parametrize" not in decorator_name:
                    # Extract marker name
                    marker_name = decorator_name.replace("pytest.mark.", "")

                    markers.append({
                        "line": node.lineno,
                        "test_name": node.name,
                        "marker_name": marker_name,
                    })

    return markers


def extract_mock_patterns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract unittest.mock usage from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of mock pattern records
    """
    mocks = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return mocks

    for node in ast.walk(actual_tree):
        # Detect @mock.patch, @patch decorators
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                decorator_name = get_node_name(dec)

                if "patch" in decorator_name or "mock" in decorator_name.lower():
                    # Extract what's being mocked
                    mock_target = None
                    if isinstance(dec, ast.Call) and dec.args:
                        first_arg = dec.args[0]
                        if isinstance(first_arg, ast.Constant):
                            mock_target = first_arg.value
                        elif isinstance(first_arg, ast.Str):
                            mock_target = first_arg.s

                    mocks.append({
                        "line": node.lineno,
                        "test_name": node.name,
                        "mock_type": "decorator",
                        "mock_target": mock_target,
                    })

        # Detect Mock() and MagicMock() instantiations
        elif isinstance(node, ast.Call):
            func_name = get_node_name(node.func)
            if "Mock" in func_name or "mock" in func_name:
                mocks.append({
                    "line": node.lineno,
                    "mock_type": "instantiation",
                    "mock_class": func_name,
                })

    return mocks


# Phase 3.2: Testing Ecosystem Additions

def extract_unittest_test_cases(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract unittest.TestCase classes and test methods.

    Detects:
    - TestCase class inheritance
    - setUp/tearDown methods
    - test_* methods
    - Assertion method usage

    Security relevance:
    - Test coverage = code quality
    - Missing tests = potential bugs
    - setUp without tearDown = resource leaks
    """
    test_cases = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return test_cases

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if inherits from TestCase
        base_names = [get_node_name(base) for base in node.bases]
        is_test_case = any('TestCase' in base for base in base_names)
        if not is_test_case:
            continue

        # Scan class methods
        test_methods = []
        has_setup = False
        has_teardown = False
        has_setupclass = False
        has_teardownclass = False

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_name = item.name
                if method_name.startswith('test_'):
                    test_methods.append(method_name)
                elif method_name == 'setUp':
                    has_setup = True
                elif method_name == 'tearDown':
                    has_teardown = True
                elif method_name == 'setUpClass':
                    has_setupclass = True
                elif method_name == 'tearDownClass':
                    has_teardownclass = True

        test_cases.append({
            "line": node.lineno,
            "test_class_name": node.name,
            "test_method_count": len(test_methods),
            "has_setup": has_setup,
            "has_teardown": has_teardown,
            "has_setupclass": has_setupclass,
            "has_teardownclass": has_teardownclass,
        })

    return test_cases


def extract_assertion_patterns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract assertion statements and methods.

    Detects:
    - assert statements
    - self.assertEqual, self.assertTrue, etc.
    - pytest.raises context managers
    - Assertion counts per function

    Security relevance:
    - Functions without assertions = untested code
    - Complex functions with few assertions = insufficient testing
    """
    assertions = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return assertions

    # Track assertions per function
    current_function = None

    for node in ast.walk(actual_tree):
        # Track current function context
        if isinstance(node, ast.FunctionDef):
            current_function = node.name

        # Direct assert statements
        elif isinstance(node, ast.Assert):
            assertions.append({
                "line": node.lineno,
                "function_name": current_function or '<module>',
                "assertion_type": "assert",
                "test_expr": get_node_name(node.test) if hasattr(node.test, '__class__') else 'unknown',
            })

        # Unittest assertion methods (self.assertEqual, etc.)
        elif isinstance(node, ast.Call):
            func_name = get_node_name(node.func)
            if func_name and (func_name.startswith('self.assert') or func_name.startswith('self.fail')):
                assertion_method = func_name.replace('self.', '')
                assertions.append({
                    "line": node.lineno,
                    "function_name": current_function or '<module>',
                    "assertion_type": "unittest",
                    "assertion_method": assertion_method,
                })

    return assertions


def extract_pytest_plugin_hooks(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract pytest plugin hooks from conftest.py.

    Detects:
    - pytest_configure
    - pytest_collection_modifyitems
    - pytest_addoption
    - pytest_runtest_* hooks
    - Custom fixtures in conftest.py

    Security relevance:
    - Plugin hooks = test infrastructure
    - Malicious conftest.py = test manipulation
    - Custom collection = test selection bias
    """
    hooks = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return hooks

    pytest_hooks = [
        'pytest_configure',
        'pytest_collection_modifyitems',
        'pytest_addoption',
        'pytest_runtest_setup',
        'pytest_runtest_call',
        'pytest_runtest_teardown',
        'pytest_sessionstart',
        'pytest_sessionfinish',
        'pytest_collection_finish',
    ]

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check if it's a pytest hook
        if node.name in pytest_hooks:
            # Count number of parameters
            param_count = len(node.args.args)

            hooks.append({
                "line": node.lineno,
                "hook_name": node.name,
                "param_count": param_count,
            })

    return hooks


def extract_hypothesis_strategies(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Hypothesis property-based testing strategies.

    Detects:
    - @given decorators
    - Strategy usage (st.integers, st.text, etc.)
    - @example decorators
    - Stateful testing classes

    Security relevance:
    - Property-based testing = edge case coverage
    - Missing strategies = incomplete fuzzing
    - Stateful tests = complex behavior validation
    """
    strategies = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return strategies

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check for @given decorator
        for dec in node.decorator_list:
            decorator_name = get_node_name(dec)

            if 'given' in decorator_name:
                # Extract strategy types from arguments
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

                strategies.append({
                    "line": node.lineno,
                    "test_name": node.name,
                    "strategy_count": len(strategy_types),
                    "strategies": ','.join(strategy_types) if strategy_types else None,
                })

    return strategies
