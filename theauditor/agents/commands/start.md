---
name: TheAuditor: Start
description: Orchestrator - analyze request, use TheAuditor tools, route to appropriate agent.
category: TheAuditor
tags: [theauditor, start, orchestrator, analyze]
---

# TheAuditor Orchestrator

**YOU ARE USING THEAUDITOR.** Every task starts here. No exceptions.

---

## Phase 0: Load Agent System (MANDATORY)

Read the full agent orchestrator documentation FIRST:

```
Read: .auditor_venv/.theauditor_tools/agents/AGENTS.md
```

This file contains:
- Agent routing table (which agent for which task)
- Command quick reference (all aud commands)
- Anti-patterns (what NOT to do)
- Thresholds (coupling scores, file sizes)
- Evidence citation requirements

**DO NOT SKIP THIS.** Without AGENTS.md, you don't know the system.

---

## Phase 1: Immediate Context Load (ALWAYS)

Before analyzing the user's request, ALWAYS run these commands:

```bash
aud blueprint # Overview of entire codebase
aud blueprint --structure    # Architecture, frameworks, conventions
aud blueprint --monoliths    # Large files requiring chunked analysis.
aud refactor # Scans migrations to check for schema mismatches.
aud deadcode # Check for orphaned/dead/zombie code
```

**DO NOT SKIP THIS.** Even for "simple" requests, blueprint provides:
- Detected frameworks (Express, FastAPI, React, etc.)
- Naming conventions (snake_case vs camelCase)
- Architectural precedents (monorepo, domain split, etc.)
- Validation libraries in use (Zod, Joi, Pydantic)

---

## Phase 2: Parse User Intent

Match the user's request to an agent:

| Keywords in Request | Route To | Slash Command |
|---------------------|----------|---------------|
| plan, architecture, design, structure, implement, approach | Planning | `/theauditor:planning` |
| refactor, split, extract, modularize, merge, consolidate | Refactor | `/theauditor:refactor` |
| security, vulnerability, XSS, SQLi, CSRF, taint, sanitize | Security | `/theauditor:security` |
| dataflow, trace, track, flow, source, sink, propagate | Dataflow | `/theauditor:dataflow` |
| impact, blast radius, coupling, dependencies, risk | Impact | `/theauditor:impact` |

**If unclear:** Ask the user which workflow fits best. Don't guess.

---

## Phase 3: Execute Agent Protocol

1. **Read the full agent protocol** from `agents/<agent>.md`
2. **Follow every phase** - no skipping steps
3. **Cite every query** - every claim backed by database evidence
4. **Present findings for approval** before implementation

---

## Command Cheat Sheet

### Discovery (Run First)
| Command | Purpose |
|---------|---------|
| `aud blueprint --structure` | Architecture overview (MANDATORY FIRST) |
| `aud blueprint --deps` | Dependencies and versions |
| `aud blueprint --monoliths` | Large files (>1950 lines) |
| `aud blueprint --taint` | Taint analysis summary (from DB) |
| `aud blueprint --boundaries` | Validation boundary summary |

### Query (Instead of Reading Files)
| Command | Purpose |
|---------|---------|
| `aud query --file X --list all` | List all symbols in file |
| `aud query --symbol X --show-callers` | Who calls this? |
| `aud query --symbol X --show-callees` | What does this call? |
| `aud query --pattern "%name%"` | SQL LIKE search on symbol names |
| `aud explain path/to/file.py` | Full context for file |
| `aud explain SymbolName` | Full context for symbol |

### Analysis
| Command | Purpose |
|---------|---------|
| `aud boundaries` | Input validation boundary analysis |
| `aud deadcode` | Dead code detection |
| `aud deadcode --path-filter 'dir/%'` | Dead code in specific directory |
| `aud taint` | Trace data flow (uses built-in patterns) |
| `aud refactor` | Detect migration/schema issues |
| `aud impact --symbol X` | Blast radius and coupling |
| `aud detect-patterns` | Security pattern detection |

**NOTE:** `--path-filter` accepts SQL LIKE syntax (`%`) or glob patterns (`**`).

### Refactor Support
| Command | Purpose |
|---------|---------|
| `aud refactor --file X --validate-only` | Validate YAML before running |
| `aud refactor --query-last` | Get last refactor results from DB |

---

## Anti-Patterns

Do NOT:
- Read files to understand structure
- Guess frameworks or libraries
- Guess command flags
- Ask permission before running commands
- Make recommendations without query evidence

---

## Why TheAuditor?

1. **No hallucination** - Every claim backed by database query
2. **Faster** - Query beats file reading
3. **Token efficient** - Structured data, not raw files
4. **Consistent** - Same analysis every time
5. **Evidence trail** - Audit log of what was queried

---

## After Routing

Once you've identified the agent:

1. Run the slash command (e.g., `/theauditor:planning`)
2. Or read the full protocol: `Read: agents/<agent>.md`
3. Follow every phase to completion
4. Present findings with evidence citations
5. Wait for user approval before implementation

**NEVER implement without presenting evidence-backed findings first.**
