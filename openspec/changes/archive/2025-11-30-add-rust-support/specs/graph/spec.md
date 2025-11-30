## ADDED Requirements

### Requirement: Rust Graph Strategy Base
The graph layer SHALL have 4 dedicated strategies for Rust-specific patterns.

#### Scenario: Strategy registration
- **WHEN** DFG builder initializes
- **THEN** all 4 Rust strategies SHALL be in the strategies list
- **AND** they SHALL be instantiated after existing Python/Node strategies

#### Scenario: Strategy interface
- **WHEN** a Rust strategy is called
- **THEN** it SHALL implement `build(db_path: str, project_root: str) -> dict[str, Any]`
- **AND** return edge data compatible with graphs.db schema

**Implementation Location**: `theauditor/graph/dfg_builder.py` line 27-32

**Required Change**:
```python
from .strategies.rust_unsafe import RustUnsafeStrategy
from .strategies.rust_ffi import RustFFIStrategy
from .strategies.rust_async import RustAsyncStrategy
from .strategies.rust_traits import RustTraitStrategy

# In __init__():
self.strategies = [
    PythonOrmStrategy(),
    NodeOrmStrategy(),
    NodeExpressStrategy(),
    InterceptorStrategy(),
    # Rust strategies
    RustUnsafeStrategy(),
    RustFFIStrategy(),
    RustAsyncStrategy(),
    RustTraitStrategy(),
]
```

**Pattern Reference**: `theauditor/graph/strategies/base.py` (GraphStrategy ABC)

---

### Requirement: RustUnsafeStrategy
The graph layer SHALL build edges connecting unsafe blocks to containing functions and track propagation.

#### Scenario: Unsafe containment edges
- **WHEN** an unsafe block exists inside a function
- **THEN** an `unsafe_contains` edge SHALL be created from function to unsafe block

#### Scenario: Unsafe call edges
- **WHEN** a call is made within an unsafe block
- **THEN** an `unsafe_calls` edge SHALL be created to the callee

#### Scenario: Unsafe propagation edges
- **WHEN** function A contains unsafe and function B calls A
- **THEN** an `unsafe_propagates` edge SHALL be created from A to B
- **AND** propagation SHALL be transitive

**Implementation Location**: `theauditor/graph/strategies/rust_unsafe.py`

**Database Dependencies** (from indexer spec):
- `rust_unsafe_blocks` - unsafe block locations
- `rust_functions` - function definitions
- `rust_unsafe_traits` - unsafe trait implementations
- `symbols` - symbol resolution

**Edge Types Produced**:

| Edge Type | Source | Target | Metadata |
|-----------|--------|--------|----------|
| `unsafe_contains` | function_id | unsafe_block_id | reason, has_safety_comment |
| `unsafe_calls` | caller_unsafe_block | callee_function | is_ffi, is_raw_pointer |
| `unsafe_propagates` | function_id | caller_function_id | propagation_reason |

**Implementation**:
```python
"""theauditor/graph/strategies/rust_unsafe.py"""

from typing import Any
import sqlite3
from .base import GraphStrategy


class RustUnsafeStrategy(GraphStrategy):
    """Strategy for building Rust unsafe block analysis edges."""

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        edges = []
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Build containment edges: function -> unsafe_block
        cursor.execute("""
            SELECT
                ub.file_path, ub.line_start, ub.line_end,
                ub.reason, ub.has_safety_comment,
                rf.name as containing_function, rf.line as fn_line
            FROM rust_unsafe_blocks ub
            JOIN rust_functions rf ON ub.file_path = rf.file_path
                AND ub.line_start BETWEEN rf.line AND rf.end_line
        """)
        for row in cursor.fetchall():
            edges.append({
                "type": "unsafe_contains",
                "source": f"{row[0]}:{row[6]}",  # function
                "target": f"{row[0]}:{row[1]}",  # unsafe block
                "metadata": {
                    "reason": row[3],
                    "has_safety_comment": bool(row[4]),
                }
            })

        # 2. Build propagation edges (transitive closure)
        # ... implementation continues

        conn.close()
        return {"edges": edges}
```

---

### Requirement: RustFFIStrategy
The graph layer SHALL build edges connecting Rust code to FFI boundaries.

#### Scenario: FFI boundary detection
- **WHEN** Rust code calls an extern function
- **THEN** an `ffi_boundary` edge SHALL be created

#### Scenario: FFI type crossing
- **WHEN** data crosses FFI boundary
- **THEN** an `ffi_type_crossing` edge MAY be created with conversion metadata

**Implementation Location**: `theauditor/graph/strategies/rust_ffi.py`

**Database Dependencies**:
- `rust_extern_functions` - extern fn declarations
- `rust_extern_blocks` - extern block metadata
- `function_call_args` - call sites

**Edge Types Produced**:

| Edge Type | Source | Target | Metadata |
|-----------|--------|--------|----------|
| `ffi_boundary` | rust_caller | extern_function | abi, is_unsafe |
| `ffi_type_crossing` | rust_type | c_type | conversion_kind |

**Security Relevance**: FFI boundaries are critical for security analysis - data crossing FFI boundaries may lose Rust's safety guarantees.

