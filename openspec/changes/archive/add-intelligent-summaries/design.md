# Design: Intelligent Summaries for AI Consumption

> **CRITICAL**: Read `VERIFICATION.md` before implementing. All JSON structures and file paths
> in this document have been verified against the live codebase. VERIFICATION.md contains
> the authoritative verified facts.

## Context

TheAuditor generates 20+ raw JSON files during `aud full`. AI agents face context window limits (32K-128K tokens) while these files can exceed 50MB. This design adds a summary layer that aggregates findings with FCE correlation metadata.

**Stakeholders**:
- AI agents consuming `.pf/` output (Claude, GPT, Gemini)
- Human developers reviewing audit results
- FCE engine (source of correlation data)

**Constraints**:
- MUST NOT modify existing `/raw/` files (ground truth preservation)
- MUST follow ZERO FALLBACK policy (crash on missing data, never silently degrade)
- MUST use database-first patterns where applicable
- MUST NOT include recommendations or severity filtering (Truth Courier principle)

## Goals / Non-Goals

**Goals**:
- Reduce AI context consumption by 80-90% for triage tasks
- Surface files with multiple independent signals (intersection map)
- Teach AI agents to query `repo_index.db` instead of parsing JSON
- Provide FCE correlation for every aggregated finding

**Non-Goals**:
- Replacing raw files (summaries are derived, not authoritative)
- AI-generated fix suggestions (out of scope)
- Real-time updates (summaries generated once per `aud full`)

## Decisions

### Decision 1: Directory Structure

```
.pf/
├── raw/                    # Ground truth (unchanged)
│   ├── patterns.json
│   ├── taint_analysis.json  # VERIFIED: NOT taint.json
│   ├── fce.json
│   ├── ...
└── summary/                # NEW: AI-optimized aggregations
    ├── SAST_Summary.json
    ├── SCA_Summary.json
    ├── Intelligence_Summary.json
    ├── Quick_Start.json
    └── Query_Guide.json
```

**Rationale**: Separate directory prevents confusion between raw (immutable) and derived (regenerated) data.

**VERIFIED Source Files for Each Summary**:

| Summary | Source Files (VERIFIED) | Key Fields |
|---------|------------------------|------------|
| `SAST_Summary.json` | `patterns.json`, `taint_analysis.json`, `github_workflows.json` | `pattern_name` OR `rule`, `file`, `line`, `severity` |
| `SCA_Summary.json` | `deps.json`, `vulnerabilities.json`, `frameworks.json` | `dependencies[]`, `vulnerabilities[]` |
| `Intelligence_Summary.json` | `graph_analysis.json`, `cfg.json`, `churn_analysis.json`, `fce_failures.json` | `hotspots[]`, `cycles[]`, meta_findings |
| `Quick_Start.json` | ALL above + `fce.json` | Intersection of 2+ signal domains |
| `Query_Guide.json` | Live `repo_index.db` schema | `PRAGMA table_info()` |

**CRITICAL CORRECTIONS from verification**:
- `taint.json` does NOT exist - use `taint_analysis.json`
- `patterns.json` uses `pattern_name` NOT `rule` (but `fce.json` normalizes to `rule`)
- `graph_analysis.json` hotspots include `external::` prefix - MUST filter these out
- `taint_analysis.json` uses `paths` NOT `taint_paths`

**Alternatives Considered**:
- Embed summaries in raw files: Rejected - violates immutability principle
- Single unified summary: Rejected - too large, defeats context optimization purpose

### Decision 2: JSON Schema Definitions

