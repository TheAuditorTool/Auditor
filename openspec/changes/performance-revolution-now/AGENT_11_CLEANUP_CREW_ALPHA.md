=== AGENT #11 REPORT: CLEANUP CREW ALPHA ===

SECTION 1: FILE STRUCTURE AUDIT
  - Total Python files: 344
  - Total JavaScript files: 0 (JavaScript extractors use .js extension but in python/javascript subdirs)
  - Files in investigation report: ~30-40 major files mentioned
  - Uncovered files: ~300+ files NOT explicitly mentioned in Agents #1-10

Major uncovered files NOT in investigation:
  - C:\Users\santa\Desktop\TheAuditor\theauditor\cache\ast_cache.py (209 lines - AST caching)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\session\*.py (7 files - session management)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\planning\*.py (4 files - planning system)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\linters\linters.py (27KB - external linter orchestration)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\lsp\rust_analyzer_client.py (11KB - LSP integration)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\refactor\profiles.py (12KB - refactoring profiles)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\aws_cdk\analyzer.py (9KB - CDK analysis)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\terraform\*.py (3 files - Terraform support)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\graphql\*.py (3 files - GraphQL graph building)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\toolboxes\*.py (2 files - toolbox management)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\insights\*.py (5 files + subdirs - ML insights)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\*.js (10 JS files - 263KB total)
  - C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python\*.py (14 files - 304KB total)

SECTION 2: UNCOVERED MODULES

theauditor/utils/:
  - Files: 11 Python files
  - Performance-critical: YES
    * memory.py (175 lines) - Memory limit detection using ctypes on Windows
    * meta_findings.py (314 lines) - Finding formatters (pure Python, low overhead)
    * helpers.py, toolbox.py, temp_manager.py (utility functions)
  - Issues found:
    * memory.py uses ctypes.windll.kernel32 on Windows (syscall overhead)
    * No caching of memory detection results - recalculates every call
    * MINOR overhead - called once at startup

theauditor/extractors/ (now theauditor/indexer/extractors/):
  - Language extractors: Python, JavaScript/TypeScript, Rust, GraphQL, Terraform, Docker, Prisma, GitHub Actions, SQL, Generic
  - Uncovered extractors:
    * graphql.py (14KB) - NOT mentioned in investigation
    * github_actions.py (13KB) - NOT mentioned in investigation
    * prisma.py (7KB) - NOT mentioned in investigation
    * sql.py (3KB) - NOT mentioned in investigation
    * rust.py (8KB) - mentioned minimally
  - Performance impact: Each extractor runs on every matching file

theauditor/reporting/:
  - Files: DIRECTORY DOES NOT EXIST
  - Report generation: Handled in commands/report.py and commands/summary.py
  - Overhead: NEGLIGIBLE (only runs on-demand via `aud report` or `aud summary`)

theauditor/config/:
  - Config loading:
    * config.py (41 lines) - Minimal mypy config appender
    * config_runtime.py (160 lines) - Runtime config with DEFAULTS dict
  - Overhead: NEGLIGIBLE
    * Loaded once at module import
    * Uses deep copy of DEFAULTS dict (cheap for small dict)
    * JSON loading from .pf/config.json is optional and cached

theauditor/cache/:
  - Files: ast_cache.py (209 lines)
  - Purpose: Persistent AST caching to avoid re-parsing unchanged files
  - Performance:
    * POSITIVE impact - reduces parsing overhead
    * Uses SHA256 hash keys, JSON serialization
    * Has eviction logic (_evict_if_needed) that runs after EVERY cache write
    * Eviction checks file count and size limits on EVERY write - potential O(n) overhead
  - ISSUE FOUND: Cache eviction runs synchronously after every write, sorting all cache files

theauditor/session/:
  - Files: 7 Python files (97KB total)
  - Purpose: Session analysis and workflow compliance tracking
  - Performance:
    * store.py - Dual-write to DB + JSON (310 lines)
    * analyzer.py - Session analysis (12KB)
    * diff_scorer.py - Diff risk scoring (10KB)
    * workflow_checker.py - Workflow compliance (7KB)
  - Overhead: MINOR - only runs when `aud session` commands are used
  - Database: Separate .pf/ml/session_history.db (not main repo_index.db)

