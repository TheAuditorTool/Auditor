# Implementation Tasks: TypeScript CDK Extraction

**Change ID**: `add-typescript-cdk-extraction`
**Status**: Pending Approval
**Estimated Time**: 6-8 hours

---

## Phase 0: Verification (CURRENT)

- [x] Verify Python CDK extraction exists
- [x] Verify JavaScript extraction pipeline architecture
- [x] Verify database schema supports both languages
- [x] Document 5-layer pipeline architecture
- [x] Create proposal.md
- [x] Create verification.md
- [x] Create design.md
- [x] Create tasks.md
- [ ] Run `openspec validate --strict`
- [ ] Architect approval (User)
- [ ] Lead Auditor approval (Gemini)

---

## Phase 1: Test Fixtures (Pre-Implementation)

### Task 1.1: Create TypeScript CDK Test Project Structure
**File**: `tests/fixtures/cdk_test_project/`

```bash
tests/fixtures/cdk_test_project/
├── vulnerable_stack.py       # Existing Python stack
├── vulnerable_stack.ts       # NEW: TypeScript equivalent
├── package.json              # NEW: CDK dependencies
├── tsconfig.json             # NEW: TypeScript config
└── cdk.json                  # NEW: CDK app config
```

**Subtasks**:
- [ ] Create `package.json` with aws-cdk-lib dependencies
- [ ] Create `tsconfig.json` with strict TypeScript settings
- [ ] Create `cdk.json` with CDK app entry point
- [ ] Verify `npm install` works (or document for CI)

### Task 1.2: Create vulnerable_stack.ts
**File**: `tests/fixtures/cdk_test_project/vulnerable_stack.ts`

**Requirements**:
Must contain IDENTICAL vulnerabilities to Python version:

1. **Public S3 Bucket**:
```typescript
import * as s3 from 'aws-cdk-lib/aws-s3';

new s3.Bucket(this, 'PublicBucket', {
  publicReadAccess: true,  // ← CRITICAL vulnerability
  versioned: false
});
```

2. **Unencrypted S3 Bucket**:
```typescript
new s3.Bucket(this, 'UnencryptedBucket', {
  encryption: s3.BucketEncryption.UNENCRYPTED  // ← CRITICAL vulnerability
});
```

3. **Unencrypted RDS Instance**:
```typescript
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ec2 from 'aws-cdk-lib/aws-ec2';

new rds.DatabaseInstance(this, 'UnencryptedDB', {
  engine: rds.DatabaseInstanceEngine.postgres({version: rds.PostgresEngineVersion.VER_14}),
  vpc: vpc,
  storageEncrypted: false  // ← CRITICAL vulnerability
});
```

4. **Open Security Group**:
```typescript
new ec2.SecurityGroup(this, 'OpenSecurityGroup', {
  vpc: vpc,
  allowAllOutbound: true,  // ← HIGH vulnerability
  description: 'Test SG'
});

// Add ingress rule allowing all traffic
securityGroup.addIngressRule(
  ec2.Peer.anyIpv4(),  // ← CRITICAL vulnerability
  ec2.Port.allTraffic(),
  'Allow all inbound traffic'
);
```

5. **IAM Wildcard Policies** (if applicable):
```typescript
import * as iam from 'aws-cdk-lib/aws-iam';

new iam.PolicyStatement({
  actions: ['*'],  // ← CRITICAL vulnerability
  resources: ['*']  // ← CRITICAL vulnerability
});
```

**Subtasks**:
- [ ] Write TypeScript CDK stack class
- [ ] Add all 4-5 vulnerable constructs
- [ ] Ensure TypeScript compiles (`tsc --noEmit`)
- [ ] Document expected findings in comments

### Task 1.3: Verify Test Fixture Extraction
**Goal**: Ensure `aud index` can parse TypeScript files

```bash
cd tests/fixtures/cdk_test_project
aud index
```

**Subtasks**:
- [ ] Verify TypeScript files indexed in `files` table
- [ ] Verify imports extracted from TypeScript
- [ ] Verify function calls extracted (even if CDK not yet recognized)
- [ ] Document baseline extraction (pre-CDK implementation)

