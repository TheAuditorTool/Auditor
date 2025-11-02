# Tier 5 Pipeline Integration - Implementation Plan

## SUMMARY

Add automatic session analysis to `aud full` pipeline so Tier 5 data is always fresh.

## CHANGES REQUIRED

### 1. Add Session Detection Helper (`theauditor/session/detector.py` - NEW FILE)

```python
"""Auto-detect Claude Code and Codex session directories."""

import json
from pathlib import Path
from typing import Optional


def detect_session_directory(root_path: Path) -> Optional[Path]:
    """
    Auto-detect AI assistant session directory for current project.

    Supports:
    - Claude Code: ~/.claude/projects/<project-name>/
    - Codex: ~/.codex/sessions/YYYY/MM/DD/*.jsonl (filters by cwd in session_meta)

    Args:
        root_path: Project root directory

    Returns:
        Path to session directory or None if not found
    """
    home = Path.home()

    # Try Claude Code first (project-specific directory)
    claude_dir = detect_claude_code_sessions(root_path, home)
    if claude_dir:
        return claude_dir

    # Try Codex (requires filtering by cwd)
    codex_dir = detect_codex_sessions(root_path, home)
    if codex_dir:
        return codex_dir

    return None


def detect_claude_code_sessions(root_path: Path, home: Path) -> Optional[Path]:
    """Detect Claude Code session directory."""
    # Pattern: ~/.claude/projects/C--Users-santa-Desktop-TheAuditor
    project_name = str(root_path).replace('/', '-').replace('\\', '-').replace(':', '-')

    candidates = [
        home / '.claude' / 'projects' / project_name,
        root_path / '.claude-sessions',  # Custom location
    ]

    for candidate in candidates:
        if candidate.exists() and list(candidate.glob('*.jsonl')):
            return candidate

    return None


def detect_codex_sessions(root_path: Path, home: Path) -> Optional[Path]:
    """
    Detect Codex session directory by scanning for matching cwd.

    Codex stores sessions in: ~/.codex/sessions/YYYY/MM/DD/*.jsonl
    Each session has session_meta with cwd field.

    Returns path to ~/.codex/sessions if sessions with matching cwd found.
    """
    codex_sessions = home / '.codex' / 'sessions'

    if not codex_sessions.exists():
        return None

    # Quick check: scan recent sessions (last 30 days) for matching cwd
    # Format: rollout-2025-11-02T04-05-04-019a413c-f30a-7721-94a8-e5a2f6391957.jsonl
    try:
        # Get all .jsonl files recursively
        session_files = list(codex_sessions.rglob('*.jsonl'))

        if not session_files:
            return None

        # Check first line of recent sessions for cwd match
        root_str = str(root_path.resolve())

        for session_file in session_files[:50]:  # Check last 50 sessions
            try:
                with open(session_file, 'r') as f:
                    first_line = f.readline()
                    data = json.loads(first_line)

                    if data.get('type') == 'session_meta':
                        payload = data.get('payload', {})
                        cwd = payload.get('cwd', '')

                        # Normalize paths for comparison
                        if Path(cwd).resolve() == root_path.resolve():
                            # Found matching session - return base sessions dir
                            return codex_sessions
            except (json.JSONDecodeError, IOError):
                continue

        return None
    except Exception:
        return None


def get_matching_codex_sessions(root_path: Path, sessions_dir: Path) -> list[Path]:
    """
    Get all Codex session files matching the project root path.

    Args:
        root_path: Project root directory
        sessions_dir: Base ~/.codex/sessions directory

    Returns:
        List of .jsonl files with matching cwd
    """
    matching = []
    root_str = str(root_path.resolve())

    for session_file in sessions_dir.rglob('*.jsonl'):
        try:
            with open(session_file, 'r') as f:
                first_line = f.readline()
                data = json.loads(first_line)

                if data.get('type') == 'session_meta':
                    payload = data.get('payload', {})
                    cwd = payload.get('cwd', '')

                    if Path(cwd).resolve() == root_path.resolve():
                        matching.append(session_file)
        except (json.JSONDecodeError, IOError):
            continue

    return matching
```