theauditor/planning/:
  - Files: 4 files (81KB total)
  - Purpose: Planning system for change management
  - Overhead: NEGLIGIBLE - only runs with `aud planning` commands

theauditor/linters/:
  - Files: linters.py (27KB)
  - Purpose: External linter orchestration (ESLint, Ruff, Clippy)
  - Overhead: HIGH when used
    * Spawns subprocess for each linter batch (timeout: 300s)
    * BATCH_SIZE = 100 files per batch
    * Queries database for files by extension
  - Performance impact: Only when `aud lint` is called

theauditor/lsp/:
  - Files: rust_analyzer_client.py (11KB)
  - Purpose: Rust LSP integration
  - Overhead: ONLY for Rust projects with `aud lsp` commands

theauditor/refactor/:
  - Files: profiles.py (12KB)
  - Purpose: Refactoring profile management
  - Overhead: NEGLIGIBLE - only for refactoring commands

theauditor/aws_cdk/:
  - Files: analyzer.py (9KB)
  - Purpose: AWS CDK infrastructure analysis
  - Overhead: ONLY for CDK projects

theauditor/terraform/:
  - Files: 3 files (analyzer.py, graph.py, parser.py)
  - Purpose: Terraform infrastructure analysis
  - Overhead: ONLY for Terraform projects

theauditor/graphql/:
  - Files: 3 files (builder.py 25KB, querier.py 7KB, visualizer.py 4KB)
  - Purpose: GraphQL schema graph building
  - Performance:
    * builder.py uses os.walk() to discover GraphQL files
    * Builds separate graph structure from schema files
  - Overhead: ONLY when GraphQL files present and `aud graphql` used

theauditor/toolboxes/:
  - Files: 2 files (base.py, rust.py)
  - Purpose: Toolbox base classes
  - Overhead: NEGLIGIBLE

theauditor/insights/:
  - Files: 5 files + subdirectories (204KB total)
  - Purpose: ML-based insights and analysis
  - Files:
    * ml.py (66KB) - ML suggestions and scoring
    * impact_analyzer.py (24KB) - Impact analysis
    * semantic_context.py (29KB) - Semantic analysis
    * graph.py (16KB) - Graph insights
    * taint.py (17KB) - Taint insights
  - Overhead: ONLY when insights commands are used

theauditor/ast_extractors/:
  - Subdirectories: javascript/, python/, base.py, *_impl.py files
  - JavaScript extractors: 10 .js files (263KB total)
    * batch_templates.js (46KB)
    * data_flow.js (46KB)
    * core_language.js (39KB)
    * cfg_extractor.js (28KB)
    * framework_extractors.js (27KB)
    * security_extractors.js (27KB)
    * module_framework.js (25KB)
    * angular_extractors.js (11KB)
    * sequelize_extractors.js (6KB)
    * bullmq_extractors.js (4KB)
  - Python extractors: 14 .py files (304KB total)
    * core_extractors.py (42KB)
    * validation_extractors.py (28KB)
    * task_graphql_extractors.py (27KB)
    * django_web_extractors.py (24KB)
    * orm_extractors.py (20KB)
    * flask_extractors.py (19KB)
    * security_extractors.py (17KB)
    * testing_extractors.py (14KB)
    * django_advanced_extractors.py (13KB)
    * cfg_extractor.py (12KB)
    * type_extractors.py (11KB)
    * framework_extractors.py (5KB)
    * async_extractors.py (5KB)
    * cdk_extractor.py (9KB)
  - Performance: These are HOT PATH - every Python/JS file runs through these
  - NOT covered in investigation report

SECTION 3: CROSS-MODULE ANTI-PATTERNS

Nested loops (O(n²) potential):
  - Count: 131 instances found
  - Critical instances (hot path):
    1. theauditor/ast_extractors/python/django_web_extractors.py - Form/ModelForm base checking
    2. Multiple instances in ast_patterns.py, ast_parser.py
    3. Commands that iterate over findings/files
    4. NOT all are performance-critical - many are one-time operations
  - Priority: P2 (need manual review to identify hot path instances)

