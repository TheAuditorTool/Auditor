# Framework Extraction Parity - Implementation Tasks

**IMPORTANT**: Read `IMPLEMENTATION_COOKBOOK.md` first - it contains 100% copy-paste ready code with zero ambiguity. This tasks.md file provides the checklist, the cookbook provides the exact code.

## 0. Verification (COMPLETE)

- [x] 0.1 Verify Node.js extractor files exist and are non-trivial
- [x] 0.2 Verify extractors are called from batch_templates.js
- [x] 0.3 Verify data is returned from batch extraction
- [x] 0.4 Verify database tables are missing for Node.js frameworks
- [x] 0.5 Verify indexer integration is missing
- [x] 0.6 Verify Python database tables exist
- [x] 0.7 Verify Python extraction functions are called
- [x] 0.8 Verify Python extraction functions don't exist in implementation
- [x] 0.9 Run `aud index` and verify silent failures
- [x] 0.10 Document findings in verification.md

---

## 1. Node.js Schema Integration (Phase 1)

### 1.1 Add Sequelize Tables to node_schema.py

- [ ] 1.1.1 Add SEQUELIZE_MODELS table schema
  - Columns: file, line, model_name, table_name, extends_model (BOOLEAN)
  - Primary key: [file, model_name]
  - Indexes: file, model_name

- [ ] 1.1.2 Add SEQUELIZE_ASSOCIATIONS table schema
  - Columns: file, line, model_name, association_type, target_model, foreign_key, through_table
  - Primary key: [file, model_name, association_type, target_model]
  - Indexes: file, model_name, target_model, association_type

- [ ] 1.1.3 Update NODE_TABLES registry
  - Add "sequelize_models": SEQUELIZE_MODELS
  - Add "sequelize_associations": SEQUELIZE_ASSOCIATIONS

### 1.2 Add BullMQ Tables to node_schema.py

- [ ] 1.2.1 Add BULLMQ_QUEUES table schema
  - Columns: file, line, queue_name, redis_config (TEXT)
  - Primary key: [file, queue_name]
  - Indexes: file, queue_name

- [ ] 1.2.2 Add BULLMQ_WORKERS table schema
  - Columns: file, line, queue_name, worker_function, processor_path
  - Primary key: [file, queue_name, worker_function]
  - Indexes: file, queue_name, worker_function

- [ ] 1.2.3 Update NODE_TABLES registry
  - Add "bullmq_queues": BULLMQ_QUEUES
  - Add "bullmq_workers": BULLMQ_WORKERS

### 1.3 Add Angular Tables to node_schema.py

- [ ] 1.3.1 Add ANGULAR_COMPONENTS table schema
  - Columns: file, line, component_name, selector, template_path, style_paths, has_lifecycle_hooks (BOOLEAN)
  - Primary key: [file, component_name]
  - Indexes: file, component_name, selector

- [ ] 1.3.2 Add ANGULAR_SERVICES table schema
  - Columns: file, line, service_name, is_injectable (BOOLEAN), provided_in (TEXT)
  - Primary key: [file, service_name]
  - Indexes: file, service_name

- [ ] 1.3.3 Add ANGULAR_MODULES table schema
  - Columns: file, line, module_name, declarations (TEXT), imports (TEXT), providers (TEXT), exports (TEXT)
  - Primary key: [file, module_name]
  - Indexes: file, module_name

- [ ] 1.3.4 Add ANGULAR_GUARDS table schema
  - Columns: file, line, guard_name, guard_type, implements_interface
  - Primary key: [file, guard_name]
  - Indexes: file, guard_name, guard_type

- [ ] 1.3.5 Add DI_INJECTIONS table schema
  - Columns: file, line, target_class, injected_service, injection_type
  - Indexes: file, target_class, injected_service

- [ ] 1.3.6 Update NODE_TABLES registry
  - Add "angular_components": ANGULAR_COMPONENTS
  - Add "angular_services": ANGULAR_SERVICES
  - Add "angular_modules": ANGULAR_MODULES
  - Add "angular_guards": ANGULAR_GUARDS
  - Add "di_injections": DI_INJECTIONS

### 1.4 Update Schema Assertions

- [ ] 1.4.1 Update schema.py total table count assertion
  - Current: 116 tables
  - New: 125 tables (116 + 9 new Node.js tables)
  - Update line 78: `assert len(TABLES) == 125`

---

## 2. Node.js Indexer Integration (Phase 1)

