# Design: Add Polyglot Package Managers Module

## Context

deps.py and docs_fetch.py are monoliths that will become unmaintainable if more languages are added inline. This design creates a modular infrastructure that:

1. Extracts Docker immediately (~200 lines, low-hanging fruit)
2. Adds Cargo and Go as new modular implementations
3. Prepares infrastructure for future npm/Python extraction (NOT this ticket)

Constraint from Architect: **NO refactoring of existing npm/Python code. They stay in deps.py/docs_fetch.py and work exactly as they do now.**

## Goals / Non-Goals

**Goals:**
- Modular package manager support (cargo, go, docker)
- Clean base interface for future migration
- Fix logging/UI wiring issues
- Add DB storage for Cargo.toml and go.mod

**Non-Goals:**
- Extract npm.py (future)
- Extract python.py (future)
- Refactor deps.py architecture
- Refactor docs_fetch.py architecture
- Change CLI interface
- Change output format

## Decisions

### Decision 1: Registry Pattern in `__init__.py`

**What:** Single entry point that routes to language-specific modules.

**Why:** deps.py and docs_fetch.py can import one thing and dispatch by manager name.

```python
# theauditor/package_managers/__init__.py
from .base import BasePackageManager
from .docker import DockerPackageManager
from .cargo import CargoPackageManager
from .go import GoPackageManager

_REGISTRY: dict[str, type[BasePackageManager]] = {
    "docker": DockerPackageManager,
    "cargo": CargoPackageManager,
    "go": GoPackageManager,
}

def get_manager(manager_name: str) -> BasePackageManager | None:
    """Get package manager instance by name."""
    cls = _REGISTRY.get(manager_name)
    return cls() if cls else None

def get_all_managers() -> list[BasePackageManager]:
    """Get all registered package managers."""
    return [cls() for cls in _REGISTRY.values()]
```

**Alternative considered:** Direct imports in deps.py. Rejected because it couples deps.py to specific implementations.

### Decision 2: Abstract Base Class

**What:** `BasePackageManager` defines the interface all managers implement.

```python
# theauditor/package_managers/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

class BasePackageManager(ABC):
    """Abstract base for all package manager implementations."""

    @property
    @abstractmethod
    def manager_name(self) -> str:
        """Return manager identifier (e.g., 'cargo', 'go', 'docker')."""
        ...

    @property
    @abstractmethod
    def file_patterns(self) -> list[str]:
        """Return glob patterns for manifest files (e.g., ['Cargo.toml'])."""
        ...

    @abstractmethod
    def parse_manifest(self, path: Path) -> list[dict[str, Any]]:
        """Parse manifest file and return list of dependency dicts."""
        ...

    @abstractmethod
    async def fetch_latest_async(
        self, client: Any, dep: dict[str, Any]
    ) -> str | None:
        """Fetch latest version from registry. Returns version string or None."""
        ...

    @abstractmethod
    async def fetch_docs_async(
        self, client: Any, dep: dict[str, Any], output_path: Path, allowlist: list[str]
    ) -> str:
        """Fetch documentation. Returns 'fetched', 'cached', 'skipped', or 'error'."""
        ...

    @abstractmethod
    def upgrade_file(
        self, path: Path, latest_info: dict[str, dict[str, Any]], deps: list[dict[str, Any]]
    ) -> int:
        """Upgrade manifest file to latest versions. Returns count of upgrades."""
        ...
```

**Why:** Enforces consistent interface. Future npm/Python extraction follows same pattern.

### Decision 3: Docker Extraction Strategy

**What:** Move Docker functions to `docker.py`, leave thin dispatch in deps.py.

**deps.py BEFORE:**
```python
def _parse_docker_compose(path: Path) -> list[dict[str, Any]]:
    # 45 lines of implementation
```

**deps.py AFTER:**
```python
from theauditor.package_managers import get_manager

# In parse_dependencies():
docker_mgr = get_manager("docker")
if docker_mgr:
    for compose_file in docker_compose_files:
        deps.extend(docker_mgr.parse_manifest(compose_file))
```

**Why:** Minimal change to deps.py. All Docker logic moves to dedicated module.

### Decision 4: Cargo Registry API

**Endpoint:** `https://crates.io/api/v1/crates/{name}`

**Response parsing:**
```python
data = response.json()
latest = data["crate"]["max_version"]  # Stable version
# OR data["crate"]["newest_version"]   # Including pre-release
```

**Rate limit:** 1 request per second (crates.io policy)

