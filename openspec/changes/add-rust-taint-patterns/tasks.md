## 0. Verification (Pre-Implementation)

- [ ] 0.1 Read `rules/go/injection_analyze.py` - understand existing pattern registration structure
- [ ] 0.2 Read `theauditor/taint/core.py` - understand TaintRegistry API
- [ ] 0.3 Read `theauditor/taint/discovery.py` - understand how patterns are discovered
- [ ] 0.4 Query database to confirm Rust rows exist in assignments/function_call_args tables
- [ ] 0.5 Confirm TaintRegistry currently has 0 Rust patterns

## 1. Create Pattern File

- [ ] 1.1 Create `theauditor/rules/rust/__init__.py` (if not exists)
- [ ] 1.2 Create `theauditor/rules/rust/rust_injection_analyze.py`
- [ ] 1.3 Add module docstring explaining purpose
- [ ] 1.4 Import TaintRegistry and logger

**File Structure:**
```python
"""Rust taint source and sink pattern registration.

Registers Rust-specific patterns for:
- Sources: stdin, env, web framework inputs (actix, axum, rocket)
- Sinks: Command execution, SQL, file writes, unsafe operations
"""

from theauditor.taint.core import TaintRegistry
from theauditor.utils.logging import logger


def register_rust_patterns(registry: TaintRegistry) -> None:
    """Register Rust source and sink patterns."""
    # ... implementation
```

## 2. Define Source Patterns

- [ ] 2.1 Add stdin sources: `std::io::stdin`, `BufReader::new(stdin())`
- [ ] 2.2 Add env sources: `std::env::args`, `std::env::var`, `std::env::vars`
- [ ] 2.3 Add file read sources: `std::fs::read`, `std::fs::read_to_string`
- [ ] 2.4 Add Actix-web sources: `web::Json`, `web::Path`, `web::Query`, `web::Form`
- [ ] 2.5 Add Axum sources: `axum::extract::Json`, `axum::extract::Path`, `axum::extract::Query`
- [ ] 2.6 Add Rocket sources: `rocket::request`, `rocket::form`
- [ ] 2.7 Add Warp sources: `warp::body::json`, `warp::path::param`
- [ ] 2.8 Add logging: `logger.debug(f"Registered {count} Rust source patterns")`

## 3. Define Sink Patterns

- [ ] 3.1 Add command injection sinks: `std::process::Command`, `Command::new`, `Command::arg`
- [ ] 3.2 Add SQL injection sinks: `sqlx::query`, `sqlx::query_as`, `diesel::sql_query`
- [ ] 3.3 Add file write sinks: `std::fs::write`, `std::fs::File::create`, `File::write_all`
- [ ] 3.4 Add unsafe memory sinks: `std::ptr::write`, `std::mem::transmute`
- [ ] 3.5 Add eval-like sinks: `include_str!` (compile-time but can be misused)
- [ ] 3.6 Add network sinks: `TcpStream::connect` (SSRF potential)
- [ ] 3.7 Add logging: `logger.debug(f"Registered {count} Rust sink patterns")`

## 4. Wire into Pipeline

- [ ] 4.1 Find where Go patterns are registered (likely in taint initialization)
- [ ] 4.2 Add import for `rust_injection_analyze`
- [ ] 4.3 Call `register_rust_patterns(registry)` alongside Go registration
- [ ] 4.4 Verify patterns appear in registry after initialization

## 5. Testing

- [ ] 5.1 Create test Rust file with known vulnerable patterns
- [ ] 5.2 Run `aud full --offline` on TheAuditor (has Rust code)
- [ ] 5.3 Run taint analysis, verify Rust flows detected
- [ ] 5.4 Verify no false positives from overly broad patterns

## 6. Documentation

- [ ] 6.1 Add docstrings to all pattern functions
- [ ] 6.2 Document pattern categories in module docstring
- [ ] 6.3 Add comments explaining why each pattern is a source/sink
