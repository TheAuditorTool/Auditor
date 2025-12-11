# Tasks: Validation Chain Tracing

## 0. Verification (Pre-Implementation)

- [ ] 0.1 Verify `aud boundaries` current behavior with `--help`
- [ ] 0.2 Verify `aud explain` current flags in `explain.py`
- [ ] 0.3 Verify `aud blueprint` current flags in `blueprint.py`
- [ ] 0.4 Verify existing boundary_analyzer.py structure
- [ ] 0.5 Verify database tables needed: `symbols`, `function_call_args`, `refs`
- [ ] 0.6 Verify type information is captured in indexing (for `any` detection)
- [ ] 0.7 **CRITICAL**: Study framework registry pattern in commit `c539722`:
  - `theauditor/boundaries/boundary_analyzer.py:28-54` - `_detect_frameworks()`: queries `frameworks` table, returns dict grouped by framework name
  - `theauditor/boundaries/boundary_analyzer.py:57-182` - `_analyze_express_boundaries()`: Express-specific logic using `express_middleware_chains` table
  - `theauditor/boundaries/boundary_analyzer.py:185-418` - `analyze_input_validation_boundaries()`: main router that calls `_detect_frameworks()` then dispatches to framework-specific analyzer
  - Copy this routing pattern for chain tracing (DO NOT write generic if/else chains)
- [ ] 0.8 **ZERO FALLBACK WARNING**: The existing boundary_analyzer.py uses `_table_exists()` checks (10 instances) which VIOLATE Zero Fallback policy. DO NOT copy this pattern. New code must:
  - Assume tables exist
  - Let queries fail loudly if tables missing
  - NO `if _table_exists()` guards
- [ ] 0.9 **TABLE NOTE**: `js_routes` table does NOT exist. Use `express_middleware_chains` for JS/TS entry points.

## 1. Core: Validation Chain Tracer

### 1.1 Data Model
- [ ] 1.1.1 Create `theauditor/boundaries/chain_tracer.py`
- [ ] 1.1.2 Define `ChainHop` dataclass:
  ```python
  @dataclass
  class ChainHop:
      function: str      # Function name at this hop
      file: str          # File path
      line: int          # Line number
      type_info: str     # Type at this hop (e.g., "CreateUserInput", "any", "unknown")
      validation_status: str  # "validated", "preserved", "broken", "unknown"
      break_reason: str | None  # Why chain broke (e.g., "cast to any")
  ```
- [ ] 1.1.3 Define `ValidationChain` dataclass:
  ```python
  @dataclass
  class ValidationChain:
      entry_point: str   # Route/endpoint
      entry_file: str
      entry_line: int
      hops: list[ChainHop]
      chain_status: str  # "intact", "broken", "no_validation"
      break_index: int | None  # Index where chain broke
  ```

### 1.2 Chain Detection Logic
- [ ] 1.2.1 Implement `trace_validation_chain(entry_file, entry_line, db_path)`:
  - Query `function_call_args` to get call chain from entry point
  - For each hop, check if type annotation exists
  - Detect type degradation: `T` -> `any` | `unknown` | no annotation
- [ ] 1.2.2 Implement `detect_chain_break(hop_types: list[str])`:
  - Returns index where type safety is lost
  - Patterns: explicit `any`, type assertion `as any`, missing annotation after validated type
- [ ] 1.2.3 Implement `get_type_at_hop(file, line, param_name, db_path)`:
  - Query symbols table for type annotations
  - Handle TypeScript/Python/Go differently

### 1.3 Validation Source Detection
- [ ] 1.3.1 Extend existing VALIDATION_PATTERNS with type-aware patterns:
  - Zod: `z.object()`, `.parse()`, `.safeParse()` - returns typed result
  - Joi: `Joi.object()`, `.validate()` - returns typed result
  - Yup: `yup.object()`, `.validate()` - returns typed result
  - TypeScript: Generic type parameters `<T>` in handler signatures
- [ ] 1.3.2 Map validation library to expected output type

## 2. Core: Security Boundary Audit

### 2.1 Audit Categories
- [ ] 2.1.1 Create `theauditor/boundaries/security_audit.py`
- [ ] 2.1.2 Define audit categories:
  ```python
  AUDIT_CATEGORIES = {
      "input": {
          "name": "INPUT BOUNDARIES",
          "patterns": ["zod", "joi", "yup", "validate", "sanitize"],
          "severity": "CRITICAL"
      },
      "output": {
          "name": "OUTPUT BOUNDARIES",
          "patterns": ["escape", "sanitize", "encode", "DOMPurify"],
          "check": "xss_prevention"
      },
      "database": {
          "name": "DATABASE BOUNDARIES",
          "patterns": ["parameterized", "prepared", "$1", "?"],
          "check": "sqli_prevention"
      },
      "file": {
          "name": "FILE BOUNDARIES",
          "patterns": ["path.resolve", "path.normalize", "realpath"],
          "check": "path_traversal"
      }
  }
  ```

### 2.2 Audit Logic
- [ ] 2.2.1 Implement `run_security_audit(db_path)`:
  - For each category, find relevant code locations
  - Check if protective pattern exists
  - Return PASS/FAIL with file:line evidence
