# Python Parity Worklog

## Autonomous Workflow (Always Follow)
1. **Re-align** – Read `teamsop.md`, `CLAUDE.md`, and OpenSpec verification before touching code.
2. **Plan from OpenSpec** – Pick the next unchecked item in `openspec/changes/add-python-extraction-parity/tasks.md` and update `verification.md` with current evidence.
3. **Change by layer** – AST (`theauditor/ast_extractors/python_impl.py`) → extractor (`theauditor/indexer/extractors/python.py`) → schema/database (`schema.py`, `database.py`) → consumers (`theauditor/taint/*`, rules, etc.).
4. **Run everything locally** – `python -m compileall theauditor`, `aud index`, `aud full --offline` (set `THEAUDITOR_TIMEOUT_SECONDS=900`). Validate `.pf/repo_index.db` with sqlite snippets; never assume.
5. **Document immediately** – Sync OpenSpec proposal/design/spec/tasks/verification and this log in the same change.
6. **Commit cleanly** – Descriptive commit titles, no co-author lines, small logical diffs.

## Quick Onboarding / Environment
- Branch: `pythonparity` (full write access; isolated working branch).
- Tooling: use `aud` CLI (`aud --help`). If PATH lookup fails, call `.venv/Scripts/aud.exe --help`.
- Prime directive: follow `teamsop.md` (verification first, zero fallbacks per `CLAUDE.md`). Respect layer boundaries: AST extractors → indexer → taint/analysis.
- Long-running commands: bump timeout via `THEAUDITOR_TIMEOUT_SECONDS=900` when running `aud full --offline`.
- Database inspection: use Python’s sqlite3 (see `CLAUDE.md` guidance) against `.pf/repo_index.db`.
- OpenSpec workflow: see `openspec/AGENTS.md`. Run `openspec validate add-python-extraction-parity --strict` after spec edits.

## Current Status (2025-10-28)
- ✅ Python type hints (function parameters/returns and class/module `AnnAssign`) populate `type_annotations` with **4,321** Python rows in the latest `.pf/repo_index.db` (`SELECT COUNT(*) FROM type_annotations WHERE file LIKE '%.py'`).
- ✅ Framework metadata flows into new tables: `python_orm_models` (**10 rows**), `python_orm_fields` (**28 rows**), `python_routes` (**13 rows**), `python_blueprints` (**2 rows**), `python_validators` (**7 rows**), plus bidirectional entries in `orm_relationships` (**16 rows**) sourced from SQLAlchemy/Django extraction.
- ✅ Import resolution populates `resolved_imports`, evidenced by **365** refs pointing at `*.py` modules (`SELECT COUNT(*) FROM refs WHERE value LIKE '%.py'`).
- ✅ SQLAlchemy relationship extraction captures `back_populates`, `backref`, cascade hints, and emits inverse rows; verified via sqlite queries (e.g., `SELECT source_model, target_model, relationship_type FROM orm_relationships`).
- ✅ Memory cache preload now ingests Python ORM metadata and extends taint propagation; running `enhance_python_fk_taint` against `.pf/repo_index.db` expands `user` bindings to include related models (`vars` include `posts`, `post.tags`, `organization.users`, etc.).
- ✅ Documentation set (`proposal.md`, `design.md`, `spec.md`, `tasks.md`, `verification.md`) synchronized with code evidence after the 2025-10-28 audit.
- 🔄 Outstanding: expand automated taint regression coverage, broaden FastAPI/Django fixtures past current samples, collect performance benchmarks, and add file-path context to annotation warning logs.

## What’s Working
- `aud full --offline` completed at 2025-10-28 14:52 UTC (see `.pf/history/full/20251028_145204/`); pipeline log reports `type annotations: 97 TypeScript, 4321 Python`.
- `resolved_imports` entries appear in `refs` (365 rows targeting `.py` modules) enabling cross-file lookups.
- Framework tables contain verified data for SQLAlchemy models (with inverse relationships), Pydantic validators, Flask/FastAPI routes, and blueprints; counts match sqlite queries listed above.
- `enhance_python_fk_taint` confirms runtime access to ORM metadata, expanding tainted variable sets to relationship aliases (`user.posts`, `post.tags`, etc.) and maintaining binding maps (`('tags', 'Tag')`, `('posts', 'Post')`).
- Targeted regression suite passes (`.venv/Scripts/python.exe -m pytest tests/test_python_framework_extraction.py -q`).
- OpenSpec validation passes (`openspec validate add-python-extraction-parity --strict`).

