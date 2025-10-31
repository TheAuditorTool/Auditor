# TheAuditor v1.4.2-RC1

### The Ground-Truth Engine for AI-Driven Development 🧭

AI assistants write code, but they don’t *understand* it. They can create a convincing illusion of progress while missing what matters. **TheAuditor gives them eyes.** 👀

**Offline-first. Polyglot. Tool-agnostic.** TheAuditor builds an incorruptible, queryable source of truth about your codebase so humans and AIs can build, refactor, and secure software with **verifiable facts**—not statistical guesses.

**Universal Integration**: No SDK, no integration, no setup - it just works with Claude, Cursor, Windsurf, Copilot, or any future AI tool that can run terminal/shell commands and read files.

## 🆕 v1.4.2-RC1: Code Context On-Demand

Our SAST + code-quality pipeline now ships with a dedicated **code context layer** so AIs stop burning tokens hunting for relationships across files.

- `aud blueprint` — Architectural drill-downs (`--structure`, `--graph`, `--security`, `--taint`) surface scope, bottlenecks, and attack surface with file:line precision.
- `aud query` — Indexed lookups for symbols, call chains, API handlers, dependency graphs, and component trees that respond in milliseconds with JSON/Text/Tree output.
- `aud context` — YAML-driven semantic mapping that tags obsolete/current code, tracks refactor states, and projects business logic directly onto TheAuditor's databases.

Together they cut typical refactor loops from 15k tokens to ~1.5k per iteration while keeping every result tied back to the same verifiable SQLite ground truth that powers our SAST findings.

### Modular Architecture Refactor

v1.4.2-RC1 includes a comprehensive architectural refactor that improves maintainability, testability, and scalability:

**Schema System (`theauditor/indexer/schemas/`)** - Monolithic 2,874-line `schema.py` split into 8 domain-specific modules:
- `core_schema.py` (21 tables) - Language-agnostic patterns
- `python_schema.py` (34 tables) - Python frameworks (Flask, Django, FastAPI, Celery)
- `node_schema.py` (17 tables) - Node.js/TypeScript/React/Vue
- `infrastructure_schema.py` (18 tables) - Docker, Terraform, AWS CDK, GitHub Actions
- `security_schema.py` (5 tables) - SQL, JWT, env vars
- `frameworks_schema.py` (5 tables) - ORM, API routing
- `planning_schema.py` (5 tables) - Implementation tracking
- `graphs_schema.py` (3 tables) - Graph database schemas

**Database Layer (`theauditor/indexer/database/`)** - Monolithic `DatabaseManager` refactored into 8 mixins using multiple inheritance:
- `BaseDatabaseManager` - Core infrastructure (transactions, schema validation, batch operations)
- Domain-specific mixins (Core, Python, Node, Infrastructure, Security, Frameworks, Planning)
- **Result**: 92 methods organized by domain, improved testability

**Indexer Storage (`theauditor/indexer/storage.py`)** - Extracted 1,169-line God Method into focused storage layer:
- `DataStorer` class with 66 handler methods (10-40 lines each)
- Handler registry pattern for clean dispatch
- Separated storage operations from orchestration logic

**TypeScript Extractor (`theauditor/ast_extractors/`)** - Split 2,249-line TypeScript implementation:
- `typescript_impl_structure.py` (1,031 lines) - Stateless structural extraction
- `typescript_impl.py` (1,292 lines) - Context-dependent behavioral analysis
- Clear separation between "what exists" (structural) and "what it does" (behavioral)

**Benefits**: 100% backward compatibility, zero functional changes, improved code organization, better separation of concerns, easier to extend with new languages/frameworks.

---

## 🚀 The Revolution: The Autonomous AI Workflow

TheAuditor isn’t just “another tool you run.” It’s a platform you hand to your AI assistant for a **recursive, self-correcting development loop** where the AI fixes its own mistakes until the code is verifiably secure and correct.

**Example loop:**

```
Human: "Add authentication to my app."

AI Assistant: Writes the initial code.
AI Assistant: Runs `aud full`.
AI Assistant: Reads structured reports in `.pf/readthis/` and queries the SQLite DB for deep context.
AI Assistant: "I found 3 security issues and 2 style violations. Fixing now."
AI Assistant: Fixes its own code.
AI Assistant: Runs `aud full` again.
AI Assistant: "All checks passed. Authentication is complete and secure."
```

### Market Reality Check

Every developer using AI assistants has this problem:
- AI writes insecure code
- AI introduces bugs
- AI doesn't see the full picture
- AI can't verify its work

TheAuditor solves ALL of this. It's not a "nice to have" - it's the missing piece that makes AI development actually trustworthy.
This isn’t hypothetical. **It works today.** It’s 100% offline, language-agnostic, and can be driven by any AI that can run a terminal command. `aud --help` is written for AI consumption so agents can **learn and operate autonomously**.

