# Implementation Tasks: Logging Migration to Loguru (Polyglot)

**IMPORTANT**: READ `specs/logging/spec.md` before implementing EACH language phase.

---

## 0. Verification (MUST COMPLETE BEFORE IMPLEMENTATION)

- [ ] 0.1 Verify `theauditor/utils/logger.py` exists and has ~24 lines
- [ ] 0.2 Count Python print statements: `grep -r "print.*\[" theauditor/ | wc -l` (expect ~323)
- [ ] 0.3 Count Python files with prints: `grep -rl "print.*\[" theauditor/ | wc -l` (expect ~51)
- [ ] 0.4 Count TypeScript console statements: `grep -r "console\." javascript/src/ | wc -l` (expect ~18)
- [ ] 0.5 Verify `theauditor/pipeline/renderer.py` exists (must NOT modify)
- [ ] 0.6 Verify `theauditor/pipeline/ui.py` exists (must NOT modify)
- [ ] 0.7 Run `aud full --index` and capture baseline output for comparison
- [ ] 0.8 Verify libcst is available or can be installed

---

## PHASE 1: Python Infrastructure Setup

**READ**: specs/logging/spec.md "Python Requirements" before starting.

### 1.1 Add Dependencies

- [ ] 1.1.1 Add `loguru>=0.7.0` to `pyproject.toml` dependencies
- [ ] 1.1.2 Add `libcst>=1.0.0` to `pyproject.toml` dev dependencies
- [ ] 1.1.3 Run `pip install -e ".[dev]"` to install dependencies

### 1.2 Create Python Logger Configuration

- [ ] 1.2.1 Create `theauditor/utils/logging.py`:

```python
"""Centralized logging configuration using Loguru.

Usage:
    from theauditor.utils.logging import logger
    logger.info("Message")
    logger.debug("Debug message")  # Only shows if THEAUDITOR_LOG_LEVEL=DEBUG

Environment Variables:
    THEAUDITOR_LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default: INFO)
    THEAUDITOR_LOG_JSON: 0|1 (default: 0, human-readable)
    THEAUDITOR_LOG_FILE: path to log file (optional)
"""
import os
import sys
from pathlib import Path

from loguru import logger

# Remove default handler
logger.remove()

# Get configuration from environment
_log_level = os.environ.get("THEAUDITOR_LOG_LEVEL", "INFO").upper()
_json_mode = os.environ.get("THEAUDITOR_LOG_JSON", "0") == "1"
_log_file = os.environ.get("THEAUDITOR_LOG_FILE")

# Human-readable format (no emojis - Windows CP1252 compatibility)
_human_format = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# Console handler
if _json_mode:
    logger.add(
        sys.stderr,
        level=_log_level,
        serialize=True,  # JSON output
        colorize=False,
    )
else:
    logger.add(
        sys.stderr,
        level=_log_level,
        format=_human_format,
        colorize=True,
    )

# Optional file handler
if _log_file:
    logger.add(
        _log_file,
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",  # File always captures everything
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        serialize=_json_mode,
    )


def configure_file_logging(log_dir: Path, level: str = "DEBUG") -> None:
    """Add rotating file handler for persistent logs.

    Args:
        log_dir: Directory for log files (e.g., Path(".pf"))
        level: Minimum log level for file output
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "theauditor.log",
        rotation="10 MB",
        retention="7 days",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


__all__ = ["logger", "configure_file_logging"]
```

- [ ] 1.2.2 Verify: `python -c "from theauditor.utils.logging import logger; logger.info('test')"` works

---

## PHASE 2: LibCST Codemod Development

### 2.1 Setup LibCST

- [ ] 2.1.1 Create directory: `mkdir -p scripts/codemods`
- [ ] 2.1.2 Create `scripts/codemods/__init__.py` (empty file)
- [ ] 2.1.3 Initialize LibCST: `python -m libcst.tool initialize .`
- [ ] 2.1.4 Create `.libcst.codemod.yaml` in repository root:

```yaml
# LibCST Codemod Configuration
modules:
  - scripts.codemods

# Exclude generated files
blacklist_patterns:
  - "*/node_modules/*"
  - "*/.venv/*"
  - "*/dist/*"
  - "*/__pycache__/*"
```

