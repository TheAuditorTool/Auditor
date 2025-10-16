# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference Commands

```bash
# Development Setup (ONLY for developing TheAuditor itself)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[all]"
aud setup-ai --target .  # MANDATORY for JS/TS analysis

# For normal usage on projects, install with system Python:
# pip install -e . (from TheAuditor directory)
# Then navigate to YOUR project and run: aud setup-ai --target .

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
aud setup-ai                 # Setup sandboxed JS/TS tools (MANDATORY)
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
aud setup-ai --target .
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

#### Using the Schema Contract System (v1.1+)

TheAuditor v1.1 introduces a schema contract system for type-safe database access.

**Key Files**:
- `theauditor/indexer/schema.py` - Single source of truth for all 36+ table schemas
- Column definitions, validation, and query builders

**Basic Usage**:

```python
from theauditor.indexer.schema import build_query, validate_all_tables, TABLES

# Build type-safe queries with validation
query = build_query('variable_usage', ['file', 'line', 'variable_name'])
cursor.execute(query)

# With WHERE clause
query = build_query('sql_queries', where="command != 'UNKNOWN'")
cursor.execute(query)

# Validate database schema at runtime
mismatches = validate_all_tables(cursor)
if mismatches:
    for table, errors in mismatches.items():
        logger.warning(f"Schema mismatch in {table}: {errors}")
```

**For Rule Authors**:

When writing new rules, ALWAYS use `build_query()` instead of hardcoded SQL:

```python
# ❌ DON'T: Hardcoded SQL (breaks if schema changes)
cursor.execute("SELECT file, line, var_name FROM variable_usage")

# ✅ DO: Schema-compliant query (validated at runtime)
from theauditor.indexer.schema import build_query
query = build_query('variable_usage', ['file', 'line', 'variable_name'])
cursor.execute(query)
```

**Schema Definitions**:

See `theauditor/indexer/schema.py` for complete table schemas. Key tables:
- `files`, `symbols`, `function_call_args` - Core code structure
- `api_endpoints` - REST endpoints with authentication detection
- `variable_usage`, `taint_paths` - Data flow analysis
- `sql_queries`, `orm_queries`, `jwt_patterns` - Database operation and security pattern tracking

**Schema Architecture (v1.1+)**:

The schema system supports comprehensive constraint definitions:
- **Columns**: Type-safe column definitions with nullability and defaults
- **Indexes**: Performance optimization via indexed lookups
- **Primary Keys**: Both single-column and composite primary keys
- **UNIQUE Constraints**: Multi-column uniqueness enforcement (e.g., frameworks table)
- **FOREIGN KEY Pattern**: Intentionally omitted from schema definitions to avoid circular dependencies - defined exclusively in database.py CREATE TABLE statements

**Migration Guide**:

If you have existing databases, the schema validation is non-fatal. Run `aud index` to see warnings:
```bash
aud index
# May show warnings like: "api_endpoints missing column: line"
# Run full re-index to apply schema updates
```

## Architecture Overview

### Truth Courier vs Insights: Separation of Concerns

TheAuditor maintains strict separation between **factual observation** and **optional interpretation**:

#### Insights Modules (Optional)
Located in `theauditor/insights/`, these modules add scoring and interpretation on top of facts from truth couriers. They follow these principles:

1. **Interpretation, not detection** - Score existing findings, don't find new ones
2. **Database-first** - Query repo_index.db for features, no file I/O during analysis
3. **Frozensets for patterns** - O(1) lookups like rules (HTTP_LIBS, DB_LIBS, etc.)
4. **Optional and isolated** - Never imported by truth couriers; commands layer bridges them
5. **Graceful degradation** - ML module checks availability, falls back if dependencies missing

**Available Insights**:
- `insights/taint.py`: Severity scoring (critical/high/medium/low), vulnerability classification
- `insights/graph.py`: Health metrics (0-100 score, A-F grades), architecture recommendations
- `insights/ml.py`: Risk predictions from historical patterns (requires `pip install -e ".[ml]"`)
- `insights/semantic_context.py`: User-defined business logic and semantic understanding (NEW in v1.1+)

All insights use the same gold standards as rules: frozensets for O(1) pattern matching, database queries instead of file I/O, and proper error handling.

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

#### Semantic Context Engine (User-Defined Business Logic)
**NEW in v1.1+**: Located in `theauditor/insights/semantic_context.py` and `theauditor/insights/semantic_rules/`

The Semantic Context Engine allows users to teach TheAuditor about THEIR specific business logic, refactorings, and codebase semantics. Unlike core truth couriers which report universal facts, semantic contexts are 100% user-defined.

**Use Cases**:
- Refactoring tracking: "product.price is obsolete, use product_variant.retail_price"
- Deprecated API detection: "API v1 endpoints should be replaced with GraphQL"
- Migration progress: "Track which files have been updated to new schema"
- Architecture compliance: "Service layer should use new patterns"

**How It Works**:
1. User writes YAML file in `theauditor/insights/semantic_rules/`
2. Define patterns as: obsolete, current, or transitional
3. Run `aud full` or `aud context --file your_context.yaml`
4. TheAuditor classifies findings based on your business logic
5. Reports: files with obsolete patterns, migration progress, high-priority fixes

**Example YAML**:
```yaml
context_name: "product_refactor"
patterns:
  obsolete:
    - id: "old_price"
      pattern: "product\\.unit_price"
      reason: "Moved to ProductVariant"
      replacement: "product_variant.retail_price"
      severity: "high"
  current:
    - id: "new_price"
      pattern: "product_variant\\.retail_price"
      reason: "Correct schema"
