# TheAuditor Architecture

A comprehensive polyglot security analysis platform with modular architecture for deep code understanding, vulnerability detection, and code context intelligence.

---

## System Overview

```
                                    USER INPUT
                                         |
                                         v
                              +------------------+
                              |   CLI Commands   |  (30+ commands, 9 categories)
                              +------------------+
                                         |
                    +--------------------+--------------------+
                    |                    |                    |
                    v                    v                    v
          +-----------------+   +-----------------+   +-----------------+
          |    Pipeline     |   |     Query       |   |    Session      |
          |  Orchestrator   |   |     System      |   |    Analyzer     |
          +-----------------+   +-----------------+   +-----------------+
                    |                    |                    |
    +---------------+---------------+    |                    |
    |               |               |    |                    |
    v               v               v    v                    v
+-------+     +--------+     +---------+----+           +---------+
|Indexer|---->|  AST   |---->|   Graph      |           | MachineL|
|       |     |Extract |     |   Engine     |           |   (ML)  |
+-------+     +--------+     +------+-------+           +---------+
    |               |               |                         ^
    v               v               v                         |
+-------+     +--------+     +---------+                      |
|Linters|     | Rules  |     |  Taint  |                      |
|       |     |Orchestr|     | Engine  |                      |
+-------+     +--------+     +---------+                      |
    |               |               |                         |
    +-------+-------+-------+-------+                         |
            |               |                                 |
            v               v                                 |
      +-----------+   +-----------+                           |
      |    FCE    |   |  Context  |--------------------------+
      | (Evidence)|   |   Query   |
      +-----------+   +-----------+
            |               |
            v               v
      +--------------------------+
      |    SQLite Databases      |
      |  repo_index.db (181MB)   |
      |  graphs.db (126MB)       |
      +--------------------------+
```

---

## Core Design Principles

| Principle | Description |
|-----------|-------------|
| **Zero Fallback** | No silent failures. If a parser fails, analysis fails visibly. |
| **Database-First** | Query indexed facts, never re-parse files during analysis. |
| **Manifest-Receipt Pairing** | Every extraction paired with verification receipt. |
| **Polyglot Native** | 7+ languages with unified extraction format. |
| **Evidence Over Opinion** | FCE provides facts, not subjective risk scores. |

---

## Engine 1: Indexer + Fidelity System

The **foundation layer** that transforms source code into queryable facts with cryptographic integrity verification.

### Architecture

```
Source Files → AST Parser → Extractors → DataStorer → SQLite
                                ↓
                          Fidelity Token
                          (manifest/receipt)
```

### The "Holy Trio" Fidelity System

**Purpose**: Prevents storage layer bugs from silently dropping data. This catches issues like incorrect SQL INSERTs, schema mismatches, or database connection failures.

**What it does NOT catch**: Human coding errors in extractors (e.g., incorrectly classifying a class as a variable). The fidelity system verifies "data extracted" matches "data stored" - it cannot validate semantic correctness.

**1. Manifest Generation** (`fidelity_utils.py`)
```python
token = {
    "count": len(data),           # Items extracted
    "tx_id": str(uuid.uuid4()),   # Transaction ID
    "columns": sorted(columns),    # Schema verification
    "bytes": byte_size,           # Data size
}
```

**2. Receipt Generation** (DataStorer)
- Storage layer echoes back tx_id with actual stored counts
- Enables comparison of "what was found" vs "what was saved"

**3. Reconciliation** (`fidelity.py`)
- **Transaction Mismatch**: `m_tx != r_tx` → Pipeline cross-talk detected
- **Schema Violation**: Dropped columns → Data corruption
- **100% Data Loss**: `m_count > 0 && r_count == 0` → Storage failure

### Three-Layer Stack

| Layer | Module | Responsibility |
|-------|--------|----------------|
| **Orchestration** | `orchestrator.py` | File discovery, AST parsing, extractor selection |
| **Storage Orchestration** | `storage/__init__.py` | Priority ordering, manifest attachment |
| **Domain Handlers** | 7 handlers | Language-specific storage logic |

### Domain-Specific Storage Handlers

| Handler | Languages/Features |
|---------|-------------------|
| `CoreStorage` | Imports, routes, SQL, symbols (all languages) |
| `PythonStorage` | Django, FastAPI, SQLAlchemy, decorators |
| `NodeStorage` | React hooks, Angular, Sequelize, Vue.js |
| `RustStorage` | Modules, traits, async/await, lifetimes |
| `GoStorage` | Goroutines, channels, error handling |
| `BashStorage` | Variables, commands, control flow |
| `InfrastructureStorage` | Docker, Compose, Terraform, CDK |

### Transaction Safety

```python
# WAL mode for concurrent reads during writes
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA foreign_keys = ON")

# Gatekeeper pattern prevents orphaned records
if construct_id not in self._valid_construct_ids:
    logger.warning("GATEKEEPER: Skipping orphaned property...")
    continue
```

### Performance Optimizations

- **Batch JS/TS Parsing**: 50 files per Node.js invocation
- **AST Caching**: SHA256-keyed cache in `.pf/.cache/`
- **Schema-Driven Batch Flush**: Generic INSERT for 70+ tables
- **Monorepo Detection**: Early detection prevents scanning irrelevant directories

### Key Metrics

- ~2,000 lines across orchestrator, core, and storage
- 70+ database tables spanning 10 schema modules
- 8 domain-specific storage handlers

---

## Engine 2: AST Extractors (Polyglot Parsing)

A **multi-language AST extraction system** providing unified semantic output across 7+ programming languages.

### Parser Strategy

| Language | Parser | Rationale |
|----------|--------|-----------|
| **Python** | Built-in `ast` | No external deps, full fidelity |
| **JavaScript/TypeScript** | TypeScript Compiler API | Type information, JSX/TSX support |
| **Go** | Tree-sitter | Fast, consistent cross-platform |
| **Rust** | Tree-sitter | Complex syntax, macros |
| **Bash** | Tree-sitter | Shell constructs, heredocs |
| **HCL/Terraform** | Tree-sitter | IaC patterns |

### Language Implementation Details

#### Python (`python_impl.py` - 1005 lines)

**47 data categories** extracted:
- **Core**: imports, symbols, assignments, function_calls, returns
- **Advanced**: async/await, comprehensions, lambda, decorators
- **Framework**: Django models/views, Flask routes, Celery tasks
- **Security**: SQL injection, command injection, JWT, crypto
- **Type System**: protocols, generics, TypedDict

**25+ specialized modules** in `python/` subdirectory for deep extraction.

#### JavaScript/TypeScript (`js_semantic_parser.py`)

**Architecture**: Python wrapper around Node.js bundle

```
javascript/
├── src/           # TypeScript source
└── dist/
    └── extractor.cjs  # 10MB compiled bundle
```

**Features**:
- JSX/TSX with configurable preservation modes
- Type extraction via TypeScript API
- tsconfig.json path resolution
- Two-pass system: standard + preserved JSX

#### Go (`go_impl.py` - 1372 lines)

