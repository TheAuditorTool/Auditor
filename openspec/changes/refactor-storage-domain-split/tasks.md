# Implementation Tasks: Storage Layer Domain Split

**Change ID**: `refactor-storage-domain-split`
**Total Tasks**: 94
**Estimated Time**: 3 hours
**Risk Level**: Low-Medium
**Rollback Strategy**: `git revert HEAD` (instant)

---

## Task Organization

- **✅ Pre-Implementation** (Tasks 0.1-0.10): 10 tasks - Setup & verification
- **🏗️ Phase 1: Setup** (Tasks 1.1-1.8): 8 tasks - Create base infrastructure
- **📦 Phase 2: Core Migration** (Tasks 2.1-2.13): 13 tasks - Extract 21 core handlers
- **🐍 Phase 3: Python Migration** (Tasks 3.1-3.13): 13 tasks - Extract 59 Python handlers
- **📘 Phase 4: Node Migration** (Tasks 4.1-4.11): 11 tasks - Extract 15 Node handlers
- **🏗️ Phase 5: Infrastructure Migration** (Tasks 5.1-5.10): 10 tasks - Extract 12 infrastructure handlers
- **🔗 Phase 6: Integration** (Tasks 6.1-6.13): 13 tasks - Wire everything together
- **✅ Phase 7: Validation** (Tasks 7.1-7.10): 10 tasks - Test & verify
- **📚 Phase 8: Documentation** (Tasks 8.1-8.6): 6 tasks - Update docs

---

## 0. Pre-Implementation Setup (CRITICAL - DO NOT SKIP)

### 0.1 Create baseline snapshot
- [x] Run `git status` and ensure clean working tree
- [x] Create baseline commit: `git commit --allow-empty -m "Baseline before storage refactor"`
- [x] Capture current line counts: `wc -l C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py > C:\Users\santa\Desktop\TheAuditor\tmp\baseline_lines.txt`

### 0.2 Create baseline database snapshot
- [ ] Run `aud index C:\Users\santa\Desktop\TheAuditor\tests\fixtures\python\ > C:\Users\santa\Desktop\TheAuditor\tmp\baseline_index.log`
- [ ] Capture table counts:
  ```bash
  sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM python_orm_models;" > C:\Users\santa\Desktop\TheAuditor\tmp\baseline_counts.txt
  sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM symbols;" >> C:\Users\santa\Desktop\TheAuditor\tmp\baseline_counts.txt
  sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM function_call_args;" >> C:\Users\santa\Desktop\TheAuditor\tmp\baseline_counts.txt
  sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM assignments;" >> C:\Users\santa\Desktop\TheAuditor\tmp\baseline_counts.txt
  ```

### 0.3 Verify handler count
- [x] Count handlers: `grep -E "def _store_" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py | wc -l` → Should be 107
- [x] List all handlers: `grep -E "def _store_" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py > C:\Users\santa\Desktop\TheAuditor\tmp\handler_list.txt`

### 0.4 Document current imports
- [ ] Extract imports from storage.py: `head -20 C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py > C:\Users\santa\Desktop\TheAuditor\tmp\baseline_imports.txt`

### 0.5 Document orchestrator integration
- [ ] Find DataStorer usage: `grep -n "DataStorer" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py > C:\Users\santa\Desktop\TheAuditor\tmp\orchestrator_integration.txt`
- [ ] Verify single import location: `grep -r "from.*storage import DataStorer" C:\Users\santa\Desktop\TheAuditor\theauditor\ --include="*.py"`

### 0.6 Check for external handler references (CRITICAL)
- [ ] Search for direct handler calls: `grep -r "\._store_" C:\Users\santa\Desktop\TheAuditor\theauditor\ --include="*.py" | grep -v "storage.py"`
- [ ] **VERIFY**: Should return 0 results (only internal calls allowed)

### 0.7 Create test validation script
- [ ] Create `C:\Users\santa\Desktop\TheAuditor\tmp\validate_refactor.sh`:
  ```bash
  #!/bin/bash
  echo "=== Running validation ==="
  cd C:/Users/santa/Desktop/TheAuditor
  aud index C:/Users/santa/Desktop/TheAuditor/tests/fixtures/python/ > C:/Users/santa/Desktop/TheAuditor/tmp/after_index.log
  sqlite3 C:/Users/santa/Desktop/TheAuditor/.pf/repo_index.db "SELECT COUNT(*) FROM python_orm_models;" > C:/Users/santa/Desktop/TheAuditor/tmp/after_counts.txt
  sqlite3 C:/Users/santa/Desktop/TheAuditor/.pf/repo_index.db "SELECT COUNT(*) FROM symbols;" >> C:/Users/santa/Desktop/TheAuditor/tmp/after_counts.txt
  sqlite3 C:/Users/santa/Desktop/TheAuditor/.pf/repo_index.db "SELECT COUNT(*) FROM function_call_args;" >> C:/Users/santa/Desktop/TheAuditor/tmp/after_counts.txt
  sqlite3 C:/Users/santa/Desktop/TheAuditor/.pf/repo_index.db "SELECT COUNT(*) FROM assignments;" >> C:/Users/santa/Desktop/TheAuditor/tmp/after_counts.txt

  echo "=== Comparing counts ==="
  diff C:/Users/santa/Desktop/TheAuditor/tmp/baseline_counts.txt C:/Users/santa/Desktop/TheAuditor/tmp/after_counts.txt

  if [ $? -eq 0 ]; then
      echo "✅ VALIDATION PASSED - Counts identical"
  else
      echo "❌ VALIDATION FAILED - Counts differ"
      exit 1
  fi
  ```
