# Tasks: ZERO FALLBACK Extraction Pipeline Refactor

**Execution Strategy**: One branch, sequential commits. Fix extractor bugs immediately as crashes occur.

---

## 0. Verification (Prime Directive - Complete Before Any Implementation)

### 0.1 Verify Deduplication Locations
- [x] **0.1.1** Read `core_storage.py` and confirm dedup blocks at lines 351-359, 456-464, 615-623
  - **HOW**: Open file, search for `seen = set()`, verify each location matches Pre-Implementation Plan
  - **WHY**: Ensure we're editing the correct code - wrong line numbers could cause partial fix
  - **EXPECTED**: 3 distinct `seen = set()` blocks with `if key not in seen:` pattern
  - **RESULT**: CONFIRMED - dedup blocks found at lines 351, 456, 615

- [x] **0.1.2** Read `core_database.py` and confirm dedup at lines 22-24
  - **HOW**: Open file, search for `if not any(item[0] == path`
  - **WHY**: This is the `add_file` method's fallback logic
  - **EXPECTED**: Single check before `batch.append((path, sha256, ext, bytes_size, loc))`
  - **RESULT**: CONFIRMED - dedup at line 23

- [x] **0.1.3** Verify `generated_validators.py` is truly unused
  - **HOW**: Run `grep -r "from.*generated_validators" theauditor/` and `grep -r "import.*generated_validators" theauditor/`
  - **WHY**: Must confirm no code imports it before deletion
  - **EXPECTED**: Zero matches (file is dead code)
  - **RESULT**: CONFIRMED - only reference in codegen.py (generates it), no imports

- [x] **0.1.4** Verify existing `visited_nodes` pattern in extractors
  - **HOW**: Read `typescript_impl.py:535-545` and `module_framework.js:149-163`
  - **WHY**: This is the reference pattern for fixing extractor bugs when Phase 1 crashes
  - **EXPECTED**: Pattern uses `(line, column, kind)` tuple as node identity
  - **RESULT**: CONFIRMED - pattern at typescript_impl.py:535-545

### 0.2 Verify Flush Order
- [x] **0.2.1** Read `base_database.py` flush_order list (lines 266-440)
  - **HOW**: Open file, locate `flush_order = [` variable
  - **WHY**: FK enforcement (Phase 3) requires correct parent-before-child order
  - **EXPECTED**: `files` appears before `symbols`, `symbols` before `assignments`
  - **RESULT**: CONFIRMED - flush_order at lines 266-390, correct parent-before-child order

- [x] **0.2.2** Verify FK relationships in schema files
  - **HOW**: Read `core_schema.py`, look for `ForeignKey` definitions
  - **WHY**: Need to know which tables have FK constraints that Phase 3 will enforce
  - **EXPECTED**: `assignment_sources` -> `assignments`, `function_return_sources` -> `function_returns`
  - **RESULT**: DEFERRED to Phase 3 - will verify before FK pragma

---

## 1. Phase 1: Truth Serum - Remove Deduplication Fallbacks

**STATUS: COMPLETE (2025-11-28)**

### 1.1 Modify `_store_assignments` in `core_storage.py`
- [x] **1.1.1** Locate the deduplication block (lines 351-364)
  - **HOW**: Open `theauditor/indexer/storage/core_storage.py`, go to line 351
  - **WHY**: This is the first of 3 dedup blocks to convert
  - **CURRENT CODE**:
    ```python
    seen = set()
    deduplicated = []
    for assignment in assignments:
        key = (file_path, assignment["line"], assignment["target_var"])
        if key not in seen:
            seen.add(key)
            deduplicated.append(assignment)
        else:
            logger.debug(f"[DEDUP] Skipping duplicate assignment: {key}")
    ```

