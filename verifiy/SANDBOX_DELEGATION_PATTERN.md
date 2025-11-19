# Sandbox Delegation Pattern - Implementation Guide

**Last Updated:** 2025-11-18
**Status:** ✅ Reference implementation complete (full.py)

---

## Overview

The sandbox delegation pattern allows commands to run in `.auditor_venv/` instead of polluting the user's global Python environment. Only `click` is installed globally; everything else runs from the sandbox.

## The Correct Pattern

### Template (Copy this exactly)

```python
@click.command()
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
def command_name(root):
    """Command description.

    Full docstring with examples, usage notes, etc.
    All the documentation goes here.
    """
    # SANDBOX DELEGATION: Check if running in sandbox
    from theauditor.sandbox_executor import is_in_sandbox, execute_in_sandbox

    if not is_in_sandbox():
        # Not in sandbox - delegate to sandbox Python
        import sys
        exit_code = execute_in_sandbox("command_name", sys.argv[2:], root=root)
        sys.exit(exit_code)

    # Normal command implementation starts here
    from theauditor.foo import bar
    # ... rest of code
```

### Critical Rules

1. **Placement**: Delegation code goes AFTER the closing `"""` of the docstring
   - ❌ WRONG: Before docstring (breaks docstring detection)
   - ❌ WRONG: Inside docstring (shows in help output)
   - ✅ CORRECT: After closing `"""`

2. **sys.argv indexing**: Use `sys.argv[2:]` NOT `sys.argv[1:]`
   - `sys.argv[0]` = "aud"
   - `sys.argv[1]` = "command_name"
   - `sys.argv[2:]` = actual arguments
   - Using `[1:]` causes duplicate command name

3. **Import timing**: Import `is_in_sandbox` and `execute_in_sandbox` INSIDE the function
   - Ensures sandbox_executor.py exists before importing
   - Avoids import errors on fresh installs

4. **Command name**: Must match the Click command name exactly
   - `execute_in_sandbox("full", ...)` for `@click.command()` named "full"
   - For grouped commands: use the subcommand name

## Reference Implementation

See `theauditor/commands/full.py:99-107` for the canonical implementation.

## Testing Checklist

Before committing a command with delegation:

- [ ] File compiles: `python -m py_compile theauditor/commands/yourfile.py`
- [ ] Help is clean: `aud yourcommand --help` (no delegation code visible)
- [ ] Delegation works: `aud yourcommand` runs without "Got unexpected extra argument"
- [ ] Imports work: No `ModuleNotFoundError` for sandbox_executor

## Common Mistakes (Already Fixed)

1. ❌ **Automation script inserting inside docstrings** (2025-11-18)
   - Broke 38 commands
   - Fixed by reverting and doing manually

2. ❌ **Using sys.argv[1:] instead of sys.argv[2:]** (2025-11-18)
   - Caused "Got unexpected extra argument (command)" errors
   - Fixed in full.py reference implementation

## Which Commands Need Delegation?

**Yes - Need delegation (most commands):**
- Any command using PyYAML, sqlparse, numpy, etc.
- All analysis commands (full, lint, taint, etc.)
- Graph commands
- FCE, patterns, deadcode, etc.

**No - Don't need delegation:**
- `setup-ai` - Must run globally to CREATE the sandbox
- `--help`, `--version` - Click handles these before our code runs

## Rollout Strategy

**Don't bulk-update.** Update commands one at a time as they're touched or as issues arise.

**Priority order (if doing systematically):**
1. Core commands users run frequently (full, index, lint)
2. Analysis commands (taint, patterns, graph)
3. Utility commands (workset, deps)
4. Rarely-used commands

## Architecture Context

- **Global environment**: Only `click==8.3.1` installed
- **Sandbox (.auditor_venv/)**: All 50+ packages (runtime + dev)
- **Delegation module**: `theauditor/sandbox_executor.py`
- **Environment variable**: `THEAUDITOR_IN_SANDBOX=1` prevents recursion

See `SANDBOX_ARCHITECTURE_STATUS.md` for full architecture details.

---

**Remember:** Never use automation scripts for mass updates. This pattern is simple but placement-sensitive. Do it manually or with extreme caution.
