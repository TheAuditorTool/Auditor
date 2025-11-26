# Node Data Fidelity Control - Pre-Implementation Briefing

**Document Type:** Handoff / Onboarding / Pre-Implementation Plan
**Date:** 2025-11-26
**Status:** PHASE 0-2 COMPLETE (Fidelity Infrastructure Ticket), PHASE 3-4 DEFERRED TO node-schema-normalization
**Authors:** Lead Coder (Opus), Lead Auditor (Gemini)

---

## Executive Summary

Python extraction is now **PRODUCTION-GRADE** with full data fidelity control. Node extraction is **NOT**. This document captures the gap and proposes a remediation plan to bring Node/JS/TS extraction to parity with Python.

**The Mission:** Bring the Node.js/TypeScript extraction pipeline up to the **Gold Standard** established by the Python refactor.

| Target | Constraint | Architecture |
|--------|------------|--------------|
| 100% Data Fidelity (Manifest vs Receipt) | Zero direct SQL in storage handlers | Consolidated Schema + Junction Tables + Two-Discriminator |

**Risk Level:** HIGH - Node can silently lose data with no detection mechanism.

---

## Part 1: The Python Hat-Trick (3 Completed Tickets)

The Python extraction system was fixed across **3 sequential tickets**. Node must follow the same progression.

### Ticket 1: `consolidate-python-orphan-tables` (61/73 tasks)
**What:** Schema consolidation from 149 granular tables to 8 core tables
**Why:** Eliminate orphan tables with no consumers, reduce schema complexity
**Key Output:** Consolidated table structure with clear ownership

### Ticket 2: `wire-extractors-to-consolidated-schema` (82/241 tasks)
**What:** Wire 150+ extractor outputs to the 28 consolidated tables
**Why:** Connect extraction layer to storage layer properly
**Key Output:** Orchestrator (`python_impl.py`) routing extractors to tables
**Critical Bug Found:** Schema columns were INVENTED without verifying extractor output → 22MB data loss

### Ticket 3: `python-extractor-consolidation-fidelity` (197/222 tasks) ✅ ARCHIVED
**What:** Fix the data loss bug, implement fidelity control
**Why:** Prevent silent data loss, enforce extraction/storage contract
**Key Outputs:**
- `extractor_truth.txt` - Ground truth of what extractors actually output
- `fidelity.py` - Manifest/Receipt reconciliation
- `exceptions.py` - `DataFidelityError` exception
- `test_schema_contract.py` - 16 tests preventing drift
- Two-discriminator pattern (`*_kind` + `*_type`)
- 5 junction tables replacing JSON blobs

### The Progression Pattern
```
Ticket 1: CONSOLIDATE schema (reduce tables)
    ↓
Ticket 2: WIRE extractors to schema (connect layers)
    ↓
Ticket 3: VERIFY fidelity (prevent data loss)
```

**Node must follow this same pattern.**

---

## Part 2: Current State of Node (Investigation Findings)

### 2.1 Schema Analysis

| Metric | Python (After) | Node (Current) | Gap |
|--------|----------------|----------------|-----|
| Total Tables | 35 | 42 | Node needs consolidation |
| Two-Discriminator | 22 tables | 0-1 tables | **CRITICAL** |
| JSON Blobs | 0 | 7+ | Needs junction tables |
| Explicit PKs | 100% | 69% | 13 tables use implicit ROWID |
| Junction Tables | 5 (proper) | 5 (partial) | Needs expansion |

### 2.2 Critical Finding: No Data Fidelity Controls

**9 of 17 Node handlers bypass the database mixin entirely:**

| Handler | File Location | Problem |
|---------|---------------|---------|
| `_store_sequelize_models` | `node_storage.py` | Direct `cursor.execute()` |
| `_store_sequelize_associations` | `node_storage.py` | No batching |
| `_store_bullmq_queues` | `node_storage.py` | No receipt tracking |
| `_store_bullmq_workers` | `node_storage.py` | No transaction coherence |
| `_store_angular_components` | `node_storage.py` | Bypasses fidelity |
| `_store_angular_services` | `node_storage.py` | Silent data loss possible |
| `_store_angular_modules` | `node_storage.py` | No batch grouping |
| `_store_angular_guards` | `node_storage.py` | Performance degradation |
| `_store_di_injections` | `node_storage.py` | All above issues |

