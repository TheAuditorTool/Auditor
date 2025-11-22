# Framework Extraction Parity - Closing the Data Gap

**Change ID**: add-framework-extraction-parity
**Created**: 2025-11-01
**Status**: Proposed
**Type**: Enhancement (Data Completeness)

## Why

TheAuditor has a critical data gap: extractors exist for Sequelize, BullMQ, and Angular, but the extracted data is discarded because database tables and indexer integration are missing. Similarly, Python extraction has database tables for Marshmallow, WTForms, Celery, and Pytest, but the extraction functions don't exist.

**Impact on Downstream Consumers**:
- `aud blueprint` cannot show security patterns for Sequelize models, BullMQ jobs, Angular services
- `aud planning` cannot plan migrations for these frameworks
- `aud taint-analyze` misses taint flows through job queues, ORM relationships, DI patterns
- `aud context` cannot apply business logic to framework-specific patterns

This isn't "nice to have" - it's existential. Production projects use these frameworks, and TheAuditor is blind to them.

## What Changes

### Phase 1: Node.js Framework Integration (Immediate)

**Problem Verified 2025-11-01**:
1. ✅ Extractors EXIST: `sequelize_extractors.js` (99 lines), `bullmq_extractors.js` (82 lines), `angular_extractors.js` (213 lines)
2. ✅ Extractors ARE CALLED: `batch_templates.js:416-418` calls all three
3. ✅ Data IS RETURNED: `batch_templates.js:484-490` returns sequelize_models, bullmq_jobs, angular_*
4. ❌ NO DATABASE TABLES: `node_schema.py` has NO tables for these frameworks
5. ❌ NO INDEXER INTEGRATION: `javascript.py` has NO code to handle `sequelize_models`, `bullmq_jobs`, `angular_*` keys
6. ❌ DATA IS DISCARDED: Extracted data thrown away because no storage exists

**Solution**:
- Add database tables to `node_schema.py`: SEQUELIZE_MODELS, SEQUELIZE_ASSOCIATIONS, BULLMQ_QUEUES, BULLMQ_WORKERS, ANGULAR_COMPONENTS, ANGULAR_SERVICES, ANGULAR_MODULES, ANGULAR_GUARDS, DI_INJECTIONS
- Add indexer integration in `javascript.py` to store extracted data
- Update indexer `__init__.py` to handle new data types

### Phase 2: Python Framework Completion (High Priority)

**Problem Verified 2025-11-01**:
1. ✅ Database tables EXIST: `python_schema.py` has PYTHON_MARSHMALLOW_SCHEMAS, PYTHON_WTFORMS_FORMS, PYTHON_CELERY_TASKS, PYTHON_PYTEST_FIXTURES, etc.
2. ✅ Extractor calls EXIST: `python.py:243-285` calls extract_marshmallow_*, extract_wtforms_*, extract_celery_*, extract_pytest_*
3. ❌ Extraction functions DON'T EXIST: `python_impl.py` has NO implementation for these functions
4. ❌ Functions called but missing: Silent failure (likely wrapped in try/except or conditional checks)

**Solution**:
- Implement extraction functions in `python_impl.py`:
  - `extract_marshmallow_schemas()` - Detect Marshmallow schema classes
  - `extract_marshmallow_fields()` - Extract field definitions with validators
  - `extract_wtforms_forms()` - Detect WTForms form classes
  - `extract_wtforms_fields()` - Extract field definitions
  - `extract_celery_tasks()` - Detect @task decorators
  - `extract_celery_task_calls()` - Track .delay(), .apply_async() calls
  - `extract_celery_beat_schedules()` - Extract periodic task schedules
  - `extract_pytest_fixtures()` - Detect @pytest.fixture decorators
  - `extract_pytest_parametrize()` - Extract @pytest.mark.parametrize
  - `extract_pytest_markers()` - Extract custom pytest markers

### Phase 3: Additional Framework Gaps (Future)

Based on EXTRACTION_GAPS.md analysis, these frameworks are used in production but have ZERO extraction:

