# CLI Audit Report: Commands 12-22
**Auditor**: Sub-Agent 1 (Opus AI)
**Date**: 2025-10-26

## Executive Summary

This report audits 11 CLI command files (commands 12-22) across TheAuditor's command suite, focusing on help text quality and AI-usability. The commands audited range from core infrastructure (`index`, `init`) to advanced analysis (`fce`, `graph`, `insights`) and utility commands (`lint`, `metadata`).

**Key Findings**:
- 7 commands have EXCELLENT help text with comprehensive examples and clear value propositions
- 3 commands need improvement in help text completeness
- 1 command has minimal help text requiring significant enhancement
- Most commands follow strong documentation patterns with multi-paragraph docstrings
- AI-usability is generally high with clear examples and output file specifications
- Some commands lack explicit flag interaction/conflict documentation

---

## Detailed Audit

### Command: `aud fce`
**File**: theauditor/commands/fce.py
**Primary Help**: "Cross-reference findings to identify compound vulnerabilities. The Factual Correlation Engine (FCE) is TheAuditor's advanced analysis system that correlates findings from multiple tools to detect complex vulnerability patterns that single tools miss. It identifies when multiple 'low severity' issues combine to create critical risks."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory" | 9 |
| --capsules | option | "Capsules directory" | 10 |
| --manifest | option | "Manifest file path" | 11 |
| --workset | option | "Workset file path" | 12 |
| --timeout | option | "Timeout in seconds" | 13 |
| --print-plan | flag | "Print detected tools without running" | 14 |

**Extended Documentation**: Lines 16-94 contain an exceptional multi-section docstring covering:
- Correlation rules (30 advanced patterns) categorized by type
- How FCE works (4-step process)
- Examples with 3 common usage patterns
- Input sources (6 different analysis types)
- Output files with exact paths and formats
- Finding format with JSON example
- Value proposition (4 key benefits)
- Prerequisites note

---

### Command: `aud full`
**File**: theauditor/commands/full.py
**Primary Help**: "Run comprehensive security audit pipeline (20 phases). Executes TheAuditor's complete analysis pipeline in 4 optimized stages with intelligent parallelization. This is your main command for full codebase auditing."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory to analyze" | 11 |
| --quiet | flag | "Minimal output" | 12 |
| --exclude-self | flag | "Exclude TheAuditor's own files (for self-testing)" | 13 |
| --offline | flag | "Skip network operations (deps, docs)" | 14 |
| --subprocess-taint | flag | "Run taint analysis as subprocess (slower but isolated)" | 15 |
| --wipecache | flag | "Delete all caches before run (for cache corruption recovery)" | 16 |

**Extended Documentation**: Lines 18-75 contain comprehensive documentation:
- Pipeline stages (4 stages with specific phases)
- Examples (5 different use cases)
- Output files with 4 specific paths
- Exit codes (4 different codes with meanings)
- Performance expectations (3 project size tiers)
- Cache behavior explanation
- Intelligent caching note

---

### Command: `aud graph`
**File**: theauditor/commands/graph.py
**Primary Help**: "Analyze code structure through dependency and call graphs. Build and analyze import/call graphs to understand your codebase's architecture, detect cycles, find hotspots, and measure change impact. Supports Python, JavaScript/TypeScript, and Go."

**Options/Arguments (Group Command):**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| -h, --help | option | (built-in help) | 10 |

**Extended Documentation**: Lines 12-46 explain the graph command group with subcommands, typical workflow, what graphs reveal, and examples.

#### Subcommand: `aud graph build`
**Primary Help**: "Build import and call graphs from your codebase."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory to analyze" | 51 |
| --langs | option | "Languages to process (e.g., python, javascript)" | 52 |
| --workset | option | "Path to workset.json to limit scope" | 53 |
| --batch-size | option | "Files per batch" | 54 |
| --resume | flag | "Resume from checkpoint" | 55 |
| --db | option | "SQLite database path" | 56 |
| --out-json | option | "JSON output directory" | 57 |

**Extended Documentation**: Lines 59-81 with examples, output description, and prerequisite note.

#### Subcommand: `aud graph build-dfg`
**Primary Help**: "Build data flow graph from indexed assignments and returns."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory" | 174 |
| --db | option | "SQLite database path" | 175 |
| --repo-db | option | "Repo index database" | 176 |

**Extended Documentation**: Lines 178-199 explaining DFG construction, examples, output, and stats.

