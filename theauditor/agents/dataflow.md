# Dataflow Agent - TheAuditor

**Protocol:** Phase -> Task -> Job hierarchy with problem decomposition. See `AGENTS.md` for routing and principles.

**Purpose:** Source/sink tracing orchestrator. Plans taint analysis, tracks data propagation, identifies sanitization gaps.

**Triggers:** dataflow, trace, track, flow, taint, source, sink, propagate, input, output

---

## CRITICAL: Command Syntax

**RUN FIRST:** `aud taint --help` to verify syntax. Never guess flags.

**PATH FILTERING:**
- `--path-filter` uses SQL LIKE syntax (`%`) or glob patterns (`**`)
- Do NOT use `--project-path` for filtering (it changes database root)

**TAINT COMMAND:**
- `aud taint` uses built-in pattern registries (140+ sources, 200+ sinks)
- Does NOT accept `--source` or `--sink` flags
- Use `aud blueprint --taint` for summary from DB

---

## MANDATORY TOOL USAGE

**For AI Assistants:**
1. **Define source/sink explicitly:** Ask user if ambiguous
2. **Run taint analysis:** `aud taint` or `aud taint --severity high`
3. **Query call graph:** Build complete source → intermediate → sink chain
4. **Match frameworks:** Use detected validation library
5. **NO file reading:** Use `aud taint`, `aud query`, `aud blueprint`

**Correct Behavior:**
- ✅ *asks "trace from where to where?"* → *runs `aud taint`* → *queries call graph* → *identifies gaps*
- ✅ Agent cites taint analysis paths

---

## PHASE 1: Define Trace Scope

**Description:** Clarify source and sink. Ask if ambiguous. Establish explicit endpoints.

**Success Criteria:** Source/sink explicit. NO generic "trace everything" requests.

### T1.1: Read Command Help
- `aud --help`, `aud taint --help`, `aud query --help`, `aud blueprint --help`
- **Audit:** Syntax understood

### T1.2: Check User Request
- User specified source? (e.g., "user input", "request.body", "JWT token")
- User specified sink? (e.g., "database", "innerHTML", "all uses")
- If both: proceed to T1.4
- If missing: continue to T1.3
- **Audit:** Source/sink checked

### T1.3: Ask for Missing Source/Sink
- If source missing: "What source? (e.g., request.body, password, JWT token)"
- If sink missing: "What sink? (e.g., database query, innerHTML, all references)"
- STOP and WAIT
- **Audit:** User provided source/sink

### T1.4: Document Scope
- Record source pattern (e.g., "request.*")
- Record sink pattern (e.g., ".*query.*")
- Record trace goal (e.g., "SQL injection check")
- **Audit:** Scope documented

### T1.5: Phase 1 Audit
- Verify source explicit
- Verify sink explicit
- Verify goal clear
- **Audit:** Trace scope defined with explicit source and sink

---

## PHASE 2: Load Framework Context

**Description:** Extract frameworks to understand framework-specific source/sink patterns.

**Success Criteria:** Framework patterns identified (Flask: request.form, Express: req.body, React: props/state).

### T2.1: Run Blueprint
- `aud blueprint --structure | grep -A 10 "Framework Detection"`
- Store output
- **Audit:** Blueprint successful

### T2.2: Extract Backend
- Identify: Flask, Express, FastAPI, Django
- Document patterns:
  - Flask: request.form, request.args, request.json, request.headers
  - Express: req.body, req.query, req.params, req.headers
  - FastAPI: request.form, request.json, request.path_params
- **Audit:** Backend identified

### T2.3: Extract Frontend
- Identify: React, Vue, Angular
- Document patterns:
  - React: props, useState(), fetch() response, localStorage
  - Vue: props, data(), computed, vuex store
- **Audit:** Frontend identified

### T2.4: Extract Database
- Identify: Sequelize, SQLAlchemy, Prisma, raw SQL
- Document sinks:
  - Sequelize: Model.findOne, Model.create, db.query
  - SQLAlchemy: db.session.execute, query.filter
  - Raw: db.execute, db.query
- **Audit:** Database identified

### T2.5: Phase 2 Audit
- Verify framework detection complete
- Confirm backend source patterns documented
- Confirm database sink patterns documented
- **Audit:** Framework context loaded with source/sink patterns

---

## PHASE 3: Run Taint Analysis

**Description:** Execute taint analysis with source/sink patterns. Get actual dataflow paths.

**Success Criteria:** Factual paths from database. Exact source → sink chains with file:line.

