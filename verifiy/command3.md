# CLI Audit Report: Commands 23-34
**Auditor**: Sub-Agent 2 (Opus AI)
**Date**: 2025-10-26

## Executive Summary

This audit examines 12 CLI commands (ml.py through workset.py) representing TheAuditor's advanced analysis and operational features. The audit reveals significant inconsistency in help text quality: some commands have exceptional AI-first documentation (query.py at 990 lines), while others have minimal help (tool_versions.py at 25 lines). Overall, 4 commands meet AI-first standards, 5 need improvement, and 3 are poorly documented.

**Key Findings**:
1. **query.py** sets the gold standard with comprehensive docstrings explaining WHY, WHEN, HOW, and ARCHITECTURE
2. **taint.py** demonstrates excellent help with security-focused context and actionable recommendations
3. **refactor.py, report.py, rules.py, summary.py** lack critical context about their purpose in the analysis pipeline
4. **tool_versions.py** has almost no help documentation (9 lines total)

---

## Detailed Audit

### Command: `aud learn`
**File**: theauditor/commands/ml.py
**Primary Help**: "Train ML models from audit artifacts to predict risk and root causes."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db-path | option | "Database path" | 8 |
| --manifest | option | "Manifest file path" | 9 |
| --journal | option | "Journal file path" | 10 |
| --fce | option | "FCE file path" | 11 |
| --ast | option | "AST proofs file path" | 12 |
| --enable-git | flag | "Enable git churn features" | 13 |
| --model-dir | option | "Model output directory" | 14 |
| --window | option | "Journal window size" | 15 |
| --seed | option | "Random seed" | 16 |
| --feedback | option | "Path to human feedback JSON file" | 17 |
| --train-on | choice | "Type of historical runs to train on" | 18 |
| --print-stats | flag | "Print training statistics" | 19 |

---

### Command: `aud suggest`
**File**: theauditor/commands/ml.py
**Primary Help**: "Generate ML-based suggestions for risky files and likely root causes."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db-path | option | "Database path" | 58 |
| --manifest | option | "Manifest file path" | 59 |
| --workset | option | "Workset file path" | 60 |
| --fce | option | "FCE file path" | 61 |
| --ast | option | "AST proofs file path" | 62 |
| --model-dir | option | "Model directory" | 63 |
| --topk | option | "Top K files to suggest" | 64 |
| --out | option | "Output file path" | 65 |
| --print-plan | flag | "Print suggestions to console" | 66 |

---

### Command: `aud learn-feedback`
**File**: theauditor/commands/ml.py
**Primary Help**: "Re-train models with human feedback for improved accuracy. The feedback file should be a JSON file with the format: {\"path/to/file.py\": {\"is_risky\": true, \"is_root_cause\": false, \"will_need_edit\": true}, ...}"

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --feedback-file | option | "Path to feedback JSON file" (REQUIRED) | 97 |
| --db-path | option | "Database path" | 98 |
| --manifest | option | "Manifest file path" | 99 |
| --model-dir | option | "Model output directory" | 100 |
| --train-on | choice | "Type of historical runs to train on" | 101 |
| --print-stats | flag | "Print training statistics" | 102 |

---

