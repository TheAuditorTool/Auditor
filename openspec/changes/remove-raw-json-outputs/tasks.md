## 0. Verification (Completed 2025-12-09)

- [x] 0.1 Grep all `.pf/raw/` references in codebase - DONE
- [x] 0.2 Identify all `json.dump()` file writers to `.pf/raw/` - DONE
- [x] 0.3 Map commands to their current output behavior - DONE
- [x] 0.4 Verify no external consumers depend on `.pf/raw/` files - None found
- [x] 0.5 Inventory existing `--json` flags - 5 commands already have them

### Existing --json Flags (Do NOT duplicate)

| File | Line | Flag | Notes |
|------|------|------|-------|
| `commands/taint.py` | 24 | `--json` | Already outputs to stdout |
| `commands/impact.py` | 37 | `--json` | Already outputs to stdout |
| `commands/graphql.py` | 174 | `--json` | Already outputs to stdout |
| `commands/session.py` | 395 | `--json-output` | Already outputs to stdout |
| `commands/tools.py` | 221 | `--json` | Already outputs to stdout |

### Evidence Table (Current Line Numbers)

| File | Lines | Type | Action |
|------|-------|------|--------|
| `vulnerability_scanner.py` | 550, 566, 606, 621 | `_write_to_json()` + `write_vulnerabilities_json()` | Remove |
| `commands/deps.py` | 37 | `--out` flag default | Remove flag |
| `package_managers/deps.py` | 332, 752 | `write_deps_json()`, `_write_latest_json()` | Remove funcs |
| `commands/taint.py` | 19 | `--output` flag | Remove (keep `--json`) |
| `taint/core.py` | 972 | `json.dump()` | Remove |
| `commands/fce.py` | 202 | `--write` flag | Remove |
| `fce/engine.py` | 97-118 | `write_fce_report()` | Remove |
| `commands/graph.py` | 131, 404, 658, 669, 675, 965, 1087, 1111 | flags + json.dump | Remove |
| `commands/detect_frameworks.py` | 19, 226 | `--output-json` + json.dump | Remove |
| `commands/cfg.py` | 53, 189 | `--output` + json.dump | Remove |
| `commands/deadcode.py` | 250-255 | unconditional json.dump | Remove |
| `commands/docker_analyze.py` | 291 | conditional json.dump | Remove |
| `commands/workflows.py` | 79, 170 | `--output` + json.dump | Remove |
| `commands/terraform.py` | 76, 162, 215, 278 | `--output` flags + json.dump | Remove |
| `commands/metadata.py` | 83, 132, 144, 250, 266 | `--output` flags | Remove |
| `commands/context.py` | 332-337 | raw_dir creation + write | Remove |
| `commands/graphql.py` | 145-149 | Phase 5 export | Remove |
| `commands/tools.py` | 366-369 | report json.dump | Remove |
| `linters/linters.py` | 176-201 | `_write_json_output()` | Remove |
| `graph/graphql/builder.py` | 453-468, 461, 466 | `export_courier_artifacts()` | Remove |
| `indexer/metadata_collector.py` | 132, 283, 296, 307 | output_path writes | Remove |
| `pipeline/pipelines.py` | 487 | deps.json reference | Update |
| `pipeline/pipelines.py` | 1210 | taint message | Remove |
| `commands/full.py` | 147, 232, 239, 255, 416 | UI messages | Remove |

---

## 1. Remove File Writers

### 1.1 vulnerability_scanner.py:549-568, 605-623
Remove `_write_to_json()` method and `write_vulnerabilities_json()` function.

```python
# REMOVE: lines 549-568 (_write_to_json method)
def _write_to_json(
    self, findings: list[dict[str, Any]], output_path: str = "./.pf/raw/vulnerabilities.json"
) -> None:
    ...

# REMOVE: lines 605-623 (write_vulnerabilities_json standalone function)
def write_vulnerabilities_json(
    vulnerabilities: list[dict], output_path: str = "./.pf/raw/vulnerabilities.json"
) -> None:
    ...

# ADD: --json flag to vulnerability scanning for stdout output
```

### 1.2 package_managers/deps.py:327-333, 746-753
Remove `write_deps_json()` and latest version writing.

