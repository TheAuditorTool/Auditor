"""Database feature extraction for ML training.

2025 Edition: Integrates blast radius from impact_analyzer into ML features.
"""

import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np

from theauditor.utils.logging import logger

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


def load_security_pattern_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """Extract security pattern features from jwt_patterns and sql_queries tables."""
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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(file_paths))

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

    return dict(stats)


def load_vulnerability_flow_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """Extract taint flow features from findings_consolidated table."""
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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(file_paths))

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

    return dict(stats)


def load_type_coverage_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """Extract TypeScript type annotation coverage from type_annotations table."""
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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(file_paths))

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

        typed = total - any_count - unknown_count
        stats[file_path]["type_coverage_ratio"] = typed / total if total > 0 else 0.0

    conn.close()

    return dict(stats)


def load_cfg_complexity_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """Extract control flow complexity from cfg_blocks and cfg_edges tables."""
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "cfg_block_count": 0,
            "cfg_edge_count": 0,
            "cyclomatic_complexity": 0,
        }
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(file_paths))

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

        blocks = stats[file_path]["cfg_block_count"]
        stats[file_path]["cyclomatic_complexity"] = edge_count - blocks + 2

    conn.close()

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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(file_paths))

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

    return dict(stats)


def load_semantic_import_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """Extract semantic import features to understand file purpose."""
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "has_http_import": False,
            "has_db_import": False,
            "has_auth_import": False,
            "has_test_import": False,
        }
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(file_paths))

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
        import_name = import_value.lower().strip("\"'")

        if "/" in import_name:
            import_name = import_name.split("/")[0].lstrip("@")

        base_import = import_name.split(".")[0]

        if any(lib in import_name or base_import == lib for lib in HTTP_LIBS):
            stats[file_path]["has_http_import"] = True

        if any(lib in import_name or base_import == lib for lib in DB_LIBS):
            stats[file_path]["has_db_import"] = True

        if any(lib in import_name or base_import == lib for lib in AUTH_LIBS):
            stats[file_path]["has_auth_import"] = True

        if any(lib in import_name or base_import == lib for lib in TEST_LIBS):
            stats[file_path]["has_test_import"] = True

    conn.close()

    return dict(stats)


def load_ast_complexity_metrics(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """Extract AST-based complexity metrics from the symbols table."""
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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(file_paths))

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

    return dict(stats)


def load_comment_hallucination_features(
    session_dir: Path, graveyard_path: Path, file_paths: list[str]
) -> dict[str, dict]:
    """Extract comment hallucination features from Claude Code session logs."""
    import json
    from collections import defaultdict

    stats = defaultdict(
        lambda: {
            "comment_reference_count": 0,
            "comment_hallucination_count": 0,
            "comment_conflict_rate": 0.0,
            "has_removed_comments": False,
        }
    )

    if not file_paths:
        return dict(stats)

    graveyard_files = set()
    if graveyard_path and Path(graveyard_path).exists():
        try:
            with open(graveyard_path, encoding="utf-8") as f:
                graveyard = json.load(f)
            for entry in graveyard:
                file_path = entry.get("file", "")
                if file_path:
                    normalized = file_path.replace("\\", "/")
                    graveyard_files.add(normalized)
        except json.JSONDecodeError as e:
            logger.debug(f"Corrupt graveyard JSON: {e}")
        except OSError as e:
            logger.debug(f"Could not read graveyard file: {e}")

    for file_path in file_paths:
        normalized = file_path.replace("\\", "/")
        if normalized in graveyard_files:
            stats[file_path]["has_removed_comments"] = True

    if not session_dir or not Path(session_dir).exists():
        return dict(stats)

    try:
        from theauditor.session.analysis import SessionAnalysis
        from theauditor.session.parser import SessionParser

        parser = SessionParser()
        analyzer = SessionAnalysis(db_path=None)

        sessions = parser.parse_all_sessions(Path(session_dir))

        project_root = Path.cwd()

        for session in sessions:
            _, findings = analyzer.analyze_session_with_findings(session, graveyard_path)

            for finding in findings:
                if finding.category != "comment_hallucination":
                    continue

                mentioned_files = finding.evidence.get("mentioned_files", [])

                for file in mentioned_files:
                    try:
                        file_path_obj = Path(file)
                        if file_path_obj.is_absolute():
                            file_path_obj = file_path_obj.relative_to(project_root)
                        normalized_file = str(file_path_obj).replace("\\", "/")
                    except ValueError:
                        normalized_file = file.replace("\\", "/")

                    if normalized_file not in file_paths:
                        continue

                    stats[normalized_file]["comment_reference_count"] += 1

                    if finding.severity == "warning":
                        stats[normalized_file]["comment_hallucination_count"] += 1

        for file_path in file_paths:
            ref_count = stats[file_path]["comment_reference_count"]
            hall_count = stats[file_path]["comment_hallucination_count"]
            if ref_count > 0:
                stats[file_path]["comment_conflict_rate"] = hall_count / ref_count

        analyzer.close()
    except ImportError:
        pass

    return dict(stats)


