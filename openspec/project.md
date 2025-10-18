# TheAuditor Project Conventions

**For OpenSpec Agents**: Read this BEFORE creating proposals to understand architectural constraints and development patterns.

**Last Updated**: 2025-10-16 against live codebase

---

## Project Overview

TheAuditor is an offline-first, AI-centric SAST platform written in Python (>=3.11). It performs comprehensive security auditing for Python and JavaScript/TypeScript projects, producing AI-consumable reports optimized for LLM context windows.

**Core Philosophy**: Truth Courier, Not Mind Reader
- TheAuditor finds where code doesn't match itself (inconsistencies)
- It does NOT try to understand business logic
- Reports FACTS, not interpretations

---

## Critical Architecture Patterns (MANDATORY)

### 3-Layer File Path Responsibility Architecture

**DO NOT VIOLATE THIS PATTERN**

1. **INDEXER Layer** (`indexer/__init__.py`)
   - PROVIDES: `file_path` parameter to database methods
   - CALLS: `extractor.extract(file_info, content, tree)`
   - RECEIVES: Extracted data WITHOUT file_path keys
   - STORES: Database records WITH file_path context

2. **EXTRACTOR Layer** (`indexer/extractors/*.py`)
   - RECEIVES: `file_info` dict (contains 'path' key)
   - DELEGATES: To `ast_parser.extract_X(tree)` methods
   - RETURNS: Extracted data WITHOUT file_path keys

3. **IMPLEMENTATION Layer** (`ast_extractors/*_impl.py`)
   - RECEIVES: AST tree only (no file context)
   - EXTRACTS: Data with 'line' numbers and content
   - RETURNS: `List[Dict]` with keys like 'line', 'name', 'type'
   - MUST NOT: Include 'file' or 'file_path' keys

**Correct Flow Example**:
```python
# INDEXER provides file_path
db_manager.add_object_literal(
    file_path,              # ← From orchestrator context
    obj_lit['line'],        # ← From extractor data
    obj_lit['variable_name']
)

# EXTRACTOR delegates (no file_path in return)
result['object_literals'] = self.ast_parser.extract_object_literals(tree)

# IMPLEMENTATION returns (NO file/file_path keys)
return [{
    "line": 42,                    # ✅ Line number
    "variable_name": "config",     # ✅ Data
    # NO 'file' or 'file_path' key  # ✅ Correct
}]
```

**Why**: Single source of truth for file paths. Violations cause NULL file paths in database.

---

### Schema Contract System

**Single Source of Truth**: `theauditor/indexer/schema.py`

All 36+ table schemas defined here. Features:
- Columns: Type-safe definitions with nullability, defaults
- Indexes: Performance optimization
- Primary Keys: Single-column and composite
- UNIQUE Constraints: Multi-column uniqueness
- **FOREIGN KEY Pattern**: Intentionally omitted from schema.py (defined in database.py to avoid circular dependencies)

**Usage in Rules/Analysis**:
```python
from theauditor.indexer.schema import build_query

# Build type-safe queries
query = build_query('variable_usage', ['file', 'line', 'variable_name'])
cursor.execute(query)

# With WHERE clause
query = build_query('sql_queries', where="command != 'UNKNOWN'")
cursor.execute(query)
```

**Key Tables**:
- `files`, `symbols`, `function_call_args` - Core code structure
- `api_endpoints` - REST endpoints with auth detection
- `variable_usage`, `taint_paths` - Data flow analysis
- `sql_queries`, `orm_queries`, `jwt_patterns` - Security patterns
- `object_literals` - Object literal structures for dispatch resolution
- `cfg_blocks`, `cfg_edges`, `cfg_block_statements` - Control flow graphs

---

### Database Contract Preservation

The `repo_index.db` schema is consumed by many downstream modules (taint_analyzer, graph builder, pattern rules, etc.).

**CRITICAL RULES**:
- NEVER change table schemas without migration
- Preserve exact column names and types
- Maintain same data format in JSON columns
- Test downstream consumers after changes
- Schema changes require openspec proposal

---

## Absolute Prohibitions (WILL BREAK BUILD)

### NO FALLBACKS. NO REGEX. NO EXCEPTIONS.

Schema contract system guarantees table existence. Rules MUST assume all contracted tables exist.

**FORBIDDEN**:
```python
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

**MANDATORY**:
```python
# ✅ CORRECT - Direct database query
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

**If table doesn't exist, rule SHOULD crash.** This indicates schema contract violation.

---

## Development Patterns by Component Type

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

---

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
        # MUST NOT include 'file' or 'file_path' keys
