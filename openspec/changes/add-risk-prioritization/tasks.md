# Implementation Tasks - add-risk-prioritization (CORRECTED)

## CRITICAL CORRECTION

**PREVIOUS IMPLEMENTATION (WRONG)**:
- Created consolidated_output.py to merge /raw/ files
- Modified 18 analyzer files to write to consolidated groups
- This BROKE THE ENTIRE PIPELINE
- All changes have been REVERTED

**CORRECT IMPLEMENTATION**:
- Keep ALL /raw/ files unchanged
- Create summaries in /readthis/ that READ FROM /raw/
- Deprecate extraction.py chunking system
- NO changes to analyzer commands

---

## 0. Verification (COMPLETE ✅)
- [x] Read proposal and understand requirements
- [x] Verify database-first commands exist (query, context, planning)
- [x] Verify current /raw/ structure (20+ separate files)
- [x] Verify extraction system creates chunks in /readthis/
- [x] Document hypotheses and evidence in verification.md
- [x] **CRITICAL**: Identify that consolidating /raw/ was WRONG architecture
- [x] Rewrite verification.md with correct architecture
- [x] Rewrite proposal.md with correct approach
- [x] Rewrite tasks.md (this file)

## 1. Create Summarize Command

### 1.1 Create Command File
- [ ] Create `theauditor/commands/summarize.py`
- [ ] Add click command decorator `@click.command("summarize")`
- [ ] Add options: `--project-path` (default ".")
- [ ] Register command in `theauditor/cli.py`

### 1.2 Implement SAST_Summary Generator
- [ ] Create function `generate_sast_summary(raw_dir: Path) -> dict`
- [ ] Read from:
  - patterns.json
  - taint.json
  - docker_findings.json (if exists)
  - github_workflows.json (if exists)
- [ ] Extract:
  - Total findings count across all security analyzers
  - File locations (no duplicates)
  - FCE correlations (read from fce.json, filter for security-related)
- [ ] Output truth courier format:
  ```json
  {
    "summary": "X patterns detected, Y taint paths found, Z FCE security correlations",
    "counts": {
      "total_findings": X,
      "patterns": Y,
      "taint_paths": Z,
      "fce_security_correlations": W
    },
    "files_with_findings": ["file1.py", "file2.js", ...],
    "fce_correlated_files": ["file3.py:42", ...],
    "query_alternative": "aud query --tool patterns --severity critical"
  }
  ```
- [ ] Write to `.pf/readthis/SAST_Summary.json`

### 1.3 Implement SCA_Summary Generator
- [ ] Create function `generate_sca_summary(raw_dir: Path) -> dict`
- [ ] Read from:
  - deps.json (if exists)
  - frameworks.json
- [ ] Extract:
  - Total packages count
  - Frameworks detected count
  - Outdated packages count (if deps.json has CVE data)
- [ ] Output truth courier format:
  ```json
  {
    "summary": "X packages analyzed, Y frameworks detected",
    "counts": {
      "total_packages": X,
      "frameworks_detected": Y,
      "outdated_packages": Z
    },
    "frameworks": ["Flask 2.3.0", "React 18.2.0", ...],
    "query_alternative": "aud query --symbol-type import --group-by package"
  }
  ```
- [ ] Write to `.pf/readthis/SCA_Summary.json`

### 1.4 Implement Intelligence_Summary Generator
- [ ] Create function `generate_intelligence_summary(raw_dir: Path) -> dict`
- [ ] Read from:
  - graph_analysis.json
  - cfg.json
  - fce.json
- [ ] Extract:
  - Hotspot count (from graph_analysis.json)
  - Cycle count (from graph_analysis.json)
  - Complex function count (from cfg.json)
  - FCE meta-findings (from fce.json correlations.meta_findings)
- [ ] Output truth courier format:
  ```json
  {
    "summary": "X hotspots, Y cycles, Z complex functions, W FCE meta-findings",
    "counts": {
      "architectural_hotspots": X,
      "dependency_cycles": Y,
      "complex_functions": Z,
      "fce_meta_findings": W
    },
    "fce_meta_findings": [
      {"type": "ARCHITECTURAL_RISK_ESCALATION", "file": "api.py", "finding_count": 5},
      ...
    ],
    "query_alternative": "aud context --file api.py --show-dependencies"
  }
  ```
- [ ] Write to `.pf/readthis/Intelligence_Summary.json`

### 1.5 Implement Quick_Start Generator
- [ ] Create function `generate_quick_start(raw_dir: Path) -> dict`
- [ ] Read from:
  - fce.json (correlations.meta_findings)
- [ ] Extract:
  - Top FCE meta-findings (ARCHITECTURAL_RISK_ESCALATION, COMPLEXITY_RISK_CORRELATION, etc.)
  - Show file:line locations
  - Show finding counts per file
