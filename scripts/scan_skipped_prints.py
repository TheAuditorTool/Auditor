"""Pre-flight scanner for loguru_migration.py.

Scans the codebase for print() statements that the migration script will IGNORE.
This gives you a concrete list of what needs manual handling.

Usage:
    python scripts/scan_skipped_prints.py theauditor/

Categories detected:
    - Legacy % formatting: print("[TAG] %s" % var)
    - .format() method: print("[TAG] {}".format(var))
    - Variable argument: print(msg) - can't detect tags in variables
    - Unknown Tag: [SOME_TAG] not in known mapping

Author: TheAuditor Team
Date: 2025-12-01
"""
from __future__ import annotations

import os
import re
import sys

import libcst as cst
from libcst import matchers as m


# Same tags as loguru_migration.py - keep in sync!
KNOWN_TAGS = [
    # Debug-level
    "[RESOLVER_DEBUG]",
    "[INDEXER_DEBUG]",
    "[AST_DEBUG]",
    "[DEBUG]",
    "[TRACE]",
    "[DEDUP]",
    "[SCHEMA]",
    "[NORMALIZE]",
    "[IFDS]",
    "[CORE]",
    # Info-level
    "[ORCHESTRATOR]",
    "[METADATA]",
    "[Indexer]",
    "[TAINT]",
    "[INFO]",
    "[FCE]",
    "[GRAPH]",
    "[RULES]",
    "[STATUS]",
    "[ARCHIVE]",
    "[OK]",
    "[TIP]",
    "[DB]",
    "[ML]",
    # Warning-level
    "[WARNING]",
    "[WARN]",
    # Error-level
    "[ERROR]",
    # Critical-level
    "[CRITICAL]",
    "[FATAL]",
]


class SkippedPrintScanner(cst.CSTVisitor):
    """Visitor that finds print() statements the migration will skip."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.found_issues: list[tuple[str, cst.Call, int]] = []
        self._current_line = 0

    def visit_Call(self, node: cst.Call) -> None:
        # Only look at print() calls
        if not m.matches(node.func, m.Name("print")):
            return

        # Empty print
        if not node.args:
            self.found_issues.append(("Empty print()", node, 0))
            return

        first_arg = node.args[0].value

        # Case A: Percent Formatting: print("[TAG] %s" % var)
        if m.matches(first_arg, m.BinaryOperation(operator=m.Modulo())):
            self.found_issues.append(("Legacy % formatting", node, 0))
            return

        # Case B: .format() calls: print("[TAG] {}".format(var))
        if m.matches(first_arg, m.Call(func=m.Attribute(attr=m.Name("format")))):
            self.found_issues.append((".format() method", node, 0))
            return

        # Case C: Variables: print(my_message) - Can't see a tag in variable
        if isinstance(first_arg, cst.Name):
            self.found_issues.append(("Variable argument", node, 0))
            return

        # Case D: Check for unknown tags in string literals
        if isinstance(first_arg, (cst.SimpleString, cst.FormattedString)):
            text = self._extract_text(first_arg)

            # If it looks like a tag "[...]" but isn't in our KNOWN list
            if "[" in text and "]" in text:
                has_known = any(tag in text for tag in KNOWN_TAGS)
                if not has_known:
                    # Find things that look like tags
                    potential_tags = re.findall(r"\[[A-Z_]+\]", text)
                    if potential_tags:
                        self.found_issues.append(
                            (f"Unknown Tag {potential_tags}", node, 0)
                        )

    def _extract_text(self, node: cst.BaseExpression) -> str:
        """Extract text content from string nodes."""
        if isinstance(node, cst.SimpleString):
            return node.value
        elif isinstance(node, cst.FormattedString):
            parts = []
            for part in node.parts:
                if isinstance(part, cst.FormattedStringText):
                    parts.append(part.value)
            return "".join(parts)
        return ""


def scan_file(filepath: str) -> list[tuple[str, cst.Call, int]]:
    """Scan a single file for skipped print patterns."""
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()

        module = cst.parse_module(source)
        scanner = SkippedPrintScanner(filepath)
        # LibCST uses visit() for both visitors and transformers
        module.visit(scanner)

        return scanner.found_issues
    except cst.ParserSyntaxError as e:
        print(f"[WARN] Syntax error in {filepath}: {e}")
        return []
    except UnicodeDecodeError as e:
        print(f"[WARN] Encoding error in {filepath}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to parse {filepath}: {e}")
        return []


def safe_print(text: str) -> None:
    """Print text safely for Windows CP1252."""
    try:
        print(text)
    except UnicodeEncodeError:
        safe_text = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_text)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/scan_skipped_prints.py <directory>")
        print("")
        print("Scans for print() statements that loguru_migration.py will skip.")
        print("")
        print("Categories:")
        print("  - Legacy % formatting: print('[TAG] %s' % var)")
        print("  - .format() method: print('[TAG] {}'.format(var))")
        print("  - Variable argument: print(msg)")
        print("  - Unknown Tag: [SOME_TAG] not in known mapping")
        sys.exit(1)

    target_dir = sys.argv[1]
    all_issues: list[tuple[str, str, str]] = []

    # Skip directories
    skip_dirs = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "node_modules",
        ".pf",
        ".auditor_venv",
        "dist",
        "build",
    }

    print(f"Scanning {target_dir} for complex print statements...")
    print("=" * 60)
    print("")

    for root, dirs, files in os.walk(target_dir):
        # Filter out skip directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file).replace("\\", "/")
                issues = scan_file(path)

                if issues:
                    safe_print(f"FILE: {path}")
                    for reason, node, _line in issues:
                        # Extract code snippet
                        try:
                            code_snippet = cst.Module([]).code_for_node(node).strip()
                            # Truncate if too long
                            if len(code_snippet) > 70:
                                code_snippet = code_snippet[:67] + "..."
                        except Exception:
                            code_snippet = "<unable to render>"

                        safe_print(f"  [!] {reason:<22} | {code_snippet}")
                        all_issues.append((path, reason, code_snippet))
                    print("")

    print("=" * 60)
    print(f"Scan Complete.")
    print(f"Found {len(all_issues)} print statements that require manual review.")
    print("")

    if all_issues:
        # Summary by category
        categories: dict[str, int] = {}
        for _path, reason, _code in all_issues:
            # Normalize unknown tag reasons
            if reason.startswith("Unknown Tag"):
                key = "Unknown Tag"
            else:
                key = reason
            categories[key] = categories.get(key, 0) + 1

        print("Summary by category:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
