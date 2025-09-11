# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference Commands

```bash
# Development Setup (ONLY for developing TheAuditor itself)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[all]"
aud setup-claude --target .  # MANDATORY for JS/TS analysis

# For normal usage on projects, install with system Python:
# pip install -e . (from TheAuditor directory)
# Then navigate to YOUR project and run: aud setup-claude --target .

# Testing
pytest -v                    # Run all tests
pytest tests/test_file.py    # Run specific test file
pytest -k "test_name"        # Run specific test by name
pytest --cov=theauditor      # With coverage

# Code Quality
ruff check theauditor tests --fix  # Lint and auto-fix
ruff format theauditor tests       # Format code
black theauditor tests             # Alternative formatter
mypy theauditor --strict           # Type checking

# Running TheAuditor
aud init                     # Initialize project
aud full                     # Complete analysis (multiple phases)
aud full --offline           # Skip network operations (deps, docs)
aud index --exclude-self     # When analyzing TheAuditor itself

# Individual Analysis Commands
aud index                    # Build code index database
aud detect-patterns          # Run security pattern detection
aud taint-analyze            # Perform taint flow analysis
aud graph build              # Build dependency graph
aud graph analyze            # Analyze graph structure
aud cfg analyze              # Analyze control flow complexity
aud cfg viz --file <f> --function <fn>  # Visualize function control flow
aud fce                      # Run Factual Correlation Engine
aud report                   # Generate final report
aud workset                  # Create working set of critical files
aud impact <file>            # Analyze impact of changing a file

# Utility Commands
aud setup-claude             # Setup sandboxed JS/TS tools (MANDATORY)
aud js-semantic <file>       # Parse JS/TS file semantically
aud structure                # Display project structure
aud insights                 # Generate ML insights (requires [ml] extras)
aud refactor <operation>     # Perform refactoring operations
```

## Project Overview

TheAuditor is an offline-first, AI-centric SAST (Static Application Security Testing) and code intelligence platform written in Python. It performs comprehensive security auditing and code analysis for Python and JavaScript/TypeScript projects, producing AI-consumable reports optimized for LLM context windows.

## Core Philosophy: Truth Courier, Not Mind Reader

**CRITICAL UNDERSTANDING**: TheAuditor does NOT try to understand business logic or make AI "smarter." It solves the real problem: **AI loses context and makes inconsistent changes across large codebases.**

### The Development Loop
1. **Human tells AI**: "Add JWT auth with CSRF protection"
2. **AI writes code**: Probably has issues due to context limits (hardcoded secrets, missing middleware, etc.)
3. **Human runs**: `aud full`
4. **TheAuditor reports**: All inconsistencies and security holes as FACTS
5. **AI reads report**: Now sees the COMPLETE picture across all files
6. **AI fixes issues**: With full visibility of what's broken
7. **Repeat until clean**

TheAuditor is about **consistency checking**, not semantic understanding. It finds where code doesn't match itself, not whether it matches business requirements.

## Critical Setup Requirements

### For JavaScript/TypeScript Analysis
TheAuditor requires a sandboxed environment for JS/TS tools. This is NOT optional:

```bash
# MANDATORY: Set up sandboxed tools
aud setup-claude --target .
```

This creates `.auditor_venv/.theauditor_tools/` with isolated TypeScript compiler and ESLint. Without this, TypeScript semantic analysis will fail.

## Key Architectural Decisions

### Modular Package Structure
The codebase follows a modular design where large modules are refactored into packages. Example: the indexer was refactored from a 2000+ line monolithic file into:
```
theauditor/indexer/
├── __init__.py           # Backward compatibility shim
├── config.py             # Constants and patterns
├── database.py           # DatabaseManager class
├── core.py               # FileWalker, ASTCache
├── orchestrator.py       # Main coordination
└── extractors/           # Language-specific logic
```

When refactoring, always:
1. Create a package with the same name as the original module
2. Provide a backward compatibility shim in `__init__.py`
3. Separate concerns into focused modules
4. Use dynamic registries for extensibility