- [ ] Make executable: `chmod +x C:\Users\santa\Desktop\TheAuditor\tmp\validate_refactor.sh`

### 0.8 Document risk areas
- [ ] List handlers that use `_current_extracted`: `grep -n "_current_extracted" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py`
  - Expected: `_store_imports` (line ~202)
- [ ] List handlers that use `jsx_pass`: `grep -n "if jsx_pass" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py`
  - Expected: `_store_symbols`, `_store_assignments`, `_store_function_calls`, `_store_returns`, `_store_cfg`

### 0.9 Create rollback script
- [ ] Create `C:\Users\santa\Desktop\TheAuditor\tmp\rollback_refactor.sh`:
  ```bash
  #!/bin/bash
  echo "=== Rolling back storage refactor ==="
  cd C:/Users/santa/Desktop/TheAuditor
  git revert HEAD --no-edit
  echo "✅ Rollback complete"
  ```

### 0.10 Final pre-check
- [ ] Verify Python environment: `C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe --version` → Should be 3.11+
- [ ] Verify TheAuditor installs: `aud --version` → Should work
- [ ] **CHECKPOINT**: All pre-implementation tasks complete? If NO, STOP and resolve issues.

---

## 1. Phase 1: Setup (Create Base Infrastructure)

### 1.1 Create storage directory
- [ ] Create directory: `mkdir C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage`
- [ ] Verify: `ls -la C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage` → Should exist

### 1.2 Create base.py module
- [ ] Create file: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\base.py`
- [ ] Add module docstring (from design.md section 4.1.2)
- [ ] Add imports:
  ```python
  from typing import Dict, Any
  ```

### 1.3 Implement BaseStorage class
- [ ] Add `class BaseStorage:` definition
- [ ] Add `__init__(self, db_manager, counts: Dict[str, int])` method
- [ ] Initialize `self.db_manager = db_manager`
- [ ] Initialize `self.counts = counts`
- [ ] Initialize `self._current_extracted = {}`

### 1.4 Add debug helper to BaseStorage
- [ ] Add `_debug(self, message: str)` method:
  ```python
  def _debug(self, message: str):
      import os
      if os.environ.get("THEAUDITOR_DEBUG"):
          print(f"[DEBUG STORAGE] {message}")
  ```

### 1.5 Test BaseStorage independently
- [ ] Create test file: `C:\Users\santa\Desktop\TheAuditor\tmp\test_base_storage.py`:
  ```python
  import sys
  sys.path.insert(0, "C:/Users/santa/Desktop/TheAuditor")
  from theauditor.indexer.storage.base import BaseStorage

  class MockDB:
      pass

  base = BaseStorage(MockDB(), {})
  assert hasattr(base, 'db_manager')
  assert hasattr(base, 'counts')
  assert hasattr(base, '_current_extracted')
  print("✅ BaseStorage works")
  ```
- [ ] Run test: `C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe C:\Users\santa\Desktop\TheAuditor\tmp\test_base_storage.py`
- [ ] **VERIFY**: Should print "✅ BaseStorage works"

### 1.6 Add base.py to git
- [ ] Stage: `git add C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\base.py`
- [ ] Verify: `git status` → Should show new file

### 1.7 Document base.py
- [ ] Add inline comments explaining BaseStorage purpose
- [ ] Add type hints to all methods

### 1.8 Phase 1 checkpoint
- [ ] **VERIFY**: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\` exists
- [ ] **VERIFY**: `base.py` can be imported without errors
- [ ] **CHECKPOINT**: Phase 1 complete? If NO, debug before proceeding.

---

## 2. Phase 2: Core Migration (21 Handlers)

### 2.1 Create core_storage.py file
- [ ] Create file: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py`
- [ ] Add module docstring (from design.md section 4.1.3)

### 2.2 Add core imports
- [ ] Copy imports from storage.py lines 9-15:
  ```python
  import json
  import os
  import sys
  import logging
  from pathlib import Path
  from typing import Dict, Any, List
  ```
- [ ] Add: `from .base import BaseStorage`

### 2.3 Create CoreStorage class skeleton
- [ ] Add `class CoreStorage(BaseStorage):` definition
- [ ] Add docstring: "Core storage handlers for language-agnostic patterns."
- [ ] Add `__init__(self, db_manager, counts):` method
- [ ] Call `super().__init__(db_manager, counts)`

### 2.4 Copy handler: _store_imports
- [ ] Copy method from storage.py:191-206 to core_storage.py
- [ ] **VERIFY**: Method signature matches: `def _store_imports(self, file_path: str, imports: List, jsx_pass: bool):`
- [ ] **VERIFY**: Uses `self.db_manager`, `self.counts`, `self._current_extracted`

### 2.5 Copy handler: _store_routes
- [ ] Copy method from storage.py:208-226
- [ ] **VERIFY**: Method signature correct

