# AI Assignment Matrix - Performance Revolution Now

**Status**: 🟢 **READY FOR PARALLEL EXECUTION**

**Verified**: 2025-11-03 by 12-agent verification audit

---

## 📋 EXECUTIVE SUMMARY

**Can 4 AIs work in parallel?** ✅ **YES** - with strict domain boundaries

**Safety Level**: 100% SAFE with defined file boundaries

**Merge Conflicts**: Only 1 file (`javascript.py`) with coordinated line ranges

**Total Time**:
- Sequential: 4-7 weeks
- Parallel (4 AIs): 3-6 weeks (40% time savings)

---

## 🎯 AI ASSIGNMENTS (4 Parallel Workstreams)

### **AI #1: TAINT SUBSYSTEM REFACTOR** (Opus AI recommended)

**Responsibility**: TIER 0 Task 1 - Taint Analysis Spatial Index Refactor

**Complexity**: 🔴 **VERY HIGH** - Most complex refactor in entire proposal

**Estimated Time**: 3-4 days implementation + 1-2 days testing = **5-6 days total**

**Impact**: 95% of total performance gain (540 seconds saved per run)

#### **File Ownership (EXCLUSIVE)**:

```
theauditor/taint/
├── discovery.py          ← AI #1 ONLY (lines 52-177: replace linear scans)
├── analysis.py           ← AI #1 ONLY (lines 187-292: add spatial indexes)
├── propagation.py        ← AI #1 ONLY (lines 224-232: fix LIKE wildcards)
└── schema_cache_adapter.py  ← READ ONLY (understand memory cache interface)

theauditor/indexer/schemas/
└── generated_cache.py    ← AI #1 ONLY (add spatial index builders)
```

**Zero file conflicts with other AIs** ✅

#### **Detailed Scope**:

1. **Add Spatial Indexes to `generated_cache.py`**:
   - `symbols_by_type: Dict[str, List[Dict]]`
   - `symbols_by_file_line: Dict[str, Dict[int, List[Dict]]]`
   - `assignments_by_location: Dict[str, Dict[int, List[Dict]]]`
   - `calls_by_location: Dict[str, Dict[int, List[Dict]]]`
   - `successors_by_block: Dict[str, List[Dict]]`
   - `blocks_by_id: Dict[str, Dict]`

2. **Refactor Discovery Phase** (`discovery.py:52-177`):
   - Replace user input source discovery (lines 52-67) with `symbols_by_type` lookup
   - Replace file read source discovery (lines 70-84) with frozenset lookups
   - Replace command injection sink discovery (lines 163-177) with indexed lookup

3. **Refactor Analysis Phase** (`analysis.py:187-292`):
   - Replace `_get_containing_function` (line 187-195) with spatial index
   - Replace `_propagate_through_block` (line 245-249) with spatial index
   - Replace `_get_calls_in_block` (line 267-270) with spatial index
   - Replace `_get_block_successors` (line 284-292) with adjacency list

4. **Refactor Propagation Phase** (`propagation.py:224-232`):
   - Replace `LIKE '%pattern%'` with indexed pre-filter + Python substring search

#### **Dependencies**:
- ✅ Must read: `INVESTIGATION_REPORT.md` section 2.1-2.4 (taint analysis findings)
- ✅ Must read: `tasks.md` section 1.1-1.4 (detailed implementation steps)
- ✅ Must read: `design.md` section 2.1 (spatial index design decisions)

#### **Testing Requirements**:
- ✅ All 113 taint rules must pass (zero regressions)
- ✅ Fixtures byte-for-byte identical (except timing)
- ✅ Measure 100-1000x operation reduction with profiling

#### **Success Criteria**:
- Taint analysis: 600s → 20-40s (15-30x speedup)
- 165M-20B operations → 1M operations
- Zero false negatives (no security findings lost)

---

### **AI #2: PYTHON AST REFACTOR** (Sonnet AI recommended)

