---
name: TheAuditor: Dataflow
description: Source-to-sink dataflow tracing using TheAuditor.
category: TheAuditor
tags: [theauditor, dataflow, taint, trace]
---

<!-- ANTIMATTER DIRECTIVE - NON-NEGOTIABLE -->
## YOU MUST READ THE FULL PROTOCOL BEFORE PROCEEDING

**STOP. DO NOT SKIP THIS.**

Before doing ANYTHING else, you MUST use the Read tool to load the complete dataflow protocol:

```
Read: agents/dataflow.md
```

This is NOT optional. This is NOT a suggestion. The summary below is INSUFFICIENT.

**WHY:** The summary tells you WHAT to do. The full protocol tells you HOW, with:
- Explicit failure modes (what NOT to do)
- Phase-by-phase breakdown with audit checkpoints
- Framework-specific source/sink patterns (Flask vs Express vs FastAPI)
- Risk categorization methodology
- Sanitization gap analysis

**FAILURE MODE:** If you proceed without reading the full protocol, you WILL guess dataflow paths instead of running taint analysis, you WILL use wrong source patterns for the detected framework, you WILL miss sanitization gaps. This has been proven repeatedly.

**EXECUTE NOW:** `Read: agents/dataflow.md` - then continue below.

---

<!-- THEAUDITOR:START - QUICK REFERENCE (read full protocol FIRST) -->
## Quick Reference (AFTER reading full protocol)

**Guardrails**
- Define explicit source AND sink BEFORE running taint analysis - ask if ambiguous.
- Run `aud blueprint` to identify framework-specific source/sink patterns (Flask: request.form, Express: req.body).
- NO file reading - use `aud taint` and `aud query` for actual dataflow.

**Steps**
1. Clarify trace scope: "What source? (request.body, password, JWT)" and "What sink? (database, innerHTML, all)".
2. Run `aud blueprint --structure | grep -A 10 "Framework Detection"` to identify backend/frontend/database.
3. Construct and run: `aud taint --source "request.*" --sink ".*query.*"` (adjust patterns).
4. Parse paths and categorize by risk: HIGH (no validation), MEDIUM (validation, no sanitization), LOW (both).
5. Query call graph: `aud query --symbol <source> --show-callers` to build complete chains.
6. Identify sanitization gaps: X paths NO validation, Y paths validation but NO escaping.
7. Generate recommendations matching detected framework (Sequelize parameterization if Sequelize).

**Reference**
- Use `aud <command> --help` for quick syntax reference.
- Use `aud manual <topic>` for detailed documentation with examples:
  - `aud manual taint` - source/sink tracking and taint propagation
  - `aud manual callgraph` - function-level call relationships
  - `aud manual fce` - finding correlation for compound vulnerabilities
  - `aud manual cfg` - control flow graph for execution paths
- Framework sources: Flask (request.form/args/json), Express (req.body/query/params), FastAPI (request.form/json).
- Framework sinks: Sequelize (Model.findOne, db.query), SQLAlchemy (db.session.execute), Raw SQL (db.execute).
- Risk categories determine fix priority: HIGH first, then MEDIUM.
<!-- THEAUDITOR:END -->

---

## Full Protocol (YOU MUST HAVE READ agents/dataflow.md BY NOW)

If you have NOT yet read `agents/dataflow.md`, STOP and read it NOW.

**Failure Modes (ALL PROHIBITED):**
- "Based on typical dataflow patterns..." -> WRONG, run `aud taint` for THIS project's actual paths
- "Let me trace the data through the code..." -> WRONG, run `aud taint`, don't guess
- Starting analysis without clarifying source/sink -> WRONG, ask first if ambiguous
- Using Flask patterns for Express project -> WRONG, run `aud blueprint` first

**Correct Behavior:**
- Agent asks: "What source? What sink?" if not specified
- Agent runs `aud blueprint --structure` FIRST to detect framework
- Agent constructs taint command with framework-appropriate patterns
- Agent categorizes paths by risk with evidence citations

---

**FINAL CHECK:** Did you read `agents/dataflow.md`? If not, do it now. If yes, proceed with Phase 1 (scope clarification).
