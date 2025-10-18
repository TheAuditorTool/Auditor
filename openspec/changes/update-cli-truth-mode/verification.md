# Verification

## Hypothesis: The CLI entrypoint (`aud --help`) still boots after recent refactors
- **Result:** Failed — `aud --help` now raises `ImportError: cannot import name 'ASTExtractorMixin' from 'theauditor.ast_extractors'`.
- **Evidence:** The `ast_extractors` package ships `__init__x.py` but no `__init__.py`, so `ASTExtractorMixin` is never exported (`theauditor/ast_extractors/__init__x.py:1`). Running `aud --help` reproduces the failure.
- **Discrepancy:** Any CLI invocation currently aborts before showing help, meaning users and automation cannot discover commands.

## Hypothesis: Commands referenced in quick-start docs (`taint`, `detect-patterns`) support `--workset`
- **Result:** Failed — neither command exposes a `--workset` flag.
- **Evidence:** Options declared in `theauditor/commands/taint.py:17-49` and `theauditor/commands/detect_patterns.py:11-32` omit any `--workset` flag.
- **Discrepancy:** `theauditor/cli.py:181` and `theauditor/cli.py:186` instruct users to run `aud taint-analyze --workset` and `aud detect-patterns --workset`, so following the documented workflow triggers a Click error.

## Hypothesis: CLI help snippets use current option names
- **Result:** Failed — help still advertises `aud cfg analyze --threshold 20`.
- **Evidence:** `theauditor/cli.py:194` mentions `--threshold`, but `theauditor/commands/cfg.py:51-76` defines the flag as `--complexity-threshold`.
- **Discrepancy:** Copying the example produces “No such option: --threshold”.

## Hypothesis: Detailed help enumerates all active commands
- **Result:** Failed — several commands are missing from the curated list.
- **Evidence:** The `VerboseGroup` block in `theauditor/cli.py:95-140` never mentions `aud metadata`, `aud summary`, `aud detect-frameworks`, `aud tool-versions`, or `aud learn-feedback`, even though they are registered at `theauditor/cli.py:274-323`.
- **Discrepancy:** CLI users relying on the overview cannot discover newer capabilities.

## Hypothesis: CLI output complies with the “truth courier” policy (no recommendations)
- **Result:** Failed — multiple commands still emit guidance.
- **Evidence:** Taint analysis prints a “RECOMMENDED ACTIONS” checklist (`theauditor/commands/taint.py:350-377`); refactor analysis echoes “Recommendations” with prescriptive steps (`theauditor/commands/refactor.py:263-277`); Docker analysis appends “Fix:” advice (`theauditor/commands/docker_analyze.py:60-74`); dependency scan ends with “TIP: Run with --check-latest” (`theauditor/commands/deps.py:264`).
- **Discrepancy:** Current messaging contradicts the architect’s directive to report facts only.