### 2.6 Copy handler: _store_sql_objects
- [ ] Copy method from storage.py:227-231

### 2.7 Copy handler: _store_sql_queries
- [ ] Copy method from storage.py:233-241

### 2.8 Copy handler: _store_cdk_constructs
- [ ] Copy method from storage.py:243-274

### 2.9 Copy remaining core handlers (batch 1 of 3)
- [ ] _store_symbols (storage.py:276-299)
- [ ] _store_type_annotations (storage.py:300-337)
- [ ] _store_orm_queries (storage.py:338-346)
- [ ] _store_validation_framework_usage (storage.py:348-366)
- [ ] _store_assignments (storage.py:367-390)

### 2.10 Copy remaining core handlers (batch 2 of 3)
- [ ] _store_function_calls (storage.py:392-456)
- [ ] _store_returns (storage.py:458-476)
- [ ] _store_cfg (storage.py:478-552)
- [ ] _store_jwt_patterns (storage.py:554-565)
- [ ] _store_react_components (storage.py:567-580)

### 2.11 Copy remaining core handlers (batch 3 of 3)
- [ ] _store_class_properties (storage.py:582-603)
- [ ] _store_env_var_usage (storage.py:605-620)
- [ ] _store_orm_relationships (storage.py:622-639)
- [ ] _store_variable_usage (storage.py:1663-1675)
- [ ] _store_object_literals (storage.py:1677-1690)
- [ ] _store_package_configs (storage.py:1692-1707)

### 2.12 Create core handler registry
- [ ] Add handler registry to `__init__` method:
  ```python
  self.handlers = {
      'imports': self._store_imports,
      'routes': self._store_routes,
      'sql_objects': self._store_sql_objects,
      # ... (all 21 handlers)
  }
  ```
- [ ] **VERIFY**: Registry has exactly 21 entries
- [ ] Count: `grep -E "'.+':" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py | wc -l` → Should be 21

### 2.13 Test CoreStorage independently
- [ ] Create test: `C:\Users\santa\Desktop\TheAuditor\tmp\test_core_storage.py`:
  ```python
  import sys
  sys.path.insert(0, "C:/Users/santa/Desktop/TheAuditor")
  from theauditor.indexer.storage.core_storage import CoreStorage

  class MockDB:
      def add_ref(self, *args): pass
      def add_symbol(self, *args): pass
      # ... (add all db_manager methods used by core handlers)

  core = CoreStorage(MockDB(), {})
  assert len(core.handlers) == 21, f"Expected 21 handlers, got {len(core.handlers)}"
  assert 'imports' in core.handlers
  assert 'symbols' in core.handlers
  assert 'cfg' in core.handlers
  print(f"✅ CoreStorage has {len(core.handlers)} handlers")
  ```
- [ ] Run test: `C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe C:\Users\santa\Desktop\TheAuditor\tmp\test_core_storage.py`
- [ ] **VERIFY**: Should print "✅ CoreStorage has 21 handlers"

---

## 3. Phase 3: Python Migration (59 Handlers)

