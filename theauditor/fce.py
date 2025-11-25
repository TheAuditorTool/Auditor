"""Factual Correlation Engine - aggregates and correlates findings from all analysis tools.

CRITICAL ARCHITECTURE RULE: NO FALLBACKS ALLOWED.
The database is generated fresh every run. It MUST exist and MUST contain all required data.
NO JSON fallbacks, NO graceful degradation, NO try/except to handle missing data.
Hard failure is the only acceptable behavior. If data is missing, the pipeline should crash.
"""


import json
import os
import re
import shlex
import sqlite3
import subprocess
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from collections.abc import Callable

from theauditor.test_frameworks import detect_test_framework
from theauditor.utils.temp_manager import TempManager




def load_graph_data_from_db(db_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Load graph analysis data (hotspots and cycles) from database.

    Queries findings_consolidated for graph-analysis findings with structured data
    in details_json column. This is faster than loading JSON files and enables
    database-first FCE operation.

    Args:
        db_path: Path to repo_index.db database

    Returns:
        Tuple of (hotspot_files dict, cycles list)
        - hotspot_files: {file_path: hotspot_data} for O(1) lookup
        - cycles: List of cycle dicts with nodes and size
    """
    hotspot_files = {}
    cycles = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load hotspots with structured data from details_json
    cursor.execute("""
        SELECT file, details_json
        FROM findings_consolidated
        WHERE tool='graph-analysis' AND rule='ARCHITECTURAL_HOTSPOT'
    """)

    for row in cursor.fetchall():
        file_path, details_json = row
        if details_json:
            details = json.loads(details_json)
            hotspot_files[file_path] = details

    # Load cycles - deduplicate by cycle nodes
    cursor.execute("""
        SELECT DISTINCT details_json
        FROM findings_consolidated
        WHERE tool='graph-analysis' AND rule='CIRCULAR_DEPENDENCY'
    """)

    seen_cycles = set()
    for row in cursor.fetchall():
        details_json = row[0]
        if details_json:
            details = json.loads(details_json)
            cycle_nodes = details.get('cycle_nodes', [])
            cycle_size = details.get('cycle_size', len(cycle_nodes))

            # Deduplicate cycles by sorted node list
            cycle_key = tuple(sorted(cycle_nodes))
            if cycle_key and cycle_key not in seen_cycles:
                cycles.append({
                    'nodes': list(cycle_key),
                    'size': cycle_size
                })
                seen_cycles.add(cycle_key)

    conn.close()

    return hotspot_files, cycles


def load_cfg_data_from_db(db_path: str) -> dict[str, Any]:
    """
    Load CFG complexity data from database.

    Args:
        db_path: Path to repo_index.db database

    Returns:
        Dict mapping 'file:function' to complexity data
    """
    complex_functions = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, details_json
        FROM findings_consolidated
        WHERE tool='cfg-analysis' AND rule='HIGH_CYCLOMATIC_COMPLEXITY'
    """)

    for row in cursor.fetchall():
        file_path, details_json = row
        if details_json:
            details = json.loads(details_json)
            function_name = details.get('function', 'unknown')
            key = f"{file_path}:{function_name}"
            complex_functions[key] = details

    conn.close()

    return complex_functions


def load_churn_data_from_db(db_path: str) -> dict[str, Any]:
    """
    Load code churn data from database.

    Args:
        db_path: Path to repo_index.db database

    Returns:
        Dict mapping file path to churn metrics
    """
    churn_files = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, details_json
        FROM findings_consolidated
        WHERE tool='churn-analysis' AND rule='HIGH_CODE_CHURN'
    """)

    for row in cursor.fetchall():
        file_path, details_json = row
        if details_json:
            details = json.loads(details_json)
            churn_files[file_path] = details

    conn.close()

    return churn_files


def load_coverage_data_from_db(db_path: str) -> dict[str, Any]:
    """
    Load test coverage data from database.

    Args:
        db_path: Path to repo_index.db database

    Returns:
        Dict mapping file path to coverage metrics
    """
    coverage_files = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, details_json
        FROM findings_consolidated
        WHERE tool='coverage-analysis' AND rule='LOW_TEST_COVERAGE'
    """)

    for row in cursor.fetchall():
        file_path, details_json = row
        if details_json:
            details = json.loads(details_json)
            coverage_files[file_path] = details

    conn.close()

    return coverage_files


def load_taint_data_from_db(db_path: str) -> list[dict[str, Any]]:
    """
    Load complete taint paths from database.

    Queries findings_consolidated for tool='taint' and deserializes
    complete taint path structures from details_json column. This enables
    FCE to perform taint-aware correlations without re-parsing JSON files.

    Args:
        db_path: Path to repo_index.db database

    Returns:
        List of complete taint path dicts with source, intermediate steps, and sink

    Performance:
        - O(n) where n = number of taint findings
        - ~10-50ms for 100-1000 paths (indexed query + JSON deserialization)

    Data Structure:
        Each taint path contains:
        - source: {file, line, name, pattern, type}
        - path: [{type, file, line, name, ...}, ...] (intermediate steps)
        - sink: {file, line, name, pattern, type}
        - severity: critical|high|medium|low
        - vulnerability_type: SQL Injection|XSS|Command Injection|etc.
    """
    taint_paths = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query all taint findings with non-empty details_json
    cursor.execute("""
        SELECT details_json
        FROM findings_consolidated
        WHERE tool='taint'
          AND details_json IS NOT NULL
          AND details_json != '{}'
    """)

    for row in cursor.fetchall():
        details_json = row[0]
        if details_json:
            path_data = json.loads(details_json)
            # Validate it has taint path structure (source and sink required)
            if 'source' in path_data and 'sink' in path_data:
                taint_paths.append(path_data)

    conn.close()

    return taint_paths


def load_workflow_data_from_db(db_path: str) -> list[dict[str, Any]]:
    """
    Load GitHub Actions workflow security findings from database.

    Queries findings_consolidated for tool='github-actions-rules' and deserializes
    workflow vulnerability data from details_json column. This enables FCE to
    correlate workflow risks with taint paths (e.g., secret exposure via PR injection).

    Args:
        db_path: Path to repo_index.db database

    Returns:
        List of workflow finding dicts with rule-specific vulnerability data

    Performance:
        - O(n) where n = number of workflow findings
        - ~5-20ms for 10-100 findings (indexed query + JSON deserialization)

    Data Structure:
        Each workflow finding contains:
        - workflow: Workflow file path (.github/workflows/*.yml)
        - workflow_name: Human-readable workflow name
        - rule: Specific vulnerability type (untrusted_checkout_sequence, etc.)
        - severity: critical|high|medium|low
        - category: supply-chain|injection|access-control
        - details: Rule-specific data (job keys, permissions, references, etc.)
    """
    workflow_findings = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query all GitHub Actions findings
    # Note: tool is set to 'patterns' by orchestrator, so we query by rule names
    # Note: details_json not always populated by orchestrator, so we use basic fields
    cursor.execute("""
        SELECT file, rule, severity, category, message
        FROM findings_consolidated
        WHERE rule IN (
            'untrusted_checkout_sequence',
            'unpinned_action_with_secrets',
            'pull_request_injection',
            'excessive_pr_permissions',
            'external_reusable_with_secrets',
            'artifact_poisoning_risk'
        )
    """)

    for row in cursor.fetchall():
        file_path, rule, severity, category, message = row
        # Build structured finding dict for correlation
        # Extract workflow name from file path (.github/workflows/name.yml)
        workflow_name = file_path.split('/')[-1].replace('.yml', '').replace('.yaml', '')

        workflow_findings.append({
            'file': file_path,
            'rule': rule,
            'severity': severity,
            'category': category,
            'message': message,
            'workflow': file_path,
            'workflow_name': workflow_name
        })

    conn.close()

    return workflow_findings


