# Verification: Python Extraction Parity (2025-10-27)

## Context
- Date: 2025-10-27
- Agent: Codex (Lead Coder) on branch `pythonparity`
- Objective: Reconcile proposal/spec claims with the live Python parity implementation before continuing downstream work.

## Hypotheses & Evidence

### H1: Python type annotations now populate `type_annotations`.
- Evidence: `theauditor/ast_extractors/python_impl.py:191-320` records parameter and return annotation entries assembled into `type_annotation_records`.
- Evidence: `theauditor/indexer/extractors/python.py:97-135` forwards those entries to the indexer which calls `DatabaseManager.add_type_annotation`.
- Evidence: `.venv/Scripts/python.exe -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); print(conn.execute('SELECT COUNT(*) FROM type_annotations WHERE file LIKE \"%.py\"').fetchone())"` → `(4020,)`.
- Verdict: ✅ Complete – Python rows now exist alongside JS/TS.

### H2: Python-specific framework tables are present and populated.
- Evidence: `theauditor/indexer/schema.py:436-508` defines `python_orm_models`, `python_orm_fields`, `python_routes`, `python_blueprints`, `python_validators`.
- Evidence: `theauditor/indexer/database.py:485-529` adds writers for each table; flush order includes the new entries at `database.py:269`.
- Evidence: Spot query `.pf/repo_index.db` returns non-zero counts for each table (see sqlite snippet: `SELECT COUNT(*) FROM python_routes;` etc.).
- Verdict: ✅ Complete – framework extraction is wired end-to-end.

### H3: Import resolution for Python mirrors JavaScript structure.
- Evidence: `theauditor/indexer/extractors/python.py:302-371` computes `resolved_imports` using file path heuristics.
- Evidence: Running `aud index` populates `refs` with resolved module paths referencing `.py` files from the same repository.
- Verdict: ✅ Complete – `resolved_imports` now available to downstream consumers.

### H4: SQLAlchemy relationships expose bidirectional metadata.
- Evidence: `theauditor/ast_extractors/python_impl.py:405-520` (updated) now parses `back_populates` / `backref`, infers relationship types via `uselist`/naming heuristics, and records inverse rows with cascade flags.
- Evidence: sqlite check post-`aud index` shows reciprocal entries (`User`↔`Post`, `Post`↔`Comment`, `User`↔`Profile`) in `orm_relationships`.
- Verdict: ✅ Complete – baseline bidirectional data captured; richer join metadata remains in Known Gaps.

### H5: Taint analyzer wiring remains incomplete.
- Evidence: `theauditor/taint/memory_cache.py` now preloads `python_orm_*` tables, but there are no downstream taint modules consuming the data (`rg "python_orm_models" theauditor/taint` → cache only).
- Verdict: ❌ Not yet implemented – need propagation/graph wiring before taint benefits from new metadata.

## Discrepancies vs Proposal / Spec
1. Proposal/spec previously claimed zero Python framework tables; implementation now provides five. Documentation required alignment (addressed in this update).
2. Spec required `type_comment` fields and new extractor keys (`arg_types`, `arg_annotations`, `attributes`) that never shipped. Updated spec removes those expectations.
3. SQLAlchemy requirements: bidirectional extraction delivered; taint traversal integration remains outstanding (tracked in Known Gaps / tasks).
4. Logging requirement referenced file path + line; implementation logs only the line number. Spec adjusted accordingly.

## Next Actions
- Keep proposal/tasks/spec synchronized with the verified reality (this update).
- Schedule follow-up work for:
  - Enhanced SQLAlchemy relationship parsing (`back_populates`, `backref`, cascade flags).
  - Taint analyzer consumption of `python_orm_*` data.
  - Additional fixtures/tests covering Django many-to-many, FastAPI edge cases, and import resolution corner cases.
- Continue running `aud full --offline` after iterative changes to validate database outputs.