- [ ] Output truth courier format:
  ```json
  {
    "summary": "X critical FCE correlations across Y files",
    "top_issues": [
      {
        "type": "ARCHITECTURAL_RISK_ESCALATION",
        "file": "api.py",
        "finding_count": 5,
        "severity": "critical",
        "message": "Critical security issues in architectural hotspot"
      },
      ...
    ],
    "guidance": "These are factual correlations identified by FCE. Query database for details.",
    "query_examples": [
      "aud query --file api.py --show-calls",
      "aud context --file api.py --show-dependencies"
    ]
  }
  ```
- [ ] Write to `.pf/readthis/Quick_Start.json`

### 1.6 Implement Query_Guide Generator
- [ ] Create function `generate_query_guide() -> dict`
- [ ] Static reference document (no file reading)
- [ ] Output query examples for each domain:
  ```json
  {
    "security_queries": [
      "aud query --tool taint --show-paths",
      "aud query --tool patterns --severity critical"
    ],
    "dependency_queries": [
      "aud query --symbol-type import --group-by package"
    ],
    "architecture_queries": [
      "aud context --file api.py --show-dependencies",
      "aud query --calls main --depth 3"
    ],
    "performance_note": "Database queries are 100x faster than parsing JSON files"
  }
  ```
- [ ] Write to `.pf/readthis/Query_Guide.json`

### 1.7 Wire Up Command
- [ ] In summarize command main function:
  - Call all 5 generators
  - Create `.pf/readthis/` directory if it doesn't exist
  - Write all 5 JSON files
  - Print summary: "[OK] Generated 5 summaries in .pf/readthis/"
- [ ] Add error handling (graceful failure if /raw/ files missing)
- [ ] Add CLI help documentation

## 2. Modify Pipeline

### 2.1 Find and Remove Extraction Call
- [ ] Open `theauditor/pipelines.py`
- [ ] Search for "extraction" or "extract_all_to_readthis"
- [ ] Find the line that calls extraction (likely after FCE phase)
- [ ] Comment out or remove extraction call
- [ ] Remove extraction import statement

### 2.2 Add Summarize Call
- [ ] After FCE phase (where extraction was called)
- [ ] Add summarize call via subprocess:
  ```python
  # Generate guidance summaries
  summarize_result = subprocess.run(
      ["aud", "summarize", "--project-path", str(root)],
      cwd=root,
      capture_output=True,
      text=True
  )
  if summarize_result.returncode == 0:
      logger.info("[SUMMARIZE] Generated 5 guidance summaries")
  else:
      logger.warning(f"[SUMMARIZE] Failed: {summarize_result.stderr}")
  ```
- [ ] Update phase counter if needed

### 2.3 Test Pipeline
- [ ] Run `aud full --offline` on test project
- [ ] Verify: Log shows "[SUMMARIZE]" message
- [ ] Verify: No errors in pipeline execution
- [ ] Verify: 5 summaries created in .pf/readthis/

## 3. Deprecate Extraction System

### 3.1 Rename extraction.py
- [ ] Rename `theauditor/extraction.py` to `theauditor/extraction.py.bak`
- [ ] Use git mv to preserve history: `git mv theauditor/extraction.py theauditor/extraction.py.bak`

### 3.2 Verify No Remaining Imports
- [ ] Search codebase: `grep -r "from.*extraction import" theauditor/`
- [ ] Search codebase: `grep -r "import extraction" theauditor/`
- [ ] Should find ZERO matches (extraction should only be in pipeline, which we removed)
- [ ] If any found, remove those imports

### 3.3 Update .gitignore
- [ ] Add to `.gitignore`:
  ```
  # Chunked files deprecated - only summaries remain
  .pf/readthis/*_chunk*.json
  ```
- [ ] Leave summaries unignored (we want to commit them)

## 4. Verify NO Changes to Analyzers

### 4.1 Verify Analyzer Commands Unchanged
- [ ] Check: `theauditor/commands/graph.py` - NO modifications
- [ ] Check: `theauditor/commands/detect_patterns.py` - NO modifications
- [ ] Check: `theauditor/commands/taint.py` - NO modifications (except what was cleaned up)
- [ ] Check: `theauditor/commands/cfg.py` - NO modifications
- [ ] Check: `theauditor/commands/deadcode.py` - NO modifications
- [ ] Check: `theauditor/commands/detect_frameworks.py` - NO modifications
- [ ] Check: `theauditor/commands/terraform.py` - NO modifications
- [ ] Check: `theauditor/commands/docker_analyze.py` - NO modifications
- [ ] Check: `theauditor/commands/workflows.py` - NO modifications
- [ ] Check: `theauditor/fce.py` - NO modifications

### 4.2 Verify /raw/ Files Still Generated
- [ ] Run individual commands and check outputs:
  - `aud detect-patterns` → creates patterns.json
  - `aud taint-analyze` → creates taint.json
  - `aud cfg analyze` → creates cfg.json
  - `aud deadcode` → creates deadcode.json
  - `aud detect-frameworks` → creates frameworks.json
  - `aud graph analyze` → creates graph_analysis.json
  - `aud fce` → creates fce.json
