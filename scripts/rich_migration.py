"""
LibCST Codemod: Migrate click.echo() to console.print() with Rich tokens.

This script transforms TheAuditor command files from click.echo to the new
Rich-based console.print system defined in theauditor.pipeline.ui.

Usage:
    # Dry run (preview changes)
    python -m libcst.tool codemod scripts.rich_migration.ClickEchoToConsoleCodemod \
        --no-format theauditor/commands/

    # Apply changes
    python -m libcst.tool codemod scripts.rich_migration.ClickEchoToConsoleCodemod \
        theauditor/commands/

    # Single file test
    python scripts/rich_migration.py theauditor/commands/lint.py --dry-run

Patterns transformed:
    click.echo("text")              -> console.print("text")
    click.echo("text", err=True)    -> console.print("[error]text[/error]")
    click.echo(f"[OK] {msg}")       -> console.print(f"[success]{msg}[/success]")
    click.echo(f"[WARN] {msg}")     -> console.print(f"[warning]{msg}[/warning]")
    click.echo(f"[ERROR] {msg}")    -> console.print(f"[error]{msg}[/error]")
    click.echo("=" * 60)            -> console.rule()
    click.echo(f"Path: {path}")     -> console.print(f"Path: [path]{path}[/path]")

Author: TheAuditor Team
Version: 1.0.0
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Sequence, Union

import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor


# Emoji patterns to remove (Windows CP1252 crashes on these)
EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001F9FF]"  # Misc symbols, emoticons, etc.
    r"|[\u2600-\u26FF]"  # Misc symbols
    r"|[\u2700-\u27BF]"  # Dingbats
    r"|[\u2B50-\u2B55]"  # Stars
    r"|[\u23E9-\u23F3]"  # Media symbols
    r"|[\u23F8-\u23FA]"  # More media
    r"|[\u25AA-\u25AB]"  # Squares
    r"|[\u25B6\u25C0]"  # Triangles
    r"|[\u25FB-\u25FE]"  # More squares
    r"|[\u2614-\u2615]"  # Umbrella, coffee
    r"|[\u2648-\u2653]"  # Zodiac
    r"|[\u267F]"  # Wheelchair
    r"|[\u2693]"  # Anchor
    r"|[\u26A1]"  # Lightning
    r"|[\u26AA-\u26AB]"  # Circles
    r"|[\u26BD-\u26BE]"  # Sports
    r"|[\u26C4-\u26C5]"  # Weather
    r"|[\u26CE]"  # Ophiuchus
    r"|[\u26D4]"  # No entry
    r"|[\u26EA]"  # Church
    r"|[\u26F2-\u26F3]"  # Fountain, golf
    r"|[\u26F5]"  # Sailboat
    r"|[\u26FA]"  # Tent
    r"|[\u26FD]"  # Fuel pump
    r"|[\u2702]"  # Scissors
    r"|[\u2705]"  # Check mark
    r"|[\u2708-\u270D]"  # Airplane, etc.
    r"|[\u270F]"  # Pencil
    r"|[\u2712]"  # Black nib
    r"|[\u2714]"  # Check mark
    r"|[\u2716]"  # X mark
    r"|[\u271D]"  # Cross
    r"|[\u2721]"  # Star of David
    r"|[\u2728]"  # Sparkles
    r"|[\u2733-\u2734]"  # Eight spoked
    r"|[\u2744]"  # Snowflake
    r"|[\u2747]"  # Sparkle
    r"|[\u274C]"  # Cross mark
    r"|[\u274E]"  # Cross mark
    r"|[\u2753-\u2755]"  # Question marks
    r"|[\u2757]"  # Exclamation
    r"|[\u2763-\u2764]"  # Hearts
    r"|[\u2795-\u2797]"  # Plus, minus, divide
    r"|[\u27A1]"  # Right arrow
    r"|[\u27B0]"  # Curly loop
    r"|[\u27BF]"  # Double curly
    r"|[\u2934-\u2935]"  # Arrows
    r"|[\u2B05-\u2B07]"  # Arrows
    r"|[\u2B1B-\u2B1C]"  # Squares
    r"|[\u3030]"  # Wavy dash
    r"|[\u303D]"  # Part alternation
    r"|[\u3297]"  # Circled ideograph
    r"|[\u3299]"  # Circled ideograph
    r"|[\U0001F004]"  # Mahjong
    r"|[\U0001F0CF]"  # Playing card
    r"|[\U0001F170-\U0001F171]"  # A, B buttons
    r"|[\U0001F17E-\U0001F17F]"  # O, P buttons
    r"|[\U0001F18E]"  # AB button
    r"|[\U0001F191-\U0001F19A]"  # CL, etc.
    r"|[\U0001F1E0-\U0001F1FF]"  # Flags
    r"|[\U0001F201-\U0001F202]"  # Japanese
    r"|[\U0001F21A]"  # Japanese
    r"|[\U0001F22F]"  # Japanese
    r"|[\U0001F232-\U0001F23A]"  # Japanese
    r"|[\U0001F250-\U0001F251]"  # Japanese
    r"|[\U0001F300-\U0001F321]"  # Weather, etc.
    r"|[\U0001F324-\U0001F393]"  # Weather, sports
    r"|[\U0001F396-\U0001F397]"  # Medals
    r"|[\U0001F399-\U0001F39B]"  # Studio
    r"|[\U0001F39E-\U0001F3F0]"  # Entertainment
    r"|[\U0001F3F3-\U0001F3F5]"  # Flags
    r"|[\U0001F3F7-\U0001F4FD]"  # Objects
    r"|[\U0001F4FF-\U0001F53D]"  # Objects
    r"|[\U0001F549-\U0001F54E]"  # Religious
    r"|[\U0001F550-\U0001F567]"  # Clocks
    r"|[\U0001F56F-\U0001F570]"  # Candle, clock
    r"|[\U0001F573-\U0001F57A]"  # Hole, etc.
    r"|[\U0001F587]"  # Paperclips
    r"|[\U0001F58A-\U0001F58D]"  # Pens
    r"|[\U0001F590]"  # Hand
    r"|[\U0001F595-\U0001F596]"  # Hands
    r"|[\U0001F5A4-\U0001F5A5]"  # Heart, desktop
    r"|[\U0001F5A8]"  # Printer
    r"|[\U0001F5B1-\U0001F5B2]"  # Mouse, trackball
    r"|[\U0001F5BC]"  # Frame
    r"|[\U0001F5C2-\U0001F5C4]"  # Folders
    r"|[\U0001F5D1-\U0001F5D3]"  # Wastebasket, etc.
    r"|[\U0001F5DC-\U0001F5DE]"  # Clamp, etc.
    r"|[\U0001F5E1]"  # Dagger
    r"|[\U0001F5E3]"  # Speaking head
    r"|[\U0001F5E8]"  # Speech bubble
    r"|[\U0001F5EF]"  # Bubble
    r"|[\U0001F5F3]"  # Ballot box
    r"|[\U0001F5FA-\U0001F64F]"  # Maps, gestures
    r"|[\U0001F680-\U0001F6C5]"  # Transport
    r"|[\U0001F6CB-\U0001F6D2]"  # Furniture
    r"|[\U0001F6E0-\U0001F6E5]"  # Tools
    r"|[\U0001F6E9]"  # Airplane
    r"|[\U0001F6EB-\U0001F6EC]"  # Airplanes
    r"|[\U0001F6F0]"  # Satellite
    r"|[\U0001F6F3-\U0001F6F9]"  # Vehicles
    r"|[\U0001F910-\U0001F93A]"  # Faces, sports
    r"|[\U0001F93C-\U0001F93E]"  # Sports
    r"|[\U0001F940-\U0001F945]"  # Plants
    r"|[\U0001F947-\U0001F94C]"  # Medals
    r"|[\U0001F950-\U0001F96B]"  # Food
    r"|[\U0001F980-\U0001F997]"  # Animals
    r"|[\U0001F9C0]"  # Cheese
    r"|[\U0001F9D0-\U0001F9E6]"  # People
)

# Prefix patterns to transform
PREFIX_PATTERNS = {
    "[OK]": "success",
    "[PASS]": "success",
    "[SUCCESS]": "success",
    "[WARN]": "warning",
    "[WARNING]": "warning",
    "[ERROR]": "error",
    "[FAILED]": "error",
    "[FAIL]": "error",
    "[INFO]": "info",
    "[CRITICAL]": "critical",
    "[HIGH]": "high",
    "[MEDIUM]": "medium",
    "[LOW]": "low",
}

# Map Click colors to Rich style names
# Rich supports all these colors natively
CLICK_TO_RICH_MAP = {
    "red": "red",
    "green": "green",
    "yellow": "yellow",
    "blue": "blue",
    "magenta": "magenta",
    "cyan": "cyan",
    "white": "white",
    "black": "black",
    "bright_red": "bright_red",
    "bright_green": "bright_green",
    "bright_yellow": "bright_yellow",
    "bright_blue": "bright_blue",
    "bright_magenta": "bright_magenta",
    "bright_cyan": "bright_cyan",
    "bright_white": "bright_white",
    "bright_black": "bright_black",
}


def remove_emojis(text: str) -> str:
    """Remove emoji and Unicode characters that crash Windows CP1252."""
    # Handle common Unicode symbols that look like status indicators
    text = text.replace("\u2714", "[OK]")  # Check mark -> [OK]
    text = text.replace("\u2716", "[X]")  # X mark -> [X]
    text = text.replace("\u2713", "[OK]")  # Check mark -> [OK]
    text = text.replace("\u2717", "[X]")  # Ballot X -> [X]
    text = text.replace("\u2705", "[OK]")  # White check mark -> [OK]
    text = text.replace("\u274C", "[X]")  # Cross mark -> [X]
    text = text.replace("\u274E", "[X]")  # Cross mark -> [X]
    text = text.replace("\u2757", "[!]")  # Exclamation -> [!]
    text = text.replace("\u26A0", "[WARN]")  # Warning sign -> [WARN]

    # Arrows (U+2190-U+21FF) - not in emoji range but crash CP1252
    text = text.replace("\u2192", "->")  # Rightwards arrow -> ->
    text = text.replace("\u2190", "<-")  # Leftwards arrow -> <-
    text = text.replace("\u2191", "^")  # Upwards arrow -> ^
    text = text.replace("\u2193", "v")  # Downwards arrow -> v
    text = text.replace("\u21D2", "=>")  # Rightwards double arrow -> =>
    text = text.replace("\u21D0", "<=")  # Leftwards double arrow -> <=

    # Remove decorative icons
    text = text.replace("\U0001F4CB", "")  # Clipboard -> remove
    text = text.replace("\U0001F4CA", "")  # Bar chart -> remove
    text = text.replace("\U0001F4C2", "")  # Folder -> remove
    text = text.replace("\U0001F50D", "")  # Magnifying glass -> remove
    text = text.replace("\U0001F6E0", "")  # Wrench -> remove
    text = text.replace("\U0001F389", "")  # Party popper -> remove

    # Remove any remaining emojis
    return EMOJI_PATTERN.sub("", text)


def escape_rich_markup(text: str) -> str:
    """
    Escape brackets to prevent Rich from interpreting them as style tags.

    Rich uses [tag]...[/tag] syntax. If your log messages contain brackets
    (like lists [1, 2, 3] or regex patterns [a-z]), Rich will try to parse
    them as tags, which can break output or cause crashes.

    Only escapes opening brackets '[' as that is sufficient for Rich.
    The tags we ADD (like [error]) are added AFTER escaping, so they remain valid.

    Output: Produces two backslashes in the string value, which when written
    to a .py source file becomes the escape sequence for a single backslash,
    avoiding Python 3.12+ SyntaxWarning about invalid escape sequences.
    """
    # We need the OUTPUT .py file to have: "text \\[bracket]"
    # Python interprets \\[ as single-backslash-bracket at runtime
    # Rich sees the backslash and treats [ as escaped text, not a tag
    #
    # r"\\[" produces: backslash-backslash-bracket (3 chars) in string value
    # When written to source, this becomes \\[ which is correct
    return text.replace("[", r"\\[")


def transform_string_content(value: str, is_error: bool = False) -> tuple[str, bool]:
    """
    Transform string content with Rich tokens.

    Returns (transformed_string, should_use_rule) where should_use_rule
    indicates the entire call should become console.rule().
    """
    # Detect separator patterns like "=" * 60 or "-" * 40
    # These are handled at the Call level, not here

    # Remove emojis first
    value = remove_emojis(value)

    # Handle prefix patterns - check with and without leading whitespace
    # e.g., "\n[SUCCESS] msg" should still be transformed
    # Note: LibCST preserves escape sequences literally, so \n is two chars: \ and n
    leading_ws = ""
    check_value = value

    # Extract leading whitespace/newlines (including escape sequences like \n, \t)
    i = 0
    while i < len(value):
        if value[i] in (" ", "\t", "\n", "\r"):
            leading_ws += value[i]
            i += 1
        elif value[i] == "\\" and i + 1 < len(value) and value[i + 1] in ("n", "t", "r"):
            # Escape sequence like \n, \t, \r
            leading_ws += value[i:i + 2]
            i += 2
        else:
            check_value = value[i:]
            break

    for prefix, token in PREFIX_PATTERNS.items():
        # Match at start of string (after any leading whitespace)
        if check_value.startswith(prefix + " "):
            rest = check_value[len(prefix) + 1:]
            # CRITICAL: Escape the content BEFORE wrapping in tags
            # This prevents Rich from interpreting [1, 2] as a style tag
            rest = escape_rich_markup(rest)
            return f"{leading_ws}[{token}]{rest}[/{token}]", False
        elif check_value.startswith(prefix):
            rest = check_value[len(prefix):]
            rest = escape_rich_markup(rest)
            return f"{leading_ws}[{token}]{rest}[/{token}]", False

    # If err=True was passed, wrap in error token
    if is_error and not value.startswith("[error]"):
        # Escape content before wrapping
        escaped_value = escape_rich_markup(value)
        return f"[error]{escaped_value}[/error]", False

    # Default case: escape any brackets in plain text
    # console.print() defaults to markup=True, so we must escape
    return escape_rich_markup(value), False


class ClickEchoToConsoleCodemod(VisitorBasedCodemodCommand):
    """
    Transform click.echo() and click.secho() calls to console.print() with Rich styling.

    This codemod handles:
    - Basic click.echo("text") -> console.print("text")
    - click.secho("text", fg="red") -> console.print("text", style="red")
    - Error output click.echo("text", err=True) -> console.print("[error]text[/error]")
    - Status prefixes [OK], [WARN], [ERROR] -> Rich tokens
    - Separator lines "=" * 60 -> console.rule()
    - Emoji removal for Windows CP1252 compatibility
    - Import management (add console, optionally remove click)

    Style Stacking Behavior:
        When encountering nested styles like `click.secho(click.style("Text", fg="red"), bold=True)`,
        this codemod flattens all styles into a single style= argument. Rich handles duplicate
        attributes gracefully (last wins for colors, attributes combine). This is safe but
        may differ slightly from Click's layered style application.

    Configuration:
        Override CONSOLE_MODULE and CONSOLE_NAME class attributes to customize the import path.
        Default: `from theauditor.pipeline.ui import console`

    Important:
        Ensure the target module (CONSOLE_MODULE) exists and exports a Console instance
        before running this codemod on a large codebase.

    Known Limitations:
        1. Variable Shadowing: If a local variable or function parameter is named 'console'
           in the target file, the added import will shadow it. This requires manual review.
           The compile() check will catch syntax errors but not shadowing issues.

        2. BinaryOperation: Explicit concatenation like "[ERROR] " + message detects the
           semantic prefix but cannot transform the string content. Rich will attempt to
           render [ERROR] as markup (unknown tags pass through safely).

        3. click.style as Variable: When click.style() result is stored in a variable and
           passed to click.echo(), the ANSI codes are preserved. Rich can render these,
           but markup=False may affect other formatting.
    """

    DESCRIPTION = "Migrate click.echo() to console.print() with Rich tokens"

    # Configurable import path for the console object
    # Override these in a subclass to use a different module
    CONSOLE_MODULE = "theauditor.pipeline.ui"
    CONSOLE_NAME = "console"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.click_echo_count = 0
        self.transformations = 0
        self.skipped_file_redirects = 0
        self.binary_concat_warnings = 0

    def visit_Module(self, node: cst.Module) -> bool:
        """Reset counters for each module."""
        self.click_echo_count = 0
        self.transformations = 0
        self.skipped_file_redirects = 0
        self.binary_concat_warnings = 0
        return True

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add console import and clean up click import if no longer used."""
        if self.transformations > 0:
            # Add the console import (uses configurable class constants)
            AddImportsVisitor.add_needed_import(
                self.context,
                self.CONSOLE_MODULE,
                self.CONSOLE_NAME
            )
            # Remove click import if it's no longer used after our transformations
            # RemoveImportsVisitor automatically checks for remaining usages
            RemoveImportsVisitor.remove_unused_import(
                self.context,
                "click"
            )
        return updated_node

    def _strip_leading_whitespace(self, text: str) -> str:
        """
        Strip leading whitespace including escape sequences like \\n, \\t.

        In a string literal, \\n is stored as two characters (backslash + n).
        Regular lstrip() won't strip these, so we handle them explicitly.
        """
        i = 0
        while i < len(text):
            if text[i] in (" ", "\t", "\n", "\r"):
                i += 1
            elif text[i] == "\\" and i + 1 < len(text) and text[i + 1] in ("n", "t", "r"):
                # Escape sequence like \n, \t, \r (two chars in source)
                i += 2
            else:
                break
        return text[i:]

    def _is_separator_pattern(self, node: cst.BaseExpression) -> bool:
        """Check if expression is a separator like '=' * 60 or '-' * 40."""
        if not m.matches(node, m.BinaryOperation(operator=m.Multiply())):
            return False

        binop = node
        # Check for "char" * number or number * "char"
        left_is_str = m.matches(binop.left, m.SimpleString())
        right_is_int = m.matches(binop.right, m.Integer())
        left_is_int = m.matches(binop.left, m.Integer())
        right_is_str = m.matches(binop.right, m.SimpleString())

        if left_is_str and right_is_int:
            str_val = binop.left.value.strip("'\"")
            return str_val in ("=", "-", "*", "_", "#")
        elif left_is_int and right_is_str:
            str_val = binop.right.value.strip("'\"")
            return str_val in ("=", "-", "*", "_", "#")

        return False

    def _transform_simple_string(
        self, node: cst.SimpleString, is_error: bool = False
    ) -> cst.SimpleString:
        """Transform a SimpleString with Rich tokens.

        Handles raw strings (r"...") by escaping existing backslashes before
        converting to a standard string. This preserves Windows paths and regex
        patterns that might contain backslashes.
        """
        value = node.value

        # Detect raw string prefix (r, R, combinations like rb, br, etc.)
        is_raw = False
        prefix = ""
        for i, char in enumerate(value):
            if char in ('"', "'"):
                prefix = value[:i]
                value_without_prefix = value[i:]
                is_raw = 'r' in prefix.lower()
                break
        else:
            # Fallback if no quote found (shouldn't happen)
            value_without_prefix = value

        # Determine quote style
        if value_without_prefix.startswith('"""') or value_without_prefix.startswith("'''"):
            quote_char = value_without_prefix[:3]
            inner = value_without_prefix[3:-3]
        else:
            quote_char = value_without_prefix[0]
            inner = value_without_prefix[1:-1]

        # EDGE CASE FIX: Raw strings with backslashes
        # In raw strings, backslashes are literal. When converting to standard string,
        # we must escape them to preserve the original meaning.
        # Example: r"C:\Users\[Name]" -> "C:\\Users\\[Name]" (before bracket escaping)
        if is_raw:
            # Escape existing backslashes (except those already part of escape sequences)
            # This is conservative: we double all backslashes
            inner = inner.replace("\\", "\\\\")
            # Remove the 'r' from prefix since we're converting to standard string
            prefix = prefix.replace('r', '').replace('R', '')

        transformed, _ = transform_string_content(inner, is_error)

        # Reconstruct without 'r' prefix (we've escaped backslashes)
        return node.with_changes(value=f"{prefix}{quote_char}{transformed}{quote_char}")

    def _transform_formatted_string(
        self, node: cst.FormattedString, is_error: bool = False
    ) -> cst.FormattedString:
        """Transform an f-string with Rich tokens and proper escaping."""
        new_parts = []
        active_token = None  # Track which token we opened (if any)
        first_text_processed = False

        for part in node.parts:
            if isinstance(part, cst.FormattedStringText):
                text = part.value

                # Remove emojis first
                text = remove_emojis(text)

                # Check for prefix on first text part only
                if not first_text_processed:
                    first_text_processed = True
                    prefix_found = False

                    for prefix, token in PREFIX_PATTERNS.items():
                        if text.startswith(prefix + " "):
                            rest = text[len(prefix) + 1:]
                            # CRITICAL: Escape the content, not the tag
                            rest = escape_rich_markup(rest)
                            text = f"[{token}]{rest}"
                            active_token = token
                            prefix_found = True
                            break
                        elif text.startswith(prefix):
                            rest = text[len(prefix):]
                            rest = escape_rich_markup(rest)
                            text = f"[{token}]{rest}"
                            active_token = token
                            prefix_found = True
                            break

                    if not prefix_found:
                        # No prefix found - just escape the text
                        text = escape_rich_markup(text)
                else:
                    # Not the first text part - just escape it
                    text = escape_rich_markup(text)

                new_parts.append(part.with_changes(value=text))
            else:
                # This is a variable/expression part {x}
                # We cannot escape runtime values at static analysis time
                # But we pass them through unchanged
                new_parts.append(part)

        # Close the token if we opened one
        if active_token:
            closing_tag = f"[/{active_token}]"
            if new_parts and isinstance(new_parts[-1], cst.FormattedStringText):
                last_part = new_parts[-1]
                new_parts[-1] = last_part.with_changes(value=last_part.value + closing_tag)
            else:
                new_parts.append(cst.FormattedStringText(value=closing_tag))

        # Handle err=True case if no prefix was found
        if is_error and not active_token:
            # Wrap in [error]...[/error]
            if new_parts and isinstance(new_parts[0], cst.FormattedStringText):
                new_parts[0] = new_parts[0].with_changes(
                    value="[error]" + new_parts[0].value
                )
            else:
                new_parts.insert(0, cst.FormattedStringText(value="[error]"))

            if new_parts and isinstance(new_parts[-1], cst.FormattedStringText):
                new_parts[-1] = new_parts[-1].with_changes(
                    value=new_parts[-1].value + "[/error]"
                )
            else:
                new_parts.append(cst.FormattedStringText(value="[/error]"))

        return node.with_changes(parts=new_parts)

    def _transform_concatenated_string(
        self, node: cst.ConcatenatedString, is_error: bool = False
    ) -> cst.ConcatenatedString:
        """Transform a concatenated string (left/right binary tree structure)."""
        # ConcatenatedString has .left and .right, not .parts
        # It's a binary tree: "a" "b" "c" becomes ConcatenatedString(left=ConcatenatedString(...), right=...)

        def transform_part(part):
            if isinstance(part, cst.SimpleString):
                return self._transform_simple_string(part, is_error)
            elif isinstance(part, cst.FormattedString):
                return self._transform_formatted_string(part, is_error)
            elif isinstance(part, cst.ConcatenatedString):
                return self._transform_concatenated_string(part, is_error)
            else:
                return part

        new_left = transform_part(node.left)
        new_right = transform_part(node.right)

        return node.with_changes(left=new_left, right=new_right)

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> Union[cst.Call, cst.BaseExpression]:
        """
        Transform click.echo() and click.secho() calls to console.print().

        Handles:
        - click.echo(...) and click.secho(...)
        - err=True -> stderr=True
        - nl=False -> end=""
        - file=sys.stderr -> stderr=True
        - file=<complex> -> ABORT (can't migrate safely)
        - color=... -> DROP (Rich handles via Console config)
        - click.style() unwrapping with style preservation
        - click.secho() style kwargs (fg, bg, bold, etc.) extraction
        - Variables -> markup=False for safety
        - F-strings with variables -> highlight=False for markup injection safety
        """

        # Match: click.echo(...) OR click.secho(...)
        is_echo = m.matches(
            updated_node.func,
            m.Attribute(value=m.Name("click"), attr=m.Name("echo"))
        )
        is_secho = m.matches(
            updated_node.func,
            m.Attribute(value=m.Name("click"), attr=m.Name("secho"))
        )

        if not (is_echo or is_secho):
            return updated_node

        # =====================================================================
        # PHASE 1: SCAN ARGUMENTS - Detect abort conditions and extract flags
        # =====================================================================
        is_error = False
        text_arg = None
        other_args = []
        end_arg = None  # Will hold end="" if nl=False is found
        # For click.secho(): capture style kwargs directly from the call
        secho_style_kwargs = {}  # Maps: 'fg' -> color, 'bold' -> True, etc.

        for arg in updated_node.args:
            if arg.keyword is not None:
                kw = arg.keyword.value

                # Handle err=True -> stderr=True
                if kw == "err":
                    if m.matches(arg.value, m.Name("True")):
                        is_error = True
                    # Drop the 'err' argument - we map it to 'stderr' later
                    continue

                # CRITICAL FIX #3: Handle nl=False -> end=""
                # click.echo uses nl=False, console.print uses end=""
                if kw == "nl":
                    if m.matches(arg.value, m.Name("False")):
                        end_arg = cst.Arg(
                            keyword=cst.Name("end"),
                            value=cst.SimpleString('""'),
                            equal=cst.AssignEqual(
                                whitespace_before=cst.SimpleWhitespace(""),
                                whitespace_after=cst.SimpleWhitespace("")
                            )
                        )
                    # If nl=True (default), just drop it - console.print adds newline by default
                    continue

                # CRITICAL FIX #4: Handle file=... redirection
                if kw == "file":
                    # file=sys.stderr -> stderr=True
                    if m.matches(arg.value, m.Attribute(attr=m.Name("stderr"))):
                        is_error = True
                        continue
                    # file=sys.stdout -> safe to ignore (default behavior)
                    if m.matches(arg.value, m.Attribute(attr=m.Name("stdout"))):
                        continue
                    # ABORT: file=open(...) or other streams
                    # console.print cannot print to arbitrary file handles
                    # without creating a new Console instance - skip this call
                    self.skipped_file_redirects += 1
                    print(
                        f"[WARN] Skipping click.echo with custom file= argument "
                        f"(console.print cannot write to arbitrary streams). "
                        f"Manual migration required.",
                        file=sys.stderr
                    )
                    return updated_node

                # Handle color=... (Click's way of forcing color on/off)
                # Rich handles this via Console(force_terminal=...), not per print
                # Drop it to prevent TypeError
                if kw == "color":
                    continue

                # For click.secho(): capture style kwargs (fg, bg, bold, etc.)
                # These are passed directly to secho, not inside click.style()
                if is_secho and kw in ("fg", "bg", "bold", "dim", "underline",
                                        "blink", "reverse", "italic", "strikethrough"):
                    if kw == "fg" and m.matches(arg.value, m.SimpleString()):
                        color = arg.value.value.strip("'\"")
                        if color in CLICK_TO_RICH_MAP:
                            secho_style_kwargs["fg"] = CLICK_TO_RICH_MAP[color]
                    elif kw == "bg" and m.matches(arg.value, m.SimpleString()):
                        # bg becomes "on <color>" in Rich
                        color = arg.value.value.strip("'\"")
                        if color in CLICK_TO_RICH_MAP:
                            secho_style_kwargs["bg"] = CLICK_TO_RICH_MAP[color]
                    elif kw in ("bold", "dim", "underline", "blink", "reverse",
                                "italic", "strikethrough"):
                        if m.matches(arg.value, m.Name("True")):
                            secho_style_kwargs[kw] = True
                    # Don't add style kwargs to other_args - they're handled separately
                    continue

                # Keep any other unknown kwargs (rare but safe)
                other_args.append(arg)
            else:
                # Positional argument - first one is the text
                if text_arg is None:
                    text_arg = arg
                else:
                    # click.echo only takes one positional arg
                    # If there's more, keep them to be safe
                    other_args.append(arg)

        self.click_echo_count += 1

        # =====================================================================
        # PHASE 2: UNWRAP click.style() AND EXTRACT STYLES
        # =====================================================================
        extracted_style_parts = []

        # For click.secho(): merge captured style kwargs
        if secho_style_kwargs:
            if "fg" in secho_style_kwargs:
                extracted_style_parts.append(secho_style_kwargs["fg"])
            if "bg" in secho_style_kwargs:
                # Rich uses "on <color>" for background
                extracted_style_parts.append(f"on {secho_style_kwargs['bg']}")
            for attr in ("bold", "dim", "underline", "blink", "reverse", "italic", "strikethrough"):
                if secho_style_kwargs.get(attr):
                    extracted_style_parts.append(attr)

        # For click.echo(click.style(...)): extract styles from nested call
        if text_arg is not None:
            if m.matches(
                text_arg.value,
                m.Call(func=m.Attribute(value=m.Name("click"), attr=m.Name("style")))
            ):
                style_call = text_arg.value

                # Extract ALL style attributes from click.style()
                for style_arg in style_call.args:
                    if style_arg.keyword is not None:
                        kw = style_arg.keyword.value
                        val = style_arg.value

                        # Handle fg="color"
                        if kw == "fg" and m.matches(val, m.SimpleString()):
                            color = val.value.strip("'\"")
                            if color in CLICK_TO_RICH_MAP:
                                extracted_style_parts.append(CLICK_TO_RICH_MAP[color])

                        # Handle bg="color" -> "on <color>"
                        elif kw == "bg" and m.matches(val, m.SimpleString()):
                            color = val.value.strip("'\"")
                            if color in CLICK_TO_RICH_MAP:
                                extracted_style_parts.append(f"on {CLICK_TO_RICH_MAP[color]}")

                        # Handle boolean style attributes: bold, dim, underline, etc.
                        # Rich supports all of these directly
                        elif kw in ("bold", "dim", "underline", "blink", "reverse", "italic", "strikethrough"):
                            if m.matches(val, m.Name("True")):
                                extracted_style_parts.append(kw)

                # Unwrap: extract the text content (first positional arg)
                if len(style_call.args) > 0:
                    text_arg = style_call.args[0]

        # =====================================================================
        # PHASE 3: CHECK FOR SEPARATOR PATTERNS
        # =====================================================================
        if text_arg is not None and self._is_separator_pattern(text_arg.value):
            self.transformations += 1
            return cst.Call(
                func=cst.Attribute(value=cst.Name("console"), attr=cst.Name("rule")),
                args=[]
            )

        # =====================================================================
        # PHASE 4: DETECT SEMANTIC PREFIXES AND TEXT TYPE
        # =====================================================================
        has_semantic_prefix = False
        is_pure_variable = False  # True if argument is just a variable/expression
        has_fstring_variables = False  # True if f-string contains {var} expressions
        is_binary_concat = False  # True if using + for string concatenation

        if text_arg is not None:
            text_value = text_arg.value

            if isinstance(text_value, cst.SimpleString):
                raw_text = text_value.value
                # Handle raw strings (r"...") and unicode strings (u"...")
                raw_text = raw_text.lstrip("rRuUbBfF")
                # Handle triple quotes
                if raw_text.startswith('"""') or raw_text.startswith("'''"):
                    raw_text = raw_text[3:-3]
                else:
                    raw_text = raw_text[1:-1]
                # Strip leading whitespace/escape sequences
                raw_text = self._strip_leading_whitespace(raw_text)
                for prefix in PREFIX_PATTERNS:
                    if raw_text.startswith(prefix):
                        has_semantic_prefix = True
                        break

            elif isinstance(text_value, cst.FormattedString):
                # Check first part of f-string for prefix
                if text_value.parts and isinstance(text_value.parts[0], cst.FormattedStringText):
                    raw_text = self._strip_leading_whitespace(text_value.parts[0].value)
                    for prefix in PREFIX_PATTERNS:
                        if raw_text.startswith(prefix):
                            has_semantic_prefix = True
                            break

                # CRITICAL FIX #6: Detect f-strings with variable expressions
                # f"User: {username}" has FormattedStringExpression parts
                # These are risky because username could be "[bold]Hacker[/bold]"
                # and Rich would interpret it as markup
                for part in text_value.parts:
                    if isinstance(part, cst.FormattedStringExpression):
                        has_fstring_variables = True
                        break

            elif isinstance(text_value, cst.ConcatenatedString):
                # Check left-most string for prefix
                pass  # Complex to extract, skip prefix detection
                # Check for f-string variables in concatenated strings
                def check_concat_for_fstring_vars(node):
                    if isinstance(node, cst.FormattedString):
                        for part in node.parts:
                            if isinstance(part, cst.FormattedStringExpression):
                                return True
                    elif isinstance(node, cst.ConcatenatedString):
                        return check_concat_for_fstring_vars(node.left) or check_concat_for_fstring_vars(node.right)
                    return False
                has_fstring_variables = check_concat_for_fstring_vars(text_value)

            elif isinstance(text_value, cst.BinaryOperation):
                # EDGE CASE: Explicit string concatenation with +
                # Example: click.echo("[ERROR] " + message)
                # Check if the left side is a string literal with semantic prefix
                # If so, we don't want to add markup=False (would disable our prefix styling)
                # Note: We can't transform the BinaryOperation content, but Rich will
                # attempt to render [ERROR] as markup. Unknown tags are passed through.
                is_binary_concat = True  # Flag for special handling
                left = text_value.left
                found_prefix = False
                if isinstance(left, cst.SimpleString):
                    raw_text = left.value
                    raw_text = raw_text.lstrip("rRuUbBfF")
                    if raw_text.startswith('"""') or raw_text.startswith("'''"):
                        raw_text = raw_text[3:-3]
                    else:
                        raw_text = raw_text[1:-1]
                    raw_text = self._strip_leading_whitespace(raw_text)
                    for prefix in PREFIX_PATTERNS:
                        if raw_text.startswith(prefix):
                            has_semantic_prefix = True
                            found_prefix = True
                            break
                # If no semantic prefix found in BinaryOperation, treat as unsafe
                # (the right side likely contains user data that could have brackets)
                if not found_prefix:
                    is_pure_variable = True
                else:
                    # WARNING: We found a semantic prefix but can't fully transform
                    # BinaryOperation. Rich will see "[ERROR]" as-is (not our styled tag).
                    # Unknown tags pass through safely, but won't be styled.
                    self.binary_concat_warnings += 1
                    print(
                        f"[WARN] BinaryOperation with semantic prefix detected. "
                        f"Cannot fully transform - Rich will render prefix as-is (unstyled). "
                        f"Consider refactoring to f-string for proper styling.",
                        file=sys.stderr
                    )

            else:
                # It's a variable or expression (e.g., click.echo(my_var))
                # We can't escape brackets at static analysis time
                is_pure_variable = True

        # =====================================================================
        # PHASE 5: TRANSFORM TEXT CONTENT
        # =====================================================================
        new_args = []
        if text_arg is not None:
            text_value = text_arg.value

            if isinstance(text_value, cst.SimpleString):
                new_text = self._transform_simple_string(text_value, is_error)
                new_args.append(cst.Arg(value=new_text))
            elif isinstance(text_value, cst.FormattedString):
                new_text = self._transform_formatted_string(text_value, is_error)
                new_args.append(cst.Arg(value=new_text))
            elif isinstance(text_value, cst.ConcatenatedString):
                new_text = self._transform_concatenated_string(text_value, is_error)
                new_args.append(cst.Arg(value=new_text))
            else:
                # Variable or expression - pass through unchanged
                new_args.append(text_arg)

        # Add back any other args
        new_args.extend(other_args)

        # =====================================================================
        # PHASE 6: BUILD EXTRA KWARGS
        # =====================================================================
        extra_kwargs = []

        # stderr=True (from err=True or file=sys.stderr)
        if is_error:
            extra_kwargs.append(
                cst.Arg(
                    keyword=cst.Name("stderr"),
                    value=cst.Name("True"),
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace("")
                    )
                )
            )

        # end="" (from nl=False)
        if end_arg:
            extra_kwargs.append(end_arg)

        # style="..." (from click.style attributes)
        # Only apply if no semantic prefix and not is_error (those provide styling)
        # FIX: Check for existing 'style' kwarg to prevent SyntaxError from duplicate kwargs
        existing_kwarg_names = {
            arg.keyword.value for arg in other_args
            if arg.keyword is not None
        }
        if extracted_style_parts and not has_semantic_prefix and not is_error:
            if "style" not in existing_kwarg_names:
                style_str = " ".join(extracted_style_parts)
                extra_kwargs.append(
                    cst.Arg(
                        keyword=cst.Name("style"),
                        value=cst.SimpleString(f'"{style_str}"'),
                        equal=cst.AssignEqual(
                            whitespace_before=cst.SimpleWhitespace(""),
                            whitespace_after=cst.SimpleWhitespace("")
                        )
                    )
                )
            # else: 'style' already exists in other_args, skip adding ours to prevent SyntaxError

        # CRITICAL FIX #5: markup=False for pure variables
        # Variables may contain brackets that Rich interprets as tags
        # Adding markup=False prevents MarkupError crashes
        if is_pure_variable and not is_error and not has_semantic_prefix:
            extra_kwargs.append(
                cst.Arg(
                    keyword=cst.Name("markup"),
                    value=cst.Name("False"),
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace("")
                    )
                )
            )

        # CRITICAL FIX #6: highlight=False for f-strings with variables
        # F-strings like f"User: {username}" have runtime values that may contain
        # brackets like "[bold]" which Rich would interpret as markup tags.
        # We cannot escape these at static analysis time.
        # Adding highlight=False prevents Rich from applying auto-highlighting
        # which could trigger MarkupError on malformed tags.
        # Note: We still allow our semantic prefixes to work via markup=True (default)
        if has_fstring_variables and not has_semantic_prefix:
            extra_kwargs.append(
                cst.Arg(
                    keyword=cst.Name("highlight"),
                    value=cst.Name("False"),
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace("")
                    )
                )
            )

        self.transformations += 1

        # Return console.print(...) call with all arguments
        return cst.Call(
            func=cst.Attribute(
                value=cst.Name("console"),
                attr=cst.Name("print")
            ),
            args=new_args + extra_kwargs
        )


