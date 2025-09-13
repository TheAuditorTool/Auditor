"""Unified orchestrator for dynamic rule discovery and execution.

This module provides a central orchestrator that:
1. Dynamically discovers ALL rules in the /rules directory
2. Analyzes their signatures to determine requirements
3. Executes them with appropriate parameters
4. Provides a unified interface for all detection systems
"""

import importlib
import inspect
import json
import os
import pkgutil
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional, Set
from dataclasses import dataclass, field

# Import standardized contracts (Phase 1 addition)
try:
    from theauditor.rules.base import (
        StandardRuleContext, 
        StandardFinding, 
        validate_rule_signature,
        convert_old_context
    )
    STANDARD_CONTRACTS_AVAILABLE = True
except ImportError:
    # Fallback if base.py not available yet
    STANDARD_CONTRACTS_AVAILABLE = False


@dataclass
class RuleInfo:
    """Metadata about a discovered rule."""
    name: str
    module: str
    function: Callable
    signature: inspect.Signature
    category: str
    is_standardized: bool = False  # NEW: Track if rule uses new interface
    requires_ast: bool = False
    requires_db: bool = False
    requires_file: bool = False
    requires_content: bool = False
    param_count: int = 0
    param_names: List[str] = field(default_factory=list)
    rule_type: str = "standalone"  # standalone, discovery, taint-dependent


