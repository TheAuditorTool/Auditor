## 0. Verification
- [x] 0.1 Capture hypotheses, evidence, and discrepancies for the Python import regression in erification.md (completed 2025-10-15 with architect review).

## 1. Implementation
- [ ] 1.1 Update ASTParser.parse_file to bypass Tree-sitter for Python and return CPython st.Module payloads.
- [ ] 1.2 Mirror the Python safeguard in parse_content and parse_files_batch so all parser entry points stay consistent.
- [ ] 1.3 Add regression tests exercising the parser/extractor combination with Tree-sitter installed, confirming Python imports populate efs.
- [ ] 1.4 Refresh any relevant docs or changelog entries referencing Python AST behaviour.

## 2. Validation
- [ ] 2.1 Run targeted extractor/indexer test suites (e.g., pytest tests/test_extractors.py) and document results.
- [ ] 2.2 Perform post-change audit per teamsop.md: re-read modified files, confirm importer counts, and update report.
