# TheAuditor Architecture

This document provides a comprehensive technical overview of TheAuditor's architecture, design patterns, and implementation details.

## System Overview

TheAuditor is an offline-first, AI-centric SAST (Static Application Security Testing) and code intelligence platform. It orchestrates industry-standard tools to provide ground truth about code quality and security, producing AI-consumable reports optimized for LLM context windows.

### Core Design Principles

1. **Offline-First Operation** - All analysis runs without network access, ensuring data privacy and reproducible results
2. **Dual-Mode Architecture** - Courier Mode preserves raw external tool outputs; Expert Mode applies security expertise objectively
3. **AI-Centric Workflow** - Produces chunks optimized for LLM context windows (65KB by default)
4. **Sandboxed Execution** - Isolated analysis environment prevents cross-contamination
5. **No Fix Generation** - Reports findings without prescribing solutions

## Truth Courier vs Insights: Separation of Concerns

TheAuditor maintains a strict architectural separation between **factual observation** and **optional interpretation**:

### Truth Courier Modules (Core)
These modules are the foundation - they gather and report verifiable facts without judgment:

- **Indexer**: Reports "Function X exists at line Y with Z parameters"
- **Taint Analyzer**: Reports "Data flows from pattern A to pattern B through path C"
- **Impact Analyzer**: Reports "Changing function X affects Y files through Z call chains"
- **Graph Analyzer**: Reports "Module A imports B, B imports C, C imports A (cycle detected)"
- **Pattern Detector**: Reports "Line X matches pattern Y from rule Z"
- **Linters**: Reports "Tool ESLint flagged line X with rule Y"

These modules form the immutable ground truth. They report **what exists**, not what it means.

### Insights Modules (Optional Interpretation Layer)
These are **optional packages** that consume Truth Courier data to add scoring and classification. All insights modules have been consolidated into a single package for better organization:

```
theauditor/insights/
├── __init__.py      # Package exports
├── ml.py           # Machine learning predictions (requires pip install -e ".[ml]")
├── graph.py        # Graph health scoring and recommendations
└── taint.py        # Vulnerability severity classification
```

- **insights/taint.py**: Adds "This flow is XSS with HIGH severity"
- **insights/graph.py**: Adds "Health score: 70/100, Grade: B"
- **insights/ml.py** (requires `pip install -e ".[ml]"`): Adds "80% probability of bugs based on historical patterns"

**Important**: Insights modules are:
- Not installed by default (ML requires explicit opt-in)
- Completely decoupled from core analysis
- Still based on technical patterns, not business logic interpretation
- Designed for teams that want actionable scores alongside raw facts
- All consolidated in `/insights` package for consistency

### The FCE: Factual Correlation Engine
The FCE correlates facts from multiple tools without interpreting them:
- Reports: "Tool A and Tool B both flagged line 100"
- Reports: "Pattern X and Pattern Y co-occur in file Z"
- Never says: "This is bad" or "Fix this way"

## Core Components

### Indexer Package (`theauditor/indexer/`)
The indexer has been refactored from a monolithic 2000+ line file into a modular package structure:

```
theauditor/indexer/
├── __init__.py           # IndexOrchestrator + backward compatibility
├── config.py             # Constants, patterns, and configuration
├── database.py           # DatabaseManager class for all DB operations
├── core.py               # FileWalker and ASTCache classes
├── metadata_collector.py # Git churn and test coverage analysis
└── extractors/
    ├── __init__.py       # BaseExtractor abstract class and registry
    ├── python.py         # Python-specific extraction logic
    ├── javascript.py     # JavaScript/TypeScript extraction
    ├── docker.py         # Docker/docker-compose extraction
    ├── sql.py            # SQL extraction
    └── generic.py        # Generic extractor (webpack, nginx, compose)
```

#### File Path Responsibility Architecture

**CRITICAL DESIGN PATTERN**: TheAuditor enforces strict separation of concerns for file path management across three architectural layers.

