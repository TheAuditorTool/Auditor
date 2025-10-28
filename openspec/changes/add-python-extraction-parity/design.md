# Design: Python Extraction Parity with JavaScript/TypeScript

## Context

TheAuditor indexes codebases by parsing AST (Abstract Syntax Tree) to extract symbols, functions, calls, imports, type information, and framework-specific patterns. This extraction feeds into:
- **Taint Analysis**: Tracks data flow from sources (user input) to sinks (SQL queries, file I/O)
- **FCE (Focused Context Extraction)**: Builds LLM-optimized context for specific code areas
- **RCA (Root Cause Analysis)**: Traces bugs through call graphs and data flow
- **Rules Engine**: Runs security/quality rules on extracted metadata

### Current State

**JavaScript/TypeScript Extraction**:
- Uses TypeScript Compiler API for semantic analysis
- Extracts type annotations, type inference, generic types
- Supports React (hooks, components, dependencies) and Vue (lifecycle, directives, provide/inject)
- Tracks ORM relationships (Prisma, Sequelize, TypeORM)
- Resolves imports to absolute paths
- Tracks environment variable usage (`process.env`)
- 7,514 lines of extraction code across Python and JavaScript
- Populates 20 framework-specific tables

**Python Extraction (2025-10-28)**:
- Uses Python's built-in `ast` module for syntactic parsing, but now records function parameter/return annotations and class/module attribute annotations.
- Populates dedicated framework tables for SQLAlchemy/Django models, Flask/FastAPI routes, and Pydantic validators (`python_orm_models`, `python_orm_fields`, `python_routes`, `python_blueprints`, `python_validators`).
- Resolves imports to absolute paths and third-party package identifiers via `resolved_imports`.
- Records ORM relationships (SQLAlchemy + Django) with heuristic relationship types; `back_populates`/`backref` semantics remain TODO.
- Taint analyzer consumes the new Python ORM tables via `theauditor/taint/orm_utils.py` and `theauditor/taint/propagation.py`.
- ~2.7k lines of extraction code (Python) versus ~7.5k lines for JavaScript/TypeScript (~2.7x gap).

**Gap**: 75-85% behind JavaScript/TypeScript. This is verified by code analysis in `PARITY_AUDIT_VERIFIED.md`.

### Problem Statement

**Immediate Problem**: Relationship extraction still relies on heuristics for `back_populates`/`backref` metadata, and benchmark/test coverage has not been expanded beyond targeted fixtures.

**Strategic Problem**: Even with recent gains, Python parity trails JavaScript due to the lack of semantic typing (Mypy/Pyright integration). Continued iteration is required to sustain the "language-agnostic" claim.

**Architectural Problem**: Python uses syntactic parsing (`ast` module), JavaScript uses semantic analysis (TypeScript Compiler API). This gap cannot be fully closed without a Python semantic analysis engine (Mypy/Pyright integration), which is 6+ months of work and out of scope. This proposal accepts 40-50% remaining gap as "good enough."

## Goals / Non-Goals

### Goals

1. **Extract Python type annotations** to populate `type_annotations` table (Phase 1)
2. **Extract Python framework patterns** for Flask, FastAPI, SQLAlchemy, Pydantic (Phase 2)
3. **Resolve Python imports** to absolute paths and build relationship graph (Phase 3)
4. **Increase Python parity** from 15-25% to 50-60% (closing gap from 4.7x to 2.4x)
5. **Maintain backward compatibility** - no breaking changes to existing Python extraction
6. **Zero performance regression** - <35ms overhead per file across all 3 phases

### Implementation Status (2025-10-28)
- ✅ Phase 1 (type annotations) implemented and flowing into `type_annotations`.
- ✅ Phase 2 (framework extraction) implemented with new `python_*` tables and ORM relationship capture.
- ✅ Import resolution populates `resolved_imports` for Python files (Phase 3 core).
- ✅ SQLAlchemy relationship metadata now parses `back_populates` / `backref`, infers inverse relationship records, and flags cascade semantics (join conditions still heuristic).
- ✅ Memory cache loads Python ORM/routes/validator tables for taint preload.
- ✅ Taint analyzer integration with Python ORM tables is live (`enhance_python_fk_taint` expands bindings for models/relationships).
- 🔄 Targeted fixtures/tests beyond the bespoke parity samples remain outstanding (need broader Django/FastAPI coverage and performance baselines).

