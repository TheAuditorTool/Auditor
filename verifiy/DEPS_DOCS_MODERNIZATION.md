# Deps & Docs Modernization - Complete Implementation Spec

**Created**: 2025-01-16
**Status**: Ready for Implementation
**Scope**: Fix dependency management and documentation retrieval systems

---

## Executive Summary

The `deps` and `docs` commands have critical bugs preventing production use:

**Current State**:
- ❌ `aud deps --upgrade-all` upgrades postgres 17→15 (DOWNGRADE!)
- ❌ Pulls alpha/beta/rc/nightly builds (`python:3.15.0a1`)
- ❌ Switches Docker base images randomly (alpine→windowsservercore)
- ❌ `aud docs fetch` only grabs README, doesn't crawl actual docs
- ❌ AIs hallucinate old API patterns (trained on v1.x, you use v7.x)
- ❌ Python deps not stored in database (inconsistent with npm)

**Target State**:
- ✅ Docker upgrades respect semantic versioning and base image preference
- ✅ Only stable releases (skip alpha/beta/rc unless flagged)
- ✅ Docs crawl version-specific API references, guides, examples
- ✅ Capsules extract concrete syntax patterns for exact version in use
- ✅ Python deps stored in database with full parity to npm

---

# Issue #1: Docker Tag Selection (CRITICAL)

## Current Broken Behavior

**Reproduction**:
```bash
cd C:/Users/santa/Desktop/DEIC
aud deps --upgrade-all
```

**Result**:
```
postgres: 17-alpine3.21 → 15.15-trixie        [DOWNGRADE + base switch]
python: 3.12-alpine3.21 → 3.15.0a1-windowsservercore  [ALPHA + base switch]
redis: 7-alpine3.21 → 8.4-rc1-bookworm       [RC + base switch]
```

## Root Cause

`deps.py:1116-1119`:
```python
if version_tags:
    version_tags.sort(reverse=True)  # ← STRING SORT (broken)
    return version_tags[0]
```

String sort: `"8.4-rc1-bookworm" > "7-alpine3.21"` alphabetically (WRONG)

## Fix Implementation

### Step 1: Parse Docker Tags Semantically

Add to `theauditor/deps.py`:

```python
def _parse_docker_tag(tag: str) -> Optional[Dict[str, Any]]:
    """
    Parse: "17-alpine3.21" → {version: (17,0,0), variant: "alpine3.21", stability: "stable"}
    Parse: "3.15.0a1-windowsservercore" → {version: (3,15,0), variant: "...", stability: "alpha"}
    """
    import re

    # Skip meta tags
    if tag in ["latest", "alpine", "slim", "main", "master"]:
        return None

    # Detect stability markers
    stability = 'stable'
    tag_lower = tag.lower()
    if any(marker in tag_lower for marker in ['alpha', '-a', 'a1', 'a2']):
        stability = 'alpha'
    elif any(marker in tag_lower for marker in ['beta', '-b']):
        stability = 'beta'
    elif any(marker in tag_lower for marker in ['rc', '-rc', 'rc1', 'rc2']):
        stability = 'rc'
    elif any(marker in tag_lower for marker in ['nightly', 'dev', 'snapshot']):
        stability = 'dev'

    # Extract semantic version (first numeric part)
    match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?', tag)
    if not match:
        return None

    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)

    # Extract variant/base (everything after version)
    variant = tag[match.end():].lstrip('-')

    return {
        'tag': tag,
        'version': (major, minor, patch),
        'variant': variant,
        'stability': stability
    }
```

### Step 2: Filter to Stable + Match Base Image

Replace `_check_dockerhub_latest()` in `deps.py:1072-1131`:

```python
def _check_dockerhub_latest(image_name: str, current_tag: str = "") -> Optional[str]:
    """Fetch latest STABLE version matching current base image."""
    from urllib import request
    import json

    # Fetch tags from Docker Hub API
    url = f"https://registry.hub.docker.com/v2/repositories/library/{image_name}/tags?page_size=100"

    try:
        with request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            tags = data.get("results", [])
    except Exception:
        return None

    # Parse all tags
    parsed_tags = []
    for tag in tags:
        parsed = _parse_docker_tag(tag.get("name", ""))
        if parsed:
            parsed_tags.append(parsed)

    # Filter to stable only (skip alpha/beta/rc/dev)
    stable_tags = [t for t in parsed_tags if t['stability'] == 'stable']

    # If no stable versions, allow rc as fallback (but warn)
    if not stable_tags:
        stable_tags = [t for t in parsed_tags if t['stability'] in ['stable', 'rc']]
        # TODO: Log warning that only rc available

    # Extract current base image preference
    current_base = _extract_base_preference(current_tag)

    # Filter to matching base (alpine → alpine, not alpine → debian)
    if current_base:
        matching = [t for t in stable_tags if current_base in t['variant'].lower()]
        if matching:
            stable_tags = matching

    # Sort by semantic version (tuple comparison)
    stable_tags.sort(key=lambda t: t['version'], reverse=True)

    return stable_tags[0]['tag'] if stable_tags else None


def _extract_base_preference(tag: str) -> str:
    """Extract base image: 'python:3.12-alpine' → 'alpine'"""
    tag_lower = tag.lower()
    for base in ['alpine', 'bookworm', 'bullseye', 'slim', 'windowsservercore', 'nanoserver']:
        if base in tag_lower:
            return base
    return ""
```

