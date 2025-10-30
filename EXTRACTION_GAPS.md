# TheAuditor Extraction Gaps - Real-World Coverage Analysis

**Date**: 2025-10-31
**Status**: CRITICAL - Missing extraction for frameworks used in production projects
**Impact**: Downstream consumers (aud blueprint, aud planning, aud taint-analyze, aud context) are BLIND to these patterns

---

## Executive Summary

Analyzed 3 real production projects (plant, PlantFlow, project_anarchy) to identify gaps between what we extract and what real codebases actually use. Found **30+ critical frameworks/patterns** with ZERO or incomplete extraction.

**Impact**: When users run `aud full` on projects using these frameworks:
- ❌ `aud blueprint` cannot show security patterns for Sequelize models, Zustand stores, Angular services
- ❌ `aud planning` cannot plan migrations for Redis caching, BullMQ jobs, node-cron tasks
- ❌ `aud taint-analyze` misses taint flows through React Query, Dexie (IndexedDB), Joi validators
- ❌ `aud context` cannot apply business logic to Material-UI themes, i18n keys, Handlebars templates
- ❌ `aud detect-patterns` misses security issues in JWT handling, 2FA (speakeasy), file uploads (Multer)

**This isn't "nice to have" - it's EXISTENTIAL.** Half our users will see empty results if we don't extract the frameworks they actually use.

---

## Methodology

**Source Projects Analyzed**:
1. **plant** (C:/Users/santa/Desktop/plant) - Production PlantPro backend + frontend
2. **PlantFlow** (C:/Users/santa/Desktop/PlantFlow) - Production inventory management system
3. **project_anarchy** (C:/Users/santa/Desktop/fakeproj/project_anarchy) - Polyglot chaos project (intentional test bed)

**Extraction Test**: For each framework, checked:
- Can we extract symbols/models/components?
- Can we populate junction tables (relationships, controls, dependencies)?
- Can we track taint flows through framework-specific patterns?
- Can downstream consumers (blueprint, planning, taint) use the data?

---

## CRITICAL GAPS (Must Fix Immediately)

### 1. Sequelize ORM (Found in: plant, PlantFlow)

**Usage**: Both production projects use Sequelize, NOT Prisma (which we test)

**Missing Extraction**:
- ❌ Sequelize model definitions (`sequelize.define`, `Model.init`)
- ❌ Relationships: `hasMany`, `belongsTo`, `hasOne`, `belongsToMany`
- ❌ Hooks: `beforeCreate`, `afterUpdate`, `beforeDestroy`
- ❌ Validations: `validate`, `allowNull`, `unique` constraints
- ❌ Associations with `through` tables (many-to-many)
- ❌ Migrations via `sequelize-cli` and Umzug

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud blueprint

# CURRENT OUTPUT (WRONG):
"ORM Patterns: None detected"

# CORRECT OUTPUT (IF WE EXTRACT SEQUELIZE):
"ORM Patterns:
  - User model: hasMany(Order), belongsTo(Role)
  - 15 models with relationships
  - 8 models with cascade delete hooks"
```

**Fixture Needed**: `node-sequelize-orm/` (300+ lines)
- Models with all relationship types
- Hooks and validations
- Migrations with Umzug
- Transaction patterns
- spec.yaml testing orm_relationships, orm_fields

---

### 2. BullMQ / Job Queues (Found in: plant)

**Usage**: Background job processing (like Celery for Python, which we DO test)

**Missing Extraction**:
- ❌ Queue definitions (`new Queue('email')`)
- ❌ Worker definitions (`new Worker('email', async (job) => ...)`)
- ❌ Job producers (`queue.add('sendEmail', data)`)
- ❌ Job flow patterns (chaining, retries, delays)
- ❌ Redis connection configuration

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud taint-analyze

# CURRENT OUTPUT (WRONG):
Misses taint flow: req.body.email -> queue.add('sendEmail') -> worker -> nodemailer.sendMail()

# CORRECT OUTPUT (IF WE EXTRACT BULLMQ):
"Taint Flow:
  Source: req.body.email (user input)
  Propagation: queue.add('sendEmail', { to: email })
  Sink: nodemailer.sendMail() in email worker"
```

