## 0. Verification (Pre-Implementation)

- [ ] 0.1 Run `aud --help | wc -l` - confirm ~366 lines
- [ ] 0.2 Run `aud init-config` - verify command works (will deprecate, not delete)
- [ ] 0.3 Run `aud init-js` - verify command works
- [ ] 0.4 Run `aud tool-versions` - verify command works
- [ ] 0.5 Confirm no other code imports from init_config.py, init_js.py, tool_versions.py

## 1. Phase 1: Restructure cli.py

### 1.1 Replace cli() Docstring (cli.py:154-221)

**Location:** `theauditor/cli.py:153-222`

**Current:** 65+ line docstring with PURPOSE, WORKFLOWS, EXIT CODES, ENV VARS

**Replace with:**
```python
@click.group(cls=VerboseGroup)
@click.version_option(version=__version__, prog_name="aud")
@click.help_option("-h", "--help")
def cli():
    """TheAuditor - Security & Code Intelligence Platform

    QUICK START:
      aud full                    # Complete security audit
      aud full --offline          # Air-gapped analysis
      aud manual --list           # Learn concepts

    For detailed options: aud <command> --help
    For concepts: aud manual --list"""
    pass
```

- [ ] 1.1.1 Edit `cli.py:153-222` - replace docstring with 10-line version above

### 1.2 Remove Inline Params from format_help() (cli.py:123-127)

**Location:** `theauditor/cli.py:123-127`

**Current:**
```python
                    if hasattr(cmd, 'params'):
                        key_options = [p for p in cmd.params[:3] if hasattr(p, 'help') and p.help]
                        for param in key_options:
                            opt_name = f"--{param.name.replace('_', '-')}"
                            formatter.write_text(f"  {opt_name:22s} # {param.help}")
```

**Delete:** Remove these 5 lines entirely.

- [ ] 1.2.1 Delete lines 123-127 in `cli.py`

### 1.3 Remove AI ASSISTANT GUIDANCE Header (cli.py:101-106)

**Location:** `theauditor/cli.py:101-106`

**Current:**
```python
        formatter.write_text("AI ASSISTANT GUIDANCE:")
        formatter.write_text("  - Commands are grouped by purpose for optimal workflow ordering")
        formatter.write_text("  - Each category shows WHEN and WHY to use commands")
        formatter.write_text("  - Run 'aud <command> --help' for detailed AI-consumable documentation")
        formatter.write_text("  - Use 'aud manual <concept>' to learn about taint, workset, fce, etc.")
        formatter.write_paragraph()
```

**Delete:** Remove these 6 lines.

- [ ] 1.3.1 Delete lines 101-106 in `cli.py`

### 1.4 Fix Hidden Command Warning Bug (cli.py:98-99, 135)

**Location:** `theauditor/cli.py:98-99`

**Current:**
```python
        registered = {name: cmd for name, cmd in self.commands.items()
                     if not name.startswith('_')}
```

**Change to:**
```python
        registered = {name: cmd for name, cmd in self.commands.items()
                     if not name.startswith('_') and not getattr(cmd, 'hidden', False)}
```

- [ ] 1.4.1 Edit `cli.py:98-99` - add hidden check to registered filter

### 1.5 Add Footer (cli.py, after line 145)

After line 145 (before warning section), add:
```python
        formatter.write_paragraph()
        formatter.write_text("For detailed options: aud <command> --help")
        formatter.write_text("For concepts: aud manual --list")
```

- [ ] 1.5.1 Add footer lines after category loop in `cli.py`

### 1.6 Test Phase 1

- [ ] 1.6.1 Run `aud --help | wc -l` - confirm <80 lines
- [ ] 1.6.2 Run `aud --help` - verify no inline options shown
- [ ] 1.6.3 Run `aud --help` - verify no "AI ASSISTANT GUIDANCE" header
- [ ] 1.6.4 Run `aud --help` - verify no "WARNING: uncategorized" section

## 2. Phase 2: Deprecate Commands

### 2.1 Deprecate init-config (init_config.py)

**Location:** `theauditor/commands/init_config.py:6-8`

**Current:**
```python
@click.command("init-config")
@click.option("--pyproject", default="pyproject.toml", help="Path to pyproject.toml")
def init_config(pyproject):
```

**Change to:**
```python
@click.command("init-config", hidden=True)
@click.option("--pyproject", default="pyproject.toml", help="Path to pyproject.toml")
def init_config(pyproject):
```

