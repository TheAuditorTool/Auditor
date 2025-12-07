# TheAuditor

**The Database-First Code Intelligence Platform**

> Modern static analysis reimagined: Database-driven, AI-optimized, zero-fallback architecture for Python, JavaScript/TypeScript, Go, and Rust projects
---

## What is TheAuditor?


TheAuditor is a **production-grade offline SAST and Code Context for AIs tool** that indexes your entire codebase into a structured SQLite database, enabling:

- **200+ security vulnerability patterns** with framework-aware detection
- **Complete data flow analysis** with cross-file taint tracking
- **Architectural intelligence** with hotspot detection and circular dependency analysis
- **AI-optimized output** designed for LLM consumption (<65KB chunks)
- **Database-first queries** replacing slow file I/O with indexed lookups
- **Framework-aware detection** for Django, Flask, FastAPI, React, Vue, Express, and 15+ more

**Key Differentiator**: While most SAST tools scan files repeatedly, TheAuditor **indexes once, queries infinitely** - enabling sub-second queries across 100K+ LOC.

---

```bash
# Index your codebase (once)
aud full

# Query anything instantly
aud query --symbol validateUser --show-callers --depth 3
aud blueprint --security
aud taint --severity critical
aud impact --symbol AuthService --planning-context
```

**One index. Infinite queries.**

---

## Architecture: Custom Compilers, Not Generic Parsers

TheAuditor's analysis accuracy comes from **deep compiler integrations**, not generic parsing:

### Python Analysis Engine

Built on Python's native `ast` module with **27 specialized extractor modules**:

| Extractor Category | Modules |
|-------------------|---------|
| **Core** | `core_extractors`, `fundamental_extractors`, `control_flow_extractors` |
| **Framework** | `django_web_extractors`, `flask_extractors`, `orm_extractors`, `task_graphql_extractors` |
| **Security** | `security_extractors`, `validation_extractors`, `data_flow_extractors` |
| **Advanced** | `async_extractors`, `protocol_extractors`, `type_extractors`, `cfg_extractor` |

Each extractor performs semantic analysis—understanding Django signals, Flask routes, Celery tasks, Pydantic validators, and 100+ framework-specific patterns.

### JavaScript/TypeScript Analysis Engine

Uses the **actual TypeScript Compiler API** via Node.js subprocess integration:

- Full semantic type resolution (not regex pattern matching)
- Module resolution across complex import graphs
- JSX/TSX transformation with component tree analysis
- tsconfig.json-aware path aliasing
- Vue SFC script extraction and analysis

This is **not tree-sitter**. The TypeScript Compiler provides the same semantic analysis as your IDE.

### Polyglot Support

| Language | Parser | Fidelity |
|----------|--------|----------|
| Python | Native `ast` module + 27 extractors | Full semantic |
| TypeScript/JavaScript | TypeScript Compiler API | Full semantic |
| Go | tree-sitter | Structural + taint |
| Rust | tree-sitter | Structural + taint |
| Bash | tree-sitter | Structural + taint |

Tree-sitter provides fast structural parsing for Go, Rust, and Bash. The heavy lifting for Python and JS/TS uses language-native compilers.

---

## Key Differentiators

| Traditional Tools | TheAuditor |
|-------------------|------------|
| Re-parse files per query | Parse once, query forever |
| Single analysis dimension | 4-vector convergence (static + structural + process + flow) |
| Human-only interfaces | AI-agent native with anti-hallucination safeguards |
| File-based navigation | Database-first with recursive CTEs |
| Point-in-time analysis | ML models trained on your codebase history |

---

## Installation

```bash
pip install theauditor

# Or from source
git clone https://github.com/TheAuditorTool/Auditor.git
cd Auditor
pip install -e .

# Install language tooling (Node.js runtime, linters)
aud setup-ai
```

**Requirements**: Python 3.12+

---

## Quick Start

```bash
# 1. Index your codebase
cd your-project
aud full

# 2. Explore architecture
aud blueprint --structure

# 3. Find security issues
aud taint --severity high
aud boundaries --type input-validation

# 4. Query anything
aud explain src/auth/service.ts
aud query --symbol authenticate --show-callers
```

