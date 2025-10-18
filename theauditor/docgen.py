"""Documentation generator from index and capsules (optional feature)."""

import hashlib
import json
import platform
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from theauditor import __version__


def is_source_file(file_path: str) -> bool:
    """Check if a file is a source code file (not test, config, or docs)."""
    path = Path(file_path)
    
    # Skip test files and directories
    if any(part in ['test', 'tests', '__tests__', 'spec', 'fixtures', 'fixture_repo', 'test_scaffold'] for part in path.parts):
        return False
    if path.name.startswith('test_') or path.name.endswith('_test.py') or '.test.' in path.name or '.spec.' in path.name:
        return False
    if 'test' in str(path).lower() and any(ext in str(path).lower() for ext in ['.spec.', '_test.', 'test_']):
        return False
    
    # Skip documentation
    if path.suffix.lower() in ['.md', '.rst', '.txt']:
        return False
    
    # Skip configuration files
    config_files = {
        '.gitignore', '.gitattributes', '.editorconfig',
        'pyproject.toml', 'setup.py', 'setup.cfg',
        'package.json', 'package-lock.json', 'yarn.lock',
        'package-template.json', 'tsconfig.json',
        'Makefile', 'makefile', 'requirements.txt',
        'Dockerfile', 'docker-compose.yml', '.dockerignore',
        'manifest.json', 'repo_index.db'
    }
    if path.name.lower() in config_files:
        return False
    
    # Skip build artifacts and caches
    skip_dirs = {'docs', 'documentation', 'examples', 'samples', 'schemas'}
    if any(part.lower() in skip_dirs for part in path.parts):
        return False
    
    return True


def load_manifest(manifest_path: str) -> tuple[list[dict], str]:
    """Load manifest and compute its hash."""
    with open(manifest_path, "rb") as f:
        content = f.read()
        manifest_hash = hashlib.sha256(content).hexdigest()

    manifest = json.loads(content)
    return manifest, manifest_hash


def load_workset(workset_path: str) -> set[str]:
    """Load workset file paths."""
    if not Path(workset_path).exists():
        return set()

    with open(workset_path) as f:
        workset = json.load(f)
    return {p["path"] for p in workset.get("paths", [])}


def load_capsules(capsules_dir: str, workset_paths: set[str] | None = None) -> list[dict]:
    """Load capsules, optionally filtered by workset."""
    capsules = []
    capsules_path = Path(capsules_dir)

    if not capsules_path.exists():
        raise RuntimeError(f"Capsules directory not found: {capsules_dir}")

    for capsule_file in sorted(capsules_path.glob("*.json")):
        with open(capsule_file) as f:
            capsule = json.load(f)

        # Filter by workset if provided
        if workset_paths is None or capsule.get("path") in workset_paths:
            # Filter out non-source files
            if is_source_file(capsule.get("path", "")):
                capsules.append(capsule)

    return capsules


def get_routes(db_path: str, workset_paths: set[str] | None = None) -> list[dict]:
    """Get routes from database, excluding test files."""
    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if workset_paths:
        placeholders = ",".join("?" * len(workset_paths))
        query = f"""
            SELECT method, pattern, file
            FROM api_endpoints
            WHERE file IN ({placeholders})
            ORDER BY file, pattern
        """
        cursor.execute(query, tuple(workset_paths))
    else:
        cursor.execute(
            """
            SELECT method, pattern, file
            FROM api_endpoints
            ORDER BY file, pattern
        """
        )

    routes = []
    for row in cursor.fetchall():
        # Filter out test files
        if is_source_file(row[2]):
            routes.append({"method": row[0], "pattern": row[1], "file": row[2]})

    conn.close()
    return routes


def get_sql_objects(db_path: str, workset_paths: set[str] | None = None) -> list[dict]:
    """Get SQL objects from database, excluding test files."""
    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if workset_paths:
        placeholders = ",".join("?" * len(workset_paths))
        query = f"""
            SELECT kind, name, file
            FROM sql_objects
            WHERE file IN ({placeholders})
            ORDER BY kind, name
        """
        cursor.execute(query, tuple(workset_paths))
    else:
        cursor.execute(
            """
            SELECT kind, name, file
            FROM sql_objects
            ORDER BY kind, name
        """
        )

    objects = []
    for row in cursor.fetchall():
        # Filter out test files
        if is_source_file(row[2]):
            objects.append({"kind": row[0], "name": row[1], "file": row[2]})

    conn.close()
    return objects


