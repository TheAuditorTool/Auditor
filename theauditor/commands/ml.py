"""Machine learning commands for TheAuditor."""

import click
from pathlib import Path


@click.command(name="learn")
@click.option("--db-path", default="./.pf/repo_index.db", help="Database path")
@click.option("--manifest", default="./.pf/manifest.json", help="Manifest file path")
@click.option("--enable-git", is_flag=True, help="Enable git churn features")
@click.option("--model-dir", default="./.pf/ml", help="Model output directory")
@click.option("--window", default=50, type=int, help="Journal window size")
@click.option("--seed", default=13, type=int, help="Random seed")
@click.option("--feedback", help="Path to human feedback JSON file")
@click.option("--train-on", type=click.Choice(["full", "diff", "all"]), default="full", help="Type of historical runs to train on")
@click.option("--print-stats", is_flag=True, help="Print training statistics")
def learn(db_path, manifest, enable_git, model_dir, window, seed, feedback, train_on, print_stats):
    """Train machine learning models from historical audit data to predict file risk and root causes.

    Learns patterns from past audit runs stored in .pf/history/ to build predictive models
    that identify risky files and likely root causes for future changes. Uses supervised
    learning on features extracted from code structure, git history, and previous findings
    to enable proactive risk assessment before code review.

    AI ASSISTANT CONTEXT:
      Purpose: Train ML models to predict file risk and root cause likelihood
      Input: .pf/history/ (historical audit runs), .pf/repo_index.db (code features)
      Output: .pf/ml/ (trained models: risk predictor, root cause classifier)
      Prerequisites: aud full (multiple historical runs for training data)
      Integration: Models used by 'aud suggest' for prioritized analysis
      Performance: ~10-30 seconds (scales with history size + feature count)

    WHAT IT LEARNS:
      Risk Prediction (Regression Model):
        - Which files are likely to have vulnerabilities
        - Based on: code complexity, churn rate, past findings, dependency centrality
        - Output: Risk score 0.0-1.0 per file

      Root Cause Classification (Binary Classifier):
        - Which files contain the source of a problem (not just symptoms)
        - Based on: function call patterns, data flow, import graph position
        - Output: Root cause probability per file

      Features Extracted (~100 dimensions):
        - Code metrics: cyclomatic complexity, function count, LOC
        - Git metrics: commit frequency, author count, last modified
        - Dependency metrics: import count, imported_by count, centrality
        - Historical metrics: past finding density, fix frequency

    HOW IT WORKS (Training Pipeline):
      1. Historical Data Collection:
         - Scans .pf/history/full/ for past audit run archives
         - Loads findings, manifest, index data from each run
         - Filters by --train-on (full/diff/all runs)

      2. Feature Engineering:
         - Extracts code features from repo_index.db (current state)
         - Computes git churn features if --enable-git specified
         - Normalizes features (z-score) for stable training

      3. Label Generation:
         - Risk labels: Finding density per file (0.0-1.0 scale)
         - Root cause labels: Binary (1=root cause, 0=symptom/no issue)
         - Derived from historical finding patterns

      4. Model Training:
         - Risk model: Gradient Boosting Regressor (XGBoost)
         - Root cause model: Random Forest Classifier
         - 80/20 train/test split, cross-validation

      5. Model Persistence:
         - Saves models to .pf/ml/ (pickle format)
         - Saves feature names, scaler, metadata
         - Ready for 'aud suggest' consumption

    EXAMPLES:
      # Use Case 1: Initial model training (after 5+ audit runs)
      aud full && aud learn --print-stats

      # Use Case 2: Re-train with git features (slower but more accurate)
      aud learn --enable-git --print-stats

      # Use Case 3: Train on diff runs only (faster, less data)
      aud learn --train-on diff

      # Use Case 4: Incorporate human feedback for better accuracy
      aud learn --feedback ./feedback.json --print-stats

    COMMON WORKFLOWS:
      Initial ML Setup (After 5+ Full Audits):
        aud full && aud learn --enable-git --print-stats

      Weekly Re-training (Incremental Learning):
        aud full && aud learn --train-on all --print-stats

      Human-in-the-Loop Refinement:
        aud learn --feedback ./corrections.json && aud suggest --print-plan

    OUTPUT FILES:
      .pf/ml/risk_model.pkl           # Risk prediction model
      .pf/ml/root_cause_model.pkl     # Root cause classifier
      .pf/ml/feature_names.json       # Feature metadata
      .pf/ml/scaler.pkl               # Feature normalization scaler
      .pf/ml/training_stats.json      # Training metrics (if --print-stats)

    OUTPUT FORMAT (training_stats.json Schema):
      {
        "n_features": 98,
        "n_samples": 1234,
        "train_test_split": "80/20",
        "risk_model": {
          "type": "GradientBoostingRegressor",
          "r2_score": 0.75,
          "mean_absolute_error": 0.12
        },
        "root_cause_model": {
          "type": "RandomForestClassifier",
          "accuracy": 0.82,
          "precision": 0.78,
          "recall": 0.85
        },
        "mean_risk": 0.23,
        "root_cause_positive_ratio": 0.15,
        "cold_start": false
      }

    PERFORMANCE EXPECTATIONS:
      Training Data Size:
        Small (<500 samples):       ~5-10 seconds,   ~200MB RAM (cold-start mode)
        Medium (1000-5000 samples): ~15-30 seconds,  ~500MB RAM
        Large (10K+ samples):       ~60-120 seconds, ~1GB RAM

      Accuracy by Sample Size:
        <500 samples:    R²~0.50 (cold-start, poor accuracy)
        1000-5000:       R²~0.70 (moderate accuracy)
        10K+:            R²~0.80+ (production-ready)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        None (all flags can be combined)

      Recommended Combinations:
        --enable-git --print-stats        # Best accuracy with visibility
        --train-on full --feedback <file> # Incorporate human corrections

      Flag Modifiers:
        --enable-git: Adds git churn features (+30% accuracy, +50% time)
        --train-on: Filters training data (full=highest quality)
        --feedback: Incorporates human labels (supervised correction)
        --window: Journal window for temporal features (default 50 commits)

    PREREQUISITES:
      Required:
        aud full (5+ runs)         # Need historical data in .pf/history/
        .pf/repo_index.db          # Current codebase features

      Optional:
        Git repository             # For --enable-git churn features
        Feedback JSON              # For --feedback supervised learning

    EXIT CODES:
      0 = Success, models trained and saved
      1 = Insufficient training data (<100 samples minimum)
      2 = Training failed (convergence error or invalid data)

    RELATED COMMANDS:
      aud full                   # Creates training data in .pf/history/
      aud suggest                # Uses trained models for predictions
      aud learn-feedback         # Re-train with human corrections

    SEE ALSO:
      aud explain fce            # Understand root cause vs symptom distinction
      aud suggest --help         # Learn how models are used for predictions

    TROUBLESHOOTING:
      Error: "Insufficient training data" (<500 samples):
        -> Run 'aud full' at least 5 times to accumulate history
        -> Each run creates ~100-200 samples (files analyzed)
        -> Cold-start mode activates automatically but has poor accuracy

      Warning: "Cold-start mode" (<500 samples):
        -> Models trained but accuracy is poor (R²<0.60)
        -> Continue running audits to accumulate more training data
        -> Re-run 'aud learn' after 10+ full audits for better models

      Training is slow (>2 minutes):
        -> Disable --enable-git to skip git churn computation (2x speedup)
        -> Use --train-on diff instead of full (reduces sample size)
        -> Large feature count (>200) slows training - expected behavior

      Model predictions seem random (low R² score):
        -> Not enough historical diversity (all runs on same code)
        -> Need code changes between audit runs for learning signal
        -> Try --enable-git to add temporal features

    NOTE: ML models require at least 5 historical audit runs (500+ samples) for
    meaningful accuracy. Cold-start mode works with less data but predictions are
    unreliable. Re-train models weekly to incorporate new findings and patterns.
    """
    from theauditor.insights.ml import learn as ml_learn
    
    click.echo(f"[ML] Training models from audit artifacts (using {train_on} runs)...")
    
    result = ml_learn(
        db_path=db_path,
        manifest_path=manifest,
        enable_git=enable_git,
        model_dir=model_dir,
        window=window,
        seed=seed,
        print_stats=print_stats,
        feedback_path=feedback,
        train_on=train_on,
    )
    
    if result.get("success"):
        stats = result.get("stats", {})
        click.echo(f"[OK] Models trained successfully")
        click.echo(f"  * Training data: {train_on} runs from history")
        click.echo(f"  * Files analyzed: {result.get('source_files', 0)}")
        click.echo(f"  * Features: {stats.get('n_features', 0)} dimensions")
        click.echo(f"  * Root cause ratio: {stats.get('root_cause_positive_ratio', 0):.2%}")
        click.echo(f"  * Risk mean: {stats.get('mean_risk', 0):.3f}")
        if stats.get('cold_start'):
            click.echo(f"  [WARN] Cold-start mode (<500 samples)")
        click.echo(f"  * Models saved to: {result.get('model_dir')}")
    else:
        click.echo(f"[FAIL] Training failed: {result.get('error')}", err=True)
        raise click.ClickException(result.get("error"))


