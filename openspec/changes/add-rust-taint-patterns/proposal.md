## Why

Rust extractor now populates language-agnostic tables (assignments, function_call_args, returns) per the recent `wire-rust-graph-integration` change. However, **no source/sink patterns are registered** for Rust, meaning taint analysis cannot identify what's user input (source) or dangerous (sink) in Rust code.

**Evidence from Prime Directive investigation:**
- `assignments` table: 321 Rust rows (extraction working!)
- `function_call_args` table: 1,620 Rust rows (extraction working!)
- TaintRegistry: 0 Rust patterns (Go has 50+, Python has 100+)
- Result: Taint flows cannot be detected despite having graph edges

## What Changes

1. **New Pattern File** - Create `theauditor/rules/rust/rust_injection_analyze.py`
   - Register Rust-specific source patterns (stdin, env, web frameworks)
   - Register Rust-specific sink patterns (Command, file writes, SQL)
   - Follow existing pattern from `rules/go/injection_analyze.py`

2. **Pattern Registration** - Wire patterns into TaintRegistry
   - Add language key "rust" to registry
   - Orchestrator auto-discovers via `collect_rule_patterns()` at `orchestrator.py:471-495`

**NOT changing:**
- Rust extractor (already working)
- Graph strategies (RustTraitStrategy, RustAsyncStrategy already exist)
- Database schema
- Orchestrator (auto-discovers `register_taint_patterns()` functions)

## Impact

- **Affected specs**: MODIFY existing `rust-extraction` capability (add source/sink patterns)
- **Affected code**:
  - NEW: `theauditor/rules/rust/rust_injection_analyze.py` (~150 lines)
  - NO WIRING CODE CHANGE: Orchestrator auto-discovers modules with `register_taint_patterns()` function
- **Risk**: Low - adding patterns only, not modifying extraction logic
- **Dependencies**: None (patterns are just data)

## Success Criteria

After implementation:
```python
# TaintRegistry should have Rust patterns
from theauditor.taint.core import TaintRegistry
registry = TaintRegistry()

# Use API methods (sources/sinks are dict[str, dict[str, list[str]]])
rust_sources = registry.get_source_patterns("rust")
rust_sinks = registry.get_sink_patterns("rust")
assert len(rust_sources) > 0, f"Expected Rust sources, got {rust_sources}"
assert len(rust_sinks) > 0, f"Expected Rust sinks, got {rust_sinks}"

# Taint analysis should find Rust flows
# (on codebases with actual vulnerabilities)
```

## Source Patterns (User Input)

Categories map to `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`.

| Pattern | Category | Description |
|---------|----------|-------------|
| `std::io::stdin` | user_input | Standard input |
| `std::env::args` | user_input | Command line arguments |
| `std::env::var` | user_input | Environment variables |
| `std::fs::read` | user_input | File contents |
| `std::fs::read_to_string` | user_input | File contents as string |
| `web::Json` | http_request | Actix-web JSON body |
| `web::Path` | http_request | Actix-web path parameters |
| `web::Query` | http_request | Actix-web query parameters |
| `axum::extract::Json` | http_request | Axum JSON body |
| `axum::extract::Path` | http_request | Axum path parameters |
| `axum::extract::Query` | http_request | Axum query parameters |
| `rocket::request` | http_request | Rocket request data |

## Sink Patterns (Dangerous Operations)

Categories map to `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`.

| Pattern | Category | Description |
|---------|----------|-------------|
| `std::process::Command` | command | Shell command execution |
| `std::process::exec` | command | Process execution |
| `sqlx::query` | sql | SQL query (sqlx) |
| `sqlx::query_as` | sql | SQL query with mapping |
| `diesel::sql_query` | sql | SQL query (diesel) |
| `std::fs::write` | path | File write |
| `std::fs::File::create` | path | File creation |
| `std::ptr::write` | code_injection | Unsafe pointer write |
| `std::mem::transmute` | code_injection | Type transmutation |