**Node.js Frameworks** (No extractors, no tables):
- Zustand (state management)
- React Query (@tanstack/react-query - data fetching)
- Material-UI (theming, styled components)
- Dexie (IndexedDB client-side database)
- Redis (caching, sessions)
- i18next (internationalization)
- Winston/Pino (logging)
- Multer (file uploads)
- Handlebars (templating)
- react-router-dom v7 (routing with loaders/actions)

**Python Frameworks** (Tables exist, extractors missing):
- Alembic (database migrations)
- Redis (Python client)
- Jinja2 (templating)
- Click (CLI commands)
- Loguru (logging)

## Impact

### Breaking Changes
**NONE** - This is purely additive.

### Affected Specs
- `specs/framework-extraction/spec.md` (NEW) - Framework detection and extraction requirements
- `specs/node-extraction/spec.md` (NEW) - Node.js framework-specific patterns
- `specs/python-extraction/spec.md` (MODIFIED) - Complete Python framework extraction

### Affected Code
**Node.js**:
- `theauditor/indexer/schemas/node_schema.py` - Add 9 new tables
- `theauditor/indexer/extractors/javascript.py` - Add integration code
- `theauditor/indexer/__init__.py` - Handle new data types
- Total new code: ~300 lines (schema + integration)

**Python**:
- `theauditor/ast_extractors/python_impl.py` - Implement 10 extraction functions
- Total new code: ~800 lines (extraction logic)

**Total Effort**: ~1,100 lines of integration code

### Database Schema Impact
**New Tables** (Node.js):
```sql
-- Sequelize ORM
CREATE TABLE sequelize_models (
    file TEXT,
    line INTEGER,
    model_name TEXT,
    table_name TEXT,
    extends_model BOOLEAN
);

CREATE TABLE sequelize_associations (
    file TEXT,
    line INTEGER,
    model_name TEXT,
    association_type TEXT, -- 'hasMany', 'belongsTo', 'hasOne', 'belongsToMany'
    target_model TEXT,
    foreign_key TEXT,
    through_table TEXT
);

-- BullMQ Job Queues
CREATE TABLE bullmq_queues (
    file TEXT,
    line INTEGER,
    queue_name TEXT,
    redis_config TEXT
);

CREATE TABLE bullmq_workers (
    file TEXT,
    line INTEGER,
    queue_name TEXT,
    worker_function TEXT,
    processor_path TEXT
);

-- Angular Framework
CREATE TABLE angular_components (
    file TEXT,
    line INTEGER,
    component_name TEXT,
    selector TEXT,
    template_path TEXT,
    style_paths TEXT
);

CREATE TABLE angular_services (
    file TEXT,
    line INTEGER,
    service_name TEXT,
    is_injectable BOOLEAN
);

CREATE TABLE angular_modules (
    file TEXT,
    line INTEGER,
    module_name TEXT,
    declarations TEXT,
    imports TEXT,
    providers TEXT
);

CREATE TABLE angular_guards (
    file TEXT,
    line INTEGER,
    guard_name TEXT,
    guard_type TEXT, -- 'CanActivate', 'CanDeactivate', etc.
    implements_interface TEXT
);

CREATE TABLE di_injections (
    file TEXT,
    line INTEGER,
    target_class TEXT,
    injected_service TEXT,
    injection_type TEXT -- 'constructor', 'property'
);
```

### Downstream Consumer Impact
**Commands Affected**:
- ✅ `aud blueprint` - Will show Sequelize/BullMQ/Angular patterns
- ✅ `aud planning` - Can plan migrations for these frameworks
- ✅ `aud taint-analyze` - Track taint through job queues, ORM, DI
- ✅ `aud context` - Apply business logic to framework patterns
- ✅ `aud detect-patterns` - Detect framework-specific security issues

## Verification Evidence

**Investigation Date**: 2025-11-01
**Method**: Source code verification + database inspection + tool execution

### Node.js Verification

