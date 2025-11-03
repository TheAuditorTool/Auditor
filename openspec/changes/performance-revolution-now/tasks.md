# Performance Revolution Implementation Tasks

**CRITICAL**: Do NOT start implementation until:
1. ✅ Architect approves `proposal.md`
2. ✅ Verification phase completed (see `verification.md`)
3. ✅ Architect approves verification findings

---

## 0. Verification Phase (MANDATORY - Complete Before Coding)

**Objective**: Verify all assumptions from INVESTIGATION_REPORT.md by reading actual code

- [ ] 0.1 **Read Investigation Report** - Fully digest INVESTIGATION_REPORT.md
- [ ] 0.2 **Read Design Document** - Understand architectural decisions in `design.md`
- [ ] 0.3 **Execute Verification Protocol** - Follow `verification.md` step-by-step
- [ ] 0.4 **Document Findings** - Record all discrepancies in `verification.md`
- [ ] 0.5 **Get Architect Approval** - Architect must approve verification before continuing

**Status**: ⚠️ **BLOCKING** - No implementation may proceed until this section is checked

---

## TIER 0 - EMERGENCY (Target: Week 1-2)

### 1. Taint Analysis Spatial Index Refactor

**Objective**: Eliminate 165M-20B operations (depending on recursion depth) → 1 MILLION (100-1000x reduction)

**Estimated Time**: 3-4 days implementation + 1-2 days testing

#### 1.1 Add Spatial Indexes to SchemaMemoryCache
- [ ] 1.1.1 Read `theauditor/indexer/schemas/generated_cache.py`
  - Verify current cache structure
  - Confirm no existing spatial indexes
- [ ] 1.1.2 Design spatial index data structures
  - `symbols_by_type: Dict[str, List[Dict]]`
  - `symbols_by_file_line: Dict[str, Dict[int, List[Dict]]]`
  - `assignments_by_location: Dict[str, Dict[int, List[Dict]]]` (file → line_block → assignments)
  - `calls_by_location: Dict[str, Dict[int, List[Dict]]]` (file → line_block → calls)
  - `successors_by_block: Dict[str, List[Dict]]` (block_id → successor_blocks)
  - `blocks_by_id: Dict[str, Dict]` (block_id → block)
- [ ] 1.1.3 Implement index builders in `generated_cache.py`
  - Add `_build_spatial_indexes()` method
  - Call from `__init__` after loading base data
  - Use 100-line block grouping for line-based lookups
- [ ] 1.1.4 Add unit tests for index builders
  - Test symbols_by_type with fixture data
  - Test spatial lookup correctness
  - Test edge cases (empty files, missing blocks)

#### 1.2 Refactor Discovery Phase (discovery.py)
- [ ] 1.2.1 Read `theauditor/taint/discovery.py:52-84`
  - Verify current linear scan pattern
  - Identify all source/sink discovery loops
- [ ] 1.2.2 Replace user input source discovery (lines 52-67)
  - BEFORE: `for symbol in self.cache.symbols if type == 'property'`
  - AFTER: `for symbol in self.cache.symbols_by_type.get('property', [])`
- [ ] 1.2.3 Replace file read source discovery (lines 70-84)
  - Use frozenset lookups instead of `if 'readFile' in func_name`
  - Pre-compile FILE_READ_FUNCTIONS = frozenset([...])
- [ ] 1.2.4 Replace command injection sink discovery (lines 163-177)
  - Use indexed lookup by callee_function
- [ ] 1.2.5 Measure speedup with profiling
  - Before: ~500K operations
  - After: ~1K operations (500x improvement expected)

#### 1.3 Refactor Analysis Phase (analysis.py)
- [ ] 1.3.1 Read `theauditor/taint/analysis.py:187-195`
  - Verify `_get_containing_function` linear scan
  - Confirm called once per source (~1,000 times)
- [ ] 1.3.2 Replace `_get_containing_function` with spatial index
  - BEFORE: `for symbol in self.cache.symbols if type == 'function' and line in range(...)`
  - AFTER: Use `symbols_by_file_line[file][line_block]` lookup
  - Expected: 100M comparisons → 1K lookups (100,000x improvement)
- [ ] 1.3.3 Read `theauditor/taint/analysis.py:245-249`
  - Verify `_propagate_through_block` full-table scan
