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


---
ultrathink remember the windows bug. when "Error: File has been unexpectedly modified. Read it again before attempting to write it. The workaround is: always use complete absolute Windows paths with drive letters and backslashes for ALL file operations. Apply this rule going forward, not just for this file.... a windows path looks like C:\Users\santa\Desktop\TheAuditor\theauditor... not fucking unix forward /
You only use your regular write, edit etc tools. no weird eof, cat or python writes or copies... be normal... its just a windows path bug...

---

# CLAUDE.md - Operational Rules for AI Assistants

> **For Claude**: This is YOUR reference. Read top-to-bottom on session start. Rules are ordered by "how badly will I waste tool calls if I forget this."

---

## SECTION 1: HARD STOPS - VIOLATE THESE = IMMEDIATE FAILURE

### 1.1 GIT ATTRIBUTION - ABSOLUTE BAN
```
NEVER EVER FUCKING TOUCH MY GIT WITH YOUR DUMBASS "CO AUTHORED BY CLAUDE"
```

### 1.2 SQLITE3 COMMAND - DOES NOT EXIST
**ALWAYS** use Python with sqlite3 import. The sqlite3 command is not installed in WSL.

```bash
# WRONG - This will fail with "sqlite3: command not found"
sqlite3 database.db "SELECT ..."
```

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

### 1.3 EMOJIS IN PYTHON OUTPUT - WILL CRASH
Windows Command Prompt uses CP1252 encoding. Emojis cause `UnicodeEncodeError: 'charmap' codec can't encode character`.

```python
# WRONG - Will crash on Windows
print('Status: ✅ PASS')
print('Cross-file: ❌')

# CORRECT - Use plain ASCII
print('Status: PASS')
print('Cross-file: NO')
```

---

## SECTION 2: ENVIRONMENT - WSL/PowerShell on Windows

**CRITICAL**: You are running in Windows Subsystem for Linux (WSL) with PowerShell commands available. This is NOT a pure Linux environment.

### 2.1 NEVER USE (Linux-specific)
| Banned | Why |
|--------|-----|
| `python3` | Use `python` instead (Python 3.13 is default) |
| `/mnt/c/Users/...` | Use `C:/Users/...` or `/c/Users/...` paths |
| `source .venv/bin/activate` | Use `.venv/Scripts/activate` (Windows paths) |
| `which`, `whereis` | Unix-only commands |
| `ls -la` | Prefer simple `ls` or `dir` |

### 2.2 ALWAYS USE (WSL/Windows-compatible)
| Use This | Notes |
|----------|-------|
| `python` | Windows Python 3.13 / Use pwshell 7 not regular powershell |
| `C:/Users/santa/Desktop/TheAuditor` | Forward slashes work in WSL |
| `.venv/Scripts/python.exe` | Windows-style Python executable |
| `.venv/Scripts/aud.exe` | Installed executables in Scripts/ |
| `cd`, `ls`, `cat`, `grep`, `wc` | Simple bash commands work |

### 2.3 Path Examples
```bash
# CORRECT - Windows paths with forward slashes
cd C:/Users/santa/Desktop/TheAuditor
python -m theauditor.cli --help
.venv/Scripts/python.exe -c "import sqlite3; print('works')"

# WRONG - Linux /mnt/ paths
cd /mnt/c/Users/santa/Desktop/TheAuditor  # Don't use /mnt/
python3 -m theauditor.cli  # python3 doesn't exist
source .venv/bin/activate  # bin/ doesn't exist on Windows
```

### 2.4 Python Execution Pattern
```bash
# CORRECT - Always use this pattern
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('C:/path/to/database.db')
# ... your code
"

# WRONG - Linux-style
python3 -c "..."  # python3 command not found
source .venv/bin/activate && python -c "..."  # bin/ doesn't exist
```

### 2.5 Global `aud` Command
```bash
# TheAuditor is installed globally - you can use 'aud' directly
aud --help
aud context query --symbol foo --show-callers
aud full

# No need for:
.venv/Scripts/aud.exe --help  # Too verbose
python -m theauditor.cli --help  # Too verbose
```

**Bottom Line**: Think "Windows with bash shell" not "Linux". Use Windows paths (C:/) and Windows Python (.exe), but Unix commands work (cd, ls, grep).

### 2.6 JavaScript Extractor Build Requirement
The JavaScript/TypeScript AST extractor is a compiled TypeScript bundle. If it's missing, `aud full` will fail.

