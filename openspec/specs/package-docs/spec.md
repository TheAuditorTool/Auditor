# package-docs Specification

## Purpose
TBD - created by archiving change add-usage-extractor. Update Purpose after archive.
## Requirements
### Requirement: Usage Snippet Extraction

The system SHALL extract code snippets from cached package documentation markdown files and return them ranked by quality score.

#### Scenario: Extract snippets from cached npm package

- **GIVEN** axios@1.13.2 docs are cached at `.pf/context/docs/npm/axios@1.13.2/doc.md`
- **WHEN** user runs `aud deps --usage axios`
- **THEN** system parses all markdown files in the package directory
- **AND** extracts fenced code blocks with their preceding context
- **AND** scores each snippet using quality heuristics
- **AND** returns top 5 snippets sorted by score descending

#### Scenario: Extract snippets from cached Python package

- **GIVEN** requests docs are cached at `.pf/context/docs/py/requests@==2.28.0/doc.md`
- **WHEN** user runs `aud deps --usage requests`
- **THEN** system finds the package directory (handling `==` version prefix)
- **AND** returns scored Python code snippets

#### Scenario: Handle scoped npm packages

- **GIVEN** @angular/core docs are cached at `.pf/context/docs/npm/_at_angular_core@18.0.0/`
- **WHEN** user runs `aud deps --usage @angular/core`
- **THEN** system converts `@` to `_at_` and `/` to `_` for path lookup
- **AND** returns scored TypeScript/JavaScript snippets

### Requirement: Snippet Quality Scoring

The system SHALL score code snippets using deterministic heuristics to rank usage examples above installation commands.

#### Scenario: Demote installation commands

- **GIVEN** a code block contains `npm install axios` or `pip install requests`
- **WHEN** scoring is applied
- **THEN** the snippet receives score of 0 (filtered from results)

#### Scenario: Promote import statements

- **GIVEN** a code block contains `import axios from 'axios'` or `from requests import get`
- **WHEN** scoring is applied
- **THEN** the snippet receives +5 score bonus

#### Scenario: Promote usage keywords in context

- **GIVEN** the text before a code block contains "usage", "example", "quickstart", or "how to"
- **WHEN** scoring is applied
- **THEN** the snippet receives +5 score bonus

#### Scenario: Demote help output

- **GIVEN** a code block contains `--help` or starts with `Usage:`
- **WHEN** scoring is applied
- **THEN** the snippet receives -5 score penalty

### Requirement: JSON Output Format

The system SHALL support JSON output for AI agent consumption via `--format json` flag.

#### Scenario: JSON output structure

- **WHEN** user runs `aud deps --usage axios --format json`
- **THEN** system outputs valid JSON with structure:
  ```json
  {
    "package": "axios",
    "manager": "npm",
    "snippets": [
      {
        "rank": 1,
        "score": 22,
        "language": "javascript",
        "content": "import axios...",
        "context": "Making a GET request:",
        "source_file": "doc.md"
      }
    ],
    "total_found": 15,
    "returned": 5
  }
  ```

#### Scenario: Empty results JSON

- **GIVEN** no docs are cached for package `nonexistent-pkg`
- **WHEN** user runs `aud deps --usage nonexistent-pkg --format json`
- **THEN** system outputs:
  ```json
  {
    "package": "nonexistent-pkg",
    "manager": null,
    "snippets": [],
    "total_found": 0,
    "returned": 0,
    "error": "No cached docs found for nonexistent-pkg"
  }
  ```

### Requirement: Cache Miss Handling

The system SHALL attempt to fetch docs on cache miss (unless offline mode).

#### Scenario: Auto-fetch on cache miss (online)

- **GIVEN** package `new-package` has no cached docs
- **AND** network is available (not `--offline`)
- **WHEN** user runs `aud deps --usage new-package`
- **THEN** system prints "Cache miss for new-package, fetching docs..."
- **AND** calls `fetch_docs` for the package
- **AND** retries extraction after fetch completes

#### Scenario: No fetch in offline mode

- **GIVEN** package `new-package` has no cached docs
- **WHEN** user runs `aud deps --usage new-package --offline`
- **THEN** system returns empty results
- **AND** prints "No cached docs found for new-package"
- **AND** does NOT attempt network fetch

### Requirement: Multi-File Parsing

The system SHALL parse all markdown files in a package's cache directory, not just `doc.md`.

#### Scenario: Parse quickstart and tutorial files

- **GIVEN** package has cached files: `doc.md`, `quickstart.md`, `api.md`, `tutorial.md`
- **WHEN** extraction is performed
- **THEN** system parses ALL `.md` files in the directory
- **AND** includes `source_file` field in each snippet for provenance

#### Scenario: Prioritize quickstart over readme

- **GIVEN** both `doc.md` and `quickstart.md` exist with similar snippets
- **WHEN** scoring is applied
- **THEN** snippets from `quickstart.md` receive implicit priority (parsed first, appear earlier in ties)

### Requirement: Context Capture

The system SHALL capture up to 3 lines of text preceding each code block as context.

#### Scenario: Multi-line context

- **GIVEN** markdown content:
  ```markdown
  ## Making Requests

  The simplest way to make a request is:

  ```javascript
  axios.get('/users')
  ```
  ```
- **WHEN** parsing extracts this code block
- **THEN** context field contains "## Making Requests\n\nThe simplest way to make a request is:"

#### Scenario: No preceding context

- **GIVEN** a code block appears at the start of a file with no preceding text
- **WHEN** parsing extracts this code block
- **THEN** context field is empty string (not None)

### Requirement: Language Detection

The system SHALL preserve the language identifier from fenced code blocks.

#### Scenario: Explicit language tag

- **GIVEN** code block starts with ` ```typescript `
- **WHEN** parsing extracts this block
- **THEN** `language` field is "typescript"

#### Scenario: No language tag

- **GIVEN** code block starts with ` ``` ` (no language)
- **WHEN** parsing extracts this block
- **THEN** `language` field is empty string
- **AND** snippet is still included (not filtered)

### Requirement: Windows Compatibility

The system SHALL NOT use emoji characters in any output (Windows CP1252 encoding crash).

#### Scenario: Text output uses ASCII only

- **WHEN** user runs `aud deps --usage axios`
- **THEN** all output uses ASCII characters only
- **AND** status indicators use text like "[OK]", "[FAIL]", not emoji