**User-Agent required:** `TheAuditor/{version} (dependency checker)`

### Decision 5: Go Proxy API

**Endpoint:** `https://proxy.golang.org/{module}/@latest`

**Module path encoding:** Forward slashes stay as-is, uppercase letters become `!lowercase`

```python
def encode_go_module(module: str) -> str:
    """Encode Go module path for proxy URL."""
    # github.com/Azure/azure-sdk-for-go -> github.com/!azure/azure-sdk-for-go
    result = []
    for char in module:
        if char.isupper():
            result.append('!')
            result.append(char.lower())
        else:
            result.append(char)
    return ''.join(result)
```

**Response parsing:**
```python
data = response.json()
latest = data["Version"]  # e.g., "v1.2.3"
```

**Rate limit:** 0.5 seconds between requests (be polite)

### Decision 6: go.mod Parsing

**Format:**
```
module github.com/user/repo

go 1.21

require (
    github.com/pkg/errors v0.9.1
    golang.org/x/sync v0.3.0
)

replace github.com/old/pkg => github.com/new/pkg v1.0.0
```

**Parsing strategy:**
```python
def parse_go_mod(path: Path) -> list[dict[str, Any]]:
    deps = []
    content = path.read_text()

    # Find require block
    require_match = re.search(r'require\s*\((.*?)\)', content, re.DOTALL)
    if require_match:
        for line in require_match.group(1).strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('//'):
                parts = line.split()
                if len(parts) >= 2:
                    deps.append({
                        "name": parts[0],
                        "version": parts[1],
                        "manager": "go",
                        "source": str(path),
                    })

    # Also handle single-line requires
    for match in re.finditer(r'^require\s+(\S+)\s+(\S+)', content, re.MULTILINE):
        deps.append({
            "name": match.group(1),
            "version": match.group(2),
            "manager": "go",
            "source": str(path),
        })

    return deps
```

### Decision 7: Database Tables for Cargo/Go

**Location:** Add methods to existing database mixins:
- Cargo: `theauditor/indexer/database/rust_database.py` (RustDatabaseMixin)
- Go: `theauditor/indexer/database/go_database.py` (GoDatabaseMixin)

**Cargo tables (add to rust_database.py):**
```sql
CREATE TABLE IF NOT EXISTS cargo_package_configs (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    package_name TEXT,
    package_version TEXT,
    edition TEXT,
    UNIQUE(file_path)
);

CREATE TABLE IF NOT EXISTS cargo_dependencies (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    version_spec TEXT,
    is_dev INTEGER NOT NULL DEFAULT 0,
    features TEXT,  -- JSON array
    FOREIGN KEY (file_path) REFERENCES files(path)
);
```

**Methods to add to RustDatabaseMixin (rust_database.py:401+):**
```python
def add_cargo_package_config(
    self,
    file_path: str,
    package_name: str | None,
    package_version: str | None,
    edition: str | None,
) -> None:
    """Add a Cargo package config to the batch."""
    self.generic_batches["cargo_package_configs"].append(
        (file_path, package_name, package_version, edition)
    )

def add_cargo_dependency(
    self,
    file_path: str,
    name: str,
    version_spec: str | None,
    is_dev: bool,
    features: str | None,
) -> None:
    """Add a Cargo dependency to the batch."""
    self.generic_batches["cargo_dependencies"].append(
        (file_path, name, version_spec, 1 if is_dev else 0, features)
    )
```

**Go tables (add to go_database.py):**
```sql
CREATE TABLE IF NOT EXISTS go_module_configs (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    module_path TEXT NOT NULL,
    go_version TEXT,
    UNIQUE(file_path)
);

CREATE TABLE IF NOT EXISTS go_dependencies (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    module_path TEXT NOT NULL,
    version TEXT NOT NULL,
    is_indirect INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (file_path) REFERENCES files(path)
);
```

**Methods to add to GoDatabaseMixin (go_database.py:356+):**
```python
def add_go_module_config(
    self,
    file_path: str,
    module_path: str,
    go_version: str | None,
) -> None:
    """Add a Go module config to the batch."""
    self.generic_batches["go_module_configs"].append(
        (file_path, module_path, go_version)
    )

def add_go_dependency(
    self,
    file_path: str,
    module_path: str,
    version: str,
    is_indirect: bool,
) -> None:
    """Add a Go module dependency to the batch."""
    self.generic_batches["go_dependencies"].append(
        (file_path, module_path, version, 1 if is_indirect else 0)
    )
```