- Structs and interfaces with generics
- Goroutines with captured variable tracking
- **Race condition detection** for loop variables in goroutines
- Defer statements, type assertions, error returns

#### Rust (`rust_impl.py` - 800+ lines)

- Modules with inline `declaration_list`
- Structs, enums, unions, traits
- Unsafe blocks, extern blocks
- Generic types and where clauses
- Macro definitions and invocations

#### Bash (`bash_impl.py` - 1053 lines)

- Function definitions (POSIX vs bash style)
- Variable assignments (local/global/exported/readonly)
- Pipelines with position tracking
- Heredoc quoting detection
- Wrapper command detection (sudo, time, env)

### Unified Output Format

All extractors produce standardized dict:

```python
{
    "type": "semantic_ast" | "python_ast" | "tree_sitter",
    "tree": <parsed AST>,
    "language": <language_name>,
    "content": <file_content>,
    "has_types": bool,      # JS/TS only
    "diagnostics": list,    # JS/TS only
}
```

### Zero Fallback in Action

```python
# Python - explicit failure
try:
    return ast.parse(content)
except SyntaxError as e:
    raise ParseError(f"Python syntax error: {e.msg}",
                     file=file_path, line=e.lineno) from e

# JS/TS - no fallbacks allowed
if not semantic_result.get("success"):
    raise RuntimeError(
        f"FATAL: TypeScript semantic parser failed for {file_path}\n"
        f"NO FALLBACKS ALLOWED - fix the error or exclude the file."
    )
```

### Design Patterns

- **Lazy Initialization**: Tree-sitter grammars loaded on-demand
- **Content Hashing**: Python AST cached by MD5 hash
- **Batch Optimization**: JS/TS files processed in single Node.js invocation
- **Error Context**: ParseError includes file path and line number
- **Monorepo Support**: tsconfig discovery walks up directory tree

---

## Engine 3: Graph Engine

A **multi-layer dependency analysis system** constructing and analyzing 4 graph types for deep code understanding.

### Graph Types

#### 1. Import Graph (Module Dependencies)

```python
# Nodes
{"id": "file.py", "type": "module", "lang": "python"}

# Edges
{"source": "a.py", "target": "b.py", "type": "import"}
```

- Internal vs external module distinction
- Language-aware resolution (Python relative imports, JS tsconfig paths)

#### 2. Call Graph (Function Relationships)

```python
# Nodes
{"id": "file.py::function_name", "type": "function"}

# Edges
{"source": "caller", "target": "callee", "type": "call"}
```

- Resolution status: `local_def`, `imported_def`, `ambiguous`, `unresolved`

#### 3. Control Flow Graph (CFG)

- **Block Types**: entry, exit, condition, loop_condition, normal, try
- **Edge Types**: fall_through, true, false, back_edge
- **Analytics**: Cyclomatic complexity, max nesting, dead code detection

#### 4. Data Flow Graph (DFG)

- Assignment flow: Variable → Variable through assignments
- Return flow: Function return values
- **9 pluggable strategies** for framework-specific edges

### DFG Strategies

| Strategy | Purpose | Language |
|----------|---------|----------|
| `PythonOrmStrategy` | SQLAlchemy, Django ORM | Python |
| `NodeOrmStrategy` | Prisma, TypeORM | Node.js |
| `NodeExpressStrategy` | Middleware chains | Node.js/Express |
| `GoHttpStrategy` | HTTP handler patterns | Go |
| `RustTraitStrategy` | Trait implementations | Rust |
| `BashPipeStrategy` | Pipe chains | Bash |
| `InterceptorStrategy` | HTTP interceptor chains | Cross-language |

### Key Algorithms

#### Cycle Detection (Iterative DFS)

```python
def detect_cycles(graph: dict) -> list[dict]:
    # Filter out _reverse edges (G3 fix for IFDS)
    for edge in graph["edges"]:
        if edge.get("type", "").endswith("_reverse"):
            continue
    # Iterative DFS with path tracking...
```

#### Impact Analysis (Bidirectional BFS)

```python
def impact_of_change(targets, import_graph, call_graph, max_depth=3):
    # Upstream: Who depends on me? (files that break if I change)
    # Downstream: What do I depend on? (files my changes might affect)
    return {"upstream": set, "downstream": set, "total_impacted": int}
```

#### Hotspot Detection (Degree Centrality)

- Ranks nodes by `in_degree + out_degree`
- High-degree nodes = architectural hubs requiring careful modification

### Critical Fixes

| Fix | Problem | Solution |
|-----|---------|----------|
| **G3** | IFDS needs reverse edges for backward traversal | Create bidirectional edges: forward + `*_reverse` |
| **G7** | Cache corruption from consumer modifications | Use `MappingProxyType` for immutable cached dicts |
| **G13/G14** | Path format mismatches (./ vs \\) | Normalize to forward-slash format everywhere |

### Database Caching (Lazy-Loading LRU)

**Problem**: Eager loading of 500K+ rows exhausts memory

**Solution**:
```python
class GraphDatabaseCache:
    IMPORTS_CACHE_SIZE = 2000
    EXPORTS_CACHE_SIZE = 2000
    RESOLVE_CACHE_SIZE = 5000

    @lru_cache(maxsize=IMPORTS_CACHE_SIZE)
    def get_imports(self, file_path: str) -> tuple[MappingProxyType, ...]:
        # Returns immutable proxies (G7 fix)
```

### Storage Schema (graphs.db)

```sql
TABLE nodes (
    id TEXT PRIMARY KEY,
    file TEXT,
    lang TEXT,
    type TEXT,          -- "module", "function", "variable"
    graph_type TEXT,    -- "import", "call", "data_flow"
    metadata JSON
);

TABLE edges (
    source TEXT,
    target TEXT,
    type TEXT,          -- "import", "call", "assignment", "*_reverse"
    graph_type TEXT,
    metadata JSON
);
```

### Performance

| Codebase Size | Build Time | Memory |
|---------------|------------|--------|
| 100 files | 2-5s | ~150MB |
| 500 files | 10-20s | ~300MB |
| 2K+ files | 30-60s | ~500MB |

---

## Engine 4: Taint Analysis Engine

A **dual-mode, multi-hop data flow analysis system** tracing untrusted data from sources to dangerous sinks with field-sensitive access path tracking.

### Architecture

```
                    +------------------+
                    |  Taint Registry  |
                    | (140+ sources,   |
                    |  200+ sinks)     |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                                       |
         v                                       v
+------------------+                   +------------------+
|  IFDS Analyzer   |                   |  FlowResolver    |
|  (Backward)      |                   |  (Forward)       |
+------------------+                   +------------------+
         |                                       |
         +-------------------+-------------------+
                             |
                             v
                    +------------------+
                    |  Vulnerability   |
                    |  Report          |
                    +------------------+
```

### Three Analysis Modes

| Mode | Engine(s) | Speed | Precision | Use Case |
|------|-----------|-------|-----------|----------|
| **Backward** | IFDS only | 30s-5m | Highest | Default, respects sanitization |
| **Forward** | FlowResolver only | 10-30s | Medium | Quick reachability check |
| **Complete** | Both (handshake) | 1-7m | Highest | Full analysis with confirmation |

