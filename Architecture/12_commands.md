# TheAuditor CLI Commands Overview

## Summary

**36 active commands** across **9 functional categories**, managed through Rich-formatted help with categorized panels.

---

## Full Command List

| # | Command | Category | Description |
|---|---------|----------|-------------|
| 1 | `setup-ai` | PROJECT_SETUP | Create isolated analysis environment |
| 2 | `tools` | PROJECT_SETUP | Tool detection and verification |
| 3 | `full` | CORE_ANALYSIS | Run complete audit pipeline |
| 4 | `workset` | CORE_ANALYSIS | Compute targeted file subset |
| 5 | `detect-patterns` | SECURITY | Detect 100+ security patterns |
| 6 | `detect-frameworks` | SECURITY | Display detected frameworks |
| 7 | `taint` | SECURITY | IFDS taint analysis |
| 8 | `boundaries` | SECURITY | Security boundary analysis |
| 9 | `rules` | SECURITY | Inspect detection rules |
| 10 | `docker-analyze` | SECURITY | Dockerfile security |
| 11 | `terraform` | SECURITY | Terraform IaC security |
| 12 | `cdk` | SECURITY | AWS CDK security |
| 13 | `workflows` | SECURITY | GitHub Actions security |
| 14 | `deps` | DEPENDENCIES | Dependency analysis |
| 15 | `docs` | DEPENDENCIES | Documentation fetching |
| 16 | `lint` | CODE_QUALITY | Run linters |
| 17 | `cfg` | CODE_QUALITY | Control flow analysis |
| 18 | `graph` | CODE_QUALITY | Dependency graphs |
| 19 | `graphql` | CODE_QUALITY | GraphQL schema analysis |
| 20 | `deadcode` | CODE_QUALITY | Dead code detection |
| 21 | `fce` | DATA_REPORTING | Factual Correlation Engine |
| 22 | `metadata` | DATA_REPORTING | Churn and coverage |
| 23 | `blueprint` | DATA_REPORTING | Architecture visualization |
| 24 | `query` | ADVANCED_QUERIES | Database query API |
| 25 | `explain` | ADVANCED_QUERIES | Symbol/file context |
| 26 | `impact` | ADVANCED_QUERIES | Blast radius analysis |
| 27 | `refactor` | ADVANCED_QUERIES | Refactoring impact |
| 28 | `context` | ADVANCED_QUERIES | Semantic rule application |
| 29 | `insights` | INSIGHTS_ML | Insight generation |
| 30 | `learn` | INSIGHTS_ML | Train ML models |
| 31 | `suggest` | INSIGHTS_ML | ML-based suggestions |
| 32 | `learn-feedback` | INSIGHTS_ML | Human feedback for ML |
| 33 | `session` | INSIGHTS_ML | AI session analysis |
| 34 | `planning` | UTILITIES | Planning system |
| 35 | `manual` | UTILITIES | Documentation system |
| 36 | `_archive` | INTERNAL | Artifact segregation |

---

## Command Groups (with Subcommands)

### `session` - AI Agent Analysis
- `analyze` - Parse and store sessions
- `report` - Detailed analysis report
- `inspect` - Single session deep-dive
- `activity` - Work/talk ratios
- `list` - List available sessions

### `graph` - Dependency Analysis
- `build` - Construct graphs
- `analyze` - Cycles, hotspots
- `query` - Interactive queries
- `viz` - Visualizations

### `cfg` - Control Flow
- `analyze` - Complexity analysis
- `viz` - DOT diagrams

### `terraform`/`cdk`/`workflows`
- `analyze` - Run security rules
- `report` - Generate reports

---

## Usage Patterns

### Initial Audit
```bash
aud setup-ai --target .
aud full --offline
aud blueprint --structure
aud taint
```

### Incremental Review
```bash
aud workset --diff main..HEAD
aud lint --workset
aud impact --symbol changedFunction
```

### Security Deep Dive
```bash
aud explain src/auth.ts
aud query --symbol loginHandler --show-callers
aud boundaries --type input-validation
aud taint --severity high
```

### Architecture Review
```bash
aud blueprint --structure
aud graph analyze
aud deadcode
aud metadata churn --days 30
```

### ML-Driven Analysis
```bash
aud learn --session-dir ~/.claude/projects/
aud suggest
```

---

## Performance

| Command | Typical Time | Dependencies |
|---------|--------------|--------------|
| `full` | 2-10 min | Network (first run) |
| `full --offline` | 1-5 min | Local only |
| `workset` | 1-3 sec | repo_index.db |
| `query` | <1 sec | repo_index.db |
| `explain` | 1-5 sec | repo_index.db |
| `taint` | 30-60 sec | repo_index.db |
| `lint --workset` | 5-15 sec | External linters |

---

## Database Requirements

**repo_index.db** (~181MB): Required by most commands
- query, explain, impact, refactor, context
- taint, boundaries, deadcode, fce
- All security scanning commands

**graphs.db** (~126MB): Required by graph commands only
- graph query, graph viz
- Impact analysis (optional enhancement)

---

## Rich Help System

```bash
aud --help          # 9 colored category panels
aud <cmd> --help    # Per-command Rich sections:
                    # - AI ASSISTANT CONTEXT
                    # - EXAMPLES
                    # - COMMON WORKFLOWS
                    # - OUTPUT FILES
                    # - RELATED COMMANDS
```

---

## Manual Command

AI-friendly searchable documentation:
```bash
aud manual --list           # List concepts
aud manual fce              # Explain FCE
aud manual --search keyword # Search docs
```