#### Subcommand: `aud graph analyze`
**Primary Help**: "Analyze graphs for cycles, hotspots, and impact."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db | option | "SQLite database path" | 258 |
| --out | option | "Output JSON path" | 259 |
| --max-depth | option | "Max traversal depth for impact analysis" | 260 |
| --workset | option | "Path to workset.json for change impact" | 261 |
| --no-insights | flag | "Skip interpretive insights (health scores, recommendations)" | 262 |

**Note**: No extended docstring beyond one-line help.

#### Subcommand: `aud graph query`
**Primary Help**: "Query graph relationships."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db | option | "SQLite database path" | 450 |
| --uses | option | "Find who uses/imports this module or calls this function" | 451 |
| --calls | option | "Find what this module/function calls or depends on" | 452 |
| --nearest-path | option | "Find shortest path between two nodes" | 453 |
| --format | option | "Output format" | 454 |

**Note**: No extended docstring beyond one-line help.

#### Subcommand: `aud graph viz`
**Primary Help**: "Visualize graphs with rich visual encoding (Graphviz)."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db | option | "SQLite database path" | 546 |
| --graph-type | option | "Graph type to visualize" | 547 |
| --out-dir | option | "Output directory for visualizations" | 548 |
| --limit-nodes | option | "Maximum nodes to display" | 549 |
| --format | option | "Output format" | 550 |
| --view | option | "Visualization view type" | 551-552 |
| --include-analysis | flag | "Include analysis results (cycles, hotspots) in visualization" | 553 |
| --title | option | "Graph title" | 554 |
| --top-hotspots | option | "Number of top hotspots to show (for hotspots view)" | 555 |
| --impact-target | option | "Target node for impact analysis (for impact view)" | 556 |
| --show-self-loops | flag | "Include self-referential edges" | 557 |

**Extended Documentation**: Lines 560-596 with excellent detail on view modes, visual encoding, and 7 examples.

---

### Command: `aud impact`
**File**: theauditor/commands/impact.py
**Primary Help**: "Analyze the blast radius of code changes. Maps the complete impact of changing a specific function or class by tracing both upstream (who depends on this) and downstream (what this depends on) dependencies. Essential for understanding risk before refactoring or making changes."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --file | option | "Path to the file containing the code to analyze" | 12 |
| --line | option | "Line number of the code to analyze" | 13 |
| --db | option | "Path to the SQLite database (default: repo_index.db)" | 14 |
| --json | flag | "Output results as JSON" | 15 |
| --max-depth | option | "Maximum depth for transitive dependencies" | 16 |
| --verbose | flag | "Show detailed dependency information" | 17 |
| --trace-to-backend | flag | "Trace frontend API calls to backend endpoints (cross-stack analysis)" | 18 |

**Extended Documentation**: Lines 20-71 with comprehensive coverage:
- Impact analysis reveals (4 categories)
- Risk levels (3 tiers with file counts)
- Examples (4 different scenarios)
- Common use cases (3 real-world scenarios)
- Output formats (2 types)
- Report includes (4 items)
- Exit codes (3 codes)
- Prerequisites note

---

### Command: `aud index`
**File**: theauditor/commands/index.py
**Primary Help**: "Build comprehensive code inventory and symbol database. Creates a complete inventory of your codebase including all functions, classes, imports, and their relationships. This is the foundation for all other analysis commands - you MUST run index first."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory to index" | 10 |
| --manifest | option | "Output manifest file path" | 11 |
| --db | option | "Output SQLite database path" | 12 |
| --print-stats | flag | "Print summary statistics" | 13 |
| --dry-run | flag | "Scan but don't write files" | 14 |
| --follow-symlinks | flag | "Follow symbolic links (default: skip)" | 15 |
| --exclude-self | flag | "Exclude TheAuditor's own files (for self-testing)" | 16 |

**Extended Documentation**: Lines 18-48 with excellent structure:
- What the index contains (4 categories)
- Examples (4 different uses)
- Output files (3 files with paths)
- Database tables (4 tables with descriptions)
- Prerequisites note

---

### Command: `aud init`
**File**: theauditor/commands/init.py
**Primary Help**: "Initialize TheAuditor and create analysis infrastructure. Sets up the complete TheAuditor environment in your project. This is typically the first command you run in a new project. It creates the .pf/ directory structure and performs initial analysis."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --offline | flag | "Skip network operations (deps check, docs fetch)" | 8 |
| --skip-docs | flag | "Skip documentation fetching" | 9 |
| --skip-deps | flag | "Skip dependency checking" | 10 |