```python
# REMOVE: lines 327-333 (write_deps_json function)
def write_deps_json(deps: list[dict[str, Any]], output_path: str = "./.pf/deps.json") -> None:
    """Write dependencies to JSON file."""
    ...

# REMOVE: lines 746-753 (latest version json write)
with open(latest_file, "w", encoding="utf-8") as f:
    json.dump(latest_info, f, indent=2, sort_keys=True)
```

### 1.3 taint/core.py:972
Remove JSON file write at end of taint analysis.

```python
# REMOVE: lines 970-972
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(analysis_result, f, indent=2, sort_keys=True)
```

### 1.4 fce/engine.py:96-118
Remove `write_fce_report()` function entirely.

```python
# REMOVE: lines 96-118
def write_fce_report(root_path: str, min_vectors: int = 2) -> Path:
    """Run FCE and write JSON report to .pf/raw/fce.json.
    ...
```

### 1.5 commands/graph.py:658, 669, 675, 1111
Remove json.dump calls in analyze and viz subcommands.

```python
# REMOVE: lines 656-658 (analyze - main analysis dump)
with open(out, "w") as f:
    json.dump(analysis, f, indent=2)

# REMOVE: lines 667-670 (analyze - metrics dump, inside if block)
metrics_path = Path(root) / ".pf" / "raw" / "graph_metrics.json"
with open(metrics_path, "w") as f:
    json.dump(metrics, f, indent=2)

# REMOVE: lines 673-676 (analyze - summary dump)
summary_path = Path(root) / ".pf" / "raw" / "graph_summary.json"
with open(summary_path, "w") as f:
    json.dump(graph_summary, f, indent=2)

# REMOVE: lines 1109-1111 (viz - json export)
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({"nodes": graph["nodes"], "edges": graph["edges"]}, f, indent=2)

# ADD: --json flag to graph analyze for stdout output
```

### 1.6 commands/detect_frameworks.py:224-226
Remove json.dump in framework detection.

```python
# REMOVE: lines 224-226
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(frameworks, f, indent=2)

# ADD: --json flag for stdout output
```

### 1.7 commands/cfg.py:187-189
Remove json.dump in CFG analysis.

```python
# REMOVE: lines 187-189
with open(output, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

# ADD: --json flag for stdout output
```

### 1.8 commands/deadcode.py:250-255
Remove unconditional json.dump.

```python
# REMOVE: lines 250-255
output_path = project_path / ".pf" / "raw" / "deadcode.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
deadcode_data = json.loads(_format_json(modules))
with open(output_path, "w") as f:
    json.dump(deadcode_data, f, indent=2)
console.print(f"[success]Deadcode analysis saved to {output_path}[/success]")

# ADD: --json flag for stdout output
```

### 1.9 commands/docker_analyze.py:288-293
Remove conditional json.dump.

```python
# REMOVE: lines 288-293
if output:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    docker_data = {"findings": findings, "summary": severity_counts, "total": len(findings)}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(docker_data, f, indent=2)

# ADD: --json flag for stdout output
```

### 1.10 commands/workflows.py:168-170
Remove json.dump in workflow analysis.

```python
# REMOVE: lines 168-170
with open(output, "w", encoding="utf-8") as f:
    json.dump(analysis, f, indent=2)

# ADD: --json flag for stdout output
```

### 1.11 commands/terraform.py:160-162, 276-278
Remove json.dump in both terraform subcommands.

```python
# provision subcommand:
# REMOVE: lines 160-162
with open(output, "w", encoding="utf-8") as f:
    json.dump(graph, f, indent=2)

# analyze subcommand:
# REMOVE: lines 276-278
with open(output, "w", encoding="utf-8") as f:
    json.dump(findings_json, f, indent=2)

# ADD: --json flag to both subcommands
```

### 1.12 commands/context.py:332-337
Remove .pf/raw/ directory creation and file write.

```python
# REMOVE: lines 332-337
raw_dir = pf_dir / "raw"
raw_dir.mkdir(parents=True, exist_ok=True)
output_file = raw_dir / f"semantic_context_{context.context_name}.json"
context.export_to_json(result, output_file)
console.print(f"\n\\[OK] Raw results: {output_file}", highlight=False)

# Modify to only write if --output is specified
```

### 1.13 commands/graphql.py:145-149
Remove Phase 5 export to .pf/raw/.

```python
# REMOVE: lines 145-149
console.print("Phase 5: Exporting courier artifacts...")
output_dir = Path(root) / ".pf" / "raw"
schema_path, execution_path = builder.export_courier_artifacts(output_dir)
console.print(f"  Exported: {schema_path.name}", highlight=False)
console.print(f"  Exported: {execution_path.name}", highlight=False)

# GraphQL query already has --json flag at line 174
```

