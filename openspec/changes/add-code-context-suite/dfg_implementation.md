# INVESTIGATION REPORT: DFG/BFS Value Analysis for Code Context Suite

**Phase**: Pure Investigation (Report Mode Only)
**OpenSpec Change**: `add-code-context-suite`
**Objective**: Determine if DFG (Data Flow Graph) and BFS add value to the planned code context query engine
**Status**: COMPLETE
**Confidence Level**: High

---

## 1. Context Suite Overview (What's Being Built)

### Purpose:
Create a query engine that exposes TheAuditor's rich database for AI-assisted code navigation and refactoring, competing with Claude Compass but using exact queries instead of embeddings.

### Core Features Planned:

| **Feature** | **Implementation** | **Database Tables** |
|:---|:---|:---|
| **Symbol Queries** | `--symbol X --show-callers` | `function_call_args`, `symbols` |
| **File Dependencies** | `--file X --show-dependencies` | `graphs.db/edges` (import graph) |
| **API Endpoints** | `--api /route --show-handlers` | `api_endpoints` |
| **Component Trees** | `--component X --show-tree` | `react_components`, `react_hooks` |
| **Cross-Stack Tracing** | `--cross-stack` | Multi-table joins |
| **Transitive Queries** | `--depth 3` | BFS traversal through call graph |

### Architecture:
```
CLI (aud context query)
    ↓
CodeQueryEngine (theauditor/context/query.py)
    ↓
Direct SQL queries on repo_index.db + graphs.db
    ↓
Formatters (text/json/tree output)
```

### Philosophy (from proposal.md:58-69):
- **Query, Don't Summarize** - AI asks questions, gets exact answers
- **No Inference** - Direct SQL queries, no guessing
- **100% Offline** - No embeddings, no CUDA, no pgvector
- **Exact Matches** - No false positives, pure accuracy

---

## 2. BFS Analysis: Already Planned and Critical

### Current Implementation (design.md:369-406):

```python
def get_callers(self, symbol_name: str, depth: int = 1) -> List[CallSite]:
    """Find who calls a symbol (with optional transitive search).

    For depth > 1, recursively finds callers of callers using BFS.
    """
    # BFS for transitive callers
    queue = deque([(symbol_name, 0)])  # ← BFS with deque

    while queue:
        current_symbol, current_depth = queue.popleft()  # ← FIFO

        if current_depth >= depth:
            continue

        # Query function_call_args for callers
        # Add results to queue for next depth
        if current_depth + 1 < depth:
            queue.append((call_site.caller_function, current_depth + 1))
```

### Why BFS is Critical:

✅ **1. Depth-Limited Traversal**
- User specifies `--depth 3` to find callers transitively
- BFS explores level-by-level (depth 1, then 2, then 3)
- Naturally respects depth limit

✅ **2. Shortest Path First**
- AI wants to know "nearest" callers first
- BFS finds direct callers before indirect ones
- Better UX: most relevant results appear first

✅ **3. Predictable Ordering**
- BFS produces deterministic results (breadth-first order)
- Same query always returns same order
- Important for AI consistency

✅ **4. Performance**
- Max depth: 5 (prevents runaway queries)
- Visited set prevents cycles
- `deque.popleft()` is O(1) vs `list.pop(0)` O(n)

### BFS Use Cases in Context Engine:

| **Query** | **BFS Application** | **Why BFS?** |
|:---|:---|:---|
| `--symbol X --show-callers --depth 3` | Transitive caller discovery | Find all paths up to depth 3 |
| `--symbol X --show-callees --depth 2` | Transitive callee discovery | Find what X calls, recursively |
| `--file X --show-dependents --depth 3` | Transitive import graph | Who imports files that import X? |
| `--cross-stack` | Multi-hop chain tracing | Frontend → API → Service → DB |

### Verdict on BFS:

**✅ BFS IS ALREADY PLANNED AND ESSENTIAL**

- design.md:369: Explicitly implements BFS with `deque` for transitive queries
- Correct algorithm choice for depth-limited graph traversal
- No changes needed - implementation is optimal

---

## 3. DFG Analysis: Implicit Capabilities, Explicit Opportunity

### What is DFG for Context Engine?

**DFG queries would answer**:
- "What variables does function X read?"
- "What variables does function X write?"
- "Show me data flow from variable A to variable B"
- "Trace this variable through the codebase"

