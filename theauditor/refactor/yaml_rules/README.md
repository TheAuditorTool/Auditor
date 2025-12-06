# Refactor Profiles (aud refactor --file …)

This directory stores YAML profiles for the refactor rule engine that powers:

```
aud refactor --file <profile.yaml>
```

Use these files to describe *which* legacy identifiers should disappear after a migration and *where* the new schema/contract must appear. The CLI then cross-references `.pf/repo_index.db` to list every file/line still violating your business rules.

## Quick Start

1. Ensure `.pf/repo_index.db` exists (`aud full`).
2. Copy an existing profile (e.g., `profile.yaml` from your project) into this directory.
3. Define rules with `match` (old identifiers) and `expect` (new identifiers).
4. Run:
   ```
   aud refactor --file theauditor/refactor/yaml_rules/<profile>.yaml --migration-limit 0
   ```
5. Read the “Profile summary” + “File priority queue” to decide which files your AI/engineers should tackle first.

## Why refactor profiles?

- Migration scripts tell you *what changed* in the DB.  
  Profiles tell TheAuditor *how your application should behave* after those changes.
- Lets you encode product-specific semantics (POS variant flows, conversion workflows, etc.) without modifying the engine.
- Keeps the CLI factual: it reports every location still referencing “old” identifiers and highlights whether the “new” ones ever appear.

## File naming & structure

- Store reusable templates in this directory (e.g., `variant_migration.yaml`, `payments_split.yaml`).
- Project-specific copies can live in the target repo (e.g., `PlantFlow/profile.yaml`) and point to them with `aud refactor --file`.
- Comments are encouraged—profiles double as runbooks for other engineers or AI loops.

For the field-by-field schema (including regex pattern syntax), see `templates_instructions.md` in this folder.

## Relationship to semantic contexts

- **Refactor profiles** (this folder) → used by `aud refactor --file`, operate directly on code/migration data.
- **Semantic contexts** (`theauditor/context/semantic_rules/`) → used by `aud context --file`, reclassify security findings.

Keep them separate; they solve different problems.
