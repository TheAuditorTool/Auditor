# Implementation Tasks: Schema Language Split Refactor

**Change ID**: `refactor-schema-language-split`
**Status**: Pending Approval
**Estimated Time**: 4-6 hours

## 0. Verification (Pre-Implementation)

- [x] 0.1 Read entire schema.py and map all tables
- [x] 0.2 Identify all consumers (50 files)
- [x] 0.3 Categorize all 70 tables by language
- [x] 0.4 Create verification.md with comprehensive mapping
- [x] 0.5 Create proposal.md
- [x] 0.6 Create design.md
- [x] 0.7 Create tasks.md (this file)
- [ ] 0.8 Architect approval on verification.md
- [ ] 0.9 Lead Auditor approval on design.md

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

## 9. Validation Tests (Critical - DO NOT SKIP)

- [ ] 9.1 Test table count: `python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == 70, f'Expected 70, got {len(TABLES)}'"`
- [ ] 9.2 Test all imports: `python -c "from theauditor.indexer.schema import TABLES, build_query, Column, TableSchema, ForeignKey, validate_all_tables, get_table_schema"`
- [ ] 9.3 Test query builder: `python -c "from theauditor.indexer.schema import build_query; q = build_query('symbols', ['name', 'type']); assert 'SELECT name, type FROM symbols' in q"`
- [ ] 9.4 Test no duplicate tables: `python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == len(set(TABLES.keys()))"`
- [ ] 9.5 Test all 70 tables present: `python -c "from theauditor.indexer.schema import TABLES; expected = ['files', 'config_files', 'refs', 'symbols', 'symbols_jsx', 'class_properties', 'env_var_usage', 'orm_relationships', 'api_endpoints', 'api_endpoint_controls', 'python_orm_models', 'python_orm_fields', 'python_routes', 'python_blueprints', 'python_validators', 'sql_objects', 'sql_queries', 'sql_query_tables', 'jwt_patterns', 'orm_queries', 'prisma_models', 'assignments', 'assignments_jsx', 'assignment_sources', 'assignment_sources_jsx', 'function_call_args', 'function_call_args_jsx', 'function_returns', 'function_returns_jsx', 'function_return_sources', 'function_return_sources_jsx', 'variable_usage', 'object_literals', 'cfg_blocks', 'cfg_edges', 'cfg_block_statements', 'react_components', 'react_component_hooks', 'react_hooks', 'react_hook_dependencies', 'vue_components', 'vue_hooks', 'vue_directives', 'vue_provide_inject', 'type_annotations', 'docker_images', 'compose_services', 'nginx_configs', 'terraform_files', 'terraform_resources', 'terraform_variables', 'terraform_variable_values', 'terraform_outputs', 'terraform_findings', 'cdk_constructs', 'cdk_construct_properties', 'cdk_findings', 'package_configs', 'lock_analysis', 'import_styles', 'import_style_names', 'frameworks', 'framework_safe_sinks', 'validation_framework_usage', 'findings_consolidated', 'plans', 'plan_tasks', 'plan_specs', 'code_snapshots', 'code_diffs']; missing = set(expected) - set(TABLES.keys()); assert not missing, f'Missing tables: {missing}'"`

## 10. Consumer Import Smoke Tests

- [ ] 10.1 Test rule imports: `python -c "import theauditor.rules.auth.jwt_analyze"`
- [ ] 10.2 Test taint imports: `python -c "import theauditor.taint.core"`
- [ ] 10.3 Test command imports: `python -c "import theauditor.commands.index"`
- [ ] 10.4 Test planning imports: `python -c "import theauditor.planning.manager"`
- [ ] 10.5 Test extractor imports: `python -c "import theauditor.indexer.extractors.python"`
- [ ] 10.6 Test database imports: `python -c "from theauditor.indexer.database import DatabaseManager"`

## 11. Schema Contract Tests

- [ ] 11.1 Run schema contract tests: `pytest tests/test_schema_contract.py -v`
- [ ] 11.2 Run database integration tests: `pytest tests/test_database_integration.py -v`
- [ ] 11.3 Run JSX pass tests: `pytest tests/test_jsx_pass.py -v`
- [ ] 11.4 Run memory cache tests: `pytest tests/test_memory_cache.py -v`

## 12. Full Test Suite

- [ ] 12.1 Run full pytest suite: `pytest tests/ -v`
- [ ] 12.2 Verify 100% test pass rate
- [ ] 12.3 Fix any failures (DO NOT COMMIT if tests fail)

## 13. Integration Tests

- [ ] 13.1 Test aud index: `aud index tests/fixtures/test_project`
- [ ] 13.2 Verify indexing completes successfully
- [ ] 13.3 Test aud full: `aud full tests/fixtures/test_project`
- [ ] 13.4 Verify full analysis completes successfully
- [ ] 13.5 Compare output before/after (should be identical)

## 14. Diff Verification

- [ ] 14.1 Create merged schema from new modules: `python -c "from theauditor.indexer.schemas.core_schema import CORE_TABLES; from theauditor.indexer.schemas.python_schema import PYTHON_TABLES; from theauditor.indexer.schemas.node_schema import NODE_TABLES; from theauditor.indexer.schemas.infrastructure_schema import INFRASTRUCTURE_TABLES; from theauditor.indexer.schemas.planning_schema import PLANNING_TABLES; merged = {**CORE_TABLES, **PYTHON_TABLES, **NODE_TABLES, **INFRASTRUCTURE_TABLES, **PLANNING_TABLES}; import json; print(json.dumps({k: str(v) for k, v in merged.items()}, indent=2))" > /tmp/merged_tables.json`
- [ ] 14.2 Create original schema dump: `python -c "import sys; sys.path.insert(0, '.'); exec(open('schema.py.backup').read()); import json; print(json.dumps({k: str(v) for k, v in TABLES.items()}, indent=2))" > /tmp/original_tables.json`
- [ ] 14.3 Compare: `diff /tmp/original_tables.json /tmp/merged_tables.json`
- [ ] 14.4 Verify NO differences (except whitespace/formatting)

