<!-- THEAUDITOR:START -->
# TheAuditor Agent System

For full documentation, see: @/.auditor_venv/.theauditor_tools/agents/AGENTS.md

**Quick Route:**
| Intent | Agent | Triggers |
|--------|-------|----------|
| Plan changes | planning.md | plan, architecture, design, structure |
| Refactor code | refactor.md | refactor, split, extract, modularize |
| Security audit | security.md | security, vulnerability, XSS, SQLi, CSRF |
| Trace dataflow | dataflow.md | dataflow, trace, source, sink |

**The One Rule:** Database first. Always run `aud blueprint --structure` before planning.

**Agent Locations:**
- Full protocols: .auditor_venv/.theauditor_tools/agents/*.md
- Slash commands: /theauditor:planning, /theauditor:security, /theauditor:refactor, /theauditor:dataflow

**Setup:** Run `aud setup-ai --target . --sync` to reinstall agents.

<!-- THEAUDITOR:END -->

---

## Custom Slash Commands (`.claude/commands/`)

Workflow commands encoding team philosophy. Use these as guidance even when not explicitly invoked.

| Command | Purpose | Key Insight |
|---------|---------|-------------|
| `/onboard` | Session init with roles/rules | Read teamsop.md + CLAUDE.md fully |
| `/start <ticket>` | Load ticket, verify, brief before building | NO partial reads, cross-reference against reality |
| `/spec` | Create OpenSpec proposal | Atomic, ironclad, explicit HOW and WHY |
| `/check <target>` | Due diligence review | Balance: fix real issues, skip code style fetishes |
| `/docs <target>` | Document a component | Use `aud explain` first, write to root |
| `/audit <path>` | Comprehensive audit | Run aud commands + manual review, prioritized output |
| `/explore` | Architecture discovery | Database first, propose structure, wait for approval |
| `/git` | Generate commit message | NO Co-authored-by, explain WHY not WHAT |

**Core Philosophy Baked Into Commands:**
1. **ZERO FALLBACK** - Hunt and destroy hidden fallbacks
2. **Polyglot awareness** - Python + Node + Rust, don't forget the orchestrator
3. **Verification first** - Read code before making claims (Prime Directive)
4. **No over-engineering** - Fix functionality, skip developer purist fetishes
5. **Single root output** - Docs/reports to root, not nested folder hell

<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# ABSOLUTE RULES - READ FIRST OR WASTE TIME

NEVER EVER FUCKING TOUCH MY GIT WITH YOUR DUMBASS FUCKING "CO AUTHORED BY CLAUDE" FUCK THE FUCKING FUCK OFF DUMBASS FUCKFACE!!!

## CORRECT AUD COMMANDS - STOP RUNNING DEPRECATED SHIT

**ONLY USE THESE:**
```bash
aud full --index      # Just indexing (rebuilds repo_index.db + graphs.db)
aud full --offline    # Full pipeline WITHOUT network (PREFERRED - no rate limiting)
aud full              # Full pipeline with network (slow due to docs/deps fetching)
```

**DEPRECATED - DO NOT USE:**
- ~~`aud index`~~ - DOES NOT EXIST
- ~~`aud init`~~ - DOES NOT EXIST
- Any other standalone indexing commands

**Why --offline is preferred:** Network fetches for docs/deps have aggressive rate limiting and take forever. Use `--offline` unless you specifically need version checking.

## NEVER USE SQLITE3 COMMAND DIRECTLY

**ALWAYS** use Python with sqlite3 import. The sqlite3 command is not installed in WSL.

## CRITICAL WINDOWS BUG!!
ultrathink remember the windows bug. when it happens...The workaround is: always use complete absolute Windows paths with drive letters and backslashes for ALL file operations. Apply this rule going forward, not just for this file.... a windows path looks like C:\Users\santa\Desktop\TheAuditor\theauditor... not fucking unix forward /
You only use your regular write, edit etc tools. no weird eof, cat or python writes or copies... be normal... its just a windows path bug...

```python
# CORRECT - Always use this pattern
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('C:/path/to/database.db')
c = conn.cursor()
c.execute('SELECT ...')
for row in c.fetchall():
    print(row)
conn.close()
"
```

```bash
# WRONG - This will fail with "sqlite3: command not found"
sqlite3 database.db "SELECT ..."
```

## NEVER USE EMOJIS IN PYTHON OUTPUT

Windows Command Prompt uses CP1252 encoding. Emojis cause `UnicodeEncodeError: 'charmap' codec can't encode character`.

```python
# WRONG - Will crash on Windows
print('Status: ✅ PASS')
print('Cross-file: ❌')

# CORRECT - Use plain ASCII
print('Status: PASS')
print('Cross-file: NO')
```

**These two rules alone waste 5-10 tool calls per session. Follow them religiously.**

## ENVIRONMENT: WSL/PowerShell on Windows

**CRITICAL**: You are running in Windows Subsystem for Linux (WSL) with PowerShell commands available. This is NOT a pure Linux environment.

### NEVER USE THESE (Linux-specific):

❌ `python3` - Use `python` instead (Python 3.13 is default)
❌ `/mnt/c/Users/...` - Use `C:/Users/...` or `/c/Users/...` paths
❌ `source .venv/bin/activate` - Use `.venv/Scripts/activate` (Windows paths)
❌ Unix-only commands - `which`, `whereis`, etc.
❌ `ls -la` with long flags - Prefer simple `ls` or `dir`

### ALWAYS USE THESE (WSL/Windows-compatible):

✅ `python` (not python3) - Windows Python 3.13 / Use pwhshell 7 not the regular powershell for shell.
✅ `C:/Users/santa/Desktop/TheAuditor` - Forward slashes work in WSL
✅ `.venv/Scripts/python.exe` - Windows-style Python executable
✅ `.venv/Scripts/aud.exe` - Installed executables in Scripts/
✅ Simple bash commands - `cd`, `ls`, `cat`, `grep`, `wc`

### Path Examples:

```bash
# CORRECT - Windows paths with forward slashes
cd C:/Users/santa/Desktop/TheAuditor
python -m theauditor.cli --help
.venv/Scripts/python.exe -c "import sqlite3; print('works')"

# WRONG - Linux /mnt/ paths
cd /mnt/c/Users/santa/Desktop/TheAuditor  # ❌ Don't use /mnt/
python3 -m theauditor.cli  # ❌ python3 doesn't exist
source .venv/bin/activate  # ❌ bin/ doesn't exist on Windows
```

### Python Execution Pattern:

```bash
# CORRECT - Always use this pattern
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('C:/path/to/database.db')
# ... your code
"

# WRONG - Linux-style
python3 -c "..."  # ❌ python3 command not found
source .venv/bin/activate && python -c "..."  # ❌ bin/ doesn't exist
```

### Global `aud` Command:

```bash
# TheAuditor is installed globally - you can use 'aud' directly
aud --help
aud context query --symbol foo --show-callers
aud full

# No need for:
.venv/Scripts/aud.exe --help  # ❌ Too verbose
python -m theauditor.cli --help  # ❌ Too verbose
```

**Bottom Line**: Think "Windows with bash shell" not "Linux". Use Windows paths (C:/) and Windows Python (.exe), but Unix commands work (cd, ls, grep).

---

# TheAuditor Project Context (AUDITED 2025-11-22)

## Project Overview

TheAuditor is an offline-first, AI-centric SAST (Static Application Security Testing) and code intelligence platform written in Python. It performs comprehensive security auditing and code analysis for Python and JavaScript/TypeScript projects, producing AI-consumable reports optimized for LLM context windows.

**Version**: 1.6.4-dev1
**Python**: >=3.14 required
**Status**: Production-ready with critical fixes needed

### Related Documentation
- `Architecture.md` - Complete system architecture and audit findings
- `quality_report.md` - Comprehensive code quality analysis
- `HowToUse.md` - Installation and usage guide
- `README.md` - Project overview

---

## WHY TWO DATABASES (.pf/repo_index.db + .pf/graphs.db)

**repo_index.db (181MB)**: Raw extracted facts from AST parsing - symbols, calls, assignments, etc.
- Updated: Every `aud full` (regenerated fresh during indexing phase)
- Used by: Everything (rules, taint, FCE, context queries)
- Tables: 251 normalized tables across 8 schema domains

**graphs.db (126MB)**: Pre-computed graph structures built FROM repo_index.db
- Updated: During `aud full` via `aud graph build` phase (automatic)
- Used by: Graph commands only (`aud graph query`, `aud graph viz`)
- Tables: 4 polymorphic tables (nodes, edges, analysis_results, metadata)

**Why separate?** Different query patterns (point lookups vs graph traversal). Separate files allow selective loading. Standard data warehouse design: fact tables vs computed aggregates.

**Key insight**: FCE reads from repo_index.db, NOT graphs.db. Graph database is optional for visualization/exploration only.

---

# ⚠️ CRITICAL ARCHITECTURE RULE - READ FIRST ⚠️

## ZERO FALLBACK POLICY - ABSOLUTE AND NON-NEGOTIABLE

**NO FALLBACKS. NO EXCEPTIONS. NO WORKAROUNDS. NO "JUST IN CASE" LOGIC.**

This is the MOST IMPORTANT rule in the entire codebase. Violation of this rule is grounds for immediate rejection.

### Current Violations (MUST FIX)
- **fce.py**: 6+ try/except blocks returning empty
- **express_analyze.py**: 10 silent exception handlers
- **sql_injection_analyze.py**: 3 table existence checks
- **context/query.py**: 14 OperationalError handlers

### What is BANNED FOREVER:

1. **Database Query Fallbacks** - NEVER write multiple queries with fallback logic:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   cursor.execute("SELECT * FROM table WHERE name = ?", (normalized_name,))
   result = cursor.fetchone()
   if not result:  # ← THIS IS CANCER
       cursor.execute("SELECT * FROM table WHERE name = ?", (original_name,))
       result = cursor.fetchone()
   ```

2. **Try-Except Fallbacks** - NEVER catch exceptions to fall back to alternative logic:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   try:
       data = load_from_database()
   except Exception:  # ← THIS IS CANCER
       data = load_from_json()  # Fallback to JSON
   ```

3. **Table Existence Checks** - NEVER check if tables exist before querying:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   if 'function_call_args' in existing_tables:  # ← THIS IS CANCER
       cursor.execute("SELECT * FROM function_call_args")
   ```

### CORRECT Pattern - HARD FAIL IMMEDIATELY:

```python
# ✅ CORRECT - Single query, hard fail if wrong
cursor.execute("SELECT path FROM symbols WHERE name = ? AND type = 'function'", (name,))
result = cursor.fetchone()
if not result:
    # Log the failure (exposing the bug) and continue
    if debug:
        print(f"Symbol not found: {name}")
    continue  # Skip this path - DO NOT try alternative query
```

**ONLY ONE CODE PATH. IF IT FAILS, IT FAILS LOUD. NO SAFETY NETS.**

---

---

## Critical Development Patterns

### Adding New Commands

1. Create module in `theauditor/commands/`:
```python
import click
from theauditor.utils.decorators import handle_exceptions
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)

@click.command()
@click.option('--workset', is_flag=True, help='Use workset files')
@handle_exceptions
def command_name(workset):
    """Command description."""
    logger.info("Starting command...")
    # Implementation
```

2. Register in `theauditor/cli.py`:
```python
from theauditor.commands import your_command
cli.add_command(your_command.command_name)
```

### Adding Language Support

Create extractor in `theauditor/indexer/extractors/`:
```python
from theauditor.indexer.extractors import BaseExtractor, register_extractor

@register_extractor
class YourLanguageExtractor(BaseExtractor):
    @property
    def supported_extensions(self):
        return ['.ext', '.ext2']

    def extract(self, file_info, content, tree):
        # Return dict with symbols, imports, etc.
``

---

## Common CLI Commands

```bash
# Full analysis pipeline
aud full

# Comprehensive context (AI-Optimized) - USE THIS FIRST
aud explain <target>              # Auto-detects file/symbol/component
aud explain src/auth.ts           # File: symbols, hooks, deps, callers, callees
aud explain validateInput         # Symbol: definition, callers, callees with code
aud explain Dashboard             # Component: info, hooks, children
aud explain --format json file.py # JSON output for AI consumption
aud explain --depth 3 Symbol.method  # Deeper call graph traversal

# Query symbol information (use explain first, this for specific needs)
aud query --symbol function_name --show-callers
aud query --symbol foo --show-callers --show-code  # Include source snippets

# Run security rules
aud detect-patterns

# Taint analysis
aud taint-analyze

# Graph visualization
aud graph viz --output graph.svg

# Check specific file
aud workset --files file1.py file2.py

# Generate report
aud report
```

**AI Assistants:** Always use `aud explain` first - it returns symbols, dependencies, and calls in ONE command, saving 5,000-10,000 context tokens per task. Only use individual queries if explain doesn't provide what you need.

---

## Common Misconceptions

### TheAuditor is NOT:
- ❌ A semantic understanding tool
- ❌ A business logic validator
- ❌ An AI enhancement tool
- ❌ A code generator

### TheAuditor IS:
- ✅ A consistency checker (finds where code doesn't match itself)
- ✅ A fact reporter (ground truth about code)
- ✅ A context provider (gives AI full picture)
- ✅ An audit trail (immutable record)

---

## Quick Reference - Key Files

| Component | File | Lines |
|-----------|------|-------|
| Orchestrator | `theauditor/indexer/orchestrator.py` | 740 |
| Schema | `theauditor/indexer/schemas/*.py` | ~2000 |
| Database | `theauditor/indexer/database/__init__.py` + mixins | 2,313 |
| Storage | `theauditor/indexer/storage.py` | 1,200+ |
| Rule Orchestrator | `theauditor/rules/orchestrator.py` | 889 |
| Taint Analyzer | `theauditor/taint/*.py` | 4,280 |
| Graph Analyzer | `theauditor/graph/analyzer.py` | 485 |
| FCE Engine | `theauditor/fce.py` | 1,846 |
| CLI | `theauditor/cli.py` | 350 |
