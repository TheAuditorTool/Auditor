# Tasks: AWS CDK Infrastructure-as-Code Security Analysis

**Change ID**: `add-aws-cdk-analysis`
**Status**: Pre-implementation
**Estimated Total Time**: 4 weeks
**Complexity**: High

---

## 0. Verification (Pre-Implementation)

**MANDATORY: Complete before any implementation**

- [x] 0.1 Read and confirm understanding of `proposal.md`
- [x] 0.2 Read and confirm understanding of `design.md`
- [x] 0.3 Read and confirm understanding of `specs/cdk-analysis/spec.md`
- [x] 0.4 Read CLAUDE.md sections on:
  - [x] 3-Layer File Path Responsibility Architecture
  - [x] Schema Contract System
  - [x] Absolute Prohibitions (NO FALLBACKS)
  - [x] Database Contract Preservation
- [x] 0.5 Read `theauditor/rules/TEMPLATE_STANDARD_RULE.py`
- [x] 0.6 Read `theauditor/rules/base.py` (StandardRuleContext, StandardFinding)
- [x] 0.7 Examine existing extractor: `theauditor/indexer/extractors/terraform.py`
- [x] 0.8 Examine existing analyzer: `theauditor/terraform/analyzer.py`
- [x] 0.9 Verify no active OpenSpec proposals conflict with this work
  - [x] Run: `openspec list`
  - [x] Confirm: No proposals modifying same files (python parity is separate)
- [x] 0.10 Create verification report (verification.md completed)

**Verification Findings**:
```
VERIFICATION COMPLETED: 2025-10-30 by Opus (Lead Coder AI)
Full report: verification.md

CONFIRMED ARCHITECTURE PATTERNS:
- ✅ Schema uses TableSchema dataclass pattern (schema.py:38-60)
- ✅ Database uses generic_batches with 200-record batches (database.py:53-55)
- ✅ 3-layer file path responsibility verified (terraform.py:44-64)
- ✅ Rules auto-discovered via RulesOrchestrator._discover_all_rules() (orchestrator.py:110-150)
- ✅ StandardRuleContext contract verified (base.py:32-73)
- ✅ Zero fallback policy confirmed (CLAUDE.md)
- ✅ No conflicting active proposals (openspec list: 10 proposals, zero conflicts)
- ✅ Pipeline integration pattern verified (pipelines.py)

CRITICAL CORRECTIONS APPLIED:
- ⚠️ CORRECTED: Python AST module location
  - OLD (proposal): theauditor/ast_extractors/python_impl.py (DEPRECATED 2025-10-30)
  - NEW (verified): theauditor/ast_extractors/python/cdk_extractor.py
  - DECISION: Architect approved Option B - separate cdk_extractor.py module

- ⚠️ CORRECTED: Analyzer directory structure
  - OLD (proposal): theauditor/analyzers/aws_cdk_analyzer.py (directory doesn't exist)
  - NEW (verified): theauditor/aws_cdk/analyzer.py (follows terraform pattern)
  - PATTERN: Examined terraform/analyzer.py as reference

BLOCKERS:
- ❌ NONE - All blockers resolved, ready for Phase 1 implementation

CONFIDENCE LEVEL: HIGH
All patterns verified against live codebase. Implementation ready to proceed.
```

---

## 1. Schema Layer (`theauditor/indexer/schema.py`)

**Goal**: Define CDK table schemas in schema contract system

**Prerequisites**: Verification complete, no schema conflicts

### 1.1 Add cdk_constructs Table Schema

**File**: `theauditor/indexer/schema.py`

**Location**: After `terraform_resources` table definition (~line 800)

**Implementation**:
- [ ] 1.1.1 Create `cdk_constructs` TableSchema definition
  - [ ] Primary key: `construct_id` (TEXT)
  - [ ] Columns: `file_path` (TEXT), `line` (INTEGER), `cdk_class` (TEXT), `construct_name` (TEXT, nullable)
  - [ ] Indexes: `idx_cdk_constructs_file` (file_path), `idx_cdk_constructs_class` (cdk_class)
- [ ] 1.1.2 Add to `TABLES` registry dict
- [ ] 1.1.3 Verify schema definition matches design.md specification

**Verification**:
```python
# Test schema registration
from theauditor.indexer.schema import TABLES
assert 'cdk_constructs' in TABLES
assert TABLES['cdk_constructs'].columns[0].name == 'construct_id'
```

