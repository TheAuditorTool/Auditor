<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# ABSOLUTE RULES - READ FIRST OR WASTE TIME

## NEVER USE SQLITE3 COMMAND DIRECTLY

**ALWAYS** use Python with sqlite3 import. The sqlite3 command is not installed in WSL.

```python
# CORRECT - Always use this pattern
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('C:/path/to/database.db')
c = conn.cursor()
c.execute('SELECT ...')
for row in c.fetchall():
    print(row)
conn.close()
"
```

```bash
# WRONG - This will fail with "sqlite3: command not found"
sqlite3 database.db "SELECT ..."
```

## NEVER USE EMOJIS IN PYTHON OUTPUT

Windows Command Prompt uses CP1252 encoding. Emojis cause `UnicodeEncodeError: 'charmap' codec can't encode character`.

```python
# WRONG - Will crash on Windows
print('Status: ✅ PASS')
print('Cross-file: ❌')

# CORRECT - Use plain ASCII
print('Status: PASS')
print('Cross-file: NO')
```

**These two rules alone waste 5-10 tool calls per session. Follow them religiously.**

---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with TheAuditor codebase.
**Last Verified**: 2025-10-16 against live codebase.

## Project Overview

TheAuditor is an offline-first, AI-centric SAST (Static Application Security Testing) and code intelligence platform written in Python. It performs comprehensive security auditing and code analysis for Python and JavaScript/TypeScript projects, producing AI-consumable reports optimized for LLM context windows.

**Version**: 1.3.0-RC1 (pyproject.toml:7)
**Python**: >=3.11 required (pyproject.toml:10)

---

# ⚠️ CRITICAL ARCHITECTURE RULE - READ FIRST ⚠️

## ZERO FALLBACK POLICY - ABSOLUTE AND NON-NEGOTIABLE

**NO FALLBACKS. NO EXCEPTIONS. NO WORKAROUNDS. NO "JUST IN CASE" LOGIC.**

This is the MOST IMPORTANT rule in the entire codebase. Violation of this rule is grounds for immediate rejection.

### What is BANNED FOREVER:

1. **Database Query Fallbacks** - NEVER write multiple queries with fallback logic:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   cursor.execute("SELECT * FROM table WHERE name = ?", (normalized_name,))
   result = cursor.fetchone()
   if not result:  # ← THIS IS CANCER
       cursor.execute("SELECT * FROM table WHERE name = ?", (original_name,))
       result = cursor.fetchone()
   ```

2. **Try-Except Fallbacks** - NEVER catch exceptions to fall back to alternative logic:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   try:
       data = load_from_database()
   except Exception:  # ← THIS IS CANCER
       data = load_from_json()  # Fallback to JSON
   ```

3. **Table Existence Checks** - NEVER check if tables exist before querying:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   if 'function_call_args' in existing_tables:  # ← THIS IS CANCER
       cursor.execute("SELECT * FROM function_call_args")
   ```

4. **Conditional Fallback Logic** - NEVER write "if X fails, try Y" patterns:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   result = method_a()
   if not result:  # ← THIS IS CANCER
       result = method_b()  # Fallback method
   ```

5. **Regex Fallbacks** - NEVER fall back to regex when database query fails:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   cursor.execute("SELECT * FROM symbols WHERE name = ?", (name,))
   if not cursor.fetchone():  # ← THIS IS CANCER
       matches = re.findall(pattern, content)  # Regex fallback
   ```

### Why NO FALLBACKS EVER:

The database is regenerated FRESH on every `aud full` run. If data is missing:
- **The database is WRONG** → Fix the indexer
- **The query is WRONG** → Fix the query
- **The schema is WRONG** → Fix the schema

Fallbacks HIDE bugs. They create:
- Inconsistent behavior across runs
- Silent failures that compound
- Technical debt that spreads like cancer
- False sense of correctness

### CORRECT Pattern - HARD FAIL IMMEDIATELY:

```python
# ✅ CORRECT - Single query, hard fail if wrong
cursor.execute("SELECT path FROM symbols WHERE name = ? AND type = 'function'", (name,))
result = cursor.fetchone()
if not result:
    # Log the failure (exposing the bug) and continue
    if debug:
        print(f"Symbol not found: {name}")
    continue  # Skip this path - DO NOT try alternative query