### IFDS Backward Worklist Algorithm

```python
worklist = [(sink_ap, depth=0, [], matched_source=None)]
visited_states = set()

while worklist:
    current_ap, depth, hop_chain, matched_source = worklist.popleft()

    if current_ap matches any source:
        matched_source = source

    if depth >= max_depth OR no predecessors:
        if matched_source:
            if path_goes_through_sanitizer(hop_chain):
                record as SANITIZED
            else:
                record as VULNERABLE
        continue

    for pred_ap in _get_predecessors(current_ap):
        worklist.append((pred_ap, depth+1, [hop]+hop_chain, matched_source))
```

### Predecessor Resolution (Dual-Direction)

```sql
-- 1. Explicit reverse edges
SELECT * FROM edges WHERE source = current AND type LIKE '%_reverse'

-- 2. Forward edges traversed backward
SELECT * FROM edges WHERE target = current AND type NOT LIKE '%_reverse'

-- 3. Call graph edges (inter-procedural)
SELECT * FROM edges WHERE target = current AND graph_type = 'call'
```

### Access Path: Field-Sensitive Tracking

```python
@dataclass(frozen=True)
class AccessPath:
    file: str
    function: str
    base: str           # e.g., "req"
    fields: tuple       # e.g., ("body", "email")

    # node_id = "api.py::handler::req.body.email"
```

**Example Flow**:
```
Source: req.body.email → AccessPath("api.py", "handler", "req", ("body", "email"))
Assignment: user_input = req.body.email → taint propagates
Sink: db.query(f"...{user_input}") → VULNERABLE
```

### Vulnerability Coverage (18+ Classes)

| Type | Risk | Detection Method |
|------|------|------------------|
| SQL Injection | CRITICAL | Sink: db.query(), interpolation |
| Command Injection | CRITICAL | Sink: os.system(), subprocess |
| XSS | HIGH | Sink: innerHTML, dangerouslySetInnerHTML |
| Path Traversal | HIGH | Sink: open() with user input |
| SSRF | HIGH | Sink: requests.get() with user URL |
| Template Injection | HIGH | Sink: render_template() |
| Deserialization | CRITICAL | Sink: pickle.loads(), eval() |
| NoSQL Injection | MEDIUM | Sink: db.find(), collection queries |
| Open Redirect | MEDIUM | Sink: redirect() with user URL |

### Sanitizer Detection

1. **Registry Lookup**: `registry.is_sanitizer(function_name, language)`
2. **Validation Framework Detection**: Zod, Joi, Yup, express-validator
3. **Safe Sink Patterns**: Pre-marked safe functions
4. **Heuristic Detection**: Names containing `validate`, `sanitize`, `escape`

### Source & Sink Registry

**Sources (140+ Patterns)**:
- HTTP: `request.args`, `request.form`, `request.json`
- Environment: `os.environ`, `process.env`, `sys.argv`
- File I/O: `open().read()`, `fs.readFile()`
- Database: `cursor.fetchall()` (secondary taint)

**Sinks (200+ Patterns)**:
- SQL: `cursor.execute()`, `db.query()`, `sequelize.query()`
- Command: `os.system()`, `subprocess.call()`, `eval()`
- XSS: `dangerouslySetInnerHTML`, `innerHTML`
- File: `open()`, `fs.writeFile()`

### Configuration

```python
max_depth = os.environ.get("AUD_IFDS_DEPTH", 100)
max_paths_per_sink = os.environ.get("AUD_IFDS_MAX_PATHS", 1000)
time_budget_seconds = os.environ.get("AUD_IFDS_BUDGET", 60)
```

### Performance

| Codebase | Forward | Backward | Complete |
|----------|---------|----------|----------|
| 5K LOC | 5s | 15s | 20s |
| 20K LOC | 20s | 60s | 80s |
| 100K+ LOC | 2m | 5m | 7m |

---

## Engine 5: FCE (Factual Correlation Engine)

The **evidence convergence system** that identifies locations where multiple independent analysis vectors converge—without imposing subjective risk judgments.

### Core Philosophy

> "I am not the judge, I am the evidence locker."

### The 4 Independent Vectors

| Vector | Source | Measures |
|--------|--------|----------|
| **STATIC (S)** | Linters (ruff, eslint, bandit) | Code quality, security patterns |
| **FLOW (F)** | Taint analysis | Source-to-sink data flow risks |
| **PROCESS (P)** | Git history (churn-analysis) | File volatility, change patterns |
| **STRUCTURAL (T)** | CFG analysis | Cyclomatic complexity, nesting depth |

**Critical Rule**: Multiple tools within the SAME vector do NOT increase density. 5 linters screaming about the same issue = 1 STATIC vector, not 5 signals.

### Convergence Scoring

```python
density = len(vectors_present) / 4  # Pure math, no opinions
```

| Density | Vectors | Interpretation |
|---------|---------|----------------|
| **1.0** | 4/4 | Everything is screaming - investigate immediately |
| **0.75** | 3/4 | Strong convergence - high priority |
| **0.5** | 2/4 | Multiple signals - worth attention |
| **0.25** | 1/4 | Single dimension - normal finding |

### Core Data Structures

```python
class VectorSignal:
    file_path: str
    vectors_present: set[Vector]  # {STATIC, FLOW, PROCESS, STRUCTURAL}

    @property
    def density(self) -> float:
        return len(self.vectors_present) / 4

    @property
    def density_label(self) -> str:
        return f"{len(self.vectors_present)}/4 vectors"

class ConvergencePoint:
    file_path: str
    line_start: int
    line_end: int
    signal: VectorSignal
    facts: list[Fact]  # The evidence

class Fact:
    vector: Vector       # Which vector detected this
    source: str          # Which tool (ruff, taint_flows, etc.)
    file_path: str
    line: int
    observation: str     # Human-readable (NO opinions)
    raw_data: dict       # Full structured data
```

### Vector Detection Logic

```python
def _build_vector_index(self) -> dict[str, set[Vector]]:
    # Query 1: findings_consolidated for STATIC, PROCESS, STRUCTURAL
    for row in cursor.execute("SELECT file, tool FROM findings_consolidated"):
        if tool == "cfg-analysis":
            index[file].add(Vector.STRUCTURAL)
        elif tool == "churn-analysis":
            index[file].add(Vector.PROCESS)
        else:
            index[file].add(Vector.STATIC)

    # Query 2: taint_flows for FLOW vector
    for row in cursor.execute("SELECT source_file, sink_file FROM taint_flows"):
        index[row["source_file"]].add(Vector.FLOW)
        index[row["sink_file"]].add(Vector.FLOW)
```

### AIContextBundle

Wraps ConvergencePoint with additional context for LLM consumption:

```python
class AIContextBundle:
    convergence: ConvergencePoint
    context_layers: dict  # Related tables' data

    # Registry includes ~148 categorized tables:
    # - RISK_SOURCES: 7 tables
    # - CONTEXT_FRAMEWORK: 34 framework tables
    # - CONTEXT_SECURITY: 6 security tables
    # - CONTEXT_LANGUAGE: 93 language-specific tables
```

