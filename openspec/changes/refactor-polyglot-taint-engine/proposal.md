## Why

The taint analysis engine is currently "Express-locked" - it works well for Node.js Express projects but has hardcoded patterns that break for Python (Flask/Django/FastAPI) and miss Rust entirely. This proposal transforms the engine from **Hardcoded Heuristics** to **Data-Driven Discovery** - a true Polyglot Ferrari.

**The Core Problem:**
1. `sanitizer_util.py` has validation patterns hardcoded TWICE (lines 199-221 AND 233-246) - Express-specific: `validateBody`, `validateParams`, `safeParse`
2. `ifds_analyzer.py` checks `'controller' in file.lower()` (line 437) - Express naming convention
3. `ifds_analyzer.py` hardcodes `['req.body', 'req.params', 'req.query']` (line 589) - Express-only sources
4. `flow_resolver.py` hardcodes Express entry points (line 163) and exit points (line 334)
5. `orm_utils.py` lives in `taint/` but is ONLY used by `graph/strategies/python_orm.py` - wrong layer
6. Node.js ORMs (Sequelize, TypeORM, Prisma) are extracted to DB but have NO graph strategy - orphaned data

**Why This Matters:**
- Python projects using Flask/Django get zero middleware chain analysis
- Rust projects are completely ignored by taint analysis
- Express middleware patterns are assumed everywhere, causing false positives/negatives
- ORM relationship expansion only works for Python (SQLAlchemy/Django), not Sequelize/TypeORM

## What Changes

### Phase 1: Graph Foundation (Cleanup & Consolidation)

- **DELETE** `taint/orm_utils.py` - Logic moved to graph strategies, vestigial file
- **VERIFY** `graph/strategies/python_orm.py` contains full ORM relationship expansion
- **CREATE** `graph/strategies/node_orm.py` - New strategy for Sequelize/TypeORM/Prisma
- **VERIFY** strategies are called in correct order by `dfg_builder.py`

### Phase 2: Infrastructure (Traffic Laws & Identity)

- **MODIFY** `taint/core.py` TaintRegistry:
  - Add `get_source_patterns(language: str)` method
  - Add `get_sink_patterns(language: str)` method
  - Add `get_sanitizer_patterns(language: str)` method
  - Load patterns from `framework_safe_sinks` table
  - Load patterns from `validation_framework_usage` table

- **CREATE** `taint/type_resolver.py` - Lightweight Polyglot Identity Checker:
  - `is_same_type(node_a, node_b) -> bool` - Check if two nodes represent same Data Model
  - Reads node metadata populated by graph strategies
  - Used for ORM aliasing without direct graph edges

### Phase 3: Logic Refactor (Teaching the Driver)

- **MODIFY** `taint/ifds_analyzer.py`:
  - `_is_true_entry_point()`: Replace hardcoded patterns with registry lookup
  - `_access_paths_match()`: Replace `'controller' in file` with TypeResolver check
  - Remove hardcoded `request_patterns = ['req.body', ...]`

- **MODIFY** `taint/sanitizer_util.py`:
  - `__init__`: Load validation patterns from TaintRegistry (not hardcode)
  - `_path_goes_through_sanitizer()`: Use loaded patterns, delete duplicate list

- **MODIFY** `taint/flow_resolver.py`:
  - `_find_entry_points()`: Replace hardcoded Express patterns with registry
  - `_find_exit_points()`: Replace hardcoded `res.json()` patterns with registry

## Impact

### Affected Specs
- `pipeline` - Taint analysis phase changes
- `indexer` - Graph strategies added/modified

### Affected Code (Verified Locations)

| File | Lines | Change Type |
|------|-------|-------------|
| `taint/orm_utils.py` | ALL | DELETE |
| `taint/core.py` | 31-161 | MODIFY (TaintRegistry) |
| `taint/type_resolver.py` | NEW | CREATE |
| `taint/ifds_analyzer.py` | 437, 589-600 | MODIFY |
| `taint/sanitizer_util.py` | 199-221, 233-246 | MODIFY |
| `taint/flow_resolver.py` | 151-176, 334-369 | MODIFY |
| `graph/strategies/python_orm.py` | 19-20 | MODIFY (import path) |
| `graph/strategies/node_orm.py` | NEW | CREATE |

### Database Tables Used (Already Exist)

**Pattern Sources (for TaintRegistry):**
- `frameworks` - Framework definitions with language (node_schema.py:522-536)
- `framework_safe_sinks` - Safe sink patterns by framework (node_schema.py:538-548)
- `validation_framework_usage` - Validation sanitizers Zod/Joi/Yup (node_schema.py:550-566)
- `api_endpoints` - Entry points by framework (frameworks_schema.py)
- `express_middleware_chains` - Middleware chain order (node_schema.py:572-593)

**ORM Relationship Data (for Graph Strategies):**
- `sequelize_models` - Node.js Sequelize ORM models
- `sequelize_associations` - Sequelize relationships (hasMany, belongsTo)
- `sequelize_model_fields` - Sequelize field definitions
- `python_orm_models` - Python SQLAlchemy/Django models (columns: file, line, model_name, table_name, orm_type)
- `orm_relationships` - ORM relationships (NOT `python_orm_relationships`!)

**Full schema definitions: See design.md Appendix F-H**

### Known Bugs to Fix During This Refactor

**BUG: sanitizer_util.py:58 queries non-existent column**
```python
# Current code (BROKEN):
SELECT DISTINCT pattern FROM framework_safe_sinks  # 'pattern' doesn't exist!

# Should be:
SELECT DISTINCT sink_pattern FROM framework_safe_sinks
```
This bug is masked because the table is empty in most projects. Will be fixed in Phase 3.3 when we refactor to use TaintRegistry.

### Risk Assessment

**HIGH RISK**: This refactor touches the core taint analysis path. All changes must maintain backward compatibility for existing Express detection while adding Python/Rust support.

**Mitigation:**
1. Phase 1 (Graph) can be verified independently with `aud graph build`
2. Phase 2 (Infrastructure) adds new code paths without breaking existing
3. Phase 3 (Refactor) should have unit tests before/after comparison

### Breaking Changes
- **NONE** - All changes are additive or replace hardcoded values with database-driven equivalents
- Existing Express detection continues to work (patterns move from code to DB)