### 3.1 Create python_storage.py file
- [ ] Create file: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\python_storage.py`
- [ ] Add module docstring (from design.md section 4.1.4)
- [ ] Add imports: `import json`, `from typing import List`, `from .base import BaseStorage`

### 3.2 Create PythonStorage class skeleton
- [ ] Add `class PythonStorage(BaseStorage):` definition
- [ ] Add `__init__(self, db_manager, counts):` with `super().__init__()`

### 3.3 Copy ORM & Routes handlers (6 handlers)
- [ ] _store_python_orm_models (storage.py:641-653)
- [ ] _store_python_orm_fields (storage.py:655-670)
- [ ] _store_python_routes (storage.py:672-688)
- [ ] _store_python_blueprints (storage.py:690-702)
- [ ] _store_python_django_views (storage.py:704-721)
- [ ] _store_python_django_forms (storage.py:723-737)

### 3.4 Copy Django Framework handlers (8 handlers)
- [ ] _store_python_django_form_fields (storage.py:739-754)
- [ ] _store_python_django_admin (storage.py:756-772)
- [ ] _store_python_django_middleware (storage.py:774-789)
- [ ] _store_python_django_signals (storage.py:1273-1287)
- [ ] _store_python_django_receivers (storage.py:1289-1302)
- [ ] _store_python_django_managers (storage.py:1304-1317)
- [ ] _store_python_django_querysets (storage.py:1319-1333)

### 3.5 Copy Validation Framework handlers (6 handlers)
- [ ] _store_python_marshmallow_schemas (storage.py:791-804)
- [ ] _store_python_marshmallow_fields (storage.py:806-822)
- [ ] _store_python_drf_serializers (storage.py:824-839)
- [ ] _store_python_drf_serializer_fields (storage.py:841-859)
- [ ] _store_python_wtforms_forms (storage.py:861-873)
- [ ] _store_python_wtforms_fields (storage.py:875-889)

### 3.6 Copy Celery & Async handlers (7 handlers)
- [ ] _store_python_celery_tasks (storage.py:891-909)
- [ ] _store_python_celery_task_calls (storage.py:911-927)
- [ ] _store_python_celery_beat_schedules (storage.py:929-944)
- [ ] _store_python_generators (storage.py:946-961)
- [ ] _store_python_async_functions (storage.py:1382-1396)
- [ ] _store_python_await_expressions (storage.py:1398-1409)
- [ ] _store_python_async_generators (storage.py:1411-1428)

### 3.7 Copy Flask Framework handlers (9 handlers - Phase 3.1)
- [ ] _store_python_flask_apps (storage.py:965-978)
- [ ] _store_python_flask_extensions (storage.py:980-992)
- [ ] _store_python_flask_hooks (storage.py:994-1006)
- [ ] _store_python_flask_error_handlers (storage.py:1008-1020)
- [ ] _store_python_flask_websockets (storage.py:1022-1034)
- [ ] _store_python_flask_cli_commands (storage.py:1036-1048)
- [ ] _store_python_flask_cors (storage.py:1050-1062)
- [ ] _store_python_flask_rate_limits (storage.py:1064-1075)
- [ ] _store_python_flask_cache (storage.py:1077-1089)

### 3.8 Copy Testing Ecosystem handlers (8 handlers - Phase 3.2)
- [ ] _store_python_unittest_test_cases (storage.py:1093-1108)
- [ ] _store_python_assertion_patterns (storage.py:1110-1123)
- [ ] _store_python_pytest_plugin_hooks (storage.py:1125-1136)
- [ ] _store_python_hypothesis_strategies (storage.py:1138-1150)
- [ ] _store_python_pytest_fixtures (storage.py:1430-1443)
- [ ] _store_python_pytest_parametrize (storage.py:1445-1461)
- [ ] _store_python_pytest_markers (storage.py:1463-1479)
- [ ] _store_python_mock_patterns (storage.py:1481-1494)

### 3.9 Copy Security Patterns handlers (8 handlers - Phase 3.3)
- [ ] _store_python_auth_decorators (storage.py:1154-1166)
- [ ] _store_python_password_hashing (storage.py:1168-1181)
- [ ] _store_python_jwt_operations (storage.py:1183-1196)
- [ ] _store_python_sql_injection (storage.py:1198-1210)
- [ ] _store_python_command_injection (storage.py:1212-1224)
- [ ] _store_python_path_traversal (storage.py:1226-1238)
- [ ] _store_python_dangerous_eval (storage.py:1240-1252)
- [ ] _store_python_crypto_operations (storage.py:1254-1267)

### 3.10 Copy Type System handlers (7 handlers - Phase 3.4)
- [ ] _store_python_validators (storage.py:1335-1348)
- [ ] _store_python_decorators (storage.py:1350-1364)
- [ ] _store_python_context_managers (storage.py:1366-1380)
- [ ] _store_python_protocols (storage.py:1496-1512)
- [ ] _store_python_generics (storage.py:1514-1529)
- [ ] _store_python_typed_dicts (storage.py:1531-1546)
- [ ] _store_python_literals (storage.py:1548-1562)
- [ ] _store_python_overloads (storage.py:1564-1579)

### 3.11 Create Python handler registry
- [ ] Add handler registry to `__init__` method with all 59 entries
- [ ] **VERIFY**: Count `grep -E "'.+':" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\python_storage.py | wc -l` → Should be 59

### 3.12 Test PythonStorage independently
- [ ] Create test: `C:\Users\santa\Desktop\TheAuditor\tmp\test_python_storage.py`
- [ ] Verify 59 handlers: `assert len(python.handlers) == 59`
- [ ] Test key handlers exist: `'python_orm_models'`, `'python_flask_apps'`, `'python_pytest_fixtures'`
- [ ] **VERIFY**: Test passes

### 3.13 Phase 3 checkpoint
- [ ] **VERIFY**: `python_storage.py` has 59 handlers
- [ ] **VERIFY**: File size ~1,180 lines: `wc -l C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\python_storage.py`
- [ ] **CHECKPOINT**: Phase 3 complete?

---

## 4. Phase 4: Node Migration (15 Handlers)

### 4.1 Create node_storage.py file
- [ ] Create file: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\node_storage.py`
- [ ] Add module docstring (from design.md section 4.1.5)
- [ ] Add imports

### 4.2 Create NodeStorage class skeleton
- [ ] Add `class NodeStorage(BaseStorage):` definition
- [ ] Add `__init__` with `super().__init__()`

### 4.3 Copy React handlers (1 handler - react_components moved to core)
- [ ] _store_react_hooks (storage.py:1581-1595)

### 4.4 Copy Vue handlers (4 handlers)
- [ ] _store_vue_components (storage.py:1597-1615)
- [ ] _store_vue_hooks (storage.py:1617-1632)
- [ ] _store_vue_directives (storage.py:1634-1648)
- [ ] _store_vue_provide_inject (storage.py:1650-1661)

### 4.5 Copy Angular handlers (5 handlers)
- [ ] _store_angular_components (storage.py:2030-2049)
- [ ] _store_angular_services (storage.py:2051-2068)
- [ ] _store_angular_modules (storage.py:2070-2089)
- [ ] _store_angular_guards (storage.py:2091-2108)
- [ ] _store_di_injections (storage.py:2110-2127)

