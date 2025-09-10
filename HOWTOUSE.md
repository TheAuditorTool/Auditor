# How to Use TheAuditor

This comprehensive guide covers everything you need to know about setting up, configuring, and using **TheAuditor** for code analysis and security auditing. Whether you're performing a one-time security audit or integrating continuous analysis into your development workflow, this guide will walk you through every step.

---

## Prerequisites

Before installing **TheAuditor**, ensure you have:

- **Python 3.11 or higher** (3.12+ recommended)
- **Git** (for repository operations)
- **Operating System**: Linux, macOS, or Windows with WSL

---

## Installation & Setup

### Understanding the Architecture

TheAuditor uses a **dual-environment** design:
1. **TheAuditor Installation** - The tool itself (installed once, used everywhere)
2. **Project Sandbox** - Created per-project for isolated analysis

### Step 1: Install TheAuditor Tool

**IMPORTANT**: Do NOT create a virtual environment. Use your system Python.

```bash
# Choose a permanent location for TheAuditor (NOT inside your projects)
cd ~/tools  # or C:\tools on Windows, or wherever you keep dev tools

# Clone the repository
git clone https://github.com/TheAuditorTool/Auditor.git
cd TheAuditor

# Install TheAuditor to your system
pip install -e .

# Verify the installation worked
aud --version

# Optional: Install with ML capabilities
# pip install -e ".[ml]"

# For development with all optional dependencies:
# pip install -e ".[all]"  # Includes Insights module
```

**Common Mistakes to Avoid:**
- ❌ Don't create a venv before installing TheAuditor
- ❌ Don't install TheAuditor inside your project directory
- ❌ Don't run `pip install` from your project directory
- ✅ Install TheAuditor ONCE in a tools directory
- ✅ Use TheAuditor to analyze MANY projects

### Step 2: Setup Project for Analysis (MANDATORY)

**Navigate to YOUR PROJECT directory first:**

```bash
# Go to the project you want to analyze (NOT TheAuditor directory!)
cd ~/my-project-to-audit

# Create the sandboxed environment for THIS project
aud setup-claude --target .
```

This command:
- Creates **`.auditor_venv/.theauditor_tools/`** sandbox directory
- Installs **TypeScript compiler** (`tsc`) in isolation
- Installs **ESLint** and related tools
- Updates all tools to latest versions
- Configures the sandbox for TheAuditor's exclusive use

**Why is this required?**
- TheAuditor **NEVER** uses your global or project-installed tools
- Ensures reproducible results across different environments
- Prevents contamination between analysis tools and project dependencies
- **Required for TheAuditor to function at all** - not just for JavaScript/TypeScript analysis

**Expected output:**
```
Step 1: Setting up Python virtual environment...
[OK] Venv already exists: C:\Users\user\Desktop\TheAuditor\.auditor_venv
[OK] TheAuditor already installed in C:\Users\user\Desktop\TheAuditor\.auditor_venv
  Upgrading to ensure latest version...
Installing TheAuditor from C:\Users\user\Desktop\TheAuditor...
[OK] Installed TheAuditor (editable) from C:\Users\user\Desktop\TheAuditor
[OK] Executable available: C:\Users\user\Desktop\TheAuditor\.auditor_venv\Scripts\aud.exe

Installing Python linting tools...
  Checking for latest linter versions...
    [OK] Updated to latest package versions
  Installing linters from pyproject.toml...
    [OK] Python linters installed (ruff, mypy, black, bandit, pylint)

Setting up JavaScript/TypeScript tools in sandboxed environment...
  Creating sandboxed tools directory: C:\Users\user\Desktop\TheAuditor\.auditor_venv\.theauditor_tools
    [OK] ESLint v9 flat config copied to sandbox
  [Track A] Checking for latest tool versions...
  [Track B] Setting up portable Node.js runtime...
    [OK] Node.js runtime already installed at C:\Users\user\Desktop\TheAuditor\.auditor_venv\.theauditor_tools\node-runtime
      [OK] Updated @typescript-eslint/parser: 8.41.0 → ^8.42.0
      [OK] Updated @typescript-eslint/eslint-plugin: 8.41.0 → ^8.42.0
    Updated 2 packages to latest versions
  Installing JS/TS linters using bundled Node.js...
    [OK] JavaScript/TypeScript tools installed in sandbox
    [OK] Tools isolated from project: C:\Users\user\Desktop\TheAuditor\.auditor_venv\.theauditor_tools
    [OK] Using bundled Node.js - no system dependency!
    [OK] ESLint verified at: C:\Users\user\Desktop\TheAuditor\.auditor_venv\.theauditor_tools\node_modules\.bin\eslint.cmd
```

