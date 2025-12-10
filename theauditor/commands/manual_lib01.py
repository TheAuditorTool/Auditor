"""Manual library part 1: Core concepts (taint through context)."""

EXPLANATIONS_01: dict[str, dict[str, str]] = {
    "taint": {
        "title": "Taint Analysis",
        "summary": "Tracks untrusted data flow from sources to dangerous sinks",
        "explanation": """
WHAT IT IS:
Taint analysis finds where user input reaches dangerous functions without
sanitization - the root cause of injection vulnerabilities (SQL injection,
XSS, command injection, path traversal).

WHEN TO USE IT:
- Security audit before deployment or release
- Investigating a reported vulnerability
- PR review for security-sensitive code changes
- After running aud full, to understand data flow paths
- When you need to trace how user input propagates through the codebase

HOW TO USE IT:

PREREQUISITES:
    aud full                           # Build database first (required)

STEPS:
1. Run taint analysis:
    aud taint                          # Full analysis with defaults
    aud taint --severity critical      # Only critical findings
    aud taint --verbose                # Show full taint paths

2. Query findings: aud query --findings --source taint

3. For each finding, verify:
   - Is the source actually user-controlled?
   - Is there sanitization the tool missed?
   - Is this a true positive requiring a fix?

EXAMPLE - Finding SQL Injection:
    aud full && aud taint --severity high
    # Output shows paths from request.body to db.execute()
    # Each path shows: source variable, propagation steps, sink function

WHAT IT DETECTS:
- SQL Injection: tainted data flows to cursor.execute(), db.query()
- Command Injection: tainted data flows to os.system(), subprocess.call()
- XSS: tainted data flows to render without escaping
- Path Traversal: tainted data flows to open(), Path operations
- LDAP/NoSQL Injection: tainted data flows to ldap/mongo queries

COMBINING WITH OTHER TOOLS:
- After taint: run aud fce to correlate with other findings
- Use aud explain <function> to understand context around a finding
- Use aud boundaries to check validation distance from entry points
- Use aud blueprint --taint to see taint summary without re-running analysis

AGENT WORKFLOW:
When using the security agent (/theauditor:security), taint analysis is
Phase 2 of the workflow. The agent queries existing taint results with:
    aud blueprint --taint
This reads from database (fast) instead of re-running analysis (slow).

KEY OPTIONS:
- --severity: Filter by severity (critical, high, medium, low, all)
- --mode: backward (IFDS, default), forward (faster), complete (thorough)
- --verbose: Show full taint propagation paths
- --json: Machine-readable output for scripting
- --memory-limit N: Limit cache to N MB on memory-constrained systems

COMMON MISTAKES:
- Running taint before aud full: No database = no analysis
- Ignoring MEDIUM findings: They often combine to CRITICAL via FCE
- Not using --json for detailed output: Terminal output is summary only
- Using --mode forward for security audits: Less accurate, use backward

EXIT CODES:
- 0: Success, no vulnerabilities found
- 1: High severity vulnerabilities detected
- 2: Critical security vulnerabilities found

RELATED:
Commands: aud taint, aud fce, aud boundaries, aud blueprint --taint
Topics: aud manual fce, aud manual boundaries, aud manual patterns
""",
    },
    "workset": {
        "title": "Workset",
        "summary": "A focused subset of files for targeted analysis",
        "explanation": """
WHAT IT IS:
A workset is a focused file list for targeted analysis. Instead of analyzing
your entire codebase, you define which files matter (changed files, specific
directories, or patterns) and TheAuditor expands to include their dependencies.
Result: 10x-100x faster analysis focused on what actually matters.

WHEN TO USE IT:
- PR reviews: Analyze only files changed in the pull request
- Incremental CI: Check changed code without full rebuild
- Feature work: Focus on specific modules during development
- Performance: Large codebase but only care about a subset
- Post-commit hooks: Quick lint of just-changed files

HOW TO USE IT:
PREREQUISITES:
    aud full                              # Build database for dependency expansion

STEPS:
    1. Create workset from your use case:
       aud workset --diff main..HEAD      # PR changes
       aud workset --diff HEAD~1          # Last commit
       aud workset --files src/auth.py    # Specific file

    2. Run targeted analysis:
       aud lint --workset                 # Lint only workset files
       aud cfg analyze --workset          # Complexity check

    3. Review results (only affected files shown)

EXAMPLE - PR Review Workflow:
    aud full                              # Ensure database is current
    aud workset --diff main..HEAD         # What changed in PR?
    aud lint --workset                    # Lint only those files
    aud cfg analyze --workset             # Check complexity

COMBINING WITH OTHER TOOLS:
- Before workset: Run aud full to enable dependency expansion
- After workset: Commands with --workset flag use the file list
- With git: Use --diff for automatic change detection
- In CI/CD: Chain workset -> lint for fast incremental checks

COMMANDS THAT SUPPORT --workset:
    aud lint --workset                    # Code quality
    aud cfg analyze --workset             # Complexity analysis
    aud graph build --workset             # Build partial graph
    aud graph analyze --workset           # Analyze dependencies
    aud workflows analyze --workset       # GitHub Actions
    aud terraform provision --workset     # IaC analysis

WHAT IT CONTAINS:
- Seed files: Your specified files (from --diff, --files, or --include)
- Expanded files: Files that import the seed files
- Transitive deps: Multi-hop dependents (up to --max-depth)

COMMAND OPTIONS:
    aud workset --diff main..HEAD         # Git diff range
    aud workset --diff HEAD~1             # Last commit
    aud workset --files auth.py api.py    # Explicit files
    aud workset --include "*/api/*"       # Glob pattern
    aud workset --exclude "test/*"        # Skip patterns
    aud workset --max-depth 3             # Limit expansion
    aud workset --all                     # All source files
    aud workset --print-stats             # Show summary

RELATED:
Commands: aud workset, aud lint, aud cfg analyze, aud graph build
Topics: aud manual lint, aud manual cfg, aud manual graph

COMMON MISTAKES:
- Using --workset without creating workset first: Command fails silently
  -> Always run aud workset before commands with --workset flag
- Skipping aud full before workset: Dependency expansion needs database
  -> Run aud full to populate refs table for accurate expansion
- Forgetting --exclude for tests: Workset includes test file dependents
  -> Add --exclude "test/*" if you only want production code
- Max-depth too high: Includes too many files, losing benefit
  -> Use --max-depth 2-3 for focused analysis

OUTPUT:
- Writes .pf/workset.json with file list
- Other commands read this file when --workset flag is used
""",
    },
    "fce": {
        "title": "Factual Correlation Engine",
        "summary": "Correlates findings from multiple tools to detect compound vulnerabilities",
        "explanation": """
WHAT IT IS:
FCE identifies where multiple independent analysis signals converge on the
same code location. When static analysis, taint tracking, complexity metrics,
and churn data all flag the same file, that's a high-confidence hot spot.

WHEN TO USE IT:
- After aud full, to see where findings cluster
- Identifying high-priority files to review
- Finding compound vulnerabilities (multiple low = one critical)
- Reducing false positives through cross-validation

HOW TO USE IT:

PREREQUISITES:
    aud full                           # Populates all analysis vectors

STEPS:
1. Run FCE:
    aud fce                            # Text report, min 2 vectors
    aud fce --min-vectors 3            # Only 3+ vector convergence
    aud fce --format json              # Machine-readable output

2. Interpret output:
    [3/4] [SF-T] src/auth/login.py
      |     |    |
      |     |    +-- File path
      |     +------- Vectors: S=Static, F=Flow, P=Process, T=Structural
      +------------- Density: 3 of 4 vectors present

3. Investigate high-density files:
    aud explain src/auth/login.py      # Get full context

EXAMPLE - Finding Hot Spots:
    aud full && aud fce --min-vectors 3
    # Shows files where 3+ independent signals converge
    # These are your highest-priority review targets

THE FOUR VECTORS:
- S (Static): Linter findings (ruff, eslint, patterns)
- F (Flow): Taint analysis findings
- P (Process): Churn analysis (high change frequency)
- T (Structural): Complexity metrics (CFG analysis)

WHY VECTOR COUNT MATTERS:
Multiple linters flagging same syntax error = 1 vector (all Static)
Ruff + Taint + Churn + Complexity on same file = 4 vectors (independent signals)

COMBINING WITH OTHER TOOLS:
- Run after aud full to use all analysis data
- Use aud explain on flagged files for detailed context
- Use aud taint for data flow details on F-vector findings
- Save report: aud fce --format json > fce_report.json

AGENT WORKFLOW:
The security agent runs FCE after taint and patterns to identify
convergence points. Results guide which files to investigate deeper.

KEY OPTIONS:
- --min-vectors N: Require N vectors (1-4, default 2)
- --format: text (human) or json (machine)
- --detailed: Include facts in text output

COMMON MISTAKES:
- Running fce before aud full: No data = no correlations
- Using --min-vectors 1: Shows everything, not useful
- Ignoring 2-vector files: Still worth reviewing
- Not using --detailed: Misses the evidence chain

EXIT CODES:
- 0: Success

RELATED:
Commands: aud fce, aud full, aud taint, aud detect-patterns
Topics: aud manual taint, aud manual patterns, aud manual severity
""",
    },
    "cfg": {
        "title": "Control Flow Graph",
        "summary": "Maps all possible execution paths through functions",
        "explanation": """
WHAT IT IS:
Control Flow Graph (CFG) analysis maps all possible execution paths through
functions to measure complexity, find unreachable code, and identify functions
that are too complex to test reliably.

WHEN TO USE IT:
- Code review: Find overly complex functions that need refactoring
- Testing: Calculate how many paths need test coverage
- Security audit: Complex functions hide vulnerabilities
- Refactoring: Identify candidates for simplification
- Dead code: Find unreachable code blocks

HOW TO USE IT:

PREREQUISITES:
    aud full                                  # Build the database first

STEPS:
1. Run complexity analysis to find problematic functions:
    aud cfg analyze                           # All functions
    aud cfg analyze --complexity-threshold 15 # Only high complexity

2. Find unreachable code blocks:
    aud cfg analyze --find-dead-code

3. Analyze a specific file:
    aud cfg analyze --file src/auth.py

4. Visualize a specific function (requires --file AND --function):
    aud cfg viz --file src/auth.py --function validate_token
    aud cfg viz --file src/auth.py --function validate_token --format svg

CYCLOMATIC COMPLEXITY GUIDE:
- 1-10: Simple, easy to test (good)
- 11-20: Moderate complexity, needs careful testing
- 21-50: High complexity, should be refactored
- 50+: Very high risk, almost impossible to test fully

EXAMPLE WORKFLOW - Finding Complex Functions:
    aud full                                  # Index codebase
    aud cfg analyze --complexity-threshold 20 # Find complex functions
    aud cfg viz --file src/api.py --function handle_request --format svg

COMBINING WITH OTHER TOOLS:
- After cfg analyze: Use aud deadcode to find unused functions
- For security: High complexity + security-sensitive = priority review
- With refactor: Complex functions are refactoring candidates
- For planning: Use aud impact before splitting complex functions

AGENT WORKFLOW:
The dataflow agent (/theauditor:dataflow) uses CFG analysis as part of
Phase 2 to understand execution paths. Query complexity with:
    aud cfg analyze --file <target>

COMMON MISTAKES:
- Running cfg without aud full first: No data to analyze
- Using aud cfg viz without --file: Command requires both --file AND --function
- Setting complexity threshold too low: Get flooded with false positives (use 15+)

RELATED:
Commands: aud cfg analyze, aud cfg viz, aud deadcode, aud graph analyze
Topics: aud manual deadcode, aud manual graph, aud manual architecture
""",
    },
    "impact": {
        "title": "Impact Analysis",
        "summary": "Measures the blast radius of code changes",
        "explanation": """
WHAT IT IS:
Impact analysis measures the blast radius of changing a function or class by
tracing upstream (who calls this) and downstream (what this calls) dependencies.
It answers: "What breaks if I change this?"

WHEN TO USE IT:
- Before refactoring: Understand scope before making changes
- API changes: See who uses an endpoint before modifying it
- Planning: Assess risk level for change proposals
- Dead code: If upstream is empty, code might be unused
- Architecture: Identify highly coupled code (coupling score)

HOW TO USE IT:

PREREQUISITES:
    aud full                                  # Build the database first

STEPS:
1. Query by symbol name (RECOMMENDED):
    aud impact --symbol AuthManager           # Exact match
    aud impact --symbol "process_*"           # Pattern match

2. Query with planning context (for refactoring):
    aud impact --symbol AuthManager --planning-context

3. Query by file and line (if symbol name unknown):
    aud impact --file src/auth.py --line 42

4. Cross-stack tracing (frontend to backend):
    aud impact --file src/api.js --line 50 --trace-to-backend

RISK LEVELS AND COUPLING SCORES:
- Low: <10 files, coupling <30 (safe to change)
- Medium: 10-30 files, coupling 30-70 (review callers, consider phased rollout)
- High: >30 files, coupling >70 (extract interface before refactoring)

Exit code 1 is returned for high impact changes (useful for CI gates).

EXAMPLE WORKFLOW - Pre-Refactor Assessment:
    aud full                                  # Index codebase
    aud impact --symbol UserService --planning-context
    aud deadcode | grep user_service.py       # Check for dead code first

COMBINING WITH OTHER TOOLS:
- Before refactor: Always run impact first to know blast radius
- With deadcode: If upstream is empty, code is likely unused
- With planning: Use --planning-context for agent-friendly output
- With graph: Impact uses the call graph, ensure aud graph build ran

AGENT WORKFLOW:
The planning agent (/theauditor:planning) uses impact analysis in Phase 2
(T2.6) to establish impact baseline before planning changes:
    aud impact --symbol <target> --planning-context

Coupling score interpretation:
- <30: LOW coupling - safe to change with minimal coordination
- 30-70: MEDIUM coupling - review callers, consider phased rollout
- >70: HIGH coupling - extract interface before refactoring

COMMON MISTAKES:
- Using --file without --line: Analyzes first symbol in file (may not be target)
- Missing --planning-context: Omits coupling score needed for planning
- Not running aud full first: No symbol data to analyze

RELATED:
Commands: aud impact, aud graph query, aud deadcode, aud query --show-callers
Topics: aud manual graph, aud manual callgraph, aud manual refactor
""",
    },
    "pipeline": {
        "title": "Analysis Pipeline",
        "summary": "TheAuditor's multi-phase execution pipeline with intelligent parallelization",
        "explanation": """
WHAT IT IS:
The pipeline is TheAuditor's orchestration system that runs multiple analysis phases
in optimized sequence. It builds databases, runs security scans, and correlates
findings - all from a single command.

WHEN TO USE IT:
- First time setup on any codebase
- After pulling new code changes
- Before submitting a pull request for review
- In CI/CD pipelines for automated security gates
- When you need comprehensive analysis (not just one tool)

HOW TO USE IT:

PREREQUISITES:
    None - the pipeline creates everything it needs

STEPS:
    1. Run the full pipeline:
       aud full                    # Complete multi-phase analysis

    2. Check the output directory:
       .pf/repo_index.db           # Symbol database (query with aud query)
       .pf/graphs.db               # Call and import graphs
       .pf/pipeline.log            # Detailed execution trace

    3. Review findings:
       aud blueprint --structure   # Architecture overview
       aud blueprint --taint       # Security findings summary

EXAMPLE - First Time Analysis:
    aud full                       # Creates .pf/ and runs all 20 phases
    aud blueprint                  # See what was found

PIPELINE STAGES (4 Stages, 20 Phases):

STAGE 1 - FOUNDATION (Sequential):
- index: Build symbol database from AST parsing
- detect-frameworks: Identify Django, Flask, React, Express, etc.

STAGE 2 - DATA PREPARATION (Sequential):
- workset: Identify target files for analysis
- graph build: Construct import and call graphs
- cfg: Extract control flow graphs for complexity

STAGE 3 - HEAVY ANALYSIS (3 Parallel Tracks):
- Track A: Taint analysis (isolated for memory)
- Track B: Static analysis (lint, patterns, graph analyze)
- Track C: Network I/O (deps, docs - skip with --offline)

STAGE 4 - AGGREGATION (Sequential):
- fce: Correlate findings across all tools
- report: Generate final output files

COMMAND OPTIONS:
    aud full                       # Complete analysis with network
    aud full --index               # Fast reindex only (Stage 1+2)
    aud full --offline             # No network operations (faster)
    aud full --quiet               # Minimal output for CI/CD
    aud full --wipecache           # Force fresh start (cache issues)

PERFORMANCE:
- Small project (<5K LOC): 2-3 minutes
- Medium project (20K LOC): 5-10 minutes
- Large monorepo (100K+ LOC): 15-20 minutes
- Second run (cached): 5-10x faster

COMBINING WITH OTHER TOOLS:
- After aud full: Use aud query, aud explain, aud blueprint
- For incremental work: aud workset --diff HEAD~1 then specific commands
- For security focus: aud taint --severity critical after full

RELATED:
- Commands: aud full, aud workset, aud blueprint
- Topics: aud manual overview, aud manual database, aud manual exit-codes

COMMON MISTAKES:
- Running analysis commands before aud full: No database means no results
- Using aud full when aud full --index suffices: Wastes time on network ops
- Ignoring pipeline.log: Contains detailed error information for debugging
- Not using --offline in CI/CD: Network operations slow down pipelines
""",
    },
    "severity": {
        "title": "Severity Levels",
        "summary": "How TheAuditor classifies finding importance",
        "explanation": """
WHAT IT IS:
A 4-level classification (CRITICAL, HIGH, MEDIUM, LOW) that prioritizes
findings by exploitability and impact. Aligned with CVSS and CWE standards.

WHEN TO USE IT:
- Filtering command output to focus on urgent issues
- Understanding exit codes from commands
- Prioritizing which findings to fix first
- Setting CI/CD pipeline fail thresholds

HOW TO USE IT:

FILTERING BY SEVERITY:
    aud taint --severity critical      # Only critical findings
    aud taint --severity high          # High and critical
    aud detect-patterns --severity medium  # Medium and above
    aud boundaries --severity critical # Critical boundary violations

EXIT CODES:
Commands return severity-based exit codes for CI/CD integration:
- 0: Success (no findings, or only LOW/MEDIUM)
- 1: HIGH severity findings detected
- 2: CRITICAL severity findings detected

EXAMPLE - CI/CD Pipeline:
    aud full && aud taint --severity high || exit 1
    # Fails pipeline if HIGH or CRITICAL findings exist

SEVERITY LEVELS:

CRITICAL (Exit Code 2):
- Remote Code Execution (RCE)
- SQL Injection with user input
- Authentication bypass
- Hardcoded secrets in production code
- Command injection vulnerabilities

HIGH (Exit Code 1):
- Cross-Site Scripting (XSS)
- Path traversal attacks
- Weak cryptography (MD5, SHA1)
- Missing authentication on sensitive endpoints
- Insecure deserialization

MEDIUM (Exit Code 0):
- Missing input validation
- Information disclosure
- Weak password policies
- Missing security headers
- Resource exhaustion risks

LOW (Exit Code 0):
- Code complexity issues
- Missing error handling
- Deprecated function usage
- Performance problems
- Style violations

SEVERITY ESCALATION:
FCE (Factual Correlation Engine) can promote severity when findings combine:
- Low + Low = may become High (multiple small issues = larger problem)
- Medium + Medium = may become Critical (compound vulnerability)

Example: "Debug mode enabled" (low) + "Exposes database credentials" (medium)
         = CRITICAL (production secret exposure via debug endpoint)

COMBINING WITH OTHER TOOLS:
- Use --severity flag on any analysis command
- Check exit codes in scripts: $? or $LASTEXITCODE
- Use aud fce to see escalated severities from combined findings

COMMON MISTAKES:
- Ignoring MEDIUM findings: They often combine to CRITICAL via FCE
- Only checking exit codes: MEDIUM findings return 0 but still need review
- Not using --severity in CI/CD: Slower pipelines processing all findings

RELATED:
Commands: aud taint, aud detect-patterns, aud boundaries, aud fce
Topics: aud manual fce, aud manual patterns, aud manual taint
""",
    },
    "patterns": {
        "title": "Pattern Detection",
        "summary": "Security vulnerability patterns TheAuditor can detect",
        "explanation": """
WHAT IT IS:
Pattern detection finds security vulnerabilities by matching code against
known-bad patterns. Uses both fast regex (secrets, hardcoded values) and
accurate AST analysis (injection, misconfigurations).

WHEN TO USE IT:
- Quick security scan without full database build
- Finding hardcoded secrets before commit
- Detecting known vulnerability patterns (OWASP Top 10)
- After aud full, patterns are already run - use aud fce to see results

HOW TO USE IT:

PREREQUISITES:
    # None for standalone scan
    # OR after aud full, patterns are already in database

STEPS:
1. Run pattern detection:
    aud detect-patterns                    # Full scan with AST
    aud detect-patterns --no-ast           # Fast regex-only scan
    aud detect-patterns --patterns auth_issues  # Specific category

2. Review findings in terminal or use --json for detailed output

3. Use --file-filter for targeted scans:
    aud detect-patterns --file-filter "*.py"   # Python only
    aud detect-patterns --file-filter "src/*"  # Specific directory

EXAMPLE - Finding Hardcoded Secrets:
    aud detect-patterns --patterns auth_issues
    # Output shows hardcoded passwords, API keys, tokens
    # Each finding has file, line, severity, CWE reference

WHAT IT DETECTS:
- Hardcoded credentials: passwords, API keys, tokens in source
- Injection patterns: SQL, command, XSS, template injection
- Weak crypto: MD5, SHA1, insecure random
- Misconfigurations: debug mode, CORS issues, missing headers
- Code quality: empty catch, race conditions, resource leaks

COMBINING WITH OTHER TOOLS:
- After patterns: run aud fce to correlate with taint findings
- Use aud taint for data-flow based detection (complements patterns)
- Use aud rules --summary to see all available pattern categories
- Patterns run automatically in aud full pipeline

AGENT WORKFLOW:
The security agent uses patterns as Phase 3 (Pattern Analysis).
Results are read from database via aud blueprint --security.
No need to re-run detect-patterns after aud full.

KEY OPTIONS:
- --patterns: Specific category (auth_issues, db_issues, runtime_issues)
- --file-filter: Glob pattern to limit scope
- --no-ast: Regex-only mode (faster, less accurate)
- --with-frameworks: Include framework-specific patterns
- --exclude-self: Skip TheAuditor's own files

COMMON MISTAKES:
- Running detect-patterns after aud full: Duplicates work already done
- Using --no-ast for security audits: Misses semantic issues
- Ignoring CWE references: They link to detailed vulnerability info
- Not using --file-filter on large codebases: Slow and noisy

EXIT CODES:
- 0: Success (findings may still exist - check output)
- 1: Error during analysis

RELATED:
Commands: aud detect-patterns, aud rules --summary, aud fce
Topics: aud manual rules, aud manual severity, aud manual taint
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
|-- repo_index.db      # Immutable facts (database)
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
WHAT IT IS:
TheAuditor is an offline-first, AI-centric static analysis platform. It extracts
ground truth from codebases: symbols, calls, data flows, security patterns. All
data goes into queryable SQLite databases for immediate, offline access.

WHEN TO USE IT:
- Security auditing: Find vulnerabilities before deployment
- Code review: Analyze PRs for risk and blast radius
- Refactoring: Detect broken imports, dead code, inconsistencies
- Architecture: Map dependencies, find hotspots, trace data flow
- AI augmentation: Give AI assistants factual codebase knowledge

HOW TO USE IT:

PREREQUISITES:
    Python 3.11+ (no external dependencies for core analysis)

STEPS:
    1. Run initial analysis:
       aud full                        # Creates .pf/ directory with all data

    2. Query the results:
       aud blueprint --structure       # Architecture overview
       aud query --symbol main         # Find symbol definitions
       aud taint                       # Security vulnerability report

    3. Get detailed explanations:
       aud manual <topic>              # Learn any concept

EXAMPLE - Complete Workflow:
    aud full                           # Index and analyze
    aud blueprint                      # See what was found
    aud taint --severity high          # Focus on critical issues
    aud query --symbol validate        # Investigate specific code

KEY CONCEPTS:

DATABASE-FIRST:
    All analysis stores results in SQLite databases:
    - .pf/repo_index.db: Symbols, calls, assignments, imports
    - .pf/graphs.db: Import and call graphs

POLYGLOT:
    Supports Python, JavaScript/TypeScript, Go, Rust, Bash.
    Single database schema across all languages.

OFFLINE-FIRST:
    No network required for core analysis.
    Use aud full --offline for air-gapped environments.

PHILOSOPHY:
TheAuditor reports FACTS, not interpretations:
- "Function X calls function Y" - FACT
- "Function X is dangerous" - INTERPRETATION (your job to decide)

OUTPUT STRUCTURE:
    .pf/
    |-- repo_index.db           # All code symbols and relationships
    |-- graphs.db               # Call and import graphs
    +-- pipeline.log            # Execution trace

COMBINING WITH OTHER TOOLS:
- AI assistants: Query database for accurate context
- CI/CD: Run aud full --quiet --offline for fast gates
- IDE: Use aud explain for context bundles

RELATED:
- Commands: aud full, aud blueprint, aud query, aud explain
- Topics: aud manual pipeline, aud manual database, aud manual workflows

COMMON MISTAKES:
- Skipping aud full: No database means all queries fail
- Not reading pipeline.log: Contains detailed error info
- Using network in CI: aud full --offline is faster and more reliable
""",
    },
    "gitflows": {
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

REFACTOR WORKFLOW (Pattern Discovery -> YAML -> Fix):
Step 1: Discover architecture before planning
    aud blueprint --structure        # Understand codebase layout
    aud blueprint --boundaries       # Find security entry points
    aud blueprint --taint            # See data flow summary
    aud deadcode                     # Find zombie/unused code
    aud fce                          # Prioritize by vector convergence

Step 2: Discover patterns before writing YAML
    aud query --list-symbols --filter "*product*"  # Find what exists
    aud query --pattern "%variant%"                # SQL LIKE search
    aud manual refactor                            # Read YAML schema

Step 3: Write and validate YAML profile
    # Create profile.yaml based on FOUND patterns
    aud refactor --file profile.yaml --validate-only  # Check syntax

Step 4: Run analysis and query results
    aud refactor --file profile.yaml   # Find violations
    aud refactor --query-last          # Query last run results

Step 5: Fix in dependency order
    aud graph analyze                  # Understand dependencies
    aud impact --file target.tsx       # Check blast radius before fix
    # Make fixes, then re-run:
    aud full --index                   # Re-index after changes
    aud refactor --file profile.yaml   # Verify 0 violations

PLANNING WORKFLOW (For Complex Refactors):
    aud planning init --name "Migrate ProductVariants"
    aud planning add-task --name "Fix Sale.tsx" --spec profile.yaml
    # ... make fixes ...
    aud planning verify-task 1 1       # Verify task passes spec
    aud planning archive 1             # Mark plan complete

AI INTEGRATION WORKFLOW:
    aud blueprint --structure --format json  # Feed to AI for context
    aud query --file X --format json         # Get file details as JSON
    aud explain <file>                       # Get AI-friendly explanation
""",
    },
    "exit-codes": {
        "title": "Exit Codes",
        "summary": "What TheAuditor's exit codes mean",
        "explanation": """
WHAT IT IS:
TheAuditor uses standardized exit codes to communicate analysis results to
CI/CD systems and scripts. These codes tell you what was found without
parsing output text.

WHEN TO USE IT:
- CI/CD pipelines: Gate deployments based on severity
- Scripts: Automate responses to different finding levels
- Pre-commit hooks: Block commits with critical issues
- Monitoring: Track security trends over time

HOW TO USE IT:

PREREQUISITES:
    None - exit codes work automatically

EXIT CODE MEANINGS:
    0: Success - No critical or high severity issues found
    1: High severity - Findings need attention before deployment
    2: Critical - Security vulnerabilities that must be fixed immediately
    3: Error - Analysis incomplete or pipeline failed

STEPS:
    1. Run analysis and capture exit code:
       aud full --quiet
       EXIT_CODE=$?

    2. Respond based on severity:
       if [ $EXIT_CODE -eq 0 ]; then
           echo "All clear"
       elif [ $EXIT_CODE -eq 1 ]; then
           echo "High severity issues found"
       elif [ $EXIT_CODE -eq 2 ]; then
           echo "CRITICAL vulnerabilities - blocking"
           exit 1
       fi

EXAMPLE - GitHub Actions:
    - name: Security Audit
      run: |
        aud full --quiet --offline
        if [ $? -eq 2 ]; then
          echo "Critical vulnerabilities found"
          exit 1
        fi

EXAMPLE - Block on Any Finding:
    aud full --quiet || exit $?

EXAMPLE - Warn on High, Block on Critical:
    aud full --quiet
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 2 ]; then
        exit 1
    elif [ $EXIT_CODE -eq 1 ]; then
        echo "::warning::High severity issues found"
    fi

COMBINING WITH OTHER TOOLS:
- Use with --quiet for minimal output in pipelines
- Use with --offline to skip network operations
- Query findings with: aud query --findings

RELATED:
- Commands: aud full, aud taint, aud detect-patterns
- Topics: aud manual pipeline, aud manual severity

COMMON MISTAKES:
- Checking exit code after piping: Use PIPESTATUS or separate commands
- Ignoring exit code 3: Pipeline errors should be investigated
- Not using --quiet: Verbose output can break CI log parsing
""",
    },
    "env-vars": {
        "title": "Environment Variables",
        "summary": "Configuration options via environment variables",
        "explanation": """
WHAT IT IS:
TheAuditor reads environment variables to adjust limits, timeouts, and
performance settings. These override defaults without modifying config files.

WHEN TO USE IT:
- Large codebases timing out during analysis
- Files being skipped due to size limits
- CI/CD environments with specific constraints
- Performance tuning for different hardware

HOW TO USE IT:

PREREQUISITES:
    Set variables before running aud commands

STEPS:
    1. Export the variable:
       export THEAUDITOR_TIMEOUT_SECONDS=3600

    2. Run the command:
       aud full

    3. Or combine in one line:
       THEAUDITOR_TIMEOUT_SECONDS=3600 aud full

AVAILABLE VARIABLES:

FILE SIZE LIMITS:
- THEAUDITOR_LIMITS_MAX_FILE_SIZE: Max file size in bytes (default: 2097152 = 2MB)
- THEAUDITOR_LIMITS_MAX_CHUNK_SIZE: Max chunk for processing (default: 65536 = 64KB)

TIMEOUTS:
- THEAUDITOR_TIMEOUT_SECONDS: Overall analysis timeout (default: 1800 = 30 min)
- THEAUDITOR_TIMEOUT_TAINT_SECONDS: Taint analysis timeout (default: 600 = 10 min)
- THEAUDITOR_TIMEOUT_LINT_SECONDS: Linting timeout (default: 300 = 5 min)

PERFORMANCE:
- THEAUDITOR_DB_BATCH_SIZE: Database batch insert size (default: 200)

EXAMPLE - Large Codebase (100K+ LOC):
    export THEAUDITOR_TIMEOUT_SECONDS=3600      # 1 hour
    export THEAUDITOR_TIMEOUT_TAINT_SECONDS=1200 # 20 min for taint
    export THEAUDITOR_DB_BATCH_SIZE=500          # Larger batches for SSD
    aud full

EXAMPLE - Big Files (>2MB):
    export THEAUDITOR_LIMITS_MAX_FILE_SIZE=10485760  # 10MB
    aud full

EXAMPLE - CI/CD with Tight Timeouts:
    export THEAUDITOR_TIMEOUT_SECONDS=300  # 5 min max
    aud full --offline --quiet || true     # Don't fail pipeline on timeout

COMBINING WITH OTHER TOOLS:
- Set in shell profile for persistent configuration
- Use in CI/CD environment blocks
- Combine with --offline for predictable timing

RELATED:
- Commands: aud full
- Topics: aud manual pipeline, aud manual troubleshooting

COMMON MISTAKES:
- Setting bytes as MB: THEAUDITOR_LIMITS_MAX_FILE_SIZE is bytes, not MB
- Forgetting export: Variable must be exported for child processes
- Timeout too short: Large codebases need 30+ minutes
""",
    },
    "database": {
        "title": "Database Schema Reference",
        "summary": "Tables, indexes, and manual SQL queries for repo_index.db",
        "explanation": """
WHAT IT IS:
TheAuditor stores all analysis data in SQLite databases. These are the ground
truth for every query, command, and report. You can query them directly for
custom analysis beyond what built-in commands provide.

WHEN TO USE IT:
- Custom queries not covered by aud query or aud explain
- Bulk data export for external tools
- Debugging why a command returns unexpected results
- Building custom reports or integrations
- Understanding what data TheAuditor extracts

HOW TO USE IT:

PREREQUISITES:
    Run aud full first to create the databases

STEPS:
    1. Connect to the database using Python:
       import sqlite3
       conn = sqlite3.connect('.pf/repo_index.db')
       cursor = conn.cursor()

    2. Query the data:
       cursor.execute('SELECT name, file, line FROM symbols WHERE type = ?', ('function',))
       for row in cursor.fetchall():
           print(row)

    3. Close the connection:
       conn.close()

EXAMPLE - Find All Callers of a Function:
    import sqlite3
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT caller_function, file, line
        FROM function_call_args
        WHERE callee_function = 'authenticate'
    ''')
    for caller, file, line in cursor.fetchall():
        print(f'{file}:{line} - {caller}')
    conn.close()

DATABASE LOCATIONS:
- .pf/repo_index.db: Main code index (symbols, calls, imports, 200k+ rows)
- .pf/graphs.db: Import and call graphs (for aud graph commands)

KEY TABLES:

SYMBOLS TABLE:
- Purpose: All function, class, variable definitions
- Columns: name, type, file, line, end_line, scope
- Index: name for fast lookups

FUNCTION_CALL_ARGS TABLE:
- Purpose: Every function call with arguments
- Columns: caller_function, callee_function, file, line, arguments
- Index: callee_function for caller lookup

ASSIGNMENTS TABLE:
- Purpose: Variable assignments for data flow
- Columns: target_var, source_expr, file, line, in_function

IMPORTS TABLE:
- Purpose: Import statements for dependency tracking
- Columns: file, module_name, style, line

API_ENDPOINTS TABLE:
- Purpose: REST API routes
- Columns: method, path, handler_function, file, line

USEFUL QUERIES:

Find functions in a file:
    cursor.execute('''
        SELECT name, line FROM symbols
        WHERE file LIKE '%auth.py%' AND type = 'function'
        ORDER BY line
    ''')

Find all API endpoints:
    cursor.execute('''
        SELECT method, path, handler_function, file
        FROM api_endpoints ORDER BY path
    ''')

Count symbols by type:
    cursor.execute('''
        SELECT type, COUNT(*) FROM symbols GROUP BY type
    ''')

COMBINING WITH OTHER TOOLS:
- Use aud query for common lookups (faster than manual SQL)
- Use aud explain for comprehensive context bundles
- Manual queries for custom analysis not covered by commands

RELATED:
- Commands: aud query, aud explain, aud blueprint
- Topics: aud manual overview, aud manual pipeline

COMMON MISTAKES:
- Using sqlite3 command line: NOT installed on Windows, use Python sqlite3 module
- Querying before aud full: Database does not exist yet
- Not closing connections: Can cause database locks
- Hardcoding row counts: Numbers vary by codebase size
""",
    },
    "troubleshooting": {
        "title": "Troubleshooting Guide",
        "summary": "Common errors and solutions for TheAuditor",
        "explanation": """
WHAT IT IS:
A reference for diagnosing and fixing common TheAuditor issues. Each problem
includes the error message or symptom, cause, and specific fix.

WHEN TO USE IT:
- Commands failing with error messages
- Getting unexpected empty results
- Performance problems (slow or hanging)
- Output formatting issues

HOW TO USE IT:

PREREQUISITES:
    None - use this when things go wrong

STEPS:
    1. Identify the error message or symptom
    2. Find the matching section below
    3. Apply the fix
    4. If problem persists, check pipeline.log for details

ERROR REFERENCE:

ERROR: "No .pf directory found"
- CAUSE: Database not created yet
- FIX: Run aud full to create .pf/ directory
- VERIFY: ls .pf/ shows repo_index.db

ERROR: "Graph database not found"
- CAUSE: graphs.db not built
- FIX: Run aud graph build (or aud full which includes it)
- VERIFY: ls .pf/ shows graphs.db

ERROR: "Symbol not found"
- CAUSE 1: Typo (names are case-sensitive)
- FIX: Run aud query --symbol partial_name to find exact spelling
- CAUSE 2: Database stale (code changed)
- FIX: Run aud full --index to rebuild
- CAUSE 3: Method needs class prefix
- FIX: Use ClassName.methodName format

SYMPTOM REFERENCE:

SYMPTOM: Empty results but code exists
- CHECK: aud query --file <file> --list all to verify indexing
- FIX: If empty, run aud full --index
- NOTE: Dynamic calls (obj[var]()) cannot be statically resolved

SYMPTOM: Slow queries (>50ms)
- CAUSE: High --depth value traversing too many nodes
- FIX: Reduce --depth to 1-2
- NOTE: depth=5 can traverse 10000+ nodes

SYMPTOM: Command hangs
- CAUSE: Large file or complex analysis
- FIX: Set THEAUDITOR_TIMEOUT_SECONDS=600
- DEBUG: Check .pf/pipeline.log for progress

SYMPTOM: Unicode/encoding errors on Windows
- CAUSE: CP1252 encoding cannot handle emojis
- FIX: TheAuditor uses ASCII-only output
- REPORT: If you see encoding errors, this is a bug

SYMPTOM: Cache corruption
- CAUSE: Interrupted analysis, disk issues
- FIX: aud full --wipecache for fresh start

GETTING HELP:
    aud manual <topic>       # Learn about specific concepts
    aud manual --list        # See all available topics
    aud <command> --help     # Command-specific help
    .pf/pipeline.log         # Detailed execution trace

COMBINING WITH OTHER TOOLS:
- Use aud manual database to understand schema
- Use aud blueprint --structure to verify indexing
- Query findings with: aud query --findings

RELATED:
- Commands: aud full, aud query, aud explain
- Topics: aud manual pipeline, aud manual database, aud manual env-vars

COMMON MISTAKES:
- Not running aud full first: Most errors stem from missing database
- Ignoring pipeline.log: Contains detailed error information
- Case sensitivity: Symbol names must match exactly
- Stale database: Re-index after code changes
""",
    },
    "rust": {
        "title": "Rust Language Support",
        "summary": "Rust-specific analysis including modules, impl blocks, traits, and unsafe code",
        "explanation": """
TheAuditor provides comprehensive Rust support with 20 dedicated tables for
extracting and analyzing Rust codebases. This includes module resolution,
trait implementations, unsafe code detection, and lifetime analysis.

WHEN TO USE IT:
- Analyzing Rust projects for security vulnerabilities
- Auditing unsafe code blocks for potential memory safety issues
- Understanding module structure and trait implementations
- Tracing data flow through Rust functions

PREREQUISITES:
- Run 'aud full' first to index Rust files
- Rust source files must have .rs extension
- Cargo.toml for dependency analysis

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

COMBINING WITH OTHER TOOLS:
  Rust + Taint Analysis:
    aud full                              # Index all including Rust
    aud taint --verbose                   # Trace tainted data through Rust

  Rust + Dependency Analysis:
    aud deps --check-latest               # Check Cargo.toml for updates
    aud deps --vuln-scan                  # Scan Rust crates for CVEs

  Rust + Graph Analysis:
    aud graph build                       # Build call graph with Rust
    aud graph analyze                     # Find cycles including Rust modules

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
    aud full                      # Index Rust files (*.rs)
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

COMMON MISTAKES:
- Querying before running 'aud full' (tables will be empty)
- Using 'aud full --index' instead of 'aud full' (both work, but full is standard)
- Expecting taint to track through raw pointer derefs (unsafe blocks are opaque)
- Not checking rust_unsafe_blocks for security-critical code

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
WHAT IT IS:
A call graph maps which functions call which other functions at function-level
granularity. Unlike the import graph (file-level), call graphs enable precise
execution path analysis for taint tracking and security auditing.

WHEN TO USE IT:
- Taint analysis: Track user input through function calls to sinks
- Dead code: Functions with no incoming edges may be unused
- Impact analysis: Find all callers before changing a function
- Security audit: Find all paths to dangerous functions (exec, query, etc.)
- Understanding: See the execution flow of the codebase

HOW TO USE IT:

PREREQUISITES:
    aud full                                  # Build the database first
    aud graph build                           # Build the call graph

STEPS:
1. Build the call graph:
    aud graph build                           # Full codebase
    aud graph build --langs python            # Python only

2. Query who calls a function:
    aud graph query --uses authenticate_user  # Who calls this?

3. Query what a function calls:
    aud graph query --calls process_payment   # What does it call?

4. Visualize the call graph:
    aud graph viz --graph-type call           # Full call graph
    aud graph viz --view hotspots --graph-type call  # Most connected

CALL GRAPH STRUCTURE:
- Nodes: Functions and methods (file, line, name, type)
- Edges: Call relationships (caller to callee with call site)
- Methods stored as: ClassName.methodName

STATIC VS DYNAMIC:
Static calls (tracked): foo(), obj.method(), Class.static_method()
Dynamic calls (NOT tracked): obj[var](), getattr(obj, name)(), eval()

TheAuditor only tracks static calls resolvable from source code.

EXAMPLE WORKFLOW - Security Audit:
    aud full                                  # Index codebase
    aud graph build                           # Build call graph
    aud graph query --uses db_execute         # Who calls db_execute?
    aud taint --sink db_execute               # Find taint paths to sink

DATABASE ACCESS:
Call graph is stored in .pf/graphs.db with graph_type='call':
- nodes table: Functions with id, file, type, graph_type
- edges table: Call relationships with source, target, file, line

Query with Python sqlite3 (per CLAUDE.md - no sqlite3 CLI):
    .venv/Scripts/python.exe -c "import sqlite3; ..."

COMBINING WITH OTHER TOOLS:
- With taint: Call graph powers taint path tracing
- With impact: Impact analysis uses caller/callee relationships
- With deadcode: Identify functions with no callers
- With graph viz: Visualize complex call chains

AGENT WORKFLOW:
The dataflow agent (/theauditor:dataflow) uses call graph queries in Phase 4
to build complete source-to-sink chains:
    aud graph query --uses <source>           # Find callers
    aud graph query --calls <sink>            # Find callees

COMMON MISTAKES:
- Querying before aud graph build: No call graph data exists
- Expecting dynamic calls: Only static calls are tracked
- Confusing with import graph: Call graph is function-level, not file-level

RELATED:
Commands: aud graph build, aud graph query, aud graph viz, aud taint
Topics: aud manual graph, aud manual dependencies, aud manual taint
""",
    },
    "dependencies": {
        "title": "Dependency Analysis",
        "summary": "Package dependencies, version checking, and vulnerability scanning",
        "explanation": """
WHAT IT IS:
Package dependency analysis tracks third-party libraries your project depends
on (npm, pip, cargo, etc.), checks for updates, and scans for vulnerabilities.
This is distinct from the import/call graphs which track YOUR code relationships.

WHEN TO USE IT:
- Security audit: Scan for known vulnerabilities in dependencies
- Maintenance: Find outdated packages that need updating
- Supply chain: Understand transitive dependency exposure
- Onboarding: Get inventory of external libraries in use
- CI/CD: Gate deployments on vulnerability scans

HOW TO USE IT:

PREREQUISITES:
    aud full                                  # Build the database first

STEPS:
1. List all dependencies:
    aud deps                                  # Full inventory

2. Check for outdated packages:
    aud deps --check-latest                   # Compare to latest versions

3. Scan for vulnerabilities:
    aud deps --vuln-scan                      # Security scan (npm audit + OSV)

4. View dependency summary in architecture context:
    aud blueprint --deps                      # Architecture view

SUPPORTED MANIFEST FILES:
- Python: requirements.txt, pyproject.toml, setup.py
- JavaScript/TypeScript: package.json, package-lock.json, yarn.lock
- Rust: Cargo.toml, Cargo.lock
- Go: go.mod, go.sum

DEPENDENCY LEVELS (THREE TYPES):
1. Package deps (this topic): External libraries from manifest files
2. Import graph: YOUR files importing each other (aud graph build)
3. Call graph: YOUR functions calling each other (aud graph build)

EXAMPLE WORKFLOW - Security Audit:
    aud full                                  # Index codebase
    aud deps --vuln-scan                      # Find vulnerabilities
    aud blueprint --deps                      # See dependency landscape

COMBINING WITH OTHER TOOLS:
- With blueprint: aud blueprint --deps shows dependency summary
- With graph: Import graph shows internal dependencies, deps shows external
- For security: Combine deps vuln-scan with taint analysis for full picture

SECURITY IMPLICATIONS:
- Direct deps: Libraries you explicitly install (your responsibility)
- Transitive deps: Dependencies of dependencies (often 10x more, supply chain risk)
- CVE exposure: Known vulnerabilities in specific versions
- Exit code 2: Returned when critical vulnerabilities found (useful for CI)

COMMON MISTAKES:
- Confusing deps with graph: deps = external packages, graph = your code
- Not running aud full first: Dependency parsing happens during indexing
- Ignoring transitive deps: Most vulnerabilities are in indirect dependencies

RELATED:
Commands: aud deps, aud blueprint --deps, aud graph build
Topics: aud manual graph, aud manual callgraph, aud manual blueprint
""",
    },
    "graph": {
        "title": "Dependency and Call Graph Analysis",
        "summary": "Build and analyze import/call graphs for architecture understanding",
        "explanation": """
WHAT IT IS:
Graph analysis builds and analyzes import graphs (file-level) and call graphs
(function-level) to understand architecture, detect circular dependencies,
find hotspots, and measure change impact.

WHEN TO USE IT:
- Architecture understanding: Map how files and functions relate
- Circular dependency detection: Find import cycles breaking modularity
- Hotspot identification: Find highly-coupled modules needing refactoring
- Change impact: Understand blast radius before making changes
- Visualization: Generate architecture diagrams for documentation

HOW TO USE IT:

PREREQUISITES:
    aud full                                  # Builds database AND graphs

NOTE: 'aud full' already runs 'aud graph build' internally. After 'aud full',
the graph is ready - jump straight to analyze/query/viz.

STEPS:
1. Analyze for issues:
    aud graph analyze                         # Find cycles, hotspots

2. Query relationships:
    aud graph query --uses auth.py            # Who imports auth.py?
    aud graph query --calls send_email        # What does send_email call?

3. Visualize the architecture:
    aud graph viz --view full                 # Complete graph
    aud graph viz --view cycles               # Only circular dependencies
    aud graph viz --view hotspots             # Top connected nodes
    aud graph viz --view impact --impact-target src/auth.py  # Impact radius

REBUILD GRAPH ONLY (optional - rarely needed):
    aud graph build                           # Rebuild without full re-index
    aud graph build --langs python            # Rebuild for specific language

TWO GRAPH TYPES:
- Import Graph (file-level): Files as nodes, imports as edges
- Call Graph (function-level): Functions as nodes, calls as edges

WHAT GRAPHS REVEAL:
- Circular dependencies: A imports B, B imports C, C imports A (breaks modularity)
- Hotspots: Modules with >20 deps (high coupling, refactor candidates)
- Hidden coupling: A->B->C creates coupling even without direct import

EXAMPLE WORKFLOW - Architecture Review:
    aud full                                  # Index codebase + build graphs
    aud graph analyze                         # Find cycles, hotspots
    aud graph viz --view cycles --format svg  # Visualize cycles
    aud graph viz --view hotspots --top-hotspots 10  # Top 10 hotspots

DATABASE STRUCTURE:
Graphs stored in .pf/graphs.db (separate from repo_index.db):
- nodes: id, file, lang, type, graph_type ('import'|'call'|'data_flow')
- edges: source, target, type, file, line, graph_type
- analysis_results: Cycle and hotspot analysis results

COMBINING WITH OTHER TOOLS:
- With impact: aud impact uses graph data for blast radius
- With blueprint: aud blueprint --graph shows graph summary
- With taint: Data flow graph enables taint path tracing
- With deadcode: Graph helps find unreferenced nodes

AGENT WORKFLOW:
The dataflow agent (/theauditor:dataflow) uses graph queries in Phase 4:
    aud graph query --uses <source>           # Find who imports
    aud graph query --calls <function>        # Find call relationships

COMMON MISTAKES:
- Running graph commands before aud full: No source data to build from
- Running viz before analyze: No cycle/hotspot data to visualize
- Forgetting --format svg: DOT files need Graphviz or online viewer

RELATED:
Commands: aud graph build, aud graph analyze, aud graph query, aud graph viz
Topics: aud manual callgraph, aud manual impact, aud manual architecture
""",
    },
    "architecture": {
        "title": "System Architecture",
        "summary": "How TheAuditor's analysis pipeline and query engine work",
        "explanation": """
WHAT IT IS:
This topic explains TheAuditor's internal architecture: how code is parsed,
indexed, and queried. Understanding this helps you use the tool effectively
and troubleshoot when things go wrong.

WHEN TO USE THIS:
- Troubleshooting: Understanding why queries return unexpected results
- Performance: Knowing how indexing and queries work
- Custom queries: Writing direct SQL against the database
- Contributing: Understanding the codebase structure

EXTRACTION PIPELINE:
Source Code -> tree-sitter (AST) -> Language Extractors -> Database Manager -> repo_index.db

The pipeline parses code with tree-sitter, extracts facts (symbols, calls,
imports), and stores them in SQLite for fast querying.

TWO-DATABASE DESIGN:
- repo_index.db: Raw extracted facts from AST parsing
  - Regenerated on every 'aud full'
  - Used by: rules, taint, FCE, context queries
- graphs.db: Pre-computed graph structures
  - Built from repo_index.db via 'aud graph build'
  - Used by: 'aud graph' commands only

KEY PRINCIPLE:
Database is REGENERATED on every 'aud full' (no migrations).
Code changes -> re-run 'aud full' -> database updated.
Database is the TRUTH SOURCE for all queries.

QUERY ENGINE:
CLI -> CodeQueryEngine -> Direct SQL SELECT -> SQLite -> Formatters -> Output

No ORM overhead. Direct indexed lookups for <10ms query times.

PERFORMANCE:
- Query time: <10ms (indexed lookups)
- Database size: 20-50MB typical project
- Memory usage: <50MB for query engine

HOW TO INSPECT:
    aud blueprint --structure                 # See what's indexed
    aud query --file src/auth.py --list all   # Query specific file

COMBINING WITH OTHER TOOLS:
- aud blueprint shows high-level architecture summary
- aud query provides direct database access
- aud explain combines multiple queries for context

AGENT WORKFLOW:
The planning agent (/theauditor:planning) relies on this architecture:
- Phase 1: Run aud blueprint --structure (database query)
- Phase 2: Run aud query commands (direct SQL)
- All recommendations cite database evidence

COMMON MISTAKES:
- Expecting incremental updates: Database is fully regenerated each time
- Querying stale database: Re-run aud full after code changes
- Confusing the two databases: repo_index.db vs graphs.db

RELATED:
Commands: aud full, aud blueprint, aud query, aud explain
Topics: aud manual pipeline, aud manual database, aud manual blueprint
""",
    },
}
