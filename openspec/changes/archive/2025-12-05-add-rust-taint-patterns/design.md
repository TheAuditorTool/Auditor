## Context

Rust extractor now populates language-agnostic tables (`assignments`, `function_call_args`, `returns`) but taint analysis cannot identify Rust vulnerabilities because TaintRegistry has zero Rust patterns registered.

**Constraints:**
- Must follow orchestrator discovery protocol (requires `find_*` function)
- Patterns must match EXACT format stored in `function_call_args.callee_function` column
- Must use existing category taxonomy from `TaintRegistry.CATEGORY_TO_VULN_TYPE`

**Stakeholders:**
- Taint analysis consumers expecting Rust vulnerability detection
- Existing rule infrastructure (orchestrator auto-discovery)

## Goals / Non-Goals

**Goals:**
- Register Rust-specific source patterns (stdin, env, web frameworks)
- Register Rust-specific sink patterns (Command, SQL, file writes, unsafe ops)
- Enable taint flow detection for Rust code via existing IFDS/FlowResolver engines

**Non-Goals:**
- Modifying Rust extractor behavior
- Changing graph strategies (RustTraitStrategy, RustAsyncStrategy already exist)
- Adding new vulnerability categories
- Modifying orchestrator discovery logic

## Decisions

### Decision 1: Follow sql_injection_analyze.py Pattern

**What:** Create module with BOTH `find_*` stub AND `register_taint_patterns()` function.

**Why:** Orchestrator discovery at `orchestrator.py:93` only finds modules with `find_*` functions. Without the stub, `collect_rule_patterns()` at line 471-495 would never call `register_taint_patterns()`.

**Evidence:**
```python
# orchestrator.py:93
if name.startswith("find_") and obj.__module__ == module_name:
    rule_info = self._analyze_rule(...)
```

**Alternatives Considered:**
1. *Modify orchestrator to scan for `register_taint_patterns` directly* - Rejected: invasive change, breaks existing pattern
2. *Add patterns directly to TaintRegistry.__init__* - Rejected: hardcoding, not discoverable
3. *Create separate pattern-only module type* - Rejected: over-engineering for single use case

### Decision 2: Exact String Matching Against Database

**What:** Patterns must match the EXACT format stored in `function_call_args.callee_function`.

**Why:** TaintRegistry uses exact string matching, not fuzzy/regex matching. If database stores `Command::new` but pattern says `std::process::Command::new`, no match occurs.

**Verification Query (MUST RUN BEFORE IMPLEMENTATION):**
```sql
SELECT DISTINCT callee_function FROM function_call_args
WHERE file LIKE '%.rs'
ORDER BY callee_function LIMIT 50;
```

**Action Required:** Document actual format in `verification.md`, update pattern tables if they don't match.

### Decision 3: Use Existing Category Taxonomy

**What:** Map patterns to categories from `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`.

**Why:** Categories determine vulnerability type strings in reports. Using non-existent categories produces "Data Exposure" fallback.

**Valid Categories:**
| Category | Vulnerability Type |
|----------|-------------------|
| `user_input` | Unvalidated Input |
| `http_request` | Unvalidated Input |
| `command` | Command Injection |
| `sql` | SQL Injection |
| `path` | Path Traversal |
| `code_injection` | Code Injection |
| `ssrf` | Server-Side Request Forgery (SSRF) |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Patterns don't match database format | Task 0.7: Verify format BEFORE implementation |
| Over-broad patterns cause false positives | Start with qualified names, expand if needed |
| Missing web framework patterns | Cover major frameworks (Actix, Axum, Rocket, Warp); add others later |
| Stub function confuses future maintainers | Document purpose in docstring and module docstring |

## Migration Plan

**Steps:**
1. Execute verification query (task 0.7)
2. Update pattern tables in proposal.md if format differs
3. Create `rust_injection_analyze.py`
4. Run `aud full --offline` to verify discovery
5. Run taint analysis on Rust code to verify detection

**Rollback:**
- Delete `theauditor/rules/rust/rust_injection_analyze.py`
- No schema changes, no data migration needed

## Open Questions

1. **Resolved:** Should patterns include crate prefixes (e.g., `tokio::fs::read`)?
   - Answer: Verify database format first (task 0.7), match whatever extractor stores

2. **Resolved:** How to handle trait method calls (e.g., `Read::read`)?
   - Answer: Extractor stores method name; add both `read` and `Read::read` if both appear in database
