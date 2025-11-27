"""Pytest fixture extraction test."""

import sys
from typing import Dict, List

import pytest


@pytest.fixture
def sample_data():
    """Basic function-scoped fixture."""
    return {'key': 'value', 'count': 42}


@pytest.fixture(scope='module')
def database_connection():
    """Module-scoped database fixture."""
    # Setup
    conn = {'connected': True}
    yield conn
    # Teardown
    conn['connected'] = False


@pytest.fixture(scope='session', autouse=True)
def configure_test_environment():
    """Session-scoped autouse fixture."""
    print("Setting up test environment")
    yield
    print("Tearing down test environment")


@pytest.fixture(scope='class')
def class_fixture():
    """Class-scoped fixture."""
    return "class_data"


# Parametrized tests
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    (4, 8),
])
def test_double(input, expected):
    """Test with parametrize."""
    assert input * 2 == expected


@pytest.mark.parametrize("x,y,result", [
    (1, 1, 2),
    (2, 3, 5),
    (-1, 1, 0),
])
def test_addition(x, y, result):
    """Test addition with parametrize."""
    assert x + y == result


# Marked tests
@pytest.mark.slow
def test_slow_operation():
    """Test marked as slow."""
    import time
    time.sleep(0.1)
    assert True


@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    """Test marked for skipping."""
    assert False


@pytest.mark.skipif(sys.version_info < (3, 8), reason="Requires Python 3.8+")
def test_modern_python():
    """Test with conditional skip."""
    assert True


@pytest.mark.xfail
def test_expected_failure():
    """Test expected to fail."""
    assert False


@pytest.mark.integration
@pytest.mark.slow
def test_integration_slow():
    """Test with multiple markers."""
    assert True


# Test using fixtures
def test_with_fixture(sample_data):
    """Test using a fixture."""
    assert sample_data['count'] == 42


def test_with_database(database_connection):
    """Test using database fixture."""
    assert database_connection['connected'] is True
