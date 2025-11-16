# Implementation Tasks: Deps & Docs Modernization

**Change ID**: `deps-docs-modernization`
**Tracking**: 4-week phased implementation with validation gates
**Status**: PROPOSED - Awaiting approval

---

## 0. Verification & Approval (Pre-Implementation)

### 0.1 TeamSOP.md Compliance
- [ ] 0.1.1 Read teamsop.md and understand Template C-4.20 requirements
- [ ] 0.1.2 Read CLAUDE.md for project-specific rules
- [ ] 0.1.3 Understand ZERO FALLBACK policy

### 0.2 Current State Verification
- [ ] 0.2.1 Read deps.py:1072-1131 (_check_dockerhub_latest)
- [ ] 0.2.2 Read deps.py:893-912 (_check_pypi_latest)
- [ ] 0.2.3 Read docs_fetch.py:481-530 (fetch_package_docs)
- [ ] 0.2.4 Verify python_package_configs table doesn't exist
- [ ] 0.2.5 Test current behavior on DEIC project
- [ ] 0.2.6 Document all line numbers for modifications

### 0.3 Proposal Documentation
- [ ] 0.3.1 Create proposal.md (this document)
- [ ] 0.3.2 Create verification.md with hypothesis testing
- [ ] 0.3.3 Create tasks.md with atomic tasks
- [ ] 0.3.4 Create design.md with technical architecture

### 0.4 Approval
- [ ] 0.4.1 Submit for Architect review (Santa)
- [ ] 0.4.2 Submit for Lead Auditor review (Gemini)
- [ ] 0.4.3 Address feedback and revise
- [ ] 0.4.4 Receive final approval

**GATE**: DO NOT proceed to Week 1 until approval received

---

## Week 1: Emergency Production Fixes (Days 1-5)

**Objective**: Stop production disasters immediately
**Risk Level**: CRITICAL (Production safety)

### Day 1-2: Docker Tag Semantic Parser

#### 1.1 Create Parser Function
- [ ] 1.1.1 Add `_parse_docker_tag()` to deps.py after line 1070
- [ ] 1.1.2 Import `re` module if not already imported
- [ ] 1.1.3 Handle meta tags (latest, alpine, slim, main, master)
- [ ] 1.1.4 Detect stability markers (alpha, beta, rc, dev, nightly)
- [ ] 1.1.5 Extract semantic version tuple (major, minor, patch)
- [ ] 1.1.6 Extract variant/base image string
- [ ] 1.1.7 Return parsed dictionary structure

#### 1.2 Parser Implementation
```python
# Location: deps.py after line 1070
def _parse_docker_tag(tag: str) -> Optional[Dict[str, Any]]:
    """Parse Docker tag into semantic components."""
    # Skip meta tags
    if tag in ["latest", "alpine", "slim", "main", "master"]:
        return None

    # Detect stability
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

    # Extract version
    match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?', tag)
    if not match:
        return None

    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)

    # Extract variant
    variant = tag[match.end():].lstrip('-')

    return {
        'tag': tag,
        'version': (major, minor, patch),
        'variant': variant,
        'stability': stability
    }
```

#### 1.3 Base Preference Helper
- [ ] 1.3.1 Add `_extract_base_preference()` function
- [ ] 1.3.2 Check for alpine, bookworm, bullseye, slim variants
- [ ] 1.3.3 Check for windowsservercore, nanoserver variants
- [ ] 1.3.4 Return base type or empty string

### Day 3: Update Docker Latest Checker

#### 1.4 Replace _check_dockerhub_latest
- [ ] 1.4.1 Back up current function (comment out)
- [ ] 1.4.2 Replace lines 1072-1131 with new implementation
- [ ] 1.4.3 Parse all tags with _parse_docker_tag
- [ ] 1.4.4 Filter to stable only by default
- [ ] 1.4.5 Allow RC fallback with warning
- [ ] 1.4.6 Match current base image preference
- [ ] 1.4.7 Sort by semantic version tuple
- [ ] 1.4.8 Return best match or None

