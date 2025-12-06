# Design: Manual System Content Optimization

## Context

`aud manual` has 41 topics explaining TheAuditor concepts. Current content is human-centric concept explanations. AI assistants need workflow guides - step-by-step "how do I actually use this" documentation.

**Primary users:** AI assistants (Claude Code, Gemini, etc.)
**Secondary users:** Humans learning TheAuditor

## Goals / Non-Goals

**Goals:**
- Every topic is a workflow guide, not just concept explanation
- Every topic emphasizes DATABASE-FIRST philosophy
- Every topic integrates with agent system where relevant
- All examples are verified working
- 1:1 parity with --help content

**Non-Goals:**
- Changing --help content (separate ticket)
- Modifying Rich formatting code (already complete)
- Adding new commands or functionality
- Changing topic list (41 topics is complete)

---

## Content Schema (CRITICAL)

All topic content is stored as Python dictionaries in two files:

### File Structure
```
theauditor/commands/
├── manual.py          # Topic registration, rendering (311 lines)
├── manual_lib01.py    # Topics 1-21 (1479 lines)
└── manual_lib02.py    # Topics 22-42 (1856 lines)
```

### Dictionary Schema
```python
EXPLANATIONS_01: dict[str, dict[str, str]] = {
    "topic_name": {
        "title": "Display Title",           # Shown in cyan panel header
        "summary": "One-line description",  # Shown after "Summary:" label
        "explanation": """
            Multi-line content with sections.

            SECTION NAME:
            - Bullet point
            - Another point

            ANOTHER SECTION:
            1. Numbered list
            2. Another item

            EXAMPLES:
                aud command --flag    # Comment
        """
    },
    # ... more topics
}
```

### Escaping Rules
- Use triple quotes `"""` for explanation content
- Escape single quotes inside strings with `\'` if needed
- Indentation inside triple-quoted strings is preserved
- NO emojis (Windows CP1252 encoding will crash)

---

## Topic Location Reference (All 41 Topics)

### manual_lib01.py (20 topics)

| # | Topic | Line | Current Sections | Agent Reference |
|---|-------|------|------------------|-----------------|
| 1 | taint | 4 | CONCEPTS, HOW IT WORKS, EXAMPLE, COMMAND OPTIONS, PREREQUISITES, EXAMPLES, EXIT CODES, OUTPUT | security.md |
| 2 | workset | 71 | WHAT IT CONTAINS, WHY USE, COMMAND OPTIONS, HOW IT WORKS, COMMANDS THAT SUPPORT, EXAMPLE WORKFLOW, EXAMPLES | - |
| 3 | fce | 129 | THE PROBLEM, HOW FCE WORKS, EXAMPLE CORRELATION, CORRELATION CATEGORIES, VALUE OF FCE | security.md |
| 4 | cfg | 175 | WHAT IS A CFG, WHY CFG MATTERS, CYCLOMATIC COMPLEXITY, EXAMPLE CFG, THEAUDITOR'S CFG ANALYSIS, USE CASES | dataflow.md |
| 5 | impact | 227 | IMPACT DIMENSIONS, HOW IT WORKS, RISK ASSESSMENT, EXAMPLE ANALYSIS, USE CASES, CROSS-STACK ANALYSIS | planning.md |
| 6 | pipeline | 284 | THE 4-STAGE PIPELINE, WHY THIS DESIGN, PERFORMANCE CHARACTERISTICS, CACHING | - |
| 7 | severity | 341 | SEVERITY LEVELS, HOW SEVERITY IS DETERMINED, SEVERITY ESCALATION, FILTERING BY SEVERITY | security.md |
| 8 | patterns | 404 | DETECTION METHODS, PATTERN CATEGORIES, PATTERN FILES, CUSTOM PATTERNS, PERFORMANCE | security.md |
| 9 | overview | 563 | PURPOSE, PHILOSOPHY, OUTPUT STRUCTURE, USE THE COMMANDS | - |
| 10 | workflows | 596 | FIRST TIME SETUP, AFTER CODE CHANGES, PULL REQUEST REVIEW, SECURITY AUDIT, PERFORMANCE OPTIMIZATION, CI/CD PIPELINE, UNDERSTANDING RESULTS, NOTE ON WORKSET | - |
| 11 | exit-codes | 640 | EXIT CODES, USAGE IN CI/CD | - |
| 12 | env-vars | 673 | FILE SIZE LIMITS, TIMEOUTS, PERFORMANCE, EXAMPLES | - |
| 13 | database | 705 | DATABASE LOCATIONS, KEY TABLES, JUNCTION TABLES, MANUAL QUERIES, SCHEMA DOCUMENTATION | - |
| 14 | troubleshooting | 783 | COMMON ERRORS AND SOLUTIONS, GETTING HELP | - |
| 15 | rust | 837 | RUST TABLES, MODULE RESOLUTION, UNSAFE CODE ANALYSIS, EXAMPLE QUERIES, USE THE COMMANDS, SUPPORTED FEATURES, CARGO INTEGRATION, CROSS-LANGUAGE ANALYSIS | - |
| 16 | callgraph | 981 | WHY CALL GRAPHS MATTER, CALL GRAPH STRUCTURE, STATIC VS DYNAMIC CALLS, EXAMPLE QUERIES, USE THE COMMANDS, RELATED CONCEPTS | dataflow.md |
| 17 | dependencies | 1076 | THREE DEPENDENCY LEVELS, PACKAGE DEPENDENCY SOURCES, DEPENDENCY ANALYSIS MODES, SECURITY IMPLICATIONS, TYPICAL WORKFLOW, USE THE COMMANDS, RELATED CONCEPTS | - |
| 18 | graph | 1192 | TWO TYPES OF GRAPHS, WHAT GRAPHS REVEAL, DATABASE STRUCTURE, TYPICAL WORKFLOW, USE THE COMMANDS, VISUALIZATION MODES, RELATED CONCEPTS | dataflow.md |
| 19 | architecture | 1278 | EXTRACTION PIPELINE, SCHEMA NORMALIZATION, QUERY ENGINE ARCHITECTURE, TWO-DATABASE DESIGN, INDEX MAINTENANCE, PERFORMANCE CHARACTERISTICS, JUNCTION TABLE PATTERN | planning.md |
| 20 | context | 1365 | THE PROBLEM IT SOLVES, CLASSIFICATION STATES, HOW IT WORKS, YAML RULE FORMAT, USE CASES, EXAMPLE WORKFLOW, OUTPUT FORMAT, IMPORTANT DISTINCTION, USE THE COMMAND | refactor.md |

