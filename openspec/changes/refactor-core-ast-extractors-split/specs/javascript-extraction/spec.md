## MODIFIED Requirements

### Requirement: Core Extractor Architecture

The JavaScript/TypeScript AST extraction layer SHALL organize extractor functions by domain (language structure, data flow, module/framework) for maintainability and scalability.

**Implementation**: The core extraction layer uses a domain-split architecture with three modules: `core_language.js` (language structure and scope), `data_flow.js` (data flow and taint analysis), and `module_framework.js` (imports and framework patterns). This organization enables independent growth of each domain while maintaining backward compatibility.

**Rationale**: The monolithic `core_ast_extractors.js` exceeded its documented 2,000 line growth policy threshold (2,376 lines). Domain separation prevents future monolithic file collapse and improves developer navigation.

#### Scenario: Extractor assembly and execution

- **WHEN** the batch helper assembles the JavaScript extraction script
- **THEN** the orchestrator SHALL load three domain-specific modules (core_language.js, data_flow.js, module_framework.js) and concatenate them in order
- **AND** the assembled batch script SHALL contain all 17 extractor functions (6 language structure, 6 data flow, 5 module/framework)
- **AND** the TypeScript compilation SHALL succeed with zero errors

#### Scenario: Extraction behavior preserved

- **WHEN** the indexer processes a TypeScript file containing functions, classes, assignments, calls, returns, imports, and ORM relationships
- **THEN** the database SHALL contain identical record counts across all extraction tables (symbols, function_call_args, imports, assignments, class_properties, env_var_usage, orm_relationships) as before the refactor
- **AND** all taint analysis dependencies (scopeMap, data flow extractors) SHALL remain functional

#### Scenario: Backward compatibility maintained

- **WHEN** the orchestrator calls `get_batch_helper('module')` from `js_helper_templates.py`
- **THEN** the function signature SHALL remain unchanged from previous versions
- **AND** the returned batch script SHALL assemble successfully
- **AND** all existing code SHALL continue to function without modification
- **AND** the batch script execution via Node.js subprocess SHALL produce identical database records

#### Scenario: Domain independence

- **WHEN** a developer adds a new language structure extractor (e.g., extractDecorators)
- **THEN** the change SHALL be isolated to `core_language.js` only
- **AND** no modifications SHALL be required to `data_flow.js` or `module_framework.js`
- **AND** the file SHALL remain under 1,000 lines after the addition

#### Scenario: Growth policy compliance

- **WHEN** any domain module exceeds 1,000 lines
- **THEN** the module SHALL be further subdivided by sub-domain
- **AND** the growth policy SHALL be documented in the module header
- **AND** the architectural pattern (domain separation) SHALL be preserved