#### 2.1 SAST_Summary.json Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["meta", "findings_map", "fce_summary"],
  "properties": {
    "meta": {
      "type": "object",
      "required": ["generated_at", "source_files", "total_findings"],
      "properties": {
        "generated_at": { "type": "string", "format": "date-time" },
        "source_files": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Raw files this summary reads from"
        },
        "total_findings": { "type": "integer" }
      }
    },
    "findings_map": {
      "type": "object",
      "description": "Findings grouped by issue_type",
      "additionalProperties": {
        "type": "object",
        "required": ["count", "affected_files", "fce_hotspot_overlap"],
        "properties": {
          "count": { "type": "integer" },
          "affected_files": { "type": "integer" },
          "fce_hotspot_overlap": { "type": "boolean" },
          "sample_locations": {
            "type": "array",
            "maxItems": 3,
            "items": {
              "type": "object",
              "properties": {
                "file": { "type": "string" },
                "line": { "type": "integer" }
              }
            }
          }
        }
      }
    },
    "fce_summary": {
      "type": "object",
      "properties": {
        "total_correlated": { "type": "integer" },
        "architectural_risk_count": { "type": "integer" }
      }
    }
  }
}
```

**Example Output**:
```json
{
  "meta": {
    "generated_at": "2025-11-24T10:30:00Z",
    "source_files": ["patterns.json", "taint.json", "github_workflows.json"],
    "total_findings": 47
  },
  "findings_map": {
    "SQL_INJECTION": {
      "count": 5,
      "affected_files": 2,
      "fce_hotspot_overlap": true,
      "sample_locations": [
        {"file": "src/db/queries.py", "line": 142},
        {"file": "src/api/users.py", "line": 87}
      ]
    },
    "HARDCODED_SECRET": {
      "count": 3,
      "affected_files": 3,
      "fce_hotspot_overlap": false,
      "sample_locations": [
        {"file": "config/settings.py", "line": 23}
      ]
    }
  },
  "fce_summary": {
    "total_correlated": 8,
    "architectural_risk_count": 2
  }
}
```

#### 2.2 SCA_Summary.json Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["meta", "packages", "frameworks"],
  "properties": {
    "meta": {
      "type": "object",
      "required": ["generated_at", "source_files"],
      "properties": {
        "generated_at": { "type": "string", "format": "date-time" },
        "source_files": { "type": "array", "items": { "type": "string" } }
      }
    },
    "packages": {
      "type": "object",
      "required": ["total", "direct", "transitive", "outdated_direct", "outdated_transitive", "vulnerable"],
      "properties": {
        "total": { "type": "integer" },
        "direct": { "type": "integer" },
        "transitive": { "type": "integer" },
        "outdated_direct": { "type": "integer" },
        "outdated_transitive": { "type": "integer" },
        "vulnerable": {
          "type": "object",
          "properties": {
            "critical": { "type": "integer" },
            "high": { "type": "integer" },
            "medium": { "type": "integer" },
            "low": { "type": "integer" }
          }
        }
      }
    },
    "frameworks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "version": { "type": "string" },
          "category": { "type": "string" }
        }
      }
    }
  }
}
```

**Example Output**:
```json
{
  "meta": {
    "generated_at": "2025-11-24T10:30:00Z",
    "source_files": ["deps.json", "vulnerabilities.json", "frameworks.json"]
  },
  "packages": {
    "total": 156,
    "direct": 32,
    "transitive": 124,
    "outdated_direct": 5,
    "outdated_transitive": 42,
    "vulnerable": {
      "critical": 0,
      "high": 2,
      "medium": 5,
      "low": 8
    }
  },
  "frameworks": [
    {"name": "fastapi", "version": "0.109.0", "category": "web"},
    {"name": "sqlalchemy", "version": "2.0.25", "category": "orm"}
  ]
}
```

