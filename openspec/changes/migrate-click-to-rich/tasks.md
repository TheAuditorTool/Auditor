## 0. Pre-Flight Verification
- [ ] 0.1 Confirm `rich>=13.0.0` in pyproject.toml dependencies
- [ ] 0.2 Confirm `libcst` available (install if needed: `pip install libcst`)
- [ ] 0.3 Verify `scripts/rich_migration.py` exists and is syntactically valid
- [ ] 0.4 Run `python -c "from theauditor.pipeline.ui import console; print(console)"` to confirm ui.py works
- [ ] 0.5 Count baseline: `grep -r "click\.echo" theauditor/commands/ | wc -l` (expect ~1470)

## 1. Run Migration Script
- [ ] 1.1 Dry run on single file to verify output: `python scripts/rich_migration.py theauditor/commands/lint.py --dry-run --diff`
- [ ] 1.2 Dry run on all commands: `python scripts/rich_migration.py theauditor/commands/*.py --dry-run`
- [ ] 1.3 Review dry run summary (files affected, transformation count)
- [ ] 1.4 Execute migration: `python scripts/rich_migration.py theauditor/commands/*.py`
- [ ] 1.5 Verify completion message shows ~1470 transformations across 39 files

## 2. Post-Migration Validation
- [ ] 2.1 Count post-migration: `grep -r "click\.echo" theauditor/commands/ | wc -l` (expect 0)
- [ ] 2.2 Count console.print usage: `grep -r "console\.print" theauditor/commands/ | wc -l` (expect ~1470+)
- [ ] 2.3 Verify imports added: `grep -r "from theauditor.pipeline.ui import" theauditor/commands/ | wc -l` (expect 39)
- [ ] 2.4 Run Python syntax check: `python -m py_compile theauditor/commands/*.py`
- [ ] 2.5 Run type check: `npm run typecheck` (if applicable) or `mypy theauditor/commands/`

## 3. Manual Review - High-Risk Files
- [ ] 3.1 Review `blueprint.py` (225 echo calls - highest count)
- [ ] 3.2 Review `planning.py` (200 echo calls)
- [ ] 3.3 Review `graph.py` (135 echo calls)
- [ ] 3.4 Review `refactor.py` (70 echo calls)
- [ ] 3.5 Review `session.py` (69 echo calls)
- [ ] 3.6 Check for any `# WARN` comments left by migration script

## 4. Edge Case Verification
- [ ] 4.1 Verify no double-escaped brackets (`\\\\[` instead of `\\[`)
- [ ] 4.2 Verify f-strings with variables have `highlight=False` where needed
- [ ] 4.3 Verify pure variable outputs have `markup=False`
- [ ] 4.4 Verify `err=True` converted to `stderr=True`
- [ ] 4.5 Verify `nl=False` converted to `end=""`
- [ ] 4.6 Verify separator patterns (`"=" * 60`) converted to `console.rule()`

## 5. Functional Testing
- [ ] 5.1 Run `aud --help` - verify no crashes, styled output
- [ ] 5.2 Run `aud full --help` - verify help text renders
- [ ] 5.3 Run `aud blueprint --structure` on test repo - verify output styling
- [ ] 5.4 Run `aud lint --workset` on test repo - verify output
- [ ] 5.5 Run `aud detect-patterns` on test repo - verify output
- [ ] 5.6 Run `aud full --index --offline` on test repo - verify pipeline integration

## 6. Windows Compatibility
- [ ] 6.1 Verify no emoji characters in migrated output (grep for Unicode ranges)
- [ ] 6.2 Test on Windows Command Prompt (if available) - no UnicodeEncodeError
- [ ] 6.3 Verify all output is CP1252-safe

## 7. Cleanup
- [ ] 7.1 Remove any unused `import click` statements that migration missed
- [ ] 7.2 Run `ruff check theauditor/commands/ --fix` for import sorting
- [ ] 7.3 Run `ruff format theauditor/commands/` for consistent formatting
- [ ] 7.4 Final git diff review before commit
