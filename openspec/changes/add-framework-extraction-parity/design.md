# Framework Extraction Parity - Design Document

**Change ID**: add-framework-extraction-parity
**Created**: 2025-11-01
**Status**: Proposed

---

## Context

TheAuditor's extraction pipeline has a critical disconnect:

**Node.js**: Extractors exist (Sequelize, BullMQ, Angular) and return data, but database tables don't exist and indexer doesn't handle the data. Result: Data extracted then discarded.

**Python**: Database tables exist (Marshmallow, WTForms, Celery, Pytest) and indexer calls extraction functions, but functions don't exist. Result: Functions called but fail silently.

**Business Impact**: Production projects using these frameworks see ZERO extraction, making `aud blueprint`, `aud taint-analyze`, and `aud planning` blind to 50%+ of real-world framework usage.

---

## Goals / Non-Goals

### Goals

1. **Data Completeness**: Close the gap between extractors and database schema - every extractor must have tables, every table must have extractors.
2. **Silent Failure Prevention**: Eliminate cases where data is extracted but discarded, or functions are called but don't exist.
3. **Downstream Enablement**: Enable `aud blueprint`, `aud taint-analyze`, and `aud planning` to work with framework-specific patterns.
4. **No Regressions**: Maintain 100% compatibility with existing extraction (React, Vue, TypeScript, Python ORM).

### Non-Goals