```

### If a query returns NULL:
1. **DO NOT** write a second fallback query
2. **DO NOT** try alternative logic
3. **DO** log the failure with debug output
4. **DO** skip that code path (continue/return)
5. **DO** investigate WHY the query failed (indexer bug, schema bug, query bug)

### This applies to EVERYTHING:
- Database queries (symbols, function_call_args, assignments, etc.)
- File operations (reading, parsing, extracting)
- API calls (module resolution, import resolution)
- Data transformations (normalization, formatting)

**ONLY ONE CODE PATH. IF IT FAILS, IT FAILS LOUD. NO SAFETY NETS.**

---

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
aud full                     # Complete 4-stage pipeline
aud full --offline           # Skip network operations (deps, docs)
aud index --exclude-self     # When analyzing TheAuditor itself

# Core Analysis
aud index                    # Build code index database
aud detect-patterns          # Run 100+ security pattern rules
aud taint-analyze            # Perform taint flow analysis

# Graph & Architecture
aud graph build              # Build dependency graph
aud graph analyze            # Analyze graph health
aud graph viz                # Visualize (4 views: full, cycles, hotspots, layers)
aud cfg analyze              # Analyze control flow complexity
aud cfg viz --file <f> --function <fn>  # Visualize function CFG

# Reporting
aud fce                      # Run Factual Correlation Engine
aud report                   # Generate final consolidated report
aud workset                  # Create working set of changed files
aud impact --file <path>     # Analyze change impact radius

# Dependencies & Security
aud deps --vuln-scan         # Run npm audit, pip-audit, OSV-Scanner
aud docker-analyze           # Analyze Docker security

# Code Quality
aud lint                     # Run configured linters
aud structure                # Display project structure

# Advanced
aud insights                 # Optional insights analysis (requires [ml] extras)
aud refactor --auto-detect   # Detect incomplete refactorings

# Code Context Queries (AI-assisted refactoring)
aud context query --symbol authenticateUser --show-callers  # Who calls this function
aud context query --symbol validateInput --show-callees     # What does this call
aud context query --file src/auth.ts --show-dependencies    # What file imports
aud context query --file src/utils.ts --show-dependents     # Who imports file
aud context query --api "/users/:id"                        # Find endpoint handler
aud context query --component UserProfile --show-tree       # Component hierarchy

# Semantic Context Analysis
aud context semantic --file rules/oauth_migration.yaml  # Classify findings by business logic
```

## Core Philosophy: Truth Courier, Not Mind Reader

TheAuditor does NOT try to understand business logic. It solves: **AI loses context and makes inconsistent changes across large codebases.**

**The Development Loop:**
1. Human tells AI: "Add JWT auth with CSRF protection"
2. AI writes code (probably has issues due to context limits)
3. Human runs: `aud full`
4. TheAuditor reports: All inconsistencies and security holes as FACTS
5. AI reads report: Now sees COMPLETE picture across all files
6. AI fixes issues: With full visibility
7. Repeat until clean

TheAuditor finds where code doesn't match itself, not whether it matches business requirements.

## Critical Setup Requirements

### JavaScript/TypeScript Analysis - NOT OPTIONAL

```bash
aud setup-ai --target .
```

Creates `.auditor_venv/.theauditor_tools/` with:
- Isolated TypeScript compiler
- ESLint
- Node.js v20.11.1
- OSV-Scanner vulnerability database (~500MB)

Without this, TypeScript semantic analysis WILL FAIL.

## Architecture Overview

### Dual-Environment Design
1. **Primary Environment** (`.venv/`): TheAuditor's Python code
2. **Sandboxed Environment** (`.auditor_venv/.theauditor_tools/`): Isolated JS/TS tools

### Truth Courier vs Insights: Separation of Concerns

**Truth Couriers** (Core - Always Active):
- **Indexer**: "Function X exists at line Y"
- **Taint Analyzer**: "Data flows from req.body to res.send"
- **Pattern Detector**: "Line X matches pattern Y"
- **Graph Analyzer**: "Cycle detected: A→B→C→A"
- **Impact Analyzer**: "Changing X affects 47 files"

**Insights** (Optional - Not Installed by Default):
- `insights/taint.py`: Severity scoring (critical/high/medium/low)
- `insights/graph.py`: Health metrics (0-100 score, A-F grades)
- `insights/ml.py`: Risk predictions (requires `pip install -e ".[ml]"`)
- `insights/semantic_context.py`: User-defined business logic