**Impact:** The same 22MB silent data loss bug we fixed in Python? **Node has it RIGHT NOW.**

### 2.3 JSON Blob Violations (Need Junction Tables)

| Table | Column | Replacement Junction Table |
|-------|--------|----------------------------|
| `react_hooks` | `dependency_array` | `react_hook_dependencies` |
| `vue_components` | `props_definition` | `vue_component_props` |
| `vue_components` | `emits_definition` | `vue_component_emits` |
| `vue_components` | `setup_return` | `vue_component_setup_returns` |
| `angular_modules` | `declarations` | `angular_module_declarations` |
| `angular_modules` | `imports` | `angular_module_imports` |
| `angular_modules` | `providers` | `angular_module_providers` |
| `angular_modules` | `exports` | `angular_module_exports` |

### 2.4 Missing Database Methods

`node_database.py` needs these `add_*` methods (currently handlers use raw SQL):

```python
# MISSING - Need to create:
add_sequelize_model()
add_sequelize_association()
add_bullmq_queue()
add_bullmq_worker()
add_angular_component()
add_angular_service()
add_angular_module()
add_angular_guard()
add_di_injection()
```

### 2.5 Storage Architecture Comparison

```
Python Storage (CORRECT):
  handler() → db_manager.add_*() → generic_batches → flush → transaction
                                   ↑
                                   RECEIPT TRACKED

Node Storage (BROKEN for 9 handlers):
  handler() → cursor.execute() → immediate write
              ↑
              BYPASSES:
              - Batching
              - Transaction coherence
              - Receipt tracking
              - Error recovery
```

### 2.6 What Node Does RIGHT (Don't Break These)

1. **Semantic Parsing** - Uses TypeScript Compiler API (not Tree-sitter) ✓
2. **Batch Processing** - Reuses compiler instance across files ✓
3. **Scope Mapping** - `buildScopeMap()` provides O(1) line→function lookups ✓
4. **Some Junction Tables** - 5 proper tables with FKs (React/Vue hooks) ✓
5. **Framework Detection** - React/Vue/Angular patterns well-covered ✓

---

## Part 3: Gap Analysis Summary

| Component | Python Status | Node Status | Priority |
|-----------|---------------|-------------|----------|
| Data Fidelity Control | ✅ PRODUCTION | ❌ NONE | **CRITICAL** |
| Storage Batching | ✅ 29/29 handlers | ⚠️ 8/17 handlers | **CRITICAL** |
| Database Mixin | ✅ Complete | ❌ 9 methods missing | **CRITICAL** |
| Two-Discriminator Pattern | ✅ 22 tables | ❌ 0-1 tables | HIGH |
| JSON Blob Elimination | ✅ Complete | ❌ 7+ blobs remain | HIGH |
| Schema Contract Tests | ✅ 16 tests | ❌ 0 tests | HIGH |
| Explicit Primary Keys | ✅ 100% | ⚠️ 69% | MEDIUM |

---

## Part 4: Implementation Plan (Lead Auditor Approved)

### Phase 0: Verification (The Audit) - COMPLETED BY LEAD AUDITOR
**Goal:** Confirm the "crime scene" before touching evidence.
**Status:** ✅ ALL HYPOTHESES VERIFIED

- [x] **0.1** Create `scripts/audit_node_extractors.py` (mirror Python version)
- [x] **0.2** Generate `node_extractor_truth.txt`
- [x] **0.3** Audit `node_storage.py` - Locate 9 rogue handlers using `cursor.execute`
- [x] **0.4** Audit `node_schema.py` - Identify all JSON blob columns
- [x] **0.5** Audit `javascript.py` / `typescript_impl.py` - Find manifest injection points
- [x] **0.6** Document invented vs actual columns (like we did for Python)

**See Part 9 for full verification evidence with line numbers.**

### Phase 1: Fidelity Infrastructure (The Safety Net) - COMPLETED 2025-11-26
**Goal:** Install the "Accountant" before we start moving money.

