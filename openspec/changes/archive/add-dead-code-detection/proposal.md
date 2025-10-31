# Proposal: Dead Code Detection & Isolation Analysis

**Change ID**: `add-dead-code-detection`
**Status**: PROPOSED
**Priority**: HIGH
**Team Protocol**: SOP v4.20 (Architect-Auditor-Coder Workflow)

---

## Team Structure & Roles

### The Architect (Human)
- **Role**: Project Manager, strategic authority, final approval
- **Responsibilities**:
  - Review and approve this proposal
  - Define business requirements and priorities
  - Validate that implementation matches strategic vision
  - Accept/reject deliverables

### The Lead Auditor (Gemini AI)
- **Role**: Technical strategist, quality control lead
- **Responsibilities**:
  - Review implementation reports from Coder
  - Validate completeness against SOP v4.20 Template C-4.20
  - Verify root cause analysis and edge case coverage
  - Approve progression to next phase

### The AI Coder (Opus/Sonnet)
- **Role**: Specialist in verification, deep analysis, precise implementation
- **Responsibilities**:
  - Execute Prime Directive (verify-before-acting)
  - Implement tasks following mandatory workflow loop
  - Provide comprehensive reports using Template C-4.20
  - Perform post-implementation integrity audits
  - **PROHIBITED**: Git commits with "Co-Authored-By: Claude" (see CLAUDE.md absolute rules)

---

## Why

TheAuditor captures all data needed to detect dead code (unused modules, unreachable functions, isolated classes) but **does not surface it to users**. This creates blind spots where significant code (e.g., `journal.py` - 446 lines, 15+ dev hours) sits unused, wasting maintenance effort and expanding attack surface.

