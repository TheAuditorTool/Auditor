"""Python Deserialization Vulnerability Analyzer - Detects pickle, YAML, marshal, and XXE issues."""

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="python_deserialization",
    category="deserialization",
    target_extensions=[".py"],
    exclude_patterns=[
        "node_modules/",
        "vendor/",
        ".venv/",
        "__pycache__/",
    ],
    execution_scope="database",
    primary_table="function_call_args",
)


PICKLE_METHODS = frozenset(
    [
        "pickle.load",
        "pickle.loads",
        "pickle.Unpickler",
        "cPickle.load",
        "cPickle.loads",
        "cPickle.Unpickler",
        "dill.load",
        "dill.loads",
        "cloudpickle.load",
        "cloudpickle.loads",
    ]
)


YAML_UNSAFE = frozenset(
    [
        "yaml.load",
        "yaml.full_load",
        "yaml.unsafe_load",
        "yaml.UnsafeLoader",
        "yaml.FullLoader",
        "yaml.Loader",
    ]
)


MARSHAL_METHODS = frozenset(
    [
        "marshal.load",
        "marshal.loads",
        "marshal.dump",
        "marshal.dumps",
    ]
)


SHELVE_METHODS = frozenset(
    [
        "shelve.open",
        "shelve.DbfilenameShelf",
        "shelve.Shelf",
    ]
)


JSON_DANGEROUS = frozenset(
    [
        "object_hook",
        "object_pairs_hook",
        "cls=",
    ]
)


DJANGO_SESSION = frozenset(
    [
        "django.contrib.sessions.serializers.PickleSerializer",
        "PickleSerializer",
        "session.get_decoded",
        "signing.loads",
    ]
)


FLASK_SESSION = frozenset(
    [
        "flask.session",
        "SecureCookie.unserialize",
        "session.loads",
    ]
)


XML_UNSAFE = frozenset(
    [
        "etree.parse",
        "etree.fromstring",
        "etree.XMLParser",
        "xml.dom.minidom.parse",
        "xml.dom.minidom.parseString",
        "xml.sax.parse",
        "ElementTree.parse",
        "ElementTree.fromstring",
    ]
)


NETWORK_SOURCES = frozenset(
    [
        "request.data",
        "request.get_data",
        "request.files",
        "request.form",
        "request.json",
        "request.values",
        "socket.recv",
        "socket.recvfrom",
        "urlopen",
        "requests.get",
        "requests.post",
        "response.content",
        "redis.get",
        "cache.get",
        "memcache.get",
    ]
)


FILE_SOURCES = frozenset(
    [
        "open",
        "file.read",
        "Path.read_bytes",
        "Path.read_text",
        "io.BytesIO",
        "io.StringIO",
        "tempfile",
    ]
)


BASE64_PATTERNS = frozenset(
    [
        "b64decode",
        "base64.b64decode",
        "base64.decode",
        "base64.standard_b64decode",
        "base64.urlsafe_b64decode",
        "decodebytes",
        "decodestring",
    ]
)