**Fixture Needed**: `node-bullmq-jobs/` (250+ lines)
- Queue and Worker definitions
- Job producers in API routes
- Taint flows: API -> queue -> worker -> external service
- spec.yaml testing job_queues, queue_workers tables

---

### 3. Zustand / State Management (Found in: plant)

**Usage**: React state management (alternative to Redux, Context API which we test)

**Missing Extraction**:
- ❌ Store definitions (`create((set, get) => ({ ... }))`)
- ❌ State mutations (`set({ user: newUser })`)
- ❌ Store slices and selectors
- ❌ Middleware patterns (persist, devtools)

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud blueprint

# CURRENT OUTPUT (WRONG):
"State Management: Context API (1 provider)"

# CORRECT OUTPUT (IF WE EXTRACT ZUSTAND):
"State Management:
  - Zustand stores: 5 (authStore, cartStore, uiStore, etc.)
  - Global state mutations: 23 actions
  - Persist middleware: enabled for authStore, cartStore"
```

**Fixture Needed**: `node-zustand-store/` (200+ lines)
- Multiple store definitions
- State mutations with taint flows (user input -> store -> components)
- Middleware patterns
- spec.yaml testing zustand_stores, store_actions tables

---

### 4. React Query (@tanstack/react-query) (Found in: plant)

**Usage**: Data fetching/caching (HUGE in React ecosystem, different from useEffect patterns we test)

**Missing Extraction**:
- ❌ Query definitions (`useQuery`, `useMutation`)
- ❌ Query keys (cache invalidation patterns)
- ❌ Mutation side effects
- ❌ Optimistic updates
- ❌ Query client configuration

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud taint-analyze

# CURRENT OUTPUT (WRONG):
Misses taint flow: userId (URL param) -> useQuery(['user', userId]) -> axios.get

# CORRECT OUTPUT (IF WE EXTRACT REACT QUERY):
"Taint Flow:
  Source: userId from useParams() (URL param)
  Propagation: useQuery(['user', userId], () => fetchUser(userId))
  Sink: axios.get(`/api/users/${userId}`)"
```

**Fixture Needed**: `node-react-query/` (300+ lines)
- useQuery with tainted query keys
- useMutation with side effects
- Query invalidation patterns
- spec.yaml testing react_queries, query_keys tables

---

### 5. Material-UI (MUI) (Found in: plant)

**Usage**: React component library with theming (different from raw React components we test)

**Missing Extraction**:
- ❌ Theme definitions (`createTheme()`)
- ❌ Styled components (`styled(Button)`)
- ❌ sx prop usage (theme-aware styling)
- ❌ Custom theme hooks (`useTheme()`)

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud context --file ui-standards.yaml

# USER'S CONTEXT FILE:
rules:
  - name: enforce_primary_color
    pattern: "MUI theme must use #007bff as primary color"

# CURRENT OUTPUT (WRONG):
"Cannot analyze: MUI theme extraction not implemented"

# CORRECT OUTPUT (IF WE EXTRACT MUI):
"Violation: Theme uses #0066cc (expected #007bff) in src/theme.ts:15"
```

**Fixture Needed**: `node-mui-theming/` (250+ lines)
- Theme creation with custom palette
- Styled components with theme access
- sx prop patterns
- spec.yaml testing mui_themes, theme_overrides tables

---

### 6. Dexie (IndexedDB) (Found in: plant)

**Usage**: Client-side database (security risk: user-controlled data)

**Missing Extraction**:
- ❌ Database schema definitions (`db.version(1).stores({ ... })`)
- ❌ Table operations (`db.users.add()`, `db.users.where()`)
- ❌ Taint flows: Dexie as taint source (like localStorage, but more complex)

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud detect-patterns --rule client-side-data-tampering

# CURRENT OUTPUT (WRONG):
"No client-side storage detected"

# CORRECT OUTPUT (IF WE EXTRACT DEXIE):
"MEDIUM: User data stored in IndexedDB (Dexie)
  - db.users table stores JWT tokens (src/db.ts:15)
  - Tokens used in Authorization header (src/api.ts:42)
  - Attacker with XSS can modify IndexedDB and inject malicious tokens"
```

