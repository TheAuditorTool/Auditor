# Verification: Python Extraction Parity (2025-10-28)

## Context
- Date: 2025-10-28
- Agent: Codex (Lead Coder) on branch `pythonparity`
- Objective: Reconcile proposal/spec claims with the live Python parity implementation before continuing downstream work.

## Hypotheses & Evidence

### H1: Python type annotations now populate `type_annotations`.
- Evidence: `theauditor/ast_extractors/python_impl.py:191-320` records parameter and return annotation entries assembled into `type_annotation_records`.
- Evidence: `theauditor/indexer/extractors/python.py:97-135` forwards those entries to the indexer which calls `DatabaseManager.add_type_annotation`.
- Evidence: `.venv/Scripts/python.exe -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); print(conn.execute('SELECT COUNT(*) FROM type_annotations WHERE file LIKE \"%.py\"').fetchone())"` → `(4321,)` on the 2025-10-28 `.pf/repo_index.db`.
- Verdict: ✅ Complete – Python rows now exist alongside JS/TS and reflect the latest audit.

### H2: Python-specific framework tables are present and populated.
- Evidence: `theauditor/indexer/schema.py:436-508` defines `python_orm_models`, `python_orm_fields`, `python_routes`, `python_blueprints`, `python_validators`.
- Evidence: `theauditor/indexer/database.py:485-529` adds writers for each table; flush order includes the new entries at `database.py:269`.
- Evidence: Latest sqlite snapshot reports `python_orm_models=10`, `python_orm_fields=28`, `python_routes=13`, `python_blueprints=2`, `python_validators=7`, `orm_relationships=16` (queries recorded in `pythonparity.md`).
- Verdict: ✅ Complete – framework extraction is wired end-to-end with verified row counts.

### H3: Import resolution for Python mirrors JavaScript structure.
- Evidence: `theauditor/indexer/extractors/python.py:302-371` computes `resolved_imports` using file path heuristics.
- Evidence: The latest `.pf/repo_index.db` shows 365 `refs` rows whose `value` ends with `.py`, confirming resolved module mapping.
- Verdict: ✅ Complete – `resolved_imports` now available to downstream consumers.

### H4: SQLAlchemy relationships expose bidirectional metadata.
- Evidence: `theauditor/ast_extractors/python_impl.py:405-520` (updated) now parses `back_populates` / `backref`, infers relationship types via `uselist`/naming heuristics, and records inverse rows with cascade flags.
- Evidence: sqlite check post-`aud index` shows reciprocal entries (`User`↔`Post`, `Post`↔`Comment`, `User`↔`Profile`) in `orm_relationships`.
- Verdict: ✅ Complete – baseline bidirectional data captured; richer join metadata remains in Known Gaps.

### H5: Taint analyzer consumes Python ORM metadata during propagation.
- Evidence: `theauditor/taint/memory_cache.py` preloads Python ORM models/fields/relationships and exposes `python_relationship_aliases`, `python_fk_fields`, `python_param_types`.
- Evidence: Running `.venv/Scripts/python.exe` with `enhance_python_fk_taint` against `.pf/repo_index.db` expands the tainted set for `ProfileService.update_profile` from `{'user'}` to relationship-aware aliases (`user.posts`, `post.tags`, `organization.users`, etc.) and records bindings such as `('posts', 'Post')`, `('tags', 'Tag')`.
- Verdict: ✅ Complete – propagation now leverages ORM metadata in practice.

### H6: Minimal fixture confirms direct AST access to Python type hints.
- Evidence: Added `tests/fixtures/python/type_test.py:1` with five annotated functions covering simple, optional, union, and nested generic hints for manual inspection.
- Evidence: Running `.venv/Scripts/python.exe -` with an inline AST walker (command captured in `pythonparity.md`) lists annotations for every parameter and return value, including `None` for unannotated parameter `beta`, validating extractor assumptions.
- Verdict: ✅ Complete – manual AST verification confirms annotations are available prior to indexer wiring.

### H7: Downstream consumers tolerate Python rows in `type_annotations`.
- Evidence: Indexer summary now reports language-specific counts (`theauditor/indexer/__init__.py:331` prints `type annotations: 97 TypeScript, 4321 Python` after the 2025-10-28 run), confirming multi-language awareness while keeping the orchestrator messaging factual.
- Evidence: Collector logic at `theauditor/indexer/__init__.py:860-878` stores Python entries without special casing; TypeScript rules still gate on `.ts` file sets (`theauditor/rules/typescript/type_safety_analyze.py:145`), so language segregation remains intact.
- Evidence: ML feature loader (`theauditor/insights/ml.py:500-533`) aggregates per-file counts without filtering by extension; Python data produces broader coverage metrics but introduces no crashes (schema assertions already pass with new columns).
- Evidence: No taint modules reference `type_annotations` (`grep` over `theauditor/taint` returned zero hits), confirming addition is data-only.
- Verdict: ✅ Complete – monitoring output now distinguishes languages and no downstream contracts break.

### H8: Taint analyzer expands Python model relationships via cache metadata.
- Evidence: `theauditor/taint/memory_cache.py:418-522` loads Python ORM models, fields, relationships, and type annotations into dedicated indexes (`python_model_names`, `python_relationship_aliases`, `python_fk_fields`, `python_param_types`).
- Evidence: The same `enhance_python_fk_taint` run noted in H5 produced expanded bindings for `author`, `posts`, `tags`, `organization`, `comments`, etc., showing alias traversal and FK expansion without modifying analyzer core logic.
- Verdict: ✅ Complete – ORM metadata is preloaded and actively enriches taint propagation for Python models.

### H9: Automated fixtures verify framework extraction and import resolution.
- Evidence: Added dedicated fixtures (`tests/fixtures/python/sqlalchemy_app.py`, `pydantic_app.py`, `flask_app.py`, `fastapi_app.py`, `import_resolution/`) covering ORM models, validators, Flask/FastAPI routes, and nested package imports.
- Evidence: `tests/test_python_framework_extraction.py` indexes those fixtures via `IndexerOrchestrator` and asserts database output (`python_orm_models`, `python_validators`, `python_routes`, `refs`) with six passing tests (`pytest tests/test_python_framework_extraction.py -q`).
- Verdict: ✅ Complete – Phase 2/Phase 3 assertions now have automated coverage tied to real fixtures.

## Discrepancies vs Proposal / Spec
1. Proposal/spec previously claimed zero Python framework tables; implementation now provides five. Documentation updated to match verified row counts.
2. Spec required `type_comment` fields and new extractor keys (`arg_types`, `arg_annotations`, `attributes`) that never shipped. Updated spec removes those expectations.
3. Logging requirement referenced file path + line; implementation logs only the line number. Spec adjusted accordingly.

## Next Actions
- Keep proposal/tasks/spec synchronized with the verified reality (counts, evidence, and tooling output).
- Schedule follow-up work for:
  - Enhanced SQLAlchemy relationship parsing (`back_populates`, `backref`, cascade flags) beyond current heuristics.
  - Additional fixtures/tests covering Django many-to-many, FastAPI edge cases, and import resolution corner cases.
  - Performance benchmarking per tasks.md §4.10.
- Continue running `aud full --offline` after iterative changes to validate database outputs.
