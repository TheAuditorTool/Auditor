# Project Context

## Purpose
TheAuditor is an offline-first, AI-centric static application security testing and code intelligence platform. It orchestrates industry-standard linters, AST analysis, taint tracking, and repository metadata to produce verifiable findings and AI-ready evidence packs that developers and AI agents can trust.

## Tech Stack
- Python 3.11+ with a Click-based CLI (`aud`) and modular `theauditor` package
- SQLite-backed repository index plus in-memory caches for taint, CFG, and graph data
- Tree-sitter parsers and custom extractors covering Python, JavaScript/TypeScript, SQL, Docker, and framework-specific patterns
- Optional extras: scikit-learn/numpy/scipy/joblib for ML scoring, tree-sitter-language-pack for AST enrichment, yaml/json tooling (PyYAML, jsonschema, ijson)
- Sandboxed Node.js toolchain in `.auditor_venv/` supplying ESLint, Prettier, TypeScript compiler, and related CLI integrations

## Project Conventions

### Code Style
- Follow PEP 8 with 100-character lines enforced by `ruff format`/`black`
- Keep `ruff check . --fix` clean; lint config enables pycodestyle, pyflakes, bugbear, and simplify rules
- Write strict, typed Python (`mypy --strict`) and add docstrings for public APIs
- Prefer descriptive names and self-documenting code; comments are reserved for complex logic

### Architecture Patterns
- Maintain the Truth Courier vs Insights separation: core modules collect facts, optional insights interpret results
- Preserve the four-stage pipeline (indexing -> preparation -> parallel heavy analysis -> aggregation) for deterministic, offline runs
- Use the extractor registry (`BaseExtractor`) and tree-sitter-backed parsing to extend language support while writing to the SQLite manifest
- Store analysis artifacts under `.pf/` and rely on in-memory caches for performance; schema contracts in `repo_index.db` must stay stable

### Testing Strategy
- Run `pytest` across unit, integration, and end-to-end suites before submitting changes
- Enforce static analysis with `mypy --strict` and the `ruff` lint/format pipeline
- Use `aud lint` (or `make lint`) to exercise orchestrated linters; many tests assume `.pf/` scaffolding created by `aud init`
- Prefer fixtures in `tests/fixtures` and integration flows in `tests/integration` when validating new extractors or taint scenarios

### Git Workflow
- Branch from `main` using `feature/<slug>` naming and keep pull requests focused
- Commit with clear, descriptive messages that explain the intent of the change
- Include test and lint results in PR descriptions; discuss larger changes via GitHub issues or roadmap alignment first

## Domain Context
TheAuditor targets multi-language repositories to surface security, architecture, and refactoring issues while remaining air-gapped. Evidence is written to `.pf/` as JSON chunks (~65 KB) and SQLite tables so AI assistants can consume ground truth without summarization. The taint engine follows sources-to-sinks across Python, Node, frontend frameworks, and SQL, while the Factual Correlation Engine cross-links findings from external tools, pattern detectors, and graph analysis.

## Important Constraints
- Default to offline execution; any network use must be opt-in (`--offline` flags exist for most commands)
- Do not collapse Truth Courier and Insights layers--insights stay optional and never mutate raw evidence
- Respect cache and schema contracts: memory caches replace disk I/O, and `repo_index.db` schema must remain compatible with taint/graph modules
- Assume the sandboxed `.auditor_venv/` provides JS/TS tooling; never require global installations
- Findings often resemble exploit payloads; never recommend disabling antivirus--design around the inevitable scanning overhead

## External Dependencies
- Core Python deps: Click, PyYAML, jsonschema, ijson, json5, sqlite3 (stdlib), plus sqlparse and dockerfile-parse for specialized parsing
- Optional extras: tree-sitter + language pack for ASTs; scikit-learn, numpy, scipy, joblib for ML insights
- Third-party CLIs orchestrated via sandbox: Ruff, MyPy, Black, Bandit, Pylint, ESLint, Prettier, TypeScript compiler, golangci-lint, go vet, hadolint, pip-audit, npm audit, OSV-Scanner
- Integrations expect Git metadata, coverage reports (coverage.py, Istanbul/nyc), and dependency manifests (pip/poetry/npm/yarn/pnpm)
