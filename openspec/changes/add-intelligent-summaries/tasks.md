# Implementation Tasks: Intelligent Summaries

> **CRITICAL**: All verification items below have been COMPLETED. See `VERIFICATION.md` for
> authoritative verified facts. DO NOT re-verify - use the verified data.

## 0. Verification (COMPLETED - 2025-11-24)

All assumptions verified against live codebase:

- [x] **0.1** `fce.py:1586` - `results["correlations"]["meta_findings"] = meta_findings` VERIFIED
- [x] **0.2** `pipelines.py:469-471` - command_order: fce -> session -> report VERIFIED
- [x] **0.3** Raw files VERIFIED (16 files). **CORRECTION**: `taint_analysis.json` NOT `taint.json`
- [x] **0.4** `findings_consolidated` schema VERIFIED: `id, file, line, column, rule, tool, message, severity, category, confidence, code_snippet, cwe, timestamp, details_json`
- [x] **0.5** No existing `.pf/summary/` directory VERIFIED
- [x] **0.6** `summary.py` is simple `@click.command()` NOT group - requires conversion

## 1. Create Summary Module

### 1.1 Create Module Structure
- [ ] **1.1.1** Create `theauditor/summary/__init__.py`
  - Export: `generate_all_summaries(root_path: str) -> dict`
  - Import generators from `generators.py`

- [ ] **1.1.2** Create `theauditor/summary/schemas.py`
  - Define Pydantic models for all 5 summary schemas
  - Include validation for required fields
  - MUST use `model_config = {"extra": "forbid"}` to catch schema violations

### 1.2 Implement Individual Generators

Each generator follows this pattern:
```python
def generate_X_summary(raw_dir: Path, fce_data: dict) -> dict:
    """Generate X summary from raw files.

    Args:
        raw_dir: Path to .pf/raw/
        fce_data: Loaded fce.json content

    Returns:
        Summary dict matching X schema

    Raises:
        FileNotFoundError: If required source file missing (ZERO FALLBACK)
        ValidationError: If output fails schema validation
    """
```

- [ ] **1.2.1** `generators.py::generate_sast_summary()`
  - Read: `patterns.json`, `taint_analysis.json`, `github_workflows.json`
  - Group findings by `pattern_name` OR `rule` field (patterns.json uses `pattern_name`)
  - Count `affected_files` using set of unique file paths
  - Set `fce_hotspot_overlap` by checking FCE meta_findings for file
  - Limit `sample_locations` to 3 per rule

- [ ] **1.2.2** `generators.py::generate_sca_summary()`
  - Read: `deps.json`, `vulnerabilities.json`, `frameworks.json`
  - Calculate `direct` vs `transitive` from deps.json `is_direct` field
  - Count `outdated_direct` / `outdated_transitive` separately
  - Group vulnerabilities by severity

- [ ] **1.2.3** `generators.py::generate_intelligence_summary()`
  - Read: `graph_analysis.json`, `cfg_analysis.json`, `churn_analysis.json`
  - Extract `hotspot_count`, `cycle_count` from graph_analysis
  - Calculate `complex_functions` count (complexity > 20)
  - Calculate 90th percentile threshold for churn

- [ ] **1.2.4** `generators.py::generate_quick_start_summary()`
  - Read: ALL raw files + fce.json
  - Build file index: `{file_path: {signals: set(), locations: []}}`
  - For each file, calculate signal domains (SAST, taint, complexity, churn)
  - ONLY include files with `len(domains) >= 2`
  - Build `locator_map` with exact line numbers
  - Populate `fce_context` from FCE meta_findings

- [ ] **1.2.5** `query_guide.py::generate_query_guide()`
  - Read schema from `repo_index.db` using `PRAGMA table_info()`
  - Include tables: `symbols`, `refs`, `findings_consolidated`, `taint_flows`, `resolved_flow_audit`
  - **NOTE**: `taint_paths` table does NOT exist - use `taint_flows` instead (VERIFIED)
  - Generate `tool_reference` with `aud explain`, `aud query` examples
  - Include 5 `investigation_workflows`:
    1. Security verification (SAST finding -> aud context -> FCE check)
    2. Architectural risk (complexity outlier -> imports -> churn)
    3. Taint investigation (taint path -> source -> sink)
    4. Dependency vulnerability (vuln -> imported_by -> impact)
    5. Code churn (high churn file -> recent authors -> commits)

### 1.3 Implement Orchestrator

- [ ] **1.3.1** `__init__.py::generate_all_summaries()`
  - Create `.pf/summary/` directory
  - Load `fce.json` once, pass to all generators
  - Call each generator in sequence
  - Write output to `.pf/summary/{name}.json`
  - Return dict with `{name: success/error}` for each summary
  - Handle `FileNotFoundError` by logging and continuing (partial summaries OK)

## 2. Add CLI Command

