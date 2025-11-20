# Taint Analysis Goals & Reality Check

## What We're Supposed to Detect (Plant Codebase Examples)

### Real Attack Paths That SHOULD Be Found

Based on comprehensive exploration of plant codebase (SaaS compliance tracker):

**Plant Codebase Stats:**
- 200+ API endpoints with user input
- 1124 sources discovered by `TaintDiscovery`
- 196 sinks discovered (192 SQL, 4 file ops)
- 5073 assignments extracted
- 17677 function calls extracted
- Complex 3-tier architecture (routes → controllers → services → DB)

---

## 10 Taint Paths That SHOULD Be Detected

### 1. SQL Injection via Dashboard Metrics
```
Source: JWT token → req.accountId (dashboard.controller.ts:108)
Flow:
  req.accountId → dashboardService.getDashboardStats(accountId)
    → sequelize.query('SELECT ... WHERE account_id = :accountId', { replacements: { accountId } })
Sink: dashboard.service.ts:240 (Raw SQL query)
Path Length: 3 hops
Files: 2 (controller → service)
```

### 2. Second-Order SQL Injection via QR Stats
```
Source: req.query.worker_id (qr.registry.controller.ts)
Flow:
  req.query.worker_id → filters.worker_id
    → qrRegistryService.getQRScanStats(filters)
      → String interpolation: `${filters.worker_id ? 'AND user_id = :workerId' : ''}`
        → sequelize.query(...)
Sink: qr.registry.service.ts:416 (Template literal in SQL)
Path Length: 4 hops
Files: 2
```

### 3. Path Traversal via Template Loading
```
Source: req.body.templateName (print.routes.ts:15)
Flow:
  req.body.templateName → printService.preparePrintData(templateName, ...)
    → path.join(__dirname, '../templates/reports', `${templateName}.hbs`)
      → fs.readFile(templatePath, 'utf-8')
Sink: print.service.ts:63 (File read with user input)
Path Length: 3 hops
Files: 2
```

### 4. User Search LIKE Injection
```
Source: req.query.search (user.controller.ts:41)
Flow:
  req.query.search → filters.search
    → userService.listUsers(accountId, { search: filters.search })
      → `%${filters.search}%`
        → User.findAll({ where: { username: { [Op.iLike]: pattern } } })
Sink: user.service.ts:132 (SQL LIKE with unescaped wildcards)
Path Length: 4 hops
Files: 2
```

### 5. Plant Bulk Move (Array to SQL IN)
```
Source: req.body.plant_ids (plant.routes.ts:21)
Flow:
  req.body.plant_ids → data.plant_ids
    → plantService.transferPlants(accountId, data, userId)
      → Plant.update({ ... }, { where: { id: { [Op.in]: data.plant_ids } } })
Sink: plant.service.ts:220 (SQL WHERE IN clause)
Path Length: 3 hops
Files: 2
```

### 6. Batch Creation with Loop Iteration
```
Source: req.body.plant_count (batch.routes.ts:38)
Flow:
  req.body.plant_count → data.plant_count
    → batchService.createBatch(accountId, facilityId, data, userId)
      → for (let i = 1; i <= data.plant_count; i++)
        → Plant.bulkCreate(plants)
Sink: batch.service.ts:137 (Bulk INSERT controlled by user count)
Path Length: 4 hops (includes loop iteration)
Files: 2
```

### 7. Export Filename Header Injection
```
Source: req.params.entityType (export.routes.ts:52)
Flow:
  req.params.entityType → entityType
    → exportController.exportEntity(req, res)
      → res.setHeader('Content-Disposition', `attachment; filename="${entityType}-${entityId}.csv"`)
Sink: export.controller.ts:255 (HTTP header injection)
Path Length: 2 hops
Files: 2
```

### 8. Tenant Context Session Variable
```
Source: JWT token → req.accountId (auth.middleware.ts:31)
Flow:
  req.accountId → TenantContext.setAccountId(accountId, transaction)
    → sequelize.query('SET LOCAL app.current_account_id = :accountId', { replacements: { accountId } })
Sink: tenant.context.ts:20 (PostgreSQL session variable)
Path Length: 2 hops
Files: 3 (middleware → util → DB)
```

### 9. Audit Log Metadata Injection
```
Source: req.body.metadata.device_id (qr.scan.routes.ts)
Flow:
  req.body.metadata → metadata
    → qrRegistryService.scanQRCode(qrCode, accountId, metadata)
      → auditService.log({ metadata: { device_id: metadata.device_id } })
        → AuditLog.create({ metadata: { ... } })
Sink: qr.registry.service.ts:70 (JSON field in database)
Path Length: 4 hops
Files: 3
```

