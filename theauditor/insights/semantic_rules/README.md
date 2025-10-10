# Semantic Context Rules Directory

This directory contains user-defined semantic context YAML files that teach TheAuditor about YOUR specific business logic, refactoring patterns, and codebase semantics.

## Quick Start

1. **Copy the example**: Start with `refactoring.yaml` as a template
2. **Customize for your needs**: Edit patterns to match YOUR refactorings
3. **Run analysis**: `aud context --file your_context.yaml`
4. **Review results**: See obsolete vs current pattern usage

## What's Included

### Files in This Directory

- **`refactoring.yaml`**: Complete example of Product → ProductVariant pricing migration
  - Shows obsolete patterns (old schema)
  - Shows current patterns (new schema)
  - Includes transitional patterns (migration period)
  - Demonstrates all features: scoping, severity, relationships

- **`templates_instructions.md`**: Comprehensive documentation
  - YAML format specification
  - Field-by-field explanations
  - Multiple examples (refactoring, API deprecation, schema changes)
  - Best practices and troubleshooting

### How to Create Your Own Context

1. **Identify your refactoring**:
   - What changed in your codebase?
   - What patterns are now obsolete?
   - What patterns are correct?

2. **Create YAML file**:
   ```bash
   cp refactoring.yaml my_refactor.yaml
   # Edit my_refactor.yaml with your patterns
   ```

3. **Run TheAuditor**:
   ```bash
   aud context --file semantic_rules/my_refactor.yaml
   ```

4. **Review report**:
   - ❌ Obsolete patterns: Files that need updating
   - ✅ Current patterns: Files that are correct
   - ⚠️ Mixed files: Partially migrated files

## Use Cases

### ✅ Perfect For:
- **Database refactorings**: Schema migrations, table splits, field moves
- **API deprecations**: REST → GraphQL, API v1 → v2
- **Architecture changes**: Service layer refactors, pattern enforcement
- **Code migrations**: React class → hooks, Vue 2 → 3
- **Business rule changes**: Policy updates, workflow changes

### ❌ Not For:
- **General security issues**: Use `theauditor/rules/` instead
- **Universal code smells**: Belong in core TheAuditor
- **One-time searches**: Use `grep` or `aud detect-patterns`

## Integration with TheAuditor

### Standalone Usage
```bash
# Run just semantic context analysis
aud context --file semantic_rules/my_context.yaml

# Verbose output with detailed findings
aud context --file my_context.yaml --verbose

# Export to JSON
aud context --file my_context.yaml --output report.json
```

### Integrated with Full Analysis
```bash
# Run full analysis with semantic context
aud full --context semantic_rules/my_context.yaml
```

The semantic context results will be included in:
- `.pf/raw/fce.json` (FCE output)
- `.pf/readthis/semantic_*.json` (AI-optimized chunks)
- Final consolidated report

## Example Output

```
SEMANTIC CONTEXT ANALYSIS: product_pricing_refactor
================================================================================

Version: 2024-01-15
Total Findings Analyzed: 47
Classified: 35 | Unclassified: 12

MIGRATION PROGRESS:
  Total Files: 21
  Fully Migrated: 10 (48%)
  Need Migration: 8
  Mixed State: 3

================================================================================
❌ OBSOLETE PATTERNS (15 occurrences)
================================================================================

HIGH Severity (12 occurrences):
  • frontend/cart.js:47 [old_product_price]
    Reason: Pricing fields moved to ProductVariant model
    Suggested: product_variant.retail_price
  • api/orders.js:89 [old_product_sku]
    Reason: SKU is now unique per variant, not per product
    Suggested: product_variant.sku
  ... and 10 more

================================================================================
✅ CURRENT PATTERNS (20 occurrences)
================================================================================
  20 occurrences of correct patterns
  Use --verbose flag for details

================================================================================
⚠️ MIXED FILES (3 files need attention)
================================================================================
  • services/pricing.js
    Obsolete: 5 | Current: 3
  • backend/api/products.js
    Obsolete: 2 | Current: 8
  ... and 1 more
```

## Documentation

For complete documentation, see:
- **`templates_instructions.md`**: Detailed YAML format guide
- **`CLAUDE.md`** (repository root): Architecture overview
- **`theauditor/insights/semantic_context.py`**: Source code documentation

## Support

- **Examples**: Study `refactoring.yaml` for all features
- **Questions**: Open issue at https://github.com/anthropics/theauditor/issues
- **Documentation**: Read `templates_instructions.md` first

## Contributing

Created a useful semantic context template? Consider:
1. Generalizing it for broader use
2. Adding it to this directory as an example
3. Documenting the use case clearly
4. Sharing with the community

---

**Remember**: Semantic contexts are YOUR business logic. TheAuditor provides the engine, you provide the knowledge!
