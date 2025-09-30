# TheAuditor

Offline-First, AI-Centric SAST & Code Intelligence Platform

## What TheAuditor Does

TheAuditor is a comprehensive code analysis platform that:

- **Finds Security Vulnerabilities**: Detects OWASP Top 10, injection attacks, authentication issues, and framework-specific vulnerabilities
- **Tracks Data Flow**: Follows untrusted data from sources to sinks to identify injection points
- **Analyzes Architecture**: Builds dependency graphs, detects cycles, and measures code complexity
- **Detects Refactoring Issues**: Identifies incomplete migrations, API contract mismatches, and cross-stack inconsistencies
- **Runs Industry-Standard Tools**: Orchestrates ESLint, Ruff, MyPy, and other trusted linters
- **Produces AI-Ready Reports**: Generates chunked, structured output optimized for LLM consumption

Unlike traditional SAST tools, TheAuditor is designed specifically for AI-assisted development workflows, providing ground truth that both developers and AI assistants can trust.

## v1.2 Memory Architecture Revolution

### The Numbers That Changed Everything
- **8,461x faster** taint analysis (4 hours → 30 seconds)
- **480x faster** overall on second run with warm caches
- **100% in-memory** operation for analysis (disk → RAM)
- **O(1) lookups** replacing O(N) searches everywhere

### What's New in v1.2
- **In-Memory Taint Analysis**: Pre-computed patterns, multi-index architecture
- **Optimized Caches**: AST parser (500→10,000), CFG (10,000→25,000)
- **Resource Protection**: Smart eviction prevents memory/disk exhaustion
- **Production Ready**: Handles 1M+ LOC codebases that crashed v1.1

### v1.1 Foundation
- **355x faster** pattern detection (10 hours → 101 seconds)
- **First-ever** working JavaScript/TypeScript CFG extraction (0 → 10,439 blocks)
- **50% faster** overall analysis with new 4-stage pipeline
- **66% faster** on typical projects (30 minutes → 10 minutes)

*Built by a non-developer who learned to code 3 months ago. If I can build this, imagine what you can audit with it.*

## Quick Start

### Step 1: Install TheAuditor (One-Time Setup)
```bash
# Clone TheAuditor to your tools directory (NOT your project!)
cd ~/tools  # or wherever you keep development tools
git clone https://github.com/TheAuditorTool/Auditor.git
cd TheAuditor

# Install using your SYSTEM Python (no venv needed!)
pip install -e .

# Verify installation
aud --version
```

### Step 2: Analyze Your Project
```bash
# Navigate to YOUR PROJECT directory (not TheAuditor!)
cd ~/my-project-to-audit

# Setup sandbox environment for THIS project
aud setup-claude --target .

# Run analysis
aud init   # First time only
aud full   # Complete security audit

# Check results
ls .pf/readthis/
```

**Important Directory Structure:**
- `~/tools/TheAuditor/` - Where TheAuditor tool lives
- `~/my-project/` - Your project being analyzed
- `~/my-project/.auditor_venv/` - Sandbox created BY TheAuditor
- `~/my-project/.pf/` - Analysis results

That's it! TheAuditor will analyze your codebase and generate AI-ready reports in `.pf/readthis/`.

## How It Works With ANY AI Assistant

<img src="https://github.com/user-attachments/assets/6abdf102-621c-4ebf-8ad6-c2912364bed5" width="600" alt="TheAuditor working in Claude Code" />

**Universal Integration**: Just tell your AI assistant to run `aud full` and read the results from `.pf/readthis/`. No SDK, no integration, no setup - it just works with Claude, Cursor, Windsurf, Copilot, or any future AI tool that can run commands and read files.

## The Solution: TheAuditor

TheAuditor is the antidote. It was built to stop "vibe coding" your way into security and quality assurance nightmares. Its mission is to provide an incorruptible source of **ground truth** for both the developer and their AI assistant.

Its philosophy is a direct rejection of the current trend:

- **It Orchestrates Verifiable Data.** The tool runs a suite of industry-standard linters and security scanners, preserving the raw, unfiltered output from each. It does not summarize or interpret this core data.
- **It's Built for AI Consumption.** The tool's primary engineering challenge is to adapt this raw truth into structured, AI-digestible chunks. It ensures the AI works with facts, not faulty summaries.
- **It's Focused and Extensible.** The initial focus is on Python and the Node.js ecosystem, but the modular, pattern-based architecture is designed to invite contributions for other languages and frameworks.