## 15. Final Validation

- [ ] 15.1 Re-run all tests one final time: `pytest tests/ -v`
- [ ] 15.2 Re-run integration tests: `aud index && aud full`
- [ ] 15.3 Verify backup exists: `ls -la schema.py.backup`
- [ ] 15.4 Verify all 7 new files exist: `ls -la theauditor/indexer/schemas/`
- [ ] 15.5 Code review: Read through ALL new files for typos
- [ ] 15.6 Documentation review: Verify all docstrings copied correctly

## 16. Commit

- [ ] 16.1 Stage all changes: `git add theauditor/indexer/schema.py theauditor/indexer/schemas/`
- [ ] 16.2 Verify staged changes: `git diff --cached`
- [ ] 16.3 Create atomic commit: `git commit -m "refactor(schema): Split schema.py into language-specific modules\n\nBREAKING: None (100% backward compatible via stub pattern)\n\nChanges:\n- Split schema.py (2146 lines) into 6 language-specific modules\n- Created schemas/ subpackage with utils, core, python, node, infrastructure, planning\n- Replaced schema.py with stub that merges all TABLES registries\n- All 70 tables preserved, all imports work identically\n- All 50 consumers unchanged (zero breaking changes)\n\nValidation:\n- All 70 tables present and accessible\n- All tests pass (pytest tests/ -v)\n- All consumers import successfully\n- aud index/full produce identical output\n\nRollback: git revert this commit"`
- [ ] 16.4 DO NOT PUSH - wait for post-commit validation

## 17. Post-Commit Validation

- [ ] 17.1 Run full test suite again: `pytest tests/ -v`
- [ ] 17.2 Run integration tests again: `aud index && aud full`
- [ ] 17.3 Test import from clean Python shell: `python3 -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == 70"`
- [ ] 17.4 If ANY test fails → `git reset --hard HEAD~1` (rollback)
- [ ] 17.5 If all tests pass → PROCEED to Section 18

## 18. Cleanup

- [ ] 18.1 Delete backup: `rm schema.py.backup` (only after confirming all tests pass)
- [ ] 18.2 Update OpenSpec tasks.md: Mark all tasks as complete
- [ ] 18.3 Update OpenSpec proposal.md: Change status to "Implemented"
- [ ] 18.4 Create verification report in OpenSpec change directory

## 19. Documentation

- [ ] 19.1 Update CLAUDE.md if needed (reference new schemas/ directory)
- [ ] 19.2 No README updates needed (internal refactor, no user-facing changes)
- [ ] 19.3 No API docs updates needed (all imports identical)

## 20. Final Sign-Off

- [ ] 20.1 Lead Coder (Opus) self-review complete
- [ ] 20.2 Architect (User) approval
- [ ] 20.3 Lead Auditor (Gemini) approval
- [ ] 20.4 Ready to archive OpenSpec change

---

## Rollback Plan

**If ANY step fails**:
1. `git reset --hard HEAD` (discard uncommitted changes)
2. `cp schema.py.backup schema.py` (restore backup)
3. `rm -rf theauditor/indexer/schemas/` (delete new directory)
4. Investigate failure, fix, retry from Section 1

**If commit succeeds but tests fail later**:
1. `git revert <commit_hash>` (atomic rollback)
2. Investigate failure
3. Create new proposal with lessons learned

---

## Checklist Summary

- [ ] **Section 0**: Verification (8/9 complete, awaiting approval)
- [ ] **Section 1**: Directory Setup (0/3 complete)
- [ ] **Section 2**: Extract Utilities (0/7 complete)
- [ ] **Section 3**: Core Schema (0/35 complete)
- [ ] **Section 4**: Python Schema (0/10 complete)
- [ ] **Section 5**: Node Schema (0/27 complete)
- [ ] **Section 6**: Infrastructure Schema (0/17 complete)
- [ ] **Section 7**: Planning Schema (0/10 complete)
- [ ] **Section 8**: Stub Creation (0/7 complete)
- [ ] **Section 9**: Validation Tests (0/5 complete)
- [ ] **Section 10**: Consumer Smoke Tests (0/6 complete)
- [ ] **Section 11**: Schema Contract Tests (0/4 complete)
- [ ] **Section 12**: Full Test Suite (0/3 complete)
- [ ] **Section 13**: Integration Tests (0/5 complete)
- [ ] **Section 14**: Diff Verification (0/4 complete)
- [ ] **Section 15**: Final Validation (0/6 complete)
- [ ] **Section 16**: Commit (0/4 complete)
- [ ] **Section 17**: Post-Commit Validation (0/5 complete)
- [ ] **Section 18**: Cleanup (0/4 complete)
- [ ] **Section 19**: Documentation (0/3 complete)
- [ ] **Section 20**: Final Sign-Off (0/4 complete)

**Total Progress**: 8/174 tasks complete (4.6%)

**Estimated Time**: 4-6 hours (excluding approval wait time)

---

**Created By**: Claude Opus (Lead Coder)
**Date**: 2025-10-30
**Status**: READY FOR APPROVAL