**The Problem This Solves:**
In early iterations, implementations tried to track file paths directly, leading to:
- Architectural violations (implementations tracking file context)
- Database corruption (NULL file paths when keys didn't match)
- Code duplication (file path handling in multiple layers)
- Maintenance nightmares (changing file paths required touching 10+ files)

**The Solution: 3-Layer Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: INDEXER (indexer/__init__.py)                      │
│ ─────────────────────────────────────────────────────────── │
│ PROVIDES: file_path (source of truth)                       │
│ CALLS:    extractor.extract(file_info, content, tree)       │
│ RECEIVES: Data WITHOUT file_path keys                       │
│ STORES:   db_manager.add_X(file_path, data['line'], ...)    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: EXTRACTOR (indexer/extractors/*.py)                │
│ ─────────────────────────────────────────────────────────── │
│ RECEIVES: file_info dict (contains 'path' key)              │
│ DELEGATES: ast_parser.extract_X(tree)                       │
│ RETURNS:  {'line': 42, 'name': 'foo', ...}                  │
│           NO 'file' or 'file_path' keys                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: IMPLEMENTATION (ast_extractors/*_impl.py)          │
│ ─────────────────────────────────────────────────────────── │
│ RECEIVES: AST tree only (NO file context)                   │
│ EXTRACTS: Data with line numbers and content                │
│ RETURNS:  [{'line': 42, 'name': 'foo', ...}]                │
│ MUST NOT: Include 'file' or 'file_path' in returned dicts   │
└─────────────────────────────────────────────────────────────┘
```

**Real-World Example: Object Literal Extraction**

```python
# LAYER 1: INDEXER provides file_path (indexer/__init__.py:952)
for obj_lit in extracted['object_literals']:
    self.db_manager.add_object_literal(
        file_path,                      # ← From orchestrator (line 564)
        obj_lit['line'],                # ← From implementation
        obj_lit['variable_name'],       # ← From implementation
        obj_lit['property_name'],       # ← From implementation
        obj_lit['property_value'],      # ← From implementation
        obj_lit['property_type'],       # ← From implementation
        obj_lit.get('nested_level', 0), # ← From implementation
        obj_lit.get('in_function', '')  # ← From implementation
    )

# LAYER 2: EXTRACTOR delegates (indexer/extractors/javascript.py:290)
result['object_literals'] = self.ast_parser.extract_object_literals(tree)

# LAYER 3: IMPLEMENTATION returns (ast_extractors/typescript_impl.py:1293)
object_literals.append({
    "line": prop_line,              # ✅ Line number only
    "variable_name": var_name,      # ✅ Data
    "property_name": prop_name,     # ✅ Data
    "property_value": prop_value,   # ✅ Data
    "property_type": prop_type,     # ✅ Data
    "nested_level": 0,              # ✅ Data
    "in_function": in_function      # ✅ Data
    # NO 'file' or 'file_path' key   ✅ Correct architecture
})
```

**Why This Matters:**

1. **Single Source of Truth**: File paths exist in ONE place (indexer orchestrator)
2. **Clear Boundaries**: Each layer has specific responsibilities
3. **Easy Testing**: Implementations can be tested without file system
4. **Maintainability**: Changing file path handling touches ONE file
5. **Type Safety**: Database operations validate complete records

**Violation Detection:**

❌ **WRONG - Implementation tracking files:**
```python
# ast_extractors/typescript_impl.py
return [{
    "file": file_path,    # ❌ ARCHITECTURAL VIOLATION
    "line": 42,
    "name": "foo"
}]
```

❌ **WRONG - Indexer expecting file from implementation:**
```python
# indexer/__init__.py
db_manager.add_object_literal(
    obj_lit['file'],      # ❌ KeyError when 'file' not in dict
    obj_lit['line'],
    ...
)
```

✅ **CORRECT - Implementation returns line only:**
```python
# ast_extractors/typescript_impl.py
return [{
    "line": 42,           # ✅ Line number
    "name": "foo"         # ✅ Data
}]
```

✅ **CORRECT - Indexer provides file_path:**
```python
# indexer/__init__.py (line 952)
db_manager.add_object_literal(
    file_path,            # ✅ From orchestrator context
    obj_lit['line'],      # ✅ From implementation
    ...
)
```

**Enforcement:**

- All `*_impl.py` files have docstring contracts prohibiting file path keys
- Code reviews check for architectural violations
- Database NULL constraints catch missing file paths immediately
- Unit tests verify implementations return correct key structures

Key features:
- **Dynamic extractor registry** for automatic language detection
- **Batched database operations** (200 records per batch by default)
- **AST caching** for performance optimization
- **Monorepo detection** and intelligent path filtering
- **Parallel JavaScript processing** when semantic parser available
- **Dual-pass JSX extraction**: Transformed mode for taint analysis, preserved mode for structural analysis
- **Metadata collection** (`metadata_collector.py`): Git churn analysis (commits, authors, volatility) and test coverage parsing (Python coverage.py, Node.js Istanbul/nyc) for temporal dimension in FCE

### Pipeline System (`theauditor/pipelines.py`)
Orchestrates comprehensive analysis pipeline in **4-stage optimized structure** (v1.1+):

**Stage 1 - Foundation (Sequential):**
1. Repository indexing - Build manifest and symbol database
2. Framework detection - Identify technologies in use

**Stage 2 - Data Preparation (Sequential) [NEW in v1.1]:**
3. Workset creation - Define analysis scope
4. Graph building - Construct dependency graph
5. CFG analysis - Build control flow graphs

**Stage 3 - Heavy Parallel Analysis (Rebalanced in v1.1, Optimized in v1.2):**
- **Track A (Taint Analysis - Isolated):**
  - Taint flow analysis (~30 seconds with v1.2 memory cache, was 2-4 hours)
- **Track B (Static & Graph Analysis):**
  - Linting
  - Pattern detection (355x faster with AST)
  - Graph analysis
  - Graph visualization
- **Track C (Network I/O):**
  - Dependency checking
  - Documentation fetching
  - Documentation summarization

**Stage 4 - Final Aggregation (Sequential):**
- Factual correlation engine
- Report generation
- Summary creation

**Performance Impact:** 480x faster overall on second run (v1.2), 25-40% faster pipeline structure (v1.1)

### Pattern Detection Engine
- **AST-based rules**: 20+ categories in `theauditor/rules/` (auth, SQL injection, XSS, secrets, frameworks, performance, etc.)
- **YAML patterns**: Configuration security in `theauditor/rules/YAML/config_patterns.yml`
- **Dynamic discovery**: Rules orchestrator (`theauditor/rules/orchestrator.py`) auto-discovers all detection rules
- **Coverage**: 100+ security rules across Python, JavaScript, Docker, Nginx, PostgreSQL, and framework-specific patterns
- Supports semantic analysis via TypeScript compiler for type-aware detection

### Factual Correlation Engine (FCE) (`theauditor/fce.py`)
- **30 advanced correlation rules** in `theauditor/correlations/rules/`
- Detects complex vulnerability patterns across multiple tools
- Categories: Authentication, Injection, Data Exposure, Infrastructure, Code Quality, Framework-Specific
- **5 architectural meta-findings**: Correlates security issues with graph hotspots, complexity, churn, and test coverage

### Code Context Query Engine (`theauditor/context/`)

**NEW in v1.3**: Direct database query interface for AI-assisted code navigation and refactoring.

#### The Problem It Solves

AI assistants waste 5-10k tokens per refactoring iteration reading files to answer basic questions:
- "Who calls this function?"
- "What does this function call?"
- "Which files import this module?"
- "Where is this API endpoint implemented?"

TheAuditor already indexes all this relationship data during `aud index`. The query engine provides instant access via SQL queries - **zero file reads, <10ms response time**.

#### Architecture Overview

```
theauditor/context/
├── __init__.py      # Package exports
├── query.py         # CodeQueryEngine class (6 query methods)
└── formatters.py    # Output formatting (text, json, tree)
```

**Design Principles:**
1. **Database-First**: NO new schema - queries existing tables from `repo_index.db` and `graphs.db`
2. **Zero Inference**: Exact SQL queries with provenance - no guessing, no embeddings
3. **Performance-Obsessed**: Indexed lookups with O(1) hash maps and BFS for transitive queries
4. **Type-Safe Results**: Dataclasses (SymbolInfo, CallSite, Dependency) for structured returns
5. **Format-Agnostic**: Text (human), JSON (AI), tree (visualization) output modes

#### Database Schema Used

The query engine leverages existing indexed data:

**repo_index.db (required):**
- `symbols` (33k rows) - Function/class definitions (CRITICAL: uses `path` column, not `file`)
- `symbols_jsx` (8k rows) - JSX component definitions
- `function_call_args` (13k rows) - Function call sites with arguments
- `function_call_args_jsx` (4k rows) - JSX component usages
- `api_endpoints` (185 rows) - REST endpoint handlers
- `react_components` (1k rows) - React component metadata
- `react_hooks` (667 rows) - Hook usage tracking

**graphs.db (optional for dependency queries):**
- `edges` (7.3k rows) - Import and call relationships
- `nodes` (4.8k rows) - File/module nodes

**No schema changes required** - queries run on existing indexed data.

#### Query Methods

The `CodeQueryEngine` class provides 6 query methods:

**1. find_symbol(name, type_filter) → List[SymbolInfo]**
- Exact name match across `symbols` and `symbols_jsx` tables
- Returns: Symbol definitions with file, line, signature, export status
- Performance: <5ms (indexed by name)

**2. get_callers(symbol_name, depth=1) → List[CallSite]**
- BFS traversal for transitive caller discovery
- Queries: `function_call_args` WHERE `callee_function = ?`
- Depth 1-5 supported (default: 1 for direct callers only)
- Performance: <10ms direct, <50ms depth=3 transitive
- Cycle detection: Visited set prevents infinite loops

**3. get_callees(symbol_name) → List[CallSite]**
- What a function calls
- Queries: `function_call_args` WHERE `caller_function LIKE ?`
- Returns: Call sites with arguments and line numbers
- Performance: <10ms

**4. get_file_dependencies(file_path, direction='both') → Dict[str, List[Dependency]]**
- Import relationships from `graphs.db`
- Directions: 'incoming' (dependents), 'outgoing' (dependencies), 'both'
- Queries: `edges` WHERE `graph_type = 'import'`
- Performance: <10ms
- Graceful degradation: Returns error if graphs.db not built

**5. get_api_handlers(route_pattern) → List[Dict]**
- Find REST endpoint implementations
- Queries: `api_endpoints` WHERE `path LIKE ? OR pattern LIKE ?`
- Returns: Method, path, handler function, auth status, file location
- Performance: <5ms

**6. get_component_tree(component_name) → Dict**
- React component hierarchy
- Queries: `react_components`, `react_hooks`, `function_call_args_jsx`
- Returns: Component metadata, hooks used, child components
- Performance: <10ms

#### Transitive Query Algorithm (BFS)

For `get_callers(depth > 1)`, the engine uses Breadth-First Search:

```python
queue = deque([(symbol_name, 0)])
visited = set()

while queue:
    current_symbol, current_depth = queue.popleft()
    if current_depth >= depth:
        continue

    # Query direct callers
    callers = query_function_call_args(current_symbol)

    for caller in callers:
        caller_key = (caller.function, caller.file, caller.line)
        if caller_key not in visited:
            visited.add(caller_key)
            all_callers.append(caller)

            # Add to queue for next level
            if current_depth + 1 < depth:
                queue.append((caller.function, current_depth + 1))
```

**Why BFS?**
- Guarantees shortest path to each caller
- Level-order traversal (depth-aware)
- Cycle detection via visited set
- Memory-efficient (stores only unique caller keys)

#### Output Formatters

Three output modes via `formatters.py`:

**1. Text Format (default)** - Human-readable:
```
Symbol Definitions (1):
  1. authenticateUser
     Type: function
     File: backend/src/auth.ts:42-67
     Signature: (username: string, password: string) => Promise<User>
     Exported: Yes

Callers (3):
  1. backend/src/routes/login.ts:23
     handleLogin -> authenticateUser
     Args: req.body.username, req.body.password
```

**2. JSON Format** - AI-consumable structured data:
```json
{
  "symbol": [{
    "name": "authenticateUser",
    "type": "function",
    "file": "backend/src/auth.ts",
    "line": 42,
    "end_line": 67,
    "signature": "(username: string, password: string) => Promise<User>",
    "is_exported": true
  }],
  "callers": [...]
}
```

**3. Tree Format** - Visual hierarchy (placeholder, falls back to text):
```
└─ authenticateUser
   ├─ handleLogin (backend/src/routes/login.ts:23)
   ├─ validateCredentials (backend/src/middleware/auth.ts:15)
   └─ refreshSession (backend/src/sessions/refresh.ts:8)
```

#### Performance Characteristics

All queries leverage SQLite indexes:

| Query Type | Time | Method |
|------------|------|--------|
| Symbol lookup | <5ms | Indexed by name + type |
| Direct callers | <10ms | Indexed by callee_function |
| Transitive (depth=3) | <50ms | BFS with visited set |
| File dependencies | <10ms | Indexed by source/target + graph_type |
| API handlers | <5ms | Indexed by path pattern |
| Component tree | <10ms | Multiple indexed queries |

**Zero file I/O** - all data from SQLite databases with O(1) hash map lookups internally.

#### CLI Integration

Exposed via `aud context query` command:

```bash
# Symbol queries
aud context query --symbol authenticateUser --show-callers --depth 3
aud context query --symbol handleRequest --show-callees

# File queries
aud context query --file src/auth.ts --show-dependents
aud context query --file src/utils.ts --show-dependencies

# API queries
aud context query --api "/users/:id"

# Component queries
aud context query --component UserProfile

# Format control
aud context query --symbol validateInput --show-callers --format json
aud context query --file src/api.ts --format json --save deps.json
```

#### Integration with Existing Systems

The query engine is a **read-only consumer** of indexed data:
- **Indexer**: Populates tables during `aud index`
- **Graph Builder**: Creates edges/nodes during `aud graph build`
- **Query Engine**: Reads data, never writes

**No pipeline changes** - runs independently after indexing completes.

#### Error Handling

**Graceful degradation:**
- Missing `repo_index.db`: Raises FileNotFoundError with remediation
- Missing `graphs.db`: Returns error dict for dependency queries
- Missing tables (e.g., no JSX in Python projects): Silently skipped via try/except
- Empty results: Returns empty list (not an error)

**Helpful error messages:**
```python
# If database not found
FileNotFoundError: "Database not found: .pf/repo_index.db\nRun 'aud index' first to build the database."

# If graphs.db not built
{'error': 'Graph database not found. Run: aud graph build'}
```

#### Example: Token Savings Calculation

**Without query engine (traditional approach):**
```
AI reads auth.ts (500 tokens)
AI reads login.ts (300 tokens)
AI reads middleware/auth.ts (400 tokens)
AI reads sessions/refresh.ts (350 tokens)
Total: 1,550 tokens per iteration
10 iterations: 15,500 tokens
```

**With query engine:**
```
aud context query --symbol authenticateUser --show-callers --depth 2 --format json
Output: 150 tokens (structured call graph)
10 iterations: 1,500 tokens
Savings: 14,000 tokens (90% reduction)
```

#### Future Enhancements

Potential additions (not yet implemented):
- Tree format visualization (currently placeholder)
- Cross-file taint path queries
- SQL query builder for custom queries
- GraphQL schema traversal
- Database migration impact analysis

### Taint Analysis Package (`theauditor/taint/`)
Previously a monolithic file, the taint analysis system has been refactored into a modular package with 11 specialized modules. A backward compatibility shim remains at `theauditor/taint_analyzer.py` for legacy imports.

**Core capabilities:**
- Tracks data flow from user inputs to dangerous outputs
- Detects SQL injection, XSS, command injection, path traversal vulnerabilities
- Database-aware analysis using `repo_index.db`
- Supports both assignment-based and direct-use taint patterns
- Flow-sensitive CFG analysis for path-aware detection
- Inter-procedural tracking across function boundaries
- Language-specific handlers for JavaScript and Python constructs
- v1.2 memory cache: 8,461x speedup (4 hours → 30 seconds)

**Package structure:**
- `core.py`: Main TaintAnalyzer orchestration
- `sources.py`, `config.py`: 650+ source/sink/sanitizer patterns
- `propagation.py`: Worklist-based taint flow algorithm
- `cfg_integration.py`: Flow-sensitive path analysis
- `interprocedural.py`: Cross-function tracking
- `memory_cache.py`: In-memory O(1) lookup cache
- `javascript.py`, `python.py`: Language-specific construct handling
- `insights.py`: Shim to `theauditor/insights/taint.py` for optional severity scoring

### Graph Analysis (`theauditor/graph/`)
- **builder.py**: Constructs dependency graph from codebase
- **analyzer.py**: Detects cycles, measures complexity, identifies hotspots
- Uses NetworkX for graph algorithms

**Note**: The optional health scoring and recommendations are provided by `theauditor/insights/graph.py` (Insights module)

### Framework Detection (`theauditor/framework_detector.py`)
- Auto-detects Django, Flask, React, Vue, Angular, etc.
- Applies framework-specific rules
- Influences pattern selection and analysis behavior

### Configuration Parsers (`theauditor/parsers/`)
Specialized parsers for configuration file analysis:
- **webpack_config_parser.py**: Webpack configuration analysis
- **compose_parser.py**: Docker Compose file parsing
- **nginx_parser.py**: Nginx configuration parsing
- **dockerfile_parser.py**: Dockerfile security analysis
- **prisma_schema_parser.py**: Prisma ORM schema parsing

These parsers are used by extractors during indexing to extract security-relevant configuration data.

### Vulnerability Scanner (`theauditor/vulnerability_scanner.py`)

**OSV-Scanner: Offline-First Vulnerability Detection**

TheAuditor uses a 3-source cross-validation approach for vulnerability detection:
- **npm audit**: Checks npm registry for JavaScript/TypeScript vulnerabilities
- **pip-audit**: Checks PyPI for Python vulnerabilities
- **OSV-Scanner**: Google's official offline vulnerability database scanner

**OSV-Scanner Architecture**:
- **Binary Location**: `.auditor_venv/.theauditor_tools/osv-scanner/osv-scanner.exe` (Windows) or `osv-scanner` (Linux/Mac)
- **Database Location**: `.auditor_venv/.theauditor_tools/osv-scanner/db/{ecosystem}/all.zip`
- **Execution Mode**: 100% offline operation (ALWAYS uses `--offline-vulnerabilities` flag)
- **Database Updates**: Via `aud setup-ai --target .` command (one-time download)

**Why Offline-Only Design**:
1. **Feature-Rich Database**: Complete vulnerability data without API limitations
2. **Privacy**: No dependency information sent to external services
3. **Performance**: Local database queries are instant, no rate limits or network delays
4. **Reliability**: Works in air-gapped environments, no network dependencies
5. **Project-Agnostic**: Single database serves all projects (stored in sandbox)

**Database Contents**:
- npm ecosystem vulnerabilities (JavaScript/TypeScript)
- PyPI ecosystem vulnerabilities (Python)
- Cross-referenced with CVE, GHSA, OSV, and other advisory sources
- CWE classifications and severity ratings
- Detailed descriptions, references, and affected version ranges

**Cross-Validation Process**:
```python
# All 3 scanners run independently
npm_findings = _run_npm_audit()      # May hit npm registry (unless --offline)
pip_findings = _run_pip_audit()      # May hit PyPI (unless --offline)
osv_findings = _run_osv_scanner()    # ALWAYS uses local database

# Cross-reference findings by vulnerability ID
validated = _cross_reference(npm_findings, pip_findings, osv_findings)
# Confidence = number of sources that found the same vulnerability
```

**Key Implementation Detail** (`vulnerability_scanner.py:478-479`):
```python
# ALWAYS use offline database (never hit API)
cmd.append("--offline-vulnerabilities")
```

This ensures OSV-Scanner operates without network access regardless of the `--offline` flag to `aud full`. The offline flag only affects npm-audit and pip-audit registry checks.

### Refactoring Detection (`theauditor/commands/refactor.py`)
Detects incomplete refactorings and cross-stack inconsistencies:
- Analyzes database migrations to detect schema changes
- Uses impact analysis to trace affected files
- Applies correlation rules from `/correlations/rules/refactoring.yaml`
- Detects API contract mismatches, field migrations, foreign key changes
- Supports auto-detection from migration files or specific change analysis

## System Architecture Diagrams

### High-Level Data Flow

```mermaid
graph TB
    subgraph "Input Layer"
        CLI[CLI Commands]
        Files[Project Files]
    end
    
    subgraph "Core Pipeline"
        Index[Indexer]
        Framework[Framework Detector]
        Deps[Dependency Checker]
        Patterns[Pattern Detection]
        Taint[Taint Analysis]
        Graph[Graph Builder]
        FCE[Factual Correlation Engine]
    end
    
    subgraph "Storage"
        DB[(SQLite DB)]
        Raw[Raw Output]
        Chunks[65KB Chunks]
    end
    
    CLI --> Index
    Files --> Index
    Index --> DB
    Index --> Framework
    Framework --> Deps
    
    Deps --> Patterns
    Patterns --> Graph
    Graph --> Taint
    Taint --> FCE
    
    FCE --> Raw
    Raw --> Chunks
```

### Parallel Pipeline Execution (v1.1 4-Stage Architecture)

```mermaid
graph LR
    subgraph "Stage 1 - Foundation"
        S1[Index] --> S2[Framework Detection]
    end
    
    subgraph "Stage 2 - Data Prep"
        D1[Workset] --> D2[Graph Build] --> D3[CFG Analyze]
    end
    
    subgraph "Stage 3 - Parallel Heavy Analysis"
        direction TB
        subgraph "Track A - Taint"
            A1[Taint Analysis<br/>~30 seconds]
        end
        
        subgraph "Track B - Static & Graph"
            B1[Linting]
            B2[Patterns<br/>355x faster]
            B3[Graph Analyze]
            B4[Graph Viz]
            B1 --> B2 --> B3 --> B4
        end
        
        subgraph "Track C - Network I/O"
            C1[Deps Check]
            C2[Doc Fetch]
            C3[Doc Summary]
            C1 --> C2 --> C3
        end
    end
    
    subgraph "Stage 4 - Final"
        E1[FCE] --> E2[Report] --> E3[Summary]
    end
    
    S2 --> D1
    D3 --> A1
    D3 --> B1
    D3 --> C1
    
    A1 --> E1
    B4 --> E1
    C3 --> E1
```

### Data Chunking System

The extraction system (`theauditor/extraction.py`) implements pure courier model chunking:

```mermaid
graph TD
    subgraph "Analysis Results"
        P[Patterns.json]
        T[Taint.json<br/>Multiple lists merged]
        L[Lint.json]
        F[FCE.json]
    end
    
    subgraph "Extraction Process"
        E[Extraction Engine<br/>Budget: 1.5MB]
        M[Merge Logic<br/>For taint_paths +<br/>rule_findings]
        C1[Chunk 1<br/>0-65KB]
        C2[Chunk 2<br/>65-130KB]
        C3[Chunk 3<br/>130-195KB]
        TR[Truncation<br/>Flag]
    end
    
    subgraph "Output"
        R1[patterns_chunk01.json]
        R2[patterns_chunk02.json]
        R3[patterns_chunk03.json]
    end
    
    P --> E
    T --> M --> E
    L --> E
    F --> E
    
    E --> C1 --> R1
    E --> C2 --> R2
    E --> C3 --> R3
    E -.->|If >195KB| TR
    TR -.-> R3
```

Key features:
- **Budget system**: 1.5MB total budget for all chunks
- **Smart merging**: Taint analysis merges multiple finding lists (taint_paths, rule_findings, infrastructure)
- **Preservation**: All findings preserved, no filtering or sampling
- **Chunking**: Only chunks files >65KB, copies smaller files as-is

### Dual Environment Architecture

```mermaid
graph TB
    subgraph "Development Environment"
        V1[.venv/]
        PY[Python 3.11+]
        AU[TheAuditor Code]
        V1 --> PY --> AU
    end
    
    subgraph "Sandboxed Analysis Environment"
        V2[.auditor_venv/.theauditor_tools/]
        NODE[Bundled Node.js v20.11.1]
        TS[TypeScript Compiler]
        ES[ESLint]
        PR[Prettier]
        NM[node_modules/]
        V2 --> NODE
        NODE --> TS
        NODE --> ES
        NODE --> PR
        NODE --> NM
    end
    
    AU -->|Analyzes using| V2
    AU -.->|Never uses| V1
```

TheAuditor maintains strict separation between:
1. **Primary Environment** (`.venv/`): TheAuditor's Python code and dependencies
2. **Sandboxed Environment** (`.auditor_venv/.theauditor_tools/`): Isolated JS/TS analysis tools

This ensures reproducibility and prevents TheAuditor from analyzing its own analysis tools.

## Database Schema

```mermaid
erDiagram
    files ||--o{ symbols : contains
    files ||--o{ refs : contains
    files ||--o{ api_endpoints : contains
    files ||--o{ sql_queries : contains
    files ||--o{ docker_images : contains
    
    files {
        string path PK
        string language
        int size
        string hash
        json metadata
    }
    
    symbols {
        string path FK
        string name
        string type
        int line
        json metadata
    }
    
    refs {
        string src FK
        string value
        string kind
        int line
    }
    
    api_endpoints {
        string file FK
        string method
        string path
        int line
    }
    
    sql_queries {
        string file_path FK
        string command
        string query
        int line_number
    }
    
    docker_images {
        string file_path FK
        string base_image
        json env_vars
        json build_args
    }
```

## Schema Contract System (v1.1+)

TheAuditor enforces a strict "single source of truth" pattern for database schema management through the schema contract system located in `theauditor/indexer/schema.py`.

### Architecture Overview

The schema contract system provides:
- **Type-safe query building** - Validates column names at runtime before query execution
- **Schema validation** - Ensures database matches schema definitions
- **Code generation** - Generates CREATE TABLE statements from schema definitions
- **Centralized definitions** - All 40+ table schemas in one authoritative location

### TableSchema Class

The `TableSchema` dataclass represents a complete table definition:

```python
@dataclass
class TableSchema:
    name: str
    columns: List[Column]
    indexes: List[Tuple[str, List[str]]] = field(default_factory=list)
    primary_key: Optional[List[str]] = None  # Composite primary keys
    unique_constraints: List[List[str]] = field(default_factory=list)  # UNIQUE constraints
```

**Supported Constraint Types:**
- **Column-level constraints**: NOT NULL, DEFAULT, CHECK, PRIMARY KEY
- **Table-level constraints**: Composite PRIMARY KEY, UNIQUE(col1, col2, ...)
- **Indexes**: Performance optimization via CREATE INDEX statements

**FOREIGN KEY Design Pattern:**
FOREIGN KEY constraints are **intentionally omitted** from TableSchema definitions. This design choice:
- Keeps schema focused on table-level structure (columns, types, indexes)
- Decouples schema from relational integrity
- Avoids circular dependencies between table definitions
- Simplifies schema validation and code generation

Foreign keys are defined exclusively in `database.py` CREATE TABLE statements and are not validated by the schema contract system.

### Usage Examples

**Building Type-Safe Queries:**
```python
from theauditor.indexer.schema import build_query

# Build validated query
query = build_query('variable_usage', ['file', 'line', 'variable_name'])
cursor.execute(query)

# With WHERE clause
query = build_query('sql_queries', where="command != 'UNKNOWN'")
cursor.execute(query)
```

**Schema Validation:**
```python
from theauditor.indexer.schema import validate_all_tables

mismatches = validate_all_tables(cursor)
if mismatches:
    for table, errors in mismatches.items():
        logger.warning(f"Schema mismatch in {table}: {errors}")
```

### Recent Enhancements (v1.1+)

**JWT Patterns Table Synchronization:**
- Added missing `jwt_patterns` table to schema.py TABLES registry
- Complete TableSchema with 6 columns and 3 indexes
- Resolved P0 schema contract violation

**UNIQUE Constraint Support:**
- Extended TableSchema with `unique_constraints` field
- Enables full constraint representation and validation
- Example: `frameworks` table uses `UNIQUE(name, language, path)`
- Supports multiple UNIQUE constraints per table

**Design Pattern Documentation:**
- Codified FOREIGN KEY omission pattern in TableSchema docstring
- Explicit architectural rationale prevents future confusion
- Maintains separation of concerns: structure vs. relationships

### Key Tables

**Core Structure:**
- `files` - File metadata and hashes
- `symbols` - Code symbols (functions, classes, variables)
- `function_call_args` - Function call argument tracking

**Security Analysis:**
- `api_endpoints` - REST endpoint detection with auth flags
- `sql_queries` - SQL query extraction with command classification
- `jwt_patterns` - JWT usage pattern detection
- `variable_usage` - Variable usage tracking for taint analysis

**Data Flow (Taint Critical):**
- `assignments` - Variable assignments
- `function_returns` - Function return statements
- `taint_paths` - Computed taint flow paths

**Framework Detection:**
- `frameworks` - Detected frameworks with UNIQUE constraint
- `framework_safe_sinks` - Framework-specific safe output methods

See `theauditor/indexer/schema.py` for complete table definitions.

## Command Flow Sequence

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Pipeline
    participant Analyzers
    participant Database
    participant Output
    
    User->>CLI: aud full
    CLI->>Pipeline: Execute pipeline
    Pipeline->>Database: Initialize schema
    
    Pipeline->>Analyzers: Index files
    Analyzers->>Database: Store file metadata
    
    par Parallel Execution
        Pipeline->>Analyzers: Dependency check
        and
        Pipeline->>Analyzers: Pattern detection
        and
        Pipeline->>Analyzers: Graph building
    end
    
    Pipeline->>Analyzers: Taint analysis
    Analyzers->>Database: Query symbols & refs
    
    Pipeline->>Analyzers: FCE correlation
    Analyzers->>Output: Generate reports
    
    Pipeline->>Output: Create chunks
    Output->>User: .pf/readthis/
```

## Output Structure

All results are organized in the `.pf/` directory:

```
.pf/
├── raw/                # Immutable tool outputs (ground truth)
│   ├── eslint.json
│   ├── ruff.json
│   └── ...
├── readthis/           # AI-optimized chunks (<65KB each, max 3 chunks per file)
│   ├── manifest.md     # Repository overview
│   ├── patterns_*.md   # Security findings
│   ├── taint_*.md      # Data-flow issues
│   └── tickets_*.md    # Actionable tasks
├── repo_index.db       # SQLite database of code symbols
├── pipeline.log        # Execution trace
└── findings.json       # Consolidated results
```

### Key Output Files

- **manifest.md**: Complete file inventory with SHA-256 hashes
- **patterns_*.md**: Chunked security findings from 100+ detection rules
- **tickets_*.md**: Prioritized, actionable issues with evidence
- **repo_index.db**: Queryable database of all code symbols and relationships

## Operating Modes

TheAuditor operates in two distinct modes:

### Courier Mode (External Tools)
- Preserves exact outputs from ESLint, Ruff, MyPy, etc.
- No interpretation or filtering
- Complete audit trail from source to finding

### Expert Mode (Internal Engines)
- **Taint Analysis**: Tracks untrusted data through the application
- **Pattern Detection**: YAML-based rules with AST matching
- **Graph Analysis**: Architectural insights and dependency tracking
- **Secret Detection**: Identifies hardcoded credentials and API keys

## CLI Entry Points

- **Main CLI**: `theauditor/cli.py` - Central command router
- **Command modules**: `theauditor/commands/` - One module per command
- **Utilities**: `theauditor/utils/` - Shared functionality
- **Configuration**: `theauditor/config_runtime.py` - Runtime configuration

Each command module follows a standardized structure with:
- `@click.command()` decorator
- `@handle_exceptions` decorator for error handling
- Consistent logging and output formatting

## Performance Optimizations

### v1.2 Cache Architecture
TheAuditor v1.2 introduces a comprehensive caching system that transforms performance:

**In-Memory Caches:**
- **Taint Analysis Memory Cache** (`theauditor/taint/memory_cache.py`):
  - Pre-computed pattern matching with O(1) lookups
  - Multi-index architecture: by file, by pattern, by type
  - 4GB memory limit with graceful degradation
  - Result: 8,461x speedup (4 hours → 30 seconds)

- **AST Parser LRU Cache** (`theauditor/ast_parser.py`):
  - Increased from 500 to 10,000 entries
  - Content-hash based caching
  - Prevents re-parsing of unchanged files
  - Result: 20x speedup on re-analysis

- **CFG Analysis Cache** (`theauditor/cache/cfg_cache.py`):
  - SQLite-based persistent cache
  - Expanded from 10,000 to 25,000 function entries
  - LRU eviction when limit reached
  - Result: 10x speedup for flow analysis

**Managed Disk Caches:**
- **Graph Cache** (`theauditor/cache/graph_cache.py`):
  - SQLite with 100,000 edge limit
  - 50,000 file state limit
  - Incremental updates for changed files
  - Smart eviction based on file age

- **AST Disk Cache** (`theauditor/cache/ast_cache.py`):
  - JSON file storage with 1GB limit
  - Maximum 20,000 cached files
  - LRU eviction when limits exceeded
  - Prevents disk exhaustion

**Cache Preservation Strategy (v1.2+):**
TheAuditor preserves caches between runs by default to maximize performance:

- **Preserved Caches**:
  - `.pf/.cache/` - AST parsing cache
  - `.pf/context/` - Documentation cache (~1.6MB typical) and summaries

- **Archive Behavior**:
  - By default, `aud full` preserves caches when archiving previous runs
  - Caches are NOT moved to `.pf/history/` directories
  - Result: ~40-90s faster on subsequent runs (docs cache reuse)

- **Force Cache Rebuild**:
  ```bash
  aud full --wipecache  # Delete all caches before analysis
  ```
  - Use this flag for cache corruption recovery
  - Useful when dependency versions change significantly
  - Documentation cache will be rebuilt from npm/PyPI (rate-limited)

- **Implementation**:
  - Archive logic: `theauditor/commands/_archive.py`
  - Cache directory detection via `CACHE_DIRS` constant
  - Metadata tracking in `_metadata.json` files

**Performance Impact**:
- First run: Full analysis (~120s medium project)
- Subsequent runs: ~40-90s faster (cache hits)
- With `--wipecache`: Equivalent to first run

### Core Optimizations
- **Batched database operations**: 200 records per batch (configurable)
- **Parallel rule execution**: ThreadPoolExecutor with 4 workers
- **Incremental analysis**: Workset-based analysis for changed files only
- **Lazy loading**: Patterns and rules loaded on-demand
- **Memory-efficient chunking**: Stream large files instead of loading entirely
- **Pre-computation**: Taint patterns compiled at load time, not search time

## Configuration System

TheAuditor supports runtime configuration via multiple sources (priority order):

1. **Environment variables** (`THEAUDITOR_*` prefix)
2. **`.pf/config.json`** file (project-specific)
3. **Built-in defaults** in `config_runtime.py`

Example configuration:
```bash
export THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE=5  # Default: 3
export THEAUDITOR_LIMITS_MAX_CHUNK_SIZE=100000  # Default: 65000
export THEAUDITOR_LIMITS_MAX_FILE_SIZE=5242880  # Default: 2097152
export THEAUDITOR_TIMEOUTS_LINT_TIMEOUT=600     # Default: 300
```

## Advanced Features

### Database-Aware Rules
Specialized analyzers query `repo_index.db` to detect:
- ORM anti-patterns (N+1 queries, missing transactions)
- Docker security misconfigurations
- Nginx configuration issues
- Multi-file correlation patterns

### Holistic Analysis
Project-level analyzers that operate across the entire codebase:
- **Bundle Analyzer**: Correlates package.json, lock files, and imports
- **Source Map Detector**: Scans build directories for exposed maps
- **Framework Detectors**: Identify technology stack automatically

### Incremental Analysis
Workset-based analysis for efficient processing:
- Git diff integration for changed file detection
- Dependency tracking for impact analysis
- Cached results for unchanged files

## Contributing to TheAuditor

### Adding Language Support

TheAuditor's modular architecture makes it straightforward to add new language support:

#### 1. Create an Extractor
Create a new extractor in `theauditor/indexer/extractors/{language}.py`:

```python
from . import BaseExtractor

class {Language}Extractor(BaseExtractor):
    def supported_extensions(self) -> List[str]:
        return ['.ext', '.ext2']
    
    def extract(self, file_info, content, tree=None):
        # Extract symbols, imports, routes, etc.
        return {
            'imports': [],
            'routes': [],
            'symbols': [],
            # ... other extracted data
        }
```

The extractor will be automatically registered via the `BaseExtractor` inheritance.

#### 2. Create Configuration Parser (Optional)
For configuration files, create a parser in `theauditor/parsers/{language}_parser.py`:

```python
class {Language}Parser:
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        # Parse configuration file
        return parsed_data
```

#### 3. Add Security Patterns
Create YAML patterns in `theauditor/patterns/{language}.yml`:

```yaml
- name: hardcoded-secret-{language}
  pattern: 'api_key\s*=\s*["\'][^"\']+["\']'
  severity: critical
  category: security
  languages: ["{language}"]
  description: "Hardcoded API key in {Language} code"
```

#### 4. Add Framework Detection
Update `theauditor/framework_detector.py` to detect {Language} frameworks.

### Adding New Analyzers

#### Database-Aware Rules
Create analyzers that query `repo_index.db` in `theauditor/rules/{category}/`:

```python
def find_{issue}_patterns(db_path: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    # Query and analyze
    return findings
```

#### AST-Based Rules
For semantic analysis, create rules in `theauditor/rules/{framework}/`:

```python
def find_{framework}_issues(tree, file_path) -> List[Dict[str, Any]]:
    # Traverse AST and detect issues
    return findings
```

#### Pattern-Based Rules
Add YAML patterns to `theauditor/patterns/` for regex-based detection.

### Architecture Guidelines

1. **Maintain Truth Courier vs Insights separation** - Core modules report facts, insights add interpretation
2. **Use the extractor registry** - Inherit from `BaseExtractor` for automatic registration
3. **Follow existing patterns** - Look at `python.py` or `javascript.py` extractors as examples
4. **Write comprehensive tests** - Test extractors, parsers, and patterns
5. **Document your additions** - Update this file and CONTRIBUTING.md

For detailed contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).