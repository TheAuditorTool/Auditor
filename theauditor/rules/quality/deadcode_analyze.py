"""Dead code detection rule - finds modules never imported.

Integrated into 'aud full' pipeline via orchestrator.
Generates findings with severity='info' (quality concern, not security).

Pattern: Follows progress.md rules - analyze() function, execution_scope='database'.
"""

import sqlite3
from typing import List
from theauditor.rules.base import (
    StandardRuleContext,
    StandardFinding,
    Severity,
    RuleMetadata
)
from theauditor.context.deadcode import detect_isolated_modules


METADATA = RuleMetadata(
    name="deadcode",
    category="quality",
    target_extensions=['.py', '.js', '.ts', '.tsx', '.jsx'],
    exclude_patterns=['node_modules/', '.venv/', '__pycache__/', 'dist/', 'build/'],
    requires_jsx_pass=False,
    execution_scope='database'  # Run once per database, not per file
)


def find_dead_code(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect dead code using database queries.

    Detection Strategy:
        1. Query symbols table for files with code definitions
        2. Query refs table for imported files
        3. Set difference identifies dead code
        4. Filter exclusions (__init__.py, tests, migrations)

    Database Tables Used:
        - symbols (read: path, name)
        - refs (read: value, kind)

    Known Limitations:
        - Does NOT detect dynamically imported modules (importlib.import_module)
        - Does NOT detect getattr() dynamic calls
        - Static analysis only

    Returns:
        List of findings with severity=INFO
    """
    findings = []

    if not context.db_path:
        return findings

    try:
        # Use context layer for detection
        modules = detect_isolated_modules(
            context.db_path,
            exclude_patterns=['__init__.py', 'test', 'migration', '__pycache__', 'node_modules', '.venv']
        )

        # Create findings (severity=INFO)
        for module in modules:
            findings.append(StandardFinding(
                rule_name="deadcode",
                message=f"Module never imported: {module.path}",
                file_path=str(module.path),
                line=1,
                severity=Severity.INFO,  # Not a security issue
                category="quality",
                snippet="",
                additional_info={
                    'type': 'isolated_module',
                    'symbol_count': module.symbol_count,
                    'lines_estimated': module.lines_estimated,
                    'confidence': module.confidence,
                    'reason': module.reason
                }
            ))

    except Exception:
        # Hard fail if database query fails (no fallback)
        raise

    return findings
