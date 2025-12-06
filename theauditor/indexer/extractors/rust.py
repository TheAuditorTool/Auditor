"""Rust file extractor - Extract Rust code structures for indexing."""

from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

from ...ast_extractors import rust_impl as rust_core
from ..fidelity_utils import FidelityToken
from . import BaseExtractor


class RustExtractor(BaseExtractor):
    """Extractor for Rust source files."""

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        """Initialize Rust extractor."""
        super().__init__(root_path, ast_parser)

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return [".rs"]

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all relevant information from a Rust file.

        Args:
            file_info: Dict with file metadata including 'path'
            content: File content as string
            tree: Parsed AST tree (tree-sitter)

        Returns:
            Dict with keys matching rust_* table names
        """
        file_path = file_info["path"]

        if not tree or tree.get("type") != "tree_sitter" or not tree.get("tree"):
            logger.error(
                "Tree-sitter failed to parse Rust file: %s. "
                "Check tree-sitter-language-pack installation or file syntax.",
                file_path,
            )
            return {}

        from ...ast_extractors.base import check_tree_sitter_parse_quality

        ts_tree = tree["tree"]
        root = ts_tree.root_node
        check_tree_sitter_parse_quality(root, file_path, logger)

        rust_functions = rust_core.extract_rust_functions(root, file_path)
        rust_structs = rust_core.extract_rust_structs(root, file_path)
        rust_enums = rust_core.extract_rust_enums(root, file_path)
        rust_traits = rust_core.extract_rust_traits(root, file_path)
        rust_use_statements = rust_core.extract_rust_use_statements(root, file_path)

        symbols = []
        for func in rust_functions:
            symbols.append(
                {
                    "path": file_path,
                    "name": func.get("name", ""),
                    "type": "function",
                    "line": func.get("line", 0),
                    "col": 0,
                    "end_line": func.get("end_line"),
                    "parameters": func.get("params_json"),
                }
            )
        for struct in rust_structs:
            symbols.append(
                {
                    "path": file_path,
                    "name": struct.get("name", ""),
                    "type": "class",
                    "line": struct.get("line", 0),
                    "col": 0,
                    "end_line": struct.get("end_line"),
                }
            )
        for enum in rust_enums:
            symbols.append(
                {
                    "path": file_path,
                    "name": enum.get("name", ""),
                    "type": "class",
                    "line": enum.get("line", 0),
                    "col": 0,
                    "end_line": enum.get("end_line"),
                }
            )
        for trait in rust_traits:
            symbols.append(
                {
                    "path": file_path,
                    "name": trait.get("name", ""),
                    "type": "class",
                    "line": trait.get("line", 0),
                    "col": 0,
                    "end_line": trait.get("end_line"),
                }
            )

        imports_for_refs = []
        for use_stmt in rust_use_statements:
            imports_for_refs.append(
                {
                    "kind": "import",
                    "value": use_stmt.get("import_path", ""),
                    "line": use_stmt.get("line"),
                }
            )

        result = {
            "symbols": symbols,
            "imports": imports_for_refs,
            "rust_modules": rust_core.extract_rust_modules(root, file_path),
            "rust_use_statements": rust_use_statements,
            "rust_functions": rust_functions,
            "rust_structs": rust_structs,
            "rust_enums": rust_enums,
            "rust_traits": rust_traits,
            "rust_impl_blocks": rust_core.extract_rust_impl_blocks(root, file_path),
            "rust_generics": rust_core.extract_rust_generics(root, file_path),
            "rust_lifetimes": rust_core.extract_rust_lifetimes(root, file_path),
            "rust_macros": rust_core.extract_rust_macros(root, file_path),
            "rust_macro_invocations": rust_core.extract_rust_macro_invocations(root, file_path),
            "rust_attributes": rust_core.extract_rust_attributes(root, file_path),
            "rust_async_functions": rust_core.extract_rust_async_functions(root, file_path),
            "rust_await_points": rust_core.extract_rust_await_points(root, file_path),
            "rust_unsafe_blocks": rust_core.extract_rust_unsafe_blocks(root, file_path),
            "rust_unsafe_traits": rust_core.extract_rust_unsafe_traits(root, file_path),
            "rust_struct_fields": rust_core.extract_rust_struct_fields(root, file_path),
            "rust_enum_variants": rust_core.extract_rust_enum_variants(root, file_path),
            "rust_trait_methods": rust_core.extract_rust_trait_methods(root, file_path),
            "rust_extern_functions": rust_core.extract_rust_extern_functions(root, file_path),
            "rust_extern_blocks": rust_core.extract_rust_extern_blocks(root, file_path),
            "assignments": rust_core.extract_rust_assignments(root, file_path),
            "function_calls": rust_core.extract_rust_function_calls(root, file_path),
            "returns": rust_core.extract_rust_returns(root, file_path),
            "cfg": rust_core.extract_rust_cfg(root, file_path),
        }

        logger.debug(
            f"Extracted Rust: {file_path} -> "
            f"{len(result['rust_functions'])} functions, "
            f"{len(result['rust_structs'])} structs, "
            f"{len(result['rust_traits'])} traits, "
            f"{len(result['rust_impl_blocks'])} impl blocks"
        )

        return FidelityToken.attach_manifest(result)
