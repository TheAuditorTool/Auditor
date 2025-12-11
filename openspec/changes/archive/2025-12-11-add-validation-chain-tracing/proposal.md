# Proposal: Add Validation Chain Tracing

## Why

Current `aud boundaries` measures "distance to validation" - an architectural metric about function call depth. This is NOT what security practitioners need. They need:

1. **Trust boundary validation** - Is input validated? Is output sanitized? Are DB writes safe?
2. **Chain integrity** - Does validation HOLD through the entire data flow, or does it break when someone casts to `any`?
3. **Teachable format** - Vibe coders don't know validation exists; show them WHERE it breaks in a visual chain

The current tool says "validation at distance 2" which means nothing for security. The new capability shows:
```
POST /users (body: CreateUserInput)
    │ [PASS] Zod validated at entry
    ↓
userService.create(data: CreateUserInput)
    │ [PASS] Type preserved
    ↓
repo.insert(data: any)        ← CHAIN BROKEN
    │ [FAIL] Cast to any - validation meaningless now
    ↓
db.query(sql)                 ← Unvalidated data hits DB
```

This is validation-aware taint tracking that teaches developers WHERE their validation fails.

## What Changes

1. **`aud boundaries --validated`** - Validation chain tracing (NEW)
   - Traces validation from entry point through data flow
   - Detects chain breaks: `any` casts, type assertions, untyped intermediates
   - Shows visual chain with PASS/FAIL at each hop
   - Teachable format for vibe coders

2. **`aud boundaries --audit`** - Security boundary audit (NEW)
   - Comprehensive trust boundary checklist
   - INPUT: Zod/Joi/Yup validation at entry points
   - OUTPUT: HTML escaping, XSS prevention
   - DATABASE: Parameterized queries, SQLi prevention
   - FILE: Path traversal checks

3. **`aud explain <file> --validated`** - Validation story for file (NEW)
   - Shows validation chain for all entry points in file
   - Integrates with existing explain output

4. **`aud blueprint --validated`** - Validation summary (NEW)
   - Shows codebase-wide validation chain health
   - Percentage of chains intact vs broken

## Impact

- **Affected specs**: `polyglot-boundaries` (MODIFIED - add new requirements)
- **Affected code**:
  - `theauditor/boundaries/boundary_analyzer.py` - Add chain tracing logic
  - `theauditor/boundaries/chain_tracer.py` - NEW: Validation chain analysis
  - `theauditor/boundaries/security_audit.py` - NEW: Trust boundary audit
  - `theauditor/commands/boundaries.py` - Add `--validated` and `--audit` flags
  - `theauditor/commands/explain.py` - Add `--validated` flag
  - `theauditor/commands/blueprint.py` - Add `--validated` flag

## Non-Goals (Explicitly Out of Scope)

- **Recommendations**: We do NOT recommend adding Zod. We show facts about where validation exists/breaks.
- **Distance scoring**: The current distance-based scoring stays as-is. This is additive.
- **Runtime analysis**: Static analysis only. No dynamic/runtime validation checking.

## Breaking Changes

None. All new flags are additive to existing behavior.
