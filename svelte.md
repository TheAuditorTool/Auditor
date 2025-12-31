Understood. I’m in **Lead Auditor** mode: evidence-first, zero-silent-failure, and we keep your **high-fidelity / full provenance** guarantees intact.  

# Pre-Implementation Plan: Add Svelte + SvelteKit Support (High-Fidelity)

## 0) Non-Negotiables (Audit Constraints)

These are the guardrails this plan is written around:

* **Verify-before-acting / no assumptions** (we will design the work to force evidence collection before implementation starts). 
* **Zero fallback / fatal on fidelity loss** (Svelte support must hard-fail if parsing/mapping fails; no “best effort” indexing that corrupts line provenance).  
* **Manifest / Receipt / Reconciliation (“Holy Trio”) for all new extraction writes**. 
* **Full call-chain provenance**: we cannot only parse `<script>` blocks; we must also capture call edges originating in **template expressions** (event handlers, bindings, inline expressions), or provenance will be broken at the UI layer.

## 1) Scope Statement (What we *will* support)

### 1.1 Svelte (.svelte)

**Goal:** Treat a `.svelte` file as a first-class citizen in your JS/TS indexing so that:

* symbols/calls/types are extracted into `repo_index.db`
* call edges are present in `graphs.db` for template-driven calls
* line/column mapping points back to the original `.svelte` file

This builds directly on your JS/TS engine’s TypeScript Compiler API approach. 

### 1.2 SvelteKit (filesystem routing + server/client boundary)

**Goal:** Index and connect:

* Pages: `+page.svelte` (+ layouts)
* Server loaders: `+page.server.(js|ts)` via `load`
* Form actions: `+page.server.(js|ts)` via `actions`
* API endpoints: `+server.(js|ts)` via exported handlers (GET/POST/…)
  …and compute route paths including advanced patterns (groups, params, rest/optional segments, matchers). ([Svelte][1]) ([Svelte][2])

### 1.3 Taint & dataflow continuity

**Goal:** Ensure taint/call/dataflow graphs don’t “stop at the boundary”:

* Loader return value → `$page.data` → page component consumption (`export let data` legacy mode, `$props()` runes mode) ([Svelte][3]) ([Svelte][4])
* Form actions treated as **write-side server entrypoints** (POST only; side-effects) ([Svelte][5])
* API endpoints from `+server` treated as standard HTTP endpoints ([Svelte][1])

## 2) Decision Log (your inputs baked in)

### DDR-1: Parser Strategy for `.svelte`

**Decision: Option B** = **transform-based** approach using the same technique the ecosystem uses for TypeScript support: convert Svelte to TSX (with source maps) and let TypeScript do the heavy lifting. This is the only option that credibly satisfies “no minimal semantics” + “full call chain provenance,” because template expressions become analyzable code. ([DeepWiki][6])

### DDR-2: New DB table for Svelte

**Decision: Yes** — add a new Svelte-focused table (details below).

### DDR-3: Differentiate endpoint types

**Proposed decision:** Add a **new column** in `api_endpoints` to differentiate *what kind* of “endpoint-like thing” it is (SvelteKit endpoint vs action vs traditional). Pages/layouts should **not** be shoved into `api_endpoints` (they aren’t HTTP endpoints); they go in the new SvelteKit routes table.

Recommended column:

* `endpoint_kind TEXT NOT NULL DEFAULT 'http'`

  * values: `http` | `sveltekit_endpoint` | `sveltekit_action`

(We keep this minimal but decisive so queries/CLI can filter cleanly without schema sprawl.)

## 3) Data Model Changes (repo_index.db)

Your system is database-first and relies on schema correctness (hard fail on mismatch).  

### 3.1 New table: `svelte_files` (DDR-2)

Purpose: store Svelte-specific metadata that doesn’t fit generic JS tables and enables route + provenance bridging.

Minimum recommended columns:

* `file_path TEXT PRIMARY KEY`
* `component_name TEXT NULL`
* `is_route_component BOOL NOT NULL`
* `route_id TEXT NULL` (FK → `sveltekit_routes.route_id`)
* `svelte_mode TEXT NOT NULL` (`legacy` | `runes`)  *(helps interpret `export let` vs `$props`)*
* `has_ts BOOL NOT NULL` (presence of `<script lang="ts">`)
* `transformer TEXT NOT NULL` (e.g., `svelte2tsx`)
* `source_map_json TEXT NOT NULL` *(critical for provenance)*
* `created_at / updated_at` optional

