## Why
- Security/PII rules (`secret-hardcoded-assignment`, `crypto-weak-encryption`, `pii-*`) still rely on substring heuristics from the pre-normalized indexer.
- After the Phase 3 normalization, the DB differentiates literal values, call metadata, and API definitions. The outdated heuristics now raise high volumes of false positives (e.g., header lookups, `.includes(` calls, `message` fields).
- These false positives erode trust in the SAST output and block downstream consumers (LLMs, CI) from acting on findings.

## What Changes
- Update affected rule modules to query structured columns (assignments/literals/call metadata/API tables) instead of raw substrings.
- Harden helper logic (e.g., `_contains_alias`) to operate on normalized call names/tokens.
- Add regression coverage using the lovaseo samples so the noisy patterns stay quiet.
- Refresh documentation/comments for the rules to note the schema dependency.

## Impact
- Restores high-signal findings for secret detection, crypto usage, and PII exposure checks.
- Reduces unnecessary remediation cycles for users running `aud full`.
- Provides a repeatable template for future rule migrations to the normalized schema.
