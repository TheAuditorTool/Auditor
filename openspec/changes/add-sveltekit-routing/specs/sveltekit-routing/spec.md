## ADDED Requirements

### Requirement: SvelteKit project detection
The system SHALL detect SvelteKit projects when any two of the following are present: `src/routes` directory, `svelte.config.*` file, `@sveltejs/kit` dependency.

#### Scenario: Two-of-three detection
- **WHEN** `src/routes` exists and `package.json` includes `@sveltejs/kit`
- **THEN** the project is classified as SvelteKit even without `svelte.config.*`.

### Requirement: SvelteKit routes table
The system SHALL store routing facts in `sveltekit_routes` with columns `route_id`, `route_path`, `route_kind`, `fs_path`, `entry_file`, `component_file`, `load_file`, `params_json`, `has_group_segments`, `has_rest_params`, and `has_optional_params`. `route_kind` MUST be one of `page`, `layout`, or `endpoint`. The system SHALL compute `route_id` as the lowercase hex SHA-256 of `route_path + \"|\" + route_kind` (64 characters). `entry_file` SHALL be `component_file` when present, otherwise `load_file` (and `+server` for endpoints). `load_file` SHALL be set only when the file exports `load`.

#### Scenario: Route row stored
- **WHEN** `+page.svelte` exists under `src/routes/blog/[slug]`
- **THEN** `sveltekit_routes` includes route_path `/blog/:slug` and route_kind `page`.

#### Scenario: Load file recorded
- **WHEN** `src/routes/account/+page.server.ts` exports `load`
- **THEN** the `sveltekit_routes` row for `/account` has `load_file` set to that file and `entry_file` set to `+page.svelte` if present.

### Requirement: Route path computation
The system SHALL compute route_path using SvelteKit rules:
- `(group)` segments ignored
- `[param]` becomes `:param`
- `[...rest]` becomes `:rest*`
- `[[param]]` becomes `:param?`
- `[param=matcher]` becomes `:param` and records matcher in params_json
The system SHALL store `params_json` as a JSON array of objects with keys `name`, `kind`, `matcher`, `segment_index`, and `raw`.

#### Scenario: Advanced routing
- **WHEN** a route directory uses `(auth)/[[id=uuid]]/[...rest]`
- **THEN** route_path is `/:id?/:rest*`, has_group_segments=1, has_optional_params=1, has_rest_params=1, and params_json includes entries for `id` (matcher `uuid`, segment_index 0) and `rest` (segment_index 1).

#### Scenario: Root route
- **WHEN** `src/routes/+page.svelte` exists
- **THEN** route_path is `/` and has_group_segments=0.

### Requirement: Endpoint classification
The system SHALL add `endpoint_kind` to `api_endpoints` and set:
- `http` for existing endpoints (default when no framework-specific kind is provided)
- `sveltekit_endpoint` for `+server` handlers
- `sveltekit_action` for form actions

#### Scenario: +server handler
- **WHEN** `+server.ts` exports `GET`
- **THEN** api_endpoints includes method `GET` with endpoint_kind `sveltekit_endpoint`.

### Requirement: Actions as endpoints
The system SHALL treat SvelteKit actions as POST endpoints and MUST record named actions with handler_function `actions.<name>` (default uses `actions.default`). The system SHALL set `pattern`, `path`, and `full_path` to the route_path for the default action, and to `route_path + "?/" + action_name` for named actions. Actions MUST be treated as server entrypoints for boundary and taint analysis.

#### Scenario: Named action
- **WHEN** actions has `login` under route_path `/account`
- **THEN** api_endpoints includes method POST, endpoint_kind `sveltekit_action`, handler_function `actions.login`, and pattern `/account?/login`.

### Requirement: Cross-boundary matching excludes actions
The system SHALL exclude `api_endpoints` rows with `endpoint_kind='sveltekit_action'` from frontend API call matching.

#### Scenario: Action excluded from matching
- **WHEN** an endpoint is stored with endpoint_kind `sveltekit_action`
- **THEN** cross-boundary matching does not create frontend->backend edges for that endpoint.

### Requirement: Pages/layouts not in api_endpoints
The system SHALL NOT store `+page` or `+layout` entries in api_endpoints; these live only in `sveltekit_routes`.

#### Scenario: +page.svelte
- **WHEN** `+page.svelte` is present
- **THEN** api_endpoints has no row for the page file, but sveltekit_routes does.

### Requirement: Route components update svelte_files
The system SHALL mark `+page.svelte` and `+layout.svelte` as route components by setting `svelte_files.is_route_component=1` and `svelte_files.route_id` to the matching `sveltekit_routes.route_id`.

#### Scenario: Route component flagged
- **WHEN** `src/routes/blog/+page.svelte` is indexed
- **THEN** the `svelte_files` row has `is_route_component=1` and a `route_id` derived from `/blog|page`.

### Requirement: Dataflow bridging
The system SHALL create synthetic dataflow edges from `{load_file}::load::return` to `{component_file}::global::$page.data`, and from `$page.data` to `{component_file}::global::<binding_name>` for each component prop binding where `prop_name` is `data`.

#### Scenario: Load to component
- **WHEN** load returns `{ userInput }` in `+page.server.ts` and the page declares `export let data`
- **THEN** the graph includes edges from `<page.server.ts>::load::return` to `<page.svelte>::global::$page.data` and to `<page.svelte>::global::data`.

### Requirement: Fidelity reconciliation
The system SHALL include sveltekit_routes and endpoint_kind writes in manifest/receipt reconciliation.

#### Scenario: Receipt created
- **WHEN** sveltekit_routes rows are stored
- **THEN** the fidelity receipt contains a matching entry for sveltekit_routes.
