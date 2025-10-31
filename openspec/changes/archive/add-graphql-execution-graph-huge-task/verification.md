# Verification Report - add-graphql-execution-graph
Generated: 2025-10-31 (Updated Post-Refactor)
SOP Reference: Standard Operating Procedure v4.20

## Phase 0: Verification Phase Report (Pre-Implementation)

**CRITICAL**: This verification was performed against the CURRENT refactored codebase (post-modular architecture changes). All hypotheses tested against source code, NOT assumptions.

### Hypotheses & Verification Results

#### Hypothesis 1: The indexer does not currently recognise `.graphql` or `.gql` schema files
- **Verification**: ✅ CONFIRMED
- **Evidence**:
  - Read `theauditor/indexer/config.py:128-138` - SUPPORTED_AST_EXTENSIONS lists only: `.py`, `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`, `.tf`, `.tfvars`
  - Executed `rg -n "graphql" theauditor/indexer/extractors` - NO matches found
  - Listed all files in `theauditor/indexer/extractors/` - NO graphql.py exists
  - Files present: javascript.py, python.py, terraform.py, docker.py, sql.py, prisma.py, json_config.py, github_actions.py, rust.py, generic.py

#### Hypothesis 2: The repository database lacks GraphQL-specific tables
- **Verification**: ✅ CONFIRMED
- **Evidence**:
  - Queried `.pf/repo_index.db` via Python sqlite3 - NO tables with name LIKE '%graphql%'
  - Read `theauditor/indexer/schema.py:62-70` - TABLES dict merges 7 module registries (CORE_TABLES, SECURITY_TABLES, FRAMEWORKS_TABLES, PYTHON_TABLES, NODE_TABLES, INFRASTRUCTURE_TABLES, PLANNING_TABLES) - TOTAL 108 tables
  - Searched `theauditor/indexer/schemas/` directory - NO graphql_schema.py exists
  - Schema modules present: core_schema.py, security_schema.py, frameworks_schema.py, python_schema.py, node_schema.py, infrastructure_schema.py, planning_schema.py, utils.py

#### Hypothesis 3: Database architecture has been refactored from monolithic to mixin-based
- **Verification**: ✅ CONFIRMED (NEW FINDING - invalidates old assumptions)
- **Evidence**:
  - Read `theauditor/indexer/database/__init__.py:44-73` - DatabaseManager now uses multiple inheritance with 7 mixins
  - Listed `theauditor/indexer/database/` - Found: base_database.py, core_database.py, python_database.py, node_database.py, infrastructure_database.py, security_database.py, frameworks_database.py, planning_database.py
  - Read `frameworks_database.py:1-81` - Pattern: FrameworksDatabaseMixin with add_* methods using self.generic_batches
  - **CRITICAL**: Old proposal references `database.py` which no longer exists - replaced with database/ package

#### Hypothesis 4: Storage logic has been extracted from orchestrator
- **Verification**: ✅ CONFIRMED (NEW FINDING - invalidates old assumptions)
- **Evidence**:
  - Read `theauditor/indexer/storage.py:1-150` - DataStorer class with 66 handler methods
  - Read `theauditor/indexer/orchestrator.py:30-65` - Imports DatabaseManager from .database and DataStorer from .storage
  - **CRITICAL**: Old proposal assumes direct DatabaseManager batch writing - now requires DataStorer handler registration

#### Hypothesis 5: Pipeline staging has been reorganized into 4 stages with parallel tracks
- **Verification**: ✅ CONFIRMED (NEW FINDING - invalidates old assumptions)
- **Evidence**:
  - Read `theauditor/pipelines.py:594-629` - Pipeline now uses: foundation_commands (Stage 1), data_prep_commands (Stage 2), track_a_commands (Stage 3A taint), track_b_commands (Stage 3B static/graph), track_c_commands (Stage 3C network), final_commands (Stage 4)
  - **CRITICAL**: Old proposal says "Stage 2 right after graph build" - now Stage 2 is data_prep_commands with specific categorization logic

#### Hypothesis 6: Security rules use heuristics for GraphQL detection
- **Verification**: ✅ CONFIRMED
- **Evidence**:
  - Read `theauditor/rules/security/api_auth_analyze.py:318-347` via grep - Method `_check_graphql_mutations()` scans function_call_args for resolver/Mutation patterns with string matching
  - Found constants at line 53: GRAPHQL_MUTATIONS = frozenset(['mutation', 'Mutation', 'createMutation', ...])
  - Found constants at line 161: GRAPHQL_PATTERNS = frozenset(['graphql', 'GraphQL', 'apollo', 'relay', ...])
  - Comment at line 539-541: "Can't parse GraphQL schema for auth directives - Need GraphQL-specific parsing"

#### Hypothesis 7: FCE has no GraphQL awareness
- **Verification**: ✅ CONFIRMED
- **Evidence**:
  - Executed `rg -n "graphql" theauditor/fce.py` - NO matches
  - Executed `rg -n "graphql" theauditor/taint/sources.py` - NO matches

### Discrepancies Found

**MAJOR DISCREPANCY 1**: Schema architecture has fundamentally changed
- **Old Assumption**: Add tables directly to `theauditor/indexer/schema.py`
- **Reality**: Must create `theauditor/indexer/schemas/graphql_schema.py` following modular pattern
- **Impact**: Schema design section of proposal is WRONG

**MAJOR DISCREPANCY 2**: Database manager has been split into mixins
- **Old Assumption**: Add batch methods to monolithic `database.py`
- **Reality**: Must create `theauditor/indexer/database/graphql_database.py` as GraphQLDatabaseMixin
- **Impact**: Database integration section of proposal is WRONG

**MAJOR DISCREPANCY 3**: Storage layer now handles data insertion
- **Old Assumption**: Extractors directly call DatabaseManager methods
- **Reality**: Must register handlers in DataStorer.handlers dict mapping data_type → handler method
- **Impact**: Extractor integration section of proposal is WRONG

**MAJOR DISCREPANCY 4**: Pipeline staging is now 4 stages with track categorization
- **Old Assumption**: "Add command to Stage 2 after graph build"
- **Reality**: Must categorize command into correct track (data_prep_commands) with conditional logic
- **Impact**: Pipeline integration section of proposal is WRONG

### Conclusion

**GraphQL is completely absent** (original hypothesis confirmed), BUT the **architectural foundation has been refactored** since original proposal was written. The proposal must be REWRITTEN to:

1. Follow modular schema pattern (schemas/graphql_schema.py)
2. Follow mixin database pattern (database/graphql_database.py)
3. Follow storage handler pattern (register in storage.py)
4. Follow 4-stage pipeline pattern (categorize into data_prep_commands)
5. Update ALL file paths and architectural references

**Original verification was CORRECT about absence of GraphQL, but WRONG about how to add it.**
