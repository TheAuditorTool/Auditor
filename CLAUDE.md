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

### Codebase Statistics (2025-11-22 Comprehensive Audit)
- **Files**: 357 Python files
- **LOC**: 158,638 lines total (51,000 in core module)
- **Database Tables**: 255 (251 in repo_index.db, 4 in graphs.db)
- **Security Rules**: 200+ across 18 categories
- **CLI Commands**: 42 registered
- **Test Coverage**: 15-20% (CRITICAL - needs immediate improvement)
- **Documentation**: 65% coverage (missing CWE IDs in rules)
- **Quality Score**: 53/100 (F) - Immediate attention required

### Related Documentation
- `Architecture.md` - Complete system architecture and audit findings
- `quality_report.md` - Comprehensive code quality analysis
- `HowToUse.md` - Installation and usage guide
- `README.md` - Project overview

---

## CRITICAL ISSUES REQUIRING IMMEDIATE ATTENTION

### P0 - Security Vulnerabilities (Fix Immediately)
1. **SQL Injection via f-strings** - 4 locations in blueprint.py, query.py, base_database.py
2. **Command Injection (shell=True)** - 5 locations including cli.py, workset.py
3. **Weak Hash (MD5)** - Replace with SHA-256 in ast_parser.py, docs_fetch.py
4. **ZERO FALLBACK violations** - 10+ files returning empty instead of crashing

### P0 - Critical Gaps
1. **Test Coverage**: Only 6% of security rules have tests (5/83)
2. **Backup Files**: Delete `theauditor/taint/backup/` (2,590 lines of dead code)
3. **Taint Module**: Actually 4,280 lines, not ~2,000 as documented
4. **FCE Performance**: 8 separate DB connections causing 400-800ms overhead

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

## Major Engines and Their Status

### 1. Indexer Engine (`theauditor/indexer/`)
- **Status**: HEALTHY
- **Performance**: Good with batch optimizations
- **Issues**: FastAPI dependency extraction bug (checks annotations instead of defaults)
- **Extractors**: 12 language-specific (Python, JS/TS, Terraform, Docker, SQL, etc.)

### 2. Taint Analysis Engine (`theauditor/taint/`)
- **Status**: FUNCTIONAL with issues
- **Lines**: 4,280 (NOT ~2,000 as claimed)
- **Architecture**: 3-layer (Schema, Discovery, Analysis)
- **Issues**: 6+ ZERO FALLBACK violations, backup files need deletion
- **Missing**: Python-specific sinks (pickle.loads, yaml.load)

### 3. Rules Engine (`theauditor/rules/`)
- **Status**: CRITICAL - needs immediate attention
- **Rules**: 200+ across 18 categories
- **Test Coverage**: 6% (5/83 rules tested)
- **Issues**: 4 files violate ZERO FALLBACK policy
- **N+1 Queries**: 20+ rules with performance issues

### 4. Graph Engine (`theauditor/graph/`)
- **Status**: EXCELLENT
- **Performance**: 9/10
- **Features**: Cycle detection, hotspot analysis, visualization
- **Issues**: Missing aggregate query index

### 5. Context Query Engine (`theauditor/context/`)
- **Status**: GOOD
- **Performance**: <50ms for most queries
- **Issues**: No workset filtering, no VS Code integration

### 6. FCE Engine (`theauditor/fce.py`)
- **Status**: FUNCTIONAL but needs optimization
- **Issues**: 8 separate DB connections, 6+ ZERO FALLBACK violations
- **Test Coverage**: 0% (1,846 LOC untested)

### 7. CLI System (`theauditor/cli.py`)
- **Status**: WELL-DESIGNED
- **Commands**: 42 registered
- **Issues**: Emojis crash Windows, inconsistent --workset flag
- **Test Coverage**: 30% (29 commands untested)

---

## Performance Bottlenecks and Optimizations

### Critical Performance Issues
1. **FCE 8 DB connections**: 400-800ms overhead → Use connection pool (87% reduction)
2. **GraphQL N+1 queries**: 101 queries → Use JOIN (99% reduction)
3. **Missing indexes**: Add 5 composite indexes (10-100x speedup)
4. **LIKE '%...%' patterns**: No index use → Use exact matches (2-10x speedup)
5. **FlowResolver discovery**: O(n) queries → Bulk load (99% reduction)

**Total potential speedup**: 15-50% on large codebases

### Memory Usage
- Small projects: ~250MB peak
- Medium projects: ~600MB peak
- Large projects: ~2GB peak
- Monorepos: ~6GB peak

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
```

### Python Framework Extraction (Parity Work)

- **ORM models**: SQLAlchemy and Django definitions populate `python_orm_models`, `python_orm_fields`, and the shared `orm_relationships` table (bidirectional rows with cascade flags).
- **HTTP routes**: Flask blueprints/routes and FastAPI handlers land in `python_routes` (method, auth flag, dependency metadata) and `python_blueprints`.
- **Validation**: Pydantic decorators produce entries in `python_validators` with field vs root classification for sanitizer parity.
- **Import resolution**: Python imports are stored in the `refs` table with `.py` file paths as targets (no separate resolved_imports dict/table exists).
- **Verification**: Fixtures under `tests/fixtures/python/` pair with `pytest tests/test_python_framework_extraction.py` to guard regressions.

---

## Common CLI Commands

```bash
# Full analysis pipeline
aud full

# Query symbol information
aud context query --symbol function_name --show-callers

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

---

## Known Issues and Workarounds

### Windows-Specific Issues
1. **Emojis crash**: context.py uses emojis that crash CP1252 - needs ASCII replacement
2. **shell=True vulnerability**: Multiple subprocess calls use shell=True on Windows
3. **Path handling**: Always use full Windows paths with drive letters

### Database Issues
1. **Foreign keys not enforced**: PRAGMA foreign_keys = 0 by design
2. **Empty tables**: python_celery_task_calls, python_crypto_operations
3. **Unknown vulnerability types**: 1,134/1,135 flows unclassified

### Framework Extraction Issues
1. **FastAPI dependencies**: Bug in extractor checks annotations instead of defaults
2. **Missing extractors**: NestJS, Redux, Webpack configs not implemented
3. **TypeScript interfaces**: Intentionally excluded but needed

---

## Technical Debt Summary

| Category | Hours to Fix | Priority |
|----------|--------------|----------|
| Security vulnerabilities | 40 | P0 |
| Test coverage gaps | 200 | P0 |
| ZERO FALLBACK violations | 20 | P0 |
| Performance bottlenecks | 30 | P1 |
| Dead code removal | 10 | P2 |
| Documentation gaps | 80 | P2 |
| Type hints | 60 | P3 |
| Code duplication | 40 | P3 |
| **TOTAL** | **480 hours** | - |

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

---

## Immediate Action Items

1. **Fix SQL injection vulnerabilities** - Use parameterized queries
2. **Remove shell=True** - Security critical
3. **Delete backup files** - `theauditor/taint/backup/`
4. **Fix ZERO FALLBACK violations** - Let DB errors crash
5. **Add tests for security rules** - 78 rules need tests
6. **Implement connection pooling** - 20-30% speedup
7. **Add missing DB indexes** - 10-100x query speedup

---

**Last Comprehensive Audit**: 2025-11-22 by 15 parallel AI agents
**Next Audit Recommended**: After P0 fixes completed
**Confidence Level**: HIGH - Based on complete codebase analysis