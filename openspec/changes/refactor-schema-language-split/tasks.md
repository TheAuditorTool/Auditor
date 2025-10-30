# Implementation Tasks: Schema Language Split + Indexer Orchestrator Refactor

**Change ID**: `refactor-schema-language-split`
**Status**: Pending Approval
**Estimated Time**: 8-10 hours (Schema: 4-6h + Orchestrator: 4-5h)

## 0. Verification (Pre-Implementation)

**Schema Verification**:
- [x] 0.1 Read entire schema.py and map all tables
- [x] 0.2 Identify all consumers (50+ files)
- [x] 0.3 Categorize all 70 tables by language

**Orchestrator Verification (NEW)**:
- [x] 0.4 Read entire `__init__.py` and map orchestration logic
- [x] 0.5 Identify critical sections (JSX dual-pass, TypeScript batch, cross-file resolution)
- [x] 0.6 Map line ranges for each orchestrator module

**Documentation**:
- [x] 0.7 Create/update verification.md with comprehensive mapping (both components)
- [x] 0.8 Create/update proposal.md (both components)
- [x] 0.9 Create/update design.md (both components)
- [x] 0.10 Update tasks.md (this file) with orchestrator tasks
- [ ] 0.11 Architect approval on verification.md
- [ ] 0.12 Lead Auditor approval on design.md

**DO NOT PROCEED TO SECTION 1 UNTIL APPROVAL RECEIVED**

## 1. Directory Setup

- [ ] 1.1 Create `theauditor/indexer/schemas/` directory
- [ ] 1.2 Create `theauditor/indexer/schemas/__init__.py` (empty file)
- [ ] 1.3 Verify directory structure created correctly

## 2. Extract Utility Classes

- [ ] 2.1 Create `theauditor/indexer/schemas/utils.py`
- [ ] 2.2 Copy `Column` class from schema.py (lines 38-59)
- [ ] 2.3 Copy `ForeignKey` class from schema.py (lines 62-121)
- [ ] 2.4 Copy `TableSchema` class from schema.py (lines 123-238)
- [ ] 2.5 Add imports: `from typing import Dict, List, Optional, Tuple`, `from dataclasses import dataclass, field`, `import sqlite3`
- [ ] 2.6 Verify utils.py has NO table definitions (classes only)
- [ ] 2.7 Test import: `python -c "from theauditor.indexer.schemas.utils import Column, ForeignKey, TableSchema"`

## 3. Create Core Schema Module

- [ ] 3.1 Create `theauditor/indexer/schemas/core_schema.py`
- [ ] 3.2 Add header docstring and imports
- [ ] 3.3 Copy FILES table (lines 245-256)
- [ ] 3.4 Copy CONFIG_FILES table (lines 258-267)
- [ ] 3.5 Copy REFS table (lines 269-280)
- [ ] 3.6 Copy SYMBOLS table (lines 286-305)
- [ ] 3.7 Copy SYMBOLS_JSX table (lines 307-323)
- [ ] 3.8 Copy ASSIGNMENTS table (lines 633-650)
- [ ] 3.9 Copy ASSIGNMENTS_JSX table (lines 652-670)
- [ ] 3.10 Copy ASSIGNMENT_SOURCES table (lines 756-777)
- [ ] 3.11 Copy ASSIGNMENT_SOURCES_JSX table (lines 779-801)
- [ ] 3.12 Copy FUNCTION_CALL_ARGS table (lines 672-691)
- [ ] 3.13 Copy FUNCTION_CALL_ARGS_JSX table (lines 693-711)
- [ ] 3.14 Copy FUNCTION_RETURNS table (lines 713-730)
- [ ] 3.15 Copy FUNCTION_RETURNS_JSX table (lines 732-750)
- [ ] 3.16 Copy FUNCTION_RETURN_SOURCES table (lines 803-824)
- [ ] 3.17 Copy FUNCTION_RETURN_SOURCES_JSX table (lines 826-848)
- [ ] 3.18 Copy VARIABLE_USAGE table (lines 850-866)
- [ ] 3.19 Copy OBJECT_LITERALS table (lines 868-887)
- [ ] 3.20 Copy SQL_OBJECTS table (lines 528-537)
- [ ] 3.21 Copy SQL_QUERIES table (lines 539-553)
- [ ] 3.22 Copy SQL_QUERY_TABLES table (lines 558-578)
- [ ] 3.23 Copy ORM_QUERIES table (lines 580-594)
- [ ] 3.24 Copy JWT_PATTERNS table (lines 596-611)
- [ ] 3.25 Copy CFG_BLOCKS table (lines 894-908)
- [ ] 3.26 Copy CFG_EDGES table (lines 910-926)
- [ ] 3.27 Copy CFG_BLOCK_STATEMENTS table (lines 928-939)
- [ ] 3.28 Copy FINDINGS_CONSOLIDATED table (lines 1569-1594)
- [ ] 3.29 Create CORE_TABLES dict with 26 entries
- [ ] 3.30 Copy build_query function (lines 1840-1899)
- [ ] 3.31 Copy build_join_query function (lines 1902-2067)
- [ ] 3.32 Copy validate_all_tables function (lines 2070-2083)
- [ ] 3.33 Copy get_table_schema function (lines 2086-2104)
- [ ] 3.34 Update imports: `from .utils import Column, ForeignKey, TableSchema`
- [ ] 3.35 Test import: `python -c "from theauditor.indexer.schemas.core_schema import CORE_TABLES; assert len(CORE_TABLES) == 26"`