def load_agent_behavior_features(
    session_dir: Path, db_path: str, file_paths: list[str]
) -> dict[str, dict]:
    """Extract AI agent behavior features from Claude Code session logs (Tier 5)."""
    if not session_dir or not Path(session_dir).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "agent_blind_edit_count": 0,
            "agent_duplicate_impl_rate": 0.0,
            "agent_missed_search_count": 0,
            "agent_read_efficiency": 0.0,
            "agent_partial_batch_read_count": 0,
        }
    )

    try:
        from theauditor.session.analysis import SessionAnalysis
        from theauditor.session.parser import SessionParser

        parser = SessionParser()
        analyzer = SessionAnalysis(db_path=Path(db_path) if Path(db_path).exists() else None)

        sessions = parser.parse_all_sessions(Path(session_dir))

        file_reads = defaultdict(int)
        file_edits = defaultdict(int)

        project_root = Path.cwd()

        for session in sessions:
            _, findings = analyzer.analyze_session_with_findings(session)

            for finding in findings:
                # Handle partial_batch_read which has failed_files list instead of file
                if finding.category == "partial_batch_read":
                    failed_files = finding.evidence.get("failed_files", [])
                    for ff in failed_files:
                        try:
                            ff_path = Path(ff)
                            if ff_path.is_absolute():
                                ff_path = ff_path.relative_to(project_root)
                            normalized = str(ff_path).replace("\\", "/")
                            if normalized in file_paths:
                                stats[normalized]["agent_partial_batch_read_count"] += 1
                        except ValueError:
                            continue
                    continue

                file = finding.evidence.get("file", "")
                if not file:
                    continue

                file_path_obj = Path(file)

                try:
                    if file_path_obj.is_absolute():
                        file_path_obj = file_path_obj.relative_to(project_root)
                except ValueError:
                    continue

                normalized_file = str(file_path_obj).replace("\\", "/")

                if normalized_file not in file_paths:
                    continue

                if finding.category == "blind_edit":
                    stats[normalized_file]["agent_blind_edit_count"] += 1
                    file_edits[normalized_file] += 1

                elif finding.category == "duplicate_implementation":
                    stats[normalized_file]["agent_duplicate_impl_rate"] += 0.1

                elif finding.category == "missed_existing_code":
                    stats[normalized_file]["agent_missed_search_count"] += 1

                elif finding.category == "duplicate_read":
                    read_count = finding.evidence.get("read_count", 0)
                    file_reads[normalized_file] += read_count

        for file_path in file_paths:
            reads = file_reads.get(file_path, 0)
            edits = file_edits.get(file_path, 0)
            if edits > 0:
                stats[file_path]["agent_read_efficiency"] = reads / edits
            else:
                stats[file_path]["agent_read_efficiency"] = 0.0

        analyzer.close()
    except ImportError:
        pass

    return dict(stats)


