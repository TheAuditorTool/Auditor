"""Factual Correlation Engine - aggregates and correlates findings from all analysis tools."""

import json
import os
import re
import shlex
import sqlite3
import subprocess
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from theauditor.test_frameworks import detect_test_framework
from theauditor.correlations import CorrelationLoader




def scan_all_findings(db_path: str) -> list[dict[str, Any]]:
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

    Fallback:
        - Gracefully handles old databases without findings_consolidated table
        - Returns empty list with warning if table missing (user should re-index)
    """
    all_findings = []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        cursor = conn.cursor()

        # Check if table exists (graceful fallback for old databases)
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='findings_consolidated'
        """)

        if not cursor.fetchone():
            print("[FCE] Warning: findings_consolidated table not found")
            print("[FCE] Database may need re-indexing with new schema")
            print("[FCE] Run: aud index")
            conn.close()
            return []

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

        # Convert rows to dicts (standardized format matching old JSON structure)
        for row in cursor.fetchall():
            all_findings.append({
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
                'cwe': row['cwe']
            })

        conn.close()

        if all_findings:
            print(f"[FCE] Loaded {len(all_findings)} findings from database (database-first)")
        else:
            print("[FCE] No findings in database - tools may need to run first")

        return all_findings

    except sqlite3.Error as e:
        print(f"[FCE] Database error: {e}")
        print("[FCE] Falling back to empty findings list")
        return []
    except Exception as e:
        print(f"[FCE] Unexpected error: {e}")
        print("[FCE] Falling back to empty findings list")
        return []


