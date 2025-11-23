<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

<!-- THEAUDITOR:START -->
# TheAuditor Planning Agent System

When user mentions planning, refactoring, security, or dataflow keywords, load specialized agents:

**Agent Triggers:**
- "refactor", "split", "extract", "merge", "modularize" => @/.theauditor_tools/agents/refactor.md
- "security", "vulnerability", "XSS", "SQL injection", "CSRF", "taint", "sanitize" => @/.theauditor_tools/agents/security.md
- "plan", "architecture", "design", "organize", "structure", "approach" => @/.theauditor_tools/agents/planning.md
- "dataflow", "trace", "track", "flow", "source", "sink", "propagate" => @/.theauditor_tools/agents/dataflow.md

**Agent Purpose:**
These agents enforce query-driven workflows using TheAuditor's database:
- NO file reading - use `aud query`, `aud blueprint`, `aud context`
- NO guessing patterns - follow detected precedents from blueprint
- NO assuming conventions - match detected naming/frameworks
- MANDATORY sequence: blueprint => query => synthesis
- ALL recommendations cite database query results

**Agent Files Location:**
Agents are copied to .auditor_venv/.theauditor_tools/agents/ during venv setup.
Run `aud init` to install the venv if agents are missing.

<!-- THEAUDITOR:END -->

