# Design Document - Extraction Data Quality Fixes

## Context

The extraction pipeline has evolved independently across JavaScript and Python, resulting in inconsistent data formats, missing validation, and defensive code that masks bugs. This violates TheAuditor's ZERO FALLBACK POLICY and causes database constraint violations.

**Key Constraints**:
- Must maintain backward compatibility with existing database schema
- Cannot break downstream consumers (taint analysis, FCE, rules)
- Must support parallel development by multiple AIs
- Performance impact must be minimal (<5% slower)

## Goals / Non-Goals

**Goals**:
- Ensure all extractors produce schema-compliant data
- Eliminate defensive type conversions (hard fail on wrong types)
- Standardize deduplication strategies across languages
- Enable parallel AI execution for fixes

**Non-Goals**:
- Redesigning the database schema
- Changing the extraction architecture
- Adding new extraction capabilities
- Optimizing extraction performance

## Decisions

### Decision 1: Fix at Source, Not Symptom
**What**: Fix extractors to produce correct types, remove defensive conversions
**Why**: Defensive code hides bugs. Per ZERO FALLBACK POLICY, we must fail fast.
**Alternatives Considered**:
- Keep defensive conversions: Rejected - violates core principles
- Add middleware layer: Rejected - adds complexity without fixing root cause

### Decision 2: Unified Deduplication Strategy
**What**: Use Set-based deduplication with consistent keys across all languages
**Key Format**: `${file}:${line}:${source}:${target}:${type}`
**Why**: Prevents duplicate records, ensures consistency
**Alternatives Considered**:
- Database-level dedup: Rejected - too late, causes constraint errors
- No deduplication: Rejected - creates duplicate data

### Decision 3: Bidirectional Relationship Generation
**What**: All ORM extractors must generate both forward and inverse relationships
**Pattern**:
```
User.hasMany(Post) → creates:
  - User → Post (hasMany)
  - Post → User (belongsTo)
```
**Why**: Taint analysis needs complete relationship graph
**Alternatives Considered**:
- Infer at query time: Rejected - incomplete, performance impact
- Single direction only: Rejected - misses data flows

### Decision 4: Schema Validation at Boundaries
**What**: Add TypedDict validation between extraction and storage
**Implementation**: Validate in storage.py before database insert
**Why**: Catches type errors early, provides clear error messages
**Alternatives Considered**:
- No validation: Rejected - current problem
- Validate in extractors: Rejected - too many places to maintain

### Decision 5: Parallel AI Execution Design
**What**: Split fixes into independent tracks for Node and Python
**Tracks**:
- Track 1 (Node/JS): All JavaScript extractor fixes
- Track 2 (Python): Python extractor and storage fixes
- Track 3 (Testing): Integration testing after both complete
**Why**: Maximizes throughput, minimizes dependencies
**Alternatives Considered**:
- Sequential fixes: Rejected - too slow
- Single AI: Rejected - doesn't utilize available resources

## Risks / Trade-offs

### Risk 1: Deduplication Performance Impact
**Risk**: Set-based dedup might slow extraction
**Mitigation**: Use efficient Set operations, measure impact
**Acceptable Trade-off**: <5% slower for data correctness

### Risk 2: Breaking Downstream Consumers
**Risk**: Changing data format might break taint/FCE
**Mitigation**: Maintain exact same output format, only fix types
**Validation**: Run full test suite after changes

### Risk 3: Parallel Development Conflicts
**Risk**: Multiple AIs might create merge conflicts
**Mitigation**: Clear file ownership per track, no overlapping files
**Coordination**: Track 3 only starts after 1&2 complete

## Migration Plan

### Phase 1: Fix Extractors (Tracks 1 & 2)
1. Each AI works on assigned track independently
2. Commit fixes to separate branches if needed
3. No database regeneration yet

### Phase 2: Validate Fixes (Track 3)
1. Merge both tracks
2. Run full indexing on test fixtures
3. Validate data quality metrics

### Phase 3: Deploy
1. Deploy fixed code
2. Full reindex with `aud index`
3. Verify no errors in production

### Rollback Plan
1. Git revert the merge commit
2. Reindex with previous version
3. Re-add defensive code temporarily if critical

## Open Questions

None - verification phase confirmed all hypotheses. Implementation path is clear.

## Technical Specifications

### Extractor Output Schema
```python
# GraphQL Resolver Params - MUST be list of strings
params: List[str]  # NOT List[Dict]

# ORM Relationships - MUST include dedup
relationships: List[{
    'line': int,
    'source_model': str,
    'target_model': str,
    'relationship_type': str,
    'foreign_key': Optional[str],
    'cascade_delete': bool
}]

# Function Call Args
function_call_args: List[{
    'param_name': str,  # MUST be string, never dict
    'param_index': int,
    'argument_expr': str
}]
```

### Deduplication Implementation
```javascript
// JavaScript
const seen = new Set();
const key = `${line}:${sourceModel}:${targetModel}:${relType}`;
if (!seen.has(key)) {
    relationships.push({...});
    seen.add(key);
}
```

```python
# Python
seen = set()
key = (line, source_model, target_model, rel_type)
if key not in seen:
    relationships.append({...})
    seen.add(key)
```

### Validation Points
1. Extractor returns data → Validate types match schema
2. Storage receives data → Assert correct types (fail on wrong type)
3. Database insert → Constraints ensure final validation