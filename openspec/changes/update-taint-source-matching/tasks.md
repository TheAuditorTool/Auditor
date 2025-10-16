## 0. Verification
- [x] Capture evidence of missing dotted property symbols in docs/.pf/repo_index.db and confirm pipeline symptoms in docs/.pf/raw/taint_analysis.json.

## 1. Extraction Fixes
- [ ] Update the TypeScript semantic extractor so property symbols retain their full accessor name (e.g., 
eq.body).
- [ ] Re-run the indexer against the sample repository to confirm dotted names reappear in symbols.name.

## 2. Analyzer Hardening
- [ ] Extend ind_taint_sources (and cache mirror) to fall back to ssignments / unction_call_args when dotted property symbols are absent.
- [ ] Add targeted regression coverage that exercises the fallback path with fixture data.

## 3. Pipeline & Docs
- [ ] Update any taint or pipeline documentation referencing source extraction assumptions.
- [ ] Capture before/after artifacts (taint JSON, pipeline log) demonstrating restored flows for the TypeScript project.

## 4. Spec & Review
- [ ] 4.1 Update OpenSpec requirements (this change) and secure architect approval before implementation.
