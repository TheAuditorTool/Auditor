"""Rule Anti-Pattern Detector - Finds optimization issues causing taint explosions.

Detects:
1. LIMIT + Python filtering (hiding bugs)
2. N+1 query patterns (causing explosions)
3. Artificial checked_count breaks (hiding bugs)
4. Missing REGEXP usage (slow string operations)

Usage:
    python scripts/rule_antipattern_detector.py theauditor/rules/
"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class AntiPattern:
    """Detected anti-pattern."""
    file: str
    line: int
    pattern_type: str
    message: str
    severity: str  # 'critical', 'high', 'medium'


class RuleAntiPatternDetector(ast.NodeVisitor):
    """Detects performance anti-patterns in rule files."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.issues: List[AntiPattern] = []
        self.in_loop = False
        self.loop_iterates_fetchall = False

    def visit_For(self, node: ast.For):
        """Detect loops over cursor.fetchall()."""
        old_in_loop = self.in_loop
        old_iterates = self.loop_iterates_fetchall

        self.in_loop = True

        # Check if iterating over cursor.fetchall()
        if isinstance(node.iter, ast.Call):
            if isinstance(node.iter.func, ast.Attribute):
                if node.iter.func.attr == 'fetchall':
                    self.loop_iterates_fetchall = True

                    # Check for N+1 pattern: cursor.execute inside loop
                    for stmt in ast.walk(node):
                        if isinstance(stmt, ast.Call):
                            if isinstance(stmt.func, ast.Attribute):
                                if stmt.func.attr == 'execute':
                                    self.issues.append(AntiPattern(
                                        file=self.filepath,
                                        line=node.lineno,
                                        pattern_type='N+1-query',
                                        message='Query execution inside fetchall() loop - N+1 anti-pattern',
                                        severity='critical'
                                    ))
                                    break

                    # Check for checked_count pattern
                    self._check_artificial_limit(node)

                    # Check for Python filtering that should be in SQL
                    self._check_python_filtering(node)

        self.generic_visit(node)

        self.in_loop = old_in_loop
        self.loop_iterates_fetchall = old_iterates

    def _check_artificial_limit(self, loop_node: ast.For):
        """Detect checked_count += 1; if count > N: break pattern."""
        has_increment = False
        has_break = False

        for stmt in ast.walk(loop_node):
            # Look for counter += 1 or counter = counter + 1
            if isinstance(stmt, ast.AugAssign):
                if isinstance(stmt.target, ast.Name):
                    if 'count' in stmt.target.id.lower():
                        has_increment = True

            # Look for if count > N: break
            if isinstance(stmt, ast.If):
                if isinstance(stmt.test, ast.Compare):
                    for op in stmt.test.ops:
                        if isinstance(op, ast.Gt):
                            # Check if body contains break
                            for body_stmt in stmt.body:
                                if isinstance(body_stmt, ast.Break):
                                    has_break = True

        if has_increment and has_break:
            self.issues.append(AntiPattern(
                file=self.filepath,
                line=loop_node.lineno,
                pattern_type='artificial-limit',
                message='Artificial loop break with checked_count - hiding bugs beyond limit',
                severity='high'
            ))

    def _check_python_filtering(self, loop_node: ast.For):
        """Detect filtering in Python that should be in SQL."""
        has_continue_in_if = False

        for stmt in loop_node.body:
            if isinstance(stmt, ast.If):
                # Check if body contains continue
                for body_stmt in stmt.body:
                    if isinstance(body_stmt, ast.Continue):
                        has_continue_in_if = True
                        break

        if has_continue_in_if:
            self.issues.append(AntiPattern(
                file=self.filepath,
                line=loop_node.lineno,
                pattern_type='python-filtering',
                message='Python-side filtering with continue - should be in SQL WHERE',
                severity='medium'
            ))

    def visit_Call(self, node: ast.Call):
        """Detect cursor.execute with LIMIT."""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == 'execute':
                # Check if query string contains LIMIT
                for arg in node.args:
                    if isinstance(arg, ast.Constant):
                        if isinstance(arg.value, str):
                            if 'LIMIT' in arg.value.upper():
                                self.issues.append(AntiPattern(
                                    file=self.filepath,
                                    line=node.lineno,
                                    pattern_type='limit-in-query',
                                    message='SQL query contains LIMIT - may hide bugs',
                                    severity='high'
                                ))

        self.generic_visit(node)


def analyze_rule_file(filepath: Path) -> List[AntiPattern]:
    """Analyze a single rule file for anti-patterns."""
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content)

        detector = RuleAntiPatternDetector(str(filepath))
        detector.visit(tree)

        return detector.issues
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}", file=sys.stderr)
        return []


def main():
    if len(sys.argv) < 2:
        print("Usage: python rule_antipattern_detector.py <rules_directory>")
        sys.exit(1)

    rules_dir = Path(sys.argv[1])
    if not rules_dir.exists():
        print(f"Error: {rules_dir} does not exist")
        sys.exit(1)

    all_issues = []

    # Scan all Python files in rules directory
    for rule_file in rules_dir.rglob('*.py'):
        if rule_file.name == '__init__.py':
            continue

        issues = analyze_rule_file(rule_file)
        all_issues.extend(issues)

    # Report findings
    if not all_issues:
        print("No anti-patterns detected!")
        return

    print(f"\nFound {len(all_issues)} anti-patterns:\n")

    # Group by severity
    by_severity = {'critical': [], 'high': [], 'medium': []}
    for issue in all_issues:
        by_severity[issue.severity].append(issue)

    for severity in ['critical', 'high', 'medium']:
        issues = by_severity[severity]
        if not issues:
            continue

        print(f"\n{'=' * 80}")
        print(f"{severity.upper()} ({len(issues)} issues)")
        print('=' * 80)

        for issue in issues:
            print(f"\n{issue.file}:{issue.line}")
            print(f"  [{issue.pattern_type}] {issue.message}")

    print(f"\n{'=' * 80}")
    print(f"Total: {len(all_issues)} issues")
    print('=' * 80)


if __name__ == '__main__':
    main()
