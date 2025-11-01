# Tasks: refactor-framework-extractors-domain-split

**Status:** Proposed
**Total Tasks:** 24
**Completed:** 0
**In Progress:** 0

---

## Phase 1: Pre-Implementation Verification (4 tasks)

### [ ] Task 1.1: Analyze Current File Structure
**Owner:** AI Lead Coder
**Est:** 15 min
**Description:**
- Read `framework_extractors.py` in full (2222 lines)
- Document exact line ranges for each framework domain
- Identify all shared helper functions and their usage patterns
- Verify no circular dependencies between extractors

**Acceptance Criteria:**
- Line range mapping documented: ORM (215-514), Validation (517+1123-1653), Django Web (620-1120), Celery (1656-1980), GraphQL (1987-2222)
- Helper function usage matrix created (which helpers are used by which extractors)
- No circular dependencies found

---

### [ ] Task 1.2: Verify Import Dependencies
**Owner:** AI Lead Coder
**Est:** 10 min
**Description:**
- Grep for `from framework_extractors import` across codebase
- Verify `python/__init__.py` imports (lines 111-134)
- Check if any external files import directly from `framework_extractors.py`
- Document all import paths that must remain working

**Acceptance Criteria:**
- All import locations documented
- `__init__.py` is the primary importer (confirmed)
- No external direct imports found (or documented if found)

**Verification Command:**
```bash
grep -r "from.*framework_extractors import" theauditor/ tests/
grep -r "import framework_extractors" theauditor/ tests/
```

---

### [ ] Task 1.3: Run Baseline Tests
**Owner:** AI Lead Coder
**Est:** 5 min
**Description:**
- Run existing framework extraction tests
- Document current test coverage
- Verify all tests pass before refactor

**Acceptance Criteria:**
- `pytest tests/test_python_framework_extraction.py -v` passes 100%
- Test output captured as baseline