### CLI Output

```bash
aud fce --min-vectors 2
```

```
[3/4] [SF-T] src/auth/login.py
  |     |    |
  |     |    +-- File path
  |     +------- Vectors: S=Static, F=Flow, P=Process, T=Structural
  +------------- Density: 3 of 4 vectors
```

### Key Design Principles

1. **No Fallback Logic**: Hard fail if data missing
2. **Bulk Loading**: 2 queries to build index, not N+1
3. **Pure Math**: Density = vectors / 4, no thresholds
4. **Evidence Aggregation**: Package facts + context for AI
5. **Signal != Noise**: Vector count is signal, tool count is noise

---

## Engine 6: Rules Orchestrator

A **unified, dynamically-discovered security rules system** with 25 categories and 113+ rule functions.

### Dynamic Rule Discovery

```python
def _discover_all_rules(self) -> dict[str, list[RuleInfo]]:
    for subdir in rules_dir.iterdir():
        for py_file in subdir.glob("*.py"):
            module = importlib.import_module(module_name)

            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("find_") or name == "analyze":
                    rule_info = self._analyze_rule(name, obj, ...)
```

**Discovery Criteria**:
- Functions named `analyze` or `find_*`
- Defined in the module (not imported)
- Metadata captured from `METADATA` object

### All 25 Rule Categories

| Category | Files | Primary Focus |
|----------|-------|---------------|
| **dependency** | 10 | Package bloat, ghost deps, version lag |
| **github_actions** | 8 | Workflow risks, untrusted checkout |
| **security** | 8 | CORS, crypto, input validation, PII |
| **deployment** | 7 | AWS CDK, IAM wildcards, security groups |
| **graphql** | 7 | Query depth, N+1, overfetch, injection |
| **xss** | 7 | Template injection, unsafe escaping |
| **frameworks** | 6 | Express, FastAPI, Flask, Next.js, React |
| **rust** | 6 | Memory safety, unsafe blocks, panic |
| **vue** | 6 | Lifecycle hooks, state management |
| **python** | 5 | Deserialization, crypto, injection |
| **auth** | 4 | JWT, OAuth, password, session |
| **go** | 4 | Concurrency, crypto, error handling |
| **react** | 4 | Hooks, component lifecycle, state |
| **sql** | 4 | SQL injection, ORM raw queries |
| **bash** | 3 | Dangerous patterns, injection, quoting |
| **orm** | 3 | Sequelize, TypeORM vulnerabilities |
| + 9 more... | | |

### Rule Architecture

```python
@dataclass
class RuleInfo:
    name: str                   # Function name
    module: str                 # Full module path
    function: Callable          # Actual function
    category: str               # Category folder

    requires_ast: bool          # Needs AST tree?
    requires_db: bool           # Needs database?
    requires_file: bool         # Needs file path?
    requires_content: bool      # Needs file content?

    rule_type: str              # standalone | discovery | taint-dependent
    execution_scope: str        # database | file
```

### Rule Types

1. **Standalone Rules** - No dependencies, execute independently
2. **Discovery Rules** - Populate taint registry with sources/sinks
3. **Taint-Dependent Rules** - Query taint analysis results

### Query System: The Q Class

Type-safe, composable database queries:

```python
from theauditor.rules.query import Q

rows = db.query(
    Q("function_call_args")
    .select("file", "line", "callee_function")
    .where("callee_function IN (?)", "eval", "exec")
    .where("file NOT LIKE ?", "%test%")
    .order_by("file, line")
)
```

**Benefits**:
- Column validation against schema at build time
- Foreign key auto-detection
- Parameterized queries (no SQL injection)

### Standardized Interfaces

```python
@dataclass
class StandardRuleContext:
    file_path: Path
    content: str
    language: str
    project_path: Path
    ast_wrapper: dict | None
    db_path: str | None
    taint_checker: Callable | None

@dataclass
class StandardFinding:
    rule_name: str              # Identifier (kebab-case)
    message: str                # Human-readable
    file_path: str
    line: int
    severity: Severity          # CRITICAL | HIGH | MEDIUM | LOW | INFO
    confidence: Confidence      # HIGH | MEDIUM | LOW
    cwe_id: str | None          # CWE-123 format
```

### Rule Execution Pipeline

```python
# Phase 1: Discovery rules populate taint registry
registry = TaintRegistry()
orchestrator.run_discovery_rules(registry)

# Phase 2: Standalone rules (database scope)
all_findings.extend(orchestrator.run_standalone_rules())

# Phase 3: Taint analysis
taint_checker = orchestrator._create_taint_checker(context)

# Phase 4: Taint-dependent rules
all_findings.extend(orchestrator.run_taint_dependent_rules(taint_checker))
```

### Fidelity Verification

```python
@dataclass
class RuleResult:
    findings: list[StandardFinding]
    manifest: dict  # {items_scanned, tables_queried, queries_executed}
```

**Purpose**: Catch "silent failures" where a rule scans nothing but reports no findings.

---

## Engine 7: Linters Integration

A **unified wrapper layer** for external static analysis tools with async parallel orchestration.

### Supported Linters

| Linter | Language | Features |
|--------|----------|----------|
| **RuffLinter** | Python | Fast, internally parallelized |
| **MypyLinter** | Python | Type checking, needs full context |
| **EslintLinter** | JS/TS | Dynamic batching (Windows limit) |
| **ClippyLinter** | Rust | Crate-level, output filtering |
| **GolangciLinter** | Go | Internally parallelized |
| **ShellcheckLinter** | Bash | Shell script analysis |

### Unified Interface

```python
class BaseLinter(ABC):
    @abstractmethod
    async def run(self, files: list[str]) -> LinterResult:
        """Run linter on files, return normalized results."""
        pass

@dataclass
class LinterResult:
    status: str          # SUCCESS | SKIPPED | FAILED
    findings: list[Finding]
    tool: str
    elapsed: float

@dataclass
class Finding:
    file: str
    line: int
    column: int
    severity: str        # error | warning | info
    message: str
    rule: str
    tool: str
```

### Parallel Orchestration

```python
class LinterOrchestrator:
    async def run_all_linters(self, workset_files: list[str]) -> dict:
        results = await asyncio.gather(
            self.ruff.run(python_files),
            self.mypy.run(python_files),
            self.eslint.run(js_files),
            self.clippy.run(rust_files),
            self.golangci.run(go_files),
            self.shellcheck.run(bash_files),
            return_exceptions=True
        )
```

**Features**:
- Parallel execution via `asyncio.gather()`
- Individual failures don't affect others
- Workset filtering for targeted analysis

### Batching Strategies

| Linter | Strategy | Reason |
|--------|----------|--------|
| Ruff | No batching | Internally parallelized |
| Mypy | No batching | Needs full project context |
| ESLint | Dynamic batching | 8191 char Windows cmd limit |
| Clippy | Crate-level | Rust compilation unit |
| GolangCI | No batching | Internally parallelized |
| ShellCheck | No batching | Fast enough |

### ESLint Dynamic Batching