### manual_lib02.py (21 topics)

| # | Topic | Line | Current Sections | Agent Reference |
|---|-------|------|------------------|-----------------|
| 21 | boundaries | 4 | KEY CONCEPTS, BOUNDARY QUALITY LEVELS, WHY DISTANCE MATTERS, MULTI-TENANT SECURITY, USE THE COMMAND, RELATED CONCEPTS | security.md |
| 22 | docker | 108 | THE SECURITY RISKS, WHAT THEAUDITOR DETECTS, SEVERITY LEVELS, DOCKERFILE BEST PRACTICES, MULTI-STAGE BUILDS, USE THE COMMAND, RELATED CONCEPTS | security.md |
| 23 | lint | 234 | WHAT LINTING DOES, WHY NORMALIZE OUTPUT, SUPPORTED LINTERS, AUTO-DETECTION, WORKSET MODE, SEVERITY MAPPING, COMMON WORKFLOWS, USE THE COMMAND, RELATED CONCEPTS | - |
| 24 | frameworks | 351 | HOW DETECTION WORKS, DETECTED FRAMEWORKS BY CATEGORY, WHY FRAMEWORK DETECTION MATTERS, PRIMARY VS SECONDARY FRAMEWORKS, DATABASE STORAGE, USE THE COMMAND, RELATED CONCEPTS | - |
| 25 | docs | 459 | WHY DOCUMENTATION CACHING, HOW IT WORKS, SECURITY CONSIDERATIONS, DOCUMENTATION CAPSULE FORMAT, OFFLINE MODE, TYPICAL WORKFLOW, USE THE COMMANDS, RELATED CONCEPTS | - |
| 26 | rules | 568 | RULE ARCHITECTURE, PATTERN FILE FORMAT, PATTERN CATEGORIES, PYTHON AST RULE FORMAT, SEVERITY LEVELS, CUSTOM PATTERNS, USE THE COMMANDS, RELATED CONCEPTS | security.md |
| 27 | setup | 685 | WHY SANDBOXED ENVIRONMENT, WHAT GETS INSTALLED, DIRECTORY STRUCTURE, OFFLINE VULNERABILITY SCANNING, MULTI-PROJECT USAGE, TYPICAL WORKFLOW, USE THE COMMAND, RELATED CONCEPTS | - |
| 28 | ml | 792 | THE ML VALUE PROPOSITION, THREE COMMANDS, WHAT THE MODELS LEARN, FEATURE ENGINEERING, DATA REQUIREMENTS, HUMAN FEEDBACK LOOP, TYPICAL WORKFLOW, USE THE COMMANDS, RELATED CONCEPTS | - |
| 29 | planning | 916 | KEY BENEFITS, DATABASE STRUCTURE, VERIFICATION SPECS, COMMON WORKFLOWS, SUBCOMMANDS, USE THE COMMANDS | planning.md |
| 30 | terraform | 1001 | WHAT IT DETECTS, PROVISIONING GRAPH, SUBCOMMANDS, TYPICAL WORKFLOW, OUTPUT FILES, USE THE COMMANDS | security.md |
| 31 | tools | 1069 | TOOL CATEGORIES, TOOL SOURCES, SUBCOMMANDS, TYPICAL WORKFLOW, CORE REQUIRED TOOLS, USE THE COMMANDS | - |
| 32 | metadata | 1137 | WHY METADATA MATTERS, CHURN METRICS, COVERAGE METRICS, SUBCOMMANDS, SUPPORTED COVERAGE FORMATS, TYPICAL WORKFLOW, USE THE COMMANDS, OUTPUT FILES | - |
| 33 | cdk | 1213 | WHAT CDK IS, SECURITY CHECKS, HOW IT WORKS, EXIT CODES, TYPICAL WORKFLOW, COMPARISON WITH TERRAFORM, USE THE COMMANDS, RELATED COMMANDS | security.md |
| 34 | graphql | 1297 | WHAT THIS DOES, HOW IT WORKS, SUBCOMMANDS, TYPICAL WORKFLOW, FRAMEWORK SUPPORT, OUTPUT, USE THE COMMANDS, RELATED COMMANDS | dataflow.md |
| 35 | blueprint | 1382 | DRILL-DOWN MODES, ADDITIONAL OPTIONS, WHAT IT SHOWS, EXAMPLES, PERFORMANCE, PREREQUISITES, RELATED COMMANDS, NOTE | planning.md |
| 36 | refactor | 1451 | THE PROBLEM IT SOLVES, WHAT IT DETECTS, HOW IT WORKS, OPTIONS, EXAMPLES, PERFORMANCE, PREREQUISITES, RELATED COMMANDS, NOTE | refactor.md |
| 37 | query | 1516 | QUERY TARGETS, ACTION FLAGS, MODIFIERS, EXAMPLES, PERFORMANCE, PREREQUISITES, RELATED COMMANDS, ANTI-PATTERNS | - |
| 38 | deps | 1596 | SUPPORTED FILES, OPERATION MODES, SELECTIVE UPGRADES, VULNERABILITY SCANNING, EXAMPLES, OUTPUT FILES, EXIT CODES, PERFORMANCE, PREREQUISITES, RELATED COMMANDS | - |
| 39 | explain | 1659 | TARGET TYPES, WHAT IT RETURNS, WHY USE THIS, EXAMPLES, PERFORMANCE, OPTIONS, PREREQUISITES, RELATED COMMANDS | - |
| 40 | deadcode | 1724 | WHAT IT DETECTS, CONFIDENCE LEVELS, ALGORITHM, EXAMPLES, PERFORMANCE, PREREQUISITES, EXIT CODES, RELATED COMMANDS | refactor.md |
| 41 | session | 1784 | WHY SESSION ANALYSIS, SESSION LOCATIONS, AUTO-DETECTION, ACTIVITY CLASSIFICATION, EFFICIENCY METRICS, INTERPRETATION GUIDELINES, ML DATABASE, USE THE COMMANDS, RELATED COMMANDS | - |