**This is DIFFERENT from**:
- **Call Graph**: Who calls what (already planned)
- **Taint Analysis**: Security vulnerabilities (existing feature)

### Current State: Implicit DFG Data

We HAVE the data for DFG queries:

| **DFG Capability** | **Database Table** | **What It Tracks** |
|:---|:---|:---|
| **Variable Definitions** | `assignments` | `target_var`, `source_expr`, `source_vars` |
| **Variable Uses** | `variable_usage` | `variable_name`, `usage_type`, `in_component` |
| **Function Parameters** | `function_call_args` | `argument_expr`, `param_name` |
| **Return Values** | `function_returns` | `return_expr`, `return_vars` |
| **Def-Use Chains** | `assignments.source_vars` | JSON list of source variables |

### Missing: Explicit DFG Query API

**Current Proposal Does NOT Include**:

```bash
# These queries are NOT in the proposal:
aud context query --symbol authenticateUser --show-data-flow
aud context query --variable userToken --show-def-use-chain
aud context query --trace-data --from req.body --to db.query
```

**But the data EXISTS in the database:**

```sql
-- What variables does authenticateUser read?
SELECT variable_name, line, usage_type
FROM variable_usage
WHERE in_function = 'authenticateUser';

-- What variables does authenticateUser write?
SELECT target_var, source_expr, line
FROM assignments
WHERE in_function = 'authenticateUser';

-- Trace variable userToken through assignments
SELECT a1.target_var, a2.target_var, a3.target_var
FROM assignments a1
JOIN assignments a2 ON a2.source_vars LIKE '%' || a1.target_var || '%'
JOIN assignments a3 ON a3.source_vars LIKE '%' || a2.target_var || '%'
WHERE a1.target_var = 'userToken';
```

### DFG Query Value-Add Analysis:

**Scenario 1: Refactoring a Function**

```
AI: "I want to refactor authenticateUser. Show me its data dependencies."

WITHOUT DFG queries:
- AI must manually query: "Show me callers" + "Show me callees"
- Then guess what data flows through based on call sites
- Risk: Miss hidden data dependencies

WITH DFG queries:
- aud context query --symbol authenticateUser --show-data-deps
- Returns: Reads [req.body, session.token], Writes [user.lastLogin, authCache]
- AI knows EXACT data contract
```

**Scenario 2: Tracing Variable Flow**

```
AI: "Where does userToken go after line 42?"

WITHOUT DFG queries:
- AI must manually trace through assignments table
- Complex SQL with recursive CTEs
- Slow, error-prone

WITH DFG queries:
- aud context query --variable userToken --from-line 42 --show-flow
- Returns: BFS through assignments → line 45 (sessionStore) → line 67 (redis.set)
- Fast, accurate, AI-consumable
```

**Scenario 3: Cross-Stack Data Flow**

```
AI: "Show me data flow from frontend input to database."

WITHOUT DFG queries:
- AI chains: Component query → API query → taint analysis (if available)
- Taint only shows security paths, not all data flow
- Incomplete picture

WITH DFG queries:
- aud context query --trace-data --from UserForm.email --to db.users
- Returns: COMPLETE chain through variable assignments
- Shows transformations: form.email → validateEmail(input) → createUser(validated) → db.insert(user)
```

### Proposed DFG Query Extensions:

**Extension 1: Data Dependencies Query**

```python
# theauditor/context/query.py (NEW METHOD)

def get_data_dependencies(self, symbol_name: str) -> Dict[str, Any]:
    """Get data dependencies (reads/writes) for a function.

    Returns:
        Dict with 'reads' (variable_usage) and 'writes' (assignments)
    """
    cursor = self.repo_db.cursor()

    # Variables READ by this function
    cursor.execute("""
        SELECT variable_name, line, usage_type
        FROM variable_usage
        WHERE in_function = ?
        ORDER BY line
    """, (symbol_name,))
    reads = [dict(row) for row in cursor.fetchall()]

    # Variables WRITTEN by this function
    cursor.execute("""
        SELECT target_var, source_expr, line
        FROM assignments
        WHERE in_function = ?
        ORDER BY line
    """, (symbol_name,))
    writes = [dict(row) for row in cursor.fetchall()]

    return {'reads': reads, 'writes': writes}
```

**Extension 2: Variable Flow Tracing**