### 2.2 Create Codemod

- [ ] 2.2.1 Create `scripts/codemods/print_to_loguru.py` with the following implementation:

```python
"""LibCST codemod: Convert print('[TAG]...') to loguru logger calls.

Usage:
    # Dry run (show diff)
    python -m libcst.tool codemod scripts.codemods.print_to_loguru.PrintToLoguruCodemod \
        --no-format theauditor/

    # Apply changes
    python -m libcst.tool codemod scripts.codemods.print_to_loguru.PrintToLoguruCodemod \
        theauditor/
"""
from __future__ import annotations

from typing import Sequence, Union

import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor


class PrintToLoguruCodemod(VisitorBasedCodemodCommand):
    """Convert print('[TAG]...') statements to loguru logger calls."""

    DESCRIPTION = "Convert print('[TAG]...') statements to loguru logger calls"

    # Map [TAG] prefixes to log levels
    TAG_TO_LEVEL: dict[str, str] = {
        # Debug level
        "[DEBUG]": "debug",
        "[TRACE]": "trace",
        "[INDEXER_DEBUG]": "debug",
        "[DEDUP]": "debug",
        "[SCHEMA]": "debug",
        # Info level
        "[INFO]": "info",
        "[Indexer]": "info",
        "[TAINT]": "info",
        "[FCE]": "info",
        "[GRAPH]": "info",
        "[RULES]": "info",
        # Warning level
        "[WARNING]": "warning",
        "[WARN]": "warning",
        # Error level
        "[ERROR]": "error",
        # Critical level
        "[CRITICAL]": "critical",
        "[FATAL]": "critical",
    }

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.needs_logger_import = False
        self.in_debug_guard = False

    def _get_level_and_clean_text(self, text: str) -> tuple[str, str]:
        """Extract log level from [TAG] prefix and return (level, cleaned_text)."""
        for tag, level in self.TAG_TO_LEVEL.items():
            if tag in text:
                cleaned = text.replace(tag, "").lstrip()
                return level, cleaned
        return "info", text  # Default to info for untagged

    def _has_tag(self, node: cst.BaseExpression) -> bool:
        """Check if expression contains a recognized tag."""
        if isinstance(node, cst.FormattedString):
            for part in node.parts:
                if isinstance(part, cst.FormattedStringText):
                    for tag in self.TAG_TO_LEVEL:
                        if tag in part.value:
                            return True
        elif isinstance(node, cst.SimpleString):
            for tag in self.TAG_TO_LEVEL:
                if tag in node.value:
                    return True
        elif isinstance(node, cst.ConcatenatedString):
            for part in node.left, node.right:
                if self._has_tag(part):
                    return True
        return False

    def _is_debug_guard(self, node: cst.If) -> bool:
        """Check if this is: if os.environ.get('THEAUDITOR_DEBUG'):"""
        return m.matches(
            node.test,
            m.Call(
                func=m.Attribute(
                    value=m.Attribute(value=m.Name("os"), attr=m.Name("environ")),
                    attr=m.Name("get"),
                ),
                args=[
                    m.Arg(
                        value=m.OneOf(
                            m.SimpleString('"THEAUDITOR_DEBUG"'),
                            m.SimpleString("'THEAUDITOR_DEBUG'"),
                        )
                    )
                ],
            ),
        )

    def visit_If(self, node: cst.If) -> bool:
        """Track when we enter a debug guard."""
        if self._is_debug_guard(node):
            self.in_debug_guard = True
        return True

    def leave_If(
        self, original_node: cst.If, updated_node: cst.If
    ) -> Union[cst.If, cst.RemovalSentinel, cst.FlattenSentinel[cst.BaseStatement]]:
        """Remove debug guards, convert inner prints to logger.debug()."""
        if not self._is_debug_guard(original_node):
            return updated_node

        self.in_debug_guard = False

        # Extract statements from the if body
        new_statements: list[cst.BaseStatement] = []
        body = updated_node.body
        if isinstance(body, cst.IndentedBlock):
            for stmt in body.body:
                # Convert print to logger.debug
                if m.matches(
                    stmt,
                    m.SimpleStatementLine(
                        body=[m.Expr(value=m.Call(func=m.Name("print")))]
                    ),
                ):
                    expr = stmt.body[0]
                    if isinstance(expr, cst.Expr) and isinstance(expr.value, cst.Call):
                        logger_call = self._convert_print_to_logger(
                            expr.value, force_level="debug"
                        )
                        if logger_call:
                            new_statements.append(
                                cst.SimpleStatementLine(body=[cst.Expr(value=logger_call)])
                            )
                            continue
                new_statements.append(stmt)

        if not new_statements:
            return cst.RemovalSentinel.REMOVE

        return cst.FlattenSentinel(new_statements)

    def _convert_print_to_logger(
        self, node: cst.Call, force_level: str | None = None
    ) -> cst.Call | None:
        """Convert a print() call to logger.level() call."""
        if not node.args:
            return None

        first_arg = node.args[0].value
        level = force_level or "info"

        # Handle FormattedString (f-string)
        if isinstance(first_arg, cst.FormattedString):
            new_parts: list[cst.BaseFormattedStringContent] = []
            tag_removed = False

            for part in first_arg.parts:
                if isinstance(part, cst.FormattedStringText) and not tag_removed:
                    new_value = part.value
                    for tag in self.TAG_TO_LEVEL:
                        if tag in new_value:
                            if not force_level:
                                level = self.TAG_TO_LEVEL[tag]
                            new_value = new_value.replace(tag, "").lstrip()
                            tag_removed = True
                            break
                    if new_value:
                        new_parts.append(part.with_changes(value=new_value))
                else:
                    new_parts.append(part)

            if not new_parts:
                return None

            new_arg = first_arg.with_changes(parts=new_parts)

        # Handle SimpleString
        elif isinstance(first_arg, cst.SimpleString):
            text = first_arg.value
            quote_char = text[0]
            inner = text[1:-1]
            for tag in self.TAG_TO_LEVEL:
                if tag in inner:
                    if not force_level:
                        level = self.TAG_TO_LEVEL[tag]
                    inner = inner.replace(tag, "").lstrip()
                    break
            if not inner:
                return None
            new_arg = cst.SimpleString(value=f"{quote_char}{inner}{quote_char}")

        else:
            # Other expression types - keep as-is
            new_arg = first_arg

        self.needs_logger_import = True

        return cst.Call(
            func=cst.Attribute(value=cst.Name("logger"), attr=cst.Name(level)),
            args=[cst.Arg(value=new_arg)],
        )

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.Call:
        """Transform print() calls to logger calls."""
        # Only transform print() calls
        if not m.matches(updated_node.func, m.Name("print")):
            return updated_node

        # Skip if inside debug guard (handled by leave_If)
        if self.in_debug_guard:
            return updated_node

        # Skip print() with no arguments
        if not updated_node.args:
            return updated_node

        # Only transform if has a recognized tag
        first_arg = updated_node.args[0].value
        if not self._has_tag(first_arg):
            return updated_node

        result = self._convert_print_to_logger(updated_node)
        return result if result else updated_node

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        """Add loguru import if any transformations occurred."""
        if self.needs_logger_import:
            AddImportsVisitor.add_needed_import(
                self.context, "theauditor.utils.logging", "logger"
            )
        return updated_node
```

