# Semantic Context YAML – Template & Instructions

Semantic contexts let `aud context` interpret findings according to **your** business logic (security, schema, or workflow migrations). This guide explains the YAML format and provides an OAuth/JWT example you can copy.

---

## 1. Concept refresher

1. Run `aud full` or `aud detect-patterns` first (populates `findings_consolidated`).
2. Write a semantic context YAML describing:
   - **obsolete** patterns → findings to de-prioritize
   - **current** patterns → findings that still matter
   - **transitional** patterns → dual-stack code allowed until a date
3. Execute `aud context --file <path>` to reclassify the findings.

> Semantic contexts affect `aud context` only. For `aud refactor --file`, use `theauditor/refactor/yaml_rules/`.

---

## 2. YAML structure

```yaml
context_name: "oauth_migration_security"
description: "Classifies JWT findings vs OAuth2 adoption state"
version: "2025-10-26"

patterns:
  obsolete:
    - id: "jwt_issue_calls"
      pattern: "(jwt\\.sign|AuthService\\.issueJwt)"
      reason: "Legacy JWT signing scheduled for removal"
      replacement: "AuthService.issueOAuthToken"
      severity: "medium"
      scope:
        include: ["backend/src/auth/"]
        exclude: ["tests/"]

  current:
    - id: "oauth_exchange"
      pattern: "oauth2Client\\."
      reason: "OAuth2/OIDC code must stay high-priority"
      scope:
        include: ["backend/src/auth/", "frontend/src/auth/"]

  transitional:
    - id: "jwt_oauth_bridge"
      pattern: "bridgeJwtToOAuth"
      reason: "Bridge layer allowed until Phase 3 completes"
      expires: "2025-12-31"
      scope:
        include: ["backend/src/auth/bridges/"]

relationships:
  - type: "replaces"
    from: "jwt_issue_calls"
    to: "oauth_exchange"

metadata:
  author: "security_team"
  jira_ticket: "SEC-2045"
  docs: "https://wiki.company.com/security/oauth-migration"
```

### Field reference

| Field | Required | Description |
|-------|----------|-------------|
| `context_name` | ✅ | Unique identifier (snake_case) |
| `description` | ✅ | Short explanation |
| `version` | ➕ | Date or semver (helps track revisions) |
| `patterns.obsolete[]` | ➕ | Patterns flagged as obsolete. Requires `id`, `pattern`, `reason`. Optional `replacement`, `severity`, `scope`. |
| `patterns.current[]` | ➕ | “Correct” patterns that should stay high-priority. Requires `id`, `pattern`, `reason`. Optional `scope`. |
| `patterns.transitional[]` | ➕ | Allowed temporarily. Requires `id`, `pattern`, `reason`, `expires`. Optional `scope`. |
| `scope.include/exclude` | ➕ | Lists of path substrings. Excludes evaluated first. |
| `relationships[]` | ➖ | Connect related pattern IDs (e.g., `replaces`, `equivalent`). |
| `metadata` | ➖ | Owner, tickets, tags, docs, rollout info. Free-form map. |

> Regex is matched case-insensitively against finding `rule`, `message`, and `code_snippet`. Escape `\` as `\\`.

---

## 3. Workflow

1. **Plan** – decide what counts as obsolete/current/transitional.
2. **Author YAML** – copy the template above or `refactoring.yaml`.
3. **Validate** – run `aud context --file ... --verbose` in a branch, adjust regex/scope until results are correct.
4. **Share** – check in the YAML (and optionally reference it in team runbooks).
5. **Iterate** – update `version`, `metadata.last_updated`, and transitional `expires` as migrations progress.

---

## 4. Severity guidance (obsolete patterns)

| Severity | Typical meaning |
|----------|-----------------|
| `critical` | Absolutely remove ASAP (e.g., leaking secrets) |
| `high` | Blocker for launch or compliance |
| `medium` | Should be cleaned up soon but not blocking |
| `low` | Cosmetic or documentation-only |

Severity changes how `aud context` sorts output—it doesn’t auto-fix anything.

---

## 5. Scope tips

- Use broad directories (`frontend/`, `backend/src/auth/`) rather than specific files—keeps YAML stable.
- Exclude `tests/`, `fixtures/`, and `migrations/` to avoid false positives.
- No globbing; TheAuditor does substring checks (`"frontend/"` matches any path containing it).

---

## 6. Best practices

1. **Write regex defensively**  
   Anchor to words, use negative lookaheads to avoid partial matches, test with `python -m re`.

2. **Document intent**  
   Metadata + inline comments help future maintainers understand why a pattern exists.

3. **Expire transitional rules**  
   Don’t leave dual-stack allowances open-ended—set `expires` and remove them once expired.

4. **One context per initiative**  
   Keep YAML focused (e.g., `payments_stripe_migration.yaml`). Multiple concurrent initiatives? Create multiple files.

5. **Pair with `aud query`**  
   After reclassifying findings, use `aud query` to inspect code relationships around the flagged files.

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| “No patterns matched” | Check that `aud detect-patterns` ran; verify scope includes the files; test regex. |
| Too many matches | Narrow scope or refine regex (e.g., `product_id(?!_variant)` instead of `product_id`). |
| Transitional never expires | Update `expires`; once the date passes, re-run to see them as obsolete. |
| Need JSON for AI agents | Use `--json` flag for stdout output (pipe to file if needed). |

Still stuck? Inspect `theauditor/insights/semantic_context.py` for exact behavior or open an issue.

---

## 8. Relationship to refactor profiles

- **Semantic context (this folder)** → input to `aud context --file`, classifies existing findings (often security-focused).
- **Refactor YAML profiles** (`theauditor/refactor/yaml_rules`) → input to `aud refactor --file`, scan migrations + code for mismatches.

Different pipelines, different schemas—use whichever matches the problem you're solving.

---

Happy context writing! Add new examples to this directory when you create reusable templates so everyone benefits.