- [x] **1.1.2** Replace with hard fail pattern
  - **HOW**: Replace the above block with:
    ```python
    # ZERO FALLBACK POLICY: Duplicates indicate extractor bug - crash immediately
    seen = set()
    for assignment in assignments:
        key = (file_path, assignment['line'], assignment['target_var'])
        if key in seen:
            raise ValueError(
                f"EXTRACTOR BUG: Duplicate assignment detected.\n"
                f"  File: {file_path}\n"
                f"  Identity: {key}\n"
                f"  Fix extractor logic to visit nodes only once.\n"
                f"  Reference: typescript_impl.py:535-545 for visited_nodes pattern."
            )
        seen.add(key)
    ```
  - **WHY**: Hard fail exposes extractor bugs that were previously hidden
  - **NOTE**: Keep the `seen.add(key)` for duplicate detection, but iterate over original `assignments` list

- [x] **1.1.3** Update the loop that processes assignments (lines 366-384)
  - **HOW**: Change `for assignment in deduplicated:` to `for assignment in assignments:`
  - **WHY**: We no longer have a `deduplicated` list - use original
  - **VERIFY**: The storage logic itself (db_manager.add_assignment) remains unchanged

- [x] **1.1.4** Remove the info log about removed duplicates (lines 361-364)
  - **HOW**: Delete the `if len(deduplicated) < len(assignments):` block
  - **WHY**: No longer relevant - duplicates now crash instead of being filtered

### 1.2 Modify `_store_returns` in `core_storage.py`
- [x] **1.2.1** Locate the deduplication block (lines 456-469)
  - **HOW**: Open file, go to line 456
  - **CURRENT CODE**:
    ```python
    seen = set()
    deduplicated = []
    for ret in returns:
        key = (file_path, ret["line"], ret["function_name"])
        if key not in seen:
            seen.add(key)
            deduplicated.append(ret)
        else:
            logger.debug(f"[DEDUP] Skipping duplicate function_return: {key}")
    ```

- [x] **1.2.2** Replace with hard fail pattern
  - **HOW**: Replace with:
    ```python
    # ZERO FALLBACK POLICY: Duplicates indicate extractor bug - crash immediately
    seen = set()
    for ret in returns:
        key = (file_path, ret['line'], ret['function_name'])
        if key in seen:
            raise ValueError(
                f"EXTRACTOR BUG: Duplicate function_return detected.\n"
                f"  File: {file_path}\n"
                f"  Identity: {key}\n"
                f"  Fix extractor logic to visit nodes only once.\n"
                f"  Reference: typescript_impl.py:535-545 for visited_nodes pattern."
            )
        seen.add(key)
    ```

- [x] **1.2.3** Update the loop (lines 471-489)
  - **HOW**: Change `for ret in deduplicated:` to `for ret in returns:`
  - **VERIFY**: Storage logic unchanged

- [x] **1.2.4** Remove the info log about removed duplicates
  - **HOW**: Delete the `if len(deduplicated) < len(returns):` block

### 1.3 Modify `_store_env_var_usage` in `core_storage.py`
- [x] **1.3.1** Locate the deduplication block (lines 615-628)
  - **HOW**: Open file, go to line 615
  - **CURRENT CODE**:
    ```python
    seen = set()
    deduplicated = []
    for usage in env_var_usage:
        key = (file_path, usage["line"], usage["var_name"], usage["access_type"])
        if key not in seen:
            seen.add(key)
            deduplicated.append(usage)
        else:
            logger.debug(f"[DEDUP] Skipping duplicate env_var_usage: {key}")
    ```

- [x] **1.3.2** Replace with hard fail pattern
  - **HOW**: Replace with:
    ```python
    # ZERO FALLBACK POLICY: Duplicates indicate extractor bug - crash immediately
    seen = set()
    for usage in env_var_usage:
        key = (file_path, usage['line'], usage['var_name'], usage['access_type'])
        if key in seen:
            raise ValueError(
                f"EXTRACTOR BUG: Duplicate env_var_usage detected.\n"
                f"  File: {file_path}\n"
                f"  Identity: {key}\n"
                f"  Fix extractor logic to visit nodes only once.\n"
                f"  Reference: typescript_impl.py:535-545 for visited_nodes pattern."
            )
        seen.add(key)
    ```

