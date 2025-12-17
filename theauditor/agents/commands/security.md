---
name: TheAuditor: Security
description: Security analysis and taint tracking using TheAuditor.
category: TheAuditor
tags: [theauditor, security, taint, vulnerability]
---

<!-- ANTIMATTER DIRECTIVE - NON-NEGOTIABLE -->
## YOU MUST READ THE FULL PROTOCOL BEFORE PROCEEDING

**STOP. DO NOT SKIP THIS.**

Before doing ANYTHING else, you MUST use the Read tool to load the complete security protocol:

```
Read: agents/security.md
```

This is NOT optional. This is NOT a suggestion. The summary below is INSUFFICIENT.

**WHY:** The summary tells you WHAT to do. The full protocol tells you HOW, with:
- Explicit failure modes (what NOT to do)
- Phase-by-phase breakdown with audit checkpoints
- Framework-specific attack surface patterns
- Taint tracking methodology and risk categorization
- Evidence citation requirements

**FAILURE MODE:** If you proceed without reading the full protocol, you WILL guess attack vectors instead of running taint analysis, you WILL recommend joi when zod is detected, you WILL miss validating your findings against the database. This has been proven repeatedly.

**EXECUTE NOW:** `Read: agents/security.md` - then continue below.

---

<!-- THEAUDITOR:START - QUICK REFERENCE (read full protocol FIRST) -->
## Quick Reference (AFTER reading full protocol)

**Guardrails**
- Run `aud blueprint` to detect frameworks FIRST - recommendations must match detected libraries (zod if zod, not joi).
- Run `aud taint` for actual dataflow paths - don't guess attack vectors.
- NO file reading - use `aud query` to find attack surface (innerHTML, query, execute).

**Steps**
1. Run `aud blueprint --structure | grep -A 10 "Framework Detection"` to identify backend, frontend, validation libraries.
2. Run `aud taint` to get actual source-to-sink dataflow paths.
3. Query attack surface: `aud query --pattern "%innerHTML%" --content` (XSS), `aud query --pattern "%query%" --content` (SQLi).
4. Query validation coverage: compare routes with validation vs total routes.
5. Generate security plan with framework-matched recommendations (use detected zod, not assumed joi).
6. Present with Evidence citations for every finding.

**Reference**
- Use `aud <command> --help` for quick syntax reference.
- Use `aud manual <topic>` for detailed documentation with examples:
  - `aud manual taint` - source/sink tracking and taint propagation
  - `aud manual boundaries` - distance from entry points to controls
  - `aud manual patterns` - security vulnerability patterns
  - `aud manual rules` - security rules and code quality checks
- Attack surfaces: XSS (innerHTML, dangerouslySetInnerHTML), SQLi (query, execute, raw), CSRF (POST without token).
- Always match recommendations to detected validation library version.
<!-- THEAUDITOR:END -->

---

## Full Protocol (YOU MUST HAVE READ agents/security.md BY NOW)

If you have NOT yet read `agents/security.md`, STOP and read it NOW.

**Failure Modes (ALL PROHIBITED):**
- "Based on typical security patterns..." -> WRONG, run `aud taint` for THIS project's actual paths
- "I recommend using joi for validation..." -> WRONG, run `aud blueprint` - might be zod
- "Let me read the file to find vulnerabilities..." -> WRONG, run `aud query` and `aud taint`
- Presenting findings without evidence -> WRONG, cite database query for every finding

**Correct Behavior:**
- Agent runs `aud blueprint --structure` FIRST to detect frameworks
- Agent runs `aud taint` for actual dataflow paths
- Agent queries database for attack surface patterns
- Agent cites evidence: "Blueprint line 45: zod 3.22.0 detected" -> recommend zod, not joi

---

**FINAL CHECK:** Did you read `agents/security.md`? If not, do it now. If yes, proceed with Phase 1 (framework detection).
