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




def scan_all_findings(raw_dir: Path) -> list[dict[str, Any]]:
    """
    Scan ALL raw outputs for structured findings with line-level detail.
    Extract findings from JSON outputs with file, line, rule, and tool information.
    """
    all_findings = []
    
    for output_file in raw_dir.glob('*.json'):
        if not output_file.is_file():
            continue
            
        tool_name = output_file.stem
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures based on tool
            findings = []
            
            # Standard findings structure (lint.json, patterns.json, etc.)
            if isinstance(data, dict) and 'findings' in data:
                findings = data['findings']
            # Vulnerabilities structure
            elif isinstance(data, dict) and 'vulnerabilities' in data:
                findings = data['vulnerabilities']
            # Taint analysis structure
            elif isinstance(data, dict) and 'taint_paths' in data:
                for path in data['taint_paths']:
                    # Create a finding for each taint path
                    if 'file' in path and 'line' in path:
                        findings.append({
                            'file': path['file'],
                            'line': path['line'],
                            'rule': f"taint-{path.get('sink_type', 'unknown')}",
                            'message': path.get('message', 'Taint path detected')
                        })
            # Direct list of findings
            elif isinstance(data, list):
                findings = data
            # RCA/test results structure
            elif isinstance(data, dict) and 'failures' in data:
                findings = data['failures']
            
            # Process each finding
            for finding in findings:
                if isinstance(finding, dict):
                    # Ensure required fields exist
                    if 'file' in finding:
                        # Create standardized finding
                        standardized = {
                            'file': finding.get('file', ''),
                            'line': int(finding.get('line', 0)),
                            'rule': finding.get('rule', finding.get('code', finding.get('pattern', 'unknown'))),
                            'tool': finding.get('tool', tool_name),
                            'message': finding.get('message', ''),
                            'severity': finding.get('severity', 'warning')
                        }
                        all_findings.append(standardized)
                        
        except (json.JSONDecodeError, KeyError, TypeError):
            # Skip files that can't be parsed as JSON or don't have expected structure
            continue
        except Exception:
            # Skip files with other errors
            continue
    
    return all_findings


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
    db_path: str = "repo_index.db",
    timeout: int = 600,
    print_plan: bool = False,
) -> dict[str, Any]:
    """Run factual correlation engine - NO interpretation, just facts."""
    try:
        # Step A: Initialization
        raw_dir = Path(root_path) / ".pf" / "raw"
        results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "all_findings": [],
            "test_results": {},
            "correlations": {}
        }
        
        # Step B: Phase 1 - Gather All Findings
        if raw_dir.exists():
            results["all_findings"] = scan_all_findings(raw_dir)
        
        # Step B2: Load Optional Insights (ML predictions, etc.)
        insights_dir = Path(root_path) / ".pf" / "insights"
        if insights_dir.exists():
            # Load ML suggestions if available
            ml_path = insights_dir / "ml_suggestions.json"
            if ml_path.exists():
                try:
                    with open(ml_path) as f:
                        ml_data = json.load(f)
                    
                    # Convert ML predictions to correlatable findings
                    # ML has separate lists for root causes, risk scores, etc.
                    for root_cause in ml_data.get("likely_root_causes", [])[:5]:  # Top 5 root causes
                        if root_cause.get("score", 0) > 0.7:
                            results["all_findings"].append({
                                "file": root_cause["path"],
                                "line": 0,  # ML doesn't provide line-level predictions
                                "rule": "ML_ROOT_CAUSE",
                                "tool": "ml",
                                "message": f"ML predicts {root_cause['score']:.1%} probability as root cause",
                                "severity": "high"
                            })
                    
                    for risk_item in ml_data.get("risk", [])[:5]:  # Top 5 risky files
                        if risk_item.get("score", 0) > 0.7:
                            results["all_findings"].append({
                                "file": risk_item["path"],
                                "line": 0,
                                "rule": f"ML_RISK_{int(risk_item['score']*100)}",
                                "tool": "ml",
                                "message": f"ML predicts {risk_item['score']:.1%} risk score",
                                "severity": "high" if risk_item.get("score", 0) > 0.85 else "medium"
                            })
                except (json.JSONDecodeError, KeyError):
                    pass  # ML insights are optional, continue if they fail
            
            # Load taint severity insights if available  
            taint_severity_path = insights_dir / "taint_severity.json"
            if taint_severity_path.exists():
                try:
                    with open(taint_severity_path) as f:
                        taint_data = json.load(f)
                    
                    # Add severity-enhanced taint findings
                    for item in taint_data.get("severity_analysis", []):
                        if item.get("severity") in ["critical", "high"]:
                            results["all_findings"].append({
                                "file": item.get("file", ""),
                                "line": item.get("line", 0),
                                "rule": f"TAINT_{item.get('vulnerability_type', 'UNKNOWN').upper().replace(' ', '_')}",
                                "tool": "taint-insights",
                                "message": f"{item.get('vulnerability_type')} with {item.get('severity')} severity",
                                "severity": item.get("severity")
                            })
                except (json.JSONDecodeError, KeyError):
                    pass  # Insights are optional
        
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
        
        # Step G: Finalization - Apply intelligent organization sorting
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
        # Step H: Error Handling
        return {
            "success": False,
            "failures_found": 0,
            "error": str(e)
        }