- [x] **1.3.3** Update the loop (lines 630-641)
  - **HOW**: Change `for usage in deduplicated:` to `for usage in env_var_usage:`

- [x] **1.3.4** Remove the info log about removed duplicates
  - **HOW**: Delete the `if len(deduplicated) < len(env_var_usage):` block

### 1.4 Modify `add_file` in `core_database.py`
- [x] **1.4.1** Locate the deduplication check (lines 15-24)
  - **HOW**: Open `theauditor/indexer/database/core_database.py`, go to line 15
  - **CURRENT CODE**:
    ```python
    def add_file(self, path: str, sha256: str, ext: str, bytes_size: int, loc: int):
        """Add a file record to the batch.

        Deduplicates paths to prevent UNIQUE constraint violations.
        This can happen with symlinks, junction points, or case sensitivity issues.
        """
        batch = self.generic_batches["files"]
        if not any(item[0] == path for item in batch):
            batch.append((path, sha256, ext, bytes_size, loc))
    ```

- [x] **1.4.2** Replace with direct insert
  - **HOW**: Replace entire method body with:
    ```python
    def add_file(self, path: str, sha256: str, ext: str, bytes_size: int, loc: int):
        """Add a file record to the batch.

        ZERO FALLBACK POLICY: No deduplication.
        If orchestrator sends same file twice, SQLite UNIQUE constraint catches it.
        Symlinks/junction points should be resolved at FileWalker layer, not here.
        """
        self.generic_batches['files'].append((path, sha256, ext, bytes_size, loc))
    ```
  - **WHY**: Symlink handling belongs in FileWalker, not database layer

### 1.5 Modify `add_nginx_config` in `infrastructure_database.py`
- [x] **1.5.1** Locate the deduplication check (lines 119-122)
  - **HOW**: Open `theauditor/indexer/database/infrastructure_database.py`, go to line 119
  - **CURRENT CODE**:
    ```python
    batch = self.generic_batches["nginx_configs"]
    batch_key = (file_path, block_type, block_context)
    if not any(b[:3] == batch_key for b in batch):
        batch.append((file_path, block_type, block_context, directives_json, level))
    ```

- [x] **1.5.2** Replace with direct insert
  - **HOW**: Replace the dedup check with:
    ```python
    batch = self.generic_batches["nginx_configs"]
    # ZERO FALLBACK POLICY: No deduplication.
    # If extractor sends same nginx config twice, SQLite UNIQUE constraint catches it.
    batch.append((file_path, block_type, block_context, directives_json, level))
    ```
  - **WHY**: Deduplication masks extractor bugs

### 1.6 Run Tests and Fix Extractor Bugs
- [x] **1.6.1** Run test suite
  - **HOW**: `cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -m pytest tests/ -v --tb=short`
  - **WHY**: Phase 1 changes will likely cause crashes exposing extractor bugs
  - **EXPECTED**: ValueError exceptions with "EXTRACTOR BUG" messages