**Verification Command:**
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -m pytest tests/test_python_framework_extraction.py -v
```

---

### [ ] Task 1.4: Create Backup Branch
**Owner:** AI Lead Coder
**Est:** 2 min
**Description:**
- Create backup branch from current state
- Ensure clean working tree

**Acceptance Criteria:**
- Branch `refactor-framework-extractors-backup` created
- Git status clean

**Verification Command:**
```bash
git checkout -b refactor-framework-extractors-backup
git checkout pythonparity  # Return to work branch
```

---

## Phase 2: Create New Domain Files (8 tasks)

### [ ] Task 2.1: Create `orm_extractors.py`
**Owner:** AI Lead Coder
**Est:** 20 min
**Description:**
- Copy lines 215-514 from `framework_extractors.py` (SQLAlchemy, Django ORM)
- Copy shared helpers: `_get_str_constant()`, `_keyword_arg()`, `_get_bool_constant()`, `_cascade_implies_delete()`, `_extract_backref_name()`, `_extract_backref_cascade()`, `_infer_relationship_type()`, `_inverse_relationship_type()`, `_get_type_annotation()`, `_is_truthy()`
- Add module docstring explaining scope
- Add imports: `import ast, logging, typing`
- Add: `from ..base import get_node_name`

**Acceptance Criteria:**
- File created: `theauditor/ast_extractors/python/orm_extractors.py`
- Contains: `extract_sqlalchemy_definitions()`, `extract_django_definitions()`
- Contains: All ORM-specific helper functions (marked with `_` prefix)
- File is ~350 lines
- No syntax errors: `python -m py_compile theauditor/ast_extractors/python/orm_extractors.py`

**Module Docstring Template:**
```python
"""ORM framework extractors - SQLAlchemy and Django ORM.

This module extracts database ORM patterns:
- SQLAlchemy: Models, fields, relationships (1:1, 1:N, M:N)
- Django ORM: Models, relationships, ForeignKey/ManyToMany

ARCHITECTURAL CONTRACT:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'model_name', 'field_name', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts
"""
```

---

### [ ] Task 2.2: Create `validation_extractors.py`
**Owner:** AI Lead Coder
**Est:** 30 min
**Description:**
- Copy lines 517-564 (Pydantic)
- Copy lines 1123-1297 (Marshmallow schemas + fields)
- Copy lines 1300-1494 (DRF serializers + fields)
- Copy lines 1497-1653 (WTForms forms + fields)
- Copy shared helpers: `_get_str_constant()`, `_keyword_arg()`, `_get_bool_constant()`
- Add module docstring

**Acceptance Criteria:**
- File created: `theauditor/ast_extractors/python/validation_extractors.py`
- Contains 8 functions: `extract_pydantic_validators()`, `extract_marshmallow_schemas()`, `extract_marshmallow_fields()`, `extract_drf_serializers()`, `extract_drf_serializer_fields()`, `extract_wtforms_forms()`, `extract_wtforms_fields()`, `_extract_list_of_strings()` (helper)
- File is ~1200 lines
- No syntax errors

---

### [ ] Task 2.3: Create `django_web_extractors.py`
**Owner:** AI Lead Coder
**Est:** 25 min
**Description:**
- Copy lines 599-754 (Django CBVs + `DJANGO_CBV_TYPES` constant)
- Copy lines 757-906 (Django Forms + Form Fields)
- Copy lines 909-1018 (Django Admin)
- Copy lines 1035-1120 (Django Middleware)
- Copy shared helpers: `_get_str_constant()`, `_keyword_arg()`, `_extract_list_of_strings()`
- Add module docstring

**Acceptance Criteria:**
- File created: `theauditor/ast_extractors/python/django_web_extractors.py`
- Contains: `extract_django_cbvs()`, `extract_django_forms()`, `extract_django_form_fields()`, `extract_django_admin()`, `extract_django_middleware()`
- Contains: `DJANGO_CBV_TYPES` dict constant
- File is ~650 lines
- No syntax errors

---

### [ ] Task 2.4: Create `task_graphql_extractors.py`
**Owner:** AI Lead Coder
**Est:** 25 min
**Description:**
- Copy lines 1656-1980 (Celery: tasks, calls, beat schedules)
- Copy lines 1987-2222 (GraphQL: Graphene, Ariadne, Strawberry resolvers)
- Copy shared helpers: `_get_str_constant()`, `_keyword_arg()`, `_dependency_name()` (for FastAPI deps)
- Add module docstring

**Acceptance Criteria:**
- File created: `theauditor/ast_extractors/python/task_graphql_extractors.py`
- Contains Celery: `extract_celery_tasks()`, `extract_celery_task_calls()`, `extract_celery_beat_schedules()`
- Contains GraphQL: `extract_graphene_resolvers()`, `extract_ariadne_resolvers()`, `extract_strawberry_resolvers()`
- File is ~750 lines
- No syntax errors

---

### [ ] Task 2.5: Verify All New Files Compile
**Owner:** AI Lead Coder
**Est:** 5 min
**Description:**
- Compile check all 4 new files
- Verify no missing imports

**Acceptance Criteria:**
- All files pass: `python -m py_compile theauditor/ast_extractors/python/orm_extractors.py`
- All files pass: `python -m py_compile theauditor/ast_extractors/python/validation_extractors.py`
- All files pass: `python -m py_compile theauditor/ast_extractors/python/django_web_extractors.py`
- All files pass: `python -m py_compile theauditor/ast_extractors/python/task_graphql_extractors.py`

---

### [ ] Task 2.6: Test Import New Modules Directly
**Owner:** AI Lead Coder
**Est:** 5 min
**Description:**
- Test importing each new module
- Verify all functions are accessible

**Acceptance Criteria:**
- Works: `python -c "from theauditor.ast_extractors.python.orm_extractors import extract_sqlalchemy_definitions; print('OK')"`
- Works: `python -c "from theauditor.ast_extractors.python.validation_extractors import extract_pydantic_validators; print('OK')"`
- Works: `python -c "from theauditor.ast_extractors.python.django_web_extractors import extract_django_cbvs; print('OK')"`
- Works: `python -c "from theauditor.ast_extractors.python.task_graphql_extractors import extract_celery_tasks; print('OK')"`

---

### [ ] Task 2.7: Handle Flask Blueprints Extraction
**Owner:** AI Lead Coder
**Est:** 10 min
**Description:**
- Decision: Keep `extract_flask_blueprints()` in which file?
- Option A: Move to `flask_extractors.py` (logically correct but adds scope)
- Option B: Keep in `orm_extractors.py` temporarily (simple, will move later)
- **DECISION:** Option B - Keep in `orm_extractors.py` for now

**Acceptance Criteria:**
- `extract_flask_blueprints()` copied to `orm_extractors.py` (temp location)
- Comment added: "# TODO: Move to flask_extractors.py in future PR"
- Function documented in verification.md as "temporary placement"

---

### [ ] Task 2.8: Handle FastAPI Dependencies Function
**Owner:** AI Lead Coder
**Est:** 10 min
**Description:**
- Decision: Keep `_extract_fastapi_dependencies()` in facade or move to domain file?
- **DECISION:** Keep in facade (`framework_extractors.py`) since it's used by upcoming FastAPI routes work

**Acceptance Criteria:**
- `_extract_fastapi_dependencies()` remains in `framework_extractors.py`
- `FASTAPI_HTTP_METHODS` constant remains in `framework_extractors.py`
- Comment added: "# Kept in facade for FastAPI routes extraction (future work)"

---

## Phase 3: Update Facade (3 tasks)

### [ ] Task 3.1: Replace `framework_extractors.py` with Facade
**Owner:** AI Lead Coder
**Est:** 15 min
**Description:**
- Backup current `framework_extractors.py` to `framework_extractors.py.bak`
- Replace with re-export facade (see proposal.md Phase 2 for template)
- Import all functions from 4 new modules
- Keep `FASTAPI_HTTP_METHODS` + `_extract_fastapi_dependencies()` in facade
- Add `__all__` list for explicit exports

**Acceptance Criteria:**
- Old file backed up: `framework_extractors.py.bak` exists (for reference)
- New facade is ~80 lines
- Contains imports from all 4 domain modules
- Contains `FASTAPI_HTTP_METHODS` constant
- Contains `_extract_fastapi_dependencies()` function
- Contains `__all__` list with all 20+ function names

**Facade Template:** See proposal.md Phase 2 for full implementation.

---

### [ ] Task 3.2: Verify Facade Imports Work
**Owner:** AI Lead Coder
**Est:** 5 min
**Description:**
- Test importing from facade (backward compatibility)
- Verify all functions accessible

**Acceptance Criteria:**
- Works: `python -c "from theauditor.ast_extractors.python.framework_extractors import extract_sqlalchemy_definitions; print('OK')"`
- Works: `python -c "from theauditor.ast_extractors.python.framework_extractors import extract_celery_tasks; print('OK')"`
- Works: `python -c "from theauditor.ast_extractors.python.framework_extractors import FASTAPI_HTTP_METHODS; print('OK')"`

---

### [ ] Task 3.3: Update `__init__.py` Comments (Optional)
**Owner:** AI Lead Coder
**Est:** 5 min
**Description:**
- Add comment in `python/__init__.py` explaining facade pattern
- Update docstring: "Framework extractors are split into domain modules (orm_extractors, validation_extractors, etc.) but re-exported via framework_extractors.py facade for backward compatibility."

**Acceptance Criteria:**
- Comment added at line 111 (before framework_extractors import)
- Docstring updated at top of file

---

## Phase 4: Verification & Testing (6 tasks)

### [ ] Task 4.1: Run Framework Extraction Tests
**Owner:** AI Lead Coder
**Est:** 10 min
**Description:**
- Run full test suite for framework extraction
- Compare output to baseline (Task 1.3)

**Acceptance Criteria:**
- All tests pass: `pytest tests/test_python_framework_extraction.py -v`
- Output matches baseline (no new failures)

---

### [ ] Task 4.2: Index Test Project
**Owner:** AI Lead Coder
**Est:** 10 min
**Description:**
- Index `tests/fixtures/python/realworld_project` with new code
- Verify ORM, validation, Celery, Django patterns extracted correctly
- Compare symbol counts to baseline

**Acceptance Criteria:**
- Index completes: `cd tests/fixtures/python/realworld_project && aud index`
- SQLAlchemy models found in `.pf/repo_index.db` (query `python_orm_models` table)
- Django forms found (query `django_forms` table)
- Celery tasks found (query `celery_tasks` table)
- GraphQL resolvers found (query `graphql_resolvers` table)

**Verification Queries:**
```bash
cd tests/fixtures/python/realworld_project && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
print('ORM Models:', conn.execute('SELECT COUNT(*) FROM python_orm_models').fetchone()[0])
print('Django Forms:', conn.execute('SELECT COUNT(*) FROM django_forms').fetchone()[0])
print('Celery Tasks:', conn.execute('SELECT COUNT(*) FROM celery_tasks').fetchone()[0])
print('GraphQL Resolvers:', conn.execute('SELECT COUNT(*) FROM graphql_resolvers').fetchone()[0])
conn.close()
"
```

---

### [ ] Task 4.3: Verify Line Counts
**Owner:** AI Lead Coder
**Est:** 2 min
**Description:**
- Count lines in all new files
- Verify reduction in facade file

**Acceptance Criteria:**
- `orm_extractors.py`: ~350 lines
- `validation_extractors.py`: ~1200 lines
- `django_web_extractors.py`: ~650 lines
- `task_graphql_extractors.py`: ~750 lines
- `framework_extractors.py` (facade): ~80 lines
- **Total:** ~3030 lines (vs original 2222 lines - acceptable due to helper duplication)

**Verification Command:**
```bash
wc -l theauditor/ast_extractors/python/orm_extractors.py
wc -l theauditor/ast_extractors/python/validation_extractors.py
wc -l theauditor/ast_extractors/python/django_web_extractors.py
wc -l theauditor/ast_extractors/python/task_graphql_extractors.py
wc -l theauditor/ast_extractors/python/framework_extractors.py
```

---

### [ ] Task 4.4: Check for Duplicated Code (Helper Analysis)
**Owner:** Lead Auditor (Gemini AI)
**Est:** 15 min
**Description:**
- Analyze helper function duplication across 4 files
- Verify duplication is acceptable (<50 lines per file)
- Document in verification.md

**Acceptance Criteria:**
- Helper duplication documented
- Total duplicated code <200 lines across all files
- Decision ratified: "Acceptable for self-contained modules"

---

### [ ] Task 4.5: Import Path Documentation
**Owner:** AI Lead Coder
**Est:** 10 min
**Description:**
- Document all valid import paths in `verification.md`
- Examples:
  - `from theauditor.ast_extractors.python import extract_sqlalchemy_definitions` (via `__init__.py`)
  - `from theauditor.ast_extractors.python.framework_extractors import extract_sqlalchemy_definitions` (via facade)
  - `from theauditor.ast_extractors.python.orm_extractors import extract_sqlalchemy_definitions` (direct)

**Acceptance Criteria:**
- All 3 import patterns documented
- Recommended pattern specified: "Use `from python import` for consistency with existing code"

---

### [ ] Task 4.6: OpenSpec Validation
**Owner:** AI Lead Coder
**Est:** 5 min
**Description:**
- Validate OpenSpec proposal structure
- Ensure all required files present

**Acceptance Criteria:**
- Command passes: `openspec validate --strict refactor-framework-extractors-domain-split`
- All required files present: `proposal.md`, `tasks.md`, `verification.md`

---

## Phase 5: Documentation & Cleanup (3 tasks)

### [ ] Task 5.1: Update Module Docstrings
**Owner:** AI Lead Coder
**Est:** 10 min
**Description:**
- Ensure all 4 new files have complete module docstrings
- Follow architectural contract pattern (see Task 2.1 template)

**Acceptance Criteria:**
- All files have docstrings explaining:
  - Scope of extractors in file
  - Frameworks covered
  - Architectural contract (RECEIVE/EXTRACT/RETURN/MUST NOT)

---

### [ ] Task 5.2: Create Migration Guide
**Owner:** AI Lead Coder
**Est:** 15 min
**Description:**
- Create `openspec/changes/refactor-framework-extractors-domain-split/MIGRATION.md`
- Document import path changes (none, but explain facade)
- Explain why developers see 4 new files

**Acceptance Criteria:**
- `MIGRATION.md` created
- Explains: "No code changes required. Existing imports continue working via facade."
- Explains: "New code can import directly from domain modules for clarity."

---

### [ ] Task 5.3: Archive Old File (Optional)
**Owner:** AI Lead Coder
**Est:** 2 min
**Description:**
- Decide: Keep `framework_extractors.py.bak` or delete?
- **DECISION:** Keep for 1 sprint, then delete

**Acceptance Criteria:**
- `.bak` file kept (for reference during review)
- Note added to `tasks.md`: "Delete `framework_extractors.py.bak` after 1 sprint if no rollback needed"

---

## Rollback Plan

If refactor fails or introduces regressions:

1. **Restore from `.bak` file:**
   ```bash
   cp theauditor/ast_extractors/python/framework_extractors.py.bak theauditor/ast_extractors/python/framework_extractors.py
   ```

2. **Delete new files:**
   ```bash
   rm theauditor/ast_extractors/python/orm_extractors.py
   rm theauditor/ast_extractors/python/validation_extractors.py
   rm theauditor/ast_extractors/python/django_web_extractors.py
   rm theauditor/ast_extractors/python/task_graphql_extractors.py
   ```

3. **Revert `__init__.py` changes:**
   ```bash
   git checkout pythonparity -- theauditor/ast_extractors/python/__init__.py
   ```

4. **Re-run tests to confirm rollback:**
   ```bash
   pytest tests/test_python_framework_extraction.py -v
   ```

---

## Success Metrics

- [ ] All 24 tasks completed
- [ ] Zero test failures introduced
- [ ] All imports working (backward compatible)
- [ ] File sizes: orm (~350), validation (~1200), django_web (~650), task_graphql (~750), facade (~80)
- [ ] OpenSpec validation passes
- [ ] Architect approves refactor

---

## Notes for AI Lead Coder

**This refactor is CODE MOVEMENT ONLY. DO NOT:**
- Change extractor logic
- Modify function signatures
- Add new features
- Refactor algorithms

**This refactor IS:**
- Copy-paste code blocks to new files
- Update imports
- Add docstrings
- Verify tests still pass

**If you find bugs or improvements while doing this refactor:**
- Document them in `verification.md` under "Issues Found During Refactor"
- DO NOT fix them in this PR
- Create separate OpenSpec proposals for bug fixes

**Teamsop.md Compliance:**
- Follow "Assume Nothing, Verify Everything" - test every step
- Use `python -c` for quick import checks
- Run `pytest` after each phase
- Document discrepancies in `verification.md`