## Known Gaps / Next Steps
- `openspec/.../tasks.md:904` – wire taint analyzer to consume `python_orm_models`, `python_orm_fields`, and `orm_relationships` during propagation.
- `openspec/.../tasks.md:812`+ – author focused fixtures (`sqlalchemy_app.py`, `pydantic_app.py`, etc.) and tests (`tests/test_python_framework_extraction.py`).
- `openspec/.../tasks.md:35` – minimal fixture for early type-hint verification still outstanding if needed for regression harness.
- Performance benchmarking tasks (tasks.md:375) remain TODO; collect data once framework enhancements settle.
- Update CLAUDE.md once broader framework coverage/limitations are locked in (tasks.md:866).

## Realworld Fixture (Do Not Remove)
- **Location**: `tests/fixtures/python/realworld_project/` – synthetic app covering SQLAlchemy models, FastAPI + Flask routes, Pydantic validators, config imports, and service/ repository layers. The code never runs; it exists solely for extraction parity.
- **Database verification**:
  * `SELECT COUNT(*) FROM type_annotations WHERE file LIKE 'realworld_project/%'` → confirms annotation coverage from the fixture (expect double-digit rows).
  * `SELECT model_name FROM python_orm_models WHERE file LIKE 'realworld_project/%'` → includes `Organization`, `User`, `Profile`, `AuditLog`.
  * `SELECT framework, method, pattern, dependencies FROM python_routes WHERE file LIKE 'realworld_project/%'` → FastAPI routes expose dependencies `['get_repository', 'get_email_service']`; Flask blueprint surfaces under `blueprint='admin'`.
  * `SELECT model_name, validator_method, validator_type FROM python_validators WHERE file LIKE 'realworld_project/%'` → `AccountPayload.timezone_supported` (field) and `AccountPayload.title_matches_role` (root).
- **Regression harness**: `pytest tests/test_python_realworld_project.py -q` copies the fixture into a temp project, runs `IndexerOrchestrator`, and asserts the queries above plus resolved-import coverage. Keep this test alongside the fixture whenever parity logic changes.
- **Dogfood usage**: When running `aud full --offline`, the fixture piggy-backs on the repo and guarantees that new extraction features (annotations, ORM relationships, dependency parsing) immediately materialize in `.pf/repo_index.db`. Never delete or rename the fixture directories; append new scenarios under the same package so historical counts remain comparable.

## Session Timeline

### Session 1 (Initiation)
- Environment setup, SOP refresh, baseline schema/database review.
- Implemented:
  - `_get_type_annotation`, `_analyze_annotation_flags`, `_parse_function_type_comment` (type serialization & generics).
  - Function/class extraction updates to capture parameter/return metadata, decorator tags, and class attribute annotations.
  - `extract_python_attribute_annotations` and supporting helpers (`find_containing_class_python`).
  - Indexer wiring: populate `type_annotations`, propagate typed symbol metadata, ensure deduping.
  - Added Python import resolution (`resolved_imports`) with heuristic filesystem mapping.
  - Created new schema tables + database writers for ORM/routes/validators; flush order adjusted accordingly.
- Verification:
  - `python -m compileall theauditor` sanity check.
  - `aud index` (timeout 600) and full pipeline run (timeout 900) succeeded; taint stage saw increased symbol counts.

### Session 2 (Docs & Verification Sync)
- Updated OpenSpec artifacts (`proposal.md`, `design.md`, `spec.md`, `tasks.md`) to match implemented behavior and highlight remaining work.
- Added current-state verification log (`openspec/.../verification.md`) documenting evidence for type annotations, framework tables, import resolution, and gaps (back_populates, taint integration).
- Logged changes in `pythonparity.md` to serve as changelog + onboarding.

### Session 3 (SQLAlchemy Inverses & Taint Cache Integration)
- Extraction:
  - Added helper utilities for SQLAlchemy relationship analysis (`_infer_relationship_type`, `_inverse_relationship_type`, cascade/backref helpers).
  - `extract_sqlalchemy_definitions` now parses `back_populates`/`backref`, infers `hasOne/hasMany/belongsTo`, flags cascade semantics, and emits inverse relationship records to `orm_relationships`.
  - Updated parity fixture (`tests/fixtures/python/parity_sample.py`) with `Comment`, `Profile`, cascade/backref, and `uselist=False` scenarios.
- Runtime plumbing:
  - `MemoryCache` loads `python_orm_models`, `python_orm_fields`, `orm_relationships`, `python_routes`, `python_blueprints`, and `python_validators`, exposing file/model indexes for taint consumers.
    - `aud full --offline` rerun (timeout 900s) succeeded; newest run (2025-10-28 14:52 UTC) shows memory preload counts of 10 models, 28 fields, 16 relationships, 13 routes, 2 blueprints, 7 validators.
    - Data checks:
      - Verified `.pf/repo_index.db` contains bidirectional relationships and cascade flags via sqlite (`SELECT source_model, target_model, relationship_type, cascade_delete FROM orm_relationships`).
      - `orm_relationships` now records inverse rows (`Post`↔`Comment`, `User`↔`Profile`, etc.) with cascade markers.
    - Open work: keep tasks `24.3` (taint traversal graph) and expanded fixture/test coverage outstanding for next iteration.

