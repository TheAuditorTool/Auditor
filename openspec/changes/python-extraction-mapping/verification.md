# Python Extraction Mapping: Verification Document (teamsop.md C-4.20 Format)

**Version**: 1.0
**Date**: 2025-11-01
**Status**: PRE-IMPLEMENTATION

---

## Prime Directive: Verify Before Acting

**Protocol**: Question Everything, Assume Nothing, Verify Everything.

Before implementing ANY phase of this proposal, the Coder MUST complete the Verification Phase. This document captures hypotheses about the current state and evidence from source code that confirms or refutes them.

---

## VERIFICATION PHASE (PRE-IMPLEMENTATION)

### Hypotheses & Verification

#### Hypothesis 1: Current walrus operator extraction = NONE
**Test**: Search for walrus-related code in extractors
**Verification Method**:
```bash
cd C:/Users/santa/Desktop/TheAuditor
.venv/Scripts/python.exe -c "
import os, re
found = False
for root, dirs, files in os.walk('theauditor/ast_extractors/python'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'walrus' in content.lower() or 'NamedExpr' in content:
                    print(f'Found in {path}')
                    found = True
if not found:
    print('NO walrus extraction found')
"
```
**Expected Result**: ❌ No walrus extraction found
**Actual Result**: [To be filled during verification]

