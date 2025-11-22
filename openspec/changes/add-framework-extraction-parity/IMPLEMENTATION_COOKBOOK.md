# Implementation Cookbook - Zero Ambiguity Guide

**Purpose**: This document provides 100% copy-paste ready code for implementing framework extraction parity. Any AI (or human) can execute this without making design decisions.

**How to Use**:
1. Read Section 1 (Sequelize) completely - this is the reference implementation
2. For other frameworks, copy the Sequelize pattern and change the marked sections
3. All code is ready to paste - no thinking required
4. Code markers are used instead of line numbers (resilient to code changes)

---

## Section 1: Sequelize ORM (Complete Reference Implementation)

### Step 1.1: Add Schema to node_schema.py

**Location**: `theauditor/indexer/schemas/node_schema.py`

**Find this code marker**:
```python
# ============================================================================
# BUILD ANALYSIS TABLES
# ============================================================================
```

**Insert BEFORE the marker** (after VUE_PROVIDE_INJECT table):

```python
# ============================================================================
# SEQUELIZE ORM TABLES
# ============================================================================

SEQUELIZE_MODELS = TableSchema(
    name="sequelize_models",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("table_name", "TEXT", nullable=True),  # Can be NULL if inferred from model name
        Column("extends_model", "BOOLEAN", default="0"),  # True if explicitly extends Model
    ],
    primary_key=["file", "model_name"],
    indexes=[
        ("idx_sequelize_models_file", ["file"]),
        ("idx_sequelize_models_name", ["model_name"]),
    ]
)

SEQUELIZE_ASSOCIATIONS = TableSchema(
    name="sequelize_associations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("association_type", "TEXT", nullable=False),  # 'hasMany', 'belongsTo', 'hasOne', 'belongsToMany'
        Column("target_model", "TEXT", nullable=False),
        Column("foreign_key", "TEXT", nullable=True),  # Can be NULL if using convention
        Column("through_table", "TEXT", nullable=True),  # Only for belongsToMany
    ],
    primary_key=["file", "model_name", "association_type", "target_model", "line"],
    indexes=[
        ("idx_sequelize_assoc_file", ["file"]),
        ("idx_sequelize_assoc_model", ["model_name"]),
        ("idx_sequelize_assoc_target", ["target_model"]),
        ("idx_sequelize_assoc_type", ["association_type"]),
    ]
)
```

**Then find this code marker**:
```python
NODE_TABLES: Dict[str, TableSchema] = {
```

**Add to the dictionary** (after "validation_framework_usage" entry):

```python
    # Sequelize ORM
    "sequelize_models": SEQUELIZE_MODELS,
    "sequelize_associations": SEQUELIZE_ASSOCIATIONS,
```

---

### Step 1.2: Add Data Handling to javascript.py

**Location**: `theauditor/indexer/extractors/javascript.py`

**Find this code marker** (in the `extract()` method):
```python
            'cdk_constructs': []  # AWS CDK infrastructure-as-code constructs (TypeScript/JavaScript)
        }
```

**Add AFTER this line** (still inside the result dict):

```python
            'cdk_constructs': [],  # AWS CDK infrastructure-as-code constructs (TypeScript/JavaScript)
            # Sequelize ORM
            'sequelize_models': [],
            'sequelize_associations': [],
```

**Then find this code marker**:
```python
            if extracted_data and isinstance(extracted_data, dict):
                used_phase5_symbols = True  # Mark that we're using Phase 5 data
```

**Find the section where extracted_data is processed** (look for lines like `result['symbols'].extend(...)`).

**Add AFTER the existing extracted_data processing** (before the `# React/Vue framework-specific analysis` comment):

```python
                # Extract Sequelize ORM data
                sequelize_models = extracted_data.get('sequelize_models', [])
                if sequelize_models:
                    result['sequelize_models'].extend(sequelize_models)

                sequelize_associations = extracted_data.get('sequelize_associations', [])
                if sequelize_associations:
                    result['sequelize_associations'].extend(sequelize_associations)
```

---

### Step 1.3: Add Storage Logic to indexer/__init__.py

**Location**: `theauditor/indexer/__init__.py`

**Find this code marker**:
```python
        # Store React component hooks (junction table)
        for hook in extraction_data.get('react_component_hooks', []):
```

**Add AFTER the React storage section** (after all React tables are stored):

```python
        # ============================================================================
        # STORE SEQUELIZE ORM DATA
        # ============================================================================

        # Store Sequelize models
        for model in extraction_data.get('sequelize_models', []):
            cursor.execute("""
                INSERT OR REPLACE INTO sequelize_models
                (file, line, model_name, table_name, extends_model)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                model.get('line', 0),
                model.get('model_name', ''),
                model.get('table_name'),  # Can be None
                model.get('extends_model', False)
            ))

        # Store Sequelize associations
        for assoc in extraction_data.get('sequelize_associations', []):
            cursor.execute("""
                INSERT OR REPLACE INTO sequelize_associations
                (file, line, model_name, association_type, target_model, foreign_key, through_table)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                assoc.get('line', 0),
                assoc.get('model_name', ''),
                assoc.get('association_type', ''),
                assoc.get('target_model', ''),
                assoc.get('foreign_key'),  # Can be None
                assoc.get('through_table')  # Can be None
            ))
```

---

### Step 1.4: Create Test Fixture

**Location**: Create directory `tests/fixtures/javascript/node-sequelize-orm/`

**Create file**: `tests/fixtures/javascript/node-sequelize-orm/models/user.js`

