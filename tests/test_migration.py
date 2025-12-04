"""Unit tests for stdlib to Loguru migration codemod.

Run with:
    python tests/test_migration.py
    # or
    pytest tests/test_migration.py -v
"""

import sys
import unittest
from pathlib import Path

# Add project root to path so we can import from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

from libcst.codemod import CodemodTest

from scripts.stdlib_loguru_migrationv2 import StdlibToLoguruCodemod


class TestLoguruMigration(CodemodTest):
    """Test suite for StdlibToLoguruCodemod."""

    TRANSFORM = StdlibToLoguruCodemod

    def test_standard_migration(self):
        """Verify the standard logger = getLogger case."""
        before = """\
import logging
logger = logging.getLogger(__name__)

def foo():
    logger.info("Test")
"""
        after = """\
from theauditor.utils.logging import logger

def foo():
    logger.info("Test")
"""
        self.assertCodemod(before, after)

    def test_alias_renaming(self):
        """Verify that 'log' is renamed to 'logger'."""
        before = """\
import logging
log = logging.getLogger(__name__)

def check():
    log.info("Test")
"""
        after = """\
from theauditor.utils.logging import logger

def check():
    logger.info("Test")
"""
        self.assertCodemod(before, after)

    def test_underscore_logger_alias(self):
        """Verify that '_logger' is renamed to 'logger'."""
        before = """\
import logging
_logger = logging.getLogger(__name__)

def check():
    _logger.warning("Warning!")
"""
        after = """\
from theauditor.utils.logging import logger

def check():
    logger.warning("Warning!")
"""
        self.assertCodemod(before, after)

    def test_skips_instance_attributes(self):
        """Verify safety: Do NOT touch self.logger assignments."""
        code = """\
import logging

class MyClass:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.info("Running")
"""
        # Should remain exactly the same - we don't transform instance attributes
        self.assertCodemod(code, code)

    def test_skips_class_attributes(self):
        """Verify safety: Do NOT touch cls.logger assignments."""
        code = """\
import logging

class MyClass:
    @classmethod
    def setup(cls):
        cls.logger = logging.getLogger(__name__)
"""
        # Should remain exactly the same
        self.assertCodemod(code, code)

    def test_preserves_logging_constants(self):
        """Verify that 'import logging' is preserved if used for constants."""
        before = """\
import logging
logger = logging.getLogger(__name__)

def foo():
    print(logging.ERROR)
    logger.error("Test")
"""
        after = """\
import logging
from theauditor.utils.logging import logger

def foo():
    print(logging.ERROR)
    logger.error("Test")
"""
        self.assertCodemod(before, after)

    def test_no_transformation_needed(self):
        """Verify files without logging.getLogger are unchanged."""
        code = """\
def hello():
    print("Hello, world!")
"""
        self.assertCodemod(code, code)

    def test_already_using_loguru(self):
        """Verify files already using loguru are unchanged."""
        code = """\
from theauditor.utils.logging import logger

def foo():
    logger.info("Already migrated")
"""
        self.assertCodemod(code, code)

    def test_multiple_logger_methods(self):
        """Verify all logger methods work after transformation."""
        before = """\
import logging
logger = logging.getLogger(__name__)

def comprehensive():
    logger.debug("Debug")
    logger.info("Info")
    logger.warning("Warning")
    logger.error("Error")
    logger.exception("Exception")
    logger.critical("Critical")
"""
        after = """\
from theauditor.utils.logging import logger

def comprehensive():
    logger.debug("Debug")
    logger.info("Info")
    logger.warning("Warning")
    logger.error("Error")
    logger.exception("Exception")
    logger.critical("Critical")
"""
        self.assertCodemod(before, after)

    def test_logger_with_string_name(self):
        """Verify getLogger with string argument works."""
        before = """\
import logging
logger = logging.getLogger("my.custom.logger")

logger.info("Custom name")
"""
        after = """\
from theauditor.utils.logging import logger

logger.info("Custom name")
"""
        self.assertCodemod(before, after)


if __name__ == "__main__":
    unittest.main()
