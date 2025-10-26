# Proposal: AWS CDK Infrastructure-as-Code Security Analysis

**Change ID**: `add-aws-cdk-analysis`
**Category**: New Capability
**Complexity**: High (multi-layer integration)
**Estimated LOC**: ~2,500 (schema, extractor, impl, analyzer, rules)
**Dependencies**: Existing indexer, orchestrator, pipeline, rules infrastructure

---

## Why

TheAuditor currently analyzes application code (Python, JavaScript/TypeScript) for security vulnerabilities but lacks visibility into **infrastructure-as-code** defined using AWS CDK (Cloud Development Kit). Infrastructure misconfigurations are a leading cause of cloud security breaches:

- **Public S3 buckets** with sensitive data
- **Unencrypted databases** (RDS, DynamoDB)
- **Overly permissive IAM policies** (wildcards, admin access)
- **Open security groups** (0.0.0.0/0 ingress rules)
- **Missing encryption** at rest and in transit

AWS CDK Python code defines cloud resources programmatically, but traditional SAST tools treat it as "just Python code" without understanding the **infrastructure semantics**. This proposal adds CDK-aware analysis to detect infrastructure security issues **before deployment**, integrated seamlessly into TheAuditor's existing pipeline.

**Business Value**:
- **Shift-left security**: Catch infrastructure issues in code review, not production
- **Complete coverage**: Analyze both application logic AND infrastructure in a single scan
- **Developer-friendly**: Findings reference CDK code lines, not CloudFormation templates
- **Zero deployment overhead**: Analysis runs offline using AST parsing, no AWS credentials required

---

## What Changes

This proposal adds a **complete end-to-end AWS CDK analysis capability** following TheAuditor's established architecture patterns:

### 1. Schema Layer (`theauditor/indexer/schema.py`)

**ADDED Tables**:
- `cdk_constructs` - CDK construct instantiations (e.g., `s3.Bucket`, `rds.DatabaseInstance`)
- `cdk_construct_properties` - Properties passed to constructs (e.g., `public_read_access=True`)
- `cdk_findings` - CDK-specific security findings

Columns follow existing conventions (file, line, construct_id as composite key).

### 2. Database Layer (`theauditor/indexer/database.py`)

**ADDED Methods**:
- `add_cdk_construct(file_path, line, cdk_class, construct_name, construct_id)`
- `add_cdk_construct_property(construct_id, property_name, property_value_expr, line)`
- `add_cdk_finding(finding_id, file_path, construct_id, category, severity, ...)`

Batch insertion with 200-record batches (matches existing pattern).

### 3. AST Implementation Layer (`theauditor/ast_extractors/python_impl.py`)

**ADDED Function**:
- `extract_python_cdk_constructs(tree: Dict, parser_self)` - Walks Python AST to identify CDK construct calls and extract keyword arguments

Uses `ast.unparse()` for property values (no string manipulation).

### 4. Extractor Layer (`theauditor/indexer/extractors/aws_cdk.py`)

**NEW Extractor**:
- `AWSCdkExtractor(BaseExtractor)` - Auto-discovered via `@register_extractor`
- Filters files by import detection (`import aws_cdk`)
- Generates `construct_id` as composite key: `{file}::L{line}::{cdk_class}::{construct_name}`

Follows 3-layer file path responsibility (NO file_path in return dict).

### 5. Rules Layer (`theauditor/rules/deployment/aws_cdk_*.py`)

**NEW Rules** (follows TEMPLATE_STANDARD_RULE.py):
- `aws_cdk_s3_public_analyze.py` - Public S3 bucket detection
- `aws_cdk_encryption_analyze.py` - Missing encryption (RDS, EBS, DynamoDB)
- `aws_cdk_sg_open_analyze.py` - Open security groups (0.0.0.0/0)
- `aws_cdk_iam_wildcards_analyze.py` - IAM wildcard permissions

Each rule:
- Uses `StandardRuleContext` and `StandardFinding` (Phase 1 contracts)
- Declares `RuleMetadata` with `target_extensions=['.py']`, `target_file_patterns=['cdk.out/', 'infrastructure/']`
- Queries `cdk_constructs` and `cdk_construct_properties` tables (NO FALLBACKS)
- Returns database-first findings (no file I/O, no regex)

Auto-discovered by `RulesOrchestrator` via `_discover_all_rules()`.

### 6. Pipeline Integration (`theauditor/pipelines.py`)

**MODIFIED**: Stage 2 (Data Preparation) - Add command:
- `cdk-analyze` - Runs CDK security analyzers after indexing

Command registered in `command_order` list, executed sequentially with other Stage 2 tasks.

### 7. CLI Layer (`theauditor/commands/cdk.py`)

