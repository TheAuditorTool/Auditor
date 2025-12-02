## Why

Go is the dominant language for cloud-native infrastructure (Kubernetes, Docker, Terraform, Prometheus, etcd). Security-critical backend services, CLI tools, and distributed systems are increasingly written in Go. TheAuditor claims polyglot support but has zero Go capability - no extractor, no schema, no storage, no security rules.

Go is significantly simpler to support than Rust:
- No lifetimes, no borrow checker, no macros
- Built-in AST tooling (`go/ast`, `go/parser`) or tree-sitter-go
- Simple type system (interfaces, not traits)
- Explicit error handling (no exceptions)

The ROI is high: large target market, low implementation complexity.

## What Changes

**Phase 0: CRITICAL Pre-Implementation Verification** *(See specs/indexer/spec.md: Go Parser Compatibility)*
- Verify tree-sitter-go grammar supports Go 1.18+ generics (BLOCKING - parser will crash on `func[T any]` if grammar too old)
- Add `vendor/` to excluded directories (Go projects vendor dependencies, indexing bloats DB 10x-50x)

**Phase 1: Foundation (Schema + Core Extraction)** *(See specs/indexer/spec.md: Go Language Extraction)*
- Create 22 `go_*` schema tables following the normalized pattern (see design.md Decision 1)
- Wire tree-sitter-go into ast_parser.py (available in package, needs initialization)
- Implement extraction for core constructs: packages, imports, structs, interfaces, functions, methods
- Extract package-level variables (critical for race detection: `is_package_level=1`)
- Extract generic type parameters (`func[T any]`, `type Stack[T comparable]`)
- Wire extraction output to storage layer via go_storage.py
- Integrate into indexer pipeline

**Phase 2: Concurrency & Error Handling** *(See specs/indexer/spec.md: Go Concurrency Tracking)*
- Goroutine tracking (`go` statements)
- Captured variable tracking in goroutines (stores in go_captured_vars)
  - Detect loop variable capture (is_loop_var=1) - #1 source of data races
- Channel declarations and operations (send/receive)
- Defer statement tracking
- Error return pattern analysis
- Panic/recover detection

**Phase 3: Framework Detection + Graph Strategies** *(See specs/graph/spec.md)*
- net/http standard library detection (more common than frameworks in Go!)
- Gin, Echo, Fiber, Chi web frameworks
- Middleware detection (.Use() calls) - critical for security auditing
- GORM, sqlx, ent ORM patterns
- gRPC service definitions
- Cobra CLI patterns
- **NEW: Graph Strategy: `go_http.py`** - Data flow through HTTP handlers
- **NEW: Graph Strategy: `go_orm.py`** - GORM/sqlx relationship expansion

**Phase 4: Security Rules** *(See specs/rules/spec.md - to be created)*
- SQL injection via string concatenation
- Command injection via os/exec
- Template injection (html/template, text/template)
- Insecure crypto usage
- Race condition patterns:
  - Captured loop variable detection (go_captured_vars WHERE is_loop_var=1)
  - Package-level variable access from goroutines (go_variables WHERE is_package_level=1)
  - Shared state without sync primitives

## Complete Component Inventory

**CRITICAL**: Go support requires changes across ALL language-modular components. TheAuditor has 9 distinct component layers that require language-specific implementations:

### Layer 1: Configuration *(specs/indexer/spec.md)*
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/indexer/config.py:23-53` | Add `"vendor"` to SKIP_DIRS | Line 27 has node_modules |
| `theauditor/indexer/config.py:79-92` | Add `.go` to SUPPORTED_AST_EXTENSIONS | After `.tfvars` |

### Layer 2: AST Parser *(specs/indexer/spec.md)*
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/ast_parser.py:52-103` | Add Go to `_init_tree_sitter_parsers()` | Follow HCL pattern at lines 86-96 |
| `theauditor/ast_parser.py:239-253` | Add `.go` to `_detect_language()` ext_map | After `.tfvars` |

### Layer 3: Schema Definitions *(specs/indexer/spec.md)*
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/indexer/schemas/go_schema.py` | NEW - 22 TableSchema definitions | Copy from `python_schema.py` |
| `theauditor/indexer/schema.py:5-24` | Import GO_TABLES, add to TABLES dict | Follow PYTHON_TABLES pattern |
| `theauditor/indexer/schema.py:27` | Update assertion: 170 → 192 | `assert len(TABLES) == 192` |

### Layer 4: Database Mixin *(specs/indexer/spec.md)*
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/indexer/database/go_database.py` | NEW - GoDatabaseMixin class | Copy from `python_database.py` |
| `theauditor/indexer/database/__init__.py:7-14` | Import GoDatabaseMixin | Add import line |
| `theauditor/indexer/database/__init__.py:17-27` | Add to DatabaseManager inheritance | After NodeDatabaseMixin |

### Layer 5: Storage Handlers *(specs/indexer/spec.md)*
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/indexer/storage/go_storage.py` | NEW - GoStorage class with handlers | Copy from `python_storage.py` |
| `theauditor/indexer/storage/__init__.py:6-9` | Import GoStorage | Add import line |
| `theauditor/indexer/storage/__init__.py:20-23` | Instantiate self.go | After self.infrastructure |
| `theauditor/indexer/storage/__init__.py:25-30` | Add `**self.go.handlers` | After infrastructure.handlers |

### Layer 6: AST Extractors *(specs/indexer/spec.md)*
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/ast_extractors/go_impl.py` | NEW - Tree-sitter extraction functions | Copy from `hcl_impl.py` |
| `theauditor/indexer/extractors/go.py` | NEW - GoExtractor(BaseExtractor) | Copy from `terraform.py` |

