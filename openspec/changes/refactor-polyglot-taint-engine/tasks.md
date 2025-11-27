## Phase 0: Pre-Flight Verification

- [ ] 0.1 Run `aud full --offline` and capture baseline metrics
  - Record: taint paths found, sources, sinks, sanitizers detected
  - Save output to `baseline_metrics.json` for comparison
- [ ] 0.2 Verify `sequelize_models` table has data (query count)
  - Command: `python -c "import sqlite3; c=sqlite3.connect('.pf/repo_index.db'); print(c.execute('SELECT COUNT(*) FROM sequelize_models').fetchone())"`
- [ ] 0.3 Verify `framework_safe_sinks` table structure exists
- [ ] 0.4 Verify `validation_framework_usage` table structure exists
- [ ] 0.5 Document current import tree for `orm_utils.py`
  - Expected: Only `graph/strategies/python_orm.py:19`

## Phase 1: Graph Foundation (Cleanup & Consolidation)

### 1.1 Relocate Intelligence to Strategies

- [ ] 1.1.1 Read `graph/strategies/python_orm.py` fully
  - Verify it contains ORM relationship expansion logic
  - Verify it queries `python_orm_models`, `python_orm_relationships`
  - Document which methods come from `orm_utils.py`

- [ ] 1.1.2 Inline `PythonOrmContext` into `python_orm.py`
  - Remove import at line 19: `from theauditor.taint.orm_utils import PythonOrmContext`
  - Copy the following methods from `taint/orm_utils.py` into the strategy file:

  **Methods to copy (verified from orm_utils.py):**
  ```python
  class PythonOrmContext:
      """ORM context for Python (SQLAlchemy/Django) - inline into strategy."""

      def __init__(self, cursor: sqlite3.Cursor):
          self.cursor = cursor
          self.models: dict[str, dict] = {}      # model_name -> {file, line, table}
          self.relationships: dict[str, list] = {}  # model_name -> [relationships]
          self._load_models()
          self._load_relationships()

      def _load_models(self):
          """Load from python_orm_models table.
          Schema: python_orm_models(file, line, model_name, table_name, base_class)
          """
          self.cursor.execute("""
              SELECT file, line, model_name, table_name, base_class
              FROM python_orm_models
          """)
          for row in self.cursor.fetchall():
              self.models[row['model_name']] = {
                  'file': row['file'],
                  'line': row['line'],
                  'table': row['table_name'],
                  'base': row['base_class']
              }

      def _load_relationships(self):
          """Load from python_orm_relationships table.
          Schema: python_orm_relationships(file, line, model_name, rel_type, target_model, backref)
          """
          self.cursor.execute("""
              SELECT file, line, model_name, rel_type, target_model, backref
              FROM python_orm_relationships
          """)
          for row in self.cursor.fetchall():
              model = row['model_name']
              if model not in self.relationships:
                  self.relationships[model] = []
              self.relationships[model].append({
                  'type': row['rel_type'],
                  'target': row['target_model'],
                  'backref': row['backref']
              })

      def get_model_for_variable(self, file: str, func: str, var_name: str) -> str | None:
          """Check if variable name matches a known model."""
          # Direct model name match
          if var_name in self.models:
              return var_name
          # Lowercase match (user -> User)
          for model_name in self.models:
              if model_name.lower() == var_name.lower():
                  return model_name
          return None

      def get_relationships(self, model_name: str) -> list[dict]:
          """Get relationships for a model."""
          return self.relationships.get(model_name, [])
  ```

