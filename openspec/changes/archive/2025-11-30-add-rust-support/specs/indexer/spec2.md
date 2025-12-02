## ADDED Requirements

### Requirement: Rust AST Parser Integration
The AST parser SHALL support Rust language detection and tree-sitter parsing.

#### Scenario: File extension detection
- **WHEN** a file with `.rs` extension is processed
- **THEN** the parser SHALL detect language as "rust"
- **AND** route to tree-sitter-rust parser

#### Scenario: Tree-sitter parser initialization
- **WHEN** the AST parser initializes
- **THEN** a Rust parser SHALL be created using `get_parser("rust")` from tree-sitter-language-pack
- **AND** registered in `self.parsers["rust"]`

**Implementation Location**: `theauditor/ast_parser.py`
- `_detect_language()` at line 239, add to `ext_map` at line 241-252
- `_init_tree_sitter_parsers()` at line 52, add Rust parser block after HCL (line 97)

```python
# Add to ext_map (line 241-252):
".rs": "rust",

# Add to _init_tree_sitter_parsers() after HCL block (after line 96):
try:
    rust_lang = get_language("rust")
    rust_parser = get_parser("rust")
    self.parsers["rust"] = rust_parser
    self.languages["rust"] = rust_lang
except Exception as e:
    print(f"[INFO] Rust tree-sitter not available: {e}")
```

---

### Requirement: Rust AST Extraction Module
The indexer SHALL have a dedicated Rust extraction module under `ast_extractors/rust/`.

#### Scenario: Module structure
- **WHEN** the Rust extraction module is created
- **THEN** it SHALL exist at `theauditor/ast_extractors/rust/`
- **AND** contain `__init__.py` and `core.py`

#### Scenario: Tree-sitter node traversal
- **WHEN** extracting Rust constructs from AST
- **THEN** the extractor SHALL walk tree-sitter nodes using `node.children` iteration
- **AND** identify nodes by `node.type` property

**Pattern Reference**: `theauditor/ast_extractors/hcl_impl.py`

**Directory Structure**:
```
theauditor/ast_extractors/rust/
├── __init__.py      # Exports: extract_rust_* functions
└── core.py          # Tree-sitter extraction implementation
```

**Tree-sitter Node Types**:
| Rust Construct | Node Type |
|----------------|-----------|
| struct | `struct_item` |
| enum | `enum_item` |
| trait | `trait_item` |
| impl | `impl_item` |
| function | `function_item` |
| use | `use_declaration` |
| mod | `mod_item` |
| macro_rules | `macro_definition` |
| macro call | `macro_invocation` |
| unsafe block | `unsafe_block` |
| extern block | `foreign_mod_item` |
| extern function (in extern block) | `function_signature_item` |
| static item (in extern block) | `static_item` |

**Function Modifiers Pattern** (for async/unsafe/const detection):
```
function_item
├── visibility_modifier  # pub, pub(crate), etc.
├── function_modifiers   # Contains: async, unsafe, const, extern
│   └── async/unsafe/const/extern
├── fn
├── identifier          # Function name
├── parameters
└── block
```

**Unsafe Trait Pattern**:
```
trait_item
├── unsafe              # Direct child, not in modifiers
├── trait
├── type_identifier
└── declaration_list
```

**Complete Extraction Function Example**:
```python
"""theauditor/ast_extractors/rust/core.py"""

from typing import Any

def extract_rust_structs(root_node: Any, file_path: str) -> list[dict]:
    """Extract struct definitions from tree-sitter AST.

    Args:
        root_node: Tree-sitter root node from parser
        file_path: Path to the source file

    Returns:
        List of struct dicts with keys: file_path, line, end_line, name,
        visibility, generics, is_tuple_struct, is_unit_struct, derives_json
    """
    structs = []

    def visit(node):
        if node.type == "struct_item":
            struct = {
                "file_path": file_path,
                "line": node.start_point[0] + 1,  # tree-sitter is 0-indexed
                "end_line": node.end_point[0] + 1,
                "name": None,
                "visibility": "",
                "generics": None,
                "is_tuple_struct": False,
                "is_unit_struct": False,
                "derives_json": None,
            }

            for child in node.children:
                if child.type == "visibility_modifier":
                    struct["visibility"] = child.text.decode("utf-8")
                elif child.type == "type_identifier":
                    struct["name"] = child.text.decode("utf-8")
                elif child.type == "type_parameters":
                    struct["generics"] = child.text.decode("utf-8")
                elif child.type == "field_declaration_list":
                    pass  # Named fields - normal struct
                elif child.type == "ordered_field_declaration_list":
                    struct["is_tuple_struct"] = True

            # Unit struct has no field list
            if struct["name"] and not any(
                c.type in ("field_declaration_list", "ordered_field_declaration_list")
                for c in node.children
            ):
                struct["is_unit_struct"] = True

            if struct["name"]:
                structs.append(struct)

        for child in node.children:
            visit(child)

    visit(root_node)
    return structs
```

