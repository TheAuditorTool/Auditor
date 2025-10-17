## MODIFIED Requirements

### Requirement: Cross-File Taint Tracking
The taint analyzer SHALL track data flow across file boundaries when functions call each other across files.

**Symbol Lookup**:
1. When tracing a call to `callee_function`, query symbols table for callee's file location
2. Query MUST include all relevant symbol types: `type IN ('function', 'call', 'property')`
3. Query MUST match both exact name and qualified names: `name = ? OR name LIKE ?`
4. If symbol not found, skip call path and log debug message (NO silent fallback to same-file)

**Worklist State**:
1. Worklist entries include `(variable, function, file, depth, path)` with explicit file tracking
2. When adding callee to worklist, use callee's actual file (from symbols table)
3. If callee file cannot be determined, skip call (don't corrupt worklist with wrong file context)

**Cross-File Guards**:
1. When checking sinks, verify sink is in callee's file (not source file)
2. Continue worklist processing across file boundaries (no artificial same-file restriction)

#### Scenario: JavaScript method call resolution
- **GIVEN** symbols table with entry: `{name: 'query', type: 'call', path: 'models/user.js'}`
- **WHEN** taint analyzer traces call to `db.query`
- **THEN** normalize to `query`
- **AND** query: `SELECT path FROM symbols WHERE name = 'query' AND type IN ('function', 'call', 'property')`
- **AND** result: `models/user.js`
- **AND** add to worklist: `(tainted_var, 'query', 'models/user.js', depth+1, path)`

#### Scenario: Symbol not found hard failure
- **GIVEN** call to `unknownFunction` not in symbols table
- **WHEN** querying symbols: `SELECT path FROM symbols WHERE name = 'unknownFunction' AND type IN (...)`
- **THEN** result is NULL
- **AND** log debug: "[INTER-PROCEDURAL] Symbol not found: unknownFunction"
- **AND** skip this call path (continue worklist loop)
- **AND** do NOT default to current file

#### Scenario: Cross-file vulnerability detection
- **GIVEN** controller.js: `const data = req.body; service.validate(data);`
- **AND** service.js: `function validate(input) { db.query(\`INSERT INTO users VALUES ('\${input}')\`); }`
- **WHEN** taint analysis runs
- **THEN** source detected: `req.body` in controller.js
- **AND** call traced: `service.validate(data)` → service.js
- **AND** sink detected: `db.query(...)` in service.js
- **AND** cross-file path created: controller.js:1 → service.js:2
- **AND** path includes inter-procedural step: `{type: 'argument_pass', from: 'data', to: 'input', file: 'service.js'}`

#### Scenario: Symbol type filter includes all relevant types
- **GIVEN** symbols table with 24,375 symbols
- **AND** type distribution: call=92.4%, function=7.1%, class=0.8%, property=0.1%
- **WHEN** querying for callees
- **THEN** query includes: `type IN ('function', 'call', 'property')`
- **AND** does NOT filter to only type='function' (would miss 92.4% of symbols)
- **AND** symbol resolution succeeds for JavaScript methods, Python functions, property accesses

## REMOVED Requirements

### Requirement: Silent Fallback to Same-File
**REMOVED**: The taint analyzer NO LONGER defaults to current file when symbol lookup fails.

**Rationale**: Silent fallback violates CLAUDE.md "NO FALLBACK" principle. It corrupts worklist file context and hides indexer data quality issues.

**Previous Behavior** (REMOVED):
```python
callee_file = callee_location[0] if callee_location else current_file
```

**New Behavior**:
```python
if not callee_location:
    if debug:
        print(f"[INTER-PROCEDURAL] Symbol not found: {callee_func}")
    continue  # Skip call path, don't corrupt context
```

#### Scenario: Fallback removal exposes indexer gaps
- **GIVEN** call to `helper.processData` where `processData` not in symbols table
- **WHEN** taint analysis runs (old behavior with fallback)
- **THEN** callee_file defaulted to current_file (WRONG - corrupted context)
- **AND** worklist processed with wrong file, may find false sinks

- **WHEN** taint analysis runs (new behavior without fallback)
- **THEN** callee_file lookup fails
- **AND** debug logged: "Symbol not found: processData"
- **AND** call path skipped (correct - don't guess file)
- **AND** exposes indexer bug: `processData` should be in symbols table

## ADDED Requirements

### Requirement: Cross-File Debug Logging
The taint analyzer SHALL provide debug logging for cross-file tracking to aid in troubleshooting.

**Debug Output**:
1. When `THEAUDITOR_TAINT_DEBUG=1` environment variable set
2. Log cross-file transitions: "Following call across files: A.js → B.js"
3. Log symbol lookup failures: "Symbol not found: functionName (normalized: baseName)"
4. Log worklist state: "Added callee to worklist (depth N): functionName in file.js"
5. Log skip decisions: "Skipping call path: symbol not found"

#### Scenario: Debug logging for successful cross-file tracking
- **GIVEN** `THEAUDITOR_TAINT_DEBUG=1` environment variable
- **AND** call from controller.js to service.js
- **WHEN** taint analysis runs
- **THEN** debug output includes:
  ```
  [INTER-PROCEDURAL] Found 1 function calls passing tainted data
    -> data passed to userService.validate(data) at line 15
  [INTER-PROCEDURAL] Following call across files:
    controller.js → service.js
    Function: handleRequest → validate
  [INTER-PROCEDURAL] Added validate to worklist (depth 1)
  ```

#### Scenario: Debug logging for symbol lookup failure
- **GIVEN** `THEAUDITOR_TAINT_DEBUG=1` environment variable
- **AND** call to unknown function `unknownHelper`
- **WHEN** taint analysis runs
- **THEN** debug output includes:
  ```
  [INTER-PROCEDURAL] Symbol not found: unknownHelper (normalized: unknownHelper)
  [INTER-PROCEDURAL] Skipping call path: symbol lookup failed
  ```