- [ ] 1.3.4 Replace `_propagate_through_block` with spatial index
  - BEFORE: `for a in self.cache.assignments if file == block.file and line in range(...)`
  - AFTER: Use `assignments_by_location[file][line_block]`
  - Expected: 500M comparisons → 500K lookups (1,000x improvement)
- [ ] 1.3.5 Read `theauditor/taint/analysis.py:267-270`
  - Verify `_get_calls_in_block` full-table scan
- [ ] 1.3.6 Replace `_get_calls_in_block` with spatial index
  - BEFORE: `for c in self.cache.function_call_args if file == block.file and line in range(...)`
  - AFTER: Use `calls_by_location[file][line_block]`
  - Expected: 500M comparisons → 500K lookups (1,000x improvement)
- [ ] 1.3.7 Read `theauditor/taint/analysis.py:284-292`
  - Verify `_get_block_successors` O(n²) nested loop
- [ ] 1.3.8 Replace `_get_block_successors` with adjacency list
  - BEFORE: `for edge in edges: for block in blocks if block.id == edge.to_block`
  - AFTER: `return self.cache.successors_by_block[block_id]`
  - Expected: 50M comparisons → O(1) lookups (50M× improvement)

#### 1.4 Refactor Propagation Phase (propagation.py)
- [ ] 1.4.1 Read `theauditor/taint/propagation.py:224-232`
  - Verify LIKE wildcard pattern: `source_expr LIKE '%{pattern}%'`
  - Confirm called ~1,000 times (once per source)
- [ ] 1.4.2 Replace LIKE wildcard with indexed pre-filter
  - BEFORE: `WHERE file = ? AND line BETWEEN ? AND ? AND source_expr LIKE '%pattern%'`
  - AFTER: `WHERE file = ? AND line BETWEEN ? AND ?` (then Python filter)
  - Filter in Python: `if source['pattern'] in row['source_expr']`
  - Expected: 50M rows scanned → 500K rows scanned (100x improvement)
- [ ] 1.4.3 Read `theauditor/taint/propagation.py:254-262`
  - Verify duplicate LIKE pattern in function_call_args query
- [ ] 1.4.4 Apply same fix as 1.4.2 for function_call_args

#### 1.5 Batch Load CFG Statements
- [ ] 1.5.1 Read `theauditor/taint/cfg_integration.py.bak:295-300`
  - Verify N+1 query pattern (query per CFG block)
  - Confirm called ~100 times per path (~10,000 total queries)
- [ ] 1.5.2 Add batch load to `SchemaMemoryCache.__init__`
  - Load all cfg_block_statements for function upfront
  - Store in `statements_by_block: Dict[str, List[Dict]]`
- [ ] 1.5.3 Replace per-block queries with cache lookup
  - BEFORE: `cursor.execute("SELECT ... WHERE block_id = ?")` (10,000 queries)
  - AFTER: `statements = self.cache.statements_by_block[block_id]` (1 query)
  - Expected: 10,000 queries → 1 query (10,000x improvement)

#### 1.6 Testing & Validation
- [ ] 1.6.1 Run existing taint analysis tests
  - `pytest tests/test_taint*.py -v`
  - All tests must pass (no regressions)
- [ ] 1.6.2 Run fixture-based validation
  - Test on 5 fixture projects (Python, JS, mixed)
  - Compare taint findings before/after (must match exactly)
- [ ] 1.6.3 Performance benchmarking
  - Measure taint analysis time on 10K LOC project
  - Before: ~10 minutes expected
  - After: ~30 seconds target
  - Document actual speedup in verification.md
- [ ] 1.6.4 Memory profiling
  - Measure memory usage before/after
  - Spatial indexes add ~10-20MB (acceptable)
  - Confirm no memory leaks

---

### 2. Python AST Single-Pass Visitor Refactor

**Objective**: Eliminate 80 AST traversals per file → 1 traversal (80x reduction)

**Estimated Time**: 4-6 days implementation + 2-3 days testing

#### 2.1 Design Unified Visitor Architecture
- [ ] 2.1.1 Read all Python extractors to understand patterns
  - `theauditor/ast_extractors/python/framework_extractors.py` (19 walks)
  - `theauditor/ast_extractors/python/core_extractors.py` (19 walks)
  - `theauditor/ast_extractors/python/flask_extractors.py` (10 walks)
  - `theauditor/ast_extractors/python/async_extractors.py` (9 walks)
  - `theauditor/ast_extractors/python/security_extractors.py` (8 walks)
  - `theauditor/ast_extractors/python/testing_extractors.py` (8 walks)
  - `theauditor/ast_extractors/python/type_extractors.py` (5 walks)
  - Document all extraction patterns in design.md