---

## Feature Overview

### Core Analysis Engine

| Command | Purpose |
|---------|---------|
| `aud full` | Comprehensive 20-phase indexing pipeline |
| `aud workset` | Create focused file subsets for targeted analysis |
| `aud detect-patterns` | 200+ security vulnerability patterns |
| `aud taint` | Source-to-sink data flow tracking |
| `aud boundaries` | Security boundary enforcement analysis |

### Intelligence & Queries

| Command | Purpose |
|---------|---------|
| `aud explain` | Complete briefing packet for any file/symbol/component |
| `aud query` | SQL-powered code structure queries |
| `aud blueprint` | Architectural visualization (8 analysis modes) |
| `aud impact` | Blast radius calculation before changes |
| `aud deadcode` | Multi-layered dead code detection |

### ML & Predictions

| Command | Purpose |
|---------|---------|
| `aud learn` | Train models on your codebase (109-dimensional features) |
| `aud suggest` | Predict root causes and next files to edit |
| `aud session` | Analyze AI agent interactions for quality insights |
| `aud fce` | Four-vector convergence engine |

### Planning & Refactoring

| Command | Purpose |
|---------|---------|
| `aud planning` | Database-centric task management with code verification |
| `aud refactor` | YAML-driven refactoring validation |
| `aud context` | Semantic classification (obsolete/current/transitional) |

---

## Language Support

| Language | Indexing | Taint | CFG | Call Graph |
|----------|----------|-------|-----|------------|
| Python | Full | Full | Full | Full |
| TypeScript/JavaScript | Full | Full | Full | Full |
| Go | Full | Full | - | Full |
| Rust | Full | Full | - | Full |
| Bash | Full | Full | - | - |
| Vue/React | Full | - | - | Component Tree |

---

## Deep Dive: Core Features

### Database-First Architecture

Every analysis result lives in SQLite databases (`.pf/repo_index.db`, `.pf/graphs.db`). This enables:

- **Instant queries**: All relationships pre-computed
- **Cross-tool correlation**: Findings from different analyzers linked
- **PRAGMA optimizations**: WAL mode, 64MB cache
- **Recursive CTEs**: Complex graph traversals in single queries

```sql
-- Example: Find all callers of a function recursively
WITH RECURSIVE caller_graph AS (
    SELECT * FROM function_call_args WHERE callee = 'validate'
    UNION ALL
    SELECT f.* FROM function_call_args f
    JOIN caller_graph c ON f.callee = c.caller
    WHERE depth < 3
)
SELECT DISTINCT file, line, caller FROM caller_graph;
```

### Four-Vector Convergence Engine (FCE)

The FCE identifies high-risk code by finding where multiple independent analysis vectors converge:

| Vector | Source | Signal |
|--------|--------|--------|
| **STATIC** | Linters (ESLint, Ruff, Clippy) | Code quality issues |
| **STRUCTURAL** | CFG complexity | Cyclomatic complexity |
| **PROCESS** | Git churn | Frequently modified code |
| **FLOW** | Taint propagation | Data flow vulnerabilities |

**Key insight**: When 3+ independent vectors agree on a file, confidence is exponentially higher than any single tool.

```bash
aud fce --threshold 3  # Files where 3+ vectors converge
```

### Taint Analysis

Track untrusted data from sources to sinks:

```bash
aud taint --severity critical
```

**Detects**:
- SQL injection: `cursor.execute(f"SELECT * FROM {user_input}")`
- Command injection: `os.system(f"ping {host}")`
- XSS: `innerHTML = userContent`
- Path traversal: `open(f"/data/{user_path}")`

### Boundary Analysis

Measure the distance between entry points and security controls:

```bash
aud boundaries --type input-validation
```

**Quality Classification**:
| Quality | Distance | Risk |
|---------|----------|------|
| CLEAR | 0 calls | Very Low |
| ACCEPTABLE | 1-2 calls | Low |
| FUZZY | 3+ calls | Medium-High |
| MISSING | No control | Critical |