- [ ] 1.1.3 Create `graph/strategies/node_orm.py`
  ```python
  # File: graph/strategies/node_orm.py
  """Node.js ORM Strategy - Handles Sequelize/TypeORM/Prisma relationship edges.

  This strategy builds edges for ORM relationship expansion:
  - User.posts -> Post (hasMany)
  - Post.author -> User (belongsTo)
  - User.profile -> Profile (hasOne)

  Schema Reference (from indexer/schemas/node_schema.py):
    sequelize_associations(file, line, model_name, association_type, target_model, foreign_key, through_table)
    sequelize_models(file, line, model_name, table_name, extends_model)
    sequelize_model_fields(file, model_name, field_name, data_type, is_primary_key, ...)
  """
  import sqlite3
  from typing import Any
  from .base import GraphStrategy
  from ..dfg_builder import DFGEdge, create_bidirectional_edges

  class NodeOrmStrategy(GraphStrategy):
      name = "node_orm"

      def build(self, db_path: str, project_root: str) -> dict[str, Any]:
          conn = sqlite3.connect(db_path)
          conn.row_factory = sqlite3.Row
          cursor = conn.cursor()

          nodes = {}
          edges = []

          # Query Sequelize associations
          # Schema: sequelize_associations(file, line, model_name, association_type, target_model, foreign_key, through_table)
          cursor.execute("""
              SELECT file, line, model_name, association_type, target_model, foreign_key
              FROM sequelize_associations
          """)

          for row in cursor.fetchall():
              # association_type: 'hasMany', 'belongsTo', 'hasOne', 'belongsToMany'
              assoc_field = self._association_to_field_name(row['association_type'], row['target_model'])

              # Source: Model.association_field (e.g., User::posts)
              source_id = f"{row['file']}::{row['model_name']}::{assoc_field}"

              # Target: Target model instance
              target_id = f"{row['file']}::{row['target_model']}::instance"

              # Create bidirectional edges for ORM relationship
              new_edges = create_bidirectional_edges(
                  source=source_id,
                  target=target_id,
                  edge_type="orm_relationship",
                  file=row['file'],
                  line=row['line'],
                  expression=f"{row['model_name']}.{row['association_type']}({row['target_model']})",
                  function=row['model_name'],
                  metadata={
                      "association_type": row['association_type'],
                      "model": row['model_name'],  # For TypeResolver aliasing
                      "target_model": row['target_model'],
                      "foreign_key": row['foreign_key'],
                  }
              )
              edges.extend(new_edges)

          conn.close()
          return {"nodes": nodes, "edges": edges}

      def _association_to_field_name(self, assoc_type: str, target_model: str) -> str:
          """Convert association type to field name.

          hasMany(Post) -> posts (lowercase plural)
          belongsTo(User) -> user (lowercase singular)
          hasOne(Profile) -> profile (lowercase singular)
          """
          target_lower = target_model.lower()
          if assoc_type == 'hasMany':
              # Simple pluralization
              return f"{target_lower}s" if not target_lower.endswith('s') else target_lower
          return target_lower
  ```

- [ ] 1.1.4 Register `NodeOrmStrategy` in `dfg_builder.py`
  - Location: `graph/dfg_builder.py:53-57`
  - Add to strategies list after `PythonOrmStrategy`

- [ ] 1.1.5 Verify strategy execution order
  - Run `aud graph build` with debug output
  - Confirm: PythonOrm -> NodeOrm -> NodeExpress -> Interceptors

### 1.2 Purge the Taint Layer

- [ ] 1.2.1 **DELETE** `taint/orm_utils.py`
  - Verify no other imports exist (grep completed in verification)
  - Remove file entirely

- [ ] 1.2.2 Run `aud full --offline` to verify no import errors
- [ ] 1.2.3 Run `aud graph build` to verify edges still created

## Phase 2: Infrastructure (Traffic Laws & Identity)

### 2.1 Registry Upgrade (The "Traffic Laws")

- [ ] 2.1.1 Add database loading to `TaintRegistry` in `taint/core.py`
  - Location: After line 161 (end of current class)
  - Add method: `load_from_database(self, cursor: sqlite3.Cursor)`

- [ ] 2.1.2 Implement `_load_safe_sinks()` method
  ```python
  def _load_safe_sinks(self, cursor: sqlite3.Cursor):
      """Load safe sink patterns from framework_safe_sinks table.

      Schema (from indexer/schemas/node_schema.py:539-548):
          framework_safe_sinks(framework_id, sink_pattern, sink_type, is_safe, reason)

      Note: No 'language' column - JOIN with frameworks table to get language.
      """
      cursor.execute("""
          SELECT f.language, fss.sink_pattern, fss.sink_type
          FROM framework_safe_sinks fss
          JOIN frameworks f ON fss.framework_id = f.id
          WHERE fss.is_safe = 1
      """)
      for row in cursor.fetchall():
          lang = row['language'] or 'global'
          self.register_sanitizer(row['sink_pattern'], lang)
  ```

