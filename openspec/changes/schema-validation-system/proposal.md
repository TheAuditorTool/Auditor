# Proposal: Schema Validation System

**Change ID**: `schema-validation-system`
**Status**: Awaiting Architect Approval
**Date**: 2025-01-03

## Why

Schema defines 154 tables but generated code has only 125 accessor classes (29 missing). No validation system exists to detect when generated code becomes stale after schema changes.

**Verified Root Cause**: Missing validation layer in schema-driven architecture (see verification.md for 8 confirmed hypotheses).

## What Changes

Add 3-layer validation system:
1. **Import-time validation** - Auto-regenerates stale code in dev mode (<50ms)
2. **CLI commands** - `aud schema --check` and `--regen` for manual control
3. **Test enforcement** - pytest tests catch staleness in CI/CD

**New Files**: validator.py, schema.py command, test_schema_integrity.py, .schema_hash
**Modified**: __init__.py (import hook), codegen.py (write hash), cli.py (register command), .gitignore

## Impact

- **Affected Specs**: NEW schema-validation capability
- **Breaking Changes**: None
- **Risk**: 🟢 LOW (fallback via THEAUDITOR_NO_VALIDATION=1)
- **Time**: 70 minutes (5 min immediate fix + 65 min validation system)

## Authorization Request

Please approve:
- **Option A**: Full implementation (Phase 1-6, 70 min)
- **Option B**: Phase 1 only (fix 29 classes, 5 min)
- **Option C**: Request revisions
- **Option D**: Reject
