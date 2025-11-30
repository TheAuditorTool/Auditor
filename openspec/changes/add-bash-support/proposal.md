## Why

TheAuditor itself runs in shell. DevOps pipelines, CI/CD workflows, Docker entrypoints, deployment scripts - all Bash. Shell scripts are everywhere and notoriously insecure: command injection, unquoted variables, unsafe eval, hardcoded credentials. Yet they rarely get the same scrutiny as application code.

This is a quick win with high practical value. Bash is simple enough to extract accurately with tree-sitter, and the security patterns are well-understood.

## What Changes

> **Specs**: This proposal is governed by two specifications:
> - `specs/indexer/spec.md` - Schema, extraction, storage requirements
> - `specs/graph/spec.md` - Graph strategies, taint, rules wiring

**Phase 1: Core Extraction** (see `specs/indexer/spec.md`)
- Function definitions (`function name()` and `name()` styles)
- Variable assignments and exports
- Source statements (`. file.sh`, `source file.sh`)
- External command invocations
- Control flow (if/case/for/while)

**Phase 2: Data Flow** (see `specs/indexer/spec.md` + `specs/graph/spec.md`)
- Pipe chains (track data flow through `|`)
- Subshell captures (`$(...)`, backticks)
- Here documents
- Redirections (`>`, `>>`, `<`, `2>&1`)
- **Graph strategy for pipe/source edges** (see `design.md` Decision 14)

**Phase 3: Security Rules** (see `specs/graph/spec.md`)
- Command injection (eval, unquoted expansion in commands)
- Unquoted variables (word splitting vulnerabilities)
- Unsafe curl-pipe-bash patterns
- Hardcoded credentials detection
- Missing safety flags (`set -euo pipefail`)
- Unsafe temp file creation
- Sudo with user-controlled arguments
- **Taint source/sink configuration** (see `design.md` Decision 16)

## Impact

- **Affected specs**:
  - `indexer` - New language support (8 tables)
  - `graph` - New strategy for Bash data flow (NEW)

- **Affected code** (Phase 1 - Indexer Layer):
  - `theauditor/indexer/schemas/bash_schema.py` - NEW: 8 TableSchema definitions
  - `theauditor/indexer/schema.py:5-11` - Add BASH_TABLES import
  - `theauditor/indexer/schema.py:15-24` - Add `**BASH_TABLES` to TABLES dict
  - `theauditor/indexer/schema.py:27` - Update assertion `170 -> 178`
  - `theauditor/indexer/extractors/bash.py` - NEW: BashExtractor class
  - `theauditor/ast_extractors/bash_impl.py` - NEW: tree-sitter extraction
  - `theauditor/indexer/storage/bash_storage.py` - NEW: storage handlers
  - `theauditor/indexer/storage/__init__.py:6-30` - Wire BashStorage into DataStorer
  - `theauditor/indexer/database/bash_database.py` - NEW: BashDatabaseMixin
  - `theauditor/indexer/database/__init__.py:17-27` - Add mixin to DatabaseManager
  - `theauditor/indexer/database/base_database.py:193-332` - Add bash_* to flush_order
  - `theauditor/indexer/core.py:125-150` - Add shebang detection in FileWalker

- **Affected code** (Phase 2 - Graph Layer):
  - `theauditor/graph/strategies/bash_pipes.py` - NEW: BashPipeStrategy
  - `theauditor/graph/strategies/__init__.py` - Export BashPipeStrategy
  - `theauditor/graph/dfg_builder.py:11-14` - Import BashPipeStrategy
  - `theauditor/graph/dfg_builder.py:27-32` - Add to strategies list

- **Affected code** (Phase 3 - Rules Layer):
  - `theauditor/rules/bash/__init__.py` - NEW: Rules module
  - `theauditor/rules/bash/injection_analyze.py` - NEW: Command injection rules
  - `theauditor/rules/bash/quoting_analyze.py` - NEW: Unquoted variable rules
  - `theauditor/rules/bash/dangerous_patterns_analyze.py` - NEW: curl-pipe-bash, secrets, etc.

- **Breaking changes**: None (new capability, additive only)
- **Dependencies**: tree-sitter-bash (via tree-sitter-language-pack, already installed)
- **Estimated effort**:
  - Phase 1: 4-6 hours
  - Phase 2: 3-4 hours
  - Phase 3: 4-6 hours
  - Total: 11-16 hours

- **Dogfooding**: Can immediately run on TheAuditor's own shell scripts (limited - mostly in node_modules)

## Architectural Notes

### Polyglot Pattern Compliance

This implementation follows existing polyglot patterns:

| Component | Python Pattern | Node Pattern | Bash Pattern (NEW) |
|-----------|---------------|--------------|-------------------|
| Schema | `python_schema.py` | `node_schema.py` | `bash_schema.py` |
| Storage | `python_storage.py` | `node_storage.py` | `bash_storage.py` |
| Database | `python_database.py` | `node_database.py` | `bash_database.py` |
| Extractor | `python.py` | `javascript.py` | `bash.py` |
| AST Impl | `python_impl.py` | `typescript_impl.py` | `bash_impl.py` |
| Graph Strategy | `python_orm.py` | `node_orm.py` | `bash_pipes.py` |
| Rules | `rules/python/` | `rules/node/` | `rules/bash/` |

### Separation of Concerns

Each layer has specific responsibilities:

1. **Schema Layer** (`schemas/bash_schema.py`): Table definitions only
2. **Extractor Layer** (`extractors/bash.py` + `ast_extractors/bash_impl.py`): Parse and extract
3. **Storage Layer** (`storage/bash_storage.py`): Route extracted data to DB methods
4. **Database Layer** (`database/bash_database.py`): Batch insertion methods
5. **Graph Layer** (`graph/strategies/bash_pipes.py`): Build data flow edges
6. **Rules Layer** (`rules/bash/`): Security analysis queries