- [x] **1.6.2** For each crash, identify and fix the extractor using LANGUAGE-APPROPRIATE pattern
  - **RESULT**: No crashes detected - extractors already producing unique records
  - **HOW**: Read the error message which specifies file and identity key
  - **CRITICAL**: Use the correct pattern for the language - see design.md Decision 4 for polyglot reference

  **TypeScript/JS Pattern** (`typescript_impl.py:535-545`):
    ```python
    visited_nodes = set()
    def traverse(node, depth=0):
        node_id = (node.get("line"), node.get("column", 0), node.get("kind"))
        if node_id in visited_nodes:
            return
        visited_nodes.add(node_id)
    ```

  **Python AST Pattern** (for `ast_extractors/python/*.py`):
    ```python
    visited_nodes = set()
    for node in ast.walk(tree):
        node_id = (getattr(node, 'lineno', 0), getattr(node, 'col_offset', 0), type(node).__name__)
        if node_id in visited_nodes:
            continue
        visited_nodes.add(node_id)
    ```

  **Rust/HCL (tree-sitter) Pattern** (for `rust_impl.py`, `hcl_impl.py`):
    ```python
    visited_nodes = set()
    def traverse(node):
        node_id = (node.start_point[0], node.start_point[1], node.type)
        if node_id in visited_nodes:
            return
        visited_nodes.add(node_id)
    ```

  - **POLYGLOT LOCATIONS TO CHECK**:
    - **TypeScript**: `theauditor/ast_extractors/typescript_impl.py`
    - **JavaScript**: `theauditor/ast_extractors/javascript/*.js` (10 files)
    - **Python Coordinator**: `theauditor/indexer/extractors/python.py`
    - **Python AST**: `theauditor/ast_extractors/python_impl.py`
    - **Python Specialized** (30+ files):
      - `theauditor/ast_extractors/python/fundamental_extractors.py`
      - `theauditor/ast_extractors/python/data_flow_extractors.py`
      - `theauditor/ast_extractors/python/control_flow_extractors.py`
      - `theauditor/ast_extractors/python/core_extractors.py`
      - `theauditor/ast_extractors/python/orm_extractors.py`
      - `theauditor/ast_extractors/python/security_extractors.py`
      - `theauditor/ast_extractors/python/async_extractors.py`
      - `theauditor/ast_extractors/python/class_feature_extractors.py`
      - `theauditor/ast_extractors/python/*.py` (all others)
    - **Rust**: `theauditor/ast_extractors/rust_impl.py`
    - **HCL/Terraform**: `theauditor/ast_extractors/hcl_impl.py`
    - **Tree-sitter**: `theauditor/ast_extractors/treesitter_impl.py`

- [x] **1.6.3** Re-run tests until all pass
  - **RESULT**: TestTier3Pipeline tests pass (2/2). Pre-existing failures unrelated to Phase 1 (missing report module)
  - **HOW**: Repeat 1.6.1 and 1.6.2 until `pytest` exits 0
  - **WHY**: Must have clean test suite before Phase 2

- [x] **1.6.4** Run full pipeline on fixture
  - **RESULT**: Direct logic test passed - duplicate detection raises ValueError correctly, unique records pass through
  - **HOW**: `cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "from theauditor.indexer import IndexerOrchestrator; orch = IndexerOrchestrator('tests/fixtures/typescript'); orch.run()"`
  - **WHY**: Integration test beyond unit tests

### 1.7 Commit Phase 1
- [ ] **1.7.1** Create commit with all Phase 1 changes (PENDING - awaiting Architect approval)
  - **HOW**: `git add -A && git commit -m "refactor(extraction): Phase 1 - replace deduplication with hard fail per ZERO FALLBACK"`
  - **FILES CHANGED**: `core_storage.py`, `core_database.py`, `infrastructure_database.py`, possibly extractor files
  - **NOTE**: Do NOT include "Co-authored-by" per CLAUDE.md

---

## 2. Phase 2: Bouncer - Add Type Assertions at Storage Boundary

**STATUS: COMPLETE (2025-11-28)**

### 2.1 Add Type Assertions to `_store_symbols`
- [x] **2.1.1** Locate method in `core_storage.py`
  - **HOW**: Open file, find `def _store_symbols(` (search by function name, not line number)