### 4.6 Copy Sequelize ORM handlers (2 handlers)
- [ ] _store_sequelize_models (storage.py:1938-1962)
- [ ] _store_sequelize_associations (storage.py:1964-1983)

### 4.7 Copy BullMQ handlers (2 handlers)
- [ ] _store_bullmq_queues (storage.py:1989-2005)
- [ ] _store_bullmq_workers (storage.py:2007-2024)

### 4.8 Copy Build System handlers (3 handlers - moved from core)
- [ ] _store_import_styles (storage.py:1724-1738)
- [ ] _store_lock_analysis (storage.py:1709-1722)
- [ ] **NOTE**: package_configs stays in core (multi-language)

### 4.9 Create Node handler registry
- [ ] Add handler registry with all 15 entries
- [ ] **VERIFY**: Count → Should be 15

### 4.10 Test NodeStorage independently
- [ ] Create test: `C:\Users\santa\Desktop\TheAuditor\tmp\test_node_storage.py`
- [ ] Verify 15 handlers
- [ ] **VERIFY**: Test passes

### 4.11 Phase 4 checkpoint
- [ ] **VERIFY**: `node_storage.py` has 15 handlers
- [ ] **VERIFY**: File size ~300 lines
- [ ] **CHECKPOINT**: Phase 4 complete?

---

## 5. Phase 5: Infrastructure Migration (12 Handlers)

