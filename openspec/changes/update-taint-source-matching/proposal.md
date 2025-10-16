## Why
- The TypeScript audit in docs/.pf/ reported only 7 sources and 0 flows, while the self-audit dataset in .pf/ still surfaces 1 002 taint paths; the regression stops TypeScript customers from receiving actionable findings.
- Root cause analysis shows the extractor now records bare property identifiers (ody, params) instead of the dotted accessors (eq.body) that ind_taint_sources expects (see verification.md).
- Without a fallback, taint analysis silently succeeds yet returns an empty result set, leaving teams blind to flow vulnerabilities in TypeScript stacks.

## What Changes
- Restore full accessor names in the TypeScript semantic extractor so symbols.name once again contains dotted taint sources (e.g., eq.body, equest.params).
- Harden ind_taint_sources and the memory cache mirror to cross-reference ssignments and unction_call_args whenever dotted symbols are missing, ensuring regressions cannot zero out source discovery.
- Add regression coverage that exercises both the restored dotted-symbol path and the new fallback using TypeScript fixtures.
- Refresh taint pipeline documentation to clarify source expectations and call out the new fallback behaviour, plus guidance on large dogfooding artifacts (3 MB taint JSON) so customers understand noisier self-test data.

## Impact
- Restores parity between JavaScript/TypeScript and other languages in the taint analyzer, re-enabling flow detection for Express/Vite applications.
- Introduces defensive source discovery so future extractor drift degrades gracefully instead of producing empty reports.
- Provides clearer operational guidance on taint artifacts, helping teams distinguish fixture-heavy dogfooding output from real project findings.

## Verification Alignment
- Evidence and discrepancies captured in openspec/changes/update-taint-source-matching/verification.md per SOP v4.20.