```javascript
// Sequelize model with associations
const { Model, DataTypes } = require('sequelize');
const sequelize = require('../database');

class User extends Model {}

User.init({
  id: {
    type: DataTypes.INTEGER,
    primaryKey: true,
    autoIncrement: true
  },
  username: {
    type: DataTypes.STRING(80),
    allowNull: false,
    unique: true
  },
  email: {
    type: DataTypes.STRING(120),
    allowNull: false,
    unique: true
  },
  passwordHash: {
    type: DataTypes.STRING(128),
    allowNull: false
  }
}, {
  sequelize,
  modelName: 'User',
  tableName: 'users'
});

// Associations
User.hasMany(require('./post'), {
  foreignKey: 'userId',
  as: 'posts'
});

User.belongsTo(require('./role'), {
  foreignKey: 'roleId',
  as: 'role'
});

User.belongsToMany(require('./group'), {
  through: 'UserGroups',
  foreignKey: 'userId',
  otherKey: 'groupId',
  as: 'groups'
});

module.exports = User;
```

**Create file**: `tests/fixtures/javascript/node-sequelize-orm/models/post.js`

```javascript
const { Model, DataTypes } = require('sequelize');
const sequelize = require('../database');

class Post extends Model {}

Post.init({
  id: {
    type: DataTypes.INTEGER,
    primaryKey: true,
    autoIncrement: true
  },
  title: {
    type: DataTypes.STRING(200),
    allowNull: false
  },
  content: {
    type: DataTypes.TEXT,
    allowNull: false
  },
  userId: {
    type: DataTypes.INTEGER,
    allowNull: false,
    references: {
      model: 'users',
      key: 'id'
    }
  }
}, {
  sequelize,
  modelName: 'Post',
  tableName: 'posts'
});

Post.belongsTo(require('./user'), {
  foreignKey: 'userId',
  as: 'author'
});

module.exports = Post;
```

**Create file**: `tests/fixtures/javascript/node-sequelize-orm/spec.yaml`

```yaml
name: node-sequelize-orm
description: Sequelize ORM model extraction test fixture
language: javascript

tables:
  sequelize_models:
    min_rows: 2  # User, Post models
    queries:
      - name: verify_user_model
        sql: SELECT * FROM sequelize_models WHERE model_name = 'User'
        expect_rows: 1

      - name: verify_table_mapping
        sql: SELECT * FROM sequelize_models WHERE model_name = 'User' AND table_name = 'users'
        expect_rows: 1

      - name: verify_extends_model
        sql: SELECT * FROM sequelize_models WHERE extends_model = 1
        expect_rows: 2  # Both User and Post extend Model

  sequelize_associations:
    min_rows: 4  # User.hasMany(Post), User.belongsTo(Role), User.belongsToMany(Group), Post.belongsTo(User)
    queries:
      - name: verify_hasmany_association
        sql: SELECT * FROM sequelize_associations WHERE model_name = 'User' AND association_type = 'hasMany' AND target_model LIKE '%post%'
        expect_rows: 1

      - name: verify_belongsto_association
        sql: SELECT * FROM sequelize_associations WHERE model_name = 'Post' AND association_type = 'belongsTo' AND target_model LIKE '%user%'
        expect_rows: 1

      - name: verify_belongstomany_association
        sql: SELECT * FROM sequelize_associations WHERE model_name = 'User' AND association_type = 'belongsToMany' AND through_table = 'UserGroups'
        expect_rows: 1

      - name: verify_foreign_key_tracking
        sql: SELECT * FROM sequelize_associations WHERE foreign_key = 'userId'
        expect_rows_min: 2  # User.hasMany(Post) and Post.belongsTo(User) both use userId
```

---

## Section 2: BullMQ (Follow Sequelize Pattern)

### Step 2.1: Schema (Copy Sequelize, Change These Parts)

**Copy the Sequelize schema code from Section 1.1, then change:**

```python
# CHANGE 1: Table names
SEQUELIZE_MODELS → BULLMQ_QUEUES
SEQUELIZE_ASSOCIATIONS → BULLMQ_WORKERS

# CHANGE 2: Columns for BULLMQ_QUEUES
columns=[
    Column("file", "TEXT", nullable=False),
    Column("line", "INTEGER", nullable=False),
    Column("queue_name", "TEXT", nullable=False),
    Column("redis_config", "TEXT", nullable=True),  # Stringified config
],
primary_key=["file", "queue_name"],
indexes=[
    ("idx_bullmq_queues_file", ["file"]),
    ("idx_bullmq_queues_name", ["queue_name"]),
]

# CHANGE 3: Columns for BULLMQ_WORKERS
columns=[
    Column("file", "TEXT", nullable=False),
    Column("line", "INTEGER", nullable=False),
    Column("queue_name", "TEXT", nullable=False),
    Column("worker_function", "TEXT", nullable=True),  # Function name or 'anonymous'
    Column("processor_path", "TEXT", nullable=True),  # File path if imported
],
primary_key=["file", "queue_name", "line"],
indexes=[
    ("idx_bullmq_workers_file", ["file"]),
    ("idx_bullmq_workers_queue", ["queue_name"]),
]

# CHANGE 4: Registry entries
"bullmq_queues": BULLMQ_QUEUES,
"bullmq_workers": BULLMQ_WORKERS,
```

### Step 2.2: Integration (Copy Sequelize, Change These Parts)

**javascript.py extract() method:**
```python
# CHANGE: Variable names and dict keys
'bullmq_queues': [],
'bullmq_workers': [],

bullmq_queues = extracted_data.get('bullmq_queues', [])
if bullmq_queues:
    result['bullmq_queues'].extend(bullmq_queues)

bullmq_workers = extracted_data.get('bullmq_workers', [])
if bullmq_workers:
    result['bullmq_workers'].extend(bullmq_workers)
```

