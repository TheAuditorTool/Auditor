"""Test suite for loguru_migration.py codemod.

Verifies the three critical fixes:
1. Multi-argument preservation: print("[TAG] msg", var) -> logger.level("msg", var)
2. Keyword argument stripping: file=sys.stderr, flush=True are dropped
3. ConcatenatedString handling: recursive tag stripping from left side

Run with: python -m pytest tests/test_loguru_migration.py -v
"""
import os
import sys
import unittest

# Add scripts directory to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from libcst.codemod import CodemodTest

from loguru_migration import PrintToLoguruCodemod


class TestPrintToLoguruMigration(CodemodTest):
    """Test suite using LibCST's CodemodTest framework."""

    TRANSFORM = PrintToLoguruCodemod

    def test_basic_tag_replacement(self) -> None:
        """Test simple [TAG] string replacement and import addition."""
        before = """
print("[INFO] Starting process")
"""
        after = """
from theauditor.utils.logging import logger

logger.info("Starting process")
"""
        self.assertCodemod(before, after)

    def test_fstring_tag_stripping(self) -> None:
        """Test stripping tags from inside f-strings."""
        before = """
print(f"[TRACE] Value is {x}")
"""
        after = """
from theauditor.utils.logging import logger

logger.trace(f"Value is {x}")
"""
        self.assertCodemod(before, after)

    def test_multi_argument_preservation(self) -> None:
        """CRITICAL: Multi-args get format string to prevent Loguru silent drop."""
        before = """
user_id = 123
print("[DEBUG] Processing user:", user_id)
"""
        # CRITICAL FIX: Inject format string "{} {}" to prevent data loss
        # Without this, Loguru would silently drop user_id!
        after = """
from theauditor.utils.logging import logger

user_id = 123
logger.debug("{} {}", "Processing user:", user_id)
"""
        self.assertCodemod(before, after)

    def test_keyword_argument_stripping(self) -> None:
        """Ensure file=sys.stderr and flush=True are removed (Loguru crashes on them)."""
        before = """
import sys
print("[ERROR] Fatal crash", file=sys.stderr, flush=True)
"""
        # LibCST AddImportsVisitor puts new imports after existing imports
        after = """
import sys
from theauditor.utils.logging import logger

logger.error("Fatal crash")
"""
        self.assertCodemod(before, after)

    def test_concatenated_string_handling(self) -> None:
        """Test stripping tags from concatenated strings - left side becomes empty."""
        before = """
print("[INFO] " + message)
"""
        after = """
from theauditor.utils.logging import logger

logger.info(message)
"""
        self.assertCodemod(before, after)

    def test_concatenated_string_with_content(self) -> None:
        """Test stripping tags from concatenated strings - left side has content."""
        before = """
print("[WARN] User input: " + user_input)
"""
        after = """
from theauditor.utils.logging import logger

logger.warning("User input: " + user_input)
"""
        self.assertCodemod(before, after)

    def test_no_tag_untouched(self) -> None:
        """Ensure normal prints without tags are ignored."""
        before = """
print("Just a normal output")
print(result)
"""
        after = """
print("Just a normal output")
print(result)
"""
        self.assertCodemod(before, after)

    def test_debug_guard_transformation(self) -> None:
        """Test debug guard with single print is UNWRAPPED (if removed)."""
        before = """
import os
if os.environ.get("THEAUDITOR_DEBUG"):
    print("Debug message")
"""
        # CASE A: Single print - the if wrapper is removed entirely!
        # The if is redundant because Loguru respects log levels anyway.
        after = """
import os
from theauditor.utils.logging import logger

logger.debug("Debug message")
"""
        self.assertCodemod(before, after)

    def test_debug_guard_with_other_statements(self) -> None:
        """Test debug guard with non-print statements keeps if wrapper (CASE B)."""
        before = """
import os
if os.environ.get("THEAUDITOR_DEBUG"):
    print("Complex object dump:", obj)
    x = 1
"""
        # CASE B: Mixed content - the if wrapper is KEPT (has other statements)
        # Multi-arg print gets format string injection
        after = """
import os
from theauditor.utils.logging import logger

if os.environ.get("THEAUDITOR_DEBUG"):
    logger.debug("{} {}", "Complex object dump:", obj)
    x = 1
"""
        self.assertCodemod(before, after)

    def test_debug_guard_single_quotes(self) -> None:
        """Ensure it catches single quotes in env var check - also unwraps."""
        before = """
import os
if os.environ.get('THEAUDITOR_DEBUG'):
    print(f"Debug {x}")
"""
        # CASE A: Single print with single quotes - still unwrapped
        after = """
import os
from theauditor.utils.logging import logger

logger.debug(f"Debug {x}")
"""
        self.assertCodemod(before, after)

    def test_multiple_tags_in_file(self) -> None:
        """Test file with multiple different tags."""
        before = """
print("[INFO] Starting")
print("[DEBUG] Detail info")
print("[ERROR] Something failed")
print("[WARNING] Be careful")
"""
        after = """
from theauditor.utils.logging import logger

logger.info("Starting")
logger.debug("Detail info")
logger.error("Something failed")
logger.warning("Be careful")
"""
        self.assertCodemod(before, after)

    def test_indexer_debug_tag(self) -> None:
        """Test the longer [INDEXER_DEBUG] tag (should match before [DEBUG])."""
        before = """
print("[INDEXER_DEBUG] Indexing file")
"""
        after = """
from theauditor.utils.logging import logger

logger.debug("Indexing file")
"""
        self.assertCodemod(before, after)

    def test_empty_print_tag_only(self) -> None:
        """Test print('[TAG]') with just tag converts to empty log."""
        before = """
print("[INFO]")
"""
        after = """
from theauditor.utils.logging import logger

logger.info("")
"""
        self.assertCodemod(before, after)

    def test_empty_print_tag_with_space(self) -> None:
        """Test print('[TAG] ') with tag and trailing space converts to empty log."""
        before = """
print("[DEBUG] ")
"""
        after = """
from theauditor.utils.logging import logger

logger.debug("")
"""
        self.assertCodemod(before, after)

    def test_multi_arg_format_string_four_args(self) -> None:
        """Test format string injection with 4 arguments."""
        before = """
print("[INFO] Loading item", item_id, "attempt", 5)
"""
        # Four args -> "{} {} {} {}"
        after = """
from theauditor.utils.logging import logger

logger.info("{} {} {} {}", "Loading item", item_id, "attempt", 5)
"""
        self.assertCodemod(before, after)

    def test_multi_arg_preserves_fstring(self) -> None:
        """Test format string injection works with f-strings."""
        before = """
print(f"[DEBUG] User {name}", extra_data, more_data)
"""
        # F-string + 2 more args = 3 args total -> "{} {} {}"
        after = """
from theauditor.utils.logging import logger

logger.debug("{} {} {}", f"User {name}", extra_data, more_data)
"""
        self.assertCodemod(before, after)

    # -------------------------------------------------------------------------
    # AUDIT FIX TESTS: sep, end, and stderr edge cases
    # -------------------------------------------------------------------------

    def test_sep_argument_custom_separator(self) -> None:
        """AUDIT FIX 3: sep argument should be used in format string."""
        before = """
print("[INFO] Item", "123", sep=", ")
"""
        # sep=", " should produce "{}, {}" not "{} {}"
        after = """
from theauditor.utils.logging import logger

logger.info("{}, {}", "Item", "123")
"""
        self.assertCodemod(before, after)

    def test_sep_argument_dash_separator(self) -> None:
        """AUDIT FIX 3: Dash separator test."""
        before = """
print("[DEBUG] A", "B", "C", sep="-")
"""
        after = """
from theauditor.utils.logging import logger

logger.debug("{}-{}-{}", "A", "B", "C")
"""
        self.assertCodemod(before, after)

    def test_end_argument_empty_skipped(self) -> None:
        """AUDIT FIX 1: end='' (progress bar) should NOT be transformed."""
        before = """
print("[INFO] Loading", end="")
"""
        # Should be untouched - loggers always add newlines
        after = """
print("[INFO] Loading", end="")
"""
        self.assertCodemod(before, after)

    def test_end_argument_carriage_return_skipped(self) -> None:
        """AUDIT FIX 1: end='\\r' (progress bar overwrite) should NOT be transformed."""
        before = """
print("[INFO] Progress: 50%", end="\\r")
"""
        # Should be untouched - loggers can't handle line overwrites
        after = """
print("[INFO] Progress: 50%", end="\\r")
"""
        self.assertCodemod(before, after)

    def test_end_argument_newline_allowed(self) -> None:
        """end='\\n' is the default and SHOULD be transformed."""
        before = """
print("[INFO] Normal message", end="\\n")
"""
        after = """
from theauditor.utils.logging import logger

logger.info("Normal message")
"""
        self.assertCodemod(before, after)

    def test_stderr_untagged_becomes_error(self) -> None:
        """AUDIT FIX 2: Untagged stderr prints should become logger.error."""
        before = """
import sys
print("Something failed", file=sys.stderr)
"""
        after = """
import sys
from theauditor.utils.logging import logger

logger.error("Something failed")
"""
        self.assertCodemod(before, after)

    def test_stderr_with_tag_uses_tag_level(self) -> None:
        """stderr with explicit tag should use the tag's level, not error."""
        before = """
import sys
print("[WARNING] Be careful", file=sys.stderr)
"""
        after = """
import sys
from theauditor.utils.logging import logger

logger.warning("Be careful")
"""
        self.assertCodemod(before, after)

    def test_combined_sep_and_stderr(self) -> None:
        """Test combination of sep and stderr (untagged)."""
        before = """
import sys
print("Error", "code", "123", sep=": ", file=sys.stderr)
"""
        after = """
import sys
from theauditor.utils.logging import logger

logger.error("{}: {}: {}", "Error", "code", "123")
"""
        self.assertCodemod(before, after)

    # -------------------------------------------------------------------------
    # BRACE HAZARD TESTS: Prevent Loguru runtime crashes
    # -------------------------------------------------------------------------

    def test_brace_hazard_single_arg_regex(self) -> None:
        """BRACE HAZARD: Single arg with {} must get format injection."""
        before = """
print("[INFO] Regex pattern: {0-9}")
"""
        # Without fix: logger.info("Regex pattern: {0-9}") -> ValueError at runtime!
        # With fix: Forces format injection to escape the braces
        after = """
from theauditor.utils.logging import logger

logger.info("{}", "Regex pattern: {0-9}")
"""
        self.assertCodemod(before, after)

    def test_brace_hazard_single_arg_json(self) -> None:
        """BRACE HAZARD: JSON-like string with braces."""
        before = """
print("[DEBUG] Example: {key: value}")
"""
        after = """
from theauditor.utils.logging import logger

logger.debug("{}", "Example: {key: value}")
"""
        self.assertCodemod(before, after)

    def test_brace_hazard_fstring_with_literal_braces(self) -> None:
        """BRACE HAZARD: f-string containing literal braces (doubled)."""
        before = """
print(f"[INFO] Template: {{name}}")
"""
        # f-string with {{ }} - the doubled braces become literal { } in output
        # These need protection too
        after = """
from theauditor.utils.logging import logger

logger.info("{}", f"Template: {{name}}")
"""
        self.assertCodemod(before, after)

    def test_brace_hazard_no_braces_unchanged(self) -> None:
        """Normal string without braces should NOT get format injection."""
        before = """
print("[INFO] Normal message without braces")
"""
        # Single arg without braces -> NO format injection needed
        after = """
from theauditor.utils.logging import logger

logger.info("Normal message without braces")
"""
        self.assertCodemod(before, after)

    def test_dynamic_sep_skipped(self) -> None:
        """Dynamic sep (variable) should be SKIPPED - cannot build static format."""
        before = """
my_sep = ", "
print("[INFO] A", "B", sep=my_sep)
"""
        # Should be untouched - we can't know the separator at transform time
        after = """
my_sep = ", "
print("[INFO] A", "B", sep=my_sep)
"""
        self.assertCodemod(before, after)

    def test_debug_guard_preserves_outer_comments(self) -> None:
        """Comments above debug guard should be preserved when unwrapping."""
        before = """
import os
# This is an important debug check
# TODO: Review this later
if os.environ.get("THEAUDITOR_DEBUG"):
    print("Debug info")
"""
        # Comments should be preserved on the new logger line
        after = """
import os
from theauditor.utils.logging import logger

# This is an important debug check
# TODO: Review this later
logger.debug("Debug info")
"""
        self.assertCodemod(before, after)

    def test_debug_guard_preserves_inner_comments(self) -> None:
        """Comments INSIDE debug guard (above print) should also be preserved."""
        before = """
import os
# Outer comment
if os.environ.get("THEAUDITOR_DEBUG"):
    # Inner comment - this was being lost!
    print("Debug info")
"""
        # BOTH outer and inner comments should be preserved
        after = """
import os
from theauditor.utils.logging import logger

# Outer comment
# Inner comment - this was being lost!
logger.debug("Debug info")
"""
        self.assertCodemod(before, after)

    # -------------------------------------------------------------------------
    # TRACEBACK TRANSFORMATION TESTS
    # -------------------------------------------------------------------------

    def test_traceback_print_exc_basic(self) -> None:
        """traceback.print_exc() should become logger.exception("")."""
        before = """
import traceback
try:
    risky()
except Exception:
    traceback.print_exc()
"""
        after = """
from theauditor.utils.logging import logger

try:
    risky()
except Exception:
    logger.exception("")
"""
        self.assertCodemod(before, after)

    def test_traceback_print_exc_with_print(self) -> None:
        """Combine traceback and print transformations."""
        before = """
import traceback
try:
    risky()
except Exception:
    print("[ERROR] Something failed")
    traceback.print_exc()
"""
        after = """
from theauditor.utils.logging import logger

try:
    risky()
except Exception:
    logger.error("Something failed")
    logger.exception("")
"""
        self.assertCodemod(before, after)

    # -------------------------------------------------------------------------
    # DATA LOSS PREVENTION TESTS
    # -------------------------------------------------------------------------

    def test_custom_file_handle_skipped(self) -> None:
        """print() with custom file handle (not stderr) must NOT be transformed."""
        before = """
audit_log = open("audit.log", "w")
print("[INFO] Transaction record", file=audit_log)
"""
        # Must be untouched - migrating would lose the file destination
        after = """
audit_log = open("audit.log", "w")
print("[INFO] Transaction record", file=audit_log)
"""
        self.assertCodemod(before, after)

    def test_eager_eval_prevention(self) -> None:
        """Debug guard with function call must KEEP the if wrapper."""
        before = """
import os
if os.environ.get("THEAUDITOR_DEBUG"):
    print(calculate_expensive_metrics())
"""
        # Must keep wrapper - unwrapping would cause eager evaluation
        after = """
import os
from theauditor.utils.logging import logger

if os.environ.get("THEAUDITOR_DEBUG"):
    logger.debug(calculate_expensive_metrics())
"""
        self.assertCodemod(before, after)

    def test_simple_args_still_unwrap(self) -> None:
        """Debug guard with simple args (literals/names) should still unwrap."""
        before = """
import os
if os.environ.get("THEAUDITOR_DEBUG"):
    print("Simple message", some_var)
"""
        # Simple args - safe to unwrap
        after = """
import os
from theauditor.utils.logging import logger

logger.debug("{} {}", "Simple message", some_var)
"""
        self.assertCodemod(before, after)


if __name__ == "__main__":
    unittest.main()
