## Why

Rust extractor now populates language-agnostic tables (assignments, function_call_args, returns) per the recent `wire-rust-graph-integration` change. However, **no source/sink patterns are registered** for Rust, meaning taint analysis cannot identify what's user input (source) or dangerous (sink) in Rust code.

**Evidence from Prime Directive investigation (verified 2025-12-05):**
- `assignments` table: 688 Rust rows (extraction working!)
- `function_call_args` table: 3,549 Rust rows (extraction working!)
- TaintRegistry: 0 Rust patterns (Go has 50+, Python has 100+)
- Result: Taint flows cannot be detected despite having graph edges

## What Changes

1. **New Pattern File** - Create `theauditor/rules/rust/rust_injection_analyze.py`
   - **CRITICAL**: Must include a `find_rust_injection_issues()` stub function for orchestrator discovery
     - Orchestrator at `orchestrator.py:93` only discovers modules with `find_*` functions
     - See `sql_injection_analyze.py:48`: "Named find_* for orchestrator discovery - enables register_taint_patterns loading"
   - Include `register_taint_patterns()` function to register sources/sinks
   - Register Rust-specific source patterns (stdin, env, web frameworks)
   - Register Rust-specific sink patterns (Command, file writes, SQL)
   - Follow existing pattern from `rules/sql/sql_injection_analyze.py` (has both functions)

2. **Pattern Registration** - Wire patterns into TaintRegistry
   - Add language key "rust" to registry
   - Orchestrator auto-discovers via `collect_rule_patterns()` at `orchestrator.py:471-495`
   - Discovery requires `find_*` function in module (see point 1)

**NOT changing:**
- Rust extractor (already working)
- Graph strategies (RustTraitStrategy, RustAsyncStrategy already exist)
- Database schema
- Orchestrator logic (just adding a new module it will discover)

## Impact

- **Affected specs**: MODIFY existing `rust-extraction` capability (add source/sink patterns)
- **Affected code**:
  - NEW: `theauditor/rules/rust/rust_injection_analyze.py` (~150 lines)
  - NO WIRING CODE CHANGE: Orchestrator auto-discovers modules with `find_*` functions, then calls `register_taint_patterns()` if present
- **Risk**: Low - adding patterns only, not modifying extraction logic
- **Dependencies**: None (patterns are just data)

## Pattern Matching Strategy

**How patterns match database entries:**

TaintRegistry uses **exact string matching** against the `callee_function` column in `function_call_args` table. The Rust extractor stores function calls in one of these formats:
- Method calls: `method_name` (e.g., `new`, `arg`, `execute`)
- Qualified paths: `module::function` (e.g., `std::env::var`)
- Associated functions: `Type::method` (e.g., `Command::new`)

**Before implementation, run this query to verify actual format:**
```sql
SELECT DISTINCT callee_function FROM function_call_args
WHERE file LIKE '%.rs'
ORDER BY callee_function LIMIT 50;
```

**Pattern writing rules:**
1. Match the EXACT format stored in database
2. If database stores `Command::new`, pattern must be `Command::new` (not `std::process::Command::new`)
3. Multiple patterns may be needed for the same concept (e.g., both `Command` and `Command::new`)

## Success Criteria

After implementation:
```python
# TaintRegistry should have Rust patterns
from theauditor.taint.core import TaintRegistry
registry = TaintRegistry()

# get_source_patterns/get_sink_patterns return list[str] (flattened from all categories)
rust_sources = registry.get_source_patterns("rust")
rust_sinks = registry.get_sink_patterns("rust")
assert len(rust_sources) > 0, f"Expected Rust sources, got {rust_sources}"
assert len(rust_sinks) > 0, f"Expected Rust sinks, got {rust_sinks}"

# Taint analysis should find Rust flows
# (on codebases with actual vulnerabilities)
```

## Source Patterns (User Input)

Categories map to `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`.

**Verified against database 2025-12-05:** Patterns include BOTH qualified and unqualified forms for maximum coverage.

| Pattern | Category | Description | Verified |
|---------|----------|-------------|----------|
| `io::stdin` | user_input | Standard input | YES |
| `std::io::stdin` | user_input | Standard input (qualified) | for coverage |
| `std::env::args` | user_input | Command line arguments | YES |
| `args` | user_input | CLI args (unqualified) | YES |
| `std::env::var` | user_input | Environment variables | YES |
| `env::var` | user_input | Environment variables (short) | YES |
| `std::env::vars` | user_input | All environment variables | YES |
| `getenv` | user_input | C-style getenv | YES |
| `std::fs::read_to_string` | user_input | File contents as string | YES |
| `fs::read_to_string` | user_input | File contents (short) | YES |
| `read_file` | user_input | File read helper | YES |
| `read_line` | user_input | Line read from stdin | YES |
| `read_user_input` | user_input | User input helper | YES |
| `BufReader::new` | user_input | Buffered reader (often stdin) | YES |
| `serde_json::from_reader` | user_input | JSON deserialization from reader | YES |
| `Json` | http_request | Actix-web JSON body | YES |
| `web::Json` | http_request | Actix-web JSON body (qualified) | for coverage |
| `web::Path` | http_request | Actix-web path parameters | for coverage |
| `web::Query` | http_request | Actix-web query parameters | for coverage |
| `web::Form` | http_request | Actix-web form data | for coverage |
| `axum::extract::Json` | http_request | Axum JSON body | for coverage |
| `axum::extract::Path` | http_request | Axum path parameters | for coverage |
| `axum::extract::Query` | http_request | Axum query parameters | for coverage |
| `rocket::request` | http_request | Rocket request data | for coverage |
| `rocket::form` | http_request | Rocket form data | for coverage |
| `warp::body::json` | http_request | Warp JSON body | for coverage |
| `warp::path::param` | http_request | Warp path parameters | for coverage |

## Sink Patterns (Dangerous Operations)

Categories map to `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`.

**Verified against database 2025-12-05:** Patterns include BOTH qualified and unqualified forms for maximum coverage.

| Pattern | Category | Description | Verified |
|---------|----------|-------------|----------|
| `Command::new` | command | Shell command execution | YES |
| `execute_command` | command | Command execution helper | YES |
| `command` | command | Generic command call | YES |
| `sqlx::query` | sql | SQL query (sqlx) | YES |
| `sqlx::query_as` | sql | SQL query with mapping | YES |
| `execute` | sql | SQL execute | YES |
| `execute_sql` | sql | SQL execute helper | YES |
| `diesel::sql_query` | sql | SQL query (diesel) | for coverage |
| `std::fs::write` | path | File write | YES |
| `fs::write` | path | File write (short) | YES |
| `write_file` | path | File write helper | YES |
| `ptr::write` | code_injection | Unsafe pointer write | YES |
| `ptr::write_volatile` | code_injection | Volatile pointer write | YES |
| `ptr::read` | code_injection | Unsafe pointer read | YES |
| `ptr::read_volatile` | code_injection | Volatile pointer read | YES |
| `std::ptr::write` | code_injection | Unsafe pointer write (qualified) | for coverage |
| `std::mem::transmute` | code_injection | Type transmutation | for coverage |
| `connect` | ssrf | Network connection | YES |
| `TcpStream::connect` | ssrf | TCP connection (qualified) | for coverage |
