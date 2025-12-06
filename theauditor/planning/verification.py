"""Verification integration for planning system."""

from pathlib import Path

from theauditor.context.query import CodeQueryEngine
from theauditor.refactor.profiles import ProfileEvaluation, RefactorProfile, RefactorRuleEngine


def verify_task_spec(spec_yaml: str, db_path: Path, repo_root: Path) -> ProfileEvaluation:
    """Verify task completion using RefactorRuleEngine."""

    profile = RefactorProfile.load_from_string(spec_yaml)

    with RefactorRuleEngine(db_path, repo_root) as engine:
        evaluation = engine.evaluate(profile)

    return evaluation


def find_analogous_patterns(root: Path, pattern_spec: dict) -> list[dict]:
    """Find similar code patterns for greenfield tasks."""
    engine = CodeQueryEngine(root)
    pattern_type = pattern_spec.get("type")

    if pattern_type == "api_route":
        handlers = engine.get_api_handlers("")
        method = pattern_spec.get("method")
        if method:
            handlers = [h for h in handlers if h.get("method") == method]
        return handlers

    elif pattern_type == "function":
        name_pattern = pattern_spec.get("name", "*")
        symbols = engine.find_symbol(name_pattern)

        functions = [s for s in symbols if s.type == "function"]
        return [{"name": f.name, "file": f.file, "line": f.line, "type": f.type} for f in functions]

    elif pattern_type == "component":
        name_pattern = pattern_spec.get("name", "*")
        symbols = engine.find_symbol(name_pattern)

        components = [
            s
            for s in symbols
            if s.framework_type in ("component", "react_component", "vue_component")
        ]
        return [
            {"name": c.name, "file": c.file, "line": c.line, "framework_type": c.framework_type}
            for c in components
        ]

    else:
        raise ValueError(
            f"Unknown pattern type: {pattern_type}. Supported: api_route, function, component"
        )
