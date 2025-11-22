# Pre-Implementation Verification: Schema Validation System

**Change ID**: `schema-validation-system`
**Lead Coder**: Claude Opus AI
**Architect**: Human (Awaiting Approval)
**Lead Auditor**: Gemini AI (Will Review Post-Implementation)
**Date**: 2025-01-03
**Protocol**: SOP v4.20

---

## Phase 0: Automated Project Onboarding

**Status**: ✅ **COMPLETE**

### Project Context Synthesis

**TheAuditor**: Offline-first SAST tool written in Python 3.11+. Database-driven architecture with schema-first design. Current state:
- 154 database tables across 8 schema modules
- Auto-generated accessor classes for memory cache
- No validation system to ensure generated code stays fresh
- **CRITICAL ISSUE**: Generated code has 125 classes but schema defines 154 tables (29 missing)

**Technology Stack**:
- Python 3.11+ with Click CLI framework
- SQLite3 for database (repo_index.db + graphs.db)
- Schema-driven codegen system (theauditor/indexer/schemas/codegen.py)
- pytest for testing

**Awaiting prompt**: Ready for pre-implementation verification.

---

## 1. Verification Phase Report (Pre-Implementation)

### 1.1 Hypotheses & Verification

#### Hypothesis 1: Generated code is stale (125 classes vs 154 schema tables)
**Verification Method**: Direct file comparison
```bash
grep -c "^class.*Table:" theauditor/indexer/schemas/generated_accessors.py
wc -l < schema.py TABLES dict
```
**Result**: ✅ **CONFIRMED STALE**
- Generated accessors: 125 classes
- Schema tables: 154 tables
- **Gap**: 29 missing accessor classes

**Evidence**: Agent audit found missing classes for:
- Angular (components, services, modules, guards)
- BullMQ (queues, workers)
- Sequelize (models, associations)
- Planning tables (newer additions)

#### Hypothesis 2: No validation mechanism exists
**Verification Method**: Search codebase for validation code
```bash
grep -r "validate_schema" theauditor/
grep -r "SchemaValidator" theauditor/
```
**Result**: ✅ **CONFIRMED - ZERO VALIDATION**
- No validator.py file exists
- No import-time checks
- No CLI commands for schema management
- No pytest tests for schema integrity

#### Hypothesis 3: No timestamp/version tracking in generated files
**Verification Method**: Read generated file headers
**Result**: ✅ **CONFIRMED - NO TRACKING**
- `generated_accessors.py` line 1: `# Auto-generated accessor classes from schema`
- No timestamp, no hash, no version indicator
- Impossible to determine when last generated

#### Hypothesis 4: Database manager methods match schema tables (1:1 parity)
**Verification Method**: Count add_* methods in database managers
```bash
grep -r "def add_" theauditor/indexer/database/ | wc -l
```
**Result**: ⚠️ **PARTIAL MISMATCH**
- Schema tables: 154
- Database add_* methods: 128
- **Gap**: 26 tables without explicit add_* methods
- **Explanation**: Junction tables and read-only result tables don't need add_* (populated indirectly)

#### Hypothesis 5: Codegen system is functional
**Verification Method**: Read codegen.py implementation
**Result**: ✅ **CONFIRMED FUNCTIONAL**
- File exists: `theauditor/indexer/schemas/codegen.py`
- Generates 4 files: types, accessors, cache, validators
- Uses SchemaCodeGenerator.generate_all_to_disk()
- **Issue**: Must be run manually (no automation)

#### Hypothesis 6: Schema modules are split by domain
**Verification Method**: List schema files
**Result**: ✅ **CONFIRMED - 8 DOMAIN MODULES**
```
core_schema.py (24 tables)
security_schema.py (5 tables)
frameworks_schema.py (5 tables)
python_schema.py (59 tables)
node_schema.py (26 tables)
infrastructure_schema.py (18 tables)
planning_schema.py (9 tables)
graphql_schema.py (8 tables)
```

