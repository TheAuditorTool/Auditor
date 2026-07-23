# TheAuditor

**Queryable code truth for AI agents and security teams.**

TheAuditor is a local, database-first code intelligence and polyglot SAST platform. It turns a codebase into deterministic, queryable facts so agents can ask focused questions about symbols, dependencies, impact, architecture, and security instead of repeatedly reading entire files.

## Release status

TheAuditor is in final commercial release preparation. Public availability is planned for early August 2026.

This repository is the official release and product-information channel. It does not currently contain distributable software.

## What it changes

- **Query-first context:** Index once, then answer code questions from structured facts.
- **Lower context cost:** Internal evaluations measured roughly 87% lower token use in selected query-first workflows compared with file-reading baselines. Results vary by task and query type, and independent field validation will begin after release.
- **Security and context from one analysis:** The same indexed truth supports code navigation, change-impact analysis, and polyglot security findings.
- **Built for agents:** Focused CLI and MCP interfaces return bounded, task-specific answers.
- **Local by design:** Source analysis and result storage stay on the operator's machine, with offline operation available.

## Follow the release

- Product: [theauditortool.com](https://theauditortool.com)
- Engineering journal: [blog.theauditortool.com](https://blog.theauditortool.com)
- Creator: [TheAuditorTool](https://github.com/TheAuditorTool)

## License

TheAuditor is proprietary software. Copyright (C) 2024-2026 TheAuditorTool. All rights reserved.

See [LICENSE](LICENSE) for terms. Commercial licensing and partnership inquiries: [TheAuditorTool](https://github.com/TheAuditorTool).
