# Design: AWS CDK Infrastructure-as-Code Security Analysis

**Change ID**: `add-aws-cdk-analysis`
**Design Version**: 1.0
**Last Updated**: 2025-10-26
**Status**: Pre-implementation

---

## Table of Contents

1. [Context & Constraints](#context--constraints)
2. [Goals & Non-Goals](#goals--non-goals)
3. [Architecture Integration](#architecture-integration)
4. [Core Design Decisions](#core-design-decisions)
5. [Data Flow](#data-flow)
6. [Schema Design](#schema-design)
7. [Rule Implementation Strategy](#rule-implementation-strategy)
8. [Orchestrator Integration](#orchestrator-integration)
9. [Pipeline Integration](#pipeline-integration)
10. [Error Handling & Edge Cases](#error-handling--edge-cases)
11. [Performance Considerations](#performance-considerations)
12. [Testing Strategy](#testing-strategy)
13. [Migration Plan](#migration-plan)
14. [Open Questions](#open-questions)

---

## Context & Constraints

### Existing Architecture (MUST RESPECT)

TheAuditor follows a **layered extraction architecture** with strict responsibility boundaries:

1. **Indexer Orchestrator** - Coordinates file walking, extractor execution, database writes
2. **Extractors** - Language-specific AST extraction (auto-discovered via `@register_extractor`)
3. **AST Implementations** - Pure extraction logic (NO file context)
4. **Database Manager** - Batched writes (200 records/batch)
5. **Schema Contract** - Single source of truth (`schema.py`)
6. **Rules Orchestrator** - Dynamic rule discovery and execution
7. **Pipeline** - 4-stage parallelized execution

### Critical Constraints (FROM CLAUDE.md)

**ABSOLUTE PROHIBITIONS**:
- ❌ NO FALLBACK LOGIC (no try/except with alternative queries)
- ❌ NO TABLE EXISTENCE CHECKS (schema contract guarantees tables exist)
- ❌ NO REGEX ON FILE CONTENT (database-first architecture)
- ❌ NO FILE_PATH IN EXTRACTOR RETURNS (3-layer responsibility pattern)
- ❌ NO JSON FALLBACKS (hard fail if database wrong)

**MANDATORY PATTERNS**:
- ✅ Database-first detection (query indexed tables)
- ✅ Hard fail on missing tables (indicates contract violation)
- ✅ Batch database inserts (200 records minimum)
- ✅ Standardized rule signatures (`StandardRuleContext → List[StandardFinding]`)
- ✅ Dynamic discovery (no hardcoded imports)

### Stakeholders

- **Architect (Human)**: Final authority, schema changes, breaking changes
- **Lead Auditor (Gemini)**: Rule logic quality, false positive rate
- **AI Coder (Opus/Claude)**: Implementation, verification, testing

---

## Goals & Non-Goals

### Goals

1. **Infrastructure Security Coverage**: Detect AWS CDK misconfigurations with zero AWS credentials
2. **Seamless Integration**: Auto-discovery via orchestrator (no manual registration)
3. **Database-First Architecture**: Query indexed tables, not file content
4. **Zero False Positives**: Conservative detection (prefer false negatives)
5. **Performance**: <5 seconds overhead for 50-file CDK projects

### Non-Goals

1. ❌ **CDK v1 Support**: Focus on CDK v2 (current stable)
2. ❌ **CloudFormation Analysis**: CDK-specific, not raw CFN templates
3. ❌ **Terraform/Pulumi**: Separate proposals
4. ❌ **Runtime Validation**: Static analysis only (no deployed resource checks)
5. ❌ **Custom Construct Inference**: Analyze only built-in AWS constructs

---

## Architecture Integration

### Layered Integration Map

```
┌──────────────────────────────────────────────────────────┐
│ LAYER 1: CLI Entry Point                                 │
│ theauditor/cli.py + theauditor/commands/cdk.py           │
│ ✅ Registers `aud cdk analyze` command                   │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│ LAYER 2: Pipeline Orchestration                          │
│ theauditor/pipelines.py                                  │
│ ✅ Adds `cdk-analyze` to Stage 2 (Data Preparation)     │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│ LAYER 3: Analyzer Orchestrator                           │
│ theauditor/analyzers/aws_cdk_analyzer.py (NEW)           │
│ ✅ Calls individual check methods                        │
│ ✅ Aggregates findings                                   │
│ ✅ Writes to cdk_findings + findings_consolidated        │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│ LAYER 4: Rules Layer                                     │
│ theauditor/rules/deployment/aws_cdk_*.py (NEW)           │
│ ✅ Database-first detection (query cdk_constructs)       │
│ ✅ Auto-discovered by RulesOrchestrator                  │
│ ✅ Uses StandardRuleContext + StandardFinding            │
└──────────────────────────────────────────────────────────┘
                            ↑ (queries)
┌──────────────────────────────────────────────────────────┐
│ LAYER 5: Database (repo_index.db)                        │
│ theauditor/indexer/database.py                           │
│ ✅ cdk_constructs table                                  │
│ ✅ cdk_construct_properties table                        │
│ ✅ cdk_findings table                                    │
└──────────────────────────────────────────────────────────┘
                            ↑ (writes)
┌──────────────────────────────────────────────────────────┐
│ LAYER 6: Extractor Layer                                 │
│ theauditor/indexer/extractors/aws_cdk.py (NEW)           │
│ ✅ Filters by CDK imports                                │
│ ✅ Delegates to python_impl.py                           │
│ ✅ Returns data WITHOUT file_path keys                   │
└──────────────────────────────────────────────────────────┘
                            ↑ (delegates)
┌──────────────────────────────────────────────────────────┐
│ LAYER 7: AST Implementation                              │
│ theauditor/ast_extractors/python_impl.py                 │
│ ✅ extract_python_cdk_constructs(tree)                   │
│ ✅ Walks ast.Call nodes                                  │
│ ✅ Uses ast.unparse() for property values                │
└──────────────────────────────────────────────────────────┘
                            ↑ (parses)
┌──────────────────────────────────────────────────────────┐
│ LAYER 8: Schema Contract                                 │
│ theauditor/indexer/schema.py                             │
│ ✅ Defines table schemas                                 │
│ ✅ Single source of truth                                │
└──────────────────────────────────────────────────────────┘
```

### Integration with Existing Orchestrator

**RulesOrchestrator** (`theauditor/rules/orchestrator.py`) already provides:
- ✅ Dynamic rule discovery via `_discover_all_rules()`
- ✅ Signature analysis via `_analyze_rule()`
- ✅ Metadata-based filtering via `_should_run_rule_on_file()`
- ✅ Execution scope management (`database` vs `file`)

**NO CHANGES NEEDED** to orchestrator. CDK rules will be auto-discovered.

---

## Core Design Decisions

### Decision 1: Dedicated Extractor vs Extending PythonExtractor

**Options Considered**:
1. **Dedicated `AWSCdkExtractor`** (CHOSEN)
2. Add CDK logic to existing `PythonExtractor`

**Decision**: Dedicated extractor

**Rationale**:
- **Separation of concerns**: CDK extraction is semantically different (infrastructure, not app code)
- **Conditional execution**: Only run when CDK imports detected (performance)
- **Independent evolution**: CDK rules evolve separately from Python app rules
- **Metadata filtering**: Can use `target_file_patterns=['cdk.out/', 'infrastructure/']`

**Trade-offs**:
- ➕ Clear boundaries
- ➕ Better performance (skips non-CDK files)
- ➖ Slight code duplication (import checking)

### Decision 2: Database Schema - Normalized vs Denormalized

**Options Considered**:
1. **Normalized schema** (CHOSEN): `cdk_constructs` + `cdk_construct_properties`
2. Denormalized: Store all properties as JSON in single table

**Decision**: Normalized schema

**Rationale**:
- **Queryability**: Can filter properties without JSON parsing (`WHERE property_name = 'public_read_access'`)
- **Consistency**: Matches existing pattern (`function_call_args` table structure)
- **Performance**: Indexed property_name lookups
- **Schema evolution**: Can add property metadata later

**Schema**:
```sql
-- Constructs table (one row per instantiation)
CREATE TABLE cdk_constructs (
    construct_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    cdk_class TEXT NOT NULL,       -- e.g., 'aws_cdk.aws_s3.Bucket'
    construct_name TEXT             -- e.g., 'myBucket'
);

-- Properties table (many rows per construct)
CREATE TABLE cdk_construct_properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    construct_id TEXT NOT NULL,
    property_name TEXT NOT NULL,
    property_value_expr TEXT NOT NULL,
    line INTEGER NOT NULL,
    FOREIGN KEY (construct_id) REFERENCES cdk_constructs(construct_id)
);

CREATE INDEX idx_cdk_props_construct ON cdk_construct_properties(construct_id);
CREATE INDEX idx_cdk_props_name ON cdk_construct_properties(property_name);
```

### Decision 3: Property Value Storage - AST Objects vs String Serialization

**Options Considered**:
1. **String serialization via `ast.unparse()`** (CHOSEN)
2. Store AST node type + raw value
3. Evaluate expressions to Python values

**Decision**: String serialization

**Rationale**:
- **Simplicity**: One string column, no complex deserialization
- **Debuggability**: Human-readable in database browser
- **Pattern matching**: Can use SQL `LIKE` for pattern detection
- **Safety**: No code execution (`eval()` forbidden)

**Example**:
```python
# CDK Code
bucket = s3.Bucket(self, "MyBucket",
    public_read_access=True,
    encryption=s3.BucketEncryption.UNENCRYPTED
)

# Stored in database
property_name = "public_read_access"
property_value_expr = "True"  # ← ast.unparse(keyword.value)
```

### Decision 4: Rule Architecture - Monolithic Analyzer vs Individual Rules

**Options Considered**:
1. **Individual rule files** (CHOSEN): `aws_cdk_s3_public_analyze.py`, etc.
2. Monolithic `AWSCdkAnalyzer` with all checks

**Decision**: Individual rule files

**Rationale**:
- **Consistency**: Matches existing pattern (100+ rules in `/rules/`)
- **Auto-discovery**: RulesOrchestrator finds and executes automatically
- **Modularity**: Can enable/disable specific checks
- **Testability**: Isolated unit tests per rule
- **Community contributions**: Easy to add new checks

**Pattern**:
```python
# theauditor/rules/deployment/aws_cdk_s3_public_analyze.py
from theauditor.rules.base import StandardRuleContext, StandardFinding, RuleMetadata

METADATA = RuleMetadata(
    name="aws_cdk_s3_public",
    category="deployment",
    target_extensions=['.py'],
    exclude_patterns=['test/', 'migrations/'],
    execution_scope='database'
)

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect public S3 buckets in CDK code."""
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # Query cdk_constructs + cdk_construct_properties
    cursor.execute("""
        SELECT c.file_path, c.line, c.construct_name
        FROM cdk_constructs c
        JOIN cdk_construct_properties p ON c.construct_id = p.construct_id
        WHERE c.cdk_class LIKE '%.Bucket'
          AND p.property_name = 'public_read_access'
          AND p.property_value_expr = 'True'
    """)

    # Return StandardFinding objects
```

### Decision 5: Construct Identification - Name Matching vs Type Inference

**Options Considered**:
1. **String pattern matching on class names** (CHOSEN)
2. Full type inference via Python type checker
3. Import path resolution

**Decision**: String pattern matching

**Rationale**:
- **Simplicity**: SQL `LIKE '%.Bucket'` patterns
- **No dependencies**: No mypy/pyright integration needed
- **Performance**: O(1) indexed lookups
- **Robustness**: Works with aliased imports

**Pattern Matching Strategy**:
```sql
-- Match by class suffix (handles various import styles)
WHERE cdk_class LIKE '%.Bucket'      -- s3.Bucket, aws_s3.Bucket, etc.
WHERE cdk_class LIKE '%.DatabaseInstance'  -- rds.DatabaseInstance
WHERE cdk_class LIKE '%.SecurityGroup'     -- ec2.SecurityGroup
```

---

## Data Flow

### Extraction Flow (Indexing Phase)

```
1. IndexerOrchestrator walks files
   └─> Encounters app.py

2. PythonExtractor runs first (symbols, imports, calls)
   └─> Extracts: import aws_cdk
   └─> Writes to: imports table

3. AWSCdkExtractor.should_extract(file_info)
   └─> Queries imports table
   └─> Returns: True (has aws_cdk import)

4. AWSCdkExtractor.extract(file_info, content, tree)
   └─> Delegates to: python_impl.extract_python_cdk_constructs(tree)
   └─> Returns: { 'cdk_constructs': [...], 'cdk_construct_properties': [...] }
   └─> NO file_path keys in returned data

5. IndexerOrchestrator._store_extracted_data(extracted, file_info)
   └─> Calls: db_manager.add_cdk_construct(file_path, line, cdk_class, ...)
   └─> file_path comes from file_info (orchestrator context)
   └─> Batch writes to database

6. Database contains indexed CDK facts
   └─> cdk_constructs table populated
   └─> cdk_construct_properties table populated
```

### Analysis Flow (Detection Phase)

```
1. Pipeline Stage 2 runs: aud cdk analyze

2. CdkCommand.cdk_analyze()
   └─> Instantiates: AWSCdkAnalyzer(db_path)

3. AWSCdkAnalyzer.analyze()
   └─> Calls check methods:
       ├─> _check_public_s3_buckets()
       ├─> _check_unencrypted_storage()
       ├─> _check_open_security_groups()
       └─> _check_iam_wildcards()

4. Each check method:
   └─> Queries: cdk_constructs + cdk_construct_properties
   └─> Returns: List[Dict] (findings)

5. AWSCdkAnalyzer._write_findings()
   └─> Writes to:
       ├─> cdk_findings (CDK-specific table)
       └─> findings_consolidated (global findings)

6. Pipeline continues to FCE (Stage 4)
   └─> Correlates CDK findings with app code findings
```

---

## Schema Design

### Full Schema Definitions

```python
# theauditor/indexer/schema.py

cdk_constructs = TableSchema(
    name='cdk_constructs',
    columns=[
        ColumnDef('construct_id', 'TEXT', primary_key=True),
        ColumnDef('file_path', 'TEXT', nullable=False),
        ColumnDef('line', 'INTEGER', nullable=False),
        ColumnDef('cdk_class', 'TEXT', nullable=False),
        ColumnDef('construct_name', 'TEXT', nullable=True)
    ],
    indexes=[
        IndexDef('idx_cdk_constructs_file', ['file_path']),
        IndexDef('idx_cdk_constructs_class', ['cdk_class'])
    ]
)

cdk_construct_properties = TableSchema(
    name='cdk_construct_properties',
    columns=[
        ColumnDef('id', 'INTEGER', primary_key=True, autoincrement=True),
        ColumnDef('construct_id', 'TEXT', nullable=False),
        ColumnDef('property_name', 'TEXT', nullable=False),
        ColumnDef('property_value_expr', 'TEXT', nullable=False),
        ColumnDef('line', 'INTEGER', nullable=False)
    ],
    indexes=[
        IndexDef('idx_cdk_props_construct', ['construct_id']),
        IndexDef('idx_cdk_props_name', ['property_name'])
    ]
)

cdk_findings = TableSchema(
    name='cdk_findings',
    columns=[
        ColumnDef('finding_id', 'TEXT', primary_key=True),
        ColumnDef('file_path', 'TEXT', nullable=False),
        ColumnDef('construct_id', 'TEXT', nullable=True),
        ColumnDef('category', 'TEXT', nullable=False),
        ColumnDef('severity', 'TEXT', nullable=False),
        ColumnDef('title', 'TEXT', nullable=False),
        ColumnDef('description', 'TEXT', nullable=False),
        ColumnDef('remediation', 'TEXT', nullable=True),
        ColumnDef('line', 'INTEGER', nullable=True)
    ],
    indexes=[
        IndexDef('idx_cdk_findings_severity', ['severity']),
        IndexDef('idx_cdk_findings_category', ['category'])
    ]
)
```

### Composite Key Design

**construct_id Format**: `{file_path}::L{line}::{cdk_class}::{construct_name}`

**Example**: `infrastructure/app.py::L42::aws_cdk.aws_s3.Bucket::myBucket`

**Rationale**:
- Unique across entire project (file + line + class + name)
- Human-readable for debugging
- Supports multiple constructs on same line (different names)

---

## Rule Implementation Strategy

### Rule Categorization

| Rule File | Detects | Severity | CWE |
|-----------|---------|----------|-----|
| `aws_cdk_s3_public_analyze.py` | Public S3 buckets | CRITICAL | CWE-732 |
| `aws_cdk_encryption_analyze.py` | Unencrypted RDS/EBS/DynamoDB | HIGH | CWE-311 |
| `aws_cdk_sg_open_analyze.py` | Open security groups (0.0.0.0/0) | CRITICAL | CWE-284 |
| `aws_cdk_iam_wildcards_analyze.py` | IAM wildcard permissions | HIGH | CWE-269 |

### Detection Patterns (Example: S3 Public Bucket)

```python
def _check_public_s3_buckets(cursor) -> List[StandardFinding]:
    """Detect S3 buckets with public read access."""
    findings = []

    # Find all S3 Bucket constructs
    cursor.execute("""
        SELECT construct_id, file_path, line, construct_name
        FROM cdk_constructs
        WHERE cdk_class LIKE '%.Bucket'
    """)

    for construct_id, file_path, line, construct_name in cursor.fetchall():
        # Check for public_read_access property
        cursor.execute("""
            SELECT property_value_expr
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND property_name = 'public_read_access'
        """, [construct_id])

        result = cursor.fetchone()
        if result and result[0] == 'True':
            findings.append(StandardFinding(
                file_path=file_path,
                line=line,
                rule_name='aws-cdk-s3-public',
                message=f'S3 bucket "{construct_name}" has public read access enabled',
                severity=Severity.CRITICAL,
                category='deployment',
                cwe_id='CWE-732',
                snippet=f'public_read_access=True'
            ))

    return findings
```

### False Positive Mitigation

**Strategy**: Conservative detection (prefer false negatives)

**Techniques**:
1. **Explicit pattern matching**: Only flag `public_read_access=True`, not permissive IAM policies
2. **Context awareness**: Check for `block_public_access` configuration
3. **Comment detection**: Ignore if line has `# SAFE: reviewed` comment
4. **Test file exclusion**: Skip `test/`, `__tests__/`, `*_test.py`

---

## Orchestrator Integration

### Auto-Discovery Flow

```python
# theauditor/rules/orchestrator.py (EXISTING - NO CHANGES)

class RulesOrchestrator:
    def _discover_all_rules(self) -> Dict[str, List[RuleInfo]]:
        # Walks theauditor/rules/ directory
        # Finds: theauditor/rules/deployment/aws_cdk_s3_public_analyze.py
        # Detects: def analyze(context: StandardRuleContext)
        # Validates: Has METADATA attribute
        # Creates: RuleInfo(name='analyze', module='...', is_standardized=True)
        # Returns: {'deployment': [RuleInfo(...)]}
```

**NO MANUAL REGISTRATION REQUIRED**

### Metadata-Based Filtering

```python
# theauditor/rules/deployment/aws_cdk_s3_public_analyze.py

METADATA = RuleMetadata(
    name="aws_cdk_s3_public",
    category="deployment",
    target_extensions=['.py'],                    # Only Python files
    target_file_patterns=['cdk.out/', 'infrastructure/', 'infra/'],  # Common CDK dirs
    exclude_patterns=['test/', 'migrations/', '__pycache__/'],
    execution_scope='database'                    # Run once per project, not per file
)
```

**Orchestrator uses this to**:
- Skip non-Python files
- Skip test files
- Run rule ONCE (database scope, not per file)

---

## Pipeline Integration

### Stage 2 Modification

```python
# theauditor/pipelines.py

command_order = [
    # Stage 1: Foundation
    ("index", []),
    ("detect-frameworks", []),

    # Stage 2: Data Preparation
    ("workset", ["--all"]),
    ("graph", ["build"]),
    ("graph", ["build-dfg"]),
    ("terraform", ["provision"]),
    ("cdk", ["analyze"]),  # ← NEW: Add here
    ("graph", ["analyze"]),

    # Stage 3: Heavy Parallel Analysis
    # ... (Track A/B/C)

    # Stage 4: Final Aggregation
    ("fce", []),
    ("report", []),
    ("summary", [])
]
```

**Execution Order**:
1. `index` builds database (includes CDK extraction)
2. `graph build-dfg` builds data flow graph
3. `terraform provision` analyzes Terraform
4. **`cdk analyze` analyzes AWS CDK** ← NEW
5. `graph analyze` analyzes dependency graph

**Dependencies**:
- Requires `index` to complete (needs `cdk_constructs` table populated)
- Independent of `terraform provision` (different IaC tools)

---

## Error Handling & Edge Cases

### Edge Case 1: No CDK Imports

**Scenario**: Project has no `import aws_cdk`

**Behavior**:
1. `AWSCdkExtractor.should_extract()` returns `False` (checks imports table)
2. Extraction skipped (zero overhead)
3. `cdk_constructs` table remains empty
4. Rules return empty findings (no crashes)

### Edge Case 2: Dynamic Property Values

**Scenario**: `bucket_name=config.get_bucket_name()`

**Behavior**:
1. `ast.unparse()` serializes to `"config.get_bucket_name()"`
2. Stored as-is in `property_value_expr`
3. Rules cannot evaluate dynamic expressions
4. **Documented limitation**: Accept false negative

### Edge Case 3: CDK v1 vs v2

**Scenario**: Old project uses CDK v1 (`@aws-cdk/aws-s3`)

**Behavior**:
1. Phase 1: Only support v2 (`aws_cdk.aws_s3`)
2. Detection: Check import module name
3. Fallback: Skip CDK v1 files (log warning)
4. Future: OpenSpec proposal for v1 support if needed

### Edge Case 4: Custom Constructs

**Scenario**: `MyCustomBucket(Construct)` extends `s3.Bucket`

**Behavior**:
1. Phase 1: Only detect built-in AWS constructs
2. Detection: Match `cdk_class LIKE 'aws_cdk.%'`
3. Skip custom constructs (no inheritance analysis)
4. **Documented limitation**: Custom constructs not analyzed

### Error Handling Strategy

**NO FALLBACKS**:
```python
# ✅ CORRECT: Hard fail if table missing
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # NO try/except, NO table existence check
    cursor.execute("SELECT * FROM cdk_constructs LIMIT 1")
    # If table doesn't exist, let it crash (schema contract violation)
```

**Graceful Degradation ONLY for Empty Tables**:
```python
# ✅ CORRECT: Empty results if no CDK code
cursor.execute("SELECT COUNT(*) FROM cdk_constructs")
if cursor.fetchone()[0] == 0:
    return []  # No CDK code in project
```

---

## Performance Considerations

### Indexing Performance

**Extractor Overhead**:
- Import check: O(1) lookup in imports table
- AST walk: O(n) where n = number of CDK construct calls
- Database write: Batched (200 records)

**Estimated Impact**:
- 50 CDK files × 10 constructs/file = 500 constructs
- 500 constructs × 3 properties/construct = 1,500 property records
- Batch writes: 1,500 ÷ 200 = 8 batches
- **Total overhead**: +2-3 seconds

### Analysis Performance

**Query Patterns**:
```sql
-- Indexed lookup (fast)
SELECT * FROM cdk_constructs WHERE cdk_class LIKE '%.Bucket'

-- JOIN with properties (indexed on construct_id)
SELECT c.*, p.property_value_expr
FROM cdk_constructs c
JOIN cdk_construct_properties p ON c.construct_id = p.construct_id
WHERE p.property_name = 'public_read_access'
```

**Worst Case**:
- 1,000 constructs × 4 rules = 4,000 queries
- Indexed lookups: ~0.1ms each
- **Total**: ~400ms

**Optimization**: Batch queries per construct type
```sql
-- Single query for all S3 buckets
SELECT c.construct_id, c.file_path, c.line,
       MAX(CASE WHEN p.property_name = 'public_read_access' THEN p.property_value_expr END) AS public_access,
       MAX(CASE WHEN p.property_name = 'encryption' THEN p.property_value_expr END) AS encryption
FROM cdk_constructs c
LEFT JOIN cdk_construct_properties p ON c.construct_id = p.construct_id
WHERE c.cdk_class LIKE '%.Bucket'
GROUP BY c.construct_id
```

---

## Testing Strategy

### Unit Tests

**Test Files**:
- `tests/test_cdk_extractor.py` - Extractor logic
- `tests/test_cdk_rules.py` - Individual rule precision/recall
- `tests/test_cdk_analyzer.py` - Analyzer orchestration

**Test Cases**:
```python
def test_extract_s3_bucket_public():
    """Test extraction of public S3 bucket."""
    code = '''
from aws_cdk import aws_s3 as s3

bucket = s3.Bucket(self, "MyBucket",
    public_read_access=True
)
    '''
    tree = ast.parse(code)
    constructs = extract_python_cdk_constructs(tree, None)

    assert len(constructs) == 1
    assert constructs[0]['cdk_class'] == 's3.Bucket'
    assert constructs[0]['construct_name'] == 'MyBucket'
    assert len(constructs[0]['properties']) == 1
    assert constructs[0]['properties'][0]['name'] == 'public_read_access'
    assert constructs[0]['properties'][0]['value_expr'] == 'True'

def test_rule_detects_public_bucket():
    """Test rule detects public S3 bucket."""
    # Setup: Create test database with CDK constructs
    # Execute: Run aws_cdk_s3_public_analyze.py
    # Assert: Finds 1 CRITICAL finding
```

### Integration Tests

**Test Fixtures**:
```
tests/fixtures/cdk_projects/
├── vulnerable_cdk/          # Sample project with known vulnerabilities
│   ├── app.py               # Entry point
│   ├── stacks/
│   │   ├── storage_stack.py # Public S3 bucket
│   │   ├── database_stack.py # Unencrypted RDS
│   │   └── network_stack.py # Open security group
│   └── expected_findings.json # Ground truth
└── secure_cdk/              # Sample project with secure config
    ├── app.py
    └── stacks/
        ├── storage_stack.py # Private bucket
        └── database_stack.py # Encrypted RDS
```

**Integration Test**:
```python
def test_end_to_end_cdk_analysis():
    """Test full pipeline on vulnerable CDK project."""
    project_dir = 'tests/fixtures/cdk_projects/vulnerable_cdk'

    # Run indexing
    subprocess.run(['aud', 'index'], cwd=project_dir)

    # Run CDK analysis
    result = subprocess.run(['aud', 'cdk', 'analyze'], cwd=project_dir, capture_output=True)

    # Load findings
    db_path = Path(project_dir) / '.pf' / 'repo_index.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cdk_findings WHERE severity = 'critical'")
    critical_count = cursor.fetchone()[0]

    # Assert expected findings
    assert critical_count >= 2  # At least public bucket + open SG
```

### Regression Tests

**Ensure No Impact on Non-CDK Projects**:
```python
def test_non_cdk_project_no_overhead():
    """Verify zero overhead on non-CDK projects."""
    project_dir = 'tests/fixtures/pure_python_project'  # No CDK imports

    # Run indexing
    start_time = time.time()
    subprocess.run(['aud', 'index'], cwd=project_dir)
    elapsed = time.time() - start_time

    # Verify CDK extractor skipped
    db_path = Path(project_dir) / '.pf' / 'repo_index.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cdk_constructs")
    assert cursor.fetchone()[0] == 0

    # Verify no performance regression (<5% overhead acceptable)
    assert elapsed < baseline_time * 1.05
```

---

## Migration Plan

### Phase 1: Schema & Extraction (Week 1)

**Tasks**:
1. Add table schemas to `schema.py`
2. Add database methods to `database.py`
3. Implement `extract_python_cdk_constructs()` in `python_impl.py`
4. Create `AWSCdkExtractor` class
5. Write unit tests for extraction

**Validation**:
- Run `aud index` on sample CDK project
- Verify `cdk_constructs` table populated
- Verify `cdk_construct_properties` table populated

### Phase 2: Rules (Week 2)

**Tasks**:
1. Create `aws_cdk_s3_public_analyze.py`
2. Create `aws_cdk_encryption_analyze.py`
3. Create `aws_cdk_sg_open_analyze.py`
4. Create `aws_cdk_iam_wildcards_analyze.py`
5. Write unit tests for each rule

**Validation**:
- Run `aud detect-patterns` on sample CDK project
- Verify findings written to `findings_consolidated`
- Verify zero false positives on secure CDK project

### Phase 3: Analyzer & CLI (Week 3)

**Tasks**:
1. Create `AWSCdkAnalyzer` orchestrator
2. Create `cdk.py` CLI command
3. Integrate into `pipelines.py`
4. Write integration tests

**Validation**:
- Run `aud full` on sample CDK project
- Verify all 4 stages execute
- Verify findings in final report

### Phase 4: Documentation & Release (Week 4)

**Tasks**:
1. Update README with CDK support
2. Write user guide (how to interpret findings)
3. Create demo video
4. Archive OpenSpec proposal

**Validation**:
- Run `openspec archive add-aws-cdk-analysis --yes`
- Verify spec created in `openspec/specs/cdk-analysis/`

---

## Open Questions

### Q1: Should we analyze CDK v1 projects?

**Context**: CDK v1 is deprecated but still widely used

**Options**:
1. Phase 1: v2 only (CURRENT)
2. Add v1 support in Phase 2
3. Separate OpenSpec proposal for v1

**Recommendation**: Start with v2, add v1 if community requests

---

### Q2: Should we detect custom construct vulnerabilities?

**Context**: Users create custom constructs that wrap AWS constructs

**Options**:
1. Phase 1: Built-in constructs only (CURRENT)
2. Add inheritance analysis (traverse base classes)
3. Allow user-defined patterns

**Recommendation**: Start with built-in, add custom support if needed

---

### Q3: Should we integrate with CDK unit tests?

**Context**: CDK projects often have snapshot tests

**Options**:
1. Analyze only source code (CURRENT)
2. Parse `cdk synth` CloudFormation output
3. Integrate with CDK Assertions

**Recommendation**: Analyze source code (avoid requiring CDK runtime)

---

## Approval Checkpoints

### Before Implementation

- [ ] Architect reviews schema design
- [ ] Lead Auditor approves detection patterns
- [ ] Team confirms no active proposal conflicts

### Before Merge

- [ ] All unit tests pass (>90% coverage)
- [ ] Integration tests pass on sample projects
- [ ] Regression tests show <5% overhead
- [ ] Documentation complete

### Before Archive

- [ ] User acceptance testing on real CDK projects
- [ ] Zero critical bugs in issue tracker
- [ ] Performance benchmarks meet targets

---

**Next Steps**: Read `tasks.md` for implementation checklist and `specs/cdk-analysis/spec.md` for requirements.