- [ ] 2.2.2 Implement `check_output_sanitization(file, line, db_path)`:
  - Detect HTML/JS output points (response.send, res.json, innerHTML)
  - Check if sanitization occurs before output
- [ ] 2.2.3 Implement `check_database_safety(file, line, db_path)`:
  - Detect raw SQL construction (string concat with variables)
  - Check if parameterized queries used
- [ ] 2.2.4 Implement `check_file_safety(file, line, db_path)`:
  - Detect file operations with user input
  - Check if path validation occurs

## 3. CLI Integration: Boundaries Command

### 3.1 Add Flags
- [ ] 3.1.1 Add `--validated` flag to `boundaries.py`:
  ```python
  @click.option("--validated", is_flag=True, help="Trace validation chains through data flow")
  ```
- [ ] 3.1.2 Add `--audit` flag to `boundaries.py`:
  ```python
  @click.option("--audit", is_flag=True, help="Run security boundary audit (input/output/DB/file)")
  ```
- [ ] 3.1.3 Update function signature to accept new flags

### 3.2 Output Formatting
- [ ] 3.2.1 Implement `format_validation_chain(chain: ValidationChain)`:
  - Visual chain with arrows and status markers
  - Use Rich for colors: green=PASS, red=FAIL, yellow=WARNING
  - ASCII-safe output (no emojis per CLAUDE.md rules)
  ```
  POST /users (body: CreateUserInput)
      | [PASS] Zod validated at entry
      v
  userService.create(data: CreateUserInput)
      | [PASS] Type preserved
      v
  repo.insert(data: any)        <- CHAIN BROKEN
      | [FAIL] Cast to any - validation meaningless now
  ```
- [ ] 3.2.2 Implement `format_security_audit(results)`:
  ```
  INPUT BOUNDARIES:
    POST /users      [PASS] Zod schema validates body
    GET /users/:id   [FAIL] No param validation

  OUTPUT BOUNDARIES:
    renderUser()     [PASS] HTML escaped via React
    emailTemplate()  [FAIL] Raw HTML interpolation (XSS risk)
  ```

## 4. CLI Integration: Explain Command

- [ ] 4.1 Add `--validated` flag to `explain.py`
- [ ] 4.2 When `--validated` is set:
  - Find entry points in the target file
  - Run `trace_validation_chain` for each
  - Append validation chain section to explain output
- [ ] 4.3 Output format:
  ```
  VALIDATION CHAINS:
    POST /api/users -> userService.create -> repo.insert
    Status: BROKEN at hop 3 (cast to any)
  ```

## 5. CLI Integration: Blueprint Command

- [ ] 5.1 Add `--validated` flag to `blueprint.py`
- [ ] 5.2 When `--validated` is set:
  - Run validation chain analysis on all entry points
  - Summarize: X chains intact, Y chains broken, Z no validation
- [ ] 5.3 Output format:
  ```
  VALIDATION CHAIN HEALTH:
    Entry Points: 47
    Chains Intact: 31 (66%)
    Chains Broken: 12 (26%)
    No Validation: 4 (8%)

    Top Break Reasons:
      - Cast to any: 8
      - Untyped intermediate: 3
      - Type assertion: 1
  ```

## 6. Database Queries

- [ ] 6.1 Create query to get call chain from entry point:
  ```sql
  -- NOTE: function_call_args schema:
  --   file, line, caller_function, callee_function, argument_index,
  --   argument_expr, param_name, callee_file_path
  -- callee_line must be joined from symbols table
  SELECT fca.callee_file_path, fca.callee_function, s.line as callee_line
  FROM function_call_args fca
  LEFT JOIN symbols s ON fca.callee_file_path = s.path
      AND fca.callee_function = s.name
      AND s.type IN ('function', 'method')
  WHERE fca.file = ? AND fca.caller_function = ?
  ORDER BY fca.line
  ```
- [ ] 6.2 Create query to get type annotation for parameter:
  ```sql
  SELECT type_annotation
  FROM symbols
  WHERE path = ? AND line = ? AND name = ?
  ```
- [ ] 6.3 Verify queries work with existing schema (NO schema changes)

## 7. Testing

- [ ] 7.1 Create test fixture with intact validation chain
- [ ] 7.2 Create test fixture with broken validation chain (`any` cast)
- [ ] 7.3 Create test fixture with no validation
- [ ] 7.4 Test chain tracer on all three fixtures
- [ ] 7.5 Test security audit on mixed codebase
- [ ] 7.6 Test CLI output formatting (no emojis)

## 8. Documentation

- [ ] 8.1 Update `aud boundaries --help` with new flags
- [ ] 8.2 Update `aud explain --help` with `--validated` flag
- [ ] 8.3 Update `aud blueprint --help` with `--validated` flag
- [ ] 8.4 Add examples to help text showing chain visualization

## 9. Integration Verification

- [ ] 9.1 Test on PlantFlow codebase (TypeScript/Express)
- [ ] 9.2 Verify no regressions in existing `aud boundaries` behavior
- [ ] 9.3 Verify `--validated` and `--audit` can be combined with existing flags
- [ ] 9.4 Performance check: ensure chain tracing doesn't add >5s to runtime