### Impact Analysis

Calculate blast radius before making changes:

```bash
aud impact --symbol AuthManager --planning-context
```

**Output**:
```
Target: AuthManager at src/auth/manager.py:42

IMPACT SUMMARY:
  Direct Upstream: 8 callers
  Direct Downstream: 3 dependencies
  Total Impact: 14 symbols across 7 files
  Coupling Score: 67/100 (MEDIUM)

RECOMMENDATION: Review callers before refactoring
```

### Dead Code Detection

Multi-layered approach with confidence scoring:

```bash
aud deadcode --format summary
```

**Detection Methods**:
1. **Isolated Modules**: Files never imported (graph reachability)
2. **Dead Symbols**: Functions defined but never called
3. **Ghost Imports**: Imports present but never used

**Confidence Levels**:
- **HIGH**: Safe to remove
- **MEDIUM**: Manual review (CLI entry points, tests)
- **LOW**: Likely false positive (magic methods, type hints)

---

## AI Agent Integration

TheAuditor is designed for AI agents with **anti-hallucination safeguards**.

### Slash Commands

```bash
/onboard      # Initialize session with rules
/start        # Load ticket, verify, brief
/audit        # Comprehensive code audit
/explore      # Explore codebase architecture
/theauditor:planning   # Database-first planning
/theauditor:security   # Security analysis
/theauditor:impact     # Blast radius analysis
```

### Agent Execution Protocol

**MANDATORY for AI Agents**:
1. Run `aud blueprint --structure` before ANY planning
2. Use `aud query` instead of reading files directly
3. Cite every query result with evidence
4. Follow Phase -> Task -> Job hierarchy

**FORBIDDEN**:
- "Let me read the file..." (use `aud explain`)
- "Based on typical patterns..." (use database facts)
- Making recommendations without query evidence

### Token Efficiency

| Traditional AI | TheAuditor Agent |
|----------------|------------------|
| Read 2000 lines to find functions | `aud query --file X --list functions` |
| Grep entire codebase | `aud blueprint` (instant) |
| Assume callers exist | `aud query --symbol X --show-callers` |

**Result**: Queries return indexed facts from the database, not generated assumptions

---

## Machine Learning Features

### 109-Dimensional Feature Extraction

TheAuditor extracts comprehensive features for ML models:

**Tier 1-5**: File metadata, graph topology, execution history, RCA, AST proofs
**Tier 6-10**: Git churn, semantic imports, AST complexity, security patterns, vulnerability flow
**Tier 11-15**: Type coverage, control flow, impact coupling, agent behavior, session execution
**Tier 16**: Text features (hashed path components)

### ML Models

```bash
# Train models on your codebase
aud learn --enable-git --session-dir ~/.claude/projects/

# Get predictions
aud suggest --topk 10
```

**Predictions**:
- **Root Cause Classifier**: Which files are likely causing failures?
- **Next Edit Predictor**: Which files need modification?
- **Risk Regression**: Quantified change risk (0-1)

### Session Analysis

Analyze AI agent interactions for quality metrics:

```bash
aud session activity
```

**Metrics**:
- `work_to_talk_ratio`: Working tokens / (Planning + Conversation)
- `research_to_work_ratio`: Research tokens / Working tokens
- `tokens_per_edit`: Efficiency measure

---

## Planning System

Database-centric task management with **code-driven verification**.

### Why Not Jira/Linear?

1. External tools never see your actual code
2. Manual verification is error-prone
3. Git can't track incremental edits (3 uncommitted edits = 1 change)

### Planning Workflow

```bash
# 1. Initialize plan
aud planning init --name "JWT Migration"
aud planning add-task 1 --title "Migrate auth" --spec auth.yaml

# 2. Track progress
aud full --index
aud planning verify-task 1 1 --verbose
# Output: 47 violations (baseline)

# 3. Iterative development
# [Make changes]
aud planning checkpoint 1 1 --name "updated-middleware"
aud planning verify-task 1 1
# Output: 37 violations (10 fixed!)

# 4. Complete
aud planning archive 1 --notes "Migration complete"
```