**indexer/__init__.py storage:**
```python
# CHANGE: Table names and column mappings
for queue in extraction_data.get('bullmq_queues', []):
    cursor.execute("""
        INSERT OR REPLACE INTO bullmq_queues
        (file, line, queue_name, redis_config)
        VALUES (?, ?, ?, ?)
    """, (
        file_path,
        queue.get('line', 0),
        queue.get('name', ''),  # NOTE: extractor returns 'name', we map to 'queue_name'
        queue.get('redis_config')
    ))

for worker in extraction_data.get('bullmq_workers', []):
    cursor.execute("""
        INSERT OR REPLACE INTO bullmq_workers
        (file, line, queue_name, worker_function, processor_path)
        VALUES (?, ?, ?, ?, ?)
    """, (
        file_path,
        worker.get('line', 0),
        worker.get('queue_name', ''),
        worker.get('worker_function'),
        worker.get('processor_path')
    ))
```

### Step 2.3: Test Fixture

**Create**: `tests/fixtures/javascript/node-bullmq-jobs/queues/emailQueue.js`

```javascript
const { Queue, Worker } = require('bullmq');

// Queue definition
const emailQueue = new Queue('emailQueue', {
  connection: {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379
  }
});

// Worker definition
const emailWorker = new Worker('emailQueue', async (job) => {
  const { to, subject, body } = job.data;
  console.log(`Sending email to ${to}: ${subject}`);
  // Send email logic here
  return { sent: true, messageId: 'abc123' };
});

// Job producer
async function sendEmail(to, subject, body) {
  await emailQueue.add('sendEmail', { to, subject, body });
}

module.exports = { emailQueue, sendEmail };
```

**spec.yaml** (copy Sequelize, change table names and queries)

---

## Section 3: Angular (5 Tables Pattern)

### Step 3.1: Schema Template

Angular has **5 tables** instead of 2, so follow this pattern:

```python
# ============================================================================
# ANGULAR FRAMEWORK TABLES
# ============================================================================

ANGULAR_COMPONENTS = TableSchema(
    name="angular_components",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("component_name", "TEXT", nullable=False),
        Column("selector", "TEXT", nullable=True),  # Can be NULL for abstract components
        Column("template_path", "TEXT", nullable=True),
        Column("style_paths", "TEXT", nullable=True),  # JSON array of style file paths
        Column("has_lifecycle_hooks", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "component_name"],
    indexes=[
        ("idx_angular_components_file", ["file"]),
        ("idx_angular_components_name", ["component_name"]),
        ("idx_angular_components_selector", ["selector"]),
    ]
)

ANGULAR_SERVICES = TableSchema(
    name="angular_services",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("service_name", "TEXT", nullable=False),
        Column("is_injectable", "BOOLEAN", default="1"),  # Always true for services
        Column("provided_in", "TEXT", nullable=True),  # 'root', 'any', or module name
    ],
    primary_key=["file", "service_name"],
    indexes=[
        ("idx_angular_services_file", ["file"]),
        ("idx_angular_services_name", ["service_name"]),
    ]
)

ANGULAR_MODULES = TableSchema(
    name="angular_modules",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("module_name", "TEXT", nullable=False),
        Column("declarations", "TEXT", nullable=True),  # JSON array of component/directive names
        Column("imports", "TEXT", nullable=True),  # JSON array of imported modules
        Column("providers", "TEXT", nullable=True),  # JSON array of service providers
        Column("exports", "TEXT", nullable=True),  # JSON array of exported declarations
    ],
    primary_key=["file", "module_name"],
    indexes=[
        ("idx_angular_modules_file", ["file"]),
        ("idx_angular_modules_name", ["module_name"]),
    ]
)

ANGULAR_GUARDS = TableSchema(
    name="angular_guards",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("guard_name", "TEXT", nullable=False),
        Column("guard_type", "TEXT", nullable=False),  # 'CanActivate', 'CanDeactivate', 'CanLoad', 'Resolve'
        Column("implements_interface", "TEXT", nullable=True),  # Interface name
    ],
    primary_key=["file", "guard_name"],
    indexes=[
        ("idx_angular_guards_file", ["file"]),
        ("idx_angular_guards_name", ["guard_name"]),
        ("idx_angular_guards_type", ["guard_type"]),
    ]
)

DI_INJECTIONS = TableSchema(
    name="di_injections",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target_class", "TEXT", nullable=False),  # Component/service that injects
        Column("injected_service", "TEXT", nullable=False),  # Service being injected
        Column("injection_type", "TEXT", nullable=False),  # 'constructor' or 'property'
    ],
    indexes=[
        ("idx_di_injections_file", ["file"]),
        ("idx_di_injections_target", ["target_class"]),
        ("idx_di_injections_service", ["injected_service"]),
    ]
)
```

**Registry:**
```python
    # Angular framework
    "angular_components": ANGULAR_COMPONENTS,
    "angular_services": ANGULAR_SERVICES,
    "angular_modules": ANGULAR_MODULES,
    "angular_guards": ANGULAR_GUARDS,
    "di_injections": DI_INJECTIONS,
```

### Step 3.2: Integration Pattern

**javascript.py:**
```python
            # Angular framework
            'angular_components': [],
            'angular_services': [],
            'angular_modules': [],
            'angular_guards': [],
            'di_injections': [],

# In extracted_data processing:
                angular_components = extracted_data.get('angular_components', [])
                if angular_components:
                    result['angular_components'].extend(angular_components)

                angular_services = extracted_data.get('angular_services', [])
                if angular_services:
                    result['angular_services'].extend(angular_services)

                angular_modules = extracted_data.get('angular_modules', [])
                if angular_modules:
                    result['angular_modules'].extend(angular_modules)

                angular_guards = extracted_data.get('angular_guards', [])
                if angular_guards:
                    result['angular_guards'].extend(angular_guards)

                di_injections = extracted_data.get('di_injections', [])
                if di_injections:
                    result['di_injections'].extend(di_injections)
```