- [ ] All files should exist in `.pf/raw/` with original names

## 5. Update Documentation

### 5.1 Update README.md
- [ ] Find "OUTPUT STRUCTURE" section
- [ ] Update to show:
  ```
  .pf/
  ├── raw/                    # Immutable tool outputs (ground truth)
  │   ├── patterns.json       # detect-patterns output
  │   ├── taint.json          # taint-analyze output
  │   ├── cfg.json            # cfg analyze output
  │   ├── deadcode.json       # deadcode output
  │   ├── frameworks.json     # detect-frameworks output
  │   ├── graph_analysis.json # graph analyze output
  │   ├── fce.json            # fce correlations
  │   └── ... (20+ separate files)
  ├── readthis/              # AI-optimized summaries
  │   ├── SAST_Summary.json  # Security findings summary
  │   ├── SCA_Summary.json   # Dependency issues summary
  │   ├── Intelligence_Summary.json # Code intelligence summary
  │   ├── Quick_Start.json   # Top critical issues (FCE-guided)
  │   └── Query_Guide.json   # Database query reference
  ├── repo_index.db          # PRIMARY DATA SOURCE - query with `aud query`
  └── pipeline.log           # Detailed execution trace
  ```
- [ ] Add note: "AIs should query repo_index.db via `aud query` for full analysis. Summaries provide quick orientation only."

### 5.2 Add Migration Guide
- [ ] Add section to README:
  ```markdown
  ## Migration from Chunks to Summaries

  If you have scripts that previously read `.pf/readthis/*_chunk*.json` files:

  **Option 1 (Recommended)**: Use database queries
  ```bash
  # Instead of parsing JSON chunks
  aud query --tool taint --show-paths
  aud query --file api.py --show-calls
  ```

  **Option 2**: Read /raw/ files directly
  - patterns.json - All pattern findings
  - taint.json - All taint paths
  - fce.json - All FCE correlations

  **Option 3**: Read summaries for quick overview
  - SAST_Summary.json - Security overview
  - Intelligence_Summary.json - Architecture overview
  ```

### 5.3 Update CLI Help
- [ ] Update `aud summarize --help` documentation
- [ ] Add note to `aud full --help`: "Generates summaries in .pf/readthis/, not chunks"

## 6. Integration Testing

### 6.1 Clean Test Run
- [ ] Delete `.pf/` directory
- [ ] Run `aud init`
- [ ] Run `aud full --offline`
- [ ] Verify: Pipeline completes without errors

### 6.2 Verify /raw/ Files
- [ ] Check `.pf/raw/` directory
- [ ] Count files: Should have 20+ separate JSON files
- [ ] Verify key files exist:
  - patterns.json
  - taint.json
  - cfg.json
  - deadcode.json
  - frameworks.json
  - graph_analysis.json
  - fce.json

### 6.3 Verify /readthis/ Summaries
- [ ] Check `.pf/readthis/` directory
- [ ] Should have EXACTLY 5 files:
  - SAST_Summary.json
  - SCA_Summary.json
  - Intelligence_Summary.json
  - Quick_Start.json
  - Query_Guide.json
- [ ] Should have ZERO chunk files (*_chunk*.json)

### 6.4 Verify Summary Content
- [ ] Open SAST_Summary.json:
  - Has "summary" field with count statement
  - Has "counts" object with numbers
  - Has "query_alternative" field
  - NO severity filtering
  - NO recommendations
- [ ] Open Intelligence_Summary.json:
  - Has FCE meta-findings
  - Shows file:line locations
  - NO recommendations
- [ ] Open Quick_Start.json:
  - Shows FCE correlations
  - Has file:line locations
  - Truth courier format only

## 7. Final Verification Checklist

- [ ] ✅ All 20+ /raw/ files UNCHANGED
- [ ] ✅ 5 summaries in /readthis/
- [ ] ✅ NO chunks in /readthis/
- [ ] ✅ extraction.py renamed to .bak
- [ ] ✅ NO changes to analyzer commands
- [ ] ✅ Pipeline runs without errors
- [ ] ✅ Summaries follow truth courier model
- [ ] ✅ Documentation updated
- [ ] ✅ Migration guide added

## Completion Criteria

**Must Have**:
- Create summarize command with 5 generators ✅
- Modify pipeline to call summarize instead of extraction ✅
- Rename extraction.py to .bak ✅
- NO changes to any analyzer ✅
- 5 summaries generated in /readthis/ ✅

**Must NOT Have**:
- Any consolidation of /raw/ files ❌
- Any modifications to analyzer commands ❌
- Any severity filtering in summaries ❌
- Any recommendations in summaries ❌

**Success Metrics**:
- `aud full --offline` runs without errors
- 20+ /raw/ files generated (unchanged from before)
- 5 summaries in /readthis/ (no chunks)
- All summaries follow truth courier model
- Database queries still work correctly