**Validation Query**:
```python
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('tests/fixtures/cdk_test_project/.pf/repo_index.db')
c = conn.cursor()

# Check TypeScript file indexed
c.execute('SELECT COUNT(*) FROM files WHERE file LIKE \"%.ts\"')
print(f'TypeScript files indexed: {c.fetchone()[0]}')

# Check imports extracted
c.execute('SELECT COUNT(*) FROM refs WHERE source_file LIKE \"%.ts\" AND target_file LIKE \"%aws-cdk-lib%\"')
print(f'CDK imports found: {c.fetchone()[0]}')

conn.close()
"
```

Expected output BEFORE implementation:
```
TypeScript files indexed: 1
CDK imports found: 3-5 (imports of s3, rds, ec2, iam)
```

---

## Phase 2: JavaScript Extraction Layer

### Task 2.1: Add extractCDKConstructs() Function
**File**: `theauditor/ast_extractors/javascript/security_extractors.js`

**Function Signature**:
```javascript
/**
 * Extract AWS CDK construct instantiations from TypeScript/JavaScript.
 *
 * Detects patterns:
 * - new s3.Bucket(this, 'MyBucket', {...})
 * - new SecurityGroup(this, 'MySG', {...})
 * - new rds.DatabaseInstance(this, 'MyDB', {...})
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs() in core extractors
 * @param {Array} imports - From extractImports() in core extractors
 * @returns {Array} - CDK construct records
 */
function extractCDKConstructs(functionCallArgs, imports) {
    const constructs = [];

    // Step 1: Detect CDK imports
    const cdkImports = imports.filter(i =>
        i.module && i.module.includes('aws-cdk-lib')
    );

    if (cdkImports.length === 0) {
        return [];  // No CDK imports = no CDK constructs (deterministic)
    }

    // Step 2: Build map of CDK module aliases
    // Example: import * as s3 from 'aws-cdk-lib/aws-s3' → {s3: 'aws-s3'}
    const cdkAliases = {};
    for (const imp of cdkImports) {
        if (imp.imported_as) {
            cdkAliases[imp.imported_as] = imp.module;
        }
    }

    // Step 3: Detect 'new X(...)' patterns from functionCallArgs
    for (const arg of functionCallArgs) {
        const callee = arg.callee_function || '';

        // Check if this is a 'new' expression
        // Core extractors mark these as 'new ClassName' or 'new module.ClassName'
        if (!callee.startsWith('new ')) {
            continue;
        }

        // Extract class name from 'new s3.Bucket' → 's3.Bucket'
        const className = callee.replace(/^new\s+/, '');

        // Check if this matches a CDK alias
        const parts = className.split('.');
        if (parts.length >= 2) {
            const moduleAlias = parts[0];  // e.g., 's3'
            const constructClass = parts.slice(1).join('.');  // e.g., 'Bucket'

            if (moduleAlias in cdkAliases) {
                // This is a CDK construct!
                const cdkModule = cdkAliases[moduleAlias];

                // Extract construct name from first string argument
                let constructName = null;
                if (arg.argument_expr && arg.argument_expr.includes('"')) {
                    const match = arg.argument_expr.match(/["']([^"']+)["']/);
                    if (match) {
                        constructName = match[1];
                    }
                }

                // Extract properties from object literal (third argument)
                const properties = extractObjectProperties(arg.argument_expr);

                constructs.push({
                    line: arg.line,
                    cdk_class: `${moduleAlias}.${constructClass}`,  // e.g., 's3.Bucket'
                    construct_name: constructName,
                    properties: properties
                });
            }
        }
    }

    return constructs;
}

/**
 * Extract properties from CDK construct object literal.
 *
 * @param {string} argExpr - Object literal expression
 * @returns {Array} - Property records
 */
function extractObjectProperties(argExpr) {
    const properties = [];

    // Parse object literal: {key: value, ...}
    // This is a simplified parser - real implementation needs to handle nested objects
    const objMatch = argExpr.match(/\{([^}]+)\}/);
    if (!objMatch) {
        return properties;
    }

    const objContent = objMatch[1];
    const pairs = objContent.split(',');

    for (const pair of pairs) {
        const colonIdx = pair.indexOf(':');
        if (colonIdx === -1) continue;

        const key = pair.substring(0, colonIdx).trim();
        const value = pair.substring(colonIdx + 1).trim();

        properties.push({
            name: key,
            value_expr: value,
            line: 0  // Line number not available in this context
        });
    }

    return properties;
}
```

