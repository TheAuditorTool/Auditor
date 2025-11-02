# Dataflow Agent - TheAuditor

**Protocol:** LLM-optimized workflow for dataflow tracing using problem decomposition and taint analysis planning.

**Purpose:** Source/sink tracing orchestrator. Plans taint analysis, tracks data propagation, identifies sanitization gaps.

**Framework:** This agent follows the Phase → Task → Job hierarchy with problem decomposition thinking (see planning.md for structure details). All phases include "Problem Solved" fields, all tasks end with audit jobs, and all phases end with phase audit tasks.

---

## TRIGGER KEYWORDS

User mentions: dataflow, trace, track, flow, taint, source, sink, propagate, input, output

---

## MANDATORY WORKFLOW STRUCTURE

### Information Architecture (Read BEFORE Starting)

**Problem Description:**
User requests dataflow tracing (e.g., "trace user input to database", "track JWT token through system"). Before running analysis, we must:
1. Define explicit source and sink (what to trace from where to where)
2. Understand framework-specific source/sink patterns (request.body vs req.query vs request.form)
3. Run taint analysis to get actual dataflow paths from database
4. Build complete call chain (source → intermediates → sink)
5. Identify sanitization gaps (validation missing, escaping missing)

**Success Criteria:**
When this analysis is complete:
- Trace scope is defined (explicit source and sink patterns)
- Framework context is loaded (backend/frontend frameworks, validation libraries)
- Taint analysis has run (source → sink dataflow paths from database)
- Call graph is queried (complete intermediate function chain)
- Sanitization gaps are identified (validation/escaping missing)
- User has evidence-based dataflow analysis with sanitization recommendations

**Prerequisites:**
Before starting analysis, ensure you understand:
1. How to use `aud --help` to verify command syntax (NEVER guess)
2. TheAuditor's database-first principle (NO file reading, use `aud taint-analyze`, `aud query`)
3. Taint analysis concepts (source, sink, dataflow path, sanitization point)
4. Framework-specific patterns (Flask vs Express vs React source/sink differences)
5. Validation library patterns (zod vs joi vs marshmallow for sanitization detection)

**Information Gathering Commands:**
```bash
$ aud --help                 # See all available commands
$ aud taint-analyze --help   # Verify taint analysis syntax
$ aud query --help           # Verify query syntax
$ aud blueprint --help       # Verify blueprint syntax
```

---

## PHASE 1: Define Trace Scope

**Description:** Clarify what source and sink to trace. Ask user if ambiguous. Establish explicit dataflow endpoints before running analysis.

**Problem Solved:** Prevents running generic taint analysis without clear goal. Forces explicit source/sink definition to ensure focused, actionable results. Avoids "trace everything" anti-pattern.

### Task 1.1: Read Command Help Documentation

**Jobs:**
- [ ] Execute: `aud --help` to see all available commands
- [ ] Execute: `aud taint-analyze --help` to verify taint syntax
- [ ] Execute: `aud query --help` to verify query options
- [ ] **Audit:** Verify command syntax understood. If audit reveals failures, amend and re-audit.

### Task 1.2: Check User Request for Source/Sink

**Jobs:**
- [ ] Check if user specified source (e.g., "user input", "request.body", "JWT token")
- [ ] Check if user specified sink (e.g., "database", "innerHTML", "all uses")
- [ ] If both specified, proceed to Task 1.3
- [ ] If missing, continue to Task 1.3 to ask user
- [ ] **Audit:** Verify source/sink checked. If audit reveals failures, amend and re-audit.

### Task 1.3: Ask User for Missing Source/Sink (If Needed)

**Jobs:**
- [ ] If source not specified, ask: "What source should I trace? (e.g., request.body, password variable, JWT token)"
- [ ] If sink not specified, ask: "What sink should I trace to? (e.g., database query, innerHTML, all references)"
- [ ] STOP and WAIT for user clarification
- [ ] **Audit:** Verify user provided source/sink. If audit reveals failures, amend and re-audit.

### Task 1.4: Document Trace Scope

**Jobs:**
- [ ] Record source pattern (e.g., "request.*" for all request data)
- [ ] Record sink pattern (e.g., ".*query.*" for database queries)
- [ ] Record trace goal (e.g., "SQL injection check", "XSS check", "JWT token flow")
- [ ] **Audit:** Verify scope documented. If audit reveals failures, amend and re-audit.

