# AST Extractors - Module Organization Delta

## MODIFIED Requirements

### Requirement: JavaScript Semantic Parser Module Location

The JavaScript semantic parser MUST be located in the `ast_extractors` package alongside other AST parsing implementations. The module MUST maintain backward compatibility through a re-export shim at the legacy location.

**Previous Behavior**: `js_semantic_parser.py` was located at `theauditor/js_semantic_parser.py` (root level).

**New Behavior**:
- Primary implementation at `theauditor/ast_extractors/js_semantic_parser.py` (logical location)
- Backward compatibility shim at `theauditor/js_semantic_parser.py` (re-exports from new location)
- Package exports module via `theauditor/ast_extractors/__init__.py`

#### Scenario: Import from legacy location (backward compatibility)
- **WHEN** code imports `from theauditor.js_semantic_parser import JSSemanticParser`
- **THEN** the import SHALL succeed via the backward compatibility shim
- **AND** the imported class SHALL be identical to importing from the new location

#### Scenario: Import from new location (logical structure)
- **WHEN** code imports `from theauditor.ast_extractors.js_semantic_parser import JSSemanticParser`
- **THEN** the import SHALL succeed directly from the implementation
- **AND** the imported class SHALL function identically to the legacy import

#### Scenario: Package-level discovery
- **WHEN** code imports `theauditor.ast_extractors`
- **THEN** the `js_semantic_parser` module SHALL be available in the package namespace
- **AND** all public API (JSSemanticParser, get_semantic_ast, get_semantic_ast_batch) SHALL be accessible

---

### Requirement: TypeScript Implementation Modular Structure

The TypeScript AST implementation MUST be organized into separate API and implementation layers to fit within AI context windows while maintaining all public API contracts.

**Previous Behavior**: Single monolithic file `typescript_impl.py` (~2000 lines) containing both public API and low-level implementation.

**New Behavior**:
- API layer: `typescript_impl.py` (~1200 lines) - public `extract_*` functions
- Implementation layer: `typescript_ast_utils.py` (~800 lines) - low-level helpers, JSX logic, complex algorithms
- API layer imports implementation layer via `from . import typescript_ast_utils as ast_utils`

#### Scenario: Public API function calls (unchanged behavior)
- **WHEN** code calls any public `extract_*` function from `typescript_impl.py`
- **THEN** the function SHALL execute with identical behavior to pre-refactor
- **AND** the function signature SHALL remain unchanged
- **AND** the return value SHALL have the same structure and content

#### Scenario: Internal helper delegation
- **WHEN** a public API function in `typescript_impl.py` needs a low-level helper
- **THEN** it SHALL call the helper via `ast_utils.function_name()`
- **AND** the helper SHALL execute from `typescript_ast_utils.py`
- **AND** the behavior SHALL be identical to the pre-refactor monolithic implementation

#### Scenario: AI context window requirement
- **WHEN** an AI assistant reads `typescript_impl.py` or `typescript_ast_utils.py`
- **THEN** each file SHALL be less than 1500 lines
- **AND** both files SHALL fit within typical AI context windows independently
- **AND** the separation SHALL follow clear separation of concerns (API vs implementation)

---

## ADDED Requirements

### Requirement: Backward Compatibility Shim Pattern

The codebase SHALL use backward compatibility shims for module reorganizations to guarantee zero breaking changes for existing consumers.

#### Scenario: Shim preserves import paths
- **WHEN** a module is moved to a new location
- **THEN** a shim module SHALL be created at the original location
- **AND** the shim SHALL re-export all public API from the new location
- **AND** all existing import statements SHALL continue working unchanged

#### Scenario: Shim maintains object identity
- **WHEN** code imports the same class from both old and new locations
- **THEN** both imports SHALL resolve to the identical Python object
- **AND** identity checks (`Old is New`) SHALL return True
- **AND** no duplicate class instances SHALL exist

#### Scenario: Shim documentation
- **WHEN** a developer reads the shim module
- **THEN** the shim SHALL have a clear docstring explaining it's for backward compatibility
- **AND** the docstring SHALL indicate the new canonical location
- **AND** the shim SHALL define `__all__` listing all re-exported names

---

## Implementation Notes

**Non-Breaking Changes**: All modifications preserve exact function signatures, return types, and behavior. Existing code continues working without any changes required.

**Internal Refactor Only**: The changes reorganize internal module structure but do not affect:
- Database schema (no table changes)
- External APIs (all public functions unchanged)
- CLI commands (no command changes)
- Configuration (no settings changes)

**Validation**: Backward compatibility is validated through import equivalence tests verifying that old and new import paths resolve to identical objects.
