"""TaintPath data model for representing taint flow paths."""

from typing import Any


class TaintPath:
    """Represents a taint flow path from source to sink."""

    def __init__(self, source: dict[str, Any], sink: dict[str, Any], path: list[dict[str, Any]]):
        self.source = source
        self.sink = sink
        self.path = path

        self.vulnerability_type = sink.get("vulnerability_type", "Data Exposure")

        self.flow_sensitive = False
        self.conditions = []
        self.condition_summary = ""
        self.path_complexity = 0
        self.tainted_vars = []
        self.sanitized_vars = []
        self.related_sources: list[dict[str, Any]] = []

        self.sanitizer_file: str | None = None
        self.sanitizer_line: int | None = None
        self.sanitizer_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization with guaranteed structure."""

        source_dict = self.source or {}
        source_dict.setdefault("name", "unknown_source")
        source_dict.setdefault("file", "unknown_file")
        source_dict.setdefault("line", 0)
        source_dict.setdefault("pattern", "unknown_pattern")

        sink_dict = self.sink or {}
        sink_dict.setdefault("name", "unknown_sink")
        sink_dict.setdefault("file", "unknown_file")
        sink_dict.setdefault("line", 0)
        sink_dict.setdefault("pattern", "unknown_pattern")

        result = {
            "source": source_dict,
            "sink": sink_dict,
            "path": self.path or [],
            "path_length": len(self.path) if self.path else 0,
            "vulnerability_type": self.vulnerability_type,
        }

        if self.flow_sensitive:
            result["flow_sensitive"] = self.flow_sensitive
            result["conditions"] = self.conditions
            result["condition_summary"] = self.condition_summary
            result["path_complexity"] = self.path_complexity
            result["tainted_vars"] = self.tainted_vars
            result["sanitized_vars"] = self.sanitized_vars

        if self.related_sources:
            result["related_sources"] = self.related_sources
            result["related_source_count"] = len(self.related_sources)
            result["unique_source_count"] = len(self.related_sources) + 1

        return result

    def add_related_path(self, other: TaintPath) -> None:
        """Attach additional source/path metadata that reaches the same sink."""
        related_entry = {
            "source": {
                "file": other.source.get("file"),
                "line": other.source.get("line"),
                "name": other.source.get("name"),
                "pattern": other.source.get("pattern"),
            },
            "path": other.path,
            "path_length": len(other.path) if other.path else 0,
            "flow_sensitive": other.flow_sensitive,
        }
        self.related_sources.append(related_entry)