def load_graphql_findings_from_db(db_path: str) -> list[dict[str, Any]]:
    """
    Load GraphQL security findings from graphql_findings_cache table.

    Queries graphql_findings_cache for pre-computed GraphQL security findings
    generated by GraphQL security rules. This enables FCE to correlate GraphQL
    vulnerabilities with taint paths and other security findings.

    Args:
        db_path: Path to repo_index.db database

    Returns:
        List of GraphQL finding dicts with vulnerability metadata

    Performance:
        - O(n) where n = number of GraphQL findings
        - ~5-20ms for 10-100 findings (indexed query + deserialization)

    Data Structure:
        Each GraphQL finding contains:
        - finding_type: Type of GraphQL vulnerability (mutation_auth, query_depth, etc.)
        - schema_file: GraphQL schema file path
        - field_path: Qualified field path (Type.field)
        - severity: critical|high|medium|low
        - confidence: high|medium|low
        - description: Human-readable finding description
        - metadata: Rule-specific data (field_name, type_name, etc.)
    """
    graphql_findings = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query all GraphQL findings from cache
    # Schema: finding_type, schema_file, field_path, line, severity, confidence, description, metadata_json
    cursor.execute("""
        SELECT finding_type, schema_file, field_path, line, severity, confidence, description, metadata_json
        FROM graphql_findings_cache
    """)

    for row in cursor.fetchall():
        finding_type, schema_file, field_path, line, severity, confidence, description, metadata_json = row

        # Parse metadata JSON if available
        metadata = {}
        if metadata_json:
            metadata = json.loads(metadata_json)

        graphql_findings.append({
            'finding_type': finding_type,
            'schema_file': schema_file,
            'field_path': field_path,
            'line': line or 0,
            'severity': severity,
            'confidence': confidence,
            'description': description,
            'metadata': metadata,
            'category': 'graphql'
        })

    conn.close()

    return graphql_findings


