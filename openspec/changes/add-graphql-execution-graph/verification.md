# Verification Report - add-graphql-execution-graph
Generated: 2025-10-16T12:22:00Z
SOP Reference: Standard Operating Procedure v4.20

## Hypotheses & Evidence

1. The indexer does not currently recognise `.graphql` or `.gql` schema files.
   - Evidence: `theauditor/indexer/config.py:128` enumerates `SUPPORTED_AST_EXTENSIONS` without any GraphQL extensions.
   - Evidence: `rg -n "graphql" theauditor/indexer/extractors` returned no matches, confirming there is no dedicated GraphQL extractor module.

2. The repository database lacks GraphQL-specific tables today.
   - Evidence: Running `rg -n "graphql" theauditor/indexer/database.py` and `rg -n "graphql" theauditor/indexer/schema.py` returned no hits, showing the schema contract has no GraphQL tables.

3. The full pipeline has no GraphQL phase or command wiring.
   - Evidence: `theauditor/pipelines.py:565-619` categorises Stage 2 commands (`workset`, `graph build`, `cfg`, `metadata`) and Stage 3 tracks without any GraphQL-related entries.

4. Existing security rules rely on resolver heuristics rather than an execution graph.
   - Evidence: `theauditor/rules/security/api_auth_analyze.py:301-321` scans the generic `function_call_args` table for names containing `mutation` or `resolver` to guess GraphQL resolvers.
   - Evidence: `theauditor/rules/security/input_validation_analyze.py:505-520` loops through string-matched GraphQL function names to flag potential injection.

5. Factual Correlation Engine summaries do not surface GraphQL findings yet.
   - Evidence: `rg -n "graphql" theauditor/fce.py` returned no matches, so FCE has no awareness of GraphQL-specific data when consolidating findings.

## Discrepancies & Alignment Notes
- The current heuristics in `api_auth_analyze.py` and `input_validation_analyze.py` produce medium-confidence findings because they cannot prove resolver mappings; the new execution graph must replace those code paths.
- No tables exist to persist resolver-to-field relationships, so the GraphQL feature must extend both `schema.py` and `database.py` alongside the batch writers in `DatabaseManager`.

## Conclusion
GraphQL artefacts are entirely absent from the indexer, database schema, pipeline wiring, and FCE aggregation. Security rules fall back to name-matching heuristics because there is no resolver execution graph. The new change must introduce first-class GraphQL extraction, persistence, pipeline integration, and rule/FCE consumers to remove guesswork while staying database-first.
