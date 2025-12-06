"""Model training, evaluation, and persistence.

2025 Edition: Uses sklearn Pipeline with HistGradientBoostingClassifier.
- Pipeline bundles scaler + classifier so they travel together
- HistGradientBoostingClassifier is faster and handles NaNs natively
- Probability calibration for reliable risk scores
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from theauditor.utils.logging import logger

if TYPE_CHECKING:
    import numpy as np


ML_AVAILABLE = False
try:
    import joblib
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    ML_AVAILABLE = True
except ImportError:
    pass


FNV_PRIME = 0x01000193
FNV_OFFSET = 0x811C9DC5

_SCHEMA_VALIDATED = False


def validate_ml_schema():
    """Validate ML queries against schema contract."""
    global _SCHEMA_VALIDATED
    if _SCHEMA_VALIDATED:
        return

    try:
        from theauditor.indexer.schema import get_table_schema

        refs_schema = get_table_schema("refs")
        refs_cols = set(refs_schema.column_names())
        assert "src" in refs_cols, "refs table missing 'src' column"
        assert "value" in refs_cols, "refs table missing 'value' column"
        assert "kind" in refs_cols, "refs table missing 'kind' column"

        symbols_schema = get_table_schema("symbols")
        symbols_cols = set(symbols_schema.column_names())
        assert "path" in symbols_cols, "symbols table missing 'path' column"
        assert "type" in symbols_cols, "symbols table missing 'type' column"
        assert "name" in symbols_cols, "symbols table missing 'name' column"

        api_endpoints_schema = get_table_schema("api_endpoints")
        api_cols = set(api_endpoints_schema.column_names())
        assert "file" in api_cols, "api_endpoints table missing 'file' column"

        sql_objects_schema = get_table_schema("sql_objects")
        sql_cols = set(sql_objects_schema.column_names())
        assert "file" in sql_cols, "sql_objects table missing 'file' column"

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
        raise RuntimeError("Schema validation failed: theauditor.indexer.schema not available") from None


def check_ml_available():
    """Check if ML dependencies are available."""
    if not ML_AVAILABLE:
        logger.info("ERROR: ML dependencies missing (sklearn, numpy, scipy, joblib)")
        logger.info("These are now installed by default. Reinstall: pip install -e .")
        return False

    validate_ml_schema()
    return True


def fowler_noll_hash(text: str, dim: int = 2000) -> int:
    """Simple FNV-1a hash for text feature hashing."""
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

    parts = Path(path).parts
    for part in parts:
        idx = fowler_noll_hash(part, dim)
        features[idx] += 1.0

    basename = Path(path).name
    idx = fowler_noll_hash(basename, dim)
    features[idx] += 2.0

    if rca_messages:
        for msg in rca_messages[:5]:
            tokens = msg.lower().split()[:10]
            for token in tokens:
                idx = fowler_noll_hash(token, dim)
                features[idx] += 0.5

    return dict(features)


def build_feature_matrix(
    file_paths: list[str],
    db_path: str,
    db_features: dict,
    historical_data: dict,
    intelligent_features: dict = None,
) -> tuple[np.ndarray, dict[str, int]]:
    """Build feature matrix for files.

    OPTIMIZED: Pre-allocates numpy array to avoid Python list resizing overhead.
    """
    if not ML_AVAILABLE:
        return None, {}

    import sqlite3
    from pathlib import Path

    file_metadata = {}
    if Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT path, ext, bytes, loc FROM files")
        for row in cursor.fetchall():
            file_metadata[row[0]] = {"path": row[0], "ext": row[1], "bytes": row[2], "loc": row[3]}
        conn.close()

    journal_stats = historical_data.get("journal_stats", {})
    rca_stats = historical_data.get("rca_stats", {})
    ast_stats = historical_data.get("ast_stats", {})
    git_churn = historical_data.get("git_churn", {})

    intelligent_features = intelligent_features or {}

    n_files = len(file_paths)
    n_features = 109
    features = np.zeros((n_files, n_features), dtype=np.float32)

    for i, file_path in enumerate(file_paths):
        col = 0

        meta = file_metadata.get(file_path, {})
        features[i, col] = meta.get("bytes", 0) / 10000.0
        col += 1
        features[i, col] = meta.get("loc", 0) / 100.0
        col += 1

        ext = meta.get("ext", "")
        features[i, col] = 1.0 if ext in [".ts", ".tsx", ".js", ".jsx"] else 0.0
        col += 1
        features[i, col] = 1.0 if ext == ".py" else 0.0
        col += 1

        db_feat = db_features.get(file_path, {})

        features[i, col] = db_feat.get("in_degree", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("out_degree", 0) / 10.0
        col += 1
        features[i, col] = 1.0 if db_feat.get("has_routes") else 0.0
        col += 1
        features[i, col] = 1.0 if db_feat.get("has_sql") else 0.0
        col += 1

        journal = journal_stats.get(file_path, {})
        features[i, col] = journal.get("touches", 0) / 10.0
        col += 1
        features[i, col] = journal.get("failures", 0) / 5.0
        col += 1
        features[i, col] = journal.get("successes", 0) / 5.0
        col += 1

        rca = rca_stats.get(file_path, {})
        features[i, col] = rca.get("fail_count", 0) / 5.0
        col += 1

        ast = ast_stats.get(file_path, {})
        features[i, col] = ast.get("invariant_fails", 0) / 3.0
        col += 1
        features[i, col] = ast.get("invariant_passes", 0) / 3.0
        col += 1

        git = git_churn.get(file_path, {})
        features[i, col] = git.get("commits_90d", 0) / 20.0
        col += 1
        features[i, col] = git.get("unique_authors", 0) / 5.0
        col += 1
        features[i, col] = git.get("days_since_modified", 999) / 100.0
        col += 1
        features[i, col] = git.get("days_active_in_range", 0) / 30.0
        col += 1

        features[i, col] = 1.0 if db_feat.get("has_http_import") else 0.0
        col += 1
        features[i, col] = 1.0 if db_feat.get("has_db_import") else 0.0
        col += 1
        features[i, col] = 1.0 if db_feat.get("has_auth_import") else 0.0
        col += 1
        features[i, col] = 1.0 if db_feat.get("has_test_import") else 0.0
        col += 1

        features[i, col] = db_feat.get("function_count", 0) / 20.0
        col += 1
        features[i, col] = db_feat.get("class_count", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("call_count", 0) / 50.0
        col += 1
        features[i, col] = db_feat.get("try_except_count", 0) / 5.0
        col += 1
        features[i, col] = db_feat.get("async_def_count", 0) / 5.0
        col += 1

        features[i, col] = db_feat.get("jwt_usage_count", 0) / 5.0
        col += 1
        features[i, col] = db_feat.get("sql_query_count", 0) / 10.0
        col += 1
        features[i, col] = 1.0 if db_feat.get("has_hardcoded_secret") else 0.0
        col += 1
        features[i, col] = 1.0 if db_feat.get("has_weak_crypto") else 0.0
        col += 1

        features[i, col] = db_feat.get("critical_findings", 0) / 3.0
        col += 1
        features[i, col] = db_feat.get("high_findings", 0) / 5.0
        col += 1
        features[i, col] = db_feat.get("medium_findings", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("unique_cwe_count", 0) / 5.0
        col += 1

        features[i, col] = db_feat.get("type_annotation_count", 0) / 50.0
        col += 1
        features[i, col] = db_feat.get("any_type_count", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("unknown_type_count", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("generic_type_count", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("type_coverage_ratio", 0.0)
        col += 1

        features[i, col] = db_feat.get("cfg_block_count", 0) / 20.0
        col += 1
        features[i, col] = db_feat.get("cfg_edge_count", 0) / 30.0
        col += 1
        features[i, col] = db_feat.get("cyclomatic_complexity", 0) / 10.0
        col += 1

        features[i, col] = db_feat.get("blast_radius", 0.0)
        col += 1
        features[i, col] = db_feat.get("coupling_score", 0.0)
        col += 1
        features[i, col] = db_feat.get("direct_upstream", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("direct_downstream", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("transitive_impact", 0) / 20.0
        col += 1
        features[i, col] = db_feat.get("affected_files", 0) / 10.0
        col += 1
        features[i, col] = 1.0 if db_feat.get("is_api_endpoint") else 0.0
        col += 1
        features[i, col] = db_feat.get("prod_dependency_count", 0) / 10.0
        col += 1

        features[i, col] = db_feat.get("agent_blind_edit_count", 0) / 5.0
        col += 1
        features[i, col] = db_feat.get("agent_duplicate_impl_rate", 0.0)
        col += 1
        features[i, col] = db_feat.get("agent_missed_search_count", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("agent_read_efficiency", 0.0) / 5.0
        col += 1

        features[i, col] = db_feat.get("comment_reference_count", 0) / 10.0
        col += 1
        features[i, col] = db_feat.get("comment_hallucination_count", 0) / 5.0
        col += 1
        features[i, col] = db_feat.get("comment_conflict_rate", 0.0)
        col += 1
        features[i, col] = 1.0 if db_feat.get("has_removed_comments") else 0.0
        col += 1

        text_feats = extract_text_features(
            file_path,
            rca.get("messages", []),
            dim=50,
        )
        for idx, val in text_feats.items():
            if idx < 50:
                features[i, col + idx] = val

    feature_names = [
        "bytes_norm",
        "loc_norm",
        "is_js",
        "is_py",
        "in_degree",
        "out_degree",
        "has_routes",
        "has_sql",
        "touches",
        "failures",
        "successes",
        "rca_fails",
        "ast_fails",
        "ast_passes",
        "git_commits_90d",
        "git_unique_authors",
        "git_days_since_modified",
        "git_days_active_in_range",
        "has_http_import",
        "has_db_import",
        "has_auth_import",
        "has_test_import",
        "function_count",
        "class_count",
        "call_count",
        "try_except_count",
        "async_def_count",
        "jwt_usage_count",
        "sql_query_count",
        "has_hardcoded_secret",
        "has_weak_crypto",
        "critical_findings",
        "high_findings",
        "medium_findings",
        "unique_cwe_count",
        "type_annotation_count",
        "any_type_count",
        "unknown_type_count",
        "generic_type_count",
        "type_coverage_ratio",
        "cfg_block_count",
        "cfg_edge_count",
        "cyclomatic_complexity",
        "blast_radius",
        "coupling_score",
        "direct_upstream",
        "direct_downstream",
        "transitive_impact",
        "affected_files",
        "is_api_endpoint",
        "prod_dependency_count",
        "agent_blind_edit_count",
        "agent_duplicate_impl_rate",
        "agent_missed_search_count",
        "agent_read_efficiency",
        "comment_reference_count",
        "comment_hallucination_count",
        "comment_conflict_rate",
        "has_removed_comments",
    ] + [f"text_{i}" for i in range(50)]

    feature_name_map = {name: i for i, name in enumerate(feature_names)}

    return features, feature_name_map


def build_labels(
    file_paths: list[str],
    journal_stats: dict,
    rca_stats: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build label vectors for training."""
    if not ML_AVAILABLE:
        return None, None, None

    root_cause_labels = np.array(
        [1.0 if rca_stats.get(fp, {}).get("fail_count", 0) > 0 else 0.0 for fp in file_paths]
    )

    next_edit_labels = np.array(
        [1.0 if journal_stats.get(fp, {}).get("touches", 0) > 0 else 0.0 for fp in file_paths]
    )

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
    features: np.ndarray,
    root_cause_labels: np.ndarray,
    next_edit_labels: np.ndarray,
    risk_labels: np.ndarray,
    seed: int = 13,
    sample_weight: np.ndarray = None,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Train the three models with optional sample weighting for human feedback.

    2025 Edition:
    - Uses HistGradientBoostingClassifier (faster, handles NaNs natively)
    - Wraps in Pipeline for portable train/predict (scaler travels with model)
    - Probability calibration for reliable risk scores
    """
    if not ML_AVAILABLE:
        return None, None, None, None, None, None

    if len(np.unique(root_cause_labels)) < 2:
        root_cause_labels[0] = 1 - root_cause_labels[0]
    if len(np.unique(next_edit_labels)) < 2:
        next_edit_labels[0] = 1 - next_edit_labels[0]

    root_cause_pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                HistGradientBoostingClassifier(
                    learning_rate=0.1,
                    max_iter=100,
                    max_depth=5,
                    random_state=seed,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    next_edit_pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                HistGradientBoostingClassifier(
                    learning_rate=0.1,
                    max_iter=100,
                    max_depth=5,
                    random_state=seed,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    root_cause_pipeline.fit(features, root_cause_labels)
    next_edit_pipeline.fit(features, next_edit_labels)

    risk_reg = Ridge(alpha=1.0, random_state=seed)
    risk_reg.fit(features_scaled, risk_labels, sample_weight=sample_weight)

    root_cause_calibrator = IsotonicRegression(out_of_bounds="clip")
    root_cause_probs = root_cause_pipeline.predict_proba(features)[:, 1]
    root_cause_calibrator.fit(root_cause_probs, root_cause_labels)

    next_edit_calibrator = IsotonicRegression(out_of_bounds="clip")
    next_edit_probs = next_edit_pipeline.predict_proba(features)[:, 1]
    next_edit_calibrator.fit(next_edit_probs, next_edit_labels)

    return (
        root_cause_pipeline,
        next_edit_pipeline,
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

    model_data = {
        "root_cause_clf": root_cause_clf,
        "next_edit_clf": next_edit_clf,
        "risk_reg": risk_reg,
        "scaler": scaler,
        "root_cause_calibrator": root_cause_calibrator,
        "next_edit_calibrator": next_edit_calibrator,
    }
    joblib.dump(model_data, Path(model_dir) / "model.joblib")

    with open(Path(model_dir) / "feature_map.json", "w") as f:
        json.dump(feature_name_map, f, indent=2)

    with open(Path(model_dir) / "training_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    feature_importance = {}
    if hasattr(root_cause_clf, "feature_importances_"):
        importance = root_cause_clf.feature_importances_
        feature_names = list(feature_name_map.keys())
        importance_pairs = sorted(
            zip(feature_names, importance, strict=False), key=lambda x: x[1], reverse=True
        )
        feature_importance["root_cause"] = {name: float(imp) for name, imp in importance_pairs[:20]}

    if hasattr(next_edit_clf, "feature_importances_"):
        importance = next_edit_clf.feature_importances_
        feature_names = list(feature_name_map.keys())
        importance_pairs = sorted(
            zip(feature_names, importance, strict=False), key=lambda x: x[1], reverse=True
        )
        feature_importance["next_edit"] = {name: float(imp) for name, imp in importance_pairs[:20]}

    if feature_importance:
        with open(Path(model_dir) / "feature_importance.json", "w") as f:
            json.dump(feature_importance, f, indent=2)


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
            model_data.get("root_cause_calibrator"),
            model_data.get("next_edit_calibrator"),
            feature_map,
        )
    except (ImportError, ValueError, AttributeError):
        return None, None, None, None, None, None, {}


def is_source_file(file_path: str) -> bool:
    """Check if a file is a source code file (not test, config, or docs)."""
    path = Path(file_path)

    if any(part in ["test", "tests", "__tests__", "spec"] for part in path.parts):
        return False
    if (
        path.name.startswith("test_")
        or path.name.endswith("_test.py")
        or ".test." in path.name
        or ".spec." in path.name
    ):
        return False

    if path.suffix.lower() in [".md", ".rst", ".txt", ".yaml", ".yml"]:
        return False

    config_files = {
        ".gitignore",
        "pyproject.toml",
        "package.json",
        "requirements.txt",
        "Dockerfile",
        ".env",
        "tsconfig.json",
        "jest.config.js",
    }
    if path.name.lower() in config_files:
        return False

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
    }

    return path.suffix.lower() in source_exts
