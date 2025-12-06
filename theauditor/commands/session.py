"""Analyze Claude Code session interactions."""

import json
from datetime import UTC, datetime
from pathlib import Path

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console, err_console
from theauditor.session.activity_metrics import (
    analyze_activity,
)
from theauditor.session.activity_metrics import (
    analyze_multiple_sessions as analyze_activity_multiple,
)
from theauditor.session.analysis import SessionAnalysis
from theauditor.session.detector import detect_agent_type, detect_session_directory
from theauditor.session.parser import SessionParser, load_session
from theauditor.utils.error_handler import handle_exceptions


@click.group(cls=RichGroup)
def session():
    """Analyze AI agent session interactions for quality insights and ML training.

    Parses and analyzes Claude Code, Codex, and other AI agent session logs to extract
    metrics, detect patterns, and store data for machine learning. Provides activity
    classification (planning vs working vs research) and efficiency measurements.

    AI ASSISTANT CONTEXT:
      Purpose: Analyze AI agent session logs for quality and ML training
      Input: Session directory (~/.claude/projects/ or ~/.codex/sessions/)
      Output: .pf/ml/session_history.db, activity metrics, findings
      Prerequisites: AI agent sessions in standard locations
      Integration: ML training pipeline, agent behavior analysis
      Performance: ~1-5 seconds per session

    SUBCOMMANDS:
      analyze:   Parse sessions and store to ML database
      report:    Generate detailed session analysis report
      inspect:   Inspect a single session file in detail
      activity:  Analyze talk vs work vs planning ratios
      list:      List all sessions for this project

    WHAT IT DETECTS:
      - Agent efficiency (work/talk ratio, tokens per edit)
      - Activity breakdown (planning, working, research, conversation)
      - Tool usage patterns (reads, edits, bash commands)
      - Session quality indicators and anti-patterns

    TYPICAL WORKFLOW:
      aud session list                    # See available sessions
      aud session analyze                 # Store to ML database
      aud session activity --limit 20    # Check efficiency trends
      aud session inspect path/to/session.jsonl

    EXAMPLES:
      aud session analyze                 # Auto-detect and analyze
      aud session report --limit 5        # Last 5 sessions report
      aud session activity --json-output  # JSON for scripting
      aud session list --project-path .   # List sessions for current project

    RELATED COMMANDS:
      aud learn       ML training on session data
      aud suggest     Get suggestions from learned patterns

    See: aud manual ml
    """
    pass


