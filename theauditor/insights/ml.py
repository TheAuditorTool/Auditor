"""Offline ML signals for TheAuditor - manual trigger, non-blocking."""

import json
import os
import sqlite3
import subprocess
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

# Safe import of ML dependencies
ML_AVAILABLE = False
try:
    import joblib
    import numpy as np
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler

    ML_AVAILABLE = True
except ImportError:
    pass

# Schema contract validation
_SCHEMA_VALIDATED = False


def validate_ml_schema():
    """
    Validate ML queries against schema contract.

    This function ensures all database queries use valid column names
    from the schema contract, preventing runtime errors if schema changes.

    Called once at module initialization.
    """
    global _SCHEMA_VALIDATED
    if _SCHEMA_VALIDATED:
        return

    try:
        from theauditor.indexer.schema import get_table_schema

        # Validate refs table columns (used in load_graph_stats, load_semantic_import_features)
        refs_schema = get_table_schema("refs")
        refs_cols = set(refs_schema.column_names())
        assert "src" in refs_cols, "refs table missing 'src' column"
        assert "value" in refs_cols, "refs table missing 'value' column"
        assert "kind" in refs_cols, "refs table missing 'kind' column"

        # Validate symbols table columns (used in load_ast_complexity_metrics)
        symbols_schema = get_table_schema("symbols")
        symbols_cols = set(symbols_schema.column_names())
        assert "path" in symbols_cols, "symbols table missing 'path' column"
        assert "type" in symbols_cols, "symbols table missing 'type' column"
        assert "name" in symbols_cols, "symbols table missing 'name' column"

        # Validate api_endpoints table columns (used in load_graph_stats)
        api_endpoints_schema = get_table_schema("api_endpoints")
        api_cols = set(api_endpoints_schema.column_names())
        assert "file" in api_cols, "api_endpoints table missing 'file' column"

        # Validate sql_objects table columns (used in load_graph_stats)
        sql_objects_schema = get_table_schema("sql_objects")
        sql_cols = set(sql_objects_schema.column_names())
        assert "file" in sql_cols, "sql_objects table missing 'file' column"

        # Validate new enhancement tables
        jwt_patterns_schema = get_table_schema("jwt_patterns")
        jwt_cols = set(jwt_patterns_schema.column_names())
        assert "file_path" in jwt_cols, "jwt_patterns table missing 'file_path' column"
        assert "secret_source" in jwt_cols, "jwt_patterns table missing 'secret_source' column"

        sql_queries_schema = get_table_schema("sql_queries")
        sql_q_cols = set(sql_queries_schema.column_names())
        assert "file_path" in sql_q_cols, "sql_queries table missing 'file_path' column"
        assert "extraction_source" in sql_q_cols, (
            "sql_queries table missing 'extraction_source' column"
        )

        findings_schema = get_table_schema("findings_consolidated")
        findings_cols = set(findings_schema.column_names())
        assert "file" in findings_cols, "findings_consolidated table missing 'file' column"
        assert "severity" in findings_cols, "findings_consolidated table missing 'severity' column"
        assert "tool" in findings_cols, "findings_consolidated table missing 'tool' column"
        assert "cwe" in findings_cols, "findings_consolidated table missing 'cwe' column"

        type_annotations_schema = get_table_schema("type_annotations")
        type_cols = set(type_annotations_schema.column_names())
        assert "file" in type_cols, "type_annotations table missing 'file' column"
        assert "is_any" in type_cols, "type_annotations table missing 'is_any' column"
        assert "is_unknown" in type_cols, "type_annotations table missing 'is_unknown' column"

        cfg_blocks_schema = get_table_schema("cfg_blocks")
        cfg_cols = set(cfg_blocks_schema.column_names())
        assert "file" in cfg_cols, "cfg_blocks table missing 'file' column"

        cfg_edges_schema = get_table_schema("cfg_edges")
        cfg_e_cols = set(cfg_edges_schema.column_names())
        assert "file" in cfg_e_cols, "cfg_edges table missing 'file' column"

        _SCHEMA_VALIDATED = True

    except ImportError:
        # Schema module not available - skip validation
        pass
    except AssertionError as e:
        # Schema mismatch - log but don't crash
        print(f"[ML] Schema validation warning: {e}")
        _SCHEMA_VALIDATED = True  # Mark as validated to avoid repeated warnings


def check_ml_available():
    """Check if ML dependencies are available."""
    if not ML_AVAILABLE:
        print("ML disabled. Install extras: pip install -e .[ml]")
        return False
    # Validate schema contract on first ML operation
    validate_ml_schema()
    return True


def fowler_noll_hash(text: str, dim: int = 2000) -> int:
    """Simple FNV-1a hash for text feature hashing."""
    FNV_PRIME = 0x01000193
    FNV_OFFSET = 0x811C9DC5

    hash_val = FNV_OFFSET
    for char in text.encode("utf-8"):
        hash_val ^= char
        hash_val = (hash_val * FNV_PRIME) & 0xFFFFFFFF

    return hash_val % dim


def extract_text_features(
    path: str, rca_messages: list[str] = None, dim: int = 2000
) -> dict[int, float]:
    """Extract hashed text features from path and RCA messages."""
    features = defaultdict(float)

    # Hash path components
    parts = Path(path).parts
    for part in parts:
        idx = fowler_noll_hash(part, dim)
        features[idx] += 1.0

    # Hash basename
    basename = Path(path).name
    idx = fowler_noll_hash(basename, dim)
    features[idx] += 2.0

    # Hash RCA messages if present
    if rca_messages:
        for msg in rca_messages[:5]:  # Limit to recent 5
            tokens = msg.lower().split()[:10]  # First 10 tokens
            for token in tokens:
                idx = fowler_noll_hash(token, dim)
                features[idx] += 0.5

    return dict(features)


