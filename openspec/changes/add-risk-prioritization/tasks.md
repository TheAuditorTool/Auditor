## 0. Verification (SOP v4.20 alignment)
- [ ] 0.1 Record hypotheses, evidence, and discrepancies in `verification.md` before implementation.
- [ ] 0.2 Review current analyzer output patterns to confirm file generation behavior.
- [ ] 0.3 Review `theauditor/pipelines.py` extraction trigger (lines 1462-1476).
- [ ] 0.4 Capture baseline: list all files currently generated in `.pf/raw/` after `aud full`.

## 1. Create Consolidated Output Helper Functions
- [ ] 1.1 Create `theauditor/utils/consolidated_output.py` with `write_to_group()` helper function.
- [ ] 1.2 Implement `write_to_group(group_name, analysis_type, data)` that:
  - Loads existing group file if it exists
  - Appends new analysis to `analyses[analysis_type]` key
  - Updates `last_updated` timestamp
  - Writes back to `.pf/raw/{group_name}.json`
- [ ] 1.3 Add validation: ensure group_name is one of 6 valid consolidated files.
- [ ] 1.4 Test helper function with sample data.

## 2. Modify Graph Analyzers (theauditor/commands/graph.py)
- [ ] 2.1 Import `write_to_group` from `theauditor.utils.consolidated_output`.
- [ ] 2.2 Replace output writes in `graph build` to call `write_to_group("graph_analysis", "build", data)`.
- [ ] 2.3 Replace output writes in `graph analyze` to call `write_to_group("graph_analysis", "analyze", data)`.
- [ ] 2.4 Replace output writes in `graph viz` to call `write_to_group("graph_analysis", f"viz_{view_type}", data)`.
- [ ] 2.5 Verify `graph_analysis.json` contains all sub-analyses after running `aud graph build && aud graph analyze`.

## 3. Modify Security Analyzers
- [ ] 3.1 Update `theauditor/commands/detect_patterns.py` to write to `security_analysis.json` via `write_to_group("security_analysis", "patterns", data)`.
- [ ] 3.2 Update `theauditor/commands/taint_analyze.py` to write to `security_analysis.json` via `write_to_group("security_analysis", "taint", data)`.
- [ ] 3.3 Verify `security_analysis.json` contains both patterns and taint analyses.

## 4. Modify Quality Analyzers
- [ ] 4.1 Update `theauditor/commands/lint.py` to write to `quality_analysis.json` via `write_to_group("quality_analysis", "lint", data)`.
- [ ] 4.2 Update `theauditor/commands/cfg.py` to write to `quality_analysis.json` via `write_to_group("quality_analysis", "cfg", data)`.
- [ ] 4.3 Update `theauditor/commands/deadcode.py` to write to `quality_analysis.json` via `write_to_group("quality_analysis", "deadcode", data)`.
- [ ] 4.4 Verify `quality_analysis.json` contains all three analyses.

## 5. Modify Dependency Analyzers
- [ ] 5.1 Update `theauditor/commands/deps.py` to write to `dependency_analysis.json` via `write_to_group("dependency_analysis", "deps", data)`.
- [ ] 5.2 Update `theauditor/commands/docs.py` to write to `dependency_analysis.json` via `write_to_group("dependency_analysis", "docs", data)`.
- [ ] 5.3 Update `theauditor/commands/detect_frameworks.py` to write to `dependency_analysis.json` via `write_to_group("dependency_analysis", "frameworks", data)`.
- [ ] 5.4 Verify `dependency_analysis.json` contains all three analyses.

## 6. Modify Infrastructure Analyzers
- [ ] 6.1 Update `theauditor/commands/terraform.py` to write to `infrastructure_analysis.json` via `write_to_group("infrastructure_analysis", "terraform", data)`.
- [ ] 6.2 Update `theauditor/commands/cdk.py` to write to `infrastructure_analysis.json` via `write_to_group("infrastructure_analysis", "cdk", data)`.
- [ ] 6.3 Update `theauditor/commands/docker_analyze.py` to write to `infrastructure_analysis.json` via `write_to_group("infrastructure_analysis", "docker", data)`.
- [ ] 6.4 Update `theauditor/commands/workflows.py` to write to `infrastructure_analysis.json` via `write_to_group("infrastructure_analysis", "workflows", data)`.
- [ ] 6.5 Verify `infrastructure_analysis.json` contains all four analyses.

## 7. Modify FCE (Correlation)
- [ ] 7.1 Update `theauditor/commands/fce.py` to write to `correlation_analysis.json` (standalone, not grouped).
- [ ] 7.2 Verify `correlation_analysis.json` contains FCE meta-findings.

## 8. Create Summary Generation Command
- [ ] 8.1 Create `theauditor/commands/summarize.py` with `aud summarize` command.
- [ ] 8.2 Implement `generate_sast_summary(raw_dir)` function:
  - Load `security_analysis.json`
  - Extract all findings from patterns + taint analyses
  - Sort by severity (critical, high, medium, low)
  - Return top 20 findings + metrics
  - Include `query_alternative` field
- [ ] 8.3 Implement `generate_sca_summary(raw_dir)` function:
  - Load `dependency_analysis.json`
  - Extract CVEs, outdated packages, vulnerable deps
  - Sort by severity
  - Return top 20 issues + metrics
