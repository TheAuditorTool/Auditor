# What's Next - Roadmap & Rationale

**Last Updated:** 2025-10-26
**Current Milestone:** Validation Framework Sanitizer Detection (Layers 1 & 2) ✅ COMPLETE

---

## The Journey: From arg0 to Complete Taint Analysis

**The Big Picture:**
Multi-hop taint analysis requires 3 foundational layers:
1. **Data Mapping** - What variables exist and how they flow
2. **Sanitization Tracking** - What gets cleaned and how (IN PROGRESS)
3. **Framework Integration** - How frameworks handle data

**Current State:** Layer 1 partially complete (parameter names ✓), Layer 2 extraction complete (taint integration pending)

---

## Phase 1: Complete Data Mapping

### ✅ COMPLETE: Parameter Name Resolution (2025-10-25)
**What:** Match variables across function boundaries
**Why:** Multi-hop needs to know 'data' in callee is the same as 'req.body' in caller
**Impact:** 29.9% of calls now have real names (3,664/13,745)
**Status:** Foundation laid, ready to use

### 🔴 NEXT: Investigate Taint Analysis Regression
**What:** Figure out why taint paths dropped from 133 to 0
**Why:** Parameter resolution won't help if taint detection is broken
**Timeline:** Immediate next session
**Approach:**
1. Compare 2025-10-20 database vs current
2. Check if multi-hop is using new param_name values
3. Debug source/sink detection with THEAUDITOR_TAINT_DEBUG=1
4. Verify memory cache and query logic

**Expected Outcome:** Restore 133+ taint paths, verify they now use real param names

### 🟡 FUTURE: Additional Data Mapping
**What:** Map more than just function parameters
**Examples:**
- Return value tracking (what functions return)
- Object property tracking (obj.foo → obj.bar)
- Array element tracking (arr[0] → arr[1])
- Closure variable tracking (captured vars)
- Async promise tracking (then/catch chains)

**Why:** Complete picture of data flow requires all mappings
**Architect Quote:** "its literally mapping everything"

---

## Phase 2: Sanitizer Detection

### What is a Sanitizer?
Code that cleans/validates/encodes data, making it safe:
```typescript
// Input validation
const validated = schema.validate(req.body);

// Encoding
const safe = encodeURIComponent(userInput);

// Framework sanitizers
const cleaned = sanitize(data);
```

### Why This Matters
Current taint analysis will flag:
```typescript
const id = req.params.id;           // Source (tainted)
const user = User.findById(id);     // Sink (SQL query)
// Vulnerability: SQL injection risk!
```

With sanitizer detection:
```typescript
const id = parseInt(req.params.id); // Sanitizer!
const user = User.findById(id);     // Safe - sanitized integer
// No vulnerability: input sanitized
```

### ✅ PARTIAL COMPLETE: Validation Framework Detection & Extraction (2025-10-26)

**Status:** Layers 1 & 2 complete, Layer 3 (taint integration) pending

#### Implementation Status (3-Layer Architecture)

**Layer 1: Framework Detection** ✅ COMPLETE
- Added 6 validation frameworks to registry: zod, joi, yup, ajv, class-validator, express-validator
- Integrated into framework_detector.py with THEAUDITOR_VALIDATION_DEBUG logging
- Created validation_debug.py for structured logging
- **Result:** Framework detection working (Zod v4.1.11 detected in Plant project)
- **Files Modified:**
  - `theauditor/framework_registry.py` (+75 lines)
  - `theauditor/framework_detector.py` (+15 lines)
  - `theauditor/utils/validation_debug.py` (NEW FILE +40 lines)

**Layer 2: Data Extraction** ✅ COMPLETE (2025-10-26)
- Created extractValidationFrameworkUsage() in security_extractors.js (+235 lines)
- Added validation_framework_usage table to schema (7 columns)
- Wired extraction to batch_templates.js (ES module + CommonJS variants)
- Mapped through KEY_MAPPINGS in javascript.py
- Integrated storage via generic batch system in __init__.py
- **Result:** 3 validation calls extracted from Plant's validate.ts
  ```
  Line 19:  zod.parseAsync() (validateBody)
  Line 67:  zod.parseAsync() (validateParams)
  Line 106: zod.parseAsync() (validateQuery)
  ```