## 4. Create Python Schema Module

- [ ] 4.1 Create `theauditor/indexer/schemas/python_schema.py`
- [ ] 4.2 Add header docstring and imports
- [ ] 4.3 Copy PYTHON_ORM_MODELS table (lines 436-450)
- [ ] 4.4 Copy PYTHON_ORM_FIELDS table (lines 452-470)
- [ ] 4.5 Copy PYTHON_ROUTES table (lines 472-489)
- [ ] 4.6 Copy PYTHON_BLUEPRINTS table (lines 491-504)
- [ ] 4.7 Copy PYTHON_VALIDATORS table (lines 506-521)
- [ ] 4.8 Create PYTHON_TABLES dict with 5 entries
- [ ] 4.9 Update imports: `from .utils import Column, ForeignKey, TableSchema`
- [ ] 4.10 Test import: `python -c "from theauditor.indexer.schemas.python_schema import PYTHON_TABLES; assert len(PYTHON_TABLES) == 5"`

## 5. Create Node Schema Module

- [ ] 5.1 Create `theauditor/indexer/schemas/node_schema.py`
- [ ] 5.2 Add header docstring and imports
- [ ] 5.3 Copy CLASS_PROPERTIES table (lines 325-345)
- [ ] 5.4 Copy ENV_VAR_USAGE table (lines 347-363)
- [ ] 5.5 Copy ORM_RELATIONSHIPS table (lines 365-384)
- [ ] 5.6 Copy API_ENDPOINTS table (lines 390-405)
- [ ] 5.7 Copy API_ENDPOINT_CONTROLS table (lines 410-430)
- [ ] 5.8 Copy PRISMA_MODELS table (lines 613-627)
- [ ] 5.9 Copy REACT_COMPONENTS table (lines 945-961)
- [ ] 5.10 Copy REACT_COMPONENT_HOOKS table (lines 966-986)
- [ ] 5.11 Copy REACT_HOOKS table (lines 988-1006)
- [ ] 5.12 Copy REACT_HOOK_DEPENDENCIES table (lines 1011-1032)
- [ ] 5.13 Copy VUE_COMPONENTS table (lines 1038-1058)
- [ ] 5.14 Copy VUE_HOOKS table (lines 1060-1077)
- [ ] 5.15 Copy VUE_DIRECTIVES table (lines 1079-1094)
- [ ] 5.16 Copy VUE_PROVIDE_INJECT table (lines 1096-1110)
- [ ] 5.17 Copy TYPE_ANNOTATIONS table (lines 1116-1140)
- [ ] 5.18 Copy PACKAGE_CONFIGS table (lines 1437-1453)
- [ ] 5.19 Copy LOCK_ANALYSIS table (lines 1455-1469)
- [ ] 5.20 Copy IMPORT_STYLES table (lines 1471-1487)
- [ ] 5.21 Copy IMPORT_STYLE_NAMES table (lines 1492-1512)
- [ ] 5.22 Copy FRAMEWORKS table (lines 1518-1532)
- [ ] 5.23 Copy FRAMEWORK_SAFE_SINKS table (lines 1534-1544)
- [ ] 5.24 Copy VALIDATION_FRAMEWORK_USAGE table (lines 1546-1562)
- [ ] 5.25 Create NODE_TABLES dict with 22 entries
- [ ] 5.26 Update imports: `from .utils import Column, ForeignKey, TableSchema`
- [ ] 5.27 Test import: `python -c "from theauditor.indexer.schemas.node_schema import NODE_TABLES; assert len(NODE_TABLES) == 22"`

