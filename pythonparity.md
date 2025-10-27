# Python Parity Worklog

## Session 1 (Initiation)
- Environment: branch `pythonparity`, full write access, focus on Python extraction parity.
- Tool check: `aud --help` failed on PATH; succeeded via `.venv/Scripts/aud.exe --help` confirming CLI availability.
- Mandates: follow SOP v4.20, zero-fallback rules, respect layer separation (parser → extractor → indexer → taint/analysis).
- TODO foundation: deep-read `theauditor/indexer/schema.py` and `theauditor/indexer/database.py` as baseline; keep log of insights, blockers, and regressions here.

### Schema & Database Review Notes
- `schema.py` enumerates 50+ tables; `type_annotations` already exists with composite PK `(file,line,column,symbol_name)` and fields for generics and return types—Python work must populate via existing contract.
- `api_endpoints` plus `api_endpoint_controls` already normalize route metadata; Python extractor currently feeds these, so parity plan should avoid creating duplicate route tables.
- `orm_relationships` table is generic and ready for SQLAlchemy/Django relationships; `database.py:add_orm_relationship` enforces tuple `(file,line,source,target,type,foreign_key,cascade_delete,alias)`.
- Batch flush order in `database.py:flush_batch` shows where new tables should slot; adding Python-specific tables may require extending both schema registry and flush ordering.
- `type_annotations` insert uses `INSERT OR REPLACE`, so multiple passes can overwrite; Python extractor should match TypeScript writer signature `(file,line,column,symbol_name,symbol_kind,...)`.
- Memory-sensitive structures (assignments, function_call_args, variable_usage, orm queries) already normalized; any Python enhancements need to reuse these rather than new schemas.

### Verification Prep
- Authored `openspec/changes/add-python-extraction-parity/verification.md` capturing confirmed gaps (type hints missing, imports unresolved) and correcting outdated proposal claim about route coverage.

### Phase 1 (Type Annotation Parity) Outline
- **Helper utilities**: Add `_get_type_annotation` + `_analyze_annotation_flags` in `theauditor/ast_extractors/python_impl.py` to stringify AST annotations and derive flags (`is_generic`, `has_type_params`, `type_params`).
- **Function extraction**: Extend `extract_python_functions` to emit parameter metadata (`arg_annotations` keyed by argument name), capture return annotations, param defaults, `posonlyargs`/`kwonlyargs`/`vararg`/`kwarg`, and optional type comments.
- **Class/attribute extraction**: Introduce extractor for `ast.AnnAssign` (class + module scope) returning annotation records; ensure dataclass/TypedDict patterns handled.
- **Collector wiring**: In `theauditor/indexer/extractors/python.py`, assemble `type_annotations` payloads matching JS structure and forward to orchestrator; propagate `is_typed` flag to symbol entries when annotations present.
- **Database flow**: Reuse `database.py:add_type_annotation` path (no schema changes); update flush statistics if needed.
- **Testing strategy**: Create fixtures under `tests/fixtures/python/types/` covering functions, methods, generics, Optional/Union, type comments, class attrs. Add end-to-end indexer test validating DB rows and aggregator invariants.
- **Validation**: Run `aud index --offline` (or targeted harness) on fixture set to confirm new rows; spot-check `.pf/repo_index.db` with sqlite via Python snippet (per CLAUDE.md).
- **Spec hygiene**: Revisit Phase 2 spec expectations (`python_routes` table) before implementation to align with existing `api_endpoints` schema.

### Dev Log
- Implemented `_get_type_annotation`, `_analyze_annotation_flags`, and `_parse_function_type_comment` helpers in `theauditor/ast_extractors/python_impl.py` for consistent annotation stringification and generic detection.
- Enhanced `extract_python_functions` to capture parameter/return metadata, build per-parameter type annotation records, and flag typed functions.
- Added `extract_python_attribute_annotations` plus supporting `find_containing_class_python` helper to record `AnnAssign` annotations for class/module scopes.
- Updated `theauditor/indexer/extractors/python.py` to hydrate `type_annotations`, propagate function metadata into symbol entries, and reuse new attribute extraction.
- Added local deduplication for Python symbols to prevent duplicate insertions when multiple passes surface identical function/call/property entries.
- Sanity check: `python -m compileall theauditor` to ensure new modules compile cleanly under CPython 3.13.
- Spot check: manual invocation of `extract_python_functions` / `extract_python_attribute_annotations` confirms parameters, varargs, generics, and class attributes emit `type_annotations` entries.
- Captured decorator names on Python functions for future type-aware logic (e.g., `@overload`, `@dataclass` factory methods).
- Reality check: `aud index` (THEAUDITOR_TIMEOUT_SECONDS=600) succeeds post-changes; `.pf/repo_index.db` now reports 4,020 Python rows in `type_annotations` with parameter/return metadata.
- Full pipeline: `aud full --offline` (timeout 900s) completes; taint stage now loads 30,919 symbols with Python annotations contributing to the cache.
- Implemented Python import resolution (`resolved_imports`) to map modules to concrete `.py` files where available; verified via `refs` table showing localized paths (e.g., `theauditor/js_semantic_parser.py`).
- Phase 2 Planning (in progress): sketch SQLAlchemy extraction (models/fields/relationships), Pydantic validator harvesting, Flask blueprint registry, FastAPI dependency capture, and new schema tables (`python_orm_models`, `python_orm_fields`, `python_routes`, `python_blueprints`, `python_validators`) with matching `DatabaseManager` helpers and flush order integration.
