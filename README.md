# TheAuditor v1.3-RC1

### The Ground-Truth Engine for AI-Driven Development 🧭

AI assistants write code, but they don’t *understand* it. They can create a convincing illusion of progress while missing what matters. **TheAuditor gives them eyes.** 👀

**Offline-first. Polyglot. Tool-agnostic.** TheAuditor builds an incorruptible, queryable source of truth about your codebase so humans and AIs can build, refactor, and secure software with **verifiable facts**—not statistical guesses.

**Universal Integration**: No SDK, no integration, no setup - it just works with Claude, Cursor, Windsurf, Copilot, or any future AI tool that can run terminal/shell commands and read files.

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

* **Polyglot:** Python, JavaScript/TypeScript, and Rust ecosystems.
* **100% Offline:** Your code never leaves your machine. 🔒
* **Performance-Obsessed:** Medium projects finish in minutes thanks to in-memory architecture and O(1) lookups. CI/CD-ready.

| Stage                              | What it Does                                                                                                                                                    |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Index & Model**               | Indexes the entire codebase into a local **SQLite** DB. Detects frameworks (React, Vue, Express, Django, Flask, FastAPI). Fetches & summarizes dependency docs. |
| **2. Dependency Security**         | Scans for OSV vulnerabilities (CVEs/CWEs) using **npm audit**, **pip-audit**, and **Google’s osv-scanner**—cross-referenced for accuracy.                       |
| **3. Industry-Standard Linting**   | Correlates **ESLint**, **Ruff**, **MyPy**, **Clippy** with project-aware configs.                                                                               |
| **4. Multi-Hop Taint Analysis**    | True inter-procedural (cross-file) taint analysis with CFG validation to surface complex vulns (SQLi, XSS) with near-zero false positives.                      |
| **5. Graph & Architecture Engine** | Builds Dependency & Call Graphs to spot cycles, hotspots, and the “blast radius” of code changes.                                                               |
| **6. Factual Correlation Engine**  | The “brain” that correlates all findings to expose deep systemic issues (e.g., a critical vuln in a high-churn, untested file).                                 |
| **7. AI-Centric Output**           | Raw outputs preserved in `.pf/raw/` for humans; concise, chunked reports for AI in `.pf/readthis/`.                                                             |

---

## ✨ The Intelligence Layer (v1.3)

**v1.3** adds an **Insights Engine** that turns ground truth into action.

* 🧠 **Semantic Context Engine**
  Teach TheAuditor your business logic via simple YAML. Define refactors, API deprecations, and architecture patterns. It flags obsolete code and tracks migration progress.

* 🔮 **Predictive ML Insights** *(optional)*
  Learns from Git churn, past findings, and complexity to predict **likely root causes** and **next files to edit**, helping teams prioritize.

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

# 1) Set up a sandboxed toolchain (npm, pip-audit, etc.)
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

### Code Context Queries

**NEW**: Direct database queries for AI-assisted refactoring - stop burning tokens on file reads.

AI assistants waste 5-10k tokens per refactoring iteration reading files to understand code relationships. TheAuditor's query interface gives them instant access to indexed relationships.

```bash
# Who calls this function? (transitive, 3 levels deep)
aud context query --symbol authenticateUser --show-callers --depth 3

# What does this function call?
aud context query --symbol handleRequest --show-callees

# What files import this module?
aud context query --file src/auth.ts --show-dependents

# Find API endpoint handler
aud context query --api "/users/:id"
```

**Query types**: Symbol lookup, call graphs, file dependencies, API handlers, React component trees.
**Performance**: <10ms indexed lookups, zero file reads.
**Formats**: Human-readable text, AI-consumable JSON, visual tree.

See [HOWTOUSE.md](HOWTOUSE.md#code-context-queries) for complete usage guide.

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