---

### Requirement: Rust Extractor Class
The indexer SHALL have a RustExtractor class that integrates with ExtractorRegistry.

#### Scenario: Auto-registration
- **WHEN** `RustExtractor` is defined as subclass of `BaseExtractor`
- **THEN** ExtractorRegistry SHALL auto-discover it via `_discover()` at `extractors/__init__.py:86-118`

#### Scenario: File extension support
- **WHEN** `supported_extensions()` is called
- **THEN** it SHALL return `[".rs"]`

#### Scenario: Extraction output
- **WHEN** `extract()` is called with valid tree-sitter tree
- **THEN** it SHALL return dict with keys matching `rust_*` table names
- **AND** each value SHALL be a list of dicts matching table columns

**Implementation Location**: `theauditor/indexer/extractors/rust.py`

**Pattern Reference**: `theauditor/indexer/extractors/python.py`

```python
"""theauditor/indexer/extractors/rust.py"""

from typing import Any
from pathlib import Path

from . import BaseExtractor
from ...ast_extractors.rust import core as rust_core
from ...utils.logger import setup_logger

logger = setup_logger(__name__)


class RustExtractor(BaseExtractor):
    """Extractor for Rust source files."""

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        super().__init__(root_path, ast_parser)

    def supported_extensions(self) -> list[str]:
        return [".rs"]

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all Rust constructs from file."""
        file_path = file_info["path"]

        if not tree or tree.get("type") != "tree_sitter":
            logger.error(f"Tree-sitter parser unavailable for {file_path}")
            return {}

        ts_tree = tree["tree"]
        root = ts_tree.root_node

        return {
            "rust_modules": rust_core.extract_rust_modules(root, file_path),
            "rust_use_statements": rust_core.extract_rust_use_statements(root, file_path),
            "rust_functions": rust_core.extract_rust_functions(root, file_path),
            "rust_structs": rust_core.extract_rust_structs(root, file_path),
            "rust_enums": rust_core.extract_rust_enums(root, file_path),
            "rust_traits": rust_core.extract_rust_traits(root, file_path),
            "rust_impl_blocks": rust_core.extract_rust_impl_blocks(root, file_path),
            # Phase 2:
            "rust_generics": rust_core.extract_rust_generics(root, file_path),
            "rust_lifetimes": rust_core.extract_rust_lifetimes(root, file_path),
            "rust_macros": rust_core.extract_rust_macros(root, file_path),
            "rust_macro_invocations": rust_core.extract_rust_macro_invocations(root, file_path),
            "rust_async_functions": rust_core.extract_rust_async_functions(root, file_path),
            "rust_await_points": rust_core.extract_rust_await_points(root, file_path),
            "rust_unsafe_blocks": rust_core.extract_rust_unsafe_blocks(root, file_path),
            "rust_unsafe_traits": rust_core.extract_rust_unsafe_traits(root, file_path),
            "rust_struct_fields": rust_core.extract_rust_struct_fields(root, file_path),
            "rust_enum_variants": rust_core.extract_rust_enum_variants(root, file_path),
            "rust_trait_methods": rust_core.extract_rust_trait_methods(root, file_path),
            "rust_extern_functions": rust_core.extract_rust_extern_functions(root, file_path),
            "rust_extern_blocks": rust_core.extract_rust_extern_blocks(root, file_path),
        }
```

---

### Requirement: Rust Schema Tables
The indexer SHALL store Rust extraction data in 20 dedicated normalized tables.

#### Scenario: Phase 1 core tables exist
- **WHEN** the database is initialized
- **THEN** 7 core tables SHALL exist: `rust_modules`, `rust_use_statements`, `rust_functions`, `rust_structs`, `rust_enums`, `rust_traits`, `rust_impl_blocks`

#### Scenario: Phase 2 advanced tables exist
- **WHEN** Phase 2 is complete
- **THEN** 13 additional tables SHALL exist for generics, lifetimes, macros, async, unsafe, relationships, and FFI

#### Scenario: Table count assertion
- **WHEN** schema.py loads
- **THEN** total table count SHALL be 190 (170 existing + 20 Rust)

**Implementation Location**: `theauditor/indexer/schemas/rust_schema.py`

