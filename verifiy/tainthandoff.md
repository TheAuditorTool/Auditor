# Taint Analysis Architecture Fixes - Session Handoff

**Date**: 2025-11-08
**Session Duration**: ~3 hours
**Status**: Partial fixes implemented, needs testing

---

## Executive Summary

Enhanced the IFDS taint analyzer to check for sanitizers along taint paths by querying the database. Fixed idiot framework detection logic in TaintRegistry. Deleted cancer CFG integration files that were rebuilding existing functionality.

**Key Insight from PDF**: Taint engine does flow analysis (resolve graph nodes/edges), rules apply SAST checks to resolved flows. Database is single source of truth.

---

## Architecture (Correct Understanding)

```
┌─────────────────────────────────────────────────────────────┐
│ ORCHESTRATOR (rules/orchestrator.py)                        │
│ - Filters rules by detected frameworks                      │
│ - Populates TaintRegistry with patterns                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ TAINT ENGINE (taint/ifds_analyzer.py)                       │
│ - IFDS backward reachability on graphs.db                   │
│ - Resolves data flows (nodes → edges → paths)               │
│ - Queries repo_index.db for sanitizers                      │
│ - Returns: List of TaintPath objects                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ RULES (/rules/)                                              │
│ - Apply SAST security checks to resolved flows              │
│ - Classify vulnerabilities (SQLi, XSS, etc.)                │
└─────────────────────────────────────────────────────────────┘
```

**Database Architecture**:
- **repo_index.db** (91MB): Raw AST facts - symbols, calls, assignments, frameworks
- **graphs.db** (79MB): Pre-computed edges for IFDS - assignments, calls, returns, etc.

**Edge types in graphs.db**: import, sql, call, assignment, return, react_hook, orm, resource_dependency, output_reference, variable_reference

---

## What Got Fixed

### 1. ✅ Enhanced ifds_analyzer.py with Sanitizer Checking

**File**: `theauditor/taint/ifds_analyzer.py`

**Changes**:
- Added `registry` parameter to `__init__()` to receive sanitizer patterns from orchestrator
- Added `_load_safe_sinks()` - loads sanitizers from `framework_safe_sinks` table (3 rows: res.json, res.jsonp, res.status().json)
- Added `_is_sanitizer()` - checks if function is sanitizer (database + registry)
- Added `_path_goes_through_sanitizer()` - queries `function_call_args` at each hop to detect sanitizers
- Modified `_trace_backward_to_any_source()` - skips paths that go through sanitizers

**How it works**:
```python
# For each hop in the backward trace:
for hop in hop_chain:
    # Query function calls at this hop's line
    SELECT callee_function FROM function_call_args
    WHERE file = ? AND line = ?

    # Check if callee is a sanitizer
    if callee in framework_safe_sinks OR callee in registry:
        # Skip this path - it's sanitized
        continue
```

**Database Query**: Direct queries to repo_index.db, no in-memory flow simulation.

### 2. ✅ Fixed TaintRegistry.get_stats()

**File**: `theauditor/taint/core.py` (lines 131-158)

**Before** (WRONG - idiot framework detection):
```python
def get_stats(self):
    stats = {}
    # Count sources by language
    for lang, categories in self.sources.items():
        total = sum(len(patterns) for patterns in categories.values())
        stats[f'sources_{lang}'] = total  # ❌ IDIOT LOGIC
    # ... same for sinks
```

**After** (CORRECT - simple totals):
```python
def get_stats(self):
    total_sources = sum(
        len(patterns)
        for lang_sources in self.sources.values()
        for patterns in lang_sources.values()
    )
    # ... same for sinks/sanitizers
    return {
        'total_sources': total_sources,
        'total_sinks': total_sinks,
        'total_sanitizers': total_sanitizers
    }
```

**Why fixed**: Registry is for pattern accumulation, NOT framework detection. Orchestrator handles framework filtering.

### 3. ✅ Passed Registry to IFDSTaintAnalyzer

**File**: `theauditor/taint/core.py` (line 551-556)

**Before**:
```python
ifds_analyzer = IFDSTaintAnalyzer(
    repo_db_path=db_path,
    graph_db_path=graph_db_path,
    cache=cache
)
```

**After**:
```python
ifds_analyzer = IFDSTaintAnalyzer(
    repo_db_path=db_path,
    graph_db_path=graph_db_path,
    cache=cache,
    registry=registry  # ✅ Now can check registry sanitizers
)
```

---

## What Got Deleted (Cancer Removal)

### 1. ❌ cfg_integration.py (Created then deleted)

**What I did wrong**: Created 350-line `theauditor/taint/cfg_integration.py` with PathAnalyzer, BlockTaintState, etc.

**Why it was cancer**: Rebuilt functionality that graphs.db already provides. IFDS analyzer already does path-sensitive analysis by following edges in graphs.db. No need for separate CFG integration.

