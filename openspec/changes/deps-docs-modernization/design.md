# Technical Design: Deps & Docs Modernization

**Change ID**: `deps-docs-modernization`
**Architecture Type**: Incremental Enhancement (Non-Breaking)
**Design Philosophy**: Fix Production Bugs First, Then Enhance

---

## Design Principles

### Core Tenets (Per CLAUDE.md)

1. **ZERO FALLBACK POLICY**: No fallback logic. Fix the root cause.
2. **Hard Failures**: If something's wrong, crash loudly (no silent degradation)
3. **Database First**: Read from DB when available, parse files only as last resort
4. **Semantic Understanding**: Use proper parsers (BeautifulSoup), not regex
5. **Production Safety**: Week 1 fixes MUST be rock solid

### Non-Negotiables

- **NO BREAKING CHANGES**: All changes backward compatible
- **NO MIGRATIONS**: Database changes are additive only
- **NO REGEX FOR HTML**: BeautifulSoup or death
- **NO STRING SORTS**: Semantic version comparison only

---

## Component Architecture

### 1. Docker Tag Selection (Week 1)

#### Current Architecture (BROKEN)
```
Docker Hub API → Tag List → String Sort → First Item → Update
                              ↑
                              BUG: "8" > "1" alphabetically
```

#### New Architecture (FIXED)
```
Docker Hub API → Tag List → Parse Tags → Filter Stable → Match Base → Semantic Sort → Update
                              ↓              ↓              ↓              ↓
                          version tuple   skip alpha   alpine→alpine  (17,0,0) > (15,0,0)
```

#### Key Components

**Tag Parser State Machine**:
```python
Input: "17.2-alpine3.21"
       ↓
Parse Version: (17, 2, 0)
       ↓
Extract Variant: "alpine3.21"
       ↓
Detect Stability: "stable"
       ↓
Output: {
    'tag': '17.2-alpine3.21',
    'version': (17, 2, 0),
    'variant': 'alpine3.21',
    'stability': 'stable'
}
```

**Stability Detection Patterns**:
- Alpha: ['alpha', '-a', 'a1', 'a2']
- Beta: ['beta', '-b', 'b1', 'b2']
- RC: ['rc', '-rc', 'rc1', 'rc2']
- Dev: ['nightly', 'dev', 'snapshot', 'edge']

**Base Image Taxonomy**:
```
Linux Lightweight: ['alpine', 'slim', 'distroless']
Linux Standard: ['bookworm', 'bullseye', 'jammy', 'focal']
Windows: ['windowsservercore', 'nanoserver']
Generic: ['latest', 'stable']
```

#### Algorithm: Semantic Version Selection

```python
def select_best_tag(tags, current_tag, allow_prerelease=False):
    # 1. Parse all tags
    parsed = [parse_tag(t) for t in tags]
    parsed = [p for p in parsed if p]  # Remove None

    # 2. Filter by stability
    if not allow_prerelease:
        stable = [t for t in parsed if t['stability'] == 'stable']
        if not stable:
            # Fallback to RC with warning
            stable = [t for t in parsed if t['stability'] in ['stable', 'rc']]
            logger.warning("Only RC versions available")
        parsed = stable

    # 3. Match base image
    current_base = extract_base(current_tag)
    if current_base:
        matching = [t for t in parsed if current_base in t['variant']]
        if matching:
            parsed = matching

    # 4. Semantic sort
    parsed.sort(key=lambda x: x['version'], reverse=True)

    # 5. Return best or None
    return parsed[0]['tag'] if parsed else None
```

### 2. Python Dependencies Storage (Week 2)

#### Current Architecture (INCONSISTENT)
```
npm:    package.json → Indexer → package_configs table → deps.py reads DB
Python: requirements.txt → [NO STORAGE] → deps.py parses file EVERY TIME
```

#### New Architecture (CONSISTENT)
```
npm:    package.json → Indexer → package_configs table → deps.py reads DB
Python: requirements.txt → Indexer → python_package_configs table → deps.py reads DB
```

#### Database Schema Design

