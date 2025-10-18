# Design: Restore CLI Truth Courier Mode

## Verification Summary (SOP v4.20)
- `aud --help` now fails with `ImportError` because `theauditor/ast_parser.py:28` imports `ASTExtractorMixin` while the package only ships `theauditor/ast_extractors/__init__x.py` (no `__init__.py`). Every command load path reproduces the crash.
- The quick-start banner in `theauditor/cli.py:177-199` still advertises `aud taint-analyze --workset` and `aud detect-patterns --workset`, but neither command defines that option (`theauditor/commands/taint.py:17-49`, `theauditor/commands/detect_patterns.py:11-32`). Copying the snippets raises “No such option” errors.
- The curated help text (`theauditor/cli.py:95-140`) references `aud cfg analyze --threshold 20`, contradicting the actual flag name `--complexity-threshold` (`theauditor/commands/cfg.py:51-76`), and omits newer commands such as `metadata`, `summary`, `detect-frameworks`, `tool-versions`, and `learn-feedback` even though they are registered at `theauditor/cli.py:274-323`.
- Several commands emit prescriptive guidance despite the “facts only” directive: taint prints “RECOMMENDED ACTIONS” (`theauditor/commands/taint.py:350-377`), refactor lists “Recommendations” (`theauditor/commands/refactor.py:263-277`), docker analysis outputs “Fix:” lines (`theauditor/commands/docker_analyze.py:60-74`), and dependency scanning ends with “TIP” messaging (`theauditor/commands/deps.py:264`).

## Goals
1. Restore CLI bootstrap so `aud --help` and every subcommand import cleanly.
2. Ensure curated help text mirrors real Click signatures and exposes the full command surface.
3. Eliminate prescriptive phrases from command output, returning raw facts only while preserving existing data structures.
4. Guard future regressions with validation that fails if help text or messaging diverges from the “truth courier” contract.

## Package Export Fix
- Rename `theauditor/ast_extractors/__init__x.py` to `__init__.py` and keep the current symbol exports (`ASTExtractorMixin`, language routers). This maintains the existing module layout and resolves the import error without touching downstream mixins.
- Add an import smoke test (`tests/cli/test_cli_bootstrap.py`) that calls `from theauditor.cli import cli` and verifies `cli.list_commands(ctx)` runs without raising. This test blocks future regressions where optional dependencies break the bootstrap path.

## Help Surface Synchronisation
- Replace the hard-coded command list inside `VerboseGroup.format_help` with an introspection-based renderer:
  - Iterate `cli.list_commands(ctx)` to fetch registered command names and the `click.Command`/`click.Group` instances stored in `cli.commands`.
  - Derive the first sentence of each command’s docstring (`command.help` or `command.short_help`) for factual descriptions.
  - Attach option listings by walking `command.params` and rendering option flags without inventing examples. Example output: `aud cfg analyze  --complexity-threshold INTEGER  # Analyze control flow complexity`.
  - Preserve grouping by defining explicit command categories in a mapping (`COMMAND_GROUPS = {"core": [...], "security": [...], ...}`) so help order remains intentional while still pulling docstrings/options from live definitions.
- Update the quick-start workflow text to reflect actual flags (`--complexity-threshold`, omit nonexistent `--workset` symbols). Where functionality exists (e.g., workset-aware behavior), document the true invocation (run `aud workset` first, then pass `--workset` flag only if Click exposes it).
- Add missing commands (`metadata`, `summary`, `detect-frameworks`, `tool-versions`, `learn-feedback`, etc.) to their respective categories so they appear in the detailed overview.

## Truth Courier Compliance
- Strip or rephrase prescriptive language in affected commands:
  - `taint.py`: replace the “RECOMMENDED ACTIONS” block with a neutral summary of severity totals already present in `result["summary"]` (e.g., “Severity counts: critical=…, high=…”) and rely on the JSON payload for context.
  - `refactor.py`: output the mismatches plus counts; move recommendation strings into machine-readable fields (e.g., include them in the JSON report under `suggested_followups` but do not print them during CLI execution).
  - `docker_analyze.py`: report findings with severity, file, and message only. Remove the “Fix:” prefix.
  - `deps.py`: drop the trailing “TIP” line; retain factual counts (total dependencies, outdated packages).
- Add a `TRUTHY_FORMATTERS` helper in `theauditor/utils/cli_output.py` that enforces neutral phrasing (numeric lists, counts) to avoid future reintroduction of recommendations.
- Create regression tests asserting the absence of forbidden keywords (e.g., “TIP”, “Fix:”, “Recommendation”, “RECOMMENDED ACTIONS”) in CLI stdout for the commands above when run in dry-run/fixture mode. These tests should inspect captured output strings and fail fast if disallowed phrases slip in.

## Validation & Tooling
- Introduce `scripts/check_cli_help.py` that:
  1. Imports `theauditor.cli.cli`.
  2. Renders help via `runner.invoke(cli, ["--help"])`.
  3. Fails if the output contains `--workset` for taint/detect-patterns, `--threshold`, or any missing command names.
  The script will run during `openspec validate` via a new tasks checklist entry.
- Update lint/test targets (`make cli-smoke` or `python -m pytest tests/cli`) to include the new smoke tests so CI blocks unsafe merges.

## Testing Strategy
- Unit tests: new bootstrap import test; CLI help rendering snapshot (focusing on presence of command names and absence of stale flags); output keyword guard tests for taint, refactor, docker, deps.
- Integration: invoke `aud full --quiet` within a fixture project to ensure the CLI runs end-to-end without the previous ImportError and that the log contains only factual statements.
- Documentation check: rerun `python scripts/check_cli_help.py` as part of the OpenSpec task checklist before requesting review.

## Open Questions
- `aud taint-analyze` truly lacks workset scoping today; confirm with auditor whether the correct path is to add a `--workset` flag or to remove the workflow snippet. The current design assumes documentation should match existing behavior (removal). If we later add the flag, the introspection-driven help will automatically list it.*** End Patch
