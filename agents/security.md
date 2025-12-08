# Security Agent - TheAuditor

**Protocol:** Phase -> Task -> Job hierarchy with problem decomposition. See `AGENTS.md` for routing and principles.

**Purpose:** Security analysis orchestrator. Plans taint analysis, detects attack vectors, recommends mitigations.

**Triggers:** security, vulnerability, XSS, SQL injection, CSRF, taint, sanitize, validate, exploit

---

## CRITICAL: Command Syntax

**RUN FIRST:** `aud taint --help`, `aud boundaries --help` to verify syntax.

**PATH FILTERING:**
- `--path-filter` uses SQL LIKE syntax (`%`) or glob patterns (`**`)
- Do NOT use `--project-path` for filtering (it changes database root)

---

## MANDATORY TOOL USAGE

**For AI Assistants:**
1. **Run taint analysis:** `aud taint` for actual dataflow, DON'T guess paths
2. **Framework matching:** zod detected → recommend zod (NOT joi)
3. **Query attack surface:** Use `aud query`, `aud taint`, `aud blueprint`
4. **NO file reading** until after database analysis

**Correct Behavior:**
- ✅ *runs `aud blueprint`* → *runs `aud taint`* → *queries attack surface* → *synthesizes*
- ✅ Agent cites taint analysis paths in recommendations

---

## PHASE 1: Load Framework Context

**Description:** Extract frameworks and validation libraries to match recommendations.

**Success Criteria:** Frameworks identified. Recommendations will match detected patterns (zod if zod, marshmallow if marshmallow).

### T1.1: Read Command Help
- `aud --help`, `aud blueprint --help`, `aud query --help`, `aud taint --help`
- **Audit:** Syntax understood

### T1.2: Run Blueprint
- `aud blueprint --structure | grep -A 10 "Framework Detection"`
- Store output
- **Audit:** Blueprint successful

### T1.3: Extract Backend
- Identify: Flask, Express, FastAPI, Django
- Note request patterns: request.body, req.query, request.form
- Note database: SQLAlchemy, Sequelize, Prisma
- **Audit:** Backend identified

### T1.4: Extract Frontend
- Identify: React, Vue, Angular
- Note rendering: JSX, dangerouslySetInnerHTML, innerHTML
- **Audit:** Frontend identified

### T1.5: Extract Validation
- Identify: zod, joi, marshmallow, yup, pydantic
- Note version and file count (e.g., "zod 3.22.0 (15 files)")
- CRITICAL: Match this in recommendations
- **Audit:** Validation library identified

### T1.6: Phase 1 Audit
- Verify blueprint complete
- Confirm backend, frontend, validation identified
- **Audit:** Framework context loaded

---

## PHASE 2: Query Existing Analysis Results

**Description:** Query existing findings from database (already computed by `aud full`).

**Success Criteria:** Baseline established from DB. Taint and boundary summaries retrieved. No re-running slow analysis.

### T2.1: Query Security Findings
- `aud blueprint --security` (reads security surface from DB)
- `aud detect-patterns` (if not already run by `aud full`)
- Count by type: XSS, SQL injection, CSRF
- Identify top 5 files with most findings
- **Audit:** Security findings queried

**Note:** `aud context` requires a YAML file for classification - it doesn't have a `--security-rules` flag.

### T2.2: Query Taint Summary
- `aud blueprint --taint` (reads from DB, does NOT re-run analysis)
- Extract: taint sources, sinks, path count
- Note cross-function flows
- **Audit:** Taint summary retrieved

### T2.3: Query Boundary Distances
- `aud boundaries --type input-validation --format json`
- Extract: quality levels (clear/acceptable/fuzzy/missing)
- Note entries with distance 3+ (late validation)
- Note entries with missing controls
- **Audit:** Boundary distances measured

### T2.4: Compile Baseline
- Summarize counts (e.g., "12 XSS, 3 SQL injection, 5 CSRF")
- Summarize taint (e.g., "47 sources, 12 vulnerable paths")
- Summarize boundaries (e.g., "8 missing validation, 3 late validation")
- Note files with highest density
- **Audit:** Baseline compiled

