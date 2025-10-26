# Node/TypeScript Support Roadmap

This plan prioritizes deterministic, framework-aware extraction (no “best effort” heuristics) so TheAuditor stays trustworthy across Node/TypeScript stacks. Focus: Vue parity, first-class validation pipelines, and better CRU (Create/Read/Update) coverage for modern build systems like Vite.

---

## 1. Current State (high level)

| Area | Status | Notes |
|------|--------|-------|
| **Generic JS/TS extraction** | ✅ Mature | Functions, classes, assignments, call graph, API endpoints, SQL tables, etc. |
| **React** | ✅ Fully indexed | `react_components` + `react_hooks` populated; downstream rules & `aud query` rely on them. |
| **Vue** | 🚧 Tables + rules exist; extractor pending | Schema + rules ready (`vue_components`, `vue_directives`, etc.), but no SFC extractor feeding them yet. |
| **Next.js** | ✅ Covered via React + file detection | Pages/components indexed via generic extractor; detection ensures rules know when Next is in play. |
| **Express/Nest/Fastify/Koa** | ✅ via generic extractor | Controllers, routes, middleware stored; rules know which framework is active. |
| **Validation libs (Zod, Joi, Yup, AJV, class-validator, express-validator)** | ⚠️ Detected but inconsistent extraction | Rules run, but we only capture what the generic extractor sees; need deeper AST hooks for schema definitions & usage. |
| **Vite/Vitest** | ⚠️ Detection in place | We parse `vite.config.*` via config scanning, but no dedicated extraction of Vite-specific entrypoints/bundler behavior. Need to confirm what data we actually store/consume. |
| **Angular** | ⚠️ Detection only | No Angular-specific extractor yet; generic JS captures class/decorator info but not templates. |

---

## 2. Prioritized Goals

1. **Vue parity** (Components, directives, hooks, provide/inject)
2. **Modern validation pipelines** (Zod, Joi, Yup, class-validator, express-validator, AJV) – deterministic extraction across controller/service layers
3. **Backend frameworks** (Express, Nest, Fastify/Koa) – ensure route/middleware semantics are stored (HTTP methods, paths, payload schemas)
4. **Vite/Vitest confirmation** – audit what data we store/use; extend if necessary (e.g., capturing aliases, env files, SSR entrypoints)
5. **Angular** (secondary priority) – maintain detection but leave deep extraction for a later phase unless a partner project depends on it

---

## 3. Workstreams

### 3.1 Vue Extraction & Rules

**Objective:** Move Vue from “detected but empty tables” to full parity with React.

- [ ] Implement `extractVueComponents()` within `framework_extractors.js` (or a new `vue_extractors.js`). It should parse `.vue` SFCs (template/script) and emit component metadata (name, script setup usage, props, emits).
- [ ] Hook into AST pipeline so `<template>` directives populate `vue_directives` (directive name, binding expression, dynamic flags).
- [ ] Capture lifecycle hooks (`setup`, `onMounted`, etc.) into `vue_hooks`.
- [ ] Store `provide`/`inject` pairs, so dependency analysis has DI info.
- [ ] Validate by indexing a sample Vue repo (create fixture if needed) and confirming `vue_*` tables have rows.
- [ ] Expand existing rules (XSS, state) to cross-reference new fields (e.g., directive scopes, script setup props).

**Deliverables:**
1. Extractor module + tests (unit + integration).
2. Updated `aud query` docs showing `--component` support for Vue.
3. Release note: “Vue extraction now populates vue_components/hooks/directives tables; XSS/state rules enforced.”

### 3.2 Validation & Sanitizer Extraction

**Objective:** Make validator pipelines first-class so rules don’t rely on string matches.

Targets: **Zod, Joi/`@hapi/joi`, Yup, Yup, AJV, class-validator, express-validator**.

