# Capability: Rules Fidelity Migration

Migration of all 95 rule files to use Q class and fidelity infrastructure.

**This is NOT just a mechanical migration.** Rules are the core value of TheAuditor. Every rule must be evaluated for detection quality, not just converted to use new infrastructure.

---

## MANDATORY READS Before Implementation

Every terminal MUST read these files BEFORE starting any work:

1. `CLAUDE.md` - ALL sections, especially ZERO FALLBACK
2. `theauditor/rules/RULES_HANDOFF.md` - Fidelity philosophy, Q class patterns
3. `theauditor/rules/TEMPLATE_FIDELITY_RULE.py` - THE canonical template

**If you skip these, your work will be rejected.**

---

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

### Requirement: All Rules Match Template Structure

Every rule file SHALL match the structure in `TEMPLATE_FIDELITY_RULE.py`.

Required structure:
1. Imports from `theauditor.rules.base` and `theauditor.rules.fidelity`
2. `METADATA = RuleMetadata(...)` constant
3. `analyze(context: StandardRuleContext) -> RuleResult` function
4. Guard clause for missing db_path
5. `RuleDB` context manager usage
6. `RuleResult` return with manifest

#### Scenario: Non-compliant structure

- **WHEN** rule does not follow template structure
- **THEN** MUST be refactored to match template exactly

---

### Requirement: Detection Logic Quality Evaluation

Every rule file SHALL have its detection logic evaluated for quality.

Quality checks MUST include:
1. Does the rule catch real vulnerabilities?
2. Are there false positive patterns (logging, testing, comments)?
3. Are there missing attack patterns?
4. Is the CWE-ID correct for what the rule detects?
5. Is the severity rating appropriate for impact?

#### Scenario: Quality issues found

- **WHEN** quality evaluation finds issues
- **THEN** issues MUST be either fixed inline OR documented as `# TODO(quality): <description>`

#### Scenario: Flagship rule evaluation

- **WHEN** rule is a flagship rule (SQLi, XSS, DOM XSS)
- **THEN** thorough detection review is REQUIRED, not optional

---

### Requirement: False Positive Mitigation

Every rule SHALL have false positive patterns identified and documented.

Minimum false positive patterns to check:
1. Logging statements (console.log, logger.info, print)
2. Test files and test fixtures
3. Comments and documentation
4. Dead/disabled code
5. Safe wrapper functions

#### Scenario: False positive pattern identified

- **WHEN** rule has obvious false positive pattern
- **THEN** pattern MUST be filtered OR documented as known limitation

---

### Requirement: CWE Mapping Verification

Every rule SHALL have its CWE-ID verified against actual detection logic.

The CWE-ID MUST:
1. Match what the rule actually detects
2. Be the most specific applicable CWE
3. Cover all detection patterns in the rule

#### Scenario: CWE mismatch

- **WHEN** CWE-ID does not match detection logic
- **THEN** CWE-ID MUST be corrected

---

### Requirement: Quality Reports

Every terminal SHALL produce a Quality Report for each wave.

Quality Report MUST include:
1. Rules with quality issues found
2. Rules with TODO(quality) comments added
3. Rules needing major rework (flagged for follow-up)
4. CWE coverage observations

#### Scenario: Quality report missing

- **WHEN** terminal completes wave without quality report
- **THEN** wave is NOT complete - quality report REQUIRED

---

## Migration Validation

### Mechanical Validation

#### Validation: Import Test

For each file:
```bash
python -c "import theauditor.rules.{module_path}"
```

#### Validation: Raw SQL Grep

```bash
grep -r "cursor.execute" theauditor/rules --include="*.py" | grep -v "Q.raw" | wc -l
# MUST be 0
```

#### Validation: Full Pipeline

```bash
aud full --offline
# MUST complete without crashes
```

#### Validation: Template Compliance

```bash
# All rules have RuleResult return
grep -rL "RuleResult" theauditor/rules --include="*_analyze.py" | wc -l
# MUST be 0

# All rules have METADATA
grep -rL "METADATA = RuleMetadata" theauditor/rules --include="*_analyze.py" | wc -l
# MUST be 0
```

### Quality Validation

#### Validation: Quality Reports Collected

```
# All 20 quality reports collected (10 terminals x 2 waves)
T1.QR, T1.QR2, T2.QR, T2.QR2, ... T10.QR, T10.QR2
```

#### Validation: TODO Comments Present

```bash
grep -r "TODO(quality)" theauditor/rules --include="*.py" | wc -l
# Should be > 0 (issues found and documented)
```

#### Validation: Flagship Rules Reviewed

Manual verification that these rules received thorough quality review:
- `sql_injection_analyze.py` - SQLi detection
- `xss_analyze.py` - XSS detection
- `dom_xss_analyze.py` - DOM XSS detection

### Success Criteria Summary

**Mechanical (MUST PASS):**
1. All 95 files import successfully
2. Zero raw `cursor.execute()` remaining
3. `aud full --offline` completes without crashes
4. All rules have `RuleResult` return
5. All rules have `METADATA` constant
6. All rules match template structure

**Quality (MUST DOCUMENT):**
1. All 20 quality reports collected
2. TODO(quality) comments present where issues found
3. Flagship rules thoroughly reviewed
4. CWE coverage verified
5. Major rework items identified for post-migration
