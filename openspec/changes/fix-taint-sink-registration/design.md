# Design: Fix Taint Sink Registration Pattern Mismatch

## Context

TheAuditor's taint analysis system uses a registry to collect sink patterns from security rules. Rules can contribute domain-specific patterns by implementing `register_taint_patterns(registry)`.

**The Bug**: `api_auth_analyze.py` registers 43 URL path segments ("user", "admin", "token") as taint sinks. The taint analyzer searches the `symbols` table for these patterns, matching common variable names instead of API endpoints.

**Timeline**:
- **v1.0**: Registry existed but not integrated with taint analysis
- **v1.1**: Rules refactored, api_auth_analyze.py created with wrong pattern intent
- **Today**: Registry integration added, exposing latent bug
- **Result**: 10 findings → 595 findings (589 false positives), 6x performance regression

## Goals

1. Fix api_auth_analyze.py to NOT register URL patterns as taint sinks
2. Add registry validation to prevent similar bugs
3. Audit all 22 rules for pattern correctness
4. Restore performance to 3.9min

## Non-Goals

- Revert registry integration (provides valuable extensibility)
- Remove SENSITIVE_OPERATIONS patterns (still valid for endpoint detection)
- Change taint analyzer matching logic (working as designed)

## Decisions

### Decision 1: Separate Pattern Sets

**Choice**: Split `SENSITIVE_OPERATIONS` into two sets:
- `SENSITIVE_URL_PATTERNS` - For endpoint detection rules (stays in api_auth_analyze.py)
- `SENSITIVE_FUNCTIONS` - For taint analysis registration (NEW, if needed)

**Rationale**:
- URL patterns and code patterns serve different purposes
- Endpoint detection queries `api_endpoints` table (has URL context)
- Taint analysis queries `symbols` table (has variable/function context)
- Clear separation prevents future confusion

**Alternatives Considered**:
1. ❌ Remove registration entirely: Loses extensibility, forces hardcoded patterns
2. ❌ Change taint analyzer to filter out generic patterns: Hides root cause, adds complexity
3. ✅ Split patterns by intent: Clear, maintainable, preserves both use cases

### Decision 2: Registry Validation Strategy

**Choice**: Add validation at registration time with warning-level feedback.

**Validation Rules**:
1. Pattern length: Warn if <4 characters (too generic)
2. Common names: Warn if in `COMMON_VARIABLE_NAMES` frozenset
3. Naming convention: Warn if no camelCase/snake_case/dot notation
4. Optional strict mode: Fail registration if validation fails

**Rationale**:
- Catch bugs at registration time, not analysis time
- Warnings allow gradual migration (strict mode for new rules)
- Logging provides context for debugging (which rule, which pattern)

**Implementation**:
```python
# theauditor/taint/registry.py
COMMON_VARIABLE_NAMES = frozenset([
    'user', 'token', 'password', 'admin', 'config', 'key', 'secret',
    'data', 'result', 'value', 'item', 'obj', 'response', 'request'
])

def register_sink(self, pattern: str, category: str, language: str):
    # Validation checks
    if len(pattern) < 4 and not pattern.isupper():  # Allow SQL, XSS
        logger.warning(f"Sink pattern '{pattern}' is very short (category={category})")

    if pattern.lower() in COMMON_VARIABLE_NAMES:
        logger.warning(f"Sink pattern '{pattern}' matches common variable name (category={category})")

    # Existing registration logic...
```

### Decision 3: Rule Audit Approach

**Choice**: Systematic audit of all 22 rules with `register_taint_patterns()`.

**Audit Criteria**:
1. Are patterns code-level (functions, methods, properties)?
2. Do patterns include object qualifiers (e.g., `db.query` not just `query`)?
3. Are patterns language-specific (avoid generic keywords)?
4. Do patterns have test coverage?

**Process**:
1. Grep for all `register_taint_patterns` implementations
2. For each rule, check pattern intent vs actual patterns
3. Verify against validation rules
4. Document findings in `audit_taint_patterns.md`
5. Fix any violations found

**Time Estimate**: 2-3 hours (5-10 min per rule × 22 rules)

## Risks & Trade-offs

### Risk 1: Breaking Legitimate Patterns
**Mitigation**: Use warnings, not errors. Add `--strict-registry` flag for opt-in enforcement.

### Risk 2: Audit Uncovers More Bugs
**Mitigation**: Document all findings, prioritize by impact. Fix critical bugs in this change, defer minor issues to future changes.

### Risk 3: Performance Still Degraded
**Mitigation**: Measure before/after sink counts and runtime. If >200 sinks remain, investigate further.

## Migration Plan

### Phase 1: Fix api_auth_analyze.py (low risk)
1. Deploy fix to api_auth_analyze.py
2. Verify sink count drops to <200
3. Verify performance returns to 3.9min
4. If successful, proceed to Phase 2

### Phase 2: Add Registry Validation (medium risk)
1. Add validation logic to registry.py
2. Run full analysis, collect warnings
3. Verify no false warnings on legitimate patterns
4. If warnings are accurate, proceed to Phase 3

### Phase 3: Audit All Rules (high effort)
1. Systematic audit of 22 rules
2. Fix any violations found
3. Add unit tests for validation
4. Enable `--strict-registry` in CI

### Rollback Plan
If performance doesn't improve:
1. Revert api_auth_analyze.py changes
2. Add rule-specific exclusion in registry (temporary)
3. Investigate taint analyzer sink matching logic

## Open Questions

1. **Q**: Should registry validation be opt-in or opt-out?
   **A**: Opt-in strict mode for now (backwards compatible)

2. **Q**: Are there legitimate use cases for generic patterns like "user"?
   **A**: No - taint analysis should track data flow, not keyword presence

3. **Q**: Should we add category-specific validation rules?
   **A**: Yes - "sql" category patterns should look like SQL commands, "xss" should look like output functions

## Success Metrics

- ✅ Sink count: 95-150 (vs 353 broken, 95 baseline)
- ✅ Runtime: <5 minutes (vs 23.7min broken, 3.9min baseline)
- ✅ False positives: 0 with "user"/"token"/"password" as sink patterns
- ✅ Audit complete: All 22 rules verified
- ✅ Validation enabled: Warnings logged for invalid patterns