```python
def _batch_files(self, files: list[str]) -> list[list[str]]:
    MAX_CMD_LENGTH = 8191  # Windows limit
    batches = []
    current_batch = []
    current_length = len(base_cmd)

    for file in files:
        if current_length + len(file) + 1 > MAX_CMD_LENGTH:
            batches.append(current_batch)
            current_batch = []
            current_length = len(base_cmd)
        current_batch.append(file)
        current_length += len(file) + 1
```

### Performance

| Linter | Typical Time (1K files) |
|--------|-------------------------|
| Ruff | 1-3 sec |
| Mypy | 5-15 sec |
| ESLint | 3-10 sec |
| Clippy | 5-20 sec |
| GolangCI | 3-10 sec |
| ShellCheck | 1-3 sec |
| **Total (parallel)** | **5-20 sec** |

---

## Engine 8: MachineL (ML/Intelligence System)

An **intelligent machine learning and impact analysis engine** for risk prediction and change impact forecasting.

### Three-Model Ensemble

| Model | Purpose | Algorithm |
|-------|---------|-----------|
| **Root Cause** | Identifies files likely causing failures | HistGradientBoostingClassifier |
| **Next Edit** | Forecasts files needing future editing | HistGradientBoostingClassifier |
| **Risk Regression** | Continuous risk score (0-1) | Ridge with L2 regularization |

### Pipeline Structure

```python
Pipeline([
    ("scaler", StandardScaler()),
    ("clf", HistGradientBoostingClassifier(
        learning_rate=0.1,
        max_iter=100,
        max_depth=5,
        class_weight="balanced",
    )),
])

# Probability calibration for reliable confidence
calibrator = IsotonicRegression(out_of_bounds="clip")
```

### Feature Engineering (109 Dimensions)

| Tier | Features | Source |
|------|----------|--------|
| 1. File Metadata | bytes, loc | `files` table |
| 2. Language | is_js, is_py | Extension detection |
| 3. Graph Topology | in_degree, out_degree, has_routes | `refs` table |
| 4. Historical Journal | touches, failures, successes | `.pf/history/` |
| 5. Root Cause | rca_fails | FCE results |
| 6. AST Invariants | invariant_fails, passes | `ast_proofs.json` |
| 7. Git Churn | commits_90d, unique_authors | `git log` |
| 8. Semantic Imports | has_http, has_db, has_auth | Import classification |
| 9. AST Complexity | function_count, class_count | `symbols` table |
| 10. Security Patterns | jwt_usage, sql_query_count | Security tables |
| 11. Findings & CWE | critical/high/medium findings | `findings_consolidated` |
| 12. Type Coverage | type_annotation_count, any_type | Type tables |
| 13. Control Flow | cfg_blocks, cyclomatic_complexity | CFG tables |
| 14. Impact Radius | blast_radius, coupling_score | Impact analyzer |
| 15. AI Agent Behavior | blind_edit_count, hallucination_rate | Session logs |

### Impact Analyzer

#### Blast Radius Calculation

```python
def analyze_impact(db_path, target_file, target_line):
    # 1. Find symbol at target_line
    # 2. Find UPSTREAM (who calls this)
    # 3. Find DOWNSTREAM (what this calls)
    # 4. Expand to transitive dependencies (2 hops)
    # 5. Classify into production/tests/config/external
```

#### Coupling Score (0-100)

```python
def calculate_coupling_score(impact_data) -> int:
    base_score = (direct_upstream * 3) + (direct_downstream * 2)
    spread_multiplier = min(affected_files / 5, 3)
    return min(score, 100)
```

**Interpretation**:
- 0-30: Low coupling - safe to refactor
- 30-70: Medium coupling - needs careful review
- 70-100: High coupling - requires design change

### Probability Calibration

```python
calibrator = IsotonicRegression(out_of_bounds="clip")
calibrator.fit(raw_probs, actual_labels)
calibrated_probs = calibrator.transform(raw_probs)
```

**Why**: Raw model saying "0.92" doesn't mean 92% actual frequency. Calibration ensures it does.

### CLI Commands

```bash
# Training
aud learn --db-path .pf/repo_index.db \
          --enable-git \
          --session-dir ~/.claude/projects/

# Inference
aud suggest --workset .pf/workset.json --topk 10
```

### Model Persistence

```python
model_data = {
    "root_cause_clf": root_cause_clf,
    "next_edit_clf": next_edit_clf,
    "risk_reg": risk_reg,
    "scaler": scaler,
    "root_cause_calibrator": calibrator,
}
joblib.dump(model_data, ".pf/ml/model.joblib")
```

### Cold Start Handling

When training on <500 samples:
- `class_weight="balanced"` over-weights rare class
- Human feedback (`feedback_path`) boosts sample weight 5x
- Large feature set (109 dims) helps interpolate

---

## Engine 9: Pipeline & Orchestration

The `aud full` command orchestrates a **24-phase security audit pipeline** organized into **4 sequential stages** with intelligent parallelization.

### Pipeline Architecture

```
        STAGE 1: Foundation (Sequential, Hard Fail)
        ├── Phase 1: Index repository (AST parsing)
        └── Phase 2: Detect frameworks
                          |
                          v
        STAGE 2: Data Preparation (Sequential, Hard Fail)
        ├── Phases 3-11: Dependencies, workset, linting,
        │                patterns, graphs
                          |
                          v
        STAGE 3: Heavy Analysis (3 Parallel Tracks, Non-Blocking)
        ├── Track A (Taint): IFDS + FlowResolver
        ├── Track B (Static): Terraform, CDK, GitHub Actions, Graph Viz
        └── Track C (Network): Dependency versions, Doc fetching
                          |
                          v
        STAGE 4: Final Aggregation (Sequential, Non-Blocking)
        └── Phases 21-25: CFG, churn, FCE, session analysis
```

### The 24 Phases

| # | Phase | Stage | Timeout |
|---|-------|-------|---------|
| 1 | index | 1 | 600s |
| 2 | detect-frameworks | 1 | 180s |
| 3 | deps --vuln-scan | 2 | 1200s |
| 4 | deps --check-latest | 2 | 1200s |
| 5 | docs fetch | 2 | 600s |
| 6 | workset --all | 2 | 600s |
| 7 | lint --workset | 2 | 600s |
| 8 | detect-patterns | 2 | 1800s |
| 9 | graph build | 2 | 600s |
| 10 | graph build-dfg | 2 | 600s |
| 11 | terraform provision | 2 | 600s |
| 12 | taint | 3A | 1800s |
| 13-16 | terraform/cdk/workflows/graph analyze | 3B | 600s |
| 17-20 | graph viz (4 views) | 3B | 600s |
| 21 | cfg analyze | 4 | 600s |
| 22 | metadata churn | 4 | 600s |
| 23 | fce | 4 | 900s |
| 24 | session analyze | 4 | 600s |

### Async Architecture

