---
name: TheAuditor: Planning
description: Database-first planning workflow using TheAuditor.
category: TheAuditor
tags: [theauditor, planning, architecture, impact]
---
<!-- THEAUDITOR:START -->
**Guardrails**
- Run `aud blueprint --structure` FIRST before any planning - this is mandatory.
- Run `aud impact --symbol <target> --planning-context` to assess blast radius BEFORE planning changes.
- NO file reading for code structure - use `aud query --file X --list functions` instead.
- Follow detected patterns from blueprint, don't invent new conventions.
- Every recommendation MUST cite a database query result.
- Refer to `.auditor_venv/.theauditor_tools/agents/planning.md` for the full protocol.

**Steps**
1. Run `aud blueprint --structure` to load architectural context (naming conventions, frameworks, precedents).
2. Run `aud structure --monoliths` to identify large files requiring chunked analysis.
3. Run `aud impact --symbol <target> --planning-context` to assess change risk and coupling score.
4. Query specific patterns with `aud query --file <target> --list all` or `aud query --symbol <name> --show-callers`.
5. Synthesize plan anchored in database facts + impact metrics - cite every query used.
6. Present plan with Context, Impact Assessment, Recommendation, Evidence sections.
7. Wait for user approval before proceeding.

**Reference**
- Use `aud --help` and `aud blueprint --help` for command syntax.
- Blueprint provides: naming conventions, architectural precedents, framework detection, refactor history.
- Query provides: symbol lists, caller/callee relationships, file structure.
- Impact provides: coupling score (0-100), dependency categories (prod/test/config), suggested phases.
- Coupling thresholds: <30 (LOW, safe), 30-70 (MEDIUM, careful), >70 (HIGH, extract interface first).
<!-- THEAUDITOR:END -->
