# Dependency Management Specification

## ADDED Requirements

### Requirement: Docker Semantic Version Parsing

TheAuditor MUST parse Docker tags using semantic versioning instead of string comparison.

#### Scenario: Postgres Version Upgrade
Given: Current postgres:17-alpine3.21
When: Running `aud deps --upgrade-all`
Then: Should suggest postgres:17.2-alpine3.21 or higher
And: Should NOT suggest postgres:15.15-trixie (downgrade)

#### Scenario: Stability Filtering
Given: Python container at 3.12-alpine
When: Checking for updates
Then: Should NOT select 3.15.0a1 (alpha)
And: Should NOT select 3.14-rc1 (release candidate)
Unless: --allow-prerelease flag is used

#### Scenario: Base Image Preservation
Given: Redis using redis:7-alpine
When: Upgrading versions
Then: Should select redis:7.4-alpine (same base)
And: Should NOT switch to redis:8-bookworm (different base)

### Requirement: Python Dependencies Database Storage

TheAuditor MUST store Python dependencies in database for consistency with npm.

#### Scenario: Database Population
Given: A project with pyproject.toml
When: Running `aud full`
Then: python_package_configs table is populated
And: Dependencies are stored as JSON

#### Scenario: Fast Dependency Reading
Given: Python deps in database
When: Running `aud deps`
Then: Execution time < 1 second
And: No file parsing occurs

#### Scenario: Monorepo Support
Given: Multiple requirements.txt files in subdirectories
When: Indexing the project
Then: All dependency files are stored
And: Each file has separate database entry

## MODIFIED Requirements

### Requirement: Documentation Fetching Enhancement

TheAuditor's docs fetch MUST retrieve actual documentation, not just README.

#### Scenario: Multi-Page Documentation
Given: Package flask with online docs
When: Running `aud docs fetch flask --max-pages 5`
Then: Fetches README.md, quickstart.md, api.md, etc.
And: Stores in .pf/context/docs/py/flask@3.1.0/

#### Scenario: Version-Specific URLs
Given: Documentation at /en/3.1.x/
When: Fetching docs for flask==3.1.0
Then: Uses version-specific URL patterns
And: Gets v3.1 docs, not latest

#### Scenario: HTML Parsing Robustness
Given: Modern React/Vue documentation site
When: Parsing HTML content
Then: BeautifulSoup handles nested/broken HTML
And: Converts to clean Markdown

### Requirement: Capsule Generation Enhancement

Documentation capsules MUST include version-specific syntax and breaking changes.

#### Scenario: Version Header
Given: Flask version 3.1.0
When: Generating capsule
Then: Header shows "# Flask v3.1.0 (py)"
And: Install shows "pip install flask==3.1.0"

#### Scenario: AI Extraction Prompts
Given: Multiple documentation pages
When: Creating capsule
Then: Generates extraction prompt in extraction_prompts/
And: Includes truncated docs for AI processing

#### Scenario: Breaking Changes Section
Given: Migration guide with deprecations
When: Parsing documentation
Then: Extracts breaking changes for version
And: Includes in capsule output

## Security Requirements

### Requirement: Package Name Validation

TheAuditor MUST validate package names to prevent security issues.

#### Scenario: Directory Traversal Prevention
Given: Malicious package name "../../../etc/passwd"
When: Processing package name
Then: Rejects with validation error
And: Prevents directory traversal

#### Scenario: URL Encoding
Given: Package name with special characters
When: Making API requests
Then: Properly URL encodes components
And: Prevents injection attacks

### Requirement: No Automatic Installation

TheAuditor MUST never automatically install or upgrade packages.

#### Scenario: Upgrade Suggestions Only
Given: Outdated dependencies detected
When: Running `aud deps --upgrade-all`
Then: Shows suggested versions
But: Does NOT run pip/npm install
And: Requires user to manually upgrade

## Performance Requirements

### Requirement: Sub-Second Dependency Checks

Dependency checks MUST complete in under 1 second when using database.

#### Scenario: Cached Python Dependencies
Given: python_package_configs table populated
When: Running `aud deps`
Then: Completes in < 1 second
And: No file system parsing occurs

#### Scenario: First Run Performance
Given: Empty database
When: Running `aud deps`
Then: Falls back to file parsing
And: Still completes in < 5 seconds

### Requirement: Documentation Crawl Rate Limiting

Documentation fetching MUST respect rate limits.

#### Scenario: Sequential Fetching
Given: Multiple pages to fetch
When: Crawling documentation site
Then: Waits 0.5 seconds between requests
And: Respects max_pages limit

#### Scenario: Timeout Handling
Given: Slow documentation server
When: Fetching page exceeds 10 seconds
Then: Times out gracefully
And: Continues with next page

## REMOVED Requirements

### Requirement: Regex HTML Parsing

TheAuditor MUST NOT use regex for HTML parsing.

#### Scenario: Complex HTML Structure
Given: HTML with nested tags
When: Parsing documentation
Then: Uses BeautifulSoup parser
And: NOT regex patterns

### Requirement: String-Based Version Comparison

TheAuditor MUST NOT use string comparison for versions.

#### Scenario: Version Sorting
Given: Tags ["17", "8", "15.15"]
When: Sorting versions
Then: Uses semantic tuples (17,0,0) > (15,15,0)
And: NOT alphabetical order

---