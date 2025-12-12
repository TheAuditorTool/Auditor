# Design: add-usage-extractor

## Context

TheAuditor's `docs_fetch.py` (652 lines) already:
1. Fetches docs from NPM registry, PyPI, crates.io, pkg.go.dev
2. Converts HTML to markdown via BeautifulSoup + markdownify
3. Caches to `.pf/context/docs/{manager}/{name}@{version}/doc.md`
4. Optionally fetches `quickstart.md`, `api.md`, `tutorial.md` from ReadTheDocs

**The gap**: No code parses these cached files back into queryable snippets.

**Stakeholders**:
- AI agents that need "how do I use library X?" answered with code, not prose
- Developers using `aud` CLI for quick reference

## Goals / Non-Goals

### Goals
- Extract code snippets from cached markdown docs
- Score snippets by quality (promote usage, demote installation)
- Provide CLI interface via `aud deps --usage <package>`
- Support JSON output for AI agent consumption
- Work entirely offline with existing cache

### Non-Goals
- NOT a web crawler or search engine
- NOT modifying `docs_fetch.py` behavior (it stays as-is)
- NOT supporting arbitrary URLs (only cached docs)
- NOT semantic understanding of code (heuristic scoring only)
- NOT caching extracted snippets (re-parse on each query - markdown is small)

## Decisions

### Decision 1: Integration Point = `aud deps --usage`

**What**: Add `--usage <package>` flag to existing `aud deps` command.

**Why NOT `aud explain --usage`**:
- `aud explain` is for code context (files, symbols, components in YOUR codebase)
- `aud deps` already handles packages (versions, upgrades, vulnerabilities)
- Natural fit: "tell me about this dependency" -> `aud deps`

**Why NOT new `aud docs` command**:
- Avoid command proliferation
- `deps` command already has related flags (`--check-latest`, `--vuln-scan`)
- Users already associate `aud deps` with package management

**Alternatives considered**:
1. `aud docs query <package>` - New command, but adds cognitive load
2. `aud explain --package <name>` - Conflates code analysis with doc mining
3. `aud context --package <name>` - Context module is for code, not external docs

### Decision 2: Heuristic Scoring (Not ML)

**What**: Score snippets with simple rules, not machine learning.

**Why**:
- Deterministic and debuggable
- No model dependencies or inference latency
- Heuristics are "good enough" for this use case
- Can tune rules based on feedback without retraining

**Scoring weights** (tunable constants at top of module):
```python
SCORE_BASE = 10
SCORE_INSTALL_COMMAND = 0      # npm install, pip install -> reject
SCORE_USAGE_KEYWORD = 5        # "usage", "example" in context
SCORE_HAS_IMPORT = 5           # import/require statement
SCORE_MULTILINE = 2            # >3 lines
SCORE_NOT_WALL = 1             # <50 lines
SCORE_MODERN_PATTERN = 1       # async/await
SCORE_HELP_OUTPUT = -5         # --help, Usage:
```

### Decision 3: No Snippet Caching

**What**: Re-parse markdown on every `--usage` query.

**Why**:
- Markdown files are small (<100KB typically)
- Parsing is fast (<50ms)
- Avoids cache invalidation complexity
- Cache is already version-pinned (axios@1.13.2 won't change)

**Trade-off**: Repeated queries do redundant work. Acceptable because:
- Queries are infrequent (AI asks once per task)
- Latency is imperceptible (<100ms total)

### Decision 4: Graceful Cache Miss -> Fetch

**What**: If cache is empty for requested package, attempt to fetch docs (if online).

**Why**:
- Better UX than "not found, run aud full first"
- Single command does what user wants
- Still respects `--offline` flag

**Implementation**:
```python
snippets = extractor.extract_usage(manager, package)
if not snippets and not offline:
    console.print(f"Cache miss for {package}, fetching docs...")
    fetch_docs([{"name": package, "version": "latest", "manager": manager}])
    snippets = extractor.extract_usage(manager, package)  # Retry once
```

### Decision 5: Multi-Line Context Capture

**What**: Capture up to 3 lines before each code block as context.

**Why the original proposal was wrong**:
```python
# WRONG - Only captures ONE line
pattern = re.compile(r"([^\n]+)\n+```(\w+)\n(.*?)```", re.DOTALL)
```

**Correct pattern**:
```python
# RIGHT - Captures up to 3 preceding non-empty lines
pattern = re.compile(
    r'((?:^[^\n`]*\n){0,3})'  # 0-3 lines before (no backticks)
    r'^```(\w*)\n'            # Opening fence
    r'(.*?)'                  # Content
    r'^```',                  # Closing fence
    re.MULTILINE | re.DOTALL
)
```

**Why 3 lines**: Most markdown has 1-2 line descriptions before code. 3 is generous without capturing unrelated content.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Regex doesn't handle all markdown variants | Use conservative parsing, skip malformed blocks, don't crash |
| Scoring misses good examples | Heuristics are tunable, start conservative, iterate |
| Scoped package names (`@scope/name`) break path lookup | Explicit handling: `@` -> `_at_`, `/` -> `_` (matches docs_fetch.py) |
| Empty results frustrate users | Clear messaging: "No examples found. Try: aud full --offline" |

## File Structure

```
theauditor/package_managers/
  __init__.py          # Already exists
  deps.py              # Already exists - will add fetch_docs import
  docs_fetch.py        # Already exists - no changes
  usage_extractor.py   # NEW - ~150 lines