Principles:
1. Interpretation, not detection
2. Database-first (no file I/O)
3. Frozensets for O(1) lookups
4. Optional and isolated
5. Graceful degradation

## Critical Architectural Decisions

### 3-Layer File Path Responsibility Architecture

**MANDATORY PATTERN - DO NOT VIOLATE:**

1. **INDEXER Layer** (`indexer/__init__.py`):
   - PROVIDES: `file_path` (absolute or relative path)
   - CALLS: `extractor.extract(file_info, content, tree)`
   - RECEIVES: Extracted data WITHOUT file_path keys
   - STORES: Database records WITH file_path context

2. **EXTRACTOR Layer** (`indexer/extractors/*.py`):
   - RECEIVES: `file_info` dict (contains 'path' key)
   - DELEGATES: To `ast_parser.extract_X(tree)` methods
   - RETURNS: Extracted data WITHOUT file_path keys

3. **IMPLEMENTATION Layer** (`ast_extractors/*_impl.py`):
   - RECEIVES: AST tree only (no file context)
   - EXTRACTS: Data with 'line' numbers and content
   - RETURNS: `List[Dict]` with keys like 'line', 'name', 'type'
   - MUST NOT: Include 'file' or 'file_path' keys

**Example Flow:**
```python
# 1. INDEXER provides file_path (indexer/__init__.py:976)
db_manager.add_object_literal(
    file_path,              # ← From orchestrator context
    obj_lit['line'],        # ← From extractor data
    obj_lit['variable_name'],
    ...
)

# 2. EXTRACTOR delegates (indexer/extractors/javascript.py:304)
result['object_literals'] = self.ast_parser.extract_object_literals(tree)

# 3. IMPLEMENTATION returns (ast_extractors/__init__.py:310)
return [{
    "line": 42,                    # ✅ Line number
    "variable_name": "config",     # ✅ Data
    # NO 'file' or 'file_path' key  # ✅ Correct
}]
```

**WHY**: Single source of truth for file paths. Prevents violations where implementations incorrectly track files.

**Violation Symptoms:**
- Implementation returns `{"file": "...", "line": 42, ...}` ❌
- Indexer uses `obj_lit['file']` instead of `file_path` parameter ❌
- Database receives NULL file paths ❌

### Database Contract Preservation

The `repo_index.db` schema is consumed by many downstream modules (taint_analyzer, graph builder, pattern rules, etc.).

**CRITICAL RULES:**
- NEVER change table schemas without migration
- Preserve exact column names and types
- Maintain same data format in JSON columns
- Test downstream consumers after changes

### Schema Contract System (v1.1+)

**Single Source of Truth**: `theauditor/indexer/schema.py`

All 36+ table schemas defined here. Supports:
- Columns: Type-safe definitions with nullability, defaults
- Indexes: Performance optimization
- Primary Keys: Single-column and composite
- UNIQUE Constraints: Multi-column uniqueness
- **FOREIGN KEY Pattern**: Intentionally omitted from schema.py (defined in database.py to avoid circular dependencies)

**Basic Usage:**
```python
from theauditor.indexer.schema import build_query, validate_all_tables

# Build type-safe queries
query = build_query('variable_usage', ['file', 'line', 'variable_name'])
cursor.execute(query)

# With WHERE clause
query = build_query('sql_queries', where="command != 'UNKNOWN'")
cursor.execute(query)

# Validate schema at runtime
mismatches = validate_all_tables(cursor)
if mismatches:
    for table, errors in mismatches.items():
        logger.warning(f"Schema mismatch in {table}: {errors}")
```

**Key Tables:**
- `files`, `symbols`, `function_call_args` - Core code structure
- `api_endpoints` - REST endpoints with auth detection
- `variable_usage`, `taint_paths` - Data flow analysis
- `sql_queries`, `orm_queries`, `jwt_patterns` - Security patterns
- `object_literals` - Object literal structures for dispatch resolution
- `cfg_blocks`, `cfg_edges`, `cfg_block_statements` - Control flow graphs

## Core Components

### Indexer Package (`theauditor/indexer/`)

