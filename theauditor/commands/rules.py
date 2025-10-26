"""Rules command - inspect and summarize detection capabilities."""

import os
import yaml
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Any

import click

from theauditor.utils import handle_exceptions
from theauditor.utils.exit_codes import ExitCodes


@click.command(name="rules")
@click.option(
    "--summary",
    is_flag=True,
    default=False,
    help="Generate a summary of all detection capabilities",
)
@handle_exceptions
def rules_command(summary: bool) -> None:
    """Inspect and summarize TheAuditor's detection rules and patterns.

    This command generates a comprehensive inventory of all security rules,
    vulnerability patterns, and code quality checks that TheAuditor can detect.
    It scans both YAML pattern files and Python AST rules to create a complete
    capability report.

    WHY USE THIS:
    - Understand what vulnerabilities TheAuditor can detect
    - Document your security audit capabilities for compliance
    - Verify which patterns are active in your analysis
    - Customize detection by understanding available rules
    - Share detection capabilities with security teams

    WHAT IT ANALYZES:
    - YAML Pattern Files: Regex-based security patterns (XSS, SQL injection, etc.)
    - Python AST Rules: Semantic code analysis rules (find_* functions)
    - Framework-Specific Patterns: Django, Flask, React patterns
    - Custom Patterns: User-defined rules in patterns/ directory

    HOW IT WORKS:
    1. Scans theauditor/patterns/ for all YAML files
    2. Extracts pattern names and categories from YAML
    3. Scans theauditor/rules/ for all find_* functions
    4. Groups rules by category and file
    5. Generates summary statistics
    6. Outputs markdown report to .pf/auditor_capabilities.md

    EXAMPLES:
      # Generate capability report
      aud rules --summary

      # Use in documentation workflow
      aud rules --summary && cat .pf/auditor_capabilities.md

      # Verify patterns after adding custom rules
      aud rules --summary | grep -i "sql"

    OUTPUT:
      .pf/auditor_capabilities.md     # Comprehensive capability report

    DETECTED CATEGORIES:
    TheAuditor can detect vulnerabilities in these categories:
    - Authentication & Authorization (OAuth, JWT, session management)
    - Injection Attacks (SQL, command, LDAP, NoSQL injection)
    - Data Security (hardcoded secrets, weak crypto, data exposure)
    - XSS & Template Injection (client-side, server-side)
    - Infrastructure Security (Docker, cloud misconfigurations)
    - Framework-Specific (Django, Flask, React, Vue patterns)
    - Code Quality (complexity, dead code, race conditions)

    PATTERN FILE LOCATIONS:
      theauditor/patterns/               # Core patterns
      theauditor/patterns/frameworks/    # Framework-specific patterns
      theauditor/rules/                  # Python AST rules

    COMMON WORKFLOWS:
      Security Audit Documentation:
        aud rules --summary                        # Generate capability report
        # Include .pf/auditor_capabilities.md in security assessment

      Custom Pattern Development:
        # Add custom pattern to patterns/custom.yml
        aud rules --summary                        # Verify pattern registered
        aud detect-patterns                        # Test custom pattern

      Compliance Reporting:
        aud rules --summary                        # Document detection capabilities
        # Show what security checks are performed

    PREREQUISITES:
      None - this command only reads pattern files, no indexing required

    RELATED COMMANDS:
      aud detect-patterns              # Run pattern detection on codebase
      aud explain patterns             # Learn about pattern detection system

    EXIT CODES:
      0 = Success, report generated
      3 = Task incomplete (must use --summary flag)

    NOTE: This command does not modify any files or perform analysis.
    It only generates a capability inventory from pattern definitions.
    """
    if not summary:
        click.echo(click.style("[ERROR] Please specify --summary to generate a capability report", fg="red"), err=True)
        raise SystemExit(ExitCodes.TASK_INCOMPLETE)

    # Get the base path for patterns and rules
    base_path = Path(__file__).parent.parent
    patterns_path = base_path / "patterns"
    rules_path = base_path / "rules"

    # Create output directory
    output_dir = Path(".pf")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "auditor_capabilities.md"

    # Collect output in a list
    output_lines = []
    output_lines.append("# TheAuditor Detection Capabilities\n")

    # Also print to console
    print("# TheAuditor Detection Capabilities\n")

    # Scan YAML patterns
    print("## YAML Patterns\n")
    output_lines.append("## YAML Patterns\n")
    yaml_patterns = scan_yaml_patterns(patterns_path)
    total_patterns = 0

    for category, files in yaml_patterns.items():
        if files:
            category_display = "patterns/" if category == "." else f"patterns/{category}/"
            print(f"### {category_display}\n")
            output_lines.append(f"### {category_display}\n")
            for file_name, patterns in files.items():
                if patterns:
                    print(f"**{file_name}** ({len(patterns)} patterns)")
                    output_lines.append(f"**{file_name}** ({len(patterns)} patterns)")
                    for pattern in patterns:
                        print(f"- `{pattern}`")
                        output_lines.append(f"- `{pattern}`")
                    print()
                    output_lines.append("")
                    total_patterns += len(patterns)

    # Scan Python rules
    print("## Python AST Rules\n")
    output_lines.append("## Python AST Rules\n")
    python_rules = scan_python_rules(rules_path)
    total_rules = 0

    for module_path, functions in python_rules.items():
        if functions:
            # Make path relative to rules/ for readability
            display_path = module_path.replace(str(rules_path) + os.sep, "")
            print(f"### {display_path}")
            output_lines.append(f"### {display_path}")
            for func in functions:
                print(f"- `{func}()`")
                output_lines.append(f"- `{func}()`")
            print()
            output_lines.append("")
            total_rules += len(functions)

    # Print summary statistics
    print("## Summary Statistics\n")
    output_lines.append("## Summary Statistics\n")
    print(f"- **Total YAML Patterns**: {total_patterns}")
    output_lines.append(f"- **Total YAML Patterns**: {total_patterns}")
    print(f"- **Total Python Rules**: {total_rules}")
    output_lines.append(f"- **Total Python Rules**: {total_rules}")
    print(f"- **Combined Detection Capabilities**: {total_patterns + total_rules}")
    output_lines.append(f"- **Combined Detection Capabilities**: {total_patterns + total_rules}")

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    click.echo(click.style(f"\n[SUCCESS] Capability report generated successfully", fg="green"))
    click.echo(f"[INFO] Report saved to: {output_file}")
    raise SystemExit(ExitCodes.SUCCESS)


