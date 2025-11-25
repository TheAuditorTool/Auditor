# TheAuditor Agent System

AI-powered code analysis workflows. Database-first, evidence-backed, zero hallucination.

---

## Agent Routing

| User Intent | Agent | Trigger Keywords |
|-------------|-------|------------------|
| Plan changes, design architecture | `planning.md` | plan, architecture, design, organize, structure, approach, implement |
| Refactor, split, modularize code | `refactor.md` | refactor, split, extract, modularize, merge, consolidate, break apart |
| Security audit, vulnerability scan | `security.md` | security, vulnerability, XSS, SQL injection, CSRF, taint, sanitize, exploit |
| Trace data flow, source-to-sink | `dataflow.md` | dataflow, trace, track, flow, source, sink, propagate, input, output |
| Assess change impact, blast radius | `planning.md` + `aud impact` | impact, blast radius, coupling, dependencies, risk |

**Loading agents:** Reference as `@/.theauditor_tools/agents/<agent>.md` or use slash commands `/theauditor:<agent>`.

---

## The One Rule: Database First

```
aud blueprint --structure   # BEFORE any planning
aud query --file X          # INSTEAD OF reading files
aud impact --symbol X       # BEFORE any changes
```

Every recommendation cites a database query. No exceptions.

---

## Command Quick Reference

| Need | Command |
|------|---------|
| Project structure, conventions, frameworks | `aud blueprint --structure` |
| Dependency info (packages, versions) | `aud blueprint --deps` |
| Taint summary (from DB) | `aud blueprint --taint` |
| Boundary summary (from DB) | `aud blueprint --boundaries` |
| Large files (>2150 lines) | `aud structure --monoliths` |
| List symbols in file | `aud query --file X --list all` |
| Who calls this? | `aud query --symbol X --show-callers` |
| What does this call? | `aud query --symbol X --show-callees` |
| Dead code detection | `aud deadcode` |
| Boundary distance analysis | `aud boundaries --type input-validation` |
| Change impact/coupling | `aud impact --symbol X --planning-context` |
| Full analysis pipeline | `aud full` |

**Performance Note:** `aud blueprint --taint` and `--boundaries` read from database (fast). Use these for summaries instead of re-running `aud taint-analyze` (slow).

**First time?** Run `aud --help` and `aud <command> --help`. Never guess syntax.

---

## Anti-Patterns (Waste Time, Get Rejected)

| Don't Do This | Do This Instead |
|---------------|-----------------|
| "Let me read the file to see..." | `aud query --file X --list functions` |
| "Based on typical patterns..." | `aud blueprint --structure` for THIS project |
| "I recommend using joi..." | `aud blueprint` to detect ACTUAL library (might be zod) |
| "Would you like me to run...?" | Just run it. Autonomous execution is the point. |
| Making recommendations without evidence | Cite the query: "Blueprint shows schemas/ uses domain split" |
| Inventing new patterns | Follow detected precedents from blueprint |

---

## How Agents Work

### Structure: Phase -> Task -> Job

Each agent follows the same hierarchy:
- **Phase**: Major workflow stage (Load Context, Query Patterns, Synthesize)
- **Task**: Specific goal within phase (T1.1, T1.2, etc.)
- **Job**: Atomic action with audit checkpoint

### Audit Loops

Every task ends with `**Audit:** [verification criteria]`. If audit fails, fix and re-audit before proceeding.

### Evidence Citations

Every recommendation must cite its source:
```
Evidence:
- aud blueprint: snake_case 99%, schemas/ (9 files, 320 avg lines)
- aud query: 45 functions, 12 python-prefixed (27%)
- aud impact: Coupling 45/100 MEDIUM, 16 affected files
```

### Key Thresholds

| Metric | LOW | MEDIUM | HIGH |
|--------|-----|--------|------|
| Coupling score | <30 | 30-70 | >70 (extract interface first) |
| Affected files | <10 | 10-30 | >30 (phase the change) |
| File size | <500 lines | 500-2150 | >2150 (chunked reading) |

---

## Slash Commands

Available after `aud setup-ai --target .`:

| Command | Purpose |
|---------|---------|
| `/theauditor:planning` | Database-first planning workflow |
| `/theauditor:refactor` | Code refactoring analysis |
| `/theauditor:security` | Security analysis and taint tracking |
| `/theauditor:dataflow` | Source-to-sink dataflow tracing |
| `/theauditor:impact` | Blast radius and coupling analysis |

---

## Agent Philosophy

1. **Database = Ground Truth** - Query don't guess
2. **Precedents Over Invention** - Follow existing patterns
3. **Evidence Citations** - Every decision backed by query
4. **Autonomous Execution** - Don't ask, execute
5. **Zero Recommendation Without Facts** - Present findings, let user decide (refactor agent)
6. **Audit Everything** - Phase/task boundaries have verification

---

## Installation

Agents are deployed automatically by `aud setup-ai --target <project>`:

```
<project>/
  .auditor_venv/.theauditor_tools/agents/   # Full agent protocols
  .claude/commands/theauditor/               # Slash commands
  AGENTS.md                                  # Trigger block (injected)
  CLAUDE.md                                  # Trigger block (injected)
```

To reinstall: `aud setup-ai --target . --sync`

---

## Agent Files

| Agent | Lines | Purpose |
|-------|-------|---------|
| `planning.md` | ~460 | Transform requests into evidence-backed plans |
| `refactor.md` | ~380 | File refactoring with split detection, zero recommendations |
| `security.md` | ~340 | Security analysis matching detected frameworks |
| `dataflow.md` | ~390 | Source-to-sink tracing with sanitization gap detection |

Each agent is self-contained with its own Phase -> Task -> Job workflow.

---

**Version:** 1.0
**Last Updated:** 2025-11-23
**Maintainer:** TheAuditor Team
