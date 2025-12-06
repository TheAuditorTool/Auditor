# TheAuditor AST Extractors (Polyglot Parsing)

## Overview

A **multi-language AST extraction system** handling 7+ programming languages through:
1. **Tree-sitter** - for Go, Rust, Bash, HCL (Terraform)
2. **TypeScript Compiler API** - for JavaScript/TypeScript (via Node.js bundle)
3. **Python built-in `ast` module** - for Python (no external deps)

**Zero Fallback Policy**: If a parser fails, it fails hard—no silent data loss.

---

## Language Support Matrix

| Language | Parser | Module | Status |
|----------|--------|--------|--------|
| **Python** | Built-in `ast` | `python_impl.py` | PRODUCTION (1005 lines) |
| **JavaScript** | TypeScript Compiler API | `js_semantic_parser.py` | PRODUCTION |
| **TypeScript** | TypeScript Compiler API | `js_semantic_parser.py` | PRODUCTION |
| **Go** | Tree-sitter | `go_impl.py` | PRODUCTION (1372 lines) |
| **Rust** | Tree-sitter | `rust_impl.py` | PRODUCTION (800+ lines) |
| **Bash** | Tree-sitter | `bash_impl.py` | PRODUCTION (1053 lines) |
| **HCL/Terraform** | Tree-sitter | `hcl_impl.py` | LIMITED |

---

## Language-Specific Extractors

### Python (`python_impl.py`)

**47 data categories** including:
- Core: imports, symbols, assignments, function_calls, returns
- Advanced: async/await, comprehensions, lambda, decorators
- Framework: Django models/views, Flask routes, Celery tasks
- Security: SQL injection, command injection, JWT, crypto
- Type system: protocols, generics, TypedDict

**25+ specialized modules** in `python/` subdirectory.

### JavaScript/TypeScript (`js_semantic_parser.py`)

**Architecture**: Python wrapper around Node.js bundle

**Bundle**: `javascript/dist/extractor.cjs` (10MB compiled)
- Source: TypeScript in `javascript/src/`
- Handles JSX/TSX with configurable modes
- Extracts type information via TypeScript API
- Supports tsconfig.json path resolution

**Build**:
```bash
cd theauditor/ast_extractors/javascript
npm install && npm run build
```

### Go (`go_impl.py`)

**Features**:
- Structs and interfaces with generics
- Goroutines with captured variable tracking
- **Race condition detection** for loop variables in goroutines
- Defer statements, type assertions, error returns

### Rust (`rust_impl.py`)

**Extracts**:
- Modules (with inline declaration_lists)
- Structs, enums, unions, traits
- Unsafe blocks, extern blocks
- Generic types and where clauses
- Macro definitions and invocations

### Bash (`bash_impl.py`)

**Features**:
- Function definitions (POSIX vs bash style)
- Variable assignments (local/global/exported/readonly)
- Pipelines with position tracking
- Heredoc quoting detection
- Wrapper command detection (sudo, time, env)

---

## Unified Output Format

All extractors return standardized dict:
```python
{
    "type": "semantic_ast" | "python_ast" | "tree_sitter",
    "tree": <parsed AST>,
    "language": <language_name>,
    "content": <file_content>,
    "has_types": bool,      # JS/TS only
    "diagnostics": list,    # JS/TS only
}
```

---

## Key Design Patterns

1. **Lazy Initialization**: Tree-sitter grammars loaded on-demand
2. **Content Hashing**: Python AST cached by MD5 hash
3. **Batch Optimization**: JS/TS files processed in single Node.js invocation
4. **Error Context**: ParseError includes file path and line number
5. **Monorepo Support**: tsconfig discovery walks up directory tree

---

## Zero Fallback in Action

```python
# Python
try:
    return ast.parse(content)
except SyntaxError as e:
    raise ParseError(f"Python syntax error: {e.msg}", file=file_path, line=e.lineno) from e

# JS/TS
if not semantic_result.get("success"):
    raise RuntimeError(
        f"FATAL: TypeScript semantic parser failed for {file_path}\n"
        f"NO FALLBACKS ALLOWED - fix the error or exclude the file."
    )
```
