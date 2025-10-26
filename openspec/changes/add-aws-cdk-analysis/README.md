# OpenSpec Proposal: AWS CDK Infrastructure-as-Code Security Analysis

**Change ID**: `add-aws-cdk-analysis`
**Status**: ⏸️ **AWAITING APPROVAL**
**Complexity**: High (multi-layer integration)
**Estimated Timeline**: 4 weeks
**Assigned**: Unassigned

---

## 🎯 Quick Start for AI Assistants

You are an AI assistant tasked with understanding or implementing this proposal. Follow this protocol:

### Step 1: Read in This Order (MANDATORY)

1. **`proposal.md`** (5 min read) - Understand WHY and WHAT
2. **`design.md`** (15 min read) - Understand HOW (architecture, decisions, integration)
3. **`tasks.md`** (10 min read) - Understand implementation checklist
4. **`specs/cdk-analysis/spec.md`** (10 min read) - Understand requirements and acceptance criteria

**Total reading time**: ~40 minutes (do NOT skip)

### Step 2: Context Prerequisites

Before starting ANY implementation, read:

- `/CLAUDE.md` - Project rules (NO FALLBACKS, 3-layer architecture)
- `/teamsop.md` - SOP v4.20 (Architect-Auditor-Coder workflow)
- `/aws_cdk.md` - Pre-spec research (Architect's notes)
- `openspec/AGENTS.md` - OpenSpec workflow
- `openspec/project.md` - TheAuditor architecture patterns

### Step 3: Verification Phase (FROM TEAMSOP.md)

**MANDATORY BEFORE CODING**:

Create verification report in `tasks.md` Section 0 by:

1. Reading existing code:
   - `theauditor/indexer/schema.py` - Schema contract system
   - `theauditor/indexer/database.py` - Batch write patterns
   - `theauditor/rules/orchestrator.py` - Rule discovery
   - `theauditor/rules/base.py` - StandardRuleContext/StandardFinding
   - `theauditor/rules/TEMPLATE_STANDARD_RULE.py` - Rule template
2. Confirming hypotheses:
   - ✅ Schema uses TableSchema dataclass pattern
   - ✅ Database uses 200-record batches
   - ✅ Orchestrator auto-discovers rules via `_discover_all_rules()`
   - ✅ Rules use `StandardRuleContext → List[StandardFinding]` signature
3. Checking for blockers:
   - ❌ Active proposals modifying same files (`openspec list`)
   - ❌ Conflicting schema changes

**DO NOT PROCEED WITHOUT VERIFICATION**

### Step 4: Implementation Workflow

Follow `tasks.md` sequentially:

1. **Schema Layer** → Database Layer → AST Layer → Extractor Layer
2. **Indexer Integration** → Rules Layer → CLI Layer → Analyzer Layer
3. **Pipeline Integration** → Testing → Documentation → Archive

**Mark tasks complete as you go** (update `tasks.md` checkboxes).

---

## 📋 What This Proposal Adds

### New Capability: CDK Infrastructure Security Analysis

Analyzes AWS Cloud Development Kit (Python) code for infrastructure misconfigurations:

- ✅ **Public S3 buckets** detection
- ✅ **Unencrypted storage** (RDS, EBS, DynamoDB)
- ✅ **Open security groups** (0.0.0.0/0 ingress)
- ✅ **IAM wildcard permissions** (*, AdministratorAccess)

### Integration Points

| Layer | What's Added | Files Modified |
|-------|--------------|----------------|
| Schema | 3 new tables | `schema.py` |
| Database | 3 batch write methods | `database.py` |
| AST | CDK construct extractor | `python_impl.py` |
| Extractor | New auto-discovered extractor | `aws_cdk.py` (NEW) |
| Rules | 4 security detection rules | `deployment/aws_cdk_*.py` (NEW) |
| CLI | New command group | `cdk.py` (NEW) |
| Analyzer | Rule orchestrator | `aws_cdk_analyzer.py` (NEW) |
| Pipeline | Stage 2 integration | `pipelines.py` |

---

## 🏗️ Architecture Anchoring (Critical Understanding)

This proposal **RESPECTS** existing architecture patterns:

### 1. Rules Orchestrator Integration

**HOW**: Rules auto-discovered by existing `RulesOrchestrator._discover_all_rules()`

**WHAT**: No manual registration required - drop rule files in `/rules/deployment/`

**WHY**: Maintains dynamic discovery pattern used by 100+ existing rules

### 2. 3-Layer File Path Responsibility

**LAYER 1 (Implementation)**: `python_impl.py` - Returns data with `line`, NO file_path

**LAYER 2 (Extractor)**: `aws_cdk.py` - Receives `file_info`, delegates to impl, returns NO file_path

**LAYER 3 (Orchestrator)**: `indexer/__init__.py` - Adds file_path when calling `db_manager.add_cdk_construct(file_path, ...)`

**WHY**: Single source of truth for file paths (prevents NULL file paths in database)

### 3. Schema Contract System

**PATTERN**: Define in `schema.py` → Auto-create via `CREATE TABLE IF NOT EXISTS`

**CONTRACT**: Rules assume tables exist (NO existence checks)

**FAILURE MODE**: Missing table = crash (indicates schema bug, not runtime error)

**WHY**: Zero fallback policy - bugs must be loud

### 4. Database-First Rules

**PATTERN**: Query indexed database tables, NOT file content

**FORBIDDEN**: Regex on file content, file I/O in rules

**EXAMPLE**:
```python
# ✅ CORRECT
cursor.execute("SELECT * FROM cdk_constructs WHERE cdk_class LIKE '%.Bucket'")

# ❌ FORBIDDEN
pattern = re.compile(r's3\.Bucket\(.*public_read_access=True')
matches = pattern.findall(file_content)  # CANCER
```

### 5. Pipeline 4-Stage Structure

**STAGE 1 (Sequential)**: Foundation - index, detect-frameworks

**STAGE 2 (Sequential)**: Data Prep - workset, graph, **CDK** ← NEW

**STAGE 3 (Parallel)**: Heavy Analysis - taint (Track A), patterns (Track B), network (Track C)

**STAGE 4 (Sequential)**: Aggregation - FCE, report, summary

**WHY**: CDK runs in Stage 2 (needs index complete, before heavy parallel analysis)

---

## 🚫 Absolute Prohibitions (FROM CLAUDE.md)

**IF YOU VIOLATE THESE, YOUR CODE WILL BE REJECTED**

### ❌ NO FALLBACKS

```python
# ❌❌❌ FORBIDDEN ❌❌❌
cursor.execute("SELECT * FROM cdk_constructs WHERE name = ?", (name,))
result = cursor.fetchone()
if not result:  # ← CANCER
    # Try alternative query
    cursor.execute("SELECT * FROM cdk_constructs WHERE name = ?", (alt_name,))
```

```python
# ✅ CORRECT - Single query, hard fail if wrong
cursor.execute("SELECT * FROM cdk_constructs WHERE name = ?", (name,))
result = cursor.fetchone()
if not result:
    continue  # Skip, don't try alternatives
```

### ❌ NO TABLE EXISTENCE CHECKS

```python
# ❌❌❌ FORBIDDEN ❌❌❌
if 'cdk_constructs' in existing_tables:  # ← CANCER
    cursor.execute("SELECT * FROM cdk_constructs")
```

```python
# ✅ CORRECT - Assume table exists
cursor.execute("SELECT * FROM cdk_constructs")
# If table doesn't exist, let it crash (schema bug)
```

### ❌ NO FILE_PATH IN EXTRACTOR RETURNS

```python
# ❌❌❌ FORBIDDEN ❌❌❌
return {
    'cdk_constructs': [
        {'file_path': 'app.py', 'line': 10, ...}  # ← CANCER
    ]
}
```

```python
# ✅ CORRECT - No file_path key
return {
    'cdk_constructs': [
        {'line': 10, 'cdk_class': 's3.Bucket', ...}  # ← Orchestrator adds file_path
    ]
}
```

---

## 📊 Success Metrics (Release Criteria)

### Must Achieve Before Merge

- [ ] Detects public S3 buckets (100% recall on test fixtures)
- [ ] Detects unencrypted RDS instances (100% recall)
- [ ] Detects open security groups (100% recall)
- [ ] Detects IAM wildcard permissions (100% recall)
- [ ] Zero false positives on secure CDK projects (>95% precision)
- [ ] <5 seconds overhead for 50-file CDK projects
- [ ] All unit tests pass (`pytest tests/test_cdk_*.py -v`)
- [ ] All integration tests pass (`pytest tests/test_cdk_integration.py -v`)
- [ ] Zero regression on non-CDK projects
- [ ] Documentation complete (README, user guide, CHANGELOG)
- [ ] OpenSpec validation passes (`openspec validate add-aws-cdk-analysis --strict`)

### Post-Merge Validation

- [ ] `aud full` completes on real-world CDK project
- [ ] Findings appear in `.pf/readthis/` chunks
- [ ] FCE correlates CDK findings with app code findings
- [ ] Performance benchmarks met (no >5% slowdown)

---

## 🔍 Known Limitations (Accept & Document)

### 1. CDK v1 Not Supported

**Impact**: Cannot analyze legacy CDK projects using `@aws-cdk/aws-s3` imports

**Workaround**: Upgrade to CDK v2 (v1 deprecated since June 2023)

**Future**: Separate proposal if community demand exists

### 2. Dynamic Property Values Not Evaluated

**Example**: `public_read_access=config.get_value()` cannot be analyzed

**Impact**: False negatives (some vulnerabilities missed)

**Workaround**: Use static values in CDK code, use environment variables for dynamic config

### 3. Custom Constructs Not Analyzed

**Example**: `class MyBucket(s3.Bucket)` not detected

**Impact**: False negatives for custom infrastructure

**Workaround**: Use built-in AWS constructs directly

### 4. Cross-Stack References Not Resolved

**Example**: `sg = ec2.SecurityGroup(..., vpc=stack1.vpc)` - stack1.vpc not resolved

**Impact**: False negatives for cross-stack security issues

**Workaround**: Keep security-sensitive config in single stack

---

## 🎓 Learning Resources

### For Understanding TheAuditor Architecture

- **Schema Contract System**: Read `schema.py` + comments in `database.py`
- **Rules Orchestrator**: Read `orchestrator.py` (especially `_discover_all_rules`)
- **3-Layer Pattern**: Read "3-Layer File Path Responsibility" in `CLAUDE.md`
- **Pipeline Structure**: Read `pipelines.py` docstrings

### For Understanding CDK Analysis

- **AWS CDK Docs**: https://docs.aws.amazon.com/cdk/api/v2/python/
- **Security Best Practices**: https://docs.aws.amazon.com/security/
- **Terraform Analyzer** (similar capability): `theauditor/commands/terraform.py`

### For Understanding OpenSpec

- **OpenSpec Agent Instructions**: `openspec/AGENTS.md`
- **Project Conventions**: `openspec/project.md`
- **Validation**: Run `openspec validate add-aws-cdk-analysis --strict`

---

## 📞 Stakeholder Sign-off

### Approval Required From

- [ ] **Architect (Human)** - Schema changes, breaking changes
- [ ] **Lead Auditor (Gemini)** - Rule logic, detection accuracy
- [ ] **Team** - No conflicts with active proposals

### Review Process

1. Read all 4 documents (proposal, design, tasks, spec)
2. Verify no conflicts with active work (`openspec list`)
3. Comment on design decisions in `design.md`
4. Approve or request changes

**Status**: ⏸️ Awaiting approval before implementation

---

## 🚀 Next Steps for Implementer

### If You're Starting Implementation

1. ✅ Read all 4 documents (40 min)
2. ✅ Read prerequisite docs (CLAUDE.md, teamsop.md, etc.)
3. ✅ Complete verification phase (Section 0 in tasks.md)
4. ✅ Get approval from Architect & Lead Auditor
5. ✅ Start with Schema Layer (tasks.md Section 1)
6. ✅ Mark tasks complete as you go
7. ✅ Run tests after each layer
8. ✅ Update this README with progress

### If You're Reviewing

1. Read `proposal.md` - Understand motivation
2. Read `design.md` - Evaluate technical decisions
3. Read `spec.md` - Validate requirements
4. Comment on specific design choices
5. Approve or request changes

---

## 📝 Implementation Progress Tracker

**Current Phase**: Pre-implementation (awaiting approval)

| Layer | Status | Completion | Notes |
|-------|--------|------------|-------|
| 0. Verification | ⬜ Not Started | 0% | - |
| 1. Schema | ⬜ Not Started | 0% | - |
| 2. Database | ⬜ Not Started | 0% | - |
| 3. AST Impl | ⬜ Not Started | 0% | - |
| 4. Extractor | ⬜ Not Started | 0% | - |
| 5. Indexer Integration | ⬜ Not Started | 0% | - |
| 6. Rules | ⬜ Not Started | 0% | - |
| 7. CLI | ⬜ Not Started | 0% | - |
| 8. Analyzer | ⬜ Not Started | 0% | - |
| 9. Pipeline | ⬜ Not Started | 0% | - |
| 10. Testing | ⬜ Not Started | 0% | - |
| 11. Documentation | ⬜ Not Started | 0% | - |
| 12. Archive | ⬜ Not Started | 0% | - |

**Legend**: ⬜ Not Started | 🟦 In Progress | ✅ Complete | ❌ Blocked

---

## 💬 Questions or Issues?

### If You're Stuck

1. Re-read the relevant section in `design.md`
2. Check `CLAUDE.md` for architecture patterns
3. Look at similar existing code (e.g., Terraform analyzer, SQL injection rule)
4. Ask specific questions with code context

### If You Find a Bug in the Proposal

1. Document the issue in this README
2. Propose a fix in the relevant document (proposal.md, design.md, tasks.md)
3. Get approval before changing spec.md (requirements are contract)

---

**Last Updated**: 2025-10-26
**Created By**: Opus (Lead Coder AI)
**For**: Architect (Human) + Lead Auditor (Gemini)
**Purpose**: Handoff documentation for future AI assistants

**This README serves as the entry point for ANY AI assistant working on this proposal.**
