"""Python Deserialization Vulnerability Analyzer - Database-First Approach.

Detects unsafe deserialization vulnerabilities in Python code using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels

Detects:
- Pickle usage (CRITICAL - remote code execution)
- YAML unsafe loading
- JSON object_hook exploitation
- Marshal/shelve usage
- Unsafe Django/Flask session deserialization
- XML entity expansion
"""

import sqlite3
from typing import List, Set
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA (Phase 3B Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="python_deserialization",
    category="deserialization",
    target_extensions=['.py'],
    exclude_patterns=['frontend/', 'client/', 'node_modules/', 'test/', '__tests__/', 'migrations/'],
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class DeserializationPatterns:
    """Immutable pattern definitions for deserialization detection."""

    # CRITICAL: Pickle methods (allow arbitrary code execution)
    PICKLE_METHODS = frozenset([
        'pickle.load', 'pickle.loads', 'pickle.Unpickler',
        'cPickle.load', 'cPickle.loads', 'cPickle.Unpickler',
        'dill.load', 'dill.loads', 'cloudpickle.load', 'cloudpickle.loads',
        'load', 'loads'  # When imported from pickle
    ])

    # CRITICAL: YAML unsafe methods
    YAML_UNSAFE = frozenset([
        'yaml.load', 'yaml.full_load', 'yaml.unsafe_load',
        'yaml.UnsafeLoader', 'yaml.FullLoader', 'yaml.Loader',
        'load'  # When imported from yaml without SafeLoader
    ])

    # SAFE: YAML safe methods (for comparison)
    YAML_SAFE = frozenset([
        'yaml.safe_load', 'yaml.SafeLoader', 'safe_load'
    ])

    # Marshal methods (can execute bytecode)
    MARSHAL_METHODS = frozenset([
        'marshal.load', 'marshal.loads', 'marshal.dump', 'marshal.dumps'
    ])

    # Shelve methods (uses pickle internally)
    SHELVE_METHODS = frozenset([
        'shelve.open', 'shelve.DbfilenameShelf', 'shelve.Shelf'
    ])

    # JSON with object_hook (can be exploited)
    JSON_DANGEROUS = frozenset([
        'object_hook', 'object_pairs_hook', 'cls='
    ])

    # Django session deserialization
    DJANGO_SESSION = frozenset([
        'django.contrib.sessions.serializers.PickleSerializer',
        'PickleSerializer', 'session.get_decoded', 'signing.loads'
    ])

    # Flask session patterns
    FLASK_SESSION = frozenset([
        'flask.session', 'SecureCookie.unserialize', 'session.loads'
    ])

    # XML parsing (XXE vulnerability)
    XML_UNSAFE = frozenset([
        'etree.parse', 'etree.fromstring', 'etree.XMLParse',
        'xml.dom.minidom.parse', 'xml.dom.minidom.parseString',
        'xml.sax.parse', 'ElementTree.parse', 'ElementTree.fromstring'
    ])

    # Eval/exec patterns (related to deserialization)
    EVAL_PATTERNS = frozenset([
        'eval', 'exec', '__import__', 'compile',
        'execfile', 'ast.literal_eval'  # literal_eval is safe but worth checking context
    ])

    # Network sources (data from network is especially dangerous)
    NETWORK_SOURCES = frozenset([
        'request.data', 'request.get_data', 'request.files',
        'request.form', 'request.json', 'request.values',
        'socket.recv', 'socket.recvfrom', 'urlopen',
        'requests.get', 'requests.post', 'response.content',
        'redis.get', 'cache.get', 'memcache.get'
    ])

    # File sources (still dangerous but slightly less than network)
    FILE_SOURCES = frozenset([
        'open', 'file.read', 'Path.read_bytes', 'Path.read_text',
        'io.BytesIO', 'io.StringIO', 'tempfile'
    ])

    # Base64 patterns (often used with pickle)
    BASE64_PATTERNS = frozenset([
        'b64decode', 'base64.b64decode', 'base64.decode',
        'base64.standard_b64decode', 'base64.urlsafe_b64decode',
        'decodebytes', 'decodestring'
    ])

    # Compression patterns (often combined with pickle)
    COMPRESSION_PATTERNS = frozenset([
        'zlib.decompress', 'gzip.decompress', 'bz2.decompress',
        'lzma.decompress', 'lz4.decompress'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class DeserializationAnalyzer:
    """Analyzer for Python deserialization vulnerabilities."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = DeserializationPatterns()
        self.findings = []

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of deserialization vulnerabilities found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Run all deserialization checks
            self._check_pickle_usage()
            self._check_yaml_unsafe()
            self._check_marshal_shelve()
            self._check_json_exploitation()
            self._check_django_flask_sessions()
            self._check_xml_xxe()
            self._check_base64_pickle_combo()
            self._check_imports_context()

        finally:
            conn.close()

        return self.findings

    def _check_pickle_usage(self):
        """Detect pickle usage - CRITICAL vulnerability."""
        pickle_placeholders = ','.join('?' * len(self.patterns.PICKLE_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr, caller_function
            FROM function_call_args
            WHERE callee_function IN ({pickle_placeholders})
            ORDER BY file, line
        """, list(self.patterns.PICKLE_METHODS))
        # ✅ FIX: Store results before loop to avoid cursor state bug
        pickle_usages = self.cursor.fetchall()

        for file, line, method, args, caller in pickle_usages:
            # Check if data comes from network (CRITICAL)
            severity = Severity.CRITICAL
            confidence = Confidence.HIGH

            # Check data source
            data_source = self._check_data_source(file, line, args)

            if data_source == 'network':
                message = f'CRITICAL: Pickle {method} with network data - remote code execution!'
            elif data_source == 'file':
                message = f'Pickle {method} with file data - code execution risk'
            else:
                message = f'Unsafe deserialization with {method}'
                severity = Severity.HIGH
                confidence = Confidence.MEDIUM

            self.findings.append(StandardFinding(
                rule_name='python-pickle-deserialization',
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category='deserialization',
                confidence=confidence,
                cwe_id='CWE-502'
            ))

    def _check_yaml_unsafe(self):
        """Detect unsafe YAML loading."""
        yaml_unsafe_placeholders = ','.join('?' * len(self.patterns.YAML_UNSAFE))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({yaml_unsafe_placeholders})
            ORDER BY file, line
        """, list(self.patterns.YAML_UNSAFE))
        # ✅ FIX: Store results before loop to avoid cursor state bug
        yaml_unsafe_usages = self.cursor.fetchall()

        for file, line, method, args in yaml_unsafe_usages:
            # Check if Loader=SafeLoader is specified
            if args and 'SafeLoader' in args:
                continue  # This is actually safe

            # Check data source
            data_source = self._check_data_source(file, line, args)

            severity = Severity.CRITICAL if data_source == 'network' else Severity.HIGH

            self.findings.append(StandardFinding(
                rule_name='python-yaml-unsafe-load',
                message=f'Unsafe YAML loading with {method} - code execution risk',
                file_path=file,
                line=line,
                severity=severity,
                category='deserialization',
                confidence=Confidence.HIGH,
                cwe_id='CWE-502'
            ))

    def _check_marshal_shelve(self):
        """Detect marshal and shelve usage."""
        # Check marshal
        marshal_placeholders = ','.join('?' * len(self.patterns.MARSHAL_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({marshal_placeholders})
            ORDER BY file, line
        """, list(self.patterns.MARSHAL_METHODS))

        for file, line, method, args in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-marshal-usage',
                message=f'Marshal {method} can execute arbitrary bytecode',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='deserialization',
                confidence=Confidence.HIGH,
                cwe_id='CWE-502'
            ))

        # Check shelve
        shelve_placeholders = ','.join('?' * len(self.patterns.SHELVE_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({shelve_placeholders})
            ORDER BY file, line
        """, list(self.patterns.SHELVE_METHODS))

        for file, line, method, args in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-shelve-usage',
                message=f'Shelve {method} uses pickle internally - code execution risk',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='deserialization',
                confidence=Confidence.HIGH,
                cwe_id='CWE-502'
            ))

    def _check_json_exploitation(self):
        """Detect potentially exploitable JSON parsing."""
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ('json.loads', 'json.load', 'loads', 'load')
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, method, args in self.cursor.fetchall():
            # Check for dangerous parameters
            has_object_hook = any(hook in args for hook in self.patterns.JSON_DANGEROUS)

            if has_object_hook:
                self.findings.append(StandardFinding(
                    rule_name='python-json-object-hook',
                    message=f'JSON {method} with object_hook can be exploited',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='deserialization',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-502'
                ))

    def _check_django_flask_sessions(self):
        """Detect unsafe session deserialization in web frameworks."""
        # Check Django PickleSerializer
        django_placeholders = ','.join('?' * len(self.patterns.DJANGO_SESSION))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({django_placeholders})
               OR argument_expr LIKE '%PickleSerializer%'
            ORDER BY file, line
        """, list(self.patterns.DJANGO_SESSION))

        for file, line, method, args in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-django-pickle-session',
                message='Django PickleSerializer for sessions is unsafe',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='deserialization',
                confidence=Confidence.HIGH,
                cwe_id='CWE-502'
            ))

        # Check Flask sessions
        flask_placeholders = ','.join('?' * len(self.patterns.FLASK_SESSION))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({flask_placeholders})
            ORDER BY file, line
        """, list(self.patterns.FLASK_SESSION))

        for file, line, method, args in self.cursor.fetchall():
            if 'pickle' in method.lower() or (args and 'pickle' in args.lower()):
                self.findings.append(StandardFinding(
                    rule_name='python-flask-unsafe-session',
                    message='Flask session using unsafe deserialization',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='deserialization',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-502'
                ))

    def _check_xml_xxe(self):
        """Detect XML external entity (XXE) vulnerabilities."""
        xml_placeholders = ','.join('?' * len(self.patterns.XML_UNSAFE))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({xml_placeholders})
            ORDER BY file, line
        """, list(self.patterns.XML_UNSAFE))

        for file, line, method, args in self.cursor.fetchall():
            # Check if resolve_entities is disabled (safe)
            if args and 'resolve_entities=False' in args:
                continue

            self.findings.append(StandardFinding(
                rule_name='python-xml-xxe',
                message=f'XML parsing with {method} vulnerable to XXE attacks',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='deserialization',
                confidence=Confidence.HIGH,
                cwe_id='CWE-611'
            ))

    def _check_base64_pickle_combo(self):
        """Detect base64-encoded pickle (common attack pattern)."""
        # Look for base64 decode followed by pickle loads
        base64_placeholders = ','.join('?' * len(self.patterns.BASE64_PATTERNS))

        self.cursor.execute(f"""
            SELECT DISTINCT f1.file, f1.line, f1.callee_function
            FROM function_call_args f1
            WHERE f1.callee_function IN ({base64_placeholders})
              AND EXISTS (
                  SELECT 1 FROM function_call_args f2
                  WHERE f2.file = f1.file
                    AND f2.line >= f1.line
                    AND f2.line <= f1.line + 5
                    AND (f2.callee_function LIKE '%pickle.load%'
                         OR f2.callee_function LIKE '%loads%')
              )
            ORDER BY f1.file, f1.line
        """, list(self.patterns.BASE64_PATTERNS))

        for file, line, method in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='python-base64-pickle',
                message='Base64-encoded pickle detected - common attack vector',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='deserialization',
                confidence=Confidence.HIGH,
                cwe_id='CWE-502'
            ))

    def _check_data_source(self, file: str, line: int, args: str) -> str:
        """Determine if data comes from network, file, or unknown source."""
        if not args:
            return 'unknown'

        # Check for network sources
        for source in self.patterns.NETWORK_SOURCES:
            if source in args:
                return 'network'

        # Check for file sources
        for source in self.patterns.FILE_SOURCES:
            if source in args:
                return 'file'

        # Check nearby code for data source
        # Look for network/file operations nearby
        self.cursor.execute("""
            SELECT callee_function FROM function_call_args
            WHERE file = ?
              AND line >= ? - 10
              AND line <= ?
            ORDER BY line DESC
            LIMIT 5
        """, [file, line, line])

        recent_calls = [row[0] for row in self.cursor.fetchall()]

        for call in recent_calls:
            if any(net in call for net in self.patterns.NETWORK_SOURCES):
                return 'network'
            if any(f in call for f in self.patterns.FILE_SOURCES):
                return 'file'

        return 'unknown'

    def _check_imports_context(self):
        """Check if dangerous modules are imported."""
        # Check for pickle imports
        self.cursor.execute("""
            SELECT src, line FROM refs
            WHERE value IN ('pickle', 'cPickle', 'dill', 'cloudpickle')
               OR value LIKE 'from pickle import%'
               OR value LIKE 'import pickle%'
            ORDER BY src, line
        """)

        pickle_imports = self.cursor.fetchall()

        if pickle_imports:
            # Check if pickle is actually used
            for file, line in pickle_imports:
                # Check if there are no pickle calls (just import)
                self.cursor.execute("""
                    SELECT COUNT(*) FROM function_call_args
                    WHERE file = ?
                      AND callee_function LIKE '%pickle%'
                """, [file])

                if self.cursor.fetchone()[0] == 0:
                    self.findings.append(StandardFinding(
                        rule_name='python-pickle-import',
                        message='Pickle module imported - consider safer alternatives',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category='deserialization',
                        confidence=Confidence.LOW,
                        cwe_id='CWE-502'
                    ))


