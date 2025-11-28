#!/usr/bin/env python
"""
purge_commentsv3.py - The "Nuclear Option" comment purger (Final Version).

PURPOSE: Break the AI hallucination feedback loop by removing all comments
from a saturated codebase, forcing AI to read only executable logic.

ACTIONS:
1. PURGES: Removes ALL # comments from every .py file
2. GRAVEYARD: Saves ALL removed comments to a flat JSON (backup/reference)
3. DEBT REPORT: Saves ONLY TODO/FIXME/etc to a separate JSON (gold mine for review)
4. TRUNCATE DOCSTRINGS: Optionally truncate verbose docstrings to first line only

PRESERVES (always):
- Code structure and formatting
- Shebang lines (#!/usr/bin/env python)

PRESERVES (optional via flags):
- Semantic comments (type:, noqa, pylint:, pragma:, fmt:) - linter directives
- Copyright headers (copyright, license, (c), etc.) - legal requirements

Based on LibCST 1.8.6 best practices.

Usage:
  python purge_commentsv3.py ./theauditor --dry-run
  python purge_commentsv3.py ./theauditor --preserve-semantic
  python purge_commentsv3.py ./theauditor --preserve-copyright
  python purge_commentsv3.py ./theauditor --truncate-docstrings
"""

import argparse
import json
import os
import sys
import time

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

# =============================================================================
# CONFIGURATION
# =============================================================================

# Directories to skip by default
DEFAULT_SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".eggs", "*.egg-info", ".pf", ".auditor_venv"
}

# Encodings to try when reading files (in order of preference)
# Handles legacy Windows files that aren't UTF-8
FILE_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

# Semantic markers - these are CODE INSTRUCTIONS, not human comments
# Removing these will break linters, type checkers, and coverage tools
SEMANTIC_MARKERS = [
    "type:",          # MyPy/Pyright: # type: ignore, # type: List[str]
    "type=",          # Alternate form
    "noqa",           # Flake8/Ruff: # noqa: E501, # noqa
    "pylint:",        # Pylint: # pylint: disable=...
    "pragma:",        # Coverage: # pragma: no cover
    "fmt:",           # Black/Ruff: # fmt: off, # fmt: on
    "fmt: ",          # With space
    "yapf:",          # YAPF: # yapf: disable
    "isort:",         # isort: # isort: skip
    "nosec",          # Bandit security: # nosec
    "skipcq",         # DeepSource: # skipcq
    "noinspection",   # PyCharm: # noinspection PyUnresolvedReferences
    "pyright:",       # Pyright: # pyright: ignore
    "mypy:",          # MyPy: # mypy: ignore
    "ruff:",          # Ruff: # ruff: noqa
]

# Copyright/license markers - legal headers that may be required
COPYRIGHT_MARKERS = [
    "copyright",
    "license",
    "licensed",
    "spdx-license-identifier",
    "spdx-",
    "(c)",
    "all rights reserved",
    "apache license",
    "mit license",
    "bsd license",
    "gnu general public",
    "gpl",
    "lgpl",
    "mozilla public",
    "proprietary",
]

# Technical debt markers with descriptions
# A comment can match MULTIPLE markers (e.g., "# TODO: HACK around bug")
DEBT_MARKERS = {
    # === CRITICAL - Address immediately ===
    "FIXME": "Known bug requiring fix",
    "BUG": "Known bug",
    "BROKEN": "Known broken code",
    "NOCOMMIT": "Should not have been committed",

    # === HIGH PRIORITY - Address soon ===
    "TODO": "Deferred task",
    "HACK": "Temporary workaround",
    "XXX": "Dangerous/requires attention",
    "KLUDGE": "Ugly hack",
    "WORKAROUND": "Working around an issue",

    # === MEDIUM PRIORITY - Technical debt ===
    "FIX": "Needs fixing",
    "OPTIMIZE": "Performance improvement needed",
    "REFACTOR": "Needs refactoring",
    "CLEANUP": "Needs cleanup",
    "REVIEW": "Needs review",

    # === LOW PRIORITY - Deferred work ===
    "DEFER": "Explicitly deferred",
    "DEFERRED": "Explicitly deferred",
    "LATER": "Do later",
    "WIP": "Work in progress",

    # === INFORMATIONAL - May contain gold ===
    "TEMP": "Temporary code",
    "TEMPORARY": "Temporary code",
    "DEBUG": "Debug code left in",
    "DEPRECATED": "Should be removed",
    "REMOVEME": "Should be removed",
    "NOTE": "Important note",
    "IMPORTANT": "Important information",
}