**Implementation**:
```python
"""theauditor/graph/strategies/rust_ffi.py"""

from typing import Any
import sqlite3
from .base import GraphStrategy


class RustFFIStrategy(GraphStrategy):
    """Strategy for building Rust FFI boundary edges."""

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        edges = []
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find calls to extern functions
        cursor.execute("""
            SELECT
                fca.file_path, fca.line, fca.callee_name,
                ref.abi, ref.is_variadic
            FROM function_call_args fca
            JOIN rust_extern_functions ref
                ON fca.callee_name = ref.name
        """)
        for row in cursor.fetchall():
            edges.append({
                "type": "ffi_boundary",
                "source": f"{row[0]}:{row[1]}",
                "target": row[2],
                "metadata": {
                    "abi": row[3],
                    "is_variadic": bool(row[4]),
                }
            })

        conn.close()
        return {"edges": edges}
```

---

### Requirement: RustAsyncStrategy
The graph layer SHALL build edges for async/await flow.

#### Scenario: Async spawn detection
- **WHEN** tokio::spawn or similar is called with async task
- **THEN** an `async_spawn` edge SHALL be created

#### Scenario: Await point tracking
- **WHEN** .await is used in async function
- **THEN** an `await_point` edge SHALL be created

#### Scenario: Async boundary detection
- **WHEN** sync code calls block_on with async code
- **THEN** an `async_boundary` edge SHALL be created

**Implementation Location**: `theauditor/graph/strategies/rust_async.py`

**Database Dependencies**:
- `rust_async_functions` - async fn definitions
- `rust_await_points` - .await locations
- `function_call_args` - spawn/block_on calls

**Edge Types Produced**:

| Edge Type | Source | Target | Metadata |
|-----------|--------|--------|----------|
| `async_spawn` | spawner_function | async_task | executor_type |
| `await_point` | async_function | awaited_future | line |
| `async_boundary` | sync_function | async_function | bridge_type |

**Implementation**:
```python
"""theauditor/graph/strategies/rust_async.py"""

from typing import Any
import sqlite3
from .base import GraphStrategy


class RustAsyncStrategy(GraphStrategy):
    """Strategy for building Rust async/await flow edges."""

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        edges = []
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find await points
        cursor.execute("""
            SELECT
                rap.file_path, rap.line, rap.containing_function,
                rap.awaited_expression
            FROM rust_await_points rap
        """)
        for row in cursor.fetchall():
            edges.append({
                "type": "await_point",
                "source": f"{row[0]}:{row[2]}",  # containing async fn
                "target": row[3],  # awaited expression
                "metadata": {"line": row[1]}
            })

        # Find spawn calls
        cursor.execute("""
            SELECT fca.file_path, fca.line, fca.callee_name
            FROM function_call_args fca
            WHERE fca.callee_name IN ('tokio::spawn', 'async_std::task::spawn')
        """)
        for row in cursor.fetchall():
            edges.append({
                "type": "async_spawn",
                "source": f"{row[0]}:{row[1]}",
                "target": row[2],
                "metadata": {"executor_type": "tokio" if "tokio" in row[2] else "async_std"}
            })

        conn.close()
        return {"edges": edges}
```

---

### Requirement: RustTraitStrategy
The graph layer SHALL build edges connecting trait definitions to implementations.

#### Scenario: Trait implementation edges
- **WHEN** an impl block implements a trait for a type
- **THEN** an `implements_trait` edge SHALL be created

#### Scenario: Trait method implementation edges
- **WHEN** a trait method is implemented
- **THEN** a `trait_method_impl` edge SHALL be created

#### Scenario: Trait bound edges
- **WHEN** a generic has trait bounds
- **THEN** a `trait_bound` edge SHALL be created

**Implementation Location**: `theauditor/graph/strategies/rust_traits.py`

**Database Dependencies**:
- `rust_traits` - trait definitions
- `rust_impl_blocks` - impl block metadata
- `rust_trait_methods` - trait method signatures

**Edge Types Produced**:

| Edge Type | Source | Target | Metadata |
|-----------|--------|--------|----------|
| `implements_trait` | impl_block_id | trait_id | target_type |
| `trait_method_impl` | impl_method_id | trait_method_id | is_default |
| `trait_bound` | generic_param | trait_id | bound_type |

**Critical for Resolution**: This strategy enables answering "which impl block handles this method call?" - essential for call graph accuracy.

**Implementation**:
```python
"""theauditor/graph/strategies/rust_traits.py"""

from typing import Any
import sqlite3
from .base import GraphStrategy


class RustTraitStrategy(GraphStrategy):
    """Strategy for building Rust trait implementation edges."""

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        edges = []
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find trait implementations
        cursor.execute("""
            SELECT
                rib.file_path, rib.line, rib.target_type_resolved,
                rib.trait_resolved, rt.file_path as trait_file, rt.line as trait_line
            FROM rust_impl_blocks rib
            JOIN rust_traits rt ON rib.trait_resolved = rt.name
            WHERE rib.trait_name IS NOT NULL
        """)
        for row in cursor.fetchall():
            edges.append({
                "type": "implements_trait",
                "source": f"{row[0]}:{row[1]}",  # impl block
                "target": f"{row[4]}:{row[5]}",  # trait definition
                "metadata": {
                    "target_type": row[2],
                    "trait": row[3],
                }
            })

        conn.close()
        return {"edges": edges}
```