ALL tree walks (not just ast.walk):
  - Count: 105 instances
  - Types:
    * ast.walk() - NOT counted in this grep
    * os.walk() - 7 instances:
      1. commands/rules.py (2x) - Walking patterns/rules directories
      2. graph/builder.py (2x) - File discovery
      3. indexer/core.py (2x) - Main file walker
      4. indexer_compat.py (2x) - Compatibility layer
      5. test_frameworks.py (1x) - Test discovery
  - Uncovered walks beyond investigation:
    * os.walk() in graph/builder.py (GraphQL file discovery)
    * os.walk() in test_frameworks.py (test discovery)
  - Priority: P1 for os.walk() calls (indexer/core.py already in investigation)

ALL LIKE wildcards:
  - Count: 54 instances
  - Locations beyond GraphQL rules:
    * session/store.py line 229: LIKE '%{file_path}%' for JSON search in diffs_scored
    * Various rules files using LIKE for pattern matching
  - Priority: P2 (most are in rules, which are already flagged)

os.walk() usage breakdown:
  1. commands/rules.py - Walking .pf/patterns/ and rules/ directories (NOT hot path)
  2. graph/builder.py - Walking project to find files (HOT PATH if GraphQL used)
  3. indexer/core.py - Main file walker (HOTTEST PATH - in investigation)
  4. test_frameworks.py - Test discovery (NOT hot path)

SECTION 4: IMPORT DEPENDENCIES

theauditor/__init__.py:
  - Heavy imports at module load: NONE
  - Only imports: importlib.metadata.version
  - Overhead: NEGLIGIBLE (1 line function, 6 lines total)

Circular imports:
  - Found: ❌ NO circular imports detected at module level
  - Test: `python -c "import theauditor"` succeeded without errors

Wildcard imports (import *):
  - Count: 11 instances
  - Locations:
    1. graph/insights.py: from theauditor.insights.graph import *
    2. ml.py: from theauditor.insights.ml import *
    3. taint/insights.py: from theauditor.insights.taint import *
    4. taint_analyzer.py: from theauditor.taint import *
  - Risk: LOW
    * All are in insights modules (not hot path)
    * Most are string patterns in framework_registry.py (not actual imports)
  - Note: grep also found string literals in framework_registry.py (false positives)

SECTION 5: CONFIGURATION & SETUP

Configuration loading:
  - File: C:\Users\santa\Desktop\TheAuditor\theauditor\config_runtime.py
  - Performance: FAST
    * Deep copy of DEFAULTS dict (160 lines of nested dicts)
    * Optional JSON load from .pf/config.json (with try/except)
    * Environment variable overrides with type casting
    * Loaded once per module import
  - Dynamic config: NO
    * All config loaded at startup
    * No per-file or per-run dynamic loading

config.py:
  - File: C:\Users\santa\Desktop\TheAuditor\theauditor\config.py
  - Purpose: Mypy config management
  - Performance: FAST (only runs for `aud init-config` command)

SECTION 6: TEST INFRASTRUCTURE

tests/ directory:
  - Structure:
    * 29 test files (769KB total)
    * fixtures/ subdirectory with test projects
    * integration/ subdirectory
    * test_rules/ subdirectory
    * Multiple markdown docs explaining test coverage
  - Performance tests: ❌ NO
    * No files named *performance*, *benchmark*, *profile*
    * ONLY functional/unit tests found
  - Fixture projects: Multiple projects in tests/fixtures/
    * node-sequelize-orm/
    * Python projects
    * Terraform projects
    * Others
  - Validation coverage: Extensive
    * test_extractors.py (38KB)
    * test_python_framework_extraction.py (58KB)
    * test_node_framework_extraction.py (30KB)
    * test_edge_cases.py (38KB)
    * Many others

Investigation claim verification:
  - "No profiling/metrics" - ✅ CONFIRMED
    * No performance tests found
    * No benchmarking infrastructure
    * No profiling tooling integrated

SECTION 7: GAPS IN INVESTIGATION REPORT

Files NOT covered in Agents #1-10:

1. AST Extractors (CRITICAL GAP - HOT PATH):
   - C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\javascript\*.js (10 files, 263KB)
   - C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python\*.py (14 files, 304KB)
   - These run on EVERY Python/JS file during indexing
   - Includes complex operations:
     * batch_templates.js (46KB) - Template extraction
     * data_flow.js (46KB) - Data flow analysis
     * core_extractors.py (42KB) - Core Python extraction
     * validation_extractors.py (28KB) - Validation logic
   - PRIORITY: P0 (HOT PATH, not mentioned at all)