### Session 4 (Verification Continuation)
- Created minimal fixture `tests/fixtures/python/type_test.py` capturing positional, optional, union, and nested generic annotations for manual AST inspection.
    - Confirmed annotations via inline walker:  
  ```bash
  cat <<'PY' | .venv/Scripts/python.exe -
  import ast, json, pathlib

  path = pathlib.Path('tests/fixtures/python/type_test.py')
  module = ast.parse(path.read_text())
  records = []
  for node in module.body:
      if isinstance(node, ast.FunctionDef):
          params = []
          for arg in list(node.args.posonlyargs) + list(node.args.args):
              params.append(
                  {
                      'name': arg.arg,
                      'annotation': ast.unparse(arg.annotation) if arg.annotation else None,
                  }
              )
          if node.args.vararg:
              params.append(
                  {
                      'name': node.args.vararg.arg,
                      'annotation': ast.unparse(node.args.vararg.annotation) if node.args.vararg.annotation else None,
                  }
              )
          kwonly = [
              {
                  'name': arg.arg,
                  'annotation': ast.unparse(arg.annotation) if arg.annotation else None,
              }
              for arg in node.args.kwonlyargs
          ]
          records.append(
              {
                  'function': node.name,
                  'params': params,
                  'kwonly': kwonly,
                  'return': ast.unparse(node.returns) if node.returns else None,
              }
          )
  print(json.dumps(records, indent=2))
  PY
  ```
- Logged verification evidence under `H6` in `openspec/changes/add-python-extraction-parity/verification.md` and checked off tasks.md item `0.7`.
- Audited downstream consumers for Python coverage acceptance: TypeScript rules gate on `.ts` file sets, ML feature loader tolerates mixed language rows, taint modules remain uninvolved. Only outstanding tweak is the indexer summary string still labeling counts as “TypeScript”; tracked for follow-up.

### Session 5 (Python ORM FK Wiring)
- Extended `MemoryCache` to preload Python ORM metadata and type annotations (`python_model_names`, `python_relationship_aliases`, `python_fk_fields`, `python_param_types`), exposing helper getters for taint analysis.
- Added `theauditor/taint/orm_utils.py` with `enhance_python_fk_taint`, called from `propagation.trace_from_source` for both CFG and non-CFG flows to seed relationship/foreign-key aliases.
- Verified behavior with inline script:  
  ```bash
  cat <<'PY' | .venv/Scripts/python.exe -
  import sqlite3
  from pprint import pprint
  from theauditor.taint.memory_cache import attempt_cache_preload
  from theauditor.taint.orm_utils import enhance_python_fk_taint

  conn = sqlite3.connect('.pf/repo_index.db')
  cursor = conn.cursor()
  cache = attempt_cache_preload(cursor, memory_limit_mb=200)
  ctx = {'ProfileService.update_profile': {'vars': {'user'},
                                           'displays': {'ProfileService.update_profile'},
                                           'file': 'tests/fixtures/python/parity_sample.py',
                                           'python_model_bindings': {'user': 'User'}}}
  enhance_python_fk_taint(cursor, cache, ctx)
  pprint(ctx['ProfileService.update_profile']['vars'])
  conn.close()
  PY
  ```
  Output now includes relationship-derived aliases such as `user.posts`, `profile.user`, `posts.owner`, and FK paths like `posts.owner_id`, confirming ORM-aware taint expansion.
- Refined indexer summary to report per-language type annotation counts (`type annotations: 97 TypeScript, 4256 Python`), reflecting the new multi-language coverage.
- Authored dedicated fixtures for frameworks/imports (`sqlalchemy_app.py`, `pydantic_app.py`, `flask_app.py`, `fastapi_app.py`, `import_resolution/`) and exercised them via `tests/test_python_framework_extraction.py` (`pytest tests/test_python_framework_extraction.py -q`), validating ORM fields, validators, route metadata, and resolved imports end-to-end.

## Useful Commands / Queries
- Re-run validation: `openspec validate add-python-extraction-parity --strict`.
- Refresh DB: `aud full --offline` (set `THEAUDITOR_TIMEOUT_SECONDS=900`).
- Inspect type annotations:  
  ```powershell
  .venv/Scripts/python.exe -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); print(conn.execute('SELECT COUNT(*) FROM type_annotations WHERE file LIKE \"%.py\"').fetchone())"
  ```
- Check framework tables similarly (`SELECT COUNT(*) FROM python_routes;` etc.).

## Reference Notes
- Keep zero-fallback policy in mind (no silent skips; crash if schema contract breaks).
- When enhancing relationship extraction, update `openspec/.../spec.md` and `tasks.md` simultaneously.
- Before modifying taint analyzer, audit current consumers to ensure new tables are loaded into in-memory caches.
