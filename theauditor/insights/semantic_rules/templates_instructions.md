# Semantic Context Templates & Instructions

This directory contains semantic context YAML files that teach TheAuditor about YOUR specific business logic, refactoring contexts, and codebase semantics.

## What Are Semantic Contexts?

Semantic contexts are **user-defined** files that tell TheAuditor:
- What code patterns are **obsolete** (need updating)
- What patterns are **current** (correct usage)
- What patterns are **transitional** (temporarily OK)

TheAuditor is a **truth courier** - it reports facts about your code. But it doesn't know YOUR business logic. That's where semantic contexts come in. You teach TheAuditor about your refactorings, migrations, and architecture patterns.

## When to Use Semantic Contexts

### ✅ Perfect Use Cases:
- **Refactoring tracking**: You moved `Product.price` to `ProductVariant.retail_price`
- **Deprecated APIs**: Old endpoints that should no longer be used
- **Schema migrations**: Database structure changes
- **Architecture transitions**: Moving from REST to GraphQL
- **Business rule enforcement**: Company-specific patterns
- **Migration progress**: Track gradual codebase updates

### ❌ Not Suitable For:
- General security issues (use rules in `theauditor/rules/` instead)
- Universal code smells (those belong in core TheAuditor)
- One-time searches (use `grep` or `aud detect-patterns`)

## YAML Format Specification

### Basic Structure

```yaml
context_name: "unique_identifier"
description: "Human-readable description of what this context tracks"
version: "YYYY-MM-DD or semver"

patterns:
  obsolete:
    - id: "pattern_id"
      pattern: "regex_pattern"
      reason: "Why this is obsolete"
      replacement: "What to use instead"
      severity: "critical|high|medium|low"
      scope:
        include: ["frontend/", "api/"]
        exclude: ["tests/", "migrations/"]

  current:
    - id: "pattern_id"
      pattern: "regex_pattern"
      reason: "Why this is correct"
      scope:
        include: ["backend/"]

  transitional:
    - id: "pattern_id"
      pattern: "regex_pattern"
      reason: "Why this is temporarily OK"
      expires: "YYYY-MM-DD"
      scope:
        include: ["services/"]

relationships:  # Optional
  - type: "replaces"
    from: "old_pattern_id"
    to: "new_pattern_id"

metadata:  # Optional
  author: "your_name"
  created: "YYYY-MM-DD"
  tags: ["refactoring", "database"]
  jira_ticket: "PROJ-1234"
```

### Field Explanations

#### Top-Level Fields

- **context_name** (required): Unique identifier for this context
  - Use snake_case
  - Examples: `product_refactor`, `rest_to_graphql`, `deprecated_api_v1`

- **description** (required): Human-readable explanation
  - 1-2 sentences explaining what this tracks

- **version** (recommended): Version or date
  - Format: `YYYY-MM-DD` or semantic version
  - Update when making changes

#### Pattern Fields

##### Required for All Patterns:
- **id**: Unique identifier within this context
- **pattern**: Regular expression to match (case-insensitive)
- **reason**: Why this pattern matters

##### Obsolete Pattern Fields:
- **severity**: How critical is this? (`critical`, `high`, `medium`, `low`)
- **replacement**: What should be used instead
- **scope**: Where this applies (see Scope section)

##### Transitional Pattern Fields:
- **expires**: Date when this becomes obsolete (`YYYY-MM-DD`)
- **scope**: Where this applies

##### Current Pattern Fields:
- **scope**: Where this applies

#### Scope Specification

Scope controls which files a pattern applies to:

```yaml
scope:
  include: ["frontend/", "api/", "services/"]  # Only these paths
  exclude: ["tests/", "migrations/", "__tests__/"]  # Skip these
```

**Rules:**
1. If no scope: applies to all files
2. Excludes checked first (higher priority)
3. If includes specified: file must match at least one
4. Patterns are substring matches (not globs)