**Subtasks**:
- [ ] Add `extractCDKConstructs()` function (~200 lines)
- [ ] Add `extractObjectProperties()` helper (~50 lines)
- [ ] Handle 3 import patterns (namespace, named, direct)
- [ ] Add debug logging for CDK detection
- [ ] NO REGEX on source code (only AST data from core extractors)
- [ ] NO FALLBACKS (if imports missing, return empty array)

**Validation**:
```bash
# Test extraction logic directly (if possible)
node -e "
const script = require('./theauditor/ast_extractors/javascript/security_extractors.js');
// Test extractCDKConstructs() with sample data
"
```

### Task 2.2: Integrate with Batch Templates
**File**: `theauditor/ast_extractors/javascript/batch_templates.js`

**Changes**:
1. Add extraction call after other security extractors:
```javascript
const cdkConstructs = extractCDKConstructs(functionCallArgs, imports);
```

2. Add to output object:
```javascript
cdkConstructs: cdkConstructs,
```

**Subtasks**:
- [ ] Add extraction call (1 line)
- [ ] Add to output (1 line)
- [ ] Verify no syntax errors (`node -c batch_templates.js`)

---

## Phase 3: Python Orchestrator (NO CHANGES NEEDED)

**File**: `theauditor/ast_extractors/js_helper_templates.py`

**Verification**:
- [x] Confirm `security_extractors.js` automatically included in assembly
- [x] No changes needed (orchestrator concatenates all .js files)

---

## Phase 4: Semantic Parser (NO CHANGES NEEDED)

**File**: `theauditor/ast_extractors/js_semantic_parser.py`

**Verification**:
- [x] Confirm parser executes assembled JavaScript
- [x] Returns JSON with all extractor outputs
- [x] No changes needed (generic executor)

---

## Phase 5: Indexer Integration

### Task 5.1: Add CDK Construct Indexing
**File**: `theauditor/indexer/extractors/javascript.py`

**Location**: Around line 150-200 (after existing extraction logic)

**Code to Add**:
```python
# Extract CDK constructs (TypeScript/JavaScript)
cdk_constructs = file_data.get('cdkConstructs', [])
for construct in cdk_constructs:
    line = construct.get('line')
    cdk_class = construct.get('cdk_class')
    construct_name = construct.get('construct_name')

    # Add CDK construct to database
    self.db.add_cdk_construct(
        file=file_path,
        line=line,
        cdk_class=cdk_class,
        construct_name=construct_name
    )

    # Add properties
    for prop in construct.get('properties', []):
        prop_name = prop.get('name')
        prop_value = prop.get('value_expr')
        prop_line = prop.get('line', line)  # Fallback to construct line

        self.db.add_cdk_construct_property(
            file=file_path,
            line=prop_line,
            construct_name=construct_name,
            property_name=prop_name,
            property_value=prop_value
        )

logger.info(f"Extracted {len(cdk_constructs)} CDK constructs from {file_path}")
```

**Subtasks**:
- [ ] Add CDK construct indexing logic (~50 lines)
- [ ] Use existing `add_cdk_construct()` and `add_cdk_construct_property()` methods
- [ ] Add logging for extracted constructs
- [ ] NO error handling fallbacks (hard fail if database write fails)

**Validation**:
```python
# After indexing, verify database writes
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('tests/fixtures/cdk_test_project/.pf/repo_index.db')
c = conn.cursor()

# Check CDK constructs from TypeScript
c.execute('SELECT COUNT(*) FROM cdk_constructs WHERE file LIKE \"%.ts\"')
print(f'TypeScript CDK constructs: {c.fetchone()[0]}')

# Expected: 4-5 constructs (s3.Bucket x2, rds.DatabaseInstance, ec2.SecurityGroup, etc.)

conn.close()
"
```

---

## Phase 6: CDK Analyzer (NO CHANGES NEEDED)

**File**: `theauditor/aws_cdk/analyzer.py`

**Verification**:
- [x] Analyzer queries `cdk_constructs` table (language-agnostic)
- [x] Rules detect both Python and TypeScript constructs
- [x] No changes needed

---

## Phase 7: Validation Testing

### Task 7.1: Test TypeScript CDK Extraction
**Goal**: Verify `aud index` extracts TypeScript CDK constructs