- [ ] 2.1.2 Design `UnifiedPythonVisitor` class structure
  - Inherits from `ast.NodeVisitor`
  - Properties for each extractor category (models, routes, validators, etc.)
  - Visit methods: `visit_ClassDef`, `visit_FunctionDef`, `visit_Import`, etc.
- [ ] 2.1.3 Create framework detection helpers
  - `_is_sqlalchemy_model(node)` → bool
  - `_is_django_model(node)` → bool
  - `_is_flask_route(node)` → bool
  - `_is_pydantic_schema(node)` → bool
  - Use frozensets for base class matching (not `.endswith()`)

#### 2.2 Implement UnifiedPythonVisitor (Core)
- [ ] 2.2.1 Create `theauditor/ast_extractors/python/unified_visitor.py`
  - 800-1000 lines estimated
  - Class definition with __init__
  - Result collection properties (self.functions, self.classes, etc.)
- [ ] 2.2.2 Implement `visit_ClassDef(self, node)`
  - Check SQLAlchemy models → extract to self.sqlalchemy_models
  - Check Django models → extract to self.django_models
  - Check Pydantic schemas → extract validators to self.validators
  - Check Django forms → extract to self.django_forms
  - Extract generic class data → self.classes
  - Call `self.generic_visit(node)` to continue traversal
- [ ] 2.2.3 Implement `visit_FunctionDef(self, node)`
  - Check Flask routes (decorator matching) → self.flask_routes
  - Check FastAPI routes → self.fastapi_routes
  - Check Celery tasks → self.celery_tasks
  - Check pytest fixtures → self.pytest_fixtures
  - Extract generic function data → self.functions
  - Call `self.generic_visit(node)`
- [ ] 2.2.4 Implement `visit_Import(self, node)`
  - Extract import statements → self.imports
  - Call `self.generic_visit(node)`
- [ ] 2.2.5 Implement `visit_ImportFrom(self, node)`
  - Extract from-import statements → self.imports
  - Call `self.generic_visit(node)`
- [ ] 2.2.6 Implement `visit_Assign(self, node)`
  - Extract assignments → self.assignments
  - Check for JWT patterns → self.jwt_patterns
  - Call `self.generic_visit(node)`
- [ ] 2.2.7 Implement `visit_Call(self, node)`
  - Extract function calls → self.calls
  - Call `self.generic_visit(node)`

#### 2.3 Migrate Framework Extractors to Visitor
- [ ] 2.3.1 Migrate SQLAlchemy extraction
  - Move logic from `framework_extractors.py:215-400` to `visit_ClassDef`
  - Test on SQLAlchemy fixture project
  - Verify extracted models match original extractor output
- [ ] 2.3.2 Migrate Django extraction
  - Move logic from `framework_extractors.py:416-906` to `visit_ClassDef`
  - Test on Django fixture project
- [ ] 2.3.3 Migrate Flask extraction
  - Move logic from `flask_extractors.py:124-400` to `visit_FunctionDef`
  - **CRITICAL**: Eliminate nested `ast.walk()` at line 138
  - Test on Flask fixture project
- [ ] 2.3.4 Migrate FastAPI extraction
  - Move dependency injection logic to `visit_FunctionDef`
  - Test on FastAPI fixture project
- [ ] 2.3.5 Migrate Pydantic extraction
  - Move validator detection to `visit_ClassDef`
  - Test on Pydantic fixture project
- [ ] 2.3.6 Migrate remaining extractors (Celery, pytest, async, security, types)
  - Incremental migration one extractor at a time
  - Test each with fixtures

#### 2.4 Update Orchestrator to Use Unified Visitor
- [ ] 2.4.1 Read `theauditor/indexer/extractors/python.py:243-434`
  - Verify current orchestration (70+ separate extractor calls)
- [ ] 2.4.2 Replace with unified visitor call
  - BEFORE: 70+ lines of `framework_extractors.extract_X(tree)`
  - AFTER: 10 lines: `visitor = UnifiedPythonVisitor(); visitor.visit(tree); return visitor.get_results()`
- [ ] 2.4.3 Implement `visitor.get_results()` method
  - Returns dict with all extracted data
  - Maps to existing result structure (backward compatible)

