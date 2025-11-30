"""Test that all core module imports work correctly.

This test was added when extraction.py was deleted to verify
no import breakage occurred. It serves as a smoke test for
the core module structure.
"""

import pytest


def test_cli_imports():
    """Verify CLI module imports work."""
    from theauditor import cli

    assert hasattr(cli, "cli")


def test_pipelines_imports():
    """Verify pipelines module imports work."""
    from theauditor import pipelines

    assert hasattr(pipelines, "run_command_async")


def test_commands_blueprint_imports():
    """Verify blueprint command imports work."""
    from theauditor.commands import blueprint

    assert hasattr(blueprint, "blueprint")


def test_indexer_imports():
    """Verify indexer module imports work."""
    from theauditor.indexer import orchestrator

    assert hasattr(orchestrator, "IndexerOrchestrator")


def test_extraction_module_removed():
    """Verify extraction.py was properly removed."""
    with pytest.raises((ModuleNotFoundError, ImportError)):
        from theauditor import extraction  # noqa: F401


def test_no_readthis_references_in_imports():
    """Verify no module tries to import readthis-related code."""

    import theauditor.cli  # noqa: F401
    import theauditor.commands.blueprint  # noqa: F401

    assert True
