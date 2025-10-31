# TheAuditor Indexer System - Complete Architecture

## SYSTEM OVERVIEW

**Two databases:**
- `repo_index.db` (91MB): Raw extracted facts - PRIMARY database used by ALL analysis
- `graphs.db` (79MB): Optional pre-computed graph structures for visualization only

**Key characteristics:**
- Two-phase extraction (transformed JSX mode + preserved JSX mode)
- AST-based analysis (NO regex for code analysis)
- Schema-driven database (108 tables)
- Modular extractor architecture (10 language support)

## CORE ARCHITECTURE LAYERS

### LAYER 1: ORCHESTRATION (orchestrator.py, 740 lines)

Main class: `IndexerOrchestrator`

Key methods:
- `index()` [line 212]: Main indexing workflow
- `_process_file()` [line 567]: Process single file
- `_get_or_parse_ast()` [line 643]: AST retrieval/parsing
- `_select_extractor()` [line 677]: Language selection
- `_store_extracted_data()` [line 698]: Storage delegation

Components:
- ASTParser: AST parsing for all languages
- ASTCache: Persistent caching by file SHA256
- DatabaseManager: SQLite operations
- FileWalker: Directory traversal with monorepo detection
- ExtractorRegistry: Dynamic language extractor discovery
- DataStorer: Handler dispatch for storage operations

**Critical Design: Two-Pass JSX Processing**

First Pass (Transformed Mode):
- JSX converted to React.createElement() calls
- Enables data flow and taint analysis
- Stored in standard tables (symbols, assignments, function_call_args)

Second Pass (Preserved Mode):
- Original JSX syntax kept intact
- Enables JSX structural/accessibility rule analysis  
- Stored in parallel _jsx tables (symbols_jsx, assignments_jsx, etc.)

Why both? TypeScript compiler only operates in ONE JSX mode, but analysis needs both views.

### LAYER 2: SCHEMA SYSTEM (schema.py + schemas/, ~2,000 lines)

Single source of truth for all 108 table definitions.

Core classes (schemas/utils.py):
- `Column`: Database column with type and constraints
- `ForeignKey`: Relationship metadata for JOIN generation
- `TableSchema`: Complete table schema definition

Query builders:
- `build_query()`: Dynamic SELECT with schema validation
- `build_join_query()`: Auto-discover JOINs using foreign keys
- `validate_all_tables()`: Check database matches schema

### LAYER 3: EXTRACTION (extractors/, 10 modules)

Supported languages:
- Python: `.py, .pyx` → `PythonExtractor`
- JavaScript/TypeScript: `.js, .jsx, .ts, .tsx, .mjs, .cjs, .vue` → `JavaScriptExtractor`
- Configuration: Generic files → `GenericExtractor`
- Docker: Dockerfile, docker-compose → `DockerExtractor`
- GitHub Actions: `.github/workflows/*.yml` → `GitHubWorkflowExtractor`
- Terraform: `.tf, .tfvars` → `TerraformExtractor`
- Other: Prisma, Rust, SQL

Plugin architecture: Auto-discovery via file naming convention
- No hardcoded registry needed
- BaseExtractor ABC defines interface
- ExtractorRegistry._discover() loads modules dynamically

### LAYER 4: STORAGE (storage.py, 1,200+ lines)

Handler dispatch pattern:
- Single entry point: `store(file_path, extracted, jsx_pass)`
- 60+ handler methods mapping data_type → `db_manager.add_*()`
- JSX pass routing (jsx_pass=True → _jsx tables)

### LAYER 5: DATABASE (database/, 2,313 lines total)

Multiple inheritance architecture:
- `BaseDatabaseManager` (626 lines): Core infrastructure
- `CoreDatabaseMixin` (295 lines, 16 methods)
- `PythonDatabaseMixin` (478 lines, 34 methods)
- `NodeDatabaseMixin` (234 lines, 14 methods)
- `InfrastructureDatabaseMixin` (358 lines, 18 methods)
- `SecurityDatabaseMixin` (95 lines, 4 methods)
- `FrameworksDatabaseMixin` (80 lines, 4 methods)
- `PlanningDatabaseMixin` (44 lines, stub)

