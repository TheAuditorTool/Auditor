# Proposal: Add Python Extraction Parity with JavaScript/TypeScript

## Why

TheAuditor's Python extraction is 75-85% behind JavaScript/TypeScript extraction capabilities, creating a critical asymmetry that undermines the tool's value proposition as a language-agnostic SAST platform. This gap is not an opinion or estimation - it is **verified by code analysis** (see `PARITY_AUDIT_VERIFIED.md` in this directory).

###

 Evidence of Gap

1. **Type Extraction Gap (Resolved in code, docs pending)**: Python extraction now populates 4,321 rows in `type_annotations` (aud full --offline run on 2025-10-28) matching parameter and return hints, reducing the original 0-row gap against TypeScript. Documentation/spec alignment was outstanding before this update.

2. **Framework Table Gap (Mostly closed)**: New Python-specific tables (`python_orm_models`, `python_orm_fields`, `python_routes`, `python_blueprints`, `python_validators`) are live and flushed via `DatabaseManager`. JavaScript still has broader coverage (React/Vue tables, etc.), but Python frameworks now have dedicated storage instead of relying solely on generic tables.

3. **Code Infrastructure Gap**: JavaScript extraction still sits at ~7,5k lines across JS+TS, while Python extraction has grown to ~2,7k lines after the recent parity work. The gap is smaller (~2.7x) but semantic tooling parity remains out of reach without a dedicated Python type engine.

4. **Architectural Gap**: JavaScript uses TypeScript Compiler API (semantic analysis with type inference, scope resolution, cross-file symbol resolution). Python uses ast module (syntax-only parsing with no type awareness).

### Real-World Impact

- **Type hints surfaced**: Function and attribute annotations now flow into `type_annotations`, unlocking richer symbol metadata for Python parity customers.
- **Framework coverage**: Flask/FastAPI routes, SQLAlchemy models, Pydantic validators, and Django relationships are captured with dedicated tables, enabling downstream analyzers to query Python frameworks similarly to JavaScript counterparts.
- **Remaining gaps**: Relationship extraction still relies on heuristics for detailed `back_populates`/`backref` semantics, limiting deeper data-flow accuracy.
- **Operational considerations**: Import resolution populates `resolved_imports`, improving cross-file context, but semantic analysis (inference, type narrowing) still trails the TypeScript compiler integration.

### Current Status (2025-10-28)

- ✅ Type annotations populate `type_annotations` for Python parameters, returns, and class/module attributes.
- ✅ Framework tables (`python_orm_models`, `python_orm_fields`, `python_routes`, `python_blueprints`, `python_validators`) are populated during indexing.
- ✅ `resolved_imports` mirrors JavaScript structure, enabling cross-file lookups.
- ✅ Memory cache preloads Python ORM/routes/validator tables so taint analysis sees the new data without disk round-trips.
- ✅ Taint propagation uses the preloaded metadata (`enhance_python_fk_taint` expands bindings such as `user.posts`, `post.tags`, `organization.users`).
- ✅ SQLAlchemy relationship metadata captures inverse `back_populates`/`backref` links with cascade heuristics (join semantics still heuristic).
- 🔄 Test coverage limited to purpose-built fixtures (`tests/fixtures/python/*.py`); broader real-world samples remain TODO.

### Why This Matters

TheAuditor is positioned as an "AI-centric SAST and code intelligence platform" that is language-agnostic. **This positioning is currently false for Python.** A Python project analyzed by TheAuditor receives dramatically inferior intelligence compared to a JavaScript project. This creates:

1. **Asymmetric value**: JavaScript projects get framework-aware taint analysis, Python projects get basic syntax parsing
2. **False confidence**: Users don't know what they're missing until they compare outputs
3. **Strategic liability**: Cannot credibly market as "language-agnostic" when one language is 75% behind

## What Changes

This proposal adds Python extraction features to achieve parity with JavaScript/TypeScript extraction. Changes are organized in **three phases** targeting different parity levels.

### Phase 1: Type System Parity (Critical Foundation)

**Goal**: Extract Python type hints to populate `type_annotations` table

