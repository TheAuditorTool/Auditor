"""End-to-end tests for Python framework extraction and import resolution."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from theauditor.indexer import IndexerOrchestrator

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "python"


def index_fixtures(tmp_path: Path, fixtures: list[str]) -> Path:
    """Copy the requested fixtures into a temp project and run the indexer."""

    project_root = tmp_path / "project"
    project_root.mkdir()

    for relative in fixtures:
        src = FIXTURE_ROOT / relative
        dest = project_root / relative
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    pf_dir = project_root / ".pf"
    pf_dir.mkdir()
    db_path = pf_dir / "repo_index.db"

    orchestrator = IndexerOrchestrator(project_root, str(db_path))
    orchestrator.db_manager.create_schema()
    orchestrator.index()

    return db_path


def fetchall(db_path: Path, query: str, params: tuple | None = None):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or tuple())
        return cursor.fetchall()


def test_sqlalchemy_models_extracted(tmp_path: Path):
    db_path = index_fixtures(tmp_path, ["sqlalchemy_app.py"])

    models = {row[0] for row in fetchall(db_path, "SELECT model_name FROM python_orm_models")}
    assert {"Organization", "User", "Profile", "Post", "Comment", "Tag"} <= models

    fk_rows = fetchall(
        db_path,
        "SELECT model_name, field_name, is_foreign_key FROM python_orm_fields WHERE model_name IN (?, ?) ORDER BY field_name",
        ("Post", "User"),
    )
    assert ("Post", "author_id", 1) in fk_rows
    assert ("User", "org_id", 1) in fk_rows

    relationships = fetchall(
        db_path,
        "SELECT source_model, target_model, relationship_type FROM orm_relationships",
    )
    assert ("User", "Organization", "belongsTo") in relationships
    assert ("Organization", "User", "hasMany") in relationships
    assert ("Post", "Tag", "manyToMany") in relationships


def test_pydantic_validators_extracted(tmp_path: Path):
    db_path = index_fixtures(tmp_path, ["pydantic_app.py"])

    validators = fetchall(
        db_path,
        "SELECT model_name, field_name, validator_method, validator_type FROM python_validators",
    )
    assert ("UserPayload", None, "passwords_match", "root") in validators
    assert ("Address", "postal_code", "postal_code_length", "field") in validators
    assert ("UserSettings", "timezone", "timezone_not_empty", "field") in validators


def test_flask_routes_extracted(tmp_path: Path):
    db_path = index_fixtures(tmp_path, ["flask_app.py"])

    routes = fetchall(
        db_path,
        "SELECT method, pattern, has_auth, blueprint FROM python_routes ORDER BY line",
    )
    assert len(routes) == 6
    assert ("GET", "/users", 1, "api") in routes
    assert ("POST", "/users", 1, "api") in routes
    assert all(row[3] == "api" for row in routes)


def test_fastapi_dependencies_extracted(tmp_path: Path):
    db_path = index_fixtures(tmp_path, ["fastapi_app.py"])

    rows = fetchall(
        db_path,
        "SELECT method, pattern, dependencies FROM python_routes ORDER BY line",
    )
    assert len(rows) == 5
    dependencies_map = {
        (method, pattern): json.loads(deps) if deps else []
        for method, pattern, deps in rows
    }
    assert dependencies_map[("GET", "/users")] == ["get_db"]
    assert dependencies_map[("GET", "/users/{user_id}")] == ["get_db", "get_current_user"]


def test_import_resolution_records_resolved_targets(tmp_path: Path):
    db_path = index_fixtures(tmp_path, ["import_resolution"])

    refs = fetchall(
        db_path,
        "SELECT src, value FROM refs WHERE src LIKE ? ORDER BY value",
        ("import_resolution/api/controllers.py",),
    )
    resolved = {value for _src, value in refs}
    assert {"services.user", "util.helpers"} <= resolved


def test_cross_framework_parity_sample(tmp_path: Path):
    db_path = index_fixtures(tmp_path, ["parity_sample.py"])

    route_count = fetchall(db_path, "SELECT COUNT(*) FROM python_routes")
    model_count = fetchall(db_path, "SELECT COUNT(*) FROM python_orm_models")
    assert route_count[0][0] > 0
    assert model_count[0][0] > 0
