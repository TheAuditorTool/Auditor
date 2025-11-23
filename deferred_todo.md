# Deferred Improvements

Architectural improvements identified during pythonparity validation that should NOT be done before merge to main.

---

## 1. OSV Database Download: Move from Setup to Deps Phase

**Discovery Date**: 2025-11-22
**Discovered During**: 7-project validation (rai project)
**Priority**: P2 (nice to have, not blocking)

### Current Problem

`venv_install.py` hardcodes subdirectory names when searching for lockfiles:

```python
# Lines 789-793 - only checks these 5 directories
for subdir in ['backend', 'frontend', 'server', 'client', 'web']:
    lock = target_dir / subdir / name
```

Projects with non-standard structures (e.g., `rai/raicalc/package-lock.json`) don't get detected.

### Chicken-and-Egg Problem

`aud setup-ai` runs BEFORE `aud full`, so there's no database to query for lockfile locations. We're doing blind filesystem search at setup time.

### Proposed Solution

**Split the responsibility:**

1. **`aud setup-ai`** - Download OSV-Scanner binary ONLY (fast, 5 seconds)
2. **`aud full` deps phase** - Query database/manifest for lockfiles, download databases on first run

```
Current:  setup-ai → [binary + databases] → aud full → [scan]
Proposed: setup-ai → [binary only] → aud full → [find lockfiles from DB, download DBs, scan]
```

### Benefits

- **No hardcoding** - uses file_manifest which already knows ALL files
- **Multiple lockfiles handled** - plant has 2, monorepos can have 10+
- **Setup is faster** - binary download only (5 sec vs 5-10 min)
- **First audit slower** - but databases cached for subsequent runs
- **Architecturally cleaner** - deps phase owns everything deps-related

### Implementation

1. **venv_install.py**: Remove database download logic from `setup_osv_scanner()`
2. **vulnerability_scanner.py**: Add database download before scan if missing
3. **Query lockfiles from database**:
   ```python
   cursor.execute("""
       SELECT DISTINCT path FROM file_manifest
       WHERE path LIKE '%package-lock.json'
          OR path LIKE '%yarn.lock'
          OR path LIKE '%pnpm-lock.yaml'
          OR path LIKE '%requirements.txt'
          OR path LIKE '%Pipfile.lock'
          OR path LIKE '%poetry.lock'
   """)
   ```

### Estimated Effort

| Task | Hours |
|------|-------|
| Move DB download to deps phase | 2 |
| Query lockfiles from database | 1 |
| Handle first-run DB download | 2 |
| Test on 7 projects | 2 |
| **TOTAL** | **7 hours** |

### Workaround (Current)

For now, the hardcoded list works for common monorepo structures. Projects with unusual structures won't get vulnerability DB downloaded during setup, but:
- Online mode still works (OSV-Scanner falls back to API)
- User can manually run scan to trigger download

---

## 2. ZERO FALLBACK Policy Violations

**Discovery Date**: 2025-11-22
**Discovered During**: Multi-agent audit fact-check
**Priority**: P2 (architectural integrity, not urgent)

### Current Problem

The codebase states "ZERO FALLBACK POLICY" as its most important rule, but violates this extensively:

**Identified Violations:**
1. **fce.py:465-476** - Checks if `findings_consolidated` table exists, returns empty list
2. **input_validation_analyzer.py:88-109** - Checks table existence before querying `python_routes` and `js_routes`
3. **blueprint.py** - 13 bare `except:` blocks at lines: 238, 470, 477, 484, 494, 509, 526, 532, 538, 560, 579, 587, 593
4. **context/query.py** - Multiple `except sqlite3.OperationalError` with silent fallbacks at lines: 207-209, 289-291, 336-338, 511-512, 516-517, 1036-1038, 1086-1088, 1099-1100

### Philosophical Decision Required

Either:
1. **Enforce the policy** - Remove all fallbacks, let failures crash hard
2. **Abandon the policy** - Remove the "ZERO FALLBACK" doctrine from CLAUDE.md

### Estimated Effort

| Task | Hours |
|------|-------|
| Remove table existence checks | 4 |
| Replace bare except blocks | 6 |
| Add proper error propagation | 8 |
| Update tests for new behavior | 12 |
| **TOTAL** | **30 hours** |

### Impact Analysis

**If enforcing ZERO FALLBACK:**
- More crashes initially
- Faster bug discovery
- Simpler code paths
- Better for debugging

**If abandoning:**
- Current behavior maintained
- More graceful degradation
- Need to document fallback strategy

---

## 3. Remove extraction.py Compatibility Layer

**Discovery Date**: 2025-11-22
**Discovered During**: Dead code analysis
**Priority**: P3 (cleanup, not blocking)

### Current Problem