**Schema Registration**: `theauditor/indexer/schema.py`
```python
from .schemas.rust_schema import RUST_TABLES

TABLES = {
    # ... existing tables ...
    **RUST_TABLES,
}

assert len(TABLES) == 190, f"Expected 190 tables, got {len(TABLES)}"
```

**Pattern Reference**: `theauditor/indexer/schemas/python_schema.py` (imports from `.utils`)

---

### Requirement: Phase 1 Core Tables (7 tables)
The indexer SHALL create 7 core Rust tables in Phase 1.

#### Scenario: rust_modules table
- **WHEN** a Rust file contains `mod` declarations
- **THEN** module data SHALL be stored in `rust_modules`

#### Scenario: rust_use_statements table
- **WHEN** a Rust file contains `use` declarations
- **THEN** import data SHALL be stored with both local alias and canonical path

#### Scenario: rust_functions table
- **WHEN** a Rust file contains function definitions
- **THEN** function data SHALL include async/unsafe/const/extern flags

#### Scenario: rust_structs table
- **WHEN** a Rust file contains struct definitions
- **THEN** struct data SHALL distinguish tuple/unit/named variants

#### Scenario: rust_enums table
- **WHEN** a Rust file contains enum definitions
- **THEN** enum data SHALL be stored with derives

#### Scenario: rust_traits table
- **WHEN** a Rust file contains trait definitions
- **THEN** trait data SHALL include supertraits and unsafe flag

#### Scenario: rust_impl_blocks table
- **WHEN** a Rust file contains impl blocks
- **THEN** impl data SHALL store both raw and resolved type paths

**SQL Schemas**:

```sql
-- rust_modules
CREATE TABLE rust_modules (
    file_path TEXT NOT NULL,
    module_name TEXT NOT NULL,
    line INTEGER NOT NULL,
    visibility TEXT,
    is_inline BOOLEAN DEFAULT FALSE,
    parent_module TEXT,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_modules_name ON rust_modules(module_name);

-- rust_use_statements
CREATE TABLE rust_use_statements (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    import_path TEXT NOT NULL,
    local_name TEXT,
    canonical_path TEXT,
    is_glob BOOLEAN DEFAULT FALSE,
    visibility TEXT,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_use_local ON rust_use_statements(local_name);
CREATE INDEX idx_rust_use_canonical ON rust_use_statements(canonical_path);

-- rust_functions
CREATE TABLE rust_functions (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    name TEXT NOT NULL,
    visibility TEXT,
    is_async BOOLEAN DEFAULT FALSE,
    is_unsafe BOOLEAN DEFAULT FALSE,
    is_const BOOLEAN DEFAULT FALSE,
    is_extern BOOLEAN DEFAULT FALSE,
    abi TEXT,
    return_type TEXT,
    params_json TEXT,
    generics TEXT,
    where_clause TEXT,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_functions_name ON rust_functions(name);
CREATE INDEX idx_rust_functions_async ON rust_functions(is_async);
CREATE INDEX idx_rust_functions_unsafe ON rust_functions(is_unsafe);

-- rust_structs
CREATE TABLE rust_structs (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    name TEXT NOT NULL,
    visibility TEXT,
    generics TEXT,
    is_tuple_struct BOOLEAN DEFAULT FALSE,
    is_unit_struct BOOLEAN DEFAULT FALSE,
    derives_json TEXT,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_structs_name ON rust_structs(name);

-- rust_enums
CREATE TABLE rust_enums (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    name TEXT NOT NULL,
    visibility TEXT,
    generics TEXT,
    derives_json TEXT,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_enums_name ON rust_enums(name);

-- rust_traits
CREATE TABLE rust_traits (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    name TEXT NOT NULL,
    visibility TEXT,
    generics TEXT,
    supertraits TEXT,
    is_unsafe BOOLEAN DEFAULT FALSE,
    is_auto BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_traits_name ON rust_traits(name);

-- rust_impl_blocks
CREATE TABLE rust_impl_blocks (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    target_type_raw TEXT NOT NULL,
    target_type_resolved TEXT,
    trait_name TEXT,
    trait_resolved TEXT,
    generics TEXT,
    where_clause TEXT,
    is_unsafe BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_impl_target_raw ON rust_impl_blocks(target_type_raw);
CREATE INDEX idx_rust_impl_target_resolved ON rust_impl_blocks(target_type_resolved);
CREATE INDEX idx_rust_impl_trait ON rust_impl_blocks(trait_name);
```

---

### Requirement: Phase 2 Advanced Tables (13 tables)
The indexer SHALL create 13 advanced Rust tables in Phase 2.