```python
# theauditor/context/query.py (NEW METHOD)

def trace_variable_flow(self, var_name: str, from_file: str, depth: int = 3) -> List[Dict]:
    """Trace variable through assignments (def-use chains).

    Uses BFS through assignments.source_vars to find data flow paths.
    """
    cursor = self.repo_db.cursor()

    # BFS through assignments
    queue = deque([(var_name, from_file, 0, [])])
    visited = set()
    flows = []

    while queue:
        current_var, current_file, current_depth, path = queue.popleft()

        if current_depth >= depth:
            continue

        # Find assignments where this var is used
        cursor.execute("""
            SELECT target_var, source_expr, line, file, in_function
            FROM assignments
            WHERE file = ? AND source_vars LIKE ?
        """, (current_file, f'%{current_var}%'))

        for row in cursor.fetchall():
            step = {
                'from_var': current_var,
                'to_var': row['target_var'],
                'expr': row['source_expr'],
                'file': row['file'],
                'line': row['line'],
                'function': row['in_function']
            }

            new_path = path + [step]
            flows.append(new_path)

            # Continue BFS
            if current_depth + 1 < depth:
                queue.append((row['target_var'], row['file'], current_depth + 1, new_path))

    return flows
```

**Extension 3: CLI Integration**

```python
# theauditor/commands/context.py (ADDITIONS TO query SUBCOMMAND)

@context.command("query")
@click.option("--symbol", help="Query symbol by name")
@click.option("--variable", help="Query variable by name")  # ← NEW
# ... existing options ...
@click.option("--show-data-deps", is_flag=True, help="Show data dependencies (reads/writes)")  # ← NEW
@click.option("--show-flow", is_flag=True, help="Show variable flow (def-use chains)")  # ← NEW
@click.option("--from-file", help="Starting file for variable flow")  # ← NEW
def query(...):
    """Query code relationships from database."""

    # NEW: Data dependency queries
    if symbol and show_data_deps:
        results = engine.get_data_dependencies(symbol)

    # NEW: Variable flow tracing
    elif variable and show_flow:
        results = engine.trace_variable_flow(variable, from_file or '.', depth=depth)
```

---

## 4. Comparison: Call Graph vs Data Flow Graph

### What Context Engine Already Has (Call Graph):

```bash
aud context query --symbol authenticateUser --show-callers
# Returns: WHO calls this function (control flow)
```

**Output**:
```
Callers (3):
  1. src/middleware/auth.ts:23  authMiddleware()
  2. src/api/users.ts:105       UserController.login()
  3. src/websocket/handler.ts:89 handleConnection()
```

### What DFG Would Add (Data Flow Graph):

```bash
aud context query --symbol authenticateUser --show-data-deps
# Returns: WHAT DATA this function uses (data flow)
```

**Output**:
```
Data Dependencies for: authenticateUser

  Reads (5):
    1. req.body.email (line 43)
    2. req.body.password (line 44)
    3. config.jwtSecret (line 52)
    4. session.token (line 56)
    5. cache.users (line 60)

  Writes (3):
    1. user.lastLogin = now (line 67)
    2. authToken = jwt.sign(...) (line 70)
    3. session.userId = user.id (line 74)
```

**These are COMPLEMENTARY, not redundant**:
- **Call Graph**: "Who interacts with this code?" (control flow)
- **Data Flow Graph**: "What data does this code touch?" (data flow)

---

## 5. Integration with Existing Features

### DFG vs Taint Analysis:

| **Aspect** | **Taint Analysis** | **DFG Queries** |
|:---|:---|:---|
| **Purpose** | Find security vulnerabilities | Show data dependencies |
| **Scope** | Source → Sink paths only | All variable flows |
| **Use Case** | "Is req.body → res.send unsafe?" | "What does authenticateUser read/write?" |
| **When Run** | `aud taint-analyze` (one-time) | `aud context query` (on-demand) |
| **Output** | `.pf/raw/taint_analysis.json` (pre-computed) | Live query results |
| **Focus** | SECURITY (injection, XSS, etc.) | REFACTORING (data contracts) |

**They are COMPLEMENTARY**:
- Taint: Pre-computed security-specific data flow
- DFG: On-demand general data flow queries

### DFG vs Call Graph:

| **Query Type** | **Table** | **What It Shows** |
|:---|:---|:---|
| **Call Graph** | `function_call_args` | `authMiddleware()` calls `authenticateUser()` |
| **Data Flow Graph** | `assignments`, `variable_usage` | `authenticateUser` reads `req.body` and writes `authToken` |

