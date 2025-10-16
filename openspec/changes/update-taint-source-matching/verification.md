# Verification Report - update-taint-source-matching
Generated: 2025-10-15T21:52:00+00:00
SOP Reference: Standard Operating Procedure v4.20

## Hypotheses & Evidence

1. Taint source discovery depends on symbols.name storing full dotted accessors such as eq.body.
   - Evidence: 	heauditor/taint/database.py:60 builds a query constrained to symbols with (type = 'call' OR type = 'property' OR type = 'symbol') AND name LIKE ? for dotted patterns.
   - Evidence: 	heauditor/taint/memory_cache.py:905 mirrors the same assumption when scanning cached symbol["name"] values for dotted strings.

2. The TypeScript extractor currently writes property identifiers without their base object, losing the dotted form the taint analyzer expects.
   - Evidence: 	heauditor/indexer/extractors/javascript.py:266 appends prop.get('name') directly as the symbol 
ame, which contains only the terminal identifier when fed by the 	sc_* helpers.
   - Evidence: Querying docs/.pf/repo_index.db with SELECT DISTINCT name FROM symbols WHERE type='property' AND path='backend/src/controllers/account.controller.ts' shows entries like ('body',) rather than ('req.body',).

3. Downstream tables still capture request usage, proving the indexer saw the data even though the symbols view dropped dotted names.
   - Evidence: docs/.pf/repo_index.db contains 199 rows in unction_call_args whose rgument_expr begins with eq. and 231 ssignments.source_expr rows with the same prefix (validated via targeted COUNT(*) queries).

4. Our self-audit dataset retains the expected dotted symbols, so the regression is local to the TypeScript semantic pipeline.
   - Evidence: .pf/repo_index.db (project root) still lists eq.body and eq.params in symbols.name, demonstrating the analyzer works when dotted names survive extraction.

5. The taint pipeline completed without runtime errors but reported zero flows because the source list collapsed.
   - Evidence: docs/.pf/pipeline.log:137 states "Found 7 taint sources / 744 security sinks / 0 taint paths" right after the taint track finished.
   - Evidence: docs/.pf/raw/taint_analysis.json records "paths": [] and "total_vulnerabilities": 0 despite uploading the same sink catalog.

## Discrepancies & Alignment Notes
- Symbols should include both the leaf identifier and its fully-qualified accessor so existing taint logic stays compatible across Python, Tree-sitter, and TypeScript backends.
- ind_taint_sources needs a defensive path that leverages unction_call_args and ssignments when dotted symbols are missing so regressions do not zero out findings.

## Conclusion
The truth pipeline is intact, but the TypeScript extraction stage dropped dotted property names, starving taint source discovery. Restoring full accessor names (or enriching the analyzer with fallbacks) will realign the database with the taint engine while preserving current sink coverage.