### Command: `aud query`
**File**: theauditor/commands/query.py
**Primary Help**: "Query code relationships from indexed database for AI-assisted refactoring. WHAT THIS DOES: Direct SQL queries over TheAuditor's indexed code relationships. NO file reading, NO parsing, NO inference - just exact database lookups. Perfect for AI assistants to understand code without burning tokens..."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --symbol | option | "Query symbol by exact name (functions, classes, variables)" | 18 |
| --file | option | "Query file by path (partial match supported)" | 19 |
| --api | option | "Query API endpoint by route pattern (supports wildcards)" | 20 |
| --component | option | "Query React/Vue component by name" | 21 |
| --variable | option | "Query variable by name (for data flow tracing)" | 22 |
| --pattern | option | "Search symbols by pattern (supports % wildcards like 'auth%')" | 23 |
| --category | option | "Search by security category (jwt, oauth, password, sql, xss, auth)" | 24 |
| --search | option | "Cross-table exploratory search (finds term across all tables)" | 25 |
| --show-callers | flag | "Show who calls this symbol (control flow incoming)" | 26 |
| --show-callees | flag | "Show what this symbol calls (control flow outgoing)" | 27 |
| --show-dependencies | flag | "Show what this file imports (outgoing dependencies)" | 28 |
| --show-dependents | flag | "Show who imports this file (incoming dependencies)" | 29 |
| --show-tree | flag | "Show component hierarchy tree (parent-child relationships)" | 30 |
| --show-hooks | flag | "Show React hooks used by component" | 31 |
| --show-data-deps | flag | "Show data dependencies (what vars function reads/writes) - DFG" | 32 |
| --show-flow | flag | "Show variable flow through assignments (def-use chains) - DFG" | 33 |
| --show-taint-flow | flag | "Show cross-function taint flow (returns -> assignments) - DFG" | 34 |
| --show-api-coverage | flag | "Show API security coverage (auth controls per endpoint)" | 35 |
| --type-filter | option | "Filter pattern search by symbol type (function, class, variable)" | 36 |
| --include-tables | option | "Comma-separated tables for cross-table search" | 37 |
| --depth | option | "Traversal depth for transitive queries (1-5, default=1)" | 38 |
| --format | choice | "Output format: text (human), json (AI), tree (visual)" | 39-40 |
| --save | option | "Save output to file (auto-creates parent dirs)" | 42 |

---

### Command: `aud refactor`
**File**: theauditor/commands/refactor.py
**Primary Help**: "Analyze refactoring impact and find inconsistencies. This command helps detect issues introduced by refactoring such as: - Data model changes (fields moved between tables) - API contract mismatches (frontend expects old structure) - Missing updates in dependent code - Cross-stack inconsistencies"

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --file / -f | option | "File to analyze refactoring impact from" | 18 |
| --line / -l | option | "Line number in the file" | 19 |
| --migration-dir / -m | option | "Directory containing database migrations" (default: backend/migrations) | 20-21 |
| --migration-limit / -ml | option | "Number of recent migrations to analyze (0=all, default=all)" | 22-23 |
| --expansion-mode / -e | choice | "Dependency expansion mode: none (affected only), direct (1 level), full (transitive)" | 24-27 |
| --auto-detect / -a | flag | "Auto-detect refactoring from recent migrations" | 28-29 |
| --workset / -w | flag | "Use current workset for analysis" | 30-31 |
| --output / -o | option | "Output file for detailed report" | 32-33 |

---

### Command: `aud report`
**File**: theauditor/commands/report.py
**Primary Help**: "Generate consolidated audit report from analysis artifacts. Aggregates findings from all analysis phases into AI-optimized chunks in the .pf/readthis/ directory. The report command is typically the final step after running various analysis commands."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --manifest | option | "Manifest file path" | 10 |
| --db | option | "Database path" | 11 |
| --workset | option | "Workset file path" | 12 |
| --capsules | option | "Capsules directory" | 13 |
| --run-report | option | "Run report file path" | 14 |
| --journal | option | "Journal file path" | 15 |
| --fce | option | "FCE file path" | 16 |
| --ast | option | "AST proofs file path" | 17 |
| --ml | option | "ML suggestions file path" | 18 |
| --patch | option | "Patch diff file path" | 19 |
| --out-dir | option | "Output directory for audit reports" | 20 |
| --max-snippet-lines | option | "Maximum lines per snippet" | 21 |
| --max-snippet-chars | option | "Maximum characters per line" | 22 |
| --print-stats | flag | "Print summary statistics" | 23 |

---

### Command: `aud rules`
**File**: theauditor/commands/rules.py
**Primary Help**: "Inspect and summarize TheAuditor's detection rules and patterns."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --summary | flag | "Generate a summary of all detection capabilities" | 18-22 |

---

### Command: `aud setup-ai`
**File**: theauditor/commands/setup.py
**Primary Help**: "Setup sandboxed analysis tools and vulnerability databases. This command creates a complete sandboxed environment for TheAuditor: 1. Creates a Python venv at <target>/.auditor_venv 2. Installs TheAuditor into that venv (editable) 3. Sets up isolated JS/TS tools (ESLint, TypeScript) 4. Downloads OSV-Scanner binary for vulnerability detection 5. Downloads offline vulnerability databases (npm, PyPI)"

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --target | option | "Target project root (absolute or relative path)" (REQUIRED) | 11-13 |
| --sync | flag | "Force update (reinstall packages)" | 16-18 |
| --dry-run | flag | "Print plan without executing" | 21-23 |