### 2.1 Add Data Handling to javascript.py

- [ ] 2.1.1 Add sequelize_models to result dict initialization
  - Line ~76: Add `'sequelize_models': []`
  - Line ~76: Add `'sequelize_associations': []`

- [ ] 2.1.2 Add bullmq_jobs to result dict initialization
  - Line ~76: Add `'bullmq_queues': []`
  - Line ~76: Add `'bullmq_workers': []`

- [ ] 2.1.3 Add angular_* to result dict initialization
  - Line ~76: Add `'angular_components': []`
  - Line ~76: Add `'angular_services': []`
  - Line ~76: Add `'angular_modules': []`
  - Line ~76: Add `'angular_guards': []`
  - Line ~76: Add `'di_injections': []`

- [ ] 2.1.4 Extract framework data from batch extraction results
  - After line 98 (extracted_data handling)
  - Add code to extract sequelize_models, bullmq_jobs, angular_* from extracted_data
  - Extend result arrays with extracted framework data

### 2.2 Add Storage Logic to indexer/__init__.py

- [ ] 2.2.1 Add Sequelize storage after React storage (~line 950)
  - Store sequelize_models to database
  - Store sequelize_associations to database

- [ ] 2.2.2 Add BullMQ storage after Sequelize storage
  - Store bullmq_queues to database
  - Store bullmq_workers to database

- [ ] 2.2.3 Add Angular storage after BullMQ storage
  - Store angular_components to database
  - Store angular_services to database
  - Store angular_modules to database
  - Store angular_guards to database
  - Store di_injections to database

---

## 3. Python Extraction Implementation (Phase 2)

### 3.1 Implement Marshmallow Extraction

- [ ] 3.1.1 Add extract_marshmallow_schemas() function
  - Location: python_impl.py (after extract_pydantic_validators)
  - Strategy: Find classes extending Schema (from marshmallow import Schema)
  - Extract: schema_name, has_meta (BOOLEAN), meta_fields (TEXT)
  - Return: List[Dict] with file, line, schema_name, has_meta, meta_fields

- [ ] 3.1.2 Add extract_marshmallow_fields() function
  - Strategy: Find field assignments in Schema classes (fields.String(), fields.Integer(), etc.)
  - Extract: schema_name, field_name, field_type, is_required, validators
  - Return: List[Dict] with file, line, schema_name, field_name, field_type, is_required, validators

### 3.2 Implement WTForms Extraction

- [ ] 3.2.1 Add extract_wtforms_forms() function
  - Strategy: Find classes extending Form (from wtforms import Form)
  - Extract: form_name, has_csrf (BOOLEAN), submit_method
  - Return: List[Dict] with file, line, form_name, has_csrf, submit_method

- [ ] 3.2.2 Add extract_wtforms_fields() function
  - Strategy: Find field assignments in Form classes (StringField(), IntegerField(), etc.)
  - Extract: form_name, field_name, field_type, validators, default_value
  - Return: List[Dict] with file, line, form_name, field_name, field_type, validators, default_value

### 3.3 Implement Celery Extraction

- [ ] 3.3.1 Add extract_celery_tasks() function
  - Strategy: Find functions with @task or @app.task decorators
  - Extract: task_name (function name), bind (BOOLEAN), max_retries, rate_limit
  - Return: List[Dict] with file, line, task_name, bind, max_retries, rate_limit

- [ ] 3.3.2 Add extract_celery_task_calls() function
  - Strategy: Find .delay() and .apply_async() calls on task objects
  - Extract: task_name, call_type ('delay' or 'apply_async'), arguments
  - Return: List[Dict] with file, line, task_name, call_type, arguments

- [ ] 3.3.3 Add extract_celery_beat_schedules() function
  - Strategy: Find app.conf.beat_schedule dict or CELERYBEAT_SCHEDULE dict
  - Extract: schedule_name, task_name, crontab (TEXT), interval (TEXT)
  - Return: List[Dict] with file, line, schedule_name, task_name, crontab, interval

### 3.4 Implement Pytest Extraction

- [ ] 3.4.1 Add extract_pytest_fixtures() function
  - Strategy: Find functions with @pytest.fixture decorator
  - Extract: fixture_name (function name), scope ('function', 'class', 'module', 'session'), autouse (BOOLEAN)
  - Return: List[Dict] with file, line, fixture_name, scope, autouse