@dataclass
class RuleContext:
    """Context information for rule execution."""
    file_path: Optional[Path] = None
    content: Optional[str] = None
    ast_tree: Optional[Any] = None
    language: Optional[str] = None
    db_path: Optional[str] = None
    project_path: Optional[Path] = None


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
        
        # NEW: Initialize taint infrastructure for rules that need it
        # Lazy imports to avoid circular dependencies
        self.taint_registry = None
        self._taint_trace_func = None
        self._taint_conn = None  # Lazy-load database connection
        
        # PHASE 1: Track migration progress
        self.migration_stats = {
            'standardized_rules': 0,
            'legacy_rules': 0,
            'categories_migrated': set(),
            'categories_pending': set()
        }
        
        # Count rules by type
        for category, rules in self.rules.items():
            for rule in rules:
                if hasattr(rule, 'is_standardized') and rule.is_standardized:
                    self.migration_stats['standardized_rules'] += 1
                    self.migration_stats['categories_migrated'].add(category)
                else:
                    self.migration_stats['legacy_rules'] += 1
                    self.migration_stats['categories_pending'].add(category)
        
        if self._debug:
            total_rules = sum(len(r) for r in self.rules.values())
            print(f"[ORCHESTRATOR] Discovered {total_rules} rules across {len(self.rules)} categories")
            if STANDARD_CONTRACTS_AVAILABLE:
                print(f"[ORCHESTRATOR] Migration Status: {self.migration_stats['standardized_rules']} standardized, {self.migration_stats['legacy_rules']} legacy")
    
    def _discover_all_rules(self) -> Dict[str, List[RuleInfo]]:
        """Dynamically discover ALL rules in /rules directory.
        
        Returns:
            Dictionary mapping category name to list of RuleInfo objects
        """
        rules_by_category = {}
        
        # Get the rules package directory
        import theauditor.rules as rules_package
        rules_dir = Path(rules_package.__file__).parent
        
        # Walk all subdirectories
        for subdir in rules_dir.iterdir():
            if not subdir.is_dir() or subdir.name.startswith('__'):
                continue
                
            category = subdir.name
            rules_by_category[category] = []
            
            # Process all Python files in the subdirectory
            for py_file in subdir.glob("*.py"):
                if py_file.name.startswith('__'):
                    continue
                
                module_name = f"theauditor.rules.{category}.{py_file.stem}"
                
                try:
                    # Import the module
                    module = importlib.import_module(module_name)
                    
                    # Find all find_* functions
                    for name, obj in inspect.getmembers(module, inspect.isfunction):
                        if name.startswith('find_'):
                            # Check if function is defined in this module (not imported)
                            if obj.__module__ == module_name:
                                rule_info = self._analyze_rule(name, obj, module_name, category)
                                rules_by_category[category].append(rule_info)
                                
                                if self._debug:
                                    print(f"[ORCHESTRATOR] Found rule: {category}/{name} with {rule_info.param_count} params")
                                    
                except ImportError as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Failed to import {module_name}: {e}")
                except Exception as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Error processing {module_name}: {e}")
        
        # Also check for top-level rule files (not in subdirectories)
        for py_file in rules_dir.glob("*.py"):
            if py_file.name.startswith('__') or py_file.is_dir():
                continue
            
            # SKIP OLD BACKUP FILES during refactor
            if py_file.name.endswith('_analyzer.py') or py_file.name.endswith('_detector.py'):
                continue  # These are old backups, not the new refactored rules
            
            module_name = f"theauditor.rules.{py_file.stem}"
            category = "general"  # Top-level rules go in general category
            
            if category not in rules_by_category:
                rules_by_category[category] = []
            
            try:
                module = importlib.import_module(module_name)
                
                for name, obj in inspect.getmembers(module, inspect.isfunction):
                    if name.startswith('find_'):
                        if obj.__module__ == module_name:
                            rule_info = self._analyze_rule(name, obj, module_name, category)
                            rules_by_category[category].append(rule_info)
                            
            except ImportError:
                pass  # Silent skip for non-importable files
            except Exception as e:
                if self._debug:
                    print(f"[ORCHESTRATOR] Warning: Error processing {module_name}: {e}")
        
        return rules_by_category
    
    def _analyze_rule(self, name: str, func: Callable, module: str, category: str) -> RuleInfo:
        """Analyze a rule function to determine its requirements.
        
        Now detects standardized vs legacy rules for dual-mode support.
        
        Args:
            name: Function name
            func: The function object
            module: Module name
            category: Category name
            
        Returns:
            RuleInfo object with metadata about the rule
        """
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        
        # Check if this is a standardized rule (Phase 1 addition)
        is_standardized = False
        if STANDARD_CONTRACTS_AVAILABLE:
            is_standardized = validate_rule_signature(func)
        
        if is_standardized:
            # New standardized rule - simple case
            if self._debug:
                print(f"[ORCHESTRATOR] Found STANDARDIZED rule: {category}/{name}")
            
            return RuleInfo(
                name=name,
                module=module,
                function=func,
                signature=sig,
                category=category,
                is_standardized=True,
                # Standardized rules handle their own requirements
                requires_ast=False,
                requires_db=False,
                requires_file=True,
                requires_content=True,
                param_count=1,
                param_names=['context'],
                rule_type="standard"
            )
        
        # Legacy rule - maintain compatibility
        if self._debug and STANDARD_CONTRACTS_AVAILABLE:
            print(f"[ORCHESTRATOR] Found LEGACY rule: {category}/{name} with params: {params}")
        
        # Determine what the rule needs based on parameter names
        requires_ast = any(p in ['ast', 'tree', 'ast_tree', 'python_ast'] for p in params)
        requires_db = any(p in ['db_path', 'database', 'conn'] for p in params)
        requires_file = any(p in ['file_path', 'filepath', 'path', 'filename'] for p in params)
        requires_content = any(p in ['content', 'source', 'code', 'text'] for p in params)
        
        # CRITICAL: Auto-detect rule type based on parameters
        rule_type = "standalone"  # Default
        
        # Discovery rules: register new sinks/sources to the registry
        if 'taint_registry' in params:
            rule_type = "discovery"
        # Taint-dependent rules: use taint analysis results
        elif 'taint_checker' in params or 'trace_taint' in params:
            rule_type = "taint-dependent"
        # Everything else is standalone (doesn't need taint infrastructure)
        else:
            rule_type = "standalone"
        
        return RuleInfo(
            name=name,
            module=module,
            function=func,
            signature=sig,
            category=category,
            requires_ast=requires_ast,
            requires_db=requires_db,
            requires_file=requires_file,
            requires_content=requires_content,
            param_count=len(params),
            param_names=params,
            rule_type=rule_type
        )
    
    def run_all_rules(self, context: Optional[RuleContext] = None) -> List[Dict[str, Any]]:
        """Execute ALL discovered rules with appropriate parameters.
        
        Args:
            context: Optional context with file, AST, database info
            
        Returns:
            List of findings from all rules
        """
        if context is None:
            context = RuleContext(
                db_path=str(self.db_path),
                project_path=self.project_path
            )
        
        all_findings = []
        total_executed = 0
        
        for category, rules in self.rules.items():
            if not rules:
                continue
                
            if self._debug:
                print(f"[ORCHESTRATOR] Running {len(rules)} rules in category: {category}")
            
            for rule in rules:
                try:
                    findings = self._execute_rule(rule, context)
                    if findings:
                        all_findings.extend(findings)
                        total_executed += 1
                        
                        if self._debug:
                            print(f"[ORCHESTRATOR]   {rule.name}: {len(findings)} findings")
                            
                except Exception as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Rule {rule.name} failed: {e}")
        
        if self._debug:
            print(f"[ORCHESTRATOR] Executed {total_executed} rules, found {len(all_findings)} issues")
        
        return all_findings
    
    def run_rules_for_file(self, context: RuleContext) -> List[Dict[str, Any]]:
        """Run rules applicable to a specific file.
        
        Args:
            context: Context with file information
            
        Returns:
            List of findings for this file
        """
        findings = []
        
        # Filter rules that need file/AST/content
        for category, rules in self.rules.items():
            for rule in rules:
                # Skip database-only rules when processing individual files
                if rule.requires_db and not (rule.requires_file or rule.requires_ast or rule.requires_content):
                    continue
                
                # Skip rules that need AST if we don't have it
                if rule.requires_ast and not context.ast_tree:
                    continue
                
                try:
                    rule_findings = self._execute_rule(rule, context)
                    if rule_findings:
                        findings.extend(rule_findings)
                        
                except Exception as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Rule {rule.name} failed for file: {e}")
        
        return findings
    
    def get_rules_by_type(self, rule_type: str) -> List[RuleInfo]:
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
    
    def run_discovery_rules(self, registry) -> List[Dict[str, Any]]:
        """Run all discovery rules that populate the taint registry.
        
        Args:
            registry: TaintRegistry to populate with discovered patterns
            
        Returns:
            List of findings from discovery rules
        """
        context = RuleContext(
            db_path=str(self.db_path),
            project_path=self.project_path
        )
        
        findings = []
        discovery_rules = self.get_rules_by_type("discovery")
        
        for rule in discovery_rules:
            try:
                # Pass registry to the rule
                kwargs = self._build_rule_kwargs(rule, context)
                kwargs['taint_registry'] = registry
                
                rule_findings = rule.function(**kwargs)
                if rule_findings:
                    findings.extend(rule_findings)
                    
                if self._debug:
                    print(f"[ORCHESTRATOR] Discovery rule {rule.name}: {len(rule_findings) if rule_findings else 0} findings")
                    
            except Exception as e:
                if self._debug:
                    print(f"[ORCHESTRATOR] Discovery rule {rule.name} failed: {e}")
        
        return findings
    
    def run_standalone_rules(self) -> List[Dict[str, Any]]:
        """Run all standalone rules that don't need taint data.
        
        Returns:
            List of findings from standalone rules
        """
        context = RuleContext(
            db_path=str(self.db_path),
            project_path=self.project_path
        )
        
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
    
    def run_taint_dependent_rules(self, taint_checker) -> List[Dict[str, Any]]:
        """Run all rules that depend on taint analysis results.
        
        Args:
            taint_checker: Function to check if a variable is tainted
            
        Returns:
            List of findings from taint-dependent rules
        """
        context = RuleContext(
            db_path=str(self.db_path),
            project_path=self.project_path
        )
        
        findings = []
        taint_rules = self.get_rules_by_type("taint-dependent")
        
        for rule in taint_rules:
            try:
                kwargs = self._build_rule_kwargs(rule, context)
                if 'taint_checker' in rule.param_names:
                    kwargs['taint_checker'] = taint_checker
                
                rule_findings = rule.function(**kwargs)
                if rule_findings:
                    findings.extend(rule_findings)
                    
            except Exception as e:
                if self._debug:
                    print(f"[ORCHESTRATOR] Taint-dependent rule {rule.name} failed: {e}")
        
        return findings
    
    def _build_rule_kwargs(self, rule: RuleInfo, context: RuleContext) -> Dict[str, Any]:
        """Build keyword arguments for a rule based on its requirements.
        
        Args:
            rule: RuleInfo object
            context: RuleContext with available data
            
        Returns:
            Dictionary of keyword arguments for the rule
        """
        kwargs = {}
        
        for param_name in rule.param_names:
            if param_name in ['db_path', 'database']:
                kwargs[param_name] = context.db_path or str(self.db_path)
            elif param_name in ['file_path', 'filepath', 'path', 'filename']:
                if context.file_path:
                    kwargs[param_name] = str(context.file_path)
            elif param_name in ['content', 'source', 'code', 'text']:
                if context.content:
                    kwargs[param_name] = context.content
            elif param_name in ['ast', 'tree', 'ast_tree', 'python_ast']:
                if context.ast_tree:
                    kwargs[param_name] = context.ast_tree
            elif param_name == 'project_path':
                kwargs[param_name] = str(context.project_path or self.project_path)
            elif param_name == 'language':
                kwargs[param_name] = context.language
        
        return kwargs
    
    def run_database_rules(self) -> List[Dict[str, Any]]:
        """Run rules that operate on the database.
        
        Returns:
            List of findings from database rules
        """
        context = RuleContext(
            db_path=str(self.db_path),
            project_path=self.project_path
        )
        
        findings = []
        
        # Filter rules that need database
        for category, rules in self.rules.items():
            for rule in rules:
                if rule.requires_db:
                    try:
                        rule_findings = self._execute_rule(rule, context)
                        if rule_findings:
                            findings.extend(rule_findings)
                            
                    except Exception as e:
                        if self._debug:
                            print(f"[ORCHESTRATOR] Database rule {rule.name} failed: {e}")
        
        return findings
    
    def _execute_rule(self, rule: RuleInfo, context: RuleContext) -> List[Dict[str, Any]]:
        """Execute a single rule with appropriate parameters.
        
        Now handles both standardized and legacy rules (Phase 1 dual-mode).
        
        Args:
            rule: RuleInfo object describing the rule
            context: RuleContext with available data
            
        Returns:
            List of findings from the rule
        """
        # PHASE 1: Check if this is a standardized rule
        if rule.is_standardized and STANDARD_CONTRACTS_AVAILABLE:
            # STANDARDIZED PATH - Clean and simple
            try:
                # Convert old context to standardized format
                std_context = convert_old_context(context, self.project_path)
                
                # Execute standardized rule
                findings = rule.function(std_context)
                
                # Convert StandardFinding objects to dicts if needed
                if findings and hasattr(findings[0], 'to_dict'):
                    return [f.to_dict() for f in findings]
                return findings if findings else []
                
            except Exception as e:
                if self._debug:
                    print(f"[ORCHESTRATOR] Standardized rule {rule.name} failed: {e}")
                return []
        
        # LEGACY PATH - Keep existing complex logic
        # Build arguments based on what the rule needs
        kwargs = {}
        
        for param_name in rule.param_names:
            # NEW: Provide taint infrastructure to rules that need it
            if param_name == 'taint_registry':
                # Lazy-load taint registry only when needed
                if self.taint_registry is None:
                    from theauditor.taint.registry import TaintRegistry
                    self.taint_registry = TaintRegistry()
                kwargs['taint_registry'] = self.taint_registry
                
            elif param_name == 'taint_checker':
                # Provide a function that checks if variable is tainted
                kwargs['taint_checker'] = self._create_taint_checker(context)
                
            elif param_name == 'trace_taint':
                # Provide inter-procedural tracking function
                kwargs['trace_taint'] = self._get_taint_tracer()
                
            # Map parameter names to context values
            elif param_name in ['ast', 'tree', 'ast_tree', 'python_ast']:
                if context.ast_tree:
                    kwargs[param_name] = context.ast_tree
                else:
                    return []  # Skip if AST required but not available
                    
            elif param_name in ['db_path', 'database']:
                kwargs[param_name] = context.db_path or str(self.db_path)
                
            elif param_name in ['file_path', 'filepath', 'path', 'filename']:
                if context.file_path:
                    kwargs[param_name] = str(context.file_path)
                else:
                    return []  # Skip if file required but not available
                    
            elif param_name in ['content', 'source', 'code', 'text']:
                if context.content:
                    kwargs[param_name] = context.content
                else:
                    return []  # Skip if content required but not available
                    
            elif param_name == 'project_path':
                kwargs[param_name] = str(context.project_path or self.project_path)
                
            elif param_name == 'language':
                kwargs[param_name] = context.language
            
            # Some rules might have other parameters - try to handle gracefully
            else:
                # Check if parameter has a default value
                param = rule.signature.parameters[param_name]
                if param.default != inspect.Parameter.empty:
                    # Has default, can skip
                    continue
                else:
                    # Required parameter we don't know how to fill
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Don't know how to fill parameter '{param_name}' for rule {rule.name}")
                    return []
        
        # Execute the rule
        try:
            result = rule.function(**kwargs)
            
            # Normalize result to list of dicts
            if result is None:
                return []
            elif isinstance(result, list):
                return result
            elif isinstance(result, dict):
                return [result]
            else:
                if self._debug:
                    print(f"[ORCHESTRATOR] Warning: Rule {rule.name} returned unexpected type: {type(result)}")
                return []
                
        except Exception as e:
            if self._debug:
                print(f"[ORCHESTRATOR] Error executing rule {rule.name}: {e}")
            return []
    
    def get_rule_stats(self) -> Dict[str, Any]:
        """Get statistics about discovered rules.
        
        Returns:
            Dictionary with rule statistics
        """
        stats = {
            'total_rules': sum(len(rules) for rules in self.rules.values()),
            'categories': list(self.rules.keys()),
            'by_category': {cat: len(rules) for cat, rules in self.rules.items()},
            'by_requirements': {
                'ast_rules': sum(1 for rules in self.rules.values() for r in rules if r.requires_ast),
                'db_rules': sum(1 for rules in self.rules.values() for r in rules if r.requires_db),
                'file_rules': sum(1 for rules in self.rules.values() for r in rules if r.requires_file),
                'content_rules': sum(1 for rules in self.rules.values() for r in rules if r.requires_content),
            }
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
        # Get cached taint results
        if not hasattr(self, '_taint_results'):
            from theauditor.taint import trace_taint
            self._taint_results = trace_taint(str(self.db_path), max_depth=5)
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
                # Check source
                source = path.get("source", {})
                if (source.get("file", "") == str(context.file_path) and 
                    abs(source.get("line", 0) - line) < 10):
                    # Check if var is in path
                    for step in path.get("path", []):
                        if var_name in str(step):
                            return True
            return False
        
        return is_tainted
    
    def collect_rule_patterns(self, registry):
        """Collect and register all taint patterns from rules that define them.
        
        This method DYNAMICALLY discovers and calls register_taint_patterns()
        functions from ALL rule modules, without hardcoding any module names.
        
        Args:
            registry: TaintRegistry instance to populate with patterns
            
        Returns:
            The populated registry
        """
        # Track unique modules we've already processed
        processed_modules = set()
        
        # Use the ALREADY DISCOVERED rules to find modules dynamically
        for category, rules in self.rules.items():
            for rule in rules:
                module_name = rule.module
                
                # Skip if we've already processed this module
                if module_name in processed_modules:
                    continue
                processed_modules.add(module_name)
                
                try:
                    # Import the module
                    module = importlib.import_module(module_name)
                    
                    # Check if it has register_taint_patterns function
                    if hasattr(module, 'register_taint_patterns'):
                        register_func = getattr(module, 'register_taint_patterns')
                        
                        # Call the registration function
                        register_func(registry)
                        
                        if self._debug:
                            print(f"[ORCHESTRATOR] Registered patterns from {module_name}")
                            
                except ImportError as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Failed to import {module_name}: {e}")
                except Exception as e:
                    if self._debug:
                        print(f"[ORCHESTRATOR] Warning: Error registering patterns from {module_name}: {e}")
        
        if self._debug:
            # Report statistics about registered patterns
            source_count = sum(len(patterns) for patterns in registry.sources.values())
            sink_count = sum(len(patterns) for patterns in registry.sinks.values())
            processed_count = len(processed_modules)
            print(f"[ORCHESTRATOR] Dynamically processed {processed_count} modules")
            print(f"[ORCHESTRATOR] Collected {source_count} sources and {sink_count} sinks from rules")
        
        return registry
    
    def _get_taint_tracer(self):
        """Get cached taint analysis results for rules to query.
        
        This provides rules with access to the main taint analyzer's
        results WITH JavaScript pattern support.
        
        Returns:
            A function that returns relevant taint paths
        """
        if self._taint_trace_func is None:
            # Run FULL taint analysis ONCE and cache it
            from theauditor.taint import trace_taint
            if not hasattr(self, '_taint_results'):
                self._taint_results = trace_taint(str(self.db_path), max_depth=5)
                if self._debug:
                    total = len(self._taint_results.get("taint_paths", []))
                    print(f"[ORCHESTRATOR] Cached {total} taint paths for rules", file=sys.stderr)
            
            def get_taint_for_location(source_var: str, source_file: str, source_line: int, source_function: str = "unknown"):
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
                    # Match by file and approximate line
                    if (source.get("file", "").endswith(source_file) and 
                        abs(source.get("line", 0) - source_line) < 10):
                        # Check if variable is in the path
                        for step in path.get("path", []):
                            if source_var in str(step.get("var", "")):
                                relevant_paths.append(path)
                                break
                return relevant_paths
            
            self._taint_trace_func = get_taint_for_location
        
        return self._taint_trace_func


# Convenience function for backward compatibility
def run_all_rules(project_path: str, db_path: str = None) -> List[Dict[str, Any]]:
    """Run all rules for a project.
    
    Args:
        project_path: Root path of the project
        db_path: Optional database path (defaults to .pf/repo_index.db)
        
    Returns:
        List of all findings
    """
    orchestrator = RulesOrchestrator(Path(project_path))
    
    context = RuleContext(
        db_path=db_path or str(orchestrator.db_path),
        project_path=Path(project_path)
    )
    
    return orchestrator.run_all_rules(context)