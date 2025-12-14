# TheAuditor Pipeline & Orchestration

## Overview

The `aud full` command orchestrates a **24-phase security audit pipeline** organized into **4 sequential stages** with intelligent parallelization.

Built on **Python asyncio** with Rich terminal UI, comprehensive error recovery, timeout management, and ML-friendly audit journaling.

---

## The 4 Stages

### Stage 1: Foundation (Sequential)
- **Phase 1**: Index repository (AST parsing)
- **Phase 2**: Detect frameworks

**Criticality**: Hard stop if fails - entire pipeline terminates

### Stage 2: Data Preparation (Sequential)
- **Phases 3-11**: Dependencies, workset, linting, patterns, graphs

**Criticality**: Hard stop if fails - parallel analysis requires this data

### Stage 3: Heavy Analysis (3 Parallel Tracks)

**Track A (Taint):**
- IFDS backward taint
- FlowResolver forward analysis

**Track B (Static & Graph):**
- Terraform + CDK + GitHub Actions security
- Graph analysis + 4 visualizations

**Track C (Network I/O):**
- Dependency version checks
- Documentation fetching

**Criticality**: Non-blocking - failures don't stop subsequent phases

### Stage 4: Final Aggregation (Sequential)
- **Phases 21-25**: CFG, churn, FCE, session analysis

**Criticality**: Non-blocking - partial results accepted

---

## The 24 Phases

| # | Phase | Stage | Timeout |
|---|-------|-------|---------|
| 1 | index | 1 | 600s |
| 2 | detect-frameworks | 1 | 180s |
| 3 | deps --vuln-scan | 2 | 1200s |
| 4 | deps --check-latest | 2 | 1200s |
| 5 | docs fetch | 2 | 600s |
| 6 | workset --all | 2 | 600s |
| 7 | lint --workset | 2 | 600s |
| 8 | detect-patterns | 2 | 1800s |
| 9 | graph build | 2 | 600s |
| 10 | graph build-dfg | 2 | 600s |
| 11 | terraform provision | 2 | 600s |
| 12 | taint | 3A | 1800s |
| 13-16 | terraform/cdk/workflows/graph analyze | 3B | 600s |
| 17-20 | graph viz (4 views) | 3B | 600s |
| 21 | cfg analyze | 4 | 600s |
| 22 | metadata churn | 4 | 600s |
| 23 | fce | 4 | 900s |
| 24 | session analyze | 4 | 600s |

---

## Async Architecture

### Parallel Execution
```python
tasks = []
if track_a_commands:
    tasks.append(run_taint_async())
if track_b_commands:
    tasks.append(run_chain_silent(track_b_commands))
if track_c_commands:
    tasks.append(run_chain_silent(track_c_commands))

parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Subprocess Execution with Timeout
```python
async def run_command_async(cmd, cwd, timeout=900):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    while True:
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=0.5
            )
            return PhaseResult(...)
        except TimeoutError:
            if time.time() - start > timeout:
                process.kill()
                return PhaseResult(status=FAILED, stderr="Timed out")
```

---

## Error Recovery

### Stages 1 & 2: Hard Fail
```python
if not result.success:
    renderer.on_phase_failed(phase_name, result.stderr)
    break  # STOP PIPELINE
```

### Stages 3 & 4: Non-Blocking
```python
if isinstance(result, Exception):
    failed_phases += 1
    # But continue with next phase
```

---

## Rich Terminal UI

### Live Table
```python
class DynamicTable:
    def _build_live_table(self):
        table = Table(title="Pipeline Progress")
        for name, info in self._phases.items():
            status = info["status"]
            elapsed = time.time() - info["start_time"]
            table.add_row(name, status, f"{elapsed:.1f}s")
```

**Features:**
- 4 updates/second refresh
- Real-time elapsed timers
- Colored status indicators
- Parallel track output buffering

---

## Modes

### --offline Flag
- Skips Track C (network I/O)
- No dependency version checks
- No documentation fetching
- **Use for**: CI/CD, air-gapped environments

### --index Flag (Index-Only)
- Runs only Stages 1 & 2
- Output: repo_index.db + graphs.db
- **Use for**: Fast reindex after code changes (1-3 min vs 15-20)

---

## Timeout Configuration

| Phase | Default | Env Variable |
|-------|---------|--------------|
| index | 600s | `THEAUDITOR_TIMEOUT_INDEX_SECONDS` |
| taint | 1800s | `THEAUDITOR_TIMEOUT_TAINT_SECONDS` |
| deps | 1200s | `THEAUDITOR_TIMEOUT_DEPS_SECONDS` |
| detect-patterns | 1800s | `THEAUDITOR_TIMEOUT_DETECT_PATTERNS_SECONDS` |

---

## Performance

| Codebase | Full Run | --offline | --index |
|----------|----------|-----------|---------|
| < 5K LOC | 2-3 min | 1-2 min | 1-2 min |
| 20K LOC | 5-10 min | 3-5 min | 2-3 min |
| 100K+ LOC | 15-20 min | 10-15 min | 5-10 min |

---

## Database Output

**repo_index.db** (~181MB):
- symbols, imports, function_calls
- api_endpoints, findings_consolidated
- graphql_*, cdk_*, terraform_*, workflow_*

**graphs.db** (~126MB):
- Precomputed call/import/DFG graphs
- Visualization metadata

---

## ML-Friendly Audit Journal

```python
# Events: phase_start, phase_end, file_touch, finding, pipeline_summary
# Format: Newline-delimited JSON (.ndjson)
# Location: .pf/history/{run_type}/{timestamp}/journal.ndjson
```