**Add at start of function (after docstring, line 56):**
```python
    click.echo("WARNING: 'aud init-config' is deprecated and will be removed in v2.0.")
    click.echo("         Mypy configuration is not part of security auditing.")
    click.echo("")
```

- [ ] 2.1.1 Edit `init_config.py:6` - add `hidden=True` to @click.command
- [ ] 2.1.2 Edit `init_config.py:56` - add deprecation warning after docstring

### 2.2 Deprecate init-js (init_js.py)

**Location:** `theauditor/commands/init_js.py:6-9`

**Current:**
```python
@click.command("init-js")
@click.option("--path", default="package.json", help="Path to package.json")
@click.option("--add-hooks", is_flag=True, help="Add TheAuditor hooks to npm scripts")
def init_js(path, add_hooks):
```

**Change to:**
```python
@click.command("init-js", hidden=True)
@click.option("--path", default="package.json", help="Path to package.json")
@click.option("--add-hooks", is_flag=True, help="Add TheAuditor hooks to npm scripts")
def init_js(path, add_hooks):
```

**Add at start of function (after docstring, line 174):**
```python
    click.echo("WARNING: 'aud init-js' is deprecated and will be removed in v2.0.")
    click.echo("         Package.json scaffolding is not part of security auditing.")
    click.echo("")
```

- [ ] 2.2.1 Edit `init_js.py:6` - add `hidden=True` to @click.command
- [ ] 2.2.2 Edit `init_js.py:174` - add deprecation warning after docstring

### 2.3 Deprecate tool-versions (tool_versions.py)

**Location:** `theauditor/commands/tool_versions.py:6-8`

**Current:**
```python
@click.command("tool-versions")
@click.option("--out-dir", default="./.pf/raw", help="Output directory for version manifest")
def tool_versions(out_dir):
```

**Change to:**
```python
@click.command("tool-versions", hidden=True)
@click.option("--out-dir", default="./.pf/raw", help="Output directory for version manifest")
def tool_versions(out_dir):
```

**Add at start of function (after docstring, line 95):**
```python
    click.echo("WARNING: 'aud tool-versions' is deprecated.")
    click.echo("         Use 'aud setup-ai --show-versions' instead.")
    click.echo("")
```

- [ ] 2.3.1 Edit `tool_versions.py:6` - add `hidden=True` to @click.command
- [ ] 2.3.2 Edit `tool_versions.py:95` - add deprecation warning after docstring

### 2.4 Remove from COMMAND_CATEGORIES (cli.py:31-34, 65)

**Location:** `theauditor/cli.py:31-34`

**Current:**
```python
        'PROJECT_SETUP': {
            'title': 'PROJECT SETUP',
            'description': 'Initial configuration and environment setup',
            'commands': ['setup-ai', 'init-js', 'init-config'],
```

**Change to:**
```python
        'PROJECT_SETUP': {
            'title': 'PROJECT SETUP',
            'description': 'Initial configuration and environment setup',
            'commands': ['setup-ai'],
```

**Location:** `theauditor/cli.py:65`

**Current:**
```python
            'commands': ['fce', 'report', 'structure', 'summary', 'metadata', 'tool-versions', 'blueprint'],
```

**Change to:**
```python
            'commands': ['fce', 'report', 'structure', 'summary', 'metadata', 'blueprint'],
```

- [ ] 2.4.1 Edit `cli.py:34` - remove 'init-js', 'init-config' from PROJECT_SETUP
- [ ] 2.4.2 Edit `cli.py:65` - remove 'tool-versions' from DATA_REPORTING

### 2.5 Add --show-versions to setup-ai (setup.py)

**Location:** `theauditor/commands/setup.py:20-24` (after existing options)

**Add new option:**
```python
@click.option(
    "--show-versions",
    is_flag=True,
    help="Show installed tool versions (reads from cache or runs detection)"
)
```

**Update function signature (line 25):**
```python
def setup_ai(target, sync, dry_run, show_versions):
```

**Add at start of function (after dry_run handling, around line 216):**

Note: `--target` is already required, so `target` will always have a value.

```python
    # Handle --show-versions (standalone operation)
    if show_versions:
        from theauditor.tools import write_tools_report

        # target is required, so always valid
        out_dir = target_dir / ".pf" / "raw"  # target_dir is already resolved above
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            res = write_tools_report(str(out_dir))
            click.echo(f"Tool versions (from {out_dir}):")
            click.echo(f"  Python tools: {sum(1 for v in res['python'].values() if v != 'missing')}/4 found")
            click.echo(f"  Node tools: {sum(1 for v in res['node'].values() if v != 'missing')}/3 found")
            for tool, version in res["python"].items():
                click.echo(f"    {tool}: {version}")
            for tool, version in res["node"].items():
                click.echo(f"    {tool}: {version}")
        except Exception as e:
            click.echo(f"Error detecting tool versions: {e}", err=True)
        return  # Exit after showing versions
```