### 1.14 commands/tools.py:366-369
Remove json.dump in report subcommand.

```python
# REMOVE: lines 366-369
json_path = out_path / "tools.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(json_data, f, indent=2)

# tools list already has --json flag at line 221
```

### 1.15 linters/linters.py:176-201
Remove entire `_write_json_output()` method.

```python
# REMOVE: lines 176-201 - entire _write_json_output() method
def _write_json_output(self, findings: list[dict[str, Any]]):
    """Write findings to JSON file for AI consumption.
    ...

# REMOVE: any calls to self._write_json_output() in the run() method
```

### 1.16 graph/graphql/builder.py:453-468
Remove `export_courier_artifacts()` method.

```python
# REMOVE: lines 453-468
def export_courier_artifacts(self, output_dir: Path) -> tuple[Path, Path]:
    """Export GraphQL data to courier-compliant JSON artifacts."""
    ...

# Note: _export_schema_data() and _export_execution_data() can be kept
# if useful for --json output, or removed if only used by this method
```

### 1.17 indexer/metadata_collector.py:130-132, 281-283
Remove file writes in metadata collection.

```python
# REMOVE: lines 130-132 (churn)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

# REMOVE: lines 281-283 (coverage)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

# Make these functions return data instead of writing files
```

---

## 2. Remove/Modify Flags

### 2.1 commands/deps.py:37
Remove --out flag.

```python
# REMOVE: line 37
@click.option("--out", default="./.pf/raw/deps.json", help="Output dependencies file")

# REMOVE: out parameter from function signature
# ADD: --json flag for stdout output
```

### 2.2 commands/taint.py:18-20
Remove --output flag (keep existing --json at line 24).

```python
# REMOVE: lines 18-20
@click.option(
    "--output", default="./.pf/raw/taint_analysis.json", help="Output path for analysis results"
)

# REMOVE: output parameter from function signature
# KEEP: --json flag at line 24 (already exists)
```

### 2.3 commands/fce.py:202
Remove --write flag entirely.

```python
# REMOVE: line 202
@click.option("--write", is_flag=True, help="Write JSON report to .pf/raw/fce.json")

# REMOVE: write parameter from function signature
# REMOVE: conditional write logic (~lines 270-286)
# ADD: --json flag for stdout output
```

### 2.4 commands/graph.py:131, 404, 965
Remove --out-json, --out, --out-dir flags.

```python
# REMOVE: line 131 - graph build
@click.option("--out-json", default="./.pf/raw/", help="JSON output directory")

# REMOVE: line 404 - graph analyze
@click.option("--out", default="./.pf/raw/graph_analysis.json", help="Output JSON path")

# REMOVE: line 965 - graph viz
@click.option("--out-dir", default="./.pf/raw/", help="Output directory for visualizations")

# ADD: --json flag to graph analyze for stdout output
```

### 2.5 commands/detect_frameworks.py:19
Remove --output-json flag.

```python
# REMOVE: line 19
@click.option("--output-json", help="Path to output JSON file (default: .pf/raw/frameworks.json)")

# ADD: --json flag for stdout output
```

### 2.6 commands/cfg.py:53
Remove --output flag.

```python
# REMOVE: line 53
@click.option("--output", default="./.pf/raw/cfg_analysis.json", help="Output JSON file path")

# ADD: --json flag for stdout output
```

### 2.7 commands/metadata.py:83, 144
Remove --output flags from churn and coverage subcommands.

```python
# churn subcommand:
# REMOVE: line 83
@click.option("--output", default="./.pf/raw/churn_analysis.json", help="Output JSON path")

# coverage subcommand:
# REMOVE: line 144
@click.option("--output", default="./.pf/raw/coverage_analysis.json", help="Output JSON path")

# ADD: --json flag to both subcommands
```

### 2.8 commands/terraform.py:76, 215
Remove --output flags.

```python
# provision subcommand:
# REMOVE: line 76
@click.option("--output", default="./.pf/raw/terraform_graph.json", help="Output JSON path")

# analyze subcommand:
# REMOVE: line 215
@click.option("--output", default="./.pf/raw/terraform_findings.json", help="Output JSON path")

# ADD: --json flag to both subcommands
```

