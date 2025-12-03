"""Manual library part 2: Advanced concepts (boundaries through session)."""

EXPLANATIONS_02: dict[str, dict[str, str]] = {
    "boundaries": {
        "title": "Security Boundary Analysis",
        "summary": "Measure distance from entry points to security controls",
        "explanation": """
Boundary analysis measures WHERE security controls (validation, authentication,
sanitization) are enforced relative to entry points (HTTP routes, CLI commands).
It reports factual distance measurements - how many function calls between where
external data enters and where it gets validated.

KEY CONCEPTS:

Boundary:
  A point where trust level changes (external->internal, untrusted->validated).
  Security controls should enforce boundaries at or near entry points.

Distance:
  Number of function calls between entry point and control point.
  - Distance 0: Control at entry (validation in function signature)
  - Distance 1-2: Control nearby (acceptable)
  - Distance 3+: Control far from entry (data spreads before enforcement)
  - Distance None: No control found (missing boundary enforcement)

Entry Point:
  Where external data enters your application:
  - HTTP routes (GET /api/users)
  - CLI commands
  - Message queue handlers
  - Websocket handlers

Control Point:
  Where security enforcement happens:
  - Input validation (validate(), parse(), sanitize())
  - Authentication checks (@requires_auth, req.user)
  - Authorization checks (check_permission())
  - Output encoding (HTML escaping, parameterized queries)

BOUNDARY QUALITY LEVELS:

  clear: Single control at distance 0
    Example: @validate_body decorator on route handler
    Meaning: Validation happens before any application code runs

  acceptable: Single control at distance 1-2
    Example: validate(req.body) called at start of handler
    Meaning: Validation happens early, minimal unvalidated code paths

  fuzzy: Multiple controls OR distance 3+
    Example: Different validation in 3 different code paths
    Meaning: Boundary enforcement is scattered or inconsistent

  missing: No control found
    Example: User input flows directly to database query
    Meaning: No boundary enforcement detected

WHY DISTANCE MATTERS:

Every function call between entry and validation is a place where:
- Unvalidated data could be used incorrectly
- Additional code paths branch off without validation
- Side effects could occur before validation rejects bad input

Example - Distance 3 Problem:
  POST /api/users -> createUser() -> processUser() -> saveUser() -> validate()

  If validate() rejects the input at distance 3:
  - createUser() already ran (maybe logged something)
  - processUser() already ran (maybe sent a notification)
  - saveUser() might have started a transaction

  The data spread through 3 functions before validation.

MULTI-TENANT SECURITY (Critical):

For SaaS applications, tenant isolation is crucial:
  - Every query on tenant-sensitive tables MUST filter by tenant_id
  - tenant_id MUST come from authenticated session, NOT user input
  - Validation distance from auth to query should be minimal

Example Violation:
  app.get('/api/docs/:id', auth, (req, res) => {
    // Distance to tenant check: 2 (after DB access - TOO LATE)
    const doc = db.query('SELECT * FROM docs WHERE id=?', [req.params.id]);
    if (doc.tenant_id !== req.user.tenantId) return 403;
  })

Correct Pattern:
  app.get('/api/docs/:id', auth, (req, res) => {
    // Distance 0 - tenant filter in query itself
    const doc = db.query('SELECT * FROM docs WHERE id=? AND tenant_id=?',
                         [req.params.id, req.user.tenantId]);
  })

USE THE COMMAND:
    aud boundaries                           # Analyze all boundary types
    aud boundaries --type input-validation   # Focus on input validation
    aud boundaries --type multi-tenant       # Focus on tenant isolation
    aud boundaries --format json             # Machine-parseable output
    aud boundaries --severity critical       # Only critical findings

RELATED CONCEPTS:
    aud manual taint       # Data flow tracking (complements boundaries)
    aud manual patterns    # Pattern detection for security rules
""",
    },
    "docker": {
        "title": "Docker Security Analysis",
        "summary": "Detect container misconfigurations, secrets, and vulnerable base images",
        "explanation": """
Docker security analysis examines Dockerfiles and container configurations
for common security mistakes that can lead to privilege escalation, secret
exposure, or vulnerable deployments.

THE SECURITY RISKS:

Running as Root:
  Containers default to running as the root user. If an attacker escapes
  the container, they have root privileges on the host. Always add:
    USER nonroot
  before ENTRYPOINT/CMD.

Exposed Secrets:
  ENV and ARG instructions are stored in image layers and can be extracted.
  NEVER put secrets in Dockerfiles - use runtime injection instead:
    BAD:  ENV API_KEY=sk_live_abc123
    GOOD: Runtime: docker run -e API_KEY=$API_KEY ...

Unpinned Base Images:
  Using 'latest' tag means builds are non-deterministic. A base image
  update can break your build or introduce vulnerabilities:
    BAD:  FROM node:latest
    GOOD: FROM node:20.10.0@sha256:abc123...

Outdated Base Images:
  Old base images contain known CVEs. TheAuditor checks image versions
  and can query vulnerability databases for known issues.

WHAT THEAUDITOR DETECTS:

Privilege Issues:
  - Missing USER instruction (defaults to root)
  - Explicit USER root
  - SUDO usage in RUN commands
  - --cap-add flags that escalate privileges

Secret Exposure:
  - High-entropy ENV/ARG values (likely secrets)
  - Hardcoded credentials (passwords, API keys, tokens)
  - Private keys copied into images (.pem, .key)
  - AWS credentials or GitHub tokens

Base Image Problems:
  - 'latest' tag usage
  - Outdated versions (Alpine <3.14, Ubuntu <20.04)
  - Missing digest pinning
  - Known CVEs (with --check-vulns)

Hardening Failures:
  - Missing HEALTHCHECK instruction
  - Exposed privileged ports (<1024)
  - World-writable permissions (chmod 777)
  - apt-get/apk without --no-cache

SEVERITY LEVELS:

CRITICAL:
  - Hardcoded secrets in ENV/ARG
  - Known CVEs in base image (with --check-vulns)
  - Private key material in image

HIGH:
  - Running as root without explicit USER
  - SUDO installation or usage
  - Capability escalations (--cap-add)

MEDIUM:
  - Missing HEALTHCHECK
  - Outdated base image version
  - 'latest' tag usage

LOW:
  - World-writable permissions
  - apt/apk cache not cleared
  - Non-optimal instruction ordering

DOCKERFILE BEST PRACTICES:

Minimal Structure:
  FROM node:20.10.0@sha256:abc123
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci --only=production
  COPY . .
  USER node
  HEALTHCHECK CMD curl -f http://localhost:3000/health || exit 1
  CMD ["node", "server.js"]

Key Points:
  - Pin base image with digest
  - Copy dependency files first (layer caching)
  - Use USER instruction before ENTRYPOINT/CMD
  - Add HEALTHCHECK for orchestration
  - Run as non-root user

MULTI-STAGE BUILDS:

Reduce attack surface with multi-stage builds:
  # Build stage
  FROM node:20 AS builder
  WORKDIR /app
  COPY . .
  RUN npm ci && npm run build

  # Production stage (smaller, fewer vulnerabilities)
  FROM node:20-alpine
  WORKDIR /app
  COPY --from=builder /app/dist ./dist
  USER node
  CMD ["node", "dist/server.js"]

USE THE COMMAND:
    aud docker-analyze                        # Full analysis
    aud docker-analyze --no-check-vulns       # Skip vulnerability checks
    aud docker-analyze --severity critical    # Only critical issues
    aud docker-analyze --output results.json  # Export findings

RELATED CONCEPTS:
    aud manual patterns    # Pattern detection system
    aud manual severity    # Severity classification
""",
    },
    "lint": {
        "title": "Code Linting and Static Analysis",
        "summary": "Run and normalize output from multiple linters across languages",
        "explanation": """
The lint command orchestrates multiple industry-standard linters across your
codebase and normalizes their output into a unified format. This enables
consistent code quality analysis regardless of language mix.

WHAT LINTING DOES:

Linting is automated static analysis that catches:
- Syntax errors (code that won't run)
- Type errors (wrong types passed to functions)
- Style violations (inconsistent formatting)
- Best practice violations (deprecated patterns)
- Security issues (potential vulnerabilities)
- Dead code (unreachable code paths)

WHY NORMALIZE OUTPUT:

Different linters have different output formats:
- ESLint outputs JSON arrays
- Ruff outputs SARIF format
- Mypy outputs plain text
- Pylint outputs custom format

TheAuditor normalizes all output to a unified format:
  {
    "file": "src/auth.py",
    "line": 42,
    "column": 10,
    "severity": "error",
    "rule": "undefined-var",
    "message": "Variable 'user' is not defined",
    "tool": "eslint"
  }

This enables:
- Unified reporting across languages
- Consistent severity classification
- Centralized findings database
- Cross-tool correlation (via FCE)

SUPPORTED LINTERS:

Python:
  - ruff: Fast, comprehensive (recommended)
  - mypy: Static type checking
  - black: Code formatting (check mode)
  - pylint: Classic linter
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

TheAuditor automatically detects which linters are available:
1. Checks system PATH
2. Checks node_modules/.bin (for JS tools)
3. Checks .auditor_venv (sandbox installation)

Only runs linters that are actually installed.

WORKSET MODE:

For large codebases, lint everything is slow. Use workset mode:

  # Identify changed files
  aud workset --diff HEAD~1

  # Lint only changed files
  aud lint --workset

This reduces lint time from minutes to seconds.

SEVERITY MAPPING:

Linter output is normalized to three levels:
  error:   Must fix (code won't work correctly)
  warning: Should fix (best practice violation)
  info:    Consider fixing (style/preference)

COMMON WORKFLOWS:

Development Cycle:
  1. Make changes to code
  2. aud workset --diff HEAD~1
  3. aud lint --workset
  4. Fix errors, commit

CI/CD Pipeline:
  aud lint || exit 1  # Fail on linter errors

Pre-commit Hook:
  aud workset --diff --cached && aud lint --workset

USE THE COMMAND:
    aud lint                     # Lint entire codebase
    aud lint --workset           # Lint only changed files
    aud lint --print-plan        # Preview without running
    aud lint --timeout 600       # Increase timeout

RELATED CONCEPTS:
    aud manual workset   # Targeted file selection
    aud manual patterns  # Pattern-based security rules
""",
    },
    "frameworks": {
        "title": "Framework Detection",
        "summary": "Identify frameworks and libraries used in your project",
        "explanation": """
Framework detection identifies the programming frameworks, libraries, and
tools used in your project. This information is essential for:
- Understanding the technology stack
- Identifying framework-specific vulnerabilities
- Generating appropriate security rules
- Architecture documentation

HOW DETECTION WORKS:

TheAuditor detects frameworks through multiple methods:

1. Package Manifests:
   - package.json (Node.js/JavaScript)
   - requirements.txt (Python)
   - pyproject.toml (Python)
   - Cargo.toml (Rust)
   - go.mod (Go)
   - pom.xml (Java/Maven)

2. Import Statements:
   - Python: from flask import Flask
   - JavaScript: import React from 'react'
   - TypeScript: import { Express } from 'express'

3. Configuration Files:
   - jest.config.js (Jest testing framework)
   - pytest.ini (.pytest.ini) (pytest)
   - webpack.config.js (Webpack)
   - tsconfig.json (TypeScript)

4. Decorator Patterns:
   - @app.route() (Flask)
   - @pytest.fixture (pytest)
   - @Component() (Angular)

DETECTED FRAMEWORKS BY CATEGORY:

Web Frameworks:
  Python: Flask, Django, FastAPI, Starlette
  JavaScript: Express, Nest.js, Koa, Hapi
  Frontend: React, Vue, Angular, Svelte

Database:
  ORMs: SQLAlchemy, Django ORM, Prisma, TypeORM
  Clients: psycopg2, mysql-connector, pymongo

Testing:
  Python: pytest, unittest, nose
  JavaScript: Jest, Mocha, Jasmine

Build Tools:
  JavaScript: Webpack, Vite, Rollup, esbuild
  Python: setuptools, poetry, hatch

Cloud SDKs:
  AWS: boto3, @aws-sdk/*
  GCP: google-cloud-*, @google-cloud/*
  Azure: azure-*, @azure/*

WHY FRAMEWORK DETECTION MATTERS:

Security Perspective:
  - Different frameworks have different security patterns
  - Framework-specific vulnerabilities (e.g., Django CSRF, Express XSS)
  - Security rules are tailored to detected frameworks
  - Dependency vulnerabilities are framework-aware

Architecture Understanding:
  - Quickly understand a new codebase
  - Identify technology decisions
  - Document the tech stack

PRIMARY VS SECONDARY FRAMEWORKS:

Primary frameworks (is_primary=true):
  - Core application frameworks (Flask, React, Express)
  - Directly shape application architecture

Secondary frameworks (is_primary=false):
  - Utility libraries (lodash, requests)
  - Development dependencies (prettier, eslint)

DATABASE STORAGE:

Framework data is stored in repo_index.db:
  CREATE TABLE frameworks (
    name TEXT,
    version TEXT,
    language TEXT,
    path TEXT,      -- Where detected
    source TEXT,    -- manifest, import, config
    is_primary INTEGER
  )

USE THE COMMAND:
    aud detect-frameworks              # Display detected frameworks
    aud detect-frameworks --output-json ./stack.json  # Export to file
    aud blueprint --structure          # See frameworks in architecture view

RELATED CONCEPTS:
    aud manual deps     # Dependency vulnerability scanning
    aud manual patterns # Framework-specific security patterns
""",
    },
    "docs": {
        "title": "External Documentation Caching",
        "summary": "Fetch, cache, and summarize library documentation for AI context",
        "explanation": """
The docs command fetches README files and API documentation from package
repositories, caches them locally for offline use, and generates condensed
"documentation capsules" optimized for LLM context windows.

WHY DOCUMENTATION CACHING:

When AI assistants analyze code using external libraries, they need to
understand library APIs. Without documentation:
- AI makes assumptions about function signatures
- Incorrect usage patterns are suggested
- Security implications are missed

Documentation caching solves this by:
- Fetching official README files from package registries
- Caching locally for offline/air-gapped environments
- Generating AI-optimized summaries (<10KB per package)
- Providing context without network access during analysis

HOW IT WORKS:

1. Dependency Detection (prerequisite):
   'aud deps' analyzes package.json, requirements.txt, etc.
   Output: .pf/deps.json with list of all dependencies

2. Documentation Fetch:
   'aud docs fetch' queries PyPI/npm for package metadata
   Downloads README from GitHub/GitLab (allowlisted sources)
   Caches raw markdown in .pf/context/docs/<package>.md

3. Documentation Summarization:
   'aud docs summarize' processes raw markdown
   Extracts: API signatures, usage examples, common patterns
   Filters: badges, contributor lists, build instructions
   Output: .pf/context/doc_capsules/<package>.json

SECURITY CONSIDERATIONS:

By default, documentation is only fetched from allowlisted sources:
- GitHub (github.com)
- GitLab (gitlab.com)
- Official registries (pypi.org, npmjs.com)

This prevents:
- Malicious packages injecting content
- Arbitrary code execution from untrusted sources
- Supply chain attacks via documentation

The --allow-non-gh-readmes flag bypasses this (USE WITH CAUTION).

DOCUMENTATION CAPSULE FORMAT:

Capsules are JSON files optimized for AI consumption:
{
  "package": "requests",
  "version": "2.31.0",
  "summary": "HTTP library for Python",
  "key_apis": [
    "requests.get(url, params=None, **kwargs)",
    "requests.post(url, data=None, json=None, **kwargs)",
    "Response.json() -> dict"
  ],
  "common_patterns": [
    "response = requests.get(url)",
    "if response.ok: data = response.json()"
  ],
  "documentation_url": "https://requests.readthedocs.io"
}

OFFLINE MODE:

After initial fetch, all documentation is cached locally:
- No network access needed for analysis
- Works in air-gapped environments
- Cache persists across sessions

To refresh: re-run 'aud docs fetch' after dependency updates.

TYPICAL WORKFLOW:

Initial Setup (with network):
  aud deps                    # Detect dependencies
  aud docs fetch              # Download documentation
  aud docs summarize          # Generate capsules

Offline Development:
  aud docs view <package>     # View cached docs
  aud docs list               # See what's available

After Dependency Changes:
  aud deps                    # Update dependency list
  aud docs fetch              # Fetch new docs only

USE THE COMMANDS:
    aud docs fetch                       # Download all dependency docs
    aud docs fetch --offline             # Use cache only
    aud docs summarize                   # Generate AI capsules
    aud docs view requests               # View package docs
    aud docs view requests --raw         # View raw README
    aud docs list                        # List cached packages

RELATED CONCEPTS:
    aud manual deps        # Dependency detection
    aud manual frameworks  # Framework identification
""",
    },
    "rules": {
        "title": "Detection Rules and Patterns",
        "summary": "Security rules, vulnerability patterns, and code quality checks",
        "explanation": """
TheAuditor uses a layered rule system to detect security vulnerabilities,
code quality issues, and framework-specific patterns. Rules come from two
sources: YAML pattern files and Python AST rules.

RULE ARCHITECTURE:

Two complementary detection mechanisms:

1. YAML Pattern Files (regex-based):
   - Fast, declarative pattern matching
   - Good for: string patterns, secret detection, known-bad patterns
   - Location: theauditor/patterns/*.yml
   - Format: List of patterns with name, regex, severity

2. Python AST Rules (semantic analysis):
   - Deep code understanding via AST parsing
   - Good for: dataflow, control flow, semantic patterns
   - Location: theauditor/rules/*.py
   - Format: Functions named find_* that analyze AST

PATTERN FILE FORMAT:

YAML patterns follow this structure:
- name: hardcoded_api_key
  pattern: "(api_key|apikey)\\s*=\\s*['\"][^'\"]{20,}['\"]"
  severity: high
  message: Hardcoded API key detected
  remediation: Use environment variables or secrets manager
  cwe: CWE-798  # Use of Hard-coded Credentials
  categories:
    - secrets
    - authentication

PATTERN CATEGORIES:

Injection Attacks:
  - sql_injection: Unparameterized SQL queries
  - command_injection: Shell command construction
  - ldap_injection: LDAP query construction
  - nosql_injection: MongoDB/Redis query patterns

Authentication:
  - hardcoded_credentials: Passwords, API keys in source
  - weak_password_patterns: Minimum length, complexity
  - jwt_vulnerabilities: None algorithm, weak secrets

Data Security:
  - pii_exposure: SSN, credit card, email patterns
  - weak_crypto: MD5, SHA1, DES usage
  - insecure_random: Math.random() for security

Framework-Specific:
  - django_csrf: Missing CSRF protection
  - flask_debug: Debug mode in production
  - react_dangerouslySetInnerHTML: XSS via innerHTML

PYTHON AST RULE FORMAT:

Python rules analyze the AST directly:

def find_sql_injection(ast_data: dict) -> list[Finding]:
    '''Detect SQL injection vulnerabilities.'''
    findings = []
    for call in ast_data.get('function_calls', []):
        if call['name'] in SQL_EXECUTE_FUNCTIONS:
            if has_string_concat_arg(call):
                findings.append(Finding(
                    rule='sql_injection',
                    severity='critical',
                    file=call['file'],
                    line=call['line'],
                    message='SQL query built with string concatenation'
                ))
    return findings

AST rules have access to:
- function_calls: All function/method calls
- assignments: Variable assignments
- imports: Import statements
- symbols: Classes, functions, variables
- control_flow: If/else, loops, try/except

SEVERITY LEVELS:

critical: Immediate exploitation risk (RCE, SQLi, auth bypass)
high:     Significant risk (XSS, SSRF, information disclosure)
medium:   Moderate risk (weak crypto, missing headers)
low:      Code quality (complexity, naming conventions)

CUSTOM PATTERNS:

Add custom patterns to theauditor/patterns/custom.yml:

- name: internal_api_endpoint
  pattern: "api\\.internal\\."
  severity: medium
  message: Internal API call detected
  categories:
    - custom
    - api

Run 'aud rules --summary' to verify registration.

USE THE COMMANDS:
    aud rules --summary           # Generate capability report
    aud detect-patterns           # Run all patterns on codebase
    aud detect-patterns --type injection  # Specific category

RELATED CONCEPTS:
    aud manual patterns   # Pattern detection fundamentals
    aud manual taint      # Dataflow-based detection
""",
    },
    "setup": {
        "title": "Sandboxed Analysis Environment",
        "summary": "Create isolated environment with offline vulnerability scanning",
        "explanation": """
The setup-ai command creates a completely isolated analysis environment
with its own Python virtual environment, JavaScript tools, and offline
vulnerability databases. This enables reproducible, air-gapped security
analysis.

WHY SANDBOXED ENVIRONMENT:

Standard analysis tools often:
- Conflict with project dependencies (version mismatches)
- Require internet access (rate limits, API keys)
- Pollute the global system (installed globally)
- Cannot be used in air-gapped environments

The sandboxed environment solves all these:
- Isolated Python venv (no conflicts)
- Isolated node_modules (no npm conflicts)
- Offline vulnerability databases (no network needed)
- Self-contained (portable between projects)

WHAT GETS INSTALLED:

Python Environment (.auditor_venv/):
  - TheAuditor (editable install)
  - ruff, mypy, black (Python linters)
  - All TheAuditor dependencies
  - Isolated from project and system

JavaScript Tools (.auditor_tools/):
  - ESLint with TypeScript support
  - Prettier code formatter
  - TypeScript compiler
  - Isolated from project node_modules

Vulnerability Databases (.auditor_venv/vuln_cache/):
  - npm advisory database (~300MB)
  - PyPI advisory database (~200MB)
  - Refreshes every 30 days

DIRECTORY STRUCTURE:

<project>/
  .auditor_venv/                   # Sandboxed Python
    bin/                           # Executables
      aud                          # TheAuditor CLI
      python                       # Isolated Python
    lib/                           # Python packages
    vuln_cache/                    # Offline databases
      npm/                         # npm advisories
      pypi/                        # PyPI advisories
    .theauditor_tools/             # JavaScript tools
      node_modules/                # Isolated npm packages

OFFLINE VULNERABILITY SCANNING:

After setup, vulnerability scanning works offline:

1. OSV-Scanner binary downloads advisories once
2. Databases cached in vuln_cache/
3. 'aud deps --vuln-scan' uses local databases
4. No network requests during analysis
5. Refresh with 'aud setup-ai --sync'

This enables:
- Air-gapped security audits
- Reproducible results (same database = same findings)
- No rate limiting or API quotas
- Fast scans (local lookups only)

MULTI-PROJECT USAGE:

Each project gets its own sandbox:
  ~/project-a/.auditor_venv/
  ~/project-b/.auditor_venv/

Or share one sandbox across projects:
  ~/.auditor_global/   # Create in home directory
  # Reference from any project

TYPICAL WORKFLOW:

Initial Setup (once per project):
  cd /path/to/project
  aud setup-ai --target .    # ~5-10 minutes

Daily Development:
  aud init                   # Uses sandboxed tools
  aud full                   # Runs analysis
  aud deps --vuln-scan       # Offline vulnerability scan

Periodic Refresh:
  aud setup-ai --target . --sync   # Update databases

USE THE COMMAND:
    aud setup-ai --target .              # Setup current directory
    aud setup-ai --target . --sync       # Force update
    aud setup-ai --target . --dry-run    # Preview plan
    aud setup-ai --target . --show-versions  # Check installed tools

RELATED CONCEPTS:
    aud manual tools   # Tool detection and management
    aud manual deps    # Dependency and vulnerability analysis
""",
    },
    "ml": {
        "title": "Machine Learning Risk Prediction",
        "summary": "Train models to predict file risk and root cause likelihood from audit history",
        "explanation": """
TheAuditor's ML system learns patterns from historical audit runs to predict
which files are most likely to contain vulnerabilities. This enables proactive
risk assessment - analyze high-risk files first for faster issue discovery.

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

KEY BENEFITS:
- Verification specs query actual code (not developer self-assessment)
- Git snapshots create immutable audit trail
- Zero external dependencies (offline-first)
- Works seamlessly with aud index / aud full workflow

DATABASE STRUCTURE:
  .pf/planning.db (separate from repo_index.db)
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
    5. aud index && aud planning verify-task 1 1

  Refactoring Migration:
    1. aud planning init --name "Auth0 to Cognito"
    2. aud planning add-task 1 --title "Migrate routes" --spec auth_spec.yaml
    3. [Make changes]
    4. aud index && aud planning verify-task 1 1 --auto-update
    5. aud planning archive 1 --notes "Deployed to prod"

  Checkpoint-Driven Development:
    1. aud planning add-task 1 --title "Complex Refactor"
    2. [Make partial changes]
    3. aud planning checkpoint 1 1 --name "step-1"
    4. [Continue work]
    5. aud planning show-diff 1 1  # View all checkpoints
    6. aud planning rewind 1 1 --to 2  # Rollback if needed

SUBCOMMANDS:
  init         Create new plan (auto-creates planning.db)
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

USE THE COMMANDS:
    aud planning init --name "Migration Plan"
    aud planning add-task 1 --title "Task" --spec spec.yaml
    aud index && aud planning verify-task 1 1 --verbose
    aud planning show 1 --format phases
""",
    },
    "terraform": {
        "title": "Terraform IaC Security Analysis",
        "summary": "Infrastructure-as-Code security analysis for Terraform configurations",
        "explanation": """
TheAuditor provides comprehensive Terraform analysis for detecting infrastructure
security misconfigurations before they reach production. Analyzes .tf files to
find public exposure, missing encryption, and overly permissive IAM policies.

WHAT IT DETECTS:

  Public Exposure:
    - S3 buckets with public access
    - Security groups allowing 0.0.0.0/0
    - Databases with public accessibility enabled
    - Unprotected ALB/NLB listeners

  IAM & Permissions:
    - Wildcard (*) permissions in IAM policies
    - Overly permissive role trust policies
    - Missing condition constraints
    - Cross-account access risks

  Encryption:
    - Unencrypted S3 buckets, EBS volumes, RDS instances
    - Missing SSL/TLS for data in transit
    - Weak encryption algorithms

  Secrets:
    - Hardcoded credentials in resource definitions
    - Exposed API keys and tokens
    - Database passwords in plaintext

PROVISIONING GRAPH:
The provision command builds a data flow graph showing:
  - Variable -> Resource -> Output connections
  - Resource dependency chains
  - Sensitive data propagation paths
  - Public exposure blast radius

SUBCOMMANDS:
  provision  Build provisioning flow graph (var->resource->output)
  analyze    Run security rules on Terraform configurations
  report     Generate consolidated infrastructure security report

TYPICAL WORKFLOW:
    # 1. Index your Terraform files
    aud full --index

    # 2. Build provisioning graph
    aud terraform provision

    # 3. Run security analysis
    aud terraform analyze

    # 4. Review findings
    cat .pf/raw/terraform_findings.json

OUTPUT FILES:
    .pf/raw/terraform_graph.json      # Provisioning flow graph
    .pf/raw/terraform_findings.json   # Security findings
    .pf/graphs.db                     # Graph stored for querying

USE THE COMMANDS:
    aud terraform provision
    aud terraform analyze --severity critical
    aud terraform analyze --categories public_exposure
""",
    },
    "tools": {
        "title": "Analysis Tool Dependencies",
        "summary": "Manage and verify installed analysis tools (linters, scanners, runtimes)",
        "explanation": """
TheAuditor uses multiple external tools for comprehensive code analysis. The tools
command group helps detect, verify, and report on these dependencies.

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
  report  Generate version report files (.pf/raw/tools.json)

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

USE THE COMMANDS:
    aud tools                          # List all tools
    aud tools list --json              # JSON output
    aud tools check                    # Verify core tools
    aud tools check --strict           # All tools required
    aud tools check --required semgrep # Require specific tool
    aud tools report                   # Generate .pf/raw/tools.json
""",
    },
    "metadata": {
        "title": "Temporal and Quality Metadata Collection",
        "summary": "Git churn and test coverage metrics for risk correlation",
        "explanation": """
The metadata command group collects temporal and quality facts about your codebase
for use in FCE (Feed-forward Correlation Engine) risk analysis. It answers: "What
files change frequently?" and "What code is poorly tested?"

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

OUTPUT FILES:
    .pf/raw/churn_analysis.json     # Git churn data
    .pf/raw/coverage_analysis.json  # Test coverage data
""",
    },
    "cdk": {
        "title": "AWS CDK Infrastructure-as-Code Security",
        "summary": "Security analysis for AWS CDK Python/TypeScript/JavaScript code",
        "explanation": """
TheAuditor provides security analysis for AWS Cloud Development Kit (CDK) code,
detecting infrastructure misconfigurations before deployment to AWS. Supports
CDK written in Python, TypeScript, and JavaScript.

WHAT CDK IS:

AWS CDK (Cloud Development Kit) lets you define AWS infrastructure using
programming languages instead of YAML/JSON templates. TheAuditor analyzes
CDK code to find security issues BEFORE deployment.

Example CDK code (Python):
    bucket = s3.Bucket(
        self, "MyBucket",
        public_read_access=True,     # <-- TheAuditor flags this
        encryption=s3.BucketEncryption.UNENCRYPTED  # <-- And this
    )

SECURITY CHECKS:

  S3 Buckets:
    - public_read_access=True (data exposure)
    - Missing block_public_access configuration
    - BucketEncryption.UNENCRYPTED (compliance violation)

  Databases (RDS/DynamoDB):
    - publicly_accessible=True
    - storage_encrypted=False
    - Missing backup retention

  IAM:
    - PolicyStatement with "*" actions
    - ManagedPolicy.fromAwsManagedPolicyName overprivilege
    - Principal.Account("*") (cross-account risk)

  Network:
    - SecurityGroup with all traffic allowed
    - VPC missing NAT for private subnets
    - Public subnets hosting sensitive resources

HOW IT WORKS:

1. 'aud index' parses CDK code (AST extraction)
2. Extracts CDK constructs to cdk_constructs table
3. 'aud cdk analyze' runs security rules
4. Writes findings to cdk_findings table
5. Returns exit code based on severity

EXIT CODES:
  0 = No security issues
  1 = Security issues detected
  2 = Critical security issues
  3 = Analysis failed

TYPICAL WORKFLOW:
    # 1. Index your CDK project
    aud full --index

    # 2. Run security analysis
    aud cdk analyze

    # 3. Query findings from database
    sqlite3 .pf/repo_index.db "SELECT * FROM cdk_findings"

COMPARISON WITH TERRAFORM:
  CDK: Programming languages (Python, TS, JS)
  Terraform: HCL configuration files (.tf)

  Use 'aud cdk' for CDK projects
  Use 'aud terraform' for Terraform projects

USE THE COMMANDS:
    aud cdk analyze                    # Full analysis
    aud cdk analyze --severity high    # High+ only
    aud cdk analyze --format json      # JSON output

RELATED COMMANDS:
    aud terraform    # Terraform IaC analysis
    aud detect-patterns  # Includes CDK security rules
""",
    },
    "graphql": {
        "title": "GraphQL Schema and Resolver Analysis",
        "summary": "Map GraphQL SDL schemas to backend resolver implementations",
        "explanation": """
TheAuditor provides GraphQL schema analysis, mapping SDL type definitions to
backend resolver functions. This enables security analysis and taint tracking
through the GraphQL execution layer.

WHAT THIS DOES:

GraphQL APIs separate schema (what clients see) from resolvers (what runs).
TheAuditor correlates them:

  Schema (SDL):               Resolver (Code):
  type Query {                @Query()
    user(id: ID!): User  -->  resolve_user(id):
  }                             return db.get_user(id)

This enables:
- Finding fields without resolver implementations
- Tracing data flow from GraphQL arguments to database
- Detecting N+1 query patterns
- Security analysis of resolver implementations

HOW IT WORKS:

1. SDL Extraction (during 'aud index'):
   Parses .graphql/.gql files into graphql_types and graphql_fields tables

2. Resolver Detection:
   Finds resolver patterns by framework:
   - Graphene: resolve_<field> methods
   - Ariadne: @query.field("name") decorators
   - Strawberry: @strawberry.field on methods
   - Apollo/NestJS: @Query()/@Mutation() decorators

3. Correlation ('aud graphql build'):
   Matches fields to resolvers via naming + type analysis
   Stores in graphql_resolver_mappings table

4. Execution Graph:
   Builds field -> resolver -> downstream call edges
   Used by taint analysis for data flow tracking

SUBCOMMANDS:
  build   Correlate SDL with resolvers, build execution graph
  query   Query schema metadata (types, fields, resolvers)
  viz     Visualize schema and execution graph

TYPICAL WORKFLOW:
    # 1. Index the codebase (extracts SDL + resolver code)
    aud full --index

    # 2. Build resolver mappings
    aud graphql build

    # 3. Inspect schema
    aud graphql query --type Query --show-resolvers

    # 4. Use in taint analysis
    aud taint-analyze  # Uses GraphQL edges for data flow

FRAMEWORK SUPPORT:
  Python:     Graphene, Ariadne, Strawberry
  JavaScript: Apollo Server, TypeGraphQL
  TypeScript: NestJS GraphQL, TypeGraphQL

OUTPUT:
  Updates graphql_resolver_mappings table
  Updates graphql_execution_edges table
  Exports .pf/raw/graphql_schema.json
  Exports .pf/raw/graphql_execution.json

USE THE COMMANDS:
    aud graphql build                    # Build resolver mappings
    aud graphql build --verbose          # Show correlation details
    aud graphql query --type Query       # Inspect Query type
    aud graphql query --field user       # Find user field resolver
    aud graphql viz --output schema.svg  # Generate visualization

RELATED COMMANDS:
    aud taint-analyze  # Uses GraphQL edges for taint
    aud graph          # Generic call graph (GraphQL adds field layer)
""",
    },
    "blueprint": {
        "title": "Blueprint Command",
        "summary": "Architectural fact visualization with drill-down analysis modes",
        "explanation": """
The blueprint command provides a complete architectural overview of your indexed
codebase. It operates in "truth courier" mode - presenting pure facts with zero
recommendations or prescriptive language.

DRILL-DOWN MODES:
  (default):    Top-level overview with module counts and file organization
  --structure:  File organization, LOC counts, module boundaries
  --graph:      Import relationships, circular dependencies, hotspots
  --security:   JWT/OAuth usage, SQL queries, API endpoints
  --taint:      Taint sources/sinks, data flow paths
  --boundaries: Entry points and validation control distances
  --deps:       Package dependencies by manager (npm, pip, cargo)
  --all:        Export complete data as JSON

ADDITIONAL OPTIONS:
  --format text|json  Output format (default: text for visual tree)
  --monoliths         Find files exceeding line threshold (too large for AI)
  --threshold N       Line count threshold for monoliths (default: 2150)

WHAT IT SHOWS:
  Structure:
    - Files by directory and language
    - Symbol counts (functions, classes, variables)
    - File categories (source, test, scripts, migrations)

  Graph Analysis:
    - Hot files (high call counts)
    - Import graph statistics
    - Gateway files (bottlenecks)

  Security Surface:
    - JWT sign/verify locations
    - OAuth and password handling
    - SQL queries (total vs raw)
    - API endpoints (protected vs unprotected)

  Data Flow:
    - Taint sources (unique variables)
    - Cross-function flows
    - Taint paths detected

EXAMPLES:
    aud blueprint                        # Top-level overview
    aud blueprint --structure            # Drill into file organization
    aud blueprint --security             # Security surface facts
    aud blueprint --graph --format json  # Export graph data as JSON
    aud blueprint --all > arch.json      # Full export
    aud blueprint --monoliths            # Find oversized files
    aud blueprint --monoliths --threshold 1000  # Custom threshold

PERFORMANCE: 2-5 seconds (database queries + formatting)

PREREQUISITES:
    aud full    # Complete analysis (builds repo_index.db)

RELATED COMMANDS:
    aud graph     # Dedicated graph analysis
    aud explain   # File/symbol context
    aud query     # Direct database queries

NOTE: Blueprint shows FACTS ONLY - no recommendations, no "should be"
statements, no prescriptive language. For actionable insights, use
'aud fce' or 'aud full' with correlation rules.
""",
    },
    "refactor": {
        "title": "Refactoring Impact Analysis",
        "summary": "Detect incomplete refactorings from database schema migrations",
        "explanation": """
The refactor command detects code-schema mismatches from incomplete database
refactorings. It analyzes migration files to identify removed/renamed tables
and columns, then queries the codebase for references to deleted schema elements.

THE PROBLEM IT SOLVES:
When you run a database migration that drops a table or column, code that still
references that schema will break at runtime. This is the classic "forgot to
update the queries" problem that breaks production silently.

WHAT IT DETECTS:
  Schema Changes (from migrations):
    - Dropped tables (DROP TABLE, dropTable)
    - Dropped columns (ALTER TABLE DROP COLUMN, removeColumn)
    - Renamed tables (ALTER TABLE RENAME TO, renameTable)
    - Renamed columns (renameColumn)

  Code References (from repo_index.db):
    - SQL queries mentioning deleted tables/columns
    - ORM model references (SQLAlchemy, Django)
    - Raw SQL in string literals
    - Dynamic query builders

  Severity Classification:
    - CRITICAL: Code references deleted table (guaranteed break)
    - HIGH: Code references deleted column in existing table
    - MEDIUM: Code may reference renamed element (needs verification)

HOW IT WORKS:
  1. Parse migration files in --migration-dir
  2. Extract DROP/ALTER/RENAME statements
  3. Query repo_index.db for code referencing deleted schema
  4. Cross-reference and report breaking changes

OPTIONS:
  --migration-dir, -m   Directory containing migrations (default: backend/migrations)
  --migration-limit, -ml  Number of recent migrations to analyze (0=all, default=5)
  --file, -f            Refactor profile YAML describing schema expectations
  --output, -o          Output file for detailed report
  --in-file             Only scan files matching pattern (e.g., 'src/components')

EXAMPLES:
    aud refactor                          # Analyze last 5 migrations
    aud refactor --migration-limit 0      # Analyze ALL migrations
    aud refactor --migration-dir ./db     # Custom migration directory
    aud refactor --output report.json     # Export detailed report
    aud refactor --file profile.yaml      # Use refactor profile
    aud refactor --in-file OrderDetails   # Focus on specific file pattern

PERFORMANCE: 2-5 seconds (migration parsing + database queries)

PREREQUISITES:
    aud full    # Populates repo_index.db with code references

RELATED COMMANDS:
    aud impact  # Broader change impact analysis
    aud query   # Manual code search for schema elements

NOTE: Detects syntactic mismatches only. Schema changes affecting data types
or constraints may still cause runtime issues not detected by this command.
""",
    },
    "query": {
        "title": "Database Query Interface",
        "summary": "Direct SQL queries over indexed code relationships",
        "explanation": """
The query command provides direct access to TheAuditor's indexed code database.
It returns exact file:line locations for symbols, dependencies, and call chains.
No file reading, no parsing, no inference - just database lookups.

QUERY TARGETS (pick one):
  --symbol NAME       Function/class/variable lookup
  --file PATH         File dependency lookup (partial match)
  --api ROUTE         API endpoint handler lookup
  --component NAME    React/Vue component tree
  --variable NAME     Variable for data flow tracing
  --pattern PATTERN   SQL LIKE search (use % wildcard)
  --list-symbols      Discovery mode with --filter and --path
  --category CAT      Security category (jwt, oauth, password, sql, xss, auth)
  --search TERM       Cross-table exploratory search

ACTION FLAGS (what to show):
  --show-callers      Who calls this symbol?
  --show-callees      What does this symbol call?
  --show-dependencies What does this file import?
  --show-dependents   Who imports this file?
  --show-incoming     Who calls symbols in this file?
  --show-tree         Component hierarchy (parent-child)
  --show-hooks        React hooks used by component
  --show-data-deps    What variables function reads/writes (DFG)
  --show-flow         Variable flow through assignments (DFG)
  --show-taint-flow   Cross-function taint flow (DFG)
  --show-api-coverage Which endpoints have auth controls?

MODIFIERS:
  --depth N              Transitive depth 1-5 (default=1)
  --format text|json|tree  Output format (default=text)
  --type-filter TYPE     Filter by symbol type (function, class, variable)
  --show-code/--no-code  Include source snippets (default: no)
  --save PATH            Save output to file

EXAMPLES:
    # Find callers before refactoring
    aud query --symbol validateUser --show-callers

    # Check file dependencies before moving
    aud query --file src/auth.ts --show-dependents

    # Find API handler
    aud query --api "/users/:id"

    # Pattern search
    aud query --pattern "auth%" --type-filter function

    # List functions in file
    aud query --file auth.py --list functions

    # JSON for parsing
    aud query --symbol foo --show-callers --format json

    # Discovery mode
    aud query --list-symbols --filter '*Controller*'

PERFORMANCE: <10ms for indexed lookups

PREREQUISITES:
    aud full    # Builds repo_index.db

RELATED COMMANDS:
    aud explain         # More comprehensive context (recommended)
    aud manual database # Database schema reference

ANTI-PATTERNS:
  X  aud query --symbol foo.bar
     Methods are stored as ClassName.methodName
     -> First run: aud query --symbol bar
     -> Then use exact name from output

  X  Using query for comprehensive context
     -> Use 'aud explain' instead (returns more in one call)
""",
    },
    "deps": {
        "title": "Dependency Analysis",
        "summary": "Analyze dependencies for vulnerabilities and updates",
        "explanation": """
The deps command provides comprehensive dependency analysis supporting multiple
package managers: npm/yarn, pip/poetry, Docker, and Cargo.

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

EXAMPLES:
    aud deps                              # Basic dependency inventory
    aud deps --check-latest               # Check for outdated packages
    aud deps --upgrade-py                 # Upgrade only Python dependencies
    aud deps --upgrade-py --upgrade-npm   # Upgrade Python and npm
    aud deps --vuln-scan                  # Security vulnerability scan
    aud deps --upgrade-all                # DANGEROUS: Upgrade everything
    aud deps --offline                    # Skip all network operations

OUTPUT FILES:
    .pf/raw/deps.json               # Dependency inventory
    .pf/raw/deps_latest.json        # Latest version info
    .pf/raw/vulnerabilities.json    # Security findings

EXIT CODES:
    0 = Success
    2 = Critical vulnerabilities found (--vuln-scan)

PERFORMANCE: 1-30 seconds (depends on network and registry responses)

PREREQUISITES:
    None for basic inventory
    Network access for --check-latest and --vuln-scan

RELATED COMMANDS:
    aud manual frameworks  # Framework detection
    aud manual docs        # Documentation caching
""",
    },
    "explain": {
        "title": "Comprehensive Code Context",
        "summary": "Get complete context about a file, symbol, or component in one call",
        "explanation": """
The explain command provides a complete "briefing packet" in ONE command,
eliminating the need to run multiple queries or read entire files.
Optimized for AI workflows.

TARGET TYPES (auto-detected):
  File path:     aud explain src/auth.ts
  Symbol:        aud explain authenticateUser
  Class.method:  aud explain UserController.create
  Component:     aud explain Dashboard

WHAT IT RETURNS:

  For files:
    - SYMBOLS DEFINED: All functions, classes, variables with line numbers
    - HOOKS USED: React/Vue hooks (if applicable)
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

WHY USE THIS:
  - Single command replaces 5-6 queries
  - Includes code snippets by default
  - Saves 5,000-10,000 context tokens per task
  - Auto-detects target type (no flags needed)

EXAMPLES:
    aud explain src/auth/service.ts       # File context
    aud explain validateInput             # Symbol context
    aud explain Dashboard --format json   # JSON output for AI
    aud explain OrderController --no-code # Fast mode
    aud explain utils/helpers.py --limit 10

PERFORMANCE: <100ms for files with <50 symbols

OPTIONS:
    --depth N      Call graph depth (1-5, default=1)
    --format json  JSON output for AI consumption
    --section X    Show only specific section
    --no-code      Disable code snippets (faster)
    --limit N      Max items per section (default=20)

PREREQUISITES:
    aud full    # Builds repo_index.db

RELATED COMMANDS:
    aud query       # Low-level database queries
    aud blueprint   # Project-wide overview
    aud impact      # Change blast radius
""",
    },
    "deadcode": {
        "title": "Dead Code Detection",
        "summary": "Find unused modules, functions, and unreachable code",
        "explanation": """
Dead code detection identifies isolated modules, unreachable functions, and
never-imported code by analyzing the import graph. Any module with symbols
that is never imported is potentially dead.

WHAT IT DETECTS:
  Isolated Modules:
    - Python files with functions/classes never imported anywhere
    - JavaScript modules with exports never imported
    - Entire features implemented but never integrated

  Dead Functions:
    - Functions defined but never called (within analyzed scope)
    - Callback handlers for removed event listeners
    - Deprecated API endpoints no longer routed

  False Positive Reduction:
    - CLI entry points (cli.py, main.py) = medium confidence
    - Test files (test_*.py) = medium confidence
    - Migration scripts = excluded by default
    - Empty __init__.py = low confidence

CONFIDENCE LEVELS:
  HIGH: Regular module with symbols, never imported, not special file
  MEDIUM: Entry point, test file, or script (might be invoked externally)
  LOW: Empty __init__.py, generated code (false positive likely)

ALGORITHM (Database-Only):
  1. Query symbols table for files containing functions/classes
  2. Query refs table for all imported file paths
  3. Compute set difference: files_with_code - imported_files
  4. Classify confidence based on file path patterns
  5. Filter by --path-filter and --exclude patterns

EXAMPLES:
    aud deadcode                              # Find all dead code
    aud deadcode --path-filter 'src/%'        # Analyze specific directory
    aud deadcode --fail-on-dead-code          # CI/CD strict mode
    aud deadcode --format json --save report.json
    aud deadcode --format summary

PERFORMANCE: ~1-2 seconds (pure database query, no file I/O)

PREREQUISITES:
    aud full    # Populates symbols and refs tables

EXIT CODES:
    0 = Success, no dead code (or --fail-on-dead-code not set)
    1 = Dead code found AND --fail-on-dead-code flag set
    2 = Error (database missing or query failed)

RELATED COMMANDS:
    aud graph analyze   # Dependency graph view
    aud refactor        # Incomplete refactorings
    aud impact          # Change blast radius (opposite of dead code)
""",
    },
    "session": {
        "title": "AI Agent Session Analysis",
        "summary": "Analyze Claude Code and AI agent sessions for quality and ML training",
        "explanation": """
Session analysis parses and analyzes AI agent interaction logs to extract
metrics, detect patterns, and store data for machine learning. Supports
Claude Code, Codex, and other AI coding assistants.

WHY SESSION ANALYSIS:
Understanding how AI agents interact with your codebase reveals:
- Agent efficiency (work/talk ratio, tokens per edit)
- Common patterns and anti-patterns
- Training data for ML-based suggestions
- Quality indicators for agent behavior

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

USE THE COMMANDS:
    aud session list                    # Find available sessions
    aud session analyze                 # Store to ML database
    aud session inspect session.jsonl   # Deep dive on one session
    aud session activity --limit 20     # Check efficiency trends
    aud session report --limit 5        # Aggregate findings

RELATED COMMANDS:
    aud learn      Train ML on session data
    aud suggest    Get suggestions from learned patterns
""",
    },
}
