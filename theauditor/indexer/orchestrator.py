"""Indexer orchestration logic."""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from theauditor.ast_parser import ASTParser
from theauditor.config_runtime import load_runtime_config

from ..cache.ast_cache import ASTCache
from .config import DEFAULT_BATCH_SIZE, JS_BATCH_SIZE, SUPPORTED_AST_EXTENSIONS
from .core import FileWalker
from .database import DatabaseManager
from .exceptions import DataFidelityError
from .extractors import ExtractorRegistry
from .extractors.docker import DockerExtractor
from .extractors.generic import GenericExtractor
from .extractors.github_actions import GitHubWorkflowExtractor
from .fidelity import reconcile_fidelity
from .js_build_guard import JavaScriptBuildGuard, get_js_project_path
from .storage import DataStorer

logger = logging.getLogger(__name__)


class IndexerOrchestrator:
    """Orchestrates the indexing process, coordinating all components."""

    def __init__(
        self,
        root_path: Path,
        db_path: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        follow_symlinks: bool = False,
        exclude_patterns: list[str] | None = None,
    ):
        """Initialize the indexer orchestrator."""
        self.root_path = root_path
        self.config = load_runtime_config(str(root_path))

        self.ast_parser = ASTParser()

        cache_dir = root_path / ".pf" / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.ast_cache = ASTCache(cache_dir)
        self.db_manager = DatabaseManager(db_path, batch_size)
        self.file_walker = FileWalker(root_path, self.config, follow_symlinks, exclude_patterns)
        self.extractor_registry = ExtractorRegistry(root_path, self.ast_parser)

        self.docker_extractor = DockerExtractor(root_path, self.ast_parser)
        self.generic_extractor = GenericExtractor(root_path, self.ast_parser)
        self.github_workflow_extractor = GitHubWorkflowExtractor(root_path, self.ast_parser)

        self.docker_extractor.db_manager = self.db_manager
        self.generic_extractor.db_manager = self.db_manager
        self.github_workflow_extractor.db_manager = self.db_manager

        for ext in self.extractor_registry.extractors.values():
            if hasattr(ext, "extract") and not hasattr(ext, "db_manager"):
                import inspect

                source = inspect.getsource(ext.extract)
                if "self.db_manager" in source:
                    ext.db_manager = self.db_manager

        self.counts = {
            "files": 0,
            "refs": 0,
            "routes": 0,
            "sql": 0,
            "sql_queries": 0,
            "symbols": 0,
            "docker": 0,
            "orm": 0,
            "react_components": 0,
            "react_hooks": 0,
            "assignments": 0,
            "function_calls": 0,
            "returns": 0,
            "variable_usage": 0,
            "object_literals": 0,
            "cfg_blocks": 0,
            "cfg_edges": 0,
            "cfg_statements": 0,
            "type_annotations": 0,
            "type_annotations_typescript": 0,
            "type_annotations_python": 0,
            "type_annotations_rust": 0,
            "frameworks": 0,
            "package_configs": 0,
            "config_files": 0,
            "github_workflows": 0,
        }

        self.data_storer = DataStorer(self.db_manager, self.counts)

    def _detect_frameworks_inline(self) -> list[dict]:
        """Detect frameworks inline without file dependency."""
        from theauditor.framework_detector import FrameworkDetector

        try:
            detector = FrameworkDetector(self.root_path, exclude_patterns=[])
            frameworks = detector.detect_all()

            try:
                save_path = self.root_path / ".pf" / "raw" / "frameworks.json"
                save_path.parent.mkdir(parents=True, exist_ok=True)
                detector.save_to_file(save_path)
            except Exception as save_error:
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] Could not save frameworks.json: {save_error}")

            return frameworks

        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Framework detection failed: {e}")
            return []

    def _store_frameworks(self):
        """Store loaded frameworks in database."""
        for fw in self.frameworks:
            self.db_manager.add_framework(
                name=fw.get("framework"),
                version=fw.get("version"),
                language=fw.get("language"),
                path=fw.get("path", "."),
                source=fw.get("source"),
                is_primary=(fw.get("path", ".") == "."),
            )
            self.counts["frameworks"] += 1

        self.db_manager.flush_batch()
        self.db_manager.commit()

        self._seed_express_patterns()
        self._seed_flask_patterns()
        self._seed_django_patterns()

    def _seed_express_patterns(self):
        """Seed Express.js taint patterns (sources, sinks, safe sinks)."""
        if not any(fw.get("framework") == "express" for fw in self.frameworks):
            return

        conn = self.db_manager.conn
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM frameworks WHERE name = ? AND language = ?", ("express", "javascript")
        )
        result = cursor.fetchone()
        if not result:
            return

        express_id = result[0]

        safe_sinks = [
            ("res.json", "response", True, "JSON encoded response - auto-sanitized"),
            ("res.jsonp", "response", True, "JSONP callback - auto-sanitized"),
            ("res.status().json", "response", True, "JSON with status - auto-sanitized"),
        ]
        for pattern, sink_type, is_safe, reason in safe_sinks:
            self.db_manager.add_framework_safe_sink(express_id, pattern, sink_type, is_safe, reason)

        express_sources = [
            ("req.body", "http_request"),
            ("req.params", "http_request"),
            ("req.query", "http_request"),
            ("req.headers", "http_request"),
            ("req.cookies", "http_request"),
            ("req.files", "http_request"),
            ("req.file", "http_request"),
        ]
        for pattern, category in express_sources:
            self.db_manager.add_framework_taint_pattern(express_id, pattern, "source", category)

        express_sinks = [
            ("eval", "code_execution"),
            ("Function", "code_execution"),
            ("child_process.exec", "command_injection"),
            ("child_process.execSync", "command_injection"),
            ("child_process.spawn", "command_injection"),
            ("res.send", "xss"),
            ("res.write", "xss"),
            ("res.render", "xss"),
            ("res.redirect", "open_redirect"),
            ("query", "sql_injection"),
            ("execute", "sql_injection"),
            ("raw", "sql_injection"),
        ]
        for pattern, category in express_sinks:
            self.db_manager.add_framework_taint_pattern(express_id, pattern, "sink", category)

    def _seed_flask_patterns(self):
        """Seed Flask taint patterns (sources, sinks)."""
        if not any(fw.get("framework") == "flask" for fw in self.frameworks):
            return

        conn = self.db_manager.conn
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM frameworks WHERE name = ? AND language = ?", ("flask", "python")
        )
        result = cursor.fetchone()
        if not result:
            return

        flask_id = result[0]

        flask_sources = [
            ("request.args", "http_request"),
            ("request.form", "http_request"),
            ("request.json", "http_request"),
            ("request.data", "http_request"),
            ("request.values", "http_request"),
            ("request.files", "http_request"),
            ("request.cookies", "http_request"),
            ("request.headers", "http_request"),
        ]
        for pattern, category in flask_sources:
            self.db_manager.add_framework_taint_pattern(flask_id, pattern, "source", category)

        flask_sinks = [
            ("eval", "code_execution"),
            ("exec", "code_execution"),
            ("os.system", "command_injection"),
            ("subprocess.call", "command_injection"),
            ("subprocess.run", "command_injection"),
            ("subprocess.Popen", "command_injection"),
            ("render_template_string", "ssti"),
            ("cursor.execute", "sql_injection"),
            ("db.execute", "sql_injection"),
            ("open", "path_traversal"),
        ]
        for pattern, category in flask_sinks:
            self.db_manager.add_framework_taint_pattern(flask_id, pattern, "sink", category)

    def _seed_django_patterns(self):
        """Seed Django taint patterns (sources, sinks)."""
        if not any(fw.get("framework") == "django" for fw in self.frameworks):
            return

        conn = self.db_manager.conn
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM frameworks WHERE name = ? AND language = ?", ("django", "python")
        )
        result = cursor.fetchone()
        if not result:
            return

        django_id = result[0]

        django_sources = [
            ("request.GET", "http_request"),
            ("request.POST", "http_request"),
            ("request.body", "http_request"),
            ("request.FILES", "http_request"),
            ("request.COOKIES", "http_request"),
            ("request.META", "http_request"),
        ]
        for pattern, category in django_sources:
            self.db_manager.add_framework_taint_pattern(django_id, pattern, "source", category)

        django_sinks = [
            ("eval", "code_execution"),
            ("exec", "code_execution"),
            ("os.system", "command_injection"),
            ("cursor.execute", "sql_injection"),
            ("raw", "sql_injection"),
            ("extra", "sql_injection"),
            ("HttpResponse", "xss"),
            ("mark_safe", "xss"),
        ]
        for pattern, category in django_sinks:
            self.db_manager.add_framework_taint_pattern(django_id, pattern, "sink", category)

    def index(self) -> tuple[dict[str, int], dict[str, Any]]:
        """Run the complete indexing process."""

        from pathlib import Path

        from theauditor.indexer.schemas.codegen import SchemaCodeGenerator
        from theauditor.utils.exit_codes import ExitCodes

        current_hash = SchemaCodeGenerator.get_schema_hash()

        cache_file = Path(__file__).parent / "schemas" / "generated_cache.py"
        built_hash = None

        if cache_file.exists():
            with open(cache_file) as f:
                lines = f.readlines()
                if len(lines) >= 2 and "SCHEMA_HASH:" in lines[1]:
                    built_hash = lines[1].split("SCHEMA_HASH:")[1].strip()

        if current_hash != built_hash:
            print(
                "[SCHEMA STALE] Schema files have changed but generated code is out of date!",
                file=sys.stderr,
            )
            print("[SCHEMA STALE] Regenerating code automatically...", file=sys.stderr)

            try:
                output_dir = Path(__file__).parent / "schemas"
                SchemaCodeGenerator.write_generated_code(output_dir)
                print("[SCHEMA FIX] Generated code updated successfully", file=sys.stderr)
                print("[SCHEMA FIX] Please re-run the indexing command", file=sys.stderr)
                sys.exit(ExitCodes.SCHEMA_STALE)
            except Exception as e:
                print(f"[SCHEMA ERROR] Failed to regenerate code: {e}", file=sys.stderr)
                raise RuntimeError(f"Schema validation failed and auto-fix failed: {e}") from e

        js_guard = JavaScriptBuildGuard(get_js_project_path())
        if js_guard.ensure_up_to_date():
            print(
                "[JS GUARD] Extractor rebuilt. Please re-run the indexing command", file=sys.stderr
            )
            sys.exit(ExitCodes.SCHEMA_STALE)

        self.frameworks = self._detect_frameworks_inline()

        files, stats = self.file_walker.walk()

        if not files:
            print("[Indexer] No files found to index.")
            return self.counts, stats

        print(f"[Indexer] Processing {len(files)} files...")

        js_ts_files = []
        js_ts_cache = {}

        for file_info in files:
            if file_info["ext"] in [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]:
                file_path = self.root_path / file_info["path"]
                js_ts_files.append(file_path)

        if js_ts_files:
            print(f"[Indexer] Batch processing {len(js_ts_files)} JavaScript/TypeScript files...")

            for i in range(0, len(js_ts_files), JS_BATCH_SIZE):
                batch = js_ts_files[i : i + JS_BATCH_SIZE]
                batch_trees = self.ast_parser.parse_files_batch(
                    batch, root_path=str(self.root_path)
                )

                for file_path in batch:
                    file_str = str(file_path).replace("\\", "/")
                    if file_str in batch_trees:
                        js_ts_cache[file_str] = batch_trees[file_str]

            print(f"[Indexer] Successfully batch processed {len(js_ts_cache)} JS/TS files")

        for idx, file_info in enumerate(files):
            if os.environ.get("THEAUDITOR_DEBUG") and idx % 50 == 0:
                print(
                    f"[INDEXER_DEBUG] Processing file {idx + 1}/{len(files)}: {file_info['path']}",
                    file=sys.stderr,
                )

            self._process_file(file_info, js_ts_cache)

            file_path = self.root_path / file_info["path"]
            file_str = str(file_path).replace("\\", "/")
            if file_str in js_ts_cache:
                del js_ts_cache[file_str]

            if (idx + 1) % self.db_manager.batch_size == 0 or idx == len(files) - 1:
                self.db_manager.flush_batch()

        self.db_manager.commit()

        from datetime import datetime

        conn = self.db_manager.conn
        cursor = conn.cursor()

        cursor.execute("SELECT path, loc FROM files WHERE loc > 500")
        for row in cursor:
            self.db_manager.add_refactor_candidate(
                file_path=row[0],
                reason="size",
                severity="high" if row[1] > 1000 else "medium",
                loc=row[1],
                detected_at=datetime.now().isoformat(),
            )

        cursor.execute(
            "SELECT src, COUNT(*) as import_count FROM refs WHERE kind IN ('import', 'from', 'require') GROUP BY src HAVING import_count > 20"
        )
        for row in cursor:
            self.db_manager.add_refactor_candidate(
                file_path=row[0],
                reason="coupling",
                severity="medium",
                num_dependencies=row[1],
                detected_at=datetime.now().isoformat(),
            )

        self.db_manager.flush_batch()
        self.db_manager.commit()

        from theauditor.indexer.extractors.javascript import JavaScriptExtractor

        if os.environ.get("THEAUDITOR_DEBUG"):
            print("[INDEXER] PHASE 6: Resolving cross-file parameter names...", file=sys.stderr)
        JavaScriptExtractor.resolve_cross_file_parameters(self.db_manager.db_path)
        self.db_manager.commit()

        self.db_manager.flush_batch()
        self.db_manager.commit()

        if os.environ.get("THEAUDITOR_DEBUG"):
            print("[INDEXER] PHASE 6.7: Resolving router mount hierarchy...", file=sys.stderr)
        JavaScriptExtractor.resolve_router_mount_hierarchy(self.db_manager.db_path)
        self.db_manager.commit()

        self.db_manager.flush_batch()
        self.db_manager.commit()

        if os.environ.get("THEAUDITOR_DEBUG"):
            print("[INDEXER] PHASE 6.9: Resolving handler file paths...", file=sys.stderr)
        JavaScriptExtractor.resolve_handler_file_paths(self.db_manager.db_path)
        self.db_manager.commit()

        if os.environ.get("THEAUDITOR_DEBUG"):
            print("[INDEXER] PHASE 6.10: Resolving import paths...", file=sys.stderr)
        JavaScriptExtractor.resolve_import_paths(self.db_manager.db_path)
        self.db_manager.commit()

        base_msg = (
            f"[Indexer] Indexed {self.counts['files']} files, "
            f"{self.counts['symbols']} symbols, {self.counts['refs']} imports, "
            f"{self.counts['routes']} routes"
        )

        if self.counts.get("react_components", 0) > 0:
            base_msg += f", {self.counts['react_components']} React components"
        if self.counts.get("react_hooks", 0) > 0:
            base_msg += f", {self.counts['react_hooks']} React hooks"
        if self.counts.get("vue_components", 0) > 0:
            base_msg += f", {self.counts['vue_components']} Vue components"
        if self.counts.get("vue_hooks", 0) > 0:
            base_msg += f", {self.counts['vue_hooks']} Vue hooks"
        if self.counts.get("vue_directives", 0) > 0:
            base_msg += f", {self.counts['vue_directives']} Vue directives"

        annotation_summaries = []
        ts_annotations = self.counts.get("type_annotations_typescript", 0)
        py_annotations = self.counts.get("type_annotations_python", 0)
        rs_annotations = self.counts.get("type_annotations_rust", 0)
        if ts_annotations:
            annotation_summaries.append(f"{ts_annotations} TypeScript")
        if py_annotations:
            annotation_summaries.append(f"{py_annotations} Python")
        if rs_annotations:
            annotation_summaries.append(f"{rs_annotations} Rust")
        if annotation_summaries:
            base_msg += ", type annotations: " + ", ".join(annotation_summaries)

        print(base_msg)

        if self.counts.get("assignments", 0) > 0 or self.counts.get("function_calls", 0) > 0:
            flow_msg = "[Indexer] Data flow: "
            flow_parts = []
            if self.counts.get("assignments", 0) > 0:
                flow_parts.append(f"{self.counts['assignments']} assignments")
            if self.counts.get("function_calls", 0) > 0:
                flow_parts.append(f"{self.counts['function_calls']} function calls")
            if self.counts.get("returns", 0) > 0:
                flow_parts.append(f"{self.counts['returns']} returns")
            if self.counts.get("variable_usage", 0) > 0:
                flow_parts.append(f"{self.counts['variable_usage']} variable usages")
            if self.counts.get("object_literals", 0) > 0:
                flow_parts.append(f"{self.counts['object_literals']} object literal properties")
            print(f"{flow_msg}{', '.join(flow_parts)}")

        if self.counts.get("cfg_blocks", 0) > 0:
            cfg_msg = f"[Indexer] Control flow: {self.counts['cfg_blocks']} blocks, {self.counts['cfg_edges']} edges"
            if self.counts.get("cfg_statements", 0) > 0:
                cfg_msg += f", {self.counts['cfg_statements']} statements"
            print(cfg_msg)

        if self.counts.get("orm", 0) > 0 or self.counts.get("sql_queries", 0) > 0:
            db_msg = "[Indexer] Database: "
            db_parts = []
            if self.counts.get("orm", 0) > 0:
                db_parts.append(f"{self.counts['orm']} ORM queries")
            if self.counts.get("sql_queries", 0) > 0:
                db_parts.append(f"{self.counts['sql_queries']} SQL queries")
            print(f"{db_msg}{', '.join(db_parts)}")

        if (
            self.counts.get("compose", 0) > 0
            or self.counts.get("nginx", 0) > 0
            or self.counts.get("docker", 0) > 0
        ):
            infra_msg = "[Indexer] Infrastructure: "
            infra_parts = []
            if self.counts.get("docker", 0) > 0:
                infra_parts.append(f"{self.counts['docker']} Dockerfiles")
            if self.counts.get("compose", 0) > 0:
                infra_parts.append(f"{self.counts['compose']} compose services")
            if self.counts.get("nginx", 0) > 0:
                infra_parts.append(f"{self.counts['nginx']} nginx blocks")
            print(f"{infra_msg}{', '.join(infra_parts)}")

        if self.counts.get("frameworks", 0) > 0 or self.counts.get("package_configs", 0) > 0:
            config_msg = "[Indexer] Configuration: "
            config_parts = []
            if self.counts.get("frameworks", 0) > 0:
                config_parts.append(f"{self.counts['frameworks']} frameworks")
            if self.counts.get("package_configs", 0) > 0:
                config_parts.append(f"{self.counts['package_configs']} package configs")
            if self.counts.get("config_files", 0) > 0:
                config_parts.append(f"{self.counts['config_files']} config files")
            print(f"{config_msg}{', '.join(config_parts)}")

        print(f"[Indexer] Database updated: {self.db_manager.db_path}")

        if hasattr(self, "frameworks") and self.frameworks:
            self._store_frameworks()

        jsx_extensions = [".jsx", ".tsx"]
        jsx_files = [f for f in files if f["ext"] in jsx_extensions]

        if jsx_files:
            print(
                f"[Indexer] Second pass: Processing {len(jsx_files)} JSX/TSX files (preserved mode)..."
            )

            jsx_file_paths = [self.root_path / f["path"] for f in jsx_files]

            jsx_cache = {}
            try:
                for i in range(0, len(jsx_file_paths), JS_BATCH_SIZE):
                    batch = jsx_file_paths[i : i + JS_BATCH_SIZE]
                    batch_trees = self.ast_parser.parse_files_batch(
                        batch, root_path=str(self.root_path), jsx_mode="preserved"
                    )

                    for file_path in batch:
                        file_str = str(file_path).replace("\\", "/")
                        if file_str in batch_trees:
                            jsx_cache[file_str] = batch_trees[file_str]

                print(f"[Indexer] Parsed {len(jsx_cache)} JSX files in preserved mode")
            except Exception as e:
                print(f"[Indexer] WARNING: Preserved mode parsing failed: {e}")
                jsx_cache = {}

            jsx_counts = {"symbols": 0, "assignments": 0, "calls": 0, "returns": 0}

            for idx, file_info in enumerate(jsx_files):
                file_path = self.root_path / file_info["path"]
                file_str = str(file_path).replace("\\", "/")

                tree = jsx_cache.get(file_str)
                if not tree:
                    continue

                if os.environ.get("THEAUDITOR_DEBUG"):
                    has_ast = False
                    if isinstance(tree, dict):
                        if "ast" in tree:
                            has_ast = tree["ast"] is not None
                        elif "tree" in tree and isinstance(tree["tree"], dict):
                            has_ast = tree["tree"].get("ast") is not None
                    print(
                        f"[DEBUG] JSX pass - {Path(file_path).name}: has_ast={has_ast}, tree_keys={list(tree.keys())[:5] if isinstance(tree, dict) else 'not_dict'}"
                    )

                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        content = f.read(1024 * 1024)
                except Exception:
                    continue

                extractor = self.extractor_registry.get_extractor(file_path, file_info["ext"])
                if not extractor:
                    continue

                if isinstance(tree, dict) and tree.get("success") is False:
                    partial_data = tree.get("extracted_data")
                    if not partial_data:
                        actual_tree = (
                            tree.get("tree") if tree.get("type") == "semantic_ast" else tree
                        )
                        if isinstance(actual_tree, dict):
                            partial_data = actual_tree.get("extracted_data")

                    if partial_data and isinstance(partial_data, dict):
                        print(
                            f"[Indexer] JavaScript PARTIAL extraction for {file_path}: "
                            f"{tree.get('error')} - processing {len(partial_data)} data keys",
                            file=sys.stderr,
                        )

                    else:
                        print(
                            f"[Indexer] JavaScript extraction FAILED for {file_path}: {tree.get('error')}",
                            file=sys.stderr,
                        )
                        continue

                try:
                    extracted = extractor.extract(file_info, content, tree)
                except Exception as e:
                    if os.environ.get("THEAUDITOR_DEBUG"):
                        print(f"[DEBUG] JSX extraction failed for {file_path}: {e}")
                    continue

                file_path_str = file_info["path"]

                self.data_storer.store(file_path_str, extracted, jsx_pass=True)

                jsx_counts["symbols"] += len(extracted.get("symbols", []))
                jsx_counts["assignments"] += len(extracted.get("assignments", []))
                jsx_counts["calls"] += len(extracted.get("function_calls", []))
                jsx_counts["returns"] += len(extracted.get("returns", []))

                if file_str in jsx_cache:
                    del jsx_cache[file_str]

                if (idx + 1) % self.db_manager.batch_size == 0:
                    self.db_manager.flush_batch()

            self.db_manager.flush_batch()
            self.db_manager.commit()

            print(
                f"[Indexer] Second pass complete: {jsx_counts['symbols']} symbols, "
                f"{jsx_counts['assignments']} assignments, {jsx_counts['calls']} calls, "
                f"{jsx_counts['returns']} returns stored to _jsx tables"
            )

        self.db_manager.commit()

        self._cleanup_extractors()

        return self.counts, stats

    def _process_file(self, file_info: dict[str, Any], js_ts_cache: dict[str, Any]):
        """Process a single file."""

        if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
            print(f"[TRACE] _process_file() called for: {file_info['path']}", file=sys.stderr)

        self.db_manager.add_file(
            file_info["path"],
            file_info["sha256"],
            file_info["ext"],
            file_info["bytes"],
            file_info["loc"],
        )
        self.counts["files"] += 1

        file_path = self.root_path / file_info["path"]
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read(1024 * 1024)
        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"Debug: Cannot read {file_path}: {e}")
            return

        if file_info["path"].endswith("tsconfig.json"):
            context_dir = None
            if "backend/" in file_info["path"]:
                context_dir = "backend"
            elif "frontend/" in file_info["path"]:
                context_dir = "frontend"

            self.db_manager.add_config_file(file_info["path"], content, "tsconfig", context_dir)
            self.counts["config_files"] += 1
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Cached tsconfig: {file_info['path']} (context: {context_dir})")

        tree = self._get_or_parse_ast(file_info, file_path, js_ts_cache)

        extractor = self._select_extractor(file_info["path"], file_info["ext"])
        if not extractor:
            return

        if os.getenv("THEAUDITOR_DEBUG"):
            print(f"[DEBUG ORCHESTRATOR] _process_file called for: {file_info['path']}")

        try:
            extracted = extractor.extract(file_info, content, tree)
        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"Debug: Extraction failed for {file_path}: {e}")
            return

        if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
            num_assignments = len(extracted.get("assignments", []))
            print(
                f"[TRACE] _store_extracted_data() called for {file_info['path']}: {num_assignments} assignments",
                file=sys.stderr,
            )
        self._store_extracted_data(file_info["path"], extracted)

    def _get_or_parse_ast(
        self, file_info: dict[str, Any], file_path: Path, js_ts_cache: dict[str, Any]
    ) -> dict | None:
        """Get AST from cache or parse the file."""
        # 1. Check extension support
        if file_info["ext"] not in SUPPORTED_AST_EXTENSIONS:
            return None

        # 2. Check JS/TS cache (from batch processing)
        file_str = str(file_path).replace("\\", "/")
        if file_str in js_ts_cache:
            return js_ts_cache[file_str]

        # 3. Check persistent AST cache (disk)
        cached_tree = self.ast_cache.get(file_info["sha256"])
        if cached_tree:
            return cached_tree

        # 4. PARSE THE FILE (This is the changed part)
        try:
            tree = self.ast_parser.parse_file(file_path, root_path=str(self.root_path))

        except RuntimeError as e:
            # FIX: Catch the "FATAL" error from ast_parser and turn it into a finding
            error_msg = str(e)

            # Try to grab the line number if it's in the error message
            line_no = 1
            if "line " in error_msg:
                try:
                    import re

                    match = re.search(r"line (\d+)", error_msg)
                    if match:
                        line_no = int(match.group(1))
                except Exception:
                    pass

            # Record the syntax error in the findings table
            self.db_manager.write_findings_batch(
                [
                    {
                        "file": str(file_path),
                        "line": line_no,
                        "rule": "syntax_error",
                        "tool": "indexer",
                        "severity": "error",
                        "message": f"Syntax Error: {error_msg}",
                        "category": "syntax",
                    }
                ],
                "indexer",
            )

            # Return None means "no AST available", but don't crash!
            return None

        # 5. Cache successful results
        if tree and isinstance(tree, dict):
            self.ast_cache.set(file_info["sha256"], tree)

        return tree

    def _select_extractor(self, file_path: str, file_ext: str):
        """Select the appropriate extractor for a file."""

        if self.docker_extractor.should_extract(file_path):
            return self.docker_extractor
        if self.github_workflow_extractor.should_extract(file_path):
            return self.github_workflow_extractor
        if self.generic_extractor.should_extract(file_path):
            return self.generic_extractor

        return self.extractor_registry.get_extractor(file_path, file_ext)

    def _store_extracted_data(self, file_path: str, extracted: dict[str, Any]):
        """Store extracted data in the database - DELEGATED TO DataStorer."""

        receipt = self.data_storer.store(file_path, extracted, jsx_pass=False)

        manifest = extracted.get("_extraction_manifest")

        if manifest:
            try:
                reconcile_fidelity(
                    manifest=manifest, receipt=receipt, file_path=file_path, strict=True
                )
            except DataFidelityError as e:
                logger.error(f"[FATAL] Fidelity Check Failed for {file_path}: {e}")
                raise

    def _cleanup_extractors(self):
        """Call cleanup() on all registered extractors."""

        for extractor in self.extractor_registry.extractors.values():
            try:
                extractor.cleanup()
            except Exception as e:
                logger.debug(f"Extractor cleanup failed: {e}")

        try:
            self.docker_extractor.cleanup()
        except Exception as e:
            logger.debug(f"Docker extractor cleanup failed: {e}")

        try:
            self.generic_extractor.cleanup()
        except Exception as e:
            logger.debug(f"Generic extractor cleanup failed: {e}")