**Verified Structure** (as of 2025-10-16):
```
theauditor/indexer/
├── __init__.py             # IndexerOrchestrator class (main coordination)
├── config.py               # Constants, patterns (7.5KB)
├── database.py             # DatabaseManager class (92KB)
├── core.py                 # FileWalker, ASTCache (15KB)
├── schema.py               # Schema contract system (40KB)
├── metadata_collector.py   # Git churn, test coverage (16KB)
└── extractors/             # Language-specific extractors
    ├── __init__.py         # ExtractorRegistry, BaseExtractor
    ├── python.py           # Python extractor (36KB)
    ├── javascript.py       # JS/TS extractor (51KB)
    ├── docker.py           # Dockerfile extractor (5KB)
    ├── generic.py          # Config file extractor (15KB)
    ├── json_config.py      # JSON config extractor (11KB)
    ├── prisma.py           # Prisma schema extractor (7KB)
    └── sql.py              # SQL file extractor (1.5KB)
```

**Dynamic Extractor Registry**: Extractors auto-discovered via `@register_extractor` decorator.

**Monorepo Detection**: Automatically detects and filters:
- Standard paths: `backend/src/`, `frontend/src/`, `packages/*/src/`
- Whitelist mode activated when detected
- Prevents analyzing test files, configs, migrations as source code

### Pipeline System (`theauditor/pipelines.py`)

**4-Stage Optimized Structure** (verified lines 565-633):

**Stage 1 (Sequential)**: Foundation
- `index` - Build code index (batched DB inserts)
- `detect-frameworks` - Framework detection

**Stage 2 (Sequential)**: Data Preparation
- `workset` - Identify changed files
- `graph build` - Build dependency graph
- `cfg analyze` - Control flow analysis
- `metadata` - Git churn analysis

**Stage 3 (Parallel)**: Heavy Analysis - 3 concurrent tracks
- **Track A**: Taint analysis (isolated, ~30s with v1.2 cache)
- **Track B**: Static & graph analysis (lint, patterns, graph analyze/viz, OSV-Scanner)
- **Track C**: Network I/O (deps --check-latest, docs) - skipped in offline mode

**Stage 4 (Sequential)**: Final Aggregation
- `fce` - Factual Correlation Engine
- `report` - Generate consolidated report
- `summary` - Executive summary

**Performance Optimizations:**
- Batched database inserts (200 records per batch)
- Pipeline-level memory cache (v1.2) shared across phases
- In-process taint execution (no subprocess overhead)
- Parallel rule execution (ThreadPoolExecutor, 3 workers)

### Taint Analysis Package (`theauditor/taint/`)

**Verified Structure** (verified via ls 2025-10-16):
```
theauditor/taint/
├── __init__.py              # Package exports
├── core.py                  # TaintAnalyzer main class (15KB)
├── sources.py               # Source pattern definitions (11KB)
├── config.py                # Sink patterns, config (8KB)
├── propagation.py           # Taint propagation algorithms (31KB)
├── cfg_integration.py       # Control flow graph integration (36KB)
├── interprocedural.py       # Cross-function tracking (13KB)
├── interprocedural_cfg.py   # CFG-based interprocedural (22KB)
├── memory_cache.py          # In-memory performance optimization (51KB)
├── database.py              # Database operations (45KB)
├── registry.py              # Dynamic handler registration (8KB)
└── insights.py              # Optional severity scoring (backward compat)
```

**Features:**
- Tracks data flow from sources to sinks
- Detects SQL injection, XSS, command injection, dynamic dispatch
- Database-aware analysis using `repo_index.db`
- Supports assignment-based and direct-use taint flows
- Merges findings from multiple detection methods

**CRITICAL: Taint Data Storage**
- **NO taint_paths table exists** - taint analysis writes to `findings_consolidated` table
- Taint findings stored with `tool='taint'` and `rule='taint-{category}'`
- Cross-file tracking data stored in `details_json` column as JSON
- Query: `SELECT * FROM findings_consolidated WHERE tool='taint'` to get all taint findings
- Do NOT look for taint_paths table - it does not exist in the schema

### Vulnerability Scanner (`theauditor/vulnerability_scanner.py`)

**3-Source Cross-Validation:**
- **npm audit**: JavaScript/TypeScript vulnerabilities (may query registry)
- **pip-audit**: Python vulnerabilities (may query PyPI)
- **OSV-Scanner**: Google's offline vulnerability database (ALWAYS offline)