def load_journal_stats(
    history_dir: Path, window: int = 50, run_type: str = "full"
) -> dict[str, dict]:
    """
    Load and aggregate stats from all historical journal files.

    Args:
        history_dir: Base history directory
        window: Number of recent entries to analyze per file
        run_type: Type of runs to load ("full", "diff", or "all")
    """
    if not history_dir.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "touches": 0,
            "failures": 0,
            "successes": 0,
            "recent_phases": [],
        }
    )

    try:
        # Find historical journal files based on run type
        if run_type == "full":
            journal_files = list(history_dir.glob("full/*/journal.ndjson"))
        elif run_type == "diff":
            journal_files = list(history_dir.glob("diff/*/journal.ndjson"))
        else:  # run_type == "all"
            journal_files = list(history_dir.glob("*/*/journal.ndjson"))

        # If no journal files found, fallback to FCE data
        if not journal_files:
            print(
                "Warning: No journal.ndjson files found. "
                "Using FCE and AST failure data as fallback for training."
            )

            # Load from FCE files instead
            if run_type == "full":
                fce_files = list(history_dir.glob("full/*/raw/fce.json"))
            elif run_type == "diff":
                fce_files = list(history_dir.glob("diff/*/raw/fce.json"))
            else:  # run_type == "all"
                fce_files = list(history_dir.glob("*/*/raw/fce.json"))

            # Process FCE files as proxy for journal data
            for fce_path in fce_files:
                try:
                    with open(fce_path) as f:
                        data = json.load(f)

                    # Treat each finding as a "touch" and errors/criticals as "failures"
                    for finding in data.get("all_findings", []):
                        file = finding.get("file", "")
                        if file:
                            stats[file]["touches"] += 1
                            severity = finding.get("severity", "")
                            if severity in ["error", "critical"]:
                                stats[file]["failures"] += 1
                            else:
                                stats[file]["successes"] += 1
                except Exception:
                    continue  # Skip files that can't be read

            return dict(stats)

        for journal_path in journal_files:
            try:
                with open(journal_path) as f:
                    # Approximate last N runs per file
                    lines = f.readlines()[-window * 20 :]

                    for line in lines:
                        try:
                            event = json.loads(line)

                            if event.get("phase") == "apply_patch" and "file" in event:
                                file = event["file"]
                                stats[file]["touches"] += 1

                            if "result" in event:
                                for file_path in stats:
                                    if event["result"] == "fail":
                                        stats[file_path]["failures"] += 1
                                    else:
                                        stats[file_path]["successes"] += 1

                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue  # Skip files that can't be read
    except (ImportError, ValueError, AttributeError):
        pass  # ML unavailable - gracefully skip

    return dict(stats)


def load_rca_stats(history_dir: Path, run_type: str = "full") -> dict[str, dict]:
    """
    Load RCA failure stats from all historical RCA files.

    Args:
        history_dir: Base history directory
        run_type: Type of runs to load ("full", "diff", or "all")
    """
    if not history_dir.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "fail_count": 0,
            "categories": [],
            "messages": [],
        }
    )

    try:
        # Find historical FCE files based on run type
        if run_type == "full":
            fce_files = list(history_dir.glob("full/*/fce.json"))
        elif run_type == "diff":
            fce_files = list(history_dir.glob("diff/*/fce.json"))
        else:  # run_type == "all"
            fce_files = list(history_dir.glob("*/*/fce.json"))

        for fce_path in fce_files:
            try:
                with open(fce_path) as f:
                    data = json.load(f)

                for failure in data.get("failures", []):
                    file = failure.get("file", "")
                    if file:
                        stats[file]["fail_count"] += 1
                        if "category" in failure:
                            stats[file]["categories"].append(failure["category"])
                        if "message" in failure:
                            stats[file]["messages"].append(failure["message"][:100])
            except Exception:
                continue  # Skip files that can't be read
    except (ImportError, ValueError, AttributeError):
        pass  # ML unavailable - gracefully skip

    return dict(stats)


def load_ast_stats(history_dir: Path, run_type: str = "full") -> dict[str, dict]:
    """
    Load AST proof stats from all historical AST files.

    Args:
        history_dir: Base history directory
        run_type: Type of runs to load ("full", "diff", or "all")
    """
    if not history_dir.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "invariant_fails": 0,
            "invariant_passes": 0,
            "failed_checks": [],
        }
    )

    try:
        # Find historical AST proof files based on run type
        if run_type == "full":
            ast_files = list(history_dir.glob("full/*/ast_proofs.json"))
        elif run_type == "diff":
            ast_files = list(history_dir.glob("diff/*/ast_proofs.json"))
        else:  # run_type == "all"
            ast_files = list(history_dir.glob("*/*/ast_proofs.json"))

        for ast_path in ast_files:
            try:
                with open(ast_path) as f:
                    data = json.load(f)

                for result in data.get("results", []):
                    file = result.get("path", "")
                    for check in result.get("checks", []):
                        if check["status"] == "FAIL":
                            stats[file]["invariant_fails"] += 1
                            stats[file]["failed_checks"].append(check["id"])
                        elif check["status"] == "PASS":
                            stats[file]["invariant_passes"] += 1
            except Exception:
                continue  # Skip files that can't be read
    except (ImportError, ValueError, AttributeError):
        pass  # ML unavailable - gracefully skip

    return dict(stats)


def load_security_pattern_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """
    Extract security pattern features from jwt_patterns and sql_queries tables.

    Returns dict with keys: jwt_usage_count, sql_query_count, has_hardcoded_secret, has_weak_crypto
    """
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "jwt_usage_count": 0,
            "sql_query_count": 0,
            "has_hardcoded_secret": False,
            "has_weak_crypto": False,
        }
    )

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(file_paths))

        # Query jwt_patterns table
        cursor.execute(
            f"""
            SELECT file_path, COUNT(*) as count
            FROM jwt_patterns
            WHERE file_path IN ({placeholders})
            GROUP BY file_path
        """,
            file_paths,
        )

        for file_path, count in cursor.fetchall():
            stats[file_path]["jwt_usage_count"] = count

        # Query for hardcoded secrets
        cursor.execute(
            f"""
            SELECT DISTINCT file_path
            FROM jwt_patterns
            WHERE file_path IN ({placeholders})
            AND secret_source = 'hardcoded'
        """,
            file_paths,
        )

        for (file_path,) in cursor.fetchall():
            stats[file_path]["has_hardcoded_secret"] = True

        # Query for weak crypto algorithms
        cursor.execute(
            f"""
            SELECT DISTINCT file_path
            FROM jwt_patterns
            WHERE file_path IN ({placeholders})
            AND algorithm IN ('HS256', 'none', 'None')
        """,
            file_paths,
        )

        for (file_path,) in cursor.fetchall():
            stats[file_path]["has_weak_crypto"] = True

        # Query sql_queries table
        cursor.execute(
            f"""
            SELECT file_path, COUNT(*) as count
            FROM sql_queries
            WHERE file_path IN ({placeholders})
            AND extraction_source = 'code_execute'
            GROUP BY file_path
        """,
            file_paths,
        )

        for file_path, count in cursor.fetchall():
            stats[file_path]["sql_query_count"] = count

        conn.close()
    except Exception:
        pass  # Gracefully skip on error

    return dict(stats)


def load_vulnerability_flow_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """
    Extract taint flow features from findings_consolidated table.

    Returns dict with keys: critical_findings, high_findings, medium_findings, unique_cwe_count
    """
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "critical_findings": 0,
            "high_findings": 0,
            "medium_findings": 0,
            "unique_cwe_count": 0,
        }
    )

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(file_paths))

        # Query findings_consolidated (dual-write pattern table)
        cursor.execute(
            f"""
            SELECT file, severity, COUNT(*) as count
            FROM findings_consolidated
            WHERE file IN ({placeholders})
            AND tool = 'taint'
            GROUP BY file, severity
        """,
            file_paths,
        )

        for file_path, severity, count in cursor.fetchall():
            if severity == "critical":
                stats[file_path]["critical_findings"] = count
            elif severity == "high":
                stats[file_path]["high_findings"] = count
            elif severity == "medium":
                stats[file_path]["medium_findings"] = count

        # Count unique CWEs per file
        cursor.execute(
            f"""
            SELECT file, COUNT(DISTINCT cwe) as unique_cwes
            FROM findings_consolidated
            WHERE file IN ({placeholders})
            AND cwe IS NOT NULL
            GROUP BY file
        """,
            file_paths,
        )

        for file_path, unique_cwes in cursor.fetchall():
            stats[file_path]["unique_cwe_count"] = unique_cwes

        conn.close()
    except Exception:
        pass  # Gracefully skip on error

    return dict(stats)


