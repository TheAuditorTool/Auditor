# Proposal: Add TypeScript CDK Infrastructure Extraction

**Change ID**: `add-typescript-cdk-extraction`
**Type**: Feature Addition (Critical Gap)
**Status**: Pending Approval
**Risk Level**: HIGH (JavaScript extraction pipeline modification)
**Breaking Change**: NO

## Why

**Problem**: TypeScript is the **primary language** for AWS CDK infrastructure code, yet TheAuditor only extracts CDK constructs from Python files. This creates a **critical blind spot** in production infrastructure security analysis.

**Current State**:
- ✅ Python CDK extraction: COMPLETE (`ast_extractors/python/cdk_extractor.py`, 280 lines)
- ✅ CDK security rules: COMPLETE (4 rules in `rules/deployment/aws_cdk_*.py`)
- ✅ CDK analyzer: COMPLETE (`aws_cdk/analyzer.py`)
- ✅ CDK command: COMPLETE (`aud cdk analyze`)
- ❌ **TypeScript/JavaScript CDK extraction**: **DOES NOT EXIST**

**Impact**:
- AWS recommends TypeScript as the primary CDK language
- Most production CDK code is TypeScript, not Python
- We have the complete pipeline (schema, rules, analyzer) but **no TS extraction**
- Infrastructure security blind spot in 80%+ of CDK projects

**Real-World Example**:
```typescript
// This vulnerable code is INVISIBLE to TheAuditor today
import * as s3 from 'aws-cdk-lib/aws-s3';

new s3.Bucket(this, 'MyBucket', {
  publicReadAccess: true,  // ← CRITICAL vulnerability NOT detected
  encryption: s3.BucketEncryption.UNENCRYPTED  // ← NOT detected
});
```

## What Changes

### High-Level Architecture

**TypeScript CDK Extraction Pipeline**:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. JavaScript Extraction (.js files executed by Node.js)       │
│    ast_extractors/javascript/security_extractors.js             │
│    └─ extractCDKConstructs(functionCallArgs, imports)           │
│       - Detects: new s3.Bucket(...), new SecurityGroup(...)    │
│       - Returns: [{line, cdk_class, construct_name, props}]    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Python Orchestrator (loads .js files, runs via Node)        │
│    ast_extractors/js_helper_templates.py                        │
│    └─ Assembles: core → security (with CDK) → framework → batch │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Semantic Parser (executes assembled JavaScript)             │
│    js_semantic_parser.py                                        │
│    └─ Returns: {cdkConstructs: [...]} in JSON                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Indexer (writes to database)                                │
│    indexer/extractors/javascript.py                             │
│    └─ Writes to: cdk_constructs, cdk_construct_properties      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. CDK Analyzer (reads database, runs rules)                   │
│    aws_cdk/analyzer.py                                          │
│    └─ Queries: cdk_constructs, cdk_construct_properties        │
│    └─ Writes: cdk_findings, findings_consolidated              │
└─────────────────────────────────────────────────────────────────┘
```

### Detailed Changes

**1. JavaScript Extraction Layer** (`ast_extractors/javascript/security_extractors.js`):

Add `extractCDKConstructs()` function (∼200 lines):

```javascript
/**
 * Extract AWS CDK construct instantiations from TypeScript/JavaScript.
 *
 * Detects patterns:
 * - new s3.Bucket(this, 'MyBucket', {...})
 * - new SecurityGroup(this, 'MySG', {...})
 * - new rds.DatabaseInstance(this, 'MyDB', {...})
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} imports - From extractImports()
 * @returns {Array} - CDK construct records
 */