2. Cache Management:
   - C:\Users\santa\Desktop\TheAuditor\theauditor\cache\ast_cache.py
   - Issue: _evict_if_needed() runs after EVERY cache write
   - Eviction algorithm sorts ALL cache files by mtime (O(n log n))
   - PRIORITY: P1 (performance bug in caching layer)

3. Session Management:
   - C:\Users\santa\Desktop\TheAuditor\theauditor\session\*.py (7 files)
   - Dual-write to database + JSON
   - LIKE '%{file_path}%' wildcard search in diffs_scored JSON column
   - PRIORITY: P2 (only used by `aud session` commands)

4. GraphQL Graph Builder:
   - C:\Users\santa\Desktop\TheAuditor\theauditor\graphql\builder.py
   - Uses os.walk() to discover GraphQL files
   - Builds separate graph structure
   - PRIORITY: P2 (only for GraphQL projects)

5. Linter Orchestration:
   - C:\Users\santa\Desktop\TheAuditor\theauditor\linters\linters.py
   - Spawns subprocesses for external linters
   - 300s timeout per batch
   - PRIORITY: P2 (only when `aud lint` is used)

6. Generated Accessors:
   - C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\generated_accessors.py (3,507 lines)
   - Auto-generated from schema
   - Every query builds dict with zip() - O(n) for every row
   - PRIORITY: P1 (if used in hot path - need to verify)

