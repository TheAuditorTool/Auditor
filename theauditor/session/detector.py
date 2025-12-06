"""Auto-detect Claude Code and Codex session directories."""

import json
from collections.abc import Iterator
from itertools import islice
from pathlib import Path
from typing import Literal

from theauditor.utils.logging import logger

AgentType = Literal["claude-code", "codex", "unknown"]


def detect_session_directory(root_path: Path) -> Path | None:
    """Auto-detect AI assistant session directory for current project."""
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
        if candidate.exists():
            if any(candidate.glob("*.jsonl")):
                return candidate

    return None


def detect_codex_sessions(root_path: Path, home: Path) -> Path | None:
    """Detect Codex session directory by scanning for matching cwd.

    Uses lazy evaluation (generator) to avoid loading thousands of files into memory.
    """
    codex_sessions = home / ".codex" / "sessions"

    if not codex_sessions.exists():
        return None

    try:
        session_files_gen = codex_sessions.rglob("*.jsonl")

        for session_file in islice(session_files_gen, 50):
            try:
                with open(session_file) as f:
                    first_line = f.readline()
                    data = json.loads(first_line)

                    if data.get("type") == "session_meta":
                        payload = data.get("payload", {})
                        cwd = payload.get("cwd", "")

                        if Path(cwd).resolve() == root_path.resolve():
                            return codex_sessions
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Skipping corrupt session file: {session_file}: {e}")
                continue

        return None
    except Exception as e:
        logger.warning(f"Error scanning codex sessions: {e}")
        return None


def get_matching_codex_sessions(
    root_path: Path, sessions_dir: Path, limit: int = 1000
) -> Iterator[Path]:
    """Get Codex session files matching the project root path.

    Returns a generator to avoid loading all paths into memory.
    Use limit to cap the number of files checked.
    """
    checked = 0
    for session_file in sessions_dir.rglob("*.jsonl"):
        if checked >= limit:
            break
        checked += 1

        try:
            with open(session_file) as f:
                first_line = f.readline()
                data = json.loads(first_line)

                if data.get("type") == "session_meta":
                    payload = data.get("payload", {})
                    cwd = payload.get("cwd", "")

                    if Path(cwd).resolve() == root_path.resolve():
                        yield session_file
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Skipping corrupt session file: {session_file}: {e}")
            continue


def detect_agent_type(session_dir: Path) -> AgentType:
    """Detect what type of AI agent created the sessions by inspecting .jsonl format."""
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

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning(f"Skipping unreadable session file: {jsonl_file}: {e}")
            continue

    return "unknown"
