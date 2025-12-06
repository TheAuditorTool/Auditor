# Refactor Profile Templates & Instructions

Refactor profiles describe business-logic checks for `aud refactor --file`. They complement the default migration scan by telling TheAuditor which legacy identifiers must disappear and which new constructs must exist in the codebase.

The CLI loads the YAML via `theauditor/refactor/profiles.py`, queries `.pf/repo_index.db`, and emits a truth-courier report (no guidance, just facts).

---

## 1. Schema overview

```yaml
refactor_name: "frontend_variants_v2"
description: "Ensure POS + dashboard flows use product_variant_id"
version: "2025-10-26"

metadata:
  owner: "plantflow_frontend"
  jira_epic: "PF-276"
  docs: "https://wiki.company.com/variants"

rules:
  - id: "order-pos-cart"
    description: "Cart/order/receipt flows must store product_variant_id"
    severity: "critical"          # critical | high | medium | low
    category: "pos-flow"          # free-form tag
    match:                         # LEGACY references we want gone
      identifiers:
        - "cartItem.product_id"
        - "orderItem.product_id"
      expressions:
        - "product.unit_price"
    expect:                        # NEW references we expect to see
      identifiers:
        - "product_variant_id"
        - "posSelection.variant"
      expressions:
        - "variant.retail_price"
    scope:
      include:
        - "frontend/src/pages/pos/**"
        - "frontend/src/pages/dashboard/CreateOrder.tsx"
      exclude:
        - "tests/"
    guidance: >
      (Optional) Human note for future readers. Not shown as advice in CLI,
      just stored in the report.
```

### Field reference

| Field | Required | Notes |
|-------|----------|-------|
| `refactor_name` | ✅ | Unique slug for the profile |
| `description` | ✅ | Short summary |
| `version` | ➕ | Use dates/semver to track revisions |
| `metadata` | ➖ | Owner, tickets, docs, rollout stage, etc. |
| `rules[]` | ✅ | Each rule defines a set of `match` and optional `expect` patterns |
| `rules[].severity` | ➕ | Sorting priority (critical/high/medium/low) |
| `rules[].category` | ➖ | Tag for grouping |
| `rules[].match` | ✅ | Legacy identifiers/expressions/API routes to find |
| `rules[].expect` | ➖ | New identifiers/expressions we hope to find (used to confirm coverage) |
| `rules[].scope.include/exclude` | ➕ | Lists of path substrings; excludes checked first |
| `rules[].guidance` | ➖ | Informational comment (printed in JSON, not as an instruction) |

> **Pattern Modes:** By default, patterns use word-boundary matching (e.g., `id` matches "id" but not "grid"). For advanced matching, wrap patterns in forward slashes to use regex (e.g., `/.*\.product\.id/` matches any `x.product.id`).

---

## 2. Pattern syntax

The engine supports two pattern modes:

### Literal patterns (default)
Plain strings match using **word boundaries** to prevent false positives:

```yaml
match:
  identifiers:
    - "product_id"      # Matches "product_id" but NOT "old_product_id" or "product_ids"
    - "cartItem.id"     # Matches exact "cartItem.id"
```

### Regex patterns (advanced)
Wrap patterns in forward slashes `/.../ for regex matching:

```yaml
match:
  identifiers:
    # Matches: item.product.id, cart.product.id, anything.product.id
    - "/.*\\.product\\.id/"

    # Matches any property ending in product_id
    - "/\\.product_id$/"

    # Matches product_id as a substring (like legacy LIKE behavior)
    - "/product_id/"
