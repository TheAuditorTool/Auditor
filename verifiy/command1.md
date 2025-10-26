# CLI Audit Report: Commands 1-11
**Auditor**: Architect (Lead)
**Date**: 2025-10-26

## Executive Summary

Audited 11 command files (including __init__.py, _archive, and 9 user-facing commands). Found **significant inconsistencies** between registered commands and VerboseGroup help text. Key findings:

- **CRITICAL**: `_archive` is registered in cli.py but NOT documented in VerboseGroup (internal command correctly hidden)
- **HIGH**: Help text quality varies wildly - from excellent (explain, deps) to minimal (detect-frameworks)
- **MEDIUM**: Several commands missing AI-usable context about WHEN to use them
- **LOW**: Option help text generally good but lacks interaction/conflict documentation

---

## Detailed Audit

### Command: `aud __init__` (Module Only)
**File**: theauditor/commands/__init__.py
**Status**: Not a CLI command - Python module initialization only
**Note**: Contains only docstring "Commands module for TheAuditor CLI."

---

### Command: `aud _archive`
**File**: theauditor/commands/_archive.py:11-138
**Registered in cli.py**: Line 316 `cli.add_command(_archive)`
**In VerboseGroup help**: ❌ NO (correctly omitted - internal command)
**Primary Help**: "Internal command to archive previous run artifacts with segregation by type."

**Analysis**: This is an internal command (prefix `_`) that should NOT be in main help. Correctly omitted from VerboseGroup. However, its presence in cli.py means it IS discoverable via `aud --help` command listing. This is acceptable for internal tooling.

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --run-type | option | "Type of run being archived" | 12 |
| --diff-spec | option | "Git diff specification for diff runs (e.g., main..HEAD)" | 13 |
| --wipe-cache | flag | "Delete caches during archive (default: preserve)" | 14 |

**Docstring Quality**: EXCELLENT (21-34) - Explains purpose, cache preservation policy, what's archived vs preserved. AI-usable.

---

### Command: `aud blueprint`
**File**: theauditor/commands/blueprint.py:18-872
**Registered in cli.py**: Line 326 `cli.add_command(blueprint)`
**In VerboseGroup help**: ✅ YES (Line 124-129)
**Primary Help**: "Architectural blueprint - Truth courier visualization of indexed codebase." (29-57)

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --structure | flag | "Drill down into codebase structure details" | 19 |
| --graph | flag | "Drill down into import/call graph analysis" | 20 |
| --security | flag | "Drill down into security surface details" | 21 |
| --taint | flag | "Drill down into taint analysis details" | 22 |
| --all | flag | "Export all data to JSON (ignores other flags)" | 23 |
| --format | choice | "Output format: text (visual tree), json (structured)" | 24-26 |

**Docstring Quality**: OUTSTANDING
- **Purpose**: ✅ "Shows facts about code architecture with NO recommendations"
- **Context**: ✅ "PREREQUISITES: aud full (recommended) OR aud index (minimum)"
- **Examples**: ✅ 6 usage examples with different drill-down modes (36-41)
- **Output**: ✅ Explains what you get (51-57)
- **Philosophy**: ✅ "Truth Courier Facts Only" - explicit AI-usability statement

**VerboseGroup Match**:
- Listed: ✅ "aud blueprint" with format options
- Note: VerboseGroup says "(NO ML/CUDA)" which is accurate but not in command help

**AI-First Rating**: ✅ EXCELLENT (9/10)

---

### Command: `aud cfg` (Group)
**File**: theauditor/commands/cfg.py:11-361
**Registered in cli.py**: Line 334 `cli.add_command(cfg)`
**In VerboseGroup help**: ✅ YES (Line 100-107)
**Primary Help**: "Analyze function complexity through Control Flow Graphs." (14-54)

**Subcommands**:
1. `cfg analyze` (58-229)
2. `cfg viz` (232-361)

#### Subcommand: `aud cfg analyze`
**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db | option | "Path to repository database" | 59 |
| --file | option | "Analyze specific file only" | 60 |
| --function | option | "Analyze specific function only" | 61 |
| --complexity-threshold | option | "Complexity threshold for reporting" | 62 |
| --output | option | "Output JSON file path" | 63 |
| --find-dead-code | flag | "Find unreachable code blocks" | 64 |
| --workset | flag | "Analyze workset files only" | 65 |

