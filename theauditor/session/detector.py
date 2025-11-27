"""Auto-detect Claude Code and Codex session directories."""

import json
from pathlib import Path
from typing import Literal


AgentType = Literal["claude-code", "codex", "unknown"]


def detect_session_directory(root_path: Path) -> Path | None:
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

    claude_dir = detect_claude_code_sessions(root_path, home)
    if claude_dir:
        return claude_dir

    codex_dir = detect_codex_sessions(root_path, home)
    if codex_dir:
        return codex_dir

    return None


def detect_claude_code_sessions(root_path: Path, home: Path) -> Path | None:
    """Detect Claude Code session directory."""

    project_name = str(root_path).replace("/", "-").replace("\\", "-").replace(":", "-")

    candidates = [
        home / ".claude" / "projects" / project_name,
        root_path / ".claude-sessions",
    ]

    for candidate in candidates:
        if candidate.exists() and list(candidate.glob("*.jsonl")):
            return candidate

    return None


def detect_codex_sessions(root_path: Path, home: Path) -> Path | None:
    """
    Detect Codex session directory by scanning for matching cwd.

    Codex stores sessions in: ~/.codex/sessions/YYYY/MM/DD/*.jsonl
    Each session has session_meta with cwd field.

    Returns path to ~/.codex/sessions if sessions with matching cwd found.
    """
    codex_sessions = home / ".codex" / "sessions"

    if not codex_sessions.exists():
        return None

    try:
        session_files = list(codex_sessions.rglob("*.jsonl"))

        if not session_files:
            return None

        for session_file in session_files[:50]:
            try:
                with open(session_file) as f:
                    first_line = f.readline()
                    data = json.loads(first_line)

                    if data.get("type") == "session_meta":
                        payload = data.get("payload", {})
                        cwd = payload.get("cwd", "")

                        if Path(cwd).resolve() == root_path.resolve():
                            return codex_sessions
            except (json.JSONDecodeError, OSError):
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

    for session_file in sessions_dir.rglob("*.jsonl"):
        try:
            with open(session_file) as f:
                first_line = f.readline()
                data = json.loads(first_line)

                if data.get("type") == "session_meta":
                    payload = data.get("payload", {})
                    cwd = payload.get("cwd", "")

                    if Path(cwd).resolve() == root_path.resolve():
                        matching.append(session_file)
        except (json.JSONDecodeError, OSError):
            continue

    return matching


def detect_agent_type(session_dir: Path) -> AgentType:
    """
    Detect what type of AI agent created the sessions by inspecting .jsonl format.

    Args:
        session_dir: Directory containing session .jsonl files

    Returns:
        'claude-code', 'codex', or 'unknown'
    """

    for jsonl_file in session_dir.glob("*.jsonl"):
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                first_line = f.readline()

            if not first_line.strip():
                continue

            data = json.loads(first_line)

            if data.get("type") == "session_meta":
                originator = data.get("payload", {}).get("originator", "")
                if "codex" in originator.lower():
                    return "codex"

            if data.get("type") == "file-history-snapshot":
                return "claude-code"

        except (json.JSONDecodeError, OSError, KeyError):
            continue

    return "unknown"