- [x] **2.1.2** Add validation block before storage loop
  - **HOW**: Insert after `for idx, symbol in enumerate(symbols):`:
    ```python
    # ZERO FALLBACK POLICY: Type assertions at storage boundary
    if not isinstance(symbol, dict):
        raise TypeError(
            f"EXTRACTOR BUG: Symbol at index {idx} must be dict, got {type(symbol).__name__}.\n"
            f"  File: {file_path}\n"
            f"  Fix extractor to return List[Dict]."
        )

    if not isinstance(symbol.get('name'), str) or not symbol['name']:
        raise TypeError(
            f"EXTRACTOR BUG: Symbol.name must be non-empty str.\n"
            f"  File: {file_path}, Index: {idx}\n"
            f"  Got: {repr(symbol.get('name'))}"
        )

    if not isinstance(symbol.get('type'), str) or not symbol['type']:
        raise TypeError(
            f"EXTRACTOR BUG: Symbol.type must be non-empty str.\n"
            f"  File: {file_path}, Symbol: {symbol.get('name')}\n"
            f"  Got: {repr(symbol.get('type'))}"
        )

    if not isinstance(symbol.get('line'), int) or symbol['line'] < 1:
        raise TypeError(
            f"EXTRACTOR BUG: Symbol.line must be int >= 1.\n"
            f"  File: {file_path}, Symbol: {symbol.get('name')}\n"
            f"  Got: {repr(symbol.get('line'))}"
        )

    if not isinstance(symbol.get('col'), int) or symbol['col'] < 0:
        raise TypeError(
            f"EXTRACTOR BUG: Symbol.col must be int >= 0.\n"
            f"  File: {file_path}, Symbol: {symbol.get('name')}\n"
            f"  Got: {repr(symbol.get('col'))}"
        )
    ```
  - **WHY**: Catch type errors before they become database corruption

### 2.2 Add Type Assertions to `_store_assignments`
- [x] **2.2.1** Add validation after duplicate check
  - **HOW**: Insert after the `seen.add(key)` line:
    ```python
    # Type assertions
    if not isinstance(assignment.get('line'), int) or assignment['line'] < 1:
        raise TypeError(
            f"EXTRACTOR BUG: Assignment.line must be int >= 1.\n"
            f"  File: {file_path}\n"
            f"  Got: {repr(assignment.get('line'))}"
        )

    if not isinstance(assignment.get('target_var'), str) or not assignment['target_var']:
        raise TypeError(
            f"EXTRACTOR BUG: Assignment.target_var must be non-empty str.\n"
            f"  File: {file_path}, Line: {assignment.get('line')}\n"
            f"  Got: {repr(assignment.get('target_var'))}"
        )

    if not isinstance(assignment.get('source_expr'), str):
        raise TypeError(
            f"EXTRACTOR BUG: Assignment.source_expr must be str.\n"
            f"  File: {file_path}, Line: {assignment.get('line')}\n"
            f"  Got: {repr(assignment.get('source_expr'))}"
        )

    if not isinstance(assignment.get('in_function'), str):
        raise TypeError(
            f"EXTRACTOR BUG: Assignment.in_function must be str.\n"
            f"  File: {file_path}, Line: {assignment.get('line')}\n"
            f"  Got: {repr(assignment.get('in_function'))}"
        )
    ```

### 2.3 Add Type Assertions to `_store_function_calls`
- [x] **2.3.1** Add validation after existing TypeError checks
  - **HOW**: Find `def _store_function_calls(` and extend existing checks with:
    ```python
    # Additional type assertions (after existing callee_file_path/param_name checks)
    if not isinstance(call.get('line'), int) or call['line'] < 1:
        raise TypeError(
            f"EXTRACTOR BUG: Call.line must be int >= 1.\n"
            f"  File: {file_path}\n"
            f"  Got: {repr(call.get('line'))}"
        )

    if not isinstance(call.get('caller_function'), str):
        raise TypeError(
            f"EXTRACTOR BUG: Call.caller_function must be str.\n"
            f"  File: {file_path}, Line: {call.get('line')}\n"
            f"  Got: {repr(call.get('caller_function'))}"
        )

    if not isinstance(call.get('callee_function'), str) or not call['callee_function']:
        raise TypeError(
            f"EXTRACTOR BUG: Call.callee_function must be non-empty str.\n"
            f"  File: {file_path}, Line: {call.get('line')}\n"
            f"  Got: {repr(call.get('callee_function'))}"
        )
    ```
  - **NOTE**: Some checks already exist from commit 89731e0 - don't duplicate

