---
name: TheAuditor: Refactor
description: Code refactoring analysis using TheAuditor.
category: TheAuditor
tags: [theauditor, refactor, split, modularize]
---
<!-- THEAUDITOR:START -->
**Guardrails**
- Run `aud deadcode` FIRST to verify file is actively used (not deprecated).
- Run `aud blueprint --structure` to extract existing split patterns and naming conventions.
- NO file reading until AFTER database structure analysis (Phase 3 Task 3.4 of protocol).
- Follow ZERO RECOMMENDATION policy - present facts only, let user decide.
- Refer to `.auditor_venv/.theauditor_tools/agents/refactor.md` for the full protocol.

**Steps**
1. Run `aud deadcode 2>&1 | grep <target>` to check if file is deprecated or active.
2. Run `aud blueprint --structure` to extract naming conventions (snake_case %) and split precedents (schemas/, commands/).
3. Run `aud structure --monoliths` to identify files >2150 lines requiring chunked reading.
4. Run `aud query --file <target> --list all` to get symbol list from database.
5. Analyze clustering by prefix (_store_python*, _store_react*) and domain (auth*, user*).
6. Check for partial splits: `ls <target>_*.py` - calculate completion % if found.
7. Present findings as facts with "What do you want to do?" - NO recommendations.

**Reference**
- Deadcode confidence: [HIGH]/[MEDIUM]/[LOW] - 0 imports + [HIGH] = truly unused.
- Split states: <10% (easy revert), >90% (easy finish), 10-90% (ambiguous - ask user).
- Chunked reading: mandatory for >2150 lines, use 1500-line chunks.
<!-- THEAUDITOR:END -->
