# Implementation Tasks: AI-First CLI Help System Modernization

**Change ID**: update-cli-help-ai-first
**Status**: Proposed
**Total Tasks**: 94
**Completed**: 0/94

---

## Phase 0: Verification & Preparation (6 tasks)

### 0.1 Pre-Implementation Verification (teamsop.md Prime Directive)

- [ ] **Task 0.1.1**: Re-read teamsop.md Section 1.3 (Prime Directive)
  - Confirm: Question Everything, Assume Nothing, Verify Everything
  - Document: Initial hypotheses about code state

- [ ] **Task 0.1.2**: Verify current VerboseGroup implementation
  - Read: `theauditor/cli.py` lines 24-172
  - Confirm: Hardcoded help text exists
  - Evidence: Screenshot or copy of current implementation

- [ ] **Task 0.1.3**: Count registered commands
  - Command: `grep -c "cli.add_command" theauditor/cli.py`
  - Expected: 35 registrations
  - Actual: [Record result]

- [ ] **Task 0.1.4**: Verify invisible commands
  - Command: `aud --help | grep "aud explain"`
  - Expected: NOT FOUND (currently invisible)
  - Command: `aud --help | grep "aud detect-frameworks"`
  - Expected: NOT FOUND (currently invisible)
  - Evidence: [Record if found or not found]

- [ ] **Task 0.1.5**: Measure baseline help text quality
  - Command: `aud explain --help | wc -l`
  - Command: `aud tool-versions --help | wc -l`
  - Command: `aud query --help | wc -l`
  - Record: Baseline line counts for comparison

- [ ] **Task 0.1.6**: Create verification.md (teamsop.md Section 2.3)
  - File: `openspec/changes/update-cli-help-ai-first/verification.md`
  - Content: Hypotheses, evidence, discrepancies found
  - Template from: teamsop.md lines 73-78

---

## Phase 1: Dynamic VerboseGroup Implementation (24 tasks)

### 1.1 Backup & Safety (3 tasks)

- [ ] **Task 1.1.1**: Backup current cli.py
  - Command: `cp theauditor/cli.py theauditor/cli.py.backup_$(date +%Y%m%d)`
  - Verify: Backup file exists

- [ ] **Task 1.1.2**: Create feature branch (if not on pythonparity)
  - Command: `git checkout pythonparity`
  - Command: `git pull origin pythonparity`
  - Verify: Clean working directory

- [ ] **Task 1.1.3**: Run baseline tests
  - Command: `aud --help > /tmp/baseline_help.txt`
  - Command: `aud full --help > /tmp/baseline_full_help.txt`
  - Purpose: Regression detection

### 1.2 VerboseGroup Taxonomy Definition (6 tasks)

- [ ] **Task 1.2.1**: Define COMMAND_CATEGORIES dict structure
  - Location: `theauditor/cli.py` after line 23
  - Structure: category_id → {title, description, commands, ai_context}
  - Reference: proposal.md Phase 1 code block

- [ ] **Task 1.2.2**: Populate PROJECT_SETUP category
  - Commands: ['init', 'setup-ai', 'setup-claude', 'init-js', 'init-config']
  - AI context: "Run these FIRST in new projects..."

- [ ] **Task 1.2.3**: Populate CORE_ANALYSIS category
  - Commands: ['full', 'index', 'workset']
  - AI context: "Foundation commands. index builds DB..."

- [ ] **Task 1.2.4**: Populate SECURITY_SCANNING category
  - Commands: ['detect-patterns', 'taint-analyze', 'docker-analyze', 'detect-frameworks', 'rules', 'context', 'workflows', 'cdk', 'terraform']
  - AI context: "Security-focused analysis..."
  - **CRITICAL**: Include 'explain' and 'detect-frameworks' here

- [ ] **Task 1.2.5**: Populate remaining 5 categories
  - DEPENDENCIES: ['deps', 'docs']
  - CODE_QUALITY: ['lint', 'cfg', 'graph']
  - DATA_REPORTING: ['fce', 'report', 'structure', 'summary', 'metadata', 'tool-versions', 'blueprint']
  - ADVANCED_QUERIES: ['query', 'impact', 'refactor']
  - INSIGHTS_ML: ['insights', 'learn', 'suggest', 'learn-feedback']
  - UTILITIES: ['explain', 'planning']