> **VERIFIED**: `summary.py` is currently a simple `@click.command()`, NOT a group.
> Must convert to `@click.group()` while preserving backward compatibility.

- [ ] **2.1** Convert `theauditor/commands/summary.py` from command to group

  **Current structure** (VERIFIED at line 11):
  ```python
  @click.command()
  @click.option("--root", default=".", help="Root directory")
  @click.option("--raw-dir", default="./.pf/raw", help="Raw outputs directory")
  @click.option("--out", default="./.pf/raw/audit_summary.json", help="Output path")
  def summary(root, raw_dir, out):
      ...
  ```

  **Required change**:
  ```python
  @click.group(invoke_without_command=True)
  @click.option("--root", default=".", help="Root directory")
  @click.option("--raw-dir", default="./.pf/raw", help="Raw outputs directory")
  @click.option("--out", default="./.pf/raw/audit_summary.json", help="Output path")
  @click.pass_context
  def summary(ctx, root, raw_dir, out):
      """Summary commands: generate intelligent summaries or legacy audit summary."""
      if ctx.invoked_subcommand is None:
          # Backward compat: run legacy summary behavior when no subcommand
          _run_legacy_summary(root, raw_dir, out)

  @summary.command("generate")
  @click.option("--root", default=".", help="Root directory")
  @click.option("--force", is_flag=True, help="Overwrite existing summaries")
  def generate(root, force):
      """Generate intelligent summary files to .pf/summary/."""
      from theauditor.summary import generate_all_summaries
      result = generate_all_summaries(root, force=force)
      # Report results...

  def _run_legacy_summary(root, raw_dir, out):
      """Original summary implementation (moved from main function)."""
      # ... existing code moved here ...
  ```

- [ ] **2.2** Create `theauditor/summary/__init__.py` with `generate_all_summaries()`
  - This is the main entry point called by the CLI command
  - Imports generators from `generators.py`

- [ ] **2.3** Verify backward compatibility
  - `aud summary` (no args) should still work as before
  - `aud summary generate` invokes new intelligent summary generation

## 3. Pipeline Integration

> **VERIFIED**: Exact line numbers from live codebase.

- [ ] **3.1** Update `pipelines.py` command_order (line 469-471)

  **Current** (VERIFIED):
  ```python
  # Line 468: ("taint-analyze", []),
  # Line 469: ("fce", []),
  # Line 470: ("session", ["analyze"]),
  # Line 471: ("report", []),
  ```

  **Required change** - insert at line 470:
  ```python
  ("taint-analyze", []),
  ("fce", []),
  ("summary", ["generate"]),  # NEW - insert here
  ("session", ["analyze"]),
  ("report", []),
  ```

- [ ] **3.2** Update `pipelines.py` Stage 4 categorization (line 676-685)

  **Current** (VERIFIED):
  ```python
  # Line 676: # Stage 4: Final aggregation (must run last)
  # Line 677: elif "fce" in cmd_str:
  # Line 678:     final_commands.append((phase_name, cmd))
  # Line 679: elif "session" in cmd_str:
  # Line 680:     final_commands.append((phase_name, cmd))
  # Line 681: elif "report" in cmd_str:
  # Line 682:     final_commands.append((phase_name, cmd))
  ```

  **Required change** - add after line 678:
  ```python
  elif "fce" in cmd_str:
      final_commands.append((phase_name, cmd))
  elif "summary" in cmd_str:  # NEW - add this block
      final_commands.append((phase_name, cmd))
  elif "session" in cmd_str:
      final_commands.append((phase_name, cmd))
  ```

- [ ] **3.3** Add phase description (line 542-545 area)
  - Add handling for `summary` command description:
  ```python
  elif cmd_name == "summary":
      description = f"{phase_num}. Generate intelligent summaries"
  ```

- [ ] **3.4** Error handling for summary generation
  - Summary failure should NOT block report generation
  - Log warning if summary generation fails
  - Continue pipeline execution (non-fatal)

## 4. Testing

- [ ] **4.1** Create `tests/test_summary_generators.py`
  - Test each generator with fixture data
  - Test ZERO FALLBACK: verify `FileNotFoundError` raised on missing files
  - Test schema validation: verify output matches Pydantic models

- [ ] **4.2** Create `tests/fixtures/summary/`
  - Add minimal `patterns.json`, `taint_analysis.json`, etc. fixtures
  - Add `fce.json` and `fce_failures.json` fixtures with meta_findings

- [ ] **4.3** Create `tests/test_summary_integration.py`
  - Test `generate_all_summaries()` end-to-end
  - Test CLI command `aud summary generate`
  - Test pipeline integration (mock subprocess)

- [ ] **4.4** Test Quick_Start intersection logic
  - Verify file with 1 signal NOT included
  - Verify file with 2+ signals IS included
  - Verify `fce_context` populated correctly

## 5. Documentation