**Table: python_package_configs**
```sql
CREATE TABLE python_package_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- File identification
    file_path TEXT NOT NULL,        -- 'pyproject.toml', 'backend/requirements.txt'
    file_type TEXT NOT NULL,        -- 'pyproject' | 'requirements'

    -- Project metadata (nullable for requirements.txt)
    project_name TEXT,               -- [project.name] from pyproject
    project_version TEXT,            -- [project.version]

    -- Dependencies (JSON for flexibility)
    dependencies TEXT,               -- {"flask": "3.1.0", "numpy": ">=1.24"}
    optional_dependencies TEXT,      -- {"dev": {...}, "test": {...}}

    -- Build info (pyproject only)
    build_system TEXT,              -- 'poetry' | 'setuptools' | 'hatch'
    python_requires TEXT,           -- '>=3.11'

    -- Tracking
    last_modified REAL,             -- File mtime for cache invalidation
    indexed_at REAL DEFAULT (julianday('now'))
);

-- Indexes for fast lookups
CREATE INDEX idx_python_package_configs_file ON python_package_configs(file_path);
CREATE INDEX idx_python_package_configs_project ON python_package_configs(project_name);
```

**Why JSON for dependencies?**
- Flexible version specifiers (==, >=, ~=, git URLs)
- Optional dependencies with groups
- No need for complex relational schema
- SQLite JSON functions for queries

#### Extraction Pipeline

```
File System → Extractor → Storage → Database
     ↓            ↓          ↓          ↓
requirements.txt  parse   validate   INSERT

Extractor Logic:
1. Detect file type (pyproject.toml vs requirements.txt)
2. Parse with appropriate parser (tomllib vs line parser)
3. Normalize dependency specs
4. Convert to JSON
5. Return storage-ready dict
```

**Dependency Spec Normalization**:
```python
Input: "flask>=3.0,<4.0"
Parse: name="flask", version=">=3.0,<4.0"

Input: "git+https://github.com/user/repo.git@v1.0"
Parse: name="repo", version="git:v1.0"

Input: "requests[security]==2.31.0"
Parse: name="requests", version="2.31.0", extras=["security"]
```

### 3. Documentation System (Weeks 3-4)

#### Current Architecture (INADEQUATE)
```
GitHub README → Regex HTML Parser → Truncate 50 lines → Capsule
                       ↓
                   BREAKS on modern HTML
```

#### New Architecture (COMPREHENSIVE)
```
Multiple Sources → BeautifulSoup Parser → Smart Crawler → AI Extraction
        ↓                  ↓                   ↓              ↓
   GitHub README    Handles any HTML    Version URLs    Semantic patterns
   Docs Site
   Migration Guide
```

#### HTML Parsing Architecture

**BeautifulSoup Pipeline**:
```python
HTML Input
    ↓
BeautifulSoup Parse (fault-tolerant)
    ↓
Remove Noise (script, style, nav, footer)
    ↓
Find Content (article, main, div.docs-content)
    ↓
Markdownify (preserves code blocks, tables, lists)
    ↓
Clean Output (normalize whitespace)
```

**Why BeautifulSoup Over Regex**:
1. **Nested Tags**: `<div><p><code>text</code></p></div>` handled correctly
2. **Broken HTML**: Missing closing tags auto-fixed
3. **Entities**: `&lt;` → `<` decoded properly
4. **Attributes**: Extracts href, src, alt correctly
5. **3 lines vs 100+**: Maintainable code

#### Crawling Strategy

**URL Pattern Detection**:
```python
# Version-specific patterns to try
patterns = [
    "/en/{version}/",     # Flask: /en/3.1.x/
    "/v{version}/",       # Requests: /v2.31.0/
    "/{version}/",        # Direct version
    "/docs/stable/",      # Latest stable
    "/{major}.x/",        # Major version only
]

# Page priority (most valuable first)
priority = [
    'quickstart',         # How to use
    'api-reference',      # Function signatures
    'examples',           # Code samples
    'migration',          # Breaking changes
    'configuration',      # Settings
    'changelog',          # Version history
]
```