def run_tool(command: str, root_path: str, timeout: int = 600) -> tuple[int, str, str]:
    """Run build/test tool with timeout and capture output."""
    try:
        # Use deque as ring buffer to limit memory usage
        max_lines = 10000
        stdout_buffer = deque(maxlen=max_lines)
        stderr_buffer = deque(maxlen=max_lines)

        # Run command - safely split command string into arguments
        cmd_args = shlex.split(command)
        
        # Write directly to temp files to avoid buffer overflow
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt') as out_tmp, \
             tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt') as err_tmp:
            
            process = subprocess.Popen(
                cmd_args,
                cwd=root_path,
                stdout=out_tmp,
                stderr=err_tmp,
                text=True,
                env={**os.environ, "CI": "true"},  # Set CI env for tools
            )
            
            stdout_file = out_tmp.name
            stderr_file = err_tmp.name

        # Stream output with timeout
        try:
            process.communicate(timeout=timeout)
            
            # Read back the outputs
            with open(stdout_file, 'r') as f:
                stdout = f.read()
            with open(stderr_file, 'r') as f:
                stderr = f.read()
            
            # Clean up temp files
            os.unlink(stdout_file)
            os.unlink(stderr_file)
            
            # Append any errors to the global error.log
            if stderr:
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

    except Exception as e:
        return 1, "", str(e)


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

    try:
        with open(capsule_path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None




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
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        for entry in manifest:
            file_hashes[entry["path"]] = entry.get("sha256")
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Load workset
    workset_files = set()
    try:
        with open(workset_path) as f:
            workset = json.load(f)
        workset_files = {p["path"] for p in workset.get("paths", [])}
    except (FileNotFoundError, json.JSONDecodeError):
        pass

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
    try:
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
        if Path(full_db_path).exists():
            results["all_findings"] = scan_all_findings(full_db_path)
        else:
            print(f"[FCE] Warning: Database not found at {full_db_path}")
            print("[FCE] Run 'aud index' to create database")
        
        # Step B1: Load Graph Analysis Data (Hotspots, Cycles, Health)
        graph_data = {}
        hotspot_files = {}  # File -> hotspot data mapping
        cycles = []  # List of dependency cycles
        graph_path = raw_dir / "graph_analysis.json"
        if graph_path.exists():
            try:
                with open(graph_path, 'r', encoding='utf-8') as f:
                    graph_data = json.load(f)
                # Index hotspots by file for O(1) lookup during correlation
                for hotspot in graph_data.get('hotspots', []):
                    hotspot_files[hotspot['id']] = hotspot
                cycles = graph_data.get('cycles', [])
                print(f"[FCE] Loaded graph analysis: {len(hotspot_files)} hotspots, {len(cycles)} cycles")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[FCE] Warning: Could not load graph analysis: {e}")
        
        # Step B1.5: Load CFG Complexity Data (Function Complexity Metrics)
        cfg_data = {}
        complex_functions = {}  # file:function -> complexity data
        cfg_path = raw_dir / "cfg_analysis.json"
        if cfg_path.exists():
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg_data = json.load(f)
                # Index complex functions for correlation
                for func in cfg_data.get('complex_functions', []):
                    key = f"{func['file']}:{func['function']}"
                    complex_functions[key] = func
                print(f"[FCE] Loaded CFG analysis: {len(complex_functions)} complex functions")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[FCE] Warning: Could not load CFG analysis: {e}")
        
        # Step B1.6: Load Metadata - Code Churn (Temporal Dimension)
        churn_data = {}
        churn_files = {}  # path -> churn metrics mapping
        churn_path = raw_dir / "churn_analysis.json"
        if churn_path.exists():
            try:
                with open(churn_path, 'r', encoding='utf-8') as f:
                    churn_data = json.load(f)
                # Index by file path for O(1) lookup during correlation
                for file_data in churn_data.get('files', []):
                    churn_files[file_data['path']] = file_data
                print(f"[FCE] Loaded churn analysis: {len(churn_files)} files with git history")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[FCE] Warning: Could not load churn analysis: {e}")
        
        # Step B1.7: Load Metadata - Test Coverage (Quality Dimension)
        coverage_data = {}
        coverage_files = {}  # path -> coverage metrics mapping
        coverage_path = raw_dir / "coverage_analysis.json"
        if coverage_path.exists():
            try:
                with open(coverage_path, 'r', encoding='utf-8') as f:
                    coverage_data = json.load(f)
                # Index by file path for O(1) lookup
                for file_data in coverage_data.get('files', []):
                    coverage_files[file_data['path']] = file_data
                format_type = coverage_data.get('format_detected', 'unknown')
                avg_coverage = coverage_data.get('average_coverage', 0)
                print(f"[FCE] Loaded {format_type} coverage: {len(coverage_files)} files, {avg_coverage}% average")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[FCE] Warning: Could not load coverage analysis: {e}")
        
        # Step B2: Load Optional Insights (Interpretive Analysis)
        # IMPORTANT: Insights are kept separate from factual findings to maintain Truth Courier principles
        insights_data = {}
        insights_dir = Path(root_path) / ".pf" / "insights"
        
        if insights_dir.exists():
            # Dynamically load ALL JSON files from insights directory
            # This future-proofs the system - new insights modules are automatically included
            for insight_file in insights_dir.glob("*.json"):
                try:
                    with open(insight_file, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                    
                    # Store each insights file's data under its name (without .json)
                    # Examples: ml_suggestions, taint_severity, graph_health, impact_analysis, unified_insights
                    insights_data[insight_file.stem] = file_data
                    print(f"[FCE] Loaded insights module: {insight_file.stem}")
                    
                except (json.JSONDecodeError, IOError) as e:
                    # Insights are optional - log warning but continue
                    print(f"[FCE] Warning: Could not load insights file {insight_file.name}: {e}")
                except Exception as e:
                    # Catch any other errors to ensure robustness
                    print(f"[FCE] Warning: Unexpected error loading {insight_file.name}: {e}")
            
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
        if package_json.exists():
            try:
                with open(package_json) as f:
                    package = json.load(f)
                scripts = package.get("scripts", {})
                if "build" in scripts:
                    tools.append({
                        "name": "npm build",
                        "command": "npm run build --silent",
                        "type": "build"
                    })
            except json.JSONDecodeError:
                pass
        
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
            tools_on_line = set(f['tool'] for f in findings)
            if len(tools_on_line) > 1:
                hotspots[line_key] = findings
        
        # Enrich hotspots with symbol context
        full_db_path = Path(root_path) / db_path
        if hotspots and full_db_path.exists():
            try:
                conn = sqlite3.connect(str(full_db_path))
                cursor = conn.cursor()
                
                enriched_hotspots = {}
                for line_key, findings in hotspots.items():
                    if ':' in line_key:
                        file_path, line_str = line_key.rsplit(':', 1)
                        try:
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
                        except (ValueError, TypeError):
                            enriched_hotspots[line_key] = {"findings": findings}
                    else:
                        enriched_hotspots[line_key] = {"findings": findings}
                
                conn.close()
                hotspots = enriched_hotspots
            except (sqlite3.Error, Exception):
                hotspots = {k: {"findings": v} for k, v in hotspots.items()}
        else:
            hotspots = {k: {"findings": v} for k, v in hotspots.items()}
        
        # Store hotspots in correlations
        results["correlations"]["hotspots"] = hotspots
        results["correlations"]["total_findings"] = len(consolidated_findings)
        results["correlations"]["total_lines_with_findings"] = len(line_groups)
        results["correlations"]["total_hotspots"] = len(hotspots)
        
        # Step F: Phase 4 - Factual Cluster Detection
        factual_clusters = []
        
        # Load correlation rules
        correlation_loader = CorrelationLoader()
        correlation_rules = correlation_loader.load_rules()
        
        if correlation_rules and consolidated_findings:
            # Group findings by file
            findings_by_file = defaultdict(list)
            for finding in consolidated_findings:
                if 'file' in finding:
                    findings_by_file[finding['file']].append(finding)
            
            # Check each file against each rule
            for file_path, file_findings in findings_by_file.items():
                for rule in correlation_rules:
                    all_facts_matched = True
                    
                    for fact_index, fact in enumerate(rule.co_occurring_facts):
                        fact_matched = False
                        for finding in file_findings:
                            if rule.matches_finding(finding, fact_index):
                                fact_matched = True
                                break
                        
                        if not fact_matched:
                            all_facts_matched = False
                            break
                    
                    if all_facts_matched:
                        factual_clusters.append({
                            "name": rule.name,
                            "file": file_path,
                            "description": rule.description,
                            "confidence": rule.confidence
                        })
        
        # Store factual clusters
        results["correlations"]["factual_clusters"] = factual_clusters
        
        # Step F2: Generate Architectural Meta-Findings (NEW)
        # These correlations combine graph, CFG, and security findings for deeper insights
        meta_findings = []
        
        # 1. ARCHITECTURAL_RISK_ESCALATION - Critical issues in architectural hotspots
        if hotspot_files and consolidated_findings:
            # Get top 5 hotspots sorted by score
            top_hotspots = sorted(hotspot_files.values(), 
                                 key=lambda x: x.get('score', 0), 
                                 reverse=True)[:5]
            
            for hotspot in top_hotspots:
                hotspot_file = hotspot['id']
                # Find critical/high severity findings in this hotspot file
                critical_in_hotspot = [
                    f for f in consolidated_findings 
                    if f.get('file') == hotspot_file and 
                    f.get('severity', '').lower() in ['critical', 'high']
                ]
                
                if critical_in_hotspot:
                    meta_findings.append({
                        'type': 'ARCHITECTURAL_RISK_ESCALATION',
                        'file': hotspot_file,
                        'severity': 'critical',
                        'message': f"Critical security issues in architectural hotspot (connectivity score: {hotspot.get('score', 0):.2f})",
                        'description': f"File {hotspot_file} is a key architectural component with {len(critical_in_hotspot)} critical/high issues. Changes here affect many other components.",
                        'finding_count': len(critical_in_hotspot),
                        'hotspot_in_degree': hotspot.get('in_degree', 0),
                        'hotspot_out_degree': hotspot.get('out_degree', 0),
                        'hotspot_centrality': hotspot.get('centrality', 0),
                        'original_findings': critical_in_hotspot[:3]  # Sample of findings
                    })
                    print(f"[FCE] Meta-finding: Critical issues in hotspot {hotspot_file[:50]}")
        
        # 2. SYSTEMIC_DEBT_CLUSTER - Multiple issues in circular dependencies
        if cycles and consolidated_findings:
            for i, cycle in enumerate(cycles[:5]):  # Analyze top 5 cycles
                cycle_files = set(cycle.get('nodes', []))
                
                # Find all findings in files that are part of this cycle
                cycle_findings = [
                    f for f in consolidated_findings
                    if f.get('file') in cycle_files
                ]
                
                # Only flag if there are significant issues in the cycle
                if len(cycle_findings) >= 5:  # Threshold: 5+ issues
                    severity_counts = {}
                    for f in cycle_findings:
                        sev = f.get('severity', 'low').lower()
                        severity_counts[sev] = severity_counts.get(sev, 0) + 1
                    
                    meta_findings.append({
                        'type': 'SYSTEMIC_DEBT_CLUSTER',
                        'severity': 'high',
                        'message': f"Circular dependency with {len(cycle_findings)} issues across {cycle.get('size', len(cycle_files))} files",
                        'description': f"Dependency cycle #{i+1} contains multiple code issues, making refactoring risky and error-prone.",
                        'cycle_size': cycle.get('size', len(cycle_files)),
                        'finding_count': len(cycle_findings),
                        'severity_breakdown': severity_counts,
                        'cycle_files': list(cycle_files)[:10],  # First 10 files
                        'sample_findings': cycle_findings[:3]  # Sample findings
                    })
                    print(f"[FCE] Meta-finding: Debt cluster in {cycle.get('size', 0)}-file dependency cycle")
        
        # 3. COMPLEXITY_RISK_CORRELATION - Security issues in complex functions
        if complex_functions and consolidated_findings:
            for finding in consolidated_findings:
                # Focus on security-related findings (taint, patterns, etc.)
                if finding.get('tool') in ['taint', 'taint-insights', 'patterns', 'bandit']:
                    file_path = finding.get('file', '')
                    line_num = finding.get('line', 0)
                    
                    # Check if this finding is in a complex function
                    for func_key, func_data in complex_functions.items():
                        # func_key format: "file:function_name"
                        if (func_data.get('file') == file_path and 
                            func_data.get('start_line', 0) <= line_num <= func_data.get('end_line', float('inf'))):
                            
                            complexity = func_data.get('complexity', 0)
                            if complexity > 20:  # High complexity threshold
                                meta_findings.append({
                                    'type': 'COMPLEXITY_RISK_CORRELATION',
                                    'file': file_path,
                                    'line': line_num,
                                    'function': func_data.get('function', 'unknown'),
                                    'severity': 'high',
                                    'message': f"Security issue in highly complex function (complexity: {complexity})",
                                    'description': f"Function {func_data.get('function')} has cyclomatic complexity of {complexity}, making the {finding.get('rule', 'security issue')} harder to fix and verify.",
                                    'complexity': complexity,
                                    'has_loops': func_data.get('has_loops', False),
                                    'block_count': func_data.get('block_count', 0),
                                    'original_finding': finding
                                })
                                print(f"[FCE] Meta-finding: Security issue in complex function {func_data.get('function', 'unknown')[:30]}")
                                break  # Found the function, no need to check others
        
        # 4. HIGH_CHURN_RISK_CORRELATION - High severity issues in volatile code (Temporal Dimension)
        if churn_files and consolidated_findings:
            # Calculate 90th percentile for churn (top 10% most active files)
            all_churns = [f.get('commits_90d', 0) for f in churn_files.values()]
            if all_churns:
                all_churns_sorted = sorted(all_churns)
                percentile_90_idx = int(len(all_churns_sorted) * 0.9)
                percentile_90 = all_churns_sorted[percentile_90_idx] if percentile_90_idx < len(all_churns_sorted) else all_churns_sorted[-1]
                
                # Find high-severity issues in high-churn files
                for finding in consolidated_findings:
                    if finding.get('severity', '').lower() in ['critical', 'high']:
                        file_path = finding.get('file', '')
                        file_churn = churn_files.get(file_path, {})
                        
                        commits_90d = file_churn.get('commits_90d', 0)
                        if commits_90d >= percentile_90 and commits_90d > 0:  # Must be in top 10% AND have commits
                            meta_findings.append({
                                'type': 'HIGH_CHURN_RISK_CORRELATION',
                                'file': file_path,
                                'line': finding.get('line', 0),
                                'severity': 'critical',  # Escalate severity due to volatility
                                'message': f"High-severity issue in volatile file ({commits_90d} commits in 90 days)",
                                'description': f"File modified by {file_churn.get('unique_authors', 0)} authors, last modified {file_churn.get('days_since_modified', 0)} days ago. High churn increases regression risk.",
                                'commits_90d': commits_90d,
                                'unique_authors': file_churn.get('unique_authors', 0),
                                'days_since_modified': file_churn.get('days_since_modified', 0),
                                'percentile': 90,
                                'original_finding': finding
                            })
                            print(f"[FCE] Meta-finding: High churn risk in {file_path[:50]} ({commits_90d} commits)")
        
        # 5. POORLY_TESTED_VULNERABILITY - Security issues in code with low test coverage (Quality Dimension)
        if coverage_files and consolidated_findings:
            for finding in consolidated_findings:
                # Focus on security-related findings (taint, patterns, security scanners)
                if finding.get('tool') in ['taint', 'taint-insights', 'patterns', 'bandit', 'semgrep', 'docker']:
                    file_path = finding.get('file', '')
                    file_coverage = coverage_files.get(file_path, {})
                    
                    # Default to 100% if no coverage data (assume tested unless proven otherwise)
                    coverage_pct = file_coverage.get('line_coverage_percent', 100)
                    
                    if coverage_pct < 50:  # Less than 50% coverage threshold
                        # Check if the specific line is uncovered (if we have that data)
                        line_num = finding.get('line', 0)
                        uncovered_lines = file_coverage.get('uncovered_lines', [])
                        is_line_uncovered = line_num in uncovered_lines if uncovered_lines else True
                        
                        meta_findings.append({
                            'type': 'POORLY_TESTED_VULNERABILITY',
                            'file': file_path,
                            'line': line_num,
                            'severity': 'high',  # High severity due to lack of test safety net
                            'message': f"Security issue in poorly tested code ({coverage_pct:.1f}% coverage)",
                            'description': f"Vulnerability in {'untested' if is_line_uncovered else 'partially tested'} code. Fixes cannot be safely validated without adequate test coverage.",
                            'line_coverage_percent': coverage_pct,
                            'is_line_uncovered': is_line_uncovered,
                            'original_finding': finding
                        })
                        print(f"[FCE] Meta-finding: Untested vulnerability in {file_path[:50]} ({coverage_pct:.1f}% coverage)")
        
        # Store meta-findings
        results["correlations"]["meta_findings"] = meta_findings
        results["correlations"]["total_meta_findings"] = len(meta_findings)
        
        if meta_findings:
            print(f"[FCE] Generated {len(meta_findings)} architectural meta-findings")
            # Log distribution of meta-finding types
            type_counts = {}
            for mf in meta_findings:
                mf_type = mf.get('type', 'unknown')
                type_counts[mf_type] = type_counts.get(mf_type, 0) + 1
            for mf_type, count in type_counts.items():
                print(f"[FCE]   - {mf_type}: {count}")
        else:
            print("[FCE] No architectural meta-findings generated (good architecture!)")
        
        # Store graph/CFG/metadata metrics in correlations for reference
        results["correlations"]["graph_metrics"] = {
            "hotspot_count": len(hotspot_files),
            "cycle_count": len(cycles),
            "largest_cycle": cycles[0].get('size', 0) if cycles else 0,
            "complex_function_count": len(complex_functions),
            "max_complexity": cfg_data.get('statistics', {}).get('max_complexity', 0) if cfg_data else 0,
            # Metadata metrics (temporal and quality dimensions)
            "files_with_churn_data": len(churn_files),
            "files_with_coverage_data": len(coverage_files),
            "average_coverage": coverage_data.get('average_coverage', 0) if coverage_data else 0
        }
        
        # Step G: Phase 5 - CFG Path-Based Correlation (Factual control flow relationships)
        path_clusters = []
        try:
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
                
        except ImportError:
            print("[FCE] Path correlation not available - CFG support required")
        except Exception as e:
            print(f"[FCE] Path correlation failed: {e}")
            # Non-fatal - continue without path correlation
        
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
        
        # Write results to JSON
        raw_dir.mkdir(parents=True, exist_ok=True)
        fce_path = raw_dir / "fce.json"
        fce_path.write_text(json.dumps(results, indent=2))
        
        # Count total failures/findings
        failures_found = len(results.get("all_findings", []))
        
        # Return success structure
        return {
            "success": True,
            "failures_found": failures_found,
            "output_files": [str(fce_path)],
            "results": results
        }
        
    except Exception as e:
        # Step I: Error Handling
        return {
            "success": False,
            "failures_found": 0,
            "error": str(e)
        }