---

### Command: `aud structure`
**File**: theauditor/commands/structure.py
**Primary Help**: "Generate comprehensive project structure and intelligence report. Creates a detailed markdown report optimized for AI assistants to quickly understand your codebase architecture, identify key files, and make informed decisions about where to focus attention."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory to analyze" | 11 |
| --manifest | option | "Path to manifest.json" | 12 |
| --db-path | option | "Path to repo_index.db" | 13 |
| --output | option | "Output file path" | 14 |
| --max-depth | option | "Maximum directory tree depth" | 15 |

---

### Command: `aud summary`
**File**: theauditor/commands/summary.py
**Primary Help**: "Generate comprehensive audit summary from all phases."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory" | 12 |
| --raw-dir | option | "Raw outputs directory" | 13 |
| --out | option | "Output path for summary" | 14 |

---

### Command: `aud taint-analyze`
**File**: theauditor/commands/taint.py
**Primary Help**: "Perform taint analysis to detect security vulnerabilities. This command traces the flow of untrusted data from taint sources (user inputs) to security sinks (dangerous functions) using: - Control Flow Graph (CFG) for path-sensitive analysis - Inter-procedural analysis to track data across function calls - Unified caching for performance optimization"

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db | option | "Path to the SQLite database (default: repo_index.db)" | 17 |
| --output | option | "Output path for analysis results" | 18 |
| --max-depth | option | "Maximum depth for taint propagation tracing" | 19 |
| --json | flag | "Output raw JSON instead of formatted report" | 20 |
| --verbose | flag | "Show detailed path information" | 21 |
| --severity | choice | "Filter results by severity level" | 22-23 |
| --rules/--no-rules | flag | "Enable/disable rule-based detection" | 24 |
| --use-cfg/--no-cfg | flag | "Use flow-sensitive CFG analysis (enabled by default)" | 25-26 |
| --memory/--no-memory | flag | "Use in-memory caching for 5-10x performance (enabled by default)" | 27-28 |
| --memory-limit | option | "Memory limit for cache in MB (auto-detected based on system RAM if not set)" | 29-30 |

---

### Command: `aud terraform`
**File**: theauditor/commands/terraform.py
**Primary Help**: "Analyze Terraform Infrastructure as Code. Provides infrastructure security analysis, provisioning flow tracking, and blast radius assessment for Terraform configurations."

**Subcommands:**
- `provision` (line 56): "Build Terraform provisioning flow graph"
- `analyze` (line 185): "Analyze Terraform for security issues"
- `report` (line 293): "Generate Terraform security report" [NOT YET IMPLEMENTED]

**Options/Arguments (provision):**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory to analyze" | 57 |
| --workset | flag | "Build graph for workset files only" | 58 |
| --output | option | "Output JSON path" | 59 |
| --db | option | "Source database path" | 60 |
| --graphs-db | option | "Graph database path" | 61 |

**Options/Arguments (analyze):**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory to analyze" | 186 |
| --severity | choice | "Minimum severity to report" | 187 |
| --categories | option | "Specific categories to check" | 188 |
| --output | option | "Output JSON path" | 189 |
| --db | option | "Database path" | 190 |

**Options/Arguments (report):**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --format | choice | "Output format" | 294 |
| --output | option | "Output file path (stdout if not specified)" | 295 |
| --severity | choice | "Minimum severity to report" | 296 |

---

### Command: `aud tool-versions`
**File**: theauditor/commands/tool_versions.py
**Primary Help**: "Detect and record tool versions."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --out-dir | option | "Output directory" | 7 |

---