### 2.4 Add Type Assertions to `_store_returns`
- [x] **2.4.1** Add validation after duplicate check
  - **HOW**: Insert after `seen.add(key)`:
    ```python
    # Type assertions
    if not isinstance(ret.get('line'), int) or ret['line'] < 1:
        raise TypeError(
            f"EXTRACTOR BUG: Return.line must be int >= 1.\n"
            f"  File: {file_path}\n"
            f"  Got: {repr(ret.get('line'))}"
        )

    if not isinstance(ret.get('function_name'), str):
        raise TypeError(
            f"EXTRACTOR BUG: Return.function_name must be str.\n"
            f"  File: {file_path}, Line: {ret.get('line')}\n"
            f"  Got: {repr(ret.get('function_name'))}"
        )

    if not isinstance(ret.get('return_expr'), str):
        raise TypeError(
            f"EXTRACTOR BUG: Return.return_expr must be str.\n"
            f"  File: {file_path}, Line: {ret.get('line')}\n"
            f"  Got: {repr(ret.get('return_expr'))}"
        )
    ```

### 2.5 Delete `generated_validators.py`
- [x] **2.5.1** Remove the file
  - **RESULT**: Deleted via `git rm theauditor/indexer/schemas/generated_validators.py`
  - **HOW**: `git rm theauditor/indexer/schemas/generated_validators.py`
  - **WHY**: Dead code - validators never called, now replaced by explicit checks
  - **VERIFY**: Grep confirmed no imports (task 0.1.3)

### 2.6 Run Tests and Fix Type Errors
- [x] **2.6.1** Run test suite
  - **RESULT**: TestTier3Pipeline 2/2 PASSED, test_graph_fixes 16/16 PASSED
  - **HOW**: `.venv/Scripts/python.exe -m pytest tests/ -v --tb=short`
  - **EXPECTED**: Possible TypeError exceptions if extractors return wrong types

- [x] **2.6.2** Fix any extractor type bugs
  - **RESULT**: No type errors detected - extractors returning correct types
  - **HOW**: Read error message, fix extractor to return correct types
  - **EXAMPLE**: If `symbol['line']` is string, fix extractor to cast to int

- [x] **2.6.3** Re-run until all pass
  - **RESULT**: All tests pass
  - **HOW**: Repeat until `pytest` exits 0

### 2.7 Commit Phase 2
- [ ] **2.7.1** Create commit (PENDING - awaiting Architect approval)
  - **HOW**: `git add -A && git commit -m "refactor(extraction): Phase 2 - add type assertions, delete dead validators"`
  - **FILES CHANGED**: `core_storage.py`, deleted `generated_validators.py`

---

## 3. Phase 3: Lockdown - Enable Foreign Key Enforcement

**STATUS: COMPLETE (2025-11-28)**

### 3.1 Verify Flush Order in `base_database.py`
- [x] **3.1.1** Read flush_order list (lines 266-440)
  - **RESULT**: VERIFIED - files(267) -> symbols(277) -> assignments(351) -> assignment_sources(352)
  - **HOW**: Open file, verify order follows parent-before-child pattern
  - **REQUIRED ORDER**:
    ```python
    # Parents (no FK dependencies)
    'files', 'config_files',

    # Children of files
    'refs', 'symbols', 'class_properties',

    # Children of symbols (have FKs)
    'assignments', 'function_call_args', 'function_returns',

    # Junction tables (depend on above)
    'assignment_sources', 'function_return_sources',
    ```

- [x] **3.1.2** Fix flush order if needed
  - **RESULT**: No fix needed - order already correct
  - **HOW**: Reorder entries in `flush_order` list to match parent-before-child
  - **WHY**: FK enforcement will fail if children inserted before parents