**Responsibility**: TIER 0 Task 2 - Python AST Single-Pass Visitor

**Complexity**: 🟠 **HIGH** - Large refactor but straightforward pattern

**Estimated Time**: 3-4 days implementation + 1-2 days testing = **5-6 days total**

**Impact**: 5% of total performance gain (25 seconds saved per 1,000 files)

#### **File Ownership (EXCLUSIVE)**:

```
theauditor/ast_extractors/python/
├── orchestrator.py       ← AI #2 ONLY (consolidate 82 ast.walk calls)
├── sqlalchemy_extractor.py   ← AI #2 ONLY (convert to visitor pattern)
├── django_extractor.py       ← AI #2 ONLY (convert to visitor pattern)
├── flask_extractor.py        ← AI #2 ONLY (convert to visitor pattern, FIX triply-nested walk line 1053)
├── fastapi_extractor.py      ← AI #2 ONLY (convert to visitor pattern)
├── pydantic_extractor.py     ← AI #2 ONLY (convert to visitor pattern)
├── async_extractor.py        ← AI #2 ONLY (convert to visitor pattern)
├── class_extractor.py        ← AI #2 ONLY (convert to visitor pattern)
├── decorator_extractor.py    ← AI #2 ONLY (convert to visitor pattern)
├── exception_extractor.py    ← AI #2 ONLY (convert to visitor pattern)
├── import_extractor.py       ← AI #2 ONLY (convert to visitor pattern)
├── variable_extractor.py     ← AI #2 ONLY (convert to visitor pattern)
├── comprehension_extractor.py ← AI #2 ONLY (convert to visitor pattern)
├── context_manager_extractor.py ← AI #2 ONLY (convert to visitor pattern)
└── typing_extractor.py       ← AI #2 ONLY (convert to visitor pattern)

theauditor/indexer/extractors/
└── python.py             ← AI #2 ONLY (replace 71 extractor calls with UnifiedPythonVisitor)
```

**Zero file conflicts with other AIs** ✅

#### **Detailed Scope**:

1. **Create `UnifiedPythonVisitor` in `orchestrator.py`**:
   ```python
   class UnifiedPythonVisitor(ast.NodeVisitor):
       def __init__(self):
           self.sqlalchemy_results = []
           self.django_results = []
           self.flask_results = []
           # ... all 15 extractors

       def visit_ClassDef(self, node):
           # All class-related extraction in ONE pass
           sqlalchemy_extractor.extract_class(node, self.sqlalchemy_results)
           django_extractor.extract_class(node, self.django_results)
           # ...
           self.generic_visit(node)

       def visit_FunctionDef(self, node):
           # All function-related extraction in ONE pass
           flask_extractor.extract_route(node, self.flask_results)
           fastapi_extractor.extract_endpoint(node, self.fastapi_results)
           # ...
           self.generic_visit(node)
   ```

2. **Refactor 15 Extractors** - Convert from:
   ```python
   # BEFORE: Independent walk (80x redundant)
   for node in ast.walk(tree):
       if isinstance(node, ast.ClassDef):
           # extract...
   ```
   To:
   ```python
   # AFTER: Visitor callback (called by UnifiedPythonVisitor)
   def extract_class(node, results):
       # extract...
   ```

3. **Replace Orchestrator** (`python.py`):
   ```python
   # BEFORE: 71 function calls, each doing ast.walk()
   results = []
   results.extend(extract_sqlalchemy(tree))
   results.extend(extract_django(tree))
   # ... 71 calls

   # AFTER: 1 visitor traversal
   visitor = UnifiedPythonVisitor()
   visitor.visit(tree)
   results = visitor.get_all_results()
   ```

4. **Critical Fixes**:
   - **TRIPLY-NESTED walk at `flask_extractor.py:1053`** - Must eliminate nested loops
   - Replace `.endswith()` string checks with frozenset lookups
   - Preserve exact database output (byte-for-byte compatibility)