- [x] **1.1** Update `javascript.py` orchestrator to generate `_extraction_manifest` - DONE (lines 806-830)
- [x] **1.2** Verify orchestrator already wired (`orchestrator.py:767` calls `reconcile_fidelity`) - VERIFIED
- [x] **1.3** Verify `storage/__init__.py:104` skips `_extraction_manifest` key in handler dispatch - VERIFIED

**Result:** Manifest generation active. Fidelity check runs automatically for all JS/TS files.

### Phase 2: Storage Architecture Repair (The Plumbing) - COMPLETED 2025-11-26
**Goal:** Fix the 9 rogue handlers that break the receipt system.

- [x] **2.1** Implement 9 missing `add_*` methods in `node_database.py` - DONE (lines 160-240)
- [x] **2.2** All methods use `self.generic_batches` pattern - VERIFIED
- [x] **2.3** Refactor 9 rogue handlers to call `db_manager.add_*` - DONE
- [x] **2.4** Remove ALL direct `cursor` usage from `node_storage.py` - VERIFIED (grep = 0 results)
- [x] **2.5** Verify receipt tracking works for all 17 handlers - VERIFIED via `aud full --offline`

**Result:** All handlers now use batched database methods. Zero direct cursor access. Pipeline tested successfully.

### Phase 3: Schema Normalization (The Structure) - DEFERRED
**Goal:** Eliminate JSON blobs and enforce precise querying.
**Status:** DEFERRED to `node-schema-normalization` ticket per design.md non-goals.

- [ ] **3.1** Create `react_hook_dependencies` junction table
- [ ] **3.2** Create `vue_component_props`, `vue_component_emits` junction tables
- [ ] **3.3** Create `angular_module_*` junction tables (declarations, imports, providers, exports)
- [ ] **3.4** Add two-discriminator pattern where applicable
- [ ] **3.5** Add explicit PKs to tables using implicit ROWID
- [ ] **3.6** Regenerate codegen for Node tables

### Phase 4: Contract Tests & Verification - PARTIAL (Fidelity Testing Done)
**Goal:** Prevent future drift, validate the fix.
**Status:** Schema contract tests DEFERRED to `node-schema-normalization`. Fidelity testing COMPLETED.

- [ ] **4.1** Create `tests/test_node_schema_contract.py` - DEFERRED
- [ ] **4.2** Test table counts, discriminators, junction FKs - DEFERRED
- [ ] **4.3** Test no JSON blob columns remain - DEFERRED
- [ ] **4.4** Test all handlers use batched methods - DEFERRED
- [ ] **4.5** Ensure all JS/TS extractors return `List[dict]` - DEFERRED
- [x] **4.6** Run `aud full --offline` on Node-heavy codebase - DONE (node-fidelity-infrastructure)
- [x] **4.7** Verify 0 fidelity errors - VERIFIED
- [x] **4.8** Final ruff check - PASSED

---

## Part 5: Files Involved

### Primary Targets (To Modify)
| File | Purpose | Changes Needed |
|------|---------|----------------|
| `theauditor/indexer/schemas/node_schema.py` | Schema definitions | Add discriminators, PKs, junction tables |
| `theauditor/indexer/database/node_database.py` | Database mixin | Add 9 missing `add_*` methods |
| `theauditor/indexer/storage/node_storage.py` | Storage handlers | Migrate 9 handlers to batched methods |
| `theauditor/indexer/extractors/javascript.py` | JS orchestrator | Add manifest generation |
| `theauditor/ast_extractors/typescript_impl.py` | TS extraction | Verify extractor outputs |

### To Create
| File | Purpose |
|------|---------|
| `scripts/audit_node_extractors.py` | Ground truth extractor audit |
| `node_extractor_truth.txt` | Extractor output documentation |
| `tests/test_node_schema_contract.py` | Schema contract tests |