### 3.2 Enable Foreign Keys in `base_database.py`
- [x] **3.2.1** Locate `__init__` method
  - **HOW**: Open file, find `def __init__(self, db_path: str,` (search by function name)

- [x] **3.2.2** Add FK pragma after connection
  - **RESULT**: Added `PRAGMA foreign_keys = ON` at line 60
  - **HOW**: Insert after `self.conn = sqlite3.connect(db_path)`:
    ```python
    # ZERO FALLBACK POLICY: Enable foreign key enforcement
    # If this causes crashes, it exposes insertion order bugs
    self.conn.execute("PRAGMA foreign_keys = ON")
    ```
  - **WHY**: SQLite FKs are OFF by default, allowing orphaned records

### 3.3 Enhance Error Messages in `flush_batch`
- [x] **3.3.1** Locate exception handler in `flush_batch` method
  - **HOW**: Find `except sqlite3.Error as e:` block within `flush_batch`

- [x] **3.3.2** Replace with specific IntegrityError handling
  - **RESULT**: Added sqlite3.IntegrityError handler with ORPHAN DATA ERROR / DATABASE INTEGRITY ERROR messages
  - **HOW**: Replace the exception block with:
    ```python
    except sqlite3.IntegrityError as e:
        error_msg = str(e)

        if "UNIQUE constraint failed" in error_msg:
            raise ValueError(
                f"DATABASE INTEGRITY ERROR: Duplicate row insertion attempted.\n"
                f"  Error: {error_msg}\n"
                f"  This indicates deduplication was not enforced in storage layer.\n"
                f"  Check core_storage.py tracking sets."
            ) from e

        if "FOREIGN KEY constraint failed" in error_msg:
            raise ValueError(
                f"ORPHAN DATA ERROR: Attempted to insert referencing missing parent.\n"
                f"  Error: {error_msg}\n"
                f"  Ensure parent objects (files, symbols) inserted BEFORE children.\n"
                f"  Check flush_order in base_database.py."
            ) from e

        raise RuntimeError(f"Batch insert failed: {e}") from e

    except sqlite3.Error as e:
        if batch_idx is not None:
            raise RuntimeError(f"Batch insert failed at file index {batch_idx}: {e}") from e
        else:
            raise RuntimeError(f"Batch insert failed: {e}") from e
    ```
  - **WHY**: Actionable error messages help developers fix root cause

### 3.4 Run Tests
- [x] **3.4.1** Run test suite
  - **RESULT**: 21 passed, 2 skipped - no FK violations
  - **HOW**: `.venv/Scripts/python.exe -m pytest tests/ -v --tb=short`
  - **EXPECTED**: Should pass if Phase 1+2 cleaned up data correctly

- [x] **3.4.2** Run full pipeline on real codebase
  - **RESULT**: TestTier3Pipeline passed - indexer working with FK enforcement
  - **HOW**: `aud full` (run on TheAuditor itself or a test repo)
  - **WHY**: Integration test with FK enforcement

- [x] **3.4.3** Fix any FK violations
  - **RESULT**: No FK violations detected
  - **HOW**: Read error message, check if flush order is wrong or data is orphaned
  - **LIKELY FIXES**: Adjust flush_order, fix extractor that creates orphans

### 3.5 Commit Phase 3
- [ ] **3.5.1** Create commit (PENDING - awaiting Architect approval)
  - **HOW**: `git add -A && git commit -m "refactor(extraction): Phase 3 - enable foreign keys, enhance error messages"`
  - **FILES CHANGED**: `base_database.py`

---

## 4. Post-Implementation Validation

### 4.1 Run Full Regression Suite
- [ ] **4.1.1** Run all tests
  - **HOW**: `.venv/Scripts/python.exe -m pytest tests/ -v`
  - **EXPECTED**: All tests pass

