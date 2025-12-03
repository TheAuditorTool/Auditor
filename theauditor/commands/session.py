"""Analyze Claude Code session interactions."""

import json
from datetime import UTC, datetime
from pathlib import Path

import click

from theauditor.pipeline.ui import console
from theauditor.session.activity_metrics import (
    ActivityClassifier,
    analyze_activity,
    analyze_multiple_sessions as analyze_activity_multiple,
)
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
            console.print("[info]No AI agent sessions found - skipping Tier 5 analysis[/info]")
            return
        console.print(f"[info]Auto-detected sessions: {session_dir}[/info]")
    else:
        session_dir = Path(session_dir)

    agent_type = detect_agent_type(session_dir)
    console.print(f"[info]Detected agent: {agent_type}[/info]")

    console.print("\\[TIER 5] Analyzing AI agent sessions...")

    parser = SessionParser()
    analyzer = SessionAnalysis()

    try:
        sessions = parser.parse_all_sessions(session_dir)

        if not sessions:
            console.print("[info]No sessions found in directory[/info]")
            return

        console.print(f"\\[TIER 5] Found {len(sessions)} sessions", highlight=False)

        for i, session in enumerate(sessions, 1):
            try:
                analyzer.analyze_session(session)
                if i % 50 == 0:
                    console.print(
                        f"\\[TIER 5] Progress: {i}/{len(sessions)} sessions analyzed",
                        highlight=False,
                    )
            except Exception as e:
                console.print(
                    f"[warning]Failed to analyze session {session.session_id}: {e}[/warning]",
                    stderr=True,
                )
                continue

        console.print(
            f"[success]Tier 5 analysis complete: {len(sessions)} sessions stored[/success]"
        )

    except Exception as e:
        console.print(f"[error]Session analysis failed: {e}[/error]", stderr=True)
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

    console.print(f"Analyzing sessions for project: {project_path}", highlight=False)

    parser = SessionParser()
    session_dir = parser.find_project_sessions(project_path)

    if not session_dir.exists():
        console.print(f"No sessions found for project: {project_path}", highlight=False)
        console.print(f"Expected directory: {session_dir}", highlight=False)
        return

    console.print(f"Loading sessions from: {session_dir}", highlight=False)
    all_sessions = parser.parse_all_sessions(session_dir)

    if not all_sessions:
        console.print("No valid sessions found")
        return

    all_sessions.sort(
        key=lambda s: s.assistant_messages[0].datetime
        if s.assistant_messages
        else datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    sessions_to_analyze = all_sessions[:limit] if limit else all_sessions

    console.print(f"\nFound {len(all_sessions)} total sessions", highlight=False)
    console.print(f"Analyzing {len(sessions_to_analyze)} most recent sessions\n", highlight=False)

    db_full_path = Path(project_path) / db_path
    analyzer = SessionAnalyzer(db_path=db_full_path if db_full_path.exists() else None)

    if db_full_path.exists():
        console.print(f"Using database for cross-referencing: {db_full_path}", highlight=False)
    else:
        console.print("Database not found - some detectors will be disabled")

    aggregate_report = analyzer.analyze_multiple_sessions(sessions_to_analyze)

    console.rule()
    console.print("SESSION ANALYSIS SUMMARY")
    console.rule()

    console.print(f"\nSessions analyzed: {aggregate_report['total_sessions']}", highlight=False)
    console.print(f"Total findings: {aggregate_report['total_findings']}", highlight=False)

    console.print("\n--- Aggregate Stats ---")
    stats = aggregate_report["aggregate_stats"]
    console.print(f"Total tool calls: {stats['total_tool_calls']}", highlight=False)
    console.print(f"Total reads: {stats['total_reads']}", highlight=False)
    console.print(f"Total edits: {stats['total_edits']}", highlight=False)
    console.print(
        f"Avg tool calls/session: {stats['avg_tool_calls_per_session']:.1f}", highlight=False
    )
    console.print(f"Edit-to-read ratio: {stats['edit_to_read_ratio']:.2f}", highlight=False)

    console.print("\n--- Findings by Category ---")
    for category, count in sorted(
        aggregate_report["findings_by_category"].items(), key=lambda x: x[1], reverse=True
    ):
        console.print(f"  {category}: {count}", highlight=False)

    if show_findings and aggregate_report["top_findings"]:
        console.print("\n--- Top Findings ---")
        for i, finding in enumerate(aggregate_report["top_findings"][:10], 1):
            console.print(f"\n{i}. \\[{finding.severity.upper()}] {finding.title}", highlight=False)
            console.print(f"   {finding.description}", highlight=False)
            if finding.evidence:
                console.print(
                    f"   Evidence: {json.dumps(finding.evidence, indent=4)}", highlight=False
                )

    analyzer.close()


@session.command()
@click.argument("session_file", type=click.Path(exists=True))
@click.option("--db-path", default=".pf/repo_index.db", help="Path to repo_index.db")
@handle_exceptions
def inspect(session_file, db_path):
    """Inspect a single session file in detail."""
    console.print(f"Loading session: {session_file}", highlight=False)

    session_obj = load_session(session_file)

    console.print("\n=== Session Details ===")
    console.print(f"Session ID: {session_obj.session_id}", highlight=False)
    console.print(f"Agent ID: {session_obj.agent_id}", highlight=False)
    console.print(f"Working directory: {session_obj.cwd}", highlight=False)
    console.print(f"Git branch: {session_obj.git_branch}", highlight=False)
    console.print(f"User messages: {len(session_obj.user_messages)}", highlight=False)
    console.print(f"Assistant messages: {len(session_obj.assistant_messages)}", highlight=False)
    console.print(f"Total tool calls: {len(session_obj.all_tool_calls)}", highlight=False)

    files_touched = session_obj.files_touched
    if files_touched:
        console.print("\n=== Files Touched ===")
        for tool, files in files_touched.items():
            console.print(f"\n{tool}:", highlight=False)
            for file in set(files):
                count = files.count(file)
                console.print(f"  - {file}" + (f" (x{count})" if count > 1 else ""), markup=False)

    db_full_path = Path(session_obj.cwd) / db_path if session_obj.cwd else Path(db_path)
    analyzer = SessionAnalyzer(db_path=db_full_path if db_full_path.exists() else None)

    stats, findings = analyzer.analyze_session(session_obj)

    console.print("\n=== Session Stats ===")
    console.print(f"Total turns: {stats.total_turns}", highlight=False)
    console.print(f"Files read: {stats.files_read}", highlight=False)
    console.print(f"Files edited: {stats.files_edited}", highlight=False)
    console.print(f"Files written: {stats.files_written}", highlight=False)
    console.print(f"Bash commands: {stats.bash_commands}", highlight=False)
    console.print(f"Avg tokens/turn: {stats.avg_tokens_per_turn:.0f}", highlight=False)

    # Activity metrics (talk vs work vs planning)
    activity = analyze_activity(session_obj)
    console.print("\n=== Activity Breakdown ===")
    console.print(f"Planning:     {activity.planning_turns:3d} turns ({activity.planning_ratio:5.1%})  |  {activity.planning_tokens:,} tokens ({activity.planning_token_ratio:5.1%})", highlight=False)
    console.print(f"Working:      {activity.working_turns:3d} turns ({activity.working_ratio:5.1%})  |  {activity.working_tokens:,} tokens ({activity.working_token_ratio:5.1%})", highlight=False)
    console.print(f"Research:     {activity.research_turns:3d} turns ({activity.research_ratio:5.1%})  |  {activity.research_tokens:,} tokens ({activity.research_token_ratio:5.1%})", highlight=False)
    console.print(f"Conversation: {activity.conversation_turns:3d} turns ({activity.conversation_ratio:5.1%})  |  {activity.conversation_tokens:,} tokens ({activity.conversation_token_ratio:5.1%})", highlight=False)
    console.print(f"\nEfficiency:", highlight=False)
    console.print(f"  Work/Talk ratio:    {activity.work_to_talk_ratio:.2f}", highlight=False)
    console.print(f"  Research/Work ratio: {activity.research_to_work_ratio:.2f}", highlight=False)
    console.print(f"  Tokens per edit:    {activity.tokens_per_edit:.0f}", highlight=False)

    if findings:
        console.print(f"\n=== Findings ({len(findings)}) ===", highlight=False)
        for finding in findings:
            console.print(f"\n\\[{finding.severity.upper()}] {finding.title}", highlight=False)
            console.print(f"  {finding.description}", highlight=False)
            if finding.evidence:
                console.print(
                    f"  Evidence: {json.dumps(finding.evidence, indent=4)}", highlight=False
                )

    analyzer.close()


@session.command()
@click.option("--project-path", default=None, help="Project path (defaults to current directory)")
@click.option("--limit", type=int, default=20, help="Number of recent sessions to analyze")
@click.option("--json-output", is_flag=True, help="Output as JSON")
@handle_exceptions
def activity(project_path, limit, json_output):
    """Analyze talk vs work vs planning ratios across sessions.

    Classifies AI turns into four categories:
    - PLANNING: Discussion, approach design (no tools, substantial text)
    - WORKING: Actual code changes (Edit, Write, Bash)
    - RESEARCH: Information gathering (Read, Grep, Glob, Task)
    - CONVERSATION: Questions, clarifications, short exchanges

    Shows token distribution and efficiency metrics.
    """
    if project_path is None:
        project_path = str(Path.cwd())

    parser = SessionParser()
    session_dir = parser.find_project_sessions(project_path)

    if not session_dir.exists():
        console.print(f"[warning]No sessions found for: {project_path}[/warning]")
        return

    session_files = parser.list_sessions(session_dir)
    if not session_files:
        console.print("[warning]No session files found[/warning]")
        return

    # Take most recent sessions
    recent_files = session_files[-limit:] if limit else session_files
    console.print(f"Analyzing {len(recent_files)} sessions...", highlight=False)

    sessions = []
    for sf in recent_files:
        try:
            sessions.append(parser.parse_session(sf))
        except Exception:
            continue

    if not sessions:
        console.print("[warning]No valid sessions to analyze[/warning]")
        return

    results = analyze_activity_multiple(sessions)

    if json_output:
        # Remove per_session for cleaner output
        output = {k: v for k, v in results.items() if k != "per_session"}
        console.print(json.dumps(output, indent=2))
        return

    # Pretty print
    console.rule("Activity Analysis")
    console.print(f"Sessions analyzed: {results['session_count']}", highlight=False)

    console.print("\n[bold]Token Distribution[/bold]")
    ratios = results["ratios"]
    agg = results["aggregate"]
    console.print(f"  Planning:     {ratios['planning']:5.1%}  ({agg['planning_tokens']:,} tokens)", highlight=False)
    console.print(f"  Working:      {ratios['working']:5.1%}  ({agg['working_tokens']:,} tokens)", highlight=False)
    console.print(f"  Research:     {ratios['research']:5.1%}  ({agg['research_tokens']:,} tokens)", highlight=False)
    console.print(f"  Conversation: {ratios['conversation']:5.1%}  ({agg['conversation_tokens']:,} tokens)", highlight=False)
    console.print(f"  [dim]Total: {agg['total_tokens']:,} tokens[/dim]", highlight=False)

    console.print("\n[bold]Efficiency Averages[/bold]")
    avgs = results["averages"]
    console.print(f"  Work/Talk ratio:    {avgs['work_to_talk_ratio']:.2f}", highlight=False)
    console.print(f"  Tokens per edit:    {avgs['tokens_per_edit']:.0f}", highlight=False)

    # Interpretation
    console.print("\n[bold]Interpretation[/bold]")
    work_pct = ratios["working"] * 100
    talk_pct = (ratios["planning"] + ratios["conversation"]) * 100

    if work_pct > 50:
        console.print(f"  [green]Highly productive[/green] - {work_pct:.0f}% of tokens go to actual work", highlight=False)
    elif work_pct > 30:
        console.print(f"  [yellow]Balanced[/yellow] - {work_pct:.0f}% work, {talk_pct:.0f}% planning/conversation", highlight=False)
    else:
        console.print(f"  [red]High overhead[/red] - Only {work_pct:.0f}% of tokens produce code changes", highlight=False)


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
        console.print(f"No sessions found for: {project_path}", highlight=False)
        return

    session_files = parser.list_sessions(session_dir)
    console.print(f"\nFound {len(session_files)} sessions in: {session_dir}\n", highlight=False)

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

            console.print(f"{session_file.name}", highlight=False)
            console.print(f"  Time: {timestamp}", highlight=False)
            console.print(f"  Branch: {session_obj.git_branch}", highlight=False)
            console.print(
                f"  Turns: {len(session_obj.user_messages) + len(session_obj.assistant_messages)}",
                highlight=False,
            )
            console.print(f"  Tools: {len(session_obj.all_tool_calls)}", highlight=False)
            console.print(f"  Preview: {preview}", highlight=False)
            console.print()
        except Exception as e:
            console.print(f"{session_file.name} - ERROR: {e}\n", highlight=False)
