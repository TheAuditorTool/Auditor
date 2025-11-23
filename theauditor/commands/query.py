"""Query command - database query API for code relationships.

Direct SQL queries over TheAuditor's indexed code relationships.
NO file reading, NO parsing, NO inference - just exact database lookups.
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional

import click

from theauditor.utils.error_handler import handle_exceptions


@click.command()
@click.option("--symbol", help="Query symbol by exact name (functions, classes, variables)")
@click.option("--file", help="Query file by path (partial match supported)")
@click.option("--api", help="Query API endpoint by route pattern (supports wildcards)")
@click.option("--component", help="Query React/Vue component by name")
@click.option("--variable", help="Query variable by name (for data flow tracing)")
@click.option("--pattern", help="Search symbols by pattern (supports % wildcards like 'auth%')")
@click.option("--category", help="Search by security category (jwt, oauth, password, sql, xss, auth)")
@click.option("--search", help="Cross-table exploratory search (finds term across all tables)")
@click.option("--list", "list_mode", help="List all symbols in file (symbols, functions, classes, imports, all)")
@click.option("--list-symbols", "list_symbols", is_flag=True, help="Discovery mode: list symbols matching filter pattern")
@click.option("--filter", "symbol_filter", help="Symbol name pattern for --list-symbols (e.g., '*Controller*', '*auth*')")
@click.option("--path", "path_filter", help="File path pattern for --list-symbols (e.g., 'src/api/*', 'services/')")
@click.option("--show-callers", is_flag=True, help="Show who calls this symbol (control flow incoming)")
@click.option("--show-callees", is_flag=True, help="Show what this symbol calls (control flow outgoing)")
@click.option("--show-dependencies", is_flag=True, help="Show what this file imports (outgoing dependencies)")
@click.option("--show-dependents", is_flag=True, help="Show who imports this file (incoming dependencies)")
@click.option("--show-tree", is_flag=True, help="Show component hierarchy tree (parent-child relationships)")
@click.option("--show-hooks", is_flag=True, help="Show React hooks used by component")
@click.option("--show-data-deps", is_flag=True, help="Show data dependencies (what vars function reads/writes) - DFG")
@click.option("--show-flow", is_flag=True, help="Show variable flow through assignments (def-use chains) - DFG")
@click.option("--show-taint-flow", is_flag=True, help="Show cross-function taint flow (returns -> assignments) - DFG")
@click.option("--show-api-coverage", is_flag=True, help="Show API security coverage (auth controls per endpoint)")
@click.option("--type-filter", help="Filter pattern search by symbol type (function, class, variable)")
@click.option("--include-tables", help="Comma-separated tables for cross-table search (e.g., 'symbols,findings')")
@click.option("--depth", default=1, type=int, help="Traversal depth for transitive queries (1-5, default=1)")
@click.option("--format", "output_format", default="text",
              type=click.Choice(['text', 'json', 'tree']),
              help="Output format: text (human), json (AI), tree (visual)")
@click.option("--save", type=click.Path(), help="Save output to file (auto-creates parent dirs)")
@click.option("--show-code/--no-code", default=False,
              help="Include source code snippets for callers/callees (default: no)")
@handle_exceptions
def query(symbol, file, api, component, variable, pattern, category, search, list_mode,
          list_symbols, symbol_filter, path_filter,
          show_callers, show_callees, show_dependencies, show_dependents,
          show_tree, show_hooks, show_data_deps, show_flow, show_taint_flow,
          show_api_coverage, type_filter, include_tables,
          depth, output_format, save, show_code):
    """Query code relationships from indexed database for AI-assisted refactoring.

    WHAT THIS DOES:
        Direct SQL queries over TheAuditor's indexed code relationships.
        NO file reading, NO parsing, NO inference - just exact database lookups.
        Perfect for AI assistants to understand code without burning tokens.

    WHY USE THIS:
        Problem: AI needs to understand "who calls this function" before refactoring
        Traditional approach: Read 10+ files, guess relationships, hope for the best
        This approach: Single query returns exact answer in <10ms

        Token savings: 5,000-10,000 tokens per refactoring iteration
        Accuracy: 100% (vs ~60% when guessing from file reading)
        Speed: <10ms (vs 1-2s to read/parse multiple files)

    HOW IT WORKS:
        1. aud index runs → Extracts all code relationships to repo_index.db
        2. You run query → Direct SQL SELECT on indexed tables
        3. Results formatted → Text for humans, JSON for AI consumption
        4. You use results → Know exactly what to refactor, zero guessing

    ARCHITECTURE:
        Query Targets (what to query):
            --symbol NAME      → Find in symbols table (33k rows)
            --file PATH        → Find in edges table (7.3k rows)
            --api ROUTE        → Find in api_endpoints table (185 rows)
            --component NAME   → Find in react_components table (1k rows)

        Symbol canonicalization (CRITICAL - read this before screaming "no results"):
            - ALL class/instance methods are indexed as ClassName.methodName
              (e.g., AccountController.handleRequest). Property-assigned functions
              and wrapped handlers follow the same Class.property pattern.
            - Free functions keep their literal name, but still require an exact
              match (case-sensitive).
            - Command returns nothing if you pass a bare method name. Run
              aud query --symbol handleRequest           # shows canonical spellings
              then reuse the exact Name field in subsequent queries.

        Query Actions (what to show):
            --show-callers     → Who calls this? (function_call_args table)
            --show-callees     → What does this call? (function_call_args table)
            --show-dependencies → What imports? (edges table, outgoing)
            --show-dependents  → Who imports this? (edges table, incoming)
            --show-tree        → Component children (react_components + calls_jsx)

        Query Modifiers (how to query):
            --depth N          → Transitive traversal (BFS algorithm, max depth=5)
            --format FORMAT    → Output style (text/json/tree)
            --save PATH        → Export to file

    PREREQUISITES:
        REQUIRED (for all queries):
            aud index
            → Builds repo_index.db with 200k+ rows of relationships
            → Takes 30-60s for typical project, runs once

        OPTIONAL (for dependency queries only):
            aud graph build
            → Builds graphs.db with import/call graph edges
            → Only needed if you use --show-dependencies or --show-dependents
            → Takes 10-30s additional

    QUERY TYPES EXPLAINED:

        1. SYMBOL QUERIES (--symbol NAME):
           What: Find function/class/variable definitions and usage
           Database: symbols, symbols_jsx tables (33k + 8k rows)
           Use cases:
               - Find where symbol is defined (file:line)
               - See who calls this function (--show-callers)
               - See what this function calls (--show-callees)
               - Transitive call chains (--depth 3)

           Examples:
               # Default: symbol info + direct callers
               aud query --symbol authenticateUser

               # Who calls this? (direct callers)
               aud query --symbol authenticateUser --show-callers

               # Who calls this? (transitive, 3 levels deep)
               aud query --symbol validateInput --show-callers --depth 3

               # What does this call?
               aud query --symbol processRequest --show-callees

           Output (text format):
               Symbol Definitions (1):
                 1. authenticateUser
                    Type: function
                    File: src/auth/service.ts:42-58

               Callers (5):
                 1. src/middleware/auth.ts:23
                    authMiddleware -> authenticateUser
                    Args: req.user
                 2. src/api/users.ts:105
                    UserController.login -> authenticateUser
                    Args: credentials

        2. FILE QUERIES (--file PATH):
           What: Find import relationships (what file imports, who imports file)
           Database: edges table in graphs.db (7.3k rows)
           Use cases:
               - Understand file dependencies before moving file
               - Find circular imports
               - See who depends on this module

           Examples:
               # Default: both incoming and outgoing
               aud query --file src/auth.ts

               # What does this file import?
               aud query --file src/auth.ts --show-dependencies

               # Who imports this file?
               aud query --file src/utils.ts --show-dependents

               # Works with partial paths
               aud query --file auth.ts --show-dependencies

           Output (text format):
               Incoming Dependencies (3):
                 (Files that import this file)
                 1. src/middleware/auth.ts (import)
                 2. src/api/users.ts (import)
                 3. src/routes/index.ts (import)

               Outgoing Dependencies (12):
                 (Files imported by this file)
                 1. external::jsonwebtoken (import)
                 2. src/utils/crypto.ts (import)
                 3. src/db/users.ts (import)

        3. API QUERIES (--api ROUTE):
           What: Find which controller handles an API endpoint
           Database: api_endpoints table (185 rows)
           Use cases:
               - Find handler for a route before modifying
               - See all endpoints for a resource (/users)
               - Check auth requirements

           Examples:
               # Exact route match
               aud query --api "/users/:id"

               # Find all /users endpoints (wildcard)
               aud query --api "/users"

               # Check /api/auth routes
               aud query --api "/api/auth"

           Output (text format):
               API Endpoints (3):
                 1. GET    /users/:id                              [AUTH]
                    Handler: UserController.getById (src/api/users.ts:45)
                 2. PUT    /users/:id                              [AUTH]
                    Handler: UserController.update (src/api/users.ts:67)
                 3. DELETE /users/:id                              [AUTH]
                    Handler: UserController.delete (src/api/users.ts:89)

        4. COMPONENT QUERIES (--component NAME):
           What: Find React/Vue component definition, hooks, and children
           Database: react_components, react_hooks tables (1k + 667 rows)
           Use cases:
               - Understand component tree before refactoring
               - See which hooks a component uses
               - Find child components

           Examples:
               # Default: component info + hooks + children
               aud query --component UserProfile

               # Explicit tree view
               aud query --component UserProfile --show-tree

           Output (text format):
               Component: UserProfile
                 Type: function
                 File: src/components/UserProfile.tsx:15
                 Has JSX: Yes

               Hooks Used (3):
                 - useState
                 - useEffect
                 - useAuth

               Child Components (2):
                 - Avatar (line 42)
                 - ProfileStats (line 67)

    ACTION FLAGS EXPLAINED:

        --show-callers (for symbols):
            Who calls this function/method?
            Database: function_call_args, function_call_args_jsx
            Returns: List of call sites with file:line and arguments
            Use case: "Before refactoring validateUser, see all 47 callers"

        --show-callees (for symbols):
            What does this function/method call?
            Database: function_call_args, function_call_args_jsx
            Returns: List of calls made by this function
            Use case: "See what dependencies processOrder has"

        --show-dependencies (for files):
            What does this file import? (outgoing dependencies)
            Database: edges table (graph_type='import')
            Returns: List of files/modules imported by this file
            Use case: "Before moving auth.ts, see what it imports"

        --show-dependents (for files):
            Who imports this file? (incoming dependencies)
            Database: edges table (graph_type='import')
            Returns: List of files that import this file
            Use case: "Moving utils.ts will affect these 23 files"

    MODIFIERS EXPLAINED:

        --depth N (default=1, range=1-5):
            Transitive traversal depth for caller/callee queries
            depth=1: Direct relationships only
            depth=2: Direct + 1 level indirect
            depth=3: Direct + 2 levels indirect (recommended max)
            depth=5: Maximum allowed (performance warning >3)

            Example (depth=1 vs depth=3):
                depth=1:  A -> B (only direct callers of B)
                depth=3:  A -> B, C -> A -> B, D -> C -> A -> B

            Algorithm: Breadth-first search (BFS) with visited set
            Performance: depth=1 <1ms, depth=3 <10ms, depth=5 <50ms

        --format FORMAT:
            text: Human-readable, numbered lists, file:line format (default)
                  Best for: Terminal display, AI reading structured text
            json: AI-consumable, valid JSON with dataclass conversion
                  Best for: Programmatic parsing, piping to jq
            tree: Visual hierarchy (currently falls back to text)
                  Best for: Future use (full tree viz not yet implemented)

        --save PATH:
            Write results to file instead of (or in addition to) stdout
            Auto-creates parent directories if they don't exist
            Encoding: UTF-8 (handles all characters)
            Use case: Save analysis for later, share with team

    COMMON WORKFLOWS:

        Workflow 1: Safe Function Refactoring
            # Step 1: Find all callers
            aud query --symbol oldFunction --show-callers

            # Step 2: Understand what it calls
            aud query --symbol oldFunction --show-callees

            # Step 3: Refactor with full knowledge of impact
            # (You now know all 47 callers and 12 callees)

        Workflow 2: File Relocation Impact Analysis
            # Step 1: See who imports this file
            aud query --file src/utils/old.ts --show-dependents

            # Step 2: See what this file imports
            aud query --file src/utils/old.ts --show-dependencies

            # Step 3: Move file, update all 23 import statements
            # (You know exactly which files need updating)

        Workflow 3: API Endpoint Modification
            # Step 1: Find handler for route
            aud query --api "/users/:id"

            # Step 2: Find callers of handler function
            aud query --symbol UserController.getById --show-callers

            # Step 3: Modify with knowledge of all consumers

        Workflow 4: Component Refactoring
            # Step 1: See component structure
            aud query --component UserProfile --show-tree

            # Step 2: Find who renders this component
            aud query --symbol UserProfile --show-callers

            # Step 3: Refactor component and all parent components

        Workflow 5: Cross-Stack Tracing
            # Frontend: Find API call
            aud query --symbol fetchUserData --show-callees

            # API: Find endpoint handler
            aud query --api "/api/users"

            # Backend: Find service calls
            aud query --symbol UserService.getById --show-callees

    COMMON TASKS (FOR AI ASSISTANTS):

        Task 1: List All Functions in a File
            # Use --list mode with --file to enumerate symbols
            aud query --file python_impl.py --list functions

            # List all symbol types
            aud query --file storage.py --list all

            # List only classes
            aud query --file auth.py --list classes

            # Alternative: Direct SQL if --list unavailable
            python -c "
            import sqlite3
            conn = sqlite3.connect('.pf/repo_index.db')
            c = conn.cursor()
            c.execute(\"SELECT name, type, line FROM symbols WHERE file LIKE '%python_impl.py%' ORDER BY line\")
            for row in c.fetchall():
                print(f'{row[0]} ({row[1]}) at line {row[2]}')
            conn.close()
            "

        Task 2: Check If File Is Deprecated (Deadcode Analysis)
            # First check if file is actively used
            aud deadcode 2>&1 | grep python_impl.py

            # If flagged, verify with import count
            python -c "
            import sqlite3
            conn = sqlite3.connect('.pf/repo_index.db')
            c = conn.cursor()
            c.execute(\"SELECT COUNT(*) FROM edges WHERE target_file LIKE '%python_impl.py%'\")
            print(f'Import count: {c.fetchone()[0]}')
            conn.close()
            "

        Task 3: Find All Callers for Refactoring
            # Step 1: Get exact symbol name (AI often guesses wrong)
            aud query --pattern "extract_python%" --format json | jq '.[].name'

            # Step 2: Use exact name to find callers
            aud query --symbol "PythonExtractor.extract_functions" --show-callers

        Task 4: Understand File Dependencies Before Moving
            # What does this file import? (outgoing)
            aud query --file src/utils/helper.ts --show-dependencies

            # Who imports this file? (incoming)
            aud query --file src/utils/helper.ts --show-dependents

        Task 5: Trace Variable Data Flow
            # Trace userToken through 3 levels of assignments
            aud query --variable userToken --show-flow --depth 3

            # Trace in specific file only
            aud query --variable app --file backend/src/app.ts --show-flow

        Task 6: Security Audit - Find Unprotected API Endpoints
            # Show all endpoints with auth controls
            aud query --show-api-coverage

            # Filter to specific route
            aud query --api "/users" --show-api-coverage

            # Find unprotected endpoints (grep for OPEN)
            aud query --show-api-coverage | grep "\[OPEN\]"

        Task 7: Cross-Function Taint Analysis
            # Find where validateUser's returns flow to
            aud query --symbol validateUser --show-taint-flow

            # See what variables a function reads/writes
            aud query --symbol createApp --show-data-deps

        Task 8: Pattern Search for Similar Symbols
            # Find all auth-related functions
            aud query --pattern "auth%" --type-filter function

            # Find all validation functions
            aud query --pattern "%validate%" --format json

        Key Principle for AI:
            - ALWAYS run `aud query --help` FIRST before using the tool
            - DO NOT guess command syntax - read help to see actual options
            - DO NOT hallucinate flags like --show-functions (doesn't exist)
            - USE --list mode for enumeration (list all X in file Y)
            - USE --show-callers/--show-callees for relationships (who calls X)
            - FALLBACK to direct SQL if CLI doesn't support your use case

    OUTPUT FORMATS:

        TEXT FORMAT (default):
            Numbered lists, file:line references, human-readable
            Perfect for AI parsing structured text
            Example:
                Results (5):
                  1. backend/src/app.ts:23
                     createApp -> app.use
                     Args: requestIdMiddleware
                  2. backend/src/app.ts:28
                     createApp -> app.use
                     Args: morgan('dev')

        JSON FORMAT (--format json):
            Valid JSON, dataclasses converted to dicts, AI-consumable
            Perfect for programmatic parsing, piping to tools
            Example:
                [
                  {
                    "caller_file": "backend/src/app.ts",
                    "caller_line": 23,
                    "caller_function": "createApp",
                    "callee_function": "app.use",
                    "arguments": ["requestIdMiddleware"]
                  },
                  ...
                ]

        TREE FORMAT (--format tree):
            Visual hierarchy (currently falls back to text format)
            Future: ASCII art tree visualization

    PERFORMANCE CHARACTERISTICS:

        Query Speed (measured on 340-file TypeScript project):
            Symbol lookup:              0.16ms  (indexed)
            Direct callers (depth=1):   0.63ms  (table scan)
            Transitive (depth=3):       4.20ms  (BFS traversal)
            File dependencies:          5.79ms  (graph query)

        Database Size:
            Small project (<5k LOC):    5-10MB
            Medium project (20k LOC):   20-50MB
            Large project (100k LOC):   100-200MB

        Memory Usage:
            Query engine: <50MB (database cached in memory)
            BFS traversal: O(n) where n = visited nodes
            Max depth=5: <10k nodes visited (typically)

    TROUBLESHOOTING:

        ERROR: "No .pf directory found"
        CAUSE: Haven't run aud full yet
        FIX: Run: aud full
        EXPLANATION: Query engine needs indexed database to work

        ERROR: "Graph database not found"
        CAUSE: Haven't run aud graph build (only for dependency queries)
        FIX: Run: aud graph build
        EXPLANATION: --show-dependencies/--show-dependents need graphs.db

        SYMPTOM: Empty results but symbol exists in code
        CAUSE 1: Typo in symbol name (case-sensitive)
        FIX: Try: aud query --symbol foo (shows symbol info if exists)
        CAUSE 2: Database stale (code changed since last index)
        FIX: Run: aud index (regenerates database)
        CAUSE 3: Provided unqualified method name (index stores ClassName.methodName)
        FIX: Run: aud query --symbol handleRequest → copy exact Name field (e.g. AccountController.handleRequest)

        SYMPTOM: Slow queries (>50ms)
        CAUSE: Large project (100k+ LOC) + high depth (>3)
        FIX: Reduce --depth to 1-2, or wait (50ms is still fast!)
        EXPLANATION: depth=5 on 100k LOC can traverse 10k+ nodes

        SYMPTOM: Missing some expected results
        CAUSE: Dynamic calls (obj[variable]()) not indexed
        FIX: Use taint analysis for dynamic dispatch detection
        EXPLANATION: Static analysis can't resolve all dynamic behavior

    INTEGRATION WITH OTHER COMMANDS:

        aud index:
            Creates repo_index.db (required for all queries)
            Run once, then query unlimited times

        aud graph build:
            Creates graphs.db (for dependency queries)
            Optional, only if you need --show-dependencies

        aud taint-analyze:
            Uses same database (function_call_args table)
            Finds security vulnerabilities, not just relationships

        aud detect-patterns:
            Uses same database (symbols, function_call_args)
            Pattern matching vs relationship queries

    DATABASE SCHEMA REFERENCE:

        Tables queried by this command:
            symbols (33k)            - Function/class definitions
            symbols_jsx (8k)         - JSX component definitions
            function_call_args (13k) - Every function call with args
            function_call_args_jsx   - JSX calls
            variable_usage (57k)     - Variable references
            api_endpoints (185)      - REST routes
            react_components (1k)    - React component metadata
            react_hooks (667)        - Hook usage
            edges (7.3k)             - Import/call graph

        Indexes for performance:
            symbols.name             - O(log n) symbol lookup
            function_call_args.callee_function - O(log n) caller lookup
            edges.source, edges.target - O(log n) dependency lookup

    EXAMPLES (COMPREHENSIVE):

        # SYMBOL QUERIES (Control Flow)
        aud query --symbol authenticateUser
        aud query --symbol authenticateUser --show-callers
        aud query --symbol authenticateUser --show-callers --depth 3
        aud query --symbol processRequest --show-callees
        aud query --symbol UserController.create --show-callers --format json

        # FILE QUERIES (Dependencies)
        aud query --file src/auth.ts
        aud query --file src/auth.ts --show-dependencies
        aud query --file src/utils.ts --show-dependents
        aud query --file auth.ts --show-dependencies --format json

        # API QUERIES (Endpoints)
        aud query --api "/users/:id"
        aud query --api "/users"
        aud query --api "/api/auth" --format json

        # COMPONENT QUERIES (React/Vue)
        aud query --component UserProfile
        aud query --component UserProfile --show-tree

        # DATA FLOW GRAPH QUERIES (NEW - Advanced)
        aud query --symbol createApp --show-data-deps
        aud query --symbol createApp --show-data-deps --format json
        aud query --variable userToken --show-flow --depth 3
        aud query --variable app --file backend/src/app.ts --show-flow
        aud query --symbol validateUser --show-taint-flow
        aud query --show-api-coverage
        aud query --api "/users" --show-api-coverage
        aud query --show-api-coverage | grep "[OPEN]"

        # SAVE TO FILE
        aud query --symbol foo --show-callers --save analysis.txt
        aud query --file bar.ts --save deps.json --format json

        # PIPING (JSON to jq)
        aud query --symbol foo --show-callers --format json | jq '.[] | .caller_file'
        aud query --show-api-coverage --format json | jq '.[] | select(.has_auth == false)'

    DATA FLOW GRAPH (DFG) QUERIES - ADVANCED:

        The following queries use NORMALIZED JUNCTION TABLES to perform
        advanced data flow analysis. These tables were created by schema
        normalization (eliminating JSON TEXT columns) and enable JOIN-based
        queries instead of LIKE patterns.

        Junction Tables Available:
            assignment_sources        (42,844 rows)  - Which vars are read in assignments
            function_return_sources   (19,313 rows)  - Which vars are returned from functions
            api_endpoint_controls     (38 rows)      - Which auth controls protect endpoints
            import_style_names        (2,891 rows)   - Which symbols are imported
            react_hook_dependencies   (376 rows)     - Which vars are in hook deps

        5. DATA DEPENDENCY QUERIES (--symbol NAME --show-data-deps):
           What: Find what variables a function reads and writes
           Database: assignments table JOIN assignment_sources junction table
           Algorithm: Single JOIN query (not LIKE on JSON column)
           Performance: <10ms

           SQL Query Used:
               SELECT DISTINCT asrc.source_var_name
               FROM assignments a
               JOIN assignment_sources asrc
                 ON a.file = asrc.assignment_file
                 AND a.line = asrc.assignment_line
                 AND a.target_var = asrc.assignment_target
               WHERE a.in_function = ?

           Examples:
               # Find what createApp reads/writes
               aud query --symbol createApp --show-data-deps

               # Get JSON for programmatic use
               aud query --symbol createApp --show-data-deps --format json

           Output (text format):
               Data Dependencies:

                 Reads (5):
                   - __dirname
                   - express
                   - path
                   - path.resolve
                   - resolve

                 Writes (2):
                   - app = express()
                     (backend/src/app.ts:20)
                   - frontendPath = path.resolve(__dirname, '../../frontend/dist')
                     (backend/src/app.ts:83)

           Use cases:
               - Before refactoring, see exact data contract
               - Find hidden dependencies (reads)
               - See side effects (writes)
               - Understand function's data surface area

        6. VARIABLE FLOW TRACING (--variable NAME --show-flow --depth N):
           What: Trace how a variable flows through assignments (def-use chains)
           Database: assignments JOIN assignment_sources (BFS traversal)
           Algorithm: Breadth-first search through junction table
           Performance: depth=1 <10ms, depth=3 <30ms

           SQL Query Used (per BFS iteration):
               SELECT a.target_var, a.source_expr, a.file, a.line
               FROM assignments a
               JOIN assignment_sources asrc
                 ON a.file = asrc.assignment_file
                 AND a.line = asrc.assignment_line
               WHERE asrc.source_var_name = ?

           Examples:
               # Trace userToken through 3 levels
               aud query --variable userToken --show-flow --depth 3

               # Trace app variable in specific file
               aud query --variable app --file backend/src/app.ts --show-flow

           Output (text format):
               Variable Flow (3 steps):
                 1. userToken -> session.token
                    Location: backend/src/auth.ts:45
                    Function: validateUser
                    Depth: 1

                 2. session.token -> authCache.set
                    Location: backend/src/cache.ts:23
                    Function: cacheSession
                    Depth: 2

                 3. authCache.set -> redis.set
                    Location: backend/src/redis.ts:67
                    Function: setKey
                    Depth: 3

           Use cases:
               - Trace sensitive data flow (tokens, passwords)
               - Find where variable is ultimately used
               - Understand data transformation chains
               - Debug unexpected assignments

        7. CROSS-FUNCTION TAINT FLOW (--symbol NAME --show-taint-flow):
           What: Track variables returned from function and assigned elsewhere
           Database: function_return_sources JOIN assignment_sources JOIN assignments
           Algorithm: Double JOIN - returns → sources → assignments
           Performance: <15ms

           SQL Query Used:
               SELECT
                 frs.return_var_name,
                 frs.return_file,
                 frs.return_line,
                 a.target_var AS assignment_var,
                 a.file AS assignment_file,
                 a.line AS assignment_line
               FROM function_return_sources frs
               JOIN assignment_sources asrc ON frs.return_var_name = asrc.source_var_name
               JOIN assignments a ON asrc.assignment_file = a.file
               WHERE frs.return_function = ?

           Examples:
               # Find where validateUser's returns are assigned
               aud query --symbol validateUser --show-taint-flow

           Output (text format):
               Cross-Function Taint Flow (2 flows):
                 1. Return: user at backend/src/auth.ts:45
                    Assigned: req.user at backend/src/middleware/auth.ts:23
                    In function: authMiddleware

                 2. Return: isValid at backend/src/auth.ts:47
                    Assigned: session.valid at backend/src/session.ts:12
                    In function: validateSession

           Use cases:
               - Find inter-procedural taint propagation
               - See how function outputs are consumed
               - Detect security-sensitive data flows
               - Understand cross-module dependencies

        8. API SECURITY COVERAGE (--show-api-coverage [--api PATTERN]):
           What: Show which authentication controls protect each API endpoint
           Database: api_endpoints LEFT JOIN api_endpoint_controls
           Algorithm: GROUP_CONCAT aggregation with LEFT JOIN
           Performance: ~20ms (185 endpoints)

           SQL Query Used:
               SELECT
                 ae.file,
                 ae.line,
                 ae.method,
                 ae.path,
                 ae.handler_function,
                 GROUP_CONCAT(aec.control_name, ', ') AS controls
               FROM api_endpoints ae
               LEFT JOIN api_endpoint_controls aec
                 ON ae.file = aec.endpoint_file
                 AND ae.line = aec.endpoint_line
               GROUP BY ae.file, ae.line, ae.method, ae.path
               ORDER BY ae.path, ae.method

           Examples:
               # Check all endpoints
               aud query --show-api-coverage

               # Filter to specific routes
               aud query --api "/users" --show-api-coverage

               # Find unprotected endpoints
               aud query --show-api-coverage | grep "[OPEN]"

           Output (text format):
               API Security Coverage (185 endpoints):
                 1. USE    backend/src/app.ts                       [OPEN]
                    Handler: apiRateLimit (backend/src/app.ts:62)

                 9. DELETE backend/src/routes/area.routes.ts        [AUTH]
                    Handler: handler(controller.removePartition) (...)
                    Controls: authenticate

                 12. GET    backend/src/routes/area.routes.ts        [2 controls]
                     Handler: handler(controller.getOccupancy) (...)
                     Controls: authenticate, requireRole

           Use cases:
               - Security audit: find endpoints without auth
               - Compliance check: verify all sensitive routes protected
               - Migration: ensure OAuth added to all endpoints
               - Documentation: generate auth requirements matrix

    MANUAL DATABASE QUERIES (FOR ADVANCED USERS / DEBUGGING):

        TheAuditor stores all indexed data in SQLite databases that you can
        query directly using Python's sqlite3 module or any SQLite client.

        Database Locations:
            .pf/repo_index.db     - Main code index (40 tables, 200k+ rows)
            .pf/graphs.db         - Import/call graph (optional)

        Querying from Python:
            cd /path/to/your/project
            python3

            >>> import sqlite3
            >>> conn = sqlite3.connect('.pf/repo_index.db')
            >>> cursor = conn.cursor()

            # See all tables
            >>> cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            >>> print([row[0] for row in cursor.fetchall()])
            ['symbols', 'function_call_args', 'assignments', 'assignment_sources', ...]

            # Check row counts
            >>> cursor.execute("SELECT COUNT(*) FROM assignment_sources")
            >>> print(f"assignment_sources: {cursor.fetchone()[0]} rows")

            # Query data dependencies manually
            >>> cursor.execute('''
            SELECT DISTINCT asrc.source_var_name
            FROM assignments a
            JOIN assignment_sources asrc
              ON a.file = asrc.assignment_file
              AND a.line = asrc.assignment_line
            WHERE a.in_function = "createApp"
            ''')
            >>> reads = [row[0] for row in cursor.fetchall()]
            >>> print("Reads:", reads)

            # Explore junction tables
            >>> cursor.execute("PRAGMA table_info(assignment_sources)")
            >>> print("Columns:", [(row[1], row[2]) for row in cursor.fetchall()])

            # Close connection
            >>> conn.close()

        Querying from Bash (if sqlite3 installed):
            sqlite3 .pf/repo_index.db "SELECT * FROM symbols WHERE name='createApp'"

        Key Tables for Manual Queries:
            symbols                   - Function/class definitions (path, name, type, line)
            function_call_args        - Function calls with arguments
            assignments               - Variable assignments (target_var, source_expr, in_function)
            assignment_sources        - Junction table (assignment → source variables)
            function_return_sources   - Junction table (function → returned variables)
            api_endpoints             - REST API routes (method, path, handler_function)
            api_endpoint_controls     - Junction table (endpoint → auth controls)
            findings_consolidated     - All security findings from analysis

        Schema Documentation:
            See: theauditor/indexer/schema.py for complete table definitions
            Each table has:
                - Column definitions with types
                - Indexes for performance
                - Primary keys and UNIQUE constraints
                - Comments explaining purpose

        Why Query Manually:
            - Custom analysis not supported by CLI
            - Debugging indexing issues
            - Exporting data for external tools
            - Learning database structure
            - Writing custom automation scripts

        Example: Find All Functions That Call External APIs:
            >>> cursor.execute('''
            SELECT DISTINCT caller_function, file, line
            FROM function_call_args
            WHERE callee_function LIKE "fetch%"
               OR callee_function LIKE "axios.%"
               OR callee_function LIKE "http.%"
            ''')
            >>> api_callers = cursor.fetchall()

        Example: Find Most Called Functions:
            >>> cursor.execute('''
            SELECT callee_function, COUNT(*) as call_count
            FROM function_call_args
            GROUP BY callee_function
            ORDER BY call_count DESC
            LIMIT 10
            ''')
            >>> top_functions = cursor.fetchall()

    ARCHITECTURE DEEP DIVE (FOR AI ASSISTANTS):

        Understanding the architecture helps you use queries effectively:

        1. EXTRACTION PIPELINE:
           Source Code → tree-sitter → AST Parser → Extractors → Database Manager
                                                                        ↓
                                                          repo_index.db (SQLite)

        2. SCHEMA NORMALIZATION (v1.2+):
           OLD: JSON TEXT columns with LIKE queries (slow, no joins)
           NEW: Junction tables with JOIN queries (fast, relational)

           Example transformation:
               OLD:  assignments.source_vars = '["x", "y", "z"]' (JSON TEXT)
               NEW:  assignment_sources table with 3 rows:
                       (assignment_id=1, source_var_name='x')
                       (assignment_id=1, source_var_name='y')
                       (assignment_id=1, source_var_name='z')

           Benefits:
               - 10x faster queries (indexed lookups vs JSON parsing)
               - Can use JOINs (relational algebra)
               - Type-safe queries (no JSON parsing errors)
               - Standard SQL (no custom functions)

        3. QUERY ENGINE ARCHITECTURE:
           User Request
               ↓
           CLI (commands/context.py)
               ↓
           CodeQueryEngine (context/query.py)
               ↓
           Direct SQL SELECT (no ORM overhead)
               ↓
           SQLite (repo_index.db)
               ↓
           Formatters (context/formatters.py)
               ↓
           Output (text/json/tree)

        4. INDEX MAINTENANCE:
           - Database is REGENERATED on every 'aud index' run
           - NO migrations (fresh build every time)
           - Changes to code → re-run 'aud index' → database updated
           - Database is TRUTH SOURCE (not code files)

        5. PERFORMANCE CHARACTERISTICS:
           - Query time: <10ms (indexed lookups)
           - Database size: 20-50MB typical project
           - Memory usage: <50MB for query engine
           - BFS traversal: O(n) where n = nodes visited
           - JOIN queries: O(log n) with proper indexes

        6. JUNCTION TABLE PATTERN:
           Parent Table ←→ Junction Table ←→ Child Table
           assignments  ←→ assignment_sources ←→ (source variables)
           (Composite key: file + line + target_var)

           This allows:
               - Many-to-many relationships
               - Fast lookups (indexed on both sides)
               - Normalized data (no duplication)
               - Standard SQL JOINs

    See also:
        aud context --help          (semantic business logic analysis)
        aud blueprint --help        (architectural visualization)
        aud index --help            (database indexing)
        aud graph build --help      (graph construction)
    """
    from pathlib import Path
    from theauditor.context import CodeQueryEngine, format_output

    # Validate .pf directory exists
    pf_dir = Path.cwd() / ".pf"
    if not pf_dir.exists():
        click.echo("\n" + "="*60, err=True)
        click.echo("ERROR: No .pf directory found", err=True)
        click.echo("="*60, err=True)
        click.echo("\nContext queries require indexed data.", err=True)
        click.echo("\nPlease run:", err=True)
        click.echo("    aud full", err=True)
        click.echo("\nThen try again:", err=True)
        if symbol:
            click.echo(f"    aud query --symbol {symbol} --show-callers\n", err=True)
        else:
            click.echo("    aud query --help\n", err=True)
        raise click.Abort()

    # Validate at least one query target provided
    if not any([symbol, file, api, component, variable, pattern, category, search, show_api_coverage, list_mode, list_symbols]):
        click.echo("\n" + "="*60, err=True)
        click.echo("ERROR: No query target specified", err=True)
        click.echo("="*60, err=True)
        click.echo("\nYou must specify what to query:", err=True)
        click.echo("    --symbol NAME       (query a symbol)", err=True)
        click.echo("    --file PATH         (query a file)", err=True)
        click.echo("    --api ROUTE         (query an API endpoint)", err=True)
        click.echo("    --component NAME    (query a component)", err=True)
        click.echo("    --variable NAME     (query variable data flow)", err=True)
        click.echo("    --pattern PATTERN   (search symbols by pattern)", err=True)
        click.echo("    --category CATEGORY (search by security category)", err=True)
        click.echo("    --search TERM       (cross-table exploratory search)", err=True)
        click.echo("    --list TYPE         (list symbols: functions, classes, imports, all)", err=True)
        click.echo("    --list-symbols      (discovery mode: find symbols by pattern)", err=True)
        click.echo("    --show-api-coverage (query all API security coverage)", err=True)
        click.echo("\nExamples:", err=True)
        click.echo("    aud query --symbol authenticateUser --show-callers", err=True)
        click.echo("    aud query --file src/auth.ts --show-dependencies", err=True)
        click.echo("    aud query --api '/users' --format json", err=True)
        click.echo("    aud query --symbol createApp --show-data-deps", err=True)
        click.echo("    aud query --variable userToken --show-flow --depth 3", err=True)
        click.echo("    aud query --pattern 'auth%' --type-filter function", err=True)
        click.echo("    aud query --category jwt --format json", err=True)
        click.echo("    aud query --search payment --include-tables symbols,findings", err=True)
        click.echo("    aud query --file python_impl.py --list functions", err=True)
        click.echo("    aud query --list-symbols --filter '*Controller*'", err=True)
        click.echo("    aud query --list-symbols --path 'services/' --filter '*'", err=True)
        click.echo("    aud query --show-api-coverage\n", err=True)
        raise click.Abort()

    # Initialize query engine
    try:
        engine = CodeQueryEngine(Path.cwd())
    except FileNotFoundError as e:
        click.echo(f"\nERROR: {e}", err=True)
        raise click.Abort()

    # Route query based on target
    results = None

    try:
        if list_symbols:
            # DISCOVERY MODE: List symbols matching filter pattern
            # Converts shell glob (*) to SQL LIKE (%)
            name_pattern = '%'  # Default: match all
            if symbol_filter:
                # Convert glob to SQL LIKE: * -> %, ? -> _
                name_pattern = symbol_filter.replace('*', '%').replace('?', '_')

            # Convert path filter glob to SQL LIKE
            sql_path_filter = None
            if path_filter:
                sql_path_filter = path_filter.replace('*', '%').replace('?', '_')
                # Ensure trailing % for directory patterns
                if not sql_path_filter.endswith('%'):
                    sql_path_filter += '%'

            results = engine.pattern_search(
                name_pattern,
                type_filter=type_filter,
                path_filter=sql_path_filter,
                limit=200
            )

            # Wrap in discovery result format
            results = {
                'type': 'discovery',
                'filter': symbol_filter or '*',
                'path': path_filter or '(all)',
                'type_filter': type_filter,
                'count': len(results),
                'symbols': results
            }

        elif pattern:
            # NEW: Pattern search - SQL LIKE pattern matching (NO ML, NO CUDA)
            results = engine.pattern_search(pattern, type_filter=type_filter)

        elif category:
            # NEW: Category search - query security pattern tables (NO embeddings)
            results = engine.category_search(category)

        elif search:
            # NEW: Cross-table exploratory search (better than Compass's vector search)
            tables = include_tables.split(',') if include_tables else None
            results = engine.cross_table_search(search, include_tables=tables)

        elif symbol:
            # Symbol queries
            if show_callers:
                results = engine.get_callers(symbol, depth=depth)
            elif show_callees:
                results = engine.get_callees(symbol)
            elif show_data_deps:
                # NEW: Data flow query - what does this function read/write?
                results = engine.get_data_dependencies(symbol)
            elif show_taint_flow:
                # NEW: Cross-function taint flow
                results = engine.get_cross_function_taint(symbol)
            else:
                # Default: symbol info + direct callers
                symbols = engine.find_symbol(symbol)
                # Handle error dict from find_symbol (fuzzy suggestions)
                if isinstance(symbols, dict) and 'error' in symbols:
                    results = symbols  # Pass error dict directly
                else:
                    callers = engine.get_callers(symbol, depth=1)
                    results = {'symbol': symbols, 'callers': callers}

        elif list_mode:
            # NEW: List symbols in file (enumeration mode)
            if not file:
                click.echo("\nERROR: --list requires --file to be specified", err=True)
                click.echo("Example: aud query --file python_impl.py --list functions\n", err=True)
                raise click.Abort()

            # Directly query symbols table for enumeration
            db_path = Path.cwd() / ".pf" / "repo_index.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Build query based on list_mode type
            list_type = list_mode.lower()
            if list_type == "all":
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE file LIKE ?
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            elif list_type in ("functions", "function"):
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE file LIKE ? AND type = 'function'
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            elif list_type in ("classes", "class"):
                query = """
                    SELECT name, type, line
                    FROM symbols
                    WHERE file LIKE ? AND type = 'class'
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            elif list_type in ("imports", "import"):
                query = """
                    SELECT module_name, style, line
                    FROM imports
                    WHERE file LIKE ?
                    ORDER BY line
                """
                cursor.execute(query, (f"%{file}%",))
            else:
                conn.close()
                click.echo(f"\nERROR: Unknown list type: {list_type}", err=True)
                click.echo("Valid types: functions, classes, imports, all\n", err=True)
                raise click.Abort()

            rows = cursor.fetchall()
            conn.close()

            # Format results
            if list_type in ("imports", "import"):
                results = {
                    'type': 'list',
                    'list_mode': list_type,
                    'file': file,
                    'count': len(rows),
                    'items': [{'module': row[0], 'style': row[1], 'line': row[2]} for row in rows]
                }
            else:
                results = {
                    'type': 'list',
                    'list_mode': list_type,
                    'file': file,
                    'count': len(rows),
                    'items': [{'name': row[0], 'type': row[1], 'line': row[2]} for row in rows]
                }

        elif file:
            # File dependency queries
            if show_dependencies:
                results = engine.get_file_dependencies(file, direction='outgoing')
            elif show_dependents:
                results = engine.get_file_dependencies(file, direction='incoming')
            else:
                # Default: both directions
                results = engine.get_file_dependencies(file, direction='both')

        elif show_api_coverage:
            # NEW: API security coverage (standalone query) - checked before 'elif api' to take precedence
            results = engine.get_api_security_coverage(api if api else None)

        elif api:
            # API endpoint queries
            results = engine.get_api_handlers(api)

        elif component:
            # Component tree queries
            results = engine.get_component_tree(component)

        elif variable:
            # NEW: Variable data flow queries
            if show_flow:
                # Trace variable through def-use chains
                from_file = file or '.'  # Use --file if provided, else current dir
                results = engine.trace_variable_flow(variable, from_file, depth=depth)
            else:
                # Default: show variable info (future enhancement)
                results = {'error': 'Please specify --show-flow with --variable'}

    except ValueError as e:
        click.echo(f"\nERROR: {e}", err=True)
        raise click.Abort()
    finally:
        engine.close()

    # Add code snippets if requested and results are caller/callee lists
    if show_code and results:
        from theauditor.utils.code_snippets import CodeSnippetManager
        snippet_manager = CodeSnippetManager(Path.cwd())

        # Handle list of CallSite objects (from get_callers/get_callees)
        if isinstance(results, list) and results and hasattr(results[0], 'caller_file'):
            for call in results:
                snippet = snippet_manager.get_snippet(call.caller_file, call.caller_line, expand_block=False)
                if not snippet.startswith('['):
                    call.arguments.append(f"__snippet__:{snippet}")

        # Handle dict with 'symbol' + 'callers' (default symbol query)
        elif isinstance(results, dict) and 'callers' in results:
            callers = results.get('callers', [])
            if isinstance(callers, list):
                for call in callers:
                    if hasattr(call, 'caller_file'):
                        snippet = snippet_manager.get_snippet(call.caller_file, call.caller_line, expand_block=False)
                        if not snippet.startswith('['):
                            call.arguments.append(f"__snippet__:{snippet}")

    # Format output
    output_str = format_output(results, format=output_format)

    # Print to stdout
    click.echo(output_str)

    # Save if requested
    if save:
        save_path = Path(save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(output_str)
        click.echo(f"\nSaved to: {save_path}", err=True)


# This is now a standalone command, not a subcommand
# Export for CLI registration (no need for alias)
