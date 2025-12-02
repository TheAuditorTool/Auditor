# Language Support Wiring Reference

> Extracted from `language-support` branch before dev merge.
> Use this to re-wire Go/Rust/Bash after accepting dev wins.

---

## 1. theauditor/indexer/schema.py

### Imports to add (after existing schema imports):
```python
from .schemas.bash_schema import BASH_TABLES
from .schemas.go_schema import GO_TABLES
from .schemas.rust_schema import RUST_TABLES
```

### TABLES dict - add these entries:
```python
TABLES: dict[str, TableSchema] = {
    **CORE_TABLES,
    **SECURITY_TABLES,
    **FRAMEWORKS_TABLES,
    **PYTHON_TABLES,
    **NODE_TABLES,
    **RUST_TABLES,      # ADD
    **GO_TABLES,        # ADD
    **BASH_TABLES,      # ADD
    **INFRASTRUCTURE_TABLES,
    **PLANNING_TABLES,
    **GRAPHQL_TABLES,
}
```

### Update assertion:
```python
# Change from 170 to 220 (or whatever dev's count is + 50)
assert len(TABLES) == 220, f"Schema contract violation: Expected 220 tables, got {len(TABLES)}"
```

---

## 2. theauditor/ast_extractors/__init__.py

### Import to add:
```python
from . import rust_impl, typescript_impl  # rust_impl is new
```

### __all__ list - add:
```python
__all__ = [
    "python_impl",
    "rust_impl",       # ADD
    "typescript_impl",
    "detect_language",
    "get_semantic_ast_batch",
]
```

---

## 3. theauditor/taint/core.py

### Add inside `_load_validation_sanitizers` method:
```python
def _load_validation_sanitizers(self, cursor: sqlite3.Cursor) -> None:
    """Load validation patterns from validation_framework_usage table."""
    # ADD THIS DICT at start of method:
    framework_languages = {
        "zod": "javascript",
        "joi": "javascript",
        "yup": "javascript",
        "express-validator": "javascript",
        "ajv": "javascript",
        "class-validator": "javascript",
        "validator": "rust",
        "pydantic": "python",
    }

    # ... existing query code ...

    # CHANGE the register_sanitizer calls to use lang:
    # OLD: self.register_sanitizer(method, "javascript")
    # NEW:
    lang = framework_languages.get(framework, "javascript")

    if method:
        self.register_sanitizer(method, lang)
    if var_name and method:
        self.register_sanitizer(f"{var_name}.{method}", lang)
    if framework and method:
        self.register_sanitizer(f"{framework}.{method}", lang)
```

---

## 4. theauditor/taint/ifds_analyzer.py

### Add Go detection in language detection function:
```python
# Find the function that detects language from file extension
# Add this elif clause:
elif lower.endswith(".go"):
    return "go"
```

---

## 5. theauditor/graph/builder.py

### Add Go/Rust import resolution in `_resolve_import` method:

After the existing TypeScript/JavaScript handling, before the final `return import_str`:

```python
        elif lang == "go":
            if import_str.startswith("./") or import_str.startswith("../"):
                source_dir = source_file.parent
                try:
                    up_count = import_str.count("../")
                    current_dir = source_dir
                    for _ in range(up_count):
                        current_dir = current_dir.parent

                    rel_import = import_str
                    for _ in range(up_count):
                        rel_import = rel_import.replace("../", "", 1)
                    rel_import = rel_import.lstrip("./")

                    target_path = current_dir / rel_import
                    rel_target = str(target_path.relative_to(self.project_root)).replace("\\", "/")

                    if self.db_cache.file_exists(rel_target):
                        return rel_target

                    for known_file in self.known_files:
                        if known_file.startswith(rel_target + "/") and known_file.endswith(".go"):
                            return rel_target

                    return rel_target

                except (ValueError, OSError):
                    return import_str

            parts = import_str.split("/")

            for i in range(len(parts), 0, -1):
                candidate_path = "/".join(parts[-i:])

                for known_file in self.known_files:
                    if known_file.startswith(candidate_path + "/") and known_file.endswith(".go"):
                        return candidate_path

                    if known_file == candidate_path + ".go":
                        return known_file

            return import_str

        elif lang == "rust":
            if import_str.startswith("crate::"):
                module_path = import_str[7:].replace("::", "/")

                candidate = f"{module_path}/mod.rs"
                if self.db_cache.file_exists(candidate):
                    return candidate

                candidate = f"{module_path}.rs"
                if self.db_cache.file_exists(candidate):
                    return candidate

                candidate = f"src/{module_path}/mod.rs"
                if self.db_cache.file_exists(candidate):
                    return candidate

                candidate = f"src/{module_path}.rs"
                if self.db_cache.file_exists(candidate):
                    return candidate

                return import_str

            elif import_str.startswith("self::") or import_str.startswith("super::"):
                source_dir = source_file.parent
                module_path = import_str

                up_count = module_path.count("super::")
                current_dir = source_dir
                for _ in range(up_count):
                    current_dir = current_dir.parent

                clean_path = module_path.replace("super::", "").replace("self::", "")
                clean_path = clean_path.replace("::", "/")

                if clean_path:
                    target_path = current_dir / clean_path
                else:
                    target_path = current_dir

                try:
                    rel_target = str(target_path.relative_to(self.project_root)).replace("\\", "/")

                    candidate = f"{rel_target}/mod.rs"
                    if self.db_cache.file_exists(candidate):
                        return candidate

                    candidate = f"{rel_target}.rs"
                    if self.db_cache.file_exists(candidate):
                        return candidate

                    return rel_target
                except ValueError:
                    return import_str

            return import_str
```

---

## Summary: What to do after merge

1. Copy `scripts/loguru_migration.py` and `scripts/rich_migration.py` back
2. Apply wiring from sections 1-5 above
3. Run `python -m theauditor.indexer.schemas.codegen` to regenerate accessors
4. Run tests: `pytest tests/test_rust_schema_contract.py tests/test_go_schema_contract.py`

---

## Files that survive automatically (no conflict):

- `theauditor/ast_extractors/rust_impl.py`
- `theauditor/ast_extractors/go_impl.py`
- `theauditor/ast_extractors/bash_impl.py`
- `theauditor/indexer/schemas/rust_schema.py`
- `theauditor/indexer/schemas/go_schema.py`
- `theauditor/indexer/schemas/bash_schema.py`
- `theauditor/indexer/storage/rust_storage.py`
- `theauditor/indexer/storage/go_storage.py`
- `theauditor/indexer/storage/bash_storage.py`
- `theauditor/indexer/extractors/rust.py`
- `theauditor/indexer/extractors/go.py`
- `theauditor/indexer/extractors/bash.py`
- `theauditor/indexer/database/rust_database.py`
- `theauditor/indexer/database/go_database.py`
- `theauditor/indexer/database/bash_database.py`
- `theauditor/graph/strategies/rust_*.py` (4 files)
- `theauditor/graph/strategies/go_*.py` (2 files)
- `theauditor/graph/strategies/bash_pipes.py`
- `theauditor/rules/rust/*.py` (5 files)
- `theauditor/rules/go/*.py` (4 files)
- `theauditor/rules/bash/*.py` (3 files)
- `theauditor/utils/logging.py`
- All tests (tests/test_rust_*, tests/test_go_*, tests/test_bash_*)
- All fixtures