### Command: `aud workset`
**File**: theauditor/commands/workset.py
**Primary Help**: "Identify files to analyze based on changes or patterns. A workset is a focused subset of files for targeted analysis. Instead of analyzing your entire codebase every time, workset identifies only the files that matter for your current task. It automatically includes dependent files that could be affected by changes."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory" | 9 |
| --db | option | "Input SQLite database path" | 10 |
| --manifest | option | "Input manifest file path" | 11 |
| --all | flag | "Include all source files (ignores common directories)" | 12 |
| --diff | option | "Git diff range (e.g., main..HEAD)" | 13 |
| --files | option | "Explicit file list" (multiple) | 14 |
| --include | option | "Include glob patterns" (multiple) | 15 |
| --exclude | option | "Exclude glob patterns" (multiple) | 16 |
| --max-depth | option | "Maximum dependency depth" | 17 |
| --out | option | "Output workset file path" | 18 |
| --print-stats | flag | "Print summary statistics" | 19 |

---

## AI-First Standard Critique

### Command: `aud learn` - ⚠️ NEEDS_IMPROVEMENT

**Purpose**: ✅ Clear - trains ML models from audit artifacts
**Context**: ❌ Missing - doesn't explain WHEN to use vs `suggest` or why ML is beneficial
**AI-Usable Examples**: ❌ None provided in help text
**Option Rationale**: ⚠️ Partial - options listed but consequences unclear (e.g., what does `--enable-git` actually add?)
**Interactions**: ❌ No mention of prerequisite commands or workflow order

**Issues:**
- No explanation of what "journal window size" means or how to choose it
- `--train-on` choices (full, diff, all) not explained
- Missing workflow context (when to use this vs `learn-feedback`)
- No examples of typical usage patterns

---

### Command: `aud suggest` - ⚠️ NEEDS_IMPROVEMENT

**Purpose**: ✅ Clear - generates ML-based suggestions
**Context**: ❌ Missing - doesn't explain relationship to `learn` command
**AI-Usable Examples**: ❌ None provided
**Option Rationale**: ⚠️ Partial - `--topk` explained but not `--print-plan`
**Interactions**: ❌ No mention of prerequisite `aud learn`

**Issues:**
- Doesn't explain that models must be trained first (`aud learn`)
- No guidance on interpreting suggestions
- Missing examples of how to use output

---

### Command: `aud learn-feedback` - ⚠️ NEEDS_IMPROVEMENT

**Purpose**: ✅ Clear - re-train models with human feedback
**Context**: ⚠️ Partial - shows JSON format but not WHEN to use feedback loop
**AI-Usable Examples**: ✅ JSON schema provided in docstring
**Option Rationale**: ❌ Missing - doesn't explain why you'd change `--train-on`
**Interactions**: ❌ No mention of workflow (learn → suggest → feedback → learn-feedback)

**Issues:**
- Excellent JSON schema example (lines 107-115)
- Missing explanation of feedback loop workflow
- No guidance on creating feedback file

---

### Command: `aud query` - ✅ GOOD (GOLD STANDARD)

**Purpose**: ✅✅✅ EXCEPTIONAL - 990 lines of documentation explaining WHAT, WHY, HOW, and ARCHITECTURE
**Context**: ✅✅✅ COMPREHENSIVE - explains token savings, accuracy improvements, speed benefits
**AI-Usable Examples**: ✅✅✅ EXTENSIVE - 50+ examples covering all query types
**Option Rationale**: ✅✅✅ DETAILED - every option has section explaining consequences and use cases
**Interactions**: ✅✅✅ COMPLETE - shows prerequisites, integration with other commands, workflows

**Highlights:**
- Lines 51-70: "WHY USE THIS" with concrete metrics (token savings, accuracy, speed)
- Lines 102-230: Detailed explanation of each query type with examples
- Lines 231-286: Action flags with database tables, use cases, and consequences
- Lines 287-326: Common workflows showing real-world usage patterns
- Lines 434-446: Database schema reference with table names and row counts
- Lines 685-756: Manual database query guide for advanced users
- Lines 778-842: Architecture deep dive for AI assistants

**This is the GOLD STANDARD for AI-first help documentation.**

---

### Command: `aud refactor` - ⚠️ NEEDS_IMPROVEMENT

**Purpose**: ✅ Clear - analyzes refactoring impact
**Context**: ⚠️ Partial - examples show WHAT but not WHEN
**AI-Usable Examples**: ✅ Good - lines 46-53 show 3 usage patterns
**Option Rationale**: ⚠️ Partial - expansion modes explained but migration-limit not
**Interactions**: ❌ Missing - doesn't explain relationship to `aud impact` or workflow order