- **Files Modified:**
  - `theauditor/ast_extractors/javascript/security_extractors.js` (+235 lines)
  - `theauditor/ast_extractors/javascript/batch_templates.js` (+4 lines)
  - `theauditor/indexer/schema.py` (+18 lines)
  - `theauditor/indexer/extractors/javascript.py` (+1 line KEY_MAPPINGS)
  - `theauditor/indexer/__init__.py` (+20 lines storage + flush)

**Layer 3: Taint Integration** 🔴 TODO (Next Session)
- Modify has_sanitizer_between() in taint/sources.py
- Query validation_framework_usage table for lines between source and sink
- Mark taint paths as safe if validation detected
- Update TaintPath to include sanitizer metadata
- Update findings output to show validation info
- **Expected Impact:** 50-70% reduction in false positives
- **Timeline:** 1-2 sessions (simpler than extraction)

#### Technical Achievements (7 Critical Fixes Applied)

**Fix 1: TypeError Prevention**
- **Location:** security_extractors.js:92
- **Issue:** extractAPIEndpoints() called .replace() on non-string route → TypeError
- **Impact:** TypeError cascaded to try/catch, skipping ALL subsequent extraction including validation
- **Fix:** Added type check `if (!route || typeof route !== 'string') continue;`

**Fix 2: Key Mismatch**
- **Location:** batch_templates.js:317, 631
- **Issue:** JavaScript used 'api_endpoints' key, Python expected 'routes' key
- **Impact:** Would cause KeyError in Python indexer
- **Fix:** Renamed to 'routes' in both ES module and CommonJS variants

**Fix 3: JavaScript Error Reporting**
- **Location:** __init__.py:518-520
- **Issue:** JavaScript batch processing failures silently swallowed
- **Impact:** No visibility into extraction errors during indexing
- **Fix:** Added error check before extraction, prints JS errors to stderr

**Fix 4: KEY_MAPPINGS Missing Entry** 🔴 CRITICAL
- **Location:** javascript.py:125
- **Issue:** validation_framework_usage extracted by JS but NOT in KEY_MAPPINGS filter
- **Impact:** Data extracted correctly, then silently dropped by Python layer!
- **Fix:** Added `'validation_framework_usage': 'validation_framework_usage'` to mappings
- **Detection Method:** Added PY-DEBUG logs showed key in extracted data but 0 items

**Fix 5: Relaxed Validation Detection**
- **Location:** security_extractors.js:272-276
- **Issue:** Only detected schemas DEFINED in same file, not imported schemas
- **Impact:** schema.parseAsync() where schema is function parameter was missed
- **Fix:** Relaxed logic - if file imports validation framework AND calls validation method, it's valid
- **Pattern:** `frameworks.length > 0 && isValidatorMethod(callee)`

**Fix 6: Zero Fallback Compliance** 🔴 CRITICAL
- **Location:** security_extractors.js:339
- **Issue:** Used `if (frameworks.length > 0)` - BANNED fallback pattern (guesses first framework)
- **Impact:** Violates ZERO FALLBACK POLICY from CLAUDE.md
- **Fix:** Changed to `if (frameworks.length === 1)` - deterministic, not fallback
- **Logic:** Only use framework if EXACTLY ONE imported; if 0 or multiple, return 'unknown' (fail loud)

**Fix 7: Generic Batch Flush Missing** 🔴 CRITICAL
- **Location:** __init__.py:636-640
- **Issue:** generic_batches never flushed at end of indexing, only on batch_size threshold
- **Impact:** Data collected in memory, never written to database!
- **Fix:** Added flush loop for all generic_batches before return
- **Detection Method:** PY-DEBUG showed "3 items" but database had 0 rows