**Both needed for complete context**.

---

## 6. Recommendations

### PRIMARY RECOMMENDATION: ADD DFG QUERY EXTENSIONS

**Reasoning**:
1. ✅ **Data already exists** - `assignments`, `variable_usage`, `function_returns` tables
2. ✅ **Complements call graph** - Data flow is orthogonal to control flow
3. ✅ **Fills gap in proposal** - Current design only has call/import graphs
4. ✅ **Aligns with philosophy** - Direct SQL queries, no inference, exact matches
5. ✅ **High value for refactoring** - AI needs to know data contracts to refactor safely
6. ✅ **BFS already planned** - Can reuse BFS pattern for variable flow tracing

### Specific Extensions to Add:

#### Extension 1: Data Dependencies (`--show-data-deps`)

**Command**:
```bash
aud context query --symbol authenticateUser --show-data-deps
```

**Implementation**:
- Query `variable_usage` for reads
- Query `assignments` for writes
- ~50 lines of code

**Value**: Shows EXACT data contract of a function

#### Extension 2: Variable Flow Tracing (`--show-flow`)

**Command**:
```bash
aud context query --variable userToken --from-file auth.ts --show-flow --depth 3
```

**Implementation**:
- BFS through `assignments.source_vars` JSON
- Track def-use chains transitively
- ~100 lines of code

**Value**: Traces variable transformations through codebase

#### Extension 3: Cross-Stack Data Flow (`--trace-data`)

**Command**:
```bash
aud context query --trace-data --from UserForm.email --to db.users.email
```

**Implementation**:
- Combine variable flow + call graph + component hierarchy
- Multi-hop BFS across tables
- ~150 lines of code

**Value**: Complete data flow from UI to database

### Implementation Priority:

**Phase 1 (Core Context Suite)**:
- ✅ Call graph queries (already planned)
- ✅ Import graph queries (already planned)
- ✅ BFS for transitive queries (already planned)

**Phase 2 (DFG Extensions) - RECOMMENDED**:
- ✅ Data dependencies query (`--show-data-deps`)
- ✅ Variable flow tracing (`--show-flow`)

**Phase 3 (Advanced) - Optional**:
- Cross-stack data flow (`--trace-data`)
- Data flow visualization

### Effort Estimate:

- **Extension 1** (Data deps): 2-3 hours
- **Extension 2** (Variable flow): 3-4 hours
- **Extension 3** (Cross-stack): 4-6 hours
- **Testing**: 3-4 hours
- **Documentation**: 2-3 hours

**Total**: 14-20 hours (2-3 days)

---

## 7. Final Verdict

### BFS: ✅ **ALREADY PLANNED - NO ACTION NEEDED**

- design.md:369-406 explicitly implements BFS with `deque`
- Correct algorithm for transitive caller/callee queries
- Depth-limited traversal (1-5 levels)
- Implementation is optimal

### DFG: ⚠️ **HIGH-VALUE EXTENSION - RECOMMEND ADDING**

- **Gap in current proposal**: Only call/import graphs, no data flow queries
- **Data already exists**: `assignments`, `variable_usage` tables ready to use
- **Complements call graph**: Data flow is orthogonal, both needed for refactoring
- **Aligns with philosophy**: Direct queries, no inference, exact matches
- **Minimal effort**: ~14-20 hours for full implementation
- **High ROI**: Enables safe AI-assisted refactoring by exposing data contracts

### Recommendation to Architect:

**Add DFG query extensions to OpenSpec change `add-code-context-suite`**:

1. **Extension 1**: `--show-data-deps` (reads/writes for a function)
2. **Extension 2**: `--show-flow` (trace variable through def-use chains)
3. **Optional**: `--trace-data` (cross-stack data flow)

**Why**:
- Fills critical gap (call graph without data flow is incomplete)
- Low implementation cost (data already indexed)
- High value for AI refactoring (know what data a function touches)
- Consistent with existing architecture (direct SQL queries)

**Integration**:
- Add 2 methods to `CodeQueryEngine` class
- Add 2-3 CLI flags to `aud context query`
- Reuse existing BFS pattern for transitive variable flow
- No new database tables needed

---

**Investigation complete. Recommendation: Add DFG query extensions (Phase 2) to complement existing call graph queries (Phase 1).**