TAR_UNSAFE = frozenset(
    [
        "extractall",
        "tarfile.extractall",
        "TarFile.extractall",
        "tar.extractall",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Python deserialization vulnerabilities.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []
        seen: set[str] = set()

        def add_finding(
            file: str,
            line: int,
            rule_name: str,
            message: str,
            severity: Severity,
            confidence: Confidence = Confidence.HIGH,
            cwe_id: str | None = None,
        ) -> None:
            """Add a finding if not already seen."""
            key = f"{file}:{line}:{rule_name}"
            if key in seen:
                return
            seen.add(key)

            findings.append(
                StandardFinding(
                    rule_name=rule_name,
                    message=message,
                    file_path=file,
                    line=line,
                    severity=severity,
                    category=METADATA.category,
                    confidence=confidence,
                    cwe_id=cwe_id,
                )
            )

        _check_pickle_usage(db, add_finding)
        _check_yaml_unsafe(db, add_finding)
        _check_marshal_shelve(db, add_finding)
        _check_json_exploitation(db, add_finding)
        _check_django_flask_sessions(db, add_finding)
        _check_xml_xxe(db, add_finding)
        _check_base64_pickle_combo(db, add_finding)
        _check_pickle_imports(db, add_finding)
        _check_tar_slip(db, add_finding)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_pickle_usage(db: RuleDB, add_finding) -> None:
    """Detect pickle usage - CRITICAL remote code execution vulnerability."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr", "caller_function")
        .where_in("callee_function", list(PICKLE_METHODS))
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args, _caller = row[0], row[1], row[2], row[3], row[4]

        data_source = _check_data_source(db, file, line, args)

        if data_source == "network":
            add_finding(
                file=file,
                line=line,
                rule_name="python-pickle-deserialization",
                message=f"CRITICAL: Pickle {method} with network data - remote code execution",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-502",
            )
        elif data_source == "file":
            add_finding(
                file=file,
                line=line,
                rule_name="python-pickle-deserialization",
                message=f"Pickle {method} with file data - code execution risk",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-502",
            )
        else:
            add_finding(
                file=file,
                line=line,
                rule_name="python-pickle-deserialization",
                message=f"Unsafe deserialization with {method}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-502",
            )


def _check_yaml_unsafe(db: RuleDB, add_finding) -> None:
    """Detect unsafe YAML loading - arbitrary object instantiation."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(YAML_UNSAFE))
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        if args and "SafeLoader" in str(args):
            continue

        data_source = _check_data_source(db, file, line, args)
        severity = Severity.CRITICAL if data_source == "network" else Severity.HIGH

        add_finding(
            file=file,
            line=line,
            rule_name="python-yaml-unsafe-load",
            message=f"Unsafe YAML loading with {method} - code execution risk",
            severity=severity,
            confidence=Confidence.HIGH,
            cwe_id="CWE-502",
        )


def _check_marshal_shelve(db: RuleDB, add_finding) -> None:
    """Detect marshal and shelve usage - bytecode execution risk."""

    marshal_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where_in("callee_function", list(MARSHAL_METHODS))
        .order_by("file, line")
    )

    for row in marshal_rows:
        file, line, method = row[0], row[1], row[2]
        add_finding(
            file=file,
            line=line,
            rule_name="python-marshal-usage",
            message=f"Marshal {method} can execute arbitrary bytecode",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            cwe_id="CWE-502",
        )

    shelve_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where_in("callee_function", list(SHELVE_METHODS))
        .order_by("file, line")
    )

    for row in shelve_rows:
        file, line, method = row[0], row[1], row[2]
        add_finding(
            file=file,
            line=line,
            rule_name="python-shelve-usage",
            message=f"Shelve {method} uses pickle internally - code execution risk",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            cwe_id="CWE-502",
        )


def _check_json_exploitation(db: RuleDB, add_finding) -> None:
    """Detect potentially exploitable JSON parsing with custom object hooks."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", ["json.loads", "json.load", "loads", "load"])
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        if not args:
            continue

        args_str = str(args)
        has_object_hook = any(hook in args_str for hook in JSON_DANGEROUS)

        if has_object_hook:
            add_finding(
                file=file,
                line=line,
                rule_name="python-json-object-hook",
                message=f"JSON {method} with object_hook can be exploited",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-502",
            )


def _check_django_flask_sessions(db: RuleDB, add_finding) -> None:
    """Detect unsafe session deserialization in Django/Flask."""

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        is_django_pickle = method in DJANGO_SESSION or (args and "PickleSerializer" in str(args))

        if is_django_pickle:
            add_finding(
                file=file,
                line=line,
                rule_name="python-django-pickle-session",
                message="Django PickleSerializer for sessions is unsafe",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-502",
            )

    flask_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(FLASK_SESSION))
        .order_by("file, line")
    )

    for row in flask_rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        method_lower = method.lower() if method else ""
        args_lower = str(args).lower() if args else ""

        if "pickle" in method_lower or "pickle" in args_lower:
            add_finding(
                file=file,
                line=line,
                rule_name="python-flask-unsafe-session",
                message="Flask session using unsafe deserialization",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-502",
            )


def _check_xml_xxe(db: RuleDB, add_finding) -> None:
    """Detect XML external entity (XXE) vulnerabilities."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where_in("callee_function", list(XML_UNSAFE))
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        if args and "resolve_entities=False" in str(args):
            continue

        add_finding(
            file=file,
            line=line,
            rule_name="python-xml-xxe",
            message=f"XML parsing with {method} vulnerable to XXE attacks",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            cwe_id="CWE-611",
        )


