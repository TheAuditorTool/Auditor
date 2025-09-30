import sqlite3
from pathlib import Path

from theauditor.indexer import build_index


def test_jsx_dual_pass_outputs(tmp_path):
    fixture_root = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "plant"
    manifest_path = tmp_path / "manifest.json"
    db_path = tmp_path / "repo_index.db"

    result = build_index(
        root_path=str(fixture_root),
        manifest_path=str(manifest_path),
        db_path=str(db_path),
        print_stats=False,
    )
    assert result.get("success"), result

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE path=?",
            ("src/components/Dashboard.tsx",),
        )
        assert cursor.fetchone()[0] > 0

        cursor = conn.execute(
            "SELECT COUNT(*) FROM symbols_jsx WHERE path=?",
            ("src/components/Dashboard.tsx",),
        )
        assert cursor.fetchone()[0] > 0

        cursor = conn.execute(
            "SELECT COUNT(*) FROM react_components WHERE file=? AND component=?",
            ("src/components/Dashboard.tsx", "Dashboard"),
        )
        assert cursor.fetchone()[0] == 1

        cursor = conn.execute(
            "SELECT COUNT(*) FROM react_components WHERE file LIKE ?",
            ("%AccountController.ts%",),
        )
        assert cursor.fetchone()[0] == 0

        cursor = conn.execute(
            "SELECT has_jsx FROM function_returns_jsx WHERE file=? AND function_name=?",
            ("src/components/Dashboard.tsx", "Dashboard"),
        )
        assert cursor.fetchone()[0] == 1

        cursor = conn.execute(
            "SELECT value FROM framework_safe_sinks WHERE framework=? ORDER BY value",
            ("express",),
        )
        safe_sinks = {row[0] for row in cursor.fetchall()}
        assert {"res.json", "res.send", "res.status"}.issubset(safe_sinks)

        cursor = conn.execute("SELECT COUNT(*) FROM refs")
        assert cursor.fetchone()[0] == 5

        cursor = conn.execute("SELECT tables FROM sql_queries ORDER BY line_number")
        tables = {row[0] for row in cursor.fetchall()}
        assert "[\"PLANTS\"]" in tables
        assert "[\"PLANT_SNAPSHOTS\"]" in tables
    finally:
        conn.close()