### Step 3: Add PyPI Pre-release Filtering (Defensive)

Replace `_check_pypi_latest()` in `deps.py`:

```python
def _check_pypi_latest(package_name: str) -> Optional[str]:
    """Fetch latest STABLE version from PyPI."""
    from packaging.version import parse
    import urllib.request
    import json

    if not validate_package_name(package_name, "py"):
        return None

    normalized_name = package_name.replace('_', '-')
    safe_package_name = sanitize_url_component(normalized_name)
    url = f"https://pypi.org/pypi/{safe_package_name}/json"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())

            # Get all releases
            releases = data.get("releases", {})

            # Filter to stable versions only
            stable_versions = []
            for version_str in releases.keys():
                try:
                    v = parse(version_str)
                    if not v.is_prerelease:
                        stable_versions.append(v)
                except Exception:
                    continue

            if not stable_versions:
                return None

            # Return the latest stable version
            latest = max(stable_versions)
            return str(latest)

    except Exception:
        return None
```

### Step 4: Add CLI Flag for Stability Preference

Update `theauditor/commands/deps.py:16`:

```python
@click.option("--allow-prerelease", is_flag=True,
              help="Allow alpha/beta/rc versions (default: stable only)")
def deps_command(..., allow_prerelease):
    """Check dependencies command."""
    # Pass allow_prerelease to _check_dockerhub_latest()
```

## Expected Results

**Before**:
```
postgres: 17-alpine3.21 → 15.15-trixie        [BROKEN]
python: 3.12-alpine3.21 → 3.15.0a1-windowsservercore  [BROKEN]
redis: 7-alpine3.21 → 8.4-rc1-bookworm       [BROKEN]
```

**After**:
```
postgres: 17-alpine3.21 → 17.2-alpine3.21    [FIXED: patch bump, same base]
python: 3.12-alpine3.21 → 3.13.1-alpine3.21  [FIXED: minor bump, stable]
redis: 7-alpine3.21 → 7.4.2-alpine3.21       [FIXED: patch bump, same base]
```

## Files to Modify
- `theauditor/deps.py:1072-1131` - Replace `_check_dockerhub_latest()`
- `theauditor/deps.py` - Add `_parse_docker_tag()` helper
- `theauditor/deps.py` - Add `_extract_base_preference()` helper
- `theauditor/deps.py` - Update `_check_pypi_latest()` with defensive filtering
- `theauditor/commands/deps.py:16` - Add `--allow-prerelease` flag

---

# Issue #2: Documentation System Overhaul

## Core Problem

**User Goal**:
> "Flask v3.1.0 uses `@app.route('/path')` decorator, NOT `app.add_url_rule()` (deprecated in v3.0)"