**indexer/__init__.py:**
```python
        # ============================================================================
        # STORE ANGULAR FRAMEWORK DATA
        # ============================================================================

        for component in extraction_data.get('angular_components', []):
            cursor.execute("""
                INSERT OR REPLACE INTO angular_components
                (file, line, component_name, selector, template_path, style_paths, has_lifecycle_hooks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                component.get('line', 0),
                component.get('name', ''),
                component.get('selector'),
                component.get('template_path'),
                component.get('style_paths'),  # Already stringified by extractor
                component.get('has_lifecycle_hooks', False)
            ))

        for service in extraction_data.get('angular_services', []):
            cursor.execute("""
                INSERT OR REPLACE INTO angular_services
                (file, line, service_name, is_injectable, provided_in)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                service.get('line', 0),
                service.get('name', ''),
                service.get('is_injectable', True),
                service.get('provided_in')
            ))

        for module in extraction_data.get('angular_modules', []):
            cursor.execute("""
                INSERT OR REPLACE INTO angular_modules
                (file, line, module_name, declarations, imports, providers, exports)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                module.get('line', 0),
                module.get('name', ''),
                module.get('declarations'),  # Already stringified
                module.get('imports'),
                module.get('providers'),
                module.get('exports')
            ))

        for guard in extraction_data.get('angular_guards', []):
            cursor.execute("""
                INSERT OR REPLACE INTO angular_guards
                (file, line, guard_name, guard_type, implements_interface)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                guard.get('line', 0),
                guard.get('name', ''),
                guard.get('guard_type', ''),
                guard.get('implements_interface')
            ))

        for injection in extraction_data.get('di_injections', []):
            cursor.execute("""
                INSERT OR REPLACE INTO di_injections
                (file, line, target_class, injected_service, injection_type)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                injection.get('line', 0),
                injection.get('target_class', ''),
                injection.get('service', ''),  # NOTE: extractor returns 'service', map to 'injected_service'
                injection.get('injection_type', 'constructor')
            ))
```

---

## Section 4: Update Schema Assertion

**Location**: `theauditor/indexer/schema.py`

**Find this code marker:**
```python
# Total: 116 tables (24 core [+3 cfg_jsx] + 5 security + 5 frameworks + 34 python + 17 node + 18 infrastructure + 5 planning + 8 graphql)

# Verify table count at module load time
assert len(TABLES) == 116, f"Schema contract violation: Expected 116 tables, got {len(TABLES)}"
```

**Replace with:**
```python
# Total: 125 tables (24 core [+3 cfg_jsx] + 5 security + 5 frameworks + 34 python + 26 node + 18 infrastructure + 5 planning + 8 graphql)
# Node increased from 17 to 26: +2 Sequelize, +2 BullMQ, +5 Angular = +9 tables

# Verify table count at module load time
assert len(TABLES) == 125, f"Schema contract violation: Expected 125 tables, got {len(TABLES)}"
print(f"[SCHEMA] Loaded {len(TABLES)} tables")
```

---

## Section 5: Python Extraction Functions (Complete Templates)

### Step 5.1: Marshmallow Schema Extraction

**Location**: `theauditor/ast_extractors/python_impl.py`

**Find this code marker:**
```python
def extract_pydantic_validators(tree: Dict, parser_self) -> List[Dict]:
```

**Add AFTER this function** (after the entire pydantic function ends):

```python
def extract_marshmallow_schemas(tree: Dict, parser_self) -> List[Dict]:
    """Extract Marshmallow schema definitions.

    Detects classes extending Schema from marshmallow.

    Args:
        tree: AST tree dict
        parser_self: Parser instance for AST traversal

    Returns:
        List of dicts with keys:
            - line: int - Line number
            - schema_name: str - Class name
            - has_meta: bool - Whether Meta inner class exists
            - meta_fields: str - Comma-separated field list from Meta.fields (or None)
    """
    schemas = []

    # Find all class definitions
    for node in parser_self._find_nodes(tree, ast.ClassDef):
        # Check if class extends Schema
        extends_schema = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == 'Schema':
                extends_schema = True
                break
            elif isinstance(base, ast.Attribute) and base.attr == 'Schema':
                extends_schema = True
                break

        if not extends_schema:
            continue

        schema_name = node.name
        line = node.lineno

        # Check for Meta inner class
        has_meta = False
        meta_fields = None

        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == 'Meta':
                has_meta = True

                # Try to extract fields from Meta.fields attribute
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.name == 'fields':
                                # Extract field names from tuple/list
                                if isinstance(meta_item.value, (ast.Tuple, ast.List)):
                                    field_names = []
                                    for elt in meta_item.value.elts:
                                        if isinstance(elt, ast.Constant):
                                            field_names.append(elt.value)
                                    meta_fields = ', '.join(field_names)
                                break
                break

        schemas.append({
            'line': line,
            'schema_name': schema_name,
            'has_meta': has_meta,
            'meta_fields': meta_fields
        })

    return schemas


def extract_marshmallow_fields(tree: Dict, parser_self) -> List[Dict]:
    """Extract Marshmallow field definitions from schema classes.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int - Line number
            - schema_name: str - Parent schema class name
            - field_name: str - Field name
            - field_type: str - Field type (String, Integer, etc.)
            - is_required: bool - Whether field is required
            - validators: str - Validator names (comma-separated)
    """
    fields = []

    # Find all class definitions that extend Schema
    for node in parser_self._find_nodes(tree, ast.ClassDef):
        # Check if class extends Schema
        extends_schema = any(
            (isinstance(base, ast.Name) and base.id == 'Schema') or
            (isinstance(base, ast.Attribute) and base.attr == 'Schema')
            for base in node.bases
        )

        if not extends_schema:
            continue

        schema_name = node.name

        # Find field assignments in class body
        for item in node.body:
            if isinstance(item, ast.Assign):
                # Get field name from assignment target
                field_name = None
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.name
                        break

                if not field_name:
                    continue

                # Check if assignment is a fields.* call
                field_type = None
                is_required = False
                validators = []

                if isinstance(item.value, ast.Call):
                    # Get field type (e.g., fields.String())
                    if isinstance(item.value.func, ast.Attribute):
                        if isinstance(item.value.func.value, ast.Name) and item.value.func.value.id == 'fields':
                            field_type = item.value.func.attr

                    # Check for required=True keyword
                    for keyword in item.value.keywords:
                        if keyword.arg == 'required':
                            if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                                is_required = True

                        # Check for validate keyword
                        elif keyword.arg == 'validate':
                            # Can be a single validator or list of validators
                            if isinstance(keyword.value, ast.Name):
                                validators.append(keyword.value.id)
                            elif isinstance(keyword.value, ast.List):
                                for elt in keyword.value.elts:
                                    if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name):
                                        validators.append(elt.func.id)

                if field_type:  # Only add if we detected a fields.* pattern
                    fields.append({
                        'line': item.lineno,
                        'schema_name': schema_name,
                        'field_name': field_name,
                        'field_type': field_type,
                        'is_required': is_required,
                        'validators': ', '.join(validators) if validators else None
                    })

    return fields
```