7. Backup Files Still Present:
   - theauditor/taint/backup/*.bak and *.backup (18 files, 13,916 lines)
   - These are OLD taint implementation files
   - NOT used in current code (refactored to schema-driven)
   - PRIORITY: P3 (cleanup only, no performance impact)

8. Large Critical Files Not Fully Covered:
   - theauditor/venv_install.py (50KB, 1,243 lines)
   - theauditor/pipelines.py (83KB, 1,694 lines)
   - theauditor/fce.py (77KB, 1,842 lines)
   - These are mentioned but not deeply analyzed

9. Subprocess Usage:
   - Count: 47 subprocess.run/Popen/call invocations
   - Used in: linters, venv_install, toolboxes
   - PRIORITY: P2 (external process overhead)

10. File Operations:
    - Count: 331 open() calls across codebase
    - Count: 372 json.load/json.dump operations
    - Count: 1,377 fetchall() database calls
    - PRIORITY: Need profiling to identify hot path file I/O

SECTION 8: ADDITIONAL FINDINGS

1. Generated Code:
   - generated_accessors.py is 3,507 lines of auto-generated accessor classes
   - Every row returned uses dict(zip(...)) pattern
   - If these accessors are used in hot path, this is O(n) overhead for every row
   - Recommendation: Profile to see if these are called frequently

2. TODO/FIXME Comments:
   - Count: Only 13 TODO/FIXME/XXX/HACK comments
   - This is VERY LOW for 344 files - indicates clean codebase
   - No obvious "FIXME: performance" comments

3. Taint Backup Files:
   - 18 .bak/.backup files in taint/backup/ (13,916 lines total)
   - These are remnants of the pre-refactor taint system
   - NOT loaded or used (confirmed by checking imports)
   - Can be safely deleted
   - PRIORITY: P3 (cleanup only)

4. Auto-Generated Files:
   - generated_accessors.py (3,507 lines)
   - generated_types.py (1,233 lines)
   - generated_cache.py (likely exists)
   - These are auto-generated from schema - changes should be made to schema, not these files

5. Database Query Patterns:
   - 1,377 fetchall() calls across codebase
   - Most are in rules, extractors, and queries
   - Need profiling to identify which are in hot path
   - Investigation covered main database issues (N+1, missing indexes)

6. Import Time:
   - theauditor/__init__.py is minimal (6 lines)
   - No heavy imports at package level
   - Good practice for CLI tool

7. Windows-Specific Code:
   - utils/memory.py uses ctypes for Windows memory detection
   - Platform detection using platform.system()
   - Proper cross-platform handling

8. JavaScript Extractors:
   - 10 .js files (not .py) in ast_extractors/javascript/
   - These are Node.js scripts called from Python
   - Subprocess overhead for every JS file
   - NOT mentioned in investigation report
   - PRIORITY: P0 (subprocess per file is EXPENSIVE)

SECTION 9: PRIORITY ASSESSMENT

High-priority gaps (P0): 3 items
  1. AST Extractors (ast_extractors/javascript/*.js and ast_extractors/python/*.py)
     - 567KB of code running on EVERY Python/JS file
     - Includes subprocess calls to Node.js for JavaScript extraction
     - NOT mentioned in investigation at all
     - CRITICAL HOT PATH

  2. JavaScript Extractor Subprocess Overhead
     - 10 .js files called via subprocess for EVERY JS/TS file
     - Each file spawns Node.js process
     - Potential for massive overhead on JS-heavy projects

  3. Generated Accessor dict(zip()) Pattern
     - generated_accessors.py uses dict(zip()) for EVERY row
     - If used in hot path, this is O(n) overhead
     - Need profiling to verify

Medium-priority gaps (P1): 4 items
  1. AST Cache Eviction Logic
     - _evict_if_needed() runs after EVERY cache write
     - Sorts all cache files (O(n log n)) synchronously
     - Should be async or batched

  2. os.walk() in graph/builder.py
     - GraphQL file discovery uses os.walk()
     - Duplicate of indexer/core.py walk
     - Should use database query instead

  3. LIKE '%pattern%' in session/store.py
     - JSON column search for file paths
     - Should use proper JSON extraction or separate table

  4. Subprocess Usage (47 calls)
     - Linters, venv_install, toolboxes
     - Need profiling to identify hot path subprocess calls

Low-priority gaps (P2): 5 items
  1. Session Management Dual-Write
     - Only used by `aud session` commands
     - Not in main analysis flow

  2. Linter Orchestration
     - Only runs with `aud lint`
     - Not in main analysis flow

  3. Nested Loops (131 instances)
     - Need manual review to identify hot path
     - Many are one-time setup operations

  4. Large Files (pipelines.py, fce.py, venv_install.py)
     - Mentioned but not deeply analyzed
     - Need code review for optimization opportunities

  5. Wildcard Imports (4 actual instances)
     - All in insights modules (not hot path)
     - Low risk

Cleanup only (P3): 2 items
  1. Taint Backup Files (18 files, 13,916 lines)
     - Can be deleted - not used

  2. TODO/FIXME Comments (13 total)
     - Very low count - no actionable items

=== END REPORT ===

## CRITICAL DISCOVERY: JavaScript Extractors

The BIGGEST gap in the investigation is the ast_extractors/javascript/ directory:
- 10 Node.js scripts totaling 263KB
- Called via subprocess for EVERY JavaScript/TypeScript file
- Each file spawns a Node.js process
- This is MASSIVE overhead on JavaScript-heavy projects

Example flow:
1. Python calls subprocess to Node.js script
2. Node.js loads tree-sitter parser
3. Node.js extracts AST data
4. Returns JSON to Python
5. Python parses JSON and stores in database

This happens for EVERY .js/.ts file in the project.

Similarly for Python extractors in ast_extractors/python/:
- 14 Python modules totaling 304KB
- These run on EVERY Python file
- Complex extraction logic in core_extractors.py (42KB)

## VERIFICATION NOTES

Investigation claim: "No profiling/metrics infrastructure"
- ✅ CONFIRMED: No performance tests found
- ✅ CONFIRMED: No benchmarking framework
- ✅ CONFIRMED: No integrated profiling

Files NOT in investigation but SHOULD BE:
1. ast_extractors/javascript/*.js (P0 - HOT PATH)
2. ast_extractors/python/*.py (P0 - HOT PATH)
3. cache/ast_cache.py (P1 - performance bug)
4. indexer/schemas/generated_accessors.py (P1 - dict(zip()) overhead)
5. graphql/builder.py (P1 - duplicate os.walk())

Total uncovered code: ~1.2MB of Python + JavaScript
Total uncovered files: ~300+ Python files not explicitly mentioned

## RECOMMENDATIONS

1. IMMEDIATE: Profile ast_extractors/* to measure subprocess overhead
2. IMMEDIATE: Investigate JavaScript extraction - can we batch or cache?
3. HIGH: Fix ast_cache.py eviction to be async or batched
4. HIGH: Replace LIKE in session/store.py with proper JSON extraction
5. MEDIUM: Audit all os.walk() calls - should use database instead
6. LOW: Delete taint/backup/*.bak files (13,916 dead lines)