- [ ] 2.5.1 Add `--show-versions` option to `setup.py:20-24`
- [ ] 2.5.2 Update function signature to include `show_versions`
- [ ] 2.5.3 Add show_versions handler after dry_run check

### 2.6 Test Phase 2

- [ ] 2.6.1 Run `aud init-config` - verify deprecation warning shown
- [ ] 2.6.2 Run `aud init-js` - verify deprecation warning shown
- [ ] 2.6.3 Run `aud tool-versions` - verify deprecation warning shown
- [ ] 2.6.4 Run `aud --help` - verify init-config, init-js, tool-versions NOT listed
- [ ] 2.6.5 Run `aud setup-ai --show-versions --target .` - verify tool versions shown

## 3. Phase 3: Hide Dev Flags in full.py

**Location:** `theauditor/commands/full.py:13, 15`

**Current (line 13):**
```python
@click.option("--exclude-self", is_flag=True, help="Exclude TheAuditor's own files (for self-testing)")
```

**Change to:**
```python
@click.option("--exclude-self", is_flag=True, hidden=True, help="Exclude TheAuditor's own files (for self-testing)")
```

**Current (line 15):**
```python
@click.option("--subprocess-taint", is_flag=True, help="Run taint analysis as subprocess (slower but isolated)")
```

**Change to:**
```python
@click.option("--subprocess-taint", is_flag=True, hidden=True, help="Run taint analysis as subprocess (slower but isolated)")
```

- [ ] 3.1 Edit `full.py:13` - add `hidden=True` to --exclude-self
- [ ] 3.2 Edit `full.py:15` - add `hidden=True` to --subprocess-taint
- [ ] 3.3 Run `aud full --help` - verify --exclude-self NOT shown
- [ ] 3.4 Run `aud full --help` - verify --subprocess-taint NOT shown
- [ ] 3.5 Run `aud full --exclude-self` - verify flag still WORKS

## 4. Phase 4: Add Manual Concepts

**Location:** `theauditor/commands/manual.py:8-516` (EXPLANATIONS dict)

Add 4 new entries to the EXPLANATIONS dict after the existing "insights" entry:

### 4.1 Add "overview" concept

```python
    "overview": {
        "title": "TheAuditor Overview",
        "summary": "What TheAuditor is and how it works",
        "explanation": """
TheAuditor is an offline-first, AI-centric SAST (Static Application Security Testing)
platform. It provides ground truth about your codebase through comprehensive security
analysis, taint tracking, and quality auditing.

PURPOSE:
  Designed for both human developers and AI assistants to detect:
  - Security vulnerabilities (SQL injection, XSS, command injection)
  - Incomplete refactorings (broken imports, orphan code)
  - Architectural issues (circular dependencies, hotspots)

PHILOSOPHY:
  TheAuditor is a Truth Courier, Not a Mind Reader:
  - Finds where code doesn't match itself (inconsistencies)
  - Does NOT try to understand business logic
  - Reports FACTS, not interpretations

OUTPUT STRUCTURE:
  .pf/
  ├── raw/                    # Immutable tool outputs (ground truth)
  ├── readthis/              # AI-optimized chunks (<65KB each)
  │   ├── *_chunk01.json     # Chunked findings for LLM consumption
  │   └── summary.json       # Executive summary
  ├── repo_index.db          # SQLite database with all code symbols
  └── pipeline.log           # Detailed execution trace

USE THE COMMANDS:
    aud full                          # Complete security audit
    aud manual workflows              # See common workflows
    aud manual exit-codes             # Understand exit codes
"""
    },
```

- [ ] 4.1.1 Add "overview" concept to EXPLANATIONS dict in manual.py

### 4.2 Add "workflows" concept