### Task 1.5: Phase 1 Audit

**Jobs:**
- [ ] Verify source pattern is explicit
- [ ] Verify sink pattern is explicit
- [ ] Verify trace goal is clear
- [ ] If any ambiguity found, return to Task 1.3 and re-audit
- [ ] **Final verification:** Trace scope defined with explicit source and sink

---

## PHASE 2: Load Framework Context

**Description:** Extract backend/frontend frameworks from database to understand framework-specific source/sink patterns.

**Problem Solved:** Provides framework-specific knowledge for source/sink patterns. Flask uses request.form, Express uses req.body, React uses props/state. Knowing framework ensures correct pattern matching in taint analysis.

### Task 2.1: Run Blueprint Framework Detection

**Jobs:**
- [ ] Execute: `aud blueprint --structure | grep -A 10 "Framework Detection"`
- [ ] Store full framework detection output
- [ ] **Audit:** Verify blueprint ran successfully. If audit reveals failures, amend and re-audit.

### Task 2.2: Extract Backend Framework

**Jobs:**
- [ ] From blueprint output, identify backend (Flask, Express, FastAPI, Django)
- [ ] Document request handling patterns:
  - Flask: request.form, request.args, request.json, request.headers
  - Express: req.body, req.query, req.params, req.headers
  - FastAPI: request.form, request.json, request.path_params
- [ ] **Audit:** Verify backend framework identified. If audit reveals failures, amend and re-audit.

### Task 2.3: Extract Frontend Framework (If Applicable)

**Jobs:**
- [ ] From blueprint output, identify frontend (React, Vue, Angular)
- [ ] Document data flow patterns:
  - React: props, useState(), fetch() response, localStorage
  - Vue: props, data(), computed, vuex store
- [ ] **Audit:** Verify frontend framework identified. If audit reveals failures, amend and re-audit.

### Task 2.4: Extract Database Layer

**Jobs:**
- [ ] From blueprint output, identify database (Sequelize, SQLAlchemy, Prisma, raw SQL)
- [ ] Document sink patterns:
  - Sequelize: Model.findOne, Model.create, db.query
  - SQLAlchemy: db.session.execute, query.filter
  - Raw: db.execute, db.query
- [ ] **Audit:** Verify database layer identified. If audit reveals failures, amend and re-audit.

### Task 2.5: Phase 2 Audit

**Jobs:**
- [ ] Verify framework detection complete
- [ ] Confirm backend source patterns documented
- [ ] Confirm database sink patterns documented
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Framework context loaded with source/sink patterns

---

## PHASE 3: Run Taint Analysis

**Description:** Execute taint analysis with source and sink patterns. Get actual dataflow paths from database. Count unsanitized flows.

**Problem Solved:** Provides factual dataflow paths from database instead of guessing. Shows exact source → sink chains with line numbers and file paths. Enables evidence-based sanitization recommendations.

### Task 3.1: Construct Taint Analysis Command

**Jobs:**
- [ ] Based on Phase 1 scope and Phase 2 framework, construct command:
  - For user input → database: `aud taint-analyze --source "request.*" --sink ".*query.*"`
  - For user input → HTML: `aud taint-analyze --source "request.*" --sink ".*innerHTML.*"`
  - For sensitive data → all uses: `aud taint-analyze --source "password" --sink "*"`
- [ ] **Audit:** Verify command constructed correctly. If audit reveals failures, amend and re-audit.

### Task 3.2: Execute Taint Analysis

**Jobs:**
- [ ] Execute: Constructed taint analysis command
- [ ] Store complete output
- [ ] **Audit:** Verify taint analysis ran successfully. If audit reveals failures, amend and re-audit.

### Task 3.3: Parse Dataflow Paths

**Jobs:**
- [ ] Extract all source → sink paths from output
- [ ] Count total paths found
- [ ] For each path, extract:
  - Source location (file:line)
  - Sink location (file:line)
  - Intermediate functions (if shown)
- [ ] **Audit:** Verify paths parsed. If audit reveals failures, amend and re-audit.