class NameConflictVisitor(cst.CSTVisitor):
    """
    Scan for existing uses of a variable name to detect potential shadowing.

    Used to warn when 'console' is already defined in a file before we add
    the import, which could cause AttributeError at runtime.
    """

    def __init__(self, target_name: str = "console"):
        self.target_name = target_name
        self.found = False
        self.locations: list[str] = []  # Track where conflicts are found

    def visit_Name(self, node: cst.Name) -> bool:
        if node.value == self.target_name:
            self.found = True
        return True  # Continue visiting

    def visit_Param(self, node: cst.Param) -> bool:
        # Check function parameters: def foo(console): ...
        if node.name.value == self.target_name:
            self.found = True
            self.locations.append("function parameter")
        return True

    def visit_AssignTarget(self, node: cst.AssignTarget) -> bool:
        # Check assignments: console = ...
        if isinstance(node.target, cst.Name) and node.target.value == self.target_name:
            self.found = True
            self.locations.append("variable assignment")
        return True


def transform_file(file_path: str, dry_run: bool = False) -> tuple[str, int]:
    """
    Transform a single file.

    Returns (new_code, transformation_count).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        print(f"[ERROR] Failed to parse {file_path}: {e}", file=sys.stderr)
        return source, 0

    context = CodemodContext()
    transformer = ClickEchoToConsoleCodemod(context)

    try:
        modified = module.visit(transformer)
    except Exception as e:
        print(f"[ERROR] Failed to transform {file_path}: {e}", file=sys.stderr)
        return source, 0

    # Apply import changes registered in leave_Module
    if transformer.transformations > 0:
        # SAFETY: Check for variable shadowing before adding import
        conflict_check = NameConflictVisitor(transformer.CONSOLE_NAME)
        module.visit(conflict_check)
        if conflict_check.found:
            locations = ", ".join(set(conflict_check.locations)) if conflict_check.locations else "unknown"
            print(
                f"[WARN] Variable '{transformer.CONSOLE_NAME}' already exists in {file_path} ({locations}). "
                f"Import may cause shadowing - manual review recommended.",
                file=sys.stderr
            )

        # AddImportsVisitor.add_needed_import was called in leave_Module
        # Now apply the visitor to insert the actual import statement
        modified = AddImportsVisitor(context).transform_module(modified)
        # RemoveImportsVisitor.remove_unused_import was called in leave_Module
        # Apply it to clean up click import if no usages remain
        modified = RemoveImportsVisitor(context).transform_module(modified)

    # SAFETY: Verify generated code is syntactically valid before writing
    if transformer.transformations > 0:
        try:
            compile(modified.code, file_path, 'exec')
        except SyntaxError as e:
            print(f"[CRITICAL] Generated invalid code for {file_path}: {e}", file=sys.stderr)
            print(f"[CRITICAL] Original file preserved - not modified", file=sys.stderr)
            return source, 0

    if not dry_run and transformer.transformations > 0:
        if not module.deep_equals(modified):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(modified.code)

    return modified.code, transformer.transformations


def main():
    """CLI entry point for standalone usage."""
    parser = argparse.ArgumentParser(
        description="Migrate click.echo() to console.print() with Rich tokens"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Python files to transform"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying files"
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show unified diff of changes"
    )

    args = parser.parse_args()

    total_transformations = 0
    files_modified = 0

    for file_path in args.files:
        path = Path(file_path)
        if not path.exists():
            print(f"[ERROR] File not found: {file_path}", file=sys.stderr)
            continue

        if not path.suffix == ".py":
            print(f"[SKIP] Not a Python file: {file_path}", file=sys.stderr)
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            original = f.read()

        new_code, count = transform_file(file_path, dry_run=args.dry_run)

        if count > 0:
            files_modified += 1
            total_transformations += count

            if args.dry_run:
                print(f"[DRY-RUN] {file_path}: {count} transformations")
            else:
                print(f"[OK] {file_path}: {count} transformations")

            if args.diff and original != new_code:
                import difflib
                diff = difflib.unified_diff(
                    original.splitlines(keepends=True),
                    new_code.splitlines(keepends=True),
                    fromfile=f"a/{file_path}",
                    tofile=f"b/{file_path}"
                )
                # Encode with 'replace' to handle Unicode chars that crash CP1252
                diff_text = "".join(diff)
                sys.stdout.buffer.write(diff_text.encode('utf-8', errors='replace'))
                sys.stdout.buffer.write(b'\n')
        else:
            print(f"[SKIP] {file_path}: no click.echo calls found")

    print(f"\n[SUMMARY] {files_modified} files, {total_transformations} transformations")

    if args.dry_run:
        print("[INFO] Dry run - no files were modified")


if __name__ == "__main__":
    main()
