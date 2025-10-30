"""Tests with pytest.mark.parametrize and markers.

These patterns should be extracted by testing_extractors.py.
"""
import pytest


# pytest.mark.parametrize patterns
@pytest.mark.parametrize("username,email,expected", [
    ("john_doe", "john@example.com", True),
    ("jane_doe", "jane@example.com", True),
    ("invalid", "notanemail", False),
    ("", "empty@example.com", False),
])
def test_user_validation(username, email, expected):
    """Test user validation with multiple parameter sets.

    Should be extracted as parametrize with 3 parameter names and 4 argvalue sets.
    """
    # Mock validation
    is_valid = bool(username) and "@" in email
    assert is_valid == expected


@pytest.mark.parametrize("user_id", [1, 2, 3, 100, 999])
def test_fetch_user_by_id(user_id):
    """Test fetching user by various IDs.

    Should be extracted as parametrize with 1 parameter and 5 argvalues.
    """
    # Mock fetch
    user = {"id": user_id}
    assert user["id"] == user_id


@pytest.mark.parametrize(
    "input_data,expected_output",
    [
        ({"name": "Alice"}, {"name": "ALICE"}),
        ({"name": "bob"}, {"name": "BOB"}),
        ({}, {}),
    ]
)
def test_data_transformation(input_data, expected_output):
    """Test data transformation with dict parameters."""
    result = {k: v.upper() if isinstance(v, str) else v for k, v in input_data.items()}
    assert result == expected_output


# Custom pytest markers
@pytest.mark.slow
def test_slow_operation():
    """Test marked as slow.

    Should be extracted as pytest marker 'slow'.
    """
    import time
    time.sleep(0.1)
    assert True


@pytest.mark.integration
def test_database_integration():
    """Test marked as integration.

    Should be extracted as pytest marker 'integration'.
    """
    assert True


@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    """Test marked with skip and reason.

    Should be extracted as pytest marker 'skip' with args.
    """
    pass


@pytest.mark.xfail(strict=True)
def test_known_failure():
    """Test marked as expected failure.

    Should be extracted as pytest marker 'xfail' with args.
    """
    assert False


# Multiple markers on same test
@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize("count", [10, 100, 1000])
def test_bulk_operation(count):
    """Test with multiple markers AND parametrize.

    Should extract:
    - 2 pytest markers (slow, integration)
    - 1 parametrize with 1 parameter and 3 argvalues
    """
    assert count > 0


# Parametrize with ids
@pytest.mark.parametrize(
    "value,expected",
    [
        (1, 2),
        (5, 10),
        (0, 0),
    ],
    ids=["double_one", "double_five", "double_zero"]
)
def test_doubling_with_ids(value, expected):
    """Parametrize with custom test IDs."""
    assert value * 2 == expected