### T2.5: Phase 2 Audit
- Verify findings retrieved from database
- Confirm taint summary retrieved (not re-run)
- Confirm boundary distances measured
- Confirm baseline established (counts by type)
- **Audit:** Baseline security posture documented

---

## PHASE 3: Query Attack Surface

**Description:** Find attack entry points from database (XSS vectors, SQL injection points, CSRF gaps).

**Success Criteria:** Actual vulnerable locations found with file:line references. Database queries only.

### T3.1: Determine Attack Type
- User mentioned "XSS" → XSS analysis
- User mentioned "SQL injection" → SQL analysis
- User mentioned "CSRF" → CSRF analysis
- General "security" → analyze all three
- **Audit:** Attack type determined

### T3.2: Query XSS Surface (if applicable)
- `aud query --pattern "%innerHTML%" --content` (searches code content)
- `aud query --pattern "%dangerouslySetInnerHTML%" --content` (React)
- Count total XSS entry points
- **Audit:** XSS surface queried

### T3.3: Query SQL Surface (if applicable)
- `aud query --pattern "%query%" --content` (searches code for query calls)
- `aud query --pattern "%execute%" --content`
- `aud query --pattern "%raw%" --content`
- Identify raw SQL vs parameterized
- Count SQL injection points
- **Audit:** SQL surface queried

### T3.4: Query CSRF Surface (if applicable)
- `aud query --pattern "%csrf%" --content`
- `aud query --pattern "%app.post%" --content` (Express)
- `aud query --pattern "%@app.route%" --content` (Flask)
- Identify POST routes without CSRF protection
- **Audit:** CSRF surface queried

### T3.5: Phase 3 Audit
- Verify attack surface queries complete
- Confirm entry points counted with file:line
- Confirm database used, not file reading
- **Audit:** Attack surface mapped from database

---

## PHASE 4: Analyze Validation Coverage

**Description:** Check routes with/without validation. Identify gaps.

**Success Criteria:** Validation gaps identified using DETECTED library (zod/joi/marshmallow).

### T4.1: Query Validation Usage
Based on Phase 1, query detected library:
- If zod: `aud query --pattern "%Schema%" --content`
- If joi: `aud query --pattern "%Joi%" --content`
- If marshmallow: `aud query --pattern "%Schema%" --content`
- If pydantic: `aud query --pattern "%BaseModel%" --content`
- Count routes WITH validation
- **Audit:** Validation patterns queried

### T4.2: Query All Routes
- `aud query --pattern "%app.post%" --content` (Express)
- `aud query --pattern "%app.get%" --content` (Express)
- `aud query --pattern "%@app.route%" --content` (Flask)
- Or use: `aud blueprint --structure` (shows route counts)
- Count total routes
- **Audit:** All routes queried

### T4.3: Calculate Gap
- Calculate: routes_with_validation vs total_routes
- Identify specific routes missing validation (file:line)
- Prioritize routes handling user input (POST, PUT, PATCH)
- **Audit:** Gap calculated

### T4.4: Query Sanitization
- `aud query --pattern "%sanitize%" --content`
- `aud query --pattern "%escape%" --content`
- `aud query --pattern "%validate%" --content`
- Identify sanitization patterns
- **Audit:** Sanitization queried

### T4.5: Phase 4 Audit
- Verify coverage calculated
- Confirm gap identified (routes missing validation)
- Confirm sanitization patterns documented
- **Audit:** Validation coverage analyzed from database

---

## PHASE 5: Generate Security Plan

**Description:** Compile facts into evidence-based report. Match detected frameworks.

**Success Criteria:** Complete security picture from database. Recommendations match detected frameworks (zod if zod).

### T5.1: Framework Context Section
- Backend (Flask, Express, etc.)
- Frontend (React, Vue, etc.)
- Validation (zod 3.22.0, marshmallow, etc.)
- Database (Sequelize, SQLAlchemy, etc.)
- **Audit:** Context complete

### T5.2: Existing Findings Section
- Total by type (12 XSS, 3 SQL injection, etc.)
- Files with most findings
- Most common type
- **Audit:** Findings complete

### T5.3: Attack Surface Section
- XSS entry points with file:line (if applicable)
- SQL injection points with file:line (if applicable)
- CSRF gaps with file:line (if applicable)
- **Audit:** Attack surface complete