#### 2.5 Optimize String Operations
- [ ] 2.5.1 Replace `.endswith()` checks with frozenset lookups
  - Create module-level frozensets for framework base classes
  - SQLALCHEMY_BASE_IDENTIFIERS = frozenset(['Base', 'DeclarativeBase', ...])
  - Use `in` operator instead of `.endswith()`
- [ ] 2.5.2 Cache `get_node_name()` results
  - Don't call `get_node_name()` multiple times on same node
  - Store result in variable, reuse in if/elif chains

#### 2.6 Testing & Validation
- [ ] 2.6.1 Unit test UnifiedPythonVisitor
  - Test each `visit_*` method independently
  - Verify extraction correctness with minimal AST trees
- [ ] 2.6.2 Fixture-based validation
  - Run on 20 Python fixture projects (all framework types)
  - Compare database contents before/after (must match exactly)
  - Use SQL diff tool to verify no regressions
- [ ] 2.6.3 Performance benchmarking
  - Measure indexing time on 1,000 Python files
  - Before: ~30 seconds expected (80 walks)
  - After: ~5 seconds target (1 walk)
  - Document actual speedup
- [ ] 2.6.4 Edge case testing
  - Empty files
  - Syntax errors (visitor should handle gracefully)
  - Very large files (10,000+ LOC)
  - Deeply nested structures

---

## TIER 1 - HIGH PRIORITY (Target: Week 3-6)

### 3. Vue In-Memory Compilation Optimization

**Objective**: Eliminate disk I/O overhead (35-95ms → 10-20ms per .vue file)

**Estimated Time**: 4-6 hours

- [ ] 3.1 Read `theauditor/extractors/js/batch_templates.js:119-175`
  - Verify current Vue SFC compilation flow
  - Confirm disk I/O pattern (writeFileSync → TypeScript → unlinkSync)
- [ ] 3.2 Research TypeScript API for in-memory compilation
  - Verify `ts.createSourceFile(filename, content, ...)` accepts string content
  - Confirm no file path dependency
- [ ] 3.3 Refactor `prepareVueSfcFile()` for in-memory compilation
  - BEFORE: `fs.writeFileSync(tempPath, compiled); ts.createSourceFile(tempPath); fs.unlinkSync(tempPath)`
  - AFTER: `ts.createSourceFile(virtualPath, compiled.content, ...)`
  - Use virtual path (e.g., `/virtual/${scopeId}.js`)
- [ ] 3.4 Test on Vue fixture projects
  - Verify extraction output matches original
  - Measure speedup (expect 60-80% reduction)
- [ ] 3.5 Test edge cases
  - Vue 2 vs Vue 3 SFC syntax
  - `<script setup>` with TypeScript
  - Empty `<script>` blocks

---

### 4. Node Module Resolution Implementation

**Objective**: Resolve 40-60% more imports (critical for cross-file taint)

**Estimated Time**: 1-2 weeks

- [ ] 4.1 Research TypeScript module resolution algorithm
  - Read TypeScript source: `moduleNameResolver.ts`
  - Understand Node.js resolution (node_modules, package.json exports)
- [ ] 4.2 Read `theauditor/indexer/extractors/javascript.py:748-768`
  - Verify current simplistic basename extraction
  - Identify gaps (relative imports, path mappings, node_modules)
- [ ] 4.3 Implement relative import resolution
  - Handle `./utils/validation` → `src/utils/validation.ts`
  - Handle `../config` → `src/config.ts`
  - Respect file extensions (.js, .ts, .tsx, .jsx)
- [ ] 4.4 Implement tsconfig.json path mapping support
  - Parse tsconfig.json "paths" field
  - Map `@/utils` → `src/utils`
  - Map `~components` → `src/components`
- [ ] 4.5 Implement node_modules resolution
  - Resolve `lodash` → `node_modules/lodash/index.js`
  - Respect package.json "exports" field
  - Handle scoped packages `@types/react`
- [ ] 4.6 Add caching for resolved modules
  - Cache: `(import_path, from_file) → resolved_path`
  - Avoid re-resolving same import multiple times
- [ ] 4.7 Testing
  - Test on 10 TypeScript projects with various import styles
  - Measure import resolution rate before/after
  - Target: 40-60% more imports resolved

---

## TIER 1.5 - JSON BLOB NORMALIZATION (Target: Week 3-5, PARALLEL with TIER 1)