### 2. Modify Pipeline (`theauditor/pipelines.py`)

**Line 454: Add session analysis to command_order (BEFORE report)**

```python
command_order = [
    ("index", []),
    ...
    ("fce", []),
    ("session-analyze", []),  # ← ADD THIS (Phase 27)
    ("report", []),
]
```

**Line 530: Add description for session-analyze**

```python
elif cmd_name == "session-analyze":
    description = f"{phase_num}. Analyze AI agent sessions (Tier 5)"
```

**Line 661-666: Add session-analyze to final_commands categorization**

```python
# Stage 4: Final aggregation (must run last)
elif "fce" in cmd_str:
    final_commands.append((phase_name, cmd))
elif "session-analyze" in cmd_str:  # ← ADD THIS
    final_commands.append((phase_name, cmd))
elif "report" in cmd_str:
    final_commands.append((phase_name, cmd))
```

### 3. Create Session Analysis Command (`theauditor/commands/session.py` - MODIFY)

**Add `analyze` subcommand:**

```python
@click.group(name='session')
def session():
    """AI agent session analysis commands."""
    pass


@session.command(name='analyze')
@click.option('--session-dir', help='Path to session directory (auto-detects if omitted)')
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
    from theauditor.session.detector import detect_session_directory
    from theauditor.session.analysis import SessionAnalysis
    from theauditor.session.parser import SessionParser

    root_path = Path.cwd()

    # Auto-detect session directory if not provided
    if not session_dir:
        session_dir = detect_session_directory(root_path)
        if not session_dir:
            click.echo("[INFO] No AI agent sessions found - skipping Tier 5 analysis")
            return
        click.echo(f"[INFO] Auto-detected sessions: {session_dir}")
    else:
        session_dir = Path(session_dir)

    # Parse and analyze sessions
    click.echo(f"[TIER 5] Analyzing AI agent sessions...")

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
```

**Register command in `theauditor/cli.py`:**

```python
from theauditor.commands import session
cli.add_command(session.session)
```

### 4. Already Fixed (Previous Work)

- ✅ Path normalization in `diff_scorer.py` (Line 104)
- ✅ Database path fix in `features.py` (Line 884)
- ✅ Persistent `.pf/ml/` directory (`_archive.py` Line 40)

## TESTING

```bash
# Test 1: Auto-detection works
cd /path/to/project
aud session analyze
# Should auto-detect ~/.claude/projects/... or ~/.codex/sessions

# Test 2: Full pipeline includes Tier 5
aud full --offline
# Should see "[Phase 27/28] Analyze AI agent sessions (Tier 5)"

# Test 3: ML training sees Tier 5 data
aud learn --session-analysis --print-stats
# Should show Tier 5 statistics (workflow compliance, risk scores, etc.)
```

## ROLLOUT

1. Create `theauditor/session/detector.py` with auto-detection logic
2. Modify `theauditor/commands/session.py` - add `analyze` subcommand
3. Modify `theauditor/pipelines.py` - add session-analyze to pipeline
4. Register `session` group in `theauditor/cli.py`
5. Test with `aud full --offline`

## IMPACT

- **Before**: Session analysis never runs → Tier 5 always empty → ML models missing 8 features
- **After**: Session analysis runs every `aud full` → Tier 5 always fresh → ML models use all 97 features

**User runs 40 `aud full` per day → 40 automatic Tier 5 updates per day → Always-fresh agent behavior data**

## STATUS

- [x] Bug Fix #1: Wrong database path (features.py:884)
- [x] Bug Fix #2: Path normalization (diff_scorer.py:104)
- [ ] **TODO**: Create detector.py
- [ ] **TODO**: Add `session analyze` command
- [ ] **TODO**: Add to pipeline (pipelines.py)
- [ ] **TODO**: Test full integration