---

## Core Commands & Workflow

### Complete Audit Pipeline

On a medium 20k LOC node/react/vite stack, expect the analysis to take around 30 minutes.
Progress bars for tracks B/C may display inconsistently on PowerShell.

Run a comprehensive audit with multiple analysis phases organized in parallel stages:

```bash
aud full

# Skip network operations (deps, docs) for faster execution
aud full --offline
```

This executes in **parallel stages** for optimal performance:

**Stage 1 - Foundation (Sequential):**
1. **Repository indexing** - Build manifest and symbol database
2. **Framework detection** - Identify technologies in use

**Stage 2 - Concurrent Analysis (3 Parallel Tracks):**
- **Track A (Network I/O):** *(skipped with --offline)*
  3. **Dependency checking** - Scan for vulnerabilities
  4. **Documentation fetching** - Gather project docs
  5. **Documentation summarization** - Create AI-friendly summaries
- **Track B (Code Analysis):**
  6. **Workset creation** - Define analysis scope
  7. **Linting** - Run code quality checks
  8. **Pattern detection** - Apply security rules
- **Track C (Graph Build):**
  9. **Graph building** - Construct dependency graph

**Stage 3 - Final Aggregation (Sequential):**
10. **Graph analysis** - Find architectural issues
11. **Taint analysis** - Track data flow
12. **Factual correlation engine** - Correlate findings across tools with 29 advanced rules
13. **Report generation** - Produce final output
14. **Summary generation** - Create executive summary

**Output**: Complete results in **`.pf/readthis/`** directory

### Offline Mode

When working on the same codebase repeatedly or when network access is limited, use offline mode to skip network operations (dependency checking and documentation fetching):

```bash
# Run full audit without network operations
aud full --offline

# Combine with other flags
aud full --offline --quiet
aud full --offline --exclude-self  # Only meant for dogfooding; in 9/10 projects, --exclude-self will correctly exclude the entire project, producing empty results
```

**Benefits:**
- **Faster execution** - Skips slow network operations
- **Air-gapped operation** - Works without internet access
- **Iterative development** - Perfect for repeated runs during development

**What gets skipped:**
- Dependency vulnerability scanning
- Documentation fetching and summarization
- Latest version checks

**What still runs:**
- All code analysis (indexing, linting, patterns)
- Graph building and analysis
- Taint analysis and FCE
- Report generation

### Incremental Analysis (Workset-based)

Analyze only changed files based on git diff:

```bash
# Create workset from uncommitted changes
aud workset

# Create workset from specific commit range
aud workset --diff "HEAD~3..HEAD"

# Create workset for all files
aud workset --all
```

Then run targeted analysis:
```bash
aud lint --workset
aud detect-patterns --workset
```

### Linting with Auto-fix

Run comprehensive linting across all supported languages:

```bash
# Run linting on workset
aud lint --workset

# Auto-fix issues where possible
aud lint --fix

# Run on all files
aud lint --all
```

Supports:
- **Python**: **Ruff**, **MyPy**, **Black**, **Bandit**, **Pylint**
- **JavaScript/TypeScript**: **ESLint** with TypeScript parser
- **General**: **Prettier** for formatting

### Security Analysis

#### Taint Analysis

Track data flow from **sources** (user input) to **sinks** (database, output):

```bash
aud taint-analyze
```

Detects:
- **SQL injection** vulnerabilities
- **XSS** (Cross-site scripting)
- **Command injection**
- **Path traversal**
- Other injection attacks

#### Pattern Detection

Run pattern-based vulnerability scanning:

```bash
aud detect-patterns
```

Uses **100+ YAML-defined patterns** across multiple categories:

**Security Patterns:**
- Hardcoded secrets and API keys
- Insecure randomness (**Math.random** for security)
- Weak cryptographic algorithms
- Authentication bypasses
- Missing authentication decorators

**Resource Management:**
- Socket, stream, and worker leaks
- File handles not closed properly
- Database connections left open
- Event listeners not removed

**Concurrency Issues:**
- **Race conditions** (check-then-act)
- **Deadlocks** (nested locks, lock ordering)
- Shared state without synchronization
- Unsafe parallel writes

**ORM & Database:**
- **Sequelize** death queries and N+1 patterns
- **Prisma** connection pool exhaustion
- **TypeORM** missing transactions
- Missing database indexes