- [ ] 3.4.2 Add extract_pytest_parametrize() function
  - Strategy: Find @pytest.mark.parametrize decorators
  - Extract: test_function, parameter_names (TEXT), parameter_values (TEXT)
  - Return: List[Dict] with file, line, test_function, parameter_names, parameter_values

- [ ] 3.4.3 Add extract_pytest_markers() function
  - Strategy: Find @pytest.mark.* decorators (excluding parametrize)
  - Extract: test_function, marker_name, marker_args
  - Return: List[Dict] with file, line, test_function, marker_name, marker_args

---

## 4. Testing & Validation

### 4.1 Unit Tests (Node.js)

- [ ] 4.1.1 Create tests/fixtures/javascript/node-sequelize-orm/
  - Add fixture files with Sequelize models
  - Add spec.yaml with expected extraction counts

- [ ] 4.1.2 Create tests/fixtures/javascript/node-bullmq-jobs/
  - Add fixture files with BullMQ queues and workers
  - Add spec.yaml with expected extraction counts

- [ ] 4.1.3 Create tests/fixtures/javascript/node-angular-app/
  - Add fixture files with Angular components, services, modules, guards
  - Add spec.yaml with expected extraction counts

- [ ] 4.1.4 Run pytest tests for Node.js fixtures
  - Verify all tables populated correctly
  - Verify SQL queries in spec.yaml pass

### 4.2 Unit Tests (Python)

- [ ] 4.2.1 Create tests/fixtures/python/python-marshmallow-schemas/
  - Add fixture files with Marshmallow schemas
  - Add spec.yaml with expected extraction counts

- [ ] 4.2.2 Create tests/fixtures/python/python-wtforms-forms/
  - Add fixture files with WTForms forms
  - Add spec.yaml with expected extraction counts

- [ ] 4.2.3 Create tests/fixtures/python/python-celery-tasks/
  - Add fixture files with Celery tasks and beat schedules
  - Add spec.yaml with expected extraction counts

- [ ] 4.2.4 Create tests/fixtures/python/python-pytest-fixtures/
  - Add fixture files with pytest fixtures and parametrize
  - Add spec.yaml with expected extraction counts

- [ ] 4.2.5 Run pytest tests for Python fixtures
  - Verify all tables populated correctly
  - Verify SQL queries in spec.yaml pass

### 4.3 Integration Tests

- [ ] 4.3.1 Test on plant project (Node.js production project)
  - Run: `cd C:/Users/santa/Desktop/plant && aud index`
  - Verify: Sequelize models extracted (should be > 0)
  - Verify: BullMQ queues extracted (should be > 0)
  - Verify: React components still working (no regressions)

- [ ] 4.3.2 Test on PlantFlow project (Node.js production project)
  - Run: `cd C:/Users/santa/Desktop/PlantFlow && aud index`
  - Verify: All Node.js framework data extracted

- [ ] 4.3.3 Test on TheAuditor project (Python project)
  - Run: `cd C:/Users/santa/Desktop/TheAuditor && aud index`
  - Verify: Python framework tables populated (if any test files exist)

### 4.4 Downstream Consumer Tests

- [ ] 4.4.1 Test aud blueprint with framework data
  - Run: `aud blueprint`
  - Verify: Shows Sequelize models section
  - Verify: Shows BullMQ jobs section
  - Verify: Shows Angular components section

- [ ] 4.4.2 Test aud taint-analyze with framework patterns
  - Create test case with taint flow through Sequelize model
  - Run: `aud taint-analyze`
  - Verify: Taint tracked through ORM relationships

- [ ] 4.4.3 Test aud planning with framework migrations
  - Run: `aud planning --type migration`
  - Verify: Can plan Sequelize model migrations

---

## 5. Documentation

### 5.1 Create Spec Files

- [ ] 5.1.1 Create specs/framework-extraction/spec.md
  - Document framework detection requirements
  - Document extraction requirements for each framework
  - Add scenarios for Sequelize, BullMQ, Angular, Marshmallow, WTForms, Celery, Pytest

- [ ] 5.1.2 Update specs/node-extraction/spec.md (if exists, else create)
  - Document Node.js framework-specific patterns
  - Add extraction requirements for React, Vue, Angular, Sequelize, BullMQ

- [ ] 5.1.3 Update specs/python-extraction/spec.md
  - Document complete Python framework extraction
  - Add extraction requirements for all frameworks

### 5.2 Update README and Docs

