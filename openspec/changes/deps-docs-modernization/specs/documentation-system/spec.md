# Documentation System Specification

## ADDED Requirements

### Requirement: Documentation Site Crawling

TheAuditor MUST crawl documentation sites for comprehensive content.

#### Scenario: ReadTheDocs Crawling
Given: Package with ReadTheDocs documentation
When: Fetching docs with crawling enabled
Then: Follows links to quickstart, API, examples
And: Stores multiple .md files

#### Scenario: Version-Aware URL Discovery
Given: Flask docs at /en/3.1.x/
When: Fetching docs for version 3.1.0
Then: Tries version-specific URL patterns
And: Gets correct version documentation

#### Scenario: Priority Page Selection
Given: Limited max_pages setting
When: Crawling documentation
Then: Prioritizes quickstart > API > examples
And: Stops at max_pages limit

### Requirement: AI Extraction Prompt Generation

TheAuditor MUST generate prompts for AI-based syntax extraction.

#### Scenario: Prompt File Creation
Given: Documentation fetched for flask@3.1.0
When: Processing docs for extraction
Then: Creates extraction_prompts/flask@3.1.0.txt
And: Includes structured extraction request

#### Scenario: Smart Content Truncation
Given: 100KB of documentation text
When: Creating extraction prompt
Then: Prioritizes valuable sections
And: Keeps within token limit

#### Scenario: Code Pattern Request
Given: AI extraction prompt
When: Specifying requirements
Then: Requests imports, patterns, breaking changes
And: Emphasizes code over explanations

## MODIFIED Requirements

### Requirement: HTML to Markdown Conversion

Documentation HTML MUST be converted using proper parsing, not regex.

#### Scenario: BeautifulSoup Parsing
Given: Complex HTML with nested tags
When: Converting to Markdown
Then: Uses BeautifulSoup4 parser
And: Handles broken HTML gracefully

#### Scenario: Code Block Preservation
Given: HTML with <pre><code> blocks
When: Converting to Markdown
Then: Preserves language hints
And: Maintains proper formatting

#### Scenario: Modern Framework Sites
Given: React/Vue documentation site
When: Parsing dynamic content
Then: Extracts rendered content correctly
And: Removes navigation/footer noise

### Requirement: Version-Specific Capsules

Documentation capsules MUST be version-specific and comprehensive.

#### Scenario: Version Header
Given: numpy version 2.3.4
When: Creating capsule
Then: Shows "# numpy v2.3.4 (py)"
And: NOT generic "# numpy"

#### Scenario: Breaking Changes Section
Given: Version with deprecations
When: Generating capsule
Then: Includes "## Breaking Changes in v2.3.4"
And: Lists deprecated/removed features

#### Scenario: Multiple Documentation Files
Given: 5 documentation files fetched
When: Creating capsule
Then: References all files in "Full Documentation" section
And: Includes file list

## Storage Requirements

### Requirement: Structured Documentation Storage

Documentation MUST be stored in version-specific directories.

#### Scenario: Directory Structure
Given: Flask version 3.1.0 docs
When: Storing documentation
Then: Creates .pf/context/docs/py/flask@3.1.0/
And: NOT generic flask/ directory

#### Scenario: Multiple File Storage
Given: README, quickstart, API docs
When: Saving documentation
Then: Stores as separate .md files
And: NOT concatenated into single file

#### Scenario: Metadata Tracking
Given: Documentation fetched from multiple sources
When: Storing docs
Then: Creates meta.json with source URLs
And: Includes fetch timestamp

### Requirement: Extraction Prompt Storage

AI extraction prompts MUST be stored for processing.

#### Scenario: Prompt File Location
Given: Generated extraction prompt
When: Saving for AI processing
Then: Stores in extraction_prompts/{package}@{version}.txt
And: Uses consistent naming

#### Scenario: Prompt Content Structure
Given: Documentation to process
When: Creating prompt
Then: Includes package, version, requirements
And: Provides truncated documentation

## Performance Requirements

### Requirement: Crawl Rate Limiting

Documentation crawling MUST respect server limits.

#### Scenario: Request Delay
Given: Multiple pages to fetch
When: Crawling sequentially
Then: Waits 0.5 seconds between requests
And: Prevents server overload

#### Scenario: Maximum Pages
Given: --max-pages 10 setting
When: Crawling large site
Then: Stops after 10 pages
And: Logs pages fetched

### Requirement: Content Size Limits

Documentation storage MUST handle large content gracefully.

#### Scenario: Individual File Limit
Given: Single documentation page
When: Content exceeds 10MB
Then: Truncates to 10MB
And: Logs truncation warning

#### Scenario: Total Package Limit
Given: Package documentation
When: Total size exceeds 50MB
Then: Stops crawling additional pages
And: Keeps existing content

## REMOVED Requirements

### Requirement: README-Only Fetching

TheAuditor MUST NOT fetch only README files.

#### Scenario: Comprehensive Fetching
Given: Package with documentation site
When: Fetching documentation
Then: Crawls multiple pages
And: NOT just README

### Requirement: Blind Content Truncation

TheAuditor MUST NOT truncate at arbitrary line counts.

#### Scenario: Smart Truncation
Given: Large documentation
When: Truncating for capsule
Then: Keeps complete sections
And: NOT cuts at 50 lines

---