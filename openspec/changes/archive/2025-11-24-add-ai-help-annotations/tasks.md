# Tasks: AI-Optimized CLI Help Annotations

**ATOMIC IMPLEMENTATION GUIDE** - Every task has exact file, line, before/after code.

## 0. Verification (Pre-Implementation)

Per teamsop.md Prime Directive: Verify BEFORE implementation.

- [ ] 0.1 **Verify cli.py structure matches expectations**
  ```bash
  # Confirm VerboseGroup.COMMAND_CATEGORIES exists at line 34
  aud --help 2>&1 | head -5  # Should show "TheAuditor - Security..."
  ```
  **Expected**: `COMMAND_CATEGORIES` dict exists with `ai_context` field per category
  **Verified Location**: `theauditor/cli.py:34-90`

- [ ] 0.2 **Verify query.py docstring length**
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
  import ast
  with open('theauditor/commands/query.py') as f:
      tree = ast.parse(f.read())
  for node in ast.walk(tree):
      if isinstance(node, ast.FunctionDef) and node.name == 'query':
          doc = ast.get_docstring(node)
          print(f'query() docstring: {len(doc.splitlines())} lines')
  "
  ```
  **Expected**: ~900 lines (confirmed by reading file)
  **Target**: <150 lines after trimming

- [ ] 0.3 **Verify manual.py EXPLANATIONS dict structure**
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
  from theauditor.commands.manual import EXPLANATIONS
  print(f'Concepts: {list(EXPLANATIONS.keys())}')
  print(f'Total: {len(EXPLANATIONS)} concepts')
  "
  ```
  **Expected**: 12 concepts including taint, workset, fce, cfg, etc.
  **Verified Location**: `theauditor/commands/manual.py:8-650`

