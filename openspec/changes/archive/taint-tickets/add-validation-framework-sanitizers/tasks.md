# Implementation Tasks: Validation Framework Sanitizers

## 0. Verification
- [x] Document baseline behaviour for sanitizer detection (verification.md complete)
- [x] Verify SANITIZERS dictionary location and structure (sources.py:171-244)
- [x] Verify is_sanitizer() implementation (propagation.py:29-43)
- [x] Verify has_sanitizer_between() usage locations (lines 186, 435, 545)
- [x] Research validation framework patterns (6 frameworks documented)
- [x] Identify edge cases and mitigation strategies (10 edge cases documented)

## 1. Pattern Addition
- [ ] 1.1 Add `validation_frameworks` category to SANITIZERS dictionary in `theauditor/taint/sources.py:244`
- [ ] 1.2 Add Zod patterns: `.parse`, `.parseAsync`, `.safeParse`, `z.parse`, `schema.parse`, `schema.parseAsync`, `schema.safeParse`
- [ ] 1.3 Add Joi patterns: `.validate`, `.validateAsync`, `Joi.validate`, `schema.validate`, `schema.validateAsync`
- [ ] 1.4 Add Yup patterns: `yup.validate`, `yup.validateSync`, `schema.validateSync`, `.isValid`, `schema.isValid`
- [ ] 1.5 Add express-validator patterns: `validationResult`, `matchedData`, `checkSchema`
- [ ] 1.6 Add class-validator patterns: `validate`, `validateSync`, `validateOrReject`
- [ ] 1.7 Add AJV patterns: `ajv.validate`, `ajv.compile`, `validator.validate`
- [ ] 1.8 Verify all patterns are in frozenset format for O(1) lookup
- [ ] 1.9 Add inline documentation explaining each framework's purpose and common usage

## 2. Matching Logic Enhancement (OPTIONAL - Evaluate During Testing)
- [ ] 2.1 Test current substring matching with new patterns (`"schema.parse" in function_name`)
- [ ] 2.2 If current matching sufficient, skip enhancement
- [ ] 2.3 If needed, enhance `is_sanitizer()` in `theauditor/taint/propagation.py:29-43` with suffix-based matching
- [ ] 2.4 Add logic to check dotted method patterns (`.parse`, `.validateAsync`)
- [ ] 2.5 Maintain backward compatibility with existing substring matching
- [ ] 2.6 Add inline documentation explaining matching strategy

## 3. Testing - Validation Framework Recognition
- [ ] 3.1 Create test fixture directory: `tests/fixtures/validation/`
- [ ] 3.2 Create `zod_validation.ts` fixture with Zod patterns (parseAsync, safeParse)
- [ ] 3.3 Create `joi_validation.js` fixture with Joi patterns (validateAsync)
- [ ] 3.4 Create `yup_validation.js` fixture with Yup patterns (validate, validateSync)
- [ ] 3.5 Create `express_validator.js` fixture with express-validator patterns (validationResult, matchedData)
- [ ] 3.6 Add test cases to `tests/test_taint_e2e.py` for each framework
- [ ] 3.7 Verify Zod validation stops taint propagation
- [ ] 3.8 Verify Joi validation stops taint propagation
- [ ] 3.9 Verify Yup validation stops taint propagation
- [ ] 3.10 Verify express-validator stops taint propagation

## 4. Testing - Edge Cases
- [ ] 4.1 Create test case: Schema builders NOT recognized as sanitizers (`z.string()`, `Joi.number()`)
- [ ] 4.2 Create test case: JSON.parse NOT recognized as sanitizer (deserializer, not validator)
- [ ] 4.3 Create test case: url.parse NOT recognized as sanitizer (parser, not validator)
- [ ] 4.4 Create test case: Failed validation with error handler (taint persists in catch block)
- [ ] 4.5 Create test case: Partial validation (one field validated, another unvalidated)
- [ ] 4.6 Create test case: Multiple frameworks in same project (no conflicts)
- [ ] 4.7 Verify all edge case tests pass

## 5. Testing - Regression Prevention
- [ ] 5.1 Run full existing test suite: `pytest tests/ -v`
- [ ] 5.2 Verify no existing tests broken by pattern addition
- [ ] 5.3 Run taint analysis on existing test projects
- [ ] 5.4 Verify vulnerable code still detected (no new false negatives)
- [ ] 5.5 Verify traditional sanitizers still recognized (escape_html, sanitize, etc.)
- [ ] 5.6 Check performance regression: taint analysis time increase <5%

## 6. Documentation
- [ ] 6.1 Update `CLAUDE.md` section on taint analysis with validation framework coverage
- [ ] 6.2 Document supported frameworks: Zod, Joi, Yup, express-validator, class-validator, AJV
- [ ] 6.3 Document patterns recognized vs patterns NOT recognized (schema builders, JSON.parse)
- [ ] 6.4 Add troubleshooting section for false positives/negatives
- [ ] 6.5 Update taint analysis false positive rate expectation (38% → 12%)
- [ ] 6.6 Document known limitations (control flow constraints still out of scope)
- [ ] 6.7 Update inline code comments in `sources.py` explaining validation_frameworks category
- [ ] 6.8 Add docstring examples showing framework validation patterns

## 7. Performance Validation
- [ ] 7.1 Benchmark taint analysis on small project (<5K LOC) before and after
- [ ] 7.2 Benchmark taint analysis on medium project (20K LOC) before and after
- [ ] 7.3 Benchmark taint analysis on large project (100K+ LOC) before and after
- [ ] 7.4 Verify performance increase <5% (acceptable)
- [ ] 7.5 Verify memory usage increase <1MB (negligible)
- [ ] 7.6 Document performance impact in CLAUDE.md if measurable

## 8. Code Quality
- [ ] 8.1 Run `ruff check theauditor/taint --fix` (linting)
- [ ] 8.2 Run `ruff format theauditor/taint` (formatting)
- [ ] 8.3 Run `mypy theauditor/taint --strict` (type checking)
- [ ] 8.4 Ensure all inline comments are clear and accurate
- [ ] 8.5 Verify frozenset syntax correct (immutable, O(1) lookup)
- [ ] 8.6 Verify alphabetical ordering within pattern categories (readability)

## 9. OpenSpec Validation
- [ ] 9.1 Run `openspec validate add-validation-framework-sanitizers --strict`
- [ ] 9.2 Resolve any validation errors or warnings
- [ ] 9.3 Verify all scenarios have proper `#### Scenario:` headers (4 hashtags)
- [ ] 9.4 Verify all requirements have at least one scenario
- [ ] 9.5 Verify proposal.md, design.md, tasks.md, verification.md all present
- [ ] 9.6 Verify spec deltas in `specs/taint/spec.md` properly formatted

## 10. Final Review & Approval
- [ ] 10.1 Post-implementation audit: Re-read all modified files
- [ ] 10.2 Verify no syntax errors introduced
- [ ] 10.3 Verify no logical flaws in pattern matching
- [ ] 10.4 Verify no unintended side effects (existing patterns still work)
- [ ] 10.5 Run full test suite one final time
- [ ] 10.6 Update OpenSpec change status to complete (after Architect approval)
- [ ] 10.7 Request Architect sign-off for deployment

---

**Total Estimated Effort:** 6-8 hours
**Risk Level:** Low (pure addition, no breaking changes)
**Dependencies:** None (no new libraries, no schema changes)
**Deployment:** Single PR, fully reversible via git revert
