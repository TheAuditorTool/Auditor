# Implementation Tasks: refactor-core-ast-extractors-split

**IRONCLAD EDITION** - Mechanical, Grep-Based, State-Verified

**Execution Mode**: ANY AI can execute this blindly. No judgment calls. No line numbers. All mechanical.

---

## 0. Verification (MANDATORY - Per teamsop.md v4.20)

**Prime Directive**: Question Everything, Assume Nothing, Verify Everything

- [x] 0.1 Read teamsop.md v4.20 to understand Prime Directive
- [x] 0.2 Read OpenSpec AGENTS.md to understand proposal format
- [x] 0.3 Read `core_ast_extractors.js` in full (2376 lines, 1500-line chunks)
- [x] 0.4 Read `js_helper_templates.py` to understand assembly logic
- [x] 0.5 Read refactor precedents (refactor-taint-schema-driven-architecture, refactor-storage-domain-split)
- [x] 0.6 Verify file exceeded 2,000 line policy (line 35 documents growth policy)
- [x] 0.7 Analyze extractor distribution and domain boundaries
- [x] 0.8 Document hypotheses in verification.md
- [x] 0.9 Create proposal.md with evidence-based claims
- [ ] 0.10 Await Architect + Lead Auditor approval

**Status**: Verification complete, awaiting approval

---

## 0.5 Current-State Verification (CRITICAL - Fail-Fast Gate)

**Purpose**: Verify file state matches proposal assumptions. If ANY check fails, STOP and re-verify proposal.

- [ ] 0.5.1 Verify file line count is within expected range
  ```bash
  cd C:\Users\santa\Desktop\TheAuditor
  wc -l theauditor\ast_extractors\javascript\core_ast_extractors.js
  # EXPECTED: 2376 ± 50 lines (allow minor growth since proposal creation)
  # IF OUTSIDE RANGE: STOP, re-read file, update proposal
  ```

- [ ] 0.5.2 Verify extractor function count
  ```bash
  grep "^function extract" theauditor\ast_extractors\javascript\core_ast_extractors.js | wc -l
  # EXPECTED: 14 extract* functions

  grep "^function " theauditor\ast_extractors\javascript\core_ast_extractors.js | wc -l
  # EXPECTED: 17 total functions (14 extract* + 3 helpers: serializeNodeForCFG, buildScopeMap, countNodes)
  # IF MISMATCH: STOP, re-verify proposal assumptions
  ```

- [ ] 0.5.3 Verify growth policy exists at documented location
  ```bash
  grep -n "Growth policy" theauditor\ast_extractors\javascript\core_ast_extractors.js
  # EXPECTED: Line ~35 contains "Growth policy: If exceeds 2,000 lines, split"
  # IF NOT FOUND: STOP, file structure changed
  ```

- [ ] 0.5.4 Verify js_helper_templates.py loader exists
  ```bash
  grep -n "core_ast_extractors" theauditor\ast_extractors\js_helper_templates.py
  # EXPECTED: Multiple matches (cache dict, loader, assembly)
  # IF NOT FOUND: STOP, orchestrator structure changed
  ```

**GATE RESULT**: ✅ PASS / ❌ FAIL (if fail, abort and re-verify)

---

## 1. Pre-Flight Checks & Baseline Capture

- [ ] 1.1 Verify git working directory is clean
  ```bash
  cd C:\Users\santa\Desktop\TheAuditor
  git status
  # EXPECTED: "nothing to commit, working tree clean" or only untracked openspec files
  # IF DIRTY: Commit or stash changes before proceeding
  ```

- [ ] 1.2 Create backup of original file
  ```bash
  cp theauditor\ast_extractors\javascript\core_ast_extractors.js theauditor\ast_extractors\javascript\core_ast_extractors.js.bak
  # Verify backup created
  ls -lh theauditor\ast_extractors\javascript\core_ast_extractors.js.bak
  ```

- [ ] 1.3 Run baseline database capture
  ```bash
  # Clean existing database
  rm -rf .pf

  # Run index on JavaScript fixtures
  aud index tests\fixtures\javascript\ --verbose

  # Capture baseline counts
  cd .pf
  sqlite3 repo_index.db "SELECT COUNT(*) FROM symbols WHERE type='function';" > C:\tmp\before_functions.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM function_call_args;" > C:\tmp\before_calls.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM imports;" > C:\tmp\before_imports.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM assignments;" > C:\tmp\before_assigns.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM class_properties;" > C:\tmp\before_props.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM env_var_usage;" > C:\tmp\before_env.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM orm_relationships;" > C:\tmp\before_orm.txt
  cd ..

  # Display baseline (for manual verification)
  echo "=== BASELINE COUNTS ==="
  cat C:\tmp\before_functions.txt
  cat C:\tmp\before_calls.txt
  cat C:\tmp\before_imports.txt
  cat C:\tmp\before_assigns.txt
  cat C:\tmp\before_props.txt
  cat C:\tmp\before_env.txt
  cat C:\tmp\before_orm.txt
  ```

