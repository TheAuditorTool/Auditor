## 0. Verification
- [ ] 0.1 Verify tree-sitter-bash is available via tree-sitter-language-pack (DONE: confirmed available)
- [ ] 0.2 Find shell scripts in TheAuditor repo to use as test cases
- [ ] 0.3 Identify common CI/CD script patterns (GitHub Actions, etc.)

## 1. Phase 1: Core Extraction

### 1.1 Schema Creation
- [ ] 1.1.1 Create `theauditor/indexer/schemas/bash_schema.py` with 8 TableSchema definitions
- [ ] 1.1.2 Add `from .bash_schema import BASH_TABLES` to `theauditor/indexer/schema.py:5-11`
- [ ] 1.1.3 Add `**BASH_TABLES` to TABLES dict in `theauditor/indexer/schema.py:15-24`
- [ ] 1.1.4 Update table count assertion in `theauditor/indexer/schema.py:27` (170 -> 178)
- [ ] 1.1.5 Verify tables created on fresh `aud full --index`

### 1.2 File Detection
- [ ] 1.2.1 Add .sh and .bash to BashExtractor.supported_extensions()
- [ ] 1.2.2 Implement shebang detection in file iterator (see design.md Decision 10)
- [ ] 1.2.3 Handle `#!/bin/bash`, `#!/usr/bin/env bash`, `#!/bin/sh` shebangs
- [ ] 1.2.4 NOTE: BashExtractor auto-discovered by ExtractorRegistry (no manual registration)

### 1.3 Extractor Implementation
- [ ] 1.3.1 Create `theauditor/indexer/extractors/bash.py` with BashExtractor class
- [ ] 1.3.2 Create `theauditor/ast_extractors/bash_impl.py` with tree-sitter extraction logic
- [ ] 1.3.3 Extract `function name()` style (tree-sitter: function_definition with `function` keyword)
- [ ] 1.3.4 Extract `name()` POSIX style (tree-sitter: function_definition without keyword)
- [ ] 1.3.5 Extract `function name` no-parens style (tree-sitter: function_definition variant)
- [ ] 1.3.6 Track function body line range from node.start_point/end_point

### 1.4 Variable Extraction
- [ ] 1.4.1 Extract simple assignments (tree-sitter: variable_assignment)
- [ ] 1.4.2 Extract exports (tree-sitter: declaration_command with 'export')
- [ ] 1.4.3 Extract local variables (tree-sitter: declaration_command with 'local')
- [ ] 1.4.4 Extract readonly declarations (tree-sitter: declaration_command with 'readonly')
- [ ] 1.4.5 Extract declare statements with flags (tree-sitter: declaration_command with 'declare')
- [ ] 1.4.6 Track containing function via scope_stack during tree walk

### 1.5 Source Statement Extraction
- [ ] 1.5.1 Extract `source file.sh` (tree-sitter: command with name='source')
- [ ] 1.5.2 Extract `. file.sh` (tree-sitter: command with name='.')
- [ ] 1.5.3 Resolve relative paths using os.path.join with script directory
- [ ] 1.5.4 Detect variable expansion in paths via expansion node children

### 1.6 Command Extraction
- [ ] 1.6.1 Extract command invocations (tree-sitter: command, simple_command)
- [ ] 1.6.2 Separate command name (first child) from arguments (subsequent children)
- [ ] 1.6.3 Track variable expansion via expansion/simple_expansion nodes
- [ ] 1.6.4 Track quote context via string/raw_string parent nodes
- [ ] 1.6.5 Track containing function via scope_stack

### 1.7 Storage Layer
- [ ] 1.7.1 Create `theauditor/indexer/storage/bash_storage.py` extending BaseStorage
- [ ] 1.7.2 Add handlers dict mapping data keys to store methods (pattern: python_storage.py:14-44)
- [ ] 1.7.3 Implement _store_bash_functions() calling db_manager.add_bash_function()
- [ ] 1.7.4 Implement _store_bash_variables() calling db_manager.add_bash_variable()
- [ ] 1.7.5 Implement _store_bash_sources() calling db_manager.add_bash_source()
- [ ] 1.7.6 Implement _store_bash_commands() with args junction table handling
- [ ] 1.7.7 Wire BashStorage in orchestrator (theauditor/indexer/orchestrator.py)

### 1.8 Database Manager Methods
- [ ] 1.8.1 Add add_bash_function() to database manager (pattern: base_database.py)
- [ ] 1.8.2 Add add_bash_variable() to database manager
- [ ] 1.8.3 Add add_bash_source() to database manager
- [ ] 1.8.4 Add add_bash_command() to database manager
- [ ] 1.8.5 Add add_bash_command_arg() to database manager

### 1.9 Phase 1 Verification
- [ ] 1.9.1 Run `aud full --index` on TheAuditor repo
- [ ] 1.9.2 Verify bash_* tables exist in .pf/repo_index.db
- [ ] 1.9.3 Query functions: `SELECT * FROM bash_functions LIMIT 5`
- [ ] 1.9.4 Query commands: `SELECT * FROM bash_commands LIMIT 5`

## 2. Phase 2: Data Flow