**OSV-Scanner: 100% Offline** (verified lines 22-25, 479):
- Binary: `.auditor_venv/.theauditor_tools/osv-scanner/osv-scanner.exe`
- Database: `.auditor_venv/.theauditor_tools/osv-scanner/db/{ecosystem}/all.zip`
- Flag: ALWAYS uses `--offline-vulnerabilities` (line 479)
- Network: Never hits API, regardless of `aud full --offline` flag

**Database Contents:**
- npm ecosystem (JavaScript/TypeScript)
- PyPI ecosystem (Python)
- CVE, GHSA, OSV cross-references
- CWE classifications, severity ratings
- Version ranges, fix versions

**Track Assignment**: OSV runs in Track B (parallel with pattern detection, graph analysis)

### Pattern Detection Engine

**Verified Structure** (`theauditor/rules/`):
- auth/ - Authentication patterns (JWT, OAuth, password, session)
- sql/ - SQL injection detection
- secrets/ - Hardcoded secrets
- security/ - General security patterns
- frameworks/ - Framework-specific rules
- react/ - React/JSX patterns
- node/ - Node.js patterns
- python/ - Python-specific patterns
- deployment/ - Deployment security
- performance/ - Performance issues
- common/ - Common patterns
- YAML/config_patterns.yml - Configuration security
- orchestrator.py - Rule discovery and execution
- base.py - RuleMetadata, StandardRuleContext

**Rule System Features:**
- 100+ security rules across languages
- AST-based detection
- Smart filtering via metadata (target_extensions, exclude_patterns)
- Database-first architecture (no file I/O)
- Dynamic rule discovery
- TypeScript semantic analysis support

### Object Literal Parsing (v1.2+)

**Purpose**: Enable dynamic dispatch resolution in taint analysis.

**What is Extracted:**
- Property-function mappings: `{ create: handleCreate }`
- Shorthand properties: `{ handleClick }`
- ES6 method definitions: `{ method() {} }`
- Nested objects: `{ api: { handler: fn } }`
- Spread operators: `{ ...base }`

**Architecture:**
- **Extraction**: `indexer/extractors/javascript.py` line 304 (JavaScriptExtractor)
- **Storage**: `object_literals` table (schema.py:495, database.py:1312)
- **Implementation**: `ast_extractors/__init__.py:310` (extract_object_literals method)
- **Consumption**: Taint analyzer queries for dispatch resolution
- **Detection**: `dynamic_dispatch` sink category

**Detected Patterns:**
- `handlers[req.query.action]()` - User-controlled dispatch
- `obj[userInput]` - Dynamic property access with tainted key
- Prototype pollution via `__proto__`, `constructor`, `prototype`

**Performance:**
- ~10-20ms per JS file during indexing
- Query time: <1ms (indexed lookups)

**Documentation:** See `docs/OBJECT_LITERAL_PARSING.md` for complete guide.

### Framework Detection (`theauditor/framework_detector.py`)

Verified exists (29KB). Auto-detects:
- Django, Flask (Python backends)
- React, Vue, Angular (frontends)
- Express, Fastify (Node.js backends)
- Applies framework-specific rules

### Graph Analysis (`theauditor/commands/graph.py`)

Commands verified:
- `aud graph build` - Build dependency graph
- `aud graph analyze` - Health metrics, cycle detection
- `aud graph viz` - GraphViz visualization (4 views)

Detects:
- Circular dependencies
- Architectural issues
- Hotspots
- Layer violations

### Control Flow Analysis (`theauditor/commands/cfg.py`)

Commands verified:
- `aud cfg analyze` - Function complexity, dead code
- `aud cfg viz` - Visualize function control flow

Features:
- Cyclomatic complexity calculation
- Unreachable code detection
- Stored in: `cfg_blocks`, `cfg_edges`, `cfg_block_statements` tables

## Output Structure

**Verified** (.pf/ directory):
```
.pf/
├── raw/                # Immutable tool outputs (ground truth)
├── readthis/          # AI-optimized chunks (<65KB each, max 3 chunks per file)
├── repo_index.db      # SQLite database of code symbols
├── pipeline.log       # Execution trace
├── .cache/            # AST cache
├── graphs.db          # Graph analysis database
└── context/           # Semantic context analysis
```

