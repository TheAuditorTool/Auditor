#!/usr/bin/env python3
"""
FileContext Migration Verifier Script
=====================================
Scans extractors BEFORE running ast_walk_to_filecontext.py to identify risks.

This script performs critical safety checks identified by Lead Auditor:
1. parser_self usage that would break after migration
2. Caller/dispatcher code that needs updating
3. Complex ast.walk patterns that might be missed
4. Variable name collisions with 'context'

Author: TheAuditor Team
Date: November 2025
"""

import ast
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# ============================================================================
# Risk Report Data Classes
# ============================================================================

@dataclass
class ExtractorInfo:
    """Information about an extractor function."""
    file_path: str
    function_name: str
    line_number: int
    uses_parser_self: bool = False
    parser_self_usages: list[str] = field(default_factory=list)
    has_complex_walk: bool = False
    complex_walk_patterns: list[str] = field(default_factory=list)
    has_context_variable: bool = False
    context_variable_lines: list[int] = field(default_factory=list)


@dataclass
class CallerInfo:
    """Information about code that calls extractors."""
    file_path: str
    line_number: int
    call_pattern: str
    extractor_name: str


@dataclass
class VerificationReport:
    """Complete verification report."""
    extractors: list[ExtractorInfo] = field(default_factory=list)
    callers: list[CallerInfo] = field(default_factory=list)
    parser_self_files: set[str] = field(default_factory=set)
    complex_walk_files: set[str] = field(default_factory=set)
    context_collision_files: set[str] = field(default_factory=set)

    # Statistics
    total_extractors: int = 0
    extractors_using_parser_self: int = 0
    extractors_with_complex_walks: int = 0
    extractors_with_context_collision: int = 0
    total_callers: int = 0

    def has_blockers(self) -> bool:
        """Check if there are critical blockers."""
        return bool(self.parser_self_files or self.context_collision_files)

    def print_summary(self):
        """Print a formatted summary of the verification."""
        print("\n" + "="*80)
        print("FILECONTEXT MIGRATION VERIFICATION REPORT")
        print("="*80)

        # Statistics
        print("\nSTATISTICS:")
        print(f"  Total extractors found: {self.total_extractors}")
        print(f"  Using parser_self: {self.extractors_using_parser_self}")
        print(f"  With complex ast.walk patterns: {self.extractors_with_complex_walks}")
        print(f"  With 'context' variable collisions: {self.extractors_with_context_collision}")
        print(f"  Caller locations found: {self.total_callers}")

        # Critical Blockers
        if self.has_blockers():
            print("\n[CRITICAL BLOCKERS FOUND]:")

            if self.parser_self_files:
                print("\n[X] parser_self Usage (MUST FIX):")
                for ext in self.extractors:
                    if ext.uses_parser_self:
                        print(f"\n  File: {ext.file_path}")
                        print(f"  Function: {ext.function_name} (line {ext.line_number})")
                        print("  Usages:")
                        for usage in ext.parser_self_usages[:5]:  # Show first 5
                            print(f"    - {usage}")
                        if len(ext.parser_self_usages) > 5:
                            print(f"    ... and {len(ext.parser_self_usages)-5} more")

            if self.context_collision_files:
                print("\n[X] 'context' Variable Collisions (MUST FIX):")
                for ext in self.extractors:
                    if ext.has_context_variable:
                        print(f"\n  File: {ext.file_path}")
                        print(f"  Function: {ext.function_name}")
                        print(f"  Lines with 'context =': {ext.context_variable_lines}")

        # Warnings
        if self.complex_walk_files:
            print("\n[WARNING] Script may miss these:")
            print("\nComplex ast.walk patterns:")
            for ext in self.extractors:
                if ext.has_complex_walk:
                    print(f"\n  File: {ext.file_path}")
                    print(f"  Function: {ext.function_name}")
                    for pattern in ext.complex_walk_patterns[:3]:
                        print(f"    - {pattern}")

        # Caller Updates Required
        if self.callers:
            print("\n[MANUAL UPDATES REQUIRED]:")
            print("\nCaller/Dispatcher locations that need FileContext update:")

            # Group by file
            callers_by_file = defaultdict(list)
            for caller in self.callers:
                callers_by_file[caller.file_path].append(caller)

            for file_path, file_callers in callers_by_file.items():
                print(f"\n  File: {file_path}")
                for caller in file_callers[:5]:  # Show first 5 per file
                    print(f"    Line {caller.line_number}: {caller.call_pattern}")
                    print(f"      -> Calling: {caller.extractor_name}")
                if len(file_callers) > 5:
                    print(f"    ... and {len(file_callers)-5} more calls")

        # Final verdict
        print("\n" + "="*80)
        if self.has_blockers():
            print("[FAIL] VERDICT: DO NOT RUN MIGRATION - Critical blockers found!")
            print("\nFix these issues first:")
            if self.parser_self_files:
                print("  1. Remove parser_self dependencies or add to FileContext")
            if self.context_collision_files:
                print("  2. Rename 'context' variables in extractors")
        else:
            print("[PASS] VERDICT: Safe to proceed with migration")
            print("\nRemember to:")
            print("  1. Run with --create-modules first")
            print("  2. Test on single file first")
            print("  3. Update caller code immediately after migration")
            if self.complex_walk_files:
                print("  4. Manually verify complex ast.walk patterns")
        print("="*80)