```python
# Parallel execution of 3 tracks
tasks = []
if track_a_commands:
    tasks.append(run_taint_async())
if track_b_commands:
    tasks.append(run_chain_silent(track_b_commands))
if track_c_commands:
    tasks.append(run_chain_silent(track_c_commands))

parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Subprocess Execution with Timeout

```python
async def run_command_async(cmd, cwd, timeout=900):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    while True:
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=0.5
            )
            return PhaseResult(...)
        except TimeoutError:
            if time.time() - start > timeout:
                process.kill()
                return PhaseResult(status=FAILED, stderr="Timed out")
```

### Error Recovery Strategy

| Stage | On Failure |
|-------|------------|
| **1 & 2** | Pipeline stops - foundational data required for later stages |
| **3 & 4** | Continue with partial results, log errors |

### Pipeline Modes

| Mode | Flag | Behavior |
|------|------|----------|
| **Full** | (default) | All 24 phases |
| **Offline** | `--offline` | Skip Track C (network I/O) |
| **Index-Only** | `--index` | Only Stages 1 & 2 |

### Rich Terminal UI

```python
class DynamicTable:
    def _build_live_table(self):
        table = Table(title="Pipeline Progress")
        for name, info in self._phases.items():
            status = info["status"]
            elapsed = time.time() - info["start_time"]
            table.add_row(name, status, f"{elapsed:.1f}s")
```

**Features**:
- 4 updates/second refresh
- Real-time elapsed timers
- Colored status indicators
- Parallel track output buffering

### Performance

| Codebase | Full Run | --offline | --index |
|----------|----------|-----------|---------|
| < 5K LOC | 2-3 min | 1-2 min | 1-2 min |
| 20K LOC | 5-10 min | 3-5 min | 2-3 min |
| 100K+ LOC | 15-20 min | 10-15 min | 5-10 min |

### Database Output

| Database | Size | Contents |
|----------|------|----------|
| **repo_index.db** | ~181MB | symbols, imports, function_calls, api_endpoints, findings, graphql_*, cdk_*, terraform_*, workflow_* |
| **graphs.db** | ~126MB | Precomputed call/import/DFG graphs, visualization metadata |

### ML-Friendly Audit Journal

```python
# Events: phase_start, phase_end, file_touch, finding, pipeline_summary
# Format: Newline-delimited JSON (.ndjson)
# Location: .pf/history/{run_type}/{timestamp}/journal.ndjson
```

---

## Engine 10: Context & Query System

A **database-first approach** to code navigation. Instead of re-reading files, the system queries indexed relationships through SQLite.

### Database Architecture

```python
repo_db = sqlite3.connect(".pf/repo_index.db")   # Raw facts (181MB)
graph_db = sqlite3.connect(".pf/graphs.db")      # Pre-computed graphs (126MB)
```

### CodeQueryEngine

#### Symbol Resolution (Priority-Based)

```python
def _resolve_symbol(self, name: str) -> list[str]:
    # Priority 1: Exact match
    # Priority 2: Suffix match (*.name)
    # Priority 3: Last segment match
    # Returns helpful "Did you mean?" on no match
```

#### Call Tracing (Recursive CTE)

```sql
WITH RECURSIVE caller_graph AS (
    SELECT ... FROM function_call_args
    WHERE callee_function IN (targets)

    UNION ALL

    SELECT ... FROM function_call_args
    JOIN caller_graph ON ...
    WHERE depth < depth_limit
)
```

#### Variable Flow

- BFS through assignments table
- Tracks def-use chains
- Depth-limited to 5 levels

### Context Bundles

**File Context**:
```python
def get_file_context_bundle(file_path):
    return {
        "symbols": get_file_symbols(file_path),
        "hooks": get_file_hooks(file_path),
        "imports": get_file_imports(file_path),
        "importers": get_file_importers(file_path),
        "outgoing_calls": get_file_outgoing_calls(file_path),
        "incoming_calls": get_file_incoming_calls(file_path),
        "framework_info": get_file_framework_info(file_path),
    }
```

**Symbol Context**:
```python
def get_symbol_context_bundle(symbol_name, depth=2):
    return {
        "definition": find_symbol(symbol_name),
        "callers": get_callers(symbol_name, depth),
        "callees": get_callees(symbol_name),
    }
```

### Dead Code Detection

#### Three Detection Methods

| Method | Target | Confidence |
|--------|--------|------------|
| **Isolated Modules** | Never-imported files | HIGH (never imported), MEDIUM (migration), LOW (init) |
| **Dead Symbols** | Defined but never called | HIGH (never called), MEDIUM (private `_name`), LOW (test_*) |
| **Ghost Imports** | Imported but never used | Cross-database verification |

#### Implementation

```sql
WITH RECURSIVE reachable(file_path) AS (
    SELECT source FROM edges WHERE source IN (entry_points)
    UNION ALL
    SELECT e.target FROM edges e
    JOIN reachable r ON e.source = r.file_path
)
-- Dead modules = all_nodes - reachable
```

### Explain System

#### Target Type Detection

```python
def detect_target_type(target):
    # 1. Known extension → file
    # 2. Path separator → file
    # 3. PascalCase.method → symbol
    # 4. PascalCase in react_components → component
    # 5. Default → symbol
```

#### Output Aggregation

| Target Type | Included Data |
|-------------|---------------|
| **File** | Symbols, hooks, dependencies, dependents, calls, framework info |
| **Symbol** | Definition, callers (transitive), callees |
| **Component** | Metadata, hooks used, child components |

### Semantic Context

#### Pattern Matching

```python
@dataclass
class ContextPattern:
    id: str               # "jwt_deprecated"
    pattern: str          # Regex pattern
    reason: str           # Why this matters
    category: str         # obsolete | current | transitional
    severity: str | None
    replacement: str | None
    expires: str | None   # For transitional (YYYY-MM-DD)
```

#### Migration Progress

```python
def get_migration_progress(self) -> dict:
    return {
        "total_files": ...,
        "files_need_migration": ...,
        "files_fully_migrated": ...,
        "migration_percentage": 100 * (migrated / total)
    }
```

### Query CLI

```bash
# Symbol lookup
aud query --symbol validateUser --show-callers --depth 2

# File analysis
aud query --file src/auth.ts --show-dependents

# API endpoints
aud query --api "/users/:id"

# Component tree
aud query --component Dashboard --show-tree

