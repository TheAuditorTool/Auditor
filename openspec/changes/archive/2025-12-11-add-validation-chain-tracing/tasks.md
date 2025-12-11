# Tasks: Validation Chain Tracing

## 0. Verification (Pre-Implementation)

- [x] 0.1 Verify `aud boundaries` current behavior with `--help`
- [x] 0.2 Verify `aud explain` current flags in `explain.py`
- [x] 0.3 Verify `aud blueprint` current flags in `blueprint.py`
- [x] 0.4 Verify existing boundary_analyzer.py structure
- [x] 0.5 Verify database tables needed: `symbols`, `function_call_args`, `refs`, `type_annotations`
- [x] 0.6 Verify type information is captured in indexing (for `any` detection):
  - `type_annotations` table has `is_any`, `is_unknown`, `is_generic` boolean flags
  - **DECISION**: `is_any` flag is unreliable (only 3 records). Use regex ONLY (no fallback per CLAUDE.md Section 4)
  - **REQUIRED**: Define exact regex patterns with word boundaries to avoid false positives:
    - `r':\s*any\b'` matches `: any` but NOT "Company"
    - `r'\bas\s+any\b'` matches `as any` but NOT "alias any"
    - Exclusion list: `z.any()`, `Joi.any()` are validation SOURCES, not breaks
- [x] 0.7 **CRITICAL**: Study framework registry pattern in commit `c539722`:
  - `theauditor/boundaries/boundary_analyzer.py:28-54` - `_detect_frameworks()`: queries `frameworks` table, returns dict grouped by framework name
  - `theauditor/boundaries/boundary_analyzer.py:57-182` - `_analyze_express_boundaries()`: Express-specific logic using `express_middleware_chains` table
  - `theauditor/boundaries/boundary_analyzer.py:185-418` - `analyze_input_validation_boundaries()`: main router that calls `_detect_frameworks()` then dispatches to framework-specific analyzer
  - Copy this routing pattern for chain tracing (DO NOT write generic if/else chains)
- [x] 0.8 **ZERO FALLBACK WARNING**: The existing boundary_analyzer.py uses `_table_exists()` checks (10 instances) which VIOLATE Zero Fallback policy. DO NOT copy this pattern. New code must:
  - Assume tables exist
  - Let queries fail loudly if tables missing
  - NO `if _table_exists()` guards
- [x] 0.9 **TABLE NOTE**: `js_routes` table does NOT exist. Use `express_middleware_chains` for JS/TS entry points.

## 1. Core: Validation Chain Tracer

### 1.1 Data Model
- [x] 1.1.1 Create `theauditor/boundaries/chain_tracer.py`
- [x] 1.1.2 Define `ChainHop` dataclass:
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
- [x] 1.1.3 Define `ValidationChain` dataclass:
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

### 1.2 Chain Detection Logic (Framework Registry Pattern)

**ARCHITECTURE**: Split into Dispatcher + Language-Specific Strategies (per Lead Auditor feedback)

- [x] 1.2.1 Implement **Framework Dispatcher** `trace_validation_chain(entry_file, entry_line, db_path)`:
  ```python
  def trace_validation_chain(entry_file: str, entry_line: int, db_path: str) -> ValidationChain:
      """Route to framework-specific chain tracer. NO generic if/else chains."""
      frameworks = _detect_frameworks(cursor)  # Reuse from boundary_analyzer.py

      if "express" in frameworks:
          return _trace_express_chain(cursor, entry_file, entry_line)
      elif "fastapi" in frameworks:
          return _trace_fastapi_chain(cursor, entry_file, entry_line)
      elif "flask" in frameworks:
          return _trace_flask_chain(cursor, entry_file, entry_line)
      else:
          return _trace_generic_chain(cursor, entry_file, entry_line)  # Go/Rust/unknown
  ```

- [x] 1.2.2 Implement **TypeScript/Express Strategy** `_trace_express_chain()`:
  - Query `express_middleware_chains` for entry points
  - Query `type_annotations` for type info (TS-specific)
  - Use regex patterns from Decision 2 for `any` detection
  - Handle `z.any()` exclusion (validation source, not break)

- [x] 1.2.3 Implement **Python/FastAPI Strategy** `_trace_fastapi_chain()`:
  - Query `python_routes` for entry points
  - Query `type_annotations` for type info
  - Handle Pydantic model detection
  - Handle `# type: ignore` comments

- [x] 1.2.4 Implement **Generic Strategy** `_trace_generic_chain()`:
  - Query `function_call_args` with recursive CTE
  - Query `symbols` for type info (Go/Rust)
  - BFS traversal for unknown frameworks

- [x] 1.2.5 Implement `is_type_unsafe(type_annotation: str)` - **REGEX ONLY, NO FALLBACKS**:
  ```python
  import re

  # Word boundaries prevent "Company", "Germany" false positives
  ANY_TYPE_PATTERNS = [
      re.compile(r':\s*any\b'),           # `: any`
      re.compile(r'\bas\s+any\b'),        # `as any`
      re.compile(r'<\s*any\s*>'),         # `<any>`
      re.compile(r'<\s*any\s*,'),         # `<any, T>`
      re.compile(r',\s*any\s*>'),         # `<T, any>`
      re.compile(r'\|\s*any\b'),          # `| any`
      re.compile(r'\bany\s*\|'),          # `any |`
      re.compile(r'=>\s*any\b'),          # `=> any`
  ]

  VALIDATION_EXCLUSIONS = ['z.any()', 'Joi.any()', 'yup.mixed()']

  def is_type_unsafe(type_annotation: str) -> bool:
      """Single code path. No fallbacks. Per CLAUDE.md Section 4."""
      if not type_annotation:
          return False
      for excl in VALIDATION_EXCLUSIONS:
          if excl in type_annotation:
              return False
      return any(p.search(type_annotation) for p in ANY_TYPE_PATTERNS)
  ```