#### Database Schema Addition

**New Table: validation_framework_usage**
```sql
CREATE TABLE validation_framework_usage (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    framework TEXT NOT NULL,      -- 'zod', 'joi', 'yup', 'ajv', etc.
    method TEXT NOT NULL,          -- 'parse', 'parseAsync', 'validate', etc.
    variable_name TEXT,            -- schema variable name or NULL for imports
    is_validator BOOLEAN DEFAULT 1,
    argument_expr TEXT             -- truncated to 200 chars
);

CREATE INDEX idx_validation_framework_file_line ON validation_framework_usage(file_path, line);
CREATE INDEX idx_validation_framework_method ON validation_framework_usage(framework, method);
CREATE INDEX idx_validation_is_validator ON validation_framework_usage(is_validator);
```

**Sample Data (Plant Project):**
```sql
sqlite> SELECT * FROM validation_framework_usage;
backend/src/middleware/validate.ts|19|zod|parseAsync|schema|1|req.body
backend/src/middleware/validate.ts|67|zod|parseAsync|schema|1|req.params
backend/src/middleware/validate.ts|106|zod|parseAsync|schema|1|req.query
```

#### Architecture Lessons Learned

**Separation of Concerns:**
- Bug 1-2: JavaScript extraction layer (security_extractors.js, batch_templates.js)
- Bug 3-4: Python mapping layer (KEY_MAPPINGS in javascript.py, error reporting in __init__.py)
- Bug 5-6: JavaScript detection logic (isValidationCall, getFrameworkName)
- Bug 7: Python storage layer (generic batch flush in __init__.py)

**Silent Failures:**
- KEY_MAPPINGS filter silently dropped extracted data (validated with PY-DEBUG logs)
- Generic batches not flushed at end of indexing (data in memory, never committed)

**Zero Fallback Compliance:**
- Initial code used `if (frameworks.length > 0)` - BANNED fallback pattern
- Corrected to `if (frameworks.length === 1)` - deterministic, not fallback
- If 0 or multiple frameworks imported, return 'unknown' (fail loud, not guess)

#### Remaining Implementation (Layer 3)

1. **Taint Integration:**
   - Modify has_sanitizer_between() in taint/sources.py
   - Query validation_framework_usage for lines between source_line and sink_line
   - If validation found, return True (sanitizer detected)
   - Example query:
   ```python
   cursor.execute("""
       SELECT framework, method, line
       FROM validation_framework_usage
       WHERE file_path = ? AND line > ? AND line < ?
   """, (file_path, min(source_line, sink_line), max(source_line, sink_line)))
   ```

2. **Additional Sanitizers (Future):**
   - Type conversions: parseInt, Number, Boolean
   - Encoding functions: escape, encodeURI, encodeURIComponent, sanitize
   - String operations: trim, toLowerCase (context-dependent)
   - Framework validators: Express-validator patterns
   - SQL parameterization detection

**Total Implementation:** 8 files modified, ~408 lines added/modified

**Expected Impact After Layer 3:** 50-70% reduction in false positives from validated inputs

---

## Phase 3: Framework-Specific Taint Patterns

### What are Framework Patterns?
Different frameworks handle data differently:

**Express (Request Handling):**
```typescript
app.post('/user', (req, res) => {
  const data = req.body;  // Source
  res.json(data);         // Safe sink (JSON encoded)
});
```

**Sequelize (ORM):**
```typescript
User.findOne({
  where: { id: userId }   // Parameterized - safe
});

sequelize.query(
  `SELECT * FROM users WHERE id=${userId}` // Dangerous!
);
```

**Prisma (Different ORM):**
```typescript
prisma.user.findUnique({
  where: { id: userId }   // Always parameterized - safe
});
```

### Why This Matters
Generic taint analysis doesn't understand:
- Which framework sinks are safe by design
- Which patterns auto-sanitize
- Which methods are dangerous

Framework-specific rules dramatically improve accuracy.

