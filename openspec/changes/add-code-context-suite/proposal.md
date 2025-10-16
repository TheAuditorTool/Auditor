## Why
- Current `aud` workflows surface security truth but still force assistants to query multiple artifacts (SQLite manifests, graph DB, taint JSON) manually for context.
- Claude Compass already bundles overview and cross-stack capsules; we record richer facts in `.pf` but lack a turnkey command that assembles them.
- Analysts have asked for single-command context packs and a "give me everything" export so AI agents can prime themselves without bespoke SQL.

## What Changes
- Promote `aud context` into a command group that keeps the YAML semantic analyzer under `aud context semantic` while adding a `code` subcommand.
- Assemble overview, targeted neighborhoods (file/symbol/route), cross-stack, and full-context presets directly from `.pf/repo_index.db`, `.pf/graphs.db`, and existing courier JSON.
- Extend the CLI with a `--full` option that emits a consolidated payload (raw + chunked) so assistants can consume the entire context pack at once.
- Annotate every emitted fact with provenance pointing to the exact table or courier file used, preserving the Truth Courier contract.
- Refresh `aud --help`, `aud context --help`, and `aud context code --help` with AI-first guidance and runnable SQLite/Python examples.

## Impact
- Delivers Claude Compass-style dependency context without new infrastructure, leveraging the authoritative truth already captured by TheAuditor.
- Gives both humans and AI a single entry point for structural understanding, reducing manual SQL and command juggling.
- Demonstrates parity—if not superiority—over Compass while staying offline-first and sandbox friendly.

## Verification Alignment
- Evidence collected in `openspec/changes/add-code-context-suite/verification.md` per SOP v4.20.
- Architectural details and data sources recorded in `design.md` for review.
