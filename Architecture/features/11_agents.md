# TheAuditor Agents System & Orchestration

## Overview

TheAuditor's AGENTS system is a **database-first, AI-friendly framework** that enables autonomous code analysis through structured workflows. It transforms TheAuditor's analysis engine into specialized agents that AI assistants can invoke without hallucination.

---

## What The Agent System Provides

1. **Autonomous Execution Protocol** - AI runs analysis without asking permission
2. **Database-First Methodology** - All analysis from indexed database, never from assumptions
3. **Phase-Task-Job Hierarchy** - Structured workflows with verification
4. **Evidence Citations** - Every recommendation backed by query results
5. **Anti-Hallucination Safeguards** - Explicit rules preventing guessing

---

## Slash Commands

**Note:** Slash commands are protocol prompts for AI agents (Claude, Cursor, etc.) to invoke TheAuditor tools. These are NOT terminal commands. Use `aud <command>` in your terminal for actual CLI operations.

### TheAuditor Integration Commands

| Command | Purpose |
|---------|---------|
| `/theauditor:planning` | Database-first planning with impact analysis |
| `/theauditor:refactor` | Code refactoring analysis |
| `/theauditor:security` | Security analysis and taint tracking |
| `/theauditor:dataflow` | Source-to-sink dataflow tracing |
| `/theauditor:impact` | Blast radius and coupling analysis |

---

## Agent Routing

Agents are automatically routed based on keywords:

| Agent | Keywords |
|-------|----------|
| **Planning** | plan, architecture, design, structure |
| **Refactor** | refactor, split, extract, merge |
| **Security** | vulnerability, XSS, injection, taint |
| **Dataflow** | trace, flow, source, sink |

---

## Database-First Principle

Agents NEVER read files directly. Instead:

```bash
# WRONG: Reading files
with open("file.py") as f:
    content = f.read()

# RIGHT: Query database
aud query --file theauditor/module.py --list functions
aud query --symbol function_name --show-callers
aud blueprint --structure
```

---

## Commands Used by Agents

| Purpose | Command |
|---------|---------|
| Get comprehensive context | `aud explain <target>` |
| Extract architecture | `aud blueprint --structure` |
| Get dependencies | `aud blueprint --deps` |
| List functions in file | `aud query --file X --list functions` |
| Find callers | `aud query --symbol X --show-callers` |
| Analyze taint | `aud taint-analyze` |
| Find dead code | `aud deadcode` |
| Assess impact | `aud impact --symbol X --planning-context` |

---

## Agent Execution Pattern

```
User Request
    ↓
Route to Agent (based on keywords)
    ↓
PHASE 1: Database Context
  - aud blueprint --structure
  - aud blueprint --monoliths
    ↓
PHASE 2: Targeted Queries
  - aud query --file/symbol X
  - aud deadcode / aud taint
    ↓
PHASE 3: Manual Analysis (if needed)
  - Read files only if >2150 lines
    ↓
PHASE 4: Evidence-Backed Output
  - Present findings with citations
  - Wait for human decision
```

---

## Orchestrators

### Rules Orchestrator (`theauditor/rules/orchestrator.py`)
- Dynamic rule discovery and execution
- Analyzes rule signatures
- Tracks fidelity failures

### Indexer Orchestrator (`theauditor/indexer/orchestrator.py`)
- Coordinates indexing pipeline
- Manages database writes
- Handles multiple language extractors

---

## Required AI Agent Behavior

### MANDATORY
1. Run `aud blueprint --structure` before ANY planning
2. Use `aud query` instead of reading files
3. Execute commands autonomously
4. Cite every query result
5. Follow Phase → Task → Job hierarchy

### FORBIDDEN
1. ❌ "Let me read the file..."
2. ❌ "Based on typical patterns..."
3. ❌ "I recommend X..." (without evidence)
4. ❌ "Would you like me to...?"
5. ❌ Making recommendations without facts

---

## Efficiency Gains

| Traditional AI | Agent-Based AI |
|----------------|----------------|
| Read 2000 lines to find functions | `aud query --file X --list functions` |
| Grep codebase for library | `aud blueprint` (instant) |
| Assume callers exist | `aud query --symbol X --show-callers` (exact) |
| Hypothesize conventions | `aud blueprint` (fact-based) |

**Result**:
- 70-80% fewer context tokens
- Zero hallucination
- Faster analysis
- Evidence citations