`extraction.py` serves as a `/readme/` compatibility layer but is still imported in 10 places:
- theauditor\commands\graphql.py
- theauditor\indexer\orchestrator.py
- theauditor\indexer\extractors\__init__.py
- theauditor\indexer\extractors\javascript.py
- theauditor\rules\dependency\ghost_dependencies.py
- theauditor\ast_extractors\typescript_impl_structure.py
- theauditor\ast_extractors\typescript_impl.py
- theauditor\indexer_compat.py
- theauditor\ast_parser.py
- theauditor\ast_extractors\javascript\security_extractors.js

### TODO: Complete Removal

1. **Update all imports** to use new extraction paths directly
2. **Remove extraction.py** (553 lines)
3. **Test all affected modules**

### Estimated Effort

| Task | Hours |
|------|-------|
| Update 10 import locations | 3 |
| Test affected modules | 4 |
| Remove extraction.py | 1 |
| **TOTAL** | **8 hours** |

---

## 4. Delete Dead `_build_function_ranges()` Functions

**Discovery Date**: 2025-11-22
**Discovered During**: Doomsday document fact-check
**Priority**: P3 (dead code cleanup)

### Current Problem

The function `_build_function_ranges(tree: ast.AST)` exists in **7 extractor files** but is **NEVER CALLED**:

| File | Lines |
|------|-------|
| `theauditor/ast_extractors/python/control_flow_extractors.py` | 56-66 |
| `theauditor/ast_extractors/python/stdlib_pattern_extractors.py` | 52-62 |
| `theauditor/ast_extractors/python/protocol_extractors.py` | 56-66 |
| `theauditor/ast_extractors/python/operator_extractors.py` | 57-67 |
| `theauditor/ast_extractors/python/fundamental_extractors.py` | 126-136 |
| `theauditor/ast_extractors/python/collection_extractors.py` | 52-62 |
| `theauditor/ast_extractors/python/class_feature_extractors.py` | 56-66 |

### Why It's Dead

A migration script `scripts/ast_walk_to_filecontext.py` was created to replace `_build_function_ranges(tree)` calls with `context.function_ranges`. The public extraction functions now use the `FileContext` pattern:

```python
# OLD (never reached):
function_ranges = _build_function_ranges(tree)

# NEW (what's actually used):
function_ranges = context.function_ranges
```

The function definitions were left behind as orphaned dead code.

### Note on Bug

The function also contains a bug (uses undefined `context` variable at line 59), but since it's never called, this bug never manifests.

### Estimated Effort

| Task | Hours |
|------|-------|
| Delete function from 7 files | 0.5 |
| Verify no calls exist | 0.5 |
| **TOTAL** | **1 hour** |

---

## 5. Monolithic Files Refactoring

**Discovery Date**: 2025-11-22
**Discovered During**: Multi-agent audit
**Priority**: P3 (maintainability, not blocking)

### Current Problem

Four files exceed reasonable size thresholds:

| File | Lines | Issue |
|------|-------|-------|
| `pipelines.py` | 1,777 | `run_full_pipeline()` is ~1,450 lines |
| `fce.py` | 1,845 | `run_fce()` is ~940 lines |
| `python_storage.py` | 2,486 | 149 methods in single class |
| `commands/query.py` | 1,169 | Single massive function |

### Proposed Refactoring

**pipelines.py** - Split into:
- `pipeline_stages.py` - Individual stage implementations
- `pipeline_core.py` - Orchestration logic

**fce.py** - Split into:
- `fce_loaders.py` - Database loading
- `fce_correlation.py` - Error correlation logic
- `fce_core.py` - Main function

**python_storage.py** - Extract method groups into mixins

**commands/query.py** - Break into subcommand modules

### Estimated Effort

| Task | Hours |
|------|-------|
| pipelines.py refactor | 16 |
| fce.py refactor | 12 |
| python_storage.py refactor | 20 |
| query.py refactor | 8 |
| **TOTAL** | **56 hours** |

---

## 6. Test Coverage for Security Rules

**Discovery Date**: 2025-11-22
**Discovered During**: Multi-agent audit
**Priority**: P3 (quality, not blocking)

### Current Problem

- **114 rule files** in `theauditor/rules/`
- **~0 test files** specifically testing rules
- The `tests/` directory contains only fixtures (test data), not test implementations

### Scope

Need tests for:
- SQL injection detection rules
- XSS detection rules
- Authentication bypass rules
- Hardcoded secrets rules
- Taint flow rules

### Estimated Effort

| Task | Hours |
|------|-------|
| Test framework setup | 8 |
| Tests for 20 critical rules | 40 |
| Tests for remaining rules | 120 |
| **TOTAL** | **168 hours** |

---

## 7. Backup Files Deletion

**Discovery Date**: 2025-11-22
**Discovered During**: Dead code analysis
**Priority**: P3 (cleanup)

### Current Problem

Three `.bak` files exist in `theauditor/taint/backup/` totaling 2,590 lines:

| File | Lines |
|------|-------|
| `cfg_integration.py.bak` | 867 |
| `interprocedural.py.bak` | 899 |
| `interprocedural_cfg.py.bak` | 824 |

These are orphaned backups with zero imports.

### Action

```bash
rm -rf theauditor/taint/backup/
```

### Estimated Effort

| Task | Hours |
|------|-------|
| Delete directory | 0.1 |
| Verify no references | 0.4 |
| **TOTAL** | **0.5 hours** |

---

## 8. Polyglot Monorepo Support in manifest_parser.py

**Discovery Date**: 2025-11-22
**Discovered During**: project_anarchy validation (anarchy_commerce polyglot structure)
**Priority**: P2 (required for realistic multi-language projects)
**Status**: RESOLVED (2025-11-23)

### Solution Implemented

Added to `manifest_parser.py`:
1. `parse_cargo_toml()` - Extracts dependencies, dev-dependencies, workspace.dependencies, workspace.members
2. `_normalize_cargo_dep()` - Handles version strings, `{workspace: true}`, git deps, path deps
3. `discover_monorepo_manifests()` - Finds all manifest files excluding node_modules/vendor/etc.
4. Updated `check_package_in_deps()` to handle Cargo workspace inheritance format

Added to `framework_registry.py`:
- Added `["workspace", "dependencies"]` path to all Rust framework detection sources

Added to `framework_detector.py`:
- `_find_cargo_workspace_root()` - Walks up tree to find workspace Cargo.toml
- `_get_cargo_workspace_deps()` - Caches and returns workspace dependencies
- `_resolve_cargo_workspace_version()` - Resolves "workspace" version markers to actual versions
- Updated `_detect_from_manifests()` to call workspace resolution for Cargo.toml files

### Validation Results

After re-indexing project_anarchy:
- **8/8 Rust files indexed** (was 1/8 before)
- **19 Rust framework detections** (actix-web, tokio, sqlx, diesel, serde across all Cargo.toml files)
- **Workspace version resolution working** (payments/search show v4.4 from workspace root)

### Original Problem (Historical)

### Real-World Example: anarchy_commerce

```
anarchy_commerce/
├── web/                      # React frontend (TypeScript) - package.json
├── services/
│   ├── gateway/              # Node.js (BFF) - package.json
│   ├── users/                # Python/FastAPI - pyproject.toml
│   ├── payments/             # Rust - Cargo.toml
│   ├── search/               # Rust - Cargo.toml
│   └── recommendations/      # Python - pyproject.toml
├── workers/
│   ├── email-sender/         # Python - requirements.txt
│   └── image-processor/      # Rust - Cargo.toml
├── Cargo.toml                # Workspace root
└── pyproject.toml            # Python workspace root
```

### Two-Sided Fix Required

**1. project_anarchy side** - Ensure manifest files are placed correctly:
- Root `Cargo.toml` should define workspace members
- Root `pyproject.toml` should define Python workspace
- Each service should have its own manifest

**2. TheAuditor side** - manifest_parser.py should:
- Parse Cargo.toml (Rust dependencies, workspace members)
- Parse go.mod (Go dependencies, module paths)
- Traverse monorepo structures to find all manifests
- Track cross-service dependencies

### Implementation Plan

**manifest_parser.py additions:**

```python
def parse_cargo_toml(self, path: Path) -> dict:
    """Parse Cargo.toml for Rust dependencies."""
    data = self.parse_toml(path)
    return {
        'dependencies': data.get('dependencies', {}),
        'dev-dependencies': data.get('dev-dependencies', {}),
        'workspace_members': data.get('workspace', {}).get('members', [])
    }

def parse_go_mod(self, path: Path) -> dict:
    """Parse go.mod for Go dependencies."""
    # Parse require blocks and module paths
    ...

def discover_monorepo_manifests(self, root: Path) -> list[Path]:
    """Find all manifest files in a polyglot monorepo."""
    manifests = []
    for pattern in ['**/package.json', '**/pyproject.toml', '**/Cargo.toml',
                    '**/go.mod', '**/requirements.txt']:
        manifests.extend(root.glob(pattern))
    return [m for m in manifests if 'node_modules' not in str(m)]
```

### Estimated Effort

| Task | Hours |
|------|-------|
| Add Cargo.toml parser | 2 |
| Add go.mod parser | 2 |
| Monorepo traversal logic | 4 |
| Cross-language dependency tracking | 8 |
| Test with anarchy_commerce | 4 |
| **TOTAL** | **20 hours** |

### Validation

After implementation, running on project_anarchy should:
- Detect all 4 Cargo.toml files (rust_backend, anarchy_commerce root + 3 services)
- Detect all pyproject.toml files
- Detect all package.json files
- Map dependencies across language boundaries

---

**File Created**: 2025-11-22
**Last Updated**: 2025-11-22