```

**Documentation**: See `theauditor/insights/semantic_rules/templates_instructions.md` for complete guide.

**Note**: This replaces the old `correlations` system (now deprecated). The old co-occurring facts model was the wrong abstraction for tracking refactorings and business logic.

### Dual-Environment Design
TheAuditor maintains strict separation between:
1. **Primary Environment** (`.venv/`): TheAuditor's Python code and dependencies
2. **Sandboxed Environment** (`.auditor_venv/.theauditor_tools/`): Isolated JS/TS analysis tools

### Core Components

#### Indexer Package (`theauditor/indexer/`)
The indexer has been refactored from a monolithic 2000+ line file into a modular package:
- **__init__.py**: IndexOrchestrator class (main coordination logic) + backward compatibility
- **config.py**: Constants, patterns, and configuration (SKIP_DIRS, language maps, etc.)
- **database.py**: DatabaseManager class handling all database operations
- **core.py**: FileWalker (with monorepo detection) and ASTCache classes
- **metadata_collector.py**: Git churn and test coverage analysis
- **extractors/**: Language-specific extractors (Python, JavaScript, Docker, SQL, generic)

The package uses a dynamic extractor registry for automatic language detection and processing.

#### Pipeline System (`theauditor/pipelines.py`)
- Orchestrates comprehensive analysis pipeline in **4-stage optimized structure** (v1.1+):
  - **Stage 1 (Sequential)**: Foundation (index with batched DB operations, framework detection)
  - **Stage 2 (Sequential)**: Data Preparation (workset, graph build, CFG, metadata) [NEW in v1.1]
  - **Stage 3 (Parallel)**: Heavy Analysis - 3 concurrent tracks:
    - Track A: Taint analysis (isolated heavy task, ~30 seconds with v1.2 memory cache)
    - Track B: Static & graph analysis (lint, patterns, graph analyze/viz)
    - Track C: Network I/O (deps, docs) - skipped in offline mode
  - **Stage 4 (Sequential)**: Final Aggregation (FCE, chunk extraction, report, summary)
- Handles error recovery and logging
- **Performance optimizations**:
  - Batched database inserts (200 records per batch) in indexer
  - Pipeline-level memory cache (v1.2) shared across analysis phases
  - In-process taint execution avoids subprocess overhead
  - Parallel rule execution with ThreadPoolExecutor (3 workers for Stage 3 tracks)

#### Pattern Detection Engine
- **AST-based rules**: 20+ categories in `theauditor/rules/` (auth, SQL injection, XSS, secrets, frameworks, etc.)
- **YAML patterns**: Configuration security in `theauditor/rules/YAML/config_patterns.yml`
- **Dynamic discovery**: Rules orchestrator (`theauditor/rules/orchestrator.py`) auto-discovers all detection rules
- **Coverage**: 100+ security rules across Python, JavaScript, Docker, Nginx, PostgreSQL, and more
- Supports semantic analysis via TypeScript compiler for type-aware detection

#### Factual Correlation Engine (FCE) (`theauditor/fce.py`)
- **30 advanced correlation rules** in `theauditor/correlations/rules/`
- Detects complex vulnerability patterns across multiple tools
- Categories: Authentication, Injection, Data Exposure, Infrastructure, Code Quality, Framework-Specific

#### Taint Analysis Package (`theauditor/taint/`)
Previously a monolithic file, now refactored into a modular package:
- **core.py**: TaintAnalyzer main class
- **sources.py**: Source pattern definitions (user inputs)
- **config.py**: Sink patterns and taint configuration
- **propagation.py**: Taint propagation algorithms
- **cfg_integration.py**: Control flow graph integration
- **interprocedural.py**: Cross-function taint tracking
- **memory_cache.py**: In-memory performance optimization
- **python.py** & **javascript.py**: Language-specific handlers
- **database.py**: Database operations for taint analysis
- **registry.py**: Dynamic handler registration
- **insights.py**: Optional severity scoring (backward compat shim)

Features:
- Tracks data flow from sources to sinks
- Detects SQL injection, XSS, command injection
- Database-aware analysis using `repo_index.db`
- Supports both assignment-based and direct-use taint flows
- Merges findings from multiple detection methods (taint_paths, rule_findings, infrastructure)

#### Vulnerability Scanner (`theauditor/vulnerability_scanner.py`)

**OSV-Scanner: Offline-First Architecture**

TheAuditor uses 3-source cross-validation for vulnerability detection:
- **npm audit**: JavaScript/TypeScript vulnerabilities (may query npm registry)
- **pip-audit**: Python vulnerabilities (may query PyPI)
- **OSV-Scanner**: Google's offline vulnerability database (ALWAYS offline)

**Critical Design Decision: OSV is 100% Offline**
- **Binary**: `.auditor_venv/.theauditor_tools/osv-scanner/osv-scanner.exe`
- **Database**: `.auditor_venv/.theauditor_tools/osv-scanner/db/{ecosystem}/all.zip`
- **Flag**: ALWAYS uses `--offline-vulnerabilities` (line 478-479 of vulnerability_scanner.py)
- **Network**: Never hits API, regardless of `aud full --offline` flag

**Why Offline-Only**:
1. **Feature-Rich**: Complete vulnerability data without API rate limits
2. **Privacy**: No dependency information sent to external services
3. **Performance**: Instant local queries, no network delays
4. **Reliability**: Works in air-gapped environments
5. **Project-Agnostic**: Single database serves all projects (stored in sandbox)

**Database Contents**:
- npm ecosystem (JavaScript/TypeScript)
- PyPI ecosystem (Python)
- CVE, GHSA, OSV cross-references
- CWE classifications, severity ratings
- Version ranges, fix versions, detailed descriptions

**Track Assignment** (v1.2+):
- OSV runs in **Track B** (Static Analysis & Offline Security)
- Runs in parallel with pattern detection, graph analysis
- NOT bottlenecked by Track C network operations (~90s of rate limits)

**Usage**:
```bash
aud deps --vuln-scan           # Run vulnerability scan (OSV always offline)
aud deps --vuln-scan --offline # Same behavior + npm/pip skip registry
aud full                       # OSV runs in Track B (parallel)
aud full --offline             # OSV still runs (Track C skipped)
```

#### Object Literal Parsing (v1.2+)

TheAuditor extracts object literal structures from JavaScript/TypeScript files to enable dynamic dispatch resolution in taint analysis.

**What is extracted:**
- Property-function mappings: `{ create: handleCreate }`
- Shorthand properties: `{ handleClick }`
- ES6 method definitions: `{ method() {} }`
- Nested objects: `{ api: { handler: fn } }`
- Spread operators: `{ ...base }`

**Why this matters:**
Dynamic dispatch patterns like `const handler = actions[req.query.action]; handler(req.body)` are common in modern JavaScript and represent a security vulnerability when user input controls dispatch. Without object literal parsing, taint analysis cannot resolve which function `handler` points to. With it, we can:
1. Detect the vulnerability (user input → property access = `dynamic_dispatch` sink)
2. Query the database to find all possible target functions
3. Trace taint flow through all possible execution paths

**Query example:**
```python
from theauditor.indexer.schema import build_query