- [ ] 8.4 Implement `generate_intelligence_summary(raw_dir)` function:
  - Load `graph_analysis.json` + `correlation_analysis.json`
  - Extract hotspots, cycles, FCE correlations
  - Sort by impact
  - Return top 20 insights + metrics
- [ ] 8.5 Implement `generate_quick_start(raw_dir)` function:
  - Load all 3 summaries (SAST, SCA, Intelligence)
  - Extract top 10 most critical issues across ALL domains
  - Include pointers to full consolidated files
- [ ] 8.6 Implement `generate_query_guide()` function:
  - Return static reference guide with `aud query` examples per domain
  - Include performance metrics (database vs JSON parsing)
- [ ] 8.7 Register `summarize` command in `theauditor/cli.py`.

## 9. Modify Pipeline to Call Summarize
- [ ] 9.1 Update `theauditor/pipelines.py` lines 1462-1476 (extraction trigger).
- [ ] 9.2 Replace extraction call with summarize call:
  - Change log message from "[EXTRACTION]" to "[SUMMARIZE]"
  - Call `aud summarize` via subprocess
  - Log success: "[OK] Generated 5 guidance summaries in .pf/raw/"
- [ ] 9.3 Remove extraction import and function call.
- [ ] 9.4 Verify pipeline runs without errors.

## 10. Deprecate Extraction System
- [ ] 10.1 Add deprecation comment to `theauditor/extraction.py` header:
  ```python
  # DEPRECATED: Extraction system obsolete - use 'aud query' for database-first AI interaction
  # This file is kept for backward compatibility only. New code should NOT use this module.
  ```
- [ ] 10.2 Add deprecation warning to `extract_all_to_readthis()` function:
  ```python
  print("[WARN] extraction.py is deprecated - use 'aud query' for database queries instead")
  ```
- [ ] 10.3 Update `.gitignore` to exclude `.pf/readthis/`:
  ```
  # Deprecated - no longer generated
  .pf/readthis/
  ```

## 11. Update Documentation
- [ ] 11.1 Update README.md OUTPUT STRUCTURE section to show:
  - 6 consolidated files in `.pf/raw/`
  - 5 guidance summaries in `.pf/raw/`
  - NO `.pf/readthis/` directory
  - Emphasize `repo_index.db` as PRIMARY DATA SOURCE
- [ ] 11.2 Update CLI help text for `aud summarize --help`.
- [ ] 11.3 Update CLI help text for `aud report --help` to mention deprecated `.pf/readthis/`.
- [ ] 11.4 Add migration guide: "If you have scripts that read `.pf/readthis/`, update them to use `aud query` or read consolidated files in `.pf/raw/`".

## 12. Testing & Verification
- [ ] 12.1 Clean test: `rm -rf .pf/ && aud full --offline`.
- [ ] 12.2 Verify 6 consolidated files exist in `.pf/raw/`:
  - `graph_analysis.json`
  - `security_analysis.json`
  - `quality_analysis.json`
  - `dependency_analysis.json`
  - `infrastructure_analysis.json`
  - `correlation_analysis.json`
- [ ] 12.3 Verify 5 guidance summaries exist in `.pf/raw/`:
  - `SAST_Summary.json`
  - `SCA_Summary.json`
  - `Intelligence_Summary.json`
  - `Quick_Start.json`
  - `Query_Guide.json`
- [ ] 12.4 Verify `.pf/readthis/` directory is NOT created.
- [ ] 12.5 Verify summaries contain:
  - Top 20 findings (or top 10 for Quick_Start)
  - Severity counts
  - `query_alternative` field
  - Cross-references to consolidated files
  - NO recommendations (truth courier only)
- [ ] 12.6 Test database queries still work:
  - `aud query --symbol authenticate`
  - `aud query --category jwt`
  - `aud query --file api.py --show-dependencies`
- [ ] 12.7 Verify pipeline log shows "[SUMMARIZE]" instead of "[EXTRACTION]".
- [ ] 12.8 Run integration test: `aud full --offline` on test project, count files in `.pf/raw/`.

## 13. Cleanup & Final Verification
- [ ] 13.1 Remove old JSON files from previous runs (if any separate files still generated).
- [ ] 13.2 Run linters: `ruff theauditor/`, `mypy theauditor/` (if applicable).
- [ ] 13.3 Verify OpenSpec ticket passes validation: `openspec validate add-risk-prioritization`.
- [ ] 13.4 Run test suite: `pytest tests/` (if tests exist for output generation).
- [ ] 13.5 Manual smoke test: Read `Quick_Start.json` - is it human-readable and actionable?

## Completion Criteria
- ✅ 6 consolidated group files generated in `.pf/raw/`
- ✅ 5 guidance summaries generated in `.pf/raw/`
- ✅ `.pf/readthis/` directory NOT created
- ✅ All analyzers write to appropriate consolidated file
- ✅ Summaries are truth couriers (no recommendations)
- ✅ Pipeline calls `aud summarize` instead of extraction
- ✅ Extraction system marked as deprecated
- ✅ Database queries work correctly
- ✅ Documentation updated
- ✅ No regressions in `aud full` pipeline