## 6. Create Infrastructure Schema Module

- [ ] 6.1 Create `theauditor/indexer/schemas/infrastructure_schema.py`
- [ ] 6.2 Add header docstring and imports
- [ ] 6.3 Copy DOCKER_IMAGES table (lines 1146-1160)
- [ ] 6.4 Copy COMPOSE_SERVICES table (lines 1162-1189)
- [ ] 6.5 Copy NGINX_CONFIGS table (lines 1191-1205)
- [ ] 6.6 Copy TERRAFORM_FILES table (lines 1211-1226)
- [ ] 6.7 Copy TERRAFORM_RESOURCES table (lines 1228-1255)
- [ ] 6.8 Copy TERRAFORM_VARIABLES table (lines 1257-1282)
- [ ] 6.9 Copy TERRAFORM_VARIABLE_VALUES table (lines 1284-1299)
- [ ] 6.10 Copy TERRAFORM_OUTPUTS table (lines 1301-1324)
- [ ] 6.11 Copy TERRAFORM_FINDINGS table (lines 1326-1358)
- [ ] 6.12 Copy CDK_CONSTRUCTS table (lines 1365-1379)
- [ ] 6.13 Copy CDK_CONSTRUCT_PROPERTIES table (lines 1381-1402)
- [ ] 6.14 Copy CDK_FINDINGS table (lines 1404-1430)
- [ ] 6.15 Create INFRASTRUCTURE_TABLES dict with 12 entries
- [ ] 6.16 Update imports: `from .utils import Column, ForeignKey, TableSchema`
- [ ] 6.17 Test import: `python -c "from theauditor.indexer.schemas.infrastructure_schema import INFRASTRUCTURE_TABLES; assert len(INFRASTRUCTURE_TABLES) == 12"`

## 7. Create Planning Schema Module

- [ ] 7.1 Create `theauditor/indexer/schemas/planning_schema.py`
- [ ] 7.2 Add header docstring and imports
- [ ] 7.3 Copy PLANS table (lines 1601-1614)
- [ ] 7.4 Copy PLAN_TASKS table (lines 1616-1650)
- [ ] 7.5 Copy PLAN_SPECS table (lines 1652-1672)
- [ ] 7.6 Copy CODE_SNAPSHOTS table (lines 1674-1702)
- [ ] 7.7 Copy CODE_DIFFS table (lines 1704-1725)
- [ ] 7.8 Create PLANNING_TABLES dict with 5 entries
- [ ] 7.9 Update imports: `from .utils import Column, ForeignKey, TableSchema`
- [ ] 7.10 Test import: `python -c "from theauditor.indexer.schemas.planning_schema import PLANNING_TABLES; assert len(PLANNING_TABLES) == 5"`

## 8. Create Stub (schema.py Replacement)

