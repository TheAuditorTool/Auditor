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
   - Register sources and sinks during pipeline initialization

**NOT changing:**
- Rust extractor (already working)
- Graph strategies (RustTraitStrategy, RustAsyncStrategy already exist)
- Database schema

## Impact

- **Affected specs**: MODIFY existing `rust-extraction` capability (add source/sink patterns)
- **Affected code**:
  - NEW: `theauditor/rules/rust/rust_injection_analyze.py` (~150 lines)
  - MODIFY: Registration hook (location TBD based on existing pattern)
- **Risk**: Low - adding patterns only, not modifying extraction logic
- **Dependencies**: None (patterns are just data)

## Success Criteria

After implementation:
```python
# TaintRegistry should have Rust patterns
from theauditor.taint.core import TaintRegistry
registry = TaintRegistry()
assert len(registry.sources.get("rust", [])) > 0
assert len(registry.sinks.get("rust", [])) > 0

# Taint analysis should find Rust flows
# (on codebases with actual vulnerabilities)
```

## Source Patterns (User Input)

| Pattern | Category | Description |
|---------|----------|-------------|
| `std::io::stdin` | stdin | Standard input |
| `std::env::args` | env | Command line arguments |
| `std::env::var` | env | Environment variables |
| `std::fs::read` | file_read | File contents |
| `std::fs::read_to_string` | file_read | File contents as string |
| `web::Json` | web_input | Actix-web JSON body |
| `web::Path` | web_input | Actix-web path parameters |
| `web::Query` | web_input | Actix-web query parameters |
| `axum::extract::Json` | web_input | Axum JSON body |
| `axum::extract::Path` | web_input | Axum path parameters |
| `axum::extract::Query` | web_input | Axum query parameters |
| `rocket::request` | web_input | Rocket request data |

## Sink Patterns (Dangerous Operations)

| Pattern | Category | Description |
|---------|----------|-------------|
| `std::process::Command` | command_injection | Shell command execution |
| `std::process::exec` | command_injection | Process execution |
| `sqlx::query` | sql_injection | SQL query (sqlx) |
| `sqlx::query_as` | sql_injection | SQL query with mapping |
| `diesel::sql_query` | sql_injection | SQL query (diesel) |
| `std::fs::write` | file_write | File write |
| `std::fs::File::create` | file_write | File creation |
| `std::ptr::write` | memory_unsafe | Unsafe pointer write |
| `std::mem::transmute` | memory_unsafe | Type transmutation |
