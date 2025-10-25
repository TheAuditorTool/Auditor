# Completion Report
Phase: MM-1  
Objective: Document the multi-hop taint investigation history, outcomes, and remaining risks.  
Status: COMPLETE

## 1. Verification Phase Report (Pre-Implementation)

| Hypothesis | Verification |
| --- | --- |
| H1: Stage 3 CFG analysis was limited to same-file flows because cross-file traversal was broken. | ✅ Confirmed via `aud full` (29 paths, all same-file) and Stage 3 logs showing the worklist stopping at `AccountService.createAccount`. |
| H2: The repo_index.db, ORM sink data, and call graph lacked the necessary cross-file facts. | ✅ Verified by querying `.pf/repo_index.db` (304 sources, 363 sinks, `function_call_args.callee_file_path` populated). |
| H3: Enabling `--no-rules` would not alter the cross-file behaviour. | ✅ `aud taint-analyze --no-rules` still returned 29 paths pre-fix. |
| H4: Memory-cache mode produced the same results as disk mode. | ❌ False. Manual `trace_taint(..., use_memory_cache=False)` yielded 204 paths with cross-file flows, pointing at cache omissions. |

**Discrepancies Found**
- Cached sink lookups silently discarded ORM sinks (`Account.create`, etc.), so Stage 3 never saw the service-layer targets once the cache was engaged.
- Stage 3 logs omitted any evidence of matching sink parameters when destructured object fields were involved (e.g. `data.company_name`).

## 2. Deep Root Cause Analysis

- **Surface Symptom:** Stage 3 multi-hop taint capped out at 29 same-file flows; controller → service → ORM paths never materialised in `taint_analysis.json`.
- **Problem Chain:**
  1. Memory cache pre-computation only indexed explicit pattern matches. ORM sinks were dropped when using preloaded cache.
  2. Sink argument matching depended solely on raw string containment, missing expressions like `data.company_name`.
  3. Interprocedural traversal lost track of the original controller source once taint moved into services, so even recovered sinks would not record the correct origin.
  4. Flow-insensitive path search grouped tainted elements by display name only, losing canonical identity and file path for cross-file calls.
- **Actual Root Cause:** Cached sink precomputation failed to preserve ORM results and interprocedural plumbing lost source provenance, preventing multi-hop matches despite the database being correct.
- **Historical Context:** Earlier sessions addressed crashes and call-site grouping, but we never realigned the cache or path metadata after the “truth courier” refactor.

## 3. Implementation Details & Rationale

### Files Modified
- `theauditor/taint/cfg_integration.py` (lines 439‑470)
- `theauditor/taint/interprocedural.py` (lines 61‑311)
- `theauditor/taint/propagation.py` (lines 360‑585)
- `theauditor/taint/memory_cache.py` (lines 116‑976)

### Decision Log
1. **Augment sink evidence gathering**  
   - *Location:* `theauditor/taint/cfg_integration.py:439`  
   - *Why:* Object literals such as `Account.create({ company_name: data.company_name })` exposed fields via `variable_usage`, not raw argument strings. Incorporating that metadata allows Stage 3 to recognise tainted sub-properties.

2. **Preserve canonical origin across interprocedural stages**  
   - *Location:* `theauditor/taint/interprocedural.py:74`, `:216`, `:284`  
   - *Why:* By threading the original controller source dict through both Stage 2 and Stage 3, and normalising function lookups with `resolve_function_identity`, cross-file paths now reference the true origin instead of the service scope.

3. **Group tainted elements by canonical function identity**  
   - *Location:* `theauditor/taint/propagation.py:360`  
   - *Why:* Previous logic keyed by display name, so aliases (`accountService.createAccount`) obscured cross-file lookups. Canonical grouping retains aliases, resolved file paths, and function lines for accurate traversal.

4. **Cache ORM sinks explicitly**  
   - *Location:* `theauditor/taint/memory_cache.py:116`, `:623`, `:843`, `:973`  
   - *Why:* When the cache is active the analyzer relies solely on precomputed sink tables. Persisting ORM queries in `precomputed_orm_sinks` re-aligns cached results with the disk-backed behaviour that previously surfaced multi-hop flows.