### Task 3.4: Categorize Paths

**Jobs:**
- [ ] Group paths by risk level:
  - HIGH: No validation, no sanitization
  - MEDIUM: Validation present, sanitization missing
  - LOW: Both validation and sanitization present
- [ ] Count paths in each category
- [ ] **Audit:** Verify paths categorized. If audit reveals failures, amend and re-audit.

### Task 3.5: Phase 3 Audit

**Jobs:**
- [ ] Verify taint analysis executed
- [ ] Confirm all paths extracted
- [ ] Confirm paths categorized by risk
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Dataflow paths retrieved from database

---

## PHASE 4: Query Call Graph

**Description:** For each taint path, query call graph to build complete source → intermediate → sink chain. Identify validation/sanitization points.

**Problem Solved:** Provides complete picture of dataflow including all intermediate functions. Identifies where validation/sanitization COULD be added. Shows function call depth and coupling.

### Task 4.1: Query Source Function Callers

**Jobs:**
- [ ] For each source function in paths, execute: `aud query --symbol <source> --show-callers`
- [ ] Identify who calls the source function
- [ ] Document caller chain
- [ ] **Audit:** Verify source callers queried. If audit reveals failures, amend and re-audit.

### Task 4.2: Query Sink Function Callees

**Jobs:**
- [ ] For each sink function in paths, execute: `aud query --symbol <sink> --show-callees`
- [ ] Identify what the sink function calls
- [ ] Document callee chain
- [ ] **Audit:** Verify sink callees queried. If audit reveals failures, amend and re-audit.

### Task 4.3: Build Complete Call Chain

**Jobs:**
- [ ] For each path, construct: caller → source → intermediate → sink → callee
- [ ] Note function depth (how many intermediate functions)
- [ ] Note coupling (high depth = more places to add validation)
- [ ] **Audit:** Verify call chains built. If audit reveals failures, amend and re-audit.

### Task 4.4: Phase 4 Audit

**Jobs:**
- [ ] Verify all source functions queried for callers
- [ ] Verify all sink functions queried for callees
- [ ] Confirm complete call chains documented
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Call graph complete for all paths

---

## PHASE 5: Identify Sanitization Gaps

**Description:** Query database for validation/sanitization functions. Check if they appear in dataflow paths. Identify gaps.

**Problem Solved:** Finds dataflow paths lacking validation/sanitization. Uses detected validation library (zod/joi/marshmallow) to identify coverage. Ensures recommendations match existing patterns.

### Task 5.1: Query Validation Patterns

**Jobs:**
- [ ] Based on Phase 2 framework, query validation library:
  - If zod: `aud query --symbol ".*Schema.*" --show-callers`
  - If joi: `aud query --symbol ".*Joi.*" --show-callers`
  - If marshmallow: `aud query --symbol ".*Schema.*" --show-callers`
  - If pydantic: `aud query --symbol ".*BaseModel.*" --show-callers`
- [ ] Store validation function locations
- [ ] **Audit:** Verify validation patterns queried. If audit reveals failures, amend and re-audit.

### Task 5.2: Query Sanitization Patterns

**Jobs:**
- [ ] Execute: `aud query --symbol ".*sanitize.*" --show-callers`
- [ ] Execute: `aud query --symbol ".*escape.*" --show-callers`
- [ ] Execute: `aud query --symbol ".*validate.*" --show-callers`
- [ ] Store sanitization function locations
- [ ] **Audit:** Verify sanitization patterns queried. If audit reveals failures, amend and re-audit.

### Task 5.3: Check Paths for Validation

**Jobs:**
- [ ] For each HIGH-risk path (no validation), check:
  - Does path pass through any validation function? (from Task 5.1)
  - If yes, mark as MEDIUM (validation present, sanitization missing)
  - If no, keep as HIGH (no validation)
- [ ] Update path categorization
- [ ] **Audit:** Verify paths checked for validation. If audit reveals failures, amend and re-audit.

### Task 5.4: Check Paths for Sanitization

**Jobs:**
- [ ] For each MEDIUM-risk path (validation but no sanitization), check:
  - Does path pass through any sanitization function? (from Task 5.2)
  - If yes, mark as LOW (both validation and sanitization)
  - If no, keep as MEDIUM