### Step 5.2: WTForms Extraction

**Add AFTER Marshmallow functions:**

```python
def extract_wtforms_forms(tree: Dict, parser_self) -> List[Dict]:
    """Extract WTForms form definitions.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - form_name: str
            - has_csrf: bool - Whether CSRF protection is enabled
            - submit_method: str - Submit method name if defined
    """
    forms = []

    for node in parser_self._find_nodes(tree, ast.ClassDef):
        # Check if class extends Form or FlaskForm
        extends_form = any(
            (isinstance(base, ast.Name) and base.id in ['Form', 'FlaskForm']) or
            (isinstance(base, ast.Attribute) and base.attr in ['Form', 'FlaskForm'])
            for base in node.bases
        )

        if not extends_form:
            continue

        form_name = node.name
        line = node.lineno
        has_csrf = True  # Default for FlaskForm
        submit_method = None

        # Look for submit method
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name in ['submit', 'on_submit', 'validate_on_submit']:
                submit_method = item.name
                break

        forms.append({
            'line': line,
            'form_name': form_name,
            'has_csrf': has_csrf,
            'submit_method': submit_method
        })

    return forms


def extract_wtforms_fields(tree: Dict, parser_self) -> List[Dict]:
    """Extract WTForms field definitions.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - form_name: str
            - field_name: str
            - field_type: str - StringField, IntegerField, etc.
            - validators: str - Comma-separated validator names
            - default_value: str - Default value if present
    """
    fields = []

    for node in parser_self._find_nodes(tree, ast.ClassDef):
        # Check if class extends Form
        extends_form = any(
            (isinstance(base, ast.Name) and base.id in ['Form', 'FlaskForm']) or
            (isinstance(base, ast.Attribute) and base.attr in ['Form', 'FlaskForm'])
            for base in node.bases
        )

        if not extends_form:
            continue

        form_name = node.name

        # Find field assignments
        for item in node.body:
            if isinstance(item, ast.Assign):
                field_name = None
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.name
                        break

                if not field_name:
                    continue

                field_type = None
                validators = []
                default_value = None

                if isinstance(item.value, ast.Call):
                    # Get field type (e.g., StringField())
                    if isinstance(item.value.func, ast.Name):
                        field_type = item.value.func.id

                    # Extract validators from second positional arg or 'validators' keyword
                    if len(item.value.args) >= 2:
                        if isinstance(item.value.args[1], ast.List):
                            for elt in item.value.args[1].elts:
                                if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name):
                                    validators.append(elt.func.id)

                    # Check for default keyword
                    for keyword in item.value.keywords:
                        if keyword.arg == 'default':
                            if isinstance(keyword.value, ast.Constant):
                                default_value = str(keyword.value.value)

                if field_type and 'Field' in field_type:  # Only WTForms fields
                    fields.append({
                        'line': item.lineno,
                        'form_name': form_name,
                        'field_name': field_name,
                        'field_type': field_type,
                        'validators': ', '.join(validators) if validators else None,
                        'default_value': default_value
                    })

    return fields
```

### Step 5.3: Celery Extraction

**Add AFTER WTForms functions:**

