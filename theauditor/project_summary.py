"""Generate project structure and intelligence reports for AI consumption."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from .indexer.config import SKIP_DIRS


def generate_directory_tree(root_path: str = ".", max_depth: int = 4) -> str:
    """
    Generate a text-based directory tree representation.

    Args:
        root_path: Root directory to analyze
        max_depth: Maximum depth to traverse

    Returns:
        String representation of directory tree
    """
    root = Path(root_path).resolve()
    tree_lines = []

    critical_files = {
        "main.py",
        "app.py",
        "__main__.py",
        "config.py",
        "settings.py",
        "models.py",
        "schemas.py",
        "auth.py",
        "authentication.py",
        "middleware.py",
        "routes.py",
        "urls.py",
        "api.py",
        "index.js",
        "index.ts",
        "app.js",
        "app.ts",
        "server.js",
        "server.ts",
        "package.json",
        "tsconfig.json",
        "types.ts",
        "requirements.txt",
        "setup.py",
        "pyproject.toml",
        "Dockerfile",
        "docker-compose.yml",
        "Makefile",
        ".env.example",
    }

    def should_skip(path: Path) -> bool:
        """Check if directory should be skipped."""
        return path.name in SKIP_DIRS or path.name.startswith(".")

    def add_directory(dir_path: Path, prefix: str = "", depth: int = 0):
        """Recursively add directory contents to tree."""
        if depth > max_depth:
            return

        try:
            items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return

        dirs = [item for item in items if item.is_dir() and not should_skip(item)]
        files = [item for item in items if item.is_file()]

        file_groups = {}
        critical_in_dir = []

        for file in files:
            if file.name in critical_files:
                critical_in_dir.append(file)
            else:
                ext = file.suffix or "no-ext"
                if ext not in file_groups:
                    file_groups[ext] = 0
                file_groups[ext] += 1

        for file in critical_in_dir:
            is_last = (file == critical_in_dir[-1]) and not dirs and not file_groups
            tree_lines.append(f"{prefix}{'└── ' if is_last else '├── '}{file.name}")

        if file_groups:
            summary_parts = []
            for ext, count in sorted(file_groups.items()):
                if count > 1:
                    summary_parts.append(f"{count} {ext} files")
                elif count == 1:
                    summary_parts.append(f"1 {ext} file")

            if summary_parts:
                is_last = not dirs
                summary = f"[{', '.join(summary_parts)}]"
                tree_lines.append(f"{prefix}{'└── ' if is_last else '├── '}{summary}")

        for i, subdir in enumerate(dirs):
            is_last_dir = i == len(dirs) - 1
            tree_lines.append(f"{prefix}{'└── ' if is_last_dir else '├── '}{subdir.name}/")

            extension = "    " if is_last_dir else "│   "
            add_directory(subdir, prefix + extension, depth + 1)

    tree_lines.append(f"{root.name}/")
    add_directory(root, "", 0)

    return "\n".join(tree_lines)


def aggregate_statistics(manifest_path: str, db_path: str) -> dict[str, Any]:
    """
    Aggregate project-wide statistics from manifest and database.

    Args:
        manifest_path: Path to manifest.json
        db_path: Path to repo_index.db

    Returns:
        Dictionary containing project statistics
    """
    stats = {
        "total_files": 0,
        "total_loc": 0,
        "total_bytes": 0,
        "total_tokens": 0,
        "languages": {},
        "total_functions": 0,
        "total_classes": 0,
        "total_imports": 0,
        "total_calls": 0,
        "top_10_largest": [],
        "top_15_critical": [],
    }

    if Path(manifest_path).exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

        stats["total_files"] = len(manifest)

        for file_info in manifest:
            stats["total_loc"] += file_info.get("loc", 0)
            stats["total_bytes"] += file_info.get("bytes", 0)

            ext = file_info.get("ext", "").lower()
            if ext:
                lang_map = {
                    ".py": "Python",
                    ".js": "JavaScript",
                    ".ts": "TypeScript",
                    ".jsx": "JSX",
                    ".tsx": "TSX",
                    ".java": "Java",
                    ".go": "Go",
                    ".rs": "Rust",
                    ".cpp": "C++",
                    ".cc": "C++",
                    ".c": "C",
                    ".rb": "Ruby",
                    ".php": "PHP",
                    ".cs": "C#",
                    ".swift": "Swift",
                    ".kt": "Kotlin",
                    ".r": "R",
                    ".m": "MATLAB",
                    ".jl": "Julia",
                    ".sh": "Shell",
                    ".yml": "YAML",
                    ".yaml": "YAML",
                    ".json": "JSON",
                    ".xml": "XML",
                    ".html": "HTML",
                    ".css": "CSS",
                    ".scss": "SCSS",
                    ".sql": "SQL",
                    ".md": "Markdown",
                }

                lang = lang_map.get(ext, "Other")
                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1

        stats["total_tokens"] = stats["total_bytes"] // 4

        sorted_by_size = sorted(manifest, key=lambda x: x.get("loc", 0), reverse=True)
        for file_info in sorted_by_size[:10]:
            stats["top_10_largest"].append(
                {
                    "path": file_info["path"],
                    "loc": file_info["loc"],
                    "bytes": file_info["bytes"],
                    "tokens": file_info["bytes"] // 4,
                    "percent": round((file_info["bytes"] / stats["total_bytes"]) * 100, 2)
                    if stats["total_bytes"] > 0
                    else 0,
                }
            )

        critical_patterns = {
            "main.py": "Entry point",
            "app.py": "Application entry",
            "__main__.py": "Module entry",
            "config.py": "Configuration",
            "settings.py": "Settings",
            "models.py": "Data models",
            "schemas.py": "Data schemas",
            "auth.py": "Authentication",
            "authentication.py": "Authentication",
            "middleware.py": "Middleware",
            "routes.py": "Routes",
            "urls.py": "URL patterns",
            "api.py": "API endpoints",
            "views.py": "Views",
            "database.py": "Database",
            "db.py": "Database",
            "index.js": "Entry point",
            "index.ts": "Entry point",
            "app.js": "Application",
            "app.ts": "Application",
            "server.js": "Server",
            "server.ts": "Server",
            "package.json": "Dependencies",
            "tsconfig.json": "TypeScript config",
            "types.ts": "Type definitions",
            "types.d.ts": "Type definitions",
            "middleware.js": "Middleware",
            "middleware.ts": "Middleware",
            "routes.js": "Routes",
            "routes.ts": "Routes",
            "config.js": "Configuration",
            "config.ts": "Configuration",
            "Dockerfile": "Container definition",
            "docker-compose.yml": "Container orchestration",
            "requirements.txt": "Python dependencies",
            "setup.py": "Python package",
            "pyproject.toml": "Python project",
            "Makefile": "Build automation",
        }

        for file_info in manifest:
            filename = Path(file_info["path"]).name
            if filename in critical_patterns:
                stats["top_15_critical"].append(
                    {
                        "path": file_info["path"],
                        "filename": filename,
                        "purpose": critical_patterns[filename],
                        "loc": file_info["loc"],
                        "bytes": file_info["bytes"],
                    }
                )

        stats["top_15_critical"] = stats["top_15_critical"][:15]

    if Path(db_path).exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM symbols WHERE type = 'function'")
            stats["total_functions"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM symbols WHERE type = 'class'")
            stats["total_classes"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM symbols WHERE type = 'call'")
            stats["total_calls"] = cursor.fetchone()[0]

            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM refs WHERE kind IN ('import', 'from', 'require')"
                )
                stats["total_imports"] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                pass

            conn.close()
        except Exception:
            pass

    return stats


def generate_project_summary(
    root_path: str = ".",
    manifest_path: str = "./.pf/manifest.json",
    db_path: str = "./.pf/repo_index.db",
    max_depth: int = 4,
) -> str:
    """
    Generate comprehensive project summary markdown report.

    Args:
        root_path: Root directory of project
        manifest_path: Path to manifest.json
        db_path: Path to repo_index.db

    Returns:
        Markdown formatted project summary report
    """
    lines = []

    lines.append("# Project Structure & Intelligence Report")
    lines.append("")
    lines.append("*This AI-optimized report provides immediate project comprehension.*")
    lines.append("")

    stats = aggregate_statistics(manifest_path, db_path)

    lines.append("## Project Summary")
    lines.append("")
    lines.append(f"- **Total Files**: {stats['total_files']:,} (analyzable)")

    claude_context = 400000
    token_percent = (
        (stats["total_tokens"] / claude_context * 100) if stats["total_tokens"] > 0 else 0
    )
    lines.append(
        f"- **Total Tokens**: ~{stats['total_tokens']:,} ({token_percent:.1f}% of Claude's context)"
    )
    lines.append(f"- **Total LOC**: {stats['total_loc']:,}")

    if stats["languages"]:
        sorted_langs = sorted(stats["languages"].items(), key=lambda x: x[1], reverse=True)
        total_files = sum(stats["languages"].values())

        lang_parts = []
        for lang, count in sorted_langs[:5]:
            percent = (count / total_files * 100) if total_files > 0 else 0
            lang_parts.append(f"{lang} ({percent:.0f}%)")

        lines.append(f"- **Languages**: {', '.join(lang_parts)}")

    lines.append("")
    lines.append("### Key Metrics")
    lines.append("")
    if stats["total_classes"] > 0:
        lines.append(f"- **Classes**: {stats['total_classes']:,}")
    if stats["total_functions"] > 0:
        lines.append(f"- **Functions**: {stats['total_functions']:,}")
    if stats["total_imports"] > 0:
        lines.append(f"- **Imports**: {stats['total_imports']:,}")
    if stats["total_calls"] > 0:
        lines.append(f"- **Function Calls**: {stats['total_calls']:,}")

    lines.append("")

    if stats["top_10_largest"]:
        lines.append("## Largest Files (by tokens)")
        lines.append("")
        lines.append("| # | File | LOC | Tokens | % of Codebase |")
        lines.append("|---|------|-----|--------|---------------|")

        for i, file_info in enumerate(stats["top_10_largest"], 1):
            path = file_info["path"]
            if len(path) > 50:
                path = "..." + path[-47:]
            lines.append(
                f"| {i} | `{path}` | {file_info['loc']:,} | {file_info['tokens']:,} | {file_info['percent']:.1f}% |"
            )

        lines.append("")

    if stats["top_15_critical"]:
        lines.append("## Critical Files (by convention)")
        lines.append("")
        lines.append("*Files identified as architecturally significant based on naming patterns:*")
        lines.append("")
        lines.append("| File | Purpose | LOC |")
        lines.append("|------|---------|-----|")

        for file_info in stats["top_15_critical"]:
            path = file_info["path"]
            if len(path) > 40:
                parts = Path(path).parts
                path = f".../{parts[-2]}/{parts[-1]}" if len(parts) > 2 else "/".join(parts)
            lines.append(f"| `{path}` | {file_info['purpose']} | {file_info['loc']:,} |")

        lines.append("")

    lines.append("## Directory Structure")
    lines.append("")
    lines.append("```")
    tree = generate_directory_tree(root_path, max_depth)
    lines.append(tree)
    lines.append("```")
    lines.append("")

    lines.append("## AI Context Optimization")
    lines.append("")
    lines.append("### Reading Order for Maximum Comprehension")
    lines.append("")
    lines.append("1. **Start here**: This file (STRUCTURE.md) - ~2,000 tokens")
    lines.append("2. **Core understanding**: Critical files listed above - ~10,000 tokens")
    lines.append("3. **Issues & findings**: AUDIT.md - ~15,000 tokens")
    lines.append("4. **Detailed analysis**: Other reports as needed")
    lines.append("")

    lines.append("### Token Budget Recommendations")
    lines.append("")
    if stats["total_tokens"] < 50000:
        lines.append("- **Small project**: Can load entire codebase if needed")
    elif stats["total_tokens"] < 150000:
        lines.append("- **Medium project**: Focus on critical files and problem areas")
    else:
        lines.append("- **Large project**: Use worksets and targeted analysis")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by TheAuditor - Truth through systematic observation*")

    return "\n".join(lines)