def group_files_by_folder(capsules: list[dict]) -> dict[str, list[dict]]:
    """Group files by their first directory segment."""
    groups = defaultdict(list)

    for capsule in capsules:
        path = capsule.get("path", "")
        if "/" in path:
            folder = path.split("/")[0]
        else:
            folder = "."
        groups[folder].append(capsule)

    # Sort by folder name
    return dict(sorted(groups.items()))


def generate_architecture_md(
    routes: list[dict],
    sql_objects: list[dict],
    capsules: list[dict],
    scope: str,
) -> str:
    """Generate ARCHITECTURE.md content."""
    now = datetime.now(UTC).isoformat()

    content = [
        "# Architecture",
        f"Generated at: {now}",
        "",
        "## Scope",
        f"Mode: {scope}",
        "",
    ]

    # Routes table
    if routes:
        content.extend(
            [
                "## Routes",
                "",
                "| Method | Pattern | File |",
                "|--------|---------|------|",
            ]
        )
        for route in routes:
            content.append(f"| {route['method']} | {route['pattern']} | {route['file']} |")
        content.append("")

    # SQL Objects table
    if sql_objects:
        content.extend(
            [
                "## SQL Objects",
                "",
                "| Kind | Name | File |",
                "|------|------|------|",
            ]
        )
        for obj in sql_objects:
            content.append(f"| {obj['kind']} | {obj['name']} | {obj['file']} |")
        content.append("")

    # Core Modules (group by actual functionality)
    groups = group_files_by_folder(capsules)
    if groups:
        content.extend(
            [
                "## Core Modules",
                "",
            ]
        )
        
        # Filter and organize by purpose
        module_categories = {
            "Core CLI": {},
            "Analysis & Detection": {},
            "Code Generation": {},
            "Reporting": {},
            "Utilities": {},
        }
        
        for folder, folder_capsules in groups.items():
            if folder == "theauditor":
                for capsule in folder_capsules:
                    path = Path(capsule.get("path", ""))
                    name = path.stem
                    
                    # Skip duplicates and internal modules
                    if name in ['__init__', 'parsers'] or name.endswith('.py.tpl'):
                        continue
                    
                    exports = capsule.get("interfaces", {}).get("exports", [])
                    functions = capsule.get("interfaces", {}).get("functions", [])
                    classes = capsule.get("interfaces", {}).get("classes", [])
                    
                    # Categorize based on filename
                    if name in ['cli', 'orchestrator', 'config', 'config_runtime']:
                        category = "Core CLI"
                    elif name in ['lint', 'ast_verify', 'universal_detector', 'pattern_loader', 'flow_analyzer', 'risk_scorer', 'pattern_rca', 'xgraph_analyzer']:
                        category = "Analysis & Detection"
                    elif name in ['scaffolder', 'test_generator', 'claude_setup', 'claude_autogen', 'venv_install']:
                        category = "Code Generation"
                    elif name in ['report', 'capsules', 'docgen', 'journal_view']:
                        category = "Reporting"
                    else:
                        # Skip certain utility files from main display
                        if name in ['utils', 'evidence', 'runner', 'contracts', 'tools']:
                            continue
                        category = "Utilities"
                    
                    # Build summary (only add if not already present)
                    if name not in module_categories[category]:
                        summary_parts = []
                        if classes:
                            summary_parts.append(f"Classes: {', '.join(classes[:3])}")
                        elif functions:
                            summary_parts.append(f"Functions: {', '.join(functions[:3])}")
                        elif exports:
                            summary_parts.append(f"Exports: {', '.join(exports[:3])}")
                        
                        summary = " | ".join(summary_parts) if summary_parts else "Utility module"
                        module_categories[category][name] = f"- **{name}**: {summary}"
        
        # Output categorized modules
        for category, modules_dict in module_categories.items():
            if modules_dict:
                content.append(f"### {category}")
                # Sort modules by name and get their descriptions
                for name in sorted(modules_dict.keys()):
                    content.append(modules_dict[name])
                content.append("")

    return "\n".join(content)