- [ ] 8.1 Backup original schema.py: `cp schema.py schema.py.backup`
- [ ] 8.2 Replace schema.py with stub implementation
- [ ] 8.3 Add imports from all sub-modules
- [ ] 8.4 Merge all TABLES dicts: `TABLES = {**CORE_TABLES, **PYTHON_TABLES, **NODE_TABLES, **INFRASTRUCTURE_TABLES, **PLANNING_TABLES}`
- [ ] 8.5 Re-export all utilities: Column, ForeignKey, TableSchema, build_query, build_join_query, validate_all_tables, get_table_schema
- [ ] 8.6 Add __all__ for explicit exports
- [ ] 8.7 Test stub import: `python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == 70"`

---

## 9. Orchestrator Directory Setup (NEW - Orchestrator Component)

- [ ] 9.1 Create `theauditor/indexer/orchestration/` directory
- [ ] 9.2 Create `theauditor/indexer/orchestration/__init__.py` (empty file)
- [ ] 9.3 Verify directory structure created correctly

## 10. Create Core Orchestrator (NEW - Base Class)

- [ ] 10.1 Create `theauditor/indexer/orchestration/core_orchestrator.py`
- [ ] 10.2 Add header docstring and imports
- [ ] 10.3 Copy BaseOrchestrator class definition (abstract base)
- [ ] 10.4 Copy `__init__()` method from `__init__.py` lines 61-146 (component initialization)
- [ ] 10.5 Copy `index()` main method skeleton (lines 230-327, 337-432, 654-658)
- [ ] 10.6 Copy `_store_frameworks()` method (lines 189-229)
- [ ] 10.7 Copy `_process_file()` method (lines 660-1007) - core delegation only
- [ ] 10.8 Copy `_store_extracted_data()` method (lines 1009-1993) - core storage only
- [ ] 10.9 Copy `_cleanup_extractors()` method (lines 1995-2021)
- [ ] 10.10 Add helper methods: `_get_or_parse_ast()`, `_select_extractor()`
- [ ] 10.11 Test import: `python -c "from theauditor.indexer.orchestration.core_orchestrator import BaseOrchestrator"`

## 11. Create Python Orchestrator (NEW)

- [ ] 11.1 Create `theauditor/indexer/orchestration/python_orchestrator.py`
- [ ] 11.2 Add header docstring and imports
- [ ] 11.3 Create PythonOrchestrationMixin class
- [ ] 11.4 Copy `_detect_python_frameworks()` method (lines 148-188, Python portion only)
- [ ] 11.5 Copy `_store_python_data()` method (lines 1009-1993, Python storage portions)
- [ ] 11.6 Add helper methods for Python-specific processing
- [ ] 11.7 Test import: `python -c "from theauditor.indexer.orchestration.python_orchestrator import PythonOrchestrationMixin"`

## 12. Create Node Orchestrator (NEW - LARGEST MODULE)

- [ ] 12.1 Create `theauditor/indexer/orchestration/node_orchestrator.py`
- [ ] 12.2 Add header docstring and imports
- [ ] 12.3 Create NodeOrchestrationMixin class
- [ ] 12.4 Copy `_batch_process_js_ts()` method (lines 258-310) - **CRITICAL: TypeScript batch + global params cache**
- [ ] 12.5 Copy `_resolve_cross_file_params()` method (lines 329-336) - **CRITICAL: Bug #3 fix**
- [ ] 12.6 Copy `_jsx_dual_pass_extraction()` method (lines 434-652) - **CRITICAL: 218-line React logic, move AS-IS!**
- [ ] 12.7 Copy `_detect_node_frameworks()` method (lines 148-188, Node portion only)
- [ ] 12.8 Copy `_store_node_data()` method (lines 1009-1993, Node storage portions)
- [ ] 12.9 Add helper methods for Node-specific processing
- [ ] 12.10 Test import: `python -c "from theauditor.indexer.orchestration.node_orchestrator import NodeOrchestrationMixin"`
- [ ] 12.11 **CRITICAL**: Verify JSX dual-pass logic copied exactly (diff lines 434-652)

## 13. Create Rust Orchestrator (NEW)