**Fixture Needed**: `node-dexie-indexeddb/` (200+ lines)
- Database schema with multiple tables
- Taint flows: Dexie -> API calls
- Security patterns: token storage
- spec.yaml testing dexie_schemas, dexie_tables tables

---

### 7. Redis / Caching (Found in: PlantFlow)

**Usage**: Session storage, caching (security critical: session fixation, cache poisoning)

**Missing Extraction**:
- ❌ Redis client configuration
- ❌ get/set operations with TTL
- ❌ Session storage patterns
- ❌ Pub/sub patterns

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud taint-analyze

# CURRENT OUTPUT (WRONG):
Misses taint flow: sessionId (cookie) -> redis.get() -> session data -> API response

# CORRECT OUTPUT (IF WE EXTRACT REDIS):
"Taint Flow:
  Source: sessionId from cookie (user-controlled)
  Propagation: redis.get(`session:${sessionId}`)
  Sink: Sensitive session data exposed in API response
  Severity: MEDIUM (session fixation risk)"
```

**Fixture Needed**: `node-redis-caching/` (250+ lines)
- Session storage patterns
- Cache operations with taint flows
- Pub/sub patterns
- spec.yaml testing redis_operations, cache_keys tables

---

### 8. Joi / Zod Validation (Found in: PlantFlow, plant)

**Usage**: Request validation (security: sanitization layer before business logic)

**Missing Extraction**:
- ❌ Schema definitions (`Joi.object()`, `z.object()`)
- ❌ Validation in middleware/routes
- ❌ Custom validation rules
- ❌ Sanitization patterns

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud taint-analyze

# CURRENT OUTPUT (WRONG):
Reports: "req.body.email flows to database without sanitization"

# CORRECT OUTPUT (IF WE EXTRACT JOI/ZOD):
"req.body.email flows through Joi validator (src/middleware/validate.ts:25)
  - Sanitized: email format validation, max length 255
  - Then flows to database (SAFE)"
```

**Fixture Needed**: `node-joi-zod-validation/` (300+ lines)
- Joi and Zod schemas side-by-side
- Validation middleware
- Taint flows: input -> validator -> sanitized output
- spec.yaml testing validators, validation_rules tables

---

### 9. node-cron / Scheduled Tasks (Found in: PlantFlow)

**Usage**: Periodic tasks (like Celery beat, which we test for Python)

**Missing Extraction**:
- ❌ Cron job definitions (`cron.schedule('0 * * * *', ...)`)
- ❌ Task handlers
- ❌ Taint flows in scheduled contexts

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud blueprint

# CURRENT OUTPUT (WRONG):
"Background Tasks: None detected"

# CORRECT OUTPUT (IF WE EXTRACT NODE-CRON):
"Background Tasks:
  - 5 scheduled jobs (email reports, cache cleanup, data sync)
  - Daily report job accesses all user emails (privacy risk)
  - Cache cleanup job has database DELETE operations"
```

**Fixture Needed**: `node-cron-tasks/` (200+ lines)
- Multiple cron schedules
- Task handlers with database operations
- Taint flows in scheduled contexts
- spec.yaml testing cron_jobs, scheduled_tasks tables

---

### 10. Multer / File Uploads (Found in: plant, PlantFlow)

**Usage**: File upload middleware (security critical: path traversal, unrestricted upload)

**Missing Extraction**:
- ❌ Multer configuration (`multer({ dest: 'uploads/' })`)
- ❌ File upload routes with multer middleware
- ❌ File validation (mimetype, size limits)
- ❌ Storage strategies (disk, memory, S3)

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud detect-patterns --rule unrestricted-file-upload

# CURRENT OUTPUT (WRONG):
"No file upload patterns detected"

# CORRECT OUTPUT (IF WE EXTRACT MULTER):
"CRITICAL: Unrestricted file upload in POST /api/upload
  - No mimetype validation (src/routes/upload.ts:15)
  - No size limit (attacker can upload 1GB file)
  - Files stored in public directory (direct access)"
```

