# FCE JSON Normalization Verification

**Status**: 🔴 PENDING - Must approve REVERSING commit d8370a7

---

## Critical Decision Point

**This proposal REVERSES commit d8370a7 exemption** for `findings_consolidated.details_json`

**Architect must approve** before proceeding.

---

## Hypotheses

### Hypothesis 1: FCE has 7 json.loads() calls
**Verification**: Read `fce.py:60-401`
**Result**: ⚠️ PENDING
- Line 60: hotspots? (Y/N)
- Line 78: cycles? (Y/N)
- Line 127: CFG complexity? (Y/N)
- Line 168: code churn? (Y/N)
- Line 207: test coverage? (Y/N)
- Line 265: taint paths? (Y/N) ← CRITICAL
- Line 401: metadata? (Y/N)

### Hypothesis 2: Taint paths are 50-500ms bottleneck
**Verification**: Profile FCE with cProfile
**Result**: ⚠️ PENDING
- Actual overhead: ___ ms

### Hypothesis 3: symbols.parameters uses JSON
**Verification**: Read `taint/discovery.py:112` and `javascript.py:1288`
**Result**: ⚠️ PENDING

---

## Baseline Performance

### FCE Time
```bash
time aud full  # Measure FCE component
```
**Result**: ⚠️ PENDING - FCE overhead: ___ ms

---

## Commit d8370a7 Analysis

### What was exempted?
**Result**: ⚠️ PENDING - Read commit diff

### Why was it exempted?
**Result**: ⚠️ PENDING - Assumption? Performance not measured?

### Is reversal justified?
**Decision**: ⚠️ PENDING - Architect must approve

---

## Architect Approval

**Status**: ⚠️ PENDING

- [ ] APPROVED - Reverse exemption, proceed with normalization
- [ ] DENIED - Keep exemption, close this proposal

**Rationale**: (Architect's reasoning)