**Examples:**
```yaml
# Apply only to frontend, except tests
scope:
  include: ["frontend/"]
  exclude: ["tests/", ".test.", ".spec."]

# Apply to backend, but not migrations
scope:
  include: ["backend/"]
  exclude: ["migrations/"]

# Apply to all API-related files
scope:
  include: ["api/", "routes/", "controllers/"]
```

### Pattern Matching

Patterns are matched against:
1. **Finding message** (highest priority)
2. **Finding rule name**
3. **Code snippet** (if available)

**Pattern Tips:**
- Use `\\` for literal dots: `product\\.price` matches `product.price`
- Use `(?:a|b|c)` for alternatives: `(?:unit_price|retail_price)`
- Use `(?!...)` for negative lookahead: `product_id(?!_variant)` matches `product_id` but not `product_id_variant`
- Patterns are case-insensitive by default

**Examples:**
```yaml
# Match field access
pattern: "product\\.(unit_price|retail_price)"

# Match function calls
pattern: "getProductPrice\\("

# Match foreign keys (but not variant IDs)
pattern: "product_id(?!_variant)"

# Match API endpoints
pattern: "/api/products/[^/]+/price"

# Match model initialization
pattern: "Product\\.init\\([^)]*price"
```

## Complete Example: Database Refactoring

```yaml
context_name: "orders_refactor_2024"
description: "Orders table split into orders and order_items"
version: "2024-02-01"

patterns:
  obsolete:
    - id: "old_orders_products"
      pattern: "orders\\.products"
      reason: "Products moved to order_items table"
      replacement: "order_items.product_variant_id with JOIN to orders"
      severity: "critical"
      scope:
        include: ["backend/", "api/"]
        exclude: ["migrations/"]

    - id: "old_orders_total_calc"
      pattern: "SELECT SUM\\(price\\) FROM orders"
      reason: "Price calculation now requires JOIN to order_items"
      replacement: "SELECT SUM(oi.price * oi.quantity) FROM orders o JOIN order_items oi"
      severity: "high"
      scope:
        include: ["backend/services/"]

  current:
    - id: "new_order_items_join"
      pattern: "JOIN order_items ON orders\\.id = order_items\\.order_id"
      reason: "Correct way to access order products"
      scope:
        include: ["backend/"]

    - id: "new_order_total"
      pattern: "order_items\\.(?:price|quantity)"
      reason: "Correct order total calculation"
      scope:
        include: ["backend/", "api/"]

  transitional:
    - id: "legacy_orders_view"
      pattern: "orders_with_products_view"
      reason: "Database view for backward compatibility during migration"
      expires: "2024-04-01"
      scope:
        include: ["backend/", "api/"]

relationships:
  - type: "replaces"
    from: "old_orders_products"
    to: "new_order_items_join"
    note: "Normalized data model"

metadata:
  author: "backend_team"
  created: "2024-02-01"
  tags: ["database", "normalization", "orders"]
  jira_ticket: "BACKEND-567"
  migration: "backend/migrations/20240201_split_orders_table.sql"
```

## Example: API Deprecation

```yaml
context_name: "api_v1_deprecation"
description: "Deprecate REST API v1 in favor of GraphQL"
version: "1.0.0"

patterns:
  obsolete:
    - id: "rest_v1_endpoints"
      pattern: "/api/v1/"
      reason: "API v1 deprecated, use GraphQL"
      replacement: "GraphQL queries via /graphql"
      severity: "high"
      scope:
        include: ["frontend/", "mobile/"]

    - id: "rest_client_import"
      pattern: "import.*RestClient.*from.*'@/api/v1'"
      reason: "Use GraphQL client instead"
      replacement: "import { useQuery } from '@apollo/client'"
      severity: "medium"
      scope:
        include: ["frontend/"]

  current:
    - id: "graphql_queries"
      pattern: "(?:useQuery|useMutation)\\("
      reason: "Correct API access via GraphQL"
      scope:
        include: ["frontend/", "mobile/"]

    - id: "graphql_endpoint"
      pattern: "/graphql"
      reason: "Current API endpoint"
      scope:
        include: ["frontend/", "backend/"]

  transitional:
    - id: "rest_v1_wrapper"
      pattern: "restToGraphqlAdapter"
      reason: "Temporary adapter during migration"
      expires: "2024-06-01"
      scope:
        include: ["frontend/utils/"]

metadata:
  author: "api_team"
  created: "2024-01-15"
  tags: ["api", "graphql", "deprecation"]
  documentation: "https://docs.company.com/graphql-migration"
```