- [ ] 2.1.3 Implement `_load_validation_sanitizers()` method
  ```python
  def _load_validation_sanitizers(self, cursor: sqlite3.Cursor):
      """Load validation patterns from validation_framework_usage table."""
      cursor.execute("""
          SELECT DISTINCT framework, variable_name, file_path
          FROM validation_framework_usage
          WHERE is_validator = 1
      """)
      # Register each validation pattern
  ```

- [ ] 2.1.4 Implement `get_source_patterns(language: str)` method
  ```python
  def get_source_patterns(self, language: str) -> list[str]:
      """Get flattened list of source patterns for a language."""
      patterns = []
      lang_sources = self.sources.get(language, {})
      for category_patterns in lang_sources.values():
          patterns.extend(category_patterns)
      return patterns
  ```

- [ ] 2.1.5 Implement `get_sink_patterns(language: str)` method
  - Same structure as source patterns

- [ ] 2.1.6 Implement `get_sanitizer_patterns(language: str)` method
  - Returns both global and language-specific sanitizers

- [ ] 2.1.7 Seed default patterns for Python/Node/Rust
  - Add SQL migration or seed script
  - Python: `request.args`, `request.form`, `request.json`
  - JavaScript: `req.body`, `req.params`, `req.query`, `ctx.request.body`
  - Rust: `web::Json`, `web::Query`, `web::Path`

### 2.2 Type Resolver (The "Identity Card")

- [ ] 2.2.1 Create `taint/type_resolver.py`
  ```python
  """Polyglot Type Identity Checker.

  Answers: "Do these two variables represent the same Data Model?"
  Used for ORM aliasing when no direct graph edge exists.
  """

  import sqlite3

  class TypeResolver:
      def __init__(self, graph_cursor: sqlite3.Cursor):
          self.graph_cursor = graph_cursor
          self._model_cache: dict[str, str] = {}
          self._preload_models()

      def _preload_models(self):
          """Pre-load node metadata into memory for O(1) lookups."""
          # Query nodes table for metadata.model field

      def is_same_type(self, node_a_id: str, node_b_id: str) -> bool:
          """Check if two nodes represent the same model type."""

      def get_model_for_node(self, node_id: str) -> str | None:
          """Get model name for a node from metadata."""

      def is_controller_file(self, file_path: str) -> bool:
          """Check if file is a controller (any framework)."""
          # Query api_endpoints table for file_path
  ```

- [ ] 2.2.2 Add unit tests for TypeResolver
  - Test same model detection
  - Test different model detection
  - Test controller file detection

## Phase 3: Logic Refactor (Teaching the Driver)

### 3.1 Refactor Entry Points (`ifds_analyzer.py`)

- [ ] 3.1.1 Inject TaintRegistry into IFDSTaintAnalyzer
  - Modify `__init__` to accept registry parameter
  - Store as `self.registry`

- [ ] 3.1.2 Inject TypeResolver into IFDSTaintAnalyzer
  - Modify `__init__` to accept type_resolver parameter
  - Store as `self.type_resolver`

- [ ] 3.1.3 Refactor `_is_true_entry_point()` method
  - Location: `ifds_analyzer.py:~580-600`
  - Current (line 589):
    ```python
    request_patterns = ['req.body', 'req.params', 'req.query', 'req.headers', 'request.body', 'request.params']
    ```
  - Target:
    ```python
    # Detect language from file extension
    lang = self._get_language_for_file(file_path)
    request_patterns = self.registry.get_source_patterns(lang)
    ```

- [ ] 3.1.4 Refactor path/file convention checks
  - Location: `ifds_analyzer.py:592`
  - Current:
    ```python
    if 'routes' in file_path or 'middleware' in file_path or 'controller' in file_path:
    ```
  - Target:
    ```python
    if self._is_api_handler_file(file_path):
        # Query api_endpoints table
    ```

- [ ] 3.1.5 Add `_get_language_for_file()` helper
  ```python
  def _get_language_for_file(self, file_path: str) -> str:
      """Detect language from file extension."""
      if file_path.endswith(('.py',)):
          return 'python'
      elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
          return 'javascript'
      elif file_path.endswith(('.rs',)):
          return 'rust'
      return 'unknown'
  ```

