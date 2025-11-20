# FCE JSON Normalization Tasks

**CRITICAL**: Reverses commit d8370a7 exemption - Architect must approve

---

## 0. Verification Phase

- [ ] 0.1 Read Investigation Report section 5.1
- [ ] 0.2 Read commit d8370a7 diff
- [ ] 0.3 Execute Verification Protocol
- [ ] 0.4 Get Architect Approval for REVERSING exemption

---

## Task 5: FCE findings_consolidated.details_json Normalization

**Estimated Time**: 2-3 days

### 5.1 Audit Current details_json Usage
- [ ] 5.1.1 Read `fce.py:60-401` - Identify all 7 json.loads() calls
- [ ] 5.1.2 Document structure of each JSON payload
- [ ] 5.1.3 Measure baseline FCE performance with cProfile

### 5.2 Create Normalized Tables (core_schema.py)
- [ ] 5.2.1 Create `finding_taint_paths` table (AUTOINCREMENT, indexed)
- [ ] 5.2.2 Create `finding_graph_hotspots` table
- [ ] 5.2.3 Create `finding_cfg_complexity` table
- [ ] 5.2.4 Create `finding_metadata` table
- [ ] 5.2.5 Verify all follow d8370a7 junction table pattern

### 5.3 Update Database Writers
- [ ] 5.3.1 Modify `base_database.py` - Remove details_json writes
- [ ] 5.3.2 Update `taint/analysis.py` - Write to finding_taint_paths
- [ ] 5.3.3 Update `graph/store.py` - Write to finding_graph_hotspots
- [ ] 5.3.4 Update CFG writer - Write to finding_cfg_complexity
- [ ] 5.3.5 Update vuln scanner - Write to finding_metadata

### 5.4 Replace FCE json.loads() Calls
- [ ] 5.4.1 Replace line 60 (hotspots) with JOIN query
- [ ] 5.4.2 Replace line 78 (cycles) with JOIN query
- [ ] 5.4.3 Replace line 127 (CFG complexity) with JOIN query
- [ ] 5.4.4 Replace line 168 (code churn) with JOIN query
- [ ] 5.4.5 Replace line 207 (test coverage) with JOIN query
- [ ] 5.4.6 Replace line 265 (taint paths - CRITICAL) with JOIN query
- [ ] 5.4.7 Replace line 401 (metadata) with JOIN query

### 5.5 Testing
- [ ] 5.5.1 Fixture validation on 10 projects
- [ ] 5.5.2 Compare FCE output before/after (functionally equivalent)
- [ ] 5.5.3 Measure FCE speedup: Target 75-700ms → <10ms

---

## Task 6: symbols.parameters Normalization

**Estimated Time**: 1 day

### 6.1 Audit Current Usage
- [ ] 6.1.1 Read `taint/discovery.py:112` - Verify JSON parsing
- [ ] 6.1.2 Read `javascript.py:1288` - Verify duplicate parsing

### 6.2 Create symbol_parameters Table
- [ ] 6.2.1 Create table in `core_schema.py` (AUTOINCREMENT pattern)
- [ ] 6.2.2 Verify follows d8370a7 style

### 6.3 Update Extractors
- [ ] 6.3.1 Modify Python extractor - Write to symbol_parameters
- [ ] 6.3.2 Modify JavaScript extractor - Write to symbol_parameters
- [ ] 6.3.3 Remove symbols.parameters column writes

### 6.4 Update Consumers
- [ ] 6.4.1 Replace `taint/discovery.py:112` with JOIN query
- [ ] 6.4.2 Replace `javascript.py:1288` with JOIN query
- [ ] 6.4.3 **COORDINATE with AI #3** (line 1288 vs lines 748-768)

### 6.5 Testing
- [ ] 6.5.1 Verify extraction parity on 100 Python/JS files
- [ ] 6.5.2 Verify taint discovery works correctly

---

## Task 7: Schema Contract Validation

**Estimated Time**: 1-2 days

### 7.1 Add JSON Blob Detector (schema.py)
- [ ] 7.1.1 Implement `_detect_json_blobs(tables)` function
- [ ] 7.1.2 Define LEGITIMATE_EXCEPTIONS (nodes.metadata, edges.metadata, plan_documents.document_json)
- [ ] 7.1.3 Add assertion: `assert len(violations) == 0`

### 7.2 Add Junction Table Validator
- [ ] 7.2.1 Implement AUTOINCREMENT checker for junction tables
- [ ] 7.2.2 Validate existing tables pass

### 7.3 Testing
- [ ] 7.3.1 Test with temporary JSON blob - Verify assertion fires
- [ ] 7.3.2 Test legitimate exceptions pass
- [ ] 7.3.3 Test would catch future violations

---

## Task 8: Coordination with AI #3

### 8.1 Merge Coordination
- [ ] 8.1.1 Communicate line number shifts
- [ ] 8.1.2 AI #3 modifies lines 748-768
- [ ] 8.1.3 AI #4 modifies line 1288 (becomes line ~1308 after AI #3)
- [ ] 8.1.4 Apply both changes, verify no conflicts

---

## Completion Checklist

- [ ] All tasks 5.1-5.5 completed (FCE normalized)
- [ ] All tasks 6.1-6.5 completed (symbols.parameters normalized)
- [ ] All tasks 7.1-7.3 completed (schema validator added)
- [ ] FCE overhead: 75-700ms → <10ms
- [ ] Zero JSON TEXT columns (except exemptions)
- [ ] Coordinated merge with AI #3
- [ ] Architect approval

---

**Status**: 🔴 VERIFICATION - Awaiting approval to REVERSE commit d8370a7

**Estimated Time**: 3-4 days