def _check_base64_pickle_combo(db: RuleDB, add_finding) -> None:
    """Detect base64-encoded pickle - common attack pattern to bypass filters."""

    base64_calls = list(
        db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function")
            .where_in("callee_function", list(BASE64_PATTERNS))
            .order_by("file, line")
        )
    )

    if not base64_calls:
        return

    all_rows = db.query(Q("function_call_args").select("file", "line", "callee_function"))

    findings_set: set[tuple[str, int]] = set()

    for b64_row in base64_calls:
        b64_file, b64_line = b64_row[0], b64_row[1]

        for call_row in all_rows:
            call_file, call_line, call_method = call_row[0], call_row[1], call_row[2]

            if call_file != b64_file:
                continue
            if not (b64_line <= call_line <= b64_line + 5):
                continue
            if not call_method:
                continue

            call_lower = call_method.lower()
            if "pickle.load" in call_lower or call_method.endswith("loads"):
                findings_set.add((b64_file, b64_line))

    for file, line in findings_set:
        add_finding(
            file=file,
            line=line,
            rule_name="python-base64-pickle",
            message="Base64-encoded pickle detected - common attack vector",
            severity=Severity.CRITICAL,
            confidence=Confidence.HIGH,
            cwe_id="CWE-502",
        )


def _check_pickle_imports(db: RuleDB, add_finding) -> None:
    """Flag pickle module imports as a code smell."""
    rows = db.query(Q("refs").select("src", "line", "value"))

    pickle_files: set[tuple[str, int]] = set()
    for row in rows:
        src, line, value = row[0], row[1], row[2]
        if not value:
            continue

        if value in ("pickle", "cPickle", "dill", "cloudpickle"):
            pickle_files.add((src, line))

    for file, import_line in pickle_files:
        usage_rows = db.query(
            Q("function_call_args").select("callee_function").where("file = ?", file)
        )

        has_pickle_usage = any("pickle" in str(row[0]).lower() for row in usage_rows if row[0])

        if not has_pickle_usage:
            add_finding(
                file=file,
                line=import_line,
                rule_name="python-pickle-import",
                message="Pickle module imported - consider safer alternatives",
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                cwe_id="CWE-502",
            )


def _check_data_source(db: RuleDB, file: str, line: int, args: str | None) -> str:
    """Determine if data comes from network, file, or unknown source."""
    if not args:
        return "unknown"

    args_str = str(args)

    for source in NETWORK_SOURCES:
        if source in args_str:
            return "network"

    for source in FILE_SOURCES:
        if source in args_str:
            return "file"

    rows = db.query(
        Q("function_call_args")
        .select("callee_function")
        .where("file = ? AND line >= ? AND line <= ?", file, line - 10, line)
        .order_by("line DESC")
    )

    for row in rows:
        callee = row[0]
        if not callee:
            continue

        if any(net in callee for net in NETWORK_SOURCES):
            return "network"
        if any(f in callee for f in FILE_SOURCES):
            return "file"

    return "unknown"


def _check_tar_slip(db: RuleDB, add_finding) -> None:
    """Detect TarSlip vulnerability (CVE-2007-4559).

    tarfile.extractall() without 'members' filter allows path traversal.
    Attackers can craft tar files with paths like '../../etc/passwd' to
    write files outside the target directory.
    """
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ?", "%extractall%")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]

        args_str = str(args) if args else ""
        if "members=" in args_str or "members =" in args_str:
            continue

        if "filter=" in args_str:
            continue

        add_finding(
            file=file,
            line=line,
            rule_name="python-tar-slip",
            message=f"tarfile {method} without 'members' filter - path traversal vulnerability (CVE-2007-4559)",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            cwe_id="CWE-22",
        )
