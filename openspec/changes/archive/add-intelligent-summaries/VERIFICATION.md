# Prime Directive Verification Report

**Verified**: 2025-11-24 by Opus AI Lead Coder
**Against**: Live codebase at commit 283b130

This document records all verified facts from the live codebase. Any human or AI implementing this proposal MUST use these verified structures, NOT the assumptions in design.md.

---

## 1. RAW FILES VERIFIED

**Location**: `.pf/raw/` (verified via `Glob` on TheAuditor and PlantFlow)

| File | Exists | Size (PlantFlow) | Size (TheAuditor) |
|------|--------|------------------|-------------------|
| `cfg.json` | YES | 6,579 | 19,723 |
| `churn_analysis.json` | YES | 129 | 394,618 |
| `deps.json` | YES | 23,315 | 23,315 |
| `deps_latest.json` | SOMETIMES | 17,647 | NOT PRESENT |
| `fce.json` | YES | 1,313,019 | 18,774,917 |
| `fce_failures.json` | YES | 4,823 | 8,662,439 |
| `frameworks.json` | YES | 924 | 3,506 |
| `github_workflows.json` | YES | 30,822 | 79,983 |
| `graph_analysis.json` | YES | 12,108 | 11,750 |
| `graph_metrics.json` | YES | 6,306 | 7,940 |
| `graph_summary.json` | YES | 1,880 | 1,913 |
| `lint.json` | YES | 205,701 | 4,824,302 |
| `patterns.json` | YES | 702,582 | 1,799,967 |
| `taint_analysis.json` | YES | 44,088 | 19,868 |
| `terraform_findings.json` | YES | 2 | 3,836 |
| `terraform_graph.json` | YES | 319 | 25,730 |
| `vulnerabilities.json` | YES | N/A | 442 |
| `deadcode.json` | SOMETIMES | 89,433 | NOT PRESENT |

**CRITICAL CORRECTION**: Original proposal said `taint.json` - actual file is `taint_analysis.json`

---

## 2. FCE META-FINDINGS TYPES (VERIFIED)

**Source**: `theauditor/fce.py` lines 1302, 1348, 1414, 1488, 1557, 1678

| Type Constant | Line | Description |
|--------------|------|-------------|
| `ARCHITECTURAL_RISK_ESCALATION` | 1302 | Critical issues in architectural hotspots |
| `SYSTEMIC_DEBT_CLUSTER` | 1348 | Multiple issues in circular dependencies |
| `COMPLEXITY_RISK_CORRELATION` | 1414 | Complex functions with findings |
| `HIGH_CHURN_RISK_CORRELATION` | 1488 | High churn files with findings |
| `POORLY_TESTED_VULNERABILITY` | 1557 | Issues in poorly tested code |
| `GITHUB_WORKFLOW_SECRET_LEAK` | 1678 | Workflow + taint compound risk |

**Verified meta_finding structure** (from `fce_failures.json`):
```json
{
  "type": "COMPLEXITY_RISK_CORRELATION",
  "file": "backend/src/services/order.service.ts",
  "function": "OrderService.createOrder",
  "severity": "high",
  "message": "17 security findings in highly complex function (complexity: 29)",
  "description": "Function ... has cyclomatic complexity of 29...",
  "complexity": 29,
  "has_loops": true,
  "block_count": 105,
  "finding_count": 17,
  "distinct_rules": ["multi-tenant-missing-rls-context", ...],
  "sample_findings": [...],
  "supporting_count": 17
}
```

---

## 3. JSON STRUCTURE CORRECTIONS

### 3.1 patterns.json uses `pattern_name` NOT `rule`

**Verified structure**:
```json
{
  "findings": [
    {
      "category": "security",
      "column": 0,
      "file": "docker-compose.yml",
      "line": 1,
      "match_type": "database",
      "message": "Service exposes PostgreSQL port...",
      "pattern_name": "compose-database-exposed",  // NOT "rule"!
      "severity": "high",
      "snippet": ""
    }
  ]
}
```

**Implementation note**: Use `finding.get('pattern_name') or finding.get('rule')` for compatibility.

### 3.2 fce.json `all_findings` uses `rule` (normalized)

**Verified structure**:
```json
{
  "all_findings": [
    {
      "file": "...",
      "line": 5,
      "column": 0,
      "rule": "pii-unencrypted-storage",  // Normalized to "rule"
      "tool": "patterns",
      "message": "...",
      "severity": "critical",
      "category": "privacy",
      "duplicate_count": 1
    }
  ]
}
```

### 3.3 taint_analysis.json uses `paths` NOT `taint_paths`

**Verified structure**:
```json
{
  "mode": "complete",
  "engines_used": ["IFDS (backward)", "FlowResolver (forward)"],
  "flow_resolver_vulnerable": 6637,
  "flow_resolver_sanitized": 0,
  "paths": [  // NOT "taint_paths"!
    {
      "path": [
        {"file": "...", "line": 0, "name": "...", "pattern": "req", "type": "source"},
        {"type": "assignment_reverse", ...},
        {"file": "...", "line": 404, "name": "RefreshToken.findOne", "type": "sink"}
      ],
      "path_length": 5
    }
  ]
}
```

### 3.4 graph_analysis.json hotspots include `external::` prefix

**Verified structure**:
```json
{
  "cycles": [],
  "hotspots": [
    {
      "id": "external::sequelize",  // EXTERNAL packages included!
      "in_degree": 36,
      "out_degree": 0,
      "centrality": 0.935,
      "score": 11.08
    }
  ]
}
```

**Implementation note**: Filter hotspots where `id.startswith("external::")` for internal files only.

---