### 2.1 Pipe Extraction
- [ ] 2.1.1 Detect pipelines (tree-sitter: pipeline node)
- [ ] 2.1.2 Track order via child index in pipeline node
- [ ] 2.1.3 Store in bash_pipes with position column
- [ ] 2.1.4 Handle pipefail context via parent compound_statement

### 2.2 Subshell Extraction
- [ ] 2.2.1 Extract command substitution (tree-sitter: command_substitution `$(...)`)
- [ ] 2.2.2 Extract backtick substitution (tree-sitter: command_substitution with backtick)
- [ ] 2.2.3 Track assignment target via parent variable_assignment node
- [ ] 2.2.4 Handle nested substitutions via recursive walk

### 2.3 Redirection Extraction
- [ ] 2.3.1 Extract output redirections (tree-sitter: file_redirect with `>` or `>>`)
- [ ] 2.3.2 Extract input redirections (tree-sitter: file_redirect with `<`)
- [ ] 2.3.3 Extract stderr redirections (tree-sitter: file_redirect with fd_number)
- [ ] 2.3.4 Extract here documents (tree-sitter: heredoc_redirect)
- [ ] 2.3.5 Extract here strings (tree-sitter: herestring_redirect)

### 2.4 Control Flow
- [ ] 2.4.1 Extract if statements (tree-sitter: if_statement)
- [ ] 2.4.2 Extract case statements (tree-sitter: case_statement)
- [ ] 2.4.3 Extract for loops (tree-sitter: for_statement, c_style_for_statement)
- [ ] 2.4.4 Extract while/until loops (tree-sitter: while_statement)
- [ ] 2.4.5 Track loop variable from for_statement variable child

## 3. Phase 3: Security Rules

### 3.1 Rule Infrastructure
- [ ] 3.1.1 Create `theauditor/rules/bash/__init__.py` (pattern: rules/python/__init__.py)
- [ ] 3.1.2 Create `theauditor/rules/bash/injection_analyze.py` for command injection
- [ ] 3.1.3 Create `theauditor/rules/bash/quoting_analyze.py` for unquoted variables
- [ ] 3.1.4 Register bash rules in orchestrator (theauditor/rules/orchestrator.py)

### 3.2 Command Injection Rules
- [ ] 3.2.1 Detect `eval "$var"` patterns via bash_commands + bash_command_args join
- [ ] 3.2.2 Detect unquoted command substitution in eval
- [ ] 3.2.3 Detect variable as command name via bash_commands.command_name starting with $
- [ ] 3.2.4 Detect backtick injection via bash_subshells.syntax='backtick'
- [ ] 3.2.5 Flag xargs with -I and unvalidated input

### 3.3 Unquoted Variable Rules
- [ ] 3.3.1 Query bash_command_args WHERE is_quoted=FALSE AND has_expansion=TRUE
- [ ] 3.3.2 Detect unquoted variable in array index
- [ ] 3.3.3 Detect unquoted variable in test expressions ([[ ]] without quotes)
- [ ] 3.3.4 Whitelist arithmetic contexts ($(())) as safe
- [ ] 3.3.5 Handle quote nesting via quote_type column

### 3.4 Dangerous Pattern Rules
- [ ] 3.4.1 Detect curl/wget piped to bash: join bash_pipes on pipeline_id
- [ ] 3.4.2 Detect hardcoded secrets: bash_variables WHERE name matches credential patterns
- [ ] 3.4.3 Detect predictable temp: bash_redirections WHERE target LIKE '/tmp/%'
- [ ] 3.4.4 Detect missing safety flags: check for 'set' commands with -e/-u/-o pipefail
- [ ] 3.4.5 Detect sudo abuse: bash_commands WHERE command_name='sudo' with variable args
- [ ] 3.4.6 Detect chmod 777: bash_commands WHERE command_name='chmod' AND args contain '777'
- [ ] 3.4.7 Detect MD5/SHA1: bash_commands WHERE command_name IN ('md5sum', 'sha1sum')

### 3.5 Path Safety Rules
- [ ] 3.5.1 Detect relative command paths: command_name without / or ./
- [ ] 3.5.2 Detect PATH manipulation: bash_variables WHERE name='PATH'
- [ ] 3.5.3 Flag security-sensitive commands that should use absolute paths

## 4. Integration & Testing

### 4.1 Dogfooding
- [ ] 4.1.1 Run on TheAuditor's own shell scripts in repo
- [ ] 4.1.2 Run on sample CI/CD configs (GitHub Actions run scripts)
- [ ] 4.1.3 Tune rules to eliminate false positives

### 4.2 Test Coverage
- [ ] 4.2.1 Unit tests for function extraction in tests/indexer/test_bash_extractor.py
- [ ] 4.2.2 Unit tests for variable extraction
- [ ] 4.2.3 Unit tests for quoting analysis
- [ ] 4.2.4 Unit tests for each security rule in tests/rules/test_bash_rules.py
- [ ] 4.2.5 Integration test with complex real-world script

### 4.3 Documentation
- [ ] 4.3.1 Update indexer spec via OpenSpec archive
- [ ] 4.3.2 Document bash_* table schemas in design.md (DONE in this proposal)
- [ ] 4.3.3 Document security rule rationale in rules/bash/README.md
- [ ] 4.3.4 Add Bash examples to `aud context --help`