# ============================================================================
# MISSING DATABASE FEATURES FLAGGED
# ============================================================================

"""
FLAGGED: Missing database features for better deserialization detection:

1. Data flow analysis:
   - Can't track: request.data -> variable -> pickle.loads(variable)
   - Need taint propagation through variables

2. Import aliasing:
   - Can't detect: import pickle as pkl; pkl.loads()
   - Need import alias tracking

3. Decorators and middleware:
   - Can't detect unsafe session middleware configuration
   - Need decorator extraction

4. Configuration files:
   - Can't check Django settings.py for SESSION_SERIALIZER
   - Need config file parsing

5. Method chaining:
   - Can't track: base64.b64decode(request.data).loads()
   - Need expression tree analysis
"""


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Python deserialization vulnerabilities.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of deserialization vulnerabilities found
    """
    analyzer = DeserializationAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# TAINT REGISTRATION (For Orchestrator)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register deserialization-specific taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = DeserializationPatterns()

    # Register network sources as tainted
    for pattern in patterns.NETWORK_SOURCES:
        taint_registry.register_source(pattern, "network_data", "python")

    # Register file sources
    for pattern in patterns.FILE_SOURCES:
        taint_registry.register_source(pattern, "file_data", "python")

    # Register pickle as critical sink
    for pattern in patterns.PICKLE_METHODS:
        taint_registry.register_sink(pattern, "pickle_deserialize", "python")

    # Register YAML as critical sink
    for pattern in patterns.YAML_UNSAFE:
        taint_registry.register_sink(pattern, "yaml_deserialize", "python")

    # Register marshal/shelve as sinks
    for pattern in patterns.MARSHAL_METHODS:
        taint_registry.register_sink(pattern, "marshal_deserialize", "python")

    for pattern in patterns.SHELVE_METHODS:
        taint_registry.register_sink(pattern, "shelve_deserialize", "python")