**PARALLEL-SAFE**: Can run concurrently with TIER 1 (different files, minimal overlap)

**CRITICAL NOTE**: This tier reverses the exemption granted in commit d8370a7 (Oct 23, 2025) which labeled findings_consolidated.details_json as "Intentional findings metadata storage". Measured FCE overhead (75-700ms, with taint paths at 50-500ms) justifies normalization.

### 5. FCE findings_consolidated.details_json Normalization

**Objective**: Eliminate 75-700ms FCE overhead (7 json.loads() calls at lines 60, 78, 127, 168, 207, 265, 401)

**Estimated Time**: 2-3 days implementation + 1 day testing

**PARALLEL-SAFE**: Different files from TIER 1

#### 5.1 Audit Current details_json Usage
- [ ] 5.1.1 Read `theauditor/fce.py:60-401`
  - Identify all 7 json.loads() calls
  - Line 60: Hotspots (5-50 items, ~5-10ms)
  - Line 78: Cycles (0-20 items, ~5-10ms)
  - Line 127: CFG complexity (10-100 items, ~10-20ms)
  - Line 168: Code churn (50-500 files, ~20-50ms)
  - Line 207: Test coverage (100-1K files, ~30-100ms)
  - Line 265: **CRITICAL** - Taint paths (100-10K paths at 1KB+ each, **50-500ms**)
  - Line 401: Additional metadata
  - Document structure of each JSON payload
- [ ] 5.1.2 Read `theauditor/indexer/database/base_database.py:~600`
  - Locate details_json write for findings_consolidated
  - Verify all tools writing details_json (vuln scanner, taint, graph, CFG)
- [ ] 5.1.3 Measure baseline FCE performance
  - Run FCE on test project with 1,000 findings
  - Profile json.loads() overhead with cProfile
  - Target: 75-700ms total, 50-500ms for taint paths

#### 5.2 Design Normalized Schema
- [ ] 5.2.1 Create `finding_taint_paths` table
  ```python
  FINDING_TAINT_PATHS = TableSchema(
      name="finding_taint_paths",
      columns=[
          Column("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
          Column("finding_id", "TEXT", nullable=False),  # FK to findings_consolidated
          Column("path_index", "INTEGER", nullable=False),  # Order within finding
          Column("source_file", "TEXT"),
          Column("source_line", "INTEGER"),
          Column("source_expr", "TEXT"),
          Column("sink_file", "TEXT"),
          Column("sink_line", "INTEGER"),
          Column("sink_expr", "TEXT"),
          Column("path_length", "INTEGER"),
          Column("confidence", "REAL"),
      ],
      indexes=[
          ("idx_finding_taint_paths_finding_id", ["finding_id"]),
          ("idx_finding_taint_paths_composite", ["finding_id", "path_index"]),
      ],
      foreign_keys=[
          ("finding_id", "findings_consolidated", "id", "CASCADE"),
      ]
  )
  ```
- [ ] 5.2.2 Create `finding_graph_hotspots` table
  ```python
  FINDING_GRAPH_HOTSPOTS = TableSchema(
      name="finding_graph_hotspots",
      columns=[
          Column("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
          Column("finding_id", "TEXT", nullable=False),
          Column("function_name", "TEXT"),
          Column("file", "TEXT"),
          Column("line", "INTEGER"),
          Column("in_degree", "INTEGER"),
          Column("out_degree", "INTEGER"),
          Column("betweenness", "REAL"),
      ],
      indexes=[
          ("idx_finding_graph_hotspots_finding_id", ["finding_id"]),
      ],
      foreign_keys=[
          ("finding_id", "findings_consolidated", "id", "CASCADE"),
      ]
  )
  ```
- [ ] 5.2.3 Create `finding_cfg_complexity` table (CFG metrics)
- [ ] 5.2.4 Create `finding_metadata` table (churn, coverage, vuln CWEs/CVEs)

#### 5.3 Update Database Writers
- [ ] 5.3.1 Modify `theauditor/indexer/database/base_database.py`
  - Remove details_json from findings_consolidated INSERT
  - Add methods: `write_finding_taint_paths()`, `write_finding_metadata()`
- [ ] 5.3.2 Update taint writer in `theauditor/taint/analysis.py`
  - After writing finding to findings_consolidated
  - Write taint paths to finding_taint_paths table (batch INSERT)
