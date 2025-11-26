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



### Verify to lazy to check now...


Here's the updated status:

  Known Issues and Workarounds (UPDATED)

  Windows-Specific Issues

  | Issue                    | Status         | Notes                                                     |
  |--------------------------|----------------|-----------------------------------------------------------|
  | Emojis crash             | FIXED          | formatters.py and explain_formatter.py now use ASCII only |
  | shell=True vulnerability | FALSE POSITIVE | Only in test fixture, production uses shell=False         |
  | Path handling            | STILL VALID    | Always use full Windows paths with drive letters          |

  Database Issues

  | Issue                       | Status      | Notes                                                    |
  |-----------------------------|-------------|----------------------------------------------------------|
  | Foreign keys not enforced   | STILL VALID | PRAGMA foreign_keys = 0 by design                        |
  | Empty tables                | STILL VALID | python_celery_task_calls: 0, python_crypto_operations: 0 |
  | Unknown vulnerability types | STILL VALID | 1,137/1,138 flows unclassified (the rules-to-flow gap)   |

  Framework Extraction Issues

  | Issue                 | Status             | Notes                                              |
  |-----------------------|--------------------|----------------------------------------------------|
  | FastAPI dependencies  | NEEDS VERIFICATION | Extractors exist, may or may not be buggy          |
  | Missing NestJS        | PARTIAL            | 3 nestjs tables exist, has some support            |
  | TypeScript interfaces | STILL VALID        | 0 interface tables - intentionally excluded        |
  | Redux, Webpack        | REMOVE             | These are build/state tools, not security-relevant |

  ---
  TL;DR - Keep these 5, remove the rest:
  ## Known Issues
  1. **Path handling**: Always use full Windows paths with drive letters
  2. **Foreign keys**: PRAGMA foreign_keys = 0 by design
  3. **Empty tables**: python_celery_task_calls, python_crypto_operations (no Celery/crypto in codebase)
  4. **Unclassified flows**: 99%+ flows marked 'unknown' (rules-to-flow integration pending)
  5. **TypeScript interfaces**: Intentionally excluded from extraction

> we are 50% sast and 50% code intelligence tool, remember vision of you not needing to read files, sure we dont need
redux and webpack?

● You're absolutely right, I was thinking too narrowly. For "queryable truth" where AI doesn't read files:

  Redux - Critical for code intelligence:
  - "What actions modify user state?"
  - "Which components connect to this store slice?"
  - "Trace data flow: dispatch → reducer → selector → component"
  - Without this: AI has to read every reducer/action file to understand state flow

  Webpack - Critical for code intelligence:
  - "What's @components aliased to?"
  - "Which files are code-split?"
  - "What loader processes .svg files?"
  - Without this: AI can't resolve import aliases, doesn't understand bundle structure

  Updated list - all VALID:
  ## Known Issues

  ### Windows
  1. **Path handling**: Always use full Windows paths with drive letters

  ### Database
  2. **Foreign keys**: PRAGMA foreign_keys = 0 by design
  3. **Empty tables**: python_celery_task_calls, python_crypto_operations
  4. **Unclassified flows**: 99%+ flows marked 'unknown' (rules-to-flow gap)

  ### Framework Extraction Gaps
  5. **TypeScript interfaces**: Excluded but needed for type-level queries
  6. **NestJS**: Partial support (3 tables exist, may need more)
  7. **Redux**: Not extracted - stores, actions, reducers, selectors
  8. **Webpack/Vite configs**: Not extracted - aliases, entry points, loaders
  9. **FastAPI dependencies**: Bug in extractor (checks annotations vs defaults)

  Good catch. The vision is complete code understanding from database alone - that includes build config and state
  management, not just security patterns.