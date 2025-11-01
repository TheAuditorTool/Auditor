# AST Extraction Specification - Delta

## MODIFIED Requirements

### Requirement: Python Implementation Layer Separation

The Python AST extraction implementation SHALL be split into two distinct layers with clear separation of concerns and one-way dependency.

**Layer 1: Structural Extraction (python_impl_structure.py)**
- SHALL contain stateless AST traversal functions
- SHALL NOT depend on function context or scope resolution
- SHALL provide core utilities, constants, and structural extractors
- SHALL be importable without importing behavioral layer

**Layer 2: Behavioral Extraction (python_impl.py)**
- SHALL contain stateful, context-dependent extraction functions
- SHALL import from python_impl_structure.py (one-way dependency)
- SHALL re-export all structural extractors for backward compatibility
- SHALL provide assignments, returns, CFG, and context-aware extraction

**Dependency Contract**:
- python_impl.py MAY import from python_impl_structure.py
- python_impl_structure.py SHALL NOT import from python_impl.py
- Circular dependencies are FORBIDDEN

#### Scenario: Structural extraction without behavioral layer

- **WHEN** a developer imports structural extractors
- **THEN** they can import from python_impl_structure.py directly
- **AND** NO behavioral layer code is loaded
- **AND** NO function context utilities are required

#### Scenario: Behavioral extraction with full context

- **WHEN** a developer uses behavioral extractors (assignments, returns, CFG)
- **THEN** they import from python_impl.py
- **AND** python_impl.py automatically loads structural layer
- **AND** both layers work together seamlessly

#### Scenario: Backward compatibility maintained

- **WHEN** existing code imports from python_impl
- **THEN** all previously available functions work unchanged
- **AND** function signatures remain identical
- **AND** output formats remain identical
- **AND** NO breaking changes occur

### Requirement: Architecture Documentation Pattern

Python implementation layers SHALL follow the TypeScript implementation documentation pattern for consistency.

**Module Docstrings SHALL include**:
- Layer identifier ("Part 1" or "Part 2" of implementation split)
- RESPONSIBILITY section describing layer purpose
- Core Components list
- ARCHITECTURAL CONTRACT defining constraints
- DEPENDENCIES section (behavioral layer only)
- CONSUMERS section listing importers

#### Scenario: Developer reads python_impl_structure.py docstring

- **WHEN** a developer opens python_impl_structure.py
- **THEN** the docstring clearly states "This module is Part 1 of the Python implementation layer split"
- **AND** RESPONSIBILITY section says "Structural Extraction (Stateless AST Traversal)"
- **AND** ARCHITECTURAL CONTRACT forbids function context dependencies
- **AND** CONSUMERS lists python_impl.py and orchestrator

#### Scenario: Developer reads python_impl.py docstring

- **WHEN** a developer opens python_impl.py
- **THEN** the docstring clearly states "This module is Part 2 of the Python implementation layer split"
- **AND** RESPONSIBILITY section says "Behavioral Analysis (Context-Dependent Semantic Extraction)"
- **AND** DEPENDENCIES section lists python_impl_structure.py and context utilities
- **AND** pattern matches typescript_impl.py exactly

### Requirement: Split Ratio Balance

The split between structural and behavioral layers SHALL achieve approximately 50/50 balance (±5%) to match TypeScript implementation pattern.

**Metrics**:
- python_impl_structure.py target: ~1150 lines (48-52% of 2324 total)
- python_impl.py target: ~1174 lines (48-52% of 2324 total)
- TypeScript reference: typescript_impl_structure.py 1031 lines (44%), typescript_impl.py 1328 lines (56%)

#### Scenario: Split ratio verification

- **WHEN** the split is complete
- **THEN** python_impl_structure.py line count is between 1105-1195 lines (48-52%)
- **AND** python_impl.py line count is between 1105-1195 lines (48-52%)
- **AND** total line count equals original 2324 lines (no code lost)
- **AND** NO duplicate function definitions exist across both files

#### Scenario: Pattern consistency with TypeScript

- **WHEN** comparing Python split to TypeScript split
- **THEN** both follow same architectural pattern
- **AND** both use one-way dependency (behavioral → structural)
- **AND** both use re-export pattern for backward compatibility
- **AND** both achieve similar split ratios (45-55%)
