# Tasks: Manual System Content Optimization

## Execution Model

```
┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
│ Track 1 │ Track 2 │ Track 3 │ Track 4 │ Track 5 │ Track 6 │
│Security │ Graph   │Analysis │  Infra  │  IaC    │Advanced │
│7 topics │7 topics │7 topics │7 topics │7 topics │7 topics │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
     │         │         │         │         │         │
     └─────────┴─────────┴─────────┴─────────┴─────────┘
                              │
                    All 6 run in parallel
                              │
                    ┌─────────┴─────────┐
                    │   Final Review    │
                    │   (Sequential)    │
                    └───────────────────┘
```

**Each track is 100% independent. No dependencies between tracks.**

---

## Pre-Work: Agent System Review (ALL TRACKS)

Before touching ANY topic, each AI team MUST:

1. **Read ALL agent files:**
   - `.auditor_venv/.theauditor_tools/agents/AGENTS.md`
   - `.auditor_venv/.theauditor_tools/agents/planning.md`
   - `.auditor_venv/.theauditor_tools/agents/refactor.md`
   - `.auditor_venv/.theauditor_tools/agents/security.md`
   - `.auditor_venv/.theauditor_tools/agents/dataflow.md`

2. **Understand the DATABASE-FIRST philosophy:**
   - `aud full` creates the database
   - All analysis reads from `.pf/repo_index.db`
   - Graph commands use `.pf/graphs.db`
   - Never analyze without indexing first

3. **Manual Entry Structure (REQUIRED for each topic):**
```
TOPIC: <name>

WHAT IT IS:
  One paragraph explaining the concept

WHEN TO USE IT:
  - Scenario 1: ...
  - Scenario 2: ...

HOW TO USE IT (Step-by-Step):
  PREREQUISITES:
    aud full                    # Always start with database

  STEPS:
    1. [First action]
    2. [Second action]
    3. [Third action]

  EXAMPLE:
    aud <command> --options     # With comments

COMBINING WITH OTHER TOOLS:
  - After this, consider running: ...
  - Works well with: ...

RELATED:
  Commands: aud <cmd1>, aud <cmd2>
  Topics: aud manual <topic1>, aud manual <topic2>

COMMON MISTAKES:
  - Mistake 1: ... → Solution: ...
  - Mistake 2: ... → Solution: ...
```

---

## Track 1: Security Concepts

**AI Team 1 Assignment**
**Topics:** 6

### Topics to Process

| Topic | Current State | Target |
|-------|---------------|--------|
| taint | Concept explanation | Full workflow: how to run taint analysis end-to-end |
| patterns | Pattern list | How to understand and use pattern detection |
| severity | Classification | How severity affects prioritization workflow |
| boundaries | Distance concept | How to measure trust boundaries step-by-step |
| rules | Rule list | How to create custom rules, load them, verify |
| fce | Correlation concept | How to use FCE to find compound vulns |

### Per-Topic Tasks

**taint**
- [ ] Read agent files for taint workflow context
- [ ] Verify: Does taint analysis actually work this way?
- [ ] Add step-by-step: "How to find SQL injection"
- [ ] Add step-by-step: "How to trace user input to dangerous sinks"
- [ ] Include actual command sequence with expected output
- [ ] Cross-reference with `aud taint --help`

**patterns**
- [ ] List all pattern categories with examples
- [ ] Show how to run pattern detection
- [ ] Explain output interpretation
- [ ] Link to rules topic for customization

**severity**
- [ ] Explain the severity levels (CRITICAL, HIGH, MEDIUM, LOW)
- [ ] Show how to filter by severity
- [ ] Explain prioritization workflow

**boundaries**
- [ ] Explain trust boundary concept
- [ ] Step-by-step distance measurement
- [ ] How to interpret boundary violations

**rules**
- [ ] How to list built-in rules
- [ ] How to create custom rules
- [ ] How to load custom rule files
- [ ] Testing and validation workflow

**fce**
- [ ] Explain correlation engine
- [ ] Step-by-step: running FCE after indexing
- [ ] How to interpret correlated findings

### Track 1 Verification Checkpoint
```bash
# Verify commands work as documented
aud taint --help              # Taint analysis command
aud detect-patterns --help    # Pattern detection command
aud boundaries --help         # Boundary analysis command
aud manual taint              # Manual topic renders correctly
# NOTE: FCE is NOT a standalone command - it runs as part of `aud full` pipeline
# To see FCE results: aud blueprint --taint (reads from database)
```

---

## Track 2: Graph/Architecture

**AI Team 2 Assignment**
**Topics:** 7

### Topics to Process

| Topic | Current State | Target |
|-------|---------------|--------|
| callgraph | Concept | How to build and query call graphs |
| dependencies | Concept | How to analyze package dependencies |
| graph | Command overview | Full graph workflow from build to viz |
| cfg | Control flow concept | How to analyze function complexity |
| architecture | System overview | How TheAuditor's pipeline works |
| blueprint | Visualization | How to get architectural overview |
| impact | Blast radius | How to measure change impact |

### Per-Topic Tasks

