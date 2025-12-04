# Capability: Rules Fidelity Migration

Migration of all 95 rule files to use Q class and fidelity infrastructure.

## ADDED Requirements

### Requirement: All Rules Use Q Class

Every rule file SHALL use the Q class for database queries.

The rule MUST:
1. Import `Q` from `theauditor.rules.query`
2. Use `Q("table").select(...).where(...).build()` instead of raw SQL
3. Only use `Q.raw()` for truly complex queries that Q cannot express
4. Log a warning when Q.raw() is used

#### Scenario: Standard query conversion

- **WHEN** a rule has `cursor.execute("SELECT col FROM table WHERE x = 'y'")`
- **THEN** it MUST be converted to `db.query(Q("table").select("col").where("x = ?", "y"))`

#### Scenario: CTE query conversion

- **WHEN** a rule has `WITH cte AS (SELECT ...) SELECT ... FROM cte`
- **THEN** it MUST be converted to `Q("main").with_cte("cte", subquery).select(...)`

---

### Requirement: All Rules Return RuleResult

Every rule function SHALL return `RuleResult` instead of bare `list[StandardFinding]`.

The rule MUST:
1. Import `RuleResult` and `RuleDB` from `theauditor.rules.fidelity`
2. Use `RuleDB` context manager for database access
3. Return `RuleResult(findings=findings, manifest=db.get_manifest())`

#### Scenario: Rule with RuleResult return

- **WHEN** rule completes analysis with 5 findings
- **THEN** returns `RuleResult(findings=[...5 findings...], manifest={"items_scanned": N, ...})`

#### Scenario: Rule with no findings

- **WHEN** rule finds no issues
- **THEN** returns `RuleResult(findings=[], manifest=db.get_manifest())` (NOT bare empty list)

---

### Requirement: All Rules Have METADATA

Every rule file SHALL have a `METADATA` constant of type `RuleMetadata`.

The METADATA MUST include:
- `name`: Unique rule identifier
- `category`: Category for grouping
- `target_extensions`: List of file extensions to analyze
- `exclude_patterns`: List of patterns to skip
- `requires_jsx_pass`: Boolean for JSX requirements
- `execution_scope`: Either "database" or "file"

#### Scenario: Missing METADATA

- **WHEN** a rule file lacks METADATA
- **THEN** migration MUST add complete METADATA constant

---

### Requirement: Zero Raw cursor.execute()

No rule file SHALL contain raw `cursor.execute()` calls with hardcoded SQL.

Allowed patterns:
1. `db.query(Q(...))` - Preferred
2. `db.execute(sql, params)` with `sql, params = Q.raw(...)` - Escape hatch with logging

Forbidden patterns:
1. `cursor.execute("SELECT ...")` - Raw hardcoded SQL
2. `cursor.execute(f"SELECT {var}...")` - Interpolated SQL
3. `cursor.execute(query)` where query is string variable with hardcoded SQL

#### Scenario: Raw SQL detected

- **WHEN** grep finds `cursor.execute("SELECT` in a rule file
- **THEN** migration is incomplete - must convert to Q class

---

### Requirement: No CLAUDE.md Violations

Every rule file SHALL comply with CLAUDE.md rules.

Violations to fix:
1. ZERO FALLBACK violations (if not result: try_alternative())
2. Emoji in strings (causes Windows CP1252 crash)
3. Table existence checks before queries
4. Try-except fallback patterns

#### Scenario: Fallback pattern detected

- **WHEN** rule has `if not result: cursor.execute(alternative_query)`
- **THEN** MUST remove fallback - single code path only

---

## Migration Validation

### Validation: Import Test

For each file:
```bash
python -c "import theauditor.rules.{module_path}"
```

### Validation: Raw SQL Grep

```bash
grep -r "cursor.execute" theauditor/rules --include="*.py" | grep -v "Q.raw" | wc -l
# MUST be 0
```

### Validation: Full Pipeline

```bash
aud full --offline
# MUST complete without crashes
```
