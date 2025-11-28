## Why

TheAuditor itself runs in shell. DevOps pipelines, CI/CD workflows, Docker entrypoints, deployment scripts - all Bash. Shell scripts are everywhere and notoriously insecure: command injection, unquoted variables, unsafe eval, hardcoded credentials. Yet they rarely get the same scrutiny as application code.

This is a quick win with high practical value. Bash is simple enough to extract accurately with tree-sitter, and the security patterns are well-understood.

## What Changes

**Phase 1: Core Extraction**
- Function definitions (`function name()` and `name()` styles)
- Variable assignments and exports
- Source statements (`. file.sh`, `source file.sh`)
- External command invocations
- Control flow (if/case/for/while)

**Phase 2: Data Flow**
- Pipe chains (track data flow through `|`)
- Subshell captures (`$(...)`, backticks)
- Here documents
- Redirections (`>`, `>>`, `<`, `2>&1`)

**Phase 3: Security Rules**
- Command injection (eval, unquoted expansion in commands)
- Unquoted variables (word splitting vulnerabilities)
- Unsafe curl-pipe-bash patterns
- Hardcoded credentials detection
- Missing safety flags (`set -euo pipefail`)
- Unsafe temp file creation
- Sudo with user-controlled arguments

## Impact

- Affected specs: `indexer` (new language support)
- Affected code:
  - `theauditor/indexer/extractors/bash.py` - New extractor (auto-discovered via ExtractorRegistry)
  - `theauditor/ast_extractors/bash_impl.py` - New tree-sitter extraction implementation
  - `theauditor/indexer/schemas/bash_schema.py` - New schema module with 8 TableSchema definitions
  - `theauditor/indexer/schema.py:15-24` - Add BASH_TABLES import to unified TABLES dict
  - `theauditor/indexer/storage/bash_storage.py` - New storage handlers
  - `theauditor/rules/bash/__init__.py` - New rules subdirectory (pattern: rules/python/, rules/security/)
- Breaking changes: None (new capability)
- Dependencies: tree-sitter-bash (via tree-sitter-language-pack, already installed)
- Estimated effort: 8-12 hours total
- Dogfooding: Can immediately run on TheAuditor's own shell scripts
