"""LibCST codemod: Migrate print('[TAG]...') statements to Loguru logger calls.

This script automates the migration of TheAuditor's logging infrastructure from
scattered print() statements to centralized Loguru logging.

Usage:
    # Dry run - preview changes without modifying files
    python scripts/loguru_migration.py theauditor/ --dry-run

    # Apply changes to directory
    python scripts/loguru_migration.py theauditor/

    # Single file with diff output
    python scripts/loguru_migration.py theauditor/taint/core.py --dry-run --diff

    # Multiple specific files
    python scripts/loguru_migration.py file1.py file2.py file3.py

Transformations:
    1. print(f"[TAG] message") -> logger.level("message")
    2. print(f"[TAG] message", file=sys.stderr) -> logger.level("message")
    3. if os.environ.get("THEAUDITOR_DEBUG"): print(...) -> logger.debug(...)
    4. print("msg", file=sys.stderr) [no tag] -> logger.error("msg")
    5. print("A", "B", sep=", ") -> logger.info("{}, {}", "A", "B")
    6. traceback.print_exc() -> logger.exception("") [captures stack trace]

Edge Cases Handled:
    - end="" or end="\\r": SKIPPED (progress bars, loggers always add newlines)
    - sep=",": Custom separator preserved in format string injection
    - sep=my_var (dynamic): SKIPPED (cannot build static format string)
    - file=sys.stderr without tag: Defaults to logger.error level
    - file=custom_handle: SKIPPED (would lose file destination - data loss prevention)
    - Multi-arg prints: Format string "{} {}" injected to prevent silent data loss
    - Brace hazard: Single args with {/} get format injection to prevent crash
    - Debug guards: Comments preserved when unwrapping if THEAUDITOR_DEBUG blocks
    - Eager evaluation: Debug guards with function calls keep wrapper (perf protection)

Tag-to-Level Mapping:
    [DEBUG], [TRACE], [INDEXER_DEBUG], [DEDUP], [SCHEMA] -> debug
    [INFO], [Indexer], [TAINT], [FCE], [GRAPH], [RULES] -> info
    [WARNING], [WARN] -> warning
    [ERROR] -> error
    [CRITICAL], [FATAL] -> critical

Safety Features:
    - Syntax validation via compile() before writing any file
    - Dry-run mode with diff output for preview
    - Multi-encoding support (utf-8, latin-1, cp1252)
    - Safe print wrapper for Windows CP1252 console

Author: TheAuditor Team
Date: 2025-12-01
LibCST Version: 1.8.6+
"""
from __future__ import annotations

from typing import Sequence, Union

import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor


class PrintToLoguruCodemod(VisitorBasedCodemodCommand):
    """Convert print('[TAG]...') statements to loguru logger calls.

    Fixed issues from code review:
    1. Multi-argument preservation: print("[TAG] msg", var) -> logger.level("msg", var)
    2. Keyword argument filtering: file=sys.stderr, flush=True are dropped
    3. ConcatenatedString handling: recursive tag stripping from left side
    4. Empty print handling: print("[TAG]") -> logger.level("") (empty log)
    5. Debug guard preservation: always keeps if wrapper (no FlattenSentinel)
    """

    DESCRIPTION = "Convert print('[TAG]...') statements to loguru logger calls"

    # Map [TAG] prefixes to log levels
    # Order matters - longer/more specific tags should come first
    TAG_TO_LEVEL: dict[str, str] = {
        # Debug-level tags (internal diagnostics)
        "[RESOLVER_DEBUG]": "debug",
        "[INDEXER_DEBUG]": "debug",
        "[AST_DEBUG]": "debug",
        "[DEBUG]": "debug",
        "[TRACE]": "trace",
        "[DEDUP]": "debug",
        "[SCHEMA]": "debug",
        "[NORMALIZE]": "debug",
        "[IFDS]": "debug",
        "[CORE]": "debug",
        # Info-level tags (operational messages)
        "[ORCHESTRATOR]": "info",
        "[METADATA]": "info",
        "[Indexer]": "info",
        "[TAINT]": "info",
        "[INFO]": "info",
        "[FCE]": "info",
        "[GRAPH]": "info",
        "[RULES]": "info",
        "[STATUS]": "info",
        "[ARCHIVE]": "info",
        "[OK]": "info",
        "[TIP]": "info",
        "[DB]": "info",
        "[ML]": "info",
        # Warning-level tags
        "[WARNING]": "warning",
        "[WARN]": "warning",
        # Error-level tags
        "[ERROR]": "error",
        # Critical-level tags
        "[CRITICAL]": "critical",
        "[FATAL]": "critical",
    }

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.needs_logger_import = False
        self.needs_traceback_cleanup = False
        self.in_debug_guard = False
        self.transform_count = 0  # Track actual number of transformations

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_level_from_str(self, text: str) -> tuple[str, str] | None:
        """Check string content for tags. Returns (level, tag) or None."""
        for tag, level in self.TAG_TO_LEVEL.items():
            if tag in text:
                return level, tag
        return None

    def _analyze_first_arg(self, node: cst.BaseExpression) -> tuple[str, str] | None:
        """Recursively check first argument for tags."""
        if isinstance(node, cst.FormattedString):
            full_text = "".join(
                part.value
                for part in node.parts
                if isinstance(part, cst.FormattedStringText)
            )
            return self._get_level_from_str(full_text)

        elif isinstance(node, cst.SimpleString):
            return self._get_level_from_str(node.value)

        elif isinstance(node, cst.ConcatenatedString):
            # Implicit concatenation: "a" "b"
            return self._analyze_first_arg(node.left)

        elif isinstance(node, cst.BinaryOperation):
            # Explicit concatenation: "a" + "b"
            if isinstance(node.operator, cst.Add):
                return self._analyze_first_arg(node.left)

        return None

    def _is_debug_guard(self, node: cst.If) -> bool:
        """Check for: if os.environ.get('THEAUDITOR_DEBUG'):"""
        return m.matches(
            node.test,
            m.Call(
                func=m.Attribute(attr=m.Name("get")),
                args=[
                    m.Arg(
                        value=m.MatchIfTrue(
                            lambda n: isinstance(n, cst.SimpleString)
                            and "THEAUDITOR_DEBUG" in n.value
                        )
                    )
                ],
            ),
        )

    def _is_safe_to_unwrap(self, print_call: cst.Call) -> bool:
        """Check if print args are simple enough to unwrap without eager eval risk.

        If args contain function calls, we must KEEP the if wrapper to preserve
        lazy evaluation semantics:
            if DEBUG: print(expensive_calc())  # Only runs if DEBUG
            logger.debug(expensive_calc())     # ALWAYS runs - perf regression!
        """
        for arg in print_call.args:
            if arg.keyword is not None:
                continue  # Skip keyword args like file=, end=
            # Safe: literals, names, f-strings, simple strings
            if m.matches(
                arg.value,
                m.SimpleString()
                | m.FormattedString()
                | m.ConcatenatedString()
                | m.Name()
                | m.Integer()
                | m.Float(),
            ):
                continue
            # Unsafe: function calls, binary ops, list comps, etc.
            return False
        return True

    def _clean_string_value(self, value: str, tag: str) -> str:
        """Remove tag and leading whitespace safely."""
        if tag in value:
            return value.replace(tag, "", 1).lstrip()
        return value

    def _strip_tag(self, node: cst.BaseExpression, tag: str) -> cst.BaseExpression | None:
        """Recursively strip tag from the node. Returns None if result is empty."""
        if isinstance(node, cst.FormattedString):
            new_parts = []
            stripped = False
            for part in node.parts:
                if not stripped and isinstance(part, cst.FormattedStringText):
                    new_val = self._clean_string_value(part.value, tag)
                    if new_val != part.value:
                        stripped = True
                        if new_val:  # Only keep if not empty
                            new_parts.append(part.with_changes(value=new_val))
                    else:
                        new_parts.append(part)
                else:
                    new_parts.append(part)
            if not new_parts:
                return None
            return node.with_changes(parts=new_parts)

        elif isinstance(node, cst.SimpleString):
            full_val = node.value
            # Handle quote wrapper
            if full_val.startswith('"""') or full_val.startswith("'''"):
                quote_len = 3
            else:
                quote_len = 1

            quote = full_val[:quote_len]
            inner = full_val[quote_len:-quote_len]
            new_inner = self._clean_string_value(inner, tag)

            if not new_inner:
                return None
            return node.with_changes(value=f"{quote}{new_inner}{quote}")

        elif isinstance(node, cst.ConcatenatedString):
            # Implicit concatenation: "a" "b"
            new_left = self._strip_tag(node.left, tag)
            if new_left is None:
                # Left side became empty, return just the right side
                return node.right
            return node.with_changes(left=new_left)

        elif isinstance(node, cst.BinaryOperation):
            # Explicit concatenation: "a" + "b"
            if isinstance(node.operator, cst.Add):
                new_left = self._strip_tag(node.left, tag)
                if new_left is None:
                    # Left side became empty, return just the right side
                    return node.right
                return node.with_changes(left=new_left)

        return node

    def _is_empty_string(self, node: cst.BaseExpression) -> bool:
        """Check if a node represents an empty string."""
        if isinstance(node, cst.SimpleString):
            inner = node.value[1:-1] if len(node.value) >= 2 else ""
            if node.value.startswith('"""') or node.value.startswith("'''"):
                inner = node.value[3:-3] if len(node.value) >= 6 else ""
            return not inner.strip()
        return False

    def _extract_string_value(self, node: cst.BaseExpression) -> str | None:
        """Extract the raw string value from a SimpleString node."""
        if not isinstance(node, cst.SimpleString):
            return None
        raw = node.value
        # Handle triple-quoted strings
        if raw.startswith('"""') or raw.startswith("'''"):
            return raw[3:-3]
        # Handle single/double quoted strings
        if raw.startswith(("'", '"')):
            return raw[1:-1]
        return None

    def _convert_print_to_logger(
        self, print_call: cst.Call, force_level: str | None = None
    ) -> cst.Call | None:
        """Convert a print() call to logger.level() call.

        Handles:
        - Tag stripping: print("[TAG] msg") -> logger.level("msg")
        - Multi-args with format string injection (CRITICAL FIX):
          print("A", "B") -> logger.info("{} {}", "A", "B")
          This prevents Loguru from silently dropping arguments!
        - Keyword filtering: file=sys.stderr, flush=True are dropped
        - sep argument: Uses actual separator in format string
        - end argument: Skips transformation if end != newline (progress bars)
        - stderr: Defaults to logger.error for untagged stderr prints
        """
        if not print_call.args:
            return None

        # ---------------------------------------------------------------------
        # AUDIT FIX 1: Detect 'end' argument - skip if not newline
        # Progress bars use end="" or end="\r" - loggers cannot handle this
        # ---------------------------------------------------------------------
        for arg in print_call.args:
            if arg.keyword and arg.keyword.value == "end":
                end_val = self._extract_string_value(arg.value)
                if end_val is not None:
                    # Normalize escape sequences for comparison
                    # Check if end is NOT a standard newline
                    if end_val not in ("\n", "\\n"):
                        return None  # Skip - likely a progress bar

        # ---------------------------------------------------------------------
        # AUDIT FIX 2: Detect file= argument
        # ---------------------------------------------------------------------
        has_stderr = False
        for arg in print_call.args:
            if arg.keyword and arg.keyword.value == "file":
                # Check for sys.stderr match
                if m.matches(
                    arg.value,
                    m.Attribute(value=m.Name("sys"), attr=m.Name("stderr")),
                ):
                    has_stderr = True
                else:
                    # CRITICAL: Custom file handle detected (not stderr)
                    # e.g. print("data", file=audit_log) - cannot migrate safely
                    return None
                break

        # Analyze the first argument for a tag
        first_arg = print_call.args[0].value
        analysis = self._analyze_first_arg(first_arg)

        # Determine level and tag to strip
        level = "info"
        tag_to_strip = None

        if force_level:
            level = force_level
            # If forced (debug guard), still strip tags if they exist
            if analysis:
                _, tag_to_strip = analysis
        elif analysis:
            level, tag_to_strip = analysis
        elif has_stderr:
            # AUDIT FIX 2: No tag, but printing to stderr -> ERROR level
            level = "error"
        else:
            # No tag found, no force, no stderr -> Don't transform
            return None

        # ---------------------------------------------------------------------
        # AUDIT FIX 3: Extract 'sep' argument for format string
        # ---------------------------------------------------------------------
        separator = " "  # Default print separator
        for arg in print_call.args:
            if arg.keyword and arg.keyword.value == "sep":
                sep_val = self._extract_string_value(arg.value)
                if sep_val is not None:
                    separator = sep_val
                else:
                    # sep is a variable/expression - cannot build static format string
                    # e.g. print("A", "B", sep=my_var) -> SKIP transformation
                    return None
                break

        # ---------------------------------------------------------------------
        # Step 1: Collect valid arguments
        # ---------------------------------------------------------------------
        log_args: list[cst.Arg] = []

        # Process first argument (strip tag)
        if tag_to_strip:
            cleaned_first_arg = self._strip_tag(first_arg, tag_to_strip)
            # Only add if it didn't become empty
            if cleaned_first_arg is not None and not self._is_empty_string(cleaned_first_arg):
                log_args.append(cst.Arg(value=cleaned_first_arg))
        else:
            # Create fresh Arg to strip original comma/whitespace metadata
            log_args.append(cst.Arg(value=print_call.args[0].value))

        # Add subsequent positional arguments
        # print("[TAG] msg", var1, var2)
        if len(print_call.args) > 1:
            for arg in print_call.args[1:]:
                # Filter out keyword args (file=sys.stderr, flush=True, end="", sep=" ")
                # These are print()-specific and would crash Loguru or be misinterpreted
                if arg.keyword is None:
                    # Create fresh Arg to strip trailing comma metadata
                    log_args.append(cst.Arg(value=arg.value))

        # Handle case where tag stripping left us with nothing: print("[TAG]")
        if not log_args and tag_to_strip:
            log_args.append(cst.Arg(cst.SimpleString('""')))

        # If still no args (shouldn't happen, but defensive), skip
        if not log_args:
            return None

        # ---------------------------------------------------------------------
        # Step 2: Inject Format String (THE CRITICAL FIX)
        # ---------------------------------------------------------------------
        # Loguru behavior: logger.info("Val:", x) -> attempts to format "Val:" with x
        # If "Val:" has no braces, x is SILENTLY DROPPED.
        # BRACE HAZARD: Single args with {} will crash Loguru at runtime!
        # e.g. logger.info("Regex: {0-9}") -> ValueError
        # Fix: Force format injection for single args containing braces too.
        should_inject_format = False

        if len(log_args) > 1:
            should_inject_format = True
        elif len(log_args) == 1:
            # Check for dangerous braces in single string literal
            arg_val = log_args[0].value
            if isinstance(arg_val, cst.SimpleString):
                raw_val = self._extract_string_value(arg_val)
                if raw_val and ("{" in raw_val or "}" in raw_val):
                    should_inject_format = True
            elif isinstance(arg_val, cst.FormattedString):
                # f-strings: check FormattedStringText parts for literal braces
                for part in arg_val.parts:
                    if isinstance(part, cst.FormattedStringText):
                        if "{" in part.value or "}" in part.value:
                            should_inject_format = True
                            break

        if should_inject_format:
            # Create format string using the actual separator
            format_str = separator.join(["{}"] * len(log_args))
            format_arg = cst.Arg(value=cst.SimpleString(f'"{format_str}"'))
            # Insert at beginning: logger.info("{}", arg1)
            log_args.insert(0, format_arg)

        self.needs_logger_import = True
        self.transform_count += 1

        return cst.Call(
            func=cst.Attribute(
                value=cst.Name("logger"),
                attr=cst.Name(level),
            ),
            args=log_args,
        )

    # -------------------------------------------------------------------------
    # Visitor Methods
    # -------------------------------------------------------------------------

    def visit_If(self, node: cst.If) -> bool:
        """Track when we enter a debug guard."""
        if self._is_debug_guard(node):
            self.in_debug_guard = True
        return True

    def leave_If(
        self, original_node: cst.If, updated_node: cst.If
    ) -> cst.BaseStatement:
        """Handle 'if os.environ.get("THEAUDITOR_DEBUG"):' blocks.

        Logic:
        1. Is this a debug guard? (e.g. if THEAUDITOR_DEBUG...)
        2. Look inside the body.
        3. CASE A: It contains ONLY a print statement.
           -> Transform the print to logger.debug
           -> REMOVE the 'if' wrapper entirely (unwrap it).
        4. CASE B: It contains a print statement AND other stuff.
           -> Transform the print to logger.debug
           -> KEEP the 'if' wrapper (to preserve the other stuff).

        Why unwrap CASE A? The if guard is redundant - Loguru respects log levels,
        so logger.debug() won't output unless THEAUDITOR_LOG_LEVEL=DEBUG anyway.
        Removing the wrapper reduces visual noise and indentation.
        """
        # Check if this is a debug guard using existing helper
        if not self._is_debug_guard(original_node):
            return updated_node

        self.in_debug_guard = False

        # Access the body of the if statement
        if not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node

        body_stmts = updated_node.body.body

        # ---------------------------------------------------------------------
        # CASE A: The Perfect Candidate (Only 1 statement, and it's a print)
        # Only unwrap if args are simple (no function calls = no eager eval risk)
        # ---------------------------------------------------------------------
        if len(body_stmts) == 1:
            stmt = body_stmts[0]

            # Check if that single statement is a print()
            if m.matches(
                stmt,
                m.SimpleStatementLine(body=[m.Expr(value=m.Call(func=m.Name("print")))]),
            ):
                # Extract the print call safely using ensure_type
                simple_line = cst.ensure_type(stmt, cst.SimpleStatementLine)
                expr_stmt = cst.ensure_type(simple_line.body[0], cst.Expr)
                print_call = cst.ensure_type(expr_stmt.value, cst.Call)

                # EAGER EVAL CHECK: Only unwrap if args are simple
                # if DEBUG: print(expensive())  <- keep wrapper (lazy)
                # if DEBUG: print("msg", var)   <- safe to unwrap
                if self._is_safe_to_unwrap(print_call):
                    new_call = self._convert_print_to_logger(print_call, force_level="debug")

                    if new_call:
                        # SUCCESS: Unwrap - return just the logger call
                        # MERGE COMMENTS: Combine outer (if) + inner (print) leading_lines
                        combined_leading_lines = list(original_node.leading_lines) + list(
                            simple_line.leading_lines
                        )
                        return cst.SimpleStatementLine(
                            body=[cst.Expr(value=new_call)],
                            leading_lines=combined_leading_lines,
                        )
                # Not safe to unwrap - fall through to CASE B

        # ---------------------------------------------------------------------
        # CASE B: The Mixed Bag (Contains print + other logic)
        # We must keep the 'if', but still transform prints inside it.
        # ---------------------------------------------------------------------
        new_body_stmts: list[cst.BaseStatement] = []
        modified = False

        for stmt in body_stmts:
            # Check if this specific line is a print
            if m.matches(
                stmt,
                m.SimpleStatementLine(body=[m.Expr(value=m.Call(func=m.Name("print")))]),
            ):
                simple_line = cst.ensure_type(stmt, cst.SimpleStatementLine)
                expr_stmt = cst.ensure_type(simple_line.body[0], cst.Expr)
                print_call = cst.ensure_type(expr_stmt.value, cst.Call)

                # Transform it
                new_call = self._convert_print_to_logger(print_call, force_level="debug")

                if new_call:
                    modified = True
                    new_body_stmts.append(
                        cst.SimpleStatementLine(body=[cst.Expr(value=new_call)])
                    )
                    continue

            # If it's not a print (or transformation failed), keep original line
            new_body_stmts.append(stmt)

        # If we changed anything inside, return the updated If block
        if modified and new_body_stmts:
            new_body = updated_node.body.with_changes(body=new_body_stmts)
            return updated_node.with_changes(body=new_body)

        return updated_node

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.Call:
        """Transform print() and traceback.print_exc() calls to logger calls."""
        # Skip if inside debug guard (handled by leave_If)
        if self.in_debug_guard:
            return updated_node

        # 1. Handle print() -> logger.level()
        if m.matches(updated_node.func, m.Name("print")):
            new_call = self._convert_print_to_logger(updated_node)
            if new_call:
                return new_call

        # 2. Handle traceback.print_exc() -> logger.exception("")
        # This captures the current exception with full stack trace
        if m.matches(
            updated_node.func,
            m.Attribute(value=m.Name("traceback"), attr=m.Name("print_exc")),
        ):
            self.needs_logger_import = True
            self.needs_traceback_cleanup = True
            self.transform_count += 1

            return cst.Call(
                func=cst.Attribute(
                    value=cst.Name("logger"),
                    attr=cst.Name("exception"),
                ),
                args=[cst.Arg(cst.SimpleString('""'))],
            )

        return updated_node

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        """Add loguru import and clean up obsolete imports."""
        if self.needs_logger_import:
            AddImportsVisitor.add_needed_import(
                self.context,
                "theauditor.utils.logging",
                "logger",
            )

        # CLEANUP: Remove traceback import if we converted all print_exc() calls
        # Note: This is conservative - only removes traceback, not sys/os which
        # are commonly used for other things (sys.exit, os.path, etc.)
        if self.needs_traceback_cleanup:
            RemoveImportsVisitor.remove_unused_import(self.context, "traceback")

        return updated_node


