# Proposal: Restore CLI Truth Courier Mode

## Why
- `aud --help` currently fails with `ImportError: ASTExtractorMixin`, so the CLI is unusable.
- Quick-start help still references obsolete flags (`--workset`, `--threshold`) and hides newer commands.
- Several commands emit “TIP”, “Fix”, and “Recommendation” messaging that conflicts with the truth-courier policy.

## What Changes
- Restore the AST extractor package exports so the CLI imports cleanly.
- Regenerate the detailed help output from live Click metadata and update the quick-start banner.
- Remove prescriptive messaging from taint, refactor, docker, and dependency commands while adding guard tests.
- Add automated validation to catch stale help text and forbidden terminology.

## Impact
- Users and automation regain access to the CLI help surface.
- Documented examples align with actual command signatures.
- Output stays factual, enabling downstream agents to interpret findings without embedded advice.