### 1.2 Add cdk_construct_properties Table Schema

**Implementation**:
- [ ] 1.2.1 Create `cdk_construct_properties` TableSchema definition
  - [ ] Primary key: `id` (INTEGER, autoincrement)
  - [ ] Columns: `construct_id` (TEXT), `property_name` (TEXT), `property_value_expr` (TEXT), `line` (INTEGER)
  - [ ] Indexes: `idx_cdk_props_construct` (construct_id), `idx_cdk_props_name` (property_name)
- [ ] 1.2.2 Add to `TABLES` registry dict
- [ ] 1.2.3 Add comment documenting FOREIGN KEY (construct_id → cdk_constructs.construct_id)
  - Note: Actual FK defined in database.py to avoid circular dependencies

**Verification**:
```python
assert 'cdk_construct_properties' in TABLES
assert len(TABLES['cdk_construct_properties'].indexes) == 2
```

### 1.3 Add cdk_findings Table Schema

**Implementation**:
- [ ] 1.3.1 Create `cdk_findings` TableSchema definition
  - [ ] Primary key: `finding_id` (TEXT)
  - [ ] Columns: `file_path`, `construct_id` (nullable), `category`, `severity`, `title`, `description`, `remediation`, `line`
  - [ ] Indexes: `idx_cdk_findings_severity`, `idx_cdk_findings_category`
- [ ] 1.3.2 Add to `TABLES` registry dict

**Verification**:
```bash
# Run schema contract validator
python -c "from theauditor.indexer.schema import validate_all_schemas; validate_all_schemas()"
```

---

## 2. Database Layer (`theauditor/indexer/database.py`)

**Goal**: Add batch write methods for CDK tables

**Prerequisites**: Schema layer complete

### 2.1 Add add_cdk_construct Method

**File**: `theauditor/indexer/database.py`

**Location**: After `add_terraform_resource` method (~line 1200)

**Implementation**:
- [ ] 2.1.1 Define method signature:
  ```python
  def add_cdk_construct(self, file_path: str, line: int, cdk_class: str, construct_name: str, construct_id: str) -> None:
  ```
- [ ] 2.1.2 Append tuple to `self.generic_batches['cdk_constructs']`
- [ ] 2.1.3 Follow existing pattern (see `add_terraform_resource`)

**Verification**:
```python
db_manager = DatabaseManager(':memory:')
db_manager.add_cdk_construct('test.py', 10, 's3.Bucket', 'myBucket', 'test.py::L10::s3.Bucket::myBucket')
assert len(db_manager.generic_batches['cdk_constructs']) == 1
```

### 2.2 Add add_cdk_construct_property Method

**Implementation**:
- [ ] 2.2.1 Define method signature:
  ```python
  def add_cdk_construct_property(self, construct_id: str, property_name: str, property_value_expr: str, line: int) -> None:
  ```
- [ ] 2.2.2 Append tuple to `self.generic_batches['cdk_construct_properties']`

### 2.3 Add add_cdk_finding Method

**Implementation**:
- [ ] 2.3.1 Define method signature (mirror `add_terraform_finding`)
- [ ] 2.3.2 Append tuple to `self.generic_batches['cdk_findings']`

### 2.4 Update flush_batch Method

**File**: `theauditor/indexer/database.py`

**Location**: `flush_batch` method (~line 500)

**Implementation**:
- [ ] 2.4.1 Add `'cdk_constructs'` to `flush_order` list
- [ ] 2.4.2 Add `'cdk_construct_properties'` to `flush_order` (AFTER cdk_constructs)
- [ ] 2.4.3 Add `'cdk_findings'` to `flush_order`
- [ ] 2.4.4 Ensure flush mode is `'INSERT'` for all three tables

**Verification**:
```python
# Test batch flush
db_manager = DatabaseManager(':memory:')
db_manager.add_cdk_construct('test.py', 10, 's3.Bucket', 'myBucket', 'test.py::L10')
db_manager.flush_batch()
# Query database to verify record written
```

---

## 3. AST Implementation Layer (`theauditor/ast_extractors/python_impl.py`)

**Goal**: Extract CDK construct calls from Python AST

**Prerequisites**: Schema and database layers complete

### 3.1 Implement extract_python_cdk_constructs Function

**File**: `theauditor/ast_extractors/python_impl.py`