query = build_query('object_literals',
    ['property_value'],
    where="variable_name = ? AND property_type IN ('function_ref', 'shorthand')"
)
cursor.execute(query, ('actions',))
possible_targets = [row[0] for row in cursor.fetchall()]
```

**Architecture:**
- **Extraction:** AST-based traversal in `theauditor/indexer/extractors/javascript.py` (lines 1131-1396)
- **Storage:** `object_literals` table in `repo_index.db` with 4 indexes for fast lookup
- **Consumption:** Taint analyzer queries database for dispatch resolution (`theauditor/taint/interprocedural_cfg.py`)
- **Sink Detection:** New `dynamic_dispatch` category in `SECURITY_SINKS` (`theauditor/taint/sources.py` line 352)

**Detected Vulnerability Patterns:**
- `handlers[req.query.action]()` - User-controlled function dispatch
- `obj[userInput]` - Dynamic property access with tainted key
- Prototype pollution via `__proto__`, `constructor`, `prototype`
- Python dynamic access via `getattr(obj, userInput)`

**Performance:**
- Adds ~10-20ms per JavaScript file during indexing
- Query time: <1ms (measured: 0.029ms average with indexed lookups)
- 18x average speedup over file I/O + regex approach

**Documentation:** See `docs/OBJECT_LITERAL_PARSING.md` for complete guide and API reference.

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

### Adding New Rules
**📖 Full documentation:** `theauditor/rules/RULE_METADATA_GUIDE.md`
**📋 Templates:** `theauditor/rules/TEMPLATE_STANDARD_RULE.py` and `TEMPLATE_JSX_RULE.py`

Rules use **smart filtering** via metadata to skip irrelevant files:

```python
from theauditor.rules.base import RuleMetadata, StandardRuleContext, StandardFinding

