## 1. Phase 1: Foundation (Schema + Core Extraction)

### 1.0 AST Parser Integration (PREREQUISITE)
- [ ] 1.0.1 Add Go parser to `ast_parser.py:52-103` (_init_tree_sitter_parsers)
  ```python
  try:
      go_lang = get_language("go")
      go_parser = get_parser("go")
      self.parsers["go"] = go_parser
      self.languages["go"] = go_lang
  except Exception as e:
      print(f"[INFO] Go tree-sitter not available: {e}")
  ```
- [ ] 1.0.2 Add `.go` extension to `ast_parser.py:240-253` (_detect_language)
  ```python
  ".go": "go",
  ```
- [ ] 1.0.3 Verify tree-sitter-go parses sample file:
  ```bash
  .venv/Scripts/python.exe -c "
  from tree_sitter_language_pack import get_parser
  p = get_parser('go')
  tree = p.parse(b'package main\nfunc main() {}')
  print(tree.root_node.sexp())
  "
  ```

### 1.1 Schema Creation
- [ ] 1.1.1 Create `theauditor/indexer/schemas/go_schema.py` with 18 TableSchema definitions (copy from design.md Decision 1)
- [ ] 1.1.2 Add `GO_TABLES` dict export at bottom of go_schema.py
- [ ] 1.1.3 Import GO_TABLES in `indexer/schemas/__init__.py` (if exists) or in base_database.py
- [ ] 1.1.4 Add go tables to schema initialization - find where PYTHON_TABLES/NODE_TABLES are registered and add GO_TABLES
- [ ] 1.1.5 Verify tables created: `aud full --index` then check sqlite for go_* tables

### 1.2 Database Methods
- [ ] 1.2.1 Create `theauditor/indexer/database/go_database.py` with GoDatabaseMixin class
- [ ] 1.2.2 Implement `add_go_package(file_path, line, name, import_path)` using self.generic_batches["go_packages"]
- [ ] 1.2.3 Implement `add_go_import(file_path, line, path, alias, is_dot)`
- [ ] 1.2.4 Implement `add_go_struct(file_path, line, name, is_exported, doc_comment)`
- [ ] 1.2.5 Implement `add_go_struct_field(file_path, struct_name, field_name, field_type, tag, is_embedded, is_exported)`
- [ ] 1.2.6 Implement `add_go_interface(file_path, line, name, is_exported, doc_comment)`
- [ ] 1.2.7 Implement `add_go_interface_method(file_path, interface_name, method_name, signature)`
- [ ] 1.2.8 Implement `add_go_function(file_path, line, name, signature, is_exported, is_async, doc_comment)`
- [ ] 1.2.9 Implement `add_go_method(file_path, line, receiver_type, receiver_name, is_pointer_receiver, name, signature, is_exported)`
- [ ] 1.2.10 Implement `add_go_func_param(file_path, func_name, func_line, param_index, param_name, param_type, is_variadic)`
- [ ] 1.2.11 Implement `add_go_func_return(file_path, func_name, func_line, return_index, return_name, return_type)`
- [ ] 1.2.12 Implement `add_go_constant(file_path, line, name, value, type, is_exported)`
- [ ] 1.2.13 Add `from .go_database import GoDatabaseMixin` to `indexer/database/__init__.py`
- [ ] 1.2.14 Add `GoDatabaseMixin` to DatabaseManager class inheritance list at `indexer/database/__init__.py:17-27`

### 1.3 Core Extraction - AST Implementation
- [ ] 1.3.1 Create `theauditor/ast_extractors/go_impl.py`
- [ ] 1.3.2 Implement `extract_go_packages(tree, content, file_path)` - query `package_clause` nodes
- [ ] 1.3.3 Implement `extract_go_imports(tree, content, file_path)` - query `import_declaration` > `import_spec`
- [ ] 1.3.4 Implement `extract_go_structs(tree, content, file_path)` - query `type_declaration` > `struct_type`
- [ ] 1.3.5 Implement `extract_go_struct_fields(tree, content, file_path)` - query `field_declaration_list`
- [ ] 1.3.6 Implement `extract_go_interfaces(tree, content, file_path)` - query `type_declaration` > `interface_type`
- [ ] 1.3.7 Implement `extract_go_interface_methods(tree, content, file_path)` - query `method_spec_list`
- [ ] 1.3.8 Implement `extract_go_functions(tree, content, file_path)` - query `function_declaration`
- [ ] 1.3.9 Implement `extract_go_methods(tree, content, file_path)` - query `method_declaration`
- [ ] 1.3.10 Implement `extract_go_calls(tree, content, file_path)` - query `call_expression`
- [ ] 1.3.11 Implement `extract_go_assignments(tree, content, file_path)` - query `short_var_declaration`, `assignment_statement`
- [ ] 1.3.12 Implement `extract_go_constants(tree, content, file_path)` - query `const_declaration`