## 4. Edge Case & Failure Mode Analysis

- **Object literal / destructuring:** Covered via `variable_usage` lookup; confirmed by detecting `data.company_name` → `Account.create` on `account.service.ts:93`.
- **Canonical name mismatches:** `resolve_function_identity` handles aliases (e.g. `this.getOffset`, `accountService.createAccount`), preventing Stage 3 from falling back to normalised placeholders that lack symbol table entries.
- **Cache vs Disk Consistency:** Verified both `trace_taint(..., use_memory_cache=True)` and `aud taint-analyze` now agree (204 paths, 6 cross-file flows).
- **Fallback Safety:** The new logic preserves prior fallbacks (simple argument search) should the usage table be empty, preventing regressions in minimal projects.

## 5. Post-Implementation Integrity Audit

Files re-read in full:
- `theauditor/taint/cfg_integration.py`
- `theauditor/taint/interprocedural.py`
- `theauditor/taint/propagation.py`
- `theauditor/taint/memory_cache.py`

Result: ✅ No syntax issues; canonical-name handling and cache additions integrate cleanly with existing code paths.

## 6. Impact, Reversion, & Testing

- **Impact:** `aud taint-analyze --json --no-rules` now yields 204 findings with controller → service → ORM flows; `aud full` reports the same, confirming cache parity.
- **Reversion Plan:** All changes are reversible via `git checkout -- <files>`; no schema or data migrations introduced.
- **Testing Performed:**
  - `aud taint-analyze --verbose` (multiple runs)
  - `aud taint-analyze --json --no-rules`
  - `aud full`
  - Direct `trace_taint` calls with and without cache to cross-check counts.

---

## Experiment Log (Chronological)

1. **Baseline Reproduction**  
   - `aud full` & `aud taint-analyze` → 29 paths, all same-file. Stage 3 logs stalled at `AccountService.createAccount`.

2. **Schema/Sink Validation**  
   - Queried `.pf/repo_index.db` manually to confirm sources, sinks, and cross-file call metadata—no data gaps.

3. **No-Rules Variant**  
   - `aud taint-analyze --no-rules` still capped at 29 → ruled out rule orchestrator as root cause.

4. **Direct `trace_taint` Disk Mode**  
   - `trace_taint(..., use_memory_cache=False)` surfaced 204 paths (including cross-file) → cache divergence identified.

5. **Cache Inspection**  
   - Found `precomputed_sinks` omitted ORM entries and canonical grouping collapsed alias information.

6. **Patch Iterations**  
   - a) Added `variable_usage` check (0 regression).  
   - b) Introduced origin threading & canonical identity (initial attempt caused `source_info` NameError; fixed by passing copies).  
   - c) Reworked propagation grouping to exploit canonical names.  
   - d) Extended cache precomputation to persist ORM sinks and include them during lookup.

7. **Verification Runs**  
   - `aud taint-analyze --json --no-rules` → 204 findings.  
   - `aud full` → same 204 findings with Stage 3 logging canonical name lookups succeeding.

## Known Gaps & Future Work

- **Dynamic Dispatch Coverage:** The cache still relies on pattern-matched call expressions; more complex ORM access via helper wrappers may require additional precomputation.  
- **CFG Entry Resolution:** Functions lacking CFG metadata still fall back to line 1; consider enriching the symbol table with start/end ranges for arrow functions.  
- **Performance:** ORM sink duplication increases cached sink count; large monorepos should be profiled to ensure acceptable memory (currently ~46 MB).  
- **Validation Tests:** Add regression tests for cached vs. uncached taint analysis to prevent future divergence.

## Recommended Next Steps

1. Add automated tests comparing cache/no-cache `trace_taint` outputs on representative fixtures.  
2. Extend sink argument analysis to cover template literal concatenations for completeness.  
3. Document the canonical-name workflow in `docs/taint.md` so future refactors preserve provenance threading.