#### Scenario: Generics extraction
- **WHEN** a Rust construct has generic parameters
- **THEN** generics SHALL be stored in `rust_generics` with bounds and defaults

#### Scenario: Lifetime extraction
- **WHEN** a Rust construct has lifetime parameters
- **THEN** lifetimes SHALL be stored in `rust_lifetimes`

#### Scenario: Macro definition extraction
- **WHEN** a Rust file contains `macro_rules!` or proc macros
- **THEN** macro data SHALL be stored in `rust_macros`

#### Scenario: Macro invocation extraction
- **WHEN** a Rust file contains macro calls
- **THEN** call data SHALL be stored in `rust_macro_invocations` with args_sample

#### Scenario: Async function extraction
- **WHEN** a Rust file contains async functions
- **THEN** async data SHALL be stored in `rust_async_functions`

#### Scenario: Await point extraction
- **WHEN** a Rust file contains `.await` expressions
- **THEN** await points SHALL be stored in `rust_await_points`

#### Scenario: Unsafe block extraction
- **WHEN** a Rust file contains unsafe blocks
- **THEN** unsafe data SHALL include SAFETY comment if present

#### Scenario: Unsafe trait extraction
- **WHEN** a Rust file implements unsafe traits
- **THEN** unsafe trait impl data SHALL be stored in `rust_unsafe_traits`

#### Scenario: Struct field extraction
- **WHEN** a struct has fields
- **THEN** field data SHALL be stored in `rust_struct_fields`

#### Scenario: Enum variant extraction
- **WHEN** an enum has variants
- **THEN** variant data SHALL be stored in `rust_enum_variants` with kind

#### Scenario: Trait method extraction
- **WHEN** a trait has methods
- **THEN** method data SHALL be stored in `rust_trait_methods`

#### Scenario: Extern function extraction
- **WHEN** a Rust file contains extern fn declarations
- **THEN** extern fn data SHALL be stored in `rust_extern_functions`

#### Scenario: Extern block extraction
- **WHEN** a Rust file contains extern blocks
- **THEN** extern block metadata SHALL be stored in `rust_extern_blocks`

**SQL Schemas**:

```sql
-- rust_generics
CREATE TABLE rust_generics (
    file_path TEXT NOT NULL,
    parent_line INTEGER NOT NULL,
    parent_type TEXT NOT NULL,
    param_name TEXT NOT NULL,
    param_kind TEXT,
    bounds TEXT,
    default_value TEXT,
    PRIMARY KEY (file_path, parent_line, param_name)
);

-- rust_lifetimes
CREATE TABLE rust_lifetimes (
    file_path TEXT NOT NULL,
    parent_line INTEGER NOT NULL,
    lifetime_name TEXT NOT NULL,
    is_static BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file_path, parent_line, lifetime_name)
);

-- rust_macros
CREATE TABLE rust_macros (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    name TEXT NOT NULL,
    macro_type TEXT,
    visibility TEXT,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_macros_name ON rust_macros(name);

-- rust_macro_invocations
CREATE TABLE rust_macro_invocations (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    macro_name TEXT NOT NULL,
    containing_function TEXT,
    args_sample TEXT,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_macro_inv_name ON rust_macro_invocations(macro_name);

-- rust_async_functions
CREATE TABLE rust_async_functions (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    function_name TEXT NOT NULL,
    return_type TEXT,
    has_await BOOLEAN DEFAULT FALSE,
    await_count INTEGER DEFAULT 0,
    PRIMARY KEY (file_path, line)
);

-- rust_await_points (NEW - was missing)
CREATE TABLE rust_await_points (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    containing_function TEXT,
    awaited_expression TEXT,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_await_function ON rust_await_points(containing_function);

-- rust_unsafe_blocks
CREATE TABLE rust_unsafe_blocks (
    file_path TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER,
    containing_function TEXT,
    reason TEXT,
    safety_comment TEXT,
    has_safety_comment BOOLEAN DEFAULT FALSE,
    operations_json TEXT,
    PRIMARY KEY (file_path, line_start)
);
CREATE INDEX idx_rust_unsafe_function ON rust_unsafe_blocks(containing_function);
CREATE INDEX idx_rust_unsafe_no_comment ON rust_unsafe_blocks(has_safety_comment);

-- rust_unsafe_traits
CREATE TABLE rust_unsafe_traits (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    trait_name TEXT NOT NULL,
    impl_type TEXT,
    PRIMARY KEY (file_path, line)
);

-- rust_struct_fields
CREATE TABLE rust_struct_fields (
    file_path TEXT NOT NULL,
    struct_line INTEGER NOT NULL,
    field_index INTEGER NOT NULL,
    field_name TEXT,
    field_type TEXT NOT NULL,
    visibility TEXT,
    is_pub BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file_path, struct_line, field_index)
);

-- rust_enum_variants
CREATE TABLE rust_enum_variants (
    file_path TEXT NOT NULL,
    enum_line INTEGER NOT NULL,
    variant_index INTEGER NOT NULL,
    variant_name TEXT NOT NULL,
    variant_kind TEXT,
    fields_json TEXT,
    discriminant TEXT,
    PRIMARY KEY (file_path, enum_line, variant_index)
);

-- rust_trait_methods
CREATE TABLE rust_trait_methods (
    file_path TEXT NOT NULL,
    trait_line INTEGER NOT NULL,
    method_line INTEGER NOT NULL,
    method_name TEXT NOT NULL,
    return_type TEXT,
    params_json TEXT,
    has_default BOOLEAN DEFAULT FALSE,
    is_async BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file_path, trait_line, method_line)
);

-- rust_extern_functions
CREATE TABLE rust_extern_functions (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    name TEXT NOT NULL,
    abi TEXT DEFAULT 'C',
    return_type TEXT,
    params_json TEXT,
    is_variadic BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file_path, line)
);
CREATE INDEX idx_rust_extern_name ON rust_extern_functions(name);

-- rust_extern_blocks (NEW - was missing)
CREATE TABLE rust_extern_blocks (
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    abi TEXT DEFAULT 'C',
    PRIMARY KEY (file_path, line)
);
```