**Location**: After `extract_python_orm_calls` function (~line 800)

**Implementation**:
- [ ] 3.1.1 Define function signature:
  ```python
  def extract_python_cdk_constructs(tree: Dict, parser_self) -> List[Dict]:
  ```
- [ ] 3.1.2 Extract `actual_tree` from tree dict (handle both dict and Module object)
- [ ] 3.1.3 Walk AST using `ast.walk(actual_tree)`
- [ ] 3.1.4 Filter for `ast.Call` nodes
- [ ] 3.1.5 For each Call node:
  - [ ] Resolve function name using `get_node_name(node.func)` or similar
  - [ ] Check if name matches CDK patterns (contains 's3.', 'rds.', 'ec2.', 'iam.', 'aws_cdk.')
  - [ ] Extract `construct_name` from `node.args[1]` if string literal
  - [ ] Extract `line = node.lineno`
  - [ ] Extract properties by iterating `node.keywords`
    - [ ] For each keyword: `property_name = keyword.arg`
    - [ ] Use `ast.unparse(keyword.value)` for `property_value_expr`
    - [ ] Use `keyword.lineno` for property line number
  - [ ] Yield/return dict: `{'line': ..., 'cdk_class': ..., 'construct_name': ..., 'properties': [...]}`
- [ ] 3.1.6 Return list of construct dicts

**Example Return Value**:
```python
[
    {
        'line': 42,
        'cdk_class': 's3.Bucket',
        'construct_name': 'myBucket',
        'properties': [
            {'name': 'public_read_access', 'value_expr': 'True', 'line': 43},
            {'name': 'encryption', 'value_expr': 's3.BucketEncryption.UNENCRYPTED', 'line': 44}
        ]
    }
]
```

**Critical**: NO `file` or `file_path` keys in return dict (3-layer responsibility)

**Verification**:
```python
import ast
from theauditor.ast_extractors.python_impl import extract_python_cdk_constructs

code = '''
from aws_cdk import aws_s3 as s3
bucket = s3.Bucket(self, "MyBucket", public_read_access=True)
'''
tree = ast.parse(code)
constructs = extract_python_cdk_constructs({'type': 'python_ast', 'tree': tree}, None)
assert len(constructs) == 1
assert constructs[0]['cdk_class'] == 's3.Bucket'
assert constructs[0]['construct_name'] == 'MyBucket'
assert constructs[0]['properties'][0]['name'] == 'public_read_access'
assert constructs[0]['properties'][0]['value_expr'] == 'True'
```

---

## 4. Extractor Layer (`theauditor/indexer/extractors/aws_cdk.py`)

**Goal**: Create auto-discovered extractor for CDK files

**Prerequisites**: AST implementation complete

### 4.1 Create AWSCdkExtractor Class

**File**: `theauditor/indexer/extractors/aws_cdk.py` (NEW FILE)

**Implementation**:
- [ ] 4.1.1 Import dependencies:
  ```python
  from theauditor.indexer.extractors import BaseExtractor, register_extractor
  from typing import Dict, Any, List, Optional
  from pathlib import Path
  ```
- [ ] 4.1.2 Define class with `@register_extractor` decorator
- [ ] 4.1.3 Implement `supported_extensions` property:
  ```python
  @property
  def supported_extensions(self) -> List[str]:
      return ['.py']
  ```
- [ ] 4.1.4 Implement `should_extract` method:
  - [ ] Query imports table to check for `aws_cdk` import
  - [ ] Return True if CDK import found, False otherwise
  - [ ] **CRITICAL**: This method MUST check database, not file content
- [ ] 4.1.5 Implement `extract` method:
  - [ ] Verify tree type is `python_ast`
  - [ ] Call `self.ast_parser.extract_cdk_constructs(tree)` (facade method)
  - [ ] Generate `construct_id` for each construct
  - [ ] Build `cdk_constructs` list (NO file_path keys)
  - [ ] Build `cdk_construct_properties` list (NO file_path keys)
  - [ ] Return dict: `{'cdk_constructs': [...], 'cdk_construct_properties': [...]}`