---

## 🎼 `aud full`: A Symphony of Analysis

A multi-stage pipeline that orchestrates best-in-class tools plus proprietary engines to build a complete, **queryable** model of your repo.

* **Polyglot:** Python, JavaScript/TypeScript, Rust ecosystems, and Terraform/HCL Infrastructure as Code.
* **100% Offline:** Your code never leaves your machine. 🔒
* **Performance-Obsessed:** Medium projects finish in minutes thanks to in-memory architecture and O(1) lookups. CI/CD-ready.

| Stage                              | What it Does                                                                                                                                                    |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Index & Model**               | Indexes the entire codebase into a local **SQLite** DB. Detects frameworks (React, Vue, Express, Django, Flask, FastAPI). Fetches & summarizes dependency docs. Extracts Terraform & AWS CDK IaC resources. |
| **2. Dependency Security**         | Scans for OSV vulnerabilities (CVEs/CWEs) using **npm audit** and **Google's osv-scanner** (offline database) — cross-referenced for accuracy.                 |
| **3. Industry-Standard Linting**   | Correlates **ESLint**, **Ruff**, **MyPy**, **Clippy** with project-aware configs.                                                                               |
| **4. Multi-Hop Taint Analysis**    | True inter-procedural (cross-file) taint analysis with CFG validation to surface complex vulns (SQLi, XSS) with near-zero false positives.                      |
| **5. Graph & Architecture Engine** | Builds Dependency & Call Graphs to spot cycles, hotspots, and the "blast radius" of code changes. Terraform & AWS CDK infrastructure security analysis. |
| **6. Factual Correlation Engine**  | The "brain" that correlates all findings to expose deep systemic issues (e.g., a critical vuln in a high-churn, untested file).                                 |
| **7. AI-Centric Output**           | Raw outputs preserved in `.pf/raw/` for humans; concise, chunked reports for AI in `.pf/readthis/`.                                                             |

---

## ✨ Code Context Intelligence (v1.4.2-RC1)

v1.4.2-RC1 layers **live code context** on top of our existing SAST + code-quality platform so agents can query architecture instead of brute-forcing file reads.

1. **`aud blueprint`** – Four drill-downs (Structure, Graph, Security, Taint) summarize repo scope, gateway files, auth coverage, and risky flows with file:line references.
2. **`aud query`** – Millisecond SQL-backed lookups for call chains, module dependencies, API handlers, and component trees, emitted in text, JSON, or tree form.
3. **`aud context`** – YAML-driven semantic overlays that classify obsolete/current code, track refactor migrations, and tag findings with business language.

All three commands run entirely offline against `.pf/repo_index.db` and `.pf/graphs.db`, keeping TheAuditor’s “truth courier” guarantees intact while closing the code-context gap for AI copilots.

### Optional Insights (Still Available)

* 🧠 **Semantic Context Engine**
  Teach TheAuditor your business logic via simple YAML. Define refactors, API deprecations, and architecture patterns. It flags obsolete code and tracks migration progress.

* 🔮 **Predictive ML Insights** *(always installed, runtime opt-in)*
  Learns from Git churn, past findings, and complexity to predict **likely root causes** and **next files to edit**, helping teams prioritize.

  **NEW in v1.4.2-RC1**: Enhanced temporal intelligence with 4x richer git analysis—now tracks commit frequency, team collaboration patterns, code recency, and sustained activity spans. ML dependencies installed by default but only activate when you train models (`aud learn --enable-git`). Historical data automatically preserved on re-indexing.

---

## ⚡ Quick Start

**Important Directory Structure:**
- `~/tools/TheAuditor/` - Where TheAuditor tool lives
- `~/my-project/` - Your project being analyzed
- `~/my-project/.auditor_venv/` - Sandbox created BY TheAuditor
- `~/my-project/.pf/` - Analysis results

### 1) Install TheAuditor (one-time)

```bash
# Clone TheAuditor to your preferred tools directory
cd ~/tools
git clone https://github.com/TheAuditorTool/Auditor.git
cd TheAuditor

# Install using your system Python (no venv here)
pip install -e .

# Verify installation
aud --version
```

### 2) Analyze your project

```bash
# Go to YOUR project
cd ~/my-project-to-audit

# 1) Set up a sandboxed toolchain (npm, osv-scanner, etc.)
aud setup-ai --target .

# 2) Index the codebase into a local SQLite DB
aud index

# 3) Run the full pipeline
aud full
```

### 3) Use the ground truth

* **For AI:** Instruct your assistant to read `.pf/readthis/` and query `.pf/repo_index.db`.
* **For humans:** Review raw outputs in `.pf/raw/` (incl. Graphviz `.dot` files).
* **For advanced queries:** Connect to `.pf/repo_index.db` directly—**the entire model is yours**.

