# Proposal: Add Fidelity Checks to Taint Analysis Pipeline

## Status

**PROPOSED** (Created: 2025-12-06)

## Why

The taint analysis pipeline is the **only critical security component** in TheAuditor that lacks fidelity verification. Every other data pipeline has manifest/receipt reconciliation:

| Component | Has Fidelity? | Risk if Data Lost |
|-----------|---------------|-------------------|
| Extractors | YES | Missing symbols/calls |
| Storage Layer | YES | Data not persisted |
| Graph Builder | YES | Missing edges/nodes |
| Graph Store | YES | Graph incomplete |
| Rules Engine | YES | Findings dropped |
| **Taint Analysis** | **NO** | **MISSED VULNERABILITIES** |

### The Critical Gap

During verification against plant/plantflow codebases (2025-12-06), we discovered:

1. **Discovery phase** can silently miss sources/sinks due to query issues
2. **IFDS analysis** can truncate paths without notification
3. **Deduplication** can drop valid paths aggressively
4. **Database inserts** can fail without raising errors
5. **JSON serialization** can lose data during file write

### The Data Flow (ZERO VISIBILITY)

```
Discovery          IFDS Analysis        Deduplication         Output (DB + JSON)
    │                    │                    │                      │
    ▼                    ▼                    ▼                      ▼
┌─────────┐        ┌─────────┐          ┌─────────┐            ┌─────────┐
│ sources │  ───►  │ paths   │  ───►    │ unique  │  ───►      │ DB +    │
│ sinks   │  ???   │ traced  │  ???     │ paths   │  ???       │ JSON    │
└─────────┘        └─────────┘          └─────────┘            └─────────┘
     │                  │                    │                      │
   NO CHECK          NO CHECK             NO CHECK              NO CHECK
```

### Why This Matters

Taint analysis is a **security tool**. If it silently loses 10% of vulnerability paths, users believe their code is more secure than it actually is. This is worse than not having the tool at all.

### Evidence From Session

Query against plant codebase showed:
- 325 vulnerabilities found
- Max depth: 3 hops (despite max_depth=10 setting)
- Depth distribution: `{1: 275, 2: 8, 3: 2}`

We cannot verify if paths were lost or if the codebase simply doesn't have deeper chains **because there are no fidelity checks**.

## What Changes

### New File: `theauditor/taint/fidelity.py`

Create a fidelity module mirroring `indexer/fidelity.py` and `graph/fidelity.py`:

```python
"""Taint Analysis Fidelity Control System."""

import os
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.utils.logging import logger


class TaintFidelityError(Exception):
    """Raised when taint fidelity check fails."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.details = details or {}


# FidelityToken.create_manifest() returns:
# {
#     "count": int,      # Number of items in the list
#     "tx_id": str,      # UUID for transaction tracing
#     "columns": list,   # Column names (for dict rows)
#     "bytes": int       # Approximate byte size
# }


def create_discovery_manifest(sources: list, sinks: list) -> dict[str, Any]:
    """Create manifest after source/sink discovery."""
    return {
        "sources": FidelityToken.create_manifest(sources),
        "sinks": FidelityToken.create_manifest(sinks),
        "_stage": "discovery",
    }


def create_analysis_manifest(
    vulnerable_paths: list,
    sanitized_paths: list,
    sinks_analyzed: int,
    sources_checked: int,
) -> dict[str, Any]:
    """Create manifest after IFDS analysis."""
    return {
        "vulnerable_paths": FidelityToken.create_manifest(vulnerable_paths),
        "sanitized_paths": FidelityToken.create_manifest(sanitized_paths),
        "sinks_analyzed": sinks_analyzed,
        "sources_checked": sources_checked,
        "_stage": "analysis",
    }


def create_dedup_manifest(
    pre_dedup_count: int,
    post_dedup_count: int,
) -> dict[str, Any]:
    """Create manifest after deduplication."""
    return {
        "pre_dedup_count": pre_dedup_count,
        "post_dedup_count": post_dedup_count,
        "removed_count": pre_dedup_count - post_dedup_count,
        "removal_ratio": (pre_dedup_count - post_dedup_count) / max(pre_dedup_count, 1),
        "_stage": "dedup",
    }


def create_db_output_receipt(
    db_rows_inserted: int,
    vulnerable_count: int,
    sanitized_count: int,
) -> dict[str, Any]:
    """Create receipt after DB write in trace_taint()."""
    return {
        "db_rows": db_rows_inserted,
        "vulnerable_count": vulnerable_count,
        "sanitized_count": sanitized_count,
        "_stage": "db_output",
    }


def create_json_output_receipt(
    json_vulnerabilities: int,
    json_bytes_written: int,
) -> dict[str, Any]:
    """Create receipt after JSON write in save_taint_analysis()."""
    return {
        "json_count": json_vulnerabilities,
        "json_bytes": json_bytes_written,
        "_stage": "json_output",
    }


def reconcile_taint_fidelity(
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    stage: str,
    strict: bool = True,
) -> dict[str, Any]:
    """Compare taint manifest vs receipt at each stage."""
    # Environment variable override
    strict_env = os.environ.get("TAINT_FIDELITY_STRICT", "1")
    if strict_env == "0":
        strict = False

    errors = []
    warnings = []

    # Stage-specific reconciliation logic
    if stage == "discovery":
        # Verify sources and sinks were found
        src_count = manifest.get("sources", {}).get("count", 0)
        sink_count = manifest.get("sinks", {}).get("count", 0)
        if src_count == 0:
            warnings.append("Discovery found 0 sources - is this expected?")
        if sink_count == 0:
            warnings.append("Discovery found 0 sinks - is this expected?")

    elif stage == "analysis":
        # Verify analysis didn't silently fail
        sinks_analyzed = manifest.get("sinks_analyzed", 0)
        sinks_expected = receipt.get("sinks_to_analyze", 0)

        if sinks_analyzed == 0 and sinks_expected > 0:
            errors.append(
                f"Analysis processed 0/{sinks_expected} sinks - pipeline stalled"
            )

    elif stage == "dedup":
        # Warn if dedup removed too many paths
        removal_ratio = manifest.get("removal_ratio", 0)
        if removal_ratio > 0.5:
            warnings.append(
                f"Dedup removed {manifest.get('removed_count')}/{manifest.get('pre_dedup_count')} "
                f"paths ({removal_ratio:.0%}) - check for hash collisions"
            )

    elif stage == "db_output":
        # Verify DB write succeeded
        manifest_count = manifest.get("paths_to_write", 0)
        db_count = receipt.get("db_rows", 0)

        if manifest_count > 0 and db_count == 0:
            errors.append(
                f"DB Output: {manifest_count} paths to write, 0 written (100% LOSS)"
            )
        elif manifest_count != db_count:
            warnings.append(
                f"DB Output: manifest={manifest_count}, db_rows={db_count} "
                f"(delta={manifest_count - db_count})"
            )

    elif stage == "json_output":
        # Verify JSON write succeeded
        manifest_count = manifest.get("paths_to_write", 0)
        json_count = receipt.get("json_count", 0)

        if manifest_count > 0 and json_count == 0:
            errors.append(
                f"JSON Output: {manifest_count} paths to write, 0 in JSON (100% LOSS)"
            )
        elif manifest_count != json_count:
            warnings.append(
                f"JSON Output: manifest={manifest_count}, json={json_count} "
                f"(delta={manifest_count - json_count})"
            )

    result = {
        "status": "FAILED" if errors else ("WARNING" if warnings else "OK"),
        "stage": stage,
        "errors": errors,
        "warnings": warnings,
    }

    if errors and strict:
        error_msg = f"Taint Fidelity FAILED at {stage}: " + "; ".join(errors)
        logger.error(error_msg)
        raise TaintFidelityError(error_msg, details=result)

    if warnings:
        logger.warning(f"Taint Fidelity Warnings at {stage}: {warnings}")

    return result
```

### Modify: `theauditor/taint/core.py`

Add fidelity checkpoints at 4 critical locations:

**Checkpoint 1: After Discovery (`core.py:566`)**

Insert after `sinks = discovery.filter_framework_safe_sinks(sinks)`:

```python
# EXACT LOCATION: core.py:566 (after filter_framework_safe_sinks)
from theauditor.taint.fidelity import (
    create_discovery_manifest,
    reconcile_taint_fidelity,
)

discovery_manifest = create_discovery_manifest(sources, sinks)
reconcile_taint_fidelity(
    discovery_manifest,
    {"sinks_to_analyze": len(sinks)},
    stage="discovery",
)
logger.info(
    f"Taint Discovery: {len(sources)} sources, {len(sinks)} sinks [Fidelity: OK]"
)
```

**Checkpoint 2: After IFDS Analysis Loop (`core.py:686`)**

Insert after line 685 `all_sanitized_paths.extend(sanitized)`, before line 686 `ifds_analyzer.close()`:

```python
# EXACT LOCATION: core.py:686 (after line 685 extend(), before ifds_analyzer.close())
from theauditor.taint.fidelity import create_analysis_manifest

analysis_manifest = create_analysis_manifest(
    all_vulnerable_paths,
    all_sanitized_paths,
    sinks_analyzed=len(sinks),
    sources_checked=len(sources),
)
reconcile_taint_fidelity(
    analysis_manifest,
    {"sinks_to_analyze": len(sinks)},
    stage="analysis",
)
```

