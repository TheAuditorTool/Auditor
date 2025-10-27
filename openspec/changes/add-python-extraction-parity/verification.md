# Verification: Python Extraction Parity

## Context
- Date: 2025-??-?? (Session 1)
- Agent: Codex (Lead Coder) on branch `pythonparity`
- Objective: Confirm assumptions behind `add-python-extraction-parity` proposal against live codebase before implementation.

## Hypotheses and Evidence

### H1: Python extractor ignores type annotations (parameters & returns).
- Evidence: `theauditor/ast_extractors/python_impl.py:46` iterates function defs but only appends `"args": [arg.arg for arg in node.args.args]`—no `annotation` or `returns` fields captured.
- Evidence: `theauditor/indexer/extractors/python.py:49-118` hydrates symbols from parser output but never constructs a `type_annotations` payload.
- Evidence: Grep check `grep -n "type_annotation" theauditor/indexer/extractors/python.py` returns no hits.
- Evidence: Schema + DB infrastructure already exist (`theauditor/indexer/schema.py:1026`, `theauditor/indexer/database.py:1002`), confirming absence is extractor gap, not storage.
- Verdict: ✅ Hypothesis confirmed.

### H2: Python routes already populate `api_endpoints`; proposal claim of "0 Python tables" for routes is outdated.
- Evidence: `_extract_routes_ast` in `theauditor/indexer/extractors/python.py:207-295` builds complete endpoint dicts, including `method`, `pattern`, `has_auth`, `controls`.
- Evidence: `_store_extracted_data` writes those dicts into `api_endpoints` and junction table in `theauditor/indexer/__init__.py:805-818`.
- Verdict: ❌ Proposal statement ("Python has no framework tables") is inaccurate for routing/auth decorators; needs adjustment to avoid duplicating endpoint tables.

### H3: No dedicated Python ORM/framework tables yet—gap remains valid.
- Evidence: `schema.py` registry lacks any `python_*` tables; only generic `orm_relationships`, `orm_queries` etc.
- Evidence: `theauditor/ast_extractors/python_impl.py` has no helpers for SQLAlchemy/Pydantic; file search `grep -n "SQLAlchemy" theauditor/ast_extractors/python_impl.py` returns nothing.
- Verdict: ✅ Proposal Phase 2 scope (add SQLAlchemy/Pydantic/FastAPI extraction) remains accurate.

### H4: Import resolution keys exist downstream but Python extractor never provides them.
- Evidence: `_store_extracted_data` expects optional `resolved_imports` (`theauditor/indexer/__init__.py:799`), but `PythonExtractor.extract` never sets the key.
- Evidence: Search `grep -n "resolved_imports" theauditor/indexer/extractors/python.py` returns nothing.
- Verdict: ✅ Proposal Phase 3 (populate resolved imports) remains valid.

### H5: Schema flush ordering must incorporate any new Python-specific tables.
- Evidence: `theauditor/indexer/database.py:226-332` defines ordered flush list; new tables require insertion to maintain FK correctness.
- Verdict: ✅ Implementation must update flush ordering alongside schema additions.

## Discrepancies vs Proposal
1. Proposal claims zero Python route support; live code already stores Flask/FastAPI routes via `api_endpoints`. Spec/tasks should clarify enhancements (e.g., richer metadata) instead of new tables.
2. Existing schema already has `type_annotations`; proposal must emphasize reuse rather than creation.

## Next Steps
- Update OpenSpec proposal/tasks to reflect verified reality (especially routing coverage).
- Confirmed via `aud index` (2025-10-27) that `.pf/repo_index.db` now stores 4,020 Python `type_annotations` rows with parameter/return metadata alongside existing JS/TS entries.
- Import resolution verified: `refs` rows now capture local module paths (e.g., `theauditor/js_semantic_parser.py`) after enabling `resolved_imports` mapping for Python files.
- Proceed to design Phase 1 plan leveraging existing schema/database contracts.
