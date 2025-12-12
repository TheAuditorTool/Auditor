"""Unified orchestrator for dynamic rule discovery and execution."""

import importlib
import inspect
import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from theauditor.rules.base import convert_old_context, validate_rule_signature
from theauditor.rules.fidelity import RuleResult, verify_fidelity
from theauditor.utils.logging import logger


@dataclass
class RuleInfo:
    """Metadata about a discovered rule."""

    name: str
    module: str
    function: Callable
    signature: inspect.Signature
    category: str
    is_standardized: bool = False
    requires_ast: bool = False
    requires_db: bool = False
    requires_file: bool = False
    requires_content: bool = False
    param_count: int = 0
    param_names: list[str] = field(default_factory=list)
    rule_type: str = "standalone"
    execution_scope: str = "database"


@dataclass
class RuleContext:
    """Context information for rule execution."""

    file_path: Path | None = None
    content: str | None = None
    ast_tree: Any | None = None
    language: str | None = None
    db_path: str | None = None
    project_path: Path | None = None


class RulesOrchestrator:
    """Unified orchestrator for ALL rule execution."""

    def __init__(self, project_path: Path, db_path: Path = None):
        """Initialize the orchestrator."""
        self.project_path = Path(project_path)
        self.db_path = Path(db_path) if db_path else self.project_path / ".pf" / "repo_index.db"
        self._debug = os.environ.get("THEAUDITOR_DEBUG", "").lower() == "true"
        self.rules = self._discover_all_rules()

        self.taint_registry = None
        self._taint_trace_func = None
        self._taint_conn = None
        self._fidelity_failures: list[tuple[str, list[str]]] = []

        if self._debug:
            total_rules = sum(len(r) for r in self.rules.values())
            logger.info(f"Discovered {total_rules} rules across {len(self.rules)} categories")

    def _discover_all_rules(self) -> dict[str, list[RuleInfo]]:
        """Dynamically discover ALL rules in /rules directory."""
        rules_by_category = {}

        import theauditor.rules as rules_package

        rules_dir = Path(rules_package.__file__).parent

        for subdir in rules_dir.iterdir():
            if not subdir.is_dir() or subdir.name.startswith("__"):
                continue

            category = subdir.name
            rules_by_category[category] = []

            for py_file in subdir.glob("*.py"):
                if py_file.name.startswith("__"):
                    continue

                module_name = f"theauditor.rules.{category}.{py_file.stem}"

                try:
                    module = importlib.import_module(module_name)

                    for name, obj in inspect.getmembers(module, inspect.isfunction):
                        if (
                            name.startswith("find_") or name == "analyze"
                        ) and obj.__module__ == module_name:
                            rule_info = self._analyze_rule(name, obj, module, module_name, category)
                            rules_by_category[category].append(rule_info)

                except ImportError as e:
                    if self._debug:
                        logger.info(f"Failed to import {module_name}: {e}")
                except Exception as e:
                    if self._debug:
                        logger.info(f"Error processing {module_name}: {e}")

        return rules_by_category

    def _analyze_rule(
        self, name: str, func: Callable, module_obj: Any, module_name: str, category: str
    ) -> RuleInfo:
        """Analyze a rule function to determine its requirements."""
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        metadata = getattr(module_obj, "METADATA", None)

        is_standardized = validate_rule_signature(func)

        execution_scope = "database" if is_standardized else "file"
        if metadata is not None:
            execution_scope = (
                getattr(metadata, "execution_scope", execution_scope) or execution_scope
            )

        if execution_scope not in {"database", "file"}:
            execution_scope = "database" if is_standardized else "file"

        if is_standardized:
            return RuleInfo(
                name=name,
                module=module_name,
                function=func,
                signature=sig,
                category=category,
                is_standardized=True,
                requires_ast=False,
                requires_db=execution_scope == "database",
                requires_file=execution_scope == "file",
                requires_content=execution_scope == "file",
                param_count=1,
                param_names=["context"],
                rule_type="standard",
                execution_scope=execution_scope,
            )

        requires_ast = any(p in ["ast", "tree", "ast_tree", "python_ast"] for p in params)
        requires_db_param = any(p in ["db_path", "database", "conn"] for p in params)
        requires_file_param = any(
            p in ["file_path", "filepath", "path", "filename"] for p in params
        )
        requires_content_param = any(p in ["content", "source", "code", "text"] for p in params)

        if execution_scope == "database":
            requires_db = True
            requires_file = False
            requires_content = False
        else:
            requires_db = requires_db_param
            requires_file = requires_file_param or execution_scope == "file"
            requires_content = requires_content_param

        rule_type = "standalone"
        if "taint_registry" in params:
            rule_type = "discovery"
        elif "taint_checker" in params or "trace_taint" in params:
            rule_type = "taint-dependent"

        return RuleInfo(
            name=name,
            module=module_name,
            function=func,
            signature=sig,
            category=category,
            requires_ast=requires_ast,
            requires_db=requires_db,
            requires_file=requires_file,
            requires_content=requires_content,
            param_count=len(params),
            param_names=params,
            rule_type=rule_type,
            execution_scope=execution_scope,
        )

    def run_all_rules(self, context: RuleContext | None = None) -> list[dict[str, Any]]:
        """Execute ALL discovered rules with appropriate parameters."""
        if context is None:
            context = RuleContext(db_path=str(self.db_path), project_path=self.project_path)

        all_findings = []

        for _category, rules in self.rules.items():
            if not rules:
                continue

            for rule in rules:
                if rule.execution_scope == "database" and context.file_path:
                    continue

                try:
                    findings = self._execute_rule(rule, context)
                    if findings:
                        all_findings.extend(findings)
                except Exception as e:
                    logger.error(f"Rule {rule.name} failed: {e}")

        return all_findings

    def run_rules_for_file(self, context: RuleContext) -> list[dict[str, Any]]:
        """Run rules applicable to a specific file, WITH METADATA FILTERING."""
        findings = []
        file_to_check = context.file_path

        for _category, rules in self.rules.items():
            for rule in rules:
                if rule.execution_scope == "database":
                    continue

                if rule.requires_db and not (
                    rule.requires_file or rule.requires_ast or rule.requires_content
                ):
                    continue

                if rule.requires_ast and not context.ast_tree:
                    continue

                try:
                    rule_module = importlib.import_module(rule.module)

                    if not self._should_run_rule_on_file(rule_module, file_to_check):
                        continue

                    rule_findings = self._execute_rule(rule, context)
                    if rule_findings:
                        findings.extend(rule_findings)
                except Exception as e:
                    if self._debug:
                        logger.info(f"Rule {rule.name} failed for file: {e}")

        return findings

    def _should_run_rule_on_file(self, rule_module: Any, file_path: Path) -> bool:
        """Check if a rule should run on a specific file based on its METADATA."""
        if not hasattr(rule_module, "METADATA"):
            return True

        metadata = rule_module.METADATA
        file_path_str = str(file_path).replace("\\", "/")

        if metadata.exclude_patterns:
            for pattern in metadata.exclude_patterns:
                if pattern in file_path_str:
                    return False

        if (
            metadata.target_extensions
            and file_path.suffix.lower() not in metadata.target_extensions
        ):
            return False

        if metadata.target_file_patterns:
            if not any(pattern in file_path_str for pattern in metadata.target_file_patterns):
                return False

        return True

    def get_rules_by_type(self, rule_type: str) -> list[RuleInfo]:
        """Get all rules of a specific type."""
        rules_of_type = []
        for _category, rules in self.rules.items():
            for rule in rules:
                if rule.rule_type == rule_type:
                    rules_of_type.append(rule)
        return rules_of_type

    def run_discovery_rules(self, registry) -> list[dict[str, Any]]:
        """Run all discovery rules that populate the taint registry."""
        context = RuleContext(db_path=str(self.db_path), project_path=self.project_path)

        findings = []
        discovery_rules = self.get_rules_by_type("discovery")

        for rule in discovery_rules:
            try:
                kwargs = self._build_rule_kwargs(rule, context)
                kwargs["taint_registry"] = registry

                rule_findings = rule.function(**kwargs)
                if rule_findings:
                    findings.extend(rule_findings)
            except Exception as e:
                logger.error(f"Discovery rule {rule.name} failed: {e}")

        return findings

    def run_standalone_rules(self) -> list[dict[str, Any]]:
        """Run all standalone rules that don't need taint data."""
        context = RuleContext(db_path=str(self.db_path), project_path=self.project_path)

        findings = []
        standalone_rules = self.get_rules_by_type("standalone")

        for rule in standalone_rules:
            try:
                kwargs = self._build_rule_kwargs(rule, context)
                rule_findings = rule.function(**kwargs)
                if rule_findings:
                    findings.extend(rule_findings)
            except Exception as e:
                logger.error(f"Standalone rule {rule.name} failed: {e}")

        return findings

    def run_taint_dependent_rules(self, taint_checker) -> list[dict[str, Any]]:
        """Run all rules that depend on taint analysis results."""
        context = RuleContext(db_path=str(self.db_path), project_path=self.project_path)

        findings = []
        taint_rules = self.get_rules_by_type("taint-dependent")

        for rule in taint_rules:
            try:
                kwargs = self._build_rule_kwargs(rule, context)
                if "taint_checker" in rule.param_names:
                    kwargs["taint_checker"] = taint_checker

                rule_findings = rule.function(**kwargs)
                if rule_findings:
                    findings.extend(rule_findings)
            except Exception as e:
                logger.error(f"Taint-dependent rule {rule.name} failed: {e}")

        return findings

    def _build_rule_kwargs(self, rule: RuleInfo, context: RuleContext) -> dict[str, Any]:
        """Build keyword arguments for a rule based on its requirements."""
        kwargs = {}

        for param_name in rule.param_names:
            if param_name in ["db_path", "database"]:
                kwargs[param_name] = context.db_path or str(self.db_path)
            elif param_name in ["file_path", "filepath", "path", "filename"]:
                if context.file_path:
                    kwargs[param_name] = str(context.file_path)
            elif param_name in ["content", "source", "code", "text"]:
                if context.content:
                    kwargs[param_name] = context.content
            elif param_name in ["ast", "tree", "ast_tree", "python_ast"]:
                if context.ast_tree:
                    kwargs[param_name] = context.ast_tree
            elif param_name == "project_path":
                kwargs[param_name] = str(context.project_path or self.project_path)
            elif param_name == "language":
                kwargs[param_name] = context.language

        return kwargs

    def run_database_rules(self) -> list[dict[str, Any]]:
        """Run rules that operate on the database."""
        context = RuleContext(db_path=str(self.db_path), project_path=self.project_path)

        findings = []

        for _category, rules in self.rules.items():
            for rule in rules:
                if rule.execution_scope != "database":
                    continue

                try:
                    rule_findings = self._execute_rule(rule, context)
                    if rule_findings:
                        findings.extend(rule_findings)
                except Exception as e:
                    logger.error(f"Database rule {rule.name} failed: {e}")

        return findings

    def _execute_rule(self, rule: RuleInfo, context: RuleContext) -> list[dict[str, Any]]:
        """Execute a single rule with appropriate parameters."""

        if rule.is_standardized:
            std_context = convert_old_context(context, self.project_path)
            result = rule.function(std_context)

            if isinstance(result, RuleResult):
                findings = result.findings
                manifest = result.manifest

                # Only verify fidelity for non-empty manifests
                # Empty manifest indicates valid early-exit (e.g., no db_path)
                if manifest:
                    expected = self._compute_expected(rule, std_context)
                    passed, errors = verify_fidelity(manifest, expected)
                    if not passed:
                        self._fidelity_failures.append((rule.name, errors))
            else:
                findings = result

            if findings and hasattr(findings[0], "to_dict"):
                return [f.to_dict() for f in findings]
            return findings if findings else []

        kwargs = {}

        for param_name in rule.param_names:
            if param_name == "taint_registry":
                if self.taint_registry is None:
                    from theauditor.taint import TaintRegistry

                    self.taint_registry = TaintRegistry()
                kwargs["taint_registry"] = self.taint_registry

            elif param_name == "taint_checker":
                kwargs["taint_checker"] = self._create_taint_checker(context)

            elif param_name == "trace_taint":
                kwargs["trace_taint"] = self._get_taint_tracer()

            elif param_name in ["ast", "tree", "ast_tree", "python_ast"]:
                if context.ast_tree:
                    kwargs[param_name] = context.ast_tree
                else:
                    return []

            elif param_name in ["db_path", "database"]:
                kwargs[param_name] = context.db_path or str(self.db_path)

            elif param_name in ["file_path", "filepath", "path", "filename"]:
                if context.file_path:
                    kwargs[param_name] = str(context.file_path)
                else:
                    return []

            elif param_name in ["content", "source", "code", "text"]:
                if context.content:
                    kwargs[param_name] = context.content
                else:
                    return []

            elif param_name == "project_path":
                kwargs[param_name] = str(context.project_path or self.project_path)

            elif param_name == "language":
                kwargs[param_name] = context.language

            else:
                param = rule.signature.parameters[param_name]
                if param.default == inspect.Parameter.empty:
                    if self._debug:
                        logger.info(f"Cannot fill parameter '{param_name}' for rule {rule.name}")
                    return []

        result = rule.function(**kwargs)

        if result is None:
            return []
        elif isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        else:
            return []

    def _create_taint_checker(self, context: RuleContext):
        """Check taint using REAL taint analysis results."""
        if not hasattr(self, "_taint_results"):
            from theauditor.taint import TaintRegistry, trace_taint

            registry = TaintRegistry()
            self._taint_results = trace_taint(str(self.db_path), max_depth=25, registry=registry)

        def is_tainted(var_name: str, line: int) -> bool:
            """Check if variable is in any taint path."""
            for path in self._taint_results.get("taint_paths", []):
                source = path.get("source", {})
                if (
                    source.get("file", "") == str(context.file_path)
                    and abs(source.get("line", 0) - line) < 10
                ):
                    for step in path.get("path", []):
                        if var_name in str(step):
                            return True
            return False

        return is_tainted

    def collect_rule_patterns(self, registry):
        """Collect and register all taint patterns from rules that define them."""
        processed_modules = set()

        for _category, rules in self.rules.items():
            for rule in rules:
                module_name = rule.module

                if module_name in processed_modules:
                    continue
                processed_modules.add(module_name)

                try:
                    module = importlib.import_module(module_name)

                    if hasattr(module, "register_taint_patterns"):
                        module.register_taint_patterns(registry)
                except ImportError as e:
                    if self._debug:
                        logger.info(f"Failed to import {module_name}: {e}")
                except Exception as e:
                    if self._debug:
                        logger.info(f"Error registering patterns from {module_name}: {e}")

        return registry

    def _get_taint_tracer(self):
        """Get cached taint analysis results for rules to query."""
        if self._taint_trace_func is None:
            from theauditor.taint import TaintRegistry, trace_taint

            if not hasattr(self, "_taint_results"):
                registry = TaintRegistry()
                self._taint_results = trace_taint(str(self.db_path), max_depth=25, registry=registry)

            def get_taint_for_location(
                source_var: str,
                source_file: str,
                source_line: int,
                source_function: str = "unknown",
            ):
                """Return cached taint paths relevant to location."""
                relevant_paths = []
                for path in self._taint_results.get("taint_paths", []):
                    source = path.get("source", {})

                    if (
                        source.get("file", "").endswith(source_file)
                        and abs(source.get("line", 0) - source_line) < 10
                    ):
                        for step in path.get("path", []):
                            if source_var in str(step.get("var", "")):
                                relevant_paths.append(path)
                                break
                return relevant_paths

            self._taint_trace_func = get_taint_for_location

        return self._taint_trace_func

    def _compute_expected(self, rule: RuleInfo, context) -> dict:
        """Compute expected fidelity values for a rule."""
        expected = {"table_row_count": 0, "expected_tables": []}

        try:
            rule_module = importlib.import_module(rule.module)
            metadata = getattr(rule_module, "METADATA", None)

            if metadata and hasattr(metadata, "primary_table"):
                table_name = metadata.primary_table
                conn = sqlite3.connect(context.db_path)
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                expected["table_row_count"] = cursor.fetchone()[0]
                expected["expected_tables"] = [table_name]
                conn.close()
        except Exception:
            pass

        return expected

    def get_aggregated_manifests(self) -> dict:
        """Get aggregated fidelity results."""
        return {
            "fidelity_failures": self._fidelity_failures,
            "failure_count": len(self._fidelity_failures),
        }

    def get_rule_stats(self) -> dict[str, Any]:
        """Get statistics about discovered rules.

        Returns:
            Dict with total_rules, categories count, and breakdown by category.
        """
        total_rules = sum(len(rules) for rules in self.rules.values())
        return {
            "total_rules": total_rules,
            "categories": len(self.rules),
            "by_category": {cat: len(rules) for cat, rules in self.rules.items()},
        }


def run_all_rules(project_path: str, db_path: str = None) -> list[dict[str, Any]]:
    """Run all rules for a project."""
    orchestrator = RulesOrchestrator(Path(project_path))

    context = RuleContext(
        db_path=db_path or str(orchestrator.db_path), project_path=Path(project_path)
    )

    return orchestrator.run_all_rules(context)
