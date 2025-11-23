# Implementation Ticket: `aud explain` Command

**Ticket ID**: TAUD-EXPLAIN-001
**Priority**: HIGH
**Created**: 2025-11-23
**Author**: Claude Sonnet (AI Coder)
**For**: Next AI implementing this feature

---

## Problem Statement

### The "Query vs Read" Gap

AI assistants using TheAuditor default to reading files instead of querying the indexed database because:

1. **Query results lack code context** - Seeing "line 42 calls X" isn't enough; we want to see the actual line
2. **Multiple queries needed** - To understand a file, we run 5-6 separate queries (symbols, callers, callees, dependencies, etc.)
3. **Habit** - AI is trained to "read code to understand" not "query relationships"

### Evidence from Testing Session

When investigating `OrderDetails.tsx`:
- AI ran `aud query --symbol` but still wanted to read the file
- AI manually queried SQLite to understand data structure
- AI read source files to see "how" not just "that"

### The Insight

> "If I query instead of read: structured data, don't burn context window, can JOIN across relationships, more precise answers"

But query results need **enough context** that file reading becomes unnecessary.

---

## Solution: `aud explain <target>`

A single command that provides comprehensive context about any file, symbol, or component - eliminating the need to read raw files.

### Core Concept

```bash
aud explain OrderDetails.tsx
```

Returns EVERYTHING needed to understand that file:
- Symbols defined
- Hooks used (for React)
- Dependencies (what it imports)
- Dependents (who imports it)
- Outgoing calls (what it calls)
- Incoming calls (who calls its exports)
- **Code snippets** for key patterns

### Extension: `--show-code` Flag

Available on `aud explain` and existing `aud query` commands:

```bash
aud query --symbol getAllOrders --show-callers --show-code
```

Before (current):
```
Callers (1):
  1. order.routes.ts:22
     global -> router.get
     Args: orderController.getAllOrders
```

After (with --show-code):
```
Callers (1):
  1. order.routes.ts:22
     router.get('/', requireWorker, filterByUserLocation, validate(orderQuerySchema), orderController.getAllOrders);
     └── Arg[4]: orderController.getAllOrders
```

---

## Technical Context

### Available Data in repo_index.db

| Table | Rows (PlantFlow) | Useful For |
|-------|------------------|------------|
| `symbols` | 21,765 | Function/class definitions with file:line |
| `function_call_args` | 11,139 | Calls with arguments, caller/callee |
| `react_components` | 447 | Component metadata, hooks, JSX |
| `react_hooks` | 667 | Hook usage per component |
| `variable_usage` | 35,029 | Variable references |
| `assignments` | varies | Variable assignments with sources |
| `api_endpoints` | 118 | HTTP routes with handlers |

### Available Data in graphs.db

| Table | Rows (PlantFlow) | Useful For |
|-------|------------------|------------|
| `edges` | 72,798 | Import relationships |
| `nodes` | 30,102 | File/module nodes |

### Code Snippet Retrieval

File contents are NOT in the database. To show code snippets:
1. Query returns `file` and `line` columns
2. Read just that line (or line ± context) from disk
3. Cache recently accessed files for performance

This is acceptable because:
- Reading 1-3 lines is cheap
- We're not dumping whole files into context
- The structured query data tells us WHICH lines matter

---

## Implementation Specification

### Command Signature

```bash
aud explain <target> [OPTIONS]

Arguments:
  target              File path, symbol name, or component name (auto-detected)

Options:
  --show-code         Include source code snippets (default: True for explain)
  --depth N           Call graph depth (default: 1)
  --format FORMAT     Output format: text, json (default: text)
  --section SECTION   Only show specific section (symbols, deps, callers, etc.)
```

### Target Auto-Detection

```python
def detect_target_type(target: str) -> str:
    if target.endswith(('.ts', '.tsx', '.js', '.jsx', '.py')):
        return 'file'
    if '.' in target and target[0].isupper():  # OrderController.getAllOrders
        return 'symbol'
    if target[0].isupper():  # POSSale (component or class)
        # Check react_components first, then symbols
        return 'component' if in_react_components(target) else 'symbol'
    return 'symbol'  # Default to symbol search
```

### Output Structure for File Target