---

## Rich Formatting Reference

The manual renderer (manual.py:17-126) supports specific formatting patterns:

### Section Headers
```
UPPERCASE TEXT:
```
Renders as bold cyan header. Must be ALL CAPS followed by colon at line start.

### Bullet Points
```
- Simple bullet
- Term: Definition with yellow term
```
`- ` prefix. If contains `: `, term before colon is highlighted yellow.

### Numbered Lists
```
1. First item
2. Second item
```
Number followed by `. ` prefix. Number renders bold.

### Code Blocks
Lines starting with these patterns get syntax highlighting:
- `aud ` - bash highlighting
- `python ` - python highlighting
- `import ` - python highlighting
- `def ` - python highlighting
- `class ` - python highlighting
- `$` - bash highlighting
- `>>>` - python highlighting
- `cursor.` - python highlighting
- `conn.` - python highlighting

### Command with Comment
```
aud command --flag  # This is a comment
```
Command renders green, comment renders dim.

---

## Agent System Integration Reference

### Agent to Topic Mapping

| Agent | Purpose | Manual Topics |
|-------|---------|---------------|
| security.md | Security analysis, taint tracking | taint, fce, severity, patterns, boundaries, docker, rules, terraform, cdk |
| refactor.md | Code refactoring, dead code | context, refactor, deadcode |
| planning.md | Planning, architecture, impact | impact, architecture, blueprint, planning |
| dataflow.md | Source-to-sink tracing | cfg, callgraph, graph, graphql |