**Docstring Quality**: GOOD
- **Purpose**: ✅ Explains McCabe complexity (25-34)
- **Context**: ✅ Prerequisites listed (44-48)
- **Examples**: ✅ 6 examples with different options (36-42)
- **Output**: ✅ Output locations specified (44-48)

#### Subcommand: `aud cfg viz`
**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db | option | "Path to repository database" | 233 |
| --file | option (required) | "File containing the function" | 234 |
| --function | option (required) | "Function name to visualize" | 235 |
| --output | option | "Output file path (default: function_name.dot)" | 236 |
| --format | choice | "Output format: dot, svg, png" | 237 |
| --show-statements | flag | "Include statements in blocks" | 238 |
| --highlight-paths | flag | "Highlight execution paths" | 239 |

**VerboseGroup Match**:
- Listed: ✅ Both analyze and viz with key options
- Accurate representation

**AI-First Rating**: ✅ GOOD (8/10)
- Missing: WHEN to use (e.g., "Use during code review to find complex functions")

---

### Command: `aud context`
**File**: theauditor/commands/context.py:19-318
**Registered in cli.py**: Line 324 `cli.add_command(context_command, name="context")`
**In VerboseGroup help**: ✅ YES (Line 119-122)
**Primary Help**: "Apply semantic business logic to findings (YAML-based classification)." (28-54)

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --file / -f | option (required) | "Semantic context YAML file" | 20-21 |
| --output / -o | option | "Custom output JSON file (optional)" | 22-23 |
| --verbose / -v | flag | "Show detailed findings in report" | 24-25 |

**Docstring Quality**: EXCELLENT
- **Purpose**: ✅ "This command classifies findings from analysis tools based on YOUR business logic"
- **Context**: ✅ "Prerequisites: You must run analysis first" with specific commands (34-38)
- **Examples**: ✅ 3 examples covering basic, verbose, and custom output (40-48)
- **Output**: ✅ Two output locations explained (50-52)
- **Cross-ref**: ✅ Points to template documentation (54)

**VerboseGroup Match**:
- Listed: ✅ With --file and --verbose options
- Accurate

**AI-First Rating**: ✅ EXCELLENT (9/10)

---

### Command: `aud deps`
**File**: theauditor/commands/deps.py:13-264
**Registered in cli.py**: Line 244 `cli.add_command(deps)`
**In VerboseGroup help**: ✅ YES (Line 72-77)
**Primary Help**: "Analyze dependencies for vulnerabilities and updates." (23-70)

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --root | option | "Root directory" | 15 |
| --check-latest | flag | "Check for latest versions from registries" | 16 |
| --upgrade-all | flag | "YOLO mode: Update ALL packages to latest versions" | 17 |
| --offline | flag | "Force offline mode (no network)" | 18 |
| --out | option | "Output dependencies file" | 19 |
| --print-stats | flag | "Print dependency statistics" | 20 |
| --vuln-scan | flag | "Scan dependencies for known vulnerabilities" | 21 |

**Docstring Quality**: OUTSTANDING (23-70)
- **Purpose**: ✅ "Comprehensive dependency analysis supporting Python and JavaScript/TypeScript"
- **Context**: ✅ WHEN to use each mode (35-47)
- **Supported Files**: ✅ Lists all supported formats (29-33)
- **Operation Modes**: ✅ 4 modes explained (35-39)
- **Examples**: ✅ 5 examples covering all modes (41-46)
- **Vuln Scanning**: ✅ DETAILED explanation (48-54) - tools used, cross-referencing, confidence scoring
- **Output**: ✅ All output files documented (61-64)
- **Exit Codes**: ✅ Explained (66-68)

**VerboseGroup Match**:
- Listed: ✅ Main command with all 4 key flags
- Accurate and comprehensive

**AI-First Rating**: ✅ OUTSTANDING (10/10)
- **Best-in-class example** - Should be template for all commands
- Has everything: WHY, WHEN, HOW, WHAT, WHERE, edge cases, exit codes

---

### Command: `aud detect-frameworks`
**File**: theauditor/commands/detect_frameworks.py:14-148
**Registered in cli.py**: Line 304 `cli.add_command(detect_frameworks)`
**In VerboseGroup help**: ❌ NO - **DISCREPANCY #1**
**Primary Help**: "Display frameworks and generate AI-consumable output." (18-24)

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --project-path | option | "Root directory to analyze" | 15 |
| --output-json | option | "Path to output JSON file (default: .pf/raw/frameworks.json)" | 16 |