**Deployment & Infrastructure:**
- **Docker** security misconfigurations
- **nginx** exposed paths and weak SSL
- **docker-compose** privileged containers
- **webpack** source map exposure in production

**Framework-Specific:**
- **Django**, **Flask**, **FastAPI** vulnerabilities
- **React** hooks dependency issues
- **Vue** reactivity problems
- **Angular**, **Next.js**, **Express.js** patterns
- Multi-tenant security violations

### Docker Security Analysis

Analyze Docker images for security misconfigurations and vulnerabilities:

```bash
# Analyze all indexed Docker images
aud docker-analyze

# Filter by severity level
aud docker-analyze --severity critical

# Save results to JSON file
aud docker-analyze --output docker-security.json
```

Detects:
- **Containers running as root** - CIS Docker Benchmark violation
- **Exposed secrets in ENV/ARG** - Hardcoded passwords, API keys, tokens
- **High entropy values** - Potential secrets using Shannon entropy
- **Known secret patterns** - GitHub tokens, AWS keys, Slack tokens

The command requires Docker images to be indexed first (`aud index`). It queries the `repo_index.db` for Docker metadata and performs security analysis.

### Project Structure Report

Generate comprehensive project structure and intelligence reports:

```bash
# Generate default structure report
aud structure

# Specify output location
aud structure --output PROJECT_OVERVIEW.md

# Adjust directory tree depth
aud structure --max-depth 6

# Analyze different root directory
aud structure --root ./src
```

The report includes:
- **Directory tree visualization** - Smart file grouping and critical file(size/loc) highlighting
- **Project statistics** - Total files, LOC, estimated tokens
- **Language distribution** - Percentage breakdown by file type
- **Top 10 largest files** - By token count with percentage of codebase
- **Top 15 critical files** - Identified by naming conventions (auth.py, config.js, etc.)
- **AI context optimization** - Recommendations for reading order and token budget
- **Symbol counts** - Functions, classes, imports from database

Useful for:
- Getting quick project overview
- Understanding codebase structure
- Planning AI assistant interactions
- Identifying critical components
- Token budget management for LLMs

### Impact Analysis

Assess the blast radius of a specific code change:

```bash
# Analyze impact of changes to a specific function
aud impact --file "src/auth/login.py" --line 42

# Analyze impact with depth limit
aud impact --file "src/database.py" --line 100 --depth 3

# Trace frontend to backend dependencies
aud impact --file "frontend/api.ts" --line 50 --trace-to-backend
```

Shows:
- Dependent functions and modules
- Call chain analysis
- Affected test files
- Risk assessment
- Cross-stack impact (frontend → backend tracing)

### Refactoring Analysis

Detect and analyze refactoring issues such as data model changes, API contract mismatches, and incomplete migrations:

```bash
# Analyze impact from a specific model change
aud refactor --file "models/Product.ts" --line 42

# Auto-detect refactoring from database migrations
aud refactor --auto-detect --migration-dir backend/migrations

# Analyze current workset for refactoring issues
aud refactor --workset

# Generate detailed report
aud refactor --auto-detect --output refactor_report.json
```

Detects:
- **Data Model Changes**: Fields moved between tables (e.g., `product.price` → `variant.price`)
- **Foreign Key Changes**: References updated (e.g., `product_id` → `product_variant_id`)
- **API Contract Mismatches**: Frontend expects old structure, backend provides new
- **Missing Updates**: Code still using old field/table names
- **Cross-Stack Inconsistencies**: TypeScript interfaces not matching backend models

The refactor command uses:
- Impact analysis to trace affected files
- Migration file analysis to detect schema changes
- Pattern detection with refactoring-specific rules
- FCE correlation to find related issues
- Risk assessment based on blast radius

### Insights Analysis (Optional)

Run optional interpretive analysis on top of factual audit data:

```bash
# Run all insights modules
aud insights --mode all

# ML-powered insights (requires pip install -e ".[ml]")
aud insights --mode ml --ml-train

# Graph health metrics and recommendations
aud insights --mode graph

# Taint vulnerability scoring
aud insights --mode taint

# Impact analysis insights
aud insights --mode impact

# Generate comprehensive report
aud insights --output insights_report.json

# Train ML model on your codebase patterns
aud insights --mode ml --ml-train --training-data .pf/raw/

# Get ML-powered suggestions
aud insights --mode ml --ml-suggest
```

Modes:
- **ml**: Machine learning predictions and pattern recognition
- **graph**: Health scores, architectural recommendations
- **taint**: Vulnerability severity scoring and classification
- **impact**: Change impact assessment and risk scoring
- **all**: Run all available insights modules