### 5.1 Create infrastructure_storage.py file
- [ ] Create file: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\infrastructure_storage.py`
- [ ] Add module docstring (from design.md section 4.1.6)
- [ ] Add imports including `import json`

### 5.2 Create InfrastructureStorage class skeleton
- [ ] Add `class InfrastructureStorage(BaseStorage):` definition
- [ ] Add `__init__` with `super().__init__()`

### 5.3 Copy Terraform handlers (5 handlers)
- [ ] _store_terraform_file (storage.py:1740-1753)
- [ ] _store_terraform_resources (storage.py:1755-1772)
- [ ] _store_terraform_variables (storage.py:1774-1790)
- [ ] _store_terraform_variable_values (storage.py:1792-1812)
- [ ] _store_terraform_outputs (storage.py:1814-1828)

### 5.4 Copy GraphQL handlers (6 handlers)
- [ ] _store_graphql_schemas (storage.py:1834-1845)
- [ ] _store_graphql_types (storage.py:1847-1868)
- [ ] _store_graphql_fields (storage.py:1870-1885)
- [ ] _store_graphql_field_args (storage.py:1887-1901)
- [ ] _store_graphql_resolver_mappings (storage.py:1903-1917)
- [ ] _store_graphql_resolver_params (storage.py:1919-1932)

### 5.5 Note about CDK constructs
- [ ] **NOTE**: _store_cdk_constructs stays in core_storage.py (cross-language AWS detection)
- [ ] Add comment in infrastructure_storage.py docstring explaining this decision

### 5.6 Create Infrastructure handler registry
- [ ] Add handler registry with 11 entries (Terraform + GraphQL, no CDK)
- [ ] **VERIFY**: Count → Should be 11

### 5.7 Test InfrastructureStorage independently
- [ ] Create test: `C:\Users\santa\Desktop\TheAuditor\tmp\test_infrastructure_storage.py`
- [ ] Verify 11 handlers
- [ ] Test key handlers: `'terraform_file'`, `'graphql_schemas'`
- [ ] **VERIFY**: Test passes

### 5.8 Phase 5 checkpoint
- [ ] **VERIFY**: `infrastructure_storage.py` has 11 handlers (not 12 - CDK in core)
- [ ] **VERIFY**: File size ~360 lines
- [ ] **CHECKPOINT**: Phase 5 complete?

### 5.9 Cross-verify handler distribution
- [ ] Count core handlers: `grep -c "def _store_" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\core_storage.py` → 22 (21 + cdk_constructs)
- [ ] Count Python handlers: `grep -c "def _store_" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\python_storage.py` → 59
- [ ] Count Node handlers: `grep -c "def _store_" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\node_storage.py` → 15
- [ ] Count Infrastructure handlers: `grep -c "def _store_" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\infrastructure_storage.py` → 11
- [ ] **TOTAL**: 22 + 59 + 15 + 11 = 107 ✅

### 5.10 Verify no handlers left in original storage.py
- [ ] **CRITICAL**: Check storage.py has been fully migrated (no `def _store_` should remain)
- [ ] Search: `grep "def _store_" C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py` → Should be 0 results

---

## 6. Phase 6: Integration (Wire Everything Together)

### 6.1 Create storage/__init__.py file
- [ ] Create file: `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\__init__.py`
- [ ] Add comprehensive module docstring (from design.md section 4.1.1)

### 6.2 Add imports to __init__.py
- [ ] Import domain modules:
  ```python
  from .base import BaseStorage
  from .core_storage import CoreStorage
  from .python_storage import PythonStorage
  from .node_storage import NodeStorage
  from .infrastructure_storage import InfrastructureStorage
  ```

### 6.3 Add missing imports to __init__.py
- [ ] Add `import os` (for THEAUDITOR_DEBUG check)
- [ ] Add type hints: `from typing import Dict, Any`

### 6.4 Create DataStorer class in __init__.py
- [ ] Add `class DataStorer:` definition
- [ ] Add class docstring: "Main storage orchestrator - aggregates domain-specific handlers."

### 6.5 Implement DataStorer.__init__
- [ ] Add `__init__(self, db_manager, counts)` method
- [ ] Store `self.db_manager = db_manager`
- [ ] Store `self.counts = counts`
- [ ] Instantiate domain modules:
  ```python
  self.core = CoreStorage(db_manager, counts)
  self.python = PythonStorage(db_manager, counts)
  self.node = NodeStorage(db_manager, counts)
  self.infrastructure = InfrastructureStorage(db_manager, counts)
  ```

### 6.6 Aggregate handler registries
- [ ] Create unified registry:
  ```python
  self.handlers = {
      **self.core.handlers,
      **self.python.handlers,
      **self.node.handlers,
      **self.infrastructure.handlers,
  }
  ```
- [ ] **VERIFY**: No duplicate keys (dict merge will silently overwrite)

### 6.7 Implement DataStorer.store method
- [ ] Copy method signature from old storage.py:159: `def store(self, file_path: str, extracted: Dict[str, Any], jsx_pass: bool = False):`
- [ ] Store `self._current_extracted = extracted`
- [ ] Propagate to domain modules:
  ```python
  self.core._current_extracted = extracted
  self.python._current_extracted = extracted
  self.node._current_extracted = extracted
  self.infrastructure._current_extracted = extracted
  ```

### 6.8 Implement JSX pass filtering in store()
- [ ] Copy JSX filtering logic from old storage.py:172-177
- [ ] Define `jsx_only_types = {'symbols', 'assignments', 'function_calls', 'returns', 'cfg'}`
- [ ] Add filtering in loop:
  ```python
  for data_type, data in extracted.items():
      if jsx_pass and data_type not in jsx_only_types:
          continue
  ```

### 6.9 Implement handler dispatch in store()
- [ ] Copy dispatch logic from old storage.py:179-186:
  ```python
  handler = self.handlers.get(data_type)
  if handler:
      handler(file_path, data, jsx_pass)
  else:
      if os.environ.get("THEAUDITOR_DEBUG"):
          print(f"[DEBUG] No handler for data type: {data_type}")
  ```

### 6.10 Add __all__ export to __init__.py
- [ ] Add: `__all__ = ["DataStorer"]`
- [ ] **NOTE**: BaseStorage and domain modules are private (not exported)

### 6.11 Test DataStorer aggregation
- [ ] Create test: `C:\Users\santa\Desktop\TheAuditor\tmp\test_datastorer.py`:
  ```python
  import sys
  sys.path.insert(0, "C:/Users/santa/Desktop/TheAuditor")
  from theauditor.indexer.storage import DataStorer

  class MockDB:
      pass

  storer = DataStorer(MockDB(), {})
  assert len(storer.handlers) == 107, f"Expected 107 handlers, got {len(storer.handlers)}"
  assert 'symbols' in storer.handlers  # Core
  assert 'python_orm_models' in storer.handlers  # Python
  assert 'react_hooks' in storer.handlers  # Node
  assert 'graphql_schemas' in storer.handlers  # Infrastructure
  print(f"✅ DataStorer aggregated {len(storer.handlers)} handlers")
  ```
- [ ] Run test: `C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe C:\Users\santa\Desktop\TheAuditor\tmp\test_datastorer.py`
- [ ] **VERIFY**: Should print "✅ DataStorer aggregated 107 handlers"

### 6.12 Verify no handler collisions
- [ ] Check for duplicate keys:
  ```python
  all_keys = (
      list(storer.core.handlers.keys()) +
      list(storer.python.handlers.keys()) +
      list(storer.node.handlers.keys()) +
      list(storer.infrastructure.handlers.keys())
  )
  assert len(all_keys) == len(set(all_keys)), "Duplicate handler keys detected!"
  ```
- [ ] **VERIFY**: No duplicates

### 6.13 Phase 6 checkpoint
- [ ] **VERIFY**: `storage/__init__.py` exports DataStorer
- [ ] **VERIFY**: DataStorer aggregates 107 handlers
- [ ] **VERIFY**: No duplicate handler keys
- [ ] **CHECKPOINT**: Phase 6 complete?

---

## 7. Phase 7: Validation (Test & Verify)

### 7.1 Update orchestrator.py import (CRITICAL - BREAKING CHANGE)
- [ ] Open `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\orchestrator.py`
- [ ] Find import line: `from .storage import DataStorer` (should be around line 31)
- [ ] **VERIFY**: Import already correct (no change needed - storage is now a package)
- [ ] **NOTE**: Python treats `storage.py` file and `storage/` directory identically for imports
- [ ] Test import: `C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe -c "from theauditor.indexer.storage import DataStorer; print('✅ Import works')"`

### 7.2 Delete old storage.py file
- [ ] **CRITICAL DECISION POINT**: Backup first!
- [ ] Backup: `copy C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py C:\Users\santa\Desktop\TheAuditor\tmp\storage.py.backup`
- [ ] Delete: `rm C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py`
- [ ] **VERIFY**: `ls C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py` → Should not exist
- [ ] **VERIFY**: `ls C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\` → Should show directory with modules

### 7.3 Test import after deletion
- [ ] Test: `C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe -c "from theauditor.indexer.storage import DataStorer; print('✅ Import still works')"`
- [ ] **IF FAILS**: Restore backup and debug import path issue
- [ ] **IF SUCCEEDS**: Proceed to next task

### 7.4 Run basic index command
- [ ] Clear database: `rm -f C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db`
- [ ] Run indexer: `aud index C:\Users\santa\Desktop\TheAuditor\tests\fixtures\python\ --verbose > C:\Users\santa\Desktop\TheAuditor\tmp\after_index.log 2>&1`
- [ ] **VERIFY**: Command completes without errors
- [ ] Check log for handler errors: `grep -i "error\|exception\|traceback" C:\Users\santa\Desktop\TheAuditor\tmp\after_index.log`
- [ ] **IF ERRORS**: Debug handler implementation, restore backup if needed

### 7.5 Compare database row counts
- [ ] Run validation script: `bash C:\Users\santa\Desktop\TheAuditor\tmp\validate_refactor.sh`
- [ ] **VERIFY**: Output shows "✅ VALIDATION PASSED - Counts identical"
- [ ] **IF FAILS**: Compare counts manually:
  ```bash
  diff C:/Users/santa/Desktop/TheAuditor/tmp/baseline_counts.txt C:/Users/santa/Desktop/TheAuditor/tmp/after_counts.txt
  # Investigate discrepancies - likely missing handler or wrong db_manager method call
  ```

### 7.6 Test Python-specific handlers
- [ ] Query Python ORM models: `sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM python_orm_models;"`
- [ ] Query Python routes: `sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM python_routes;"`
- [ ] Query Python Flask apps: `sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM python_flask_apps;"`
- [ ] **VERIFY**: Counts > 0 (if test fixtures have Python code)

