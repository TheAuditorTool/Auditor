"""Journal system for tracking audit execution history."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger


class JournalWriter:
    """Writes execution events to persistent journal.ndjson file.

    The journal lives in .pf/ml/ which is preserved across runs (not archived).
    Events accumulate over time, providing a complete audit trail.
    """

    def __init__(self, journal_path: str = "./.pf/ml/journal.ndjson"):
        """Initialize journal writer.

        Raises:
            OSError: If journal file cannot be opened (permissions, disk space, etc.)
        """
        self.journal_path = Path(journal_path).resolve()
        self.session_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

        self.file_handle = open(self.journal_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115

    def write_event(self, event_type: str, data: dict[str, Any]) -> bool:
        """Write an event to the journal.

        Trust the state - if we're here, file_handle exists (enforced by __init__).
        If write fails, let it crash. Silent journal failures corrupt audit trail.
        """
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            **data,
        }

        json.dump(event, self.file_handle)
        self.file_handle.write("\n")
        self.file_handle.flush()
        return True

    def phase_start(self, phase_name: str, command: str, phase_num: int = 0) -> bool:
        """Record the start of a pipeline phase."""
        return self.write_event(
            "phase_start", {"phase": phase_name, "command": command, "phase_num": phase_num}
        )

    def phase_end(
        self,
        phase_name: str,
        success: bool,
        elapsed: float,
        exit_code: int = 0,
        error_msg: str | None = None,
    ) -> bool:
        """Record the end of a pipeline phase."""
        return self.write_event(
            "phase_end",
            {
                "phase": phase_name,
                "result": "success" if success else "fail",
                "elapsed": elapsed,
                "exit_code": exit_code,
                "error": error_msg,
            },
        )

    def file_touch(
        self, file_path: str, operation: str = "analyze", success: bool = True, findings: int = 0
    ) -> bool:
        """Record a file being touched/analyzed."""
        return self.write_event(
            "file_touch",
            {
                "file": file_path,
                "operation": operation,
                "result": "success" if success else "fail",
                "findings": findings,
            },
        )

    def finding(
        self, file_path: str, severity: str, category: str, message: str, line: int | None = None
    ) -> bool:
        """Record a specific finding/issue."""
        return self.write_event(
            "finding",
            {
                "file": file_path,
                "severity": severity,
                "category": category,
                "message": message,
                "line": line,
            },
        )

    def apply_patch(
        self, file_path: str, success: bool, patch_type: str = "fix", error_msg: str | None = None
    ) -> bool:
        """Record a patch/fix being applied to a file."""
        return self.write_event(
            "apply_patch",
            {
                "file": file_path,
                "result": "success" if success else "fail",
                "patch_type": patch_type,
                "error": error_msg,
            },
        )

    def pipeline_summary(
        self,
        total_phases: int,
        failed_phases: int,
        total_files: int,
        total_findings: int,
        elapsed: float,
        status: str = "complete",
    ) -> bool:
        """Record pipeline execution summary."""
        return self.write_event(
            "pipeline_summary",
            {
                "total_phases": total_phases,
                "failed_phases": failed_phases,
                "total_files": total_files,
                "total_findings": total_findings,
                "elapsed": elapsed,
                "status": status,
            },
        )

    def close(self):
        """Close the journal file handle."""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close journal."""
        self.close()


class JournalReader:
    """Reads and queries the persistent journal.ndjson file."""

    def __init__(self, journal_path: str = "./.pf/ml/journal.ndjson"):
        """Initialize journal reader."""
        self.journal_path = Path(journal_path)

    def read_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read events from journal with optional filtering."""
        if not self.journal_path.exists():
            return []

        events = []
        try:
            with open(self.journal_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)

                        if event_type and event.get("event_type") != event_type:
                            continue

                        if session_id and event.get("session_id") != session_id:
                            continue

                        if since:
                            event_time = datetime.fromisoformat(event.get("timestamp", ""))
                            if event_time < since:
                                continue

                        events.append(event)

                    except json.JSONDecodeError:
                        logger.warning(f"Skipping malformed JSON at line {line_num}")
                        continue

        except Exception as e:
            logger.warning(f"Error reading journal: {e}")

        return events

    def get_file_stats(self) -> dict[str, dict[str, int]]:
        """Get statistics for file touches and failures."""
        stats = {}

        for event in self.read_events(event_type="file_touch"):
            file_path = event.get("file", "")
            if not file_path:
                continue

            if file_path not in stats:
                stats[file_path] = {"touches": 0, "failures": 0, "successes": 0, "findings": 0}

            stats[file_path]["touches"] += 1

            if event.get("result") == "fail":
                stats[file_path]["failures"] += 1
            else:
                stats[file_path]["successes"] += 1

            stats[file_path]["findings"] += event.get("findings", 0)

        for event in self.read_events(event_type="apply_patch"):
            file_path = event.get("file", "")
            if not file_path:
                continue

            if file_path not in stats:
                stats[file_path] = {"touches": 0, "failures": 0, "successes": 0, "findings": 0}

            stats[file_path]["touches"] += 1

            if event.get("result") == "fail":
                stats[file_path]["failures"] += 1
            else:
                stats[file_path]["successes"] += 1

        return stats

    def get_phase_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for pipeline phases."""
        stats = {}

        for event in self.read_events(event_type="phase_start"):
            phase = event.get("phase", "")
            if not phase:
                continue

            if phase not in stats:
                stats[phase] = {
                    "executions": 0,
                    "failures": 0,
                    "total_elapsed": 0.0,
                    "last_executed": None,
                }

            stats[phase]["executions"] += 1
            stats[phase]["last_executed"] = event.get("timestamp")

        for event in self.read_events(event_type="phase_end"):
            phase = event.get("phase", "")
            if not phase or phase not in stats:
                continue

            if event.get("result") == "fail":
                stats[phase]["failures"] += 1

            stats[phase]["total_elapsed"] += event.get("elapsed", 0.0)

        return stats

    def get_recent_failures(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent failure events."""
        failures = []

        for event in self.read_events():
            if event.get("result") == "fail" or event.get("event_type") == "error":
                failures.append(event)

        failures.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return failures[:limit]


def get_journal_writer(run_type: str = "full") -> JournalWriter:
    """Get a journal writer for the current run.

    Journal is persistent in .pf/ml/ - not archived between runs.
    The run_type parameter is kept for API compatibility but unused.
    """
    return JournalWriter()


def integrate_with_pipeline(pipeline_func):
    """Decorator to integrate journal writing with pipeline execution."""

    def wrapper(*args, **kwargs):
        journal = kwargs.pop("journal", None)
        close_journal = False

        if journal is None:
            journal = get_journal_writer(kwargs.get("run_type", "full"))
            close_journal = True

        try:
            kwargs["journal"] = journal

            result = pipeline_func(*args, **kwargs)

            if isinstance(result, dict):
                journal.pipeline_summary(
                    total_phases=result.get("total_phases", 0),
                    failed_phases=result.get("failed_phases", 0),
                    total_files=len(result.get("created_files", [])),
                    total_findings=result.get("findings", {}).get("total_vulnerabilities", 0),
                    elapsed=result.get("elapsed_time", 0.0),
                    status="complete" if result.get("success") else "failed",
                )

            return result

        finally:
            if close_journal:
                journal.close()

    return wrapper
