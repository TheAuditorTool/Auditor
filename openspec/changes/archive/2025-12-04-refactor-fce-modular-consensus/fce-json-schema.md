# FCE JSON Output Schema

This document describes the JSON output format for the FCE (Factual Correlation Engine) command.

## Command

```bash
aud fce --format json
```

## Root Object

```json
{
  "metadata": { ... },
  "summary": { ... },
  "convergence_points": [ ... ]
}
```

### metadata

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string | ISO 8601 timestamp of report generation |
| `min_vectors_filter` | integer | Minimum vectors filter applied (1-4) |
| `root_path` | string | Absolute path to analyzed project root |

### summary

| Field | Type | Description |
|-------|------|-------------|
| `total_files` | integer | Total files with any vector data |
| `static_files` | integer | Files with STATIC vector findings |
| `flow_files` | integer | Files with FLOW vector findings |
| `process_files` | integer | Files with PROCESS vector data |
| `structural_files` | integer | Files with STRUCTURAL vector data |

### convergence_points

Array of objects, each representing a file with vector convergence:

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | string | Relative path to file |
| `line_start` | integer | Start line of convergence region |
| `line_end` | integer | End line of convergence region |
| `signal` | object | Vector signal data (see below) |
| `facts` | array | Array of Fact objects (see below) |

#### signal

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | string | File path (redundant, for convenience) |
| `vectors_present` | array[string] | Vectors present: "static", "flow", "process", "structural" |
| `density` | float | Density value (0.0 - 1.0) = len(vectors_present) / 4 |
| `density_label` | string | Human-readable label: "N/4 vectors" |

#### facts

Each fact object:

| Field | Type | Description |
|-------|------|-------------|
| `vector` | string | One of: "static", "flow", "process", "structural" |
| `source` | string | Tool/analyzer that produced this fact |
| `message` | string | Fact description/message |
| `file` | string | File path where fact was found |
| `line` | integer | Line number (0 if not applicable) |
| `metadata` | object | Optional additional data |

## Example Output

```json
{
  "metadata": {
    "generated_at": "2025-12-04T15:30:00.000000+00:00",
    "min_vectors_filter": 2,
    "root_path": "C:/Users/santa/Desktop/TheAuditor"
  },
  "summary": {
    "total_files": 605,
    "static_files": 42,
    "flow_files": 15,
    "process_files": 200,
    "structural_files": 3
  },
  "convergence_points": [
    {
      "file_path": "theauditor/cli.py",
      "line_start": 1,
      "line_end": 270,
      "signal": {
        "file_path": "theauditor/cli.py",
        "vectors_present": ["static", "process", "structural"],
        "density": 0.75,
        "density_label": "3/4 vectors"
      },
      "facts": [
        {
          "vector": "static",
          "source": "ruff",
          "message": "Line too long (105 > 100 characters)",
          "file": "theauditor/cli.py",
          "line": 42,
          "metadata": {}
        },
        {
          "vector": "process",
          "source": "churn-analysis",
          "message": "High change frequency: 15 commits in 30 days",
          "file": "theauditor/cli.py",
          "line": 0,
          "metadata": {}
        }
      ]
    }
  ]
}
```

## Vector Codes

The `--format text` output uses compact vector codes:

| Code | Vector | Description |
|------|--------|-------------|
| S | STATIC | Linters (ruff, eslint, bandit) |
| F | FLOW | Taint analysis |
| P | PROCESS | Code churn, change frequency |
| T | STRUCTURAL | Complexity (CFG analysis) |

Example: `S-PT` means STATIC, PROCESS, and STRUCTURAL vectors are present (no FLOW).

## Filtering

Use `--min-vectors` to filter results:

```bash
aud fce --min-vectors 3 --format json  # Only 3+ vector convergence
aud fce --min-vectors 1 --format json  # All files with any findings
```

## Writing Reports

Use `--write` to save JSON to `.pf/raw/fce.json`:

```bash
aud fce --write  # Saves to .pf/raw/fce.json
```