def load_session_execution_features(
    db_path: str = None, file_paths: list[str] = None
) -> dict[str, dict]:
    """Extract Tier 5 features from session_executions table (new 3-layer system)."""
    import json
    import sqlite3

    stats = defaultdict(
        lambda: {
            "session_workflow_compliance": 0.0,
            "session_avg_risk_score": 0.0,
            "session_blind_edit_rate": 0.0,
            "session_user_engagement": 0.0,
        }
    )

    if db_path is None:
        db_path = str(Path(".pf/ml/session_history.db"))

    if not file_paths:
        return dict(stats)

    if not Path(db_path).exists():
        return dict(stats)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    project_root = Path.cwd()

    for file_path in file_paths:
        normalized_path = str(Path(file_path).as_posix())

        cursor.execute(
            """
            SELECT workflow_compliant, compliance_score, risk_score,
                   user_engagement_rate, diffs_scored
            FROM session_executions
            WHERE diffs_scored LIKE ?
        """,
            (f"%{normalized_path}%",),
        )

        rows = cursor.fetchall()

        if not rows:
            continue

        compliance_scores = [row[1] for row in rows]
        risk_scores = [row[2] for row in rows]
        engagement_rates = [row[3] for row in rows]

        blind_edits = 0
        total_edits = 0

        for row in rows:
            diffs_json = row[4]
            if not diffs_json:
                continue

            try:
                diffs = json.loads(diffs_json)
                for diff in diffs:
                    diff_file = diff.get("file", "")
                    if not diff_file:
                        continue

                    try:
                        diff_path_obj = Path(diff_file)
                        if diff_path_obj.is_absolute():
                            diff_path_obj = diff_path_obj.relative_to(project_root)
                        normalized_diff = str(diff_path_obj.as_posix())
                    except ValueError:
                        normalized_diff = str(Path(diff_file).as_posix())

                    if normalized_diff == normalized_path:
                        total_edits += 1
                        if diff.get("blind_edit", False):
                            blind_edits += 1
            except json.JSONDecodeError:
                continue

        stats[file_path]["session_workflow_compliance"] = (
            sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0.0
        )
        stats[file_path]["session_avg_risk_score"] = (
            sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
        )
        stats[file_path]["session_blind_edit_rate"] = (
            blind_edits / total_edits if total_edits > 0 else 0.0
        )
        stats[file_path]["session_user_engagement"] = (
            sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
        )

    conn.close()

    return dict(stats)