### Implementation Approach
1. **Catalog Framework Patterns:**
   - Express: req.body, req.params, req.query (sources)
   - Express: res.json, res.send (safe vs unsafe sinks)
   - Sequelize: findOne, create, update (parameterized)
   - Sequelize: query, literal (raw SQL - dangerous)
   - Prisma: all methods (auto-sanitized)

2. **Add Framework Metadata:**
   - Tag sources/sinks with framework
   - Framework-specific safe/unsafe classifications
   - Custom rules per framework

3. **Integrate with Taint:**
   - Check framework when analyzing paths
   - Apply framework-specific logic
   - Include framework context in findings

**Expected Impact:** More accurate findings, fewer false positives

---

## Phase 4: CFG Integration Improvements

### What is CFG Integration?
Control Flow Graph - understanding execution paths through code:

```typescript
function process(input) {
  if (isValid(input)) {
    return safe(input);     // This path is safe
  } else {
    log(input);            // This path might be unsafe
  }
}
```

Without CFG: Both paths flagged
With CFG: Only unsafe path flagged

### Current State (from handoff.md)
CFG integration exists:
- Stage 3 uses CFG for multi-hop
- Callback handling working
- 2-5 hop chains detected (was working on 2025-10-20)

### Future Improvements
1. **Better Async/Await:**
   ```typescript
   async function handler(req) {
     const data = await validate(req.body);  // Async sanitizer
     return await save(data);                 // Async sink
   }
   ```

2. **Promise Chains:**
   ```typescript
   getData()
     .then(sanitize)       // Sanitizer in chain
     .then(process)        // Should be safe
     .catch(handleError);
   ```

3. **Callback Closures:**
   ```typescript
   function outer(tainted) {
     inner(() => {
       use(tainted);  // Captured variable taint
     });
   }
   ```

**Expected Impact:** More complete taint tracking

---

## The Iterative Process (Why Step-by-Step)

### Architect's Wisdom
> "its not a sprint, its an iteration thing... dont stress, step by step"

### Why This Approach?
1. **Complexity:** Taint analysis touches indexer, extractors, analyzers
2. **Separation of Concerns:** Data layer vs analysis layer issues
3. **Verification:** Each step needs testing before next
4. **Stability:** One bug can cascade through system

### Example of Iteration (Parameter Resolution Session)
```
Problem: Multi-hop can't match variables
└─> Investigate: Why can't it match?
    └─> Root cause: Parameter names are generic (arg0)
        └─> Fix: Data layer (indexer) not analysis layer (taint)
            └─> Implement: Database-first resolution
                └─> Verify: Database queries confirm fix
                    └─> Result: Foundation complete, ready for next layer
```

### Example of Iteration (Validation Framework Session)
```
Problem: validation_framework_usage table empty
└─> Investigation Layer 1: Python debug logs
    └─> Key in extracted data but 0 items
        └─> Investigation Layer 2: JavaScript debug logs
            └─> No logs appeared (function not called OR logs not captured)
                └─> Investigation Layer 3: Check JavaScript assembly
                    └─> Function exists and called
                        └─> Investigation Layer 4: Use PY-DEBUG
                            └─> Key EXISTS with "0 items" (function returns empty)
                                └─> Fix 4: KEY_MAPPINGS missing
                                └─> Fix 5: Relaxed validation detection
                                └─> Key EXISTS with "3 items" but DB still 0 rows!
                                    └─> Fix 7: Generic batches not flushed
                                        └─> SUCCESS: 3 rows in database
```

### Not a Rush
- Parameter resolution: ~6 hours (8 steps)
- Validation framework extraction: ~8 hours (7 fixes across 4 architectural layers)

**This is normal and expected.** Quality over speed.

---

## Timeline Estimates (Rough)

### Immediate (Next 1-2 Sessions)
- ✅ Parameter resolution (COMPLETE 2025-10-25)
- ✅ Validation framework extraction (COMPLETE 2025-10-26)
- 🔴 Fix taint regression (1-2 sessions)
- 🔴 Validation taint integration (1-2 sessions)