- [ ] Update path categorization
- [ ] **Audit:** Verify paths checked for sanitization. If audit reveals failures, amend and re-audit.

### Task 5.5: Document Sanitization Gaps

**Jobs:**
- [ ] List all HIGH-risk paths (no validation, no sanitization)
- [ ] List all MEDIUM-risk paths (validation present, sanitization missing)
- [ ] Count gaps: X paths have NO validation, Y paths have validation but NO escaping
- [ ] **Audit:** Verify gaps documented. If audit reveals failures, amend and re-audit.

### Task 5.6: Phase 5 Audit

**Jobs:**
- [ ] Verify validation patterns queried
- [ ] Verify sanitization patterns queried
- [ ] Confirm all paths checked for validation/sanitization
- [ ] Confirm gaps documented with counts
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Sanitization gaps identified

---

## PHASE 6: Generate Dataflow Analysis

**Description:** Compile all gathered facts into evidence-based dataflow report. Match detected framework patterns. Present findings with database query citations.

**Problem Solved:** Provides complete dataflow picture using only database facts. Ensures recommendations match detected frameworks (zod if zod detected). Shows exact paths, gaps, and framework-appropriate fixes.

### Task 6.1: Compile Trace Scope Section

**Jobs:**
- [ ] Report: Source pattern (e.g., request.body)
- [ ] Report: Sink pattern (e.g., database query)
- [ ] Report: Trace goal (e.g., SQL injection check)
- [ ] **Audit:** Verify scope section complete. If audit reveals failures, amend and re-audit.

### Task 6.2: Compile Framework Context Section

**Jobs:**
- [ ] Report: Backend framework (Flask, Express, etc.)
- [ ] Report: Frontend framework (React, Vue, etc.) if applicable
- [ ] Report: Database layer (Sequelize, SQLAlchemy, etc.)
- [ ] Report: Validation library (zod 3.22.0, marshmallow, etc.)
- [ ] **Audit:** Verify context section complete. If audit reveals failures, amend and re-audit.

### Task 6.3: Compile Taint Analysis Results Section

**Jobs:**
- [ ] Report: Total dataflow paths found (count)
- [ ] Report: Breakdown by risk level:
  - HIGH: X paths (no validation, no sanitization)
  - MEDIUM: Y paths (validation present, no sanitization)
  - LOW: Z paths (validation and sanitization present)
- [ ] **Audit:** Verify taint results section complete. If audit reveals failures, amend and re-audit.

### Task 6.4: Compile Path Details Section

**Jobs:**
- [ ] For each HIGH/MEDIUM path, report:
  - Source: file:line (what data enters)
  - Flow: Intermediate functions (data transformations)
  - Sink: file:line (where data exits)
  - Sanitization: NONE or Validation present
  - Risk: HIGH or MEDIUM
- [ ] **Audit:** Verify path details complete. If audit reveals failures, amend and re-audit.

### Task 6.5: Compile Sanitization Gaps Section

**Jobs:**
- [ ] Report: X paths have NO validation
- [ ] Report: Y paths have validation but NO HTML escaping/parameterization
- [ ] Report: Z paths have complete sanitization
- [ ] **Audit:** Verify gaps section complete. If audit reveals failures, amend and re-audit.

### Task 6.6: Generate Recommendations (Match Framework)

**Jobs:**
- [ ] For validation gaps: Recommend DETECTED validation library
  - If zod detected → Show zod schema example
  - If joi detected → Show joi validation example
  - If marshmallow detected → Show marshmallow schema example
- [ ] For sanitization gaps: Recommend framework-appropriate sanitization
  - If SQL injection → Use detected ORM parameterization
  - If XSS → Use DOMPurify or framework escaping
- [ ] **Audit:** Verify recommendations match framework. If audit reveals failures, amend and re-audit.

### Task 6.7: Compile Evidence Citations

**Jobs:**
- [ ] List all database queries run with results
- [ ] Example: "Taint analysis: 7 paths request.body → innerHTML"
- [ ] Example: "Framework detection: zod 3.22.0 (15 files)"
- [ ] Example: "Query: 5 routes without .*schema.* call"
- [ ] **Audit:** Verify evidence complete. If audit reveals failures, amend and re-audit.

