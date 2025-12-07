---
name: TheAuditor: Planning
description: Database-first planning workflow using TheAuditor.
category: TheAuditor
tags: [theauditor, planning, architecture, impact]
---

<!-- ANTIMATTER DIRECTIVE - NON-NEGOTIABLE -->
## YOU MUST READ THE FULL PROTOCOL BEFORE PROCEEDING

**STOP. DO NOT SKIP THIS.**

Before doing ANYTHING else, you MUST use the Read tool to load the complete planning protocol:

```
Read: agents/planning.md
```

This is NOT optional. This is NOT a suggestion. The summary below is INSUFFICIENT.

**WHY:** The summary tells you WHAT to do. The full protocol tells you HOW, with:
- Explicit failure modes (what NOT to do)
- Phase-by-phase breakdown with audit checkpoints
- Concrete examples of correct vs incorrect behavior
- The full 6-phase workflow including post-implementation validation

**FAILURE MODE:** If you proceed without reading the full protocol, you WILL skip steps, you WILL read files instead of querying the database, you WILL forget to wait for approval. This has been proven repeatedly.

**EXECUTE NOW:** `Read: agents/planning.md` - then continue below.

---

<!-- THEAUDITOR:START - QUICK REFERENCE (read full protocol FIRST) -->
## Quick Reference (AFTER reading full protocol)

**Guardrails**
- Run `aud blueprint --structure` FIRST before any planning - this is mandatory.
- Run `aud impact --symbol <target> --planning-context` to assess blast radius BEFORE planning changes.
- NO file reading for code structure - use `aud query --file X --list functions` instead.
- Follow detected patterns from blueprint, don't invent new conventions.
- Every recommendation MUST cite a database query result.

**Steps**
1. Run `aud blueprint --structure` to load architectural context (naming conventions, frameworks, precedents).
2. Run `aud blueprint --monoliths` to identify large files requiring chunked analysis.
3. Run `aud impact --symbol <target> --planning-context` to assess change risk and coupling score.
4. Query specific patterns with `aud query --file <target> --list all` or `aud query --symbol <name> --show-callers`.
5. Synthesize plan anchored in database facts + impact metrics - cite every query used.
6. Present plan with Context, Impact Assessment, Recommendation, Evidence sections.
7. Wait for user approval before proceeding.

**Reference**
- Use `aud --help` and `aud <command> --help` for quick syntax reference.
- Use `aud manual <topic>` for detailed documentation with examples.
- Blueprint provides: naming conventions, architectural precedents, framework detection, refactor history.
- Query provides: symbol lists, caller/callee relationships, file structure.
- Impact provides: coupling score (0-100), dependency categories (prod/test/config), suggested phases.
- Coupling thresholds: <30 (LOW, safe), 30-70 (MEDIUM, careful), >70 (HIGH, extract interface first).
<!-- THEAUDITOR:END -->

---

## Full Protocol (YOU MUST HAVE READ agents/planning.md BY NOW)

If you have NOT yet read `agents/planning.md`, STOP and read it NOW.

**Failure Modes (ALL PROHIBITED):**
- "I'll read the file to see..." -> WRONG, run `aud query --file X --list functions`
- "Based on typical patterns..." -> WRONG, run `aud blueprint --structure` for THIS project's patterns
- "Let me check the file first..." -> WRONG, run `aud query`, not `read`
- "Would you like me to run blueprint?" -> WRONG, just run it autonomously

**Correct Behavior:**
- User: "Plan auth architecture" -> Agent: *immediately runs `aud blueprint --structure`*, *then runs queries*, *then synthesizes*
- Agent executes commands without asking, without explaining intent
- Agent cites every query result used in recommendations
- Agent follows phases sequentially, completing all tasks/jobs

---

**FINAL CHECK:** Did you read `agents/planning.md`? If not, do it now. If yes, proceed with Phase 1.