#### Hypothesis 2: Current augmented assignment extraction = NONE
**Test**: Search for augmented assignment extraction
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import ast
# Check if AugAssign is handled in any extractor
import os
found = False
for root, dirs, files in os.walk('theauditor/ast_extractors/python'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'AugAssign' in content:
                    print(f'Found in {path}')
                    found = True
if not found:
    print('NO augmented assignment extraction found')
"
```
**Expected Result**: ❌ No augmented assignment extraction
**Actual Result**: [To be filled during verification]

#### Hypothesis 3: Current lambda function extraction = NONE
**Test**: Search for Lambda node handling
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import os
found = False
for root, dirs, files in os.walk('theauditor/ast_extractors/python'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'ast.Lambda' in content or 'isinstance(node, Lambda)' in content:
                    print(f'Found in {path}')
                    found = True
if not found:
    print('NO lambda extraction found')
"
```
**Expected Result**: ❌ No lambda extraction
**Actual Result**: [To be filled during verification]

#### Hypothesis 4: Current exception raising extraction = NONE
**Test**: Search for Raise node handling
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import os
found = False
for root, dirs, files in os.walk('theauditor/ast_extractors/python'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'ast.Raise' in content or 'isinstance(node, Raise)' in content:
                    print(f'Found in {path}')
                    found = True
if not found:
    print('NO exception raising extraction found')
"
```
**Expected Result**: ❌ No exception raising extraction
**Actual Result**: [To be filled during verification]

#### Hypothesis 5: Current Python table count = 59
**Test**: Count tables in python_schema.py
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import re
with open('theauditor/indexer/schemas/python_schema.py', 'r', encoding='utf-8') as f:
    content = f.read()
    # Count TableSchema definitions
    matches = re.findall(r'PYTHON_\w+\s*=\s*TableSchema', content)
    print(f'Found {len(matches)} Python tables')
    if len(matches) < 59:
        print('WARNING: Expected 59 tables')
    elif len(matches) > 59:
        print('WARNING: More than 59 tables found')
    else:
        print('CONFIRMED: 59 tables')
"
```
**Expected Result**: ✅ 59 tables
**Actual Result**: [To be filled during verification]

#### Hypothesis 6: Pydantic V2 validators NOT extracted
**Test**: Search for field_validator (V2 decorator)
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import os
found = False
for root, dirs, files in os.walk('theauditor/ast_extractors/python'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'field_validator' in content:  # V2 decorator
                    print(f'Found Pydantic V2 in {path}')
                    found = True
if not found:
    print('NO Pydantic V2 extraction found')
    print('Note: V1 @validator may exist, check separately')
"
```
**Expected Result**: ❌ No Pydantic V2 extraction (only V1 @validator exists)
**Actual Result**: [To be filled during verification]

#### Hypothesis 7: Django URL pattern extraction = NONE
**Test**: Search for Django URL extraction
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import os
found = False
for root, dirs, files in os.walk('theauditor/ast_extractors/python'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'urlpatterns' in content or 'django.*url' in content.lower():
                    print(f'Found Django URL extraction in {path}')
                    found = True
if not found:
    print('NO Django URL extraction found')
"
```
**Expected Result**: ❌ No Django URL extraction
**Actual Result**: [To be filled during verification]

#### Hypothesis 8: FastAPI response_model extraction = NONE
**Test**: Search for FastAPI response model extraction
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import os
found = False
for root, dirs, files in os.walk('theauditor/ast_extractors/python'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'response_model' in content:
                    print(f'Found FastAPI response_model in {path}')
                    found = True
if not found:
    print('NO FastAPI response_model extraction found')
"
```
**Expected Result**: ❌ No FastAPI response_model extraction
**Actual Result**: [To be filled during verification]

#### Hypothesis 9: SQLAlchemy cascade extraction = NONE
**Test**: Search for cascade extraction
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import os
found = False
for root, dirs, files in os.walk('theauditor/ast_extractors/python'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'cascade' in content and 'relationship' in content:
                    print(f'Found SQLAlchemy cascade in {path}')
                    found = True
if not found:
    print('NO SQLAlchemy cascade extraction found')
"
```
**Expected Result**: ❌ No cascade extraction (relationships extracted but not cascade details)
**Actual Result**: [To be filled during verification]

#### Hypothesis 10: Current extraction count on TheAuditor = ~7,761 records
**Test**: Query database for Python record count
**Verification Method**:
```bash
.venv/Scripts/python.exe -c "
import sqlite3, os
db_path = '.pf/repo_index.db'
if not os.path.exists(db_path):
    print('ERROR: Database not found. Run aud index first.')
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Count all python_* tables
    tables = c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'python_%'\").fetchall()
    total = 0
    for (table,) in tables:
        count = c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        if count > 0:
            print(f'{table}: {count}')
        total += count
    print(f'TOTAL: {total} Python records')
    conn.close()
"
```
**Expected Result**: ✅ ~7,761 Python records
**Actual Result**: [To be filled during verification]

---

### Discrepancies Found

**List any discrepancies between proposal assumptions and actual source code**:

1. [Example] If walrus operator extraction found but proposal assumes NONE
2. [Example] If table count is 60 not 59
3. [Example] If Pydantic V2 already partially extracted

[To be filled during verification]

---

### Verification Checklist (PRE-IMPLEMENTATION)

Before starting ANY implementation:

- [ ] Read all extractor modules in `theauditor/ast_extractors/python/`
- [ ] Read schema file `theauditor/indexer/schemas/python_schema.py`
- [ ] Read storage handlers `theauditor/indexer/storage.py`
- [ ] Read database writers `theauditor/indexer/database/python_database.py`
- [ ] Read orchestrator `theauditor/indexer/extractors/python.py`
- [ ] Count existing tables (expected: 59)
- [ ] Query database for baseline record count (expected: ~7,761)
- [ ] Verify all 10 hypotheses above
- [ ] Document any discrepancies
- [ ] Update proposal if reality differs from assumptions

---

## ROOT CAUSE ANALYSIS (WHY THE GAPS EXIST)

### Surface Symptom
Python extraction at 70% parity, JavaScript at 90% parity. ~100 patterns missing.

### Problem Chain Analysis

1. **Phase 2 (2024)**: Focused on foundational extraction (classes, functions, imports, ORM basics)
   - **Decision**: Build foundation first, defer advanced patterns
   - **Result**: 49 extractors, 34 tables, 40% parity

2. **Phase 3 (2025)**: Added Flask, Security, Django, Testing frameworks
   - **Decision**: Focus on OWASP Top 10 security patterns, add Flask ecosystem
   - **Result**: 75 extractors, 59 tables, 70% parity
   - **But**: Still missing core language patterns (walrus, lambdas, comprehensions)

3. **Gap Analysis (2025-11-01)**: Comprehensive audit revealed ~100 missing patterns
   - **Finding**: Core language gaps (no walrus, no lambdas, no comprehensions)
   - **Finding**: Framework gaps (no Django URLs, no FastAPI response models)
   - **Finding**: Validation gaps (no Pydantic V2, no Marshmallow hooks)

### Actual Root Cause

**Incremental scope creep management**: Each phase focused on specific categories (Phase 2: Foundation, Phase 3: Frameworks+Security) but deliberately deferred other patterns to control complexity. This was intentional, not a mistake.

### Why This Happened (Historical Context)

**Design Decision**: Phases were scoped conservatively to ensure completion. Each phase had 40-week estimates, and adding more patterns would have created unbounded work.

**Missing Safeguard**: No systematic gap analysis performed between Phase 2 → Phase 3. If gap analysis had been done earlier, Phase 3 could have included core language patterns (walrus, lambdas) instead of focusing entirely on frameworks.

---

## IMPLEMENTATION DETAILS & RATIONALE (PER PHASE)

### Phase 4: Core Language Completion

**Decision**: Implement core language patterns first (walrus, augmented, lambdas, comprehensions, exceptions)

**Reasoning**: These are foundational patterns used everywhere. Without them, data flow analysis is incomplete. Must come before framework-specific work.

**Alternative Considered**: Start with frameworks (Django, FastAPI)

**Rejected Because**: Core language patterns are dependencies for framework analysis. Example: Django views use lambdas, Flask uses comprehensions. Need core patterns first.

**Code Implementation**:
```python
# Phase 4: expression_extractors.py
def extract_walrus_assignments(tree: Dict, parser_self) -> List[Dict]:
    """Extract walrus operator (:=) patterns.

    Detects:
    - if (n := len(data)) > 10:
    - while (line := file.readline()):
    - [x for x in range(10) if (y := x*2) > 5]
    """
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.NamedExpr):
            results.append({
                'file': tree.get('file'),
                'line': node.lineno,
                'target': node.target.id if hasattr(node.target, 'id') else str(node.target),
                'value': ast.unparse(node.value),
                'context': _infer_context(node),  # 'if_condition', 'while_condition', 'comprehension'
            })
    return results
```

### Phase 5: Framework Deep Dive

**Decision**: Implement framework-specific patterns (Django URLs, FastAPI response models, SQLAlchemy cascade)

**Reasoning**: Frameworks have deep patterns that require specialized extraction. Cannot be covered by generic extractors.

**Code Implementation**:
```python
# Phase 5: django_url_extractors.py
def extract_django_url_patterns(tree: Dict, parser_self) -> List[Dict]:
    """Extract Django URL patterns from urlpatterns lists.

    Detects:
    - path('api/users/', views.UserListView.as_view(), name='user-list')
    - re_path(r'^users/(?P<pk>[0-9]+)/$', views.UserDetailView, name='user-detail')
    - include('api.urls', namespace='api')
    """
    results = []
    file_path = tree.get('file', '')

    # Priority: urls.py files
    if file_path.endswith('urls.py'):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if _is_urlpatterns_assignment(node):
                    results.extend(_extract_patterns_from_list(node.value))

    return results
```

### Phase 6: Validation Framework Completion

**Decision**: Implement validation framework patterns (Pydantic V2, Marshmallow, WTForms, DRF)

**Reasoning**: Input validation is critical for security analysis. Pydantic V2 is now industry standard (5-10x faster than V1), must support it.

**Code Implementation**:
```python
# Phase 6: pydantic_v2_extractors.py
def extract_pydantic_field_validators(tree: Dict, parser_self) -> List[Dict]:
    """Extract Pydantic V2 @field_validator decorators.

    Detects:
    - @field_validator('name')
    - @field_validator('name', 'email', mode='before')
    - Multiple validators on same field
    """
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if _is_pydantic_v2_field_validator(decorator):
                    results.append({
                        'file': tree.get('file'),
                        'line': node.lineno,
                        'model': _infer_model_name(node),
                        'fields': _extract_validated_fields(decorator),
                        'validator_func': node.name,
                        'mode': _extract_validator_mode(decorator),
                        'version': 'v2',
                    })
    return results
```

### Phase 7: Parity Polish

**Decision**: Fill remaining gaps (async tasks, type aliases, doctest)

**Reasoning**: Final 4% to reach 95% parity. Lower priority patterns but needed for completeness.

---

## EDGE CASE & FAILURE MODE ANALYSIS

### Edge Cases Considered (Per Phase)

**Phase 4: Core Language**

1. **Walrus in nested contexts**: `if (a := (b := 5))` - Handle nested NamedExpr
2. **Augmented assignment with complex targets**: `obj.attr += 1`, `dict[key] += 1`
3. **Lambda in lambda**: `lambda x: lambda y: x + y` - Handle nesting
4. **Comprehension in comprehension**: `[[y for y in range(x)] for x in range(10)]`
5. **Exception with chained from**: `raise ValueError("msg") from exc`

**Phase 5: Frameworks**

1. **Django URL include() chains**: `include(include('sub.urls'))` - Don't follow recursively (deferred)
2. **FastAPI response_model as string**: `response_model="User"` vs `response_model=User`
3. **SQLAlchemy cascade as list**: `cascade=['all', 'delete-orphan']` vs `cascade='all, delete-orphan'`

**Phase 6: Validation**

1. **Pydantic V1 in V2 codebase**: `from pydantic.v1 import validator` - Detect V1 fallback
2. **Marshmallow unknown with custom**: `class Meta: unknown = custom_function` - Handle callable

**Phase 7: Polish**

1. **asyncio.gather with star-args**: `asyncio.gather(*tasks)` - Handle unpacking
2. **Type alias with complex types**: `TypeAlias = Union[Dict[str, List[int]], None]`

### Performance & Scale Analysis

**Performance Impact** (Expected):
- Phase 3: 75 extractors, 2-7 files/sec (0.14-0.5s per file)
- Phase 4-7: 175 extractors (2.3x increase)
- **Without optimization**: 0.32-1.15s per file (2.3x slower) ❌
- **With single-pass optimization**: 0.09-0.32s per file (40% faster) ✅

**Scalability**:
- Database size: 91MB → 105MB (+15%)
- Memory usage: 300MB → 400MB (still under 500MB limit) ✅
- Query performance: Sub-second (indexes on all key columns) ✅

**Bottlenecks**:
- AST walking: O(N) where N = nodes in tree (single-pass mitigates)
- Database writes: O(M) where M = records (batch inserts mitigate)
- Memory: O(T) where T = table count (lazy loading mitigates)

---

## POST-IMPLEMENTATION INTEGRITY AUDIT (PER PHASE)

### Audit Method
After each phase:
1. Re-read all modified files
2. Run `aud index` on TheAuditor
3. Query all new tables for data
4. Compare counts with expectations
5. Performance benchmark
6. Memory usage check

### Audit Template (To be filled per phase)

#### Phase 4 Audit

**Files Modified**:
- [ ] `theauditor/ast_extractors/python/expression_extractors.py` (NEW)
- [ ] `theauditor/ast_extractors/python/exception_extractors.py` (NEW)
- [ ] `theauditor/ast_extractors/python/import_extractors.py` (NEW)
- [ ] `theauditor/ast_extractors/python/dataclass_extractors.py` (NEW)
- [ ] `theauditor/indexer/schemas/python_schema.py` (+8 tables)
- [ ] `theauditor/indexer/extractors/python.py` (+22 extractor calls)
- [ ] `theauditor/indexer/storage.py` (+22 storage handlers)
- [ ] `theauditor/indexer/database/python_database.py` (+8 writers)

**Audit Result**: [To be filled post-implementation]
- ✅/❌ All files syntactically correct
- ✅/❌ All changes applied as intended
- ✅/❌ No new issues introduced
- ✅/❌ 5,000+ new records extracted
- ✅/❌ Performance <10ms per file

---

## IMPACT, REVERSION, & TESTING

### Impact Assessment

**Phase 4 Impact**:
- Immediate: 22 new extractors, 8 new tables
- Downstream: All code using lambdas/comprehensions now tracked
- Database: +5,000 records on TheAuditor

**Phase 5 Impact**:
- Immediate: 50+ new extractors, 15 new tables
- Downstream: Django/FastAPI/SQLAlchemy analysis complete
- Database: +500 records on TheAuditor

**Phase 6 Impact**:
- Immediate: 20+ new extractors, 6 new tables
- Downstream: Pydantic V2/Marshmallow validation complete
- Database: +270 records on TheAuditor

**Phase 7 Impact**:
- Immediate: 8 new extractors, 3 new tables
- Downstream: 95% parity achieved
- Database: +230 records on TheAuditor

### Reversion Plan

**Reversibility**: Fully Reversible per phase

**Phase-Level Rollback**:
```bash
# Rollback Phase 4
git checkout pythonmapping-phase3-complete
# Database automatically reverts (fresh generation)

# Rollback Phase 5
git checkout pythonmapping-phase4-complete
# Database automatically reverts

# etc.
```

**Emergency Rollback to Phase 3**:
```bash
git checkout pythonparity  # Phase 3 baseline
# Database: .pf/history/full/20251101_xxxxx/repo_index.db
```

### Testing Performed (Per Phase)

**Phase 4 Testing** (To be filled post-implementation):
```bash
# Test 1: Run Phase 4 extractors on TheAuditor
aud index
# Expected: 5,000+ new records

# Test 2: Query walrus assignments
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
count = c.execute('SELECT COUNT(*) FROM python_walrus_assignments').fetchone()[0]
print(f'Walrus assignments: {count}')
# Expected: ~200
"

# Test 3: Performance benchmark
time aud index
# Expected: <10ms per file
```

**Phase 5 Testing**: [To be filled]
**Phase 6 Testing**: [To be filled]
**Phase 7 Testing**: [To be filled]

---

## CONFIRMATION OF UNDERSTANDING

### Verification Finding
[To be filled after verification phase]

**Summary**: Current state verified against 10 hypotheses. All gaps confirmed.

### Root Cause
**Summary**: Incremental scope management led to deferred patterns. Intentional, not a mistake. Gap analysis now defines next 4 phases.

### Implementation Logic
**Summary**: 4 phases (Core → Frameworks → Validation → Polish) with clear dependencies. 16-24 weeks to 95% parity.

### Confidence Level
**Pre-Implementation**: MEDIUM (hypotheses not yet verified)
**Post-Verification**: [HIGH/MEDIUM/LOW based on verification results]

---

**END OF VERIFICATION DOCUMENT**

**Next Step**: Complete verification phase, then begin Phase 4 implementation