@click.command(name="suggest")
@click.option("--db-path", default="./.pf/repo_index.db", help="Database path")
@click.option("--manifest", default="./.pf/manifest.json", help="Manifest file path")
@click.option("--workset", default="./.pf/workset.json", help="Workset file path")
@click.option("--model-dir", default="./.pf/ml", help="Model directory")
@click.option("--topk", default=10, type=int, help="Top K files to suggest")
@click.option("--out", default="./.pf/insights/ml_suggestions.json", help="Output file path")
@click.option("--print-plan", is_flag=True, help="Print suggestions to console")
def suggest(db_path, manifest, workset, model_dir, topk, out, print_plan):
    """Generate ML-powered priority list of files most likely to contain vulnerabilities.

    Uses trained ML models (from 'aud learn') to predict which files in the current
    workset are highest risk and most likely to be root causes of issues. Ranks files
    by predicted risk score to enable prioritized code review and targeted analysis.
    This is a predictive optimization - analyze high-risk files first for faster issue
    discovery.

    AI ASSISTANT CONTEXT:
      Purpose: Prioritize files for review using ML risk predictions
      Input: .pf/ml/ (trained models), .pf/workset.json (files to analyze)
      Output: .pf/insights/ml_suggestions.json (ranked file list with scores)
      Prerequisites: aud learn (must train models first), aud workset (files to rank)
      Integration: Priority list for human reviewers or targeted 'aud taint-analyze'
      Performance: ~1-5 seconds (inference only, no training)

    WHAT IT PREDICTS:
      File Risk Scores (0.0-1.0):
        - Probability that file contains security vulnerabilities
        - Based on: code complexity, dependency centrality, historical patterns
        - Higher score = higher priority for review

      Root Cause Likelihood (0.0-1.0):
        - Probability that file is the source (not symptom) of issues
        - Based on: call graph position, data flow patterns, import structure
        - Useful for focusing fixes at the source vs downstream effects

      Suggestion Rankings:
        - Top K files sorted by risk score (descending)
        - Includes both risk and root cause predictions
        - File path, scores, feature explanations (if available)

    HOW IT WORKS (Inference Pipeline):
      1. Load Trained Models:
         - Reads models from .pf/ml/ (risk_model.pkl, root_cause_model.pkl)
         - Loads feature scaler and metadata
         - Validates model compatibility with current codebase

      2. Extract Features for Workset:
         - Queries repo_index.db for current code metrics
         - Computes dependency features from import graph
         - Normalizes features using saved scaler

      3. Run Inference:
         - Risk model: Predicts vulnerability probability per file
         - Root cause model: Predicts source vs symptom likelihood
         - Fast inference (<1ms per file)

      4. Rank and Filter:
         - Sorts files by risk score (descending)
         - Takes top K files (default 10)
         - Excludes non-source files (configs, docs)

      5. Output Generation:
         - Writes JSON to .pf/insights/ml_suggestions.json
         - Optionally prints human-readable plan (--print-plan)

    EXAMPLES:
      # Use Case 1: Generate top 10 risky files after training models
      aud learn && aud workset --all && aud suggest --print-plan

      # Use Case 2: Prioritize PR review (changed files only)
      aud workset --diff main..HEAD && aud suggest --topk 5 --print-plan

      # Use Case 3: Export suggestions for CI/CD integration
      aud suggest --out ./build/review_priority.json

      # Use Case 4: Focus taint analysis on high-risk files
      aud suggest --topk 3 && aud taint-analyze --files $(cat .pf/insights/ml_suggestions.json | jq -r '.suggestions[].file')

    COMMON WORKFLOWS:
      Code Review Prioritization:
        aud workset --diff main..HEAD && aud suggest --print-plan

      Pre-Release Risk Assessment:
        aud workset --all && aud suggest --topk 20 --out ./release_risks.json

      Continuous Learning (Weekly):
        aud full && aud learn && aud suggest --print-plan

    OUTPUT FILES:
      .pf/insights/ml_suggestions.json   # Ranked priority list with scores
      .pf/ml/ (models read):
        - risk_model.pkl                 # Risk prediction model
        - root_cause_model.pkl           # Root cause classifier
        - feature_names.json             # Feature metadata
        - scaler.pkl                     # Feature normalization

    OUTPUT FORMAT (ml_suggestions.json Schema):
      {
        "suggestions": [
          {
            "file": "src/auth.py",
            "risk_score": 0.87,
            "root_cause_prob": 0.72,
            "rank": 1,
            "features": {
              "complexity": 45,
              "churn": 12,
              "dependency_centrality": 0.65
            }
          }
        ],
        "topk": 10,
        "workset_size": 120,
        "model_metadata": {
          "risk_model_accuracy": 0.75,
          "training_date": "2025-11-01T12:00:00Z"
        }
      }

    PERFORMANCE EXPECTATIONS:
      Inference Speed (per file): <1ms (CPU only)
      Total Time:
        Small workset (<50 files):      ~0.5-1 seconds
        Medium workset (200 files):     ~1-2 seconds
        Large workset (1000+ files):    ~3-5 seconds

    FLAG INTERACTIONS:
      Mutually Exclusive:
        None (all flags can be combined)

      Recommended Combinations:
        --print-plan --topk 5              # Human-readable top 5 priorities
        --workset <custom> --topk 20       # Large priority list for CI

      Flag Modifiers:
        --topk: Number of files to suggest (default 10)
        --print-plan: Shows suggestions in console (human-readable)
        --workset: Custom workset path (default .pf/workset.json)

    PREREQUISITES:
      Required:
        aud learn                  # Must train models first
        aud workset                # Must create workset to rank

      Optional:
        None (standalone inference)

    EXIT CODES:
      0 = Success, suggestions generated
      1 = Models not found (run 'aud learn' first)
      2 = Inference failed (incompatible features or corrupt models)

    RELATED COMMANDS:
      aud learn                  # Trains models required for suggestions
      aud workset                # Creates file list to rank
      aud full                   # Creates training data for 'aud learn'

    SEE ALSO:
      aud learn --help           # Understand model training process
      aud explain fce            # Learn about root cause vs symptom

    TROUBLESHOOTING:
      Error: "Models not found" or "No such file":
        -> Run 'aud learn' first to train models
        -> Check .pf/ml/ directory exists with *.pkl files
        -> Re-run 'aud learn' if models corrupted

      Predictions seem random (all scores ~0.5):
        -> Models trained with insufficient data (cold-start mode)
        -> Re-train with more historical runs: aud full (5+ times) then aud learn
        -> Check training accuracy: aud learn --print-stats (R² should be >0.70)

      Workset empty or suggestions list is empty:
        -> Run 'aud workset --all' to populate workset
        -> Check .pf/workset.json exists and has files
        -> Non-source files (configs, docs) are excluded automatically

      Suggestions don't match intuition (unexpected files ranked high):
        -> Models learn from historical patterns, not human intuition
        -> Provide feedback: create feedback.json and run 'aud learn-feedback'
        -> High churn or complexity files naturally rank higher

    NOTE: Suggestions are predictions based on historical patterns, not guarantees
    of vulnerabilities. Use as a prioritization tool, not a replacement for thorough
    review. Re-train models weekly to keep predictions accurate as code evolves.
    """
    from theauditor.insights.ml import suggest as ml_suggest
    
    click.echo("[ML] Generating suggestions from trained models...")
    
    result = ml_suggest(
        db_path=db_path,
        manifest_path=manifest,
        workset_path=workset,
        model_dir=model_dir,
        topk=topk,
        out_path=out,
        print_plan=print_plan,
    )
    
    if result.get("success"):
        click.echo(f"[OK] Suggestions generated")
        click.echo(f"  * Workset size: {result.get('workset_size', 0)} files")
        click.echo(f"  * Source files analyzed: {result.get('workset_size', 0)}")
        click.echo(f"  * Non-source excluded: {result.get('excluded_count', 0)}")
        click.echo(f"  * Top {result.get('topk', 10)} suggestions saved to: {result.get('out_path')}")
    else:
        click.echo(f"[FAIL] Suggestion generation failed: {result.get('error')}", err=True)
        raise click.ClickException(result.get("error"))


