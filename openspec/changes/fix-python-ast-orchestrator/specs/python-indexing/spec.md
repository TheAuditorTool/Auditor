# Python Indexing Specification Delta

## MODIFIED Requirements

### Requirement: Python AST Traversal Efficiency

The Python indexing pipeline SHALL walk each AST file exactly once during extraction, caching parsed nodes in memory for all extractors to access.

**Rationale**: Current implementation walks each AST 82 times per file (once per extractor function), causing 80-90x performance degradation. Single-walk architecture with node caching eliminates redundant traversals while preserving domain module organization.

#### Scenario: Single Walk Per File

- **GIVEN** a Python file with 500 AST nodes
- **WHEN** the file is indexed
- **THEN** the AST SHALL be traversed exactly once
- **AND** all nodes SHALL be cached in memory by node type
- **AND** all extractors SHALL receive cached nodes (not raw tree)
- **AND** the total node visits SHALL be 500 (not 41,000)

#### Scenario: Node Cache Structure

- **GIVEN** a Python file has been parsed into an AST
- **WHEN** the orchestrator builds the node cache
- **THEN** the cache SHALL be a dictionary mapping node type names to lists of nodes
- **AND** the cache SHALL include all node types present in the tree (ClassDef, FunctionDef, Assign, etc.)
- **AND** the cache SHALL be built in O(n) time where n = number of nodes
- **AND** the cache SHALL be released after extraction completes (no persistent storage)

#### Scenario: Extractor Cache Access

- **GIVEN** the orchestrator has built a node cache
- **WHEN** an extractor function is called
- **THEN** the extractor SHALL receive the node cache as a parameter
- **AND** the extractor SHALL filter cached nodes by type (e.g., `node_cache.get('ClassDef', [])`)
- **AND** the extractor SHALL NOT call `ast.walk()` on the raw tree
- **AND** the extractor SHALL produce identical output to the original implementation

#### Scenario: Performance Target

- **GIVEN** a project with 1,000 Python files averaging 500 nodes each
- **WHEN** indexing is performed
- **THEN** the total AST traversal time SHALL be <1 second
- **AND** the total node visits SHALL be ~500,000 (1 walk × 1,000 files × 500 nodes)
- **AND** this represents an 80-90x speedup compared to the original 82-walk implementation
- **AND** memory overhead from caching SHALL be <10% of baseline

#### Scenario: Backward Compatibility

- **GIVEN** the Python indexing pipeline has been optimized
- **WHEN** a file is indexed
- **THEN** the external API SHALL remain unchanged (`extract(file_info, content, tree)`)
- **AND** the database schema SHALL remain unchanged (no new tables)
- **AND** the extracted data SHALL match the original implementation byte-for-byte
- **AND** all existing tests SHALL pass without modification

---

### Requirement: Extractor Domain Module Organization

The Python extraction pipeline SHALL preserve domain module organization, with extractors grouped by concern (framework, core, Flask, async, security, testing, types, ORM, validation, Django, tasks/GraphQL, CFG, CDK).

**Rationale**: Consolidating extractors into a monolithic visitor class creates a maintainability nightmare and failed during implementation. The "thin orchestrator wrapper" pattern preserves clean separation of concerns while achieving performance goals.

#### Scenario: Orchestrator Responsibility

- **GIVEN** the Python indexing pipeline
- **WHEN** a file is indexed
- **THEN** the orchestrator SHALL walk the AST once and build the node cache
- **AND** the orchestrator SHALL call domain module extraction functions with the cache
- **AND** the orchestrator SHALL aggregate results from all extractors
- **AND** the orchestrator SHALL NOT contain extractor logic (only orchestration)
- **AND** the orchestrator SHALL be <200 lines (10KB max)

#### Scenario: Domain Module Independence

- **GIVEN** the Python extraction pipeline
- **WHEN** extractors are called by the orchestrator
- **THEN** each domain module (framework, core, Flask, etc.) SHALL remain independent
- **AND** extractors SHALL NOT depend on each other's output
- **AND** extractors SHALL be testable in isolation (by passing mock cache)
- **AND** domain expertise SHALL remain co-located in domain modules

#### Scenario: Extractor Function Signature

- **GIVEN** a Python extractor function
- **WHEN** the function is called
- **THEN** the signature SHALL be `extract_X(node_cache: Dict[str, List[ast.Node]], file_info: FileInfo) -> dict`
- **AND** the function SHALL NOT accept raw tree as parameter (prevents accidental re-walking)
- **AND** the function SHALL filter cached nodes by type
- **AND** the function SHALL preserve all extraction logic from the original implementation

---

## ADDED Requirements

### Requirement: Node Cache Lifecycle

The Python indexing pipeline SHALL manage node cache lifecycle per-file, building the cache at extraction start and releasing it at extraction end.

**Rationale**: In-memory caching avoids disk I/O overhead and schema complexity, while per-file lifecycle prevents memory accumulation.