---

## 🧩 Feature Deep Dive

### Semantic Context & Refactor Engine

Track major refactors by declaring what’s **obsolete** vs **current** in a tiny YAML.

**`refactoring.yaml`**

```yaml
context_name: "product_pricing_refactor"
patterns:
  obsolete:
    - id: "old_product_price"
      pattern: "product\\.(unit_price|retail_price)"
      reason: "Pricing fields moved to ProductVariant model"
      replacement: "product_variant.retail_price"
  current:
    - id: "new_variant_price"
      pattern: "product_variant\\.retail_price"
      reason: "Correct pricing structure"
```

Run it:

```bash
# Auto-detect refactoring from recent DB migrations
aud refactor --auto-detect --output report.json
```

### Graph Analysis & Visualization

Understand your architecture with rich, data-encoded diagrams.

```bash
# Visualize the top 5 hotspots and their connections
aud graph viz --view hotspots --top-hotspots 5

# Show the impact of changing a file
aud graph viz --view impact --impact-target "src/api/auth.js"

# Build data flow graph (tracks variable assignments and returns)
aud graph build-dfg
```

Data flow graphs track how variables flow through assignments and function returns, stored in `.pf/graphs.db` and `.pf/raw/data_flow_graph.json`. Used by taint analysis for more accurate inter-procedural tracking.

### Architectural Intelligence & Code Queries

**NEW in v1.4.2-RC1**: Blueprint, Query, and Context commands convert our indexed SAST output into an always-on code context fabric.

AI assistants previously wasted 5-10k tokens per refactor just to re-learn architecture. TheAuditor now exposes the same SQLite truth our analyzers use so they can ask the repo—not grep through it.

#### Blueprint: Architectural Overview

Get a top-level view of your codebase structure, dependencies, security surface, and data flows - all in one command.

```bash
# Top-level overview (tree structure with key metrics)
aud blueprint

# Drill down into specific areas:
aud blueprint --structure   # Scope, monorepo detection, token estimates
aud blueprint --graph       # Gateway files, circular deps, bottlenecks
aud blueprint --security    # Unprotected endpoints, auth patterns, SQL risk
aud blueprint --taint       # Vulnerable data flows, sanitization coverage

# Export everything for AI consumption
aud blueprint --all --format json
```

**Each drill-down shows**: Exact file:line locations, impact analysis, actionable data. No recommendations - just facts about what exists and where.

#### Query: Code Relationship Lookups

Direct SQL queries over indexed code relationships for precise, token-efficient analysis.

```bash
# Who calls this function? (transitive, 3 levels deep)
aud query --symbol authenticateUser --show-callers --depth 3

# What does this function call?
aud query --symbol handleRequest --show-callees

# What files import this module?
aud query --file src/auth.ts --show-dependents

# Find API endpoint handler
aud query --api "/users/:id"

# Check API security coverage
aud query --show-api-coverage
```

#### Context: Semantic Refactor Tracking

`aud context` projects YAML-defined business rules onto the same database so AIs can reason with your domain language instead of raw file paths.

```bash
# Apply semantic overlays and emit a refactor plan
aud context --file refactors/auth_migration.yaml --verbose

# Run context-aware queries (pairs with blueprint/query output)
aud context query --symbol authenticateUser --show-callers --depth 2 --format json
```

Use it to mark patterns as obsolete/current, measure migration progress, and label findings with terms your stakeholders recognize. Because it runs against `.pf/repo_index.db`, every tag still maps to concrete file:line evidence.

**Performance**: <10ms indexed lookups, zero file reads. Query entire call chains across 100k LOC projects instantly.
**Formats**: Human-readable text, AI-consumable JSON.

#### Planning: Implementation Tracking & Verification

Track implementation plans, verify task completion against YAML specs, and maintain an immutable audit trail with git snapshots.

```bash
# Create a new implementation plan
aud planning init --name "API Migration" --description "Migrate to REST v2"

# Add task with verification spec
aud planning add-task 1 --title "Migrate auth endpoints" --spec migration_spec.yaml

# Verify task completion (checks codebase against spec)
aud planning verify-task 1 1 --verbose --auto-update

# Update task status
aud planning update-task 1 1 --status completed

# Show plan with all tasks
aud planning show 1 --tasks --verbose

# Archive completed plan with final snapshot
aud planning archive 1 --notes "Migration completed"

# Show rollback instructions
aud planning rewind 1 --checkpoint "pre-migration"
```

**Verification specs** are YAML refactor profiles that define expected patterns. Planning system runs them through RefactorRuleEngine and reports violations with file:line precision. Each verification creates a git snapshot for audit trail.

