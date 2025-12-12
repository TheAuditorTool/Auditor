"""Parse Claude Code session JSONL files into structured data."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger


@dataclass
class ToolResult:
    """Represents the result of a tool invocation."""

    tool_use_id: str
    is_error: bool
    content: str
    timestamp: str

    @property
    def datetime(self) -> datetime:
        """Parse ISO timestamp."""
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


@dataclass
class ToolCall:
    """Represents a single tool invocation by the agent."""

    tool_name: str
    timestamp: str
    uuid: str
    input_params: dict[str, Any] = field(default_factory=dict)
    result: ToolResult | None = None

    @property
    def datetime(self) -> datetime:
        """Parse ISO timestamp."""
        return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))

    @property
    def succeeded(self) -> bool:
        """Check if tool call succeeded (has result and no error)."""
        return self.result is not None and not self.result.is_error

    @property
    def failed(self) -> bool:
        """Check if tool call failed (has result with error)."""
        return self.result is not None and self.result.is_error


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

        # Track tool calls by their ID to link results later
        tool_calls_by_id: dict[str, ToolCall] = {}

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

                # Check for tool result in this user entry
                tool_result_data = entry.get("toolUseResult")
                if tool_result_data:
                    self._link_tool_result(
                        tool_calls_by_id, tool_result_data, entry, msg
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
                        tool_call = ToolCall(
                            tool_name=block.get("name", ""),
                            timestamp=entry.get("timestamp", ""),
                            uuid=block.get("id", ""),
                            input_params=block.get("input", {}),
                        )
                        tool_calls.append(tool_call)
                        # Index by ID for result linking
                        if tool_call.uuid:
                            tool_calls_by_id[tool_call.uuid] = tool_call

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

    def _link_tool_result(
        self,
        tool_calls_by_id: dict[str, ToolCall],
        result_data: Any,
        entry: dict,
        msg: dict,
    ) -> None:
        """Link a tool result back to its corresponding tool call."""
        timestamp = entry.get("timestamp", "")

        # Handle different result formats
        if isinstance(result_data, str):
            # Error result is often just a string like "Error: File does not exist."
            is_error = result_data.startswith("Error") or "error" in result_data.lower()
            content = result_data

            # Try to find the tool call this result belongs to
            # Claude Code sends results with the message content containing tool_use_id
            tool_use_id = msg.get("content", [{}])[0].get("tool_use_id") if isinstance(
                msg.get("content"), list
            ) else None

            if tool_use_id and tool_use_id in tool_calls_by_id:
                tool_calls_by_id[tool_use_id].result = ToolResult(
                    tool_use_id=tool_use_id,
                    is_error=is_error,
                    content=content[:500],  # Truncate for memory
                    timestamp=timestamp,
                )
        elif isinstance(result_data, dict):
            # Structured result
            result_type = result_data.get("type", "")
            is_error = result_data.get("isError", False)

            # Extract content preview
            if result_type == "text" and "file" in result_data:
                file_info = result_data["file"]
                content = f"Read {file_info.get('filePath', 'unknown')} ({file_info.get('numLines', 0)} lines)"
                is_error = False
            elif "stdout" in result_data:
                content = result_data.get("stdout", "")[:200]
                stderr = result_data.get("stderr", "")
                if stderr:
                    is_error = True
                    content = stderr[:200]
            else:
                content = str(result_data)[:200]

            # Find corresponding tool call - check message content for tool_use_id
            tool_use_id = None
            msg_content = msg.get("content", [])
            if isinstance(msg_content, list) and msg_content:
                first_block = msg_content[0] if msg_content else {}
                if isinstance(first_block, dict):
                    tool_use_id = first_block.get("tool_use_id")

            if tool_use_id and tool_use_id in tool_calls_by_id:
                tool_calls_by_id[tool_use_id].result = ToolResult(
                    tool_use_id=tool_use_id,
                    is_error=is_error,
                    content=content,
                    timestamp=timestamp,
                )

    def parse_all_sessions(self, session_dir: Path) -> list[Session]:
        """Parse all sessions in a directory."""
        sessions = []
        for jsonl_file in self.list_sessions(session_dir):
            try:
                sessions.append(self.parse_session(jsonl_file))
            except Exception as e:
                logger.info(f"Warning: Failed to parse {jsonl_file.name}: {e}")
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
