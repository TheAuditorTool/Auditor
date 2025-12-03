# Verification: Rich CLI Help Modernization

## Purpose
Document hypotheses and verification results before implementation begins.

---

## Hypothesis 1: Click Supports Custom Command Classes

**Hypothesis:** Click's `@click.command(cls=CustomClass)` allows overriding `format_help()` to use Rich.

**Verification Method:** Check Click documentation and test with minimal example.

**Status:** PENDING

**Evidence:**
```python
# Test this works:
class RichCommand(click.Command):
    def format_help(self, ctx, formatter):
        # Custom Rich output here
        pass

@click.command(cls=RichCommand)
def test():
    """Test command."""
    pass
```

**Result:** _To be filled during verification_

---

## Hypothesis 2: Rich Console Works in format_help Context

**Hypothesis:** Rich Console can print to stdout during Click's help formatting without conflicts.

**Verification Method:** Test Rich output within format_help override.

**Status:** PENDING

**Evidence:**
```python
def format_help(self, ctx, formatter):
    console = Console()
    console.print("[bold]Test[/bold]")  # Does this work?
```

**Result:** _To be filled during verification_

---

## Hypothesis 3: Existing RichGroup Pattern Works

**Hypothesis:** The existing `RichGroup` class in `cli.py` provides a working pattern we can follow.

**Verification Method:** Read `cli.py:24-138` and confirm pattern.

**Status:** VERIFIED

**Evidence:**
```python
# cli.py:24-138 shows working pattern:
class RichGroup(click.Group):
    def format_help(self, ctx, formatter):
        console = Console(force_terminal=sys.stdout.isatty())
        console.print()
        console.rule(...)  # Rich formatting works
        console.print(Panel(...))  # Panels work
```

**Result:** CONFIRMED - RichGroup demonstrates the pattern works. We can follow the same approach for RichCommand.

---

## Hypothesis 4: All 36 Command Files Use Click Decorators

**Hypothesis:** All command files use standard `@click.command()` decorators that can accept `cls=` parameter.

**Verification Method:** Grep for command decorators in all files.

**Status:** PENDING

**Evidence:**
```bash
# Run: grep -r "@click.command" theauditor/commands/
# Check each file uses standard decorator
```

**Result:** _To be filled during verification_

---

## Hypothesis 5: Group Commands Need Different Handling

**Hypothesis:** Commands like `graph`, `session`, `terraform` are groups with subcommands and need `RichGroup` + `RichCommand` combination.

**Verification Method:** Identify all group commands.

**Status:** PENDING

**Commands to check:**
- [ ] graph.py - confirmed group
- [ ] session.py - likely group
- [ ] terraform.py - likely group
- [ ] cdk.py - likely group
- [ ] docs.py - check if group

**Result:** _To be filled during verification_

---

## Hypothesis 6: Manual Entries Can Use Rich Markup

**Hypothesis:** The `EXPLANATIONS` dict in manual.py can store Rich markup strings that render correctly.

**Verification Method:** Test Rich markup in explanation strings.

**Status:** PENDING

**Evidence:**
```python
# Current: console.print(info["explanation"], markup=False)
# This explicitly disables markup!
# Need to change to: console.print(info["explanation"])
# Or use: console.print(Markdown(info["explanation"]))
```

**Result:** _To be filled during verification_

---

## Hypothesis 7: Docstring Sections Can Be Parsed Reliably

**Hypothesis:** Docstrings with section headers (AI CONTEXT:, EXAMPLES:, etc.) can be reliably parsed.

**Verification Method:** Test parsing logic with various docstring formats.

**Status:** PENDING

**Edge cases to test:**
- Docstring with no sections (just summary)
- Docstring with some but not all sections
- Docstring with colon in content (not just headers)
- Multi-line section content
- Code blocks within sections

**Result:** _To be filled during verification_

---

## Hypothesis 8: Terminal Width Detection Works

**Hypothesis:** Rich Console correctly detects terminal width for wrapping.

**Verification Method:** Test on different terminals.

**Status:** PENDING

**Terminals to test:**
- [ ] Windows Terminal
- [ ] CMD.exe
- [ ] PowerShell
- [ ] VSCode integrated terminal
- [ ] Non-TTY (piped output)

**Result:** _To be filled during verification_

---

## Hypothesis 9: Existing Help Text Is Outdated

**Hypothesis:** Many docstrings reference outdated features, commands, or architecture.

**Verification Method:** Read each command's docstring and compare to current behavior.

**Status:** VERIFIED (partial)

**Evidence found:**
1. `index.py` - References deprecated standalone index command
2. `taint.py` - References "aud index" which is deprecated
3. Multiple files reference old database paths
4. Pipeline stages count is outdated in several files

**Result:** CONFIRMED - Content modernization needed alongside formatting.

---

## Hypothesis 10: No Breaking Changes to Exit Codes

**Hypothesis:** Changing help text formatting will not affect command exit codes or machine output.

**Verification Method:** Review code paths - help text is separate from command execution.

**Status:** VERIFIED

**Evidence:**
- `format_help()` only runs when `--help` flag is used
- Normal command execution bypasses help formatting
- Exit codes are set by command logic, not help system

**Result:** CONFIRMED - Safe to modify help formatting.

---

## Discrepancies Found

### Discrepancy 1: manual.py Disables Markup
**Expected:** Manual entries should support Rich markup
**Actual:** `console.print(info["explanation"], markup=False)` explicitly disables it
**Impact:** Need to remove `markup=False` and restructure explanation content
**Location:** `manual.py:1200`

### Discrepancy 2: Inconsistent Section Headers
**Expected:** All commands use same section header names
**Actual:** Various formats: "AI CONTEXT:", "AI ASSISTANT CONTEXT:", "WHAT IT DETECTS:", etc.
**Impact:** Need to standardize before parsing can work reliably

### Discrepancy 3: Some Commands Have No Docstrings
**Expected:** All commands have help text
**Actual:** Some commands have minimal or missing docstrings
**Impact:** Need to write new content, not just reformat

---

## Verification Checklist

Before starting Phase 1:
- [ ] Verify Hypothesis 1 (Click custom class)
- [ ] Verify Hypothesis 2 (Rich in format_help)
- [ ] Verify Hypothesis 4 (all files use decorators)
- [ ] Verify Hypothesis 5 (identify all group commands)
- [ ] Verify Hypothesis 6 (Rich markup in manual)
- [ ] Test Hypothesis 7 (docstring parsing)

Before starting Phase 2+:
- [ ] Complete Phase 1 infrastructure
- [ ] Test with at least one command end-to-end
