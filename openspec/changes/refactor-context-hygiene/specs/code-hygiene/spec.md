# Code Hygiene Capability

Internal standards for AI-consumable code quality.

## ADDED Requirements

### Requirement: Generated Code Quality

The code generator (`schemas/codegen.py`) SHALL output Python code that passes `ruff check` with zero errors.

Generated code MUST use:
- Modern type hints (`list[str]` not `List[str]`)
- Union syntax (`X | None` not `Optional[X]`)
- No trailing whitespace

#### Scenario: Generator produces clean output
- **WHEN** the code generator runs
- **THEN** all generated files (`generated_*.py`) have zero ruff issues
- **AND** use Python 3.9+ type syntax

#### Scenario: Regeneration maintains cleanliness
- **WHEN** generated files are regenerated after schema changes
- **THEN** the new files still have zero ruff issues

---

### Requirement: Zero Dead Code Policy

The codebase SHALL NOT contain dead code that pollutes AI context windows.

Dead code includes:
- Functions with no callers (verified via `aud query --symbol X --show-callers`)
- Commented-out "legacy" blocks
- Unused imports (F401)
- Unused variables (F841)

#### Scenario: Dead function detection
- **WHEN** a function has zero callers in the call graph
- **THEN** it MUST be deleted (git is the safety net)

#### Scenario: Unused import cleanup
- **WHEN** an import is flagged as F401 (unused)
- **AND** the imported symbol has no references in the file
- **THEN** the import MUST be deleted

---

### Requirement: Zero Fallback Compliance

All code MUST comply with CLAUDE.md's ZERO FALLBACK POLICY.

Forbidden patterns:
- Try/except blocks that return empty results on failure
- Table existence checks before queries
- Multiple query fallbacks (try query A, if fail try query B)

#### Scenario: No silent exception swallowing
- **WHEN** a database query fails
- **THEN** the error MUST propagate (crash loud)
- **AND** NOT return empty results silently

#### Scenario: No table existence checks
- **WHEN** querying a contracted table
- **THEN** the query MUST execute directly
- **AND** NOT check if table exists first

---

### Requirement: Type Safety at Boundaries

Public API interfaces MUST have type hints for inputs and outputs.

Scope includes:
- Extractor interfaces (`BaseExtractor` methods)
- Database manager public methods
- CLI command signatures
- Graph builder interfaces

Scope excludes:
- Private methods (`_helper`)
- Internal module functions
- Complex `**kwargs` handlers

#### Scenario: Public extractor method is typed
- **WHEN** a method is part of `BaseExtractor` public interface
- **THEN** it MUST have type hints for all parameters and return value

#### Scenario: Internal helper is not over-typed
- **WHEN** a function is private (`_name`) and under 10 lines
- **THEN** type hints are optional (AI can infer from context)

---

### Requirement: Data Integrity in Iterations

All `zip()` calls processing data where length mismatch indicates a bug MUST use `strict=True`.

#### Scenario: Parallel data processing uses strict zip
- **WHEN** iterating over two related data structures (e.g., `calls` and `definitions`)
- **AND** a length mismatch would indicate data corruption
- **THEN** `zip(..., strict=True)` MUST be used

#### Scenario: Intentional truncation is documented
- **WHEN** `zip()` is used without `strict=True`
- **AND** truncation is intentional behavior
- **THEN** a comment MUST explain why truncation is acceptable
