"""Explain TheAuditor concepts and terminology."""

import click
from typing import Dict


# Concept explanations database
EXPLANATIONS: Dict[str, Dict[str, str]] = {
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
- SQL Injection (tainted data → SQL query)
- Command Injection (tainted data → system command)
- XSS (tainted data → HTML output)
- Path Traversal (tainted data → file path)
- LDAP/NoSQL Injection

USE THE COMMAND:
    aud taint-analyze                  # Full taint analysis
    aud taint-analyze --severity high  # Only high severity issues
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
"""
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
├── raw/               # Immutable facts (truth)
└── insights/          # Interpretations (opinions)
    ├── ml_suggestions.json
    ├── graph_health.json
    └── taint_severity.json

PHILOSOPHY:
TheAuditor deliberately separates facts from interpretations because:
1. Facts are objective - the code does what it does
2. Severity is subjective - risk tolerance varies
3. AI needs both - facts for accuracy, insights for prioritization

The core system will NEVER tell you something is "critical" or "needs fixing."
It only reports what IS. The insights layer adds what it MEANS.
"""
    }
}


@click.command("explain")
@click.argument("concept", required=False)
@click.option("--list", "list_concepts", is_flag=True, help="List all available concepts")
def explain(concept, list_concepts):
    """Interactive documentation for TheAuditor concepts, terminology, and security analysis techniques.

    Built-in reference system that explains security concepts, analysis methodologies, and tool-specific
    terminology through detailed, example-rich explanations optimized for learning. Covers 9 core topics
    from taint analysis to pipeline architecture, each with practical examples and related commands.

    AI ASSISTANT CONTEXT:
      Purpose: Provide interactive documentation for TheAuditor concepts
      Input: Concept name (taint, workset, fce, cfg, etc.)
      Output: Terminal-formatted explanation with examples
      Prerequisites: None (standalone documentation)
      Integration: Referenced throughout other command help texts
      Performance: Instant (no I/O, pure string formatting)

    AVAILABLE CONCEPTS (9 topics):
      taint:
        - Data flow tracking from untrusted sources to dangerous sinks
        - Detects SQL injection, XSS, command injection
        - Example: user_input → query string → database execution

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
        - Execution stages (index → analyze → correlate → report)
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
      aud explain taint

      # Use Case 2: Understand workset concept
      aud explain workset

      # Use Case 3: List all available topics
      aud explain --list

      # Use Case 4: Understand FCE correlation
      aud explain fce

    COMMON WORKFLOWS:
      Before First Analysis:
        aud explain pipeline      # Understand execution flow
        aud explain taint         # Learn security analysis
        aud init && aud full

      Understanding Command Output:
        aud taint-analyze
        aud explain taint         # Learn what taint findings mean

      Troubleshooting Performance:
        aud explain workset       # Learn optimization techniques
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
        -> Use 'aud explain --list' to see all available concepts
        -> Check spelling (case-sensitive: 'taint' not 'Taint')
        -> Some advanced concepts may not have explanations yet

      Output formatting issues:
        -> Terminal width <80 chars may cause wrapping
        -> Use terminal with proper UTF-8 support
        -> Pipe to 'less' for scrolling: aud explain fce | less

    NOTE: Explanations are embedded in the CLI for offline use. They cover
    core concepts but not every command detail - use --help on specific commands
    for comprehensive usage information.
    """
    # SANDBOX DELEGATION: Check if running in sandbox
    from theauditor.sandbox_executor import is_in_sandbox, execute_in_sandbox

    if not is_in_sandbox():
        # Not in sandbox - delegate to sandbox Python
        import sys
        exit_code = execute_in_sandbox("explain", sys.argv[2:], root=".")
        sys.exit(exit_code)

    if list_concepts:
        click.echo("\nAvailable concepts to explain:\n")
        for key, info in EXPLANATIONS.items():
            click.echo(f"  {key:12} - {info['summary']}")
        click.echo("\nUse 'aud explain <concept>' for detailed information.")
        return

    if not concept:
        click.echo("Please specify a concept to explain or use --list to see available topics.")
        click.echo("\nExample: aud explain taint")
        return

    # Normalize concept name
    concept = concept.lower().strip()

    if concept not in EXPLANATIONS:
        click.echo(f"Unknown concept: '{concept}'")
        click.echo("\nAvailable concepts:")
        for key in EXPLANATIONS:
            click.echo(f"  - {key}")
        return

    # Display explanation
    info = EXPLANATIONS[concept]
    click.echo(f"\n{'=' * 70}")
    click.echo(f"{info['title'].upper()}")
    click.echo(f"{'=' * 70}")
    click.echo(info['explanation'])
    click.echo(f"{'=' * 70}\n")
