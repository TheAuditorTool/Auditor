# Design: Python AST Fallback

## Verification Summary (SOP v4.20)
- Confirmed `ASTParser.parse_file` returns a Tree-sitter payload before the Python fallback when Tree-sitter bindings are present, so extractors never see `ast.Module` instances (theauditor/ast_parser.py:208).
- Observed the same precedence in `ASTParser.parse_content`, which yields `"type": "tree_sitter"` for Python whenever parsers are registered (theauditor/ast_parser.py:352).
- Python import and symbol extractors require CPython nodes and exit early when the payload is not an `ast.Module` (theauditor/indexer/extractors/python.py:303 and theauditor/ast_extractors/python_impl.py:32).
- Verification artifacts capturing hypotheses, evidence, and discrepancies are recorded in `openspec/changes/update-python-ast-fallback/verification.md`.

## Goals
1. Guarantee every Python parsing entry point returns `"type": "python_ast"` payloads that wrap CPython `ast.AST` nodes, regardless of Tree-sitter availability.
2. Add explicit safeguards so future refactors cannot silently reintroduce Tree-sitter payloads for Python without extractor updates.
3. Extend automated coverage and documentation to prove Python import extraction works with Tree-sitter installed and to codify the CPython requirement.

## Non-Goals
- Implement Tree-sitter parity inside Python extractors.
- Change parsing behaviour for non-Python languages or the semantic TypeScript pipeline.
- Alter verification scope that is already captured in `verification.md`.

## Current Behaviour Summary
- `parse_file` and `parse_content` prioritise Tree-sitter caching, returning `"type": "tree_sitter"` before attempting the CPython fallback when `self.has_tree_sitter` is true (theauditor/ast_parser.py:208 and theauditor/ast_parser.py:352).
- Batch parsing defers to `parse_file` for Python files, so the regression propagates to indexer runs and caches (theauditor/ast_parser.py:453).
- Downstream extractors demand CPython nodes (`ast.walk`, `ast.Module`) and silently produce empty datasets when provided Tree-sitter payloads (theauditor/indexer/extractors/python.py:303 and theauditor/ast_extractors/python_impl.py:32).

## Proposed Parser Changes
### `ASTParser.parse_file`
- Short-circuit Python handling before the Tree-sitter branch: decode the file, call `_parse_python_cached`, and immediately return the CPython payload.
- Gate Tree-sitter usage with `language != "python"` to make the intent explicit, leaving logging hooks intact for other languages.
- Add an inline assertion or debug log that highlights when Python unexpectedly yields non-CPython payloads to aid future diagnostics.

### `ASTParser.parse_content`
- Re-order the logic so Python bypasses Tree-sitter entirely and relies on `_parse_python_cached` even when `self.parsers` contains `"python"`.
- Retain the existing temporary-file flow for JS/TS, and ensure the Python branch mirrors the `parse_file` contract (same `"type"` and content fields).

### `ASTParser.parse_files_batch`
- Leave JavaScript and TypeScript batching untouched.
- When iterating Python files, call a shared helper (see below) so the same CPython payload construction is used for file, content, and batch entry points.
- Ensure batch results persist decoded content strings for Python as they do today, so downstream consumers remain unchanged.

### Shared Helper & Safeguards
- Introduce a private `_build_python_payload(content_hash, decoded_content)` utility that encapsulates the CPython parse, error handling, and return dictionary. Reuse it from the three entry points to prevent future divergence.
- Store a boolean flag such as `self.forced_python_builtin = True` set during `__init__` so later refactors can quickly detect the intentional override.
- Extend `supports_language("python")` to note that the CPython path is enforced even when Tree-sitter reports support, clarifying the public contract.

## Defensive Instrumentation
- Add a developer-facing warning (behind `THEAUDITOR_DEBUG`) when Tree-sitter produces a Python tree, noting the value will be ignored. This makes future regressions obvious during local experimentation.
- Consider a `TreeSitterPythonUnsupported` custom exception that can be raised if a future coder tries to flip the order; catching it in tests will keep the guarantee explicit.

## Testing Plan
- **Unit test**: add `tests/unit/parser/test_python_ast_fallback.py` that patches an `ASTParser` instance to simulate installed Tree-sitter (`has_tree_sitter = True`, `parsers["python"] = object()`) and asserts all three entry points return `"type": "python_ast"` with `ast.Module` payloads.
- **Integration test**: extend or add a regression case under `tests/test_extractors.py` to run the Python extractor over a sample file while Tree-sitter is enabled, verifying imports are saved to the `refs` fixture.
- **Property test**: ensure the new helper returns cached objects (content hash reuse) by calling it twice with identical content and confirming object identity where caching is intended.
- **Validation**: keep existing parser tests passing, and document required test commands (`pytest tests/unit/parser/test_python_ast_fallback.py` and relevant extractor suites) in `tasks.md` step 2.

## Documentation & Spec Updates
- Update `openspec/changes/update-python-ast-fallback/specs/indexer/spec.md` if additional scenarios emerge (e.g., content parsing). At minimum, reference the design in the proposal rationale.
- Add a short note to `docs/indexer/python.md` (or closest equivalent) describing that Python relies on CPython AST until Tree-sitter parity exists.
- Capture test execution details in `verification.md` after implementation per SOP v4.20.

## Risks & Mitigations
- *Risk*: Future contributors may re-enable Tree-sitter for Python to chase feature parity. *Mitigation*: bake the requirement into tests and explicit flags; documentation now states the constraint.
- *Risk*: Performance regressions for large Python batches. *Mitigation*: CPython parsing is already the historical path; caching remains via `_parse_python_cached`.
- *Risk*: Content encoding mismatches between file and batch paths. *Mitigation*: centralise payload creation in the shared helper and audit return structures post-change.

## Task Alignment
- **1.1–1.2**: Implemented via the reordered logic, shared helper, and explicit `language != "python"` guard.
- **1.3**: Covered by the new unit and integration tests that prove refs population with Tree-sitter installed.
- **1.4**: Addressed through the planned documentation updates.
- **2.1–2.2**: Validated by running the specified pytest suites and recording the audit trail, as captured in `tasks.md`.

## Rollout & Validation
- Execute focused pytest runs plus any impacted integration suites, then record outcomes in `verification.md`.
- Review modified files post-change to satisfy SOP v4.20 post-implementation audit.
- Once tests and audits pass, run `openspec validate update-python-ast-fallback --strict` to ensure the change set stays consistent.