**Template**:
```python
@register_extractor
class AWSCdkExtractor(BaseExtractor):
    @property
    def supported_extensions(self) -> List[str]:
        return ['.py']

    def should_extract(self, file_path: str) -> bool:
        # Query imports table (requires db_path access via self.ast_parser)
        # Return True if 'aws_cdk' in imports
        pass

    def extract(self, file_info: Dict[str, Any], content: str, tree: Optional[Any] = None) -> Dict[str, Any]:
        if not tree or tree.get("type") != "python_ast":
            return {}

        # Call implementation
        cdk_calls = self.ast_parser.extract_cdk_constructs(tree)

        extracted_constructs = []
        extracted_properties = []

        for call in cdk_calls:
            # Generate construct_id
            construct_id = f"{file_info['path']}::L{call['line']}::{call['cdk_class']}::{call['construct_name']}"

            extracted_constructs.append({
                'construct_id': construct_id,
                'line': call['line'],
                'cdk_class': call['cdk_class'],
                'construct_name': call['construct_name']
                # NO file_path key - added by orchestrator
            })

            for prop in call['properties']:
                extracted_properties.append({
                    'construct_id': construct_id,
                    'property_name': prop['name'],
                    'property_value_expr': prop['value_expr'],
                    'line': prop['line']
                })

        return {
            'cdk_constructs': extracted_constructs,
            'cdk_construct_properties': extracted_properties
        }
```

**Verification**:
```python
# Test auto-discovery
from theauditor.indexer.extractors import get_all_extractors
extractors = get_all_extractors()
assert 'AWSCdkExtractor' in [e.__class__.__name__ for e in extractors]
```

### 4.2 Add Facade Method to ASTParser

**File**: `theauditor/indexer/ast_parser.py`

**Location**: After `extract_orm_calls` method

**Implementation**:
- [ ] 4.2.1 Add method:
  ```python
  def extract_cdk_constructs(self, tree: Dict) -> List[Dict]:
      """Extract AWS CDK constructs from Python AST."""
      if tree.get("type") == "python_ast":
          from theauditor.ast_extractors.python_impl import extract_python_cdk_constructs
          return extract_python_cdk_constructs(tree, self)
      return []
  ```

---

## 5. Indexer Integration (`theauditor/indexer/__init__.py`)

**Goal**: Store extracted CDK data in database

**Prerequisites**: Extractor layer complete

### 5.1 Update _store_extracted_data Method

**File**: `theauditor/indexer/__init__.py`

**Location**: `_store_extracted_data` method (~line 600)

**Implementation**:
- [ ] 5.1.1 Add CDK constructs storage block (after `terraform_resources` block):
  ```python
  # Store CDK constructs
  if 'cdk_constructs' in extracted:
      for construct in extracted['cdk_constructs']:
          self.db_manager.add_cdk_construct(
              file_path,  # ← Orchestrator provides this
              construct['line'],
              construct['cdk_class'],
              construct['construct_name'],
              construct['construct_id']
          )
          self.counts['cdk_constructs'] = self.counts.get('cdk_constructs', 0) + 1
  ```
- [ ] 5.1.2 Add CDK properties storage block:
  ```python
  # Store CDK construct properties
  if 'cdk_construct_properties' in extracted:
      for prop in extracted['cdk_construct_properties']:
          self.db_manager.add_cdk_construct_property(
              prop['construct_id'],
              prop['property_name'],
              prop['property_value_expr'],
              prop['line']
          )
          self.counts['cdk_properties'] = self.counts.get('cdk_properties', 0) + 1
  ```

**Verification**:
```bash
# Run indexer on sample CDK project
aud index --target tests/fixtures/cdk_projects/vulnerable_cdk

# Query database
python -c "
import sqlite3
conn = sqlite3.connect('tests/fixtures/cdk_projects/vulnerable_cdk/.pf/repo_index.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM cdk_constructs')
print(f'Constructs: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM cdk_construct_properties')
print(f'Properties: {cursor.fetchone()[0]}')
"
```

---

## 6. Rules Layer (`theauditor/rules/deployment/`)

**Goal**: Implement CDK security detection rules

**Prerequisites**: Indexer integration complete

### 6.1 Create aws_cdk_s3_public_analyze.py

**File**: `theauditor/rules/deployment/aws_cdk_s3_public_analyze.py` (NEW FILE)

**Implementation**:
- [ ] 6.1.1 Copy template from `TEMPLATE_STANDARD_RULE.py`
- [ ] 6.1.2 Define METADATA:
  ```python
  METADATA = RuleMetadata(
      name="aws_cdk_s3_public",
      category="deployment",
      target_extensions=['.py'],
      exclude_patterns=['test/', 'migrations/'],
      execution_scope='database'
  )
  ```