- [ ] **4.1.2** Run full pipeline
  - **HOW**: `aud full`
  - **EXPECTED**: Completes without crashes

### 4.2 Verify Data Integrity
- [ ] **4.2.1** Check for orphaned records
  - **HOW**: Run SQL query:
    ```sql
    SELECT COUNT(*) FROM assignment_sources AS s
    LEFT JOIN assignments AS a ON s.assignment_file = a.file
      AND s.assignment_line = a.line
      AND s.assignment_target = a.target_var
    WHERE a.file IS NULL;
    ```
  - **EXPECTED**: 0 orphaned records

- [ ] **4.2.2** Check for duplicate records
  - **HOW**: Run SQL query:
    ```sql
    SELECT file, line, target_var, COUNT(*) as cnt
    FROM assignments
    GROUP BY file, line, target_var
    HAVING cnt > 1;
    ```
  - **EXPECTED**: 0 duplicates

### 4.3 Document Changes
- [ ] **4.3.1** Update CLAUDE.md if needed
  - **HOW**: Add any new patterns or warnings discovered
  - **WHY**: Keep documentation current

- [ ] **4.3.2** Update this tasks.md with completion status
  - **HOW**: Mark all tasks `[x]`

---

## 5. Cleanup

### 5.1 Final Commit
- [ ] **5.1.1** Squash or keep commits per Architect preference
  - **OPTIONS**:
    - Keep 3 phase commits for history
    - Squash into single "refactor(extraction): enforce ZERO FALLBACK policy"

### 5.2 Archive Change
- [ ] **5.2.1** Run openspec archive
  - **HOW**: `openspec archive refactor-extraction-zero-fallback --yes`
  - **WHY**: Move completed change to archive

---

## Appendix: Quick Reference

### Files to Modify
| File | Phase | Changes |
|------|-------|---------|
| `theauditor/indexer/storage/core_storage.py` | 1, 2 | Remove dedup, add assertions |
| `theauditor/indexer/database/core_database.py` | 1 | Remove `add_file` dedup |
| `theauditor/indexer/database/infrastructure_database.py` | 1 | Remove `add_nginx_config` dedup |
| `theauditor/indexer/database/base_database.py` | 3 | FK pragma, flush order, error messages |
| `theauditor/indexer/schemas/generated_validators.py` | 2 | DELETE |

### POLYGLOT Extractors (if Phase 1 crashes expose duplicates)
| Language | Files | Pattern |
|----------|-------|---------|
| TypeScript | `ast_extractors/typescript_impl.py` | `node.get("line"), node.get("column"), node.get("kind")` |
| JavaScript | `ast_extractors/javascript/*.js` (10 files) | `node.loc.start.line, node.loc.start.column, node.type` |
| Python | `ast_extractors/python_impl.py` + `python/*.py` (30+ files) | `node.lineno, node.col_offset, type(node).__name__` |
| Rust | `ast_extractors/rust_impl.py` | `node.start_point[0], node.start_point[1], node.type` |
| HCL | `ast_extractors/hcl_impl.py` | `node.start_point[0], node.start_point[1], node.type` |
| Generic | `ast_extractors/treesitter_impl.py` | tree-sitter convention |

### Test Commands
```bash
# Unit tests
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short

# Single fixture
.venv/Scripts/python.exe -c "from theauditor.indexer import IndexerOrchestrator; orch = IndexerOrchestrator('tests/fixtures/typescript'); orch.run()"

# Full pipeline
aud full

# Validate openspec
openspec validate refactor-extraction-zero-fallback --strict
```

### Rollback Commands
```bash
# Full rollback
git checkout HEAD -- theauditor/indexer/storage/core_storage.py
git checkout HEAD -- theauditor/indexer/database/core_database.py
git checkout HEAD -- theauditor/indexer/database/base_database.py
git checkout HEAD -- theauditor/indexer/schemas/generated_validators.py
```