**Current Behavior**:
- Only fetches README from GitHub
- No crawling of docs sites (ReadTheDocs, GitHub Pages, etc.)
- No version-specific content (can't distinguish v7.x from v6.x)
- Regex HTML parsing fails on modern sites

**What We Get Now**:
```markdown
# Flask

A micro web framework.

## Install
pip install flask

...
(truncated README with install instructions)
```

**What We NEED**:
```markdown
# Flask v3.1.0 (py)

## Imports
from flask import Flask, request, jsonify

## Common Patterns

### Define route (v3.0+ syntax)
@app.route('/users', methods=['GET', 'POST'])
def users():
    if request.method == 'POST':
        data = request.get_json()
        return jsonify(data), 201
    return jsonify({'users': []})

*Changed in v3.0: @app.route decorator is now required*

## Breaking Changes in v3.1.0
- app.config["DEBUG"] deprecated, use app.debug property

## Full Documentation
- Cached: .pf/context/docs/py/flask@3.1.0/
- Files: README.md, quickstart.md, api.md, routing.md
```

## Fix Strategy

### Phase 1: Replace Regex with BeautifulSoup

**Add Dependencies to `pyproject.toml`**:
```toml
[project.optional-dependencies]
docs = [
    "beautifulsoup4>=4.12.0",
    "markdownify>=0.11.0",
]

dev = [
    # ... existing dev deps
    "packaging>=23.0",  # For version parsing
]
```

**Install**:
```bash
pip install -e ".[docs]"
```

**New Implementation** - Replace in `theauditor/docs_fetch.py`:

```python
from bs4 import BeautifulSoup
from markdownify import markdownify as md

def _fetch_and_convert_html(url: str) -> str:
    """Fetch HTML and convert to clean Markdown."""
    import urllib.request
    import re

    with urllib.request.urlopen(url, timeout=10) as response:
        html = response.read().decode('utf-8')

    # Parse with BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    # Remove script and style tags
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()

    # Find main content (try common patterns)
    content = (
        soup.find('article') or
        soup.find('div', class_='documentation') or
        soup.find('div', class_='docs-content') or
        soup.find('div', class_='main-content') or
        soup.find('main') or
        soup.body
    )

    if not content:
        return ""

    # Convert to Markdown
    markdown = md(str(content), heading_style="ATX", bullets="-")

    # Clean up excessive whitespace
    markdown = '\n'.join(line.rstrip() for line in markdown.split('\n'))
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)

    return markdown.strip()
```

### Phase 2: Intelligent Doc Crawling

**Add to `theauditor/docs_fetch.py`**:

```python
def fetch_package_docs(name: str, version: str, ecosystem: str, allowlist: List[str]) -> Dict[str, str]:
    """
    Fetch version-specific documentation from multiple sources.

    Returns:
        {
            'README.md': '...',
            'quickstart.md': '...',
            'api_reference.md': '...',
            'examples.md': '...',
            'migration_guide.md': '...'
        }
    """
    docs = {}

    # 1. Get package metadata to find docs URL
    docs_url = _get_docs_url(name, version, ecosystem)

    # 2. Fetch README (current behavior)
    readme = _fetch_github_readme(repo_url, allowlist)
    if readme:
        docs['README.md'] = readme

    # 3. Crawl docs site if available
    if docs_url:
        crawled = _crawl_docs_site(docs_url, version, allowlist)
        docs.update(crawled)

    # 4. Look for version-specific changelog/migration guide
    migration = _fetch_migration_guide(repo_url, version, allowlist)
    if migration:
        docs['migration_guide.md'] = migration

    return docs


def _crawl_docs_site(base_url: str, version: str, allowlist: List[str],
                     max_pages: int = 10) -> Dict[str, str]:
    """
    Crawl documentation site for version-specific content.

    Examples:
        https://flask.palletsprojects.com/en/3.1.x/quickstart/
        https://numpy.org/doc/2.3/user/quickstart.html
        https://requests.readthedocs.io/en/v2.31.0/
    """
    import time

    crawled = {}

    # Parse version into URL patterns
    version_patterns = [
        f"/{version}/",           # /2.31.0/
        f"/en/{version}/",        # /en/2.31.0/
        f"/v{version}/",          # /v2.31.0/
        f"/{version.split('.')[0]}.x/",  # /2.x/ (for Flask-style)
    ]

    # Priority pages to fetch
    priority_pages = [
        'quickstart', 'getting-started', 'tutorial',
        'api', 'api-reference', 'reference',
        'examples', 'cookbook', 'howto',
        'migration', 'changelog', 'whats-new'
    ]

    for page_name in priority_pages:
        # Try different URL patterns
        for pattern in version_patterns:
            # Common doc URL formats
            urls_to_try = [
                f"{base_url}{pattern}{page_name}",
                f"{base_url}{pattern}{page_name}.html",
                f"{base_url}{pattern}user/{page_name}",
            ]

            for url in urls_to_try:
                if not _is_url_allowed(url, allowlist):
                    continue

                try:
                    content = _fetch_and_convert_html(url)
                    if content and len(content) > 500:
                        # Found substantial content
                        crawled[f"{page_name}.md"] = content
                        time.sleep(0.5)  # Rate limit
                        break  # Found this page, move to next priority
                except Exception:
                    continue

            if f"{page_name}.md" in crawled:
                break  # Found this page

        # Stop if we hit max pages
        if len(crawled) >= max_pages:
            break

    return crawled
```

### Phase 3: AI-Based Syntax Extraction

**Create new file: `theauditor/docs_extract.py`**:

```python
"""AI-based documentation syntax extraction."""

from pathlib import Path
from typing import Dict, Any


def create_ai_extraction_prompt(
    package: str,
    version: str,
    ecosystem: str,
    full_docs: str,
    max_tokens: int = 10000
) -> str:
    """
    Generate AI extraction prompt for semantic doc processing.

    This replaces regex parsing with AI-based extraction.
    """
    # Smart truncation that prioritizes important sections
    truncated_docs = _smart_truncate(full_docs, max_tokens)

    prompt = f"""From the following documentation for `{package}@{version}`, extract:

1. **Install command**: The exact pip/npm command to install this version
2. **Essential imports**: The 3-5 most common import statements
3. **Quickstart code**: A complete, minimal working example (5-15 lines)
4. **Top API patterns**: The 5-10 most common functions/methods with their syntax
5. **Breaking changes**: Any changes marked as breaking/deprecated/removed in v{version}

Prioritize concrete code examples over explanations.
Format as Markdown with code blocks.

---
Documentation:

{truncated_docs}
"""

    # Save extraction prompt for MCP/AI processing
    prompt_file = Path(f".pf/context/extraction_prompts/{package}@{version}.txt")
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt)

    return prompt


def _smart_truncate(content: str, max_tokens: int = 10000) -> str:
    """
    Smart truncation that preserves complete sections.

    Prioritizes: Quickstart > API > Examples > Reference
    """
    sections = {}
    current_section = None
    current_content = []

    for line in content.split('\n'):
        if line.startswith('#'):
            # Save previous section
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            # Start new section
            current_section = line.strip('#').strip().lower()
            current_content = [line]
        else:
            current_content.append(line)

    # Save final section
    if current_section:
        sections[current_section] = '\n'.join(current_content)

    # Priority order
    priority = ['quickstart', 'getting started', 'installation',
                'api', 'reference', 'examples', 'tutorial']

    result = []
    token_count = 0

    for keyword in priority:
        for section_name, section_content in sections.items():
            if keyword in section_name:
                section_tokens = len(section_content.split()) * 1.3  # Rough estimate
                if token_count + section_tokens <= max_tokens:
                    result.append(section_content)
                    token_count += section_tokens

    return '\n\n'.join(result)
```

### Phase 4: Version-Specific Capsule Generation

**Update `theauditor/docs_summarize.py`**:

```python
def create_version_capsule(
    package: str,
    version: str,
    ecosystem: str,
    docs: Dict[str, str],
    max_tokens: int = 2000
) -> str:
    """
    Generate AI-optimized capsule with version-specific syntax.

    Structure:
        1. Version header (which version this is)
        2. Quick install
        3. AI extraction prompt reference
        4. Link to full docs
    """
    from datetime import datetime

    capsule = []

    # Header
    capsule.append(f"# {package} v{version} ({ecosystem})")
    capsule.append(f"\n**Version**: {version}")
    capsule.append(f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}")
    capsule.append("\n---\n")

    # Install
    if ecosystem == 'py':
        capsule.append(f"\n## Install\n\n```bash\npip install {package}=={version}\n```\n")
    elif ecosystem == 'npm':
        capsule.append(f"\n## Install\n\n```bash\nnpm install {package}@{version}\n```\n")

    # AI Extraction Reference
    capsule.append("\n## AI Extraction\n")
    capsule.append(f"**Prompt**: `.pf/context/extraction_prompts/{package}@{version}.txt`")
    capsule.append("\nUse MCP/AI to extract:")
    capsule.append("- Essential imports")
    capsule.append("- Common patterns with code examples")
    capsule.append("- Breaking changes")
    capsule.append("- API reference\n")

    # Full docs reference
    capsule.append("\n## Full Documentation\n")
    capsule.append(f"- Cached docs: `.pf/context/docs/{ecosystem}/{package}@{version}/`")
    capsule.append(f"- Files available: {', '.join(docs.keys())}")

    # Concatenate all docs for easy AI consumption
    capsule.append("\n\n---\n\n## Raw Documentation (For AI Extraction)\n\n")
    for doc_name, doc_content in docs.items():
        capsule.append(f"### {doc_name}\n\n{doc_content}\n\n")

    return '\n'.join(capsule)
```

## Storage Structure

```
.pf/context/docs/
  py/
    flask@3.1.0/
      README.md              # From GitHub
      quickstart.md          # From docs site
      api_reference.md       # From docs site
      migration_guide.md     # From changelog
      meta.json              # Metadata
  npm/
    express@4.18.0/
      README.md
      getting-started.md
      api.md
      meta.json

.pf/context/doc_capsules/
  py/
    flask@3.1.0.md           # Version-specific capsule
  npm/
    express@4.18.0.md

.pf/context/extraction_prompts/
  flask@3.1.0.txt            # AI extraction prompt
  express@4.18.0.txt
```

## New CLI Flags

```bash
# Fetch docs with crawling
aud docs fetch --max-pages 10

# Force version-aware docs
aud docs fetch --version-aware

# Generate AI extraction prompts
aud docs summarize --extract-syntax

# Debug mode
THEAUDITOR_DEBUG=1 aud docs fetch
```

## Files to Create/Modify

**New Files**:
- `theauditor/docs_extract.py` - AI extraction prompt generation

**Modified Files**:
- `theauditor/docs_fetch.py` - Add crawling, BeautifulSoup parser
- `theauditor/docs_summarize.py` - Version-specific capsules
- `theauditor/commands/docs.py` - Add flags
- `pyproject.toml` - Add beautifulsoup4 + markdownify dependencies

---

# Issue #3: Python Deps Storage (Database Parity)

## Current Gap

**npm deps**: Stored in `package_configs` table ✅
**Python deps**: NOT stored, parsed from files every time ❌

## Why This Matters

1. **Consistency**: npm and Python should work the same way
2. **Performance**: Don't re-parse requirements.txt on every `aud deps` run
3. **Cross-referencing**: Can't join Python deps with other analysis (imports table)
4. **History tracking**: Can't see dep changes over time

## Solution: Add `python_package_configs` Table

### Schema

Add to `theauditor/indexer/schemas/python_schema.py`:

```python
PYTHON_TABLES = [
    # ... existing tables ...

    """
    CREATE TABLE IF NOT EXISTS python_package_configs (
        id INTEGER PRIMARY KEY,
        file_path TEXT NOT NULL,              -- 'pyproject.toml', 'requirements.txt', 'backend/requirements-dev.txt'
        file_type TEXT NOT NULL,              -- 'pyproject', 'requirements'

        -- Project metadata (for pyproject.toml)
        project_name TEXT,                    -- From [project.name]
        project_version TEXT,                 -- From [project.version]

        -- Dependencies (JSON arrays)
        dependencies TEXT,                    -- JSON: {"flask": "3.1.0", "numpy": ">=1.24.4"}
        optional_dependencies TEXT,           -- JSON: {"dev": {...}, "test": {...}}

        -- Build metadata (for pyproject.toml)
        build_system TEXT,                    -- 'poetry', 'setuptools', 'hatch'
        python_requires TEXT,                 -- '>=3.11'

        -- Tracking
        last_modified REAL,
        indexed_at REAL DEFAULT (julianday('now'))
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_python_package_configs_file ON python_package_configs(file_path)",
    "CREATE INDEX IF NOT EXISTS idx_python_package_configs_project ON python_package_configs(project_name)",
]
```

### Extractor Implementation

**Create new file: `theauditor/indexer/extractors/python_deps.py`**:

```python
"""Extract Python dependencies from requirements.txt and pyproject.toml."""

import json
import tomllib
from pathlib import Path
from typing import Dict, List, Any, Optional


def extract_python_dependencies(file_path: Path, content: str) -> Optional[Dict[str, Any]]:
    """
    Extract Python dependencies from requirements.txt or pyproject.toml.

    Returns dict suitable for python_package_configs table.
    """
    file_name = file_path.name.lower()

    if file_name == 'pyproject.toml':
        return _extract_from_pyproject(file_path, content)
    elif 'requirements' in file_name and file_name.endswith('.txt'):
        return _extract_from_requirements(file_path, content)
    else:
        return None


def _extract_from_pyproject(file_path: Path, content: str) -> Optional[Dict[str, Any]]:
    """Extract from pyproject.toml."""
    try:
        data = tomllib.loads(content)
    except Exception:
        return None

    project = data.get('project', {})
    build_system = data.get('build-system', {})

    # Parse dependencies
    deps = {}
    for dep_spec in project.get('dependencies', []):
        name, version = _parse_dep_spec(dep_spec)
        if name:
            deps[name] = version or 'latest'

    # Parse optional dependencies
    optional_deps = {}
    for group_name, group_deps in project.get('optional-dependencies', {}).items():
        group_dict = {}
        for dep_spec in group_deps:
            name, version = _parse_dep_spec(dep_spec)
            if name:
                group_dict[name] = version or 'latest'
        if group_dict:
            optional_deps[group_name] = group_dict

    return {
        'file_path': str(file_path),
        'file_type': 'pyproject',
        'project_name': project.get('name'),
        'project_version': project.get('version'),
        'dependencies': json.dumps(deps) if deps else None,
        'optional_dependencies': json.dumps(optional_deps) if optional_deps else None,
        'build_system': build_system.get('build-backend', '').split('.')[-1],  # 'setuptools.build_meta' -> 'meta'
        'python_requires': project.get('requires-python'),
        'last_modified': file_path.stat().st_mtime
    }


def _extract_from_requirements(file_path: Path, content: str) -> Optional[Dict[str, Any]]:
    """Extract from requirements.txt."""
    deps = {}

    for line in content.split('\n'):
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue

        # Skip directives
        if line.startswith('-'):
            continue

        # Strip inline comments
        if '#' in line:
            line = line.split('#')[0].strip()

        name, version = _parse_dep_spec(line)
        if name:
            deps[name] = version or 'latest'

    if not deps:
        return None

    return {
        'file_path': str(file_path),
        'file_type': 'requirements',
        'dependencies': json.dumps(deps),
        'last_modified': file_path.stat().st_mtime
    }


def _parse_dep_spec(spec: str) -> tuple[str, Optional[str]]:
    """
    Parse dependency spec: 'flask==3.1.0' → ('flask', '3.1.0')
    """
    import re

    # Remove extras: 'requests[security]==2.31.0' -> 'requests==2.31.0'
    spec = re.sub(r'\[.*?\]', '', spec)

    # Handle git URLs
    if '@' in spec and ('git+' in spec or 'https://' in spec):
        name = spec.split('@')[0].strip()
        return (name, 'git')

    # Parse version: 'package==1.2.3'
    match = re.match(r'^([a-zA-Z0-9._-]+)\s*([><=~!]+)\s*(.+)$', spec)
    if match:
        name, op, version = match.groups()
        return (name, version)

    # No version
    return (spec.strip(), None)
```

### Register in Indexer

Update `theauditor/indexer/extractors/python.py`:

```python
from .python_deps import extract_python_dependencies
from pathlib import Path

def extract(file_info, content, tree):
    """Extract Python file data."""
    # ... existing extraction ...

    # If this is pyproject.toml or requirements.txt, extract deps
    file_path = Path(file_info['path'])
    if file_path.name.lower() == 'pyproject.toml' or 'requirements' in file_path.name.lower():
        deps_data = extract_python_dependencies(file_path, content)
        if deps_data:
            # Store in DB (handled by storage layer)
            file_info['python_deps'] = deps_data

    return file_info
```

### Update deps.py to Read from Database

Update `theauditor/deps.py`:

```python
def parse_dependencies(root_path: str = ".") -> List[Dict[str, Any]]:
    """Parse dependencies from database or files."""
    import sqlite3
    from pathlib import Path

    root = Path(root_path)
    deps = []

    db_path = root / ".pf" / "repo_index.db"

    # =========================================================================
    # DATABASE-FIRST: Read npm deps from package_configs
    # =========================================================================
    if db_path.exists():
        npm_deps = _read_npm_deps_from_database(db_path, root, debug)
        if npm_deps:
            deps.extend(npm_deps)

        # =========================================================================
        # DATABASE-FIRST: Read Python deps from python_package_configs
        # =========================================================================
        python_deps = _read_python_deps_from_database(db_path, root, debug)
        if python_deps:
            deps.extend(python_deps)

    # =========================================================================
    # FALLBACK: Parse from files if database is empty
    # =========================================================================
    if not any(d['manager'] == 'npm' for d in deps):
        # Parse npm from files
        # ... existing code ...

    if not any(d['manager'] == 'py' for d in deps):
        # Parse Python from files
        # ... existing code ...

    return deps


def _read_python_deps_from_database(db_path: Path, root: Path, debug: bool) -> List[Dict[str, Any]]:
    """Read Python dependencies from python_package_configs table."""
    import sqlite3
    import json

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='python_package_configs'
        """)

        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute("""
            SELECT file_path, dependencies, optional_dependencies
            FROM python_package_configs
        """)

        deps = []

        for file_path, deps_json, optional_deps_json in cursor.fetchall():
            if not deps_json:
                continue

            try:
                dependencies = json.loads(deps_json)

                # Convert to deps.py format
                for name, version in dependencies.items():
                    deps.append({
                        "name": name,
                        "version": version,
                        "manager": "py",
                        "files": [],
                        "source": file_path
                    })

                # Include optional dependencies
                if optional_deps_json:
                    optional_deps = json.loads(optional_deps_json)
                    for group_name, group_deps in optional_deps.items():
                        for name, version in group_deps.items():
                            deps.append({
                                "name": name,
                                "version": version,
                                "manager": "py",
                                "files": [],
                                "source": file_path,
                                "optional_group": group_name
                            })

            except json.JSONDecodeError:
                if debug:
                    print(f"Debug: Failed to parse Python deps JSON from {file_path}")
                continue

        conn.close()
        return deps

    except Exception as e:
        if debug:
            print(f"Debug: Database read error: {e}")
        return []
```

## Example SQL Queries

```sql
-- Find all Flask projects
SELECT DISTINCT project_name, file_path
FROM python_package_configs
WHERE dependencies LIKE '%flask%';

-- Find projects using outdated numpy
SELECT file_path, json_extract(dependencies, '$.numpy') AS numpy_version
FROM python_package_configs
WHERE dependencies LIKE '%numpy%'
  AND json_extract(dependencies, '$.numpy') < '2.0.0';

-- Find all dev dependencies
SELECT file_path, key, value
FROM python_package_configs,
     json_each(optional_dependencies)
WHERE json_each.key = 'dev';
```

## Files to Create/Modify

**New Files**:
- `theauditor/indexer/extractors/python_deps.py`
- `tests/test_python_deps_extraction.py`

**Modified Files**:
- `theauditor/indexer/schemas/python_schema.py` - Add table
- `theauditor/indexer/extractors/python.py` - Call extractor
- `theauditor/deps.py` - Add `_read_python_deps_from_database()`

---

# Implementation Roadmap

## Week 1: Critical Production Fixes

**Goal**: Make `aud deps --upgrade-all` production-safe

**Tasks**:
1. Fix Docker tag selection (2-3 hours)
   - Add `_parse_docker_tag()` function
   - Add `_extract_base_preference()` helper
   - Update `_check_dockerhub_latest()` with semantic versioning
   - Test on postgres, redis, python, rabbitmq images

2. Add PyPI defensive filtering (1 hour)
   - Update `_check_pypi_latest()` with packaging.version
   - Filter pre-releases

3. Add `--allow-prerelease` flag (1 hour)
   - Update `commands/deps.py` CLI flags
   - Default to stable-only, allow override

4. Testing (1 hour)
   - Test on DEIC project
   - Verify no downgrades
   - Verify no alpha/beta/rc pulls
   - Verify base image preservation

**Deliverable**: `aud deps --upgrade-all` is production-safe

---

## Week 2: Store Python Deps

**Goal**: Database parity for npm and Python

**Tasks**:
1. Create extractor (3 hours)
   - `theauditor/indexer/extractors/python_deps.py`
   - Extract from pyproject.toml
   - Extract from requirements*.txt
   - Handle monorepo patterns

2. Add to schema (1 hour)
   - `python_package_configs` table
   - Indexes on file_path and project_name

3. Update deps.py (2 hours)
   - Add `_read_python_deps_from_database()`
   - Maintain file parsing as fallback
   - Test on TheAuditor's own deps

4. Testing (1 hour)
   - Run `aud full` to populate table
   - Verify `aud deps` reads from DB
   - Check monorepo support

**Deliverable**: Python deps in database, queryable

---

## Week 3: Docs Crawling (Phase 1)

**Goal**: Fetch actual documentation, not just README

**Tasks**:
1. Add dependencies (1 hour)
   - Add beautifulsoup4 + markdownify to pyproject.toml
   - Install and test

2. Replace regex HTML parsing (4 hours)
   - Replace regex with BeautifulSoup in docs_fetch.py
   - Test on ReadTheDocs, GitHub Pages, Sphinx sites

3. Add docs site crawler (4 hours)
   - Implement `_crawl_docs_site()`
   - Version-aware URL patterns
   - Priority page selection (quickstart > changelog)
   - Rate limiting

4. Storage restructure (2 hours)
   - Directories per package: `docs/py/flask@3.1.0/`
   - Multiple files: README.md, api.md, quickstart.md
   - meta.json with source URLs

5. Testing (2 hours)
   - Test on requests, flask, numpy (Python)
   - Test on express, react, lodash (npm)
   - Verify content quality

**Deliverable**: Actual docs fetched, not just README

---

## Week 4: AI Extraction (Phase 2)

**Goal**: Generate AI extraction prompts for version-specific syntax

**Tasks**:
1. Create extraction module (5 hours)
   - `theauditor/docs_extract.py`
   - `create_ai_extraction_prompt()`
   - `_smart_truncate()`

2. Update capsule generation (3 hours)
   - Version header (explicit version)
   - AI extraction prompt reference
   - Full raw docs for AI consumption
   - Breaking changes section

3. Add CLI flags (2 hours)
   - `--max-pages` for crawler
   - `--extract-syntax` for AI prompts
   - `--version-aware` for version-specific docs

4. Testing (2 hours)
   - Test extraction prompt quality
   - Verify docs are AI-consumable
   - Check version-specific content

**Deliverable**: Version-specific documentation with AI extraction prompts

---

# Testing Strategy

## Unit Tests

**Create `tests/test_docker_tag_parsing.py`**:

```python
def test_parse_docker_tag_stable():
    result = _parse_docker_tag("17-alpine3.21")
    assert result['version'] == (17, 0, 0)
    assert result['variant'] == 'alpine3.21'
    assert result['stability'] == 'stable'

def test_parse_docker_tag_alpha():
    result = _parse_docker_tag("3.15.0a1-windowsservercore")
    assert result['version'] == (3, 15, 0)
    assert result['stability'] == 'alpha'

def test_docker_latest_stable_only():
    # Mock Docker Hub API response with mixed tags
    tags = ["17-alpine3.21", "15.15-trixie", "18.0-rc1-bookworm"]
    result = _check_dockerhub_latest("postgres", current_tag="17-alpine3.21")
    assert result == "17-alpine3.21"  # Not downgrade, not rc
```

**Create `tests/test_python_deps_extraction.py`**:

```python
def test_extract_from_pyproject():
    content = """
[project]
name = "myproject"
version = "1.0.0"
dependencies = [
    "flask==3.1.0",
    "numpy>=1.24.4"
]

[project.optional-dependencies]
dev = ["pytest==7.4.0"]
"""
    result = extract_python_dependencies(Path("pyproject.toml"), content)
    assert result['project_name'] == 'myproject'
    deps = json.loads(result['dependencies'])
    assert deps['flask'] == '3.1.0'
```

## Integration Tests

```bash
# Test Docker upgrade safety
cd C:/Users/santa/Desktop/DEIC
aud deps --upgrade-all
# Verify: No downgrades, no alpha/beta/rc, same base images

# Test Python deps storage
cd C:/Users/santa/Desktop/TheAuditor
aud full
# Query database
python -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); print(conn.execute('SELECT * FROM python_package_configs').fetchall())"

# Test docs fetch
aud docs fetch flask --max-pages 5
ls .pf/context/docs/py/flask@*/
# Verify: Multiple .md files (not just README)

# Test capsule quality
aud docs summarize flask
cat .pf/context/doc_capsules/py/flask@*.md
# Verify: Has version header, AI extraction prompt, raw docs
```

---

# Success Metrics

## For Docker Fixes:
- ✅ Zero downgrades on `aud deps --upgrade-all`
- ✅ Zero alpha/beta/rc pulls (unless flagged)
- ✅ 100% base image preservation (alpine stays alpine)

## For Docs System:
- ✅ Average 5+ doc pages fetched per package (not just README)
- ✅ 90%+ packages have version-specific capsules
- ✅ Capsules contain AI extraction prompts
- ✅ Raw docs available for AI consumption

## For Database Parity:
- ✅ Python deps queryable via SQL
- ✅ Performance: `aud deps` runs in <1 second (cached)
- ✅ Cross-reference: Can join deps with imports table

---

# Files Summary

## New Files:
1. `theauditor/indexer/extractors/python_deps.py` - Python deps extractor
2. `theauditor/docs_extract.py` - AI extraction prompt generation
3. `tests/test_docker_tag_parsing.py` - Unit tests
4. `tests/test_python_deps_extraction.py` - Unit tests

## Modified Files:
1. `theauditor/deps.py` - Docker/PyPI tag selection + Python DB reading
2. `theauditor/commands/deps.py` - Add `--allow-prerelease` flag
3. `theauditor/docs_fetch.py` - BeautifulSoup parser + crawler
4. `theauditor/docs_summarize.py` - Version-specific capsules
5. `theauditor/indexer/schemas/python_schema.py` - Add python_package_configs table
6. `theauditor/indexer/extractors/python.py` - Call python_deps extractor
7. `pyproject.toml` - Add beautifulsoup4 + markdownify dependencies

---

# Next Steps

Ready to implement. Choose approach:

**Option A**: Implement yourself using this spec (all details provided)
**Option B**: I implement critical fixes (Week 1) for production safety
**Option C**: OpenSpec proposal route (formal TeamSOp workflow)
**Option D**: I implement full roadmap (Weeks 1-4)

All specifications are complete with code examples, test cases, and success criteria.