```

**When to use regex:**
- Catching variations: `/cart.*\\.product_id/` catches `cartItem.product_id`, `cartData.product_id`
- Property patterns: `/\\.product\\.id/` catches `x.product.id` regardless of prefix
- Flexible matching when you can't enumerate all variable names

**Regex tips:**
- Escape dots as `\\.` (YAML requires double backslash)
- `.*` matches any characters
- `$` anchors to end of string
- Patterns are case-insensitive

---

## 3. Writing effective rules

1. **Treat `match` as "old world"**
   Every string listed should represent a legacy table/column/API. The engine queries `symbols`, `assignments`, `function_call_args`, `api_endpoints`, and more to find matches.

2. **Use `expect` for "new world"**
   When provided, the CLI reports whether any new identifiers appear. Missing expectations show up under "Rules with missing new schema references".

3. **Scope aggressively**
   Include only relevant directories. Exclude generated code, migrations, tests, or vendor folders to keep results crisp.

4. **Start specific, go regex when needed**
   Begin with literal patterns (`cartItem.product_id`). If you find yourself adding many variations, switch to a regex (`/.*\\.product_id/`).

5. **Annotate with `guidance`**
   Short description that humans/AI can read when reviewing JSON output. The CLI itself remains factual (no prescriptive text).

6. **Group by workflow**
   Create separate rules for POS cart, transfers, returns, reports, etc. That keeps the priority queue meaningful.

---

## 4. Running the profile

```
aud refactor --file theauditor/refactor/yaml_rules/<profile>.yaml --migration-limit 0
```

Output sections:
- **Profile summary** – totals, rule coverage, missing expectations.
- **Rule breakdown** – per-rule counts, top files, cross-reference with schema mismatches.
- **File priority queue** – severity-sorted list of files with most violations (plus schema overlap counts).
- **Schema mismatch summary** – default Phase 3 output (dropped tables/columns from migrations).

The CLI never suggests fixes; it only lists the facts so you/your AI agent can decide what to edit next.

---

## 5. Example snippets

### Transfers rule
```yaml
  - id: "transfers-variant-ids"
    description: "Transfers + QR flows must use product_variant_id"
    severity: "high"
    match:
      identifiers:
        - "transferItem.product_id"
        - "product_variant.product.name"
      expressions:
        - "qrPayload.product_id"
    expect:
      identifiers:
        - "transferItem.product_variant_id"
      expressions:
        - "qrPayload.product_variant_id"
    scope:
      include:
        - "frontend/src/pages/dashboard/Transfers.tsx"
        - "frontend/src/components/dashboard/TransferDetailsModal.tsx"
        - "frontend/src/components/QRScanner.tsx"
```

### Backend validation rule
```yaml
  - id: "backend-variant-contract"
    severity: "critical"
    match:
      expressions:
        - "products.inventory_type"
        - "transfer_items.weight"
    expect:
      identifiers:
        - "variant.inventory_type"
    scope:
      include:
        - "backend/src/controllers/**"
        - "backend/src/validations/**"
```

### Regex pattern rule (catches variable name variations)
```yaml
  - id: "order-pos-cart"
    description: "Ordering flows must use variant IDs"
    severity: "critical"
    match:
      identifiers:
        # Regex: catches item.product.id, cart.product.id, x.product.id
        - "/.*\\.product\\.id/"
        # Regex: catches any .product_id property access
        - "/\\.product_id/"
      expressions:
        # Literal: exact match with word boundaries
        - "product.unit_price"
    expect:
      identifiers:
        - "product_variant_id"
    scope:
      include:
        - "frontend/src/pages/pos/**"
```

---

## 6. Tips & troubleshooting

| Symptom | Suggestion |
|---------|------------|
| Too few matches | Add more identifiers to `match`, widen scope, or use regex patterns (`/.*\\.product_id/`). Ensure `.pf/repo_index.db` is up to date (`aud full`). |
| Too many matches | Tighten scope, use more precise substrings (`cartItem.product_id`), or use word-boundary matching (default). |
| Missing variable names | Use regex: `/.*\\.product\\.id/` catches `item.product.id`, `cart.product.id`, etc. |
| Expectation never fulfilled | Double-check spelling; consider whether the new identifiers actually exist in the code yet. |
| Need JSON for automation | Use `--output report.json`; it includes profile + schema data. |

---

## 7. Best practices

- Store shared templates here, but keep project-specific copies in the target repo (e.g., `PlantFlow/profile.yaml`).
- Add inline comments so future contributors/AI agents understand the intent.
- Update `version` and `metadata.last_updated` when changing the profile.
- Pair with semantic contexts when you also need to re-label security findings (`aud context`).

Happy auditing!
