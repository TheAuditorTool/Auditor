## Verification Summary (2025-10-16)
- Python CFG data absent: `SELECT COUNT(*) FROM cfg_blocks WHERE file LIKE "api/%"` returned 0.
- Tree-sitter stub is active: `ASTParser.parse_file` produced `type="tree_sitter"` while `_extract_python_cfg` requires CPython AST.
- JavaScript extractor emits object literals: manual invocation captured 7 records for `order.service.ts`, but they are dropped before reaching SQLite.
- Storage failure reproduced in isolation: inserting a `Path` into the batch raises `sqlite3.ProgrammingError`, mirroring the production symptom.

Discrepancies vs expectations
- README for Project Anarchy assumes Python complexity metrics and JS object literal mappings exist; current pipeline violates those assumptions.
- No existing OpenSpec change addresses both regressions together.

Next Steps
- Execute tasks in `tasks.md` once proposal is approved.
- Post-change rerun `aud full` on project_anarchy and capture updated counts.