theauditor/commands/
  deps.py              # MODIFY - add --usage option (~30 lines added)
```

## API Design

### UsageExtractor Class

```python
@dataclass
class CodeSnippet:
    language: str
    content: str
    context: str
    score: int
    source_file: str
    package: str

class UsageExtractor:
    def __init__(self, docs_dir: str = "./.pf/context/docs"):
        self.docs_dir = Path(docs_dir)

    def extract_usage(
        self,
        manager: str,
        package: str,
        version: str | None = None,
        limit: int = 10
    ) -> list[CodeSnippet]:
        """Extract and rank code snippets from cached docs.

        Args:
            manager: Package manager (npm, py, cargo, go)
            package: Package name (e.g., "axios", "@angular/core", "requests")
            version: Specific version or None for latest cached
            limit: Max snippets to return (default 10)

        Returns:
            List of CodeSnippet sorted by score descending.
            Empty list if package not cached (does NOT raise).
        """
```

### CLI Interface

```bash
# Basic usage
aud deps --usage axios
aud deps --usage requests
aud deps --usage @angular/core

# JSON for AI agents
aud deps --usage axios --format json

# Combines with other flags
aud deps --usage axios --offline  # Won't fetch if cache miss
```

## Open Questions

None. All decisions are final pending implementation feedback.

## Package Path Escaping (EMBEDDED from docs_fetch.py:219-233)

The `_find_package_dir` method in `usage_extractor.py` MUST match this exact logic from `docs_fetch.py`:

```python
def _get_pkg_dir(output_dir: Path, manager: str, name: str, version: str) -> Path:
    """Get the package-specific cache directory."""

    # Version escaping (handles git URLs)
    if version.startswith("git") or "://" in version:
        version_hash = hashlib.md5(version.encode()).hexdigest()[:8]
        safe_version = f"git-{version_hash}"
    else:
        safe_version = re.sub(r"[:/\\]", "_", version)

    # Name escaping (npm scoped packages vs others)
    if manager == "npm":
        safe_name = name.replace("@", "_at_").replace("/", "_")
    else:
        safe_name = re.sub(r"[/\\]", "_", name)

    return output_dir / manager / f"{safe_name}@{safe_version}"
```

**Examples**:
| Input | Manager | Output Directory |
|-------|---------|------------------|
| `axios`, `1.13.2` | npm | `npm/axios@1.13.2/` |
| `@angular/core`, `18.0.0` | npm | `npm/_at_angular_core@18.0.0/` |
| `requests`, `==2.28.0` | py | `py/requests@==2.28.0/` |
| `click`, `==8.3.1` | py | `py/click@==8.3.1/` |

**CRITICAL**: The `==` prefix in Python versions is preserved (not stripped). This is intentional - it matches how poetry/pip specify exact versions.

## References

- `theauditor/package_managers/docs_fetch.py:219-233` - `_get_pkg_dir()` (embedded above)
- `theauditor/package_managers/docs_fetch.py:75-108` - `fetch_docs()` signature
- `theauditor/commands/deps.py:16-51` - CLI option insertion points
- `.pf/context/docs/npm/axios@1.13.2/doc.md` - Example cached doc (7KB, has code blocks)