- [ ] **Task 1.2.6**: Verify all 35 commands categorized
  - Script: Count commands in COMMAND_CATEGORIES
  - Expected: 33 user-facing + 2 aliases (setup-claude, planning)
  - Missing: Only '_archive' (internal)

### 1.3 Dynamic format_help Implementation (8 tasks)

- [ ] **Task 1.3.1**: Replace format_help method signature
  - Location: `theauditor/cli.py` line 27
  - Change: Keep signature, rewrite body

- [ ] **Task 1.3.2**: Implement super().format_help(ctx, formatter) call
  - Purpose: Preserve original CLI docstring (PURPOSE, QUICK START, etc.)

- [ ] **Task 1.3.3**: Add AI Context Banner
  - Text: "AI ASSISTANT GUIDANCE:"
  - Content: 4 bullet points about categorization and usage
  - Reference: proposal.md Phase 1 code

- [ ] **Task 1.3.4**: Implement registered commands extraction
  - Code: `registered = {name: cmd for name, cmd in self.commands.items() if not name.startswith('_')}`
  - Purpose: Get all user-facing commands

- [ ] **Task 1.3.5**: Implement category iteration loop
  - Loop: for category_id, category_data in COMMAND_CATEGORIES.items()
  - Output: Title, description, ai_context per category

- [ ] **Task 1.3.6**: Implement command listing per category
  - Extract: First line of cmd.help as short_help
  - Format: `aud {cmd_name:20s} # {short_help}`
  - Options: Show first 3 params with help text

- [ ] **Task 1.3.7**: Implement ungrouped command warning
  - Logic: all_categorized = set(sum(commands lists))
  - Logic: ungrouped = registered - all_categorized
  - Output: Warning box if ungrouped exists

- [ ] **Task 1.3.8**: Add footer with guidance
  - Text: "For detailed help: aud <command> --help"
  - Text: "For concepts: aud explain --list"

### 1.4 Testing & Validation (7 tasks)

- [ ] **Task 1.4.1**: Test basic `aud --help` works
  - Command: `aud --help`
  - Verify: No errors, output contains categories

- [ ] **Task 1.4.2**: Verify explain command visible
  - Command: `aud --help | grep "aud explain"`
  - Expected: FOUND (was invisible before)

- [ ] **Task 1.4.3**: Verify detect-frameworks visible
  - Command: `aud --help | grep "aud detect-frameworks"`
  - Expected: FOUND (was invisible before)

- [ ] **Task 1.4.4**: Verify internal commands hidden
  - Command: `aud --help | grep "aud _archive"`
  - Expected: NOT FOUND (correctly hidden)

- [ ] **Task 1.4.5**: Check for ungrouped command warnings
  - Command: `aud --help | grep "WARNING: The following commands are not categorized"`
  - Expected: NO WARNING (all commands should be categorized)

- [ ] **Task 1.4.6**: Test individual command help unchanged
  - Command: `aud full --help`
  - Verify: Original help text still shows (no regression)

- [ ] **Task 1.4.7**: Compare new vs old help output
  - Command: `diff /tmp/baseline_help.txt <(aud --help)`
  - Analyze: Ensure improvements, no loss of information

---

## Phase 2: AI-First Documentation Template (18 tasks)

### 2.1 Template Creation & Documentation (6 tasks)

- [ ] **Task 2.1.1**: Create CLI_DOCUMENTATION_STANDARD.md
  - Location: `docs/CLI_DOCUMENTATION_STANDARD.md` (new file)
  - Content: Full template from proposal.md Phase 2
  - Include: All sections (PURPOSE, AI CONTEXT, EXAMPLES, etc.)

- [ ] **Task 2.1.2**: Document AI ASSISTANT CONTEXT fields
  - Required fields: Purpose, Input, Output, Prerequisites, Integration, Performance
  - Format: YAML-style key-value

- [ ] **Task 2.1.3**: Document EXAMPLES conventions
  - Format: `# Use Case N: Description` followed by command
  - Minimum: 4 examples per command
  - Categories: Common, workset, CI/CD, advanced

- [ ] **Task 2.1.4**: Document COMMON WORKFLOWS structure
  - Required: 3 workflow scenarios
  - Categories: Before Deployment, Pull Request Review, Security Audit

- [ ] **Task 2.1.5**: Document OUTPUT FORMAT JSON schema requirements
  - Must include: file, line, severity, message fields
  - Optional: recommendation, category, confidence

