# Proposal: Optimize Manual System Content for AI Workflows

## Why

`aud manual` is the handbook for AI assistants. When Claude Code or other AIs need to understand HOW to use TheAuditor - not just what commands exist, but actual workflows - they go to the manual.

Current state:
- 41 topics exist (good coverage)
- Content is human-centric, not AI-workflow-centric
- No step-by-step "how to use this system" guidance
- Missing integration with agent system
- Doesn't explain the DATABASE-FIRST philosophy
- Doesn't show command sequences and decision trees

**What AI assistants actually need:**
```
"I need to analyze a refactoring request"
→ "First, run aud full to index. Then create a custom refactor.yaml
   with your detection rules. Run aud refactor --profile path/to/rules.yaml.
   Combine with aud deadcode and aud blueprint for full picture.
   Ask user if they want a planning session..."
```

This is the GUIDE. The reference. The "how do I actually use this system" documentation.

## What Changes

### Content Rewrite (All 41 Topics)
- Rewrite each topic as a WORKFLOW guide, not just a concept explanation
- Include step-by-step command sequences
- Include decision trees (when to use this vs that)
- Cross-reference with --help content for consistency
- Cross-reference with agent system for runtime workflows

### Agent System Integration
- Reference `.auditor_venv/.theauditor_tools/agents/*.md` for workflows
- Ensure manual matches agent protocol descriptions
- Link manual topics to agent triggers

### New Topics (If Needed)
- Add any missing topics for complete coverage
- Ensure 1:1 parity with --help commands

## Scope

**In Scope:**
- 42 manual topics in `theauditor/commands/manual.py` and `manual_lib*.py`
- Cross-reference with 5 agent files
- Workflow-centric rewrite of all content

**Out of Scope:**
- Command --help text (separate ticket: optimize-cli-help-v2)
- Rich formatting (already complete)
- New features or functionality

## Execution Model

**6 Parallel AI Teams** - Each team handles one track independently:

| Track | Focus | Topics | Theme |
|-------|-------|--------|-------|
| 1 | Security Concepts | 6 topics | taint, patterns, severity, boundaries, rules, fce |
| 2 | Graph/Architecture | 7 topics | callgraph, dependencies, graph, cfg, architecture, blueprint, impact |
| 3 | Code Analysis | 7 topics | deadcode, refactor, workset, context, explain, query, lint |
| 4 | Infrastructure | 7 topics | pipeline, overview, database, env-vars, exit-codes, troubleshooting, setup |
| 5 | Integrations | 7 topics | docker, terraform, cdk, graphql, workflows, frameworks, docs |
| 6 | Advanced/ML | 7 topics | planning, session, ml, metadata, deps, tools, rust |

Each track is independent. No blocking dependencies between tracks.

## Key Principle: DATABASE-FIRST

Every workflow in the manual MUST emphasize:

1. **Run `aud full` first** - The database is the single source of truth
2. **Query the database** - Most analysis reads from .pf/repo_index.db
3. **Check agent protocols** - Reference the agent system for runtime workflows
4. **Combine commands** - Show how commands work together

Example workflow structure:
```
HOW TO: Detect incomplete refactorings

PREREQUISITES:
  aud full                        # Build the database

PREPARATION:
  1. Identify the refactoring scope (ask user or infer from context)
  2. Create refactor rules YAML (see examples below)

EXECUTION:
  aud refactor --profile rules.yaml  # Detect migration issues
  aud deadcode                        # Find orphaned code
  aud blueprint --structure           # See overall architecture

INTERPRETATION:
  - Combine refactor findings with deadcode results
  - Flag any inconsistencies for human review

NEXT STEPS:
  Ask user: "Would you like to create a remediation plan?"
  If yes: Use aud planning init to track fixes
```

## Verification Protocol

For EVERY topic touched, the AI team MUST:

1. **Read the agent files** - Understand runtime workflow protocols
2. **Run relevant commands** - Verify command sequences work
3. **Cross-reference --help** - Ensure consistency with help text
4. **Test workflows** - Actually execute the described steps
5. **Verify examples** - All code snippets must work

## Success Criteria

- [ ] All 41 topics rewritten as workflow guides
- [ ] All topics reference agent system where applicable
- [ ] All command sequences verified working
- [ ] All cross-references to --help are accurate
- [ ] DATABASE-FIRST philosophy emphasized throughout
- [ ] Each topic includes WHEN to use, not just WHAT it is

## Files Affected

**Primary (content changes):**
- `theauditor/commands/manual.py` (311 lines) - Topic registration, rendering logic
- `theauditor/commands/manual_lib01.py` (1479 lines) - Topics 1-21: taint through context
- `theauditor/commands/manual_lib02.py` (1856 lines) - Topics 22-42: boundaries through session

**Reference (read for verification, do not modify):**
- `.auditor_venv/.theauditor_tools/agents/AGENTS.md` (159 lines) - Command reference, philosophy
- `.auditor_venv/.theauditor_tools/agents/security.md` (343 lines) - Security workflow
- `.auditor_venv/.theauditor_tools/agents/refactor.md` (405 lines) - Refactor workflow
- `.auditor_venv/.theauditor_tools/agents/planning.md` (466 lines) - Planning workflow
- `.auditor_venv/.theauditor_tools/agents/dataflow.md` (391 lines) - Dataflow workflow

**Implementation Details:**
- See `design.md` for Topic Location Reference (file:line for all 41 topics)
- See `design.md` for Content Schema (EXPLANATIONS dict structure)
- See `design.md` for Rich Formatting Reference (supported syntax)
- See `design.md` for Verified Command Reference (tested commands)

**Constraints:**
- NO emojis in content (Windows CP1252 crash)
- NO `aud index` references (deprecated, use `aud full`)
- Content must render correctly with Rich formatter (manual.py:17-126)