```
================================================================================
EXPLAIN: frontend/src/pages/dashboard/OrderDetails.tsx
================================================================================

SYMBOLS DEFINED (5):
  1. OrderDetails (function) - line 45
     export default function OrderDetails() { ... }
  2. handleRefund (function) - line 234
     const handleRefund = async (orderId: string) => { ... }
  3. OrderItem (interface) - line 12
     interface OrderItem { product_id: string; quantity: number; ... }
  ...

REACT HOOKS USED (8):
  - useState (lines 47, 52, 58)
  - useQuery (line 63)
  - useMutation (line 89)
  - useParams (line 46)
  ...

DEPENDENCIES (12 imports):
  1. react (external)
  2. @tanstack/react-query (external)
  3. @/lib/api (internal) -> frontend/src/lib/api.ts
  4. @/types/order (internal) -> frontend/src/types/order.ts
  ...

DEPENDENTS (0 files import this):
  (none - this is a page/route component)

OUTGOING CALLS (23):
  1. line 95: api.orders.getById(orderId)
     const { data: order } = useQuery({ queryFn: () => api.orders.getById(orderId) });
  2. line 156: api.orders.refund(orderId, refundData)
     await api.orders.refund(orderId, { items: selectedItems, reason });
  ...

INCOMING CALLS (0):
  (none - exports are not called, only rendered by router)

PATTERN MATCHES (from active refactor profile):
  ⚠ Rule 'returns-variant-state': 28 matches
    - line 67: order.items.map(item => ...)
    - line 89: line.product_id
    - line 134: returnLines.forEach(...)
    ...

================================================================================
```

### Output Structure for Symbol Target

```
================================================================================
EXPLAIN: OrderController.createOrder
================================================================================

DEFINITION:
  File: backend/src/controllers/order.controller.ts:147
  Type: async method
  Signature: (req: Request, res: Response) => Promise<void>

  Code:
    147: async createOrder(req: Request, res: Response): Promise<void> {
    148:   try {
    149:     const { customer_id, location_id, items, order_type } = req.body;
    150:     const order = await orderService.createOrder({
    ...

CALLERS (2):
  1. backend/src/routes/order.routes.ts:27
     router.post('/', requireWorker, requireLocationAccess(...), validate(createOrderSchema), orderController.createOrder);
     └── Passed as callback to router.post

  2. (none other)

CALLEES (3):
  1. line 150: orderService.createOrder(...)
     -> backend/src/services/order.service.ts:45
  2. line 178: res.status(201).json(...)
  3. line 183: logger.error(...)

PARAMETERS:
  - req: Request (Express request object)
  - res: Response (Express response object)

RELATED SYMBOLS:
  - orderService.createOrder (called by this)
  - createOrderSchema (validates input)
  - OrderController.getAllOrders (sibling method)

================================================================================
```

### `--show-code` Implementation for Query Commands

Add to existing query output:

```python
def format_caller_with_code(caller: dict, show_code: bool) -> str:
    base = f"{caller['file']}:{caller['line']}\n"
    base += f"   {caller['caller_function']} -> {caller['callee_function']}\n"
    base += f"   Args: {caller['arguments']}"

    if show_code:
        code_line = read_line_from_file(caller['file'], caller['line'])
        base += f"\n   Code: {code_line.strip()}"

    return base
```

---

## Database Queries Required

### For File Explain

```sql
-- Symbols in file
SELECT name, type, line, type_annotation, parameters
FROM symbols WHERE path = ?;

-- React hooks
SELECT hook_name, line
FROM react_hooks WHERE file = ?;

-- Dependencies (outgoing imports)
SELECT target, type FROM edges
WHERE source = ? AND graph_type = 'import';

-- Dependents (incoming imports)
SELECT source FROM edges
WHERE target LIKE ? AND graph_type = 'import';

-- Outgoing calls
SELECT callee_function, line, argument_expr
FROM function_call_args WHERE file = ?;

-- Incoming calls (to exports from this file)
SELECT file, line, caller_function, argument_expr
FROM function_call_args
WHERE callee_function IN (SELECT name FROM symbols WHERE path = ?);
```

### For Symbol Explain

```sql
-- Definition
SELECT path, name, type, line, type_annotation, parameters
FROM symbols WHERE name = ? OR name LIKE ?;

-- Callers
SELECT file, line, caller_function, argument_expr
FROM function_call_args
WHERE callee_function = ? OR argument_expr LIKE ?;

-- Callees
SELECT callee_function, line, argument_expr
FROM function_call_args
WHERE file = ? AND line BETWEEN ? AND ?;
```

---

## File Structure

```
theauditor/
├── commands/
│   ├── explain.py          # NEW: Main explain command
│   └── query.py            # MODIFY: Add --show-code flag
├── context/
│   └── explain_formatter.py # NEW: Output formatting
└── utils/
    └── code_snippets.py     # NEW: Line reading with caching
```