- [ ] 5.3.3 Update graph writer in `theauditor/graph/store.py`
  - Write hotspots to finding_graph_hotspots table
- [ ] 5.3.4 Update CFG writer (complexity metrics)
- [ ] 5.3.5 Update vulnerability_scanner.py (CWE/CVE to finding_metadata)

#### 5.4 Update FCE Queries
- [ ] 5.4.1 Replace json.loads() at line 60 (hotspots)
  ```python
  # BEFORE:
  # details = json.loads(details_json)
  # hotspots = details.get('hotspots', [])

  # AFTER:
  # cursor.execute("""
  #     SELECT function_name, file, line, in_degree, out_degree
  #     FROM finding_graph_hotspots
  #     WHERE finding_id = ?
  # """, (finding_id,))
  # hotspots = cursor.fetchall()
  ```
- [ ] 5.4.2 Replace json.loads() at line 265 (taint paths - **CRITICAL BOTTLENECK**)
  ```python
  # BEFORE:
  # path_data = json.loads(details_json)  # 50-500ms for 100-10K paths
  # taint_paths = path_data.get('paths', [])

  # AFTER:
  # cursor.execute("""
  #     SELECT source_file, source_line, source_expr,
  #            sink_file, sink_line, sink_expr, confidence
  #     FROM finding_taint_paths
  #     WHERE finding_id = ?
  #     ORDER BY path_index
  # """, (finding_id,))
  # taint_paths = cursor.fetchall()  # O(1) indexed lookup
  ```
- [ ] 5.4.3 Replace remaining 6 json.loads() calls (cycles, CFG, churn, coverage, vuln)

#### 5.5 Testing & Validation
- [ ] 5.5.1 Run fixture validation
  - Test on 10 projects with known taint findings
  - Verify FCE output matches original (functionally equivalent)
- [ ] 5.5.2 Performance benchmarking
  - Measure FCE time before/after
  - Before: 75-700ms overhead
  - After: <10ms overhead (90%+ improvement)
- [ ] 5.5.3 Verify taint path correctness
  - Critical: Ensure path_index ordering preserved
  - Critical: Ensure no data loss in normalization

---

### 6. symbols.parameters Normalization

**Objective**: Eliminate duplicate JSON parsing in taint/discovery.py + extractors/javascript.py

**Estimated Time**: 1 day implementation + 1 day testing

**PARALLEL-SAFE**: Different files from TIER 1 (except javascript.py line 1288 vs TIER 1 lines 748-768)

#### 6.1 Audit Current Usage
- [ ] 6.1.1 Read `theauditor/taint/discovery.py:112`
  - Verify JSON parsing: `params = json.loads(symbol.get('parameters', '[]'))`
  - Used for taint source discovery
- [ ] 6.1.2 Read `theauditor/indexer/extractors/javascript.py:1288`
  - Verify duplicate parsing of same column
  - **COORDINATE with TIER 1**: Different line (1288 vs 748-768), safe to work in parallel

#### 6.2 Create Normalized Schema
- [ ] 6.2.1 Create `symbol_parameters` table
  ```python
  SYMBOL_PARAMETERS = TableSchema(
      name="symbol_parameters",
      columns=[
          Column("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
          Column("symbol_id", "TEXT", nullable=False),  # FK to symbols.id
          Column("param_index", "INTEGER", nullable=False),
          Column("param_name", "TEXT"),
          Column("param_type", "TEXT"),
          Column("default_value", "TEXT"),
          Column("is_optional", "INTEGER"),  # 0 or 1
      ],
      indexes=[
          ("idx_symbol_parameters_symbol_id", ["symbol_id"]),
          ("idx_symbol_parameters_composite", ["symbol_id", "param_index"]),
      ],
      foreign_keys=[
          ("symbol_id", "symbols", "id", "CASCADE"),
      ]
  )
  ```
- [ ] 6.2.2 Verify pattern matches commit d8370a7 junction table style
  - AUTOINCREMENT on id
  - Composite index on (symbol_id, param_index)
  - CASCADE foreign key

#### 6.3 Update Extractors
- [ ] 6.3.1 Modify Python extractor to write to symbol_parameters
  - After writing symbol to symbols table
  - Batch INSERT parameters to symbol_parameters
- [ ] 6.3.2 Modify JavaScript extractor (same pattern)
- [ ] 6.3.3 Remove symbols.parameters column writes
  - Mark column as deprecated (or remove if safe)