#### **Dependencies**:
- ✅ Must read: `INVESTIGATION_REPORT.md` section 1.1-1.3 (Python AST findings)
- ✅ Must read: `tasks.md` section 2.1-2.7 (detailed implementation steps)
- ✅ Must read: `design.md` section 1.1 (single-pass visitor design)

#### **Testing Requirements**:
- ✅ All Python extraction tests must pass (zero regressions)
- ✅ Database output byte-for-byte identical to current
- ✅ Test on 1,000 Python files (must show 5-8x speedup)

#### **Success Criteria**:
- Python indexing: 90s → 12-18s (5-7.5x speedup)
- 82 ast.walk() → 1 unified visitor
- Zero extraction accuracy loss

---

### **AI #3: JAVASCRIPT OPTIMIZATION** (Sonnet AI recommended)

**Responsibility**: TIER 1 - Vue In-Memory Compilation + Node Module Resolution

**Complexity**: 🟡 **MEDIUM** - JavaScript knowledge required

**Estimated Time**: 2-3 days implementation + 1 day testing = **3-4 days total**

**Impact**: Minor performance gain (6-10 seconds saved per 100 Vue files + 40-60% import accuracy)

#### **File Ownership (MOSTLY EXCLUSIVE)**:

```
theauditor/ast_extractors/javascript/
├── batch_templates.js    ← AI #3 ONLY (Vue in-memory compilation)
├── js_helper_templates.py ← READ ONLY (understand template system)
└── typescript_impl.js     ← READ ONLY (understand TypeScript API)

theauditor/indexer/extractors/
└── javascript.py         ← AI #3 ONLY (LINES 748-768 ONLY - module resolution)
                          ⚠️ CONFLICT with AI #4 (line 1288)
                          ✅ SAFE: Different sections, coordinate merge
```

**1 file partial conflict with AI #4** - Coordinated by line ranges ✅

#### **Detailed Scope**:

**Task 3: Vue SFC In-Memory Compilation** (`batch_templates.js`):

1. **Current Pattern** (3 disk operations per .vue file):
   ```javascript
   // BEFORE: Write temp file, compile, read back, delete
   fs.writeFileSync(tempPath, vueContent);
   const compiled = compileVueSFC(tempPath);
   const result = fs.readFileSync(tempPath);
   fs.unlinkSync(tempPath);
   ```

2. **New Pattern** (in-memory):
   ```javascript
   // AFTER: Compile in-memory, pass to TypeScript API
   const { script, template, styles } = parseVueSFC(vueContent);
   const compiledScript = compileScriptSetup(script);
   return { script: compiledScript, template, styles };
   ```

3. **Expected Impact**: 35-95ms overhead eliminated per .vue file

**Task 4: Node Module Resolution** (`javascript.py:748-768`):

1. **Current Pattern** (basename only):
   ```python
   # BEFORE: 40-60% imports unresolved
   imp_path.split('/')[-1]  # Only gets basename
   ```

2. **New Pattern** (TypeScript algorithm):
   ```python
   # AFTER: Proper resolution
   def resolve_import(import_path, from_file):
       # 1. Relative imports (./foo, ../bar)
       # 2. Path mappings (@/components)
       # 3. node_modules lookup
       # 4. index.js/ts resolution
       return resolved_path
   ```

3. **Expected Impact**: 40-60% more imports resolved (cross-file taint accuracy)

#### **Dependencies**:
- ✅ Must read: `INVESTIGATION_REPORT.md` sections 4.1-4.2 (JavaScript findings)
- ✅ Must read: `tasks.md` sections 3.1-3.4, 4.1-4.5 (Vue + module resolution)
- ✅ Must read: `design.md` sections 3.1-3.2 (Vue + resolution design)

#### **Coordination with AI #4**:
- ⚠️ Both touch `javascript.py`
- ✅ AI #3: Lines 748-768 (module resolution)
- ✅ AI #4: Line 1288 (parameters normalization)
- ✅ Merge strategy: Apply both changes, no overlap