def scan_all_findings(db_path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Scan ALL findings from database with line-level detail.

    Database-first design for 100x performance improvement over JSON file reading.
    This implements the dual-write pattern: tools write to BOTH database (for FCE speed)
    AND JSON files (for AI consumption via extraction.py).

    Args:
        db_path: Path to repo_index.db database

    Returns:
        List of standardized finding dicts with file, line, rule, tool, message, severity

    Performance:
        - O(log n) database query vs O(n*m) file I/O (n=files, m=avg size)
        - Indexed queries on (file, line), tool, severity
        - Pre-sorted by severity in SQL (faster than Python sort)
    """
    all_findings: list[dict[str, Any]] = []
    dedupe_stats: dict[str, Any] = {
        "total_rows": 0,
        "unique_rows": 0,
        "duplicates_collapsed": 0,
        "top_duplicates": [],
    }
    seen_keys: dict[tuple[Any, ...], dict[str, Any]] = {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    cursor = conn.cursor()

    # Query all findings, pre-sorted by severity for efficiency
    # This is 100x faster than reading JSON files due to:
    # 1. Indexed queries (O(log n) vs O(n))
    # 2. Binary data format (vs text parsing)
    # 3. SQL-side sorting (vs Python sorting)
    cursor.execute("""
        SELECT file, line, column, rule, tool, message, severity,
               category, confidence, code_snippet, cwe
        FROM findings_consolidated
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            file, line
    """)

    total_rows = 0
    for row in cursor.fetchall():
        total_rows += 1
        entry = {
            'file': row['file'],
            'line': row['line'],
            'column': row['column'],
            'rule': row['rule'],
            'tool': row['tool'],
            'message': row['message'],
            'severity': row['severity'],
            'category': row['category'],
            'confidence': row['confidence'],
            'code_snippet': row['code_snippet'],
            'cwe': row['cwe'],
            'duplicate_count': 1,
        }

        dedupe_key = (
            entry['file'],
            entry['line'],
            entry['rule'],
            entry['tool'],
            entry['message'],
        )

        existing = seen_keys.get(dedupe_key)
        if existing:
            existing['duplicate_count'] += 1
            continue

        seen_keys[dedupe_key] = entry
        all_findings.append(entry)

    conn.close()

    dedupe_stats['total_rows'] = total_rows
    dedupe_stats['unique_rows'] = len(all_findings)
    dedupe_stats['duplicates_collapsed'] = total_rows - len(all_findings)

    if all_findings:
        if dedupe_stats['duplicates_collapsed'] > 0:
            print(
                "[FCE] Loaded "
                f"{dedupe_stats['unique_rows']} unique findings from database "
                f"(collapsed {dedupe_stats['duplicates_collapsed']} duplicates)"
            )
        else:
            print(
                f"[FCE] Loaded {len(all_findings)} findings from database (database-first)"
            )
    else:
        print("[FCE] No findings in database - tools may need to run first")

    if dedupe_stats['duplicates_collapsed'] > 0:
        # Surface top duplicate clusters for diagnostics
        top_duplicates = sorted(
            (
                {
                    'file': entry['file'],
                    'line': entry['line'],
                    'rule': entry['rule'],
                    'tool': entry['tool'],
                    'duplicate_count': entry['duplicate_count'],
                }
                for entry in all_findings
                if entry['duplicate_count'] > 1
            ),
            key=lambda item: item['duplicate_count'],
            reverse=True,
        )[:5]
        dedupe_stats['top_duplicates'] = top_duplicates
        if top_duplicates:
            sample = ', '.join(
                f"{d['rule']}@{d['file']}:{d['line']}×{d['duplicate_count']}"
                for d in top_duplicates[:3]
            )
            print(f"[FCE] Top duplicate clusters: {sample}")

    return all_findings, dedupe_stats



def run_tool(command: str, root_path: str, timeout: int = 600) -> tuple[int, str, str]:
    """Run build/test tool with timeout and capture output."""
    # Use deque as ring buffer to limit memory usage
    max_lines = 10000
    stdout_buffer = deque(maxlen=max_lines)
    stderr_buffer = deque(maxlen=max_lines)

    # Run command - safely split command string into arguments
    cmd_args = shlex.split(command)
    tool_name = Path(cmd_args[0]).name if cmd_args else "process"

    stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
        root_path,
        tool_name=tool_name,
    )

    env = {**os.environ, "CI": "true"}
    if tool_name.startswith("pytest"):
        pytest_temp = TempManager.get_temp_dir(root_path) / "pytest"
        pytest_temp.mkdir(parents=True, exist_ok=True)
        existing_opts = env.get("PYTEST_ADDOPTS", "").strip()
        extra_opt = f"--basetemp={pytest_temp}"
        env["PYTEST_ADDOPTS"] = f"{existing_opts} {extra_opt}".strip()

    with open(stdout_path, 'w', encoding='utf-8') as out_tmp, \
         open(stderr_path, 'w', encoding='utf-8') as err_tmp:

        process = subprocess.Popen(
            cmd_args,
            cwd=root_path,
            stdout=out_tmp,
            stderr=err_tmp,
            text=True,
            env=env,
        )

    # Stream output with timeout
    try:
        process.communicate(timeout=timeout)
        
        # Read back the outputs
        with open(stdout_path, encoding='utf-8', errors='ignore') as f:
            stdout = f.read()
        with open(stderr_path, encoding='utf-8', errors='ignore') as f:
            stderr = f.read()
        
        # Clean up temp files
        try:
            os.unlink(stdout_path)
        except OSError:
            pass
        try:
            os.unlink(stderr_path)
        except OSError:
            pass
        
        # Append any errors to the global error.log
        if stderr.strip():
            from pathlib import Path
            error_log = Path(root_path) / ".pf" / "error.log"
            error_log.parent.mkdir(parents=True, exist_ok=True)
            with open(error_log, 'a') as f:
                f.write(f"\n=== RCA Subprocess Error ({command[:50]}) ===\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(stderr)
                f.write("\n")
        # Store in buffers
        stdout_buffer.extend(stdout.splitlines())
        stderr_buffer.extend(stderr.splitlines())
    except subprocess.TimeoutExpired:
        process.kill()
        return 124, "Process timed out", f"Command exceeded {timeout}s timeout"

    # Join lines
    stdout_text = "\n".join(stdout_buffer)
    stderr_text = "\n".join(stderr_buffer)

    return process.returncode, stdout_text, stderr_text



def parse_typescript_errors(output: str) -> list[dict[str, Any]]:
    """Parse TypeScript/TSNode compiler errors."""
    errors = []

    # TypeScript error format: file:line:col - error CODE: message
    pattern = (
        r"(?P<file>[^:\n]+):(?P<line>\d+):(?P<col>\d+) - error (?P<code>[A-Z]+\d+): (?P<msg>.+)"
    )

    for match in re.finditer(pattern, output):
        errors.append(
            {
                "tool": "tsc",
                "file": match.group("file"),
                "line": int(match.group("line")),
                "column": int(match.group("col")),
                "message": match.group("msg"),
                "code": match.group("code"),
                "category": "type_error",
            }
        )

    return errors


def parse_jest_errors(output: str) -> list[dict[str, Any]]:
    """Parse Jest/Vitest test failures."""
    errors = []

    # Jest failed test: ● Test Suite Name › test name
    # Followed by stack trace: at Object.<anonymous> (file:line:col)
    test_pattern = r"● (?P<testname>[^\n]+)"
    stack_pattern = r"at .*? \((?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+)\)"

    lines = output.splitlines()
    for i, line in enumerate(lines):
        test_match = re.match(test_pattern, line)
        if test_match:
            # Look for stack trace in next lines
            for j in range(i + 1, min(i + 20, len(lines))):
                stack_match = re.search(stack_pattern, lines[j])
                if stack_match:
                    errors.append(
                        {
                            "tool": "jest",
                            "file": stack_match.group("file"),
                            "line": int(stack_match.group("line")),
                            "column": int(stack_match.group("col")),
                            "message": f"Test failed: {test_match.group('testname')}",
                            "category": "test_failure",
                        }
                    )
                    break

    return errors


def parse_pytest_errors(output: str) -> list[dict[str, Any]]:
    """Parse pytest failures."""
    errors = []

    # Pytest error format varies, but typically:
    # FAILED path/to/test.py::TestClass::test_method - AssertionError: message
    # Or: E   AssertionError: message
    #     path/to/file.py:42: AssertionError

    failed_pattern = r"FAILED (?P<file>[^:]+)(?:::(?P<test>[^\s]+))? - (?P<msg>.+)"
    error_pattern = r"^E\s+(?P<msg>.+)\n.*?(?P<file>[^:]+):(?P<line>\d+):"

    for match in re.finditer(failed_pattern, output):
        errors.append(
            {
                "tool": "pytest",
                "file": match.group("file"),
                "line": 0,  # Line not in FAILED format
                "message": match.group("msg"),
                "category": "test_failure",
            }
        )

    for match in re.finditer(error_pattern, output, re.MULTILINE):
        errors.append(
            {
                "tool": "pytest",
                "file": match.group("file"),
                "line": int(match.group("line")),
                "message": match.group("msg"),
                "category": "test_failure",
            }
        )

    return errors


def parse_python_compile_errors(output: str) -> list[dict[str, Any]]:
    """Parse Python compilation errors from py_compile output."""
    errors = []
    
    # Python compile error format:
    # Traceback (most recent call last):
    #   File "path/to/file.py", line X, in <module>
    # SyntaxError: invalid syntax
    # Or: ModuleNotFoundError: No module named 'xxx'
    
    # Parse traceback format
    lines = output.splitlines()
    for i, line in enumerate(lines):
        # Look for File references in tracebacks
        if 'File "' in line and '", line ' in line:
            # Extract file and line number
            match = re.match(r'.*File "([^"]+)", line (\d+)', line)
            if match and i + 1 < len(lines):
                file_path = match.group(1)
                line_num = int(match.group(2))
                
                # Look for the error type in following lines
                for j in range(i + 1, min(i + 5, len(lines))):
                    if 'Error:' in lines[j]:
                        error_msg = lines[j].strip()
                        errors.append({
                            "tool": "py_compile",
                            "file": file_path,
                            "line": line_num,
                            "message": error_msg,
                            "category": "compile_error",
                        })
                        break
        
        # Also catch simple error messages
        if 'SyntaxError:' in line or 'ModuleNotFoundError:' in line or 'ImportError:' in line:
            # Try to extract file info from previous lines
            file_info = None
            for j in range(max(0, i - 3), i):
                if '***' in lines[j] and '.py' in lines[j]:
                    # py_compile format: *** path/to/file.py
                    file_match = re.match(r'\*\*\* (.+\.py)', lines[j])
                    if file_match:
                        file_info = file_match.group(1)
                        break
            
            if file_info:
                errors.append({
                    "tool": "py_compile",
                    "file": file_info,
                    "line": 0,
                    "message": line.strip(),
                    "category": "compile_error",
                })
    
    return errors


def parse_errors(output: str, tool_name: str) -> list[dict[str, Any]]:
    """Parse errors based on tool type."""
    all_errors = []

    # Try all parsers
    all_errors.extend(parse_typescript_errors(output))
    all_errors.extend(parse_jest_errors(output))
    all_errors.extend(parse_pytest_errors(output))
    all_errors.extend(parse_python_compile_errors(output))

    return all_errors


def load_capsule(capsules_dir: str, file_hash: str) -> dict | None:
    """Load capsule by file hash."""
    capsule_path = Path(capsules_dir) / f"{file_hash}.json"
    if not capsule_path.exists():
        return None

    with open(capsule_path) as f:
        return json.load(f)




def correlate_failures(
    errors: list[dict[str, Any]],
    manifest_path: str,
    workset_path: str,
    capsules_dir: str,
    db_path: str,
) -> list[dict[str, Any]]:
    """Correlate failures with capsules for factual enrichment."""
    # Load manifest for hash lookup
    file_hashes = {}
    if Path(manifest_path).exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        for entry in manifest:
            file_hashes[entry["path"]] = entry.get("sha256")

    # Load workset (for future use)
    if Path(workset_path).exists():
        with open(workset_path) as f:
            json.load(f)

    # Correlate each error
    for error in errors:
        file = error.get("file", "")

        # Load capsule if file in workset/manifest
        if file in file_hashes:
            file_hash = file_hashes[file]
            capsule = load_capsule(capsules_dir, file_hash)
            if capsule:
                error["capsule"] = {
                    "path": capsule.get("path"),
                    "hash": capsule.get("sha256"),
                    "interfaces": capsule.get("interfaces", {}),
                }


    return errors


def generate_rca_json(failures: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate RCA JSON output."""
    return {
        "completed_at": datetime.now(UTC).isoformat(),
        "failures": failures,
    }


def run_fce(
    root_path: str = ".",
    capsules_dir: str = "./.pf/capsules",
    manifest_path: str = "manifest.json",
    workset_path: str = "./.pf/workset.json",
    db_path: str = ".pf/repo_index.db",
    timeout: int = 600,
    print_plan: bool = False,
) -> dict[str, Any]:
    """Run factual correlation engine - NO interpretation, just facts."""
    # Step A: Initialization
    raw_dir = Path(root_path) / ".pf" / "raw"
    full_db_path = str(Path(root_path) / db_path)
    results = {
        "timestamp": datetime.now(UTC).isoformat(),
        "all_findings": [],
        "test_results": {},
        "correlations": {}
    }

    # Step B: Phase 1 - Gather All Findings (Database-First)
    # Uses database query instead of JSON file reading for 100x performance
    dedupe_stats = {}
    if Path(full_db_path).exists():
        findings, dedupe_stats = scan_all_findings(full_db_path)
        results["all_findings"] = findings
    else:
        print(f"[FCE] Warning: Database not found at {full_db_path}")
        print("[FCE] Run 'aud index' to create database")

    if not dedupe_stats:
        dedupe_stats = {
            "total_rows": len(results.get("all_findings", [])),
            "unique_rows": len(results.get("all_findings", [])),
            "duplicates_collapsed": 0,
            "top_duplicates": [],
        }
    
    # Step B1: Load Graph Analysis Data (Hotspots, Cycles, Health)
    hotspot_files, cycles = load_graph_data_from_db(full_db_path)
    print(f"[FCE] Loaded from database: {len(hotspot_files)} hotspots, {len(cycles)} cycles")

    # Step B1.5: Load CFG Complexity Data (Function Complexity Metrics)
    complex_functions = load_cfg_data_from_db(full_db_path)
    print(f"[FCE] Loaded from database: {len(complex_functions)} complex functions")

    # Step B1.6: Load Metadata - Code Churn (Temporal Dimension)
    churn_files = load_churn_data_from_db(full_db_path)
    print(f"[FCE] Loaded from database: {len(churn_files)} files with git history")

    # Step B1.7: Load Metadata - Test Coverage (Quality Dimension)
    coverage_files = load_coverage_data_from_db(full_db_path)
    print(f"[FCE] Loaded from database: {len(coverage_files)} files with coverage data")

    # Step B1.8: Load Taint Analysis Data (Complete Flow Paths)
    taint_paths = load_taint_data_from_db(full_db_path)
    print(f"[FCE] Loaded from database: {len(taint_paths)} taint flow paths")

    # Step B1.9: Load GitHub Actions Workflow Security Findings
    workflow_findings = load_workflow_data_from_db(full_db_path)
    print(f"[FCE] Loaded from database: {len(workflow_findings)} workflow security findings")

    # Step B1.10: Load GraphQL Security Findings (Section 7: Taint & FCE Integration)
    graphql_findings = load_graphql_findings_from_db(full_db_path)
    print(f"[FCE] Loaded from database: {len(graphql_findings)} GraphQL security findings")

    # Step B2: Load Optional Insights (Interpretive Analysis)
    # IMPORTANT: Insights are kept separate from factual findings to maintain Truth Courier principles
    insights_data = {}
    insights_dir = Path(root_path) / ".pf" / "insights"
    
    if insights_dir.exists():
        # Dynamically load ALL JSON files from insights directory
        # This future-proofs the system - new insights modules are automatically included
        for insight_file in insights_dir.glob("*.json"):
            with open(insight_file, encoding='utf-8') as f:
                file_data = json.load(f)

            # Store each insights file's data under its name (without .json)
            # Examples: ml_suggestions, taint_severity, graph_health, impact_analysis, unified_insights
            insights_data[insight_file.stem] = file_data
            print(f"[FCE] Loaded insights module: {insight_file.stem}")
        
        if insights_data:
            # Store ALL insights in a separate section to maintain fact/interpretation separation
            # This preserves the Truth Courier model - facts and interpretations are never mixed
            results["insights"] = insights_data
            print(f"[FCE] Loaded {len(insights_data)} insights modules into results['insights']")
            
            # Log what was loaded for transparency
            modules_loaded = list(insights_data.keys())
            print(f"[FCE] Available insights: {', '.join(modules_loaded)}")
        else:
            print("[FCE] No insights data found in .pf/insights/")
    else:
        print("[FCE] Insights directory not found - skipping optional insights loading")
    
    # Step C: Phase 2 - Execute Tests
    # Detect test framework
    framework_info = detect_test_framework(root_path)
    
    tools = []
    if framework_info["name"] != "unknown" and framework_info["cmd"]:
        command = framework_info["cmd"]
        
        # Add quiet flags
        if "pytest" in command:
            command = "pytest -q -p no:cacheprovider"
        elif "npm test" in command:
            command = "npm test --silent"
        elif "unittest" in command:
            command = "python -m unittest discover -q"
        
        tools.append({
            "name": framework_info["name"],
            "command": command,
            "type": "test"
        })
    
    # Check for build scripts
    package_json = Path(root_path) / "package.json"
    run_build = os.environ.get("THEAUDITOR_FCE_RUN_BUILD", "0") == "1"

    if package_json.exists() and run_build:
        with open(package_json) as f:
            package = json.load(f)
        scripts = package.get("scripts", {})
        if "build" in scripts:
            tools.append({
                "name": "npm build",
                "command": "npm run build --silent",
                "type": "build"
            })
    elif package_json.exists() and not run_build:
        print("[FCE] Skipping npm build (set THEAUDITOR_FCE_RUN_BUILD=1 to enable)")
    
    if print_plan:
        print("Detected tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['command']}")
        return {"success": True, "printed_plan": True}
    
    if not tools:
        tools = []  # No test tools, continue processing
    
    # Run tools and collect failures
    all_failures = []
    
    for tool in tools:
        print(f"Running {tool['name']}...")
        exit_code, stdout, stderr = run_tool(tool["command"], root_path, timeout)
        
        if exit_code != 0:
            output = stdout + "\n" + stderr
            errors = parse_errors(output, tool["name"])
            
            # Special handling for pytest collection failures
            if tool["name"] == "pytest" and exit_code == 2 and "ERROR collecting" in output:
                print("Pytest collection failed. Falling back to Python compilation check...")
                
                py_files = []
                for py_file in Path(root_path).rglob("*.py"):
                    if "__pycache__" not in str(py_file) and not any(part.startswith('.') for part in py_file.parts):
                        py_files.append(str(py_file.relative_to(root_path)))
                
                if py_files:
                    print(f"Checking {len(py_files)} Python files for compilation errors...")
                    compile_errors = []
                    
                    for py_file in py_files[:50]:
                        module_path = str(Path(py_file).as_posix()).replace('/', '.').replace('.py', '')
                        import_cmd = f'python3 -c "import {module_path}"'
                        comp_exit, comp_out, comp_err = run_tool(import_cmd, root_path, 10)
                        
                        if comp_exit != 0:
                            comp_output = comp_out + "\n" + comp_err
                            if comp_output.strip():
                                error_lines = comp_output.strip().split('\n')
                                error_msg = "Import failed"
                                
                                for line in error_lines:
                                    if 'ModuleNotFoundError:' in line:
                                        error_msg = line.strip()
                                        break
                                    elif 'ImportError:' in line:
                                        error_msg = line.strip()
                                        break
                                    elif 'SyntaxError:' in line:
                                        error_msg = line.strip()
                                        break
                                    elif 'AttributeError:' in line:
                                        error_msg = line.strip()
                                        break
                                
                                compile_errors.append({
                                    "tool": "py_import",
                                    "file": py_file,
                                    "line": 0,
                                    "message": error_msg,
                                    "category": "compile_error",
                                })
                    
                    if compile_errors:
                        print(f"Found {len(compile_errors)} compilation errors")
                        errors.extend(compile_errors)
            
            # If no errors parsed, create generic one
            if not errors and exit_code != 0:
                errors.append({
                    "tool": tool["name"],
                    "file": "unknown",
                    "line": 0,
                    "message": f"Tool failed with exit code {exit_code}",
                    "category": "runtime",
                })
            
            all_failures.extend(errors)
    
    # Correlate with capsules
    all_failures = correlate_failures(
        all_failures,
        Path(root_path) / manifest_path,
        Path(root_path) / workset_path,
        Path(root_path) / capsules_dir,
        Path(root_path) / db_path,
    )
    
    # Store test results
    results["test_results"] = {
        "completed_at": datetime.now(UTC).isoformat(),
        "failures": all_failures,
        "tools_run": len(tools)
    }
    
    # Step D: Consolidate Evidence
    consolidated_findings = results["all_findings"].copy()
    
    # Add test failures to consolidated list
    if all_failures:
        for failure in all_failures:
            if 'file' in failure and 'line' in failure:
                consolidated_findings.append({
                    'file': failure['file'],
                    'line': int(failure.get('line', 0)),
                    'rule': failure.get('code', failure.get('category', 'test-failure')),
                    'tool': failure.get('tool', 'test'),
                    'message': failure.get('message', ''),
                    'severity': failure.get('severity', 'error')
                })
    
    # Step E: Phase 3 - Line-Level Correlation (Hotspots)
    # Group findings by file:line
    line_groups = defaultdict(list)
    for finding in consolidated_findings:
        if finding['line'] > 0:
            key = f"{finding['file']}:{finding['line']}"
            line_groups[key].append(finding)
    
    # Find hotspots
    hotspots = {}
    for line_key, findings in line_groups.items():
        tools_on_line = {f['tool'] for f in findings}
        if len(tools_on_line) > 1:
            hotspots[line_key] = findings
    
    # Enrich hotspots with symbol context
    full_db_path = Path(root_path) / db_path
    if hotspots and full_db_path.exists():
        conn = sqlite3.connect(str(full_db_path))
        cursor = conn.cursor()

        enriched_hotspots = {}
        for line_key, findings in hotspots.items():
            if ':' in line_key:
                file_path, line_str = line_key.rsplit(':', 1)
                line_num = int(line_str)

                query = """
                SELECT name, type, line
                FROM symbols
                WHERE file = ?
                  AND line <= ?
                  AND type IN ('function', 'class')
                ORDER BY line DESC
                LIMIT 1
                """
                cursor.execute(query, (file_path, line_num))
                result = cursor.fetchone()

                hotspot_data = {"findings": findings}

                if result:
                    symbol_name, symbol_type, symbol_line = result
                    hotspot_data["in_symbol"] = f"{symbol_type}: {symbol_name}"

                enriched_hotspots[line_key] = hotspot_data
            else:
                enriched_hotspots[line_key] = {"findings": findings}

        conn.close()
        hotspots = enriched_hotspots
    else:
        hotspots = {k: {"findings": v} for k, v in hotspots.items()}
    
    # Store hotspots in correlations
    results["correlations"]["hotspots"] = hotspots
    results["correlations"]["total_findings"] = len(consolidated_findings)
    results["correlations"]["total_lines_with_findings"] = len(line_groups)
    results["correlations"]["total_hotspots"] = len(hotspots)
    
    # Step F: Phase 4 - Factual Cluster Detection (DEPRECATED)
    # NOTE: Old correlation system removed in v1.1+
    # User-defined business logic now handled by semantic context engine:
    #   theauditor/insights/semantic_context.py
    # See: aud context --file <yaml>
    factual_clusters = []  # Keep for backward compatibility with downstream code

    # Store empty factual clusters (backward compat)
    results["correlations"]["factual_clusters"] = factual_clusters
    
    # Step F2: Generate Architectural Meta-Findings (NEW)
    # These correlations combine graph, CFG, and security findings for deeper insights
    meta_findings: list[dict[str, Any]] = []
    meta_registry: dict[tuple[Any, ...], dict[str, Any]] = {}
    meta_stats = {'attempted': 0, 'added': 0, 'merged': 0}

    def register_meta(
        entry: dict[str, Any],
        key: tuple[Any, ...],
        *,
        merge: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
        log_fn: Callable[[dict[str, Any]], str] | None = None,
    ) -> bool:
        """Add a meta finding once and merge subsequent duplicates."""

        entry.setdefault('supporting_count', entry.get('finding_count', 1))
        meta_stats['attempted'] += 1
        existing = meta_registry.get(key)
        if existing:
            meta_stats['merged'] += 1
            if merge:
                merge(existing, entry)
            else:
                existing['supporting_count'] = existing.get('supporting_count', 1) + entry.get('supporting_count', 1)
            return False

        meta_registry[key] = entry
        meta_findings.append(entry)
        meta_stats['added'] += 1
        if log_fn:
            print(log_fn(entry))
        return True

    # 1. ARCHITECTURAL_RISK_ESCALATION - Critical issues in architectural hotspots
    if hotspot_files and consolidated_findings:
        top_hotspots = sorted(
            hotspot_files.values(),
            key=lambda x: x.get('score', x.get('total_connections', 0)),
            reverse=True,
        )[:5]

        for hotspot in top_hotspots:
            hotspot_file = hotspot.get('file') or hotspot.get('id')
            if not hotspot_file or str(hotspot_file).startswith('external::'):
                continue

            critical_in_hotspot = [
                f for f in consolidated_findings
                if f.get('file') == hotspot_file and f.get('severity', '').lower() in ['critical', 'high']
            ]

            if critical_in_hotspot:
                hotspot_score = hotspot.get('score', hotspot.get('total_connections', 0))
                hotspot_issue_count = sum(
                    f.get('duplicate_count', 1) for f in critical_in_hotspot
                )
                entry = {
                    'type': 'ARCHITECTURAL_RISK_ESCALATION',
                    'file': hotspot_file,
                    'severity': 'critical',
                    'message': (
                        f"Critical security issues in architectural hotspot "
                        f"(connectivity score: {hotspot_score:.2f})"
                    ),
                    'description': (
                        f"File {hotspot_file} is a key architectural component with "
                        f"{hotspot_issue_count} critical/high issues. Changes here affect many other components."
                    ),
                    'finding_count': hotspot_issue_count,
                    'hotspot_in_degree': hotspot.get('in_degree', 0),
                    'hotspot_out_degree': hotspot.get('out_degree', 0),
                    'hotspot_total_connections': hotspot.get('total_connections', hotspot_score),
                    'hotspot_centrality': hotspot.get('centrality', 0),
                    'sample_findings': critical_in_hotspot[:3],
                }

                register_meta(
                    entry,
                    ('ARCHITECTURAL_RISK_ESCALATION', hotspot_file),
                    log_fn=lambda e, hf=hotspot_file: (
                        f"[FCE] Meta-finding: Critical issues in hotspot {hf[:50]}"
                    ),
                )

    # 2. SYSTEMIC_DEBT_CLUSTER - Multiple issues in circular dependencies
    if cycles and consolidated_findings:
        for i, cycle in enumerate(cycles[:5]):
            cycle_files = set(cycle.get('nodes', []))
            cycle_findings = [
                f for f in consolidated_findings
                if f.get('file') in cycle_files
            ]

            if len(cycle_findings) >= 5:
                severity_counts: dict[str, int] = {}
                for f in cycle_findings:
                    sev = f.get('severity', 'low').lower()
                    severity_counts[sev] = severity_counts.get(sev, 0) + f.get('duplicate_count', 1)

                total_cycle_findings = sum(
                    f.get('duplicate_count', 1) for f in cycle_findings
                )
                entry = {
                    'type': 'SYSTEMIC_DEBT_CLUSTER',
                    'severity': 'high',
                    'message': (
                        f"Circular dependency with {total_cycle_findings} issues across "
                        f"{cycle.get('size', len(cycle_files))} files"
                    ),
                    'description': (
                        f"Dependency cycle #{i + 1} contains multiple code issues, making refactoring risky and error-prone."
                    ),
                    'cycle_size': cycle.get('size', len(cycle_files)),
                    'finding_count': total_cycle_findings,
                    'severity_breakdown': severity_counts,
                    'cycle_files': list(cycle_files)[:10],
                    'sample_findings': cycle_findings[:3],
                }

                register_meta(
                    entry,
                    ('SYSTEMIC_DEBT_CLUSTER', tuple(sorted(cycle_files))),
                    log_fn=lambda e, size=cycle.get('size', len(cycle_files)): (
                        f"[FCE] Meta-finding: Debt cluster in {size}-file dependency cycle"
                    ),
                )

    # 3. COMPLEXITY_RISK_CORRELATION - Security issues in complex functions (aggregated)
    complexity_buckets: dict[tuple[str, str], dict[str, Any]] = {}
    if complex_functions and consolidated_findings:
        for finding in consolidated_findings:
            if finding.get('tool') not in ['taint', 'taint-insights', 'patterns', 'bandit']:
                continue

            file_path = finding.get('file', '')
            line_num = finding.get('line', 0)
            for func_key, func_data in complex_functions.items():
                if func_data.get('file') != file_path:
                    continue
                if not (func_data.get('start_line', 0) <= line_num <= func_data.get('end_line', float('inf'))):
                    continue

                complexity = func_data.get('complexity', 0)
                if complexity <= 20:
                    continue

                bucket_key = (file_path, func_data.get('function', 'unknown'))
                bucket = complexity_buckets.setdefault(
                    bucket_key,
                    {
                        'file': file_path,
                        'function': func_data.get('function', 'unknown'),
                        'complexity': complexity,
                        'has_loops': func_data.get('has_loops', False),
                        'block_count': func_data.get('block_count', 0),
                        'finding_count': 0,
                        'distinct_rules': set(),
                        'samples': [],
                    },
                )

                bucket['finding_count'] += finding.get('duplicate_count', 1)
                bucket['distinct_rules'].add(finding.get('rule'))
                if len(bucket['samples']) < 3:
                    bucket['samples'].append(finding)
                break

        for (file_path, function_name), bucket in complexity_buckets.items():
            entry = {
                'type': 'COMPLEXITY_RISK_CORRELATION',
                'file': file_path,
                'function': function_name,
                'severity': 'high',
                'message': (
                    f"{bucket['finding_count']} security findings in highly complex function "
                    f"(complexity: {bucket['complexity']})"
                ),
                'description': (
                    f"Function {function_name} has cyclomatic complexity of {bucket['complexity']}, "
                    "increasing remediation risk for the associated vulnerabilities."
                ),
                'complexity': bucket['complexity'],
                'has_loops': bucket['has_loops'],
                'block_count': bucket['block_count'],
                'finding_count': bucket['finding_count'],
                'distinct_rules': sorted(r for r in bucket['distinct_rules'] if r),
                'sample_findings': bucket['samples'],
            }

            register_meta(
                entry,
                ('COMPLEXITY_RISK_CORRELATION', file_path, function_name),
                log_fn=lambda e, fn=function_name: (
                    f"[FCE] Meta-finding: Security issues in complex function {fn[:30]}"
                ),
            )

    # 4. HIGH_CHURN_RISK_CORRELATION - High severity issues in volatile code (aggregated)
    if churn_files and consolidated_findings:
        all_churns = [f.get('commits_90d', 0) for f in churn_files.values()]
        if all_churns:
            all_churns_sorted = sorted(all_churns)
            percentile_90_idx = int(len(all_churns_sorted) * 0.9)
            percentile_90 = (
                all_churns_sorted[percentile_90_idx]
                if percentile_90_idx < len(all_churns_sorted)
                else all_churns_sorted[-1]
            )

            churn_buckets: dict[str, dict[str, Any]] = {}
            for finding in consolidated_findings:
                if finding.get('severity', '').lower() not in ['critical', 'high']:
                    continue

                file_path = finding.get('file', '')
                file_churn = churn_files.get(file_path)
                if not file_churn:
                    continue

                commits_90d = file_churn.get('commits_90d', 0)
                if commits_90d < percentile_90 or commits_90d == 0:
                    continue

                bucket = churn_buckets.setdefault(
                    file_path,
                    {
                        'file': file_path,
                        'commits_90d': commits_90d,
                        'unique_authors': file_churn.get('unique_authors', 0),
                        'days_since_modified': file_churn.get('days_since_modified', 0),
                        'finding_count': 0,
                        'distinct_rules': set(),
                        'sample_findings': [],
                    },
                )

                bucket['finding_count'] += finding.get('duplicate_count', 1)
                bucket['distinct_rules'].add(finding.get('rule'))
                if len(bucket['sample_findings']) < 3:
                    bucket['sample_findings'].append(finding)

            for file_path, bucket in churn_buckets.items():
                entry = {
                    'type': 'HIGH_CHURN_RISK_CORRELATION',
                    'file': file_path,
                    'severity': 'critical',
                    'message': (
                        f"{bucket['finding_count']} high-severity findings in volatile file "
                        f"({bucket['commits_90d']} commits in 90 days)"
                    ),
                    'description': (
                        f"File touched by {bucket['unique_authors']} authors and last modified "
                        f"{bucket['days_since_modified']} days ago. High churn increases regression risk."
                    ),
                    'commits_90d': bucket['commits_90d'],
                    'unique_authors': bucket['unique_authors'],
                    'days_since_modified': bucket['days_since_modified'],
                    'percentile': 90,
                    'finding_count': bucket['finding_count'],
                    'distinct_rules': sorted(r for r in bucket['distinct_rules'] if r),
                    'sample_findings': bucket['sample_findings'],
                }

                register_meta(
                    entry,
                    ('HIGH_CHURN_RISK_CORRELATION', file_path),
                    log_fn=lambda e, fp=file_path, commits=bucket['commits_90d']: (
                        f"[FCE] Meta-finding: High churn risk in {fp[:50]} ({commits} commits)"
                    ),
                )

    # 5. POORLY_TESTED_VULNERABILITY - Security issues in code with low test coverage
    if coverage_files and consolidated_findings:
        coverage_buckets: dict[tuple[str, int], dict[str, Any]] = {}
        for finding in consolidated_findings:
            if finding.get('tool') not in ['taint', 'taint-insights', 'patterns', 'bandit', 'semgrep', 'docker']:
                continue

            file_path = finding.get('file', '')
            file_coverage = coverage_files.get(file_path)
            if not file_coverage:
                continue

            coverage_pct = file_coverage.get('line_coverage_percent', 100)
            if coverage_pct >= 50:
                continue

            line_num = finding.get('line', 0)
            uncovered_lines = file_coverage.get('uncovered_lines', [])
            is_line_uncovered = line_num in uncovered_lines if uncovered_lines else True

            bucket_key = (file_path, line_num)
            bucket = coverage_buckets.setdefault(
                bucket_key,
                {
                    'file': file_path,
                    'line': line_num,
                    'coverage_pct': coverage_pct,
                    'is_line_uncovered': is_line_uncovered,
                    'finding_count': 0,
                    'distinct_rules': set(),
                    'sample_findings': [],
                },
            )

            bucket['finding_count'] += finding.get('duplicate_count', 1)
            bucket['distinct_rules'].add(finding.get('rule'))
            if len(bucket['sample_findings']) < 3:
                bucket['sample_findings'].append(finding)

        for (file_path, line_num), bucket in coverage_buckets.items():
            entry = {
                'type': 'POORLY_TESTED_VULNERABILITY',
                'file': file_path,
                'line': line_num,
                'severity': 'high',
                'message': (
                    f"{bucket['finding_count']} security findings in poorly tested code "
                    f"({bucket['coverage_pct']:.1f}% coverage)"
                ),
                'description': (
                    "Vulnerability resides in "
                    f"{'untested' if bucket['is_line_uncovered'] else 'partially tested'} code. "
                    "Fixes cannot be safely validated without adequate coverage."
                ),
                'line_coverage_percent': bucket['coverage_pct'],
                'is_line_uncovered': bucket['is_line_uncovered'],
                'finding_count': bucket['finding_count'],
                'distinct_rules': sorted(r for r in bucket['distinct_rules'] if r),
                'sample_findings': bucket['sample_findings'],
            }

            register_meta(
                entry,
                ('POORLY_TESTED_VULNERABILITY', file_path, line_num),
                log_fn=lambda e, fp=file_path, pct=bucket['coverage_pct']: (
                    f"[FCE] Meta-finding: Untested vulnerability in {fp[:50]} ({pct:.1f}% coverage)"
                ),
            )
    
    # Store meta-findings and correlation statistics
    results["correlations"]["meta_findings"] = meta_findings
    results["correlations"]["total_meta_findings"] = len(meta_findings)
    results["correlations"]["meta_stats"] = {
        **meta_stats,
        "unique": len(meta_findings),
    }

    if meta_stats.get('merged'):
        print(f"[FCE] Deduplicated {meta_stats['merged']} overlapping meta correlations")

    if meta_findings:
        print(f"[FCE] Generated {len(meta_findings)} architectural meta-findings")
        type_counts: dict[str, int] = {}
        for mf in meta_findings:
            mf_type = mf.get('type', 'unknown')
            type_counts[mf_type] = type_counts.get(mf_type, 0) + 1
        for mf_type, count in type_counts.items():
            print(f"[FCE]   - {mf_type}: {count}")
    else:
        print("[FCE] No architectural meta-findings generated (good architecture!)")
    
    # Store graph/CFG/metadata metrics in correlations for reference
    max_complexity = max((func.get('complexity', 0) for func in complex_functions.values()), default=0) if complex_functions else 0

    total_coverage = sum(f.get('line_coverage_percent', 0) for f in coverage_files.values())
    average_coverage = total_coverage / len(coverage_files) if coverage_files else 0

    results["correlations"]["graph_metrics"] = {
        "hotspot_count": len(hotspot_files),
        "cycle_count": len(cycles),
        "largest_cycle": cycles[0].get('size', 0) if cycles else 0,
        "complex_function_count": len(complex_functions),
        "max_complexity": max_complexity,
        # Metadata metrics (temporal and quality dimensions)
        "files_with_churn_data": len(churn_files),
        "files_with_coverage_data": len(coverage_files),
        "average_coverage": average_coverage
    }
    results["correlations"]["finding_dedupe"] = dedupe_stats

    # Store taint paths for downstream correlation and analysis
    results["correlations"]["taint_paths"] = taint_paths
    results["correlations"]["total_taint_paths"] = len(taint_paths)

    # Store workflow findings for downstream analysis
    results["correlations"]["github_workflows"] = workflow_findings
    results["correlations"]["total_workflow_findings"] = len(workflow_findings)

    # Store GraphQL findings for downstream analysis (Section 7)
    results["correlations"]["graphql_findings"] = graphql_findings
    results["correlations"]["total_graphql_findings"] = len(graphql_findings)

    # Step F3: GitHub Actions Workflow Correlation (Supply Chain + Taint)
    # Correlate workflow vulnerabilities with taint paths to identify compound risks
    # Example: PR script injection (workflow) + secret exposure (taint) = CRITICAL
    workflow_taint_correlations = []

    if workflow_findings and taint_paths:
        print("[FCE] Correlating workflow findings with taint paths...")

        # Build workflow file index for fast lookup
        workflow_by_file = {}
        for wf in workflow_findings:
            file_path = wf.get('file', '')
            if file_path not in workflow_by_file:
                workflow_by_file[file_path] = []
            workflow_by_file[file_path].append(wf)

        # For each taint path, check if it involves workflow-related files or secrets
        for taint in taint_paths:
            source_file = taint.get('source', {}).get('file', '')
            sink_file = taint.get('sink', {}).get('file', '')
            vuln_type = taint.get('vulnerability_type', '')
            severity = taint.get('severity', 'medium')

            # Check if taint path involves workflow files
            workflow_file_match = None
            if source_file in workflow_by_file:
                workflow_file_match = source_file
            elif sink_file in workflow_by_file:
                workflow_file_match = sink_file

            # Check if taint involves secrets (credential leaks, API keys, tokens)
            is_secret_leak = any(keyword in vuln_type.lower()
                                for keyword in ['secret', 'credential', 'token', 'key', 'password'])

            # Correlate: workflow vulnerability + secret taint path = compound risk
            if workflow_file_match and is_secret_leak:
                for wf in workflow_by_file[workflow_file_match]:
                    # Only correlate injection and permission vulnerabilities
                    if wf.get('category') in ['injection', 'access-control']:
                        correlation = {
                            'type': 'GITHUB_WORKFLOW_SECRET_LEAK',
                            'severity': 'critical',  # Elevate to CRITICAL
                            'workflow_file': workflow_file_match,
                            'workflow_name': wf.get('workflow_name', 'unknown'),
                            'workflow_rule': wf.get('rule', 'unknown'),
                            'workflow_severity': wf.get('severity', 'unknown'),
                            'taint_source': taint.get('source', {}),
                            'taint_sink': taint.get('sink', {}),
                            'taint_vulnerability_type': vuln_type,
                            'taint_severity': severity,
                            'message': (
                                f"Workflow vulnerability '{wf.get('rule')}' in {wf.get('workflow_name')} "
                                f"combined with taint path {vuln_type} creates compound supply-chain risk"
                            ),
                            'mitigation': (
                                "1. Fix workflow vulnerability to prevent untrusted execution, AND "
                                "2. Fix taint path to prevent secret leakage, AND "
                                "3. Implement secrets scanning and rotation policies"
                            )
                        }
                        workflow_taint_correlations.append(correlation)

    # Store workflow-taint correlations
    results["correlations"]["github_workflow_secret_leak"] = workflow_taint_correlations
    results["correlations"]["total_workflow_taint_correlations"] = len(workflow_taint_correlations)

    if workflow_taint_correlations:
        print(f"[FCE] Found {len(workflow_taint_correlations)} workflow + taint correlations (CRITICAL compound risks)")

    # Step G: Phase 5 - CFG Path-Based Correlation (Factual control flow relationships)
    path_clusters = []
    from theauditor.graph.path_correlator import PathCorrelator

    print("[FCE] Running CFG-based path correlation...")

    # Use the database path from the root
    full_db_path = Path(root_path) / db_path
    if full_db_path.exists():
        path_correlator = PathCorrelator(str(full_db_path))
        path_clusters = path_correlator.correlate(consolidated_findings)
        path_correlator.close()

        print(f"[FCE] Found {len(path_clusters)} high-confidence path clusters")

        # Log example of factual conditions for verification
        if path_clusters and path_clusters[0].get("conditions"):
            print(f"[FCE] Example cluster conditions: {path_clusters[0]['conditions']}")

        # Add to correlations with factual structure
        results["correlations"]["path_clusters"] = path_clusters
        results["correlations"]["total_path_clusters"] = len(path_clusters)

        # Calculate reduction in false positives (factual metric)
        if hotspots and path_clusters:
            # Count findings that were hotspots but not in path clusters
            hotspot_findings = set()
            for hotspot_data in hotspots.values():
                for finding in hotspot_data.get("findings", []):
                    hotspot_findings.add(f"{finding['file']}:{finding['line']}")

            path_findings = set()
            for cluster in path_clusters:
                for finding in cluster.get("findings", []):
                    path_findings.add(f"{finding['file']}:{finding['line']}")

            false_positives_removed = len(hotspot_findings - path_findings)
            if false_positives_removed > 0:
                print(f"[FCE] Path correlation filtered {false_positives_removed} potential false positives")
    else:
        print("[FCE] Skipping path correlation - database not found")
    
    # Step H: Finalization - Apply intelligent organization sorting
    from theauditor.utils.finding_priority import sort_findings, normalize_severity
    
    # CRITICAL: Normalize all severities BEFORE sorting
    # This handles Docker's integer severity and ESLint's "error" strings
    if results.get("all_findings"):
        # First pass: normalize severity in-place
        for finding in results["all_findings"]:
            original_severity = finding.get("severity")
            finding["severity"] = normalize_severity(original_severity)
            
            # Debug log for unusual severities (helps catch new formats)
            if original_severity and str(original_severity) != finding["severity"]:
                if isinstance(original_severity, int):
                    # Expected for Docker, don't log
                    pass
                else:
                    print(f"[FCE] Normalized severity: {original_severity} -> {finding['severity']}")
        
        # Second pass: sort using centralized logic
        results["all_findings"] = sort_findings(results["all_findings"])
        
        # Log sorting results for verification
        if results["all_findings"]:
            print(f"[FCE] Sorted {len(results['all_findings'])} findings")
            first = results["all_findings"][0]
            last = results["all_findings"][-1] if len(results["all_findings"]) > 1 else first
            print(f"[FCE] First: {first.get('severity')} from {first.get('tool')}")
            print(f"[FCE] Last: {last.get('severity')} from {last.get('tool')}")
    
    meta_count = len(meta_findings)
    factual_count = len(factual_clusters)
    path_cluster_count = len(path_clusters)
    test_failure_count = len(all_failures)
    correlated_failures = meta_count + factual_count + path_cluster_count + test_failure_count

    unique_findings_count = len(results.get("all_findings", []))
    results["summary"] = {
        "raw_rows": dedupe_stats.get("total_rows", unique_findings_count),
        "unique_findings": unique_findings_count,
        "duplicates_collapsed": dedupe_stats.get("duplicates_collapsed", 0),
        "test_failures": test_failure_count,
        "meta_findings": meta_count,
        "factual_clusters": factual_count,
        "path_clusters": path_cluster_count,
    }
    # Backwards compatibility alias
    results["summary"]["raw_findings"] = unique_findings_count
    if dedupe_stats.get("top_duplicates"):
        results["summary"]["top_duplicate_clusters"] = dedupe_stats["top_duplicates"]
    results["summary"]["meta_dedupe"] = meta_stats

    # Write results to individual JSON files
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Write main FCE results
    fce_path = raw_dir / "fce.json"
    with open(fce_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    # Write failures as separate file
    failures_path = raw_dir / "fce_failures.json"
    failures_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "meta_findings": meta_findings,
        "factual_clusters": factual_clusters,
        "path_clusters": path_clusters,
        "test_failures": all_failures,
    }
    with open(failures_path, 'w', encoding='utf-8') as f:
        json.dump(failures_payload, f, indent=2)

    # Count total correlated failures
    failures_found = correlated_failures

    # Return success structure
    return {
        "success": True,
        "failures_found": failures_found,
        "output_files": [str(fce_path), str(failures_path)],
        "results": results
    }
        