### 1.3 Validation Source Detection
- [x] 1.3.1 Extend existing VALIDATION_PATTERNS with type-aware patterns:
  - Zod: `z.object()`, `.parse()`, `.safeParse()` - returns typed result
  - Joi: `Joi.object()`, `.validate()` - returns typed result
  - Yup: `yup.object()`, `.validate()` - returns typed result
  - TypeScript: Generic type parameters `<T>` in handler signatures
- [x] 1.3.2 Map validation library to expected output type

## 2. Core: Security Boundary Audit

### 2.1 Audit Categories
- [x] 2.1.1 Create `theauditor/boundaries/security_audit.py`
- [x] 2.1.2 Define audit categories:
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
- [x] 2.2.1 Implement `run_security_audit(db_path)`:
  - For each category, find relevant code locations
  - Check if protective pattern exists
  - Return PASS/FAIL with file:line evidence
- [x] 2.2.2 Implement `check_output_sanitization(file, line, db_path)`:
  - Detect HTML/JS output points (response.send, res.json, innerHTML)
  - Check if sanitization occurs before output
- [x] 2.2.3 Implement `check_database_safety(file, line, db_path)`:
  - Detect raw SQL construction (string concat with variables)
  - Check if parameterized queries used
- [x] 2.2.4 Implement `check_file_safety(file, line, db_path)`:
  - Detect file operations with user input
  - Check if path validation occurs

## 3. CLI Integration: Boundaries Command

### 3.1 Add Flags
- [x] 3.1.1 Add `--validated` flag to `boundaries.py`:
  ```python
  @click.option("--validated", is_flag=True, help="Trace validation chains through data flow")
  ```
- [x] 3.1.2 Add `--audit` flag to `boundaries.py`:
  ```python
  @click.option("--audit", is_flag=True, help="Run security boundary audit (input/output/DB/file)")
  ```
- [x] 3.1.3 Update function signature to accept new flags

### 3.2 Output Formatting
- [x] 3.2.1 Implement `format_validation_chain(chain: ValidationChain)`:
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
- [x] 3.2.2 Implement `format_security_audit(results)`:
  ```
  INPUT BOUNDARIES:
    POST /users      [PASS] Zod schema validates body
    GET /users/:id   [FAIL] No param validation

  OUTPUT BOUNDARIES:
    renderUser()     [PASS] HTML escaped via React
    emailTemplate()  [FAIL] Raw HTML interpolation (XSS risk)
  ```

## 4. CLI Integration: Explain Command

- [x] 4.1 Add `--validated` flag to `explain.py`
- [x] 4.2 When `--validated` is set:
  - Find entry points in the target file
  - Run `trace_validation_chain` for each
  - Append validation chain section to explain output
- [x] 4.3 Output format:
  ```
  VALIDATION CHAINS:
    POST /api/users -> userService.create -> repo.insert
    Status: BROKEN at hop 3 (cast to any)
  ```

## 5. CLI Integration: Blueprint Command

- [x] 5.1 Add `--validated` flag to `blueprint.py`
- [x] 5.2 When `--validated` is set:
  - Run validation chain analysis on all entry points
  - Summarize: X chains intact, Y chains broken, Z no validation
- [x] 5.3 Output format:
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

- [x] 6.1 Create query to get call chain from entry point:
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
- [x] 6.2 Create query to get type annotation for parameter (language-specific):
  - **TypeScript/JavaScript**: Query `type_annotations` table (has `is_any`, `is_unknown` flags)
  - **Python**: Query `type_annotations` table
  - **Go/Rust**: Query `symbols` table (fallback)
  - See task 1.2.3 for detailed query patterns
- [x] 6.3 Verify queries work with existing schema (NO schema changes)
- [x] 6.4 **CRITICAL**: Verify path storage consistency between tables:
  - Check if `function_call_args.callee_file_path` uses same format as `symbols.path`
  - Potential mismatch: relative (`./utils/helper.ts`) vs absolute (`/src/utils/helper.ts`)
  - **If inconsistent**: Document as known limitation. Do NOT implement fuzzy matching fallback (Zero Fallback policy)
  - **Verification query**:
    ```sql
    -- Find mismatches: calls where callee exists but JOIN fails
    SELECT DISTINCT fca.callee_file_path, s.path
    FROM function_call_args fca
    LEFT JOIN symbols s ON fca.callee_file_path = s.path
    WHERE fca.callee_file_path IS NOT NULL
      AND s.path IS NULL
    LIMIT 10
    ```

## 7. Testing

- [x] 7.1 Create test fixture with intact validation chain
- [x] 7.2 Create test fixture with broken validation chain (`any` cast)
- [x] 7.3 Create test fixture with no validation
- [x] 7.4 Test chain tracer on all three fixtures
- [x] 7.5 Test security audit on mixed codebase
- [x] 7.6 Test CLI output formatting (no emojis)

## 8. Documentation

- [x] 8.1 Update `aud boundaries --help` with new flags
- [x] 8.2 Update `aud explain --help` with `--validated` flag
- [x] 8.3 Update `aud blueprint --help` with `--validated` flag
- [x] 8.4 Add examples to help text showing chain visualization

## 9. Integration Verification

- [x] 9.1 Test on deepflow-typescript codebase (TypeScript/Express)
- [x] 9.2 Verify no regressions in existing `aud boundaries` behavior
- [x] 9.3 Verify `--validated` and `--audit` can be combined with existing flags
- [x] 9.4 Performance check: ensure chain tracing doesn't add >5s to runtime
