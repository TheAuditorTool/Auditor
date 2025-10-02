TheAuditor Indexer Architecture - Senior Dev Briefing

  ---
  INDEXER FLOW OVERVIEW

  High-Level Pipeline

  1. Initialize Indexer
  2. Detect Frameworks (inline)
  3. Walk Directory
  4. First Pass: Parse ALL files → Standard tables
  5. Second Pass: Parse JSX files → _jsx tables
  6. Store Frameworks to database
  7. Commit & Report

  ---
  COMPONENT ARCHITECTURE

  1. IndexerOrchestrator (theauditor/indexer/__init__.py)

  Main coordinator - 860 lines, modular design

  Key Methods:
  index()                          # Main entry point
  _detect_frameworks_inline()      # NEW: Inline framework detection
  _process_file()                  # Process single file
  _store_extracted_data()          # Store to database
  _store_frameworks()              # Store framework metadata

  Initialization (lines 44-82):
  - Creates DatabaseManager
  - Creates FileWalker (with monorepo detection)
  - Creates ASTParser (with JS semantic parsing)
  - Creates ExtractorRegistry (dynamic registration)
  - Initializes counters

  ---
  2. ASTParser (theauditor/ast_parser.py)

  Dual-mode TypeScript compiler wrapper

  Critical Limitation: TypeScript compiler can ONLY parse in ONE JSX mode at a time:
  - jsx_mode='transformed': <Button /> → React.createElement(Button, null)
  - jsx_mode='preserved': <Button /> → kept as JSX syntax

  Key Methods:
  parse_files_batch(paths, jsx_mode='transformed')  # Batch parse for performance
  extract_functions(tree)                           # Extract function declarations
  extract_classes(tree)                             # Extract class declarations
  extract_assignments(tree)                         # Extract variable assignments
  extract_function_calls_with_args(tree)            # Extract call sites
  extract_returns(tree)                             # Extract return statements
  extract_cfg(tree)                                 # Extract control flow graph
  extract_imports(tree)                             # Extract imports

  Performance: Batches 50 files at a time to Node.js subprocess to avoid overhead.

  Location: Uses sandboxed tools in .auditor_venv/.theauditor_tools/ (Node v20.11.1, TypeScript, ESLint).

  ---
  3. ExtractorRegistry (theauditor/indexer/extractors/__init__.py)

  Dynamic extractor discovery via @register_extractor decorator

  Current Extractors:
  - JavaScriptExtractor - .js, .jsx, .ts, .tsx, .mjs, .cjs, .vue
  - PythonExtractor - .py
  - DockerExtractor - Dockerfile, .dockerfile
  - SQLExtractor - .sql
  - GenericExtractor - webpack.config.js, nginx.conf, docker-compose.yml

  ---
  4. JavaScriptExtractor (theauditor/indexer/extractors/javascript.py)

  452 lines - Framework-aware extraction

  Extraction Categories:

  Core Data (lines 74-122):
  - symbols: Functions, classes (declaration types: "function", "class", "variable")
  - assignments: Variable assignments with source tracking
  - function_calls: Call sites with arguments
  - returns: Return statements with JSX detection

  Framework-Specific (lines 134-307):
  - react_components: Components (checks uppercase name + JSX returns)
  - react_hooks: Hook usage with dependency arrays
  - vue_components: Vue 3 Composition API
  - vue_hooks: Vue reactivity (ref, reactive, computed, watch)
  - vue_directives: v-model, v-if, etc.
  - vue_provide_inject: Dependency injection

  Security Patterns (lines 309-393):
  - sql_queries: SQL injection detection
  - jwt_patterns: Hardcoded secrets
  - orm_queries: Sequelize/Prisma/TypeORM with include/limit/transaction analysis

  Other:
  - type_annotations: TypeScript type info (from AST)
  - variable_usage: Read/write tracking for dead code detection
  - cfg: Control flow graph blocks/edges/statements
  - api_endpoints: Route definitions
  - routes: Express/Fastify route patterns

  ---
  DUAL-PASS JSX EXTRACTION

  Why Dual-Pass?

  TypeScript Compiler Limitation: Cannot parse in both JSX modes simultaneously.

  Pass 1 Purpose (jsx_mode='transformed'):
  - For taint tracking: Track data flow through function calls
  - <Button onClick={userInput} /> → React.createElement(Button, {onClick: userInput}, null)
  - Now taint analyzer can see userInput flowing to onClick argument

  Pass 2 Purpose (jsx_mode='preserved'):
  - For structural analysis: Detect component hierarchy, JSX patterns
  - <Button onClick={userInput} /> → kept as JSX for component tree analysis
  - Rules can detect unsafe patterns like dangerouslySetInnerHTML

  ---
  CURRENT IMPLEMENTATION (As of Latest Changes)

  Pass 1: ALL Files, Transformed Mode (Lines 170-251)

  # Walk directory
  files, stats = self.file_walker.walk()

  # Separate JS/TS for batch parsing
  js_ts_files = [f for f in files if f['ext'] in JS_EXTENSIONS]

  # Batch parse with jsx_mode='transformed' (default)
  for i in range(0, len(js_ts_files), 50):
      batch = js_ts_files[i:i+50]
      batch_trees = self.ast_parser.parse_files_batch(
          batch,
          root_path=str(self.root_path),
          jsx_mode='transformed'  # EXPLICIT for taint tracking
      )
      js_ts_cache[path] = tree

  # Process ALL files (Python, Docker, SQL, JS, etc.)
  for file_info in files:
      self._process_file(file_info, js_ts_cache)
      # Stores to standard tables:
      # - files, symbols, assignments, function_call_args,
      # - function_returns, cfg_blocks, cfg_edges,
      # - react_components, react_hooks, orm_queries, etc.

  Tables Populated:
  - files - File metadata (path, sha256, ext, bytes, loc)
  - symbols - Function/class declarations
  - assignments - Variable assignments for taint tracking
  - function_call_args - Call sites with arguments
  - function_returns - Return statements
  - cfg_blocks, cfg_edges, cfg_block_statements - Control flow graph
  - react_components - Components (uppercase + JSX returns)
  - react_hooks - Hook usage (useState, useEffect, etc.)
  - vue_components, vue_hooks, vue_directives, vue_provide_inject - Vue data
  - type_annotations - TypeScript types
  - variable_usage - Read/write tracking (137k rows typically)
  - orm_queries - ORM query patterns
  - sql_queries - SQL queries (many false positives currently)

  ---
  Pass 2: JSX Files Only, Preserved Mode (Lines 257-371)

  # Filter JSX/TSX files only
  jsx_files = [f for f in files if f['ext'] in ['.jsx', '.tsx']]

  # Batch parse with jsx_mode='preserved'
  for i in range(0, len(jsx_files), 50):
      batch_trees = self.ast_parser.parse_files_batch(
          batch,
          root_path=str(self.root_path),
          jsx_mode='preserved'  # Keep JSX syntax
      )
      jsx_cache[path] = tree

  # Extract and store to _jsx tables
  for file_info in jsx_files:
      tree = jsx_cache.get(file_path)
      extracted = extractor.extract(file_info, content, tree)

      # Store to parallel _jsx tables
      for symbol in extracted['symbols']:
          db_manager.add_symbol_jsx(...)
      for assign in extracted['assignments']:
          db_manager.add_assignment_jsx(...)
      for call in extracted['function_calls']:
          db_manager.add_function_call_arg_jsx(...)
      for ret in extracted['returns']:
          db_manager.add_function_return_jsx(...)

  Tables Populated:
  - symbols_jsx - Symbols from preserved JSX
  - assignments_jsx - Assignments from preserved JSX
  - function_call_args_jsx - Call args from preserved JSX
  - function_returns_jsx - Returns from preserved JSX (with has_jsx, returns_component flags)

  All _jsx tables have:
  - jsx_mode column: 'preserved'
  - extraction_pass column: 2
  - PRIMARY KEY: Allows INSERT OR REPLACE to handle duplicates

  ---
  Framework Detection (Line 168, Lines 253-255)

  # BEFORE first pass - detect frameworks
  self.frameworks = self._detect_frameworks_inline()
  # - Scans package.json, requirements.txt, pyproject.toml
  # - Detects Express, React, Vue, Django, Flask, etc.
  # - Returns List[Dict] with framework/version/language/path/source
  # - Saves to .pf/raw/frameworks.json for backward compat

  # AFTER second pass - store to database
  if self.frameworks:
      self._store_frameworks()
      # - Inserts into frameworks table
      # - For Express: inserts safe sinks (res.json, res.jsonp)

  Tables Populated:
  - frameworks - Detected frameworks (name, version, language, path, source, is_primary)
  - framework_safe_sinks - Safe sink patterns (e.g., Express res.json auto-sanitizes)

  ---
  DATABASE SCHEMA

  Standard Tables (First Pass)

  files(path PK, sha256, ext, bytes, loc)
  symbols(path, name, type, line, col)
  assignments(file, line, target_var, source_expr, source_vars, in_function)
  function_call_args(file, line, caller_function, callee_function, argument_index, argument_expr, param_name)
  function_returns(file, line, function_name, return_expr, return_vars, has_jsx, returns_component,
  cleanup_operations)
  cfg_blocks(id PK AI, file, function_name, block_type, start_line, end_line, condition_expr)
  cfg_edges(id PK AI, file, function_name, source_block_id, target_block_id, edge_type)
  cfg_block_statements(block_id FK, statement_type, line, statement_text)
  react_components(file, name, type, start_line, end_line, has_jsx, hooks_used, props_type)
  react_hooks(file, line, component_name, hook_name, dependency_array, dependency_vars, callback_body,
  has_cleanup, cleanup_type)
  vue_components(file, name, type, start_line, end_line, has_template, has_style, composition_api_used,
  props_definition, emits_definition, setup_return)
  vue_hooks(file, line, component_name, hook_name, hook_type, dependencies, return_value, is_async)
  vue_directives(file, line, directive_name, expression, in_component, has_key, modifiers)
  vue_provide_inject(file, line, component_name, operation_type, key_name, value_expr, is_reactive)
  type_annotations(file PK, line, column, symbol_name, symbol_kind, type_annotation, is_any, is_unknown,
  is_generic, has_type_params, type_params, return_type, extends_type)
  variable_usage(file, line, variable_name, usage_type, in_component, in_hook, scope_level)
  orm_queries(file, line, query_type, includes, has_limit, has_transaction)
  sql_queries(file_path, line_number, query_text, command, tables)
  frameworks(id PK AI, name, version, language, path, source, package_manager, is_primary)
  framework_safe_sinks(framework_id FK, sink_pattern, sink_type, is_safe, reason)

  JSX Tables (Second Pass)

  symbols_jsx(path, name, type, line, col, jsx_mode, extraction_pass) PK(path, name, line, jsx_mode)
  assignments_jsx(file, line, target_var, source_expr, source_vars, in_function, jsx_mode, extraction_pass)
  PK(file, line, target_var, jsx_mode)
  function_call_args_jsx(file, line, caller_function, callee_function, argument_index, argument_expr,
  param_name, jsx_mode, extraction_pass) PK(file, line, callee_function, argument_index, jsx_mode)
  function_returns_jsx(file, line, function_name, return_expr, return_vars, has_jsx, returns_component,
  cleanup_operations, jsx_mode, extraction_pass) PK(file, line, extraction_pass)

  Unified Views (Backward Compatibility)

  function_returns_unified = function_returns UNION ALL function_returns_jsx
  symbols_unified = symbols UNION ALL symbols_jsx

  ---
  CURRENT PAIN POINTS

  1. FALSE POSITIVES 🔴

  sql_queries table (8,779 rows in test DB):
  - All have command='UNKNOWN'
  - Contains random code fragments like export class AccountController... marked as SQL CREATE
  - Cause: Overly aggressive regex in SQL extractor

  react_components table (462 rows):
  - Backend controller classes detected as React components
  - e.g., AccountController, AreaController detected because uppercase name
  - Cause: Line 138 in javascript.py only checks name[0:1].isupper() without checking if backend file

  react_hooks table (546 rows):
  - Contains .map(), .get() method calls (not hooks)
  - Cause: Line 182 checks call_name.startswith('use') but also catches methods like users.map

  2. EMPTY TABLES 🟡

  refs table (0 rows):
  - Extractor returns imports data (line 66-71 in javascript.py)
  - Never stored: _store_extracted_data() doesn't call db_manager.add_ref()

  api_endpoints table (0 rows):
  - Extractor returns routes and builds api_endpoints (line 372-381)
  - Never stored: Missing storage code

  3. UNIQUE CONSTRAINT FAILURES ✅ FIXED

  function_call_args_jsx PRIMARY KEY too restrictive:
  - Was failing on: const x = foo(1) + foo(2); (both foo() at same line)
  - Fixed: Changed to INSERT OR REPLACE in database.py

  4. FRAMEWORK DETECTION CIRCULAR DEPENDENCY ✅ FIXED

  - Indexer loads from .pf/raw/frameworks.json → doesn't exist
  - Had to manually run aud detect-frameworks first
  - Fixed: Inline detection in _detect_frameworks_inline()

  ---
  CONSTRAINTS & COMPATIBILITY

  Schema Constraints

  MUST NOT CHANGE:
  - Standard table schemas (symbols, assignments, function_call_args, function_returns)
  - Reason: Taint analyzer, graph builder, and 30+ rules query these tables directly

  CAN ADD:
  - New tables (already did: _jsx tables, frameworks tables)
  - New columns to existing tables (use ALTER TABLE with try/except for backward compat)

  CLI Surface

  MUST KEEP WORKING:
  aud index                    # Main indexing command
  aud index --exclude-self     # When analyzing TheAuditor itself
  aud detect-frameworks        # Standalone command (now redundant but kept for compat)

  NO NEW FLAGS ADDED: User explicitly forbade jsx_mode flags/parameters - always dual-pass unconditionally.

  Performance Constraints

  Current Performance (plant project, 335 files, 72 JSX):
  - First pass: ~30-60 seconds
  - Second pass: ~10-20 seconds
  - Framework detection: ~1-2 seconds
  - Total: ~1-2 minutes

  Acceptable: User stated "MEASURED IN FUCKING SECONDS" - performance is acceptable.

  Backward Compatibility

  Files That Read Database:
  - theauditor/taint_analyzer.py - Queries assignments, function_call_args, symbols
  - theauditor/commands/graph.py - Queries symbols, imports (refs table currently empty)
  - theauditor/rules/**/*.py - 30+ rules query various tables
  - theauditor/fce.py - Factual Correlation Engine queries multiple tables

  Must Not Break:
  - Rules expect frameworks table populated (XSS rules check for Express/React/Vue)
  - Taint analyzer expects assignments/function_call_args populated
  - Graph builder expects symbols populated

  ---
  TESTS & WORKFLOWS

  Critical Workflows

  1. Full Pipeline:
  cd C:\Users\santa\Desktop\plant
  rm -rf .pf
  aud full
  # Should complete without errors
  # Should detect frameworks, populate all tables, run taint, run rules

  2. Index Only:
  rm -rf .pf
  aud index
  # Should populate database, detect frameworks, run dual-pass JSX

  3. Taint Analysis:
  aud index
  aud taint-analyze
  # Should detect taint flows using assignments/function_call_args tables

  4. Rules Execution:
  aud index
  aud fce
  # Should run 30 correlation rules, use frameworks table for context

  Test Project

  Location: C:\Users\santa\Desktop\plant
  - 335 files total
  - 72 JSX/TSX files
  - Express backend, React frontend
  - Sequelize ORM

  Expected Database Size: ~70MB (was 7MB when broken, now should be fixed)

  ---
  WHAT "DUAL EXTRACTION" MUST DO

  Requirements (User's Words)

  "INDEXER ALWAYUS FUCKING CAPTURES BOTH... WE ONLY DO DUAL PASS BECAUSE WE FUCKING HAVE TO"

  Translation:
  1. Unconditional: No flags, no parameters, always both passes
  2. Fast: Seconds, not minutes (batch parsing = key)
  3. Complete: Both passes populate their respective tables fully
  4. Separate: Standard tables vs _jsx tables (different data for different purposes)

  What Each Pass Provides

  Pass 1 (Transformed):
  - Data flow for taint tracking: req.body → userInput → res.send(userInput)
  - Control flow graph for complexity analysis
  - Symbol declarations for dependency graphs
  - ORM queries for N+1 detection
  - Type annotations for type safety rules

  Pass 2 (Preserved):
  - JSX structure for component hierarchy analysis
  - Component patterns for React/Vue rules
  - Original JSX for template injection detection
  - Hook dependencies for exhaustive-deps rules

  What Gets Stored Where

  Standard Tables (Pass 1 data):
  - Used by: Taint analyzer, graph builder, general rules
  - Contains: Transformed AST data suitable for data flow analysis

  _jsx Tables (Pass 2 data):
  - Used by: React/Vue rules, component analysis, JSX-specific patterns
  - Contains: Preserved AST data with original JSX syntax

  Both Queryable:
  - Via unified views: function_returns_unified, symbols_unified
  - Or directly: Query specific table based on analysis needs

  ---
  QUICK REFERENCE

  Entry Point: theauditor/commands/index.py → calls IndexerOrchestrator.index()

  Key Files:
  - theauditor/indexer/__init__.py - Main orchestrator (860 lines)
  - theauditor/indexer/extractors/javascript.py - JS/TS extraction (452 lines)
  - theauditor/indexer/database.py - Database operations (1434 lines)
  - theauditor/ast_parser.py - TypeScript wrapper (varies)
  - theauditor/framework_detector.py - Framework detection (608 lines)

  Database: .pf/repo_index.db (SQLite)

  Output: .pf/readthis/ - AI-optimized chunks for LLM consumption