The insights command:
- Reads existing audit data from `.pf/raw/`
- Applies interpretive scoring and classification
- Generates actionable recommendations
- Outputs to `.pf/insights/` for separation from facts
- Provides technical scoring without crossing into semantic interpretation

### Graph Visualization

Generate rich visual intelligence from dependency graphs:

```bash
# Build dependency graphs first
aud graph build

# Basic visualization
aud graph viz

# Show only dependency cycles
aud graph viz --view cycles --include-analysis

# Top 10 hotspots (most connected nodes)
aud graph viz --view hotspots --top-hotspots 10

# Architectural layers visualization
aud graph viz --view layers --format svg

# Impact analysis visualization
aud graph viz --view impact --impact-target "src/auth/login.py"

# Call graph instead of import graph
aud graph viz --graph-type call --view full

# Generate SVG for AI analysis
aud graph viz --format svg --include-analysis --title "System Architecture"

# Custom output location
aud graph viz --out-dir ./architecture/ --format png
```

View Modes:
- **full**: Complete graph with all nodes and edges
- **cycles**: Only nodes/edges involved in dependency cycles (red highlighting)
- **hotspots**: Top N most connected nodes with gradient coloring
- **layers**: Architectural layers as subgraphs with clear hierarchy
- **impact**: Highlight impact radius with color-coded upstream/downstream

Visual Encoding:
- **Node Color**: Programming language (Python=blue, JavaScript=yellow, TypeScript=blue)
- **Node Size**: Importance/connectivity (larger = more dependencies)
- **Edge Color**: Red for cycles, gray for normal dependencies
- **Border Width**: Code churn (thicker = more changes)
- **Node Shape**: Module=box, Function=ellipse, Class=diamond

The graph viz command:
- Generates Graphviz DOT format files
- Optionally creates SVG/PNG images (requires Graphviz installation)
- Supports filtered views for focusing on specific concerns
- Includes analysis data for cycle and hotspot highlighting
- Produces AI-readable SVG output for LLM analysis

### Control Flow Graph Analysis

Analyze function-level control flow complexity and find code quality issues:

```bash
# Analyze all functions for high complexity
aud cfg analyze --complexity-threshold 10

# Find complex functions in specific file
aud cfg analyze --file src/payment.py --complexity-threshold 15

# Find dead code (unreachable blocks)
aud cfg analyze --find-dead-code

# Analyze workset files only
aud cfg analyze --workset --find-dead-code

# Save analysis results
aud cfg analyze --output cfg_analysis.json

# Visualize a specific function's control flow
aud cfg viz --file src/auth.py --function validate_token

# Generate SVG with statements shown
aud cfg viz --file src/api.py --function handle_request --format svg --show-statements

# Highlight execution paths
aud cfg viz --file src/payment.py --function process_payment --highlight-paths
```

Metrics Provided:
- **Cyclomatic Complexity**: Number of independent paths through code (McCabe complexity)
- **Decision Points**: Count of if/else, loops, try/catch blocks
- **Maximum Nesting**: Deepest level of nested control structures
- **Unreachable Code**: Dead code blocks that can never execute
- **Execution Paths**: All possible paths through a function

The CFG commands help identify:
- Functions that are too complex and need refactoring
- Dead code that can be removed
- High-risk functions with many execution paths
- Code quality issues before they become bugs

### Dependency Management

Check for outdated or vulnerable dependencies:

```bash
# Check for latest versions
aud deps --check-latest

# Scan for known vulnerabilities
aud deps --vuln-scan

# Update all dependencies to latest
aud deps --upgrade-all
```

---

## Architecture: Truth Courier vs Insights

### Understanding the Separation of Concerns

TheAuditor implements a strict architectural separation between **factual observation** (Truth Courier modules) and **optional interpretation** (Insights modules). This design ensures the tool remains an objective source of ground truth while offering actionable intelligence when needed.

### The Core Philosophy

TheAuditor doesn't try to understand your business logic or make your AI "smarter." Instead, it solves the real problem: **LLMs lose context and make inconsistent changes across large codebases.**

The workflow:
1. **You tell AI**: "Add JWT auth with CSRF tokens and password complexity"
2. **AI writes code**: Probably inconsistent due to context limits
3. **You run**: `aud full`
4. **TheAuditor reports**: All the inconsistencies and security holes
5. **AI reads the report**: Now sees the complete picture across all files
6. **AI fixes issues**: With full visibility of what's broken
7. **Repeat until clean**

