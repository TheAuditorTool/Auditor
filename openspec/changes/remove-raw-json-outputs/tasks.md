## 0. Verification

- [x] 0.1 Grep all `.pf/raw/` references in codebase - DONE (see evidence below)
- [x] 0.2 Identify all `json.dump()` file writers to `.pf/raw/` - DONE
- [x] 0.3 Map commands to their current output behavior - DONE
- [x] 0.4 Verify no external consumers depend on `.pf/raw/` files - None found

### Evidence Collected

| File | Lines | Type | Action |
|------|-------|------|--------|
| `vulnerability_scanner.py` | 550, 606 | json.dump + default path | Remove |
| `commands/docker_analyze.py` | 291 | json.dump | Remove |
| `commands/graph.py` | 93, 366, 581, 592, 598, 743, 889 | flags + json.dump | Remove |
| `commands/detect_frameworks.py` | 19, 226 | flag + json.dump | Remove |
| `commands/deps.py` | 37 | --out flag | Remove |
| `commands/cfg.py` | 53, 189 | flag + json.dump | Remove |
| `commands/terraform.py` | 76, 162, 215, 278 | flags + json.dump | Remove |
| `commands/workflows.py` | 79, 170 | flag + json.dump | Remove |
| `commands/metadata.py` | 83, 144 | --output flags | Remove |
| `commands/context.py` | 324-327 | directory creation + write | Remove |
| `commands/deadcode.py` | 206 | json.dump | Remove |
| `commands/refactor.py` | 371 | json.dump | Remove |
| `commands/taint.py` | 19 | --output flag | Remove |
| `commands/fce.py` | 202 | --write flag | Remove |
| `commands/graphql.py` | 146-147 | export to .pf/raw | Remove |
| `commands/tools.py` | 368 | json.dump (report subcommand) | Remove |
| `linters/linters.py` | 176-194 | _write_json_output() | Remove |
| `fce/engine.py` | 96-116 | write_fce_report() | Remove |
| `graph/graphql/builder.py` | 453-468 | export_courier_artifacts() | Remove |
| `indexer/metadata_collector.py` | 296, 307 | output_path defaults | Remove |
| `pipeline/pipelines.py` | 444, 1163 | .pf/raw/ references | Update |

## 1. Remove File Writers

### 1.1 vulnerability_scanner.py:550,606
Remove `_save_report()` method and standalone `save_vulnerability_report()` function.

```python
# REMOVE: lines 550-603 (_save_report method)
# REMOVE: lines 606-621 (save_vulnerability_report function)
```

### 1.2 commands/docker_analyze.py:291
Remove JSON file write in analyze command.

```python
# BEFORE (line 291)
            json.dump(docker_data, f, indent=2)

# AFTER
# Delete entire with open(...) block (~lines 288-291)
# Add --json flag to output to stdout instead
```

### 1.3 commands/graph.py:93,366,581,592,598,743,889
Remove multiple flags and json.dump calls.

```python
# REMOVE: line 93 - @click.option("--out-json", default="./.pf/raw/", ...)
# REMOVE: line 366 - @click.option("--out", default="./.pf/raw/graph_analysis.json", ...)
# REMOVE: line 743 - @click.option("--out-dir", default="./.pf/raw/", ...)
# REMOVE: lines 581, 592, 598 - json.dump() calls in analyze subcommand
# REMOVE: line 889 - json.dump() in viz subcommand
# ADD: --json flag to analyze subcommand for stdout output
```

### 1.4 commands/detect_frameworks.py:19,226
Remove --output-json flag and json.dump.

```python
# REMOVE: line 19 - @click.option("--output-json", help="Path to output JSON file...")
# REMOVE: lines 224-226 - with open(...) json.dump block
# ADD: --json flag for stdout output
```

### 1.5 commands/deps.py:37
Remove --out flag.

```python
# REMOVE: line 37 - @click.option("--out", default="./.pf/raw/deps.json", ...)
# ADD: --json flag for stdout output
```

### 1.6 commands/cfg.py:53,189
Remove --output flag and json.dump.

```python
# REMOVE: line 53 - @click.option("--output", default="./.pf/raw/cfg_analysis.json", ...)
# REMOVE: lines 187-189 - with open(...) json.dump block
# ADD: --json flag for stdout output
```

### 1.7 commands/terraform.py:76,162,215,278
Remove --output flags and json.dump calls from both subcommands.

```python
# provision subcommand:
# REMOVE: line 76 - @click.option("--output", default="./.pf/raw/terraform_graph.json", ...)
# REMOVE: lines 160-162 - with open(...) json.dump block

# analyze subcommand:
# REMOVE: line 215 - @click.option("--output", default="./.pf/raw/terraform_findings.json", ...)
# REMOVE: lines 276-278 - with open(...) json.dump block

# ADD: --json flag to both subcommands
```