def load_impact_features(db_path: str, file_paths: list[str]) -> dict[str, dict]:
    """Extract blast radius features by integrating impact_analyzer.

    This is the 2025 "feature fusion" - the ML model now knows about
    the theoretical maximum impact if each file were touched.

    Returns raw counts without formatting (headless mode for ML).

    OPTIMIZED: Uses batch queries instead of N+1 pattern.
    Before: O(N * M) queries where N=files, M=avg dependency depth
    After: O(1) batch queries regardless of file count
    """
    if not Path(db_path).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "blast_radius": 0.0,
            "coupling_score": 0.0,
            "direct_upstream": 0,
            "direct_downstream": 0,
            "transitive_impact": 0,
            "affected_files": 0,
            "is_api_endpoint": False,
            "prod_dependency_count": 0,
        }
    )

    try:
        from . import impact_analyzer
    except ImportError:
        logger.debug("impact_analyzer not available for feature extraction")
        return dict(stats)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(file_paths))
        cursor.execute(
            f"SELECT DISTINCT file FROM api_endpoints WHERE file IN ({placeholders})",
            file_paths,
        )
        api_files = {row[0] for row in cursor.fetchall()}

        for fp in file_paths:
            if fp in api_files:
                stats[fp]["is_api_endpoint"] = True

        cursor.execute(
            f"""
            SELECT path, name, type, line
            FROM symbols
            WHERE path IN ({placeholders})
            AND type IN ('function', 'class')
            ORDER BY path, line
        """,
            file_paths,
        )

        file_symbols: dict[str, tuple[str, str, int]] = {}
        for path, name, sym_type, line in cursor.fetchall():
            if path not in file_symbols:
                file_symbols[path] = (name, sym_type, line)

        if not file_symbols:
            return dict(stats)

        upstream_symbols = [
            (fp, name, sym_type) for fp, (name, sym_type, _) in file_symbols.items()
        ]
        downstream_symbols = [(fp, line, name) for fp, (name, _, line) in file_symbols.items()]

        upstream_results = impact_analyzer.find_upstream_dependencies_batch(
            cursor, upstream_symbols
        )

        downstream_results = impact_analyzer.find_downstream_dependencies_batch(
            cursor, downstream_symbols
        )

        for fp in file_paths:
            if fp not in file_symbols:
                continue

            name, sym_type, line = file_symbols[fp]

            upstream = upstream_results.get(name, [])

            downstream_key = f"{fp}:{name}"
            downstream = downstream_results.get(downstream_key, [])

            downstream_transitive = impact_analyzer.calculate_transitive_impact(
                cursor, downstream, "downstream", max_depth=2
            )

            all_impacts = upstream + downstream + downstream_transitive
            risk_data = impact_analyzer.classify_risk(all_impacts)

            stats[fp]["direct_upstream"] = len(upstream)
            stats[fp]["direct_downstream"] = len(downstream)
            stats[fp]["transitive_impact"] = len(downstream_transitive)

            total_impact = len(upstream) + len(downstream) + len(downstream_transitive)
            affected_files = len(
                {item["file"] for item in all_impacts if item.get("file") != "external"}
            )

            stats[fp]["affected_files"] = affected_files

            stats[fp]["blast_radius"] = float(np.log1p(total_impact))

            stats[fp]["coupling_score"] = min(total_impact / 50.0, 1.0)

            stats[fp]["prod_dependency_count"] = risk_data["metrics"]["prod_count"]

    return dict(stats)


def load_all_db_features(
    db_path: str,
    file_paths: list[str],
    session_dir: Path | None = None,
    graveyard_path: Path | None = None,
) -> dict[str, dict]:
    """Convenience function to load all database features at once."""
    combined_features = defaultdict(dict)

    security = load_security_pattern_features(db_path, file_paths)
    vulnerabilities = load_vulnerability_flow_features(db_path, file_paths)
    types = load_type_coverage_features(db_path, file_paths)
    cfg = load_cfg_complexity_features(db_path, file_paths)
    graph = load_graph_stats(db_path, file_paths)
    semantic = load_semantic_import_features(db_path, file_paths)
    complexity = load_ast_complexity_metrics(db_path, file_paths)

    impact_features = load_impact_features(db_path, file_paths)

    session_execution_features = load_session_execution_features(None, file_paths)

    agent_behavior = {}
    if session_dir:
        agent_behavior = load_agent_behavior_features(session_dir, db_path, file_paths)

    comment_hallucination = {}
    if session_dir:
        if graveyard_path is None:
            graveyard_path = Path("comment_graveyard.json")
        comment_hallucination = load_comment_hallucination_features(
            session_dir, graveyard_path, file_paths
        )

    for file_path in file_paths:
        combined_features[file_path].update(security.get(file_path, {}))
        combined_features[file_path].update(vulnerabilities.get(file_path, {}))
        combined_features[file_path].update(types.get(file_path, {}))
        combined_features[file_path].update(cfg.get(file_path, {}))
        combined_features[file_path].update(graph.get(file_path, {}))
        combined_features[file_path].update(semantic.get(file_path, {}))
        combined_features[file_path].update(complexity.get(file_path, {}))

        combined_features[file_path].update(impact_features.get(file_path, {}))

        combined_features[file_path].update(session_execution_features.get(file_path, {}))

        if agent_behavior:
            combined_features[file_path].update(agent_behavior.get(file_path, {}))

        if comment_hallucination:
            combined_features[file_path].update(comment_hallucination.get(file_path, {}))

    return dict(combined_features)