#### Hypothesis 7: schema.py has table count assertion
**Verification Method**: Read schema.py line 78
**Result**: ✅ **CONFIRMED**
```python
assert len(TABLES) == 154, f"Schema contract violation: Expected 154 tables, got {len(TABLES)}"
```
**Purpose**: Runtime check that merged schema is correct

#### Hypothesis 8: No .schema_hash file exists
**Verification Method**: Check filesystem
**Result**: ✅ **CONFIRMED - NO HASH FILE**
- File does not exist
- No tracking mechanism for schema changes

### 1.2 Discrepancies Found

| Expected | Reality | Impact |
|----------|---------|--------|
| Generated code in sync | 29 classes missing | 🔴 **CRITICAL** - Accessors for 29 tables don't exist |
| Validation system exists | No validation at all | 🔴 **CRITICAL** - Can't detect staleness |
| Timestamp in generated files | No timestamp | 🟠 **HIGH** - No way to know freshness |
| 1:1 schema-database parity | 26 tables without add_* | 🟡 **MEDIUM** - Acceptable for junction tables |

---

## 2. Deep Root Cause Analysis

### Surface Symptom
- Architect has anxiety about generated code freshness
- No way to verify if codegen was run after schema changes
- 29 accessor classes are missing (stale generated code)

### Problem Chain Analysis

1. **Schema-driven refactor completed** (taint analysis, 77% code reduction)
   ↓
2. **Auto-generation system created** (codegen.py generates 4 files from schemas)
   ↓
3. **New tables added** (Angular, BullMQ, Sequelize, Planning - 29 tables)
   ↓
4. **Codegen NOT re-run** after adding new tables
   ↓
5. **Generated code became stale** (125 classes vs 154 schema tables)
   ↓
6. **No detection mechanism** to warn about staleness
   ↓
7. **Architect anxiety** - Can't trust the system

### Actual Root Cause
**Missing validation layer between schema definitions and generated code.**

The schema-driven architecture eliminated manual cache loaders (good!) but introduced a new failure mode: forgetting to regenerate code after schema changes. No automated checks catch this.

### Why This Happened (Historical Context)

**Design Decision**: Schema-driven codegen was prioritized for eliminating 40+ manual cache loaders (77% code reduction). Validation was deferred as "nice to have."

**Missing Safeguard**: No import-time, test-time, or CLI-time checks to verify generated code matches schemas.

**Fragile Workflow**: Developer must manually remember to run codegen after adding tables. Human memory = unreliable.

---

## 3. Proposed Solution Design

### 3.1 Three-Layer Defense System

**Layer 1: Import-Time Validation** (Fast, automatic)
- Runs when `theauditor.indexer.schemas` is imported
- Checks schema hash vs stored hash
- Checks generated file existence
- Development mode: Auto-regenerates if stale
- Production mode: Warns if stale
- **Performance**: < 50ms (SHA-256 hash + file checks)

**Layer 2: CLI Commands** (Manual control)
```bash
aud schema --check   # Validate integrity (dry-run)
aud schema --regen   # Force regeneration
```

**Layer 3: Test-Time Enforcement** (CI/CD safety)
- pytest fixture validates schema integrity
- Hard fail if stale (prevents bad merges)
- Runs in CI/CD pipeline

### 3.2 Hash-Based Staleness Detection

**Mechanism**: SHA-256 hash of schema structure
- Includes: table names, column names, column types, indexes
- Stored in: `.schema_hash` file (gitignored)
- Regenerated: After every codegen run
- Validated: On import, in tests, via CLI

**Example**:
```python
def compute_schema_hash(tables_dict):
    schema_data = {}
    for name, schema in sorted(tables_dict.items()):
        schema_data[name] = {
            'columns': [(c.name, c.type, c.nullable) for c in schema.columns],
            'indexes': sorted(schema.indexes) if schema.indexes else []
        }
    return hashlib.sha256(json.dumps(schema_data, sort_keys=True).encode()).hexdigest()
```

### 3.3 Auto-Regeneration Strategy

**Trigger**: Schema hash mismatch
**Action**:
- **Development mode** (git repo exists): Auto-regenerate with warning
- **Production mode** (pip installed): Hard fail with instructions
**Feedback**:
```
[SCHEMA] Schema changed since last generation
[SCHEMA] Auto-regenerating code... (development mode)
[SCHEMA] Regeneration complete (154 tables, 4 files)
```