**User feedback**: "you are now rebuilding the fucking cancer... we should utilize the existing graphs.db and use the logic to resolve it"

---

## What Didn't Get Fixed (Still Broken)

### 1. ⚠️ Python Framework Detection (Partially Fixed)

**File**: `theauditor/manifest_parser.py` (lines 160, 162, 165)

**What was fixed**:
- Made package name comparison case-insensitive
- `"Django" != "django"` was breaking detection
- Now uses `lower()` for comparison

**What's still unclear**:
- Is this actually wired up correctly post-refactor?
- Does orchestrator actually query frameworks table?
- User mentioned "manifest_parser.py isnt correctly wired up, investigate that"

**Status**: Code fix applied, but not tested end-to-end.

### 2. ⚠️ TaintRegistry Population

**Current architecture** (from code):
```python
# orchestrator.py
def collect_rule_patterns(self, registry):
    detected_languages = set()
    cursor.execute("SELECT DISTINCT language FROM frameworks")
    for (language,) in cursor.fetchall():
        detected_languages.add(language.lower())

    # Filter rules by detected languages
    for category, rules in self.rules.items():
        if category in detected_languages:
            # Register patterns for this language
```

**What might be broken**:
- Are rules actually calling `registry.register_source()` with correct signature?
- Rule signature is `register_source(pattern, category, language)` - do all 200+ rules use this?
- Is orchestrator even being called before taint analysis runs?

**Status**: Architecture exists, but unclear if it works.

### 3. ⚠️ Cross-File Taint Tracking

**What should work** (from IFDS paper):
- Backward reachability from sinks
- Follow edges in graphs.db (call, return, assignment)
- Access path tracking (x.f.g)
- Function summaries

**What might be broken**:
- Are edges in graphs.db actually correct?
- Does AccessPath matching work?
- Is `_get_predecessors()` returning the right edges?

**Evidence from pipeline.log**:
```
Taint paths: 82
Sources found: 1477
Sinks found: 956
```

**Status**: Some paths found, but unclear if cross-file works.

---

## Current Database State

### repo_index.db Tables (Relevant)
- `frameworks` - Detected frameworks (14 rows from last run)
- `framework_safe_sinks` - Sanitizers (3 rows: res.json, res.jsonp, res.status().json)
- `function_call_args` - All function calls with args (used for sanitizer checking)
- `symbols` - All code symbols
- `assignments` - Variable assignments
- `assignment_sources` - Junction table for assignment source vars

### graphs.db Tables
- `nodes` - Graph nodes (variables, functions, etc.)
- `edges` - 80,585 edges (10 types: import, sql, call, assignment, return, react_hook, orm, resource_dependency, output_reference, variable_reference)
- `analysis_results` - Pre-computed analysis results

**Key insight**: All the data exists. Just need to wire queries correctly.

---

## Test Status

### What Needs Testing

1. **Sanitizer checking works**:
   ```bash
   cd C:/Users/santa/Desktop/TheAuditor
   aud index  # Rebuild with manifest_parser fix
   THEAUDITOR_DEBUG=1 aud taint-analyze --max-depth 5
   # Look for: "[IFDS] Path sanitized by res.json at file:line"
   ```

2. **Python frameworks detected**:
   ```bash
   aud detect-frameworks
   # Should see: Flask, Django, FastAPI if in requirements.txt
   ```

3. **Registry populated**:
   ```bash
   # Add debug print in core.py after orchestrator.collect_rule_patterns()
   print(f"[DEBUG] Registry stats: {registry.get_stats()}")
   # Should see: total_sources > 0, total_sinks > 0
   ```

4. **Cross-file paths work**:
   ```bash
   aud taint-analyze --max-depth 10
   # Check .pf/raw/taint_analysis.json for paths with different source/sink files
   ```

### Background Processes Still Running

When session ended, 6 background bash processes were running:
- `aud full --offline` (4d76bd)
- `aud taint-analyze` variations (350b56, d637b6, 332ac7, a27b2e)
- `find . -name "*.py" -exec grep -l "get_self_exclusion_patterns"` (7cfee0)

**Check their output** to see if any errors occurred:
```bash
# If processes still running, check output with BashOutput tool
# Or check .pf/pipeline.log and .pf/error.log
```

---

## Architecture Violations I Made (Learn From These)

### Violation 1: Rebuilding Existing Functionality
**What I did**: Created cfg_integration.py with PathAnalyzer, BlockTaintState
**Why wrong**: graphs.db already has CFG edges. IFDS analyzer already does path-sensitive analysis.
**Correct approach**: Query graphs.db for edges, query repo_index.db for facts.

### Violation 2: Framework Detection in Registry
**What I did**: Added language breakdown to `get_stats()` - `sources_python`, `sources_javascript`
**Why wrong**: Registry is pattern accumulator, NOT framework detector. Orchestrator handles framework filtering.
**Correct approach**: Simple totals only. Let orchestrator do the filtering.