#### 2.3 Intelligence_Summary.json Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["meta", "graph_metrics", "cfg_metrics", "churn_metrics"],
  "properties": {
    "meta": {
      "type": "object",
      "required": ["generated_at", "source_files"],
      "properties": {
        "generated_at": { "type": "string", "format": "date-time" },
        "source_files": { "type": "array", "items": { "type": "string" } }
      }
    },
    "graph_metrics": {
      "type": "object",
      "properties": {
        "hotspot_count": { "type": "integer" },
        "cycle_count": { "type": "integer" },
        "largest_cycle_size": { "type": "integer" },
        "top_hotspots": {
          "type": "array",
          "maxItems": 5,
          "items": {
            "type": "object",
            "properties": {
              "file": { "type": "string" },
              "in_degree": { "type": "integer" },
              "out_degree": { "type": "integer" },
              "score": { "type": "number" }
            }
          }
        }
      }
    },
    "cfg_metrics": {
      "type": "object",
      "properties": {
        "total_functions_analyzed": { "type": "integer" },
        "complex_functions": { "type": "integer", "description": "Cyclomatic complexity > 20" },
        "max_complexity": { "type": "integer" },
        "avg_complexity": { "type": "number" },
        "top_complex_functions": {
          "type": "array",
          "maxItems": 5,
          "items": {
            "type": "object",
            "properties": {
              "file": { "type": "string" },
              "function": { "type": "string" },
              "complexity": { "type": "integer" }
            }
          }
        }
      }
    },
    "churn_metrics": {
      "type": "object",
      "properties": {
        "files_analyzed": { "type": "integer" },
        "high_churn_files": { "type": "integer", "description": "Files in 90th percentile of commits" },
        "percentile_90_threshold": { "type": "integer" },
        "top_churned_files": {
          "type": "array",
          "maxItems": 5,
          "items": {
            "type": "object",
            "properties": {
              "file": { "type": "string" },
              "commits_90d": { "type": "integer" },
              "unique_authors": { "type": "integer" }
            }
          }
        }
      }
    }
  }
}
```

#### 2.4 Quick_Start.json Schema (The Intersection Map)

This is the most critical file - it ONLY contains entries where MULTIPLE independent signals converge.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["meta", "intersections"],
  "properties": {
    "meta": {
      "type": "object",
      "required": ["generated_at", "scan_id", "total_intersections"],
      "properties": {
        "generated_at": { "type": "string", "format": "date-time" },
        "scan_id": { "type": "string" },
        "total_intersections": { "type": "integer" },
        "intersection_threshold": {
          "type": "integer",
          "default": 2,
          "description": "Minimum signals required to appear in this file"
        }
      }
    },
    "intersections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["file_path", "fce_context", "active_signals", "locator_map"],
        "properties": {
          "file_path": { "type": "string" },
          "fce_context": {
            "type": "object",
            "description": "Factual context from FCE meta-findings",
            "properties": {
              "churn_velocity": {
                "type": "string",
                "enum": ["HIGH", "MODERATE", "LOW", "STAGNANT"]
              },
              "architectural_role": {
                "type": "string",
                "description": "From graph hotspot analysis"
              },
              "recent_commit_count": { "type": "integer" },
              "unique_contributors": { "type": "integer" },
              "in_cycle": { "type": "boolean" },
              "is_hotspot": { "type": "boolean" }
            }
          },
          "active_signals": {
            "type": "object",
            "description": "Raw findings grouped by domain",
            "properties": {
              "sast_patterns": {
                "type": "array",
                "items": { "type": "string" },
                "description": "Pattern rule IDs that matched"
              },
              "taint_paths": {
                "type": "integer",
                "description": "Count of taint paths involving this file"
              },
              "complexity_outliers": {
                "type": "array",
                "items": { "type": "string" },
                "description": "Function names with complexity > 20"
              },
              "sca_vulnerabilities": {
                "type": "array",
                "items": { "type": "string" },
                "description": "Vulnerability IDs affecting imports in this file"
              }
            }
          },
          "locator_map": {
            "type": "array",
            "description": "Exact line locations for each signal",
            "items": {
              "type": "object",
              "required": ["line", "signal_source", "signal_id"],
              "properties": {
                "line": { "type": "integer" },
                "signal_source": {
                  "type": "string",
                  "enum": ["sast_patterns", "taint_paths", "complexity_outliers", "sca_vulnerabilities"]
                },
                "signal_id": { "type": "string" },
                "value_raw": {
                  "type": ["number", "string"],
                  "description": "Original value (e.g., complexity score)"
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**Example Output**:
```json
{
  "meta": {
    "generated_at": "2025-11-24T10:30:00Z",
    "scan_id": "aud_run_8821x",
    "total_intersections": 3,
    "intersection_threshold": 2
  },
  "intersections": [
    {
      "file_path": "src/controllers/AuthController.ts",
      "fce_context": {
        "churn_velocity": "HIGH",
        "architectural_role": "CORE_API_GATEWAY",
        "recent_commit_count": 14,
        "unique_contributors": 5,
        "in_cycle": false,
        "is_hotspot": true
      },
      "active_signals": {
        "sast_patterns": ["SQL_INJECTION", "HARDCODED_SECRET"],
        "taint_paths": 3,
        "complexity_outliers": ["handleLogin"]
      },
      "locator_map": [
        {"line": 42, "signal_source": "sast_patterns", "signal_id": "SQL_INJECTION"},
        {"line": 87, "signal_source": "taint_paths", "signal_id": "request.body -> db.query"},
        {"line": 105, "signal_source": "complexity_outliers", "signal_id": "handleLogin", "value_raw": 25}
      ]
    }
  ]
}
```

**CRITICAL**: A file appears in `intersections` ONLY if it has 2+ signals from DIFFERENT domains (e.g., SAST + High Churn). Multiple SAST findings in the same file count as 1 signal.

#### 2.5 Query_Guide.json Schema

This is a reference document that teaches AI agents how to query the database.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["meta", "agent_directives", "tool_reference", "schema_map", "investigation_workflows"],
  "properties": {
    "meta": {
      "type": "object",
      "properties": {
        "purpose": { "type": "string", "const": "Agent Instruction Manual" },
        "description": { "type": "string" },
        "access_level": { "type": "string", "const": "READ_ONLY" }
      }
    },
    "agent_directives": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Instructions for AI agents"
    },
    "tool_reference": {
      "type": "object",
      "description": "CLI command templates",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "command_template": { "type": "string" },
          "example": { "type": "string" },
          "output_format": { "type": "string" },
          "use_case": { "type": "string" }
        }
      }
    },
    "schema_map": {
      "type": "object",
      "description": "Database schema for aud query",
      "properties": {
        "tables": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "properties": {
              "columns": { "type": "array", "items": { "type": "string" } },
              "join_key": { "type": "string" },
              "description": { "type": "string" }
            }
          }
        }
      }
    },
    "investigation_workflows": {
      "type": "object",
      "description": "Step-by-step investigation patterns",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "trigger": { "type": "string" },
          "steps": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  }
}
```