**Docstring Quality**: POOR
- **Purpose**: ✅ "Reads from frameworks table (populated by 'aud index')"
- **Context**: ❌ NO - Doesn't explain WHEN to use or WHY you'd run this standalone
- **Examples**: ❌ NO
- **Output**: ⚠️ Minimal - just says "Generates .pf/raw/frameworks.json"
- **Prerequisites**: ✅ "If database doesn't exist, run 'aud index' first"

**VerboseGroup Match**: ❌ NOT LISTED - This is a registered command that's invisible to users!

**AI-First Rating**: ❌ POOR (3/10)
- Missing: Context about when/why to use
- Missing: Examples
- Missing: What you can DO with the output
- **CRITICAL**: Not documented in main help at all

---

### Command: `aud detect-patterns`
**File**: theauditor/commands/detect_patterns.py:8-190
**Registered in cli.py**: Line 303 `cli.add_command(detect_patterns)`
**In VerboseGroup help**: ✅ YES (Line 57-59)
**Primary Help**: "Detect security vulnerabilities and code quality issues." (19-96)

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --project-path | option | "Root directory to analyze" | 9 |
| --patterns | option (multiple) | "Pattern categories to use (e.g., runtime_issues, db_issues)" | 10 |
| --output-json | option | "Path to output JSON file" | 11 |
| --file-filter | option | "Glob pattern to filter files" | 12 |
| --max-rows | option | "Maximum rows to display in table" | 13 |
| --print-stats | flag | "Print summary statistics" | 14 |
| --with-ast/--no-ast | flag | "Enable AST-based pattern matching" | 15 |
| --with-frameworks/--no-frameworks | flag | "Enable framework detection and framework-specific patterns" | 16 |
| --exclude-self | flag | "Exclude TheAuditor's own files (for self-testing)" | 17 |

**Docstring Quality**: EXCELLENT (19-96)
- **Purpose**: ✅ "Runs 100+ security pattern rules across your codebase"
- **Context**: ✅ Pattern categories explained (25-55)
- **Detection Methods**: ✅ 3 methods explained (57-60)
- **Examples**: ✅ 5 examples with different modes (62-67)
- **Output**: ✅ Output locations (69-71) and format (73-82)
- **Severity**: ✅ 4 levels explained (84-89)
- **Performance**: ✅ Timing expectations (91-93)

**VerboseGroup Match**:
- Listed: ✅ With --workset flag
- Accurate

**AI-First Rating**: ✅ EXCELLENT (9/10)

---

### Command: `aud docker-analyze`
**File**: theauditor/commands/docker_analyze.py:10-94
**Registered in cli.py**: Line 329 `cli.add_command(docker_analyze)`
**In VerboseGroup help**: ✅ YES (Line 65-68)
**Primary Help**: "Analyze Docker images for security issues." (19-26)

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| --db-path | option | "Path to repo_index.db" | 12 |
| --output | option | "Output file for findings (JSON format)" | 13 |
| --severity | choice | "Minimum severity to report: all/critical/high/medium/low" | 14-15 |
| --check-vulns/--no-check-vulns | flag | "Check base images for vulnerabilities (requires network)" | 16-17 |

**Docstring Quality**: NEEDS IMPROVEMENT
- **Purpose**: ✅ Brief list of what it detects (21-25)
- **Context**: ❌ NO - Doesn't explain WHEN to use
- **Examples**: ❌ NO
- **Output**: ❌ NO - Doesn't explain what you get
- **Prerequisites**: ⚠️ Says "Run 'aud index' first" in error message (31-33) but not in help

**VerboseGroup Match**:
- Listed: ✅ With --severity and --check-vulns flags
- Accurate

**AI-First Rating**: ⚠️ NEEDS IMPROVEMENT (5/10)
- Good: Brief, clear list of detections
- Missing: Context, examples, output explanation

---

### Command: `aud docs` (Subcommands)
**File**: theauditor/commands/docs.py:8-201
**Registered in cli.py**: Line 305 `cli.add_command(docs)`
**In VerboseGroup help**: ✅ YES (Line 79-82)
**Primary Help**: "Fetch or summarize documentation for dependencies." (20)

