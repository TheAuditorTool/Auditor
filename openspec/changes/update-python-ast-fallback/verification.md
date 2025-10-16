# Verification – update-python-ast-fallback

## Hypotheses
1. Python import extraction still receives CPython st.Module trees.
2. Tree-sitter Python output is normalized before reaching the extractor.
3. Regression is isolated to database ingestion, not AST creation.

## Evidence
- python -c 'from theauditor.ast_parser import ASTParser; ...' showed 	ree['type'] == "tree_sitter" and 	ree['tree'] as 	ree_sitter.Tree (see session log 2025-10-15).
- PythonExtractor._extract_imports_ast in 	heauditor/indexer/extractors/python.py:280-321 returns early unless it receives an st.Module.
- Helpers in 	heauditor/ast_extractors/python_impl.py also call st.walk and therefore fail with Tree-sitter payloads.
- Database writes in _store_extracted_data (theauditor/indexer/__init__.py:626-642) never execute because imports is empty, explaining the missing lint refs.

## Discrepancies
- Tree-sitter enablement for Python was shipped without updating extractor logic, contrary to architect expectation that language-specific impls handled AST diversity.
- Existing unit tests only cover the CPython AST path, so CI missed the regression.

## Conclusion
Tree-sitter Python output bypasses all existing extractor logic. Restoring CPython AST payloads (or adding dedicated Tree-sitter handlers) is required before any further lint/index work. Architect approved reverting to CPython AST as the superior near-term option and requested this OpenSpec change prior to implementation.