### 2.9 commands/workflows.py:79
Remove --output flag.

```python
# REMOVE: line 79
@click.option("--output", default="./.pf/raw/github_workflows.json", help="Output JSON path")

# ADD: --json flag for stdout output
```

### 2.10 commands/docker_analyze.py
Add --json flag (currently uses --output which is optional).

```python
# REMOVE: --output flag if it exists
# ADD: --json flag for stdout output
```

---

## 3. Update Pipeline

### 3.1 commands/full.py:232, 239
Remove raw file counting from summary output.

```python
# REMOVE: line 232
raw_files = [f for f in created_files if f.startswith(".pf/raw/")]

# MODIFY: line 239 - remove .pf/raw/ count
# BEFORE:
f"[dim].pf/raw/:[/dim] [cyan]{len(raw_files)}[/cyan]"
# AFTER: Remove this line entirely
```

### 3.2 commands/full.py:255
Remove .pf/raw/ from output messaging.

```python
# REMOVE: line 255
console.print("  [cyan].pf/raw/[/cyan]              [dim]All analysis artifacts[/dim]")
```

### 3.3 commands/full.py:416
Remove .pf/raw/ reference from final message.

```python
# REMOVE: line 416
console.print("\nReview the findings in [path].pf/raw/[/path]")

# REPLACE WITH:
console.print("\nQuery findings: [cmd]aud query --findings[/cmd]")
```

### 3.4 pipeline/pipelines.py:487
Update docs fetch command - remove .pf/raw/deps.json reference.

```python
# BEFORE: line 487
("docs", ["fetch", "--deps", "./.pf/raw/deps.json"]),

# AFTER: Remove --deps argument (docs will use parse_dependencies() fallback)
("docs", ["fetch"]),

# NOTE: docs.py:216-217 already has fallback:
# if Path(deps).exists():
#     ...
# else:
#     deps_list = parse_dependencies()
```

### 3.5 pipeline/pipelines.py:1210
Remove .pf/raw/taint_analysis.json reference from output message.

```python
# REMOVE: line 1210
"  Results saved to .pf/raw/taint_analysis.json",
```

---

## 4. Update Archive Command

### 4.1 commands/_archive.py:40
Remove .pf/raw/ from archive docstring.

```python
# REMOVE: line 40
- .pf/raw/ (raw tool outputs)
```

---

## 5. Update Help Text / Docstrings

### 5.1 commands/manual_lib01.py
Remove all .pf/raw/ references:
- Line 31: `.pf/raw/taint_analysis.json`
- Line 72: `.pf/raw/taint_analysis.json`
- Line 227: `.pf/raw/fce.json`
- Line 237: `.pf/raw/fce.json`
- Line 422: `.pf/raw/*.json`
- Line 594: `.pf/raw/patterns.json`
- Line 955: `.pf/raw/*.json`
- Line 1231: `.pf/raw/*.json`

### 5.2 commands/manual_lib02.py
Remove all .pf/raw/ references:
- Line 193: `.pf/raw/docker_findings.json`
- Line 357: `.pf/raw/lint.json`
- Line 1076: `.pf/raw/terraform_findings.json`
- Line 1077: `.pf/raw/terraform_graph.json`
- Line 1107: `.pf/raw/terraform_graph.json`
- Line 1108: `.pf/raw/terraform_findings.json`
- Line 1175: `.pf/raw/tools.json`
- Line 1221: `.pf/raw/tools.json`
- Line 1327: `.pf/raw/churn_analysis.json`
- Line 1328: `.pf/raw/coverage_analysis.json`
- Line 1491: `.pf/raw/graphql_schema.json`
- Line 1492: `.pf/raw/graphql_execution.json`
- Line 1754: `.pf/raw/deps.json`
- Line 1755: `.pf/raw/deps_latest.json`
- Line 1756: `.pf/raw/vulnerabilities.json`

### 5.3 commands/manual_lib03.py
Remove .pf/raw/ references:
- Line 382: `.pf/raw/semantic_context_<name>.json`
- Line 395: `.pf/raw/semantic_context_<name>.json`

### 5.4 Command Docstrings (embedded in each command file)