**Actions (Subcommands via argument)**:
- `docs fetch` - Fetch documentation
- `docs summarize` - Create AI capsules
- `docs view <package>` - View specific doc
- `docs list` - List available docs

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| action | argument | Choice: fetch/summarize/view/list | 9 |
| package_name | argument | (required for 'view') | 10 |
| --deps | option | "Input dependencies file" | 11 |
| --offline | flag | "Force offline mode" | 12 |
| --allow-non-gh-readmes | flag | "Allow non-GitHub README fetching" | 13 |
| --docs-dir | option | "Documentation cache directory" | 14 |
| --capsules-dir | option | "Output capsules directory" | 15 |
| --workset | option | "Workset file for filtering" | 16 |
| --print-stats | flag | "Print statistics" | 17 |
| --raw | flag | "View raw fetched doc instead of capsule" | 18 |

**Docstring Quality**: POOR
- **Purpose**: ❌ Only says "Fetch or summarize documentation" - too vague
- **Context**: ❌ NO - Doesn't explain WHEN/WHY to fetch docs or what capsules are for
- **Examples**: ❌ NO
- **Output**: ❌ NO
- **Workflow**: ❌ NO - Doesn't explain the fetch→summarize→view pipeline

**VerboseGroup Match**:
- Listed: ✅ All 4 actions listed separately (79-82)
- Accurate but help is minimal

**AI-First Rating**: ❌ POOR (3/10)
- Missing: Everything except basic action list
- AI wouldn't know WHEN to use each action or how they relate
- No explanation of "capsules" concept

---

### Command: `aud explain`
**File**: theauditor/commands/explain.py:519-582
**Registered in cli.py**: Line 300 `cli.add_command(explain)`
**In VerboseGroup help**: ❌ NO - **DISCREPANCY #2**
**Primary Help**: "Explain TheAuditor concepts and terminology." (523-552)

**Options/Arguments:**
| Flag | Type | Help Text | Line # |
|------|------|-----------|--------|
| concept | argument | (optional) Topic to explain | 520 |
| --list | flag | "List all available concepts" | 521 |

**Docstring Quality**: EXCELLENT (523-552)
- **Purpose**: ✅ "Provides detailed explanations of security concepts, analysis techniques, and TheAuditor-specific terminology"
- **Context**: ✅ Explains it helps users "understand the tool's capabilities and outputs"
- **Examples**: ✅ 5 examples covering different concepts (529-534)
- **Available Concepts**: ✅ Lists all 8 topics with brief descriptions (536-545)
- **Content Promise**: ✅ "Each explanation includes: overview, how it works, practical examples, use cases, related commands" (547-551)

**EXPLANATIONS Database**: OUTSTANDING (8-515)
- Contains 8 comprehensive concept explanations
- Each explanation is 30-100 lines with:
  - Title and summary
  - Detailed HOW IT WORKS section
  - Concrete examples
  - Use cases
  - Related commands
- Examples: taint (12-43), workset (45-81), fce (82-126), cfg (128-178), impact (180-236), pipeline (238-293), severity (295-356), patterns (358-434), insights (436-515)

**VerboseGroup Match**: ❌ NOT LISTED - Command is invisible to users!

**AI-First Rating**: ✅ OUTSTANDING (10/10)
- **Best educational command in the codebase**
- Should be promoted in main help
- Essential for AI understanding

---

## AI-First Standard Critique

### ✅ GOOD (4 commands)
1. **blueprint** - Outstanding "Truth Courier" philosophy, clear prerequisites, 6 examples
2. **context** - Clear business logic explanation, prerequisites, cross-references
3. **deps** - GOLD STANDARD - has everything (WHY, WHEN, HOW, WHAT, WHERE, exit codes)
4. **explain** - Outstanding educational content, comprehensive concept database

### ⚠️ NEEDS IMPROVEMENT (5 commands)
1. **cfg** - Good but missing WHEN context (e.g., "Use during code review")
2. **detect-patterns** - Excellent but could use more workflow context
3. **docker-analyze** - Brief help, missing examples and context
4. **docs** - Missing pipeline explanation (fetch→summarize→view workflow)
5. **_archive** (internal) - Actually good but internal-only

### ❌ POOR (2 commands)
1. **detect-frameworks** - Minimal help, no examples, no context, NOT IN MAIN HELP
2. ~~**__init__.py**~~ - Not a command (module only)

---

## Summary Statistics
- **Total files audited**: 11
- **CLI commands**: 9 (excluding __init__.py and _archive)
- **Command groups**: 2 (cfg with 2 subcommands, docs with 4 actions)
- **✅ GOOD**: 4
- **⚠️ NEEDS_IMPROVEMENT**: 5
- **❌ POOR**: 2