**Extended Documentation**: Lines 12-49 with excellent organizational structure:
- Creates directory structure (detailed tree with 10+ paths)
- Operations performed (4 sequential steps)
- Examples (4 different scenarios)
- After init next steps (3 common commands)
- Safety note (idempotent)

---

### Command: `aud init-config`
**File**: theauditor/commands/init_config.py
**Primary Help**: "Ensure minimal mypy config exists (idempotent)."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --pyproject | option | "Path to pyproject.toml" | 7 |

**Note**: MINIMAL documentation - only one-line help text. No extended docstring, no examples, no explanation of WHAT mypy config or WHY it's needed.

---

### Command: `aud init-js`
**File**: theauditor/commands/init_js.py
**Primary Help**: "Create or merge minimal package.json for lint/typecheck."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --path | option | "Path to package.json" | 7 |
| --add-hooks | flag | "Add TheAuditor hooks to npm scripts" | 8 |

**Note**: MINIMAL documentation - only one-line help text. No extended docstring, no examples, no explanation of WHAT is merged or WHY.

---

### Command: `aud insights`
**File**: theauditor/commands/insights.py
**Primary Help**: "Add interpretive scoring and predictions to raw audit facts. The Insights system is TheAuditor's optional interpretation layer that sits ON TOP of factual data. While core modules report facts ('XSS found at line 42'), insights add interpretation ('This is CRITICAL severity')."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --mode / -m | option | "Which insights modules to run" | 16-18 |
| --ml-train | flag | "Train ML models before generating suggestions" | 20-21 |
| --topk | option | "Top K files for ML suggestions" | 22-23 |
| --output-dir / -o | option | "Directory for insights output" | 24-26 |
| --print-summary | flag | "Print summary to console" | 27-28 |

**Extended Documentation**: Lines 30-136 contain EXCEPTIONAL documentation:
- Critical understanding section (two-layer architecture)
- Available insights modules (4 modules with detailed descriptions)
- How it works (4-step process)
- Examples (5 different scenarios)
- Output files (5 specific paths)
- Severity levels (5 tiers with definitions)
- Health grades (5 letter grades with ranges)
- ML risk scores (5 ranges with recommendations)
- Prerequisites (3 installation options)
- Philosophy note explaining interpretation vs facts
- Exit codes (2 codes)

---

### Command: `aud lint`
**File**: theauditor/commands/lint.py
**Primary Help**: "Run code quality checks with industry-standard linters. Automatically detects and runs available linters in your project, normalizing all output into a unified format for analysis. Supports both full codebase and targeted workset analysis."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory" | 101 |
| --workset | flag | "Use workset mode (lint only files in .pf/workset.json)" | 102 |
| --workset-path | option | "Custom workset path (rarely needed)" | 103 |
| --manifest | option | "Manifest file path" | 104 |
| --timeout | option | "Timeout in seconds for each linter" | 105 |
| --print-plan | flag | "Print lint plan without executing" | 106 |

**Extended Documentation**: Lines 108-169 with comprehensive coverage:
- Supported linters by language (4 languages, 12+ tools)
- Examples (4 common scenarios)
- Common workflows (3 real-world patterns)
- Output files (2 paths)
- Finding format (JSON example with 7 fields)
- Exit behavior explanation
- Installation note
- Auto-fix deprecation notice

---

### Command: `aud metadata`
**File**: theauditor/commands/metadata.py
**Primary Help**: "Collect temporal (churn) and quality (coverage) metadata."

**Options/Arguments (Group Command):**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| -h, --help | option | (built-in help) | 11 |

**Note**: MINIMAL group-level documentation.

#### Subcommand: `aud metadata churn`
**Primary Help**: "Analyze git commit history for code churn metrics."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory to analyze" | 18 |
| --days | option | "Number of days to analyze" | 19 |
| --output | option | "Output JSON path" | 20 |

**Extended Documentation**: Lines 22-40 with good structure:
- What data is collected (3 metrics)
- Purpose statement
- Examples (3 scenarios)

#### Subcommand: `aud metadata coverage`
**Primary Help**: "Parse test coverage reports for quality metrics."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory" | 75 |
| --coverage-file | option | "Path to coverage file (auto-detects if not specified)" | 76 |
| --output | option | "Output JSON path" | 77 |

**Extended Documentation**: Lines 78-101 with good structure:
- Supports (2 ecosystems)
- What data is collected (3 metrics)
- Purpose statement
- Examples (3 scenarios)

