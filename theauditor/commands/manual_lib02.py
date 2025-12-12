"""Manual library part 2: Advanced concepts (boundaries through session)."""

EXPLANATIONS_02: dict[str, dict[str, str]] = {
    "boundaries": {
        "title": "Security Boundary Analysis",
        "summary": "Measure distance from entry points to security controls",
        "explanation": """
WHAT IT IS:
Boundary analysis measures how far user input travels before security
controls are applied. Distance 0 = control at entry. Distance 3+ = late
validation, data already spread through multiple functions.

WHEN TO USE IT:
- Auditing input validation placement in API handlers
- Checking multi-tenant isolation (tenant_id filtering)
- Reviewing authentication/authorization control placement
- After aud full, to see boundary enforcement quality

HOW TO USE IT:

PREREQUISITES:
    aud full                               # Build database first

STEPS:
1. Run boundary analysis:
    aud boundaries                         # All boundary types
    aud boundaries --type input-validation # Focus on input validation
    aud boundaries --type multi-tenant     # Focus on tenant isolation

2. Interpret results - quality levels:
   - clear: Control at distance 0 (best)
   - acceptable: Control at distance 1-2
   - fuzzy: Multiple controls or distance 3+
   - missing: No control found (critical)

3. Investigate flagged entry points:
    aud explain <entry_file>               # Get context

EXAMPLE - Finding Late Validation:
    aud full && aud boundaries --severity critical
    # Output shows entry points with missing or late validation
    # Each finding shows: entry point, control function, distance

DISTANCE SEMANTICS:
- Distance 0: Control at entry (decorator or first line)
- Distance 1-2: Control nearby (acceptable)
- Distance 3+: Control far from entry (data spreads before enforcement)
- Distance None: No control found (security gap)

MULTI-TENANT USE CASE:
For SaaS apps, tenant isolation is critical:
    aud boundaries --type multi-tenant
Flags queries on tenant tables without tenant_id filter.

Example Violation (Distance 2 - too late):
    const doc = db.query('SELECT * FROM docs WHERE id=?', [id]);
    if (doc.tenant_id !== req.user.tenantId) return 403;  // After query!

Correct Pattern (Distance 0):
    const doc = db.query('SELECT * FROM docs WHERE id=? AND tenant_id=?',
                         [id, req.user.tenantId]);  // In query itself

COMBINING WITH OTHER TOOLS:
- Use with aud taint: boundaries = where controls are, taint = where data flows
- Use aud blueprint --boundaries for summary without re-running
- Use aud explain on flagged files for deeper context

AGENT WORKFLOW:
The security agent uses boundaries to verify control placement.
Query existing results with: aud blueprint --boundaries

BOUNDARY TYPES (What Each Type Analyzes):
Input Validation:
  Entry Points: python_routes, js_routes (HTTP endpoints)
  Control Patterns: validate(), parse(), check(), sanitize(), schema validators
  Violation: External data flows N functions before validation
  Example: req.body -> service.create() -> db.insert() -> validate() (distance 3)

Multi-Tenant Isolation (RLS):
  Entry Points: Database queries on tenant-sensitive tables
  Control Patterns: tenant_id in WHERE clause, SET LOCAL app.current_tenant_id
  Violation: Query on sensitive table without tenant filter
  Example: SELECT * FROM orders WHERE id=? (missing tenant_id filter)

Authorization:
  Entry Points: Protected routes, admin operations
  Control Patterns: @requires_auth, check_permission(), req.user validation
  Violation: Protected operation without auth check
  Example: DELETE /api/user/:id without permission check

Sanitization:
  Entry Points: User input to dangerous sinks (SQL, HTML, shell)
  Control Patterns: Parameterized queries, HTML escaping, input sanitization
  Violation: User input used in sink without sanitization
  Example: db.query(f"SELECT * FROM users WHERE name='{name}'")

JSON OUTPUT STRUCTURE (--format json):
    {
      "entry_point": "POST /api/users",
      "entry_file": "src/routes/users.js",
      "entry_line": 34,
      "controls": [{
        "control_function": "validateUser",
        "control_file": "src/validators/user.js",
        "control_line": 12,
        "distance": 2,
        "path": ["create_user", "processUser", "validateUser"]
      }],
      "quality": {
        "quality": "acceptable",
        "reason": "Single control point 'validateUser' at distance 2",
        "facts": [
          "Validation occurs 2 function call(s) after entry",
          "Data flows through 2 intermediate function(s) before validation"
        ]
      },
      "violations": []
    }

COMMON PATTERNS DETECTED:
Joi/Zod Triple Handler Problem:
  Observation: Multiple validation controls at distances 0, 1, 3
  Fact: 3 different validation points indicate distributed boundary
  Implication: Different code paths encounter different validation

Validation After Use:
  Observation: Validation at distance 3 (data flows through 3 functions first)
  Fact: Distance 3 creates 3 potential unvalidated code paths
  Implication: Data may spread to multiple locations before validation

User-Controlled Tenant ID:
  Observation: tenant_id sourced from req.query (user input)
  Fact: Tenant identifier originates from untrusted source
  Implication: User can access arbitrary tenant data

Missing Validation:
  Observation: Entry point accepts external data without validation control
  Fact: No validation control detected within search depth
  Implication: External data flows to downstream functions unvalidated

KEY OPTIONS:
- --type: input-validation, multi-tenant, authorization
- --format: report (human) or json (machine)
- --severity: Filter by severity level
- --max-entries: Limit entry points analyzed (performance)

COMMON MISTAKES:
- Running before aud full: No routes/endpoints indexed
- Ignoring "fuzzy" quality: Scattered validation = inconsistent security
- Not checking multi-tenant: Missing tenant filter = data leak
- Only checking input-validation: Auth boundaries matter too

EXIT CODES:
- 0: Success, no critical boundary violations
- 1: Critical boundary violations found

RELATED:
Commands: aud boundaries, aud taint, aud blueprint --boundaries
Topics: aud manual taint, aud manual patterns, aud manual severity
""",
    },
    "docker": {
        "title": "Docker Security Analysis",
        "summary": "Detect container misconfigurations, secrets, and vulnerable base images",
        "explanation": """
WHAT IT IS:
Docker security analysis examines Dockerfiles for privilege escalation risks,
exposed secrets, and vulnerable base images. It reads from the indexed database
(not live files) and applies security rules to detect common container mistakes.

WHEN TO USE IT:
- Before deploying new Docker images to production
- During PR review when Dockerfiles are modified
- As part of security audit after running aud full
- In CI/CD pipelines to block insecure images
- When investigating container escape vulnerabilities

HOW TO USE IT:

PREREQUISITES:
    aud full                              # Build database first (required)

STEPS:
1. Ensure Dockerfiles are indexed in the database:
   aud full                               # Extracts Dockerfile contents

2. Run Docker security analysis:
   aud docker-analyze                     # Full analysis
   aud docker-analyze --severity high     # Filter to high+ severity

3. Review findings in output:
   - Terminal shows summary by severity
   - Use --json for machine-readable output

4. For each finding, verify and remediate:
   - Check if finding is true positive
   - Apply fix (add USER, remove secrets, pin base image)

EXAMPLE - Pre-Deployment Security Check:
    aud full && aud docker-analyze --severity high --check-vulns

WHAT IT DETECTS:
- Privilege Issues: Missing USER instruction, SUDO usage, --cap-add
- Secret Exposure: Hardcoded API keys, passwords, private keys in ENV/ARG
- Base Image Problems: 'latest' tag, outdated versions, missing digest
- Hardening Failures: Missing HEALTHCHECK, exposed ports, chmod 777

SEVERITY MAPPING:
- CRITICAL: Hardcoded secrets, known CVEs in base image
- HIGH: Running as root, SUDO installation, capability escalations
- MEDIUM: Missing HEALTHCHECK, 'latest' tag, outdated base image
- LOW: Cache not cleared, suboptimal instruction ordering

COMBINING WITH OTHER TOOLS:
- After docker-analyze: Run aud detect-patterns for broader security scan
- For full audit: aud full includes docker analysis in pipeline
- With deps: aud deps --vuln-scan checks package vulnerabilities
- For IaC context: Combine with aud terraform or aud cdk

AGENT WORKFLOW:
When using the security agent (/theauditor:security), Docker analysis runs
as part of Phase 3 infrastructure checks. The agent queries existing findings
from the database rather than re-running analysis.

BEST PRACTICES (Dockerfile Structure):
    FROM node:20.10.0@sha256:abc123       # Pin with digest
    WORKDIR /app
    COPY package*.json ./
    RUN npm ci --only=production
    COPY . .
    USER node                             # Non-root user
    HEALTHCHECK CMD curl -f http://localhost:3000/health || exit 1
    CMD ["node", "server.js"]

RELATED:
Commands: aud docker-analyze, aud detect-patterns, aud deps --vuln-scan
Topics: aud manual patterns, aud manual severity, aud manual terraform

COMMON MISTAKES:
- Running before aud full: No database = no Dockerfile content to analyze
- Ignoring MEDIUM findings: Unpinned base images become CRITICAL when CVEs hit
- Not using --check-vulns: Without it, known CVEs in base images are not detected
- Expecting live file analysis: Reads from database, re-run aud full after changes

EXIT CODES:
- 0: Success, no critical/high issues found
- 1: High severity findings detected
- 2: Critical security vulnerabilities found
- 3: Analysis incomplete (database missing)
""",
    },
    "lint": {
        "title": "Code Linting and Static Analysis",
        "summary": "Run and normalize output from multiple linters across languages",
        "explanation": """
WHAT IT IS:
The lint command orchestrates multiple industry-standard linters (ESLint, Ruff,
Mypy, etc.) and normalizes their output into a unified format. This enables
consistent code quality analysis across Python, JavaScript/TypeScript, Go,
and Docker regardless of the underlying tool's native format.

WHEN TO USE IT:
- Before committing: Catch errors early in development
- During CI/CD: Block merges with linter errors
- Code review: Check quality of changed files only
- Large codebases: Use --workset for 10-100x faster targeted linting
- New project setup: Verify linters are working correctly

HOW TO USE IT:
PREREQUISITES:
    aud full                              # Optional: enables --workset mode
    # Linters must be installed (auto-detected)

STEPS:
    1. For full codebase lint:
       aud lint                           # Lint everything

    2. For targeted lint (faster):
       aud workset --diff HEAD~1          # Identify changed files
       aud lint --workset                 # Lint only those files

    3. Review findings by severity:
       - error: Must fix (code won't work)
       - warning: Should fix (best practice)
       - info: Consider fixing (style)

EXAMPLE - PR Review Workflow:
    aud workset --diff main..HEAD         # What changed in PR?
    aud lint --workset                    # Lint only changed files
    # Shows: 3 errors, 12 warnings in 5 files
    # Action: Fix errors before merge

COMBINING WITH OTHER TOOLS:
- With workset: Use aud workset first for targeted linting
- With fce: Lint findings feed into FCE correlation
- In CI/CD: Chain with other checks (aud lint && aud taint)
- With detect-patterns: Lint catches syntax, patterns catch security

SUPPORTED LINTERS:
Python:
- ruff: Fast, comprehensive (recommended)
- mypy: Static type checking
- black: Code formatting (check mode)
- bandit: Security-focused

JavaScript/TypeScript:
- eslint: Industry standard
- prettier: Code formatting
- tsc: TypeScript type checking

Go:
- golangci-lint: Meta-linter
- go vet: Static analyzer

Docker:
- hadolint: Dockerfile linter

AUTO-DETECTION:
TheAuditor automatically finds installed linters:
1. Checks system PATH
2. Checks node_modules/.bin (for JS tools)
3. Checks .auditor_venv (sandbox installation)
Only runs linters that are actually installed.

COMMAND OPTIONS:
    aud lint                     # Lint entire codebase
    aud lint --workset           # Lint only workset files
    aud lint --print-plan        # Preview what would run
    aud lint --timeout 600       # Increase timeout (seconds)

NORMALIZED OUTPUT FORMAT:
All linters output to unified format:
  {
    "file": "src/auth.py",
    "line": 42,
    "severity": "error",
    "rule": "undefined-var",
    "message": "Variable 'user' is not defined",
    "tool": "ruff"
  }

RELATED:
Commands: aud lint, aud workset, aud detect-patterns, aud fce
Topics: aud manual workset, aud manual patterns, aud manual fce

COMMON MISTAKES:
- Linting full codebase when only a few files changed: Very slow
  -> Use aud workset + aud lint --workset for 10-100x speedup
- Running lint without installed linters: Silent failure
  -> Use aud tools check to verify linters are installed
- Ignoring warnings: They often indicate real bugs
  -> Treat warnings seriously, especially type errors
- Not using in CI/CD: Code quality degrades over time
  -> Add aud lint || exit 1 to CI pipeline

OUTPUT:
- findings_consolidated table: All normalized findings (query with aud query --findings)
- Exit code 1: If errors found
""",
    },
    "frameworks": {
        "title": "Framework Detection",
        "summary": "Identify frameworks and libraries used in your project",
        "explanation": """
WHAT IT IS:
Framework detection identifies programming frameworks, libraries, and tools used
in your project by analyzing package manifests, import statements, config files,
and decorator patterns. This information enables framework-specific security rules
and architecture documentation.

WHEN TO USE IT:
- When first analyzing a new codebase to understand tech stack
- After running aud full to see detected frameworks
- Before security audit to enable framework-specific rules
- When documenting project architecture
- To identify framework-specific vulnerabilities

HOW TO USE IT:

PREREQUISITES:
    aud full                              # Build database first (required)

STEPS:
1. Index the codebase (detects frameworks automatically):
   aud full                               # Frameworks detected during indexing

2. View detected frameworks:
   aud detect-frameworks                  # Display in terminal
   aud detect-frameworks --json > ./stack.json  # Export to file

3. See frameworks in architecture context:
   aud blueprint --structure              # Shows frameworks with file organization

EXAMPLE - Tech Stack Documentation:
    aud full && aud detect-frameworks --json > ./tech_stack.json

DETECTION METHODS:
- Package Manifests: package.json, requirements.txt, pyproject.toml, Cargo.toml
- Import Statements: from flask import Flask, import React from 'react'
- Config Files: jest.config.js, pytest.ini, webpack.config.js, tsconfig.json
- Decorators: @app.route() (Flask), @pytest.fixture, @Component() (Angular)

SUPPORTED FRAMEWORKS:
- Web: Flask, Django, FastAPI, Express, Nest.js, React, Vue, Angular
- Database: SQLAlchemy, Prisma, TypeORM, psycopg2, pymongo
- Testing: pytest, Jest, Mocha, Jasmine
- Build: Webpack, Vite, setuptools, poetry
- Cloud: boto3, @aws-sdk/*, google-cloud-*

PRIMARY VS SECONDARY:
- Primary (is_primary=true): Core frameworks shaping architecture (Flask, React)
- Secondary (is_primary=false): Utility libraries (lodash, requests)

COMBINING WITH OTHER TOOLS:
- After detect-frameworks: Run aud deps --vuln-scan for framework CVEs
- For security: Framework detection enables framework-specific security rules
- With blueprint: aud blueprint --structure shows frameworks in architecture
- For docs: aud docs fetch uses detected frameworks for documentation priority

AGENT WORKFLOW:
Framework detection runs automatically during 'aud full'. The security agent
(/theauditor:security) uses detected frameworks to enable appropriate rules.
Query detected frameworks with:
    aud detect-frameworks

DATABASE TABLE:
    CREATE TABLE frameworks (
      name TEXT, version TEXT, language TEXT,
      path TEXT, source TEXT, is_primary INTEGER
    )

RELATED:
Commands: aud detect-frameworks, aud blueprint --structure, aud deps
Topics: aud manual deps, aud manual patterns, aud manual architecture

COMMON MISTAKES:
- Running detect-frameworks before aud full: No data to display
- Expecting real-time detection: Reads from database, re-run aud full if changed
- Missing transitive frameworks: Only detects explicitly declared dependencies
- Confusing with deps: frameworks shows what's used, deps shows vulnerabilities

EXIT CODES:
- 0: Success, frameworks detected or no frameworks found
- 1: Database not found (run 'aud full' first)
- 3: Database query failed
""",
    },
    "docs": {
        "title": "External Documentation Caching",
        "summary": "Fetch, cache, and summarize library documentation for AI context",
        "explanation": """
WHAT IT IS:
Documentation caching fetches README files and API docs from package registries,
caches them locally for offline use, and generates "documentation capsules" -
condensed JSON summaries optimized for LLM context windows (<10KB per package).

WHEN TO USE IT:
- After detecting dependencies to fetch their documentation
- Before offline/air-gapped security audits
- When AI assistants need library API context
- After adding new dependencies to refresh cache
- When generating documentation capsules for LLM consumption

HOW TO USE IT:

PREREQUISITES:
    aud deps                              # Detect dependencies first (required)

STEPS:
1. Detect project dependencies:
   aud deps                               # Creates .pf/deps.json

2. Fetch documentation from registries:
   aud docs fetch                         # Downloads from PyPI/npm/GitHub
   aud docs fetch --offline               # Use cache only (no network)

3. Generate AI-optimized capsules:
   aud docs summarize                     # Creates condensed JSON files

4. View cached documentation:
   aud docs view requests                 # View package docs
   aud docs list                          # See all cached packages

EXAMPLE - Full Documentation Setup:
    aud deps && aud docs fetch && aud docs summarize

CAPSULE FORMAT (AI-Optimized):
{
  "package": "requests",
  "version": "2.31.0",
  "summary": "HTTP library for Python",
  "key_apis": ["requests.get()", "requests.post()", "Response.json()"],
  "common_patterns": ["response = requests.get(url)"]
}

SECURITY CONSIDERATIONS:
Documentation is only fetched from allowlisted sources:
- GitHub (github.com)
- GitLab (gitlab.com)
- Official registries (pypi.org, npmjs.com)

The --allow-non-gh-readmes flag bypasses this (USE WITH CAUTION).

COMBINING WITH OTHER TOOLS:
- After deps: aud deps detects dependencies, aud docs fetch downloads docs
- With frameworks: Detected frameworks prioritize documentation fetching
- For offline: Cache enables air-gapped security audits
- With AI: Capsules provide context without reading full READMEs

AGENT WORKFLOW:
AI assistants use documentation capsules to understand library APIs without
making assumptions. The typical flow is:
    aud deps && aud docs fetch && aud docs summarize

OUTPUT FILES:
    .pf/deps.json                    # Dependency list (from aud deps)
    .pf/context/docs/<pkg>.md        # Raw README files
    .pf/context/doc_capsules/<pkg>.json  # AI-optimized summaries

RELATED:
Commands: aud docs fetch, aud docs summarize, aud docs view, aud docs list
Topics: aud manual deps, aud manual frameworks

COMMON MISTAKES:
- Running docs fetch before aud deps: No dependency list to fetch docs for
- Expecting real-time updates: Cached docs don't auto-update, re-run fetch
- Skipping summarize: Raw READMEs are large, capsules are optimized for AI
- Using --allow-non-gh-readmes carelessly: Security risk from untrusted sources

EXIT CODES:
- 0: Success, documentation fetched/summarized
- 1: Some packages failed (partial success)
- 2: Network error or all packages failed
- 3: No dependencies found (run 'aud deps' first)
""",
    },
    "rules": {
        "title": "Detection Rules and Patterns",
        "summary": "Security rules, vulnerability patterns, and code quality checks",
        "explanation": """
WHAT IT IS:
TheAuditor's detection system uses two layers: fast YAML regex patterns
(secrets, hardcoded values) and accurate Python AST rules (semantic
analysis of code structure). aud rules --summary shows all available rules.

WHEN TO USE IT:
- Documenting what security checks TheAuditor performs
- Verifying custom patterns are registered
- Understanding what categories of vulnerabilities are covered
- Before adding custom organization-specific patterns

HOW TO USE IT:

PREREQUISITES:
    # None - reads pattern files directly

STEPS:
1. Generate capability report:
    aud rules --summary

2. Review output at .pf/auditor_capabilities.md:
   - Lists all YAML patterns by category
   - Lists all Python AST rules (find_* functions)
   - Shows severity distribution

3. Verify custom patterns:
    aud rules --summary | grep -i "custom"

EXAMPLE - Documenting Detection Capabilities:
    aud rules --summary
    # Generates .pf/auditor_capabilities.md
    # Include in security audit documentation

RULE SOURCES:
1. YAML Patterns (theauditor/patterns/*.yml):
   - Fast regex matching
   - Good for: secrets, hardcoded values, known-bad strings
   - Format: name, pattern (regex), severity, message, cwe

2. Python AST Rules (theauditor/rules/*.py):
   - Semantic code analysis
   - Good for: dataflow, control flow, context-aware detection
   - Format: Functions named find_* returning Finding objects

PATTERN CATEGORIES:
- Injection: SQL, command, LDAP, NoSQL injection
- Authentication: Hardcoded credentials, weak passwords, JWT issues
- Data Security: PII exposure, weak crypto, insecure random
- Framework-Specific: Django CSRF, Flask debug, React XSS

ADDING CUSTOM PATTERNS:
Create theauditor/patterns/custom.yml:
    - name: internal_api_call
      pattern: "api\\.internal\\."
      severity: medium
      message: Internal API call detected
      cwe: CWE-200
      categories:
        - custom

Then verify: aud rules --summary | grep internal_api

COMBINING WITH OTHER TOOLS:
- Use aud detect-patterns to run all rules on codebase
- Use aud rules --summary for documentation/compliance
- Rules feed into aud fce for correlation analysis

AGENT WORKFLOW:
Before security audits, run aud rules --summary to document
what vulnerabilities TheAuditor checks. Include capability
report in audit deliverables.

KEY OPTIONS:
- --summary: Generate comprehensive capability report (required flag)

OUTPUT FILES:
- .pf/auditor_capabilities.md: Full capability report

COMMON MISTAKES:
- Running without --summary: Command requires the flag
- Expecting rules to run analysis: Use aud detect-patterns for that
- Adding patterns with syntax errors: Validate YAML before running
- Forgetting to verify custom patterns: Always run --summary after adding

EXIT CODES:
- 0: Success, report generated
- 3: Task incomplete (must use --summary flag)

RELATED:
Commands: aud rules --summary, aud detect-patterns
Topics: aud manual patterns, aud manual severity, aud manual taint
""",
    },
    "setup": {
        "title": "Sandboxed Analysis Environment",
        "summary": "Create isolated environment with offline vulnerability scanning",
        "explanation": """
WHAT IT IS:
The setup-ai command creates a completely isolated analysis environment with its
own Python venv, JavaScript tools, and offline vulnerability databases. This
enables reproducible, air-gapped security analysis with no dependency conflicts.

WHEN TO USE IT:
- First time using TheAuditor on a project
- When you need offline/air-gapped vulnerability scanning
- To avoid conflicts with project dependencies
- Setting up CI/CD environments with consistent tooling
- After updating TheAuditor to refresh local tools

HOW TO USE IT:

PREREQUISITES:
    Python 3.11+, Node.js (for JavaScript tools), network access (initial setup)

STEPS:
    1. Run setup for your project:
       aud setup-ai --target .         # Creates .auditor_venv/ (~5-10 min)

    2. Wait for downloads to complete:
       - Python linters (ruff, mypy, black)
       - JavaScript tools (ESLint, TypeScript)
       - Vulnerability databases (~500MB)

    3. Run analysis:
       aud full                        # Uses sandboxed tools automatically

EXAMPLE - First Time Project Setup:
    cd /path/to/project
    aud setup-ai --target .            # One-time setup
    aud full                           # Run analysis
    aud deps --vuln-scan               # Offline vulnerability scan

COMMAND OPTIONS:
    aud setup-ai --target .            # Setup current directory
    aud setup-ai --target . --sync     # Force refresh all tools and databases
    aud setup-ai --target . --dry-run  # Preview what will be installed

WHAT GETS INSTALLED:

PYTHON ENVIRONMENT (.auditor_venv/):
- TheAuditor and all dependencies
- ruff, mypy, black (Python linters)
- Isolated from project and system Python

JAVASCRIPT TOOLS (.auditor_tools/):
- ESLint with TypeScript support
- Prettier code formatter
- TypeScript compiler
- Isolated from project node_modules

VULNERABILITY DATABASES (.auditor_venv/vuln_cache/):
- npm advisory database (~300MB)
- PyPI advisory database (~200MB)
- Auto-refreshes every 30 days

DIRECTORY STRUCTURE:
    <project>/
      .auditor_venv/                # Sandboxed environment
        Scripts/ (Windows) or bin/ # Executables
        vuln_cache/                 # Offline vulnerability databases
      .auditor_tools/               # JavaScript tools
        node_modules/               # Isolated npm packages

OFFLINE VULNERABILITY SCANNING:
After setup, aud deps --vuln-scan works completely offline:
1. OSV-Scanner uses local advisory database
2. No network requests during scanning
3. Reproducible results (same database = same findings)
4. Refresh with aud setup-ai --sync when needed

MULTI-PROJECT SETUP:
Each project can have its own sandbox:
    ~/project-a/.auditor_venv/
    ~/project-b/.auditor_venv/

COMBINING WITH OTHER TOOLS:
- After setup: Run aud full for complete analysis
- For CI/CD: Run setup once, then aud full --offline
- For updates: Run aud setup-ai --sync periodically

RELATED:
- Commands: aud setup-ai, aud tools, aud deps
- Topics: aud manual tools, aud manual deps, aud manual pipeline

COMMON MISTAKES:
- Skipping setup: Some features require sandboxed tools
- No network during initial setup: Databases need to download first
- Forgetting --sync: Vulnerability databases become stale
- Running in wrong directory: Use --target to specify project path
""",
    },
    "ml": {
        "title": "Machine Learning Risk Prediction",
        "summary": "Train models to predict file risk and root cause likelihood from audit history",
        "explanation": """
TheAuditor's ML system learns patterns from historical audit runs to predict
which files are most likely to contain vulnerabilities. This enables proactive
risk assessment - analyze high-risk files first for faster issue discovery.

WHEN TO USE IT:
- Prioritizing code review on large PRs (focus on risky files first)
- Identifying root cause files vs symptom files in bug hunts
- Building institutional knowledge from historical audit patterns
- Optimizing security review time on large codebases

PREREQUISITES:
- Run 'aud full' at least 5 times to build history in .pf/history/
- Each run creates ~100-200 samples (files analyzed)
- Cold-start mode works with less data but accuracy is poor
- Optional: Git repository for churn features (--enable-git)
- Optional: Claude Code sessions for agent behavior features

THE ML VALUE PROPOSITION:

Without ML, you analyze all files equally (expensive).
With ML, you prioritize high-risk files (efficient):
  - Top 10 risky files analyzed first
  - Root causes identified before symptoms
  - Review effort focused where bugs hide

THREE COMMANDS:

1. aud learn
   Train models from historical audit data in .pf/history/
   Output: .pf/ml/risk_model.pkl, root_cause_model.pkl

2. aud suggest
   Use trained models to rank files by risk score
   Output: .pf/insights/ml_suggestions.json

3. aud learn-feedback
   Re-train models with human corrections
   Output: Improved models with higher accuracy

WHAT THE MODELS LEARN:

Risk Prediction (Regression Model):
  - Which files are likely to have vulnerabilities
  - Based on: code complexity, churn rate, past findings
  - Output: Risk score 0.0-1.0 per file

Root Cause Classification (Binary):
  - Which files are the SOURCE of issues (not symptoms)
  - Based on: call graph position, data flow patterns
  - Output: Root cause probability per file

FEATURE ENGINEERING (97 dimensions):

Tier 1 - Pipeline Features:
  - Phase timing, success/failure patterns
  - Which analysis phases found issues

Tier 2 - Journal Features:
  - File touch frequency
  - Audit trail events

Tier 3 - Artifact Features:
  - Code complexity (cyclomatic, lines, functions)
  - Security patterns detected
  - Control flow graph metrics

Tier 4 - Git Features (optional):
  - Commit frequency (churn)
  - Author count
  - Days since modified

Tier 5 - Agent Behavior (optional):
  - Claude Code session metrics
  - Blind edit rate, user engagement
  - Workflow compliance

DATA REQUIREMENTS:

Cold Start (<500 samples):
  - Models trained but accuracy poor (R2 < 0.60)
  - Works but predictions are unreliable
  - Need more audit runs

Production Ready (1000+ samples):
  - Accuracy improves (R2 > 0.70)
  - Predictions become useful
  - Can trust top-K rankings

COMBINING WITH OTHER TOOLS:
  ML + Session Analysis:
    aud session analyze                      # Parse agent sessions
    aud learn --session-analysis --enable-git # Include Tier 5 features

  ML + Workset:
    aud workset --diff main..HEAD            # Create focused file list
    aud suggest --print-plan                 # Rank workset by risk

  ML + Taint Analysis:
    aud suggest --topk 5                     # Get highest risk files
    aud taint --verbose                      # Focus deep analysis there

HUMAN FEEDBACK LOOP:

Models improve via supervised correction:

1. Run 'aud suggest' to get predictions
2. Review predictions, note errors
3. Create feedback.json with corrections
4. Run 'aud learn-feedback' to re-train
5. Verify improved predictions

Feedback file format:
{
  "src/auth.py": {
    "is_risky": true,
    "is_root_cause": true,
    "will_need_edit": true
  }
}

TYPICAL WORKFLOW:

Initial Setup (accumulate data):
  aud full              # Run 5+ times
  aud learn --print-stats

Daily Usage:
  aud workset --diff main..HEAD
  aud suggest --print-plan
  # Focus review on top-K files

Weekly Re-training:
  aud full && aud learn --enable-git

USE THE COMMANDS:
    aud learn --print-stats             # Train models
    aud learn --enable-git              # Include git features
    aud suggest --print-plan            # Show top risky files
    aud suggest --topk 20               # More suggestions
    aud learn-feedback --feedback-file corrections.json

COMMON MISTAKES:
- Running 'aud suggest' before 'aud learn' (models don't exist yet)
- Expecting good predictions with <500 samples (cold-start is unreliable)
- Not re-training after code changes (models become stale)
- Using --enable-git without a git repository (feature extraction fails)
- Forgetting to run 'aud full' between code changes (history stays stale)

RELATED CONCEPTS:
    aud manual fce        # Root cause vs symptom
    aud manual session    # Agent behavior analysis
""",
    },
    "planning": {
        "title": "Planning and Verification System",
        "summary": "Database-centric task management with spec-based verification",
        "explanation": """
The planning system provides deterministic task tracking with spec-based
verification. Unlike external tools (Jira, Linear), planning integrates
directly with TheAuditor's indexed codebase for instant verification.

WHEN TO USE IT:
- Large refactoring requiring checkpoints and rollback capability
- Migration projects with verifiable success criteria
- Complex multi-phase work needing progress tracking
- Team coordination with spec-based acceptance criteria

PREREQUISITES:
- Git repository (for snapshots and diffs)
- Run 'aud full' before verify-task (needs indexed codebase)
- YAML spec file for verification-based tasks

DATABASE STRUCTURE:
  .pf/planning/planning.db (separate from repo_index.db, persists across aud full)
  - plans              # Top-level plan metadata
  - plan_phases        # Grouped phases for hierarchical planning
  - plan_tasks         # Individual tasks (auto-numbered 1,2,3...)
  - plan_jobs          # Checkbox items within tasks
  - plan_specs         # YAML verification specs (RefactorProfile format)
  - code_snapshots     # Git checkpoint metadata
  - code_diffs         # Full unified diffs for rollback

VERIFICATION SPECS:
  Specs use RefactorProfile YAML format (compatible with aud refactor):

  Example - JWT Secret Migration:
    refactor_name: Secure JWT Implementation
    description: Ensure all JWT signing uses env vars
    rules:
      - id: jwt-secret-env
        description: JWT must use process.env.JWT_SECRET
        match:
          identifiers: [jwt.sign]
        expect:
          identifiers: [process.env.JWT_SECRET]

COMMON WORKFLOWS:

  Greenfield Feature Development:
    1. aud planning init --name "New Feature"
    2. aud query --api "/users" --format json  # Find analogous patterns
    3. aud planning add-task 1 --title "Add /products endpoint"
    4. [Implement feature]
    5. aud full && aud planning verify-task 1 1

  Refactoring Migration:
    1. aud planning init --name "Auth0 to Cognito"
    2. aud planning add-task 1 --title "Migrate routes" --spec auth_spec.yaml
    3. [Make changes]
    4. aud full && aud planning verify-task 1 1 --auto-update
    5. aud planning archive 1 --notes "Deployed to prod"

  Checkpoint-Driven Development:
    1. aud planning add-task 1 --title "Complex Refactor"
    2. [Make partial changes]
    3. aud planning checkpoint 1 1 --name "step-1"
    4. [Continue work]
    5. aud planning show-diff 1 1  # View all checkpoints
    6. aud planning rewind 1 1 --to 2  # Rollback if needed

SUBCOMMANDS:
  init         Create new plan (auto-creates .pf/planning/planning.db)
  show         Display plan status and task list
  list         List all plans in the database
  add-phase    Add a phase (hierarchical planning)
  add-task     Add task with optional YAML spec
  add-job      Add checkbox item to task
  update-task  Change task status or assignee
  verify-task  Run spec against indexed code
  archive      Create final snapshot and mark complete
  rewind       Show git commands to rollback
  checkpoint   Create incremental snapshot
  show-diff    View stored diffs for a task
  validate     Validate execution against session logs
  setup-agents Inject agent triggers into docs

SUBCOMMAND REFERENCE (exact syntax):

  init - Create a new plan:
    aud planning init --name "Plan Name" --description "Optional description"

  add-phase - Add hierarchical phase (groups tasks):
    aud planning add-phase <plan_id> --phase-number <N> --title "Phase Title" \\
        --description "What this phase covers" \\
        --success-criteria "How we know phase is complete"
    Example:
      aud planning add-phase 1 --phase-number 1 --title "Database Migration" \\
          --success-criteria "All tables migrated and verified"

  add-task - Add task to plan (optionally under a phase):
    aud planning add-task <plan_id> --title "Task Title" \\
        --description "Details" --phase <N> --spec spec.yaml
    Example:
      aud planning add-task 1 --title "Migrate users table" --phase 1

  add-job - Add checkbox item to task:
    aud planning add-job <plan_id> <task_number> --description "Step" --is-audit
    Example:
      aud planning add-job 1 1 --description "Run migration script"
      aud planning add-job 1 1 --description "Verify row counts match" --is-audit

  update-task - Change task status:
    aud planning update-task <plan_id> <task_number> --status completed
    aud planning update-task <plan_id> <task_number> --assigned-to "Name"

  verify-task - Run spec verification:
    aud planning verify-task <plan_id> <task_number> --verbose --auto-update

  show - Display plan hierarchy:
    aud planning show <plan_id> --format phases  # Full hierarchy
    aud planning show <plan_id> --format flat    # Flat task list

FLAG NAMING NOTE:
  - init uses --name (plan name)
  - add-phase and add-task use --title (phase/task title)
  This is intentional: plans have names, phases/tasks have titles.

COMBINING WITH OTHER TOOLS:
  Planning + Refactor Agent:
    The planning system integrates with the /theauditor:planning slash command
    which triggers the planning.md agent for database-first approach.
    See: .auditor_venv/.theauditor_tools/agents/planning.md

  Planning + Impact Analysis:
    aud impact --file changed.py --line 50  # Assess blast radius
    aud planning add-task 1 --title "Update affected files"

  Planning + Workset:
    aud workset --diff HEAD~5                # What changed?
    aud planning checkpoint 1 1              # Snapshot before more work

COMMON MISTAKES:
- Forgetting to run 'aud full' before verify-task (spec checks stale index)
- Creating specs that are too strict (any change fails verification)
- Not using checkpoint before risky changes (lose rollback ability)
- Using aud planning without git (snapshots and diffs won't work)

USE THE COMMANDS:
    aud planning init --name "Migration Plan"
    aud planning add-task 1 --title "Task" --spec spec.yaml
    aud full && aud planning verify-task 1 1 --verbose
    aud planning show 1 --format phases
""",
    },
    "terraform": {
        "title": "Terraform IaC Security Analysis",
        "summary": "Infrastructure-as-Code security analysis for Terraform configurations",
        "explanation": """
WHAT IT IS:
Terraform security analysis detects infrastructure misconfigurations in .tf files
before deployment. It builds a provisioning graph showing how variables flow to
resources and outputs, then runs security rules to find public exposure, missing
encryption, and overly permissive IAM policies.

WHEN TO USE IT:
- Before applying Terraform changes to production
- During PR review when infrastructure files are modified
- As part of security audit after running aud full
- In CI/CD pipelines to block insecure infrastructure
- When auditing existing cloud infrastructure definitions

HOW TO USE IT:

PREREQUISITES:
    aud full                              # Build database first (required)

STEPS:
1. Index your Terraform files:
   aud full                               # Extracts .tf file contents

2. Build the provisioning graph:
   aud terraform provision                # Maps var->resource->output flow

3. Run security analysis:
   aud terraform analyze                  # All findings
   aud terraform analyze --severity high  # Filter to high+ severity

4. Review findings:
   - Terminal shows summary by category
   - Use --format json for machine-readable output
   - Query graph with: aud graph query

EXAMPLE - Pre-Deployment Security Check:
    aud full && aud terraform provision && aud terraform analyze --severity high

WHAT IT DETECTS:
- Public Exposure: S3 public access, 0.0.0.0/0 security groups, public RDS
- IAM Issues: Wildcard permissions, overly permissive trust policies
- Encryption: Unencrypted S3/EBS/RDS, missing TLS, weak algorithms
- Secrets: Hardcoded credentials, exposed API keys, plaintext passwords

PROVISIONING GRAPH:
The provision command builds a data flow graph showing:
- Variable -> Resource -> Output connections
- Resource dependency chains (depends_on, implicit refs)
- Sensitive data propagation paths
- Public exposure blast radius

COMBINING WITH OTHER TOOLS:
- After terraform: Run aud cdk analyze if you also have CDK code
- For full audit: aud full includes terraform in pipeline
- With deps: Check Terraform provider versions for vulnerabilities
- For code context: Use aud explain on modules referenced in .tf files

AGENT WORKFLOW:
When using the security agent (/theauditor:security), Terraform analysis runs
as part of Phase 3 infrastructure checks. The agent queries:
    aud terraform provision && aud terraform analyze --severity high

OUTPUT:
    .pf/graphs.db                     # Graph stored for querying
    findings_consolidated table       # Security findings (query with aud query --findings)

RELATED:
Commands: aud terraform provision, aud terraform analyze, aud cdk analyze
Topics: aud manual docker, aud manual cdk, aud manual severity

COMMON MISTAKES:
- Running analyze before provision: Graph not built, missing dependency insights
- Skipping aud full: No .tf content in database to analyze
- Ignoring variable flow: Sensitive data may propagate through multiple resources
- Not using --severity filter: Getting overwhelmed by low-priority findings

EXIT CODES:
- 0: Success, no critical/high issues found
- 1: Security issues detected
- 2: Critical security issues detected
- 3: Analysis failed (database missing)
""",
    },
    "tools": {
        "title": "Analysis Tool Dependencies",
        "summary": "Manage and verify installed analysis tools (linters, scanners, runtimes)",
        "explanation": """
TheAuditor uses multiple external tools for comprehensive code analysis. The tools
command group helps detect, verify, and report on these dependencies.

WHEN TO USE IT:
- Before first run to verify environment is properly configured
- CI/CD setup to ensure required tools are available
- Troubleshooting missing tool errors
- Documenting your analysis environment

PREREQUISITES:
- None (this command checks prerequisites for OTHER commands)

TOOL CATEGORIES:

  Python Tools:
    - python:  Python interpreter (required)
    - ruff:    Fast Python linter (recommended)
    - mypy:    Static type checker
    - pytest:  Test framework
    - bandit:  Security linter
    - semgrep: Semantic code analysis

  Node.js Tools:
    - node:       Node.js runtime (required for JS/TS)
    - npm:        Package manager
    - eslint:     JavaScript linter
    - typescript: TypeScript compiler
    - prettier:   Code formatter

  Rust Tools:
    - cargo:       Rust package manager
    - tree-sitter: Parser generator (used for AST parsing)

TOOL SOURCES:
  TheAuditor checks for tools in two locations:
  - system:  Installed globally on your system (in PATH)
  - sandbox: Installed in .auditor_venv/.theauditor_tools/

  The sandbox is preferred for isolation and reproducibility.

SUBCOMMANDS:
  list    Show all tools and their versions (default)
  check   Verify required tools are installed
  report  Generate version report (use --json for machine-readable)

COMBINING WITH OTHER TOOLS:
  Tools + Setup:
    aud setup-ai --target .              # Install tools to sandbox
    aud tools check --strict             # Verify all installed

  Tools + Full Audit:
    aud tools check                      # Verify before running
    aud full --offline                   # Run with confidence

  CI/CD Pipeline:
    aud tools check --required semgrep,bandit || exit 1
    aud full

TYPICAL WORKFLOW:
    # 1. Check what tools are installed
    aud tools

    # 2. Verify core tools before analysis
    aud tools check

    # 3. Generate report for CI/documentation
    aud tools report

CORE REQUIRED TOOLS:
By default, 'aud tools check' requires:
  - python
  - ruff
  - node
  - eslint

Use --strict to require ALL tools, or --required to specify custom requirements.

COMMON MISTAKES:
- Running analysis without checking tools first (failures mid-pipeline)
- Installing tools in system PATH when sandbox is preferred
- Expecting 'aud tools' to install missing tools (it only checks)
- Not running 'aud setup-ai' after fresh clone

USE THE COMMANDS:
    aud tools                          # List all tools
    aud tools list --json              # JSON output
    aud tools check                    # Verify core tools
    aud tools check --strict           # All tools required
    aud tools check --required semgrep # Require specific tool
    aud tools report --json            # JSON version report to stdout
""",
    },
    "metadata": {
        "title": "Temporal and Quality Metadata Collection",
        "summary": "Git churn and test coverage metrics for risk correlation",
        "explanation": """
The metadata command group collects temporal and quality facts about your codebase
for use in FCE (Feed-forward Correlation Engine) risk analysis. It answers: "What
files change frequently?" and "What code is poorly tested?"

WHEN TO USE IT:
- Before running FCE to correlate vulnerabilities with code quality
- Identifying hot spots that need refactoring attention
- Prioritizing security review on high-churn, low-coverage files
- Adding temporal dimension to ML training features

PREREQUISITES:
- Git repository for churn analysis
- Coverage report file for coverage analysis (pytest-cov, Istanbul, lcov)
- Run 'aud full' first if correlating with taint/pattern findings

WHY METADATA MATTERS:

Code Risk = Vulnerabilities + Churn + (Inverse of Coverage)

A file with:
- Security vulnerabilities (from taint/patterns analysis)
- High churn (many recent changes, many authors)
- Low coverage (no tests catching bugs)

...is a HIGH RISK file that should be prioritized for review.

CHURN METRICS:

Git churn measures file volatility:
- commits_90d: Total commits in last N days
- unique_authors: Number of different contributors
- days_since_modified: Time since last change

High churn indicates:
- Active development (bugs likely)
- Unstable interfaces (breaking changes)
- Hot spots (everyone touches it)

COVERAGE METRICS:

Test coverage measures quality:
- line_coverage_percent: Percentage of lines executed by tests
- lines_missing: Count of untested lines
- uncovered_lines: Specific line numbers without tests

Low coverage indicates:
- Untested paths (bugs hiding)
- Incomplete validation
- Risky refactoring targets

SUBCOMMANDS:
  churn     Analyze git commit history for file volatility
  coverage  Parse test coverage reports (coverage.py, Jest)
  analyze   Combined churn + coverage analysis

SUPPORTED COVERAGE FORMATS:
  Python:     coverage.json (coverage.py)
  JavaScript: coverage-final.json (Istanbul/nyc)
  Generic:    lcov.info

COMBINING WITH OTHER TOOLS:
  Metadata + FCE:
    aud metadata churn && aud metadata coverage
    aud fce                              # Correlates all findings + metadata

  Metadata + ML:
    aud metadata churn --days 30
    aud learn --enable-git               # Uses churn as Tier 4 features

  Metadata + Security Audit:
    aud full
    aud metadata analyze
    aud manual fce                       # Understand correlation results

TYPICAL WORKFLOW:
    # 1. Generate coverage report (using your test framework)
    pytest --cov=src --cov-report=json

    # 2. Collect metadata
    aud metadata churn --days 30
    aud metadata coverage

    # 3. Correlate with findings
    aud fce

USE THE COMMANDS:
    aud metadata churn                    # Last 90 days churn
    aud metadata churn --days 30          # Last 30 days
    aud metadata coverage                 # Auto-detect coverage file
    aud metadata coverage --coverage-file coverage.json
    aud metadata analyze                  # Both churn + coverage

COMMON MISTAKES:
- Running churn without a git repository (no history to analyze)
- Expecting coverage analysis without a coverage report file
- Using wrong coverage format (pytest-cov needs --cov-report=json)
- Not running aud full first (FCE needs indexed findings to correlate)

OUTPUT:
    Data stored in repo_index.db    # Query with aud query
    Use --json for stdout output    # Pipe to file if needed
""",
    },
    "cdk": {
        "title": "AWS CDK Infrastructure-as-Code Security",
        "summary": "Security analysis for AWS CDK Python/TypeScript/JavaScript code",
        "explanation": """
WHAT IT IS:
AWS CDK security analysis detects infrastructure misconfigurations in CDK code
(Python, TypeScript, JavaScript) before deployment to AWS. Unlike Terraform
which uses HCL, CDK uses programming languages - TheAuditor parses the AST to
find security issues in construct configurations.

WHEN TO USE IT:
- Before running cdk deploy to production
- During PR review when CDK stacks are modified
- As part of security audit after running aud full
- In CI/CD pipelines to block insecure infrastructure
- When auditing existing CDK applications

HOW TO USE IT:

PREREQUISITES:
    aud full                              # Build database first (required)

STEPS:
1. Index your CDK project:
   aud full                               # Extracts CDK construct definitions

2. Run security analysis:
   aud cdk analyze                        # All findings
   aud cdk analyze --severity high        # Filter to high+ severity

3. Review findings:
   - Terminal shows summary by category
   - Use --format json for machine-parseable output
   - Findings stored in cdk_findings database table

4. For programmatic access, use Python:
   import sqlite3
   conn = sqlite3.connect('.pf/repo_index.db')
   c = conn.cursor()
   c.execute('SELECT * FROM cdk_findings WHERE severity="critical"')

EXAMPLE - Pre-Deployment Security Check:
    aud full && aud cdk analyze --severity high

WHAT IT DETECTS:
- S3 Buckets: public_read_access=True, missing block_public_access, unencrypted
- Databases: publicly_accessible=True, storage_encrypted=False, no backup
- IAM: Wildcard actions, overly permissive policies, Principal.Account("*")
- Network: Open security groups, missing NAT, public subnet misuse

CDK CODE EXAMPLE (What Gets Flagged):
    bucket = s3.Bucket(
        self, "MyBucket",
        public_read_access=True,     # FLAGGED: data exposure
        encryption=s3.BucketEncryption.UNENCRYPTED  # FLAGGED: compliance
    )

COMBINING WITH OTHER TOOLS:
- After cdk: Run aud terraform analyze if you also have .tf files
- For full audit: aud full includes CDK analysis in pipeline
- With detect-patterns: Includes CDK-specific security rules
- For code context: Use aud explain on CDK stack files

AGENT WORKFLOW:
When using the security agent (/theauditor:security), CDK analysis runs
as part of Phase 3 infrastructure checks. The agent queries:
    aud cdk analyze --severity high

CDK VS TERRAFORM:
- CDK: Programming languages (Python, TypeScript, JavaScript)
- Terraform: HCL configuration files (.tf)
Use aud cdk for CDK projects, aud terraform for Terraform projects.

RELATED:
Commands: aud cdk analyze, aud terraform analyze, aud detect-patterns
Topics: aud manual terraform, aud manual docker, aud manual severity

COMMON MISTAKES:
- Running before aud full: No CDK constructs in database to analyze
- Expecting CloudFormation output: Analyzes CDK source, not synth output
- Ignoring MEDIUM findings: Public access issues may seem minor but cascade
- Not checking both CDK and Terraform: Projects often mix IaC approaches

EXIT CODES:
- 0: No security issues found
- 1: Security issues detected
- 2: Critical security issues detected
- 3: Analysis failed (database missing)
""",
    },
    "graphql": {
        "title": "GraphQL Schema and Resolver Analysis",
        "summary": "Map GraphQL SDL schemas to backend resolver implementations",
        "explanation": """
WHAT IT IS:
GraphQL analysis correlates SDL schema definitions (.graphql/.gql files) with
backend resolver implementations. This bridges the gap between "what clients
can query" and "what code actually runs", enabling data flow tracking through
the GraphQL execution layer.

WHEN TO USE IT:
- After indexing a GraphQL API to understand schema-to-code mapping
- Before taint analysis to include GraphQL argument flows
- When auditing resolvers for security issues (N+1, auth bypass)
- During PR review when schema or resolvers change
- When finding orphaned resolvers or unimplemented fields

HOW TO USE IT:

PREREQUISITES:
    aud full                              # Build database first (required)

STEPS:
1. Index the codebase (extracts SDL + resolver code):
   aud full                               # Parses .graphql and resolver files

2. Build resolver mappings:
   aud graphql build                      # Correlates fields to resolvers
   aud graphql build --verbose            # Show correlation details

3. Inspect schema and mappings:
   aud graphql query --type Query         # List Query type fields
   aud graphql query --field user         # Find user field resolver

4. Use in taint analysis:
   aud taint                              # Uses GraphQL edges for data flow

EXAMPLE - Full GraphQL Security Audit:
    aud full && aud graphql build && aud taint

SCHEMA-TO-RESOLVER CORRELATION:

  Schema (SDL):               Resolver (Code):
  type Query {                @Query()
    user(id: ID!): User  -->  resolve_user(id):
  }                             return db.get_user(id)

This enables:
- Finding fields without resolver implementations
- Tracing data flow from GraphQL arguments to database
- Detecting N+1 query patterns
- Security analysis of resolver implementations

FRAMEWORK SUPPORT:
- Python: Graphene (resolve_<field>), Ariadne (@query.field), Strawberry
- JavaScript: Apollo Server, TypeGraphQL
- TypeScript: NestJS GraphQL (@Query/@Mutation), TypeGraphQL

COMBINING WITH OTHER TOOLS:
- After graphql build: Run aud taint for complete data flow analysis
- For architecture: aud blueprint --graph shows GraphQL in call graph
- With explain: aud explain <resolver_function> for caller/callee context
- For security: Combine with aud detect-patterns for injection detection

AGENT WORKFLOW:
When using the dataflow agent (/theauditor:dataflow), GraphQL analysis runs
as part of Phase 2 to build execution edges. The agent queries:
    aud graphql build --verbose

OUTPUT:
    Data stored in database tables (see below)
    Use --format json for stdout output

DATABASE TABLES:
    graphql_types              # Type definitions from SDL
    graphql_fields             # Field definitions with args
    graphql_resolver_mappings  # Field-to-resolver correlations
    graphql_execution_edges    # Execution flow graph

RELATED:
Commands: aud graphql build, aud graphql query, aud taint, aud graph
Topics: aud manual taint, aud manual graph, aud manual architecture

COMMON MISTAKES:
- Running graphql query before graphql build: No mappings to query
- Expecting auto-correlation: Run 'aud graphql build' explicitly
- Missing SDL files: Ensure .graphql/.gql files are in indexed directories
- Wrong framework pattern: Check resolver naming matches detected framework

EXIT CODES:
- 0: Success, mappings built
- 1: Partial success (some fields unresolved)
- 2: Error (database missing or SDL parse failed)
""",
    },
    "blueprint": {
        "title": "Blueprint Command",
        "summary": "Architectural fact visualization with drill-down analysis modes",
        "explanation": """
WHAT IT IS:
Blueprint provides a complete architectural overview of your indexed codebase
in "truth courier" mode - presenting pure facts with zero recommendations.
It's the starting point for understanding any codebase.

WHEN TO USE IT:
- Onboarding: First command when exploring a new codebase
- Planning: Before making architectural changes (database first!)
- Security audit: See security surface overview
- AI context: Get codebase facts for planning agents
- Documentation: Export architecture as JSON for reports

HOW TO USE IT:

PREREQUISITES:
    aud full                                  # Build the database first

STEPS:
1. Get top-level overview:
    aud blueprint                             # Default overview

2. Drill into specific dimensions:
    aud blueprint --structure                 # File organization, LOC counts
    aud blueprint --graph                     # Import relationships, hotspots
    aud blueprint --security                  # JWT, OAuth, SQL, API endpoints
    aud blueprint --taint                     # Taint sources/sinks
    aud blueprint --deps                      # Package dependencies
    aud blueprint --boundaries                # Entry points, validation distances

3. Find large files (for AI chunk planning):
    aud blueprint --monoliths                 # Files >2150 lines
    aud blueprint --monoliths --threshold 1000  # Custom threshold

4. Export for documentation:
    aud blueprint --all > architecture.json   # Full JSON export
    aud blueprint --graph --format json       # Specific dimension as JSON

DRILL-DOWN FLAGS:
- --structure: File counts, LOC, module boundaries
- --graph: Import graph stats, hotspots, cycles
- --security: JWT, OAuth, SQL, API endpoints
- --taint: Sources, sinks, flow paths
- --boundaries: Entry points, validation distances
- --deps: Package dependencies by manager
- --all: Complete JSON export

EXAMPLE WORKFLOW - New Codebase Onboarding:
    aud full                                  # Index the codebase
    aud blueprint --structure                 # Understand file organization
    aud blueprint --security                  # See security surface
    aud blueprint --monoliths                 # Find large files needing chunks

COMBINING WITH OTHER TOOLS:
- With planning agent: Run blueprint --structure FIRST (database first rule)
- With graph: Blueprint summarizes, graph commands drill deeper
- With impact: Blueprint shows overall architecture, impact shows change scope
- For export: --format json for programmatic consumption

AGENT WORKFLOW:
The planning agent (/theauditor:planning) MUST run blueprint in Phase 1:
    aud blueprint --structure                 # Load foundation context
    aud blueprint --monoliths                 # Identify large files

This is THE ONE RULE: Database first. Always run blueprint before planning.

COMMON MISTAKES:
- Skipping aud full: Blueprint queries the database, needs indexing first
- Expecting recommendations: Blueprint shows FACTS only (truth courier mode)
- Missing --monoliths: Large files (>2150 lines) need chunked reading for AI

RELATED:
Commands: aud blueprint, aud graph, aud explain, aud query
Topics: aud manual architecture, aud manual graph, aud manual pipeline
""",
    },
    "query": {
        "title": "Database Query Interface",
        "summary": "Direct SQL queries over indexed code relationships",
        "explanation": """
WHAT IT IS:
The query command provides direct access to TheAuditor's indexed database.
It returns exact file:line locations for symbols, dependencies, and call
chains. Pure database lookups - no file reading, no parsing, instant results.
Use this for precise, targeted lookups; use aud explain for comprehensive context.

WHEN TO USE IT:
- Finding symbol callers: Who calls this function before I change it?
- Checking file dependencies: Who imports this file before I move it?
- API endpoint lookup: What handles this route?
- Pattern search: Find all functions matching a pattern
- Discovery mode: List all symbols in a file or matching a filter
- Data flow tracing: Track variable assignments and usage

HOW TO USE IT:
PREREQUISITES:
    aud full                              # Build database first

STEPS:
    1. Pick your query target:
       aud query --symbol validateUser    # Look up a symbol
       aud query --file src/auth.ts       # Look up a file
       aud query --api "/users/:id"       # Look up an API route

    2. Add action flags to show relationships:
       aud query --symbol foo --show-callers   # Who calls foo?
       aud query --file bar.ts --show-dependents  # Who imports bar.ts?

    3. Add modifiers for output control:
       aud query --symbol foo --show-callers --format json  # JSON output
       aud query --symbol foo --show-callers --depth 2  # 2-level deep

EXAMPLE - Before Renaming a Function:
    aud query --symbol validateUser --show-callers
    # Shows: called by auth.py:42, login.py:15, api.py:88
    # Action: Update all 3 callers when renaming

COMBINING WITH OTHER TOOLS:
- For comprehensive context: Use aud explain instead (more info, one call)
- For project overview: Use aud blueprint first, then query specifics
- For impact analysis: Use aud impact for blast radius, query for details
- In scripts: Use --format json for parseable output

QUERY TARGETS (pick one):
    --symbol NAME       Function/class/variable lookup
    --file PATH         File dependency lookup
    --api ROUTE         API endpoint handler lookup
    --component NAME    React/Vue component tree
    --variable NAME     Variable for data flow tracing
    --pattern PATTERN   SQL LIKE search (use % wildcard)
    --list-symbols      List symbols with --filter and --path
    --category CAT      Security category (jwt, oauth, password, sql)
    --search TERM       Cross-table exploratory search

ACTION FLAGS (what to show):
    --show-callers      Who calls this symbol?
    --show-callees      What does this symbol call?
    --show-dependencies What does this file import?
    --show-dependents   Who imports this file?
    --show-incoming     Who calls symbols in this file?
    --show-tree         Component hierarchy (parent-child)
    --show-hooks        React hooks used by component
    --show-data-deps    Variables function reads/writes (DFG)
    --show-flow         Variable flow through assignments
    --show-taint-flow   Cross-function taint flow
    --show-api-coverage Which endpoints have auth controls?

MODIFIERS:
    --depth N           Transitive depth 1-5 (default=1)
    --format json       JSON output for parsing
    --type-filter TYPE  Filter by type (function, class, variable)
    --show-code         Include source snippets
    --save PATH         Save output to file

RELATED:
Commands: aud query, aud explain, aud blueprint, aud impact
Topics: aud manual explain, aud manual database, aud manual blueprint

COMMON MISTAKES:
- Using query for comprehensive context: Too many calls needed
  -> Use aud explain instead (returns everything in one call)
- Querying ClassName.method as foo.bar: Methods stored differently
  -> Query just the method name, or use exact ClassName.methodName
- Running before aud full: No database means no results
  -> Always run aud full first to populate repo_index.db
- Forgetting --format json in scripts: Text output is for humans
  -> Use --format json when parsing output programmatically

PERFORMANCE:
- <10ms for indexed lookups
- Instant results (pure database query, no file I/O)
""",
    },
    "deps": {
        "title": "Dependency Analysis",
        "summary": "Analyze dependencies for vulnerabilities and updates",
        "explanation": """
The deps command provides comprehensive dependency analysis supporting multiple
package managers: npm/yarn, pip/poetry, Docker, and Cargo.

WHEN TO USE IT:
- CI/CD pipelines to block deploys with known vulnerabilities
- Pre-release security checks on third-party dependencies
- Batch upgrading outdated packages by ecosystem
- Auditing supply chain risk in your dependency tree

SUPPORTED FILES:
  - package.json / package-lock.json (npm/yarn)
  - pyproject.toml (Poetry/setuptools)
  - requirements.txt / requirements-*.txt (pip)
  - docker-compose*.yml / Dockerfile (Docker)
  - Cargo.toml (Rust)

OPERATION MODES:
  Default:        Parse and inventory all dependencies
  --check-latest: Check for available updates (grouped by file)
  --vuln-scan:    Run security scanners (npm audit + OSV-Scanner)
  --upgrade-all:  YOLO mode - upgrade everything to latest
  --usage <pkg>:  Extract usage examples from cached docs (JSON output)

SELECTIVE UPGRADES:
  --upgrade-py:     Only requirements*.txt + pyproject.toml
  --upgrade-npm:    Only package.json files
  --upgrade-docker: Only docker-compose*.yml + Dockerfile
  --upgrade-cargo:  Only Cargo.toml
  (Combine flags to upgrade multiple ecosystems)

VULNERABILITY SCANNING (--vuln-scan):
  - Runs 2 native tools: npm audit and OSV-Scanner
  - Cross-references findings for validation (confidence scoring)
  - Reports CVEs with severity levels
  - Exit code 2 for critical vulnerabilities
  - Offline mode uses local OSV databases

COMBINING WITH OTHER TOOLS:
  Deps + Full Audit:
    aud full --offline                   # Complete security audit
    aud deps --vuln-scan                 # Add supply chain check

  Deps + FCE Correlation:
    aud deps --vuln-scan
    aud fce                              # Correlate vuln findings with code

  CI/CD Pipeline:
    aud deps --vuln-scan --offline || exit 2  # Block on vulnerabilities

EXAMPLES:
    aud deps                              # Basic dependency inventory
    aud deps --check-latest               # Check for outdated packages
    aud deps --upgrade-py                 # Upgrade only Python dependencies
    aud deps --upgrade-py --upgrade-npm   # Upgrade Python and npm
    aud deps --vuln-scan                  # Security vulnerability scan
    aud deps --upgrade-all                # DANGEROUS: Upgrade everything
    aud deps --offline                    # Skip all network operations
    aud deps --usage axios                # Get usage examples for axios (JSON)
    aud deps --usage @angular/core        # Works with scoped npm packages

OUTPUT:
    Data stored in database         # Query with aud query --findings
    Use --json for stdout output    # Pipe to file if needed

EXIT CODES:
    0 = Success
    2 = Critical vulnerabilities found (--vuln-scan)

COMMON MISTAKES:
- Running --check-latest without network access (needs registry APIs)
- Using --upgrade-all without testing (breaks your project)
- Expecting vuln-scan to find code vulnerabilities (only finds package CVEs)
- Not using --offline in CI/CD (rate limits cause flaky builds)

PERFORMANCE: 1-30 seconds (depends on network and registry responses)

PREREQUISITES:
    None for basic inventory
    Network access for --check-latest and --vuln-scan

RELATED COMMANDS:
    aud manual frameworks  # Framework detection
    aud manual rust        # Rust/Cargo specific analysis
""",
    },
    "explain": {
        "title": "Comprehensive Code Context",
        "summary": "Get complete context about a file, symbol, or component in one call",
        "explanation": """
WHAT IT IS:
The explain command provides a complete "briefing packet" in ONE command.
It returns everything you need to know about a file, symbol, or component:
definitions, callers, callees, dependencies, and code snippets. Optimized
for AI workflows - saves 5-10 query calls per task.

WHEN TO USE IT:
- Before modifying code: Understand callers before changing signature
- Investigating a symbol: Find definition, callers, and what it calls
- Understanding a file: See all symbols, imports, and who depends on it
- Component analysis: Get props, hooks, and child components
- Replacing multiple queries: One call instead of 5-6 aud query calls

HOW TO USE IT:
PREREQUISITES:
    aud full                              # Build database first

STEPS:
    1. Run explain on your target (auto-detects type):
       aud explain src/auth.py            # File context
       aud explain validateUser           # Symbol context
       aud explain Dashboard              # Component context

    2. Review the briefing packet:
       - SYMBOLS DEFINED (for files)
       - CALLERS / CALLEES (for symbols)
       - DEPENDENCIES / DEPENDENTS (for files)

    3. Use the context to make informed changes

EXAMPLE - Before Refactoring a Function:
    aud explain validateUser
    # Shows: defined at auth.py:42, called by 15 functions
    # Shows: calls sanitizeInput, checkPermissions
    # Action: Now you know the blast radius before changing signature

TARGET TYPES (auto-detected):
- File path: aud explain src/auth.ts
- Symbol name: aud explain validateUser
- Class.method: aud explain UserController.create
- Component: aud explain Dashboard

COMBINING WITH OTHER TOOLS:
- Instead of query: Use explain for comprehensive context in one call
- Before impact: Use explain to understand a symbol before impact analysis
- After deadcode: Use explain to verify a file is truly unused
- With blueprint: Use blueprint for overview, explain for specific targets

WHAT IT RETURNS:

For files:
- SYMBOLS DEFINED: Functions, classes, variables with line numbers
- HOOKS USED: React/Vue hooks (frontend files)
- DEPENDENCIES: Files imported by this file
- DEPENDENTS: Files that import this file
- OUTGOING CALLS: Functions called from this file
- INCOMING CALLS: Functions in this file called elsewhere

For symbols:
- DEFINITION: File, line, type, signature
- CALLERS: Who calls this symbol
- CALLEES: What this symbol calls

For components:
- COMPONENT INFO: Type, props, file location
- HOOKS USED: React hooks with lines
- CHILD COMPONENTS: Components rendered by this one

COMMAND OPTIONS:
    aud explain <target>                  # Auto-detect type
    aud explain <target> --format json    # JSON for AI parsing
    aud explain <target> --depth 2        # Follow call graph deeper
    aud explain <target> --no-code        # Skip snippets (faster)
    aud explain <target> --limit 10       # Max items per section
    aud explain <target> --section callers # Only show callers

RELATED:
Commands: aud explain, aud query, aud blueprint, aud impact
Topics: aud manual query, aud manual blueprint, aud manual impact

COMMON MISTAKES:
- Using query for comprehensive context: Explain does it in one call
  -> Use aud explain instead of multiple aud query commands
- Running before aud full: No database means no results
  -> Always run aud full first to populate repo_index.db
- Forgetting --format json for AI: Text output is for humans
  -> Use --format json when parsing output programmatically
- Deep depth on large codebases: Slow and too much output
  -> Start with --depth 1, increase only if needed

PERFORMANCE:
- <100ms for files with <50 symbols
- Scales linearly with symbol count and call graph depth
""",
    },
    "deadcode": {
        "title": "Dead Code Detection",
        "summary": "Find unused modules, functions, and unreachable code",
        "explanation": """
WHAT IT IS:
Dead code detection finds modules and functions that are never imported or
called anywhere in your codebase. It queries the database (not files) to
identify code that can be safely removed, reducing maintenance burden and
attack surface.

WHEN TO USE IT:
- After completing a refactoring to find orphaned code
- Before major releases to reduce bundle size and complexity
- During code reviews to verify removed features are fully deleted
- In CI/CD to prevent accumulating unused code over time
- After removing a feature to find all related dead code

HOW TO USE IT:
PREREQUISITES:
    aud full                              # Build database first (required)

STEPS:
    1. Run dead code detection:
       aud deadcode                       # Find all dead code

    2. Review findings by confidence level:
       - HIGH: Definitely unused, safe to delete
       - MEDIUM: Might be entry point or test, verify manually
       - LOW: Likely false positive (empty __init__.py, generated)

    3. For each HIGH confidence finding, verify and delete:
       aud explain <file>                 # Check for hidden usage
       git rm <file>                      # Remove if truly dead

EXAMPLE - Cleaning Up After Refactoring:
    aud full && aud deadcode --path-filter 'src/%'
    # Shows: src/old_auth.py [HIGH] - 0 imports, 5 functions
    # Action: Verify not used, then delete

COMBINING WITH OTHER TOOLS:
- Before deadcode: Run aud full to ensure fresh database
- After deadcode: Use aud explain <file> to verify findings
- With refactor: Run aud refactor first to find incomplete migrations
- In CI/CD: Use --fail-on-dead-code to block PRs adding dead code

AGENT WORKFLOW:
The refactor agent (/theauditor:refactor) runs aud deadcode in Phase 1
to verify files are actively used before analyzing for refactoring.
If deadcode shows [HIGH] confidence unused, the agent flags for cleanup
rather than refactoring.

CONFIDENCE LEVELS:
- HIGH: Regular module with symbols, never imported, not special file
- MEDIUM: Entry point, test file, or script (might be invoked externally)
- LOW: Empty __init__.py, generated code (false positive likely)

WHAT IT DETECTS:
- Isolated Modules: Files with code never imported anywhere
- Dead Functions: Functions defined but never called
- Orphaned Features: Entire features implemented but never integrated

COMMAND OPTIONS:
    aud deadcode                              # Find all dead code
    aud deadcode --path-filter 'src/%'        # Specific directory only
    aud deadcode --exclude 'test/%'           # Skip test files
    aud deadcode --fail-on-dead-code          # Exit 1 if dead code found
    aud deadcode --format json                # Machine-readable output
    aud deadcode --format summary             # Counts only

RELATED:
Commands: aud deadcode, aud refactor, aud graph analyze, aud explain
Topics: aud manual refactor, aud manual graph, aud manual impact

COMMON MISTAKES:
- Running before aud full: No database means no analysis
  -> Always run aud full first to populate symbols and refs tables
- Deleting MEDIUM confidence files: These might be CLI entry points
  -> Verify with aud explain or grep for external invocations
- Ignoring deadcode in CI: Technical debt accumulates silently
  -> Add aud deadcode --fail-on-dead-code to CI pipeline

EXIT CODES:
- 0: Success (no dead code, or dead code found but --fail-on-dead-code not set)
- 1: Dead code found AND --fail-on-dead-code flag set
- 2: Error (database missing or query failed)
""",
    },
    "session": {
        "title": "AI Agent Session Analysis",
        "summary": "Analyze Claude Code and AI agent sessions for quality and ML training",
        "explanation": """
Session analysis parses and analyzes AI agent interaction logs to extract
metrics, detect patterns, and store data for machine learning. Supports
Claude Code, Codex, and other AI coding assistants.

WHEN TO USE IT:
- After completing a complex coding session to measure efficiency
- Building training data for ML models (aud learn)
- Diagnosing why an agent session was slow or expensive
- Comparing agent performance across different projects

PREREQUISITES:
- AI agent session logs must exist in standard locations
- Claude Code: ~/.claude/projects/<project-name>/
- Codex: ~/.codex/sessions/
- Or specify custom path with --session-dir

SESSION LOCATIONS:
  Claude Code:  ~/.claude/projects/<project-name>/
  Codex:        ~/.codex/sessions/

AUTO-DETECTION:
TheAuditor automatically finds sessions based on your current working
directory. If you're in a project, it looks for matching sessions.

ACTIVITY CLASSIFICATION:
Sessions are analyzed by classifying each AI turn into:

  PLANNING (no tools, substantial text):
    Discussion of approach, design decisions, clarifications

  WORKING (Edit, Write, Bash):
    Actual code changes and system commands

  RESEARCH (Read, Grep, Glob, Task):
    Information gathering and codebase exploration

  CONVERSATION (short exchanges):
    Quick Q&A, confirmations, clarifications

EFFICIENCY METRICS:
  Work/Talk ratio:     Working tokens / (Planning + Conversation tokens)
                       Higher = more productive

  Research/Work ratio: Research tokens / Working tokens
                       Lower = less thrashing

  Tokens per edit:     Total tokens / Number of edits
                       Lower = more efficient

INTERPRETATION GUIDELINES:
  >50% working tokens:  Highly productive session
  30-50% working:       Balanced planning and execution
  <30% working:         High overhead - consider improving prompts

ML DATABASE:
Session data is stored in .pf/ml/session_history.db for:
- Training ML models on your coding patterns
- Generating suggestions based on similar sessions
- Long-term trend analysis

COMBINING WITH OTHER TOOLS:
  Session + ML Training:
    aud session analyze                  # Parse and store session data
    aud learn --session-analysis         # Train with agent behavior features
    aud suggest --print-plan             # Get predictions using session patterns

  Session + Audit Comparison:
    aud session activity --limit 10      # See recent session efficiency
    aud full && aud fce                  # Compare: agent work vs audit findings

USE THE COMMANDS:
    aud session list                    # Find available sessions
    aud session analyze                 # Store to ML database
    aud session inspect session.jsonl   # Deep dive on one session
    aud session activity --limit 20     # Check efficiency trends
    aud session report --limit 5        # Aggregate findings

COMMON MISTAKES:
- Running analyze on empty session directory (no data found)
- Expecting sessions from different projects to auto-merge (they don't)
- Not running 'aud session analyze' before 'aud learn' (no training data)
- Confusing session efficiency with code quality (separate concerns)

RELATED COMMANDS:
    aud learn      Train ML on session data
    aud suggest    Get suggestions from learned patterns
    aud manual ml  Understand machine learning system
""",
    },
}