```

Auto-discovered via registry.

---

### Adding New Rules

**Templates**:
- `theauditor/rules/TEMPLATE_STANDARD_RULE.py` - Backend/SQL/Auth rules
- `theauditor/rules/TEMPLATE_JSX_RULE.py` - JSX syntax rules

**Smart Filtering via Metadata**:
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

**Rule Discovery**: Orchestrator auto-discovers rules via file structure and metadata.

---

## Core Components & Responsibilities

### Indexer Package (`theauditor/indexer/`)

Structure:
- `__init__.py` - IndexerOrchestrator class (main coordination)
- `config.py` - Constants, patterns
- `database.py` - DatabaseManager class (92KB)
- `core.py` - FileWalker, ASTCache
- `schema.py` - Schema contract system (40KB)
- `metadata_collector.py` - Git churn, test coverage
- `extractors/` - Language-specific extractors (Python, JS/TS, Docker, SQL, etc.)

**Dynamic Extractor Registry**: Extractors auto-discovered via `@register_extractor` decorator.

**Monorepo Detection**: Automatically detects and filters standard paths (`backend/src/`, `frontend/src/`, `packages/*/src/`).

---

### Pipeline System (`theauditor/pipelines.py`)

**4-Stage Optimized Structure**:

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

**Performance Optimizations**:
- Batched database inserts (200 records per batch)
- Pipeline-level memory cache (v1.2) shared across phases
- In-process taint execution (no subprocess overhead)
- Parallel rule execution (ThreadPoolExecutor, 3 workers)

---

### Taint Analysis Package (`theauditor/taint/`)

Structure:
- `core.py` - TaintAnalyzer main class
- `sources.py` - Source pattern definitions
- `config.py` - Sink patterns, config
- `propagation.py` - Taint propagation algorithms
- `cfg_integration.py` - Control flow graph integration
- `interprocedural.py` - Cross-function tracking
- `interprocedural_cfg.py` - CFG-based interprocedural
- `memory_cache.py` - In-memory performance optimization (51KB)
- `database.py` - Database operations
- `registry.py` - Dynamic handler registration
- `insights.py` - Optional severity scoring (backward compat)

**Features**:
- Tracks data flow from sources to sinks
- Detects SQL injection, XSS, command injection, dynamic dispatch
- Database-aware analysis using `repo_index.db`
- Supports assignment-based and direct-use taint flows
- Merges findings from multiple detection methods

---

### Vulnerability Scanner (`theauditor/vulnerability_scanner.py`)

**3-Source Cross-Validation**:
- **npm audit**: JavaScript/TypeScript vulnerabilities (may query registry)
- **pip-audit**: Python vulnerabilities (may query PyPI)
- **OSV-Scanner**: Google's offline vulnerability database (ALWAYS offline)

**OSV-Scanner: 100% Offline**:
- Binary: `.auditor_venv/.theauditor_tools/osv-scanner/osv-scanner.exe`
- Database: `.auditor_venv/.theauditor_tools/osv-scanner/db/{ecosystem}/all.zip`
- Flag: ALWAYS uses `--offline-vulnerabilities`
- Network: Never hits API, regardless of `aud full --offline` flag

---

### Pattern Detection Engine (`theauditor/rules/`)

Structure:
- `auth/` - Authentication patterns (JWT, OAuth, password, session)
- `sql/` - SQL injection detection
- `secrets/` - Hardcoded secrets
- `security/` - General security patterns
- `frameworks/` - Framework-specific rules
- `react/` - React/JSX patterns
- `node/` - Node.js patterns
- `python/` - Python-specific patterns
- `deployment/` - Deployment security
- `performance/` - Performance issues
- `common/` - Common patterns
- `YAML/config_patterns.yml` - Configuration security
- `orchestrator.py` - Rule discovery and execution
- `base.py` - RuleMetadata, StandardRuleContext

**Features**:
- 100+ security rules across languages
- AST-based detection
- Smart filtering via metadata (target_extensions, exclude_patterns)
- Database-first architecture (no file I/O)
- Dynamic rule discovery

---

### Object Literal Parsing (v1.2+)

**Purpose**: Enable dynamic dispatch resolution in taint analysis.

**What is Extracted**:
- Property-function mappings: `{ create: handleCreate }`
- Shorthand properties: `{ handleClick }`
- ES6 method definitions: `{ method() {} }`
- Nested objects: `{ api: { handler: fn } }`
- Spread operators: `{ ...base }`

**Architecture**:
- **Extraction**: `indexer/extractors/javascript.py:304`
- **Storage**: `object_literals` table
- **Implementation**: `ast_extractors/__init__.py:310`
- **Consumption**: Taint analyzer queries for dispatch resolution
- **Detection**: `dynamic_dispatch` sink category

---

### Graph Analysis (`theauditor/commands/graph.py`)

Commands:
- `aud graph build` - Build dependency graph
- `aud graph analyze` - Health metrics, cycle detection
- `aud graph viz` - GraphViz visualization (4 views)

Detects:
- Circular dependencies
- Architectural issues
- Hotspots
- Layer violations

---

### Control Flow Analysis (`theauditor/commands/cfg.py`)

Commands:
- `aud cfg analyze` - Function complexity, dead code
- `aud cfg viz` - Visualize function control flow

Features:
- Cyclomatic complexity calculation
- Unreachable code detection
- Stored in: `cfg_blocks`, `cfg_edges`, `cfg_block_statements` tables

---

## Output Structure

`.pf/` directory:
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

**Chunking Behavior**:
- Files >65KB split into chunks (configurable: `THEAUDITOR_LIMITS_MAX_CHUNK_SIZE`)
- Max 3 chunks per file (configurable: `THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE`)
- Format: `patterns_chunk01.json`, `patterns_chunk02.json`, etc.
- If `truncated: true` in `chunk_info`, more findings existed

---

## Validation & Testing Requirements

### Testing

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

**Test Categories**:
- Unit Tests: Schema definitions, query builder
- End-to-End Tests: Full pipeline, taint analysis

**Test fixtures**: `tests/conftest.py`

### Code Quality

```bash
# Linting
ruff check theauditor tests --fix  # Lint and auto-fix
ruff format theauditor tests       # Format code

# Type checking
mypy theauditor --strict

# Alternative formatter
black theauditor tests
```

---

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

**Resources**:
- Memory usage: 500MB-4GB (depends on codebase size)
- Disk space: ~100-500MB for .pf/ output

**Key Improvements**:
- v1.2: 8,461x faster taint analysis (4 hours → 30 seconds)
- v1.1: 355x faster pattern detection (10 hours → 101 seconds)
- Memory cache: Pre-loads DB with O(1) lookups

---

## Environment Variables

**Configuration**:
- `THEAUDITOR_LIMITS_MAX_FILE_SIZE` - Max file size (default: 2097152 = 2MB)
- `THEAUDITOR_LIMITS_MAX_CHUNK_SIZE` - Max chunk size (default: 65536 = 65KB)
- `THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE` - Max chunks per file (default: 3)
- `THEAUDITOR_DB_BATCH_SIZE` - Database batch insert size (default: 200)
- `THEAUDITOR_TIMEOUT_SECONDS` - Default timeout (default: 1800 = 30 min)
- `THEAUDITOR_TIMEOUT_{COMMAND}_SECONDS` - Per-command timeout override

---

## Known Issues & Context

### Schema Contract System (v1.1+)
- jwt_patterns table synchronized (was missing from schema.py registry)
- UNIQUE constraint architecture enhanced
- FOREIGN KEY pattern codified (intentionally in database.py, not schema.py)

### Auth Rules Expansion (v1.1+)
- OAuth, password, session analyzers added to `theauditor/rules/auth/`
- All follow database-first architecture

### Parser Integration (Fixed)
- Configuration parsers (webpack, nginx, docker-compose) now functional
- Import paths corrected in extractors

### Taint Analysis (Fixed)
- Extraction budget increased to 1.5MB
- All taint finding lists now properly merged
- TypeScript taint analysis working (text extraction restored)
- Direct-use vulnerability detection added

### Known Limitations
- Maximum 2MB file size for analysis (configurable)
- TypeScript decorator metadata not fully parsed
- Some advanced ES2024+ syntax may not be recognized
- GraphViz visualization requires separate installation
- SQL extraction patterns may produce UNKNOWN entries (P0 fix scheduled)
- Empty refs table issue (Python extractor uses regex fallback - P0 priority)

---

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

---

## Reference: Core Commands

```bash
# Complete pipeline
aud full                     # Complete 4-stage pipeline
aud full --offline           # Skip network operations

# Core analysis
aud index                    # Build code index database
aud detect-patterns          # Run 100+ security pattern rules
aud taint-analyze            # Perform taint flow analysis

# Graph & architecture
aud graph build              # Build dependency graph
aud graph analyze            # Analyze graph health
aud graph viz                # Visualize (4 views: full, cycles, hotspots, layers)
aud cfg analyze              # Analyze control flow complexity

# Security
aud deps --vuln-scan         # Run npm audit, pip-audit, OSV-Scanner

# Reporting
aud fce                      # Run Factual Correlation Engine
aud report                   # Generate consolidated report
```

---

**This document distills critical patterns from CLAUDE.md for OpenSpec proposal creation. For comprehensive developer documentation, see CLAUDE.md.**
