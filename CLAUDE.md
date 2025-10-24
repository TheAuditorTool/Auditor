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

## NEVER USE SQLITE3 COMMAND DIRECTLY

**ALWAYS** use Python with sqlite3 import. The sqlite3 command is not installed in WSL.

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

✅ `python` (not python3) - Windows Python 3.13
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
aud index

# No need for:
.venv/Scripts/aud.exe --help  # ❌ Too verbose
python -m theauditor.cli --help  # ❌ Too verbose
```

**Bottom Line**: Think "Windows with bash shell" not "Linux". Use Windows paths (C:/) and Windows Python (.exe), but Unix commands work (cd, ls, grep).

---

## Project Overview

TheAuditor is an offline-first, AI-centric SAST (Static Application Security Testing) and code intelligence platform written in Python. It performs comprehensive security auditing and code analysis for Python and JavaScript/TypeScript projects, producing AI-consumable reports optimized for LLM context windows.

**Version**: 1.3.0-RC1 (pyproject.toml:7)
**Python**: >=3.11 required (pyproject.toml:10)

---

# ⚠️ CRITICAL ARCHITECTURE RULE - READ FIRST ⚠️

## ZERO FALLBACK POLICY - ABSOLUTE AND NON-NEGOTIABLE

**NO FALLBACKS. NO EXCEPTIONS. NO WORKAROUNDS. NO "JUST IN CASE" LOGIC.**

This is the MOST IMPORTANT rule in the entire codebase. Violation of this rule is grounds for immediate rejection.

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

4. **Conditional Fallback Logic** - NEVER write "if X fails, try Y" patterns:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   result = method_a()
   if not result:  # ← THIS IS CANCER
       result = method_b()  # Fallback method
   ```

5. **Regex Fallbacks** - NEVER fall back to regex when database query fails:
   ```python
   # ❌❌❌ ABSOLUTELY FORBIDDEN ❌❌❌
   cursor.execute("SELECT * FROM symbols WHERE name = ?", (name,))
   if not cursor.fetchone():  # ← THIS IS CANCER
       matches = re.findall(pattern, content)  # Regex fallback
   ```

### Why NO FALLBACKS EVER:

The database is regenerated FRESH on every `aud full` run. If data is missing:
- **The database is WRONG** → Fix the indexer
- **The query is WRONG** → Fix the query
- **The schema is WRONG** → Fix the schema

Fallbacks HIDE bugs. They create:
- Inconsistent behavior across runs
- Silent failures that compound
- Technical debt that spreads like cancer
- False sense of correctness

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

### If a query returns NULL:
1. **DO NOT** write a second fallback query
2. **DO NOT** try alternative logic
3. **DO** log the failure with debug output
4. **DO** skip that code path (continue/return)
5. **DO** investigate WHY the query failed (indexer bug, schema bug, query bug)

### This applies to EVERYTHING:
- Database queries (symbols, function_call_args, assignments, etc.)
- File operations (reading, parsing, extracting)
- API calls (module resolution, import resolution)
- Data transformations (normalization, formatting)

**ONLY ONE CODE PATH. IF IT FAILS, IT FAILS LOUD. NO SAFETY NETS.**


## CLI Entry Points

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
```
### ABSOLUTE PROHIBITION: Fallback Logic & Regex

**NO FALLBACKS. NO REGEX. NO MIGRATIONS. NO EXCEPTIONS.**

The database is GENERATED FRESH every `aud full` run. It MUST exist and MUST be correct.
Schema contract system guarantees table existence. All code MUST assume contracted tables exist.

**FORBIDDEN PATTERNS:**
```python
# ❌ CANCER - Database migrations
def _run_migrations(self):
    try:
        cursor.execute("ALTER TABLE...")
    except sqlite3.OperationalError:
        pass  # NO! Database is fresh every run!

# ❌ CANCER - JSON fallbacks in FCE
try:
    data = load_from_db(db_path)
except Exception:
    # Fallback to JSON - NO! Hard fail if DB is wrong
    data = json.load(open('fallback.json'))

# ❌ CANCER - Table existence checking
if 'function_call_args' not in existing_tables:
    return findings

# ❌ CANCER - Fallback execution
if 'api_endpoints' not in existing_tables:
    return _check_oauth_state_fallback(cursor)

# ❌ CANCER - Regex on file content
pattern = re.compile(r'password\s*=\s*["\'](.+)["\']')
matches = pattern.findall(content)
```

**MANDATORY PATTERN:**
```python
# ✅ CORRECT - Direct database query, hard failure on error
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # NO try/except, NO table checks, NO fallbacks
    cursor.execute("""
        SELECT file, line, argument_expr
        FROM function_call_args
        WHERE callee_function LIKE '%jwt.sign'
    """)
    # Process findings...

# ✅ CORRECT - FCE loads directly from database
def run_fce(root_path):
    db_path = Path(root_path) / ".pf" / "repo_index.db"

    # NO try/except, NO JSON fallback, hard crash if DB wrong
    hotspots, cycles = load_graph_data_from_db(db_path)
    complex_funcs = load_cfg_data_from_db(db_path)
```

**WHY NO FALLBACKS:**
- Database regenerated from scratch every run - migrations are meaningless
- If data is missing, pipeline is broken and SHOULD crash
- Graceful degradation hides bugs and creates inconsistent behavior
- Hard failure forces immediate fix of root cause

**If table doesn't exist or data is missing, code MUST crash.** This indicates schema contract violation or pipeline bug that must be fixed immediately.

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