### 7.7 Test Node-specific handlers (if applicable)
- [ ] Run: `aud index C:\Users\santa\Desktop\TheAuditor\tests\fixtures\javascript\ --verbose` (if JavaScript fixtures exist)
- [ ] Query React hooks: `sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM react_hooks;"`
- [ ] Query Vue components: `sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM vue_components;"`

### 7.8 Test Infrastructure handlers (if applicable)
- [ ] Run: `aud index C:\Users\santa\Desktop\TheAuditor\tests\fixtures\terraform\ --verbose` (if Terraform fixtures exist)
- [ ] Query Terraform resources: `sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM terraform_resources;"`

### 7.9 Test JSX pass handlers
- [ ] Clear database: `rm -f C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db`
- [ ] Run indexer on React code (if available)
- [ ] Query JSX tables: `sqlite3 C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db "SELECT COUNT(*) FROM symbols_jsx;"`
- [ ] **VERIFY**: JSX tables populated correctly

### 7.10 Phase 7 checkpoint - FINAL VERIFICATION
- [ ] **VERIFY**: Old storage.py deleted
- [ ] **VERIFY**: `aud index` runs successfully
- [ ] **VERIFY**: Database row counts identical to baseline
- [ ] **VERIFY**: No errors in logs
- [ ] **VERIFY**: All 107 handlers executed at least once (check via counts dict)
- [ ] **CHECKPOINT**: Phase 7 complete? If ANY failures, rollback and debug.

---

## 8. Phase 8: Documentation (Update Docs)

### 8.1 Update CLAUDE.md
- [ ] Open `C:\Users\santa\Desktop\TheAuditor\CLAUDE.md`
- [ ] Find section on storage layer (search for "storage.py" or "DataStorer")
- [ ] Add subsection: "Storage Layer Architecture (v1.3.1 - Domain Split)"
- [ ] Document new structure:
  ```markdown
  ### Storage Layer Architecture

  `theauditor/indexer/storage/` (Domain Split Pattern)
  - `__init__.py` - DataStorer orchestrator (exports public API)
  - `base.py` - BaseStorage base class (shared logic)
  - `core_storage.py` - 21 language-agnostic handlers
  - `python_storage.py` - 59 Python framework handlers
  - `node_storage.py` - 15 JavaScript framework handlers
  - `infrastructure_storage.py` - 11 IaC & GraphQL handlers

  Total: 107 handlers organized by domain for maintainability.
  ```

### 8.2 Add storage layer example to CLAUDE.md
- [ ] Add code example showing usage:
  ```python
  # Orchestrator usage (unchanged)
  from theauditor.indexer.storage import DataStorer

  storer = DataStorer(db_manager, counts)
  storer.store(file_path, extracted, jsx_pass=False)
  ```

### 8.3 Update openspec/project.md
- [ ] Open `C:\Users\santa\Desktop\TheAuditor\openspec\project.md`
- [ ] Find "Indexer Package" section
- [ ] Update storage.py reference to storage/ directory
- [ ] Add note: "Storage layer follows domain split pattern (matching schema layer)"

### 8.4 Create storage/README.md (optional but recommended)
- [ ] Create `C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\README.md`
- [ ] Add quick reference guide