#### 6.4 Update Consumers
- [ ] 6.4.1 Replace taint/discovery.py:112
  ```python
  # BEFORE:
  # params = json.loads(symbol.get('parameters', '[]'))

  # AFTER:
  # cursor.execute("""
  #     SELECT param_name, param_type
  #     FROM symbol_parameters
  #     WHERE symbol_id = ?
  #     ORDER BY param_index
  # """, (symbol['id'],))
  # params = cursor.fetchall()
  ```
- [ ] 6.4.2 Replace javascript.py:1288 (same pattern)

#### 6.5 Testing
- [ ] 6.5.1 Verify extraction parity
  - Test on 100 Python/JS files
  - Verify parameters extracted correctly
- [ ] 6.5.2 Verify taint discovery works
  - Test on fixture with known parameter-based taint sources

---

### 7. Schema Contract Validation Enhancement

**Objective**: Prevent future "3rd refactor" by catching violations at schema load time

**Estimated Time**: 1-2 days implementation + 1 day testing

**PARALLEL-SAFE**: Only touches indexer/schema.py

#### 8.1 Add JSON Blob Detector
- [ ] 8.1.1 Read `theauditor/indexer/schema.py:78`
  - Current assertion: `assert len(TABLES) == 154`
  - Only validates table count, not structure
- [ ] 8.1.2 Implement JSON blob detector
  ```python
  def _detect_json_blobs(tables):
      """Detect TEXT columns that should be normalized."""
      violations = []
      LEGITIMATE_EXCEPTIONS = {
          # graphs.db intentional denormalization (documented)
          ('nodes', 'metadata'),
          ('edges', 'metadata'),
          # Planning documents (legitimate JSON storage)
          ('plan_documents', 'document_json'),
          # ... (see verification.md for full list)
      }
      for table in tables:
          for col in table.columns:
              if col.type == "TEXT" and col.name.endswith(('_json', 'dependencies', 'parameters')):
                  if (table.name, col.name) not in LEGITIMATE_EXCEPTIONS:
                      violations.append((table.name, col.name))
      return violations
  ```
- [ ] 8.1.3 Add assertion in schema.py
  ```python
  json_violations = _detect_json_blobs(TABLES)
  assert len(json_violations) == 0, f"JSON blob violations detected: {json_violations}. Normalize to junction tables with AUTOINCREMENT."
  ```

#### 8.2 Add Junction Table Validator
- [ ] 8.2.1 Implement AUTOINCREMENT checker
  ```python
  def _validate_junction_tables(tables):
      """Ensure junction tables follow d8370a7 pattern."""
      violations = []
      for table in tables:
          if table.name.endswith(('_deps', '_dependencies', '_params', '_fields', '_hooks')):
              # Junction table pattern expected
              if not table.columns[0].name == 'id':
                  violations.append((table.name, 'Missing id column'))
              if 'AUTOINCREMENT' not in table.columns[0].type:
                  violations.append((table.name, 'Missing AUTOINCREMENT on id'))
      return violations
  ```
  - Note: Existing junction tables already have INTEGER PRIMARY KEY (which implies AUTOINCREMENT in SQLite)
  - This validator is for catching future violations in new tables

#### 8.3 Add Write Path Validator (Optional)
- [ ] 8.3.1 Audit all json.dumps() calls
  - Current count: 28 calls across database writers
  - Verify each has corresponding normalized table
- [ ] 8.3.2 Add runtime warning (if json.dumps() detected on non-exempt column)
  - Log warning: "JSON write detected on {table}.{column} - consider normalizing"

#### 8.4 Testing
- [ ] 8.4.1 Test schema load with violations
  - Temporarily add a JSON blob column
  - Verify assertion fires
- [ ] 8.4.2 Test legitimate exceptions pass
  - Verify graphs.db metadata columns exempted
  - Verify plan_documents exempted
- [ ] 8.4.3 Test junction table validator
  - Verify 3 fixed tables pass
  - Verify would catch future violations

---

## TIER 2 - MEDIUM PRIORITY (Target: Week 7)

### 9. Add Missing Database Indexes

**Objective**: 120ms saved per run (trivial change, free performance)

**Estimated Time**: 5 minutes

- [ ] 5.1 Read `theauditor/indexer/schemas/core_schema.py`
  - Locate FUNCTION_CALL_ARGS schema definition
