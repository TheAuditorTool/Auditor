"""Explain TheAuditor concepts and terminology."""

import click

EXPLANATIONS: dict[str, dict[str, str]] = {
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
1. Identify taint sources (e.g., request.body, input())
2. Track data flow through variables and functions
3. Check if tainted data reaches dangerous sinks
4. Report potential vulnerabilities

EXAMPLE VULNERABILITY:
    user_input = request.body.get('name')  # SOURCE: User input is tainted
    query = f"SELECT * FROM users WHERE name = '{user_input}'"  # Taint propagates
    db.execute(query)  # SINK: SQL injection vulnerability!

WHAT THEAUDITOR DETECTS:
- SQL Injection (tainted data -> SQL query)
- Command Injection (tainted data -> system command)
- XSS (tainted data -> HTML output)
- Path Traversal (tainted data -> file path)
- LDAP/NoSQL Injection

USE THE COMMAND:
    aud taint-analyze                  # Full taint analysis
    aud taint-analyze --severity high  # Only high severity issues
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
- Transitive dependencies: Multi-hop relationships

WHY USE WORKSETS:
1. Performance: Analyze 10 files instead of 1000 (100x faster)
2. Relevance: Focus on what actually changed
3. CI/CD: Only check modified code in pull requests
4. Incremental: Build on previous analysis

HOW IT WORKS:
1. Identify seed files (from git diff, patterns, or manual selection)
2. Trace dependencies using the symbol database
3. Expand to include all potentially affected files
4. Save as .pf/workset.json for other commands to use

EXAMPLE WORKFLOW:
    aud workset --diff HEAD~1          # What changed in last commit?
    aud lint --workset                 # Lint only those files
    aud taint-analyze --workset        # Security check changed code

WORKSET STRATEGIES:
- Git-based: --diff main..feature
- Pattern-based: --include "*/api/*"
- Manual: --files auth.py user.py
- Everything: --all
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
    aud taint-analyze --severity critical   # Only critical issues
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
    aud lint --workset                # Quality check changes
    aud taint-analyze --workset       # Security check changes

PULL REQUEST REVIEW:
    aud workset --diff main..feature  # What changed in PR
    aud impact --file api.py --line 1 # Check change impact
    aud detect-patterns --workset     # Security patterns

SECURITY AUDIT:
    aud full --offline                # Complete offline audit
    aud deps --vuln-scan              # Check for CVEs
    aud manual severity               # Understand findings

PERFORMANCE OPTIMIZATION:
    aud cfg analyze --threshold 20    # Find complex functions
    aud graph analyze                 # Find circular dependencies
    aud structure                     # Understand architecture

CI/CD PIPELINE:
    aud full --quiet || exit $?       # Fail on critical issues

UNDERSTANDING RESULTS:
    aud manual taint                  # Learn about concepts
    aud structure                     # Project overview
    aud report --print-stats          # Summary statistics
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
}


