# Cross-File Taint Flow Test Fixture (TypeScript)

This fixture demonstrates multi-hop taint propagation through TypeScript files:

```
User Input (controller) → Business Logic (service) → Database Sink (database)
```

## Expected Taint Paths

### Path 1: Search Query
1. **controller.ts**: `req.query.search` (SOURCE)
2. **service.ts**: `searchService.search(query)` (PROPAGATION)
3. **database.ts**: `connection.query(sql)` (SINK in try block)

### Path 2: User ID
1. **controller.ts**: `req.params.id` (SOURCE)
2. **service.ts**: `searchService.getUserById(id)` (PROPAGATION)
3. **database.ts**: `connection.execute(query)` (SINK in try block)

### Path 3: Filter Expression
1. **controller.ts**: `req.body.filter` (SOURCE)
2. **service.ts**: `searchService.filterRecords(filter)` (PROPAGATION)
3. **database.ts**: `db.raw(sql)` (SINK in try block)

## Tests

This fixture verifies:

1. **TypeScript callee_file_path resolution**: Cross-file function calls are resolved
2. **CFG try block fix**: Sinks inside try blocks are found (lines 56-67 pattern)
3. **Stage 3 path reconstruction**: Multi-hop paths are built using taint_flow_graph
4. **Cross-file taint propagation**: Taint flows through 3 files

## Critical for CFG Fix

All database operations are wrapped in **try blocks** to specifically test the TypeScript CFG fix that makes try block bodies span proper line ranges instead of single-line markers.