@session.command(name="analyze", cls=RichCommand)
@click.option("--session-dir", help="Path to session directory (auto-detects if omitted)")
@handle_exceptions
def analyze(session_dir):
    """Parse AI agent sessions and store to ML database for training.

    Auto-detects and analyzes Claude Code, Codex, and other AI agent session logs.
    Extracts metrics, tool usage, and quality indicators. Stores results to
    persistent database for ML training and trend analysis.

    AI ASSISTANT CONTEXT:
      Purpose: Parse session logs and store to ML database
      Input: Session directory (auto-detected or specified)
      Output: .pf/ml/session_history.db
      Prerequisites: AI agent sessions in standard locations
      Integration: ML training pipeline (aud learn, aud suggest)
      Performance: ~1-5 seconds per session, batch processes all found

    EXAMPLES:
      aud session analyze                       # Auto-detect and analyze
      aud session analyze --session-dir ~/.claude/projects/myapp/

    TROUBLESHOOTING:
      No sessions found:
        -> Check ~/.claude/projects/ for Claude Code sessions
        -> Check ~/.codex/sessions/ for Codex sessions
        -> Use --session-dir to specify custom location

      Analysis fails:
        -> Ensure .jsonl files are valid JSON Lines format
        -> Check session file permissions

    RELATED COMMANDS:
      aud session list      List available sessions
      aud learn             Train ML on session data

    See: aud manual ml
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
                err_console.print(
                    f"[warning]Failed to analyze session {session.session_id}: {e}[/warning]",
                )
                continue

        console.print(
            f"[success]Tier 5 analysis complete: {len(sessions)} sessions stored[/success]"
        )

    except Exception as e:
        err_console.print(
            f"[error]Session analysis failed: {e}[/error]",
        )
        raise


@session.command(name="report", cls=RichCommand)
@click.option("--project-path", default=None, help="Project path (defaults to current directory)")
@click.option("--db-path", default=".pf/repo_index.db", help="Path to repo_index.db")
@click.option("--limit", type=int, default=10, help="Limit number of sessions to analyze")
@click.option("--show-findings/--no-findings", default=True, help="Show individual findings")
@handle_exceptions
def report(project_path, db_path, limit, show_findings):
    """Generate detailed aggregate report of AI agent sessions.

    Analyzes multiple sessions and produces aggregate statistics including
    tool call counts, read/edit ratios, and cross-session findings. Uses
    the legacy analyzer for compatibility with older session formats.

    AI ASSISTANT CONTEXT:
      Purpose: Generate aggregate session analysis report
      Input: Session logs from project directory
      Output: Terminal report with stats and findings
      Prerequisites: Sessions in ~/.claude/projects/
      Integration: Cross-references with repo_index.db if available
      Performance: 1-2 seconds per session

    EXAMPLES:
      aud session report                     # Last 10 sessions
      aud session report --limit 5           # Last 5 sessions
      aud session report --no-findings       # Stats only, no findings

    OUTPUT INCLUDES:
      - Sessions analyzed count
      - Total tool calls, reads, edits
      - Edit-to-read ratio
      - Findings by category
      - Top findings with evidence

    RELATED COMMANDS:
      aud session activity   More detailed activity breakdown
      aud session inspect    Single session deep dive

    See: aud manual ml
    """
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
    analyzer = SessionAnalysis(db_path=db_full_path if db_full_path.exists() else None)

    if db_full_path.exists():
        console.print(f"Using database for cross-referencing: {db_full_path}", highlight=False)
    else:
        console.print("Database not found - some detectors will be disabled")

    aggregate_report = analyzer.analyze_multiple_sessions_with_findings(sessions_to_analyze)

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


@session.command(cls=RichCommand)
@click.argument("session_file", type=click.Path(exists=True))
@click.option("--db-path", default=".pf/repo_index.db", help="Path to repo_index.db")
@handle_exceptions
def inspect(session_file, db_path):
    """Deep-dive inspection of a single session file.

    Loads and analyzes a specific session file, showing detailed breakdown
    of session metadata, files touched, tool usage statistics, and activity
    classification. Most comprehensive view of a single agent session.

    AI ASSISTANT CONTEXT:
      Purpose: Detailed inspection of a single session file
      Input: Path to .jsonl session file
      Output: Terminal report with all session details
      Prerequisites: Valid session file
      Integration: Cross-references with repo_index.db if available
      Performance: <1 second

    EXAMPLES:
      aud session inspect path/to/session.jsonl
      aud session inspect ~/.claude/projects/myapp/session123.jsonl

    OUTPUT INCLUDES:
      - Session metadata (ID, agent, cwd, branch)
      - Message counts (user, assistant, tool calls)
      - Files touched by tool type
      - Session stats (turns, reads, edits, bash)
      - Activity breakdown (planning, working, research, conversation)
      - Efficiency metrics (work/talk ratio, tokens per edit)
      - Findings and anti-patterns

    RELATED COMMANDS:
      aud session list      Find sessions to inspect
      aud session activity  Aggregate activity across sessions

    See: aud manual ml
    """
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
    analyzer = SessionAnalysis(db_path=db_full_path if db_full_path.exists() else None)

    stats, findings = analyzer.analyze_session_with_findings(session_obj)

    console.print("\n=== Session Stats ===")
    console.print(f"Total turns: {stats.total_turns}", highlight=False)
    console.print(f"Files read: {stats.files_read}", highlight=False)
    console.print(f"Files edited: {stats.files_edited}", highlight=False)
    console.print(f"Files written: {stats.files_written}", highlight=False)
    console.print(f"Bash commands: {stats.bash_commands}", highlight=False)
    console.print(f"Avg tokens/turn: {stats.avg_tokens_per_turn:.0f}", highlight=False)

    activity = analyze_activity(session_obj)
    console.print("\n=== Activity Breakdown ===")
    console.print(
        f"Planning:     {activity.planning_turns:3d} turns ({activity.planning_ratio:5.1%})  |  {activity.planning_tokens:,} tokens ({activity.planning_token_ratio:5.1%})",
        highlight=False,
    )
    console.print(
        f"Working:      {activity.working_turns:3d} turns ({activity.working_ratio:5.1%})  |  {activity.working_tokens:,} tokens ({activity.working_token_ratio:5.1%})",
        highlight=False,
    )
    console.print(
        f"Research:     {activity.research_turns:3d} turns ({activity.research_ratio:5.1%})  |  {activity.research_tokens:,} tokens ({activity.research_token_ratio:5.1%})",
        highlight=False,
    )
    console.print(
        f"Conversation: {activity.conversation_turns:3d} turns ({activity.conversation_ratio:5.1%})  |  {activity.conversation_tokens:,} tokens ({activity.conversation_token_ratio:5.1%})",
        highlight=False,
    )
    console.print("\nEfficiency:", highlight=False)
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


@session.command(cls=RichCommand)
@click.option("--project-path", default=None, help="Project path (defaults to current directory)")
@click.option("--limit", type=int, default=20, help="Number of recent sessions to analyze")
@click.option("--json-output", is_flag=True, help="Output as JSON")
@handle_exceptions
def activity(project_path, limit, json_output):
    """Analyze talk vs work vs planning ratios across sessions.

    Classifies AI assistant turns into four activity categories and calculates
    token distribution and efficiency metrics. Key metric for understanding
    agent productivity patterns and identifying inefficiencies.

    AI ASSISTANT CONTEXT:
      Purpose: Activity classification and efficiency analysis
      Input: Session logs from project directory
      Output: Token distribution and efficiency metrics
      Prerequisites: Sessions in ~/.claude/projects/
      Integration: ML training, productivity analysis
      Performance: ~1 second for 20 sessions

    ACTIVITY CATEGORIES:
      PLANNING:     Discussion, approach design (no tools, substantial text)
      WORKING:      Actual code changes (Edit, Write, Bash)
      RESEARCH:     Information gathering (Read, Grep, Glob, Task)
      CONVERSATION: Questions, clarifications, short exchanges

    EXAMPLES:
      aud session activity                    # Default 20 sessions
      aud session activity --limit 50         # More sessions
      aud session activity --json-output      # JSON for scripting

    EFFICIENCY METRICS:
      Work/Talk ratio:    Higher = more productive
      Research/Work ratio: Lower = less thrashing
      Tokens per edit:    Lower = more efficient

    INTERPRETATION:
      >50% working:  Highly productive
      30-50% working: Balanced
      <30% working:  High overhead, consider improving prompts

    RELATED COMMANDS:
      aud session inspect   Detailed single session analysis
      aud session report    Aggregate findings report

    See: aud manual ml
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
        output = {k: v for k, v in results.items() if k != "per_session"}
        console.print(json.dumps(output, indent=2))
        return

    console.rule("Activity Analysis")
    console.print(f"Sessions analyzed: {results['session_count']}", highlight=False)

    console.print("\n[bold]Token Distribution[/bold]")
    ratios = results["ratios"]
    agg = results["aggregate"]
    console.print(
        f"  Planning:     {ratios['planning']:5.1%}  ({agg['planning_tokens']:,} tokens)",
        highlight=False,
    )
    console.print(
        f"  Working:      {ratios['working']:5.1%}  ({agg['working_tokens']:,} tokens)",
        highlight=False,
    )
    console.print(
        f"  Research:     {ratios['research']:5.1%}  ({agg['research_tokens']:,} tokens)",
        highlight=False,
    )
    console.print(
        f"  Conversation: {ratios['conversation']:5.1%}  ({agg['conversation_tokens']:,} tokens)",
        highlight=False,
    )
    console.print(f"  [dim]Total: {agg['total_tokens']:,} tokens[/dim]", highlight=False)

    console.print("\n[bold]Efficiency Averages[/bold]")
    avgs = results["averages"]
    console.print(f"  Work/Talk ratio:    {avgs['work_to_talk_ratio']:.2f}", highlight=False)
    console.print(f"  Tokens per edit:    {avgs['tokens_per_edit']:.0f}", highlight=False)

    console.print("\n[bold]Interpretation[/bold]")
    work_pct = ratios["working"] * 100
    talk_pct = (ratios["planning"] + ratios["conversation"]) * 100

    if work_pct > 50:
        console.print(
            f"  [green]Highly productive[/green] - {work_pct:.0f}% of tokens go to actual work",
            highlight=False,
        )
    elif work_pct > 30:
        console.print(
            f"  [yellow]Balanced[/yellow] - {work_pct:.0f}% work, {talk_pct:.0f}% planning/conversation",
            highlight=False,
        )
    else:
        console.print(
            f"  [red]High overhead[/red] - Only {work_pct:.0f}% of tokens produce code changes",
            highlight=False,
        )


@session.command(cls=RichCommand)
@click.option("--project-path", default=None, help="Project path (defaults to current directory)")
@handle_exceptions
def list(project_path):
    """List all AI agent sessions for this project.

    Discovers and lists all session files in the project's session directory,
    showing timestamp, git branch, message counts, and a preview of the first
    user message. Use this to find sessions for inspection or debugging.

    AI ASSISTANT CONTEXT:
      Purpose: Discover and list available session files
      Input: Project path (defaults to cwd)
      Output: Terminal list with session metadata
      Prerequisites: Sessions in ~/.claude/projects/
      Integration: Use before inspect or activity commands
      Performance: ~1-2 seconds (parses all session files)

    EXAMPLES:
      aud session list                       # Current project
      aud session list --project-path /path/to/project

    OUTPUT PER SESSION:
      - Filename
      - Timestamp (first message)
      - Git branch
      - Turn count (user + assistant messages)
      - Tool call count
      - Preview of first user message

    RELATED COMMANDS:
      aud session inspect   Deep dive on a specific session
      aud session analyze   Bulk analyze to ML database

    See: aud manual ml
    """
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
