---
name: TheAuditor: Dataflow
description: Source-to-sink dataflow tracing using TheAuditor.
category: TheAuditor
tags: [theauditor, dataflow, taint, trace]
---
<!-- THEAUDITOR:START -->
**Guardrails**
- Define explicit source AND sink BEFORE running taint analysis - ask if ambiguous.
- Run `aud blueprint` to identify framework-specific source/sink patterns (Flask: request.form, Express: req.body).
- NO file reading - use `aud taint` and `aud query` for actual dataflow.
- Refer to `.auditor_venv/.theauditor_tools/agents/dataflow.md` for the full protocol.

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