#### **Testing Requirements**:
- ✅ Vue fixtures must match byte-for-byte
- ✅ Import resolution: Measure % resolved (expect 40-60% improvement)
- ✅ TypeScript API: No redundant calls (1 program per batch)

#### **Success Criteria**:
- Vue compilation: 9s → 3s per 100 files (70% speedup)
- Import resolution: 40-60% → 80-90% resolved
- Zero extraction accuracy loss

---

### **AI #4: DATABASE NORMALIZATION** (Sonnet AI recommended)

**Responsibility**: TIER 1.5 - JSON Blob Normalization (4 tasks)

**Complexity**: 🟡 **MEDIUM** - Schema and database work

**Estimated Time**: 2-3 days implementation + 1 day testing = **3-4 days total**

**Impact**: Minor performance gain (75-700ms FCE overhead eliminated)

#### **File Ownership (MOSTLY EXCLUSIVE)**:

```
theauditor/
├── fce.py                ← AI #4 ONLY (replace 7 json.loads calls)

theauditor/indexer/
├── schema.py             ← AI #4 ONLY (add JSON blob validator)
└── schemas/
    └── core_schema.py    ← AI #4 ONLY (add 4 normalized tables)

theauditor/indexer/database/
├── base_database.py      ← AI #4 ONLY (update findings_consolidated writer)
├── python_database.py    ← READ ONLY (understand python_routes schema)
└── javascript_database.py ← READ ONLY (understand symbols.parameters)

theauditor/taint/
└── discovery.py          ← AI #4 ONLY (line 112 - replace symbols.parameters JSON parse)

theauditor/indexer/extractors/
└── javascript.py         ← AI #4 ONLY (LINE 1288 ONLY - parameters normalization)
                          ⚠️ CONFLICT with AI #3 (lines 748-768)
                          ✅ SAFE: Different lines, coordinate merge
```

**1 file partial conflict with AI #3** - Coordinated by line ranges ✅

#### **Detailed Scope**:

**Task 5: FCE findings_consolidated.details_json Normalization**:

1. **Replace 7 json.loads() calls in `fce.py`**:
   - Line 60: Hotspots → `finding_graph_hotspots` table
   - Line 78: Cycles → `finding_graph_cycles` table
   - Line 127: CFG complexity → `finding_cfg_complexity` table
   - Line 168: Code churn → `finding_code_churn` table (already exists? verify)
   - Line 207: Test coverage → `finding_test_coverage` table (already exists? verify)
   - Line 265: **CRITICAL** Taint paths → `finding_taint_paths` table (50-500ms bottleneck)
   - Line 401: Additional metadata → `finding_metadata` table

2. **Create 4 new normalized tables in `core_schema.py`**:
   ```python
   FINDING_TAINT_PATHS = TableSchema(
       name="finding_taint_paths",
       columns=[
           Column("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
           Column("finding_id", "TEXT", nullable=False),
           Column("path_index", "INTEGER", nullable=False),
           Column("source_file", "TEXT"),
           Column("source_line", "INTEGER"),
           Column("sink_file", "TEXT"),
           Column("sink_line", "INTEGER"),
           Column("path_length", "INTEGER"),
       ],
       indexes=[("idx_taint_paths_finding_id", ["finding_id"])],
       foreign_keys=[("finding_id", "findings_consolidated", "id", "CASCADE")]
   )
   ```

3. **Update `base_database.py` writer** - Replace JSON dumps with INSERT to normalized tables

**Task 6: symbols.parameters Normalization**:

1. **Create `symbol_parameters` table in `core_schema.py`**
2. **Update `javascript.py:1288`** - Write to table instead of JSON column
3. **Update `discovery.py:112`** - Read from JOIN instead of json.loads()

**Task 7: Schema Contract Validation** (`schema.py`):

