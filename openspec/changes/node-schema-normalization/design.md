## Context

This is the second ticket in the Node fidelity series. After `node-fidelity-infrastructure` installs the crash-on-data-loss safety net, this ticket normalizes the schema to eliminate JSON blobs and enable SQL joins.

**Stakeholders:**
- Lead Coder (Opus): Implementation
- Lead Auditor (Gemini): Verification (Phase 0 completed, line numbers documented)
- Architect: Approval

**Constraints:**
- Must complete `node-fidelity-infrastructure` first (fidelity catches migration mistakes)
- Junction tables must match parent table file+name keys (no synthetic IDs needed)
- Preserve existing working junction tables (react_component_hooks, react_hook_dependencies, import_style_names)

## Goals / Non-Goals

### Goals
1. Replace 8 JSON blob columns with junction tables
2. Enable SQL JOINs for framework analysis queries
3. Create contract tests to prevent future schema drift
4. Document extractor outputs with audit script

### Non-Goals
1. Consolidate Node tables (42 tables is acceptable)
2. Add new extractors (only restructure existing data)
3. Performance optimization (out of scope)
4. Change JavaScript extraction logic (schema-only changes)

## Decisions

### Decision 1: Use composite key (file, component_name) instead of foreign key ID

**Why:** Node tables don't have synthetic primary keys - they use (file, name) as natural keys. Adding IDs would require schema migration and break existing data.

**Pattern:**
```python
ANGULAR_MODULE_DECLARATIONS = TableSchema(
    columns=[
        Column('file', 'TEXT NOT NULL'),           # Same as parent
        Column('module_name', 'TEXT NOT NULL'),    # Same as parent
        Column('declaration_name', 'TEXT NOT NULL'),
        Column('declaration_type', 'TEXT'),
    ],
    # No FK constraint - relies on data integrity from extraction
)
```

**Tradeoff:** No referential integrity at DB level. Acceptable because:
- Extraction always produces parent+children together
- Fidelity control catches missing data
- Simpler schema without ID management

### Decision 2: Parse JSON in database method, not storage handler

**Why:** Keeps storage handlers thin (just iteration and counting) and concentrates data transformation in one place.

**Pattern:**
```python
# node_database.py
def add_vue_component(self, ..., props_definition: dict | None = None, ...):
    # Store parent record
    self.generic_batches['vue_components'].append((file, name, ...))

    # Parse and store children
    if props_definition:
        for prop_name, prop_info in props_definition.items():
            self.generic_batches['vue_component_props'].append((
                file, name, prop_name, prop_info.get('type'), ...
            ))
```

**Alternative:** Parse in storage handler. Rejected because:
- Duplicates JSON parsing logic across handlers
- Handler becomes responsible for data transformation (not its job)
- Harder to test database layer independently

### Decision 3: Remove JSON columns only after junction tables verified

**Why:** Safer migration - can rollback if junction tables have issues.

**Migration order:**
1. Add junction tables to schema
2. Modify add_* methods to populate junction tables
3. Run full pipeline, verify junction data correct
4. Remove JSON columns from schema
5. Regenerate codegen

### Decision 4: Contract tests verify schema structure, not data content

**Why:** Content validation is fidelity control's job. Contract tests prevent schema definition drift.

**Test categories:**
1. **Structural:** Table exists, columns correct, indexes present
2. **Negative:** No JSON blob columns remain
3. **Integration:** Handlers and methods exist for all tables
4. **Consistency:** Node and Python patterns align

### Decision 5: Handle multiple Vue extractor output formats

**Why:** TypeScript extractor produces different JSON structures based on Vue syntax variant. Implementation must handle all.

**Vue Props Format Variants (Ground Truth from typescript_impl.py):**

**Format 1: TypeScript defineProps with object syntax**
```json
{
  "name": { "type": "String", "required": true, "default": null },
  "age": { "type": "Number", "required": false, "default": 18 }
}
```

**Format 2: Options API with simple types**
```json
{
  "name": "String",
  "age": "Number"
}
```

**Format 3: Mixed (some detailed, some simple)**
```json
{
  "name": { "type": "String", "required": true },
  "count": "Number"
}
```

**Implementation Pattern (handle all formats):**
```python
for prop_name, prop_info in props_definition.items():
    if isinstance(prop_info, dict):
        # Detailed format: {"type": "String", "required": true, ...}
        prop_type = prop_info.get('type')
        is_required = prop_info.get('required', False)
        default_value = prop_info.get('default')
    else:
        # Simple format: "String"
        prop_type = str(prop_info) if prop_info else None
        is_required = False
        default_value = None
```

**Vue Emits Format Variants:**

**Format 1: Array of strings** (most common)
```json
["update", "delete", "change"]
```
Note: When emits is array, convert to dict: `{"update": {}, "delete": {}, "change": {}}`

**Format 2: Object with payload types**
```json
{
  "update": { "payload_type": "UpdatePayload" },
  "delete": null
}
```

**Vue Setup Returns Format:**

Always a dict mapping return names to their types:
```json
{
  "count": { "type": "ref<number>" },
  "increment": { "type": "function" },
  "user": "ComputedRef<User>"
}
```

**Angular Module Arrays Format:**

All four arrays (declarations, imports, providers, exports) are simple string arrays:
```json
{
  "declarations": ["AppComponent", "HeaderComponent"],
  "imports": ["CommonModule", "FormsModule"],
  "providers": ["AuthService", "ApiService"],
  "exports": ["SharedComponent"]
}
```

## Risks / Trade-offs

### Risk 1: Extractor output doesn't match expected JSON structure

**Likelihood:** MEDIUM - JS extractors may produce varied formats
**Impact:** Junction tables get wrong/missing data
**Mitigation:** Audit script generates ground truth before implementation. Verify extractor output matches expected format.

### Risk 2: Breaking existing queries that read JSON columns

**Likelihood:** LOW - JSON columns aren't queryable anyway (that's the problem)
**Impact:** Any code parsing JSON from DB breaks
**Mitigation:** Grep codebase for column names before removing

### Risk 3: Angular module junction tables are 4x the implementation work

**Likelihood:** HIGH - 4 arrays to normalize vs 2 for Vue
**Impact:** More code, more tests, more chances for bugs
**Mitigation:** Implement one at a time, test after each

## Open Questions

1. **Q:** Should we add explicit PKs (id column) to junction tables?
   **A:** No. Composite natural key (file, parent_name, child_name) is sufficient. Adding IDs adds complexity without benefit.

2. **Q:** What if an extractor output field is missing from expected structure?
   **A:** Hard fail (ZERO FALLBACK). The audit script documents expected output - if extraction differs, fix extraction or update expectations.

3. **Q:** Should two-discriminator pattern be applied to all consolidated tables?
   **A:** Analyze case-by-case. Only add discriminators where types are genuinely different (not just subtypes of same concept).