# Priority ordering for sorting (lower = higher priority)
MARKER_PRIORITY = {
    "FIXME": 1, "BUG": 1, "BROKEN": 1, "NOCOMMIT": 1,
    "TODO": 2, "HACK": 2, "XXX": 2, "KLUDGE": 2, "WORKAROUND": 2,
    "FIX": 3, "OPTIMIZE": 3, "REFACTOR": 3, "CLEANUP": 3, "REVIEW": 3,
    "DEFER": 4, "DEFERRED": 4, "LATER": 4, "WIP": 4,
    "TEMP": 5, "TEMPORARY": 5, "DEBUG": 5, "DEPRECATED": 5, "REMOVEME": 5,
    "NOTE": 6, "IMPORTANT": 6,
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def read_file_with_fallback(filepath: str) -> tuple[str, str]:
    """
    Read file trying multiple encodings.

    Returns: (content, encoding_used)
    Raises: UnicodeDecodeError if all encodings fail
    """
    last_error = None
    for encoding in FILE_ENCODINGS:
        try:
            with open(filepath, encoding=encoding) as f:
                content = f.read()
            return content, encoding
        except UnicodeDecodeError as e:
            last_error = e
            continue

    # All encodings failed
    raise UnicodeDecodeError(
        "all",
        b"",
        0,
        0,
        f"Failed to decode {filepath} with any of: {FILE_ENCODINGS}"
    )


def is_semantic_comment(content: str) -> bool:
    """Check if comment is a semantic/linter directive."""
    content_lower = content.lower()
    return any(marker in content_lower for marker in SEMANTIC_MARKERS)


def is_copyright_comment(content: str) -> bool:
    """Check if comment is a copyright/license header."""
    content_lower = content.lower()
    return any(marker in content_lower for marker in COPYRIGHT_MARKERS)


def detect_debt_tags(comment_text: str) -> list[str]:
    """
    Detect ALL debt markers in a comment (not just the first one).

    A single comment like "# TODO: This is a HACK to work around BUG-123"
    will return ["TODO", "HACK", "BUG"].

    Returns: List of matched markers (empty if none found)
    """
    comment_upper = comment_text.upper()
    found_tags = []

    for marker in DEBT_MARKERS:
        if marker in comment_upper:
            found_tags.append(marker)

    return found_tags


def get_priority_marker(tags: list[str]) -> str:
    """Get the highest-priority marker from a list of tags."""
    if not tags:
        return "UNKNOWN"
    return min(tags, key=lambda t: MARKER_PRIORITY.get(t, 99))


def safe_print(text: str) -> None:
    """Print text safely, replacing non-encodable characters."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Replace problematic characters with ?
        safe_text = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_text)


# =============================================================================
# LIBCST TRANSFORMER
# =============================================================================

def extract_first_line(docstring: str) -> str:
    """Extract the first meaningful line from a docstring.

    Handles both single-line and multi-line docstrings.
    Returns just the summary line, properly quoted.
    """
    # Remove the triple quotes
    content = docstring.strip()

    # Detect quote style
    if content.startswith('"""'):
        quote = '"""'
        inner = content[3:-3]
    elif content.startswith("'''"):
        quote = "'''"
        inner = content[3:-3]
    elif content.startswith('r"""') or content.startswith('f"""'):
        prefix = content[0]
        quote = '"""'
        inner = content[4:-3]
        quote = prefix + quote
    elif content.startswith("r'''") or content.startswith("f'''"):
        prefix = content[0]
        quote = "'''"
        inner = content[4:-3]
        quote = prefix + quote
    else:
        # Not a triple-quoted string, return as-is
        return docstring

    # Get first line/sentence
    inner = inner.strip()

    # Split on newlines and get first non-empty line
    lines = inner.split('\n')
    first_line = ''
    for line in lines:
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break

    if not first_line:
        return f'{quote}{quote}'

    # Return truncated docstring
    return f'{quote}{first_line}{quote}'


class DocstringTruncateTransformer(cst.CSTTransformer):
    """
    Truncates verbose docstrings to first line only.

    Identifies docstrings as:
    - First statement in module body that is a string expression
    - First statement in function/class body that is a string expression

    Preserves:
    - Single-line docstrings (already concise)
    - The first line of multi-line docstrings
    """
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, filename: str) -> None:
        super().__init__()
        self.filename = filename
        self.truncated_docstrings: list[dict] = []
        self.is_first_statement_in_body = False

    def _is_docstring_node(self, node: cst.SimpleStatementLine) -> tuple[bool, cst.BaseExpression | None]:
        """Check if node is a docstring (string expression statement)."""
        if len(node.body) != 1:
            return False, None

        stmt = node.body[0]
        if not isinstance(stmt, cst.Expr):
            return False, None

        expr = stmt.value
        # Check for simple string or concatenated string
        if isinstance(expr, (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString)):
            return True, expr

        return False, None

    def _should_truncate(self, string_node: cst.BaseExpression) -> bool:
        """Check if string should be truncated (is multi-line and verbose)."""
        if isinstance(string_node, cst.SimpleString):
            value = string_node.value
            # Only truncate triple-quoted strings
            if not (value.startswith('"""') or value.startswith("'''") or
                    value.startswith('r"""') or value.startswith("r'''") or
                    value.startswith('f"""') or value.startswith("f'''")):
                return False
            # Count lines - only truncate if > 1 line
            return value.count('\n') > 1
        return False

    def _truncate_string(self, string_node: cst.SimpleString, line: int) -> cst.SimpleString:
        """Truncate a string to its first line."""
        original = string_node.value
        truncated = extract_first_line(original)

        if original != truncated:
            # Log the truncation
            original_lines = original.count('\n') + 1
            self.truncated_docstrings.append({
                "file": self.filename,
                "line": line,
                "original_lines": original_lines,
                "original": original,
                "truncated": truncated,
            })

        return string_node.with_changes(value=truncated)

    def _process_body(
        self,
        body: cst.IndentedBlock | cst.SimpleStatementSuite
    ) -> cst.IndentedBlock | cst.SimpleStatementSuite:
        """Process a body, truncating the first statement if it's a docstring."""
        if not isinstance(body, cst.IndentedBlock):
            return body

        if not body.body:
            return body

        first_stmt = body.body[0]
        if not isinstance(first_stmt, cst.SimpleStatementLine):
            return body

        is_docstring, string_node = self._is_docstring_node(first_stmt)
        if not is_docstring or not isinstance(string_node, cst.SimpleString):
            return body

        if not self._should_truncate(string_node):
            return body

        # Get line number
        try:
            pos = self.get_metadata(PositionProvider, first_stmt)
            line = pos.start.line
        except (KeyError, AttributeError):
            line = -1

        # Truncate the docstring
        new_string = self._truncate_string(string_node, line)
        new_expr = first_stmt.body[0].with_changes(value=new_string)
        new_stmt = first_stmt.with_changes(body=[new_expr])

        # Replace first statement in body
        new_body_list = [new_stmt] + list(body.body[1:])
        return body.with_changes(body=new_body_list)

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Truncate function docstrings."""
        new_body = self._process_body(updated_node.body)
        if new_body is not updated_node.body:
            return updated_node.with_changes(body=new_body)
        return updated_node

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """Truncate class docstrings."""
        new_body = self._process_body(updated_node.body)
        if new_body is not updated_node.body:
            return updated_node.with_changes(body=new_body)
        return updated_node

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module
    ) -> cst.Module:
        """Truncate module docstrings."""
        if not updated_node.body:
            return updated_node

        first_stmt = updated_node.body[0]
        if not isinstance(first_stmt, cst.SimpleStatementLine):
            return updated_node

        is_docstring, string_node = self._is_docstring_node(first_stmt)
        if not is_docstring or not isinstance(string_node, cst.SimpleString):
            return updated_node

        if not self._should_truncate(string_node):
            return updated_node

        # Get line number
        try:
            pos = self.get_metadata(PositionProvider, first_stmt)
            line = pos.start.line
        except (KeyError, AttributeError):
            line = -1

        # Truncate the docstring
        new_string = self._truncate_string(string_node, line)
        new_expr = first_stmt.body[0].with_changes(value=new_string)
        new_stmt = first_stmt.with_changes(body=[new_expr])

        # Replace first statement
        new_body = [new_stmt] + list(updated_node.body[1:])
        return updated_node.with_changes(body=new_body)


class CommentPurgeTransformer(cst.CSTTransformer):
    """
    Removes comments while optionally preserving semantic/copyright markers.

    Per LibCST FAQ Best Practices:
    - Comments are "trivia" attached to EmptyLine and TrailingWhitespace nodes
    - We use PositionProvider for accurate line number logging
    - We modify updated_node (not original_node) to preserve child transformations

    Multi-line debt grouping:
    - If a comment has a debt marker, it starts a new debt entry
    - If the next comment is on line+1 with NO marker, it's a continuation
    - If there's a gap (code between), the chain breaks
    """
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        filename: str,
        preserve_semantic: bool = False,
        preserve_copyright: bool = False
    ) -> None:
        super().__init__()
        self.filename = filename
        self.preserve_semantic = preserve_semantic
        self.preserve_copyright = preserve_copyright
        self.all_comments: list[dict] = []
        self.debt_comments: list[dict] = []
        self.preserved_comments: list[dict] = []

        # State tracking for multi-line debt comment grouping
        # These only affect JSON reporting, not the purge logic
        self.active_debt_entry: dict | None = None
        self.last_debt_line: int = -1

    def _should_preserve(self, content: str) -> tuple[bool, str]:
        """
        Check if a comment should be preserved.

        Returns: (should_preserve, reason)
        """
        if self.preserve_semantic and is_semantic_comment(content):
            return True, "semantic"
        if self.preserve_copyright and is_copyright_comment(content):
            return True, "copyright"
        return False, ""

    def _log_comment(
        self,
        node: cst.CSTNode,
        comment_content: str,
        context_type: str
    ) -> bool:
        """
        Extract comment metadata and categorize.

        Handles multi-line debt grouping:
        - Case A: New debt marker found -> start new entry
        - Case B: No marker, immediate next line -> continuation of previous
        - Case C: No marker, gap in lines -> break chain

        Returns: True if comment should be PRESERVED (not removed)
        """
        # Get line number from metadata
        try:
            pos = self.get_metadata(PositionProvider, node)
            line = pos.start.line
        except (KeyError, AttributeError):
            line = -1

        # Clean content (strip # and whitespace) for readability
        clean_content = comment_content.lstrip("#").strip()

        # Check if we should preserve this comment
        should_preserve, preserve_reason = self._should_preserve(comment_content)

        # Detect debt tags
        tags = detect_debt_tags(comment_content)

        # Build graveyard record (always flat, no grouping)
        record = {
            "file": self.filename,
            "line": line,
            "type": context_type,
            "raw": comment_content,
            "clean": clean_content
        }

        if should_preserve:
            # Track preserved comments separately
            record["preserve_reason"] = preserve_reason
            self.preserved_comments.append(record)
            # Break any active debt chain since we're keeping this comment
            self.active_debt_entry = None
            self.last_debt_line = -1
            return True  # Keep this comment

        # Comment will be removed - add to graveyard (flat dump)
        self.all_comments.append(record)

        # Debt report logic with multi-line grouping
        if tags:
            # CASE A: New debt marker found - start new entry
            primary = get_priority_marker(tags)
            self.active_debt_entry = {
                "file": self.filename,
                "line": line,
                "primary_marker": primary,
                "tags": tags,
                "category": DEBT_MARKERS.get(primary, "Unknown"),
                "clean": clean_content,
                "raw": comment_content
            }
            self.debt_comments.append(self.active_debt_entry)
            self.last_debt_line = line

        elif self.active_debt_entry is not None and line == self.last_debt_line + 1:
            # CASE B: No marker, but immediate next line - continuation
            # Append this text to the previous debt entry
            self.active_debt_entry["clean"] += f" {clean_content}"
            self.active_debt_entry["raw"] += f"\n{comment_content}"
            self.last_debt_line = line

        else:
            # CASE C: No marker, and gap or first comment - break chain
            self.active_debt_entry = None
            self.last_debt_line = -1

        return False  # Remove this comment

    def leave_EmptyLine(
        self,
        original_node: cst.EmptyLine,
        updated_node: cst.EmptyLine
    ) -> cst.EmptyLine:
        """Handle block comments (lines that are just # comment)."""
        if updated_node.comment is not None:
            should_keep = self._log_comment(
                original_node, updated_node.comment.value, "block"
            )
            if not should_keep:
                return updated_node.with_changes(comment=None)
        return updated_node

    def leave_TrailingWhitespace(
        self,
        original_node: cst.TrailingWhitespace,
        updated_node: cst.TrailingWhitespace
    ) -> cst.TrailingWhitespace:
        """Handle inline comments (e.g., x = 1  # comment)."""
        if updated_node.comment is not None:
            should_keep = self._log_comment(
                original_node, updated_node.comment.value, "inline"
            )
            if not should_keep:
                return updated_node.with_changes(comment=None)
            # Inline comments usually end a context, so reset chain
            # (only if we didn't preserve - preserve already resets)
        else:
            # No comment on this line - if there was code, break the chain
            # This handles: # TODO: foo \n x = 1 \n # more comment
            pass
        return updated_node


# =============================================================================
# FILE PROCESSING
# =============================================================================

def process_file(
    filepath: str,
    graveyard_log: list[dict],
    debt_log: list[dict],
    preserved_log: list[dict],
    docstring_log: list[dict],
    preserve_semantic: bool = False,
    preserve_copyright: bool = False,
    truncate_docstrings: bool = False,
    dry_run: bool = False
) -> tuple[int, int, int, int]:
    """
    Process a single Python file to remove comments and optionally truncate docstrings.

    Returns: (total_removed, debt_count, preserved_count, docstrings_truncated)
    """
    try:
        # Read with encoding fallback
        source, encoding = read_file_with_fallback(filepath)

        # Parse module
        module = cst.parse_module(source)

        # Wrap with metadata for PositionProvider
        wrapper = MetadataWrapper(module)

        # Create and apply comment transformer
        transformer = CommentPurgeTransformer(
            filepath,
            preserve_semantic=preserve_semantic,
            preserve_copyright=preserve_copyright
        )
        modified_module = wrapper.visit(transformer)

        # Collect comment results
        removed_count = len(transformer.all_comments)
        debt_count = len(transformer.debt_comments)
        preserved_count = len(transformer.preserved_comments)

        if removed_count > 0:
            graveyard_log.extend(transformer.all_comments)
        if debt_count > 0:
            debt_log.extend(transformer.debt_comments)
        if preserved_count > 0:
            preserved_log.extend(transformer.preserved_comments)

        # Apply docstring truncation if requested
        docstrings_truncated = 0
        if truncate_docstrings:
            # Re-wrap for second pass (metadata must be fresh)
            wrapper2 = MetadataWrapper(modified_module)
            docstring_transformer = DocstringTruncateTransformer(filepath)
            modified_module = wrapper2.visit(docstring_transformer)
            docstrings_truncated = len(docstring_transformer.truncated_docstrings)
            if docstrings_truncated > 0:
                docstring_log.extend(docstring_transformer.truncated_docstrings)

        # Per FAQ Best Practice #4: Only write if tree actually changed
        if not module.deep_equals(modified_module):
            if not dry_run:
                # Write with same encoding we read with
                with open(filepath, "w", encoding=encoding, newline="") as f:
                    f.write(modified_module.code)
            return removed_count, debt_count, preserved_count, docstrings_truncated

        return 0, 0, preserved_count, 0

    except cst.ParserSyntaxError as e:
        safe_print(f"  ! SYNTAX ERROR in {filepath}: {e}")
        return 0, 0, 0, 0
    except UnicodeDecodeError as e:
        safe_print(f"  ! ENCODING ERROR in {filepath}: {e}")
        return 0, 0, 0, 0
    except Exception as e:
        safe_print(f"  ! ERROR processing {filepath}: {type(e).__name__}: {e}")
        return 0, 0, 0, 0


# =============================================================================
# DIRECTORY PROCESSING
# =============================================================================

def purge_directory(
    directory: str,
    graveyard_file: str,
    debt_file: str,
    docstring_file: str,
    skip_dirs: set[str],
    preserve_semantic: bool = False,
    preserve_copyright: bool = False,
    truncate_docstrings: bool = False,
    skip_commands: bool = False,
    dry_run: bool = False,
    extract_only: bool = False
) -> tuple[int, int, int, int, int]:
    """
    Walk directory and purge comments from all Python files.

    Returns: (total_removed, debt_count, preserved_count, docstrings_truncated, files_modified)
    """
    total_removed = 0
    total_debt = 0
    total_preserved = 0
    total_docstrings = 0
    files_modified = 0
    graveyard_log: list[dict] = []
    debt_log: list[dict] = []
    preserved_log: list[dict] = []
    docstring_log: list[dict] = []

    start_time = time.time()
    abs_dir = os.path.abspath(directory)

    if dry_run:
        mode_str = "[DRY RUN] "
    elif extract_only:
        mode_str = "[EXTRACT ONLY] "
    else:
        mode_str = ""
    safe_print(f"{mode_str}NUCLEAR COMMENT PURGE")
    safe_print(f"Target: {abs_dir}")
    safe_print(f"Skipping: {', '.join(sorted(skip_dirs))}")
    safe_print(f"Debt markers: {len(DEBT_MARKERS)} types tracked")
    if preserve_semantic:
        safe_print("PRESERVING: Semantic comments (type:, noqa, pylint:, etc.)")
    if preserve_copyright:
        safe_print("PRESERVING: Copyright/license headers")
    if truncate_docstrings:
        safe_print("TRUNCATING: Verbose docstrings to first line only")
        if skip_commands:
            safe_print("SKIPPING: Docstrings in commands/ directories (preserving --help)")
    safe_print("")

    for root, dirs, files in os.walk(directory):
        # Modify dirs in-place to skip specified directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                # Normalize to forward slashes for consistent JSON output
                filepath_normalized = filepath.replace("\\", "/")

                # Check if this file is in a commands directory
                is_command_file = "/commands/" in filepath_normalized or "\\commands\\" in filepath
                should_truncate = truncate_docstrings and not (skip_commands and is_command_file)

                removed, debt, preserved, docstrings = process_file(
                    filepath_normalized,
                    graveyard_log,
                    debt_log,
                    preserved_log,
                    docstring_log,
                    preserve_semantic=preserve_semantic,
                    preserve_copyright=preserve_copyright,
                    truncate_docstrings=should_truncate,
                    dry_run=dry_run or extract_only  # Don't modify source files
                )

                if removed > 0 or docstrings > 0:
                    total_removed += removed
                    total_debt += debt
                    total_preserved += preserved
                    total_docstrings += docstrings
                    files_modified += 1

                    parts = []
                    if removed > 0:
                        parts.append(f"{removed} comments")
                    if debt > 0:
                        parts.append(f"{debt} debt")
                    if preserved > 0:
                        parts.append(f"{preserved} kept")
                    if docstrings > 0:
                        parts.append(f"{docstrings} docstrings")

                    safe_print(f"  - {', '.join(parts)} : {filepath_normalized}")

    # Save outputs (write JSON for extract_only, but not for dry_run)
    if not dry_run:
        # 1. Graveyard: flat dump of ALL removed comments
        if graveyard_log:
            with open(graveyard_file, "w", encoding="utf-8") as f:
                # Use ensure_ascii=True to avoid encoding issues with emojis
                json.dump(graveyard_log, f, indent=2, ensure_ascii=False)

        # 2. Debt report: sorted by priority, then file, then line
        if debt_log:
            sorted_debt = sorted(
                debt_log,
                key=lambda x: (
                    MARKER_PRIORITY.get(x.get("primary_marker", ""), 99),
                    x.get("file", ""),
                    x.get("line", 0)
                )
            )
            with open(debt_file, "w", encoding="utf-8") as f:
                json.dump(sorted_debt, f, indent=2, ensure_ascii=False)

        # 3. Docstring graveyard: sorted by original line count (biggest first)
        if docstring_log:
            sorted_docstrings = sorted(
                docstring_log,
                key=lambda x: (-x.get("original_lines", 0), x.get("file", ""), x.get("line", 0))
            )
            with open(docstring_file, "w", encoding="utf-8") as f:
                json.dump(sorted_docstrings, f, indent=2, ensure_ascii=False)

    duration = time.time() - start_time

    # Summary
    safe_print("")
    safe_print("=" * 60)
    safe_print(f"{mode_str}COMPLETED in {duration:.2f}s")
    safe_print(f"Files Modified: {files_modified}")
    safe_print(f"Comments Removed: {total_removed}")
    safe_print(f"Comments Preserved: {len(preserved_log)}")
    safe_print(f"Technical Debt Found: {total_debt}")
    if truncate_docstrings:
        safe_print(f"Docstrings Truncated: {total_docstrings}")

    # Debt breakdown by marker type
    if debt_log:
        safe_print("")
        safe_print("=== TECHNICAL DEBT BREAKDOWN ===")
        debt_by_marker: dict[str, int] = {}
        for item in debt_log:
            marker = item.get("primary_marker", "UNKNOWN")
            debt_by_marker[marker] = debt_by_marker.get(marker, 0) + 1

        # Sort by priority then count
        for marker, count in sorted(
            debt_by_marker.items(),
            key=lambda x: (MARKER_PRIORITY.get(x[0], 99), -x[1])
        ):
            desc = DEBT_MARKERS.get(marker, "Unknown")
            priority = MARKER_PRIORITY.get(marker, 99)
            priority_label = {
                1: "CRITICAL", 2: "HIGH", 3: "MEDIUM",
                4: "LOW", 5: "INFO", 6: "NOTE"
            }.get(priority, "")
            safe_print(f"  {marker:12} : {count:4}  [{priority_label:8}] {desc}")

    # Preserved breakdown
    if preserved_log:
        safe_print("")
        safe_print("=== PRESERVED COMMENTS ===")
        by_reason: dict[str, int] = {}
        for item in preserved_log:
            reason = item.get("preserve_reason", "unknown")
            by_reason[reason] = by_reason.get(reason, 0) + 1
        for reason, count in sorted(by_reason.items()):
            safe_print(f"  {reason:12} : {count:4}")

    # Output files
    if not dry_run:
        safe_print("")
        safe_print("OUTPUT FILES:")
        if graveyard_log:
            safe_print(f"  {graveyard_file}")
            safe_print(f"    -> {len(graveyard_log)} comments (backup dump)")
        if debt_log:
            safe_print(f"  {debt_file}")
            safe_print(f"    -> {len(debt_log)} items (REVIEW THIS FOR GOLD)")
        if docstring_log:
            safe_print(f"  {docstring_file}")
            safe_print(f"    -> {len(docstring_log)} docstrings (truncated originals)")
    safe_print("=" * 60)

    return total_removed, total_debt, len(preserved_log), total_docstrings, files_modified


# =============================================================================
# CLI
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nuclear comment purger - removes ALL # comments, extracts debt markers, truncates docstrings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WHAT THIS DOES:
  1. Removes ALL # comments from Python files (by default)
  2. Saves ALL removed comments to graveyard JSON (backup)
  3. Saves ONLY debt markers (TODO/FIXME/etc) to separate JSON
  4. Optionally truncates verbose docstrings to first line only

OUTPUT FILES:
  comment_graveyard.json  - ALL removed comments (backup dump)
  technical_debt.json     - ONLY tagged comments (gold mine for review)
  docstring_graveyard.json - Original docstrings before truncation

FLAGS:
  --preserve-semantic    Keep linter directives (type:, noqa, pylint:, etc.)
  --preserve-copyright   Keep copyright/license headers
  --truncate-docstrings  Truncate multi-line docstrings to first line only

DEBT MARKERS TRACKED (27 types):
  CRITICAL: FIXME, BUG, BROKEN, NOCOMMIT
  HIGH:     TODO, HACK, XXX, KLUDGE, WORKAROUND
  MEDIUM:   FIX, OPTIMIZE, REFACTOR, CLEANUP, REVIEW
  LOW:      DEFER, DEFERRED, LATER, WIP
  INFO:     TEMP, TEMPORARY, DEBUG, DEPRECATED, REMOVEME, NOTE, IMPORTANT

EXAMPLES:
  # Preview only (ALWAYS DO THIS FIRST)
  python purge_commentsv3.py ./theauditor --dry-run

  # Extract comments to JSON WITHOUT modifying source files
  python purge_commentsv3.py ./theauditor --extract-only

  # Full nuclear - remove comments AND truncate docstrings
  python purge_commentsv3.py ./theauditor --truncate-docstrings --no-confirm

  # Just truncate docstrings (preserve comments)
  python purge_commentsv3.py ./theauditor --truncate-docstrings --preserve-semantic --no-confirm

  # Skip additional directories
  python purge_commentsv3.py . --skip tests,fixtures

AFTER RUNNING:
  ruff format .             # Clean up whitespace gaps
  cat technical_debt.json   # Review the gold
"""
    )

    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Target directory (default: current directory)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files or writing JSON"
    )

    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Extract comments to JSON files WITHOUT modifying source files"
    )

    parser.add_argument(
        "--preserve-semantic",
        action="store_true",
        help="Keep semantic comments (type:, noqa, pylint:, pragma:, fmt:, etc.)"
    )

    parser.add_argument(
        "--preserve-copyright",
        action="store_true",
        help="Keep copyright/license headers"
    )

    parser.add_argument(
        "--truncate-docstrings",
        action="store_true",
        help="Truncate multi-line docstrings to first line only (removes verbose docs)"
    )

    parser.add_argument(
        "--skip-commands",
        action="store_true",
        help="Skip docstring truncation in commands/ directory (preserves --help text)"
    )

    parser.add_argument(
        "--graveyard",
        default="comment_graveyard.json",
        help="Output file for ALL removed comments (default: comment_graveyard.json)"
    )

    parser.add_argument(
        "--debt-file",
        default="technical_debt.json",
        help="Output file for debt markers only (default: technical_debt.json)"
    )

    parser.add_argument(
        "--docstring-file",
        default="docstring_graveyard.json",
        help="Output file for truncated docstrings (default: docstring_graveyard.json)"
    )

    parser.add_argument(
        "--skip",
        type=str,
        default="",
        help="Additional directories to skip (comma-separated)"
    )

    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # Build skip set
    skip_dirs = DEFAULT_SKIP_DIRS.copy()
    if args.skip:
        for d in args.skip.split(","):
            skip_dirs.add(d.strip())

    # Validate directory
    if not os.path.isdir(args.directory):
        safe_print(f"ERROR: Directory not found: {args.directory}")
        return 1

    # Confirmation prompt (skip if not modifying files)
    if not args.no_confirm and not args.dry_run and not args.extract_only:
        safe_print("=" * 60)
        safe_print("WARNING: NUCLEAR OPTION")
        safe_print("This will DELETE ALL # comments from Python files.")
        if args.truncate_docstrings:
            safe_print("This will TRUNCATE all multi-line docstrings to first line.")
        else:
            safe_print("Docstrings (triple-quoted) will remain intact.")
        if args.preserve_semantic:
            safe_print("KEEPING: Semantic comments (type:, noqa, etc.)")
        if args.preserve_copyright:
            safe_print("KEEPING: Copyright/license headers")
        safe_print("=" * 60)
        safe_print("")
        confirm = input("Do you have a git commit? (yes/no): ")
        if confirm.lower() not in ("yes", "y"):
            safe_print("")
            safe_print("Aborting. First run:")
            safe_print("  git add -A && git commit -m 'pre-purge snapshot'")
            return 1
        safe_print("")

    # Execute purge
    removed, debt, preserved, docstrings, files = purge_directory(
        args.directory,
        args.graveyard,
        args.debt_file,
        args.docstring_file,
        skip_dirs,
        preserve_semantic=args.preserve_semantic,
        preserve_copyright=args.preserve_copyright,
        truncate_docstrings=args.truncate_docstrings,
        skip_commands=args.skip_commands,
        dry_run=args.dry_run,
        extract_only=args.extract_only
    )

    # Next steps
    if (removed > 0 or docstrings > 0) and not args.dry_run:
        safe_print("")
        safe_print("NEXT STEPS:")
        safe_print("  1. Clean up whitespace gaps:")
        safe_print("     ruff format .")
        safe_print("")
        if debt > 0:
            safe_print("  2. Mine the gold:")
            safe_print(f"     cat {args.debt_file}")
            safe_print("")
            safe_print("  3. Address by priority:")
            safe_print("     - CRITICAL first (FIXME, BUG, BROKEN)")
            safe_print("     - Then HIGH (TODO, HACK, XXX)")
        if docstrings > 0:
            safe_print("")
            safe_print(f"  Truncated docstrings backed up to: {args.docstring_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