```bash
# Build the extractor bundle (required before first run or after TS changes)
cd C:/Users/santa/Desktop/TheAuditor/theauditor/ast_extractors/javascript
npm install    # First time only
npm run build  # Produces dist/extractor.cjs (~10MB)
```

---

## SECTION 3: AUD COMMANDS - CORRECT USAGE

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

---

## SECTION 4: ZERO FALLBACK POLICY - ARCHITECTURE LAW

**NO FALLBACKS. NO EXCEPTIONS. NO WORKAROUNDS. NO "JUST IN CASE" LOGIC.**

This is the MOST IMPORTANT rule in the entire codebase. Violation of this rule is grounds for immediate rejection.

### 4.1 What is BANNED FOREVER

**Database Query Fallbacks** - NEVER write multiple queries with fallback logic:
```python
# ABSOLUTELY FORBIDDEN
cursor.execute("SELECT * FROM table WHERE name = ?", (normalized_name,))
result = cursor.fetchone()
if not result:  # THIS IS CANCER
    cursor.execute("SELECT * FROM table WHERE name = ?", (original_name,))
    result = cursor.fetchone()
```

**Try-Except Fallbacks** - NEVER catch exceptions to fall back to alternative logic:
```python
# ABSOLUTELY FORBIDDEN
try:
    data = load_from_database()
except Exception:  # THIS IS CANCER
    data = load_from_json()  # Fallback to JSON
```

**Table Existence Checks** - NEVER check if tables exist before querying:
```python
# ABSOLUTELY FORBIDDEN
if 'function_call_args' in existing_tables:  # THIS IS CANCER
    cursor.execute("SELECT * FROM function_call_args")
```

### 4.2 CORRECT Pattern - HARD FAIL IMMEDIATELY
```python
# CORRECT - Single query, hard fail if wrong
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

## SECTION 5: DATABASE ARCHITECTURE

### 5.1 Two Databases Explained

| Database | Size | Purpose | Updated |
|----------|------|---------|---------|
| `.pf/repo_index.db` | ~181MB | Raw extracted facts from AST parsing | Every `aud full` |
| `.pf/graphs.db` | ~126MB | Pre-computed graph structures | During `aud full` via `aud graph build` |

**repo_index.db** - Raw extracted facts from AST parsing (symbols, calls, assignments, etc.)
- Used by: Everything (rules, taint, FCE, context queries)

**graphs.db** - Pre-computed graph structures built FROM repo_index.db
- Used by: Graph commands only (`aud graph query`, `aud graph viz`)

**Why separate?** Different query patterns (point lookups vs graph traversal). Separate files allow selective loading. Standard data warehouse design: fact tables vs computed aggregates.
**Key insight**: FCE reads from repo_index.db, NOT graphs.db. Graph database is optional for visualization/exploration only.

---

## SECTION 6: SLASH COMMANDS REFERENCE

### 6.1 Custom Slash Commands (`.claude/commands/`)

Workflow commands encoding team philosophy. Use these as guidance even when not explicitly invoked.

| Command | Purpose | Key Insight |
|---------|---------|-------------|
| `/onboard` | Session init with roles/rules | Read teamsop.md + CLAUDE.md fully |
| `/start <ticket>` | Load ticket, verify, brief before building | NO partial reads, cross-reference against reality |
| `/spec` | Create OpenSpec proposal | Atomic, ironclad, explicit HOW and WHY |
| `/check <target>` | OpenSpec proposal due diligence | Ironclad verification, FULL reads only, zero detective work |
| `/review <target>` | Code modernization/quality review | Balance: fix real issues, skip code style fetishes |
| `/docs <target>` | Document a component | Use `aud explain` first, write to root |
| `/audit <path>` | Comprehensive code audit | Run aud commands + manual review, prioritized output |
| `/explore` | Architecture discovery | Database first, propose structure, wait for approval |
| `/git` | Generate commit message | NO Co-authored-by, explain WHY not WHAT |
| `/progress` | Re-onboard after compaction | Restore context, sync state from tasks.md |
| `/sop` | Generate completion report | Template C-4.20, SHOW actual code evidence |

### 6.2 Core Philosophy Baked Into Commands
1. **ZERO FALLBACK** - Hunt and destroy hidden fallbacks
2. **Polyglot awareness** - Python + Node + Rust, don't forget the orchestrator
3. **Verification first** - Read code before making claims (Prime Directive)
4. **No over-engineering** - Fix functionality, skip developer purist fetishes
5. **Single root output** - Docs/reports to root, not nested folder hell

---