@click.command("manual")
@click.argument("concept", required=False)
@click.option("--list", "list_concepts", is_flag=True, help="List all available concepts")
def manual(concept, list_concepts):
    """Interactive documentation for TheAuditor concepts, terminology, and security analysis techniques.

    Built-in reference system that explains security concepts, analysis methodologies, and tool-specific
    terminology through detailed, example-rich explanations optimized for learning. Covers 10 core topics
    from taint analysis to Rust language support, each with practical examples and related commands.

    AI ASSISTANT CONTEXT:
      Purpose: Provide interactive documentation for TheAuditor concepts
      Input: Concept name (taint, workset, fce, cfg, etc.)
      Output: Terminal-formatted explanation with examples
      Prerequisites: None (standalone documentation)
      Integration: Referenced throughout other command help texts
      Performance: Instant (no I/O, pure string formatting)

    AVAILABLE CONCEPTS (10 topics):
      taint:
        - Data flow tracking from untrusted sources to dangerous sinks
        - Detects SQL injection, XSS, command injection
        - Example: user_input -> query string -> database execution

      workset:
        - Focused file subset for targeted analysis (10-100x faster)
        - Git diff integration for PR review workflows
        - Dependency expansion algorithm

      fce:
        - Feed-forward Correlation Engine for compound risk detection
        - Combines static analysis + git churn + test coverage
        - Identifies hot spots (high churn + low coverage + vulnerabilities)

      cfg:
        - Control Flow Graphs for complexity and reachability analysis
        - Cyclomatic complexity calculation
        - Dead code detection via unreachable blocks

      impact:
        - Change impact analysis (blast radius)
        - Transitive dependency tracking
        - PR risk assessment

      pipeline:
        - Execution stages (index -> analyze -> correlate -> report)
        - Tool orchestration and data flow
        - .pf/ directory structure

      severity:
        - Finding classification (CRITICAL/HIGH/MEDIUM/LOW)
        - CVSS scoring integration
        - Severity promotion rules

      patterns:
        - Pattern detection system architecture
        - 2000+ built-in security rules
        - Custom pattern authoring

      insights:
        - ML-powered risk prediction
        - Historical learning from audit runs
        - Root cause vs symptom classification

      rust:
        - Rust language analysis (20 tables)
        - Module resolution (crate::, super::, use aliases)
        - Unsafe code detection and operation cataloging

    HOW IT WORKS (Documentation Lookup):
      1. Concept Validation:
         - Checks if concept exists in EXPLANATIONS dict
         - Shows available concepts if not found

      2. Explanation Retrieval:
         - Loads detailed explanation from internal database
         - Includes: title, summary, full explanation, examples

      3. Formatting:
         - Terminal-optimized layout with sections
         - Syntax highlighting for code examples
         - Links to related commands

    EXAMPLES:
      # Use Case 1: Learn about taint analysis
      aud manual taint

      # Use Case 2: Understand workset concept
      aud manual workset

      # Use Case 3: List all available topics
      aud manual --list

      # Use Case 4: Understand FCE correlation
      aud manual fce

    COMMON WORKFLOWS:
      Before First Analysis:
        aud manual pipeline      # Understand execution flow
        aud manual taint         # Learn security analysis
        aud init && aud full

      Understanding Command Output:
        aud taint-analyze
        aud manual taint         # Learn what taint findings mean

      Troubleshooting Performance:
        aud manual workset       # Learn optimization techniques
        aud workset --diff HEAD

    OUTPUT FORMAT (Terminal Display):
      CONCEPT: Taint Analysis
      ----------------------------------------
      SUMMARY: Tracks untrusted data flow from sources to dangerous sinks

      EXPLANATION:
      Taint analysis is a security technique that tracks how untrusted data...
      [Detailed multi-paragraph explanation with examples]

      USE THE COMMAND:
        aud taint-analyze
        aud taint-analyze --severity high

    PERFORMANCE EXPECTATIONS:
      Instant: <1ms (pure string formatting, no I/O)

    FLAG INTERACTIONS:
      --list: Shows all 9 available concepts with one-line summaries

    PREREQUISITES:
      None (standalone documentation, works offline)

    EXIT CODES:
      0 = Success, explanation displayed
      1 = Unknown concept (use --list to see available)

    RELATED COMMANDS:
      All commands reference specific concepts in their help text
      Use 'aud <command> --help' for command-specific documentation

    SEE ALSO:
      TheAuditor documentation: docs/
      Online docs: https://github.com/user/theauditor

    TROUBLESHOOTING:
      Concept not found:
        -> Use 'aud manual --list' to see all available concepts
        -> Check spelling (case-sensitive: 'taint' not 'Taint')
        -> Some advanced concepts may not have explanations yet

      Output formatting issues:
        -> Terminal width <80 chars may cause wrapping
        -> Use terminal with proper UTF-8 support
        -> Pipe to 'less' for scrolling: aud manual fce | less

    NOTE: Explanations are embedded in the CLI for offline use. They cover
    core concepts but not every command detail - use --help on specific commands
    for comprehensive usage information.
    """

    if list_concepts:
        click.echo("\nAvailable concepts to explain:\n")
        for key, info in EXPLANATIONS.items():
            click.echo(f"  {key:12} - {info['summary']}")
        click.echo("\nUse 'aud manual <concept>' for detailed information.")
        return

    if not concept:
        click.echo("Please specify a concept to explain or use --list to see available topics.")
        click.echo("\nExample: aud manual taint")
        return

    concept = concept.lower().strip()

    if concept not in EXPLANATIONS:
        click.echo(f"Unknown concept: '{concept}'")
        click.echo("\nAvailable concepts:")
        for key in EXPLANATIONS:
            click.echo(f"  - {key}")
        return

    info = EXPLANATIONS[concept]
    click.echo(f"\n{'=' * 70}")
    click.echo(f"{info['title'].upper()}")
    click.echo(f"{'=' * 70}")
    click.echo(info["explanation"])
    click.echo(f"{'=' * 70}\n")
