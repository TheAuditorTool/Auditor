---
name: TheAuditor: Refactor
description: Code refactoring analysis using TheAuditor.
category: TheAuditor
tags: [theauditor, refactor, split, modularize, impact]
---

<!-- ANTIMATTER DIRECTIVE - NON-NEGOTIABLE -->
## YOU MUST READ THE FULL PROTOCOL BEFORE PROCEEDING

**STOP. DO NOT SKIP THIS.**

Before doing ANYTHING else, you MUST use the Read tool to load the complete refactor protocol:

```
Read: agents/refactor.md
```

This is NOT optional. This is NOT a suggestion. The summary below is INSUFFICIENT.

**WHY:** The summary tells you WHAT to do. The full protocol tells you HOW, with:
- Explicit failure modes (what NOT to do)
- Phase-by-phase breakdown with audit checkpoints
- The ZERO RECOMMENDATION policy details
- Chunked reading requirements for large files (>1950 lines)
- Split state detection and completion percentage calculation

**FAILURE MODE:** If you proceed without reading the full protocol, you WILL read files before querying the database, you WILL make recommendations instead of presenting facts, you WILL miss the deadcode check. This has been proven repeatedly.

**EXECUTE NOW:** `Read: agents/refactor.md` - then continue below.

---

<!-- THEAUDITOR:START - QUICK REFERENCE (read full protocol FIRST) -->
## Quick Reference (AFTER reading full protocol)

**Guardrails**
- Run `aud refactor` FIRST (bare-bones, no YAML) to see current migration state.
- Run `aud deadcode` to verify file is actively used (not deprecated).
- Run `aud blueprint --structure` to extract existing split patterns and naming conventions.
- Run `aud impact --file <target> --planning-context` to assess blast radius BEFORE refactoring.
- NO file reading until AFTER database structure analysis (Phase 3 Task 3.4 of protocol).
- Follow ZERO RECOMMENDATION policy - present facts only, let user decide.

**Steps**
1. Run `aud refactor` FIRST (no YAML needed) - see current migration/schema state.
2. Run `aud deadcode` (or `aud deadcode --path-filter 'dir/%'`) and grep for target.
3. Use `aud refactor` output to guide planning - YAML is only for advanced custom tracking.
4. Run `aud blueprint --structure` to extract naming conventions and split precedents.
5. Run `aud query --file <target> --list all` to get symbol list from database.
6. Run `aud impact --file <target> --planning-context` to assess blast radius.
7. Analyze clustering by prefix (_store_python*, _store_react*) and domain (auth*, user*).
8. Present findings as facts with "What do you want to do?" - NO recommendations.

**PATH FILTERING:**
- `--path-filter` uses SQL LIKE syntax (`%`) or glob patterns (`**`)
- Do NOT use `--project-path` for filtering (it changes database root)

**Reference**
- Deadcode confidence: [HIGH]/[MEDIUM]/[LOW] - 0 imports + [HIGH] = truly unused.
- Split states: <10% (easy revert), >90% (easy finish), 10-90% (ambiguous - ask user).
- Chunked reading: mandatory for >1950 lines, use 1500-line chunks.
- Impact thresholds: <10 files (LOW), 10-30 (MEDIUM), >30 (HIGH risk refactor).
- High coupling (>70) suggests extracting interface before splitting.
<!-- THEAUDITOR:END -->

---

## Full Protocol (YOU MUST HAVE READ agents/refactor.md BY NOW)

If you have NOT yet read `agents/refactor.md`, STOP and read it NOW.

**Failure Modes (ALL PROHIBITED):**
- "Let me read the file to understand..." -> WRONG, run `aud query --file X --list all` first
- "I recommend splitting into..." -> WRONG, present facts only, ask "What do you want to do?"
- "Based on typical refactoring patterns..." -> WRONG, run `aud blueprint --structure` for THIS project's patterns
- Skipping deadcode check -> WRONG, might be refactoring deprecated code

**Correct Behavior:**
- Agent runs `aud deadcode` FIRST before any analysis
- Agent queries database for structure BEFORE reading files
- Agent presents facts: "File has 45 functions, 3 clusters by prefix, 0 imports"
- Agent asks: "What do you want to do?" - NOT "I recommend..."

---

**FINAL CHECK:** Did you read `agents/refactor.md`? If not, do it now. If yes, proceed with Phase 1 (deadcode check).