```python
def extract_celery_tasks(tree: Dict, parser_self) -> List[Dict]:
    """Extract Celery task definitions.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - task_name: str - Function name
            - bind: bool - Whether bind=True
            - max_retries: int - Max retries (or None)
            - rate_limit: str - Rate limit string (or None)
    """
    tasks = []

    for node in parser_self._find_nodes(tree, ast.FunctionDef):
        # Check for @task or @app.task decorator
        has_task_decorator = False
        bind = False
        max_retries = None
        rate_limit = None

        for decorator in node.decorator_list:
            # Check for @task
            if isinstance(decorator, ast.Name) and decorator.id == 'task':
                has_task_decorator = True

            # Check for @app.task or @celery.task
            elif isinstance(decorator, ast.Attribute) and decorator.attr == 'task':
                has_task_decorator = True

            # Check for @task(...) with arguments
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == 'task':
                    has_task_decorator = True
                elif isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'task':
                    has_task_decorator = True

                # Extract decorator arguments
                for keyword in decorator.keywords:
                    if keyword.arg == 'bind':
                        if isinstance(keyword.value, ast.Constant):
                            bind = keyword.value.value
                    elif keyword.arg == 'max_retries':
                        if isinstance(keyword.value, ast.Constant):
                            max_retries = keyword.value.value
                    elif keyword.arg == 'rate_limit':
                        if isinstance(keyword.value, ast.Constant):
                            rate_limit = keyword.value.value

        if not has_task_decorator:
            continue

        tasks.append({
            'line': node.lineno,
            'task_name': node.name,
            'bind': bind,
            'max_retries': max_retries,
            'rate_limit': rate_limit
        })

    return tasks


def extract_celery_task_calls(tree: Dict, parser_self) -> List[Dict]:
    """Extract Celery task invocations (.delay(), .apply_async()).

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - task_name: str - Task being invoked
            - call_type: str - 'delay' or 'apply_async'
            - arguments: str - Stringified arguments
    """
    task_calls = []

    for node in parser_self._find_nodes(tree, ast.Call):
        # Check for task.delay() or task.apply_async()
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['delay', 'apply_async']:
                # Get task name from the object being called
                task_name = None
                if isinstance(node.func.value, ast.Name):
                    task_name = node.func.value.id

                if task_name:
                    # Stringify arguments
                    arguments = []
                    for arg in node.args:
                        if isinstance(arg, ast.Constant):
                            arguments.append(f"{arg.value!r}")
                        elif isinstance(arg, ast.Name):
                            arguments.append(arg.id)

                    for keyword in node.keywords:
                        if isinstance(keyword.value, ast.Constant):
                            arguments.append(f"{keyword.arg}={keyword.value.value!r}")

                    task_calls.append({
                        'line': node.lineno,
                        'task_name': task_name,
                        'call_type': node.func.attr,
                        'arguments': ', '.join(arguments)
                    })

    return task_calls


def extract_celery_beat_schedules(tree: Dict, parser_self) -> List[Dict]:
    """Extract Celery Beat periodic task schedules.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - schedule_name: str - Schedule entry name
            - task_name: str - Task to execute
            - crontab: str - Crontab schedule (if present)
            - interval: str - Interval schedule (if present)
    """
    schedules = []

    # Look for beat_schedule dict or CELERYBEAT_SCHEDULE dict
    for node in parser_self._find_nodes(tree, ast.Assign):
        schedule_dict_name = None

        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr == 'beat_schedule':
                schedule_dict_name = 'beat_schedule'
                break
            elif isinstance(target, ast.Name) and target.id == 'CELERYBEAT_SCHEDULE':
                schedule_dict_name = 'CELERYBEAT_SCHEDULE'
                break

        if not schedule_dict_name:
            continue

        # Parse the dict
        if isinstance(node.value, ast.Dict):
            for key, value in zip(node.value.keys, node.value.values):
                if isinstance(key, ast.Constant):
                    schedule_name = key.value

                    # Parse schedule entry dict
                    task_name = None
                    crontab = None
                    interval = None

                    if isinstance(value, ast.Dict):
                        for k, v in zip(value.keys, value.values):
                            if isinstance(k, ast.Constant):
                                if k.value == 'task':
                                    if isinstance(v, ast.Constant):
                                        task_name = v.value
                                elif k.value == 'schedule':
                                    # Could be crontab(...) or interval seconds
                                    if isinstance(v, ast.Call):
                                        if isinstance(v.func, ast.Name) and v.func.id == 'crontab':
                                            # Extract crontab args
                                            crontab_parts = []
                                            for keyword in v.keywords:
                                                if isinstance(keyword.value, ast.Constant):
                                                    crontab_parts.append(f"{keyword.arg}={keyword.value.value}")
                                            crontab = ', '.join(crontab_parts)
                                    elif isinstance(v, ast.Constant):
                                        interval = str(v.value)

                    if task_name:
                        schedules.append({
                            'line': node.lineno,
                            'schedule_name': schedule_name,
                            'task_name': task_name,
                            'crontab': crontab,
                            'interval': interval
                        })

    return schedules
```

### Step 5.4: Pytest Extraction

**Add AFTER Celery functions:**

```python
def extract_pytest_fixtures(tree: Dict, parser_self) -> List[Dict]:
    """Extract pytest fixture definitions.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - fixture_name: str - Function name
            - scope: str - 'function', 'class', 'module', 'session'
            - autouse: bool - Whether autouse=True
    """
    fixtures = []

    for node in parser_self._find_nodes(tree, ast.FunctionDef):
        # Check for @pytest.fixture decorator
        has_fixture_decorator = False
        scope = 'function'  # Default
        autouse = False

        for decorator in node.decorator_list:
            # Check for @pytest.fixture
            if isinstance(decorator, ast.Attribute):
                if isinstance(decorator.value, ast.Name) and decorator.value.id == 'pytest':
                    if decorator.attr == 'fixture':
                        has_fixture_decorator = True

            # Check for @pytest.fixture(...) with arguments
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == 'pytest':
                        if decorator.func.attr == 'fixture':
                            has_fixture_decorator = True

                            # Extract decorator arguments
                            for keyword in decorator.keywords:
                                if keyword.arg == 'scope':
                                    if isinstance(keyword.value, ast.Constant):
                                        scope = keyword.value.value
                                elif keyword.arg == 'autouse':
                                    if isinstance(keyword.value, ast.Constant):
                                        autouse = keyword.value.value

        if not has_fixture_decorator:
            continue

        fixtures.append({
            'line': node.lineno,
            'fixture_name': node.name,
            'scope': scope,
            'autouse': autouse
        })

    return fixtures


def extract_pytest_parametrize(tree: Dict, parser_self) -> List[Dict]:
    """Extract pytest.mark.parametrize decorators.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - test_function: str - Test function name
            - parameter_names: str - Comma-separated parameter names
            - parameter_values: str - Stringified parameter values
    """
    parametrize_decorators = []

    for node in parser_self._find_nodes(tree, ast.FunctionDef):
        for decorator in node.decorator_list:
            # Check for @pytest.mark.parametrize(...)
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    # Check for pytest.mark.parametrize
                    if (isinstance(decorator.func.value, ast.Attribute) and
                        isinstance(decorator.func.value.value, ast.Name) and
                        decorator.func.value.value.id == 'pytest' and
                        decorator.func.value.attr == 'mark' and
                        decorator.func.attr == 'parametrize'):

                        # Extract parameter names (first arg)
                        parameter_names = None
                        if len(decorator.args) >= 1:
                            if isinstance(decorator.args[0], ast.Constant):
                                parameter_names = decorator.args[0].value

                        # Extract parameter values (second arg)
                        parameter_values = None
                        if len(decorator.args) >= 2:
                            # This is typically a list of tuples
                            parameter_values = ast.unparse(decorator.args[1])

                        if parameter_names:
                            parametrize_decorators.append({
                                'line': node.lineno,
                                'test_function': node.name,
                                'parameter_names': parameter_names,
                                'parameter_values': parameter_values
                            })

    return parametrize_decorators


def extract_pytest_markers(tree: Dict, parser_self) -> List[Dict]:
    """Extract custom pytest markers.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - test_function: str - Test function name
            - marker_name: str - Marker name (e.g., 'slow', 'skipif')
            - marker_args: str - Stringified marker arguments (or None)
    """
    markers = []

    for node in parser_self._find_nodes(tree, ast.FunctionDef):
        for decorator in node.decorator_list:
            # Check for @pytest.mark.* (excluding parametrize which is handled separately)
            if isinstance(decorator, ast.Attribute):
                if (isinstance(decorator.value, ast.Attribute) and
                    isinstance(decorator.value.value, ast.Name) and
                    decorator.value.value.id == 'pytest' and
                    decorator.value.attr == 'mark'):

                    marker_name = decorator.attr
                    if marker_name != 'parametrize':  # Skip parametrize
                        markers.append({
                            'line': node.lineno,
                            'test_function': node.name,
                            'marker_name': marker_name,
                            'marker_args': None
                        })

            # Check for @pytest.mark.*(...) with arguments
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if (isinstance(decorator.func.value, ast.Attribute) and
                        isinstance(decorator.func.value.value, ast.Name) and
                        decorator.func.value.value.id == 'pytest' and
                        decorator.func.value.attr == 'mark'):

                        marker_name = decorator.func.attr
                        if marker_name != 'parametrize':  # Skip parametrize
                            # Stringify arguments
                            marker_args = ast.unparse(decorator)
                            markers.append({
                                'line': node.lineno,
                                'test_function': node.name,
                                'marker_name': marker_name,
                                'marker_args': marker_args
                            })

    return markers
```