### Database Contract Preservation
The `repo_index.db` schema is consumed by many downstream modules (taint_analyzer, graph builder, etc.). When modifying indexer or database operations:
- NEVER change table schemas without migration
- Preserve exact column names and types
- Maintain the same data format in JSON columns
- Test downstream consumers after changes

## Architecture Overview

### Truth Courier vs Insights: Separation of Concerns

TheAuditor maintains strict separation between **factual observation** and **optional interpretation**:

#### Truth Courier Modules (Core - Always Active)
Report verifiable facts without judgment:
- **Indexer**: "Function X exists at line Y"
- **Taint Analyzer**: "Data flows from req.body to res.send" (NOT "XSS vulnerability")
- **Impact Analyzer**: "Changing X affects 47 files through dependency chains"
- **Pattern Detector**: "Line X matches pattern Y"
- **Graph Analyzer**: "Cycle detected: A→B→C→A"

#### Insights Modules (Optional - Not Installed by Default)
Add scoring and classification on top of facts:
- **taint/insights.py**: Adds "This is HIGH severity XSS"
- **graph/insights.py**: Adds "Health score: 70/100"
- **ml.py**: Requires `pip install -e ".[ml]"` - adds predictions

#### Correlation Rules (Project-Specific Pattern Detection)
- Located in `theauditor/correlations/rules/`
- Detect when multiple facts indicate inconsistency
- Example: "Backend moved field to ProductVariant but frontend still uses Product.price"
- NOT business logic understanding, just pattern matching YOUR refactorings

### Dual-Environment Design
TheAuditor maintains strict separation between:
1. **Primary Environment** (`.venv/`): TheAuditor's Python code and dependencies
2. **Sandboxed Environment** (`.auditor_venv/.theauditor_tools/`): Isolated JS/TS analysis tools

### Core Components