#### 1.5 PyPI Defensive Filtering
- [ ] 1.5.1 Add packaging to imports: `from packaging.version import parse`
- [ ] 1.5.2 Update _check_pypi_latest (lines 893-912)
- [ ] 1.5.3 Get all releases from PyPI JSON
- [ ] 1.5.4 Filter with parse(version).is_prerelease
- [ ] 1.5.5 Return max(stable_versions) only
- [ ] 1.5.6 Add try/except for packaging import

### Day 4: CLI Flag Integration

#### 1.6 Add --allow-prerelease Flag
- [ ] 1.6.1 Open theauditor/commands/deps.py
- [ ] 1.6.2 Find @click.option decorators (around line 16)
- [ ] 1.6.3 Add new option: `@click.option("--allow-prerelease", is_flag=True)`
- [ ] 1.6.4 Add help text: "Allow alpha/beta/rc versions (default: stable only)"
- [ ] 1.6.5 Pass flag to check functions
- [ ] 1.6.6 Update function signatures to accept flag
- [ ] 1.6.7 Test flag works: `aud deps --help`

### Day 5: Production Testing

#### 1.7 Test on DEIC Project
- [ ] 1.7.1 Navigate to DEIC: `cd C:/Users/santa/Desktop/DEIC`
- [ ] 1.7.2 Run: `aud deps --upgrade-all`
- [ ] 1.7.3 Verify NO downgrades (17 should stay 17 or higher)
- [ ] 1.7.4 Verify NO alpha/beta/rc (unless --allow-prerelease)
- [ ] 1.7.5 Verify base preserved (alpine stays alpine)
- [ ] 1.7.6 Document results in verification.md

#### 1.8 Unit Tests
- [ ] 1.8.1 Create tests/test_docker_tag_parsing.py
- [ ] 1.8.2 Test _parse_docker_tag with various inputs
- [ ] 1.8.3 Test stability detection
- [ ] 1.8.4 Test version extraction
- [ ] 1.8.5 Test base preference matching
- [ ] 1.8.6 Run tests: `pytest tests/test_docker_tag_parsing.py -v`

**GATE**: Week 1 must be production-safe before proceeding

---

## Week 2: Python Deps Database Storage (Days 6-10)

**Objective**: Achieve parity between npm and Python deps storage
**Risk Level**: LOW (Additive, backward compatible)

### Day 6-7: Create Python Deps Extractor

#### 2.1 Create Extractor Module
- [ ] 2.1.1 Create theauditor/indexer/extractors/python_deps.py
- [ ] 2.1.2 Add imports: json, tomllib, Path, typing
- [ ] 2.1.3 Create extract_python_dependencies() main function
- [ ] 2.1.4 Add _extract_from_pyproject() for pyproject.toml
- [ ] 2.1.5 Add _extract_from_requirements() for requirements.txt
- [ ] 2.1.6 Add _parse_dep_spec() for version parsing
- [ ] 2.1.7 Handle git URLs and extras

#### 2.2 Pyproject.toml Parsing
- [ ] 2.2.1 Use tomllib.loads() to parse TOML
- [ ] 2.2.2 Extract [project] section
- [ ] 2.2.3 Get dependencies array
- [ ] 2.2.4 Get optional-dependencies groups
- [ ] 2.2.5 Extract project name and version
- [ ] 2.2.6 Extract build-system info
- [ ] 2.2.7 Return structured dict for database

#### 2.3 Requirements.txt Parsing
- [ ] 2.3.1 Split content by lines
- [ ] 2.3.2 Skip comments and empty lines
- [ ] 2.3.3 Skip -r and -e directives
- [ ] 2.3.4 Strip inline comments
- [ ] 2.3.5 Parse package==version format
- [ ] 2.3.6 Handle >=, ~=, != operators
- [ ] 2.3.7 Return JSON-serializable dict

### Day 8: Add Database Schema

#### 2.4 Update Python Schema
- [ ] 2.4.1 Open theauditor/indexer/schemas/python_schema.py
- [ ] 2.4.2 Find PYTHON_TABLES list
- [ ] 2.4.3 Add CREATE TABLE python_package_configs SQL
- [ ] 2.4.4 Add columns: file_path, file_type, project_name, etc.
- [ ] 2.4.5 Add dependencies column (JSON TEXT)
- [ ] 2.4.6 Add indexes on file_path and project_name
- [ ] 2.4.7 Verify SQL syntax is correct