---

### Requirement: Rust Storage Handlers
The indexer SHALL have storage handlers for all 20 Rust tables.

#### Scenario: Storage class registration
- **WHEN** DataStorer initializes
- **THEN** RustStorage SHALL be instantiated and handlers merged

#### Scenario: Phase 1 handlers
- **WHEN** Phase 1 extraction completes
- **THEN** 7 storage handlers SHALL process core table data

#### Scenario: Phase 2 handlers
- **WHEN** Phase 2 extraction completes
- **THEN** 13 additional storage handlers SHALL process advanced table data

**Implementation Location**: `theauditor/indexer/storage/rust_storage.py`

**Registration Location**: `theauditor/indexer/storage/__init__.py`

```python
from .rust_storage import RustStorage

class DataStorer:
    def __init__(self, db_manager, counts):
        # ... existing init ...
        self.rust = RustStorage(db_manager, counts)

        self.handlers = {
            # ... existing handlers ...
            **self.rust.handlers,
        }
```

**Complete Handler List**:
```python
"""theauditor/indexer/storage/rust_storage.py"""

class RustStorage:
    def __init__(self, db_manager, counts):
        self.db = db_manager
        self.counts = counts
        self.handlers = {
            # Phase 1 (7 handlers)
            "rust_modules": self.store_rust_modules,
            "rust_use_statements": self.store_rust_use_statements,
            "rust_functions": self.store_rust_functions,
            "rust_structs": self.store_rust_structs,
            "rust_enums": self.store_rust_enums,
            "rust_traits": self.store_rust_traits,
            "rust_impl_blocks": self.store_rust_impl_blocks,
            # Phase 2 (13 handlers)
            "rust_generics": self.store_rust_generics,
            "rust_lifetimes": self.store_rust_lifetimes,
            "rust_macros": self.store_rust_macros,
            "rust_macro_invocations": self.store_rust_macro_invocations,
            "rust_async_functions": self.store_rust_async_functions,
            "rust_await_points": self.store_rust_await_points,
            "rust_unsafe_blocks": self.store_rust_unsafe_blocks,
            "rust_unsafe_traits": self.store_rust_unsafe_traits,
            "rust_struct_fields": self.store_rust_struct_fields,
            "rust_enum_variants": self.store_rust_enum_variants,
            "rust_trait_methods": self.store_rust_trait_methods,
            "rust_extern_functions": self.store_rust_extern_functions,
            "rust_extern_blocks": self.store_rust_extern_blocks,
        }
```

---

### Requirement: Table Count Tracking
The indexer SHALL correctly track table count changes across phases.

#### Scenario: Phase 1 count
- **WHEN** Phase 1 is complete
- **THEN** table count SHALL be 177 (170 + 7)

#### Scenario: Phase 2 count
- **WHEN** Phase 2 is complete
- **THEN** table count SHALL be 190 (177 + 13)

**Implementation**: Update `schema.py` assertion in two commits:
1. Phase 1: `assert len(TABLES) == 177`
2. Phase 2: `assert len(TABLES) == 190`