- [ ] 13.1 Create `theauditor/indexer/orchestration/rust_orchestrator.py`
- [ ] 13.2 Add header docstring and imports
- [ ] 13.3 Create RustOrchestrationMixin class
- [ ] 13.4 Copy `_store_rust_data()` method (lines 1009-1993, Rust storage portions)
- [ ] 13.5 Add helper methods for Rust-specific processing
- [ ] 13.6 Test import: `python -c "from theauditor.indexer.orchestration.rust_orchestrator import RustOrchestrationMixin"`

## 14. Create Infrastructure Orchestrator (NEW)

- [ ] 14.1 Create `theauditor/indexer/orchestration/infrastructure_orchestrator.py`
- [ ] 14.2 Add header docstring and imports
- [ ] 14.3 Create InfrastructureOrchestrationMixin class
- [ ] 14.4 Copy `_store_infrastructure_data()` method (lines 1009-1993, Infrastructure storage portions)
- [ ] 14.5 Add helper methods for Docker/Terraform/CDK processing
- [ ] 14.6 Test import: `python -c "from theauditor.indexer.orchestration.infrastructure_orchestrator import InfrastructureOrchestrationMixin"`

## 15. Merge Orchestrators & Create Stub (NEW)

- [ ] 15.1 In `core_orchestrator.py`, import all mixins
- [ ] 15.2 Create final merged `IndexerOrchestrator` class with all mixins
- [ ] 15.3 Test MRO: `python -c "from theauditor.indexer.orchestration.core_orchestrator import IndexerOrchestrator; print(IndexerOrchestrator.__mro__)"`
- [ ] 15.4 Backup original `__init__.py`: `cp __init__.py __init__.py.backup`
- [ ] 15.5 Replace `__init__.py` with stub implementation (20 lines)
- [ ] 15.6 Import IndexerOrchestrator from `orchestration.core_orchestrator`
- [ ] 15.7 Re-export: IndexerOrchestrator, FileWalker, ASTCache, DatabaseManager, ExtractorRegistry
- [ ] 15.8 Add __all__ for explicit exports
- [ ] 15.9 Test stub import: `python -c "from theauditor.indexer import IndexerOrchestrator, FileWalker, DatabaseManager"`

---

## 16. Schema Validation Tests (Critical - DO NOT SKIP)

- [ ] 16.1 Test table count: `python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == 70, f'Expected 70, got {len(TABLES)}'"`
- [ ] 16.2 Test all imports: `python -c "from theauditor.indexer.schema import TABLES, build_query, Column, TableSchema, ForeignKey, validate_all_tables, get_table_schema"`
- [ ] 16.3 Test query builder: `python -c "from theauditor.indexer.schema import build_query; q = build_query('symbols', ['name', 'type']); assert 'SELECT name, type FROM symbols' in q"`
- [ ] 16.4 Test no duplicate tables: `python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == len(set(TABLES.keys()))"`
- [ ] 16.5 Test all 70 tables present: `python -c "from theauditor.indexer.schema import TABLES; expected = ['files', 'config_files', 'refs', 'symbols', 'symbols_jsx', 'class_properties', 'env_var_usage', 'orm_relationships', 'api_endpoints', 'api_endpoint_controls', 'python_orm_models', 'python_orm_fields', 'python_routes', 'python_blueprints', 'python_validators', 'sql_objects', 'sql_queries', 'sql_query_tables', 'jwt_patterns', 'orm_queries', 'prisma_models', 'assignments', 'assignments_jsx', 'assignment_sources', 'assignment_sources_jsx', 'function_call_args', 'function_call_args_jsx', 'function_returns', 'function_returns_jsx', 'function_return_sources', 'function_return_sources_jsx', 'variable_usage', 'object_literals', 'cfg_blocks', 'cfg_edges', 'cfg_block_statements', 'react_components', 'react_component_hooks', 'react_hooks', 'react_hook_dependencies', 'vue_components', 'vue_hooks', 'vue_directives', 'vue_provide_inject', 'type_annotations', 'docker_images', 'compose_services', 'nginx_configs', 'terraform_files', 'terraform_resources', 'terraform_variables', 'terraform_variable_values', 'terraform_outputs', 'terraform_findings', 'cdk_constructs', 'cdk_construct_properties', 'cdk_findings', 'package_configs', 'lock_analysis', 'import_styles', 'import_style_names', 'frameworks', 'framework_safe_sinks', 'validation_framework_usage', 'findings_consolidated', 'plans', 'plan_tasks', 'plan_specs', 'code_snapshots', 'code_diffs']; missing = set(expected) - set(TABLES.keys()); assert not missing, f'Missing tables: {missing}'"`