1. **Add JSON blob detector**:
   ```python
   def _detect_json_blobs(tables):
       violations = []
       LEGITIMATE_EXCEPTIONS = {
           ('nodes', 'metadata'),  # graphs.db intentional
           ('edges', 'metadata'),  # graphs.db intentional
           ('plan_documents', 'document_json'),  # legitimate
       }
       for table in tables:
           for col in table.columns:
               if col.type == "TEXT" and col.name.endswith(('_json', 'dependencies', 'parameters')):
                   if (table.name, col.name) not in LEGITIMATE_EXCEPTIONS:
                       violations.append((table.name, col.name))
       return violations
   ```

2. **Add assertion**: `assert len(violations) == 0`

#### **Dependencies**:
- ✅ Must read: `INVESTIGATION_REPORT.md` section 5.1 (FCE findings)
- ✅ Must read: `tasks.md` sections 5.1-5.5, 6.1-6.5, 7.1-7.4 (normalization tasks)
- ✅ Must read: `design.md` sections 5.1-5.3 (normalization design)

#### **Coordination with AI #3**:
- ⚠️ Both touch `javascript.py`
- ✅ AI #4: Line 1288 (parameters write)
- ✅ AI #3: Lines 748-768 (module resolution)
- ✅ Merge strategy: Apply both changes, no overlap

#### **Testing Requirements**:
- ✅ FCE output byte-for-byte identical (except timing)
- ✅ Measure 75-700ms speedup in FCE
- ✅ Schema validator must catch future JSON blob violations

#### **Success Criteria**:
- FCE overhead: 75-700ms eliminated
- Zero JSON TEXT columns (except documented exemptions)
- Future violations caught at schema load time

---

## ⚙️ EXECUTION PROTOCOL

### **Phase 1: Sequential Prerequisite (DO NOT SKIP)**

**ALL 4 AIs must complete verification BEFORE coding**:

1. ✅ Read `INVESTIGATION_REPORT.md` (relevant sections for your AI)
2. ✅ Read `design.md` (relevant sections for your AI)
3. ✅ Read `tasks.md` (relevant sections for your AI)
4. ✅ Read `VERIFICATION_COMPLETE.md` (executive summary)
5. ✅ Verify file paths still valid (use Windows paths: `C:\Users\santa\Desktop\TheAuditor\...`)
6. ✅ Get Architect approval to proceed

**Estimated Time**: 1-2 hours per AI (reading + verification)

---

### **Phase 2: Parallel Implementation**

**TIER 0 (Week 1-2)** - AI #1 and AI #2 work in parallel:
- 🔴 AI #1: Taint refactor (5-6 days)
- 🟠 AI #2: Python AST refactor (5-6 days)

**Status**: Can merge independently (zero file conflicts)

---

**TIER 1 + TIER 1.5 (Week 3-5)** - AI #3 and AI #4 work in parallel:
- 🟡 AI #3: Vue + Module resolution (3-4 days)
- 🟡 AI #4: JSON normalization (3-4 days)

**Status**: 1 file conflict (`javascript.py`) - coordinated by line ranges

**Merge Strategy for `javascript.py`**:
```python
# AI #3 changes (lines 748-768)
def resolve_import(import_path, from_file):
    # New module resolution logic
    ...

# AI #4 changes (line 1288)
def _write_symbols(symbols):
    # Replace JSON dump with normalized table write
    for symbol in symbols:
        params = symbol.get('parameters')
        for idx, param in enumerate(params):
            cursor.execute("""
                INSERT INTO symbol_parameters (symbol_id, param_index, param_name, param_type)
                VALUES (?, ?, ?, ?)
            """, (symbol['id'], idx, param['name'], param['type']))
```

**Conflict Resolution**: Simple - both changes applied, different line ranges ✅

---

**TIER 2 (Week 6-7)** - Any AI can do this:
- 🟢 Database indexes (5 minutes)
- 🟢 GraphQL LIKE fixes (10 minutes)