- [ ] 6.1.3 Implement `analyze(context: StandardRuleContext)` function:
  - [ ] Query `cdk_constructs` for S3 buckets
  - [ ] JOIN with `cdk_construct_properties` to check `public_read_access`
  - [ ] Return `StandardFinding` objects for violations
- [ ] 6.1.4 Test on sample CDK project with public bucket

**Detection Logic**:
```python
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    findings = []
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.file_path, c.line, c.construct_name
        FROM cdk_constructs c
        JOIN cdk_construct_properties p ON c.construct_id = p.construct_id
        WHERE c.cdk_class LIKE '%.Bucket'
          AND p.property_name = 'public_read_access'
          AND p.property_value_expr = 'True'
    """)

    for file_path, line, construct_name in cursor.fetchall():
        findings.append(StandardFinding(
            file_path=file_path,
            line=line,
            rule_name='aws-cdk-s3-public',
            message=f'S3 bucket "{construct_name}" has public read access enabled',
            severity=Severity.CRITICAL,
            category='deployment',
            cwe_id='CWE-732'
        ))

    conn.close()
    return findings
```

**Verification**:
```bash
# Test rule directly
python -c "
from theauditor.rules.deployment.aws_cdk_s3_public_analyze import analyze
from theauditor.rules.base import StandardRuleContext
from pathlib import Path

ctx = StandardRuleContext(
    file_path=Path('test.py'),
    content='',
    language='python',
    project_path=Path('.'),
    db_path='tests/fixtures/cdk_projects/vulnerable_cdk/.pf/repo_index.db'
)
findings = analyze(ctx)
print(f'Found {len(findings)} public buckets')
"
```

### 6.2 Create aws_cdk_encryption_analyze.py

**Implementation**:
- [ ] 6.2.1 Copy template
- [ ] 6.2.2 Define METADATA (same as 6.1.2)
- [ ] 6.2.3 Implement detection for:
  - [ ] Unencrypted RDS instances (`rds.DatabaseInstance` without `storage_encrypted`)
  - [ ] Unencrypted EBS volumes (`ec2.Volume` without `encrypted`)
  - [ ] Unencrypted DynamoDB tables (`dynamodb.Table` without `encryption`)
- [ ] 6.2.4 Return HIGH severity findings

**Detection Pattern**:
```sql
-- Find RDS instances without encryption
SELECT c.file_path, c.line, c.construct_name
FROM cdk_constructs c
WHERE c.cdk_class LIKE '%.DatabaseInstance'
  AND c.construct_id NOT IN (
    SELECT construct_id FROM cdk_construct_properties
    WHERE property_name = 'storage_encrypted'
      AND property_value_expr = 'True'
  )
```

### 6.3 Create aws_cdk_sg_open_analyze.py

**Implementation**:
- [ ] 6.3.1 Copy template
- [ ] 6.3.2 Define METADATA
- [ ] 6.3.3 Implement detection for security groups with `0.0.0.0/0` ingress
- [ ] 6.3.4 Check for:
  - [ ] `ingress_rules` with `peer` containing `0.0.0.0/0`
  - [ ] `allow_all_outbound = True`
- [ ] 6.3.5 Return CRITICAL severity findings

### 6.4 Create aws_cdk_iam_wildcards_analyze.py

**Implementation**:
- [ ] 6.4.1 Copy template
- [ ] 6.4.2 Define METADATA
- [ ] 6.4.3 Implement detection for IAM policies with wildcard actions
- [ ] 6.4.4 Check for:
  - [ ] `actions` containing `'*'`
  - [ ] `resources` containing `'*'`
- [ ] 6.4.5 Return HIGH severity findings

---

## 7. CLI Layer (`theauditor/commands/cdk.py`)

**Goal**: Create CLI command for CDK analysis

**Prerequisites**: Rules layer complete

### 7.1 Create cdk.py Command Module

**File**: `theauditor/commands/cdk.py` (NEW FILE)

**Implementation**:
- [ ] 7.1.1 Import dependencies:
  ```python
  import click
  from pathlib import Path
  from theauditor.utils.decorators import handle_exceptions
  from theauditor.utils.logger import setup_logger
  ```
- [ ] 7.1.2 Define command group:
  ```python
  @click.group()
  def cdk():
      """AWS CDK infrastructure security analysis."""
      pass
  ```