## How to Use Semantic Contexts

### 1. Create Your Context File

Place YAML files in this directory:
```
theauditor/insights/semantic_rules/your_context.yaml
```

### 2. Run TheAuditor with Context

```bash
# Run full analysis with semantic context
aud full --context theauditor/insights/semantic_rules/your_context.yaml

# Run just the semantic analysis
aud context --file theauditor/insights/semantic_rules/your_context.yaml

# Generate detailed report
aud context --file your_context.yaml --verbose --output report.json
```

### 3. Interpret Results

TheAuditor will report:
- **❌ OBSOLETE**: Findings matching obsolete patterns (need fixing)
- **✅ CURRENT**: Findings matching current patterns (correct)
- **⏳ TRANSITIONAL**: Findings using transitional patterns (OK for now)
- **⚠️ MIXED**: Files with both obsolete and current patterns

### 4. Track Migration Progress

The semantic context engine tracks:
- Files fully migrated (only current patterns)
- Files needing migration (obsolete patterns found)
- Mixed files (partially migrated)
- Migration percentage

## Best Practices

### Pattern Design

1. **Be Specific**: `product\\.price` is better than just `price`
2. **Use Anchors**: `product_id(?!_variant)` avoids false matches
3. **Test Patterns**: Use regex testers before deploying
4. **Document Why**: Always explain the reason

### Scope Management

1. **Exclude Tests**: Tests often contain example of old patterns
2. **Exclude Migrations**: Migration files show both old and new
3. **Include Relevant**: Only scan files that should be updated

### Severity Guidelines

- **CRITICAL**: Data corruption, security issues, breaks functionality
- **HIGH**: Deprecated APIs, incorrect business logic
- **MEDIUM**: Code smells, sub-optimal patterns
- **LOW**: Style issues, minor optimizations

### Transitional Patterns

Use transitional patterns for:
- Gradual migrations (dual support during rollout)
- Backward compatibility layers
- Feature flags during transitions

Always set realistic expiration dates!

### Versioning

Update the version field when:
- Adding new patterns
- Changing pattern semantics
- Updating expiration dates
- Refining scope rules

## Examples in This Directory

- **refactoring.yaml**: Product to ProductVariant pricing migration
- *(Add your own examples here!)*

## Troubleshooting

### "No patterns matched"
- Check if your pattern regex is correct
- Verify scope includes the right paths
- Run `aud detect-patterns` first to see what findings exist

### "Too many false positives"
- Narrow the scope (exclude test files)
- Make patterns more specific
- Use negative lookaheads

### "Pattern not matching expected findings"
- Check if pattern is case-sensitive (it shouldn't be)
- Verify you're escaping special regex characters
- Test pattern against actual finding messages

## Integration with TheAuditor

Semantic contexts integrate with:
- **FCE (Factual Correlation Engine)**: Loads contexts automatically
- **Report Generator**: Includes semantic analysis section
- **Extraction/Chunking**: Semantic findings in `.pf/readthis/`

## Contributing Context Templates

If you create a useful semantic context template, consider:
1. Generalizing it for broader use
2. Adding it to this directory as an example
3. Documenting the use case clearly
4. Sharing with the community

## Support

For questions about semantic contexts:
- Check `CLAUDE.md` in repository root
- See examples in this directory
- Open an issue: https://github.com/anthropics/theauditor/issues

---

**Remember**: Semantic contexts are YOUR business logic. TheAuditor provides the engine, you provide the knowledge!