### 10. Validation Error Reflected XSS
```
Source: req.query.facility_id (compliance.routes.ts:16)
Flow:
  req.query.facility_id → validation.query.complianceReport.parse(req.query)
    → Validation error includes input: "Invalid UUID: <script>alert(1)</script>"
      → Error response → Frontend renders error.message
Sink: Error message rendered in frontend (compliance.controller.ts:32)
Path Length: 3 hops
Files: 3 (route → controller → frontend)
```

---

## What Actually Works Right Now

### Test Fixture (Simple Single-Function Path)
```
✅ WORKS: req.query.search → search → query → SQL (products.js:25-34)
Why: All in ONE function, no cross-function calls
Path Length: 4 hops
Files: 1
Result: 1 SQL injection detected
```

### Plant Codebase (Real Multi-Function Paths)
```
❌ BROKEN: All 10 paths above
Why: Taint dies at function call boundaries
Path Length Required: 2-4 hops across 2-3 files
Files: Multiple
Result: 0 detections despite 1124 sources, 196 sinks, 989 taint_flow_graph nodes
```

---

## Root Cause Analysis

### Current Implementation Issues

**Problem 1: Function Parameter Mapping**
```python
# Current placeholder approach (analysis.py:155)
param_name = 'param'  # Generic placeholder - WRONG

# What should happen:
# Call: userService.login({ email: req.body.email })
# Need to map: req.body.email → email parameter in login() function
# Requires: Function signature extraction from database
```

**Problem 2: Cross-File Call Resolution**
```python
# Current approach uses callee_file_path but doesn't continue propagation
callee_file = call.get('callee_file_path', '') or file

# Missing: After finding callee in different file, need to:
# 1. Get function signature from symbols table
# 2. Map arguments to parameters by position/name
# 3. Continue taint propagation in callee's body
```

**Problem 3: Taint Reconstruction**
```python
# _reconstruct_paths_for_sinks() checks if sink variables are tainted
# But sink detection uses sink.get('name') which is often generic like 'sql_query'
# Should check if any variable used IN the sink is tainted

# Example:
# Tainted: data.plant_ids
# Sink uses: { where: { id: { [Op.in]: data.plant_ids } } }
# Need to match: tainted var name appears in sink pattern/expression
```

---

## What Needs to Happen

### Phase 1: Parameter Mapping (CRITICAL)
- [ ] Extract function signatures from `symbols` table
- [ ] Map call arguments to function parameters by position
- [ ] Handle destructuring: `{ email, password } = req.body`
- [ ] Support named parameters, default values, rest params

### Phase 2: Cross-File Propagation (CRITICAL)
- [ ] When call has `callee_file_path`, switch context to new file
- [ ] Continue building taint_flow_graph in callee function
- [ ] Track file boundaries in path reconstruction
- [ ] Handle circular dependencies (A calls B, B calls A)

### Phase 3: Sink Variable Matching (HIGH)
- [ ] Don't just check sink.get('name')
- [ ] Check if tainted variable appears in:
  - SQL query text
  - Function call arguments
  - Assignment source expressions
- [ ] Use substring matching or AST position matching

### Phase 4: Sanitizer Detection (MEDIUM)
- [ ] Expand sanitizer list beyond basic functions
- [ ] Detect validation frameworks (Zod, joi)
- [ ] Track validation result (success/failure branches)
- [ ] Handle conditional sanitization (if validated, then safe)

---

## Success Metrics

### Minimum Viable Detection
```
Plant codebase: Detect at least 5/10 example paths
Test fixture: Continue detecting existing path
False positives: < 10% (max 20 FPs for 200 real paths)
Performance: < 2 minutes for 20K LOC codebase
```

### Full Success
```
Plant codebase: Detect all 10 example paths + discover new ones
Cross-file: Detect paths spanning 3+ files
Deep paths: Detect paths with 10+ hops
Sanitizers: Correctly exclude validated paths
False positive rate: < 5%
```

---

## Current Status: BROKEN

**Detections on plant:** 0/10 (0%)
**Detections on test fixture:** 1/1 (100%)

**Diagnosis:** Implementation works for single-function paths only. Cross-function parameter mapping not implemented.

**Next Step:** Implement function signature extraction and argument-to-parameter mapping in `_build_taint_flow_graph()`.