**Issues:**
- Good examples but missing workflow context
- `--expansion-mode` choices explained inline but consequences unclear
- No explanation of when to use vs `aud impact --file --line`

---

### Command: `aud report` - ⚠️ NEEDS_IMPROVEMENT

**Purpose**: ✅ Clear - generates consolidated report
**Context**: ⚠️ Partial - mentions "final step" but not complete workflow
**AI-Usable Examples**: ✅ Good - lines 71-78 show typical workflow
**Option Rationale**: ❌ Missing - most options have no explanation (what is `--capsules`?)
**Interactions**: ⚠️ Partial - mentions "after running various analysis commands" but vague

**Issues:**
- Excellent chunking strategy documentation (lines 65-69)
- Missing explanation of most input file purposes
- Vague about which commands produce which inputs
- No guidance on interpreting output

---

### Command: `aud rules` - ❌ POOR

**Purpose**: ⚠️ Vague - "inspect and summarize" doesn't explain value
**Context**: ❌ Missing - no explanation of WHEN or WHY to use this
**AI-Usable Examples**: ❌ None
**Option Rationale**: ⚠️ Minimal - only one flag with generic description
**Interactions**: ❌ None

**Issues:**
- Minimal help (24 lines total)
- Doesn't explain what "detection capabilities" means
- No example output or use cases
- No explanation of why you'd want a capability report

---

### Command: `aud setup-ai` - ✅ GOOD

**Purpose**: ✅ Clear - setup sandboxed environment
**Context**: ✅ Good - explains benefits and initial setup time
**AI-Usable Examples**: ⚠️ Partial - shows workflow but not concrete commands
**Option Rationale**: ✅ Good - options explained with consequences
**Interactions**: ✅ Good - mentions "After setup, run: aud deps --vuln-scan"

**Highlights:**
- Lines 28-44: Clear numbered steps and benefits
- Lines 36-44: Honest about download size and time
- Line 46: Clear next step after setup

**Issues:**
- Missing example commands with actual paths

---

### Command: `aud structure` - ✅ GOOD

**Purpose**: ✅ Clear - generates project structure report
**Context**: ✅ Good - explains AI optimization and use cases
**AI-Usable Examples**: ✅ Good - lines 52-55 with 3 usage patterns
**Option Rationale**: ✅ Good - `--max-depth` explained with use case
**Interactions**: ✅ Good - mentions prerequisite `aud index` and output format

**Highlights:**
- Lines 23-45: Comprehensive report sections list
- Lines 61-80: Example output format
- Lines 81-85: Clear use cases
- Lines 87-91: Token estimation explanation

**Issues:**
- Could explain "critical files" detection algorithm

---

### Command: `aud summary` - ❌ POOR

**Purpose**: ⚠️ Vague - "comprehensive audit summary" too generic
**Context**: ❌ Missing - no explanation of WHEN to run this
**AI-Usable Examples**: ❌ None
**Option Rationale**: ❌ Missing - all options are just file paths with no context
**Interactions**: ❌ Missing - doesn't explain which commands produce inputs

**Issues:**
- Minimal help (15 lines total)
- No explanation of what goes into summary or output format
- No examples of usage or interpretation
- Doesn't explain relationship to `aud report`

---

### Command: `aud taint-analyze` - ✅ GOOD

**Purpose**: ✅ Clear - performs taint analysis for security vulns
**Context**: ✅ Good - explains techniques and detected issues
**AI-Usable Examples**: ✅ Good - lines 50-53 with 3 usage patterns
**Option Rationale**: ✅ Good - `--use-cfg`, `--memory` explained with benefits
**Interactions**: ✅ Good - shows prerequisite `aud index`

**Highlights:**
- Lines 32-47: Clear explanation of techniques and detected issues
- Lines 25-30: Good explanation of performance options
- Lines 360-385: Actionable recommendations based on severity

**Issues:**
- Could explain CFG vs non-CFG performance/accuracy tradeoffs more clearly

---

### Command: `aud terraform` - ✅ GOOD

