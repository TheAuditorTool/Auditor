"""Slim CLI orchestrator for ML training and inference."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

from . import features, loaders, models


def learn(
    db_path: str = "./.pf/repo_index.db",
    enable_git: bool = False,
    model_dir: str = "./.pf/ml",
    window: int = 50,
    seed: int = 13,
    print_stats: bool = False,
    feedback_path: str = None,
    train_on: str = "full",
    session_dir: str = None,
    graveyard_path: str = None,
) -> dict[str, Any]:
    """Train ML models from artifacts."""
    if not models.check_ml_available():
        return {"success": False, "error": "ML not available"}

    try:
        if not Path(db_path).exists():
            return {"success": False, "error": f"Database not found: {db_path}"}
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM files")
        all_file_paths = [row[0] for row in cursor.fetchall()]
        conn.close()
        file_paths = [fp for fp in all_file_paths if models.is_source_file(fp)]

        if print_stats:
            excluded_count = len(all_file_paths) - len(file_paths)
            if excluded_count > 0:
                logger.info(f"Excluded {excluded_count} non-source files (tests, docs, configs)")

    except Exception as e:
        return {"success": False, "error": f"Failed to load files from database: {e}"}

    if not file_paths:
        return {"success": False, "error": "No source files found in database"}

    history_dir = Path("./.pf/history")
    historical_data = loaders.load_all_historical_data(history_dir, train_on, window, enable_git)

    if enable_git:
        historical_data["git_churn"] = loaders.load_git_churn(
            file_paths=file_paths, window_days=90, root_path=Path(".")
        )

    session_path = Path(session_dir) if session_dir else None
    graveyard_file = Path(graveyard_path) if graveyard_path else None
    db_features = features.load_all_db_features(
        db_path, file_paths, session_dir=session_path, graveyard_path=graveyard_file
    )

    feature_matrix, feature_name_map = models.build_feature_matrix(
        file_paths,
        db_path,
        db_features,
        historical_data,
    )

    root_cause_labels, next_edit_labels, risk_labels = models.build_labels(
        file_paths,
        historical_data["journal_stats"],
        historical_data["rca_stats"],
    )

    sample_weight = None
    if feedback_path and Path(feedback_path).exists():
        try:
            import numpy as np

            with open(feedback_path) as f:
                feedback_data = json.load(f)

            sample_weight = np.ones(len(file_paths))

            for i, fp in enumerate(file_paths):
                if fp in feedback_data:
                    sample_weight[i] = 5.0
                    feedback = feedback_data[fp]
                    if "is_risky" in feedback:
                        risk_labels[i] = 1.0 if feedback["is_risky"] else 0.0
                    if "is_root_cause" in feedback:
                        root_cause_labels[i] = 1.0 if feedback["is_root_cause"] else 0.0
                    if "will_need_edit" in feedback:
                        next_edit_labels[i] = 1.0 if feedback["will_need_edit"] else 0.0

            if print_stats:
                feedback_count = sum(1 for fp in file_paths if fp in feedback_data)
                logger.info(f"Incorporating human feedback for {feedback_count} files")

        except Exception as e:
            if print_stats:
                logger.info(f"Warning: Could not load feedback file: {e}")

    import numpy as np

    n_samples = len(file_paths)
    cold_start = n_samples < 500

    if print_stats:
        logger.info(f"Training on {n_samples} files")
        logger.info(f"Features: {feature_matrix.shape[1]} dimensions")
        logger.info(f"Root cause positive: {np.sum(root_cause_labels)}/{n_samples}")
        logger.info(f"Next edit positive: {np.sum(next_edit_labels)}/{n_samples}")
        logger.info(f"Mean risk: {np.mean(risk_labels):.3f}")
        if cold_start:
            logger.info("WARNING: Cold-start with <500 samples, expect noisy signals")

    root_cause_clf, next_edit_clf, risk_reg, scaler, root_cause_calibrator, next_edit_calibrator = (
        models.train_models(
            feature_matrix,
            root_cause_labels,
            next_edit_labels,
            risk_labels,
            seed,
            sample_weight=sample_weight,
        )
    )

    stats = {
        "n_samples": n_samples,
        "n_features": feature_matrix.shape[1],
        "root_cause_positive_ratio": float(np.mean(root_cause_labels)),
        "next_edit_positive_ratio": float(np.mean(next_edit_labels)),
        "mean_risk": float(np.mean(risk_labels)),
        "cold_start": cold_start,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    models.save_models(
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
        logger.info(f"Models saved to {model_dir}")

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
    workset_path: str = "./.pf/workset.json",
    model_dir: str = "./.pf/ml",
    topk: int = 10,
    out_path: str = "./.pf/insights/ml_suggestions.json",
    print_plan: bool = False,
) -> dict[str, Any]:
    """Generate ML suggestions for workset files."""
    if not models.check_ml_available():
        return {"success": False, "error": "ML not available"}

    (
        root_cause_clf,
        next_edit_clf,
        risk_reg,
        scaler,
        root_cause_calibrator,
        next_edit_calibrator,
        _feature_map,
    ) = models.load_models(model_dir)

    if root_cause_clf is None:
        logger.info(f"No models found in {model_dir}. Run 'aud learn' first.")
        return {"success": False, "error": "Models not found. Run 'aud learn' first."}

    workset_file = Path(workset_path)
    if not workset_file.exists():
        return {
            "success": False,
            "error": f"Workset not found at {workset_path}. Run 'aud workset --all' or 'aud workset --diff HEAD~1' first to create it.",
        }

    try:
        with open(workset_path) as f:
            workset = json.load(f)
        all_file_paths = [p["path"] for p in workset.get("paths", [])]
        file_paths = [fp for fp in all_file_paths if models.is_source_file(fp)]

        if print_plan:
            excluded_count = len(all_file_paths) - len(file_paths)
            if excluded_count > 0:
                logger.info(f"Excluded {excluded_count} non-source files from suggestions")

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid workset JSON: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to load workset: {e}"}

    if not file_paths:
        return {"success": False, "error": "No source files in workset"}

    db_features = features.load_all_db_features(db_path, file_paths)

    feature_matrix, _ = models.build_feature_matrix(
        file_paths,
        db_path,
        db_features,
        {
            "journal_stats": {},
            "rca_stats": {},
            "ast_stats": {},
            "git_churn": {},
        },
    )

    import numpy as np

    expected_features = scaler.n_features_in_
    actual_features = feature_matrix.shape[1]
    if expected_features != actual_features:
        logger.error(
            f"Feature count mismatch: model expects {expected_features} features, "
            f"but current code generates {actual_features}. "
            f"Run 'aud learn' to retrain models with current feature set."
        )
        return {
            "success": False,
            "error": f"Model incompatible: trained with {expected_features} features, "
            f"current code generates {actual_features}. Run 'aud learn' to retrain.",
        }

    features_scaled = scaler.transform(feature_matrix)

    root_cause_scores = root_cause_clf.predict_proba(feature_matrix)[:, 1]
    next_edit_scores = next_edit_clf.predict_proba(feature_matrix)[:, 1]

    risk_scores = np.clip(risk_reg.predict(features_scaled), 0, 1)

    if root_cause_calibrator is not None:
        root_cause_scores = root_cause_calibrator.transform(root_cause_scores)
    if next_edit_calibrator is not None:
        next_edit_scores = next_edit_calibrator.transform(next_edit_scores)

    root_cause_std = np.zeros(len(file_paths))
    next_edit_std = np.zeros(len(file_paths))

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

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    import os

    tmp_path = f"{out_path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(output, f, indent=2, sort_keys=True)
    os.replace(tmp_path, out_path)

    if print_plan:
        logger.info(f"Workset: {len(file_paths)} files")
        logger.info(f"\nTop {min(5, topk)} likely root causes:")
        for item in output["likely_root_causes"][:5]:
            conf_str = (
                f" (±{item['confidence_std']:.3f})" if item.get("confidence_std", 0) > 0 else ""
            )
            logger.info(f"  {item['score']:.3f}{conf_str} - {item['path']}")

    return {
        "success": True,
        "out_path": out_path,
        "workset_size": len(file_paths),
        "original_size": len(all_file_paths),
        "excluded_count": len(all_file_paths) - len(file_paths),
        "topk": topk,
    }
