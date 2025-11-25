"""Journal system for tracking audit execution history.

This module provides functionality to write and read execution journals in NDJSON format.
The journal tracks all pipeline events, file touches, and results for ML training.
"""


import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


class JournalWriter:
    """Writes execution events to journal.ndjson file."""

    def __init__(self, journal_path: str = "./.pf/journal.ndjson", history_dir: str | None = None):
        """Initialize journal writer.
        
        Args:
            journal_path: Path to the journal file
            history_dir: Optional history directory for archival copies
        """
        self.journal_path = Path(journal_path)
        self.history_dir = Path(history_dir) if history_dir else None
        self.session_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        # Ensure parent directory exists
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

        # Open file in append mode for continuous writing
        self.file_handle = None
        self._open_journal()

    def _open_journal(self):
        """Open journal file for writing."""
        try:
            self.file_handle = open(self.journal_path, 'a', encoding='utf-8', buffering=1)
        except Exception as e:
            print(f"[WARNING] Could not open journal file {self.journal_path}: {e}")
            self.file_handle = None

    def write_event(self, event_type: str, data: dict[str, Any]) -> bool:
        """Write an event to the journal.
        
        Args:
            event_type: Type of event (phase, file_touch, result, error, etc.)
            data: Event data dictionary
            
        Returns:
            True if written successfully, False otherwise
        """
        if not self.file_handle:
            return False

        try:
            event = {
                "timestamp": datetime.now(UTC).isoformat(),
                "session_id": self.session_id,
                "event_type": event_type,
                **data
            }

            # Write as NDJSON (one JSON object per line)
            json.dump(event, self.file_handle)
            self.file_handle.write('\n')
            self.file_handle.flush()  # Force write to disk
            return True

        except Exception as e:
            print(f"[WARNING] Failed to write journal event: {e}")
            return False

    def phase_start(self, phase_name: str, command: str, phase_num: int = 0) -> bool:
        """Record the start of a pipeline phase.
        
        Args:
            phase_name: Human-readable phase name
            command: Command being executed
            phase_num: Phase number in sequence
        """
        return self.write_event("phase_start", {
            "phase": phase_name,
            "command": command,
            "phase_num": phase_num
        })

    def phase_end(self, phase_name: str, success: bool, elapsed: float, 
                  exit_code: int = 0, error_msg: str | None = None) -> bool:
        """Record the end of a pipeline phase.
        
        Args:
            phase_name: Human-readable phase name
            success: Whether phase succeeded
            elapsed: Execution time in seconds
            exit_code: Process exit code
            error_msg: Optional error message
        """
        return self.write_event("phase_end", {
            "phase": phase_name,
            "result": "success" if success else "fail",
            "elapsed": elapsed,
            "exit_code": exit_code,
            "error": error_msg
        })

    def file_touch(self, file_path: str, operation: str = "analyze", 
                   success: bool = True, findings: int = 0) -> bool:
        """Record a file being touched/analyzed.
        
        Args:
            file_path: Path to the file
            operation: Type of operation (analyze, modify, create, etc.)
            success: Whether operation succeeded
            findings: Number of findings/issues found
        """
        return self.write_event("file_touch", {
            "file": file_path,
            "operation": operation,
            "result": "success" if success else "fail",
            "findings": findings
        })

    def finding(self, file_path: str, severity: str, category: str, 
                message: str, line: int | None = None) -> bool:
        """Record a specific finding/issue.
        
        Args:
            file_path: File where finding was detected
            severity: Severity level (critical, high, medium, low)
            category: Category of finding
            message: Finding message
            line: Optional line number
        """
        return self.write_event("finding", {
            "file": file_path,
            "severity": severity,
            "category": category,
            "message": message,
            "line": line
        })

    def apply_patch(self, file_path: str, success: bool, 
                    patch_type: str = "fix", error_msg: str | None = None) -> bool:
        """Record a patch/fix being applied to a file.
        
        Args:
            file_path: File being patched
            success: Whether patch succeeded
            patch_type: Type of patch (fix, refactor, update, etc.)
            error_msg: Optional error message
        """
        return self.write_event("apply_patch", {
            "file": file_path,
            "result": "success" if success else "fail",
            "patch_type": patch_type,
            "error": error_msg
        })

    def pipeline_summary(self, total_phases: int, failed_phases: int,
                        total_files: int, total_findings: int,
                        elapsed: float, status: str = "complete") -> bool:
        """Record pipeline execution summary.
        
        Args:
            total_phases: Total number of phases executed
            failed_phases: Number of failed phases
            total_files: Total files analyzed
            total_findings: Total findings detected
            elapsed: Total execution time
            status: Overall status (complete, partial, failed)
        """
        return self.write_event("pipeline_summary", {
            "total_phases": total_phases,
            "failed_phases": failed_phases,
            "total_files": total_files,
            "total_findings": total_findings,
            "elapsed": elapsed,
            "status": status
        })

    def close(self, copy_to_history: bool = True):
        """Close the journal file and optionally copy to history.
        
        Args:
            copy_to_history: Whether to copy journal to history directory
        """
        if self.file_handle:
            try:
                self.file_handle.close()
            except:
                pass
            self.file_handle = None

        # Copy to history if requested and history_dir is set
        if copy_to_history and self.history_dir and self.journal_path.exists():
            try:
                import shutil
                self.history_dir.mkdir(parents=True, exist_ok=True)
                dest_path = self.history_dir / f"journal_{self.session_id}.ndjson"
                shutil.copy2(self.journal_path, dest_path)
                print(f"[INFO] Journal copied to history: {dest_path}")
            except Exception as e:
                print(f"[WARNING] Could not copy journal to history: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close journal."""
        self.close()


class JournalReader:
    """Reads and queries journal.ndjson files."""

    def __init__(self, journal_path: str = "./.pf/journal.ndjson"):
        """Initialize journal reader.
        
        Args:
            journal_path: Path to the journal file
        """
        self.journal_path = Path(journal_path)

    def read_events(self, event_type: str | None = None,
                    since: datetime | None = None,
                    session_id: str | None = None) -> list[dict[str, Any]]:
        """Read events from journal with optional filtering.
        
        Args:
            event_type: Filter by event type
            since: Only events after this timestamp
            session_id: Filter by session ID
            
        Returns:
            List of matching events
        """
        if not self.journal_path.exists():
            return []

        events = []
        try:
            with open(self.journal_path, encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)

                        # Apply filters
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
                        print(f"[WARNING] Skipping malformed JSON at line {line_num}")
                        continue

        except Exception as e:
            print(f"[WARNING] Error reading journal: {e}")

        return events

    def get_file_stats(self) -> dict[str, dict[str, int]]:
        """Get statistics for file touches and failures.
        
        Returns:
            Dict mapping file paths to stats (touches, failures, successes)
        """
        stats = {}

        for event in self.read_events(event_type="file_touch"):
            file_path = event.get("file", "")
            if not file_path:
                continue

            if file_path not in stats:
                stats[file_path] = {
                    "touches": 0,
                    "failures": 0,
                    "successes": 0,
                    "findings": 0
                }

            stats[file_path]["touches"] += 1

            if event.get("result") == "fail":
                stats[file_path]["failures"] += 1
            else:
                stats[file_path]["successes"] += 1

            stats[file_path]["findings"] += event.get("findings", 0)

        # Also count apply_patch events
        for event in self.read_events(event_type="apply_patch"):
            file_path = event.get("file", "")
            if not file_path:
                continue

            if file_path not in stats:
                stats[file_path] = {
                    "touches": 0,
                    "failures": 0, 
                    "successes": 0,
                    "findings": 0
                }

            stats[file_path]["touches"] += 1

            if event.get("result") == "fail":
                stats[file_path]["failures"] += 1
            else:
                stats[file_path]["successes"] += 1

        return stats

    def get_phase_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for pipeline phases.
        
        Returns:
            Dict mapping phase names to execution stats
        """
        stats = {}

        # Track phase starts
        for event in self.read_events(event_type="phase_start"):
            phase = event.get("phase", "")
            if not phase:
                continue

            if phase not in stats:
                stats[phase] = {
                    "executions": 0,
                    "failures": 0,
                    "total_elapsed": 0.0,
                    "last_executed": None
                }

            stats[phase]["executions"] += 1
            stats[phase]["last_executed"] = event.get("timestamp")

        # Track phase ends
        for event in self.read_events(event_type="phase_end"):
            phase = event.get("phase", "")
            if not phase or phase not in stats:
                continue

            if event.get("result") == "fail":
                stats[phase]["failures"] += 1

            stats[phase]["total_elapsed"] += event.get("elapsed", 0.0)

        return stats

    def get_recent_failures(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent failure events.
        
        Args:
            limit: Maximum number of failures to return
            
        Returns:
            List of recent failure events
        """
        failures = []

        # Get all failure events
        for event in self.read_events():
            if event.get("result") == "fail" or event.get("event_type") == "error":
                failures.append(event)

        # Sort by timestamp (most recent first)
        failures.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return failures[:limit]


# Integration functions for pipeline
def get_journal_writer(run_type: str = "full") -> "JournalWriter":
    """Get a journal writer for the current run.
    
    Args:
        run_type: Type of run (full, diff, etc.)
        
    Returns:
        JournalWriter instance
    """
    # Determine history directory based on run type
    history_dir = Path("./.pf/history") / run_type / datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    return JournalWriter(
        journal_path="./.pf/journal.ndjson",
        history_dir=str(history_dir)
    )


def integrate_with_pipeline(pipeline_func):
    """Decorator to integrate journal writing with pipeline execution.
    
    This decorator wraps pipeline functions to automatically write journal events.
    """
    def wrapper(*args, **kwargs):
        # Get or create journal writer
        journal = kwargs.pop('journal', None)
        close_journal = False

        if journal is None:
            journal = get_journal_writer(kwargs.get('run_type', 'full'))
            close_journal = True

        try:
            # Inject journal into kwargs
            kwargs['journal'] = journal

            # Execute pipeline
            result = pipeline_func(*args, **kwargs)

            # Write summary if available
            if isinstance(result, dict):
                journal.pipeline_summary(
                    total_phases=result.get('total_phases', 0),
                    failed_phases=result.get('failed_phases', 0),
                    total_files=len(result.get('created_files', [])),
                    total_findings=result.get('findings', {}).get('total_vulnerabilities', 0),
                    elapsed=result.get('elapsed_time', 0.0),
                    status='complete' if result.get('success') else 'failed'
                )

            return result

        finally:
            if close_journal:
                journal.close()

    return wrapper