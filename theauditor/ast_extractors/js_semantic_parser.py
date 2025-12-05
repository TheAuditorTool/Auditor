"""JavaScript/TypeScript semantic parser using the TypeScript Compiler API."""

import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from theauditor.ast_extractors import js_helper_templates
from theauditor.utils.logging import logger

try:
    from theauditor.utils.temp_manager import TempManager
except ImportError:
    TempManager = None


IS_WINDOWS = platform.system() == "Windows"


_module_resolver_cache = None


_parser_cache = {}


_cache_stats = {"hits": 0, "misses": 0}


class JSSemanticParser:
    """Semantic parser for JavaScript/TypeScript using the TypeScript Compiler API."""

    def __init__(self, project_root: str = None):
        """Initialize the semantic parser."""
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
        self.using_windows_node = False
        self.tsc_path = None
        self.node_modules_path = None
        self.project_module_type = self._detect_module_type()

        if os.environ.get("THEAUDITOR_DEBUG"):
            import traceback

            stack = traceback.extract_stack()
            caller = stack[-2] if len(stack) > 1 else None
            if caller:
                logger.debug(
                    f"JSSemanticParser.__init__ called from {caller.filename}:{caller.lineno}"
                )
            logger.debug(f"Created JSSemanticParser for project: {self.project_root}")
            if self.project_module_type == "module":
                logger.debug("Detected ES module project (package.json has 'type': 'module')")

        global _module_resolver_cache
        if _module_resolver_cache is None:
            from .module_resolver import ModuleResolver

            _module_resolver_cache = ModuleResolver()

        self.module_resolver = _module_resolver_cache

        search_dir = self.project_root
        sandbox_base = None

        for _ in range(10):
            potential_venv = search_dir / ".auditor_venv" / ".theauditor_tools"
            if potential_venv.exists():
                sandbox_base = potential_venv
                break
            parent = search_dir.parent
            if parent == search_dir:
                break
            search_dir = parent

        if sandbox_base is None:
            sandbox_base = self.project_root / ".auditor_venv" / ".theauditor_tools"

        node_runtime = sandbox_base / "node-runtime"

        possible_node_paths = [
            node_runtime / "node.exe",
            node_runtime / "node",
            node_runtime / "bin" / "node",
            node_runtime / "bin" / "node.exe",
        ]

        self.node_exe = None
        for node_path in possible_node_paths:
            if node_path.exists():
                self.node_exe = node_path

                self.using_windows_node = str(node_path).endswith(".exe") and str(
                    node_path
                ).startswith("/")
                break

        self.tsc_available = self._check_tsc_availability()

        self.helper_script = None
        self.batch_helper_script = self._create_batch_helper_script()

    def _detect_module_type(self) -> str:
        """Detect the project's module type from package.json."""
        try:
            package_json_path = self.project_root / "package.json"
            if package_json_path.exists():
                with open(package_json_path, encoding="utf-8") as f:
                    package_data = json.load(f)
                    module_type = package_data.get("type", "commonjs")
                    if module_type == "module":
                        return "module"

            return "commonjs"
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Could not detect module type: {e}. Defaulting to CommonJS.")
            return "commonjs"

    def _convert_path_for_node(self, path: Path) -> str:
        """Convert path to appropriate format for node execution."""
        path_str = str(path)
        if self.using_windows_node:
            try:
                import subprocess as sp

                result = sp.run(
                    ["wslpath", "-w", path_str], capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass
        return path_str

    def _check_tsc_availability(self) -> bool:
        """Check if TypeScript compiler is available in our sandbox."""

        search_dir = self.project_root
        sandbox_base = None

        for _ in range(10):
            potential_venv = search_dir / ".auditor_venv" / ".theauditor_tools" / "node_modules"
            if potential_venv.exists():
                sandbox_base = potential_venv
                break
            parent = search_dir.parent
            if parent == search_dir:
                break
            search_dir = parent

        if sandbox_base is None:
            sandbox_base = (
                self.project_root / ".auditor_venv" / ".theauditor_tools" / "node_modules"
            )

        sandbox_locations = [sandbox_base]

        for sandbox_base in sandbox_locations:
            if not sandbox_base.exists():
                continue

            tsc_js_path = sandbox_base / "typescript" / "lib" / "tsc.js"

            if self.node_exe and tsc_js_path.exists():
                try:
                    absolute_sandbox = sandbox_base.resolve()

                    if TempManager:
                        stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                            str(self.project_root), "tsc_verify"
                        )
                        with (
                            open(stdout_path, "w+", encoding="utf-8") as stdout_fp,
                            open(stderr_path, "w+", encoding="utf-8") as stderr_fp,
                        ):
                            pass
                    else:
                        with (
                            tempfile.NamedTemporaryFile(
                                mode="w+", delete=False, suffix="_stdout.txt", encoding="utf-8"
                            ) as stdout_fp,
                            tempfile.NamedTemporaryFile(
                                mode="w+", delete=False, suffix="_stderr.txt", encoding="utf-8"
                            ) as stderr_fp,
                        ):
                            stdout_path = stdout_fp.name
                            stderr_path = stderr_fp.name

                    with (
                        open(stdout_path, "w+", encoding="utf-8") as stdout_fp,
                        open(stderr_path, "w+", encoding="utf-8") as stderr_fp,
                    ):
                        tsc_path_str = self._convert_path_for_node(tsc_js_path)

                        result = subprocess.run(
                            [str(self.node_exe), tsc_path_str, "--version"],
                            stdout=stdout_fp,
                            stderr=stderr_fp,
                            text=True,
                            timeout=5,
                            env={**os.environ, "NODE_PATH": str(absolute_sandbox)},
                            shell=False,
                        )

                        with open(stdout_path, encoding="utf-8") as f:
                            result.stdout = f.read()
                        with open(stderr_path, encoding="utf-8") as f:
                            result.stderr = f.read()

                    os.unlink(stdout_path)
                    os.unlink(stderr_path)
                    if result.returncode == 0:
                        self.tsc_path = tsc_js_path
                        self.node_modules_path = absolute_sandbox
                        return True
                except (subprocess.SubprocessError, FileNotFoundError, OSError):
                    pass

        return False

    def _create_helper_script(self) -> Path:
        """DEPRECATED: Single-file mode removed in Phase 5."""
        raise RuntimeError(
            "Single-file mode removed in Phase 5. Single-file templates serialize full AST (512MB crash). "
            "Use _create_batch_helper_script() instead (sets ast: null)."
        )

    def _create_batch_helper_script(self) -> Path:
        """Create a Node.js helper script for batch TypeScript AST extraction."""
        pf_dir = self.project_root / ".pf"
        pf_dir.mkdir(exist_ok=True)

        batch_helper_path = pf_dir / "tsc_batch_helper.cjs"

        if self.project_module_type == "module":
            batch_helper_content = js_helper_templates.get_batch_helper("module")
        else:
            batch_helper_content = js_helper_templates.get_batch_helper("commonjs")

        batch_helper_path.write_text(batch_helper_content, encoding="utf-8")
        return batch_helper_path

    def get_semantic_ast_batch(
        self,
        file_paths: list[str],
        jsx_mode: str = "transformed",
        tsconfig_map: dict[str, str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Get semantic ASTs for multiple JavaScript/TypeScript files in a single process."""

        results = {}
        valid_files = []

        normalized_tsconfig_map: dict[str, str] = {}
        tsconfig_map = tsconfig_map or {}

        for file_path in file_paths:
            file = Path(file_path).resolve()
            if not file.exists():
                results[file_path] = {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": [],
                }
            elif file.suffix.lower() not in [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue"]:
                results[file_path] = {
                    "success": False,
                    "error": f"Not a JavaScript/TypeScript file: {file_path}",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": [],
                }
            else:
                resolved_file = file.resolve()
                normalized_path = str(resolved_file).replace("\\", "/")
                valid_files.append(normalized_path)

                config_path = (
                    tsconfig_map.get(file_path)
                    or tsconfig_map.get(str(file_path))
                    or tsconfig_map.get(normalized_path)
                )
                if config_path:
                    normalized_tsconfig_map[normalized_path] = str(
                        Path(config_path).resolve()
                    ).replace("\\", "/")

        if not valid_files:
            return results

        if not self.tsc_available:
            for file_path in valid_files:
                results[file_path] = {
                    "success": False,
                    "error": "TypeScript compiler not available in TheAuditor sandbox. Run 'aud setup-ai' to install tools.",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": [],
                }
            return results

        try:
            batch_request = {
                "files": valid_files,
                "projectRoot": str(self.project_root),
                "jsxMode": jsx_mode,
                "configMap": normalized_tsconfig_map,
            }

            if TempManager:
                request_path, req_fd = TempManager.create_temp_file(
                    str(self.project_root), suffix="_request.json"
                )
                os.close(req_fd)
                output_path, out_fd = TempManager.create_temp_file(
                    str(self.project_root), suffix="_output.json"
                )
                os.close(out_fd)
            else:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False, encoding="utf-8"
                ) as tmp_req:
                    request_path = tmp_req.name
                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".json", delete=False, encoding="utf-8"
                ) as tmp_out:
                    output_path = tmp_out.name

            with open(request_path, "w", encoding="utf-8") as f:
                json.dump(batch_request, f)

            dynamic_timeout = min(5 + (len(valid_files) * 2), 120)

            try:
                helper_path = self._convert_path_for_node(self.batch_helper_script.resolve())
                request_path_converted = self._convert_path_for_node(Path(request_path))
                output_path_converted = self._convert_path_for_node(Path(output_path))

                if not self.node_exe:
                    raise RuntimeError(
                        "Node.js runtime not found. Run 'aud setup-ai' to install tools."
                    )

                result = subprocess.run(
                    [
                        str(self.node_exe),
                        helper_path,
                        request_path_converted,
                        output_path_converted,
                    ],
                    capture_output=False,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=dynamic_timeout,
                    cwd=self.project_root,
                    shell=IS_WINDOWS,
                )

                if result.returncode != 0:
                    error_msg = f"Batch TypeScript compiler failed (exit code {result.returncode})"
                    if result.stderr:
                        error_msg += f": {result.stderr.strip()[:500]}"

                    for file_path in valid_files:
                        results[file_path] = {
                            "success": False,
                            "error": error_msg,
                            "ast": None,
                            "diagnostics": [],
                            "symbols": [],
                        }
                else:
                    if os.environ.get("THEAUDITOR_DEBUG") and result.stderr:
                        logger.debug(f"{result.stderr}")

                    if Path(output_path).exists():
                        with open(output_path, encoding="utf-8") as f:
                            batch_results = json.load(f)

                        def _normalize(path_str: str) -> str:
                            normalized = path_str.replace("\\", "/")
                            try:
                                resolved = Path(path_str).resolve()
                                normalized_resolved = str(resolved).replace("\\", "/")
                                return normalized_resolved or normalized
                            except OSError:
                                return normalized

                        normalized_results: dict[str, dict[str, Any]] = {}
                        for key, value in batch_results.items():
                            candidates = {key, key.replace("\\", "/"), _normalize(key)}
                            for candidate in candidates:
                                normalized_results[candidate] = value

                        for file_path in file_paths:
                            candidate_keys = [
                                file_path,
                                file_path.replace("\\", "/"),
                                _normalize(file_path),
                            ]

                            matched = False
                            for candidate in candidate_keys:
                                if candidate in normalized_results:
                                    results[file_path] = normalized_results[candidate]
                                    matched = True
                                    break

                            if not matched and file_path not in results:
                                results[file_path] = {
                                    "success": False,
                                    "error": "File not processed in batch",
                                    "ast": None,
                                    "diagnostics": [],
                                    "symbols": [],
                                }
                    else:
                        for file_path in valid_files:
                            results[file_path] = {
                                "success": False,
                                "error": "Batch output file not created",
                                "ast": None,
                                "diagnostics": [],
                                "symbols": [],
                            }
            finally:
                for temp_path in [request_path, output_path]:
                    if Path(temp_path).exists():
                        Path(temp_path).unlink()

        except subprocess.TimeoutExpired:
            for file_path in valid_files:
                results[file_path] = {
                    "success": False,
                    "error": f"Batch timeout: Files too large or complex to parse within {dynamic_timeout:.0f} seconds",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": [],
                }
        except Exception as e:
            for file_path in valid_files:
                results[file_path] = {
                    "success": False,
                    "error": f"Unexpected error in batch processing: {e}",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": [],
                }

        return results

    def get_semantic_ast(
        self, file_path: str, jsx_mode: str = "transformed", tsconfig_path: str | None = None
    ) -> dict[str, Any]:
        """Get semantic AST for a JavaScript/TypeScript file using the TypeScript compiler."""

        if jsx_mode not in ["preserved", "transformed"]:
            return {
                "success": False,
                "error": f"Invalid jsx_mode: {jsx_mode}. Must be 'preserved' or 'transformed'",
                "ast": None,
                "diagnostics": [],
                "symbols": [],
                "jsx_mode": jsx_mode,
            }

        file = Path(file_path).resolve()
        if not file.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "ast": None,
                "diagnostics": [],
                "symbols": [],
                "jsx_mode": jsx_mode,
            }

        if file.suffix.lower() not in [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue"]:
            return {
                "success": False,
                "error": f"Not a JavaScript/TypeScript file: {file_path}",
                "ast": None,
                "diagnostics": [],
                "symbols": [],
                "jsx_mode": jsx_mode,
            }

        if not self.tsc_available:
            return {
                "success": False,
                "error": "TypeScript compiler not available in TheAuditor sandbox. Run 'aud setup-ai' to install tools.",
                "ast": None,
                "diagnostics": [],
                "symbols": [],
                "jsx_mode": jsx_mode,
            }

        try:
            helper_absolute = str(self.helper_script.resolve()).replace("\\", "/")

            file_size_kb = file.stat().st_size / 1024
            dynamic_timeout = min(10 + (file_size_kb / 10), 60)

            if TempManager:
                tmp_output_path, out_fd = TempManager.create_temp_file(
                    str(self.project_root), suffix="_ast_output.json"
                )
                os.close(out_fd)
            else:
                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".json", delete=False, encoding="utf-8"
                ) as tmp_out:
                    tmp_output_path = tmp_out.name

            if not self.node_exe:
                return {
                    "success": False,
                    "error": "Node.js runtime not found. Run 'aud setup-ai' to install tools.",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": [],
                    "jsx_mode": jsx_mode,
                }

            helper_path_converted = self._convert_path_for_node(Path(helper_absolute))
            file_path_converted = self._convert_path_for_node(file.resolve())
            output_path_converted = self._convert_path_for_node(Path(tmp_output_path))

            project_root_converted = self._convert_path_for_node(self.project_root)
            tsconfig_path_converted = ""
            if tsconfig_path:
                try:
                    tsconfig_path_converted = self._convert_path_for_node(
                        Path(tsconfig_path).resolve()
                    )
                except OSError:
                    tsconfig_path_converted = tsconfig_path

            result = subprocess.run(
                [
                    str(self.node_exe),
                    helper_path_converted,
                    file_path_converted,
                    output_path_converted,
                    project_root_converted,
                    jsx_mode,
                    tsconfig_path_converted,
                ],
                capture_output=False,
                stderr=subprocess.PIPE,
                text=True,
                timeout=dynamic_timeout,
                cwd=file.parent,
                shell=IS_WINDOWS,
            )

            try:
                if result.returncode != 0:
                    error_json = None

                    if result.stderr and result.stderr.strip():
                        try:
                            error_json = json.loads(result.stderr)
                        except json.JSONDecodeError:
                            pass

                    if error_json and isinstance(error_json, dict):
                        error_msg = error_json.get(
                            "error", "Unknown error from TypeScript compiler"
                        )
                    else:
                        error_details = []
                        if result.stderr and result.stderr.strip():
                            error_details.append(f"stderr: {result.stderr.strip()[:500]}")
                        if not error_details:
                            error_details.append("No error output from TypeScript compiler")

                        error_msg = (
                            f"TypeScript compiler failed (exit code {result.returncode}). "
                            + " | ".join(error_details)
                        )

                    return {
                        "success": False,
                        "error": error_msg,
                        "ast": None,
                        "diagnostics": [],
                        "symbols": [],
                        "jsx_mode": jsx_mode,
                    }
                else:
                    if not Path(tmp_output_path).exists():
                        return {
                            "success": False,
                            "error": "TypeScript compiler succeeded but output file was not created",
                            "ast": None,
                            "diagnostics": [],
                            "symbols": [],
                            "jsx_mode": jsx_mode,
                        }

                    try:
                        with open(tmp_output_path, encoding="utf-8") as f:
                            ast_data = json.load(f)

                        ast_data["jsx_mode"] = jsx_mode
                        return ast_data
                    except json.JSONDecodeError as e:
                        file_size = Path(tmp_output_path).stat().st_size
                        return {
                            "success": False,
                            "error": f"Failed to parse TypeScript AST output: {e}. Output file size: {file_size} bytes",
                            "ast": None,
                            "diagnostics": [],
                            "symbols": [],
                            "jsx_mode": jsx_mode,
                        }
            finally:
                if Path(tmp_output_path).exists():
                    Path(tmp_output_path).unlink()

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Timeout: File too large or complex to parse within {dynamic_timeout:.0f} seconds",
                "ast": None,
                "diagnostics": [],
                "symbols": [],
                "jsx_mode": jsx_mode,
            }
        except subprocess.SubprocessError as e:
            return {
                "success": False,
                "error": f"Subprocess error: {e}",
                "ast": None,
                "diagnostics": [],
                "symbols": [],
                "jsx_mode": jsx_mode,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {e}",
                "ast": None,
                "diagnostics": [],
                "symbols": [],
                "jsx_mode": jsx_mode,
            }

    def resolve_imports(self, ast_data: dict[str, Any], current_file: str) -> dict[str, str]:
        """Resolve import statements in the AST using ModuleResolver."""
        resolved_imports = {}

        if not ast_data.get("success") or not ast_data.get("ast"):
            return resolved_imports

        def find_imports(node, depth=0):
            if depth > 100 or not isinstance(node, dict):
                return

            kind = node.get("kind")

            if kind == "ImportDeclaration":
                module_specifier = node.get("moduleSpecifier", {})
                if isinstance(module_specifier, dict):
                    import_path = module_specifier.get("text", "")
                    if import_path:
                        resolved = self.module_resolver.resolve(import_path, current_file)
                        if resolved:
                            resolved_imports[import_path] = resolved
                        logger.debug(f"Failed to resolve '{import_path}' from '{current_file}'")

            elif kind == "CallExpression":
                expression = node.get("expression", {})
                if isinstance(expression, dict) and expression.get("text") == "require":
                    arguments = node.get("arguments", [])
                    if arguments and isinstance(arguments[0], dict):
                        import_path = arguments[0].get("text", "")
                        if import_path:
                            resolved = self.module_resolver.resolve(import_path, current_file)
                            if resolved:
                                resolved_imports[import_path] = resolved
                            logger.debug(
                                f"Failed to resolve require('{import_path}') from '{current_file}'"
                            )

            for child in node.get("children", []):
                find_imports(child, depth + 1)

        find_imports(ast_data.get("ast", {}))

        if os.environ.get("THEAUDITOR_DEBUG") and resolved_imports:
            logger.debug(f"Resolved {len(resolved_imports)} imports in {current_file}")
            for imp, resolved in list(resolved_imports.items())[:3]:
                logger.debug(f"'{imp}' -> '{resolved}'")

        return resolved_imports

    def extract_type_issues(self, ast_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract type-related issues from the semantic AST."""
        issues = []

        if not ast_data.get("success") or not ast_data.get("ast"):
            return issues

        for symbol in ast_data.get("symbols", []):
            if symbol.get("type") == "any":
                issues.append(
                    {
                        "type": "any_type",
                        "name": symbol.get("name"),
                        "line": symbol.get("line"),
                        "severity": "warning",
                        "message": f"Symbol '{symbol.get('name')}' has type 'any'",
                    }
                )

        for diagnostic in ast_data.get("diagnostics", []):
            if diagnostic.get("category") == "Error":
                issues.append(
                    {
                        "type": "type_error",
                        "line": diagnostic.get("line"),
                        "column": diagnostic.get("column"),
                        "severity": "error",
                        "message": diagnostic.get("message"),
                        "code": diagnostic.get("code"),
                    }
                )

        def search_ast(node, depth=0):
            if depth > 100 or not isinstance(node, dict):
                return

            if node.get("kind") == "AnyKeyword":
                issues.append(
                    {
                        "type": "any_type",
                        "line": node.get("line"),
                        "column": node.get("column"),
                        "severity": "warning",
                        "message": "Explicit 'any' type annotation",
                        "text": node.get("text", "")[:100],
                    }
                )

            if node.get("kind") == "AsExpression":
                type_node = node.get("type", {})
                if type_node.get("kind") in ["AnyKeyword", "UnknownKeyword"]:
                    issues.append(
                        {
                            "type": "unsafe_cast",
                            "line": node.get("line"),
                            "column": node.get("column"),
                            "severity": "warning",
                            "message": f"Unsafe type assertion to '{type_node.get('kind')}'",
                            "text": node.get("text", "")[:100],
                        }
                    )

            text = node.get("text", "")
            if "@ts-ignore" in text or "@ts-nocheck" in text:
                issues.append(
                    {
                        "type": "type_suppression",
                        "line": node.get("line"),
                        "column": node.get("column"),
                        "severity": "warning",
                        "message": "TypeScript error suppression comment",
                        "text": text[:100],
                    }
                )

            for child in node.get("children", []):
                search_ast(child, depth + 1)

        search_ast(ast_data.get("ast", {}))

        return issues


def get_semantic_ast(
    file_path: str,
    project_root: str = None,
    jsx_mode: str = "transformed",
    tsconfig_path: str | None = None,
) -> dict[str, Any]:
    """Get semantic AST for a JavaScript/TypeScript file."""

    cache_key = str(Path(project_root).resolve() if project_root else Path.cwd().resolve())
    if cache_key not in _parser_cache:
        _cache_stats["misses"] += 1
        _parser_cache[cache_key] = JSSemanticParser(project_root=project_root)
        if os.environ.get("THEAUDITOR_DEBUG"):
            logger.debug(f"Cache MISS - Created new JSSemanticParser for {cache_key}")
            logger.debug(
                f"Cache stats: {_cache_stats['hits']} hits, {_cache_stats['misses']} misses"
            )
    else:
        _cache_stats["hits"] += 1
        if os.environ.get("THEAUDITOR_DEBUG") and _cache_stats["hits"] % 10 == 0:
            logger.debug(
                f"Cache HIT #{_cache_stats['hits']} - Reusing JSSemanticParser for {cache_key}"
            )
    parser = _parser_cache[cache_key]
    return parser.get_semantic_ast(file_path, jsx_mode, tsconfig_path)


def get_semantic_ast_batch(
    file_paths: list[str],
    project_root: str = None,
    jsx_mode: str = "transformed",
    tsconfig_map: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Get semantic ASTs for multiple JavaScript/TypeScript files in batch."""

    cache_key = str(Path(project_root).resolve() if project_root else Path.cwd().resolve())
    if cache_key not in _parser_cache:
        _cache_stats["misses"] += 1
        _parser_cache[cache_key] = JSSemanticParser(project_root=project_root)
        if os.environ.get("THEAUDITOR_DEBUG"):
            logger.debug(f"Cache MISS - Created new JSSemanticParser for {cache_key}")
            logger.debug(
                f"Cache stats: {_cache_stats['hits']} hits, {_cache_stats['misses']} misses"
            )
    else:
        _cache_stats["hits"] += 1
        if os.environ.get("THEAUDITOR_DEBUG") and _cache_stats["hits"] % 10 == 0:
            logger.debug(
                f"Cache HIT #{_cache_stats['hits']} - Reusing JSSemanticParser for {cache_key}"
            )
    parser = _parser_cache[cache_key]
    return parser.get_semantic_ast_batch(file_paths, jsx_mode, tsconfig_map)