- [ ] 7.1.3 Define `analyze` subcommand:
  ```python
  @cdk.command()
  @click.option('--category', help='Analyze specific category only')
  @handle_exceptions
  def analyze(category):
      """Run CDK security analyzers."""
      # Implementation
  ```
- [ ] 7.1.4 Implement analyzer instantiation and execution
- [ ] 7.1.5 Return exit code based on severity (0=clean, 1=findings, 2=critical)

**Template**:
```python
@cdk.command()
@handle_exceptions
def analyze(category):
    """Run CDK security analyzers."""
    from theauditor.analyzers.aws_cdk_analyzer import AWSCdkAnalyzer

    db_path = Path('.pf/repo_index.db')
    if not db_path.exists():
        click.echo('[ERROR] Database not found. Run `aud index` first.')
        return 1

    analyzer = AWSCdkAnalyzer(str(db_path))
    findings = analyzer.analyze(category=category)

    click.echo(f'[CDK] Found {len(findings)} issues')

    # Determine exit code
    severities = [f.severity for f in findings]
    if 'critical' in severities:
        return 2
    elif findings:
        return 1
    return 0
```

### 7.2 Register Command in CLI

**File**: `theauditor/cli.py`

**Location**: After `terraform` command registration

**Implementation**:
- [ ] 7.2.1 Import command:
  ```python
  from theauditor.commands.cdk import cdk
  ```
- [ ] 7.2.2 Register command:
  ```python
  cli.add_command(cdk)
  ```

**Verification**:
```bash
# Test command registration
aud cdk --help
aud cdk analyze --help
```

---

## 8. Analyzer Layer (`theauditor/analyzers/aws_cdk_analyzer.py`)

**Goal**: Orchestrate CDK rule execution and findings consolidation

**Prerequisites**: CLI layer complete

### 8.1 Create AWSCdkAnalyzer Class

**File**: `theauditor/analyzers/aws_cdk_analyzer.py` (NEW FILE)

**Implementation**:
- [ ] 8.1.1 Define class:
  ```python
  class AWSCdkAnalyzer:
      def __init__(self, db_path: str):
          self.db_path = db_path
  ```
- [ ] 8.1.2 Implement `analyze` method:
  - [ ] Connect to database
  - [ ] Call check methods: `_check_public_s3()`, `_check_unencrypted()`, etc.
  - [ ] Aggregate findings
  - [ ] Call `_write_findings()`
  - [ ] Return findings list
- [ ] 8.1.3 Implement check methods (delegate to rules)
- [ ] 8.1.4 Implement `_write_findings` method:
  - [ ] Delete existing CDK findings
  - [ ] Write to `cdk_findings` table
  - [ ] Write to `findings_consolidated` table (tool='cdk')

**Template**:
```python
class AWSCdkAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def analyze(self, category: str = None) -> List[StandardFinding]:
        """Run all CDK security checks."""
        from theauditor.rules.orchestrator import RulesOrchestrator

        orchestrator = RulesOrchestrator(project_path=Path('.'), db_path=self.db_path)
        findings = orchestrator.run_database_rules()

        # Filter for CDK rules only
        cdk_findings = [f for f in findings if 'cdk' in f.get('rule', '')]

        # Write to database
        self._write_findings(cdk_findings)

        return cdk_findings

    def _write_findings(self, findings: List[Dict]):
        """Write findings to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Clear existing CDK findings
        cursor.execute("DELETE FROM cdk_findings")
        cursor.execute("DELETE FROM findings_consolidated WHERE tool = 'cdk'")

        # Write findings
        for finding in findings:
            # Insert into cdk_findings
            # Insert into findings_consolidated

        conn.commit()
        conn.close()
```

---

## 9. Pipeline Integration (`theauditor/pipelines.py`)

**Goal**: Add CDK analysis to Stage 2 pipeline

**Prerequisites**: Analyzer layer complete

### 9.1 Add CDK Command to Pipeline

**File**: `theauditor/pipelines.py`

**Location**: `command_order` list (~line 420)

**Implementation**:
- [ ] 9.1.1 Add to `command_order` after `terraform provision`:
  ```python
  ("cdk", ["analyze"]),
  ```
- [ ] 9.1.2 Add description generation in command loop:
  ```python
  elif cmd_name == "cdk" and "analyze" in extra_args:
      description = f"{phase_num}. Analyze AWS CDK security"
  ```

