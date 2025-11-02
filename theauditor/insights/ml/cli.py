"""Slim CLI orchestrator for ML training and inference.

Delegates to specialized modules:
- loaders.py: Historical data loading
- features.py: Database feature extraction
- intelligence.py: Smart parsing (journal + raw artifacts)
- models.py: Model training/loading/saving
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import features, intelligence, loaders, models


def learn(
    db_path: str = "./.pf/repo_index.db",
    manifest_path: str = "./.pf/manifest.json",
    enable_git: bool = False,
    model_dir: str = "./.pf/ml",
    window: int = 50,
    seed: int = 13,
    print_stats: bool = False,
    feedback_path: str = None,
    train_on: str = "full",
    session_dir: str = None,
) -> dict[str, Any]:
    """Train ML models from artifacts.

    Args:
        session_dir: Optional path to Claude Code session logs (enables Tier 5 agent behavior features)
    """
    if not models.check_ml_available():
        return {"success": False, "error": "ML not available"}

    # Load manifest
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        all_file_paths = [entry["path"] for entry in manifest]
        file_paths = [fp for fp in all_file_paths if models.is_source_file(fp)]

        if print_stats:
            excluded_count = len(all_file_paths) - len(file_paths)
            if excluded_count > 0:
                print(f"Excluded {excluded_count} non-source files (tests, docs, configs)")

    except Exception as e:
        return {"success": False, "error": f"Failed to load manifest: {e}"}

    if not file_paths:
        return {"success": False, "error": "No source files found in manifest"}

    # TIER 1: Load historical data from archived runs
    history_dir = Path("./.pf/history")
    historical_data = loaders.load_all_historical_data(history_dir, train_on, window, enable_git)

    # TIER 4: Load git churn data (commits, authors, recency)
    if enable_git:
        historical_data["git_churn"] = loaders.load_git_churn(
            file_paths=file_paths,
            window_days=90,
            root_path=Path(".")
        )

    # TIER 2-5: Load database features from repo_index.db
    # Tier 5 (agent behavior) is enabled if session_dir is provided
    session_path = Path(session_dir) if session_dir else None
    db_features = features.load_all_db_features(db_path, file_paths, session_dir=session_path)

    # TIER 3: Load intelligent features (NEW - THE MISSING 90%)
    # Currently not used in feature matrix but available for future enhancement
    # intelligent_data = intelligence.parse_all_raw_artifacts(Path("./.pf/raw"))

    # Build features and labels
    feature_matrix, feature_name_map = models.build_feature_matrix(
        file_paths,
        manifest_path,
        db_features,
        historical_data,
    )

    root_cause_labels, next_edit_labels, risk_labels = models.build_labels(
        file_paths,
        historical_data["journal_stats"],
        historical_data["rca_stats"],
    )

    # Load human feedback if provided
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
                print(f"Incorporating human feedback for {feedback_count} files")

        except Exception as e:
            if print_stats:
                print(f"Warning: Could not load feedback file: {e}")

    # Check data size
    import numpy as np
    n_samples = len(file_paths)
    cold_start = n_samples < 500

    if print_stats:
        print(f"Training on {n_samples} files")
        print(f"Features: {feature_matrix.shape[1]} dimensions")
        print(f"Root cause positive: {np.sum(root_cause_labels)}/{n_samples}")
        print(f"Next edit positive: {np.sum(next_edit_labels)}/{n_samples}")
        print(f"Mean risk: {np.mean(risk_labels):.3f}")
        if cold_start:
            print("WARNING: Cold-start with <500 samples, expect noisy signals")

    # Train models
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

    # Calculate stats
    stats = {
        "n_samples": n_samples,
        "n_features": feature_matrix.shape[1],
        "root_cause_positive_ratio": float(np.mean(root_cause_labels)),
        "next_edit_positive_ratio": float(np.mean(next_edit_labels)),
        "mean_risk": float(np.mean(risk_labels)),
        "cold_start": cold_start,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Save models
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
    model_dir: str = "./.pf/ml",
    topk: int = 10,
    out_path: str = "./.pf/insights/ml_suggestions.json",
    print_plan: bool = False,
) -> dict[str, Any]:
    """Generate ML suggestions for workset files."""
    if not models.check_ml_available():
        return {"success": False, "error": "ML not available"}

    # Load models
    (
        root_cause_clf,
        next_edit_clf,
        risk_reg,
        scaler,
        root_cause_calibrator,
        next_edit_calibrator,
        feature_map,
    ) = models.load_models(model_dir)

    if root_cause_clf is None:
        print(f"No models found in {model_dir}. Run 'aud learn' first.")
        return {"success": False, "error": "Models not found"}

    # Load workset
    try:
        with open(workset_path) as f:
            workset = json.load(f)
        all_file_paths = [p["path"] for p in workset.get("paths", [])]
        file_paths = [fp for fp in all_file_paths if models.is_source_file(fp)]

        if print_plan:
            excluded_count = len(all_file_paths) - len(file_paths)
            if excluded_count > 0:
                print(f"Excluded {excluded_count} non-source files from suggestions")

    except Exception as e:
        return {"success": False, "error": f"Failed to load workset: {e}"}

    if not file_paths:
        return {"success": False, "error": "No source files in workset"}

    # Load database features
    db_features = features.load_all_db_features(db_path, file_paths)

    # Build features (no historical data for prediction)
    feature_matrix, _ = models.build_feature_matrix(
        file_paths,
        manifest_path,
        db_features,
        {
            "journal_stats": {},
            "rca_stats": {},
            "ast_stats": {},
            "git_churn": {},
        },
    )

    # Get predictions
    import numpy as np
    features_scaled = scaler.transform(feature_matrix)

    root_cause_scores = root_cause_clf.predict_proba(features_scaled)[:, 1]
    next_edit_scores = next_edit_clf.predict_proba(features_scaled)[:, 1]
    risk_scores = np.clip(risk_reg.predict(features_scaled), 0, 1)

    # Apply calibration if available
    if root_cause_calibrator is not None:
        root_cause_scores = root_cause_calibrator.transform(root_cause_scores)
    if next_edit_calibrator is not None:
        next_edit_scores = next_edit_calibrator.transform(next_edit_scores)

    # Calculate confidence intervals
    root_cause_std = np.zeros(len(file_paths))
    next_edit_std = np.zeros(len(file_paths))

    if hasattr(root_cause_clf, "estimators_"):
        tree_preds = np.array(
            [tree.predict_proba(features_scaled)[:, 1] for tree in root_cause_clf.estimators_]
        )
        root_cause_std = np.std(tree_preds, axis=0)

    if hasattr(next_edit_clf, "estimators_"):
        tree_preds = np.array(
            [tree.predict_proba(features_scaled)[:, 1] for tree in next_edit_clf.estimators_]
        )
        next_edit_std = np.std(tree_preds, axis=0)

    # Rank files
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

    # Build output
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

    # Write output
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    import os
    tmp_path = f"{out_path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(output, f, indent=2, sort_keys=True)
    os.replace(tmp_path, out_path)

    if print_plan:
        print(f"Workset: {len(file_paths)} files")
        print(f"\nTop {min(5, topk)} likely root causes:")
        for item in output["likely_root_causes"][:5]:
            conf_str = f" (±{item['confidence_std']:.3f})" if item.get("confidence_std", 0) > 0 else ""
            print(f"  {item['score']:.3f}{conf_str} - {item['path']}")

    return {
        "success": True,
        "out_path": out_path,
        "workset_size": len(file_paths),
        "original_size": len(all_file_paths),
        "excluded_count": len(all_file_paths) - len(file_paths),
        "topk": topk,
    }