---

## Acceptance Criteria

### Must Have (MVP)

- [ ] `aud explain <file.tsx>` returns symbols, hooks, dependencies, dependents, calls
- [ ] `aud explain <Symbol.method>` returns definition, callers, callees
- [ ] `--show-code` included by default for explain
- [ ] Code snippets show actual source lines (read from disk)
- [ ] Auto-detect target type (file vs symbol vs component)

### Should Have

- [ ] `--show-code` flag added to `aud query --show-callers`
- [ ] `--show-code` flag added to `aud query --show-callees`
- [ ] `--depth N` for call graph traversal
- [ ] `--section` to filter output (only show deps, only show callers, etc.)
- [ ] Integration with active refactor profile (show pattern matches)

### Nice to Have

- [ ] `--format json` for programmatic consumption
- [ ] Caching of recently read files for performance
- [ ] Fuzzy target matching with suggestions (like query now has)
- [ ] `aud explain --interactive` for drill-down exploration

---

## Testing Plan

### Test Cases

1. **File explain - Frontend component**
   ```bash
   aud explain frontend/src/pages/dashboard/OrderDetails.tsx
   ```
   Expect: Symbols, hooks, deps, no dependents (page component), outgoing API calls

2. **File explain - Backend controller**
   ```bash
   aud explain backend/src/controllers/order.controller.ts
   ```
   Expect: Class + methods, no hooks, deps, dependents (routes), incoming + outgoing calls

3. **Symbol explain - Method**
   ```bash
   aud explain OrderController.createOrder
   ```
   Expect: Definition with code, callers (routes), callees (service)

4. **Symbol explain - Fuzzy match**
   ```bash
   aud explain createOrder
   ```
   Expect: Resolves to OrderController.createOrder or suggests options

5. **Component explain**
   ```bash
   aud explain POSSale
   ```
   Expect: Component info, hooks (24), child components, props

6. **--show-code on query**
   ```bash
   aud query --symbol getAllOrders --show-callers --show-code
   ```
   Expect: Caller info + actual source line

### Verification Command

After implementation:
```bash
aud explain frontend/src/pages/dashboard/OrderDetails.tsx | head -50
# Should show structured output with code snippets, not empty/error
```

---

## Agent Integration

### Update Planning Agent

Add to `.claude/commands/theauditor/planning.md`:
```markdown
**Steps**
1. Run `aud explain <target>` to get comprehensive context about the file/symbol.
2. Run `aud blueprint --structure` if architectural context needed.
...
```

### Update Refactor Agent

Add to `.claude/commands/theauditor/refactor.md`:
```markdown
**Steps**
1. Run `aud explain <target>` to understand the file before modifying.
2. Run `aud deadcode` to verify file is actively used.
...
```

### CLAUDE.md Trigger

Consider adding "explain" as a trigger word:
```markdown
- "explain", "understand", "what does", "how does" => suggest `aud explain <target>`
```

---

## Implementation Notes

### Performance Considerations

- Reading source lines from disk is I/O bound
- Cache last N files read (LRU cache, N=20)
- Only read lines actually displayed (don't preload entire file)
- For large outputs, consider pagination or `--limit`

### Edge Cases

1. **Binary files** - Skip code snippets, show metadata only
2. **Deleted files** - Show "file not found" for code snippets, still show indexed data
3. **Very long lines** - Truncate at 120 chars with `...`
4. **Multi-line expressions** - Show line ± 1 context if expression spans lines

### Error Handling

```python
def read_source_line(file: str, line: int) -> str:
    try:
        # ... read line
    except FileNotFoundError:
        return "(file not found on disk - showing indexed data only)"
    except Exception as e:
        return f"(error reading: {e})"
```

---

## Handoff Checklist

For the implementing AI:

- [ ] Read this ticket fully
- [ ] Check `aud query --help` for existing patterns to follow
- [ ] Check `theauditor/commands/query.py` for code structure
- [ ] Run `aud explain --help` after implementation to verify help text
- [ ] Test all 6 test cases above
- [ ] Update agents after implementation
- [ ] Run on PlantFlow to verify real-world output

---

## Success Metrics

After implementation, AI assistants should:

1. **Default to `aud explain`** instead of reading files
2. **Reduce file reads by 80%** in typical refactoring workflows
3. **Get comprehensive context in one command** instead of 5-6 queries
4. **See actual code** without burning context window on full files

---

*End of ticket*