1. **Not Phase 3 Frameworks**: This change does NOT add Zustand, React Query, Material-UI, Dexie, Redis, i18next, Winston, Multer, Handlebars, etc. Those are future work.
2. **Not Architecture Refactoring**: This change does NOT refactor extractor architecture (that's `python-extraction-phase2-modular-architecture`).
3. **Not Performance Optimization**: This change does NOT optimize extraction speed (acceptable to add +3-5% indexing time).
4. **Not UI Changes**: This change does NOT modify CLI output formats or user-facing messages (except logging framework extraction counts).

---

## Decisions

### Decision 1: Node.js Tables in node_schema.py (Not Separate Files)

**What**: Add all 9 new Node.js tables (Sequelize, BullMQ, Angular) to existing `node_schema.py` file rather than creating separate `sequelize_schema.py`, `bullmq_schema.py`, `angular_schema.py` files.

**Why**:
- Consistency with existing pattern (React, Vue, TypeScript all in `node_schema.py`)
- File size remains manageable (426 lines → ~626 lines, well under 1000-line threshold)
- Easier to maintain single source of truth for Node.js ecosystem
- Reduces file proliferation (3 new files avoided)

**Alternatives Considered**:
- **Alternative A**: Separate schema file per framework
  - **Rejected**: Creates unnecessary file proliferation. Would need 3 new files for ~200 lines of code total.
- **Alternative B**: Create `frameworks_schema.py` for all framework tables (ORM, job queues, etc.)
  - **Rejected**: `frameworks_schema.py` already exists for cross-language patterns (ORM, API routing). Language-specific frameworks belong in language-specific schema files.

**Trade-offs**:
- ✅ Single file for all Node.js patterns (easier navigation)
- ✅ Consistent with existing architecture
- ❌ `node_schema.py` becomes larger (but still manageable)

---

### Decision 2: Sequelize Associations in Separate Table

**What**: Store Sequelize associations (hasMany, belongsTo, etc.) in separate `sequelize_associations` table rather than JSON column in `sequelize_models` table.

**Why**:
- **Normalization**: One model can have multiple associations (one-to-many relationship). Separate table is normalized form.
- **Querying**: SQL queries like "find all models with hasMany relationship" are simple with separate table (`SELECT * FROM sequelize_associations WHERE association_type = 'hasMany'`), complex with JSON column.
- **Taint Tracking**: Taint analyzer can efficiently track data flows through ORM relationships by joining `sequelize_associations` with `symbols` and `function_calls`.
- **Graph Analysis**: Dependency graph of models requires separate table for efficient graph queries.

**Alternatives Considered**:
- **Alternative A**: JSON column `associations` in `sequelize_models` table
  - **Rejected**: Violates database normalization. Makes SQL queries complex (requires JSON extraction functions). Poor performance for graph queries.
- **Alternative B**: Store each association type (hasMany, belongsTo) in separate tables
  - **Rejected**: Over-normalization. Creates 4+ tables for what's essentially the same data structure (source, target, type, foreign_key). Query complexity increases.

**Trade-offs**:
- ✅ Normalized database design
- ✅ Efficient SQL queries
- ✅ Taint tracking through relationships
- ❌ Two tables instead of one (but this is correct design)

---

### Decision 3: Angular DI in Separate di_injections Table

**What**: Store Angular dependency injection in separate `di_injections` table rather than JSON column in `angular_components` or `angular_services` tables.

**Why**:
- **Cross-Cutting**: Components, services, guards, pipes, and modules all inject dependencies. Separate table captures all injection points in one place.
- **Taint Tracking**: Taint analyzer needs to track "tainted data flows from ServiceA to ComponentB via DI". Separate table enables JOIN queries: `taint_sources → symbols → di_injections → symbols → taint_sinks`.
- **Dependency Graph**: Visualize "what services does ComponentX inject?" and "what components inject ServiceY?" requires efficient queries on injection relationships.

**Alternatives Considered**:
- **Alternative A**: JSON column `injected_services` in each Angular table (components, services, guards)
  - **Rejected**: Data duplication (injection data stored in 4 different tables). Complex queries require UNION across all tables.
- **Alternative B**: Store injections as TEXT list in single column
  - **Rejected**: Can't track injection type (constructor vs property) or service types. Poor queryability.

**Trade-offs**:
- ✅ Single source of truth for all DI
- ✅ Efficient taint tracking queries
- ✅ Dependency graph queries
- ❌ Extra table (but necessary for cross-cutting concern)

---

### Decision 4: Python Extraction Functions in python_impl.py (Not Separate Modules)

**What**: Implement all 10 Python extraction functions (`extract_marshmallow_schemas`, `extract_wtforms_forms`, `extract_celery_tasks`, etc.) in existing `python_impl.py` file.

**Why**:
- Consistency with existing pattern (all Python extraction in `python_impl.py`: `extract_sqlalchemy_definitions`, `extract_django_definitions`, `extract_pydantic_validators`)
- File size remains manageable (1594 lines → ~2400 lines, acceptable for implementation file)
- Single import point for Python extractor (`from python_impl import extract_*`)

**Alternatives Considered**:
- **Alternative A**: Separate file per framework (marshmallow_impl.py, wtforms_impl.py, celery_impl.py)
  - **Rejected**: Inconsistent with existing architecture. Would require refactoring all existing extraction functions to separate files (breaking change).
- **Alternative B**: Split by extraction type (orm_impl.py, validation_impl.py, testing_impl.py)
  - **Rejected**: Violates single responsibility (one file per framework domain). Difficult to navigate (where is Celery? Is it in async_impl.py or task_impl.py?).

**Trade-offs**:
- ✅ Consistent with existing codebase
- ✅ Single import point
- ❌ Larger file (but still under 2500-line threshold for maintainability)

---

### Decision 5: Marshmallow Extraction via AST Class Inheritance

**What**: Extract Marshmallow schemas by traversing AST to find classes extending `Schema`, then extract fields from class body and `Meta` inner class.

**Why**:
- **Correctness**: Only classes extending `Schema` are valid Marshmallow schemas. AST traversal ensures 100% accuracy.
- **No False Positives**: Regex would match `class UserSchema:` (no inheritance) or `# class UserSchema(Schema)` (comment). AST is ground truth.
- **Meta Class Support**: Marshmallow schemas can define fields in `Meta.fields` or as class attributes. AST allows checking both locations.

**Example Pattern**:
```python
class UserSchema(Schema):
    class Meta:
        fields = ('id', 'username', 'email')

    password = fields.String(load_only=True)
```

**Extraction Strategy**:
1. Find classes with base `Schema` (via `any(base.id == 'Schema' for base in node.bases)`)
2. Check for `Meta` inner class (`any(isinstance(n, ast.ClassDef) and n.name == 'Meta' for n in node.body)`)
3. Extract `Meta.fields` if present
4. Extract field assignments from class body (`fields.String()`, `fields.Integer()`, etc.)

**Alternatives Considered**:
- **Alternative A**: Regex pattern matching
  - **Rejected**: ABSOLUTE PROHIBITION on regex fallbacks (CLAUDE.md). Regex would produce false positives.
- **Alternative B**: Import checking only (detect `from marshmallow import Schema`)
  - **Rejected**: Import doesn't mean schema is defined. False positives on files that only import Schema for type hints.

**Trade-offs**:
- ✅ 100% accuracy (no false positives)
- ✅ Handles both Meta.fields and class attribute patterns
- ✅ Complies with ABSOLUTE PROHIBITION on regex
- ❌ More complex code than regex (but correctness > simplicity)

---

### Decision 6: Celery Task Extraction via Decorator Detection

**What**: Extract Celery tasks by finding functions with `@task` or `@app.task` decorators, then extract task options from decorator arguments.

**Why**:
- **Decorator Contract**: Celery tasks are ALWAYS defined with `@task` or `@app.task` decorator. No decorator = not a task.
- **Option Extraction**: Decorator arguments (`bind=True`, `max_retries=3`) are critical for security analysis (e.g., "task with unlimited retries = DoS risk").

**Example Patterns**:
```python
# Pattern 1: Module-level task
@app.task
def send_email(to, subject, body):
    ...

# Pattern 2: Task with options
@app.task(bind=True, max_retries=3, rate_limit='10/m')
def process_upload(self, file_id):
    ...

# Pattern 3: Imported task decorator
from celery import task

@task
def background_job():
    ...
```

**Extraction Strategy**:
1. Find functions with decorators (`any(isinstance(d, ast.Name) and d.id in ['task'] for d in node.decorator_list)`)
2. Check for `@app.task` pattern (`ast.Attribute` with attr='task'`)
3. Extract decorator arguments (keywords: `bind`, `max_retries`, `rate_limit`)
4. Extract task name (function name)

**Alternatives Considered**:
- **Alternative A**: Function name pattern matching (functions starting with `task_`)
  - **Rejected**: Not a Celery convention. False positives on non-Celery functions.
- **Alternative B**: Call site detection (find `.delay()` and `.apply_async()` calls)
  - **Rejected**: Call sites don't define tasks, they invoke them. Need decorator to find task definition.

**Trade-offs**:
- ✅ 100% accuracy (decorator = task)
- ✅ Extracts task options for security analysis
- ✅ Handles all Celery decorator patterns
- ❌ Requires AST traversal (but necessary for correctness)

---

### Decision 7: BullMQ Queue Extraction via Constructor Detection

**What**: Extract BullMQ queues by finding `new Queue(...)` calls in JavaScript code, extract queue name from first argument.

**Why**:
- **Constructor Contract**: BullMQ queues are ALWAYS instantiated with `new Queue(name, options)`. Constructor call = queue definition.
- **Name as First Arg**: Queue name is always first argument. Easy to extract from AST.

**Example Patterns**:
```javascript
// Pattern 1: String literal queue name
const emailQueue = new Queue('emailQueue', { connection: redisConnection });

// Pattern 2: Variable queue name (dynamic)
const queueName = process.env.QUEUE_NAME;
const queue = new Queue(queueName, options);

// Pattern 3: Imported Queue class
import { Queue } from 'bullmq';
const queue = new Queue('notifications');
```

**Extraction Strategy**:
1. Find `new Queue(...)` calls in function_call_args (callee_function='Queue', argument_index=0)
2. Extract queue name from first argument (argument_expr)
3. Handle string literals directly, mark variables as `is_dynamic=True`
4. Extract redis_config from second argument (if present)

**Alternatives Considered**:
- **Alternative A**: Variable assignment tracking (track `const emailQueue = ...`)
  - **Rejected**: Variable name != queue name. Queue name is the STRING argument, not the variable name.
- **Alternative B**: Import detection only
  - **Rejected**: Import doesn't mean queue is instantiated. Need constructor call to confirm queue exists.

**Trade-offs**:
- ✅ Accurate queue detection
- ✅ Handles both literal and dynamic queue names
- ✅ Extracts configuration for taint analysis
- ❌ Dynamic queue names require variable tracking (future enhancement)

---

## Risks / Trade-offs

### Risk 1: Database Size Increase

**Risk**: Adding 9 new tables with framework data could increase database size significantly.

**Mitigation**:
- Estimated increase: +5-10% (based on typical project having ~100 Sequelize models, ~10 BullMQ queues, ~50 Angular components)
- Database is regenerated fresh every run - no accumulation over time
- SQLite handles 100k+ rows efficiently

**Measurement**: Benchmark database size before/after on plant project (765 files)

**Fallback**: If database size becomes problematic (>500MB), add compression or per-framework extraction flags

---

### Risk 2: Indexing Time Increase

**Risk**: Adding 10 new Python extraction functions could slow down indexing.

**Mitigation**:
- Estimated increase: +3-5% (based on AST already being parsed, extraction is cheap)
- Extraction functions are opt-in (only run if imports detected)
- Parallel file processing already exists (batch extraction)

**Measurement**: Benchmark indexing time before/after on TheAuditor project (765 files)

**Acceptable Threshold**: Up to +10% indexing time is acceptable for complete framework coverage

**Fallback**: If indexing time becomes problematic (>30 seconds for 1000 files), optimize extraction functions or add caching

---

### Risk 3: False Positives in Angular Extraction

**Risk**: `angular_extractors.js` uses naming conventions (@Component = class name includes "Component") rather than true decorator AST parsing. Could produce false positives.

**Mitigation**:
- Current implementation checks for Angular imports (`@angular/core`) before extraction
- Path filtering excludes `node_modules/` (already implemented in framework_extractors.js)
- Test fixtures will verify accuracy on real Angular projects

**Known Limitation**: Acknowledged in `angular_extractors.js:16-20`:
```javascript
// KNOWN LIMITATIONS:
// - Uses naming conventions (@Component = class name includes "Component")
//   rather than AST decorator detection
// - Will produce false positives for non-Angular classes with Angular-style naming
```

**Long-term Solution**: Implement proper TypeScript decorator AST parsing (requires tree-sitter-typescript upgrade)

**Acceptable Trade-off**: 5-10% false positive rate acceptable for Phase 1. Proper decorator parsing in Phase 2.

---

### Risk 4: Silent Failures in Python Extraction

**Risk**: Python extraction functions are called but if they fail (AttributeError, TypeError), error might be silently caught.

**Mitigation**:
- Wrap extraction calls in try/except with explicit logging:
  ```python
  try:
      celery_tasks = python_impl.extract_celery_tasks(tree, self.ast_parser)
      if celery_tasks:
          result['python_celery_tasks'].extend(celery_tasks)
  except Exception as e:
      logger.warning(f"Celery task extraction failed: {e}")
  ```
- Unit tests verify extraction functions work on valid input
- Integration tests verify extraction functions don't crash on malformed input

**Monitoring**: Add extraction counts to indexer summary output (`[Indexer] Celery tasks: 5, Marshmallow schemas: 3`)

---

### Risk 5: Schema Validation Failures

**Risk**: New tables might not match schema contract (missing indexes, wrong column types).

**Mitigation**:
- Use `validate_all_tables()` from `schema.py` to verify schema matches database
- Run validation in CI/CD before merging
- Add schema version bump if needed

**Test**:
```python
from theauditor.indexer.schema import validate_all_tables
import sqlite3

conn = sqlite3.connect('.pf/repo_index.db')
cursor = conn.cursor()
mismatches = validate_all_tables(cursor)
assert len(mismatches) == 0, f"Schema mismatches: {mismatches}"
```

---

## Migration Plan

### Phase 1: Node.js Integration (Days 1-2)

**Steps**:
1. Add 9 tables to `node_schema.py`
2. Update `javascript.py` to handle framework data
3. Update `indexer/__init__.py` to store framework data
4. Run tests on TheAuditor project
5. Run tests on plant project (production Node.js project)

**Rollback**: If Phase 1 fails, revert commits. Database is regenerated fresh every run - no data loss.

**Success Criteria**:
- ✅ `aud index` on plant project extracts Sequelize models
- ✅ `aud index` on plant project extracts BullMQ queues
- ✅ No regressions in React/Vue extraction

---

### Phase 2: Python Extraction (Days 3-5)

**Steps**:
1. Implement 10 extraction functions in `python_impl.py`
2. Run tests on TheAuditor project (has pytest tests)
3. Create test fixtures for Marshmallow, WTForms, Celery
4. Run full test suite

**Rollback**: If Phase 2 fails, revert Python extraction commits. Node.js integration (Phase 1) remains functional.

**Success Criteria**:
- ✅ `aud index` on project with Marshmallow extracts schemas
- ✅ `aud index` on project with Celery extracts tasks
- ✅ No regressions in SQLAlchemy/Django/Pydantic extraction

---

### Phase 3: Testing & Validation (Days 6-7)

**Steps**:
1. Create comprehensive test fixtures
2. Run full test suite (`pytest tests/`)
3. Run `aud full --offline` on TheAuditor, plant, PlantFlow
4. Verify `aud blueprint`, `aud taint-analyze`, `aud planning` work with new data
5. Check database size and indexing time

**Success Criteria**:
- ✅ All tests pass
- ✅ Database size increase < 15%
- ✅ Indexing time increase < 10%
- ✅ Downstream consumers work correctly

---

### Phase 4: Documentation & Deployment (Days 8-9)

**Steps**:
1. Update README.md with supported frameworks
2. Update EXTRACTION_GAPS.md (remove completed frameworks)
3. Create specs/framework-extraction/spec.md
4. Update CHANGELOG.md
5. Bump version to 1.3.0-RC2
6. Create Git commit and push

**Success Criteria**:
- ✅ Documentation updated
- ✅ OpenSpec validation passes (`openspec validate add-framework-extraction-parity --strict`)
- ✅ Ready for merge to main branch

---

## Open Questions

1. **Q**: Should BullMQ worker extraction include processor file content or just file path?
   - **A**: Just file path. Processor content can be large and is already captured in symbols/functions tables.

2. **Q**: Should Angular DI injection track injection token (for providers with `useValue`, `useFactory`)?
   - **A**: Not in Phase 1. Track class-to-class injection only. Token-based injection in Phase 2.

3. **Q**: Should Celery task extraction include task signature (args, kwargs, returns)?
   - **A**: Not in Phase 1. Signature already captured in symbols/functions tables. Phase 1 focuses on task metadata (bind, max_retries, etc.).

4. **Q**: Should pytest fixture extraction include fixture dependencies (fixtures that depend on other fixtures)?
   - **A**: Not in Phase 1. Dependency tracking requires parameter analysis. Phase 1 focuses on fixture metadata (scope, autouse).

5. **Q**: Should Marshmallow schema extraction include nested schemas (Schema with Nested() fields)?
   - **A**: Yes, in `marshmallow_fields` table. Store `field_type='Nested'` and `nested_schema_name` in field record.

---

## Success Metrics

**Quantitative**:
- 9 new Node.js tables created
- 10 new Python extraction functions implemented
- All 107 tasks completed
- 0 regressions in existing tests
- Database size increase < 15%
- Indexing time increase < 10%

**Qualitative**:
- `aud blueprint` shows framework patterns on production projects
- `aud taint-analyze` tracks taint through ORM/job queues/DI
- `aud planning` supports framework migrations
- User feedback: "TheAuditor now understands my project's architecture"

---

## Related Work

**Complements**:
- `python-extraction-phase2-modular-architecture` - Refactors Python extraction architecture
- `add-graphql-execution-graph-huge-task` - Adds GraphQL extraction

**Distinct From**:
- `pythonparity` ticket - Systematically maps entire Python ecosystem. This change is laser-focused on closing extractor-schema gaps.

**Enables**:
- Future Phase 3 frameworks (Zustand, React Query, Material-UI, etc.)
- Taint tracking through framework-specific patterns
- Business logic validation in `aud context`

---

**Status**: Design complete. Awaiting approval to proceed with implementation.