### 8.5 Update this OpenSpec change documentation
- [ ] Update `C:\Users\santa\Desktop\TheAuditor\openspec\changes\refactor-storage-domain-split\verification.md` with "Post-Implementation Audit" section
- [ ] Update `C:\Users\santa\Desktop\TheAuditor\openspec\changes\refactor-storage-domain-split\design.md` with "Implementation Status: ✅ COMPLETE"
- [ ] Update this tasks.md - mark all tasks as complete

### 8.6 Create migration notes for future developers
- [ ] Create `C:\Users\santa\Desktop\TheAuditor\openspec\changes\refactor-storage-domain-split\MIGRATION_NOTES.md`

---

## 9. Final Checklist (CRITICAL - DO NOT SKIP)

### 9.1 Pre-commit verification
- [ ] Run linter: `ruff check C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\ --fix`
- [ ] Run formatter: `ruff format C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\`
- [ ] Fix any linter errors

### 9.2 Verify file counts
- [ ] Count modules: `ls C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\*.py | wc -l` → Should be 5 (base, core, python, node, infrastructure)
- [ ] Count total lines: `wc -l C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\*.py` → Should be ~2,400 (with docstrings)

### 9.3 Verify handler counts
- [ ] Count core handlers: 22 (21 + cdk_constructs)
- [ ] Count Python handlers: 59
- [ ] Count Node handlers: 15
- [ ] Count Infrastructure handlers: 11
- [ ] **TOTAL**: 107 ✅

### 9.4 Verify no import errors
- [ ] Test all imports:
  ```bash
  C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe -c "
  from theauditor.indexer.storage import DataStorer
  from theauditor.indexer.storage.core_storage import CoreStorage
  from theauditor.indexer.storage.python_storage import PythonStorage
  from theauditor.indexer.storage.node_storage import NodeStorage
  from theauditor.indexer.storage.infrastructure_storage import InfrastructureStorage
  print('✅ All imports successful')
  "
  ```

### 9.5 Run full test suite (if exists)
- [ ] Run: `pytest C:\Users\santa\Desktop\TheAuditor\tests\ -v` (if tests exist)
- [ ] **VERIFY**: All tests pass
- [ ] **IF FAILS**: Debug and fix before committing

### 9.6 Run validation script one final time
- [ ] Run: `bash C:\Users\santa\Desktop\TheAuditor\tmp\validate_refactor.sh`
- [ ] **VERIFY**: "✅ VALIDATION PASSED - Counts identical"

### 9.7 Create git commit
- [ ] Stage all files:
  ```bash
  git add C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage\
  git rm C:\Users\santa\Desktop\TheAuditor\theauditor\indexer\storage.py
  ```
- [ ] Verify staged changes: `git status`
- [ ] Create commit:
  ```bash
  git commit -m "refactor(storage): split monolithic storage.py into domain modules

  Split 2,127-line storage.py into 5 focused modules following schema refactor pattern:
  - core_storage.py (22 handlers): Language-agnostic patterns
  - python_storage.py (59 handlers): Python frameworks (Django, Flask, pytest, etc.)
  - node_storage.py (15 handlers): JavaScript frameworks (React, Vue, Angular, etc.)
  - infrastructure_storage.py (11 handlers): Terraform, GraphQL
  - base.py: Shared BaseStorage class

  BREAKING: None - Import path and public API unchanged
  TESTING: All validation tests pass, database counts identical
  PATTERN: Matches schema refactor architecture (commit 5c71739)

  Closes: openspec/changes/refactor-storage-domain-split
  "
  ```

### 9.8 Verify commit
- [ ] Check commit: `git show HEAD --stat`
- [ ] **VERIFY**: Shows +~2,400 lines (new modules) and -2,127 lines (old storage.py)
- [ ] **VERIFY**: Net change is +~300 lines (docstrings, imports, structure)

### 9.9 Test from clean state
- [ ] Checkout clean working tree: `git stash` (if any uncommitted changes)
- [ ] Run indexer: `aud index C:\Users\santa\Desktop\TheAuditor\tests\fixtures\python\ --verbose`
- [ ] **VERIFY**: Works correctly

### 9.10 Archive OpenSpec change
- [ ] Run: `openspec validate refactor-storage-domain-split --strict`
- [ ] **VERIFY**: Validation passes
- [ ] Mark proposal as implemented in proposal.md

---

## Task Summary

**Total Tasks**: 94 (10 pre-implementation + 84 implementation)
**Estimated Time**: 3 hours
**Actual Time**: _______ (fill in after completion)

**Critical Tasks** (Must not be skipped):
- 0.2: Baseline database snapshot
- 0.6: Check for external handler references
- 2.13, 3.12, 4.10, 5.7: Independent module tests
- 6.11: DataStorer aggregation test
- 7.2: Delete old storage.py (BREAKING)
- 7.5: Validate database counts
- 9.7: Create git commit

**High-Risk Tasks** (Extra care required):
- 6.6: Handler registry aggregation (check for duplicates)
- 6.7-6.9: DataStorer.store() implementation (critical dispatch logic)
- 7.1: Orchestrator import (verify no changes needed)
- 7.4: First index run after refactor

---

**Implementation Status**: ⏳ **READY TO START**
**Approval Status**: ✅ **OpenSpec VALIDATED**

**Author**: Claude (Opus AI - Lead Coder)
**Date**: 2025-01-01
**Protocol**: OpenSpec + SOP v4.20
