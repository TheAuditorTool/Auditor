"""Unified orchestrator for dynamic rule discovery and execution.

This module provides a central orchestrator that:
1. Dynamically discovers ALL rules in the /rules directory
2. Analyzes their signatures to determine requirements
3. Executes them with appropriate parameters
4. Provides a unified interface for all detection systems
"""

import importlib
import inspect
import os
import sqlite3
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from theauditor.rules.base import convert_old_context, validate_rule_signature

    STANDARD_CONTRACTS_AVAILABLE = True
except ImportError:
    STANDARD_CONTRACTS_AVAILABLE = False


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
        """Initialize the orchestrator.

        Args:
            project_path: Root path of the project being analyzed
            db_path: Optional path to the database (defaults to .pf/repo_index.db)
        """
        self.project_path = Path(project_path)
        self.db_path = Path(db_path) if db_path else self.project_path / ".pf" / "repo_index.db"
        self._debug = os.environ.get("THEAUDITOR_DEBUG", "").lower() == "true"
        self.rules = self._discover_all_rules()

        self.taint_registry = None
        self._taint_trace_func = None
        self._taint_conn = None

        self.migration_stats = {
            "standardized_rules": 0,
            "legacy_rules": 0,
            "categories_migrated": set(),
            "categories_pending": set(),
        }

        for category, rules in self.rules.items():
            for rule in rules:
                if hasattr(rule, "is_standardized") and rule.is_standardized:
                    self.migration_stats["standardized_rules"] += 1
                    self.migration_stats["categories_migrated"].add(category)
                else:
                    self.migration_stats["legacy_rules"] += 1
                    self.migration_stats["categories_pending"].add(category)

        if self._debug:
            total_rules = sum(len(r) for r in self.rules.values())
            print(
                f"[ORCHESTRATOR] Discovered {total_rules} rules across {len(self.rules)} categories"
            )
            if STANDARD_CONTRACTS_AVAILABLE:
                print(
                    f"[ORCHESTRATOR] Migration Status: {self.migration_stats['standardized_rules']} standardized, {self.migration_stats['legacy_rules']} legacy"
                )

    def _discover_all_rules(self) -> dict[str, list[RuleInfo]]:
        """Dynamically discover ALL rules in /rules directory.

        Returns:
            Dictionary mapping category name to list of RuleInfo objects
        """
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
                        if name.startswith("find_"):
                            if obj.__module__ == module_name:
                                rule_info = self._analyze_rule(
                                    name, obj, module, module_name, category
                                )
                                rules_by_category[category].append(rule_info)

                                if self._debug:
                                    print(
                                        f"[ORCHESTRATOR] Found rule: {category}/{name} with {rule_info.param_count} params"
                                    )

                except ImportError as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Failed to import {module_name}: {e}")
                except Exception as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Error processing {module_name}: {e}")

        for py_file in rules_dir.glob("*.py"):
            if py_file.name.startswith("__") or py_file.is_dir():
                continue

            if py_file.name.endswith("_analyzer.py") or py_file.name.endswith("_detector.py"):
                continue

            module_name = f"theauditor.rules.{py_file.stem}"
            category = "general"

            if category not in rules_by_category:
                rules_by_category[category] = []

            try:
                module = importlib.import_module(module_name)

                for name, obj in inspect.getmembers(module, inspect.isfunction):
                    if name.startswith("find_"):
                        if obj.__module__ == module_name:
                            rule_info = self._analyze_rule(name, obj, module, module_name, category)
                            rules_by_category[category].append(rule_info)

            except ImportError:
                pass
            except Exception as e:
                if self._debug:
                    print(f"[ORCHESTRATOR] Warning: Error processing {module_name}: {e}")

        return rules_by_category

    def _analyze_rule(
        self, name: str, func: Callable, module_obj: Any, module_name: str, category: str
    ) -> RuleInfo:
        """Analyze a rule function to determine its requirements.

        Args:
            name: Function name
            func: The function object
            module_obj: Imported module containing the rule
            module_name: Module name string
            category: Category name

        Returns:
            RuleInfo object with metadata about the rule
        """
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        metadata = getattr(module_obj, "METADATA", None)

        is_standardized = False
        if STANDARD_CONTRACTS_AVAILABLE:
            is_standardized = validate_rule_signature(func)

        execution_scope_default = "database" if is_standardized else "file"
        execution_scope = execution_scope_default
        if metadata is not None:
            execution_scope = (
                getattr(metadata, "execution_scope", execution_scope_default)
                or execution_scope_default
            )

        if execution_scope not in {"database", "file"}:
            execution_scope = execution_scope_default

        if is_standardized:
            if self._debug:
                print(f"[ORCHESTRATOR] Found STANDARDIZED rule: {category}/{name}")

            requires_db = execution_scope == "database"
            requires_file = execution_scope == "file"
            requires_content = execution_scope == "file"

            return RuleInfo(
                name=name,
                module=module_name,
                function=func,
                signature=sig,
                category=category,
                is_standardized=True,
                requires_ast=False,
                requires_db=requires_db,
                requires_file=requires_file,
                requires_content=requires_content,
                param_count=1,
                param_names=["context"],
                rule_type="standard",
                execution_scope=execution_scope,
            )

        if self._debug and STANDARD_CONTRACTS_AVAILABLE:
            print(f"[ORCHESTRATOR] Found LEGACY rule: {category}/{name} with params: {params}")

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
        """Execute ALL discovered rules with appropriate parameters.

        Args:
            context: Optional context with file, AST, database info

        Returns:
            List of findings from all rules
        """
        if context is None:
            context = RuleContext(db_path=str(self.db_path), project_path=self.project_path)

        all_findings = []
        total_executed = 0

        for category, rules in self.rules.items():
            if not rules:
                continue

            if self._debug:
                print(f"[ORCHESTRATOR] Running {len(rules)} rules in category: {category}")

            for rule in rules:
                if rule.execution_scope == "database" and context.file_path:
                    continue

                try:
                    import sys

                    print(
                        f"[ORCHESTRATOR] >> Starting rule: {category}/{rule.name}...",
                        file=sys.stderr,
                        end="",
                        flush=True,
                    )

                    findings = self._execute_rule(rule, context)

                    print(f" Done. ({len(findings or [])} findings)", file=sys.stderr, flush=True)

                    if findings:
                        all_findings.extend(findings)
                        total_executed += 1

                        if self._debug:
                            print(f"[ORCHESTRATOR]   {rule.name}: {len(findings)} findings")

                except Exception as e:
                    print(f" FAILED: {e}", file=sys.stderr, flush=True)
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Rule {rule.name} failed: {e}")

        if self._debug:
            print(
                f"[ORCHESTRATOR] Executed {total_executed} rules, found {len(all_findings)} issues"
            )

        return all_findings

    def _should_run_rule_on_file(self, rule_module: Any, file_path: Path) -> bool:
        """Check if a rule should run on a specific file based on its METADATA.

        Args:
            rule_module: The imported rule module
            file_path: Path to the file being analyzed

        Returns:
            True if rule should run on this file, False otherwise
        """
        if not hasattr(rule_module, "METADATA"):
            return True

        metadata = rule_module.METADATA
        file_path_str = str(file_path).replace("\\", "/")

        if metadata.exclude_patterns:
            for pattern in metadata.exclude_patterns:
                if pattern in file_path_str:
                    return False

        if metadata.target_extensions:
            if file_path.suffix.lower() not in metadata.target_extensions:
                return False

        if metadata.target_file_patterns:
            if not any(pattern in file_path_str for pattern in metadata.target_file_patterns):
                return False

        return True

    def run_rules_for_file(self, context: RuleContext) -> list[dict[str, Any]]:
        """Run rules applicable to a specific file, WITH METADATA FILTERING.

        Args:
            context: Context with file information

        Returns:
            List of findings for this file
        """
        findings = []

        file_to_check = context.file_path

        for category, rules in self.rules.items():
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
                        if self._debug:
                            print(
                                f"[ORCHESTRATOR] Skipping rule '{rule.name}' on file '{file_to_check.name}' due to metadata mismatch."
                            )
                        continue

                    rule_findings = self._execute_rule(rule, context)
                    if rule_findings:
                        findings.extend(rule_findings)

                except Exception as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Rule {rule.name} failed for file: {e}")

        return findings

    def get_rules_by_type(self, rule_type: str) -> list[RuleInfo]:
        """Get all rules of a specific type.

        Args:
            rule_type: Type of rules to retrieve (standalone, discovery, taint-dependent)

        Returns:
            List of RuleInfo objects matching the type
        """
        rules_of_type = []
        for category, rules in self.rules.items():
            for rule in rules:
                if rule.rule_type == rule_type:
                    rules_of_type.append(rule)
        return rules_of_type

    def run_discovery_rules(self, registry) -> list[dict[str, Any]]:
        """Run all discovery rules that populate the taint registry.

        Args:
            registry: TaintRegistry to populate with discovered patterns

        Returns:
            List of findings from discovery rules
        """
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

                if self._debug:
                    print(
                        f"[ORCHESTRATOR] Discovery rule {rule.name}: {len(rule_findings) if rule_findings else 0} findings"
                    )

            except Exception as e:
                if self._debug:
                    print(f"[ORCHESTRATOR] Discovery rule {rule.name} failed: {e}")

        return findings

    def run_standalone_rules(self) -> list[dict[str, Any]]:
        """Run all standalone rules that don't need taint data.

        Returns:
            List of findings from standalone rules
        """
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
                if self._debug:
                    print(f"[ORCHESTRATOR] Standalone rule {rule.name} failed: {e}")

        return findings

    def run_taint_dependent_rules(self, taint_checker) -> list[dict[str, Any]]:
        """Run all rules that depend on taint analysis results.

        Args:
            taint_checker: Function to check if a variable is tainted

        Returns:
            List of findings from taint-dependent rules
        """
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
                if self._debug:
                    print(f"[ORCHESTRATOR] Taint-dependent rule {rule.name} failed: {e}")

        return findings

    def _build_rule_kwargs(self, rule: RuleInfo, context: RuleContext) -> dict[str, Any]:
        """Build keyword arguments for a rule based on its requirements.

        Args:
            rule: RuleInfo object
            context: RuleContext with available data

        Returns:
            Dictionary of keyword arguments for the rule
        """
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
        """Run rules that operate on the database.

        Returns:
            List of findings from database rules
        """
        context = RuleContext(db_path=str(self.db_path), project_path=self.project_path)

        findings = []

        for category, rules in self.rules.items():
            for rule in rules:
                if rule.execution_scope != "database":
                    continue

                try:
                    rule_findings = self._execute_rule(rule, context)
                    if rule_findings:
                        findings.extend(rule_findings)

                except Exception as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Database rule {rule.name} failed: {e}")

        return findings

    def _execute_rule(self, rule: RuleInfo, context: RuleContext) -> list[dict[str, Any]]:
        """Execute a single rule with appropriate parameters.

        Now handles both standardized and legacy rules (Phase 1 dual-mode).

        Args:
            rule: RuleInfo object describing the rule
            context: RuleContext with available data

        Returns:
            List of findings from the rule
        """

        if rule.is_standardized and STANDARD_CONTRACTS_AVAILABLE:
            try:
                std_context = convert_old_context(context, self.project_path)

                findings = rule.function(std_context)

                if findings and hasattr(findings[0], "to_dict"):
                    return [f.to_dict() for f in findings]
                return findings if findings else []

            except Exception as e:
                if self._debug:
                    print(f"[ORCHESTRATOR] Standardized rule {rule.name} failed: {e}")
                return []

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
                if param.default != inspect.Parameter.empty:
                    continue
                else:
                    if self._debug:
                        print(
                            f"[ORCHESTRATOR] Warning: Don't know how to fill parameter '{param_name}' for rule {rule.name}"
                        )
                    return []

        try:
            result = rule.function(**kwargs)

            if result is None:
                return []
            elif isinstance(result, list):
                return result
            elif isinstance(result, dict):
                return [result]
            else:
                if self._debug:
                    print(
                        f"[ORCHESTRATOR] Warning: Rule {rule.name} returned unexpected type: {type(result)}"
                    )
                return []

        except Exception as e:
            if self._debug:
                print(f"[ORCHESTRATOR] Error executing rule {rule.name}: {e}")
            return []

    def get_rule_stats(self) -> dict[str, Any]:
        """Get statistics about discovered rules.

        Returns:
            Dictionary with rule statistics
        """
        stats = {
            "total_rules": sum(len(rules) for rules in self.rules.values()),
            "categories": list(self.rules.keys()),
            "by_category": {cat: len(rules) for cat, rules in self.rules.items()},
            "by_requirements": {
                "ast_rules": sum(
                    1 for rules in self.rules.values() for r in rules if r.requires_ast
                ),
                "db_rules": sum(1 for rules in self.rules.values() for r in rules if r.requires_db),
                "file_rules": sum(
                    1 for rules in self.rules.values() for r in rules if r.requires_file
                ),
                "content_rules": sum(
                    1 for rules in self.rules.values() for r in rules if r.requires_content
                ),
            },
        }
        return stats

    def _create_taint_checker(self, context: RuleContext):
        """Check taint using REAL taint analysis results.

        This provides rules with a way to check if variables are tainted
        using the main taint analyzer's cached results.

        Args:
            context: The rule execution context

        Returns:
            A function that checks if a variable is tainted
        """

        if not hasattr(self, "_taint_results"):
            from theauditor.taint import TaintRegistry, trace_taint

            registry = TaintRegistry()
            self._taint_results = trace_taint(str(self.db_path), max_depth=5, registry=registry)
            if self._debug:
                total = len(self._taint_results.get("taint_paths", []))
                print(f"[ORCHESTRATOR] Cached {total} taint paths for rules", file=sys.stderr)

        def is_tainted(var_name: str, line: int) -> bool:
            """Check if variable is in any taint path.

            Args:
                var_name: Name of the variable to check
                line: Line number where the check is happening

            Returns:
                True if the variable is tainted, False otherwise
            """
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
        """Collect and register all taint patterns from rules that define them.

        ARCHITECTURAL FIX: Framework-Aware Pattern Collection
        This method now FILTERS rules by detected frameworks before registering patterns.
        Only runs Python rules if Python frameworks detected (Flask, Django, etc.),
        only runs JavaScript rules if JavaScript frameworks detected (Express, React, etc.).

        This prevents registry pollution (Python patterns matching JavaScript code) and
        ensures taint analysis only uses relevant patterns for the project's languages.

        Args:
            registry: TaintRegistry instance to populate with patterns

        Returns:
            The populated registry
        """

        detected_languages = set()
        if self.db_path.exists():
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                cursor.execute("SELECT DISTINCT language FROM frameworks")

                for (language,) in cursor.fetchall():
                    if language:
                        detected_languages.add(language.lower())

                conn.close()

                if self._debug:
                    print(f"[ORCHESTRATOR] Detected languages: {detected_languages}")
            except Exception as e:
                if self._debug:
                    print(f"[ORCHESTRATOR] Warning: Failed to query frameworks: {e}")

        processed_modules = set()
        skipped_categories = set()

        for category, rules in self.rules.items():
            if (
                category in {"python", "javascript", "rust", "typescript"}
                and category not in detected_languages
            ):
                skipped_categories.add(category)
                if self._debug:
                    print(
                        f"[ORCHESTRATOR] Skipping {category} rules (no {category} frameworks detected)"
                    )
                continue

            for rule in rules:
                module_name = rule.module

                if module_name in processed_modules:
                    continue
                processed_modules.add(module_name)

                try:
                    module = importlib.import_module(module_name)

                    if hasattr(module, "register_taint_patterns"):
                        register_func = module.register_taint_patterns

                        register_func(registry)

                        if self._debug:
                            print(f"[ORCHESTRATOR] Registered patterns from {module_name}")

                except ImportError as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Failed to import {module_name}: {e}")
                except Exception as e:
                    if self._debug:
                        print(
                            f"[ORCHESTRATOR] Warning: Error registering patterns from {module_name}: {e}"
                        )

        if self._debug:
            stats = registry.get_stats()
            processed_count = len(processed_modules)
            print(f"[ORCHESTRATOR] Dynamically processed {processed_count} modules")
            print(
                f"[ORCHESTRATOR] Skipped {len(skipped_categories)} categories: {skipped_categories}"
            )
            print(f"[ORCHESTRATOR] Pattern statistics: {stats}")

        return registry

    def _get_taint_tracer(self):
        """Get cached taint analysis results for rules to query.

        This provides rules with access to the main taint analyzer's
        results WITH JavaScript pattern support.

        Returns:
            A function that returns relevant taint paths
        """
        if self._taint_trace_func is None:
            from theauditor.taint import TaintRegistry, trace_taint

            if not hasattr(self, "_taint_results"):
                registry = TaintRegistry()
                self._taint_results = trace_taint(str(self.db_path), max_depth=5, registry=registry)
                if self._debug:
                    total = len(self._taint_results.get("taint_paths", []))
                    print(f"[ORCHESTRATOR] Cached {total} taint paths for rules", file=sys.stderr)

            def get_taint_for_location(
                source_var: str,
                source_file: str,
                source_line: int,
                source_function: str = "unknown",
            ):
                """Return cached taint paths relevant to location.

                Args:
                    source_var: The variable to trace
                    source_file: File containing the variable
                    source_line: Line where the variable is defined
                    source_function: Function containing the variable (optional)

                Returns:
                    List of relevant taint paths from cached results
                """
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


def run_all_rules(project_path: str, db_path: str = None) -> list[dict[str, Any]]:
    """Run all rules for a project.

    Args:
        project_path: Root path of the project
        db_path: Optional database path (defaults to .pf/repo_index.db)

    Returns:
        List of all findings
    """
    orchestrator = RulesOrchestrator(Path(project_path))

    context = RuleContext(
        db_path=db_path or str(orchestrator.db_path), project_path=Path(project_path)
    )

    return orchestrator.run_all_rules(context)