**Status (2025-10-28)**: Implemented in core extraction pipeline; Python type hints now populate `type_annotations` and are consumed by downstream taint preprocessing.

**Changes**:
- `theauditor/ast_extractors/python_impl.py:29-57` - Add type annotation extraction to `extract_python_functions()`
  - Extract `arg.annotation` for each parameter (currently only extracts `arg.arg`)
  - Extract `node.returns` for function return type annotation
  - Extract `node.type_comment` for PEP 484 type comments
  - Handle Optional, Union, List, Dict, Tuple type constructs
  - Serialize type annotations to strings matching TypeScript format
- `theauditor/ast_extractors/python_impl.py:60-77` - Add type annotation extraction to `extract_python_classes()`
  - Extract class attribute annotations (`node.annotation`)
  - Extract base class types
- `theauditor/indexer/extractors/python.py:47-75` - Store type annotations in database
  - Map extracted type data to `type_annotations` table (already exists in schema)
  - Populate `symbol_name`, `type_annotation`, `return_type` columns
  - Set `is_generic`, `has_type_params` flags for generic types

**Database Impact**: Populates existing `type_annotations` table (no schema changes)

**Backward Compatibility**: Pure addition, no breaking changes

### Phase 2: Framework Support Parity (Flask, FastAPI, SQLAlchemy)

**Goal**: Add Python framework extraction matching JavaScript's React/Vue framework support

**Status (2025-10-28)**: Extraction and storage for SQLAlchemy, Django, Pydantic, Flask, and FastAPI are live; taint propagation consumes the ORM data, while richer relationship semantics remain follow-up work.

**Changes**:
- `theauditor/ast_extractors/python_impl.py` - Add new extraction functions:
  - `extract_sqlalchemy_models()` - Extract Model classes, relationships, foreign keys
  - `extract_pydantic_models()` - Extract BaseModel classes, field validators, FastAPI dependencies
  - `extract_flask_routes()` - Extract Flask route decorators with middleware/auth detection
  - `extract_fastapi_routes()` - Extract FastAPI route decorators with dependency injection tracking
- `theauditor/indexer/schema.py` - Add new Python framework tables (matching JavaScript framework tables):
  - `python_orm_models` - SQLAlchemy/Django model definitions
  - `python_orm_fields` - Model field definitions with types
  - `python_validators` - Pydantic validators and FastAPI dependencies
  - `python_routes` - Flask/FastAPI route definitions with metadata
  - `python_blueprints` - Flask Blueprint hierarchy
- `theauditor/indexer/extractors/python.py` - Store framework data in new tables

**Database Impact**: Adds 5 new tables for Python framework support

**Backward Compatibility**: Pure addition, no breaking changes

### Phase 3: Advanced Feature Parity (Import Resolution, ORM Relationships)

**Goal**: Add import resolution and ORM relationship graph to match JavaScript capabilities

**Status (2025-10-28)**: Import resolution, ORM extraction, and taint-engine consumption are in place; richer `back_populates`/`backref` handling remains open.

**Changes**:
- `theauditor/ast_extractors/python_impl.py` - Import path resolution:
  - Resolve relative imports to absolute module paths via `resolve_python_imports()`
  - Distinguish local modules vs third-party packages without site-packages lookups
  - Populate `resolved_imports` dict (structure mirrors JavaScript extractor)
- `theauditor/ast_extractors/python_impl.py` - ORM relationship extraction:
  - Capture SQLAlchemy `relationship()` calls (first positional target) and `ForeignKey` usage
  - Capture Django `ForeignKey`, `ManyToManyField`, `OneToOneField`
  - Store results in `python_orm_models`, `python_orm_fields`, and shared `orm_relationships`
  - Advanced metadata (`back_populates`, cascade semantics beyond Django CASCADE) deferred

**Database Impact**: Populates existing `orm_relationships` table and `resolved_imports` payload (no new tables required)

**Backward Compatibility**: Pure addition, no breaking changes

## Impact

### Affected Specs

- `specs/python-extraction/spec.md` now reflects the implemented Python parity work (updated in this pass).
- Additional cross-language specs (`type-extraction`, `framework-extraction`) remain optional future consolidation efforts.

### Affected Code

