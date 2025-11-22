# Known Issues

Tracked bugs and architectural issues. See also `docs/oops_taint.md` for the taint analysis Express-only limitation.

---

## KI-002: Taint Analysis is Express-Only

**Discovered**: 2025-11-22
**Severity**: CRITICAL ARCHITECTURAL FLAW
**Status**: UNFIXED
**Full Documentation**: `docs/oops_taint.md`

### Summary

FlowResolver and IFDS analyzer are hard-coded for Express/Node.js. Python projects (Django, FastAPI, Flask) receive essentially zero taint analysis.

### Impact

| Project Type | Effective Coverage |
|--------------|-------------------|
| Express + React monorepo | 100% |
| Express standalone | 60% |
| Django/FastAPI/Flask | 20% |
| Python standalone | 10% |

### Estimated Fix Effort

48 hours across FlowResolver, IFDS analyzer, and DFG builder.

---

## Template for New Issues

```markdown
## KI-XXX: Title

**Reported**: YYYY-MM-DD
**Severity**: LOW | MEDIUM | HIGH | CRITICAL
**Status**: OPEN | IN PROGRESS | FIXED (version)
**Affected Versions**:

### Symptoms

What the user sees.

### Root Cause

Why it happens.

### Workaround

Temporary fix if any.

### Fix Applied

Code changes made.

### Files Modified

- file1.py - Description
- file2.js - Description
```
