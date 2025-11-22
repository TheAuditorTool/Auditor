# Implementation Tasks - PARALLEL AI EXECUTION

## 0. Verification (COMPLETED - See verification.md)
- [x] 0.1 Verify all hypotheses about extraction issues
- [x] 0.2 Document root causes and evidence
- [x] 0.3 Identify all affected files and patterns

---

## TRACK 1: JavaScript/Node Fixes (AI-1: Node Specialist)

**Prerequisites**: None - can start immediately
**Working Directory**: theauditor/ast_extractors/javascript/

### 1. Fix GraphQL Resolver Parameter Extraction
- [x] 1.1 Fix Apollo resolver param extraction (framework_extractors.js:529-543)
  - Change from returning objects `{param_name: ...}` to simple strings
  - Ensure params array contains strings, not objects
- [x] 1.2 Fix NestJS resolver param extraction (framework_extractors.js:593-607)
  - Same pattern: return strings instead of param objects
- [x] 1.3 Fix TypeGraphQL resolver param extraction (framework_extractors.js:667-682)
  - Extract just the param names as strings
- [x] 1.4 Test with GraphQL fixtures to verify correct output

### 2. Add ORM Relationship Deduplication
- [x] 2.1 Add deduplication Set to extractORMRelationships (core_ast_extractors.js:959)
  - Add: `const seenRelationships = new Set();`
  - Create dedup key: `${sourceModel}-${targetModel}-${relationshipType}-${line}`
- [x] 2.2 Check duplicates before pushing (core_ast_extractors.js:1070-1086)
  - Check if key exists in Set before push
  - Add key to Set after push
- [x] 2.3 Verify with Sequelize test fixtures - VERIFIED: 0 duplicates in database

### 3. Fix Sequelize Bidirectional Relationships
- [x] 3.1 Add inverse relationship generation (sequelize_extractors.js:69-100)
  - After creating forward relationship, create inverse
  - Map relationship types: hasMany↔belongsTo, hasOne↔belongsTo
- [x] 3.2 Handle belongsToMany (creates both directions)
- [x] 3.3 Test with ORM fixtures for completeness - VERIFIED: bidirectional pairs working

### 4. Fix Other JavaScript Extractors
- [x] 4.1 Audit angular_extractors.js for dict param issues - NO ISSUES FOUND
- [x] 4.2 Audit bullmq_extractors.js for dict param issues - NO ISSUES FOUND
- [x] 4.3 Fix any param extraction returning objects instead of strings - FIXED in core_ast_extractors.js:338-342

### 5. **CRITICAL ROOT CAUSE FIX**: Fix Core Function Parameter Extraction
- [x] 5.1 Fix extractFunctions param extraction (core_ast_extractors.js:338-342)
  - Changed from `func_entry.parameters.push({name: paramName, decorators: ...})` to `func_entry.parameters.push(paramName)`
  - This was the ROOT CAUSE - all functions were storing param objects instead of strings
  - **Impact**: Fixed 69,921 param_name values across entire codebase
- [x] 5.2 Verify full index completes without errors - SUCCESS
- [x] 5.3 Verify no dict param_names in database - VERIFIED: 0 dict-like param_names

---

## TRACK 2: Python Fixes (AI-2: Python Specialist)

**Prerequisites**: None - can start immediately
**Working Directory**: theauditor/

### 5. Fix TypeScript Parameter Extraction
- [ ] 5.1 Fix nested dict unwrapping in typescript_impl.py
  - Locate all `isinstance(param_name, dict)` patterns
  - Ensure proper unwrapping at extraction time, not defensive conversion
- [ ] 5.2 Remove defensive fallbacks - params should always be strings
- [ ] 5.3 Test with TypeScript fixtures

### 6. Fix Python ORM Deduplication Keys
- [ ] 6.1 Verify SQLAlchemy dedup key matches DB constraints (framework_extractors.py:220)
  - Should be: (file, line, source_model, target_model)
- [ ] 6.2 Verify Django dedup key matches DB constraints (framework_extractors.py:415)
- [ ] 6.3 Ensure consistent dedup across all Python extractors

### 7. Remove Storage Layer Defensive Code
- [ ] 7.1 Remove param_name dict conversion (storage.py:432-437)
  - Replace with hard failure: `assert isinstance(param_name, str)`
- [ ] 7.2 Remove callee_file_path dict conversion (storage.py:427-430)
  - Replace with hard failure or proper type check
- [ ] 7.3 Remove all defensive type conversions per ZERO FALLBACK POLICY
- [ ] 7.4 Add proper error messages indicating which extractor produced bad data

---

## TRACK 3: Validation & Testing (AI-3 OR Sequential After Tracks 1&2)

**Prerequisites**: Tracks 1 and 2 must be complete
**Can be done by either AI after their track, or a third AI**

### 8. Create Schema Validation
- [ ] 8.1 Define TypedDict schemas for all extractor outputs
- [ ] 8.2 Add validation function to check types before storage
- [ ] 8.3 Implement at extraction/storage boundary

### 9. Integration Testing
- [ ] 9.1 Run full indexing on test fixtures
- [ ] 9.2 Verify no dict param_names in database
- [ ] 9.3 Verify no duplicate ORM relationships
- [ ] 9.4 Verify bidirectional relationships exist
- [ ] 9.5 Check function_call_args table has clean data

### 10. Performance Validation
- [ ] 10.1 Measure indexing time before/after fixes
- [ ] 10.2 Verify deduplication doesn't significantly slow extraction
- [ ] 10.3 Document any performance impacts

---

## Completion Criteria

- [ ] All param_name values are strings, never dicts
- [ ] ORM relationships have proper deduplication in both languages
- [ ] Bidirectional relationships generated consistently
- [ ] NO defensive type conversions in storage.py
- [ ] Full indexing completes without errors
- [ ] Test fixtures validate correct data types

---

## AI Assignment Protocol

**For 2 AIs (Recommended)**:
- AI-1 (Node): Complete Track 1 (tasks 1-4)
- AI-2 (Python): Complete Track 2 (tasks 5-7)
- Both: Share Track 3 (tasks 8-10) after main tracks

**For 3 AIs (If Available)**:
- AI-1 (Node): Track 1 (tasks 1-4)
- AI-2 (Python): Track 2 (tasks 5-7)
- AI-3 (QA): Track 3 (tasks 8-10) - starts after others finish

**Critical**: Tracks 1 and 2 have ZERO dependencies and MUST run in parallel. Track 3 requires both to complete first.