**Key Feature**: Tasks complete when code matches YAML specs - verified against database, not human opinion.

---

## YAML Refactor Profiles

Define *what refactored code should look like*:

```yaml
refactor_name: "express_v5_migration"
description: "Ensure Express v5 patterns"

rules:
  - id: "middleware-signature"
    description: "Use new middleware signature"
    severity: "critical"
    match:
      identifiers:
        - "app.use(err, req, res, next)"  # Old pattern
    expect:
      identifiers:
        - "app.use((err, req, res, next) =>)"  # New pattern
    scope:
      include: ["src/middleware/**"]
    guidance: "Update to arrow function signature"
```

```bash
aud refactor --file express_v5.yaml
```

---

## Semantic Context

Classify findings by business meaning during migrations:

```yaml
context_name: "oauth_migration"

patterns:
  obsolete:
    - id: "jwt_calls"
      pattern: "jwt\\.(sign|verify)"
      reason: "JWT deprecated, use OAuth2"
      replacement: "AuthService.issueOAuthToken"

  current:
    - id: "oauth_exchange"
      pattern: "oauth2Client\\."
      reason: "OAuth2 is approved mechanism"

  transitional:
    - id: "bridge_layer"
      pattern: "bridgeJwtToOAuth"
      expires: "2025-12-31"  # Auto-escalates after date
```

```bash
aud context --file oauth_migration.yaml
```

---

## Built-in Documentation

30+ topics with AI-friendly formatting:

```bash
aud manual --list        # List all topics
aud manual taint         # Taint analysis guide
aud manual fce           # FCE explanation
aud manual boundaries    # Boundary analysis
```

**Features**:
- Offline-first (embedded in CLI)
- <1ms response time
- Rich terminal formatting
- AI agent optimized

---

## CLI Help System

Rich-formatted help with 9 command categories:

```bash
aud --help              # Dashboard view
aud taint --help        # Per-command help with examples
```

**13 Recognized Sections**:
- AI ASSISTANT CONTEXT
- EXAMPLES
- COMMON WORKFLOWS
- TROUBLESHOOTING
- And more...

---

## Output Databases

All analysis stored in `.pf/` directory:

| Database | Contents |
|----------|----------|
| `repo_index.db` | Symbols, calls, imports, findings |
| `graphs.db` | Dependency graph, call graph |
| `fce.db` | Vector convergence data |
| `ml/session_history.db` | AI session analysis |
| `planning.db` | Task management |

---

## Performance

| Codebase Size | Index Time | Query Time | RAM |
|---------------|------------|------------|-----|
| <5K LOC | ~5s | <10ms | ~100MB |
| 20K LOC | ~15s | <50ms | ~200MB |
| 100K+ LOC | ~60s | <100ms | ~500MB |

**Optimizations**:
- SQLite WAL mode for concurrent reads
- 64MB cache for hot data
- Recursive CTEs instead of N+1 queries
- Batch operations where possible

---

## Configuration

### `.pf/config.yaml`

```yaml
analysis:
  max_file_size: 1048576  # 1MB
  exclude_patterns:
    - "node_modules/**"
    - "**/*.min.js"
    - ".git/**"

linters:
  enabled:
    - ruff
    - eslint
    - mypy

ml:
  enable_git_features: true
  session_directory: "~/.claude/projects/"
```

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/yourorg/theauditor.git
cd theauditor
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy theauditor

# Linting
ruff check theauditor
```

---

## License

AGPL-3.0 - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

Built with:
- [Python AST](https://docs.python.org/3/library/ast.html) - Native Python parsing
- [TypeScript Compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API) - Semantic JavaScript/TypeScript analysis
- [tree-sitter](https://tree-sitter.github.io/tree-sitter/) - Go, Rust, Bash structural parsing
- [Rich](https://rich.readthedocs.io/) - Terminal output
- [Click](https://click.palletsprojects.com/) - CLI framework
- [scikit-learn](https://scikit-learn.org/) - ML models
- [SQLite](https://sqlite.org/) - The world's most deployed database

---