def load_type_coverage_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """
    Extract TypeScript type annotation coverage from type_annotations table.

    Returns dict with keys: type_annotation_count, any_type_count, unknown_type_count,
                           generic_type_count, type_coverage_ratio
    """
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "type_annotation_count": 0,
            "any_type_count": 0,
            "unknown_type_count": 0,
            "generic_type_count": 0,
            "type_coverage_ratio": 0.0,
        }
    )

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(file_paths))

        # Query type_annotations table (13 field semantic analysis!)
        cursor.execute(
            f"""
            SELECT file,
                   COUNT(*) as total,
                   SUM(CASE WHEN is_any = 1 THEN 1 ELSE 0 END) as any_count,
                   SUM(CASE WHEN is_unknown = 1 THEN 1 ELSE 0 END) as unknown_count,
                   SUM(CASE WHEN is_generic = 1 THEN 1 ELSE 0 END) as generic_count
            FROM type_annotations
            WHERE file IN ({placeholders})
            GROUP BY file
        """,
            file_paths,
        )

        for file_path, total, any_count, unknown_count, generic_count in cursor.fetchall():
            stats[file_path]["type_annotation_count"] = total
            stats[file_path]["any_type_count"] = any_count
            stats[file_path]["unknown_type_count"] = unknown_count
            stats[file_path]["generic_type_count"] = generic_count

            # Calculate type coverage (1.0 - ratio of any/unknown types)
            typed = total - any_count - unknown_count
            stats[file_path]["type_coverage_ratio"] = typed / total if total > 0 else 0.0

        conn.close()
    except Exception:
        pass  # Gracefully skip on error

    return dict(stats)


def load_cfg_complexity_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """
    Extract control flow complexity from cfg_blocks and cfg_edges tables.

    Returns dict with keys: cfg_block_count, cfg_edge_count, cyclomatic_complexity
    """
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "cfg_block_count": 0,
            "cfg_edge_count": 0,
            "cyclomatic_complexity": 0,
        }
    )

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(file_paths))

        # Query cfg_blocks table
        cursor.execute(
            f"""
            SELECT file, COUNT(*) as block_count
            FROM cfg_blocks
            WHERE file IN ({placeholders})
            GROUP BY file
        """,
            file_paths,
        )

        for file_path, block_count in cursor.fetchall():
            stats[file_path]["cfg_block_count"] = block_count

        # Query cfg_edges for complexity
        cursor.execute(
            f"""
            SELECT file, COUNT(*) as edge_count
            FROM cfg_edges
            WHERE file IN ({placeholders})
            GROUP BY file
        """,
            file_paths,
        )

        for file_path, edge_count in cursor.fetchall():
            stats[file_path]["cfg_edge_count"] = edge_count
            # Cyclomatic complexity = edges - blocks + 2
            blocks = stats[file_path]["cfg_block_count"]
            stats[file_path]["cyclomatic_complexity"] = edge_count - blocks + 2

        conn.close()
    except Exception:
        pass  # Gracefully skip on error

    return dict(stats)


