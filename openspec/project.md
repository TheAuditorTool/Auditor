# Project Context

## Mission & Guarantees
- TheAuditor exposes a security-first, AI-servicing CLI where the default help output is curated in `theauditor/cli.py:24` to emphasize complete audits, taint analysis, dependency checks, and sandbox setup before anything else executes.
- The audit pipeline is intentionally deterministic and offline-first; `run_full_pipeline` enforces a fixed stage order and honors the `offline` flag at `theauditor/pipelines.py:310` and `theauditor/pipelines.py:866` so network work is only attempted when explicitly requested.
- Every command the CLI spawns runs through the project sandbox (`.auditor_venv`) when available, as hard-coded in `theauditor/pipelines.py:507`, keeping host machines isolated from toolchain side effects.

## Core Runtime Flow
- Stage 1 – **Foundation**: repository indexing and framework detection are serialised to guarantee a complete manifest before any parallelism (`theauditor/pipelines.py:625`).
- Stage 2 – **Data Preparation**: workset creation, graph construction, CFG emission, and metadata collection run sequentially to prime downstream analyses (`theauditor/pipelines.py:754`).
- Stage 3 – **Parallel Heavy Analysis**: three tracks execute concurrently—taint (Track A), static + graph analyzers (Track B), and dependency/doc fetching (Track C)—with taint defaulting to an in-process engine for speed and cache reuse (`theauditor/pipelines.py:857`, `theauditor/pipelines.py:881`).
- Stage 4 – **Final Aggregation**: the Factual Correlation Engine, reporting, and summary steps consolidate outputs and propagate exit codes (`theauditor/pipelines.py:1074`).
- The pipeline logs and inventories every artifact into `.pf/pipeline.log` and `.pf/allfiles.md`, ensuring downstream agents can prove where data originated (`theauditor/pipelines.py:357`, `theauditor/pipelines.py:1276`).

## Data & Artifact Model
- `.pf/raw/` is the ground-truth store for immutable JSON findings; it is created before any phase starts so every tool can dual-write there (`theauditor/pipelines.py:371`).
- `.pf/readthis/` is regenerated per run with AI-sized capsules and is safe to hand to copilots (`theauditor/pipelines.py:382`).
- `.pf/status/` tracks live phase telemetry, enabling supervising agents to poll progress (`theauditor/pipelines.py:166` and `theauditor/pipelines.py:968`).
- The SQLite manifest (`.pf/repo_index.db`) is the single source for taint, graph, and correlation queries; its schema is centralised in `theauditor/indexer/schema.py:1` and enforced through `build_query`.

## Modules & Responsibilities
- **CLI & Commands** – Click group + command registry live in `theauditor/cli.py:24` with individual command implementations under `theauditor/commands/`, e.g. the sandbox bootstrapper in `theauditor/commands/setup.py:9`.
- **Indexer** – `IndexerOrchestrator` wires AST parsing, batch DB writes, and dynamic extractor registration (`theauditor/indexer/__init__.py:35`). Extension support is auto-discovered via `ExtractorRegistry` with AST-first mandates laid out in `theauditor/indexer/extractors/__init__.py:1`.
- **Rules & Pattern Engine** – The orchestration layer introspects every rule module, normalises inputs, and ensures schema-safe database access in `theauditor/rules/orchestrator.py:1`.
- **Taint Engine** – Source-to-sink tracing is implemented in `theauditor/taint/core.py:1`, leveraging the preloadable `MemoryCache` for O(1) lookups across 30+ indexes defined in `theauditor/taint/memory_cache.py:23`.
- **Graph Analysis** – Pure algorithmic graph operations (cycles, impact, layering) reside in `theauditor/graph/analyzer.py:1` and feed both reports and the FCE.
- **Factual Correlation Engine (FCE)** – Database-first consolidation of findings happens in `theauditor/fce.py:1`, collapsing duplicates and emitting AI-ready evidence packs.
- **Insights (Optional)** – Interpretive scoring stays quarantined in `theauditor/insights/__init__.py:1`, keeping the courier/insight split explicit.

## Performance & Caching
- The pipeline seeds a shared taint cache before Track A starts, constructing it with `MemoryCache.preload` to avoid redundant DB scans on large codebases (`theauditor/pipelines.py:772`, `theauditor/pipelines.py:881`).
- `MemoryCache` guards against double-loading and keeps signature-aware pattern maps so framework-specific taint rules can be injected without rehydrating every table (`theauditor/taint/memory_cache.py:131`).

## External Tooling & Sandbox Expectations
- Dependency and vulnerability orchestration (`aud deps`) shells out to npm audit, pip-audit, and OSV-Scanner through the sandbox; see timeout and command wiring in `theauditor/pipelines.py:418`.
- `aud setup-ai` is non-optional for JS/TS analysis and is encoded to create the Python venv, install toolchains, and download offline vulnerability data (`theauditor/commands/setup.py:9`).

## Testing & Quality Gates
- Schema contracts are verified in `tests/test_schema_contract.py:1`, guarding every consumer against column drift.
- End-to-end coverage for taint and pipeline flows lives in `tests/test_taint_e2e.py:1` and `tests/test_e2e_smoke.py:1`, ensuring regressions surface before release.
- The project expects contributors to keep `pytest`, `mypy --strict`, and `ruff check` green; these expectations are encoded directly into the documentation embedded in `theauditor/cli.py:39` and the command set exposed to users.

## Constraints & Expectations
- Never bypass `build_query` when touching the database—this is enforced both by convention in `theauditor/indexer/schema.py:20` and through the orchestrators that reject raw SQL.
- Treat `.pf/` as immutable after each phase finishes; pipeline housekeeping (archival, cleanup, file manifesting) is all centralised in `theauditor/pipelines.py:310` so new capabilities must integrate there rather than re-implementing archival logic.
