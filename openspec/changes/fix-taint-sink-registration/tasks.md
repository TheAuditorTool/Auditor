# Implementation Tasks

## 1. Fix api_auth_analyze.py (30 minutes)
- [ ] 1.1 Read current `register_taint_patterns()` implementation (lines 533-543)
- [ ] 1.2 Create separate pattern sets: `SENSITIVE_URL_PATTERNS` (for URL matching) and `SENSITIVE_FUNCTIONS` (for taint analysis)
- [ ] 1.3 Update `register_taint_patterns()` to only register function-level patterns
- [ ] 1.4 Add docstring explaining why URL patterns are NOT registered as taint sinks
- [ ] 1.5 Verify rule still detects missing auth on sensitive endpoints using database-first pattern matching

## 2. Add Registry Validation (45 minutes)
- [ ] 2.1 Read `theauditor/taint/registry.py` register_sink method (lines 102-122)
- [ ] 2.2 Add COMMON_VARIABLE_NAMES frozenset: `{'user', 'token', 'password', 'admin', 'config', 'key', 'secret', 'data', 'result', 'value'}`
- [ ] 2.3 Add validation in `register_sink()`: warn if pattern is too generic (in common names, <4 chars, no camelCase/snake_case)
- [ ] 2.4 Add `--strict-registry` flag to fail on invalid patterns
- [ ] 2.5 Log warnings for rejected patterns with file/line context

## 3. Audit Other Rules (2-3 hours)
- [ ] 3.1 Query all files with `register_taint_patterns` method: `Grep "register_taint_patterns" theauditor/rules`
- [ ] 3.2 For each of 22 rules, verify patterns are code-level (functions/methods), not domain-level (URLs/keywords)
- [ ] 3.3 Document findings in `audit_taint_patterns.md`
- [ ] 3.4 Fix any similar pattern mismatches found
- [ ] 3.5 Add unit tests for registry validation with good/bad pattern examples

## 4. Testing & Verification (1 hour)
- [ ] 4.1 Run `aud full` and verify sink count: expect 95-150 (vs 353 broken)
- [ ] 4.2 Query taint_analysis.json: verify 0 paths with "user"/"token"/"password" as sink patterns
- [ ] 4.3 Verify runtime: expect <5 minutes (vs 23.7min broken)
- [ ] 4.4 Check taint_paths table: verify legitimate sinks only (sql, xss, command, path, dynamic_dispatch)
- [ ] 4.5 Run `pytest tests/test_registry.py -v` (create if needed)

## 5. Documentation (30 minutes)
- [ ] 5.1 Update CLAUDE.md section on rule pattern registration best practices
- [ ] 5.2 Add "Common Pitfalls" section: URL patterns vs code patterns
- [ ] 5.3 Update api_auth_analyze.py docstring with corrected pattern usage
- [ ] 5.4 Add example to rules/TEMPLATE_STANDARD_RULE.py showing correct pattern registration