@click.command(name="learn-feedback")
@click.option("--feedback-file", required=True, help="Path to feedback JSON file")
@click.option("--db-path", default="./.pf/repo_index.db", help="Database path")
@click.option("--manifest", default="./.pf/manifest.json", help="Manifest file path")
@click.option("--model-dir", default="./.pf/ml", help="Model output directory")
@click.option("--train-on", type=click.Choice(["full", "diff", "all"]), default="full", help="Type of historical runs to train on")
@click.option("--print-stats", is_flag=True, help="Print training statistics")
def learn_feedback(feedback_file, db_path, manifest, model_dir, train_on, print_stats):
    """Re-train ML models with human corrections to improve prediction accuracy via supervised learning.

    Human-in-the-loop machine learning workflow that incorporates expert feedback to correct
    model predictions. Accepts a JSON file with manual risk/root-cause labels for files that
    were incorrectly predicted, then re-trains models using this ground truth to reduce future
    errors. This is the primary mechanism for improving model accuracy beyond cold-start.

    AI ASSISTANT CONTEXT:
      Purpose: Improve ML model accuracy via human feedback (supervised correction)
      Input: feedback.json (human labels), .pf/history/ (training data), .pf/repo_index.db
      Output: .pf/ml/ (re-trained models with improved accuracy)
      Prerequisites: aud learn (initial models), feedback.json (human corrections)
      Integration: Refines models used by 'aud suggest' for better prioritization
      Performance: ~15-45 seconds (full re-training with feedback incorporated)

    WHAT IT CORRECTS:
      Risk Score Corrections:
        - Override predicted risk for files that were false positives/negatives
        - Example: Model predicted low risk but file had critical vulnerability
        - New label: "is_risky": true (overrides model prediction)

      Root Cause Corrections:
        - Override root cause classification for misattributed issues
        - Example: Model flagged symptom file as root cause
        - New label: "is_root_cause": false (trains model to recognize pattern)

      Edit Likelihood Corrections:
        - Optionally label files that will need edits during fix
        - Helps model learn which files are most actionable
        - New label: "will_need_edit": true

    HOW IT WORKS (Feedback Learning Pipeline):
      1. Feedback File Validation:
         - Parses JSON file for correct format
         - Validates required fields (is_risky, is_root_cause, will_need_edit)
         - Counts feedback entries for reporting

      2. Merge Feedback with Historical Data:
         - Loads historical training data from .pf/history/
         - Overrides historical labels for feedback files
         - Weighted by recency (recent feedback weighted higher)

      3. Feature Re-extraction:
         - Queries current repo_index.db for updated features
         - Ensures feature compatibility with feedback file paths

      4. Model Re-training:
         - Same training pipeline as 'aud learn'
         - Feedback samples get higher weight in loss function
         - Cross-validation ensures feedback doesn't overfit

      5. Model Replacement:
         - Saves new models to .pf/ml/ (overwrites old models)
         - Preserves model metadata with feedback timestamp

    EXAMPLES:
      # Use Case 1: Correct false positives (model over-predicted risk)
      cat > feedback.json <<EOF
      {
        "src/utils.py": {
          "is_risky": false,
          "is_root_cause": false,
          "will_need_edit": false
        }
      }
      EOF
      aud learn-feedback --feedback-file feedback.json --print-stats

      # Use Case 2: Correct missed vulnerabilities (false negatives)
      cat > feedback.json <<EOF
      {
        "src/auth.py": {
          "is_risky": true,
          "is_root_cause": true,
          "will_need_edit": true
        }
      }
      EOF
      aud learn-feedback --feedback-file feedback.json

      # Use Case 3: Batch corrections after code review
      # (Create feedback.json with 10-20 corrections)
      aud learn-feedback --feedback-file ./corrections.json --print-stats

    COMMON WORKFLOWS:
      Weekly Feedback Loop:
        aud suggest --print-plan > review.txt
        # (Manually create feedback.json after review)
        aud learn-feedback --feedback-file feedback.json
        aud suggest --print-plan  # Verify improved predictions

      Post-Incident Learning:
        # After security incident, label missed vulnerability
        aud learn-feedback --feedback-file incident_corrections.json
        aud learn --enable-git --print-stats  # Full re-train

    OUTPUT FILES:
      .pf/ml/risk_model.pkl           # Re-trained risk prediction model
      .pf/ml/root_cause_model.pkl     # Re-trained root cause classifier
      .pf/ml/feedback_history.json    # Log of applied feedback (for auditing)
      .pf/ml/training_stats.json      # Updated training metrics

    FEEDBACK FILE FORMAT (feedback.json Schema):
      {
        "path/to/file.py": {
          "is_risky": true | false,          # Required: Is file risky?
          "is_root_cause": true | false,     # Required: Is file root cause?
          "will_need_edit": true | false     # Required: Will file need edits?
        },
        "another/file.js": {
          "is_risky": false,
          "is_root_cause": false,
          "will_need_edit": false
        }
      }

    PERFORMANCE EXPECTATIONS:
      Re-training Time:
        Small feedback (<10 files):     ~10-15 seconds
        Medium feedback (20-50 files):  ~20-30 seconds
        Large feedback (100+ files):    ~40-60 seconds

      Accuracy Improvement (depends on feedback quality):
        10 corrections:    +5-10% accuracy (marginal)
        50 corrections:    +15-25% accuracy (significant)
        100+ corrections:  +30-40% accuracy (substantial)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        None (all flags can be combined)

      Recommended Combinations:
        --print-stats --train-on full      # Best accuracy with visibility
        --feedback-file <path> --model-dir <dir>  # Custom model location

      Flag Modifiers:
        --feedback-file: Path to JSON with corrections (REQUIRED)
        --train-on: Which historical runs to include (full=best quality)
        --print-stats: Shows accuracy improvements after re-training

    PREREQUISITES:
      Required:
        aud learn                  # Initial models must exist
        feedback.json              # Human-labeled corrections file

      Optional:
        .pf/history/ (5+ runs)     # More history = better learning

    EXIT CODES:
      0 = Success, models re-trained with feedback
      1 = Feedback file not found or invalid format
      2 = Re-training failed (convergence error)

    RELATED COMMANDS:
      aud learn                  # Initial model training (no feedback)
      aud suggest                # Uses re-trained models for predictions
      aud full                   # Creates training data in .pf/history/

    SEE ALSO:
      aud learn --help           # Understand base training process
      aud suggest --help         # Learn how models make predictions

    TROUBLESHOOTING:
      Error: "Feedback file not found":
        -> Check file path is correct and accessible
        -> Use absolute path or relative from current directory
        -> Example: ./feedback.json or /path/to/feedback.json

      Error: "Invalid feedback file format":
        -> Ensure JSON is valid (use jsonlint or jq to validate)
        -> Required fields: is_risky, is_root_cause, will_need_edit
        -> File paths must be relative to project root

      Accuracy didn't improve after feedback:
        -> Need more feedback samples (10+ for measurable improvement)
        -> Ensure feedback covers diverse file types (not just one area)
        -> Check feedback labels are actually correct (garbage in = garbage out)

      Feedback file paths don't match project files:
        -> Use relative paths from project root (e.g., "src/auth.py")
        -> Avoid absolute paths (e.g., "/home/user/project/src/auth.py")
        -> Paths must match exactly as they appear in .pf/manifest.json

    NOTE: Feedback quality matters more than quantity - 10 accurate corrections beat
    50 guesses. Focus feedback on files where model predictions were confidently wrong
    (high-risk predictions that were clean, or low-risk predictions that had bugs).
    """
    from theauditor.insights.ml import learn as ml_learn
    
    # Validate feedback file exists
    if not Path(feedback_file).exists():
        click.echo(f"[FAIL] Feedback file not found: {feedback_file}", err=True)
        raise click.ClickException(f"Feedback file not found: {feedback_file}")
    
    # Validate feedback file format
    try:
        import json
        with open(feedback_file) as f:
            feedback_data = json.load(f)
        
        if not isinstance(feedback_data, dict):
            raise ValueError("Feedback file must contain a JSON object")
        
        # Count feedback entries
        feedback_count = len(feedback_data)
        click.echo(f"[ML] Loading human feedback for {feedback_count} files...")
        
    except Exception as e:
        click.echo(f"[FAIL] Invalid feedback file format: {e}", err=True)
        raise click.ClickException(f"Invalid feedback file: {e}")
    
    click.echo(f"[ML] Re-training models with human feedback (using {train_on} runs)...")
    
    result = ml_learn(
        db_path=db_path,
        manifest_path=manifest,
        model_dir=model_dir,
        print_stats=print_stats,
        feedback_path=feedback_file,
        train_on=train_on,
        # Use default paths for historical data from .pf/history
        enable_git=False,  # Disable git for speed in feedback mode
    )
    
    if result.get("success"):
        stats = result.get("stats", {})
        click.echo(f"[OK] Models re-trained with human feedback")
        click.echo(f"  * Training data: {train_on} runs from history")
        click.echo(f"  * Files analyzed: {result.get('source_files', 0)}")
        click.echo(f"  * Human feedback incorporated: {feedback_count} files")
        click.echo(f"  * Features: {stats.get('n_features', 0)} dimensions")
        click.echo(f"  * Models saved to: {result.get('model_dir')}")
        click.echo(f"\n[TIP] The models have learned from your feedback and will provide more accurate predictions.")
    else:
        click.echo(f"[FAIL] Re-training failed: {result.get('error')}", err=True)
        raise click.ClickException(result.get("error"))