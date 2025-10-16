# Design: Update Indexer Language Parity

## Verification Summary (SOP v4.20)
- `theauditor/ast_parser.py:209-217` returns `{"type": "tree_sitter"}` whenever Tree-sitter is available, so Python callers never see the CPython payload that `_parse_python_cached` prepares later at `theauditor/ast_parser.py:222-231`.
- `theauditor/ast_parser.py:343-360` repeats the Tree-sitter-first branching in `parse_content`, and `parse_files_batch` delegates every Python path back to `parse_file`, compounding the mismatch.
- `theauditor/ast_extractors/__init__.py:255-268` routes Python CFG work to `treesitter_impl.extract_treesitter_cfg` when `tree["type"] == "tree_sitter"`, but that stub at `theauditor/ast_extractors/treesitter_impl.py:749-767` returns an empty list by design.
- `theauditor/indexer/extractors/javascript.py:1266-1309` forwards `file_info["path"]` as-is into each object literal record, and `_store_extracted_data` in `theauditor/indexer/__init__.py:949-961` queues those values without normalising.
- `theauditor/indexer/database.py:1751-1757` flushes the `object_literals` batch straight into SQLite; when a `Path` instance slips through (reproduced in `verification.md`), the cursor raises `sqlite3.ProgrammingError` and the batch is dropped.

## Goals
1. Guarantee every Python parsing entry point (`parse_file`, `parse_content`, `parse_files_batch`) emits `type="python_ast"` so the CFG extractor always receives `ast.AST` inputs.
2. Harden the JavaScript object literal pipeline so queued records serialise file paths deterministically and database flushes cannot lose data.
3. Add regression coverage that fails if Python CFG rows disappear or object literal inserts start raising `sqlite3.ProgrammingError`.
4. Synchronise the forthcoming spec delta with the earlier `update-python-ast-fallback` change to avoid conflicting parser guidance.

## Python AST Enforcement
- Introduce a dedicated `_build_python_ast_response(content_hash, content_str)` helper inside `theauditor/ast_parser.py` so all three callers reuse identical logic and metadata (`type`, `tree`, `language`, `content`).
- In `parse_file` (`theauditor/ast_parser.py:151-238`), short-circuit whenever `language == "python"`: decode once, call `_parse_python_cached`, and return the CPython structure even when `self.has_tree_sitter` is true. Tree-sitter should only remain as a fallback for non-Python languages.
- Mirror the same guard in `parse_content` (`theauditor/ast_parser.py:312-360`) so in-memory parsing obeys the CPython-first rule; retain semantic/Tree-sitter paths solely for JS/TS.
- Adjust `parse_files_batch` (`theauditor/ast_parser.py:380-452`) to skip the Tree-sitter detection for Python batches entirely. We will hydrate `results[...]` with the helper output rather than looping back into the old Tree-sitter branches.
- Update docstrings and inline comments to make the enforced precedence explicit for future contributors.

## JavaScript Object Literal Pipeline
- Normalise every file path through `os.fspath` (or `Path(...).as_posix()`) at the extractor boundary: when creating object literal records in `theauditor/indexer/extractors/javascript.py:1266-1309`, convert `file_info["path"]` to a plain POSIX string once.
- Add a defensive coercion inside `DatabaseManager.add_object_literal` (`theauditor/indexer/database.py:1336-1356`) so any residual `Path` instances are converted before batching.
- Extend `flush_batch` (`theauditor/indexer/database.py:1749-1758`) with targeted exception handling that surfaces the offending record count and aborts the commit instead of silently dropping rows; the handler will re-raise after logging to keep failure visible during verification.
- Backfill `verification.md` with instructions to capture both the successful insert counts and the absence of `sqlite3.ProgrammingError` after the fix.

## Testing Plan
- Unit: add parser tests under `tests/unit/ast_parser/test_python_mode.py` that force `has_tree_sitter = True` and assert `parse_file`/`parse_content` emit `type="python_ast"` plus non-empty CFG nodes via `extract_cfg`.
- Integration: extend the indexer regression suite (`tests/integration/indexer/test_python_cfg_parity.py`) to run the indexer against the `docs/fakeproj/project_anarchy` fixture with Tree-sitter enabled and confirm `cfg_blocks` gains Python entries.
- Database: introduce a persistence test (`tests/integration/indexer/test_object_literals_persistence.py`) that seeds a synthetic object literal extraction and verifies the resulting `object_literals` table row count and stored path.
- CLI smoke: reuse the existing `aud full` fixture run to ensure no new warnings are emitted during batch flushes.

## Risks & Mitigations
- **Tree-sitter-only deployments:** Environments that relied on Tree-sitter for Python AST shape diversity will now get consistent CPython trees; emphasise this in the spec delta and gate with tests to detect accidental reversion.
- **Performance:** CPython parsing is already used as fallback, but forcing it may surface latent performance regressions. Mitigate by capturing timing metrics during validation and documenting acceptable variance.
- **Batch coercion coverage:** Double conversion (extractor + database) might hide future regressions. Mitigate by asserting in tests that the stored `file` column matches the expected POSIX string exactly.

## Coordination Notes
- Review `openspec/changes/update-python-ast-fallback` once more after drafting the spec delta; if both changes overlap on parser directives, plan to consolidate the language guidance into a single modified requirement set before requesting approval.