**Verification**:
```bash
# Test pipeline integration
aud full --offline

# Verify CDK analysis runs in Stage 2
# Check .pf/pipeline.log for "Analyze AWS CDK security"
```

---

## 10. Testing

**Goal**: Comprehensive test coverage

**Prerequisites**: All implementation complete

### 10.1 Create Test Fixtures

**Directory**: `tests/fixtures/cdk_projects/`

**Implementation**:
- [ ] 10.1.1 Create `vulnerable_cdk/` project:
  - [ ] `app.py` - CDK app entry point
  - [ ] `stacks/storage_stack.py` - Public S3 bucket
  - [ ] `stacks/database_stack.py` - Unencrypted RDS
  - [ ] `stacks/network_stack.py` - Open security group
  - [ ] `expected_findings.json` - Ground truth
- [ ] 10.1.2 Create `secure_cdk/` project:
  - [ ] `app.py` - CDK app entry point
  - [ ] `stacks/storage_stack.py` - Private bucket
  - [ ] `stacks/database_stack.py` - Encrypted RDS
  - [ ] Expected: Zero findings

### 10.2 Write Unit Tests

**File**: `tests/test_cdk_extractor.py` (NEW FILE)

**Implementation**:
- [ ] 10.2.1 Test `extract_python_cdk_constructs`:
  - [ ] Test S3 bucket extraction
  - [ ] Test RDS instance extraction
  - [ ] Test property extraction
  - [ ] Test nested properties
  - [ ] Test multiple constructs
- [ ] 10.2.2 Test `AWSCdkExtractor`:
  - [ ] Test `should_extract` (CDK import detection)
  - [ ] Test `extract` (full extraction flow)
  - [ ] Test construct_id generation
- [ ] 10.2.3 Run: `pytest tests/test_cdk_extractor.py -v`

### 10.3 Write Rule Tests

**File**: `tests/test_cdk_rules.py` (NEW FILE)

**Implementation**:
- [ ] 10.3.1 Test `aws_cdk_s3_public_analyze`:
  - [ ] Test detects public bucket
  - [ ] Test ignores private bucket
  - [ ] Test handles missing property
- [ ] 10.3.2 Test `aws_cdk_encryption_analyze`:
  - [ ] Test detects unencrypted RDS
  - [ ] Test ignores encrypted RDS
- [ ] 10.3.3 Test `aws_cdk_sg_open_analyze`:
  - [ ] Test detects 0.0.0.0/0 ingress
- [ ] 10.3.4 Test `aws_cdk_iam_wildcards_analyze`:
  - [ ] Test detects wildcard permissions
- [ ] 10.3.5 Run: `pytest tests/test_cdk_rules.py -v`

### 10.4 Write Integration Tests

**File**: `tests/test_cdk_integration.py` (NEW FILE)

**Implementation**:
- [ ] 10.4.1 Test end-to-end pipeline:
  ```python
  def test_cdk_pipeline_vulnerable_project():
      project_dir = 'tests/fixtures/cdk_projects/vulnerable_cdk'
      subprocess.run(['aud', 'index'], cwd=project_dir)
      subprocess.run(['aud', 'cdk', 'analyze'], cwd=project_dir)

      db_path = Path(project_dir) / '.pf' / 'repo_index.db'
      conn = sqlite3.connect(db_path)
      cursor = conn.cursor()
      cursor.execute("SELECT COUNT(*) FROM cdk_findings WHERE severity = 'critical'")
      assert cursor.fetchone()[0] >= 2
  ```
- [ ] 10.4.2 Test backward compatibility (non-CDK project):
  ```python
  def test_non_cdk_project_zero_overhead():
      project_dir = 'tests/fixtures/pure_python_project'
      subprocess.run(['aud', 'index'], cwd=project_dir)

      db_path = Path(project_dir) / '.pf' / 'repo_index.db'
      conn = sqlite3.connect(db_path)
      cursor = conn.cursor()
      cursor.execute("SELECT COUNT(*) FROM cdk_constructs")
      assert cursor.fetchone()[0] == 0
  ```
- [ ] 10.4.3 Run: `pytest tests/test_cdk_integration.py -v`

### 10.5 Performance Testing

**Implementation**:
- [ ] 10.5.1 Benchmark indexing overhead:
  - [ ] Measure baseline: `aud index` on 100-file Python project
  - [ ] Add CDK imports to 50 files
  - [ ] Measure new time
  - [ ] Assert: <5% overhead
