# TheAuditor: Complete Usage Guide

TheAuditor is a **multi-language, database-first security and code analysis platform** that indexes your entire codebase into SQLite, then provides fast queries, taint analysis, ML predictions, and deterministic context bundles for AI agents.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [The Pipeline](#the-pipeline)
4. [System Architecture](#system-architecture)
5. [Basic Usage](#basic-usage)
6. [Security Analysis](#security-analysis)
7. [Code Intelligence](#code-intelligence)
8. [ML & Predictions](#ml--predictions)
9. [AI Agent Integration](#ai-agent-integration)
10. [Command Reference](#command-reference)
11. [Performance Guide](#performance-guide)

---

## Quick Start

```bash
# 1. Setup isolated analysis environment
aud setup-ai --target .

# 2. Run the complete audit pipeline
aud full

# 3. View architectural overview
aud blueprint --structure

# 4. Check for security vulnerabilities
aud taint --severity high

# 5. Get context on any file or function
aud explain src/auth/service.ts
```

**What Just Happened:**
- `setup-ai` creates a `.pf/` directory with databases and cache
- `full` runs a 24-phase pipeline: indexing, linting, graph building, taint analysis, and more
- `blueprint` shows codebase architecture facts
- `taint` finds injection vulnerabilities (SQLi, XSS, command injection)
- `explain` provides comprehensive context on any code target

---

## Core Concepts

### Database-First Philosophy

TheAuditor parses your code ONCE, stores everything in SQLite, then answers questions fast:

```
Traditional: User asks → Read files → Parse ASTs → Traverse → Return (seconds)
TheAuditor:  aud full → Parse once → Store in SQLite → Query (<1s typically)
```

### The .pf Directory

After running `aud full`, you'll have:

```
.pf/
├── repo_index.db    # Main database (~181MB) - symbols, imports, calls, security patterns
├── graphs.db        # Graph database (~126MB) - import/call/data flow graphs
├── raw/             # JSON exports
│   ├── taint_analysis.json
│   ├── fce.json
│   └── lint.json
├── cache/           # AST cache (SHA256-keyed)
└── ml/              # ML models and session history
    └── model.joblib
```

### Zero Fallback Policy

TheAuditor prioritizes correctness over convenience. When critical issues occur, the pipeline stops rather than continuing with incomplete data:
- No retry logic on foreign key violations (indicates schema bugs)
- Fidelity errors stop the pipeline (indicates data corruption risk)
- Parse errors halt indexing for that language (fix syntax or exclude problematic files)

---

## The Pipeline

The `aud full` command runs a **24-phase pipeline** in 4 stages:

### Stage 1: Foundation (Sequential, REQUIRED)
| Phase | Command | Purpose |
|-------|---------|---------|
| 1 | index | Parse all code, extract ASTs |
| 2 | detect-frameworks | Identify Django, Express, React, etc. |

### Stage 2: Data Preparation (Sequential)
| Phase | Command | Purpose |
|-------|---------|---------|
| 3-4 | deps | Dependency analysis + vulnerability scan |
| 5 | docs fetch | Fetch library documentation |
| 6 | workset | Compute targeted file subset |
| 7 | lint | Run linters (ruff, eslint, mypy, clippy) |
| 8 | detect-patterns | Detect 200+ security patterns |
| 9-10 | graph build | Build import/call/DFG graphs |
| 11 | terraform provision | Prepare IaC analysis |

### Stage 3: Heavy Analysis (3 Parallel Tracks)
| Track | Phases | Purpose |
|-------|--------|---------|
| A | 12 | Taint analysis (IFDS backward + FlowResolver forward) |
| B | 13-20 | Terraform/CDK/GitHub Actions security + graph viz |
| C | Network | Dependency version checks, doc fetching |

### Stage 4: Aggregation (Sequential)
| Phase | Command | Purpose |
|-------|---------|---------|
| 21 | cfg analyze | Control flow complexity |
| 22 | metadata churn | Git churn analysis |
| 23 | fce | Factual Correlation Engine |
| 24 | session analyze | AI agent session analysis |

### Pipeline Modes

```bash
aud full              # Complete run (2-10 min)
aud full --offline    # Skip network I/O (1-5 min)
aud full --index      # Index only, skip analysis (1-3 min)
```

---

## System Architecture

### Language Support

| Language | Parser | Features |
|----------|--------|----------|
| **Python** | Built-in `ast` | 47 data categories, Django/Flask/FastAPI |
| **JavaScript/TypeScript** | TypeScript Compiler API | JSX/TSX, React hooks, type info |
| **Go** | Tree-sitter | Goroutines, channels, race detection |
| **Rust** | Tree-sitter | Traits, unsafe blocks, lifetimes |
| **Bash** | Tree-sitter | Pipelines, heredocs, variable tracking |
| **HCL/Terraform** | Tree-sitter | Resource analysis |

### Database Schema

**repo_index.db** contains 70+ tables:
- `symbols` - Functions, classes, variables
- `imports` - Import statements
- `function_call_args` - All function calls with arguments
- `api_endpoints` - HTTP routes
- `sql_queries` - SQL statements
- `jwt_patterns`, `oauth_patterns` - Auth patterns
- `findings_consolidated` - All linter findings
- Framework-specific tables (Django models, React components, etc.)

**graphs.db** contains:
- `nodes` - Graph nodes (modules, functions, variables)
- `edges` - Graph edges (import, call, assignment, reverse edges)

### The Fidelity System

Every extraction is verified with a "Holy Trio":

1. **Manifest**: What the extractor found (count, columns, bytes)
2. **Receipt**: What storage actually saved
3. **Reconciliation**: Compare manifest vs receipt

If they don't match → FATAL ERROR (no silent data loss)

---

## Basic Usage

### Initial Setup

```bash
# Create analysis environment
aud setup-ai --target /path/to/project

# Verify tools are available
aud tools

# Run full analysis
aud full
```

### Viewing Results

```bash
# Architecture overview
aud blueprint                 # Quick snapshot
aud blueprint --structure     # Detailed structure
aud blueprint --security      # Security surface
aud blueprint --graph         # Dependency analysis
aud blueprint --all           # Everything as JSON

# View findings
aud fce --min-vectors 2       # Files with 2+ analysis vectors agreeing

# Check specific file
aud explain src/auth.ts       # Complete context bundle
```

### Incremental Analysis

```bash
# Create workset from git diff
aud workset --diff main..HEAD

# Run only on changed files
aud lint --workset
aud detect-patterns --workset
```

---

## Security Analysis

### Taint Analysis

Traces untrusted data from sources (user input) to dangerous sinks (SQL, eval, etc.):

```bash
# Run taint analysis
aud taint

# Filter by severity
aud taint --severity critical
aud taint --severity high

# Detailed output
aud taint --verbose
```

**What It Detects:**
| Type | Risk | Example |
|------|------|---------|
| SQL Injection | CRITICAL | `db.query(f"SELECT * FROM users WHERE id={user_input}")` |
| Command Injection | CRITICAL | `os.system(f"ping {user_input}")` |
| XSS | HIGH | `innerHTML = user_input` |
| Path Traversal | HIGH | `open(user_provided_path)` |
| SSRF | HIGH | `requests.get(user_url)` |
| Deserialization | CRITICAL | `pickle.loads(user_data)` |

### Boundary Analysis

Measures distance between entry points and security controls:

```bash
# All boundary types
aud boundaries

# Input validation only
aud boundaries --type input-validation

# Filter by severity
aud boundaries --severity critical
```

**Quality Classification:**
| Quality | Distance | Risk |
|---------|----------|------|
| CLEAR | 0 hops | Very Low |
| ACCEPTABLE | 1-2 hops | Low |
| FUZZY | 3+ hops | Medium-High |
| MISSING | No control | Critical |

### Pattern Detection

Detects 200+ security patterns:

```bash
aud detect-patterns

# With workset filtering
aud detect-patterns --workset
```

### IaC Security

```bash
# Terraform analysis
aud terraform analyze

# AWS CDK analysis
aud cdk analyze

# GitHub Actions security
aud workflows analyze

# Docker security
aud docker-analyze
```

---

## Code Intelligence

### Explain Command

Get complete context on any target in one command:

```bash
# File context
aud explain src/auth/service.ts
# Returns: symbols, hooks, imports, importers, calls, framework info

# Symbol context
aud explain authenticateUser
# Returns: definition, callers, callees

# Component context
aud explain Dashboard
# Returns: component metadata, hooks, children

# Options
aud explain src/auth.ts --format json    # Machine-readable
aud explain src/auth.ts --depth 3        # Deeper call graph
aud explain src/auth.ts --fce            # Include FCE signals
```

### Query Command

Direct database queries:

```bash
# Symbol lookup
aud query --symbol validateUser --show-callers --depth 2

# File analysis
aud query --file src/auth.ts --show-dependents

# API endpoints
aud query --api "/users/:id"

# Component tree
aud query --component Dashboard --show-tree

# Variable flow
aud query --variable userId --show-flow --depth 3
```

### Impact Analysis

Calculate blast radius before changes:

```bash
# By symbol name
aud impact --symbol AuthManager

# By file + line
aud impact --file src/auth.py --line 42

# Planning context (AI-friendly)
aud impact --symbol validate --planning-context
```

**Coupling Score Interpretation:**
| Score | Level | Action |
|-------|-------|--------|
| 0-29 | LOW | Safe to refactor directly |
| 30-69 | MEDIUM | Review callers, phased rollout |
| 70-100 | HIGH | Extract interface first |

### Dead Code Detection

```bash
# Find all dead code
aud deadcode

# Filter by path
aud deadcode --path-filter 'src/features/%'

# CI/CD mode
aud deadcode --fail-on-dead-code
```

**Detection Methods:**
1. **Isolated Modules** - Files never imported
2. **Dead Symbols** - Functions defined but never called
3. **Ghost Imports** - Imports that are never used

---

## ML & Predictions

### Training Models

```bash
# Train on current codebase + history
aud learn --db-path .pf/repo_index.db \
          --enable-git \
          --session-dir ~/.claude/projects/
```

### Getting Predictions

```bash
# Suggest risky files
aud suggest --workset .pf/workset.json --topk 10
```

**Output:**
```json
{
  "likely_root_causes": [
    {"path": "auth/jwt.py", "score": 0.87}
  ],
  "next_files_to_edit": [
    {"path": "middleware.py", "score": 0.92}
  ]
}
```

### Feature Dimensions (109 Total)

The ML system uses 15 feature tiers:
1. File metadata (bytes, LOC)
2. Language detection
3. Graph topology (in/out degree)
4. Historical journal (touches, failures)
5. Root cause analysis
6. AST invariants
7. Git churn (commits, authors)
8. Semantic imports (HTTP, DB, auth)
9. AST complexity (functions, classes)
10. Security patterns (JWT, SQL)
11. Vulnerability findings (CWE counts)
12. Type coverage
13. Control flow complexity
14. Impact radius
15. Agent behavior patterns

---

## AI Agent Integration

### Slash Commands

TheAuditor provides slash commands for AI agents:

| Command | Purpose |
|---------|---------|
| `/onboard` | Initialize session with rules |
| `/start` | Load ticket, verify, brief |
| `/spec` | Create atomic proposals |
| `/check` | Due diligence for proposals |
| `/audit` | Run comprehensive audit |
| `/review` | Quality review |
| `/explore` | Architecture documentation |
| `/git` | Generate commit messages |
| `/progress` | Re-onboard after compaction |

### TheAuditor Integration Commands

| Command | Purpose |
|---------|---------|
| `/theauditor:planning` | Database-first planning |
| `/theauditor:refactor` | Refactoring analysis |
| `/theauditor:security` | Security + taint tracking |
| `/theauditor:dataflow` | Source-to-sink tracing |
| `/theauditor:impact` | Blast radius analysis |

### Session Analysis

Analyze AI agent productivity:

```bash
# List available sessions
aud session list

# Parse and store sessions
aud session analyze

# View activity breakdown
aud session activity

# Deep-dive single session
aud session inspect path/to/session.jsonl
```

**Activity Types:**
| Type | Definition |
|------|------------|
| PLANNING | Discussion & design (text >200 chars, no tools) |
| WORKING | Code changes (Edit, Write, Bash) |
| RESEARCH | Info gathering (Read, Grep, Glob) |
| CONVERSATION | Questions, clarifications |

**Key Metrics:**
- `work_to_talk_ratio` - Higher is better (productive)
- `research_to_work_ratio` - Lower is better (efficient)
- `tokens_per_edit` - Lower is better

---

## FCE: Factual Correlation Engine

FCE identifies where **multiple independent analysis vectors converge**:

### The 4 Vectors

| Vector | Source | Measures |
|--------|--------|----------|
| **STATIC (S)** | Linters | Code quality, security patterns |
| **FLOW (F)** | Taint analysis | Source-to-sink data flow |
| **PROCESS (P)** | Git history | File volatility, churn |
| **STRUCTURAL (T)** | CFG analysis | Complexity, nesting depth |

### Usage

```bash
aud fce                    # Default: 2+ vectors
aud fce --min-vectors 3    # High confidence only
aud fce --format json      # Machine-readable
aud fce --detailed         # Include all facts
```

### Interpreting Density

```
[3/4] [SF-T] src/auth/login.py
  |     |    |
  |     |    +-- File path
  |     +------- Vectors: S=Static, F=Flow, P=Process, T=Structural
  +------------- Density: 3 of 4 vectors
```

| Density | Meaning |
|---------|---------|
| 4/4 (1.0) | Everything screaming - investigate immediately |
| 3/4 (0.75) | Strong convergence - high priority |
| 2/4 (0.5) | Multiple signals - worth attention |
| 1/4 (0.25) | Single dimension - normal finding |

---

## Planning & Refactoring

### Planning System

Database-centric task management with code verification:

```bash
# Create a plan
aud planning init --name "JWT Migration"

# Add task with verification spec
aud planning add-task 1 --title "Migrate auth" --spec auth.yaml

# Create checkpoint before changes
aud planning checkpoint 1 1 --name "added-imports"

# Verify task completion
aud full --index && aud planning verify-task 1 1 --verbose

# Archive completed plan
aud planning archive 1 --notes "Deployed"
```

### Refactor Profiles (YAML)

Define what refactored code should look like:

```yaml
refactor_name: "product_variants"
version: "2025-10-26"

rules:
  - id: "order-cart"
    description: "Cart must use variant IDs"
    severity: "critical"
    match:
      identifiers:
        - "product.unit_price"
        - "/.*\\.product\\.id/"
    expect:
      identifiers:
        - "product_variant.retail_price"
    scope:
      include: ["frontend/src/pages/pos/**"]
```

```bash
aud refactor --file profile.yaml
```

### Semantic Context

Classify findings by business meaning:

```yaml
context_name: "oauth_migration"

patterns:
  obsolete:
    - id: "jwt_issue_calls"
      pattern: "(jwt\\.sign|jwt\\.verify)"
      reason: "JWT deprecated; use OAuth2"
      replacement: "AuthService.issueOAuthToken"

  current:
    - id: "oauth_exchange"
      pattern: "oauth2Client\\."

  transitional:
    - id: "jwt_bridge"
      pattern: "bridgeJwtToOAuth"
      expires: "2025-12-31"
```

```bash
aud context --file oauth_migration.yaml
```

---

## Command Reference

### Project Setup
| Command | Description |
|---------|-------------|
| `aud setup-ai` | Create isolated analysis environment |
| `aud tools` | Tool detection and verification |

### Core Analysis
| Command | Description |
|---------|-------------|
| `aud full` | Run complete 24-phase pipeline |
| `aud full --offline` | Skip network I/O |
| `aud full --index` | Index only, skip analysis |
| `aud workset` | Compute targeted file subset |

### Security
| Command | Description |
|---------|-------------|
| `aud detect-patterns` | Detect 200+ security patterns |
| `aud detect-frameworks` | Display detected frameworks |
| `aud taint` | IFDS taint analysis |
| `aud boundaries` | Security boundary analysis |
| `aud terraform analyze` | Terraform security |
| `aud cdk analyze` | AWS CDK security |
| `aud workflows analyze` | GitHub Actions security |
| `aud docker-analyze` | Dockerfile security |

### Dependencies
| Command | Description |
|---------|-------------|
| `aud deps` | Dependency analysis |
| `aud deps --vuln-scan` | Vulnerability scanning |
| `aud docs` | Documentation fetching |

### Code Quality
| Command | Description |
|---------|-------------|
| `aud lint` | Run all linters |
| `aud cfg analyze` | Control flow complexity |
| `aud graph build` | Build dependency graphs |
| `aud graph analyze` | Cycles, hotspots |
| `aud deadcode` | Dead code detection |

### Queries & Context
| Command | Description |
|---------|-------------|
| `aud explain <target>` | Complete context bundle |
| `aud query` | Database query API |
| `aud impact` | Blast radius analysis |
| `aud refactor` | Refactoring impact |
| `aud context` | Semantic classification |

### Reporting
| Command | Description |
|---------|-------------|
| `aud fce` | Factual Correlation Engine |
| `aud metadata churn` | Git churn analysis |
| `aud blueprint` | Architecture visualization |

### ML & Insights
| Command | Description |
|---------|-------------|
| `aud learn` | Train ML models |
| `aud suggest` | ML-based suggestions |
| `aud session analyze` | AI session analysis |

### Utilities
| Command | Description |
|---------|-------------|
| `aud manual` | Built-in documentation |
| `aud manual --list` | List all topics |
| `aud planning` | Planning system |

---

## Performance Guide

### Typical Run Times

| Codebase | Full | --offline | --index |
|----------|------|-----------|---------|
| < 5K LOC | 2-3 min | 1-2 min | 1-2 min |
| 20K LOC | 5-10 min | 3-5 min | 2-3 min |
| 100K+ LOC | 15-20 min | 10-15 min | 5-10 min |

### Query Performance

| Operation | Time |
|-----------|------|
| `aud query --symbol X` | <1 sec |
| `aud explain src/file.ts` | 1-5 sec |
| `aud taint` | 30-60 sec |
| `aud deadcode` | 1-2 sec |

### Linter Times (1K files)

| Linter | Time |
|--------|------|
| Ruff | 1-3 sec |
| Mypy | 5-15 sec |
| ESLint | 3-10 sec |
| Clippy | 5-20 sec |
| GolangCI | 3-10 sec |
| ShellCheck | 1-3 sec |
| **Total (parallel)** | **5-20 sec** |

### Memory Usage

| Size | RAM |
|------|-----|
| 100 files | ~150MB |
| 500 files | ~300MB |
| 2K+ files | ~500MB |

### Optimization Tips

1. **Use `--offline`** for CI/CD or air-gapped environments
2. **Use `--index`** for quick reindex after code changes
3. **Use worksets** for incremental analysis:
   ```bash
   aud workset --diff main..HEAD
   aud lint --workset
   ```
4. **Configure timeouts** via environment variables:
   ```bash
   export THEAUDITOR_TIMEOUT_INDEX_SECONDS=600
   export THEAUDITOR_TIMEOUT_TAINT_SECONDS=1800
   ```

---

## Getting Help

```bash
# Main help (9 category panels)
aud --help

# Per-command help with examples
aud <command> --help

# Built-in documentation
aud manual --list
aud manual taint
aud manual fce
aud manual boundaries
```

---

## Common Workflows

### Security Audit

```bash
aud setup-ai --target .
aud full
aud blueprint --security
aud taint --severity high
aud boundaries --type input-validation
aud fce --min-vectors 2
```

### Pre-Refactor Assessment

```bash
aud full --index
aud impact --symbol TargetFunction --planning-context
aud query --symbol TargetFunction --show-callers --depth 3
aud deadcode
```

### Incremental PR Review

```bash
aud workset --diff main..HEAD
aud lint --workset
aud detect-patterns --workset
aud impact --symbol changedFunction
```

### Architecture Discovery

```bash
aud full --index
aud blueprint --structure
aud blueprint --graph
aud graph analyze
aud explain src/core/index.ts
```

### ML-Driven Analysis

```bash
aud full
aud learn --enable-git --session-dir ~/.claude/projects/
aud suggest --topk 10
```