**Fixture Needed**: `node-multer-upload/` (250+ lines)
- Secure and insecure upload patterns
- File validation
- Taint flows: uploaded file -> filesystem/S3
- spec.yaml testing file_uploads, upload_controls tables

---

### 11. Handlebars / Template Engines (Found in: plant, PlantFlow)

**Usage**: Server-side templating (security: template injection, XSS)

**Missing Extraction**:
- ❌ Template registration (`handlebars.registerPartial()`)
- ❌ Template rendering (`template({ data })`)
- ❌ Taint flows: user data -> template -> HTML output
- ❌ Helper functions (custom filters)

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud detect-patterns --rule template-injection

# CURRENT OUTPUT (WRONG):
"No template engine detected"

# CORRECT OUTPUT (IF WE EXTRACT HANDLEBARS):
"HIGH: Template injection in email templates
  - User input flows to Handlebars template (src/services/email.ts:42)
  - Template: 'Hello {{username}}, your code is {{verificationCode}}'
  - Attacker can inject: '{{process.env.DB_PASSWORD}}' to leak secrets"
```

**Fixture Needed**: `node-handlebars-templates/` (200+ lines)
- Template definitions with user data
- Taint flows: input -> template -> output
- Helper functions
- spec.yaml testing templates, template_variables tables

---

### 12. Angular Framework (Found in: project_anarchy)

**Usage**: Enterprise frontend framework (HUGE market share, especially in enterprise)

**Missing Extraction**:
- ❌ Components (`@Component` decorator)
- ❌ Services (`@Injectable`)
- ❌ Dependency injection patterns
- ❌ RxJS observables (reactive patterns)
- ❌ Angular routing
- ❌ Angular forms (template-driven, reactive)

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud blueprint

# CURRENT OUTPUT (WRONG):
"Frontend: Unknown (detected package.json with @angular/* deps)"

# CORRECT OUTPUT (IF WE EXTRACT ANGULAR):
"Frontend: Angular 15
  - 42 components
  - 15 services (UserService, AuthService, etc.)
  - Dependency injection: 23 injection points
  - RxJS observables: 18 streams with taint flows"
```

**Fixture Needed**: `node-angular-app/` (600+ lines)
- Components with @Component decorator
- Services with @Injectable and DI
- RxJS observables with taint flows
- Angular forms with validation
- Routing patterns
- spec.yaml testing angular_components, angular_services, di_injections tables

---

### 13. react-router-dom v7 (Found in: plant)

**Usage**: React routing (different patterns than basic routing we might test)

**Missing Extraction**:
- ❌ Route definitions (`createBrowserRouter`, `RouterProvider`)
- ❌ Loader functions (data fetching)
- ❌ Action functions (form handling)
- ❌ Route params and search params
- ❌ Protected routes patterns

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud taint-analyze

# CURRENT OUTPUT (WRONG):
Misses taint flow: URL params -> loader -> API call

# CORRECT OUTPUT (IF WE EXTRACT REACT-ROUTER):
"Taint Flow:
  Source: userId from useParams() (URL parameter)
  Propagation: Route loader: ({ params }) => fetchUser(params.userId)
  Sink: axios.get(`/api/users/${userId}`)"
```

**Fixture Needed**: Add to `node-react-app/` fixture (100+ lines)
- React Router v7 patterns with loaders/actions
- Protected route patterns
- Taint flows from URL params
- Update spec.yaml with route patterns

---

### 14. i18next / Internationalization (Found in: plant)

**Usage**: Multi-language support (important for context/business logic rules)

**Missing Extraction**:
- ❌ Translation key definitions
- ❌ `useTranslation()` hook usage
- ❌ Language file references
- ❌ Dynamic key patterns

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud context --file i18n-standards.yaml

# USER'S CONTEXT FILE:
rules:
  - name: enforce_key_naming
    pattern: "Translation keys must use dot notation: 'auth.login.button'"

# CURRENT OUTPUT (WRONG):
"Cannot analyze: i18n extraction not implemented"

# CORRECT OUTPUT (IF WE EXTRACT I18NEXT):
"Violation: Translation key 'loginButton' doesn't follow convention
  (expected 'auth.login.button') in src/components/Login.tsx:42"
```