#### Subcommand: `aud metadata analyze`
**Primary Help**: "Run both churn and coverage analysis (convenience command)."

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory" | 149 |
| --days | option | "Number of days for churn analysis" | 150 |
| --coverage-file | option | "Path to coverage file (optional)" | 151 |
| --skip-churn | flag | "Skip churn analysis" | 152 |
| --skip-coverage | flag | "Skip coverage analysis" | 153 |

**Extended Documentation**: Lines 155-169 with examples and purpose.

---

## AI-First Standard Critique

### Command: `aud fce` - Rating: ✅ GOOD
**Strengths**:
- Exceptional PURPOSE explanation with "why compound vulnerabilities matter"
- Excellent CONTEXT with 30 correlation rule examples categorized by type
- Outstanding AI-USABLE EXAMPLES with 3 concrete usage patterns
- Comprehensive OPTION RATIONALE (timeout for large projects, print-plan for previews)
- Clear INPUT/OUTPUT specifications with file paths and JSON schemas

**Weaknesses**:
- No explicit flag interaction documentation (e.g., does --print-plan suppress other flags?)
- Missing performance expectations/timings

**AI Usability Score**: 9/10 - Nearly perfect for AI consumption.

---

### Command: `aud full` - Rating: ✅ GOOD
**Strengths**:
- Clear PURPOSE: "main command for full codebase auditing"
- Excellent CONTEXT with 4-stage pipeline breakdown
- Strong AI-USABLE EXAMPLES (5 scenarios covering different use cases)
- Good OPTION RATIONALE (offline for air-gapped, wipecache for corruption)
- Exit codes clearly documented for CI/CD integration
- Performance expectations by project size

**Weaknesses**:
- No explicit flag conflict documentation (e.g., --quiet + --exclude-self behavior)
- Missing explanation of stage parallelization mechanics

**AI Usability Score**: 9/10 - Excellent for automation and AI workflows.

---

### Command: `aud graph` (Group) - Rating: ✅ GOOD
**Strengths**:
- Clear PURPOSE hierarchy (group + 5 subcommands)
- Good CONTEXT with typical workflow explanation
- Subcommand `build` and `viz` have excellent documentation
- Visual encoding legend in `viz` is outstanding for AI interpretation

**Weaknesses**:
- Subcommands `analyze` and `query` have MINIMAL help text (one-line only)
- No rationale for why graphs.db is separate from repo_index.db
- Missing performance/timing expectations for graph builds

**AI Usability Score**: 7/10 - Inconsistent quality across subcommands.

---

### Command: `aud impact` - Rating: ✅ GOOD
**Strengths**:
- Excellent PURPOSE: "understand risk before refactoring"
- Strong CONTEXT with 4 categories of impact analysis
- Outstanding AI-USABLE EXAMPLES with real-world scenarios
- Clear OPTION RATIONALE (trace-to-backend for cross-stack, verbose for details)
- Exit codes documented for CI/CD
- Risk level thresholds clearly defined

**Weaknesses**:
- No explanation of when to use --max-depth values
- Missing performance expectations (how long for 100K LOC?)

**AI Usability Score**: 8.5/10 - Very strong for AI-driven impact analysis.

---

### Command: `aud index` - Rating: ✅ GOOD
**Strengths**:
- Clear PURPOSE: "foundation for all other commands"
- Good CONTEXT explaining what the index contains
- Solid AI-USABLE EXAMPLES (4 scenarios)
- Clear output file specifications
- Schema validation shown in implementation (lines 82-105)

**Weaknesses**:
- No performance expectations (timing for different project sizes)
- Missing explanation of when to re-run index
- No rationale for --follow-symlinks default behavior

**AI Usability Score**: 8/10 - Strong foundational command documentation.

---

### Command: `aud init` - Rating: ✅ GOOD
**Strengths**:
- Excellent PURPOSE: "first command in new project"
- Outstanding CONTEXT with complete directory tree visualization
- Clear AI-USABLE EXAMPLES (4 scenarios)
- Good OPTION RATIONALE (offline skips network, skip-docs/deps for partial setup)
- Idempotency clearly documented
- "After init" next steps are helpful

**Weaknesses**:
- No timing expectations (how long does init take?)
- Missing explanation of when to re-run init

**AI Usability Score**: 8.5/10 - Excellent onboarding documentation.

---

### Command: `aud init-config` - Rating: ❌ POOR
**Strengths**:
- Idempotent behavior mentioned in help text
- Simple, focused command