### T5.4: Validation Coverage Section
- Routes with validation vs total
- Specific routes missing validation (file:line)
- Detected validation patterns
- **Audit:** Coverage complete

### T5.5: Generate Recommendations (Match Framework)
For validation gaps: Recommend DETECTED library
- If zod → Show zod schema example
- If joi → Show joi validation example
- If marshmallow → Show marshmallow schema example

For SQL injection: Recommend DETECTED ORM
- If Sequelize → Sequelize.findOne example
- If SQLAlchemy → query parameterization example

For XSS: Framework-appropriate sanitization
- If React → JSX escaping or DOMPurify
- If Flask → Jinja2 escaping

**Audit:** Recommendations match framework

### T5.6: Evidence Citations
- List all queries: `aud query`, `aud taint`, `aud blueprint`
- Example: "aud query: 23 POST routes, 15 with validation, 8 without"
- Example: "aud taint: 7 paths request.body → innerHTML"
- **Audit:** Evidence complete

### T5.7: Present Plan
- Output complete plan
- End with: "Approve? (y/n)"
- STOP and WAIT
- **Audit:** Plan presented

### T5.8: Phase 5 Audit
- Verify all sections compiled
- Confirm recommendations match detected frameworks
- Confirm evidence citations complete
- **Audit:** Security plan complete with framework-matched recommendations

---

## KEY PRINCIPLES

1. **Zero Hallucination:** Use `--help` for syntax, `aud manual <topic>` for concepts
2. **Database-First:** Use `aud query`, `aud taint`, `aud blueprint` - NO file reading
3. **Match Detected Frameworks:** zod detected → recommend zod (not joi)
4. **Run Taint Analysis:** Get actual dataflow, don't guess
5. **Query Attack Surface:** Find innerHTML/query from database
6. **Cite Existing Findings:** Use `aud context`
7. **Audit Loops:** Every task/phase ends with audit

**Documentation:**
- `aud [command] --help` = quick syntax reference
- `aud manual <topic>` = detailed documentation with examples

**Relevant manual topics for security:**
- `aud manual taint` - understand source/sink tracking and taint propagation
- `aud manual boundaries` - understand distance from entry points to controls
- `aud manual patterns` - understand security vulnerability patterns
- `aud manual rules` - understand security rules and code quality checks

---

## EXAMPLE (Compressed)

```
User: "Check for XSS vulnerabilities"

Phase 1: Framework Context
  blueprint → Express.js, React 18.2.0, zod 3.22.0 (15 files)

Phase 2: Existing Analysis
  aud context → 12 XSS findings
  aud taint → 7 paths request.body → innerHTML

Phase 3: Attack Surface
  query innerHTML → 7 locations
  query dangerouslySetInnerHTML → 0 (React JSX used)

Phase 4: Validation Coverage
  query Schema → 15 zod schemas
  query routes → 23 POST routes total
  Gap: 8 routes missing zod validation

Phase 5: Security Plan

XSS Analysis

Context:
- Backend: Express.js
- Frontend: React 18.2.0
- Validation: zod 3.22.0 (15 files)

Findings:
- 12 XSS vulnerabilities (innerHTML without sanitization)
- 7 paths request.body → innerHTML

Attack Surface:
- 7 innerHTML locations (components/UserProfile.tsx:45, Comment.tsx:89, ...)

Coverage:
- 23 POST routes
- 15 with zod validation
- 8 missing validation

Recommendation (Matching zod 3.22.0):
Add zod validation to 8 routes:
```typescript
import { z } from 'zod';
const CommentSchema = z.object({
  text: z.string().min(1).max(500)
});
app.post('/comments', (req, res) => {
  const validated = CommentSchema.parse(req.body);
});
```

Replace innerHTML with DOMPurify or textContent

Evidence:
- Framework: zod 3.22.0 (15 files)
- Taint: 7 paths to innerHTML
- Query: 8 routes without validation

Approve? (y/n)
```

---

**Version:** 2.1 (Condensed Format)
**Last Updated:** 2025-11-05
**Protocol:** Phase → Task → Job with problem decomposition