- [ ] 0.4 **Verify no CI scripts parse aud --help**
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor && rg "aud.*--help" .github/ scripts/ 2>/dev/null || echo "No matches"
  ```
  **Expected**: No matches or non-critical usage

## 1. Extend COMMAND_CATEGORIES Metadata

**File**: `theauditor/cli.py`
**Location**: Lines 34-90 (`VerboseGroup.COMMAND_CATEGORIES`)
**Change Type**: Extend existing dict values with `use_when` and `gives` fields

- [ ] 1.1 **Add use_when/gives to PRIMARY commands category**

  **BEFORE** (line 71-77):
  ```python
      'ADVANCED_QUERIES': {
          'title': 'ADVANCED QUERIES',
          'description': 'Direct database queries and impact analysis',
          'commands': ['explain', 'query', 'impact', 'refactor'],
          'ai_context': 'explain=comprehensive context, query=SQL-like symbol lookup, impact=blast radius, refactor=migration analysis.',
      },
  ```

  **AFTER**:
  ```python
      'ADVANCED_QUERIES': {
          'title': 'ADVANCED QUERIES',
          'description': 'Direct database queries and impact analysis',
          'commands': ['explain', 'query', 'impact', 'refactor'],
          'ai_context': 'explain=comprehensive context, query=SQL-like symbol lookup, impact=blast radius, refactor=migration analysis.',
          'command_meta': {
              'explain': {
                  'use_when': 'Need to understand code before editing',
                  'gives': 'Definitions, dependencies, hooks, call flows',
              },
              'query': {
                  'use_when': 'Need specific facts (Who calls X?, Where is Y?)',
                  'gives': 'Exact file:line locations and relationships',
              },
              'impact': {
                  'use_when': 'Assessing blast radius of changes',
                  'gives': 'Upstream/downstream dependency counts',
              },
              'refactor': {
                  'use_when': 'Detecting incomplete migrations',
                  'gives': 'Broken imports, orphan code locations',
              },
          },
      },
  ```

- [ ] 1.2 **Add use_when/gives to CORE_ANALYSIS category**

  **BEFORE** (line 41-45):
  ```python
      'CORE_ANALYSIS': {
          'title': 'CORE ANALYSIS',
          'description': 'Essential indexing and workset commands',
          'commands': ['full', 'workset'],  # 'index' deprecated (hidden)
          'ai_context': 'Foundation commands. full runs complete audit, workset filters scope.',
      },
  ```

  **AFTER**:
  ```python
      'CORE_ANALYSIS': {
          'title': 'CORE ANALYSIS',
          'description': 'Essential indexing and workset commands',
          'commands': ['full', 'workset'],
          'ai_context': 'Foundation commands. full runs complete audit, workset filters scope.',
          'command_meta': {
              'full': {
                  'run_when': 'First time, or after major changes',
              },
              'workset': {
                  'use_when': 'Need incremental analysis on file subset',
                  'gives': 'Filtered file list for targeted scans',
              },
          },
      },
  ```

- [ ] 1.3 **Add use_when/gives to SECURITY_SCANNING category**

  **BEFORE** (line 46-53):
  ```python
      'SECURITY_SCANNING': {
          'title': 'SECURITY SCANNING',
          'description': 'Vulnerability detection and taint analysis',
          'commands': ['detect-patterns', 'taint-analyze', 'boundaries', 'docker-analyze',
                      'detect-frameworks', 'rules', 'context', 'workflows', 'cdk', 'terraform', 'deadcode'],
          'ai_context': 'Security-focused analysis. detect-patterns=rules, taint-analyze=data flow, boundaries=control distance.',
      },
  ```

  **AFTER**:
  ```python
      'SECURITY_SCANNING': {
          'title': 'SECURITY SCANNING',
          'description': 'Vulnerability detection and taint analysis',
          'commands': ['detect-patterns', 'taint-analyze', 'boundaries', 'docker-analyze',
                      'detect-frameworks', 'rules', 'context', 'workflows', 'cdk', 'terraform', 'deadcode'],
          'ai_context': 'Security-focused analysis. detect-patterns=rules, taint-analyze=data flow, boundaries=control distance.',
          'command_meta': {
              'detect-patterns': {
                  'use_when': 'Need security vulnerability scan',
                  'gives': '200+ rule findings with file:line',
              },
              'taint-analyze': {
                  'use_when': 'Need data flow analysis',
                  'gives': 'Source-to-sink paths with vuln type',
              },
              'boundaries': {
                  'use_when': 'Checking trust boundary enforcement',
                  'gives': 'Trust boundary violations',
              },
          },
      },
  ```

- [ ] 1.4 **Add use_when/gives to remaining categories**

  Apply same pattern to:
  - `PROJECT_SETUP` (line 35-40): setup-ai -> run_when: "Once per project"
  - `DEPENDENCIES` (line 54-58): deps -> use_when: "Need CVE check"
  - `CODE_QUALITY` (line 59-64): lint, cfg, graph -> appropriate metadata
  - `DATA_REPORTING` (line 65-70): fce, report, structure -> appropriate metadata
  - `UTILITIES` (line 84-89): manual -> use_when: "Need concept explanation"

## 2. Modify format_help() to Display Annotations

**File**: `theauditor/cli.py`
**Location**: Lines 102-119 (`VerboseGroup.format_help()`)
**Change Type**: Modify the command display loop to inject annotations

- [ ] 2.1 **Modify format_help() to show USE WHEN/GIVES**

  **BEFORE** (line 102-119):
  ```python
      for category_id, category_data in self.COMMAND_CATEGORIES.items():
          formatter.write_text(f"  {category_data['title']}:")
          for cmd_name in category_data['commands']:
              if cmd_name not in registered:
                  continue
              cmd = registered[cmd_name]
              # Get first sentence, truncate at word boundary if too long
              first_line = (cmd.help or "").split('\n')[0].strip()
              period_idx = first_line.find('.')
              if period_idx > 0:
                  short_help = first_line[:period_idx]
              else:
                  short_help = first_line
              # Truncate at word boundary if >50 chars
              if len(short_help) > 50:
                  short_help = short_help[:50].rsplit(' ', 1)[0] + "..."
              formatter.write_text(f"    {cmd_name:20s} {short_help}")
          formatter.write_paragraph()
  ```

  **AFTER**:
  ```python
      for category_id, category_data in self.COMMAND_CATEGORIES.items():
          formatter.write_text(f"  {category_data['title']}:")
          for cmd_name in category_data['commands']:
              if cmd_name not in registered:
                  continue
              cmd = registered[cmd_name]
              # Get first sentence, truncate at word boundary if too long
              first_line = (cmd.help or "").split('\n')[0].strip()
              period_idx = first_line.find('.')
              if period_idx > 0:
                  short_help = first_line[:period_idx]
              else:
                  short_help = first_line
              # Truncate at word boundary if >50 chars
              if len(short_help) > 50:
                  short_help = short_help[:50].rsplit(' ', 1)[0] + "..."
              formatter.write_text(f"    {cmd_name:20s} {short_help}")

              # Add AI routing annotations if available
              cmd_meta = category_data.get('command_meta', {}).get(cmd_name, {})
              if 'use_when' in cmd_meta:
                  formatter.write_text(f"                          > USE WHEN: {cmd_meta['use_when']}")
              elif 'run_when' in cmd_meta:
                  formatter.write_text(f"                          > RUN: {cmd_meta['run_when']}")
              if 'gives' in cmd_meta:
                  formatter.write_text(f"                          > GIVES: {cmd_meta['gives']}")

          formatter.write_paragraph()
  ```

  **WHY**: The 26-space indent aligns annotations under the command description.

## 3. Add Anti-Patterns to explain.py

**File**: `theauditor/commands/explain.py`
**Location**: Lines 87-153 (docstring of `explain()` function)
**Change Type**: Insert ANTI-PATTERNS and OUTPUT FORMAT sections before closing triple-quote

- [ ] 3.1 **Add ANTI-PATTERNS section to explain.py docstring**

  **INSERT BEFORE** line 153 (the closing `"""`):
  ```python
    \b
    ANTI-PATTERNS (Do NOT Do This)
    ------------------------------
      X  aud explain --symbol foo
         -> Just use: aud explain foo (auto-detects target type)

      X  aud explain .
         -> Use 'aud structure' for project overview

      X  Running 'aud query' before 'aud explain'
         -> Always try 'explain' first - it returns more comprehensive context

      X  aud explain --format json | jq '.symbols'
         -> JSON structure varies by target type, check OUTPUT FORMAT below

    \b
    OUTPUT FORMAT
    -------------
    Text mode (file target):
      === FILE: src/auth.py ===
      SYMBOLS DEFINED (5):
        - authenticate (function) line 42-58
        - User (class) line 10-40
      DEPENDENCIES (3):
        - src/utils/crypto.py
        - src/db/users.py
      INCOMING CALLS (2):
        - src/api/login.py:15 login_handler() -> authenticate

    JSON mode (--format json):
      {
        "target": "src/auth.py",
        "target_type": "file",
        "symbols": [{"name": "authenticate", "type": "function", "line": 42}],
        "imports": ["src/utils/crypto.py"],
        "incoming_calls": [{"file": "src/api/login.py", "line": 15, ...}]
      }
  ```

  **EXACT LOCATION**: Insert at line 152, before the `"""` on line 153.

## 4. Trim query.py Docstring (MAJOR CHANGE)

**File**: `theauditor/commands/query.py`
**Location**: Lines 56-957 (docstring of `query()` function)
**Change Type**: REPLACE entire docstring with trimmed version

- [ ] 4.1 **Replace query() docstring with trimmed version**

  **NEW DOCSTRING** (replace lines 56-957):
  ```python
  def query(symbol, file, api, component, variable, pattern, category, search, list_mode,
            list_symbols, symbol_filter, path_filter,
            show_callers, show_callees, show_dependencies, show_dependents,
            show_tree, show_hooks, show_data_deps, show_flow, show_taint_flow,
            show_api_coverage, type_filter, include_tables,
            depth, output_format, save, show_code):
      """Query code relationships from indexed database.

      Direct SQL queries over TheAuditor's indexed code relationships.
      NO file reading, NO parsing - just exact database lookups in <10ms.

      QUERY TARGETS:
          --symbol NAME      Query function/class/variable by name
          --file PATH        Query file dependencies (partial match OK)
          --api ROUTE        Query API endpoint by route
          --component NAME   Query React/Vue component
          --variable NAME    Query variable for data flow

      QUERY ACTIONS:
          --show-callers     Who calls this symbol?
          --show-callees     What does this symbol call?
          --show-dependencies  What does this file import?
          --show-dependents    Who imports this file?
          --show-tree        Component children hierarchy

      MODIFIERS:
          --depth N          Traversal depth 1-5 (default: 1)
          --format FORMAT    text|json|tree (default: text)
          --show-code        Include source snippets

      CRITICAL - Symbol Canonicalization:
          Class methods are indexed as ClassName.methodName.
          If --symbol handleRequest returns nothing, try:
          aud query --symbol Controller.handleRequest

      ANTI-PATTERNS (Do NOT Do This)
      ------------------------------
        X  aud query "how does auth work?"
           -> Use 'aud explain' or 'aud manual' for conceptual questions

        X  aud query --file "main.py"
           -> Use 'aud explain main.py' for file summaries

        X  aud query --symbol "foo" (no action flag)
           -> Always specify --show-callers or --show-callees

        X  aud query --symbol handleRequest
           -> Use qualified name: aud query --symbol Controller.handleRequest

      EXAMPLES (Copy These Patterns)
      ------------------------------
        # Find where a function is used
        aud query --symbol authenticate --show-callers --depth 2

        # See what a function calls
        aud query --symbol ProcessOrder --show-callees

        # Find class method (ALWAYS use qualified name)
        aud query --symbol OrderController.create --show-callers

        # JSON output for AI consumption
        aud query --symbol validate --show-callers --format json

        # File dependency analysis
        aud query --file src/auth.ts --show-dependents

        # API endpoint lookup
        aud query --api "/users/:id"

      OUTPUT FORMAT
      -------------
      Text mode:
        Symbol Definitions (1):
          1. authenticateUser
             Type: function
             File: src/auth/service.ts:42-58

        Callers (5):
          1. src/middleware/auth.ts:23
             authMiddleware -> authenticateUser

      JSON mode (--format json):
        [
          {
            "caller_file": "src/middleware/auth.ts",
            "caller_line": 23,
            "caller_function": "authMiddleware",
            "callee_function": "authenticateUser"
          }
        ]

      PREREQUISITES:
          aud full              Required - builds repo_index.db
          aud graph build       Optional - only for --show-dependencies

      TROUBLESHOOTING:
          Run: aud manual troubleshooting
          Run: aud manual database

      See also: aud explain, aud manual database, aud manual troubleshooting
      """
  ```

  **LINE COUNT**: ~95 lines (down from ~900)
  **REMOVED**: DATABASE SCHEMA, ARCHITECTURE, PERFORMANCE, MANUAL SQL sections
  **MOVED TO**: `aud manual database`, `aud manual troubleshooting`, `aud manual architecture`

## 5. Add New Concepts to manual.py

**File**: `theauditor/commands/manual.py`
**Location**: Lines 8-650 (`EXPLANATIONS` dict)
**Change Type**: Add 3 new entries to the dict

- [ ] 5.1 **Add 'database' concept to EXPLANATIONS**

  **INSERT AFTER** line 649 (before the closing `}`):
  ```python
      "database": {
          "title": "Database Schema Reference",
          "summary": "Tables, indexes, and query patterns for advanced usage",
          "explanation": """
  TheAuditor stores all indexed data in SQLite databases. This reference
  covers the schema for advanced queries and debugging.

  DATABASE LOCATIONS:
      .pf/repo_index.db     Main code index (250 tables, 200k+ rows)
      .pf/graphs.db         Import/call graph (4 tables)

  KEY TABLES:
      symbols (33k rows)           Function/class definitions
      symbols_jsx (8k rows)        JSX component definitions
      function_call_args (13k)     Function calls with arguments
      variable_usage (57k)         Variable references
      api_endpoints (185)          REST API routes
      react_components (1k)        React component metadata
      react_hooks (667)            Hook usage
      edges (7.3k)                 Import/call graph edges
      assignments (42k)            Variable assignments
      assignment_sources           Junction: assignment -> source vars

  QUERYING FROM PYTHON:
      import sqlite3
      conn = sqlite3.connect('.pf/repo_index.db')
      cursor = conn.cursor()

      # See all tables
      cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
      print([row[0] for row in cursor.fetchall()])

      # Find all functions in a file
      cursor.execute('''
          SELECT name, type, line FROM symbols
          WHERE file LIKE '%auth.py%'
          ORDER BY line
      ''')

      # Find callers of a function
      cursor.execute('''
          SELECT caller_file, caller_line, caller_function
          FROM function_call_args
          WHERE callee_function = 'authenticate'
      ''')

  INDEXES FOR PERFORMANCE:
      symbols.name                 O(log n) symbol lookup
      function_call_args.callee    O(log n) caller lookup
      edges.source, edges.target   O(log n) dependency lookup

  WHY QUERY MANUALLY:
      - Custom analysis not supported by CLI
      - Debugging indexing issues
      - Exporting data for external tools
      - Learning database structure
  """
      },
  ```

- [ ] 5.2 **Add 'troubleshooting' concept to EXPLANATIONS**

  **INSERT AFTER** the 'database' entry:
  ```python
      "troubleshooting": {
          "title": "Troubleshooting Guide",
          "summary": "Common errors and solutions for all commands",
          "explanation": """
  Common errors and their solutions for TheAuditor commands.

  ERROR: "No .pf directory found"
      CAUSE: Have not run aud full yet
      FIX: Run: aud full
      EXPLANATION: All commands need the indexed database

  ERROR: "Graph database not found"
      CAUSE: Have not run aud graph build
      FIX: Run: aud graph build
      EXPLANATION: --show-dependencies needs graphs.db

  SYMPTOM: Empty results but symbol exists in code
      CAUSE 1: Typo in symbol name (case-sensitive)
      FIX: Run aud query --symbol foo to see if it exists

      CAUSE 2: Database stale (code changed since last index)
      FIX: Run: aud full (regenerates database)

      CAUSE 3: Unqualified method name
      FIX: Use ClassName.methodName instead of just methodName
      EXAMPLE: aud query --symbol Controller.handleRequest

  SYMPTOM: Slow queries (>50ms)
      CAUSE: Large project + high depth (>3)
      FIX: Reduce --depth to 1-2
      EXPLANATION: depth=5 on 100k LOC traverses 10k+ nodes

  SYMPTOM: Missing expected results
      CAUSE: Dynamic calls (obj[variable]()) not indexed
      FIX: Use taint analysis for dynamic dispatch
      EXPLANATION: Static analysis cannot resolve all dynamic behavior

  SYMPTOM: UnicodeEncodeError on Windows
      CAUSE: Emoji characters in output
      FIX: This is a bug - report it. ASCII-only output is required.

  GENERAL DEBUGGING:
      1. Check database exists: ls -la .pf/repo_index.db
      2. Check table has data: aud query --symbol "*" --format json | head
      3. Run with verbose: THEAUDITOR_DEBUG=1 aud query ...
  """
      },
  ```

- [ ] 5.3 **Add 'architecture' concept to EXPLANATIONS**

  **INSERT AFTER** the 'troubleshooting' entry:
  ```python
      "architecture": {
          "title": "CLI Architecture",
          "summary": "How query engine, databases, and commands interact",
          "explanation": """
  Understanding TheAuditor's architecture for advanced usage.

  TWO DATABASES:

  repo_index.db (181MB typical):
      - Raw extracted facts from AST parsing
      - Updated: Every aud full (regenerated fresh)
      - Used by: Everything (rules, taint, FCE, queries)
      - Tables: 250 normalized tables

  graphs.db (126MB typical):
      - Pre-computed graph structures
      - Updated: During aud full via aud graph build
      - Used by: Graph commands only (viz, analyze)
      - Tables: 4 tables (nodes, edges, analysis_results, metadata)

  WHY SEPARATE:
      - Different query patterns (point lookups vs graph traversal)
      - Selective loading (queries don't need graph)
      - Standard data warehouse design

  EXTRACTION PIPELINE:
      Source Code
          |
          v
      tree-sitter (AST parsing)
          |
          v
      Language Extractors (Python, JS, TS, etc.)
          |
          v
      Database Manager (batch inserts)
          |
          v
      repo_index.db (SQLite)

  QUERY ARCHITECTURE:
      User Request
          |
          v
      CLI Command (commands/*.py)
          |
          v
      CodeQueryEngine (context/query.py)
          |
          v
      Direct SQL SELECT (no ORM)
          |
          v
      SQLite (repo_index.db)
          |
          v
      Formatter (text/json)
          |
          v
      Output

  SCHEMA NORMALIZATION (v1.2+):
      OLD: JSON TEXT columns with LIKE queries (slow)
      NEW: Junction tables with JOIN queries (fast)

      Example:
          OLD: assignments.source_vars = '["x", "y"]' (JSON)
          NEW: assignment_sources table with 2 rows

      Benefits:
          - 10x faster queries (indexed)
          - Can use JOINs
          - Type-safe queries
  """
      },
  ```

## 6. Add ASCII Enforcement Test

**File**: `tests/test_cli_ascii.py` (NEW FILE)
**Change Type**: Create new test file

- [ ] 6.1 **Create ASCII enforcement test**

  **NEW FILE**: `tests/test_cli_ascii.py`
  ```python
  """Test that all CLI docstrings are ASCII-only for Windows CP1252 compatibility.

  CLAUDE.md ABSOLUTE RULE: No emojis in Python output. Windows Command Prompt
  uses CP1252 encoding which cannot handle emoji characters.
  """
  import ast
  import glob
  import pytest


  def test_cli_docstrings_ascii_only():
      """Ensure all CLI command docstrings are ASCII-only."""
      cli_files = glob.glob('theauditor/commands/*.py') + ['theauditor/cli.py']

      for filepath in cli_files:
          with open(filepath, 'r', encoding='utf-8') as f:
              content = f.read()

          try:
              tree = ast.parse(content)
          except SyntaxError:
              continue  # Skip files with syntax errors

          for node in ast.walk(tree):
              if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                  docstring = ast.get_docstring(node)
                  if docstring:
                      try:
                          docstring.encode('ascii')
                      except UnicodeEncodeError as e:
                          # Find the offending character
                          for i, char in enumerate(docstring):
                              if ord(char) > 127:
                                  context = docstring[max(0,i-20):i+20]
                                  pytest.fail(
                                      f"Non-ASCII character in {filepath}:{node.lineno}\n"
                                      f"Character: {char!r} (U+{ord(char):04X})\n"
                                      f"Context: ...{context}..."
                                  )


  def test_cli_help_output_ascii():
      """Ensure aud --help output is ASCII-only."""
      import subprocess
      result = subprocess.run(
          ['aud', '--help'],
          capture_output=True,
          text=True,
          timeout=30
      )
      output = result.stdout + result.stderr

      for i, char in enumerate(output):
          if ord(char) > 127:
              context = output[max(0,i-20):i+20]
              pytest.fail(
                  f"Non-ASCII character in aud --help output\n"
                  f"Character: {char!r} (U+{ord(char):04X})\n"
                  f"Context: ...{context}..."
              )
  ```

## 7. Validation

- [ ] 7.1 **Verify root help line count**
  ```bash
  aud --help 2>&1 | wc -l
  # Target: <80 lines
  ```

- [ ] 7.2 **Verify query help line count**
  ```bash
  aud query --help 2>&1 | wc -l
  # Target: <150 lines (down from ~900)
  ```

- [ ] 7.3 **Verify new manual concepts work**
  ```bash
  aud manual database
  aud manual troubleshooting
  aud manual architecture
  aud manual --list  # Should show 15 concepts (was 12)
  ```

- [ ] 7.4 **Run ASCII test**
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -m pytest tests/test_cli_ascii.py -v
  ```

