"""Python file extractor - Thin wrapper for Python AST extraction."""

import ast
from pathlib import Path
from typing import Any

from theauditor.ast_extractors.python.utils.context import build_file_context
from theauditor.ast_extractors.python_impl import extract_all_python_data
from theauditor.utils.logging import logger

from . import BaseExtractor


class PythonExtractor(BaseExtractor):
    """Extractor for Python files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return [".py", ".pyx"]

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all relevant information from a Python file."""

        if not hasattr(self.__class__, "_processed_files"):
            self.__class__._processed_files = set()

        file_path = file_info["path"]

        self.__class__._processed_files.add(file_path)

        #     print(f"[PYTHON.PY ENTRY] Tree type: {tree.get('type') if isinstance(tree, dict) else type(tree)}", file=sys.stderr)

        context = None
        if tree and isinstance(tree, dict) and tree.get("type") == "python_ast":
            actual_tree = tree.get("tree")
            if actual_tree:
                try:
                    context = build_file_context(actual_tree, content, str(file_info["path"]))

                except Exception:
                    logger.exception("")

        if not context:
            return self._empty_result()

        result = extract_all_python_data(context)

        if tree and isinstance(tree, dict):
            resolved = self._resolve_imports(file_info, tree)
            if resolved:
                result["resolved_imports"] = resolved

        return result

    def _empty_result(self) -> dict[str, Any]:
        """Return an empty result structure."""
        return {
            "imports": [],
            "routes": [],
            "symbols": [],
            "assignments": [],
            "function_calls": [],
            "returns": [],
            "variable_usage": [],
            "cfg": [],
            "object_literals": [],
            "sql_queries": [],
            "jwt_patterns": [],
            "type_annotations": [],
            "resolved_imports": {},
        }

    def _resolve_imports(self, file_info: dict[str, Any], tree: dict[str, Any]) -> dict[str, str]:
        """Resolve Python import targets to absolute module/file paths."""
        resolved: dict[str, str] = {}
        actual_tree = tree.get("tree")

        if not isinstance(actual_tree, ast.AST):
            return resolved

        file_path = Path(file_info["path"])
        module_parts = list(file_path.with_suffix("").parts)
        package_parts = module_parts[:-1]

        def normalize_path(path: Path) -> str:
            return str(path).replace("\\", "/")

        def module_parts_to_path(parts: list[str]) -> str | None:
            if not parts:
                return None
            candidate_file = Path(*parts).with_suffix(".py")
            candidate_init = Path(*parts) / "__init__.py"

            if (self.root_path / candidate_file).exists():
                return normalize_path(candidate_file)
            if (self.root_path / candidate_init).exists():
                return normalize_path(candidate_init)
            return None

        def resolve_dotted(module_name: str) -> str | None:
            if not module_name:
                return None
            return module_parts_to_path(module_name.split("."))

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    resolved_target = resolve_dotted(module_name) or module_name

                    local_name = alias.asname or module_name.split(".")[-1]

                    resolved[module_name] = resolved_target
                    resolved[local_name] = resolved_target

            elif isinstance(node, ast.ImportFrom):
                level = getattr(node, "level", 0) or 0
                base_parts = package_parts.copy()

                if level:
                    base_parts = base_parts[:-level] if level <= len(base_parts) else []

                module_name = node.module or ""
                module_name_parts = module_name.split(".") if module_name else []
                target_base = base_parts + module_name_parts

                module_key = ".".join(part for part in target_base if part)
                module_path = module_parts_to_path(target_base)
                if module_key:
                    resolved[module_key] = module_path or module_key
                elif module_path:
                    resolved[module_path] = module_path

                for alias in node.names:
                    imported_name = alias.name
                    local_name = alias.asname or imported_name

                    full_parts = target_base + [imported_name]
                    symbol_path = module_parts_to_path(full_parts)

                    if symbol_path:
                        resolved_value = symbol_path
                    elif module_path:
                        resolved_value = module_path
                    elif module_key:
                        resolved_value = f"{module_key}.{imported_name}"
                    else:
                        resolved_value = local_name

                    resolved[local_name] = resolved_value

        return resolved

    def _extract_imports_ast(self, tree: dict[str, Any]) -> list[tuple]:
        """Extract imports from Python AST."""
        imports = []

        if not tree or not isinstance(tree, dict):
            return imports

        actual_tree = tree.get("tree")

        logger.debug(
            f"_extract_imports_ast: tree type={type(tree)}, has 'tree' key={('tree' in tree) if isinstance(tree, dict) else False}"
        )
        if isinstance(tree, dict) and "tree" in tree:
            logger.debug(
                f"actual_tree type={type(actual_tree)}, isinstance(ast.Module)={isinstance(actual_tree, ast.Module)}"
            )

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            logger.debug("Returning empty - actual_tree check failed")
            return imports
