## Why

The extraction pipeline is producing malformed data that causes database constraint violations and crashes. JavaScript extractors output dict objects where strings are expected, lack deduplication for ORM relationships, and Python extractors have incorrect deduplication keys. This results in ~5,800+ corrupted records, pipeline failures, and unreliable taint analysis.

## What Changes

- **CRITICAL**: Fix JavaScript GraphQL resolver param extraction producing dict objects instead of strings (framework_extractors.js:529-682)
- **CRITICAL**: Add ORM relationship deduplication to JavaScript extractors matching Python implementation (core_ast_extractors.js:959-1086)
- Fix TypeScript parameter extraction returning nested dict nodes instead of unwrapped strings (typescript_impl.py)
- Add bidirectional relationship generation for Sequelize matching SQLAlchemy/Django patterns (sequelize_extractors.js:69-100)
- **BREAKING**: Remove ALL defensive type conversions from storage.py - hard fail on wrong types per ZERO FALLBACK POLICY
- Add schema validation at extraction layer to prevent type mismatches reaching database
- Create comprehensive test fixtures validating extraction output types and deduplication

## Impact

- Affected specs: extraction, data-storage
- Affected code:
  - JavaScript: framework_extractors.js, core_ast_extractors.js, sequelize_extractors.js, angular_extractors.js, bullmq_extractors.js
  - Python: typescript_impl.py, framework_extractors.py, storage.py
- Database tables: function_call_args, orm_relationships, graphql_resolver_params
- Downstream: All taint analysis, FCE, code intelligence features relying on clean extraction data