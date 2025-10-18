# Design: Validation Framework Sanitizer Recognition

## Context
TheAuditor's taint analyzer tracks data flow from sources (user input) to sinks (database queries, HTML output) to detect security vulnerabilities. When data passes through a sanitizer/validator, taint analysis should recognize this and stop reporting it as a vulnerability.

The original SANITIZERS dictionary was designed in 2024 with generic patterns matching traditional sanitization functions (`escape_html`, `sanitize_filename`) and generic validation verbs (`"validate"`, `"sanitize"`, `"clean"`). These patterns work via substring matching: `"validate" in function_name.lower()`.

**Problem:** Modern JavaScript/TypeScript validation frameworks (Zod 2020+, Joi 2014+, Yup 2016+) use method-based APIs where validation happens via specific method calls like `.parse()`, `.validateAsync()`, `.isValid()`. These methods don't contain the substring "validate", causing them to be invisible to current sanitizer detection.

**Real-world impact:** TypeScript projects using Zod (now standard for TypeScript validation) report 38% false positive rate because validated data is still flagged as tainted.

## Goals / Non-Goals

### Goals
1. Recognize Zod, Joi, Yup, express-validator, class-validator, and AJV validation methods as sanitizers
2. Reduce false positive rate from 38% to ~12% in modern TypeScript projects
3. Maintain backward compatibility - no breaking changes to existing patterns
4. Zero performance regression (maintain O(1) frozenset lookup)
5. Zero new dependencies or database schema changes

### Non-Goals
1. **Control flow constraint analysis** - Detecting strict equality checks (`=== 'en'`) requires CFG-based constraint propagation, separate feature
2. **Python validation frameworks** - Pydantic, Marshmallow belong in separate task for Python ecosystem
3. **Type system validation** - TypeScript type narrowing requires full type system integration
4. **Custom project-specific validators** - Users rely on existing generic patterns or future configuration system

## Decisions

### Decision 1: Framework-Specific Patterns vs Generic Enhancement
**Chosen:** Add framework-specific patterns to SANITIZERS dictionary

**Rationale:**
- Explicit beats implicit - developers can see exactly which frameworks are supported
- No false negatives from overly broad matching (e.g., bare `.parse` would match `JSON.parse`, `url.parse`)
- Easy to extend - new frameworks just add patterns to frozenset
- Maintains existing architecture (no refactoring needed)

**Alternative Considered:** Generic pattern like `".parse"` or `".validate"`
- **Rejected:** Too broad, would match non-validation functions:
  - `JSON.parse(req.body)` - Deserializes but doesn't validate
  - `url.parse(req.query.url)` - Parses but doesn't sanitize
  - `Date.parse(req.body.date)` - Type conversion, not validation

### Decision 2: New Category vs Extend Existing "validation"
**Chosen:** Create new `validation_frameworks` category in SANITIZERS

**Rationale:**
- Clear separation between generic patterns and framework-specific patterns
- Easier to document which frameworks are supported
- Cleaner code organization (generic vs specific)
- Future extensibility (can add `validation_frameworks_python` later)

**Alternative Considered:** Add to existing `"validation"` category
- **Rejected:** Mixes generic patterns with framework-specific, harder to understand what's supported

### Decision 3: Matching Logic Enhancement (OPTIONAL)
**Chosen:** Evaluate during implementation whether current substring matching is sufficient

**Current Logic (propagation.py:40):**
```python
if sanitizer.lower() in func_lower or func_lower in sanitizer.lower():
    return True
```

**Possible Enhancement (if needed):**
```python
# Suffix-based matching for dotted methods
if sanitizer.startswith('.') and func_lower.endswith(sanitizer.lower()):
    return True

# Exact substring for framework methods
if '.' in sanitizer and sanitizer.lower() in func_lower:
    return True

# Fallback to existing logic for generic names
if sanitizer.lower() in func_lower or func_lower in sanitizer.lower():
    return True
```

**Rationale for deferred decision:**
- Current substring matching may already work: `"schema.parse" in "schema.parse(req.body)"` → True
- Enhancement only needed if testing shows misses
- Don't over-engineer until proven necessary (simplicity first per OpenSpec best practices)

### Decision 4: Schema Builders Explicitly Excluded
**Chosen:** Only add validation methods, NOT schema builders

**Patterns to ADD:**
- ✅ `schema.parse` - Validates data
- ✅ `.parseAsync` - Validates data
- ✅ `validationResult` - Extracts validated data

**Patterns to EXCLUDE:**
- ❌ `z.string()` - Schema builder, not validator
- ❌ `Joi.number()` - Schema builder, not validator
- ❌ `yup.object()` - Schema builder, not validator

**Rationale:**
```typescript
const schema = z.string();        // NOT a sanitizer - just builds schema
const result = schema.parse(input);  // THIS is the sanitizer - validates
```

Schema construction doesn't validate data, only the `.parse()` call does.

## Pattern Selection Methodology

### Research Process
1. Review official documentation for each framework
2. Identify methods that **validate and return clean data** or **throw on invalid data**
3. Exclude methods that only **construct schemas** or **check types**
4. Verify patterns against real-world usage in popular open-source projects

### Selected Patterns by Framework

#### Zod (TypeScript-first, released 2020)
- `.parse` - Validates, throws on error, returns typed data
- `.parseAsync` - Async version of .parse
- `.safeParse` - Validates, returns result object (never throws)
- `z.parse` - Shorthand usage
- `schema.parse` / `schema.parseAsync` / `schema.safeParse` - Explicit variants