### 1.4 Extractor Class
- [ ] 1.4.1 Create `theauditor/indexer/extractors/go.py` with GoExtractor(BaseExtractor)
- [ ] 1.4.2 Implement `supported_extensions()` returning `[".go"]`
- [ ] 1.4.3 Implement `extract()` method that:
  - Calls all go_impl extraction functions
  - Returns dict with keys matching storage handler expectations (go_packages, go_imports, etc.)
- [ ] 1.4.4 Note: Extractor auto-registers via `indexer/extractors/__init__.py:86-118` discovery - no manual registration needed

### 1.5 Storage Layer
- [ ] 1.5.1 Create `theauditor/indexer/storage/go_storage.py` with GoStorage class
- [ ] 1.5.2 Implement `__init__` with handlers dict mapping extraction keys to handler methods
- [ ] 1.5.3 Implement `_store_go_packages(file_path, data, jsx_pass)` calling db.add_go_package()
- [ ] 1.5.4 Implement `_store_go_imports(file_path, data, jsx_pass)`
- [ ] 1.5.5 Implement `_store_go_structs(file_path, data, jsx_pass)`
- [ ] 1.5.6 Implement `_store_go_struct_fields(file_path, data, jsx_pass)`
- [ ] 1.5.7 Implement `_store_go_interfaces(file_path, data, jsx_pass)`
- [ ] 1.5.8 Implement `_store_go_interface_methods(file_path, data, jsx_pass)`
- [ ] 1.5.9 Implement `_store_go_functions(file_path, data, jsx_pass)`
- [ ] 1.5.10 Implement `_store_go_methods(file_path, data, jsx_pass)`
- [ ] 1.5.11 Implement `_store_go_func_params(file_path, data, jsx_pass)`
- [ ] 1.5.12 Implement `_store_go_func_returns(file_path, data, jsx_pass)`
- [ ] 1.5.13 Implement `_store_go_constants(file_path, data, jsx_pass)`
- [ ] 1.5.14 Add `from .go_storage import GoStorage` to `indexer/storage/__init__.py`
- [ ] 1.5.15 Add `self.go = GoStorage(db_manager, counts)` to DataStorer.__init__
- [ ] 1.5.16 Add `**self.go.handlers` to DataStorer.handlers dict

### 1.6 Phase 1 Verification
- [ ] 1.6.1 Create sample Go file for testing:
  ```go
  package main
  import "fmt"
  type User struct { Name string `json:"name"` }
  func (u *User) Greet() string { return "Hello " + u.Name }
  func main() { fmt.Println("test") }
  ```
- [ ] 1.6.2 Run `aud full --index` on directory with sample file
- [ ] 1.6.3 Verify go_* tables populated:
  ```bash
  .venv/Scripts/python.exe -c "
  import sqlite3
  conn = sqlite3.connect('.pf/repo_index.db')
  for t in ['go_packages','go_imports','go_structs','go_struct_fields','go_functions','go_methods']:
      c = conn.cursor()
      c.execute(f'SELECT COUNT(*) FROM {t}')
      print(f'{t}: {c.fetchone()[0]}')
  "
  ```
- [ ] 1.6.4 Test `aud context query --symbol main` returns Go function
- [ ] 1.6.5 Verify no regression on Python/JS extraction (run on mixed project)

## 2. Phase 2: Concurrency & Error Handling

### 2.1 Goroutine Tracking
- [ ] 2.1.1 Implement `extract_go_goroutines(tree, content, file_path)` - query `go_statement`
- [ ] 2.1.2 Detect spawned expression (call_expression or func_literal)
- [ ] 2.1.3 Extract containing function name by walking up AST
- [ ] 2.1.4 Set is_anonymous=True for `go func() {...}()` patterns
- [ ] 2.1.5 Add `add_go_goroutine(file_path, line, containing_func, spawned_expr, is_anonymous)` to go_database.py
- [ ] 2.1.6 Add `_store_go_goroutines()` to go_storage.py

### 2.2 Channel Operations
- [ ] 2.2.1 Implement `extract_go_channels(tree, content, file_path)` - detect `make(chan T)` patterns
- [ ] 2.2.2 Implement `extract_go_channel_ops(tree, content, file_path)` - query `send_statement`, `receive_expression`
- [ ] 2.2.3 Add database methods: `add_go_channel()`, `add_go_channel_op()`
- [ ] 2.2.4 Add storage handlers: `_store_go_channels()`, `_store_go_channel_ops()`

### 2.3 Defer Tracking
- [ ] 2.3.1 Implement `extract_go_defers(tree, content, file_path)` - query `defer_statement`
- [ ] 2.3.2 Extract deferred call expression
- [ ] 2.3.3 Add `add_go_defer(file_path, line, containing_func, deferred_expr)` to database
- [ ] 2.3.4 Add `_store_go_defer_statements()` to storage