#### 2.5 Register Extractor
- [ ] 2.5.1 Open theauditor/indexer/extractors/python.py
- [ ] 2.5.2 Import python_deps module
- [ ] 2.5.3 In extract() function, check for pyproject.toml
- [ ] 2.5.4 Check for requirements*.txt files
- [ ] 2.5.5 Call extract_python_dependencies()
- [ ] 2.5.6 Store result in file_info['python_deps']
- [ ] 2.5.7 Ensure storage layer handles new data

### Day 9: Update deps.py Reader

#### 2.6 Add Database Reader
- [ ] 2.6.1 Create _read_python_deps_from_database() in deps.py
- [ ] 2.6.2 Check if python_package_configs table exists
- [ ] 2.6.3 Query: SELECT file_path, dependencies, optional_dependencies
- [ ] 2.6.4 Parse JSON from dependencies column
- [ ] 2.6.5 Convert to deps.py format (name, version, manager)
- [ ] 2.6.6 Include optional dependencies with group tag
- [ ] 2.6.7 Handle JSON decode errors gracefully

#### 2.7 Integrate with parse_dependencies
- [ ] 2.7.1 Find parse_dependencies() function
- [ ] 2.7.2 Add database check for Python deps
- [ ] 2.7.3 Only fall back to file parsing if DB empty
- [ ] 2.7.4 Maintain backward compatibility
- [ ] 2.7.5 Test with database present
- [ ] 2.7.6 Test with database absent (fallback)

### Day 10: Testing

#### 2.8 Integration Testing
- [ ] 2.8.1 Run `aud full` on TheAuditor itself
- [ ] 2.8.2 Query: `sqlite3 .pf/repo_index.db "SELECT * FROM python_package_configs"`
- [ ] 2.8.3 Verify pyproject.toml extracted
- [ ] 2.8.4 Verify dependencies JSON valid
- [ ] 2.8.5 Run `aud deps` and time it
- [ ] 2.8.6 Verify <1 second execution (vs 2-5 seconds before)

#### 2.9 Monorepo Testing
- [ ] 2.9.1 Test on project with multiple requirements.txt
- [ ] 2.9.2 Verify all files extracted
- [ ] 2.9.3 Check backend/requirements.txt handled
- [ ] 2.9.4 Check frontend/requirements.txt handled
- [ ] 2.9.5 Verify no duplicate entries

---

## Week 3: Documentation Crawling (Days 11-15)

**Objective**: Fetch real documentation, not just README
**Risk Level**: MEDIUM (External dependencies, network I/O)

### Day 11: Add Dependencies

#### 3.1 Update pyproject.toml
- [ ] 3.1.1 Open pyproject.toml
- [ ] 3.1.2 Find [project.optional-dependencies]
- [ ] 3.1.3 Add docs group if not exists
- [ ] 3.1.4 Add "beautifulsoup4>=4.12.0"
- [ ] 3.1.5 Add "markdownify>=0.11.0"
- [ ] 3.1.6 Add "packaging>=23.0" to dev group
- [ ] 3.1.7 Run: `pip install -e ".[docs]"`

### Day 12-13: Replace Regex with BeautifulSoup

#### 3.2 Create HTML Parser
- [ ] 3.2.1 Open theauditor/docs_fetch.py
- [ ] 3.2.2 Add imports: from bs4 import BeautifulSoup
- [ ] 3.2.3 Add: from markdownify import markdownify as md
- [ ] 3.2.4 Find regex HTML parsing section (~line 600-700)
- [ ] 3.2.5 Comment out regex code (keep for reference)
- [ ] 3.2.6 Create _fetch_and_convert_html() function

#### 3.3 BeautifulSoup Implementation
- [ ] 3.3.1 Parse HTML with BeautifulSoup(html, 'html.parser')
- [ ] 3.3.2 Remove script, style, nav, footer, header tags
- [ ] 3.3.3 Find main content (article, main, div.docs-content)
- [ ] 3.3.4 Convert to markdown with markdownify
- [ ] 3.3.5 Clean excessive whitespace
- [ ] 3.3.6 Handle encoding properly (utf-8)
- [ ] 3.3.7 Test on sample HTML