# ============================================================================
# AST Analysis Visitors
# ============================================================================

class ExtractorAnalyzer(ast.NodeVisitor):
    """Analyze an extractor function for risks."""

    def __init__(self, function_name: str):
        self.function_name = function_name
        self.parser_self_usages = []
        self.complex_walks = []
        self.context_assignments = []
        self.current_line = 0

    def visit_Name(self, node: ast.Name):
        """Check for parser_self usage."""
        if node.id == "parser_self":
            # Get context of usage
            line = getattr(node, 'lineno', self.current_line)
            # Try to get the full expression context
            usage = f"Line {line}: parser_self"
            self.parser_self_usages.append(usage)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        """Check for parser_self.attribute usage."""
        if isinstance(node.value, ast.Name) and node.value.id == "parser_self":
            line = getattr(node, 'lineno', self.current_line)
            usage = f"Line {line}: parser_self.{node.attr}"
            self.parser_self_usages.append(usage)
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        """Check for complex ast.walk patterns."""
        self.current_line = getattr(node, 'lineno', 0)

        # Check if this is an ast.walk loop
        if (isinstance(node.iter, ast.Call) and
            isinstance(node.iter.func, ast.Attribute) and
            node.iter.func.attr == "walk" and
            isinstance(node.iter.func.value, ast.Name) and
            node.iter.func.value.id == "ast"):

            # Check for complex patterns
            body = node.body
            if body:
                first_stmt = body[0]

                # Pattern 1: Logic before isinstance
                if not isinstance(first_stmt, ast.If):
                    pattern = f"Line {self.current_line}: ast.walk with logic before isinstance check"
                    self.complex_walks.append(pattern)

                # Pattern 2: isinstance not as first statement
                elif isinstance(first_stmt, ast.If):
                    # Check if it's an isinstance check
                    test = first_stmt.test
                    if not (isinstance(test, ast.Call) and
                           isinstance(test.func, ast.Name) and
                           test.func.id == "isinstance"):
                        pattern = f"Line {self.current_line}: ast.walk with non-isinstance condition"
                        self.complex_walks.append(pattern)

                # Pattern 3: Nested ast.walk
                for child in ast.walk(node):
                    if (child != node and isinstance(child, ast.For) and
                        isinstance(child.iter, ast.Call) and
                        isinstance(child.iter.func, ast.Attribute) and
                        child.iter.func.attr == "walk"):
                        pattern = f"Line {self.current_line}: Nested ast.walk loops"
                        self.complex_walks.append(pattern)
                        break

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """Check for context = assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "context":
                line = getattr(node, 'lineno', 0)
                self.context_assignments.append(line)
        self.generic_visit(node)


class CallerFinder(ast.NodeVisitor):
    """Find locations where extractors are called."""

    def __init__(self, extractor_names: set[str]):
        self.extractor_names = extractor_names
        self.calls = []

    def visit_Call(self, node: ast.Call):
        """Find calls to extractors."""
        call_name = None

        # Direct function call: extract_functions(...)
        if isinstance(node.func, ast.Name):
            call_name = node.func.id

        # Method call: self.extract_functions(...)
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr

        # Check if it's an extractor
        if call_name and call_name in self.extractor_names:
            line = getattr(node, 'lineno', 0)

            # Check arguments to see if it matches (tree, parser_self) pattern
            if len(node.args) >= 2:
                # Likely a caller we need to update
                arg_pattern = self._get_arg_pattern(node)
                self.calls.append({
                    'line': line,
                    'name': call_name,
                    'pattern': arg_pattern
                })

        self.generic_visit(node)

    def _get_arg_pattern(self, call_node: ast.Call) -> str:
        """Get a string representation of the call pattern."""
        parts = []
        for arg in call_node.args[:2]:  # First 2 args
            if isinstance(arg, ast.Name):
                parts.append(arg.id)
            else:
                parts.append("...")
        return f"({', '.join(parts)})"


# ============================================================================
# File Processing Functions
# ============================================================================

def analyze_extractor_file(file_path: Path, report: VerificationReport) -> None:
    """Analyze a single Python file for extractors."""

    try:
        with open(file_path, encoding='utf-8') as f:
            source_code = f.read()

        # Parse the AST
        try:
            tree = ast.parse(source_code, filename=str(file_path))
        except SyntaxError:
            print(f"  Warning: Could not parse {file_path}")
            return

        # Find all extractor functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name

                # Check if it's an extractor
                if func_name.startswith("extract_"):
                    # Check parameters match expected pattern
                    params = node.args.args
                    if len(params) >= 2:
                        param_names = [p.arg for p in params[:2]]
                        if param_names == ["tree", "parser_self"]:
                            # This is an extractor
                            report.total_extractors += 1

                            # Analyze the function
                            analyzer = ExtractorAnalyzer(func_name)
                            analyzer.visit(node)

                            # Create ExtractorInfo
                            info = ExtractorInfo(
                                file_path=str(file_path),
                                function_name=func_name,
                                line_number=getattr(node, 'lineno', 0),
                                uses_parser_self=bool(analyzer.parser_self_usages),
                                parser_self_usages=analyzer.parser_self_usages,
                                has_complex_walk=bool(analyzer.complex_walks),
                                complex_walk_patterns=analyzer.complex_walks,
                                has_context_variable=bool(analyzer.context_assignments),
                                context_variable_lines=analyzer.context_assignments
                            )

                            report.extractors.append(info)

                            # Update statistics
                            if info.uses_parser_self:
                                report.extractors_using_parser_self += 1
                                report.parser_self_files.add(str(file_path))

                            if info.has_complex_walk:
                                report.extractors_with_complex_walks += 1
                                report.complex_walk_files.add(str(file_path))

                            if info.has_context_variable:
                                report.extractors_with_context_collision += 1
                                report.context_collision_files.add(str(file_path))

    except Exception as e:
        print(f"  Error analyzing {file_path}: {e}")


def find_extractor_callers(root_dir: Path, extractor_names: set[str],
                           report: VerificationReport) -> None:
    """Find all locations where extractors are called."""

    # Common locations for dispatcher/router code
    search_paths = [
        root_dir / "indexer" / "extractors",
        root_dir / "indexer",
        root_dir / "ast_extractors",
        root_dir,
    ]

    processed_files = set()

    for search_path in search_paths:
        if not search_path.exists():
            continue

        # Find Python files
        for py_file in search_path.rglob("*.py"):
            # Skip test files and backups
            if ('test' in py_file.name.lower() or
                py_file.name.endswith('.bak') or
                str(py_file) in processed_files):
                continue

            processed_files.add(str(py_file))

            try:
                with open(py_file, encoding='utf-8') as f:
                    source_code = f.read()

                # Quick check if any extractor names are mentioned
                has_extractor = any(name in source_code for name in extractor_names)
                if not has_extractor:
                    continue

                # Parse and analyze
                try:
                    tree = ast.parse(source_code, filename=str(py_file))
                    finder = CallerFinder(extractor_names)
                    finder.visit(tree)

                    # Add findings to report
                    for call in finder.calls:
                        caller = CallerInfo(
                            file_path=str(py_file),
                            line_number=call['line'],
                            call_pattern=call['pattern'],
                            extractor_name=call['name']
                        )
                        report.callers.append(caller)
                        report.total_callers += 1

                except SyntaxError:
                    pass

            except Exception:
                pass  # Silent fail for files we can't read


def verify_migration_readiness(target_dir: Path) -> VerificationReport:
    """Main verification function."""

    report = VerificationReport()

    print("\n[Phase 1] Analyzing extractor files...")

    # Find all Python files in target directory
    if target_dir.is_file():
        python_files = [target_dir]
    else:
        python_files = list(target_dir.glob("*.py"))
        # Filter out non-extractor files
        python_files = [f for f in python_files
                        if not f.name.startswith("__")
                        and not f.name.endswith(".bak")]

    print(f"  Found {len(python_files)} Python files to analyze")

    # Analyze each file
    for py_file in sorted(python_files):
        analyze_extractor_file(py_file, report)

    # Collect all extractor names
    extractor_names = {ext.function_name for ext in report.extractors}

    print(f"  Found {len(extractor_names)} extractor functions")

    print("\n[Phase 2] Finding caller/dispatcher code...")

    # Find root of project (go up from target_dir until we find theauditor)
    root_dir = target_dir
    while root_dir.parent != root_dir:
        if (root_dir / "theauditor").exists():
            root_dir = root_dir / "theauditor"
            break
        root_dir = root_dir.parent

    find_extractor_callers(root_dir, extractor_names, report)

    print(f"  Found {report.total_callers} caller locations")

    return report


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the verifier."""

    print("="*80)
    print("FILECONTEXT MIGRATION VERIFIER")
    print("="*80)
    print("This script checks for risks BEFORE running ast_walk_to_filecontext.py")
    print("="*80)

    # Default target directory
    target_dir = Path("./theauditor/ast_extractors/python/")

    # Allow command line override
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])

    if not target_dir.exists():
        print(f"\n[ERROR] Target directory does not exist: {target_dir}")
        print("\nUsage: python verify_filecontext_migration.py [target_dir]")
        sys.exit(1)

    print(f"\nTarget directory: {target_dir}")
    print("\nRunning verification...")

    # Run verification
    report = verify_migration_readiness(target_dir)

    # Print report
    report.print_summary()

    # Exit with appropriate code
    if report.has_blockers():
        sys.exit(1)  # Exit with error if blockers found
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