def generate_features_md(capsules: list[dict]) -> str:
    """Generate FEATURES.md content with meaningful feature descriptions."""
    content = [
        "# Features & Capabilities",
        "",
        "## Core Functionality",
        "",
    ]
    
    # Analyze capsules to extract features
    features = {
        "Code Analysis": [],
        "Test Generation": [],
        "Documentation": [],
        "CI/CD Integration": [],
        "ML Capabilities": [],
    }
    
    cli_commands = set()
    
    for capsule in capsules:
        path = Path(capsule.get("path", ""))
        if path.parent.name != "theauditor":
            continue
            
        name = path.stem
        exports = capsule.get("interfaces", {}).get("exports", [])
        functions = capsule.get("interfaces", {}).get("functions", [])
        
        # Extract features based on module
        if name == "cli":
            # Try to extract CLI commands from functions
            for func in functions:
                if func not in ['main', 'cli']:
                    cli_commands.add(func)
        elif name == "lint":
            features["Code Analysis"].append("- **Linting**: Custom security and quality rules")
        elif name == "ast_verify":
            features["Code Analysis"].append("- **AST Verification**: Contract-based code verification")
        elif name == "universal_detector":
            features["Code Analysis"].append("- **Pattern Detection**: Security and performance anti-patterns")
        elif name == "flow_analyzer":
            features["Code Analysis"].append("- **Flow Analysis**: Deadlock and race condition detection")
        elif name == "risk_scorer":
            features["Code Analysis"].append("- **Risk Scoring**: Automated risk assessment for files")
        elif name == "test_generator":
            features["Test Generation"].append("- **Test Scaffolding**: Generate test stubs from code")
        elif name == "scaffolder":
            features["Test Generation"].append("- **Contract Tests**: Generate DB/API contract tests")
        elif name == "docgen":
            features["Documentation"].append("- **Architecture Docs**: Auto-generate architecture documentation")
        elif name == "capsules":
            features["Documentation"].append("- **Code Capsules**: Compressed code summaries")
        elif name == "report":
            features["Documentation"].append("- **Audit Reports**: Comprehensive audit report generation")
        elif name == "claude_setup":
            features["CI/CD Integration"].append("- **Claude Code Integration**: Automated hooks for Claude AI")
        elif name == "orchestrator":
            features["CI/CD Integration"].append("- **Event-Driven Automation**: Git hooks and CI pipeline support")
        elif name == "ml":
            features["ML Capabilities"].append("- **ML-Based Suggestions**: Learn from codebase patterns")
            features["ML Capabilities"].append("- **Root Cause Prediction**: Predict likely failure points")
    
    # Output features by category
    for category, feature_list in features.items():
        if feature_list:
            content.append(f"### {category}")
            # Deduplicate
            seen = set()
            for feature in feature_list:
                if feature not in seen:
                    content.append(feature)
                    seen.add(feature)
            content.append("")
    
    # Add CLI commands summary
    if cli_commands:
        content.append("## Available Commands")
        content.append("")
        content.append("The following commands are available through the CLI:")
        content.append("")
        # Group commands by purpose
        cmd_groups = {
            "Analysis": ['lint', 'ast_verify', 'detect_patterns', 'flow_analyze', 'risk_score'],
            "Generation": ['gen_tests', 'scaffold', 'suggest_fixes'],
            "Reporting": ['report', 'journal', 'capsules'],
            "Setup": ['init', 'setup_claude', 'deps'],
        }
        
        for group, cmds in cmd_groups.items():
            group_cmds = [c for c in cli_commands if any(cmd in c for cmd in cmds)]
            if group_cmds:
                content.append(f"**{group}**: {', '.join(sorted(group_cmds)[:5])}")
        content.append("")
    
    # Add configuration info
    content.append("## Configuration")
    content.append("")
    content.append("- **Zero Dependencies**: Core functionality uses only Python stdlib")
    content.append("- **Offline Mode**: All operations work without network access")
    content.append("- **Per-Project**: No global state, everything is project-local")
    content.append("")
    
    return "\n".join(content)