# Variable flow
aud query --variable userId --show-flow --depth 3
```

### Key Principles

1. **Zero Fallback**: Hard fail if query wrong
2. **Database-First**: Never re-parse files
3. **Recursive CTEs**: Graph traversal in SQL, not Python
4. **Limits at SQL Level**: Performance enforced in database
5. **Error Messages Expose Fix**: "Did you mean?" suggestions

---

## Engine 11: Session Analyzer

A **Tier 5 (ML training) pipeline** that parses AI agent session logs, analyzes behavior patterns, and detects anti-patterns for quality improvement.

### Core Question

> "How efficiently did the AI work? Did it follow instructions?"

### Key Components

#### 1. Session Parser (`parser.py`)

- Reads `.jsonl` session files
- Extracts: user messages, assistant messages, tool calls
- Creates `Session` dataclass with chronological turns
- Location: `~/.claude/projects/` or `~/.codex/sessions/`

#### 2. Activity Classifier (`activity_metrics.py`)

| Activity Type | Definition | Tools |
|---------------|------------|-------|
| **PLANNING** | Discussion & design | Text >200 chars, no tools |
| **WORKING** | Code changes | Edit, Write, Bash, NotebookEdit |
| **RESEARCH** | Info gathering | Read, Grep, Glob, Task, WebFetch |
| **CONVERSATION** | Questions, clarifications | User messages, short responses |

**Key Metrics**:
- `work_to_talk_ratio`: Working tokens / (Planning + Conversation)
- `research_to_work_ratio`: Research tokens / Working tokens
- `tokens_per_edit`: Total tokens / (Edit + Write count)

#### 3. Workflow Compliance Checker (`workflow_checker.py`)

**Checks**:
- `blueprint_first`: Run `aud blueprint` before modifications
- `query_before_edit`: Use `aud query` before editing
- `no_blind_reads`: Read files before editing them

```python
@dataclass
class WorkflowCompliance:
    compliant: bool
    score: float      # 0-1
    violations: list[str]
```

#### 4. Diff Risk Scorer (`diff_scorer.py`)

**Risk Factors (0-1)**:
- Taint analysis (40%): SQL injection, command injection, eval()
- Pattern detection (30%): Hardcoded credentials, TODO/FIXME
- FCE completeness (20%): File completion estimate
- RCA historical (10%): Prior failure rates

### Finding Categories

| Finding | Severity | Meaning |
|---------|----------|---------|
| `blind_edit` | WARNING | Edit without Read |
| `duplicate_read` | INFO | File read >3 times |
| `missing_search` | INFO | Write without Grep/Glob |
| `comment_hallucination` | WARNING | AI references non-existent comments |
| `duplicate_implementation` | WARNING | Creates symbols already in DB |

### Activity Classification Logic

```
Turn Classification:
├─ User message? → CONVERSATION
├─ No tools?
│  └─ Text >200 chars? → PLANNING, else CONVERSATION
├─ Only META tools? (TodoWrite, AskUserQuestion)
│  └─ Text >200 chars? → PLANNING, else CONVERSATION
├─ Has WORKING tools? (Edit, Write, Bash)
│  └─ WORKING
└─ Has RESEARCH tools? (Read, Grep, Glob)
   └─ RESEARCH
```

### Storage Layer

**Database**: `.pf/ml/session_history.db`

```sql
TABLE session_executions (
    session_id TEXT,
    workflow_compliant BOOL,
    compliance_score FLOAT,
    risk_score FLOAT,
    task_completed BOOL,
    corrections_needed BOOL,
    user_engagement_rate FLOAT,
    diffs_scored JSON
);
```

### ML Integration (Tier 5 Features)

```python
load_session_execution_features(db_path, file_paths) → {
    "session_workflow_compliance": 0.85,
    "session_avg_risk_score": 0.32,
    "session_blind_edit_rate": 0.0,
    "session_user_engagement": 1.5
}
```

**Correlation Statistics**:
```
Compliant sessions:
  - Avg risk score: 0.28
  - Correction rate: 12%

Non-compliant sessions:
  - Avg risk score: 0.42 (50% higher)
  - Correction rate: 34% (3x higher)
```

### CLI Commands

```bash
aud session analyze    # Parse and store to DB
aud session report     # Aggregate findings
aud session inspect    # Deep-dive single session
aud session activity   # Work/talk/planning ratios
aud session list       # List available sessions
```

### Why This Matters

1. **Quality Feedback Loop**: Detect when AI doesn't follow instructions
2. **Productivity Metrics**: Quantify work vs overhead
3. **Risk Prediction**: Learn which patterns correlate with failures
4. **Behavioral Learning**: Train models on successful execution patterns
5. **Compliance Verification**: Ensure workflows are followed

---

## Engine 12: CLI Commands

**36 top-level commands** (26 standalone + 10 groups) with **77 total commands** including subcommands, organized across **9 functional categories** with Rich-formatted help.

### Command Categories

| Category | Commands | Focus |
|----------|----------|-------|
| **PROJECT_SETUP** | setup-ai, tools | Environment initialization |
| **CORE_ANALYSIS** | full, workset | Main audit pipeline |
| **SECURITY** | detect-patterns, detect-frameworks, taint, boundaries, rules, docker-analyze, terraform, cdk, workflows | Security scanning |
| **DEPENDENCIES** | deps, docs | Package analysis |
| **CODE_QUALITY** | lint, cfg, graph, graphql, deadcode | Quality metrics |
| **DATA_REPORTING** | fce, metadata, blueprint | Evidence aggregation |
| **ADVANCED_QUERIES** | query, explain, impact, refactor, context | Database queries |
| **INSIGHTS_ML** | insights, learn, suggest, learn-feedback, session | ML-driven analysis |
| **UTILITIES** | planning, manual, _archive | Support functions |

### Command Inventory

**Top-Level Commands**: 36 commands (26 standalone + 10 groups)
**Subcommands**: 41 subcommands within groups
**Total**: 77 commands including all subcommands

The table below lists all available commands:

| # | Command | Description |
|---|---------|-------------|
| 1 | `setup-ai` | Create isolated analysis environment |
| 2 | `tools` | Tool detection and verification |
| 3 | `full` | Run complete audit pipeline |
| 4 | `workset` | Compute targeted file subset |
| 5 | `detect-patterns` | Detect 100+ security patterns |
| 6 | `detect-frameworks` | Display detected frameworks |
| 7 | `taint` | IFDS taint analysis |
| 8 | `boundaries` | Security boundary analysis |
| 9 | `rules` | Inspect detection rules |
| 10 | `docker-analyze` | Dockerfile security |
| 11 | `terraform` | Terraform IaC security |
| 12 | `cdk` | AWS CDK security |
| 13 | `workflows` | GitHub Actions security |
| 14 | `deps` | Dependency analysis |
| 15 | `docs` | Documentation fetching |
| 16 | `lint` | Run linters |
| 17 | `cfg` | Control flow analysis |
| 18 | `graph` | Dependency graphs |
| 19 | `graphql` | GraphQL schema analysis |
| 20 | `deadcode` | Dead code detection |
| 21 | `fce` | Factual Correlation Engine |
| 22 | `metadata` | Churn and coverage |
| 23 | `blueprint` | Architecture visualization |
| 24 | `query` | Database query API |
| 25 | `explain` | Symbol/file context |
| 26 | `impact` | Blast radius analysis |
| 27 | `refactor` | Refactoring impact |
| 28 | `context` | Semantic rule application |
| 29 | `insights` | Insight generation |
| 30 | `learn` | Train ML models |
| 31 | `suggest` | ML-based suggestions |
| 32 | `learn-feedback` | Human feedback for ML |
| 33 | `session` | AI session analysis |
| 34 | `planning` | Planning system |
| 35 | `manual` | Documentation system |
| 36 | `_archive` | Artifact segregation |

### Command Groups (with Subcommands)

#### `session` - AI Agent Analysis
- `analyze` - Parse and store sessions
- `report` - Detailed analysis report
- `inspect` - Single session deep-dive
- `activity` - Work/talk ratios
- `list` - List available sessions

#### `graph` - Dependency Analysis
- `build` - Construct graphs
- `analyze` - Cycles, hotspots
- `query` - Interactive queries
- `viz` - Visualizations

#### `cfg` - Control Flow
- `analyze` - Complexity analysis
- `viz` - DOT diagrams

#### `terraform`/`cdk`/`workflows`
- `analyze` - Run security rules
- `report` - Generate reports

### Usage Patterns

#### Initial Audit
```bash
aud setup-ai --target .
aud full --offline
aud blueprint --structure
aud taint
```

#### Incremental Review
```bash
aud workset --diff main..HEAD
aud lint --workset
aud impact --symbol changedFunction
```

#### Security Deep Dive
```bash
aud explain src/auth.ts
aud query --symbol loginHandler --show-callers
aud boundaries --type input-validation
aud taint --severity high
```

#### Architecture Review
```bash
aud blueprint --structure
aud graph analyze
aud deadcode
aud metadata churn --days 30
```

#### ML-Driven Analysis
```bash
aud learn --session-dir ~/.claude/projects/
aud suggest
```

### Performance

| Command | Typical Time | Dependencies |
|---------|--------------|--------------|
| `full` | 2-10 min | Network (first run) |
| `full --offline` | 1-5 min | Local only |
| `workset` | 1-3 sec | repo_index.db |
| `query` | <1 sec | repo_index.db |
| `explain` | 1-5 sec | repo_index.db |
| `taint` | 30-60 sec | repo_index.db |
| `lint --workset` | 5-15 sec | External linters |

### Database Requirements

| Database | Size | Required By |
|----------|------|-------------|
| **repo_index.db** | ~181MB | query, explain, impact, refactor, context, taint, boundaries, deadcode, fce, all security scanning |
| **graphs.db** | ~126MB | graph query, graph viz, impact analysis (optional) |

### Rich Help System

```bash
aud --help          # 9 colored category panels
aud <cmd> --help    # Per-command Rich sections:
                    # - AI ASSISTANT CONTEXT
                    # - EXAMPLES
                    # - COMMON WORKFLOWS
                    # - OUTPUT FILES
                    # - RELATED COMMANDS