- [ ] 5.2.1 Update README.md framework support section
  - List all supported frameworks with extraction status
  - Mark Sequelize, BullMQ, Angular, Marshmallow, WTForms, Celery, Pytest as SUPPORTED

- [ ] 5.2.2 Update EXTRACTION_GAPS.md
  - Remove Sequelize, BullMQ, Angular from gaps list
  - Remove Marshmallow, WTForms, Celery, Pytest from gaps list
  - Keep remaining gaps for Phase 3 (Zustand, React Query, etc.)

---

## 6. Post-Implementation Audit

### 6.1 Code Quality Audit

- [ ] 6.1.1 Re-read node_schema.py
  - Verify all 9 tables added correctly
  - Verify no syntax errors
  - Verify indexes on all foreign keys
  - Verify primary keys set correctly

- [ ] 6.1.2 Re-read javascript.py
  - Verify all framework data extracted from batch results
  - Verify result dict has all new keys
  - Verify no syntax errors

- [ ] 6.1.3 Re-read __init__.py
  - Verify all 9 framework data types stored to database
  - Verify proper error handling
  - Verify no regressions in existing storage code

- [ ] 6.1.4 Re-read python_impl.py
  - Verify all 10 extraction functions implemented
  - Verify proper AST traversal (no regex fallbacks)
  - Verify error handling (return empty list on failure)
  - Verify no syntax errors

### 6.2 Regression Testing

- [ ] 6.2.1 Run full test suite
  - Command: `pytest tests/`
  - Verify: All existing tests pass
  - Verify: No regressions in React/Vue/TypeScript extraction

- [ ] 6.2.2 Run aud index on TheAuditor project
  - Command: `aud index`
  - Verify: Completes without errors
  - Verify: Symbol counts match previous runs
  - Verify: New framework tables populated (if applicable)

- [ ] 6.2.3 Run aud full on TheAuditor project
  - Command: `aud full --offline`
  - Verify: All pipelines complete
  - Verify: No errors in taint analysis
  - Verify: Database saved to .pf/history/

### 6.3 Database Schema Validation

- [ ] 6.3.1 Verify table count
  - Expected: 125 tables (116 + 9 new)
  - Command: `SELECT COUNT(*) FROM sqlite_master WHERE type='table'`

- [ ] 6.3.2 Verify all indexes created
  - Command: `SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_sequelize%'`
  - Verify: All Sequelize indexes exist
  - Repeat for BullMQ, Angular tables

- [ ] 6.3.3 Run schema validation
  - Command: `python -c "from theauditor.indexer.schema import validate_all_tables; ..."`
  - Verify: No schema mismatches

---

## 7. Deployment Preparation

### 7.1 Version Bump

- [ ] 7.1.1 Update pyproject.toml version
  - Current: 1.3.0-RC1
  - New: 1.3.0-RC2 (or 1.3.0 if ready for release)

- [ ] 7.1.2 Update CHANGELOG.md
  - Add entry for framework extraction parity
  - List all new framework support

### 7.2 Git Commit

- [ ] 7.2.1 Stage all changes
  - `git add openspec/changes/add-framework-extraction-parity/`
  - `git add theauditor/indexer/schemas/node_schema.py`
  - `git add theauditor/indexer/extractors/javascript.py`
  - `git add theauditor/indexer/__init__.py`
  - `git add theauditor/ast_extractors/python_impl.py`
  - `git add tests/fixtures/javascript/node-*`
  - `git add tests/fixtures/python/python-*`

- [ ] 7.2.2 Create commit
  - Message: `feat(extraction): add framework extraction parity for Sequelize, BullMQ, Angular, Marshmallow, WTForms, Celery, Pytest`
  - Include verification.md reference in commit body

---

## Summary

**Total Tasks**: 107 tasks
**Completed**: 10 (verification phase)
**Remaining**: 97 tasks

**Estimated Effort**:
- Phase 1 (Node.js): 2 days (tasks 1.1-2.2)
- Phase 2 (Python): 3 days (tasks 3.1-3.4)
- Testing: 2 days (tasks 4.1-4.4)
- Documentation: 1 day (tasks 5.1-5.2)
- Audit & Deployment: 1 day (tasks 6.1-7.2)

**Total**: 9 days of focused implementation

**Dependencies**:
- Phase 2 can start in parallel with Phase 1 (independent codebases)
- Testing requires both phases complete
- Documentation can happen in parallel with testing
- Audit must happen after all code complete