def scan_yaml_patterns(patterns_path: Path) -> Dict[str, Dict[str, List[str]]]:
    """Scan YAML pattern files and extract pattern names.

    Args:
        patterns_path: Path to the patterns directory

    Returns:
        Dictionary mapping category -> file -> list of pattern names
    """
    results = {}

    if not patterns_path.exists():
        return results

    # Walk through all subdirectories
    for root, dirs, files in os.walk(patterns_path):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".yml") or file.endswith(".yaml"):
                file_path = Path(root) / file

                # Determine category from directory structure
                rel_path = file_path.relative_to(patterns_path)
                # If file is in root of patterns/, use "." as category
                # If in subdirectory like frameworks/, use that as category
                if rel_path.parent == Path("."):
                    category = "."
                else:
                    category = str(rel_path.parent)

                if category not in results:
                    results[category] = {}

                # Parse YAML and extract pattern names
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)

                    if data and isinstance(data, list):
                        pattern_names = []
                        for pattern in data:
                            if isinstance(pattern, dict) and 'name' in pattern:
                                pattern_names.append(pattern['name'])

                        if pattern_names:
                            results[category][file] = pattern_names

                except (yaml.YAMLError, OSError) as e:
                    # Skip files that can't be parsed
                    continue

    return results


def scan_python_rules(rules_path: Path) -> Dict[str, List[str]]:
    """Scan Python rule files and find all find_* functions.

    Args:
        rules_path: Path to the rules directory

    Returns:
        Dictionary mapping module path -> list of find_* function names
    """
    results = {}

    if not rules_path.exists():
        return results

    # First, check what's exposed in the main __init__.py
    init_file = rules_path / "__init__.py"
    if init_file.exists():
        try:
            module = importlib.import_module("theauditor.rules")
            exposed_functions = []
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("find_"):
                    exposed_functions.append(name)
            if exposed_functions:
                results["rules/__init__.py (exposed)"] = exposed_functions
        except ImportError:
            pass

    # Walk through all Python files
    for root, dirs, files in os.walk(rules_path):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file

                # Skip __init__.py files for now (we handle them separately)
                if file == "__init__.py":
                    continue

                # Try basic text scanning (more reliable than import)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Simple regex to find function definitions
                    import re
                    pattern = r'^def\s+(find_\w+)\s*\('
                    matches = re.findall(pattern, content, re.MULTILINE)

                    if matches:
                        # Make path relative for display
                        display_path = str(file_path.relative_to(rules_path.parent))
                        results[display_path] = matches

                except OSError:
                    continue

    return results