**Extractor Files Confirmed**:
```bash
$ wc -l theauditor/ast_extractors/javascript/*.js
   213 angular_extractors.js
    82 bullmq_extractors.js
    99 sequelize_extractors.js
```

**Extraction Confirmed in batch_templates.js:416-418**:
```javascript
const sequelizeModels = extractSequelizeModels(functions, classes, functionCallArgs, imports);
const bullmqJobs = extractBullMQJobs(functions, classes, functionCallArgs, imports);
const angularData = extractAngularComponents(functions, classes, imports, functionCallArgs);
```

**Data Return Confirmed in batch_templates.js:484-490**:
```javascript
sequelize_models: sequelizeModels,
bullmq_jobs: bullmqJobs,
angular_components: angularData.components,
angular_services: angularData.services,
angular_modules: angularData.modules,
angular_guards: angularData.guards,
```

**Indexer Integration Missing**:
```bash
$ grep -r "sequelize_models\|bullmq_jobs\|angular_components" theauditor/indexer/
# NO RESULTS - indexer doesn't know what to do with this data
```

**Database Tables Missing**:
```bash
$ python -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); ..."
sequelize_models: TABLE DOES NOT EXIST
bullmq_jobs: TABLE DOES NOT EXIST
angular_components: TABLE DOES NOT EXIST
```

### Python Verification

**Extractor Calls Confirmed in python.py:243-285**:
```python
marshmallow_schemas = python_impl.extract_marshmallow_schemas(tree, self.ast_parser)
wtforms_forms = python_impl.extract_wtforms_forms(tree, self.ast_parser)
celery_tasks = python_impl.extract_celery_tasks(tree, self.ast_parser)
pytest_fixtures = python_impl.extract_pytest_fixtures(tree, self.ast_parser)
```

**Extraction Functions Missing**:
```bash
$ grep -E "^def extract_(marshmallow|wtforms|celery|pytest)" theauditor/ast_extractors/python_impl.py
# NO RESULTS - functions don't exist
```

**Database Tables Exist**:
```bash
$ python -c "import sqlite3; conn = sqlite3.connect('.pf/repo_index.db'); ..."
python_marshmallow_schemas: 0 rows (TABLE EXISTS)
python_wtforms_forms: 0 rows (TABLE EXISTS)
python_celery_tasks: 0 rows (TABLE EXISTS)
python_pytest_fixtures: 0 rows (TABLE EXISTS)
```

## Relationship to Other Changes

- **Distinct from `python-extraction-phase2-modular-architecture`**: That change focuses on architectural refactoring (splitting monoliths, modularizing extractors). This change focuses on **data completeness** (closing extraction gaps).
- **Complements `add-graphql-execution-graph-huge-task`**: That change adds GraphQL extraction. This change completes ORM/job queue/framework extraction.
- **Different from `pythonparity` ticket**: That ticket systematically maps the entire Python ecosystem. This change is laser-focused on **closing the gap between extractors and database schema** for frameworks already in use.

## Success Criteria

1. All 9 new Node.js tables created and integrated
2. All 10 Python extraction functions implemented
3. `aud index` on production project (plant, PlantFlow) populates new tables
4. `aud blueprint` shows framework patterns
5. `aud taint-analyze` tracks taint through new frameworks
6. No regressions in existing extraction

## Next Steps

1. Review and approve this proposal
2. Read `IMPLEMENTATION_COOKBOOK.md` - contains 100% copy-paste ready code
3. Implement Phase 1 (Node.js integration) - 2-3 hours (copy-paste from cookbook)
4. Implement Phase 2 (Python extraction) - 3-4 hours (copy-paste from cookbook)
5. Test on production projects
6. Document in specs/framework-extraction/

## Implementation Resources

- **IMPLEMENTATION_COOKBOOK.md**: Complete worked examples with copy-paste ready code
- **verification.md**: Detailed investigation findings and evidence
- **tasks.md**: 107-task checklist
- **design.md**: Technical decisions and rationale
- **specs/framework-extraction/spec.md**: Requirements and scenarios
