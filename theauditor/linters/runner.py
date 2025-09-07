"""Linter runner module - executes linter subprocesses."""

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

# Import our custom temp manager to avoid WSL2/Windows issues
from theauditor.utils.temp_manager import TempManager

# Detect if running on Windows for subprocess shell handling
IS_WINDOWS = platform.system() == "Windows"

# Note: Path quoting is NOT needed when using shell=False (which we now use everywhere).
# subprocess.run() with shell=False passes arguments directly to the OS without 
# shell interpretation, so paths with spaces work correctly without quotes.


def run_linter(
    tool: str,
    command: list[str],
    root_path: str,
    workset_files: set[str],
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Run a linter and parse its output.

    Returns:
        Tuple of (findings, ast_data) where ast_data maps file paths to AST objects
    """
    findings = []
    ast_data = {}

    try:
        # Add workset files to command if tool supports it
        if tool in ["eslint", "ruff", "mypy", "prettier", "black", "bandit"]:
            # Filter files by appropriate extension for each tool
            if tool in ["ruff", "mypy", "black", "bandit"]:
                # Python linters - only process .py files
                file_args = [f for f in workset_files if f.endswith('.py')]
                # Skip Python linters entirely if no Python files in workset
                if not file_args:
                    # Silent skip - no Python files to lint
                    return [], {}
            elif tool == "eslint":
                # JavaScript/TypeScript linter
                file_args = []
                has_standard_structure = False
                
                for f in workset_files:
                    if f.endswith(('.js', '.jsx', '.ts', '.tsx', '.mjs')):
                        normalized = f.replace('\\', '/')
                        
                        # Professional structures: /src/ anywhere (monorepo + traditional)
                        if '/src/' in normalized:
                            has_standard_structure = True
                            # Exclude obvious non-source files with more robust path-based exclusions
                            if not any(excluded_path in normalized for excluded_path in [
                                '/config/', '/scripts/', '/migrations/', '/seeders/',
                                '.config.', '.test.', '.spec.',
                                '/node_modules/', '/dist/', '/build/', '/.next/', '/.nuxt/'
                            ]):
                                file_args.append(f)
                
                # Fallback for non-standard projects
                if not file_args and not has_standard_structure:
                    print("\n" + "="*60)
                    print("WARNING: NON-STANDARD PROJECT STRUCTURE DETECTED")
                    print("="*60)
                    print("This project does not follow conventional src/ directory structure.")
                    print("TheAuditor will attempt to lint ALL JavaScript files.")
                    print("This is HIGH RISK and may produce incorrect results.")
                    print("Consider restructuring your project to use:")
                    print("  - frontend/src/ and backend/src/ (traditional)")
                    print("  - packages/*/src/ or apps/*/src/ (monorepo)")
                    print("="*60 + "\n")
                    
                    # Just grab everything and pray
                    for f in workset_files:
                        if f.endswith(('.js', '.jsx', '.ts', '.tsx', '.mjs')):
                            normalized = f.replace('\\', '/')
                            # At least skip the absolute garbage
                            if not any(x in normalized.lower() for x in [
                                '/node_modules/', '/dist/', '/build/', '/.git/'
                            ]):
                                file_args.append(f)
            elif tool == "prettier":
                # Prettier can handle many file types - focus on source code only
                file_args = [f for f in workset_files if f.endswith(('.js', '.jsx', '.ts', '.tsx', '.json', '.css', '.scss', '.html'))]
            else:
                # Default: use all files
                file_args = list(workset_files)
            
            if not file_args:
                return [], {}
            
            # Check if we need to chunk for Windows command line limit
            CHUNK_SIZE = 50  # Safe for 8KB Windows limit
            # Enable chunking for all tools that accept file lists
            all_chunking_tools = ["eslint", "prettier", "ruff", "mypy", "black", "bandit"]
            needs_chunking = tool in all_chunking_tools and len(file_args) > CHUNK_SIZE
            
            if needs_chunking:
                # We'll process in chunks - set up aggregation
                all_findings = []
                all_ast_data = {}
                total_chunks = (len(file_args) + CHUNK_SIZE - 1) // CHUNK_SIZE
                print(f"  Processing {len(file_args)} files in {total_chunks} chunks...")
                
                # Process each chunk
                for chunk_num, i in enumerate(range(0, len(file_args), CHUNK_SIZE), 1):
                    chunk_files = file_args[i:i + CHUNK_SIZE]
                    print(f"    Chunk {chunk_num}/{total_chunks}: {len(chunk_files)} files")
                    
                    # Normalize paths for JavaScript tools only
                    if tool in ["eslint", "prettier"]:
                        chunk_files = [f.replace('\\', '/') for f in chunk_files]
                    # Python tools use native path format
                    chunk_command = command + chunk_files
                    
                    # Execute this chunk
                    chunk_findings, chunk_ast_data = _execute_linter_command(
                        tool, chunk_command, root_path, workset_files, timeout
                    )
                    
                    # Aggregate results
                    all_findings.extend(chunk_findings)
                    all_ast_data.update(chunk_ast_data)
                
                return all_findings, all_ast_data
            else:
                # Single command execution (no chunking needed)
                if tool in ["eslint", "prettier"]:  # JS tools need normalized paths
                    file_args = [f.replace('\\', '/') for f in file_args]
                # Python tools use native path format
                command = command + file_args
                
                # Execute single command
                return _execute_linter_command(
                    tool, command, root_path, workset_files, timeout
                )
                
        elif tool in ["golangci-lint", "go-vet"]:
            # Go linters - filter to .go files if needed
            go_files = [f for f in workset_files if f.endswith('.go')]
            if not go_files:
                return [], {}
            # Note: These tools typically operate on packages/directories, not individual files
        elif tool == "tsc":
            # TypeScript compiler - check if we have any TS/TSX files
            ts_files = [f for f in workset_files if f.endswith(('.ts', '.tsx'))]
            if not ts_files:
                return [], {}
            # Note: tsc doesn't take file arguments - it uses tsconfig.json
        elif tool in ["spotbugs", "checkstyle"]:
            # Java linters - check if we have any Java files
            java_files = [f for f in workset_files if f.endswith('.java')]
            if not java_files:
                return [], {}
            # Note: Maven tools operate on the whole project
        
        # For non-chunked tools, execute directly
        return _execute_linter_command(tool, command, root_path, workset_files, timeout)

    except subprocess.TimeoutExpired:
        print(f"Warning: {tool} timed out after {timeout}s")
    except FileNotFoundError:
        print(f"Warning: {tool} not found, skipping")
    except Exception as e:
        print(f"Warning: Error running {tool}: {e}")

    return findings, ast_data


def _execute_linter_command(
    tool: str,
    command: list[str],
    root_path: str,
    workset_files: set[str],
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Execute a single linter command and parse its output.
    This is called once for non-chunked tools, multiple times for chunked tools.
    """
    findings = []
    ast_data = {}
    
    try:
        # Create debug log file when debug flag is set
        debug_log_path = None
        if os.environ.get("THEAUDITOR_DEBUG"):
            debug_log_path = Path(".pf") / "linter_debug.log"
            debug_log_path.parent.mkdir(exist_ok=True)
            
            # Log ground truth before execution
            debug_info = {
                "tool": tool,
                "command": command,
                "root_path": root_path,
                "cwd": os.getcwd(),
                "PATH": os.environ.get('PATH', ''),
                "NODE_PATH": os.environ.get('NODE_PATH', ''),
                "platform": platform.system(),
                "IS_WINDOWS": IS_WINDOWS,
                "workset_files_count": len(workset_files)
            }
            
            with open(debug_log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"[{tool}] Pre-execution debug at {os.path.basename(__file__)}:{_execute_linter_command.__name__}\n")
                f.write(json.dumps(debug_info, indent=2))
                f.write("\n")
        
        # Run the linter using our custom temp files to avoid buffer overflow and WSL2 issues
        stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(root_path, tool)
        
        with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
             open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
            
            # Use bundled Node.js for JavaScript tools on ALL platforms
            js_tools = ["eslint", "tsc", "prettier"]
            if tool in js_tools:
                # Find bundled Node.js runtime
                sandbox_base = Path(root_path) / ".auditor_venv" / ".theauditor_tools"
                node_runtime = sandbox_base / "node-runtime"
                
                # Platform-specific Node.js executable
                if IS_WINDOWS:
                    node_exe = node_runtime / "node.exe"
                else:
                    node_exe = node_runtime / "bin" / "node"
                
                if node_exe.exists():
                    # The command[0] is the .cmd or shell wrapper path
                    # We need to find the actual JavaScript entry point
                    # npm installs in node_modules/<package>/<entry>
                    
                    # Map tool to its JavaScript entry point
                    # These are the ACTUAL paths where npm installs them
                    node_modules = sandbox_base / "node_modules"
                    
                    if tool == "eslint":
                        # ESLint main entry is at node_modules/eslint/bin/eslint.js
                        js_script = node_modules / "eslint" / "bin" / "eslint.js"
                        # Fallback to lib/cli.js if bin doesn't exist (older versions)
                        if not js_script.exists():
                            js_script = node_modules / "eslint" / "lib" / "cli.js"
                    elif tool == "tsc":
                        # TypeScript compiler is at node_modules/typescript/lib/tsc.js
                        js_script = node_modules / "typescript" / "lib" / "tsc.js"
                    elif tool == "prettier":
                        # Prettier can be at different locations
                        # Try node_modules/prettier/bin/prettier.cjs first
                        js_script = node_modules / "prettier" / "bin" / "prettier.cjs"
                        if not js_script.exists():
                            # Try prettier.js
                            js_script = node_modules / "prettier" / "bin" / "prettier.js"
                        if not js_script.exists():
                            # Try the main entry
                            js_script = node_modules / "prettier" / "index.js"
                    
                    if js_script.exists():
                        # Build new command using bundled Node.js
                        # Direct execution: node script.js [args...]
                        command_to_run = [str(node_exe), str(js_script)] + command[1:]
                        use_shell = False  # No shell needed with direct execution
                        
                        if debug_log_path:
                            with open(debug_log_path, 'a', encoding='utf-8') as f:
                                f.write(f"[{tool}] Using bundled Node.js runtime\n")
                                f.write(f"  Node: {node_exe}\n")
                                f.write(f"  Script: {js_script}\n")
                                f.write(f"  Command: {command_to_run}\n")
                    else:
                        # Script not found - try to help debug
                        if debug_log_path:
                            with open(debug_log_path, 'a', encoding='utf-8') as f:
                                f.write(f"[{tool}] Script not found: {js_script}\n")
                                # List what actually exists to help debug
                                tool_dir = node_modules / tool.replace("tsc", "typescript")
                                if tool_dir.exists():
                                    f.write(f"[{tool}] Directory exists: {tool_dir}\n")
                                    try:
                                        files = list(tool_dir.rglob("*.js"))[:5]
                                        f.write(f"[{tool}] Found JS files: {files}\n")
                                    except:
                                        pass
                        print(f"ERROR: JavaScript entry point not found: {js_script}")
                        print(f"       Expected location: {js_script}")
                        print(f"       Run 'aud setup-claude --target .' to reinstall")
                        return [], {}
                else:
                    # No bundled Node.js - fail with clear error
                    if debug_log_path:
                        with open(debug_log_path, 'a', encoding='utf-8') as f:
                            f.write(f"[{tool}] Bundled Node.js not found at: {node_exe}\n")
                    print(f"WARNING: {tool} requires bundled Node.js runtime")
                    print(f"         Expected at: {node_exe}")
                    print(f"         Run 'aud setup-claude --target .' to install")
                    return [], {}
            else:
                # Non-JS tools: always use list-based execution
                command_to_run = command
                use_shell = False  # Never use shell
            
            # Log the actual command that will be executed
            if debug_log_path:
                with open(debug_log_path, 'a', encoding='utf-8') as f:
                    f.write(f"[{tool}] Actual command to execute:\n")
                    f.write(f"  Type: {type(command_to_run)}\n")
                    f.write(f"  Value: {command_to_run}\n")
                    f.write(f"  Shell: {use_shell}\n")
            
            result = subprocess.run(
                command_to_run,
                cwd=root_path,
                stdout=stdout_fp,
                stderr=stderr_fp,
                text=True,
                encoding='utf-8',
                errors='replace',  # Handle encoding errors gracefully
                timeout=timeout,
                shell=use_shell,  # Determined above based on tool and platform
            )
        
        with open(stdout_path, 'r', encoding='utf-8', errors='replace') as f:
            result.stdout = f.read()
        with open(stderr_path, 'r', encoding='utf-8', errors='replace') as f:
            result.stderr = f.read()
        
        # Log the result after execution
        if debug_log_path:
            with open(debug_log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{tool}] Post-execution results:\n")
                f.write(f"  Return code: {result.returncode}\n")
                f.write(f"  Stdout length: {len(result.stdout)} bytes\n")
                f.write(f"  Stderr length: {len(result.stderr)} bytes\n")
                if result.stdout:
                    f.write(f"  Stdout first 500 chars: {result.stdout[:500]}\n")
                if result.stderr:
                    f.write(f"  Stderr first 500 chars: {result.stderr[:500]}\n")
                f.write(f"{'='*60}\n")
        
        # Clean up temp files - best effort, don't fail if can't delete
        try:
            Path(stdout_path).unlink()
            Path(stderr_path).unlink()
        except (OSError, PermissionError):
            pass  # WSL2/Windows may hold locks

        # Import parsers dynamically to avoid circular imports
        from . import parsers

        # Parse output based on tool
        if tool == "eslint":
            findings, ast_data = parsers.parse_eslint_output(result.stdout, workset_files)
        elif tool == "ruff":
            findings = parsers.parse_ruff_output(result.stdout, workset_files)
        elif tool == "mypy":
            findings = parsers.parse_mypy_output(result.stdout, workset_files)
        elif tool == "tsc":
            findings = parsers.parse_tsc_output(result.stdout, workset_files)
        elif tool == "prettier":
            findings = parsers.parse_prettier_output(result.stdout, result.stderr, workset_files)
        elif tool == "black":
            findings = parsers.parse_black_output(result.stdout, result.stderr, workset_files)
        elif tool == "bandit":
            findings = parsers.parse_bandit_output(result.stdout, workset_files)
        elif tool == "golangci-lint":
            findings = parsers.parse_golangci_output(result.stdout, workset_files)
        elif tool == "go-vet":
            findings = parsers.parse_go_vet_output(result.stderr, workset_files)
        elif tool in ["spotbugs", "checkstyle"]:
            findings = parsers.parse_maven_output(tool, result.stdout, workset_files)

    except subprocess.TimeoutExpired:
        print(f"Warning: {tool} timed out after {timeout}s")
    except FileNotFoundError:
        print(f"Warning: {tool} not found, skipping")
    except Exception as e:
        print(f"Warning: Error running {tool}: {e}")

    return findings, ast_data