| File | Lines | Reference to Remove |
|------|-------|---------------------|
| `commands/detect_patterns.py` | 56, 85 | `.pf/raw/patterns.json` |
| `commands/lint.py` | 48, 78, 108, 157-158 | `.pf/raw/lint.json` |
| `commands/cfg.py` | 24 | `.pf/raw/cfg.json` |
| `commands/docker_analyze.py` | 39, 81, 110, 216 | `.pf/raw/docker_findings.json` |
| `commands/deps.py` | 84, 111-113 | `.pf/raw/*.json` |
| `commands/detect_frameworks.py` | 30, 53, 80 | `.pf/raw/frameworks.json` |
| `commands/fce.py` | 236, 261 | `.pf/raw/fce.json` |
| `commands/full.py` | 147 | `.pf/raw/*.json` |
| `commands/graph.py` | 115-116, 420, 1015 | `.pf/raw/*.json` |
| `commands/metadata.py` | 22, 284-285 | `.pf/raw/*.json` |
| `commands/taint.py` | 62, 166 | `.pf/raw/taint_analysis.json` |
| `commands/terraform.py` | 29, 102, 237 | `.pf/raw/*.json` |
| `commands/tools.py` | 197, 211 | `.pf/raw/tools.json` |
| `commands/workflows.py` | 33, 110 | `.pf/raw/*.json` |
| `commands/context.py` | 41-42, 73, 84, 150, 180 | `.pf/raw/*.json` |

### 5.5 Semantic Context Documentation
- `context/semantic_rules/templates_instructions.md:139`
- `context/semantic_rules/README_semantic.md:62`

---

## 6. Testing

- [ ] 6.1 Run `aud full --offline` and verify no `.pf/raw/` directory created
- [ ] 6.2 Test each modified command with `--json` flag outputs valid JSON to stdout
- [ ] 6.3 Verify `aud fce --write` returns "unrecognized option" error
- [ ] 6.4 Verify `aud taint` without args outputs to stdout (no file created)
- [ ] 6.5 Run smoke tests
- [ ] 6.6 Verify `jq` can parse output from each `--json` command:
  ```bash
  aud taint --json | jq .
  aud deps --json | jq .
  aud graph analyze --json | jq .
  aud detect-frameworks --json | jq .
  aud fce --json | jq .
  aud deadcode --json | jq .
  aud cfg analyze --json | jq .
  aud terraform analyze --json | jq .
  aud workflows analyze --json | jq .
  aud metadata churn --json | jq .
  ```
- [ ] 6.7 Verify existing --json flags still work (taint, impact, graphql, session, tools)
- [ ] 6.8 Test `docs fetch` works without `--deps` argument (uses parse_dependencies fallback)

---

## 7. Cleanup

- [ ] 7.1 Delete existing `.pf/raw/` directory in dev environment
- [ ] 7.2 Add `.pf/raw/` to `.gitignore` as safety net
- [ ] 7.3 Update CHANGELOG.md with breaking changes note:
  ```markdown
  ## [2.0.0] - YYYY-MM-DD

  ### Breaking Changes
  - Removed `.pf/raw/` JSON file outputs. Use `--json` flag for stdout output.
  - Removed flags: `--write` (fce), `--output` (taint, terraform, workflows, metadata, cfg)
  - Removed flags: `--out` (deps), `--out-json` (graph build), `--out-dir` (graph viz)
  ```

---

## Summary: Commands Requiring --json Flag Addition

| Command | Current State | Action |
|---------|---------------|--------|
| `aud taint` | Has `--json` (line 24) | Keep existing |
| `aud impact` | Has `--json` (line 37) | Keep existing |
| `aud graphql query` | Has `--json` (line 174) | Keep existing |
| `aud session analyze` | Has `--json-output` (line 395) | Keep existing |
| `aud tools list` | Has `--json` (line 221) | Keep existing |
| `aud deps` | Needs `--json` | Add |
| `aud fce` | Needs `--json` (replace `--write`) | Add |
| `aud graph analyze` | Needs `--json` | Add |
| `aud detect-frameworks` | Needs `--json` | Add |
| `aud detect-patterns` | Needs `--json` | Add |
| `aud cfg analyze` | Needs `--json` | Add |
| `aud deadcode` | Needs `--json` | Add |
| `aud docker-analyze` | Needs `--json` | Add |
| `aud workflows analyze` | Needs `--json` | Add |
| `aud terraform provision` | Needs `--json` | Add |
| `aud terraform analyze` | Needs `--json` | Add |
| `aud metadata churn` | Needs `--json` | Add |
| `aud metadata coverage` | Needs `--json` | Add |