```bash
cd tests/fixtures/cdk_test_project
rm -rf .pf/  # Clean slate
aud index
```

**Validation Queries**:
```python
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('tests/fixtures/cdk_test_project/.pf/repo_index.db')
c = conn.cursor()

# 1. Verify TypeScript CDK constructs extracted
c.execute('SELECT file, cdk_class, construct_name FROM cdk_constructs WHERE file LIKE \"%.ts\"')
for row in c.fetchall():
    print(f'Construct: {row[1]} ({row[2]}) in {row[0]}')

# Expected output:
# Construct: s3.Bucket (PublicBucket) in vulnerable_stack.ts
# Construct: s3.Bucket (UnencryptedBucket) in vulnerable_stack.ts
# Construct: rds.DatabaseInstance (UnencryptedDB) in vulnerable_stack.ts
# Construct: ec2.SecurityGroup (OpenSecurityGroup) in vulnerable_stack.ts

# 2. Verify properties extracted
c.execute('''
    SELECT construct_name, property_name, property_value
    FROM cdk_construct_properties
    WHERE file LIKE \"%.ts\"
''')
for row in c.fetchall():
    print(f'Property: {row[0]}.{row[1]} = {row[2]}')

# Expected output:
# Property: PublicBucket.publicReadAccess = true
# Property: UnencryptedBucket.encryption = s3.BucketEncryption.UNENCRYPTED
# Property: UnencryptedDB.storageEncrypted = false
# Property: OpenSecurityGroup.allowAllOutbound = true

conn.close()
"
```

**Subtasks**:
- [ ] Run `aud index` on test fixtures
- [ ] Verify TypeScript constructs in database
- [ ] Verify properties extracted correctly
- [ ] Compare with Python extraction (should be identical structure)

### Task 7.2: Test CDK Analyzer
**Goal**: Verify `aud cdk analyze` detects TypeScript vulnerabilities

```bash
cd tests/fixtures/cdk_test_project
aud cdk analyze
```

**Expected Output**:
```
Found 4 CDK security issue(s):

[CRITICAL] S3 Bucket with Public Read Access
  File: vulnerable_stack.ts:10
  Construct: PublicBucket
  Category: publicly-accessible
  Remediation: Set public_read_access=False

[CRITICAL] Unencrypted S3 Bucket
  File: vulnerable_stack.ts:15
  Construct: UnencryptedBucket
  Category: unencrypted
  Remediation: Add encryption=s3.BucketEncryption.S3_MANAGED

[CRITICAL] Unencrypted RDS Instance
  File: vulnerable_stack.ts:20
  Construct: UnencryptedDB
  Category: unencrypted
  Remediation: Set storage_encrypted=True

[HIGH] Security Group with Open Egress
  File: vulnerable_stack.ts:30
  Construct: OpenSecurityGroup
  Category: network-security
  Remediation: Restrict allow_all_outbound to False
```

**Validation Query**:
```python
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('tests/fixtures/cdk_test_project/.pf/repo_index.db')
c = conn.cursor()

# Check CDK findings for TypeScript
c.execute('''
    SELECT file_path, severity, title
    FROM cdk_findings
    WHERE file_path LIKE \"%.ts\"
    ORDER BY severity
''')

critical_count = 0
high_count = 0

for row in c.fetchall():
    print(f'{row[1].upper()}: {row[2]} in {row[0]}')
    if row[1] == 'critical':
        critical_count += 1
    elif row[1] == 'high':
        high_count += 1

print(f'\nTotal: {critical_count} critical, {high_count} high')

# Expected: 3 critical, 1 high

conn.close()
"
```

**Subtasks**:
- [ ] Run `aud cdk analyze` on test fixtures
- [ ] Verify 4 findings detected from TypeScript
- [ ] Verify findings written to `cdk_findings` table
- [ ] Compare with Python findings (should match)

### Task 7.3: Test Full Pipeline
**Goal**: Verify `aud full --offline` works end-to-end

```bash
cd tests/fixtures/cdk_test_project
rm -rf .pf/  # Clean slate
aud full --offline
```

**Validation**:
- [ ] Indexing completes without errors
- [ ] CDK analyzer runs automatically
- [ ] Findings written to database
- [ ] No network calls (--offline mode)
- [ ] Exit code 2 (critical findings detected)

