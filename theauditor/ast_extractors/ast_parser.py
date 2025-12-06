"""AST parser with language-specific parsers for optimal analysis."""

import ast
import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

from .js_semantic_parser import get_semantic_ast_batch


class ParseError(Exception):
    """Structured parse error with file and line info.

    Use this instead of RuntimeError for parse failures so callers
    can access .line and .file directly instead of regex-parsing error messages.
    """

    def __init__(self, message: str, file: str = "unknown", line: int = 1):
        self.file = file
        self.line = line
        super().__init__(message)


@dataclass
class ASTMatch:
    """Represents an AST pattern match."""

    node_type: str
    start_line: int
    end_line: int
    start_col: int
    snippet: str
    metadata: dict[str, Any] = None


class ASTParser:
    """Multi-language AST parser using Tree-sitter for structural analysis."""

    def __init__(self):
        """Initialize parser with Tree-sitter language support."""
        self.has_tree_sitter = False
        self.parsers = {}
        self.languages = {}
        self.project_type = None

        try:
            import tree_sitter

            self.tree_sitter = tree_sitter
            self.has_tree_sitter = True
            self._init_tree_sitter_parsers()
        except ImportError:
            logger.warning("\n AST parsing dependencies not fully installed.")
            logger.info("  - Python analysis: ✓ Will work (uses built-in ast module)")
            logger.info(
                "  - JavaScript/TypeScript analysis: ✗ Will fail (requires Node.js semantic parser)"
            )
            logger.info("  - Terraform/HCL analysis: ✗ Limited functionality")
            logger.info("\nTo enable full analysis capabilities, run:")
            logger.info("  aud setup-ai --target .\n")

    def _init_tree_sitter_parsers(self):
        """Initialize Tree-sitter language parsers with proper bindings."""
        if not self.has_tree_sitter:
            return

        try:
            from tree_sitter_language_pack import get_language, get_parser

            try:
                js_lang = get_language("javascript")
                js_parser = get_parser("javascript")
                self.parsers["javascript"] = js_parser
                self.languages["javascript"] = js_lang
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load tree-sitter grammar for JavaScript: {e}\n"
                    "This is often due to missing build tools or corrupted installation.\n"
                    "Please try: pip install --force-reinstall tree-sitter-language-pack\n"
                    "Or install with AST support: pip install -e '.[ast]'"
                ) from e

            try:
                ts_lang = get_language("typescript")
                ts_parser = get_parser("typescript")
                self.parsers["typescript"] = ts_parser
                self.languages["typescript"] = ts_lang
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load tree-sitter grammar for TypeScript: {e}\n"
                    "This is often due to missing build tools or corrupted installation.\n"
                    "Please try: pip install --force-reinstall tree-sitter-language-pack\n"
                    "Or install with AST support: pip install -e '.[ast]'"
                ) from e

            try:
                hcl_lang = get_language("hcl")
                hcl_parser = get_parser("hcl")
                self.parsers["hcl"] = hcl_parser
                self.languages["hcl"] = hcl_lang
            except Exception as e:
                logger.info(f"HCL tree-sitter not available: {e}")
                logger.info(
                    "Terraform analysis requires the tree-sitter HCL grammar. "
                    "Install language support with 'pip install -e .[ast]' or run 'aud setup-ai --target .' ."
                )

            try:
                rust_lang = get_language("rust")
                rust_parser = get_parser("rust")
                self.parsers["rust"] = rust_parser
                self.languages["rust"] = rust_lang
            except Exception as e:
                logger.info(f"Rust tree-sitter not available: {e}")

            try:
                go_lang = get_language("go")
                go_parser = get_parser("go")
                self.parsers["go"] = go_parser
                self.languages["go"] = go_lang
            except Exception as e:
                logger.info(f"Go tree-sitter not available: {e}")

            try:
                bash_lang = get_language("bash")
                bash_parser = get_parser("bash")
                self.parsers["bash"] = bash_parser
                self.languages["bash"] = bash_lang
            except Exception as e:
                logger.info(f"Bash tree-sitter not available: {e}")

        except ImportError as e:
            logger.info(
                f"ERROR: tree-sitter is installed but tree-sitter-language-pack is not: {e}"
            )
            logger.info("This means tree-sitter AST analysis cannot work properly.")
            logger.info("Please install with: pip install tree-sitter-language-pack")
            logger.info("Or install TheAuditor with full AST support: pip install -e '.[ast]'")

            self.has_tree_sitter = False

    def _detect_project_type(self) -> str:
        """Detect the primary project type based on manifest files."""
        if self.project_type is not None:
            return self.project_type

        has_js = Path("package.json").exists()
        has_python = (
            Path("requirements.txt").exists()
            or Path("pyproject.toml").exists()
            or Path("setup.py").exists()
        )
        has_go = Path("go.mod").exists()

        if has_js and has_python or has_js and has_go or has_python and has_go:
            self.project_type = "polyglot"
        elif has_js:
            self.project_type = "javascript"
        elif has_python:
            self.project_type = "python"
        elif has_go:
            self.project_type = "go"
        else:
            self.project_type = "unknown"

        return self.project_type

    def parse_file(
        self,
        file_path: Path,
        language: str = None,
        root_path: str = None,
        jsx_mode: str = "transformed",
    ) -> Any:
        """Parse a file into an AST."""
        if language is None:
            language = self._detect_language(file_path)

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            tsconfig_path = self._find_tsconfig_for_file(file_path, root_path)

            content_hash = hashlib.md5(content).hexdigest()

            if language in ["javascript", "typescript"]:
                normalized_path = str(file_path).replace("\\", "/")

                try:
                    tsconfig_map = {}
                    if tsconfig_path:
                        tsconfig_map[normalized_path] = str(tsconfig_path).replace("\\", "/")

                    batch_results = get_semantic_ast_batch(
                        [normalized_path],
                        project_root=root_path,
                        jsx_mode=jsx_mode,
                        tsconfig_map=tsconfig_map,
                    )

                    if normalized_path not in batch_results:
                        raise RuntimeError(
                            f"FATAL: Batch processor did not return result for {file_path}\n"
                            f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                            f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                            f"DO NOT use fallback parsers - they produce corrupted data."
                        )

                    semantic_result = batch_results[normalized_path]

                    if os.environ.get("THEAUDITOR_DEBUG"):
                        cfg_count = len(semantic_result.get("extracted_data", {}).get("cfg", []))
                        logger.debug(
                            f"Single-pass result for {file_path}: {cfg_count} CFGs in extracted_data"
                        )

                except Exception as e:
                    raise RuntimeError(
                        f"FATAL: TypeScript semantic parser failed for {file_path}\n"
                        f"Error: {e}\n"
                        f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                        f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                        f"DO NOT use fallback parsers - they produce corrupted data."
                    ) from e

                if not semantic_result.get("success"):
                    error_msg = semantic_result.get("error", "Unknown error")
                    raise RuntimeError(
                        f"FATAL: TypeScript semantic parser failed for {file_path}\n"
                        f"Error: {error_msg}\n"
                        f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                        f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                        f"DO NOT use fallback parsers - they produce corrupted data."
                    )

                return {
                    "type": "semantic_ast",
                    "tree": semantic_result,
                    "language": language,
                    "content": content.decode("utf-8", errors="ignore"),
                    "has_types": semantic_result.get("hasTypes", False),
                    "diagnostics": semantic_result.get("diagnostics", []),
                    "symbols": semantic_result.get("symbols", []),
                }

            if language == "python":
                decoded = content.decode("utf-8", errors="ignore")
                python_ast = self._parse_python_cached(content_hash, decoded, str(file_path))
                return {
                    "type": "python_ast",
                    "tree": python_ast,
                    "language": language,
                    "content": decoded,
                }

            if language in self.parsers:
                parser = self.parsers[language]
                tree = parser.parse(content)
                if tree:
                    return {
                        "type": "tree_sitter",
                        "tree": tree,
                        "language": language,
                        "content": content.decode("utf-8", errors="ignore"),
                    }

            return None

        except RuntimeError:
            raise
        except Exception as e:
            if language in ["javascript", "typescript"]:
                raise RuntimeError(
                    f"FATAL: Failed to parse {file_path}: {e}\n"
                    f"JavaScript/TypeScript files REQUIRE successful parsing.\n"
                    f"NO FALLBACKS ALLOWED - fix the error or exclude the file."
                ) from e

            raise RuntimeError(f"FATAL: Failed to parse {file_path}: {e}") from e

    def _detect_language(self, file_path: Path) -> str:
        """Detect language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".vue": "javascript",
            ".tf": "hcl",
            ".tfvars": "hcl",
            ".rs": "rust",
            ".go": "go",
            ".sh": "bash",
            ".bash": "bash",
        }
        return ext_map.get(file_path.suffix.lower(), "")

    def _parse_python_builtin(self, content: str, file_path: str = "unknown") -> ast.AST:
        """Parse Python code using built-in ast module.

        NO FALLBACKS: SyntaxError is fatal - file must be valid Python.
        """
        try:
            return ast.parse(content)
        except SyntaxError as e:
            raise ParseError(
                f"Python syntax error: {e.msg}",
                file=file_path,
                line=e.lineno or 1,
            ) from e

    def _parse_python_cached(
        self, content_hash: str, content: str, file_path: str = "unknown"
    ) -> ast.AST:
        """Parse Python code (caching removed - error messages need file context)."""
        return self._parse_python_builtin(content, file_path)

    @lru_cache(maxsize=10000)  # noqa: B019 - singleton, lives entire session
    def _parse_treesitter_cached(self, content_hash: str, content: bytes, language: str) -> Any:
        """Parse code using Tree-sitter with caching based on content hash."""
        parser = self.parsers[language]
        return parser.parse(content)

    def supports_language(self, language: str) -> bool:
        """Check if a language is supported for AST parsing."""

        if language == "python":
            return True

        if language in ["javascript", "typescript"]:
            return True

        return self.has_tree_sitter and language in self.parsers

    def parse_content(
        self, content: str, language: str, filepath: str = "unknown", jsx_mode: str = "transformed"
    ) -> Any:
        """Parse in-memory content into AST."""
        import tempfile

        content_bytes = content.encode("utf-8")
        content_hash = hashlib.md5(content_bytes).hexdigest()

        if language in ["javascript", "typescript"]:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                normalized_path = str(tmp_path).replace("\\", "/")

                try:
                    batch_results = get_semantic_ast_batch([normalized_path], jsx_mode=jsx_mode)

                    if normalized_path not in batch_results:
                        raise RuntimeError(
                            f"FATAL: Batch processor did not return result for {filepath}\n"
                            f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                            f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                            f"DO NOT use fallback parsers - they produce corrupted data."
                        )

                    semantic_result = batch_results[normalized_path]

                except Exception as e:
                    raise RuntimeError(
                        f"FATAL: TypeScript semantic parser failed for {filepath}\n"
                        f"Error: {e}\n"
                        f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                        f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                        f"DO NOT use fallback parsers - they produce corrupted data."
                    ) from e

                if not (semantic_result and semantic_result.get("success")):
                    error_msg = (
                        semantic_result.get("error", "Unknown error")
                        if semantic_result
                        else "No result"
                    )
                    raise RuntimeError(
                        f"FATAL: TypeScript semantic parser failed for {filepath}\n"
                        f"Error: {error_msg}\n"
                        f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                        f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                        f"DO NOT use fallback parsers - they produce corrupted data."
                    )

                return {
                    "type": "semantic_ast",
                    "tree": semantic_result,
                    "language": language,
                    "content": content,
                }
            finally:
                os.unlink(tmp_path)

        if language == "python":
            python_ast = self._parse_python_cached(content_hash, content, filepath)
            return {
                "type": "python_ast",
                "tree": python_ast,
                "language": language,
                "content": content,
            }

        return None

    def parse_files_batch(
        self, file_paths: list[Path], root_path: str = None, jsx_mode: str = "transformed"
    ) -> dict[str, Any]:
        """Parse multiple files into ASTs in batch for performance.

        NO FALLBACKS: If batch processing fails for JS/TS files, we fail loud.
        Individual file failures are also fatal - no silent data loss.
        """
        results = {}

        js_ts_files = []
        python_files = []
        other_files = []

        for file_path in file_paths:
            language = self._detect_language(file_path)
            if language in ["javascript", "typescript"]:
                js_ts_files.append(file_path)
            elif language == "python":
                python_files.append(file_path)
            else:
                other_files.append(file_path)

        if js_ts_files:
            if not get_semantic_ast_batch:
                raise RuntimeError(
                    "FATAL: JavaScript/TypeScript files found but semantic parser not available.\n"
                    "Run: aud setup-ai --target .\n"
                    "NO FALLBACKS ALLOWED - semantic parser is required."
                )

            js_ts_paths = []
            tsconfig_map: dict[str, str] = {}
            for f in js_ts_files:
                normalized_path = str(f).replace("\\", "/")
                js_ts_paths.append(normalized_path)
                tsconfig_for_file = self._find_tsconfig_for_file(f, root_path)
                if tsconfig_for_file:
                    tsconfig_map[normalized_path] = str(tsconfig_for_file).replace("\\", "/")

            batch_results = get_semantic_ast_batch(
                js_ts_paths,
                project_root=root_path,
                jsx_mode=jsx_mode,
                tsconfig_map=tsconfig_map,
            )

            for file_path in js_ts_files:
                file_str = str(file_path).replace("\\", "/")

                if file_str not in batch_results:
                    raise RuntimeError(
                        f"FATAL: Batch processor did not return result for {file_path}\n"
                        f"This indicates a bug in the semantic parser.\n"
                        f"NO FALLBACKS ALLOWED - fix the parser or exclude the file."
                    )

                semantic_result = batch_results[file_str]

                if os.environ.get("THEAUDITOR_DEBUG"):
                    cfg_count = len(semantic_result.get("extracted_data", {}).get("cfg", []))
                    logger.debug(
                        f"Single-pass result for {Path(file_path).name}: {cfg_count} CFGs in extracted_data"
                    )

                if not semantic_result.get("success"):
                    raise RuntimeError(
                        f"FATAL: Semantic parser failed for {file_path}\n"
                        f"Error: {semantic_result.get('error', 'Unknown error')}\n"
                        f"NO FALLBACKS ALLOWED - fix the error or exclude the file."
                    )

                with open(file_path, "rb") as f:
                    content = f.read()

                results[file_str] = {
                    "type": "semantic_ast",
                    "tree": semantic_result,
                    "language": self._detect_language(file_path),
                    "content": content.decode("utf-8", errors="ignore"),
                    "has_types": semantic_result.get("hasTypes", False),
                    "diagnostics": semantic_result.get("diagnostics", []),
                    "symbols": semantic_result.get("symbols", []),
                }

        for file_path in python_files:
            results[str(file_path).replace("\\", "/")] = self.parse_file(
                file_path, root_path=root_path, jsx_mode=jsx_mode
            )

        for file_path in other_files:
            results[str(file_path).replace("\\", "/")] = self.parse_file(
                file_path, root_path=root_path, jsx_mode=jsx_mode
            )

        return results

    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages."""

        languages = ["python", "javascript", "typescript"]

        if self.has_tree_sitter:
            languages.extend(self.parsers.keys())

        return sorted(set(languages))

    def _find_tsconfig_for_file(self, file_path: Path, root_path: str | None) -> Path | None:
        """Locate the nearest tsconfig.json for a given file within the project root."""
        try:
            resolved_file = file_path.resolve()
        except OSError:
            resolved_file = file_path

        search_dir = resolved_file.parent
        root_dir = Path(root_path).resolve() if root_path else None

        while True:
            candidate = search_dir / "tsconfig.json"
            if candidate.exists():
                return candidate

            if search_dir == search_dir.parent:
                break

            if root_dir and search_dir == root_dir:
                break

            if root_dir and not str(search_dir).startswith(str(root_dir)):
                break

            search_dir = search_dir.parent

        return None
