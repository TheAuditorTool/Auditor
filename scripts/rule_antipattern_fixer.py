"""Rule Anti-Pattern Auto-Fixer - LibCST-based codemod for fixing taint-explosion patterns.

Fixes:
1. REMOVES checked_count breaks (hiding bugs beyond limit)
2. REMOVES LIMIT clauses from SQL strings (hiding bugs)
3. ADDS TODO comments for N+1 patterns (need manual JOIN rewrite)
4. ADDS TODO comments for Python filtering (needs WHERE clause migration)

Based on libcst_faq.md best practices (LibCST 1.8.6).

Usage (DRY RUN - shows diff only):
    python -m libcst.tool codemod scripts.rule_antipattern_fixer.RuleAntiPatternFixer \
        --no-format \
        theauditor/rules/sql/

Usage (APPLY CHANGES):
    python -m libcst.tool codemod scripts.rule_antipattern_fixer.RuleAntiPatternFixer \
        theauditor/rules/sql/

WARNING: Review diff carefully before applying. Some fixes may need manual adjustment.
"""

import re

import libcst as cst
from libcst.codemod import CodemodContext, SkipFile, VisitorBasedCodemodCommand


class RuleAntiPatternFixer(VisitorBasedCodemodCommand):
    """Auto-fix anti-patterns that cause taint analysis explosions."""

    DESCRIPTION = "Fix checked_count breaks, LIMIT clauses, and flag N+1 patterns"

    # Strict pattern for counter variables (not just any *count*)
    COUNTER_NAMES = frozenset([
        'checked_count', 'check_count', 'processed_count',
        'iteration_count', 'loop_count', 'item_count'
    ])

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.inside_for_loop = False

    def visit_Module(self, node: cst.Module) -> None:
        """Skip non-rule files."""
        filename = self.context.filename or ""
        if not filename.endswith("_analyze.py"):
            raise SkipFile("Not an analyzer rule file")

    # =========================================================================
    # FIX 1: Remove checked_count breaks
    # Pattern: checked_count += 1; if checked_count > N: break
    # =========================================================================

    def leave_For(
        self, original_node: cst.For, updated_node: cst.For
    ) -> cst.For:
        """Remove checked_count logic and add N+1/filtering TODOs."""
        # Only process loops that iterate over fetchall()
        if not self._iterates_over_fetchall(updated_node):
            return updated_node

        # Track what we find and fix
        removed_counter = False
        has_n_plus_one = False
        has_python_filter = False
        new_body_stmts = []

        for stmt in updated_node.body.body:
            # Skip: checked_count = 0 (initialization)
            if self._is_counter_init(stmt):
                removed_counter = True
                continue

            # Skip: checked_count += 1
            if self._is_counter_increment(stmt):
                removed_counter = True
                continue

            # Skip: if checked_count > N: break
            if self._is_counter_break(stmt):
                removed_counter = True
                continue

            # Detect N+1: cursor.execute inside loop
            if self._is_cursor_execute(stmt):
                has_n_plus_one = True

            # Detect Python filtering: if condition: continue
            if self._is_python_filter(stmt):
                has_python_filter = True

            new_body_stmts.append(stmt)

        # Build comments for fixes applied
        comments_to_add = []

        if removed_counter:
            comments_to_add.append(
                "# FIXED: Removed checked_count break - was hiding bugs beyond limit"
            )

        if has_n_plus_one:
            comments_to_add.append(
                "# TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop"
            )
            comments_to_add.append(
                "#       Rewrite with JOIN or CTE to eliminate per-row queries"
            )

        if has_python_filter:
            comments_to_add.append(
                "# TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found"
            )
            comments_to_add.append(
                "#       Move filtering logic to SQL WHERE clause for efficiency"
            )

        # Apply comments if any fixes/detections occurred
        if comments_to_add and new_body_stmts:
            first_stmt = new_body_stmts[0]

            # Build EmptyLine nodes for each comment
            comment_lines = []
            for comment_text in comments_to_add:
                comment_lines.append(
                    cst.EmptyLine(comment=cst.Comment(value=comment_text))
                )

            # Add comments to first statement's leading lines
            if hasattr(first_stmt, 'leading_lines'):
                new_leading = list(first_stmt.leading_lines) + comment_lines
                new_body_stmts[0] = first_stmt.with_changes(
                    leading_lines=new_leading
                )

            new_body = updated_node.body.with_changes(body=new_body_stmts)
            return updated_node.with_changes(body=new_body)

        # If only counter removed but no body changes needed
        if removed_counter:
            new_body = updated_node.body.with_changes(body=new_body_stmts)
            return updated_node.with_changes(body=new_body)

        return updated_node

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        """Remove checked_count = 0 initializations before loops."""
        if len(updated_node.body) == 1:
            stmt = updated_node.body[0]
            if isinstance(stmt, cst.Assign):
                for target in stmt.targets:
                    if isinstance(target.target, cst.Name):
                        var_name = target.target.value.lower()
                        # Strict matching - only known counter patterns
                        if (var_name in self.COUNTER_NAMES and isinstance(stmt.value, cst.Integer) and
                            stmt.value.value == '0'):
                            return cst.RemovalSentinel.REMOVE

        return updated_node

    # =========================================================================
    # FIX 2: Remove LIMIT from SQL strings
    # Pattern: cursor.execute("SELECT ... LIMIT N")
    # Handles: SimpleString ("..."), FormattedString (f"..."), ConcatenatedString ("""...""")
    # =========================================================================

    def _remove_limit_from_sql(self, value: str) -> tuple[str, bool]:
        """Remove LIMIT clause from SQL string. Returns (new_value, was_modified)."""
        # Check if it's a SQL string with LIMIT
        if not ('SELECT' in value.upper() or 'UPDATE' in value.upper() or 'DELETE' in value.upper()):
            return value, False

        if 'LIMIT' not in value.upper():
            return value, False

        # Remove LIMIT N pattern (handles LIMIT 15, LIMIT 30, etc.)
        new_value = re.sub(
            r'\s+LIMIT\s+\d+',
            '\n        -- REMOVED LIMIT: was hiding bugs\n        ',
            value,
            flags=re.IGNORECASE
        )

        return new_value, (new_value != value)

    def leave_SimpleString(
        self, original_node: cst.SimpleString, updated_node: cst.SimpleString
    ) -> cst.SimpleString:
        """Remove LIMIT clauses from simple SQL query strings."""
        new_value, modified = self._remove_limit_from_sql(updated_node.value)
        if modified:
            return updated_node.with_changes(value=new_value)
        return updated_node

    def leave_FormattedStringText(
        self, original_node: cst.FormattedStringText, updated_node: cst.FormattedStringText
    ) -> cst.FormattedStringText:
        """Remove LIMIT clauses from f-string SQL queries."""
        new_value, modified = self._remove_limit_from_sql(updated_node.value)
        if modified:
            return updated_node.with_changes(value=new_value)
        return updated_node

    def leave_ConcatenatedString(
        self, original_node: cst.ConcatenatedString, updated_node: cst.ConcatenatedString
    ) -> cst.ConcatenatedString:
        """Remove LIMIT clauses from concatenated/triple-quoted SQL strings."""
        new_parts = []
        modified = False

        for part in updated_node.left, updated_node.right:
            if isinstance(part, cst.SimpleString):
                new_value, part_modified = self._remove_limit_from_sql(part.value)
                if part_modified:
                    modified = True
                    new_parts.append(part.with_changes(value=new_value))
                else:
                    new_parts.append(part)
            else:
                new_parts.append(part)

        if modified:
            return updated_node.with_changes(left=new_parts[0], right=new_parts[1])
        return updated_node

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _iterates_over_fetchall(self, node: cst.For) -> bool:
        """Check if for loop iterates over cursor.fetchall()."""
        if isinstance(node.iter, cst.Call) and isinstance(node.iter.func, cst.Attribute):
            return node.iter.func.attr.value == 'fetchall'
        return False

    def _is_counter_init(self, stmt: cst.BaseStatement) -> bool:
        """Check if statement is: checked_count = 0 or similar."""
        if isinstance(stmt, cst.SimpleStatementLine):
            for inner in stmt.body:
                if isinstance(inner, cst.Assign):
                    for target in inner.targets:
                        if isinstance(target.target, cst.Name):
                            var_name = target.target.value.lower()
                            if var_name in self.COUNTER_NAMES and isinstance(inner.value, cst.Integer):
                                return inner.value.value == '0'
        return False

    def _is_counter_increment(self, stmt: cst.BaseStatement) -> bool:
        """Check if statement is: checked_count += 1 or similar."""
        if isinstance(stmt, cst.SimpleStatementLine):
            for inner in stmt.body:
                if isinstance(inner, cst.AugAssign) and isinstance(inner.target, cst.Name):
                    var_name = inner.target.value.lower()
                    if var_name in self.COUNTER_NAMES and isinstance(inner.operator, cst.AddAssign):
                        return True
        return False

    def _is_counter_break(self, stmt: cst.BaseStatement) -> bool:
        """Check if statement is: if checked_count > N: break."""
        if isinstance(stmt, cst.If) and isinstance(stmt.test, cst.Comparison):
            # Check if test is comparison with counter
            left = stmt.test.left
            if isinstance(left, cst.Name):
                var_name = left.value.lower()
                if var_name in self.COUNTER_NAMES:
                    # Check if body contains break
                    for body_stmt in stmt.body.body:
                        if isinstance(body_stmt, cst.SimpleStatementLine):
                            for inner in body_stmt.body:
                                if isinstance(inner, cst.Break):
                                    return True
        return False

    def _is_cursor_execute(self, stmt: cst.BaseStatement) -> bool:
        """Check if statement contains cursor.execute()."""
        if isinstance(stmt, cst.SimpleStatementLine):
            for inner in stmt.body:
                if (isinstance(inner, cst.Expr) and isinstance(inner.value, cst.Call) and
                    isinstance(inner.value.func, cst.Attribute)):
                    return inner.value.func.attr.value == 'execute'
        return False

    def _is_python_filter(self, stmt: cst.BaseStatement) -> bool:
        """Check if statement is Python filtering: if condition: continue."""
        if isinstance(stmt, cst.If):
            # Check if body contains continue (filtering pattern)
            for body_stmt in stmt.body.body:
                if isinstance(body_stmt, cst.SimpleStatementLine):
                    for inner in body_stmt.body:
                        if isinstance(inner, cst.Continue):
                            return True
        return False


