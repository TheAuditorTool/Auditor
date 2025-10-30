# Design Document: TypeScript CDK Extraction

**Change ID**: `add-typescript-cdk-extraction`
**Document Version**: 1.0
**Last Updated**: 2025-10-30

## Context

AWS Cloud Development Kit (CDK) supports multiple languages (Python, TypeScript, Java, Go, C#). TheAuditor currently extracts CDK constructs from **Python only**, creating a critical blind spot for TypeScript CDK infrastructure (the AWS-recommended and most common language for CDK).

**Current Coverage**:
- Python CDK: ✅ COMPLETE (extraction, rules, analysis)
- TypeScript CDK: ❌ MISSING (no extraction)

**Stakeholders**:
- **Security Engineers**: Need to analyze TypeScript CDK infrastructure
- **DevOps Teams**: Most production CDK code is TypeScript
- **Developers**: Want language parity (Python and TypeScript both supported)

## Goals / Non-Goals

### Goals

1. **Add TypeScript CDK extraction** matching Python CDK extraction feature parity
2. **Reuse existing infrastructure** (database schema, rules, analyzer unchanged)
3. **Maintain zero fallbacks** (teamsop.md ZERO FALLBACK POLICY)
4. **Enable end-to-end testing** with TypeScript CDK test fixtures
5. **Document 5-layer architecture** for future maintainers

### Non-Goals

1. ❌ Modify Python CDK extraction (already complete)
2. ❌ Add new CDK rules (existing 4 rules sufficient)
3. ❌ Support CDK v1 (deprecated, EOL June 2023)
4. ❌ Add Terraform/Pulumi support (separate extractors)
5. ❌ Refactor JavaScript extraction pipeline (works, don't touch)

## Architectural Decisions

### Decision 1: Add to `security_extractors.js` vs New File

**Options Considered**:
1. **Add to security_extractors.js** (CHOSEN)
   - Pros: Security-focused (IaC vulnerabilities), under 1200-line limit, simpler
   - Cons: Security file gets larger (433 + 200 = 633 lines)

2. **Create new cdk_extractors.js**
   - Pros: Dedicated file, clear separation
   - Cons: New file in assembly pipeline, orchestrator changes, overkill for 200 lines

3. **Add to framework_extractors.js**
   - Pros: Infrastructure = framework?
   - Cons: Wrong domain (React/Vue ≠ CDK), confusing organization

**Rationale**: security_extractors.js chosen because:
- CDK extraction detects **security vulnerabilities** (public S3, unencrypted RDS)
- Still under 1200-line growth limit (633 < 1200)
- No orchestrator changes needed (already concatenated)
- Follows existing pattern (ORM, API, SQL in security file)

### Decision 2: Detection Strategy

**Question**: How to detect CDK constructs in TypeScript?

**Approach**: **Import-driven + AST-based** (NO REGEX)

```javascript
// Step 1: Detect CDK imports
const cdkImports = imports.filter(i =>
    i.module && i.module.includes('aws-cdk-lib')
);

if (cdkImports.length === 0) {
    return [];  // No CDK imports = no CDK constructs (deterministic)
}

// Step 2: Detect 'new' expressions from functionCallArgs
// Core extractors mark these with callee_function like 'new s3.Bucket'
for (const call of functionCallArgs) {
    if (call.callee_function && call.callee_function.startsWith('new ')) {
        // This is a constructor call, check if it's a CDK construct
    }
}
```

**Why This Works**:
- Core extractors (`core_ast_extractors.js:1012, 1364`) already parse NewExpression AST nodes
- Marked in `functionCallArgs` with `callee_function: 'new ClassName'`
- No regex needed - use existing AST data
- Import filtering ensures deterministic behavior

**Alternatives Rejected**:
- ❌ Regex on source code (`/new\s+\w+\./g`) - violates ZERO FALLBACK POLICY
- ❌ Heuristics (uppercase class names) - too many false positives
- ❌ Direct AST traversal in JavaScript - reinvents core extractors

### Decision 3: Import Pattern Matching

**Question**: How to match imports to CDK constructs?

**Patterns to Support**:

```typescript
// Pattern 1: Named import (most common)
import * as s3 from 'aws-cdk-lib/aws-s3';
new s3.Bucket(...)  // ← Match: 's3' module → 's3.Bucket' class

// Pattern 2: Destructured import
import { Bucket } from 'aws-cdk-lib/aws-s3';
new Bucket(...)  // ← Match: 'Bucket' name → 's3.Bucket' class (inferred)

// Pattern 3: Direct CDK import
import { aws_s3 as s3 } from 'aws-cdk-lib';
new s3.Bucket(...)  // ← Match: 's3' alias → 's3.Bucket' class
```

**Implementation Strategy**:
1. Build import map: `{alias: module_path}`
2. When detecting `new X(...)`, check if `X` or its prefix matches import map
3. Normalize class name to CDK format (`s3.Bucket`, not `Bucket`)

**Edge Cases**:
- Multiple aliases for same module → Use first match (deterministic)
- Non-CDK imports → Filtered out by `aws-cdk-lib` check
- Dynamic imports → Skip (can't analyze statically)

### Decision 4: Property Extraction

**Question**: How to extract construct properties (configuration)?

**Approach**: **Object literal parsing** (same as React props)

```typescript
new s3.Bucket(this, 'MyBucket', {
  publicReadAccess: true,  // ← Extract this
  encryption: s3.BucketEncryption.UNENCRYPTED  // ← And this
});
```

**Detection**:
- 3rd argument to constructor is properties object
- Use existing object literal parser (React props use this)
- Extract `{key: value}` pairs
- Serialize values as strings (for database storage)

**Challenges**:
- Enum values (`s3.BucketEncryption.UNENCRYPTED`) → Store full expression
- Nested objects (`vpc: { ... }`) → Flatten or store as JSON
- Template strings with interpolation → Skip (dynamic)

**Decision**: Store property values as unparsed expressions (Python extractor does this).

### Decision 5: Database Schema

**Question**: Do we need new tables for TypeScript CDK?

**Decision**: **NO** - Reuse existing Python CDK tables.

**Existing Tables** (schema.py:1365-1402):
```sql
CREATE TABLE cdk_constructs (
    file TEXT NOT NULL,          -- ← Works for .py and .ts
    line INTEGER NOT NULL,
    cdk_class TEXT NOT NULL,     -- ← 's3.Bucket' (language-agnostic)
    construct_name TEXT          -- ← Logical ID (language-agnostic)
);

CREATE TABLE cdk_construct_properties (
    file TEXT NOT NULL,          -- ← Works for .py and .ts
    line INTEGER NOT NULL,
    cdk_class TEXT NOT NULL,
    property_name TEXT NOT NULL, -- ← 'publicReadAccess' (language-agnostic)
    property_value TEXT          -- ← 'true' (serialized)
);
```

**Rationale**:
- Tables are language-agnostic (no Python-specific columns)
- Rules query these tables (don't care about source language)
- Analyzer reads these tables (works for both languages)
- Findings table already supports both (tool='cdk', file='*.ts')

**No Schema Changes Needed** ✅

### Decision 6: Test Fixtures

**Question**: How to create TypeScript CDK test fixtures?

**Decision**: **Mirror Python vulnerable_stack.py with TypeScript equivalent**.

**Requirements**:
1. Same vulnerabilities as Python stack:
   - Public S3 bucket
   - Unencrypted RDS instance
   - Open security group

2. Runnable with `aud full --offline`:
   - npm dependencies defined in package.json
   - TypeScript config in tsconfig.json
   - CDK app config in cdk.json

3. Verifiable extraction:
   - `aud index` populates cdk_constructs table
   - `aud cdk analyze` detects 3 critical findings
   - Same findings as Python stack (parity test)

**Files to Create**:
- `vulnerable_stack.ts` - TypeScript CDK stack
- `package.json` - npm dependencies (aws-cdk-lib, constructs)
- `tsconfig.json` - TypeScript config
- `cdk.json` - CDK app entry point

### Decision 7: Error Handling

**Question**: How to handle extraction failures?

**Approach**: **Log and continue** (NO FALLBACKS)

```javascript
function extractCDKConstructs(functionCallArgs, imports) {
    const constructs = [];

    for (const call of functionCallArgs) {
        try {
            const construct = parseConstruct(call);
            if (construct) {
                constructs.push(construct);
            }
        } catch (error) {
            // Log error (for debugging) but don't crash
            if (process.env.THEAUDITOR_DEBUG) {
                console.error(`[CDK] Failed to parse construct at line ${call.line}: ${error}`);
            }
            // Skip this construct, continue to next
            continue;
        }
    }

    return constructs;
}
```

**Principles**:
- Try-catch prevents crashes (JavaScript runs in Node subprocess)
- Errors logged to stderr (visible with debug flag)
- Incomplete extraction is acceptable (better than crash)
- NO fallback logic (no alternative parsing methods)

**What Causes Failures**:
- Malformed AST data (rare, indicates core extractor bug)
- Unsupported import patterns (e.g., dynamic imports)
- Complex property expressions (e.g., computed keys)

**Resolution**:
- Log failure with line number for debugging
- Fix core issue (update detection logic or core extractors)
- Do NOT add fallback parsing

## Risks / Trade-offs

### Risk 1: NewExpression Detection

**Risk**: Core extractors may not mark `new` expressions consistently.

**Mitigation**:
- Verified: core_ast_extractors.js:1012, 1364 handle NewExpression
- Test with real-world TypeScript CDK projects
- Add debug logging to track detection rate

### Risk 2: Import Pattern Variations

**Risk**: Real-world projects may use import patterns we don't detect.

**Mitigation**:
- Start with 3 common patterns (named, destructured, direct)
- Add debug logging for unmatched imports
- Iterate based on test failures (add new patterns as needed)

### Risk 3: Property Serialization

**Risk**: Complex property values (enums, nested objects) may not serialize correctly.

**Mitigation**:
- Store as unparsed expressions (same as Python extractor)
- Rules check for specific values (e.g., `publicReadAccess = 'true'`)
- If serialization fails, log and skip property (don't crash)

### Trade-off 1: security_extractors.js File Size

**Before**: 433 lines
**After**: 633 lines (+200 lines)

**Analysis**:
- Pro: Single file, simpler organization
- Con: File growing larger (but still under 1200-line limit)
- Verdict: Acceptable - still maintainable

### Trade-off 2: Import-Driven Detection

**Approach**: Only extract constructs if CDK imports detected.

**Pros**:
- Deterministic (no guessing)
- Fast (skip files without CDK imports)
- No false positives

**Cons**:
- Misses constructs if import detection fails
- Requires accurate import parsing (core extractors must work)

**Verdict**: Worth it - determinism > coverage

## Migration Plan

### Phase 1: JavaScript Extraction Layer

**File**: `theauditor/ast_extractors/javascript/security_extractors.js`

**Add** (end of file, ~200 lines):
1. `extractCDKConstructs()` main function
2. `detectCDKImports()` helper
3. `isCDKConstruct()` helper
4. `parseConstructProperties()` helper

**Testing**: Unit test with sample AST data.

### Phase 2: Batch Template Integration

**File**: `theauditor/ast_extractors/javascript/batch_templates.js`

**Modify** (2 lines):
1. Add extraction call: `const cdkConstructs = extractCDKConstructs(...)`
2. Add to output: `cdkConstructs: cdkConstructs`

**Testing**: Verify output JSON includes `cdkConstructs` field.

### Phase 3: Indexer Integration

**File**: `theauditor/indexer/extractors/javascript.py`

**Add** (after line ~1200, ~50 lines):
```python
# Extract CDK constructs (TypeScript/JavaScript)
cdk_constructs = file_data.get('cdkConstructs', [])
for construct in cdk_constructs:
    # Write to database
```

**Testing**: Verify database writes with test fixture.

### Phase 4: Test Fixtures

**Create** (4 files):
1. `vulnerable_stack.ts` - TypeScript CDK stack with vulnerabilities
2. `package.json` - npm dependencies
3. `tsconfig.json` - TypeScript config
4. `cdk.json` - CDK app config

**Testing**: Run `aud index` and verify extraction.

### Phase 5: End-to-End Validation

**Tests** (5 validation tests from verification.md):
1. Extraction verification (database query)
2. Property extraction (database query)
3. Rule detection (`aud cdk analyze`)
4. Offline mode (`aud full --offline`)
5. Python parity (compare Python vs TypeScript findings)

**Pass Criteria**: All 5 tests pass with identical results to Python stack.

## Open Questions

### Resolved

✅ **Q1**: Can we reuse Python CDK tables?
**A1**: YES - Tables are language-agnostic.

✅ **Q2**: Do rules need changes?
**A2**: NO - Rules query database, don't care about language.

✅ **Q3**: How to detect `new` expressions?
**A3**: Core extractors already handle NewExpression AST nodes.

✅ **Q4**: Should we support CDK v1?
**A4**: NO - Deprecated, EOL June 2023.

### Unresolved

❓ **Q5**: Should we extract CDK context variables?
💬 **Recommendation**: DEFERRED - Focus on construct extraction first.

❓ **Q6**: Should we support CDK aspects/modifiers?
💬 **Recommendation**: DEFERRED - Core construct extraction first.

## Performance Considerations

**Impact**: Negligible

**Analysis**:
- JavaScript extraction already runs for all .ts/.js files
- Adding one more extraction function (extractCDKConstructs) is marginal
- No CDK imports → Early return (fast path)
- Construct count typically <100 per file (fast iteration)

**Benchmarks** (estimated):
- Empty file (no CDK): +0.1ms (import check only)
- CDK file with 10 constructs: +5ms (extraction + serialization)

## Testing Strategy

### Unit Tests

**JavaScript Tests** (security_extractors.js):
```javascript
// Test 1: Detect CDK imports
assert(detectCDKImports([
    {module: 'aws-cdk-lib/aws-s3'}
]).length === 1);

// Test 2: Extract construct
const constructs = extractCDKConstructs([
    {callee_function: 'new s3.Bucket', line: 10}
], [{module: 'aws-cdk-lib/aws-s3'}]);
assert(constructs.length === 1);
assert(constructs[0].cdk_class === 's3.Bucket');
```

**Python Tests** (indexer integration):
```python
def test_typescript_cdk_extraction():
    file_data = {'cdkConstructs': [
        {'line': 10, 'cdk_class': 's3.Bucket', 'construct_name': 'MyBucket'}
    ]}
    extractor.process_file_data('test.ts', file_data)
    # Verify database writes
```

### Integration Tests

**Test Fixture** (vulnerable_stack.ts):
```bash
cd tests/fixtures/cdk_test_project
aud index
aud cdk analyze
# Verify 3 critical findings
```

### End-to-End Tests

**Full Pipeline** (aud full --offline):
```bash
aud full --offline tests/fixtures/cdk_test_project
# Verify extraction + analysis + findings
```

## Documentation Updates

**Files to Update**:
1. ✅ verification.md (this proposal) - Comprehensive architecture documentation
2. ✅ proposal.md - High-level overview
3. ✅ design.md (this file) - Technical decisions
4. ✅ tasks.md - Implementation checklist

**No Updates Required**:
- README.md - User documentation (no API changes)
- theauditor/aws_cdk/README.md - Already covers both languages conceptually

## Success Criteria

**Functional**:
1. ✅ TypeScript CDK constructs extracted to database
2. ✅ Same 3 vulnerabilities detected as Python stack
3. ✅ Rules work identically for Python and TypeScript
4. ✅ `aud cdk analyze` reports findings from both languages

**Non-Functional**:
1. ✅ Zero breaking changes to Python CDK extraction
2. ✅ No new dependencies (Node.js already required)
3. ✅ Performance impact negligible (<5ms per file)
4. ✅ teamsop.md compliance (NO FALLBACKS, database-first)

## Alternatives Considered

### Alternative 1: Separate TypeScript Analyzer

**Idea**: Create separate analyzer for TypeScript CDK (parallel to Python analyzer).

**Pros**:
- Complete language separation
- Independent evolution

**Cons**:
- Duplicate rules (4 rules × 2 languages = 8 rules)
- Duplicate analyzer logic
- Separate findings tables (fragmentation)
- More maintenance burden

**Verdict**: Rejected - sharing database/rules/analyzer is cleaner.

### Alternative 2: Regex-Based Extraction

**Idea**: Use regex to find `new s3.Bucket(...)` patterns in source code.

**Pros**:
- Simpler implementation (no AST parsing)
- Faster (string matching vs AST traversal)

**Cons**:
- Violates ZERO FALLBACK POLICY
- False positives (matches in comments, strings)
- False negatives (multi-line constructs, complex syntax)
- No property extraction (regex can't parse object literals)

**Verdict**: Rejected - violates teamsop.md prime directive.

### Alternative 3: CDK Metadata Extraction

**Idea**: Parse CDK cdk.out/ directory (synthesized CloudFormation).

**Pros**:
- Complete infrastructure view
- No AST parsing needed

**Cons**:
- Requires CDK synthesis (dependencies, AWS account)
- Loses source code context (line numbers)
- Can't run offline (needs AWS SDK)
- Doesn't match Python approach (AST-based)

**Verdict**: Rejected - violates offline-first principle.

## Conclusion

This design document outlines a comprehensive, low-risk approach to adding TypeScript CDK extraction:

✅ **Reuses existing infrastructure** (schema, rules, analyzer)
✅ **Follows ZERO FALLBACK POLICY** (import-driven, deterministic)
✅ **Maintains database-first architecture** (extraction → database → rules)
✅ **Enables end-to-end testing** (TypeScript test fixtures)
✅ **Documents 5-layer pipeline** (JavaScript → Orchestrator → Parser → Indexer → Analyzer)

**Confidence Level**: HIGH (85%)

**Ready for Implementation**: YES (pending Architect/Auditor approval)

---

**Designed By**: Claude Opus (Lead Coder)
**Date**: 2025-10-30
**Status**: AWAITING APPROVAL