### Decision 3: Implementation Architecture

**New Module**: `theauditor/summary/`

```
theauditor/summary/
├── __init__.py           # Exports generate_all_summaries()
├── generators.py         # Individual summary generators
├── schemas.py            # Pydantic models for validation
└── query_guide.py        # Query_Guide.json generator (reads live schema)
```

**Key Implementation Patterns**:

1. **ZERO FALLBACK**: Every generator MUST raise `FileNotFoundError` if source file missing
```python
# CORRECT - Hard fail
def load_raw_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required raw file missing: {path}")
    with open(path) as f:
        return json.load(f)

# FORBIDDEN - Silent degradation
def load_raw_file(path: Path) -> dict:
    if not path.exists():
        return {}  # CANCER - violates ZERO FALLBACK
```

2. **FCE Correlation**: Look up files in FCE meta-findings
```python
def get_fce_context(file_path: str, fce_data: dict) -> dict:
    """Extract FCE context for a file."""
    context = {
        "churn_velocity": "STAGNANT",
        "is_hotspot": False,
        "in_cycle": False
    }

    # Check if file is in architectural hotspots
    for meta in fce_data.get("correlations", {}).get("meta_findings", []):
        if meta.get("file") == file_path:
            if meta["type"] == "ARCHITECTURAL_RISK_ESCALATION":
                context["is_hotspot"] = True
                context["architectural_role"] = "CORE_COMPONENT"
            elif meta["type"] == "HIGH_CHURN_RISK_CORRELATION":
                context["churn_velocity"] = "HIGH"
                context["recent_commit_count"] = meta.get("commits_90d", 0)
            elif meta["type"] == "SYSTEMIC_DEBT_CLUSTER":
                context["in_cycle"] = True

    return context
```

3. **Intersection Logic**: Only emit files with 2+ signal domains
```python
def calculate_signal_domains(file_path: str, all_findings: dict) -> set:
    """Count distinct signal domains for a file."""
    domains = set()

    # Domain 1: SAST patterns
    if any(f["file"] == file_path for f in all_findings.get("patterns", [])):
        domains.add("sast")

    # Domain 2: Taint paths
    if any(path["sink"]["file"] == file_path for path in all_findings.get("taint_paths", [])):
        domains.add("taint")

    # Domain 3: Complexity
    if any(f["file"] == file_path for f in all_findings.get("complex_functions", [])):
        domains.add("complexity")

    # Domain 4: High churn
    if any(f["file"] == file_path for f in all_findings.get("high_churn", [])):
        domains.add("churn")

    return domains

def should_include_in_quick_start(file_path: str, all_findings: dict) -> bool:
    """File must have 2+ distinct signal domains."""
    domains = calculate_signal_domains(file_path, all_findings)
    return len(domains) >= 2
```

### Decision 4: Pipeline Integration

**Location**: Stage 4, after FCE, before report

```python
# In pipelines.py command_order
command_order = [
    # ... Stage 1-3 ...
    ("fce", []),
    ("summary", ["generate"]),  # NEW: Generate all summaries
    ("report", []),
]
```

**Rationale**: Summary generation requires FCE output for correlation data.

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Raw files missing | Summary generation crashes | ZERO FALLBACK is correct - exposes pipeline bugs |
| Large codebases slow | +500ms per summary | Acceptable - runs once at end |
| Schema drift | Query_Guide.json becomes stale | Generate dynamically from live DB |
| FCE changes format | Summary generators break | Pin to FCE output contract |

## Migration Plan

1. **Phase 1**: Add `theauditor/summary/` module
2. **Phase 2**: Add `aud summary generate` command
3. **Phase 3**: Integrate into `aud full` pipeline
4. **Phase 4**: Update documentation

**Rollback**: Remove summary phase from pipeline; `.pf/summary/` is optional.

## Open Questions

1. **Q**: Should `Query_Guide.json` include example SQL queries for common investigations?
   **A**: Yes - include 5-10 common queries (find callers, find taint sources, etc.)

2. **Q**: Should summaries be regenerated if raw files change without re-running `aud full`?
   **A**: No - summaries are tied to a specific pipeline run. Stale detection out of scope.

3. **Q**: Maximum number of intersections in `Quick_Start.json`?
   **A**: No limit. If 100 files have intersections, show all 100. AI can filter.
