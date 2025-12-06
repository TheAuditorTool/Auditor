---
name: TheAuditor: Impact
description: Blast radius and coupling analysis for code changes using TheAuditor.
category: TheAuditor
tags: [theauditor, impact, blast-radius, coupling, risk, planning]
---
<!-- THEAUDITOR:START -->
**Guardrails**
- Run impact analysis BEFORE planning any change - this is mandatory.
- Use `--symbol` for single target or `--file` for whole file analysis.
- Use `--planning-context` for structured output with coupling score and phases.
- Coupling >70 = HIGH risk, requires interface extraction before refactoring.
- Refer to `.auditor_venv/.theauditor_tools/agents/planning.md` for integration.

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