```python
    "workflows": {
        "title": "Common Workflows",
        "summary": "Typical usage patterns for TheAuditor",
        "explanation": """
FIRST TIME SETUP:
    aud full                          # Complete audit (auto-creates .pf/)

AFTER CODE CHANGES:
    aud workset --diff HEAD~1         # Identify changed files
    aud lint --workset                # Quality check changes
    aud taint-analyze --workset       # Security check changes

PULL REQUEST REVIEW:
    aud workset --diff main..feature  # What changed in PR
    aud impact --file api.py --line 1 # Check change impact
    aud detect-patterns --workset     # Security patterns

SECURITY AUDIT:
    aud full --offline                # Complete offline audit
    aud deps --vuln-scan              # Check for CVEs
    aud manual severity               # Understand findings

PERFORMANCE OPTIMIZATION:
    aud cfg analyze --threshold 20    # Find complex functions
    aud graph analyze                 # Find circular dependencies
    aud structure                     # Understand architecture

CI/CD PIPELINE:
    aud full --quiet || exit $?       # Fail on critical issues

UNDERSTANDING RESULTS:
    aud manual taint                  # Learn about concepts
    aud structure                     # Project overview
    aud report --print-stats          # Summary statistics
"""
    },
```

- [ ] 4.2.1 Add "workflows" concept to EXPLANATIONS dict in manual.py

### 4.3 Add "exit-codes" concept

```python
    "exit-codes": {
        "title": "Exit Codes",
        "summary": "What TheAuditor's exit codes mean",
        "explanation": """
TheAuditor uses standardized exit codes for CI/CD automation:

EXIT CODES:
    0 = Success, no critical or high severity issues found
    1 = High severity findings detected (needs attention)
    2 = Critical security vulnerabilities found (block deployment)
    3 = Analysis incomplete or pipeline failed

USAGE IN CI/CD:
    # Fail pipeline on any issues
    aud full --quiet || exit $?

    # Fail only on critical
    aud full --quiet
    if [ $? -eq 2 ]; then
        echo "CRITICAL vulnerabilities found!"
        exit 1
    fi

    # Continue with warnings
    aud full --quiet
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 2 ]; then
        exit 1  # Block on critical
    elif [ $EXIT_CODE -eq 1 ]; then
        echo "Warning: High severity issues found"
    fi
"""
    },
```

- [ ] 4.3.1 Add "exit-codes" concept to EXPLANATIONS dict in manual.py

### 4.4 Add "env-vars" concept

```python
    "env-vars": {
        "title": "Environment Variables",
        "summary": "Configuration options via environment variables",
        "explanation": """
TheAuditor can be configured via environment variables:

FILE SIZE LIMITS:
    THEAUDITOR_LIMITS_MAX_FILE_SIZE=2097152   # Max file size in bytes (default: 2MB)
    THEAUDITOR_LIMITS_MAX_CHUNK_SIZE=65536    # Max chunk size (default: 65KB)

TIMEOUTS:
    THEAUDITOR_TIMEOUT_SECONDS=1800           # Default timeout (default: 30 min)
    THEAUDITOR_TIMEOUT_TAINT_SECONDS=600      # Taint analysis timeout
    THEAUDITOR_TIMEOUT_LINT_SECONDS=300       # Linting timeout

PERFORMANCE:
    THEAUDITOR_DB_BATCH_SIZE=200              # Database batch insert size

EXAMPLES:
    # Increase file size limit for large files
    export THEAUDITOR_LIMITS_MAX_FILE_SIZE=5242880  # 5MB
    aud full

    # Increase timeout for large codebase
    export THEAUDITOR_TIMEOUT_SECONDS=3600  # 1 hour
    aud full

    # Optimize for SSD with larger batches
    export THEAUDITOR_DB_BATCH_SIZE=500
    aud full
"""
    },
```

- [ ] 4.4.1 Add "env-vars" concept to EXPLANATIONS dict in manual.py

### 4.5 Test Phase 4

- [ ] 4.5.1 Run `aud manual --list` - verify 4 new concepts listed
- [ ] 4.5.2 Run `aud manual overview` - verify content displayed
- [ ] 4.5.3 Run `aud manual workflows` - verify content displayed
- [ ] 4.5.4 Run `aud manual exit-codes` - verify content displayed
- [ ] 4.5.5 Run `aud manual env-vars` - verify content displayed

## 5. Final Validation

- [ ] 5.1 Run `aud --help | wc -l` - MUST be <80 lines
- [ ] 5.2 Run `aud --help` - verify clean output with no bloat
- [ ] 5.3 Run `aud full --help` - verify --exclude-self NOT visible
- [ ] 5.4 Run `aud full --exclude-self` - verify flag still WORKS
- [ ] 5.5 Run `aud init-config` - verify deprecation warning
- [ ] 5.6 Run `aud setup-ai --show-versions --target .` - verify works
- [ ] 5.7 Run `aud manual --list` - verify all 13 concepts listed (9 original + 4 new)
- [ ] 5.8 Grep codebase for imports of deprecated commands (should only be cli.py)