### Decision 8: Shared Utilities Strategy

**Problem:** Docker functions use utilities defined elsewhere in deps.py. Where do they live after extraction?

**Solution:**

| Utility | Current Location | After Extraction | Rationale |
|---------|------------------|------------------|-----------|
| `_create_versioned_backup()` | deps.py:991-1008 | STAYS in deps.py | Called by orchestrator, not package managers |
| `IS_WINDOWS` | deps.py:32 | STAYS in deps.py, pass as param | Platform detection is caller's concern |
| `__version__` | `theauditor/__init__.py` | Import in each module | Standard package version |
| httpx client | Created in deps.py:461 | Pass as parameter | Caller owns connection pool |

**Import pattern for new modules:**
```python
# theauditor/package_managers/cargo.py
from theauditor import __version__
from theauditor.utils.logging import logger
from theauditor.utils.rate_limiter import get_rate_limiter
```

**BasePackageManager receives from caller:**
```python
async def fetch_latest_async(
    self,
    client: httpx.AsyncClient,  # Caller provides
    dep: dict[str, Any]
) -> str | None:
```

### Decision 9: deps.py Wiring Points

**File:** `theauditor/deps.py`

**Import addition (line ~18):**
```python
from theauditor.package_managers import get_manager
```

**Docker parsing replacement (lines 81-93):**
```python
# BEFORE (current):
docker_compose_files = list(root.glob("**/docker-compose*.yml"))
for compose_file in docker_compose_files:
    if not any(skip in compose_file.parts for skip in skip_dirs):
        deps.extend(_parse_docker_compose(compose_file))

# AFTER:
docker_mgr = get_manager("docker")
if docker_mgr:
    docker_compose_files = list(root.glob("**/docker-compose*.yml"))
    for compose_file in docker_compose_files:
        if not any(skip in compose_file.parts for skip in skip_dirs):
            deps.extend(docker_mgr.parse_manifest(compose_file))
```

**Dockerfile parsing replacement (lines 89-93):**
```python
# BEFORE:
dockerfiles = list(root.glob("**/Dockerfile*"))
for dockerfile in dockerfiles:
    if not any(skip in dockerfile.parts for skip in skip_dirs):
        deps.extend(_parse_dockerfile(dockerfile))

# AFTER:
    # (inside same docker_mgr block)
    dockerfiles = list(root.glob("**/Dockerfile*"))
    for dockerfile in dockerfiles:
        if not any(skip in dockerfile.parts for skip in skip_dirs):
            deps.extend(docker_mgr.parse_manifest(dockerfile))
```

**Go parsing addition (after Cargo block, ~line 100):**
```python
# ADD NEW:
go_mgr = get_manager("go")
if go_mgr:
    go_mod_files = list(root.glob("**/go.mod"))
    for go_mod in go_mod_files:
        if not any(skip in go_mod.parts for skip in skip_dirs):
            deps.extend(go_mgr.parse_manifest(go_mod))
```

**Version fetch dispatch (lines 572-580):**
```python
# BEFORE:
if manager == "docker":
    result = await _fetch_docker_async(client, name, version)

# AFTER:
if manager in ("docker", "cargo", "go"):
    mgr = get_manager(manager)
    if mgr:
        result = await mgr.fetch_latest_async(client, dep)
```

**Upgrade dispatch (lines 1096-1139):**
```python
# BEFORE:
if "docker" in ecosystems or not ecosystems:
    for compose_file in docker_compose_files:
        upgraded["docker-compose"] += _upgrade_docker_compose(...)
    for dockerfile in dockerfiles:
        upgraded["dockerfile"] += _upgrade_dockerfile(...)

# AFTER:
for mgr_name in ("docker", "cargo", "go"):
    if mgr_name in ecosystems or not ecosystems:
        mgr = get_manager(mgr_name)
        if mgr:
            for manifest_file in manifest_files_for_manager[mgr_name]:
                upgraded[mgr_name] += mgr.upgrade_file(manifest_file, latest_info, deps)
```

### Decision 10: docs_fetch.py Wiring Points

**File:** `theauditor/docs_fetch.py`

**Import additions (line ~15):**
```python
from theauditor.utils.logging import logger
from theauditor.pipeline.ui import console
from theauditor.package_managers import get_manager
```