---

## Key Findings

### 1. CRITICAL: Registered but Undocumented Commands
**Commands registered in cli.py but MISSING from VerboseGroup help:**
- `aud detect-frameworks` (cli.py:304, but NOT in VerboseGroup)
- `aud explain` (cli.py:300, but NOT in VerboseGroup)

**Impact**: Users cannot discover these commands. AI assistants won't know they exist.

### 2. HIGH: Wildly Inconsistent Help Quality
**Scoring breakdown (out of 10):**
- **10/10**: deps, explain (GOLD STANDARD)
- **9/10**: blueprint, context, detect-patterns
- **8/10**: cfg
- **5/10**: docker-analyze
- **3/10**: detect-frameworks, docs

**Gap**: 330% quality variance between best (deps) and worst (detect-frameworks/docs)

### 3. MEDIUM: Missing Workflow Context
Most commands don't explain:
- WHEN to use them (lifecycle context)
- WHERE they fit in the pipeline
- WHAT to do with their output

**Example**: `docs` command has 4 actions but doesn't explain the fetch→summarize→view pipeline or WHY you'd use capsules vs raw docs.

### 4. LOW: No Flag Interaction Documentation
**ZERO commands** document:
- Which flags conflict (`--offline` + `--check-latest` = no-op)
- Which flags should be used together (`--workset` requires prior `aud workset` run)
- What happens when you combine flags

**Example**: `deps --offline --vuln-scan` - Does vuln-scan work offline? (Yes, it does, but help doesn't say)

### 5. POSITIVE: Strong Examples in Best Commands
Commands like `deps`, `blueprint`, `detect-patterns` have 5-6 concrete examples that an AI can directly copy-paste. This is the gold standard.

---

## Recommendations for Architect/Lead Auditor

### Immediate Action Required
1. **Add missing commands to VerboseGroup**:
   - `detect-frameworks` (add to SECURITY SCANNING or PROJECT ANALYSIS section)
   - `explain` (add to SETUP & CONFIG or HELP section)

2. **Promote `explain` command**:
   - Move to top of help (it's an educational command)
   - Suggest adding to "Understanding results" section in main cli.py docstring

### Template Development
Use **`deps` command** as the gold standard template for Phase 2 implementation. It has:
- Clear purpose statement
- Lifecycle context (WHEN to use)
- Operation modes explained
- 5+ examples
- Output locations
- Exit codes
- Performance expectations
- Cross-references

### Quick Wins (Low Effort, High Value)
1. Add 2-3 examples to `docker-analyze`
2. Add pipeline explanation to `docs` command
3. Add "WHEN to use" section to `cfg`
4. Expand `detect-frameworks` help (currently 6 lines, should be 30+)

---

## Cross-Reference: VerboseGroup vs Registered Commands

**Registered in cli.py (lines 287-336):**
1. ✅ init
2. ✅ index
3. ✅ workset
4. ✅ lint
5. ✅ deps
6. ✅ report
7. ✅ summary
8. ✅ full
9. ✅ fce
10. ✅ impact
11. ✅ taint_analyze
12. ✅ setup_ai (+ setup-claude alias)
13. ❌ **explain** (NOT in VerboseGroup)
14. ❌ **detect-frameworks** (NOT in VerboseGroup)
15. ✅ detect-patterns
16. ✅ docs
17. ✅ tool_versions (NOT reviewed - in another agent's scope)
18. ✅ init_js
19. ✅ init_config
20. ✅ learn
21. ✅ suggest
22. ✅ learn_feedback (NOT reviewed - in another agent's scope)
23. ✅ _archive (internal - correctly omitted)
24. ✅ rules (NOT reviewed - in another agent's scope)
25. ✅ refactor
26. ✅ insights
27. ✅ context
28. ✅ query (NOT reviewed - in another agent's scope)
29. ✅ blueprint
30. ✅ docker-analyze
31. ✅ structure (NOT reviewed - in another agent's scope)
32. ✅ graph
33. ✅ cfg
34. ✅ metadata (NOT reviewed - in another agent's scope)
35. ✅ terraform (NOT reviewed - in another agent's scope)

**From my audit (commands 1-11):**
- detect-frameworks: ❌ NOT in VerboseGroup
- explain: ❌ NOT in VerboseGroup

---

**END OF AUDIT REPORT - COMMAND1.MD**