### Non-Goals

1. **Semantic type inference** - Python's `ast` module is syntactic only. Full inference requires Mypy/Pyright integration (out of scope).
2. **CFG sophistication parity** - JavaScript has dedicated 27KB cfg_extractor.js. Python CFG remains basic (defer to future proposal).
3. **Control flow constraint analysis** - Detecting `if lang === 'en'` constraints requires CFG-based constraint propagation (separate feature).
4. **Python import style analysis** - JavaScript has tree-shaking analysis via `import_styles` table. Python equivalent is low priority (defer).
5. **Full 100% parity** - Architectural gap (semantic vs syntactic) cannot be closed without major investment. Accept 40-50% remaining gap.
6. **Django-specific framework tables** - Django lumped into generic ORM tables in Phase 2. Dedicated Django extraction is future work.

## Decisions

### Decision 1: Phased Rollout (3 Phases)

**Chosen**: Implement in 3 independent phases: Type System → Framework Support → Advanced Features

**Rationale**:
- **Risk mitigation**: Each phase can be tested, validated, and deployed independently
- **Value delivery**: Phase 1 delivers immediate value (type annotations) without waiting for Phase 2-3
- **Rollback safety**: If Phase 2 fails, Phase 1 value is preserved
- **Resource flexibility**: Can pause between phases if priorities shift

**Alternative Considered**: Big Bang implementation (all changes at once)
- **Rejected**: Too risky. ~1,500 lines of code, 5 new tables, 100+ tasks. One bug blocks entire feature.

**Phase Boundaries**:
- **Phase 1**: Type annotations only (pure extraction enhancement, no schema changes)
- **Phase 2**: Framework extraction (adds 5 new tables, significant functionality)
- **Phase 3**: Import resolution + ORM relationships (completes the picture)

**Dependencies**:
- Phase 2 depends on Phase 1 (framework extraction uses type annotations for better accuracy)
- Phase 3 depends on Phase 1-2 (import resolution enhances framework analysis)

### Decision 2: Reuse Existing `type_annotations` Table (No Schema Change for Phase 1)

**Chosen**: Populate existing `type_annotations` table for Python types (same table used by JavaScript)

**Rationale**:
- **Table already exists** in `schema.py:1025-1049` with correct columns (file, line, symbol_name, type_annotation, return_type)
- **Zero migration needed** - database regenerated fresh on every `aud index`
- **Consistency** - Python and JavaScript types in same table, same format, enables unified queries
- **Fast deployment** - No schema approval needed for Phase 1

**Alternative Considered**: Create separate `python_type_annotations` table
- **Rejected**: Unnecessary duplication. Unified table allows cross-language type queries (e.g., find all functions returning `Promise<User>` or `Awaitable[User]`).

**Compatibility**:
- JavaScript populates: `symbol_name`, `type_annotation`, `return_type`, `is_any`, `is_unknown`, `is_generic`, `has_type_params`, `type_params`, `extends_type`
- Python will populate: `symbol_name`, `type_annotation`, `return_type` (Phase 1)
- Python will leave NULL: `is_any`, `is_unknown`, `is_generic`, `has_type_params`, `type_params`, `extends_type` (Phase 1 - basic extraction only)
- Future: Phase 2+ could detect generic types and populate `is_generic`, `has_type_params`

### Decision 3: Use `ast.unparse()` for Type Serialization

**Chosen**: Use Python 3.9+ `ast.unparse()` to convert AST type annotation nodes to strings

**Rationale**:
- **Built-in**: No external dependency
- **Accurate**: Official Python AST-to-code serializer
- **Handles complex types**: `List[Dict[str, Union[int, str]]]` → correct string representation
- **Matches source**: Preserves original type syntax (important for debugging)

