"""TaintPath data model for representing taint flow paths."""

from typing import Any


def determine_vulnerability_type(sink_pattern: str, source_pattern: str | None = None) -> str:
    """Determine vulnerability type from sink and source patterns.

    Centralized classification logic shared by IFDS and FlowResolver engines.
    Classification based on common sink patterns across Node.js/Python/React.
    """
    if not sink_pattern:
        return "Data Exposure"

    lower_sink = sink_pattern.lower()
    lower_source = (source_pattern or "").lower()

    xss_patterns = [
        "innerhtml",
        "outerhtml",
        "dangerouslysetinnerhtml",
        "insertadjacenthtml",
        "document.write",
        "document.writeln",
        "res.send",
        "res.render",
        "res.write",
        "response.write",
        "response.send",
        "sethtml",
        "v-html",
        "ng-bind-html",
        "__html",
        "createelement",
        "appendchild",
        "insertbefore",
    ]
    if any(p in lower_sink for p in xss_patterns):
        return "Cross-Site Scripting (XSS)"

    sql_patterns = [
        "query",
        "execute",
        "exec",
        "raw",
        "sequelize.query",
        "knex.raw",
        "prisma.$queryraw",
        "prisma.$executeraw",
        "cursor.execute",
        "conn.execute",
        "db.query",
        "pool.query",
        "client.query",
        "sql",
        "rawquery",
    ]
    if any(p in lower_sink for p in sql_patterns):
        return "SQL Injection"

    cmd_patterns = [
        "exec",
        "execsync",
        "spawn",
        "spawnsync",
        "child_process",
        "shellexecute",
        "popen",
        "system",
        "subprocess",
        "os.system",
        "os.popen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.popen",
        "eval",
        "function(",
        "new function",
    ]
    if any(p in lower_sink for p in cmd_patterns):
        if "eval" in lower_sink or "function(" in lower_sink:
            return "Code Injection"
        return "Command Injection"

    path_patterns = [
        "readfile",
        "writefile",
        "readfilesync",
        "writefilesync",
        "createreadstream",
        "createwritestream",
        "fs.read",
        "fs.write",
        "open(",
        "path.join",
        "path.resolve",
        "sendfile",
        "download",
        "unlink",
        "rmdir",
        "mkdir",
        "rename",
        "copy",
        "move",
    ]
    if any(p in lower_sink for p in path_patterns):
        return "Path Traversal"

    ssrf_patterns = [
        "fetch",
        "axios",
        "request",
        "http.get",
        "http.request",
        "https.get",
        "https.request",
        "urllib",
        "requests.get",
        "requests.post",
        "curl",
        "httpx",
    ]
    if any(p in lower_sink for p in ssrf_patterns):
        return "Server-Side Request Forgery (SSRF)"

    proto_patterns = [
        "__proto__",
        "constructor.prototype",
        "object.assign",
        "merge(",
        "extend(",
        "deepmerge",
        "lodash.merge",
        "$.extend",
    ]
    if any(p in lower_sink for p in proto_patterns):
        return "Prototype Pollution"

    log_patterns = [
        "console.log",
        "console.error",
        "console.warn",
        "logger.",
        "logging.",
        "log.info",
        "log.error",
        "log.debug",
    ]
    if any(p in lower_sink for p in log_patterns):
        return "Log Injection"

    redirect_patterns = [
        "redirect",
        "location.href",
        "location.assign",
        "location.replace",
        "res.redirect",
        "window.location",
    ]
    if any(p in lower_sink for p in redirect_patterns):
        return "Open Redirect"

    if (
        "req.body" in lower_source
        or "req.params" in lower_source
        or "req.query" in lower_source
    ):
        return "Unvalidated Input"
    if "user" in lower_source or "input" in lower_source:
        return "Unvalidated Input"

    return "Data Exposure"


class TaintPath:
    """Represents a taint flow path from source to sink."""

    def __init__(self, source: dict[str, Any], sink: dict[str, Any], path: list[dict[str, Any]]):
        self.source = source
        self.sink = sink
        self.path = path
        self.vulnerability_type = determine_vulnerability_type(
            sink.get("pattern", sink.get("name", "")),
            source.get("pattern", source.get("name", ""))
        )

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