### 1.8 commands/workflows.py:79,170
Remove --output flag and json.dump.

```python
# REMOVE: line 79 - @click.option("--output", default="./.pf/raw/github_workflows.json", ...)
# REMOVE: lines 168-170 - with open(...) json.dump block
# ADD: --json flag for stdout output
```

### 1.9 commands/metadata.py:83,144
Remove --output flags from churn and coverage subcommands.

```python
# churn subcommand:
# REMOVE: line 83 - @click.option("--output", default="./.pf/raw/churn_analysis.json", ...)

# coverage subcommand:
# REMOVE: line 144 - @click.option("--output", default="./.pf/raw/coverage_analysis.json", ...)

# ADD: --json flag to both subcommands
```

### 1.10 commands/context.py:324-327
Remove .pf/raw/ directory creation and file write.

```python
# REMOVE: lines 324-327
raw_dir = pf_dir / "raw"
raw_dir.mkdir(parents=True, exist_ok=True)
output_file = raw_dir / f"semantic_context_{context.context_name}.json"
```

### 1.11 commands/deadcode.py:206
Remove json.dump call.

```python
# REMOVE: lines 204-206 - with open(...) json.dump block
# ADD: --json flag for stdout output
```

### 1.12 commands/refactor.py:371
Remove json.dump call.

```python
# REMOVE: lines 369-371 - with open(...) json.dump block
```

### 1.13 linters/linters.py:176-194
Remove entire `_write_json_output()` method.

```python
# REMOVE: lines 176-201 - entire _write_json_output() method
# REMOVE: any calls to self._write_json_output() in the class
```

### 1.14 indexer/metadata_collector.py:296,307
Remove hardcoded .pf/raw/ output paths.

```python
# MODIFY: line 296 - remove output_path=".pf/raw/churn_analysis.json"
# MODIFY: line 307 - remove output_path=".pf/raw/coverage_analysis.json"
# Make these functions return data instead of writing files
```

### 1.15 commands/graphql.py:146-149
Remove Phase 5 export to .pf/raw/.

```python
# REMOVE: lines 145-149
console.print("Phase 5: Exporting courier artifacts...")
output_dir = Path(root) / ".pf" / "raw"
schema_path, execution_path = builder.export_courier_artifacts(output_dir)
console.print(f"  Exported: {schema_path.name}", highlight=False)
console.print(f"  Exported: {execution_path.name}", highlight=False)
```

### 1.16 commands/tools.py:368
Remove json.dump in report subcommand.

```python
# REMOVE: lines 366-368 - with open(...) json.dump block
# Modify report subcommand to output to stdout with --json
```

## 2. Remove/Modify Flags

### 2.1 commands/fce.py:202
Remove --write flag entirely.

```python
# REMOVE: line 202
@click.option("--write", is_flag=True, help="Write JSON report to .pf/raw/fce.json")

# REMOVE: line ~270 (parameter from function signature)
write: bool = False,

# REMOVE: lines ~290-295 (conditional write logic)
if write:
    from theauditor.fce.engine import write_fce_report
    ...
```

### 2.2 commands/taint.py:19
Remove --output flag, keep --json flag.

```python
# REMOVE: lines 19-20
@click.option(
    "--output", default="./.pf/raw/taint_analysis.json", help="Output path for analysis results"
)

# REMOVE: output parameter from function signature
# REMOVE: any file writing logic using output parameter
```

### 2.3 commands/graph.py:93,366,743
Remove --out-json, --out, --out-dir flags (covered in 1.3).

### 2.4 commands/cfg.py:53
Remove --output flag (covered in 1.6).

### 2.5 commands/metadata.py:83,144
Remove --output flags (covered in 1.9).

### 2.6 commands/terraform.py:76,215
Remove --output flags (covered in 1.7).

### 2.7 commands/workflows.py:79
Remove --output flag (covered in 1.8).

## 3. Update Pipeline

### 3.1 commands/full.py:232-239
Remove raw file counting from summary output.

```python
# REMOVE: lines 232-239
raw_files = [f for f in created_files if f.startswith(".pf/raw/")]
...
f"[dim].pf/raw/:[/dim] [cyan]{len(raw_files)}[/cyan]"
```

### 3.2 commands/full.py:255
Remove .pf/raw/ from output messaging.

```python
# REMOVE: line 255
console.print("  [cyan].pf/raw/[/cyan]              [dim]All analysis artifacts[/dim]")
```

