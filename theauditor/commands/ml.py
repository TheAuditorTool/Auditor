"""Machine learning commands for TheAuditor."""

import click
from pathlib import Path


@click.command(name="learn")
@click.option("--db-path", default="./.pf/repo_index.db", help="Database path")
@click.option("--manifest", default="./.pf/manifest.json", help="Manifest file path")
@click.option("--journal", default="./.pf/journal.ndjson", help="Journal file path")
@click.option("--fce", default="./.pf/fce.json", help="FCE file path")
@click.option("--ast", default="./.pf/ast_proofs.json", help="AST proofs file path")
@click.option("--enable-git", is_flag=True, help="Enable git churn features")
@click.option("--model-dir", default="./.pf/ml", help="Model output directory")
@click.option("--window", default=50, type=int, help="Journal window size")
@click.option("--seed", default=13, type=int, help="Random seed")
@click.option("--feedback", help="Path to human feedback JSON file")
@click.option("--train-on", type=click.Choice(["full", "diff", "all"]), default="full", help="Type of historical runs to train on")
@click.option("--print-stats", is_flag=True, help="Print training statistics")
def learn(db_path, manifest, journal, fce, ast, enable_git, model_dir, window, seed, feedback, train_on, print_stats):
    """Train ML models from audit artifacts to predict risk and root causes."""
    from theauditor.ml import learn as ml_learn
    
    click.echo(f"[ML] Training models from audit artifacts (using {train_on} runs)...")
    
    result = ml_learn(
        db_path=db_path,
        manifest_path=manifest,
        journal_path=journal,
        fce_path=fce,
        ast_path=ast,
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
@click.option("--fce", default="./.pf/fce.json", help="FCE file path")
@click.option("--ast", default="./.pf/ast_proofs.json", help="AST proofs file path")
@click.option("--model-dir", default="./.pf/ml", help="Model directory")
@click.option("--topk", default=10, type=int, help="Top K files to suggest")
@click.option("--out", default="./.pf/insights/ml_suggestions.json", help="Output file path")
@click.option("--print-plan", is_flag=True, help="Print suggestions to console")
def suggest(db_path, manifest, workset, fce, ast, model_dir, topk, out, print_plan):
    """Generate ML-based suggestions for risky files and likely root causes."""
    from theauditor.ml import suggest as ml_suggest
    
    click.echo("[ML] Generating suggestions from trained models...")
    
    result = ml_suggest(
        db_path=db_path,
        manifest_path=manifest,
        workset_path=workset,
        fce_path=fce,
        ast_path=ast,
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
    """
    Re-train models with human feedback for improved accuracy.
    
    The feedback file should be a JSON file with the format:
    {
        "path/to/file.py": {
            "is_risky": true,
            "is_root_cause": false,
            "will_need_edit": true
        },
        ...
    }
    """
    from theauditor.ml import learn as ml_learn
    
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