#### 3.4 Implement Crawler
- [ ] 3.4.1 Create _crawl_docs_site() function
- [ ] 3.4.2 Build version-specific URL patterns
- [ ] 3.4.3 Define priority pages list
- [ ] 3.4.4 Try multiple URL formats per page
- [ ] 3.4.5 Check _is_url_allowed() for each
- [ ] 3.4.6 Add rate limiting (0.5 sec sleep)
- [ ] 3.4.7 Stop at max_pages limit

#### 3.5 Version URL Patterns
- [ ] 3.5.1 Pattern: /{version}/
- [ ] 3.5.2 Pattern: /en/{version}/
- [ ] 3.5.3 Pattern: /v{version}/
- [ ] 3.5.4 Pattern: /{major}.x/ for Flask-style
- [ ] 3.5.5 Try with .html extension
- [ ] 3.5.6 Try /user/ subdirectory
- [ ] 3.5.7 Handle 404s gracefully

### Day 14: Storage Restructure

#### 3.6 Update fetch_package_docs
- [ ] 3.6.1 Modify return type to Dict[str, str]
- [ ] 3.6.2 Store README.md separately
- [ ] 3.6.3 Store quickstart.md separately
- [ ] 3.6.4 Store api_reference.md separately
- [ ] 3.6.5 Store migration_guide.md separately
- [ ] 3.6.6 Create directory: docs/{ecosystem}/{package}@{version}/
- [ ] 3.6.7 Write each .md file separately

#### 3.7 Add Metadata
- [ ] 3.7.1 Create meta.json for each package
- [ ] 3.7.2 Store source URLs
- [ ] 3.7.3 Store fetch timestamp
- [ ] 3.7.4 Store version info
- [ ] 3.7.5 Store file count

### Day 15: Integration Testing

#### 3.8 Test Popular Packages
- [ ] 3.8.1 Test: `aud docs fetch flask --max-pages 5`
- [ ] 3.8.2 Test: `aud docs fetch requests --max-pages 5`
- [ ] 3.8.3 Test: `aud docs fetch numpy --max-pages 5`
- [ ] 3.8.4 Test: `aud docs fetch express --max-pages 5`
- [ ] 3.8.5 Test: `aud docs fetch react --max-pages 5`

#### 3.9 Verify Content Quality
- [ ] 3.9.1 Check .pf/context/docs/ structure
- [ ] 3.9.2 Verify multiple .md files per package
- [ ] 3.9.3 Check markdown formatting clean
- [ ] 3.9.4 Verify code blocks preserved
- [ ] 3.9.5 Check no HTML artifacts remain

---

## Week 4: AI Extraction Prompts (Days 16-20)

**Objective**: Generate prompts for AI-based syntax extraction
**Risk Level**: LOW (Additive feature)

### Day 16-17: Create Extraction Module

#### 4.1 Create docs_extract.py
- [ ] 4.1.1 Create theauditor/docs_extract.py
- [ ] 4.1.2 Add imports: Path, Dict, Any, typing
- [ ] 4.1.3 Create create_ai_extraction_prompt() function
- [ ] 4.1.4 Create _smart_truncate() helper
- [ ] 4.1.5 Define prompt template
- [ ] 4.1.6 Handle token limits
- [ ] 4.1.7 Save prompts to files

#### 4.2 Smart Truncation
- [ ] 4.2.1 Parse content into sections
- [ ] 4.2.2 Identify section headers
- [ ] 4.2.3 Priority: quickstart > api > examples
- [ ] 4.2.4 Track token count (rough estimate)
- [ ] 4.2.5 Include complete sections only
- [ ] 4.2.6 Stop at max_tokens limit
- [ ] 4.2.7 Return prioritized content

#### 4.3 Prompt Generation
- [ ] 4.3.1 Include package name and version
- [ ] 4.3.2 Request essential imports
- [ ] 4.3.3 Request quickstart code
- [ ] 4.3.4 Request API patterns
- [ ] 4.3.5 Request breaking changes
- [ ] 4.3.6 Emphasize code over explanation
- [ ] 4.3.7 Include truncated docs

### Day 18: Update Capsule Generation