METADATA = RuleMetadata(
    name="sql_injection",
    category="sql",
    target_extensions=['.py', '.js', '.ts'],     # ONLY these files
    exclude_patterns=['frontend/', 'migrations/'], # SKIP these paths
    requires_jsx_pass=False  # True = use *_jsx tables (React/Vue)
)

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Database-first detection (no file I/O, no AST traversal)."""
    conn = sqlite3.connect(context.db_path)
    # Query function_call_args, symbols, etc.
```

**Key decisions:**
- **Backend/SQL/Auth rules** → Use `TEMPLATE_STANDARD_RULE.py`
- **JSX syntax rules** → Use `TEMPLATE_JSX_RULE.py` (requires `requires_jsx_pass=True`)
- **React hooks rules** → Use `TEMPLATE_STANDARD_RULE.py` ⚠️ (hooks are function calls, not JSX)

**Result:** SQL rules skip `.jsx` files, React rules skip `.py` files, migrations auto-filtered.

### ABSOLUTE PROHIBITION: Fallback Logic & Regex

**NO FALLBACKS. NO REGEX. NO EXCEPTIONS.**

The schema contract system (`theauditor/indexer/schema.py`) guarantees table existence.
Rules MUST assume all contracted tables exist. Any table existence check is architectural cancer.

**FORBIDDEN PATTERNS:**
```python
# ❌ CANCER - Table existence checking
def _check_tables(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'...")
    return {row[0] for row in cursor.fetchall()}

# ❌ CANCER - Conditional execution based on table existence
if 'function_call_args' not in existing_tables:
    return findings

# ❌ CANCER - Fallback execution paths
if 'api_endpoints' not in existing_tables:
    return _check_oauth_state_fallback(cursor)

# ❌ CANCER - Regex on file content (ANY reason)
pattern = re.compile(r'password\s*=\s*["\'](.+)["\']')
matches = pattern.findall(content)
```

**MANDATORY PATTERN:**
```python
# ✅ CORRECT - Direct database query, assume table exists
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, line, argument_expr
        FROM function_call_args
        WHERE callee_function LIKE '%jwt.sign'
    """)
    # Process findings...
