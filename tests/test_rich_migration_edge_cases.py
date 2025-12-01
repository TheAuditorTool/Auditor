"""
Test suite for Rich Markup Injection prevention in rich_migration.py.

These tests verify that brackets in log messages are properly escaped
so Rich doesn't interpret them as style tags.

The codemod uses r"\\\\[" which produces TWO backslashes in source code.
When Python parses that source, \\\\[ becomes \\[ at runtime.
Rich then sees \\[ and treats it as escaped text, not a tag.

IMPORTANT: In these tests, we use \\\\[ to represent source code with \\[
because Python's string escaping consumes one layer:
    Test string \\\\[ -> Expected source \\[
"""

import unittest

from libcst.codemod import CodemodTest

from scripts.rich_migration import ClickEchoToConsoleCodemod


class TestRichMigrationEdgeCases(CodemodTest):
    TRANSFORM = ClickEchoToConsoleCodemod

    def test_escape_brackets_in_simple_string(self) -> None:
        """
        Verify that brackets in log messages (like lists) are escaped so Rich
        doesn't interpret them as style tags.
        """
        before = """
click.echo("Processing items: [1, 2, 3]")
"""
        # \\\\[ in test string = \\[ in expected source code
        after = """
from theauditor.pipeline.ui import console

console.print("Processing items: \\\\[1, 2, 3]")
"""
        self.assertCodemod(before, after)

    def test_escape_brackets_with_prefix(self) -> None:
        """
        Verify that when a valid prefix is transformed, the REST of the content
        is still escaped.
        """
        before = """
click.echo("[OK] Saved file [data.csv] to disk")
"""
        # [OK] becomes [success]...[/success]
        # [data.csv] becomes \\[data.csv] (escaped text)
        after = """
from theauditor.pipeline.ui import console

console.print("[success]Saved file \\\\[data.csv] to disk[/success]")
"""
        self.assertCodemod(before, after)

    def test_escape_f_string_literals(self) -> None:
        """
        Verify that brackets inside f-string LITERAL parts are escaped.
        F-strings with variables also get highlight=False for safety.
        """
        before = """
click.echo(f"Found [matches]: {count}")
"""
        # Brackets escaped + highlight=False for f-string with variable
        after = """
from theauditor.pipeline.ui import console

console.print(f"Found \\\\[matches]: {count}", highlight=False)
"""
        self.assertCodemod(before, after)

    def test_f_string_with_prefix_and_nested_brackets(self) -> None:
        """
        Complex case: F-string with semantic prefix AND bracketed data.
        """
        before = """
click.echo(f"[ERROR] Could not parse [json] in {filename}")
"""
        # [ERROR] -> [error] tag (unescaped, it's our tag)
        # [json] -> \\[json] text (escaped)
        after = """
from theauditor.pipeline.ui import console

console.print(f"[error]Could not parse \\\\[json] in {filename}[/error]")
"""
        self.assertCodemod(before, after)

    def test_err_flag_adds_stderr(self) -> None:
        """
        CRITICAL FIX #1: err=True must route to stderr, not just color red.
        Verifies stderr=True is added to console.print().
        """
        before = """
click.echo("System crash: [segfault]", err=True)
"""
        # err=True -> [error] wrapper AND stderr=True for proper routing
        after = """
from theauditor.pipeline.ui import console

console.print("[error]System crash: \\\\[segfault][/error]", stderr=True)
"""
        self.assertCodemod(before, after)

    def test_multiple_brackets_in_string(self) -> None:
        """
        Verify multiple bracket pairs are all escaped.
        """
        before = """
click.echo("Arrays: [1, 2] and [3, 4]")
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Arrays: \\\\[1, 2] and \\\\[3, 4]")
"""
        self.assertCodemod(before, after)

    def test_separator_becomes_rule(self) -> None:
        """
        Verify separator patterns become console.rule().
        """
        before = """
click.echo("=" * 60)
"""
        after = """
from theauditor.pipeline.ui import console

console.rule()
"""
        self.assertCodemod(before, after)

    def test_click_style_with_semantic_prefix(self) -> None:
        """
        When click.style wraps text with a semantic prefix, the prefix tag
        takes precedence. No style= argument should be added.
        """
        before = """
click.echo(click.style("[ERROR] Failed [task]", fg="red"))
"""
        # [ERROR] becomes tag, fg="red" is dropped (tag provides styling)
        after = """
from theauditor.pipeline.ui import console

console.print("[error]Failed \\\\[task][/error]")
"""
        self.assertCodemod(before, after)

    def test_click_style_preserves_color(self) -> None:
        """
        CRITICAL FIX #2: click.style fg= color must be preserved when no
        semantic prefix is present.
        """
        before = """
click.echo(click.style("Completed successfully", fg="green"))
"""
        # No semantic prefix, so fg="green" becomes style="green"
        after = """
from theauditor.pipeline.ui import console

console.print("Completed successfully", style="green")
"""
        self.assertCodemod(before, after)

    def test_click_style_preserves_bold(self) -> None:
        """
        Verify bold=True from click.style is preserved.
        """
        before = """
click.echo(click.style("Important message", bold=True))
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Important message", style="bold")
"""
        self.assertCodemod(before, after)

    def test_click_style_bold_and_color(self) -> None:
        """
        Verify bold + color combination is preserved.
        Style order: color first, then attributes (both valid for Rich).
        """
        before = """
click.echo(click.style("Warning text", fg="yellow", bold=True))
"""
        # Rich accepts "yellow bold" or "bold yellow" - our code produces color first
        after = """
from theauditor.pipeline.ui import console

console.print("Warning text", style="yellow bold")
"""
        self.assertCodemod(before, after)

    def test_click_style_with_newline_prefix(self) -> None:
        """
        Edge case: click.style with leading newline before semantic prefix.
        The \\n should be stripped when checking for prefix.
        """
        before = """
click.echo(click.style("\\n[SUCCESS] Done", fg="green"))
"""
        # [SUCCESS] is found after stripping \\n, so no style= added
        after = """
from theauditor.pipeline.ui import console

console.print("\\n[success]Done[/success]")
"""
        self.assertCodemod(before, after)

    def test_no_change_without_click_echo(self) -> None:
        """
        Verify files without click.echo are unchanged.
        """
        before = """
print("Hello [world]")
"""
        after = """
print("Hello [world]")
"""
        self.assertCodemod(before, after)

    def test_regex_pattern_escaped(self) -> None:
        """
        Verify regex-like patterns with brackets are escaped.
        """
        before = """
click.echo("Pattern: [a-zA-Z0-9]+")
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Pattern: \\\\[a-zA-Z0-9]+")
"""
        self.assertCodemod(before, after)


    # =========================================================================
    # NEW TESTS: Critical fixes for nl=False, file=, variables, more styles
    # =========================================================================

    def test_nl_false_becomes_end_empty(self) -> None:
        """
        CRITICAL FIX #3: nl=False must become end="" not nl=False.
        click.echo uses nl=False, console.print uses end="".
        """
        before = """
click.echo("Progress: ", nl=False)
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Progress: ", end="")
"""
        self.assertCodemod(before, after)

    def test_file_stderr_becomes_stderr_true(self) -> None:
        """
        CRITICAL FIX #4: file=sys.stderr must map to stderr=True.
        """
        before = """
click.echo("Error message", file=sys.stderr)
"""
        # file=sys.stderr -> stderr=True AND wraps in [error] tags
        after = """
from theauditor.pipeline.ui import console

console.print("[error]Error message[/error]", stderr=True)
"""
        self.assertCodemod(before, after)

    def test_file_complex_aborts_transformation(self) -> None:
        """
        CRITICAL FIX #4: file=open(...) should NOT be transformed.
        console.print can't write to arbitrary file handles.
        """
        before = """
click.echo("Log entry", file=log_file)
"""
        # Should remain unchanged - can't safely migrate
        after = """
click.echo("Log entry", file=log_file)
"""
        self.assertCodemod(before, after)

    def test_pure_variable_gets_markup_false(self) -> None:
        """
        CRITICAL FIX #5: Pure variables get markup=False for safety.
        Variables may contain brackets that Rich interprets as tags.
        """
        before = """
click.echo(user_message)
"""
        after = """
from theauditor.pipeline.ui import console

console.print(user_message, markup=False)
"""
        self.assertCodemod(before, after)

    def test_click_style_dim_underline(self) -> None:
        """
        Verify dim and underline attributes are preserved.
        """
        before = """
click.echo(click.style("Subtle text", dim=True, underline=True))
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Subtle text", style="dim underline")
"""
        self.assertCodemod(before, after)

    def test_click_style_italic(self) -> None:
        """
        Verify italic attribute is preserved.
        """
        before = """
click.echo(click.style("Emphasis", fg="cyan", italic=True))
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Emphasis", style="cyan italic")
"""
        self.assertCodemod(before, after)

    def test_color_arg_is_dropped(self) -> None:
        """
        The color= argument should be dropped (Rich handles via Console config).
        """
        before = """
click.echo("Forced color", color=True)
"""
        # color= is dropped to prevent TypeError
        after = """
from theauditor.pipeline.ui import console

console.print("Forced color")
"""
        self.assertCodemod(before, after)


    # =========================================================================
    # NEW TESTS: click.secho() support
    # =========================================================================

    def test_secho_basic(self) -> None:
        """
        CRITICAL FIX #7: click.secho() must be transformed like click.echo().
        secho is the most common way to print colored text in Click.
        """
        before = """
click.secho("Hello world")
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Hello world")
"""
        self.assertCodemod(before, after)

    def test_secho_with_fg_color(self) -> None:
        """
        click.secho with fg= should transform to console.print with style=.
        """
        before = """
click.secho("Error message", fg="red")
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Error message", style="red")
"""
        self.assertCodemod(before, after)

    def test_secho_with_err_and_fg(self) -> None:
        """
        click.secho with err=True AND fg= should route to stderr AND apply style.
        Since err=True adds [error] wrapper, the fg= style is dropped.
        """
        before = """
click.secho("Fatal error", err=True, fg="red")
"""
        # err=True adds [error] wrapper AND stderr=True
        # fg="red" is redundant when [error] is applied
        after = """
from theauditor.pipeline.ui import console

console.print("[error]Fatal error[/error]", stderr=True)
"""
        self.assertCodemod(before, after)

    def test_secho_bold_and_color(self) -> None:
        """
        click.secho with bold=True and fg= should combine styles.
        """
        before = """
click.secho("Important!", fg="yellow", bold=True)
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Important!", style="yellow bold")
"""
        self.assertCodemod(before, after)

    def test_secho_with_bg_color(self) -> None:
        """
        click.secho with bg= should transform to Rich's 'on <color>' syntax.
        """
        before = """
click.secho("Highlighted", bg="white", fg="black")
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Highlighted", style="black on white")
"""
        self.assertCodemod(before, after)

    def test_secho_with_semantic_prefix(self) -> None:
        """
        click.secho with semantic prefix should use tag instead of style=.
        """
        before = """
click.secho("[ERROR] Something broke", fg="red")
"""
        # [ERROR] becomes [error] tag, fg="red" is dropped (tag provides styling)
        after = """
from theauditor.pipeline.ui import console

console.print("[error]Something broke[/error]")
"""
        self.assertCodemod(before, after)

    def test_secho_nl_false(self) -> None:
        """
        click.secho with nl=False should transform to end="".
        """
        before = """
click.secho("Loading...", nl=False, fg="cyan")
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Loading...", style="cyan", end="")
"""
        self.assertCodemod(before, after)

    def test_secho_multiple_style_attrs(self) -> None:
        """
        click.secho with multiple style attrs should combine them.
        """
        before = """
click.secho("Warning text", fg="yellow", bold=True, underline=True)
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Warning text", style="yellow bold underline")
"""
        self.assertCodemod(before, after)

    # =========================================================================
    # NEW TESTS: F-string variable safety (highlight=False)
    # =========================================================================

    def test_fstring_with_variable_gets_highlight_false(self) -> None:
        """
        CRITICAL FIX #6: F-strings with variables need highlight=False.
        Variables may contain brackets that Rich interprets as markup.
        """
        before = """
click.echo(f"User: {username}")
"""
        # F-string with {username} gets highlight=False for safety
        after = """
from theauditor.pipeline.ui import console

console.print(f"User: {username}", highlight=False)
"""
        self.assertCodemod(before, after)

    def test_fstring_with_prefix_no_highlight_false(self) -> None:
        """
        F-strings with semantic prefix should NOT get highlight=False.
        The prefix provides our own markup that we control.
        """
        before = """
click.echo(f"[OK] Processed {count} items")
"""
        # Has semantic prefix - we wrap in [success] tags
        # No highlight=False because we control the markup
        after = """
from theauditor.pipeline.ui import console

console.print(f"[success]Processed {count} items[/success]")
"""
        self.assertCodemod(before, after)

    def test_fstring_literal_only_no_highlight_false(self) -> None:
        """
        F-strings with ONLY literal text (no variables) don't need highlight=False.
        """
        before = """
click.echo(f"Static text only")
"""
        # No variables, no highlight=False needed
        after = """
from theauditor.pipeline.ui import console

console.print(f"Static text only")
"""
        self.assertCodemod(before, after)

    def test_concatenated_fstring_with_variable(self) -> None:
        """
        Concatenated strings containing f-strings with variables get highlight=False.
        """
        before = """
click.echo("Prefix: " f"{value}")
"""
        after = """
from theauditor.pipeline.ui import console

console.print("Prefix: " f"{value}", highlight=False)
"""
        self.assertCodemod(before, after)


if __name__ == "__main__":
    unittest.main()