**Rate Limiting & Politeness**:
```python
CRAWL_DELAY = 0.5  # seconds between requests
MAX_PAGES = 10     # default limit
TIMEOUT = 10       # seconds per request

# Respect robots.txt implicitly via allowlist
if not _is_url_allowed(url, allowlist):
    skip()
```

#### Storage Structure

**File Organization**:
```
.pf/context/
├── docs/
│   ├── py/
│   │   └── flask@3.1.0/
│   │       ├── README.md          # GitHub README
│   │       ├── quickstart.md      # From docs site
│   │       ├── api_reference.md   # API docs
│   │       ├── migration.md       # Breaking changes
│   │       └── meta.json          # Metadata
│   └── npm/
│       └── express@4.18.0/
│           └── ...
├── doc_capsules/
│   ├── py/
│   │   └── flask@3.1.0.md        # AI-optimized capsule
│   └── npm/
│       └── express@4.18.0.md
└── extraction_prompts/
    ├── flask@3.1.0.txt            # For AI/MCP processing
    └── express@4.18.0.txt
```

**meta.json Structure**:
```json
{
    "package": "flask",
    "version": "3.1.0",
    "ecosystem": "py",
    "fetched_at": "2025-01-16T10:30:00Z",
    "sources": {
        "README.md": "https://github.com/pallets/flask",
        "quickstart.md": "https://flask.palletsprojects.com/en/3.1.x/quickstart/",
        "api_reference.md": "https://flask.palletsprojects.com/en/3.1.x/api/"
    },
    "file_count": 4,
    "total_size": 45678
}
```

### 4. AI Extraction Architecture (Week 4)

#### Extraction Pipeline
```
Raw Docs → Smart Truncation → Prompt Generation → AI Processing → Pattern Extraction
    ↓            ↓                    ↓                ↓              ↓
  All .md    Keep valuable      Structure request   MCP/LLM     Code patterns
   files       sections             template                    Breaking changes
```

#### Smart Truncation Algorithm

**Section Priority Scoring**:
```python
SECTION_PRIORITIES = {
    'quickstart': 100,
    'getting started': 95,
    'installation': 90,
    'basic usage': 85,
    'api reference': 80,
    'api': 75,
    'examples': 70,
    'cookbook': 65,
    'advanced': 50,
    'contributing': 20,
    'license': 10
}

def smart_truncate(content, max_tokens=10000):
    sections = parse_sections(content)

    # Score each section
    scored = []
    for name, text in sections.items():
        score = max(
            SECTION_PRIORITIES.get(keyword, 0)
            for keyword in SECTION_PRIORITIES
            if keyword in name.lower()
        )
        scored.append((score, name, text))

    # Sort by priority
    scored.sort(reverse=True, key=lambda x: x[0])

    # Include until token limit
    result = []
    tokens = 0
    for score, name, text in scored:
        estimated = len(text.split()) * 1.3  # Rough token estimate
        if tokens + estimated <= max_tokens:
            result.append(f"## {name}\n\n{text}")
            tokens += estimated

    return '\n\n'.join(result)
```

#### Prompt Engineering

**Extraction Prompt Template**:
```python
EXTRACTION_TEMPLATE = """
You are analyzing documentation for {package} version {version}.

From the documentation below, extract the following information:

1. **Install Command**: The exact command to install this specific version
   Example: pip install flask==3.1.0

2. **Essential Imports**: The 3-5 most commonly used import statements
   Example: from flask import Flask, request, jsonify

3. **Quickstart Code**: A complete, minimal working example (5-15 lines)
   Must be runnable code, not fragments

4. **Common API Patterns**: The 5-10 most frequently used functions/methods
   Include their signatures and brief usage

5. **Breaking Changes**: Any changes marked as breaking, deprecated, or removed in v{version}
   Look for migration guides, changelog entries, deprecation warnings

Prioritize concrete code examples over explanations.
Format your response as Markdown with clear headers.

---
DOCUMENTATION:

{truncated_docs}
---

Extract the requested information:
"""
```

---

## Error Handling Strategy

### Production Safety (Week 1)

