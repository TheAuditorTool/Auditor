"""Manual library part 1: Core concepts (taint through context)."""

EXPLANATIONS_01: dict[str, dict[str, str]] = {
    "taint": {
        "title": "Taint Analysis",
        "summary": "Tracks untrusted data flow from sources to dangerous sinks",
        "explanation": """
Taint analysis is a security technique that tracks how untrusted data (tainted data)
flows through a program to potentially dangerous operations (sinks).

CONCEPTS:
- Source: Where untrusted data enters (user input, network, files)
- Sink: Dangerous operations (SQL queries, system commands, file writes)
- Taint: The property of being untrusted/contaminated
- Propagation: How taint spreads through assignments and function calls

HOW IT WORKS:
1. Read database tables: function_call_args, assignments from repo_index.db
2. Build call graph for inter-procedural analysis across functions
3. Identify sources: Match against 140+ taint source patterns
4. Propagate taint: Follow data flow through assignments and calls
5. Detect sinks: Match against 200+ security sink patterns
6. Classify severity: Critical (no sanitization) to Low (partial)
7. Output JSON with taint paths showing source -> sink with line numbers

EXAMPLE VULNERABILITY:
    user_input = request.body.get('name')  # SOURCE: User input is tainted
    query = f"SELECT * FROM users WHERE name = '{user_input}'"  # Taint propagates
    db.execute(query)  # SINK: SQL injection vulnerability!

WHAT THEAUDITOR DETECTS:
- SQL Injection: tainted data flows to cursor.execute(), db.query()
- Command Injection: tainted data flows to os.system(), subprocess.call()
- XSS: tainted data flows to render without escaping
- Path Traversal: tainted data flows to open(), Path operations
- LDAP/NoSQL Injection: tainted data flows to ldap/mongo queries

COMMAND OPTIONS (verified from source):
- --db: Path to SQLite database (default: .pf/repo_index.db)
- --output: Output path (default: .pf/raw/taint_analysis.json)
- --max-depth: Maximum inter-procedural depth (default: 5)
- --json: Output raw JSON instead of formatted report
- --verbose: Show detailed path information
- --severity: Filter by severity (all, critical, high, medium, low)
- --rules/--no-rules: Enable/disable rule-based detection (default: on)
- --memory/--no-memory: In-memory caching for 5-10x speed (default: on)
- --memory-limit: Cache limit in MB (auto-detected if not set)
- --mode: backward (IFDS), forward (entry->exit), complete (all flows)

PREREQUISITES:
- Run 'aud full' first to build repo_index.db with call graph data

EXAMPLES:
    aud taint                      # Full analysis with defaults
    aud taint --severity critical  # Only critical findings
    aud taint --verbose            # Show full taint paths
    aud taint --json               # Raw JSON output
    aud taint --mode forward       # Forward flow analysis
    aud taint --memory-limit 512   # Limit cache to 512MB

EXIT CODES:
- 0: Success, no vulnerabilities found
- 1: High severity vulnerabilities detected
- 2: Critical security vulnerabilities found

OUTPUT:
- .pf/raw/taint.json: All taint paths with source/sink details
- Findings also written to repo_index.db findings table for FCE
""",
    },
    "workset": {
        "title": "Workset",
        "summary": "A focused subset of files for targeted analysis",
        "explanation": """
A workset is TheAuditor's mechanism for focusing analysis on specific files
rather than the entire codebase. This dramatically improves performance and
relevance when working on specific features or reviewing changes.

WHAT IT CONTAINS:
- Seed files: Directly changed or selected files
- Expanded files: Dependencies that could be affected
- Transitive dependencies: Multi-hop relationships (up to --max-depth)

WHY USE WORKSETS:
1. Performance: Analyze 10 files instead of 1000 (100x faster)
2. Relevance: Focus on what actually changed
3. CI/CD: Only check modified code in pull requests
4. Incremental: Build on previous analysis

COMMAND OPTIONS (verified from source):
- --root: Root directory (default: current directory)
- --db: Input SQLite database path
- --all: Include all source files
- --diff: Git diff range (e.g., main..HEAD)
- --files: Explicit file list (can specify multiple)
- --include: Include glob patterns (can specify multiple)
- --exclude: Exclude glob patterns (can specify multiple)
- --max-depth: Maximum dependency expansion depth (default: 10)
- --out: Output workset file path (default: .pf/workset.json)
- --print-stats: Print summary statistics

HOW IT WORKS:
1. Identify seed files (from git diff, patterns, or explicit list)
2. Query refs table for files importing seed files
3. Expand importers recursively up to --max-depth hops
4. Apply --exclude patterns and deduplicate
5. Save to .pf/workset.json for other commands

COMMANDS THAT SUPPORT --workset (verified):
- aud lint --workset
- aud cfg analyze --workset
- aud graph build --workset
- aud graph analyze --workset
- aud workflows analyze --workset
- aud terraform provision --workset

EXAMPLE WORKFLOW:
    aud workset --diff HEAD~1          # What changed in last commit?
    aud lint --workset                 # Lint only those files

EXAMPLES:
    aud workset --diff main..feature   # PR changes
    aud workset --files auth.py api.py # Explicit files
    aud workset --include "*/api/*"    # Pattern match
    aud workset --all                  # All source files
    aud workset --diff HEAD --exclude "test/*"  # Skip tests
""",
    },
    "fce": {
        "title": "Factual Correlation Engine",
        "summary": "Correlates findings from multiple tools to detect compound vulnerabilities",
        "explanation": """
The Factual Correlation Engine (FCE) is TheAuditor's advanced analysis system
that identifies when multiple seemingly minor issues combine to create serious
vulnerabilities. It's like a security expert who sees the bigger picture.

THE PROBLEM FCE SOLVES:
Individual tools often miss complex vulnerabilities because they analyze in
isolation. For example:
- Tool A finds: "User input not validated"
- Tool B finds: "SQL query uses string concatenation"
- Tool C finds: "No prepared statements"
Each finding alone might be "low severity", but together they indicate
a critical SQL injection vulnerability.

HOW FCE WORKS:
1. Loads findings from all analysis tools
2. Applies 26 correlation rules
3. Identifies matching patterns across tools
4. Elevates severity when patterns combine
5. Provides evidence chain for each finding

EXAMPLE CORRELATION:
    Rule: "Authentication Bypass"
    Evidence Required:
    - Missing authentication check (from patterns)
    - Exposed endpoint (from graph analysis)
    - No rate limiting (from lint)
    Result: Critical vulnerability - unrestricted access to protected resources

CORRELATION CATEGORIES:
- Authentication & Authorization (missing auth + exposed endpoints)
- Injection Attacks (user input + dangerous operations)
- Data Exposure (debug mode + sensitive data)
- Infrastructure (misconfigurations + known CVEs)
- Code Quality (high complexity + no tests = hidden bugs)

VALUE OF FCE:
- Finds vulnerabilities that single tools miss
- Reduces false positives through cross-validation
- Provides complete evidence for each finding
- Prioritizes real risks over theoretical issues
""",
    },
    "cfg": {
        "title": "Control Flow Graph",
        "summary": "Maps all possible execution paths through functions",
        "explanation": """
A Control Flow Graph (CFG) represents all possible paths that program execution
might take through a function. It's essential for understanding code complexity
and finding bugs.

WHAT IS A CFG:
- Nodes: Basic blocks (sequences of instructions without branches)
- Edges: Possible transitions between blocks
- Entry: Where function execution starts
- Exit: Where function returns

WHY CFG MATTERS:
1. Complexity Analysis: More paths = harder to test and understand
2. Dead Code Detection: Blocks with no incoming edges
3. Security Analysis: Complex functions hide vulnerabilities
4. Test Coverage: Ensures all paths are tested

CYCLOMATIC COMPLEXITY:
The number of independent paths through a function.
Formula: M = E - N + 2P (Edges - Nodes + 2*Components)

Complexity Guidelines:
  1-10:  Simple, easy to test
  11-20: Moderate complexity, needs careful testing
  21-50: High complexity, should be refactored
  50+:   Very high risk, almost impossible to test fully

EXAMPLE CFG:
    def process(x):
        if x > 0:        # Branch node
            x = x * 2    # Block 1
        else:
            x = -x       # Block 2
        return x         # Merge node

This creates 2 independent paths with complexity of 2.

THEAUDITOR'S CFG ANALYSIS:
    aud cfg analyze                           # Find complex functions
    aud cfg analyze --find-dead-code          # Find unreachable code
    aud cfg viz --function process            # Visualize CFG

USE CASES:
- Code review: Identify overly complex functions
- Testing: Calculate paths to cover
- Refactoring: Find functions to simplify
- Security: Complex code hides bugs
""",
    },
    "impact": {
        "title": "Impact Analysis",
        "summary": "Measures the blast radius of code changes",
        "explanation": """
Impact analysis determines what parts of your codebase would be affected if
you change a specific function or class. It's like asking "what breaks if I
change this?"

IMPACT DIMENSIONS:
1. Upstream Impact: Who depends on this code?
   - Direct callers
   - Indirect callers (transitive)
   - Test files that test this code

2. Downstream Impact: What does this code depend on?
   - Direct dependencies
   - Indirect dependencies (transitive)
   - External libraries

3. Total Blast Radius: All affected files

HOW IT WORKS:
1. Identify target symbol at specified line
2. Query symbol database for relationships
3. Traverse dependency graph in both directions
4. Calculate transitive closure
5. Assess risk level

RISK ASSESSMENT:
- Low Impact: < 5 files affected (safe to change)
- Medium Impact: 5-20 files (review carefully)
- High Impact: > 20 files (dangerous change, extensive testing needed)

EXAMPLE ANALYSIS:
    aud impact --file auth.py --line 42

    Results:
    - Target: authenticate_user() function
    - Upstream: 15 files call this function
    - Downstream: Function uses 8 dependencies
    - Total Impact: 23 files
    - Risk: HIGH - extensive testing required

USE CASES:
1. Before Refactoring: Understand scope of changes
2. API Changes: See who uses the endpoint
3. Bug Fixes: Find all affected code paths
4. Dead Code: If upstream is empty, code might be unused
5. Architecture: Identify highly coupled code

CROSS-STACK ANALYSIS:
With --trace-to-backend, TheAuditor can trace:
- Frontend API calls to backend endpoints
- Database queries to their users
- Message queue producers to consumers
""",
    },
    "pipeline": {
        "title": "Analysis Pipeline",
        "summary": "TheAuditor's 4-stage optimized execution pipeline",
        "explanation": """
The pipeline is TheAuditor's orchestrated execution system that runs multiple
analysis tools in an optimized sequence with intelligent parallelization.

THE 4-STAGE PIPELINE:

STAGE 1: FOUNDATION (Sequential)
Must complete first to provide data for other stages:
- index: Build symbol database (all tools need this)
- detect-frameworks: Identify Django, Flask, React, etc.

STAGE 2: DATA PREPARATION (Sequential)
Prepares data structures for parallel analysis:
- workset: Identify target files
- graph build: Construct dependency graphs
- cfg: Extract control flow graphs

STAGE 3: HEAVY ANALYSIS (3 Parallel Tracks)
Track A: Taint Analysis (isolated for performance)
  - Runs in separate process/memory space
  - Most memory-intensive operation

Track B: Static Analysis
  - lint: Run code quality checks
  - detect-patterns: Security pattern matching
  - graph analyze: Find cycles and hotspots

Track C: Network I/O (skippable with --offline)
  - deps: Check dependencies
  - docs: Fetch documentation

STAGE 4: AGGREGATION (Sequential)
Combines findings from all previous stages:
- fce: Correlate findings across tools
- report: Generate final output

WHY THIS DESIGN:
1. Dependencies: Each stage needs data from previous stages
2. Performance: Parallel tracks reduce total time by 3x
3. Memory: Taint analysis isolated to prevent OOM
4. Flexibility: Can skip stages with flags

PERFORMANCE CHARACTERISTICS:
Small project (<5K LOC):      ~2 minutes
Medium project (20K LOC):     ~10 minutes
Large monorepo (100K+ LOC):   ~30-60 minutes

CACHING:
Second run is 5-10x faster due to:
- AST cache (.pf/.ast_cache/)
- Symbol database (repo_index.db)
- Incremental analysis with worksets
""",
    },
    "severity": {
        "title": "Severity Levels",
        "summary": "How TheAuditor classifies finding importance",
        "explanation": """
TheAuditor uses a 4-level severity system aligned with industry standards
like CVSS and CWE to prioritize security findings and code issues.

SEVERITY LEVELS:

CRITICAL (Exit Code 2)
Immediate security risk requiring emergency response:
- Remote Code Execution (RCE)
- SQL Injection with user input
- Authentication bypass
- Hardcoded secrets in code
- Command injection vulnerabilities
Action: Block deployment, fix immediately

HIGH (Exit Code 1)
Serious vulnerabilities requiring prompt attention:
- Cross-Site Scripting (XSS)
- Path traversal attacks
- Weak cryptography
- Missing authentication
- Insecure deserialization
Action: Fix before next release

MEDIUM (Exit Code 0, but reported)
Potential issues requiring investigation:
- Missing input validation
- Information disclosure
- Weak password policies
- Missing security headers
- Resource exhaustion risks
Action: Schedule for next sprint

LOW (Exit Code 0)
Code quality and minor security concerns:
- Code complexity issues
- Missing error handling
- Deprecated functions
- Performance problems
- Style violations
Action: Fix during refactoring

HOW SEVERITY IS DETERMINED:
1. Exploitability: How easy to exploit?
2. Impact: What's the damage potential?
3. Confidence: How certain is the finding?
4. Context: Framework-specific considerations

SEVERITY ESCALATION:
The FCE can escalate severity when patterns combine:
- Low + Low can become High
- Medium + Medium can become Critical

Example: "Debug mode" (low) + "Exposes secrets" (medium) = Critical

FILTERING BY SEVERITY:
    aud taint --severity critical   # Only critical issues
    aud full --quiet                       # Exit code indicates severity
""",
    },
    "patterns": {
        "title": "Pattern Detection",
        "summary": "Security vulnerability patterns TheAuditor can detect",
        "explanation": """
Pattern detection is TheAuditor's rule-based system for finding security
vulnerabilities and code quality issues using both regex patterns and
Abstract Syntax Tree (AST) analysis.

DETECTION METHODS:

1. REGEX PATTERNS (Fast)
   Simple text matching for obvious issues:
   - Hardcoded passwords: password = "admin123"
   - API keys: api_key = "sk_live_..."
   - Debug flags: DEBUG = True

2. AST PATTERNS (Accurate)
   Semantic understanding of code structure:
   - SQL injection in string concatenation
   - Unsafe deserialization
   - Missing authentication decorators

PATTERN CATEGORIES:

Authentication & Authorization:
- Hardcoded credentials
- Weak password validation
- Missing authentication checks
- Insecure session management
- JWT vulnerabilities

Injection Attacks:
- SQL injection patterns
- Command injection risks
- XSS vulnerabilities
- Template injection
- LDAP/NoSQL injection

Data Security:
- Exposed sensitive data
- Weak cryptography (MD5, SHA1)
- Insecure random generation
- Missing encryption
- Data leakage in logs

Infrastructure:
- Debug mode enabled
- CORS misconfiguration
- Missing security headers
- Exposed admin panels
- Insecure file uploads

Code Quality:
- Empty catch blocks
- Infinite loops
- Race conditions
- Resource leaks
- Dead code

PATTERN FILES:
Located in theauditor/patterns/*.yaml
Each pattern includes:
- pattern: Regex or AST pattern
- message: What was found
- severity: critical/high/medium/low
- cwe: Common Weakness Enumeration ID

CUSTOM PATTERNS:
You can add custom patterns for your organization:
1. Create YAML file in patterns/
2. Define pattern, severity, message
3. Run detect-patterns to use

PERFORMANCE:
- Regex only: Very fast (<30 seconds)
- With AST: 2-3x slower but more accurate
- Default: Both methods for comprehensive analysis
""",
    },
    "insights": {
        "title": "Insights System",
        "summary": "Optional interpretation layer that adds scoring to raw facts",
        "explanation": """
The Insights System is TheAuditor's optional interpretation layer that sits
ON TOP of factual data. It's the crucial distinction between reporting facts
and adding judgments about those facts.

TWO-LAYER ARCHITECTURE:

1. TRUTH COURIERS (Core Modules):
   Report verifiable facts WITHOUT judgment:
   - "Data flows from req.body to res.send"
   - "Function complexity is 47"
   - "17 circular dependencies detected"
   - "Password field has no validation"

2. INSIGHTS (Optional Interpretation):
   Add scoring, severity, and predictions:
   - "This is CRITICAL severity XSS"
   - "Health score: 35/100 - Needs refactoring"
   - "Risk prediction: 87% chance of vulnerabilities"
   - "Recommend immediate review"

AVAILABLE INSIGHTS MODULES:

Machine Learning (theauditor/insights/ml.py):
- Trains on your codebase patterns
- Predicts vulnerability likelihood
- Identifies high-risk files
- Suggests review priorities
- Requires: pip install -e ".[ml]"

Graph Health (theauditor/insights/graph.py):
- Calculates architecture health scores
- Grades codebase quality (A-F)
- Identifies hotspots and bottlenecks
- Recommends refactoring targets

Taint Severity (theauditor/insights/taint.py):
- Adds CVSS-like severity scores
- Classifies vulnerability types
- Calculates exploitability risk
- Prioritizes security fixes

WHY SEPARATION MATTERS:

Facts are universal:
- "SQL query concatenates user input" - FACT
- Everyone agrees this happens

Interpretations are contextual:
- "This is CRITICAL" - OPINION
- Depends on your threat model
- Varies by organization

USING INSIGHTS:
    aud insights                    # Run all insights
    aud insights --mode ml          # ML predictions only
    aud insights --mode graph       # Architecture health
    aud insights --print-summary    # Show results in terminal

OUTPUT STRUCTURE:
.pf/
|-- raw/               # Immutable facts (truth)
+-- insights/          # Interpretations (opinions)
    |-- ml_suggestions.json
    |-- graph_health.json
    +-- taint_severity.json

PHILOSOPHY:
TheAuditor deliberately separates facts from interpretations because:
1. Facts are objective - the code does what it does
2. Severity is subjective - risk tolerance varies
3. AI needs both - facts for accuracy, insights for prioritization

The core system will NEVER tell you something is "critical" or "needs fixing."
It only reports what IS. The insights layer adds what it MEANS.
""",
    },
    "overview": {
        "title": "TheAuditor Overview",
        "summary": "What TheAuditor is and how it works",
        "explanation": """
TheAuditor is an offline-first, AI-centric SAST (Static Application Security Testing)
platform. It provides ground truth about your codebase through comprehensive security
analysis, taint tracking, and quality auditing.

PURPOSE:
  Designed for both human developers and AI assistants to detect:
  - Security vulnerabilities (SQL injection, XSS, command injection)
  - Incomplete refactorings (broken imports, orphan code)
  - Architectural issues (circular dependencies, hotspots)

PHILOSOPHY:
  TheAuditor is a Truth Courier, Not a Mind Reader:
  - Finds where code doesn't match itself (inconsistencies)
  - Does NOT try to understand business logic
  - Reports FACTS, not interpretations

OUTPUT STRUCTURE:
  .pf/
  |-- raw/                    # Immutable tool outputs (ground truth)
  |-- repo_index.db           # SQLite database with all code symbols
  |-- graphs.db               # Graph database (query with 'aud graph')
  +-- pipeline.log            # Detailed execution trace

USE THE COMMANDS:
    aud full                          # Complete security audit
    aud manual workflows              # See common workflows
    aud manual exit-codes             # Understand exit codes
""",
    },
    "workflows": {
        "title": "Common Workflows",
        "summary": "Typical usage patterns for TheAuditor",
        "explanation": """
FIRST TIME SETUP:
    aud full                          # Complete audit (auto-creates .pf/)

AFTER CODE CHANGES:
    aud workset --diff HEAD~1         # Identify changed files
    aud lint --workset                # Quality check changes (has --workset)
    aud taint                 # Run taint on full codebase

PULL REQUEST REVIEW:
    aud workset --diff main..feature  # What changed in PR
    aud impact --file api.py --line 1 # Check change impact
    aud detect-patterns               # Security pattern scan

SECURITY AUDIT:
    aud full --offline                # Complete offline audit
    aud taint --severity high # High severity taint issues
    aud manual severity               # Understand findings

PERFORMANCE OPTIMIZATION:
    aud cfg analyze                   # Find complex functions
    aud graph analyze                 # Find circular dependencies
    aud blueprint                     # Understand architecture

CI/CD PIPELINE:
    aud full --quiet || exit $?       # Fail on critical issues

UNDERSTANDING RESULTS:
    aud manual taint                  # Learn about concepts
    aud blueprint                     # Project overview

NOTE ON WORKSET:
Only these commands support --workset flag:
- aud lint --workset
- aud cfg analyze --workset
- aud graph build --workset
- aud graph analyze --workset
- aud workflows analyze --workset
- aud terraform provision --workset
""",
    },
    "exit-codes": {
        "title": "Exit Codes",
        "summary": "What TheAuditor's exit codes mean",
        "explanation": """
TheAuditor uses standardized exit codes for CI/CD automation:

EXIT CODES:
    0 = Success, no critical or high severity issues found
    1 = High severity findings detected (needs attention)
    2 = Critical security vulnerabilities found (block deployment)
    3 = Analysis incomplete or pipeline failed

USAGE IN CI/CD:
    # Fail pipeline on any issues
    aud full --quiet || exit $?

    # Fail only on critical
    aud full --quiet
    if [ $? -eq 2 ]; then
        echo "CRITICAL vulnerabilities found!"
        exit 1
    fi

    # Continue with warnings
    aud full --quiet
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 2 ]; then
        exit 1  # Block on critical
    elif [ $EXIT_CODE -eq 1 ]; then
        echo "Warning: High severity issues found"
    fi
""",
    },
    "env-vars": {
        "title": "Environment Variables",
        "summary": "Configuration options via environment variables",
        "explanation": """
TheAuditor can be configured via environment variables:

FILE SIZE LIMITS:
    THEAUDITOR_LIMITS_MAX_FILE_SIZE=2097152   # Max file size in bytes (default: 2MB)
    THEAUDITOR_LIMITS_MAX_CHUNK_SIZE=65536    # Max chunk size (default: 65KB)

TIMEOUTS:
    THEAUDITOR_TIMEOUT_SECONDS=1800           # Default timeout (default: 30 min)
    THEAUDITOR_TIMEOUT_TAINT_SECONDS=600      # Taint analysis timeout
    THEAUDITOR_TIMEOUT_LINT_SECONDS=300       # Linting timeout

PERFORMANCE:
    THEAUDITOR_DB_BATCH_SIZE=200              # Database batch insert size

EXAMPLES:
    # Increase file size limit for large files
    export THEAUDITOR_LIMITS_MAX_FILE_SIZE=5242880  # 5MB
    aud full

    # Increase timeout for large codebase
    export THEAUDITOR_TIMEOUT_SECONDS=3600  # 1 hour
    aud full

    # Optimize for SSD with larger batches
    export THEAUDITOR_DB_BATCH_SIZE=500
    aud full
""",
    },
    "database": {
        "title": "Database Schema Reference",
        "summary": "Tables, indexes, and manual SQL queries for repo_index.db",
        "explanation": """
TheAuditor stores all indexed data in SQLite databases that you can query
directly using Python's sqlite3 module.

DATABASE LOCATIONS:
    .pf/repo_index.db     - Main code index (250+ tables, 200k+ rows)
    .pf/graphs.db         - Import/call graph (optional)

KEY TABLES:

    symbols (33k rows)
        - Function/class/variable definitions
        - Columns: name, type, file, line, end_line, scope
        - Index: symbols.name for O(log n) lookup

    function_call_args (13k rows)
        - Every function call with arguments
        - Columns: caller_function, callee_function, file, line, arguments
        - Index: callee_function for caller lookup

    assignments (42k rows)
        - Variable assignments with source expressions
        - Columns: target_var, source_expr, file, line, in_function
        - Used for data flow analysis

    api_endpoints (185 rows)
        - REST API routes
        - Columns: method, path, handler_function, file, line
        - Tracks auth controls via api_endpoint_controls junction

    imports (7k rows)
        - Import statements
        - Columns: file, module_name, style, line
        - Used for dependency tracking

JUNCTION TABLES (for normalized queries):
    assignment_sources        - Which vars are read in assignments
    function_return_sources   - Which vars are returned from functions
    api_endpoint_controls     - Which auth controls protect endpoints
    import_style_names        - Which symbols are imported

MANUAL QUERIES (Python):

    import sqlite3
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    # Find all functions in a file
    cursor.execute('''
        SELECT name, line FROM symbols
        WHERE file LIKE '%auth.py%' AND type = 'function'
        ORDER BY line
    ''')

    # Find callers of a function
    cursor.execute('''
        SELECT caller_function, file, line
        FROM function_call_args
        WHERE callee_function = 'validateUser'
    ''')

    # Find all API endpoints
    cursor.execute('''
        SELECT method, path, handler_function, file
        FROM api_endpoints
        ORDER BY path
    ''')

    conn.close()

SCHEMA DOCUMENTATION:
    See: theauditor/indexer/schema.py for complete table definitions
    Each table includes column types, indexes, and constraints.
""",
    },
    "troubleshooting": {
        "title": "Troubleshooting Guide",
        "summary": "Common errors and solutions for TheAuditor",
        "explanation": """
COMMON ERRORS AND SOLUTIONS:

ERROR: "No .pf directory found"
    CAUSE: Haven't run aud full yet
    FIX: Run 'aud full' to create .pf/ and build index
    NOTE: All query commands require indexed data

ERROR: "Graph database not found"
    CAUSE: graphs.db not built (only for dependency queries)
    FIX: Run 'aud graph build'
    NOTE: Only needed for --show-dependencies/--show-dependents

SYMPTOM: Empty results but symbol exists in code
    CAUSE 1: Typo in symbol name (case-sensitive)
    FIX: Run 'aud query --symbol foo' to see exact name

    CAUSE 2: Database stale (code changed since last index)
    FIX: Re-run 'aud full' to rebuild index

    CAUSE 3: Unqualified method name
    FIX: Methods stored as ClassName.methodName
         Run 'aud query --symbol bar' to find canonical name
         Then use exact name: 'aud query --symbol Foo.bar'

SYMPTOM: Slow queries (>50ms)
    CAUSE: Large project + high --depth
    FIX: Reduce --depth to 1-2
    NOTE: depth=5 can traverse 10k+ nodes

SYMPTOM: Missing expected results
    CAUSE: Dynamic calls (obj[variable]()) not indexed
    FIX: Use taint analysis for dynamic dispatch
    NOTE: Static analysis cannot resolve all dynamic behavior

SYMPTOM: Unicode/emoji errors on Windows
    CAUSE: CP1252 encoding cannot handle emojis
    FIX: TheAuditor uses ASCII-only output
    NOTE: If you see encoding errors, report the bug

SYMPTOM: Command hangs during analysis
    CAUSE: Large file or infinite loop in code
    FIX: Set timeout: THEAUDITOR_TIMEOUT_SECONDS=600
    NOTE: Check pipeline.log for progress

GETTING HELP:
    aud manual <concept>     - Learn about specific concepts
    aud manual --list        - See all available topics
    aud <command> --help     - Command-specific help
""",
    },
    "rust": {
        "title": "Rust Language Support",
        "summary": "Rust-specific analysis including modules, impl blocks, traits, and unsafe code",
        "explanation": """
TheAuditor provides comprehensive Rust support with 20 dedicated tables for
extracting and analyzing Rust codebases. This includes module resolution,
trait implementations, unsafe code detection, and lifetime analysis.

RUST TABLES (20 total):

  Core Tables:
    rust_modules              - Crate and module definitions
    rust_use_statements       - Use imports with resolution
    rust_structs              - Struct definitions with generics
    rust_enums                - Enum types and variants
    rust_traits               - Trait definitions

  Implementation:
    rust_impl_blocks          - impl blocks (inherent + trait)
    rust_impl_functions       - Functions within impl blocks
    rust_trait_methods        - Trait method signatures
    rust_struct_fields        - Struct field definitions
    rust_enum_variants        - Enum variant definitions

  Functions & Macros:
    rust_functions            - Standalone functions
    rust_macros               - Macro definitions (macro_rules!)
    rust_macro_invocations    - Macro usage sites

  Safety & Lifetimes:
    rust_unsafe_blocks        - Unsafe blocks with operation catalog
    rust_lifetimes            - Lifetime parameters
    rust_type_aliases         - Type alias definitions

  Cargo Integration:
    rust_crate_dependencies   - Cargo.toml dependencies
    rust_crate_features       - Feature flags

  Analysis Metadata:
    rust_call_graph           - Function call relationships

MODULE RESOLUTION:
TheAuditor resolves Rust's complex module system automatically:

  - crate::     -> Absolute path from crate root
  - super::     -> Parent module
  - self::      -> Current module
  - use aliases -> Imported names to canonical paths

  Example resolution:
    use std::collections::HashMap;
    // HashMap -> std::collections::HashMap

    use crate::models::User as U;
    // U -> crate::models::User

UNSAFE CODE ANALYSIS:
The rust_unsafe_blocks table catalogs unsafe operations:

  Operation Types:
    - ptr_deref:     Raw pointer dereferences (*ptr)
    - unsafe_call:   Calls to unsafe functions (transmute, from_raw)
    - ptr_cast:      Pointer casts (as_ptr, as_mut_ptr)
    - static_access: Mutable static variable access

  Query unsafe code:
    SELECT file, line, operations_json
    FROM rust_unsafe_blocks
    WHERE operations_json LIKE '%ptr_deref%'

EXAMPLE QUERIES (Python):

    import sqlite3
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    # Find all trait implementations
    cursor.execute('''
        SELECT file, target_type_raw, trait_name, target_type_resolved
        FROM rust_impl_blocks
        WHERE trait_name IS NOT NULL
        ORDER BY trait_name
    ''')

    # Find all public functions
    cursor.execute('''
        SELECT name, file, line, is_async
        FROM rust_functions
        WHERE visibility = 'pub'
    ''')

    # Find unsafe blocks with pointer dereferences
    cursor.execute('''
        SELECT file, line, operations_json
        FROM rust_unsafe_blocks
        WHERE operations_json LIKE '%ptr_deref%'
    ''')

    # Trace module imports
    cursor.execute('''
        SELECT file_path, import_path, local_name, canonical_path
        FROM rust_use_statements
        WHERE local_name IS NOT NULL
        ORDER BY file_path
    ''')

    # Find all async functions
    cursor.execute('''
        SELECT name, file, line, return_type
        FROM rust_functions
        WHERE is_async = 1
    ''')

    conn.close()

USE THE COMMANDS:
    aud full --index              # Index Rust files (*.rs)
    aud query --file src/main.rs  # Query specific file
    aud graph build               # Build call graph including Rust

SUPPORTED FEATURES:
    - Async functions (async fn)
    - Generic parameters (<T: Trait>)
    - Lifetime parameters ('a, 'static)
    - Visibility modifiers (pub, pub(crate))
    - Attribute macros (#[derive], #[test])
    - Macro rules (macro_rules!)
    - Associated types and constants
    - Extern blocks (extern "C")

CARGO INTEGRATION:
TheAuditor parses Cargo.toml for dependency analysis:

    SELECT crate_name, version, is_dev, is_optional
    FROM rust_crate_dependencies
    WHERE is_dev = 0

CROSS-LANGUAGE ANALYSIS:
Rust modules integrate with TheAuditor's full-stack analysis:
    - Import graph includes Rust use statements
    - Call graph connects Rust functions
    - Security patterns detect unsafe code misuse
""",
    },
    "callgraph": {
        "title": "Call Graph Analysis",
        "summary": "Function-level call relationships for execution path tracing",
        "explanation": """
A call graph maps which functions call which other functions. Unlike the import
graph (file-level), the call graph operates at function granularity, enabling
precise execution path analysis and security tracing.

WHY CALL GRAPHS MATTER:

Taint Analysis:
  - Track how user input flows through function calls
  - Find paths from sources (input) to sinks (SQL, exec, etc.)
  - Identify intermediate functions that transform data

Dead Code Detection:
  - Functions with no incoming edges are potentially unused
  - Entry points are exceptions (main, handlers, callbacks)

Impact Analysis:
  - Change a function? Call graph shows all callers
  - Recursive impact: callers of callers, etc.

Security Auditing:
  - Find all paths to dangerous functions
  - Verify authentication checks on all call chains
  - Identify functions that bypass security layers

CALL GRAPH STRUCTURE:

Nodes: Functions and methods
  - Stored with: file, line, name, type (function/method)
  - Methods include: ClassName.methodName

Edges: Call relationships
  - Direction: caller -> callee
  - Stored with: call site (file, line)
  - Multiple edges possible (same caller calls same callee multiple places)

STATIC VS DYNAMIC CALLS:

Static Calls (tracked):
  - foo()
  - obj.method()
  - Class.static_method()

Dynamic Calls (NOT tracked):
  - obj[variable]()
  - getattr(obj, name)()
  - eval('function()')

TheAuditor only tracks static calls that can be resolved from source code.
Dynamic dispatch requires runtime tracing.

EXAMPLE QUERIES (Python):

    import sqlite3
    conn = sqlite3.connect('.pf/graphs.db')
    cursor = conn.cursor()

    # Find all callers of authenticate_user
    cursor.execute('''
        SELECT e.source, e.file, e.line
        FROM edges e
        WHERE e.target LIKE '%authenticate_user%'
        AND e.graph_type = 'call'
    ''')

    # Find all call graph nodes (functions)
    cursor.execute('''
        SELECT id, file, type
        FROM nodes
        WHERE graph_type = 'call'
    ''')

    # Find functions that call a specific target
    cursor.execute('''
        SELECT DISTINCT e.source
        FROM edges e
        WHERE e.target LIKE '%db.execute%'
        AND e.graph_type = 'call'
    ''')

USE THE COMMANDS:
    aud graph build       # Build call graph (and import graph)
    aud graph query --calls func    # What does func call?
    aud graph query --uses func     # Who calls func?
    aud graph viz --graph-type call # Visualize call graph

RELATED CONCEPTS:
    aud manual graph         # Import graph (file-level)
    aud manual dependencies  # Package-level dependencies
    aud manual taint         # Uses call graph for taint tracking
""",
    },
    "dependencies": {
        "title": "Dependency Analysis",
        "summary": "Package dependencies, version checking, and vulnerability scanning",
        "explanation": """
Dependency analysis covers multiple levels: file imports (import graph),
function calls (call graph), and package dependencies (npm, pip, cargo).
This entry focuses on PACKAGE dependencies - third-party libraries your
project depends on.

THREE DEPENDENCY LEVELS:

1. File Dependencies (Import Graph):
   - src/auth.py imports src/utils.py
   - Tracked by: aud graph build
   - Query with: aud graph query --uses file.py

2. Function Dependencies (Call Graph):
   - authenticate() calls hash_password()
   - Tracked by: aud graph build
   - Query with: aud graph query --calls func

3. Package Dependencies (This Entry):
   - Your project depends on flask==2.0.1
   - Tracked by: aud deps
   - Vulnerability scan: aud deps --vuln-scan

PACKAGE DEPENDENCY SOURCES:

Python:
  - requirements.txt, requirements-*.txt
  - pyproject.toml (Poetry, setuptools)
  - setup.py (legacy)

JavaScript/TypeScript:
  - package.json
  - package-lock.json (exact versions)
  - yarn.lock

Rust:
  - Cargo.toml
  - Cargo.lock

Go:
  - go.mod
  - go.sum

DEPENDENCY ANALYSIS MODES:

Inventory (default):
  aud deps
  Lists all dependencies with versions, sources, types

Version Checking:
  aud deps --check-latest
  Compares installed vs latest available versions

Vulnerability Scanning:
  aud deps --vuln-scan
  Runs npm audit + OSV-Scanner for security issues
  Exit code 2 if critical vulnerabilities found

DEPENDENCY GRAPH VS PACKAGE DEPS:

Import/Call Graphs:
  - YOUR code relationships
  - Internal architecture
  - Built from source analysis

Package Dependencies:
  - EXTERNAL library relationships
  - Third-party code you consume
  - Parsed from manifest files

Both are "dependencies" but at different abstraction levels.

SECURITY IMPLICATIONS:

Direct Dependencies:
  - Libraries you explicitly install
  - You chose them, you're responsible

Transitive Dependencies:
  - Libraries your dependencies depend on
  - Often 10x more than direct deps
  - Supply chain attack vector

Vulnerability Classes:
  - Known CVEs in specific versions
  - Deprecated packages (no longer maintained)
  - Typosquatting (malicious package names)

TYPICAL WORKFLOW:
    # 1. Build index (includes dependency parsing)
    aud full

    # 2. Check for outdated packages
    aud deps --check-latest

    # 3. Scan for vulnerabilities
    aud deps --vuln-scan

    # 4. View dependency summary
    aud blueprint --deps

USE THE COMMANDS:
    aud deps                    # List all dependencies
    aud deps --check-latest     # Check for updates
    aud deps --vuln-scan        # Security scan
    aud blueprint --deps        # Architecture view

RELATED CONCEPTS:
    aud manual graph      # File-level import graph
    aud manual callgraph  # Function-level call graph
    aud manual frameworks # Framework detection
""",
    },
    "graph": {
        "title": "Dependency and Call Graph Analysis",
        "summary": "Build and analyze import/call graphs for architecture understanding",
        "explanation": """
Dependency and call graph analysis maps relationships between code components
to understand architecture, detect issues, and measure change impact.

TWO TYPES OF GRAPHS:

Import Graph (File-level):
  - Nodes: Files and modules
  - Edges: Import relationships (who imports what)
  - Use: Understand module structure, find circular imports

Call Graph (Function-level):
  - Nodes: Functions and methods
  - Edges: Call relationships (who calls what)
  - Use: Trace execution paths, find unused functions

WHAT GRAPHS REVEAL:

Circular Dependencies:
  - Import cycles that break modular design
  - Example: A imports B, B imports C, C imports A
  - Impact: Harder to test, refactor, and understand

Architectural Hotspots:
  - Modules with >20 dependencies (high coupling)
  - Single points of failure
  - Candidates for refactoring

Change Impact (Blast Radius):
  - Upstream: Who depends on this? (callers, importers)
  - Downstream: What does this depend on? (callees, imports)
  - Total affected files for a code change

Hidden Coupling:
  - Indirect dependencies through intermediaries
  - A doesn't import C directly, but A->B->C creates coupling

DATABASE STRUCTURE:
The graph database (.pf/graphs.db) uses unified tables with graph_type column:

  nodes table:
    - id, file, lang, loc, churn, type, graph_type, metadata
    - graph_type: 'import' | 'call' | 'data_flow' | 'terraform_provisioning'

  edges table:
    - source, target, type, file, line, graph_type, metadata
    - graph_type: 'import' | 'call' | 'data_flow'

  analysis_results table:
    - Stores cycle detection and hotspot analysis results

Query by graph_type to filter:
    SELECT * FROM nodes WHERE graph_type = 'call'
    SELECT * FROM edges WHERE graph_type = 'import'

Note: Graphs stored separately from repo_index.db for query optimization.

TYPICAL WORKFLOW:
    aud full                              # Build code index
    aud graph build                       # Construct graphs
    aud graph analyze                     # Find issues
    aud graph query --uses auth.py        # Who uses auth?
    aud graph viz --view cycles           # Visualize cycles

USE THE COMMANDS:
    aud graph build       # Build import and call graphs
    aud graph build-dfg   # Build data flow graph
    aud graph analyze     # Detect cycles, hotspots
    aud graph query       # Query relationships
    aud graph viz         # Generate visualizations

VISUALIZATION MODES:
    --view full      Complete graph
    --view cycles    Only circular dependencies
    --view hotspots  Top connected nodes
    --view layers    Architectural layers
    --view impact    Change impact radius

RELATED CONCEPTS:
    aud manual impact     # Change impact analysis
    aud manual cfg        # Control flow graphs
""",
    },
    "architecture": {
        "title": "System Architecture",
        "summary": "How TheAuditor's analysis pipeline and query engine work",
        "explanation": """
EXTRACTION PIPELINE:
    Source Code
        |
        v
    tree-sitter (AST parsing)
        |
        v
    Language Extractors (Python, JS/TS, etc.)
        |
        v
    Database Manager
        |
        v
    repo_index.db (SQLite)

SCHEMA NORMALIZATION (v1.2+):
    OLD: JSON TEXT columns with LIKE queries (slow)
         assignments.source_vars = '["x", "y", "z"]'

    NEW: Junction tables with JOIN queries (fast)
         assignment_sources table:
           (file, line, target_var, source_var_name='x')
           (file, line, target_var, source_var_name='y')
           (file, line, target_var, source_var_name='z')

    Benefits:
    - 10x faster queries (indexed lookups vs JSON parsing)
    - Standard SQL JOINs work correctly
    - Type-safe queries (no JSON parsing errors)

QUERY ENGINE ARCHITECTURE:
    User Request
        |
        v
    CLI (commands/query.py)
        |
        v
    CodeQueryEngine (context/query.py)
        |
        v
    Direct SQL SELECT (no ORM overhead)
        |
        v
    SQLite (repo_index.db)
        |
        v
    Formatters (text/json/tree)
        |
        v
    Output

TWO-DATABASE DESIGN:
    repo_index.db (181MB):
        - Raw extracted facts from AST parsing
        - Regenerated on every 'aud full'
        - Used by: rules, taint, FCE, context queries

    graphs.db (126MB):
        - Pre-computed graph structures
        - Built from repo_index.db
        - Used by: 'aud graph' commands only

INDEX MAINTENANCE:
    - Database is REGENERATED on every 'aud full'
    - NO migrations (fresh build every time)
    - Code changes -> re-run 'aud full' -> database updated
    - Database is TRUTH SOURCE (not code files)

PERFORMANCE CHARACTERISTICS:
    Query time: <10ms (indexed lookups)
    Database size: 20-50MB typical project
    Memory usage: <50MB for query engine
    BFS traversal: O(n) where n = nodes visited
    JOIN queries: O(log n) with proper indexes

JUNCTION TABLE PATTERN:
    Parent Table <-> Junction Table <-> (values)
    assignments  <-> assignment_sources <-> (source variables)

    Composite key: file + line + target_var
    Enables: Many-to-many relationships, fast lookups
""",
    },
    "context": {
        "title": "Semantic Context Classification",
        "summary": "Apply business logic rules to classify findings during migrations and refactoring",
        "explanation": """
Semantic context classification lets you interpret analysis findings based on your
project's business context, refactoring state, or migration phase. Instead of treating
all findings equally, you define YAML rules that classify issues as obsolete, current,
or transitional based on your organization's situation.

THE PROBLEM IT SOLVES:
During migrations and refactorings, your codebase is temporarily inconsistent:
- Old patterns exist alongside new ones (by design)
- Security tools flag the old patterns as issues
- But you KNOW those patterns are being replaced
- You need a way to track what's intentional vs actual problems

CLASSIFICATION STATES:

1. OBSOLETE (Must Fix):
   Code using deprecated patterns that need immediate attention.
   Example: JWT authentication in files that should use OAuth2

2. CURRENT (Correct):
   Code following current standards - the right pattern.
   Example: OAuth2 calls in the new auth system

3. TRANSITIONAL (Acceptable Temporarily):
   Old patterns that are acceptable during a migration window.
   Example: Legacy API endpoints during 30-day deprecation period

HOW IT WORKS:
1. You create a YAML file defining classification rules
2. Rules match findings by pattern, file path, or finding type
3. Run 'aud context --file rules.yaml' after analysis
4. Findings are classified and grouped by state
5. Report shows what needs fixing vs what's acceptable

YAML RULE FORMAT:
    refactor_context:
      name: "OAuth2 Migration"
      rules:
        - pattern: "jwt.sign"
          state: "obsolete"
          reason: "JWT auth deprecated, use OAuth2"
          files: ["api/auth/*.py"]

        - pattern: "oauth2.authorize"
          state: "current"
          reason: "New OAuth2 standard"

        - pattern: "legacy_api_key"
          state: "transitional"
          reason: "Allowed during 30-day migration"

USE CASES:

Authentication Migration:
    Mark old auth patterns obsolete, new patterns current
    Track which files still need migration

API Versioning:
    v1 endpoints transitional during deprecation
    v2 endpoints current

Framework Upgrade:
    Old framework patterns obsolete
    New framework patterns current

Database Migration:
    Old table references obsolete
    New schema references current

EXAMPLE WORKFLOW:
    # 1. Run analysis
    aud full

    # 2. Classify findings with your business rules
    aud context --file oauth_migration.yaml

    # 3. Review classification report
    # Shows: 15 obsolete, 120 current, 8 transitional

    # 4. Focus on obsolete findings first
    # Transitional findings are acceptable (for now)

OUTPUT FORMAT:
    .pf/raw/semantic_context_<name>.json
    {
      "context_name": "OAuth2 Migration",
      "classified_findings": {
        "obsolete": [...],
        "current": [...],
        "transitional": [...]
      },
      "summary": {
        "obsolete_count": 15,
        "current_count": 120,
        "transitional_count": 8
      }
    }

IMPORTANT DISTINCTION:
Context classification is for WORKFLOW MANAGEMENT, not security bypass.
- "Transitional" findings are still real issues
- They just have a documented exception for a limited time
- You're tracking technical debt, not ignoring it

USE THE COMMAND:
    aud context --file rules.yaml            # Classify findings
    aud context --file rules.yaml --verbose  # Show all classified findings
    aud context --file rules.yaml -o out.json # Custom output path
""",
    },
}