**Fixture Needed**: `node-i18next/` (150+ lines)
- Translation files (JSON)
- useTranslation() usage in components
- Dynamic key patterns
- spec.yaml testing i18n_keys, translation_files tables

---

### 15. Winston / Pino Logging (Found in: PlantFlow, plant)

**Usage**: Structured logging (security: log injection, sensitive data in logs)

**Missing Extraction**:
- ❌ Logger configuration
- ❌ Log statements (`logger.info()`, `logger.error()`)
- ❌ Taint flows: user input -> logs (log injection)
- ❌ Sensitive data patterns in logs

**Impact on Downstream Consumers**:
```bash
# USER RUNS:
aud detect-patterns --rule log-injection

# CURRENT OUTPUT (WRONG):
"No logging patterns detected"

# CORRECT OUTPUT (IF WE EXTRACT WINSTON/PINO):
"MEDIUM: Log injection in error handler
  - User input flows to logger.error() (src/middleware/errors.ts:25)
  - Pattern: logger.error(`User error: ${req.body.message}`)
  - Attacker can inject newlines to forge log entries"
```

**Fixture Needed**: `node-winston-pino-logging/` (200+ lines)
- Logger configuration (Winston and Pino)
- Log statements with taint flows
- Sensitive data patterns (passwords, tokens in logs)
- spec.yaml testing log_statements, log_injection_risks tables

---

## MEDIUM PRIORITY GAPS (Important but not blocking)

### 16. Puppeteer / Headless Browser (Found in: plant, PlantFlow)
- Missing: Browser automation patterns, XSS in PDF generation
- Impact: Misses SSRF, XSS in PDF reports
- Fixture: `node-puppeteer-automation/` (200+ lines)

### 17. Helmet / Security Headers (Found in: plant, PlantFlow)
- Missing: Security header configuration
- Impact: Cannot verify CSP, HSTS, X-Frame-Options
- Fixture: Add to `node-express-api/` (50+ lines)

### 18. express-rate-limit (Found in: plant, PlantFlow)
- Missing: Rate limit configuration
- Impact: Cannot detect missing rate limiting
- Fixture: Add to `node-express-api/` (50+ lines)

### 19. speakeasy / 2FA (Found in: PlantFlow)
- Missing: TOTP generation/verification
- Impact: Misses 2FA bypass vulnerabilities
- Fixture: `node-2fa-totp/` (150+ lines)

### 20. nodemailer / Email (Found in: plant, PlantFlow)
- Missing: Email sending patterns
- Impact: Misses email injection, SMTP credential leaks
- Fixture: `node-nodemailer/` (200+ lines)

### 21. jsonwebtoken / JWT (Found in: plant, PlantFlow)
- Missing: JWT sign/verify patterns
- Impact: Misses weak JWT secrets, algorithm confusion
- Fixture: `node-jwt/` (200+ lines)

### 22. bcrypt / argon2 / Password Hashing (Found in: PlantFlow, plant)
- Missing: Password hashing patterns
- Impact: Misses weak hash rounds, timing attacks
- Fixture: `node-password-hashing/` (150+ lines)

### 23. csv-writer / CSV Generation (Found in: PlantFlow)
- Missing: CSV generation patterns
- Impact: Misses CSV injection
- Fixture: `node-csv-injection/` (100+ lines)

### 24. qrcode / QR Generation (Found in: plant, PlantFlow)
- Missing: QR code generation
- Impact: Misses QR code injection patterns
- Fixture: Add to existing fixtures (50+ lines)

### 25. sharp / Image Processing (Found in: plant)
- Missing: Image manipulation
- Impact: Misses image bomb attacks, path traversal
- Fixture: `node-image-processing/` (150+ lines)

