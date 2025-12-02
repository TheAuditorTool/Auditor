<!-- THEAUDITOR:START -->
# TheAuditor Agent System

For full documentation, see: @/.auditor_venv/.theauditor_tools/agents/AGENTS.md

**Quick Route:**
| Intent | Agent | Triggers |
|--------|-------|----------|
| Plan changes | planning.md | plan, architecture, design, structure |
| Refactor code | refactor.md | refactor, split, extract, modularize |
| Security audit | security.md | security, vulnerability, XSS, SQLi, CSRF |
| Trace dataflow | dataflow.md | dataflow, trace, source, sink |

**The One Rule:** Database first. Always run `aud blueprint --structure` before planning.

**Agent Locations:**
- Full protocols: .auditor_venv/.theauditor_tools/agents/*.md
- Slash commands: /theauditor:planning, /theauditor:security, /theauditor:refactor, /theauditor:dataflow

**Setup:** Run `aud setup-ai --target . --sync` to reinstall agents.

<!-- THEAUDITOR:END -->

