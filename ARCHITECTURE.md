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