- [ ] 2.2.2 Verify all tag-to-level mappings match design.md Decision 4
- [ ] 2.2.3 Verify debug guard removal pattern handles `if os.environ.get("THEAUDITOR_DEBUG"):`
- [ ] 2.2.4 Note: `file=sys.stderr` is automatically dropped when converting to logger (logger always goes to stderr)

### 2.3 Create Codemod Tests

- [ ] 2.3.1 Create `scripts/codemods/test_print_to_loguru.py`
- [ ] 2.3.2 Test: tagged f-string to logger
- [ ] 2.3.3 Test: tagged print with stderr
- [ ] 2.3.4 Test: debug guard removal
- [ ] 2.3.5 Test: untagged print unchanged
- [ ] 2.3.6 Test: multiple tags in file
- [ ] 2.3.7 Run tests: `python -m pytest scripts/codemods/test_print_to_loguru.py -v`

---

## PHASE 3: Python Codemod Dry Run

### 3.1 Single File Test

- [ ] 3.1.1 Dry run on `theauditor/taint/core.py` (has many prints):
```bash
python -m libcst.tool codemod scripts.codemods.print_to_loguru.PrintToLoguruCodemod \
    --no-format \
    theauditor/taint/core.py
```
- [ ] 3.1.2 Review the diff output
- [ ] 3.1.3 Verify tag-to-level mapping is correct
- [ ] 3.1.4 Verify imports are added correctly