**Docker Hub API Failures**:
```python
try:
    response = urlopen(docker_hub_url, timeout=10)
except (URLError, TimeoutError) as e:
    logger.warning(f"Docker Hub unreachable: {e}")
    return None  # Keep current version

# NEVER fall back to wrong version
# Better to stay on current than downgrade
```

**PyPI API Failures**:
```python
try:
    response = urlopen(pypi_url, timeout=10)
except Exception as e:
    logger.warning(f"PyPI unreachable: {e}")
    return None  # Keep current version

# NEVER return pre-release without explicit flag
```

### Database Operations (Week 2)

**Missing Table Handling**:
```python
# Check table exists (one time)
cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='python_package_configs'"
)
if not cursor.fetchone():
    # Table doesn't exist - use file parsing
    return _parse_from_files()

# Table exists - query it
# NO FALLBACK within same function
```

### Documentation Fetching (Week 3)

**Network Failures**:
```python
for url in urls_to_try:
    try:
        content = fetch_url(url, timeout=10)
        if content and len(content) > 500:
            return content
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {e}")
        continue  # Try next URL

# All failed - that's OK, some packages have no docs
return {}  # Empty docs, not an error
```

---

## Performance Considerations

### Database Query Performance

**Indexed Columns**:
- file_path: O(log n) lookup for file changes
- project_name: O(log n) for cross-project queries

**JSON Query Performance**:
```sql
-- SQLite JSON functions are optimized
SELECT json_extract(dependencies, '$.flask') as flask_version
FROM python_package_configs
WHERE dependencies LIKE '%flask%';  -- Uses index

-- Avoid full table scans
-- Bad: WHERE json_extract(dependencies, '$.flask') IS NOT NULL
-- Good: WHERE dependencies LIKE '%flask%' (can use index)
```

### Network I/O Optimization

**Parallel Fetching** (Future Enhancement):
```python
# Current: Sequential
for package in packages:
    fetch_docs(package)

# Future: Parallel with asyncio
async def fetch_all(packages):
    tasks = [fetch_docs_async(p) for p in packages]
    return await asyncio.gather(*tasks)
```