### Truth Courier Modules (Core)

These modules report verifiable facts without judgment:

```python
# What Truth Couriers Report - Just Facts
{
    "taint_analyzer": "Data from req.body flows to res.send at line 45",
    "pattern_detector": "Line 45 matches pattern 'unsanitized-output'",
    "impact_analyzer": "Changing handleRequest() affects 12 downstream functions",
    "graph_analyzer": "Module A imports B, B imports C, C imports A"
}
```

**Key Truth Couriers:**
- **Indexer**: Maps all code symbols and their locations
- **Taint Analyzer**: Traces data flow through the application
- **Impact Analyzer**: Maps dependency chains and change blast radius
- **Graph Analyzer**: Detects cycles and architectural patterns
- **Pattern Detector**: Matches code against security patterns

### Insights Modules (Optional Scoring)

These optional modules add technical scoring and classification:

```python
# What Insights Add - Technical Classifications
{
    "taint/insights": {
        "vulnerability_type": "Cross-Site Scripting",
        "severity": "HIGH"
    },
    "graph/insights": {
        "health_score": 70,
        "recommendation": "Reduce coupling"
    }
}
```

**Installation:**
```bash
# Base installation (Truth Couriers only)
pip install -e .

# With ML insights (optional)
pip install -e ".[ml]"

# Development with all dependencies (not for general users)
# pip install -e ".[all]"
```

### Correlation Rules: Detecting YOUR Patterns

Correlation rules detect when multiple facts indicate an inconsistency in YOUR codebase:

```yaml
# Example: Detecting incomplete refactoring
- name: "PRODUCT_VARIANT_REFACTOR"
  co_occurring_facts:
    - tool: "grep"
      pattern: "ProductVariant.*retail_price"  # Backend changed
    - tool: "grep"
      pattern: "product\\.unit_price"         # Frontend didn't
```

This isn't "understanding" that products have prices. It's detecting that you moved a field from one model to another and some code wasn't updated. Pure consistency checking.

The correlation engine loads rules from `/correlations/rules/`. We provide common patterns, but many are project-specific. You write rules that detect YOUR patterns, YOUR refactorings, YOUR inconsistencies.

### Why This Works

**What doesn't work:**
- Making AI "understand" your business domain
- Adding semantic layers to guess what you mean
- Complex context management systems

**What does work:**
- Accept that AI will make inconsistent changes
- Detect those inconsistencies after the fact
- Give AI the full picture so it can fix them

TheAuditor doesn't try to prevent mistakes. It finds them so they can be fixed.

### Practical Example

```bash
# You ask AI to implement authentication
Human: "Add JWT auth with CSRF protection"

# AI writes code (probably with issues due to context limits)
AI: *implements auth across 15 files*

# You audit it
$ aud full

# TheAuditor finds issues
- "JWT secret hardcoded at auth.js:47"
- "CSRF token generated but never validated"
- "Auth middleware missing on /api/admin/*"

# You can also check impact of changes
$ aud impact --file "auth.js" --line 47
# Shows: "Changing this affects 23 files, 47 functions"

# AI reads the audit and can now see ALL issues
AI: *reads .pf/readthis/*
AI: "I see 5 security issues across auth flow. Fixing..."

# AI fixes with complete visibility
AI: *fixes all issues because it can see the full picture*
```

### Key Points

1. **No Business Logic Understanding**: TheAuditor doesn't need to know what your app does
2. **Just Consistency Checking**: It finds where your code doesn't match itself
3. **Facts, Not Opinions**: Reports what IS, not what SHOULD BE
4. **Complete Dependency Tracing**: Impact analyzer shows exactly what's affected by changes
5. **AI + Audit Loop**: Write → Audit → Fix → Repeat until clean

This is why TheAuditor works where semantic understanding fails - it's not trying to read your mind, just verify your code's consistency.

---

## Understanding the Output

### Directory Structure

After running analyses, results are organized in **`.pf/`**:

```
.pf/
├── raw/                    # Raw, unmodified tool outputs (Truth Couriers)
│   ├── linting.json       # Raw linter results
│   ├── patterns.json      # Pattern detection findings
│   ├── taint_analysis.json # Taint analysis results
│   ├── graph.json         # Dependency graph data
│   └── graph_analysis.json # Graph analysis (cycles, hotspots)
│
├── insights/              # Optional interpretive analysis (Insights modules)
│   ├── ml_suggestions.json # ML predictions and patterns
│   ├── taint_insights.json # Vulnerability severity scoring
│   └── graph_insights.json # Health scores and recommendations
│
├── readthis/              # AI-consumable chunks
│   ├── manifest.md        # Repository overview
│   ├── patterns_001.md    # Chunked findings (65KB max)
│   ├── patterns_002.md    
│   ├── taint_001.md       # Chunked taint results
│   ├── tickets_001.md     # Actionable issue tickets
│   └── summary.md         # Executive summary
│
├── graphs/                # Graph visualizations
│   ├── import_graph.dot   # Dependency graph DOT file
│   ├── import_graph_cycles.dot # Cycles-only view
│   └── import_graph.svg   # SVG visualization (if generated)
│
├── pipeline.log           # Complete execution log
├── error.log             # Error details (if failures occur)
├── findings.json         # Consolidated findings
├── risk_scores.json      # Risk analysis results
└── report.md             # Human-readable report
```

### Key Output Files

#### `.pf/raw/`
Contains **unmodified outputs** from each tool. These files preserve the exact format and data from linters, scanners, and analyzers. **Never modified** after creation. This is the source of ground truth.

#### `.pf/insights/`
Contains **optional interpretive analysis** from Insights modules. These files add technical scoring and classification on top of raw data. Only created when insights commands are run.

#### `.pf/graphs/`
Contains **graph visualizations** in DOT and image formats. Generated by `aud graph viz` command with various view modes for focusing on specific concerns.

#### `.pf/readthis/`
Contains processed, **chunked data optimized for AI consumption**:
- Each file is under **65KB** by default (configurable via `THEAUDITOR_LIMITS_MAX_CHUNK_SIZE`)
- Maximum 3 chunks per file by default (configurable via `THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE`)
- Structured with clear headers and sections
- Includes context, evidence, and suggested fixes
- Ready for direct consumption by **Claude**, **GPT-4**, etc.

#### `.pf/pipeline.log`
Complete execution log showing:
- Each phase's **execution time**
- **Success/failure** status
- Key statistics and findings
- Error messages if any

#### `.pf/error.log`
Created only when errors occur. Contains:
- Full **stack traces**
- Detailed error messages
- Phase-specific failure information
- Debugging information

---

## Advanced Usage

### Custom Pattern Rules

Create custom detection patterns in **`.pf/patterns/`**:

```yaml
# .pf/patterns/custom_auth.yaml
name: weak_password_check
severity: high
category: security
pattern: 'password\s*==\s*["\']'
description: "Hardcoded password comparison"
test_template: |
  def test_weak_password():
      assert password != "admin"
```

### ML-Powered Suggestions

Train models on your codebase patterns:

```bash
# Initial training
aud learn

# Get improvement suggestions
aud suggest

# Provide feedback for continuous learning
aud learn-feedback --accept
```

### Development-Specific Flags

#### Excluding TheAuditor's Own Files

When testing or developing within TheAuditor's repository (e.g., analyzing `fakeproj/project_anarchy/`), use the `--exclude-self` flag to prevent false positives from TheAuditor's own files:

```bash
# Exclude all TheAuditor files from analysis
aud index --exclude-self
aud full --exclude-self
```

This flag excludes:
- All TheAuditor source code directories (`theauditor/`, `tests/`, etc.)
- Root configuration files (`pyproject.toml`, `package-template.json`, `Dockerfile`)
- Documentation and build files

**Use case:** Testing vulnerable projects within TheAuditor's repository without framework detection picking up TheAuditor's own configuration files.

### CI/CD Integration

#### GitHub Actions Example

```yaml
name: Security Audit
on: [push, pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      
      - name: Set up Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      
      - name: Install TheAuditor
        run: |
          pip install -e ".[all]"
          aud setup-claude --target .
      
      - name: Run Audit
        run: aud full
        
      - name: Upload Results
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: audit-results
          path: .pf/
```

### Running TheAuditor on Its Own Codebase (Dogfooding)

When developing TheAuditor or testing it on itself, you need a special dual-environment setup:

#### Understanding the Dual-Environment Architecture

TheAuditor maintains strict separation between:
1. **Primary Environment** (`.venv/`) - Where TheAuditor runs from
2. **Sandboxed Environment** (`.auditor_venv/.theauditor_tools/`) - Tools TheAuditor uses for analysis

This ensures reproducibility and prevents TheAuditor from analyzing its own analysis tools.

#### Setup Procedure for Dogfooding