## 17. Orchestrator Validation Tests (NEW - Critical - DO NOT SKIP)

- [ ] 17.1 Test orchestrator import: `python -c "from theauditor.indexer import IndexerOrchestrator, FileWalker, DatabaseManager"`
- [ ] 17.2 Test orchestrator instantiation: `python -c "from theauditor.indexer import IndexerOrchestrator; orc = IndexerOrchestrator('.', '.pf/repo_index.db'); print('OK')"`
- [ ] 17.3 Test MRO correctness: `python -c "from theauditor.indexer import IndexerOrchestrator; mro = IndexerOrchestrator.__mro__; assert 'BaseOrchestrator' in str(mro)"`
- [ ] 17.4 Test mixin presence: `python -c "from theauditor.indexer import IndexerOrchestrator; mro = IndexerOrchestrator.__mro__; assert 'PythonOrchestrationMixin' in str(mro) and 'NodeOrchestrationMixin' in str(mro)"`
- [ ] 17.5 Test method availability: `python -c "from theauditor.indexer import IndexerOrchestrator; assert hasattr(IndexerOrchestrator, 'index')"`

## 18. Combined Consumer Import Smoke Tests

- [ ] 18.1 Test rule imports: `python -c "import theauditor.rules.auth.jwt_analyze"`
- [ ] 18.2 Test taint imports: `python -c "import theauditor.taint.core"`
- [ ] 18.3 Test command imports: `python -c "import theauditor.commands.index"`
- [ ] 18.4 Test planning imports: `python -c "import theauditor.planning.manager"`
- [ ] 18.5 Test extractor imports: `python -c "import theauditor.indexer.extractors.python"`
- [ ] 18.6 Test database imports: `python -c "from theauditor.indexer.database import DatabaseManager"`

## 19. Schema Contract Tests

- [ ] 19.1 Run schema contract tests: `pytest tests/test_schema_contract.py -v`
- [ ] 19.2 Run database integration tests: `pytest tests/test_database_integration.py -v`
- [ ] 19.3 Run JSX pass tests (CRITICAL for orchestrator): `pytest tests/test_jsx_pass.py -v`
- [ ] 19.4 Run memory cache tests: `pytest tests/test_memory_cache.py -v`

## 20. Full Test Suite

- [ ] 20.1 Run full pytest suite: `pytest tests/ -v`
- [ ] 20.2 Verify 100% test pass rate
- [ ] 20.3 Fix any failures (DO NOT COMMIT if tests fail)

## 21. Integration Tests (CRITICAL - Both Schema & Orchestrator)

- [ ] 21.1 Test aud index: `aud index tests/fixtures/test_project`
- [ ] 21.2 Verify indexing completes successfully
- [ ] 21.3 **CRITICAL**: Test JSX extraction on React project (verify _jsx tables populated)
- [ ] 21.4 Test aud full: `aud full tests/fixtures/test_project`
- [ ] 21.5 Verify full analysis completes successfully
- [ ] 21.6 Compare database output before/after (MUST be identical)

## 22. Diff Verification (Both Components)

**Schema Verification**:
- [ ] 22.1 Verify merged schema matches original
- [ ] 22.2 Verify all 70 tables present in TABLES registry
- [ ] 22.3 Verify query builders work identically

**Orchestrator Verification (CRITICAL)**:
- [ ] 22.4 Compare `aud index` output before/after on test React project
- [ ] 22.5 **CRITICAL**: Verify JSX tables populated identically (compare _jsx table counts)
- [ ] 22.6 Verify orchestrator MRO correctness: `python -c "from theauditor.indexer import IndexerOrchestrator; print(IndexerOrchestrator.__mro__)"`
- [ ] 22.7 Verify TypeScript batch processing works (check debug output for global_function_params cache)

