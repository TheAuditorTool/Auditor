"""Verification integration for planning system.

This module bridges planning with RefactorRuleEngine and CodeQueryEngine.

Integration Points:
- RefactorProfile.load() (refactor/profiles.py:121)
- RefactorRuleEngine.evaluate() (refactor/profiles.py:257)
- CodeQueryEngine.find_symbol() (context/query.py:158)
- CodeQueryEngine.get_api_handlers() (context/query.py:412)

NO FALLBACKS. Hard failure if spec YAML is malformed or database query fails.
"""
from __future__ import annotations


from pathlib import Path
from typing import List, Dict
import tempfile
import os

from theauditor.refactor.profiles import RefactorProfile, RefactorRuleEngine, ProfileEvaluation
from theauditor.context.query import CodeQueryEngine, SymbolInfo


def verify_task_spec(spec_yaml: str, db_path: Path, repo_root: Path) -> ProfileEvaluation:
    """Verify task completion using RefactorRuleEngine.

    Args:
        spec_yaml: YAML specification (RefactorProfile format)
        db_path: Path to repo_index.db
        repo_root: Project root directory

    Returns:
        ProfileEvaluation with violations and expected_references

    Integration:
        - Uses RefactorProfile.load() (refactor/profiles.py:121)
        - Uses RefactorRuleEngine.evaluate() (refactor/profiles.py:257)

    NO FALLBACKS. Raises ValueError if spec_yaml is malformed.

    Example:
        spec_yaml = '''
        refactor_name: Auth Migration
        description: Migrate from old_auth to new_auth
        rules:
          - id: old-auth-removed
            description: Old auth should be removed
            match:
              identifiers: [old_authenticate]
            expect:
              identifiers: [new_authenticate]
        '''
        evaluation = verify_task_spec(spec_yaml, db_path, repo_root)
        if evaluation.total_violations() == 0:
            print("Task verified: All old auth removed")
        else:
            print(f"Found {evaluation.total_violations()} violations")
    """
    # RefactorProfile.load expects a file path, create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write(spec_yaml)
        temp_path = Path(f.name)

    try:
        # Parse YAML into RefactorProfile
        # This validates YAML structure and rule format
        profile = RefactorProfile.load(temp_path)
    finally:
        os.unlink(temp_path)

    # Run verification using existing engine
    with RefactorRuleEngine(db_path, repo_root) as engine:
        evaluation = engine.evaluate(profile)

    return evaluation


def find_analogous_patterns(root: Path, pattern_spec: dict) -> list[dict]:
    """Find similar code patterns for greenfield tasks.

    Args:
        root: Project root (contains .pf/)
        pattern_spec: Dict describing pattern to find
          Example: {"type": "api_route", "method": "POST"}

    Returns:
        List of dicts matching pattern

    Integration:
        - Uses CodeQueryEngine.find_symbol() (context/query.py:158)
        - Uses CodeQueryEngine.get_api_handlers() (context/query.py:412)

    Use Case:
        Task: "Add POST /users route"
        Greenfield: No existing /users routes
        Analogous: find_analogous_patterns({"type": "api_route", "method": "POST"})
        Result: All existing POST routes for reference

    Example:
        # Find all POST routes
        patterns = find_analogous_patterns(root, {"type": "api_route", "method": "POST"})
        for route in patterns:
            print(f"{route['path']} in {route['file']}")

        # Find functions with name pattern
        patterns = find_analogous_patterns(root, {"type": "function", "name": "validate*"})
        for func in patterns:
            print(f"{func.name} in {func.file}:{func.line}")
    """
    engine = CodeQueryEngine(root)
    pattern_type = pattern_spec.get("type")

    if pattern_type == "api_route":
        # Find similar API routes
        handlers = engine.get_api_handlers("")  # All routes
        method = pattern_spec.get("method")
        if method:
            handlers = [h for h in handlers if h.get('method') == method]
        return handlers

    elif pattern_type == "function":
        # Find similar functions by name pattern
        name_pattern = pattern_spec.get("name", "*")
        symbols = engine.find_symbol(name_pattern)
        # Filter to functions only and convert to dict
        functions = [s for s in symbols if s.type == "function"]
        return [{"name": f.name, "file": f.file, "line": f.line, "type": f.type} for f in functions]

    elif pattern_type == "component":
        # Find similar React/Vue components
        name_pattern = pattern_spec.get("name", "*")
        symbols = engine.find_symbol(name_pattern)
        # Filter to components
        components = [s for s in symbols if s.framework_type in ("component", "react_component", "vue_component")]
        return [{"name": c.name, "file": c.file, "line": c.line, "framework_type": c.framework_type} for c in components]

    else:
        raise ValueError(f"Unknown pattern type: {pattern_type}. Supported: api_route, function, component")