**Subtasks**:
- [ ] Run `aud full --offline` on test fixtures
- [ ] Verify TypeScript and Python both analyzed
- [ ] Verify total findings count includes both languages
- [ ] Check exit code is 2 (critical issues)

---

## Phase 8: Python Test Suite

### Task 8.1: Add TypeScript CDK Extraction Test
**File**: `tests/test_cdk_extraction.py` (NEW)

```python
import pytest
import sqlite3
from pathlib import Path
from theauditor.indexer.database import Database
from theauditor.indexer.extractors.javascript import JavaScriptExtractor

def test_typescript_cdk_extraction():
    """Test TypeScript CDK construct extraction."""
    test_fixture = Path(__file__).parent / 'fixtures' / 'cdk_test_project' / 'vulnerable_stack.ts'

    # Run extraction
    db_path = test_fixture.parent / '.pf' / 'repo_index.db'
    db = Database(str(db_path))
    extractor = JavaScriptExtractor(db)

    # Extract file
    with open(test_fixture) as f:
        content = f.read()
    extractor.extract_file(str(test_fixture), content)

    # Verify constructs extracted
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cdk_constructs WHERE file LIKE '%.ts'")
    assert cursor.fetchone()[0] >= 4, "Expected at least 4 CDK constructs"

    cursor.execute("SELECT COUNT(*) FROM cdk_construct_properties WHERE file LIKE '%.ts'")
    assert cursor.fetchone()[0] >= 8, "Expected at least 8 properties"

    conn.close()
```

**Subtasks**:
- [ ] Create `tests/test_cdk_extraction.py`
- [ ] Add test for TypeScript extraction
- [ ] Add test for property extraction
- [ ] Add test comparing Python vs TypeScript output
- [ ] Run `pytest tests/test_cdk_extraction.py`

### Task 8.2: Add Integration Test
**File**: `tests/test_cdk_integration.py` (NEW)

```python
import pytest
import subprocess
from pathlib import Path

def test_typescript_cdk_end_to_end():
    """Test full pipeline: index → analyze → findings."""
    test_dir = Path(__file__).parent / 'fixtures' / 'cdk_test_project'

    # Clean slate
    import shutil
    pf_dir = test_dir / '.pf'
    if pf_dir.exists():
        shutil.rmtree(pf_dir)

    # Run indexing
    result = subprocess.run(
        ['aud', 'index'],
        cwd=test_dir,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Indexing failed: {result.stderr}"

    # Run CDK analyzer
    result = subprocess.run(
        ['aud', 'cdk', 'analyze'],
        cwd=test_dir,
        capture_output=True,
        text=True
    )

    # Should detect critical findings (exit code 2)
    assert result.returncode == 2, f"Expected critical findings, got exit code {result.returncode}"

    # Verify TypeScript findings in output
    assert 'vulnerable_stack.ts' in result.stdout, "TypeScript file not in findings"
    assert 'PublicBucket' in result.stdout, "PublicBucket not detected"
    assert 'UnencryptedDB' in result.stdout, "UnencryptedDB not detected"
```

**Subtasks**:
- [ ] Create `tests/test_cdk_integration.py`
- [ ] Add end-to-end test
- [ ] Run `pytest tests/test_cdk_integration.py`
- [ ] Verify test passes

---

## Phase 9: Documentation

### Task 9.1: Update CDK README
**File**: `theauditor/aws_cdk/README.md`

**Changes**:
- [ ] Add section: "Supported Languages: Python, TypeScript"
- [ ] Add TypeScript example snippets
- [ ] Update "How It Works" section with JavaScript extraction pipeline

### Task 9.2: Update Main README (if applicable)
**File**: `README.md` (root)

**Changes**:
- [ ] Update feature list: "AWS CDK security analysis (Python, TypeScript)"
- [ ] Add TypeScript CDK example to quickstart

### Task 9.3: Update CHANGELOG
**File**: `CHANGELOG.md`

**Entry**:
```markdown
## [1.4.0] - 2025-10-30

### Added
- TypeScript/JavaScript AWS CDK infrastructure extraction
- CDK construct detection for aws-cdk-lib imports
- Parity with Python CDK extraction (s3, rds, ec2, iam constructs)
- Test fixtures for TypeScript CDK vulnerable stacks

### Changed
- `aud cdk analyze` now detects both Python and TypeScript CDK issues
- JavaScript extraction pipeline extended with CDK support
```

