## MODIFIED Requirements
### Requirement: TypeScript Taint Source Extraction
The indexer MUST record fully-qualified accessor names (e.g., `req.body`, `request.params`) in `symbols.name` for JavaScript/TypeScript property accesses so taint pattern matching remains consistent across languages.

#### Scenario: Express request handler
- **GIVEN** a TypeScript controller that reads from `req.body`
- **WHEN** `aud index` completes
- **THEN** `symbols` MUST contain a row with `name = 'req.body'` and `type IN ('property','symbol','call')`
- **AND** the taint analyzer MUST report `req.body` as a source in `taint_analysis.json`

### Requirement: Taint Source Fallback Safety Net
The taint analyzer MUST fall back to `assignments` and `function_call_args` when dotted property symbols are missing, surfacing flows instead of silently returning zero sources.

#### Scenario: Missing dotted symbol but assignments present
- **GIVEN** the database lacks `symbols.name = 'req.body'` but contains `function_call_args.argument_expr = 'req.body'`
- **WHEN** taint analysis runs
- **THEN** the analyzer MUST still emit a `req.body` source (with fallback metadata) and document the fallback in the pipeline log.