**callgraph**
- [ ] How to build call graph: `aud graph build`
- [ ] How to query: `aud graph query --symbol X --show-callers`
- [ ] How to visualize: `aud graph viz`
- [ ] Interpretation examples

**dependencies**
- [ ] Package vs code dependencies distinction
- [ ] How to check for vulnerabilities
- [ ] How to find outdated packages
- [ ] Upgrade workflow

**graph**
- [ ] Complete workflow: build → query → viz
- [ ] Different graph types (import, call, data flow)
- [ ] When to use each

**cfg**
- [ ] How to analyze function complexity
- [ ] Interpreting cyclomatic complexity
- [ ] Finding dead code paths

**architecture**
- [ ] TheAuditor's 4-stage pipeline explained
- [ ] How data flows through the system
- [ ] Database schema overview

**blueprint**
- [ ] Different modes (--structure, --files, etc.)
- [ ] When to use blueprint vs other commands
- [ ] How to drill down

**impact**
- [ ] How to measure blast radius of a change
- [ ] Step-by-step impact analysis
- [ ] Combining with workset

### Track 2 Verification Checkpoint
```bash
aud graph build --help
aud graph query --help
aud blueprint --help
aud impact --help
```

---

## Track 3: Code Analysis

**AI Team 3 Assignment**
**Topics:** 7

### Topics to Process

| Topic | Current State | Target |
|-------|---------------|--------|
| deadcode | Detection concept | Full workflow: find and remove dead code |
| refactor | Detection concept | Full workflow: detect incomplete refactorings |
| workset | File subset concept | How to scope analysis to specific files |
| context | Classification | How to apply business logic rules |
| explain | Symbol lookup | How to get full context on any symbol |
| query | SQL access | How to query the database directly |
| lint | Multi-linter | How to run and normalize linter output |

### Per-Topic Tasks

**deadcode**
- [ ] Step-by-step: finding unused modules
- [ ] Understanding confidence levels
- [ ] Verifying findings before deletion
- [ ] Integration with refactor workflow

**refactor**
- [ ] Creating custom refactor rules YAML
- [ ] Running detection
- [ ] Interpreting migration issues
- [ ] Remediation workflow

**workset**
- [ ] Creating worksets from git diff
- [ ] Expanding dependencies
- [ ] Scoping analysis to PR changes

**context**
- [ ] Business logic rule format
- [ ] Classification workflow
- [ ] Finding findings in specific contexts

**explain**
- [ ] Getting full context on a file
- [ ] Getting full context on a symbol
- [ ] When to use explain vs query

**query**
- [ ] Direct SQL query examples
- [ ] Common query patterns
- [ ] Table structure reference

**lint**
- [ ] Supported linters
- [ ] Running and normalizing output
- [ ] Combining with other analysis

### Track 3 Verification Checkpoint
```bash
aud deadcode --help
aud refactor --help
aud workset --help
aud query --help
aud explain --help
```

---

## Track 4: Infrastructure

**AI Team 4 Assignment**
**Topics:** 7

### Topics to Process

| Topic | Current State | Target |
|-------|---------------|--------|
| pipeline | Stage overview | Complete pipeline explanation with timing |
| overview | Tool intro | What TheAuditor is and primary use cases |
| database | Schema reference | How to query the database, table guide |
| env-vars | Config options | All environment variables with examples |
| exit-codes | Code meanings | How to interpret exit codes in CI/CD |
| troubleshooting | Error solutions | Common errors and fixes |
| setup | Installation | Complete setup workflow |

### Per-Topic Tasks

**pipeline**
- [ ] All 20 phases explained
- [ ] What happens in each stage
- [ ] Timing expectations by codebase size
- [ ] How to skip stages

**overview**
- [ ] What TheAuditor does (for AI context)
- [ ] Primary use cases
- [ ] Quick start workflow

**database**
- [ ] Table-by-table reference
- [ ] Common query patterns
- [ ] Direct SQL examples
- [ ] WARNING: Use Python, not sqlite3 command

**env-vars**
- [ ] All environment variables
- [ ] Effect of each
- [ ] Recommended settings

**exit-codes**
- [ ] All exit codes with meanings
- [ ] CI/CD interpretation
- [ ] Scripting examples

**troubleshooting**
- [ ] Common errors by category
- [ ] Solutions for each
- [ ] How to debug

**setup**
- [ ] Initial installation
- [ ] Agent setup
- [ ] Verification steps

### Track 4 Verification Checkpoint
```bash
aud full --help
aud setup-ai --help
aud manual pipeline
aud manual database
```

---

## Track 5: Integrations

**AI Team 5 Assignment**
**Topics:** 7

### Topics to Process

| Topic | Current State | Target |
|-------|---------------|--------|
| docker | Container analysis | Full Dockerfile security workflow |
| terraform | IaC analysis | Full Terraform security workflow |
| cdk | AWS CDK | Full CDK security workflow |
| graphql | Schema mapping | GraphQL SDL to resolver mapping |
| workflows | CI/CD | GitHub Actions security analysis |
| frameworks | Detection | Framework identification workflow |
| docs | Documentation | Doc fetching and caching |

### Per-Topic Tasks