### 3.3 commands/full.py:329
Remove .pf/raw/ reference from final message.

```python
# REMOVE: line 329
console.print("\nReview the findings in [path].pf/raw/[/path]")
```

### 3.4 pipeline/pipelines.py:444
Update docs fetch command - remove .pf/raw/deps.json reference.

```python
# BEFORE: line 444
("docs", ["fetch", "--deps", "./.pf/raw/deps.json"]),

# AFTER: Remove --deps argument or change to database query
("docs", ["fetch"]),
```

### 3.5 pipeline/pipelines.py:1163
Remove .pf/raw/taint_analysis.json reference from output message.

```python
# REMOVE: line 1163
"  Results saved to .pf/raw/taint_analysis.json",
```

## 4. Update Archive Command

### 4.1 commands/_archive.py:40
Remove .pf/raw/ from archive docstring.

```python
# REMOVE: line 40
- .pf/raw/ (raw tool outputs)
```

## 5. Update Help Text / Docstrings

### 5.1 commands/manual_lib01.py
Remove all .pf/raw/ references (lines 31, 72, 227, 237, 422, 594, 915, 1191, 1784).

### 5.2 commands/manual_lib02.py
Remove all .pf/raw/ references (lines 124, 288, 966, 967, 997, 998, 1065, 1111, 1217, 1218, 1381, 1382, 1739, 1740, 1741).

### 5.3 commands/detect_patterns.py:56,85
Remove .pf/raw/patterns.json from docstrings.

### 5.4 commands/lint.py:48,78,108,157-158
Remove .pf/raw/lint.json from docstrings.

### 5.5 commands/cfg.py:24
Remove .pf/raw/cfg.json from docstring.

### 5.6 commands/docker_analyze.py:39,81,110,216
Remove .pf/raw/docker_findings.json from docstrings.

### 5.7 commands/deps.py:84,111-113
Remove .pf/raw/*.json references from docstrings.

### 5.8 commands/detect_frameworks.py:30,53,80
Remove .pf/raw/frameworks.json from docstrings.

### 5.9 commands/fce.py:236,261
Remove .pf/raw/fce.json from docstrings.

### 5.10 commands/full.py:147
Remove .pf/raw/*.json from docstring.

### 5.11 commands/graph.py:77-78,380,793
Remove .pf/raw/ references from docstrings.

### 5.12 commands/metadata.py:22,284-285
Remove .pf/raw/ references from docstrings.

### 5.13 commands/taint.py:62,166
Remove .pf/raw/taint_analysis.json from docstrings.

### 5.14 commands/terraform.py:29,102,237
Remove .pf/raw/ references from docstrings.

### 5.15 commands/tools.py:197,211
Remove .pf/raw/tools.json from docstrings.

### 5.16 commands/workflows.py:33,110
Remove .pf/raw/ references from docstrings.

### 5.17 commands/context.py:41-42,65,76,142,172
Remove .pf/raw/ references from docstrings.

### 5.18 context/semantic_rules/templates_instructions.md:139
Remove .pf/raw/ reference from documentation.

### 5.19 context/semantic_rules/README_semantic.md:62
Remove .pf/raw/ reference from documentation.

## 6. FCE Engine

### 6.1 fce/engine.py:96-116
Remove `write_fce_report()` function entirely.

```python
# REMOVE: lines 96-116 - entire write_fce_report() function
def write_fce_report(root_path: str, min_vectors: int = 2) -> Path:
    """Run FCE and write JSON report to .pf/raw/fce.json.
    ...
```

## 7. GraphQL Builder

### 7.1 graph/graphql/builder.py:453-468
Remove `export_courier_artifacts()` method entirely.

```python
# REMOVE: lines 453-468 - entire export_courier_artifacts() method
def export_courier_artifacts(self, output_dir: Path) -> tuple[Path, Path]:
    ...
```

Also remove helper methods if only used by this:
- `_export_schema_data()` (lines 470-494)
- `_export_execution_data()` (lines 496-520)

## 8. Testing

- [ ] 8.1 Run `aud full --offline` and verify no `.pf/raw/` directory created
- [ ] 8.2 Test each modified command with `--json` flag outputs valid JSON to stdout
- [ ] 8.3 Verify `aud fce --write` returns "unrecognized option" error
- [ ] 8.4 Verify `aud taint` without args outputs to stdout, creates no files
- [ ] 8.5 Run smoke tests
- [ ] 8.6 Verify `jq` can parse output from each `--json` command

## 9. Cleanup

- [ ] 9.1 Delete existing `.pf/raw/` directory in dev environment
- [ ] 9.2 Add `.pf/raw/` to `.gitignore` as safety net