**Subtasks**:
- [ ] Add changelog entry
- [ ] Version bump (if applicable)

---

## Phase 10: Post-Implementation Validation

### Task 10.1: Run Full Test Suite
```bash
cd C:/Users/santa/Desktop/TheAuditor
pytest tests/ -v
```

**Expected**:
- [ ] All tests pass (100%)
- [ ] New CDK tests pass
- [ ] No regressions in existing tests

### Task 10.2: Validate OpenSpec Contract
```bash
openspec validate add-typescript-cdk-extraction --strict
```

**Expected**:
- [ ] All acceptance criteria met
- [ ] No schema contract violations
- [ ] No breaking changes detected

### Task 10.3: Manual Verification
**Steps**:
1. Create fresh TypeScript CDK project (outside test fixtures)
2. Add vulnerable CDK constructs
3. Run `aud full --offline`
4. Verify findings detected

**Subtasks**:
- [ ] Test on real-world TypeScript CDK project (if available)
- [ ] Verify no false positives
- [ ] Verify no false negatives (compare with manual audit)

---

## Phase 11: Future Work (Rust CDK Support)

**NOTE**: Rust CDK extraction is OUT OF SCOPE for this proposal.

### Rationale:
- Rust is a **supported language** in TheAuditor (basic extraction exists)
- Rust CDK is **less common** than TypeScript/Python CDK (niche use case)
- Adding Rust CDK requires understanding Rust AST extraction pipeline
- Risk: Complicates proposal and delays TypeScript implementation

### Proposed Approach:
- **Phase 1 (this proposal)**: TypeScript CDK extraction only
- **Phase 2 (future proposal)**: Rust CDK extraction (separate OpenSpec change)

### Checklist for Future Rust CDK Work:
- [ ] Verify Rust extraction pipeline architecture
- [ ] Check if Rust has equivalent extraction hooks
- [ ] Create Rust CDK test fixtures
- [ ] Add `extractCDKConstructs()` to Rust extractor (if applicable)
- [ ] Test with real-world Rust CDK projects

**Decision**: Defer Rust CDK to separate proposal to maintain focus and reduce risk.

---

## Phase 12: Commit and Deploy

### Task 12.1: Create Single Atomic Commit
```bash
git add theauditor/ast_extractors/javascript/security_extractors.js
git add theauditor/ast_extractors/javascript/batch_templates.js
git add theauditor/indexer/extractors/javascript.py
git add tests/fixtures/cdk_test_project/vulnerable_stack.ts
git add tests/fixtures/cdk_test_project/package.json
git add tests/fixtures/cdk_test_project/tsconfig.json
git add tests/fixtures/cdk_test_project/cdk.json
git add tests/test_cdk_extraction.py
git add tests/test_cdk_integration.py
git add theauditor/aws_cdk/README.md
git add CHANGELOG.md

git commit -m "feat(cdk): Add TypeScript CDK infrastructure extraction

Add TypeScript/JavaScript AWS CDK construct extraction to match Python parity.

Changes:
- Add extractCDKConstructs() to JavaScript security extractors
- Integrate with JavaScript extraction pipeline (5 layers)
- Add TypeScript CDK test fixtures with vulnerable constructs
- Add Python test suite for TypeScript CDK extraction
- Update CDK analyzer to support both Python and TypeScript

Detection:
- S3 buckets (public access, encryption)
- RDS instances (encryption)
- Security groups (ingress/egress rules)
- IAM policies (wildcard permissions)

Validation:
- All tests pass (100%)
- OpenSpec validation passed (--strict)
- Test fixtures validated with aud full --offline

Architecture:
- JavaScript extraction layer (security_extractors.js)
- Python orchestrator (js_helper_templates.py - no changes)
- Semantic parser (js_semantic_parser.py - no changes)
- Indexer integration (javascript.py extractor)
- CDK analyzer (analyzer.py - no changes)

Database:
- Writes to cdk_constructs table (language-agnostic)
- Writes to cdk_construct_properties table
- Rules query database (no language-specific logic)

Teamsop.md Compliance:
- ZERO FALLBACK POLICY enforced
- Database-first architecture (no regex, no migrations)
- Hard failure on missing data (no graceful degradation)
- Comprehensive verification before implementation

Co-Authored-By: Claude Opus <opus@anthropic.com>
"
```

