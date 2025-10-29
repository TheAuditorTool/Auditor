## 1. Planning & Verification
- [x] 1.1 Capture reproduction evidence (logs/snippets) for each affected rule
- [x] 1.2 Review existing rule metadata to confirm scope/extensions/exclusions

## 2. Implementation
- [x] 2.1 Update secret detection rule to check assignment literal metadata
- [x] 2.2 Update crypto weak algorithm rule to use structured call identifiers
- [x] 2.3 Update PII exposure/error/storage rules to use normalized API/assignment data
- [x] 2.4 Add regression tests covering lovaseo scenarios (unit + integration snapshots)

## 3. Validation & Docs
- [x] 3.1 Run `pytest` suites and targeted CLI smoke tests
- [x] 3.2 Re-run `aud detect-patterns` on lovaseo to confirm reductions
- [x] 3.3 Update rule documentation/comments where behavior changed