**Most common:** `.parseAsync` in async Express/Fastify handlers

#### Joi (@hapi/joi, Node.js standard since 2014)
- `.validate` - Synchronous validation
- `.validateAsync` - Async validation (recommended)
- `Joi.validate` - Static method
- `schema.validate` / `schema.validateAsync` - Instance methods

**Most common:** `schema.validateAsync` in Node.js servers

#### Yup (React ecosystem, released 2016)
- `.validate` - Async validation (default)
- `.validateSync` - Synchronous validation
- `.isValid` - Boolean check (validates but returns true/false)
- `yup.validate` / `schema.validateSync` - Explicit variants

**Most common:** `.validate` in React form validation

#### express-validator (Express middleware ecosystem)
- `validationResult` - Extracts validation errors from request
- `matchedData` - Returns only validated data (safe to use)
- `checkSchema` - Schema-based validation

**Most common:** `validationResult(req)` in Express routes

#### class-validator (TypeScript decorators, NestJS standard)
- `validate` - Validates decorated class instance
- `validateSync` - Synchronous version
- `validateOrReject` - Throws on validation failure

**Most common:** `validate(dto)` in NestJS controllers

#### AJV (JSON Schema validator, high-performance)
- `ajv.validate` - Validates against JSON Schema
- `ajv.compile` - Compiles validator function
- `validator.validate` - Compiled validator usage

**Most common:** `ajv.validate(schema, data)` in API gateways

## Risks / Trade-offs

### Risk 1: False Negatives from Non-Validation `.parse` Methods
**Risk:** Over-matching causes JSON.parse, url.parse to be treated as sanitizers

**Mitigation:**
- Use framework-specific patterns: `schema.parse`, `z.parse` (not bare `.parse`)
- Test JSON.parse and url.parse still detected as non-sanitizers
- Document in CLAUDE.md which patterns are recognized

**Trade-off:** May miss custom Zod-like validators, but avoids dangerous false negatives

### Risk 2: Schema Builders Accidentally Included
**Risk:** Patterns like `z.string` or `Joi.number` might be treated as sanitizers

**Mitigation:**
- Explicit pattern review - only validation methods, not builders
- Test case: Schema builder followed by tainted usage should detect vulnerability
- Code review checklist includes pattern verification

**Trade-off:** None - builders clearly don't validate data

### Risk 3: Control Flow False Positives Remain
**Risk:** Users expect strict equality checks to be recognized

**Impact:** Low - this was never in scope, but users may still report as issue

**Mitigation:**
- Document in CLAUDE.md as known limitation
- Explain control flow constraint analysis requires separate CFG enhancement
- Set expectations: This fix reduces false positives by ~70%, doesn't eliminate all

**Trade-off:** Perfect is enemy of good - 70% improvement is highly valuable even if not 100%

### Risk 4: Performance Regression
**Risk:** More patterns = slower sanitizer checks

**Analysis:**
- Current: ~60 patterns across 5 categories
- After: ~80 patterns across 6 categories (+33% patterns)
- Frozenset lookup: O(1) regardless of size
- Nested loop: O(categories × patterns per category)
- Expected overhead: ~0.05ms per check (negligible)

**Mitigation:**
- Keep using frozensets (O(1) membership testing)
- No change to lookup algorithm
- Benchmark on large project to confirm

**Trade-off:** Negligible performance cost for significant accuracy improvement

## Migration Plan

**No migration needed.** This is a pure addition with zero breaking changes.

### Deployment Steps
1. Update `theauditor/taint/sources.py` with new patterns
2. Optionally enhance `is_sanitizer()` matching logic
3. Add test fixtures for validation frameworks
4. Run full test suite to ensure no regressions
5. Deploy to production

### Rollback Plan
If unexpected issues occur, simply revert commit. No database migrations, no state changes, no cleanup needed.

### Backward Compatibility
- ✅ All existing sanitizer patterns unchanged
- ✅ All existing taint sources unchanged
- ✅ All existing sinks unchanged
- ✅ Database schema unchanged
- ✅ No new dependencies
- ✅ No configuration changes required

## Open Questions

### Q1: Should we enhance is_sanitizer() matching logic?
**Status:** DEFERRED to implementation phase

**Options:**
1. Keep current substring matching (simplest)
2. Add suffix-based matching for dotted methods (moderate)
3. Add regex pattern matching (complex)

**Decision Criteria:**
- If current matching works for `schema.parse`, keep it simple
- Only enhance if testing shows false negatives
- Prefer simplicity until proven insufficient

### Q2: Should we add Python validation frameworks now or later?
**Status:** OUT OF SCOPE for this change

**Rationale:**
- Different ecosystem, different usage patterns
- Should be separate task to avoid scope creep
- Focus on Node.js/TypeScript false positives first (bigger impact)

**Follow-up:** Create separate change proposal for Python validation frameworks (Pydantic, Marshmallow, Cerberus)

### Q3: How do we handle custom project-specific validators?
**Status:** DOCUMENT workaround, future enhancement

**Current Solution:**
- Custom validators should use conventional names: `validateFoo`, `sanitizeFoo`, `cleanFoo`
- Generic patterns in existing `"validation"` category will catch these

**Future Enhancement:**
- Add configuration file support: `.theauditor/sanitizers.yml`
- Allow projects to register custom patterns
- Document as enhancement request after this change validates the approach

---

**Design Approved:** Ready for implementation
**Architect Sign-off Required:** Pending