### Reference (Python Implementation - Copy Patterns From)
| File | Pattern To Copy |
|------|-----------------|
| `theauditor/indexer/schemas/python_schema.py` | Two-discriminator pattern, junction tables |
| `theauditor/indexer/database/python_database.py` | Batched `add_*` method pattern |
| `theauditor/indexer/storage/python_storage.py` | Handler → db_manager pattern |
| `theauditor/indexer/fidelity.py` | Manifest/receipt reconciliation |
| `theauditor/ast_extractors/python_impl.py` | Manifest generation in orchestrator |
| `tests/test_schema_contract.py` | Contract test pattern |
| `scripts/audit_extractors.py` | Extractor audit script pattern |

---

## Part 6: Risk Assessment

### High Risk Areas
1. **Angular module JSON blobs** - 4 columns need junction tables, complex data
2. **Direct cursor handlers** - 9 handlers need careful migration to preserve behavior
3. **TypeScript Compiler API** - Don't break the semantic parsing that works
4. **Cross-file dependencies** - Node extraction has more complex module resolution

### Mitigations
1. **Incremental migration** - One handler at a time with tests after each
2. **Row count verification** - Before/after comparison for each change
3. **Reference implementation** - Python code provides exact patterns to follow
4. **Crash-first fidelity** - Install fidelity control FIRST so it catches our mistakes

### What NOT To Touch
- TypeScript Compiler API integration
- `buildScopeMap()` functionality
- Batch processing architecture
- Framework detection logic
- Existing working junction tables

---

## Part 7: Session Onboarding Checklist

When resuming this work in a new session:

1. [ ] Read this document (`node_receipts.md`)
2. [ ] Read `teamsop.md` for protocol compliance
3. [ ] Check OpenSpec status: `openspec list`
4. [ ] Verify Python implementation still works: `pytest tests/test_schema_contract.py`
5. [ ] Identify current phase from task checklist above
6. [ ] Continue from last completed task

---

## Part 8: Definition of Done

### Fidelity Infrastructure (node-fidelity-infrastructure) - COMPLETED 2025-11-26

- [x] All 17 storage handlers use `db_manager.add_*()` (0 direct cursors)
- [x] Manifest/Receipt reconciliation enabled for Node pipeline
- [x] `aud full --offline` runs clean on Node-heavy codebase
- [x] 0 data loss between extraction and storage (verified: sequelize=3+21, react=224+196)

### Schema Normalization (node-schema-normalization) - PENDING

- [ ] All JSON blob columns replaced with junction tables
- [ ] Two-discriminator pattern applied where applicable
- [ ] Schema contract tests pass (target: 10+ tests)

---

## Part 9: Lead Auditor Verification Report

**Role:** Lead Auditor Gemini
**Status:** SOP v4.20 Loaded. Prime Directive (Verify Before Acting) Active.
**Date:** 2025-11-26

### Files Ingested for Verification
- `node_schema.py`
- `node_storage.py`
- `node_database.py`
- `javascript.py`
- `typescript_impl.py`
- `js_helper_templates.py`
- `js_semantic_parser.py`
- `core_language.js`

---

### Hypothesis 1: Rogue Handlers use direct `cursor.execute()` in `node_storage.py`
**Verification:** ✅ **CONFIRMED**

**Evidence (Line Numbers):**
| Line | Method | Problem |
|------|--------|---------|
| 109 | `_store_sequelize_models` | `self.db_manager.conn.cursor()` direct access |
| 125 | `_store_sequelize_associations` | Direct SQL execution |
| 141 | `_store_bullmq_queues` | Bypasses batching |
| 155 | `_store_bullmq_workers` | No transaction coherence |
| 169 | `_store_angular_components` | Direct cursor |
| 185 | `_store_angular_services` | Direct cursor |
| 199 | `_store_angular_modules` | Direct cursor |
| 213 | `_store_angular_guards` | Direct cursor |
| 227 | `_store_di_injections` | Direct cursor |

**Impact:** These handlers bypass the batching system (`generic_batches`), transaction management, and the future Receipt tracking system.

---

### Hypothesis 2: `node_database.py` is missing mixin methods for rogue handlers
**Verification:** ✅ **CONFIRMED**

**Evidence:**
- `node_database.py` contains methods for: `class_properties`, `react_components`, `vue_components`, `package_configs`
- **MISSING:** `add_sequelize_model`, `add_sequelize_association`, `add_bullmq_queue`, `add_angular_component`, etc.

