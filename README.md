TheAuditor v1.3-RC1

The Ground Truth Engine for AI-Driven Development

AI assistants write code, but they don't understand it. They operate with a fundamental blindness, creating a dangerous illusion of progress. TheAuditor gives them eyes.

It's an offline-first, polyglot, and tool-agnostic static analysis platform that creates an incorruptible source of ground truth about your codebase. It empowers developers and AI assistants to build, refactor, and secure software with verifiable facts, not statistical guesses.

The Revolution: The Autonomous AI Workflow

TheAuditor isn't just another tool you run. It's a platform you give to your AI assistant. It's designed for a fully autonomous, recursive development loop where the AI corrects its own mistakes until the code is verifiably secure and correct.

This is the new paradigm:

Human: "Add authentication to my app."

AI Assistant: Writes the initial code.

AI Assistant: Runs aud full.

AI Assistant: Reads the structured reports in .pf/readthis/.

AI Assistant: "I found 3 security issues and 2 style violations. Fixing now."

AI Assistant: Fixes its own code.

AI Assistant: Runs aud full again.

AI Assistant: "All checks passed. Authentication is complete and secure."

This is not a theoretical workflow. This is what TheAuditor enables, today. It's 100% offline, language-agnostic, and works with any AI assistant that can run a terminal command.

What TheAuditor Actually Does

The aud full command is a comprehensive, multi-stage pipeline that orchestrates a suite of best-in-class tools and proprietary engines to build a complete model of your codebase.

Project Agnostic: Full support for Python, JavaScript/TypeScript, and Rust ecosystems.

100% Offline Analysis: No code ever leaves your machine.

Performance-Obsessed: A full analysis on a medium-sized project completes in minutes, thanks to an in-memory architecture and O(1) lookups. It's CI/CD ready.

Analysis Stage

What it Does

Framework & Dependency Scan

Detects frameworks (React, Vue, Express, Django, Flask, FastAPI) and scans for OSV vulnerabilities (CVEs/CWEs) using npm audit, pip-audit, and osv-scanner.

Industry-Standard Linting

Runs and correlates findings from professional linters: ESLint, Ruff, MyPy, and Clippy.

Multi-Hop Taint Analysis

Performs true inter-procedural (cross-file) taint analysis with Control Flow Graph (CFG) validation to find complex vulnerabilities like SQL Injection and XSS with near-zero false positives.

Graph & Architecture Engine

Builds and analyzes Dependency & Call Graphs to find circular dependencies, identify architectural hotspots, and visualize the "blast radius" of code changes.

Factual Correlation Engine

The "brain" that correlates findings from all other tools to uncover deep, systemic issues that no single tool could find alone.

AI-Centric Output Generation

Preserves all raw tool output in .pf/raw/ for human review, while generating concise, chunked, and summarized reports specifically for AI consumption in .pf/readthis/.

✨ New in v1.3-RC1: The Intelligence Layer

v1.3 introduces the "Insights Engine," turning factual data into actionable intelligence.

🧠 Semantic Context Engine: Teach TheAuditor your project's specific business logic! Define refactorings, API deprecations, and architectural patterns in simple YAML files. The engine uses this context to find obsolete code and track migration progress.

🔮 Predictive ML Insights: An optional Machine Learning engine that learns from your project's history (Git churn, past findings, code complexity) to predict "likely root causes" of bugs and the "next files to edit," helping teams prioritize their work.

🚀 Quick Start

TheAuditor is installed once on your system. It creates a sandboxed toolchain within each project you analyze.

Step 1: Install TheAuditor (One-Time)

# Clone TheAuditor to your preferred tools directory
cd ~/tools
git clone [https://github.com/TheAuditorTool/Auditor.git](https://github.com/TheAuditorTool/Auditor.git)
cd TheAuditor

# Install using your system's Python (do not use a venv here)
pip install -e .

# Verify installation
aud --version


Step 2: Analyze Your Project

# Go to YOUR project's directory
cd ~/my-project-to-audit

# 1. Setup a sandboxed toolchain for this project (npm, pip-audit, etc.)
aud setup-ai --target .

# 2. Index the codebase into a local SQLite database
aud index

# 3. Run the full analysis pipeline
aud full


Step 3: Use the Ground Truth

For AI: Instruct your AI assistant to read the reports in the .pf/readthis/ directory.

For Humans: Review the raw, unfiltered tool output in the .pf/raw/ directory.

For Advanced Queries: Connect directly to the SQLite database at .pf/repo_index.db to run custom queries. The entire model of your code is yours to explore.

💡 Feature Deep Dive

The Semantic Context & Refactor Engine

Track a major refactoring by defining what's obsolete and what's current in a simple YAML file.

Example: refactoring.yaml

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


Run the refactor command to automatically find inconsistencies and track your migration progress across the entire stack.

# Auto-detect refactoring from recent DB migrations
aud refactor --auto-detect --output report.json


Graph Analysis & Visualization

Understand your architecture like never before with rich, data-encoded diagrams.

# Visualize the top 5 hotspots and their connections
aud graph viz --view hotspots --top-hotspots 5

# Create a diagram showing the impact of changing a file
aud graph viz --view impact --impact-target "src/api/auth.js"


Contributing

This project was built by a non-developer in three months. Imagine what we can build together. We welcome contributions! See CONTRIBUTING.md for details.

We are especially looking for help with GraphQL, Java/Spring, Go, and Ruby on Rails support.

License

TheAuditor is licensed under AGPL-3.0. For commercial use, SaaS deployment, or integration into proprietary systems, please contact us for commercial licensing options.