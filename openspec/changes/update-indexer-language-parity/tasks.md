## 0. Verification
- [ ] 0.1 Snapshot database evidence: confirm `cfg_blocks` has zero Python entries and `object_literals` table is empty in `docs/fakeproj/project_anarchy/.pf/repo_index.db`. Archive shell outputs in `verification.md`.

## 1. Implementation
- [ ] 1.1 Update `ASTParser.parse_file` to always return `type="python_ast"` for Python files, bypassing tree-sitter.
- [ ] 1.2 Mirror the Python safeguard in `parse_content` and `parse_files_batch` so every entry point delivers CPython AST payloads.
- [ ] 1.3 Repair `DatabaseManager` object literal batching so file paths are stored as strings and inserts succeed; add targeted tests validating persistence for a TypeScript fixture (e.g., `order.service.ts`).
- [ ] 1.4 Add regression coverage asserting Python CFG data exists when tree-sitter packages are installed (unit or integration level).
- [ ] 1.5 Coordinate with the existing `update-python-ast-fallback` change: merge or supersede to eliminate conflicting directives.

## 2. Validation
- [ ] 2.1 Run relevant extractor/indexer tests plus `aud index` on project_anarchy; document Python CFG and object literal counts post-change.
- [ ] 2.2 Perform SOP post-implementation audit: re-read modified files, confirm no syntax errors, and log results in `verification.md`.
