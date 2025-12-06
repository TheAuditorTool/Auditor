# TheAuditor Semantic Context System

## Overview

**Semantic Context** is TheAuditor's business logic classification system that maps analysis findings to organizational workflow. Rather than treating all findings equally, semantic context lets you define which code patterns are:

- **Obsolete**: Deprecated, scheduled for removal
- **Current**: Correct, enforce strictly
- **Transitional**: Temporarily acceptable during migrations

---

## What Problem Does It Solve?

During technical migrations (OAuth → JWT, schema changes, framework upgrades), developers face a dilemma:
- Analysis tools flag ALL instances equally (no priority)
- But business reality is: some patterns are intentionally scheduled for removal
- Teams need to acknowledge findings while tracking migration progress

**Semantic context bridges this gap** by applying YOUR business logic to findings AFTER detection.

---

## Three-Layer Classification

| Category | Meaning | Action |
|----------|---------|--------|
| **Obsolete** | Deprecated pattern scheduled for removal | De-prioritize, track removal progress |
| **Current** | Correct/modern pattern | Keep high-priority |
| **Transitional** | Allowed temporarily during migration | Accept until expiration date |

---

## YAML Rule Schema

```yaml
context_name: "oauth_migration_security"
description: "Classify JWT vs OAuth2 findings during migration"
version: "2025-10-26"

patterns:
  obsolete:
    - id: "jwt_issue_calls"
      pattern: "(jwt\\.sign|jwt\\.verify)"
      reason: "JWT signing deprecated; use OAuth2"
      replacement: "AuthService.issueOAuthToken"
      severity: "high"
      scope:
        include: ["backend/src/auth/"]
        exclude: ["tests/"]

  current:
    - id: "oauth_exchange"
      pattern: "oauth2Client\\."
      reason: "OAuth2 is the approved mechanism"

  transitional:
    - id: "jwt_oauth_bridge"
      pattern: "bridgeJwtToOAuth"
      reason: "Bridge layer during Phase 2"
      expires: "2025-12-31"  # REQUIRED for transitional

metadata:
  jira_ticket: "SEC-2045"
  documentation: "https://wiki/oauth-migration"
```

---

## Classification Logic

For each finding:
1. Try obsolete patterns (first match wins)
2. Try current patterns
3. Try transitional patterns (check expiration)
4. Unclassified if no match

**Transitional Expiration**: After `expires` date, pattern auto-escalates to obsolete.

---

## CLI Usage

```bash
# Apply semantic context to findings
aud context --file oauth_migration.yaml

# With custom output
aud context -f rules.yaml -o ./reports/migration_report.json

# Verbose mode
aud context -f rules.yaml --verbose
```

---

## Migration Progress Tracking

```python
{
    "total_files": 42,
    "files_need_migration": 15,
    "files_fully_migrated": 25,
    "files_mixed": 2,
    "migration_percentage": 59.5
}
```

---

## Output Format

### Console Report
- OBSOLETE PATTERNS: Count, severity, file locations
- CURRENT PATTERNS: Confirmation of correct usage
- TRANSITIONAL PATTERNS: Expiration status
- MIXED FILES: Files with both obsolete and current
- HIGH PRIORITY FILES: Critical/high severity obsolete

### JSON Export
Complete classification with finding details, pattern matches, and migration suggestions.

---

## How It Differs from Grep

| Aspect | grep/rg | Semantic Context |
|--------|---------|------------------|
| **Purpose** | Find text | Classify findings by business meaning |
| **Input** | Raw source | Analysis findings (already detected) |
| **Output** | Matching lines | Classified findings + progress metrics |
| **Migration** | No | Built-in progress, priority, expiration |