### Layer 7: Graph Strategies *(specs/graph/spec.md)* **← MISSING FROM ORIGINAL TICKET**
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/graph/strategies/go_http.py` | NEW - GoHttpStrategy for net/http + frameworks | Copy from `node_express.py` |
| `theauditor/graph/strategies/go_orm.py` | NEW - GoOrmStrategy for GORM/sqlx | Copy from `python_orm.py` |
| `theauditor/graph/dfg_builder.py:11-14` | Import Go strategies | Add import lines |
| `theauditor/graph/dfg_builder.py:27-32` | Add to self.strategies list | After NodeExpressStrategy |

### Layer 8: Rules *(specs/rules/spec.md - to be created)*
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/rules/go/` | NEW directory with Go-specific rules | Copy structure from `rules/python/` |
| `theauditor/rules/go/__init__.py` | NEW - Package init | |
| `theauditor/rules/go/injection_analyze.py` | NEW - SQL/command injection | Reference `python/python_injection_analyze.py` |
| `theauditor/rules/go/crypto_analyze.py` | NEW - Crypto misuse | Reference `python/python_crypto_analyze.py` |
| `theauditor/rules/go/concurrency_analyze.py` | NEW - Race condition detection | Go-specific |

### Layer 9: Framework Registry
| File | Change | Reference |
|------|--------|-----------|
| `theauditor/framework_registry.py` | Add Go frameworks to FRAMEWORK_REGISTRY | After JavaScript frameworks |

## Impact

- Affected specs:
  - `indexer` (new language support) - PRIMARY
  - `graph` (new strategies) - **CRITICAL - WAS MISSING**
  - `rules` (new security rules) - NEW SPEC NEEDED
- New files: ~15 Python files across 8 component layers
- Modified files: ~12 existing files (registrations, assertions, imports)
- Breaking changes: None (new capability)
- Dependencies:
  - **CRITICAL**: tree-sitter-go grammar MUST support Go 1.18+ generics
    - Task 0.0.1 verifies this BEFORE any implementation
    - If grammar too old, parser crashes on `func[T any]`
  - tree-sitter-go: Available in tree-sitter-language-pack, but NOT yet wired in ast_parser.py
  - OSV scanning: Already works via go.mod parsing

## Implementation Reference Points

Read these files BEFORE starting implementation:

**Go follows the HCL/Terraform pattern** (tree-sitter based), NOT Python (built-in ast) or JS/TS (Node.js semantic parser).

| Component | Reference File | What to Copy |
|-----------|----------------|--------------|
| **AST Extraction** | `ast_extractors/hcl_impl.py` | Tree-sitter query pattern for go_impl.py |
| **Extractor wrapper** | `indexer/extractors/terraform.py` | Thin wrapper pattern for go.py |
| Schema pattern | `indexer/schemas/python_schema.py:1-95` | TableSchema with Column, indexes |
| Database mixin | `indexer/database/python_database.py:6-60` | add_* methods using generic_batches |
| Mixin registration | `indexer/database/__init__.py:17-27` | Add GoDatabaseMixin to class composition |
| Storage handlers | `indexer/storage/python_storage.py:1-80` | Handler dict pattern |
| Storage wiring | `indexer/storage/__init__.py:20-30` | Add GoStorage to DataStorer |
| Extractor base | `indexer/extractors/__init__.py:12-31` | BaseExtractor interface |
| Extractor auto-discovery | `indexer/extractors/__init__.py:86-118` | Just create file, auto-registers |
| AST parser init | `ast_parser.py:52-103` | Add Go to _init_tree_sitter_parsers |
| Extension mapping | `ast_parser.py:240-253` | Add .go to ext_map |
| **Graph strategy** | `graph/strategies/python_orm.py` | ORM expansion pattern |
| **HTTP strategy** | `graph/strategies/node_express.py` | Middleware chain pattern |
| **DFG registration** | `graph/dfg_builder.py:27-32` | Strategy list |
| **Rules structure** | `rules/python/` | Language-specific rule directory |

## Verification

After implementation, verify with:
```bash
# 1. Check tree-sitter-go is wired
python -c "from theauditor.ast_parser import ASTParser; p = ASTParser(); print('go' in p.parsers)"

# 2. Run indexer on Go project
aud full --index --target /path/to/go/project

# 3. Verify tables populated
python -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
for table in ['go_packages', 'go_functions', 'go_structs', 'go_variables', 'go_type_params']:
    c.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'{table}: {c.fetchone()[0]} rows')
"

# 4. Verify graph strategies loaded
python -c "
from theauditor.graph.dfg_builder import DFGBuilder
builder = DFGBuilder('.pf/repo_index.db')
print([s.name for s in builder.strategies])
# Should include: GoHttpStrategy, GoOrmStrategy
"

# 5. Verify rules discovered
python -c "
from theauditor.rules.orchestrator import RulesOrchestrator
orch = RulesOrchestrator()
go_rules = [r for r in orch.rules if 'go' in r.__module__]
print(f'Go rules: {len(go_rules)}')
"
```