- [ ] **Task 2.1.6**: Create example command using template
  - Pick: `aud tool-versions` (currently 9 lines)
  - Implement: Full template (should become ~100 lines)
  - Purpose: Demonstrate template application

### 2.2 PR Checklist Integration (4 tasks)

- [ ] **Task 2.2.1**: Update .github/PULL_REQUEST_TEMPLATE.md
  - Add: "CLI Documentation Quality" checklist section
  - Items: 12 checkboxes from proposal.md Phase 2 enforcement checklist

- [ ] **Task 2.2.2**: Create .github/CHECKLIST_CLI_DOCS.md
  - Content: Detailed checklist for reviewers
  - Include: Examples of good vs bad documentation

- [ ] **Task 2.2.3**: Update CONTRIBUTING.md
  - Add: Section "CLI Command Documentation Standards"
  - Link: To CLI_DOCUMENTATION_STANDARD.md

- [ ] **Task 2.2.4**: Add documentation to pyproject.toml metadata
  - Field: `[project.urls]`
  - Add: `"CLI Documentation Standard" = "https://github.com/.../docs/CLI_DOCUMENTATION_STANDARD.md"`

### 2.3 CI Enforcement (8 tasks)

- [ ] **Task 2.3.1**: Create tests/test_cli_help_ai_first.py
  - Location: `tests/test_cli_help_ai_first.py` (new file)
  - Purpose: Automated validation of help text quality

- [ ] **Task 2.3.2**: Implement test_all_commands_categorized()
  - Logic: Verify every registered command in COMMAND_CATEGORIES
  - Exception: Only _archive should be uncategorized

- [ ] **Task 2.3.3**: Implement test_help_text_minimum_quality()
  - Logic: Check line count per command tier
  - Thresholds: complex=200, medium=150, simple=80, utility=50

- [ ] **Task 2.3.4**: Implement test_ai_context_section_exists()
  - Logic: Search for "AI ASSISTANT CONTEXT:" in cmd.help
  - Exception: Internal commands

- [ ] **Task 2.3.5**: Implement test_examples_exist()
  - Logic: Count occurrences of `aud {cmd_name}` in help text
  - Minimum: 4 examples per command (except simple utils)

- [ ] **Task 2.3.6**: Implement test_no_duplicate_categories()
  - Logic: Check no command appears in multiple categories
  - Use: collections.Counter

- [ ] **Task 2.3.7**: Add tests to CI pipeline
  - File: `.github/workflows/tests.yml` (or equivalent)
  - Command: `pytest tests/test_cli_help_ai_first.py -v`

- [ ] **Task 2.3.8**: Test CI enforcement locally
  - Command: `pytest tests/test_cli_help_ai_first.py -v`
  - Expected: All tests pass after Phase 3 implementation

---

## Phase 3: Command-Specific Enhancements (46 tasks)

### 3.1 Tier 1: Critical Commands (14 tasks)

#### 3.1.1 detect-frameworks (4 tasks)

- [ ] **Task 3.1.1.1**: Add AI ASSISTANT CONTEXT section
  - Purpose: Shows detected frameworks from database
  - Input: .pf/repo_index.db (frameworks table)
  - Output: .pf/raw/frameworks.json
  - Prerequisites: aud index

- [ ] **Task 3.1.1.2**: Add WHAT IT ANALYZES section
  - Detect: Python (Flask, Django, FastAPI, SQLAlchemy)
  - Detect: JavaScript (React, Vue, Express, Nest.js)
  - Detect: Database frameworks

- [ ] **Task 3.1.1.3**: Add 4 examples
  - Basic: `aud detect-frameworks`
  - Custom output: `aud detect-frameworks --output-json ./frameworks.json`
  - After index: `aud index && aud detect-frameworks`
  - With workset: `aud detect-frameworks --project-path ./src`

- [ ] **Task 3.1.1.4**: Add OUTPUT FORMAT, PERFORMANCE, RELATED COMMANDS
  - JSON schema: {language, framework, version, files_count, confidence}
  - Performance: ~5 seconds (reads from DB)
  - Related: aud index, aud structure

#### 3.1.2 explain (2 tasks)

- [ ] **Task 3.1.2.1**: Verify help text quality (already 515 lines)
  - Confirm: Has comprehensive concept explanations
  - Confirm: Has --list option documented