#### Indexer Package (`theauditor/indexer/`)
The indexer has been refactored from a monolithic 2000+ line file into a modular package:
- **config.py**: Constants, patterns, and configuration (SKIP_DIRS, language maps, etc.)
- **database.py**: DatabaseManager class handling all database operations
- **core.py**: FileWalker (with monorepo detection) and ASTCache classes  
- **orchestrator.py**: IndexOrchestrator coordinating the indexing process
- **extractors/**: Language-specific extractors (Python, JavaScript, Docker, SQL, nginx)

The package uses a dynamic extractor registry for automatic language detection and processing.

#### Pipeline System (`theauditor/pipelines.py`)
- Orchestrates comprehensive analysis pipeline in **parallel stages**:
  - **Stage 1**: Foundation (index with batched DB operations, framework detection)
  - **Stage 2**: 3 concurrent tracks (Network I/O, Code Analysis, Graph Build)
  - **Stage 3**: Final aggregation (graph analysis, taint, FCE, report)
- Handles error recovery and logging
- **Performance optimizations**:
  - Batched database inserts (200 records per batch) in indexer
  - Parallel rule execution with ThreadPoolExecutor (4 workers)
  - Parallel holistic analysis (bundle + sourcemap detection)

#### Pattern Detection Engine
- 100+ YAML-defined security patterns in `theauditor/patterns/`
- AST-based matching for Python and JavaScript
- Supports semantic analysis via TypeScript compiler

#### Factual Correlation Engine (FCE) (`theauditor/fce.py`)
- **29 advanced correlation rules** in `theauditor/correlations/rules/`
- Detects complex vulnerability patterns across multiple tools
- Categories: Authentication, Injection, Data Exposure, Infrastructure, Code Quality, Framework-Specific

#### Taint Analysis Package (`theauditor/taint_analyzer/`)
Previously a monolithic 1822-line file, now refactored into a modular package:
- **core.py**: TaintAnalyzer main class
- **sources.py**: Source pattern definitions (user inputs)
- **sinks.py**: Sink pattern definitions (dangerous outputs)
- **patterns.py**: Pattern matching logic
- **flow.py**: Data flow tracking algorithms
- **insights.py**: Optional severity scoring (Insights module)

Features:
- Tracks data flow from sources to sinks
- Detects SQL injection, XSS, command injection
- Database-aware analysis using `repo_index.db`
- Supports both assignment-based and direct-use taint flows
- Merges findings from multiple detection methods (taint_paths, rule_findings, infrastructure)

#### Framework Detection (`theauditor/framework_detector.py`)
- Auto-detects Django, Flask, React, Vue, etc.
- Applies framework-specific rules

#### Graph Analysis (`theauditor/commands/graph.py`)
- Build dependency graphs with `aud graph build`
- Analyze graph health with `aud graph analyze`
- Visualize with GraphViz output (optional)
- Detect circular dependencies and architectural issues

#### Control Flow Analysis (`theauditor/commands/cfg.py`)
- Analyze function complexity with `aud cfg analyze`
- Visualize control flow with `aud cfg viz`
- Find dead code blocks (unreachable code)
- Calculate cyclomatic complexity metrics
- Stored in database tables: cfg_blocks, cfg_edges, cfg_block_statements
- Future: Flow-sensitive taint analysis using CFG paths

#### Output Structure
```
.pf/
├── raw/            # Immutable tool outputs (ground truth)
├── readthis/       # AI-optimized chunks (<65KB each, max 3 chunks per file)
├── repo_index.db   # SQLite database of code symbols
└── pipeline.log    # Execution trace
```

### CLI Entry Points
- Main CLI: `theauditor/cli.py`
- Command modules: `theauditor/commands/`
- Each command is a separate module with standardized structure

## Available Commands

### Core Analysis Commands
- `aud index`: Build comprehensive code index
- `aud detect-patterns`: Run security pattern detection
- `aud taint-analyze`: Perform taint flow analysis
- `aud fce`: Run Factual Correlation Engine
- `aud report`: Generate final consolidated report

### Graph Commands
- `aud graph build`: Build dependency graph
- `aud graph analyze`: Analyze graph health metrics
- `aud graph visualize`: Generate GraphViz visualization

### Utility Commands
- `aud deps`: Analyze dependencies and vulnerabilities
- `aud docs`: Extract and analyze documentation
- `aud docker-analyze`: Analyze Docker configurations
- `aud lint`: Run code linters
- `aud workset`: Create critical file working set
- `aud impact <file>`: Analyze change impact radius
- `aud structure`: Display project structure
- `aud insights`: Generate ML-powered insights (optional)
- `aud refactor <operation>`: Automated refactoring tools

## How to Work with TheAuditor Effectively

### The Correct Workflow
1. **Write specific requirements**: "Add JWT auth with httpOnly cookies, CSRF tokens, rate limiting"
2. **Let AI implement**: It will probably mess up due to context limits
3. **Run audit**: `aud full`
4. **Read the facts**: Check `.pf/readthis/` for issues
5. **Fix based on facts**: Address the specific inconsistencies found
6. **Repeat until clean**: Keep auditing and fixing until no issues

### What NOT to Do
- ❌ Don't ask AI to "implement secure authentication" (too vague)
- ❌ Don't try to make TheAuditor understand your business logic
- ❌ Don't expect TheAuditor to write fixes (it only reports issues)
- ❌ Don't ignore the audit results and claim "done"

### Understanding the Output
- **Truth Couriers** report facts: "JWT secret hardcoded at line 47"
- **Insights** (if installed) add interpretation: "HIGH severity"
- **Correlations** detect YOUR patterns: "Frontend expects old API structure"
- **Impact Analysis** shows blast radius: "Changing this affects 23 files"

## Critical Development Patterns

### Adding New Commands
1. Create module in `theauditor/commands/` with this structure:
```python
import click
from theauditor.utils.decorators import handle_exceptions
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)

@click.command()
@click.option('--workset', is_flag=True, help='Use workset files')
@handle_exceptions
def command_name(workset):
    """Command description."""
    logger.info("Starting command...")
    # Implementation
```

2. Register in `theauditor/cli.py`:
```python
from theauditor.commands import your_command
cli.add_command(your_command.command_name)
```

### Adding Language Support
To add a new language, create an extractor in `theauditor/indexer/extractors/`:
```python
from theauditor.indexer.extractors import BaseExtractor, register_extractor

@register_extractor
class YourLanguageExtractor(BaseExtractor):
    @property
    def supported_extensions(self):
        return ['.ext', '.ext2']
    
    def extract(self, file_info, content, tree):
        # Return dict with symbols, imports, etc.
```

The extractor will be auto-discovered via the registry pattern.

## CRITICAL: Reading Chunked Data

**IMPORTANT**: When processing files from `.pf/readthis/`, you MUST check for truncation:

```python
# Files may be split into chunks if >65KB
# Always check the 'chunk_info' field in JSON files:
chunk_info = data.get('chunk_info', {})
if chunk_info.get('truncated', False):
    # This means there were more findings but only 3 chunks were created
    # The data is incomplete - warn the user
    print("WARNING: Data was truncated at 3 chunks")
```

**Key Points**:
- Files larger than 65KB are split into chunks (configurable via `THEAUDITOR_LIMITS_MAX_CHUNK_SIZE`)
- Maximum 3 chunks per file by default (configurable via `THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE`)
- Example: `patterns_chunk01.json`, `patterns_chunk02.json`, `patterns_chunk03.json`
- If `truncated: true` in `chunk_info`, there were more findings that couldn't fit
- Always process ALL chunk files for complete data

## Critical Working Knowledge

### Pipeline Execution Order
The `aud full` command runs multiple analysis phases in 3 stages:
1. **Sequential**: index → framework_detect
2. **Parallel**: (deps, docs) || (workset, lint, patterns) || (graph_build)
3. **Sequential**: graph_analyze → taint → fce → report

If modifying pipeline, maintain this dependency order.

### File Size and Memory Management
- Files >2MB are skipped by default (configurable)
- JavaScript files are batched for semantic parsing to avoid memory issues
- AST cache persists parsed trees to `.pf/.ast_cache/`
- Database operations batch at 200 records (configurable)

### Monorepo Detection
The indexer automatically detects monorepo structures and applies intelligent filtering:
- Standard paths: `backend/src/`, `frontend/src/`, `packages/*/src/`
- Whitelist mode activated when monorepo detected
- Prevents analyzing test files, configs, migrations as source code

### JavaScript/TypeScript Special Handling
- MUST run `aud setup-claude --target .` first
- Uses bundled Node.js v20.11.1 in `.auditor_venv/.theauditor_tools/`
- TypeScript semantic analysis requires `js_semantic_parser.py`
- ESLint runs in sandboxed environment, not project's node_modules

### Environment Variables
Key environment variables for configuration:
- `THEAUDITOR_LIMITS_MAX_FILE_SIZE`: Maximum file size to analyze (default: 2MB)
- `THEAUDITOR_LIMITS_MAX_CHUNK_SIZE`: Maximum chunk size for readthis output (default: 65KB)
- `THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE`: Maximum chunks per file (default: 3)
- `THEAUDITOR_DB_BATCH_SIZE`: Database batch insert size (default: 200)

## Recent Fixes & Known Issues

### Parser Integration (Fixed)
- **Previous Issue**: Configuration parsers (webpack, nginx, docker-compose) were orphaned
- **Root Cause**: Import paths in extractors didn't match actual parser module names
- **Fix Applied**: Corrected import paths in `generic.py` and `docker.py` extractors
- **Current Status**: All 5 parsers now functional for config security analysis

### Extraction Budget & Taint Merging (Fixed)
- **Previous Issue**: Taint analysis only extracted 26 of 102 findings
- **Root Cause**: Only chunking `taint_paths`, missing `all_rule_findings` and `infrastructure_issues`
- **Fix Applied**: Extraction now merges all taint finding lists; budget increased to 1.5MB
- **Current Status**: All taint findings properly extracted and chunked

### Migration Detection (Enhanced)
- **Previous Issue**: Only checked basic migration paths
- **Root Cause**: Missing common paths like `backend/migrations/` and `frontend/migrations/`
- **Fix Applied**: Added standard migration paths with validation for actual migration files
- **Current Status**: Auto-detects migrations with helpful warnings for non-standard locations

### TypeScript Taint Analysis (Fixed)
- **Previous Issue**: Taint analysis reported 0 sources/sinks for TypeScript
- **Root Cause**: Text extraction was removed from `js_semantic_parser.py` (lines 275, 514)
- **Fix Applied**: Restored `result.text` field extraction
- **Current Status**: TypeScript taint analysis now working - detects req.body → res.send flows

### Direct-Use Vulnerability Detection (Fixed)
- **Previous Issue**: Only detected vulnerabilities through variable assignments
- **Root Cause**: `trace_from_source()` required intermediate variables
- **Fix Applied**: Added direct-use detection for patterns like `res.send(req.body)`
- **Current Status**: Now detects both assignment-based and direct-use taint flows

### Known Limitations
- Maximum 2MB file size for analysis (configurable)
- TypeScript decorator metadata not fully parsed
- Some advanced ES2024+ syntax may not be recognized
- GraphViz visualization requires separate installation

## Common Misconceptions to Avoid

### TheAuditor is NOT:
- ❌ A semantic understanding tool (doesn't understand what your code "means")
- ❌ A business logic validator (doesn't know your business rules)
- ❌ An AI enhancement tool (doesn't make AI "smarter")
- ❌ A code generator (only reports issues, doesn't fix them)

### TheAuditor IS:
- ✅ A consistency checker (finds where code doesn't match itself)
- ✅ A fact reporter (provides ground truth about your code)
- ✅ A context provider (gives AI the full picture across all files)
- ✅ An audit trail (immutable record of what tools found)

## Troubleshooting

### TypeScript Analysis Fails
Solution: Run `aud setup-claude --target .`

### Taint Analysis Reports 0 Vulnerabilities on TypeScript
- Check that `js_semantic_parser.py` has text extraction enabled (lines 275, 514)
- Verify symbols table contains property accesses: `SELECT * FROM symbols WHERE name LIKE '%req.body%'`
- Ensure you run `aud index` before `aud taint-analyze`

### Pipeline Failures
Check `.pf/error.log` and `.pf/pipeline.log` for details

### Linting No Results
Ensure linters installed: `pip install -e ".[linters]"`

### Graph Commands Not Working
- Ensure `aud index` has been run first
- Check that NetworkX is installed: `pip install -e ".[all]"`

## Testing Vulnerable Code
Test projects are in `fakeproj/` directory. Always use `--exclude-self` when analyzing them to avoid false positives from TheAuditor's own configuration.

## Project Dependencies

### Required Dependencies (Core)
- click==8.2.1 - CLI framework
- PyYAML==6.0.2 - YAML parsing
- jsonschema==4.25.1 - JSON validation
- ijson==3.4.0 - Incremental JSON parsing

### Optional Dependencies
Install with `pip install -e ".[group]"`:
- **[linters]**: ruff, mypy, black, bandit, pylint
- **[ml]**: scikit-learn, numpy, scipy, joblib
- **[ast]**: tree-sitter, sqlparse, dockerfile-parse
- **[all]**: Everything including NetworkX for graphs

## Performance Expectations
- Small project (< 5K LOC): ~2 minutes
- Medium project (20K LOC): ~30 minutes
- Large monorepo (100K+ LOC): 1-2 hours
- Memory usage: ~500MB-2GB depending on codebase size
- Disk space: ~100MB for .pf/ output directory