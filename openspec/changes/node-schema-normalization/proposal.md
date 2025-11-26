## Prerequisites Verification (BLOCKING)

**This ticket CANNOT start until `node-fidelity-infrastructure` is 100% complete.**

Before implementation, verify ALL of the following:

```bash
# 1. Check prerequisite ticket status
openspec list | grep node-fidelity-infrastructure
# REQUIRED: 52/52 tasks (100% complete)

# 2. Verify 9 add_* methods exist in node_database.py
grep -c "def add_sequelize_model\|def add_sequelize_association\|def add_bullmq_queue\|def add_bullmq_worker\|def add_angular_component\|def add_angular_service\|def add_angular_module\|def add_angular_guard\|def add_di_injection" theauditor/indexer/database/node_database.py
# REQUIRED: 9 (all methods created by prerequisite)

# 3. Verify no direct cursor access in node_storage.py
grep -c "cursor = self.db_manager.conn.cursor()" theauditor/indexer/storage/node_storage.py
# REQUIRED: 0 (all handlers refactored by prerequisite)

# 4. Verify fidelity infrastructure active
grep -c "_extraction_manifest" theauditor/indexer/extractors/javascript.py
# REQUIRED: 1+ (manifest generation added by prerequisite)
```

**If ANY check fails: STOP. Complete `node-fidelity-infrastructure` first.**

---

## Why

After `node-fidelity-infrastructure` completes, Node extraction will have fidelity control but still have **SCHEMA QUALITY ISSUES** that block SQL joins and precise querying:

1. **8 JSON blob columns** - Can't query "Which module imports AuthModule?" without parsing JSON
2. **No two-discriminator pattern** - Can't distinguish framework-specific vs general data
3. **No contract tests** - Schema can drift without detection
4. **No extractor audit script** - Can't verify extractor outputs match schema

**Evidence from Lead Auditor Verification (2025-11-26):**
| Table | Line | Column(s) | Problem |
|-------|------|-----------|---------|
| `vue_components` | 150 | `props_definition`, `emits_definition`, `setup_return` | TEXT (JSON blobs) |
| `angular_components` | 335 | `style_paths` | TEXT (JSON blob) |
| `angular_modules` | 370 | `declarations`, `imports`, `providers`, `exports` | TEXT (JSON blobs) |

**Dependency:** Requires `node-fidelity-infrastructure` to be completed first (fidelity control catches migration mistakes).

## What Changes

### Phase 3: Schema Normalization (Junction Tables)

1. **Create Vue junction tables:**
   - `vue_component_props` (file, component_name, prop_name, prop_type, is_required, default_value)
   - `vue_component_emits` (file, component_name, emit_name, payload_type)
   - `vue_component_setup_returns` (file, component_name, return_name, return_type)
   - Remove `props_definition`, `emits_definition`, `setup_return` from `vue_components`

2. **Create Angular junction tables:**
   - `angular_component_styles` (file, component_name, style_path) - replaces `style_paths` JSON
   - `angular_module_declarations` (file, module_name, declaration_name, declaration_type)
   - `angular_module_imports` (file, module_name, imported_module)
   - `angular_module_providers` (file, module_name, provider_name, provider_type)
   - `angular_module_exports` (file, module_name, exported_name)
   - Remove JSON columns from parent tables

3. **Update database methods:**
   - Modify `add_vue_component()` to insert parent -> get ID -> insert children
   - Modify `add_angular_module()` to use ID return pattern
   - Add `add_vue_component_prop()`, `add_vue_component_emit()`, etc.

4. **Update storage handlers:**
   - Modify handlers to parse JSON and insert to junction tables

### Phase 4: Two-Discriminator Pattern + Contract Tests

1. **Add discriminator columns where applicable:**
   - Analyze Python schema for pattern applicability
   - Add `*_kind` columns to tables that consolidate multiple types

2. **Create `tests/test_node_schema_contract.py`:**
   - Test table counts match expected
   - Test no JSON blob columns remain (grep for TEXT columns with "definition", "paths", etc.)
   - Test junction table FKs exist
   - Test all handlers use batched methods

3. **Create `scripts/audit_node_extractors.py`:**
   - Mirror `scripts/audit_extractors.py` for Python
   - Generate `node_extractor_truth.txt`
   - Document what each JS extractor actually outputs

4. **Regenerate codegen:**
   - Run codegen after schema changes
   - Update `generated_types.py`, `generated_cache.py`, `generated_accessors.py`

## Impact

### Affected Files (8+)
| File | Purpose | Changes |
|------|---------|---------|
| `theauditor/indexer/schemas/node_schema.py` | Schema definitions | Add 7 junction tables, remove JSON columns |
| `theauditor/indexer/database/node_database.py` | Database mixin | Add junction table methods, modify parent methods |
| `theauditor/indexer/storage/node_storage.py` | Storage handlers | Modify handlers for junction pattern |
| `tests/test_node_schema_contract.py` | Contract tests | CREATE (new file) |
| `scripts/audit_node_extractors.py` | Extractor audit | CREATE (new file) |
| `node_extractor_truth.txt` | Ground truth doc | CREATE (new file) |
| `theauditor/indexer/schemas/generated_*.py` | Codegen output | REGENERATE |

### New Junction Tables (8)
1. `vue_component_props`
2. `vue_component_emits`
3. `vue_component_setup_returns`
4. `angular_component_styles`
5. `angular_module_declarations`
6. `angular_module_imports`
7. `angular_module_providers`
8. `angular_module_exports`

### Risk Assessment
- **HIGH** - Schema changes require careful migration
- **Mitigation:** Fidelity control (from ticket 1) catches data loss during migration
- **Rollback:** Schema changes are additive (add junction tables before removing JSON columns)

## Definition of Done

- [ ] All 8 JSON blob columns replaced with junction tables
- [ ] Junction tables have proper FKs to parent tables
- [ ] `test_node_schema_contract.py` passes (target: 10+ tests)
- [ ] `audit_node_extractors.py` generates `node_extractor_truth.txt`
- [ ] `aud full --offline` completes without fidelity errors
- [ ] Codegen regenerated successfully
- [ ] `ruff check` passes on all modified files

## References

- Pre-implementation briefing: `node_receipts.md` (root)
- Python reference: `python_schema.py` (junction tables, two-discriminator pattern)
- Prerequisite ticket: `node-fidelity-infrastructure`
- teamsop.md v4.20 compliance: VERIFIED
