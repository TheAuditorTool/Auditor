# Design: Schema Validation System

**Change ID**: `schema-validation-system`

## Context

Schema-driven refactor (v1.3.0) eliminated 8,691 lines of manual cache loaders but introduced new failure mode: forgetting to regenerate code after schema changes.

**Current**: 154 schema tables, 125 generated classes (29 missing)

## Goals / Non-Goals

**Goals**:
- Detect stale code via SHA-256 hash
- Auto-regenerate in dev mode
- Hard fail in CI/CD
- <50ms import overhead

**Non-Goals**:
- Validate semantic correctness (trust codegen)
- Add migration system (DB regenerated fresh)

## Key Decisions

### Decision 1: Hash-Based Detection
Use SHA-256 of schema structure (table names, columns, types, indexes). Fast (<5ms), reliable, comprehensive.

**Alternative rejected**: Timestamp comparison (unreliable with git)

### Decision 2: 3-Layer Defense
- **Layer 1**: Import-time (auto-fix dev, warn prod)
- **Layer 2**: CLI (`aud schema --check/--regen`)
- **Layer 3**: Tests (hard fail CI)

**Alternative rejected**: Single layer (insufficient coverage)

### Decision 3: Dev vs Prod Behavior
- **Dev mode** (git repo exists): Auto-regenerate with warning
- **Prod mode** (pip install): Hard fail with instructions
- **Bypass**: THEAUDITOR_NO_VALIDATION=1

**Alternative rejected**: Always fail (too much friction)

## Risks / Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Import overhead | Low | Medium | Hash caching, <50ms target |
| Validation breaks imports | Low | High | Env var bypass |
| Codegen errors | Low | High | Rollback via git revert |
| Developer bypass | Medium | Medium | Test enforcement in CI |

## Architecture

```
schemas/__init__.py → SchemaValidator
                       ├→ compute_hash()
                       ├→ validate()
                       └→ regenerate()

CLI: aud schema --check/--regen
Tests: test_schema_integrity.py
```

## Performance

- Hash computation: ~5ms for 154 tables
- File checks: ~1ms
- Total overhead: <50ms (cached after first check)

## Migration Plan

No migration needed. New files only, no schema changes.

**Rollback**: `git revert HEAD`