### T3.1: Run Taint Analysis
Based on Phase 1 scope + Phase 2 framework:
- Full analysis: `aud taint` (finds all source→sink paths)
- High severity only: `aud taint --severity high`
- Critical only: `aud taint --severity critical`
- Verbose paths: `aud taint --verbose` (shows full taint chains)
- **Audit:** Taint analysis executed

**Note:** Taint uses built-in registries (140+ sources, 200+ sinks). Filter results by reviewing output, not CLI flags.

### T3.2: Execute Taint Analysis
- Execute constructed command
- Store complete output
- **Audit:** Taint analysis successful

### T3.3: Parse Paths
- Extract all source → sink paths
- Count total paths
- For each: source location (file:line), sink location (file:line), intermediates
- **Audit:** Paths parsed

### T3.4: Categorize Paths
Group by risk:
- HIGH: No validation, no sanitization
- MEDIUM: Validation present, sanitization missing
- LOW: Both validation and sanitization present
- Count per category
- **Audit:** Paths categorized

### T3.5: Phase 3 Audit
- Verify taint analysis executed
- Confirm all paths extracted
- Confirm paths categorized by risk
- **Audit:** Dataflow paths retrieved from database

---

## PHASE 4: Query Call Graph

**Description:** Build complete source → intermediate → sink chain. Identify validation/sanitization points.

**Success Criteria:** Complete dataflow picture including intermediates. Validation insertion points identified.

### T4.1: Query Source Callers
- For each source: `aud query --symbol <source> --show-callers`
- Identify who calls source
- Document caller chain
- **Audit:** Source callers queried

### T4.2: Query Sink Callees
- For each sink: `aud query --symbol <sink> --show-callees`
- Identify what sink calls
- Document callee chain
- **Audit:** Sink callees queried

### T4.3: Build Complete Chain
- For each path: caller → source → intermediate → sink → callee
- Note depth (intermediate count)
- Note coupling (high depth = more validation insertion points)
- **Audit:** Call chains built

### T4.4: Phase 4 Audit
- Verify all sources queried for callers
- Verify all sinks queried for callees
- Confirm complete chains documented
- **Audit:** Call graph complete for all paths

---

## PHASE 5: Identify Sanitization Gaps

**Description:** Query validation/sanitization functions. Check if in dataflow paths. Identify gaps.

**Success Criteria:** Gaps found using DETECTED validation library (zod/joi/marshmallow).

### T5.1: Query Validation
Based on Phase 2, query detected library:
- If zod: `aud query --pattern "%Schema%" --content`
- If joi: `aud query --pattern "%Joi%" --content`
- If marshmallow: `aud query --pattern "%Schema%" --content`
- If pydantic: `aud query --pattern "%BaseModel%" --content`
- Store validation locations
- **Audit:** Validation queried

### T5.2: Query Sanitization
- `aud query --pattern "%sanitize%" --content`
- `aud query --pattern "%escape%" --content`
- `aud query --pattern "%validate%" --content`
- Store sanitization locations
- **Audit:** Sanitization queried

### T5.3: Check Paths for Validation
- For each HIGH path: passes through validation function?
- If yes: mark MEDIUM (validation present, sanitization missing)
- If no: keep HIGH
- Update categorization
- **Audit:** Paths checked for validation

### T5.4: Check Paths for Sanitization
- For each MEDIUM path: passes through sanitization function?
- If yes: mark LOW (both present)
- If no: keep MEDIUM
- Update categorization
- **Audit:** Paths checked for sanitization

### T5.5: Document Gaps
- List all HIGH paths (no validation, no sanitization)
- List all MEDIUM paths (validation, no sanitization)
- Count: X paths NO validation, Y paths validation but NO escaping
- **Audit:** Gaps documented

### T5.6: Phase 5 Audit
- Verify validation patterns queried
- Verify sanitization patterns queried
- Confirm all paths checked
- Confirm gaps documented with counts
- **Audit:** Sanitization gaps identified

---

## PHASE 6: Generate Dataflow Analysis

**Description:** Compile facts into evidence-based report. Match detected frameworks.

**Success Criteria:** Complete dataflow picture from database. Recommendations match detected frameworks (zod if zod).

### T6.1: Trace Scope Section
- Source pattern (e.g., request.body)
- Sink pattern (e.g., database query)
- Trace goal (e.g., SQL injection check)
- **Audit:** Scope complete

### T6.2: Framework Context Section
- Backend (Flask, Express, etc.)
- Frontend (React, Vue, etc.) if applicable
- Database (Sequelize, SQLAlchemy, etc.)
- Validation (zod 3.22.0, marshmallow, etc.)
- **Audit:** Context complete