### Task 6.8: Present Dataflow Analysis

**Jobs:**
- [ ] Output complete dataflow analysis with all sections
- [ ] End with: "Approve? (y/n)"
- [ ] STOP and WAIT for user confirmation
- [ ] **Audit:** Verify analysis presented correctly. If audit reveals failures, amend and re-audit.

### Task 6.9: Phase 6 Audit

**Jobs:**
- [ ] Verify all report sections compiled
- [ ] Confirm recommendations match detected frameworks
- [ ] Confirm evidence citations complete
- [ ] Confirm analysis ends with approval prompt
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Dataflow analysis complete with framework-matched recommendations

---

## KEY PRINCIPLES

1. **Zero Hallucination:** Read `--help` FIRST, never guess command syntax
2. **Database-First:** Use `aud taint-analyze`, `aud query` - NO file reading
3. **Run Taint Analysis First:** Get actual dataflow, don't guess paths
4. **Query Call Graph:** Build complete source → sink picture
5. **Check Sanitization:** Identify validation/escaping gaps
6. **Match Detected Frameworks:** Use zod if zod detected
7. **Audit Loops:** Every task ends with audit, every phase ends with phase audit
8. **Problem Decomposition:** Each phase solves specific sub-problem with justification

---

## COMMON MISTAKES TO AVOID

**DON'T:**
- ❌ Guess dataflow paths → RUN: `aud taint-analyze`
- ❌ Assume validation exists → QUERY: `aud query --symbol ".*validate.*"`
- ❌ Invent sanitization approach → USE: detected validation library
- ❌ Skip call graph analysis → QUERY: `aud query --show-callers`
- ❌ Read files to trace data → USE: taint analysis engine
- ❌ Recommend joi when project uses zod → MATCH: detected framework

**DO:**
- ✅ Read `--help` documentation before every command
- ✅ Run `aud taint-analyze` for actual paths (Phase 3)
- ✅ Query call graph for complete picture (Phase 4)
- ✅ Check for validation/sanitization in paths (Phase 5)
- ✅ Use detected framework patterns (Phase 2)
- ✅ Cite taint analysis evidence (Phase 6)
- ✅ End every task with audit, every phase with phase audit

---

## EXAMPLE WORKFLOWS

### Example 1: User Input → Database (SQL Injection Check)

```
User: "Trace user input to database queries"

Agent: Starting Phase 1: Define Trace Scope...
Agent: Task 1.2: User specified source: "user input", sink: "database queries"
Agent: Task 1.4: Scope documented:
  - Source: request.* (all request data)
  - Sink: .*query.* (database queries)
  - Goal: SQL injection check
Agent: Phase 1 Audit: ✓ Trace scope defined

Agent: Starting Phase 2: Load Framework Context...
Agent: Task 2.1: Running aud blueprint --structure...
Agent: Task 2.2: Backend: Express.js
Agent: Task 2.4: Database: Sequelize ORM
Agent: Phase 2 Audit: ✓ Framework context loaded

Agent: Starting Phase 3: Run Taint Analysis...
Agent: Task 3.1: Constructing command: aud taint-analyze --source "request.*" --sink ".*query.*"
Agent: Task 3.2: Executing taint analysis...
Agent: Task 3.3: Found 12 dataflow paths from request to database
Agent: Task 3.4: Categorized:
  - HIGH: 3 paths (no validation, string interpolation)
  - MEDIUM: 0 paths
  - LOW: 9 paths (Sequelize parameterization)
Agent: Phase 3 Audit: ✓ 12 paths analyzed

Agent: Starting Phase 4: Query Call Graph...
Agent: Task 4.1-4.3: Building complete call chains for 3 HIGH-risk paths...
Agent: Phase 4 Audit: ✓ Call graph complete

Agent: Starting Phase 5: Identify Sanitization Gaps...
Agent: Task 5.1: No validation library detected for SQL (using raw queries)
Agent: Task 5.3-5.5: 3 paths use string interpolation (no parameterization)
Agent: Phase 5 Audit: ✓ Sanitization gaps identified

Agent: Starting Phase 6: Generate Dataflow Analysis...

Dataflow Analysis: User Input → Database

Trace Scope:
- Source: request.* (all request data)
- Sink: .*query.* (database queries)
- Goal: SQL injection vulnerability check

Detected Context:
- Backend: Express.js
- Database: Sequelize ORM

Taint Analysis Results:
- 12 dataflow paths from request to database
- HIGH risk: 3 paths (string interpolation)
- LOW risk: 9 paths (Sequelize parameterization)

Path Details:

Path 1 (HIGH RISK):
- Source: routes/products.js:67 (req.body.name)
- Flow: db.query(`SELECT * WHERE name='${name}'`)
- Sink: Database (string interpolation)
- Sanitization: NONE
- Risk: HIGH (SQL injection)

Path 2 (HIGH RISK):
- Source: routes/search.js:12 (req.query.q)
- Flow: db.query(`SELECT * WHERE title LIKE '%${q}%'`)
- Sink: Database (string interpolation)
- Sanitization: NONE
- Risk: HIGH (SQL injection)

Path 3 (HIGH RISK):
- Source: routes/users.js:89 (req.params.id)
- Flow: db.execute(`DELETE WHERE id=${id}`)
- Sink: Database (string interpolation)
- Sanitization: NONE
- Risk: HIGH (SQL injection)

Sanitization Gaps:
- 3 paths have NO parameterization (string interpolation)
- 9 paths use Sequelize parameterization (SAFE)

Recommendation (Matching Detected Sequelize ORM):
Convert 3 unsafe queries to Sequelize parameterized queries:

```javascript
// routes/products.js:67 - BEFORE (UNSAFE)
db.query(`SELECT * FROM products WHERE name='${req.body.name}'`)