```

**If a table doesn't exist, the rule SHOULD crash. This indicates schema contract violation, not a condition to handle gracefully.**

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
The `aud full` command runs multiple analysis phases in 4 stages:
1. **Sequential Foundation**: index → framework_detect
2. **Sequential Data Prep**: workset → graph_build → cfg_analyze → metadata_churn
3. **Parallel Heavy Analysis**:
   - Track A: taint-analyze (isolated, ~30s with v1.2 cache)
   - Track B: lint → patterns → graph_analyze → graph_viz (4 views)
   - Track C: deps → docs_fetch → docs_summarize (skipped in --offline mode)
4. **Sequential Aggregation**: fce → extract_chunks → report → summary

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
- MUST run `aud setup-ai --target .` first
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

### Schema Contract System Enhancements (v1.1+)
- **jwt_patterns Table Synchronization (Fixed)**: The jwt_patterns table was fully implemented in database.py but missing from schema.py TABLES registry, breaking schema-aware query building. Fixed by adding complete TableSchema definition with all 6 columns and 3 indexes.
- **UNIQUE Constraint Architecture (Enhanced)**: Extended TableSchema class to support UNIQUE constraints via new `unique_constraints` field. Enables full constraint representation, code generation, and validation. Applied to frameworks table: `UNIQUE(name, language, path)`.
- **FOREIGN KEY Design Pattern (Codified)**: Documented intentional omission of FOREIGN KEY constraints from schema.py - they are defined exclusively in database.py to avoid circular dependencies and simplify schema validation. Pattern now explicit in TableSchema docstring.
- **Current Status**: Schema contract system now comprehensive - supports columns, indexes, primary keys, UNIQUE constraints, with explicit FOREIGN KEY pattern documentation.

### Auth Rules Expansion (v1.1+)
- **New Analyzers**: OAuth, password handling, and session management analyzers added
- **Location**: `theauditor/rules/auth/` now contains jwt_analyze.py, oauth_analyze.py, password_analyze.py, session_analyze.py
- **Pattern**: All follow database-first architecture querying function_call_args and symbols tables
- **Current Status**: Comprehensive authentication security coverage across all major patterns

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

### Phase 2 Rules Refactor (In Progress)
Based on comprehensive audit documented in `theauditor/rules/nightmare_fuel.md`:
- **Completed**: Auth rules package (JWT, OAuth, password, session)
- **Completed**: XSS rules refactor with framework-aware safe sinks
- **Gold Standard Pattern**: Database-first queries, frozensets for O(1) lookups, table existence checks
- **Next Phase**: SQL injection rules, remaining categories per priority matrix

### Known Limitations
- Maximum 2MB file size for analysis (configurable)
- TypeScript decorator metadata not fully parsed
- Some advanced ES2024+ syntax may not be recognized
- GraphViz visualization requires separate installation
- SQL extraction patterns may produce UNKNOWN entries (P0 fix scheduled - see nightmare_fuel.md)

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
Solution: Run `aud setup-ai --target .`

### Taint Analysis Reports 0 Vulnerabilities on TypeScript
- Check that `js_semantic_parser.py` has text extraction enabled (lines 275, 514)
- Verify symbols table contains property accesses: `SELECT * FROM symbols WHERE name LIKE '%req.body%'`
- Ensure you run `aud index` before `aud taint-analyze`

### High UNKNOWN Count in sql_queries Table
This is a known issue documented in `theauditor/rules/nightmare_fuel.md`:
- **Symptom**: `SELECT command, COUNT(*) FROM sql_queries` shows 95%+ UNKNOWN
- **Root Cause**: SQL_QUERY_PATTERNS in `indexer/config.py` are too broad
- **Impact**: SQL injection rules may have false positives
- **Fix Status**: P0 priority, 3-hour fix scheduled
- **Workaround**: Focus on non-UNKNOWN findings, or manually verify SQL patterns

### Pipeline Failures
Check `.pf/error.log` and `.pf/pipeline.log` for details

### Linting No Results
Ensure linters installed: `pip install -e ".[linters]"`

### Graph Commands Not Working
- Ensure `aud index` has been run first
- Check that NetworkX is installed: `pip install -e ".[all]"`

### Empty refs Table
- **Symptom**: `SELECT COUNT(*) FROM refs` returns 0
- **Root Cause**: Python extractor uses regex fallback for imports (line 48)
- **Fix Status**: P0 priority, documented in nightmare_fuel.md
- **Impact**: Import tracking and dependency analysis incomplete

## Testing TheAuditor

### Running Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=theauditor --cov-report=html

# Run specific test file
pytest tests/test_schema_contract.py -v
```

### Test Categories

**Unit Tests** (`tests/test_schema_contract.py`):
- Schema definitions and validation
- Query builder correctness
- Column name compliance

**End-to-End Tests** (`tests/test_taint_e2e.py`):
- Full pipeline execution
- Taint analysis on sample code
- Database schema validation

**Adding New Tests**:
See `tests/conftest.py` for fixtures. Follow existing patterns in test files.

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

### v1.2 with Memory Cache (Current)
- **Small project** (< 5K LOC): ~1 minute first run, near-instant on warm cache
- **Medium project** (20K LOC): ~2-5 minutes first run, ~30 seconds on warm cache
- **Large monorepo** (100K+ LOC): ~15-30 minutes first run, ~5 minutes on warm cache
- **Memory usage**: 500MB-4GB depending on codebase size and cache settings
- **Disk space**: ~100-500MB for .pf/ output directory

### Key Performance Improvements
- **v1.2**: 8,461x faster taint analysis (4 hours → 30 seconds), 480x faster overall on warm cache
- **v1.1**: 355x faster pattern detection (10 hours → 101 seconds), 66% faster typical projects
- **Memory cache**: Pre-loads database with O(1) lookups, graceful degradation if memory constrained