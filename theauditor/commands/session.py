"""Analyze Claude Code session interactions."""

import json
from datetime import UTC, datetime
from pathlib import Path

import click

from theauditor.session.analysis import SessionAnalysis
from theauditor.session.analyzer import SessionAnalyzer
from theauditor.session.detector import detect_agent_type, detect_session_directory
from theauditor.session.parser import SessionParser, load_session
from theauditor.utils.error_handler import handle_exceptions


@click.group()
def session():
    """Analyze Claude Code session interactions and agent behavior."""
    pass


@session.command(name="analyze")
@click.option("--session-dir", help="Path to session directory (auto-detects if omitted)")
@handle_exceptions
def analyze(session_dir):
    """Analyze AI agent sessions and store to .pf/ml/session_history.db.

    Auto-detects session directories for:
    - Claude Code: ~/.claude/projects/<project-name>/
    - Codex: ~/.codex/sessions/ (filtered by cwd)

    Runs 3-layer analysis pipeline:
    1. Parse session logs (.jsonl files)
    2. Score diffs through SAST pipeline
    3. Check workflow compliance (planning.md)

    Stores results to persistent .pf/ml/session_history.db for ML training.
    """
    from pathlib import Path

    root_path = Path.cwd()

    if not session_dir:
        session_dir = detect_session_directory(root_path)
        if not session_dir:
            click.echo("[INFO] No AI agent sessions found - skipping Tier 5 analysis")
            return
        click.echo(f"[INFO] Auto-detected sessions: {session_dir}")
    else:
        session_dir = Path(session_dir)

    agent_type = detect_agent_type(session_dir)
    click.echo(f"[INFO] Detected agent: {agent_type}")

    click.echo("[TIER 5] Analyzing AI agent sessions...")

    parser = SessionParser()
    analyzer = SessionAnalysis()

    try:
        sessions = parser.parse_all_sessions(session_dir)

        if not sessions:
            click.echo("[INFO] No sessions found in directory")
            return

        click.echo(f"[TIER 5] Found {len(sessions)} sessions")

        for i, session in enumerate(sessions, 1):
            try:
                analyzer.analyze_session(session)
                if i % 50 == 0:
                    click.echo(f"[TIER 5] Progress: {i}/{len(sessions)} sessions analyzed")
            except Exception as e:
                click.echo(f"[WARN] Failed to analyze session {session.session_id}: {e}", err=True)
                continue

        click.echo(f"[OK] Tier 5 analysis complete: {len(sessions)} sessions stored")

    except Exception as e:
        click.echo(f"[ERROR] Session analysis failed: {e}", err=True)
        raise