**Chunking Behavior:**
- Files >65KB split into chunks (configurable: `THEAUDITOR_LIMITS_MAX_CHUNK_SIZE`)
- Max 3 chunks per file (configurable: `THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE`)
- Format: `patterns_chunk01.json`, `patterns_chunk02.json`, etc.
- If `truncated: true` in `chunk_info`, more findings existed

## CLI Entry Points

**Verified** (cli.py lines 232-323):

Commands registered:
- init, index, workset, lint, deps, report, summary, full, fce, impact
- taint_analyze, setup_ai, explain, detect_patterns, detect_frameworks
- docs, tool_versions, init_js, init_config
- learn, suggest, learn_feedback (ML commands)
- rules_command, refactor_command, insights_command, context_command
- docker_analyze, structure, metadata
- graph (group), cfg (group)

## Critical Development Patterns

### Adding New Commands

1. Create module in `theauditor/commands/`:
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

Create extractor in `theauditor/indexer/extractors/`:
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

Auto-discovered via registry.

### Adding New Rules

**Templates:**
- `theauditor/rules/TEMPLATE_STANDARD_RULE.py` - Backend/SQL/Auth rules
- `theauditor/rules/TEMPLATE_JSX_RULE.py` - JSX syntax rules

**Smart Filtering via Metadata:**
```python
from theauditor.rules.base import RuleMetadata, StandardRuleContext, StandardFinding

METADATA = RuleMetadata(
    name="sql_injection",
    category="sql",
    target_extensions=['.py', '.js', '.ts'],     # ONLY these files
    exclude_patterns=['frontend/', 'migrations/'], # SKIP these paths
    requires_jsx_pass=False  # True = use *_jsx tables
)

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Database-first detection (no file I/O, no AST traversal)."""
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # Query function_call_args, symbols, etc.
    cursor.execute("""
        SELECT file, line, argument_expr
        FROM function_call_args
        WHERE callee_function LIKE '%execute%'
    """)
    # Process findings...
```

### ABSOLUTE PROHIBITION: Fallback Logic & Regex

**NO FALLBACKS. NO REGEX. NO MIGRATIONS. NO EXCEPTIONS.**

The database is GENERATED FRESH every `aud full` run. It MUST exist and MUST be correct.
Schema contract system guarantees table existence. All code MUST assume contracted tables exist.

**FORBIDDEN PATTERNS:**
```python
# ❌ CANCER - Database migrations
def _run_migrations(self):
    try:
        cursor.execute("ALTER TABLE...")
    except sqlite3.OperationalError:
        pass  # NO! Database is fresh every run!

# ❌ CANCER - JSON fallbacks in FCE
try:
    data = load_from_db(db_path)
except Exception:
    # Fallback to JSON - NO! Hard fail if DB is wrong
    data = json.load(open('fallback.json'))

# ❌ CANCER - Table existence checking
if 'function_call_args' not in existing_tables:
    return findings

# ❌ CANCER - Fallback execution
if 'api_endpoints' not in existing_tables:
    return _check_oauth_state_fallback(cursor)

# ❌ CANCER - Regex on file content
pattern = re.compile(r'password\s*=\s*["\'](.+)["\']')
matches = pattern.findall(content)
```

**MANDATORY PATTERN:**
```python
# ✅ CORRECT - Direct database query, hard failure on error
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # NO try/except, NO table checks, NO fallbacks
    cursor.execute("""
        SELECT file, line, argument_expr
        FROM function_call_args
        WHERE callee_function LIKE '%jwt.sign'
    """)
    # Process findings...

# ✅ CORRECT - FCE loads directly from database
def run_fce(root_path):
    db_path = Path(root_path) / ".pf" / "repo_index.db"

    # NO try/except, NO JSON fallback, hard crash if DB wrong
    hotspots, cycles = load_graph_data_from_db(db_path)
    complex_funcs = load_cfg_data_from_db(db_path)
```

**WHY NO FALLBACKS:**
- Database regenerated from scratch every run - migrations are meaningless
- If data is missing, pipeline is broken and SHOULD crash
- Graceful degradation hides bugs and creates inconsistent behavior
- Hard failure forces immediate fix of root cause

**If table doesn't exist or data is missing, code MUST crash.** This indicates schema contract violation or pipeline bug that must be fixed immediately.

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

## Project Dependencies

**Verified** (pyproject.toml lines 15-73):

