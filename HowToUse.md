# TheAuditor - Complete Usage Guide

**Version 1.6.4-dev1** | Comprehensive Command Reference & Workflows

> From quick start to advanced analysis - everything you need to master TheAuditor

**Requires Python >=3.14**

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Common Workflows](#common-workflows)
3. [Command Reference (43 Commands)](#command-reference)
4. [Query Language & Patterns](#query-language--patterns)
5. [Output Format & Structure](#output-format--structure)
6. [Advanced Usage](#advanced-usage)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### First-Time Setup

```bash
# Install
pip install theauditor

# Run complete security audit (auto-creates .pf/ directory)
cd C:\Your\Project\Path
aud full

# View summary
cat .pf\readthis\summary.json
```

**Output**:
```
.pf\
├── repo_index.db          # 250-table SQLite database (9 schema domains)
├── manifest.json          # File inventory
├── workset.json          # Changed files
├── raw\                   # Immutable tool output
│   ├── patterns.json
│   ├── taint_analysis.json
│   └── ...
└── readthis\             # AI-optimized (<65KB chunks)
    ├── summary.json
    ├── patterns_chunk01.json
    └── ...
```

### 5-Minute Security Audit

```bash
# Step 1: Run complete audit (includes indexing + all analysis)
aud full

# Or run specific analysis after full audit:
# Step 2: Run security patterns (10-15 seconds)
aud detect-patterns

# Step 3: Run taint analysis (15-30 seconds)
aud taint

# View critical findings
aud query --category security --severity critical
```

---

## Common Workflows

### Workflow 1: Pull Request Security Review

**Scenario**: Check security issues in PR changes only

```bash
# Step 1: Create workset from PR diff
aud workset --diff main..feature-branch

# Step 2: Run security analysis on changed files
aud detect-patterns --file-filter "workset"
aud taint --workset

# Step 3: Query specific concerns
aud query --category security --show-flow

# Step 4: Check impact radius
aud impact --file src\auth.py --line 42
```

**Performance**: 10-100x faster than full scan

### Workflow 2: Refactoring Safety Check

**Scenario**: Ensure refactoring doesn't break dependencies

```bash
# Step 1: Identify what depends on this code
aud query --symbol old_function_name --show-callers

# Step 2: Check impact radius
aud impact --file src\database.py --line 156

# Step 3: Update code
# ... make changes ...

# Step 4: Verify no regressions
aud full  # Includes refactor analysis
aud lint --workset
```

### Workflow 3: Architecture Health Check

**Scenario**: Understand codebase architecture and identify hotspots

```bash
# Step 1: Build dependency graphs
aud graph build

# Step 2: Analyze architecture
aud graph analyze --no-insights

# Step 3: Identify circular dependencies
aud graph query --show-cycles

# Step 4: Find hotspots
aud graph query --hotspots --top 10

# Step 5: Visualize
aud graph viz --view cycles --format svg
```

### Workflow 4: Machine Learning Risk Prediction

**Scenario**: Predict which files will need editing

```bash
# Step 1: Train models on execution history
aud learn --enable-git

# Step 2: Get predictions for current work
aud suggest --topk 20 --print-plan

# Step 3: Validate predictions
# ... work on suggested files ...

# Step 4: Provide feedback for retraining
cat > feedback.json << EOF
{
  "src/auth.py": {"is_risky": true, "will_need_edit": true},
  "src/utils.py": {"is_risky": false, "will_need_edit": false}
}
EOF

aud learn-feedback --feedback feedback.json
```

### Workflow 5: Infrastructure Security Audit

**Scenario**: Check IaC and container security

```bash
# Step 1: Run complete audit (includes infrastructure analysis)
aud full

# Or run specific Docker analysis:
# Step 2: Analyze Docker security
aud docker-analyze --severity high

# Step 3: Check Terraform compliance
aud terraform

# Step 4: Audit AWS CDK constructs
aud cdk analyze

# Step 5: Check GitHub Actions security
aud workflows
```

---

## Command Reference

### Foundation Commands (4)

#### `aud init` **[DEPRECATED]**

**⚠️ DEPRECATION NOTICE**: This command now runs `aud full` for data fidelity.

**Why Deprecated**:
- `aud init` originally ran only 4 setup steps (index, workset, deps, docs)
- Modern analysis requires complete pipeline context (frameworks, graphs, taint, etc.)
- Partial initialization leads to incomplete/incorrect analysis results

**Replacement**: Use `aud full` instead
```bash
# OLD workflow
aud init && aud taint

# NEW workflow
aud full  # Auto-creates .pf/ and runs complete audit
```

**Backward Compatibility**:
- Command still works but redirects to `aud full`
- Prints deprecation warning with 3-second cancellation window
- Update scripts to use `aud full` directly

**Migration Guide**:
```bash
# OLD: Initialization only
aud init --offline

# NEW: Complete audit (auto-initializes)
aud full --offline
```

---

#### `aud index` **[DEPRECATED]**

**⚠️ DEPRECATION NOTICE**: This command now runs `aud full` for data fidelity.

**Why Deprecated**:
- `aud index` only runs Phase 1 (AST indexing ~30-60 seconds)
- Modern analysis requires Phases 2-20 (frameworks, graphs, taint, patterns)
- Running `aud index` alone leads to incomplete analysis context
- Commands like `taint`, `deadcode`, `graph` need full pipeline context

**Replacement**: Use `aud full` instead
```bash
# OLD workflow (incomplete)
aud index && aud taint && aud deadcode

# NEW workflow (complete audit)
aud full  # Includes indexing + all 20 phases
```

**Backward Compatibility**:
- Command still works but redirects to `aud full`
- Prints deprecation warning with 3-second cancellation window
- Performance: ~10-60 minutes (vs ~30 seconds for old index-only)
- This is INTENTIONAL - ensures data fidelity

**Migration Guide**:
```bash
# OLD: Index only
aud index --print-stats

# NEW: Complete audit with stats
aud full

# OLD: Exclude self-testing
aud index --exclude-self

# NEW: Exclude self-testing
aud full --exclude-self

# OLD: CI/CD quick index
aud index --no-archive

# NEW: CI/CD complete audit
aud full --offline --quiet
```

**Note**: The database (250 tables across 9 schema domains) is created via `aud full`
which ensures all phases populate their respective tables correctly
- Medium (20K LOC): ~60 seconds
- Large (100K LOC): ~180 seconds

**Output**: `.pf\repo_index.db` (~180MB typical)

---

#### `aud workset`

**Purpose**: Identify files to analyze based on changes or patterns

**Synopsis**:
```bash
aud workset [OPTIONS]
```

**Options**:
```
--root DIR                    Root directory (default: .)
--db PATH                     SQLite database path
--manifest PATH               Manifest file path
--all                         Include all source files (ignore git diff)
--diff SPEC                   Git diff range (e.g., main..HEAD, HEAD~3..HEAD)
--files FILE [FILE ...]       Explicit file list
--include PATTERN [...]       Include glob patterns
--exclude PATTERN [...]       Exclude glob patterns
--max-depth INT               Maximum dependency depth (default: 3)
--out PATH                    Output workset file path
--print-stats                 Print summary statistics
```

**Use Cases**:
- **PR Review**: Analyze only PR changes + dependencies
- **Incremental Analysis**: 10-100x faster than full scan
- **Targeted Scanning**: Focus on specific components

**Example**:
```bash
# Files changed in last commit
aud workset --diff HEAD~1

# PR changes
aud workset --diff main..feature-branch

# Specific files + dependencies
aud workset --files src\auth.py src\db.py

# All source files (no git diff)
aud workset --all

# Limit dependency depth
aud workset --diff HEAD~1 --max-depth 2
```

**Workset Structure** (`.pf\workset.json`):
```json
{
  "seed_files": ["directly changed files"],
  "expanded_files": ["dependencies and affected files"],
  "total_files": ["complete set for analysis"]
}
```

**Use with other commands**:
```bash
# Analyze workset only
aud lint --workset
aud taint --workset
aud detect-patterns --workset
```

---

#### `aud setup-ai`

**Purpose**: Setup sandboxed tools and vulnerability databases (~500MB)

**Synopsis**:
```bash
aud setup-ai [OPTIONS]
```

**Options**:
```
--target DIR       Target directory (default: .)
```

**Downloads**:
- OSV vulnerability database
- npm audit data
- Linter configurations
- Sandbox runtime

**Example**:
```bash
aud setup-ai --target .
```

---

### Security Analysis Commands (3)

#### `aud detect-patterns`

**Purpose**: Run 200+ security pattern rules across codebase

**Synopsis**:
```bash
aud detect-patterns [OPTIONS]
```

**Options**:
```
--project-path DIR            Root directory (default: .)
--patterns NAME [...]         Pattern categories
--output-json PATH            Custom output JSON path
--file-filter PATTERN         Glob pattern to filter files
--max-rows INT                Maximum rows in table display
--print-stats                 Print summary statistics
--with-ast / --no-ast         Enable AST-based matching (default: true)
--with-frameworks / --no-frameworks  Enable framework detection (default: true)
--exclude-self                Exclude TheAuditor's own files
```

**Pattern Categories**:
- `auth_issues`: JWT, OAuth, session, passwords
- `injection`: SQL, command, XSS, template
- `crypto`: Weak algorithms, ECB mode, insecure random
- `secrets`: Hardcoded keys, passwords, tokens
- `config`: CORS, security headers, debug mode
- `api`: Rate limiting, auth bypass, key exposure
- `pii`: GDPR, CCPA, HIPAA compliance

**Example**:
```bash
# Run all patterns
aud detect-patterns

# Specific category
aud detect-patterns --patterns auth_issues

# Python files only
aud detect-patterns --file-filter "*.py"

# Regex-only (faster)
aud detect-patterns --no-ast

# With statistics
aud detect-patterns --print-stats
```

**Detection Methods**:
1. **Pattern Matching**: Fast regex-based
2. **AST Analysis**: Semantic understanding
3. **Framework Detection**: Django, Flask, React-specific

**Output**: `.pf\raw\patterns.json` + `.pf\readthis\patterns_chunk*.json`

**Finding Format**:
```json
{
  "file": "src/auth.py",
  "line": 42,
  "pattern": "hardcoded_secret",
  "severity": "critical",
  "message": "Hardcoded API key detected",
  "code_snippet": "api_key = 'sk_live_...'",
  "cwe": "CWE-798"
}
```

---

#### `aud taint`

**Purpose**: Detect vulnerabilities via cross-file data flow tracking

**Synopsis**:
```bash
aud taint [OPTIONS]
```

**Options**:
```
--db PATH                   SQLite database path
--output PATH               Output file (default: .pf\raw\taint_analysis.json)
--max-depth INT             Taint propagation depth (default: 5)
--json                      Output raw JSON instead of formatted report
--verbose                   Show detailed path information
--severity LEVEL            Filter by severity (all/critical/high/medium/low)
--rules / --no-rules        Enable rule-based detection (default: true)
--use-cfg / --no-cfg        Use CFG flow-sensitive analysis (default: true)
--memory / --no-memory      Use in-memory caching (default: true)
--memory-limit INT          Memory limit in MB (auto-detected if not set)
```

**Analysis Pipeline**:
1. Schema Validation (verify database contract)
2. Infrastructure Rules (Docker, Terraform standalone checks)
3. Discovery Rules (populate taint registry with framework patterns)
4. Taint Analysis (trace untrusted data from sources to sinks)
5. Taint-Dependent Rules (advanced security checks using taint results)
6. Findings Consolidation (combine all results with enrichment)

**Detected Vulnerabilities**:
- SQL Injection (4 patterns: format, f-string, concatenation, template literal)
- Command Injection (subprocess.call, os.system, eval, exec)
- Cross-Site Scripting (DOM, Response, Template)
- Path Traversal (open, os.path.join)
- LDAP/NoSQL Injection

**Example**:
```bash
# Full analysis
aud taint

# Critical issues only
aud taint --severity critical

# Verbose output
aud taint --json --verbose

# Disable CFG (not recommended)
aud taint --no-cfg

# Workset mode
aud taint --workset
```

**Output**:
```json
{
  "success": true,
  "taint_paths": [
    {
      "source": {"file": "app.py", "line": 10, "name": "user_input"},
      "sink": {"file": "db.py", "line": 45, "category": "sql"},
      "path": [
        {"file": "api.py", "line": 23, "function": "process_query"},
        {"file": "db.py", "line": 35, "function": "execute_query"}
      ],
      "vulnerability_type": "SQL Injection",
      "severity": "CRITICAL",
      "confidence": "HIGH"
    }
  ],
  "summary": {
    "critical_count": 3,
    "high_count": 8,
    "medium_count": 15,
    "risk_level": "CRITICAL"
  }
}
```

**Exit Codes**:
- 0: No critical or high vulnerabilities
- 1: High severity vulnerabilities found
- 2: Critical vulnerabilities found

---

#### `aud docker-analyze`

**Purpose**: Analyze Docker security issues

**Synopsis**:
```bash
aud docker-analyze [OPTIONS]
```

**Options**:
```
--severity LEVEL            Filter by severity (critical/high/medium/low)
--check-vulns               Enable vulnerability scanning
```

**Checks**:
- Base image vulnerabilities
- Insecure environment variables
- Missing healthchecks
- Root user usage
- Exposed secrets
- Privileged containers

**Example**:
```bash
# Basic analysis
aud docker-analyze

# Critical issues only
aud docker-analyze --severity critical

# With vulnerability scanning
aud docker-analyze --check-vulns
```

---

### Dependency & Documentation Commands (2)

#### `aud deps`

**Purpose**: Analyze dependencies for vulnerabilities and updates

**Synopsis**:
```bash
aud deps [OPTIONS]
```

**Options**:
```
--root DIR                    Root directory (default: .)
--check-latest                Check for available updates
--upgrade-all                 YOLO mode - upgrade everything (dangerous)
--offline                     Skip network operations
--out PATH                    Output JSON file
--print-stats                 Print summary statistics
--vuln-scan                   Scan for known vulnerabilities
```

**Supported Package Managers**:
- **Python**: pip, Poetry, setuptools
- **JavaScript/TypeScript**: npm, yarn
- **Format Files**: `package.json`, `pyproject.toml`, `requirements.txt`, `setup.py`

**Vulnerability Scanning**:
- Runs 2 native tools: `npm audit` and `OSV-Scanner`
- Cross-references findings for validation
- Reports CVEs with severity levels
- Exit code 2 for critical vulnerabilities
- Requires `aud setup-ai --target .` first

**Example**:
```bash
# Basic dependency inventory
aud deps

# Check for outdated packages
aud deps --check-latest

# Security vulnerability scan
aud deps --vuln-scan

# Offline mode (use local databases)
aud deps --offline

# DANGEROUS: Upgrade everything
aud deps --upgrade-all
```

**Output**: `.pf\raw\deps.json`, `.pf\raw\deps_latest.json`, `.pf\raw\vulnerabilities.json`

---

#### `aud docs`

**Purpose**: Manage project dependency documentation

**Sub-commands**:
```bash
aud docs fetch              # Download documentation for dependencies
aud docs summarize          # Create AI-optimized doc capsules (<65KB each)
aud docs list               # List available documentation
aud docs view PACKAGE       # View specific package docs
```

**Example**:
```bash
# Fetch all dependency docs
aud docs fetch

# Create AI summaries
aud docs summarize

# List available docs
aud docs list

# View requests library docs
aud docs view requests
```

---

### Code Quality Commands (2)

#### `aud lint`

**Purpose**: Run code quality checks with industry-standard linters

**Synopsis**:
```bash
aud lint [OPTIONS]
```

**Options**:
```
--root DIR                    Root directory (default: .)
--workset                     Use workset mode (lint only .pf\workset.json)
--workset-path PATH           Custom workset path
--manifest PATH               Manifest file path
--timeout INT                 Timeout in seconds per linter (default: 300)
--print-plan                  Preview what would run without executing
```

**Supported Linters** (Auto-Detected):
- **Python**: ruff, mypy, black, pylint, bandit
- **JavaScript/TypeScript**: eslint, prettier, tsc
- **Go**: golangci-lint, go vet
- **Docker**: hadolint

**Normalization**: All linter outputs normalized to unified format:
```json
{
  "file": "src/auth.py",
  "line": 42,
  "column": 10,
  "severity": "error|warning|info",
  "rule": "undefined-var",
  "message": "Variable 'user' is not defined",
  "tool": "eslint"
}
```

**Example**:
```bash
# Lint entire codebase
aud lint

# Lint only changed files
aud lint --workset

# Preview without executing
aud lint --print-plan

# Increase timeout for large projects
aud lint --timeout 600
```

**Output**: `.pf\raw\lint.json` + findings written to `findings_consolidated`

---

#### `aud cfg`

**Purpose**: Analyze function complexity through Control Flow Graphs

**Sub-commands**:

##### `aud cfg analyze`

**Synopsis**:
```bash
aud cfg analyze [OPTIONS]
```

**Options**:
```
--db PATH                       Repository database
--file PATH                     Analyze specific file only
--function NAME                 Analyze specific function only
--complexity-threshold INT      Complexity threshold (default: 10)
--output PATH                   Output JSON file
--find-dead-code                Find unreachable code blocks
--workset                       Analyze workset files only
```

**McCabe Complexity Guidelines**:
- 1-10: Simple, low risk
- 11-20: Moderate complexity, medium risk
- 21-50: Complex, high risk, needs refactoring
- 50+: Untestable, very high risk

**Example**:
```bash
# Find complex functions
aud cfg analyze --complexity-threshold 15

# Detect unreachable code
aud cfg analyze --find-dead-code

# Analyze specific file
aud cfg analyze --file src\auth.py

# Workset mode
aud cfg analyze --workset
```

##### `aud cfg viz`

**Synopsis**:
```bash
aud cfg viz [OPTIONS]
```

**Options**:
```
--db PATH                   Repository database
--file PATH                 File containing function
--function NAME             Function name to visualize
--output PATH               Output file path
--format dot|svg|png        Output format (default: svg)
--show-statements           Include statements in blocks
--highlight-paths           Highlight execution paths
```

**Example**:
```bash
# Visualize login function
aud cfg viz --file src\auth.py --function login

# SVG output
aud cfg viz --file src\auth.py --function login --format svg

# With statements
aud cfg viz --file src\auth.py --function login --show-statements
```

---

### Graph Analysis Commands (1 group)

#### `aud graph`

**Sub-commands**:

##### `aud graph build`

**Purpose**: Build dependency and call graphs

**Synopsis**:
```bash
aud graph build [OPTIONS]
```

**Options**:
```
--root DIR                    Root directory (default: .)
--langs LANG [...]            Languages (python, javascript)
--workset PATH                Limit scope to workset
--batch-size INT              Files per batch (default: 200)
--resume                      Resume from checkpoint
--db PATH                     SQLite database path
--out-json DIR                JSON output directory
```

**Graphs Generated**:
1. **Import Graph**: Module/file dependencies
2. **Call Graph**: Function relationships

**Example**:
```bash
# Build complete graphs
aud graph build

# Python only
aud graph build --langs python

# Resume interrupted build
aud graph build --resume
```

**Output**: `.pf\graphs.db` + `.pf\raw\import_graph.json`, `.pf\raw\call_graph.json`

---

##### `aud graph build-dfg`

**Purpose**: Build data flow graph from assignments and returns

**Synopsis**:
```bash
aud graph build-dfg [OPTIONS]
```

**Options**:
```
--root DIR                    Root directory (default: .)
--db PATH                     Graphs database path
--repo-db PATH                Repo index database
```

**Example**:
```bash
aud graph build-dfg
```

---

##### `aud graph analyze`

**Purpose**: Detect cycles, hotspots, and analyze dependencies

**Synopsis**:
```bash
aud graph analyze [OPTIONS]
```

**Options**:
```
--db PATH                   Graphs database path
--out PATH                  Output JSON path
--max-depth INT             Impact traversal depth (default: 3)
--workset PATH              Workset for change impact
--no-insights               Skip interpretive insights
```

**Analysis Results**:
- Circular dependencies (import cycles)
- Architectural hotspots (highly connected files)
- Change impact radius
- Hidden dependencies

**Example**:
```bash
# Full analysis
aud graph analyze

# Without interpretive scoring
aud graph analyze --no-insights

# Change impact for workset
aud graph analyze --workset .pf\workset.json
```

**Output**:
```json
{
  "cycles": [
    {
      "size": 5,
      "nodes": ["auth.py", "db.py", "models.py", "api.py", "utils.py"]
    }
  ],
  "hotspots": [
    {
      "id": "database.py",
      "score": 0.95,
      "in_degree": 47,
      "out_degree": 12,
      "centrality": 0.23
    }
  ],
  "impact": {
    "upstream": ["file1.py", "file2.py"],
    "downstream": ["file3.py"],
    "total_impacted": 3
  }
}
```

---

##### `aud graph query`

**Purpose**: Query graph relationships

**Synopsis**:
```bash
aud graph query [OPTIONS]
```

**Options**:
```
--db PATH                   Graphs database path
--uses MODULE               Find who uses this module
--calls FUNC                Find what this calls
--nearest-path SRC TGT      Find shortest path
--format table|json         Output format (default: table)
```

**Example**:
```bash
# Who depends on database.py?
aud graph query --uses database.py

# What does send_email call?
aud graph query --calls api.send_email

# Path from auth to db
aud graph query --nearest-path auth.py db.py

# JSON output
aud graph query --uses database.py --format json
```

---

##### `aud graph viz`

**Purpose**: Visualize dependency graphs

**Synopsis**:
```bash
aud graph viz [OPTIONS]
```

**Options**:
```
--db PATH                       Graphs database
--graph-type import|call        Graph type (default: import)
--out-dir DIR                   Output directory
--limit-nodes INT               Maximum nodes (default: 500)
--format dot|svg|png|json       Output format (default: svg)
--view full|cycles|hotspots|layers|impact  Visualization mode
--include-analysis              Include cycle/hotspot analysis
--title TEXT                    Graph title
--top-hotspots INT              Top N hotspots (default: 10)
--impact-target NODE            Target node for impact view
--show-self-loops               Include self-referential edges
```

**View Modes**:
- **full**: Complete graph with all nodes/edges
- **cycles**: Only nodes/edges involved in cycles
- **hotspots**: Top N most connected nodes
- **layers**: Architectural layers as subgraphs
- **impact**: Highlight impact radius of changes

**Visual Encoding**:
- **Node Color**: Programming language (Python=blue, JS=yellow)
- **Node Size**: Importance/connectivity
- **Edge Color**: Red for cycles, gray for normal
- **Border Width**: Code churn (thicker = more changes)

**Example**:
```bash
# Visualize import graph
aud graph viz

# Show only cycles
aud graph viz --view cycles

# SVG format
aud graph viz --view hotspots --format svg

# Impact radius
aud graph viz --view impact --impact-target database.py

# PNG output
aud graph viz --format png --out-dir C:\output
```

---

### Impact & Refactoring Commands (2)

#### `aud impact`

**Purpose**: Analyze blast radius of code changes

**Synopsis**:
```bash
aud impact [OPTIONS]
```

**Options**:
```
--file PATH                 Path to file to analyze (required)
--line INT                  Line number of code (required)
--db PATH                   SQLite database path
--json                      Output JSON instead of formatted report
--max-depth INT             Transitive dependency depth (default: 2)
--verbose                   Show detailed dependency information
--trace-to-backend          Trace frontend API calls to backend
```

**Impact Dimensions**:
1. **Upstream**: Who depends on this code?
2. **Downstream**: What does this code depend on?
3. **Transitive**: Multi-hop relationships

**Risk Assessment**:
- Low Impact: < 5 files (safe to change)
- Medium Impact: 5-20 files (review carefully)
- High Impact: > 20 files (extensive testing needed, exit code 1)

**Example**:
```bash
# Analyze function impact
aud impact --file src\auth.py --line 42

# Detailed report
aud impact --file src\auth.py --line 42 --verbose

# JSON output
aud impact --file src\auth.py --line 42 --json

# Cross-stack tracing
aud impact --file frontend\api.js --line 200 --trace-to-backend
```

**Output**:
```json
{
  "target": {
    "symbol": "authenticate_user",
    "file": "auth.py",
    "line": 42
  },
  "impact_summary": {
    "upstream_direct": 15,
    "downstream_direct": 8,
    "total_impact": 23,
    "risk_level": "HIGH"
  },
  "upstream": [
    {"symbol": "login", "file": "routes.py", "line": 100}
  ],
  "downstream": [
    {"symbol": "check_db", "file": "db.py", "line": 50}
  ]
}
```

---

#### `aud refactor`

**Purpose**: Detect incomplete refactorings from database migrations

**Synopsis**:
```bash
aud refactor [OPTIONS]
```

**Options**:
```
--migration-dir DIR         Directory with database migrations
--migration-limit INT       Number of recent migrations (0=all, default: 5)
--file YAML                 Refactor profile YAML spec
--output PATH               Output report file
```

**Workflow**:
1. Parses migrations to find removed/renamed fields
2. Queries repo_index.db for code referencing those items
3. Reports mismatches (code using deleted schema)

**Example**:
```bash
# Last 5 migrations
aud refactor

# All migrations
aud refactor --migration-limit 0

# Custom migration directory
aud refactor --migration-dir db\migrations

# With spec file
aud refactor --file migration_spec.yaml
```

---

### Machine Learning Commands (3)

#### `aud learn`

**Purpose**: Train ML models on execution history

**Synopsis**:
```bash
aud learn [OPTIONS]
```

**Options**:
```
--db-path PATH              Database path
--manifest PATH             Manifest file
--enable-git                Enable git churn features
--model-dir DIR             Model output directory (default: .pf\ml)
--window INT                Journal window size (default: 50)
--seed INT                  Random seed for reproducibility
--feedback PATH             Human feedback JSON
--train-on full|diff|all    Training data type (default: all)
--print-stats               Print training statistics
```

**Models Trained**:
1. **Root Cause Classifier**: Which file caused the failure?
2. **Next Edit Predictor**: Which file will need editing?
3. **Risk Scorer**: Continuous risk score [0, 1]

**Features** (50+ dimensions):
- Graph topology (in/out degree, centrality)
- Security patterns (JWT, SQL, secrets)
- Complexity (cyclomatic, AST depth)
- Git temporal (commits, authors, recency)
- Historical findings (recurring CWEs)

**Example**:
```bash
# Train models
aud learn

# With git analysis
aud learn --enable-git

# With human feedback
aud learn --feedback feedback.json

# Print statistics
aud learn --print-stats
```

**Output**: `.pf\ml\risk_model.pkl`, `.pf\ml\root_cause_model.pkl`, `.pf\ml\feature_stats.json`

---

#### `aud suggest`

**Purpose**: Generate ML risk predictions

**Synopsis**:
```bash
aud suggest [OPTIONS]
```

**Options**:
```
--db-path PATH              Database path
--manifest PATH             Manifest file
--workset PATH              Workset file
--model-dir DIR             Model directory (default: .pf\ml)
--topk INT                  Top K files (default: 10)
--out PATH                  Output file
--print-plan                Print to console
```

**Example**:
```bash
# Top 10 risky files
aud suggest --topk 10

# Verbose output
aud suggest --topk 20 --print-plan

# Save to file
aud suggest --topk 10 --out predictions.json
```

**Output**:
```json
{
  "suggestions": [
    {
      "file": "auth.py",
      "risk_score": 0.87,
      "likely_root_causes": ["high_complexity", "many_changes"],
      "will_need_edit_prob": 0.92
    }
  ]
}
```

---

#### `aud learn-feedback`

**Purpose**: Retrain models with human feedback

**Synopsis**:
```bash
aud learn-feedback --feedback PATH
```

**Feedback Format**:
```json
{
  "path/to/file.py": {
    "is_risky": true,
    "is_root_cause": false,
    "will_need_edit": true
  }
}
```

**Example**:
```bash
aud learn-feedback --feedback feedback.json
```

---

### Planning System Commands (1 group)

#### `aud planning`

**Sub-commands**:

##### `aud planning init`

**Purpose**: Create new plan

**Synopsis**:
```bash
aud planning init [OPTIONS]
```

**Options**:
```
--name TEXT                 Plan name (required)
--description TEXT          Plan description
```

**Example**:
```bash
aud planning init --name "Auth0 Migration" --description "Migrate from Auth0 to AWS Cognito"
```

---

##### `aud planning show`

**Purpose**: Display plan status

**Synopsis**:
```bash
aud planning show [OPTIONS]
```

**Options**:
```
--plan-id INT               Plan ID (shows all if omitted)
--tasks                     Show task details
--specs                     Show verification specs
--snapshots                 Show checkpoint history
```

**Example**:
```bash
# Show all plans
aud planning show

# Show specific plan with tasks
aud planning show --plan-id 1 --tasks
```

---

##### `aud planning add-task`

**Purpose**: Add task with verification spec

**Synopsis**:
```bash
aud planning add-task PLAN_ID [OPTIONS]
```

**Options**:
```
--title TEXT                Task title (required)
--description TEXT          Task description
--spec-file PATH            RefactorProfile YAML spec
```

**Example**:
```bash
# Add task
aud planning add-task 1 --title "Migrate routes"

# With verification spec
aud planning add-task 1 --title "Migrate routes" --spec-file jwt_migration.yaml
```

---

##### `aud planning verify-task`

**Purpose**: Run spec against indexed code

**Synopsis**:
```bash
aud planning verify-task PLAN_ID TASK_ID [OPTIONS]
```

**Options**:
```
--verbose                   Show detailed output
```

**Example**:
```bash
# Verify task
aud planning verify-task 1 1

# Verbose output
aud planning verify-task 1 1 --verbose
```

---

##### `aud planning update-task`

**Purpose**: Change task status

**Synopsis**:
```bash
aud planning update-task PLAN_ID TASK_ID [OPTIONS]
```

**Options**:
```
--status STATUS             Status (pending/in_progress/completed/blocked)
--notes TEXT                Update notes
```

**Example**:
```bash
# Mark in progress
aud planning update-task 1 1 --status in_progress

# Mark completed
aud planning update-task 1 1 --status completed --notes "All tests passing"
```

---

##### `aud planning checkpoint`

**Purpose**: Create checkpoint (save current state)

**Synopsis**:
```bash
aud planning checkpoint PLAN_ID TASK_ID [OPTIONS]
```

**Options**:
```
--message TEXT              Checkpoint message
```

**Example**:
```bash
aud planning checkpoint 1 1 --message "Migrated 5 routes"
```

---

##### `aud planning archive`

**Purpose**: Create snapshot and mark plan complete

**Synopsis**:
```bash
aud planning archive PLAN_ID [OPTIONS]
```

**Options**:
```
--notes TEXT                Archival notes
```

**Example**:
```bash
aud planning archive 1 --notes "Deployed to production"
```

---

##### `aud planning rewind`

**Purpose**: Show git rollback commands to checkpoint

**Synopsis**:
```bash
aud planning rewind PLAN_ID TASK_ID [OPTIONS]
```

**Options**:
```
--to INT                    Checkpoint sequence number
```

**Example**:
```bash
# Show commands to rewind to checkpoint 2
aud planning rewind 1 1 --to 2
```

---

### Correlation & Reporting Commands (3)

#### `aud fce`

**Purpose**: Factual Correlation Engine - cross-reference findings

**Synopsis**:
```bash
aud fce [OPTIONS]
```

**Options**:
```
--root DIR                  Root directory (default: .)
--capsules DIR              Capsules directory
--manifest PATH             Manifest file
--workset PATH              Workset file
--timeout INT               Timeout in seconds (default: 300)
--print-plan                Preview without running
```

**Correlation Rules** (30+ patterns):
- Authentication & Authorization combinations
- Injection attack patterns
- Data exposure scenarios
- Infrastructure misconfigurations
- Code quality impact on security

**Example Correlations**:
```
IF: Debug mode enabled + Exposes secrets
THEN: Severity escalated to CRITICAL

IF: User input + SQL query + No validation
THEN: SQL injection vulnerability
```

**Example**:
```bash
# Run FCE
aud fce

# Preview correlations
aud fce --print-plan

# Custom timeout
aud fce --timeout 600
```

**Output**: `.pf\raw\fce.json`, `.pf\raw\fce_failures.json`

---

#### `aud report`

**Purpose**: Generate consolidated audit report

**Synopsis**:
```bash
aud report [OPTIONS]
```

**Options**:
```
--manifest PATH             Manifest file path
--db PATH                   Database path
--workset PATH              Workset file path
--capsules DIR              Capsules directory
--run-report PATH           Run report file
--journal PATH              Journal file
--fce PATH                  FCE file
--ast PATH                  AST proofs file
--ml PATH                   ML suggestions file
--patch PATH                Patch diff file
--out-dir DIR               Output directory (default: .pf\readthis)
--max-snippet-lines INT     Max lines per snippet
--max-snippet-chars INT     Max chars per line
--print-stats               Print statistics
```

**Output Structure**:
```
.pf\readthis\
├── summary.json           # Executive summary
├── patterns_chunk01.json  # Security patterns
├── taint_chunk01.json     # Taint findings
├── terraform_chunk01.json # Infrastructure
└── *_chunk*.json          # Other findings (<65KB each)
```

**Chunking Strategy**:
- Each file split into <65KB chunks
- Maximum 3 chunks per analysis type
- Designed for LLM context windows

**Example**:
```bash
# Generate report
aud report

# Custom output directory
aud report --out-dir C:\reports

# With statistics
aud report --print-stats
```

---

### Query & Utilities Commands (6)

#### `aud query`

**Purpose**: Query code relationships from indexed database

**Synopsis**:
```bash
aud query [OPTIONS]
```

**Options**:
```
--symbol NAME               Query symbol by name
--file PATH                 Query file by path
--api ROUTE                 Query API endpoint
--component NAME            Query React/Vue component
--variable NAME             Query variable
--pattern PATTERN           Search by pattern (% wildcards)
--category CATEGORY         Search by category
--search TERM               Cross-table search
--show-callers              Show who calls this
--show-callees              Show what this calls
--show-dependencies         Show what imports
--show-dependents           Show who imports
--show-tree                 Component hierarchy
--show-hooks                React hooks
--show-data-deps            Data dependencies
--show-flow                 Variable flow
--show-taint-flow           Cross-function taint
--show-api-coverage         API security coverage
--type-filter TYPE          Filter by type (function/class/variable)
--depth INT                 Traversal depth (default: 1)
--format text|json|tree     Output format (default: text)
--save PATH                 Save to file
```

**Token Savings**:
- Traditional: Read 10+ files, guess relationships
- Query approach: Single SQL query returns exact answer
- Saves 5,000-10,000 tokens per refactoring iteration
- 100% accuracy vs ~60% from file guessing

**Example**:
```bash
# Find function
aud query --symbol authenticate

# Show callers
aud query --symbol authenticate --show-callers

# API dependencies
aud query --api "/users" --show-dependencies

# Transitive dependencies
aud query --symbol db --depth 3 --format json

# Pattern match
aud query --pattern "auth%" --format tree

# Variable flow
aud query --variable user_input --show-flow

# Save to file
aud query --symbol authenticate --save results.json
```

---

#### `aud context`

**Purpose**: Query symbol context (alias for `aud query`)

**Example**:
```bash
aud context --symbol authenticate
```

---

#### `aud explain`

**Purpose**: Explain TheAuditor concepts and terminology

**Synopsis**:
```bash
aud explain [CONCEPT] [OPTIONS]
```

**Options**:
```
--list                      List all available concepts
```

**Available Concepts**:
- `taint`: Taint analysis and data flow
- `workset`: Focused file analysis
- `fce`: Factual Correlation Engine
- `cfg`: Control Flow Graphs
- `impact`: Impact radius analysis
- `pipeline`: Execution pipeline stages
- `severity`: Finding severity levels
- `patterns`: Pattern detection system
- `insights`: Interpretation layer

**Example**:
```bash
# Explain taint analysis
aud explain taint

# List all concepts
aud explain --list
```

---

#### `aud structure`

**Purpose**: Generate project structure tree

**Synopsis**:
```bash
aud structure [OPTIONS]
```

**Options**:
```
--max-depth INT             Directory depth limit
--output PATH               Output file path
```

**Example**:
```bash
# Generate structure
aud structure

# Limit depth
aud structure --max-depth 3

# Save to file
aud structure --output structure.json
```

---

#### `aud detect-frameworks`

**Purpose**: Detect frameworks used in project

**Synopsis**:
```bash
aud detect-frameworks [OPTIONS]
```

**Example**:
```bash
aud detect-frameworks
```

**Output**:
```json
{
  "frameworks": ["Django", "PostgreSQL", "React", "TypeScript"]
}
```

---

#### `aud rules`

**Purpose**: List all available rules

**Synopsis**:
```bash
aud rules [OPTIONS]
```

**Options**:
```
--category CATEGORY         Filter by category
--verbose                   Show rule details
```

**Example**:
```bash
# List all rules
aud rules

# Security rules only
aud rules --category security

# Detailed output
aud rules --verbose
```

---

### Infrastructure Analysis Commands (3)

#### `aud cdk analyze`

**Purpose**: AWS CDK security analysis

**Synopsis**:
```bash
aud cdk analyze [OPTIONS]
```

**Options**:
```
--root DIR                  Custom root (default: .)
--severity LEVEL            Filter by severity (critical/high/medium/low)
--format json|text          Output format (default: text)
--output PATH               Save to file
```

**Checks** (4 rules):
1. **S3 Bucket Security**: Public read access, missing block_public_access
2. **Security Group Permissions**: Ingress from 0.0.0.0/0, allow_all_outbound
3. **Encryption at Rest**: RDS storage_encrypted, EBS encrypted, DynamoDB encryption
4. **IAM Wildcards**: Actions='*', Resources='*', AdministratorAccess

**Example**:
```bash
# Analyze CDK
aud cdk analyze

# Critical issues only
aud cdk analyze --severity critical

# JSON output
aud cdk analyze --format json --output cdk_findings.json
```

---

#### `aud terraform`

**Purpose**: Terraform/IaC security analysis

**Synopsis**:
```bash
aud terraform [OPTIONS]
```

**Example**:
```bash
aud terraform
```

---

#### `aud workflows`

**Purpose**: GitHub Actions workflow security

**Synopsis**:
```bash
aud workflows [OPTIONS]
```

**Checks** (6 rules):
1. **Untrusted Checkout**: Code from PR checked out unsafely
2. **PR Injection**: User input in run commands
3. **Unpinned Actions**: Actions without commit SHA
4. **Excessive Permissions**: Broad GITHUB_TOKEN scopes
5. **Artifact Poisoning**: Artifacts uploaded/downloaded unsafely
6. **External Reusable Workflows**: Third-party workflows

**Example**:
```bash
aud workflows
```

---

### Complete Pipeline Command (1)

#### `aud full`

**Purpose**: Run complete security audit pipeline

**Synopsis**:
```bash
aud full [OPTIONS]
```

**Options**:
```
--offline                   Skip network operations
--workset                   Use workset mode
--skip-tests                Skip test execution
--skip-ml                   Skip ML suggestions
--timeout INT               Global timeout in seconds
```

**Execution Pipeline**:
```
Stage 1: Foundation (Sequential)
  ├─ Repository indexing (internal)
  └─ Workset creation (internal)

Stage 2: Analysis Preparation (Sequential)
  ├─ aud graph build
  └─ aud cfg analyze

Stage 3: Heavy Analysis (3 Parallel Tracks)
  ├─ Track A: aud taint (subprocess, isolated)
  ├─ Track B: aud lint + aud detect-patterns + aud graph analyze
  └─ Track C: aud deps + aud docs (network I/O, skippable with --offline)

Stage 4: Aggregation (Sequential)
  ├─ aud fce
  └─ aud report
```

**Performance**:
- Small project (<5K LOC): ~2 minutes
- Medium project (20K LOC): ~10 minutes
- Large monorepo (100K+ LOC): ~30-60 minutes

**Example**:
```bash
# Complete audit
aud full

# Offline mode (no network)
aud full --offline

# Workset mode (changed files only)
aud full --workset

# Skip ML
aud full --skip-ml
```

**Exit Codes**:
- 0: Success, no critical issues
- 1: High severity findings
- 2: Critical vulnerabilities
- 3: Analysis incomplete/failed

---

## Query Language & Patterns

### Database Queries

**Direct SQL** (advanced users):
```bash
# Use sqlite3 directly
cd .pf
sqlite3 repo_index.db

# Find all functions
SELECT name, file_path, line FROM symbols WHERE type='function';

# Find SQL injection patterns
SELECT fca.file_path, fca.line, fca.arg_expr
FROM function_call_args fca
WHERE fca.callee_function LIKE '%execute%'
AND fca.arg_expr LIKE '%f"%';

# Find complex functions
SELECT file, function_name, complexity
FROM findings_consolidated
WHERE tool='cfg-analysis' AND rule='HIGH_CYCLOMATIC_COMPLEXITY'
ORDER BY CAST(JSON_EXTRACT(details_json, '$.complexity') AS INTEGER) DESC;
```

### Pattern Matching

**Glob patterns** (workset, file-filter):
```bash
# Python files
*.py

# All files in directory
src/**/*

# Multiple extensions
*.{js,ts,jsx,tsx}
```

**SQL wildcards** (query):
```bash
# Starts with
auth%

# Contains
%user%

# Single character
auth_?
```

---

## Output Format & Structure

### Directory Structure

```
C:\Your\Project\
├── .pf\                              # TheAuditor working directory
│   ├── repo_index.db                 # 250-table SQLite (~180MB)
│   ├── graphs.db                     # Graph structures (~130MB, optional)
│   ├── planning.db                   # Planning system (separate)
│   ├── manifest.json                 # File inventory
│   ├── workset.json                  # Changed files
│   ├── config.json                   # Runtime configuration
│   ├── .ast_cache\                   # Cached AST trees
│   ├── archive\                      # Previous versions
│   ├── history\                      # Archived results
│   ├── ml\                           # ML models
│   │   ├── risk_model.pkl
│   │   ├── root_cause_model.pkl
│   │   └── feature_stats.json
│   ├── raw\                          # Immutable tool output
│   │   ├── patterns.json
│   │   ├── taint_analysis.json
│   │   ├── lint.json
│   │   ├── deps.json
│   │   ├── graph_analysis.json
│   │   ├── fce.json
│   │   └── ...
│   └── readthis\                     # AI-optimized chunks (<65KB)
│       ├── summary.json
│       ├── patterns_chunk01.json
│       ├── taint_chunk01.json
│       └── ...
```

### JSON Output Format

**Summary** (`.pf\readthis\summary.json`):
```json
{
  "project": {
    "name": "MyProject",
    "total_files": 150,
    "total_loc": 25000,
    "languages": ["Python", "JavaScript"]
  },
  "summary": {
    "critical_count": 3,
    "high_count": 12,
    "medium_count": 45,
    "low_count": 100,
    "total_findings": 160,
    "risk_level": "CRITICAL"
  },
  "categories": {
    "security": 35,
    "quality": 80,
    "performance": 25,
    "maintainability": 20
  },
  "top_issues": [
    {
      "file": "src/auth.py",
      "line": 42,
      "severity": "critical",
      "message": "SQL injection via f-string",
      "category": "security",
      "cwe": "CWE-89"
    }
  ]
}
```

**Findings** (`.pf\readthis\patterns_chunk01.json`):
```json
{
  "findings": [
    {
      "file": "src/auth.py",
      "line": 42,
      "column": 10,
      "rule_name": "sql-injection",
      "severity": "critical",
      "confidence": "high",
      "category": "security",
      "cwe_id": "CWE-89",
      "message": "SQL injection via f-string concatenation",
      "code_snippet": "cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")",
      "remediation": "Use parameterized queries with placeholders",
      "references": [
        "https://owasp.org/www-community/attacks/SQL_Injection"
      ]
    }
  ],
  "metadata": {
    "chunk": 1,
    "total_chunks": 2,
    "chunk_size_kb": 63.5
  }
}
```

---

## Advanced Usage

### Custom Configuration

**`.pf\config.json`**:
```json
{
  "paths": {
    "db": ".pf/repo_index.db",
    "graphs_db": ".pf/graphs.db",
    "manifest": ".pf/manifest.json",
    "workset": ".pf/workset.json"
  },
  "limits": {
    "max_file_size": 2097152,
    "max_chunk_size": 65536,
    "batch_size": 5000
  },
  "timeouts": {
    "lint_timeout": 300,
    "analysis_timeout": 1800
  },
  "report": {
    "max_rows": 1000,
    "max_snippet_lines": 5,
    "max_snippet_chars": 200
  }
}
```

### Environment Variables

```bash
# Configuration overrides
set THEAUDITOR_LIMITS_MAX_FILE_SIZE=4194304
set THEAUDITOR_TIMEOUTS_ANALYSIS=3600
set THEAUDITOR_PATHS_DB=C:\custom\database.db

# Debug logging
set THEAUDITOR_DEBUG=1
set THEAUDITOR_TAINT_DEBUG=1
set THEAUDITOR_CDK_DEBUG=1
```

### Scripting

**PowerShell**:
```powershell
# Audit loop
$projects = @("C:\project1", "C:\project2", "C:\project3")
foreach ($proj in $projects) {
    cd $proj
    aud full --offline
    if ($LASTEXITCODE -eq 2) {
        Write-Host "CRITICAL vulnerabilities in $proj"
    }
}
```

**Python**:
```python
import subprocess
import json

# Run audit
result = subprocess.run(['aud', 'full', '--workset'], capture_output=True)

# Parse findings
with open('.pf/readthis/summary.json') as f:
    summary = json.load(f)

if summary['summary']['critical_count'] > 0:
    print(f"CRITICAL: {summary['summary']['critical_count']} issues found")
    exit(2)
```

---

## Troubleshooting

### Common Issues

#### "Schema mismatch" error
```bash
# Solution: Regenerate database
aud full --exclude-self
```

#### Out of memory
```bash
# Solution: Reduce batch size
set THEAUDITOR_LIMITS_BATCH_SIZE=100
aud full
```

#### Slow indexing
```bash
# Solution: Configure exclusions in .auditorconfig before running aud full
# Edit .auditorconfig to add:
#   exclude_patterns = ["tests/", "node_modules/", "__pycache__/"]
aud full
```

#### Windows path issues
```bash
# Solution: Use absolute paths with backslashes
cd C:\Users\YourName\Desktop\TheAuditor
aud index --root C:\Users\YourName\Desktop\TheAuditor
```

#### UTF-8 encoding errors (Windows)
```bash
# Solution: Set console to UTF-8
chcp 65001
aud full
```

#### Taint analysis timeout
```bash
# Solution: Increase timeout or disable CFG
aud taint --timeout 600
# or
aud taint --no-cfg
```

#### Graph build interrupted
```bash
# Solution: Resume from checkpoint
aud graph build --resume
```

### Debug Logging

```bash
# Enable debug logging
set THEAUDITOR_DEBUG=1
aud full

# Taint analysis debug
set THEAUDITOR_TAINT_DEBUG=1
aud taint

# CDK analysis debug
set THEAUDITOR_CDK_DEBUG=1
aud cdk analyze
```

### Performance Optimization

**For large codebases**:
```bash
# 1. Exclude unnecessary files
aud index --exclude-patterns "tests/" "docs/" "node_modules/" ".venv/" "__pycache__/"

# 2. Use workset mode
aud workset --diff main..HEAD
aud full --workset

# 3. Increase memory limit
set THEAUDITOR_LIMITS_MEMORY=8192
aud full

# 4. Skip ML if not needed
aud full --skip-ml

# 5. Increase timeouts
set THEAUDITOR_TIMEOUTS_ANALYSIS=3600
aud full
```

### Validation

```bash
# Verify database schema
cd .pf
sqlite3 repo_index.db "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"

# Check findings count
sqlite3 repo_index.db "SELECT COUNT(*) FROM findings_consolidated;"

# Verify graph database
sqlite3 graphs.db "SELECT COUNT(*) FROM nodes;"
```

---

## Exit Codes Reference

| Code | Meaning | Triggered By |
|------|---------|--------------|
| 0 | Success, no critical issues | All commands (default) |
| 1 | High severity findings | `aud full`, `aud taint`, `aud impact` |
| 2 | Critical vulnerabilities | `aud full`, `aud taint`, `aud deps --vuln-scan` |
| 3 | Analysis incomplete/failed | `aud full`, `aud impact` |

**Usage in CI/CD**:
```bash
# Fail build on critical vulnerabilities
aud full
if [ $? -eq 2 ]; then
    echo "Critical vulnerabilities found - failing build"
    exit 1
fi
```

---

**For comprehensive architecture details, see [Architecture.md](Architecture.md)**

**For development guidelines, see [Contributing.md](Contributing.md)**