**Phase 1 (Type System)**:
- `theauditor/ast_extractors/python_impl.py` - ~200 lines added (type annotation extraction)
- `theauditor/indexer/extractors/python.py` - ~50 lines added (type annotation storage)
- Total: ~250 lines

**Phase 2 (Framework Support)**:
- `theauditor/ast_extractors/python_impl.py` - ~500 lines added (framework extraction functions)
- `theauditor/indexer/schema.py` - ~150 lines added (5 new tables)
- `theauditor/indexer/extractors/python.py` - ~200 lines added (framework storage)
- Total: ~850 lines

**Phase 3 (Advanced Features)**:
- `theauditor/ast_extractors/python_impl.py` - ~300 lines added (import resolution, ORM relationships)
- `theauditor/indexer/extractors/python.py` - ~100 lines added (storage logic)
- Total: ~400 lines

**Overall**: ~1,500 lines added across 3 phases (Python extraction grows from 1,615 lines to ~3,115 lines, still smaller than JavaScript's 7,514 lines but closing the gap to ~2.4x instead of 4.7x)

### Performance Impact

- **Indexing time**: Phase 1 adds ~5-10ms per Python file (type annotation extraction). Phase 2 adds ~10-15ms per Python file (framework detection). Phase 3 adds ~5-10ms per Python file (import resolution). **Total**: ~20-35ms per file, acceptable overhead.
- **Database size**: Phase 1 adds ~0 MB (uses existing table). Phase 2 adds ~5-10 MB for framework tables. Phase 3 adds ~2-5 MB for import/ORM data. **Total**: ~7-15 MB increase, negligible.
- **Query performance**: No regression expected. New tables are indexed appropriately.

### Benefits

**Quantifiable Improvements**:
- Python type annotation coverage: 0% → 100% (based on files with type hints)
- Python framework detection: 0 frameworks → 5 frameworks (Flask, FastAPI, SQLAlchemy, Pydantic, Django)
- Python database tables: 0 → 5+ framework-specific tables
- Python extraction infrastructure: 1,615 lines → ~3,115 lines (~93% increase, reduces gap from 4.7x to 2.4x)
- Parity score: 15-25% → 50-60% (Phase 1: +15%, Phase 2: +20%, Phase 3: +10%)

**Strategic Benefits**:
- **Credible positioning**: Can truthfully claim "language-agnostic SAST" when Python extraction is 50-60% of JavaScript (vs current 15-25%)
- **Python project adoption**: Python-heavy organizations can now use TheAuditor with confidence
- **Taint analysis accuracy**: Import resolution enables cross-file taint tracking for Python
- **Framework intelligence**: Flask/FastAPI/Django projects get framework-aware analysis matching React/Vue quality

### Downstream Effects

**Positive**:
- **Taint analyzer**: Can now track taint across Python imports (currently broken)
- **FCE (Focused Context Extraction)**: Produces richer context for Python projects
- **RCA (Root Cause Analysis)**: Can trace bugs through type-annotated functions
- **Rules engine**: Can write Python framework-specific rules (Flask auth, Pydantic validation, etc.)

**Neutral**:
- **Existing Python analysis**: Backward compatible, no breaking changes
- **JavaScript analysis**: Unaffected

**No Breaking Changes**: All changes are pure additions. Existing functionality remains unchanged.

## Implementation Approach

### Phased Rollout

**Why Phased?**: Each phase delivers value independently and can be deployed separately. Phased rollout reduces risk and allows incremental validation.

**Phase 1 Duration**: Can be completed in isolation. Lays foundation for Phases 2-3.
**Phase 2 Duration**: Builds on Phase 1. Framework extraction uses type annotations for better accuracy.
**Phase 3 Duration**: Builds on Phase 1-2. Import resolution and ORM relationships enhance framework analysis.

### Verification-First Implementation

Following teamsop.md SOP v4.20, each phase follows the verification workflow:

1. **Read existing code**: Document current behavior in verification.md
2. **Verify assumptions**: Test hypotheses about Python AST API, database schema, TypeScript patterns
3. **Implement changes**: Write code only after verification complete
4. **Post-implementation audit**: Re-read all modified files to confirm correctness
5. **Test validation**: Create comprehensive test fixtures and test cases
6. **OpenSpec validation**: Run `openspec validate --strict` before requesting approval

### Testing Strategy

**Test Fixtures**:
- `tests/fixtures/python/parity_sample.py` exercises combined type, route, validator, and ORM extraction paths (added with initial implementation).
- Additional focused fixtures for SQLAlchemy edge cases, Django ManyToMany, and import-resolution edge cases remain TODO.

**Test Cases** (one per feature):
- Type annotation extraction for functions, classes, parameters, return types
- Generic type handling (Optional, Union, List, Dict, Tuple)
- Flask route extraction with decorators and middleware
- FastAPI dependency injection tracking
- SQLAlchemy relationship graph construction
- Pydantic validator detection
- Import path resolution (relative, absolute, virtual environment)

**Regression Prevention**:
- `aud index` / `aud full --offline` runs confirm end-to-end indexing after each major change.
- Manual SQLite spot-checks (via `.venv/Scripts/python.exe -c ...`) validate table population.
- Performance benchmark: ensure indexing time increase stays <10% for representative repos.

### Rollback Plan

Each phase is independently reversible via git revert:
- **Phase 1**: Revert type annotation extraction commits (no schema changes to revert)
- **Phase 2**: Revert framework extraction commits + migrate/drop new tables
- **Phase 3**: Revert import/ORM commits (only affects existing tables)

No data migration needed - database is regenerated fresh on every `aud index`.

## Risk Assessment

### Technical Risks

**Risk 1: Python AST API complexity**
- **Likelihood**: Medium
- **Impact**: Low
- **Mitigation**: Python ast module is well-documented and stable. Type annotation extraction is straightforward (`arg.annotation`, `node.returns`). Verify with test fixtures before implementation.

**Risk 2: Database schema conflicts**
- **Likelihood**: Low
- **Impact**: Medium
- **Mitigation**: New tables use distinct names (`python_*` prefix). Type annotations use existing table. Schema validation catches conflicts before deployment.

**Risk 3: Performance regression**
- **Likelihood**: Low
- **Impact**: Low
- **Mitigation**: Type annotation extraction adds ~5-10ms per file (negligible). Framework detection adds ~10-15ms per file (acceptable). Benchmark before deployment.

**Risk 4: TypeScript parity maintainability**
- **Likelihood**: Medium
- **Impact**: Medium
- **Mitigation**: This proposal doesn't achieve full parity (75-85% gap → 40-50% gap). Future TypeScript improvements may widen gap again. Document known limitations clearly.

### Process Risks

**Risk 1: Scope creep**
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**: This proposal is already large (3 phases, ~1,500 lines). Stick to defined phases. Defer additional features to future proposals.

**Risk 2: Testing coverage gaps**
- **Likelihood**: Medium
- **Impact**: Medium
- **Mitigation**: Create comprehensive test fixtures BEFORE implementation. Follow teamsop.md SOP v4.20 verification-first approach.

### Acceptable Trade-offs

**Trade-off 1: Not achieving full parity**
- **Gap remaining**: Even after Phase 3, Python will be ~40-50% behind JavaScript (vs current 75-85%)
- **Why acceptable**: Full parity requires Python semantic analysis engine (equivalent to TypeScript Compiler API), which doesn't exist. Mypy/Pyright integration would take 6+ months and is out of scope.
- **Alternative**: Accept 40-50% gap as "good enough" for Python projects. Clearly document limitations.

**Trade-off 2: No CFG sophistication**
- **Gap**: Python CFG extraction remains basic compared to JavaScript's dedicated 27KB cfg_extractor.js
- **Why acceptable**: CFG parity is orthogonal to type/framework parity. Defer to future proposal.
- **Alternative**: Accept basic CFG for Python. Clearly document limitation.

**Trade-off 3: No React-equivalent complexity**
- **Gap**: Python frameworks (Flask/FastAPI) are simpler than React (no hook dependency arrays, no cleanup tracking)
- **Why acceptable**: Python frameworks don't have equivalent complexity. Extracting what exists is sufficient.
- **Alternative**: None needed - Python frameworks are inherently simpler.

## Dependencies

**External Dependencies**: None (no new library dependencies)

**Internal Dependencies**:
- **Phase 1**: Depends on existing `type_annotations` table in schema (already exists)
- **Phase 2**: Depends on Phase 1 (type annotations used for framework analysis)
- **Phase 3**: Depends on Phase 1-2 (import resolution enhances framework analysis)

**Blocking Issues**: None identified

## Success Criteria

**Phase 1 Success Criteria**:
- [ ] All Python files with type hints have type annotations extracted
- [ ] `type_annotations` table populated with Python types (currently 0 Python rows, 69 TypeScript rows)
- [ ] Type annotation format matches TypeScript format (consistent serialization)
- [ ] Generic types (Optional, Union, List, Dict) handled correctly
- [ ] Performance: <10ms per file overhead
- [ ] Test suite: 100% pass rate for type annotation tests

**Phase 2 Success Criteria**:
- [ ] Flask routes extracted with decorator detection and middleware/auth flags
- [ ] FastAPI routes extracted with dependency injection tracking
- [ ] SQLAlchemy models extracted with field definitions
- [ ] Pydantic models extracted with validator detection
- [ ] 5 new tables populated with framework data
- [ ] Performance: <15ms per file overhead
- [ ] Test suite: 100% pass rate for framework extraction tests

**Phase 3 Success Criteria**:
- [ ] Python imports resolved to absolute paths (relative imports, virtual environment packages)
- [ ] `resolved_imports` dict populated (matching JavaScript structure)
- [ ] SQLAlchemy relationships extracted to `orm_relationships` table
- [ ] Django relationships extracted to `orm_relationships` table
- [ ] ORM relationship graph enables taint analysis FK traversal
- [ ] Performance: <10ms per file overhead
- [ ] Test suite: 100% pass rate for import/ORM tests

**Overall Success Criteria**:
- [ ] Python extraction infrastructure grows from 1,615 lines to ~3,115 lines (~93% increase)
- [ ] Python parity increases from 15-25% to 50-60% (+35-45 percentage points)
- [ ] Python extraction gap reduces from 4.7x to ~2.4x (JavaScript 7,514 lines, Python 3,115 lines)
- [ ] All phases deployed to production
- [ ] PARITY_AUDIT_VERIFIED.md updated with post-implementation verification

## Notes

### Why This Can't Wait

The current gap (75-85% behind) is a **strategic liability**. Every Python project analyzed with TheAuditor gets inferior intelligence compared to JavaScript projects. This undermines TheAuditor's positioning as a language-agnostic platform.

### Why This Is Tractable

Python type hints are **already in the code**. We're not inventing new features - we're extracting what exists. The audit proved this with grep: `grep "def.*:.*->" theauditor/ast_parser.py` shows type hints everywhere, but `python_impl.py:54` ignores them entirely.

### Why Phased Approach

Each phase delivers independent value:
- **Phase 1**: Type annotations enable better taint analysis and intelligence
- **Phase 2**: Framework extraction enables Python-specific rules and security analysis
- **Phase 3**: Import resolution and ORM graphs complete the picture

If Phase 2 or 3 get blocked, Phase 1 still delivers massive value.

### Alignment with teamsop.md

This proposal follows SOP v4.20 principles:
- **Verification-first**: PARITY_AUDIT_VERIFIED.md contains comprehensive code-based verification
- **Evidence-based**: Every claim backed by code reference or database query
- **No assumptions**: Audit used zero trust in docs, only code and database queries
- **Exhaustive documentation**: This proposal includes context, rationale, risks, trade-offs, and success criteria

### Related Work

This proposal is foundational for future Python improvements:
- **Future**: Python CFG sophistication (dedicated extractor matching JavaScript's cfg_extractor.js)
- **Future**: Mypy/Pyright integration for semantic analysis (equivalent to TypeScript Compiler API)
- **Future**: Django-specific framework extraction (currently lumped into SQLAlchemy/ORM)
- **Future**: Python import style analysis (tree-shaking equivalent for Python)

These are explicitly out of scope for this proposal to maintain tractability.