- [ ] 10.5.2 Benchmark analysis time:
  - [ ] Run `aud cdk analyze` on 50-file CDK project
  - [ ] Assert: <5 seconds

---

## 11. Documentation

**Goal**: Complete user and developer documentation

**Prerequisites**: Testing complete

### 11.1 Update README.md

**File**: `README.md`

**Implementation**:
- [ ] 11.1.1 Add CDK support to features list
- [ ] 11.1.2 Add CDK example to quickstart
- [ ] 11.1.3 Add CDK commands to CLI reference

### 11.2 Create User Guide

**File**: `docs/cdk_analysis.md` (NEW FILE)

**Implementation**:
- [ ] 11.2.1 Write "What is CDK Analysis?" section
- [ ] 11.2.2 Write "Supported Checks" section (list all 4 rules)
- [ ] 11.2.3 Write "How to Interpret Findings" section
- [ ] 11.2.4 Write "False Positives" section
- [ ] 11.2.5 Write "Limitations" section
- [ ] 11.2.6 Add code examples

### 11.3 Update CHANGELOG.md

**File**: `CHANGELOG.md`

**Implementation**:
- [ ] 11.3.1 Add entry for new CDK analysis capability
- [ ] 11.3.2 List all 4 detection rules
- [ ] 11.3.3 Document breaking changes (new database tables)

---

## 12. Archive OpenSpec Proposal

**Goal**: Move proposal to specs/

**Prerequisites**: All testing and documentation complete

### 12.1 Validate Proposal

**Implementation**:
- [ ] 12.1.1 Run: `openspec validate add-aws-cdk-analysis --strict`
- [ ] 12.1.2 Fix any validation errors

### 12.2 Create Spec from Deltas

**File**: `openspec/specs/cdk-analysis/spec.md`

**Implementation**:
- [ ] 12.2.1 Copy `specs/cdk-analysis/spec.md` from proposal deltas
- [ ] 12.2.2 Verify all requirements present
- [ ] 12.2.3 Verify all scenarios present

### 12.3 Archive Proposal

**Implementation**:
- [ ] 12.3.1 Run: `openspec archive add-aws-cdk-analysis --yes`
- [ ] 12.3.2 Verify proposal moved to `changes/archive/`
- [ ] 12.3.3 Verify spec created in `specs/cdk-analysis/`

---

## 13. Post-Implementation Verification

**Goal**: Final validation before release

**Prerequisites**: Archive complete

### 13.1 Full Pipeline Test

**Implementation**:
- [ ] 13.1.1 Run `aud full` on vulnerable CDK project
- [ ] 13.1.2 Verify all 4 CDK findings detected
- [ ] 13.1.3 Verify findings in `.pf/readthis/` chunks
- [ ] 13.1.4 Verify findings in final report

### 13.2 Backward Compatibility Test

**Implementation**:
- [ ] 13.2.1 Run `aud full` on pure Python project (no CDK)
- [ ] 13.2.2 Verify zero CDK findings
- [ ] 13.2.3 Verify no performance regression

### 13.3 Rule Accuracy Test

**Implementation**:
- [ ] 13.3.1 Calculate precision/recall on test fixtures
- [ ] 13.3.2 Assert: Precision >95% (no false positives)
- [ ] 13.3.3 Assert: Recall >90% (catch most issues)

---

## Completion Checklist

### Before Declaring Complete

- [ ] All tasks marked complete
- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Code formatted (`ruff format theauditor`)
- [ ] Linting clean (`ruff check theauditor`)
- [ ] Documentation complete
- [ ] OpenSpec proposal archived
- [ ] Performance benchmarks met
- [ ] Architect approval obtained
- [ ] Lead Auditor approval obtained

### Success Metrics

- [ ] Detects public S3 buckets (CRITICAL severity)
- [ ] Detects unencrypted RDS (HIGH severity)
- [ ] Detects open security groups (CRITICAL severity)
- [ ] Detects IAM wildcards (HIGH severity)
- [ ] Integrated into `aud full` pipeline
- [ ] Zero impact on non-CDK projects
- [ ] <5 seconds overhead for 50-file CDK projects
- [ ] >95% precision, >90% recall on test fixtures

---

**Next Steps**: Read `specs/cdk-analysis/spec.md` for detailed requirements and acceptance criteria.