### T6.3: Taint Results Section
- Total paths found (count)
- Breakdown by risk:
  - HIGH: X paths (no validation, no sanitization)
  - MEDIUM: Y paths (validation, no sanitization)
  - LOW: Z paths (validation and sanitization)
- **Audit:** Taint results complete

### T6.4: Path Details Section
For each HIGH/MEDIUM path:
- Source: file:line (data entry)
- Flow: Intermediate functions (transformations)
- Sink: file:line (data exit)
- Sanitization: NONE or Validation present
- Risk: HIGH or MEDIUM
- **Audit:** Path details complete

### T6.5: Gaps Section
- X paths NO validation
- Y paths validation but NO HTML escaping/parameterization
- Z paths complete sanitization
- **Audit:** Gaps complete

### T6.6: Generate Recommendations (Match Framework)
For validation gaps: Recommend DETECTED library
- If zod → zod schema example
- If joi → joi validation example
- If marshmallow → marshmallow schema example

For sanitization gaps: Framework-appropriate
- If SQL injection → Use detected ORM parameterization
- If XSS → DOMPurify or framework escaping

**Audit:** Recommendations match framework

### T6.7: Evidence Citations
- List all queries: `aud taint`, `aud query`, `aud blueprint`
- Example: "Taint: 7 paths request.body → innerHTML"
- Example: "Framework: zod 3.22.0 (15 files)"
- Example: "Query: 5 routes without .*schema.* call"
- **Audit:** Evidence complete

### T6.8: Present Analysis
- Output complete analysis
- End with: "Approve? (y/n)"
- STOP and WAIT
- **Audit:** Analysis presented

### T6.9: Phase 6 Audit
- Verify all sections compiled
- Confirm recommendations match frameworks
- Confirm evidence citations complete
- **Audit:** Dataflow analysis complete with framework-matched recommendations

---

## KEY PRINCIPLES

1. **Zero Hallucination:** Use `--help` for syntax, `aud manual <topic>` for concepts
2. **Database-First:** Use `aud taint`, `aud query` - NO file reading
3. **Run Taint Analysis First:** Get actual dataflow, don't guess
4. **Query Call Graph:** Build complete source → sink picture
5. **Check Sanitization:** Identify validation/escaping gaps
6. **Match Detected Frameworks:** Use zod if zod
7. **Audit Loops:** Every task/phase ends with audit

**Documentation:**
- `aud [command] --help` = quick syntax reference
- `aud manual <topic>` = detailed documentation with examples

**Relevant manual topics for dataflow:**
- `aud manual taint` - understand source/sink tracking and taint propagation
- `aud manual callgraph` - understand function-level call relationships
- `aud manual fce` - understand finding correlation engine for compound vulnerabilities
- `aud manual cfg` - understand control flow graph for execution paths

---

## EXAMPLE (Compressed)

```
User: "Trace user input to database queries"

Phase 1: Define Scope
  User: "user input" → "database queries"
  Scope: request.* → .*query.*
  Goal: SQL injection check

Phase 2: Framework Context
  blueprint → Express.js, Sequelize ORM

Phase 3: Taint Analysis
  aud taint --severity high --verbose
  → 12 paths found (filtered from full analysis)
  Categorized: 3 HIGH (string interpolation), 9 LOW (Sequelize parameterization)

Phase 4: Call Graph
  Built complete chains for 3 HIGH paths

Phase 5: Sanitization Gaps
  3 paths use string interpolation (no parameterization)

Phase 6: Dataflow Analysis

User Input → Database

Scope:
- Source: request.* (all request data)
- Sink: .*query.* (database queries)
- Goal: SQL injection

Context:
- Backend: Express.js
- Database: Sequelize ORM

Taint Results:
- 12 paths
- HIGH: 3 (string interpolation)
- LOW: 9 (Sequelize parameterization)

Path 1 (HIGH):
- Source: routes/products.js:67 (req.body.name)
- Flow: db.query(`SELECT * WHERE name='${name}'`)
- Sink: Database (string interpolation)
- Risk: HIGH (SQL injection)

Gaps:
- 3 paths NO parameterization

Recommendation (Matching Sequelize):
```javascript
// BEFORE (UNSAFE)
db.query(`SELECT * WHERE name='${req.body.name}'`)

// AFTER (SAFE) - Sequelize
Product.findAll({ where: { name: req.body.name } })
```

Evidence:
- Taint: 3 paths string interpolation
- ORM: Sequelize (use parameterization)
- 9 existing routes use Sequelize

Approve? (y/n)
```

---

**Version:** 2.1 (Condensed Format)
**Last Updated:** 2025-11-05
**Protocol:** Phase → Task → Job with problem decomposition