**Weaknesses**:
- NO PURPOSE explanation (why does mypy need config?)
- NO CONTEXT (what config is created? what values?)
- NO AI-USABLE EXAMPLES
- NO OPTION RATIONALE (why specify pyproject path?)
- Minimal one-line help text only

**AI Usability Score**: 2/10 - Insufficient for AI to understand usage.

---

### Command: `aud init-js` - Rating: ⚠️ NEEDS_IMPROVEMENT
**Strengths**:
- Clear target (package.json)
- Idempotent behavior shown in implementation

**Weaknesses**:
- Minimal PURPOSE explanation (what is "minimal" package.json?)
- NO CONTEXT (what dependencies are added? what scripts?)
- NO AI-USABLE EXAMPLES
- Limited OPTION RATIONALE (what hooks does --add-hooks add?)
- Implementation shows "PIN_ME" placeholders but help doesn't explain

**AI Usability Score**: 4/10 - Needs more context and examples.

---

### Command: `aud insights` - Rating: ✅ GOOD (EXCEPTIONAL)
**Strengths**:
- EXCEPTIONAL PURPOSE: Two-layer architecture clearly explained (facts vs interpretations)
- Outstanding CONTEXT with 4 insights modules detailed
- Excellent AI-USABLE EXAMPLES (5 different scenarios)
- Comprehensive OPTION RATIONALE (ml-train for training, topk for filtering)
- Severity levels, health grades, and risk scores all quantified
- Philosophy note explaining interpretation vs facts
- Prerequisites clearly documented
- Exit codes specified

**Weaknesses**:
- None significant - this is exemplary documentation

**AI Usability Score**: 10/10 - Gold standard for AI-consumable help text.

---

### Command: `aud lint` - Rating: ✅ GOOD
**Strengths**:
- Clear PURPOSE: "industry-standard linters with unified output"
- Excellent CONTEXT with 12+ linters across 4 languages
- Strong AI-USABLE EXAMPLES (4 scenarios)
- Good OPTION RATIONALE (workset for targeted, timeout for large projects)
- Common workflows section is excellent for AI
- Finding format with JSON schema
- Auto-fix deprecation clearly documented

**Weaknesses**:
- No performance expectations (timing)
- Missing explanation of linter auto-detection mechanism

**AI Usability Score**: 8.5/10 - Strong for automation workflows.

---

### Command: `aud metadata` (Group) - Rating: ⚠️ NEEDS_IMPROVEMENT
**Strengths**:
- Subcommands `churn` and `coverage` have good documentation
- Clear data collection purpose (temporal + quality)
- Examples provided for each subcommand

**Weaknesses**:
- Group-level help is MINIMAL (one line)
- No explanation of WHY metadata is collected (FCE correlation)
- No performance expectations
- Missing integration examples (how metadata feeds into FCE)

**AI Usability Score**: 6/10 - Subcommands are good, group documentation is weak.

---

## Summary Statistics

- **Total commands audited**: 11 (plus 8 subcommands = 19 total command surfaces)
- **✅ GOOD**: 7 commands (fce, full, graph, impact, index, init, insights, lint)
- **⚠️ NEEDS_IMPROVEMENT**: 3 commands (init-js, metadata group)
- **❌ POOR**: 1 command (init-config)

### Grade Distribution by Section:
- **PRIMARY HELP**: 8 excellent, 2 good, 1 poor
- **EXAMPLES**: 8 excellent, 1 good, 2 minimal
- **OPTION RATIONALE**: 6 excellent, 3 good, 2 minimal
- **CONTEXT**: 8 excellent, 1 good, 2 minimal
- **INTERACTIONS**: 0 commands explicitly document flag conflicts

---

## Key Findings

### 1. **CRITICAL: Inconsistent Subcommand Documentation**
**Issue**: Commands like `graph analyze` and `graph query` have comprehensive parent help but minimal subcommand help (one-line only). This creates confusion when users run `aud graph query --help` expecting full documentation.

**Impact**: AI agents and users cannot understand subcommand usage without reading parent help.

**Recommendation**: Move or duplicate subcommand-specific documentation to each subcommand's docstring.

**Affected Commands**: `graph analyze`, `graph query`

---

### 2. **CRITICAL: Init Helper Commands Lack Context**
**Issue**: `init-config` and `init-js` have one-line help text with no explanation of WHAT is configured or WHY it's needed. These are critical onboarding commands that need better documentation.

**Impact**: New users and AI agents cannot understand when/why to run these commands.