### Agent Command Quick Reference (from AGENTS.md)

These commands MUST be referenced in relevant manual topics:

| Need | Command |
|------|---------|
| Project structure | `aud blueprint --structure` |
| Dependency info | `aud blueprint --deps` |
| Taint summary | `aud blueprint --taint` |
| Boundary summary | `aud blueprint --boundaries` |
| Large files | `aud blueprint --monoliths` |
| List symbols | `aud query --file X --list all` |
| Who calls this? | `aud query --symbol X --show-callers` |
| What does this call? | `aud query --symbol X --show-callees` |
| Dead code | `aud deadcode` |
| Boundary distances | `aud boundaries --type input-validation` |
| Change impact | `aud impact --symbol X --planning-context` |
| Full analysis | `aud full` |

### Agent Philosophy (must align with manual content)

1. **Database = Ground Truth** - Query don't guess
2. **Precedents Over Invention** - Follow existing patterns
3. **Evidence Citations** - Every decision backed by query
4. **Autonomous Execution** - Don't ask, execute
5. **Zero Recommendation Without Facts** - Present findings, let user decide

---

## Before/After Example (REAL Content)

### Current State: `taint` topic (manual_lib01.py:4-69)

The current `taint` topic is already well-structured but concept-focused:

```python
"taint": {
    "title": "Taint Analysis",
    "summary": "Tracks untrusted data flow from sources to dangerous sinks",
    "explanation": """
Taint analysis is a security technique that tracks how untrusted data (tainted data)
flows through a program to potentially dangerous operations (sinks).

CONCEPTS:
- Source: Where untrusted data enters (user input, network, files)
- Sink: Dangerous operations (SQL queries, system commands, file writes)
- Taint: The property of being untrusted/contaminated
- Propagation: How taint spreads through assignments and function calls

HOW IT WORKS:
1. Read database tables: function_call_args, assignments from repo_index.db
2. Build call graph for inter-procedural analysis across functions
3. Identify sources: Match against 140+ taint source patterns
...
""",
}
```

### Target State: Workflow-Centric Structure

```python
"taint": {
    "title": "Taint Analysis",
    "summary": "Tracks untrusted data flow from sources to dangerous sinks",
    "explanation": """
WHAT IT IS:
Taint analysis finds where user input reaches dangerous functions without
sanitization - the root cause of injection vulnerabilities (SQL injection,
XSS, command injection).

WHEN TO USE IT:
- Security audit before deployment
- Investigating a reported vulnerability
- PR review for security-sensitive code changes
- After running aud full, to understand data flow paths

HOW TO USE IT:
PREREQUISITES:
    aud full                           # Build database first (required)

STEPS:
    1. Run taint analysis:
       aud taint                       # Full analysis with defaults
       aud taint --severity critical  # Only critical findings

    2. Review findings in .pf/raw/taint_analysis.json

    3. For each finding, verify:
       - Is the source actually user-controlled?
       - Is there sanitization the tool missed?
       - Is this a true positive?

EXAMPLE - Finding SQL Injection:
    aud full && aud taint --severity high
    # Output shows paths from request.body to db.execute()

COMBINING WITH OTHER TOOLS:
- After taint: run aud fce to correlate with other findings
- Use aud explain <function> to understand context around a finding
- Use aud boundaries to check validation distance from entry points
- Check aud manual patterns for detection rules used

AGENT WORKFLOW:
When using the security agent (/theauditor:security), taint analysis runs
automatically as part of the Phase 3 analysis. The agent queries existing
taint results with: aud blueprint --taint

RELATED:
Commands: aud taint, aud fce, aud boundaries, aud blueprint --taint
Topics: aud manual fce, aud manual boundaries, aud manual patterns

COMMON MISTAKES:
- Running taint before aud full: No database = no analysis
- Ignoring MEDIUM findings: They often combine to become CRITICAL via FCE
- Not checking .pf/raw/taint_analysis.json: Terminal output is summary only

COMMAND OPTIONS (verified from source):
- --db: Path to SQLite database (default: .pf/repo_index.db)
- --output: Output path (default: .pf/raw/taint_analysis.json)
- --max-depth: Maximum inter-procedural depth (default: 5)
- --json: Output raw JSON instead of formatted report
- --verbose: Show detailed path information
- --severity: Filter by severity (all, critical, high, medium, low)

EXIT CODES:
- 0: Success, no vulnerabilities found
- 1: High severity vulnerabilities detected
- 2: Critical security vulnerabilities found
""",
}
```