**Status**: Trivial, done last

---

### **Phase 3: Testing & Validation**

Each AI must verify:
1. ✅ All tests pass (zero regressions)
2. ✅ Fixtures byte-for-byte identical (except timing)
3. ✅ Performance targets met (profiling data)
4. ✅ No security findings lost (taint analysis critical)

---

## 🔒 SAFETY GUARANTEES

### **File Conflict Matrix**

| AI #1 (Taint) | AI #2 (Python AST) | AI #3 (Vue/Module) | AI #4 (JSON Norm) |
|---------------|-------------------|-------------------|-------------------|
| **taint/*.py** | ast_extractors/python/*.py | ast_extractors/javascript/*.js | fce.py |
| **generated_cache.py** | indexer/extractors/python.py | javascript.py (L748-768) | indexer/schemas/core_schema.py |
|               |                   |                   | javascript.py (L1288) |
|               |                   |                   | indexer/schema.py |
|               |                   |                   | indexer/database/*.py |

**Conflicts**: Only `javascript.py` touched by AI #3 + AI #4 (different line ranges) ✅

---

### **Dependency Order**

```
┌─────────────────────────────────────────────┐
│  VERIFICATION PHASE (ALL AIs)               │
│  ✅ Read docs, verify paths, get approval   │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼──────┐     ┌───────▼──────┐
│  AI #1       │     │  AI #2       │
│  Taint       │ ║   │  Python AST  │  ← TIER 0 (parallel, no conflicts)
│  5-6 days    │     │  5-6 days    │
└───────┬──────┘     └───────┬──────┘
        │                     │
        └──────────┬──────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼──────┐     ┌───────▼──────┐
│  AI #3       │     │  AI #4       │
│  Vue/Module  │ ║   │  JSON Norm   │  ← TIER 1/1.5 (parallel, 1 coordinated conflict)
│  3-4 days    │     │  3-4 days    │
└───────┬──────┘     └───────┬──────┘
        │                     │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  TIER 2 (Any AI)    │
        │  Database indexes   │  ← Trivial, 1-2 days
        │  1-2 days           │
        └─────────────────────┘
```

**Merge Points**:
1. **After TIER 0**: Merge AI #1 + AI #2 (zero conflicts)
2. **After TIER 1/1.5**: Merge AI #3 + AI #4 (1 file conflict, coordinated)
3. **After TIER 2**: Final merge (trivial)

---

## 📊 PERFORMANCE IMPACT BY AI

| AI | Subsystem | Impact | Time Saved |
|----|-----------|--------|------------|
| AI #1 | Taint Analysis | 🔴 **CRITICAL** | 540s (95% of total gain) |
| AI #2 | Python AST | 🟠 **HIGH** | 25s (5% of total gain) |
| AI #3 | Vue/Module | 🟡 **MEDIUM** | 6-10s + accuracy |
| AI #4 | JSON Normalization | 🟢 **LOW** | 75-700ms |

**Total**: 16 min → 2-3 min (83-86% faster, 5-8x speedup)

---

## ✅ SUCCESS CRITERIA (ALL AIs)

Each AI must meet these criteria before merging:

1. **Zero Regressions**:
   - ✅ All existing tests pass
   - ✅ Database output byte-for-byte identical (except timing)
   - ✅ No security findings lost (taint analysis critical)

2. **Performance Targets**:
   - ✅ AI #1: Taint 600s → 20-40s (15-30x speedup)
   - ✅ AI #2: Python AST 90s → 12-18s (5-7.5x speedup)
   - ✅ AI #3: Vue 9s → 3s per 100 files, imports 40-60% → 80-90% resolved
   - ✅ AI #4: FCE 75-700ms eliminated

3. **Code Quality**:
   - ✅ Zero fallback logic (hard fail on errors)
   - ✅ Windows-safe paths (absolute paths with drive letters)
   - ✅ No emojis in output (Windows CP1252 encoding)
   - ✅ Follows teamsop.md v4.20 protocols

4. **Documentation**:
   - ✅ Update relevant sections of proposal.md if discrepancies found
   - ✅ Document merge strategy for `javascript.py` conflict

---

## 🚨 CRITICAL WARNINGS

### **⚠️ WARNING 1: Do NOT start coding until verification complete**

Each AI MUST:
1. Read investigation report (relevant sections)
2. Verify file paths still valid
3. Verify line numbers still accurate
4. Get Architect approval

**Skipping this WILL waste days fixing wrong problems.**

---

### **⚠️ WARNING 2: Coordinate javascript.py merge**

AI #3 and AI #4 both touch `javascript.py`:
- AI #3: Lines 748-768 (module resolution)
- AI #4: Line 1288 (parameters normalization)

**Merge Strategy**:
1. AI #3 applies changes to lines 748-768
2. AI #4 applies changes to line 1288 (now line 1308 after AI #3's changes)
3. Both AIs must communicate line number shifts

---

### **⚠️ WARNING 3: TIER 0 is 95% of the impact**

Do NOT skip TIER 0 (AI #1 + AI #2):
- Taint refactor: 540s saved (95% of total gain)
- Python AST refactor: 25s saved (5% of total gain)

TIER 1/1.5/2 are minor compared to TIER 0.

---

## 📞 COMMUNICATION PROTOCOL

**Architect (Human)**: Final authority on:
- Approving verification findings
- Resolving merge conflicts
- Approving each AI's implementation before merge

**Lead Auditor (Gemini AI)**: Quality control:
- Reviews verification findings
- Reviews code changes before merge
- Ensures no regressions

**Lead Coder (Opus AI)**: Typically assigned to AI #1 (most complex)

---

## 📚 REQUIRED READING (BY AI)

### **AI #1 (Taint)** must read:
1. `INVESTIGATION_REPORT.md` sections 2.1-2.4 (taint findings)
2. `design.md` section 2.1 (spatial index design)
3. `tasks.md` sections 1.1-1.4 (taint implementation)
4. `VERIFICATION_COMPLETE.md` (executive summary)

### **AI #2 (Python AST)** must read:
1. `INVESTIGATION_REPORT.md` sections 1.1-1.3 (Python AST findings)
2. `design.md` section 1.1 (single-pass visitor design)
3. `tasks.md` sections 2.1-2.7 (Python AST implementation)
4. `VERIFICATION_COMPLETE.md` (executive summary)

### **AI #3 (Vue/Module)** must read:
1. `INVESTIGATION_REPORT.md` sections 4.1-4.2 (JavaScript findings)
2. `design.md` sections 3.1-3.2 (Vue + module resolution design)
3. `tasks.md` sections 3.1-3.4, 4.1-4.5 (Vue + module implementation)
4. `VERIFICATION_COMPLETE.md` (executive summary)

### **AI #4 (JSON Normalization)** must read:
1. `INVESTIGATION_REPORT.md` section 5.1 (FCE findings)
2. `design.md` sections 5.1-5.3 (normalization design)
3. `tasks.md` sections 5.1-5.5, 6.1-6.5, 7.1-7.4 (normalization implementation)
4. `VERIFICATION_COMPLETE.md` (executive summary)

---

## 🎯 FINAL RECOMMENDATION

**Parallelization Strategy**: ✅ **APPROVED FOR EXECUTION**

**Safety Level**: 100% SAFE with defined file boundaries

**Expected Outcome**: 4-7 weeks → 3-6 weeks (40% time savings with 4 AIs)

**Risk Level**: 🟢 **LOW** - Only 1 file conflict with coordinated line ranges

---

**Last Updated**: 2025-11-03

**Verified By**: 12-agent comprehensive audit (VERIFICATION_COMPLETE.md)

**Status**: 🟢 **READY FOR PARALLEL EXECUTION** - Awaiting Architect approval