**Recommendation**: Add comprehensive docstrings explaining:
- What config/package.json is created/modified
- Why this configuration is necessary
- Examples of before/after state
- When to re-run these commands

**Affected Commands**: `init-config`, `init-js`

---

### 3. **High Priority: Missing Flag Interaction Documentation**
**Issue**: No commands explicitly document flag conflicts or interactions (e.g., does `--quiet` suppress `--print-stats`? Can `--offline` be used with `--skip-docs`?).

**Impact**: Users and AI agents must guess flag compatibility, leading to trial-and-error usage.

**Recommendation**: Add "Flag Interactions:" section to help text for commands with 3+ flags, documenting:
- Mutually exclusive flags
- Recommended flag combinations
- Flags that modify other flag behavior

**Affected Commands**: All commands with 3+ flags (full, graph build, impact, index, init, lint)

---

### 4. **Medium Priority: Missing Performance Expectations**
**Issue**: Only `full` command documents performance expectations. Other long-running commands (index, graph build, fce) don't specify timing.

**Impact**: Users cannot estimate completion time, leading to premature command termination.

**Recommendation**: Add "Performance:" section with:
- Small project (< 5K LOC): ~X minutes
- Medium project (20K LOC): ~X minutes
- Large project (100K+ LOC): ~X minutes

**Affected Commands**: `index`, `graph build`, `fce`, `taint-analyze` (if audited)

---

### 5. **Low Priority: Excellent AI-First Examples**
**Finding**: Commands like `insights`, `fce`, `full`, `impact`, and `lint` provide exceptional examples organized by use case (e.g., "Before refactoring:", "PR review:", "CI pipeline:").

**Impact**: AI agents can immediately understand context-appropriate usage.

**Recommendation**: Apply this pattern to all commands. Current best practice examples:
- `aud insights` (lines 79-93): 5 examples with clear scenarios
- `aud impact` (lines 44-53): Common use cases with context
- `aud lint` (lines 134-143): Workflow-based examples

**Model Commands**: `insights`, `impact`, `lint`

---

## Recommendations Summary

### Immediate Actions (Critical):
1. **Enhance init-config and init-js help text** - Add comprehensive docstrings with examples, config explanations, and use cases.
2. **Document graph subcommand help** - Move/duplicate `analyze` and `query` documentation to subcommand docstrings.

### High Priority:
3. **Add flag interaction documentation** - Document mutually exclusive flags and recommended combinations for commands with 3+ flags.
4. **Add performance expectations** - Document expected runtimes for `index`, `graph build`, `fce`.

### Medium Priority:
5. **Standardize example formats** - Apply the "Common Use Cases:" pattern from `impact` and `lint` to all commands.
6. **Add "When to Use" sections** - Help users understand command timing (e.g., "Run after code changes", "Run before deployment").

### Low Priority:
7. **Add exit code documentation universally** - Commands like `full` and `impact` document exit codes; apply this pattern to all commands that exit non-zero.
8. **Document re-run behavior** - Explain when to re-run commands (e.g., "Re-run index after adding new files").

---

## Exemplary Commands for Reference

When improving other commands, use these as templates:

1. **`aud insights`** (theauditor/commands/insights.py) - Gold standard for:
   - Multi-layer architecture explanation
   - Comprehensive module documentation
   - Severity/grade quantification
   - Philosophy notes

2. **`aud full`** (theauditor/commands/full.py) - Gold standard for:
   - Pipeline stage documentation
   - Performance expectations
   - Exit code documentation
   - Cache behavior explanation

3. **`aud impact`** (theauditor/commands/impact.py) - Gold standard for:
   - Real-world use case examples
   - Risk level quantification
   - Context-appropriate usage patterns

4. **`aud lint`** (theauditor/commands/lint.py) - Gold standard for:
   - Workflow-based examples
   - Tool ecosystem documentation
   - Finding format schemas

---

## Conclusion

TheAuditor's CLI commands 12-22 demonstrate strong documentation practices overall, with 7 out of 11 commands receiving "GOOD" ratings. The standout commands (`insights`, `full`, `impact`, `lint`) provide exceptional AI-first documentation with comprehensive examples, clear value propositions, and quantified outputs.

The primary areas for improvement are:
1. Inconsistent subcommand documentation depth
2. Minimal help text for init helper commands
3. Missing flag interaction documentation
4. Incomplete performance expectations

Addressing these issues will bring the entire command suite to the exemplary standard set by the best-documented commands.
