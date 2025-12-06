# Design: CLI Help Content Optimization

## Context

TheAuditor's CLI has 38 command files producing 80+ commands. The Rich formatting infrastructure is complete (RichCommand class works). What's missing is content quality - the actual text in docstrings is outdated, inconsistent, and not optimized for AI consumption.

**Primary users:** AI assistants (Claude Code, Gemini, etc.)
**Secondary users:** Humans (developers)

## Goals / Non-Goals

**Goals:**
- Every command has accurate, verified help text
- Every command has AI ASSISTANT CONTEXT section
- Zero references to deprecated commands (aud index)
- All examples are copy-paste executable
- Content explains WHEN and WHY, not just WHAT

**Non-Goals:**
- Changing command behavior (content only)
- Modifying Rich formatting code (already complete)
- Adding new commands or options
- Changing manual entries (separate ticket)

## Technical Decisions

### Decision 1: Docstring Section Format

**Choice:** Standardized section format parsed by RichCommand (theauditor/cli.py:141-350)

**RichCommand Section Parsing (cli.py:144-159):**

RichCommand recognizes these section headers in docstrings:
```python
SECTIONS = [
    "AI ASSISTANT CONTEXT",
    "DESCRIPTION",
    "EXAMPLES",
    "COMMON WORKFLOWS",
    "OUTPUT FILES",
    "PERFORMANCE",
    "EXIT CODES",
    "RELATED COMMANDS",
    "SEE ALSO",
    "TROUBLESHOOTING",
    "NOTE",
    "WHAT IT DETECTS",
    "DATA FLOW ANALYSIS METHOD",
]
```

**Parsing Rules (cli.py:179-205):**
- Section headers are ALL CAPS, optionally followed by colon
- Parser matches `stripped.upper().startswith(section_name.upper())`
- Content after header is collected until next section header
- First lines before any section header become "summary"

**Standard Docstring Template:**
```python
"""One-line summary for main help listing.

DESCRIPTION:
  Expanded explanation in 2-3 sentences. What problem does this solve?
  When would you use this vs alternatives?

AI ASSISTANT CONTEXT:
  Purpose: Single sentence describing what this accomplishes
  Input: Required files/databases with paths (e.g., .pf/repo_index.db)
  Output: What gets produced with paths (e.g., .pf/raw/analysis.json)
  Prerequisites: What must run first (use "aud full" not "aud index")
  Integration: How this fits in typical workflow

EXAMPLES:
  aud command --option     # Comment explaining use case
  aud command --other      # Another common pattern

COMMON WORKFLOWS:
  Workflow name:
    aud command1 && aud command2

RELATED COMMANDS:
  aud other    Brief description of when to use instead

SEE ALSO:
  aud manual topic
"""
```

**Rationale:** RichCommand already parses these sections. Consistency enables reliable AI parsing.

### Decision 2: Verification Before Edit

**Choice:** Every AI team MUST run commands before editing docstrings

**Rationale:** Prevents hallucination. If docstring says "detects 140+ patterns" but reality is different, we catch it.

**Protocol:**
1. Run `aud <command> --help` to see current state
2. Run command with test args to verify functionality
3. Cross-reference with implementation if claims seem wrong
4. Only then edit the docstring

### Decision 3: No Fallback References

**Choice:** All prerequisites say "aud full", never "aud index"

**Rationale:** CLAUDE.md explicitly bans "aud index". It's deprecated. Every reference is a bug.

**Search pattern to verify:**
```bash
grep -r "aud index" theauditor/commands/*.py | grep -v "DEPRECATED"
```

### Decision 4: Parallel Track Independence

**Choice:** 6 tracks with zero cross-dependencies

**Rationale:** Enables 6 AI teams to work simultaneously. No blocking.

**Track boundaries:**
- Track 1: Core (full, taint, patterns, index, manual)
- Track 2: Graph (graph, graphql, cfg, fce)
- Track 3: Security (boundaries, docker, workflows, terraform, cdk)
- Track 4: Analysis (query, explain, impact, deadcode, refactor, context)
- Track 5: Infra (deps, tools, setup, workset, rules, lint, docs)
- Track 6: Planning (planning, session, ml, metadata, blueprint, detect_frameworks)

No file appears in multiple tracks. No shared state.

## AI ASSISTANT CONTEXT Templates

### Template for cfg.py (Group + analyze/viz subcommands)

**Group docstring (cfg.py:16-36):**
```python
AI ASSISTANT CONTEXT:
  Purpose: Analyze control flow graph complexity and detect unreachable code
  Input: .pf/repo_index.db (after aud full)
  Output: .pf/raw/cfg.json (complexity metrics), DOT/SVG diagrams
  Prerequisites: aud full (populates CFG data in database)
  Integration: Use after aud full to identify complex functions needing refactoring
```

### Template for deps.py

**Command docstring (deps.py:54-112):**
```python
AI ASSISTANT CONTEXT:
  Purpose: Analyze dependencies for vulnerabilities, outdated packages, and upgrades
  Input: package.json, pyproject.toml, requirements.txt, Cargo.toml, Dockerfiles
  Output: .pf/raw/deps.json, .pf/raw/deps_latest.json, .pf/raw/vulnerabilities.json
  Prerequisites: None (reads manifest files directly, no database required)
  Integration: Run standalone or as part of aud full --offline pipeline
```

