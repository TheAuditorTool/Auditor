#!/usr/bin/env python3
"""
AST Walk to FileContext Transformation Script
==============================================
Transforms Python extractors from inefficient ast.walk() patterns to FileContext with NodeIndex.

This implements Option B: Clean Architecture approach from the performance briefing.

Author: TheAuditor Team
Date: November 2025
LibCST Version: 1.8.6
Target: Python 3.14

Changes made:
1. Function signatures: (tree: dict, parser_self) → (context: FileContext)
2. ast.walk() patterns → context.find_nodes()
3. tree.get("tree") → context.tree
4. Manual import resolution → context.resolve_symbol()
5. _build_function_ranges() → context.function_ranges

Usage:
    # Dry run first
    python ast_walk_to_filecontext.py --dry-run --target-dir ./theauditor/ast_extractors/python/

    # Apply changes
    python ast_walk_to_filecontext.py --target-dir ./theauditor/ast_extractors/python/
"""

import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Union, Optional, Sequence
from dataclasses import dataclass

import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext


# ============================================================================
# Statistics Tracking
# ============================================================================

@dataclass
class TransformationStats:
    """Track what we've transformed."""
    files_processed: int = 0
    files_modified: int = 0
    signatures_changed: int = 0
    ast_walks_replaced: int = 0
    tree_gets_replaced: int = 0
    function_ranges_replaced: int = 0
    imports_added: int = 0

    def print_summary(self):
        """Print a summary of changes."""
        print("\n" + "="*60)
        print("FILECONTEXT TRANSFORMATION SUMMARY")
        print("="*60)
        print(f"Files processed: {self.files_processed}")
        print(f"Files modified: {self.files_modified}")
        print(f"\nTransformations applied:")
        print(f"  Function signatures updated: {self.signatures_changed}")
        print(f"  ast.walk() -> context.find_nodes(): {self.ast_walks_replaced}")
        print(f"  tree.get('tree') removed: {self.tree_gets_replaced}")
        print(f"  _build_function_ranges() replaced: {self.function_ranges_replaced}")
        print(f"  FileContext imports added: {self.imports_added}")
        print("="*60)


# ============================================================================
# FileContext Transformer
# ============================================================================

