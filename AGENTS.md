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

