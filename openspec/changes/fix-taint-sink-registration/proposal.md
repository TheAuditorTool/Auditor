# Fix Taint Sink Registration Pattern Mismatch

## Why

The `api_auth_analyze.py` rule registers 43 URL path patterns ("user", "token", "password") as taint sinks. The taint analyzer interprets these as variable names, creating 589 false positive findings and degrading performance 6x (3.9min → 23.7min).

**Root Cause**: Semantic mismatch between rule intent (URL endpoint detection) and registry usage (variable/function name matching).

**Evidence**: Database analysis confirms 3918 sinks registered (vs 95 hardcoded), with garbage patterns present in dynamic sinks. The registry integration exposed a latent bug in rule pattern registration.

## What Changes

- **Fix `api_auth_analyze.py`**: Remove or refactor `register_taint_patterns()` to NOT register URL patterns as taint sinks (lines 542-543)
- **Audit 22 rules**: Check all rules with `register_taint_patterns()` for similar pattern mismatches
- **Add registry validation**: Reject patterns that match common variable names ("user", "token", "password", "admin", "config")
- **Performance restoration**: Return to 3.9min analysis time with 95-353 legitimate sinks

**Impact**: Eliminates 589 false positives, restores 6x performance improvement.

## Impact

- **Affected specs**: `taint-analysis` (sink registration)
- **Affected code**:
  - `theauditor/rules/security/api_auth_analyze.py:542-543` (primary fix)
  - `theauditor/taint/registry.py` (add validation)
  - 22 rules with `register_taint_patterns()` (audit)
- **Breaking changes**: None (removes false positives only)
- **Performance impact**: -6x (from 23.7min back to 3.9min)

## Non-Goals

- Revert registry integration (registry is correct and provides value)
- Remove SENSITIVE_OPERATIONS patterns entirely (still valid for URL matching rules)
- Change taint analyzer sink matching logic
