# Design Document - update-taint-source-matching
Generated: 2025-10-16
SOP Reference: Standard Operating Procedure v4.20

## 1. Problem Statement
- TypeScript files indexed via the semantic pipeline record property symbols as leaf identifiers (e.g., `body`) rather than dotted accessors (`req.body`).
- Taint analyzer functions (`theauditor/taint/database.py:19`, `theauditor/taint/memory_cache.py:846`) assume dotted names when matching `TAINT_SOURCES`, so the source discovery step collapses for TypeScript projects.
- Downstream tables (`function_call_args`, `assignments`) still hold fully-qualified expressions, which the analyzer currently ignores, leading to zero taint paths despite the raw data being present.

## 2. Goals
1. Ensure JavaScript/TypeScript extraction preserves fully-qualified accessor names so taint source matching retains parity with Python.

## 3. Non-Goals
- No changes to framework registries or taint sink detection.
- No modifications to pipeline orchestration or logging beyond what is required for the fallback notice.

## 4. Current Behaviour & Evidence
- `openspec/changes/update-taint-source-matching/verification.md` captures queries showing symbols table lacks dotted names while function calls contain `req.body`.
- `docs/fakeproj/project_anarchy/.pf/pipeline.log` reports "Found 7 taint sources...0 taint paths" in earlier runs before analyzer improvements.
- Prior self-audit `.pf/repo_index.db` still holds dotted names, confirming the regression is localized to the TypeScript extractor.

## 5. Proposed Changes
### 5.1 Extraction (JavaScript/TypeScript)
- Update `theauditor/indexer/extractors/javascript.py` so symbol emission includes fully-qualified names:
  - For property access nodes, concatenate base object + property name (`req.body`).
  - For nested accesses, ensure recursion preserves the complete path.
  - Maintain existing batch semantic parsing workflow; no regex fallbacks.
- Verify compatibility with React/JSX logic and ensure symbol counts remain stable.

### 5.2 Analyzer Fallback
- Extend `find_taint_sources` and `MemoryCache.find_taint_sources_cached` to:
  - Check `function_call_args.argument_expr` and `assignments.source_expr` when dotted symbols are missing.
  - Tag fallback results with metadata (e.g., `"source_variant": "fallback"`) so logs can highlight the degraded mode.
  - Maintain performance by reusing cached assignment/call indexes already loaded in memory cache.
- Log a warning when fallback triggers, advising teams to restore proper symbols.

### 5.3 Tests & Tooling
- Add fixture-driven tests covering:
  - TypeScript controller using `req.body` and `req.params`, asserting dotted symbols appear post-extraction.
  - Analyzer fallback scenario by stubbing symbol removal and verifying flows surface via assignments.
- Update documentation (flagged in tasks) describing source expectations and artifact size caveats.

## 6. Risks & Mitigations
- Risk: Concatenating accessors might double-count or clash with existing symbol naming.
  - Mitigation: Use structured traversal to build names (base + '.' + property) only for relevant node types; keep legacy behaviour for non-object accesses.
- Risk: Fallback could introduce false positives if unrelated assignments reference similar patterns.
  - Mitigation: Scope fallback to known HTTP request variables (req, request, ctx) or existing `TAINT_SOURCES` patterns; include metadata for manual review.
- Risk: Additional logging may confuse users.
  - Mitigation: Emit warnings only when fallback sources are generated, referencing documentation updates.

## 7. Dependencies & Coordination
- Coordinates with `update-indexer-language-parity` change to ensure object literal persistence (shared extractor module). Changes must avoid conflicting edits to `JavaScriptExtractor` or shared batching helpers.
- No external dependencies beyond existing test fixtures.

## 8. Rollout & Validation Plan
1. Implement extraction and analyzer updates behind unit/integration tests.
2. Re-run `aud index` and `aud taint-analyze` on `docs/fakeproj/project_anarchy` to confirm dotted symbols and restored taint paths.
3. Capture before/after metrics in `verification.md` per SOP (source counts, taint paths, fallback warnings if triggered).
4. Update documentation and finalize OpenSpec checklist before requesting architect approval.