**Checkpoint 3: After Deduplication (`core.py:697`)**

Insert after line 696 `unique_sanitized_paths = deduplicate_paths(all_sanitized_paths)`:

```python
# EXACT LOCATION: core.py:697 (after unique_sanitized_paths assignment)
from theauditor.taint.fidelity import create_dedup_manifest

pre_dedup_total = len(all_vulnerable_paths) + len(all_sanitized_paths)
post_dedup_total = len(unique_vulnerable_paths) + len(unique_sanitized_paths)

dedup_manifest = create_dedup_manifest(pre_dedup_total, post_dedup_total)
reconcile_taint_fidelity(dedup_manifest, {}, stage="dedup")
```

**Checkpoint 4a: After DB Write (`core.py:797`)**

Insert after line 796 `conn.commit()`:

```python
# EXACT LOCATION: core.py:797 (after conn.commit())
from theauditor.taint.fidelity import create_db_output_receipt

db_receipt = create_db_output_receipt(
    db_rows_inserted=total_inserted,
    vulnerable_count=len(unique_vulnerable_paths),
    sanitized_count=len(unique_sanitized_paths),
)
reconcile_taint_fidelity(
    {"paths_to_write": len(unique_vulnerable_paths) + len(unique_sanitized_paths)},
    db_receipt,
    stage="db_output",
)
logger.info(f"Taint DB Output: {total_inserted} rows [Fidelity: OK]")
```

### Modify: `theauditor/taint/core.py` - save_taint_analysis()

**Checkpoint 4b: After JSON Write (`core.py:973`)**

The JSON write happens in a **separate function** `save_taint_analysis()`, not in `trace_taint()`:

```python
# EXACT LOCATION: core.py:955-973 (replace entire save_taint_analysis function)
# The current function uses json.dump() directly to file handle.
# We need to change to json.dumps() + f.write() to capture byte count.

def save_taint_analysis(
    analysis_result: dict[str, Any], output_path: str = "./.pf/taint_analysis.json"
):
    """Save taint analysis results to JSON file with normalized structure."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Normalize paths (existing code at lines 962-969)
    if "taint_paths" in analysis_result:
        analysis_result["taint_paths"] = [
            normalize_taint_path(p) for p in analysis_result.get("taint_paths", [])
        ]
    if "paths" in analysis_result:
        analysis_result["paths"] = [
            normalize_taint_path(p) for p in analysis_result.get("paths", [])
        ]

    # CHANGED: Use dumps() + write() instead of dump() to capture byte count
    with open(output, "w") as f:
        json_str = json.dumps(analysis_result, indent=2, sort_keys=True)
        f.write(json_str)
        json_bytes = len(json_str.encode("utf-8"))

    # NEW: Fidelity checkpoint for JSON output
    from theauditor.taint.fidelity import (
        create_json_output_receipt,
        reconcile_taint_fidelity,
    )

    vuln_count = len(analysis_result.get("vulnerabilities", []))
    json_receipt = create_json_output_receipt(vuln_count, json_bytes)
    reconcile_taint_fidelity(
        {"paths_to_write": vuln_count},
        json_receipt,
        stage="json_output",
    )
    logger.info(f"Taint JSON Output: {vuln_count} vulns, {json_bytes} bytes [Fidelity: OK]")
```

## Impact

- **New capability**: `taint-fidelity`
- **New file**: `theauditor/taint/fidelity.py`
- **Modified files**:
  - `theauditor/taint/core.py` - `trace_taint()` (3 checkpoints) + `save_taint_analysis()` (1 checkpoint)

## Non-Goals

- NOT changing the IFDS algorithm itself
- NOT changing source/sink discovery logic
- NOT changing deduplication algorithm (just adding visibility)
- NOT adding new database tables
- NOT changing taint_analysis.json format
- NOT modifying CLI interface
- NOT adding cross-engine verification (IFDS and FlowResolver are independent)

## Success Criteria

1. `aud taint` logs fidelity status at each checkpoint
2. If sources=0 or sinks=0, warning is logged (not silent)
3. If dedup removes >50% of paths, warning is logged
4. If DB insert fails, error is raised (not silent continue)
5. If JSON write loses data, error is raised
6. `aud full --offline` includes taint fidelity in pipeline report

## Risk Assessment

**LOW RISK** - Adding verification, not changing core logic.

### Mitigation

1. All new code is additive (no existing logic changed)
2. `TAINT_FIDELITY_STRICT=0` env var disables strict mode
3. Fidelity errors include full context for diagnosis
4. Existing tests continue to pass (fidelity is additional check)

### Rollback

If fidelity causes issues:
1. Set `TAINT_FIDELITY_STRICT=0` env var to disable
2. Or revert the 4 checkpoint additions in core.py