### 2.4 Error Handling Patterns
- [ ] 2.4.1 Implement `extract_go_error_returns(tree, content, file_path)` - detect functions with `error` return type
- [ ] 2.4.2 Check last return type in `result` node for "error" identifier
- [ ] 2.4.3 Add `add_go_error_return(file_path, line, func_name, returns_error)` to database
- [ ] 2.4.4 Add `_store_go_error_returns()` to storage

### 2.5 Type Assertions
- [ ] 2.5.1 Implement `extract_go_type_assertions(tree, content, file_path)` - query `type_assertion_expression`
- [ ] 2.5.2 Detect type switches via `type_switch_statement`
- [ ] 2.5.3 Add database and storage methods

## 3. Phase 3: Framework Detection

### 3.1 Web Framework Detection
- [ ] 3.1.1 Add Go web frameworks to `framework_registry.py`:
  ```python
  "gin": {
      "language": "go",
      "detection_sources": {"go.mod": "line_search"},
      "import_patterns": ["github.com/gin-gonic/gin"],
  },
  ```
- [ ] 3.1.2 Add Echo, Fiber, Chi with same pattern
- [ ] 3.1.3 Update FrameworkDetector to check go_imports table for import paths

### 3.2 Route Extraction
- [ ] 3.2.1 Implement `extract_go_routes(tree, content, file_path)` - detect `r.GET("/path", handler)` patterns
- [ ] 3.2.2 Support Gin pattern: method call on router variable with HTTP method name
- [ ] 3.2.3 Support Echo pattern: same but e.GET, e.POST
- [ ] 3.2.4 Support Fiber pattern: app.Get, app.Post
- [ ] 3.2.5 Store in go_routes table (framework, method, path, handler_func)

### 3.3 ORM Detection
- [ ] 3.3.1 Detect GORM via import `gorm.io/gorm`
- [ ] 3.3.2 Detect sqlx via import `github.com/jmoiron/sqlx`
- [ ] 3.3.3 Detect ent via import `entgo.io/ent`

### 3.4 Other Frameworks
- [ ] 3.4.1 Detect gRPC via `google.golang.org/grpc` import
- [ ] 3.4.2 Detect Cobra via `github.com/spf13/cobra` import
- [ ] 3.4.3 Detect Viper via `github.com/spf13/viper` import

## 4. Phase 4: Security Rules

### 4.1 Injection Vulnerabilities
- [ ] 4.1.1 Create `theauditor/rules/go_security.py`
- [ ] 4.1.2 SQL injection rule: detect `db.Query(fmt.Sprintf(...))` or string concat passed to Query/Exec
- [ ] 4.1.3 Command injection rule: detect `exec.Command()` with non-literal first arg
- [ ] 4.1.4 Template injection rule: detect `template.HTML()` with variable input
- [ ] 4.1.5 Path traversal rule: detect `filepath.Join()` with user input containing `..`

### 4.2 Crypto Misuse
- [ ] 4.2.1 Detect `math/rand` import used near crypto operations (should use `crypto/rand`)
- [ ] 4.2.2 Detect MD5/SHA1 usage for security purposes (weak hashes)
- [ ] 4.2.3 Detect hardcoded secrets via regex patterns in string literals
- [ ] 4.2.4 Detect `InsecureSkipVerify: true` in TLS configs

### 4.3 Concurrency Issues
- [ ] 4.3.1 Flag goroutines accessing package-level variables without sync primitives
- [ ] 4.3.2 Detect shared map access from multiple goroutines (race condition)
- [ ] 4.3.3 Flag missing mutex around shared state modifications

### 4.4 Error Handling Issues
- [ ] 4.4.1 Detect ignored errors: `_ = someFunc()` where someFunc returns error
- [ ] 4.4.2 Detect panic in library code (non-main packages)
- [ ] 4.4.3 Detect recover without re-panic for unexpected errors

### 4.5 Linting Integration
- [ ] 4.5.1 Create `theauditor/linters/go_lint.py`
- [ ] 4.5.2 Implement staticcheck wrapper: `staticcheck ./...` with JSON output
- [ ] 4.5.3 Implement golangci-lint wrapper: `golangci-lint run --out-format json`
- [ ] 4.5.4 Parse JSON output into standard findings format
- [ ] 4.5.5 Register in linter pipeline (check where Python/JS linters are registered)

## 5. Integration & Testing

### 5.1 Test Coverage
- [ ] 5.1.1 Unit tests for each go_impl extraction function
- [ ] 5.1.2 Integration test: index sample Go project, verify all tables populated correctly
- [ ] 5.1.3 Test framework detection on real projects (gin-gonic/gin examples)
- [ ] 5.1.4 Test security rules precision (use known-vulnerable patterns)

### 5.2 Documentation
- [ ] 5.2.1 Update indexer spec with Go capability (via this openspec)
- [ ] 5.2.2 Document go_* table schemas in codebase (docstrings in go_schema.py)
- [ ] 5.2.3 Add Go examples to `aud context` help text
- [ ] 5.2.4 Document security rule rationale in go_security.py docstrings