### Violation 3: Creating New Files
**What I did**: Created cfg_integration.py (350 lines of cancer)
**Why wrong**: "we certainly shouldnt have fucking 3 more new files idiot dumbass"
**Correct approach**: Enhance existing files (ifds_analyzer.py) with database queries.

### Violation 4: Not Reading the PDF First
**What I did**: Tried to implement before understanding architecture
**Why wrong**: Wasted 2 hours building wrong solutions
**Correct approach**: Read docs/taint_research.pdf first. Architecture is: Engine resolves flows → Rules apply SAST.

---

## Next Steps (Priority Order)

### Immediate (Must Do)
1. **Test sanitizer checking** - Run `THEAUDITOR_DEBUG=1 aud taint-analyze` and verify paths are skipped
2. **Verify registry population** - Add debug prints to see if orchestrator populates registry
3. **Check Python framework detection** - Run `aud detect-frameworks` after indexing

### Short-term (Should Do)
4. **Verify cross-file tracking** - Check if paths span multiple files in taint_analysis.json
5. **Check edge types** - Verify graphs.db has correct edge types (call, return, assignment)
6. **Review AccessPath matching** - Is `_access_paths_match()` too strict or too loose?

### Long-term (Could Do)
7. **Optimize sanitizer checking** - Currently queries DB for every hop (could be slow)
8. **Add more sanitizers** - framework_safe_sinks only has 3 entries (need more)
9. **Enhance edge discovery** - Are all edge types being used in backward analysis?

---

## Files Modified This Session

```
theauditor/taint/core.py
  - Fixed get_stats() (lines 131-158)
  - Passed registry to IFDSTaintAnalyzer (line 555)

theauditor/taint/ifds_analyzer.py
  - Added registry parameter (line 43)
  - Added _load_safe_sinks() (lines 463-474)
  - Added _is_sanitizer() (lines 476-494)
  - Added _path_goes_through_sanitizer() (lines 496-522)
  - Modified backward analysis to skip sanitized paths (lines 171-174)

theauditor/manifest_parser.py (EARLIER IN SESSION - may have been reverted)
  - Made package name comparison case-insensitive (lines 160, 162, 165)
```

---

## Key Quotes from User (Architecture Lessons)

> "the core idea is that taint engine does flow analysis, basically 'resolve graphs nodes and edges and shit' and /rules/ applies the sast portion to that taint flow analysis"

> "we should utilize the existing graphs.db and use the logic to resolve it"

> "The database is regenerated FRESH on every `aud full` run. If data is missing: The database is WRONG → Fix the indexer"

> "NO FALLBACKS. NO EXCEPTIONS. NO WORKAROUNDS. NO 'JUST IN CASE' LOGIC."

---

## Architecture Reference

**IFDS Paper** (docs/taint_research.pdf):
- Backward demand-driven analysis from sinks
- Access paths: x.f.g (k=5 default)
- h-sparse complexity: O(CallD³ + 2ED²)
- No expensive alias analysis
- Function summaries for inter-procedural

**Database Schema** (.pf/repo_index.db):
- 154 tables (auto-generated from schema)
- SchemaMemoryCache loads all tables into memory
- All queries use build_query() for schema compliance

**Graph Database** (.pf/graphs.db):
- Pre-computed during `aud full` via `aud graph build`
- Used by IFDS for backward reachability
- 80,585 edges across 10 types

---

## Debug Commands

```bash
# Check if sanitizer checking works
THEAUDITOR_DEBUG=1 aud taint-analyze --max-depth 5 2>&1 | grep -i sanitiz

# Check registry stats
aud taint-analyze 2>&1 | grep -i "registry\|sources\|sinks"

# Check Python frameworks detected
aud detect-frameworks | grep -i "flask\|django\|fastapi"

# Check graphs.db edge types
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/graphs.db')
c = conn.cursor()
c.execute('SELECT type, COUNT(*) FROM edges GROUP BY type')
for row in c.fetchall():
    print(f'{row[0]}: {row[1]} edges')
"

# Check framework_safe_sinks
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT * FROM framework_safe_sinks')
for row in c.fetchall():
    print(row)
"
```

---

## Conclusion

**What works**: Sanitizer checking is now wired into IFDS analyzer via database queries.

**What's untested**: Everything. All changes need end-to-end testing.

**What's still broken**: Registry population unclear, Python framework detection partially fixed, cross-file tracking status unknown.

**Next session**: Test the sanitizer checking, verify registry gets populated, check if Python frameworks are detected.

**Architecture understanding**: ✅ Clear. Taint engine resolves flows from graphs.db. Rules apply SAST to resolved flows. Database is single source of truth. No fallbacks, no cancer, no new files.