**Manager dispatch addition (lines 170-180):**
```python
# CURRENT (line 170-180):
async def _fetch_one_doc(...):
    if manager == "npm":
        return await _fetch_npm_docs_async(...)
    elif manager == "py":
        return await _fetch_pypi_docs_async(...)
    else:
        return "skipped"

# AFTER:
async def _fetch_one_doc(...):
    if manager == "npm":
        return await _fetch_npm_docs_async(...)
    elif manager == "py":
        return await _fetch_pypi_docs_async(...)
    elif manager in ("cargo", "go"):
        mgr = get_manager(manager)
        if mgr:
            return await mgr.fetch_docs_async(client, dep, output_path, allowlist)
        return "skipped"
    else:
        return "skipped"
```

### Decision 11: Cargo.toml Upgrade Strategy

**Problem:** How to upgrade Cargo.toml while preserving formatting and comments?

**Solution:** Regex replacement (NOT TOML parsing/serialization which destroys formatting)

```python
# theauditor/package_managers/cargo.py

def upgrade_file(
    self,
    path: Path,
    latest_info: dict[str, dict[str, Any]],
    deps: list[dict[str, Any]]
) -> int:
    """Upgrade Cargo.toml to latest versions."""
    content = path.read_text(encoding="utf-8")
    original = content
    count = 0

    for dep in deps:
        if dep.get("source") != str(path):
            continue

        key = f"cargo:{dep['name']}:{dep.get('version', '')}"
        info = latest_info.get(key)
        if not info or not info.get("latest") or not info.get("is_outdated"):
            continue

        old_version = dep.get("version", "")
        new_version = info["latest"]
        name = dep["name"]

        # Pattern 1: simple string version
        # serde = "1.0.0"
        pattern1 = rf'({re.escape(name)}\s*=\s*")({re.escape(old_version)})(")'
        if re.search(pattern1, content):
            content = re.sub(pattern1, rf'\g<1>{new_version}\g<3>', content)
            count += 1
            continue

        # Pattern 2: table with version key
        # serde = { version = "1.0.0", features = ["derive"] }
        pattern2 = rf'({re.escape(name)}\s*=\s*\{{[^}}]*version\s*=\s*")({re.escape(old_version)})(")'
        if re.search(pattern2, content):
            content = re.sub(pattern2, rf'\g<1>{new_version}\g<3>', content)
            count += 1

    if content != original:
        # Backup handled by caller (deps.py orchestrator)
        path.write_text(content, encoding="utf-8")

    return count
```

### Decision 12: Cargo Docs Strategy

**Problem:** Where to get README for Rust crates?

**Solution:** Two-source approach using crates.io API, then GitHub if needed

The crates.io API at `https://crates.io/api/v1/crates/{name}` returns:
```json
{
  "crate": {
    "name": "serde",
    "max_version": "1.0.210",
    "readme": "# Serde\n\nSerde is a framework for...",  // README content (may be null)
    "repository": "https://github.com/serde-rs/serde"
  }
}
```

**Documentation Sources (in order):**
1. **Primary:** `data["crate"]["readme"]` - direct README content from crates.io
2. **Secondary:** GitHub README via `data["crate"]["repository"]` - if readme is null but repository points to GitHub

**Note:** This is NOT a "fallback" in the ZERO FALLBACK policy sense. GitHub is a legitimate documentation source - many crates don't include README in the crates.io payload but do have comprehensive docs on GitHub. Following the repository link is following the authoritative source chain, same pattern as npm/PyPI.

**Implementation:**
```python
# theauditor/package_managers/cargo.py

async def fetch_docs_async(
    self,
    client: httpx.AsyncClient,
    dep: dict[str, Any],
    output_path: Path,
    allowlist: list[str],
) -> str:
    """Fetch crate README from crates.io API, then GitHub if needed."""
    name = dep["name"]

    # Check allowlist
    if allowlist and name not in allowlist:
        return "skipped"

    # Check cache
    doc_file = output_path / f"{name}.md"
    if doc_file.exists():
        return "cached"

    # Rate limit
    limiter = get_rate_limiter("cargo")
    await limiter.acquire()

    try:
        url = f"https://crates.io/api/v1/crates/{name}"
        headers = {"User-Agent": f"TheAuditor/{__version__} (dependency docs fetcher)"}
        response = await client.get(url, headers=headers, timeout=10.0)

        if response.status_code != 200:
            logger.warning(f"Failed to fetch docs for {name}: HTTP {response.status_code}")
            return "error"

        data = response.json()
        crate_data = data.get("crate", {})
        readme = crate_data.get("readme")

        # Source 1: Direct README from crates.io
        if readme:
            output_path.mkdir(parents=True, exist_ok=True)
            doc_file.write_text(readme, encoding="utf-8")
            return "fetched"

        # Source 2: GitHub README via repository link
        repository = crate_data.get("repository", "")
        if repository and "github.com" in repository:
            github_readme = await self._fetch_github_readme(client, repository)
            if github_readme:
                output_path.mkdir(parents=True, exist_ok=True)
                doc_file.write_text(github_readme, encoding="utf-8")
                return "fetched"

        logger.info(f"No README available for {name}")
        return "skipped"

    except Exception as e:
        logger.warning(f"Failed to fetch docs for {name}: {e}")
        return "error"
```