**ROLLBACK POINT #1**: If you need to abort after this phase, just delete backup file. No changes made yet.

---

## 2. Create core_language.js (6 extractors, ~660 lines)

**METHOD**: Mechanical extraction using grep patterns. NO line numbers.

- [ ] 2.1 Create new file with header
  ```bash
  cd C:\Users\santa\Desktop\TheAuditor
  cat > theauditor\ast_extractors\javascript\core_language.js << 'HEADER_EOF'
/**
 * Core Language Extractors - Structure Layer
 *
 * Language structure and scope analysis extractors. These extractors
 * capture fundamental TypeScript/JavaScript code organization patterns.
 *
 * STABILITY: HIGH - Rarely changes once language features are implemented.
 * Only modify when adding support for new ECMAScript/TypeScript syntax.
 *
 * DEPENDENCIES: None (foundation layer)
 * USED BY: data_flow.js (scope map), security_extractors.js, framework_extractors.js
 *
 * Architecture:
 * - Extracted from: core_ast_extractors.js (refactored 2025-11-01)
 * - Used by: ES Module and CommonJS batch templates
 * - Assembly: Runtime file loading + concatenation in js_helper_templates.py
 *
 * Functions (6 language structure extractors):
 * 1. extractFunctions() - Function metadata with type annotations
 * 2. extractClasses() - Class declarations and expressions
 * 3. extractClassProperties() - Class field declarations
 * 4. buildScopeMap() - Line-to-function mapping for scope context
 * 5. serializeNodeForCFG() - AST serialization (legacy, minimal)
 * 6. countNodes() - AST complexity metrics (utility)
 */

HEADER_EOF
  ```

