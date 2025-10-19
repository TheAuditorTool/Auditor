"""AST parser with language-specific parsers for optimal analysis.

Architecture:
- Python: CPython ast module (stdlib) - NOT Tree-sitter
- JavaScript/TypeScript: TypeScript Compiler API MANDATORY - NO FALLBACKS
- Tree-sitter: DEPRECATED for JS/TS (produces corrupted data)

This module provides true structural code analysis using the best parser for
each language, enabling high-fidelity pattern detection that understands code
semantics rather than just text matching.

CRITICAL:
- Python is NEVER parsed by Tree-sitter (see _init_tree_sitter_parsers() lines 63-90)
- JS/TS MUST use semantic parser - silent fallbacks produce "anonymous" function names
"""

import ast
import hashlib
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, List, Dict, Union

from theauditor.js_semantic_parser import get_semantic_ast, get_semantic_ast_batch
from theauditor.ast_patterns import ASTPatternMixin
from theauditor.ast_extractors import ASTExtractorMixin


@dataclass
class ASTMatch:
    """Represents an AST pattern match."""

    node_type: str
    start_line: int
    end_line: int
    start_col: int
    snippet: str
    metadata: Dict[str, Any] = None


class ASTParser(ASTPatternMixin, ASTExtractorMixin):
    """Multi-language AST parser using Tree-sitter for structural analysis."""

    def __init__(self):
        """Initialize parser with Tree-sitter language support."""
        self.has_tree_sitter = False
        self.parsers = {}
        self.languages = {}
        self.project_type = None  # Cache project type detection
        
        # Try to import tree-sitter and language bindings
        try:
            import tree_sitter
            self.tree_sitter = tree_sitter
            self.has_tree_sitter = True
            self._init_tree_sitter_parsers()
        except ImportError:
            print("Warning: Tree-sitter not available. Install with: pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-typescript")

    def _init_tree_sitter_parsers(self):
        """Initialize Tree-sitter language parsers with proper bindings."""
        if not self.has_tree_sitter:
            return
        
        # Use tree-sitter-language-pack for all languages
        try:
            from tree_sitter_language_pack import get_language, get_parser
            
            # ============================================================================
            # CRITICAL ARCHITECTURAL DECISION: PYTHON IS NEVER PARSED BY TREE-SITTER
            # ============================================================================
            # Python MUST use CPython's built-in ast module (stdlib) for these reasons:
            #
            # 1. CORRECTNESS: All Python extractors expect ast.Module objects and use
            #    ast.walk(), ast.Import, ast.FunctionDef, etc. Tree-sitter has completely
            #    different node types (.type, .children, .text) that will cause silent
            #    failures and return empty results.
            #
            # 2. SUPERIORITY: CPython ast is the authoritative Python parser - complete,
            #    mature, zero dependencies, faster than Tree-sitter subprocess.
            #
            # 3. ARCHITECTURE: TheAuditor uses language-specific excellence, NOT generic
            #    unification. Each language gets its best tool:
            #    - Python → CPython ast (this is THE correct choice)
            #    - JavaScript/TypeScript → TypeScript Compiler API (semantic + types)
            #    - SQL → sqlparse
            #    - Docker → dockerfile-parse
            #
            # DO NOT ADD Python to self.parsers dict below. It will break import extraction.
            # If you think "prefer tree-sitter for consistency" - you are wrong. Read this
            # comment again. Python parsing happens at parse_file() lines 211-219 and
            # parse_content() lines 354-360.
            #
            # Last incident: 2025-10-16 - Tree-sitter Python was added, broke all Python
            # import extraction (0 refs in database). Fixed by removing it. Don't repeat.
            # ============================================================================

            # JavaScript parser (CRITICAL - must fail fast)
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
                )
            
            # TypeScript parser (CRITICAL - must fail fast)
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
                )
                
        except ImportError as e:
            # If tree-sitter is installed but language pack is not, this is a critical error
            # The user clearly intends to use tree-sitter, so we should fail loudly
            print(f"ERROR: tree-sitter is installed but tree-sitter-language-pack is not: {e}")
            print("This means tree-sitter AST analysis cannot work properly.")
            print("Please install with: pip install tree-sitter-language-pack")
            print("Or install TheAuditor with full AST support: pip install -e '.[ast]'")
            # Set flags to indicate no language support
            self.has_tree_sitter = False
            # Don't raise - allow fallback to regex-based parsing

    def _detect_project_type(self) -> str:
        """Detect the primary project type based on manifest files.
        
        Returns:
            'polyglot' if multiple language manifest files exist
            'javascript' if only package.json exists
            'python' if only Python manifest files exist
            'go' if only go.mod exists
            'unknown' otherwise
        """
        if self.project_type is not None:
            return self.project_type
        
        # Check all manifest files first
        has_js = Path("package.json").exists()
        has_python = (Path("requirements.txt").exists() or 
                      Path("pyproject.toml").exists() or 
                      Path("setup.py").exists())
        has_go = Path("go.mod").exists()
        
        # Determine project type based on combinations
        if has_js and has_python:
            self.project_type = "polyglot"  # NEW: Properly handle mixed projects
        elif has_js and has_go:
            self.project_type = "polyglot"
        elif has_python and has_go:
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

    def parse_file(self, file_path: Path, language: str = None, root_path: str = None, jsx_mode: str = 'transformed') -> Any:
        """Parse a file into an AST.

        Args:
            file_path: Path to the source file.
            language: Programming language (auto-detected if None).
            root_path: Absolute path to project root (for sandbox resolution).
            jsx_mode: JSX extraction mode ('preserved' or 'transformed').

        Returns:
            AST tree object or None if parsing fails.
        """
        if language is None:
            language = self._detect_language(file_path)

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            tsconfig_path = self._find_tsconfig_for_file(file_path, root_path)
            
            # Compute content hash for caching
            content_hash = hashlib.md5(content).hexdigest()

            # For JavaScript/TypeScript, semantic parser is MANDATORY
            # NO FALLBACKS. If semantic parser fails, we MUST fail loudly.
            # Silent fallbacks to Tree-sitter produce corrupted databases with "anonymous" function names.
            if language in ["javascript", "typescript"]:
                # Normalize path for cross-platform compatibility
                normalized_path = str(file_path).replace("\\", "/")

                try:
                    semantic_result = get_semantic_ast(
                        normalized_path,
                        project_root=root_path,
                        jsx_mode=jsx_mode,
                        tsconfig_path=str(tsconfig_path) if tsconfig_path else None
                    )
                except Exception as e:
                    raise RuntimeError(
                        f"FATAL: TypeScript semantic parser failed for {file_path}\n"
                        f"Error: {e}\n"
                        f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                        f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                        f"DO NOT use fallback parsers - they produce corrupted data."
                    )

                if not semantic_result.get("success"):
                    error_msg = semantic_result.get('error', 'Unknown error')
                    raise RuntimeError(
                        f"FATAL: TypeScript semantic parser failed for {file_path}\n"
                        f"Error: {error_msg}\n"
                        f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                        f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                        f"DO NOT use fallback parsers - they produce corrupted data."
                    )

                # Return the semantic AST with full type information
                return {
                    "type": "semantic_ast",
                    "tree": semantic_result,
                    "language": language,
                    "content": content.decode("utf-8", errors="ignore"),
                    "has_types": semantic_result.get("hasTypes", False),
                    "diagnostics": semantic_result.get("diagnostics", []),
                    "symbols": semantic_result.get("symbols", [])
                }

            # PRIMARY PYTHON PARSER - CPython ast module (NOT a fallback!)
            # Python is NEVER parsed by Tree-sitter - CPython ast is the correct, intended tool.
            # Tree-sitter adds zero value for Python. See lines 63-64 where Python is explicitly
            # excluded from Tree-sitter initialization.
            if language == "python":
                decoded = content.decode("utf-8", errors="ignore")
                python_ast = self._parse_python_cached(content_hash, decoded)
                if python_ast:
                    return {"type": "python_ast", "tree": python_ast, "language": language, "content": decoded}

            # Return None for unsupported languages
            return None

        except Exception as e:
            print(f"Warning: Failed to parse {file_path}: {e}")
            return None

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
            ".vue": "javascript",  # Vue SFCs contain JavaScript/TypeScript
        }
        return ext_map.get(file_path.suffix.lower(), "")  # Empty not unknown

    def _parse_python_builtin(self, content: str) -> Optional[ast.AST]:
        """Parse Python code using built-in ast module."""
        try:
            return ast.parse(content)
        except SyntaxError:
            return None
    
    @lru_cache(maxsize=10000)
    def _parse_python_cached(self, content_hash: str, content: str) -> Optional[ast.AST]:
        """Parse Python code with caching based on content hash.
        
        Args:
            content_hash: MD5 hash of the file content
            content: The actual file content
            
        Returns:
            Parsed AST or None if parsing fails
        """
        return self._parse_python_builtin(content)
    
    @lru_cache(maxsize=10000)
    def _parse_treesitter_cached(self, content_hash: str, content: bytes, language: str) -> Any:
        """Parse code using Tree-sitter with caching based on content hash.
        
        Args:
            content_hash: MD5 hash of the file content
            content: The actual file content as bytes
            language: The programming language
            
        Returns:
            Parsed Tree-sitter tree
        """
        parser = self.parsers[language]
        return parser.parse(content)
    
    
    def supports_language(self, language: str) -> bool:
        """Check if a language is supported for AST parsing.

        Args:
            language: Programming language name.

        Returns:
            True if AST parsing is supported.
        """
        # Python is always supported via built-in ast module (NOT Tree-sitter)
        if language == "python":
            return True

        # JavaScript and TypeScript require semantic parser (NO FALLBACKS)
        if language in ["javascript", "typescript"]:
            return True  # Will fail loudly at parse time if semantic parser unavailable

        # Check Tree-sitter support for other languages
        if self.has_tree_sitter and language in self.parsers:
            return True

        return False
    
    def parse_content(self, content: str, language: str, filepath: str = "unknown", jsx_mode: str = 'transformed') -> Any:
        """Parse in-memory content into AST.

        Why: parse_file() reads from disk, but universal_detector already has content.
        This provides memory-based parsing with same infrastructure for both languages.

        Args:
            content: Source code as string
            language: Programming language ('python' or 'javascript')
            filepath: Original file path for error messages
            jsx_mode: JSX extraction mode ('preserved' or 'transformed')

        Returns:
            Dictionary with parsed AST or None if parsing fails
        """
        import tempfile
        
        # Hash for caching
        content_bytes = content.encode('utf-8')
        content_hash = hashlib.md5(content_bytes).hexdigest()
        
        # JavaScript/TypeScript REQUIRE semantic parser - NO FALLBACKS
        if language in ["javascript", "typescript"]:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Use semantic parser - MUST succeed
                try:
                    semantic_result = get_semantic_ast(tmp_path, jsx_mode=jsx_mode)
                except Exception as e:
                    raise RuntimeError(
                        f"FATAL: TypeScript semantic parser failed for {filepath}\n"
                        f"Error: {e}\n"
                        f"TypeScript/JavaScript files REQUIRE the semantic parser for correct analysis.\n"
                        f"Ensure Node.js is installed and run: aud setup-ai --target .\n"
                        f"DO NOT use fallback parsers - they produce corrupted data."
                    )

                if not (semantic_result and semantic_result.get("success")):
                    error_msg = semantic_result.get('error', 'Unknown error') if semantic_result else 'No result'
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
                    "content": content
                }
            finally:
                os.unlink(tmp_path)

        # PRIMARY PYTHON PARSER - CPython ast module (NOT a fallback!)
        # Python is NEVER parsed by Tree-sitter - CPython ast is the correct, intended tool.
        # This is the ONLY Python parsing path - intentional architectural decision.
        if language == "python":
            python_ast = self._parse_python_cached(content_hash, content)
            if python_ast:
                return {"type": "python_ast", "tree": python_ast, "language": language, "content": content}
        
        return None

    def parse_files_batch(self, file_paths: List[Path], root_path: str = None, jsx_mode: str = 'transformed') -> Dict[str, Any]:
        """Parse multiple files into ASTs in batch for performance.

        This method dramatically improves performance for JavaScript/TypeScript projects
        by processing multiple files in a single TypeScript compiler invocation.

        Args:
            file_paths: List of paths to source files
            root_path: Absolute path to project root (for sandbox resolution)
            jsx_mode: JSX extraction mode ('preserved' or 'transformed')

        Returns:
            Dictionary mapping file paths to their AST trees
        """
        results = {}

        # Separate files by language
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

        # Batch process JavaScript/TypeScript files if in a JS or polyglot project
        project_type = self._detect_project_type()
        if js_ts_files and project_type in ["javascript", "polyglot"] and get_semantic_ast_batch:
            try:
                # Convert paths to strings for the semantic parser with normalized separators
                js_ts_paths = []
                tsconfig_map: Dict[str, str] = {}
                for f in js_ts_files:
                    normalized_path = str(f).replace("\\", "/")
                    js_ts_paths.append(normalized_path)
                    tsconfig_for_file = self._find_tsconfig_for_file(f, root_path)
                    if tsconfig_for_file:
                        tsconfig_map[normalized_path] = str(tsconfig_for_file).replace("\\", "/")

                # Use batch processing for JS/TS files
                batch_results = get_semantic_ast_batch(
                    js_ts_paths,
                    project_root=root_path,
                    jsx_mode=jsx_mode,
                    tsconfig_map=tsconfig_map
                )

                # Process batch results
                for file_path in js_ts_files:
                    file_str = str(file_path).replace("\\", "/")  # Normalize for matching
                    if file_str in batch_results:
                        semantic_result = batch_results[file_str]
                        if semantic_result.get("success"):
                            # Read file content for inclusion
                            try:
                                with open(file_path, "rb") as f:
                                    content = f.read()

                                results[str(file_path).replace("\\", "/")] = {
                                    "type": "semantic_ast",
                                    "tree": semantic_result,
                                    "language": self._detect_language(file_path),
                                    "content": content.decode("utf-8", errors="ignore"),
                                    "has_types": semantic_result.get("hasTypes", False),
                                    "diagnostics": semantic_result.get("diagnostics", []),
                                    "symbols": semantic_result.get("symbols", [])
                                }
                            except Exception as e:
                                print(f"Warning: Failed to read {file_path}: {e}, falling back to individual parsing")
                                # CRITICAL FIX: Fall back to individual parsing on read failure
                                individual_result = self.parse_file(file_path, root_path=root_path, jsx_mode=jsx_mode)
                                results[str(file_path).replace("\\", "/")] = individual_result
                        else:
                            print(f"Warning: Semantic parser failed for {file_path}: {semantic_result.get('error')}, falling back to individual parsing")
                            # CRITICAL FIX: Fall back to individual parsing instead of None
                            individual_result = self.parse_file(file_path, root_path=root_path, jsx_mode=jsx_mode)
                            results[str(file_path).replace("\\", "/")] = individual_result
                    else:
                        # CRITICAL FIX: Fall back to individual parsing instead of None
                        print(f"Warning: No batch result for {file_path}, falling back to individual parsing")
                        individual_result = self.parse_file(file_path, root_path=root_path, jsx_mode=jsx_mode)
                        results[str(file_path).replace("\\", "/")] = individual_result

            except Exception as e:
                print(f"Warning: Batch processing failed for JS/TS files: {e}")
                # Fall back to individual processing
                for file_path in js_ts_files:
                    results[str(file_path).replace("\\", "/")] = self.parse_file(file_path, root_path=root_path, jsx_mode=jsx_mode)
        else:
            # Process JS/TS files individually if not in JS project or batch failed
            for file_path in js_ts_files:
                results[str(file_path).replace("\\", "/")] = self.parse_file(file_path, root_path=root_path, jsx_mode=jsx_mode)

        # Process Python files individually (they're fast enough)
        for file_path in python_files:
            results[str(file_path).replace("\\", "/")] = self.parse_file(file_path, root_path=root_path, jsx_mode=jsx_mode)

        # Process other files individually
        for file_path in other_files:
            results[str(file_path).replace("\\", "/")] = self.parse_file(file_path, root_path=root_path, jsx_mode=jsx_mode)

        return results

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages.

        Returns:
            List of language names.

        Note:
            JavaScript/TypeScript require semantic parser setup (run: aud setup-ai --target .)
            Will fail loudly at parse time if not configured.
        """
        # Python: always supported via built-in ast
        # JS/TS: supported but require semantic parser (will fail loudly if not available)
        languages = ["python", "javascript", "typescript"]

        if self.has_tree_sitter:
            languages.extend(self.parsers.keys())

        return sorted(set(languages))

    def _find_tsconfig_for_file(self, file_path: Path, root_path: Optional[str]) -> Optional[Path]:
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
                # Already checked project root, stop searching
                break

            if root_dir and not str(search_dir).startswith(str(root_dir)):
                break

            search_dir = search_dir.parent

        return None