**Alternative Considered**: Manual string construction (walk AST and build type string)
- **Rejected**: Error-prone, hard to maintain, doesn't handle edge cases (nested generics, type aliases, forward references)

**Fallback**: If Python <3.9 detected (unlikely for TheAuditor's target environment), use `ast.get_source_segment()` or fail gracefully with NULL

**Implementation**:
```python
def _get_type_annotation(node: Optional[ast.expr]) -> Optional[str]:
    if node is None:
        return None
    return ast.unparse(node) if hasattr(ast, 'unparse') else None
```

### Decision 4: Extract Both List and Dict Formats for Parameters

**Chosen**: Store parameter types as both list (`arg_types: ["int", "str"]`) and dict (`arg_annotations: {"x": "int", "y": "str"}`)

**Rationale**:
- **List format**: Positional access (needed for call analysis - "2nd argument is type X")
- **Dict format**: Lookup by name (needed for type-aware taint analysis - "parameter `user_id` is type int")
- **Low overhead**: Minimal cost to store both formats
- **Backward compatibility**: Existing `"args"` list preserved

**Alternative Considered**: Store only dict format
- **Rejected**: Call analysis needs positional access. Reconstructing list from dict requires knowing parameter order (fragile).

**Storage**:
```python
{
    "name": "foo",
    "args": ["x", "y"],  # EXISTING - preserve for backward compat
    "arg_types": ["int", "str"],  # NEW - positional types
    "arg_annotations": {"x": "int", "y": "str"},  # NEW - named types
    "return_type": "bool"  # NEW
}
```

### Decision 5: Framework Tables Use `python_*` Prefix (Phase 2)

**Chosen**: New tables named `python_validators`, `python_routes`, `python_orm_models`, `python_orm_fields`, `python_blueprints`

**Rationale**:
- **Namespace isolation**: Avoids conflicts with existing tables
- **Clear ownership**: Obvious which tables are Python-specific
- **Parallel structure**: Mirrors JavaScript's framework tables (react_components, vue_hooks, etc.)
- **Query clarity**: `SELECT * FROM python_routes` vs `SELECT * FROM routes WHERE language='python'`

**Alternative Considered**: Generic `routes` table with `language` column
- **Rejected**: Different frameworks have different metadata. Flask routes have blueprints, FastAPI routes have dependencies. Unified table would have many NULL columns or require JSON blobs.

**Exception**: `orm_relationships` table reused for Python (already exists, language-agnostic schema).

### Decision 6: SQLAlchemy vs Django ORM - Unified Extraction

**Chosen**: Treat SQLAlchemy and Django ORM similarly - both extract to same tables (`python_orm_models`, `python_orm_fields`, `orm_relationships`)

**Rationale**:
- **Similar patterns**: Both use `Column()` for fields, both use `ForeignKey()`, both use class-based models
- **Unified analysis**: Rules engine can write single rule for "ORM model with unsanitized input" that applies to both
- **Lower complexity**: 1 extractor function instead of 2

**Differences Handled**:
- **Detection**: Check `Base` inheritance (SQLAlchemy) vs `models.Model` inheritance (Django)
- **Field syntax**: SQLAlchemy uses `Column(Integer)`, Django uses `IntegerField()` - both extractable
- **Relationships**: SQLAlchemy uses `relationship()`, Django uses `ForeignKey()` - both extractable

**Table Design**:
- `python_orm_models`: Stores model class (name, file, line, orm_type='sqlalchemy' or 'django')
- `python_orm_fields`: Stores fields (name, type, is_primary_key, is_foreign_key, foreign_key_target)
- `orm_relationships`: Stores relationships (source_model, target_model, relationship_type, as_name)

### Decision 7: Pydantic Validators - Dedicated Table

**Chosen**: Create `python_validators` table for Pydantic `@validator` and `@root_validator` decorators

**Rationale**:
- **Taint analysis integration**: Pydantic validators are sanitizers. Taint analyzer needs to know "field X has validation"
- **FastAPI dependency**: FastAPI uses Pydantic models for request validation. Tracking validators enables FastAPI-aware taint analysis.
- **Rules potential**: Can write rules like "Pydantic model has no email validator" or "Validator doesn't check for XSS"

**Extraction**:
- Detect `@validator('field_name')` decorators on methods within `BaseModel` classes
- Store: model_name, field_name, validator_method, validator_type (field/root/pre/post)
- Example: `@validator('email') def check_email(cls, v): ...` → store `('User', 'email', 'check_email', 'field')`

**Usage**: Taint analyzer can query "does this Pydantic field have validator?" to avoid false positives.

### Decision 8: Flask vs FastAPI Routes - Single Table

**Chosen**: Single `python_routes` table with `framework` column to distinguish Flask vs FastAPI

**Rationale**:
- **Similar enough**: Both have method, pattern, handler function
- **Shared columns**: 80% of columns are same (file, line, framework, method, pattern, handler_function, has_auth)
- **Framework-specific columns**: FastAPI dependencies stored as JSON text in `dependencies` column (NULL for Flask)
- **Simpler queries**: `SELECT * FROM python_routes WHERE framework='fastapi'` vs joining separate tables

**Differences Handled**:
- **Flask**: Decorators like `@app.route('/users', methods=['GET'])` → extract method from `methods` kwarg
- **FastAPI**: Decorators like `@app.get('/users')` → extract method from decorator name (`get` → `GET`)
- **Flask auth**: Look for `@login_required` above route → set `has_auth=True`
- **FastAPI deps**: Parse `Depends()` in function parameters → store as JSON list in `dependencies` column

### Decision 9: Import Resolution - Simplistic Approach (Phase 3)

**Chosen**: Use file path + import statement to calculate absolute module name (no sys.path traversal)

**Rationale**:
- **Good enough**: Resolves 80% of imports (relative imports within project)
- **No dependencies**: Doesn't require running Python interpreter or importing sys
- **Fast**: Simple string manipulation
- **Deterministic**: Always produces same result for same input

**Algorithm**:
```python
# File: myapp/views/user.py
# Import: from ..models import User

# Step 1: Get file's module path
file_path = "myapp/views/user.py"
file_module = "myapp.views.user"  # Convert path to module

# Step 2: Parse import
from_statement = "from ..models import User"
relative_part = ".."  # Go up 2 levels
import_module = "models"  # Import this module

# Step 3: Resolve relative to file's module
# file_module = "myapp.views.user"
# ".." goes to "myapp.views" then "myapp"
# Add ".models" → "myapp.models"
resolved_module = "myapp.models"

# Step 4: Store
resolved_imports['User'] = 'myapp/models.py'
```

**Limitations**:
- **Virtual environment packages**: Will resolve to package name only (e.g., `'requests'`), not full path to site-packages
- **Absolute imports**: Already resolved (e.g., `import requests` → `'requests'`)
- **Dynamic imports**: `importlib.import_module(variable)` → cannot resolve (skip)

**Trade-off**: Accept limitations. Full resolution requires sys.path traversal, which requires running Python and is fragile. Simplistic approach handles 80% of cases (project-internal imports) which is what taint analysis needs.

### Decision 10: No Fallback Logic (CRITICAL - Per CLAUDE.md)

**Chosen**: All extraction functions return empty lists if extraction fails. NO FALLBACKS.

**Rationale** (from CLAUDE.md ZERO FALLBACK POLICY):
- **Database is GENERATED FRESH** every `aud index` run. If data is missing, pipeline is broken and SHOULD crash.
- **Fallbacks hide bugs**: Silent failures compound, create inconsistent behavior
- **Hard failure forces fixes**: If type annotation extraction fails, fix the extractor, don't fall back to regex

**Forbidden Patterns**:
```python
# ❌ FORBIDDEN - Fallback to regex if AST extraction fails
try:
    types = extract_types_from_ast(node)
except Exception:
    types = re.findall(r'-> (\w+):', content)  # NO FALLBACK

# ❌ FORBIDDEN - Try multiple queries with fallback logic
cursor.execute("SELECT * FROM type_annotations WHERE name = ?", (normalized_name,))
result = cursor.fetchone()
if not result:  # NO FALLBACK QUERY
    cursor.execute("SELECT * FROM type_annotations WHERE name = ?", (original_name,))

# ✅ CORRECT - Single code path, hard fail if wrong
def extract_type_annotation(node):
    if node is None:
        return None  # Expected case - no annotation
    return ast.unparse(node)  # If this fails, let it crash
```

**Testing**: If extraction returns empty list, debug WHY, don't add fallback.

## Risks / Trade-offs

### Risk 1: Python <3.9 Compatibility (ast.unparse availability)

**Risk**: `ast.unparse()` added in Python 3.9. Older Python versions will fail.

**Likelihood**: Low (TheAuditor likely requires Python 3.9+ already, verify in pyproject.toml:10)

**Mitigation**:
- Check `pyproject.toml:10` for Python version requirement
- If Python 3.8 support needed, add fallback to `astor` library or manual serialization
- Add runtime check: `if hasattr(ast, 'unparse'): ...`

**Trade-off**: If Python 3.8 support is required, accept dependency on `astor` library OR implement manual type serialization (complex but no dependency).

### Risk 2: Generic Type Detection Complexity

**Risk**: Python generic types (`List[T]`, `Dict[K, V]`, `Optional[X]`) are complex AST structures. `ast.unparse()` should handle them, but edge cases may exist.

**Likelihood**: Medium (generic types are common in modern Python)

**Mitigation**:
- Comprehensive test fixtures covering all generic type patterns
- Test edge cases: nested generics (`List[Dict[str, Union[int, str]]]`), type aliases, forward references
- If `ast.unparse()` fails on specific pattern, add special case handling OR accept NULL for that case (don't crash)

**Trade-off**: Accept that some complex type annotations may serialize incorrectly or return NULL. Document known limitations in CLAUDE.md.

### Risk 3: Framework Detection False Positives

**Risk**: Detecting SQLAlchemy models by checking `Base` inheritance may false-positive on unrelated classes named `Base`.

**Likelihood**: Low (Python convention is to import as `from sqlalchemy.ext.declarative import declarative_base; Base = declarative_base()`)

**Mitigation**:
- Check import statements - if file imports `sqlalchemy`, increase confidence
- Check for `__tablename__` attribute (SQLAlchemy-specific)
- Accept some false positives - better to extract too much than too little

**Trade-off**: False positives (non-ORM classes detected as ORM) vs false negatives (ORM classes missed). Prefer false positives - user can filter, but can't recover missed data.

### Risk 4: Performance Regression

**Risk**: Adding ~1,500 lines of extraction code may slow down indexing.

**Likelihood**: Low (extraction is CPU-bound, not I/O-bound. Extra parsing is incremental.)

**Mitigation**:
- Benchmark indexing time before and after each phase
- Target: <10ms per file for Phase 1, <15ms for Phase 2, <10ms for Phase 3
- Total acceptable overhead: <35ms per file (on 1,000 file project = 35 seconds increase, acceptable)

**Trade-off**: Accept small performance regression for massive functionality gain. If overhead >50ms per file, optimize hot paths.

### Risk 5: Scope Creep into Full Semantic Analysis

**Risk**: Temptation to add type inference, control flow analysis, semantic checks (out of scope).

**Likelihood**: Medium (easy to over-engineer)

**Mitigation**:
- **Stick to proposal**: Phase 1 = extract annotations only, Phase 2 = extract framework patterns, Phase 3 = resolve imports
- **No inference**: Do NOT attempt to infer types for unannotated code
- **No CFG enhancement**: Do NOT enhance Python CFG to match JavaScript sophistication (defer to separate proposal)
- **No Mypy integration**: Do NOT integrate Mypy for semantic analysis (6+ months of work, out of scope)

**Trade-off**: Accept that Python will remain 40-50% behind JavaScript. This is acceptable - proposal goal is 50-60% parity, not 100%.

## Migration Plan

### Phase 1: Type System Parity

**Pre-Deployment**:
1. Verify `type_annotations` table exists and has correct schema (already exists)
2. Create test fixtures with comprehensive type annotations
3. Run `aud index` on test fixtures, verify type_annotations populated
4. Benchmark performance: index 100 Python files, measure time before/after

**Deployment**:
1. Merge Phase 1 code to main branch
2. Deploy to production
3. Run `aud index` on production codebases (database regenerated fresh, no migration needed)
4. Monitor for errors in logs

**Post-Deployment**:
1. Query `SELECT COUNT(*) FROM type_annotations WHERE file LIKE '%.py'` — current 2025-10-28 run returns 4,321 rows (baseline before parity work was 0).
2. Compare before/after: previous audits reported 0 Python type annotations; confirm counts remain ≥4,321 after deployment.
3. Check performance: indexing time increase <10%

**Rollback**:
- If critical bug found, revert commit via `git revert`
- Database regenerated on next `aud index`, no data migration needed

### Phase 2: Framework Support Parity

**Pre-Deployment**:
1. Schema changes: Add 5 new tables (`python_validators`, `python_routes`, `python_orm_models`, `python_orm_fields`, `python_blueprints`)
2. Test fixtures: Create Flask/FastAPI/SQLAlchemy/Pydantic sample apps
3. Verify extraction: Index fixtures, verify new tables populated

**Deployment**:
1. Merge Phase 2 code to main branch (includes schema changes)
2. Deploy to production
3. Run `aud index` (new tables auto-created, database regenerated fresh)

**Post-Deployment**:
1. Verify new tables exist: `SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'python_%'`
2. Verify tables populated: `SELECT COUNT(*) FROM python_routes` (should be >0 for Flask/FastAPI projects)
3. Check performance: indexing time increase <15ms per file

**Rollback**:
- Revert commit via `git revert`
- Drop new tables if needed (database regenerated fresh anyway)

### Phase 3: Advanced Feature Parity

**Pre-Deployment**:
1. Test import resolution: Verify relative imports resolve correctly
2. Test ORM relationships: Verify bidirectional relationships tracked

**Deployment**:
1. Merge Phase 3 code to main branch
2. Deploy to production
3. Run `aud index`

**Post-Deployment**:
1. Verify import resolution: Check `resolved_imports` dict populated for Python files
2. Verify ORM relationships: Check `orm_relationships` table has Python entries

**Rollback**:
- Revert commit via `git revert`

### Data Migration

**None required** - Database is regenerated fresh on every `aud index`. No data migration ever needed for TheAuditor.

## Open Questions

### Question 1: Should Django get dedicated extraction in Phase 2 or be deferred?

**Context**: Django ORM is similar to SQLAlchemy but has different syntax. Proposal lumps Django into generic ORM extraction. Should Django get dedicated extractor?

**Options**:
- **Option A**: Include Django in Phase 2 (adds complexity, increases scope)
- **Option B**: Defer Django to Phase 3 or future proposal (reduces risk, faster Phase 2 deployment)

**Recommendation**: Defer Django to Phase 3 or future proposal. Flask + FastAPI + SQLAlchemy + Pydantic is already large scope for Phase 2.

### Question 2: Should Python import style analysis be included?

**Context**: JavaScript has `import_styles` table tracking tree-shaking opportunities. Python equivalent would track `import *` vs selective imports.

**Options**:
- **Option A**: Include in Phase 3 (adds import style analysis)
- **Option B**: Defer to future proposal (reduces scope)

**Recommendation**: Defer to future proposal. Phase 3 already has import resolution + ORM relationships. Import style analysis is low priority.

### Question 3: Should Phase 1 attempt to detect generic types (List, Dict, Optional)?

**Context**: TypeScript extraction populates `is_generic`, `has_type_params`, `type_params` columns. Should Python do the same?

**Options**:
- **Option A**: Detect generic types in Phase 1 (check if type is `ast.Subscript`, extract `value` and `slice`)
- **Option B**: Leave NULL in Phase 1, add in Phase 2 (simpler Phase 1, faster deployment)

**Recommendation**: Detect generic types in Phase 1. Logic is straightforward (`isinstance(node, ast.Subscript)` → `is_generic=True`), adds value immediately.

### Question 4: Should Pydantic validators be treated as sanitizers in taint analysis?

**Context**: Pydantic `@validator` decorators validate/sanitize data. Should taint analyzer recognize them?

**Options**:
- **Option A**: Yes, add Pydantic validators to SANITIZERS dict (requires taint analyzer changes, out of scope for this proposal)
- **Option B**: No, just extract validators in Phase 2, taint integration is future work

**Recommendation**: Option B. This proposal focuses on extraction. Taint integration is separate proposal (similar to add-validation-framework-sanitizers proposal).

## Success Metrics

### Phase 1 Success Metrics

- [ ] `type_annotations` table populated with Python types (query confirms >0 rows)
- [ ] Python files with type hints have annotations extracted (spot check 10 files)
- [ ] Generic types handled correctly (List, Dict, Optional, Union tested)
- [ ] Performance overhead <10ms per file (benchmark confirms)
- [ ] No regression: existing tests pass (pytest 100% pass rate)

### Phase 2 Success Metrics

- [ ] 5 new tables created and populated (python_validators, python_routes, python_orm_models, python_orm_fields, python_blueprints)
- [ ] Flask routes extracted (spot check Flask project, verify routes in table)
- [ ] FastAPI routes extracted (spot check FastAPI project, verify routes in table)
- [ ] SQLAlchemy models extracted (spot check models, verify fields in table)
- [ ] Pydantic validators extracted (spot check models, verify validators in table)
- [ ] Performance overhead <15ms per file (benchmark confirms)
- [ ] No regression: existing tests pass

### Phase 3 Success Metrics

- [ ] Import resolution working (relative imports resolve to absolute paths)
- [ ] `resolved_imports` dict populated for Python files
- [ ] ORM relationships tracked (SQLAlchemy relationships in orm_relationships table)
- [ ] Performance overhead <10ms per file (benchmark confirms)
- [ ] No regression: existing tests pass

### Overall Success Metrics

- [ ] Python extraction infrastructure grows from 1,615 lines to ~3,115 lines (~93% increase)
- [ ] Python parity increases from 15-25% to 50-60% (+35-45 percentage points)
- [ ] Python extraction gap reduces from 4.7x to ~2.4x (JavaScript 7,514 lines, Python 3,115 lines)
- [ ] PARITY_AUDIT_VERIFIED.md updated with post-implementation results
- [ ] No production incidents related to Python extraction changes
- [ ] User feedback positive (if applicable - internal tool)

## Related Work

### Prerequisite Work

None - this proposal is self-contained.

### Follow-on Work

**After Phase 3 completion**, these proposals become possible:

1. **Pydantic Sanitizer Integration**: Add Pydantic validators to taint analyzer's SANITIZERS dict (similar to add-validation-framework-sanitizers)
2. **Python CFG Sophistication**: Enhance Python CFG extraction to match JavaScript's dedicated cfg_extractor.js
3. **Django-Specific Extraction**: Dedicated Django framework extraction (models, views, middleware, admin)
4. **Python Import Style Analysis**: Track `import *` vs selective imports for code quality analysis
5. **Mypy/Pyright Integration**: Full semantic analysis engine for Python (6+ months, major investment)

### Parallel Work

**Can be done concurrently with this proposal** (no conflicts):

- Taint analyzer enhancements (algorithm improvements, new sources/sinks)
- FCE/RCA improvements (prompt engineering, context selection)
- Rules engine expansion (new security rules, quality rules)
- JavaScript/TypeScript extraction enhancements (new framework support, better type inference)

### Blocking Work

None - no other work blocks this proposal.

## References

- **PARITY_AUDIT_VERIFIED.md**: Comprehensive code-based audit proving 75-85% gap
- **CLAUDE.md**: Project instructions including ZERO FALLBACK POLICY
- **teamsop.md**: SOP v4.20 verification-first workflow
- **openspec/AGENTS.md**: OpenSpec methodology
- **Python AST documentation**: https://docs.python.org/3/library/ast.html
- **PEP 484 (Type Hints)**: https://peps.python.org/pep-0484/
- **PEP 526 (Variable Annotations)**: https://peps.python.org/pep-0526/
- **TypeScript Compiler API** (for comparison): https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API