### 26. Vite PWA / Service Workers (Found in: plant)
- Missing: PWA patterns, service worker registration
- Impact: Misses cache poisoning, offline attacks
- Fixture: `node-vite-pwa/` (200+ lines)

### 27. TailwindCSS / Utility CSS (Found in: plant)
- Missing: Tailwind config, utility class patterns
- Impact: Cannot analyze styling for context rules
- Fixture: `node-tailwindcss/` (100+ lines)

### 28. @emotion/react / CSS-in-JS (Found in: plant)
- Missing: Emotion styled components
- Impact: Cannot track dynamic styles with taint flows
- Fixture: Add to `node-react-app/` (100+ lines)

### 29. moment / date-fns / Date Handling (Found in: plant, project_anarchy)
- Missing: Date manipulation patterns
- Impact: Misses timezone bugs, date injection
- Fixture: `node-date-handling/` (100+ lines)

### 30. lodash / Utility Functions (Found in: plant, project_anarchy)
- Missing: Lodash usage patterns
- Impact: Misses prototype pollution (lodash.merge)
- Fixture: `node-lodash-security/` (150+ lines)

---

## HOW TO FIX: Extraction Pipeline Enhancement

### Step 1: Create Comprehensive Fixtures (Priority Order)

**MUST FIX (Within 1 week)**:
1. `node-sequelize-orm/` (300 lines) - Critical: Both production projects use this
2. `node-bullmq-jobs/` (250 lines) - Critical: Job queues are core to async patterns
3. `node-zustand-store/` (200 lines) - Critical: State management is everywhere
4. `node-react-query/` (300 lines) - Critical: Data fetching is half of React apps
5. `node-angular-app/` (600 lines) - Critical: Enterprise market, huge user base

**HIGH PRIORITY (Within 2 weeks)**:
6. `node-mui-theming/` (250 lines)
7. `node-dexie-indexeddb/` (200 lines)
8. `node-redis-caching/` (250 lines)
9. `node-joi-zod-validation/` (300 lines)
10. `node-cron-tasks/` (200 lines)
11. `node-multer-upload/` (250 lines)
12. `node-handlebars-templates/` (200 lines)

**MEDIUM PRIORITY (Within 1 month)**:
13-30. All remaining gaps listed above

### Step 2: Enhance Extractors

**Needed Extractors** (new or enhanced):
- `theauditor/indexer/extractors/sequelize_extractor.py` (NEW)
- `theauditor/indexer/extractors/job_queue_extractor.py` (NEW)
- `theauditor/indexer/extractors/state_management_extractor.py` (NEW)
- `theauditor/indexer/extractors/angular_extractor.py` (NEW)
- Enhance `react_extractor.py` for React Query, React Router v7, Material-UI

**Schema Enhancements Needed**:
```sql
-- Job queues
CREATE TABLE job_queues (
    queue_name TEXT,
    file TEXT,
    line INTEGER
);

CREATE TABLE queue_workers (
    queue_name TEXT,
    worker_function TEXT,
    file TEXT,
    line INTEGER
);

-- State management
CREATE TABLE zustand_stores (
    store_name TEXT,
    file TEXT,
    line INTEGER
);

CREATE TABLE store_actions (
    store_name TEXT,
    action_name TEXT,
    file TEXT,
    line INTEGER
);

-- Angular
CREATE TABLE angular_components (
    component_name TEXT,
    selector TEXT,
    file TEXT,
    line INTEGER
);

CREATE TABLE angular_services (
    service_name TEXT,
    file TEXT,
    line INTEGER
);

CREATE TABLE di_injections (
    target_class TEXT,
    injected_service TEXT,
    file TEXT,
    line INTEGER
);

-- React Query
CREATE TABLE react_queries (
    query_key TEXT,
    query_function TEXT,
    component TEXT,
    file TEXT,
    line INTEGER
);

-- Redis
CREATE TABLE redis_operations (
    operation TEXT, -- 'get', 'set', 'del', etc.
    key_pattern TEXT,
    file TEXT,
    line INTEGER
);

-- File uploads
CREATE TABLE file_uploads (
    route_path TEXT,
    middleware TEXT,
    validation_config TEXT,
    file TEXT,
    line INTEGER
);

-- Templates
CREATE TABLE templates (
    template_name TEXT,
    engine TEXT, -- 'handlebars', 'ejs', etc.
    file TEXT
);

CREATE TABLE template_variables (
    template_name TEXT,
    variable_name TEXT,
    tainted BOOLEAN
);

-- Logging
CREATE TABLE log_statements (
    level TEXT, -- 'info', 'error', 'warn'
    message_template TEXT,
    file TEXT,
    line INTEGER
);

-- i18n
CREATE TABLE i18n_keys (
    key TEXT,
    namespace TEXT,
    file TEXT,
    line INTEGER
);
```

