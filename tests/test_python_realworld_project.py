"""End-to-end assertions for the synthetic realworld Python fixture."""


import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from theauditor.indexer import IndexerOrchestrator

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "python" / "realworld_project"


def index_realworld_fixture(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir()

    shutil.copytree(FIXTURE_ROOT, project_root / "realworld_project")

    pf_dir = project_root / ".pf"
    pf_dir.mkdir()
    db_path = pf_dir / "repo_index.db"

    orchestrator = IndexerOrchestrator(project_root, str(db_path))
    orchestrator.db_manager.create_schema()
    orchestrator.index()

    return db_path


def fetchall(db_path: Path, query: str, params: tuple | None = None) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or tuple())
        return cursor.fetchall()


@pytest.mark.integration
def test_realworld_project_end_to_end(tmp_path: Path) -> None:
    db_path = index_realworld_fixture(tmp_path)

    type_count = fetchall(
        db_path,
        "SELECT COUNT(*) FROM type_annotations WHERE file LIKE 'realworld_project/%'",
    )[0][0]
    assert type_count >= 15

    models = {
        row[0]
        for row in fetchall(
            db_path,
            "SELECT model_name FROM python_orm_models WHERE file LIKE 'realworld_project/%'",
        )
    }
    assert {"Organization", "User", "Profile", "AuditLog"} <= models

    relationships = {
        (row[0], row[1], row[2])
        for row in fetchall(
            db_path,
            "SELECT source_model, target_model, relationship_type FROM orm_relationships "
            "WHERE file LIKE 'realworld_project/%'",
        )
    }
    assert ("User", "Organization", "belongsTo") in relationships
    assert ("Organization", "User", "hasMany") in relationships
    assert ("User", "Profile", "hasOne") in relationships

    routes = fetchall(
        db_path,
        "SELECT framework, method, pattern, dependencies, blueprint FROM python_routes "
        "WHERE file LIKE 'realworld_project/%' ORDER BY framework, line",
    )
    fastapi_routes = [row for row in routes if row[0] == "fastapi"]
    assert any(route[1] == "POST" and route[2] == "/users" for route in fastapi_routes)
    dependencies = {
        (route[1], route[2]): json.loads(route[3]) if route[3] else []
        for route in fastapi_routes
    }
    assert dependencies[("POST", "/users")] == ["get_repository", "get_email_service"]

    flask_routes = [row for row in routes if row[0] == "flask"]
    assert any(route[4] == "admin" for route in flask_routes)

    validators = {
        (row[0], row[1], row[2], row[3])
        for row in fetchall(
            db_path,
            "SELECT model_name, field_name, validator_method, validator_type FROM python_validators "
            "WHERE file LIKE 'realworld_project/%'",
        )
    }
    assert ("AccountPayload", "timezone", "timezone_supported", "field") in validators
    assert ("AccountPayload", None, "title_matches_role", "root") in validators