// AFTER (SAFE) - Sequelize parameterization
Product.findAll({ where: { name: req.body.name } })

// routes/search.js:12 - BEFORE (UNSAFE)
db.query(`SELECT * FROM posts WHERE title LIKE '%${req.query.q}%'`)

// AFTER (SAFE) - Sequelize Op.like
const { Op } = require('sequelize');
Post.findAll({ where: { title: { [Op.like]: `%${req.query.q}%` } } })

// routes/users.js:89 - BEFORE (UNSAFE)
db.execute(`DELETE FROM users WHERE id=${req.params.id}`)

// AFTER (SAFE) - Sequelize destroy
User.destroy({ where: { id: req.params.id } })
```

Evidence:
- Taint analysis: 3 paths use string interpolation
- ORM detected: Sequelize (use parameterized queries)
- 9 existing routes already use Sequelize parameterization

Approve? (y/n)
```

### Example 2: User Input → HTML Output (XSS Check)

```
User: "Trace user input to HTML rendering"

Agent: Starting Phase 1: Define Trace Scope...
Agent: Scope: request.* → .*innerHTML.*
Agent: Phase 1 Audit: ✓ Trace scope defined

Agent: Starting Phase 2: Load Framework Context...
Agent: Backend: Express.js, Frontend: React 18.2.0, Validation: zod 3.22.0
Agent: Phase 2 Audit: ✓ Framework context loaded

Agent: Starting Phase 3: Run Taint Analysis...
Agent: Execute: aud taint-analyze --source "request.*" --sink ".*innerHTML.*"
Agent: Found 7 dataflow paths from request to innerHTML
Agent: Phase 3 Audit: ✓ 7 paths analyzed

Agent: Starting Phase 5: Identify Sanitization Gaps...
Agent: 5 paths have NO validation
Agent: 7 paths have NO HTML escaping (all use innerHTML)
Agent: Phase 5 Audit: ✓ Gaps identified

Agent: Starting Phase 6: Generate Dataflow Analysis...

Dataflow Analysis: User Input → HTML Output

Taint Analysis Results:
- 7 dataflow paths from request.body to innerHTML

Path 1 (MEDIUM RISK):
- Source: routes/profile.js:45 (req.body.bio)
- Flow: UserSchema.parse (zod validation ✓)
- Flow: User.update (stores to database)
- Sink: components/UserProfile.tsx:45 (innerHTML = bio)
- Sanitization: Validation present, but NO HTML escaping
- Risk: MEDIUM (XSS via validated but unescaped HTML)

Path 2 (HIGH RISK):
- Source: routes/comments.js:67 (req.body.comment)
- Flow: NO VALIDATION
- Sink: components/Comment.tsx:89 (innerHTML = comment)
- Sanitization: NONE
- Risk: HIGH (XSS)

... (5 more paths)

Sanitization Gaps:
- 5 paths have NO validation
- 7 paths have NO HTML escaping (all use innerHTML)

Recommendation (Matching Detected Framework):
1. Add zod validation to 5 missing paths (matches existing zod 3.22.0 usage)
2. Install DOMPurify: npm install dompurify
3. Replace innerHTML with DOMPurify.sanitize (7 locations)

Example fix:
```typescript
import DOMPurify from 'dompurify';
import { z } from 'zod';

