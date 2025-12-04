# Verification: migrate-rules-to-fidelity-layer

Pre-implementation verification checklist. All hypotheses must be confirmed before starting Wave 1.

---

## Hypothesis 1: Phase 1 Infrastructure Exists

Phase 1 (`add-rules-data-fidelity`) must be complete before this migration can start.

### Verification 1.1: query.py exists

```bash
cd C:/Users/santa/Desktop/TheAuditor && ls theauditor/rules/query.py
# Expected: File exists
```

**Status**: [ ] Confirmed

### Verification 1.2: fidelity.py exists

```bash
cd C:/Users/santa/Desktop/TheAuditor && ls theauditor/rules/fidelity.py
# Expected: File exists
```

**Status**: [ ] Confirmed

### Verification 1.3: Q class has required methods

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.rules.query import Q
assert hasattr(Q, 'select'), 'Missing select'
assert hasattr(Q, 'where'), 'Missing where'
assert hasattr(Q, 'join'), 'Missing join'
assert hasattr(Q, 'with_cte'), 'Missing with_cte'
assert hasattr(Q, 'build'), 'Missing build'
assert hasattr(Q, 'raw'), 'Missing raw'
print('Q class API complete')
"
```

**Status**: [ ] Confirmed

### Verification 1.4: RuleDB and RuleResult exist

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.rules.fidelity import RuleResult, RuleDB, RuleManifest
print('Fidelity classes exist')
"
```

**Status**: [ ] Confirmed

---

## Hypothesis 2: Orchestrator Handles RuleResult

The orchestrator must be updated to handle `RuleResult` return type from rules.

### Verification 2.1: _execute_rule handles RuleResult

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import inspect
from theauditor.rules.orchestrator import RulesOrchestrator

source = inspect.getsource(RulesOrchestrator._execute_rule)
assert 'RuleResult' in source, '_execute_rule does not handle RuleResult'
print('Orchestrator handles RuleResult')
"
```

**Status**: [ ] Confirmed

### Verification 2.2: Fidelity imports exist in orchestrator

```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -n "RuleResult" theauditor/rules/orchestrator.py | head -3
# Expected: Import line at top of file
```

**Status**: [ ] Confirmed

---

## Hypothesis 3: Rule Files Are Migratable

All 95 rule files can be read and have an `analyze()` or `find_*` function.

### Verification 3.1: All rule files importable

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import importlib
import os

failed = []
for root, dirs, files in os.walk('theauditor/rules'):
    dirs[:] = [d for d in dirs if not d.startswith('__')]
    for f in files:
        if f.endswith('.py') and not f.startswith('__') and not f.startswith('TEMPLATE'):
            rel_path = os.path.join(root, f)
            module = rel_path.replace('/', '.').replace('\\\\', '.')[:-3]
            try:
                importlib.import_module(module)
            except Exception as e:
                failed.append((module, str(e)[:50]))

if failed:
    print(f'FAILED: {len(failed)} modules')
    for m, e in failed[:5]:
        print(f'  {m}: {e}')
else:
    print('All rule modules importable')
"
```

**Status**: [ ] Confirmed

---

## Hypothesis 4: Database Schema is Stable

The TABLES dict has all tables referenced by rules.

### Verification 4.1: Key tables exist

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES

required = ['symbols', 'function_call_args', 'assignments', 'sql_queries', 'react_components']
missing = [t for t in required if t not in TABLES]

if missing:
    print(f'MISSING TABLES: {missing}')
else:
    print(f'All required tables exist ({len(TABLES)} total tables)')
"
```

**Status**: [ ] Confirmed

---

## Hypothesis 5: base.py Has RuleMetadata

Rules need RuleMetadata for METADATA constant.

### Verification 5.1: RuleMetadata exists

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.rules.base import RuleMetadata
print(f'RuleMetadata fields: {list(RuleMetadata.__dataclass_fields__.keys())}')
"
```

**Status**: [ ] Confirmed

---

## Pre-Flight Checklist

Before starting Wave 1, ALL of the following must be checked:

- [ ] All Hypothesis 1 verifications pass (Phase 1 complete)
- [ ] All Hypothesis 2 verifications pass (Orchestrator ready)
- [ ] All Hypothesis 3 verifications pass (Rules importable)
- [ ] All Hypothesis 4 verifications pass (Schema stable)
- [ ] All Hypothesis 5 verifications pass (RuleMetadata exists)

**If ANY verification fails:**
1. Do NOT start Wave 1
2. Complete Phase 1 (`add-rules-data-fidelity`) first
3. Re-run all verifications
4. Only proceed when all pass

---

## Post-Migration Verification

After all waves complete:

### Final 1: No raw cursor.execute() remains

```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -r "cursor.execute" theauditor/rules --include="*.py" | grep -v "__pycache__" | grep -v "Q.raw" | wc -l
# Expected: 0
```

### Final 2: All rules return RuleResult

```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -r "def analyze" theauditor/rules --include="*.py" -A 1 | grep "RuleResult" | wc -l
# Expected: >= 95
```

### Final 3: Full pipeline runs

```bash
cd C:/Users/santa/Desktop/TheAuditor && aud full --offline
# Expected: Completes without crashes
```