def load_historical_findings(history_dir: Path, run_type: str = "full") -> dict[str, dict]:
    """
    Load historical findings from findings_consolidated table in past runs.

    Returns dict with keys: total_findings, critical_count, high_count, recurring_cwes
    """
    if not history_dir.exists():
        return {}

    stats = defaultdict(
        lambda: {
            "total_findings": 0,
            "critical_count": 0,
            "high_count": 0,
            "recurring_cwes": [],
        }
    )

    try:
        # Find historical database files
        if run_type == "full":
            db_files = list(history_dir.glob("full/*/repo_index.db"))
        elif run_type == "diff":
            db_files = list(history_dir.glob("diff/*/repo_index.db"))
        else:
            db_files = list(history_dir.glob("*/*/repo_index.db"))

        for db_path in db_files:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT file, severity, cwe, COUNT(*) as count
                    FROM findings_consolidated
                    GROUP BY file, severity, cwe
                """)

                for file_path, severity, cwe, count in cursor.fetchall():
                    stats[file_path]["total_findings"] += count
                    if severity == "critical":
                        stats[file_path]["critical_count"] += count
                    elif severity == "high":
                        stats[file_path]["high_count"] += count
                    if cwe:
                        stats[file_path]["recurring_cwes"].append(cwe)

                conn.close()
            except Exception:
                continue
    except Exception:
        pass  # Gracefully skip on error

    return dict(stats)


def load_graph_stats(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """Load graph topology stats from index DB."""
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "in_degree": 0,
            "out_degree": 0,
            "has_routes": False,
            "has_sql": False,
        }
    )

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get refs (imports/exports)
        placeholders = ",".join("?" * len(file_paths))

        # In-degree: files that import this file
        cursor.execute(
            f"""
            SELECT value, COUNT(*) as count
            FROM refs
            WHERE value IN ({placeholders})
            GROUP BY value
        """,
            file_paths,
        )

        for file_path, count in cursor.fetchall():
            stats[file_path]["in_degree"] = count

        # Out-degree: files this file imports
        cursor.execute(
            f"""
            SELECT src, COUNT(*) as count
            FROM refs
            WHERE src IN ({placeholders})
            GROUP BY src
        """,
            file_paths,
        )

        for file_path, count in cursor.fetchall():
            stats[file_path]["out_degree"] = count

        # Check for routes (now stored in api_endpoints table after refactor)
        cursor.execute(
            f"""
            SELECT DISTINCT file
            FROM api_endpoints
            WHERE file IN ({placeholders})
        """,
            file_paths,
        )

        for (file_path,) in cursor.fetchall():
            stats[file_path]["has_routes"] = True

        # Check for SQL objects
        cursor.execute(
            f"""
            SELECT DISTINCT file
            FROM sql_objects
            WHERE file IN ({placeholders})
        """,
            file_paths,
        )

        for (file_path,) in cursor.fetchall():
            stats[file_path]["has_sql"] = True

        conn.close()
    except (ImportError, ValueError, AttributeError):
        pass  # ML unavailable - gracefully skip

    return dict(stats)


def load_git_churn(file_paths: list[str], window_days: int = 30) -> dict[str, int]:
    """Load git churn counts if available."""
    if not Path(".git").exists():
        return {}

    churn = defaultdict(int)

    try:
        # Use temp files to avoid buffer overflow
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

            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--name-only",
                    "--pretty=format:",
                    f"--since={window_days} days ago",
                ],
                stdout=stdout_fp,
                stderr=stderr_fp,
                text=True,
                timeout=10,
            )

        with open(stdout_path, "r", encoding="utf-8") as f:
            result.stdout = f.read()
        with open(stderr_path, "r", encoding="utf-8") as f:
            result.stderr = f.read()

        os.unlink(stdout_path)
        os.unlink(stderr_path)

        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line and line in file_paths:
                    churn[line] += 1
    except (ImportError, ValueError, AttributeError):
        pass  # ML unavailable - gracefully skip

    return dict(churn)


def load_semantic_import_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """
    Extract semantic import features to understand file purpose.

    Returns dict with keys: has_http_import, has_db_import, has_auth_import, has_test_import
    """
    if not Path(db_path).exists() or not file_paths:
        return {}

    # Common library patterns for different purposes (frozensets for O(1) lookup)
    HTTP_LIBS = frozenset(
        {
            "requests",
            "aiohttp",
            "httpx",
            "urllib",
            "axios",
            "fetch",
            "superagent",
            "express",
            "fastapi",
            "flask",
            "django.http",
            "tornado",
            "starlette",
        }
    )

    DB_LIBS = frozenset(
        {
            "sqlalchemy",
            "psycopg2",
            "psycopg",
            "pymongo",
            "redis",
            "django.db",
            "peewee",
            "tortoise",
            "databases",
            "asyncpg",
            "sqlite3",
            "mysql",
            "mongoose",
            "sequelize",
            "typeorm",
            "prisma",
            "knex",
            "pg",
        }
    )

    AUTH_LIBS = frozenset(
        {
            "jwt",
            "pyjwt",
            "passlib",
            "oauth",
            "oauth2",
            "authlib",
            "django.contrib.auth",
            "flask_login",
            "flask_jwt",
            "bcrypt",
            "cryptography",
            "passport",
            "jsonwebtoken",
            "express-jwt",
            "firebase-auth",
            "auth0",
        }
    )

    TEST_LIBS = frozenset(
        {
            "pytest",
            "unittest",
            "mock",
            "faker",
            "factory_boy",
            "hypothesis",
            "jest",
            "mocha",
            "chai",
            "sinon",
            "enzyme",
            "vitest",
            "testing-library",
        }
    )

    stats = defaultdict(
        lambda: {
            "has_http_import": False,
            "has_db_import": False,
            "has_auth_import": False,
            "has_test_import": False,
        }
    )

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(file_paths))

        # Get all imports for the specified files
        cursor.execute(
            f"""
            SELECT src, value
            FROM refs
            WHERE src IN ({placeholders})
            AND kind IN ('import', 'from', 'require')
            """,
            file_paths,
        )

        for file_path, import_value in cursor.fetchall():
            # Normalize import value (strip quotes, extract package name)
            import_name = import_value.lower().strip("\"'")
            # Handle scoped packages like @angular/core
            if "/" in import_name:
                import_name = import_name.split("/")[0].lstrip("@")
            # Handle sub-modules like django.contrib.auth
            base_import = import_name.split(".")[0]

            # Check against our semantic categories
            if any(lib in import_name or base_import == lib for lib in HTTP_LIBS):
                stats[file_path]["has_http_import"] = True

            if any(lib in import_name or base_import == lib for lib in DB_LIBS):
                stats[file_path]["has_db_import"] = True

            if any(lib in import_name or base_import == lib for lib in AUTH_LIBS):
                stats[file_path]["has_auth_import"] = True

            if any(lib in import_name or base_import == lib for lib in TEST_LIBS):
                stats[file_path]["has_test_import"] = True

        conn.close()
    except Exception:
        pass  # Gracefully skip on error

    return dict(stats)


def load_ast_complexity_metrics(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """
    Extract AST-based complexity metrics from the symbols table.

    Returns dict with keys: function_count, class_count, call_count,
                           try_except_count, async_def_count
    """
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "function_count": 0,
            "class_count": 0,
            "call_count": 0,
            "try_except_count": 0,
            "async_def_count": 0,
        }
    )

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(file_paths))

        # Count different symbol types per file
        cursor.execute(
            f"""
            SELECT path, type, COUNT(*) as count
            FROM symbols
            WHERE path IN ({placeholders})
            GROUP BY path, type
            """,
            file_paths,
        )

        for file_path, symbol_type, count in cursor.fetchall():
            if symbol_type == "function":
                stats[file_path]["function_count"] = count
            elif symbol_type == "class":
                stats[file_path]["class_count"] = count
            elif symbol_type == "call":
                stats[file_path]["call_count"] = count

        # Count async functions (those with 'async' in the name)
        # This is a heuristic since we don't have a dedicated async flag
        cursor.execute(
            f"""
            SELECT path, COUNT(*) as count
            FROM symbols
            WHERE path IN ({placeholders})
            AND type = 'function'
            AND (name LIKE 'async%' OR name LIKE '%async%')
            GROUP BY path
            """,
            file_paths,
        )

        for file_path, count in cursor.fetchall():
            stats[file_path]["async_def_count"] = count

        # Count try/except patterns - look for exception handling calls
        # Common patterns: catch, except, rescue, error
        cursor.execute(
            f"""
            SELECT path, COUNT(*) as count
            FROM symbols
            WHERE path IN ({placeholders})
            AND type = 'call'
            AND (name IN ('catch', 'except', 'rescue', 'error', 'try', 'finally'))
            GROUP BY path
            """,
            file_paths,
        )

        for file_path, count in cursor.fetchall():
            stats[file_path]["try_except_count"] = count

        conn.close()
    except Exception:
        pass  # Gracefully skip on error

    return dict(stats)


def build_feature_matrix(
    file_paths: list[str],
    manifest_path: str,
    db_path: str,
    journal_stats: dict = None,
    rca_stats: dict = None,
    ast_stats: dict = None,
    enable_git: bool = False,
) -> tuple["np.ndarray", dict[str, int]]:
    """Build feature matrix for files."""
    if not ML_AVAILABLE:
        return None, {}

    # Load manifest for file metadata
    manifest_map = {}
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        for entry in manifest:
            manifest_map[entry["path"]] = entry
    except (ImportError, ValueError, AttributeError):
        pass  # ML unavailable - gracefully skip

    # Use provided stats or default to empty dicts
    journal_stats = journal_stats if journal_stats is not None else {}
    rca_stats = rca_stats if rca_stats is not None else {}
    ast_stats = ast_stats if ast_stats is not None else {}
    graph_stats = load_graph_stats(db_path, file_paths)

    # Load centrality from graph metrics if available
    try:
        metrics_path = Path("./.pf/raw/graph_metrics.json")
        if metrics_path.exists():
            with open(metrics_path) as f:
                graph_metrics = json.load(f)
            # Merge into existing stats
            for path in file_paths:
                if path in graph_metrics:
                    if path not in graph_stats:
                        graph_stats[path] = {
                            "in_degree": 0,
                            "out_degree": 0,
                            "has_routes": False,
                            "has_sql": False,
                        }
                    graph_stats[path]["centrality"] = graph_metrics[path]
    except (json.JSONDecodeError, IOError):
        pass  # Proceed without centrality scores

    git_churn = load_git_churn(file_paths) if enable_git else {}

    # Load new advanced features
    semantic_imports = load_semantic_import_features(db_path, file_paths)
    complexity_metrics = load_ast_complexity_metrics(db_path, file_paths)

    # Load security pattern features
    security_patterns = load_security_pattern_features(db_path, file_paths)

    # Load vulnerability flow features
    vulnerability_flows = load_vulnerability_flow_features(db_path, file_paths)

    # Load type coverage features (TypeScript)
    type_coverage = load_type_coverage_features(db_path, file_paths)

    # Load CFG complexity features
    cfg_complexity = load_cfg_complexity_features(db_path, file_paths)

    # Load historical findings
    history_dir = Path("./.pf/history")
    historical_findings = load_historical_findings(history_dir, run_type="full")

    # Build feature vectors
    feature_names = []
    features = []

    for file_path in file_paths:
        feat = []

        # Basic metadata features
        meta = manifest_map.get(file_path, {})
        feat.append(meta.get("bytes", 0) / 10000.0)  # Normalized
        feat.append(meta.get("loc", 0) / 100.0)  # Normalized

        # Extension as categorical
        ext = meta.get("ext", "")
        feat.append(1.0 if ext in [".ts", ".tsx", ".js", ".jsx"] else 0.0)
        feat.append(1.0 if ext == ".py" else 0.0)

        # Graph topology
        graph = graph_stats.get(file_path, {})
        feat.append(graph.get("in_degree", 0) / 10.0)
        feat.append(graph.get("out_degree", 0) / 10.0)
        feat.append(1.0 if graph.get("has_routes") else 0.0)
        feat.append(1.0 if graph.get("has_sql") else 0.0)
        feat.append(graph.get("centrality", 0.0))  # Already normalized [0,1]

        # Journal history
        journal = journal_stats.get(file_path, {})
        feat.append(journal.get("touches", 0) / 10.0)
        feat.append(journal.get("failures", 0) / 5.0)
        feat.append(journal.get("successes", 0) / 5.0)

        # RCA history
        rca = rca_stats.get(file_path, {})
        feat.append(rca.get("fail_count", 0) / 5.0)

        # AST checks
        ast = ast_stats.get(file_path, {})
        feat.append(ast.get("invariant_fails", 0) / 3.0)
        feat.append(ast.get("invariant_passes", 0) / 3.0)

        # Git churn
        feat.append(git_churn.get(file_path, 0) / 5.0)

        # NEW: Semantic import features
        semantic = semantic_imports.get(file_path, {})
        feat.append(1.0 if semantic.get("has_http_import") else 0.0)
        feat.append(1.0 if semantic.get("has_db_import") else 0.0)
        feat.append(1.0 if semantic.get("has_auth_import") else 0.0)
        feat.append(1.0 if semantic.get("has_test_import") else 0.0)

        # NEW: AST complexity metrics
        complexity = complexity_metrics.get(file_path, {})
        feat.append(complexity.get("function_count", 0) / 20.0)  # Normalized
        feat.append(complexity.get("class_count", 0) / 10.0)  # Normalized
        feat.append(complexity.get("call_count", 0) / 50.0)  # Normalized
        feat.append(complexity.get("try_except_count", 0) / 5.0)  # Normalized
        feat.append(complexity.get("async_def_count", 0) / 5.0)  # Normalized

        # NEW: Security pattern features
        security = security_patterns.get(file_path, {})
        feat.append(security.get("jwt_usage_count", 0) / 5.0)  # Normalized
        feat.append(security.get("sql_query_count", 0) / 10.0)  # Normalized
        feat.append(1.0 if security.get("has_hardcoded_secret") else 0.0)
        feat.append(1.0 if security.get("has_weak_crypto") else 0.0)

        # NEW: Vulnerability flow features
        vuln = vulnerability_flows.get(file_path, {})
        feat.append(vuln.get("critical_findings", 0) / 3.0)  # Normalized
        feat.append(vuln.get("high_findings", 0) / 5.0)  # Normalized
        feat.append(vuln.get("medium_findings", 0) / 10.0)  # Normalized
        feat.append(vuln.get("unique_cwe_count", 0) / 5.0)  # Normalized

        # NEW: Type coverage features (TypeScript)
        types = type_coverage.get(file_path, {})
        feat.append(types.get("type_annotation_count", 0) / 50.0)  # Normalized
        feat.append(types.get("any_type_count", 0) / 10.0)  # Normalized
        feat.append(types.get("unknown_type_count", 0) / 10.0)  # Normalized
        feat.append(types.get("generic_type_count", 0) / 10.0)  # Normalized
        feat.append(types.get("type_coverage_ratio", 0.0))  # Already [0,1]

        # NEW: CFG complexity features
        cfg = cfg_complexity.get(file_path, {})
        feat.append(cfg.get("cfg_block_count", 0) / 20.0)  # Normalized
        feat.append(cfg.get("cfg_edge_count", 0) / 30.0)  # Normalized
        feat.append(cfg.get("cyclomatic_complexity", 0) / 10.0)  # Normalized

        # NEW: Historical findings features
        hist = historical_findings.get(file_path, {})
        feat.append(hist.get("total_findings", 0) / 10.0)  # Normalized
        feat.append(hist.get("critical_count", 0) / 3.0)  # Normalized
        feat.append(hist.get("high_count", 0) / 5.0)  # Normalized
        feat.append(len(hist.get("recurring_cwes", [])) / 5.0)  # Normalized

        # Text features (simplified - just path hash)
        text_feats = extract_text_features(
            file_path,
            rca.get("messages", []),
            dim=50,  # Small for speed
        )
        text_vec = [0.0] * 50
        for idx, val in text_feats.items():
            if idx < 50:
                text_vec[idx] = val
        feat.extend(text_vec)

        features.append(feat)

    # Feature names for debugging
    feature_names = [
        "bytes_norm",
        "loc_norm",
        "is_js",
        "is_py",
        "in_degree",
        "out_degree",
        "has_routes",
        "has_sql",
        "centrality",
        "touches",
        "failures",
        "successes",
        "rca_fails",
        "ast_fails",
        "ast_passes",
        "git_churn",
        # Semantic import features
        "has_http_import",
        "has_db_import",
        "has_auth_import",
        "has_test_import",
        # AST complexity metrics
        "function_count",
        "class_count",
        "call_count",
        "try_except_count",
        "async_def_count",
        # Security pattern features
        "jwt_usage_count",
        "sql_query_count",
        "has_hardcoded_secret",
        "has_weak_crypto",
        # Vulnerability flow features
        "critical_findings",
        "high_findings",
        "medium_findings",
        "unique_cwe_count",
        # Type coverage features (TypeScript)
        "type_annotation_count",
        "any_type_count",
        "unknown_type_count",
        "generic_type_count",
        "type_coverage_ratio",
        # CFG complexity features
        "cfg_block_count",
        "cfg_edge_count",
        "cyclomatic_complexity",
        # Historical findings features
        "total_findings_hist",
        "critical_count_hist",
        "high_count_hist",
        "recurring_cwe_count",
    ] + [f"text_{i}" for i in range(50)]

    feature_name_map = {name: i for i, name in enumerate(feature_names)}

    return np.array(features), feature_name_map


def build_labels(
    file_paths: list[str],
    journal_stats: dict,
    rca_stats: dict,
) -> tuple["np.ndarray", "np.ndarray", "np.ndarray"]:
    """Build label vectors for training."""
    if not ML_AVAILABLE:
        return None, None, None

    # Root cause labels (binary): file failed in RCA
    root_cause_labels = np.array(
        [1.0 if rca_stats.get(fp, {}).get("fail_count", 0) > 0 else 0.0 for fp in file_paths]
    )

    # Next edit labels (binary): file was edited in journal
    next_edit_labels = np.array(
        [1.0 if journal_stats.get(fp, {}).get("touches", 0) > 0 else 0.0 for fp in file_paths]
    )

    # Risk scores (continuous): failure ratio
    risk_labels = np.array(
        [
            min(
                1.0,
                journal_stats.get(fp, {}).get("failures", 0)
                / max(1, journal_stats.get(fp, {}).get("touches", 1)),
            )
            for fp in file_paths
        ]
    )

    return root_cause_labels, next_edit_labels, risk_labels


def train_models(
    features: "np.ndarray",
    root_cause_labels: "np.ndarray",
    next_edit_labels: "np.ndarray",
    risk_labels: "np.ndarray",
    seed: int = 13,
    sample_weight: "np.ndarray" = None,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """
    Train the three models with optional sample weighting for human feedback
    and probability calibration.
    """
    if not ML_AVAILABLE:
        return None, None, None, None, None, None

    # Handle empty or all-same labels
    if len(np.unique(root_cause_labels)) < 2:
        root_cause_labels[0] = 1 - root_cause_labels[0]  # Flip one for training
    if len(np.unique(next_edit_labels)) < 2:
        next_edit_labels[0] = 1 - next_edit_labels[0]

    # Scale features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # Train root cause classifier with GradientBoostingClassifier
    # More powerful ensemble model that captures non-linear relationships
    root_cause_clf = GradientBoostingClassifier(
        n_estimators=50,  # Reduced for speed
        learning_rate=0.1,
        max_depth=3,
        random_state=seed,
        subsample=0.8,  # Stochastic gradient boosting
        min_samples_split=5,  # Prevent overfitting
    )
    root_cause_clf.fit(features_scaled, root_cause_labels, sample_weight=sample_weight)

    # Train next edit classifier with GradientBoostingClassifier
    next_edit_clf = GradientBoostingClassifier(
        n_estimators=50,
        learning_rate=0.1,
        max_depth=3,
        random_state=seed,
        subsample=0.8,
        min_samples_split=5,
    )
    next_edit_clf.fit(features_scaled, next_edit_labels, sample_weight=sample_weight)

    # Train risk regressor (keep Ridge for regression task)
    risk_reg = Ridge(alpha=1.0, random_state=seed)
    risk_reg.fit(features_scaled, risk_labels, sample_weight=sample_weight)

    # Calibrate probabilities using isotonic regression (already imported at top!)
    # This improves probability estimates for more accurate risk scoring
    root_cause_calibrator = IsotonicRegression(out_of_bounds="clip")
    root_cause_probs = root_cause_clf.predict_proba(features_scaled)[:, 1]
    root_cause_calibrator.fit(root_cause_probs, root_cause_labels)

    next_edit_calibrator = IsotonicRegression(out_of_bounds="clip")
    next_edit_probs = next_edit_clf.predict_proba(features_scaled)[:, 1]
    next_edit_calibrator.fit(next_edit_probs, next_edit_labels)

    return (
        root_cause_clf,
        next_edit_clf,
        risk_reg,
        scaler,
        root_cause_calibrator,
        next_edit_calibrator,
    )


def save_models(
    model_dir: str,
    root_cause_clf: Any,
    next_edit_clf: Any,
    risk_reg: Any,
    scaler: Any,
    root_cause_calibrator: Any,
    next_edit_calibrator: Any,
    feature_name_map: dict,
    stats: dict,
):
    """Save trained models, calibrators, and metadata."""
    if not ML_AVAILABLE:
        return

    Path(model_dir).mkdir(parents=True, exist_ok=True)

    # Save models and calibrators
    model_data = {
        "root_cause_clf": root_cause_clf,
        "next_edit_clf": next_edit_clf,
        "risk_reg": risk_reg,
        "scaler": scaler,
        "root_cause_calibrator": root_cause_calibrator,
        "next_edit_calibrator": next_edit_calibrator,
    }
    joblib.dump(model_data, Path(model_dir) / "model.joblib")

    # Save feature map
    with open(Path(model_dir) / "feature_map.json", "w") as f:
        json.dump(feature_name_map, f, indent=2)

    # Save training stats
    with open(Path(model_dir) / "training_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    # Extract and save feature importance
    feature_importance = {}
    if hasattr(root_cause_clf, "feature_importances_"):
        importance = root_cause_clf.feature_importances_
        # Get feature names
        feature_names = list(feature_name_map.keys())
        # Sort by importance
        importance_pairs = sorted(
            zip(feature_names, importance, strict=False), key=lambda x: x[1], reverse=True
        )
        feature_importance["root_cause"] = {
            name: float(imp)
            for name, imp in importance_pairs[:20]  # Top 20
        }

    if hasattr(next_edit_clf, "feature_importances_"):
        importance = next_edit_clf.feature_importances_
        feature_names = list(feature_name_map.keys())
        importance_pairs = sorted(
            zip(feature_names, importance, strict=False), key=lambda x: x[1], reverse=True
        )
        feature_importance["next_edit"] = {
            name: float(imp)
            for name, imp in importance_pairs[:20]  # Top 20
        }

    if feature_importance:
        with open(Path(model_dir) / "feature_importance.json", "w") as f:
            json.dump(feature_importance, f, indent=2)


def is_source_file(file_path: str) -> bool:
    """Check if a file is a source code file (not test, config, or docs)."""
    path = Path(file_path)

    # Skip test files and test directories
    if any(part in ["test", "tests", "__tests__", "spec"] for part in path.parts):
        return False
    if (
        path.name.startswith("test_")
        or path.name.endswith("_test.py")
        or ".test." in path.name
        or ".spec." in path.name
    ):
        return False

    # Skip documentation
    if path.suffix.lower() in [".md", ".rst", ".txt", ".yaml", ".yml"]:
        return False

    # Skip configuration files
    config_files = {
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "Makefile",
        "makefile",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        ".env",
        ".env.example",
        "tsconfig.json",
        "jest.config.js",
        "webpack.config.js",
        "babel.config.js",
        ".eslintrc.js",
        ".prettierrc",
        "tox.ini",
        "pytest.ini",
    }
    if path.name.lower() in config_files:
        return False

    # Skip non-source extensions
    non_source_exts = {
        ".json",
        ".xml",
        ".lock",
        ".log",
        ".bak",
        ".tmp",
        ".temp",
        ".cache",
        ".pid",
        ".sock",
    }
    if path.suffix.lower() in non_source_exts and path.name != "manifest.json":
        return False

    # Skip directories that are typically not source
    skip_dirs = {"docs", "documentation", "examples", "samples", "fixtures"}
    if any(part.lower() in skip_dirs for part in path.parts):
        return False

    # Accept common source file extensions
    source_exts = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".cs",
        ".cpp",
        ".cc",
        ".c",
        ".h",
        ".hpp",
        ".rs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".lua",
        ".sh",
        ".bash",
        ".ps1",
        ".sql",
    }

    return path.suffix.lower() in source_exts


def load_models(model_dir: str) -> tuple[Any, Any, Any, Any, Any, Any, dict]:
    """Load trained models and calibrators."""
    if not ML_AVAILABLE:
        return None, None, None, None, None, None, {}

    model_path = Path(model_dir) / "model.joblib"
    if not model_path.exists():
        return None, None, None, None, None, None, {}

    try:
        model_data = joblib.load(model_path)

        with open(Path(model_dir) / "feature_map.json") as f:
            feature_map = json.load(f)

        return (
            model_data["root_cause_clf"],
            model_data["next_edit_clf"],
            model_data["risk_reg"],
            model_data["scaler"],
            model_data.get("root_cause_calibrator"),  # Backward compatibility
            model_data.get("next_edit_calibrator"),  # Backward compatibility
            feature_map,
        )
    except (ImportError, ValueError, AttributeError):
        # ML unavailable - return graceful defaults
        return None, None, None, None, None, None, {}


def learn(
    db_path: str = "./.pf/repo_index.db",
    manifest_path: str = "./.pf/manifest.json",
    journal_path: str = "./.pf/journal.ndjson",
    fce_path: str = "./.pf/fce.json",
    ast_path: str = "./.pf/ast_proofs.json",
    enable_git: bool = False,
    model_dir: str = "./.pf/ml",
    window: int = 50,
    seed: int = 13,
    print_stats: bool = False,
    feedback_path: str = None,
    train_on: str = "full",
) -> dict[str, Any]:
    """Train ML models from artifacts."""
    if not check_ml_available():
        return {"success": False, "error": "ML not available"}

    # Get all files from manifest
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        all_file_paths = [entry["path"] for entry in manifest]

        # Filter to only source files
        file_paths = [fp for fp in all_file_paths if is_source_file(fp)]

        if print_stats:
            excluded_count = len(all_file_paths) - len(file_paths)
            if excluded_count > 0:
                print(f"Excluded {excluded_count} non-source files (tests, docs, configs)")

    except Exception as e:
        return {"success": False, "error": f"Failed to load manifest: {e}"}

    if not file_paths:
        return {"success": False, "error": "No source files found in manifest"}

    # Define history directory
    history_dir = Path("./.pf/history")

    # Load historical data based on train_on parameter
    journal_stats = load_journal_stats(history_dir, window, run_type=train_on)
    rca_stats = load_rca_stats(history_dir, run_type=train_on)
    ast_stats = load_ast_stats(history_dir, run_type=train_on)

    # Build features with loaded stats
    features, feature_name_map = build_feature_matrix(
        file_paths,
        manifest_path,
        db_path,
        journal_stats,
        rca_stats,
        ast_stats,
        enable_git,
    )

    # Build labels with loaded stats
    root_cause_labels, next_edit_labels, risk_labels = build_labels(
        file_paths,
        journal_stats,
        rca_stats,
    )

    # Load human feedback if provided
    sample_weight = None
    if feedback_path and Path(feedback_path).exists():
        try:
            with open(feedback_path) as f:
                feedback_data = json.load(f)

            # Create sample weights array
            sample_weight = np.ones(len(file_paths))

            # Increase weight for files with human feedback
            for i, fp in enumerate(file_paths):
                if fp in feedback_data:
                    # Weight human-reviewed files 5x higher
                    sample_weight[i] = 5.0

                    # Also update labels based on feedback
                    feedback = feedback_data[fp]
                    if "is_risky" in feedback:
                        # Human says file is risky - treat as positive for risk
                        risk_labels[i] = 1.0 if feedback["is_risky"] else 0.0
                    if "is_root_cause" in feedback:
                        # Human says file is root cause
                        root_cause_labels[i] = 1.0 if feedback["is_root_cause"] else 0.0
                    if "will_need_edit" in feedback:
                        # Human says file will need editing
                        next_edit_labels[i] = 1.0 if feedback["will_need_edit"] else 0.0

            if print_stats:
                feedback_count = sum(1 for fp in file_paths if fp in feedback_data)
                print(f"Incorporating human feedback for {feedback_count} files")

        except Exception as e:
            if print_stats:
                print(f"Warning: Could not load feedback file: {e}")

    # Check data size
    n_samples = len(file_paths)
    cold_start = n_samples < 500

    if print_stats:
        print(f"Training on {n_samples} files")
        print(f"Features: {features.shape[1]} dimensions")
        print(f"Root cause positive: {np.sum(root_cause_labels)}/{n_samples}")
        print(f"Next edit positive: {np.sum(next_edit_labels)}/{n_samples}")
        print(f"Mean risk: {np.mean(risk_labels):.3f}")
        if cold_start:
            print("WARNING: Cold-start with <500 samples, expect noisy signals")

    # Train models with optional sample weights from human feedback
    root_cause_clf, next_edit_clf, risk_reg, scaler, root_cause_calibrator, next_edit_calibrator = (
        train_models(
            features,
            root_cause_labels,
            next_edit_labels,
            risk_labels,
            seed,
            sample_weight=sample_weight,
        )
    )

    # Calculate simple metrics
    stats = {
        "n_samples": n_samples,
        "n_features": features.shape[1],
        "root_cause_positive_ratio": float(np.mean(root_cause_labels)),
        "next_edit_positive_ratio": float(np.mean(next_edit_labels)),
        "mean_risk": float(np.mean(risk_labels)),
        "cold_start": cold_start,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Save models with calibrators
    save_models(
        model_dir,
        root_cause_clf,
        next_edit_clf,
        risk_reg,
        scaler,
        root_cause_calibrator,
        next_edit_calibrator,
        feature_name_map,
        stats,
    )

    if print_stats:
        print(f"Models saved to {model_dir}")

    return {
        "success": True,
        "stats": stats,
        "model_dir": model_dir,
        "source_files": len(file_paths),
        "total_files": len(all_file_paths),
        "excluded_count": len(all_file_paths) - len(file_paths),
    }


def suggest(
    db_path: str = "./.pf/repo_index.db",
    manifest_path: str = "./.pf/manifest.json",
    workset_path: str = "./.pf/workset.json",
    fce_path: str = "./.pf/fce.json",
    ast_path: str = "./.pf/ast_proofs.json",
    model_dir: str = "./.pf/ml",
    topk: int = 10,
    out_path: str = "./.pf/insights/ml_suggestions.json",
    print_plan: bool = False,
) -> dict[str, Any]:
    """Generate ML suggestions for workset files."""
    if not check_ml_available():
        return {"success": False, "error": "ML not available"}

    # Load models and calibrators
    (
        root_cause_clf,
        next_edit_clf,
        risk_reg,
        scaler,
        root_cause_calibrator,
        next_edit_calibrator,
        feature_map,
    ) = load_models(model_dir)

    if root_cause_clf is None:
        print(f"No models found in {model_dir}. Run 'aud learn' first.")
        return {"success": False, "error": "Models not found"}

    # Load workset
    try:
        with open(workset_path) as f:
            workset = json.load(f)
        all_file_paths = [p["path"] for p in workset.get("paths", [])]

        # Filter to only source files
        file_paths = [fp for fp in all_file_paths if is_source_file(fp)]

        if print_plan:
            excluded_count = len(all_file_paths) - len(file_paths)
            if excluded_count > 0:
                print(f"Excluded {excluded_count} non-source files from suggestions")

    except Exception as e:
        return {"success": False, "error": f"Failed to load workset: {e}"}

    if not file_paths:
        return {"success": False, "error": "No source files in workset"}

    # Load current FCE and AST stats if available
    current_fce_stats = {}
    if fce_path and Path(fce_path).exists():
        try:
            with open(fce_path) as f:
                data = json.load(f)
            for failure in data.get("failures", []):
                file = failure.get("file", "")
                if file:
                    if file not in current_fce_stats:
                        current_fce_stats[file] = {
                            "fail_count": 0,
                            "categories": [],
                            "messages": [],
                        }
                    current_fce_stats[file]["fail_count"] += 1
                    if "category" in failure:
                        current_fce_stats[file]["categories"].append(failure["category"])
                    if "message" in failure:
                        current_fce_stats[file]["messages"].append(failure["message"][:100])
        except Exception:
            pass

    current_ast_stats = {}
    if ast_path and Path(ast_path).exists():
        try:
            with open(ast_path) as f:
                data = json.load(f)
            for result in data.get("results", []):
                file = result.get("path", "")
                if file:
                    if file not in current_ast_stats:
                        current_ast_stats[file] = {
                            "invariant_fails": 0,
                            "invariant_passes": 0,
                            "failed_checks": [],
                        }
                    for check in result.get("checks", []):
                        if check["status"] == "FAIL":
                            current_ast_stats[file]["invariant_fails"] += 1
                            current_ast_stats[file]["failed_checks"].append(check["id"])
                        elif check["status"] == "PASS":
                            current_ast_stats[file]["invariant_passes"] += 1
        except Exception:
            pass

    # Build features for workset files
    features, _ = build_feature_matrix(
        file_paths,
        manifest_path,
        db_path,
        None,  # No journal for prediction
        current_fce_stats,  # Use current FCE if available
        current_ast_stats,  # Use current AST if available
        False,  # No git for speed
    )

    # Scale features
    features_scaled = scaler.transform(features)

    # Get predictions
    root_cause_scores = root_cause_clf.predict_proba(features_scaled)[:, 1]
    next_edit_scores = next_edit_clf.predict_proba(features_scaled)[:, 1]
    risk_scores = np.clip(risk_reg.predict(features_scaled), 0, 1)

    # Apply calibration if available
    if root_cause_calibrator is not None:
        root_cause_scores = root_cause_calibrator.transform(root_cause_scores)
    if next_edit_calibrator is not None:
        next_edit_scores = next_edit_calibrator.transform(next_edit_scores)

    # Calculate confidence intervals (standard deviation across trees)
    root_cause_std = np.zeros(len(file_paths))
    next_edit_std = np.zeros(len(file_paths))

    if hasattr(root_cause_clf, "estimators_"):
        # Get predictions from all trees
        tree_preds = np.array(
            [tree.predict_proba(features_scaled)[:, 1] for tree in root_cause_clf.estimators_]
        )
        root_cause_std = np.std(tree_preds, axis=0)

    if hasattr(next_edit_clf, "estimators_"):
        tree_preds = np.array(
            [tree.predict_proba(features_scaled)[:, 1] for tree in next_edit_clf.estimators_]
        )
        next_edit_std = np.std(tree_preds, axis=0)

    # Rank files with confidence
    root_cause_ranked = sorted(
        zip(file_paths, root_cause_scores, root_cause_std, strict=False),
        key=lambda x: x[1],
        reverse=True,
    )[:topk]

    next_edit_ranked = sorted(
        zip(file_paths, next_edit_scores, next_edit_std, strict=False),
        key=lambda x: x[1],
        reverse=True,
    )[:topk]

    risk_ranked = sorted(
        zip(file_paths, risk_scores, strict=False),
        key=lambda x: x[1],
        reverse=True,
    )[:topk]

    # Build output with confidence intervals
    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "workset_size": len(file_paths),
        "likely_root_causes": [
            {"path": path, "score": float(score), "confidence_std": float(std)}
            for path, score, std in root_cause_ranked
        ],
        "next_files_to_edit": [
            {"path": path, "score": float(score), "confidence_std": float(std)}
            for path, score, std in next_edit_ranked
        ],
        "risk": [{"path": path, "score": float(score)} for path, score in risk_ranked],
    }

    # Ensure output directory exists
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # Write output atomically
    tmp_path = f"{out_path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(output, f, indent=2, sort_keys=True)
    os.replace(tmp_path, out_path)

    if print_plan:
        print(f"Workset: {len(file_paths)} files")
        print(f"\nTop {min(5, topk)} likely root causes:")
        for item in output["likely_root_causes"][:5]:
            conf_str = (
                f" (±{item['confidence_std']:.3f})" if item.get("confidence_std", 0) > 0 else ""
            )
            print(f"  {item['score']:.3f}{conf_str} - {item['path']}")

        print(f"\nTop {min(5, topk)} next files to edit:")
        for item in output["next_files_to_edit"][:5]:
            conf_str = (
                f" (±{item['confidence_std']:.3f})" if item.get("confidence_std", 0) > 0 else ""
            )
            print(f"  {item['score']:.3f}{conf_str} - {item['path']}")

        print(f"\nTop {min(5, topk)} risk scores:")
        for item in output["risk"][:5]:
            print(f"  {item['score']:.3f} - {item['path']}")

    return {
        "success": True,
        "out_path": out_path,
        "workset_size": len(file_paths),
        "original_size": len(all_file_paths),
        "excluded_count": len(all_file_paths) - len(file_paths),
        "topk": topk,
    }