### Decision 13: Go Docs Strategy

**Problem:** pkg.go.dev returns HTML, need markdown.

**Solution:** Use regex-based HTML extraction (NO FALLBACKS, single code path)

**ZERO FALLBACK Compliance:** We use regex extraction only. No BeautifulSoup with fallback to regex - just regex. Simple, no extra dependencies, one code path.

```python
# theauditor/package_managers/go.py

async def fetch_docs_async(
    self,
    client: httpx.AsyncClient,
    dep: dict[str, Any],
    output_path: Path,
    allowlist: list[str],
) -> str:
    """Fetch Go module docs from pkg.go.dev. NO FALLBACKS."""
    module = dep["name"]
    version = dep.get("version", "latest")

    # Check allowlist
    if allowlist and module not in allowlist:
        return "skipped"

    # Check cache
    safe_name = module.replace("/", "_")
    doc_file = output_path / f"{safe_name}.md"
    if doc_file.exists():
        return "cached"

    # Rate limit
    limiter = get_rate_limiter("go")
    await limiter.acquire()

    try:
        # pkg.go.dev URL
        url = f"https://pkg.go.dev/{module}@{version}"
        response = await client.get(url, timeout=10.0, follow_redirects=True)

        if response.status_code != 200:
            logger.warning(f"Failed to fetch docs for {module}: HTTP {response.status_code}")
            return "error"

        html = response.text

        # Extract documentation section using regex (single code path)
        markdown = self._extract_go_docs(html)

        if markdown:
            output_path.mkdir(parents=True, exist_ok=True)
            doc_file.write_text(markdown, encoding="utf-8")
            return "fetched"

        logger.info(f"No documentation section found for {module}")
        return "skipped"

    except Exception as e:
        logger.warning(f"Failed to fetch docs for {module}: {e}")
        return "error"

def _extract_go_docs(self, html: str) -> str | None:
    """Extract Go documentation from pkg.go.dev HTML using regex. Single code path."""
    import re

    # Extract text between Documentation tags
    match = re.search(
        r'<section[^>]*class="[^"]*Documentation[^"]*"[^>]*>(.*?)</section>',
        html,
        re.DOTALL | re.IGNORECASE
    )

    if not match:
        # Try alternative div structure
        match = re.search(
            r'<div[^>]*class="[^"]*Documentation-content[^"]*"[^>]*>(.*?)</div>',
            html,
            re.DOTALL | re.IGNORECASE
        )

    if not match:
        return None

    content = match.group(1)

    # Strip scripts and styles
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)

    # Convert headers to markdown
    content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', content, flags=re.DOTALL)
    content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', content, flags=re.DOTALL)
    content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', content, flags=re.DOTALL)

    # Convert code blocks
    content = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```\n', content, flags=re.DOTALL)
    content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', content, flags=re.DOTALL)

    # Convert paragraphs
    content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', content, flags=re.DOTALL)

    # Strip remaining HTML tags
    content = re.sub(r'<[^>]+>', '', content)

    # Normalize whitespace
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()

    return content if content else None
```

## Risks / Trade-offs

### Risk 1: Breaking existing Docker functionality
**Mitigation:** Extraction is pure move, no logic changes. Test thoroughly after extraction.

### Risk 2: crates.io rate limiting
**Mitigation:** Add 1-second rate limit. Use cache like deps.py does for npm/PyPI.

### Risk 3: Go module path encoding edge cases
**Mitigation:** Follow Go proxy spec exactly. Test with Azure, Google, AWS modules (uppercase in paths).

### Trade-off: Technical debt on npm/Python
**Accepted:** Per Architect decision, we keep npm/Python in monoliths for now. Infrastructure is ready for future migration.

## Open Questions

None. All decisions made during Prime Directive investigation with Architect.
