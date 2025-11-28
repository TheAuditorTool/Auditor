## 0. Verification
- [ ] 0.1 Verify tree-sitter-bash is available via tree-sitter-language-pack
- [ ] 0.2 Document tree-sitter-bash node types available
- [ ] 0.3 Find shell scripts in TheAuditor repo to use as test cases
- [ ] 0.4 Identify common CI/CD script patterns (GitHub Actions, etc.)

## 1. Phase 1: Core Extraction

### 1.1 Schema Creation
- [ ] 1.1.1 Create `theauditor/schema/bash_schema.sql` with 8 tables
- [ ] 1.1.2 Add bash tables to schema registry
- [ ] 1.1.3 Add bash table creation to database initialization
- [ ] 1.1.4 Verify tables created on fresh `aud full --index`

### 1.2 File Detection
- [ ] 1.2.1 Add .sh and .bash to supported extensions
- [ ] 1.2.2 Implement shebang detection for extensionless files
- [ ] 1.2.3 Handle `#!/bin/bash`, `#!/usr/bin/env bash`, `#!/bin/sh`
- [ ] 1.2.4 Register BashExtractor in extractor registry

### 1.3 Function Extraction
- [ ] 1.3.1 Create `theauditor/indexer/extractors/bash.py` with BashExtractor
- [ ] 1.3.2 Extract `function name()` style definitions
- [ ] 1.3.3 Extract `name()` POSIX style definitions
- [ ] 1.3.4 Extract `function name` (no parens) bash style
- [ ] 1.3.5 Track function body line range

### 1.4 Variable Extraction
- [ ] 1.4.1 Extract simple assignments (`VAR=value`)
- [ ] 1.4.2 Extract exports (`export VAR=value`)
- [ ] 1.4.3 Extract local variables (`local var=value`)
- [ ] 1.4.4 Extract readonly declarations
- [ ] 1.4.5 Extract declare statements with flags
- [ ] 1.4.6 Track containing function for scope

### 1.5 Source Statement Extraction
- [ ] 1.5.1 Extract `source file.sh` statements
- [ ] 1.5.2 Extract `. file.sh` (dot) statements
- [ ] 1.5.3 Resolve relative paths where possible
- [ ] 1.5.4 Handle variable expansion in paths (`source "$DIR/lib.sh"`)

### 1.6 Command Extraction
- [ ] 1.6.1 Extract simple command invocations
- [ ] 1.6.2 Separate command name from arguments
- [ ] 1.6.3 Track which arguments contain variable expansion
- [ ] 1.6.4 Track quote context for each argument
- [ ] 1.6.5 Extract containing function context

### 1.7 Storage Layer
- [ ] 1.7.1 Create `theauditor/indexer/storage/bash_storage.py`
- [ ] 1.7.2 Implement store_bash_function()
- [ ] 1.7.3 Implement store_bash_variable()
- [ ] 1.7.4 Implement store_bash_source()
- [ ] 1.7.5 Implement store_bash_command() with args junction
- [ ] 1.7.6 Wire BashExtractor output to storage

### 1.8 Phase 1 Verification
- [ ] 1.8.1 Run `aud full --index` on TheAuditor repo
- [ ] 1.8.2 Verify bash_* tables populated
- [ ] 1.8.3 Query functions from a shell script
- [ ] 1.8.4 Query commands used in shell scripts

## 2. Phase 2: Data Flow

### 2.1 Pipe Extraction
- [ ] 2.1.1 Detect pipeline commands (`cmd1 | cmd2 | cmd3`)
- [ ] 2.1.2 Track order of commands in pipeline
- [ ] 2.1.3 Store in bash_pipes with left/right command refs
- [ ] 2.1.4 Handle pipefail context

### 2.2 Subshell Extraction
- [ ] 2.2.1 Extract command substitution `$(cmd)`
- [ ] 2.2.2 Extract backtick substitution `` `cmd` ``
- [ ] 2.2.3 Track assignment target when captured (`var=$(cmd)`)
- [ ] 2.2.4 Handle nested substitutions

### 2.3 Redirection Extraction
- [ ] 2.3.1 Extract output redirections (`>`, `>>`)
- [ ] 2.3.2 Extract input redirections (`<`)
- [ ] 2.3.3 Extract stderr redirections (`2>`, `2>&1`)
- [ ] 2.3.4 Extract here documents (`<<EOF`)
- [ ] 2.3.5 Extract here strings (`<<<`)

### 2.4 Control Flow
- [ ] 2.4.1 Extract if/then/else/fi blocks
- [ ] 2.4.2 Extract case statements
- [ ] 2.4.3 Extract for loops (both styles)
- [ ] 2.4.4 Extract while/until loops
- [ ] 2.4.5 Track loop variable assignments

## 3. Phase 3: Security Rules

### 3.1 Rule Infrastructure
- [ ] 3.1.1 Create `theauditor/rules/bash_security.py`
- [ ] 3.1.2 Define finding severity levels for bash
- [ ] 3.1.3 Create bash-specific finding category

### 3.2 Command Injection Rules
- [ ] 3.2.1 Detect `eval "$var"` patterns
- [ ] 3.2.2 Detect unquoted command substitution in eval
- [ ] 3.2.3 Detect variable as command name (`$cmd args`)
- [ ] 3.2.4 Detect backtick injection patterns
- [ ] 3.2.5 Flag xargs with -I and unvalidated input

### 3.3 Unquoted Variable Rules
- [ ] 3.3.1 Detect unquoted variable in command arguments
- [ ] 3.3.2 Detect unquoted variable in array index
- [ ] 3.3.3 Detect unquoted variable in test expressions
- [ ] 3.3.4 Allow unquoted in safe contexts (arithmetic)
- [ ] 3.3.5 Track quote nesting correctly

### 3.4 Dangerous Pattern Rules
- [ ] 3.4.1 Detect curl/wget piped to bash/sh
- [ ] 3.4.2 Detect hardcoded passwords/secrets in assignments
- [ ] 3.4.3 Detect predictable temp file names
- [ ] 3.4.4 Detect missing `set -e` / `set -u` / `set -o pipefail`
- [ ] 3.4.5 Detect sudo with variable command/arguments
- [ ] 3.4.6 Detect chmod 777 patterns
- [ ] 3.4.7 Detect use of MD5/SHA1 for security purposes

### 3.5 Path Safety Rules
- [ ] 3.5.1 Detect relative command paths without ./
- [ ] 3.5.2 Detect PATH manipulation patterns
- [ ] 3.5.3 Flag commands that should use absolute paths

## 4. Integration & Testing

### 4.1 Dogfooding
- [ ] 4.1.1 Run on TheAuditor's own shell scripts
- [ ] 4.1.2 Run on sample CI/CD configs (GitHub Actions runners)
- [ ] 4.1.3 Fix any false positives from our own scripts

### 4.2 Test Coverage
- [ ] 4.2.1 Unit tests for function extraction
- [ ] 4.2.2 Unit tests for variable extraction
- [ ] 4.2.3 Unit tests for quoting analysis
- [ ] 4.2.4 Unit tests for each security rule
- [ ] 4.2.5 Integration test with complex real-world script

### 4.3 Documentation
- [ ] 4.3.1 Update indexer spec with Bash capability
- [ ] 4.3.2 Document bash_* table schemas
- [ ] 4.3.3 Document security rule rationale
- [ ] 4.3.4 Add Bash examples to `aud context` help
