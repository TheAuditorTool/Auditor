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
