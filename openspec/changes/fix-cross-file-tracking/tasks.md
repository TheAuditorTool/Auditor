# Implementation Tasks

## 1. Fix Symbol Query Type Filter (15 minutes)
- [ ] 1.1 Read `theauditor/taint/interprocedural.py` lines 130-137 (flow-insensitive)
- [ ] 1.2 Change line 132: `where="(name = ? OR name LIKE ?) AND type = 'function'"` → `where="(name = ? OR name LIKE ?) AND type IN ('function', 'call', 'property')"`
- [ ] 1.3 Read `theauditor/taint/interprocedural.py` lines 452-456 (CFG-based)
- [ ] 1.4 Change line 453: Apply same type filter fix
- [ ] 1.5 Verify both locations use identical query pattern

## 2. Remove Silent Fallback (15 minutes)
- [ ] 2.1 Replace line 136-137 (flow-insensitive): Remove `if callee_location else current_file` ternary
- [ ] 2.2 Add explicit NULL check: `if not callee_location: continue` with debug log
- [ ] 2.3 Replace line 456 (CFG-based): Apply same fallback removal
- [ ] 2.4 Add debug logging: `print(f"[INTER-PROCEDURAL] Symbol not found: {callee_func} (normalized: {normalized_callee})", file=sys.stderr)`
- [ ] 2.5 Verify both code paths fail loudly if symbol not found

## 3. Database Validation (30 minutes)
- [ ] 3.1 Create test script `test_symbol_lookup.py` to verify query fix
- [ ] 3.2 Test broken query: `SELECT path FROM symbols WHERE name = 'query' AND type = 'function'` (expect NULL)
- [ ] 3.3 Test fixed query: `SELECT path FROM symbols WHERE name = 'query' AND type IN ('function', 'call', 'property')` (expect result)
- [ ] 3.4 Run validation on 10 common callees: db.query, app.post, res.send, etc.
- [ ] 3.5 Document success rate: expect 25% → 100% improvement

## 4. Integration Testing (1 hour)
- [ ] 4.1 Create test fixture: `controller.js` calling `service.js` calling `model.js` (3-hop chain)
- [ ] 4.2 Run `aud index` on fixture
- [ ] 4.3 Run `aud taint-analyze` with `THEAUDITOR_TAINT_DEBUG=1`
- [ ] 4.4 Verify debug output shows: "Following call across files: controller.js → service.js"
- [ ] 4.5 Query taint_paths: verify at least 1 cross-file path exists
- [ ] 4.6 Verify inter-procedural step types: `argument_pass`, `return_flow`, or `call` steps present

## 5. Full Codebase Testing (30 minutes)
- [ ] 5.1 Run `aud full` on TheAuditor itself
- [ ] 5.2 Query taint_analysis.json: count cross-file paths (expect > 0)
- [ ] 5.3 Verify no crashes from missing symbols (fallback removed cleanly)
- [ ] 5.4 If crashes occur, investigate indexer gaps and document in issue
- [ ] 5.5 Compare total path count: should be similar to baseline (880 paths)

## 6. Documentation (30 minutes)
- [ ] 6.1 Update CLAUDE.md: Document NO FALLBACK enforcement in cross-file tracking
- [ ] 6.2 Add "Known Issues" section: If symbol lookup fails, indexer must be fixed (not runtime)
- [ ] 6.3 Update interprocedural.py docstring: Document type filter rationale
- [ ] 6.4 Add comment at lines 132, 453: "CRITICAL: Include 'call' and 'property' types for JS/TS methods"
- [ ] 6.5 Update troubleshooting guide: "0 cross-file paths" → "Check symbol type distribution"
