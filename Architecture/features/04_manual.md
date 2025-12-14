# TheAuditor Manual System

## Overview

The **MANUAL system** is TheAuditor's built-in interactive documentation engine - a comprehensive reference system explaining security concepts, analysis methodologies, and tool-specific terminology. Designed for both users and AI agents.

### Key Characteristics

- **Offline-first**: All documentation embedded in CLI binary
- **AI-friendly**: Structured markdown with consistent formatting
- **Instant**: <1ms response time (pure string formatting)
- **Comprehensive**: 30+ core topics
- **Rich terminal formatting**: Color-coded, syntax-highlighted output

---

## Architecture

```
User Input (aud manual <topic>)
         │
         ▼
  manual.py (Command Handler)
         │
         ▼
  EXPLANATIONS dict (manual_lib01.py + manual_lib02.py)
         │
         ▼
  Rich Formatting Engine
         │
         ▼
  Terminal Output
```

---

## Manual Entry Structure

```python
"concept_name": {
    "title": "Display Title",
    "summary": "One-line summary",
    "explanation": """
    WHAT IT IS:
    Taint analysis finds where user input reaches dangerous functions...

    WHEN TO USE IT:
    - Security audit before deployment
    - PR review for security-sensitive code

    HOW TO USE IT:
    PREREQUISITES:
        aud full

    EXAMPLE - Finding SQL Injection:
        aud full && aud taint --severity high
    """
}
```

---

## Available Topics (30+)

### Security Concepts
| Topic | Summary |
|-------|---------|
| `taint` | Track untrusted data flow from sources to sinks |
| `patterns` | 25 rule categories with 200+ detection functions |
| `boundaries` | Measure distance from entry points to controls |

### Analysis Architecture
| Topic | Summary |
|-------|---------|
| `pipeline` | 24-phase execution pipeline |
| `cfg` | Control flow graphs for complexity |
| `graph` | Import and call graphs |
| `fce` | Multi-vector correlation engine |

### Features
| Topic | Summary |
|-------|---------|
| `workset` | Focused file subsets for faster analysis |
| `impact` | Blast radius analysis for changes |
| `deadcode` | Sophisticated dead code detection |
| `session` | AI agent session analysis |

---

## CLI Commands

```bash
# List all available topics
aud manual --list

# View detailed topic
aud manual taint
aud manual fce
aud manual boundaries

# Interactive guide (no arguments)
aud manual
```

---

## Rich Formatting Features

### Section Types (Auto-Detected)

1. **Headers**: Lines ending with `:` in UPPERCASE
2. **Code Blocks**: Lines starting with `aud `, `python `, `$`
3. **Bullet Points**: Lines starting with `- `
4. **Numbered Lists**: Lines with `1. `, `2. `

### Color Scheme

- **Cyan**: Section headers, paths
- **Green**: Command examples
- **Yellow**: Summary, warnings
- **Dim**: Comments, secondary info

---

## How AI Agents Use It

1. **Context Building**: Query topics to understand concepts
2. **Learning From Examples**: Each topic includes practical examples
3. **Related Navigation**: Explanations cross-reference other topics

### Agent Workflow
```
Agent needs to run taint analysis
    ↓
Query: aud manual taint
    ↓
Learns: "Requires aud full first"
    ↓
Learns: "Use --severity flag to filter"
    ↓
Runs: aud full && aud taint --severity high
```

---

## Sample Entry: TAINT

```
TITLE: Taint Analysis
SUMMARY: Tracks untrusted data flow from sources to sinks

WHAT IT IS:
Taint analysis finds where user input reaches dangerous functions
without sanitization - the root cause of injection vulnerabilities.

WHEN TO USE IT:
- Security audit before deployment
- Investigating a reported vulnerability
- PR review for security-sensitive code

HOW TO USE IT:
PREREQUISITES:
    aud full

STEPS:
1. Run taint analysis:
    aud taint --severity critical

EXAMPLE - Finding SQL Injection:
    aud full && aud taint --severity high

RELATED:
Commands: aud taint, aud fce, aud boundaries
Topics: aud manual fce, aud manual patterns
```