---

## 4. Implementation Plan

### 4.1 Files to Create

1. **`theauditor/indexer/schemas/validator.py`** (~250 lines)
   - SchemaValidator class
   - Hash computation (SHA-256)
   - File existence checks
   - Database method verification
   - Auto-regeneration logic

2. **`theauditor/commands/schema.py`** (~80 lines)
   - CLI command group: `aud schema`
   - Subcommands: `--check`, `--regen`
   - Clear error messages

3. **`tests/test_schema_integrity.py`** (~100 lines)
   - Test: All tables have database methods
   - Test: Generated files exist
   - Test: Schema hash is current
   - Test: Table count assertion matches

4. **`theauditor/indexer/schemas/.schema_hash`** (gitignored)
   - SHA-256 hash of current schema structure
   - Generated during codegen

### 4.2 Files to Modify

1. **`theauditor/indexer/schemas/__init__.py`**
   - Add import-time validation hook
   - Check for THEAUDITOR_NO_VALIDATION env var
   - Auto-regenerate in development mode

2. **`theauditor/indexer/schemas/codegen.py`**
   - Add hash writing after generation
   - Add timestamp to generated file headers
   - Return success/failure status

3. **`theauditor/cli.py`**
   - Register `schema` command group

4. **`.gitignore`**
   - Add `.schema_hash` to gitignore

### 4.3 Implementation Sequence

**Phase 1: Immediate Fix (5 minutes)**
- Task 1.1: Run codegen to fix 29 missing classes
- Task 1.2: Verify 154 accessor classes generated

**Phase 2: Create Validator (20 minutes)**
- Task 2.1: Create validator.py with SchemaValidator class
- Task 2.2: Implement hash computation
- Task 2.3: Implement validation checks
- Task 2.4: Implement auto-regeneration logic

**Phase 3: Add CLI Commands (15 minutes)**
- Task 3.1: Create schema.py command module
- Task 3.2: Implement `aud schema --check`
- Task 3.3: Implement `aud schema --regen`
- Task 3.4: Register in cli.py

**Phase 4: Add Import Hook (10 minutes)**
- Task 4.1: Modify schemas/__init__.py
- Task 4.2: Add import-time validation
- Task 4.3: Add development mode detection
- Task 4.4: Add THEAUDITOR_NO_VALIDATION env var

**Phase 5: Add Tests (15 minutes)**
- Task 5.1: Create test_schema_integrity.py
- Task 5.2: Test table-method parity
- Task 5.3: Test generated file existence
- Task 5.4: Test schema hash validation

**Phase 6: Documentation (5 minutes)**
- Task 6.1: Update CLAUDE.md with validation workflow
- Task 6.2: Add .schema_hash to .gitignore

**Total Estimated Time**: 70 minutes

---

## 5. Edge Cases & Failure Modes

### Edge Case 1: Developer adds table but forgets database method
**Detection**: Validator checks for missing add_* methods
**Handling**: Warn but don't block (junction tables are valid)
**Message**: "Table X has no add_* method (may be intentional for junction tables)"

### Edge Case 2: Import fails due to validation error
**Detection**: Validation raises exception during import
**Handling**:
- Development: Auto-regenerate and continue
- Production: Hard fail with clear instructions
**Fallback**: THEAUDITOR_NO_VALIDATION=1 env var to bypass

### Edge Case 3: Schema changes during active development
**Detection**: Hash mismatch on next import
**Handling**: Auto-regenerate with warning in dev mode
**Performance**: 200-500ms one-time cost

### Edge Case 4: Codegen fails (syntax error in generated code)
**Detection**: Python import error after generation
**Handling**: Validator catches and reports
**Rollback**: Restore from backup or git revert

### Edge Case 5: Multiple developers modify schemas
**Detection**: Git merge conflicts in schema files
**Handling**: Standard git resolution, then run codegen
**CI**: Test suite catches stale code before merge

---