### Short Term (1-2 Months)
- 🟡 Additional data mapping (2-3 sessions)
- 🟡 Additional sanitizer patterns (3-5 sessions)
- 🟡 Framework patterns (5-10 sessions)

### Medium Term (2-4 Months)
- 🟢 CFG improvements (5-10 sessions)
- 🟢 Advanced features (ongoing)

**Note:** These are ROUGH estimates. Each iteration may reveal new issues.

---

## Success Metrics

### Current State
- Parameters resolved: 29.9%
- Validation frameworks: 6 frameworks detected
- Validation calls extracted: 3 from Plant project
- Taint paths: 0 (regression - needs investigation)
- Cross-file matching: Ready to use

### Near-Term Goals
- Taint paths: 100+ (restore previous functionality)
- Cross-file paths: Using real param names (verify)
- Validation integration: Working (Layer 3)
- False positive baseline: Established

### Mid-Term Goals
- Validation sanitizer detection: 50-70% FP reduction
- Additional sanitizers: 80%+ pattern coverage
- Framework awareness: 80%+ accuracy
- CFG coverage: Complete async/promise support

### Long-Term Goals
- Production ready: Safe to use on real projects
- False positive rate: <10%
- Coverage: 90%+ of common vulnerability patterns

---

## Key Principles (Carry Forward)

### 1. Database-First
Always query database, never parse files during analysis

### 2. Zero Fallback
If data is missing, fail loud - don't hide the problem
Example: frameworks.length === 1 (deterministic), not > 0 (fallback)

### 3. Separation of Concerns
Data layer bugs fixed in indexer, not taint analysis
Example: 7 fixes across 4 layers (JS extraction, JS/Python boundary, Python mapping, Python storage)

### 4. Iterative Progress
Small verified steps better than large unverified leaps
Example: 7 fixes applied incrementally with verification at each step

### 5. Evidence-Based
Verify claims with database queries, not assumptions
Example: Debug logging at each boundary, database queries after each fix

---

## What Success Looks Like

**Ultimate Goal:** Architect can run TheAuditor on production codebases and trust the results.

**Example:**
```
Input: Plant project (Express + TypeScript app)
Output: 20-30 high-confidence vulnerabilities
  - SQL injection (5-10)
  - XSS (3-5)
  - Command injection (1-2)
  - Path traversal (2-4)
  - Authentication bypass (2-3)

False positives: <5
Coverage: 90%+ of OWASP Top 10 patterns
```

**Current State:** Foundation being built, parameter mapping complete, validation extraction complete.

**Distance to Goal:** 40-50% of work remaining (taint integration, additional sanitizers, framework patterns, CFG improvements).

---

## Summary

**Where We Are:**
- ✅ Parameter name resolution COMPLETE (2025-10-25)
- ✅ Validation framework detection COMPLETE (2025-10-26 Layer 1)
- ✅ Validation extraction COMPLETE (2025-10-26 Layer 2)
- 🔴 Validation taint integration PENDING (Layer 3)
- ⚠️ Taint detection needs investigation (0 paths regression)
- 📊 Data mapping ~30% complete
- 📊 Sanitizer detection ~67% complete (2 of 3 layers)

**What's Next (Priority Order):**
1. Validation taint integration (HIGH - Layer 3)
2. Fix taint regression (URGENT)
3. Complete data mapping (MEDIUM)
4. Additional sanitizer patterns (MEDIUM)
5. Framework patterns (MEDIUM)
6. CFG improvements (LOW)

**How Long:**
- Months, not weeks
- Iterative, not sprint
- Quality over speed

**Why This Matters:**
Each layer builds on previous. Parameter resolution enables sanitizer detection. Sanitizer detection enables accurate framework patterns. All together enable production-ready taint analysis.

**Architect's Vision:**
Deterministic multi-hop taint analysis without manual hints. We're building it, step by step.

---

**Next session starts with:** Validation taint integration (Layer 3) or investigating taint analysis regression (0 paths).