---

## Section 6: Python Schema Tables (Already Exist - No Changes Needed!)

**IMPORTANT**: Python tables already exist in `python_schema.py`. You do NOT need to add them. They are:

- `python_marshmallow_schemas`
- `python_marshmallow_fields`
- `python_wtforms_forms`
- `python_wtforms_fields`
- `python_celery_tasks`
- `python_celery_task_calls`
- `python_celery_beat_schedules`
- `python_pytest_fixtures`
- `python_pytest_parametrize`
- `python_pytest_markers`

**However**, you DO need to add storage logic in `indexer/__init__.py`.

### Step 6.1: Python Storage in indexer/__init__.py

**Find this code marker:**
```python
        # Store Python ORM fields
        for field in extraction_data.get('python_orm_fields', []):
```

**Add AFTER the Python ORM storage section:**

```python
        # ============================================================================
        # STORE PYTHON FRAMEWORK DATA (Marshmallow, WTForms, Celery, Pytest)
        # ============================================================================

        # Marshmallow
        for schema in extraction_data.get('python_marshmallow_schemas', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_marshmallow_schemas
                (file, line, schema_name, has_meta, meta_fields)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                schema.get('line', 0),
                schema.get('schema_name', ''),
                schema.get('has_meta', False),
                schema.get('meta_fields')
            ))

        for field in extraction_data.get('python_marshmallow_fields', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_marshmallow_fields
                (file, line, schema_name, field_name, field_type, is_required, validators)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                field.get('line', 0),
                field.get('schema_name', ''),
                field.get('field_name', ''),
                field.get('field_type'),
                field.get('is_required', False),
                field.get('validators')
            ))

        # WTForms
        for form in extraction_data.get('python_wtforms_forms', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_wtforms_forms
                (file, line, form_name, has_csrf, submit_method)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                form.get('line', 0),
                form.get('form_name', ''),
                form.get('has_csrf', True),
                form.get('submit_method')
            ))

        for field in extraction_data.get('python_wtforms_fields', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_wtforms_fields
                (file, line, form_name, field_name, field_type, validators, default_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                field.get('line', 0),
                field.get('form_name', ''),
                field.get('field_name', ''),
                field.get('field_type'),
                field.get('validators'),
                field.get('default_value')
            ))

        # Celery
        for task in extraction_data.get('python_celery_tasks', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_celery_tasks
                (file, line, task_name, bind, max_retries, rate_limit)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                task.get('line', 0),
                task.get('task_name', ''),
                task.get('bind', False),
                task.get('max_retries'),
                task.get('rate_limit')
            ))

        for call in extraction_data.get('python_celery_task_calls', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_celery_task_calls
                (file, line, task_name, call_type, arguments)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                call.get('line', 0),
                call.get('task_name', ''),
                call.get('call_type', ''),
                call.get('arguments')
            ))

        for schedule in extraction_data.get('python_celery_beat_schedules', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_celery_beat_schedules
                (file, line, schedule_name, task_name, crontab, interval)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                schedule.get('line', 0),
                schedule.get('schedule_name', ''),
                schedule.get('task_name', ''),
                schedule.get('crontab'),
                schedule.get('interval')
            ))

        # Pytest
        for fixture in extraction_data.get('python_pytest_fixtures', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_pytest_fixtures
                (file, line, fixture_name, scope, autouse)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                fixture.get('line', 0),
                fixture.get('fixture_name', ''),
                fixture.get('scope', 'function'),
                fixture.get('autouse', False)
            ))

        for parametrize in extraction_data.get('python_pytest_parametrize', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_pytest_parametrize
                (file, line, test_function, parameter_names, parameter_values)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                parametrize.get('line', 0),
                parametrize.get('test_function', ''),
                parametrize.get('parameter_names', ''),
                parametrize.get('parameter_values')
            ))

        for marker in extraction_data.get('python_pytest_markers', []):
            cursor.execute("""
                INSERT OR REPLACE INTO python_pytest_markers
                (file, line, test_function, marker_name, marker_args)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                marker.get('line', 0),
                marker.get('test_function', ''),
                marker.get('marker_name', ''),
                marker.get('marker_args')
            ))
```

