# TheAuditor Architecture Documentation

> Comprehensive system architecture with data flow diagrams for AI assistants and developers.
>
> **Last Updated**: 2025-11-25
> **Version**: 1.6.4-dev1

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Two-Database Philosophy](#2-two-database-philosophy)
3. [AST Parsing Layer](#3-ast-parsing-layer)
4. [Extraction Layer](#4-extraction-layer)
5. [Indexer Layer](#5-indexer-layer)
6. [Storage Layer](#6-storage-layer)
7. [Graph Layer](#7-graph-layer)
8. [Taint Analysis & FCE](#8-taint-analysis--fce)
9. [Rules Engine](#9-rules-engine)
10. [Complete Data Flow Examples](#10-complete-data-flow-examples)
11. [Critical Architectural Rules](#11-critical-architectural-rules)
12. [Key Files Reference](#12-key-files-reference)

---

## 1. High-Level Architecture

TheAuditor is an offline-first, AI-centric SAST platform with a **strict three-phase architecture**:

```mermaid
flowchart TB
    subgraph Phase1["Phase 1: Indexing (aud full)"]
        FW[FileWalker<br/>core.py] --> AST[AST Parser<br/>ast_parser.py]
        AST --> EXT[Extractors<br/>extractors/*.py]
        EXT --> STORE[Storage Layer<br/>storage/*.py]
        STORE --> DB1[(repo_index.db<br/>181MB, 250 tables)]
    end

    subgraph Phase2["Phase 2: Graph Building (aud graph build)"]
        DB1 --> CACHE[GraphDatabaseCache<br/>db_cache.py]
        CACHE --> BUILD[XGraphBuilder<br/>builder.py]
        BUILD --> DFG[DFGBuilder<br/>dfg_builder.py]
        DFG --> DB2[(graphs.db<br/>126MB, 3 tables)]
    end

    subgraph Phase3["Phase 3: Analysis"]
        DB1 --> RULES[Rules Engine<br/>orchestrator.py]
        DB2 --> TAINT[Taint Analysis<br/>taint/*.py]
        RULES --> FIND[(findings_consolidated)]
        TAINT --> FIND
        FIND --> FCE[FCE Aggregation<br/>fce.py]
        FCE --> OUT[fce_output.json]
    end

    style Phase1 fill:#e1f5fe
    style Phase2 fill:#fff3e0
    style Phase3 fill:#f3e5f5
```

### Architecture Principles

| Principle | Description |
|-----------|-------------|
| **Database-First** | ALL data flows through SQLite. No JSON file fallbacks. |
| **Zero Fallback** | Missing data = crash loudly. No silent degradation. |
| **Language-Specific Excellence** | Each language gets its best parser, not generic solutions. |
| **Facts vs Interpretations** | Raw facts in database, interpretations in .pf/insights/. |

---

## 2. Two-Database Philosophy

### Why Two Databases?

```mermaid
flowchart LR
    subgraph repo["repo_index.db (181MB)"]
        direction TB
        R1[files]
        R2[symbols]
        R3[assignments]
        R4[function_call_args]
        R5[sql_queries]
        R6["... 245 more tables"]
    end

    subgraph graphs["graphs.db (126MB)"]
        direction TB
        G1[nodes]
        G2[edges]
        G3[analysis_results]
    end

    repo -->|"XGraphBuilder reads"| graphs

    style repo fill:#bbdefb
    style graphs fill:#ffe0b2
```

| Database | Purpose | Updated | Used By |
|----------|---------|---------|---------|
| **repo_index.db** | Raw extracted facts from AST | Fresh every `aud full` | Everything (rules, taint, FCE, queries) |
| **graphs.db** | Pre-computed graph structures | `aud graph build` phase | Graph commands, IFDS analyzer |

### Key Insight

FCE reads from **repo_index.db**, NOT graphs.db. The graph database is optional for visualization/exploration only.

---

## 3. AST Parsing Layer

### Parser Selection Strategy

```mermaid
flowchart TD
    FILE[Source File] --> CHECK{Extension?}

    CHECK -->|.py, .pyx| PYTHON[CPython ast.parse<br/>Native, zero deps]
    CHECK -->|.js, .jsx, .ts, .tsx| TS[TypeScript Compiler API<br/>Semantic + types]
    CHECK -->|.tf, .rs, .hcl| TREE[Tree-sitter<br/>Flexible configs]

    PYTHON --> OUT[AST Tree]
    TS --> OUT
    TREE --> OUT

    style PYTHON fill:#c8e6c9
    style TS fill:#bbdefb
    style TREE fill:#fff9c4
```

### File: `theauditor/ast_parser.py` (645 lines)

**Why NOT Tree-sitter for Python?**
- Tree-sitter produces different node types (`.type`, `.children`, `.text`)
- Extractors expect CPython types (`ast.Module`, `ast.FunctionDef`, `ast.Name`)
- Silent fallbacks corrupt databases (incident: 2025-10-16)

### AST Output Formats

```python
# Python (CPython ast)
{"type": "python_ast", "tree": <ast.Module>, "content": str}

# JavaScript/TypeScript (Semantic)
{
    "type": "semantic_ast",
    "tree": semantic_result,
    "symbols": [...],
    "extracted_data": {
        "symbols": [...],
        "function_calls": [...],
        "cfg": [...]
    }
}

# Tree-Sitter (HCL, Rust)
{"type": "tree_sitter", "tree": tree_object, "content": str}
```

---

## 4. Extraction Layer

### Extractor Registry Architecture

```mermaid
flowchart TB
    subgraph Registry["ExtractorRegistry (Auto-Discovery)"]
        SCAN["Scan extractors/*.py"] --> IMPORT["Dynamic import"]
        IMPORT --> FIND["Find BaseExtractor subclass"]
        FIND --> REG["Register for extensions"]
    end

    subgraph Extractors["Language-Specific Extractors"]
        PY["PythonExtractor<br/>.py, .pyx"]
        JS["JavaScriptExtractor<br/>.js, .jsx, .ts, .tsx"]
        SQL["SQLExtractor<br/>.sql"]
        TF["TerraformExtractor<br/>.tf, .tfvars"]
        RS["RustExtractor<br/>.rs"]
        GQL["GraphQLExtractor<br/>.graphql"]
    end

    Registry --> Extractors

    style Registry fill:#e8f5e9
```

### Python Extraction Path

```mermaid
flowchart LR
    subgraph Python["Python Extraction (263 lines)"]
        AST[CPython AST] --> CTX[FileContext<br/>O(1) NodeIndex]
        CTX --> IMPL[python_impl.py<br/>1,033 lines]
        IMPL --> MODS["Extractor Modules"]
    end

    MODS --> OUT["{'symbols': [...],<br/>'imports': [...],<br/>'assignments': [...],<br/>... 40+ keys}"]

    style Python fill:#c8e6c9
```

**Key Files:**
- `theauditor/indexer/extractors/python.py` (263 lines) - Wrapper
- `theauditor/ast_extractors/python_impl.py` (1,033 lines) - Orchestrator
- `theauditor/ast_extractors/python/utils/context.py` - FileContext

### JavaScript/TypeScript Extraction Path

```mermaid
flowchart LR
    subgraph JS["JS/TS Extraction (1,674 lines)"]
        SEM[Semantic AST<br/>from TypeScript API] --> PRE["Pre-extracted data<br/>(symbols, calls, cfg)"]
        PRE --> FW["Framework Analysis<br/>(React, Vue, Angular)"]
        FW --> POST["Post-Processing<br/>(SQL, JWT, routes)"]
    end

    POST --> OUT["Unified extraction dict"]

    style JS fill:#bbdefb
```

**Three-Phase Architecture:**
1. **Phase 1**: Receive pre-extracted data from TypeScript Compiler API
2. **Phase 2**: Framework analysis (React, Vue, Angular detection)
3. **Phase 3**: Post-processing (SQL patterns, JWT, routes)

### Extraction Output Structure

```python
{
    # Core language (all languages)
    'symbols': [{'name': 'func', 'type': 'function', 'line': 5}],
    'imports': [{'target': 'os', 'type': 'import', 'line': 1}],
    'assignments': [{'target': 'x', 'source': 'y', 'line': 10}],
    'function_calls': [{'callee': 'func', 'args': [...], 'line': 15}],
    'returns': [{'value': 'x', 'line': 20, 'in_function': 'bar'}],
    'cfg': [{'block_id': 1, 'type': 'entry', 'statements': [...]}],

    # Security patterns
    'sql_queries': [{'query': 'SELECT...', 'parameterized': False}],
    'jwt_patterns': [{'pattern': 'jwt.sign', 'line': 40}],

    # Framework-specific
    'routes': [{'method': 'GET', 'pattern': '/', 'handler': 'index'}],
    'react_components': [{'name': 'Button', 'type': 'function'}],
    'python_django_views': [...],

    # Resolution metadata
    'resolved_imports': {'os': 'os', 'django': '/lib/django/__init__.py'}
}
```

---

## 5. Indexer Layer

### Orchestrator Pipeline

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant FW as FileWalker
    participant AST as ASTParser
    participant EXT as Extractor
    participant ST as DataStorer
    participant DB as repo_index.db

    O->>FW: walk()
    FW-->>O: [file_info, ...]

    loop Batch JS/TS
        O->>AST: parse_files_batch()
        AST-->>O: cached trees
    end

    loop Each File
        O->>AST: get_or_parse_ast()
        O->>EXT: extract(file_info, content, tree)
        EXT-->>O: extracted_data
        O->>ST: store(file_path, extracted)
        ST->>DB: INSERT INTO tables
    end

    Note over O: JSX Second Pass (preserved mode)
    loop JSX Files
        O->>AST: parse(jsx_mode='preserved')
        O->>EXT: extract()
        O->>ST: store(jsx_pass=True)
        ST->>DB: INSERT INTO *_jsx tables
    end
```

### File: `theauditor/indexer/orchestrator.py` (786 lines)

**Key Methods:**
| Method | Lines | Purpose |
|--------|-------|---------|
| `index()` | 222-613 | Main pipeline entry point |
| `_process_file()` | 615-688 | Single file processing |
| `_select_extractor()` | 724-743 | Route to correct extractor |

### JSX Dual-Pass Architecture

**Problem**: TypeScript compiler only supports ONE JSX mode at a time.

```mermaid
flowchart TB
    JSX[JSX File] --> P1["Pass 1: Transformed<br/>JSX → React.createElement()"]
    JSX --> P2["Pass 2: Preserved<br/>Keep JSX syntax"]

    P1 --> T1["Standard tables<br/>(symbols, assignments, cfg)"]
    P2 --> T2["JSX tables<br/>(symbols_jsx, assignments_jsx)"]

    T1 --> TAINT["Taint Analysis<br/>(sees function calls)"]
    T2 --> STRUCT["Structural Rules<br/>(accessibility, composition)"]

    style P1 fill:#bbdefb
    style P2 fill:#ffe0b2
```

---

## 6. Storage Layer

### Handler Architecture

```mermaid
flowchart TB
    subgraph DataStorer["DataStorer (storage/__init__.py)"]
        ROUTE["Route by data type"]
    end

    subgraph Handlers["Domain Handlers"]
        CORE["CoreStorage<br/>23 handlers<br/>imports, symbols, cfg, sql, jwt"]
        PY["PythonStorage<br/>148 handlers<br/>Django, Flask, Celery, pytest"]
        NODE["NodeStorage<br/>17 handlers<br/>React, Vue, TypeScript"]
        INFRA["InfraStorage<br/>11 handlers<br/>Docker, Terraform, CDK"]
    end

    DataStorer --> Handlers

    subgraph DB["DatabaseManager"]
        MIX["8 Mixins<br/>97 total methods"]
        BATCH["Generic batch system<br/>executemany()"]
    end

    Handlers --> DB
    DB --> SQLITE[(repo_index.db)]

    style DataStorer fill:#e8f5e9
    style DB fill:#fff3e0
```

### Schema Organization (250 tables, 8 domains)

```mermaid
pie title Schema Domains
    "Core (24)" : 24
    "Security (7)" : 7
    "Frameworks (6)" : 6
    "Python (149)" : 149
    "Node (29)" : 29
    "Infrastructure (18)" : 18
    "Planning (9)" : 9
    "GraphQL (8)" : 8
```

**File: `theauditor/indexer/schema.py` (582 lines)**

### Storage File Sizes

| Module | Lines | Handlers | Purpose |
|--------|-------|----------|---------|
| `core_storage.py` | 641 | 23 | Cross-language patterns |
| `python_storage.py` | 2,486 | 148 | Django, Flask, SQLAlchemy, Celery |
| `node_storage.py` | 354 | 17 | React, Vue, Angular, TypeScript |
| `infrastructure_storage.py` | 229 | 11 | Docker, Terraform, CDK, GitHub Actions |

---

## 7. Graph Layer

### Graph Construction Pipeline

```mermaid
flowchart TB
    subgraph Input["Input: repo_index.db"]
        FILES[files table]
        REFS[refs table]
        SYMBOLS[symbols table]
        CALLS[function_call_args]
        ASSIGN[assignments]
        RETURNS[function_returns]
    end

    subgraph Cache["GraphDatabaseCache (O(1) lookups)"]
        BULK["Bulk load once<br/>~0.1s for 360 files"]
    end

    subgraph Builders["Graph Builders"]
        IMPORT["build_import_graph()<br/>File dependencies"]
        CALL["build_call_graph()<br/>Function relationships"]
        DFG["build_data_flow_graph()<br/>Variable flows"]
    end

    subgraph Output["Output: graphs.db"]
        NODES[nodes table]
        EDGES[edges table]
        ANALYSIS[analysis_results]
    end

    Input --> Cache
    Cache --> Builders
    Builders --> Output

    style Cache fill:#fff9c4
```

### Graph Schema (Polymorphic Design)

```sql
-- nodes table: All graph node types
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,      -- "file::function" or "module_id"
    file TEXT,
    lang TEXT,                -- 'python', 'typescript', etc.
    loc INTEGER,              -- Lines of code
    churn INTEGER,            -- Git commit count
    type TEXT,                -- 'module', 'function', 'variable'
    graph_type TEXT,          -- 'import', 'call', 'data_flow'
    metadata JSON
);

-- edges table: All relationship types
CREATE TABLE edges (
    id INTEGER PRIMARY KEY,
    source TEXT,              -- Source node ID
    target TEXT,              -- Target node ID
    type TEXT,                -- 'import', 'call', 'assignment', 'return'
    file TEXT,
    line INTEGER,
    graph_type TEXT,
    metadata JSON,
    UNIQUE(source, target, type, graph_type)
);
```

### Data Flow Graph (DFG)

```mermaid
flowchart LR
    subgraph DFGBuilder["DFGBuilder (dfg_builder.py)"]
        A["assignments +<br/>assignment_sources"] --> FORWARD["Forward edges<br/>(source → target)"]
        R["function_returns +<br/>function_return_sources"] --> REVERSE["Reverse edges<br/>(target → source)"]
    end

    FORWARD --> GRAPH["Unified DFG<br/>(bidirectional)"]
    REVERSE --> GRAPH

    GRAPH --> IFDS["IFDS Backward Analysis<br/>(10-hop tracing)"]

    style DFGBuilder fill:#e8f5e9
```

**Key Insight**: Bidirectional edges enable both ancestor and descendant queries for IFDS backward analysis.

**File: `theauditor/graph/dfg_builder.py` (950 lines)**

---

## 8. Taint Analysis & FCE

### Taint Analysis Architecture

```mermaid
flowchart TB
    subgraph Discovery["Discovery Phase"]
        RULES["200+ Rules"] -->|"register_source/sink"| REG["TaintRegistry"]
    end

    subgraph Analysis["Analysis Phase (trace_taint)"]
        REG --> MODE{Mode?}
        MODE -->|backward| IFDS["IFDSTaintAnalyzer<br/>10-hop IFDS"]
        MODE -->|forward| FLOW["FlowResolver<br/>Complete flows"]
        MODE -->|complete| BOTH["Both engines"]
    end

    subgraph Sources["Data Sources"]
        DB1[(repo_index.db)] --> IFDS
        DB2[(graphs.db)] --> IFDS
        DB1 --> FLOW
    end

    subgraph Output["Output"]
        IFDS --> PATHS["taint_paths"]
        FLOW --> AUDIT["resolved_flow_audit"]
        PATHS --> FIND[(findings_consolidated)]
        AUDIT --> FIND
    end

    style Discovery fill:#e8f5e9
    style Analysis fill:#bbdefb
```

### Taint Directory Structure

```
theauditor/taint/
├── core.py           (921 lines)  - Main orchestrator + TaintRegistry
├── ifds_analyzer.py  (629 lines)  - IFDS backward analysis
├── flow_resolver.py  (777 lines)  - Forward flow resolution
├── discovery.py      (695 lines)  - Database-driven source/sink discovery
├── access_path.py    (246 lines)  - Field-sensitive tracking (k=5)
├── sanitizer_util.py (299 lines)  - Sanitizer detection
└── orm_utils.py      (305 lines)  - ORM-aware taint tracking
```

### FCE Aggregation Pipeline

```mermaid
flowchart TB
    subgraph Sources["Data Sources"]
        F1["findings_consolidated"]
        F2["graphql_findings_cache"]
        F3["resolved_flow_audit"]
        F4[".pf/insights/*.json"]
    end

    subgraph Loaders["FCE Loaders (fce.py)"]
        L1["scan_all_findings()"]
        L2["load_taint_data_from_db()"]
        L3["load_graphql_findings_from_db()"]
        L4["load_workflow_data_from_db()"]
        L5["load_graph_data_from_db()"]
    end

    subgraph Output["FCE Output"]
        OUT["fce_output.json"]
        ALL["all_findings: [...]"]
        TAINT["taint_paths: [...]"]
        INSIGHTS["insights: {...}"]
    end

    Sources --> Loaders
    Loaders --> Output

    style Loaders fill:#f3e5f5
```

### FCE Performance

| Operation | Time | Reason |
|-----------|------|--------|
| `scan_all_findings()` | 100-500ms | O(log n) indexed SQL |
| Read JSON files (old) | 10-30s | O(n*m) file I/O |
| IFDS backward taint | 5-30s | 10-hop graph traversal |
| FlowResolver forward | 30-120s | Complete codebase traversal |

---

## 9. Rules Engine

### Rule Discovery & Execution

```mermaid
flowchart TB
    subgraph Discovery["Rule Discovery (_discover_all_rules)"]
        WALK["Walk theauditor/rules/"] --> IMPORT["Dynamic import *.py"]
        IMPORT --> FIND["Find find_* functions"]
        FIND --> ANALYZE["_analyze_rule()<br/>Extract metadata"]
    end

    subgraph Categories["20+ Rule Categories"]
        AUTH["auth/"]
        SQL["sql/"]
        XSS["xss/"]
        GQL["graphql/"]
        REACT["react/"]
        VUE["vue/"]
        MORE["..."]
    end

    subgraph Execution["Rule Execution"]
        CTX["StandardRuleContext"]
        RUN["run_all_rules()"]
        STORE["Store to findings_consolidated"]
    end

    Discovery --> Categories
    Categories --> Execution

    style Discovery fill:#e8f5e9
    style Execution fill:#bbdefb
```

### Rule Types

| Type | Receives | Example |
|------|----------|---------|
| `standalone` | StandardRuleContext | `sql_injection_analyze.py` |
| `discovery` | StandardRuleContext + taint_registry | Framework pattern registration |
| `taint-dependent` | StandardRuleContext + taint_checker | Check if variable is tainted |

### StandardRuleContext (Unified Input)

```python
@dataclass
class StandardRuleContext:
    # Required
    file_path: Path
    content: str
    language: str           # 'python', 'javascript', etc.
    project_path: Path

    # Optional (lazy-loaded)
    ast_wrapper: dict | None
    db_path: str | None
    taint_checker: Callable | None

    # Metadata
    file_hash: str | None
    file_size: int | None
    line_count: int | None

    # Helper methods
    def get_ast(expected_type: str = None) -> Any
    def get_lines() -> list[str]
    def get_snippet(line: int, context: int = 2) -> str
```

---

## 10. Complete Data Flow Examples

### Example 1: Python Import Extraction

```mermaid
sequenceDiagram
    participant FW as FileWalker
    participant O as Orchestrator
    participant AST as ASTParser
    participant EXT as PythonExtractor
    participant CTX as FileContext
    participant IMPL as python_impl.py
    participant ST as DataStorer
    participant DB as repo_index.db

    FW->>O: yield {'path': 'src/app.py', 'ext': '.py'}
    O->>AST: parse_file('src/app.py')
    AST-->>O: {'type': 'python_ast', 'tree': <Module>}

    O->>EXT: extract(file_info, content, tree)
    EXT->>CTX: build_file_context(tree, content, path)
    CTX-->>EXT: FileContext with NodeIndex

    EXT->>IMPL: extract_all_python_data(context)
    IMPL-->>EXT: {'imports': [...], 'symbols': [...], ...}
    EXT-->>O: extracted_data

    O->>ST: store('src/app.py', extracted)
    ST->>DB: INSERT INTO refs VALUES (...)
    ST->>DB: INSERT INTO symbols VALUES (...)
```

### Example 2: SQL Injection Detection

```mermaid
sequenceDiagram
    participant CLI as aud detect-patterns
    participant O as RulesOrchestrator
    participant R as sql_injection_analyze
    participant DB as repo_index.db
    participant F as findings_consolidated
    participant FCE as fce.py

    CLI->>O: run_all_rules()
    O->>O: _discover_all_rules()
    O->>R: analyze(StandardRuleContext)

    R->>DB: SELECT FROM sql_queries WHERE interpolation
    DB-->>R: [vulnerable queries]
    R->>DB: SELECT FROM symbols WHERE name IN ('execute', 'raw')
    DB-->>R: [raw SQL executions]
    R-->>O: [StandardFinding, ...]

    O->>F: INSERT findings

    Note over FCE: Later: aud fce
    FCE->>F: scan_all_findings()
    F-->>FCE: All findings including sql_injection
    FCE-->>CLI: fce_output.json
```

### Example 3: Taint Path Tracing

```mermaid
sequenceDiagram
    participant CLI as aud taint-analyze
    participant T as trace_taint()
    participant IFDS as IFDSTaintAnalyzer
    participant GDB as graphs.db
    participant RDB as repo_index.db
    participant F as findings_consolidated

    CLI->>T: trace_taint(mode='backward')
    T->>IFDS: analyze_sink_to_sources(sink, sources)

    loop 10-hop backward traversal
        IFDS->>GDB: Query backward edges
        GDB-->>IFDS: DFG edges
        IFDS->>RDB: Query function boundaries
        RDB-->>IFDS: Symbol info
    end

    IFDS-->>T: (vulnerable_paths, sanitized_paths)
    T->>F: INSERT taint findings
    T-->>CLI: taint_paths
```

---

## 11. Critical Architectural Rules

### ZERO FALLBACK POLICY

**BANNED FOREVER:**

```python
# 1. Database Query Fallbacks
cursor.execute("SELECT * FROM table WHERE name = ?", (normalized_name,))
result = cursor.fetchone()
if not result:  # <- THIS IS CANCER
    cursor.execute("SELECT * FROM table WHERE name = ?", (original_name,))

# 2. Try-Except Fallbacks
try:
    data = load_from_database()
except Exception:  # <- THIS IS CANCER
    data = load_from_json()

# 3. Table Existence Checks
if 'function_call_args' in existing_tables:  # <- THIS IS CANCER
    cursor.execute("SELECT * FROM function_call_args")
```

**CORRECT Pattern:**

```python
cursor.execute("SELECT path FROM symbols WHERE name = ?", (name,))
result = cursor.fetchone()
if not result:
    if debug:
        print(f"Symbol not found: {name}")  # Expose the bug
    continue  # Skip - DO NOT try alternative query
```

### Other Critical Rules

| Rule | Description |
|------|-------------|
| **No File Paths in Extractors** | Extractors return data WITHOUT file_path. Indexer provides it. |
| **Schema-Driven Everything** | All tables from TABLES registry. No hardcoded CREATE TABLE. |
| **AST-First, String-Fallback** | Use AST for code. String patterns ONLY for config files. |
| **Dual-Pass JSX** | Parse same file twice for data flow AND structure. |

---

## 12. Key Files Reference

### By Layer

| Layer | File | Lines | Purpose |
|-------|------|-------|---------|
| **AST** | `ast_parser.py` | 645 | Language router |
| **Extraction** | `extractors/__init__.py` | 274 | Registry |
| **Extraction** | `extractors/python.py` | 263 | Python wrapper |
| **Extraction** | `extractors/javascript.py` | 1,674 | JS/TS wrapper |
| **Extraction** | `ast_extractors/python_impl.py` | 1,033 | Python orchestrator |
| **Extraction** | `ast_extractors/typescript_impl.py` | 1,334 | TS extraction |
| **Indexer** | `indexer/orchestrator.py` | 786 | Main pipeline |
| **Schema** | `indexer/schema.py` | 581 | Schema registry |
| **Database** | `indexer/database/__init__.py` | 108 | 8 mixin composition |
| **Database** | `indexer/database/base_database.py` | 700 | Core infrastructure |
| **Storage** | `indexer/storage/__init__.py` | 103 | Handler router |
| **Storage** | `indexer/storage/core_storage.py` | 641 | 23 handlers |
| **Graph** | `graph/builder.py` | 1,131 | Import + call graphs |
| **Graph** | `graph/dfg_builder.py` | 950 | Data flow graph |
| **Graph** | `graph/store.py` | 422 | SQLite persistence |
| **Graph** | `graph/analyzer.py` | 485 | Graph algorithms |
| **Taint** | `taint/core.py` | 921 | Orchestrator + registry |
| **Taint** | `taint/ifds_analyzer.py` | 629 | IFDS backward |
| **Taint** | `taint/flow_resolver.py` | 777 | Forward resolution |
| **FCE** | `fce.py` | 1,845 | Aggregation |
| **Rules** | `rules/orchestrator.py` | 944 | Discovery + execution |

### Database Tables (Most Important)

| Table | Database | Purpose |
|-------|----------|---------|
| `files` | repo_index.db | All source files with metadata |
| `symbols` | repo_index.db | Functions, classes, variables |
| `refs` | repo_index.db | Import references |
| `assignments` | repo_index.db | Variable assignments |
| `function_call_args` | repo_index.db | Function calls with arguments |
| `sql_queries` | repo_index.db | SQL query patterns |
| `jwt_patterns` | repo_index.db | JWT security patterns |
| `findings_consolidated` | repo_index.db | ALL rule findings |
| `resolved_flow_audit` | repo_index.db | Complete flow provenance |
| `nodes` | graphs.db | Graph nodes (polymorphic) |
| `edges` | graphs.db | Graph edges (polymorphic) |
| `analysis_results` | graphs.db | Cached analysis (cycles, hotspots) |

---

## Summary Diagram

```mermaid
flowchart TB
    subgraph Files["Source Files"]
        PY[".py"]
        TS[".ts/.tsx"]
        TF[".tf"]
    end

    subgraph Phase1["INDEXING"]
        AST["AST Parser"]
        EXT["Extractors"]
        STORE["Storage"]
    end

    subgraph DB1["repo_index.db"]
        TABLES["250 tables<br/>8 domains"]
    end

    subgraph Phase2["GRAPH BUILD"]
        BUILD["XGraphBuilder"]
        DFG["DFGBuilder"]
    end

    subgraph DB2["graphs.db"]
        GRAPH["3 polymorphic tables"]
    end

    subgraph Phase3["ANALYSIS"]
        RULES["200+ Rules"]
        TAINT["Taint (IFDS/Forward)"]
        FCE["FCE Aggregation"]
    end

    subgraph Output["OUTPUT"]
        JSON["fce_output.json"]
        INSIGHTS[".pf/insights/"]
    end

    Files --> Phase1
    Phase1 --> DB1
    DB1 --> Phase2
    Phase2 --> DB2
    DB1 --> Phase3
    DB2 --> Phase3
    Phase3 --> Output

    style Phase1 fill:#e1f5fe
    style Phase2 fill:#fff3e0
    style Phase3 fill:#f3e5f5
```

---

**Document End**

*This document is auto-generated from codebase analysis. Keep synchronized with actual implementation.*
