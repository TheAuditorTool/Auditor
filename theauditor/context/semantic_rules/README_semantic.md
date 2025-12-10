# Semantic Context Rules (aud context)

Use this directory to define **semantic context YAML files** for `aud context`. These files teach TheAuditor how to classify existing findings (from `aud detect-patterns` / `aud full`) according to **your** business logic so the tool can keep being a truth courier without guessing.

## Quick Start

1. **Generate findings**  
   Run `aud full` (recommended) or `aud detect-patterns` so `.pf/repo_index.db` + `findings_consolidated` exist.

2. **Copy the template**
   ```
   cd theauditor/context/semantic_rules
   cp template.yaml my_security_context.yaml
   ```

3. **Customize**  
   Edit the YAML’s `patterns` to describe which findings are obsolete, current, or transitional. Use the comments inside `refactoring.yaml` (OAuth/JWT example) as guidance.

4. **Run aud context**
   ```
   aud context --file theauditor/context/semantic_rules/my_security_context.yaml
   # optional extras
   aud context --file ... --verbose
   aud context --file ... --output semantic_report.json
   ```

5. **Consume the facts**  
   The report shows ❌ obsolete (de‑prioritized), ✅ current (still critical), ⏳ transitional (allowed until date), and ⚠️ mixed files.

## What’s in this folder

| File | Purpose |
|------|---------|
| `refactoring.yaml` | End-to-end **security migration** example (JWT → OAuth2). Demonstrates obsolete/current/transitional patterns, scopes, relationships, metadata. Copy/modify for your context. |
| `templates_instructions.md` | Extensive format reference: field descriptions, regex tips, scoping rules, severity guidance, troubleshooting. |

> **Important:** Semantic context YAML is **only** used by `aud context`. Refactor profiles for `aud refactor --file ...` live under `theauditor/refactor/yaml_rules/` and have a different schema/engine.

## When to use semantic contexts

### Great fits
- Security migrations (JWT → OAuth2, legacy crypto → KMS, token policy changes)
- Database / schema moves when you want to label findings by rollout stage
- API/platform deprecations (REST v1 → GraphQL, SOAP → REST)
- Architecture transitions (React class → hooks, queue → event bus)
- Business/compliance rules unique to your org

### Not a fit
- Adding new detectors (use `theauditor/rules/`)
- Enforcing migration mismatches (use refactor YAML profiles)
- One-off searches (use `rg`, `aud query`, or `aud detect-patterns`)

## How TheAuditor uses this YAML

1. `aud context` loads your semantic context (via `theauditor/context/semantic_context.py`).
2. For each finding in `findings_consolidated`, it checks the regex+scope rules:
   - **obsolete** → flagged as deprioritized
   - **current** → still important
   - **transitional** → temporarily acceptable until `expires`
3. Summaries + migration progress land in:
   - CLI output (truth courier facts only)
   - Use `--json` for machine-readable output (pipe to file if needed)

## Recommended workflow

1. `aud full` (or `aud detect-patterns`)
2. `aud context --file semantic_rules/<name>.yaml`
3. Optionally re-run after fixes to track migration progress

## Best practices

- **Be explicit**: Regex should match only the findings you intend (use anchors, negative lookaheads, precise scopes).
- **Use scope**: Narrow to relevant directories, exclude tests/migrations to avoid noise.
- **Severity signals intent**: `critical`/`high` for blocking obsolete findings, `low` for informational.
- **Expire transitional patterns**: Set realistic dates so they eventually flip to obsolete.
- **Document metadata**: Add owner, tickets, docs links—future you will thank you.

## Need more detail?

See `templates_instructions.md` for:
- Field-by-field guides
- Multiple examples (security, API, schema)
- Validation and troubleshooting tips

Questions? Open an issue on the repo or extend the documentation with your own templates. This directory is meant to stay example-rich so every team can bootstrap their own semantic contexts quickly. Remember: you provide the business logic, TheAuditor reports the facts.