#### 4.4 Modify docs_summarize.py
- [ ] 4.4.1 Open theauditor/docs_summarize.py
- [ ] 4.4.2 Update create_version_capsule() signature
- [ ] 4.4.3 Add version header section
- [ ] 4.4.4 Add install command for version
- [ ] 4.4.5 Add AI extraction prompt path
- [ ] 4.4.6 Add raw docs section
- [ ] 4.4.7 Update capsule structure

#### 4.5 Capsule Content
- [ ] 4.5.1 Header: # {package} v{version} ({ecosystem})
- [ ] 4.5.2 Install: pip install {package}=={version}
- [ ] 4.5.3 AI prompt location reference
- [ ] 4.5.4 Full docs directory reference
- [ ] 4.5.5 List available doc files
- [ ] 4.5.6 Include raw docs for AI consumption
- [ ] 4.5.7 Keep under token limit

### Day 19: CLI Flags

#### 4.6 Add Command Options
- [ ] 4.6.1 Open theauditor/commands/docs.py
- [ ] 4.6.2 Add --max-pages option (default 10)
- [ ] 4.6.3 Add --extract-syntax flag
- [ ] 4.6.4 Add --version-aware flag
- [ ] 4.6.5 Pass options to fetch functions
- [ ] 4.6.6 Update help text
- [ ] 4.6.7 Test: `aud docs fetch --help`

### Day 20: Final Validation

#### 4.7 End-to-End Testing
- [ ] 4.7.1 Fetch docs: `aud docs fetch flask --max-pages 5`
- [ ] 4.7.2 Check extraction prompts created
- [ ] 4.7.3 Generate capsule: `aud docs summarize flask`
- [ ] 4.7.4 Verify capsule has version header
- [ ] 4.7.5 Check AI prompt referenced
- [ ] 4.7.6 Verify raw docs included

#### 4.8 Performance Validation
- [ ] 4.8.1 Time full workflow
- [ ] 4.8.2 Check crawl rate limiting works
- [ ] 4.8.3 Verify no memory leaks
- [ ] 4.8.4 Test with slow network
- [ ] 4.8.5 Check error handling

#### 4.9 Final Cleanup
- [ ] 4.9.1 Remove commented old code
- [ ] 4.9.2 Update documentation
- [ ] 4.9.3 Run full test suite
- [ ] 4.9.4 Create PR if needed
- [ ] 4.9.5 Update CHANGELOG

---

## Post-Implementation Validation

### 5.1 Success Metrics Verification
- [ ] 5.1.1 Zero downgrades on DEIC project
- [ ] 5.1.2 No alpha/beta/rc unless flagged
- [ ] 5.1.3 Base images preserved
- [ ] 5.1.4 5+ doc pages per package
- [ ] 5.1.5 Python deps in database
- [ ] 5.1.6 Sub-1 second deps command

### 5.2 Documentation Updates
- [ ] 5.2.1 Update README with new flags
- [ ] 5.2.2 Document database schema changes
- [ ] 5.2.3 Add examples to docs
- [ ] 5.2.4 Update CLI help text

### 5.3 Rollback Plan
- [ ] 5.3.1 Document rollback steps
- [ ] 5.3.2 Keep old code commented (1 month)
- [ ] 5.3.3 Database migration reversible
- [ ] 5.3.4 Test rollback procedure

---

## Risk Mitigation Checkpoints

**After Each Week:**
- [ ] Run full test suite
- [ ] Test on production project
- [ ] Profile performance
- [ ] Check memory usage
- [ ] Verify backward compatibility
- [ ] Document any issues

**Before Production Release:**
- [ ] Architect approval (Santa)
- [ ] Lead Auditor approval (Gemini)
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Rollback plan tested

---

## Task Summary

**Total Tasks**: ~250
**Week 1**: 50 tasks (Emergency fixes)
**Week 2**: 45 tasks (Database parity)
**Week 3**: 65 tasks (Docs crawling)
**Week 4**: 60 tasks (AI extraction)
**Validation**: 30 tasks

**Critical Path**: Week 1 MUST complete first (production safety)

**Dependencies**:
- BeautifulSoup4 (Week 3)
- Markdownify (Week 3)
- Packaging (Week 1)

---

**END OF TASK LIST**