- [ ] **Task 3.1.2.2**: Add to VerboseGroup UTILITIES category
  - Already done in Task 1.2.5 (UTILITIES category)
  - Verify: Shows up in `aud --help`

#### 3.1.3 init-config (3 tasks)

- [ ] **Task 3.1.3.1**: Expand help text from 1 line to 90 lines
  - Add: PURPOSE - Ensures mypy config exists for type checking
  - Add: WHAT IT CONFIGURES - pyproject.toml [tool.mypy] section

- [ ] **Task 3.1.3.2**: Add mypy config explanation
  - Section: WHAT THIS CREATES
  - Content: Default mypy settings (strict mode, ignore missing imports)
  - Show: Before/after pyproject.toml example

- [ ] **Task 3.1.3.3**: Add examples and integration
  - Example: `aud init-config`
  - Example: `aud init-config --pyproject ./custom/pyproject.toml`
  - Workflow: Run after `aud init` for Python projects
  - Related: aud init, aud lint

#### 3.1.4 rules (3 tasks)

- [ ] **Task 3.1.4.1**: Expand from 24 to 160 lines
  - Add: PURPOSE - Inspects TheAuditor's built-in detection rules
  - Add: WHAT IT SHOWS - 100+ pattern rules, severity levels, categories

- [ ] **Task 3.1.4.2**: Add output examples
  - Show: Sample output of --summary flag
  - Content: Rule categories, severity distribution, coverage by language

- [ ] **Task 3.1.4.3**: Add use cases and integration
  - Use case: Understand what detect-patterns will find
  - Use case: Customize rules for your project
  - Example: `aud rules --summary`
  - Example: `aud rules --summary | grep "SQL Injection"`
  - Related: aud detect-patterns, aud context

#### 3.1.5 summary (3 tasks)

- [ ] **Task 3.1.5.1**: Expand from 15 to 140 lines
  - Add: PURPOSE - Generates executive summary from all phases
  - Differentiate: vs `aud report` (report=detailed, summary=executive)

