# AI-Optimized CLI Help System - Foundation Document

**Purpose:** Strategy and design brief for TheAuditor's CLI help system, optimized for AI agent consumption.

**Status:** Foundation document. Use this to create OpenSpec proposal AFTER `refactor-cli-help` cleanup is complete.

**Author:** Lead Auditor (Gemini) + AI Coder (Claude)
**Date:** 2025-11-23

---

## The Problem

AI agents interact with CLI tools differently than humans:

| Aspect | Human | AI Agent |
|--------|-------|----------|
| **Reading** | Linear, skims for keywords | Tokenizes entire blob, maps intent to tools |
| **Learning** | Follows abstract rules | Few-shot learner - copies patterns |
| **Failure mode** | Asks for help | Hallucinates arguments |

Current `aud --help` (366 lines) fails both:
- **Too dense** for humans (can't scan)
- **Too noisy** for AI (truncates context, gets confused)

---

## The Strategy: Router vs Executor vs System Prompt

### 1. Root Help (`aud --help`) = The Router

**Goal:** Help AI pick the RIGHT command.

**Content:**
- Group commands by **Intent**, not function
- Include "USE WHEN" + "GIVES" annotations per command
- NO flags here - just routing information

**Categories by Intent:**
```
PRIMARY COMMANDS (Context & Understanding)
  - explain, query, structure

PROJECT MAINTENANCE (Setup & Indexing)
  - full, setup-ai, graph

SECURITY ANALYSIS
  - detect-patterns, taint-analyze, boundaries

UTILITIES
  - manual, report, workset
```

### 2. Sub-command Help (`aud <cmd> --help`) = The Instruction Manual

**Goal:** Ensure valid execution.

**Content:**
- Heavy on **Examples** (few-shot learning)
- Explicit **Output Format** section
- **Anti-Patterns** section (what NOT to do)
- All flags with clear descriptions

### 3. The Manual (`aud manual`) = The System Prompt

**Goal:** Philosophy injection for AI context.

**Content:**
- Tool philosophy ("Truth Courier, Not Mind Reader")
- When to use which command
- Token-dense markdown (not human-pretty)
- Run at session start, add to AI context

---

## Target Mockup: `aud --help`

```text
Usage: aud [COMMAND] [OPTIONS]

TheAuditor - AI-First Codebase Intelligence
============================================
Static analysis + SQLite indexing + graph theory.
Prevents "context window burnout" with structured answers.

PRIMARY COMMANDS (Context & Understanding)
------------------------------------------
  explain     Comprehensive context for file, symbol, or component.
              > USE WHEN: Need to understand code before editing.
              > GIVES: Definitions, dependencies, hooks, call flows.

  query       Precise lookups in the codebase database.
              > USE WHEN: Need specific facts ("Who calls X?", "Where is Y?").
              > GIVES: Exact file:line locations and relationships.

  structure   Project architecture overview.
              > USE WHEN: Starting work on unfamiliar codebase.
              > GIVES: Module map, entry points, tech stack.

PROJECT MAINTENANCE (Setup & Indexing)
--------------------------------------
  full        Complete analysis pipeline (20 phases).
              > RUN: First time, or after major changes.

  setup-ai    Create sandboxed analysis environment.
              > RUN: Once per project, before first 'aud full'.

  graph       Dependency graph management.
              > RUN WHEN: 'explain' shows stale dependency data.

SECURITY ANALYSIS
-----------------
  detect-patterns   Security vulnerability detection (200+ rules).
  taint-analyze     Data flow from sources to sinks.
  boundaries        Security boundary enforcement analysis.

UTILITIES
---------
  manual      Philosophy and concepts (add to AI context).
  report      Generate consolidated findings.
  workset     Compute file subset for incremental analysis.

GLOBAL FLAGS
------------
  --json      Output as JSON (preferred for AI consumption).
  --quiet     Minimal output for CI/CD.

EXAMPLES
--------
  1. Understand a file:    aud explain src/auth/service.py
  2. Find callers:         aud query --symbol validate_user --show-callers
  3. Full security audit:  aud full --offline

Run 'aud [COMMAND] --help' for flags and detailed examples.
Run 'aud manual --list' for concept explanations.
```

**Line count:** ~55 lines (down from 366)
**Discriminative power:** High - each command has USE WHEN/GIVES

---

## Target Mockup: `aud query --help`

```text
Usage: aud query [OPTIONS]

Query the indexed database for symbols, calls, and relationships.
FAST (<10ms). Deterministic. NO inference or guessing.

ARGUMENTS
---------
  --symbol <NAME>       Symbol name (e.g., 'UserController', 'process_payment').
                        Supports partial matches and dot-notation (User.save).
  --file <PATH>         Query by file path (partial match supported).
  --api <ROUTE>         Query API endpoint by route pattern.

FLAGS
-----
  --show-callers        List functions that call this symbol.
  --show-callees        List functions this symbol calls.
  --show-code           Include source code snippets (recommended).
  --depth <N>           Call graph depth (1-5, default: 1).
  --format <FMT>        'text' (default) or 'json'.

EXAMPLES (Copy These Patterns)
------------------------------
  # Find where a function is used
  aud query --symbol "authenticate" --show-callers --depth 2

  # See what a function depends on
  aud query --symbol "ProcessOrder" --show-callees --show-code

  # Find a specific class method
  aud query --symbol "OrderController.create"

  # JSON output for parsing
  aud query --symbol "validate" --show-callers --format json

ANTI-PATTERNS (Do NOT Do This)
------------------------------
  X  aud query "how does auth work?"
     -> Use 'aud explain' or 'aud manual' for conceptual questions

  X  aud query --file "main.py"
     -> Use 'aud explain main.py' for file summaries

  X  aud query --symbol "foo" (without --show-callers or --show-callees)
     -> Always specify what relationship you want

OUTPUT FORMAT
-------------
Text mode:
  Symbol: authenticate (function)
  File: src/auth/service.py:42
  Callers:
    - src/api/login.py:15 -> login_handler()
    - src/api/oauth.py:88 -> oauth_callback()

JSON mode (--format json):
  {
    "symbol": "authenticate",
    "type": "function",
    "file": "src/auth/service.py",
    "line": 42,
    "callers": [...]
  }
```

---

## Target Mockup: `aud explain --help`

```text
Usage: aud explain [OPTIONS] TARGET

Comprehensive context about a file, symbol, or component in ONE command.
Eliminates need for multiple queries. Optimized for AI workflows.

TARGET (auto-detected)
----------------------
  File path:      aud explain src/auth.ts
  Symbol:         aud explain authenticateUser
  Class.method:   aud explain UserController.create
  Component:      aud explain Dashboard

RETURNS
-------
  For files:
    - SYMBOLS DEFINED: Functions, classes, variables with line numbers
    - HOOKS USED: React/Vue hooks (if applicable)
    - DEPENDENCIES: Files imported by this file
    - DEPENDENTS: Files that import this file
    - OUTGOING CALLS: Functions called from this file
    - INCOMING CALLS: Functions in this file called elsewhere

  For symbols:
    - DEFINITION: File, line, type, signature
    - CALLERS: Who calls this symbol (with code snippets)
    - CALLEES: What this symbol calls

FLAGS
-----
  --format [text|json]    Output format (json recommended for AI).
  --section <NAME>        Show only: symbols|hooks|deps|callers|callees
  --no-code               Disable code snippets (faster).
  --depth <N>             Call graph depth (default: 2).
  --limit <N>             Max items per section (default: 20).

EXAMPLES (Copy These Patterns)
------------------------------
  # Full context for a file (MOST COMMON)
  aud explain src/auth/service.ts

  # Symbol with callers and code
  aud explain validateInput

  # JSON for AI consumption
  aud explain Dashboard --format json

  # Just dependencies
  aud explain utils/helpers.py --section deps

ANTI-PATTERNS (Do NOT Do This)
------------------------------
  X  aud explain --symbol foo
     -> Just use: aud explain foo (auto-detects)

  X  aud explain .
     -> Use 'aud structure' for project overview

  X  Running 'aud query' before 'aud explain'
     -> Always try 'explain' first - it's more comprehensive

WHY USE THIS
------------
  - Single command replaces 5-6 queries
  - Saves 5,000-10,000 context tokens per task
  - Auto-detects target type (no flags needed)
  - Includes code snippets by default

OUTPUT FORMAT
-------------
Text mode outputs human-readable sections.
JSON mode outputs structured data for programmatic use.
```

---

## Implementation Notes

### How to Add "USE WHEN" / "GIVES" Annotations

Option 1: Metadata dict in cli.py
```python
COMMAND_ANNOTATIONS = {
    'explain': {
        'use_when': 'Need to understand code before editing',
        'gives': 'Definitions, dependencies, hooks, call flows',
    },
    'query': {
        'use_when': 'Need specific facts ("Who calls X?")',
        'gives': 'Exact file:line locations and relationships',
    },
}
```

Option 2: Convention in docstrings
```python
@click.command()
def explain():
    """Comprehensive context for file, symbol, or component.

    USE_WHEN: Need to understand code before editing.
    GIVES: Definitions, dependencies, hooks, call flows.

    [rest of docstring]
    """
```

### How to Add Anti-Patterns

Add to each command's docstring:
```python
"""
ANTI-PATTERNS (Do NOT Do This):
  X  aud query "how does auth work?"
     -> Use 'aud explain' for conceptual questions
"""
```

### How to Structure Output Format Sections

Explicit in docstring:
```python
"""
OUTPUT FORMAT:
  Text mode:
    [example output]

  JSON mode (--format json):
    [example JSON]
"""
```

---

## Key Principles for AI-Optimized Help

1. **Discriminative Power**
   - "USE WHEN" tells AI planning module which tool fits
   - Prevents using `query` when should use `explain`

2. **Negative Constraints**
   - "Anti-Patterns" explicitly states what NOT to do
   - LLMs hallucinate when struggling - ground them

3. **Few-Shot Learning**
   - Examples section with copy-paste patterns
   - AI learns better from examples than rules

4. **JSON Preference**
   - Always mention `--json` option
   - AI parses structured data more reliably

5. **Token Density**
   - Every word should help routing decision
   - Remove filler, keep discriminative content

---

## Migration Path

### Phase 1: Cleanup (Current - refactor-cli-help)
- Remove redundant sections from root help
- Deprecate garbage commands (init-config, init-js)
- Hide dev flags
- Move educational content to manual
- Result: Less garbage, but not yet AI-optimized

### Phase 2: AI-Optimization (Future proposal based on this doc)
- Restructure categories by Intent
- Add USE WHEN / GIVES annotations
- Add Anti-Patterns to subcommands
- Add Output Format sections
- Add Examples sections
- Result: Properly AI-optimized CLI

### Phase 3: Validation
- Test with AI agents (Claude, GPT-4, Gemini)
- Measure: Correct command selection rate
- Measure: Valid argument construction rate
- Iterate based on failure modes

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| `aud --help` line count | 366 | <60 |
| Commands with USE WHEN/GIVES | 0 | 100% |
| Commands with Anti-Patterns | 0 | 100% |
| Commands with Examples section | ~20% | 100% |
| Commands with Output Format doc | ~10% | 100% |
| AI correct command selection | Unknown | >90% |

---

## References

- Lead Auditor strategy document (2025-11-23)
- Click documentation: Custom help formatting
- Anthropic best practices: Tool use with Claude

---

**Next Steps:**
1. Complete `refactor-cli-help` proposal (garbage removal)
2. Create Phase 2 OpenSpec proposal using this document
3. Implement and test with AI agents