@session.command(name="report")
@click.option("--project-path", default=None, help="Project path (defaults to current directory)")
@click.option("--db-path", default=".pf/repo_index.db", help="Path to repo_index.db")
@click.option("--limit", type=int, default=10, help="Limit number of sessions to analyze")
@click.option("--show-findings/--no-findings", default=True, help="Show individual findings")
@handle_exceptions
def report(project_path, db_path, limit, show_findings):
    """Generate detailed report of Claude Code sessions (legacy analyzer)."""
    if project_path is None:
        project_path = str(Path.cwd())

    click.echo(f"Analyzing sessions for project: {project_path}")

    parser = SessionParser()
    session_dir = parser.find_project_sessions(project_path)

    if not session_dir.exists():
        click.echo(f"No sessions found for project: {project_path}")
        click.echo(f"Expected directory: {session_dir}")
        return

    click.echo(f"Loading sessions from: {session_dir}")
    all_sessions = parser.parse_all_sessions(session_dir)

    if not all_sessions:
        click.echo("No valid sessions found")
        return

    all_sessions.sort(
        key=lambda s: s.assistant_messages[0].datetime
        if s.assistant_messages
        else datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    sessions_to_analyze = all_sessions[:limit] if limit else all_sessions

    click.echo(f"\nFound {len(all_sessions)} total sessions")
    click.echo(f"Analyzing {len(sessions_to_analyze)} most recent sessions\n")

    db_full_path = Path(project_path) / db_path
    analyzer = SessionAnalyzer(db_path=db_full_path if db_full_path.exists() else None)

    if db_full_path.exists():
        click.echo(f"Using database for cross-referencing: {db_full_path}")
    else:
        click.echo("Database not found - some detectors will be disabled")

    aggregate_report = analyzer.analyze_multiple_sessions(sessions_to_analyze)

    click.echo("=" * 60)
    click.echo("SESSION ANALYSIS SUMMARY")
    click.echo("=" * 60)

    click.echo(f"\nSessions analyzed: {aggregate_report['total_sessions']}")
    click.echo(f"Total findings: {aggregate_report['total_findings']}")

    click.echo("\n--- Aggregate Stats ---")
    stats = aggregate_report["aggregate_stats"]
    click.echo(f"Total tool calls: {stats['total_tool_calls']}")
    click.echo(f"Total reads: {stats['total_reads']}")
    click.echo(f"Total edits: {stats['total_edits']}")
    click.echo(f"Avg tool calls/session: {stats['avg_tool_calls_per_session']:.1f}")
    click.echo(f"Edit-to-read ratio: {stats['edit_to_read_ratio']:.2f}")

    click.echo("\n--- Findings by Category ---")
    for category, count in sorted(
        aggregate_report["findings_by_category"].items(), key=lambda x: x[1], reverse=True
    ):
        click.echo(f"  {category}: {count}")

    if show_findings and aggregate_report["top_findings"]:
        click.echo("\n--- Top Findings ---")
        for i, finding in enumerate(aggregate_report["top_findings"][:10], 1):
            click.echo(f"\n{i}. [{finding.severity.upper()}] {finding.title}")
            click.echo(f"   {finding.description}")
            if finding.evidence:
                click.echo(f"   Evidence: {json.dumps(finding.evidence, indent=4)}")

    analyzer.close()


@session.command()
@click.argument("session_file", type=click.Path(exists=True))
@click.option("--db-path", default=".pf/repo_index.db", help="Path to repo_index.db")
@handle_exceptions
def inspect(session_file, db_path):
    """Inspect a single session file in detail."""
    click.echo(f"Loading session: {session_file}")

    session_obj = load_session(session_file)

    click.echo("\n=== Session Details ===")
    click.echo(f"Session ID: {session_obj.session_id}")
    click.echo(f"Agent ID: {session_obj.agent_id}")
    click.echo(f"Working directory: {session_obj.cwd}")
    click.echo(f"Git branch: {session_obj.git_branch}")
    click.echo(f"User messages: {len(session_obj.user_messages)}")
    click.echo(f"Assistant messages: {len(session_obj.assistant_messages)}")
    click.echo(f"Total tool calls: {len(session_obj.all_tool_calls)}")

    files_touched = session_obj.files_touched
    if files_touched:
        click.echo("\n=== Files Touched ===")
        for tool, files in files_touched.items():
            click.echo(f"\n{tool}:")
            for file in set(files):
                count = files.count(file)
                click.echo(f"  - {file}" + (f" (x{count})" if count > 1 else ""))

    db_full_path = Path(session_obj.cwd) / db_path if session_obj.cwd else Path(db_path)
    analyzer = SessionAnalyzer(db_path=db_full_path if db_full_path.exists() else None)

    stats, findings = analyzer.analyze_session(session_obj)

    click.echo("\n=== Session Stats ===")
    click.echo(f"Total turns: {stats.total_turns}")
    click.echo(f"Files read: {stats.files_read}")
    click.echo(f"Files edited: {stats.files_edited}")
    click.echo(f"Files written: {stats.files_written}")
    click.echo(f"Bash commands: {stats.bash_commands}")
    click.echo(f"Avg tokens/turn: {stats.avg_tokens_per_turn:.0f}")

    if findings:
        click.echo(f"\n=== Findings ({len(findings)}) ===")
        for finding in findings:
            click.echo(f"\n[{finding.severity.upper()}] {finding.title}")
            click.echo(f"  {finding.description}")
            if finding.evidence:
                click.echo(f"  Evidence: {json.dumps(finding.evidence, indent=4)}")

    analyzer.close()


@session.command()
@click.option("--project-path", default=None, help="Project path (defaults to current directory)")
@handle_exceptions
def list(project_path):
    """List all sessions for this project."""
    if project_path is None:
        project_path = str(Path.cwd())

    parser = SessionParser()
    session_dir = parser.find_project_sessions(project_path)

    if not session_dir.exists():
        click.echo(f"No sessions found for: {project_path}")
        return

    session_files = parser.list_sessions(session_dir)
    click.echo(f"\nFound {len(session_files)} sessions in: {session_dir}\n")

    for session_file in session_files:
        try:
            session_obj = parser.parse_session(session_file)
            first_msg = session_obj.user_messages[0] if session_obj.user_messages else None
            timestamp = first_msg.datetime.strftime("%Y-%m-%d %H:%M") if first_msg else "Unknown"
            preview = (
                (first_msg.content[:60] + "...")
                if first_msg and len(first_msg.content) > 60
                else (first_msg.content if first_msg else "")
            )

            click.echo(f"{session_file.name}")
            click.echo(f"  Time: {timestamp}")
            click.echo(f"  Branch: {session_obj.git_branch}")
            click.echo(
                f"  Turns: {len(session_obj.user_messages) + len(session_obj.assistant_messages)}"
            )
            click.echo(f"  Tools: {len(session_obj.all_tool_calls)}")
            click.echo(f"  Preview: {preview}")
            click.echo()
        except Exception as e:
            click.echo(f"{session_file.name} - ERROR: {e}\n")