**Caching Strategy**:
- Cache docs for 7 days (version-specific, won't change)
- Cache Docker tags for 1 hour (may have new releases)
- Cache PyPI versions for 1 hour

### Memory Management

**Smart Truncation Prevents OOM**:
```python
MAX_DOC_SIZE = 10_000_000  # 10MB per doc file
MAX_TOTAL_SIZE = 50_000_000  # 50MB total per package

# Truncate individual files
if len(content) > MAX_DOC_SIZE:
    content = content[:MAX_DOC_SIZE]
    logger.warning(f"Truncated {url} to 10MB")

# Stop crawling if total too large
if total_size > MAX_TOTAL_SIZE:
    break
```

---

## Testing Strategy

### Unit Tests (Required)

**Docker Tag Parser Tests**:
```python
def test_parse_docker_tag():
    assert _parse_docker_tag("17-alpine3.21") == {
        'tag': '17-alpine3.21',
        'version': (17, 0, 0),
        'variant': 'alpine3.21',
        'stability': 'stable'
    }

def test_detect_prerelease():
    assert _parse_docker_tag("3.15.0a1-windows")['stability'] == 'alpha'
    assert _parse_docker_tag("8.0-rc1")['stability'] == 'rc'
```

**Dependency Parser Tests**:
```python
def test_parse_requirements():
    content = """
    flask==3.1.0
    numpy>=1.24.4
    requests[security]==2.31.0  # with extras
    """
    result = extract_python_dependencies(Path("requirements.txt"), content)
    deps = json.loads(result['dependencies'])
    assert deps['flask'] == '3.1.0'
    assert deps['numpy'] == '>=1.24.4'
    assert deps['requests'] == '2.31.0'
```

### Integration Tests (Critical)

**Production Project Test (DEIC)**:
```bash
# Must pass before release
cd C:/Users/santa/Desktop/DEIC
aud deps --upgrade-all

# Assertions:
# - No downgrades (version only goes up)
# - No pre-releases (unless --allow-prerelease)
# - Same base image (alpine stays alpine)
```

**Database Population Test**:
```bash
aud full
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM python_package_configs"
# Should return > 0
```

---

## Migration & Rollback

### Migration Plan: NONE REQUIRED

All changes are **additive** and **backward compatible**:

1. **New functions**: Don't affect existing code paths
2. **New table**: Ignored by old code
3. **New dependencies**: Optional group [docs]
4. **New flags**: Have sensible defaults

### Rollback Procedure (If Needed)

**Week 1 Rollback**:
```python
# Comment out new functions
# Uncomment old _check_dockerhub_latest
# Remove --allow-prerelease flag
```

**Week 2 Rollback**:
```sql
-- Just don't query the table
-- Or: DROP TABLE python_package_configs;
```

**Week 3-4 Rollback**:
```bash
# Remove beautifulsoup4, markdownify from pyproject.toml
pip uninstall beautifulsoup4 markdownify
# Use old regex code (kept commented)
```

---

## Security Considerations

### Input Validation

**Package Name Validation**:
```python
def validate_package_name(name: str, ecosystem: str) -> bool:
    # Prevent directory traversal
    if '..' in name or '/' in name or '\\' in name:
        return False

    # Alphanumeric + dash/underscore only
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return False

    return True
```

**URL Validation**:
```python
def sanitize_url_component(component: str) -> str:
    # URL encode to prevent injection
    return urllib.parse.quote(component, safe='')
```

### Dependency Security

**Never Auto-Install**:
- Only check versions, never run `pip install` automatically
- User must explicitly approve updates

**Verification**:
```python
# Always verify package exists on PyPI/npm
# Never trust user input directly
response = urlopen(f"https://pypi.org/pypi/{sanitized_name}/json")
if response.status != 200:
    raise ValueError(f"Package {name} not found on PyPI")
```

---

## Future Enhancements (Not In Scope)

### Parallel Processing
- Async/await for network operations
- ThreadPoolExecutor for CPU-bound parsing

### Advanced Caching
- Redis/memcached for distributed cache
- Incremental crawling (only new pages)

### AI Integration
- Direct MCP integration for extraction
- Local LLM for offline processing
- Fine-tuned model for code extraction

### Version Pinning
- Lock file generation (like poetry.lock)
- Reproducible builds
- Security audit integration

---

## Design Decision Log

**Decision 1**: Use JSON for dependencies storage
- **Alternatives**: Normalized tables, separate version column
- **Choice**: JSON TEXT column
- **Rationale**: Flexible for complex version specs, SQLite has JSON support

**Decision 2**: BeautifulSoup over regex
- **Alternatives**: Regex, lxml, html.parser
- **Choice**: BeautifulSoup4
- **Rationale**: Most forgiving parser, handles broken HTML

**Decision 3**: Semantic versioning via tuples
- **Alternatives**: String comparison, version library
- **Choice**: Tuple comparison (17, 0, 0) > (15, 0, 0)
- **Rationale**: Simple, no extra dependencies, works for most cases

**Decision 4**: File-based prompt storage
- **Alternatives**: Database storage, direct API calls
- **Choice**: Save to .txt files
- **Rationale**: Allows manual review, future MCP integration, debugging

---

## Success Validation

### Acceptance Criteria

**Week 1 Success**:
```python
def validate_week1():
    # Test on DEIC project
    result = run_command("aud deps --upgrade-all")

    assert no_downgrades(result)
    assert no_prereleases(result)
    assert base_images_preserved(result)

    return "PASS"
```

**Week 2 Success**:
```python
def validate_week2():
    # Check database
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM python_package_configs")
    count = cursor.fetchone()[0]

    assert count > 0
    assert deps_command_time() < 1.0  # seconds

    return "PASS"
```

**Week 3-4 Success**:
```python
def validate_docs():
    # Check multi-file docs
    docs_path = Path(".pf/context/docs/py/flask@3.1.0/")

    assert docs_path.exists()
    assert len(list(docs_path.glob("*.md"))) >= 3
    assert (docs_path / "meta.json").exists()

    return "PASS"
```

---

**END OF DESIGN DOCUMENT**