## 23. Final Pre-Commit Validation (Both Components)

- [ ] 23.1 Re-run all tests one final time: `pytest tests/ -v`
- [ ] 23.2 Re-run integration tests: `aud index && aud full`
- [ ] 23.3 Verify backups exist: Check `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py.backup` and `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\__init__.py.backup`
- [ ] 23.4 Verify all 14 new files exist (7 schema + 6 orchestration + 1 orchestration __init__)
- [ ] 23.5 Code review: Read through ALL new files for typos
- [ ] 23.6 Documentation review: Verify all docstrings copied correctly
- [ ] 23.7 **CRITICAL**: Verify JSX dual-pass logic (lines 434-652 from __init__.py.backup) copied exactly to node_orchestrator.py

## 24. Commit (Single Atomic Commit - Both Components)

- [ ] 24.1 Stage schema changes: `git add C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\`
- [ ] 24.2 Stage orchestrator changes: `git add C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\__init__.py C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestration\`
- [ ] 24.3 Verify staged changes: `git diff --cached`
- [ ] 24.4 Create atomic commit: `git commit -m "refactor(indexer): Split schema.py + __init__.py into language-specific modules\n\nBREAKING: None (100% backward compatible via stub pattern)\n\nChanges:\n- Split schema.py (2146 lines) into 6 language-specific modules\n- Split __init__.py (2021 lines) into 5 language-specific orchestrators\n- Created schemas/ subpackage: utils, core, python, node, infrastructure, planning\n- Created orchestration/ subpackage: core, python, node, rust, infrastructure\n- Replaced both with stubs maintaining backward compatibility\n- All 70 tables preserved, all imports work identically\n- All 50+ consumers unchanged (zero breaking changes)\n- Fixes code smell: __init__.py now proper Python usage (imports only)\n\nValidation:\n- All 70 tables present and accessible\n- All tests pass (pytest tests/ -v)\n- All consumers import successfully\n- aud index/full produce identical output\n- JSX dual-pass works identically (React analysis unaffected)\n- TypeScript batch processing works (Bug #3 fix preserved)\n- Cross-file param resolution works\n\nRollback: git revert this commit"`
- [ ] 24.5 DO NOT PUSH - wait for post-commit validation

## 25. Post-Commit Validation (CRITICAL - Both Components)

**Schema Validation**:
- [ ] 25.1 Test schema import: `python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == 70"`
- [ ] 25.2 Test query builders: `python -c "from theauditor.indexer.schema import build_query; print(build_query('symbols', ['name']))"`

**Orchestrator Validation (CRITICAL)**:
- [ ] 25.3 Test orchestrator import: `python -c "from theauditor.indexer import IndexerOrchestrator, FileWalker, DatabaseManager"`
- [ ] 25.4 Test orchestrator instantiation: `python -c "from theauditor.indexer import IndexerOrchestrator; orc = IndexerOrchestrator('.', '.pf/repo_index.db'); print('OK')"`
- [ ] 25.5 **CRITICAL**: Run JSX pass test: `pytest tests\test_jsx_pass.py -v`
- [ ] 25.6 Run full test suite again: `pytest tests/ -v`
- [ ] 25.7 Run integration tests again: `aud index && aud full`
- [ ] 25.8 If ANY test fails → `git reset --hard HEAD~1` (rollback immediately)
- [ ] 25.9 If all tests pass → PROCEED to Section 26

## 26. Cleanup (Both Components)

- [ ] 26.1 Delete schema backup: Delete `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py.backup`
- [ ] 26.2 Delete orchestrator backup: Delete `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\__init__.py.backup`
- [ ] 26.3 Update OpenSpec tasks.md: Mark all tasks as complete
- [ ] 26.4 Update OpenSpec proposal.md: Change status to "Implemented"
- [ ] 26.5 Create verification report in OpenSpec change directory

## 27. Documentation (Both Components)