TheAuditor is not a replacement for a formal third-party audit. It is an engineering tool designed to catch the vast majority of glaring issues—from the OWASP Top 10 to common framework anti-patterns. **Its core commitment is to never cross the line from verifiable truth into semantic interpretation.**

Every AI assistant - Claude Code, Cursor, Windsurf, Copilot - they're all blind. They can write code but can't verify it's secure, correct, or complete. TheAuditor gives them eyes.

### Why This Matters

1. **Tool Agnostic** - Works with ANY AI assistant or IDE
   - `aud full` from any terminal
   - Results in `.pf/readthis/` ready for any LLM

2. **AI Becomes Self-Correcting**
   - AI writes code
   - AI runs `aud full`
   - AI reads the ground truth
   - AI fixes its own mistakes
   - Recursive loop until actually correct

3. **No Human Intervention Required**
   - You never touch the terminal
   - The AI runs everything
   - You just review and approve

### The Genius Architecture

```
Human: "Add authentication to my app"
    ↓
AI: *writes auth code*
    ↓
AI: `aud full`
    ↓
AI: *reads .pf/readthis/*
    ↓
AI: "Found 3 security issues, fixing..."
    ↓
AI: *fixes issues*
    ↓
AI: `aud full`
    ↓
AI: "Clean. Authentication complete."
```

### Market Reality Check

Every developer using AI assistants has this problem:
- AI writes insecure code
- AI introduces bugs
- AI doesn't see the full picture
- AI can't verify its work

TheAuditor solves ALL of this. It's not a "nice to have" - it's the missing piece that makes AI development actually trustworthy.

I've built the tool that makes AI assistants production-ready. This isn't competing with SonarQube/SemGrep. This is creating an entirely new category: **AI Development Verification Tools**.

## The Search for Ground Truth in an Age of AI

My background is in systems architecture/infrastructure, not professional software development. I have only been "coding/developing" for little over 3 months. This gives me a unique perspective: I can see the forest, but I'm blind to the individual trees of the code. After immersing myself for 500+ hours in AI-assisted development, I concluded that the entire ecosystem is built on a fundamentally flawed premise: it lacks a source of **ground truth**.

From start to launch on GitHub took me about a month across 250 active hours in front of the computer, for anyone that wonders or cares :P

### The Problem: A Cascade of Corrupted Context

Most AI development tools try to solve the wrong problem. They focus on perfecting the *input*—better prompts, more context—but they ignore the critical issue of **compounding deviation**.

An LLM is a powerful statistical engine, but it doesn't *understand*. The modern AI workflow forces this engine to play a high-stakes game of "telephone," where the original intent is corrupted at every step:

1. A human has an idea.
2. An AI refines it into a prompt.
3. Other tools add their own interpretive layers.
4. The primary AI assistant (e.g., Claude Opus) interprets the final, distorted prompt to generate code.

As a rookie "developer," the only thing I could trust was the raw output: the code and its errors. In a vacuum of deep programming knowledge, these facts were my only anchors.

This architectural flaw is amplified by two dangerous behaviours inherent to AI assistants:

- **Security Theater**: AI assistants are optimized to "make it work," which often means introducing rampant security anti-patterns like hardcoded credentials, disabled authentication, and the pervasive use of `as any` in TypeScript. This creates a dangerous illusion of progress.
- **Context Blindness**: With aggressive context compaction, an AI never sees the full picture. It works with fleeting snapshots of code, forcing it to make assumptions instead of decisions based on facts.

## The Comprehensive Analysis Pipeline

TheAuditor runs a comprehensive audit through multiple analysis phases organized in a 4-stage optimized pipeline (v1.1+):

**STAGE 1: Foundation (Sequential)**
1. **Index Repository** - Build complete code inventory and SQLite database
2. **Detect Frameworks** - Identify Django, Flask, React, Vue, etc.

**STAGE 2: Data Preparation (Sequential) [NEW in v1.1]**
3. **Create Workset** - Define analysis scope
4. **Build Graph** - Construct dependency graph structure
5. **CFG Analysis** - Build control flow graphs (10,439 blocks for JS/TS!)

**STAGE 3: Heavy Parallel Analysis (3 rebalanced tracks)**

*Track A - Taint Analysis (Isolated):*
6. **Taint Analysis** - Track data flow from sources to sinks (~30 seconds with v1.2 memory cache)

*Track B - Static & Graph Analysis:*
7. **Run Linting** - Execute Ruff, MyPy, ESLint as configured
8. **Detect Patterns** - Apply security rules (355x faster with AST!)
9. **Analyze Graph** - Find cycles, measure complexity
10. **Visualize Graph** - Generate multiple graph views