**Purpose**: ✅ Clear - Terraform IaC analysis
**Context**: ✅ Good - explains workflow and outputs
**AI-Usable Examples**: ✅ Good - multiple examples per subcommand
**Option Rationale**: ✅ Good - options explained with use cases
**Interactions**: ✅ Good - clear workflow with numbered steps

**Highlights:**
- Lines 29-39: Clear workflow with 4 numbered steps
- Lines 62-96: Detailed `provision` help with prerequisites and graph structure
- Lines 192-212: Clear explanation of detected issues

**Issues:**
- `report` subcommand not yet implemented but documented (honesty is good)

---

### Command: `aud tool-versions` - ❌ POOR

**Purpose**: ✅ Clear but trivial - "detect and record tool versions"
**Context**: ❌ Missing - no explanation of WHY this matters
**AI-Usable Examples**: ❌ None
**Option Rationale**: ❌ Missing - single option with no context
**Interactions**: ❌ None

**Issues:**
- Minimal help (9 lines total)
- No explanation of what this is used for or when to run it
- No mention of what tools are detected

---

### Command: `aud workset` - ✅ GOOD

**Purpose**: ✅ Clear - identifies files for targeted analysis
**Context**: ✅✅ EXCELLENT - explains performance benefits and use cases
**AI-Usable Examples**: ✅✅ COMPREHENSIVE - 5 creation examples + 3 usage examples
**Option Rationale**: ✅ Good - options explained with patterns
**Interactions**: ✅✅ EXCELLENT - shows integration with other commands

**Highlights:**
- Lines 22-32: Clear use cases with concrete benefits (10-100x speedup)
- Lines 34-44: Comprehensive examples showing creation and usage together
- Lines 42-44: Integration examples with other commands
- Lines 49-53: Clear output structure explanation

**Issues:**
- None significant - this is well-documented

---

## Summary Statistics

- **Total commands audited**: 12
- **✅ GOOD**: 6 (query, setup-ai, structure, taint-analyze, terraform, workset)
- **⚠️ NEEDS_IMPROVEMENT**: 5 (learn, suggest, learn-feedback, refactor, report)
- **❌ POOR**: 3 (rules, summary, tool_versions)

---

## Key Findings

### 1. **Massive Documentation Quality Variance** (CRITICAL)
The variance between best (query.py - 990 lines) and worst (tool_versions.py - 9 lines) is 110x. This creates inconsistent user experience where some commands are self-explanatory while others require source code reading.

**Impact**: AI assistants will struggle with poorly documented commands, leading to incorrect usage and user frustration.

**Recommendation**: Establish minimum documentation standard (200 lines for complex commands, 50 lines for simple commands).

---

### 2. **Missing Workflow Context** (HIGH PRIORITY)
Commands like `learn`, `suggest`, `summary`, and `report` don't explain their place in the analysis pipeline. Users won't know:
- Which command to run first
- Which commands produce inputs for other commands
- When to use one command vs another

**Examples:**
- `aud summary` vs `aud report` - what's the difference?
- `aud learn` vs `aud learn-feedback` - when to use which?
- `aud refactor` vs `aud impact` - overlapping functionality?

**Recommendation**: Add "Workflow Context" section to every command showing:
```
Prerequisites: aud index, aud graph build
Produces: .pf/raw/summary.json (consumed by aud report)
Related: aud report (aggregates this + other outputs)
```

---

### 3. **query.py Sets Unrealistic Standard** (OBSERVATION)
While `query.py` is exceptional documentation (990 lines), it may be unrealistic to expect all commands to reach this level. However, it demonstrates valuable patterns:
- WHY USE THIS section with concrete metrics
- Multiple query types with dedicated sections
- 50+ examples covering all use cases
- Architecture deep dive for advanced users
- Manual database access guide

**Recommendation**: Extract documentation patterns from query.py into a "Documentation Template" that other commands can follow at smaller scale.

---

### 4. **Option Consequences Rarely Explained** (MEDIUM PRIORITY)
Most commands list options but don't explain:
- What happens if you enable/disable this flag?
- What's the performance/accuracy tradeoff?
- When would you use this vs default?

**Good Examples:**
- `query.py --depth`: Explains depth=1 vs depth=3 with performance numbers
- `taint.py --use-cfg`: Explains "Stage 3 (CFG multi-hop)" vs "Stage 2 (call-graph)"