// Add zod validation (matching detected zod 3.22.0)
const CommentSchema = z.object({
  text: z.string().min(1).max(500)
});

app.post('/comments', (req, res) => {
  const validated = CommentSchema.parse(req.body); // Add validation
  // ... rest
});

// Replace innerHTML with DOMPurify (React-compatible)
// BEFORE (UNSAFE)
element.innerHTML = userBio;

// AFTER (SAFE)
element.innerHTML = DOMPurify.sanitize(userBio);
```

Evidence:
- Taint analysis: 7 paths request.body → innerHTML (no escaping)
- Framework: zod 3.22.0 (use for validation), React 18.2.0
- 5 paths missing validation, 7 paths missing HTML escaping

Approve? (y/n)
```

### Example 3: JWT Token Flow Tracking

```
User: "Track JWT token through the system"

Agent: Starting Phase 1: Define Trace Scope...
Agent: Scope: jwt.sign → * (all uses)
Agent: Phase 1 Audit: ✓ Trace scope defined

Agent: Starting Phase 2: Load Framework Context...
Agent: Backend: Express.js, Library: jsonwebtoken
Agent: Phase 2 Audit: ✓ Framework context loaded

Agent: Starting Phase 3: Run Taint Analysis...
Agent: Execute: aud query --symbol "jwt.sign" --show-callers
Agent: Found 2 locations signing JWTs
Agent: Execute: aud query --symbol "jwt.verify" --show-callers
Agent: Found 5 locations verifying JWTs
Agent: Execute: aud taint-analyze --source "jwt.sign" --sink "*"
Agent: Tracing JWT token flow...
Agent: Phase 3 Audit: ✓ Token flow analyzed

Agent: Starting Phase 4: Query Call Graph...
Agent: Building complete token lifecycle...
Agent: Phase 4 Audit: ✓ Call graph complete

Agent: Starting Phase 6: Generate Dataflow Analysis...

Dataflow Analysis: JWT Token Lifecycle

Token Flow:
1. Created: auth/login.js:45 (jwt.sign with user.id)
2. Stored: res.cookie('token', jwt, { httpOnly: true })
3. Verified: middleware/auth.js:12 (jwt.verify on every request)
4. Used: req.user passed to 23 protected routes
5. Exposed: 3 routes return req.user in response (potential leak)

Security Findings:
- ✓ httpOnly cookie (prevents XSS theft)
- ✓ JWT verification on protected routes
- ⚠ 3 routes expose full user object (including sensitive fields)

Routes Exposing User Object:
- routes/profile.js:34 (returns req.user with password hash)
- routes/settings.js:67 (returns req.user with email verification token)
- routes/api.js:89 (returns req.user with internal role flags)

Recommendation:
Create userSerializer to filter sensitive fields:

```javascript
// middleware/serializer.js (NEW)
function serializeUser(user) {
  const { password, emailVerificationToken, internalRoleFlags, ...safeUser } = user;
  return safeUser;
}

// routes/profile.js:34 - BEFORE (UNSAFE)
res.json({ user: req.user });

// AFTER (SAFE)
res.json({ user: serializeUser(req.user) });
```

Evidence:
- Query: jwt.sign called 2 times, jwt.verify called 5 times
- Taint analysis: JWT token flows to 23 routes, exposed in 3
- 3 routes return full user object with sensitive fields

Approve? (y/n)
```

---

**Version:** 2.0 (Eric's Framework Adoption)
**Last Updated:** 2025-11-02
**Protocol:** Phase → Task → Job hierarchy with problem decomposition