Total: 105 tables, 93 add_*() methods

**Generic Batching System:**
- Single `generic_batches` dict instead of 93 individual batch lists
- `flush_generic_batch(table_name)` instead of 93 flush methods
- Consistent batching logic for all tables

## INDEXING WORKFLOW

1. **Framework Detection** → Framework list
2. **File Discovery** → File metadata with hash/LOC
3. **Batch Parse JS/TS** (First Pass - Transformed Mode)
4. **Process All Files** (Single Pass)
   - Read file content
   - Parse or retrieve cached AST
   - Select appropriate extractor
   - Extract data
   - Store to database
5. **Cross-File Parameter Resolution** (Phase 6)
6. **Store Frameworks & Safe Sinks**
7. **JSX Preserved Mode** (Second Pass - Unconditional)
8. **Final Flush, Commit, Report**

## COMPLETE TABLE LIST (108 TABLES)

**CORE (21):** files, config_files, refs, symbols, symbols_jsx, assignments, assignments_jsx, assignment_sources, function_call_args, function_call_args_jsx, function_returns, function_returns_jsx, variable_usage, object_literals, cfg_blocks, cfg_edges, cfg_block_statements, findings_consolidated, etc.

**PYTHON (34):** ORM models, routes, decorators, async functions, Django views, DRF serializers, Celery tasks, pytest fixtures, etc.

**NODE (17):** React components/hooks, Vue components/hooks, TypeScript annotations, package configs, frameworks, etc.

**SECURITY (5):** sql_objects, sql_queries, sql_query_tables, jwt_patterns, env_var_usage

**FRAMEWORKS (5):** orm_queries, orm_relationships, prisma_models, api_endpoints, api_endpoint_controls

**INFRASTRUCTURE (18):** Docker, Terraform, CDK, GitHub Actions configurations

**PLANNING (5):** plans, plan_tasks, plan_specs, code_snapshots, code_diffs

## KEY DESIGN PATTERNS

1. **Schema-Driven Architecture**: Single source of truth in schema.py
2. **Generic Batching**: Eliminates 93 individual batch lists
3. **Extractor Plugin Architecture**: Auto-discovery, no hardcoded registry
4. **Handler Dispatch**: Clean separation of storage logic
5. **Multiple Inheritance**: Logical domain-based organization
6. **Two-Pass JSX Processing**: Different analysis needs, different table views
7. **File Path Responsibility**: Orchestrator provides, storage uses, single source of truth

## CRITICAL RULES

**RULE 1: NO FALLBACKS EVER**
- Database regenerated fresh every 'aud index'
- Hard failure exposes bugs immediately

**RULE 2: USE AST, NOT REGEX**
- Language extractors MUST use AST
- Regex only for routes, SQL DDL, config patterns

**RULE 3: SCHEMA IS SINGLE SOURCE OF TRUTH**
- Never hardcode column names
- Use TableSchema.column_names() everywhere

**RULE 4: DATABASE ASSUMES TABLES EXIST**
- No table existence checks
- No graceful degradation

**RULE 5: EVERY EXTRACTION NEEDS A HANDLER**
- Handler method in DataStorer
- add_*() method in DatabaseManager
- Schema table definition in schema.py

## FILE REFERENCES

Main entry points:
- `orchestrator.py:212` - index() main workflow
- `orchestrator.py:417` - JSX second pass logic
- `schema.py:62` - TABLES registry
- `storage.py:112` - DataStorer.store() dispatch
- `database/base_database.py:172` - flush_generic_batch()
- `database/__init__.py` - DatabaseManager class definition
- `extractors/__init__.py` - BaseExtractor and ExtractorRegistry

## SUMMARY STATISTICS

- **Total Tables**: 108
- **Database Methods**: 93 add_*() methods
- **Storage Handlers**: 60+ handler methods
- **Extractors**: 10 language support
- **Code Size**: ~9,500 lines of code (indexer/)
- **Indexing Time**: 2-5 minutes (typical projects)
- **Database Sizes**: repo_index.db 80-100MB, graphs.db 60-80MB

