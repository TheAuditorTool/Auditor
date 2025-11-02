"""Database feature extraction for ML training.

Extracts 50+ semantic features from repo_index.db tables:
- Security patterns (JWT, SQL, secrets, crypto)
- Vulnerability flows (taint findings, CWE counts)
- Type coverage (TypeScript annotations)
- CFG complexity (control flow graphs)
- Graph topology (imports, exports, centrality)
- Semantic imports (HTTP, DB, Auth, Test libraries)
- AST complexity (functions, classes, calls)
"""

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Optional


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


def load_agent_behavior_features(
    session_dir: Path, db_path: str, file_paths: list[str]
) -> dict[str, dict]:
    """
    Extract AI agent behavior features from Claude Code session logs (Tier 5).

    Cross-references agent actions with repo_index.db ground truth to detect:
    - Blind edits (editing without reading)
    - Duplicate implementations (creating symbols that already exist)
    - Missed context (relevant files not examined)
    - Tool inefficiency (excessive reads/writes)

    Args:
        session_dir: Path to Claude session logs directory
        db_path: Path to repo_index.db for cross-referencing
        file_paths: List of files to analyze

    Returns:
        dict with keys:
        - agent_blind_edit_count: Files edited without prior read
        - agent_duplicate_impl_rate: Rate of duplicate symbol creation
        - agent_missed_search_count: Relevant files not examined
        - agent_read_efficiency: Reads per successful edit (lower = better)
    """
    if not session_dir or not Path(session_dir).exists() or not file_paths:
        return {}

    stats = defaultdict(
        lambda: {
            "agent_blind_edit_count": 0,
            "agent_duplicate_impl_rate": 0.0,
            "agent_missed_search_count": 0,
            "agent_read_efficiency": 0.0,
        }
    )

    try:
        from theauditor.session.analyzer import SessionAnalyzer
        from theauditor.session.parser import SessionParser

        parser = SessionParser()
        analyzer = SessionAnalyzer(db_path=db_path if Path(db_path).exists() else None)

        # Parse all sessions
        sessions = parser.parse_all_sessions(Path(session_dir))

        # Track reads and edits per file for efficiency calculation
        file_reads = defaultdict(int)
        file_edits = defaultdict(int)

        # Get project root for path normalization
        project_root = Path.cwd()

        # Aggregate findings by file
        for session in sessions:
            _, findings = analyzer.analyze_session(session)

            for finding in findings:
                file = finding.evidence.get("file", "")
                if not file:
                    continue

                # Convert to Path object
                file_path_obj = Path(file)

                # If absolute, make it relative to project root
                try:
                    if file_path_obj.is_absolute():
                        file_path_obj = file_path_obj.relative_to(project_root)
                except ValueError:
                    # Path is not under project_root, skip it
                    continue

                # Normalize to forward slashes for comparison
                normalized_file = str(file_path_obj).replace("\\", "/")

                # Only track files in target list
                if normalized_file not in file_paths:
                    continue

                if finding.category == "blind_edit":
                    stats[normalized_file]["agent_blind_edit_count"] += 1
                    file_edits[normalized_file] += 1

                elif finding.category == "duplicate_implementation":
                    # Rate increments by 0.1 per duplicate
                    stats[normalized_file]["agent_duplicate_impl_rate"] += 0.1

                elif finding.category == "missed_existing_code":
                    stats[normalized_file]["agent_missed_search_count"] += 1

                elif finding.category == "duplicate_read":
                    read_count = finding.evidence.get("read_count", 0)
                    file_reads[normalized_file] += read_count

        # Calculate read efficiency (reads per edit)
        for file_path in file_paths:
            reads = file_reads.get(file_path, 0)
            edits = file_edits.get(file_path, 0)
            if edits > 0:
                stats[file_path]["agent_read_efficiency"] = reads / edits
            else:
                stats[file_path]["agent_read_efficiency"] = 0.0

        analyzer.close()
    except ImportError:
        # Session module not available - gracefully skip
        pass
    except Exception:
        # Gracefully skip on error
        pass

    return dict(stats)


def load_all_db_features(
    db_path: str, file_paths: list[str], session_dir: Optional[Path] = None
) -> dict[str, dict]:
    """
    Convenience function to load all database features at once.

    Args:
        db_path: Path to repo_index.db
        file_paths: List of files to analyze
        session_dir: Optional path to Claude session logs (enables Tier 5 features)

    Returns combined dict with all feature categories.
    """
    combined_features = defaultdict(dict)

    # Load all feature categories (Tiers 1-4)
    security = load_security_pattern_features(db_path, file_paths)
    vulnerabilities = load_vulnerability_flow_features(db_path, file_paths)
    types = load_type_coverage_features(db_path, file_paths)
    cfg = load_cfg_complexity_features(db_path, file_paths)
    graph = load_graph_stats(db_path, file_paths)
    semantic = load_semantic_import_features(db_path, file_paths)
    complexity = load_ast_complexity_metrics(db_path, file_paths)

    # Load Tier 5: Agent behavior (if session_dir provided)
    agent_behavior = {}
    if session_dir:
        agent_behavior = load_agent_behavior_features(session_dir, db_path, file_paths)

    # Merge all features per file
    for file_path in file_paths:
        combined_features[file_path].update(security.get(file_path, {}))
        combined_features[file_path].update(vulnerabilities.get(file_path, {}))
        combined_features[file_path].update(types.get(file_path, {}))
        combined_features[file_path].update(cfg.get(file_path, {}))
        combined_features[file_path].update(graph.get(file_path, {}))
        combined_features[file_path].update(semantic.get(file_path, {}))
        combined_features[file_path].update(complexity.get(file_path, {}))
        if agent_behavior:
            combined_features[file_path].update(agent_behavior.get(file_path, {}))

    return dict(combined_features)