## 4. DATABASE SCHEMA (VERIFIED)

**Source**: `PRAGMA table_info()` on `.pf/repo_index.db`

### Key Tables for Query_Guide.json

| Table | Columns | Join Key |
|-------|---------|----------|
| `symbols` | `path, name, type, line, col, end_line, type_annotation, parameters, is_typed` | `path` |
| `refs` | `src, kind, value, line` | `src` |
| `files` | `path, sha256, ext, bytes, loc, file_category` | `path` |
| `findings_consolidated` | `id, file, line, column, rule, tool, message, severity, category, confidence, code_snippet, cwe, timestamp, details_json` | `file` |
| `function_call_args` | `file, line, caller_function, callee_function, argument_index, argument_expr, param_name, callee_file_path` | `file` |
| `frameworks` | `id, name, version, language, path, source, package_manager, is_primary` | `path` |
| `taint_flows` | `id, source_file, source_line, source_pattern, sink_file, sink_line, sink_pattern, vulnerability_type, path_length, hops, path_json, flow_sensitive` | `source_file`, `sink_file` |
| `resolved_flow_audit` | `id, source_file, source_line, source_pattern, sink_file, sink_line, sink_pattern, vulnerability_type, path_length, hops, path_json, flow_sensitive, status, sanitizer_file, sanitizer_line, sanitizer_method, engine` | `source_file`, `sink_file` |

**Note**: `taint_paths` table does NOT exist. Use `taint_flows` or `resolved_flow_audit` instead.

---

## 5. PIPELINE INTEGRATION POINTS (VERIFIED)

### 5.1 command_order (pipelines.py:446-472)

**Current sequence**:
```python
# Line 468
("taint-analyze", []),
# Line 469
("fce", []),
# Line 470
("session", ["analyze"]),  # <-- INSERT summary BEFORE this
# Line 471
("report", []),
```

**Required change**:
```python
("fce", []),
("summary", ["generate"]),  # NEW LINE - insert at line 470
("session", ["analyze"]),
("report", []),
```

### 5.2 Stage 4 Categorization (pipelines.py:676-685)

**Current code**:
```python
# Stage 4: Final aggregation (must run last)
elif "fce" in cmd_str:
    final_commands.append((phase_name, cmd))
elif "session" in cmd_str:
    final_commands.append((phase_name, cmd))
elif "report" in cmd_str:
    final_commands.append((phase_name, cmd))
```

**Required change** (add at line 679):
```python
elif "fce" in cmd_str:
    final_commands.append((phase_name, cmd))
elif "summary" in cmd_str:  # NEW LINE
    final_commands.append((phase_name, cmd))  # NEW LINE
elif "session" in cmd_str:
    final_commands.append((phase_name, cmd))
```

---

## 6. EXISTING SUMMARY.PY STRUCTURE (VERIFIED)

**Source**: `theauditor/commands/summary.py`

**Current structure**: Simple `@click.command()`, NOT a command group

```python
@click.command()
@click.option("--root", default=".", help="Root directory")
@click.option("--raw-dir", default="./.pf/raw", help="Raw outputs directory")
@click.option("--out", default="./.pf/raw/audit_summary.json", help="Output path for summary")
def summary(root, raw_dir, out):
    """Aggregate statistics from all analysis phases..."""
```

**Design Decision Required**:
- Option A: Convert to `@click.group()` with `@summary.command("generate")` subcommand
- Option B: Create new standalone command `aud generate-summaries`
- **RECOMMENDED**: Option A (maintains `aud summary` compatibility)

**Implementation for Option A**:
```python
@click.group(invoke_without_command=True)
@click.pass_context
def summary(ctx):
    """Summary commands group."""
    if ctx.invoked_subcommand is None:
        # Backward compat: run legacy summary behavior
        ctx.invoke(legacy_summary)

@summary.command("generate")
def generate():
    """Generate intelligent summary files."""
    ...

@summary.command("legacy", hidden=True)
def legacy_summary():
    """Original summary behavior (backward compat)."""
    ...
```

---

## 7. INTERSECTION LOGIC VERIFICATION

For `Quick_Start.json`, a file must have signals from 2+ DISTINCT domains:

| Domain | Signal Source | Verified Path |
|--------|--------------|---------------|
| SAST | patterns.json findings | `findings[].file` |
| Taint | taint_analysis.json paths | `paths[].path[-1].file` (sink) |
| Complexity | cfg.json or fce_failures.json | meta_findings where type=COMPLEXITY_RISK_CORRELATION |
| Churn | churn_analysis.json or fce_failures.json | meta_findings where type=HIGH_CHURN_RISK_CORRELATION |

**Filter criteria**:
```python
# Only include if 2+ domains have signals for this file
domains = set()
if file in sast_files: domains.add("sast")
if file in taint_sink_files: domains.add("taint")
if file in complexity_files: domains.add("complexity")
if file in churn_files: domains.add("churn")
include = len(domains) >= 2
```

---

## 8. WINDOWS COMPATIBILITY NOTES

Per CLAUDE.md requirements:
- Use `pathlib.Path` for all paths
- No emojis in any output (CP1252 encoding)
- Use forward slashes in paths (works in Windows)
- JSON encoding: `ensure_ascii=True` for safety

---

## VERIFICATION SIGN-OFF

All facts in this document were verified against:
- TheAuditor codebase at `C:\Users\santa\Desktop\TheAuditor`
- PlantFlow codebase at `C:\Users\santa\Desktop\PlantFlow`
- Live database `.pf/repo_index.db`
- Raw JSON files in `.pf/raw/`

Any implementation that contradicts these verified facts is WRONG.