*Track C - Network I/O:*
11. **Check Dependencies** - Analyze package versions and known vulnerabilities
12. **Fetch Documentation** - Extract docstrings and comments
13. **Summarize Documentation** - Create AI-readable documentation chunks

**STAGE 4: Final Aggregation (Sequential)**
14. **Factual Correlation Engine** - Cross-reference findings across all tools with 30 advanced rules
15. **Chunk Extraction** - Automatically create AI-consumable chunks (<65KB) in `.pf/readthis/`
16. **Generate Report** - Produce final consolidated output
17. **Summary Generation** - Create executive summary of findings

## Key Features

### Refactoring Detection & Analysis

TheAuditor detects incomplete refactorings and cross-stack inconsistencies using correlation rules:

```bash
# Analyze refactoring impact
aud refactor --file models/Product.ts --line 42

# Auto-detect from migrations
aud refactor --auto-detect

# Analyze workset
aud refactor --workset --output refactor_report.json
```

Detects:
- **Data Model Changes**: Fields moved between tables
- **API Contract Mismatches**: Frontend/backend inconsistencies
- **Foreign Key Updates**: Incomplete reference changes
- **Cross-Stack Issues**: TypeScript interfaces not matching models

Users define custom rules in `/correlations/rules/`, example provided in refactoring.yaml to detect project-specific patterns.

### Dependency Graph Visualization

TheAuditor now includes rich visual intelligence for dependency graphs using Graphviz:

- **Multiple View Modes**: Full graph, cycles-only, hotspots, architectural layers, impact analysis
- **Visual Intelligence Encoding**:
  - Node colors indicate programming language (Python=blue, JS=yellow, TypeScript=blue)
  - Node size shows importance based on connectivity
  - Red highlighting for dependency cycles
  - Border thickness encodes code churn
- **Actionable Insights**: Focus on what matters with filtered views
- **AI-Readable Output**: Generate SVG visualizations that LLMs can analyze

```bash
# Basic visualization
aud graph viz

# Show only dependency cycles
aud graph viz --view cycles --include-analysis

# Top 5 hotspots with connections
aud graph viz --view hotspots --top-hotspots 5

# Architectural layers visualization
aud graph viz --view layers --format svg

# Impact analysis for a specific file
aud graph viz --view impact --impact-target "src/auth.py"
```

### Control Flow Graph Analysis

TheAuditor analyzes function-level control flow to identify code quality issues:

- **Cyclomatic Complexity**: Measures number of independent paths through functions
- **Dead Code Detection**: Finds unreachable code blocks that can be removed
- **Nesting Analysis**: Identifies deeply nested control structures
- **Visual CFG Generation**: Creates Graphviz visualizations of function control flow
- **Path Analysis**: Enumerates all possible execution paths through functions

```bash
# Analyze all functions for high complexity
aud cfg analyze --complexity-threshold 10

# Find dead code in specific file
aud cfg analyze --file src/auth.py --find-dead-code

# Visualize function control flow
aud cfg viz --file src/payment.py --function process_payment

# Generate SVG with statements shown
aud cfg viz --file src/api.py --function handle_request --format svg --show-statements
```

Use cases:
- Identify functions that need refactoring (high complexity)
- Find and remove dead code
- Visualize complex logic for better understanding
- Future: Enable flow-sensitive taint analysis for higher accuracy

### Insights Analysis (Optional)

Separate from the core Truth Courier modules, TheAuditor offers optional Insights for technical scoring:

```bash
# Run insights analysis on existing audit data
aud insights --mode all

# ML-powered insights (requires: pip install -e ".[ml]")
aud insights --mode ml --ml-train

# Graph health metrics and recommendations
aud insights --mode graph

# Generate comprehensive insights report
aud insights --output insights_report.json
```

Insights modules add interpretive scoring on top of factual data:
- **Health Scores**: Architecture quality metrics
- **Severity Classification**: Risk assessment beyond raw findings
- **Recommendations**: Actionable improvement suggestions
- **ML Predictions**: Pattern-based issue prediction

## Important: Antivirus Software Interaction

#### Why TheAuditor Triggers Antivirus Software

TheAuditor is a security scanner that identifies vulnerabilities in your code. By its very nature, it must:

1. **Read and analyze security vulnerabilities** - SQL injection, XSS attacks, hardcoded passwords
2. **Write these findings to disk** - Creating reports with exact code snippets as evidence
3. **Process files rapidly** - Scanning entire codebases in parallel for efficiency