def generate_trace_md(
    manifest_hash: str,
    manifest: list[dict],
    capsules: list[dict],
    db_path: str,
    workset_paths: set[str] | None,
) -> str:
    """Generate TRACE.md content with meaningful metrics."""
    # Count database entries
    routes_count = 0
    sql_objects_count = 0
    refs_count = 0
    imports_count = 0

    if Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM api_endpoints")
        routes_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sql_objects")
        sql_objects_count = cursor.fetchone()[0]

        # Count refs (files table)
        cursor.execute("SELECT COUNT(*) FROM files")
        refs_count = cursor.fetchone()[0]
        
        # Count imports
        try:
            cursor.execute("SELECT COUNT(*) FROM imports")
            imports_count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            imports_count = 0

        conn.close()
    
    # Separate source files from all files
    source_files = [f for f in manifest if is_source_file(f.get("path", ""))]
    test_files = [f for f in manifest if 'test' in f.get("path", "").lower()]
    doc_files = [f for f in manifest if f.get("path", "").endswith(('.md', '.rst', '.txt'))]

    # Calculate coverage
    if workset_paths:
        coverage = len(capsules) / len(workset_paths) * 100 if workset_paths else 0
    else:
        coverage = len(capsules) / len(source_files) * 100 if source_files else 0

    content = [
        "# Audit Trace",
        "",
        "## Repository Snapshot",
        f"**Manifest Hash**: `{manifest_hash}`",
        f"**Timestamp**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## File Statistics",
        f"- **Total Files**: {len(manifest)}",
        f"  - Source Files: {len(source_files)}",
        f"  - Test Files: {len(test_files)}",
        f"  - Documentation: {len(doc_files)}",
        f"  - Other: {len(manifest) - len(source_files) - len(test_files) - len(doc_files)}",
        "",
        "## Code Metrics",
        f"- **Cross-References**: {refs_count}",
        f"- **Import Statements**: {imports_count}",
        f"- **HTTP Routes**: {routes_count}",
        f"- **SQL Objects**: {sql_objects_count}",
        "",
        "## Analysis Coverage",
        f"- **Coverage**: {coverage:.1f}% of source files",
        f"- **Capsules Generated**: {len(capsules)}",
        f"- **Scope**: {'Workset' if workset_paths else 'Full repository'}",
        "",
        "## Language Distribution",
    ]
    
    # Count languages
    lang_counts = defaultdict(int)
    for capsule in capsules:
        lang = capsule.get("language", "")  # Empty not unknown
        lang_counts[lang] += 1
    
    for lang, count in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True):
        content.append(f"- {lang}: {count} files")
    
    content.extend([
        "",
        "## Environment",
        f"- **TheAuditor Version**: {__version__}",
        f"- **Python**: {sys.version.split()[0]}",
        f"- **Platform**: {platform.platform()}",
        f"- **Processor**: {platform.processor() or 'Unknown'}",
        "",
        "## Audit Trail",
        "This document provides cryptographic proof of the codebase state at audit time.",
        "The manifest hash can be used to verify no files have been modified since analysis.",
        "",
    ])

    return "\n".join(content)


# This function was moved above generate_trace_md


def generate_docs(
    manifest_path: str = "manifest.json",
    db_path: str = "repo_index.db",
    capsules_dir: str = "./.pf/capsules",
    workset_path: str = "./.pf/workset.json",
    out_dir: str = "./.pf/docs",
    full: bool = False,
    print_stats: bool = False,
) -> dict[str, Any]:
    """Generate documentation from index and capsules."""

    # Load data
    manifest, manifest_hash = load_manifest(manifest_path)
    workset_paths = None if full else load_workset(workset_path)

    try:
        capsules = load_capsules(capsules_dir, workset_paths)
    except RuntimeError as e:
        raise RuntimeError(f"Cannot generate docs: {e}. Run 'aud capsules' first.") from e

    # Get database data
    routes = get_routes(db_path, workset_paths)
    sql_objects = get_sql_objects(db_path, workset_paths)

    # Generate content
    scope = "full" if full else "workset"
    architecture_content = generate_architecture_md(routes, sql_objects, capsules, scope)
    trace_content = generate_trace_md(manifest_hash, manifest, capsules, db_path, workset_paths)
    features_content = generate_features_md(capsules)

    # Write files
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    (out_path / "ARCHITECTURE.md").write_text(architecture_content)
    (out_path / "TRACE.md").write_text(trace_content)
    (out_path / "FEATURES.md").write_text(features_content)

    result = {
        "files_written": 3,
        "scope": scope,
        "capsules_used": len(capsules),
        "routes": len(routes),
        "sql_objects": len(sql_objects),
    }

    if print_stats:
        print(f"Generated {result['files_written']} docs in {out_dir}")
        print(f"  Scope: {result['scope']}")
        print(f"  Capsules: {result['capsules_used']}")
        print(f"  Routes: {result['routes']}")
        print(f"  SQL Objects: {result['sql_objects']}")

    return result