**docker**
- [ ] How to analyze Dockerfiles
- [ ] What security issues are detected
- [ ] Remediation guidance
- [ ] Integration with CI/CD

**terraform**
- [ ] Analyzing Terraform configs
- [ ] Detecting misconfigurations
- [ ] Resource provisioning analysis
- [ ] Compliance checking

**cdk**
- [ ] CDK construct detection
- [ ] Security analysis
- [ ] Supported languages (Python, TS, JS)

**graphql**
- [ ] SDL schema extraction
- [ ] Resolver mapping
- [ ] Security analysis

**workflows**
- [ ] GitHub Actions analysis
- [ ] Security checks
- [ ] Secret detection

**frameworks**
- [ ] How detection works
- [ ] Supported frameworks list
- [ ] Using framework info in analysis

**docs**
- [ ] Doc fetching workflow
- [ ] Caching behavior
- [ ] AI context preparation

### Track 5 Verification Checkpoint
```bash
aud docker-analyze --help         # Docker security analysis
aud terraform provision --help    # Terraform provisioning graph (not "analyze")
aud cdk analyze --help            # CDK security analysis
aud detect-frameworks --help      # Framework detection
# NOTE: Terraform uses "provision" subcommand, not "analyze"
```

---

## Track 6: Advanced/ML

**AI Team 6 Assignment**
**Topics:** 7

### Topics to Process

| Topic | Current State | Target |
|-------|---------------|--------|
| planning | Task management | Full planning workflow with database |
| session | Session analysis | ML training from sessions |
| ml | Machine learning | Risk prediction workflow |
| metadata | Git metrics | Churn and coverage analysis |
| deps | Dependencies | Full dependency analysis workflow |
| tools | Tool management | Managing installed analysis tools |
| rust | Rust support | Rust-specific analysis features |

### Per-Topic Tasks

**planning**
- [ ] Database-centric task management
- [ ] Spec-based verification
- [ ] Full planning workflow
- [ ] Integration with aud full

**session**
- [ ] Session capture and analysis
- [ ] Quality metrics
- [ ] ML training data preparation

**ml**
- [ ] Risk prediction training
- [ ] Using predictions
- [ ] Feedback loop

**metadata**
- [ ] Git churn analysis
- [ ] Test coverage metrics
- [ ] Risk correlation

**deps**
- [ ] Full dependency workflow
- [ ] Vulnerability scanning
- [ ] Update recommendations

**tools**
- [ ] Managing installed tools
- [ ] Version verification
- [ ] Installation guidance

**rust**
- [ ] Rust-specific features
- [ ] Module analysis
- [ ] Unsafe code detection
- [ ] Trait and impl block handling

### Track 6 Verification Checkpoint
```bash
aud planning --help
aud session analyze --help
aud learn --help
aud deps --help
aud tools list --help
```

---

## Final Review Phase (Sequential - After All Tracks Complete)

### Cross-Track Consistency Check
- [x] All topics follow same structure (42/42 render correctly)
- [x] All topics include workflow steps (verified across all tracks)
- [x] All topics reference prerequisites correctly
- [x] All cross-references are valid

### Agent System Alignment
- [x] Manual workflows match agent protocols
- [x] No contradictions between manual and agents
- [x] All agent-relevant topics reference agent files (20+ references in lib01, 45+ in lib02)

### Full Verification
```bash
# Verify all topics render - PASSED 2024-12-05
# All 42 topics: OK
```

### Final Documentation
- [x] Update tasks.md with completion status
- [x] Create summary of changes made (see below)

---

## Completion Summary (2024-12-05)

### All Tracks Complete

| Track | Topics | Status | Files Modified |
|-------|--------|--------|----------------|
| 1 | 6 | COMPLETE | manual_lib01.py (taint, fce, patterns, severity), manual_lib02.py (boundaries, rules) |
| 2 | 7 | COMPLETE | manual_lib01.py (callgraph, cfg, impact, architecture), manual_lib02.py (graph, blueprint, dependencies) |
| 3 | 7 | COMPLETE | manual_lib01.py (workset, context), manual_lib02.py (deadcode, refactor, explain, query, lint) |
| 4 | 7 | COMPLETE | manual_lib01.py (pipeline, overview, gitflows, exit-codes, env-vars, database, troubleshooting), manual_lib02.py (setup) |
| 5 | 7 | COMPLETE | manual_lib02.py (docker, terraform, cdk, graphql, frameworks, docs, workflows) |
| 6 | 7 | COMPLETE | manual_lib01.py (rust, insights), manual_lib02.py (planning, session, ml, metadata, deps, tools) |
| **Total** | **42** | **COMPLETE** | |

### Additional Improvements
- `aud manual` now shows styled welcome page with categorized topics
- `aud explain` now shows styled welcome page when no target provided
- All topics verified to render with Rich formatting
- Agent workflow references added to security-related topics

### File Statistics
| File | Lines | Topics |
|------|-------|--------|
| manual.py | 346 | 0 (formatter + welcome page) |
| manual_lib01.py | 1758 | 21 |
| manual_lib02.py | 1890 | 21 |
| **Total** | **3994** | **42** |