- [ ] **5.1** Update `CLAUDE.md`
  - Add `.pf/summary/` to output structure section
  - Document `aud summary generate` command
  - Add AI guidance for using Quick_Start.json

- [ ] **5.2** Update `HowToUse.md`
  - Add summary generation to pipeline overview
  - Document summary file purposes

- [ ] **5.3** Update `openspec/project.md`
  - Add summary module to component list
  - Document Truth Courier principle

## 6. Validation

- [ ] **6.1** Run `aud full` on TheAuditor itself
  - Verify `.pf/summary/` created with 5 files
  - Verify Quick_Start.json contains expected intersections
  - Verify Query_Guide.json has accurate schema

- [ ] **6.2** Run `openspec validate add-intelligent-summaries --strict`
  - Fix any validation errors

- [ ] **6.3** Manual review of generated summaries
  - Verify no recommendations in output (Truth Courier)
  - Verify FCE correlation flags present
  - Verify line numbers accurate

## Implementation Notes

### ZERO FALLBACK Enforcement

Every generator MUST crash on missing data:
```python
# In each generator function:
source_path = raw_dir / "required_file.json"
if not source_path.exists():
    raise FileNotFoundError(
        f"Summary generation failed: {source_path} not found. "
        "Run 'aud full' to generate required raw files."
    )
```

### FCE Data Access Pattern

```python
def get_fce_meta_findings(fce_data: dict, finding_type: str) -> list:
    """Extract meta-findings of specific type from FCE output."""
    return [
        mf for mf in fce_data.get("correlations", {}).get("meta_findings", [])
        if mf.get("type") == finding_type
    ]

# Usage:
hotspot_findings = get_fce_meta_findings(fce_data, "ARCHITECTURAL_RISK_ESCALATION")
churn_findings = get_fce_meta_findings(fce_data, "HIGH_CHURN_RISK_CORRELATION")
cycle_findings = get_fce_meta_findings(fce_data, "SYSTEMIC_DEBT_CLUSTER")
```

### Intersection Calculation (VERIFIED against actual JSON structures)

```python
# VERIFIED: patterns.json uses "pattern_name", taint_analysis.json uses "paths" not "taint_paths"
# VERIFIED: graph_analysis.json hotspots have "external::" prefix - filter them out

def get_sast_files(patterns_data: dict) -> set:
    """Extract files with SAST findings."""
    return {f.get("file") for f in patterns_data.get("findings", [])}

def get_taint_sink_files(taint_data: dict) -> set:
    """Extract sink files from taint paths."""
    files = set()
    for path_obj in taint_data.get("paths", []):  # NOT "taint_paths"!
        path_list = path_obj.get("path", [])
        if path_list:
            sink = path_list[-1]  # Last item is sink
            if sink.get("type") == "sink" and sink.get("file"):
                files.add(sink["file"])
    return files

def get_complexity_files(fce_failures: dict) -> set:
    """Extract files with complexity meta-findings."""
    return {
        mf["file"] for mf in fce_failures.get("meta_findings", [])
        if mf.get("type") == "COMPLEXITY_RISK_CORRELATION"
    }

def get_churn_files(fce_failures: dict) -> set:
    """Extract files with high churn meta-findings."""
    return {
        mf["file"] for mf in fce_failures.get("meta_findings", [])
        if mf.get("type") == "HIGH_CHURN_RISK_CORRELATION"
    }

def get_internal_hotspot_files(graph_data: dict) -> set:
    """Extract internal hotspot files (filter out external:: packages)."""
    return {
        h["id"] for h in graph_data.get("hotspots", [])
        if not h.get("id", "").startswith("external::")
    }

def calculate_signal_domains(file_path: str, all_data: dict) -> set:
    """Count distinct signal domains for a file. Returns set of domain names."""
    domains = set()
    if file_path in all_data["sast_files"]:
        domains.add("sast")
    if file_path in all_data["taint_sink_files"]:
        domains.add("taint")
    if file_path in all_data["complexity_files"]:
        domains.add("complexity")
    if file_path in all_data["churn_files"]:
        domains.add("churn")
    return domains

def should_include_in_quick_start(file_path: str, all_data: dict) -> bool:
    """File must have 2+ distinct signal domains."""
    return len(calculate_signal_domains(file_path, all_data)) >= 2
```

### Windows Path Handling

Use `pathlib.Path` throughout to avoid Windows path issues:
```python
# CORRECT
raw_dir = Path(root) / ".pf" / "raw"
summary_dir = Path(root) / ".pf" / "summary"

# FORBIDDEN
raw_dir = f"{root}/.pf/raw"  # May fail on Windows
```

### No Emojis in Output

All summary files MUST use ASCII only:
```python
# CORRECT
"status": "PASS"
"severity": "high"

# FORBIDDEN - Will crash on Windows CP1252
"status": "PASS"
"severity": "high"
```
