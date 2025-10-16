## Why
- Verification on 2025-10-16 confirmed the latest `aud full` run leaves Python CFG tables empty in `docs/fakeproj/project_anarchy/.pf/repo_index.db`; `_extract_python_cfg` in `theauditor/ast_extractors/python_impl.py` only emits blocks when the parser hands it CPython `ast.Module` trees.
- `ASTParser.parse_file/parse_files_batch` now exits early for Python once tree-sitter loads (`theauditor/ast_parser.py:213`), returning `type="tree_sitter"`. The downstream tree-sitter CFG hook is a stub that yields `[]`, so indexing silently loses all Python control-flow metrics.
- JavaScript extractor regression: manual extraction shows `object_literals` records for `full_stack_node/backend/src/services/order.service.ts`, but the database contains zero entries. Batches store `Path` objects instead of plain strings, causing `sqlite3.ProgrammingError` during flush; those exceptions are swallowed by final commits.
- Architect directed us to restore parity for supported languages without fallback heuristics and to document the plan via OpenSpec so the team can review before code changes begin.

## What Changes
- Force CPython AST output for every Python parser entry point (`parse_file`, `parse_content`, `parse_files_batch`), ensuring extractors always receive `type="python_ast"` payloads even when tree-sitter is installed.
- Harden the object literal storage pipeline so all properties discovered by `JavaScriptExtractor` persist to `object_literals` with correct path, value, and context metadata.
- Add automated regression coverage: Python CFG assertion with tree-sitter libraries present, and object literal persistence check against a known TypeScript fixture. Update existing Python AST fallback change (`update-python-ast-fallback`) to avoid overlap.
- Document these guarantees in the indexer spec so future parser work respects the enforced CPython path and verifies object literal persistence.

## Impact
- Restores Python CFG metrics, unlocking complexity analysis and downstream tooling that depend on `cfg_blocks`/`cfg_edges` data.
- Enables rules and analytics that rely on object literal metadata (dynamic dispatch, service map audits) to query the database as intended.
- Clarifies architectural expectations around Python parsing and JS object literal storage, preventing silent regressions in future parser refactors.

## Verification Alignment
- Pre-change evidence: `cfg_blocks` contains 0 Python rows; `object_literals` has 0 rows despite extractor output; inspections captured in this session’s verification notes and will be mirrored in `verification.md`.
- Post-change plan includes rerunning `aud index/full` on project_anarchy, rechecking database counts, and recording results per SOP v4.20.
