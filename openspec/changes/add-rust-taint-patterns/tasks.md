## 0. Verification (Pre-Implementation)

- [ ] 0.1 Read `rules/sql/sql_injection_analyze.py:45-50` - understand existing pattern with BOTH `find_*` and `register_taint_patterns()`
- [ ] 0.2 Read `theauditor/taint/core.py:18-180` - understand TaintRegistry API
- [ ] 0.3 Read `theauditor/rules/orchestrator.py:68-100` - understand `_discover_all_rules()` requires `find_*` functions
- [ ] 0.4 Read `theauditor/rules/orchestrator.py:471-495` - understand `collect_rule_patterns()` only iterates discovered modules
- [ ] 0.5 Query database to confirm Rust rows exist in assignments/function_call_args tables
- [ ] 0.6 Confirm TaintRegistry currently has 0 Rust patterns
- [ ] 0.7 **CRITICAL**: Verify Rust function call format in database and document findings:
      ```sql
      SELECT DISTINCT callee_function FROM function_call_args WHERE file LIKE '%.rs' ORDER BY callee_function LIMIT 50;
      ```
      **Required output**: Document actual format in verification.md (e.g., "Command" vs "std::process::Command")
      **Action**: Update pattern tables in proposal.md if patterns don't match database format

## 1. Create Pattern File

**Note:** `theauditor/rules/rust/` directory already exists with 5 rules:
`ffi_boundary.py`, `integer_safety.py`, `memory_safety.py`, `panic_paths.py`, `unsafe_analysis.py`

- [ ] 1.1 Create `theauditor/rules/rust/rust_injection_analyze.py`
- [ ] 1.2 Add module docstring explaining purpose
- [ ] 1.3 Import StandardRuleContext, StandardFinding, logger
- [ ] 1.4 **CRITICAL**: Add `find_rust_injection_issues()` stub for orchestrator discovery

**File Structure:**
```python
"""Rust taint source and sink pattern registration.

Registers Rust-specific patterns for:
- Sources: stdin, env, web framework inputs (actix, axum, rocket, warp)
- Sinks: Command execution, SQL, file writes, unsafe operations

IMPORTANT: The find_rust_injection_issues() function is required for orchestrator
discovery. See sql_injection_analyze.py:48 - "Named find_* for orchestrator
discovery - enables register_taint_patterns loading."

Auto-discovered by orchestrator._discover_all_rules() at orchestrator.py:68-100.
Pattern registration via collect_rule_patterns() at orchestrator.py:471-495.
"""

from theauditor.rules.base import StandardFinding, StandardRuleContext
from theauditor.utils.logging import logger


def find_rust_injection_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Stub for orchestrator discovery.

    Named find_* for orchestrator discovery - enables register_taint_patterns loading.
    Actual taint analysis happens via TaintRegistry, not this rule.

    The orchestrator at orchestrator.py:93 only discovers modules with find_* functions.
    Without this function, register_taint_patterns() would never be called.
    """
    return []  # Pattern-only module - taint analysis uses TaintRegistry


def register_taint_patterns(taint_registry):
    """Register Rust source and sink patterns.

    Called by orchestrator.collect_rule_patterns() after module is discovered
    via find_rust_injection_issues().
    """
    # ... implementation
```

## 2. Define Source Patterns

**Use categories from `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`**

- [ ] 2.1 Add stdin sources (category: `user_input`): `std::io::stdin`, `BufReader::new(stdin())`
- [ ] 2.2 Add env sources (category: `user_input`): `std::env::args`, `std::env::var`, `std::env::vars`
- [ ] 2.3 Add file read sources (category: `user_input`): `std::fs::read`, `std::fs::read_to_string`
- [ ] 2.4 Add Actix-web sources (category: `http_request`): `web::Json`, `web::Path`, `web::Query`, `web::Form`
- [ ] 2.5 Add Axum sources (category: `http_request`): `axum::extract::Json`, `axum::extract::Path`, `axum::extract::Query`
- [ ] 2.6 Add Rocket sources (category: `http_request`): `rocket::request`, `rocket::form`
- [ ] 2.7 Add Warp sources (category: `http_request`): `warp::body::json`, `warp::path::param`
- [ ] 2.8 Add logging: `logger.debug(f"Registered {count} Rust source patterns")`

## 3. Define Sink Patterns

**Use categories from `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`**

- [ ] 3.1 Add command sinks (category: `command`): `std::process::Command`, `Command::new`, `Command::arg`
- [ ] 3.2 Add SQL sinks (category: `sql`): `sqlx::query`, `sqlx::query_as`, `diesel::sql_query`
- [ ] 3.3 Add file write sinks (category: `path`): `std::fs::write`, `std::fs::File::create`, `File::write_all`
- [ ] 3.4 Add unsafe memory sinks (category: `code_injection`): `std::ptr::write`, `std::mem::transmute`
- [ ] 3.5 Add network sinks (category: `ssrf`): `TcpStream::connect`
- [ ] 3.6 Add logging: `logger.debug(f"Registered {count} Rust sink patterns")`

## 4. Verify Auto-Discovery

**Discovery requires BOTH functions:**
1. `find_rust_injection_issues()` - for orchestrator to discover the module
2. `register_taint_patterns()` - called by orchestrator after discovery

- [ ] 4.1 Verify module is importable: `python -c "from theauditor.rules.rust import rust_injection_analyze"`
- [ ] 4.2 Verify BOTH functions exist:
      ```python
      from theauditor.rules.rust import rust_injection_analyze
      assert hasattr(rust_injection_analyze, 'find_rust_injection_issues'), "Missing find_* function!"
      assert hasattr(rust_injection_analyze, 'register_taint_patterns'), "Missing register function!"
      ```
- [ ] 4.3 Run `aud full --offline` and check logs for Rust pattern registration
- [ ] 4.4 Verify patterns appear in registry after initialization:
      ```python
      from pathlib import Path
      from theauditor.rules.orchestrator import RulesOrchestrator
      from theauditor.taint.core import TaintRegistry
      registry = TaintRegistry()
      orch = RulesOrchestrator(Path("."))
      orch.collect_rule_patterns(registry)
      print(f"Rust sources: {len(registry.get_source_patterns('rust'))}")
      print(f"Rust sinks: {len(registry.get_sink_patterns('rust'))}")
      assert len(registry.get_source_patterns('rust')) > 0, "No Rust sources registered!"
      assert len(registry.get_sink_patterns('rust')) > 0, "No Rust sinks registered!"
      ```

## 5. Testing

- [ ] 5.1 Create test Rust file with known vulnerable patterns
- [ ] 5.2 Run `aud full --offline` on TheAuditor (has Rust code)
- [ ] 5.3 Run taint analysis, verify Rust flows detected
- [ ] 5.4 Verify no false positives from overly broad patterns

## 6. Documentation

- [ ] 6.1 Add docstrings to all pattern functions
- [ ] 6.2 Document pattern categories in module docstring
- [ ] 6.3 Add comments explaining why each pattern is a source/sink