**Core:**
- click==8.3.0
- PyYAML==6.0.3
- jsonschema==4.25.1
- ijson==3.4.0.post0
- json5==0.12.1

**Optional Groups** (`pip install -e ".[group]"`):

**[dev]**:
- pytest==8.4.2
- pytest-cov>=4.0.0
- pytest-xdist>=3.0.0
- ruff==0.14.0
- black==25.9.0

**[linters]**:
- ruff==0.14.0
- mypy==1.18.2
- black==25.9.0
- bandit==1.8.6
- pylint==3.3.9

**[ml]**:
- scikit-learn==1.7.2
- numpy==2.3.3
- scipy==1.16.2
- joblib==1.5.2

**[ast]**:
- tree-sitter==0.25.2
- tree-sitter-language-pack==0.10.0
- sqlparse==0.5.3
- dockerfile-parse==2.0.1

**[all]**: Everything above combined

## Performance Expectations

### v1.2 with Memory Cache (Current)

**Small project** (< 5K LOC):
- First run: ~1 minute
- Warm cache: near-instant

**Medium project** (20K LOC):
- First run: ~2-5 minutes
- Warm cache: ~30 seconds

**Large monorepo** (100K+ LOC):
- First run: ~15-30 minutes
- Warm cache: ~5 minutes

**Resources:**
- Memory usage: 500MB-4GB (depends on codebase size)
- Disk space: ~100-500MB for .pf/ output

**Key Improvements:**
- v1.2: 8,461x faster taint analysis (4 hours → 30 seconds)
- v1.1: 355x faster pattern detection (10 hours → 101 seconds)
- Memory cache: Pre-loads DB with O(1) lookups

## Environment Variables

**Configuration:**
- `THEAUDITOR_LIMITS_MAX_FILE_SIZE` - Max file size (default: 2097152 = 2MB)
- `THEAUDITOR_LIMITS_MAX_CHUNK_SIZE` - Max chunk size (default: 65536 = 65KB)
- `THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE` - Max chunks per file (default: 3)
- `THEAUDITOR_DB_BATCH_SIZE` - Database batch insert size (default: 200)
- `THEAUDITOR_TIMEOUT_SECONDS` - Default timeout (default: 1800 = 30 min)
- `THEAUDITOR_TIMEOUT_{COMMAND}_SECONDS` - Per-command timeout override

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
- **Gold Standard Pattern**: Database-first queries, frozensets for O(1) lookups
- **Next Phase**: SQL injection rules, remaining categories per priority matrix

### Known Limitations
- Maximum 2MB file size for analysis (configurable)
- TypeScript decorator metadata not fully parsed
- Some advanced ES2024+ syntax may not be recognized
- GraphViz visualization requires separate installation
- SQL extraction patterns may produce UNKNOWN entries (P0 fix scheduled - see nightmare_fuel.md)

## Testing

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=theauditor --cov-report=html

# Run specific test
pytest tests/test_schema_contract.py -v
```

**Test Categories:**
- Unit Tests: Schema definitions, query builder
- End-to-End Tests: Full pipeline, taint analysis

**Test fixtures**: `tests/conftest.py`

## Common Misconceptions

### TheAuditor is NOT:
- ❌ A semantic understanding tool
- ❌ A business logic validator
- ❌ An AI enhancement tool
- ❌ A code generator

### TheAuditor IS:
- ✅ A consistency checker (finds where code doesn't match itself)
- ✅ A fact reporter (ground truth about code)
- ✅ A context provider (gives AI full picture)
- ✅ An audit trail (immutable record)

## Troubleshooting

### TypeScript Analysis Fails
**Solution**: Run `aud setup-ai --target .`

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
Check `.pf/error.log` and `.pf/pipeline.log`

### Linting No Results
Ensure linters installed: `pip install -e ".[linters]"`

### Graph Commands Not Working
- Ensure `aud index` ran first
- Check NetworkX installed: `pip install -e ".[all]"`

### Empty refs Table
- **Symptom**: `SELECT COUNT(*) FROM refs` returns 0
- **Root Cause**: Python extractor uses regex fallback for imports (line 48)
- **Fix Status**: P0 priority, documented in nightmare_fuel.md
- **Impact**: Import tracking and dependency analysis incomplete

---

**This document is anchored in code verified on 2025-10-16. All claims checked against live implementation. Zero hallucinations.**