**Evidence from Database Analysis**:
- ✅ `symbols` table tracks all functions, classes, modules
- ✅ `refs` table tracks all imports
- ✅ `function_call_args` table tracks all function calls
- ✅ `graph/analyzer.py` counts isolated nodes (but doesn't list them)
- ❌ No command to expose dead code to users
- ❌ No AI-readable reports for cleanup recommendations

**Security & Maintenance Impact**:
- Dead code = unpatched vulnerabilities in unused code
- Attack surface expansion (code exists but shouldn't run)
- False sense of completeness ("we have feature X!" when unused)
- Wasted developer time updating code that serves no purpose

**The Gap**: TheAuditor has a security camera that records everything (database) but no motion detection alerts (analysis surfacing).

---

## What Changes

This proposal adds **dead code detection and isolation analysis** as a first-class feature of TheAuditor, exposing existing database evidence to users through multiple interfaces.

### New Capabilities

1. **`aud deadcode` Command** (Primary Interface)
   - Lists modules never imported
   - Lists functions never called
   - Lists classes never instantiated
   - JSON output for CI/CD integration
   - Human-readable summary with recommendations

2. **`aud graph analyze --show-isolated` Flag**
   - Extends existing graph analysis
   - Lists isolated nodes (not just counts them)
   - Writes detailed output to `.pf/raw/graph_summary.json`
   - Updates `.pf/readthis/dead_code.txt` for AI consumption

3. **Dead Code Quality Rule** (`rules/quality/dead_code.py`)
   - Integrated into `aud full` pipeline
   - Generates findings with severity="info"
   - Written to `findings_consolidated` table
   - Query-based (no AST parsing required)

4. **AI-Readable Dead Code Report** (`.pf/readthis/dead_code.txt`)
   - Auto-generated when dead code detected
   - Includes file paths, symbol counts, context
   - Recommendations for cleanup (remove vs integrate)
   - Consumed by AI assistants for proactive suggestions

### Implementation Philosophy

**Apply DRY Principle**:
- Single source of truth: `repo_index.db` (symbols, refs, function_call_args tables)
- Shared query logic in `theauditor/queries/dead_code.py`
- Reusable across CLI command, quality rule, graph analyzer

**Separation of Concerns**:
- **Data Layer**: SQL queries in `theauditor/queries/dead_code.py`
- **Analysis Layer**: Detection logic in `theauditor/analysis/isolation.py`
- **Presentation Layer**: CLI formatters, JSON serializers, report generators
- **Integration Layer**: Quality rule, graph analyzer hooks

**No Fallbacks, No Exceptions** (per CLAUDE.md):
- Direct database queries with hard failure on error
- No regex fallbacks if database queries return empty
- No table existence checks (schema contract guarantees tables exist)
- Crashes expose bugs immediately (database wrong = fix indexer)

---

## Impact

### Affected Specifications

**New Capability Created**:
- `openspec/specs/code-quality/spec.md` (NEW)
  - Dead code detection requirements
  - Isolation analysis scenarios
  - Report generation contract

**Modified Capabilities**:
- `openspec/specs/graph-analysis/spec.md` (MODIFIED)
  - Add `--show-isolated` flag requirement
  - Update graph summary JSON schema
- `openspec/specs/quality-rules/spec.md` (MODIFIED if exists, else ADDED)
  - Add dead code rule integration
- `openspec/specs/ai-reports/spec.md` (MODIFIED if exists, else ADDED)
  - Add dead_code.txt report specification

### Affected Code

**New Files**:
- `theauditor/queries/dead_code.py` - SQL queries for isolation detection
- `theauditor/analysis/isolation.py` - Dead code analysis logic
- `theauditor/commands/deadcode.py` - CLI command implementation
- `rules/quality/dead_code.py` - Quality rule integration
- `tests/test_dead_code_detection.py` - Test suite

**Modified Files**:
- `theauditor/graph/analyzer.py` - Add `--show-isolated` flag support
- `theauditor/cli.py` - Register `deadcode` command
- `.pf/readthis/` - Add `dead_code.txt` report generation

### Database Impact

**NO schema changes required** (all data exists):
- Queries: `symbols`, `refs`, `function_call_args` tables
- No migrations needed (database regenerated fresh every `aud full`)
- Schema contract guarantees table existence

### User Impact

**Before (Current State)**:
```bash
# Dead code detection requires manual SQL
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
# ... manual query construction ...
"
```

**After (This Proposal)**:
```bash
# Simple CLI command
aud deadcode

# Output:
# === Dead Code Analysis ===
#
# Modules never imported:
#   - theauditor/journal.py (3 symbols, 446 lines)
#     Recommendation: Remove or integrate into pipelines
#
# Functions never called:
#   - theauditor/utils/legacy.py::old_format() (line 42)
#
# Classes never instantiated:
#   - theauditor/insights/experimental.py::ExperimentalFeature
#
# Total: 1 module, 1 function, 1 class (estimated 15+ hours of wasted effort)

# Graph integration
aud graph analyze --show-isolated

# CI/CD integration
aud deadcode --json > dead_code_report.json
```

### Risk Assessment

**Low Risk Implementation**:
- ✅ No schema changes (uses existing tables)
- ✅ No breaking changes to existing commands
- ✅ Opt-in feature (doesn't run unless invoked)
- ✅ Read-only operations (no database writes)
- ✅ Independent of core indexing pipeline

**Potential False Positives**:
- Dynamically imported modules (e.g., `importlib.import_module()`)
- Reflection-based calls (e.g., `getattr(obj, 'method_name')()`)
- Entry points called externally (CLI commands, API routes)

**Mitigation Strategy**:
- Severity = "info" (not "warning" or "error")
- Clear documentation of limitations
- Allowlist mechanism for known false positives (future enhancement)

---

## Success Criteria

### Functional Requirements
- [ ] `aud deadcode` command successfully lists unused modules, functions, classes
- [ ] `aud graph analyze --show-isolated` flag lists isolated nodes
- [ ] Quality rule generates findings in `findings_consolidated` table
- [ ] `.pf/readthis/dead_code.txt` generated when dead code detected
- [ ] JSON output format suitable for CI/CD pipelines

### Quality Requirements (SOP v4.20)
- [ ] Coder provides Template C-4.20 report for each implementation phase
- [ ] Lead Auditor validates root cause analysis and edge case coverage
- [ ] Post-implementation integrity audit confirms no syntax errors or side effects
- [ ] Architect approves final deliverables

### Performance Requirements
- [ ] Dead code analysis completes in <2 seconds for 10,000-symbol codebase
- [ ] No measurable impact on `aud full` runtime (rule runs in parallel)
- [ ] Graph analysis overhead <500ms when `--show-isolated` flag used

### Validation Requirements
- [ ] `openspec validate add-dead-code-detection --strict` passes
- [ ] All spec deltas have at least one `#### Scenario:` per requirement
- [ ] Design decisions documented with alternatives considered
- [ ] Test coverage ≥90% for new code

---

## Timeline Estimate

**Total Effort**: 4-6 hours (single session)

- **Phase 1**: Data layer queries (1 hour)
- **Phase 2**: CLI command + formatters (1.5 hours)
- **Phase 3**: Graph analyzer integration (1 hour)
- **Phase 4**: Quality rule + report generation (1 hour)
- **Phase 5**: Testing + validation (1.5 hours)

---

## Approval Workflow

1. **Architect Reviews Proposal** → Approves/Requests Changes
2. **Lead Auditor Reviews Technical Approach** → Validates DRY/SoC principles
3. **Coder Begins Implementation** → Only after approval from both
4. **Phased Reporting** → Coder reports after each phase using Template C-4.20
5. **Lead Auditor Validates Each Phase** → Before Coder proceeds to next
6. **Final Acceptance** → Architect validates complete implementation

---

## Next Steps

**DO NOT PROCEED WITH IMPLEMENTATION UNTIL THIS PROPOSAL IS APPROVED.**

1. Architect: Review and approve/modify this proposal
2. Lead Auditor: Validate technical approach and resource estimates
3. Coder: Execute Phase 0 verification (read existing code, validate hypotheses)
4. Coder: Implement tasks sequentially, reporting after each phase
5. Coder: Perform post-implementation audit and submit final report
6. Archive: Move to `openspec/changes/archive/YYYY-MM-DD-add-dead-code-detection/`

---

**Document Version**: 1.0
**Created**: 2025-10-31
**Protocol Compliance**: SOP v4.20, OpenSpec Stage 1 (Creating Changes)