- [ ] 5.2 Add index on argument_index
  ```python
  ("idx_function_call_args_argument_index", ["argument_index"])
  ```
- [ ] 5.3 Add index on param_name (optional, lower priority)
  ```python
  ("idx_function_call_args_param_name", ["param_name"])
  ```
- [ ] 5.4 Test index creation
  - Run `aud index` on test project
  - Verify indexes created in repo_index.db
  - Query: `SELECT name FROM sqlite_master WHERE type='index'`
- [ ] 5.5 Benchmark query speedup
  - Before: 9.82ms (unindexed)
  - After: <0.5ms (indexed)

---

### 10. Fix GraphQL LIKE Patterns

**Objective**: Clean up minor query anti-patterns (<500ms impact)

**Estimated Time**: 30 minutes

- [ ] 10.1 Read `theauditor/rules/graphql/injection.py:103`
  - Verify LIKE pattern: `argument_expr LIKE '%{arg}%'`
- [ ] 10.2 Replace with indexed pre-filter + Python search
  - BEFORE: `WHERE argument_expr LIKE '%{arg}%'`
  - AFTER: `WHERE file = ? AND line BETWEEN ? AND ?` (Python filter: `if arg in expr`)
- [ ] 10.3 Read `theauditor/rules/graphql/input_validation.py:38`
  - Verify LIKE pattern: `arg_type LIKE '%String%'`
- [ ] 10.4 Replace with Python filter
  - BEFORE: `WHERE arg_type LIKE '%String%' OR arg_type LIKE 'Input%'`
  - AFTER: `WHERE type_name = 'Mutation' AND is_nullable = 1` (Python filter: `if 'String' in arg_type or arg_type.startswith('Input')`)
- [ ] 10.5 Test on GraphQL fixture projects
  - Verify findings unchanged

---

## 11. Documentation & Deployment

- [ ] 11.1 Update CLAUDE.md with performance patterns
  - Add "Single-Pass Visitor Pattern" section
  - Add "Spatial Index Pattern" section
  - Add "JSON Normalization Pattern" section (commit d8370a7 style)
  - Document anti-patterns to avoid
- [ ] 11.2 Update README with new performance metrics
  - Indexing: 90s → 12-18s
  - Taint: 10 min → 30s
  - FCE: 75-700ms → <10ms
- [ ] 11.3 Write CHANGELOG.md entry
  - Document breaking changes (database schema changes in TIER 1.5)
  - Document performance improvements
- [ ] 11.4 Create migration guide
  - **TIER 1.5 REQUIRES** `aud full` to regenerate database
  - Document new normalized tables
- [ ] 11.5 Performance regression tests
  - Add benchmark tests to CI
  - Fail if performance degrades >20%
- [ ] 11.6 Archive OpenSpec change
  - Run `openspec archive performance-revolution-now --yes`
  - Update specs/performance-optimization/spec.md

---

## Task Status Legend

- [ ] **Pending** - Not started
- [▶] **In Progress** - Currently working
- [x] **Completed** - Done and verified
- [⚠] **Blocked** - Waiting on dependency
- [❌] **Failed** - Attempted but failed (requires resolution)

---

## Completion Checklist (Final Verification)

Before marking this change as complete:

- [ ] All TIER 0 tasks completed and tested (sections 1-2)
- [ ] All TIER 1 tasks completed and tested (sections 3-4)
- [ ] All TIER 1.5 tasks completed and tested (sections 5-8, PARALLEL-SAFE with TIER 1)
- [ ] All TIER 2 tasks completed and tested (sections 9-10)
- [ ] Performance targets met (measured and documented):
  - Indexing: 90s → ≤18s
  - Taint: 600s → ≤40s
  - FCE: 75-700ms → ≤10ms
- [ ] All tests passing (no regressions)
- [ ] Fixtures validated (byte-for-byte output match)
- [ ] Memory usage within 10% of baseline
- [ ] Architect final approval
- [ ] Documentation updated
- [ ] Change archived

---

**Current Status**: 🔴 **VERIFICATION PHASE** - Complete verification.md before starting implementation

**Estimated Total Time**: 4-7 weeks sequential, 3-6 weeks if TIER 1 and TIER 1.5 executed in parallel

**Parallelization Note**: TIER 1.5 can run concurrently with TIER 1 (different files, one merge conflict on javascript.py coordinated by line ranges)