### Step 3: Update Downstream Consumers

**Commands Affected** (EVERY command that reads from repo_index.db):
- `aud blueprint` - Add sections for Sequelize, BullMQ, Zustand, Angular
- `aud planning` - Support migrations for these frameworks
- `aud taint-analyze` - Track taint through job queues, stores, validators
- `aud context` - Support business logic for i18n, themes, templates
- `aud detect-patterns` - Add rules for new security patterns
- `aud fce` - Include new hotspot types

### Step 4: Documentation

**Update**:
- `docs/extractors.md` - Document new extractors
- `docs/schema.md` - Document new tables
- `docs/fixtures.md` - Link to new fixtures
- Each fixture's README.md - Comprehensive pattern documentation

---

## VERIFICATION CHECKLIST

For each new fixture/extractor, verify:

1. ✅ Fixture code simulates real-world usage (check against plant/PlantFlow)
2. ✅ Extractor populates junction tables (not just symbols table)
3. ✅ spec.yaml has SQL JOIN queries (not just COUNT(*))
4. ✅ README.md documents all patterns, taint flows, security risks
5. ✅ Run `aud index` on fixture - verify tables populated
6. ✅ Run `aud blueprint` - verify patterns detected
7. ✅ Run `aud taint-analyze` - verify taint flows tracked
8. ✅ Run `aud planning` - verify framework migrations supported
9. ✅ Run `aud context` with custom rules - verify business logic works
10. ✅ Test on REAL project (plant or PlantFlow) - verify extraction works

---

## ESTIMATED EFFORT

**Total Lines of Code Needed**: ~8,000 lines
- Fixtures: ~5,000 lines (30+ new fixtures)
- Extractors: ~2,000 lines (8-10 new extractors)
- Schema updates: ~500 lines
- Documentation: ~500 lines

**Timeline** (if working full-time):
- Week 1: 5 critical fixtures + Sequelize extractor
- Week 2: 7 high-priority fixtures + BullMQ + React Query extractors
- Week 3: 10 medium-priority fixtures + Angular + state management extractors
- Week 4: Remaining fixtures + documentation + testing on real projects

**Reality Check**: This is 1 month of focused work. But if we don't do it, we're shipping a toy that works on our test fixtures but FAILS on real codebases.

---

## FINAL THOUGHT

You're right - the tests are dual-purpose:
1. **Traditional testing**: Does the extractor work?
2. **Real-world coverage**: Can we extract what users actually use?

We've been optimizing for (1) while ignoring (2). The result? **100% test pass rate, 50% real-world coverage.**

These gaps are NOT "nice to have enhancements". They're **existential blockers** for adoption:
- Enterprise users WILL use Angular (we have ZERO extraction)
- Production apps WILL use Sequelize (we test Prisma instead)
- React apps WILL use React Query (we have basic hooks only)
- Async processing WILL use BullMQ (we have Celery for Python, nothing for Node)

**The good news**: We have the pipeline. We just need to feed it the right fixtures and extractors. The architecture is sound - we're just missing the data sources.

**Next steps**: Start with the 5 critical fixtures. Build the Sequelize extractor. Test on plant/PlantFlow. Iterate. Ship when we hit 80% real-world coverage, not when we hit 100% test pass rate.