**Result:** The storage layer *has* to use direct SQL because the DB layer provides no interface.

---

### Hypothesis 3: JSON Blobs exist in `node_schema.py` that block SQL JOINs
**Verification:** ✅ **CONFIRMED**

**Evidence (Line Numbers):**
| Table | Line | Column(s) | Type |
|-------|------|-----------|------|
| `VUE_COMPONENTS` | 148 | `props_definition`, `emits_definition` | TEXT (JSON) |
| `ANGULAR_COMPONENTS` | 327 | `style_paths` | TEXT (JSON) |
| `ANGULAR_MODULES` | 354 | `declarations`, `imports`, `providers`, `exports` | TEXT (JSON) |

**Result:** Taint analysis cannot query "Which module imports `AuthModule`?" without parsing JSON rows.

---

### Hypothesis 4: Extraction Manifest infrastructure is missing in `javascript.py`
**Verification:** ✅ **CONFIRMED**

**Evidence:**
- `javascript.py` (Line 73) returns a plain `result` dictionary
- **Missing:** No logic to count items and inject `_extraction_manifest`

---

### Receipt Tracking Partial Analysis

**Observation:** `_store_sequelize_models` (Line 122) *does* update `self.counts['sequelize_models'] += 1`.

**Analysis:** Receipt generation *might* partially work, BUT the direct SQL bypasses the *transactional* safety of the receipt. Items could be counted but fail insert without detection.

**Verdict:** Partial counting is worse than no counting - it creates false confidence.

---

### AI Coder Implementation Prompts

#### Phase 1 Prompt (Fidelity Infrastructure):
1. Modify `theauditor/indexer/extractors/javascript.py`:
   - In `extract()`, before returning `result`, count all list items in `result`
   - Create `manifest = {key: len(value) ...}`
   - Add metadata: `_total`, `_timestamp`
   - Inject `result['_extraction_manifest'] = manifest`

2. Verify `theauditor/indexer/orchestrator.py`:
   - `_store_extracted_data` calls `reconcile_fidelity` if manifest exists
   - Node uses same orchestrator method - adding manifest activates check automatically

#### Phase 2 Prompt (Storage Repair):
1. Update `node_database.py`:
   - Implement 9 missing `add_*` methods using `self.generic_batches`
   - Follow `python_database.py` pattern exactly

2. Update `node_storage.py`:
   - Refactor 9 handlers to call `db_manager.add_*` instead of `cursor.execute`
   - Remove ALL direct cursor access

#### Phase 3 Prompt (Schema Normalization):
1. Schema Layer:
   - Create `vue_component_props`, `vue_component_emits` junction tables
   - Create `angular_module_declarations`, `angular_module_imports`, `angular_module_providers`, `angular_module_exports` junction tables
   - Update parent table schemas to remove JSON columns

2. Database Layer:
   - Update `add_*` methods to support new schema (ID return pattern for parents)

3. Storage Layer:
   - Logic to insert parent -> get ID -> insert children

---

## Confirmation of Understanding

This document captures:
- ✅ The 3 Python tickets (the hat-trick reference implementation)
- ✅ Current Node state (investigation findings)
- ✅ Gap analysis (prioritized by severity)
- ✅ Detailed implementation plan (4 phases, 30+ tasks)
- ✅ Files involved (modify, create, reference)
- ✅ Risk assessment with mitigations
- ✅ Session onboarding checklist
- ✅ Definition of done
- ✅ **Lead Auditor verification report with line-number evidence** (Part 9)
- ✅ **AI Coder implementation prompts for each phase** (Part 9)

**Next Step:** Create OpenSpec proposal from this briefing when ready to execute.

---

*Document prepared by Lead Coder (Opus) with handoff notes from Lead Auditor (Gemini)*
*Reference: teamsop.md v4.20, Prime Directive compliance verified*
*Python reference tickets: consolidate-python-orphan-tables, wire-extractors-to-consolidated-schema, python-extractor-consolidation-fidelity*
*Lead Auditor verification completed: 2025-11-26, 4/4 hypotheses confirmed*