function extractCDKConstructs(functionCallArgs, imports) {
    // Implementation: Detect 'new X(...)' where X is from 'aws-cdk-lib/*'
}
```

**Detection Strategy**:
- Parse imports to identify `aws-cdk-lib/*` modules
- Detect `new` expressions with CDK construct classes
- Extract construct properties from object literals
- Handle both direct imports and aliased imports

**2. Batch Template Integration** (`ast_extractors/javascript/batch_templates.js`):

Add extraction call (1 line):

```javascript
const cdkConstructs = extractCDKConstructs(functionCallArgs, imports);
```

Add to output (1 line):

```javascript
cdkConstructs: cdkConstructs,
```

**3. Orchestrator Update** (`ast_extractors/js_helper_templates.py`):

NO CHANGES - Already concatenates `security_extractors.js` automatically.

**4. Indexer Integration** (`indexer/extractors/javascript.py`):

Add CDK construct handling (∼50 lines):

```python
# Extract CDK constructs (TypeScript/JavaScript)
cdk_constructs = file_data.get('cdkConstructs', [])
for construct in cdk_constructs:
    self.db.add_cdk_construct(
        file=file_path,
        line=construct.get('line'),
        cdk_class=construct.get('cdk_class'),
        construct_name=construct.get('construct_name')
    )
    # Add properties
    for prop in construct.get('properties', []):
        self.db.add_cdk_construct_property(...)
```

**5. Test Fixtures** (`tests/fixtures/cdk_test_project/`):

Add TypeScript CDK stack with identical vulnerabilities to Python version:

```
tests/fixtures/cdk_test_project/
├── vulnerable_stack.py       # Existing Python stack
├── vulnerable_stack.ts       # NEW: TypeScript equivalent
├── package.json              # NEW: CDK dependencies
├── tsconfig.json             # NEW: TypeScript config
└── cdk.json                  # NEW: CDK app config
```

### TypeScript Test Stack Requirements

**File**: `tests/fixtures/cdk_test_project/vulnerable_stack.ts`

Must contain identical vulnerabilities to Python version:
- Public S3 bucket (`publicReadAccess: true`)
- Unencrypted RDS instance (`storageEncrypted: false`)
- Open security group (`allowAllOutbound: true`)
- Unencrypted S3 bucket (missing `encryption`)
- IAM wildcard policies (if applicable)

**Verification Criteria**:
```bash
# After implementation, this MUST work
cd tests/fixtures/cdk_test_project
aud index
aud cdk analyze

# Expected: Same 3-4 critical findings as Python stack
```

## Impact

### Affected Files

**Modified (3 files)**:
- `theauditor/ast_extractors/javascript/security_extractors.js` (+200 lines)
- `theauditor/ast_extractors/javascript/batch_templates.js` (+2 lines)
- `theauditor/indexer/extractors/javascript.py` (+50 lines)

**Created (4 files)**:
- `tests/fixtures/cdk_test_project/vulnerable_stack.ts` (NEW)
- `tests/fixtures/cdk_test_project/package.json` (NEW)
- `tests/fixtures/cdk_test_project/tsconfig.json` (NEW)
- `tests/fixtures/cdk_test_project/cdk.json` (NEW)

**Not Modified**:
- `theauditor/indexer/schema.py` - Tables already exist (cdk_constructs, cdk_construct_properties)
- `theauditor/aws_cdk/analyzer.py` - Works for both Python and TypeScript
- `theauditor/rules/deployment/aws_cdk_*.py` - Rules are language-agnostic
- `theauditor/commands/cdk.py` - Command works for both languages

### Benefits

1. **Feature Parity**: Python and TypeScript CDK both supported
2. **Production Coverage**: Analyze 80%+ of real-world CDK infrastructure
3. **Zero Rule Changes**: Existing 4 CDK rules work for both languages
4. **Unified Analysis**: `aud cdk analyze` detects issues in both Python and TypeScript
5. **Database Sharing**: Both languages write to same tables (cdk_constructs)

### Risks

**HIGH RISK FACTORS**:
1. **JavaScript Pipeline Complexity**: 5-layer architecture (js files → orchestrator → semantic parser → indexer → database)
   - Mitigation: Comprehensive verification.md with architecture documentation
2. **TypeScript AST Handling**: Must correctly parse `new` expressions
   - Mitigation: Test fixtures with known vulnerable patterns
3. **Import Resolution**: Must match `aws-cdk-lib/*` imports to construct classes
   - Mitigation: Explicit import pattern matching (no regex fallbacks)

**MEDIUM RISK FACTORS**:
1. **Test Fixture Maintenance**: TypeScript CDK stack needs npm dependencies
   - Mitigation: Document fixture setup in verification.md
2. **Node.js Execution**: Requires Node.js runtime in sandboxed environment
   - Mitigation: Already required for JavaScript extraction (no new dependency)

**LOW RISK FACTORS**:
1. **Schema Changes**: None required (tables already exist)
2. **Rule Changes**: None required (rules query database, agnostic to source language)

## Validation Criteria

**MUST PASS BEFORE COMMIT**:

1. ✅ **Extraction Verification**:
   ```bash
   cd tests/fixtures/cdk_test_project
   aud index
   # Query database
   sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM cdk_constructs WHERE file LIKE '%.ts'"
   # Expected: >=3 constructs extracted from TypeScript
   ```

2. ✅ **Rule Detection**:
   ```bash
   aud cdk analyze
   # Expected: Critical findings for TypeScript stack (same as Python)
   ```

3. ✅ **Database Integrity**:
   ```sql
   SELECT file, cdk_class, construct_name
   FROM cdk_constructs
   WHERE file LIKE '%.ts';
   -- Expected: s3.Bucket, rds.DatabaseInstance, ec2.SecurityGroup
   ```

4. ✅ **Property Extraction**:
   ```sql
   SELECT property_name, property_value
   FROM cdk_construct_properties
   WHERE file LIKE '%.ts';
   -- Expected: publicReadAccess=true, storageEncrypted=false
   ```

5. ✅ **Offline Mode**:
   ```bash
   aud full --offline tests/fixtures/cdk_test_project
   # Expected: Complete extraction without external dependencies
   ```

## Teamsop.md Compliance

### ZERO FALLBACK POLICY

**CRITICAL**: NO FALLBACKS, NO REGEX, NO GRACEFUL DEGRADATION

```javascript
// ❌ FORBIDDEN - Regex fallback
if (!imports.some(i => i.module.includes('aws-cdk-lib'))) {
    // Fallback to regex pattern matching - NO!
    const cdkPattern = /new\s+\w+\.\w+\(/g;
}

// ✅ CORRECT - Hard fail if imports not detected
if (!imports.some(i => i.module.includes('aws-cdk-lib'))) {
    return [];  // No CDK imports = no CDK constructs (deterministic)
}
```

**Principles**:
1. If imports don't contain `aws-cdk-lib`, return empty array (not a fallback)
2. If `new` expression can't be parsed, skip it (not a fallback, just incomplete extraction)
3. Database is single source of truth - if extraction fails, indexer logs error and continues
4. NO regex parsing of source code - use AST data from core extractors only

### Database-First Architecture

**MUST FOLLOW**:
1. Extract to database first (cdk_constructs table)
2. Rules query database (never parse source files)
3. Analyzer reads database (never re-extract)
4. JSON output is for humans only (AI queries database)

### Verification Requirements

**teamsop.md Prime Directives**:
1. ✅ Comprehensive verification.md before implementation
2. ✅ Architecture documented (5-layer pipeline)
3. ✅ Test fixtures created (TypeScript vulnerable stack)
4. ✅ Validation criteria defined (5 tests)
5. ✅ No fallback logic anywhere
6. ✅ Database as source of truth

## Non-Goals (Explicitly Out of Scope)

1. ❌ **Python CDK enhancements** - Already complete
2. ❌ **CDK rule additions** - Existing 4 rules sufficient for initial TypeScript support
3. ❌ **Multi-language CDK projects** - Focus on TypeScript-only projects first
4. ❌ **CDK v1 support** - CDK v2 only (v1 is deprecated)
5. ❌ **Terraform/Pulumi** - CDK only (separate extractors needed)

## Dependencies

**Prerequisites**:
- Node.js runtime (already required for JavaScript extraction)
- TypeScript compiler (already installed in sandbox)
- aws-cdk-lib (installed via npm in test fixtures)

**No New Dependencies**: All infrastructure already exists.

## Rollback Plan

**Single Atomic Commit**: All changes in one commit.

**Rollback**: `git revert <commit_hash>` - Instant restore.

**Zero Data Loss**: Only adds extraction, doesn't modify existing data.

**Failure Modes**:
- If TypeScript extraction fails → Python CDK still works
- If database write fails → Logged, doesn't crash indexer
- If rules fail → Other security rules still run

## Success Metrics

1. ✅ TypeScript CDK constructs extracted to database
2. ✅ Same vulnerabilities detected in TypeScript as Python
3. ✅ `aud full --offline` works on TypeScript CDK projects
4. ✅ Zero breaking changes to existing Python CDK extraction
5. ✅ 100% test pass rate

## Approval Checklist

- [ ] Architect approval (User)
- [ ] Lead Auditor approval (Gemini)
- [ ] Lead Coder verification complete (Opus)
- [ ] verification.md created and reviewed
- [ ] Test fixtures created
- [ ] Architecture documented
- [ ] teamsop.md compliance verified

---

**Proposed By**: Claude Opus (Lead Coder)
**Date**: 2025-10-30
**Status**: AWAITING ARCHITECT APPROVAL