**Use cases**: Track complex refactors, ensure migration completeness, maintain deployment audit trail, rollback instructions for failed deployments.

#### CDK: AWS Infrastructure Security Analysis

Analyze AWS Cloud Development Kit (Python, TypeScript, JavaScript) infrastructure code for security misconfigurations before deployment.

```bash
# Run full CDK security analysis
aud cdk analyze

# Filter by severity
aud cdk analyze --severity critical

# Export findings for review
aud cdk analyze --format json --output cdk_findings.json
```

**Detects**:
- **Public S3 buckets** - CRITICAL severity when `public_read_access=True`
- **Unencrypted storage** - HIGH severity for RDS, EBS, DynamoDB without encryption
- **Open security groups** - CRITICAL severity for 0.0.0.0/0 or ::/0 ingress rules
- **IAM wildcard permissions** - HIGH/CRITICAL for policies with `*` actions/resources or AdministratorAccess

**Workflow**: CDK analysis runs automatically in `aud full` pipeline (Stage 2, after Terraform). Findings written to `.pf/raw/cdk_findings.json` and correlated by FCE with application code vulnerabilities.

#### workflows: GitHub Actions CI/CD Security Analysis

Analyze GitHub Actions workflows for supply-chain vulnerabilities, privilege escalation, and CI/CD pipeline attacks.

```bash
# Run workflow security analysis
aud workflows analyze

# Filter by severity
aud workflows analyze --severity critical

# Export findings
aud workflows analyze --output workflow_security.json
```

**Detects**:
- **Untrusted code execution** - CRITICAL severity for `pull_request_target` with early checkout of untrusted PR code
- **Script injection** - CRITICAL severity for PR metadata (title, body, branch names) interpolated into shell scripts
- **Unpinned actions with secrets** - HIGH severity for mutable action versions (@main, @v1) exposing secrets
- **Excessive permissions** - CRITICAL severity for write permissions (`contents`, `packages`, `id-token`) in untrusted contexts
- **Artifact poisoning** - CRITICAL severity for untrusted builds deployed without validation
- **External workflow risks** - HIGH severity for external reusable workflows with `secrets: inherit`

**Attack Patterns Covered**:
- **CWE-284**: Improper Access Control (untrusted checkout sequences)
- **CWE-829**: Untrusted Supply Chain (unpinned third-party actions)
- **CWE-77**: Command Injection (PR data in run scripts)
- **CWE-269**: Privilege Management (excessive workflow permissions)
- **CWE-200**: Information Exposure (secret leaks to external workflows)
- **CWE-494**: Integrity Check Missing (artifact poisoning chains)

**Workflow**: GitHub Actions analysis runs automatically in `aud full` pipeline (Stage 2). Workflows extracted to `.pf/raw/github_workflows.json` with AI-optimized chunks in `.pf/readthis/`. Findings correlated by FCE with application code and infrastructure vulnerabilities.

**Taint Integration**: PR/issue data registered as taint sources, shell execution as sinks. Enables cross-file flow analysis from workflow inputs to dangerous sinks.

See [HOWTOUSE.md](HOWTOUSE.md#architectural-intelligence--code-queries) for blueprint, query, context, planning, CDK, and workflows walkthroughs.

---

## How It Works With ANY AI Assistant

<img src="https://github.com/user-attachments/assets/6abdf102-621c-4ebf-8ad6-c2912364bed5" width="600" alt="TheAuditor working in Claude Code" />

---

## 🛡️ Troubleshooting & Antivirus

TheAuditor documents vulnerabilities, which can occasionally trip antivirus heuristics—**that’s expected** and means both your AV and TheAuditor are doing their jobs. We don’t recommend adding exclusions. For deeper context, see the original `README.md`.

**Common fixes:**

```bash
# Refresh tool install
cd ~/tools/TheAuditor && git pull && pip install -e .

# Rebuild project sandbox
cd ~/my-project && rm -rf .auditor_venv && aud setup-ai --target .

# Run a clean analysis
aud full --wipecache
```

---

## 🤝 Contributing

This project started from a newcomer in ~3 months. Imagine what we can build together. See **CONTRIBUTING.md**.
We’re especially looking for help with **GraphQL**, **Java/Spring**, **Go**, and **Ruby on Rails** support.

---

## 📜 License

**AGPL-3.0.**
For commercial use, SaaS deployment, or proprietary integration, please reach out for commercial licensing options.

---

## 🧠 Philosophy: A Truth Courier

After ~500 hours of AI-assisted development, one gap stood out: there’s no shared **ground truth**. TheAuditor is built on a simple principle—**be a courier of truth**. It collects and orchestrates **verifiable data** and presents it **without semantic interpretation**. The core engine reports facts; the optional Insights Engine interprets them. That separation keeps your foundation uncorrupted, for humans and AIs alike.