# =========================================================================
# Standalone Script Mode
# =========================================================================

def transform_file(file_path: str) -> bool:
    """Transform a single file. Returns True if file was modified."""
    from pathlib import Path

    path = Path(file_path)
    source = path.read_text(encoding='utf-8')

    try:
        module = cst.parse_module(source)
    except Exception as e:
        print(f"  ERROR parsing {file_path}: {e}")
        return False

    context = CodemodContext(filename=file_path)

    try:
        transformer = RuleAntiPatternFixer(context)
        modified = module.visit(transformer)
    except SkipFile as e:
        print(f"  SKIP {file_path}: {e}")
        return False

    # Only write if changed
    if not module.deep_equals(modified):
        path.write_text(modified.code, encoding='utf-8')
        print(f"  FIXED {file_path}")
        return True
    else:
        print(f"  OK {file_path} (no changes needed)")
        return False


def main():
    """Run as standalone script."""
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python rule_antipattern_fixer.py <rules_directory>")
        print("       python -m libcst.tool codemod scripts.rule_antipattern_fixer.RuleAntiPatternFixer <path>")
        sys.exit(1)

    rules_dir = Path(sys.argv[1])
    if not rules_dir.exists():
        print(f"Error: {rules_dir} does not exist")
        sys.exit(1)

    print(f"Scanning {rules_dir} for anti-patterns...\n")

    modified_count = 0
    total_count = 0

    for rule_file in rules_dir.rglob('*_analyze.py'):
        total_count += 1
        if transform_file(str(rule_file)):
            modified_count += 1

    print(f"\nSummary: {modified_count}/{total_count} files modified")


if __name__ == '__main__':
    main()