### 3.2 Refactor Aliasing (`ifds_analyzer.py`)

- [ ] 3.2.1 Refactor `_access_paths_match()` controller check
  - Location: `ifds_analyzer.py:437`
  - Current:
    ```python
    'controller' in ap1.file.lower() and 'controller' in ap2.file.lower()
    ```
  - Target:
    ```python
    self.type_resolver.is_controller_file(ap1.file) and self.type_resolver.is_controller_file(ap2.file)
    ```

- [ ] 3.2.2 Add TypeResolver-based aliasing check
  - After existing checks, add:
    ```python
    # ORM Model Identity Check (Polyglot)
    if self.type_resolver.is_same_type(ap1_node_id, ap2_node_id):
        # Same model type - weak alias
        if ap1.base == ap2.base:
            return True
    ```

### 3.3 Refactor Sanitizers (`sanitizer_util.py`)

- [ ] 3.3.1 Remove DUPLICATE validation_patterns list
  - Location: `sanitizer_util.py:233-246`
  - This is a copy-paste of lines 199-221
  - DELETE the duplicate block

- [ ] 3.3.2 Inject TaintRegistry into SanitizerRegistry
  - Modify `__init__` signature:
    ```python
    def __init__(self, repo_cursor, taint_registry=None, debug=False):
    ```

- [ ] 3.3.3 Replace hardcoded patterns with registry lookup
  - Location: `sanitizer_util.py:199-221`
  - Current:
    ```python
    validation_patterns = [
        'validateBody', 'validateParams', ...
    ]
    ```
  - Target (ZERO FALLBACK - registry is MANDATORY):
    ```python
    # ZERO FALLBACK POLICY - TaintRegistry is MANDATORY
    # If registry is None, we CRASH - this is intentional
    if self.taint_registry is None:
        raise ValueError(
            "TaintRegistry is MANDATORY for SanitizerRegistry. "
            "Initialize with taint_registry parameter. NO FALLBACKS."
        )

    # Get language from file path
    lang = self._get_language_for_file(hop_file)
    validation_patterns = self.taint_registry.get_sanitizer_patterns(lang)
    ```

- [ ] 3.3.4 Add language detection to sanitizer check
  - Extract language from file path in hop
  - Use appropriate patterns for that language

### 3.4 Refactor Flow Resolver (`flow_resolver.py`)

- [ ] 3.4.1 Inject TaintRegistry into FlowResolver
  - Modify `__init__` to accept registry parameter

- [ ] 3.4.2 Refactor `_find_entry_points()` method
  - Location: `flow_resolver.py:151-163`
  - Current: Hardcoded Express middleware patterns
  - Target: Query registry for entry patterns by language

- [ ] 3.4.3 Refactor `_find_exit_points()` method
  - Location: `flow_resolver.py:334-350`
  - Current: Hardcoded `res.json()`, `res.send()` patterns
  - Target: Query registry for exit patterns by language

## Phase 4: Validation & Testing

- [ ] 4.1 Run `aud full --offline` and compare to baseline
  - Taint paths should be equal or greater (new language support)
  - No regressions in Express detection

- [ ] 4.2 Create integration test for Python project
  - Test Flask entry points detected
  - Test Django middleware handled

- [ ] 4.3 Create integration test for mixed project
  - Test both Python and Node.js files analyzed correctly

- [ ] 4.4 Run existing test suite
  - `pytest tests/ -v`
  - All tests must pass

- [ ] 4.5 Manual verification on PlantFlow codebase
  - Verify Express middleware chains detected
  - Verify Sequelize ORM relationships expanded
  - Verify taint flows cross ORM boundaries

## Phase 5: Documentation & Cleanup

- [ ] 5.1 Update CLAUDE.md with new architecture
  - Document TaintRegistry methods
  - Document TypeResolver usage
  - Update component diagram

- [ ] 5.2 Update Architecture.md
  - Add polyglot support section
  - Document database tables used

- [ ] 5.3 Remove any remaining Express-specific comments
  - Search for "Express" in taint/ directory
  - Update to be framework-agnostic

- [ ] 5.4 Archive this OpenSpec change
  - Run `openspec archive refactor-polyglot-taint-engine --yes`
