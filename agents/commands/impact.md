---
name: TheAuditor: Impact
description: Blast radius and coupling analysis for code changes using TheAuditor.
category: TheAuditor
tags: [theauditor, impact, blast-radius, coupling, risk, planning]
---

<!-- ANTIMATTER DIRECTIVE - NON-NEGOTIABLE -->
## YOU MUST READ THE FULL PROTOCOL BEFORE PROCEEDING

**STOP. DO NOT SKIP THIS.**

Before doing ANYTHING else, you MUST use the Read tool to load the complete planning protocol (impact is part of planning):

```
Read: agents/planning.md
```

This is NOT optional. This is NOT a suggestion. The summary below is INSUFFICIENT.

**WHY:** Impact analysis is Phase 2.6 of the planning protocol. The full protocol tells you:
- How impact integrates with blueprint and queries
- Coupling score interpretation and thresholds
- When to extract interface vs proceed directly
- How to structure phased rollouts based on risk

**FAILURE MODE:** If you proceed without reading the full protocol, you WILL miss integration with other planning phases, you WILL misinterpret coupling scores, you WILL skip the prerequisite blueprint analysis. This has been proven repeatedly.

**EXECUTE NOW:** `Read: agents/planning.md` - then continue below.

---

<!-- THEAUDITOR:START - QUICK REFERENCE (read full protocol FIRST) -->
## Quick Reference (AFTER reading full protocol)

**Guardrails**
- Run impact analysis BEFORE planning any change - this is mandatory.
- Use `--symbol` for single target or `--file` for whole file analysis.
- Use `--planning-context` for structured output with coupling score and phases.
- Coupling >70 = HIGH risk, requires interface extraction before refactoring.

**Steps**
1. Identify target: symbol name or file path from user request.
2. Run `aud impact --symbol <name> --planning-context` or `aud impact --file <path> --planning-context`.
3. Review coupling score: <30 (LOW), 30-70 (MEDIUM), >70 (HIGH).
4. Review dependency categories: production, tests, config, external.
5. Note suggested phases from impact output.
6. If HIGH coupling: recommend extracting interface before changes.
7. Present impact summary with risk assessment.

**Reference**
- Use `aud impact --help` for command syntax.
- Coupling thresholds: <30 (safe), 30-70 (careful), >70 (extract interface first).
- Risk thresholds: <10 files (LOW), 10-30 (MEDIUM), >30 (HIGH).
- Dependency categories: production (high priority), tests (update mocks), config (low risk), external (no action).
- Pattern matching: Use `--symbol "prefix*"` for wildcard searches.
<!-- THEAUDITOR:END -->

---

## Full Protocol (YOU MUST HAVE READ agents/planning.md BY NOW)

If you have NOT yet read `agents/planning.md`, STOP and read it NOW.

**Failure Modes (ALL PROHIBITED):**
- Running impact without blueprint first -> WRONG, Phase 1 comes before Phase 2.6
- Ignoring coupling score thresholds -> WRONG, >70 requires interface extraction
- Skipping dependency categorization -> WRONG, prod vs test vs config matters
- Not using --planning-context -> WRONG, missing structured output for planning

**Correct Behavior:**
- Agent runs `aud blueprint --structure` BEFORE impact analysis
- Agent uses `--planning-context` flag for structured output
- Agent interprets coupling: <30 (proceed), 30-70 (careful), >70 (extract interface)
- Agent categorizes dependencies and notes suggested phases

---

**FINAL CHECK:** Did you read `agents/planning.md`? If not, do it now. If yes, run the impact analysis.