Steps:
- [ ] Add AST visitors in JS/TS extractors to recognize schema definitions (e.g., `z.object({ ... })`, `const schema = Joi.object({ ... })`, `class CreateUserDto { @IsString() email: string }`).
- [ ] Normalize schema metadata into a new table (e.g., `validation_schemas`: file, name, type, source library, AST summary).
- [ ] Track where schemas are used (controller/middleware/service) by scanning assignments/call expressions.
- [ ] Update security rules to query this table instead of heuristics (e.g., “route uses express-validator” or “Zod schema applied to request body”).
- [ ] Provide `aud query` hooks (`--validator <name>`?) so AI can fetch schema definitions without opening files.

**Deliverables:**
1. Schema extraction code + DB schema updates.
2. New CLI examples in docs showing “Find routes using Zod schema X”.
3. Extended sanitizer rules leveraging the structured data.

### 3.3 Backend Framework Semantics (Express/Nest/Fastify/Koa)

**Objective:** Capture HTTP semantics (method, path, middleware stack) deterministically.

- [ ] Formalize a `http_routes` table storing controller file, method, HTTP verb, path, handler function, middleware reference.
- [ ] Extend JS extractor(s) to recognize common patterns:
  - Express: `router.get('/path', middleware?, handler)`
  - Nest: decorators `@Get('/path')`
  - Fastify/Koa: `app.route({ method, url, handler })`, `router.get(...)`
- [ ] Persist middleware chains, so security rules can verify validators/sanitizers are in place.
- [ ] Update `aud query` to support `--api /route` queries backed by this table.

**Deliverables:**
1. New DB table(s) + extractor logic.
2. CLI demo showing “List everything that hits `/api/orders`”.
3. Security/validation rules referencing the same data for enforcement.

### 3.4 Vite / Vitest Audit

**Objective:** Confirm what we already capture and whether more is needed.

- [ ] Audit `indexer/core.py` + config parsers to see what we pull out of `vite.config.*` (aliases? env? build targets?).
- [ ] Check if Vite-specific info is stored anywhere; if not, decide what matters (e.g., SSR entrypoints, env vars, alias resolution).
- [ ] Document the detection workflow in `framework_registry.py` and possibly expose `aud query --tool vite` (or similar) to show Vite config summary.
- [ ] Ensure `rules/security/sourcemap_analyze.py` has the data it needs (Vite outputs).

**Deliverables:**
1. Short audit doc (maybe in `docs/build_tool_support.md`).
2. Any necessary extractor additions (e.g., parse `defineConfig` to capture alias mappings).
3. CLI example verifying Vite data is accessible.

### 3.5 Angular (lower priority)

Angular is less common in the repos we target. For now:
- Keep detection up-to-date (Angular CLI, `angular.json`).
- Ensure generic extractor captures controllers/services (which it does).
- If future demand rises, plan an Angular-specific extractor similar to Vue’s (templates, directives, DI). Not in the current sprint.

---

## 4. Execution Approach

1. **Stack order:** Vue → Validation → Backend HTTP → Vite audit → (maybe Angular later).
2. **Verification:** For each feature, index a real or sample repo and confirm DB tables contain rows. Add tests similar to `tests/test_jsx_pass.py`.
3. **CLI demos:** Every completed workstream should have a canonical `aud query` command that showcases the new data (copy/paste into README/HOWTOUSE).
4. **Docs:** Update relevant READMEs (`semantic_rules`, `refactor/yaml_rules`, `HOWTOUSE.md`) as features land.

---

## 5. Definition of Done (per workstream)

| Workstream | DoD |
|------------|-----|
| Vue extraction | Extractor code + tests + sample CLI output + rules pulling real data |
| Validation | New schema table populated + rules/CLI referencing it |
| Backend HTTP | `http_routes` table live + queryable + rules using it |
| Vite audit | Documented data flow + any necessary extractor/plugins + CLI example |
| Angular (future) | TBD (detect demand first) |

---

This plan puts quality above breadth: each framework gets deterministic extraction before we claim support. React already sets the bar; Vue + validation + HTTP semantics are next so Node workflows feel equally robust. Once these land, we can revisit Angular or other niches with the same standard.