```

---

## Data Flow Summary

```
                          SOURCE CODE
                               |
                               v
    +------------------+  +------------------+
    |   AST Extractors |  |    Linters       |
    | (Python, JS, Go, |  | (Ruff, ESLint,   |
    |  Rust, Bash)     |  |  Clippy, etc.)   |
    +--------+---------+  +--------+---------+
             |                     |
             v                     v
    +------------------+  +------------------+
    |     Indexer      |  |   Linter         |
    | (Fidelity Layer) |  |   Orchestrator   |
    +--------+---------+  +--------+---------+
             |                     |
             +----------+----------+
                        |
                        v
             +---------------------+
             |  repo_index.db      |
             |  (181MB, 70+ tables)|
             +----------+----------+
                        |
        +---------------+---------------+
        |               |               |
        v               v               v
+-------------+  +-------------+  +-------------+
|   Graph     |  |   Rules     |  |   Taint     |
|   Engine    |  | Orchestrator|  |   Engine    |
+------+------+  +------+------+  +------+------+
       |                |                |
       v                |                |
+-------------+         |                |
| graphs.db   |         |                |
| (126MB)     |         |                |
+------+------+         |                |
       |                |                |
       +-------+--------+--------+-------+
               |                 |
               v                 v
        +-------------+   +-------------+
        |     FCE     |   |   Context   |
        | (Evidence)  |   |    Query    |
        +------+------+   +------+------+
               |                 |
               +--------+--------+
                        |
                        v
               +------------------+
               |    Session       |
               |    Analyzer      |
               +--------+---------+
                        |
                        v
               +------------------+
               |    MachineL      |
               |    (ML Models)   |
               +------------------+
```

---

## Performance Characteristics

### By Codebase Size

| Size | Index | Full Analysis | Memory |
|------|-------|---------------|--------|
| <5K LOC | 30-60s | 2-3 min | ~500MB |
| 5-20K LOC | 1-2 min | 5-10 min | ~1GB |
| 20-50K LOC | 2-5 min | 10-15 min | ~1.5GB |
| 100K+ LOC | 5-10 min | 15-20 min | ~2GB |

### Database Sizes

| Codebase Size | repo_index.db | graphs.db |
|:--- |:--- |:--- |
| **Small (~5k LOC)** | ~50MB | ~30MB |
| **Medium (~20k LOC)** | ~180MB | ~120MB |
| **Large (~100k+ LOC)** | ~600MB+ | ~300MB+ |

---

## Key Technologies

| Component | Technology | Reason |
|-----------|------------|--------|
| **Database** | SQLite + WAL mode | Concurrent reads, transactional safety |
| **Parsing** | Tree-sitter + TypeScript API | Polyglot support, type information |
| **ML** | scikit-learn | Production-grade, interpretable |
| **CLI** | Click + Rich | Beautiful terminal UI |
| **Async** | asyncio | Parallel linter execution |
| **Graphs** | NetworkX-compatible | Standard algorithms |

---

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUD_IFDS_DEPTH` | 100 | Max taint analysis hops |
| `AUD_IFDS_MAX_PATHS` | 1000 | Max paths per sink |
| `AUD_IFDS_BUDGET` | 60 | Time budget (seconds) |
| `THEAUDITOR_TIMEOUT_INDEX_SECONDS` | 600 | Indexing timeout |
| `THEAUDITOR_TIMEOUT_TAINT_SECONDS` | 1800 | Taint analysis timeout |
| `THEAUDITOR_TIMEOUT_DEPS_SECONDS` | 1200 | Dependency check timeout |

### Output Directories

```
.pf/
├── repo_index.db          # Main indexed database
├── graphs.db              # Pre-computed graphs
├── raw/                   # JSON exports
│   ├── fce.json
│   ├── lint.json
│   └── taint.json
├── history/               # Audit journals
│   └── {run_type}/{timestamp}/journal.ndjson
├── ml/                    # ML artifacts
│   ├── model.joblib
│   └── session_history.db
└── .cache/                # AST cache (SHA256-keyed)
```

---

## Summary

TheAuditor is a **modular polyglot security analysis platform** that transforms source code into queryable facts through a sophisticated pipeline of AST extraction, graph construction, taint analysis, and ML-driven insights. The system enforces **Zero Fallback** (no silent failures), **Database-First** navigation (never re-parse during analysis), and **Evidence Over Opinion** (FCE provides facts, not subjective scores).

The architecture enables:
- Deep semantic understanding of 7+ programming languages
- Multi-hop interprocedural taint analysis
- 4-vector evidence convergence (FCE)
- ML-based risk prediction and impact forecasting
- AI agent behavior analysis for quality improvement
- Comprehensive CLI with 30+ commands across 9 categories

All components share a common SQLite backend with transactional integrity (WAL mode, manifest-receipt pairing), enabling reliable incremental analysis and efficient database-first querying.
