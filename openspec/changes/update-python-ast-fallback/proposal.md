## Why
- Architect (user) directed the coder to investigate lint failures where Python imports were no longer captured; verification (2025-10-15) traced the regression to Tree-sitter payloads replacing CPython st.Module objects, leaving efs empty.
- Python extractor helpers in 	heauditor/indexer/extractors/python.py and 	heauditor/ast_extractors/python_impl.py explicitly require the built-in AST structure; they were not refactored when Tree-sitter support was enabled in ASTParser.
- Teamsop v4.20 mandates restore-before-build behaviour and documented verification prior to action; we already logged hypotheses, evidence, and discrepancies in this session and must encode the fix plan before touching code.
- Architect clarified that Python should stick with the superior CPython AST path unless/until Tree-sitter parity is implemented, and requested an OpenSpec proposal reflecting today’s discussion to remove ambiguity.

## What Changes
- Update 	heauditor/ast_parser.ASTParser so Python parsing (file, content, and batch flows) consistently yields 	ype="python_ast" payloads backed by CPython st.AST objects; Tree-sitter remains available for other languages.
- Add defensive logic making the Python path explicit (e.g., bypass Tree-sitter initialization or coerce Tree-sitter results back to st), ensuring downstream extractors continue to function even if Tree-sitter libraries are present.
- Extend automated coverage to assert that Python import extraction still works when the parser is configured with Tree-sitter support, preventing silent regressions.
- Document the behaviour in the Python indexer spec so future Tree-sitter integration attempts are gated on extractor support rather than implicit parser swaps.

## Impact
- Restores Python import/reference extraction, re-enabling lint and graph features that depend on efs rows.
- Keeps other Python extractor capabilities (assignments, function calls, taint metadata) on their proven code path without additional refactors.
- Provides a specification guardrail describing why CPython AST is currently required, reducing the risk of repeat regressions when parser internals change.

## Verification Alignment
- Verification notes (hypotheses, evidence, discrepancies) captured in openspec/changes/update-python-ast-fallback/verification.md per SOP v4.20.
- Follow-up work will include post-implementation audits and validation runs before status changes.