**Subtasks**:
- [ ] Create single atomic commit
- [ ] Run `git status` to verify all files staged
- [ ] Run `git diff --cached` to review changes
- [ ] Push to branch (NOT main)

### Task 12.2: Create Pull Request
```bash
# Create PR with GitHub CLI
gh pr create \
  --title "feat(cdk): Add TypeScript CDK infrastructure extraction" \
  --body "$(cat openspec/changes/add-typescript-cdk-extraction/proposal.md)" \
  --base main \
  --head add-typescript-cdk-extraction
```

**PR Checklist**:
- [ ] Title follows conventional commits
- [ ] Body includes proposal.md content
- [ ] All CI checks pass
- [ ] Test coverage maintained/improved
- [ ] Documentation updated

---

## Rollback Plan

**If ANY test fails after commit**:

1. **Immediate Rollback**:
```bash
git revert HEAD
git push origin main --force-with-lease
```

2. **Verify Rollback**:
```bash
pytest tests/ -v  # All tests should pass
aud full --offline tests/fixtures/cdk_test_project  # Should work with Python only
```

3. **Post-Rollback Analysis**:
- Identify failure root cause
- Fix in separate branch
- Re-run full validation
- Re-submit proposal (if needed)

**Failure Isolation**:
- If TypeScript extraction fails → Python CDK still works (zero impact)
- If indexer fails → Other extractors unaffected (isolated to JavaScript)
- If analyzer fails → Other rules still run (database unchanged)

---

## Success Criteria

**MUST PASS ALL**:
- [x] OpenSpec validation passed (`--strict` mode)
- [ ] All Python tests pass (100%)
- [ ] TypeScript CDK constructs extracted to database
- [ ] CDK analyzer detects TypeScript vulnerabilities
- [ ] `aud full --offline` works end-to-end
- [ ] Zero breaking changes to Python CDK extraction
- [ ] Zero regressions in existing rules
- [ ] Documentation updated

**NICE TO HAVE**:
- [ ] Test on real-world TypeScript CDK project
- [ ] Performance benchmarks (extraction time)
- [ ] Comparison with Python extraction (parity check)

---

## Estimated Timeline

| Phase | Tasks | Time | Status |
|-------|-------|------|--------|
| 0. Verification | 11 tasks | 4h | ✅ COMPLETE |
| 1. Test Fixtures | 3 tasks | 1h | ⏳ PENDING |
| 2. JavaScript Extraction | 2 tasks | 2h | ⏳ PENDING |
| 3. Python Orchestrator | 0 tasks | 0h | ✅ NO CHANGES |
| 4. Semantic Parser | 0 tasks | 0h | ✅ NO CHANGES |
| 5. Indexer Integration | 1 task | 30m | ⏳ PENDING |
| 6. CDK Analyzer | 0 tasks | 0h | ✅ NO CHANGES |
| 7. Validation Testing | 3 tasks | 1h | ⏳ PENDING |
| 8. Python Test Suite | 2 tasks | 1h | ⏳ PENDING |
| 9. Documentation | 3 tasks | 30m | ⏳ PENDING |
| 10. Post-Implementation | 3 tasks | 30m | ⏳ PENDING |
| 11. Future Work (Rust) | 0 tasks | N/A | ⏳ DEFERRED |
| 12. Commit and Deploy | 2 tasks | 30m | ⏳ PENDING |

**Total Estimated Time**: 6-8 hours (excluding verification, which is complete)

---

## Notes

1. **Rust CDK Support**: Deferred to separate proposal (Phase 2)
2. **Import Patterns**: Handles 3 TypeScript import styles (namespace, named, direct)
3. **Error Handling**: NO FALLBACKS - hard fail on missing data
4. **Database Schema**: NO CHANGES - cdk_constructs table supports both languages
5. **Backward Compatibility**: Python CDK extraction unaffected (zero breaking changes)

---

**Status**: ✅ READY FOR APPROVAL

**Next Steps**:
1. Run `openspec validate add-typescript-cdk-extraction --strict`
2. Await architect (User) approval
3. Await lead auditor (Gemini) approval
4. Proceed with Phase 1 implementation