### Key Changes Made

| Before | After |
|--------|-------|
| Starts with concept definition | Starts with WHAT IT IS (brief) + WHEN TO USE IT |
| HOW IT WORKS is internal architecture | HOW TO USE IT is step-by-step commands |
| No PREREQUISITES section | Explicit PREREQUISITES with aud full |
| No COMBINING WITH OTHER TOOLS | Cross-references to related commands |
| No AGENT WORKFLOW | References security.md agent integration |
| No COMMON MISTAKES | Documents pitfalls and solutions |

---

## Verified Command Reference

These commands exist and work (verified):

### Track 1: Security
```bash
aud taint --help             # EXISTS (taint analysis command)
aud detect-patterns --help   # EXISTS
aud boundaries --help        # EXISTS
aud manual taint             # EXISTS
```

Note: `aud fce` is NOT a standalone command. FCE runs as part of `aud full` pipeline. Use `aud blueprint --taint` to see taint results.
Note: `aud insights` is NOT a command. Insights are accessed via `aud learn`, `aud suggest`, and `aud blueprint --taint`.

### Track 2: Graph/Architecture
```bash
aud graph build --help       # EXISTS
aud graph query --help       # EXISTS
aud blueprint --help         # EXISTS
aud impact --help            # EXISTS
```

### Track 3: Code Analysis
```bash
aud deadcode --help          # EXISTS
aud refactor --help          # EXISTS
aud workset --help           # EXISTS
aud query --help             # EXISTS
aud explain --help           # EXISTS
```

### Track 4: Infrastructure
```bash
aud full --help              # EXISTS
aud setup-ai --help          # EXISTS
aud manual pipeline          # EXISTS
aud manual database          # EXISTS
```

### Track 5: Integrations
```bash
aud docker-analyze --help    # EXISTS - Note: docker-analyze not docker
aud terraform provision --help  # EXISTS - subcommand
aud cdk analyze --help       # EXISTS - subcommand
aud detect-frameworks --help # EXISTS
```

### Track 6: Advanced/ML
```bash
aud planning --help          # EXISTS
aud session analyze --help   # EXISTS - subcommand
aud learn --help             # EXISTS
aud deps --help              # EXISTS
aud tools list --help        # EXISTS - subcommand
```

---

## Quality Gates

### Per-Topic Gate
Each topic must have:
- [ ] WHAT IT IS section (1 paragraph max)
- [ ] WHEN TO USE IT section (bullet scenarios)
- [ ] HOW TO USE IT with PREREQUISITES, STEPS, EXAMPLE
- [ ] COMBINING WITH OTHER TOOLS section
- [ ] RELATED section with Commands and Topics
- [ ] COMMON MISTAKES section
- [ ] No "aud index" references (deprecated)
- [ ] No emojis (Windows crash)
- [ ] Verified working examples
- [ ] Agent reference (if topic maps to agent)

### Final Gate
```bash
# All topics render without error
for topic in $(aud manual --list 2>/dev/null | awk '{print $1}'); do
  aud manual $topic > /dev/null 2>&1 && echo "OK: $topic" || echo "FAIL: $topic"
done

# No deprecated references
grep -r "aud index" theauditor/commands/manual*.py | grep -v "deprecated"
# Must be empty

# No emojis
grep -P '[\x{1F300}-\x{1F9FF}]' theauditor/commands/manual*.py
# Must be empty
```

---

## Open Questions

None - scope is clearly defined. Execute.