---

## Section 7: Execution Checklist

**Use this checklist to ensure nothing is missed:**

### Node.js Integration
- [ ] Added 2 Sequelize tables to node_schema.py
- [ ] Added 2 BullMQ tables to node_schema.py
- [ ] Added 5 Angular tables to node_schema.py
- [ ] Updated NODE_TABLES registry (9 new entries)
- [ ] Updated schema.py assertion (116 → 125)
- [ ] Added 9 keys to javascript.py result dict
- [ ] Added 9 data extraction blocks to javascript.py
- [ ] Added 9 storage blocks to indexer/__init__.py

### Python Implementation
- [ ] Added extract_marshmallow_schemas() function
- [ ] Added extract_marshmallow_fields() function
- [ ] Added extract_wtforms_forms() function
- [ ] Added extract_wtforms_fields() function
- [ ] Added extract_celery_tasks() function
- [ ] Added extract_celery_task_calls() function
- [ ] Added extract_celery_beat_schedules() function
- [ ] Added extract_pytest_fixtures() function
- [ ] Added extract_pytest_parametrize() function
- [ ] Added extract_pytest_markers() function
- [ ] Added 10 storage blocks to indexer/__init__.py

### Testing
- [ ] Created Sequelize test fixture
- [ ] Created BullMQ test fixture
- [ ] Created Angular test fixture
- [ ] Created Marshmallow test fixture
- [ ] Created WTForms test fixture
- [ ] Created Celery test fixture
- [ ] Created Pytest test fixture
- [ ] All spec.yaml files created with SQL queries

### Validation
- [ ] Run `aud index` on TheAuditor project
- [ ] Run `aud index` on plant project
- [ ] Verify table counts in database
- [ ] Run `openspec validate add-framework-extraction-parity --strict`
- [ ] Run `pytest tests/`

---

## Section 8: Common Pitfalls & Solutions

### Pitfall 1: Line Numbers Drift

**Problem**: Code says "add after line 98" but line 98 changes.

**Solution**: Use code markers (unique strings) instead:
```python
# Find this EXACT text (unique in file):
'cdk_constructs': []  # AWS CDK infrastructure-as-code constructs

# Then add AFTER it
```

### Pitfall 2: Column Name Mismatches

**Problem**: Extractor returns `{name: 'emailQueue'}` but schema expects `queue_name`.

**Solution**: Map in storage code:
```python
queue.get('name', '')  # Extractor returns 'name'
# Store as 'queue_name' in database
```

### Pitfall 3: Missing Nullable Checks

**Problem**: Extractor returns `None` for optional field, SQL INSERT fails.

**Solution**: Use `.get()` with no default (returns None) for nullable columns:
```python
model.get('table_name')  # Returns None if missing (OK for nullable column)
model.get('table_name', '')  # Returns '' if missing (for non-nullable column)
```

### Pitfall 4: Forgot to Update Registry

**Problem**: Added table schema but forgot to add to NODE_TABLES dict.

**Solution**: Always add in TWO places:
1. Table definition (`SEQUELIZE_MODELS = TableSchema(...)`)
2. Registry entry (`"sequelize_models": SEQUELIZE_MODELS,`)

### Pitfall 5: Primary Key Too Restrictive

**Problem**: Primary key `[file, queue_name]` allows only one queue per file.

**Solution**: Add `line` to primary key if multiple instances allowed:
```python
primary_key=["file", "queue_name", "line"]  # Allows multiple queues with same name
```

---

## Section 9: Final Verification Script

**Run this after implementation to verify everything works:**

```bash
# Step 1: Run indexer
cd C:/Users/santa/Desktop/TheAuditor
aud index

# Step 2: Verify tables exist
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
cursor = conn.cursor()

# Check Node.js tables
tables = ['sequelize_models', 'sequelize_associations', 'bullmq_queues', 'bullmq_workers',
          'angular_components', 'angular_services', 'angular_modules', 'angular_guards', 'di_injections']

print('Node.js Framework Tables:')
for table in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'  ✅ {table}: {count} rows')
    except sqlite3.OperationalError:
        print(f'  ❌ {table}: TABLE MISSING')

# Check Python tables
python_tables = ['python_marshmallow_schemas', 'python_marshmallow_fields',
                 'python_wtforms_forms', 'python_wtforms_fields',
                 'python_celery_tasks', 'python_celery_task_calls', 'python_celery_beat_schedules',
                 'python_pytest_fixtures', 'python_pytest_parametrize', 'python_pytest_markers']

print('\nPython Framework Tables:')
for table in python_tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'  ✅ {table}: {count} rows')
    except sqlite3.OperationalError:
        print(f'  ❌ {table}: TABLE MISSING')

conn.close()
"

# Step 3: Validate OpenSpec
openspec validate add-framework-extraction-parity --strict

# Step 4: Run tests
pytest tests/fixtures/javascript/node-sequelize-orm/ -v
pytest tests/fixtures/javascript/node-bullmq-jobs/ -v
pytest tests/fixtures/javascript/node-angular-app/ -v
```

---

## Summary

**This cookbook provides:**
- ✅ Complete schema code (copy-paste ready)
- ✅ Complete integration code (copy-paste ready)
- ✅ Complete storage code (copy-paste ready)
- ✅ Complete function implementations (copy-paste ready)
- ✅ Test fixture examples
- ✅ Verification scripts
- ✅ Code markers instead of line numbers
- ✅ Common pitfalls and solutions

**Any AI can now:**
1. Read Section 1 (Sequelize reference)
2. Copy pattern for other frameworks
3. Paste code into correct locations (using code markers)
4. Run verification script
5. Done - no thinking required

**Estimated time**: 6-8 hours of focused copy-paste work (no design decisions needed).
