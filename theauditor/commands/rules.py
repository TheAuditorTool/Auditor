"""Rules command - inspect and summarize detection capabilities."""

import importlib
import inspect
import os
from pathlib import Path

import click
import yaml

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console
from theauditor.utils import handle_exceptions
from theauditor.utils.constants import ExitCodes


@click.command(name="rules", cls=RichCommand)
@click.option(
    "--summary",
    is_flag=True,
    default=False,
    help="Generate a summary of all detection capabilities",
)
@handle_exceptions
def rules_command(summary: bool) -> None:
    """Inspect and summarize TheAuditor's detection rules and patterns.

    Generates a comprehensive inventory of all security rules, vulnerability
    patterns, and code quality checks built into TheAuditor. Scans YAML pattern
    files and Python AST rules to create a complete capability report for
    documentation, compliance, and customization planning.

    AI ASSISTANT CONTEXT:
      Purpose: Document TheAuditor's detection capabilities
      Input: theauditor/patterns/*.yml, theauditor/rules/*.py (pattern definitions)
      Output: .pf/auditor_capabilities.md (comprehensive report)
      Prerequisites: None (reads pattern files, no indexing required)
      Integration: Security documentation, compliance reporting, custom pattern development
      Performance: ~1-2 seconds (file scanning only)

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

    SEE ALSO:
      aud manual rules     # Deep dive into rule system concepts
      aud manual patterns  # Pattern matching fundamentals

    TROUBLESHOOTING:
      No patterns found:
        -> Check theauditor/patterns/ directory exists
        -> YAML files must have .yml or .yaml extension
        -> Pattern format: list of dicts with 'name' key

      Python rules not appearing:
        -> Functions must start with 'find_' prefix
        -> Check theauditor/rules/*.py files exist
        -> Syntax errors prevent rule scanning

    NOTE: This command does not modify any files or perform analysis.
    It only generates a capability inventory from pattern definitions.
    """
    if not summary:
        err_console.print(
            "[error]Please specify --summary to generate a capability report[/error]",
        )
        raise SystemExit(ExitCodes.TASK_INCOMPLETE)

    base_path = Path(__file__).parent.parent
    patterns_path = base_path / "patterns"
    rules_path = base_path / "rules"

    output_dir = Path(".pf")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "auditor_capabilities.md"

    output_lines = []
    output_lines.append("# TheAuditor Detection Capabilities\n")

    console.print("# TheAuditor Detection Capabilities\n")

    console.print("## YAML Patterns\n")
    output_lines.append("## YAML Patterns\n")
    yaml_patterns = scan_yaml_patterns(patterns_path)
    total_patterns = 0

    for category, files in yaml_patterns.items():
        if files:
            category_display = "patterns/" if category == "." else f"patterns/{category}/"
            console.print(f"### {category_display}\n", highlight=False)
            output_lines.append(f"### {category_display}\n")
            for file_name, patterns in files.items():
                if patterns:
                    console.print(f"**{file_name}** ({len(patterns)} patterns)", highlight=False)
                    output_lines.append(f"**{file_name}** ({len(patterns)} patterns)")
                    for pattern in patterns:
                        console.print(f"- `{pattern}`", highlight=False)
                        output_lines.append(f"- `{pattern}`")
                    console.print()
                    output_lines.append("")
                    total_patterns += len(patterns)

    console.print("## Python AST Rules\n")
    output_lines.append("## Python AST Rules\n")
    python_rules = scan_python_rules(rules_path)
    total_rules = 0

    for module_path, functions in python_rules.items():
        if functions:
            display_path = module_path.replace(str(rules_path) + os.sep, "")
            console.print(f"### {display_path}", highlight=False)
            output_lines.append(f"### {display_path}")
            for func in functions:
                console.print(f"- `{func}()`", highlight=False)
                output_lines.append(f"- `{func}()`")
            console.print()
            output_lines.append("")
            total_rules += len(functions)

    console.print("## Summary Statistics\n")
    output_lines.append("## Summary Statistics\n")
    console.print(f"- **Total YAML Patterns**: {total_patterns}", highlight=False)
    output_lines.append(f"- **Total YAML Patterns**: {total_patterns}")
    console.print(f"- **Total Python Rules**: {total_rules}", highlight=False)
    output_lines.append(f"- **Total Python Rules**: {total_rules}")
    console.print(
        f"- **Combined Detection Capabilities**: {total_patterns + total_rules}", highlight=False
    )
    output_lines.append(f"- **Combined Detection Capabilities**: {total_patterns + total_rules}")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    console.print("\n[success]Capability report generated successfully[/success]")
    console.print(f"[info]Report saved to: {output_file}[/info]")
    raise SystemExit(ExitCodes.SUCCESS)


def scan_yaml_patterns(patterns_path: Path) -> dict[str, dict[str, list[str]]]:
    """Scan YAML pattern files and extract pattern names.

    Args:
        patterns_path: Path to the patterns directory

    Returns:
        Dictionary mapping category -> file -> list of pattern names
    """
    results = {}

    if not patterns_path.exists():
        return results

    for root, dirs, files in os.walk(patterns_path):
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".yml") or file.endswith(".yaml"):
                file_path = Path(root) / file

                rel_path = file_path.relative_to(patterns_path)

                category = "." if rel_path.parent == Path(".") else str(rel_path.parent)

                if category not in results:
                    results[category] = {}

                try:
                    with open(file_path, encoding="utf-8") as f:
                        data = yaml.safe_load(f)

                    if data and isinstance(data, list):
                        pattern_names = []
                        for pattern in data:
                            if isinstance(pattern, dict) and "name" in pattern:
                                pattern_names.append(pattern["name"])

                        if pattern_names:
                            results[category][file] = pattern_names

                except (yaml.YAMLError, OSError):
                    continue

    return results


def scan_python_rules(rules_path: Path) -> dict[str, list[str]]:
    """Scan Python rule files and find all find_* functions.

    Args:
        rules_path: Path to the rules directory

    Returns:
        Dictionary mapping module path -> list of find_* function names
    """
    results = {}

    if not rules_path.exists():
        return results

    init_file = rules_path / "__init__.py"
    if init_file.exists():
        try:
            module = importlib.import_module("theauditor.rules")
            exposed_functions = []
            for name, _obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("find_"):
                    exposed_functions.append(name)
            if exposed_functions:
                results["rules/__init__.py (exposed)"] = exposed_functions
        except ImportError:
            pass

    for root, dirs, files in os.walk(rules_path):
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file

                if file == "__init__.py":
                    continue

                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    import re

                    pattern = r"^def\s+(find_\w+)\s*\("
                    matches = re.findall(pattern, content, re.MULTILINE)

                    if matches:
                        display_path = str(file_path.relative_to(rules_path.parent))
                        results[display_path] = matches

                except OSError:
                    continue

    return results
