## Why

Go is the dominant language for cloud-native infrastructure (Kubernetes, Docker, Terraform, Prometheus, etcd). Security-critical backend services, CLI tools, and distributed systems are increasingly written in Go. TheAuditor claims polyglot support but has zero Go capability - no extractor, no schema, no storage, no security rules.

Go is significantly simpler to support than Rust:
- No lifetimes, no borrow checker, no macros
- Built-in AST tooling (`go/ast`, `go/parser`) or tree-sitter-go
- Simple type system (interfaces, not traits)
- Explicit error handling (no exceptions)

The ROI is high: large target market, low implementation complexity.

## What Changes

**Phase 0: CRITICAL Pre-Implementation Verification**
- Verify tree-sitter-go grammar supports Go 1.18+ generics (BLOCKING - parser will crash on `func[T any]` if grammar too old)
- Add `vendor/` to excluded directories (Go projects vendor dependencies, indexing bloats DB 10x-50x)

**Phase 1: Foundation (Schema + Core Extraction)**
- Create 22 `go_*` schema tables following the normalized pattern (see design.md for full definitions):
  - 18 original tables + go_variables + go_type_params + go_captured_vars + go_middleware
- Wire tree-sitter-go into ast_parser.py (available in package, needs initialization)
- Implement extraction for core constructs: packages, imports, structs, interfaces, functions, methods
- **NEW**: Extract package-level variables (critical for race detection: `is_package_level=1`)
- **NEW**: Extract generic type parameters (`func[T any]`, `type Stack[T comparable]`)
- Wire extraction output to storage layer via go_storage.py
- Integrate into indexer pipeline

**Phase 2: Concurrency & Error Handling**
- Goroutine tracking (`go` statements)
- **NEW**: Captured variable tracking in goroutines (stores in go_captured_vars)
  - Detect loop variable capture (is_loop_var=1) - #1 source of data races
- Channel declarations and operations (send/receive)
- Defer statement tracking
- Error return pattern analysis
- Panic/recover detection

**Phase 3: Framework Detection**
- **NEW**: net/http standard library detection (more common than frameworks in Go!)
- Gin, Echo, Fiber, Chi web frameworks
- **NEW**: Middleware detection (.Use() calls) - critical for security auditing
- GORM, sqlx, ent ORM patterns
- gRPC service definitions
- Cobra CLI patterns

**Phase 4: Security Rules**
- SQL injection via string concatenation
- Command injection via os/exec
- Template injection (html/template, text/template)
- Insecure crypto usage
- Race condition patterns:
  - **NEW**: Captured loop variable detection (go_captured_vars WHERE is_loop_var=1)
  - Package-level variable access from goroutines (go_variables WHERE is_package_level=1)
  - Shared state without sync primitives

## Impact

- Affected specs: `indexer` (new language support)
- Affected code:
  - `theauditor/ast_parser.py:52-103` - Add Go to _init_tree_sitter_parsers
  - `theauditor/ast_parser.py:240-253` - Add .go to extension mapping
  - `theauditor/indexer/extractors/go.py` - NEW (auto-registers via discovery)
  - `theauditor/ast_extractors/go_impl.py` - NEW
  - `theauditor/indexer/schemas/go_schema.py` - NEW (22 TableSchema definitions)
  - `theauditor/indexer/storage/go_storage.py` - NEW
  - `theauditor/indexer/storage/__init__.py:20-30` - Add GoStorage to DataStorer
  - `theauditor/indexer/database/go_database.py` - NEW (GoDatabaseMixin)
  - `theauditor/indexer/database/__init__.py:17-27` - Add mixin to DatabaseManager
  - `theauditor/rules/go_security.py` - NEW
  - `theauditor/linters/go_lint.py` - NEW (staticcheck/golangci-lint wrapper)
  - File walker exclusions - Add `vendor/` to excluded directories
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

## Verification

After implementation, verify with:
```bash
# 1. Check tree-sitter-go is wired
.venv/Scripts/python.exe -c "from theauditor.ast_parser import ASTParser; p = ASTParser(); print('go' in p.parsers)"

# 2. Run indexer on Go project
aud full --index --target /path/to/go/project

# 3. Verify tables populated
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
for table in ['go_packages', 'go_functions', 'go_structs']:
    c.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'{table}: {c.fetchone()[0]} rows')
"
```
