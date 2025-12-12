"""Usage snippet extractor for cached package documentation.

Parses markdown files from the docs cache and extracts code snippets,
ranking them by quality heuristics to surface usage examples over
installation commands.

Usage:
    extractor = UsageExtractor()
    snippets = extractor.extract_usage("npm", "axios")
    for s in snippets[:5]:
        print(f"{s.language}: {s.content[:50]}...")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# =============================================================================
# Task 1.1: CodeSnippet dataclass
# =============================================================================


@dataclass(slots=True)
class CodeSnippet:
    """A code snippet extracted from cached package documentation.

    Attributes:
        language: Code block language tag (python, javascript, typescript, bash, etc.)
        content: The actual code content.
        context: Text preceding the code block (up to 3 lines).
        score: Quality score (higher = better). Install commands score 0.
        source_file: Which cached file this came from (e.g., "doc.md", "quickstart.md").
        package: Package name for reference.
    """

    language: str
    content: str
    context: str
    score: int
    source_file: str
    package: str


# =============================================================================
# Task 1.2: UsageExtractor class
# =============================================================================


class UsageExtractor:
    """Extract and rank code snippets from cached package documentation.

    This class parses markdown files stored in the docs cache directory
    and extracts fenced code blocks, scoring them by quality heuristics
    to rank actual usage examples above installation commands.

    The cache structure is:
        .pf/context/docs/{manager}/{safe_name}@{safe_version}/doc.md

    Where:
        - manager: npm, py, cargo, go
        - safe_name: Package name with escaping (@->_at_, /->_)
        - safe_version: Version with escaping (:/\\->_)
    """

    # Scoring weights (tunable constants)
    SCORE_BASE = 10
    SCORE_USAGE_KEYWORD = 5
    SCORE_HAS_IMPORT = 5
    SCORE_MULTILINE = 2
    SCORE_NOT_WALL = 1
    SCORE_COMMON_LANG = 1
    SCORE_TYPESCRIPT_BONUS = 1
    SCORE_ASYNC_PATTERN = 1
    SCORE_HELP_OUTPUT = -5

    # Languages considered "common" for bonus scoring
    COMMON_LANGS = {"python", "javascript", "typescript", "js", "ts", "rust", "go"}

    # Install command patterns that should be demoted to score 0
    INSTALL_PATTERNS = [
        r"\bnpm\s+install\b",
        r"\byarn\s+add\b",
        r"\bpnpm\s+add\b",
        r"\bpip\s+install\b",
        r"\bcargo\s+add\b",
        r"\bgo\s+get\b",
        r"\bbower\s+install\b",
    ]

    def __init__(self, docs_dir: str = "./.pf/context/docs") -> None:
        """Initialize the extractor with a docs cache directory.

        Args:
            docs_dir: Path to the docs cache directory.
                      Defaults to "./.pf/context/docs".
        """
        self.docs_dir = Path(docs_dir)

    def extract_usage(
        self,
        manager: str,
        package: str,
        version: str | None = None,
        limit: int = 10,
    ) -> list[CodeSnippet]:
        """Extract and rank code snippets from cached docs.

        Args:
            manager: Package manager (npm, py, cargo, go).
            package: Package name (e.g., "axios", "@angular/core", "requests").
            version: Specific version or None for latest cached.
            limit: Max snippets to return (default 10).

        Returns:
            List of CodeSnippet sorted by score descending.
            Empty list if package not cached (does NOT raise).
        """
        pkg_dir = self._find_package_dir(manager, package, version)
        if pkg_dir is None:
            return []

        # Parse all markdown files in the package directory
        all_snippets: list[CodeSnippet] = []
        for md_file in pkg_dir.glob("*.md"):
            snippets = self._parse_markdown(md_file, package)
            all_snippets.extend(snippets)

        # Sort by score descending, then by content length (prefer substantial)
        all_snippets.sort(key=lambda s: (-s.score, -len(s.content)))

        return all_snippets[:limit]

    # =========================================================================
    # Task 1.3: _find_package_dir (MUST match docs_fetch.py escaping)
    # =========================================================================

    def _find_package_dir(
        self, manager: str, package: str, version: str | None = None
    ) -> Path | None:
        """Find cached package directory.

        Escaping rules (from docs_fetch.py:219-233):
        - npm: @ -> _at_, / -> _
        - py/cargo/go: / and \\ -> _
        - Version: :, /, \\ -> _ (or git hash for git URLs)

        Args:
            manager: "npm", "py", "cargo", or "go"
            package: Package name (e.g., "axios", "@angular/core", "requests")
            version: Specific version or None (finds first match)

        Returns:
            Path to package directory, or None if not cached.
            Does NOT raise (ZERO FALLBACK - caller handles missing).
        """
        mgr_dir = self.docs_dir / manager
        if not mgr_dir.exists():
            return None

        # Escape package name (match docs_fetch.py exactly)
        if manager == "npm":
            safe_name = package.replace("@", "_at_").replace("/", "_")
        else:
            safe_name = re.sub(r"[/\\]", "_", package)

        if version:
            # Exact version match
            safe_version = re.sub(r"[:/\\]", "_", version)
            pkg_path = mgr_dir / f"{safe_name}@{safe_version}"
            return pkg_path if pkg_path.exists() else None
        else:
            # Find any version (glob for {safe_name}@*)
            matches = list(mgr_dir.glob(f"{safe_name}@*"))
            if matches:
                # Return most recently modified (likely latest)
                return max(matches, key=lambda p: p.stat().st_mtime)
            return None

    # =========================================================================
    # Task 1.4: _parse_markdown with CORRECT multi-line context regex
    # =========================================================================

    def _parse_markdown(self, path: Path, package: str) -> list[CodeSnippet]:
        """Parse a markdown file and extract code snippets.

        Args:
            path: Path to the markdown file.
            package: Package name for the snippet metadata.

        Returns:
            List of CodeSnippet objects with scores applied.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        snippets: list[CodeSnippet] = []
        source_file = path.name

        # Pattern captures MULTI-LINE context before code block
        # Group 1: Up to 3 lines before (no backticks in those lines)
        # Group 2: Language tag (may be empty)
        # Group 3: Code content (non-greedy)
        pattern = re.compile(
            r"((?:^[^\n`]*\n){0,3})"  # Up to 3 lines before (no backticks)
            r"^```(\w*)\n"  # Opening fence with optional language
            r"(.*?)"  # Code content (non-greedy)
            r"^```",  # Closing fence
            re.MULTILINE | re.DOTALL,
        )

        for match in pattern.finditer(content):
            context = match.group(1).strip()
            language = match.group(2).lower()
            code = match.group(3).strip()

            if not code:
                continue

            score = self._score_snippet(code, language, context)

            snippets.append(
                CodeSnippet(
                    language=language,
                    content=code,
                    context=context,
                    score=score,
                    source_file=source_file,
                    package=package,
                )
            )

        return snippets

    # =========================================================================
    # Task 1.5: _score_snippet with heuristics
    # =========================================================================

    def _score_snippet(self, code: str, lang: str, context: str) -> int:
        """Score a code snippet by quality heuristics.

        Scoring rules:
        - Base score: 10
        - DEMOTE to 0: Install commands (npm install, pip install, etc.)
        - DEMOTE -5: Help output (--help, Usage:)
        - PROMOTE +5: Usage keywords in context (usage, example, quickstart, how to)
        - PROMOTE +5: Import statements (import, require, from, use)
        - PROMOTE +2: Multi-line code (>3 lines)
        - PROMOTE +1: Not a wall of text (<50 lines)
        - PROMOTE +1: Common language (python, javascript, typescript, rust, go)
        - PROMOTE +1: TypeScript over JavaScript
        - PROMOTE +1: Async/await patterns

        Args:
            code: The code content.
            lang: Language tag from the code fence.
            context: Text preceding the code block.

        Returns:
            Integer score. Higher is better. Install commands return 0.
        """
        # Check for install commands first - immediate disqualification
        code_lower = code.lower()
        for pattern in self.INSTALL_PATTERNS:
            if re.search(pattern, code_lower):
                return 0

        # Shell blocks with install-like content get score 0
        if lang in ("bash", "sh", "shell", "") and any(
            cmd in code_lower
            for cmd in ["install", "add axios", "add react", "get ", "$ npm", "$ pip"]
        ):
            return 0

        score = self.SCORE_BASE

        # DEMOTE: Help output
        if "--help" in code or code.strip().startswith("Usage:"):
            score += self.SCORE_HELP_OUTPUT

        # PROMOTE: Usage keywords in context
        context_lower = context.lower()
        usage_keywords = ["usage", "example", "quickstart", "how to", "getting started"]
        if any(kw in context_lower for kw in usage_keywords):
            score += self.SCORE_USAGE_KEYWORD

        # PROMOTE: Import statements
        import_patterns = ["import ", "require(", "from ", "use "]
        if any(pat in code for pat in import_patterns):
            score += self.SCORE_HAS_IMPORT

        # PROMOTE: Multi-line code (>3 lines = non-trivial)
        line_count = code.count("\n") + 1
        if line_count > 3:
            score += self.SCORE_MULTILINE

        # PROMOTE: Not a wall of text (<50 lines)
        if line_count < 50:
            score += self.SCORE_NOT_WALL

        # PROMOTE: Common languages
        if lang in self.COMMON_LANGS:
            score += self.SCORE_COMMON_LANG

        # SPECIAL: TypeScript bonus over JavaScript
        if lang in ("typescript", "ts"):
            score += self.SCORE_TYPESCRIPT_BONUS

        # SPECIAL: Async/await patterns (modern code)
        if "async " in code or "await " in code:
            score += self.SCORE_ASYNC_PATTERN

        return score
