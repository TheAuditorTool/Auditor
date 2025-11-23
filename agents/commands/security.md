---
name: TheAuditor: Security
description: Security analysis and taint tracking using TheAuditor.
category: TheAuditor
tags: [theauditor, security, taint, vulnerability]
---
<!-- THEAUDITOR:START -->
**Guardrails**
- Run `aud blueprint` to detect frameworks FIRST - recommendations must match detected libraries (zod if zod, not joi).
- Run `aud taint-analyze` for actual dataflow paths - don't guess attack vectors.
- NO file reading - use `aud query` to find attack surface (innerHTML, query, execute).
- Refer to `.auditor_venv/.theauditor_tools/agents/security.md` for the full protocol.

**Steps**
1. Run `aud blueprint --structure | grep -A 10 "Framework Detection"` to identify backend, frontend, validation libraries.
2. Run `aud taint-analyze` to get actual source-to-sink dataflow paths.
3. Query attack surface: `aud query --symbol ".*innerHTML.*" --show-callers` (XSS), `aud query --symbol ".*query.*" --show-callers` (SQLi).
4. Query validation coverage: compare routes with validation vs total routes.
5. Generate security plan with framework-matched recommendations (use detected zod, not assumed joi).
6. Present with Evidence citations for every finding.

**Reference**
- Use `aud taint-analyze --help` for taint analysis options.
- Attack surfaces: XSS (innerHTML, dangerouslySetInnerHTML), SQLi (query, execute, raw), CSRF (POST without token).
- Always match recommendations to detected validation library version.
<!-- THEAUDITOR:END -->