### 3.2 New table: `sveltekit_routes`

Purpose: canonical routing facts (so `aud query --api` doesn’t become a dumping ground for pages).

* `route_id TEXT PRIMARY KEY` (stable hash of route path + kind)
* `route_path TEXT NOT NULL` (e.g., `/blog/:slug`)
* `route_kind TEXT NOT NULL` (`page` | `layout` | `endpoint` | `action`)
* `fs_path TEXT NOT NULL` (directory under `src/routes`)
* `entry_file TEXT NOT NULL` (`+page.svelte`, `+server.ts`, etc.)
* `params_json TEXT` (list of params + matcher info)
* `has_group_segments BOOL`
* `has_rest_params BOOL`
* `has_optional_params BOOL`

### 3.3 Modify existing: `api_endpoints` (DDR-3)

* add `endpoint_kind TEXT NOT NULL DEFAULT 'http'`
* for SvelteKit:

  * `+server.*` handlers → insert `api_endpoints` row with `endpoint_kind='sveltekit_endpoint'`
  * `actions` → insert `api_endpoints` row with `endpoint_kind='sveltekit_action'`

This keeps existing tooling that expects `api_endpoints` working, while still allowing precise filtering.

## 4) Node.js Extractor Plan (AST / calls / provenance)

Your JS/TS stack is already TypeScript Compiler API driven. 

### 4.1 Core approach (Option B)

1. **Add `svelte2tsx`** (or equivalent transformer) and wire it into the existing JS extractor pipeline.

   * svelte2tsx explicitly outputs TSX + source map, which is what we need for provenance. ([npm][7])
2. For every `.svelte` file:

   * Transform → TSX + sourcemap
   * Feed TSX into the TypeScript Program as a “virtual file”
   * **Map all extracted facts back** to the original `.svelte` path + line/col using the sourcemap
3. Store sourcemap in `svelte_files.source_map_json` (so downstream phases can translate reliably without re-transforming during analysis — consistent with database-first). 

### 4.2 What “full call-chain provenance” means concretely

We must ensure these show up as call edges (not just text matches):

* `on:click={fn}`, `on:submit={handler}`, inline lambdas `on:click={() => doThing(x)}`
* template expressions `{foo(bar)}`, `{obj?.method()}`, `{#each items as item}{use(item)}{/each}`
* bindings that invoke setters / stores / runes patterns

The transform-to-TSX approach is the best practice path used by Svelte language tooling itself. ([DeepWiki][6])

### 4.3 Failure modes (must hard-fail)

* sourcemap missing/invalid
* position mapping lands outside original file bounds
* transform errors on supported syntax (esp. Svelte 5 runes mode)
  All of these should be **fatal for Svelte indexing** to comply with zero-fallback. 

## 5) Python Framework Extractor Plan (SvelteKit routing + boundary facts)

### 5.1 Detect SvelteKit projects

Heuristics (any 2 = confident):

* `src/routes/` exists
* `svelte.config.*` exists
* `@sveltejs/kit` present in dependencies

### 5.2 Route walker (must support advanced routing)

Implement canonical route computation following SvelteKit rules:

* route groups `(group)` do **not** affect URL path ([Svelte][8])
* dynamic params `[slug]` → `:slug`
* rest params `[...rest]` and their matching behavior ([Svelte][2])
* optional params `[[id]]` (from advanced routing patterns) ([Svelte][2])
* matchers `[id=matcher]` (record matcher name in `params_json`) ([Svelte][2])

### 5.3 File-to-kind mapping

* `+page.svelte` → `route_kind='page'` into `sveltekit_routes` (+ `svelte_files.is_route_component=1`)
* `+layout.svelte` → `route_kind='layout'`
* `+page.server.(js|ts)` with `load` → creates loader facts (see §6)
* `+page.server.(js|ts)` with `actions` → `api_endpoints.endpoint_kind='sveltekit_action'` ([Svelte][5])
* `+server.(js|ts)` handlers → `api_endpoints.endpoint_kind='sveltekit_endpoint'` ([Svelte][1])

## 6) Graph + Taint Bridging (the “don’t break provenance” layer)

Your pipeline explicitly builds import/call/DFG graphs and then runs taint on top.  

### 6.1 Loader → Page data continuity

SvelteKit semantics:

* server `load` feeds into page `data` (directly or via universal load). ([Svelte][3])

We need a deterministic graph representation:

* Create/identify a node for:

  * `load()` return object (server)
  * `$page.data` (conceptual boundary object)
  * component consumption (`export let data` legacy, `$props()` runes mode) ([Svelte][4])
* Add explicit `DATA_FLOW` edges to guarantee analysis doesn’t stop at the boundary.

### 6.2 Form actions as server-side write entrypoints

Actions always POST and are intended for side effects. ([Svelte][5])
Model them like endpoints:

* `actions.default` and named actions become sink/entrypoints depending on your taint model
* store in `api_endpoints` with `endpoint_kind='sveltekit_action'` so existing query paths still work

### 6.3 `+server` endpoints

Routing docs describe handler behavior (GET/HEAD relationship, etc.). ([Svelte][1])
Index each exported handler as an API endpoint with method + path.

## 7) Pipeline Integration (where this lands in “aud full”)

You run a multi-stage pipeline including graph build and taint. 

Additions:

* Stage 1 (index):

  * JS extractor includes `.svelte` via transform+map
  * framework detection identifies SvelteKit and schedules new framework extractor
* Stage 2 (detect-frameworks / detect-patterns):

  * populate `svelte_files`, `sveltekit_routes`, `api_endpoints(endpoint_kind=...)`
* Stage 2/3 (graph build / taint):

  * add synthetic edges for boundary continuity

All of these must participate in Manifest/Receipt reconciliation. 

## 8) Test Plan (acceptance gates)

### 8.1 Fidelity tests (must-pass)

* **Line mapping correctness**:

  * pick 20 call sites in template + script
  * verify `repo_index.db` line numbers point to the right `.svelte` lines
* **Call-chain completeness**:

  * a template handler calling `foo()` must show `foo` in callers/callees outputs (transitive call graph) 

### 8.2 Routing tests (must-pass)

Build a small fixture SvelteKit repo covering:

* route groups `(auth)`
* `[slug]`, `[[id]]`, `[...rest]`
* `+page`, `+layout`, `+page.server load`, `+page.server actions`, `+server`

Assert computed `route_path` matches docs semantics. ([Svelte][2])

### 8.3 Taint continuity tests (must-pass)

* loader returns `{ userInput }` → page uses it in a sink path; ensure taint can traverse the synthetic edges (no boundary stop). 

## 9) Risks & Mitigations

* **Source map drift** (highest risk): mitigated by storing sourcemaps in-db (`svelte_files`) and hard-failing on any mapping anomaly. 
* **Svelte 5 runes mode differences**: mitigate by explicitly supporting `$props()` for prop consumption modeling and recognizing runes patterns in transformed output. ([Svelte][4])
* **Schema/API ambiguity**: mitigated by DDR-3 column + separate `sveltekit_routes` (keeps your query semantics clean).

## 10) Deliverables for Review (what you’ll approve before implementation)

1. **Design/DDR doc** capturing Option B + DDR-2 + DDR-3 (this plan distilled into decisions + invariants)
2. **DB migration spec** (new tables + new column + indices)
3. **Fixture repo** (SvelteKit routing edge cases + runes + actions + endpoints)
4. **Acceptance checklist** (fidelity, routing, taint continuity, zero-fallback behavior)

---

[1]: https://svelte.dev/docs/kit/routing?utm_source=chatgpt.com "Routing • SvelteKit Docs"
[2]: https://svelte.dev/docs/kit/advanced-routing?utm_source=chatgpt.com "Advanced routing • SvelteKit Docs"
[3]: https://svelte.dev/docs/kit/load?utm_source=chatgpt.com "Loading data • SvelteKit Docs"
[4]: https://svelte.dev/docs/svelte/%24props?utm_source=chatgpt.com "$props • Svelte Docs"
[5]: https://svelte.dev/docs/kit/form-actions?utm_source=chatgpt.com "Form actions • SvelteKit Docs"
[6]: https://deepwiki.com/sveltejs/language-tools/2.1.2-typescript-integration?utm_source=chatgpt.com "TypeScript Integration | sveltejs/language-tools | DeepWiki"
[7]: https://www.npmjs.com/package/svelte2tsx?utm_source=chatgpt.com "svelte2tsx - npm"
[8]: https://svelte.dev/tutorial/kit/route-groups?utm_source=chatgpt.com "Advanced routing / Route groups • Svelte Tutorial"