- [ ] **Task 3.1.5.2**: Add input/output explanation
  - Input: .pf/raw/*.json (all analysis outputs)
  - Output: .pf/readthis/summary.json
  - Format: JSON schema with counts, severity distribution, top findings

- [ ] **Task 3.1.5.3**: Add workflow integration
  - Example: `aud full && aud summary`
  - Example: `aud summary --out ./report/summary.json`
  - Related: aud report, aud full, aud insights

#### 3.1.6 tool-versions (2 tasks) - Already completed in Task 2.1.6

- [ ] **Task 3.1.6.1**: Verify example implementation from Phase 2
  - Confirm: ~100 lines with all required sections

- [ ] **Task 3.1.6.2**: Finalize and test
  - Test: `aud tool-versions --help | wc -l` (should be ~100)
  - Test: Contains AI ASSISTANT CONTEXT section

### 3.2 Tier 2: Needs Improvement (20 tasks)

#### 3.2.1 docker-analyze (2 tasks)

- [ ] **Task 3.2.1.1**: Add context and examples (50→130 lines)
  - AI CONTEXT: Analyzes Dockerfiles for security issues
  - WHEN: Run after aud index on projects with Docker
  - Examples: 4 usage patterns (basic, severity filter, vuln scan, workset)

- [ ] **Task 3.2.1.2**: Add WHAT IT DETECTS
  - List: Exposed secrets, insecure base images, privilege escalation
  - List: Missing health checks, root user, outdated packages

#### 3.2.2 docs (2 tasks)

- [ ] **Task 3.2.2.1**: Add pipeline workflow explanation (20→110 lines)
  - Pipeline: fetch → summarize → view
  - WHEN: After aud deps to get documentation for dependencies
  - AI CONTEXT: Creates AI-optimized "capsules" of package docs

- [ ] **Task 3.2.2.2**: Add examples for all 4 subcommands
  - docs fetch: Fetch README files
  - docs summarize: Create capsules
  - docs list: Show available docs
  - docs view: Display specific package docs

#### 3.2.3 init-js (2 tasks)

- [ ] **Task 3.2.3.1**: Explain package.json changes (25→100 lines)
  - WHAT IT CREATES: package.json with ESLint, TypeScript, scripts
  - Show: Before/after package.json example
  - Explain: --add-hooks adds TheAuditor pre-commit hooks

- [ ] **Task 3.2.3.2**: Add integration examples
  - Example: `aud init && aud init-js`
  - Example: `aud init-js --add-hooks`
  - WHEN: Run after aud init for JavaScript/TypeScript projects

#### 3.2.4 metadata (2 tasks)

- [ ] **Task 3.2.4.1**: Expand group help (20→110 lines)
  - Add: PURPOSE - Collects temporal (churn) and quality (coverage) metadata
  - Add: WHY - Used by FCE for correlation with findings

- [ ] **Task 3.2.4.2**: Link to FCE integration
  - Explain: Metadata feeds into aud fce for risk scoring
  - Example: `aud metadata analyze && aud fce`
  - Related: aud fce, aud insights

#### 3.2.5 learn (2 tasks)

- [ ] **Task 3.2.5.1**: Add ML workflow context (40→140 lines)
  - ML Pipeline: learn → suggest → feedback → learn-feedback
  - WHEN: After multiple aud full runs (needs historical data)
  - AI CONTEXT: Trains models to predict risky files

- [ ] **Task 3.2.5.2**: Explain options in detail
  - --enable-git: Adds git churn features
  - --window: Journal window size (default 10 recent runs)
  - --train-on: full|diff|all (which historical runs to use)

#### 3.2.6 suggest (2 tasks)

- [ ] **Task 3.2.6.1**: Add prerequisite explanation (30→110 lines)
  - PREREQUISITE: Must run aud learn first to train models
  - ERROR: "No models found" → Run aud learn
  - AI CONTEXT: Predicts which files are risky based on training

- [ ] **Task 3.2.6.2**: Add interpretation guidance
  - OUTPUT: JSON with risk scores 0.0-1.0
  - Threshold: >0.7 = high risk, 0.4-0.7 = medium, <0.4 = low
  - Example: Using output with aud workset

#### 3.2.7 learn-feedback (2 tasks)

- [ ] **Task 3.2.7.1**: Add workflow integration (45→120 lines)
  - Workflow: suggest → review → create feedback.json → learn-feedback
  - Show: feedback.json schema (already in docstring, expand)
  - Example: Iterative improvement loop

- [ ] **Task 3.2.7.2**: Add examples with feedback file
  - Example: Creating feedback file after review
  - Example: Re-training with feedback
  - Example: Comparing before/after model performance

#### 3.2.8 refactor (2 tasks)

- [ ] **Task 3.2.8.1**: Add WHEN context (60→150 lines)
  - WHEN: After database migrations or large refactorings
  - Use case: Detect incomplete refactorings (missing updates)
  - Use case: Find cross-stack inconsistencies

- [ ] **Task 3.2.8.2**: Differentiate from aud impact
  - Difference: refactor=migration analysis, impact=change blast radius
  - When to use refactor: After schema changes
  - When to use impact: Before making changes

#### 3.2.9 report (2 tasks)

- [ ] **Task 3.2.9.1**: Explain inputs clearly (70→170 lines)
  - Input: --manifest (file list from aud index)
  - Input: --fce (correlation findings from aud fce)
  - Input: --ml (ML suggestions from aud suggest)
  - Explain: What each input contributes to report

- [ ] **Task 3.2.9.2**: Show output format and chunking
  - OUTPUT: .pf/readthis/*_chunk01.json (65KB chunks)
  - WHY: Optimized for LLM context windows
  - Example: How to consume chunked output

#### 3.2.10 graph analyze (2 tasks)

- [ ] **Task 3.2.10.1**: Expand subcommand help (10→100 lines)
  - Currently: One-line "Analyze graphs for cycles, hotspots, and impact"
  - Add: WHAT IT FINDS - Circular dependencies, hotspots, impact analysis

- [ ] **Task 3.2.10.2**: Add examples and output explanation
  - Example: `aud graph build && aud graph analyze`
  - Example: `aud graph analyze --no-insights` (faster)
  - OUTPUT: .pf/raw/graph_analysis.json with cycles, hotspots

### 3.3 Tier 3: Good Commands - Add Advanced Sections (12 tasks)

#### 3.3.1 full (2 tasks)

- [ ] **Task 3.3.1.1**: Add FLAG INTERACTIONS section
  - Mutually exclusive: --offline + --vuln-scan (vuln-scan requires network, but works offline with cached DBs)
  - Recommended: --exclude-self when running on TheAuditor itself
  - Modifier: --quiet suppresses progress output

- [ ] **Task 3.3.1.2**: Add TROUBLESHOOTING section
  - Error: "Permission denied" → Run aud setup-ai to install sandboxed tools
  - Error: "Timeout" → Increase timeout with env var THEAUDITOR_TIMEOUT_SECONDS
  - Performance: Use --offline to skip network ops (5-10x faster)

#### 3.3.2 index (2 tasks)

- [ ] **Task 3.3.2.1**: Add FLAG INTERACTIONS
  - --follow-symlinks: Default skip (prevents loops)
  - --exclude-self: Use when indexing TheAuditor's own code
  - --dry-run: Preview what will be indexed without writing

- [ ] **Task 3.3.2.2**: Add TROUBLESHOOTING
  - Error: "Database locked" → Close other connections to .pf/repo_index.db
  - Error: "Out of memory" → Use --batch-size to reduce memory usage
  - When to re-run: After adding new files or large refactorings

#### 3.3.3 taint-analyze (2 tasks)

- [ ] **Task 3.3.3.1**: Add FLAG INTERACTIONS
  - --use-cfg: Enabled by default (flow-sensitive analysis)
  - --memory: Enabled by default (5-10x faster with caching)
  - --memory-limit: Auto-detected based on system RAM

- [ ] **Task 3.3.3.2**: Add TROUBLESHOOTING
  - Error: "Out of memory" → Reduce --memory-limit or use --no-memory
  - Performance: --no-cfg disables CFG (faster but less accurate)
  - False positives: Use --severity high to reduce noise

#### 3.3.4 fce (2 tasks)

- [ ] **Task 3.3.4.1**: Add FLAG INTERACTIONS
  - --workset: Limits correlation to workset files
  - --print-plan: Shows detected input files without running
  - --timeout: For large projects (default 1800s = 30 min)

- [ ] **Task 3.3.4.2**: Add TROUBLESHOOTING
  - Error: "No findings to correlate" → Run aud detect-patterns first
  - Performance: Use --workset to limit scope
  - Timeout: Increase with --timeout for 100K+ LOC projects

#### 3.3.5 graph build (2 tasks)

- [ ] **Task 3.3.5.1**: Add FLAG INTERACTIONS
  - --resume: Continue from checkpoint (useful for large projects)
  - --batch-size: Trade off memory vs parallelization
  - --workset: Build graph only for workset files

- [ ] **Task 3.3.5.2**: Add TROUBLESHOOTING
  - Error: "Out of memory" → Reduce --batch-size from default 200
  - Performance: Checkpoint every N batches (resume on crash)
  - When to rebuild: After major refactorings or adding dependencies

#### 3.3.6 impact (2 tasks)

- [ ] **Task 3.3.6.1**: Add FLAG INTERACTIONS
  - --max-depth: Default 1, increase for transitive dependencies
  - --trace-to-backend: Cross-stack analysis (frontend → backend)
  - --verbose: Show detailed dependency chains

- [ ] **Task 3.3.6.2**: Add TROUBLESHOOTING
  - Error: "Symbol not found" → Run aud index first
  - Performance: --max-depth 1 is fast, depth 3+ can be slow
  - Use case: Check impact before refactoring

---

## Phase 4: Validation & Post-Implementation Audit (6 tasks)

### 4.1 Automated Testing (3 tasks)

- [ ] **Task 4.1.1**: Run full test suite
  - Command: `pytest tests/test_cli_help_ai_first.py -v`
  - Expected: All tests pass
  - Fix: Any failing tests indicate missing sections

- [ ] **Task 4.1.2**: Run CI pipeline locally
  - Command: `pytest tests/test_cli_help_ai_first.py -v --cov`
  - Expected: 100% coverage of validation checks

- [ ] **Task 4.1.3**: Test all commands individually
  - Script: `for cmd in $(aud --help | grep "aud " | awk '{print $1}'); do aud $cmd --help | wc -l; done`
  - Verify: All commands meet minimum line counts

### 4.2 Manual QA (3 tasks)

- [ ] **Task 4.2.1**: Manual checklist execution
  - Verify: All 34 commands appear in `aud --help`
  - Verify: explain and detect-frameworks now visible
  - Verify: _archive remains hidden
  - Verify: No ungrouped command warnings

- [ ] **Task 4.2.2**: AI assistant testing
  - Test: New Claude session - can it use tool after only reading --help?
  - Test: Ask AI to run workset analysis after code change
  - Test: Ask AI to explain difference between report and summary

- [ ] **Task 4.2.3**: Regression testing
  - Compare: Old vs new help output for all commands
  - Verify: No information loss
  - Verify: All original content preserved, only enhancements added

---

## Phase 5: Documentation & Communication (6 tasks)

### 5.1 Update Project Documentation (3 tasks)

- [ ] **Task 5.1.1**: Update README.md
  - Section: "AI-First Design" (new)
  - Content: Explain how help system is optimized for AI assistants
  - Link: To CLI_DOCUMENTATION_STANDARD.md

- [ ] **Task 5.1.2**: Update CHANGELOG.md
  - Entry: "CLI Help System Modernization"
  - List: All 6 Tier 1 commands enhanced
  - List: All 10 Tier 2 commands enhanced
  - Note: No breaking changes, only help text improvements

- [ ] **Task 5.1.3**: Create migration guide (optional)
  - File: `docs/CLI_HELP_MIGRATION_GUIDE.md`
  - Content: Before/after examples
  - Audience: Contributors who need to update commands

### 5.2 Communicate Changes (3 tasks)

- [ ] **Task 5.2.1**: Update CLAUDE.md project instructions
  - Section: "CLI Help System" (new)
  - Content: Explain AI-first approach and how to use it
  - Examples: Show AI how to navigate help system

- [ ] **Task 5.2.2**: Create demo video/GIF (optional)
  - Show: `aud --help` before and after
  - Show: `aud explain --help` becoming visible
  - Show: AI ASSISTANT CONTEXT sections

- [ ] **Task 5.2.3**: Prepare announcement
  - Audience: Team, users, AI assistant developers
  - Content: Key improvements, no breaking changes
  - Examples: Show enhanced help for 2-3 commands

---

## Final Verification (teamsop.md Post-Implementation Audit)

- [ ] **Task FINAL.1**: Re-read all modified files
  - Purpose: Confirm correctness, no syntax errors
  - Files: cli.py, all command files, test files
  - Method: Full file read with syntax validation

- [ ] **Task FINAL.2**: Run comprehensive test suite
  - Command: `pytest tests/test_cli_help_ai_first.py -v`
  - Command: `aud --help` (visual inspection)
  - Command: `aud full --help` (visual inspection)

- [ ] **Task FINAL.3**: Measure improvements
  - Metric: Commands visible (before: 33/35, after: 35/35)
  - Metric: Min lines per command (before: 3, after: 50)
  - Metric: Commands with AI CONTEXT (before: 0, after: 35)
  - Metric: Commands with 4+ examples (before: ~60%, after: 100%)

- [ ] **Task FINAL.4**: Create completion report (teamsop.md Template C-4.20)
  - File: `openspec/changes/update-cli-help-ai-first/completion_report.md`
  - Content: Verification phase, root cause, implementation details
  - Content: Edge cases, post-implementation audit, impact assessment

---

## Task Summary

**Total**: 94 tasks
**Phase 0**: 6 tasks (Verification)
**Phase 1**: 24 tasks (Dynamic VerboseGroup)
**Phase 2**: 18 tasks (Documentation Template)
**Phase 3**: 46 tasks (Command Enhancements)
  - Tier 1: 14 tasks (Critical)
  - Tier 2: 20 tasks (Needs Improvement)
  - Tier 3: 12 tasks (Good Commands)
**Phase 4**: 6 tasks (Validation)
**Phase 5**: 6 tasks (Documentation)
**Final**: 4 tasks (Verification)

**Estimated Effort**: 140 hours (19 days single developer, 7 days with 2 developers)

---

## Dependencies & Blockers

**External Dependencies**: None
**Internal Dependencies**:
- Phase 2 depends on Phase 1 (need dynamic VerboseGroup for categorization)
- Phase 3 depends on Phase 2 (need template before enhancements)
- Phase 4 depends on Phase 3 (need all enhancements done before validation)

**Potential Blockers**:
- Merge conflicts with other CLI changes → Coordinate with team
- Testing infrastructure needs update → Set up pytest first
- CI pipeline configuration → May need DevOps assistance

---

## Progress Tracking

**Status**: Not started
**Last Updated**: 2025-10-31
**Next Review**: After Phase 1 completion
**Blockers**: None currently
**Notes**: Awaiting Architect approval to begin implementation