**NEW Command Group**:
```bash
aud cdk analyze [--category <category>]
```

Entry point that:
1. Instantiates `AWSCdkAnalyzer`
2. Calls analyzer methods
3. Writes findings to `cdk_findings` + `findings_consolidated`
4. Returns exit code based on severity (0=clean, 1=findings, 2=critical)

---

## Impact

### Affected Specs
- **NEW**: `specs/cdk-analysis/spec.md` - Complete CDK analysis capability

### Affected Code
- `theauditor/indexer/schema.py` - Add 3 tables
- `theauditor/indexer/database.py` - Add 3 methods
- `theauditor/ast_extractors/python_impl.py` - Add extraction function
- `theauditor/indexer/extractors/aws_cdk.py` - **NEW** extractor (100 LOC)
- `theauditor/rules/deployment/aws_cdk_*.py` - **NEW** 4 rule files (~400 LOC each)
- `theauditor/analyzers/aws_cdk_analyzer.py` - **NEW** analyzer orchestrator (300 LOC)
- `theauditor/commands/cdk.py` - **NEW** CLI command (150 LOC)
- `theauditor/pipelines.py` - Add 1 command to Stage 2
- `theauditor/cli.py` - Register `cdk` command group

### Database Schema Changes
**BREAKING**: Adds 3 new tables to `repo_index.db`

**Migration Strategy**:
- Schema contract system auto-creates tables on first run
- Existing databases receive new tables via `CREATE TABLE IF NOT EXISTS`
- NO data migration required (new capability, not schema change)

### Backward Compatibility
**FULLY COMPATIBLE**:
- New tables only populated when CDK files detected
- Rules only run if CDK constructs found in database
- Zero impact on non-CDK projects
- Graceful degradation if `cdk_constructs` table empty

### Performance Impact
**Minimal**:
- Extractor runs ONLY on files with `import aws_cdk` (pre-filtered by import table)
- Rules query indexed tables (no file I/O)
- Estimated overhead: +2-5 seconds for 50-file CDK project

### Testing Requirements
**MUST TEST**:
1. End-to-end pipeline on sample CDK project (included in proposal)
2. Rule precision/recall on known-vulnerable CDK patterns
3. Backward compatibility on non-CDK projects
4. Performance regression on large monorepos

---

## Risks & Mitigations

### Risk 1: CDK Version Compatibility
**Risk**: AWS CDK API changes between v1 and v2
**Mitigation**:
- Phase 1 targets CDK v2 (current stable)
- Version detection via `import aws_cdk` vs `import @aws-cdk/...`
- Future OpenSpec proposal for CDK v1 if needed

### Risk 2: Complex Property Analysis
**Risk**: CDK properties use complex Python expressions (`ec2.Peer.any_ipv4()`)
**Mitigation**:
- Use `ast.unparse()` to serialize property values as strings
- Pattern matching on known dangerous patterns (0.0.0.0/0, *, etc.)
- Accept false negatives for highly dynamic patterns (documented limitation)

### Risk 3: Rule Maintenance Burden
**Risk**: AWS adds new constructs/properties frequently
**Mitigation**:
- Modular rule architecture (one file per construct type)
- Database-first design makes adding patterns trivial (SQL INSERT)
- Community contribution path via GitHub issues

---

## Success Criteria

### Must Have (Phase 1)
- ✅ Detect public S3 buckets
- ✅ Detect unencrypted RDS instances
- ✅ Detect open security groups (0.0.0.0/0)
- ✅ Detect IAM wildcard permissions
- ✅ Integrate into `aud full` pipeline
- ✅ Write findings to `findings_consolidated`

### Nice to Have (Phase 2+)
- Terraform/Pulumi support (separate proposal)
- Cross-stack resource references
- CDK construct inheritance analysis
- Custom construct pattern library

---

## References

- **AWS CDK API Documentation**: https://docs.aws.amazon.com/cdk/api/v2/
- **AWS Security Best Practices**: https://docs.aws.amazon.com/security/
- **Pre-implementation Research**: `/aws_cdk.md` (Architect's notes)
- **Architecture Templates**: `/theauditor/rules/TEMPLATE_STANDARD_RULE.py`
- **Similar Capability**: Terraform analysis (`theauditor/commands/terraform.py`)

---

## Approval Checklist

Before implementation:
- [ ] Architect approves schema changes
- [ ] Lead Auditor reviews rule logic
- [ ] Team confirms no conflicts with active proposals (`openspec list`)
- [ ] Test fixtures prepared (sample CDK project with vulnerabilities)

**Status**: ⏸️ **AWAITING APPROVAL**

**Next Step**: Read `design.md` and `tasks.md` for technical implementation details.