- [ ] 27.1 Update CLAUDE.md if needed (reference new schemas/ and orchestration/ directories)
- [ ] 27.2 Update `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py` docstring (stub file)
- [ ] 27.3 Update `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\__init__.py` docstring (stub file)
- [ ] 27.4 No README updates needed (internal refactor, no user-facing changes)
- [ ] 27.5 No API docs updates needed (all imports identical)

## 28. Final Sign-Off

- [ ] 28.1 Lead Coder (Opus) self-review complete
- [ ] 28.2 Architect (User) approval
- [ ] 28.3 Lead Auditor (Gemini) approval
- [ ] 28.4 Ready to archive OpenSpec change

---

## Rollback Plan (Both Components)

**If ANY step fails BEFORE commit**:
1. `git reset --hard HEAD` (discard uncommitted changes)
2. Restore backups:
   - Copy `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schema.py.backup` to `schema.py`
   - Copy `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\__init__.py.backup` to `__init__.py`
3. Delete new directories:
   - Delete `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\schemas\`
   - Delete `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestration\`
4. Investigate failure, fix, retry from Section 1

**If commit succeeds but tests fail later**:
1. `git revert <commit_hash>` (atomic rollback of BOTH schema + orchestrator)
2. Investigate failure
3. Create new proposal with lessons learned

---

## Checklist Summary

**Schema Component (Sections 1-8)**:
- [ ] **Section 0**: Verification (10/12 complete, awaiting approval)
- [ ] **Section 1**: Directory Setup - Schema (0/3 complete)
- [ ] **Section 2**: Extract Utilities (0/7 complete)
- [ ] **Section 3**: Core Schema (0/35 complete)
- [ ] **Section 4**: Python Schema (0/10 complete)
- [ ] **Section 5**: Node Schema (0/27 complete)
- [ ] **Section 6**: Infrastructure Schema (0/17 complete)
- [ ] **Section 7**: Planning Schema (0/10 complete)
- [ ] **Section 8**: Stub Creation - Schema (0/7 complete)

**Orchestrator Component (Sections 9-15)**:
- [ ] **Section 9**: Directory Setup - Orchestrator (0/3 complete)
- [ ] **Section 10**: Core Orchestrator (0/11 complete)
- [ ] **Section 11**: Python Orchestrator (0/7 complete)
- [ ] **Section 12**: Node Orchestrator (0/11 complete - CRITICAL: JSX dual-pass)
- [ ] **Section 13**: Rust Orchestrator (0/6 complete)
- [ ] **Section 14**: Infrastructure Orchestrator (0/6 complete)
- [ ] **Section 15**: Merge Orchestrators & Stub (0/9 complete)

**Combined Validation & Commit (Sections 16-28)**:
- [ ] **Section 16**: Schema Validation Tests (0/5 complete)
- [ ] **Section 17**: Orchestrator Validation Tests (0/5 complete - CRITICAL: JSX)
- [ ] **Section 18**: Combined Consumer Smoke Tests (0/6 complete)
- [ ] **Section 19**: Schema Contract Tests (0/4 complete)
- [ ] **Section 20**: Full Test Suite (0/3 complete)
- [ ] **Section 21**: Integration Tests (0/6 complete - CRITICAL: Both components)
- [ ] **Section 22**: Diff Verification (0/7 complete)
- [ ] **Section 23**: Final Pre-Commit Validation (0/7 complete - CRITICAL: JSX verification)
- [ ] **Section 24**: Commit (0/5 complete - Single atomic commit)
- [ ] **Section 25**: Post-Commit Validation (0/9 complete - CRITICAL: JSX test)
- [ ] **Section 26**: Cleanup (0/5 complete)
- [ ] **Section 27**: Documentation (0/5 complete)
- [ ] **Section 28**: Final Sign-Off (0/4 complete)

**Total Progress**: 10/248 tasks complete (4.0%)

**Estimated Time**: 8-10 hours (Schema: 4-6h + Orchestrator: 4-5h, excluding approval wait time)

---

**Created By**: Claude Opus (Lead Coder)
**Date**: 2025-10-30
**Status**: READY FOR APPROVAL