```bash
# 1. Clone and set up development environment
git clone https://github.com/TheAuditorTool/Auditor.git
cd theauditor
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# 2. CRITICAL: Create the sandboxed analysis environment
aud setup-claude --target .

# 3. Verify setup
aud full --quick-test

# 4. Run full analysis on TheAuditor itself
aud full
```

#### Analyzing Test Projects Within TheAuditor

When analyzing test projects like `fakeproj/` from within TheAuditor's repository:

```bash
cd fakeproj/project_anarchy
aud full --exclude-self  # Excludes TheAuditor's own files
```

The `--exclude-self` flag prevents:
- Framework detection from identifying TheAuditor's `pyproject.toml`
- False positives from TheAuditor's configuration files
- Contamination from TheAuditor's source code

---

## Refactoring Detection

TheAuditor includes sophisticated capabilities for detecting incomplete refactorings, data model changes, and cross-stack inconsistencies.

### Understanding Refactoring Issues

Common refactoring problems TheAuditor detects:

1. **Data Model Evolution** - Fields moved between models (e.g., `product.price` → `variant.price`)
2. **Foreign Key Changes** - References updated in database but not in code
3. **API Contract Mismatches** - Frontend expects old structure, backend provides new
4. **Cross-Stack Inconsistencies** - TypeScript interfaces not matching backend models
5. **Incomplete Migrations** - Some code still using old field/table names

### How Refactoring Detection Works

TheAuditor uses multiple techniques:

#### Migration Analysis
Analyzes database migration files to understand schema changes:
```javascript
// Migration detected: Field moved from products to product_variants
removeColumn('products', 'unit_price');
addColumn('product_variants', 'retail_price', DataTypes.DECIMAL);
```

#### Impact Analysis
Traces dependencies to find all affected code:
```bash
aud impact --file "models/Product.ts" --line 42
# Shows: 47 files need updating
```

#### Pattern Detection
Over 30 refactoring-specific patterns detect common issues:
```yaml
- name: "PRODUCT_PRICE_FIELD_REMOVED"
  description: "Code accessing price on Product after migration to ProductVariant"
```

#### Cross-Stack Tracing
Matches frontend API calls to backend endpoints to detect contract mismatches.

### Using Refactoring Detection

#### Quick Detection
```bash
# Auto-detect from migrations
aud refactor --auto-detect

# Analyze specific change
aud refactor --file "models/Product.ts" --line 42

# Use with workset
aud refactor --workset

# Generate detailed report
aud refactor --auto-detect --output refactor_report.json
```

#### Best Practices for Refactoring

**Before Refactoring:**
1. Run impact analysis: `aud impact --file "model.ts" --line 42`
2. Create workset: `aud workset --from-impact`
3. Baseline analysis: `aud refactor --workset`

**During Refactoring:**
- Run incremental checks: `aud refactor --workset`
- Validate cross-stack: `aud impact --trace-to-backend`

**After Refactoring:**
- Full validation: `aud unified --mode refactor`
- Generate report: `aud report --format refactoring`

### Real-World Example

A product variant refactoring might be detected as:

```
PRODUCT_PRICE_FIELD_REMOVED
- Frontend: 23 files accessing product.unit_price
- Backend: Field moved to ProductVariant.retail_price
- Impact: POS system cannot display prices

ORDER_ITEMS_WRONG_REFERENCE
- Database: order_items.product_variant_id (new)
- Code: Still using order_items.product_id (old)
- Impact: Orders cannot be created
```

### Custom Refactoring Rules

TheAuditor uses YAML-based correlation rules to detect refactoring issues. These rules are YOUR business logic - you define what patterns indicate problems in YOUR codebase.

#### How It Works

1. **Rules Location**: `/theauditor/correlations/rules/refactoring.yaml`
2. **Rule Structure**: Each rule defines co-occurring facts that must ALL match
3. **Detection**: When all facts match, TheAuditor reports the issue
4. **No Code Changes**: Just edit YAML to define new patterns

#### Creating Your Own Rules

Edit `/theauditor/correlations/rules/refactoring.yaml` or create new YAML files:

```yaml
rules:
  - name: "MY_FIELD_MIGRATION"
    description: "Detect when price field moved but old code remains"
    co_occurring_facts:
      - tool: "grep"
        pattern: "removeColumn.*price"  # Migration removed field
      - tool: "grep"
        pattern: "product\\.price"      # Code still uses old field
    confidence: 0.92

  - name: "API_VERSION_MISMATCH"
    description: "Frontend calling v1 API but backend is v2"
    co_occurring_facts:
      - tool: "grep"
        pattern: "/api/v1/"             # Frontend uses v1
      - tool: "grep"
        pattern: "router.*'/v2/'"       # Backend only has v2
    confidence: 0.95
```

