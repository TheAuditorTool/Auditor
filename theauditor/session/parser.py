"""Parse Claude Code session JSONL files into structured data."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ToolCall:
    """Represents a single tool invocation by the agent."""

    tool_name: str
    timestamp: str
    uuid: str
    input_params: dict[str, Any] = field(default_factory=dict)

    @property
    def datetime(self) -> datetime:
        """Parse ISO timestamp."""
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


@dataclass
class UserMessage:
    """Represents a user message in the conversation."""

    content: str
    timestamp: str
    uuid: str
    cwd: str
    git_branch: str

    @property
    def datetime(self) -> datetime:
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


@dataclass
class AssistantMessage:
    """Represents an assistant message (text + tool calls)."""

    timestamp: str
    uuid: str
    text_content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    tokens_used: dict[str, int] = field(default_factory=dict)

    @property
    def datetime(self) -> datetime:
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


@dataclass
class Session:
    """Represents a complete Claude Code conversation session."""

    session_id: str
    agent_id: str
    cwd: str
    git_branch: str
    user_messages: list[UserMessage] = field(default_factory=list)
    assistant_messages: list[AssistantMessage] = field(default_factory=list)

    @property
    def all_tool_calls(self) -> list[ToolCall]:
        """Flatten all tool calls from all assistant messages."""
        calls = []
        for msg in self.assistant_messages:
            calls.extend(msg.tool_calls)
        return calls

    @property
    def files_touched(self) -> dict[str, list[str]]:
        """Return files touched by each tool type."""
        touched = {}
        for call in self.all_tool_calls:
            if call.tool_name not in touched:
                touched[call.tool_name] = []

            file_path = (
                call.input_params.get("file_path")
                or call.input_params.get("path")
                or call.input_params.get("notebook_path")
            )
            if file_path:
                touched[call.tool_name].append(file_path)

        return touched


class SessionParser:
    """Parse Claude Code JSONL session logs."""

    def __init__(self, claude_dir: Path = None):
        """Initialize with Claude project directory."""
        if claude_dir is None:
            claude_dir = Path.home() / ".claude" / "projects"
        self.claude_dir = Path(claude_dir)

    def find_project_sessions(self, project_path: str) -> Path:
        """Find session directory for a given project path."""

        encoded_name = project_path.replace(":", "-").replace("\\", "-").replace("/", "-")
        session_dir = self.claude_dir / encoded_name

        if not session_dir.exists():
            encoded_name = project_path.replace("\\", "-")
            session_dir = self.claude_dir / encoded_name

        return session_dir

    def list_sessions(self, session_dir: Path) -> list[Path]:
        """List all JSONL session files in directory."""
        if not session_dir.exists():
            return []
        return sorted(session_dir.glob("*.jsonl"))

    def parse_session(self, jsonl_file: Path) -> Session:
        """Parse a single JSONL session file into structured Session object."""
        entries = []
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                entries.append(json.loads(line))

        if not entries:
            raise ValueError(f"Empty session file: {jsonl_file}")

        first_entry = entries[0]
        session = Session(
            session_id=first_entry.get("sessionId", ""),
            agent_id=first_entry.get("agentId", jsonl_file.stem),
            cwd=first_entry.get("cwd", ""),
            git_branch=first_entry.get("gitBranch", ""),
        )

        for entry in entries:
            entry_type = entry.get("type")

            if entry_type == "user":
                msg = entry.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        block.get("text", "") or block.get("source", {}).get("data", "")
                        for block in content
                        if isinstance(block, dict)
                    )

                session.user_messages.append(
                    UserMessage(
                        content=content,
                        timestamp=entry.get("timestamp", ""),
                        uuid=entry.get("uuid", ""),
                        cwd=entry.get("cwd", ""),
                        git_branch=entry.get("gitBranch", ""),
                    )
                )

            elif entry_type == "assistant":
                msg = entry.get("message", {})
                text_blocks = []
                tool_calls = []

                for block in msg.get("content", []):
                    block_type = block.get("type")

                    if block_type == "text":
                        text_blocks.append(block.get("text", ""))

                    elif block_type == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                tool_name=block.get("name", ""),
                                timestamp=entry.get("timestamp", ""),
                                uuid=block.get("id", ""),
                                input_params=block.get("input", {}),
                            )
                        )

                session.assistant_messages.append(
                    AssistantMessage(
                        timestamp=entry.get("timestamp", ""),
                        uuid=entry.get("uuid", ""),
                        text_content="\n".join(text_blocks),
                        tool_calls=tool_calls,
                        model=msg.get("model", ""),
                        tokens_used=msg.get("usage", {}),
                    )
                )

        return session

    def parse_all_sessions(self, session_dir: Path) -> list[Session]:
        """Parse all sessions in a directory."""
        sessions = []
        for jsonl_file in self.list_sessions(session_dir):
            try:
                sessions.append(self.parse_session(jsonl_file))
            except Exception as e:
                print(f"Warning: Failed to parse {jsonl_file.name}: {e}")
                continue
        return sessions


def load_session(jsonl_path: str | Path) -> Session:
    """Convenience function to load a single session."""
    parser = SessionParser()
    return parser.parse_session(Path(jsonl_path))


def load_project_sessions(project_path: str) -> list[Session]:
    """Load all sessions for a given project path."""
    parser = SessionParser()
    session_dir = parser.find_project_sessions(project_path)
    return list(parser.parse_all_sessions(session_dir))