# =============================================================================
# Standalone Runner - No yaml/init required
# =============================================================================

DEFAULT_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
    ".pf",
    ".auditor_venv",
}

FILE_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


def safe_print(text: str) -> None:
    """Print text safely, replacing non-encodable characters for Windows CP1252."""
    try:
        print(text)
    except UnicodeEncodeError:
        safe_text = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_text)


def read_file_with_fallback(filepath: str) -> tuple[str, str]:
    """Read file trying multiple encodings. Returns (content, encoding_used)."""
    last_error = None
    for encoding in FILE_ENCODINGS:
        try:
            with open(filepath, encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError as e:
            last_error = e
    raise UnicodeDecodeError(
        "all", b"", 0, 0, f"Failed to decode {filepath} with any of: {FILE_ENCODINGS}"
    )


def transform_file(file_path: str, dry_run: bool = False) -> tuple[str, int]:
    """Transform a single file. Returns (new_code, transformation_count)."""
    import sys

    try:
        source, encoding = read_file_with_fallback(file_path)
    except UnicodeDecodeError as e:
        safe_print(f"[ERROR] Encoding error in {file_path}: {e}")
        return "", 0

    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        safe_print(f"[ERROR] Syntax error in {file_path}: {e}")
        return source, 0

    context = CodemodContext()
    transformer = PrintToLoguruCodemod(context)

    try:
        modified = module.visit(transformer)
    except Exception as e:
        safe_print(f"[ERROR] Transform failed for {file_path}: {e}")
        return source, 0

    # Get actual transformation count from the transformer
    transform_count = transformer.transform_count

    # Apply import changes manually (this is why we don't need the CLI)
    if transformer.needs_logger_import:
        AddImportsVisitor.add_needed_import(
            context, "theauditor.utils.logging", "logger"
        )
        modified = AddImportsVisitor(context).transform_module(modified)

    # Validate generated code is syntactically correct
    if transform_count > 0:
        try:
            compile(modified.code, file_path, "exec")
        except SyntaxError as e:
            safe_print(f"[CRITICAL] Generated invalid code for {file_path}: {e}")
            safe_print(f"[CRITICAL] Original file preserved - not modified")
            return source, 0

    # Write if changed and not dry run
    if not dry_run and transform_count > 0:
        if not module.deep_equals(modified):
            with open(file_path, "w", encoding=encoding, newline="") as f:
                f.write(modified.code)

    return modified.code, transform_count


def process_directory(
    directory: str, skip_dirs: set[str], dry_run: bool = False
) -> tuple[int, int]:
    """Walk directory and transform all Python files. Returns (files_modified, total_transforms)."""
    import os

    files_modified = 0
    total_transforms = 0

    for root, dirs, files in os.walk(directory):
        # Filter out skip directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file).replace("\\", "/")
                _, count = transform_file(filepath, dry_run=dry_run)

                if count > 0:
                    files_modified += 1
                    total_transforms += count
                    mode = "[DRY-RUN]" if dry_run else "[OK]"
                    safe_print(f"  {mode} {filepath}")

    return files_modified, total_transforms


def main():
    """CLI entry point for standalone usage."""
    import argparse
    import os
    import sys

    parser = argparse.ArgumentParser(
        description="Migrate print('[TAG]...') to loguru logger calls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run on directory
  python scripts/loguru_migration.py theauditor/ --dry-run

  # Apply to single file
  python scripts/loguru_migration.py theauditor/taint/core.py

  # Show diff for changes
  python scripts/loguru_migration.py theauditor/taint/core.py --dry-run --diff

Tag-to-Level Mapping:
  [DEBUG], [TRACE], [INDEXER_DEBUG], [DEDUP], [SCHEMA] -> debug
  [INFO], [Indexer], [TAINT], [FCE], [GRAPH], [RULES]  -> info
  [WARNING], [WARN]                                    -> warning
  [ERROR]                                              -> error
  [CRITICAL], [FATAL]                                  -> critical
""",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to transform")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--diff", action="store_true", help="Show unified diff of changes"
    )
    parser.add_argument(
        "--skip",
        type=str,
        default="",
        help="Additional directories to skip (comma-separated)",
    )

    args = parser.parse_args()

    skip_dirs = DEFAULT_SKIP_DIRS.copy()
    if args.skip:
        for d in args.skip.split(","):
            skip_dirs.add(d.strip())

    total_files = 0
    total_transforms = 0

    mode_str = "[DRY RUN] " if args.dry_run else ""
    safe_print(f"{mode_str}Loguru Migration - print('[TAG]...') -> logger.level()")
    safe_print("=" * 60)

    for path in args.paths:
        if os.path.isdir(path):
            safe_print(f"\nProcessing directory: {path}")
            files, transforms = process_directory(path, skip_dirs, dry_run=args.dry_run)
            total_files += files
            total_transforms += transforms
        elif os.path.isfile(path):
            if not path.endswith(".py"):
                safe_print(f"[SKIP] Not a Python file: {path}")
                continue

            with open(path, "r", encoding="utf-8") as f:
                original = f.read()

            new_code, count = transform_file(path, dry_run=args.dry_run)

            if count > 0:
                total_files += 1
                total_transforms += count
                mode = "[DRY-RUN]" if args.dry_run else "[OK]"
                safe_print(f"  {mode} {path}")

                if args.diff and original != new_code:
                    import difflib

                    diff = difflib.unified_diff(
                        original.splitlines(keepends=True),
                        new_code.splitlines(keepends=True),
                        fromfile=f"a/{path}",
                        tofile=f"b/{path}",
                    )
                    print("".join(diff))
            else:
                safe_print(f"  [SKIP] {path}: no tagged prints found")
        else:
            safe_print(f"[ERROR] Path not found: {path}")

    safe_print("")
    safe_print("=" * 60)
    safe_print(f"{mode_str}COMPLETED")
    safe_print(f"Files modified: {total_files}")
    safe_print(f"Transformations: {total_transforms}")

    if args.dry_run:
        safe_print("\n[INFO] Dry run - no files were modified")


if __name__ == "__main__":
    main()