## 6. Testing Strategy

### Unit Tests (pytest)
```python
def test_all_tables_have_methods():
    """Every schema table must have database add_* method (or be junction)."""

def test_generated_files_exist():
    """All 4 generated files must exist."""

def test_schema_hash_current():
    """Schema hash must match generated code."""

def test_table_count_assertion():
    """len(TABLES) must match schema.py assertion."""
```

### Integration Tests
```python
def test_validator_detects_stale_code():
    """Validator catches hash mismatch."""

def test_auto_regeneration_works():
    """Development mode auto-regenerates."""

def test_cli_commands_work():
    """aud schema --check and --regen execute."""
```

### Manual Tests
1. Add new table to schema → Verify auto-regeneration
2. Delete generated file → Verify detection
3. Modify schema → Verify hash mismatch caught
4. Run in production mode → Verify hard fail with instructions

---

## 7. Rollback Plan

### If Validation System Fails
**Immediate Rollback**:
```bash
git revert HEAD  # Restore pre-validation state
```

**Fallback**:
```bash
export THEAUDITOR_NO_VALIDATION=1  # Disable validation
```

### If Codegen Fails
**Restore from Backup**:
```bash
cp theauditor/indexer/schemas/generated_*.py.backup theauditor/indexer/schemas/
```

**Or Git Restore**:
```bash
git restore theauditor/indexer/schemas/generated_*.py
```

---

## 8. Success Criteria

**Immediate Success** (Phase 1):
- [ ] Generated code has 154 accessor classes (not 125)
- [ ] All schema tables have corresponding generated classes

**Long-Term Success** (Phase 2-6):
- [ ] Import-time validation catches stale code
- [ ] CLI commands provide manual control
- [ ] Tests enforce integrity in CI/CD
- [ ] Architect has zero anxiety (system is self-checking)

**Measurable Outcomes**:
- [ ] Validation runs in < 50ms (acceptable overhead)
- [ ] Auto-regeneration works in development mode
- [ ] Test suite catches staleness before merge
- [ ] Clear error messages guide developers

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Import overhead > 50ms | Low | Medium | Optimize hash computation with caching |
| Validation breaks imports | Low | High | THEAUDITOR_NO_VALIDATION env var |
| Codegen produces bad code | Low | High | Post-gen validation + rollback plan |
| Developers bypass validation | Medium | Medium | Test suite enforces in CI/CD |
| Hash collisions | Very Low | Medium | SHA-256 has negligible collision risk |

**Overall Risk**: 🟢 **LOW** (with fallback mechanisms in place)

---

## 10. Confirmation & Authorization Request

### Verification Summary
- ✅ **Confirmed**: Generated code is stale (29 classes missing)
- ✅ **Confirmed**: No validation system exists
- ✅ **Confirmed**: No timestamp/hash tracking
- ✅ **Root Cause**: Missing validation layer in schema-driven architecture

### Proposed Solution Summary
- **Layer 1**: Import-time validation (auto-fix in dev)
- **Layer 2**: CLI commands (manual control)
- **Layer 3**: Test enforcement (CI/CD safety)
- **Mechanism**: SHA-256 hash-based staleness detection

### Implementation Summary
- **Immediate**: Regenerate to fix 29 missing classes (5 min)
- **Long-term**: Implement 3-layer validation (65 min)
- **Total Time**: 70 minutes
- **Files**: 4 new, 4 modified

### Confidence Level
**HIGH (95%)** - Proven pattern, clear failure mode, thorough testing strategy

---

## Authorization Required

**Architect (Human)**: Please review this pre-implementation plan and authorize one of:

**Option A**: ✅ **APPROVE** - Proceed with Phase 1-6 implementation
**Option B**: ✅ **APPROVE PHASE 1 ONLY** - Fix immediate issue (29 missing classes), defer validation system
**Option C**: 🔄 **REVISE** - Request changes to design or approach
**Option D**: ❌ **REJECT** - Do not proceed

**Lead Coder (Opus AI)**: Awaiting authorization before implementation.

**Protocol**: SOP v4.20 compliance confirmed. Prime Directive followed.
