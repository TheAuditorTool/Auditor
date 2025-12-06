# TheAuditor Blueprint Command

## Overview

**BLUEPRINT** is TheAuditor's architectural visualization command that displays facts about codebase structure, dependencies, security surface, and data flows. Operating in "truth courier mode," it presents pure architectural facts with zero prescriptive language.

### Key Philosophy
- **100% Accurate, 0% Inference**: Facts only - no guesses
- **No AI Prescriptions**: Shows what exists, not what "should be"
- **Multiple Views**: 8 distinct drill-down analysis modes
- **Dual Output**: Terminal (ASCII tree) or JSON

---

## Quick Start

```bash
aud full                    # Build database first
aud blueprint               # Top-level overview
aud blueprint --structure   # Codebase organization
aud blueprint --security    # Attack surface mapping
```

---

## Available Views (8 Modes)

### 1. Default (No Flags)
Quick architectural snapshot: structure + security + metrics

### 2. `--structure`
- Directory organization, file counts
- Language distribution
- Symbol type breakdown
- Naming convention analysis (snake_case, camelCase consistency)
- Architectural precedents (plugin loader patterns)
- Framework detection
- Token estimates for LLM context

### 3. `--graph`
- Import graph summary
- Gateway files (bottlenecks - high betweenness)
- Circular dependencies
- External dependencies

### 4. `--security`
- API endpoint coverage (protected vs unprotected)
- Authentication patterns (JWT, OAuth, passwords)
- SQL injection risk (raw vs parameterized)
- Hardcoded secrets detection

### 5. `--taint`
- Taint paths detected
- Top taint sources (user-controlled data)
- Vulnerable data flows
- Sanitization coverage

### 6. `--boundaries`
- Entry points analyzed
- Boundary quality (clear/acceptable/fuzzy/missing)
- Validation distance metrics
- Risk summary

### 7. `--deps`
- Total dependencies by package manager
- Projects/workspaces detected
- Outdated package detection

### 8. `--fce`
- Vector convergence points
- Signal density distribution
- High priority files (3+ vectors)

### 9. `--monoliths`
- Files exceeding line threshold (default: 2150)
- Helps plan AI context window management

### 10. `--all`
Complete JSON export for programmatic consumption

---

## CLI Examples

```bash
# Security audit drill-down
aud blueprint --security

# Find bottleneck files
aud blueprint --graph

# Export everything as JSON
aud blueprint --all > architecture.json

# Find large files blocking AI analysis
aud blueprint --monoliths --threshold 3000

# Dependencies with JSON output
aud blueprint --deps --format json
```

---

## Data Sources

### Primary: `.pf/repo_index.db`
- `symbols` - Functions, classes, variables
- `api_endpoints` - Route definitions
- `api_endpoint_controls` - Auth middleware
- `sql_queries` - SQL statements
- `jwt_patterns`, `oauth_patterns` - Auth surface
- `findings_consolidated` - All findings

### Secondary: `.pf/graphs.db`
- `edges` - Dependency/call graph

---

## Sample Output

```
TheAuditor Code Blueprint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURAL ANALYSIS (100% Accurate, 0% Inference)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[STRUCTURE] Codebase Structure:
  ├─ Backend: 150 files
  ├─ Frontend: 200 files
  └─ Total: 350 files, 4,200 symbols

[HOT] Hot Files (by call count):
  1. src/auth/jwt_handler.py
     → Called by: 24 files (87 call sites)

[SECURITY] Security Surface:
  ├─ API Endpoints: 42 total (4 unprotected)
  ├─ SQL Queries: 156 total (23 raw)
  └─ JWT: 12 sign, 18 verify

[DATAFLOW] Taint Paths: 67 detected
```

---

## How It Helps

| View | Question Answered |
|------|-------------------|
| `--structure` | "How big is this codebase?" |
| `--graph` | "What breaks if I change X?" |
| `--security` | "What's vulnerable?" |
| `--taint` | "Where does user data flow?" |
| `--boundaries` | "How far is validation from entry?" |
| `--deps` | "What packages? Outdated?" |
| `--fce` | "Where do signals converge?" |
| `--monoliths` | "Which files are too large for AI?" |