### 3.2 Full Dry Run

- [ ] 3.2.1 Dry run on all theauditor files:
```bash
python -m libcst.tool codemod scripts.codemods.print_to_loguru.PrintToLoguruCodemod \
    --no-format \
    theauditor/
```
- [ ] 3.2.2 Review full diff
- [ ] 3.2.3 Note any edge cases not handled
- [ ] 3.2.4 Fix codemod if needed, re-run tests

---

## PHASE 4: Python Codemod Application

### 4.1 Apply Transformation

- [ ] 4.1.1 Apply codemod to all files:
```bash
python -m libcst.tool codemod scripts.codemods.print_to_loguru.PrintToLoguruCodemod \
    theauditor/
```

### 4.2 Post-Transform Cleanup

- [ ] 4.2.1 Run ruff to fix formatting:
```bash
ruff check --fix theauditor/
ruff format theauditor/
```
- [ ] 4.2.2 Verify transformation count:
```bash
# Should be 0 or near-0 (only untagged prints remain)
grep -r "print.*\[" theauditor/ | wc -l
```
- [ ] 4.2.3 Verify imports added correctly:
```bash
grep -r "from theauditor.utils.logging import logger" theauditor/ | wc -l
```

---

## PHASE 5: Python Cleanup

### 5.1 Remove Old Logger

- [ ] 5.1.1 Delete old logger.py: `rm theauditor/utils/logger.py`
- [ ] 5.1.2 Update any remaining imports of old logger:
```bash
# Find files still importing from old location
grep -r "from theauditor.utils.logger import" theauditor/
# Replace with new import
```

### 5.2 Update Old Logger References (21 files)

The following files use `setup_logger` and need import migration:

**theauditor/commands/** (8 files):
- [ ] 5.2.1 `cdk.py` - lines 12, 14
- [ ] 5.2.2 `cfg.py` - lines 8, 10
- [ ] 5.2.3 `graphql.py` - lines 8, 10
- [ ] 5.2.4 `workflows.py` - lines 15, 17
- [ ] 5.2.5 `planning.py` - lines 13, 15
- [ ] 5.2.6 `metadata.py` - lines 5, 7
- [ ] 5.2.7 `lint.py` - lines 12, 14
- [ ] 5.2.8 `terraform.py` - lines 12, 14

**theauditor/utils/** (3 files):
- [ ] 5.2.9 `memory.py` - lines 13, 15
- [ ] 5.2.10 `helpers.py` - lines 8, 10
- [ ] 5.2.11 `code_snippets.py` - lines 6, 8

**theauditor/linters/** (1 file):
- [ ] 5.2.12 `linters.py` - lines 11, 13

**theauditor/terraform/** (2 files):
- [ ] 5.2.13 `graph.py` - lines 11, 13
- [ ] 5.2.14 `analyzer.py` - lines 10, 12

**theauditor/indexer/extractors/** (4 files):
- [ ] 5.2.15 `terraform.py` - lines 8, 11
- [ ] 5.2.16 `rust.py` - lines 7, 10
- [ ] 5.2.17 `go.py` - lines 6, 9
- [ ] 5.2.18 `bash.py` - lines 5, 8

**theauditor/taint/** (1 file):
- [ ] 5.2.19 `flow_resolver.py` - lines 7, 11

**theauditor/** (1 file):
- [ ] 5.2.20 `vulnerability_scanner.py` - lines 13, 17

**theauditor/utils/__init__.py** (re-export):
- [ ] 5.2.21 Update `__init__.py` - remove `setup_logger` from `__all__` (lines 33, 56)

**Replacement pattern for each file:**
```python
# OLD (2 lines)
from theauditor.utils.logger import setup_logger
logger = setup_logger(__name__)

# NEW (1 line)
from theauditor.utils.logging import logger
```

- [ ] 5.2.22 Verify all 21 files updated:
```bash
grep -r "setup_logger" theauditor/ | grep -v "__pycache__"  # Should only show logger.py definition
```

---

## PHASE 6: Python Testing

### 6.1 Functional Tests

- [ ] 6.1.1 Run test suite: `python -m pytest tests/ -v`
- [ ] 6.1.2 Fix any test failures

### 6.2 Log Level Tests

- [ ] 6.2.1 Default (INFO) - should show info and above:
```bash
aud full --index
```
- [ ] 6.2.2 Debug - should show all logs:
```bash
THEAUDITOR_LOG_LEVEL=DEBUG aud full --index
```
- [ ] 6.2.3 Error only - should show minimal output:
```bash
THEAUDITOR_LOG_LEVEL=ERROR aud full --index
```

### 6.3 JSON Output Tests

- [ ] 6.3.1 Verify JSON output:
```bash
THEAUDITOR_LOG_JSON=1 aud full --index 2>&1 | head -5
```
- [ ] 6.3.2 Validate JSON is parseable:
```bash
THEAUDITOR_LOG_JSON=1 aud full --index 2>&1 | python -c "import sys,json; [json.loads(l) for l in sys.stdin]"
```

### 6.4 Rich UI Verification

- [ ] 6.4.1 Run full pipeline and verify live table still works:
```bash
aud full --offline
```
- [ ] 6.4.2 Compare output to baseline captured in 0.7

---

## PHASE 7: TypeScript Migration (Manual)

**READ**: specs/logging/spec.md "TypeScript Requirements" before starting.

### 7.1 Create TypeScript Logger

- [ ] 7.1.1 Create directory: `mkdir -p theauditor/ast_extractors/javascript/src/utils`
- [ ] 7.1.2 Create `theauditor/ast_extractors/javascript/src/utils/logger.ts`:

```typescript
/**
 * Lightweight logger for TypeScript extractor.
 *
 * Respects same environment variables as Python:
 * - THEAUDITOR_LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default: INFO)
 * - THEAUDITOR_LOG_JSON: 0|1 (default: 0)
 *
 * All output goes to stderr to avoid corrupting stdout JSON.
 */

