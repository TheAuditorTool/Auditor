"""FileContext: Shared extraction context with NodeIndex."""

import ast
from dataclasses import dataclass, field

from .node_index import NodeIndex


@dataclass
class FileContext:
    """Shared context for file extraction with O(1) node lookups.

    Built ONCE per file, used by ALL extractors.
    """

    tree: ast.AST
    content: str
    file_path: str

    _index: NodeIndex = field(init=False)

    imports: dict[str, str] = field(default_factory=dict)
    function_ranges: list[tuple[str, int, int]] = field(default_factory=list)
    class_ranges: list[tuple[str, int, int]] = field(default_factory=list)

    def __post_init__(self):
        """Build index and pre-compute common data."""

        self._index = NodeIndex(self.tree)

        self._build_imports()

        self._build_ranges()

    def find_nodes(self, node_type: type[ast.AST] | tuple[type[ast.AST], ...]) -> list[ast.AST]:
        """O(1) node lookup by type.

        Args:
            node_type: Single type or tuple of types

        Returns:
            List of matching nodes
        """
        return self._index.find_nodes(node_type)

    def walk_tree(self) -> list[ast.AST]:
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
        if "." not in name:
            return self.imports.get(name, name)

        parts = name.split(".")
        if parts[0] in self.imports:
            resolved_base = self.imports[parts[0]]
            return f"{resolved_base}.{'.'.join(parts[1:])}"
        return name

    def find_containing_function(self, line: int) -> str | None:
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

    def find_containing_class(self, line: int) -> str | None:
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

        for node in self._index.find_nodes(ast.Import):
            for alias in node.names:
                import_name = alias.name
                alias_name = alias.asname or import_name
                self.imports[alias_name] = import_name

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

        for node in self._index.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                self.function_ranges.append(
                    (node.name, node.lineno, node.end_lineno or node.lineno)
                )

        self.function_ranges.sort(key=lambda x: x[1])

        for node in self._index.find_nodes(ast.ClassDef):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                self.class_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

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
    return FileContext(tree=tree, content=content, file_path=file_path)