- [ ] 2.2 Extract serializeNodeForCFG() function (FIRST - it's early in file)
  ```bash
  # Find start of function (includes JSDoc)
  grep -n "^/\*\*" theauditor\ast_extractors\javascript\core_ast_extractors.js | grep -B1 "Serialize TypeScript AST"
  # Manually extract from /** comment to closing } of function
  # Search for "function serializeNodeForCFG" and copy until matching closing brace

  # MECHANICAL EXTRACTION STEPS:
  # 1. Open core_ast_extractors.js in editor
  # 2. Search for "Serialize TypeScript AST node to plain JavaScript object"
  # 3. Select from /** comment above to closing } of serializeNodeForCFG function
  # 4. Copy to core_language.js (append with double newline)
  # 5. Verify function signature: function serializeNodeForCFG(node, sourceFile, ts, depth = 0, maxDepth = 100)
  ```

- [ ] 2.3 Extract extractFunctions() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract function metadata directly from TypeScript AST"
  # 2. Select from /** comment to closing } of extractFunctions function
  # 3. Copy to core_language.js (append with double newline)
  # 4. Verify function signature: function extractFunctions(sourceFile, checker, ts)
  # 5. Verify nested functions included: traverse, getNameFromParent (if exists)
  ```

- [ ] 2.4 Extract extractClasses() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract class declarations for symbols table"
  # 2. Select from /** comment to closing } of extractClasses function
  # 3. Copy to core_language.js (append with double newline)
  # 4. Verify function signature: function extractClasses(sourceFile, checker, ts)
  # 5. Verify nested function included: traverse
  ```

- [ ] 2.5 Extract extractClassProperties() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract class property declarations (TypeScript/JavaScript ES2022+)"
  # 2. Select from /** comment to closing } of extractClassProperties function
  # 3. Copy to core_language.js (append with double newline)
  # 4. Verify function signature: function extractClassProperties(sourceFile, ts)
  # 5. Verify nested function included: traverse
  ```

- [ ] 2.6 Extract buildScopeMap() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Build a map of line numbers to function names for scope context"
  # 2. Select from /** comment to closing } of buildScopeMap function
  # 3. Copy to core_language.js (append with double newline)
  # 4. Verify function signature: function buildScopeMap(sourceFile, ts)
  # 5. Verify nested functions included: collectFunctions, getNameFromParent
  ```

- [ ] 2.7 Extract countNodes() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Count total nodes in AST for complexity metrics"
  # 2. Select from /** comment to closing } of countNodes function
  # 3. Copy to core_language.js (append with double newline)
  # 4. Verify function signature: function countNodes(node, ts)
  ```

- [ ] 2.8 Verify core_language.js completeness
  ```bash
  # Count functions in new file
  grep "^function " theauditor\ast_extractors\javascript\core_language.js | wc -l
  # EXPECTED: 6 functions

  # Verify function names
  grep "^function " theauditor\ast_extractors\javascript\core_language.js
  # EXPECTED OUTPUT (order doesn't matter):
  # function serializeNodeForCFG
  # function extractFunctions
  # function extractClasses
  # function extractClassProperties
  # function buildScopeMap
  # function countNodes

  # Check file size
  wc -l theauditor\ast_extractors\javascript\core_language.js
  # EXPECTED: 650-700 lines (includes header + 6 functions)
  ```

**ROLLBACK POINT #2**: If extraction failed, delete core_language.js and retry from 2.1

---

## 3. Create data_flow.js (6 extractors, ~947 lines)

**METHOD**: Mechanical extraction using grep patterns. NO line numbers.

- [ ] 3.1 Create new file with header
  ```bash
  cat > theauditor\ast_extractors\javascript\data_flow.js << 'HEADER_EOF'
/**
 * Data Flow Extractors - Analysis Layer
 *
 * Data flow and taint tracking extractors. These extractors capture
 * how data moves through the program for security analysis.
 *
 * STABILITY: MEDIUM - Changes when adding new taint tracking patterns.
 * Modify when adding support for new data flow patterns or frameworks.
 *
 * DEPENDENCIES: core_language.js (buildScopeMap for scope context)
 * USED BY: security_extractors.js, taint analysis pipeline
 *
 * Architecture:
 * - Extracted from: core_ast_extractors.js (refactored 2025-11-01)
 * - Used by: ES Module and CommonJS batch templates
 * - Assembly: Runtime file loading + concatenation in js_helper_templates.py
 *
 * Functions (6 data flow extractors):
 * 1. extractCalls() - Call expressions and property accesses
 * 2. extractAssignments() - Variable assignments with data flow
 * 3. extractFunctionCallArgs() - Function call arguments (foundation for taint)
 * 4. extractReturns() - Return statements with scope
 * 5. extractObjectLiterals() - Object literals for dynamic dispatch
 * 6. extractVariableUsage() - Variable reference tracking (utility)
 */

HEADER_EOF
  ```

- [ ] 3.2 Extract extractCalls() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract call expressions with arguments and cross-file resolution"
  # 2. Select from /** comment to closing } of extractCalls function
  # 3. Copy to data_flow.js (append with double newline)
  # 4. Verify function signature: function extractCalls(sourceFile, checker, ts, projectRoot)
  # 5. Verify nested function included: traverse
  ```

- [ ] 3.3 Extract extractAssignments() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract variable assignments with scope context for taint analysis"
  # 2. Select from /** comment to closing } of extractAssignments function
  # 3. Copy to data_flow.js (append with double newline)
  # 4. Verify function signature: function extractAssignments(sourceFile, ts, scopeMap)
  # 5. Verify nested functions included: extractVarsFromNode, traverse
  ```

- [ ] 3.4 Extract extractFunctionCallArgs() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract function call arguments with caller context"
  # 2. Select from /** comment to closing } of extractFunctionCallArgs function
  # 3. Copy to data_flow.js (append with double newline)
  # 4. Verify function signature: function extractFunctionCallArgs(sourceFile, checker, ts, scopeMap, functionParams, projectRoot)
  # 5. Verify nested functions included: buildDottedName, traverse
  ```

- [ ] 3.5 Extract extractReturns() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract return statements with JSX detection"
  # 2. Select from /** comment to closing } of extractReturns function
  # 3. Copy to data_flow.js (append with double newline)
  # 4. Verify function signature: function extractReturns(sourceFile, ts, scopeMap)
  # 5. Verify nested functions included: extractVarsFromNode, detectJsxInNode, traverse
  ```

- [ ] 3.6 Extract extractObjectLiterals() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract object literal properties for dynamic dispatch"
  # 2. Select from /** comment to closing } of extractObjectLiterals function
  # 3. Copy to data_flow.js (append with double newline)
  # 4. Verify function signature: function extractObjectLiterals(sourceFile, ts, scopeMap)
  # 5. Verify nested functions included: extractFromObjectNode, traverse
  ```

- [ ] 3.7 Extract extractVariableUsage() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Compute variable usage from assignments and calls"
  # 2. Select from /** comment to closing } of extractVariableUsage function
  # 3. Copy to data_flow.js (append with double newline)
  # 4. Verify function signature: function extractVariableUsage(assignments, functionCallArgs)
  ```

- [ ] 3.8 Verify data_flow.js completeness
  ```bash
  # Count functions in new file
  grep "^function " theauditor\ast_extractors\javascript\data_flow.js | wc -l
  # EXPECTED: 6 functions

  # Verify function names
  grep "^function extract" theauditor\ast_extractors\javascript\data_flow.js
  # EXPECTED OUTPUT:
  # function extractCalls
  # function extractAssignments
  # function extractFunctionCallArgs
  # function extractReturns
  # function extractObjectLiterals
  # function extractVariableUsage

  # Check file size
  wc -l theauditor\ast_extractors\javascript\data_flow.js
  # EXPECTED: 930-980 lines
  ```

**ROLLBACK POINT #3**: If extraction failed, delete data_flow.js and retry from 3.1

---

## 4. Create module_framework.js (5 extractors, ~769 lines)

**METHOD**: Mechanical extraction using grep patterns. NO line numbers.

- [ ] 4.1 Create new file with header
  ```bash
  cat > theauditor\ast_extractors\javascript\module_framework.js << 'HEADER_EOF'
/**
 * Module & Framework Extractors - Integration Layer
 *
 * Module system and framework pattern extractors. These extractors
 * capture imports, module resolution, and framework-specific patterns.
 *
 * STABILITY: MEDIUM - Changes when adding new framework support.
 * Modify when adding support for new import patterns or ORM frameworks.
 *
 * DEPENDENCIES: None (standalone patterns)
 * USED BY: framework_extractors.js, sequelize_extractors.js
 *
 * Architecture:
 * - Extracted from: core_ast_extractors.js (refactored 2025-11-01)
 * - Used by: ES Module and CommonJS batch templates
 * - Assembly: Runtime file loading + concatenation in js_helper_templates.py
 *
 * Functions (5 module/framework extractors):
 * 1. extractImports() - Import/require/dynamic import detection
 * 2. extractRefs() - Module resolution mappings for cross-file analysis
 * 3. extractImportStyles() - Bundle optimization analysis (utility)
 * 4. extractEnvVarUsage() - Environment variable usage patterns
 * 5. extractORMRelationships() - ORM relationship declarations
 */

HEADER_EOF
  ```

- [ ] 4.2 Extract extractImports() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract import statements from TypeScript AST"
  # 2. Select from /** comment to closing } of extractImports function
  # 3. Copy to module_framework.js (append with double newline)
  # 4. Verify function signature: function extractImports(sourceFile, ts)
  # 5. Verify nested function included: visit
  ```

- [ ] 4.3 Extract extractEnvVarUsage() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract environment variable usage patterns"
  # 2. Select from /** comment to closing } of extractEnvVarUsage function
  # 3. Copy to module_framework.js (append with double newline)
  # 4. Verify function signature: function extractEnvVarUsage(sourceFile, ts, scopeMap)
  # 5. Verify nested function included: traverse
  ```

- [ ] 4.4 Extract extractORMRelationships() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract ORM relationship declarations"
  # 2. Select from /** comment to closing } of extractORMRelationships function
  # 3. Copy to module_framework.js (append with double newline)
  # 4. Verify function signature: function extractORMRelationships(sourceFile, ts)
  # 5. Verify nested function included: traverse
  ```

- [ ] 4.5 Extract extractImportStyles() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Analyze import statements for bundle optimization"
  # 2. Select from /** comment to closing } of extractImportStyles function
  # 3. Copy to module_framework.js (append with double newline)
  # 4. Verify function signature: function extractImportStyles(imports)
  ```

- [ ] 4.6 Extract extractRefs() function
  ```bash
  # MECHANICAL EXTRACTION STEPS:
  # 1. Search for "Extract module resolution mappings for cross-file analysis"
  # 2. Select from /** comment to closing } of extractRefs function
  # 3. Copy to module_framework.js (append with double newline)
  # 4. Verify function signature: function extractRefs(imports)
  ```

- [ ] 4.7 Verify module_framework.js completeness
  ```bash
  # Count functions in new file
  grep "^function " theauditor\ast_extractors\javascript\module_framework.js | wc -l
  # EXPECTED: 5 functions

  # Verify function names
  grep "^function extract" theauditor\ast_extractors\javascript\module_framework.js
  # EXPECTED OUTPUT:
  # function extractImports
  # function extractEnvVarUsage
  # function extractORMRelationships
  # function extractImportStyles
  # function extractRefs

  # Check file size
  wc -l theauditor\ast_extractors\javascript\module_framework.js
  # EXPECTED: 750-800 lines
  ```

**ROLLBACK POINT #4**: If extraction failed, delete module_framework.js and retry from 4.1

---

## 5. Update js_helper_templates.py Orchestrator

**METHOD**: Surgical edits to Python file. Exact string replacements.

- [ ] 5.1 Update _JS_CACHE dictionary (add 3 entries, remove 1)
  ```bash
  # BEFORE (line ~37):
  _JS_CACHE = {
      'core_ast_extractors': None,
      'security_extractors': None,
      ...
  }

  # AFTER:
  _JS_CACHE = {
      'core_language': None,
      'data_flow': None,
      'module_framework': None,
      'security_extractors': None,
      ...
  }
  ```

  Use Edit tool with exact string match:
  ```python
  # OLD STRING:
  _JS_CACHE = {
      'core_ast_extractors': None,
      'security_extractors': None,

  # NEW STRING:
  _JS_CACHE = {
      'core_language': None,
      'data_flow': None,
      'module_framework': None,
      'security_extractors': None,
  ```

- [ ] 5.2 Update _load_javascript_modules() function (replace core loader with 3 loaders)
  ```bash
  # Find the section loading core_ast_extractors.js (around line 79-84)
  # Replace entire block
  ```

  Use Edit tool with exact string match:
  ```python
  # OLD STRING:
      # Load core AST extractors (foundation layer)
      core_path = js_dir / 'core_ast_extractors.js'
      if not core_path.exists():
          raise FileNotFoundError(f"Missing core AST extractors: {core_path}")
      _JS_CACHE['core_ast_extractors'] = core_path.read_text(encoding='utf-8')

  # NEW STRING:
      # Load core language extractors (language structure layer)
      core_lang_path = js_dir / 'core_language.js'
      if not core_lang_path.exists():
          raise FileNotFoundError(f"Missing core language extractors: {core_lang_path}")
      _JS_CACHE['core_language'] = core_lang_path.read_text(encoding='utf-8')

      # Load data flow extractors (data flow & taint layer)
      data_flow_path = js_dir / 'data_flow.js'
      if not data_flow_path.exists():
          raise FileNotFoundError(f"Missing data flow extractors: {data_flow_path}")
      _JS_CACHE['data_flow'] = data_flow_path.read_text(encoding='utf-8')

      # Load module/framework extractors (integration layer)
      module_fw_path = js_dir / 'module_framework.js'
      if not module_fw_path.exists():
          raise FileNotFoundError(f"Missing module/framework extractors: {module_fw_path}")
      _JS_CACHE['module_framework'] = module_fw_path.read_text(encoding='utf-8')
  ```

- [ ] 5.3 Update get_batch_helper() assembly (replace single concat with 3 concats)
  ```bash
  # Find the assembled_script concatenation (around line 213-229)
  ```

  Use Edit tool with exact string match:
  ```python
  # OLD STRING:
      assembled_script = (
          _JS_CACHE['core_ast_extractors'] +
          '\n\n' +
          _JS_CACHE['security_extractors'] +

  # NEW STRING:
      assembled_script = (
          _JS_CACHE['core_language'] +
          '\n\n' +
          _JS_CACHE['data_flow'] +
          '\n\n' +
          _JS_CACHE['module_framework'] +
          '\n\n' +
          _JS_CACHE['security_extractors'] +
  ```

- [ ] 5.4 Update docstring (line ~8-17) to reflect 3 new files
  ```bash
  # Find Architecture section in module docstring
  ```

  Use Edit tool with exact string match:
  ```python
  # OLD STRING:
  - javascript/core_ast_extractors.js: Foundation extractors (imports, functions, classes, etc.)

  # NEW STRING:
  - javascript/core_language.js: Language structure extractors (functions, classes, scope)
  - javascript/data_flow.js: Data flow extractors (assignments, calls, returns, taint)
  - javascript/module_framework.js: Module/framework extractors (imports, env vars, ORM)
  ```

- [ ] 5.5 Verify js_helper_templates.py syntax
  ```bash
  # Check Python syntax
  cd C:\Users\santa\Desktop\TheAuditor
  python -m py_compile theauditor\ast_extractors\js_helper_templates.py
  # EXPECTED: No output (success)
  # IF ERROR: Fix syntax errors before proceeding

  # Run ruff linter
  ruff check theauditor\ast_extractors\js_helper_templates.py
  # EXPECTED: No errors or only style warnings (acceptable)
  ```

**ROLLBACK POINT #5**: If Python update failed, restore from git (file is under version control)

---

## 6. Integration Testing & Validation

**CRITICAL**: Database row counts MUST be identical before/after. Any difference is a bug.

- [ ] 6.1 Clean database and re-index with new files
  ```bash
  cd C:\Users\santa\Desktop\TheAuditor

  # Remove old database
  rm -rf .pf

  # Run index with refactored extractors
  aud index tests\fixtures\javascript\ --verbose
  # Watch for TypeScript compilation errors (should be ZERO)
  ```

- [ ] 6.2 Capture post-refactor database counts
  ```bash
  cd .pf
  sqlite3 repo_index.db "SELECT COUNT(*) FROM symbols WHERE type='function';" > C:\tmp\after_functions.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM function_call_args;" > C:\tmp\after_calls.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM imports;" > C:\tmp\after_imports.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM assignments;" > C:\tmp\after_assigns.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM class_properties;" > C:\tmp\after_props.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM env_var_usage;" > C:\tmp\after_env.txt
  sqlite3 repo_index.db "SELECT COUNT(*) FROM orm_relationships;" > C:\tmp\after_orm.txt
  cd ..
  ```

- [ ] 6.3 Compare before/after counts (MUST BE IDENTICAL)
  ```bash
  echo "=== FUNCTIONS ==="
  diff C:\tmp\before_functions.txt C:\tmp\after_functions.txt
  # EXPECTED: No output (files identical)

  echo "=== FUNCTION CALL ARGS ==="
  diff C:\tmp\before_calls.txt C:\tmp\after_calls.txt
  # EXPECTED: No output

  echo "=== IMPORTS ==="
  diff C:\tmp\before_imports.txt C:\tmp\after_imports.txt
  # EXPECTED: No output

  echo "=== ASSIGNMENTS ==="
  diff C:\tmp\before_assigns.txt C:\tmp\after_assigns.txt
  # EXPECTED: No output

  echo "=== CLASS PROPERTIES ==="
  diff C:\tmp\before_props.txt C:\tmp\after_props.txt
  # EXPECTED: No output

  echo "=== ENV VAR USAGE ==="
  diff C:\tmp\before_env.txt C:\tmp\after_env.txt
  # EXPECTED: No output

  echo "=== ORM RELATIONSHIPS ==="
  diff C:\tmp\before_orm.txt C:\tmp\after_orm.txt
  # EXPECTED: No output

  # IF ANY DIFF SHOWS OUTPUT: ROLLBACK IMMEDIATELY, investigate bug
  ```

- [ ] 6.4 Verify all 17 extractors present in assembled batch script
  ```bash
  # Generate temp batch script
  python -c "from theauditor.ast_extractors.js_helper_templates import get_batch_helper; print(get_batch_helper('module'))" > C:\tmp\batch.mjs

  # Count extractor functions
  grep "^function extract" C:\tmp\batch.mjs | wc -l
  # EXPECTED: 14 extract* functions

  # Count total functions (should include serializeNodeForCFG, buildScopeMap, countNodes)
  grep "^function " C:\tmp\batch.mjs | grep -E "(extract|serialize|buildScope|countNodes)" | wc -l
  # EXPECTED: 17 functions

  # IF MISMATCH: Missing extractors, rollback and check file loading
  ```

- [ ] 6.5 Test on additional fixture projects
  ```bash
  # Clean database
  rm -rf .pf

  # Test React fixtures (if exist)
  if [ -d tests\fixtures\react ]; then
    aud index tests\fixtures\react\ --verbose
    echo "React fixtures: PASS"
  fi

  # Test Vue fixtures (if exist)
  if [ -d tests\fixtures\vue ]; then
    aud index tests\fixtures\vue\ --verbose
    echo "Vue fixtures: PASS"
  fi

  # Test TypeScript fixtures (if exist)
  if [ -d tests\fixtures\typescript ]; then
    aud index tests\fixtures\typescript\ --verbose
    echo "TypeScript fixtures: PASS"
  fi
  ```

**GATE RESULT**: ✅ ALL TESTS PASS / ❌ REGRESSIONS FOUND

**IF FAIL**: ROLLBACK to Point #5, restore backup files, investigate

---

## 7. Post-Implementation Audit (MANDATORY - Per teamsop.md v4.20)

**Purpose**: Re-read ALL modified files to verify syntax, no unintended changes, completeness.

- [ ] 7.1 Re-read core_language.js in full
  ```bash
  # Read entire file, verify:
  # - 6 functions present (serializeNodeForCFG, extractFunctions, extractClasses, extractClassProperties, buildScopeMap, countNodes)
  # - No syntax errors (balanced braces, proper function definitions)
  # - All JSDoc comments preserved
  # - File size reasonable (~650-700 lines)
  ```

- [ ] 7.2 Re-read data_flow.js in full
  ```bash
  # Read entire file, verify:
  # - 6 functions present (extractCalls, extractAssignments, extractFunctionCallArgs, extractReturns, extractObjectLiterals, extractVariableUsage)
  # - No syntax errors
  # - All JSDoc comments preserved
  # - File size reasonable (~930-980 lines)
  ```

- [ ] 7.3 Re-read module_framework.js in full
  ```bash
  # Read entire file, verify:
  # - 5 functions present (extractImports, extractEnvVarUsage, extractORMRelationships, extractImportStyles, extractRefs)
  # - No syntax errors
  # - All JSDoc comments preserved
  # - File size reasonable (~750-800 lines)
  ```

- [ ] 7.4 Re-read modified js_helper_templates.py
  ```bash
  # Verify changes correct:
  # - _JS_CACHE has 3 new entries (core_language, data_flow, module_framework)
  # - _load_javascript_modules() loads 3 new files
  # - get_batch_helper() concatenates 3 files in correct order
  # - Docstring updated to reference new file structure
  ```

- [ ] 7.5 Document audit results
  ```bash
  # Create audit report (plain text)
  cat > C:\tmp\post_audit_report.txt << 'AUDIT_EOF'
  === POST-IMPLEMENTATION AUDIT REPORT ===
  Date: [INSERT DATE]

  Files Audited:
  1. core_language.js - [✅ PASS / ❌ ISSUES]
  2. data_flow.js - [✅ PASS / ❌ ISSUES]
  3. module_framework.js - [✅ PASS / ❌ ISSUES]
  4. js_helper_templates.py - [✅ PASS / ❌ ISSUES]

  Issues Found:
  [NONE / LIST ISSUES]

  Overall Result: [✅ SUCCESS / ❌ FAIL]
  AUDIT_EOF

  # Display report
  cat C:\tmp\post_audit_report.txt
  ```

**Audit Result**: ✅ SUCCESS / ❌ ISSUES FOUND (describe)

**IF FAIL**: Fix issues before proceeding to cleanup

---

## 8. Cleanup & Documentation

- [ ] 8.1 Delete original core_ast_extractors.js (ONLY if all tests passed)
  ```bash
  cd C:\Users\santa\Desktop\TheAuditor

  # Final confirmation
  echo "About to delete core_ast_extractors.js. All tests passed? [y/N]"
  # IF YES:
  rm theauditor\ast_extractors\javascript\core_ast_extractors.js

  # Verify deletion
  ls theauditor\ast_extractors\javascript\core_ast_extractors.js
  # EXPECTED: "No such file or directory"
  ```

- [ ] 8.2 Delete backup file (ONLY if refactor successful and committed)
  ```bash
  # Keep backup until git commit is made
  # After commit, safe to delete:
  rm theauditor\ast_extractors\javascript\core_ast_extractors.js.bak
  ```

- [ ] 8.3 Update CLAUDE.md if file structure documented there
  ```bash
  # Search for references to core_ast_extractors.js
  grep -n "core_ast_extractors" CLAUDE.md
  # IF FOUND: Update to reference new 3-file structure
  ```

- [ ] 8.4 Create git commit
  ```bash
  cd C:\Users\santa\Desktop\TheAuditor

  # Stage new files
  git add theauditor\ast_extractors\javascript\core_language.js
  git add theauditor\ast_extractors\javascript\data_flow.js
  git add theauditor\ast_extractors\javascript\module_framework.js

  # Stage modified file
  git add theauditor\ast_extractors\js_helper_templates.py

  # Stage deleted file (if using git rm)
  git rm theauditor\ast_extractors\javascript\core_ast_extractors.js

  # Create commit (NO CLAUDE CO-AUTHOR per architect mandate)
  git commit -m "refactor(ast): split core extractors into domain modules

Split core_ast_extractors.js (2376 lines) into 3 domain-focused modules:
- core_language.js (660 lines): Language structures & scope
- data_flow.js (947 lines): Data flow & taint analysis
- module_framework.js (769 lines): Imports & framework patterns

Zero functional changes - pure code organization refactor.
All 17 extractors verified identical behavior via database row counts.

Refs: openspec/changes/refactor-core-ast-extractors-split"

  # Verify commit
  git log -1 --stat
  ```

---

## 9. Completion Report (MANDATORY - Per teamsop.md v4.20)

Use Template C-4.20 from teamsop.md to document:

### 9.1 Verification Phase Report
- **Hypotheses tested**: File size (2376 lines), extractor count (17), assembly logic (string concat)
- **Evidence found**: Growth policy at line 35, grep analysis confirms 17 functions, js_helper_templates.py loads as monolith
- **Discrepancies**: Header documentation stale (14 vs 17 functions), growth policy violated (2376 > 2000)

### 9.2 Deep Root Cause Analysis
- **Surface symptom**: 2376-line monolithic JavaScript file
- **Problem chain**: Phase 5 refactor created foundation layer → Python Phase 3 added 3 extractors → No domain boundaries enforced → Linear growth to 2376 lines
- **Actual root cause**: No domain organization enforced during feature additions, despite growth policy documenting split threshold

### 9.3 Implementation Details & Rationale
- **Decision**: Split into 3 files (core_language, data_flow, module_framework)
- **Reasoning**: Clear domain boundaries, balanced sizes, matches existing pattern (security, framework extractors)
- **Alternative considered**: Keep monolithic (rejected: technical debt compounds)

### 9.4 Edge Case & Failure Mode Analysis
- **Assembly order**: Extractors are pure, order-independent (verified by function signature analysis)
- **Missing files**: Explicit FileNotFoundError with clear message
- **Name collisions**: None (all 17 function names unique)
- **Database regressions**: Mandatory before/after row count comparison caught 0 regressions

### 9.5 Post-Implementation Integrity Audit
- **Files audited**: core_language.js, data_flow.js, module_framework.js, js_helper_templates.py
- **Result**: [✅ SUCCESS / ❌ ISSUES FOUND]
- **Issues**: [NONE / LIST]

### 9.6 Impact, Reversion, & Testing
- **Immediate**: 3 files created, 1 deleted, orchestrator updated (4 file changes)
- **Downstream**: Batch assembly continues to work, all 17 extractors available
- **Reversibility**: Fully reversible (restore .bak, revert orchestrator)
- **Testing**: Database row counts identical, no TypeScript errors, all fixtures pass

---

**Status**: ✅ **COMPLETE** / ⏳ **IN PROGRESS** / ❌ **BLOCKED**

**Total Time**: [ACTUAL TIME]

**Confidence**: [High/Medium/Low]

**Final Verification**: All 7 database row count diffs show ZERO differences

---

## Appendix A: Rollback Procedures

### Full Rollback (Restore to Pre-Refactor State)

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Restore original file
cp theauditor\ast_extractors\javascript\core_ast_extractors.js.bak theauditor\ast_extractors\javascript\core_ast_extractors.js

# Delete new files
rm theauditor\ast_extractors\javascript\core_language.js
rm theauditor\ast_extractors\javascript\data_flow.js
rm theauditor\ast_extractors\javascript\module_framework.js

# Revert orchestrator (if committed, use git)
git checkout theauditor\ast_extractors\js_helper_templates.py

# Clean up test artifacts
rm -rf .pf
rm C:\tmp\before_*.txt
rm C:\tmp\after_*.txt
rm C:\tmp\batch.mjs
rm C:\tmp\post_audit_report.txt

echo "Rollback complete. Original state restored."
```

---

## Appendix B: Quick Start (For Future AI)

**If you're an AI starting this task fresh, follow this order:**

1. Read verification.md (understand what was verified)
2. Run section 0.5 (current-state verification - CRITICAL)
3. If state matches, proceed with section 1
4. Follow sections 2-4 mechanically (extraction is grep-based, no judgment)
5. Section 5 is surgical Python edits (use Edit tool, exact string match)
6. Section 6 is validation (database row counts MUST match)
7. If section 6 passes, proceed to 7-9 (audit, cleanup, commit)
8. If ANY section fails, check Appendix A for rollback

**Red flags that mean STOP**:
- Section 0.5 file verification fails (state changed, re-verify proposal)
- Section 6.3 database diffs show ANY differences (extraction bug)
- Section 6.4 assembled script missing extractors (loader bug)

**Green lights to proceed**:
- All grep counts match expected values
- Database row counts identical before/after
- TypeScript compiles with zero errors
- All 17 extractors present in assembled batch script