const LOG_LEVELS = {
  DEBUG: 0,
  INFO: 1,
  WARNING: 2,
  ERROR: 3,
} as const;

type LogLevel = keyof typeof LOG_LEVELS;

const currentLevel: number =
  LOG_LEVELS[
    (process.env.THEAUDITOR_LOG_LEVEL?.toUpperCase() as LogLevel) ?? "INFO"
  ] ?? LOG_LEVELS.INFO;

const jsonMode = process.env.THEAUDITOR_LOG_JSON === "1";

function formatMessage(level: string, message: string): string {
  const timestamp = new Date().toISOString().slice(11, 19);
  if (jsonMode) {
    return JSON.stringify({ time: timestamp, level, message });
  }
  return `${timestamp} | ${level.padEnd(8)} | ${message}`;
}

export const logger = {
  debug: (msg: string): void => {
    if (currentLevel <= LOG_LEVELS.DEBUG) {
      console.error(formatMessage("DEBUG", msg));
    }
  },
  info: (msg: string): void => {
    if (currentLevel <= LOG_LEVELS.INFO) {
      console.error(formatMessage("INFO", msg));
    }
  },
  warning: (msg: string): void => {
    if (currentLevel <= LOG_LEVELS.WARNING) {
      console.error(formatMessage("WARNING", msg));
    }
  },
  error: (msg: string): void => {
    if (currentLevel <= LOG_LEVELS.ERROR) {
      console.error(formatMessage("ERROR", msg));
    }
  },
};
```

### 7.2 Migrate main.ts (15 statements)

- [ ] 7.2.1 Add import: `import { logger } from "./utils/logger";`
- [ ] 7.2.2 Replace line 33: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.3 Replace line 44: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.4 Replace line 149: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.5 Replace line 242: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.6 Replace line 360: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.7 Replace line 460: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.8 Replace line 469: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.9 Replace line 483: `console.error(`[DEBUG JS BATCH]...`)` → `logger.debug(...)`
- [ ] 7.2.10 Replace line 746: `console.error(`[DEBUG JS BATCH]...`)` → `logger.debug(...)`
- [ ] 7.2.11 Replace line 825: `console.error(`[DEBUG JS BATCH]...`)` → `logger.debug(...)`
- [ ] 7.2.12 Replace line 851: `console.error("[BATCH DEBUG]...")` → `logger.debug(...)`
- [ ] 7.2.13 Replace line 854: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.14 Replace line 857: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.15 Replace line 866: `console.error(...)` → `logger.error(...)`
- [ ] 7.2.16 Replace line 878: `console.error(...)` → `logger.error(...)`

### 7.3 Migrate core_language.ts (1 statement)

- [ ] 7.3.1 Add import: `import { logger } from "../utils/logger";`
- [ ] 7.3.2 Replace line 350: `console.error(...)` → `logger.error(...)`

### 7.4 Migrate data_flow.ts (2 statements)

- [ ] 7.4.1 Add import: `import { logger } from "../utils/logger";`
- [ ] 7.4.2 Replace line 184: `console.error(...)` → `logger.error(...)`
- [ ] 7.4.3 Replace line 189: `console.error(`[DEBUG JS]...`)` → `logger.debug(...)`

### 7.5 Rebuild TypeScript

- [ ] 7.5.1 Build: `cd theauditor/ast_extractors/javascript && npm run build`
- [ ] 7.5.2 Verify no build errors
- [ ] 7.5.3 Verify no remaining console.error (except in logger.ts):
```bash
grep -r "console\." theauditor/ast_extractors/javascript/src/ | grep -v logger.ts
```

---

## PHASE 8: Final Verification

**READ**: specs/logging/spec.md "All Requirements" before verifying.

### 8.1 Python Verification

- [ ] 8.1.1 Zero tagged prints remaining:
```bash
grep -r "print.*\[" theauditor/ | wc -l  # Should be 0
```
- [ ] 8.1.2 Logger imports present:
```bash
grep -r "from theauditor.utils.logging import logger" theauditor/ | wc -l  # Should be ~51
```
- [ ] 8.1.3 All tests pass:
```bash
python -m pytest tests/ -v
```

### 8.2 TypeScript Verification

- [ ] 8.2.1 Zero console.error remaining (except logger.ts):
```bash
grep -r "console\." theauditor/ast_extractors/javascript/src/ | grep -v logger.ts  # Should be empty
```
- [ ] 8.2.2 Logger import present in all modified files
- [ ] 8.2.3 TypeScript builds without errors

### 8.3 Integration Verification

- [ ] 8.3.1 Full pipeline works:
```bash
aud full --offline
```
- [ ] 8.3.2 Log level filtering works across both languages:
```bash
THEAUDITOR_LOG_LEVEL=DEBUG aud full --index
THEAUDITOR_LOG_LEVEL=ERROR aud full --index
```
- [ ] 8.3.3 JSON output works:
```bash
THEAUDITOR_LOG_JSON=1 aud full --index 2>&1 | head -10
```
- [ ] 8.3.4 Rich UI unchanged (visual comparison)

### 8.4 Cleanup

- [ ] 8.4.1 Remove any debug code added during implementation
- [ ] 8.4.2 Verify no `.pyc` or build artifacts committed
- [ ] 8.4.3 Final ruff check: `ruff check theauditor/`

---

## Task Dependencies

| Phase | Depends On |
|-------|------------|
| Phase 1 | Phase 0 verification |
| Phase 2 | Phase 1 (dependencies installed) |
| Phase 3 | Phase 2 (codemod written) |
| Phase 4 | Phase 3 (dry run verified) |
| Phase 5 | Phase 4 (transformation applied) |
| Phase 6 | Phase 5 (cleanup done) |
| Phase 7 | Phase 1 (Python logger available for reference) |
| Phase 8 | Phase 6 AND Phase 7 |

**Note**: Phase 7 (TypeScript) can run in parallel with Phases 2-6 (Python).

---

## Rollback Procedure

If anything goes wrong:

**Python:**
```bash
git checkout -- theauditor/
git checkout -- scripts/
rm theauditor/utils/logging.py
rm -rf scripts/codemods/
rm .libcst.codemod.yaml
```

**TypeScript:**
```bash
git checkout -- theauditor/ast_extractors/javascript/src/
rm -rf theauditor/ast_extractors/javascript/src/utils/
```

**Full rollback time**: ~2 minutes