**Bad Examples:**
- `learn.py --window`: What does "journal window size" mean? How to choose?
- `report.py --max-snippet-lines`: Why would you change from default 3?

**Recommendation**: Every option should answer: "What happens if I change this from the default?"

---

### 5. **ML Commands Lack Cohesive Documentation** (MEDIUM PRIORITY)
The three ML commands (`learn`, `suggest`, `learn-feedback`) are related but documented as isolated commands. Users need a unified "ML Workflow" explanation showing:
1. Run `aud learn` to train initial models
2. Run `aud suggest` to get predictions
3. Review suggestions and create feedback.json
4. Run `aud learn-feedback` to improve models
5. Repeat steps 2-4 iteratively

**Recommendation**: Add "ML WORKFLOW" section to all three commands with cross-references.

---

## Recommendations by Priority

### CRITICAL (Implement Immediately)
1. **Establish Minimum Documentation Standard**: All commands must have:
   - Purpose section (WHY this exists)
   - Context section (WHEN to use it)
   - At least 3 examples
   - Prerequisites and outputs
   - Related commands

2. **Fix the Minimal Three**: `rules`, `summary`, `tool_versions` are embarrassingly under-documented
   - `rules`: Add examples of output, explain use cases (200+ lines needed)
   - `summary`: Explain vs `report`, show output format, add examples (150+ lines)
   - `tool_versions`: Explain why this matters, what tools detected (80+ lines)

### HIGH PRIORITY (Implement This Sprint)
3. **Add Workflow Context to All Commands**: Every command should show:
   ```
   Prerequisites: [commands to run first]
   Produces: [output files]
   Consumed by: [commands that use this output]
   Related: [similar/alternative commands]
   ```

4. **Document ML Command Workflow**: Add unified ML workflow section to `learn`, `suggest`, `learn-feedback`

5. **Explain Option Consequences**: Every option should answer "What happens if I change this?"

### MEDIUM PRIORITY (Next Sprint)
6. **Create Documentation Template**: Extract patterns from `query.py` into reusable template

7. **Add Performance Metrics**: Where relevant (like `query.py`), show:
   - Typical execution time
   - Memory usage
   - Output size
   - Token consumption

8. **Cross-Reference Related Commands**: Add "See also:" sections linking related commands

---

## Exemplary Documentation Patterns (Learn From These)

### query.py - The Gold Standard
- **WHY USE THIS** section (lines 56-63) with concrete metrics
- **HOW IT WORKS** section (lines 65-69) with numbered steps
- **ARCHITECTURE** section (lines 71-89) showing query targets, actions, modifiers
- **QUERY TYPES EXPLAINED** (lines 102-230) with dedicated sections per type
- **COMMON WORKFLOWS** (lines 287-326) showing real-world usage
- **TROUBLESHOOTING** (lines 388-414) with error messages and fixes
- **EXAMPLES (COMPREHENSIVE)** (lines 452-492) covering all variations

### workset.py - Excellent Use Case Documentation
- **Use Cases** section (lines 28-32) with concrete benefits ("10-100x speedup")
- Integration examples (lines 42-44) showing how to use with other commands
- Clear output structure (lines 49-53)

### taint.py - Good Security Context
- Detection list (lines 41-47) showing what vulnerabilities are caught
- Performance options (lines 25-30) explaining tradeoffs
- Actionable recommendations (lines 360-385) based on severity

### structure.py - Good Report Format Preview
- Report sections (lines 23-45) showing exactly what to expect
- Example output (lines 61-80) with actual formatting
- Token estimation (lines 87-91) explaining AI context usage

---

## Final Assessment

TheAuditor's command documentation is **inconsistent but shows pockets of excellence**. The `query` command demonstrates world-class AI-first documentation, while `tool_versions` has almost no help. This creates a confusing user experience where some commands are self-documenting while others require source code archeology.

**Priority**: Raise the floor for poorly documented commands before raising the ceiling further. Users encountering `rules`, `summary`, or `tool_versions` will assume the entire tool is poorly documented, even though `query`, `workset`, and `structure` are excellent.

**Action**: Implement CRITICAL recommendations immediately to bring all commands to minimum viable documentation standard.