#### Scenario: Cache Creation

- **GIVEN** a Python file is being indexed
- **WHEN** the orchestrator begins extraction
- **THEN** a node cache SHALL be created for that file only
- **AND** the cache SHALL be built by walking the AST once
- **AND** the cache build time SHALL be <10ms per file

#### Scenario: Cache Lifetime

- **GIVEN** a node cache exists for a file
- **WHEN** extraction completes
- **THEN** the cache SHALL be released (garbage collected)
- **AND** the cache SHALL NOT persist across files
- **AND** the cache SHALL NOT be written to the database

#### Scenario: Cache Memory Overhead

- **GIVEN** a Python file with 10,000 lines of code (~5,000 nodes)
- **WHEN** the node cache is built
- **THEN** the cache memory overhead SHALL be <2MB
- **AND** the overhead SHALL be acceptable for typical projects
- **AND** memory SHALL be released after extraction

---

### Requirement: Nested Walk Verification

The Python extractor refactor SHALL verify nested `ast.walk()` calls to determine if they are functionally necessary or redundant traversals.

**Rationale**: Some nested walks serve functional purposes (e.g., traversing inside a specific FunctionDef body), while others are redundant re-traversals of the entire tree. Blind removal risks breaking extraction logic.

#### Scenario: Verification Phase

- **GIVEN** an extractor module contains nested `ast.walk()` calls
- **WHEN** the refactor is planned
- **THEN** the coder MUST read the surrounding code to determine purpose
- **AND** functional nested walks SHALL be preserved (or converted to nested filtering)
- **AND** redundant nested walks SHALL be removed (replaced with cache lookups)
- **AND** the determination SHALL be documented in `verification.md`

#### Scenario: Functional Nested Walk

- **GIVEN** a nested walk traverses a specific subtree (e.g., inside a FunctionDef body)
- **WHEN** the extractor is refactored
- **THEN** the nested walk MAY be preserved if semantically important
- **OR** the nested walk MAY be converted to nested filtering of cached nodes
- **AND** the extraction output MUST match the original implementation

#### Scenario: Redundant Nested Walk

- **GIVEN** a nested walk re-traverses the entire tree
- **WHEN** the extractor is refactored
- **THEN** the nested walk SHALL be removed
- **AND** the outer walk SHALL be replaced with cache lookup
- **AND** the extraction output MUST match the original implementation

---

## Performance Contracts

### Target: 80-90x Speedup for Python Indexing

- **Baseline**: 18-30 seconds for 1,000 Python files (82 walks per file)
- **Target**: <1 second for 1,000 Python files (1 walk per file)
- **Node Visits**: 90,200,000 → 500,000 (180x reduction with nesting overhead)
- **Measured**: Implementation MUST measure actual speedup and document in completion report

### Memory Overhead: <10% Increase

- **Baseline**: [To be measured during verification phase]
- **Target**: Cache overhead <10% of baseline peak memory
- **Typical File**: 500-1000 nodes = ~500KB-1MB cache
- **Large File**: 5,000 nodes = ~2-3MB cache (acceptable)

### Cache Build Time: <10ms Per File

- **Operation**: Walk tree once, group nodes by type
- **Complexity**: O(n) where n = number of nodes
- **Target**: <10ms for typical file (500 nodes)
- **Measured**: Profile cache builder separately from extractor logic

---

## Testing Requirements

### Fixture Validation (Mandatory)

- **Coverage**: 100 Python files across all framework types
- **Comparison**: Byte-for-byte match of database contents (original vs optimized)
- **Exclusions**: Timing/metadata fields may differ, all extraction data must match
- **Failure Criteria**: ANY discrepancy in extracted data is a regression

### Performance Benchmarking (Mandatory)

- **Test Set**: 1,000 Python files with diverse patterns
- **Metrics**: Total time, node visits, cache build time, extraction time
- **Comparison**: Before vs after (must show 80-90x speedup)
- **Documentation**: Results documented in completion report

### Memory Profiling (Mandatory)

- **Measurement**: Peak memory usage during indexing
- **Comparison**: Before vs after (overhead must be <10%)
- **Edge Case**: Large files (10K LOC) must not cause excessive memory usage

### Edge Case Testing (Mandatory)

- **Empty Files**: Must not crash, must produce empty cache
- **Syntax Errors**: Must handle gracefully (skip extraction)
- **Large Files**: Performance and memory must remain acceptable
- **Deeply Nested**: All nodes must be captured in cache

---

## Rollback Plan

### Reversion: Fully Reversible

- **Method**: `git revert <commit_hash>`
- **Impact**: No database migrations to reverse
- **Recovery**: Immediate (1 command)
- **Data Loss**: None (no schema changes)

### Validation After Rollback

- **Test**: Run `aud index` on test project
- **Verify**: Indexing works (reverts to 82-walk implementation)
- **Confirm**: Database populated correctly