- [ ] 7.5 **Verify annotations appear in help**
  ```bash
  aud --help 2>&1 | grep "USE WHEN"
  # Should show USE WHEN annotations for primary commands
  ```

- [ ] 7.6 **Test AI routing with sample prompts**
  Test these prompts with an AI agent:
  1. "I need to find all callers of validateUser"
     - Expected: `aud query --symbol validateUser --show-callers`
  2. "Give me context about the auth module"
     - Expected: `aud explain src/auth/` or `aud explain auth`
  3. "What's the project structure?"
     - Expected: `aud structure`

## Summary of File Changes

| File | Lines Changed | Change Summary |
|------|---------------|----------------|
| `theauditor/cli.py` | ~50 lines added | Add `command_meta` to categories, modify `format_help()` |
| `theauditor/commands/explain.py` | ~40 lines added | Add ANTI-PATTERNS, OUTPUT FORMAT to docstring |
| `theauditor/commands/query.py` | ~800 lines removed | Replace 900-line docstring with 95-line version |
| `theauditor/commands/manual.py` | ~150 lines added | Add database, troubleshooting, architecture concepts |
| `tests/test_cli_ascii.py` | ~50 lines (new) | ASCII enforcement test |

**Total Net Change**: ~-550 lines (significant reduction due to query.py trim)