This creates an inherent conflict with antivirus software, which sees these exact same behaviours as potentially malicious. When TheAuditor finds and documents a SQL injection vulnerability in your code, your antivirus sees us writing "malicious SQL injection patterns" to disk - because that's literally what we're doing, just for legitimate security analysis purposes.

#### Performance Impact You May Experience

When running TheAuditor, you may notice:

- **Increased antivirus CPU usage** - Your AV will scan every file we read AND every finding we write
- **Approximately 10-50% performance reduction, depending on software.** - Both TheAuditor and your AV are reading the same files simultaneously
- **Occasional delays or pauses** - Your AV may temporarily quarantine our output files for deeper inspection

This is not a bug or inefficiency in TheAuditor - it's the unavoidable consequence of two security tools doing their jobs simultaneously.

#### Our Stance on Antivirus

**We do NOT recommend:**
- ❌ Disabling your antivirus software
- ❌ Adding TheAuditor to your exclusion/whitelist
- ❌ Reducing your system's security in any way

Your antivirus is correctly identifying that we're writing security vulnerability patterns to disk. That's exactly what we do - we find vulnerabilities and document them. The fact that your AV is suspicious of this behavior means it's working properly.

#### What We've Done to Minimize Impact

1. **Intelligent resource management** - We automatically reduce parallel workers when system resources are constrained
2. **Pattern defanging** - We insert invisible characters into dangerous patterns to reduce false positives
3. **Adaptive performance** - We monitor CPU and RAM usage to avoid overwhelming your system

#### The Industry Reality

This is not a problem unique to TheAuditor. Every legitimate security scanner faces this same issue:
- **GitHub Advanced Security** runs in isolated cloud containers to avoid this
- **Commercial SAST tools** require enterprise AV exceptions
- **Popular scanners** explicitly document AV conflicts in their installation guides

The fundamental paradox: A tool that finds security vulnerabilities must write those vulnerabilities to disk, which makes it indistinguishable from malware to an antivirus. There is no technical solution to this - it's the inherent nature of security analysis tools.

#### What This Means for You

- Run TheAuditor when system load is low for best performance
- Expect the analysis to take longer than the raw processing time due to AV overhead
- If your AV quarantines output files in `.pf/`, you may need to restore them manually
- Consider running TheAuditor in a controlled environment if performance is critical

We believe in complete transparency about these limitations. This interaction with antivirus software is not a flaw in TheAuditor - it's proof that both your AV and our scanner are doing exactly what they're designed to do: identify and handle potentially dangerous code patterns.

## Common Issues & Troubleshooting

### "No such file or directory: .pf/manifest.json"
- **Cause**: Running `aud init` on a fresh project
- **Fix**: Update TheAuditor and reinstall:
  ```bash
  cd ~/tools/TheAuditor
  git pull
  pip install -e .
  ```

### "Tree-sitter not available" warning
- **Cause**: Missing AST analysis tools
- **Fix**: Reinstall the sandbox in your project:
  ```bash
  cd ~/my-project
  rm -rf .auditor_venv
  aud setup-claude --target .
  ```

### Installation timeout errors
- **Cause**: Slow compilation of C extensions
- **Fix**: Update TheAuditor or manually install:
  ```bash
  cd ~/my-project
  .auditor_venv/bin/pip install tree-sitter tree-sitter-language-pack
  ```

### Nested virtual environments
- **Issue**: Created your own venv before installing
- **Fix**: Exit all venvs and use system Python:
  ```bash
  deactivate  # Exit any active venv
  cd ~/tools/TheAuditor
  pip install -e .  # Use system pip
  ```

---

## Documentation

- **[How to Use](HOWTOUSE.md)** - Complete installation and usage guide
- **[Architecture](ARCHITECTURE.md)** - Technical architecture and design patterns
- **[Contributing](CONTRIBUTING.md)** - How to contribute to TheAuditor
- **[Roadmap](ROADMAP.md)** - Future development plans

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- How to add new language support
- Creating security patterns
- Adding framework-specific rules
- Development guidelines

We especially need help with:
- **GraphQL** analysis
- **Java/Spring** support
- **Go** patterns
- **Ruby on Rails** detection
- **C#/.NET** analysis

---

## License

AGPL-3.0

## Commercial Licensing

TheAuditor is AGPL-3.0 licensed. For commercial use, SaaS deployment, or integration into proprietary systems, please contact via GitHub for licensing options.

## Support

For issues, questions, or feature requests, please open an issue on our [GitHub repository](https://github.com/TheAuditorTool/Auditor).

---

*TheAuditor: Bringing ground truth to AI-assisted development*