---

### Requirement: Rust Module Resolution
The graph layer SHALL resolve Rust type names to canonical paths.

#### Scenario: Use statement alias resolution
- **WHEN** a file has `use crate::models::User`
- **THEN** `User` in that file SHALL resolve to `crate::models::User`

#### Scenario: Glob import handling
- **WHEN** a file has `use crate::prelude::*`
- **THEN** all exported names from prelude SHALL be available

#### Scenario: Resolution fallback
- **WHEN** a type cannot be resolved
- **THEN** it SHALL remain as raw name with `external::` prefix for external crates

**Implementation Location**: `theauditor/rust_resolver.py`

**Integration Points**:
- `theauditor/graph/builder.py` - extend `resolve_import_path()` for Rust
- Called during impl block storage to populate `target_type_resolved`

**Implementation**:
```python
"""theauditor/rust_resolver.py"""

import sqlite3
from typing import Optional


class RustResolver:
    """Resolves Rust type names to canonical crate paths."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._alias_cache: dict[str, dict[str, str]] = {}

    def resolve_type(self, file_path: str, type_name: str) -> Optional[str]:
        """Resolve a type name to its canonical path.

        Args:
            file_path: The file containing the type reference
            type_name: The local type name (e.g., "User")

        Returns:
            Canonical path (e.g., "crate::models::User") or None if unresolved
        """
        # 1. Check if type is defined locally in same file
        local = self._check_local_definition(file_path, type_name)
        if local:
            return local

        # 2. Check use statements for alias
        alias_map = self._get_alias_map(file_path)
        if type_name in alias_map:
            return alias_map[type_name]

        # 3. Check prelude imports (std types like Vec, String, etc.)
        prelude = self._check_prelude(type_name)
        if prelude:
            return prelude

        # 4. Unresolved - mark as external
        return f"external::{type_name}"

    def _get_alias_map(self, file_path: str) -> dict[str, str]:
        """Build alias map from use statements for a file."""
        if file_path in self._alias_cache:
            return self._alias_cache[file_path]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT local_name, import_path
            FROM rust_use_statements
            WHERE file_path = ? AND local_name IS NOT NULL
        """, (file_path,))

        alias_map = {}
        for local_name, import_path in cursor.fetchall():
            alias_map[local_name] = import_path

        conn.close()
        self._alias_cache[file_path] = alias_map
        return alias_map

    def _check_local_definition(self, file_path: str, type_name: str) -> Optional[str]:
        """Check if type is defined in the same file."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check structs
        cursor.execute("""
            SELECT 1 FROM rust_structs
            WHERE file_path = ? AND name = ?
        """, (file_path, type_name))
        if cursor.fetchone():
            conn.close()
            return f"crate::{type_name}"  # Simplified - real impl needs module path

        # Check enums
        cursor.execute("""
            SELECT 1 FROM rust_enums
            WHERE file_path = ? AND name = ?
        """, (file_path, type_name))
        if cursor.fetchone():
            conn.close()
            return f"crate::{type_name}"

        conn.close()
        return None

    def _check_prelude(self, type_name: str) -> Optional[str]:
        """Check if type is in Rust prelude."""
        prelude_types = {
            "Vec": "std::vec::Vec",
            "String": "std::string::String",
            "Option": "std::option::Option",
            "Result": "std::result::Result",
            "Box": "std::boxed::Box",
            "Rc": "std::rc::Rc",
            "Arc": "std::sync::Arc",
            "HashMap": "std::collections::HashMap",
            "HashSet": "std::collections::HashSet",
        }
        return prelude_types.get(type_name)
```

---

### Requirement: Graph Verification
The graph layer SHALL produce verifiable Rust edges in graphs.db.

#### Scenario: Edge type verification
- **WHEN** `aud graph build` completes on Rust project
- **THEN** graphs.db SHALL contain edges with types starting with `unsafe_`, `ffi_`, `async_`, `implements_`

#### Scenario: Unsafe propagation is transitive
- **WHEN** unsafe propagation edges are built
- **THEN** indirect callers of unsafe functions SHALL have propagation edges

#### Scenario: Trait resolution enables call graphs
- **WHEN** trait impl edges are built
- **THEN** method calls on trait objects SHALL resolve to impl blocks

**Verification Commands**:
```sql
-- Check edge types exist
SELECT DISTINCT type FROM edges
WHERE type LIKE 'unsafe_%'
   OR type LIKE 'ffi_%'
   OR type LIKE 'async_%'
   OR type LIKE 'implements_%';

-- Check unsafe propagation is transitive
SELECT COUNT(*) FROM edges WHERE type = 'unsafe_propagates';

-- Check trait implementations
SELECT source, target, metadata FROM edges WHERE type = 'implements_trait' LIMIT 10;
```