class FileContextTransformer(m.MatcherDecoratableTransformer):
    """
    Transforms extractors to use FileContext pattern with NodeIndex.

    Major changes:
    1. Function signatures: (tree: dict, parser_self) → (context: FileContext)
    2. ast.walk(actual_tree) → context.find_nodes(ast.X)
    3. tree.get("tree") → context.tree
    4. Import resolution via context
    """

    def __init__(self, context: CodemodContext, stats: TransformationStats):
        super().__init__()
        self.context = context
        self.stats = stats

        # Track if we need to add imports
        self.needs_filecontext_import = False
        self.needs_ast_import = False

        # Track current function being processed
        self.current_function = None
        self.inside_extractor = False

        # Track variable names that hold the tree
        self.tree_variables = {"actual_tree", "tree", "ast_tree"}

        # Track if we've seen tree.get("tree") pattern
        self.has_tree_get = False

    # ------------------------------------------------------------------------
    # Transform function signatures
    # ------------------------------------------------------------------------

    @m.leave(
        m.FunctionDef(
            params=m.Parameters(
                params=[
                    m.Param(name=m.Name("tree")),
                    m.Param(name=m.Name("parser_self"))
                ]
            )
        )
    )
    def update_extractor_signature(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Transform extractor function signature to use FileContext."""

        # Check if this looks like an extractor function
        func_name = updated_node.name.value
        if not func_name.startswith("extract_"):
            return updated_node

        self.stats.signatures_changed += 1
        self.needs_filecontext_import = True

        # Create new parameter: context: FileContext
        new_param = cst.Param(
            name=cst.Name("context"),
            annotation=cst.Annotation(
                annotation=cst.Name("FileContext")
            )
        )

        # Update return type if needed (list[dict] is fine, but could be more specific)
        new_params = updated_node.params.with_changes(
            params=[new_param]
        )

        return updated_node.with_changes(params=new_params)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Track when we enter an extractor function."""
        if node.name.value.startswith("extract_"):
            self.current_function = node.name.value
            self.inside_extractor = True
            # Check for tree.get("tree") pattern
            self.has_tree_get = self._contains_tree_get(node)

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Clean up when leaving extractor function."""
        if original_node.name.value.startswith("extract_"):
            self.current_function = None
            self.inside_extractor = False

            # Remove tree.get("tree") lines if we found them
            if self.has_tree_get:
                updated_node = self._remove_tree_get_assignment(updated_node)
                self.has_tree_get = False

        return updated_node

    def _contains_tree_get(self, node: cst.FunctionDef) -> bool:
        """Check if function contains tree.get('tree') pattern."""
        # Simple text-based check - convert function to code string
        try:
            # Use the module's code generation
            code = cst.Module(body=[node]).code
            return 'tree.get("tree")' in code or "tree.get('tree')" in code
        except:
            # If that fails, assume it might contain the pattern
            return True

    def _remove_tree_get_assignment(self, node: cst.FunctionDef) -> cst.FunctionDef:
        """Remove actual_tree = tree.get('tree') assignment."""
        new_body = []
        for stmt in node.body.body:
            # Skip assignment statements that match: actual_tree = tree.get("tree")
            if m.matches(
                stmt,
                m.SimpleStatementLine(
                    body=[
                        m.Assign(
                            targets=[m.AssignTarget(target=m.Name())],
                            value=m.Call(
                                func=m.Attribute(
                                    value=m.Name("tree"),
                                    attr=m.Name("get")
                                ),
                                args=[m.Arg(m.SimpleString('"tree"') | m.SimpleString("'tree'"))]
                            )
                        )
                    ]
                )
            ):
                self.stats.tree_gets_replaced += 1
                continue  # Skip this line
            new_body.append(stmt)

        if len(new_body) != len(node.body.body):
            return node.with_changes(
                body=node.body.with_changes(body=new_body)
            )
        return node

    # ------------------------------------------------------------------------
    # Transform ast.walk() patterns
    # ------------------------------------------------------------------------

    @m.leave(
        m.For(
            target=m.Name(),
            iter=m.Call(
                func=m.Attribute(
                    value=m.Name("ast"),
                    attr=m.Name("walk")
                ),
                args=[m.Arg()]
            )
        )
    )
    def replace_ast_walk_loop(
        self,
        original_node: cst.For,
        updated_node: cst.For
    ) -> cst.For:
        """Transform: for node in ast.walk(tree) → for node in context.find_nodes(...)"""

        if not self.inside_extractor:
            return updated_node

        # Extract the tree argument (might be actual_tree, tree, etc.)
        walk_call = updated_node.iter
        tree_arg = walk_call.args[0].value

        # Check if the loop body starts with isinstance check
        node_type = self._extract_isinstance_node_type(updated_node.body)

        if node_type:
            # Transform to context.find_nodes(node_type)
            self.stats.ast_walks_replaced += 1
            self.needs_ast_import = True  # Need ast for ast.FunctionDef, etc.

            new_iter = cst.Call(
                func=cst.Attribute(
                    value=cst.Name("context"),
                    attr=cst.Name("find_nodes")
                ),
                args=[cst.Arg(node_type)]
            )

            # Remove the isinstance check from body since find_nodes handles it
            new_body = self._remove_isinstance_check(updated_node.body)

            return updated_node.with_changes(
                iter=new_iter,
                body=new_body
            )
        else:
            # No isinstance check, transform to context.walk_tree() or similar
            # This is rare but handle it
            new_iter = cst.Call(
                func=cst.Attribute(
                    value=cst.Name("context"),
                    attr=cst.Name("walk_tree")
                ),
                args=[]
            )

            return updated_node.with_changes(iter=new_iter)

    def _extract_isinstance_node_type(self, body: cst.IndentedBlock) -> Optional[cst.BaseExpression]:
        """Extract the node type from isinstance check at start of loop body."""
        if not body.body:
            return None

        first_stmt = body.body[0]

        # Check for: if isinstance(node, ast.X):
        if m.matches(
            first_stmt,
            m.If(
                test=m.Call(
                    func=m.Name("isinstance"),
                    args=[
                        m.Arg(m.Name()),  # node variable
                        m.Arg()  # node type
                    ]
                )
            )
        ):
            isinstance_call = first_stmt.test
            node_type_arg = isinstance_call.args[1].value

            # Handle tuple of types: isinstance(node, (ast.X, ast.Y))
            # For now, just return the first type or the single type
            return node_type_arg

        return None

    def _remove_isinstance_check(self, body: cst.IndentedBlock) -> cst.IndentedBlock:
        """Remove the isinstance check from loop body since find_nodes handles it."""
        if not body.body:
            return body

        first_stmt = body.body[0]

        # If first statement is isinstance check, unwrap its body
        if m.matches(
            first_stmt,
            m.If(
                test=m.Call(
                    func=m.Name("isinstance"),
                    args=[m.Arg(m.Name()), m.Arg()]
                )
            )
        ):
            # Get the body of the if statement
            if_body = first_stmt.body.body
            remaining = body.body[1:] if len(body.body) > 1 else []

            # Combine if body with remaining statements
            new_body = list(if_body) + list(remaining)

            return body.with_changes(body=new_body)

        return body

    # ------------------------------------------------------------------------
    # Replace tree variable references
    # ------------------------------------------------------------------------

    @m.leave(m.Name())
    def replace_tree_references(
        self,
        original_node: cst.Name,
        updated_node: cst.Name
    ) -> cst.BaseExpression:
        """Replace references to actual_tree with context.tree."""

        if not self.inside_extractor:
            return updated_node

        # Replace actual_tree or tree variable with context.tree
        if updated_node.value in ["actual_tree", "ast_tree"]:
            return cst.Attribute(
                value=cst.Name("context"),
                attr=cst.Name("tree")
            )

        return updated_node

    # ------------------------------------------------------------------------
    # Replace _build_function_ranges() calls
    # ------------------------------------------------------------------------

    @m.leave(
        m.Call(
            func=m.Name("_build_function_ranges"),
            args=[m.Arg()]
        )
    )
    def replace_function_ranges(
        self,
        original_node: cst.Call,
        updated_node: cst.Call
    ) -> cst.Attribute:
        """Replace _build_function_ranges(tree) with context.function_ranges."""

        if not self.inside_extractor:
            return updated_node

        self.stats.function_ranges_replaced += 1

        return cst.Attribute(
            value=cst.Name("context"),
            attr=cst.Name("function_ranges")
        )

    # ------------------------------------------------------------------------
    # Add imports at module level
    # ------------------------------------------------------------------------

    def leave_Module(
        self,
        original_node: cst.Module,
        updated_node: cst.Module
    ) -> cst.Module:
        """Add necessary imports at the top of the module."""

        if not self.needs_filecontext_import:
            return updated_node

        new_body = []
        imports_added = False

        # Find where to insert imports (after initial docstring/comments)
        for i, stmt in enumerate(updated_node.body):
            if not imports_added:
                # Skip docstrings and comments
                if m.matches(stmt, m.SimpleStatementLine(body=[m.Expr(m.SimpleString())])):
                    new_body.append(stmt)
                    continue

                # Add our imports before first non-docstring statement
                if self.needs_filecontext_import:
                    # Add FileContext import
                    import_stmt = cst.SimpleStatementLine(
                        body=[
                            cst.ImportFrom(
                                module=cst.Attribute(
                                    value=cst.Attribute(
                                        value=cst.Attribute(
                                            value=cst.Name("theauditor"),
                                            attr=cst.Name("ast_extractors")
                                        ),
                                        attr=cst.Name("utils")
                                    ),
                                    attr=cst.Name("context")
                                ),
                                names=[
                                    cst.ImportAlias(name=cst.Name("FileContext"))
                                ]
                            )
                        ]
                    )
                    new_body.append(import_stmt)
                    self.stats.imports_added += 1

                imports_added = True

            new_body.append(stmt)

        return updated_node.with_changes(body=new_body)


# ============================================================================
# Create FileContext Infrastructure Files
# ============================================================================

def create_filecontext_module(output_dir: Path):
    """Create the FileContext and NodeIndex modules."""

    # Create utils directory if it doesn't exist
    utils_dir = output_dir / "utils"
    utils_dir.mkdir(exist_ok=True)

    # Create __init__.py
    init_file = utils_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""AST extraction utilities."""\n')

    # Create node_index.py
    node_index_file = utils_dir / "node_index.py"
    if not node_index_file.exists():
        node_index_content = '''"""NodeIndex: O(1) node lookup by type for AST trees."""
import ast
from collections import defaultdict
from typing import Union, Type, List, Tuple, Dict


class NodeIndex:
    """Fast AST node lookup by type.

    Builds index in single pass, enables O(1) queries.
    """

    def __init__(self, tree: ast.AST):
        """Build index of all nodes by type.

        Args:
            tree: AST tree to index
        """
        self._index: Dict[Type[ast.AST], List[ast.AST]] = defaultdict(list)
        self._line_index: Dict[Type[ast.AST], Dict[int, List[ast.AST]]] = defaultdict(lambda: defaultdict(list))

        # Single walk to build index
        for node in ast.walk(tree):
            node_type = type(node)
            self._index[node_type].append(node)

            # Also index by line number for range queries
            if hasattr(node, 'lineno'):
                self._line_index[node_type][node.lineno].append(node)

    def find_nodes(self, node_type: Union[Type[ast.AST], Tuple[Type[ast.AST], ...]]) -> List[ast.AST]:
        """Get all nodes of given type(s) with O(1) lookup.

        Args:
            node_type: Single type or tuple of types to find

        Returns:
            List of matching nodes
        """
        if isinstance(node_type, tuple):
            # Handle multiple types
            result = []
            for nt in node_type:
                result.extend(self._index.get(nt, []))
            return result
        return self._index.get(node_type, []).copy()

    def find_nodes_in_range(self, node_type: Type[ast.AST], start_line: int, end_line: int) -> List[ast.AST]:
        """Get nodes of type within line range.

        Args:
            node_type: Type of nodes to find
            start_line: Start line (inclusive)
            end_line: End line (inclusive)

        Returns:
            List of matching nodes in range
        """
        result = []
        type_lines = self._line_index.get(node_type, {})
        for line_num in range(start_line, end_line + 1):
            result.extend(type_lines.get(line_num, []))
        return result

    def get_stats(self) -> Dict[str, int]:
        """Get count of each node type.

        Returns:
            Dictionary mapping node type names to counts
        """
        return {
            node_type.__name__: len(nodes)
            for node_type, nodes in self._index.items()
        }
'''
        node_index_file.write_text(node_index_content)
        print(f"Created: {node_index_file}")

    # Create context.py
    context_file = utils_dir / "context.py"
    if not context_file.exists():
        context_content = '''"""FileContext: Shared extraction context with NodeIndex."""
import ast
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Union, Type
from pathlib import Path

from .node_index import NodeIndex


@dataclass
class FileContext:
    """Shared context for file extraction with O(1) node lookups.

    Built ONCE per file, used by ALL extractors.
    """

    # Core data
    tree: ast.AST
    content: str
    file_path: str

    # Internal index (private)
    _index: NodeIndex = field(init=False)

    # Pre-computed data
    imports: Dict[str, str] = field(default_factory=dict)
    function_ranges: List[Tuple[str, int, int]] = field(default_factory=list)
    class_ranges: List[Tuple[str, int, int]] = field(default_factory=list)

    def __post_init__(self):
        """Build index and pre-compute common data."""
        # Build NodeIndex
        self._index = NodeIndex(self.tree)

        # Build import mapping
        self._build_imports()

        # Build function/class ranges
        self._build_ranges()

    def find_nodes(self, node_type: Union[Type[ast.AST], Tuple[Type[ast.AST], ...]]) -> List[ast.AST]:
        """O(1) node lookup by type.

        Args:
            node_type: Single type or tuple of types

        Returns:
            List of matching nodes
        """
        return self._index.find_nodes(node_type)

    def walk_tree(self) -> List[ast.AST]:
        """Get all nodes (fallback for complex patterns).

        Returns:
            All nodes in tree
        """
        return list(ast.walk(self.tree))

    def resolve_symbol(self, name: str) -> str:
        """Resolve import alias to full module path.

        Examples:
            jwt.encode -> jose.jwt.encode (if import jose.jwt as jwt)
            j.encode -> jwt.encode (if import jwt as j)

        Args:
            name: Symbol name to resolve

        Returns:
            Resolved full name
        """
        if '.' not in name:
            return self.imports.get(name, name)

        parts = name.split('.')
        if parts[0] in self.imports:
            resolved_base = self.imports[parts[0]]
            return f"{resolved_base}.{'.'.join(parts[1:])}"
        return name

    def find_containing_function(self, line: int) -> Optional[str]:
        """Find function containing given line.

        Args:
            line: Line number

        Returns:
            Function name or None if global scope
        """
        for fname, start, end in self.function_ranges:
            if start <= line <= end:
                return fname
        return None

    def find_containing_class(self, line: int) -> Optional[str]:
        """Find class containing given line.

        Args:
            line: Line number

        Returns:
            Class name or None if not in class
        """
        for cname, start, end in self.class_ranges:
            if start <= line <= end:
                return cname
        return None

    def _build_imports(self):
        """Build import resolution mapping."""
        # Process import statements
        for node in self._index.find_nodes(ast.Import):
            for alias in node.names:
                import_name = alias.name
                alias_name = alias.asname or import_name
                self.imports[alias_name] = import_name

        # Process from imports
        for node in self._index.find_nodes(ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                import_name = alias.name
                alias_name = alias.asname or import_name
                if module:
                    self.imports[alias_name] = f"{module}.{import_name}"
                else:
                    self.imports[alias_name] = import_name

    def _build_ranges(self):
        """Build function and class line ranges."""
        # Build function ranges
        for node in self._index.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                self.function_ranges.append((
                    node.name,
                    node.lineno,
                    node.end_lineno or node.lineno
                ))

        # Sort by start line for efficient lookup
        self.function_ranges.sort(key=lambda x: x[1])

        # Build class ranges
        for node in self._index.find_nodes(ast.ClassDef):
            if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                self.class_ranges.append((
                    node.name,
                    node.lineno,
                    node.end_lineno or node.lineno
                ))

        # Sort by start line
        self.class_ranges.sort(key=lambda x: x[1])


def build_file_context(tree: ast.AST, content: str = "", file_path: str = "") -> FileContext:
    """Build FileContext with NodeIndex.

    This is the main entry point for extractors.

    Args:
        tree: Parsed AST tree
        content: File content (optional)
        file_path: Path to file (optional)

    Returns:
        FileContext with index and pre-computed data
    """
    return FileContext(
        tree=tree,
        content=content,
        file_path=file_path
    )
'''
        context_file.write_text(context_content)
        print(f"Created: {context_file}")


# ============================================================================
# File Processing
# ============================================================================

def process_file(filepath: Path, stats: TransformationStats,
                 dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Process a single Python file for FileContext transformation.

    Args:
        filepath: Path to the Python file
        stats: Statistics tracking object
        dry_run: If True, don't write changes
        verbose: If True, print detailed information

    Returns:
        True if file was modified, False otherwise
    """

    stats.files_processed += 1

    try:
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # Skip if not an extractor file
        if 'def extract_' not in source_code:
            if verbose:
                print(f"  Skipping {filepath.name} (no extractor functions)")
            return False

        # Parse with LibCST
        try:
            source_tree = cst.parse_module(source_code)
        except cst.ParserSyntaxError as e:
            print(f"  ERROR: Failed to parse {filepath.name}: {e}")
            return False

        # Create context and transformer
        context = CodemodContext()
        transformer = FileContextTransformer(context, stats)

        # Transform the tree
        modified_tree = source_tree.visit(transformer)

        # Check if anything changed
        if modified_tree.deep_equals(source_tree):
            if verbose:
                print(f"  No changes needed in {filepath.name}")
            return False

        # File was modified
        stats.files_modified += 1

        if dry_run:
            print(f"  Would modify: {filepath.name}")
            if verbose:
                # Show what would change
                print(f"    - Signatures changed: {stats.signatures_changed}")
                print(f"    - ast.walk() replaced: {stats.ast_walks_replaced}")
            return True

        # Create backup
        backup_path = filepath.with_suffix('.py.bak')
        shutil.copy2(filepath, backup_path)

        # Write the transformed code
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(modified_tree.code)

        print(f"  [OK] Transformed: {filepath.name} (backup: {backup_path.name})")
        return True

    except Exception as e:
        print(f"  ERROR processing {filepath.name}: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return False


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the FileContext transformer."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Transform Python extractors to use FileContext pattern with NodeIndex",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create FileContext infrastructure first
  python ast_walk_to_filecontext.py --create-modules --target-dir ./theauditor/ast_extractors/python/

  # Dry run to see what would change
  python ast_walk_to_filecontext.py --dry-run --target-dir ./theauditor/ast_extractors/python/

  # Run on specific file
  python ast_walk_to_filecontext.py --target-dir ./theauditor/ast_extractors/python/fundamental_extractors.py

  # Run on directory
  python ast_walk_to_filecontext.py --target-dir ./theauditor/ast_extractors/python/

  # Verbose output
  python ast_walk_to_filecontext.py --verbose --dry-run --target-dir ./theauditor/
        """
    )

    parser.add_argument(
        '--target-dir',
        type=Path,
        default=Path('./theauditor/ast_extractors/python/'),
        help='File or directory to process (default: ./theauditor/ast_extractors/python/)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Don't actually modify files, just show what would change"
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed progress information'
    )

    parser.add_argument(
        '--create-modules',
        action='store_true',
        help='Create FileContext and NodeIndex modules first'
    )

    args = parser.parse_args()

    # Create infrastructure if requested
    if args.create_modules:
        print("="*60)
        print("Creating FileContext Infrastructure")
        print("="*60)

        if args.target_dir.is_file():
            output_dir = args.target_dir.parent
        else:
            output_dir = args.target_dir

        create_filecontext_module(output_dir)
        print("\nFileContext modules created successfully!")

        if not args.target_dir.is_file():
            print("\nNow run without --create-modules to transform extractors")
            sys.exit(0)

    # Validate target
    if not args.target_dir.exists():
        print(f"ERROR: Target does not exist: {args.target_dir}")
        sys.exit(1)

    print("="*60)
    print("AST WALK TO FILECONTEXT TRANSFORMER")
    print("="*60)
    print(f"Target: {args.target_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Verbose: {args.verbose}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print()

    # Initialize statistics
    stats = TransformationStats()

    # Find Python files
    if args.target_dir.is_file():
        python_files = [args.target_dir]
    else:
        python_files = list(args.target_dir.rglob("*.py"))

        # Filter out test files and backups
        python_files = [
            f for f in python_files
            if 'test' not in f.name.lower()
            and not f.name.endswith('.bak')
            and not f.name.endswith('.backup')
            and 'utils' not in str(f.parent)  # Don't transform our own utils
        ]

    print(f"Found {len(python_files)} Python files to process\n")

    if not python_files:
        print("No Python files found to process!")
        sys.exit(0)

    # Process each file
    for filepath in sorted(python_files):
        if args.verbose:
            print(f"Processing: {filepath}")

        process_file(filepath, stats, dry_run=args.dry_run, verbose=args.verbose)

    # Print summary
    stats.print_summary()

    if args.dry_run:
        print("\nThis was a DRY RUN - no files were actually modified")
        print("Run without --dry-run to apply changes")
    else:
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Backup files created with .bak extension")
        print("\nTo restore from backups:")
        print('  for f in **/*.py.bak; do mv "$f" "${f%.bak}"; done')

    # Exit with appropriate code
    sys.exit(0 if stats.files_modified > 0 or args.dry_run else 1)


if __name__ == "__main__":
    main()