## Context

TheAuditor commands write JSON analysis outputs to `.pf/raw/` directory. This was designed for:
1. Chunking large outputs for AI consumption
2. Human-readable analysis artifacts
3. CI/CD pipeline integration

Reality:
- AI can't read 10MB files anyway
- Commands already have `--json` for human/CI consumption
- Database is the actual source of truth

This is a v2.0 breaking change affecting ~15 command files.

## Goals / Non-Goals

**Goals:**
- Remove all `.pf/raw/` file writes
- Add `--json` flags where missing (stdout output)
- Update documentation/help text
- Clean removal with no fallback patterns

**Non-Goals:**
- Providing migration scripts (v2.0 breaks things, that's fine)
- Preserving backwards compatibility
- Creating alternative file output mechanisms

## Decisions

### Decision 1: Remove `--output` flags entirely vs change defaults

**Decision**: Remove `--output` flags that default to `.pf/raw/`. Replace with `--json` for stdout.

**Reasoning**:
- `--output` implies file writing, which we're eliminating
- `--json` to stdout is pipeable: `aud taint --json > my_report.json`
- User controls destination, not the tool

**Alternative considered**: Keep `--output` but require explicit path (no default)
**Rejected**: Still encourages file-based workflows we want to eliminate

### Decision 2: Commands without any JSON output

**Decision**: Add `--json` flag to all commands that currently only write to `.pf/raw/`:
- `docker_analyze`
- `graph analyze`
- `detect_frameworks`
- `deps`
- `cfg analyze`
- `terraform provision`, `terraform analyze`
- `workflows analyze`
- `metadata churn`, `metadata coverage`

**Reasoning**: Every command should have machine-readable output option

### Decision 3: FCE `--write` flag

**Decision**: Remove `--write` flag entirely. FCE already outputs to stdout.

**Reasoning**: `aud fce --json` already works for JSON output. `--write` is redundant.

### Decision 4: `aud full` summary

**Decision**: Remove raw file counting from pipeline summary. Keep other output.

**Reasoning**: No raw files = nothing to count

### Decision 5: Archive command

**Decision**: Remove `.pf/raw/` from archive logic entirely.

**Reasoning**: Nothing to archive if nothing is written

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| CI/CD pipelines break expecting `.pf/raw/*.json` | v2.0 breaking change, document in changelog |
| Users lose "saved" analysis | Use `--json > file.json` pattern instead |
| Debugging harder without files | Database is queryable, `--json` available |

## Migration Plan

1. Remove all `.pf/raw/` writers in single PR
2. Add `--json` flags to commands lacking them
3. Update help text
4. Document breaking change in v2.0 changelog
5. No deprecation period - this is v2.0

**Rollback**: `git revert` if needed, but we won't need it

## Open Questions

None. Crystal clear.