#### Available Tools for Facts

- **grep**: Pattern matching in files
- **patterns**: Matches from pattern detection
- **taint_analyzer**: Taint flow findings
- **lint**: Linter findings

#### Real Example from Production

```yaml
- name: "PRODUCT_VARIANT_REFACTOR"
  description: "Product fields moved to ProductVariant but frontend still uses old structure"
  co_occurring_facts:
    - tool: "grep"
      pattern: "ProductVariant.*retail_price.*Sequelize"  # Backend changed
    - tool: "grep"
      pattern: "product\\.unit_price|product\\.retail_price"  # Frontend didn't
  confidence: 0.92
```

This detects when you moved price fields from Product to ProductVariant model but frontend still expects the old structure.

---

## Troubleshooting

### Common Issues

#### "TypeScript compiler not available in TheAuditor sandbox"

**Solution**: Run **`aud setup-claude --target .`** to set up the sandbox.

#### "Coverage < 90% - run `aud capsules` first"

**Solution**: Generate code capsules for better analysis coverage:
```bash
aud index
aud workset --all
```

#### Linting produces no results

**Solution**: Ensure linters are installed:
```bash
# For Python
pip install -e ".[linters]"

# For JavaScript/TypeScript
aud setup-claude --target .
```

#### Pipeline fails at specific phase

**Solution**: Check **`.pf/error.log`** for details:
```bash
cat .pf/error.log
# Or check phase-specific error log
cat .pf/error_phase_08.log
```

### Performance Optimization

For large repositories:

```bash
# Limit analysis scope
aud workset --paths "src/critical/**/*.py"

# Run specific commands only
aud index && aud lint && aud detect-patterns

# Adjust chunking for larger context windows
export THEAUDITOR_LIMITS_MAX_CHUNK_SIZE=100000  # 100KB chunks
export THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE=5   # Allow up to 5 chunks
```

### Runtime Configuration

TheAuditor supports environment variable overrides for runtime configuration:

```bash
# Chunking configuration
export THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE=5     # Default: 3
export THEAUDITOR_LIMITS_MAX_CHUNK_SIZE=100000     # Default: 65000 (bytes)

# File size limits
export THEAUDITOR_LIMITS_MAX_FILE_SIZE=5242880     # Default: 2097152 (2MB)

# Timeout configuration
export THEAUDITOR_TIMEOUTS_LINT_TIMEOUT=600        # Default: 300 (seconds)
export THEAUDITOR_TIMEOUTS_FCE_TIMEOUT=1200        # Default: 600 (seconds)

# Batch processing
export THEAUDITOR_LIMITS_DEFAULT_BATCH_SIZE=500    # Default: 200
```

Configuration can also be set via `.pf/config.json` for project-specific overrides.

---

## Best Practices

1. **Always run `aud init` first** in a new project
2. **Set up the sandbox** for JavaScript/TypeScript projects using **`aud setup-claude --target .`**
3. **Use worksets** for incremental analysis during development
4. **Run `aud full`** before releases for comprehensive analysis
5. **Review `.pf/readthis/`** for AI-friendly issue summaries
6. **Check exit codes** in CI/CD for automated pass/fail decisions
7. **Archive results** with timestamps for audit trails

---

## Exit Codes for Automation

**TheAuditor** uses specific exit codes for CI/CD integration:

- **`0`** - Success, no critical/high issues
- **`1`** - High severity findings
- **`2`** - Critical severity findings  
- **`3`** - Pipeline/task incomplete

Use these in scripts:
```bash
aud full
if [ $? -eq 2 ]; then
    echo "Critical vulnerabilities found - blocking deployment"
    exit 1
fi
```

---

## Getting Help

- Run **`aud --help`** for command overview
- Run **`aud <command> --help`** for specific command help
- Check **`.pf/pipeline.log`** for execution details
- Review **`.pf/error.log`** for troubleshooting
- Refer to **`teamsop.md`** for development workflow

---

## Next Steps

1. Initialize your first project with **`aud init`**
2. Run **`aud full`** to see TheAuditor in action
3. Explore the results in **`.pf/readthis/`**
4. Integrate into your CI/CD pipeline
5. Customize patterns for your specific needs

---

**Remember**: TheAuditor is designed to work **offline**, maintain **data integrity**, and produce **AI-ready outputs**. All analysis is **deterministic** and **reproducible**.