### Template for planning.py (Group + 14 subcommands)

**Group docstring (planning.py:49-138):**
```python
AI ASSISTANT CONTEXT:
  Purpose: Database-centric task management with spec-based verification
  Input: .pf/planning.db (auto-created), YAML verification specs
  Output: .pf/planning.db updates, git snapshots, verification reports
  Prerequisites: aud full (for verify-task to query indexed code)
  Integration: Create plans, add tasks with specs, verify against indexed code
```

### Template for query.py

**Command docstring (query.py:143-232):**
```python
AI ASSISTANT CONTEXT:
  Purpose: Query code relationships from indexed database (symbols, callers, dependencies)
  Input: .pf/repo_index.db (after aud full)
  Output: Structured results (text, JSON, or tree format)
  Prerequisites: aud full (populates symbols, calls, refs tables)
  Integration: Use for precise lookups; use aud explain for comprehensive context
```

### Template for tools.py (Group + list/check/report subcommands)

**Group docstring (tools.py:186-208):**
```python
AI ASSISTANT CONTEXT:
  Purpose: Detect and verify installed analysis tools (linters, runtimes, scanners)
  Input: System PATH, .auditor_venv sandbox
  Output: Tool version information (stdout or .pf/raw/tools.json)
  Prerequisites: None (reads system state directly)
  Integration: Run before aud full to verify toolchain, or after setup-ai
```

### Template for _archive.py (Internal command)

**Command docstring (_archive.py:26-43):**
```python
AI ASSISTANT CONTEXT:
  Purpose: Internal command to archive previous run artifacts by run type
  Input: .pf/ directory contents
  Output: .pf/history/{full|diff}/<timestamp>/ archived artifacts
  Prerequisites: None (called internally by pipeline)
  Integration: Not for direct use - called by full/orchestrate workflows
```

### Template for index.py (Deprecated command)

**Command docstring - deprecation-focused:**
```python
AI ASSISTANT CONTEXT:
  Purpose: DEPRECATED - redirects to aud full for backwards compatibility
  Input: N/A (runs aud full instead)
  Output: N/A (runs aud full instead)
  Prerequisites: N/A
  Integration: DO NOT USE - always use 'aud full' or 'aud full --index' instead
```

## Reference Implementation

**theauditor/commands/full.py:68-192** is the gold standard. Key sections:

| Section | Lines | Purpose |
|---------|-------|---------|
| Summary | 95 | One-line for help listing |
| DESCRIPTION | 97-115 | Detailed 4-stage breakdown |
| AI ASSISTANT CONTEXT | 116-122 | Structured metadata for AI |
| EXAMPLES | 124-129 | Copy-paste commands with comments |
| COMMON WORKFLOWS | 131-143 | Named scenarios with command chains |
| OUTPUT FILES | 144-150 | File paths with descriptions |
| PERFORMANCE | 151-155 | Timing expectations by codebase size |
| EXIT CODES | 157-161 | Meaningful codes for scripting |
| RELATED COMMANDS | 163-167 | Cross-references with brief descriptions |
| SEE ALSO | 169-171 | Manual topic references |
| TROUBLESHOOTING | 173-187 | Problem -> solution format |
| NOTE | 189-192 | Important caveats |

## Content Guidelines

### What AI Assistants Need

1. **Purpose** - One sentence: what does this command do?
2. **Prerequisites** - What must exist/run before this works?
3. **Input** - What files/data does it read?
4. **Output** - What files/data does it produce?
5. **Examples** - Copy-paste commands that work
6. **Workflow position** - What comes before/after?

### What to Avoid

1. **Developer jargon** - "Inter-procedural data flow" -> "Traces data across functions"
2. **Unverified claims** - "Detects 200+ patterns" (verify this is true)
3. **Deprecated references** - "Run aud index first" (wrong - use aud full)
4. **Orphan examples** - Examples without context
5. **Missing prerequisites** - Commands that fail without prior steps

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| AI teams hallucinate content | Verification protocol requires running commands first |
| Inconsistent style across tracks | Final review phase catches inconsistencies |
| Breaking existing scripts | Help text changes don't affect behavior |
| Missing edge cases | Each track has verification checkpoint |

## Quality Gates

### Per-Track Gate
```bash
# No aud index references (except deprecation notice)
grep -i "aud index" theauditor/commands/<track-files>.py | grep -v DEPRECATED
# Should return nothing

# AI ASSISTANT CONTEXT present
grep "AI ASSISTANT CONTEXT" theauditor/commands/<track-files>.py
# Should match file count
```

### Final Gate
```bash
# Full sweep
grep -r "aud index" theauditor/commands/*.py | grep -v "DEPRECATED\|deprecated"
# Must be empty

# All commands have context
for f in theauditor/commands/*.py; do
  grep -q "AI ASSISTANT CONTEXT" "$f" || echo "MISSING: $f"
done
# Only __init__.py, config.py, manual_lib*.py should show
```

## Open Questions

None - scope is clearly defined. Execute.
